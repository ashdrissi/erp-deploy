import importlib.util
import sys
import types
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = APP_ROOT / "customize_form_guard.py"


class Row(dict):
    def __getattr__(self, key):
        return self.get(key)


class FakeCustomizeForm(dict):
    def __init__(self, doc_type="Lead", fields=None):
        super().__init__(fields=fields or [])
        self.doc_type = doc_type


def load_guard(*, user="ashdrissi@gmail.com", field_owner="Administrator"):
    custom_field = Row(name="Lead-custom_partner_campaign", owner=field_owner)
    standard = Row(fieldname="utm_analytics_section", is_custom_field=0, name="Lead-utm_analytics_section")
    custom = Row(
        fieldname="custom_partner_campaign",
        is_custom_field=1,
        is_system_generated=0,
        name=custom_field.name,
    )

    class Meta:
        def get(self, key, filters=None):
            if key != "fields":
                return []
            if filters:
                return [row for row in (standard, custom) if row.fieldname == filters.get("fieldname")]
            return [standard, custom]

    deleted = []
    frappe = types.ModuleType("frappe")
    frappe.session = types.SimpleNamespace(user=user)
    frappe.get_meta = lambda doctype: Meta()
    frappe.get_doc = lambda doctype, name: custom_field
    frappe.delete_doc = lambda doctype, name: deleted.append((doctype, name))

    customize_module = types.ModuleType("frappe.custom.doctype.customize_form.customize_form")
    customize_module.CustomizeForm = FakeCustomizeForm
    customize_module.is_standard_or_system_generated_field = (
        lambda df: not df.get("is_custom_field") or df.get("is_system_generated")
    )
    dependencies = {
        "frappe": frappe,
        "frappe.custom.doctype.customize_form.customize_form": customize_module,
    }
    previous = {name: sys.modules.get(name) for name in dependencies}
    sys.modules.update(dependencies)
    try:
        spec = importlib.util.spec_from_file_location("customize_form_guard_test", MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
    return module, deleted, standard


class TestCustomizeFormGuard(unittest.TestCase):
    def test_non_administrator_preserves_omitted_administrator_field(self):
        module, deleted, standard = load_guard()
        doc = module.OrderliftCustomizeForm(fields=[standard])

        doc.delete_custom_fields()

        self.assertEqual(deleted, [])

    def test_non_administrator_can_remove_own_custom_field(self):
        module, deleted, standard = load_guard(field_owner="ashdrissi@gmail.com")
        doc = module.OrderliftCustomizeForm(fields=[standard])

        doc.delete_custom_fields()

        self.assertEqual(deleted, [("Custom Field", "Lead-custom_partner_campaign")])

    def test_administrator_retains_native_delete_behavior(self):
        module, deleted, standard = load_guard(user="Administrator")
        doc = module.OrderliftCustomizeForm(fields=[standard])

        doc.delete_custom_fields()

        self.assertEqual(deleted, [("Custom Field", "Lead-custom_partner_campaign")])

    def test_hook_registers_customize_form_override(self):
        hooks = (APP_ROOT / "hooks.py").read_text()

        self.assertIn('"Customize Form": "orderlift.customize_form_guard.OrderliftCustomizeForm"', hooks)


if __name__ == "__main__":
    unittest.main()
