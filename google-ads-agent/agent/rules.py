"""Optimization rules. Each rule reads snapshot rows and returns proposals.

Rules never change anything. They only describe a finding and the exact
change that *would* be made, so a human can review it first.
"""

import re

PENDING = "PENDING"


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _proposal(rule_id, severity, title, finding, action, execution, evidence, risk="low"):
    return {
        "rule": rule_id,
        "severity": severity,
        "title": title,
        "finding": finding,
        "recommended_action": action,
        "execution": execution,
        "evidence": evidence,
        "risk": risk,
        "status": PENDING,
    }


def _manual(where, steps):
    return {"channel": "manual", "where": where, "steps": steps}


def _tokens(title):
    words = re.findall(r"[a-z0-9]+", (title or "").lower())
    stop = {"protogrow", "pro", "to", "grow", "ready", "eat", "oats", "breakfast", "the", "and", "of", "with", "for", "g"}
    return {w for w in words if w not in stop}


def _source(product_id):
    return "shopify" if product_id.lower().startswith("shopify_") else "ptg_feed"


# ---------------------------------------------------------------- Merchant Center

def mc_broken_items(products, cfg):
    broken = [p for p in products if not p["product_title"] or _num(p["price"]) <= 0]
    if not broken:
        return []
    return [_proposal(
        "MC-001", "high", f"{len(broken)} products have no title or a price of 0",
        "Items without a title or with price 0 cannot serve and lower account quality.",
        "Fix title and price in the source (Shopify / feed), or exclude these items from the Google channel.",
        _manual("Shopify > Products (or Merchant Center > Products)",
                ["Open each item listed in evidence", "Add title + price, or unpublish from the Google & YouTube channel"]),
        [{"product_id": p["product_id"], "brand": p["brand"]} for p in broken],
        risk="none")]


def mc_duplicates(products, cfg):
    threshold = cfg["merchant_center"]["duplicate_title_similarity"]
    shop = [p for p in products if _source(p["product_id"]) == "shopify" and p["product_title"]]
    feed = [p for p in products if _source(p["product_id"]) == "ptg_feed" and p["product_title"]]
    pairs = []
    for f in feed:
        ft = _tokens(f["product_title"])
        best, best_score = None, 0.0
        for s in shop:
            st = _tokens(s["product_title"])
            if not ft or not st:
                continue
            score = len(ft & st) / len(ft | st)
            if score > best_score:
                best, best_score = s, score
        if best and best_score >= threshold:
            pairs.append({"ptg_feed_id": f["product_id"], "shopify_id": best["product_id"],
                          "title": f["product_title"], "similarity": round(best_score, 2)})
    if not pairs:
        return []
    return [_proposal(
        "MC-002", "high", f"{len(pairs)} products appear to be listed twice (Shopify feed + PTG feed)",
        "The same product is submitted by two data sources. Duplicates split clicks and history, "
        "and can compete against each other in the same auction.",
        "Pick ONE primary data source per product. Recommended: keep the PTG-* feed (it has custom labels, "
        "GTINs and numeric categories) and exclude the matching Shopify items from Google.",
        _manual("Merchant Center > Products > Data sources",
                ["Confirm each pair in evidence is really the same SKU",
                 "Exclude the Shopify duplicate (or delete the PTG item and move its labels to Shopify)"]),
        pairs, risk="medium")]


def mc_brand(products, cfg):
    canonical = cfg["account"]["canonical_brand"]
    wrong = [p for p in products if p["brand"] and p["brand"] != canonical]
    if not wrong:
        return []
    counts = {}
    for p in wrong:
        counts[p["brand"]] = counts.get(p["brand"], 0) + 1
    return [_proposal(
        "MC-003", "medium", f"{len(wrong)} products use a non-standard brand name",
        f"Brand values found: {counts}. 'My Store' is the Shopify default and is wrong.",
        f"Set brand (Shopify vendor) to '{canonical}' on every product.",
        {"channel": "shopify", "action": "update-product", "field": "vendor", "value": canonical,
         "product_ids": [p["product_id"] for p in wrong]},
        [{"product_id": p["product_id"], "brand": p["brand"]} for p in wrong],
        risk="low")]


