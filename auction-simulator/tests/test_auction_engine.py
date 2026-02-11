"""
Tests for auction engine core logic.
"""

import pytest
from auction_simulator.auction_engine import Ad, AuctionEngine
from auction_simulator.config import Config


@pytest.fixture
def config():
    """Create test configuration."""
    return Config({
        'simulation': {
            'min_time_left_threshold': 0.001,
            'min_time_progress_threshold': 0.042,
            'pacing_tolerance': 0.2,
            'bid_step': 0.1,
            'batch_size': 40
        }
    })


@pytest.fixture
def engine(config):
    """Create auction engine instance."""
    return AuctionEngine(config)


def test_pressure_calculation_with_budget(engine):
    """Test pressure calculation for ad with budget."""
    ad = Ad(
        ad_id=1,
        seller_id=100,
        category_id=1234,
        daily_budget=1000,
        remaining_budget=1000,
        actual_spend=0.0,
        simulated_reach=0,
        simulated_spending=0.0,
        total_reach_historical=0
    )

    time_left = 0.5  # 12 hours remaining
    pressure = engine.calculate_pressure(ad, time_left)

    assert pressure == 2000.0  # 1000 / 0.5


def test_pressure_zero_for_no_budget(engine):
    """Test pressure is zero when budget is exhausted."""
    ad = Ad(
        ad_id=1,
        seller_id=100,
        category_id=1234,
        daily_budget=1000,
        remaining_budget=0,  # No budget left
        actual_spend=1000.0,
        simulated_reach=100,
        simulated_spending=1000.0,
        total_reach_historical=0
    )

    time_left = 0.5
    pressure = engine.calculate_pressure(ad, time_left)

    assert pressure == 0.0


def test_pressure_division_by_zero_prevention(engine):
    """Test min_time_left_threshold prevents division by zero."""
    ad = Ad(
        ad_id=1,
        seller_id=100,
        category_id=1234,
        daily_budget=1000,
        remaining_budget=500,
        actual_spend=0.0,
        simulated_reach=0,
        simulated_spending=0.0,
        total_reach_historical=0
    )

    time_left = 0.0  # Edge case (not realistic with hourly updates)
    pressure = engine.calculate_pressure(ad, time_left)

    # Should use min_time_left_threshold instead of 0
    assert pressure == 500 / engine.min_time_left_threshold


def test_pacing_gate_within_limits(engine):
    """Test ad is eligible when within pacing limits."""
    ad = Ad(
        ad_id=1,
        seller_id=100,
        category_id=1234,
        daily_budget=1000,
        remaining_budget=800,
        actual_spend=200.0,  # 20% spent
        simulated_reach=0,
        simulated_spending=0.0,
        total_reach_historical=0
    )

    time_progress = 0.25  # 25% of day elapsed
    is_eligible = engine.check_pacing_gate(ad, time_progress)

    # Expected: 250 (25% of 1000)
    # Max allowed: 300 (250 * 1.2)
    # Actual: 200
    # 200 < 300, so eligible
    assert is_eligible is True


def test_pacing_gate_exceeds_limits(engine):
    """Test ad is paused when exceeding pacing limits."""
    ad = Ad(
        ad_id=1,
        seller_id=100,
        category_id=1234,
        daily_budget=1000,
        remaining_budget=650,
        actual_spend=350.0,  # 35% spent
        simulated_reach=0,
        simulated_spending=0.0,
        total_reach_historical=0
    )

    time_progress = 0.25  # 25% of day elapsed
    is_eligible = engine.check_pacing_gate(ad, time_progress)

    # Expected: 250
    # Max allowed: 300
    # Actual: 350
    # 350 > 300, so paused
    assert is_eligible is False


def test_rank_ads_by_pressure(engine):
    """Test ads are ranked by pressure descending."""
    ads = [
        Ad(1, 100, 1234, 1000, 1000, 0.0, 0, 0.0, 0),  # pressure = 1000 / 0.5 = 2000
        Ad(2, 100, 1234, 1500, 1500, 0.0, 0, 0.0, 0),  # pressure = 1500 / 0.5 = 3000
        Ad(3, 100, 1234, 500, 500, 0.0, 0, 0.0, 0),    # pressure = 500 / 0.5 = 1000
    ]

    time_progress = 0.5
    time_left = 0.5

    ranked = engine.rank_ads(ads, time_progress, time_left)

    # Should be ranked: ad2 (3000), ad1 (2000), ad3 (1000)
    assert ranked[0][0].ad_id == 2
    assert ranked[0][2] == 0  # rank_index
    assert ranked[1][0].ad_id == 1
    assert ranked[1][2] == 1
    assert ranked[2][0].ad_id == 3
    assert ranked[2][2] == 2


