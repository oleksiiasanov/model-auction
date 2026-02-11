#!/usr/bin/env python3
"""
Test the new filename format for output files.
Format: HHMMSS_country_XX_category_YY_bidstep_0.XXXX_<type>.{csv|txt}
"""

from datetime import datetime

def build_filename(country, categories, bid_step):
    """Build filename with new format."""
    time_prefix = datetime.now().strftime("%H%M%S")
    filename_parts = [time_prefix]

    if country is not None:
        filename_parts.append(f"country_{country}")

    if categories is not None:
        cat_list = [c.strip() for c in categories.split(',')]
        if len(cat_list) == 1:
            filename_parts.append(f"category_{cat_list[0]}")
        else:
            filename_parts.append(f"categories_{'_'.join(cat_list)}")

    if bid_step is not None:
        filename_parts.append(f"bidstep_{bid_step:.4f}")

    return "_".join(filename_parts)

# Test cases
test_cases = [
    (13, "6282", 0.003, "Single category"),
    (13, "6282", 0.005, "Single category, different bid_step"),
    (13, "6282,1234", 0.003, "Multiple categories"),
    (13, "6282, 1234, 5678", 0.0075, "Multiple categories with spaces"),
]

print("=" * 80)
print("FILENAME FORMAT TEST")
print("=" * 80)
print()

for country, categories, bid_step, description in test_cases:
    base = build_filename(country, categories, bid_step)
    print(f"Test: {description}")
    print(f"  seller_comparison_{base}.csv")
    print(f"  ad_comparison_{base}.csv")
    print(f"  summary_statistics_{base}.txt")
    print()

print("=" * 80)
print("EXAMPLE OUTPUT")
print("=" * 80)
print()
print("When running:")
print("  python -m auction_simulator.cli simulate \\")
print("    --country 13 \\")
print("    --categories 6282 \\")
print("    --bid-step 0.005 \\")
print("    --time-from 2026-01-31 \\")
print("    --time-to 2026-02-01")
print()
print("Output files will be named:")
base = build_filename(13, "6282", 0.005)
print(f"  {base}_seller_comparison.csv")
print(f"  {base}_ad_comparison.csv")
print(f"  {base}_summary_statistics.txt")
print()
