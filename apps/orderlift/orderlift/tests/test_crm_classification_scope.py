import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda message, *args, **kwargs: message
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(value or 0)
sys.modules["frappe.utils"] = utils_stub


from orderlift.orderlift_crm import classification


class TestCrmClassificationScope(unittest.TestCase):
    def setUp(self):
        self.original_frappe = classification.frappe
        self.fake_db = _FakeDB()
        classification.frappe = types.SimpleNamespace(
            db=self.fake_db,
            get_meta=lambda doctype: _FakeMeta({
                "Opportunity": {"custom_crm_business_type", "custom_crm_segment", "company"},
                "Quotation": {"custom_crm_business_type", "custom_crm_segment", "company"},
            }.get(doctype, set())),
            get_all=lambda *args, **kwargs: [],
            throw=lambda message: (_ for _ in ()).throw(ValueError(message)),
        )

    def tearDown(self):
        classification.frappe = self.original_frappe

    def test_quotation_rejects_opportunity_from_another_company(self):
        self.fake_db.values[("Opportunity", "OPP-DIST")] = {
            "company": "Orderlift Maroc Distribution",
            "custom_crm_business_type": "Distribution",
            "custom_crm_segment": "Installateur",
        }
        quotation = _FakeDoc(
            "Quotation",
            company="Orderlift Maroc Installation",
            opportunity="OPP-DIST",
        )

        with self.assertRaisesRegex(ValueError, "belongs to company Orderlift Maroc Distribution"):
            classification.sync_quotation_crm_classification(quotation)

        self.assertEqual(quotation.custom_crm_business_type, "")
        self.assertEqual(quotation.custom_crm_segment, "")

    def test_quotation_accepts_opportunity_from_same_company(self):
        self.fake_db.values[("Opportunity", "OPP-INST")] = {
            "company": "Orderlift Maroc Installation",
            "custom_crm_business_type": "Installation",
            "custom_crm_segment": "Installateur",
        }
        quotation = _FakeDoc(
            "Quotation",
            company="Orderlift Maroc Installation",
            opportunity="OPP-INST",
        )

        classification.sync_quotation_crm_classification(quotation)

        self.assertEqual(quotation.custom_crm_business_type, "Installation")
        self.assertEqual(quotation.custom_crm_segment, "Installateur")


class _FakeDB:
    def __init__(self):
        self.values = {}

    def exists(self, doctype, name):
        return (doctype, name) in self.values

    def get_value(self, doctype, name, fields, as_dict=False):
        values = self.values.get((doctype, name), {})
        if isinstance(fields, str):
            return values.get(fields)
        result = {field: values.get(field, "") for field in fields}
        return result if as_dict else [result.get(field) for field in fields]


class _FakeDoc:
    def __init__(self, doctype, **values):
        self.doctype = doctype
        self.meta = _FakeMeta({"custom_crm_business_type", "custom_crm_segment", "company", "opportunity"})
        self.company = ""
        self.opportunity = ""
        self.custom_crm_business_type = ""
        self.custom_crm_segment = ""
        for key, value in values.items():
            setattr(self, key, value)

    def get(self, fieldname):
        return getattr(self, fieldname, "")

    def set(self, fieldname, value):
        setattr(self, fieldname, value)


class _FakeMeta:
    def __init__(self, fields):
        self.fields = set(fields)

    def get_field(self, fieldname):
        return fieldname if fieldname in self.fields else None


if __name__ == "__main__":
    unittest.main()
