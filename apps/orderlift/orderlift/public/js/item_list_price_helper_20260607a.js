(function () {
    if (window.__orderlift_item_list_price_helper_20260607a_installed) return;
    window.__orderlift_item_list_price_helper_20260607a_installed = true;

    const API = "orderlift.orderlift_sales.utils.item_price_tools";
    frappe.provide("frappe.listview_settings");
    const settings = frappe.listview_settings["Item"] = frappe.listview_settings["Item"] || {};
    const originalOnload = settings.onload;

    settings.onload = function (listview) {
        if (typeof originalOnload === "function") originalOnload(listview);
        if (listview.__orderlift_quick_item_prices_installed) return;
        listview.__orderlift_quick_item_prices_installed = true;
        listview.page.add_inner_button(__("Quick Item Prices"), () => showQuickPriceDialog(listview));
    };

    async function showQuickPriceDialog(listview) {
        const itemCodes = selectedItemCodes(listview);
        if (!itemCodes.length) {
            frappe.show_alert({ message: __("Select at least one Item."), indicator: "orange" });
            return;
        }

        const dialog = new frappe.ui.Dialog({
            title: __("Quick Item Prices"),
            size: "extra-large",
            fields: [
                {
                    fieldname: "price_type",
                    fieldtype: "Select",
                    label: __("Price Type"),
                    options: "Selling\nBuying",
                    default: "Selling",
                    reqd: 1,
                    onchange: () => {
                        dialog.set_value("price_list", "");
                        loadQuickRows(dialog, itemCodes);
                    },
                },
                {
                    fieldname: "price_list",
                    fieldtype: "Link",
                    label: __("Price List"),
                    options: "Price List",
                    reqd: 1,
                    get_query: () => ({ filters: priceListFilters(dialog.get_value("price_type")) }),
                    onchange: () => loadQuickRows(dialog, itemCodes),
                },
                { fieldtype: "HTML", fieldname: "items_html" },
            ],
            primary_action_label: __("Save Item Prices"),
            primary_action: async () => saveQuickPrices(dialog, listview),
        });
        dialog.__orderlift_item_codes = itemCodes;
        dialog.__orderlift_quick_rows = [];
        dialog.show();
        injectStyles();
        await loadQuickRows(dialog, itemCodes);
    }

    function selectedItemCodes(listview) {
        const rows = typeof listview.get_checked_items === "function" ? listview.get_checked_items() : [];
        return rows.map((row) => row.name).filter(Boolean);
    }

    async function loadQuickRows(dialog, itemCodes) {
        if (!dialog || !dialog.fields_dict || !dialog.fields_dict.items_html) return;
        const wrapper = dialog.fields_dict.items_html.$wrapper;
        wrapper.html(`<div class="olq-empty">${esc(__("Loading selected Items..."))}</div>`);
        try {
            const response = await frappe.call({
                method: `${API}.get_quick_price_rows`,
                args: {
                    item_codes: JSON.stringify(itemCodes),
                    price_type: normalizePriceType(dialog.get_value("price_type")),
                    price_list: dialog.get_value("price_list") || "",
                },
            });
            dialog.__orderlift_quick_rows = (response.message || {}).rows || [];
            renderQuickRows(dialog);
        } catch (error) {
            console.error("Orderlift quick Item Prices failed", error);
            wrapper.html(`<div class="olq-error">${esc(__("Unable to load selected Items."))}</div>`);
        }
    }

    async function saveQuickPrices(dialog, listview) {
        const priceList = dialog.get_value("price_list");
        if (!priceList) {
            frappe.msgprint({ title: __("Missing Price List"), message: __("Select a Price List before saving."), indicator: "orange" });
            return;
        }
        const rows = collectQuickRows(dialog);
        if (!rows.length) {
            frappe.msgprint({ title: __("No Rates"), message: __("Enter at least one rate before saving."), indicator: "orange" });
            return;
        }
        const response = await frappe.call({
            method: `${API}.save_quick_item_prices`,
            args: {
                price_type: normalizePriceType(dialog.get_value("price_type")),
                price_list: priceList,
                rows: JSON.stringify(rows),
            },
            freeze: true,
            freeze_message: __("Saving Item Prices..."),
        });
        const out = response.message || {};
        frappe.show_alert({
            message: __("Item Prices saved. Created: {0}, Updated: {1}, Skipped: {2}", [out.created || 0, out.updated || 0, out.skipped || 0]),
            indicator: "green",
        }, 8);
        dialog.hide();
        if (listview && typeof listview.refresh === "function") listview.refresh();
    }

    function renderQuickRows(dialog) {
        const rows = dialog.__orderlift_quick_rows || [];
        const priceList = dialog.get_value("price_list") || "";
        const html = `
            <div class="olq-help">${esc(priceList ? __("Existing latest rates are prefilled. Blank rate rows are skipped on save.") : __("Select a Price List to prefill existing rates. Blank rate rows are skipped on save."))}</div>
            <div class="olq-table-wrap"><table class="olq-table">
                <thead><tr><th>${esc(__("Item"))}</th><th>${esc(__("Name"))}</th><th>${esc(__("UOM"))}</th><th>${esc(__("Rate"))}</th><th>${esc(__("Currency"))}</th></tr></thead>
                <tbody>${rows.length ? rows.map(quickRowHtml).join("") : `<tr><td colspan="5" class="olq-empty">${esc(__("No selected Items found."))}</td></tr>`}</tbody>
            </table></div>`;
        dialog.fields_dict.items_html.$wrapper.html(html);
    }

    function quickRowHtml(row, index) {
        const rate = Number(row.price_list_rate || 0) > 0 ? row.price_list_rate : "";
        return `<tr data-quick-row="${index}">
            <td><strong>${esc(row.item_code || "")}</strong></td>
            <td>${esc(row.item_name || "")}</td>
            <td><input data-quick-field="uom" value="${attr(row.uom || row.stock_uom || "")}"></td>
            <td><input data-quick-field="price_list_rate" type="number" step="0.01" min="0" value="${attr(rate)}" placeholder="0.00"></td>
            <td><input data-quick-field="currency" value="${attr(row.currency || "")}"></td>
        </tr>`;
    }

    function collectQuickRows(dialog) {
        const sourceRows = dialog.__orderlift_quick_rows || [];
        const out = [];
        dialog.fields_dict.items_html.$wrapper.find("[data-quick-row]").each(function () {
            const index = Number($(this).attr("data-quick-row"));
            const source = sourceRows[index] || {};
            const rateInput = $(this).find('[data-quick-field="price_list_rate"]').val();
            if (String(rateInput || "").trim() === "") return;
            out.push({
                name: source.name || "",
                item_code: source.item_code || "",
                uom: String($(this).find('[data-quick-field="uom"]').val() || source.stock_uom || "").trim(),
                price_list_rate: Number(rateInput || 0),
                currency: String($(this).find('[data-quick-field="currency"]').val() || "").trim(),
            });
        });
        return out;
    }

    function priceListFilters(priceType) {
        const type = normalizePriceType(priceType);
        return type === "buying" ? { buying: 1, enabled: 1 } : { selling: 1, enabled: 1 };
    }

    function normalizePriceType(value) {
        return String(value || "selling").toLowerCase() === "buying" ? "buying" : "selling";
    }

    function esc(value) {
        return frappe.utils.escape_html(String(value == null ? "" : value));
    }

    function attr(value) {
        return esc(value).replace(/`/g, "&#96;");
    }

    function injectStyles() {
        if (document.getElementById("orderlift-item-list-price-helper-style")) return;
        const style = document.createElement("style");
        style.id = "orderlift-item-list-price-helper-style";
        style.textContent = `
            .olq-help{border:1px solid #dbeafe;border-radius:8px;background:#eff6ff;color:#1e3a8a;padding:9px 10px;margin-bottom:10px;font-weight:600}.olq-table-wrap{max-height:520px;overflow:auto;border:1px solid #e5e7eb;border-radius:10px}.olq-table{width:100%;border-collapse:collapse}.olq-table th,.olq-table td{padding:8px;border-bottom:1px solid #edf2f7;vertical-align:middle}.olq-table th{position:sticky;top:0;background:#f8fafc;color:#475569;font-size:11px;text-transform:uppercase;z-index:1}.olq-table input{height:32px;border:1px solid #cbd5e1;border-radius:7px;padding:0 8px;background:#fff}.olq-table input[data-quick-field='price_list_rate']{text-align:right;min-width:120px}.olq-empty{color:#64748b;text-align:center;padding:18px}.olq-error{border:1px solid #fecaca;border-radius:8px;background:#fef2f2;color:#991b1b;padding:10px}
        `;
        document.head.appendChild(style);
    }
})();
