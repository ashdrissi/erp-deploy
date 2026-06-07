import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value, *args, **kwargs: value
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.throw = lambda message: (_ for _ in ()).throw(ValueError(message))
frappe_stub.db = types.SimpleNamespace()
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(float(value or 0))
utils_stub.flt = lambda value=0: float(value or 0)
utils_stub.now_datetime = lambda: "2026-01-01 00:00:00"
utils_stub.nowdate = lambda: "2026-01-01"
sys.modules["frappe.utils"] = utils_stub


from orderlift.scripts import import_b2b_opportunities


class TestImportB2BOpportunities(unittest.TestCase):
    def test_distribution_status_mapping_uses_internal_prefixed_stage(self):
        self.assertEqual(
            import_b2b_opportunities.map_sales_stage("5. Devis Envoyé", "Distribution"),
            "Distribution - 5. Devis Envoyé",
        )
        self.assertEqual(
            import_b2b_opportunities.map_sales_stage("payment remain + marchendise livre", "Distribution"),
            "Distribution - 9. Avance payée",
        )

    def test_installation_status_mapping_uses_installation_pipeline_stage(self):
        self.assertEqual(
            import_b2b_opportunities.map_sales_stage("2. Prise de mesure en cours", "installation"),
            "2. Prise de mesure en cours",
        )
        self.assertEqual(
            import_b2b_opportunities.map_sales_stage("9. Avance payée", "installation"),
            "8. Avance 40% payée",
        )

    def test_confirmed_statuses_create_customers(self):
        self.assertTrue(import_b2b_opportunities.is_confirmed({"Projet Situation": "9. Avance payée"}))
        self.assertTrue(import_b2b_opportunities.is_confirmed({"Projet Situation": "13. Marchandise livrée"}))
        self.assertFalse(import_b2b_opportunities.is_confirmed({"Projet Situation": "5. Devis Envoyé"}))

    def test_title_does_not_include_excel_reference(self):
        title = import_b2b_opportunities.build_title(
            {"Réf Devis/Projet": "4-12.25", "Nom projet": "Batiments R+7 Marrakech", "Client / Societe": "Client A", "Ville/Site": "Casablanca"}
        )
        self.assertEqual(title, "Batiments R+7 Marrakech")
        self.assertNotIn("4-12.25", title)

    def test_title_falls_back_to_client_city_without_project_name(self):
        title = import_b2b_opportunities.build_title(
            {"Réf Devis/Projet": "4-12.25", "Client / Societe": "Client A", "Ville/Site": "Casablanca"}
        )
        self.assertEqual(title, "Client A - Casablanca")

    def test_business_type_normalization_supports_file_values(self):
        self.assertEqual(import_b2b_opportunities.normalize_business_type("distribution"), "Distribution")
        self.assertEqual(import_b2b_opportunities.normalize_business_type("installation"), "Installation")
        self.assertEqual(import_b2b_opportunities.normalize_business_type(""), "")

    def test_converted_distribution_downstream_status_mapping(self):
        self.assertEqual(
            import_b2b_opportunities.sales_order_status_for_row({"Projet Situation": "13'. 1ère partie livrée"}),
            "Orderlift Maroc Distribution - Delivering",
        )
        self.assertEqual(
            import_b2b_opportunities.sales_order_status_for_row({"Projet Situation": "payment remain + marchendise livre"}),
            "Orderlift Maroc Distribution - Final Payment",
        )
        self.assertEqual(
            import_b2b_opportunities.project_status_for_row({"Projet Situation": "13. Marchandise livrée"}),
            "11. Marchandise livréeau client",
        )

    def test_delivery_date_never_precedes_transaction_date(self):
        self.assertEqual(
            import_b2b_opportunities._safe_delivery_date({"Date de livraison": "2026-01-01"}, "2026-01-05"),
            "2026-01-05",
        )
        self.assertEqual(
            import_b2b_opportunities._safe_delivery_date({"Date de livraison": "2026-01-10"}, "2026-01-05"),
            "2026-01-10",
        )


if __name__ == "__main__":
    unittest.main()
