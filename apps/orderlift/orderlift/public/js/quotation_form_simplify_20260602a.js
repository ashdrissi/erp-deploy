(function () {
    const HIDDEN_FIELDS = [
        "additional_discount_section",
        "apply_discount_on",
        "coupon_code",
        "additional_discount_percentage",
        "discount_amount",
        "base_discount_amount",
        "referral_sales_partner",
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
            hideNativeDiscountAndTaxFields(frm);
        },
        refresh(frm) {
            hideNativeDiscountAndTaxFields(frm);
            addBulkQuantityButton(frm);
            setTimeout(() => addBulkQuantityGridButton(frm), 250);
        },
    });

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

        const $wrapper = $(grid.wrapper);
        if ($wrapper.find("[data-orderlift-bulk-quantity]").length) return;

        let $target = $wrapper.find(".grid-buttons").first();
        if (!$target.length) $target = $wrapper.find(".grid-footer").first();
        if (!$target.length) return;

        const $button = $(
            `<button type="button" class="btn btn-xs btn-default" data-orderlift-bulk-quantity>${__("Bulk Quantity")}</button>`
        );
        $button.on("click", (event) => {
            event.preventDefault();
            openBulkQuantityDialog(frm);
        });
        $target.prepend($button);
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
