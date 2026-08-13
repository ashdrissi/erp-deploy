import importlib.util
import sys
import types
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = APP_ROOT / "orderlift_crm" / "party_propagation.py"


class Meta:
    def get_field(self, fieldname):
        return True


class Doc(dict):
    def __init__(self, doctype, name, **values):
        super().__init__(values)
        self.doctype = doctype
        self.name = name
        self.meta = Meta()
        self.save_count = 0

    def __getattr__(self, key):
        return self.get(key)

    def __setattr__(self, key, value):
        if key in {"doctype", "name", "meta", "save_count"}:
            object.__setattr__(self, key, value)
        else:
            self[key] = value

    def set(self, fieldname, value):
        self[fieldname] = value

    def append(self, fieldname, value):
        self.setdefault(fieldname, []).append(Doc("Child", "new-child", **value))

    def save(self, **kwargs):
        self.save_count += 1
        return self

    def as_dict(self):
        return dict(self)


class DbStub:
    def __init__(self, docs):
        self.docs = docs

    def exists(self, doctype, name):
        if doctype == "DocType":
            return name in {"Sales Person", "CRM Segment Assignment"}
        return (doctype, name) in self.docs

    def has_column(self, doctype, fieldname):
        return doctype == "Sales Person" and fieldname in {"user", "enabled"}

    def get_value(self, doctype, name_or_filters=None, fieldname=None, *args, **kwargs):
        if doctype == "Sales Person" and isinstance(name_or_filters, dict):
            if name_or_filters.get("user") == "owner@example.com" and name_or_filters.get("enabled") == 1:
                return "Sales Person A"
            return ""
        if doctype == "Address" and isinstance(name_or_filters, dict):
            names = name_or_filters.get("name", [None, []])[1]
            for name in names:
                doc = self.docs.get(("Address", name))
                if not doc or doc.get("disabled"):
                    continue
                if name_or_filters.get("is_primary_address") and not doc.get("is_primary_address"):
                    continue
                if name_or_filters.get("is_shipping_address") and not doc.get("is_shipping_address"):
                    continue
                return doc.get(fieldname) if fieldname != "name" else name
            return ""
        doc = self.docs.get((doctype, name_or_filters))
        return doc.get(fieldname) if doc else ""


