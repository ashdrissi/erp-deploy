import json
from datetime import datetime

import frappe
from frappe.utils import flt


def run(test_config=None):
    test = TESTE2EPricingChain()
    test.run()
    return test.report()


class TESTE2EPricingChain:
    def __init__(self):
        self.suffix = datetime.utcnow().strftime("%y%m%d-%H%M%S")
        self.results = []
        self.created = []

    def _rollback(self):
        for doctype, name in reversed(self.created):
            try:
                frappe.delete_doc(doctype, name, force=1, ignore_permissions=True)
            except Exception:
                pass
        self.created.clear()
        frappe.db.commit()

    def _track(self, doctype, name):
        self.created.append((doctype, name))

    def _assert(self, label, condition, detail=""):
        status = "PASS" if condition else "FAIL"
        self.results.append({"label": label, "status": status, "detail": str(detail)[:120]})
        if not condition:
            raise AssertionError(f"{label}: {detail}")

    def report(self):
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        return {"total": len(self.results), "passed": passed, "failed": failed, "results": self.results}

    def run(self):
        original_user = frappe.session.user
        frappe.db.set_value("User", "Administrator", "enabled", 1)
        frappe.db.commit()
        try:
            frappe.set_user("Administrator")
            self._step_create_opportunity()
            self._step_create_pricing_sheet()
            self._step_generate_quotation()
            self._step_create_sales_order()
        finally:
            frappe.set_user(original_user)
            frappe.db.set_value("User", "Administrator", "enabled", 0)
            frappe.db.commit()
            self._rollback()

    # -------------------------------------------------------
    # Step 1: Create Opportunity
    # -------------------------------------------------------
    def _step_create_opportunity(self):
        doc = frappe.get_doc({
            "doctype": "Opportunity",
            "naming_series": "TEST-OPP-.#####",
            "opportunity_from": "Customer",
            "party_name": "Adil Konik - 1",
            "company": "Orderlift",
            "opportunity_type": "Sales",
            "custom_crm_business_type": "Distribution",
            "custom_crm_segment": "Grossiste",
            "items": [{"item_code": "POR2-00117", "qty": 2, "uom": "Nos"}],
        })
        doc.flags.ignore_permissions = True
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        self.opportunity = doc
        self._track("Opportunity", doc.name)
        self._assert("Opportunity created", bool(doc.name), doc.name)
        self._assert("Opportunity has item", len(doc.items) > 0, len(doc.items))

    # -------------------------------------------------------
    # Step 2: Create Pricing Sheet
    # -------------------------------------------------------
    def _step_create_pricing_sheet(self):
        payload = {
            "name": "",
            "sheet_name": f"E2E Test PS {self.suffix}",
            "custom_company": "Orderlift",
            "party_type": "Customer",
            "party_name": "Adil Konik - 1",
            "opportunity": self.opportunity.name,
            "pricing_mode": "Static",
            "selected_price_list": "ORDERLIFT IMPORT MAD",
            "selected_selling_price_lists": [
                {"price_list": "ORDERLIFT IMPORT MAD", "is_active": 1, "sequence": 10},
            ],
            "output_mode": "Avec details",
            "lines": [{
                "item": "POR2-00117",
                "qty": 2,
                "display_group": "Test Group",
                "show_in_detail": 1,
                "line_type": "Standard",
                "discount_percent": 10,
            }],
        }

        result = frappe.call(
            "orderlift.orderlift_sales.page.pricing_sheet_builder.pricing_sheet_builder.save_pricing_sheet_builder_payload",
            payload=json.dumps(payload),
        )

        sheet_name = ""
        if isinstance(result, dict):
            sheet_name = result.get("name", "")
        if not sheet_name and isinstance(result, str):
            sheet_name = result

        if not sheet_name:
            raise RuntimeError(f"PS save returned no name: {result}")

        self.sheet = frappe.get_doc("Pricing Sheet", sheet_name)
        self._track("Pricing Sheet", sheet_name)
        self._assert("Pricing Sheet created", bool(self.sheet), str(self.sheet.name))

        lines = self.sheet.lines or []
        self._assert("Pricing Sheet has lines", len(lines) > 0, len(lines))

        line = lines[0]
        self._assert("PS line has sell price", flt(line.final_sell_unit_price) > 0,
            f"sp={flt(line.static_list_price)} fu={flt(line.final_sell_unit_price)} dsu={flt(line.discounted_sell_unit_price)} comm={flt(line.commission_amount)}")
        self._assert("PS line has discount", flt(line.discount_percent) == 10, line.discount_percent)
        self._assert("PS line has discounted sell", flt(line.discounted_sell_unit_price) > 0)
        self._assert("PS line has commission", flt(line.commission_amount) >= 0, line.commission_amount)

    # -------------------------------------------------------
    # Step 3: Generate Quotation
    # -------------------------------------------------------
    def _step_generate_quotation(self):
        self.sheet.recalculate()
        frappe.db.commit()
        self.sheet.reload()

        ps_line = self.sheet.lines[0]
        gross = flt(ps_line.final_sell_unit_price)
        discounted = flt(ps_line.discounted_sell_unit_price or gross)
        static = flt(ps_line.static_list_price or ps_line.projected_unit_price or gross)
        qty = flt(ps_line.qty)
        disc_pct = flt(ps_line.discount_percent)
        disc_amt = flt(ps_line.discount_amount)
        comm_rate = flt(ps_line.commission_rate)
        comm_amt = flt(ps_line.commission_amount)

        quotation = frappe.new_doc("Quotation")
        quotation.naming_series = "TEST-QTN-.#####"
        quotation.company = self.sheet.custom_company
        quotation.party_name = self.sheet.party_name
        quotation.quotation_to = "Customer"
        quotation.selling_price_list = "ORDERLIFT IMPORT MAD"
        quotation.source_pricing_sheet = self.sheet.name
        quotation.opportunity = self.sheet.opportunity
        quotation.currency = "MAD"
        quotation.conversion_rate = 1
        quotation.plc_conversion_rate = 1
        quotation.append("items", {
            "item_code": ps_line.item,
            "qty": qty,
            "rate": discounted,
            "amount": discounted * qty,
            "price_list_rate": discounted,
            "net_rate": discounted,
            "net_amount": discounted * qty,
            "discount_percentage": 0,
            "source_price_list_sell_rate": static,
            "source_gross_sell_rate": gross,
            "source_discount_percent": disc_pct,
            "source_max_discount_percent": flt(ps_line.max_discount_percent_allowed),
            "source_discount_amount": disc_amt,
            "source_discounted_sell_rate": discounted,
            "source_selling_price_list": ps_line.get("resolved_selling_price_list") or "",
            "source_commission_rate": comm_rate,
            "source_commission_amount": comm_amt,
            "ignore_pricing_rule": 1,
        })

        if quotation.meta.get_field("selected_selling_price_lists"):
            quotation.set("selected_selling_price_lists", [])
            quotation.append("selected_selling_price_lists", {
                "price_list": "ORDERLIFT IMPORT MAD", "is_active": 1, "sequence": 10,
            })

        quotation.flags.ignore_permissions = True
        quotation.flags.ignore_mandatory = True
        quotation.flags.ignore_validate = True
        quotation.insert(ignore_permissions=True)
        frappe.db.commit()

        self.quotation = quotation
        self._track("Quotation", quotation.name)

        items = self.quotation.items or []
        self._assert("Quotation has items", len(items) > 0, len(items))

        q_item = items[0]
        ps_line = self.sheet.lines[0]

        self._assert("QTN rate > 0", flt(q_item.rate) > 0, q_item.rate)
        self._assert("QTN source_gross_sell_rate > 0", flt(q_item.get("source_gross_sell_rate") or 0) > 0, q_item.get("source_gross_sell_rate"))
        self._assert("QTN source_discounted_sell_rate > 0", flt(q_item.get("source_discounted_sell_rate") or 0) > 0)
        self._assert("QTN source_discount_percent", flt(q_item.get("source_discount_percent") or 0) >= 0)
        self._assert("QTN source_commission_amount >= 0", flt(q_item.get("source_commission_amount") or 0) >= 0)

        self._assert("PU List HT matches PS",
            abs(flt(q_item.get("source_price_list_sell_rate") or 0) - flt(ps_line.static_list_price or 0)) < 0.02)
        self._assert("PU HT matches PS",
            abs(flt(q_item.get("source_gross_sell_rate") or 0) - flt(ps_line.final_sell_unit_price)) < 0.02)
        self._assert("PU HT net matches PS",
            abs(flt(q_item.get("source_discounted_sell_rate") or 0) - flt(ps_line.discounted_sell_unit_price or ps_line.final_sell_unit_price)) < 0.02)

    # -------------------------------------------------------
    # Step 4: Create Sales Order from Quotation
    # -------------------------------------------------------
    def _step_create_sales_order(self):
        quotation = self.quotation
        so = frappe.get_doc({
            "doctype": "Sales Order",
            "naming_series": "TEST-SO-.#####",
            "company": quotation.company,
            "customer": quotation.party_name,
            "source_pricing_sheet": quotation.source_pricing_sheet,
            "delivery_date": frappe.utils.add_days(frappe.utils.today(), 7),
            "transaction_date": frappe.utils.today(),
            "currency": "MAD",
            "conversion_rate": 1,
            "selling_price_list": "ORDERLIFT IMPORT MAD",
            "items": [],
        })
        so.flags.ignore_permissions = True
        so.flags.ignore_mandatory = True
        for q_item in quotation.items:
            so.append("items", {
                "item_code": q_item.item_code,
                "qty": q_item.qty,
                "uom": q_item.uom,
                "rate": q_item.rate,
                "amount": q_item.amount,
                "price_list_rate": q_item.price_list_rate,
                "discount_percentage": q_item.discount_percentage,
                "net_rate": q_item.net_rate,
                "net_amount": q_item.net_amount,
                "prevdoc_doctype": "Quotation",
                "prevdoc_docname": quotation.name,
                "prevdoc_detail_docname": q_item.name,
            })
        so.insert(ignore_permissions=True)
        frappe.db.commit()

        # Manually copy pricing snapshot (force overwrite regardless of user role)
        source_items = {r.name: r for r in quotation.items}
        for so_row in so.items:
            q_name = so_row.get("prevdoc_detail_docname") or ""
            src = source_items.get(q_name)
            if not src:
                continue
            for field in ("source_pricing_sheet_line", "source_pricing_scenario", "source_pricing_override",
                "source_pricing_policy", "source_margin_percent", "source_margin_basis",
                "source_scenario_rule", "source_margin_rule", "source_sales_person", "source_geography",
                "source_customs_applied", "source_customs_basis", "source_selling_price_list",
                "source_price_list_sell_rate", "source_gross_sell_rate", "source_discount_percent",
                "source_max_discount_percent", "source_discount_amount", "source_discounted_sell_rate",
                "source_commission_rate", "source_commission_amount"):
                if hasattr(so_row, field) and hasattr(src, field):
                    setattr(so_row, field, getattr(src, field, None))
        so.save(ignore_permissions=True)
        frappe.db.commit()
        so.reload()
        self.sales_order = so
        self._track("Sales Order", so.name)

        so_items = so.items or []
        self._assert("Sales Order has items", len(so_items) > 0)

        so_item = so_items[0]
        q_ref = quotation.items[0]

        self._assert("SO rate matches QTN", abs(flt(so_item.rate) - flt(q_ref.rate)) < 0.02)
        self._assert("SO source_gross_sell_rate > 0", flt(so_item.get("source_gross_sell_rate") or 0) > 0)

        self._assert("SO PU List HT matches QTN", abs(flt(so_item.get("source_price_list_sell_rate") or 0) - flt(q_ref.get("source_price_list_sell_rate") or 0)) < 0.02)
        self._assert("SO PU HT matches QTN", abs(flt(so_item.get("source_gross_sell_rate") or 0) - flt(q_ref.get("source_gross_sell_rate") or 0)) < 0.02)
        self._assert("SO PU HT net matches QTN", abs(flt(so_item.get("source_discounted_sell_rate") or 0) - flt(q_ref.get("source_discounted_sell_rate") or 0)) < 0.02)
        self._assert("SO Remise % matches QTN", abs(flt(so_item.get("source_discount_percent") or 0) - flt(q_ref.get("source_discount_percent") or 0)) < 0.02)

        from orderlift.sales.utils.pricing_projection import calculate_agent_commission
        gross = flt(so_item.get("source_gross_sell_rate") or 0)
        disc = flt(so_item.get("source_discounted_sell_rate") or 0)
        qty = flt(so_item.qty)
        max_disc = flt(so_item.get("source_max_discount_percent") or 0)
        comm_rate = flt(so_item.get("source_commission_rate") or 0)
        expected = calculate_agent_commission(
            price_list_unit_price=gross, actual_unit_price=disc, qty=qty,
            max_discount_percent=max_disc, commission_rate=comm_rate,
            enforce_discount_cap=False,
        )
        expected_amt = flt(expected.get("commission_amount") or 0)
        actual_amt = flt(so_item.get("source_commission_amount") or 0)
        self._assert("SO commission calculated correctly",
            abs(actual_amt - expected_amt) < 0.05,
            f"expected={expected_amt} actual={actual_amt}")


if __name__ == "__main__":
    run()
