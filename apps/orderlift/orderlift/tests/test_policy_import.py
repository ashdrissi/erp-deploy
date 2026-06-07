import sys
import types
import unittest


class AttrDict(dict):
    def __getattr__(self, key):
        return self.get(key)

    def __setattr__(self, key, value):
        self[key] = value


class FakeField:
    def __init__(self, fieldname, fieldtype="Data"):
        self.fieldname = fieldname
        self.fieldtype = fieldtype


class FakeMeta:
    def __init__(self, fields):
        self.fields = [FakeField(fieldname, fieldtype) for fieldname, fieldtype in fields]

    def has_field(self, fieldname):
        return any(field.fieldname == fieldname for field in self.fields)

    def get_field(self, fieldname):
        return next((field for field in self.fields if field.fieldname == fieldname), None)


POLICY_META = FakeMeta(
    [
        ("policy_name", "Data"),
        ("company", "Link"),
        ("is_active", "Check"),
        ("is_default", "Check"),
        ("notes", "Small Text"),
        ("customs_rules", "Table"),
    ]
)
CUSTOMS_RULE_META = FakeMeta(
    [
        ("tariff_number", "Data"),
        ("material", "Data"),
        ("value_per_kg", "Float"),
        ("rate_percent", "Percent"),
        ("is_active", "Check"),
    ]
)
META_BY_DOCTYPE = {
    "Pricing Customs Policy": POLICY_META,
    "Pricing Customs Rule": CUSTOMS_RULE_META,
}
TABLE_CHILD_DOCTYPES = {"customs_rules": "Pricing Customs Rule"}


class FakeDoc(AttrDict):
    def __init__(self, doctype, **values):
        super().__init__(**values)
        self.doctype = doctype
        self.meta = META_BY_DOCTYPE[doctype]

    def get(self, fieldname, default=None):
        return super().get(fieldname, default)

    def set(self, fieldname, value):
        self[fieldname] = value

    def append(self, fieldname, value):
        child = FakeDoc(TABLE_CHILD_DOCTYPES[fieldname], **value)
        self.setdefault(fieldname, []).append(child)
        return child

    def insert(self, ignore_permissions=False):
        if self.doctype == "Pricing Customs Policy":
            self.name = f"PCPOL-{len(DB[self.doctype]) + 1:05d}"
            DB[self.doctype][self.name] = self
        return self


DB = {"Pricing Customs Policy": {}}

frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value: value
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.session = types.SimpleNamespace(user="demo@example.com")
frappe_stub.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(ValueError(message))
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(value or 0)
sys.modules["frappe.utils"] = utils_stub

sys.modules.pop("orderlift.orderlift_sales.utils.policy_import", None)
from orderlift.orderlift_sales.utils import policy_import


class TestPolicyImport(unittest.TestCase):
    def setUp(self):
        DB["Pricing Customs Policy"] = {
            "PCPOL-00001": FakeDoc(
                "Pricing Customs Policy",
                name="PCPOL-00001",
                policy_name="Source Customs",
                company="Orderlift Distribution",
                is_active=1,
                is_default=1,
                notes="Keep me",
                customs_rules=[
                    FakeDoc(
                        "Pricing Customs Rule",
                        tariff_number="8431310000",
                        material="ACIER",
                        value_per_kg=12,
                        rate_percent=25,
                        is_active=1,
                    )
                ],
            )
        }
        frappe_stub.get_meta = lambda doctype: META_BY_DOCTYPE[doctype]
        frappe_stub.new_doc = lambda doctype: FakeDoc(doctype)
        frappe_stub.get_doc = self._get_doc
        frappe_stub.db = types.SimpleNamespace(exists=self._exists)
        policy_import.company_field_for = lambda doctype: "company"
        policy_import.resolve_current_company = lambda **kwargs: "Orderlift Installation"
        policy_import.user_can_access_company = lambda company, user=None: company in {
            "Orderlift Distribution",
            "Orderlift Installation",
        }
        policy_import.get_allowed_companies = lambda user=None: [
            "Orderlift Distribution",
            "Orderlift Installation",
        ]

    def test_import_copies_policy_and_child_rows_to_target_company(self):
        result = policy_import.import_policy_from_existing(
            policy_doctype="Pricing Customs Policy",
            source_policy="PCPOL-00001",
            target_policy_name="Source Customs - Installation",
            target_company="Orderlift Installation",
        )

        self.assertEqual(result["policy_doctype"], "Pricing Customs Policy")
        self.assertEqual(result["target_company"], "Orderlift Installation")
        target = DB["Pricing Customs Policy"][result["policy"]]
        self.assertEqual(target.policy_name, "Source Customs - Installation")
        self.assertEqual(target.company, "Orderlift Installation")
        self.assertEqual(target.notes, "Keep me")
        self.assertEqual(len(target.customs_rules), 1)
        self.assertEqual(target.customs_rules[0].tariff_number, "8431310000")
        self.assertEqual(target.customs_rules[0].material, "ACIER")

    def test_import_rejects_same_target_company(self):
        with self.assertRaisesRegex(ValueError, "already belongs"):
            policy_import.import_policy_from_existing(
                policy_doctype="Pricing Customs Policy",
                source_policy="PCPOL-00001",
                target_policy_name="Source Customs Copy",
                target_company="Orderlift Distribution",
            )

    def _exists(self, doctype, name=None, *args, **kwargs):
        if isinstance(name, dict):
            if "policy_name" in name:
                return next(
                    (doc_name for doc_name, doc in DB.get(doctype, {}).items() if doc.policy_name == name["policy_name"]),
                    None,
                )
            return False
        return name in DB.get(doctype, {})

    def _get_doc(self, doctype, name):
        return DB[doctype][name]


if __name__ == "__main__":
    unittest.main()
