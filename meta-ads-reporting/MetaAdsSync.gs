/**
 * Meta Ads -> Google Sheets sync (free, Marketing API Insights endpoint)
 * ---------------------------------------------------------------------
 * Paste into: Google Sheet > Extensions > Apps Script (replace Code.gs).
 *
 * One-time setup:
 *   1. Project Settings > Script Properties:
 *        META_TOKEN        = <System User token with ads_read>
 *        META_API_VERSION  = v23.0   (optional; use the current Graph API version)
 *   2. Fill 00_Config (one row per ad account, active = Y).
 *   3. Run setupHeaders() once, then backfill90Days() once.
 *   4. Run createDailyTrigger() once -> runDailySync() runs every morning.
 *
 * How it works:
 *   - Every run re-pulls the last N days (lookback_days in 00_Config, default 7)
 *     and REPLACES those rows, because Meta keeps updating conversions inside
 *     the attribution window.
 *   - Only additive numbers are stored. Compute CTR / CPC / CPM / CPA / ROAS
 *     in Looker Studio as SUM(x)/SUM(y).
 *   - `reach` is NOT additive across days or breakdowns; use it only at
 *     single-day grain, never SUM it in Looker for a period.
 */

// ===================== SETTINGS =====================
const TZ = 'Asia/Kolkata';
const DEFAULT_LOOKBACK = 7;
const ATTRIBUTION = ['7d_click', '1d_view'];

const ID_SHEETS = {
  config: '00_Config',
  log: 'Run_Log',
  creatives: 'RAW_Ad_Creatives',
};

// Additive metrics written for every job (order = column order)
const METRICS = [
  'spend', 'impressions', 'reach', 'clicks', 'link_clicks', 'landing_page_views',
  'add_to_cart', 'initiate_checkout', 'purchases', 'purchase_value', 'leads', 'registrations',
];
const VIDEO_METRICS = ['video_3s_views', 'thruplays', 'video_p25', 'video_p50', 'video_p75', 'video_p100'];

// Action types to look for, first match wins (unified first, pixel fallback)
const ACTION_MAP = {
  landing_page_views: ['landing_page_view', 'omni_landing_page_view'],
  add_to_cart: ['add_to_cart', 'omni_add_to_cart', 'offsite_conversion.fb_pixel_add_to_cart'],
  initiate_checkout: ['initiate_checkout', 'omni_initiated_checkout', 'offsite_conversion.fb_pixel_initiate_checkout'],
  purchases: ['purchase', 'omni_purchase', 'offsite_conversion.fb_pixel_purchase'],
  leads: ['lead', 'onsite_conversion.lead_grouped', 'offsite_conversion.fb_pixel_lead'],
  registrations: ['complete_registration', 'omni_complete_registration', 'offsite_conversion.fb_pixel_complete_registration'],
  video_3s_views: ['video_view'],
};
const VALUE_MAP = {
  purchase_value: ['purchase', 'omni_purchase', 'offsite_conversion.fb_pixel_purchase'],
};

const BASE_FIELDS = 'account_id,account_name,campaign_id,campaign_name,spend,impressions,reach,clicks,inline_link_clicks,actions,action_values';

// ===================== JOBS =====================
// Each job = one RAW_ tab.
const JOBS = [
  {
    sheet: 'RAW_Campaign_Daily', level: 'campaign',
    extraFields: 'objective',
    dims: ['date', 'account_id', 'account_name', 'campaign_id', 'campaign_name', 'objective'],
  },
  {
    sheet: 'RAW_AdSet_Daily', level: 'adset',
    extraFields: 'adset_id,adset_name,optimization_goal',
    dims: ['date', 'account_id', 'account_name', 'campaign_id', 'campaign_name', 'adset_id', 'adset_name', 'optimization_goal'],
  },
  {
    sheet: 'RAW_Ad_Daily', level: 'ad', video: true,
    extraFields: 'adset_id,adset_name,ad_id,ad_name,video_thruplay_watched_actions,video_p25_watched_actions,video_p50_watched_actions,video_p75_watched_actions,video_p100_watched_actions',
    dims: ['date', 'account_id', 'account_name', 'campaign_id', 'campaign_name', 'adset_id', 'adset_name', 'ad_id', 'ad_name'],
  },
  {
    sheet: 'RAW_AgeGender', level: 'campaign', breakdowns: 'age,gender',
    dims: ['date', 'account_id', 'account_name', 'campaign_id', 'campaign_name', 'age', 'gender'],
  },
  {
    sheet: 'RAW_Placement', level: 'campaign', breakdowns: 'publisher_platform,platform_position',
    dims: ['date', 'account_id', 'account_name', 'campaign_id', 'campaign_name', 'publisher_platform', 'platform_position'],
  },
  {
    sheet: 'RAW_Region', level: 'campaign', breakdowns: 'region',
    dims: ['date', 'account_id', 'account_name', 'campaign_id', 'campaign_name', 'region'],
  },
  {
    sheet: 'RAW_Device', level: 'campaign', breakdowns: 'impression_device',
    dims: ['date', 'account_id', 'account_name', 'campaign_id', 'campaign_name', 'impression_device'],
  },
];

