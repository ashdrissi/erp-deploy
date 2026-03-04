# Copyright (c) 2026, Orderlift and contributors
# For license information, please see license.txt

import re
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, cint, getdate, date_diff, nowdate


class CustomerSegmentationEngine(Document):
    """Rules engine for auto-assigning customer segments/tiers.

    Each rule has a condition string evaluated against customer variables.
    Rules are evaluated top-down by priority — first match wins.
    """

    def validate(self):
        self._validate_rules()

    def _validate_rules(self):
        """Check that all rule conditions are syntactically valid."""
        for rule in self.segmentation_rules or []:
            condition = (rule.condition or "").strip()
            if not condition:
                frappe.throw(_("Row {0}: Condition cannot be empty.").format(rule.idx))
            if condition.upper() == "DEFAULT":
                continue
            # Quick syntax check by attempting parse
            try:
                self._parse_condition(condition)
            except Exception as e:
                frappe.throw(
                    _("Row {0}: Invalid condition syntax: {1}").format(rule.idx, str(e))
                )

    @frappe.whitelist()
    def calculate_segments(self):
        """Run the engine against all matching customers and return results."""
        if not self.is_active:
            frappe.throw(_("This engine is not active."))

        customers = self._get_target_customers()
        results = []
        for cust in customers:
            variables = self._build_customer_variables(cust)
            segment, rule_idx, confidence = self._evaluate_rules(variables)
            results.append({
                "customer": cust.get("name"),
                "customer_name": cust.get("customer_name"),
                "assigned_segment": segment,
                "matched_rule": rule_idx,
                "variables": variables,
                "confidence": confidence,
            })

        return results

    @frappe.whitelist()
    def apply_segments(self):
        """Run the engine and update customer records with assigned tiers."""
        results = self.calculate_segments()
        updated = 0
        for r in results:
            if r["assigned_segment"]:
                try:
                    frappe.db.set_value(
                        "Customer", r["customer"], "tier", r["assigned_segment"],
                        update_modified=False,
                    )
                    updated += 1
                except Exception:
                    pass

        frappe.db.commit()
        frappe.msgprint(
            _("Segmentation complete. Updated {0} of {1} customers.").format(
                updated, len(results)
            )
        )
        return results

    def _get_target_customers(self):
        """Fetch customers matching the target type."""
        filters = {"disabled": 0}
        if self.target_customer_type:
            filters["customer_type"] = self.target_customer_type

        return frappe.get_all(
            "Customer",
            filters=filters,
            fields=["name", "customer_name", "customer_type", "creation",
                     "territory", "customer_group"],
            order_by="name",
            limit_page_length=0,
        )

    def _build_customer_variables(self, customer):
        """Build evaluation variables for a customer."""
        customer_name = customer.get("name")
        creation = customer.get("creation")
        age_days = date_diff(nowdate(), getdate(creation)) if creation else 0

        # Revenue last 12 months
        revenue_12m = flt(frappe.db.sql("""
            SELECT COALESCE(SUM(grand_total), 0)
            FROM `tabSales Order`
            WHERE customer = %s
            AND transaction_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            AND docstatus = 1
        """, customer_name)[0][0]) if customer_name else 0

        # Total orders
        total_orders = cint(frappe.db.sql("""
            SELECT COUNT(*)
            FROM `tabSales Order`
            WHERE customer = %s AND docstatus = 1
        """, customer_name)[0][0]) if customer_name else 0

        # Simple RFM proxy (0-10 scale based on recency + frequency + monetary)
        rfm_score = self._compute_rfm_score(customer_name, revenue_12m, total_orders, age_days)

        return {
            "Revenue_12M": revenue_12m,
            "RFM_score": rfm_score,
            "Customer_Age_Days": age_days,
            "Total_Orders": total_orders,
        }

    def _compute_rfm_score(self, customer_name, revenue_12m, total_orders, age_days):
        """Compute a simple RFM proxy score (0-10)."""
        score = 0.0

        # Recency: days since last order
        last_order = frappe.db.sql("""
            SELECT MAX(transaction_date)
            FROM `tabSales Order`
            WHERE customer = %s AND docstatus = 1
        """, customer_name)
        if last_order and last_order[0][0]:
            recency_days = date_diff(nowdate(), getdate(last_order[0][0]))
            if recency_days <= 30:
                score += 3.3
            elif recency_days <= 90:
                score += 2.5
            elif recency_days <= 180:
                score += 1.5
            else:
                score += 0.5

        # Frequency
        if total_orders >= 20:
            score += 3.3
        elif total_orders >= 10:
            score += 2.5
        elif total_orders >= 5:
            score += 1.5
        elif total_orders >= 1:
            score += 0.5

        # Monetary
        if revenue_12m >= 2000000:
            score += 3.4
        elif revenue_12m >= 800000:
            score += 2.5
        elif revenue_12m >= 200000:
            score += 1.5
        elif revenue_12m > 0:
            score += 0.5

        return round(min(score, 10.0), 1)

    def _evaluate_rules(self, variables):
        """Evaluate rules top-down by priority. Return (segment, rule_idx, confidence)."""
        active_rules = sorted(
            [r for r in (self.segmentation_rules or []) if r.is_active],
            key=lambda r: cint(r.priority),
        )

        for rule in active_rules:
            condition = (rule.condition or "").strip()
            if condition.upper() == "DEFAULT":
                return rule.designated_segment, rule.idx, 100
            try:
                result = self._eval_condition(condition, variables)
                if result:
                    return rule.designated_segment, rule.idx, 100
            except Exception:
                continue

        return None, None, 0

    def _eval_condition(self, condition, variables):
        """Safely evaluate a condition string against variables.

        Supports: >=, <=, >, <, ==, !=, AND, OR, NOT, parentheses
        Variables: Revenue_12M, RFM_score, Customer_Age_Days, Total_Orders
        """
        parsed = self._parse_condition(condition)
        # Safe eval with only allowed variables
        safe_dict = {k: v for k, v in variables.items()}
        return bool(eval(parsed, {"__builtins__": {}}, safe_dict))  # noqa: S307

    def _parse_condition(self, condition):
        """Parse user-friendly condition to safe Python expression."""
        expr = condition.strip()

        # Normalize logical operators (case-insensitive)
        expr = re.sub(r'\bAND\b', ' and ', expr, flags=re.IGNORECASE)
        expr = re.sub(r'\bOR\b', ' or ', expr, flags=re.IGNORECASE)
        expr = re.sub(r'\bNOT\b', ' not ', expr, flags=re.IGNORECASE)

        # Only allow safe tokens: numbers, variable names, operators, parens
        allowed = re.compile(
            r'^[\s\d\w_.>=<!()and or not+-]+$', re.IGNORECASE
        )
        if not allowed.match(expr):
            raise ValueError("Unsafe characters in condition: {}".format(expr))

        # Block dangerous builtins
        dangerous = ['import', 'exec', 'eval', 'open', 'os', 'sys', '__']
        for d in dangerous:
            if d in expr.lower():
                raise ValueError("Forbidden keyword: {}".format(d))

        return expr
