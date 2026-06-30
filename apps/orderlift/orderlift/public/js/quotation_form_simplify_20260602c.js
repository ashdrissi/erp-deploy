(function () {
    const HIDDEN_FIELDS = [
        "additional_discount_section",
        "apply_discount_on",
        "coupon_code",
        "additional_discount_percentage",
        "discount_amount",
        "base_discount_amount",
        "referral_sales_partner",
    ];

    const TAX_FIELDS = [
        "taxes_section",
        "tax_category",
        "taxes_and_charges",
        "shipping_rule",
        "incoterm",
        "named_place",
        "taxes",
        "total_taxes_and_charges",
        "base_total_taxes_and_charges",
        "taxes_and_charges_calculation",
        "other_charges_calculation",
        "tax_breakup",
    ];

    frappe.ui.form.on("Quotation", {
        setup(frm) {
            showOpportunityField(frm);
            showTaxFields(frm);
            hideNativeDiscountAndTaxFields(frm);
            setupOpportunityQuery(frm);
        },
        onload(frm) {
            applyOpportunityRouteOption(frm);
        },
        onload_post_render(frm) {
            showOpportunityField(frm);
            showTaxFields(frm);
        },
        refresh(frm) {
            showOpportunityField(frm);
            showTaxFields(frm);
            applyOpportunityRouteOption(frm);
            hideNativeDiscountAndTaxFields(frm);
            setupOpportunityQuery(frm);
            addBulkQuantityButton(frm);
            addBulkQuantityGridButton(frm);
        },
    });

    function showOpportunityField(frm) {
        if (!frm || !frm.fields_dict || !frm.fields_dict.opportunity) return;
        const field = frm.get_field && frm.get_field("opportunity");
        frm.set_df_property("opportunity", "hidden", 0);
        frm.set_df_property("opportunity", "read_only", 0);
        frm.toggle_display("opportunity", true);
        if (frm.toggle_enable) frm.toggle_enable("opportunity", true);
        frm.refresh_field("opportunity");
        if (field && field.wrapper) $(field.wrapper).show();
        setTimeout(() => {
            const refreshedField = frm.get_field && frm.get_field("opportunity");
            if (refreshedField && refreshedField.wrapper) $(refreshedField.wrapper).show();
        }, 0);
    }

    function showTaxFields(frm) {
        if (!frm || !frm.fields_dict) return;
        TAX_FIELDS.forEach((fieldname) => {
            if (!frm.fields_dict[fieldname]) return;
            frm.set_df_property(fieldname, "hidden", 0);
            frm.toggle_display(fieldname, true);
            frm.refresh_field(fieldname);
            const field = frm.get_field && frm.get_field(fieldname);
            if (field && field.wrapper) $(field.wrapper).show();
        });
    }

    function applyOpportunityRouteOption(frm) {
        if (
            !frm || !frm.is_new || !frm.is_new() || !frm.fields_dict.opportunity
            || frm.doc.opportunity || frm.__orderlift_opportunity_route_applied
        ) return;
        const options = frappe.route_options || {};
        const opportunity = options.opportunity || "";
        if (!opportunity) return;
        frm.__orderlift_opportunity_route_applied = true;
        frm.set_value("opportunity", opportunity);
    }

    function setupOpportunityQuery(frm) {
        if (!frm || !frm.set_query || !frm.fields_dict.opportunity) return;
        frm.set_query("opportunity", () => {
            const filters = { docstatus: ["<", 2] };
            const company = frm.doc.company || "";
            if (company) filters.company = company;
            return { filters };
        });
    }

    function hideNativeDiscountAndTaxFields(frm) {
        HIDDEN_FIELDS.forEach((fieldname) => {
            if (!frm.fields_dict[fieldname]) return;
            frm.set_df_property(fieldname, "hidden", 1);
            frm.toggle_display(fieldname, false);
        });
    }

    function addBulkQuantityButton(frm) {
        frm.add_custom_button(__("Bulk Quantity"), () => openBulkQuantityDialog(frm), __("Items"));
    }

    function addBulkQuantityGridButton(frm) {
        const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
        if (!grid || !grid.wrapper) return;

        // Try adding to the 'top' position which goes to grid_custom_buttons (appears with multi-select actions)
        if (typeof grid.add_custom_button === "function") {
            const $btn = grid.add_custom_button(__("Bulk Quantity"), () => {
                openBulkQuantityDialog(frm);
            }, "top");
            
            // Also add to bottom so it's visible if top isn't configured correctly in some versions
            const $btn_bottom = grid.add_custom_button(__("Bulk Quantity"), () => {
                openBulkQuantityDialog(frm);
            });
            
            if ($btn) $btn.attr("data-orderlift-bulk-quantity", "1").addClass("btn-secondary");
            if ($btn_bottom) $btn_bottom.attr("data-orderlift-bulk-quantity", "1").addClass("btn-secondary");
            return;
        }

        const $wrapper = $(grid.wrapper);
        if ($wrapper.find("[data-orderlift-bulk-quantity]").length) return;

        let $target = $wrapper.find(".grid-custom-buttons").first();
        let insertBeforeTarget = false;
        if (!$target.length) {
            $target = $wrapper.find(".grid-add-multiple-rows").first();
            insertBeforeTarget = true;
        }
        if (!$target.length) return;

        const $button = $(
            `<button type="button" class="btn btn-xs btn-secondary" data-orderlift-bulk-quantity="1">${__("Bulk Quantity")}</button>`
        );
        $button.on("click", (event) => {
            event.preventDefault();
            openBulkQuantityDialog(frm);
        });
        if (insertBeforeTarget) {
            $button.insertBefore($target);
        } else {
            $target.prepend($button);
        }
    }

    function openBulkQuantityDialog(frm) {
        const selectedRows = getSelectedItemRows(frm);
        if (!selectedRows.length) {
            frappe.msgprint({
                title: __("No Items Selected"),
                message: __("Select one or more rows in the Items table before applying a bulk quantity."),
                indicator: "orange",
            });
            return;
        }

        const dialog = new frappe.ui.Dialog({
            title: __("Apply Quantity to Selected Items"),
            fields: [
                {
                    fieldname: "qty",
                    fieldtype: "Float",
                    label: __("Quantity"),
                    reqd: 1,
                    default: 1,
                    description: __("This will update {0} selected item row(s).", [selectedRows.length]),
                },
            ],
            primary_action_label: __("Apply Quantity"),
            primary_action(values) {
                const qty = Number(values.qty || 0);
                if (!Number.isFinite(qty) || qty <= 0) {
                    frappe.msgprint({
                        title: __("Invalid Quantity"),
                        message: __("Enter a quantity greater than zero."),
                        indicator: "red",
                    });
                    return;
                }

                applyBulkQuantity(frm, selectedRows, qty);
                dialog.hide();
            },
        });
        dialog.show();
    }

    function getSelectedItemRows(frm) {
        const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
        if (grid && typeof grid.get_selected_children === "function") {
            const rows = grid.get_selected_children() || [];
            if (rows.length) return rows;
        }

        let selectedNames = [];
        if (frm.get_selected) {
            const selected = frm.get_selected() || {};
            selectedNames = selected.items || [];
        }
        if (!selectedNames.length && grid && typeof grid.get_selected === "function") {
            selectedNames = grid.get_selected() || [];
        }

        if (!selectedNames.length) return [];
        return (frm.doc.items || []).filter((row) => selectedNames.includes(row.name));
    }

    function applyBulkQuantity(frm, rows, qty) {
        rows.forEach((row) => {
            frappe.model.set_value(row.doctype, row.name, "qty", qty);
        });
        frm.refresh_field("items");
        frm.dirty();
        frappe.show_alert({
            message: __("Updated quantity for {0} selected item row(s).", [rows.length]),
            indicator: "green",
        });
    }
})();
