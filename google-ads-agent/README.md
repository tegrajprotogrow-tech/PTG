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

## Connections
| Account | Status |
|---|---|
| Merchant Center `5775540276` (Pro-to-grow) | ✅ connected, read-only |
| Google Ads `294-317-5872` (PRO-TO-GROW 2026) | ✅ connected via Composio (`googleads`). Accounts 783-909-8191 and 389-160-9052 return permission denied |
| Shopify `protogrow.in` | ✅ read-only analytics (orders/AOV) for tracking checks |

Google Ads data is read through Composio. Writing changes back (budgets, negatives, pauses) is only done after approval, and the
Composio write path has not been exercised yet; the first approved Ads change will be applied and verified one item at a time.
Merchant Center changes go through Shopify or manual steps. Windsor does not provide write access to Merchant Center.
