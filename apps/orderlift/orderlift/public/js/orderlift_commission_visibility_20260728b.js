(function () {
    const CONFIG = {
        Opportunity: { child: null, fields: [] },
        "Pricing Sheet": { child: "lines", fields: ["commission_rate", "commission_amount"] },
        Quotation: { child: "items", fields: ["source_commission_rate", "source_commission_amount"] },
        "Sales Order": { child: "items", fields: ["source_commission_rate", "source_commission_amount"] },
    };

    function teamMembers(frm) {
        return (frm.doc.custom_sales_team || []).map((row) => row.sales_person).filter(Boolean);
    }

    function applyGridVisibility(frm, config, visible) {
        if (!config.child) return;
        const grid = frm.fields_dict?.[config.child]?.grid;
        if (!grid?.update_docfield_property) return;
        config.fields.forEach((fieldname) => {
            grid.update_docfield_property(fieldname, "hidden", visible ? 0 : 1);
            grid.update_docfield_property(fieldname, "in_list_view", visible ? 1 : 0);
        });
        frm.refresh_field(config.child);
    }

    function applyParentVisibility(frm, visible) {
        if (frm.fields_dict?.commission_sales_person) {
            frm.toggle_display("commission_sales_person", visible);
        }
        if (frm.fields_dict?.custom_sales_team) {
            frm.toggle_display("custom_sales_team", visible);
        }
        if (frm.fields_dict?.custom_sales_team_section) {
            frm.toggle_display("custom_sales_team_section", visible);
        }
        const teamGrid = frm.fields_dict?.custom_sales_team?.grid;
        if (teamGrid?.update_docfield_property) {
            ["commission_rate", "commission_amount"].forEach((fieldname) => {
                teamGrid.update_docfield_property(fieldname, "hidden", visible ? 0 : 1);
                teamGrid.update_docfield_property(fieldname, "in_list_view", visible ? 1 : 0);
            });
            frm.refresh_field("custom_sales_team");
        }
    }

    function apply(frm) {
        const config = CONFIG[frm.doctype];
        if (!config) return;
        const teamMembersJson = JSON.stringify(teamMembers(frm));
        frappe.call({
            method: "orderlift.orderlift_sales.utils.sales_team.get_commission_visibility",
            args: {
                doctype: frm.doctype,
                name: frm.doc.name || "",
                team_members: teamMembersJson,
            },
            callback(response) {
                const visible = Boolean(response.message?.can_view);
                frm.__orderliftCanViewCommission = visible;
                applyGridVisibility(frm, config, visible);
                applyParentVisibility(frm, visible);
            },
        });
    }

    Object.keys(CONFIG).forEach((doctype) => {
        frappe.ui.form.on(doctype, {
            refresh: apply,
            onload_post_render: apply,
            custom_sales_team_add: apply,
            custom_sales_team_remove: apply,
        });
    });
})();