def load_module():
    docs = {
        ("User", "owner@example.com"): Doc("User", "owner@example.com"),
        (
            "Customer",
            "CUST-1",
        ): Doc(
            "Customer",
            "CUST-1",
            customer_name="Customer One",
            tax_id="ICE-001",
            customer_primary_address="ADDR-BILL",
            primary_address="Formatted text, not an Address name",
            customer_primary_contact="CONTACT-1",
            language="en",
            custom_crm_segments=[],
            sales_team=[],
            custom_general_email="general@example.com",
            custom_general_mobile="+212611111111",
            custom_general_phone="0522000000",
            custom_general_whatsapp="+212622222222",
        ),
        ("Contact", "CONTACT-1"): Doc(
            "Contact",
            "CONTACT-1",
            links=[Doc("Dynamic Link", "link-1", link_doctype="Lead", link_name="LEAD-1")],
        ),
        ("Address", "ADDR-BILL"): Doc(
            "Address",
            "ADDR-BILL",
            address_line1="Billing street",
            disabled=0,
            is_primary_address=1,
            links=[Doc("Dynamic Link", "link-2", link_doctype="Lead", link_name="LEAD-1")],
        ),
        ("Address", "ADDR-SHIP"): Doc(
            "Address",
            "ADDR-SHIP",
            address_line1="Shipping street",
            disabled=0,
            links=[],
        ),
    }
    frappe = types.ModuleType("frappe")
    frappe.db = DbStub(docs)
    frappe.get_doc = lambda doctype, name: docs[(doctype, name)]

    def get_all(doctype, filters=None, fields=None, pluck=None, **kwargs):
        if doctype == "CRM Segment Assignment":
            return [Doc("CRM Segment Assignment", "SEG-1", business_type="Distribution", segment="Grossiste", is_primary=1)]
        if doctype == "Dynamic Link" and filters.get("parenttype") == "Contact":
            return ["CONTACT-1"] if pluck == "parent" else []
        if doctype == "Dynamic Link" and filters.get("parenttype") == "Address":
            return ["ADDR-BILL"] if pluck == "parent" else []
        return []

    frappe.get_all = get_all

    contact_module = types.ModuleType("frappe.contacts.doctype.contact.contact")
    contact_module.get_default_contact = lambda doctype, name: "CONTACT-1"
    contact_module.get_contact_details = lambda name: {
        "contact_display": "Contact One",
        "contact_email": "contact@example.com",
        "contact_mobile": "+212600000000",
        "contact_phone": "",
    }
    address_module = types.ModuleType("frappe.contacts.doctype.address.address")
    address_module.get_default_address = lambda doctype, name: "ADDR-BILL"
    address_module.get_address_display = lambda address: address.get("address_line1") or ""
    party_module = types.ModuleType("erpnext.accounts.party")
    party_module.get_party_shipping_address = lambda doctype, name: "ADDR-SHIP"

    dependencies = {
        "frappe": frappe,
        "frappe.contacts.doctype.contact.contact": contact_module,
        "frappe.contacts.doctype.address.address": address_module,
        "erpnext.accounts.party": party_module,
    }
    previous = {name: sys.modules.get(name) for name in dependencies}
    sys.modules.update(dependencies)
    try:
        spec = importlib.util.spec_from_file_location("party_propagation_test", MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
    return module, frappe, docs, dependencies


class TestPartyPropagation(unittest.TestCase):
    def setUp(self):
        self.module, self.frappe, self.docs, self.dependencies = load_module()
        self.previous = {name: sys.modules.get(name) for name in self.dependencies}
        sys.modules.update(self.dependencies)

    def tearDown(self):
        for name, value in self.previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value

    def test_customer_context_uses_link_field_and_separate_shipping_address(self):
        context = self.module.resolve_party_context("Customer", "CUST-1")

        self.assertEqual(context["billing_address_name"], "ADDR-BILL")
        self.assertEqual(context["billing_address_display"], "Billing street")
        self.assertEqual(context["shipping_address_name"], "ADDR-SHIP")
        self.assertEqual(context["shipping_address_display"], "Shipping street")
        self.assertEqual(context["contact_name"], "CONTACT-1")
        self.assertEqual(context["email"], "contact@example.com")
        self.assertEqual(context["general_email"], "general@example.com")
        self.assertEqual(context["crm_segment"], "Grossiste")
        self.assertEqual(context["tax_id"], "ICE-001")

    def test_party_general_communication_is_fallback_without_contact(self):
        self.docs[("Customer", "CUST-1")].customer_primary_contact = ""
        self.frappe.get_all = lambda doctype, filters=None, fields=None, pluck=None, **kwargs: []
        sys.modules["frappe.contacts.doctype.contact.contact"].get_default_contact = lambda doctype, name: ""

        context = self.module.resolve_party_context("Customer", "CUST-1")

        self.assertEqual(context["contact_name"], "")
        self.assertEqual(context["email"], "general@example.com")
        self.assertEqual(context["mobile"], "+212611111111")
        self.assertEqual(context["phone"], "0522000000")

    def test_quotation_receives_distinct_billing_and_shipping_snapshots(self):
        quotation = Doc("Quotation", "new-quotation")
        context = self.module.resolve_party_context("Customer", "CUST-1")

        self.module.apply_party_context_to_quotation(quotation, context)

        self.assertEqual(quotation.customer_address, "ADDR-BILL")
        self.assertEqual(quotation.address_display, "Billing street")
        self.assertEqual(quotation.shipping_address_name, "ADDR-SHIP")
        self.assertEqual(quotation.shipping_address, "Shipping street")
        self.assertEqual(quotation.custom_customer_tax_id, "ICE-001")

    def test_direct_sales_order_receives_customer_tax_id(self):
        sales_order = Doc("Sales Order", "new-sales-order", customer="CUST-1", tax_id="")

        self.module.apply_sales_order_party_context(sales_order)

        self.assertEqual(sales_order.tax_id, "ICE-001")

    def test_sales_invoice_receives_customer_tax_id_when_source_order_is_empty(self):
        self.docs[("Sales Order", "SO-1")] = Doc(
            "Sales Order",
            "SO-1",
            customer="CUST-1",
            customer_name="Customer One",
            tax_id="",
            items=[],
        )
        invoice = Doc(
            "Sales Invoice",
            "new-sales-invoice",
            tax_id="",
            items=[Doc("Sales Invoice Item", "row-1", sales_order="SO-1")],
        )

        self.module.sync_downstream_sales_party_context(invoice)

        self.assertEqual(invoice.tax_id, "ICE-001")
        self.assertEqual(invoice.custom_customer_tax_id, "ICE-001")

    def test_billing_address_falls_back_to_linked_party_address(self):
        sys.modules["frappe.contacts.doctype.address.address"].get_default_address = lambda doctype, name: ""

        context = self.module.resolve_party_context("Customer", "CUST-1")

        self.assertEqual(context["billing_address_name"], "ADDR-BILL")

    def test_customer_ownership_separates_user_and_sales_person(self):
        customer = Doc("Customer", "new-customer", sales_team=[])

        self.module.apply_customer_ownership(customer, "owner@example.com")

        self.assertEqual(customer.account_manager, "owner@example.com")
        self.assertEqual(customer.sales_team[0].sales_person, "Sales Person A")
        self.assertEqual(customer.sales_team[0].allocated_percentage, 100)

    def test_existing_customer_ownership_is_preserved(self):
        customer = Doc(
            "Customer",
            "CUST-2",
            account_manager="existing@example.com",
            sales_team=[Doc("Sales Team", "row-1", sales_person="Existing Person")],
        )

        self.module.apply_customer_ownership(customer, "owner@example.com")

        self.assertEqual(customer.account_manager, "existing@example.com")
        self.assertEqual(len(customer.sales_team), 1)
        self.assertEqual(customer.sales_team[0].sales_person, "Existing Person")

    def test_link_propagation_reuses_parent_documents_idempotently(self):
        self.module.link_party_contacts_and_addresses("Lead", "LEAD-1", "Customer", "CUST-1")
        self.module.link_party_contacts_and_addresses("Lead", "LEAD-1", "Customer", "CUST-1")

        contact_links = self.docs[("Contact", "CONTACT-1")].links
        address_links = self.docs[("Address", "ADDR-BILL")].links
        self.assertEqual(sum(row.link_doctype == "Customer" for row in contact_links), 1)
        self.assertEqual(sum(row.link_doctype == "Customer" for row in address_links), 1)

    def test_first_customer_address_is_selected_without_replacing_existing_primary(self):
        customer = self.docs[("Customer", "CUST-1")]
        customer.customer_primary_address = ""
        address = self.docs[("Address", "ADDR-BILL")]
        address.links.append(Doc("Dynamic Link", "link-3", link_doctype="Customer", link_name="CUST-1"))

        self.module.set_first_customer_address(address)
        self.module.set_first_customer_address(self.docs[("Address", "ADDR-SHIP")])

        self.assertEqual(customer.customer_primary_address, "ADDR-BILL")
        self.assertEqual(customer.save_count, 1)

    def test_conversion_hooks_and_address_refresh_are_wired(self):
        pipeline = (APP_ROOT / "orderlift_crm" / "api" / "pipeline.py").read_text()
        hooks = (APP_ROOT / "hooks.py").read_text()
        address_js = (APP_ROOT / "public" / "js" / "address_customer_refresh_20260723a.js").read_text()

        for token in [
            "_set_customer_lineage",
            "apply_customer_ownership",
            "link_party_contacts_and_addresses",
            "_apply_linked_customer_defaults",
            "apply_party_context_to_quotation(target, context, overwrite=True)",
        ]:
            self.assertIn(token, pipeline)
        self.assertIn('"after_insert": "orderlift.orderlift_crm.party_propagation.set_first_customer_address"', hooks)
        self.assertIn('"Address": "public/js/address_customer_refresh_20260723a.js"', hooks)
        self.assertIn('frappe.model.clear_doc("Customer", customer)', address_js)
        self.assertIn("cur_frm.reload_doc()", address_js)


if __name__ == "__main__":
    unittest.main()
