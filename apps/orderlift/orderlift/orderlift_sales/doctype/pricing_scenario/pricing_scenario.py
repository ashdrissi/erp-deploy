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
                "sequence": 10,
                "label": "Freight",
                "type": "Percentage",
                "value": 8,
                "applies_to": "Base Price",
                "scope": "Per Unit",
                "is_active": 1,
            },
            {
                "sequence": 20,
                "label": "Handling",
                "type": "Fixed",
                "value": 12,
                "applies_to": "Running Total",
                "scope": "Per Unit",
                "is_active": 1,
            },
            {
                "sequence": 30,
                "label": "Commercial Margin",
                "type": "Percentage",
                "value": 15,
                "applies_to": "Running Total",
                "scope": "Per Unit",
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
        seen_sequence = set()
        active_rows = 0

        for row in self.expenses:
            row.sequence = int(row.sequence or (row.idx * 10))
            if row.sequence <= 0:
                frappe.throw(_("Row {0}: Sequence must be greater than zero.").format(row.idx))
            if row.sequence in seen_sequence:
                frappe.throw(_("Duplicate sequence value: {0}").format(row.sequence))
            seen_sequence.add(row.sequence)

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

            row.scope = (row.scope or "Per Unit").strip().title()
            if row.scope not in ("Per Unit", "Per Line", "Per Sheet"):
                frappe.throw(_("Row {0}: Scope must be Per Unit, Per Line, or Per Sheet.").format(row.idx))
            if row.type == "Percentage" and row.scope != "Per Unit":
                frappe.throw(_("Row {0}: Percentage expenses only support Per Unit scope.").format(row.idx))

            row.value = flt(row.value)
            if row.type == "Percentage" and row.value < -100:
                frappe.throw(_("Row {0}: Percentage cannot be below -100.").format(row.idx))

            if flt(row.is_active):
                active_rows += 1

        if active_rows == 0:
            frappe.throw(_("At least one active expense is required."))
