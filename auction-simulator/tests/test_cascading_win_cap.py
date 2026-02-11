"""
Tests for cascading win cap and pacing relaxation.

Tests verify cascade evaluation, win cap application, and pacing adjustment.
"""

import pytest
from auction_simulator.auction_engine import Ad, AuctionEngine
from auction_simulator.config import Config


@pytest.fixture
def cascade_config():
    """Create test configuration with cascade enabled."""
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
                'Kp': 0.05,
                'Ki': 0.02,
                'multiplier_min': 0.5,
                'multiplier_max': 3.0,
                'multiplier_initial': 1.0,
                'delta_limit': 0.3,
                'integral_min': -1.0,
                'integral_max': 1.0,
                'alpha': 0.7,
                'update_cadence': 'hourly',
                'target_curve': {
                    'shape': 'linear'
                }
            },
            'cascading_win_cap': {
                'enabled': True,
                'cap_thresholds': [
                    {'ratio': 0.9, 'cap': 2},
                    {'ratio': 0.75, 'cap': 3},
                    {'ratio': 0.6, 'cap': 4}
                ],
                'max_win_per_ad_cap': 4,
                'pacing_relaxation': {
                    'enabled': True,
                    'fallback_hours': 2,
                    'under_spend_threshold': 0.85,
                    'tolerance_increment': 0.1,
                    'tolerance_max': 0.5
                }
            }
        }
    })


@pytest.fixture
def engine(cascade_config):
    """Create auction engine with cascade enabled."""
    return AuctionEngine(cascade_config)


def test_cascade_initialization(engine):
    """Test that cascade state initializes correctly."""
    engine.reset_cascade_state_for_day(1234, '2026-02-01')

    cap = engine.get_win_per_ad_cap(1234, '2026-02-01')
    tolerance = engine.get_adjusted_pacing_tolerance(1234, '2026-02-01')

    assert cap == 1, "Initial win_per_ad_cap should be 1"
    assert tolerance == 0.2, "Initial pacing_tolerance should be base value"


def test_win_cap_increases_on_underspend(engine):
    """Test that win_per_ad_cap increases when under-spending."""
    # Initial state: cap = 1
    initial_cap = engine.get_win_per_ad_cap(1234, '2026-02-01')
    assert initial_cap == 1

    # Simulate under-spend (spending 80% of target)
    diagnostics = engine.evaluate_cascade(
        category_id=1234,
        date='2026-02-01',
        total_budget=1000.0,
        cumulative_spend=400.0,  # 40% spent
        time_progress=0.5  # 50% of day elapsed → target = 500
    )

    # Under-spend ratio = 400/500 = 0.8 < 0.9 → cap should be 2
    assert diagnostics['under_spend_ratio'] == 0.8
    assert diagnostics['win_per_ad_cap'] == 2, "Cap should increase to 2 when ratio < 0.9"
    assert engine.get_win_per_ad_cap(1234, '2026-02-01') == 2


def test_win_cap_graduated_thresholds(engine):
    """Test that win_per_ad_cap increases through graduated thresholds."""
    # Scenario 1: spending 85% of target → cap = 2
    d1 = engine.evaluate_cascade(1234, '2026-02-01', 1000.0, 425.0, 0.5)
    assert d1['under_spend_ratio'] == 0.85
    assert d1['win_per_ad_cap'] == 2

    # Scenario 2: spending 70% of target → cap = 3
    d2 = engine.evaluate_cascade(1234, '2026-02-02', 1000.0, 350.0, 0.5)
    assert d2['under_spend_ratio'] == 0.70
    assert d2['win_per_ad_cap'] == 3

    # Scenario 3: spending 55% of target → cap = 4
    d3 = engine.evaluate_cascade(1234, '2026-02-03', 1000.0, 275.0, 0.5)
    assert d3['under_spend_ratio'] == 0.55
    assert d3['win_per_ad_cap'] == 4


def test_win_cap_never_exceeds_max(engine):
    """Test that win_per_ad_cap is clamped to max_win_per_ad_cap."""
    # Extreme under-spend (spending 10% of target)
    diagnostics = engine.evaluate_cascade(
        category_id=1234,
        date='2026-02-01',
        total_budget=1000.0,
        cumulative_spend=50.0,
        time_progress=0.5
    )

    assert diagnostics['win_per_ad_cap'] <= 4, "Cap should never exceed max_win_per_ad_cap"


def test_pacing_tolerance_relaxation(engine):
    """Test that pacing tolerance relaxes after sustained under-spend."""
    # Hour 1: under-spend → streak = 1, no relaxation yet
    d1 = engine.evaluate_cascade(1234, '2026-02-01', 1000.0, 400.0, 0.5)
    assert d1['under_spend_streak'] == 1
    assert d1['pacing_tolerance_adjusted'] == 0.2, "No relaxation before fallback_hours"

    # Hour 2: still under-spending → streak = 2, relaxation triggers
    d2 = engine.evaluate_cascade(1234, '2026-02-01', 1000.0, 420.0, 0.55)
    assert d2['under_spend_streak'] == 2
    assert abs(d2['pacing_tolerance_adjusted'] - 0.3) < 0.001, "Tolerance should increase by 0.1"

    # Hour 3: still under-spending → streak = 3, more relaxation
    d3 = engine.evaluate_cascade(1234, '2026-02-01', 1000.0, 440.0, 0.60)
    assert d3['under_spend_streak'] == 3
    assert abs(d3['pacing_tolerance_adjusted'] - 0.4) < 0.001, "Tolerance should increase by another 0.1"


