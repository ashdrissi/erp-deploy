/**
 * Orderlift — company + business-type scope, form layer.
 *
 * For company-owned masters / operational records:
 *   - auto-fill the owning company from the active company on new docs and lock it
 *     (restricted users can never change it; mirrors orderlift.company_scope on the server),
 *   - default + lock the business type when the company has a single business type,
 *   - restrict the business type to the company's allowed set otherwise,
 *   - further narrow the business type to the user's per-user allow-list
 *     (frappe.boot.orderlift_business_type_access) when configured,
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

    // Per-user business-type allow-list. Returns a Set when the user is restricted
    // to specific business types, or null when unrestricted (no extra narrowing).
    function userBusinessTypes() {
        const ctx = (window.frappe && frappe.boot && frappe.boot.orderlift_business_type_access) || {};
        if (ctx.unrestricted) return null;
        const list = ctx.business_types || [];
        return list.length ? new Set(list) : null;
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
        // Lock the owning company for EVERYONE so records stay strictly on the
        // active company. Admins get an explicit unlock button for intentional
        // reassignment (e.g. fixing backfilled records); non-admins stay locked.
        if (frm._orderlift_company_unlocked) {
            frm.set_df_property(field, "read_only", 0);
        } else {
            frm.set_df_property(field, "read_only", 1);
            if (isUnrestricted()) addUnlockButton(frm, config);
        }
    }

    function addUnlockButton(frm, config) {
        // add_custom_button dedupes by label and Frappe clears custom buttons on
        // each refresh, so it is safe to call this on every apply().
        frm.add_custom_button(__("Change company"), () => {
            frm._orderlift_company_unlocked = true;
            frm.set_df_property(config.company, "read_only", 0);
            frappe.show_alert({ message: __("Company is now editable for this record."), indicator: "blue" });
        });
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

        let names = (data.business_types || []).map((row) => row.name).filter(Boolean);
        let single = data.single_business_type || "";

        // Narrow to the user's per-user business-type allow-list (mirrors the
        // server-side read filter). When the company exposes no explicit set,
        // fall back to the user's allowed types directly.
        const userBt = userBusinessTypes();
        if (userBt) {
            names = names.length ? names.filter((name) => userBt.has(name)) : Array.from(userBt);
            if (single && !userBt.has(single)) single = "";
            if (!single && names.length === 1) single = names[0];
        }

        const current = frm.doc[btField] || "";

        // Constrain selectable values to the effective allowed business types.
        frm.set_query(btField, () => ({
            filters: names.length ? { name: ["in", names] } : { is_active: 1 },
        }));

        // Clear a value the company/user no longer allows.
        if (current && names.length && !names.includes(current)) {
            await frm.set_value(btField, "");
            frappe.show_alert({
                message: __("This business type {0} is not available here. Allowed: {1}", [
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
