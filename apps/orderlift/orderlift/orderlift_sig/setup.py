from __future__ import annotations

import json
import os

import frappe

# Fixture files to load, in order
_FIXTURE_FILES = [
    "custom_field_project_sig.json",
    "custom_field_sales_order_sig.json",
]


def after_migrate():
    """
    Import SIG custom fields from bundled fixture files.
    Safe to run multiple times — existing fields are updated in-place.
    """
    fixtures_dir = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "fixtures")
    )

    total = 0
    for filename in _FIXTURE_FILES:
        path = os.path.join(fixtures_dir, filename)
        if not os.path.exists(path):
            frappe.logger().warning("orderlift_sig.setup: fixture not found: %s", path)
            continue

        with open(path) as f:
            fields = json.load(f)

        total += _upsert_custom_fields(fields)

    frappe.db.commit()
    frappe.logger().info("orderlift_sig.setup: %d SIG custom fields synced", total)


def _upsert_custom_fields(fields: list) -> int:
    count = 0
    for field_def in fields:
        fieldname = field_def.get("fieldname")
        dt = field_def.get("dt")
        if not fieldname or not dt:
            continue

        if frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname}):
            doc = frappe.get_doc("Custom Field", {"dt": dt, "fieldname": fieldname})
            for key, val in field_def.items():
                if key not in ("doctype", "dt"):
                    setattr(doc, key, val)
            doc.save(ignore_permissions=True)
        else:
            doc = frappe.new_doc("Custom Field")
            for key, val in field_def.items():
                if key != "doctype":
                    setattr(doc, key, val)
            doc.insert(ignore_permissions=True)
        count += 1
    return count
