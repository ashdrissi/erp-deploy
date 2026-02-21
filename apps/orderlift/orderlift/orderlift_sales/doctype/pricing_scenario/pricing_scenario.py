import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class PricingScenario(Document):
    def before_insert(self):
        if self.expenses:
            return

        default_expenses = [
            {
                "label": "Freight",
                "type": "Percentage",
                "value": 8,
                "applies_to": "Base Price",
                "is_active": 1,
            },
            {
                "label": "Handling",
                "type": "Fixed",
                "value": 12,
                "applies_to": "Running Total",
                "is_active": 1,
            },
            {
                "label": "Commercial Margin",
                "type": "Percentage",
                "value": 15,
                "applies_to": "Running Total",
                "is_active": 1,
            },
        ]

        for row in default_expenses:
            self.append("expenses", row)

    def validate(self):
        self.buying_price_list = self.buying_price_list or "Buying"
        self._validate_expenses()

    def _validate_expenses(self):
        if not self.expenses:
            frappe.throw(_("Please add at least one expense row."))

        seen_labels = set()
        active_rows = 0

        for row in self.expenses:
            label = (row.label or "").strip()
            if not label:
                frappe.throw(_("Row {0}: Label is required.").format(row.idx))

            label_key = label.lower()
            if label_key in seen_labels:
                frappe.throw(_("Duplicate expense label: {0}").format(label))
            seen_labels.add(label_key)

            row.label = label
            row.type = (row.type or "Percentage").strip().title()
            if row.type not in ("Percentage", "Fixed"):
                frappe.throw(_("Row {0}: Type must be Percentage or Fixed.").format(row.idx))

            row.applies_to = (row.applies_to or "Running Total").strip().title()
            if row.applies_to not in ("Base Price", "Running Total"):
                frappe.throw(_("Row {0}: Applies To must be Base Price or Running Total.").format(row.idx))

            row.value = flt(row.value)
            if row.type == "Percentage" and row.value < -100:
                frappe.throw(_("Row {0}: Percentage cannot be below -100.").format(row.idx))

            if flt(row.is_active):
                active_rows += 1

        if active_rows == 0:
            frappe.throw(_("At least one active expense is required."))
