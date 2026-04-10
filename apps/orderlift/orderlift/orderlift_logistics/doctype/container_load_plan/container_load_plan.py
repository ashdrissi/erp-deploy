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
from orderlift.orderlift_logistics.services.capacity_math import (
    candidate_balance_score,
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
            if not cint(row.sequence):
                row.sequence = idx * 10
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
    _publish_load_plan_updated(load_plan_name)
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
    _publish_load_plan_updated(load_plan_name)
    return {
        "added": added,
        "total_weight_kg": doc.total_weight_kg,
        "total_volume_m3": doc.total_volume_m3,
        "analysis_status": doc.analysis_status,
    }


def _build_plan_summary(doc):
    profile = None
    if doc.container_profile:
        profile = frappe.db.get_value(
            "Container Profile",
            doc.container_profile,
            ["name", "container_name", "container_type", "max_weight_kg", "max_volume_m3"],
            as_dict=True,
        )

    return {
        "name": doc.name,
        "container_label": doc.container_label,
        "status": doc.status,
        "analysis_status": doc.analysis_status,
        "company": doc.company,
        "destination_zone": doc.destination_zone,
        "departure_date": str(doc.departure_date) if doc.departure_date else "",
        "container_profile": doc.container_profile,
        "container_profile_label": (profile.container_name if profile else "") or doc.container_profile,
        "container_type": profile.container_type if profile else "",
        "max_weight_kg": round3(profile.max_weight_kg if profile else 0),
        "max_volume_m3": round3(profile.max_volume_m3 if profile else 0),
        "total_weight_kg": round3(doc.total_weight_kg),
        "total_volume_m3": round3(doc.total_volume_m3),
        "weight_utilization_pct": round3(doc.weight_utilization_pct),
        "volume_utilization_pct": round3(doc.volume_utilization_pct),
        "limiting_factor": doc.limiting_factor,
    }


def _delivery_note_metrics(dn_row):
    weight = flt(dn_row.get("custom_total_weight_kg"))
    volume = flt(dn_row.get("custom_total_volume_m3"))
    if weight <= 0 or volume <= 0:
        totals = compute_delivery_note_totals(dn_row.name)
        weight = flt(totals.get("total_weight_kg"))
        volume = flt(totals.get("total_volume_m3"))
    return round3(weight), round3(volume)


def _queue_for_plan(doc):
    filters = {"docstatus": 1}
    if doc.company:
        filters["company"] = doc.company
    if doc.destination_zone and frappe.db.has_column("Delivery Note", "custom_destination_zone"):
        filters["custom_destination_zone"] = doc.destination_zone

    rows = frappe.get_all(
        "Delivery Note",
        filters=filters,
        fields=[
            "name",
            "customer",
            "posting_date",
            "company",
            "custom_destination_zone",
            "custom_assigned_container_load_plan",
            "custom_total_weight_kg",
            "custom_total_volume_m3",
            "custom_logistics_status",
        ],
        order_by="posting_date asc, creation asc",
        limit_page_length=0,
    )

    selected = {row.delivery_note for row in (doc.shipments or []) if row.delivery_note}
    queue = []
    for row in rows:
        assigned = (row.get("custom_assigned_container_load_plan") or "").strip()
        if assigned and assigned != doc.name:
            continue
        if row.name in selected:
            continue

        weight, volume = _delivery_note_metrics(row)
        queue.append(
            {
                "delivery_note": row.name,
                "customer": row.customer,
                "posting_date": str(row.posting_date) if row.posting_date else "",
                "company": row.company,
                "destination_zone": row.get("custom_destination_zone") or "",
                "total_weight_kg": weight,
                "total_volume_m3": volume,
                "logistics_status": row.get("custom_logistics_status") or "",
            }
        )

    return queue


def _publish_load_plan_updated(load_plan_name):
    """Broadcast that this load plan was modified, so any open cockpit tabs refresh."""
    frappe.publish_realtime(
        event="load_plan_updated",
        message={
            "load_plan": load_plan_name,
            "user": frappe.session.user,
            "user_fullname": frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user,
        },
        doctype="Container Load Plan",
        docname=load_plan_name,
        after_commit=True,
    )


@frappe.whitelist()
def reorder_shipments(load_plan_name, delivery_notes_ordered):
    """Update the sequence field of shipments to reflect a new order."""
    if isinstance(delivery_notes_ordered, str):
        delivery_notes_ordered = frappe.parse_json(delivery_notes_ordered)

    doc = frappe.get_doc("Container Load Plan", load_plan_name)
    index_map = {dn: (i + 1) * 10 for i, dn in enumerate(delivery_notes_ordered)}

    for row in doc.shipments or []:
        if row.delivery_note in index_map:
            row.sequence = index_map[row.delivery_note]

    doc.save(ignore_permissions=True)
    _publish_load_plan_updated(load_plan_name)
    return {"reordered": len(index_map)}


@frappe.whitelist()
def preview_consolidation(company=None, departure_date=None):
    """Wraps consolidation_preview for cockpit access."""
    from orderlift.orderlift_logistics.services.load_planning import consolidation_preview
    return consolidation_preview(company=company, departure_date=departure_date)


@frappe.whitelist()
def get_utilization_trends(days=30):
    """Aggregates Shipment Analysis records to compute utilization trends."""
    from collections import defaultdict

    days = cint(days) or 30
    from_date = frappe.utils.add_days(frappe.utils.today(), -days)

    records = frappe.get_all(
        "Shipment Analysis",
        filters={
            "source_type": "Container Load Plan",
            "status": "ok",
            "creation": [">=", from_date],
        },
        fields=[
            "destination_zone",
            "weight_utilization_pct",
            "volume_utilization_pct",
            "limiting_factor",
            "creation",
        ],
        limit_page_length=0,
    )

    if not records:
        return {"plan_count": 0, "avg_weight_pct": 0, "avg_volume_pct": 0, "by_zone": [], "by_limiting_factor": {}}

    total = len(records)
    avg_w = round3(sum(flt(r.weight_utilization_pct) for r in records) / total)
    avg_v = round3(sum(flt(r.volume_utilization_pct) for r in records) / total)

    # Per-zone breakdown
    zone_data = defaultdict(lambda: {"count": 0, "weight_sum": 0.0, "volume_sum": 0.0})
    factor_counts = defaultdict(int)

    for r in records:
        z = (r.destination_zone or "(no zone)").strip()
        zone_data[z]["count"] += 1
        zone_data[z]["weight_sum"] += flt(r.weight_utilization_pct)
        zone_data[z]["volume_sum"] += flt(r.volume_utilization_pct)
        factor_counts[r.limiting_factor or "unknown"] += 1

    by_zone = [
        {
            "zone": z,
            "count": d["count"],
            "avg_weight_pct": round3(d["weight_sum"] / d["count"]),
            "avg_volume_pct": round3(d["volume_sum"] / d["count"]),
        }
        for z, d in sorted(zone_data.items(), key=lambda x: x[1]["count"], reverse=True)
    ]

    return {
        "plan_count": total,
        "avg_weight_pct": avg_w,
        "avg_volume_pct": avg_v,
        "by_zone": by_zone,
        "by_limiting_factor": dict(factor_counts),
    }


@frappe.whitelist()
def get_cockpit_data(load_plan_name):
    doc = frappe.get_doc("Container Load Plan", load_plan_name)
    doc.recalculate_totals()
    doc.save(ignore_permissions=True)

    shipments = []
    for row in doc.shipments or []:
        shipments.append(
            {
                "name": row.name,
                "delivery_note": row.delivery_note,
                "customer": row.customer,
                "shipment_weight_kg": round3(row.shipment_weight_kg),
                "shipment_volume_m3": round3(row.shipment_volume_m3),
                "selected": cint(row.selected),
                "sequence": cint(row.sequence),
            }
        )

    # Sort shipments by sequence order for proper rendering
    shipments.sort(key=lambda x: cint(x.get("sequence") or 0))

    queue = _queue_for_plan(doc)
    return {
        "plan": _build_plan_summary(doc),
        "shipments": shipments,
        "queue": queue,
    }


@frappe.whitelist()
def remove_shipment(load_plan_name, delivery_note):
    doc = frappe.get_doc("Container Load Plan", load_plan_name)
    for row in list(doc.shipments or []):
        if row.delivery_note == delivery_note:
            doc.remove(row)
    doc.recalculate_totals()
    doc.save(ignore_permissions=True)
    _publish_load_plan_updated(load_plan_name)
    return {
        "removed": delivery_note,
        "total_weight_kg": doc.total_weight_kg,
        "total_volume_m3": doc.total_volume_m3,
        "analysis_status": doc.analysis_status,
    }


@frappe.whitelist()
def set_shipment_selected(load_plan_name, delivery_note, selected=1):
    doc = frappe.get_doc("Container Load Plan", load_plan_name)
    selected_int = 1 if cint(selected) else 0
    found = False
    for row in doc.shipments or []:
        if row.delivery_note == delivery_note:
            row.selected = selected_int
            found = True
            break

    if not found:
        frappe.throw(f"Delivery Note {delivery_note} is not in this load plan.")

    doc.recalculate_totals()
    doc.save(ignore_permissions=True)
    _publish_load_plan_updated(load_plan_name)
    return {
        "delivery_note": delivery_note,
        "selected": selected_int,
        "total_weight_kg": doc.total_weight_kg,
        "total_volume_m3": doc.total_volume_m3,
        "analysis_status": doc.analysis_status,
    }
