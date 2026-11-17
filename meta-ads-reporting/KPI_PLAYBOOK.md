# Meta Ads KPI Playbook (shared reference for the agent and skills)

## Data hub

- Google Sheet ID: `1qGmreQIm_jrhpizDeXFDBMa2Dlx0FM8Khlu_UX-C6Os` (Meta Ads Reporting – Looker Studio Data Hub)
- Timezone: Asia/Kolkata. Currency: INR (check `00_Config.currency` per account).
- Filled daily by `meta-ads-reporting/MetaAdsSync.gs`. Each run re-pulls the last 7 days.

| Tab | Grain | Use for |
|---|---|---|
| RAW_Campaign_Daily | date × campaign | Headline KPIs, trends, pacing |
| RAW_AdSet_Daily | date × ad set | Audience and optimization-goal analysis |
| RAW_Ad_Daily | date × ad (+ video) | Creative analysis |
| RAW_Ad_Creatives | ad | Thumbnails and status |
| RAW_AgeGender / RAW_Placement / RAW_Region / RAW_Device | date × campaign × breakdown | Audience and placement mix |
| 00_Config | account | Which accounts are active |
| 01_Targets | month × account/campaign | Budget, target CPA / ROAS |
| 02_Naming_Map | campaign | funnel_stage, audience_type, product, geo |
| 03_Change_Log | change | Explains jumps in trends |
| 04_Creative_Tracker | ad | Format, angle, hook, test status, learnings |
| RAW_Backend_Orders | date | Real revenue → MER, blended CAC |
| RAW_Leads_Quality | lead | Cost per qualified lead |
| Run_Log | sync run | Data freshness and errors |

## Metric rules

- Sum additive columns first, then divide. Never average daily ratios.
- `reach` is not additive across days or breakdowns. Don't sum it; report reach only at one-day grain or from Ads Manager.
- The last 7 days are still settling (attribution). Label them "provisional" when comparing.
- Join on IDs, not names.

## Formulas

| KPI | Formula |
|---|---|
| CTR (link) | link_clicks / impressions |
| CPC (link) | spend / link_clicks |
| CPM | spend / impressions × 1000 |
| LPV rate | landing_page_views / link_clicks |
| ATC rate | add_to_cart / landing_page_views |
| Checkout rate | initiate_checkout / add_to_cart |
| Purchase rate | purchases / initiate_checkout |
| CVR | purchases / link_clicks |
| CPA | spend / purchases |
| CPL | spend / leads |
| ROAS | purchase_value / spend |
| AOV | purchase_value / purchases |
| Hook rate | video_3s_views / impressions |
| Hold rate | thruplays / video_3s_views |
| MER | backend revenue / total ad spend |
| Blended CAC | total ad spend / new_customer_orders |

## Diagnosis tree (why did CPA / ROAS move?)

CPA = CPM ÷ (1000 × CTR × CVR). So a CPA change is explained by one or more of:

1. **CPM up** → auction or audience cost. Check: frequency, audience size, seasonality (festive sales, month-end), placement mix shift, competition.
2. **CTR down** → creative fatigue or weak hook. Check: ad-level CTR trend, hook rate, frequency > 3 on prospecting, creative age > 3–4 weeks.
3. **LPV rate down** (< ~70%) → slow landing page or broken link / tracking.
4. **ATC → purchase drop** → site, price, offer, stock or checkout issue. Not an ads problem; flag it to the site or product owner.
5. **AOV down** → product mix or discount change; ROAS falls even if CPA is flat.
6. **Tracking** → sudden drop to ~0 conversions while clicks stay steady means pixel/CAPI is broken. Check Run_Log and Events Manager.

Always check `03_Change_Log` for the same dates before concluding.

## Thresholds (defaults; override with 01_Targets)

| Signal | Flag when |
|---|---|
| CPA vs target | > 115% of target → red; 100–115% → amber |
| ROAS vs target | < 85% of target → red |
| Frequency (7d, prospecting) | > 3 |
| Frequency (7d, retargeting) | > 6 |
| Hook rate | < 25% (Reels/video) |
| Hold rate | < 15% |
| Link CTR | < 0.8% prospecting |
| Week-on-week change | |Δ| > 20% on spend, CPA or ROAS |
| Learning phase | ad set with < 50 optimization events in 7 days |

## Recommendation format

Every recommendation must include: **what** (entity + action), **why** (metric + number), **expected impact**, **risk**, and **how to measure** (KPI + date to re-check). Order by impact.

## Safety

- Analysis and reporting are read-only.
- Never pause, activate, change budget, duplicate or create anything in Meta without the user's explicit confirmation of that exact change.
- Log every approved change in `03_Change_Log`.
