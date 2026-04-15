"""Pricing Benchmark Policy controller.

Manages benchmark sources (which price lists to compare against)
and ratio-band rules (cost/benchmark ratio -> margin %).
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt


class PricingBenchmarkPolicy(Document):
    def validate(self):
        self.margin_application_basis = (self.margin_application_basis or "Base Price").strip() or "Base Price"
        self._sync_benchmark_basis()
        self._validate_sources()
        self._validate_rules()
        self._validate_tier_modifiers()
        self._validate_fallback_discount()
        self._validate_margin_application_basis()

    def _sync_benchmark_basis(self):
        active_types = []
        for row in self.benchmark_sources or []:
            if not cint(row.is_active):
                continue
            price_list = (row.price_list or "").strip()
            if not price_list:
                continue
            active_types.append(_price_list_type(price_list))

        normalized = {t for t in active_types if t in {"Buying", "Selling"}}
        if normalized == {"Buying"}:
            self.benchmark_basis = "Buying Supplier"
        elif normalized == {"Selling"}:
            self.benchmark_basis = "Selling Market"
        elif normalized:
            self.benchmark_basis = "Any List"
        else:
            self.benchmark_basis = self.benchmark_basis or "Selling Market"

    def _validate_sources(self):
        active = 0
        seen = set()
        basis = (self.benchmark_basis or "Selling Market").strip() or "Selling Market"
        source_type_values = []
        warnings = []

        for row in self.benchmark_sources or []:
            row.price_list = (row.price_list or "").strip()
            if not row.price_list:
                frappe.throw(_("Row {0}: Price List is required.").format(row.idx))
            if row.price_list in seen:
                frappe.throw(_("Row {0}: duplicate price list {1}.").format(row.idx, row.price_list))
            seen.add(row.price_list)

            row.source_kind = (row.source_kind or "").strip()
            row.weight = flt(row.weight) or 1.0

            price_list_type = _price_list_type(row.price_list)
            if not row.source_kind:
                row.source_kind = _default_source_kind(price_list_type)

            if cint(row.is_active):
                active += 1
                source_type_values.append(price_list_type)
                mismatch = _basis_mismatch(basis, price_list_type)
                if mismatch:
                    warnings.append(
                        _("Row {0}: source {1} is {2}, which may not fit Benchmark Basis '{3}'.").format(
                            row.idx,
                            row.price_list,
                            price_list_type,
                            basis,
                        )
                    )

        if active == 0:
            frappe.throw(_("At least one active benchmark source is required."))

        normalized_types = {t for t in source_type_values if t in {"Selling", "Buying"}}
        if basis == "Any List" and len(normalized_types) > 1:
            warnings.append(
                _("Active benchmark sources mix Buying and Selling lists. Results are valid but interpretation is mixed.")
            )

        if warnings:
            frappe.msgprint(
                "<br>".join(warnings),
                title=_("Benchmark Basis Warnings"),
                indicator="orange",
                alert=True,
            )

    def _validate_rules(self):
        active = 0
        for row in self.benchmark_rules or []:
            row.ratio_min = flt(row.ratio_min)
            row.ratio_max = flt(row.ratio_max)
            row.target_margin_percent = flt(row.target_margin_percent)
            row.priority = cint(row.priority or 10)
            row.sequence = cint(row.sequence or 90)

            if row.ratio_min < 0:
                frappe.throw(_("Row {0}: ratio_min cannot be negative.").format(row.idx))
            if row.ratio_max and row.ratio_max <= row.ratio_min:
                frappe.throw(_("Row {0}: ratio_max must be greater than ratio_min.").format(row.idx))
            if row.target_margin_percent < -100:
                frappe.throw(_("Row {0}: target margin cannot be below -100%.").format(row.idx))

            if cint(row.is_active):
                active += 1

        if active == 0:
            frappe.throw(_("At least one active benchmark rule is required."))

    def _validate_margin_application_basis(self):
        basis = (self.margin_application_basis or "Base Price").strip() or "Base Price"
        if basis not in {"Base Price", "Loaded Cost", "Sale Price"}:
            frappe.throw(_("Margin Application Basis must be Base Price, Loaded Cost, or Sale Price."))

        if basis != "Sale Price":
            return

        if flt(self.fallback_margin_percent) >= 100:
            frappe.throw(_("Fallback Margin % must be below 100 when Margin Application Basis is Sale Price."))

        for row in self.benchmark_rules or []:
            if cint(row.is_active) and flt(row.target_margin_percent) >= 100:
                frappe.throw(_("Row {0}: target margin must be below 100 when Margin Application Basis is Sale Price.").format(row.idx))

    def _validate_fallback_discount(self):
        fallback_max_discount = flt(self.fallback_max_discount_percent)
        if fallback_max_discount < 0:
            frappe.throw(_("Fallback Max Discount % cannot be negative."))
        if fallback_max_discount > 100:
            frappe.throw(_("Fallback Max Discount % cannot exceed 100%."))

    def _validate_tier_modifiers(self):
        seen = set()
        for row in self.tier_modifiers or []:
            row.customer_group = (row.customer_group or "").strip()
            row.tier = (row.tier or "").strip()
            row.modifier_type = (row.modifier_type or "Fixed").strip() or "Fixed"

            if not row.customer_group and not row.tier:
                frappe.throw(_("Row {0}: set Customer Group, Tier, or both for a dynamic modifier.").format(row.idx))

            key = (row.customer_group.lower(), row.tier.lower())
            if key in seen:
                if row.customer_group:
                    if row.tier:
                        frappe.throw(
                            _("Row {0}: duplicate tier modifier for Customer Group {1} and Tier {2}.").format(
                                row.idx,
                                row.customer_group,
                                row.tier,
                            )
                        )
                    frappe.throw(
                        _("Row {0}: duplicate customer-group modifier for Customer Group {1}.").format(
                            row.idx, row.customer_group
                        )
                    )
                frappe.throw(_("Row {0}: duplicate tier-only modifier for Tier {1}.").format(row.idx, row.tier))
            seen.add(key)


def _price_list_type(price_list_name):
    values = frappe.db.get_value("Price List", price_list_name, ["buying", "selling"], as_dict=True) or {}
    is_buying = cint(values.get("buying")) == 1
    is_selling = cint(values.get("selling")) == 1
    if is_buying and is_selling:
        return "Mixed"
    if is_buying:
        return "Buying"
    if is_selling:
        return "Selling"
    return "Unknown"


def _default_source_kind(price_list_type):
    if price_list_type == "Buying":
        return "Supplier"
    if price_list_type == "Selling":
        return "Competitor"
    return "Other"


def _basis_mismatch(basis, price_list_type):
    if basis == "Selling Market":
        return price_list_type in {"Buying", "Mixed", "Unknown"}
    if basis == "Buying Supplier":
        return price_list_type in {"Selling", "Mixed", "Unknown"}
    return False
