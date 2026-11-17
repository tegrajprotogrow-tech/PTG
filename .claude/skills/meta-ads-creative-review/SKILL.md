---
name: meta-ads-creative-review
description: Analyze Meta Ads creatives at ad level (hook rate, hold rate, CTR, CPA, ROAS, fatigue) from the Meta Ads reporting Google Sheet, label winners, losers and fatiguing ads, update 04_Creative_Tracker and propose the next creative tests. Use when asked which ads or creatives are working, what to scale or kill, about creative fatigue, hook performance, or for new creative ideas based on data.
---

# Meta Ads creative review

Read `meta-ads-reporting/KPI_PLAYBOOK.md` first.

## Inputs

- **Period:** default is the last 14 complete days, compared with the 14 days before. Use the last 30 days if total ad-level spend is low.
- **Minimum data:** to judge an ad, it needs spend ≥ 2× target CPA **or** ≥ 3,000 impressions. Ads below that are "Not enough data".

## Steps

1. **Pull** `RAW_Ad_Daily` (period plus previous period), `RAW_Ad_Creatives`, `04_Creative_Tracker` and `01_Targets` with the Google Sheets connector. If the Sheet is empty, use the Meta Ads connector (`ads_get_ad_entities` at ad level with insights, and `ads_get_creatives`).
2. **Aggregate per ad_id** (sum, then divide): spend, impressions, link_clicks, purchases, purchase_value, leads, video_3s_views, thruplays. Compute CTR, CPM, CPA/CPL, ROAS, hook rate and hold rate.
3. **Fatigue check** per ad: compare the last 7 days with the 7 days before. Flag *Fatiguing* when CTR is down > 20% and CPM is flat or up, or when CPA is up > 25% at stable spend. Add the ad's age from `launch_date` in the tracker, or its first date in RAW_Ad_Daily.
4. **Label** each ad that has enough data:
   - **Winner:** CPA ≤ target (or ROAS ≥ target) and spend share is meaningful
   - **Promising:** within 115% of target CPA with a strong hook rate (≥ 30%) or CTR
   - **Loser:** CPA > 150% of target after the minimum data
   - **Fatiguing:** as defined in step 3
5. **Find patterns.** Join to `04_Creative_Tracker` (format, angle, hook, offer). Compare spend-weighted CPA and ROAS and average hook/hold rate by format, angle and hook type. Report only groups that have ≥ 2 ads.
6. **Next tests:** propose 3–5 tests. Each test changes one variable (for example, same angle with a new hook, or the winning hook in a new format). Name the hypothesis and the success metric. If the user wants ad copy, use the `ad-creative:social-ad-set` skill when it is available.
7. **Update the tracker (only with the user's OK):** write the labels into `04_Creative_Tracker.status` and a one-line `learning` per ad. Add rows for ads that are missing from the tracker.

## Output

```
## Creative Review – <period>
| Thumb | Ad | Format/Angle | Spend | Hook % | Hold % | CTR | CPA | ROAS | Label |
(top 10 by spend; thumbnail as a link to thumbnail_url)

**Winners → scale**: ...
**Fatiguing → refresh**: ... (ad age, CTR Δ)
**Losers → pause (needs your OK)**: ...
**Patterns**: <format/angle/hook insight with numbers>
**Next tests**: 1. Hypothesis · variable · success metric · budget/days
```

## Rules

- Read-only on Meta. Pausing or scaling is a recommendation until the user confirms the exact change.
- Don't call a winner on fewer than ~10 conversions. Say "directional" instead.
- For statistical "is this difference real" questions, use the `ad-creative:ad-test-readout` skill when it is available.
