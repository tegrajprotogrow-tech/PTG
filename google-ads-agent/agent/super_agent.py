#!/usr/bin/env python3
"""Pro-To-Grow Google Ads super agent: analyze -> propose -> human review -> apply.

Nothing is ever changed on Google Ads, Merchant Center or Shopify unless the
proposal has status APPROVED in proposals/<date>.json. The `plan` command is
the only way to release changes, and it only releases APPROVED items that
still pass the guardrails.

Usage:
  python agent/super_agent.py analyze --date 2026-09-28
  python agent/super_agent.py review  --date 2026-09-28
  python agent/super_agent.py approve --date 2026-09-28 P001 P003 --note "ok"
  python agent/super_agent.py reject  --date 2026-09-28 P002 --note "not now"
  python agent/super_agent.py plan    --date 2026-09-28
  python agent/super_agent.py applied --date 2026-09-28 P001 --result "done"
"""

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rules  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOTS = ROOT / "data" / "snapshots"
PROPOSALS = ROOT / "proposals"
REPORTS = ROOT / "reports"
CONFIG = ROOT / "config" / "guardrails.json"

APPROVED, REJECTED, APPLIED = "APPROVED", "REJECTED", "APPLIED"
BLOCKED_ACTIONS = {"delete_customer_match_list", "remove_keywords"}


def load_config():
    return json.loads(CONFIG.read_text())


def read_csv(name, date):
    path = SNAPSHOTS / f"{date}_{name}.csv"
    if not path.exists():
        return None
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _read_any(path):
    if not path.exists():
        return None
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


ATTRIBUTES_SHEET = "1ueCXep3whov23Dqe1RQDTiRpsVEL9D6ywC-AUPUnlgs"


def _feed_append(date, products, cfg):
    """Shopify-sourced products that the linked attributes sheet doesn't cover yet (no product-line label in MC)."""
    rows = []
    for p in products:
        if not p["product_id"].lower().startswith("shopify_") or p.get("custom_label_0") or not p["product_title"]:
            continue
        label, ptype = rules.product_line(p["product_title"])
        rows.append({"id": p["product_id"], "brand": cfg["account"]["canonical_brand"], "product_type": ptype,
                     "custom_label_0": label, "custom_label_1": ""})
    if not rows:
        return []
    out = ROOT / "data" / "feeds" / f"{date}_attributes_append.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["id", "brand", "product_type", "custom_label_0", "custom_label_1"])
        w.writeheader()
        w.writerows(rows)
    return [{
        "rule": "FEED-002", "severity": "medium",
        "title": f"Add {len(rows)} new products to the linked Brand/Type/Labels sheet",
        "finding": "These products were added to Shopify after the 2026-09-28 feed: brand shows 'Pro-to-grow' and they "
                   "have no product_type or product-line label, so Shopping can't group or report them.",
        "recommended_action": "Append the rows to the existing sheet (same file, same link; Merchant Center picks them up "
                              "at the next daily fetch). Nothing else in the sheet changes.",
        "execution": {"channel": "google_sheets", "action": "append_rows", "spreadsheet_id": ATTRIBUTES_SHEET,
                      "file": str(out.relative_to(ROOT))},
        "evidence": rows, "risk": "low", "status": rules.PENDING,
    }]


def proposals_path(date):
    return PROPOSALS / f"{date}.json"


def load_proposals(date):
    path = proposals_path(date)
    if not path.exists():
        sys.exit(f"No proposals for {date}. Run: analyze --date {date}")
    return json.loads(path.read_text())


def save_proposals(date, data):
    PROPOSALS.mkdir(exist_ok=True)
    proposals_path(date).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------- analyze

