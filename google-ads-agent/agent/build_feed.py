#!/usr/bin/env python3
"""Build a DRAFT Merchant Center supplemental feed from the latest snapshots.

The file is only a draft. It changes nothing until someone uploads it or links it
as a supplemental data source in Merchant Center, which happens only after approval.
Only the columns listed below are overridden. Price, stock and links stay with Shopify.

Usage: python agent/build_feed.py --date 2026-09-28
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rules  # noqa: E402
import super_agent as sa  # noqa: E402

FIELDS = ["id", "title", "brand", "product_type", "custom_label_0", "custom_label_1", "custom_label_4"]


def build(date):
    cfg = sa.load_config()
    mc = cfg["merchant_center"]
    shop = sa.read_csv("shopify_products", date) or []
    perf = {p["product_id"].lower(): p for p in (sa.read_csv("mc_performance_30d", date) or [])}
    titles_path = sa.ROOT / "config" / "title_overrides.csv"
    titles = {r["shopify_product_id"]: r["google_title"] for r in csv.DictReader(titles_path.open(encoding="utf-8"))}

    rows = []
    for p in shop:
        if p["status"] != "ACTIVE" or "hidden-bundle-item" in p["tags"]:
            continue
        offer = f"shopify_ZZ_{p['product_id']}_{p['variant_id']}"
        label0, ptype = rules.product_line(p["title"])
        stats = perf.get(offer.lower(), {})
        imp, clk = rules._num(stats.get("impressions")), rules._num(stats.get("clicks"))
        ctr = clk / imp * 100 if imp else 0
        label1 = ""
        if clk >= mc["hero_min_clicks"] and ctr >= mc["hero_min_ctr_pct"]:
            label1 = "HERO"
        elif imp >= mc["low_ctr_min_impressions"] and ctr < mc["low_ctr_threshold_pct"]:
            label1 = "LOW-CTR"
        title = titles.get(p["product_id"], "")
        if len(title) > 150:
            sys.exit(f"title too long for {p['product_id']}: {len(title)} chars (max 150)")
        rows.append({
            "id": offer,
            "title": title,
            "brand": cfg["account"]["canonical_brand"],
            "product_type": ptype,
            "custom_label_0": label0,
            "custom_label_1": label1,
            "custom_label_4": "EXCLUDE-ADS" if label0 in ("INFANT-FORMULA", "BABY-CEREAL") else "",
        })
    out = sa.ROOT / "data" / "feeds" / f"{date}_supplemental_feed_DRAFT.tsv"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS, delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    return out, rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    path, rows = build(ap.parse_args().date)
    print(f"{len(rows)} rows, {sum(1 for r in rows if r['title'])} new titles -> {path.relative_to(sa.ROOT)}")
