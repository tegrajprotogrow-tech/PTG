---
name: meta-ads-sync-ops
description: Operate and maintain the free Meta Marketing API → Google Sheets sync (meta-ads-reporting/MetaAdsSync.gs) and its Looker Studio setup. Covers checking Run_Log health, explaining and fixing sync errors (token, permissions, rate limits, timeouts), reconciling Sheet numbers with Ads Manager, adding new metrics or breakdowns, adding ad accounts, and archiving old rows. Use when data is missing or wrong in the Sheet or Looker Studio, or when the sync needs to change.
---

# Meta Ads sync operations

Files:
- `meta-ads-reporting/MetaAdsSync.gs`: the Apps Script. The copy in this repo is the source of truth; the user pastes it into the Sheet's Apps Script editor.
- `meta-ads-reporting/LOOKER_STUDIO_SETUP.md`: data sources, blends, calculated fields and pages.
- `meta-ads-reporting/KPI_PLAYBOOK.md`: Sheet ID and tab map.

## Health check

1. Read `Run_Log` (last 50 rows) with the Google Sheets connector.
2. For each RAW_ tab and account, report the last OK run, row count and any ERROR rows with their message.
3. Check that the max `date` in `RAW_Campaign_Daily` is yesterday.

## Error guide

| Message contains | Cause | Fix |
|---|---|---|
| `Set META_TOKEN` | Script property missing | Apps Script → Project Settings → Script Properties → add META_TOKEN |
| `code 190` / `Error validating access token` | Token expired or revoked | Generate a new System User token (ads_read) and replace META_TOKEN |
| `code 200` / `(#10)` / `permission` | System User lacks access to the ad account | Business Settings → System Users → Assign assets → ad account (View performance) |
| `code 100` + field name | Field or breakdown not valid in this API version or combination | Remove or rename the field in `JOBS`, or check the Marketing API changelog; update META_API_VERSION |
| `code 17` / `80000–80014` / `User request limit` | Rate limit | The script retries automatically. If it keeps failing, reduce accounts per run or move the breakdown jobs to a second trigger |
| `Exceeded maximum execution time` | Apps Script 6-minute limit | Split runs: `runOne('RAW_Ad_Daily', 7)` on its own trigger; lower the backfill to 30-day runs |
| `retries exhausted` | Meta API outage or sustained throttling | Re-run later; check status.fb.com |
| Sheet "above the limit of 10000000 cells" | Sheet is full | Archive: copy rows older than N months to an archive spreadsheet, then delete them from RAW_ tabs. Consider BigQuery |

## Reconcile with Ads Manager

Compare one complete day older than 7 days (so attribution has settled) for one account. Ads Manager settings: same attribution (7-day click, 1-day view), same columns, account timezone. Spend should match within about 1%. Purchases may differ slightly for the most recent days only. Common causes of mismatch: a different attribution setting in Ads Manager, the date range in a different timezone, or `purchase` vs `omni_purchase` action types (see `ACTION_MAP`).

## Changing the script

- **New metric from `actions`:** add a column name to `METRICS` and its action types to `ACTION_MAP` (or `VALUE_MAP` for values). Headers update automatically. Run `setupHeaders`, then `backfill90Days`, because existing rows would otherwise have shifted columns. Add the field to the Looker data source (Resource → Manage data sources → Refresh fields).
- **New breakdown tab:** add a `JOBS` entry with `breakdowns` and `dims`. Check that the breakdown is valid with action metrics (some breakdowns, like `hourly_stats_aggregated_by_advertiser_time_zone`, have limits).
- **New account:** add a row to `00_Config` with `active = Y`, then run `backfill90Days` (it touches only active accounts, and row replacement is per account).
- After any change: run `node --check` on a copy of the file to catch syntax errors, update the repo copy, and tell the user to paste the new version into Apps Script.

## Rules

- Never write tokens into the Sheet, the repo or chat. They belong only in Script Properties.
- Don't hand-edit RAW_ tabs. Fix the script and re-pull instead.
