"""Market Price Entry controller.

Tracks competitor/market prices for items. Automatically calculates
the difference with our current cost price for comparison.
"""

import frappe
from frappe.model.document import Document


class MarketPriceEntry(Document):
    def validate(self):
        self._fetch_our_price()
        self._calculate_difference()

    def _fetch_our_price(self):
        """Fetch the item's current cost price for comparison."""
        if not self.item_code:
            self.our_current_price = 0
            return

        if not frappe.db.has_column("Item", "custom_current_cost_price"):
            # Field does not exist on this site yet; keep comparison safe.
            self.our_current_price = 0
            return

        our_price = frappe.db.get_value("Item", self.item_code, "custom_current_cost_price")
        self.our_current_price = our_price or 0

    def _calculate_difference(self):
        """Calculate price difference and percentage."""
        market = self.market_price or 0
        ours = self.our_current_price or 0

        self.price_difference = market - ours

        if ours > 0:
            self.price_difference_percent = ((market - ours) / ours) * 100
        else:
            self.price_difference_percent = 0