def mc_gtin(products, cfg):
    missing = [p for p in products if p["product_title"] and not p["gtin"]]
    if not missing:
        return []
    return [_proposal(
        "MC-004", "medium", f"{len(missing)} products have no GTIN (barcode)",
        "Products with GTINs get better matching and more impressions in Shopping.",
        "Add the EAN-13 barcode from the pack to each product (Shopify variant 'Barcode' field).",
        _manual("Shopify > Products > Variant > Barcode", ["Enter the 13-digit barcode printed on the pack"]),
        [p["product_id"] for p in missing], risk="none")]


def mc_custom_labels(products, cfg):
    missing = [p for p in products if p["product_title"] and not p["custom_label_0"]]
    if not missing:
        return []
    return [_proposal(
        "MC-005", "medium", f"{len(missing)} products have no custom_label_0 (product line)",
        "Without labels, Shopping / Performance Max cannot split budget by product line.",
        "Set custom_label_0 to the product line (OATS-BBO, OATS-HPO, OATS-ZAS, CD, PANCAKE, COMBO, ACCESSORY).",
        _manual("Merchant Center > Data sources > Rules (or Shopify metafield mm-google-shopping.custom_label_0)",
                ["Create a rule mapping title keywords to the product line label"]),
        [{"product_id": p["product_id"], "title": p["product_title"]} for p in missing], risk="none")]


def mc_local_disapprovals(statuses, cfg):
    out = []
    for s in statuses:
        if s["reporting_context"] in ("LOCAL_INVENTORY_ADS", "FREE_LOCAL_LISTINGS") and _num(s["disapproved"]) > 0 and _num(s["active"]) == 0:
            out.append(s)
    if not out:
        return []
    return [_proposal(
        "MC-006", "low", f"All products disapproved for local destinations ({', '.join(s['reporting_context'] for s in out)})",
        "Every item is disapproved for local inventory / free local listings. This is normal if you have no "
        "physical store linked, but it inflates the disapproval count and hides real issues.",
        "If Pro-To-Grow has no retail store on Google Business Profile: turn off the local destinations. "
        "If it does: link the Business Profile and submit a local inventory feed.",
        _manual("Merchant Center > Settings > Add-ons / Destinations", ["Disable Local inventory ads and Free local listings"]),
        out, risk="none")]


