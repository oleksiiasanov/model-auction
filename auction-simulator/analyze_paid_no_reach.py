import pandas as pd
import json

# Читаємо ad_comparison
df = pd.read_csv('outputs/ad_comparison_20260204_212804.csv', comment='#')

# Знаходимо paid ads без simulated reach
paid_ads = df[df['is_paid_actual'] == True]
paid_no_reach = paid_ads[paid_ads['simulated_reach_total'] == 0]

print(f"Paid ads БЕЗ simulated reach: {len(paid_no_reach)}")
print()

# Виводимо top 5 для детального аналізу
print("TOP 5 для аналізу:")
for idx, row in paid_no_reach.head(5).iterrows():
    print(f"\nad_id: {int(row['ad_id'])}")
    print(f"  seller_id: {int(row['seller_id'])}")
    print(f"  actual_reach_total: {row['actual_reach_total']:.0f}")
    print(f"  actual_reach_paid: {row['actual_reach_paid']:.0f}")
    print(f"  actual_reach_organic: {row['actual_reach_organic']:.0f}")
    print(f"  actual_spending: {row['actual_spending_azn']:.4f} AZN")

# Зберігаємо список ad_id для пошуку в логах
ad_ids = paid_no_reach['ad_id'].head(5).tolist()
print(f"\nAd IDs для пошуку в логах: {[int(x) for x in ad_ids]}")

# Зберігаємо в файл
with open('paid_no_reach_ids.txt', 'w') as f:
    for ad_id in ad_ids:
        f.write(f"{int(ad_id)}\n")
