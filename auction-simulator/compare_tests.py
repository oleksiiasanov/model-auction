import pandas as pd

print("=" * 80)
print("ПОРІВНЯННЯ ТЕСТІВ: bid_step 0.003 vs 0.005")
print("=" * 80)

# Baseline: bid_step=0.003
baseline_ads = pd.read_csv("outputs/ad_comparison_20260205_133938.csv")
baseline_sellers = pd.read_csv("outputs/seller_comparison_20260205_133938.csv")

# Test: bid_step=0.005
test_ads = pd.read_csv("outputs/ad_comparison_20260205_134055.csv")
test_sellers = pd.read_csv("outputs/seller_comparison_20260205_134055.csv")

print("\n📊 МЕТРИКИ (Baseline vs Test):\n")

# Budget utilization
baseline_budget = baseline_ads[baseline_ads['is_paid_actual']]['daily_budget_azn'].sum()
baseline_spent = baseline_ads['simulated_spending_azn'].sum()
test_budget = test_ads[test_ads['is_paid_actual']]['daily_budget_azn'].sum()
test_spent = test_ads['simulated_spending_azn'].sum()

print(f"1. Budget Utilization:")
print(f"   Baseline: {baseline_spent:.2f}/{baseline_budget:.2f} AZN ({baseline_spent/baseline_budget*100:.1f}%)")
print(f"   Test:     {test_spent:.2f}/{test_budget:.2f} AZN ({test_spent/test_budget*100:.1f}%)")
print(f"   Δ:        {(test_spent/test_budget - baseline_spent/baseline_budget)*100:+.1f}%")

# Free ads coverage
baseline_free = len(baseline_ads[(baseline_ads['is_paid_actual']==False) & (baseline_ads['simulated_reach_total']>0)])
baseline_free_total = len(baseline_ads[baseline_ads['is_paid_actual']==False])
test_free = len(test_ads[(test_ads['is_paid_actual']==False) & (test_ads['simulated_reach_total']>0)])
test_free_total = len(test_ads[test_ads['is_paid_actual']==False])

print(f"\n2. Free Ads Coverage:")
print(f"   Baseline: {baseline_free}/{baseline_free_total} ({baseline_free/baseline_free_total*100:.2f}%)")
print(f"   Test:     {test_free}/{test_free_total} ({test_free/test_free_total*100:.2f}%)")

# Paid ads coverage
baseline_paid = len(baseline_ads[(baseline_ads['is_paid_actual']==True) & (baseline_ads['simulated_reach_total']>0)])
baseline_paid_total = len(baseline_ads[baseline_ads['is_paid_actual']==True])
test_paid = len(test_ads[(test_ads['is_paid_actual']==True) & (test_ads['simulated_reach_total']>0)])
test_paid_total = len(test_ads[test_ads['is_paid_actual']==True])

print(f"\n3. Paid Ads Coverage:")
print(f"   Baseline: {baseline_paid}/{baseline_paid_total} ({baseline_paid/baseline_paid_total*100:.1f}%)")
print(f"   Test:     {test_paid}/{test_paid_total} ({test_paid/test_paid_total*100:.1f}%)")

# Reach distribution
baseline_paid_reach = baseline_ads[baseline_ads['is_paid_simulated']==True]['simulated_reach_total'].sum()
baseline_free_reach = baseline_ads[(baseline_ads['is_paid_simulated']==False) & (baseline_ads['simulated_reach_total']>0)]['simulated_reach_total'].sum()
baseline_total_reach = baseline_ads['simulated_reach_total'].sum()

test_paid_reach = test_ads[test_ads['is_paid_simulated']==True]['simulated_reach_total'].sum()
test_free_reach = test_ads[(test_ads['is_paid_simulated']==False) & (test_ads['simulated_reach_total']>0)]['simulated_reach_total'].sum()
test_total_reach = test_ads['simulated_reach_total'].sum()

print(f"\n4. Reach Distribution (Simulated):")
print(f"   Baseline Paid:    {baseline_paid_reach:,} ({baseline_paid_reach/baseline_total_reach*100:.1f}%)")
print(f"   Baseline Organic: {baseline_free_reach:,} ({baseline_free_reach/baseline_total_reach*100:.1f}%)")
print(f"   Test Paid:        {test_paid_reach:,} ({test_paid_reach/test_total_reach*100:.1f}%)")
print(f"   Test Organic:     {test_free_reach:,} ({test_free_reach/test_total_reach*100:.1f}%)")

# Reach accuracy (порівняння з actual)
baseline_actual_paid = baseline_ads['actual_reach_paid'].sum()
test_actual_paid = test_ads['actual_reach_paid'].sum()

print(f"\n5. Reach Accuracy (vs Actual):")
print(f"   Actual Paid Reach: {baseline_actual_paid:,}")
print(f"   Baseline Simulated: {baseline_paid_reach:,} (accuracy: {(1-abs(baseline_paid_reach-baseline_actual_paid)/baseline_actual_paid)*100:.1f}%)")
print(f"   Test Simulated:     {test_paid_reach:,} (accuracy: {(1-abs(test_paid_reach-test_actual_paid)/test_actual_paid)*100:.1f}%)")

print("\n" + "=" * 80)
