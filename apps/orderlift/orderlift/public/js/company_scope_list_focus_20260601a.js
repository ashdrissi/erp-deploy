/**
 * Orderlift — company focus for list views.
 *
 * Each scoped doctype list is STRICTLY focused on the active company: every load
 * forces the company filter to the active company, overriding any stale/different
 * value (e.g. a saved filter holding the previously-active company after a switch).
 * To view another company, switch via the sidebar switcher — the single source of
 * truth. The server permission query (allowed companies) remains the hard backstop.
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

    function isCorrect(row, field, company) {
        return Array.isArray(row) && row[1] === field && row[2] === "=" && row[3] === company;
    }

    function enforceFocus(listview, field) {
        const company = activeCompany();
        if (!company || !listview) return;

        // 1) Correct the seed array applied on first render. onload runs before
        //    filter_area is populated from listview.filters (base_list.js), so
        //    rewriting the seed here makes the active company win over any saved
        //    (possibly stale) company filter.
        if (Array.isArray(listview.filters)) {
            listview.filters = listview.filters.filter((row) => !(Array.isArray(row) && row[1] === field));
            listview.filters.push([listview.doctype, field, "=", company]);
        }

        // 2) If filter_area is already populated (re-entry / soft route), override
        //    a stale value: add() alone won't replace an existing one (exists()),
        //    so remove then add.
        if (!listview.filter_area) return;
        try {
            const live = (listview.filter_area.get() || []).find((row) => row[1] === field);
            if (live && !isCorrect(live, field, company)) {
                Promise.resolve(listview.filter_area.remove(field)).then(() => {
                    listview.filter_area.add([[listview.doctype, field, "=", company]]);
                });
            } else if (!live) {
                listview.filter_area.add([[listview.doctype, field, "=", company]]);
            }
        } catch (error) {
            console.error("company_scope: unable to enforce list focus", error);
        }
    }

    frappe.provide("frappe.listview_settings");

    Object.keys(FIELD).forEach((doctype) => {
        const field = FIELD[doctype];
        const existing = frappe.listview_settings[doctype] || {};
        const previousOnload = existing.onload;
        existing.onload = function (listview) {
            if (typeof previousOnload === "function") previousOnload(listview);
            enforceFocus(listview, field);
        };
        frappe.listview_settings[doctype] = existing;
    });
})();
