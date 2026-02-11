"""
Auction engine for ad distribution simulation.

Implements pressure-based auction with pacing gate and organic fallback.
"""

import logging
from typing import List, Dict, Tuple
from dataclasses import dataclass
import math

logger = logging.getLogger(__name__)


@dataclass
class Ad:
    """Ad state during simulation (change: migrate-impressions-to-reach)."""
    ad_id: int
    seller_id: int
    category_id: int
    daily_budget: float  # kopecks (supports fractional kopecks)
    remaining_budget: float  # kopecks (supports fractional kopecks)
    actual_spend: float  # kopecks (float for exact tracking)
    simulated_reach: int  # RENAMED from simulated_impressions
    simulated_spending: float  # kopecks
    total_reach_historical: int  # Total historical reach (paid + organic) for organic fallback proportions
    raw_impressions_historical: int = 0  # NEW: for comparison with reach

    def __repr__(self):
        return (f"Ad(id={self.ad_id}, seller={self.seller_id}, "
                f"remaining={self.remaining_budget:.2f}, spend={self.actual_spend:.2f})")


class AuctionEngine:
    """Core auction logic with pressure-based ranking."""

    def __init__(self, config):
        """
        Initialize auction engine.

        Args:
            config: Configuration object with simulation parameters
        """
        self.config = config
        self.min_time_left_threshold = config.simulation.min_time_left_threshold
        self.min_time_progress_threshold = config.simulation.min_time_progress_threshold
        self.pacing_tolerance = config.simulation.pacing_tolerance
        self.bid_step = config.simulation.bid_step
        self.batch_size = config.simulation.batch_size

        # Organic fallback configuration (change: update-paid-eligibility-and-organic-fallback-allocation)
        organic_fallback = getattr(config.simulation, 'organic_fallback', None)
        if organic_fallback:
            self.organic_free_share = getattr(organic_fallback, 'free_share', 0.8)
            self.use_cumulative_allocator = getattr(organic_fallback, 'use_cumulative_allocator', True)
        else:
            # Fallback defaults
            self.organic_free_share = 0.8
            self.use_cumulative_allocator = True

        # Cumulative carry-over state (reset per day)
        self.carry_free = {}  # ad_id -> fractional carry
        self.carry_paid_exhausted = {}  # ad_id -> fractional carry

        # Feedback pricing controller (change: add-feedback-price-multiplier-universal-pacing)
        feedback_pricing = getattr(config.simulation, 'feedback_pricing', None)
        if feedback_pricing and getattr(feedback_pricing, 'enabled', False):
            self.feedback_pricing_enabled = True
            self.feedback_Kp = getattr(feedback_pricing, 'Kp', 0.05)
            self.feedback_Ki = getattr(feedback_pricing, 'Ki', 0.02)
            self.feedback_multiplier_min = getattr(feedback_pricing, 'multiplier_min', 0.5)
            self.feedback_multiplier_max = getattr(feedback_pricing, 'multiplier_max', 3.0)
            self.feedback_multiplier_initial = getattr(feedback_pricing, 'multiplier_initial', 1.0)
            self.feedback_delta_limit = getattr(feedback_pricing, 'delta_limit', 0.3)
            self.feedback_integral_min = getattr(feedback_pricing, 'integral_min', -1.0)
            self.feedback_integral_max = getattr(feedback_pricing, 'integral_max', 1.0)
            self.feedback_alpha = getattr(feedback_pricing, 'alpha', 0.7)
            self.feedback_update_cadence = getattr(feedback_pricing, 'update_cadence', 'hourly')

            target_curve_config = getattr(feedback_pricing, 'target_curve', None)
            self.feedback_target_curve_shape = getattr(target_curve_config, 'shape', 'linear') if target_curve_config else 'linear'
        else:
            self.feedback_pricing_enabled = False
            # Set default curve shape for cascade (even when feedback pricing disabled)
            self.feedback_target_curve_shape = 'linear'

        # Controller state: {(category_id, date): {'multiplier': float, 'integral': float, 'last_spend': float}}
        self.controller_state = {}

        # Cascading win cap configuration (change: add-cascading-win-cap-and-pacing)
        cascading_win_cap = getattr(config.simulation, 'cascading_win_cap', None)
        if cascading_win_cap and getattr(cascading_win_cap, 'enabled', False):
            self.cascade_enabled = True

            # Parse cap thresholds
            cap_thresholds_config = getattr(cascading_win_cap, 'cap_thresholds', [])
            # Convert to list of (ratio, cap) tuples, sorted by ratio descending
            # Note: thresholds are dicts, not Config objects
            self.cascade_cap_thresholds = sorted(
                [(t.get('ratio', 1.0) if isinstance(t, dict) else getattr(t, 'ratio', 1.0),
                  t.get('cap', 1) if isinstance(t, dict) else getattr(t, 'cap', 1))
                 for t in cap_thresholds_config],
                key=lambda x: x[0],
                reverse=True
            )
            self.cascade_max_cap = getattr(cascading_win_cap, 'max_win_per_ad_cap', 4)

            # Pacing relaxation config
            pacing_relaxation = getattr(cascading_win_cap, 'pacing_relaxation', None)
            if pacing_relaxation and getattr(pacing_relaxation, 'enabled', False):
                self.cascade_pacing_relax_enabled = True
                self.cascade_fallback_hours = getattr(pacing_relaxation, 'fallback_hours', 2)
                self.cascade_under_spend_threshold = getattr(pacing_relaxation, 'under_spend_threshold', 0.85)
                self.cascade_tolerance_increment = getattr(pacing_relaxation, 'tolerance_increment', 0.1)
                self.cascade_tolerance_max = getattr(pacing_relaxation, 'tolerance_max', 0.5)
            else:
                self.cascade_pacing_relax_enabled = False
        else:
            self.cascade_enabled = False

        # Cascade state: {(category_id, date): {'under_spend_streak': int, 'win_per_ad_cap': int, 'pacing_tolerance_adjusted': float}}
        self.cascade_state = {}

    def reset_carry_state(self):
        """Reset cumulative carry-over state (call at day boundary)."""
        self.carry_free = {}
        self.carry_paid_exhausted = {}

    def reset_controller_state_for_day(self, category_id: int, date: str):
        """
        Reset controller state for a specific category/day.

        Args:
            category_id: Category ID
            date: Date string (YYYY-MM-DD)
        """
        key = (category_id, date)
        if self.feedback_pricing_enabled:
            self.controller_state[key] = {
                'multiplier': self.feedback_multiplier_initial,
                'integral': 0.0,
                'last_spend': 0.0
            }

    def calculate_target_spend(self, total_budget: float, time_progress: float) -> float:
        """
        Calculate target cumulative spend based on time progress and curve shape.

        Args:
            total_budget: Total daily budget (kopecks)
            time_progress: Fraction of day elapsed (0.0 to 1.0)

        Returns:
            Target cumulative spend (kopecks)
        """
        if self.feedback_target_curve_shape == 'linear':
            return total_budget * time_progress
        elif self.feedback_target_curve_shape == 'front_loaded':
            # Spend faster early: T_t = B * (t^0.8)
            return total_budget * (time_progress ** 0.8)
        elif self.feedback_target_curve_shape == 'back_loaded':
            # Spend slower early: T_t = B * (t^1.2)
            return total_budget * (time_progress ** 1.2)
        else:
            # Default to linear
            return total_budget * time_progress

    def update_price_multiplier(
        self,
        category_id: int,
        date: str,
        total_budget: float,
        cumulative_spend: float,
        time_progress: float
    ) -> Dict[str, float]:
        """
        Update price multiplier using PI feedback controller.

        Args:
            category_id: Category ID
            date: Date string (YYYY-MM-DD)
            total_budget: Total daily budget for category (kopecks)
            cumulative_spend: Actual cumulative spend so far (kopecks)
            time_progress: Fraction of day elapsed (0.0 to 1.0)

        Returns:
            Dict with controller diagnostics: {
                'multiplier': float,
                'error': float,
                'integral': float,
                'target_spend': float,
                'actual_spend': float,
                'control_signal': float,
                'clamped': bool
            }
        """
        if not self.feedback_pricing_enabled:
            return {
                'multiplier': 1.0,
                'error': 0.0,
                'integral': 0.0,
                'target_spend': 0.0,
                'actual_spend': cumulative_spend,
                'control_signal': 0.0,
                'clamped': False
            }

        key = (category_id, date)
        if key not in self.controller_state:
            self.reset_controller_state_for_day(category_id, date)

        state = self.controller_state[key]

        # Calculate target and error
        target_spend = self.calculate_target_spend(total_budget, time_progress)
        error = target_spend - cumulative_spend  # Positive = under-spending, negative = over-spending

        # Update integral with anti-windup
        new_integral = state['integral'] + error
        new_integral = max(self.feedback_integral_min, min(self.feedback_integral_max, new_integral))

        # PI control signal
        control_signal = self.feedback_Kp * error + self.feedback_Ki * new_integral

        # Update multiplier using exponential scaling
        # multiplier_new = multiplier_old * exp(control_signal)
        multiplier_raw = state['multiplier'] * math.exp(control_signal)

        # Apply delta limit (prevent large jumps)
        max_delta = state['multiplier'] * self.feedback_delta_limit
        multiplier_limited = max(
            state['multiplier'] - max_delta,
            min(state['multiplier'] + max_delta, multiplier_raw)
        )

        # Apply bounds
        multiplier_bounded = max(
            self.feedback_multiplier_min,
            min(self.feedback_multiplier_max, multiplier_limited)
        )

        clamped = (multiplier_bounded != multiplier_raw)

        # Apply EMA smoothing
        multiplier_smoothed = (
            self.feedback_alpha * multiplier_bounded +
            (1 - self.feedback_alpha) * state['multiplier']
        )

        # Update state
        state['multiplier'] = multiplier_smoothed
        state['integral'] = new_integral
        state['last_spend'] = cumulative_spend

        return {
            'multiplier': multiplier_smoothed,
            'error': error,
            'integral': new_integral,
            'target_spend': target_spend,
            'actual_spend': cumulative_spend,
            'control_signal': control_signal,
            'clamped': clamped
        }

    def get_price_multiplier(self, category_id: int, date: str) -> float:
        """
        Get current price multiplier for category/day.

        Args:
            category_id: Category ID
            date: Date string (YYYY-MM-DD)

        Returns:
            Current multiplier value (default 1.0 if disabled or not initialized)
        """
        if not self.feedback_pricing_enabled:
            return 1.0

        key = (category_id, date)
        if key not in self.controller_state:
            return self.feedback_multiplier_initial

        return self.controller_state[key]['multiplier']

    def reset_cascade_state_for_day(self, category_id: int, date: str):
        """
        Reset cascade state for a specific category/day.

        Args:
            category_id: Category ID
            date: Date string (YYYY-MM-DD)
        """
        key = (category_id, date)
        self.cascade_state[key] = {
            'under_spend_streak': 0,
            'win_per_ad_cap': 1,  # Default: 1 win per ad
            'pacing_tolerance_adjusted': self.pacing_tolerance  # Start with base tolerance
        }

    def evaluate_cascade(
        self,
        category_id: int,
        date: str,
        total_budget: float,
        cumulative_spend: float,
        time_progress: float
    ) -> Dict:
        """
        Evaluate cascading win cap and pacing relaxation based on under-spend.

        Args:
            category_id: Category ID
            date: Date string (YYYY-MM-DD)
            total_budget: Total daily budget for category (kopecks)
            cumulative_spend: Cumulative spend so far (kopecks)
            time_progress: Fraction of day elapsed (0.0 to 1.0)

        Returns:
            Dict with: win_per_ad_cap, pacing_tolerance_adjusted, under_spend_ratio, under_spend_streak
        """
        if not self.cascade_enabled:
            return {
                'win_per_ad_cap': 1,
                'pacing_tolerance_adjusted': self.pacing_tolerance,
                'under_spend_ratio': 1.0,
                'under_spend_streak': 0,
                'cascade_applied': False
            }

        # Initialize state if needed
        key = (category_id, date)
        if key not in self.cascade_state:
            self.reset_cascade_state_for_day(category_id, date)

        state = self.cascade_state[key]

        # Calculate target spend using same curve as feedback pricing
        target_spend = self.calculate_target_spend(total_budget, time_progress) if total_budget > 0 else 0.0

        # Calculate under-spend ratio
        if target_spend > 0:
            under_spend_ratio = cumulative_spend / target_spend
        else:
            under_spend_ratio = 1.0  # No budget = no under-spend

        # Check if under-spending this hour
        is_under_spending = under_spend_ratio < self.cascade_under_spend_threshold if self.cascade_pacing_relax_enabled else False

        # Update streak
        if is_under_spending:
            state['under_spend_streak'] += 1
        else:
            state['under_spend_streak'] = 0  # Reset streak

        # Determine win_per_ad_cap based on thresholds
        # Iterate descending (highest ratio first) and update cap while under-spending
        # Stop when we reach a threshold we're NOT below
        win_per_ad_cap = 1  # Default
        for ratio_threshold, cap in sorted(self.cascade_cap_thresholds, key=lambda x: x[0], reverse=True):
            if under_spend_ratio < ratio_threshold:
                win_per_ad_cap = cap  # We're below this threshold, use this cap
            else:
                break  # We're NOT below this threshold, stop (use previous cap)

        # Clamp to max
        win_per_ad_cap = min(win_per_ad_cap, self.cascade_max_cap)

        # Determine pacing tolerance adjustment
        pacing_tolerance_adjusted = self.pacing_tolerance

        if self.cascade_pacing_relax_enabled and state['under_spend_streak'] >= self.cascade_fallback_hours:
            # Relax pacing: increase tolerance by increment per hour beyond fallback threshold
            hours_beyond = state['under_spend_streak'] - self.cascade_fallback_hours + 1
            pacing_tolerance_adjusted = min(
                self.pacing_tolerance + hours_beyond * self.cascade_tolerance_increment,
                self.cascade_tolerance_max
            )

        # Update state
        state['win_per_ad_cap'] = win_per_ad_cap
        state['pacing_tolerance_adjusted'] = pacing_tolerance_adjusted

        return {
            'win_per_ad_cap': win_per_ad_cap,
            'pacing_tolerance_adjusted': pacing_tolerance_adjusted,
            'under_spend_ratio': under_spend_ratio,
            'under_spend_streak': state['under_spend_streak'],
            'target_spend': target_spend,
            'actual_spend': cumulative_spend,
            'cascade_applied': (win_per_ad_cap > 1 or pacing_tolerance_adjusted > self.pacing_tolerance)
        }

    def get_win_per_ad_cap(self, category_id: int, date: str) -> int:
        """
        Get current win_per_ad_cap for category/day.

        Args:
            category_id: Category ID
            date: Date string (YYYY-MM-DD)

        Returns:
            Current win_per_ad_cap (default 1 if disabled or not initialized)
        """
        if not self.cascade_enabled:
            return 1

        key = (category_id, date)
        if key not in self.cascade_state:
            return 1

        return self.cascade_state[key]['win_per_ad_cap']

    def get_adjusted_pacing_tolerance(self, category_id: int, date: str) -> float:
        """
        Get current adjusted pacing tolerance for category/day.

        Args:
            category_id: Category ID
            date: Date string (YYYY-MM-DD)

        Returns:
            Current adjusted pacing tolerance (default to base pacing_tolerance)
        """
        if not self.cascade_enabled:
            return self.pacing_tolerance

        key = (category_id, date)
        if key not in self.cascade_state:
            return self.pacing_tolerance

        return self.cascade_state[key]['pacing_tolerance_adjusted']

    def calculate_pressure(self, ad: Ad, time_left: float) -> float:
        """
        Calculate pressure for ad based on remaining budget and time.

        Args:
            ad: Ad object with budget state
            time_left: Fraction of day remaining (0.0 to 1.0)

        Returns:
            Pressure value (higher = more urgent to spend)
        """
        if ad.remaining_budget <= 0:
            return 0.0

        # Use minimum threshold to prevent division by near-zero values
        # NOTE: With hourly updates (hour ∈ [0,23]), min time_left = 0.042 > 0.001
        # This threshold serves as safety net for edge cases and future implementations
        safe_time_left = max(time_left, self.min_time_left_threshold)
        pressure = ad.remaining_budget / safe_time_left

        return pressure

    def check_pacing_gate(
        self,
        ad: Ad,
        time_progress: float,
        category_id: int = None,
        date: str = None
    ) -> bool:
        """
        Check if ad is within pacing limits with cascading tolerance adjustment.

        Args:
            ad: Ad object with budget and spend state
            time_progress: Fraction of day elapsed (0.0 to 1.0)
            category_id: Category ID (for cascade adjustment, change: add-cascading-win-cap-and-pacing)
            date: Date string YYYY-MM-DD (for cascade adjustment)

        Returns:
            True if ad is eligible (within pacing limits), False if paused
        """
        if ad.daily_budget <= 0:
            return True  # No budget = always eligible (simulated organic)

        # Apply minimum threshold to prevent zero max_allowed at hour 0
        # NOTE: At hour 0, time_progress=0.0 < 0.042, so threshold is applied
        # This allows ads to spend ~5% of budget in first hour
        safe_time_progress = max(time_progress, self.min_time_progress_threshold)

        # Get adjusted pacing tolerance (change: add-cascading-win-cap-and-pacing)
        pacing_tolerance = self.pacing_tolerance
        if self.cascade_enabled and category_id is not None and date is not None:
            pacing_tolerance = self.get_adjusted_pacing_tolerance(category_id, date)

        expected_spend = ad.daily_budget * safe_time_progress
        max_allowed = expected_spend * (1 + pacing_tolerance)

        is_eligible = ad.actual_spend <= max_allowed

        if not is_eligible:
            logger.debug(f"Ad {ad.ad_id} paused by pacing gate: "
                         f"spend={ad.actual_spend:.2f} > max_allowed={max_allowed:.2f} "
                         f"(tolerance={pacing_tolerance:.2f})")

        return is_eligible

    def rank_ads(
        self,
        ads: List[Ad],
        time_progress: float,
        time_left: float,
        logger=None,
        batch_number: int = None,
        category_id: int = None,
        hour: int = None,
        date: str = None
    ) -> List[Tuple[Ad, float, float, int]]:
        """
        Rank ads by pressure and calculate effective bids with cascade support.

        Args:
            ads: List of all ads
            time_progress: Fraction of day elapsed
            time_left: Fraction of day remaining
            logger: SimulationLogger instance
            batch_number: Batch number for logging
            category_id: Category ID for logging and cascade
            hour: Hour for logging
            date: Date string YYYY-MM-DD (for cascade, change: add-cascading-win-cap-and-pacing)

        Returns:
            List of tuples: (ad, pressure, effective_bid, rank_index)
            Sorted by pressure descending (highest first)
        """
        # Get adjusted pacing tolerance for logging (change: add-cascading-win-cap-and-pacing)
        pacing_tolerance_for_logging = self.pacing_tolerance
        if self.cascade_enabled and category_id is not None and date is not None:
            pacing_tolerance_for_logging = self.get_adjusted_pacing_tolerance(category_id, date)

        # Calculate pressure and apply pacing gate
        ad_pressure = []
        paused_ads = []

        for ad in ads:
            is_eligible = self.check_pacing_gate(ad, time_progress, category_id, date)
            if is_eligible:
                pressure = self.calculate_pressure(ad, time_left)
            else:
                pressure = 0.0  # Paused by pacing gate
                if ad.daily_budget > 0:  # Only log for ads with budget
                    expected_spend = ad.daily_budget * time_progress
                    max_allowed = expected_spend * (1 + pacing_tolerance_for_logging)
                    paused_ads.append({
                        'ad_id': ad.ad_id,
                        'actual_spend': ad.actual_spend,
                        'expected_spend': expected_spend,
                        'max_allowed': max_allowed
                    })

            ad_pressure.append((ad, pressure))

        # Log pacing exclusions
        if logger and self.config.logging.log_pacing_events and paused_ads:
            for paused_info in paused_ads:
                logger.log_event('pacing_exclusion', {
                    'batch': batch_number,
                    'ad_id': paused_info['ad_id'],
                    'reason': 'exceeded_pacing_limit',
                    'actual_spend': paused_info['actual_spend'],
                    'expected_spend': paused_info['expected_spend'],
                    'max_allowed': paused_info['max_allowed'],
                    'pacing_tolerance': pacing_tolerance_for_logging
                })

        # Sort by pressure descending, then by ad_id ascending (deterministic tie-breaking)
        ad_pressure.sort(key=lambda x: (-x[1], x[0].ad_id))

        # Assign rank_index and calculate effective_bid
        N = len(ad_pressure)
        ranked = []

        for rank_index, (ad, pressure) in enumerate(ad_pressure):
            # effective_bid = min_bid + (N - 1 - rank_index) * bid_step
            # Note: min_bid is per-category and passed separately during winner selection
            ranked.append((ad, pressure, rank_index))

        return ranked

    def select_winners(
        self,
        ranked_ads: List[Tuple[Ad, float, int]],
        min_bid: float,
        slots: int,
        category_id: int = None,
        date: str = None,
        win_per_ad_cap: int = 1
    ) -> List[Tuple[Ad, float, int]]:
        """
        Select top N winners by effective bid with cascading win cap.

        Args:
            ranked_ads: List of (ad, pressure, rank_index) tuples
            min_bid: Minimum bid for category (kopecks)
            slots: Number of reach slots available
            category_id: Category ID (for feedback pricing multiplier)
            date: Date string YYYY-MM-DD (for feedback pricing multiplier)
            win_per_ad_cap: Max wins per ad in this batch (change: add-cascading-win-cap-and-pacing)

        Returns:
            List of (ad, effective_bid, reach_won) tuples
        """
        # Count only ads with budget > 0 (ads that can actually pay)
        ads_with_budget_count = sum(1 for ad, _, _ in ranked_ads if ad.remaining_budget > 0)
        N = max(ads_with_budget_count, 1)  # Prevent edge case where N=0

        logger.debug(f"Effective bid calculation: N={N} ads with budget (out of {len(ranked_ads)} total), win_per_ad_cap={win_per_ad_cap}")

        # Get price multiplier for feedback pricing (change: add-feedback-price-multiplier-universal-pacing)
        price_multiplier = self.get_price_multiplier(category_id, date) if (category_id and date) else 1.0

        winners = []
        ad_win_count = {}  # Track wins per ad in this batch

        slots_remaining = slots

        # Iterate through ranked ads cyclically until slots are filled or no eligible ads remain
        while slots_remaining > 0:
            made_progress = False

            for ad, pressure, rank_index in ranked_ads:
                if slots_remaining <= 0:
                    break

                # Check if ad has budget and hasn't reached cap
                if ad.remaining_budget <= 0:
                    continue

                current_wins = ad_win_count.get(ad.ad_id, 0)
                if current_wins >= win_per_ad_cap:
                    continue

                # Ad is eligible for another win
                made_progress = True

                # Calculate base effective_bid (convert min_bid to float for arithmetic)
                base_effective_bid = float(min_bid) + (N - 1 - rank_index) * self.bid_step

                # Apply price multiplier (Task 2.3: apply multiplier to bid calculation)
                effective_bid = base_effective_bid * price_multiplier

                # Award 1 reach slot
                reach_won = 1
                winners.append((ad, effective_bid, reach_won))

                # Update tracking
                ad_win_count[ad.ad_id] = current_wins + 1
                slots_remaining -= 1

            # If no progress made (all ads either out of budget or at cap), stop
            if not made_progress:
                break

        return winners

    def charge_winners(
        self,
        winners: List[Tuple[Ad, float, int]]
    ):
        """
        Charge winners and update ad state.

        Args:
            winners: List of (ad, effective_bid, reach_won) tuples

        Side effects:
            Updates ad.remaining_budget, ad.actual_spend, ad.simulated_reach
        """
        for ad, effective_bid, reach_won in winners:
            if ad.remaining_budget > 0:
                # Calculate cost in fractional kopecks (no rounding)
                cost = effective_bid * reach_won

                # Cap charge by remaining budget to prevent overspend (Task 4.1)
                charged = min(cost, ad.remaining_budget)

                # Deduct from remaining budget (float, supports fractional kopecks)
                ad.remaining_budget -= charged

                # Track exact spend (float for reporting)
                ad.actual_spend += charged
                ad.simulated_spending += charged
            else:
                # Ad has budget=0, this is simulated organic reach
                pass

            ad.simulated_reach += reach_won

    def run_batch_auction(
        self,
        ads: List[Ad],
        min_bid: float,
        time_progress: float,
        time_left: float,
        batch_slots: int,
        category_id: int = None,
        date: str = None,
        hour: int = None,
        batch_number: int = None,
        logger=None,
        win_per_ad_cap: int = 1
    ) -> int:
        """
        Run one batch auction.

        Args:
            ads: List of all ads
            min_bid: Minimum bid for category
            time_progress: Fraction of day elapsed
            time_left: Fraction of day remaining
            batch_slots: Number of slots to allocate
            category_id: Category ID for logging and feedback pricing
            date: Date string YYYY-MM-DD for feedback pricing
            hour: Hour for logging
            batch_number: Batch number for logging
            logger: SimulationLogger instance

        Returns:
            Number of slots allocated
        """
        # Count ads with budget
        ads_with_budget = sum(1 for ad in ads if ad.remaining_budget > 0)

        # Log batch start
        if logger:
            logger.log_event('batch_start', {
                'batch': batch_number,
                'category_id': category_id,
                'hour': hour,
                'slots': batch_slots,
                'eligible_ads': len(ads),
                'ads_with_budget': ads_with_budget,
                'time_progress': time_progress,
                'time_left': time_left
            })

        # Rank ads (includes pacing gate logging and cascade pacing adjustment)
        ranked = self.rank_ads(
            ads,
            time_progress,
            time_left,
            logger=logger,
            batch_number=batch_number,
            category_id=category_id,
            hour=hour,
            date=date
        )

        # Select winners (with feedback pricing multiplier and cascading win cap)
        winners = self.select_winners(
            ranked,
            min_bid,
            batch_slots,
            category_id,
            date,
            win_per_ad_cap=win_per_ad_cap
        )

        # Log batch winner summary with N value (use module logger, not param logger)
        if batch_number and category_id and hour is not None:
            module_logger = logging.getLogger(__name__)
            module_logger.info(f"Batch {batch_number} (cat={category_id}, hour={hour}): "
                              f"{len(winners)} winners, N={ads_with_budget} ads with budget "
                              f"(out of {len(ads)} total)")

        # Log auction winners (top-N)
        if logger and winners:
            top_n = self.config.logging.log_top_n_winners
            top_winners = []

            for ad, effective_bid, reach_won in winners[:top_n]:
                # Find rank_index from ranked list
                rank_index = next((rank for a, p, rank in ranked if a.ad_id == ad.ad_id), 0)
                pressure = next((p for a, p, rank in ranked if a.ad_id == ad.ad_id), 0.0)

                top_winners.append({
                    'ad_id': ad.ad_id,
                    'seller_id': ad.seller_id,
                    'pressure': pressure,
                    'rank': rank_index,
                    'bid': effective_bid,
                    'remaining_budget': ad.remaining_budget,
                    'reach_won': reach_won
                })

            logger.log_event('auction_winners', {
                'batch': batch_number,
                'category_id': category_id,
                'hour': hour,
                'top_winners': top_winners,
                'total_winners': len(winners)
            })

        # Track budgets before charging for exhaustion detection
        budgets_before = {ad.ad_id: ad.remaining_budget for ad, _, _ in winners}

        # Charge winners
        self.charge_winners(winners)

        # Log budget exhaustion events
        if logger and self.config.logging.log_budget_events:
            for ad, effective_bid, reach_won in winners:
                if budgets_before[ad.ad_id] > 0 and ad.remaining_budget == 0:
                    logger.log_event('budget_exhaustion', {
                        'batch': batch_number,
                        'ad_id': ad.ad_id,
                        'seller_id': ad.seller_id,
                        'category_id': category_id,
                        'hour': hour,
                        'initial_budget': ad.daily_budget,
                        'total_spent': ad.simulated_spending,
                        'reach_won': ad.simulated_reach,
                        'time_progress': time_progress
                    })

        # Log batch complete
        if logger:
            remaining_slots = batch_slots - len(winners)
            logger.log_event('batch_complete', {
                'batch': batch_number,
                'allocated': len(winners),
                'remaining_slots': remaining_slots
            })

        return len(winners)

    def distribute_organic_proportional(
        self,
        ads: List[Ad],
        remaining_slots: int,
        category_id: int = None,
        hour: int = None,
        sim_logger=None
    ):
        """
        Distribute remaining slots proportionally by historical total reach.

        IMPORTANT: This is a SIMULATION-ONLY mechanism. In production, organic reach
        distribution happens naturally through user behavior, not algorithmically.

        Uses formal 6-step algorithm from specs to guarantee conservation.

        Includes ALL ads in distribution:
        - Free ads (daily_budget=0): Always eligible for organic
        - Paid ads with exhausted budget (remaining_budget=0): Can receive organic
        - Paid ads blocked by pacing gate (pressure=0): Can receive organic if budget exhausted

        Proportional allocation is based on historical total reach (paid + organic)
        from the time range being simulated. This ensures ads popular when promoted
        also receive organic reach when budget exhausts, reflecting overall ad popularity.

        Args:
            ads: List of all ads (paid + free, regardless of budget state)
            remaining_slots: Number of slots to distribute
            category_id: Category ID for logging
            hour: Hour for logging
            sim_logger: SimulationLogger instance

        Side effects:
            Updates ad.simulated_reach for allocated ads
        """
        if remaining_slots <= 0:
            return

        # Calculate total historical reach (paid + organic) for proportional allocation
        total_reach_sum = sum(ad.total_reach_historical for ad in ads)

        if total_reach_sum == 0:
            # Fallback to equal distribution
            logger.warning("No historical total reach, using equal distribution")
            self.distribute_organic_equal(ads, remaining_slots, category_id, hour, sim_logger)
            return

        # Step 1: Calculate proportions
        proportions = [
            (ad, ad.total_reach_historical / total_reach_sum)
            for ad in ads
        ]

        # Step 2: Base allocation (floor)
        allocations = {}
        total_allocated = 0

        for ad, proportion in proportions:
            base = math.floor(remaining_slots * proportion)
            allocations[ad.ad_id] = base
            total_allocated += base

        # Step 3: Calculate remainder
        remainder = remaining_slots - total_allocated

        # Conservation check
        assert remainder >= 0, f"Negative remainder: {remainder}"

        # Step 4: Sort by proportion descending (deterministic tie-breaking by ad_id)
        proportions.sort(key=lambda x: (-x[1], x[0].ad_id))

        # Step 5 & 6: Distribute remainder
        for i, (ad, proportion) in enumerate(proportions):
            if i < remainder:
                allocations[ad.ad_id] += 1

        # Update ad reach
        for ad in ads:
            allocated = allocations.get(ad.ad_id, 0)
            ad.simulated_reach += allocated

        # Validation: conservation guarantee
        total_allocated = sum(allocations.values())
        is_valid = total_allocated == remaining_slots

        if not is_valid:
            logger.error(f"Conservation violated: {total_allocated} != {remaining_slots}")

        # Log organic fallback
        if sim_logger:
            allocation_list = [
                {
                    'ad_id': ad.ad_id,
                    'total_reach_historical': ad.total_reach_historical,
                    'allocated': allocations.get(ad.ad_id, 0)
                }
                for ad in ads if allocations.get(ad.ad_id, 0) > 0
            ]

            sim_logger.log_event('organic_fallback', {
                'category_id': category_id,
                'hour': hour,
                'remaining_slots': remaining_slots,
                'method': 'proportional',
                'allocations': allocation_list,
                'conservation_check': {
                    'expected': remaining_slots,
                    'actual': total_allocated,
                    'valid': is_valid
                }
            })

        logger.info(f"Distributed {remaining_slots} organic slots proportionally across {len(ads)} ads")

    def distribute_organic_equal(
        self,
        ads: List[Ad],
        remaining_slots: int,
        category_id: int = None,
        hour: int = None,
        sim_logger=None
    ):
        """
        Distribute remaining slots equally (fallback when no organic history).

        Uses formal 4-step algorithm from specs to guarantee conservation.

        Args:
            ads: List of all ads
            remaining_slots: Number of slots to distribute
            category_id: Category ID for logging
            hour: Hour for logging
            sim_logger: SimulationLogger instance

        Side effects:
            Updates ad.simulated_reach for allocated ads
        """
        if remaining_slots <= 0:
            return

        if len(ads) == 0:
            logger.error(f"Cannot distribute {remaining_slots} slots: no ads available")
            return

        # Step 1: Base allocation
        base = math.floor(remaining_slots / len(ads))

        # Step 2: Calculate remainder
        remainder = remaining_slots % len(ads)

        # Step 3: Sort by ad_id ascending (deterministic)
        sorted_ads = sorted(ads, key=lambda x: x.ad_id)

        # Step 4: Distribute
        allocations = {}
        for i, ad in enumerate(sorted_ads):
            allocation = base + (1 if i < remainder else 0)
            ad.simulated_reach += allocation
            allocations[ad.ad_id] = allocation

        # Validation: conservation guarantee
        total_allocated = base * len(ads) + remainder
        is_valid = total_allocated == remaining_slots

        if not is_valid:
            logger.error(f"Conservation violated: {total_allocated} != {remaining_slots}")

        # Log organic fallback
        if sim_logger:
            allocation_list = [
                {
                    'ad_id': ad.ad_id,
                    'organic_historical': 0,
                    'allocated': allocations.get(ad.ad_id, 0)
                }
                for ad in sorted_ads if allocations.get(ad.ad_id, 0) > 0
            ]

            sim_logger.log_event('organic_fallback', {
                'category_id': category_id,
                'hour': hour,
                'remaining_slots': remaining_slots,
                'method': 'equal',
                'allocations': allocation_list,
                'conservation_check': {
                    'expected': remaining_slots,
                    'actual': total_allocated,
                    'valid': is_valid
                }
            })

        logger.warning(f"Distributed {remaining_slots} organic slots equally across {len(ads)} ads "
                       f"(base={base}, remainder={remainder})")

    def distribute_organic_with_pool_split(
        self,
        ads: List[Ad],
        remaining_slots: int,
        category_id: int = None,
        hour: int = None,
        sim_logger=None
    ):
        """
        Distribute remaining slots with pool split: free ads vs paid-exhausted ads.

        Uses cumulative carry-over allocator to preserve fractional allocations across batches,
        significantly improving coverage for long-tail ads.

        Pool split (configurable):
        - free_share (default 0.8 = 80%) for ads with daily_budget=0
        - paid_exhausted_share (1 - free_share = 20%) for ads with budget>0 but remaining_budget=0

        Args:
            ads: List of all ads
            remaining_slots: Number of slots to distribute
            category_id: Category ID for logging
            hour: Hour for logging
            sim_logger: SimulationLogger instance

        Side effects:
            Updates ad.simulated_reach for allocated ads
            Updates self.carry_free and self.carry_paid_exhausted state
        """
        if remaining_slots <= 0:
            return

        # Split ads into pools
        free_ads = [ad for ad in ads if ad.daily_budget == 0]
        paid_exhausted = [ad for ad in ads if ad.daily_budget > 0 and ad.remaining_budget == 0]

        # Calculate pool allocations
        free_slots = round(remaining_slots * self.organic_free_share)
        paid_exhausted_slots = remaining_slots - free_slots

        logger.debug(f"Pool split: {free_slots} free, {paid_exhausted_slots} paid_exhausted "
                     f"(total={remaining_slots}, free_share={self.organic_free_share})")

        # Allocate to each pool using cumulative allocator
        free_allocations = {}
        paid_exhausted_allocations = {}

        if free_slots > 0 and len(free_ads) > 0:
            free_allocations = self._cumulative_allocate(
                free_ads,
                free_slots,
                self.carry_free,
                pool_name='free'
            )

        if paid_exhausted_slots > 0 and len(paid_exhausted) > 0:
            paid_exhausted_allocations = self._cumulative_allocate(
                paid_exhausted,
                paid_exhausted_slots,
                self.carry_paid_exhausted,
                pool_name='paid_exhausted'
            )

        # Task 3.3: Reassign slots when one pool is empty (preserve conservation)
        free_allocated = sum(free_allocations.values())
        paid_exhausted_allocated = sum(paid_exhausted_allocations.values())

        # If free pool got slots but couldn't use them (pool empty), reassign to paid_exhausted
        if free_slots > free_allocated and len(paid_exhausted) > 0:
            unallocated_free = free_slots - free_allocated
            logger.debug(f"Reassigning {unallocated_free} unallocated free slots to paid_exhausted pool")
            additional_allocations = self._cumulative_allocate(
                paid_exhausted,
                unallocated_free,
                self.carry_paid_exhausted,
                pool_name='paid_exhausted_reassigned'
            )
            for ad_id, amount in additional_allocations.items():
                paid_exhausted_allocations[ad_id] = paid_exhausted_allocations.get(ad_id, 0) + amount

        # If paid_exhausted pool got slots but couldn't use them, reassign to free
        if paid_exhausted_slots > paid_exhausted_allocated and len(free_ads) > 0:
            unallocated_paid = paid_exhausted_slots - paid_exhausted_allocated
            logger.debug(f"Reassigning {unallocated_paid} unallocated paid_exhausted slots to free pool")
            additional_allocations = self._cumulative_allocate(
                free_ads,
                unallocated_paid,
                self.carry_free,
                pool_name='free_reassigned'
            )
            for ad_id, amount in additional_allocations.items():
                free_allocations[ad_id] = free_allocations.get(ad_id, 0) + amount

        # Apply allocations
        for ad in ads:
            allocated = free_allocations.get(ad.ad_id, 0) + paid_exhausted_allocations.get(ad.ad_id, 0)
            ad.simulated_reach += allocated

        # Validation: conservation
        total_allocated = sum(free_allocations.values()) + sum(paid_exhausted_allocations.values())
        is_valid = total_allocated == remaining_slots

        if not is_valid:
            logger.error(f"Conservation violated: {total_allocated} != {remaining_slots}")

        # Logging
        if sim_logger:
            allocation_list = []
            for ad in ads:
                allocated = free_allocations.get(ad.ad_id, 0) + paid_exhausted_allocations.get(ad.ad_id, 0)
                if allocated > 0:
                    pool = 'free' if ad.ad_id in free_allocations else 'paid_exhausted'
                    allocation_list.append({
                        'ad_id': ad.ad_id,
                        'pool': pool,
                        'total_reach_historical': ad.total_reach_historical,
                        'allocated': allocated
                    })

            sim_logger.log_event('organic_fallback', {
                'category_id': category_id,
                'hour': hour,
                'remaining_slots': remaining_slots,
                'method': 'pool_split_cumulative',
                'free_share': self.organic_free_share,
                'free_slots': free_slots,
                'paid_exhausted_slots': paid_exhausted_slots,
                'free_ads_count': len(free_ads),
                'paid_exhausted_count': len(paid_exhausted),
                'free_allocated': sum(free_allocations.values()),
                'paid_exhausted_allocated': sum(paid_exhausted_allocations.values()),
                'allocations': allocation_list[:20],  # Limit to 20 for log size
                'conservation_check': {
                    'expected': remaining_slots,
                    'actual': total_allocated,
                    'valid': is_valid
                }
            })

        logger.info(f"Distributed {remaining_slots} organic slots: "
                    f"{sum(free_allocations.values())} to {len(free_allocations)} free ads, "
                    f"{sum(paid_exhausted_allocations.values())} to {len(paid_exhausted_allocations)} paid-exhausted ads")

    def _cumulative_allocate(
        self,
        ads: List[Ad],
        slots: int,
        carry_state: Dict[int, float],
        pool_name: str = None
    ) -> Dict[int, int]:
        """
        Cumulative carry-over allocator for proportional distribution.

        Preserves fractional allocations across batches to improve coverage for long-tail ads.

        Algorithm:
        1. For each ad: carry[ad_id] += slots * proportion
        2. base_allocation = floor(carry[ad_id])
        3. carry[ad_id] -= base_allocation (keep fractional part)
        4. If residual slots remain, allocate by highest carry (tie-break by ad_id asc)

        Args:
            ads: List of ads to allocate to
            slots: Number of slots to distribute
            carry_state: Mutable dict of ad_id -> fractional carry (updated in-place)
            pool_name: Pool name for logging

        Returns:
            Dict of ad_id -> allocated_slots
        """
        if slots <= 0 or len(ads) == 0:
            return {}

        # Calculate proportions based on historical total reach
        total_reach_sum = sum(ad.total_reach_historical for ad in ads)

        if total_reach_sum == 0:
            # Equal distribution fallback
            base = slots // len(ads)
            remainder = slots % len(ads)
            allocations = {}
            sorted_ads = sorted(ads, key=lambda x: x.ad_id)
            for i, ad in enumerate(sorted_ads):
                allocations[ad.ad_id] = base + (1 if i < remainder else 0)
            return allocations

        # Step 1: Add proportional share to carry
        proportions = {ad.ad_id: ad.total_reach_historical / total_reach_sum for ad in ads}

        for ad in ads:
            proportion = proportions[ad.ad_id]
            carry_state[ad.ad_id] = carry_state.get(ad.ad_id, 0.0) + (slots * proportion)

        # Step 2: Floor allocations and update carry
        allocations = {}
        for ad in ads:
            carry = carry_state[ad.ad_id]
            base = math.floor(carry)
            allocations[ad.ad_id] = base
            carry_state[ad.ad_id] = carry - base  # Keep fractional part

        # Step 3: Distribute residual slots (if any due to rounding)
        total_allocated = sum(allocations.values())
        residual = slots - total_allocated

        if residual > 0:
            # Sort by carry descending, tie-break by ad_id ascending
            sorted_by_carry = sorted(
                ads,
                key=lambda ad: (-carry_state.get(ad.ad_id, 0.0), ad.ad_id)
            )
            for i in range(residual):
                if i < len(sorted_by_carry):
                    ad = sorted_by_carry[i]
                    allocations[ad.ad_id] += 1
                    # Consume one full carry unit for residual slot assignment.
                    # Clamp to [0, 1) to avoid negative carry values.
                    carry_state[ad.ad_id] = max(0.0, carry_state.get(ad.ad_id, 0.0) - 1.0)

        # Conservation check
        final_total = sum(allocations.values())
        if final_total != slots:
            logger.error(f"Cumulative allocator conservation violated: {final_total} != {slots}")

        return allocations