const CREATIVE_HEADERS = ['ad_id', 'ad_name', 'account_id', 'effective_status', 'creative_id', 'creative_name', 'thumbnail_url', 'image_url', 'preview_link', 'updated_at'];

function headersFor(job) {
  return job.dims.concat(METRICS, job.video ? VIDEO_METRICS : [], ['updated_at']);
}

// ===================== ENTRY POINTS =====================
function runDailySync() { runAll_(null); }

function backfill90Days() { runAll_(90); }

/** Run one job by sheet name, e.g. runOne('RAW_Ad_Daily', 30) */
function runOne(sheetName, days) {
  const job = JOBS.find(j => j.sheet === sheetName);
  if (!job) throw new Error('No job for ' + sheetName);
  runJobs_([job], days || null);
}

function setupHeaders() {
  const ss = SpreadsheetApp.getActive();
  JOBS.forEach(job => writeHeader_(ss, job.sheet, headersFor(job)));
  writeHeader_(ss, ID_SHEETS.creatives, CREATIVE_HEADERS);
  writeHeader_(ss, ID_SHEETS.log, ['run_at', 'sheet', 'account_id', 'since', 'until', 'rows', 'status', 'message']);
}

function createDailyTrigger() {
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'runDailySync')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('runDailySync').timeBased().everyDays(1).atHour(6).inTimezone(TZ).create();
}

function onOpen() {
  SpreadsheetApp.getUi().createMenu('Meta Ads Sync')
    .addItem('Run daily sync now', 'runDailySync')
    .addItem('Backfill last 90 days', 'backfill90Days')
    .addItem('Refresh ad creatives / thumbnails', 'pullAdCreatives')
    .addSeparator()
    .addItem('Write headers', 'setupHeaders')
    .addItem('Create daily 6 AM trigger', 'createDailyTrigger')
    .addToUi();
}

// ===================== CORE =====================
function runAll_(daysOverride) {
  runJobs_(JOBS, daysOverride);
  pullAdCreatives();
}

function runJobs_(jobs, daysOverride) {
  const accounts = getAccounts_();
  if (!accounts.length) throw new Error('No active accounts in ' + ID_SHEETS.config);
  const ss = SpreadsheetApp.getActive();

  jobs.forEach(job => {
    accounts.forEach(acct => {
      const days = daysOverride || acct.lookback || DEFAULT_LOOKBACK;
      const until = fmt_(addDays_(new Date(), -1));
      const since = fmt_(addDays_(new Date(), -days));
      try {
        const rows = [];
        // Pull in <=30-day chunks so large backfills don't time out / hit limits
        chunkRanges_(since, until, 30).forEach(r => {
          fetchInsights_(acct.id, job, r.since, r.until).forEach(rec => rows.push(toRow_(rec, job)));
        });
        upsert_(ss, job.sheet, headersFor(job), rows, acct.id, since);
        log_(job.sheet, acct.id, since, until, rows.length, 'OK', '');
      } catch (e) {
        log_(job.sheet, acct.id, since, until, 0, 'ERROR', String(e).slice(0, 500));
      }
    });
  });
}

function fetchInsights_(accountId, job, since, until) {
  const fields = [BASE_FIELDS, job.extraFields].filter(Boolean).join(',');
  const params = {
    level: job.level,
    time_increment: 1,
    time_range: JSON.stringify({ since: since, until: until }),
    fields: fields,
    action_attribution_windows: JSON.stringify(ATTRIBUTION),
    use_unified_attribution_setting: true,
    limit: 500,
  };
  if (job.breakdowns) params.breakdowns = job.breakdowns;
  return graphGetAll_('/' + actId_(accountId) + '/insights', params);
}