def analyze(date, cfg):
    products = read_csv("mc_products", date)
    perf = read_csv("mc_performance_30d", date)
    status = read_csv("mc_status", date)
    campaigns = read_csv("ads_campaigns_14d", date)
    terms = read_csv("ads_search_terms_30d", date)
    shop = read_csv("shopify_products", date)
    actions = read_csv("ads_conversion_actions", date)
    sales = read_csv("shopify_sales_30d", date)
    items = read_csv("ads_products_30d", date)
    titles = _read_any(ROOT / "data" / "feeds" / "live_titles_sheet.csv")

    found = []
    if products:
        for rule in (rules.mc_broken_items, rules.mc_duplicates, rules.mc_brand,
                     rules.mc_gtin, rules.mc_custom_labels):
            found += rule(products, cfg)
        if titles:
            found += rules.mc_titles_not_applied(products, titles, cfg)
        if not shop:
            found += rules.mc_compliance(products, cfg)
        found += _feed_append(date, products, cfg)
    if shop:
        found += rules.shop_vendor(shop, cfg) + rules.shop_product_type(shop, cfg) + rules.compliance_infant(shop, cfg)
        if products:
            found += rules.mc_sync_gap(shop, products, cfg)
    if status:
        found += rules.mc_local_disapprovals(status, cfg)
    if perf:
        found += rules.mc_performance(perf, cfg, products)
    if terms:
        found += rules.ads_negative_keywords(terms, cfg)
    if campaigns:
        found += rules.ads_budget(campaigns, cfg) + rules.ads_not_serving(campaigns, cfg)
    if actions:
        found += rules.ads_tracking(actions, sales, cfg)
    if items:
        found += rules.ads_product_waste(items, cfg)

    feed = ROOT / "data" / "feeds" / f"{date}_supplemental_feed_DRAFT.tsv"
    if feed.exists():
        with feed.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f, delimiter="\t"))
        found.append({
            "rule": "FEED-001", "severity": "high",
            "title": f"Link supplemental feed: {sum(1 for r in rows if r['title'])} new Google titles, "
                     f"brand/product_type/labels for {len(rows)} products",
            "finding": "Fixes brand, product_type, product-line labels, HERO/LOW-CTR labels and ad exclusions "
                       "for Merchant Center in one step, without changing store titles or prices.",
            "recommended_action": "Review the titles in the draft. After approval, the agent creates it as a Google Sheet "
                                  "and you link it once in Merchant Center > Data sources > Add supplemental source.",
            "execution": {"channel": "google_sheets", "file": str(feed.relative_to(ROOT)),
                          "then": "Merchant Center > Data sources > Supplemental > Google Sheets (daily fetch)"},
            "evidence": [{"id": r["id"], "title": r["title"]} for r in rows if r["title"]],
            "risk": "low", "status": rules.PENDING,
        })

    disabled = cfg.get("disabled_rules", {})
    found = [p for p in found if p["rule"] not in disabled]
    waste = {e["item_id"].lower() for p in found if p["rule"] == "ADS-007" for e in p["evidence"]}
    for p in found:
        if p["rule"] == "PERF-002":  # a high-CTR product that loses money in Ads is not a hero
            p["evidence"] = [e for e in p["evidence"] if e["product_id"].lower() not in waste]
    found = [p for p in found if not (p["rule"] == "PERF-002" and not p["evidence"])]
    if any(p["rule"] == "FEED-002" for p in found):
        found = [p for p in found if p["rule"] != "MC-005"]  # same products, FEED-002 is the fix

    order = {"high": 0, "medium": 1, "low": 2}
    found.sort(key=lambda p: order.get(p["severity"], 3))
    for i, p in enumerate(found, 1):
        p["id"] = f"P{i:03d}"
        p["history"] = [{"at": now(), "event": "proposed"}]
    return {
        "date": date,
        "generated_at": now(),
        "sources": {
            "merchant_center": bool(products or perf or status),
            "shopify": bool(shop),
            "google_ads": bool(campaigns or terms or actions or items),
        },
        "proposals": found,
    }


def write_report(data):
    REPORTS.mkdir(exist_ok=True)
    lines = [f"# Review queue — {data['date']}", "",
             "Nothing below has been applied. Approve or reject each item by ID.", "",
             "| ID | Severity | Risk | Change | Executes via |", "|---|---|---|---|---|"]
    for p in data["proposals"]:
        via = p["execution"].get("action") or p["execution"].get("where", "manual")
        lines.append(f"| {p['id']} | {p['severity']} | {p['risk']} | {p['title']} | {via} |")
    for p in data["proposals"]:
        lines += ["", f"## {p['id']} — {p['title']}", "",
                  f"**Status:** {p['status']}  ", f"**Why:** {p['finding']}  ",
                  f"**Proposed change:** {p['recommended_action']}", ""]
        ev = p["evidence"] if isinstance(p["evidence"], list) else [p["evidence"]]
        lines.append(f"<details><summary>Evidence ({len(ev)} rows)</summary>\n")
        lines.append("```json")
        lines.append(json.dumps(ev[:40], indent=1, ensure_ascii=False))
        lines.append("```\n</details>")
    path = REPORTS / f"{data['date']}_review.md"
    path.write_text("\n".join(lines) + "\n")
    return path


# ---------------------------------------------------------------- guardrails

