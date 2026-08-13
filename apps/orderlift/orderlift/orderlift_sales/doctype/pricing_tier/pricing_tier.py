import frappe
from frappe import _
from frappe.model.document import Document

from orderlift.reference_access import get_reference_options


PROTECTED_TIER = "New"


class PricingTier(Document):
    def validate(self):
        if self.name == PROTECTED_TIER or self.tier_name == PROTECTED_TIER:
            self.tier_name = PROTECTED_TIER
            self.is_active = 1

    def before_delete(self):
        self._prevent_protected_delete()

    def on_trash(self):
        self._prevent_protected_delete()

    def _prevent_protected_delete(self):
        if self.name == PROTECTED_TIER or self.tier_name == PROTECTED_TIER:
            frappe.throw(_("Pricing Tier {0} is required and cannot be deleted.").format(PROTECTED_TIER))


@frappe.whitelist()
def get_active_pricing_tiers() -> list[str]:
    return [row.name for row in get_reference_options(
        "Pricing Tier",
        filters={"is_active": 1},
        fields=["name"],
        order_by="sequence asc, name asc",
    )]
