# Copyright (c) 2026, Orderlift and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AgentPricingRules(Document):
    def validate(self):
        if self.pricing_mode == "Dynamic Calculation Engine":
            if not self.default_buying_price_list:
                frappe.throw("Base Buying Price List is required for Dynamic Calculation mode.")
