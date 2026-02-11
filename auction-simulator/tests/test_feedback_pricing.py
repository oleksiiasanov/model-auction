"""
Tests for feedback pricing controller.

Tests verify PI controller math, bounds, and multiplier application.
"""

import pytest
from auction_simulator.auction_engine import Ad, AuctionEngine
from auction_simulator.config import Config


@pytest.fixture
def feedback_config():
    """Create test configuration with feedback pricing enabled."""
    return Config({
        'simulation': {
            'min_time_left_threshold': 0.001,
            'min_time_progress_threshold': 0.042,
            'pacing_tolerance': 0.2,
            'bid_step': 0.003,
            'batch_size': 40,
            'organic_fallback': {
                'free_share': 0.8,
                'use_cumulative_allocator': True
            },
            'feedback_pricing': {
                'enabled': True,
                'Kp': 0.1,
                'Ki': 0.05,
                'multiplier_min': 0.5,
                'multiplier_max': 3.0,
                'multiplier_initial': 1.0,
                'delta_limit': 0.5,
                'integral_min': -1.0,
                'integral_max': 1.0,
                'alpha': 0.8,
                'update_cadence': 'hourly',
                'target_curve': {
                    'shape': 'linear'
                }
            }
        }
    })


@pytest.fixture
def engine(feedback_config):
    """Create auction engine with feedback pricing."""
    return AuctionEngine(feedback_config)


def test_multiplier_initialization(engine):
    """Test that multiplier initializes to configured initial value."""
    multiplier = engine.get_price_multiplier(1234, '2026-02-01')
    assert multiplier == 1.0, "Initial multiplier should be 1.0"


def test_multiplier_bounded(engine):
    """Test that multiplier stays within configured bounds."""
    # Simulate under-spending (should increase multiplier)
    for i in range(10):
        diagnostics = engine.update_price_multiplier(
            category_id=1234,
            date='2026-02-01',
            total_budget=1000.0,
            cumulative_spend=0.0,  # Massive under-spend
            time_progress=0.5
        )

        multiplier = diagnostics['multiplier']
        assert multiplier >= 0.5, f"Multiplier {multiplier} below min 0.5"
        assert multiplier <= 3.0, f"Multiplier {multiplier} above max 3.0"


def test_multiplier_increases_on_underspend(engine):
    """Test that multiplier increases when under-spending."""
    # Initial state
    initial_mult = engine.get_price_multiplier(1234, '2026-02-01')

    # Update with under-spend (target=500, actual=100)
    engine.update_price_multiplier(
        category_id=1234,
        date='2026-02-01',
        total_budget=1000.0,
        cumulative_spend=100.0,
        time_progress=0.5  # Target = 500
    )

    new_mult = engine.get_price_multiplier(1234, '2026-02-01')
    assert new_mult > initial_mult, "Multiplier should increase on under-spend"


def test_multiplier_decreases_on_overspend(engine):
    """Test that multiplier decreases when over-spending."""
    # Initialize with high multiplier
    engine.reset_controller_state_for_day(1234, '2026-02-01')
    engine.controller_state[(1234, '2026-02-01')]['multiplier'] = 2.0

    initial_mult = 2.0

    # Update with over-spend (target=100, actual=900)
    engine.update_price_multiplier(
        category_id=1234,
        date='2026-02-01',
        total_budget=1000.0,
        cumulative_spend=900.0,
        time_progress=0.1  # Target = 100
    )

    new_mult = engine.get_price_multiplier(1234, '2026-02-01')
    assert new_mult < initial_mult, "Multiplier should decrease on over-spend"


def test_multiplier_applied_to_bid(engine, feedback_config):
    """Test that multiplier is applied to effective bid calculation."""
    # Create test ads
    ads = []
    for i in range(3):
        ad = Ad(
            ad_id=i,
            seller_id=100 + i,
            category_id=1234,
            daily_budget=100.0,
            remaining_budget=100.0,
            actual_spend=0.0,
            simulated_reach=0,
            simulated_spending=0.0,
            total_reach_historical=50
        )
        ads.append(ad)

    # Set multiplier to 2.0
    engine.reset_controller_state_for_day(1234, '2026-02-01')
    engine.controller_state[(1234, '2026-02-01')]['multiplier'] = 2.0

    # Rank ads
    ranked = engine.rank_ads(ads, time_progress=0.5, time_left=0.5)

    # Select winners with multiplier
    winners = engine.select_winners(ranked, min_bid=100.0, slots=3, category_id=1234, date='2026-02-01')

    # Check that bids are scaled by multiplier
    for ad, effective_bid, reach_won in winners:
        # Base bid would be ~100 + N*bid_step, with multiplier should be ~2x
        # Just verify that bid is scaled (>=200)
        assert effective_bid >= 200.0, f"Bid {effective_bid} should be scaled by multiplier 2.0"


def test_target_curve_shapes(engine):
    """Test different target curve shapes."""
    total_budget = 1000.0

    # Linear: T(0.5) = 500
    linear_target = engine.calculate_target_spend(total_budget, 0.5)
    assert abs(linear_target - 500.0) < 1.0, "Linear curve should give 50% at t=0.5"

    # Front-loaded: T(0.5) should be > 500 (spend faster early)
    engine.feedback_target_curve_shape = 'front_loaded'
    front_target = engine.calculate_target_spend(total_budget, 0.5)
    assert front_target > 500.0, "Front-loaded curve should spend more than 50% by t=0.5"

    # Back-loaded: T(0.5) should be < 500 (spend slower early)
    engine.feedback_target_curve_shape = 'back_loaded'
    back_target = engine.calculate_target_spend(total_budget, 0.5)
    assert back_target < 500.0, "Back-loaded curve should spend less than 50% by t=0.5"


def test_controller_reset_per_day(engine):
    """Test that controller state resets correctly for each day."""
    # Set state for day 1
    engine.reset_controller_state_for_day(1234, '2026-02-01')
    engine.controller_state[(1234, '2026-02-01')]['multiplier'] = 2.5
    engine.controller_state[(1234, '2026-02-01')]['integral'] = 0.5

    # Reset for day 2
    engine.reset_controller_state_for_day(1234, '2026-02-02')

    # Day 1 should still have old state
    assert engine.controller_state[(1234, '2026-02-01')]['multiplier'] == 2.5

    # Day 2 should have fresh state
    assert engine.controller_state[(1234, '2026-02-02')]['multiplier'] == 1.0
    assert engine.controller_state[(1234, '2026-02-02')]['integral'] == 0.0


def test_feedback_disabled_returns_multiplier_one(feedback_config):
    """Test that when feedback pricing is disabled, multiplier is always 1.0."""
    # Disable feedback pricing
    feedback_config._config['simulation']['feedback_pricing']['enabled'] = False
    engine_disabled = AuctionEngine(feedback_config)

    # Try to update (should do nothing)
    diagnostics = engine_disabled.update_price_multiplier(
        category_id=1234,
        date='2026-02-01',
        total_budget=1000.0,
        cumulative_spend=0.0,
        time_progress=0.5
    )

    assert diagnostics['multiplier'] == 1.0, "Disabled controller should always return 1.0"
    assert engine_disabled.get_price_multiplier(1234, '2026-02-01') == 1.0
