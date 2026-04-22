import sys
import types
import unittest
from unittest.mock import patch


class FrappeThrow(Exception):
    pass


frappe_stub = types.ModuleType("frappe")
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.throw = lambda msg, title=None: (_ for _ in ()).throw(FrappeThrow(msg))
frappe_stub.DoesNotExistError = FrappeThrow
frappe_stub.db = types.SimpleNamespace()

frappe_utils_stub = types.ModuleType("frappe.utils")
frappe_utils_stub.cint = lambda value=0: int(value or 0)
frappe_utils_stub.flt = lambda value=0, precision=None: round(float(value or 0), precision) if precision is not None else float(value or 0)
frappe_utils_stub.now_datetime = lambda: "2026-04-17 00:00:00"
frappe_utils_stub.getdate = lambda value=None: value or "2026-04-17"

load_planning_stub = types.ModuleType("orderlift.orderlift_logistics.services.load_planning")
load_planning_stub._get_item_metrics = lambda item_code: (0, 0)
load_planning_stub._get_row_metrics = lambda row, parent_doctype=None, packaging_profile=None: {
    "unit_weight_kg": 0,
    "unit_volume_m3": 0,
    "line_weight_kg": 0,
    "line_volume_m3": 0,
}

capacity_math_stub = types.ModuleType("orderlift.orderlift_logistics.services.capacity_math")
capacity_math_stub.round3 = lambda value: round(float(value or 0), 3)

sys.modules["frappe"] = frappe_stub
sys.modules["frappe.utils"] = frappe_utils_stub
sys.modules["orderlift.orderlift_logistics.services.load_planning"] = load_planning_stub
sys.modules["orderlift.orderlift_logistics.services.capacity_math"] = capacity_math_stub


from orderlift.orderlift_logistics.services import forecast_planning


class FakeForecast:
    def __init__(self, status="Planning", container_profile="CP-001", items=None):
        self.name = "FLP-00001"
        self.status = status
        self.container_profile = container_profile
        self.items = items or []
        self.saved = False

    def check_permission(self, action):
        return None

    def save(self, ignore_permissions=False):
        self.saved = True


class TestForecastSingleDocumentMode(unittest.TestCase):
    def test_advance_status_ready_does_not_create_container_load_plan(self):
        forecast = FakeForecast(items=[types.SimpleNamespace(selected=1)])

        with patch.object(forecast_planning.frappe, "get_doc", return_value=forecast, create=True), \
             patch.object(forecast_planning, "_link_source_docs") as link_docs, \
             patch.object(forecast_planning, "get_plan_detail", return_value={"name": forecast.name}):
            result = forecast_planning.advance_status(forecast.name, "Ready", bypass_validation=True)

        self.assertEqual(result, {"name": forecast.name})
        self.assertEqual(forecast.status, "Ready")
        self.assertTrue(forecast.saved)
        link_docs.assert_called_once_with(forecast)

    def test_ready_transition_requires_container_profile(self):
        forecast = FakeForecast(container_profile="", items=[types.SimpleNamespace(selected=1)])

        with patch.object(forecast_planning.frappe, "get_doc", return_value=forecast, create=True):
            with self.assertRaises(FrappeThrow):
                forecast_planning.advance_status(forecast.name, "Ready", bypass_validation=True)

    def test_unconfirm_releases_linked_source_docs(self):
        forecast = FakeForecast(status="Ready", items=[types.SimpleNamespace(selected=1)])

        with patch.object(forecast_planning.frappe, "get_doc", return_value=forecast, create=True), \
             patch.object(forecast_planning, "_unlink_source_docs") as unlink_docs, \
             patch.object(forecast_planning, "get_plan_detail", return_value={"name": forecast.name, "status": "Planning"}):
            result = forecast_planning.advance_status(forecast.name, "Planning")

        self.assertEqual(result["status"], "Planning")
        self.assertEqual(forecast.status, "Planning")
        unlink_docs.assert_called_once_with(forecast)


if __name__ == "__main__":
    unittest.main()
