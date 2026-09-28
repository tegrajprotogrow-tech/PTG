import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent"))
import rules  # noqa: E402
import super_agent as sa  # noqa: E402

CFG = json.loads((Path(__file__).resolve().parent.parent / "config" / "guardrails.json").read_text())


class RuleTests(unittest.TestCase):
    def test_every_proposal_starts_pending(self):
        terms = [{"search_term": "free oats sample", "campaign_id": "111", "cost": "900", "clicks": "40", "conversions": "0"}]
        out = rules.ads_negative_keywords(terms, CFG)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["status"], "PENDING")
        self.assertEqual(out[0]["execution"]["action"], "push_negative_keywords")

    def test_converting_term_not_negated(self):
        terms = [{"search_term": "protein oats", "campaign_id": "1", "cost": "900", "clicks": "40", "conversions": "2"}]
        self.assertEqual(rules.ads_negative_keywords(terms, CFG), [])

    def test_budget_cut_respects_max_pct(self):
        camps = [{"campaign": "PMax", "campaign_id": "9", "cost": "10000", "conversion_value": "10000",
                  "daily_budget": "1000", "budget_limited": "false"}]
        out = rules.ads_budget(camps, CFG)
        self.assertEqual(out[0]["execution"]["params"]["amount_micros"], 800_000_000)
        self.assertEqual(sa.guardrail_violations(out[0], CFG), [])

    def test_budget_increase_capped(self):
        camps = [{"campaign": "Hero", "campaign_id": "9", "cost": "1000", "conversion_value": "9000",
                  "daily_budget": "4900", "budget_limited": "true"}]
        out = rules.ads_budget(camps, CFG)
        self.assertEqual(out[0]["execution"]["params"]["amount_micros"], 5000 * 1_000_000)

    def test_guardrail_blocks_oversized_budget(self):
        p = {"execution": {"action": "set_campaign_budget", "params": {"amount_micros": 2000 * 1_000_000}},
             "evidence": {"daily_budget": "1000"}}
        self.assertTrue(sa.guardrail_violations(p, CFG))

    def test_guardrail_blocks_destructive_actions(self):
        p = {"execution": {"action": "remove_keywords", "params": {}}, "evidence": {}}
        self.assertTrue(sa.guardrail_violations(p, CFG))


class ProductLineTests(unittest.TestCase):
    def test_classification(self):
        self.assertEqual(rules.product_line("Progen Stage 1 Infant Formula – 400g")[0], "INFANT-FORMULA")
        self.assertEqual(rules.product_line("Procan-D Banana & Dates Baby Cereal")[0], "BABY-CEREAL")
        self.assertEqual(rules.product_line("High-Protein Double Chocolate Oats Value Pack – 750g")[0], "OATS-HPO")
        self.assertEqual(rules.product_line("Zero Added Sugar Oats with Monk Fruit & Millets")[0], "OATS-ZAS")
        self.assertEqual(rules.product_line("Stainless Steel Bowl with Lid & Spoon – 500ml")[0], "ACCESSORY")
        self.assertEqual(rules.product_line("Bhim Banana Oats & Stainless Steel Bowl Combo")[0], "OATS-BBO")

    def test_vendor_rule_is_case_insensitive(self):
        shop = [{"product_id": "1", "title": "x", "status": "ACTIVE", "vendor": "Pro-to-grow"},
                {"product_id": "2", "title": "y", "status": "ACTIVE", "vendor": "My Store"}]
        out = rules.shop_vendor(shop, CFG)
        self.assertEqual([i["id"] for i in out[0]["execution"]["items"]], ["gid://shopify/Product/2"])


class ApprovalGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        sa.PROPOSALS = Path(self.tmp.name)
        self.date = "2099-01-01"
        sa.save_proposals(self.date, {"date": self.date, "proposals": [
            {"id": "P001", "status": "PENDING", "title": "a", "history": [],
             "execution": {"channel": "windsor", "action": "pause_campaign", "params": {"campaign_id": "1"}},
             "evidence": {}},
            {"id": "P002", "status": "PENDING", "title": "b", "history": [],
             "execution": {"channel": "windsor", "action": "pause_campaign", "params": {"campaign_id": "2"}},
             "evidence": {}},
        ]})

    def tearDown(self):
        self.tmp.cleanup()

    def plan_ids(self):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            sa.cmd_plan(self.date)
        return [p["id"] for p in json.loads(buf.getvalue())]

    def test_plan_releases_only_approved(self):
        self.assertEqual(self.plan_ids(), [])
        sa.set_status(self.date, ["P002"], sa.APPROVED, "", "tester")
        self.assertEqual(self.plan_ids(), ["P002"])

    def test_rejected_never_released(self):
        sa.set_status(self.date, ["P001"], sa.REJECTED, "", "tester")
        self.assertEqual(self.plan_ids(), [])


if __name__ == "__main__":
    unittest.main()
