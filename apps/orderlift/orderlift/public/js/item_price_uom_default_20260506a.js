(function () {
    if (window.__orderlift_item_price_uom_default_20260506a_installed) return;
    window.__orderlift_item_price_uom_default_20260506a_installed = true;

    frappe.ui.form.on("Item Price", {
        refresh(frm) {
            applyItemDefaultUom(frm, { onlyIfEmpty: true });
        },
        item_code(frm) {
            applyItemDefaultUom(frm, { onlyIfEmpty: false });
        },
    });

    async function applyItemDefaultUom(frm, options) {
        const itemCode = (frm.doc.item_code || "").trim();
        if (!itemCode) return;
        if (options.onlyIfEmpty && frm.doc.uom) return;

        const response = await frappe.db.get_value("Item", itemCode, "stock_uom");
        const stockUom = response && response.message && response.message.stock_uom;
        if (!stockUom) return;
        if (frm.doc.uom === stockUom) return;

        await frm.set_value("uom", stockUom);
    }

    async function getItemStockUom(itemCode) {
        itemCode = (itemCode || "").trim();
        if (!itemCode) return "";
        const response = await frappe.db.get_value("Item", itemCode, "stock_uom");
        return response && response.message && response.message.stock_uom;
    }

    async function applyQuickEntryDefaultUom(dialog, options) {
        if (!dialog || !dialog.get_value || !dialog.set_value) return;
        const itemCode = dialog.get_value("item_code");
        if (!itemCode) return;
        const currentUom = dialog.get_value("uom");
        if (options.onlyIfEmpty && currentUom) return;
        const stockUom = await getItemStockUom(itemCode);
        if (!stockUom || currentUom === stockUom) return;
        await dialog.set_value("uom", stockUom);
    }

    function wireQuickEntryUom(dialog) {
        if (!dialog || dialog.__orderlift_item_price_uom_wired) return;
        if (dialog.doctype !== "Item Price") return;
        const itemField = dialog.fields_dict && dialog.fields_dict.item_code;
        if (!itemField) return;
        dialog.__orderlift_item_price_uom_wired = true;

        const originalOnchange = itemField.df.onchange;
        itemField.df.onchange = function () {
            if (typeof originalOnchange === "function") {
                originalOnchange.apply(this, arguments);
            }
            applyQuickEntryDefaultUom(dialog, { onlyIfEmpty: false });
        };
        if (itemField.$input) {
            itemField.$input.on("change.orderliftItemPriceUom awesomplete-selectcomplete.orderliftItemPriceUom", function () {
                setTimeout(() => applyQuickEntryDefaultUom(dialog, { onlyIfEmpty: false }), 0);
            });
        }
        applyQuickEntryDefaultUom(dialog, { onlyIfEmpty: true });
    }

    function installQuickEntrySupport(attempts) {
        if (frappe.ui.form && frappe.ui.form.QuickEntryForm) {
            const Base = frappe.ui.form.ItemPriceQuickEntryForm || frappe.ui.form.QuickEntryForm;
            frappe.ui.form.ItemPriceQuickEntryForm = class ItemPriceQuickEntryForm extends Base {
                render_dialog() {
                    super.render_dialog();
                    wireQuickEntryUom(this.dialog || this);
                }
            };
            return;
        }
        if (attempts <= 0) return;
        setTimeout(() => installQuickEntrySupport(attempts - 1), 100);
    }

    installQuickEntrySupport(50);
})();
