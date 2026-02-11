#!/usr/bin/env python3
"""
Comparison of pacing gate behavior: before vs after min_time_progress_threshold

Simulates first 5 auction batches at hour=0 to demonstrate the blocking issue.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class Ad:
    ad_id: int
    daily_budget: float
    actual_spend: float = 0.0


def pacing_gate_OLD(ad: Ad, time_progress: float, pacing_tolerance: float) -> tuple[bool, float]:
    """Current implementation - blocks everything at hour=0 after first batch."""
    if ad.daily_budget <= 0:
        return True, 0.0

    expected_spend = ad.daily_budget * time_progress
    max_allowed = expected_spend * (1 + pacing_tolerance)
    is_eligible = ad.actual_spend <= max_allowed

    return is_eligible, max_allowed


def pacing_gate_NEW(ad: Ad, time_progress: float, pacing_tolerance: float,
                     min_time_progress_threshold: float) -> tuple[bool, float]:
    """New implementation with min_time_progress_threshold."""
    if ad.daily_budget <= 0:
        return True, 0.0

    # Apply minimum threshold (similar to min_time_left_threshold)
    safe_time_progress = max(time_progress, min_time_progress_threshold)

    expected_spend = ad.daily_budget * safe_time_progress
    max_allowed = expected_spend * (1 + pacing_tolerance)
    is_eligible = ad.actual_spend <= max_allowed

    return is_eligible, max_allowed


def simulate_batches():
    """Simulate first 5 batches at hour=0."""

    # Configuration
    HOUR = 0
    time_progress = HOUR / 24.0  # 0.0 at hour 0
    pacing_tolerance = 0.2
    min_time_progress_threshold = 0.042  # 1 hour = 1/24

    # Test ads
    ads = [
        Ad(ad_id=1, daily_budget=100.0),
        Ad(ad_id=2, daily_budget=100.0),
        Ad(ad_id=3, daily_budget=100.0),
    ]

    # Cost per auction win (typical bid)
    cost_per_win = 0.15

    print("=" * 80)
    print("ПОРІВНЯННЯ PACING GATE: БЕЗ vs З min_time_progress_threshold")
    print("=" * 80)
    print(f"\n📊 Конфігурація:")
    print(f"   hour = {HOUR}")
    print(f"   time_progress = {time_progress:.3f}")
    print(f"   pacing_tolerance = {pacing_tolerance}")
    print(f"   min_time_progress_threshold = {min_time_progress_threshold}")
    print(f"   daily_budget = 100.0 коп.")
    print(f"   cost_per_win = {cost_per_win} коп.")
    print()

    # Run OLD implementation
    print("🔴 БЕЗ min_time_progress_threshold (поточна логіка):")
    print("-" * 80)

    ads_old = [Ad(ad_id=a.ad_id, daily_budget=a.daily_budget) for a in ads]
    eligible_count_old = []

    for batch in range(1, 6):
        print(f"\nБатч #{batch} (00:0{batch}):")

        eligible_ads = []
        blocked_ads = []

        for ad in ads_old:
            is_eligible, max_allowed = pacing_gate_OLD(ad, time_progress, pacing_tolerance)

            if is_eligible:
                eligible_ads.append(ad)
                print(f"   Ad {ad.ad_id}: ✅ ELIGIBLE | spend={ad.actual_spend:.4f} <= max={max_allowed:.4f}")
                # Simulate win and charge
                ad.actual_spend += cost_per_win
            else:
                blocked_ads.append(ad)
                print(f"   Ad {ad.ad_id}: ❌ BLOCKED  | spend={ad.actual_spend:.4f} > max={max_allowed:.4f}")

        eligible_count_old.append(len(eligible_ads))
        print(f"   📊 Eligible: {len(eligible_ads)}/{len(ads_old)}, Blocked: {len(blocked_ads)}/{len(ads_old)}")

    # Run NEW implementation
    print("\n" + "=" * 80)
    print("🟢 З min_time_progress_threshold (нова логіка):")
    print("-" * 80)

    ads_new = [Ad(ad_id=a.ad_id, daily_budget=a.daily_budget) for a in ads]
    eligible_count_new = []

    for batch in range(1, 6):
        print(f"\nБатч #{batch} (00:0{batch}):")

        eligible_ads = []
        blocked_ads = []

        for ad in ads_new:
            is_eligible, max_allowed = pacing_gate_NEW(
                ad, time_progress, pacing_tolerance, min_time_progress_threshold
            )

            if is_eligible:
                eligible_ads.append(ad)
                print(f"   Ad {ad.ad_id}: ✅ ELIGIBLE | spend={ad.actual_spend:.4f} <= max={max_allowed:.4f}")
                # Simulate win and charge
                ad.actual_spend += cost_per_win
            else:
                blocked_ads.append(ad)
                print(f"   Ad {ad.ad_id}: ❌ BLOCKED  | spend={ad.actual_spend:.4f} > max={max_allowed:.4f}")

        eligible_count_new.append(len(eligible_ads))
        print(f"   📊 Eligible: {len(eligible_ads)}/{len(ads_new)}, Blocked: {len(blocked_ads)}/{len(ads_new)}")

    # Summary comparison
    print("\n" + "=" * 80)
    print("📊 ПІДСУМОК ПОРІВНЯННЯ")
    print("=" * 80)

    print("\n| Батч | БЕЗ threshold | З threshold | Різниця |")
    print("|------|---------------|-------------|---------|")
    for i in range(5):
        old = eligible_count_old[i]
        new = eligible_count_new[i]
        diff = "✅ FIX!" if new > old else "="
        print(f"|  {i+1}   |     {old}/3       |    {new}/3      | {diff:^7} |")

    print("\n💡 Пояснення:")
    print("\n🔴 БЕЗ threshold:")
    print(f"   expected_spend = 100 × {time_progress} = {100 * time_progress:.4f} коп.")
    print(f"   max_allowed = {100 * time_progress:.4f} × 1.2 = {100 * time_progress * 1.2:.4f} коп.")
    print(f"   ❌ Після першого батчу (spend=0.15) всі ads блокуються!")

    print("\n🟢 З threshold:")
    safe_progress = max(time_progress, min_time_progress_threshold)
    print(f"   safe_time_progress = max({time_progress}, {min_time_progress_threshold}) = {safe_progress}")
    print(f"   expected_spend = 100 × {safe_progress} = {100 * safe_progress:.4f} коп.")
    print(f"   max_allowed = {100 * safe_progress:.4f} × 1.2 = {100 * safe_progress * 1.2:.4f} коп.")
    print(f"   ✅ Ads можуть витратити до {100 * safe_progress * 1.2:.4f} коп. протягом години!")

    print("\n📈 Очікувана поведінка:")
    max_spend = 100 * safe_progress * 1.2
    batches_before_block = int(max_spend / cost_per_win)
    print(f"   Кожен ad може виграти ~{batches_before_block} аукціонів перед блокуванням")
    print(f"   (max_allowed={max_spend:.4f} / cost={cost_per_win} = {batches_before_block} wins)")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    simulate_batches()
