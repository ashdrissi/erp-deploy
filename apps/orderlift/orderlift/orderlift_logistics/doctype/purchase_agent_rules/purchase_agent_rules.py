from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from orderlift.company_access import has_company_permission
from orderlift.menu_access import resolve_current_company
from orderlift.orderlift_sales.utils.price_list_scope import BUYING_PRICE_LIST, get_price_list_type
from orderlift.role_capabilities import CAPABILITY_PURCHASE_AGENT_RULES_MANAGEMENT, user_has_capability


class PurchaseAgentRules(Document):
    def before_validate(self):
        if not (self.company or "").strip():
            self.company = resolve_current_company(user=frappe.session.user)

    def validate(self):
        self._validate_purchase_user()
        self._validate_unique_enabled_rule()
        self._validate_buying_price_lists()

    def _validate_purchase_user(self):
        user = (self.purchase_user or "").strip()
        values = frappe.db.get_value("User", user, ["enabled", "user_type"], as_dict=True) if user else None
        if not values or not cint(values.get("enabled")):
            frappe.throw(_("Purchase User must be an enabled System User."))
        if values.get("user_type") != "System User" or user in {"Administrator", "Guest"}:
            frappe.throw(_("Purchase User must be an enabled System User."))

    def _validate_unique_enabled_rule(self):
        if not cint(self.enabled):
            return
        filters = {
            "purchase_user": self.purchase_user,
            "company": self.company,
            "enabled": 1,
            "name": ["!=", self.name or ""],
        }
        if frappe.db.exists("Purchase Agent Rules", filters):
            frappe.throw(_("An enabled Purchase Agent Rule already exists for this user and company."))

    def _validate_buying_price_lists(self):
        seen = set()
        active_defaults = 0
        for row in self.allowed_buying_price_lists or []:
            price_list = (row.buying_price_list or "").strip()
            if not price_list:
                continue
            if not cint(row.is_active):
                if cint(row.is_default):
                    frappe.throw(_("A default Buying Price List must be active."))
                continue
            if price_list in seen:
                frappe.throw(_("Buying Price List {0} is duplicated.").format(price_list))
            seen.add(price_list)
            self._validate_buying_price_list(price_list)
            if cint(row.is_active) and cint(row.is_default):
                active_defaults += 1
        if active_defaults > 1:
            frappe.throw(_("Only one active Buying Price List can be the default."))

    def _validate_buying_price_list(self, price_list):
        fields = ["enabled", "buying", "selling"]
        if frappe.db.has_column("Price List", "custom_price_list_type"):
            fields.append("custom_price_list_type")
        if frappe.db.has_column("Price List", "custom_company"):
            fields.append("custom_company")
        values = frappe.db.get_value("Price List", price_list, fields, as_dict=True)
        if not values or not cint(values.get("enabled", 1)):
            frappe.throw(_("Buying Price List {0} is unavailable.").format(price_list))
        if get_price_list_type(values=values) != BUYING_PRICE_LIST:
            frappe.throw(_("Price List {0} is not a Buying Price List.").format(price_list))
        if "custom_company" in fields and (values.get("custom_company") or "").strip() != self.company:
            frappe.throw(_("Buying Price List {0} does not belong to company {1}.").format(price_list, self.company))


def can_manage_purchase_agent_rules(user=None):
    return user_has_capability(CAPABILITY_PURCHASE_AGENT_RULES_MANAGEMENT, user=user)


def has_purchase_agent_rules_permission(doc=None, ptype=None, user=None, permission_type=None):
    user = user or frappe.session.user
    if not can_manage_purchase_agent_rules(user):
        return False
    if not doc:
        return True
    return has_company_permission(doc, ptype=ptype, user=user, permission_type=permission_type)
