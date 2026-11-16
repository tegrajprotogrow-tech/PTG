# Looker Studio setup: Meta Ads performance dashboard

Data source: Google Sheet **Meta Ads Reporting – Looker Studio Data Hub**, filled by `MetaAdsSync.gs`.

## 1. Data sources to add

| Looker data source | Sheet tab | Notes |
|---|---|---|
| Meta – Campaign Daily | RAW_Campaign_Daily | Main source for most pages |
| Meta – AdSet Daily | RAW_AdSet_Daily | |
| Meta – Ad Daily | RAW_Ad_Daily | Creative page |
| Meta – Ad Creatives | RAW_Ad_Creatives | Thumbnail images |
| Meta – Age Gender / Placement / Region / Device | RAW_* breakdown tabs | Audience page |
| Targets | 01_Targets | Pacing |
| Naming Map | 02_Naming_Map | Funnel, audience and product grouping |
| Backend Orders | RAW_Backend_Orders | MER and blended CAC |

When you add each one:
- Set `date` to type **Date (YYYYMMDD)**. Set every `*_id` field to **Text**, because long IDs lose digits if Looker reads them as numbers.
- Set metric aggregation to **Sum**. For `reach`, set the aggregation to **None** and don't use it on period scorecards.
- Set `spend` and `purchase_value` to type **Currency (INR)**.

## 2. Blends

| Blend | Left table | Right table | Join |
|---|---|---|---|
| Campaign + Naming | RAW_Campaign_Daily | 02_Naming_Map | Left outer on `campaign_id` |
| Ad + Creative | RAW_Ad_Daily | RAW_Ad_Creatives (+ 04_Creative_Tracker) | Left outer on `ad_id` |
| Meta vs Backend | RAW_Campaign_Daily (SUM spend by date) | RAW_Backend_Orders | Left outer on `date` |

## 3. Calculated fields

Create these in the data source so every chart can use them. Always divide sums; never average a ratio. (Looker Studio returns null when dividing by zero, so no extra guard is needed.)

```
CTR (link)          = SUM(link_clicks) / SUM(impressions)
CTR (all)           = SUM(clicks) / SUM(impressions)
CPC (link)          = SUM(spend) / SUM(link_clicks)
CPM                 = SUM(spend) / SUM(impressions) * 1000
LPV rate            = SUM(landing_page_views) / SUM(link_clicks)
ATC rate            = SUM(add_to_cart) / SUM(landing_page_views)
Checkout rate       = SUM(initiate_checkout) / SUM(add_to_cart)
Purchase rate       = SUM(purchases) / SUM(initiate_checkout)
CVR (click→purchase)= SUM(purchases) / SUM(link_clicks)
CPA                 = SUM(spend) / SUM(purchases)
CPL                 = SUM(spend) / SUM(leads)
ROAS                = SUM(purchase_value) / SUM(spend)
AOV                 = SUM(purchase_value) / SUM(purchases)
Cost per LPV        = SUM(spend) / SUM(landing_page_views)
```

These go in the **Ad Daily** source (video metrics):
```
Hook rate (3s)      = SUM(video_3s_views) / SUM(impressions)
Hold rate           = SUM(thruplays) / SUM(video_3s_views)
Completion rate     = SUM(video_p100) / SUM(video_3s_views)
```

This goes in the **Meta vs Backend** blend:
```
MER                 = SUM(revenue) / SUM(spend)
Blended CAC         = SUM(spend) / SUM(new_customer_orders)
Meta share of revenue = SUM(purchase_value) / SUM(revenue)
```

This goes in **Ad Creatives**. Set the field type to **Image**:
```
Thumbnail = IMAGE(thumbnail_url)
```

## 4. Pages

**Every page:** add a date range control (default *Last 28 days*, comparison *Previous period*), plus filter controls for account, campaign, funnel_stage and audience_type.

1. **Executive Summary**
   - Scorecards with change vs the previous period: Spend, Revenue (purchase_value), ROAS, Purchases, CPA, CTR, CPM, MER
   - Time series: Spend (bars) against ROAS (line), daily
   - Bullet chart: Spend MTD against `monthly_budget` from 01_Targets
2. **Funnel**
   - Funnel bars: Impressions → Link clicks → LPV → ATC → Checkout → Purchases
   - Table showing each step's rate by funnel_stage
3. **Campaigns & Ad Sets**
   - Table: campaign, spend, purchases, CPA, ROAS, CTR, CPM, with heatmap on CPA and ROAS
   - Drill down from campaign to ad set
4. **Creative**
   - Table: Thumbnail, ad_name, format, angle, spend, hook rate, hold rate, CTR, CPA, ROAS
   - Scatter: Hook rate (x) against CPA (y), bubble size = spend
5. **Audience**
   - Age × gender pivot heatmap on CPA and ROAS
   - Placement table (publisher_platform + platform_position)
   - Geo map by region
   - Device split
6. **Trends & Diagnostics**
   - Weekly CPM, CTR, CVR and CPA lines. Use these to tell rising costs (CPM up) apart from a creative problem (CTR down) or a site problem (CVR down)
   - Table from 03_Change_Log shown next to the trends
7. **Pacing**
   - Spend MTD, budget, % used, % of month passed
   - Projected month-end spend = Spend MTD / days passed × days in month

## 5. Weekly review checklist

- [ ] Run_Log shows no ERROR rows
- [ ] Meta spend matches Ads Manager for yesterday (within about 1%)
- [ ] CPA and ROAS are within 15% of target. If not, check whether CPM, CTR or CVR caused it
- [ ] Frequency on retargeting is below 3–4 per week (check in Ads Manager)
- [ ] Top 3 and bottom 3 creatives by CPA are recorded in 04_Creative_Tracker
- [ ] Every change made this week is logged in 03_Change_Log
