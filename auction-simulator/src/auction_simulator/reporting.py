"""
Comparison reporting for auction simulation results.

Generates CSV reports comparing actual vs simulated metrics.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Tuple
import pandas as pd

logger = logging.getLogger(__name__)


def get_currency(country_id: int) -> str:
    """
    Get currency code for a given country.

    Args:
        country_id: Country identifier

    Returns:
        Currency code (e.g., 'AZN', 'KGS')
    """
    currency_map = {
        12: 'KGS',  # Kyrgyzstan
        13: 'AZN',  # Azerbaijan
    }
    return currency_map.get(country_id, 'AZN')  # Default to AZN if unknown


class Reporter:
    """Generates comparison reports for simulation results."""

    def __init__(self, config):
        """
        Initialize reporter.

        Args:
            config: Configuration object
        """
        self.config = config
        self.output_dir = Path(config.reporting.output_directory)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_reports(
        self,
        impressions_df: pd.DataFrame,
        budgets_df: pd.DataFrame,
        simulation_results: pd.DataFrame,
        time_from,
        time_to,
        min_bid_by_category: dict = None,
        bid_step: float = None,
        country: int = None,
        categories: str = None
    ):
        """
        Generate all comparison reports.

        Args:
            impressions_df: Historical impression data
            budgets_df: Historical budget data
            simulation_results: Simulation results from Simulation.run_simulation()
            time_from: Start date
            time_to: End date
            min_bid_by_category: Dictionary of {category_id: min_bid} values
            bid_step: bid_step value used in simulation
            country: Country ID
            categories: Comma-separated category IDs
        """
        logger.info("Generating comparison reports...")

        # Build filename with format: HHMMSS_country_XX_category_YY_bidstep_0.XXX
        time_prefix = datetime.now().strftime("%H%M%S")
        filename_parts = [time_prefix]

        if country is not None:
            filename_parts.append(f"country_{country}")

        if categories is not None:
            # Handle multiple categories: use first one or join with underscore
            cat_list = [c.strip() for c in categories.split(',')]
            if len(cat_list) == 1:
                filename_parts.append(f"category_{cat_list[0]}")
            elif len(cat_list) <= 5:
                filename_parts.append(f"categories_{'_'.join(cat_list)}")
            else:
                # Too many categories - use count instead of listing all
                filename_parts.append(f"all_{len(cat_list)}_categories")

        if bid_step is not None:
            filename_parts.append(f"bidstep_{bid_step:.4f}")

        timestamp = "_".join(filename_parts)

        # Generate per-seller comparison
        seller_comparison = self.build_seller_comparison(
            impressions_df,
            budgets_df,
            simulation_results
        )

        seller_file = self.output_dir / f"seller_comparison_{timestamp}.csv"
        self._save_csv_with_metadata(
            seller_comparison,
            seller_file,
            time_from,
            time_to,
            "Seller-level comparison"
        )

        # Generate per-ad comparison
        ad_comparison = self.build_ad_comparison(
            impressions_df,
            budgets_df,
            simulation_results
        )

        ad_file = self.output_dir / f"ad_comparison_{timestamp}.csv"
        self._save_csv_with_metadata(
            ad_comparison,
            ad_file,
            time_from,
            time_to,
            "Ad-level comparison"
        )

        # Generate summary statistics
        summary = self.build_summary_statistics(
            seller_comparison,
            ad_comparison,
            impressions_df,
            budgets_df,
            simulation_results,
            min_bid_by_category=min_bid_by_category,
            bid_step=bid_step,
            country=country
        )

        summary_file = self.output_dir / f"summary_statistics_{timestamp}.txt"
        self._save_summary(summary, summary_file, time_from, time_to)

        logger.info(f"Reports saved to {self.output_dir}")

    def build_seller_comparison(
        self,
        impressions_df: pd.DataFrame,
        budgets_df: pd.DataFrame,
        simulation_results: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Build seller-level comparison table.

        Returns DataFrame with columns:
        - seller_id
        - actual_reach_total
        - actual_reach_paid
        - actual_reach_organic
        - actual_spending
        - simulated_reach_total
        - simulated_spending
        - diff_reach_total
        - diff_spending
        """
        # Aggregate actual reach by seller
        actual_reach = impressions_df.groupby('seller_id').agg({
            'total_reach': 'sum',
            'organic_reach': 'sum'
        }).reset_index()

        actual_reach['paid_reach'] = (
            actual_reach['total_reach'] -
            actual_reach['organic_reach']
        )

        actual_reach.rename(columns={
            'total_reach': 'actual_reach_total',
            'organic_reach': 'actual_reach_organic',
            'paid_reach': 'actual_reach_paid'
        }, inplace=True)

        # Aggregate actual spending by seller
        actual_spending = budgets_df.groupby('seller_id').agg({
            'actual_spend': 'sum'
        }).reset_index()

        actual_spending.rename(columns={
            'actual_spend': 'actual_spending'
        }, inplace=True)

        # Convert Decimal to float to avoid type errors in calculations
        actual_spending['actual_spending'] = actual_spending['actual_spending'].astype(float)

        # Aggregate simulated results by seller
        simulated = simulation_results.groupby('seller_id').agg({
            'simulated_reach': 'sum',
            'simulated_spending': 'sum'
        }).reset_index()

        simulated.rename(columns={
            'simulated_reach': 'simulated_reach_total',
            'simulated_spending': 'simulated_spending'
        }, inplace=True)

        # Merge all
        comparison = actual_reach.merge(
            actual_spending,
            on='seller_id',
            how='outer'
        ).merge(
            simulated,
            on='seller_id',
            how='outer'
        ).fillna(0)

        # Calculate paid status flags
        # is_paid_actual: TRUE if seller had at least one ad with daily_budget > 0
        seller_max_budgets = budgets_df.groupby('seller_id')['daily_budget'].max()
        comparison['is_paid_actual'] = comparison['seller_id'].map(
            lambda sid: seller_max_budgets.get(sid, 0) > 0
        ).fillna(False)

        # is_paid_simulated: TRUE if seller spent any budget in simulation
        comparison['is_paid_simulated'] = comparison['simulated_spending'] > 0

        # Reorder columns: seller_id, is_paid_*, then metrics
        cols = ['seller_id', 'is_paid_actual', 'is_paid_simulated']
        other_cols = [c for c in comparison.columns if c not in cols]
        comparison = comparison[cols + other_cols]

        # Calculate differences
        comparison['diff_reach_total'] = (
            comparison['simulated_reach_total'] -
            comparison['actual_reach_total']
        )

        comparison['diff_spending'] = (
            comparison['simulated_spending'] -
            comparison['actual_spending']
        )

        # Convert kopecks to currency for spending columns
        for col in ['actual_spending', 'simulated_spending', 'diff_spending']:
            comparison[f'{col}_azn'] = comparison[col] / 100
            comparison.drop(columns=[col], inplace=True)

        return comparison

    def build_ad_comparison(
        self,
        impressions_df: pd.DataFrame,
        budgets_df: pd.DataFrame,
        simulation_results: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Build ad-level comparison table.

        Returns DataFrame with columns:
        - ad_id
        - seller_id
        - category_id
        - actual_reach_total
        - actual_reach_paid
        - actual_reach_organic
        - actual_spending
        - simulated_reach_total
        - simulated_spending
        - diff_reach_total
        - diff_spending
        """
        # Aggregate actual reach by ad
        actual_reach = impressions_df.groupby(['ad_id', 'seller_id', 'category_id']).agg({
            'total_reach': 'sum',
            'organic_reach': 'sum'
        }).reset_index()

        actual_reach['paid_reach'] = (
            actual_reach['total_reach'] -
            actual_reach['organic_reach']
        )

        actual_reach.rename(columns={
            'total_reach': 'actual_reach_total',
            'organic_reach': 'actual_reach_organic',
            'paid_reach': 'actual_reach_paid'
        }, inplace=True)

        # Aggregate actual spending and budget by ad + category.
        # NOTE: category_id is required here to avoid creating synthetic category=0 rows
        # for budget-only ads during outer merge.
        actual_spending = budgets_df.groupby(['ad_id', 'seller_id', 'category_id']).agg({
            'daily_budget': 'sum',
            'actual_spend': 'sum'
        }).reset_index()

        actual_spending.rename(columns={
            'daily_budget': 'daily_budget',
            'actual_spend': 'actual_spending'
        }, inplace=True)

        # Convert Decimal to float to avoid type errors in calculations
        actual_spending['daily_budget'] = actual_spending['daily_budget'].astype(float)
        actual_spending['actual_spending'] = actual_spending['actual_spending'].astype(float)

        # Merge with simulated results
        comparison = actual_reach.merge(
            actual_spending,
            on=['ad_id', 'seller_id', 'category_id'],
            how='outer'
        ).merge(
            simulation_results[['ad_id', 'seller_id', 'category_id',
                                'simulated_reach', 'simulated_spending']],
            on=['ad_id', 'seller_id', 'category_id'],
            how='outer'
        ).fillna(0)

        comparison.rename(columns={
            'simulated_reach': 'simulated_reach_total',
            'simulated_spending': 'simulated_spending'
        }, inplace=True)

        # Calculate paid status flags
        # is_paid_actual: TRUE if ad had daily_budget > 0 on any day
        ad_max_budgets = budgets_df.groupby('ad_id')['daily_budget'].max()
        comparison['is_paid_actual'] = comparison['ad_id'].map(
            lambda aid: ad_max_budgets.get(aid, 0) > 0
        ).fillna(False)

        # is_paid_simulated: TRUE if ad spent any budget in simulation
        comparison['is_paid_simulated'] = comparison['simulated_spending'] > 0

        # Reorder columns: ad_id, seller_id, category_id, is_paid_*, then metrics
        cols = ['ad_id', 'seller_id', 'category_id', 'is_paid_actual', 'is_paid_simulated']
        other_cols = [c for c in comparison.columns if c not in cols]
        comparison = comparison[cols + other_cols]

        # Calculate differences
        comparison['diff_reach_total'] = (
            comparison['simulated_reach_total'] -
            comparison['actual_reach_total']
        )

        comparison['diff_spending'] = (
            comparison['simulated_spending'] -
            comparison['actual_spending']
        )

        # Convert kopecks to currency for spending and budget columns
        for col in ['daily_budget', 'actual_spending', 'simulated_spending', 'diff_spending']:
            comparison[f'{col}_azn'] = comparison[col] / 100
            comparison.drop(columns=[col], inplace=True)

        return comparison

    def build_summary_statistics(
        self,
        seller_comparison: pd.DataFrame,
        ad_comparison: pd.DataFrame,
        impressions_df: pd.DataFrame,
        budgets_df: pd.DataFrame,
        simulation_results: pd.DataFrame,
        min_bid_by_category: dict = None,
        bid_step: float = None,
        country: int = None
    ) -> str:
        """
        Build summary statistics text.

        Args:
            min_bid_by_category: Dictionary of {category_id: min_bid} values
            bid_step: bid_step value used in simulation
            country: Country ID for currency formatting

        Returns:
            Summary statistics as formatted string
        """
        # Get currency for this country
        currency = get_currency(country) if country is not None else 'AZN'

        lines = []
        lines.append("=" * 80)
        lines.append("SIMULATION SUMMARY STATISTICS")
        lines.append("=" * 80)
        lines.append("")

        # Simulation parameters
        if bid_step is not None or min_bid_by_category:
            lines.append("SIMULATION PARAMETERS:")
            if bid_step is not None:
                lines.append(f"  bid_step: {bid_step:.4f}")
            if min_bid_by_category:
                lines.append("  min_bid (by category):")
                for cat_id, min_bid_val in sorted(min_bid_by_category.items()):
                    lines.append(f"    Category {cat_id}: {min_bid_val:.4f} {currency}")
            lines.append("")
            lines.append("=" * 80)
            lines.append("")

        # Metric definitions
        lines.append("METRIC DEFINITIONS:")
        lines.append("  - Unique Users: COUNT(DISTINCT user_id) globally (estimated from reach)")
        lines.append("  - Reach: COUNT(DISTINCT user_id) per ad per day, then summed")
        lines.append("  - Impressions: COUNT(*) - all views including repeats")
        lines.append("")
        lines.append("=" * 80)
        lines.append("")

        # Calculate metrics
        # Task 5.4: Use deduplicated simulation_results to prevent double-counting
        sim_results_for_totals = simulation_results.drop_duplicates(subset=['ad_id'])

        total_reach_actual = impressions_df['total_reach'].sum()
        total_reach_simulated = sim_results_for_totals['simulated_reach'].sum()
        raw_impressions_actual = impressions_df['raw_impressions'].sum()

        # Estimate unique users (reach / avg combinations per user)
        # Using ~68 as average from observed data
        estimated_unique_users = int(total_reach_actual / 68)

        # Unique Users (estimated)
        lines.append(f"Unique Users (globally):")
        lines.append(f"  Estimated: ~{estimated_unique_users:,}")
        lines.append(f"  Formula: total_reach / 68 (avg combinations per user)")
        lines.append(f"  Note: Exact count requires tracking user_id list (not implemented)")
        lines.append("")

        # Total reach
        lines.append(f"Total Reach (user × ad × date combinations):")
        lines.append(f"  Actual:    {total_reach_actual:,}")
        lines.append(f"  Simulated: {total_reach_simulated:,}")
        diff_reach = total_reach_simulated - total_reach_actual
        lines.append(f"  Diff:      {diff_reach:,}")

        # Task 3.1 & 3.2: Conservation validation
        # With proper negative carry handling, simulated should match actual exactly
        # (within tolerance for edge cases in different aggregation methods)
        if abs(diff_reach) > 10:  # Tolerance for minor aggregation differences
            lines.append(f"  ⚠️  WARNING: Conservation drift detected (+{diff_reach} reach)")
            lines.append(f"      This may indicate a bug in organic fallback allocation.")
        elif abs(diff_reach) > 0:
            lines.append(f"  ℹ️  Note: Small diff (+{diff_reach}) within acceptable range")

        lines.append("")

        # Raw impressions
        lines.append(f"Raw Impressions (all views):")
        lines.append(f"  Actual:    {raw_impressions_actual:,}")
        lines.append(f"  Note: Simulation operates on reach, not raw impressions")
        lines.append("")

        # Metrics ratios
        impressions_per_reach = raw_impressions_actual / total_reach_actual if total_reach_actual > 0 else 0
        lines.append(f"Metrics Ratios:")
        lines.append(f"  Impressions per reach: {impressions_per_reach:.2f}x")
        lines.append(f"  Reach per unique user: ~68 (estimated)")
        lines.append("")

        # Paid vs Organic
        paid_reach_actual = (impressions_df['total_reach'] - impressions_df['organic_reach']).sum()
        organic_reach_actual = impressions_df['organic_reach'].sum()

        # For simulated, estimate based on spending
        paid_simulated = (simulation_results['simulated_spending'] > 0).sum()
        organic_simulated = total_reach_simulated - paid_simulated

        lines.append(f"Paid Reach:")
        lines.append(f"  Actual:    {paid_reach_actual:,} ({paid_reach_actual/total_reach_actual*100:.1f}%)")
        lines.append(f"  Simulated: ~estimate based on ads with spending")
        lines.append("")

        lines.append(f"Organic Reach:")
        lines.append(f"  Actual:    {organic_reach_actual:,} ({organic_reach_actual/total_reach_actual*100:.1f}%)")
        lines.append(f"  Simulated: ~remainder")
        lines.append("")

        # Total spending (convert to float to avoid Decimal type errors)
        spending_actual = float(budgets_df['actual_spend'].sum()) / 100  # to currency
        spending_simulated = float(sim_results_for_totals['simulated_spending'].sum()) / 100

        lines.append(f"Total Spending ({currency}):")
        lines.append(f"  Actual:    {spending_actual:,.2f}")
        lines.append(f"  Simulated: {spending_simulated:,.2f}")
        lines.append(f"  Diff:      {spending_simulated - spending_actual:,.2f}")
        lines.append("")

        # Budget utilization with active vs overall breakdown
        budget_total_all_paid = float(budgets_df['daily_budget'].sum()) / 100

        # Calculate active budget (only for ads that participated in simulation)
        # Get ads that were initialized in simulation (they have entries in simulation_results)
        active_ad_ids = set(simulation_results['ad_id'].unique())
        budget_total_active_paid = float(
            budgets_df[budgets_df['ad_id'].isin(active_ad_ids)]['daily_budget'].sum()
        ) / 100

        overall_budget_utilization = (spending_simulated / budget_total_all_paid * 100) if budget_total_all_paid > 0 else 0
        active_budget_utilization = (spending_simulated / budget_total_active_paid * 100) if budget_total_active_paid > 0 else 0

        lines.append(f"Budget Utilization:")
        lines.append(f"  Total Budget (All Paid):   {budget_total_all_paid:,.2f} {currency}")
        lines.append(f"  Total Budget (Active):     {budget_total_active_paid:,.2f} {currency}")
        lines.append(f"  Excluded Budget:           {budget_total_all_paid - budget_total_active_paid:,.2f} {currency}")
        lines.append(f"  ")
        lines.append(f"  Actual Spend:              {spending_actual:,.2f} {currency}")
        lines.append(f"  Simulated Spend:           {spending_simulated:,.2f} {currency}")
        lines.append(f"  ")
        lines.append(f"  Overall Budget Utilization:  {overall_budget_utilization:.1f}%")
        lines.append(f"    (simulated / all paid budget)")
        lines.append(f"  Active Budget Utilization:   {active_budget_utilization:.1f}%")
        lines.append(f"    (simulated / active paid budget)")
        lines.append("")

        # Task 5.3: Create period-level paid flags (not last-day state)
        # An ad is "paid" if it had budget > 0 on ANY day in the period
        paid_ad_ids = set(budgets_df[budgets_df['daily_budget'] > 0]['ad_id'].unique())
        paid_seller_ids = set(budgets_df[budgets_df['daily_budget'] > 0]['seller_id'].unique())

        # Task 5.4: Deduplicate simulation_results by ad_id
        # (in case there are duplicates from outer merge in build process)
        sim_results_dedup = simulation_results.drop_duplicates(subset=['ad_id'])

        # Paid Coverage Analysis
        # Count total paid sellers/ads (those with budget in period)
        total_paid_sellers = len(paid_seller_ids)
        total_paid_ads = len(paid_ad_ids)

        # Count paid sellers/ads with simulated reach > 0 (using period-level flags)
        paid_ads_with_reach_df = sim_results_dedup[
            (sim_results_dedup['ad_id'].isin(paid_ad_ids)) &
            (sim_results_dedup['simulated_reach'] > 0)
        ]
        paid_sellers_with_reach = paid_ads_with_reach_df['seller_id'].nunique()
        paid_ads_with_reach = paid_ads_with_reach_df['ad_id'].nunique()

        seller_coverage = (paid_sellers_with_reach / total_paid_sellers * 100) if total_paid_sellers > 0 else 0
        ad_coverage = (paid_ads_with_reach / total_paid_ads * 100) if total_paid_ads > 0 else 0

        lines.append(f"Paid Coverage Analysis:")
        lines.append(f"  Paid Sellers:")
        lines.append(f"    Total:          {total_paid_sellers}")
        lines.append(f"    With Reach:     {paid_sellers_with_reach}")
        lines.append(f"    Coverage:       {seller_coverage:.1f}%")
        lines.append(f"  ")
        lines.append(f"  Paid Ads:")
        lines.append(f"    Total:          {total_paid_ads}")
        lines.append(f"    With Reach:     {paid_ads_with_reach}")
        lines.append(f"    Coverage:       {ad_coverage:.1f}%")
        lines.append("")

        # Free (Organic) Coverage Analysis (using period-level flags)
        # Free = ads that were NOT paid during the period
        free_ads_with_reach_df = sim_results_dedup[
            (~sim_results_dedup['ad_id'].isin(paid_ad_ids)) &
            (sim_results_dedup['simulated_reach'] > 0)
        ]

        # Total free = all ads in simulation minus paid ads
        total_free_ads = len(sim_results_dedup) - len(paid_ad_ids)
        total_free_sellers = sim_results_dedup[~sim_results_dedup['seller_id'].isin(paid_seller_ids)]['seller_id'].nunique()

        free_ads_with_reach = free_ads_with_reach_df['ad_id'].nunique()
        free_sellers_with_reach = free_ads_with_reach_df['seller_id'].nunique()

        free_seller_coverage = (free_sellers_with_reach / total_free_sellers * 100) if total_free_sellers > 0 else 0
        free_ad_coverage = (free_ads_with_reach / total_free_ads * 100) if total_free_ads > 0 else 0

        lines.append(f"Free (Organic) Coverage Analysis:")
        lines.append(f"  Free Sellers:")
        lines.append(f"    Total:          {total_free_sellers}")
        lines.append(f"    With Reach:     {free_sellers_with_reach}")
        lines.append(f"    Coverage:       {free_seller_coverage:.1f}%")
        lines.append(f"  ")
        lines.append(f"  Free Ads:")
        lines.append(f"    Total:          {total_free_ads}")
        lines.append(f"    With Reach:     {free_ads_with_reach}")
        lines.append(f"    Coverage:       {free_ad_coverage:.1f}%")
        lines.append("")

        # Reach Performance Distribution
        # Compare simulated vs actual reach for paid and free ads
        # Filter only ads that had actual reach (to avoid division issues)
        ads_with_actual_reach = ad_comparison[ad_comparison['actual_reach_total'] > 0].copy()

        # Paid ads performance
        paid_ads_perf = ads_with_actual_reach[ads_with_actual_reach['is_paid_actual'] == True].copy()
        paid_ads_improved_mask = paid_ads_perf['simulated_reach_total'] >= paid_ads_perf['actual_reach_total']
        paid_ads_decreased_mask = paid_ads_perf['simulated_reach_total'] < paid_ads_perf['actual_reach_total']

        paid_ads_improved_or_same = paid_ads_improved_mask.sum()
        paid_ads_decreased = paid_ads_decreased_mask.sum()
        total_paid_ads_perf = len(paid_ads_perf)

        paid_improved_pct = (paid_ads_improved_or_same / total_paid_ads_perf * 100) if total_paid_ads_perf > 0 else 0
        paid_decreased_pct = (paid_ads_decreased / total_paid_ads_perf * 100) if total_paid_ads_perf > 0 else 0

        # Calculate statistics for paid ads improved
        if paid_ads_improved_or_same > 0:
            paid_ads_improved_sim_avg = paid_ads_perf.loc[paid_ads_improved_mask, 'simulated_reach_total'].mean()
            paid_ads_improved_sim_median = paid_ads_perf.loc[paid_ads_improved_mask, 'simulated_reach_total'].median()
            # Bottom 5% average instead of min
            n_bottom = max(1, int(paid_ads_improved_or_same * 0.05))
            paid_ads_improved_sim_bottom5 = paid_ads_perf.loc[paid_ads_improved_mask, 'simulated_reach_total'].nsmallest(n_bottom).mean()

            paid_ads_improved_act_avg = paid_ads_perf.loc[paid_ads_improved_mask, 'actual_reach_total'].mean()
            paid_ads_improved_act_median = paid_ads_perf.loc[paid_ads_improved_mask, 'actual_reach_total'].median()
            paid_ads_improved_act_bottom5 = paid_ads_perf.loc[paid_ads_improved_mask, 'actual_reach_total'].nsmallest(n_bottom).mean()

            paid_ads_improved_avg_pct = ((paid_ads_improved_sim_avg - paid_ads_improved_act_avg) / paid_ads_improved_act_avg * 100) if paid_ads_improved_act_avg > 0 else 0
            paid_ads_improved_median_pct = ((paid_ads_improved_sim_median - paid_ads_improved_act_median) / paid_ads_improved_act_median * 100) if paid_ads_improved_act_median > 0 else 0
            paid_ads_improved_bottom5_pct = ((paid_ads_improved_sim_bottom5 - paid_ads_improved_act_bottom5) / paid_ads_improved_act_bottom5 * 100) if paid_ads_improved_act_bottom5 > 0 else 0
        else:
            paid_ads_improved_sim_avg = paid_ads_improved_sim_median = paid_ads_improved_sim_bottom5 = 0
            paid_ads_improved_act_avg = paid_ads_improved_act_median = paid_ads_improved_act_bottom5 = 0
            paid_ads_improved_avg_pct = paid_ads_improved_median_pct = paid_ads_improved_bottom5_pct = 0

        # Calculate statistics for paid ads decreased
        if paid_ads_decreased > 0:
            paid_ads_decreased_sim_avg = paid_ads_perf.loc[paid_ads_decreased_mask, 'simulated_reach_total'].mean()
            paid_ads_decreased_sim_median = paid_ads_perf.loc[paid_ads_decreased_mask, 'simulated_reach_total'].median()
            # Bottom 5% average instead of min
            n_bottom = max(1, int(paid_ads_decreased * 0.05))
            paid_ads_decreased_sim_bottom5 = paid_ads_perf.loc[paid_ads_decreased_mask, 'simulated_reach_total'].nsmallest(n_bottom).mean()

            paid_ads_decreased_act_avg = paid_ads_perf.loc[paid_ads_decreased_mask, 'actual_reach_total'].mean()
            paid_ads_decreased_act_median = paid_ads_perf.loc[paid_ads_decreased_mask, 'actual_reach_total'].median()
            paid_ads_decreased_act_bottom5 = paid_ads_perf.loc[paid_ads_decreased_mask, 'actual_reach_total'].nsmallest(n_bottom).mean()

            paid_ads_decreased_avg_pct = ((paid_ads_decreased_sim_avg - paid_ads_decreased_act_avg) / paid_ads_decreased_act_avg * 100) if paid_ads_decreased_act_avg > 0 else 0
            paid_ads_decreased_median_pct = ((paid_ads_decreased_sim_median - paid_ads_decreased_act_median) / paid_ads_decreased_act_median * 100) if paid_ads_decreased_act_median > 0 else 0
            paid_ads_decreased_bottom5_pct = ((paid_ads_decreased_sim_bottom5 - paid_ads_decreased_act_bottom5) / paid_ads_decreased_act_bottom5 * 100) if paid_ads_decreased_act_bottom5 > 0 else 0
        else:
            paid_ads_decreased_sim_avg = paid_ads_decreased_sim_median = paid_ads_decreased_sim_bottom5 = 0
            paid_ads_decreased_act_avg = paid_ads_decreased_act_median = paid_ads_decreased_act_bottom5 = 0
            paid_ads_decreased_avg_pct = paid_ads_decreased_median_pct = paid_ads_decreased_bottom5_pct = 0

        # Free ads performance
        free_ads_perf = ads_with_actual_reach[ads_with_actual_reach['is_paid_actual'] == False].copy()
        free_ads_improved_mask = free_ads_perf['simulated_reach_total'] >= free_ads_perf['actual_reach_total']
        free_ads_decreased_mask = free_ads_perf['simulated_reach_total'] < free_ads_perf['actual_reach_total']

        free_ads_improved_or_same = free_ads_improved_mask.sum()
        free_ads_decreased = free_ads_decreased_mask.sum()
        total_free_ads_perf = len(free_ads_perf)

        free_improved_pct = (free_ads_improved_or_same / total_free_ads_perf * 100) if total_free_ads_perf > 0 else 0
        free_decreased_pct = (free_ads_decreased / total_free_ads_perf * 100) if total_free_ads_perf > 0 else 0

        # Calculate statistics for free ads improved
        if free_ads_improved_or_same > 0:
            free_ads_improved_sim_avg = free_ads_perf.loc[free_ads_improved_mask, 'simulated_reach_total'].mean()
            free_ads_improved_sim_median = free_ads_perf.loc[free_ads_improved_mask, 'simulated_reach_total'].median()
            # Bottom 5% average instead of min
            n_bottom = max(1, int(free_ads_improved_or_same * 0.05))
            free_ads_improved_sim_bottom5 = free_ads_perf.loc[free_ads_improved_mask, 'simulated_reach_total'].nsmallest(n_bottom).mean()

            free_ads_improved_act_avg = free_ads_perf.loc[free_ads_improved_mask, 'actual_reach_total'].mean()
            free_ads_improved_act_median = free_ads_perf.loc[free_ads_improved_mask, 'actual_reach_total'].median()
            free_ads_improved_act_bottom5 = free_ads_perf.loc[free_ads_improved_mask, 'actual_reach_total'].nsmallest(n_bottom).mean()

            free_ads_improved_avg_pct = ((free_ads_improved_sim_avg - free_ads_improved_act_avg) / free_ads_improved_act_avg * 100) if free_ads_improved_act_avg > 0 else 0
            free_ads_improved_median_pct = ((free_ads_improved_sim_median - free_ads_improved_act_median) / free_ads_improved_act_median * 100) if free_ads_improved_act_median > 0 else 0
            free_ads_improved_bottom5_pct = ((free_ads_improved_sim_bottom5 - free_ads_improved_act_bottom5) / free_ads_improved_act_bottom5 * 100) if free_ads_improved_act_bottom5 > 0 else 0
        else:
            free_ads_improved_sim_avg = free_ads_improved_sim_median = free_ads_improved_sim_bottom5 = 0
            free_ads_improved_act_avg = free_ads_improved_act_median = free_ads_improved_act_bottom5 = 0
            free_ads_improved_avg_pct = free_ads_improved_median_pct = free_ads_improved_bottom5_pct = 0

        # Calculate statistics for free ads decreased
        if free_ads_decreased > 0:
            free_ads_decreased_sim_avg = free_ads_perf.loc[free_ads_decreased_mask, 'simulated_reach_total'].mean()
            free_ads_decreased_sim_median = free_ads_perf.loc[free_ads_decreased_mask, 'simulated_reach_total'].median()
            # Bottom 5% average instead of min
            n_bottom = max(1, int(free_ads_decreased * 0.05))
            free_ads_decreased_sim_bottom5 = free_ads_perf.loc[free_ads_decreased_mask, 'simulated_reach_total'].nsmallest(n_bottom).mean()

            free_ads_decreased_act_avg = free_ads_perf.loc[free_ads_decreased_mask, 'actual_reach_total'].mean()
            free_ads_decreased_act_median = free_ads_perf.loc[free_ads_decreased_mask, 'actual_reach_total'].median()
            free_ads_decreased_act_bottom5 = free_ads_perf.loc[free_ads_decreased_mask, 'actual_reach_total'].nsmallest(n_bottom).mean()

            free_ads_decreased_avg_pct = ((free_ads_decreased_sim_avg - free_ads_decreased_act_avg) / free_ads_decreased_act_avg * 100) if free_ads_decreased_act_avg > 0 else 0
            free_ads_decreased_median_pct = ((free_ads_decreased_sim_median - free_ads_decreased_act_median) / free_ads_decreased_act_median * 100) if free_ads_decreased_act_median > 0 else 0
            free_ads_decreased_bottom5_pct = ((free_ads_decreased_sim_bottom5 - free_ads_decreased_act_bottom5) / free_ads_decreased_act_bottom5 * 100) if free_ads_decreased_act_bottom5 > 0 else 0
        else:
            free_ads_decreased_sim_avg = free_ads_decreased_sim_median = free_ads_decreased_sim_bottom5 = 0
            free_ads_decreased_act_avg = free_ads_decreased_act_median = free_ads_decreased_act_bottom5 = 0
            free_ads_decreased_avg_pct = free_ads_decreased_median_pct = free_ads_decreased_bottom5_pct = 0

        # Sellers performance analysis
        sellers_with_actual_reach = seller_comparison[seller_comparison['actual_reach_total'] > 0].copy()

        # Paid sellers performance
        paid_sellers_perf = sellers_with_actual_reach[sellers_with_actual_reach['is_paid_actual'] == True].copy()
        paid_sellers_improved_mask = paid_sellers_perf['simulated_reach_total'] >= paid_sellers_perf['actual_reach_total']
        paid_sellers_decreased_mask = paid_sellers_perf['simulated_reach_total'] < paid_sellers_perf['actual_reach_total']

        paid_sellers_improved_or_same = paid_sellers_improved_mask.sum()
        paid_sellers_decreased = paid_sellers_decreased_mask.sum()
        total_paid_sellers_perf = len(paid_sellers_perf)

        paid_sellers_improved_pct = (paid_sellers_improved_or_same / total_paid_sellers_perf * 100) if total_paid_sellers_perf > 0 else 0
        paid_sellers_decreased_pct = (paid_sellers_decreased / total_paid_sellers_perf * 100) if total_paid_sellers_perf > 0 else 0

        # Calculate statistics for paid sellers improved
        if paid_sellers_improved_or_same > 0:
            paid_sellers_improved_sim_avg = paid_sellers_perf.loc[paid_sellers_improved_mask, 'simulated_reach_total'].mean()
            paid_sellers_improved_sim_median = paid_sellers_perf.loc[paid_sellers_improved_mask, 'simulated_reach_total'].median()
            # Bottom 5% average instead of min
            n_bottom = max(1, int(paid_sellers_improved_or_same * 0.05))
            paid_sellers_improved_sim_bottom5 = paid_sellers_perf.loc[paid_sellers_improved_mask, 'simulated_reach_total'].nsmallest(n_bottom).mean()

            paid_sellers_improved_act_avg = paid_sellers_perf.loc[paid_sellers_improved_mask, 'actual_reach_total'].mean()
            paid_sellers_improved_act_median = paid_sellers_perf.loc[paid_sellers_improved_mask, 'actual_reach_total'].median()
            paid_sellers_improved_act_bottom5 = paid_sellers_perf.loc[paid_sellers_improved_mask, 'actual_reach_total'].nsmallest(n_bottom).mean()

            paid_sellers_improved_avg_pct = ((paid_sellers_improved_sim_avg - paid_sellers_improved_act_avg) / paid_sellers_improved_act_avg * 100) if paid_sellers_improved_act_avg > 0 else 0
            paid_sellers_improved_median_pct = ((paid_sellers_improved_sim_median - paid_sellers_improved_act_median) / paid_sellers_improved_act_median * 100) if paid_sellers_improved_act_median > 0 else 0
            paid_sellers_improved_bottom5_pct = ((paid_sellers_improved_sim_bottom5 - paid_sellers_improved_act_bottom5) / paid_sellers_improved_act_bottom5 * 100) if paid_sellers_improved_act_bottom5 > 0 else 0
        else:
            paid_sellers_improved_sim_avg = paid_sellers_improved_sim_median = paid_sellers_improved_sim_bottom5 = 0
            paid_sellers_improved_act_avg = paid_sellers_improved_act_median = paid_sellers_improved_act_bottom5 = 0
            paid_sellers_improved_avg_pct = paid_sellers_improved_median_pct = paid_sellers_improved_bottom5_pct = 0

        # Calculate statistics for paid sellers decreased
        if paid_sellers_decreased > 0:
            paid_sellers_decreased_sim_avg = paid_sellers_perf.loc[paid_sellers_decreased_mask, 'simulated_reach_total'].mean()
            paid_sellers_decreased_sim_median = paid_sellers_perf.loc[paid_sellers_decreased_mask, 'simulated_reach_total'].median()
            # Bottom 5% average instead of min
            n_bottom = max(1, int(paid_sellers_decreased * 0.05))
            paid_sellers_decreased_sim_bottom5 = paid_sellers_perf.loc[paid_sellers_decreased_mask, 'simulated_reach_total'].nsmallest(n_bottom).mean()

            paid_sellers_decreased_act_avg = paid_sellers_perf.loc[paid_sellers_decreased_mask, 'actual_reach_total'].mean()
            paid_sellers_decreased_act_median = paid_sellers_perf.loc[paid_sellers_decreased_mask, 'actual_reach_total'].median()
            paid_sellers_decreased_act_bottom5 = paid_sellers_perf.loc[paid_sellers_decreased_mask, 'actual_reach_total'].nsmallest(n_bottom).mean()

            paid_sellers_decreased_avg_pct = ((paid_sellers_decreased_sim_avg - paid_sellers_decreased_act_avg) / paid_sellers_decreased_act_avg * 100) if paid_sellers_decreased_act_avg > 0 else 0
            paid_sellers_decreased_median_pct = ((paid_sellers_decreased_sim_median - paid_sellers_decreased_act_median) / paid_sellers_decreased_act_median * 100) if paid_sellers_decreased_act_median > 0 else 0
            paid_sellers_decreased_bottom5_pct = ((paid_sellers_decreased_sim_bottom5 - paid_sellers_decreased_act_bottom5) / paid_sellers_decreased_act_bottom5 * 100) if paid_sellers_decreased_act_bottom5 > 0 else 0
        else:
            paid_sellers_decreased_sim_avg = paid_sellers_decreased_sim_median = paid_sellers_decreased_sim_bottom5 = 0
            paid_sellers_decreased_act_avg = paid_sellers_decreased_act_median = paid_sellers_decreased_act_bottom5 = 0
            paid_sellers_decreased_avg_pct = paid_sellers_decreased_median_pct = paid_sellers_decreased_bottom5_pct = 0

        # Free sellers performance
        free_sellers_perf = sellers_with_actual_reach[sellers_with_actual_reach['is_paid_actual'] == False].copy()
        free_sellers_improved_mask = free_sellers_perf['simulated_reach_total'] >= free_sellers_perf['actual_reach_total']
        free_sellers_decreased_mask = free_sellers_perf['simulated_reach_total'] < free_sellers_perf['actual_reach_total']

        free_sellers_improved_or_same = free_sellers_improved_mask.sum()
        free_sellers_decreased = free_sellers_decreased_mask.sum()
        total_free_sellers_perf = len(free_sellers_perf)

        free_sellers_improved_pct = (free_sellers_improved_or_same / total_free_sellers_perf * 100) if total_free_sellers_perf > 0 else 0
        free_sellers_decreased_pct = (free_sellers_decreased / total_free_sellers_perf * 100) if total_free_sellers_perf > 0 else 0

        # Calculate statistics for free sellers improved
        if free_sellers_improved_or_same > 0:
            free_sellers_improved_sim_avg = free_sellers_perf.loc[free_sellers_improved_mask, 'simulated_reach_total'].mean()
            free_sellers_improved_sim_median = free_sellers_perf.loc[free_sellers_improved_mask, 'simulated_reach_total'].median()
            # Bottom 5% average instead of min
            n_bottom = max(1, int(free_sellers_improved_or_same * 0.05))
            free_sellers_improved_sim_bottom5 = free_sellers_perf.loc[free_sellers_improved_mask, 'simulated_reach_total'].nsmallest(n_bottom).mean()

            free_sellers_improved_act_avg = free_sellers_perf.loc[free_sellers_improved_mask, 'actual_reach_total'].mean()
            free_sellers_improved_act_median = free_sellers_perf.loc[free_sellers_improved_mask, 'actual_reach_total'].median()
            free_sellers_improved_act_bottom5 = free_sellers_perf.loc[free_sellers_improved_mask, 'actual_reach_total'].nsmallest(n_bottom).mean()

            free_sellers_improved_avg_pct = ((free_sellers_improved_sim_avg - free_sellers_improved_act_avg) / free_sellers_improved_act_avg * 100) if free_sellers_improved_act_avg > 0 else 0
            free_sellers_improved_median_pct = ((free_sellers_improved_sim_median - free_sellers_improved_act_median) / free_sellers_improved_act_median * 100) if free_sellers_improved_act_median > 0 else 0
            free_sellers_improved_bottom5_pct = ((free_sellers_improved_sim_bottom5 - free_sellers_improved_act_bottom5) / free_sellers_improved_act_bottom5 * 100) if free_sellers_improved_act_bottom5 > 0 else 0
        else:
            free_sellers_improved_sim_avg = free_sellers_improved_sim_median = free_sellers_improved_sim_bottom5 = 0
            free_sellers_improved_act_avg = free_sellers_improved_act_median = free_sellers_improved_act_bottom5 = 0
            free_sellers_improved_avg_pct = free_sellers_improved_median_pct = free_sellers_improved_bottom5_pct = 0

        # Calculate statistics for free sellers decreased
        if free_sellers_decreased > 0:
            free_sellers_decreased_sim_avg = free_sellers_perf.loc[free_sellers_decreased_mask, 'simulated_reach_total'].mean()
            free_sellers_decreased_sim_median = free_sellers_perf.loc[free_sellers_decreased_mask, 'simulated_reach_total'].median()
            # Bottom 5% average instead of min
            n_bottom = max(1, int(free_sellers_decreased * 0.05))
            free_sellers_decreased_sim_bottom5 = free_sellers_perf.loc[free_sellers_decreased_mask, 'simulated_reach_total'].nsmallest(n_bottom).mean()

            free_sellers_decreased_act_avg = free_sellers_perf.loc[free_sellers_decreased_mask, 'actual_reach_total'].mean()
            free_sellers_decreased_act_median = free_sellers_perf.loc[free_sellers_decreased_mask, 'actual_reach_total'].median()
            free_sellers_decreased_act_bottom5 = free_sellers_perf.loc[free_sellers_decreased_mask, 'actual_reach_total'].nsmallest(n_bottom).mean()

            free_sellers_decreased_avg_pct = ((free_sellers_decreased_sim_avg - free_sellers_decreased_act_avg) / free_sellers_decreased_act_avg * 100) if free_sellers_decreased_act_avg > 0 else 0
            free_sellers_decreased_median_pct = ((free_sellers_decreased_sim_median - free_sellers_decreased_act_median) / free_sellers_decreased_act_median * 100) if free_sellers_decreased_act_median > 0 else 0
            free_sellers_decreased_bottom5_pct = ((free_sellers_decreased_sim_bottom5 - free_sellers_decreased_act_bottom5) / free_sellers_decreased_act_bottom5 * 100) if free_sellers_decreased_act_bottom5 > 0 else 0
        else:
            free_sellers_decreased_sim_avg = free_sellers_decreased_sim_median = free_sellers_decreased_sim_bottom5 = 0
            free_sellers_decreased_act_avg = free_sellers_decreased_act_median = free_sellers_decreased_act_bottom5 = 0
            free_sellers_decreased_avg_pct = free_sellers_decreased_median_pct = free_sellers_decreased_bottom5_pct = 0

        lines.append(f"Reach Performance Distribution:")
        lines.append(f"  (comparing simulated vs actual reach for entities with historical data)")
        lines.append(f"  ")
        lines.append(f"  Paid Ads:")
        lines.append(f"    Total analyzed:              {total_paid_ads_perf}")
        lines.append(f"    Reach >= actual:             {paid_ads_improved_or_same} ({paid_improved_pct:.1f}%)")
        lines.append(f"      Average reach:             {paid_ads_improved_sim_avg:.1f} (vs {paid_ads_improved_act_avg:.1f}, {paid_ads_improved_avg_pct:+.1f}%)")
        lines.append(f"      Median reach:              {paid_ads_improved_sim_median:.1f} (vs {paid_ads_improved_act_median:.1f}, {paid_ads_improved_median_pct:+.1f}%)")
        lines.append(f"      Bottom 5% avg:             {paid_ads_improved_sim_bottom5:.1f} (vs {paid_ads_improved_act_bottom5:.1f}, {paid_ads_improved_bottom5_pct:+.1f}%)")
        lines.append(f"    Reach < actual:              {paid_ads_decreased} ({paid_decreased_pct:.1f}%)")
        lines.append(f"      Average reach:             {paid_ads_decreased_sim_avg:.1f} (vs {paid_ads_decreased_act_avg:.1f}, {paid_ads_decreased_avg_pct:+.1f}%)")
        lines.append(f"      Median reach:              {paid_ads_decreased_sim_median:.1f} (vs {paid_ads_decreased_act_median:.1f}, {paid_ads_decreased_median_pct:+.1f}%)")
        lines.append(f"      Bottom 5% avg:                 {paid_ads_decreased_sim_bottom5:.1f} (vs {paid_ads_decreased_act_bottom5:.1f}, {paid_ads_decreased_bottom5_pct:+.1f}%)")
        lines.append(f"  ")
        lines.append(f"  Free Ads:")
        lines.append(f"    Total analyzed:              {total_free_ads_perf}")
        lines.append(f"    Reach >= actual:             {free_ads_improved_or_same} ({free_improved_pct:.1f}%)")
        lines.append(f"      Average reach:             {free_ads_improved_sim_avg:.1f} (vs {free_ads_improved_act_avg:.1f}, {free_ads_improved_avg_pct:+.1f}%)")
        lines.append(f"      Median reach:              {free_ads_improved_sim_median:.1f} (vs {free_ads_improved_act_median:.1f}, {free_ads_improved_median_pct:+.1f}%)")
        lines.append(f"      Bottom 5% avg:                 {free_ads_improved_sim_bottom5:.1f} (vs {free_ads_improved_act_bottom5:.1f}, {free_ads_improved_bottom5_pct:+.1f}%)")
        lines.append(f"    Reach < actual:              {free_ads_decreased} ({free_decreased_pct:.1f}%)")
        lines.append(f"      Average reach:             {free_ads_decreased_sim_avg:.1f} (vs {free_ads_decreased_act_avg:.1f}, {free_ads_decreased_avg_pct:+.1f}%)")
        lines.append(f"      Median reach:              {free_ads_decreased_sim_median:.1f} (vs {free_ads_decreased_act_median:.1f}, {free_ads_decreased_median_pct:+.1f}%)")
        lines.append(f"      Bottom 5% avg:                 {free_ads_decreased_sim_bottom5:.1f} (vs {free_ads_decreased_act_bottom5:.1f}, {free_ads_decreased_bottom5_pct:+.1f}%)")
        lines.append(f"  ")
        lines.append(f"  Paid Sellers:")
        lines.append(f"    Total analyzed:              {total_paid_sellers_perf}")
        lines.append(f"    Reach >= actual:             {paid_sellers_improved_or_same} ({paid_sellers_improved_pct:.1f}%)")
        lines.append(f"      Average reach:             {paid_sellers_improved_sim_avg:.1f} (vs {paid_sellers_improved_act_avg:.1f}, {paid_sellers_improved_avg_pct:+.1f}%)")
        lines.append(f"      Median reach:              {paid_sellers_improved_sim_median:.1f} (vs {paid_sellers_improved_act_median:.1f}, {paid_sellers_improved_median_pct:+.1f}%)")
        lines.append(f"      Bottom 5% avg:                 {paid_sellers_improved_sim_bottom5:.1f} (vs {paid_sellers_improved_act_bottom5:.1f}, {paid_sellers_improved_bottom5_pct:+.1f}%)")
        lines.append(f"    Reach < actual:              {paid_sellers_decreased} ({paid_sellers_decreased_pct:.1f}%)")
        lines.append(f"      Average reach:             {paid_sellers_decreased_sim_avg:.1f} (vs {paid_sellers_decreased_act_avg:.1f}, {paid_sellers_decreased_avg_pct:+.1f}%)")
        lines.append(f"      Median reach:              {paid_sellers_decreased_sim_median:.1f} (vs {paid_sellers_decreased_act_median:.1f}, {paid_sellers_decreased_median_pct:+.1f}%)")
        lines.append(f"      Bottom 5% avg:                 {paid_sellers_decreased_sim_bottom5:.1f} (vs {paid_sellers_decreased_act_bottom5:.1f}, {paid_sellers_decreased_bottom5_pct:+.1f}%)")
        lines.append(f"  ")
        lines.append(f"  Free Sellers:")
        lines.append(f"    Total analyzed:              {total_free_sellers_perf}")
        lines.append(f"    Reach >= actual:             {free_sellers_improved_or_same} ({free_sellers_improved_pct:.1f}%)")
        lines.append(f"      Average reach:             {free_sellers_improved_sim_avg:.1f} (vs {free_sellers_improved_act_avg:.1f}, {free_sellers_improved_avg_pct:+.1f}%)")
        lines.append(f"      Median reach:              {free_sellers_improved_sim_median:.1f} (vs {free_sellers_improved_act_median:.1f}, {free_sellers_improved_median_pct:+.1f}%)")
        lines.append(f"      Bottom 5% avg:                 {free_sellers_improved_sim_bottom5:.1f} (vs {free_sellers_improved_act_bottom5:.1f}, {free_sellers_improved_bottom5_pct:+.1f}%)")
        lines.append(f"    Reach < actual:              {free_sellers_decreased} ({free_sellers_decreased_pct:.1f}%)")
        lines.append(f"      Average reach:             {free_sellers_decreased_sim_avg:.1f} (vs {free_sellers_decreased_act_avg:.1f}, {free_sellers_decreased_avg_pct:+.1f}%)")
        lines.append(f"      Median reach:              {free_sellers_decreased_sim_median:.1f} (vs {free_sellers_decreased_act_median:.1f}, {free_sellers_decreased_median_pct:+.1f}%)")
        lines.append(f"      Bottom 5% avg:                 {free_sellers_decreased_sim_bottom5:.1f} (vs {free_sellers_decreased_act_bottom5:.1f}, {free_sellers_decreased_bottom5_pct:+.1f}%)")
        lines.append("")

        # Seller counts with paid/free breakdown (period-level classification)
        sellers_with_impressions_actual = seller_comparison[seller_comparison['actual_reach_total'] > 0].shape[0]
        sellers_paid_actual = seller_comparison[
            (seller_comparison['actual_reach_total'] > 0) &
            (seller_comparison['is_paid_actual'] == True)
        ].shape[0]
        sellers_free_actual = sellers_with_impressions_actual - sellers_paid_actual

        sellers_with_impressions_simulated = sim_results_dedup[sim_results_dedup['simulated_reach'] > 0]['seller_id'].nunique()
        sellers_paid_simulated = sim_results_dedup[
            (sim_results_dedup['simulated_reach'] > 0) &
            (sim_results_dedup['seller_id'].isin(paid_seller_ids))
        ]['seller_id'].nunique()
        sellers_free_simulated = sellers_with_impressions_simulated - sellers_paid_simulated

        lines.append(f"Sellers with Reach:")
        lines.append(f"  Actual:              {sellers_with_impressions_actual}")
        lines.append(f"    Paid sellers:      {sellers_paid_actual}")
        lines.append(f"    Free sellers:      {sellers_free_actual}")
        lines.append(f"  Simulated:           {sellers_with_impressions_simulated}")
        lines.append(f"    Paid sellers:      {sellers_paid_simulated}")
        lines.append(f"    Free sellers:      {sellers_free_simulated}")
        lines.append("")

        # Ad counts with paid/free breakdown (period-level classification)
        ads_with_impressions_actual = ad_comparison[ad_comparison['actual_reach_total'] > 0].shape[0]
        ads_paid_actual = ad_comparison[
            (ad_comparison['actual_reach_total'] > 0) &
            (ad_comparison['is_paid_actual'] == True)
        ].shape[0]
        ads_free_actual = ads_with_impressions_actual - ads_paid_actual

        ads_with_impressions_simulated = sim_results_dedup[sim_results_dedup['simulated_reach'] > 0].shape[0]
        ads_paid_simulated = sim_results_dedup[
            (sim_results_dedup['simulated_reach'] > 0) &
            (sim_results_dedup['ad_id'].isin(paid_ad_ids))
        ].shape[0]
        ads_free_simulated = ads_with_impressions_simulated - ads_paid_simulated

        lines.append(f"Ads with Reach:")
        lines.append(f"  Actual:              {ads_with_impressions_actual}")
        lines.append(f"    Paid ads:          {ads_paid_actual}")
        lines.append(f"    Free ads:          {ads_free_actual}")
        lines.append(f"  Simulated:           {ads_with_impressions_simulated}")
        lines.append(f"    Paid ads:          {ads_paid_simulated}")
        lines.append(f"    Free ads:          {ads_free_simulated}")
        lines.append("")

        # Reach distribution analysis (period-level classification)
        # Calculate total reach for paid vs free ads
        paid_reach_actual = ad_comparison['actual_reach_paid'].sum()
        free_reach_actual = ad_comparison['actual_reach_organic'].sum()

        paid_reach_simulated = sim_results_dedup[
            sim_results_dedup['ad_id'].isin(paid_ad_ids)
        ]['simulated_reach'].sum()
        free_reach_simulated = sim_results_dedup[
            ~sim_results_dedup['ad_id'].isin(paid_ad_ids)
        ]['simulated_reach'].sum()

        # Calculate changes
        paid_reach_change = paid_reach_simulated - paid_reach_actual
        paid_reach_change_pct = (paid_reach_change / paid_reach_actual * 100) if paid_reach_actual > 0 else 0

        free_reach_change = free_reach_simulated - free_reach_actual
        free_reach_change_pct = (free_reach_change / free_reach_actual * 100) if free_reach_actual > 0 else 0

        lines.append(f"Reach Distribution Analysis:")
        lines.append(f"  Paid Reach:")
        lines.append(f"    Actual:    {paid_reach_actual:,}")
        lines.append(f"    Simulated: {paid_reach_simulated:,}")
        lines.append(f"    Change:    {paid_reach_change:+,} ({paid_reach_change_pct:+.1f}%)")
        lines.append(f"  Organic Reach:")
        lines.append(f"    Actual:    {free_reach_actual:,}")
        lines.append(f"    Simulated: {free_reach_simulated:,}")
        lines.append(f"    Change:    {free_reach_change:+,} ({free_reach_change_pct:+.1f}%)")
        lines.append("")

        # Summary conclusion
        if abs(paid_reach_change_pct) > 5 or abs(free_reach_change_pct) > 5:
            lines.append(f"Conclusion:")
            if paid_reach_change > 0:
                lines.append(f"  Simulation INCREASED paid reach by {abs(paid_reach_change):,} ({abs(paid_reach_change_pct):.1f}%)")
            elif paid_reach_change < 0:
                lines.append(f"  Simulation DECREASED paid reach by {abs(paid_reach_change):,} ({abs(paid_reach_change_pct):.1f}%)")

            if free_reach_change > 0:
                lines.append(f"  Simulation INCREASED organic reach by {abs(free_reach_change):,} ({abs(free_reach_change_pct):.1f}%)")
            elif free_reach_change < 0:
                lines.append(f"  Simulation DECREASED organic reach by {abs(free_reach_change):,} ({abs(free_reach_change_pct):.1f}%)")
            lines.append("")

        # Per-Ad Reach Statistics
        lines.append(f"Reach per Ad Statistics:")
        lines.append(f"  Paid Ads (Actual):")
        paid_ads_actual = ad_comparison[ad_comparison['is_paid_actual'] == True]
        if len(paid_ads_actual) > 0:
            mean_paid_actual = paid_ads_actual['actual_reach_total'].mean()
            median_paid_actual = paid_ads_actual['actual_reach_total'].median()
            lines.append(f"    Mean:   {mean_paid_actual:,.1f} reach/ad")
            lines.append(f"    Median: {median_paid_actual:,.1f} reach/ad")
        else:
            lines.append(f"    No paid ads")

        lines.append(f"  Paid Ads (Simulated):")
        paid_ads_simulated = ad_comparison[
            (ad_comparison['is_paid_actual'] == True) &
            (ad_comparison['simulated_reach_total'] > 0)
        ]
        if len(paid_ads_simulated) > 0:
            mean_paid_simulated = paid_ads_simulated['simulated_reach_total'].mean()
            median_paid_simulated = paid_ads_simulated['simulated_reach_total'].median()
            lines.append(f"    Mean:   {mean_paid_simulated:,.1f} reach/ad")
            lines.append(f"    Median: {median_paid_simulated:,.1f} reach/ad")
        else:
            lines.append(f"    No paid ads")

        lines.append(f"  Organic Ads (Actual):")
        organic_ads_actual = ad_comparison[(ad_comparison['is_paid_actual'] == False) & (ad_comparison['actual_reach_total'] > 0)]
        if len(organic_ads_actual) > 0:
            mean_organic_actual = organic_ads_actual['actual_reach_total'].mean()
            median_organic_actual = organic_ads_actual['actual_reach_total'].median()
            lines.append(f"    Mean:   {mean_organic_actual:,.1f} reach/ad")
            lines.append(f"    Median: {median_organic_actual:,.1f} reach/ad")
        else:
            lines.append(f"    No organic ads with reach")

        lines.append(f"  Organic Ads (Simulated):")
        organic_ads_simulated = ad_comparison[
            (ad_comparison['is_paid_actual'] == False) &
            (ad_comparison['simulated_reach_total'] > 0)
        ]
        if len(organic_ads_simulated) > 0:
            mean_organic_simulated = organic_ads_simulated['simulated_reach_total'].mean()
            median_organic_simulated = organic_ads_simulated['simulated_reach_total'].median()
            lines.append(f"    Mean:   {mean_organic_simulated:,.1f} reach/ad")
            lines.append(f"    Median: {median_organic_simulated:,.1f} reach/ad")
        else:
            lines.append(f"    No organic ads with reach")
        lines.append("")

        # Task 4.2: Feedback pricing controller summary (change: add-feedback-price-multiplier-universal-pacing)
        # Note: This will be displayed even when disabled to show configuration status
        lines.append("Feedback Pricing Controller:")
        feedback_pricing_config = getattr(self.config.simulation, 'feedback_pricing', None)
        if feedback_pricing_config and getattr(feedback_pricing_config, 'enabled', False):
            lines.append(f"  Status: ENABLED")
            lines.append(f"  Kp: {getattr(feedback_pricing_config, 'Kp', 'N/A')}, Ki: {getattr(feedback_pricing_config, 'Ki', 'N/A')}")
            lines.append(f"  Multiplier range: {getattr(feedback_pricing_config, 'multiplier_min', 'N/A')} - {getattr(feedback_pricing_config, 'multiplier_max', 'N/A')}")
            lines.append(f"  Target curve: {getattr(getattr(feedback_pricing_config, 'target_curve', None), 'shape', 'N/A') if getattr(feedback_pricing_config, 'target_curve', None) else 'N/A'}")
            lines.append(f"  Note: Check simulation logs for per-category multiplier updates")
        else:
            lines.append(f"  Status: DISABLED (using static bid_step)")
        lines.append("")

        # Cascading win cap summary (change: add-cascading-win-cap-and-pacing)
        lines.append("Cascading Win Cap & Pacing Relaxation:")
        cascading_config = getattr(self.config.simulation, 'cascading_win_cap', None)
        if cascading_config and getattr(cascading_config, 'enabled', False):
            lines.append(f"  Status: ENABLED")

            # Win cap thresholds
            cap_thresholds = getattr(cascading_config, 'cap_thresholds', [])
            if cap_thresholds:
                lines.append(f"  Win cap thresholds:")
                for threshold in cap_thresholds:
                    # Handle both dict and object types
                    if isinstance(threshold, dict):
                        ratio = threshold.get('ratio', 1.0)
                        cap = threshold.get('cap', 1)
                    else:
                        ratio = getattr(threshold, 'ratio', 1.0)
                        cap = getattr(threshold, 'cap', 1)

                    lines.append(f"    - spend < {float(ratio)*100:.0f}% of target → cap = {cap}")

            max_cap = getattr(cascading_config, 'max_win_per_ad_cap', 'N/A')
            lines.append(f"  Max win per ad cap: {max_cap}")

            # Pacing relaxation
            pacing_relax = getattr(cascading_config, 'pacing_relaxation', None)
            if pacing_relax and getattr(pacing_relax, 'enabled', False):
                fallback_hours = getattr(pacing_relax, 'fallback_hours', 'N/A')
                tolerance_max = getattr(pacing_relax, 'tolerance_max', 'N/A')
                lines.append(f"  Pacing relaxation: ENABLED")
                lines.append(f"    - Triggers after {fallback_hours} consecutive under-spend hours")
                lines.append(f"    - Max tolerance: {tolerance_max}")
            else:
                lines.append(f"  Pacing relaxation: DISABLED")

            lines.append(f"  Note: Check simulation logs for cascade_evaluation events")
        else:
            lines.append(f"  Status: DISABLED (fixed win_per_ad_cap=1)")
        lines.append("")

        lines.append("=" * 80)

        return "\n".join(lines)

    def _save_csv_with_metadata(
        self,
        df: pd.DataFrame,
        file_path: Path,
        time_from,
        time_to,
        description: str
    ):
        """Save DataFrame to CSV with metadata header."""
        with open(file_path, 'w') as f:
            # Write metadata
            f.write(f"# {description}\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            f.write(f"# Time Range: {time_from} to {time_to}\n")
            f.write(f"# Records: {len(df)}\n")
            f.write("#\n")

            # Add column documentation for paid status flags
            if 'is_paid_actual' in df.columns:
                f.write("# Paid Status Columns:\n")
                if 'seller_id' in df.columns and 'ad_id' not in df.columns:
                    # Seller-level report
                    f.write("#   is_paid_actual: TRUE if seller had at least one paid campaign in actual data (daily_budget > 0)\n")
                    f.write("#   is_paid_simulated: TRUE if seller spent any budget in simulation (simulated_spending > 0)\n")
                else:
                    # Ad-level report
                    f.write("#   is_paid_actual: TRUE if ad had paid campaign in actual data (daily_budget > 0 on any day)\n")
                    f.write("#   is_paid_simulated: TRUE if ad spent any budget in simulation (simulated_spending > 0)\n")
                f.write("#\n")

            # Write CSV data
            df.to_csv(f, index=False)

        logger.info(f"Saved report: {file_path} ({len(df)} records)")

    def _save_summary(
        self,
        summary_text: str,
        file_path: Path,
        time_from,
        time_to
    ):
        """Save summary statistics to text file."""
        with open(file_path, 'w') as f:
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write(f"Time Range: {time_from} to {time_to}\n")
            f.write("\n")
            f.write(summary_text)

        logger.info(f"Saved summary: {file_path}")