def guardrail_violations(p, cfg):
    ex = p["execution"]
    problems = []
    if ex.get("action") in BLOCKED_ACTIONS:
        problems.append(f"action '{ex['action']}' is never allowed")
    if ex.get("action") == "set_campaign_budget":
        amount = ex["params"]["amount_micros"] / 1_000_000
        if amount > cfg["budget"]["max_daily_budget_inr"]:
            problems.append(f"budget ₹{amount:.0f} exceeds cap ₹{cfg['budget']['max_daily_budget_inr']}")
        old = rules._num(p["evidence"].get("daily_budget")) if isinstance(p["evidence"], dict) else 0
        if old:
            pct = abs(amount - old) / old * 100
            if pct > cfg["budget"]["max_daily_change_pct"] + 0.01:
                problems.append(f"budget change {pct:.0f}% exceeds {cfg['budget']['max_daily_change_pct']}%")
    if ex.get("action") == "create_campaign" and ex.get("params", {}).get("status", "PAUSED") != "PAUSED":
        problems.append("new campaigns must be created PAUSED")
    return problems


# ---------------------------------------------------------------- commands

def set_status(date, ids, status, note, by):
    data = load_proposals(date)
    index = {p["id"]: p for p in data["proposals"]}
    cfg = load_config()
    for pid in ids:
        p = index.get(pid)
        if not p:
            print(f"{pid}: not found")
            continue
        if p["status"] == APPLIED:
            print(f"{pid}: already applied, cannot change")
            continue
        if status == APPROVED:
            problems = guardrail_violations(p, cfg)
            if problems:
                print(f"{pid}: cannot approve — {'; '.join(problems)}")
                continue
        p["status"] = status
        p["history"].append({"at": now(), "event": status.lower(), "by": by, "note": note})
        print(f"{pid}: {status}")
    save_proposals(date, data)


def cmd_review(date):
    data = load_proposals(date)
    for p in data["proposals"]:
        print(f"{p['id']}  [{p['status']:<8}] {p['severity']:<6} {p['title']}")


def cmd_plan(date):
    """Print the approved, guardrail-clean changes. This is the only release gate."""
    data = load_proposals(date)
    cfg = load_config()
    expiry = dt.date.fromisoformat(data["date"]) + dt.timedelta(days=cfg["approval"]["proposal_expiry_days"])
    if dt.date.today() > expiry:
        sys.exit(f"Proposals from {date} expired on {expiry}. Re-run analyze on fresh data.")
    plan = []
    for p in data["proposals"]:
        if p["status"] != APPROVED:
            continue
        problems = guardrail_violations(p, cfg)
        if problems:
            print(f"{p['id']}: skipped — {'; '.join(problems)}", file=sys.stderr)
            continue
        plan.append({"id": p["id"], "title": p["title"], "execution": p["execution"]})
    print(json.dumps(plan, indent=2, ensure_ascii=False))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("analyze", "review", "plan"):
        s = sub.add_parser(name)
        s.add_argument("--date", default=dt.date.today().isoformat())
    for name in ("approve", "reject", "applied"):
        s = sub.add_parser(name)
        s.add_argument("--date", default=dt.date.today().isoformat())
        s.add_argument("ids", nargs="+")
        s.add_argument("--note", default="")
        s.add_argument("--result", default="")
        s.add_argument("--by", default=load_config()["approval"]["approver"])
    args = ap.parse_args(argv)

    if args.cmd == "analyze":
        data = analyze(args.date, load_config())
        save_proposals(args.date, data)
        report = write_report(data)
        print(f"{len(data['proposals'])} proposals written to {proposals_path(args.date).relative_to(ROOT)}")
        print(f"Review report: {report.relative_to(ROOT)}")
    elif args.cmd == "review":
        cmd_review(args.date)
    elif args.cmd == "approve":
        set_status(args.date, args.ids, APPROVED, args.note, args.by)
    elif args.cmd == "reject":
        set_status(args.date, args.ids, REJECTED, args.note, args.by)
    elif args.cmd == "applied":
        data = load_proposals(args.date)
        for p in data["proposals"]:
            if p["id"] in args.ids:
                if p["status"] != APPROVED:
                    print(f"{p['id']}: not approved, refusing to mark applied")
                    continue
                p["status"] = APPLIED
                p["history"].append({"at": now(), "event": "applied", "result": args.result})
                print(f"{p['id']}: APPLIED")
        save_proposals(args.date, data)
    elif args.cmd == "plan":
        cmd_plan(args.date)


if __name__ == "__main__":
    main()