def test_effective_bid_calculation(engine):
    """Test effective bid calculation with correct formula."""
    ads = [
        Ad(1, 100, 1234, 1000, 1000, 0.0, 0, 0.0, 0),
        Ad(2, 100, 1234, 1500, 1500, 0.0, 0, 0.0, 0),
        Ad(3, 100, 1234, 500, 500, 0.0, 0, 0.0, 0),
    ]

    time_progress = 0.5
    time_left = 0.5

    ranked = engine.rank_ads(ads, time_progress, time_left)

    min_bid = 0.5
    N = 3

    # Top-ranked (rank_index=0): min_bid + (3-1-0)*0.1 = 0.5 + 0.2 = 0.7
    winners = engine.select_winners(ranked, min_bid, 3)

    assert len(winners) == 3
    assert winners[0][1] == 0.7  # effective_bid for rank 0
    assert winners[1][1] == 0.6  # effective_bid for rank 1
    assert winners[2][1] == 0.5  # effective_bid for rank 2 (min_bid)


def test_organic_fallback_proportional_conservation(engine):
    """Test proportional organic fallback guarantees conservation."""
    ads = [
        Ad(1, 100, 1234, 0, 0, 0.0, 0, 0.0, 100),  # 100 historical organic
        Ad(2, 100, 1234, 0, 0, 0.0, 0, 0.0, 50),   # 50 historical organic
        Ad(3, 100, 1234, 0, 0, 0.0, 0, 0.0, 0),    # 0 historical organic
    ]

    remaining_slots = 300

    engine.distribute_organic_proportional(ads, remaining_slots)

    # Total allocated should equal remaining_slots
    total_allocated = sum(ad.simulated_reach for ad in ads)
    assert total_allocated == remaining_slots

    # Proportions: 100/150, 50/150, 0/150
    # Ad 1 should get ~200, Ad 2 should get ~100, Ad 3 should get 0
    assert ads[0].simulated_reach == 200
    assert ads[1].simulated_reach == 100
    assert ads[2].simulated_reach == 0


def test_organic_fallback_equal_conservation(engine):
    """Test equal organic fallback guarantees conservation."""
    ads = [
        Ad(1, 100, 1234, 0, 0, 0.0, 0, 0.0, 0),
        Ad(2, 100, 1234, 0, 0, 0.0, 0, 0.0, 0),
        Ad(3, 100, 1234, 0, 0, 0.0, 0, 0.0, 0),
    ]

    remaining_slots = 100

    engine.distribute_organic_equal(ads, remaining_slots)

    # Total allocated should equal remaining_slots
    total_allocated = sum(ad.simulated_reach for ad in ads)
    assert total_allocated == remaining_slots

    # 100 / 3 = 33 base, 1 remainder
    # First ad gets 34, others get 33
    assert ads[0].simulated_reach == 34
    assert ads[1].simulated_reach == 33
    assert ads[2].simulated_reach == 33


def test_charge_winners_with_rounding(engine):
    """Test winners are charged with exact fractional kopecks (no rounding)."""
    ad = Ad(1, 100, 1234, 1000.0, 1000.0, 0.0, 0, 0.0, 0)

    winners = [(ad, 1.5, 1)]  # effective_bid=1.5 kopecks

    engine.charge_winners(winners)

    # Exact deduction: 1000.0 - 1.5 = 998.5 (no rounding with float budgets)
    assert ad.remaining_budget == 998.5
    assert ad.actual_spend == 1.5  # exact spend tracked
    assert ad.simulated_reach == 1


def test_charge_winners_organic_no_charge(engine):
    """Test organic impressions (budget=0) are not charged."""
    ad = Ad(1, 100, 1234, 0, 0, 0.0, 0, 0.0, 100)

    winners = [(ad, 1.5, 1)]

    engine.charge_winners(winners)

    # No charge for organic
    assert ad.remaining_budget == 0
    assert ad.actual_spend == 0.0
    assert ad.simulated_reach == 1


def test_pacing_gate_hour_zero_not_blocked(engine):
    """Test that ads are not blocked at hour 0 after first win."""
    ad = Ad(
        ad_id=1,
        seller_id=100,
        category_id=1234,
        daily_budget=100.0,
        remaining_budget=100.0,
        actual_spend=0.0,
        simulated_reach=0,
        simulated_spending=0.0,
        total_reach_historical=0
    )

    time_progress = 0.0  # Hour 0

    # First batch: ad has not spent yet
    assert engine.check_pacing_gate(ad, time_progress) is True

    # Simulate winning auction (cost ~0.15)
    ad.actual_spend = 0.15

    # Second batch: ad should still be eligible
    # max_allowed = 100 × max(0.0, 0.042) × 1.2 = 5.04 kopecks
    # 0.15 < 5.04 → eligible
    assert engine.check_pacing_gate(ad, time_progress) is True

    # Continue spending up to threshold
    ad.actual_spend = 5.0
    assert engine.check_pacing_gate(ad, time_progress) is True

    # Exceed threshold
    ad.actual_spend = 5.1
    assert engine.check_pacing_gate(ad, time_progress) is False