def mc_performance(perf, cfg):
    mc = cfg["merchant_center"]
    low_ctr, heroes, zero = [], [], []
    for p in perf:
        imp, clk = _num(p["impressions"]), _num(p["clicks"])
        ctr = (clk / imp * 100) if imp else 0.0
        row = {"product_id": p["product_id"], "title": p["product_title"], "impressions": int(imp),
               "clicks": int(clk), "ctr_pct": round(ctr, 2)}
        if imp >= mc["low_ctr_min_impressions"] and ctr < mc["low_ctr_threshold_pct"]:
            low_ctr.append(row)
        if clk >= mc["hero_min_clicks"] and ctr >= mc["hero_min_ctr_pct"]:
            heroes.append(row)
        if imp >= mc["zero_click_min_impressions"] and clk == 0:
            zero.append(row)
    out = []
    if low_ctr:
        low_ctr.sort(key=lambda r: -r["impressions"])
        out.append(_proposal(
            "PERF-001", "high", f"{len(low_ctr)} products get lots of impressions but almost no clicks",
            f"CTR below {mc['low_ctr_threshold_pct']}% on {mc['low_ctr_min_impressions']}+ impressions (30 days). "
            "Usually a weak main image, a vague title, or a price that looks high next to competitors.",
            "1) Rewrite titles as: Brand + Product + Key benefit + Size (front-load the search words). "
            "2) Use a clean white-background pack shot as the main image. "
            "3) Tag these custom_label_1=LOW-CTR so Ads can bid them down until fixed.",
            _manual("Shopify product title/image + Merchant Center label rule",
                    ["Review each item", "Approve new title text (agent will draft it on request)"]),
            low_ctr, risk="low"))
    if heroes:
        heroes.sort(key=lambda r: -r["ctr_pct"])
        out.append(_proposal(
            "PERF-002", "medium", f"{len(heroes)} hero products with strong CTR",
            f"{mc['hero_min_clicks']}+ clicks and CTR above {mc['hero_min_ctr_pct']}%.",
            "Tag custom_label_1=HERO and give them their own asset group / campaign with a higher budget share.",
            _manual("Merchant Center label rule, then Google Ads", ["Create the label", "Build a HERO listing group"]),
            heroes, risk="low"))
    if zero:
        out.append(_proposal(
            "PERF-003", "low", f"{len(zero)} products with impressions but zero clicks",
            "No clicks at all over 30 days.",
            "Check price vs benchmark and image; consider excluding from Shopping if still zero after fixes.",
            _manual("Merchant Center > Products", ["Review each item"]),
            zero, risk="low"))
    return out


# ---------------------------------------------------------------- Google Ads

def ads_negative_keywords(search_terms, cfg):
    kw = cfg["keywords"]
    wasted = [t for t in search_terms
              if _num(t["cost"]) >= kw["negative_min_cost_inr"] and _num(t["conversions"]) == 0
              and _num(t["clicks"]) >= kw["negative_min_clicks"]]
    wasted.sort(key=lambda t: -_num(t["cost"]))
    wasted = wasted[: kw["max_negatives_per_run"]]
    out = []
    for t in wasted:
        out.append(_proposal(
            "ADS-001", "high", f"Add negative keyword [{t['search_term']}]",
            f"Spent ₹{_num(t['cost']):.0f} on {int(_num(t['clicks']))} clicks with 0 conversions.",
            "Add as exact-match negative at campaign level.",
            {"channel": "windsor", "connector": "google_ads", "action": "push_negative_keywords",
             "params": {"level": "campaign", "campaign_id": t["campaign_id"],
                        "keywords": [{"text": t["search_term"], "match_type": "EXACT"}]}},
            t, risk="low"))
    return out


def ads_budget(campaigns, cfg):
    target = cfg["bidding"]["target_roas"]
    max_pct = cfg["budget"]["max_daily_change_pct"]
    cap = cfg["budget"]["max_daily_budget_inr"]
    out = []
    for c in campaigns:
        cost, value, budget = _num(c["cost"]), _num(c["conversion_value"]), _num(c["daily_budget"])
        if cost <= 0 or budget <= 0:
            continue
        roas = value / cost
        if roas < target * 0.7:
            new = round(budget * (1 - max_pct / 100))
            direction = "Decrease"
        elif roas > target * 1.3 and c.get("budget_limited", "").lower() == "true":
            new = min(round(budget * (1 + max_pct / 100)), cap)
            direction = "Increase"
        else:
            continue
        if new == budget:
            continue
        out.append(_proposal(
            "ADS-002", "high", f"{direction} budget of '{c['campaign']}' ₹{budget:.0f} → ₹{new:.0f}/day",
            f"ROAS {roas:.2f} vs target {target:.2f} (cost ₹{cost:.0f}, value ₹{value:.0f}).",
            f"{direction} daily budget by {max_pct}% (guardrail maximum).",
            {"channel": "windsor", "connector": "google_ads", "action": "set_campaign_budget",
             "params": {"campaign_id": c["campaign_id"], "budget_type": "daily",
                        "amount_micros": int(new * 1_000_000)}},
            c, risk="medium"))
    return out
