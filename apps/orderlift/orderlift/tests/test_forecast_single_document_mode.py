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
frappe_model_stub = types.ModuleType("frappe.model")
frappe_document_stub = types.ModuleType("frappe.model.document")
frappe_document_stub.Document = object

frappe_utils_stub = types.ModuleType("frappe.utils")
frappe_utils_stub.cint = lambda value=0: int(value or 0)
frappe_utils_stub.flt = lambda value=0, precision=None: round(float(value or 0), precision) if precision is not None else float(value or 0)
frappe_utils_stub.now_datetime = lambda: "2026-04-17 00:00:00"
frappe_utils_stub.getdate = lambda value=None: value or "2026-04-17"

load_planning_stub = types.ModuleType("orderlift.orderlift_logistics.services.load_planning")
load_planning_stub._get_item_metrics = lambda item_code: (0, 0)
load_planning_stub._get_packaging_metrics = lambda **kwargs: {
    "unit_weight_kg": 0,
    "unit_volume_m3": 0,
    "line_weight_kg": 0,
    "line_volume_m3": 0,
}
load_planning_stub._get_row_metrics = lambda row, parent_doctype=None, packaging_profile=None: {
    "unit_weight_kg": 0,
    "unit_volume_m3": 0,
    "line_weight_kg": 0,
    "line_volume_m3": 0,
}

capacity_math_stub = types.ModuleType("orderlift.orderlift_logistics.services.capacity_math")
capacity_math_stub.round3 = lambda value: round(float(value or 0), 3)
capacity_math_stub.compute_utilization = lambda total_weight_kg, total_volume_m3, max_weight_kg, max_volume_m3: {
    "weight_utilization_pct": capacity_math_stub.round3((float(total_weight_kg or 0) / float(max_weight_kg or 1)) * 100) if float(max_weight_kg or 0) > 0 else 0,
    "volume_utilization_pct": capacity_math_stub.round3((float(total_volume_m3 or 0) / float(max_volume_m3 or 1)) * 100) if float(max_volume_m3 or 0) > 0 else 0,
}
capacity_math_stub.detect_limiting_factor = lambda weight_utilization_pct, volume_utilization_pct, epsilon=1.0: (
    "both" if abs(float(weight_utilization_pct or 0) - float(volume_utilization_pct or 0)) <= float(epsilon or 0)
    else "weight" if float(weight_utilization_pct or 0) > float(volume_utilization_pct or 0)
    else "volume"
)
capacity_math_stub.candidate_pressure = lambda total_weight_kg, total_volume_m3, remaining_weight_kg, remaining_volume_m3: max(
    (float(total_weight_kg or 0) / float(remaining_weight_kg or 1)) if float(remaining_weight_kg or 0) > 0 else 0,
    (float(total_volume_m3 or 0) / float(remaining_volume_m3 or 1)) if float(remaining_volume_m3 or 0) > 0 else 0,
)

sys.modules["frappe"] = frappe_stub
sys.modules["frappe.utils"] = frappe_utils_stub
sys.modules["frappe.model"] = frappe_model_stub
sys.modules["frappe.model.document"] = frappe_document_stub
sys.modules["orderlift.orderlift_logistics.services.load_planning"] = load_planning_stub
sys.modules["orderlift.orderlift_logistics.services.capacity_math"] = capacity_math_stub


from orderlift.orderlift_logistics.services import forecast_planning


class FakeForecast:
    def __init__(self, status="Planning", container_profile="CP-001", items=None):
        self.name = "FLP-00001"
        self.status = status
        self.container_profile = container_profile
        self.items = items or []
        self.packaging_layout_json = ""
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

    def test_capacity_status_without_container_does_not_crash(self):
        forecast = FakeForecast(
            container_profile="",
            items=[types.SimpleNamespace(selected=1, total_volume_m3=12, total_weight_kg=1200)],
        )

        with patch.object(forecast_planning.frappe, "get_doc", return_value=forecast, create=True):
            result = forecast_planning.get_capacity_status(forecast.name)

        self.assertEqual(result["max_volume_m3"], 0)
        self.assertEqual(result["max_weight_kg"], 0)
        self.assertFalse(result["near_volume_limit"])
        self.assertFalse(result["near_weight_limit"])

    def test_container_dimensions_fall_back_for_existing_profiles(self):
        profile = types.SimpleNamespace(container_type="40ft", length_cm=0, width_cm=0, height_cm=0)

        self.assertEqual(
            forecast_planning._container_dimensions_cm(profile),
            (1203.2, 235.2, 239.3),
        )

    def test_container_dimensions_derive_from_volume_for_trucks(self):
        profile = types.SimpleNamespace(
            container_type="Standard Truck",
            length_cm=0,
            width_cm=0,
            height_cm=0,
            max_volume_m3=18,
        )

        self.assertEqual(
            forecast_planning._container_dimensions_cm(profile),
            (340.90909090909093, 240.0, 220.0),
        )

    def test_save_packaging_layout_sanitizes_payload(self):
        forecast = FakeForecast()
        meta = types.SimpleNamespace(get_field=lambda fieldname: fieldname == "packaging_layout_json")
        payload = '{"pkg-1":{"x":1.2345,"y":2,"z":0,"pl":10,"pw":20,"ph":30},"bad":[]}'

        with patch.object(forecast_planning.frappe, "get_doc", return_value=forecast, create=True), \
             patch.object(forecast_planning.frappe, "get_meta", return_value=meta, create=True):
            result = forecast_planning.save_packaging_layout(forecast.name, payload)

        self.assertEqual(result, {"saved": True, "count": 1})
        self.assertTrue(forecast.saved)
        self.assertIn('"pkg-1"', forecast.packaging_layout_json)
        self.assertNotIn('"bad"', forecast.packaging_layout_json)

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
