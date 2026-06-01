/**
 * Orderlift — company focus for list views.
 *
 * Each scoped doctype list defaults to a filter on the active company so users
 * focus on one company at a time. The filter is REMOVABLE: the hard isolation
 * stays in the server permission query (allowed companies), so clearing the
 * filter only widens to companies the user may already access. Switching the
 * active company via the sidebar switcher reloads and re-applies the focus.
 */

(function () {
    // doctype -> company fieldname
    const FIELD = {
        Customer: "custom_company",
        Supplier: "custom_company",
        "Price List": "custom_company",
        Prospect: "company",
        Lead: "company",
        Opportunity: "company",
        Quotation: "company",
        "Sales Order": "company",
        Project: "company",
        "Pricing Sheet": "custom_company",
        "Pricing Scenario": "custom_company",
        "Pricing Benchmark Policy": "company",
        "Pricing Customs Policy": "company",
        "Customer Segmentation Engine": "custom_company",
        "Partner Campaign": "custom_company",
        "Portal Customer Group Policy": "custom_company",
        "Portal Quote Request": "custom_company",
    };

    function context() {
        return (window.frappe && frappe.boot && frappe.boot.orderlift_company_access) || {};
    }

    function activeCompany() {
        const ctx = context();
        return ctx.current_company || ctx.user_default_company || (ctx.companies || [])[0] || "";
    }

    function alreadyFiltered(listview, field) {
        try {
            const filters = listview.filter_area.get() || [];
            return filters.some((row) => row[1] === field);
        } catch (error) {
            return false;
        }
    }

    function applyFocus(listview, field) {
        const company = activeCompany();
        if (!company || !listview || !listview.filter_area) return;
        // Respect a route/user-supplied filter (e.g. drill-down from a report).
        if (alreadyFiltered(listview, field)) return;
        try {
            listview.filter_area.add([[listview.doctype, field, "=", company]]);
        } catch (error) {
            console.error("company_scope: unable to apply list focus", error);
        }
    }

    frappe.provide("frappe.listview_settings");

    Object.keys(FIELD).forEach((doctype) => {
        const field = FIELD[doctype];
        const existing = frappe.listview_settings[doctype] || {};
        const previousOnload = existing.onload;
        existing.onload = function (listview) {
            if (typeof previousOnload === "function") previousOnload(listview);
            applyFocus(listview, field);
        };
        frappe.listview_settings[doctype] = existing;
    });
})();
