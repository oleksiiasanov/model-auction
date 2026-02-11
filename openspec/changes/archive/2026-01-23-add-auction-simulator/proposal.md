# Change: Add Auction-Based Traffic Distribution Simulator

## Why

Current ad distribution system has critical fairness and predictability issues:

**Problem 1**: PPV and Reach Profile compete with each other - PPV ads don't participate in Reach Profile logic, reducing value for sellers using both products

**Problem 2**: Reach depends on ad count - sellers with fewer ads cannot achieve good reach even with high budgets, unfair to small sellers

**Problem 3**: Budget doesn't guarantee priority - no clear "higher budget → more impressions" relationship, sellers don't understand ROI

**Problem 4**: Plan/fact reach calculations are complex, brittle, and hard to scale

**Problem 5**: Mass sellers have hidden advantage - 100 ads get more impressions than 5 ads even with equal budgets

We need to validate that an auction-based model (where sellers compete with algorithmic bids) can make the system fairer and more predictable before changing production.

## What Changes

**Add offline simulation system** to test auction-based traffic distribution:

- **Auction engine**: First-price auction with pressure-based ranking (higher urgency to spend = higher priority)
  - Pressure formula: `pressure = remaining_budget / time_left`
  - Effective bid: `min_bid + (N - 1 - rank_index) * bid_step`
  - Pacing gate to prevent budget dumping
  - All ads always eligible (no rotation constraints in MVP)
- **Data extraction**: Pull real impression data with configurable filters (country, categories, time range)
- **Comparison reporting**: Generate "was vs would be" comparison tables per seller and per ad

**Runtime Parameters**:
- `country`: integer (e.g., 13 for Azerbaijan)
- `categories`: list of integers (e.g., [1234, 5678])
- `time_from`: date (start of simulation period, full day only: YYYY-MM-DD)
- `time_to`: date (end of simulation period, full day only: YYYY-MM-DD)

**Scope limitations (MVP)**:
- Offline only (no production changes)
- Category feed only (no complex search filters)
- Uses real **total impression volumes** (paid + organic), redistributes them algorithmically
- Does NOT simulate UI, buyer behavior, or session-level uniqueness
- Ad-level auction (scope = ad_id, not user-level)

**Key principles**:
- We don't invent traffic. We redistribute real total impressions within selected filters.
- "All ads" means all ads that had impressions in the selected period/categories, not all ads in universe.
- Two definitions of "organic":
  - **Historical organic** (is_paid=false in ClickHouse): used for proportional fallback distribution
  - **Simulated organic** (budget=0 at auction time): ads compete with pressure=0
- Total impressions conserved. Paid/organic split changes based on which ads have budget when they win.
- Budget resets daily (from Campaign MS). Multi-day simulation supported.
- Preferred source: spendings_distributed for both spending and paid impression counts (schema-dependent, may require join with enriched_distributed)

## Impact

- **Affected specs**: None (new capabilities)
- **Affected systems**: None (offline simulation)
- **Data requirements**: Read-only access to ClickHouse (enriched_distributed, spendings_distributed)
- **Business value**: Validate fairness improvements before production investment
- **Risk**: Low (offline only, no user impact)
- **Known limitations**: Full days only (no partial days), hourly granularity, uses historical organic distribution for fallback, schema verification required for min_bid calculation (spendings_distributed must have impressions count or join with enriched_distributed)
- **Technical details**: Complete specs include formal algorithms for remainder distribution, JOIN deduplication logic, currency unit definitions (all values in kopecks), and rounding rules for budget deduction
