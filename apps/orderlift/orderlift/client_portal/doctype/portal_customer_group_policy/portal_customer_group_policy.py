from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class PortalCustomerGroupPolicy(Document):
    def validate(self):
        self.customer_group = (self.customer_group or "").strip()
        if self.portal_price_list:
            self.currency = frappe.db.get_value("Price List", self.portal_price_list, "currency") or self.currency
        if frappe.db.exists("Portal Customer Group Policy", {"customer_group": self.customer_group, "name": ["!=", self.name]}):
            frappe.throw(frappe._("A portal policy already exists for customer group {0}.").format(self.customer_group))

        seen = set()
        for row in self.catalog_items or []:
            if bool(row.item_code) == bool(row.product_bundle):
                frappe.throw(frappe._("Each catalog row must choose either Item or Product Bundle."))
            key = (row.item_code or "", row.product_bundle or "")
            if key in seen:
                frappe.throw(frappe._("Duplicate catalog entry found in this customer group policy."))
            seen.add(key)

    @frappe.whitelist()
    def bulk_add_products(self, filter_type: str, filter_value: str, featured: int = 0, allow_quote: int = 1):
        filter_type = (filter_type or "").strip()
        filter_value = (filter_value or "").strip()
        if filter_type not in {"item_group", "brand", "codes"}:
            frappe.throw(_("Unsupported filter type for bulk add."))
        if not filter_value:
            frappe.throw(_("Please choose an item group or brand to bulk add."))

        if filter_type == "codes":
            codes = [part.strip() for part in filter_value.replace(",", "\n").splitlines() if part.strip()]
            items = frappe.get_all(
                "Item",
                filters={"name": ["in", codes], "disabled": 0},
                fields=["name", "item_name", "description"],
                order_by="modified desc",
                limit_page_length=1000,
            )
        else:
            filters = {filter_type: filter_value, "disabled": 0}
            items = frappe.get_all(
                "Item",
                filters=filters,
                fields=["name", "item_name", "description"],
                order_by="modified desc",
                limit_page_length=1000,
            )
        existing_items = {row.item_code for row in self.catalog_items if row.item_code}
        sort_seed = max((int(row.sort_order or 0) for row in self.catalog_items), default=0)
        added = 0

        for row in items:
            if row.name in existing_items:
                continue
            sort_seed += 1
            self.append(
                "catalog_items",
                {
                    "enabled": 1,
                    "item_code": row.name,
                    "portal_title": row.item_name,
                    "short_description": (row.description or "")[:140],
                    "featured": int(featured or 0),
                    "allow_quote": int(allow_quote or 0),
                    "sort_order": sort_seed,
                },
            )
            added += 1

        self.save(ignore_permissions=True)
        return {"added": added, "filter_type": filter_type, "filter_value": filter_value}

    @frappe.whitelist()
    def bulk_add_bundles(self, filter_type: str, filter_value: str, featured: int = 0, allow_quote: int = 1):
        filter_type = (filter_type or "").strip()
        filter_value = (filter_value or "").strip()
        if filter_type not in {"item_group", "brand", "codes"}:
            frappe.throw(_("Unsupported filter type for bulk bundle add."))
        if not filter_value:
            frappe.throw(_("Please choose an item group or brand to bulk add bundles."))

        existing_bundles = {row.product_bundle for row in self.catalog_items if row.product_bundle}
        sort_seed = max((int(row.sort_order or 0) for row in self.catalog_items), default=0)
        added = 0

        bundles = frappe.get_all(
            "Product Bundle",
            fields=["name", "new_item_code", "description"],
            limit_page_length=1000,
        )
        bundle_codes = [part.strip() for part in filter_value.replace(",", "\n").splitlines() if part.strip()] if filter_type == "codes" else []
        for bundle in bundles:
            if bundle.name in existing_bundles or not bundle.new_item_code:
                continue
            item = frappe.db.get_value(
                "Item",
                bundle.new_item_code,
                ["item_name", "item_group", "brand", "description"],
                as_dict=True,
            ) or {}
            if filter_type == "codes":
                if bundle.name not in bundle_codes and bundle.new_item_code not in bundle_codes:
                    continue
            elif (item.get(filter_type) or "") != filter_value:
                continue
            sort_seed += 1
            self.append(
                "catalog_items",
                {
                    "enabled": 1,
                    "product_bundle": bundle.name,
                    "portal_title": item.get("item_name") or bundle.name,
                    "short_description": (bundle.description or item.get("description") or "")[:140],
                    "featured": int(featured or 0),
                    "allow_quote": int(allow_quote or 0),
                    "sort_order": sort_seed,
                },
            )
            added += 1

        self.save(ignore_permissions=True)
        return {"added": added, "filter_type": filter_type, "filter_value": filter_value}

    @frappe.whitelist()
    def remove_disabled_rows(self):
        before = len(self.catalog_items or [])
        self.catalog_items = [row for row in (self.catalog_items or []) if int(row.enabled or 0) == 1]
        self.save(ignore_permissions=True)
        return {"removed": before - len(self.catalog_items or [])}

    @frappe.whitelist()
    def get_readiness_report(self):
        issues = []
        enabled_rows = [row for row in (self.catalog_items or []) if int(row.enabled or 0) == 1]

        if not self.enabled:
            issues.append(_("Portal policy is disabled."))
        if not self.portal_price_list:
            issues.append(_("Portal price list is not set."))
        if not enabled_rows:
            issues.append(_("No enabled allowed products are configured."))

        missing_prices = []
        for row in enabled_rows:
            item_code = row.item_code
            if not item_code and row.product_bundle:
                item_code = frappe.db.get_value("Product Bundle", row.product_bundle, "new_item_code")
            if not item_code:
                issues.append(_("One allowed product row has no resolvable item."))
                continue
            if self.portal_price_list and not frappe.db.exists(
                "Item Price",
                {"item_code": item_code, "price_list": self.portal_price_list},
            ):
                missing_prices.append(item_code)

        if missing_prices:
            issues.append(_("Missing portal price for: {0}").format(", ".join(sorted(set(missing_prices)))))

        return {
            "ok": not issues,
            "issues": issues,
            "enabled_products": len(enabled_rows),
            "featured_products": len([row for row in enabled_rows if int(row.featured or 0) == 1]),
        }
