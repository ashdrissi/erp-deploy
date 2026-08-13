(function () {
    const DOCTYPES = ["Opportunity", "Pricing Sheet", "Quotation", "Sales Order"];
    const CHILD_DOCTYPE = "Orderlift Sales Team Member";

    function rows(frm) {
        return frm.doc.custom_sales_team || [];
    }

    function redistribute(frm) {
        const team = rows(frm);
        if (!team.length) return;
        const share = Math.round((100 / team.length) * 1e9) / 1e9;
        team.forEach((row, index) => {
            const value = index === team.length - 1 ? 100 - share * (team.length - 1) : share;
            frappe.model.set_value(row.doctype, row.name, "allocated_percentage", value);
            frappe.model.set_value(row.doctype, row.name, "is_primary", index === 0 ? 1 : 0);
        });
        frm.refresh_field("custom_sales_team");
    }

    function configure(frm) {
        if (!frm?.fields_dict?.custom_sales_team || !frm.set_query) return;
        frm.set_query("sales_person", "custom_sales_team", () => ({
            filters: { enabled: 1, is_group: 0 },
        }));
    }

    DOCTYPES.forEach((doctype) => {
        frappe.ui.form.on(doctype, {
            setup: configure,
            refresh: configure,
            custom_sales_team_add(frm) {
                redistribute(frm);
            },
            custom_sales_team_remove(frm) {
                redistribute(frm);
            },
        });
    });

    frappe.ui.form.on(CHILD_DOCTYPE, {
        sales_person(frm) {
            if (DOCTYPES.includes(frm.doctype) && rows(frm).length > 1) redistribute(frm);
        },
    });
})();
