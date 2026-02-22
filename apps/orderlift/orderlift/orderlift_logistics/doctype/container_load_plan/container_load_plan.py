import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt

from orderlift.orderlift_logistics.services.load_planning import (
    STATUS_INCOMPLETE,
    STATUS_OK,
    STATUS_OVER_CAPACITY,
    build_analysis,
    compute_delivery_note_totals,
    compute_utilization,
    create_shipment_analysis,
    detect_limiting_factor,
    round3,
    suggest_shipments_for_load_plan,
)


class ContainerLoadPlan(Document):
    def validate(self):
        self._enforce_unique_delivery_notes()
        self.recalculate_totals()

        if self.analysis_status == STATUS_OVER_CAPACITY:
            frappe.throw("Container capacity exceeded. Remove one or more shipments before saving.")

    def on_submit(self):
        self.status = self.status or "Loading"
        self._flag_delivery_notes(1)
        self._create_plan_analysis_snapshot()

    def on_cancel(self):
        self._flag_delivery_notes(0)
        self._mark_latest_analysis_cancelled()

    def _enforce_unique_delivery_notes(self):
        seen = set()
        for row in self.shipments or []:
            if not row.delivery_note:
                continue
            if row.delivery_note in seen:
                frappe.throw(f"Duplicate Delivery Note in plan: {row.delivery_note}")
            seen.add(row.delivery_note)

    def recalculate_totals(self):
        total_weight = 0.0
        total_volume = 0.0
        has_missing = False

        for idx, row in enumerate(self.shipments or [], start=1):
            row.sequence = cint(row.sequence or (idx * 10))
            if not row.delivery_note:
                continue

            totals = compute_delivery_note_totals(row.delivery_note)
            row.customer = totals.get("customer")
            row.shipment_weight_kg = round3(totals.get("total_weight_kg"))
            row.shipment_volume_m3 = round3(totals.get("total_volume_m3"))
            row.selected = 1 if cint(row.selected) else 0

            if totals.get("missing_data_items"):
                has_missing = True

            if row.selected:
                total_weight += flt(row.shipment_weight_kg)
                total_volume += flt(row.shipment_volume_m3)

        self.total_weight_kg = round3(total_weight)
        self.total_volume_m3 = round3(total_volume)

        if not self.container_profile:
            self.weight_utilization_pct = 0
            self.volume_utilization_pct = 0
            self.limiting_factor = ""
            self.analysis_status = STATUS_INCOMPLETE if has_missing else STATUS_OK
            return

        profile = frappe.get_doc("Container Profile", self.container_profile)
        utilization = compute_utilization(
            self.total_weight_kg,
            self.total_volume_m3,
            profile.max_weight_kg,
            profile.max_volume_m3,
        )
        self.weight_utilization_pct = utilization["weight_utilization_pct"]
        self.volume_utilization_pct = utilization["volume_utilization_pct"]
        self.limiting_factor = detect_limiting_factor(self.weight_utilization_pct, self.volume_utilization_pct)

        if has_missing:
            self.analysis_status = STATUS_INCOMPLETE
        elif self.weight_utilization_pct > 100 or self.volume_utilization_pct > 100:
            self.analysis_status = STATUS_OVER_CAPACITY
        else:
            self.analysis_status = STATUS_OK

    def _flag_delivery_notes(self, is_locked):
        has_plan_link = frappe.db.has_column("Delivery Note", "custom_assigned_container_load_plan")
        has_lock = frappe.db.has_column("Delivery Note", "custom_logistics_locked")

        for row in self.shipments or []:
            if not row.delivery_note:
                continue

            updates = {}
            if has_plan_link:
                updates["custom_assigned_container_load_plan"] = self.name if is_locked else ""
            if has_lock:
                updates["custom_logistics_locked"] = 1 if is_locked else 0

            if updates:
                frappe.db.set_value("Delivery Note", row.delivery_note, updates)

    def _create_plan_analysis_snapshot(self):
        recommendation = {
            "container": frappe.get_doc("Container Profile", self.container_profile),
            "weight_utilization_pct": self.weight_utilization_pct,
            "volume_utilization_pct": self.volume_utilization_pct,
            "limiting_factor": self.limiting_factor,
        }
        totals = {
            "total_weight_kg": self.total_weight_kg,
            "total_volume_m3": self.total_volume_m3,
            "missing_data_items": [],
        }
        analysis_payload = build_analysis(
            source_type="Container Load Plan",
            source_name=self.name,
            customer="",
            destination_zone=self.destination_zone,
            totals=totals,
            recommendation=recommendation,
        )
        analysis_payload["container_load_plan"] = self.name
        analysis_payload["status"] = self.analysis_status
        create_shipment_analysis(analysis_payload)

    def _mark_latest_analysis_cancelled(self):
        analysis_name = frappe.get_value(
            "Shipment Analysis",
            {
                "source_type": "Container Load Plan",
                "source_name": self.name,
            },
            "name",
            order_by="creation desc",
        )
        if analysis_name:
            frappe.db.set_value("Shipment Analysis", analysis_name, "status", "cancelled")


@frappe.whitelist()
def run_load_plan_analysis(load_plan_name):
    doc = frappe.get_doc("Container Load Plan", load_plan_name)
    doc.recalculate_totals()
    doc.save(ignore_permissions=True)
    return {
        "total_weight_kg": doc.total_weight_kg,
        "total_volume_m3": doc.total_volume_m3,
        "weight_utilization_pct": doc.weight_utilization_pct,
        "volume_utilization_pct": doc.volume_utilization_pct,
        "limiting_factor": doc.limiting_factor,
        "analysis_status": doc.analysis_status,
    }


@frappe.whitelist()
def suggest_shipments(load_plan_name):
    doc = frappe.get_doc("Container Load Plan", load_plan_name)
    result = suggest_shipments_for_load_plan(doc)
    return result


@frappe.whitelist()
def append_shipments(load_plan_name, delivery_notes):
    if isinstance(delivery_notes, str):
        delivery_notes = frappe.parse_json(delivery_notes)

    doc = frappe.get_doc("Container Load Plan", load_plan_name)
    existing = {row.delivery_note for row in (doc.shipments or []) if row.delivery_note}

    added = 0
    for dn in delivery_notes or []:
        if dn in existing:
            continue
        doc.append("shipments", {"delivery_note": dn, "selected": 1})
        added += 1

    doc.recalculate_totals()
    doc.save(ignore_permissions=True)
    return {
        "added": added,
        "total_weight_kg": doc.total_weight_kg,
        "total_volume_m3": doc.total_volume_m3,
        "analysis_status": doc.analysis_status,
    }
