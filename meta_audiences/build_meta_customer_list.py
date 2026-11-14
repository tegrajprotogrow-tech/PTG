#!/usr/bin/env python3
"""Build a Meta (Facebook) Customer List file from Shopify order exports.

Input : one or more Shopify Admin GraphQL `orders` JSON pages
        ({"data":{"orders":{"nodes":[...]}}}).
Output: Meta Customer List CSV with SHA-256 hashed identifiers, following
        Meta's normalisation rules, plus an unhashed `value` column for
        value-based lookalikes.

Rules applied (per Meta "Customer list formatting guidelines"):
  email   trim, lowercase
  phone   digits only, with country code (India -> 91XXXXXXXXXX), no leading 0/+
  fn, ln  lowercase, letters only (no spaces / punctuation), UTF-8
  ct      lowercase, no spaces / punctuation
  st      lowercase, no spaces / punctuation (full state name outside the US)
  zip     lowercase, no spaces (India: 6 digits)
  country ISO-3166 alpha-2, lowercase
  value   NOT hashed - total spend in the window (INR)
"""
import csv, hashlib, json, re, sys, unicodedata
from collections import OrderedDict

INCLUDE_STATUS = {"PAID", "PARTIALLY_PAID"}   # COD advance orders count as buyers
COLS = ["email", "phone", "fn", "ln", "ct", "st", "zip", "country", "value"]


def sha(v):
    return hashlib.sha256(v.encode("utf-8")).hexdigest() if v else ""

def letters(v):
    v = unicodedata.normalize("NFKC", (v or "")).lower()
    return re.sub(r"[\W_\d]+", "", v)

def norm_email(v):
    v = (v or "").strip().lower()
    return v if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v) else ""

def norm_phone(v, cc="IN"):
    d = re.sub(r"\D", "", v or "").lstrip("0")
    if cc == "IN":
        if len(d) == 10 and d[0] in "6789":
            d = "91" + d
        if not (len(d) == 12 and d.startswith("91")):
            return ""
    return d if 8 <= len(d) <= 15 else ""

def norm_zip(v):
    return re.sub(r"\s+", "", (v or "").lower())


def main(out_path, pages):
    custs = OrderedDict()
    stats = {"orders": 0, "kept": 0, "skipped_status": 0, "skipped_cancelled": 0, "no_identifier": 0}
    for p in pages:
        for o in json.load(open(p))["data"]["orders"]["nodes"]:
            stats["orders"] += 1
            if o.get("cancelledAt"):
                stats["skipped_cancelled"] += 1; continue
            if o.get("displayFinancialStatus") not in INCLUDE_STATUS:
                stats["skipped_status"] += 1; continue
            c = o.get("customer") or {}
            a = o.get("billingAddress") or o.get("shippingAddress") or c.get("defaultAddress") or {}
            cc = a.get("countryCodeV2") or "IN"
            email = norm_email(o.get("email") or (c.get("defaultEmailAddress") or {}).get("emailAddress"))
            phone = ""
            for cand in (o.get("phone"), (c.get("defaultPhoneNumber") or {}).get("phoneNumber"),
                         a.get("phone"), (o.get("shippingAddress") or {}).get("phone")):
                phone = norm_phone(cand, cc)
                if phone: break
            if not email and not phone:
                stats["no_identifier"] += 1; continue
            stats["kept"] += 1
            key = c.get("id") or email or phone
            amt = float(((o.get("totalPriceSet") or {}).get("shopMoney") or {}).get("amount") or 0)
            row = custs.get(key)
            if row:
                row["value"] += amt
                for k, v in (("email", email), ("phone", phone)):
                    if not row[k] and v: row[k] = v
                continue
            custs[key] = {
                "email": email, "phone": phone,
                "fn": letters(a.get("firstName") or c.get("firstName")),
                "ln": letters(a.get("lastName") or c.get("lastName")),
                "ct": letters(a.get("city")), "st": letters(a.get("province")),
                "zip": norm_zip(a.get("zip")), "country": cc.lower(), "value": amt,
            }
    # de-dupe again on identical email/phone across different customer ids
    seen, final = {}, []
    for r in custs.values():
        k = r["email"] or r["phone"]
        if k in seen:
            seen[k]["value"] += r["value"]; continue
        seen[k] = r; final.append(r)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        for r in final:
            w.writerow([sha(r[c]) for c in COLS[:-1]] + [f"{r['value']:.2f}"])
    stats["unique_customers"] = len(final)
    stats["with_email"] = sum(1 for r in final if r["email"])
    stats["with_phone"] = sum(1 for r in final if r["phone"])
    stats["total_value_inr"] = round(sum(r["value"] for r in final), 2)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
