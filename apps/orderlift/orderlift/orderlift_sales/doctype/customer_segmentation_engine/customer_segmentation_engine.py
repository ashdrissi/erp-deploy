# Copyright (c) 2026, Orderlift and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, cint, getdate, date_diff, nowdate


# Maps user-friendly Select labels → internal variable names
VARIABLE_MAP = {
    "Revenue (12 months)": "Revenue_12M",
    "RFM Score": "RFM_score",
    "Customer Age (Days)": "Customer_Age_Days",
    "Total Orders": "Total_Orders",
}

# Maps user-friendly operator labels → Python operators
OPERATOR_MAP = {
    "≥ (greater or equal)": ">=",
    "> (greater than)": ">",
    "≤ (less or equal)": "<=",
    "< (less than)": "<",
    "= (equals)": "==",
    "≠ (not equal)": "!=",
}


class CustomerSegmentationEngine(Document):
    """Rules engine for auto-assigning customer segments/tiers.

    Each rule uses structured dropdowns (variable, operator, value).
    Rules are evaluated top-down by priority — first match wins.
    """

    def validate(self):
        self._validate_rules()

    def _validate_rules(self):
        """Check that all rule rows are properly configured."""
        for rule in self.segmentation_rules or []:
            if not rule.designated_segment:
                frappe.throw(_("Row {0}: Assign Segment is required.").format(rule.idx))
            if rule.is_default:
                continue
            if not rule.variable_1 or not rule.operator_1:
                frappe.throw(
                    _("Row {0}: First condition (If / Is / Value) is required unless Catch-All is checked.").format(rule.idx)
                )
            if rule.connector:
                if not rule.variable_2 or not rule.operator_2:
                    frappe.throw(
                        _("Row {0}: Second condition is required when AND/OR connector is set.").format(rule.idx)
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
                    is_dynamic = 1
                    if frappe.db.has_column("Customer", "enable_dynamic_segmentation"):
                        is_dynamic = cint(
                            frappe.db.get_value(
                                "Customer", r["customer"], "enable_dynamic_segmentation"
                            )
                            or 0
                        )
                    if is_dynamic != 1:
                        continue

                    values = {"tier": r["assigned_segment"]}
                    if frappe.db.has_column("Customer", "tier_source"):
                        values["tier_source"] = self.engine_name or self.name
                    if frappe.db.has_column("Customer", "tier_last_calculated_on"):
                        values["tier_last_calculated_on"] = frappe.utils.now_datetime()

                    frappe.db.set_value("Customer", r["customer"], values, update_modified=False)
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
        """Fetch customers matching the target customer group."""
        filters = {"disabled": 0}
        if self.target_customer_type:
            filters["customer_group"] = self.target_customer_type

        return frappe.get_all(
            "Customer",
            filters=filters,
            fields=["name", "customer_name", "customer_group", "creation", "territory"],
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

        # Simple RFM proxy (0-10 scale)
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
            if rule.is_default:
                return rule.designated_segment, rule.idx, 100

            try:
                result = self._eval_structured_rule(rule, variables)
                if result:
                    return rule.designated_segment, rule.idx, 100
            except Exception:
                continue

        return None, None, 0

    def _eval_structured_rule(self, rule, variables):
        """Evaluate a structured rule (dropdown-based) against variables."""
        # Resolve first condition
        var_key_1 = VARIABLE_MAP.get(rule.variable_1)
        op_1 = OPERATOR_MAP.get(rule.operator_1)
        if not var_key_1 or not op_1:
            return False

        val_1 = flt(variables.get(var_key_1, 0))
        threshold_1 = flt(rule.value_1)
        result_1 = self._compare(val_1, op_1, threshold_1)

        # Single condition
        if not rule.connector:
            return result_1

        # Resolve second condition
        var_key_2 = VARIABLE_MAP.get(rule.variable_2)
        op_2 = OPERATOR_MAP.get(rule.operator_2)
        if not var_key_2 or not op_2:
            return result_1

        val_2 = flt(variables.get(var_key_2, 0))
        threshold_2 = flt(rule.value_2)
        result_2 = self._compare(val_2, op_2, threshold_2)

        if rule.connector == "AND":
            return result_1 and result_2
        elif rule.connector == "OR":
            return result_1 or result_2

        return result_1

    @staticmethod
    def _compare(actual, operator, threshold):
        """Safe comparison without eval."""
        if operator == ">=":
            return actual >= threshold
        elif operator == ">":
            return actual > threshold
        elif operator == "<=":
            return actual <= threshold
        elif operator == "<":
            return actual < threshold
        elif operator == "==":
            return actual == threshold
        elif operator == "!=":
            return actual != threshold
        return False


@frappe.whitelist()
def get_customer_group_tiers(customer_group=None):
    customer_group = (customer_group or "").strip()
    if customer_group:
        active_engines = frappe.get_all(
            "Customer Segmentation Engine",
            filters={"is_active": 1, "target_customer_type": customer_group},
            pluck="name",
            limit_page_length=0,
        )

        if not active_engines:
            active_engines = frappe.get_all(
                "Customer Segmentation Engine",
                filters={"is_active": 1, "target_customer_type": ["in", ["", None]]},
                pluck="name",
                limit_page_length=0,
            )
    else:
        active_engines = frappe.get_all(
            "Customer Segmentation Engine",
            filters={"is_active": 1},
            pluck="name",
            limit_page_length=0,
        )

    tiers = set()
    for engine_name in active_engines:
        rows = frappe.get_all(
            "Customer Segmentation Rule",
            filters={"parent": engine_name, "is_active": 1},
            fields=["designated_segment", "priority"],
            order_by="priority asc, idx asc",
            limit_page_length=0,
        )
        for row in rows:
            value = (row.get("designated_segment") or "").strip()
            if value:
                tiers.add(value)

    return sorted(tiers)
