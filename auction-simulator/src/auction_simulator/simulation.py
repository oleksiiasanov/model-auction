"""
Simulation orchestration for multi-day auction simulation.

Manages simulation state, daily budget resets, and hourly auctions.
"""

import logging
from datetime import date, timedelta, datetime
from typing import Dict, List
import pandas as pd
from .auction_engine import Ad, AuctionEngine
from .logger import SimulationLogger

logger = logging.getLogger(__name__)


class Simulation:
    """Orchestrates multi-day auction simulation."""

    def __init__(self, config, auction_engine: AuctionEngine):
        """
        Initialize simulation.

        Args:
            config: Configuration object
            auction_engine: AuctionEngine instance
        """
        self.config = config
        self.engine = auction_engine
        self.ads: Dict[int, Ad] = {}  # ad_id -> Ad
        self.simulation_results = []
        self.sim_logger = None  # Will be initialized in run_simulation

    def initialize_ads(
        self,
        impressions_df: pd.DataFrame,
        budgets_df: pd.DataFrame
    ):
        """
        Initialize ad objects from extracted data (union of impressions and budgets).

        Budget-driven eligibility: ads with budgets but no historical reach are included
        as cold-start participants with zero historical metrics.

        Args:
            impressions_df: DataFrame with impression history
            budgets_df: DataFrame with budget data
        """
        logger.info("Initializing ads from union of impressions and budgets...")

        # Get unique ads from reach data
        unique_ads_impressions = impressions_df[['ad_id', 'seller_id', 'category_id']].drop_duplicates()

        # Get unique ads from budget data
        unique_ads_budgets = budgets_df[['ad_id', 'seller_id', 'category_id']].drop_duplicates()

        # Union of both sets
        unique_ads = pd.concat([unique_ads_impressions, unique_ads_budgets]).drop_duplicates(subset=['ad_id'])

        # Calculate historical total reach per ad (used for organic fallback proportions)
        total_reach_by_ad = impressions_df.groupby('ad_id')['total_reach'].sum().to_dict()
        # Calculate raw impressions for comparison
        raw_impressions_by_ad = impressions_df.groupby('ad_id')['raw_impressions'].sum().to_dict()

        # Track cold-start ads for logging
        budget_only_ads = 0

        # Create Ad objects
        for _, row in unique_ads.iterrows():
            ad_id = row['ad_id']
            seller_id = row['seller_id']
            category_id = row['category_id']

            total_reach_hist = total_reach_by_ad.get(ad_id, 0)
            raw_impressions_hist = raw_impressions_by_ad.get(ad_id, 0)

            # Track budget-only (cold-start) ads
            if total_reach_hist == 0 and raw_impressions_hist == 0:
                budget_only_ads += 1

            self.ads[ad_id] = Ad(
                ad_id=ad_id,
                seller_id=seller_id,
                category_id=category_id,
                daily_budget=0.0,  # Set per day (float for fractional kopecks)
                remaining_budget=0.0,  # Set per day (float for fractional kopecks)
                actual_spend=0.0,
                simulated_reach=0,
                simulated_spending=0.0,
                total_reach_historical=total_reach_hist,
                raw_impressions_historical=raw_impressions_hist
            )

        logger.info(f"Initialized {len(self.ads)} ads ({budget_only_ads} budget-only/cold-start ads)")

    def reset_daily_budgets(self, current_date: date, budgets_df: pd.DataFrame):
        """
        Reset ad budgets for new day.

        Args:
            current_date: Current simulation date
            budgets_df: DataFrame with budget data
        """
        # Get budgets for this date
        daily_budgets = budgets_df[budgets_df['date'] == current_date]

        # Reset all ads to budget=0 first
        for ad in self.ads.values():
            ad.daily_budget = 0.0
            ad.remaining_budget = 0.0
            ad.actual_spend = 0.0

        # Set budgets for ads that have campaigns
        for _, row in daily_budgets.iterrows():
            ad_id = row['ad_id']
            if ad_id in self.ads:
                budget = float(row['daily_budget'])  # Keep as float for fractional kopecks
                self.ads[ad_id].daily_budget = budget
                self.ads[ad_id].remaining_budget = budget

        ads_with_budget = sum(1 for ad in self.ads.values() if ad.daily_budget > 0)
        total_budget = sum(ad.daily_budget for ad in self.ads.values())

        logger.info(f"Reset budgets for {current_date}: {ads_with_budget} ads with budget, "
                    f"total={total_budget} kopecks")

    def run_simulation(
        self,
        impressions_df: pd.DataFrame,
        budgets_df: pd.DataFrame,
        min_bid_by_category: Dict[int, float],
        time_from: date,
        time_to: date
    ) -> pd.DataFrame:
        """
        Run full multi-day simulation.

        Args:
            impressions_df: Historical impression data
            budgets_df: Campaign budget data
            min_bid_by_category: Min bid per category (kopecks)
            time_from: Start date
            time_to: End date

        Returns:
            DataFrame with simulation results per ad
        """
        logger.info(f"Starting simulation from {time_from} to {time_to}")

        # Initialize simulation logger
        if self.config.logging.simulation_log_enabled:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.sim_logger = SimulationLogger(
                self.config.reporting.output_directory,
                timestamp,
                self.config
            )

        try:
            # Initialize ads
            self.initialize_ads(impressions_df, budgets_df)

            # Track total reach allocated for validation (Task 6.3)
            simulation_total_reach_allocated = 0

            # Simulate each day
            current_date = time_from
            while current_date <= time_to:
                logger.info(f"Simulating {current_date}")

                # Reset daily budgets
                self.reset_daily_budgets(current_date, budgets_df)

                # Reset cumulative carry-over state (change: update-paid-eligibility-and-organic-fallback-allocation)
                self.engine.reset_carry_state()

                # Task 3.2: Reset feedback pricing controller for all categories in this day
                # (change: add-feedback-price-multiplier-universal-pacing)
                if self.engine.feedback_pricing_enabled:
                    # Get unique categories that will be simulated today
                    day_impressions_for_init = impressions_df[impressions_df['date'] == current_date]
                    if len(day_impressions_for_init) > 0:
                        unique_categories = day_impressions_for_init['category_id'].unique()
                        for cat_id in unique_categories:
                            self.engine.reset_controller_state_for_day(cat_id, str(current_date))

                # Reset cascade state for all categories in this day
                # (change: add-cascading-win-cap-and-pacing)
                if self.engine.cascade_enabled:
                    day_impressions_for_init = impressions_df[impressions_df['date'] == current_date]
                    if len(day_impressions_for_init) > 0:
                        unique_categories = day_impressions_for_init['category_id'].unique()
                        for cat_id in unique_categories:
                            self.engine.reset_cascade_state_for_day(cat_id, str(current_date))

                # Log day start
                if self.sim_logger:
                    ads_with_budget = sum(1 for ad in self.ads.values() if ad.daily_budget > 0)
                    total_budget = sum(ad.daily_budget for ad in self.ads.values())
                    self.sim_logger.log_event('day_start', {
                        'date': str(current_date),
                        'total_ads': len(self.ads),
                        'ads_with_budget': ads_with_budget,
                        'total_daily_budget': total_budget
                    })

                # Get impressions for this day
                day_impressions = impressions_df[impressions_df['date'] == current_date]

                if len(day_impressions) == 0:
                    logger.warning(f"No reach records for {current_date}, skipping")
                    current_date += timedelta(days=1)
                    continue

                # Track day totals for logging
                day_impressions_total = 0
                day_paid_slots = 0
                day_organic_slots = 0

                # Simulate each hour
                for hour in range(24):
                    hour_stats = self.simulate_hour(
                        current_date,
                        hour,
                        day_impressions,
                        min_bid_by_category
                    )
                    if hour_stats:
                        day_impressions_total += hour_stats.get('total_allocated', 0)
                        day_paid_slots += hour_stats.get('paid_slots', 0)
                        day_organic_slots += hour_stats.get('organic_slots', 0)

                # Accumulate total reach for validation
                simulation_total_reach_allocated += day_impressions_total

                # Log day complete
                if self.sim_logger:
                    total_spending = sum(ad.simulated_spending for ad in self.ads.values())
                    ads_exhausted = sum(1 for ad in self.ads.values() if ad.daily_budget > 0 and ad.remaining_budget == 0)
                    self.sim_logger.log_event('day_complete', {
                        'date': str(current_date),
                        'total_reach_allocated': day_impressions_total,
                        'paid_reach': day_paid_slots,
                        'organic_reach': day_organic_slots,
                        'total_spending': total_spending,
                        'ads_exhausted': ads_exhausted
                    })

                current_date += timedelta(days=1)

            # Generate results DataFrame
            results = self._build_results()

            # Invariant checks (Task 4.2)
            # Check: no ad overspends its budget
            # Calculate total period budget per ad from budgets_df
            period_budgets = budgets_df.groupby('ad_id')['daily_budget'].sum().astype(float).to_dict()

            # Add period budget to results for checking
            results['period_total_budget'] = results['ad_id'].map(lambda x: period_budgets.get(x, 0.0))

            # Check overspending (allow 0.01 tolerance for floating point)
            overspend_ads = results[results['simulated_spending'] > results['period_total_budget'] + 0.01]
            if len(overspend_ads) > 0:
                logger.error(f"INVARIANT VIOLATION: {len(overspend_ads)} ads overspent period budget!")
                for _, row in overspend_ads.head(10).iterrows():
                    logger.error(f"  Ad {row['ad_id']}: spent={row['simulated_spending']:.2f}, period_budget={row['period_total_budget']:.2f}")
                raise AssertionError(f"Budget invariant violated: {len(overspend_ads)} ads overspent")

            # Task 6.3: Verify summary reach matches simulation allocations
            summary_total_reach = results['simulated_reach'].sum()
            reach_diff = abs(summary_total_reach - simulation_total_reach_allocated)
            if reach_diff > 0:
                logger.warning(
                    f"Reach conservation drift: summary={summary_total_reach}, "
                    f"allocated={simulation_total_reach_allocated}, diff={reach_diff}"
                )
                # This is a warning, not an error, as small differences may occur due to
                # rounding or edge cases in cumulative allocator

            logger.info(f"Simulation complete: {len(results)} ad records")
            logger.info(f"✓ Budget invariant check passed: all ads within budget")
            logger.info(f"✓ Reach conservation check: diff={reach_diff} (summary vs allocated)")

            return results

        finally:
            # Always close logger
            if self.sim_logger:
                self.sim_logger.close()

    def simulate_hour(
        self,
        current_date: date,
        hour: int,
        day_impressions: pd.DataFrame,
        min_bid_by_category: Dict[int, float]
    ) -> Dict[str, int]:
        """
        Simulate one hour of impressions.

        Args:
            current_date: Current date
            hour: Hour of day (0-23)
            day_impressions: Impressions for current day
            min_bid_by_category: Min bid per category

        Returns:
            Dictionary with hour statistics (total_allocated, paid_slots, organic_slots)
        """
        # Get impressions for this hour
        hour_impressions = day_impressions[day_impressions['hour'] == hour]

        if len(hour_impressions) == 0:
            return {'total_allocated': 0, 'paid_slots': 0, 'organic_slots': 0}

        # Calculate time progress and time left
        time_progress = hour / 24.0
        time_left = (24 - hour) / 24.0

        # Track hour-level statistics
        hour_total_allocated = 0
        hour_paid_slots = 0
        hour_organic_slots = 0

        # Group by category and run auctions
        for category_id, category_group in hour_impressions.groupby('category_id'):
            total_slots = int(category_group['total_reach'].sum())

            if total_slots <= 0:
                continue

            # Get min_bid for this category
            min_bid = min_bid_by_category.get(category_id, self.config.simulation.min_bid_fallback)

            # Get ads for this category
            category_ads = [ad for ad in self.ads.values() if ad.category_id == category_id]

            if len(category_ads) == 0:
                logger.warning(f"No ads for category {category_id}, hour {hour}")
                continue

            # Log hour start for this category
            if self.sim_logger:
                self.sim_logger.log_event('hour_start', {
                    'date': str(current_date),
                    'hour': hour,
                    'category_id': category_id,
                    'total_reach': total_slots,
                    'min_bid': min_bid
                })

            # Track reach before auction for unique winners
            reach_before = {ad.ad_id: ad.simulated_reach for ad in category_ads}

            # Run auction in batches (includes organic fallback within batches)
            auction_result = self.run_hour_auction(
                category_ads,
                min_bid,
                time_progress,
                time_left,
                total_slots,
                category_id,
                current_date,
                hour
            )

            batch_count = auction_result['batch_count']
            paid_slots = auction_result['paid_slots']
            organic_slots = auction_result['organic_slots']

            # Calculate slots allocated
            reach_after = {ad.ad_id: ad.simulated_reach for ad in category_ads}

            # Calculate unique winners
            unique_winners = sum(1 for ad_id in reach_after
                               if reach_after[ad_id] > reach_before.get(ad_id, 0))

            # Log hour complete for this category
            if self.sim_logger:
                self.sim_logger.log_event('hour_complete', {
                    'category_id': category_id,
                    'hour': hour,
                    'total_allocated': total_slots,
                    'paid_slots': paid_slots,
                    'organic_slots': organic_slots,
                    'num_batches': batch_count,
                    'unique_winners': unique_winners
                })

            # Accumulate hour statistics
            hour_total_allocated += total_slots
            hour_paid_slots += paid_slots
            hour_organic_slots += organic_slots

        return {
            'total_allocated': hour_total_allocated,
            'paid_slots': hour_paid_slots,
            'organic_slots': hour_organic_slots
        }

    def run_hour_auction(
        self,
        ads: List[Ad],
        min_bid: float,
        time_progress: float,
        time_left: float,
        total_slots: int,
        category_id: int,
        current_date: date,
        hour: int
    ) -> dict:
        """
        Run auction for one hour in batches.

        Args:
            ads: List of ads in category
            min_bid: Minimum bid
            time_progress: Fraction of day elapsed
            time_left: Fraction of day remaining
            total_slots: Total reach slots to allocate
            category_id: Category ID for logging and feedback pricing
            current_date: Current date (for feedback pricing)
            hour: Hour of day for logging

        Returns:
            Dictionary with batch_count, paid_slots, organic_slots
        """
        date_str = str(current_date)
        batch_size = self.config.simulation.batch_size
        slots_allocated = 0
        batch_number = 0
        paid_slots = 0
        organic_slots = 0

        # Task 3.1: Update feedback pricing controller at hour start (change: add-feedback-price-multiplier-universal-pacing)
        if self.engine.feedback_pricing_enabled and self.engine.feedback_update_cadence == 'hourly':
            # Calculate total daily budget for category
            category_ads_with_budget = [ad for ad in ads if ad.daily_budget > 0]
            total_daily_budget = sum(ad.daily_budget for ad in category_ads_with_budget)

            # Calculate cumulative spend so far
            cumulative_spend = sum(ad.simulated_spending for ad in category_ads_with_budget)

            # Update controller
            controller_diagnostics = self.engine.update_price_multiplier(
                category_id,
                date_str,
                total_daily_budget,
                cumulative_spend,
                time_progress
            )

            # Log controller update
            if self.sim_logger:
                self.sim_logger.log_event('multiplier_update', {
                    'date': date_str,
                    'hour': hour,
                    'category_id': category_id,
                    'time_progress': time_progress,
                    **controller_diagnostics
                })

        # Evaluate cascading win cap at hour start (change: add-cascading-win-cap-and-pacing)
        win_per_ad_cap = 1  # Default
        pacing_tolerance_adjusted = self.engine.pacing_tolerance  # Default

        if self.engine.cascade_enabled:
            # Calculate total daily budget and cumulative spend for category
            category_ads_with_budget = [ad for ad in ads if ad.daily_budget > 0]
            total_daily_budget = sum(ad.daily_budget for ad in category_ads_with_budget)
            cumulative_spend = sum(ad.simulated_spending for ad in category_ads_with_budget)

            # Evaluate cascade
            cascade_diagnostics = self.engine.evaluate_cascade(
                category_id,
                date_str,
                total_daily_budget,
                cumulative_spend,
                time_progress
            )

            win_per_ad_cap = cascade_diagnostics['win_per_ad_cap']
            pacing_tolerance_adjusted = cascade_diagnostics['pacing_tolerance_adjusted']

            # Log cascade evaluation
            if self.sim_logger:
                self.sim_logger.log_event('cascade_evaluation', {
                    'date': date_str,
                    'hour': hour,
                    'category_id': category_id,
                    'time_progress': time_progress,
                    **cascade_diagnostics
                })

        while slots_allocated < total_slots:
            # Calculate batch size
            remaining = total_slots - slots_allocated
            current_batch = min(batch_size, remaining)

            # Check if any ads have budget remaining
            ads_with_budget = [ad for ad in ads if ad.remaining_budget > 0]

            if len(ads_with_budget) == 0:
                # No paid ads - distribute entire batch via organic fallback
                # Use pool split cumulative allocator if enabled (change: update-paid-eligibility-and-organic-fallback-allocation)
                if self.engine.use_cumulative_allocator:
                    self.engine.distribute_organic_with_pool_split(
                        ads,
                        current_batch,
                        category_id=category_id,
                        hour=hour,
                        sim_logger=self.sim_logger
                    )
                else:
                    self.engine.distribute_organic_proportional(
                        ads,
                        current_batch,
                        category_id=category_id,
                        hour=hour,
                        sim_logger=self.sim_logger
                    )
                slots_allocated += current_batch
                organic_slots += current_batch
                continue  # Continue to next batch

            batch_number += 1

            # Run batch auction - ONLY with ads that have budget (with cascading win cap)
            allocated_paid = self.engine.run_batch_auction(
                ads_with_budget,
                min_bid,
                time_progress,
                time_left,
                current_batch,
                category_id=category_id,
                date=date_str,
                hour=hour,
                batch_number=batch_number,
                logger=self.sim_logger,
                win_per_ad_cap=win_per_ad_cap
            )

            slots_allocated += allocated_paid
            paid_slots += allocated_paid

            # If couldn't fill the batch - distribute remaining via organic fallback
            if allocated_paid < current_batch:
                remaining_in_batch = current_batch - allocated_paid
                # Use pool split cumulative allocator if enabled (change: update-paid-eligibility-and-organic-fallback-allocation)
                if self.engine.use_cumulative_allocator:
                    self.engine.distribute_organic_with_pool_split(
                        ads,
                        remaining_in_batch,
                        category_id=category_id,
                        hour=hour,
                        sim_logger=self.sim_logger
                    )
                else:
                    self.engine.distribute_organic_proportional(
                        ads,
                        remaining_in_batch,
                        category_id=category_id,
                        hour=hour,
                        sim_logger=self.sim_logger
                    )
                slots_allocated += remaining_in_batch
                organic_slots += remaining_in_batch

        return {
            'batch_count': batch_number,
            'paid_slots': paid_slots,
            'organic_slots': organic_slots
        }

    def _build_results(self) -> pd.DataFrame:
        """
        Build results DataFrame from ad states.

        Returns:
            DataFrame with per-ad simulation results
        """
        records = []

        for ad in self.ads.values():
            records.append({
                'ad_id': ad.ad_id,
                'seller_id': ad.seller_id,
                'category_id': ad.category_id,
                'simulated_reach': ad.simulated_reach,
                'simulated_spending': ad.simulated_spending,
                'daily_budget': ad.daily_budget,
                'total_reach_historical': ad.total_reach_historical,
                'raw_impressions_historical': ad.raw_impressions_historical
            })

        return pd.DataFrame(records)
