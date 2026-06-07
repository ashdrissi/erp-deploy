(function () {
    if (window.__orderliftFinanceAccountGuardRegistered) return;
    window.__orderliftFinanceAccountGuardRegistered = true;

    const SUPERADMIN_ROLES = new Set(["Administrator", "System Manager", "Developer"]);
    const ACCOUNT_FIELD_CONFIG = {
        "Sales Order": {
            tables: {
                items: ["cost_center"],
            },
        },
        "Sales Invoice": {
            parent: ["debit_to", "party_account_currency", "is_opening", "against_income_account"],
            tables: {
                items: ["income_account", "expense_account", "cost_center"],
                taxes: ["account_head", "cost_center"],
            },
        },
        "Purchase Invoice": {
            parent: ["credit_to", "party_account_currency", "is_opening", "against_expense_account"],
            tables: {
                items: ["expense_account", "cost_center"],
                taxes: ["account_head", "cost_center"],
            },
        },
        "Payment Entry": {
            parent: [
                "paid_from",
                "paid_to",
                "paid_from_account_currency",
                "paid_to_account_currency",
                "source_exchange_rate",
                "target_exchange_rate",
                "difference_amount",
            ],
            tables: {
                deductions: ["account", "cost_center"],
            },
        },
    };

    function canEditAccounts() {
        if (frappe.session && frappe.session.user === "Administrator") return true;
        const roles = frappe.user_roles || [];
        return roles.some((role) => SUPERADMIN_ROLES.has(role));
    }

    function applyAccountFieldGuard(frm) {
        if (canEditAccounts()) return;
        const config = ACCOUNT_FIELD_CONFIG[frm.doctype];
        if (!config) return;

        (config.parent || []).forEach((fieldname) => hideParentField(frm, fieldname));
        Object.entries(config.tables || {}).forEach(([tableField, fieldnames]) => {
            hideGridFields(frm, tableField, fieldnames);
        });
    }

    function hideParentField(frm, fieldname) {
        if (!frm.get_field(fieldname)) return;
        frm.set_df_property(fieldname, "read_only", 1);
        frm.set_df_property(fieldname, "hidden", 1);
    }

    function hideGridFields(frm, tableField, fieldnames) {
        const grid = frm.fields_dict[tableField] && frm.fields_dict[tableField].grid;
        if (!grid) return;
        fieldnames.forEach((fieldname) => {
            try {
                grid.update_docfield_property(fieldname, "read_only", 1);
                grid.update_docfield_property(fieldname, "hidden", 1);
                if (grid.toggle_display) grid.toggle_display(fieldname, false);
            } catch (error) {
                console.warn("Unable to hide account grid field", tableField, fieldname, error);
            }
        });
        frm.refresh_field(tableField);
    }

    function registerHandlers() {
        if (!window.frappe || !frappe.ui || !frappe.ui.form || !frappe.ui.form.on) {
            window.setTimeout(registerHandlers, 100);
            return;
        }

        ["Sales Order", "Sales Invoice", "Purchase Invoice", "Payment Entry"].forEach((doctype) => {
            frappe.ui.form.on(doctype, {
                setup: applyAccountFieldGuard,
                refresh: applyAccountFieldGuard,
                company: applyAccountFieldGuard,
            });
        });
    }

    registerHandlers();
})();
