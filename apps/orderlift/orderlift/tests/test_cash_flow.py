import inspect
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value, *args, **kwargs: value
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn) if not args else args[0]
frappe_stub.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(Exception(message))
frappe_stub.PermissionError = PermissionError
frappe_stub.session = types.SimpleNamespace(user="finance@example.com")
frappe_stub.get_roles = lambda user=None: ["Finance User"]
frappe_stub.has_permission = lambda *args, **kwargs: True
sys.modules["frappe"] = frappe_stub

frappe_custom_stub = types.ModuleType("frappe.custom")
frappe_custom_doctype_stub = types.ModuleType("frappe.custom.doctype")
frappe_custom_field_pkg_stub = types.ModuleType("frappe.custom.doctype.custom_field")
frappe_custom_field_stub = types.ModuleType("frappe.custom.doctype.custom_field.custom_field")
frappe_custom_field_stub.create_custom_fields = lambda *args, **kwargs: None
sys.modules["frappe.custom"] = frappe_custom_stub
sys.modules["frappe.custom.doctype"] = frappe_custom_doctype_stub
sys.modules["frappe.custom.doctype.custom_field"] = frappe_custom_field_pkg_stub
sys.modules["frappe.custom.doctype.custom_field.custom_field"] = frappe_custom_field_stub

frappe_utils_stub = types.ModuleType("frappe.utils")
frappe_utils_stub.flt = lambda value, precision=None: round(float(value or 0), precision) if precision else float(value or 0)
frappe_utils_stub.cint = lambda value: int(value or 0)
sys.modules["frappe.utils"] = frappe_utils_stub

from orderlift.orderlift_finance import cash_flow, cash_flow_setup


def fixture_data():
    return {
        "company_currency": "MAD",
        "projects": [
            {
                "name": "PROJ-1",
                "project_name": "Tower One",
                "customer": "Customer A",
                "company": "Demo Company",
                "custom_project_status": "Execution",
                "project_type": "Installation",
            }
        ],
        "sales_orders": [
            {
                "name": "SO-1",
                "customer": "Customer A",
                "company": "Demo Company",
                "project": "PROJ-1",
                "currency": "USD",
                "conversion_rate": 10,
                "grand_total": 100,
                "base_grand_total": 1000,
                "net_total": 80,
                "base_net_total": 800,
                "transaction_date": "2026-01-01",
                "delivery_date": "2026-10-01",
                "status": "To Deliver and Bill",
            },
            {
                "name": "SO-2",
                "customer": "Customer B",
                "company": "Demo Company",
                "project": "",
                "currency": "MAD",
                "conversion_rate": 1,
                "grand_total": 500,
                "base_grand_total": 500,
                "net_total": 400,
                "base_net_total": 400,
                "transaction_date": "2026-02-01",
                "delivery_date": "2026-11-01",
                "status": "To Deliver and Bill",
            },
        ],
        "sales_order_items": [
            {"parent": "SO-1", "qty": 10, "source_landed_cost": 20},
            {"parent": "SO-2", "qty": 1, "source_landed_cost": 100},
        ],
        "sales_order_schedules": [
            {"parent": "SO-1", "name": "SCH-1", "due_date": "2026-09-01", "payment_amount": 100},
        ],
        "sales_invoices": [
            {
                "name": "SI-1", "project": "PROJ-1", "currency": "MAD", "conversion_rate": 1,
                "base_grand_total": 600, "grand_total": 600, "base_outstanding_amount": 100,
                "base_net_total": 500, "net_total": 500,
                "outstanding_amount": 100, "base_paid_amount": 100, "paid_amount": 100,
                "posting_date": "2026-03-01", "due_date": "2026-04-01",
            },
            {
                "name": "SI-2", "currency": "MAD", "conversion_rate": 1,
                "base_grand_total": 300, "grand_total": 300, "base_outstanding_amount": 0,
                "base_net_total": 250, "net_total": 250,
                "outstanding_amount": 0, "base_paid_amount": 300, "paid_amount": 300,
                "posting_date": "2026-03-10", "due_date": "2026-04-10",
            },
            {
                "name": "SI-ADV", "currency": "MAD", "conversion_rate": 1,
                "base_grand_total": 100, "grand_total": 100, "base_outstanding_amount": 0,
                "base_net_total": 80, "net_total": 80,
                "outstanding_amount": 0, "base_paid_amount": 100, "paid_amount": 100,
                "posting_date": "2026-03-15", "due_date": "2026-03-15",
                "custom_advance_sales_order": "SO-2", "custom_advance_payment_entry": "PE-ADV",
            },
        ],
        "sales_invoice_items": [
            {"parent": "SI-1", "sales_order": "SO-1", "project": "PROJ-1", "base_net_amount": 600},
            {"parent": "SI-2", "sales_order": "SO-2", "base_net_amount": 300},
            {"parent": "SI-ADV", "base_net_amount": 100},
        ],
        "purchase_orders": [
            {
                "name": "PO-1", "project": "PROJ-1", "currency": "MAD", "conversion_rate": 1,
                "base_grand_total": 500, "grand_total": 500, "transaction_date": "2026-02-01",
                "base_net_total": 450, "net_total": 450,
                "schedule_date": "2026-08-01", "status": "To Receive and Bill",
            }
        ],
        "purchase_order_items": [
            {"parent": "PO-1", "name": "POI-1", "project": "PROJ-1", "base_amount": 500},
        ],
        "purchase_order_schedules": [
            {"parent": "PO-1", "name": "PSCH-1", "due_date": "2026-07-01", "payment_amount": 500},
        ],
        "purchase_invoices": [
            {
                "name": "PI-1", "project": "PROJ-1", "currency": "MAD", "conversion_rate": 1,
                "base_grand_total": 400, "grand_total": 400, "base_outstanding_amount": 100,
                "base_net_total": 350, "net_total": 350,
                "outstanding_amount": 100, "base_paid_amount": 200, "paid_amount": 200,
                "posting_date": "2026-03-05", "due_date": "2026-04-05",
            },
            {
                "name": "PI-2", "currency": "MAD", "conversion_rate": 1,
                "base_grand_total": 100, "grand_total": 100, "base_outstanding_amount": 50,
                "base_net_total": 80, "net_total": 80,
                "outstanding_amount": 50, "base_paid_amount": 50, "paid_amount": 50,
                "posting_date": "2026-03-20", "due_date": "2026-04-20",
            },
            {
                "name": "PI-UNASSIGNED", "currency": "MAD", "conversion_rate": 1,
                "base_grand_total": 70, "grand_total": 70, "base_outstanding_amount": 70,
                "base_net_total": 60, "net_total": 60,
                "outstanding_amount": 70, "posting_date": "2026-03-25", "due_date": "2026-04-25",
            },
        ],
        "purchase_invoice_items": [
            {
                "parent": "PI-1", "project": "PROJ-1", "purchase_order": "PO-1",
                "po_detail": "POI-1", "base_net_amount": 400,
            },
            {"parent": "PI-2", "custom_sales_order": "SO-2", "base_net_amount": 100},
            {"parent": "PI-UNASSIGNED", "base_net_amount": 70},
        ],
        "payment_entries": [
            {
                "name": "PE-SO", "payment_type": "Receive", "posting_date": "2026-03-01",
                "base_paid_amount": 200, "base_received_amount": 220,
                "custom_source_document_currency": "USD",
            },
            {
                "name": "PE-SI", "payment_type": "Receive", "posting_date": "2026-03-10",
                "base_paid_amount": 300, "base_received_amount": 300,
            },
            {
                "name": "PE-ADV", "payment_type": "Receive", "posting_date": "2026-03-15",
                "base_paid_amount": 100, "base_received_amount": 100,
            },
            {
                "name": "PE-PI1", "payment_type": "Pay", "posting_date": "2026-03-06",
                "base_paid_amount": 210, "base_received_amount": 200,
            },
            {
                "name": "PE-PI2", "payment_type": "Pay", "posting_date": "2026-03-21",
                "base_paid_amount": 50, "base_received_amount": 50,
            },
        ],
        "payment_references": [
            {"parent": "PE-SO", "reference_doctype": "Sales Order", "reference_name": "SO-1", "allocated_amount": 20, "exchange_rate": 10},
            {"parent": "PE-SI", "reference_doctype": "Sales Invoice", "reference_name": "SI-2", "allocated_amount": 300, "exchange_rate": 1},
            {"parent": "PE-ADV", "reference_doctype": "Sales Order", "reference_name": "SO-2", "allocated_amount": 100, "exchange_rate": 1},
            {"parent": "PE-PI1", "reference_doctype": "Purchase Invoice", "reference_name": "PI-1", "allocated_amount": 200, "exchange_rate": 1},
            {"parent": "PE-PI2", "reference_doctype": "Purchase Invoice", "reference_name": "PI-2", "allocated_amount": 50, "exchange_rate": 1},
        ],
    }


