"""
Tests for organic fallback allocation with total_reach_historical.

Tests verify that organic fallback now uses total_reach_historical (paid + organic)
instead of organic_reach_historical (organic only) for proportional distribution.
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


def test_promoted_without_budget_receives_allocation(engine):
    """
    Test that ads promoted without budget (total_reach > 0, but historically paid)
    now receive organic fallback allocation.

    This was the primary issue: 1,471 ads had total_reach_historical > 0 but
    organic_reach_historical = 0, so they got proportion = 0 and no allocation.
    """
    # Ad A: Promoted without budget (was paid, now organic)
    # Previously: organic_reach_historical=0 → proportion=0 → allocated=0
    # Now: total_reach_historical=100 → proportion>0 → allocated>0
    ad_promoted = Ad(
        ad_id=1,
        seller_id=100,
        category_id=1234,
        daily_budget=0.0,
        remaining_budget=0.0,
        actual_spend=0.0,
        simulated_reach=0,
        simulated_spending=0.0,
        total_reach_historical=100  # Has reach history, should get allocation
    )

    # Ad B: Pure organic ad for comparison
    ad_organic = Ad(
        ad_id=2,
        seller_id=200,
        category_id=1234,
        daily_budget=0.0,
        remaining_budget=0.0,
        actual_spend=0.0,
        simulated_reach=0,
        simulated_spending=0.0,
        total_reach_historical=100  # Same total reach
    )

    ads = [ad_promoted, ad_organic]
    remaining_slots = 40

    # Run organic fallback
    engine.distribute_organic_proportional(ads, remaining_slots, category_id=1234, hour=0)

    # Both ads should receive equal allocation (both have total_reach=100)
    assert ad_promoted.simulated_reach > 0, "Promoted-without-budget ad should receive allocation"
    assert ad_organic.simulated_reach > 0, "Organic ad should receive allocation"
    assert ad_promoted.simulated_reach == ad_organic.simulated_reach, "Equal total_reach should give equal allocation"
    assert ad_promoted.simulated_reach + ad_organic.simulated_reach == remaining_slots, "Conservation violated"


def test_low_reach_ads_get_better_allocation(engine):
    """
    Test that low-reach ads get better allocation with total_reach_historical.

    Previously: 3,156 ads with organic_reach_historical 1-8 got floored to 0.
    Now: Using total_reach_historical increases proportions, more ads get >0.
    """
    # Create ads with low reach (1-8)
    ads = []
    for i in range(1, 9):
        ad = Ad(
            ad_id=i,
            seller_id=100 + i,
            category_id=1234,
            daily_budget=0.0,
            remaining_budget=0.0,
            actual_spend=0.0,
            simulated_reach=0,
            simulated_spending=0.0,
            total_reach_historical=i  # Small but non-zero
        )
        ads.append(ad)

    remaining_slots = 100

    # Run organic fallback
    engine.distribute_organic_proportional(ads, remaining_slots, category_id=1234, hour=0)

    # Check that at least some low-reach ads get allocation
    allocated_count = sum(1 for ad in ads if ad.simulated_reach > 0)
    total_allocated = sum(ad.simulated_reach for ad in ads)

    assert allocated_count > 0, "At least some low-reach ads should get allocation"
    assert total_allocated == remaining_slots, "Conservation violated"

    # Ads with higher total_reach should get more (proportional)
    assert ads[-1].simulated_reach >= ads[0].simulated_reach, "Higher reach should get >= allocation"


def test_proportional_distribution_respects_total_reach(engine):
    """Test that allocation is proportional to total_reach_historical."""
    # Ad A: 200 total reach
    ad_a = Ad(
        ad_id=1,
        seller_id=100,
        category_id=1234,
        daily_budget=0.0,
        remaining_budget=0.0,
        actual_spend=0.0,
        simulated_reach=0,
        simulated_spending=0.0,
        total_reach_historical=200
    )

    # Ad B: 100 total reach (half of A)
    ad_b = Ad(
        ad_id=2,
        seller_id=200,
        category_id=1234,
        daily_budget=0.0,
        remaining_budget=0.0,
        actual_spend=0.0,
        simulated_reach=0,
        simulated_spending=0.0,
        total_reach_historical=100
    )

    ads = [ad_a, ad_b]
    remaining_slots = 30

    # Run organic fallback
    engine.distribute_organic_proportional(ads, remaining_slots, category_id=1234, hour=0)

    # Ad A should get ~20, Ad B should get ~10 (2:1 ratio)
    # Allow ±1 for rounding
    expected_a = 20
    expected_b = 10

    assert abs(ad_a.simulated_reach - expected_a) <= 1, f"Ad A should get ~{expected_a}, got {ad_a.simulated_reach}"
    assert abs(ad_b.simulated_reach - expected_b) <= 1, f"Ad B should get ~{expected_b}, got {ad_b.simulated_reach}"
    assert ad_a.simulated_reach + ad_b.simulated_reach == remaining_slots, "Conservation violated"


def test_conservation_holds_with_total_reach(engine):
    """Test that conservation property holds with total_reach_historical basis."""
    # Create various ads with different total_reach values
    ads = []
    for i in range(10):
        ad = Ad(
            ad_id=i,
            seller_id=100 + i,
            category_id=1234,
            daily_budget=0.0,
            remaining_budget=0.0,
            actual_spend=0.0,
            simulated_reach=0,
            simulated_spending=0.0,
            total_reach_historical=(i + 1) * 10  # 10, 20, 30, ..., 100
        )
        ads.append(ad)

    # Test with various remaining_slots values
    for remaining_slots in [10, 40, 100, 173]:  # Various values including odd numbers
        # Reset simulated_reach
        for ad in ads:
            ad.simulated_reach = 0

        # Run organic fallback
        engine.distribute_organic_proportional(ads, remaining_slots, category_id=1234, hour=0)

        # Check conservation
        total_allocated = sum(ad.simulated_reach for ad in ads)
        assert total_allocated == remaining_slots, \
            f"Conservation violated: allocated {total_allocated} != {remaining_slots}"


def test_zero_total_reach_fallback_to_equal(engine):
    """Test that if all ads have total_reach_historical=0, fallback to equal distribution."""
    # Create ads with zero total_reach
    ads = []
    for i in range(5):
        ad = Ad(
            ad_id=i,
            seller_id=100 + i,
            category_id=1234,
            daily_budget=0.0,
            remaining_budget=0.0,
            actual_spend=0.0,
            simulated_reach=0,
            simulated_spending=0.0,
            total_reach_historical=0  # No historical reach
        )
        ads.append(ad)

    remaining_slots = 50

    # Run organic fallback - should fallback to equal distribution
    engine.distribute_organic_proportional(ads, remaining_slots, category_id=1234, hour=0)

    # All ads should get equal allocation (10 each)
    for ad in ads:
        assert ad.simulated_reach == 10, f"Ad {ad.ad_id} should get 10 slots (equal distribution)"

    total_allocated = sum(ad.simulated_reach for ad in ads)
    assert total_allocated == remaining_slots, "Conservation violated"


def test_cumulative_allocator_zero_drift_multi_batch(engine):
    """
    Test that cumulative allocator maintains zero drift across many batches.

    Regression test for conservation drift bug where carry clamping to zero
    caused systematic over-allocation. With proper negative carry (debt) handling,
    total allocation across batches should exactly equal total slots.
    """
    # Create ads with varying reach
    ads = []
    for i in range(10):
        ad = Ad(
            ad_id=i,
            seller_id=100 + i,
            category_id=1234,
            daily_budget=0.0,
            remaining_budget=0.0,
            actual_spend=0.0,
            simulated_reach=0,
            simulated_spending=0.0,
            total_reach_historical=(i + 1) * 10  # 10, 20, 30, ..., 100
        )
        ads.append(ad)

    # Simulate many small batches (stress test for drift accumulation)
    total_target_slots = 0
    for batch in range(100):
        # Small batch sizes (where rounding matters most)
        slots = 7  # Prime number to maximize rounding edge cases
        total_target_slots += slots

        # Reset reach for this batch
        for ad in ads:
            ad.simulated_reach = 0

        # Allocate using pool split method (which uses cumulative allocator)
        engine.distribute_organic_with_pool_split(
            ads,
            remaining_slots=slots,
            category_id=1234,
            hour=0
        )

    # Check cumulative allocation
    total_allocated = sum(ad.simulated_reach for ad in ads)

    # With negative carry support, drift should be zero
    assert total_allocated == total_target_slots, \
        f"Conservation drift detected: allocated {total_allocated} != target {total_target_slots} " \
        f"(drift={total_allocated - total_target_slots})"


def test_cumulative_allocator_negative_carry_debt(engine):
    """
    Test that negative carry (debt) is properly handled and recovers over time.

    When an ad receives a residual slot before accumulating full carry,
    carry should go negative (debt), which is paid back in future batches.
    This ensures exact conservation without systematic drift.
    """
    # Simple scenario: 2 ads, many small batches
    ad_a = Ad(
        ad_id=1,
        seller_id=100,
        category_id=1234,
        daily_budget=0.0,
        remaining_budget=0.0,
        actual_spend=0.0,
        simulated_reach=0,
        simulated_spending=0.0,
        total_reach_historical=100  # 50% share
    )

    ad_b = Ad(
        ad_id=2,
        seller_id=200,
        category_id=1234,
        daily_budget=0.0,
        remaining_budget=0.0,
        actual_spend=0.0,
        simulated_reach=0,
        simulated_spending=0.0,
        total_reach_historical=100  # 50% share
    )

    ads = [ad_a, ad_b]

    # Run many batches with odd slot counts (forces residual allocation)
    cumulative_target = 0
    cumulative_actual = 0

    for batch in range(50):
        slots = 3  # Odd number: each ad gets proportion = 1.5, floor = 1, residual = 1
        cumulative_target += slots

        for ad in ads:
            ad.simulated_reach = 0

        engine.distribute_organic_with_pool_split(
            ads,
            remaining_slots=slots,
            category_id=1234,
            hour=0
        )

        cumulative_actual += sum(ad.simulated_reach for ad in ads)

    # Over 50 batches, cumulative allocation must equal cumulative target
    assert cumulative_actual == cumulative_target, \
        f"Cumulative drift: allocated {cumulative_actual} != target {cumulative_target}"

    # Individual ad allocations should also be balanced (within ±1 due to tie-breaking)
    assert abs(ad_a.simulated_reach - ad_b.simulated_reach) <= 1, \
        f"Ads with equal reach should have similar allocation (A={ad_a.simulated_reach}, B={ad_b.simulated_reach})"
