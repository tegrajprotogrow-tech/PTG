# Pro-To-Grow Google Ads Super Agent

Human-in-the-loop optimization agent for **Google Ads** and **Google Merchant Center**.
It reads your accounts, finds problems, and proposes fixes. It **applies nothing until you approve it**.

Read the full process in [WORKFLOW.md](WORKFLOW.md).

## Layout
```
agent/rules.py          optimization rules (read-only, output = proposals)
agent/super_agent.py    CLI: analyze / review / approve / reject / plan / applied
config/guardrails.json  hard limits (budget caps, blocked actions, thresholds)
data/snapshots/         dated read-only data pulls (CSV)
proposals/<date>.json   review queue (PENDING / APPROVED / REJECTED / APPLIED)
reports/<date>_review.md human-readable review report
tests/                  unit tests for rules + approval gate
```

## Quick start
```bash
cd google-ads-agent
python3 agent/super_agent.py analyze --date 2026-09-28   # build the proposals
python3 agent/super_agent.py review  --date 2026-09-28   # list them
python3 -m unittest discover -s tests                    # run the tests
```
Python 3.9+ and the standard library are all it needs.

## Connections (via Windsor.ai)
| Account | Status |
|---|---|
| Merchant Center `5775540276` (Pro-to-grow) | ✅ connected, read-only |
| Google Ads / Manager (MCC) account | ⛔ not connected yet. Authorize at https://onboard.windsor.ai/connect?connector=google_ads&next=/google_ads/authorize and choose the MCC so all client accounts are included |

Once Google Ads is connected, the agent can execute these actions (only after approval): pause or enable campaigns, ad groups and ads;
set budget, tROAS, tCPA and max CPC; push negative keywords; create paused campaigns, ad groups and RSAs; set geo, language and ad schedule.
Merchant Center changes go through Shopify or manual steps. Windsor does not provide write access to Merchant Center.
