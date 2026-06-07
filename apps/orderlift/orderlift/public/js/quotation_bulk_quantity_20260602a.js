(function () {
    const BUTTON_SELECTOR = "[data-orderlift-quotation-bulk-quantity]";
    let timer = null;

    function scheduleAttach() {
        window.clearTimeout(timer);
        timer = window.setTimeout(attachBulkQuantityButton, 250);
    }

    function currentQuotationForm() {
        const frm = window.cur_frm;
        if (!frm || frm.doctype !== "Quotation" || !frm.fields_dict || !frm.fields_dict.items) return null;
        return frm;
    }

    function attachBulkQuantityButton() {
        const frm = currentQuotationForm();
        if (!frm) return;

        const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
        if (!grid || !grid.wrapper) return;

        const $wrapper = $(grid.wrapper);
        if ($wrapper.find(BUTTON_SELECTOR).length) return;

        const $buttons = $wrapper.find(".grid-buttons").first();
        if (!$buttons.length) return;

        const $button = $(
            `<button type="button" class="btn btn-xs btn-primary" data-orderlift-quotation-bulk-quantity="1">${__("Bulk Quantity")}</button>`
        );
        $button.css({ "margin-right": "4px" });
        $button.on("click", (event) => {
            event.preventDefault();
            openBulkQuantityDialog(frm);
        });

        const $addMultiple = $buttons.find(".grid-add-multiple-rows").first();
        if ($addMultiple.length) {
            $button.insertBefore($addMultiple);
        } else {
            $buttons.prepend($button);
        }
    }

    function openBulkQuantityDialog(frm) {
        const rows = getSelectedItemRows(frm);
        if (!rows.length) {
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
                    description: __("This will update {0} selected item row(s).", [rows.length]),
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

                rows.forEach((row) => frappe.model.set_value(row.doctype, row.name, "qty", qty));
                frm.refresh_field("items");
                frm.dirty();
                dialog.hide();
                frappe.show_alert({
                    message: __("Updated quantity for {0} selected item row(s).", [rows.length]),
                    indicator: "green",
                });
            },
        });
        dialog.show();
    }

    function getSelectedItemRows(frm) {
        const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
        if (grid && typeof grid.get_selected_children === "function") {
            const children = grid.get_selected_children() || [];
            if (children.length) return children;
        }

        const selected = frm.get_selected ? frm.get_selected() || {} : {};
        const names = selected.items || [];
        if (!names.length) return [];
        return (frm.doc.items || []).filter((row) => names.includes(row.name));
    }

    function startWatcher() {
        scheduleAttach();
        window.setInterval(attachBulkQuantityButton, 1000);
        $(document).on("form-refresh after_ajax", scheduleAttach);
        if (frappe.router && frappe.router.on) {
            frappe.router.on("change", scheduleAttach);
        }
    }

    if (window.frappe && frappe.boot) {
        startWatcher();
    } else {
        $(document).on("app_ready", startWatcher);
    }
})();
