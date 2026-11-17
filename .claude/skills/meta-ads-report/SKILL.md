---
name: meta-ads-report
description: Build a weekly, monthly or custom-period Meta Ads performance report from the Meta Ads reporting Google Sheet (or the Meta Ads connector as fallback), with KPI vs previous period and target, funnel diagnosis, top movers and prioritized actions. Use when asked "how are Meta ads doing", "weekly report", "monthly report", "why did CPA/ROAS change", or for a client or management performance update.
---

# Meta Ads performance report

Read `meta-ads-reporting/KPI_PLAYBOOK.md` first. It has the Sheet ID, tabs, formulas, diagnosis tree and thresholds.

## Inputs

- **Period:** default is the last 7 complete days (yesterday back 7 days). "Monthly" means the last full calendar month, or month-to-date if asked.
- **Comparison:** the previous equal-length period.
- **Account(s):** all active rows in `00_Config` unless the user names one.

## Steps

1. **Freshness.** Read `Run_Log` (last ~20 rows). Note the last OK run time and any ERROR rows.
2. **Pull data** with the Google Sheets connector `get_values`:
   - `RAW_Campaign_Daily` for both periods
   - `02_Naming_Map` (funnel_stage, audience_type, product)
   - `01_Targets` for the period's month
   - `03_Change_Log` for both periods
   - `RAW_Backend_Orders` if it has rows for the period
   - If the Sheet is empty or stale, use the Meta Ads connector instead (`ads_get_ad_accounts`, then `ads_get_ad_entities` with insights for the period) and say so in the report.
3. **Compute** in a short Python script (pandas) when there are more than ~200 rows. Otherwise work it out directly. Sum first, then use the playbook formulas. Totals and by-campaign views:
   - Spend, Impressions, Link clicks, LPV, ATC, Checkout, Purchases, Revenue, Leads
   - CPM, CTR, CPC, LPV rate, ATC rate, CVR, CPA, CPL, ROAS, AOV
   - Δ% vs previous period; status vs target (green / amber / red per the thresholds)
   - MER and blended CAC if backend data exists
4. **Diagnose** each red or amber KPI and any |Δ| > 20% using the diagnosis tree (CPM → CTR → LPV → on-site → AOV → tracking). Name the campaigns that drove the change: show each one's contribution to the total Δ spend and Δ purchases.
5. **Group** by funnel_stage and audience_type (join on campaign_id). Show the spend share and CPA/ROAS for each group.
6. **Top movers:** the 3 best and 3 worst campaigns by Δ CPA (or Δ CPL for lead-gen) with spend ≥ 5% of total.
7. **Recommendations:** 3–7 actions in the playbook's format, ordered by expected impact.

## Output template

```
## Meta Ads Report – <period> vs <previous period>
Data as of <last OK sync> · Last 7 days provisional

**Summary**: <3–5 lines: result vs target, main driver, top action>

| KPI | This period | Previous | Δ% | Target | Status |
|---|---|---|---|---|---|
| Spend | ... |
| Purchases / Leads | ... |
| CPA / CPL | ... |
| ROAS | ... |
| CPM | ... |
| CTR (link) | ... |
| CVR | ... |
| MER (backend) | ... |

### Funnel
Impr → Link clicks → LPV → ATC → Checkout → Purchase (rates and Δ)

### By funnel stage / audience
<table>

### What changed and why
- <driver with numbers + linked Change_Log entry>

### Top movers
<best 3 / worst 3>

### Actions (priority order)
1. **<Action>** on <entity (ID)>: why <metric/number>; expected <impact>; risk <...>; re-check <KPI> on <date>
```

## Delivery

- Answer in chat with the report.
- If the user asks for a shareable or management version, also publish it as a private artifact page (or a Google Doc if they prefer Docs), and give them the link.
- Never change campaigns. Hand off actions for the user to approve.
