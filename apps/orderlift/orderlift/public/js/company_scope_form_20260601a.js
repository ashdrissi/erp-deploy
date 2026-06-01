/**
 * Orderlift — company + business-type scope, form layer.
 *
 * For company-owned masters / operational records:
 *   - auto-fill the owning company from the active company on new docs and lock it
 *     (restricted users can never change it; mirrors orderlift.company_scope on the server),
 *   - default + lock the business type when the company has a single business type,
 *   - restrict the business type to the company's allowed set otherwise,
 *   - clear an invalid business type and alert with the allowed list.
 *
 * Party + transaction CRM docs (Customer/Prospect/Lead/Opportunity/Quotation/Sales
 * Order/Project) keep their business-type/segment query wiring in crm_classification.js;
 * here we only add company set+lock for the CRM masters.
 */

frappe.provide("orderlift.company_scope");

(function () {
    // doctype -> { company: <company fieldname>, bt: <business-type fieldname or null> }
    const SCOPE = {
        Customer: { company: "custom_company", bt: null },
        Supplier: { company: "custom_company", bt: null },
        "Price List": { company: "custom_company", bt: null },
        Prospect: { company: "company", bt: null },
        Lead: { company: "company", bt: null },
        "Pricing Sheet": { company: "custom_company", bt: "crm_business_type" },
        "Pricing Scenario": { company: "custom_company", bt: null },
        "Customer Segmentation Engine": { company: "custom_company", bt: "business_type_filter" },
        "Partner Campaign": { company: "custom_company", bt: "business_type_filter" },
        "Portal Customer Group Policy": { company: "custom_company", bt: "business_type" },
        "Portal Quote Request": { company: "custom_company", bt: "business_type" },
    };

    function context() {
        return (window.frappe && frappe.boot && frappe.boot.orderlift_company_access) || {};
    }

    function activeCompany() {
        const ctx = context();
        return ctx.current_company || ctx.user_default_company || (ctx.companies || [])[0] || "";
    }

    function isUnrestricted() {
        return !!context().unrestricted;
    }

    function hasField(frm, fieldname) {
        return fieldname && frm.fields_dict && !!frm.fields_dict[fieldname];
    }

    function applyCompany(frm, config) {
        const field = config.company;
        if (!hasField(frm, field)) return;
        if (frm.is_new() && !frm.doc[field]) {
            const company = activeCompany();
            if (company) frm.set_value(field, company);
        }
        // Lock the owning company for everyone except all-company admins.
        if (!isUnrestricted()) {
            frm.set_df_property(field, "read_only", 1);
        }
    }

    async function applyBusinessType(frm, config) {
        const btField = config.bt;
        if (!hasField(frm, btField)) return;
        const company = frm.doc[config.company] || "";
        if (!company) {
            frm.set_df_property(btField, "read_only", 0);
            return;
        }

        let data = {};
        try {
            const res = await frappe.call({
                method: "orderlift.orderlift_crm.company_business_type.get_company_business_type_payload",
                args: { company },
            });
            data = res.message || {};
        } catch (error) {
            console.error("company_scope: unable to load business types", error);
            return;
        }

        const names = (data.business_types || []).map((row) => row.name).filter(Boolean);
        const single = data.single_business_type || "";
        const current = frm.doc[btField] || "";

        // Constrain selectable values to the company's allowed business types.
        frm.set_query(btField, () => ({
            filters: names.length ? { name: ["in", names] } : { is_active: 1 },
        }));

        // Clear a value the company no longer allows.
        if (current && names.length && !names.includes(current)) {
            await frm.set_value(btField, "");
            frappe.show_alert({
                message: __("This company does not allow business type {0}. Allowed: {1}", [
                    current,
                    names.join(", ") || "—",
                ]),
                indicator: "orange",
            });
        }

        if (single) {
            if (!frm.doc[btField]) await frm.set_value(btField, single);
            frm.set_df_property(btField, "read_only", 1);
        } else {
            frm.set_df_property(btField, "read_only", 0);
        }
    }

    async function apply(frm) {
        const config = SCOPE[frm.doctype];
        if (!config) return;
        applyCompany(frm, config);
        await applyBusinessType(frm, config);
    }

    orderlift.company_scope.apply = apply;

    Object.keys(SCOPE).forEach((doctype) => {
        const config = SCOPE[doctype];
        const handlers = {
            refresh: apply,
            onload_post_render: apply,
        };
        // Reload allowed business types whenever the company changes (admins only).
        if (config.company) {
            handlers[config.company] = apply;
        }
        frappe.ui.form.on(doctype, handlers);
    });
})();