def test_pacing_tolerance_max_bound(engine):
    """Test that pacing tolerance never exceeds tolerance_max."""
    # Simulate 10 consecutive under-spend hours
    for hour in range(10):
        time_progress = 0.1 * (hour + 1)
        diagnostics = engine.evaluate_cascade(
            category_id=1234,
            date='2026-02-01',
            total_budget=1000.0,
            cumulative_spend=50.0 * (hour + 1),  # Always under-spending
            time_progress=time_progress
        )

        # Should never exceed tolerance_max = 0.5
        assert diagnostics['pacing_tolerance_adjusted'] <= 0.5


def test_streak_resets_on_normal_spend(engine):
    """Test that under-spend streak resets when spending normalizes."""
    # Hour 1: under-spend → streak = 1
    d1 = engine.evaluate_cascade(1234, '2026-02-01', 1000.0, 400.0, 0.5)
    assert d1['under_spend_streak'] == 1

    # Hour 2: back to normal spending (90% of target) → streak resets
    d2 = engine.evaluate_cascade(1234, '2026-02-01', 1000.0, 495.0, 0.55)
    assert d2['under_spend_ratio'] >= 0.85, "Should be above under_spend_threshold"
    assert d2['under_spend_streak'] == 0, "Streak should reset"
    assert d2['pacing_tolerance_adjusted'] == 0.2, "Tolerance should return to base"


def test_select_winners_with_win_cap(engine, cascade_config):
    """Test that select_winners respects win_per_ad_cap."""
    # Create 3 ads
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

    # Rank ads
    ranked = engine.rank_ads(ads, time_progress=0.5, time_left=0.5)

    # Test 1: win_per_ad_cap = 1 (default behavior)
    winners = engine.select_winners(ranked, min_bid=100.0, slots=10, win_per_ad_cap=1)
    # With 3 ads and cap=1, should get exactly 3 winners (1 per ad)
    assert len(winners) == 3

    # Test 2: win_per_ad_cap = 3 (allow multiple wins)
    winners = engine.select_winners(ranked, min_bid=100.0, slots=10, win_per_ad_cap=3)
    # With 3 ads and cap=3, should get up to 9 winners (3 per ad)
    # But we only request 10 slots, so should get 9 (3 ads * 3 wins each)
    assert len(winners) == 9

    # Verify each ad won exactly 3 times
    ad_wins = {}
    for ad, bid, reach in winners:
        ad_wins[ad.ad_id] = ad_wins.get(ad.ad_id, 0) + 1

    for ad_id in range(3):
        assert ad_wins[ad_id] == 3, f"Ad {ad_id} should have won exactly 3 times"


def test_cascade_disabled_returns_defaults(cascade_config):
    """Test that when cascade is disabled, defaults are returned."""
    # Disable cascade
    cascade_config._config['simulation']['cascading_win_cap']['enabled'] = False
    engine_disabled = AuctionEngine(cascade_config)

    # Evaluate cascade (should do nothing)
    diagnostics = engine_disabled.evaluate_cascade(
        category_id=1234,
        date='2026-02-01',
        total_budget=1000.0,
        cumulative_spend=200.0,
        time_progress=0.5
    )

    assert diagnostics['win_per_ad_cap'] == 1
    assert diagnostics['pacing_tolerance_adjusted'] == 0.2
    assert diagnostics['cascade_applied'] == False


def test_cascade_state_per_category_per_day(engine):
    """Test that cascade state is tracked independently per category/day."""
    # Category 1, Day 1: under-spend
    d1 = engine.evaluate_cascade(1234, '2026-02-01', 1000.0, 400.0, 0.5)
    assert d1['under_spend_streak'] == 1
    assert d1['win_per_ad_cap'] == 2

    # Category 2, Day 1: different state
    d2 = engine.evaluate_cascade(5678, '2026-02-01', 1000.0, 490.0, 0.5)
    assert d2['under_spend_streak'] == 0  # Different category, fresh state
    assert d2['win_per_ad_cap'] == 1

    # Category 1, Day 2: fresh state for new day
    engine.reset_cascade_state_for_day(1234, '2026-02-02')
    d3 = engine.evaluate_cascade(1234, '2026-02-02', 1000.0, 400.0, 0.5)
    assert d3['under_spend_streak'] == 1  # Fresh start

    # But Day 1 state for Category 1 should still exist
    assert engine.cascade_state[(1234, '2026-02-01')]['under_spend_streak'] == 1
