# Copyright (c) 2026, Orderlift and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, cint, getdate, date_diff, now_datetime, nowdate

from orderlift.menu_access import get_allowed_companies, resolve_current_company, user_can_access_company


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
        self._validate_modifiers()

    def _validate_rules(self):
        """Check that all rule rows are properly configured."""
        for rule in self.segmentation_rules or []:
            if not rule.designated_segment:
                frappe.throw(_("Row {0}: Assign Pricing Tier is required.").format(rule.idx))
            self._validate_pricing_tier(rule)
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

    def _validate_pricing_tier(self, rule):
        tier = ((getattr(rule, "designated_segment", None) or getattr(rule, "tier", None) or "")).strip()
        if not tier or not frappe.db.exists("DocType", "Pricing Tier"):
            return
        is_active = frappe.db.get_value("Pricing Tier", tier, "is_active")
        if is_active is None:
            frappe.throw(_("Row {0}: Pricing Tier {1} does not exist.").format(rule.idx, tier))
        if cint(is_active) != 1:
            frappe.throw(_("Row {0}: Pricing Tier {1} is inactive.").format(rule.idx, tier))

    def _validate_modifiers(self):
        for row in self.tier_modifiers or []:
            row.modifier_type = (row.modifier_type or "Fixed").strip() or "Fixed"
            if row.modifier_type not in {"Fixed", "Percentage"}:
                frappe.throw(_("Tier Modifier row {0}: Type must be Fixed or Percentage.").format(row.idx))
            row.modifier_amount = flt(row.modifier_amount)
            if row.tier:
                self._validate_pricing_tier(row)

        for row in self.zone_modifiers or []:
            row.modifier_type = (row.modifier_type or "Fixed").strip() or "Fixed"
            if row.modifier_type not in {"Fixed", "Percentage"}:
                frappe.throw(_("Territory Modifier row {0}: Type must be Fixed or Percentage.").format(row.idx))
            row.modifier_amount = flt(row.modifier_amount)
            if not row.territory:
                frappe.throw(_("Territory Modifier row {0}: Territory is required.").format(row.idx))

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
        """Fetch customers matching optional CRM audience filters."""
        filters = {"disabled": 0}
        company = _engine_company(self)
        if company and frappe.db.has_column("Customer", "custom_company"):
            filters["custom_company"] = company

        business_type = (getattr(self, "business_type_filter", None) or "").strip()
        crm_segment = (getattr(self, "crm_segment_filter", None) or "").strip()
        if business_type or crm_segment:
            return self._get_crm_filtered_customers(filters, business_type, crm_segment)

        return frappe.get_all(
            "Customer",
            filters=filters,
            fields=["name", "customer_name", "creation", "territory"],
            order_by="name",
            limit_page_length=0,
        )

    def _get_crm_filtered_customers(self, filters, business_type, crm_segment):
        if not frappe.db.exists("DocType", "CRM Segment Assignment"):
            return []

        conditions = ["c.disabled = %(disabled)s"]
        values = {"disabled": filters["disabled"]}
        if filters.get("custom_company"):
            conditions.append("c.custom_company = %(company)s")
            values["company"] = filters["custom_company"]
        if business_type:
            conditions.append("csa.business_type = %(business_type)s")
            values["business_type"] = business_type
        if crm_segment:
            conditions.append("csa.segment = %(crm_segment)s")
            values["crm_segment"] = crm_segment

        return frappe.db.sql(
            f"""
            SELECT DISTINCT
                c.name,
                c.customer_name,
                c.creation,
                c.territory
            FROM `tabCustomer` c
            INNER JOIN `tabCRM Segment Assignment` csa
                ON csa.parent = c.name
                AND csa.parenttype = 'Customer'
            WHERE {' AND '.join(conditions)}
            ORDER BY c.name
            """,
            values,
            as_dict=True,
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
def get_segmentation_workspace():
    companies = get_allowed_companies(frappe.session.user)
    current_company = resolve_current_company(user=frappe.session.user, allowed_companies=companies)
    tabs = []
    for company in companies:
        engine = get_or_create_company_engine(company)
        tabs.append(_serialize_engine(engine))
    return {"companies": companies, "current_company": current_company, "tabs": tabs}


@frappe.whitelist()
def save_company_segmentation(company, payload):
    company = (company or "").strip()
    _require_company_access(company)
    payload = frappe.parse_json(payload or {}) or {}
    engine = get_or_create_company_engine(company)
    engine.engine_name = (payload.get("engine_name") or engine.engine_name or f"Customer Segmentation - {company}").strip()
    engine.business_type_filter = (payload.get("business_type_filter") or "").strip()
    engine.crm_segment_filter = (payload.get("crm_segment_filter") or "").strip()
    engine.is_active = 1 if cint(payload.get("is_active", 1)) else 0
    engine.description = payload.get("description") or ""
    engine.set("segmentation_rules", [])
    for row in payload.get("segmentation_rules") or []:
        engine.append("segmentation_rules", _clean_segmentation_rule(row))
    engine.set("tier_modifiers", [])
    for row in payload.get("tier_modifiers") or []:
        engine.append("tier_modifiers", _clean_tier_modifier(row))
    engine.set("zone_modifiers", [])
    for row in payload.get("zone_modifiers") or []:
        engine.append("zone_modifiers", _clean_zone_modifier(row))
    engine.save(ignore_permissions=True)
    frappe.db.commit()
    return {"engine": _serialize_engine(engine)}


@frappe.whitelist()
def calculate_company_segmentation(company):
    company = (company or "").strip()
    _require_company_access(company)
    engine = get_or_create_company_engine(company)
    return {"results": engine.calculate_segments(), "engine": _serialize_engine(engine)}


@frappe.whitelist()
def apply_company_segmentation(company):
    company = (company or "").strip()
    _require_company_access(company)
    engine = get_or_create_company_engine(company)
    return {"results": engine.apply_segments(), "engine": _serialize_engine(engine)}


def get_or_create_company_engine(company):
    company = (company or "").strip()
    _require_company_access(company)
    return _get_or_create_company_engine_unchecked(company)


def _get_or_create_company_engine_unchecked(company):
    company = (company or "").strip()
    filters = {"custom_company": company} if frappe.db.has_column("Customer Segmentation Engine", "custom_company") else {"engine_name": f"Customer Segmentation - {company}"}
    existing = frappe.db.get_value("Customer Segmentation Engine", filters, "name")
    if existing:
        return frappe.get_doc("Customer Segmentation Engine", existing)

    engine = frappe.new_doc("Customer Segmentation Engine")
    engine.engine_name = f"Customer Segmentation - {company}"
    engine.is_active = 1
    if frappe.db.has_column("Customer Segmentation Engine", "custom_company"):
        engine.custom_company = company
    engine.append("segmentation_rules", {
        "designated_segment": _first_active_pricing_tier(),
        "is_default": 1,
        "priority": 100,
        "is_active": 1,
    })
    engine.insert(ignore_permissions=True)
    frappe.db.commit()
    return engine


def after_migrate():
    sync_company_segmentation_engines()
    frappe.db.commit()


def sync_company_segmentation_engines():
    if not frappe.db.exists("DocType", "Customer Segmentation Engine"):
        return {"skipped": True, "reason": "missing Customer Segmentation Engine"}
    if not frappe.db.exists("DocType", "Company"):
        return {"skipped": True, "reason": "missing Company"}

    companies = frappe.get_all("Company", pluck="name", limit_page_length=0)
    created_or_existing = 0
    for company in companies:
        _get_or_create_company_engine_unchecked(company)
        created_or_existing += 1

    copied = _copy_benchmark_modifiers_to_company_engines(companies)
    return {"companies": created_or_existing, "copied_modifiers": copied}


def _copy_benchmark_modifiers_to_company_engines(companies):
    if not frappe.db.exists("DocType", "Pricing Benchmark Policy"):
        return 0
    company_set = set(companies or [])
    default_company = frappe.db.get_single_value("Global Defaults", "default_company") or (companies[0] if companies else "")
    policies = frappe.get_all(
        "Pricing Benchmark Policy",
        fields=["name", "company"],
        limit_page_length=0,
    )
    copied = 0
    for policy_row in policies:
        policy = frappe.get_doc("Pricing Benchmark Policy", policy_row.name)
        if not (policy.get("tier_modifiers") or policy.get("zone_modifiers")):
            continue
        company = (policy.get("company") or default_company or "").strip()
        if company_set and company not in company_set:
            continue
        engine = _get_or_create_company_engine_unchecked(company)
        existing_tiers = {
            (
                (row.get("business_type") or "").strip(),
                (row.get("crm_segment") or "").strip(),
                (row.get("tier") or "").strip(),
                flt(row.get("modifier_amount")),
                (row.get("modifier_type") or "Fixed").strip(),
            )
            for row in (engine.get("tier_modifiers") or [])
        }
        existing_zones = {
            (
                (row.get("territory") or "").strip(),
                flt(row.get("modifier_amount")),
                (row.get("modifier_type") or "Fixed").strip(),
            )
            for row in (engine.get("zone_modifiers") or [])
        }
        changed = False
        for row in policy.get("tier_modifiers") or []:
            key = (
                (row.get("business_type") or "").strip(),
                (row.get("crm_segment") or "").strip(),
                (row.get("tier") or "").strip(),
                flt(row.get("modifier_amount")),
                (row.get("modifier_type") or "Fixed").strip(),
            )
            if key in existing_tiers:
                continue
            engine.append("tier_modifiers", {
                "business_type": key[0],
                "crm_segment": key[1],
                "tier": key[2],
                "modifier_amount": key[3],
                "modifier_type": key[4],
                "is_active": 1 if cint(row.get("is_active")) else 0,
            })
            existing_tiers.add(key)
            copied += 1
            changed = True
        for row in policy.get("zone_modifiers") or []:
            key = (
                (row.get("territory") or "").strip(),
                flt(row.get("modifier_amount")),
                (row.get("modifier_type") or "Fixed").strip(),
            )
            if key in existing_zones:
                continue
            engine.append("zone_modifiers", {
                "territory": key[0],
                "modifier_amount": key[1],
                "modifier_type": key[2],
                "is_active": 1 if cint(row.get("is_active")) else 0,
            })
            existing_zones.add(key)
            copied += 1
            changed = True
        if changed:
            engine.save(ignore_permissions=True)
    return copied


def resolve_global_pricing_modifiers(company=None, tier=None, business_type=None, crm_segment=None, territory=None):
    company = (company or "").strip()
    if not company:
        return None, None, ""
    engine_name = frappe.db.get_value(
        "Customer Segmentation Engine",
        {"custom_company": company, "is_active": 1} if frappe.db.has_column("Customer Segmentation Engine", "custom_company") else {"is_active": 1},
        "name",
    )
    if not engine_name:
        return None, None, ""
    engine = frappe.get_doc("Customer Segmentation Engine", engine_name)
    tier_mod = _match_tier_modifier(engine, tier, business_type, crm_segment)
    zone_mod = _match_zone_modifier(engine, territory)
    return tier_mod, zone_mod, ""


def _serialize_engine(engine):
    return {
        "name": engine.name,
        "company": _engine_company(engine),
        "engine_name": engine.engine_name or engine.name,
        "business_type_filter": engine.business_type_filter or "",
        "crm_segment_filter": engine.crm_segment_filter or "",
        "is_active": 1 if cint(engine.is_active) else 0,
        "description": engine.description or "",
        "segmentation_rules": [_serialize_segmentation_rule(row) for row in (engine.segmentation_rules or [])],
        "tier_modifiers": [_serialize_tier_modifier(row) for row in (engine.tier_modifiers or [])],
        "zone_modifiers": [_serialize_zone_modifier(row) for row in (engine.zone_modifiers or [])],
    }


def _serialize_segmentation_rule(row):
    return {
        "designated_segment": _row_value(row, "designated_segment") or "",
        "is_default": 1 if cint(_row_value(row, "is_default")) else 0,
        "priority": cint(_row_value(row, "priority") or 10),
        "is_active": 1 if cint(_row_value(row, "is_active", 1)) else 0,
        "variable_1": _row_value(row, "variable_1") or "",
        "operator_1": _row_value(row, "operator_1") or "",
        "value_1": flt(_row_value(row, "value_1")),
        "connector": _row_value(row, "connector") or "",
        "variable_2": _row_value(row, "variable_2") or "",
        "operator_2": _row_value(row, "operator_2") or "",
        "value_2": flt(_row_value(row, "value_2")),
    }


def _serialize_tier_modifier(row):
    return {
        "business_type": _row_value(row, "business_type") or "",
        "crm_segment": _row_value(row, "crm_segment") or "",
        "tier": _row_value(row, "tier") or "",
        "modifier_amount": flt(_row_value(row, "modifier_amount")),
        "modifier_type": _row_value(row, "modifier_type") or "Fixed",
        "is_active": 1 if cint(_row_value(row, "is_active", 1)) else 0,
    }


def _serialize_zone_modifier(row):
    return {
        "territory": _row_value(row, "territory") or "",
        "modifier_amount": flt(_row_value(row, "modifier_amount")),
        "modifier_type": _row_value(row, "modifier_type") or "Fixed",
        "is_active": 1 if cint(_row_value(row, "is_active", 1)) else 0,
    }


def _clean_segmentation_rule(row):
    return _serialize_segmentation_rule(row)


def _clean_tier_modifier(row):
    return _serialize_tier_modifier(row)


def _clean_zone_modifier(row):
    return _serialize_zone_modifier(row)


def _row_value(row, fieldname, default=None):
    if isinstance(row, dict):
        return row.get(fieldname, default)
    getter = getattr(row, "get", None)
    if callable(getter):
        return getter(fieldname, default)
    return getattr(row, fieldname, default)


def _match_tier_modifier(engine, tier, business_type, crm_segment):
    tier = (tier or "").strip()
    business_type = (business_type or "").strip()
    crm_segment = (crm_segment or "").strip()
    candidates = []
    for row in engine.tier_modifiers or []:
        if not cint(row.is_active):
            continue
        row_tier = (row.tier or "").strip()
        row_business_type = (row.business_type or "").strip()
        row_crm_segment = (row.crm_segment or "").strip()
        if row_tier and row_tier != tier:
            continue
        if row_business_type and row_business_type != business_type:
            continue
        if row_crm_segment and row_crm_segment != crm_segment:
            continue
        score = 0
        if row_crm_segment:
            score += 16
        if row_business_type:
            score += 8
        if row_tier:
            score += 4
        if not score:
            continue
        candidates.append((-score, cint(row.idx or 0), row))
    if not candidates:
        return None
    selected = sorted(candidates, key=lambda item: (item[0], item[1]))[0][2]
    parts = []
    if selected.business_type:
        parts.append("Business Type: {}".format(selected.business_type))
    if selected.crm_segment:
        parts.append("CRM Segment: {}".format(selected.crm_segment))
    if selected.tier:
        parts.append("Tier: {}".format(selected.tier))
    return {"amount": flt(selected.modifier_amount), "type": selected.modifier_type or "Fixed", "label": " / ".join(parts)}


def _match_zone_modifier(engine, territory):
    territory = (territory or "").strip()
    if not territory:
        return None
    for row in engine.zone_modifiers or []:
        if not cint(row.is_active):
            continue
        if (row.territory or "").strip() != territory:
            continue
        return {"amount": flt(row.modifier_amount), "type": row.modifier_type or "Fixed", "label": "Zone: {}".format(territory)}
    return None


def _first_active_pricing_tier():
    if not frappe.db.exists("DocType", "Pricing Tier"):
        return ""
    return frappe.db.get_value("Pricing Tier", {"is_active": 1}, "name", order_by="sequence asc, name asc") or ""


def _engine_company(engine):
    if frappe.db.has_column("Customer Segmentation Engine", "custom_company"):
        return (engine.get("custom_company") or "").strip()
    return ""


def _require_company_access(company):
    if not company:
        frappe.throw(_("Company is required."))
    if not user_can_access_company(company):
        frappe.throw(_("You do not have access to company {0}.").format(company), frappe.PermissionError)


@frappe.whitelist()
def get_customer_group_tiers(customer_group=None):
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


@frappe.whitelist()
def get_crm_context_tiers(business_type=None, crm_segment=None):
    business_type = (business_type or "").strip()
    crm_segment = (crm_segment or "").strip()
    conditions = ["is_active = 1"]
    values = {}
    if business_type:
        conditions.append("(COALESCE(business_type_filter, '') = '' OR business_type_filter = %(business_type)s)")
        values["business_type"] = business_type
    if crm_segment:
        conditions.append("(COALESCE(crm_segment_filter, '') = '' OR crm_segment_filter = %(crm_segment)s)")
        values["crm_segment"] = crm_segment

    active_engines = frappe.db.sql(
        f"""
        SELECT name
        FROM `tabCustomer Segmentation Engine`
        WHERE {' AND '.join(conditions)}
        """,
        values,
        pluck=True,
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


@frappe.whitelist()
def calculate_customer_dynamic_tier(customer=None, apply=0):
    customer = (customer or "").strip()
    if not customer:
        return _dynamic_tier_result(
            status="missing_customer",
            message=_("Save the customer before calculating a dynamic pricing tier."),
        )
    if not frappe.db.exists("Customer", customer):
        frappe.throw(_("Customer {0} was not found.").format(customer))

    context = _get_customer_crm_context(customer)
    business_type = context.get("business_type") or ""
    crm_segment = context.get("crm_segment") or ""
    company = _get_customer_company(customer)
    if not business_type or not crm_segment:
        return _apply_dynamic_tier_result(
            customer,
            _dynamic_tier_result(
                status="missing_context",
                business_type=business_type,
                crm_segment=crm_segment,
                message=_(
                    "Missing CRM Business Type or CRM Segment. Add both values before calculating a dynamic pricing tier."
                ),
            ),
            apply=apply,
        )

    engines = _get_matching_engines(business_type, crm_segment, company=company)
    if not engines:
        return _apply_dynamic_tier_result(
            customer,
            _dynamic_tier_result(
                status="missing_engine",
                business_type=business_type,
                crm_segment=crm_segment,
                message=_(
                    "No active segmentation engine matches Business Type {0} / Segment {1}. Add a matching segmentation policy before calculating a dynamic pricing tier."
                ).format(business_type, crm_segment),
            ),
            apply=apply,
        )

    customer_row = frappe.db.get_value(
        "Customer",
        customer,
        ["name", "customer_name", "creation", "territory"],
        as_dict=True,
    ) or {"name": customer}

    evaluated = []
    for engine_row in engines:
        engine = frappe.get_doc("Customer Segmentation Engine", engine_row.name)
        variables = engine._build_customer_variables(customer_row)
        tier, rule_idx, confidence = engine._evaluate_rules(variables)
        if tier:
            rule_label = _format_matched_rule(engine, rule_idx)
            return _apply_dynamic_tier_result(
                customer,
                _dynamic_tier_result(
                    status="matched",
                    tier=tier,
                    engine=engine.name,
                    engine_name=engine.engine_name or engine.name,
                    matched_rule=rule_label,
                    matched_rule_idx=rule_idx,
                    confidence=confidence,
                    business_type=business_type,
                    crm_segment=crm_segment,
                    variables=variables,
                    message=_(
                        "Dynamic Pricing Tier {0} matched by {1} for Business Type {2} / Segment {3}."
                    ).format(tier, rule_label, business_type, crm_segment),
                ),
                apply=apply,
            )
        evaluated.append(engine.engine_name or engine.name)

    return _apply_dynamic_tier_result(
        customer,
        _dynamic_tier_result(
            status="missing_rule",
            business_type=business_type,
            crm_segment=crm_segment,
            evaluated_engines=evaluated,
            message=_(
                "No active segmentation rule matched Business Type {0} / Segment {1}. Dynamic pricing tier was not calculated."
            ).format(business_type, crm_segment),
        ),
        apply=apply,
    )


def _dynamic_tier_result(**values):
    result = {
        "status": "",
        "tier": "",
        "engine": "",
        "engine_name": "",
        "matched_rule": "",
        "matched_rule_idx": "",
        "business_type": "",
        "crm_segment": "",
        "message": "",
        "variables": {},
        "evaluated_engines": [],
    }
    result.update(values)
    return result


def _apply_dynamic_tier_result(customer, result, apply=0):
    if not cint(apply):
        return result

    values = {}
    if frappe.db.has_column("Customer", "tier"):
        values["tier"] = result.get("tier") or ""
    if frappe.db.has_column("Customer", "tier_source"):
        values["tier_source"] = result.get("engine_name") or "No Dynamic Tier Rule"
    if frappe.db.has_column("Customer", "tier_last_calculated_on"):
        values["tier_last_calculated_on"] = now_datetime()

    if values:
        frappe.db.set_value("Customer", customer, values, update_modified=False)
        frappe.db.commit()
    return result


def _get_customer_crm_context(customer):
    if not frappe.db.exists("DocType", "CRM Segment Assignment"):
        return {"business_type": "", "crm_segment": ""}

    rows = frappe.get_all(
        "CRM Segment Assignment",
        filters={"parenttype": "Customer", "parent": customer},
        fields=["business_type", "segment", "is_primary", "idx"],
        order_by="is_primary desc, idx asc",
        limit_page_length=0,
    )
    for row in rows:
        business_type = (row.get("business_type") or "").strip()
        crm_segment = (row.get("segment") or "").strip()
        if business_type or crm_segment:
            return {"business_type": business_type, "crm_segment": crm_segment}
    return {"business_type": "", "crm_segment": ""}


def _get_matching_engines(business_type, crm_segment, company=None):
    filters = {"is_active": 1}
    fields = ["name", "engine_name", "business_type_filter", "crm_segment_filter"]
    if company and frappe.db.has_column("Customer Segmentation Engine", "custom_company"):
        filters["custom_company"] = company
        fields.append("custom_company")
    rows = frappe.get_all(
        "Customer Segmentation Engine",
        filters=filters,
        fields=fields,
        limit_page_length=0,
    )
    candidates = []
    for row in rows:
        row_business_type = (row.get("business_type_filter") or "").strip()
        row_crm_segment = (row.get("crm_segment_filter") or "").strip()
        if row_business_type and row_business_type != business_type:
            continue
        if row_crm_segment and row_crm_segment != crm_segment:
            continue
        score = 0
        if row_business_type:
            score += 2
        if row_crm_segment:
            score += 1
        candidates.append((-score, row.get("engine_name") or row.get("name"), row))

    return [item[2] for item in sorted(candidates, key=lambda item: (item[0], item[1]))]


def _get_customer_company(customer):
    if not customer or not frappe.db.has_column("Customer", "custom_company"):
        return ""
    return (frappe.db.get_value("Customer", customer, "custom_company") or "").strip()


def _format_matched_rule(engine, rule_idx):
    for rule in engine.segmentation_rules or []:
        if cint(rule.idx) != cint(rule_idx):
            continue
        if cint(rule.is_default):
            return _("rule {0} catch-all").format(rule.idx)
        conditions = [
            _format_rule_condition(rule.variable_1, rule.operator_1, rule.value_1),
        ]
        if rule.connector:
            conditions.append(rule.connector)
            conditions.append(_format_rule_condition(rule.variable_2, rule.operator_2, rule.value_2))
        return _("rule {0}: {1}").format(rule.idx, " ".join([part for part in conditions if part]))
    return _("rule {0}").format(rule_idx or "-")


def _format_rule_condition(variable, operator, value):
    variable = (variable or "").strip()
    operator = (operator or "").strip()
    if not variable or not operator:
        return ""
    return "{0} {1} {2:g}".format(variable, operator, flt(value))
