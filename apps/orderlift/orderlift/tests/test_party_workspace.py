import importlib.util
import sys
import types
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = APP_ROOT / "orderlift_crm" / "party_management.py"


class Meta:
    def get_field(self, fieldname):
        return fieldname != "disabled"


class AttrDict(dict):
    __getattr__ = dict.get


class PartyDoc(AttrDict):
    def __init__(self, doctype, name=None, **values):
        super().__init__(values)
        self.doctype = doctype
        self.name = name
        self.meta = Meta()
        self.flags = types.SimpleNamespace()

    def is_new(self):
        return not bool(self.name)


class DuplicatePartyError(Exception):
    pass


def load_module():
    frappe = types.ModuleType("frappe")
    frappe._ = lambda value, *args, **kwargs: value
    frappe.whitelist = lambda *args, **kwargs: (lambda fn: fn) if args == () else args[0]
    frappe.get_meta = lambda doctype: Meta()
    frappe.db = types.SimpleNamespace(
        exists=lambda *args, **kwargs: True,
        get_value=lambda *args, **kwargs: None,
    )
    frappe_utils = types.ModuleType("frappe.utils")
    frappe_utils.now_datetime = lambda: "2026-08-12 00:00:00"

    def get_all(doctype, filters=None, fields=None, pluck=None, **kwargs):
        if doctype == "Dynamic Link":
            return ["CONTACT-1"] if pluck == "parent" else []
        if doctype == "Contact":
            assert filters == {"name": ["in", ["CONTACT-1"]]}
            return [
                {
                    "name": "CONTACT-1",
                    "first_name": "Passive Contact",
                    "status": "Passive",
                }
            ]
        return []

    frappe.get_all = get_all
    dependencies = {
        "frappe": frappe,
        "frappe.utils": frappe_utils,
        "orderlift.menu_access": types.SimpleNamespace(get_allowed_companies=lambda user=None: []),
        "orderlift.role_capabilities": types.SimpleNamespace(
            CAPABILITY_PARTY_COMPANY_ACCESS_APPROVAL="Party Company Access Approval",
            user_has_capability=lambda *args, **kwargs: False,
        ),
    }
    previous = {name: sys.modules.get(name) for name in dependencies}
    sys.modules.update(dependencies)
    try:
        spec = importlib.util.spec_from_file_location("party_management_test", MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
    return module


class TestPartyWorkspace(unittest.TestCase):
    def test_linked_contacts_include_passive_contacts(self):
        module = load_module()

        contacts = module._linked_contacts("Prospect", "PROSPECT-1")

        self.assertEqual(contacts[0]["status"], "Passive")

    def test_customer_normalized_duplicate_name_is_blocked(self):
        module = load_module()
        module.frappe.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(DuplicatePartyError(message))
        module.frappe.has_permission = lambda *args, **kwargs: True
        module.frappe.get_all = lambda doctype, **kwargs: (
            [AttrDict(name="Gerivall", customer_name="Gerivall", custom_company="Orderlift")]
            if doctype == "Customer"
            else []
        )

        with self.assertRaisesRegex(DuplicatePartyError, "Gerivall"):
            module._validate_unique_party_name(PartyDoc("Customer", customer_name="  GERIVALL  "))

    def test_supplier_normalized_duplicate_name_is_blocked(self):
        module = load_module()
        module.frappe.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(DuplicatePartyError(message))
        module.frappe.has_permission = lambda *args, **kwargs: True
        module.frappe.get_all = lambda doctype, **kwargs: (
            [AttrDict(name="SUP-GERIVALL", supplier_name="Gerivall", custom_company="Orderlift")]
            if doctype == "Supplier"
            else []
        )

        with self.assertRaisesRegex(DuplicatePartyError, "SUP-GERIVALL"):
            module._validate_unique_party_name(PartyDoc("Supplier", supplier_name="Gerivall"))

    def test_customer_and_supplier_names_use_separate_duplicate_domains(self):
        module = load_module()
        module.frappe.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(DuplicatePartyError(message))
        module.frappe.has_permission = lambda *args, **kwargs: True
        module.frappe.get_all = lambda doctype, **kwargs: (
            [AttrDict(name="Gerivall", customer_name="Gerivall", custom_company="Orderlift")]
            if doctype == "Customer"
            else []
        )

        module._validate_unique_party_name(PartyDoc("Supplier", supplier_name="Gerivall"))

    def test_existing_party_does_not_match_itself(self):
        module = load_module()
        module.frappe.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(DuplicatePartyError(message))
        module.frappe.has_permission = lambda *args, **kwargs: True
        module.frappe.get_all = lambda doctype, **kwargs: (
            [AttrDict(name="Gerivall", customer_name="Gerivall", custom_company="Orderlift")]
            if doctype == "Customer"
            else []
        )

        module._validate_unique_party_name(PartyDoc("Customer", name="Gerivall", customer_name="Gerivall"))

    def test_unchanged_existing_duplicate_name_remains_editable(self):
        module = load_module()
        module.frappe.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(DuplicatePartyError(message))
        module.frappe.has_permission = lambda *args, **kwargs: True
        module.frappe.db.get_value = lambda *args, **kwargs: AttrDict(customer_name="Gerivall")
        module.frappe.get_all = lambda doctype, **kwargs: [
            AttrDict(name="Gerivall", customer_name="Gerivall", custom_company="Orderlift")
        ]

        module._validate_unique_party_name(
            PartyDoc("Customer", name="Gerivall - 1", customer_name="Gerivall")
        )


if __name__ == "__main__":
    unittest.main()
