import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestIntercompanyAutomation(unittest.TestCase):
    def test_purchase_order_submit_creates_draft_sales_order(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        source = (APP_ROOT / "intercompany.py").read_text()

        # Must fire on submit, never on draft save: a draft PO can still change
        # (the copied snapshot would go stale) or be deleted (orphaning the SO).
        self.assertIn("orderlift.intercompany.create_draft_sales_order_from_purchase_order", hooks)
        self.assertNotIn(
            '"after_insert": "orderlift.intercompany.create_draft_sales_order_from_purchase_order"',
            hooks,
        )
        purchase_order_hooks = hooks.split('"Purchase Order": {', 1)[1].split("\n    },", 1)[0]
        on_submit_block = purchase_order_hooks.split('"on_submit"', 1)[1]
        self.assertIn(
            "orderlift.intercompany.create_draft_sales_order_from_purchase_order",
            on_submit_block,
        )
        # The hook move is inert unless the guard accepts submitted docs too.
        self.assertIn('int(doc.get("docstatus") or 0) != 1', source)
        self.assertNotIn('int(doc.get("docstatus") or 0) != 0', source)
        for token in [
            "ORDERLIFT_PARENT_COMPANY",
            "_operating_companies",
            "_is_orderlift_operating_company",
            "ensure_internal_orderlift_parties",
            "create_draft_sales_order_from_purchase_order",
            "doc.doctype != \"Purchase Order\"",
            "int(doc.get(\"docstatus\") or 0) != 1",
            "is_internal_supplier",
            "represents_company",
            "_internal_customer_for_company_pair(target_company, source_company)",
            "Sales Order",
            "sales_order.inter_company_order_reference = doc.name",
            "sales_order.po_no = doc.name",
            "sales_order.insert(ignore_permissions=True)",
            "doc.db_set(\"inter_company_order_reference\", sales_order.name",
            "ignore_orderlift_company_scope",
        ]:
            self.assertIn(token, source)

    def test_internal_party_setup_is_pair_scoped_and_allowed_to_transact(self):
        source = (APP_ROOT / "intercompany.py").read_text()
        script = (APP_ROOT / "scripts" / "setup_internal_orderlift_parties.py").read_text()

        self.assertIn("ensure_internal_orderlift_parties", script)
        for token in [
            "parent_company",
            "companies=companies",
            "REPORTING_COMPANY_FIELD",
            "_is_descendant_company",
            "for represented_company in companies:",
            "allowed_companies = [company for company in companies if company != represented_company]",
            "_ensure_internal_customer(represented_company, allowed_companies",
            "_ensure_internal_supplier(represented_company, allowed_companies",
            "filters = {\"is_internal_customer\": 1, \"represents_company\": represented_company}",
            "filters = {\"is_internal_supplier\": 1, \"represents_company\": represented_company}",
            "_set_if_field(doc, \"custom_company\", represented_company)",
            "_remove_internal_company_access(doc, [represented_company])",
            "_ensure_internal_company_access(doc, allowed_companies)",
            "_ensure_allowed_companies(doc, allowed_companies)",
            "return represented_company",
            "INTERNAL_PARTY_TAG = \"Orderlift Internal Party\"",
            "_tag_internal_party(\"Customer\", doc.name, summary)",
            "_tag_internal_party(\"Supplier\", doc.name, summary)",
            "add_tag(INTERNAL_PARTY_TAG, doctype, name)",
            "doc.append(\"companies\", {\"company\": company})",
            "doc.flags.ignore_orderlift_company_scope = True",
            "frappe.rename_doc(doctype, doc.name, target_name, force=True, merge=False, show_alert=False)",
        ]:
            self.assertIn(token, source)
