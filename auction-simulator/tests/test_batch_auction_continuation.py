"""
Tests for batch auction continuation fix.

Tests verify that batch auction continues processing batches even when
paid ads < batch_size, properly distributing remaining slots via organic fallback.
"""

import pytest
from auction_simulator.auction_engine import Ad, AuctionEngine
from auction_simulator.config import Config
from auction_simulator.simulation import Simulation


@pytest.fixture
def config():
    """Create test configuration."""
    return Config({
        'simulation': {
            'min_time_left_threshold': 0.001,
            'min_time_progress_threshold': 0.042,
            'pacing_tolerance': 0.2,
            'bid_step': 0.003,
            'batch_size': 40
        }
    })


@pytest.fixture
def simulation(config):
    """Create simulation instance."""
    # Mock data loading
    sim = Simulation.__new__(Simulation)
    sim.config = config
    sim.engine = AuctionEngine(config)
    sim.sim_logger = None  # No logging in tests
    return sim


def test_multiple_batches_with_few_paid_ads(simulation):
    """
    Test that paid ads participate in multiple batches when ads_with_budget < batch_size.

    Setup: 4 paid ads, 160 total slots, batch_size=40
    Expected: 4 batches run, each with 4 paid + 36 organic
    """
    # Create 4 paid ads with budget
    paid_ads = []
    for i in range(4):
        ad = Ad(
            ad_id=i,
            seller_id=100 + i,
            category_id=1234,
            daily_budget=100.0,  # 100 kopecks = 1 AZN
            remaining_budget=100.0,
            actual_spend=0.0,
            simulated_reach=0,
            simulated_spending=0.0,
            total_reach_historical=100  # Historical reach
        )
        paid_ads.append(ad)

    # Create 10 organic ads (no budget)
    organic_ads = []
    for i in range(10):
        ad = Ad(
            ad_id=100 + i,
            seller_id=200 + i,
            category_id=1234,
            daily_budget=0.0,
            remaining_budget=0.0,
            actual_spend=0.0,
            simulated_reach=0,
            simulated_spending=0.0,
            total_reach_historical=50
        )
        organic_ads.append(ad)

    all_ads = paid_ads + organic_ads

    # Run auction
    min_bid = 0.1
    time_progress = 0.5
    time_left = 0.5
    total_slots = 160

    result = simulation.run_hour_auction(
        all_ads,
        min_bid,
        time_progress,
        time_left,
        total_slots,
        category_id=1234,
        hour=10
    )

    # Verify result structure
    assert 'batch_count' in result
    assert 'paid_slots' in result
    assert 'organic_slots' in result

    # Verify 4 batches ran
    assert result['batch_count'] == 4, f"Expected 4 batches, got {result['batch_count']}"

    # Verify paid slots: 4 batches × 4 ads = 16
    assert result['paid_slots'] == 16, f"Expected 16 paid slots, got {result['paid_slots']}"

    # Verify organic slots: 160 - 16 = 144
    assert result['organic_slots'] == 144, f"Expected 144 organic slots, got {result['organic_slots']}"

    # Verify conservation
    assert result['paid_slots'] + result['organic_slots'] == total_slots


def test_organic_fallback_called_per_batch(simulation):
    """
    Test that organic fallback is called once per batch, not once at end.

    This ensures proper interleaving of paid and organic reach.
    """
    # Create 2 paid ads
    paid_ads = []
    for i in range(2):
        ad = Ad(
            ad_id=i,
            seller_id=100 + i,
            category_id=1234,
            daily_budget=50.0,
            remaining_budget=50.0,
            actual_spend=0.0,
            simulated_reach=0,
            simulated_spending=0.0,
            total_reach_historical=100
        )
        paid_ads.append(ad)

    # Create 5 organic ads
    organic_ads = []
    for i in range(5):
        ad = Ad(
            ad_id=100 + i,
            seller_id=200 + i,
            category_id=1234,
            daily_budget=0.0,
            remaining_budget=0.0,
            actual_spend=0.0,
            simulated_reach=0,
            simulated_spending=0.0,
            total_reach_historical=50
        )
        organic_ads.append(ad)

    all_ads = paid_ads + organic_ads

    # Run auction for 80 slots (2 batches)
    result = simulation.run_hour_auction(
        all_ads,
        min_bid=0.1,
        time_progress=0.5,
        time_left=0.5,
        total_slots=80,
        category_id=1234,
        hour=10
    )

    # Verify 2 batches
    assert result['batch_count'] == 2

    # Verify paid: 2 batches × 2 ads = 4
    assert result['paid_slots'] == 4

    # Verify organic: 80 - 4 = 76
    assert result['organic_slots'] == 76

    # Verify organic ads received reach (not all in paid ads)
    organic_reach = sum(ad.simulated_reach for ad in organic_ads)
    assert organic_reach > 0, "Organic ads should receive reach"