function toRow_(r, job) {
  const row = job.dims.map(d => {
    if (d === 'date') return r.date_start;
    if (d === 'account_id') return 'act_' + r.account_id;
    return r[d] !== undefined ? r[d] : '';
  });
  METRICS.forEach(m => {
    switch (m) {
      case 'spend': row.push(num_(r.spend)); break;
      case 'impressions': row.push(num_(r.impressions)); break;
      case 'reach': row.push(num_(r.reach)); break;
      case 'clicks': row.push(num_(r.clicks)); break;
      case 'link_clicks': row.push(num_(r.inline_link_clicks)); break;
      default:
        if (ACTION_MAP[m]) row.push(pickAction_(r.actions, ACTION_MAP[m]));
        else if (VALUE_MAP[m]) row.push(pickAction_(r.action_values, VALUE_MAP[m]));
        else row.push(0);
    }
  });
  if (job.video) {
    row.push(pickAction_(r.actions, ACTION_MAP.video_3s_views));
    row.push(sumAction_(r.video_thruplay_watched_actions));
    row.push(sumAction_(r.video_p25_watched_actions));
    row.push(sumAction_(r.video_p50_watched_actions));
    row.push(sumAction_(r.video_p75_watched_actions));
    row.push(sumAction_(r.video_p100_watched_actions));
  }
  row.push(new Date());
  return row;
}

/** Replace rows for this account with date >= since, then append fresh rows. */
function upsert_(ss, sheetName, headers, newRows, accountId, since) {
  const sh = ss.getSheetByName(sheetName) || ss.insertSheet(sheetName);
  writeHeader_(ss, sheetName, headers);
  const lastRow = sh.getLastRow();
  let keep = [];
  if (lastRow > 1) {
    const data = sh.getRange(2, 1, lastRow - 1, headers.length).getValues();
    const acctIdx = headers.indexOf('account_id');
    keep = data.filter(r => {
      if (r[0] === '' || r[0] === null) return false;
      const d = r[0] instanceof Date ? fmt_(r[0]) : String(r[0]);
      return String(r[acctIdx]) !== actId_(accountId) || d < since;
    });
  }
  const all = keep.concat(newRows);
  if (lastRow > 1) sh.getRange(2, 1, lastRow - 1, headers.length).clearContent();
  if (all.length) {
    ensureRows_(sh, all.length + 1);
    sh.getRange(2, 1, all.length, headers.length).setValues(all);
    sh.getRange(2, 1, all.length, 1).setNumberFormat('yyyy-mm-dd');
  }
}

// ===================== CREATIVES (thumbnails for Looker) =====================
function pullAdCreatives() {
  const ss = SpreadsheetApp.getActive();
  const rows = [];
  getAccounts_().forEach(acct => {
    try {
      const ads = graphGetAll_('/' + actId_(acct.id) + '/ads', {
        fields: 'id,name,effective_status,preview_shareable_link,creative{id,name,thumbnail_url,image_url}',
        thumbnail_width: 300, thumbnail_height: 300,
        limit: 200,
      });
      ads.forEach(a => {
        const c = a.creative || {};
        rows.push([a.id, a.name, actId_(acct.id), a.effective_status || '', c.id || '', c.name || '',
          c.thumbnail_url || '', c.image_url || '', a.preview_shareable_link || '', new Date()]);
      });
      log_(ID_SHEETS.creatives, acct.id, '', '', ads.length, 'OK', '');
    } catch (e) {
      log_(ID_SHEETS.creatives, acct.id, '', '', 0, 'ERROR', String(e).slice(0, 500));
    }
  });
  const sh = ss.getSheetByName(ID_SHEETS.creatives) || ss.insertSheet(ID_SHEETS.creatives);
  sh.clearContents();
  writeHeader_(ss, ID_SHEETS.creatives, CREATIVE_HEADERS);
  if (rows.length) {
    ensureRows_(sh, rows.length + 1);
    sh.getRange(2, 1, rows.length, CREATIVE_HEADERS.length).setValues(rows);
  }
}