class TestCashFlow(unittest.TestCase):
    def test_classification_never_duplicates_project_sales_order(self):
        contexts, quality = cash_flow.classify_sales_orders(
            fixture_data()["projects"], fixture_data()["sales_orders"]
        )
        self.assertEqual(set(contexts), {("Project", "PROJ-1"), ("Sales Order", "SO-2")})
        self.assertEqual(quality, [])

    def test_payment_direction_and_funding_gap(self):
        self.assertEqual(cash_flow.payment_direction("Receive"), ("inflow", 1))
        self.assertEqual(cash_flow.payment_direction("Pay"), ("outflow", -1))
        self.assertEqual(cash_flow.payment_direction("Internal Transfer"), ("", 0))
        self.assertEqual(
            cash_flow.funding_position(100, 200, 250, 150),
            {"forecast_net": -100.0, "funding_gap": 100.0},
        )

    def test_schedule_replacement_does_not_emit_replaced_amount(self):
        rows = cash_flow.replace_scheduled_amounts(
            [
                {"name": "A", "due_date": "2026-01-01", "amount": 300},
                {"name": "B", "due_date": "2026-02-01", "amount": 700},
            ],
            550,
        )
        self.assertEqual(rows, [{"name": "B", "due_date": "2026-02-01", "amount": 450.0}])

    def test_model_uses_bank_side_actuals_and_company_currency(self):
        model = cash_flow.build_cash_flow_model(fixture_data(), company="Demo Company")
        project = model["contexts"][("Project", "PROJ-1")]
        standalone = model["contexts"][("Sales Order", "SO-2")]

        self.assertEqual(project["ordered"], 1000)
        self.assertEqual(project["invoiced"], 600)
        self.assertEqual(project["collected"], 300)
        self.assertEqual(project["supplier_paid"], 200)
        self.assertEqual(project["net_cash"], 100)
        self.assertEqual(project["actual_cost"], 400)
        self.assertEqual(project["committed_inflow"], 300)
        self.assertEqual(project["committed_outflow"], 200)
        self.assertEqual(project["forecast_outflow"], 1500)
        self.assertEqual(project["funding_gap"], 1300)
        self.assertEqual(project["currency"], "MAD")
        self.assertEqual(project["source_currency"], "Mixed")
        self.assertEqual(project["company_currency"], "MAD")

        self.assertEqual(standalone["invoiced"], 400)
        self.assertEqual(standalone["collected"], 400)
        self.assertEqual(standalone["supplier_paid"], 50)
        self.assertEqual(standalone["committed_inflow"], 100)
        self.assertEqual(standalone["committed_outflow"], 50)
        self.assertEqual(standalone["forecast_outflow"], 0)

        quality_codes = {row["code"] for row in model["data_quality"]}
        self.assertIn("unassigned_invoice", quality_codes)
        self.assertIn("partially_unassigned_payment", quality_codes)
        self.assertFalse(any("account" in key.lower() for row in model["events"] for key in row))

    def test_profitability_separates_expected_actual_and_cash(self):
        model = cash_flow.build_cash_flow_model(fixture_data(), company="Demo Company")
        project = model["contexts"][("Project", "PROJ-1")]

        self.assertEqual(project["ordered_revenue_ht"], 800)
        self.assertEqual(project["ordered_revenue_ttc"], 1000)
        self.assertEqual(project["ordered_taxes"], 200)
        self.assertEqual(project["invoiced_revenue_ht"], 500)
        self.assertEqual(project["invoiced_revenue_ttc"], 600)
        self.assertEqual(project["baseline_cost"], 2000)
        self.assertEqual(project["actual_cost_ht"], 350)
        self.assertEqual(project["committed_cost"], 100)
        self.assertEqual(project["forecast_cost"], 1550)
        self.assertEqual(project["expected_cost"], 2000)
        self.assertEqual(project["expected_profit"], -1200)
        self.assertEqual(project["expected_profit_pct"], -150)
        self.assertEqual(project["actual_profit_to_date"], 150)
        self.assertEqual(project["actual_profit_pct"], 30)
        self.assertEqual(project["net_cash"], 100)
        self.assertNotEqual(project["net_cash"], project["expected_profit"])

    def test_payment_changes_cash_without_changing_profit(self):
        first = cash_flow.build_cash_flow_model(fixture_data(), company="Demo Company")["contexts"][("Project", "PROJ-1")]
        data = fixture_data()
        data["payment_entries"] = []
        data["payment_references"] = []
        second = cash_flow.build_cash_flow_model(data, company="Demo Company")["contexts"][("Project", "PROJ-1")]

        for field in (
            "expected_revenue_ht", "expected_cost", "expected_profit", "invoiced_revenue_ht",
            "actual_cost_ht", "actual_profit_to_date",
        ):
            self.assertEqual(first[field], second[field])
        self.assertNotEqual(first["net_cash"], second["net_cash"])

    def test_final_forecasts_remove_only_theoretical_revenue_and_cost(self):
        data = fixture_data()
        data["projects"][0]["custom_revenue_forecast_final"] = 1
        data["projects"][0]["custom_cost_forecast_final"] = 1
        model = cash_flow.build_cash_flow_model(data, company="Demo Company")
        project = model["contexts"][("Project", "PROJ-1")]

        self.assertEqual(project["remaining_revenue_ht"], 0)
        self.assertEqual(project["expected_revenue_ht"], 500)
        self.assertEqual(project["actual_cost_ht"], 350)
        self.assertEqual(project["committed_cost"], 100)
        self.assertEqual(project["forecast_cost"], 0)
        self.assertEqual(project["expected_cost"], 450)
        self.assertEqual(project["expected_profit"], 50)
        project_events = [row for row in model["events"] if row["context_name"] == "PROJ-1"]
        self.assertFalse(any(row["event_type"] == "Sales Order Residual Schedule" for row in project_events))
        self.assertFalse(any(row["event_type"] == "Uncovered Landed Cost" for row in project_events))
        self.assertTrue(any(row["event_type"] == "Sales Invoice Outstanding" for row in project_events))
        self.assertTrue(any(row["event_type"] == "Purchase Order Residual Schedule" for row in project_events))
        self.assertIn("revenue_closed_uninvoiced", {row["code"] for row in model["data_quality"]})

    def test_invoice_payment_is_not_counted_again_as_inline_paid(self):
        model = cash_flow.build_cash_flow_model(fixture_data(), company="Demo Company")
        standalone_events = [
            row for row in model["events"] if row["context_name"] == "SO-2" and row["layer"] == "actual"
        ]
        self.assertEqual(sum(row["signed_amount"] for row in standalone_events), 350)
        self.assertFalse(
            any(row["event_type"] == "Inline Invoice Payment" and row["reference_name"] in {"SI-2", "SI-ADV"} for row in standalone_events)
        )

    def test_partial_payment_entry_keeps_only_inline_paid_residual(self):
        data = fixture_data()
        payment = next(row for row in data["payment_entries"] if row["name"] == "PE-SI")
        payment["base_paid_amount"] = 100
        payment["base_received_amount"] = 100
        reference = next(row for row in data["payment_references"] if row["parent"] == "PE-SI")
        reference["allocated_amount"] = 100

        model = cash_flow.build_cash_flow_model(data, company="Demo Company")
        invoice_events = [
            row
            for row in model["events"]
            if row.get("source_reference_name") == "SI-2" or row.get("reference_name") == "SI-2"
        ]
        self.assertEqual(sum(row["amount"] for row in invoice_events if row["layer"] == "actual"), 300)
        inline = [row for row in invoice_events if row["event_type"] == "Inline Invoice Payment"]
        self.assertEqual([row["amount"] for row in inline], [200])

    def test_bank_remainder_is_unassigned_and_custom_source_amount_is_proportional(self):
        data = fixture_data()
        payment = next(row for row in data["payment_entries"] if row["name"] == "PE-SO")
        payment["custom_source_payment_amount"] = 22
        model = cash_flow.build_cash_flow_model(data, company="Demo Company")
        event = next(row for row in model["events"] if row.get("reference_name") == "PE-SO")
        self.assertEqual(event["amount"], 200)
        self.assertEqual(event["source_currency"], "USD")
        self.assertEqual(event["source_amount"], 20)
        issue = next(
            row
            for row in model["data_quality"]
            if row["code"] == "partially_unassigned_payment" and row["document_name"] == "PE-SO"
        )
        self.assertEqual(issue["amount"], 20)

    def test_negative_invoice_outstanding_reverses_cash_direction(self):
        data = fixture_data()
        data["sales_invoices"].append(
            {
                "name": "SI-RET", "project": "PROJ-1", "currency": "MAD", "conversion_rate": 1,
                "base_grand_total": -50, "grand_total": -50, "base_outstanding_amount": -20,
                "outstanding_amount": -20, "posting_date": "2026-03-30", "due_date": "2026-04-30",
                "is_return": 1,
            }
        )
        data["sales_invoice_items"].append(
            {"parent": "SI-RET", "sales_order": "SO-1", "project": "PROJ-1", "base_net_amount": -50}
        )
        data["purchase_invoices"].append(
            {
                "name": "PI-RET", "project": "PROJ-1", "currency": "MAD", "conversion_rate": 1,
                "base_grand_total": -30, "grand_total": -30, "base_outstanding_amount": -10,
                "outstanding_amount": -10, "posting_date": "2026-03-31", "due_date": "2026-05-01",
                "is_return": 1,
            }
        )
        data["purchase_invoice_items"].append(
            {"parent": "PI-RET", "project": "PROJ-1", "base_net_amount": -30}
        )

        model = cash_flow.build_cash_flow_model(data, company="Demo Company")
        sales_return = next(row for row in model["events"] if row["reference_name"] == "SI-RET")
        purchase_return = next(row for row in model["events"] if row["reference_name"] == "PI-RET")
        self.assertEqual((sales_return["direction"], sales_return["amount"]), ("outflow", 20))
        self.assertEqual((purchase_return["direction"], purchase_return["amount"]), ("inflow", 10))
        self.assertEqual(model["contexts"][("Project", "PROJ-1")]["actual_cost"], 370)

    def test_standalone_purchase_order_and_invoice_chain_remains_attributed(self):
        data = fixture_data()
        data["purchase_orders"].append(
            {
                "name": "PO-SO2", "project": "", "currency": "MAD", "conversion_rate": 1,
                "base_grand_total": 100, "grand_total": 100, "transaction_date": "2026-04-01",
                "schedule_date": "2026-06-01", "status": "To Receive and Bill",
            }
        )
        data["purchase_order_items"].append(
            {"parent": "PO-SO2", "name": "POI-SO2", "sales_order": "SO-2", "base_amount": 100}
        )
        data["purchase_order_schedules"].append(
            {"parent": "PO-SO2", "name": "PS-SO2", "due_date": "2026-06-01", "payment_amount": 100}
        )
        data["purchase_invoices"].append(
            {
                "name": "PI-SO2-PO", "currency": "MAD", "conversion_rate": 1,
                "base_grand_total": 30, "grand_total": 30, "base_outstanding_amount": 20,
                "outstanding_amount": 20, "posting_date": "2026-04-10", "due_date": "2026-05-10",
            }
        )
        data["purchase_invoice_items"].append(
            {
                "parent": "PI-SO2-PO", "po_detail": "POI-SO2", "base_net_amount": 30,
            }
        )

        model = cash_flow.build_cash_flow_model(data, company="Demo Company")
        standalone = model["contexts"][("Sales Order", "SO-2")]
        self.assertEqual(standalone["actual_cost"], 130)
        self.assertEqual(standalone["actual_cost_ht"], 110)
        self.assertEqual(standalone["committed_cost"], 70)
        self.assertEqual(standalone["expected_cost"], 180)
        self.assertTrue(
            any(
                row["context_name"] == "SO-2" and row["reference_name"] == "PO-SO2"
                for row in model["events"]
            )
        )

    def test_mixed_direct_and_po_invoice_rows_reduce_only_po_linked_commitment(self):
        data = fixture_data()
        data["projects"][0]["custom_cost_forecast_final"] = 1
        data["purchase_invoices"].append(
            {
                "name": "PI-MIX", "project": "PROJ-1", "currency": "MAD", "conversion_rate": 1,
                "base_grand_total": 100, "grand_total": 100, "base_net_total": 100,
                "net_total": 100, "base_outstanding_amount": 0, "outstanding_amount": 0,
                "posting_date": "2026-04-01", "due_date": "2026-04-01",
            }
        )
        data["purchase_invoice_items"].extend(
            [
                {
                    "parent": "PI-MIX", "project": "PROJ-1", "purchase_order": "PO-1",
                    "po_detail": "POI-1", "base_net_amount": 50,
                },
                {"parent": "PI-MIX", "project": "PROJ-1", "base_net_amount": 50},
            ]
        )

        project = cash_flow.build_cash_flow_model(data, company="Demo Company")["contexts"][("Project", "PROJ-1")]
        self.assertEqual(project["actual_cost_ht"], 450)
        self.assertEqual(project["committed_cost"], 50)
        self.assertEqual(project["expected_cost"], 500)

    def test_closed_po_keeps_only_posted_invoice_coverage_against_cash_forecast(self):
        data = fixture_data()
        data["purchase_orders"][0]["status"] = "Closed"
        model = cash_flow.build_cash_flow_model(data, company="Demo Company")
        project = model["contexts"][("Project", "PROJ-1")]
        uncovered = [
            row for row in model["events"]
            if row["context_name"] == "PROJ-1" and row["event_type"] == "Uncovered Landed Cost"
        ]
        self.assertEqual(project["committed_cost"], 0)
        self.assertEqual(project["forecast_cost"], 1650)
        self.assertEqual(sum(row["amount"] for row in uncovered), 1600)

    def test_direct_pi_accrual_coverage_excludes_po_linked_rows_without_double_replacement(self):
        coverage = cash_flow._direct_purchase_invoice_accrual_coverage(
            [{"name": "PI-MIX", "base_grand_total": 100}],
            [
                {"parent": "PI-MIX", "custom_sales_order": "SO-2", "base_net_amount": 50},
                {
                    "parent": "PI-MIX", "purchase_order": "PO-1", "po_detail": "POI-1",
                    "base_net_amount": 50,
                },
            ],
            {
                "PI-MIX": {
                    ("Sales Order", "SO-2"): 0.5,
                    ("Project", "PROJ-1"): 0.5,
                }
            },
            {"SO-2": ("Sales Order", "SO-2")},
            {"PROJ-1"},
            {"POI-1": ("Project", "PROJ-1")},
        )
        self.assertEqual(coverage[("Sales Order", "SO-2")], 50)
        self.assertNotIn(("Project", "PROJ-1"), coverage)

    def test_purchase_invoice_return_reverses_direct_procurement_accrual_coverage(self):
        data = fixture_data()
        data["purchase_invoices"].append(
            {
                "name": "PI-2-RETURN", "currency": "MAD", "conversion_rate": 1,
                "base_grand_total": -60, "grand_total": -60, "base_outstanding_amount": 0,
                "outstanding_amount": 0, "posting_date": "2026-03-30", "due_date": "2026-03-30",
                "is_return": 1, "return_against": "PI-2",
            }
        )
        data["purchase_invoice_items"].append(
            {
                "parent": "PI-2-RETURN", "custom_sales_order": "SO-2",
                "base_net_amount": -60,
            }
        )

        model = cash_flow.build_cash_flow_model(data, company="Demo Company")
        standalone = model["contexts"][("Sales Order", "SO-2")]
        uncovered = [
            row for row in model["events"]
            if row["context_name"] == "SO-2" and row["event_type"] == "Uncovered Landed Cost"
        ]

        self.assertEqual(standalone["actual_cost"], 40)
        self.assertEqual(sum(row["amount"] for row in uncovered), 60)

    def test_po_invoice_and_advance_overlap_is_conservative_and_explicit(self):
        data = fixture_data()
        data["payment_entries"].append(
            {
                "name": "PE-PO", "payment_type": "Pay", "posting_date": "2026-03-01",
                "base_paid_amount": 50, "base_received_amount": 50,
            }
        )
        data["payment_references"].append(
            {
                "parent": "PE-PO", "reference_doctype": "Purchase Order", "reference_name": "PO-1",
                "allocated_amount": 50, "exchange_rate": 1,
            }
        )
        model = cash_flow.build_cash_flow_model(data, company="Demo Company")
        residual = next(
            row for row in model["events"]
            if row["event_type"] == "Purchase Order Residual Schedule" and row["reference_name"] == "PO-1"
        )
        self.assertEqual(residual["amount"], 100)
        self.assertEqual(residual["confidence"], "Low")
        self.assertIn("ambiguous_po_replacement_overlap", {row["code"] for row in model["data_quality"]})

    def test_payment_schedule_uses_outstanding_and_keeps_unscheduled_residual(self):
        rows = cash_flow.replace_scheduled_amounts(
            [
                {
                    "name": "A", "due_date": "2026-01-01", "amount": 200,
                    "scheduled_amount": 500,
                }
            ],
            0,
            fallback_date="2026-02-01",
            fallback_amount=1000,
        )
        self.assertEqual(sum(row["amount"] for row in rows), 700)
        self.assertTrue(any(row.get("is_schedule_residual") for row in rows))
        quality = []
        cash_flow._validate_payment_schedule(
            [{"scheduled_amount": 500, "amount": 200}], 1000, "Sales Order", "SO-X", quality
        )
        self.assertEqual(quality[0]["code"], "payment_schedule_residual")

        events = cash_flow._residual_order_events(
            [
                {
                    "name": "SO-X", "status": "To Deliver and Bill", "currency": "MAD",
                    "conversion_rate": 1, "base_grand_total": 1000, "grand_total": 1000,
                    "delivery_date": "2026-02-01",
                }
            ],
            [
                {
                    "parent": "SO-X", "name": "S-X", "due_date": "2026-02-01",
                    "payment_amount": 1000, "outstanding": 300,
                }
            ],
            {"SO-X": ("Sales Order", "SO-X")},
            {("SO-X", ("Sales Order", "SO-X")): 500},
            {("SO-X", ("Sales Order", "SO-X")): 0},
            "MAD",
            direction="inflow",
        )
        self.assertEqual([row["amount"] for row in events], [300])

    def test_chronological_gap_captures_outflow_before_inflow(self):
        key = ("Project", "P")
        events = [
            cash_flow._event(
                key, layer="committed", direction="outflow", event_type="Cost", event_date="2026-01-02",
                amount=100, company_currency="MAD", source_amount=100, source_currency="MAD",
                reference_doctype="Purchase Invoice", reference_name="PI", confidence="High",
            ),
            cash_flow._event(
                key, layer="committed", direction="inflow", event_type="Receipt", event_date="2026-01-03",
                amount=100, company_currency="MAD", source_amount=100, source_currency="MAD",
                reference_doctype="Sales Invoice", reference_name="SI", confidence="High",
            ),
        ]
        bounds = {"from_date": "2026-01-01", "to_date": "2026-01-31", "interval": "week"}
        self.assertEqual(
            cash_flow.chronological_funding_position(events, bounds)["funding_gap"], 100
        )

    def test_portfolio_gap_uses_consolidated_event_path(self):
        a = ("Project", "A")
        b = ("Project", "B")
        events = [
            cash_flow._event(
                b, layer="actual", direction="inflow", event_type="Opening", event_date="2026-01-01",
                amount=100, company_currency="MAD", source_amount=100, source_currency="MAD",
                reference_doctype="Payment Entry", reference_name="OPEN", confidence="Actual",
            ),
            cash_flow._event(
                a, layer="committed", direction="outflow", event_type="A Cost", event_date="2026-01-02",
                amount=100, company_currency="MAD", source_amount=100, source_currency="MAD",
                reference_doctype="Purchase Invoice", reference_name="A-PI", confidence="High",
            ),
            cash_flow._event(
                a, layer="committed", direction="inflow", event_type="A Receipt", event_date="2026-01-03",
                amount=100, company_currency="MAD", source_amount=100, source_currency="MAD",
                reference_doctype="Sales Invoice", reference_name="A-SI", confidence="High",
            ),
            cash_flow._event(
                b, layer="committed", direction="outflow", event_type="B Cost", event_date="2026-01-04",
                amount=100, company_currency="MAD", source_amount=100, source_currency="MAD",
                reference_doctype="Purchase Invoice", reference_name="B-PI", confidence="High",
            ),
        ]
        rows = [{field: 0 for field in cash_flow.MONEY_FIELDS} for _ in range(2)]
        rows[0].update({"context_type": "Project", "funding_gap": 100, "risk_status": "Funding Gap"})
        rows[1].update({"context_type": "Project", "funding_gap": 0, "risk_status": "On Track"})
        bounds = {"from_date": "2026-01-02", "to_date": "2026-01-31", "interval": "week"}
        summary = cash_flow._summarize(rows, [], events=events, bounds=bounds)
        self.assertEqual(summary["funding_gap"], 0)

    def test_custom_horizon_applies_same_as_of_cutoff_to_kpis_and_buckets(self):
        with patch.object(cash_flow, "_authorize", return_value=("finance@example.com", "Demo Company")), patch.object(
            cash_flow, "_load_data", return_value=fixture_data()
        ):
            result = cash_flow.get_cash_flow_detail(
                "Project", "PROJ-1", from_date="2026-01-01", to_date="2026-03-05"
            )
        self.assertEqual(result["identity"]["net_cash"], 300)
        self.assertEqual(result["identity"]["supplier_paid"], 0)
        self.assertEqual(result["buckets"][-1]["closing_position"], 300)

    def test_portfolio_api_shape(self):
        with patch.object(cash_flow, "_authorize", return_value=("finance@example.com", "Demo Company")), patch.object(
            cash_flow, "_load_data", return_value=fixture_data()
        ):
            result = cash_flow.get_portfolio_data({})
        for key in (
            "active_company", "modes", "counts", "summary", "project_rows", "standalone_order_rows",
            "profitability_rows", "cash_flow_rows", "customer_rows", "monthly_rows", "data_quality_rows", "currencies", "filter_options",
        ):
            self.assertIn(key, result)
        for key in (
            "context_type", "context_name", "name", "title", "customer", "company", "currency",
            "company_currency", "workflow_status", "project_type", "ordered", "invoiced", "collected",
            "actual_cost", "supplier_paid", "net_cash", "committed_inflow", "committed_outflow",
            "forecast_outflow", "forecast_net", "funding_gap", "next_cash_event", "risk_status",
            "confidence", "link", "detail_route",
            "expected_revenue_ht", "expected_revenue_ttc", "expected_cost", "expected_profit",
            "expected_profit_pct", "actual_profit_to_date", "revenue_forecast_final", "cost_forecast_final",
        ):
            self.assertIn(key, result["project_rows"][0])

    def test_detail_api_shape_and_forward_buckets(self):
        with patch.object(cash_flow, "_authorize", return_value=("finance@example.com", "Demo Company")), patch.object(
            cash_flow, "_load_data", return_value=fixture_data()
        ):
            result = cash_flow.get_cash_flow_detail(
                "Project", "PROJ-1", from_date="2026-08-01", to_date="2026-11-15"
            )
        for key in (
            "identity", "kpis", "buckets", "events", "receivables", "payables", "documents",
            "alerts", "data_quality", "profitability",
        ):
            self.assertIn(key, result)
        self.assertEqual(result["identity"]["context_name"], "PROJ-1")
        self.assertEqual(result["profitability"]["expected"]["profit"], -1200)
        self.assertEqual(result["profitability"]["actual"]["profit"], 150)
        self.assertEqual(result["profitability"]["cash"]["net_cash"], 100)
        self.assertTrue(result["weekly_buckets"])
        self.assertEqual(result["weekly_buckets"][0]["opening_position"], 100)

    def test_missing_landed_cost_is_low_confidence_data_quality(self):
        data = fixture_data()
        data["sales_order_items"][0]["source_landed_cost"] = 0
        model = cash_flow.build_cash_flow_model(data, company="Demo Company")
        project = model["contexts"][("Project", "PROJ-1")]
        self.assertEqual(project["confidence"], "Low")
        self.assertFalse(project["profitability_complete"])
        self.assertFalse(cash_flow._profitability_payload(project)["expected"]["complete"])
        self.assertIn("missing_landed_cost", {row["code"] for row in model["data_quality"]})

        data["projects"][0]["custom_cost_forecast_final"] = 1
        finalized = cash_flow.build_cash_flow_model(data, company="Demo Company")["contexts"][("Project", "PROJ-1")]
        self.assertTrue(finalized["profitability_complete"])

    def test_truncated_source_lowers_all_context_confidence(self):
        data = fixture_data()
        data["data_quality"] = [
            {
                "code": "source_truncated", "severity": "Warning", "message": "bounded",
                "document_type": "Sales Invoice",
            }
        ]
        model = cash_flow.build_cash_flow_model(data, company="Demo Company")
        self.assertTrue(all(row["confidence"] == "Low" for row in model["contexts"].values()))

    def test_bounded_query_reports_truncation_and_permission_unavailability(self):
        quality = []
        rows = [{"name": "3"}, {"name": "2"}, {"name": "1"}]
        with patch.object(cash_flow, "_can_read", return_value=True), patch.object(
            cash_flow, "_available_fields", return_value=["name"]
        ), patch.object(cash_flow.frappe, "get_list", return_value=rows, create=True):
            result = cash_flow._get_list(
                "Sales Invoice", filters={}, fields=["name"], limit=2, quality=quality
            )
        self.assertEqual(len(result), 2)
        self.assertEqual(quality[0]["code"], "source_truncated")

        class DB:
            @staticmethod
            def exists(doctype, name):
                return True

        permission_quality = []
        with patch.object(cash_flow.frappe, "db", DB(), create=True), patch.object(
            cash_flow.frappe, "has_permission", return_value=False
        ):
            self.assertFalse(cash_flow._can_read("Purchase Invoice", permission_quality))
        self.assertEqual(permission_quality[0]["code"], "unavailable_source")

    def test_source_access_does_not_swallow_arbitrary_errors(self):
        class BrokenDB:
            @staticmethod
            def exists(doctype, name):
                raise RuntimeError("database unavailable")

        with patch.object(cash_flow.frappe, "db", BrokenDB(), create=True):
            with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                cash_flow._can_read("Sales Invoice", [])

    def test_detail_exposes_event_bounds_and_completeness(self):
        with patch.object(cash_flow, "MAX_DETAIL_EVENTS", 10000), patch.object(
            cash_flow, "_authorize", return_value=("finance@example.com", "Demo Company")
        ), patch.object(cash_flow, "_load_data", return_value=fixture_data()):
            complete = cash_flow.get_cash_flow_detail(
                "Project", "PROJ-1", from_date="2026-04-01", to_date="2026-11-15"
            )
        with patch.object(cash_flow, "MAX_DETAIL_EVENTS", 2), patch.object(
            cash_flow, "_authorize", return_value=("finance@example.com", "Demo Company")
        ), patch.object(cash_flow, "_load_data", return_value=fixture_data()):
            result = cash_flow.get_cash_flow_detail(
                "Project", "PROJ-1", from_date="2026-04-01", to_date="2026-11-15"
            )

        returned_ids = {row["id"] for row in result["events"]}
        bucket_event_ids = {
            row["id"] for bucket in result["buckets"] for row in bucket["events"]
        }
        self.assertEqual(result["bounded_events"]["returned"], 2)
        self.assertEqual(result["bounded_events"]["total"], complete["bounded_events"]["returned"])
        self.assertEqual(result["bounded_events"]["from_date"], "2026-04-01")
        self.assertEqual(result["bounded_events"]["to_date"], "2026-11-15")
        self.assertTrue(result["bounded_events"]["truncated"])
        self.assertEqual(bucket_event_ids, returned_ids)
        self.assertLessEqual(sum(len(row["events"]) for row in result["buckets"]), 2)
        self.assertTrue({row["id"] for row in result["receivables"]}.issubset(returned_ids))
        self.assertTrue({row["id"] for row in result["payables"]}.issubset(returned_ids))
        self.assertLessEqual(len(result["receivables"]), 2)
        self.assertLessEqual(len(result["payables"]), 2)
        self.assertTrue(
            all(
                row["date"] <= "2026-11-15"
                and (row["layer"] != "actual" or row["date"] > "2026-04-01")
                for row in result["events"]
            )
        )
        for bounded_bucket, complete_bucket in zip(result["buckets"], complete["buckets"]):
            for field in (
                "opening_position", "actual_inflow", "actual_outflow", "committed_inflow",
                "committed_outflow", "forecast_outflow", "closing_position", "funding_gap",
            ):
                self.assertEqual(bounded_bucket[field], complete_bucket[field])
        self.assertFalse(result["detail_completeness"]["complete"])
        self.assertIn("detail_events_truncated", {row["code"] for row in result["data_quality"]})

    def test_purchase_invoice_loader_uses_native_po_detail_lineage(self):
        source = inspect.getsource(cash_flow._load_purchase_documents)
        self.assertIn('"po_detail"', source)
        self.assertNotIn('"purchase_order_item"', source)

    def test_child_query_keeps_frappe_system_columns_for_attribution(self):
        with patch.object(cash_flow, "_has_field", side_effect=lambda doctype, fieldname: fieldname == "qty"):
            fields = cash_flow._available_fields(
                "Sales Order Item",
                ["parent", "parenttype", "idx", "name", "qty", "unknown"],
            )
        self.assertEqual(fields, ["parent", "parenttype", "idx", "name", "qty"])

    def test_filter_options_standardize_workflow_statuses(self):
        options = cash_flow._filter_options(
            [{"company": "C", "workflow_status": "Execution"}], ["MAD"]
        )
        self.assertEqual(options["workflow_statuses"], ["Execution"])
        self.assertEqual(options["statuses"], options["workflow_statuses"])

    def test_forecast_status_filters_are_independent(self):
        row = {"revenue_forecast_final": True, "cost_forecast_final": False}
        self.assertTrue(cash_flow._matches_output_filters(row, {"revenue_forecast_status": "Final"}))
        self.assertTrue(cash_flow._matches_output_filters(row, {"cost_forecast_status": "Open"}))
        self.assertFalse(cash_flow._matches_output_filters(row, {"revenue_forecast_status": "Open"}))
        self.assertFalse(cash_flow._matches_output_filters(row, {"cost_forecast_status": "Final"}))

    def test_service_uses_permission_aware_bounded_queries(self):
        source = inspect.getsource(cash_flow)
        self.assertIn("frappe.get_list(", source)
        self.assertNotIn("frappe.get_all(", source)
        self.assertIn("get_session_company_context", source)
        self.assertIn('filters={"company": company, "docstatus": 1}', source)
        self.assertIn("limit_page_length=limit", source)
        self.assertIn("parent_doctype=parent_doctype", source)

    def test_standalone_direct_charge_field_has_focused_migration_setup(self):
        app_root = Path(__file__).resolve().parents[1]
        setup = (app_root / "orderlift_finance" / "cash_flow_setup.py").read_text()
        hooks = (app_root / "hooks.py").read_text()
        self.assertIn('"Purchase Invoice Item"', setup)
        self.assertIn('"fieldname": "custom_sales_order"', setup)
        self.assertIn('"options": "Sales Order"', setup)
        self.assertIn('"fieldname": "custom_revenue_forecast_final"', setup)
        self.assertIn('"fieldname": "custom_cost_forecast_final"', setup)
        self.assertIn('"allow_on_submit": 1', setup)
        self.assertIn("orderlift.orderlift_finance.cash_flow_setup.after_migrate", hooks)
        self.assertIn("cash_flow_setup.validate_purchase_invoice_sales_order", hooks)

    def test_purchase_invoice_direct_sales_order_validation(self):
        class DB:
            order = {"company": "Demo Company", "docstatus": 1, "project": ""}

            def get_value(self, doctype, name, fields, as_dict=False):
                return dict(self.order) if name == "SO-2" else None

        valid = {
            "company": "Demo Company", "project": "",
            "items": [
                {
                    "idx": 1, "custom_sales_order": "SO-2", "project": "",
                    "purchase_order": "", "po_detail": "",
                }
            ],
        }
        with patch.object(cash_flow_setup.frappe, "db", DB(), create=True):
            cash_flow_setup.validate_purchase_invoice_sales_order(valid)

            invalid_cases = [
                ({**valid, "company": "Other Company"}, "another company"),
                ({**valid, "project": "PROJ-1"}, "Project lineage"),
                (
                    {
                        **valid,
                        "items": [{"idx": 1, "custom_sales_order": "SO-2", "po_detail": "POI-1"}],
                    },
                    "mutually exclusive",
                ),
            ]
            for document, message in invalid_cases:
                with self.subTest(message=message), self.assertRaisesRegex(Exception, message):
                    cash_flow_setup.validate_purchase_invoice_sales_order(document)

            DB.order = {"company": "Demo Company", "docstatus": 0, "project": ""}
            with self.assertRaisesRegex(Exception, "must be submitted"):
                cash_flow_setup.validate_purchase_invoice_sales_order(valid)
            DB.order = {"company": "Demo Company", "docstatus": 1, "project": "PROJ-1"}
            with self.assertRaisesRegex(Exception, "project-linked"):
                cash_flow_setup.validate_purchase_invoice_sales_order(valid)

    def test_forecast_finality_requires_admin_role_and_same_company_context(self):
        class Meta:
            @staticmethod
            def get_field(fieldname):
                return {"fieldname": fieldname}

        class Doc(dict):
            meta = Meta()

            def check_permission(self, permission):
                self["checked_permission"] = permission

            def db_set(self, fieldname, value, notify=False):
                self[fieldname] = value
                self["notified"] = notify

            def add_comment(self, comment_type, text):
                self["comment"] = (comment_type, text)

        doc = Doc(company="Demo Company", project="")
        with patch.object(cash_flow, "_authorize", return_value=("admin@example.com", "Demo Company")), patch.object(
            cash_flow.frappe, "get_roles", return_value=["Finance Admin"]
        ), patch.object(cash_flow.frappe, "get_doc", return_value=doc, create=True), patch.object(
            cash_flow, "get_cash_flow_detail", return_value={"ok": True}
        ):
            result = cash_flow.set_forecast_finality("Sales Order", "SO-2", "cost", 1)
        self.assertEqual(result, {"ok": True})
        self.assertEqual(doc["custom_cost_forecast_final"], 1)
        self.assertEqual(doc["checked_permission"], "read")
        self.assertTrue(doc["notified"])

        with patch.object(cash_flow, "_authorize", return_value=("finance@example.com", "Demo Company")), patch.object(
            cash_flow.frappe, "get_roles", return_value=["Finance User"]
        ):
            with self.assertRaisesRegex(Exception, "Only Finance Admin"):
                cash_flow.set_forecast_finality("Sales Order", "SO-2", "cost", 1)

        with patch.object(cash_flow, "_authorize", return_value=("admin@example.com", "Demo Company")), patch.object(
            cash_flow.frappe, "get_roles", return_value=["Finance Admin"]
        ), patch.object(cash_flow.frappe, "get_doc", return_value=doc, create=True):
            with self.assertRaisesRegex(Exception, "true or false"):
                cash_flow.set_forecast_finality("Sales Order", "SO-2", "cost", "invalid")

    def test_forecast_fields_reject_generic_document_updates(self):
        class Meta:
            @staticmethod
            def get_field(fieldname):
                return {"fieldname": fieldname}

        class Doc(dict):
            doctype = "Project"
            name = "PROJ-1"
            meta = Meta()

            @staticmethod
            def is_new():
                return False

            @staticmethod
            def get_doc_before_save():
                return {"custom_revenue_forecast_final": 0, "custom_cost_forecast_final": 0}

        with self.assertRaisesRegex(Exception, "Project & Order Finance"):
            cash_flow_setup.protect_forecast_finality(
                Doc(custom_revenue_forecast_final=1, custom_cost_forecast_final=0)
            )

        class NewDoc(Doc):
            @staticmethod
            def is_new():
                return True

            def set(self, fieldname, value):
                self[fieldname] = value

        new_doc = NewDoc(custom_revenue_forecast_final=1, custom_cost_forecast_final=1)
        cash_flow_setup.protect_forecast_finality(new_doc)
        self.assertEqual(new_doc["custom_revenue_forecast_final"], 0)
        self.assertEqual(new_doc["custom_cost_forecast_final"], 0)

        source = inspect.getsource(cash_flow.set_forecast_finality)
        self.assertIn('methods=["POST"]', inspect.getsource(cash_flow))
        self.assertIn("Forecast finality must be true or false", source)


if __name__ == "__main__":
    unittest.main()
