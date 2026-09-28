# Super Agent Workflow — Google Ads + Merchant Center

**Rule #1: nothing is changed on any account until you approve it.**
The agent reads data, finds problems, and writes proposals. Each proposal stays
`PENDING` until you mark it `APPROVED`. Only approved items can be applied.

```
 ┌────────────┐   ┌────────────┐   ┌────────────┐   ┌──────────────────┐   ┌────────────┐   ┌────────────┐
 │ 1. COLLECT │ → │ 2. ANALYZE │ → │ 3. PROPOSE │ → │ 4. REVIEW (YOU)  │ → │ 5. APPLY   │ → │ 6. VERIFY  │
 │ read-only  │   │ rules.py   │   │ PENDING    │   │ approve / reject │   │ approved   │   │ 7 days     │
 │ data pull  │   │ guardrails │   │ report.md  │   │ ◄── GATE ──►     │   │ items only │   │ later      │
 └────────────┘   └────────────┘   └────────────┘   └──────────────────┘   └────────────┘   └─────┬──────┘
       ▲                                                                                          │
       └──────────────────────────────── weekly loop ◄──────────────────────────────────────────┘
```

## Stage 1: Collect (read-only)
Claude pulls data through Windsor.ai and saves it as CSV in `data/snapshots/<date>_*.csv`:

| File | Source | Status |
|---|---|---|
| `mc_products.csv` | Merchant Center product attributes | ✅ connected (5775540276) |
| `mc_performance_30d.csv` | Merchant Center impressions and clicks | ✅ connected |
| `mc_status.csv` | Approved or disapproved counts per destination | ✅ connected |
| `ads_campaigns_14d.csv` | Google Ads campaign cost, value and budget | ⛔ connect Google Ads first |
| `ads_search_terms_30d.csv` | Google Ads search terms | ⛔ connect Google Ads first |

## Stage 2: Analyze
`python agent/super_agent.py analyze --date YYYY-MM-DD` runs every rule in `agent/rules.py`:

| Rule | What it catches | How the fix is applied |
|---|---|---|
| MC-001 | Items with no title or price 0 | Manual (Shopify) |
| MC-002 | The same product listed twice (Shopify feed and PTG feed) | Manual (MC data sources) |
| MC-003 | Wrong brand ("My Store", "Pro-to-grow") | Shopify vendor update |
| MC-004 | Missing GTIN or barcode | Manual (Shopify barcode) |
| MC-005 | Missing custom_label_0 (product line) | MC feed rule |
| MC-006 | Local-destination disapprovals | MC settings |
| PERF-001 | High impressions with CTR below 0.15% | Title and image rewrite, then label LOW-CTR |
| PERF-002 | Hero products (CTR of 1.5% or more, 100+ clicks) | Label HERO and give it a dedicated budget |
| PERF-003 | Impressions with zero clicks | Review or exclude |
| ADS-001 | Search terms that spend and never convert | `push_negative_keywords` |
| ADS-002 | Campaign ROAS far below or above target | `set_campaign_budget` (±20% max) |

## Stage 3: Propose
The agent writes two files:
- `proposals/<date>.json` is the machine-readable queue. Each item has an id, the evidence, the exact API payload, and `status: PENDING`.
- `reports/<date>_review.md` is the human-readable version for you to read.

## Stage 4: Review (you are the gate)
Read the report, then tell Claude in chat, for example: *"approve P001 P004, reject P002"*.
You can also run the commands yourself:

```bash
python agent/super_agent.py review  --date 2026-09-28
python agent/super_agent.py approve --date 2026-09-28 P001 P004 --note "go"
python agent/super_agent.py reject  --date 2026-09-28 P002 --note "check SKUs first"
```

Every decision is logged in the proposal's `history`, with who approved it, when, and the note.
Proposals expire after 7 days. Old data is never applied.

## Stage 5: Apply (approved only)
`python agent/super_agent.py plan --date <date>` prints **only** items that are APPROVED and still pass the guardrails.
- `channel: windsor`: Claude runs `execute_action` with that exact payload on Google Ads.
- `channel: shopify`: Claude runs the Shopify product update.
- `channel: manual`: Claude gives you step-by-step instructions. Merchant Center has no write API in this setup.

After each change, run `applied --date <date> P00X --result "..."`.

## Stage 6: Verify
Seven days later, Claude pulls fresh data and compares it with the "before" snapshot for each applied proposal.
If a change made things worse, the agent writes a **rollback proposal**. That proposal also needs your approval.

## Guardrails (`config/guardrails.json`)
These are hard limits. Even an approved change is blocked if it breaks one.
- Budget moves at most ±20% per change, the cap is ₹5,000 per day, and budgets change at most once every 7 days.
- tROAS or tCPA moves at most ±15%, and only after 30+ conversions.
- New campaigns are always created **PAUSED**.
- Keywords and customer lists are never deleted. Negatives are capped at 25 per run.
- A campaign is never touched during its first 14 days (learning period).

## Cadence
| When | What |
|---|---|
| Every Monday | Full Collect, Analyze and Propose run, then the review report is sent to you |
| Daily (optional) | Anomaly check only (spend spike, disapprovals). Alerts, no proposals |
| 7 days after apply | Verify |
