## 1. Implementation
- [x] 1.1 Add cascade configuration defaults (cap steps, max cap=4, fallback hours=2, pacing tolerance increment caps)
- [x] 1.2 Track per-category hourly under-spend streaks and compute `win_per_ad_cap`
- [x] 1.3 Apply `win_per_ad_cap` during winner selection in a batch
- [x] 1.4 If under-spend streak >= 2 hours, relax pacing gate for that category/hour
- [x] 1.5 Emit simulation log events for cascade decisions and applied parameters

## 2. Validation
- [ ] 2.1 Verify cap never exceeds 4 and pacing tolerance never exceeds configured max (user validation: run tests and simulation)
- [ ] 2.2 Verify no overspend beyond period budget (user validation: check simulation results)