// ===================== GRAPH API =====================
function graphGetAll_(path, params) {
  const props = PropertiesService.getScriptProperties();
  const token = props.getProperty('META_TOKEN');
  if (!token) throw new Error('Set META_TOKEN in Script Properties');
  const ver = props.getProperty('META_API_VERSION') || 'v23.0';
  let url = 'https://graph.facebook.com/' + ver + path + '?' + qs_(Object.assign({}, params, { access_token: token }));
  const out = [];
  while (url) {
    const res = fetchWithRetry_(url);
    (res.data || []).forEach(x => out.push(x));
    url = res.paging && res.paging.next ? res.paging.next : null;
  }
  return out;
}

function fetchWithRetry_(url) {
  for (let attempt = 0; attempt < 5; attempt++) {
    const resp = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
    const body = JSON.parse(resp.getContentText() || '{}');
    if (resp.getResponseCode() === 200 && !body.error) return body;
    const err = body.error || {};
    // 4/17/32/613/80000-80014 = rate limits; 1/2 = transient
    const retryable = [1, 2, 4, 17, 32, 613].indexOf(err.code) > -1 || (err.code >= 80000 && err.code <= 80014) || resp.getResponseCode() >= 500;
    if (!retryable) throw new Error('Graph API ' + resp.getResponseCode() + ': ' + (err.message || resp.getContentText()));
    Utilities.sleep(Math.min(60000, 5000 * Math.pow(2, attempt)));
  }
  throw new Error('Graph API: retries exhausted');
}

// ===================== HELPERS =====================
function getAccounts_() {
  const sh = SpreadsheetApp.getActive().getSheetByName(ID_SHEETS.config);
  const v = sh.getDataRange().getValues();
  const h = v[0].map(String);
  const iActive = h.indexOf('active'), iId = h.indexOf('ad_account_id'), iLb = h.indexOf('lookback_days');
  return v.slice(1)
    .filter(r => String(r[iActive]).toUpperCase() === 'Y' && String(r[iId]).trim())
    .map(r => ({ id: String(r[iId]).trim(), lookback: Number(r[iLb]) || DEFAULT_LOOKBACK }));
}

function actId_(id) { id = String(id).trim(); return id.indexOf('act_') === 0 ? id : 'act_' + id; }

function pickAction_(arr, types) {
  if (!arr) return 0;
  for (let i = 0; i < types.length; i++) {
    const hit = arr.find(a => a.action_type === types[i]);
    if (hit) return num_(hit.value);
  }
  return 0;
}

function sumAction_(arr) { return (arr || []).reduce((s, a) => s + num_(a.value), 0); }
function num_(x) { const n = Number(x); return isNaN(n) ? 0 : n; }
function fmt_(d) { return Utilities.formatDate(d, TZ, 'yyyy-MM-dd'); }
function addDays_(d, n) { const x = new Date(d.getTime()); x.setDate(x.getDate() + n); return x; }

function chunkRanges_(since, until, size) {
  const out = [];
  let s = new Date(since + 'T00:00:00');
  const end = new Date(until + 'T00:00:00');
  while (s <= end) {
    let e = addDays_(s, size - 1);
    if (e > end) e = end;
    out.push({ since: fmt_(s), until: fmt_(e) });
    s = addDays_(e, 1);
  }
  return out;
}

function qs_(o) {
  return Object.keys(o).map(k => encodeURIComponent(k) + '=' + encodeURIComponent(o[k])).join('&');
}

function writeHeader_(ss, name, headers) {
  const sh = ss.getSheetByName(name) || ss.insertSheet(name);
  if (sh.getMaxColumns() < headers.length) sh.insertColumnsAfter(sh.getMaxColumns(), headers.length - sh.getMaxColumns());
  sh.getRange(1, 1, 1, headers.length).setValues([headers]).setFontWeight('bold');
  sh.setFrozenRows(1);
}

function ensureRows_(sh, n) {
  if (sh.getMaxRows() < n) sh.insertRowsAfter(sh.getMaxRows(), n - sh.getMaxRows());
}

function log_(sheet, acct, since, until, rows, status, msg) {
  const sh = SpreadsheetApp.getActive().getSheetByName(ID_SHEETS.log);
  if (sh) sh.appendRow([new Date(), sheet, acct, since, until, rows, status, msg]);
}
