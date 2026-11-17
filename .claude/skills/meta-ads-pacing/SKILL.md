---
name: meta-ads-pacing
description: Check Meta Ads budget pacing for the current month against 01_Targets in the Meta Ads reporting Google Sheet, with spend-to-date, projected month-end spend, CPA and ROAS vs target, and the daily budget needed to land on plan. Use when asked about budget pacing, overspend or underspend, "are we on track this month", or what daily budget to set.
---

# Meta Ads budget pacing

Read `meta-ads-reporting/KPI_PLAYBOOK.md` first.

## Steps

1. **Today and month bounds** in Asia/Kolkata. Days passed = complete days through yesterday. Days left = days in month − days passed.
2. **Pull** `01_Targets` rows for this month (`month` = first day of month) and month-to-date `RAW_Campaign_Daily`. If yesterday is missing from the Sheet, pull yesterday from the Meta Ads connector and say so.
3. **Compute per target row:** account-level when `campaign_id = ALL`; otherwise campaign-level, or the Naming Map group if `product_or_group` matches a `02_Naming_Map.product`.
   - Spend MTD, % of budget used, % of month passed
   - Run rate = average spend of the last 7 days
   - Projected month-end = Spend MTD + run rate × days left
   - Required daily budget = (budget − Spend MTD) / days left
   - Purchases or leads MTD vs target (pro-rated), CPA and ROAS MTD vs target
4. **Status:**
   - On track: projection within ±5% of budget
   - Under: projection < 95% → name the campaigns with headroom (CPA below target) where budget could go
   - Over: projection > 105% → name the campaigns with the worst CPA to trim first
   - Efficiency: if CPA > 115% of target, flag it. Spending to plan at a bad CPA is not "on track".

## Output

```
## Pacing – <Month YYYY> (day X of N)
| Scope | Budget | Spend MTD | % used | % month | Projected | Required/day | CPA vs target | ROAS vs target | Status |

**Actions**
- <Campaign (ID)>: change daily budget ₹A → ₹B (why); needs your OK
```

## Rules

- Budget changes are recommendations only. Apply them through the Meta Ads connector only after the user confirms the exact amounts, then log each change in `03_Change_Log`.
- Don't move budget by more than ~20% per ad set per day; bigger jumps can reset the learning phase. Suggest stepwise increases.
- If `01_Targets` has no row for this month, ask the user for the budget and targets, or offer to add them.
