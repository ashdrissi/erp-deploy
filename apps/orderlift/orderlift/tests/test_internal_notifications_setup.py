from pathlib import Path
import unittest

from orderlift.notification_i18n import build_multilingual_text, select_multilingual_text


APP_ROOT = Path(__file__).resolve().parents[1]


class TestInternalNotificationsSetup(unittest.TestCase):
    def test_notification_seed_is_wired_after_migrate(self):
        hooks = (APP_ROOT / "hooks.py").read_text()

        self.assertIn("orderlift.scripts.setup_internal_notifications.after_migrate", hooks)

    def test_notification_log_language_hook_is_wired(self):
        hooks = (APP_ROOT / "hooks.py").read_text()

        self.assertIn('"Notification Log"', hooks)
        self.assertIn("orderlift.notification_i18n.apply_user_language_to_notification_log", hooks)

    def test_notification_pack_is_internal_system_only(self):
        script = (APP_ROOT / "scripts" / "setup_internal_notifications.py").read_text()

        self.assertIn('SYSTEM_CHANNEL = "System Notification"', script)
        self.assertIn("doc.enabled = 1", script)
        self.assertIn("doc.send_system_notification = 1", script)
        self.assertNotIn('channel = "Email"', script)
        self.assertNotIn("receiver_by_document_field\": \"customer", script)
        self.assertNotIn("receiver_by_document_field\": \"contact", script)

    def test_notification_pack_stores_french_and_english_templates(self):
        script = (APP_ROOT / "scripts" / "setup_internal_notifications.py").read_text()

        self.assertIn("build_multilingual_text", script)
        self.assertIn('"subject_en"', script)
        self.assertIn('"message_en"', script)

    def test_notification_language_selector_uses_user_language(self):
        value = build_multilingual_text("Bonjour", "Hello")

        self.assertEqual(select_multilingual_text(value, "fr"), "Bonjour")
        self.assertEqual(select_multilingual_text(value, "fr-FR"), "Bonjour")
        self.assertEqual(select_multilingual_text(value, "en"), "Hello")
        self.assertEqual(select_multilingual_text(value, None), "Hello")

    def test_notification_pack_covers_core_operational_areas(self):
        script = (APP_ROOT / "scripts" / "setup_internal_notifications.py").read_text()

        for doctype in [
            "Opportunity",
            "Quotation",
            "Sales Order",
            "Sales Invoice",
            "Payment Entry",
            "Bin",
            "Material Request",
            "Purchase Receipt",
            "Stock Entry",
            "Delivery Note",
            "SAV Ticket",
            "Project",
            "Forecast Load Plan",
            "Sales Commission",
        ]:
            self.assertIn(f'"doctype": "{doctype}"', script)

    def test_low_stock_notification_uses_reorder_threshold(self):
        script = (APP_ROOT / "scripts" / "setup_internal_notifications.py").read_text()

        self.assertIn("Orderlift - Low Stock Reorder Alert", script)
        self.assertIn('"doctype": "Bin"', script)
        self.assertIn('"value_changed": "actual_qty"', script)
        self.assertIn("Item Reorder", script)
        self.assertIn("warehouse_reorder_level", script)


if __name__ == "__main__":
    unittest.main()