def test_conservation_with_mixed_batches(simulation):
    """
    Test conservation property holds with mixed paid/organic batches.

    Tests various combinations of ads_with_budget and total_slots.
    """
    test_cases = [
        # (num_paid, num_organic, total_slots)
        (3, 10, 120),
        (5, 20, 200),
        (1, 5, 40),
        (10, 50, 160),
    ]

    for num_paid, num_organic, total_slots in test_cases:
        # Create paid ads
        paid_ads = [
            Ad(
                ad_id=i,
                seller_id=100 + i,
                category_id=1234,
                daily_budget=100.0,
                remaining_budget=100.0,
                actual_spend=0.0,
                simulated_reach=0,
                simulated_spending=0.0,
                total_reach_historical=100
            )
            for i in range(num_paid)
        ]

        # Create organic ads
        organic_ads = [
            Ad(
                ad_id=100 + i,
                seller_id=200 + i,
                category_id=1234,
                daily_budget=0.0,
                remaining_budget=0.0,
                actual_spend=0.0,
                simulated_reach=0,
                simulated_spending=0.0,
                total_reach_historical=50
            )
            for i in range(num_organic)
        ]

        all_ads = paid_ads + organic_ads

        # Reset reach
        for ad in all_ads:
            ad.simulated_reach = 0

        # Run auction
        result = simulation.run_hour_auction(
            all_ads,
            min_bid=0.1,
            time_progress=0.5,
            time_left=0.5,
            total_slots=total_slots,
            category_id=1234,
            hour=10
        )

        # Verify conservation
        assert result['paid_slots'] + result['organic_slots'] == total_slots, \
            f"Conservation violated for {num_paid} paid, {num_organic} organic, {total_slots} slots: " \
            f"paid={result['paid_slots']}, organic={result['organic_slots']}"


def test_budget_exhaustion_stops_correctly(simulation):
    """
    Test that loop stops when all ads exhaust budget.

    Setup: 2 ads with small budget that exhausts after ~2 batches
    """
    # Create 2 paid ads with very small budget
    paid_ads = []
    for i in range(2):
        ad = Ad(
            ad_id=i,
            seller_id=100 + i,
            category_id=1234,
            daily_budget=1.0,  # 1 kopeck (very small)
            remaining_budget=1.0,
            actual_spend=0.0,
            simulated_reach=0,
            simulated_spending=0.0,
            total_reach_historical=100
        )
        paid_ads.append(ad)

    # Create 5 organic ads
    organic_ads = []
    for i in range(5):
        ad = Ad(
            ad_id=100 + i,
            seller_id=200 + i,
            category_id=1234,
            daily_budget=0.0,
            remaining_budget=0.0,
            actual_spend=0.0,
            simulated_reach=0,
            simulated_spending=0.0,
            total_reach_historical=50
        )
        organic_ads.append(ad)

    all_ads = paid_ads + organic_ads

    # Run auction for 200 slots (would be 5 batches if budget didn't exhaust)
    result = simulation.run_hour_auction(
        all_ads,
        min_bid=0.1,
        time_progress=0.5,
        time_left=0.5,
        total_slots=200,
        category_id=1234,
        hour=10
    )

    # Budget should limit paid slots (not all 200 slots can be paid with 1 kopeck budget)
    # With 2 ads, each batch allocates 2 paid slots
    # Budget allows ~2-5 batches depending on CPR
    assert result['paid_slots'] < 20, \
        f"Expected paid_slots < 20 (limited by budget), got {result['paid_slots']}"

    # Organic should fill the rest
    assert result['organic_slots'] == 200 - result['paid_slots']

    # Conservation should hold
    assert result['paid_slots'] + result['organic_slots'] == 200

    # At least one ad should have spent some budget
    total_spent = sum(ad.actual_spend for ad in paid_ads)
    assert total_spent > 0, "Paid ads should have spent some budget"


def test_return_dict_structure(simulation):
    """
    Test that run_hour_auction returns correct dict structure.
    """
    # Create minimal setup
    ads = [
        Ad(
            ad_id=1,
            seller_id=100,
            category_id=1234,
            daily_budget=50.0,
            remaining_budget=50.0,
            actual_spend=0.0,
            simulated_reach=0,
            simulated_spending=0.0,
            total_reach_historical=100
        ),
        Ad(
            ad_id=2,
            seller_id=200,
            category_id=1234,
            daily_budget=0.0,
            remaining_budget=0.0,
            actual_spend=0.0,
            simulated_reach=0,
            simulated_spending=0.0,
            total_reach_historical=50
        )
    ]

    result = simulation.run_hour_auction(
        ads,
        min_bid=0.1,
        time_progress=0.5,
        time_left=0.5,
        total_slots=40,
        category_id=1234,
        hour=10
    )

    # Verify structure
    assert isinstance(result, dict), "Result should be a dict"
    assert 'batch_count' in result, "Missing 'batch_count' key"
    assert 'paid_slots' in result, "Missing 'paid_slots' key"
    assert 'organic_slots' in result, "Missing 'organic_slots' key"

    # Verify types
    assert isinstance(result['batch_count'], int), "batch_count should be int"
    assert isinstance(result['paid_slots'], int), "paid_slots should be int"
    assert isinstance(result['organic_slots'], int), "organic_slots should be int"

    # Verify values make sense
    assert result['batch_count'] >= 0
    assert result['paid_slots'] >= 0
    assert result['organic_slots'] >= 0
    assert result['paid_slots'] + result['organic_slots'] == 40
