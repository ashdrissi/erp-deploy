(function () {
    if (window.__orderlift_item_list_price_helper_20260608g_installed) return;
    window.__orderlift_item_list_price_helper_20260608g_installed = true;

    const API = "orderlift.orderlift_sales.utils.item_price_tools";
    const EMPTY_FILTER_SENTINEL = "__orderlift_no_items_for_price_list__";
    const STOCK_FIELD = "custom_current_company_stock_qty";
    frappe.provide("frappe.listview_settings");
    const settings = frappe.listview_settings["Item"] = frappe.listview_settings["Item"] || {};
    const originalOnload = settings.onload;
    const originalRefresh = settings.refresh;

    settings.onload = function (listview) {
        if (typeof originalOnload === "function") originalOnload(listview);
        installPersistentSelection(listview);
        installQuickPrices(listview);
        installPriceListFilter(listview);
        scheduleStockRefresh(listview);
        scheduleSelectionRestore(listview);
    };

    settings.refresh = function (listview) {
        if (typeof originalRefresh === "function") originalRefresh(listview);
        scheduleStockRefresh(listview);
        scheduleSelectionRestore(listview);
    };

    function installPersistentSelection(listview) {
        if (!listview || listview.__orderlift_persistent_selection_installed) return;
        listview.__orderlift_persistent_selection_installed = true;
        listview.__orderlift_selected_item_codes = listview.__orderlift_selected_item_codes || new Set();
        ensureStockStyles();
        const clearButton = listview.page.add_inner_button(__("Clear Selection"), () => {
            listview.__orderlift_selected_item_codes.clear();
            restoreVisibleSelection(listview);
            updateSelectionButton(listview);
        });
        listview.__orderlift_clear_selection_button = clearButton;
        const badge = $(`<span class="ol-item-selection-badge">${esc(__("0 selected"))}</span>`);
        if (clearButton && clearButton.length) {
            clearButton.after(badge);
        } else if (listview.page && listview.page.inner_toolbar) {
            listview.page.inner_toolbar.append(badge);
        }
        listview.__orderlift_selection_badge = badge;
        const result = listResult(listview);
        result.off("change.orderliftItemSelection click.orderliftItemSelection");
        result.on("change.orderliftItemSelection click.orderliftItemSelection", "input[type='checkbox']", function () {
            scheduleSelectionSync(listview);
        });
        updateSelectionButton(listview);
    }

    function scheduleSelectionSync(listview) {
        if (!listview) return;
        window.clearTimeout(listview.__orderlift_selection_sync_timer);
        listview.__orderlift_selection_sync_timer = window.setTimeout(() => syncVisibleSelection(listview), 80);
    }

    function scheduleSelectionRestore(listview) {
        if (!listview) return;
        window.clearTimeout(listview.__orderlift_selection_timer);
        listview.__orderlift_selection_timer = window.setTimeout(() => restoreVisibleSelection(listview), 180);
    }

    function restoreVisibleSelection(listview) {
        const selected = listview.__orderlift_selected_item_codes || new Set();
        listResult(listview).find(".list-row-container").each(function (index) {
            const itemCode = itemCodeForContainer(listview, $(this), index);
            const checkbox = $(this).find("input[type='checkbox']").first();
            if (checkbox.length && itemCode) {
                checkbox.prop("checked", selected.has(itemCode));
            }
        });
        updateSelectionButton(listview);
    }

    function updateSelectionButton(listview) {
        const button = listview && listview.__orderlift_clear_selection_button;
        const count = (listview.__orderlift_selected_item_codes || new Set()).size;
        if (button && button.length) {
            button.text(count ? __("Clear Selection ({0})", [count]) : __("Clear Selection"));
        }
        const badge = listview && listview.__orderlift_selection_badge;
        if (badge && badge.length) {
            badge.text(__("{0} selected", [count]));
            badge.toggleClass("active", count > 0);
        }
    }

    function installQuickPrices(listview) {
        if (!listview || listview.__orderlift_quick_item_prices_installed) return;
        listview.__orderlift_quick_item_prices_installed = true;
        listview.page.add_inner_button(__("Quick Item Prices"), () => showQuickPriceDialog(listview));
    }

    async function installPriceListFilter(listview) {
        if (!listview || listview.__orderlift_price_list_filter_installed) return;
        listview.__orderlift_price_list_filter_installed = true;
        ensureStockStyles();
        const control = $(`
            <div class="ol-item-price-list-filter">
                <label>${esc(__("Price List"))}</label>
                <select data-orderlift-price-list-filter><option value="">${esc(__("Loading..."))}</option></select>
            </div>
        `);
        placePriceListControl(listview, control);
        control.find("select").on("change", function () {
            applyPriceListFilter(listview, $(this).val());
        });
        listview.__orderlift_price_list_control = control;
        await loadPriceListOptions(listview, control.find("select"));
    }

    async function loadPriceListOptions(listview, select) {
        try {
            const response = await frappe.call({ method: `${API}.get_item_list_price_lists` });
            const lists = ((response.message || {}).price_lists || []).map((row) => row.name).filter(Boolean);
            listview.__orderlift_allowed_price_lists = lists;
            select.html([`<option value="">${esc(__("All Price Lists"))}</option>`, ...lists.map((name) => `<option value="${attr(name)}">${esc(name)}</option>`)].join(""));
        } catch (error) {
            console.error("Orderlift Item price list filter options failed", error);
            select.html(`<option value="">${esc(__("Price Lists unavailable"))}</option>`);
        }
    }

    function placePriceListControl(listview, control) {
        const target = filterControlTarget(listview);
        if (target.length) {
            if (!target.find(".ol-item-price-list-filter").length) target.append(control);
            return;
        }
        window.setTimeout(() => placePriceListControl(listview, control), 150);
    }

    function filterControlTarget(listview) {
        const filterWrapper = listview && listview.filter_area && listview.filter_area.$wrapper;
        if (filterWrapper && filterWrapper.length) return filterWrapper;
        const root = listview && listview.page && listview.page.wrapper ? $(listview.page.wrapper) : $(document);
        const selectors = [".filter-area", ".list-filter-area", ".list-filters", ".standard-filter-section", ".filters-section"];
        for (const selector of selectors) {
            const target = root.find(selector).first();
            if (target.length) return target;
        }
        return $();
    }

    async function applyPriceListFilter(listview, priceList) {
        priceList = String(priceList || "").trim();
        if (listview.__orderlift_applying_price_list_filter) return;
        listview.__orderlift_applying_price_list_filter = true;
        try {
            if (!priceList) {
                await clearManagedNameFilter(listview);
                listview.__orderlift_active_price_list = "";
                refreshList(listview);
                return;
            }

            const response = await frappe.call({
                method: `${API}.get_items_for_price_list`,
                args: { price_list: priceList },
                freeze: true,
                freeze_message: __("Filtering Items by Price List..."),
            });
            const itemCodes = ((response.message || {}).item_codes || []).filter(Boolean);
            await replaceManagedNameFilter(listview, itemCodes.length ? itemCodes : [EMPTY_FILTER_SENTINEL]);
            listview.__orderlift_active_price_list = priceList;
            if (!itemCodes.length) {
                frappe.show_alert({ message: __("No Items have prices in {0}.", [priceList]), indicator: "orange" }, 6);
            }
            refreshList(listview);
        } catch (error) {
            console.error("Orderlift Item Price List filter failed", error);
            frappe.msgprint({
                title: __("Price List Filter Failed"),
                message: error && error.message ? error.message : __("Unable to filter Items by Price List."),
                indicator: "red",
            });
        } finally {
            listview.__orderlift_applying_price_list_filter = false;
        }
    }

    async function replaceManagedNameFilter(listview, itemCodes) {
        const filterArea = listview && listview.filter_area;
        if (!filterArea) return;
        if (!listview.__orderlift_saved_name_filters) {
            listview.__orderlift_saved_name_filters = currentNameFilters(listview);
        }
        await removeNameFilters(filterArea);
        const restored = listview.__orderlift_saved_name_filters || [];
        const managed = [[listview.doctype, "name", "in", itemCodes]];
        await addFilters(filterArea, [...restored, ...managed]);
    }

    async function clearManagedNameFilter(listview) {
        const filterArea = listview && listview.filter_area;
        if (!filterArea) return;
        const restored = listview.__orderlift_saved_name_filters || [];
        await removeNameFilters(filterArea);
        if (restored.length) await addFilters(filterArea, restored);
        listview.__orderlift_saved_name_filters = null;
    }

    function currentNameFilters(listview) {
        try {
            return (listview.filter_area.get() || []).filter((row) => Array.isArray(row) && row[1] === "name");
        } catch (error) {
            return [];
        }
    }

    function removeNameFilters(filterArea) {
        try {
            return Promise.resolve(filterArea.remove("name"));
        } catch (error) {
            return Promise.resolve();
        }
    }

    function addFilters(filterArea, filters) {
        if (!filters.length) return Promise.resolve();
        try {
            return Promise.resolve(filterArea.add(filters));
        } catch (error) {
            return Promise.resolve();
        }
    }

    function refreshList(listview) {
        if (listview && typeof listview.refresh === "function") {
            listview.refresh();
        }
    }

    function scheduleStockRefresh(listview) {
        if (!listview) return;
        window.clearTimeout(listview.__orderlift_stock_timer);
        listview.__orderlift_stock_timer = window.setTimeout(() => refreshStockColumn(listview), 120);
    }

    async function refreshStockColumn(listview) {
        const itemCodes = visibleItemCodes(listview);
        ensureStockStyles();
        if (!itemCodes.length) return;
        try {
            const response = await frappe.call({
                method: `${API}.get_item_list_stock_totals`,
                args: { item_codes: JSON.stringify(itemCodes) },
            });
            renderStockColumn(listview, (response.message || {}).rows || {});
        } catch (error) {
            console.error("Orderlift Item stock totals failed", error);
        }
    }

    function visibleItemCodes(listview) {
        return (listview.data || []).map((row) => row.name).filter(Boolean);
    }

    function renderStockColumn(listview, stockMap) {
        const result = listResult(listview);
        const rows = listview.data || [];
        if (!result || !result.length) return;
        const containers = result.find(".list-row-container");
        containers.each(function (index) {
            const item = rows[index] || {};
            const value = stockMap[item.name] == null ? 0 : stockMap[item.name];
            item[STOCK_FIELD] = value;
            const cell = stockFieldCell($(this));
            if (cell.length) cell.text(formatQty(value));
        });
    }

    function stockFieldCell(container) {
        const selectors = [
            `[data-fieldname="${STOCK_FIELD}"]`,
            `[data-field-name="${STOCK_FIELD}"]`,
            `.list-row-col[data-fieldname="${STOCK_FIELD}"]`,
        ];
        for (const selector of selectors) {
            const cell = container.find(selector).first();
            if (cell.length) return cell;
        }
        return $();
    }

    function listResult(listview) {
        return listview && listview.$result ? listview.$result : $();
    }

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
        injectQuickStyles();
        await loadQuickRows(dialog, itemCodes);
    }

    function selectedItemCodes(listview) {
        syncVisibleSelection(listview);
        const persistent = Array.from(listview.__orderlift_selected_item_codes || []);
        if (persistent.length) return persistent;
        const rows = typeof listview.get_checked_items === "function" ? listview.get_checked_items() : [];
        return rows.map((row) => row.name).filter(Boolean);
    }

    function syncVisibleSelection(listview) {
        if (!listview) return;
        if (!listview.__orderlift_selected_item_codes) listview.__orderlift_selected_item_codes = new Set();
        const selected = listview.__orderlift_selected_item_codes;
        listResult(listview).find(".list-row-container").each(function (index) {
            const itemCode = itemCodeForContainer(listview, $(this), index);
            const checkbox = $(this).find("input[type='checkbox']").first();
            if (!itemCode || !checkbox.length) return;
            if (checkbox.is(":checked")) {
                selected.add(itemCode);
            } else {
                selected.delete(itemCode);
            }
        });
        updateSelectionButton(listview);
    }

    function itemCodeForContainer(listview, container, index) {
        const direct = container.attr("data-name") || container.attr("data-docname") || container.attr("data-row-name");
        if (direct) return direct;
        const named = container.find("[data-name], [data-docname], [data-row-name]").first();
        const nested = named.attr("data-name") || named.attr("data-docname") || named.attr("data-row-name");
        if (nested) return nested;
        const checkbox = container.find("input[type='checkbox']").first();
        const checkboxName = checkbox.attr("data-name") || checkbox.attr("data-docname") || checkbox.val();
        if (checkboxName && checkboxName !== "on") return checkboxName;
        return ((listview.data || [])[index] || {}).name || "";
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
        refreshList(listview);
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
            <td><input data-quick-field="currency" value="${attr(row.currency || "")}" readonly></td>
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

    function formatQty(value) {
        const number = Number(value || 0);
        if (!Number.isFinite(number)) return "0";
        return Number.isInteger(number) ? String(number) : number.toFixed(2).replace(/\.00$/, "");
    }

    function esc(value) {
        return frappe.utils.escape_html(String(value == null ? "" : value));
    }

    function attr(value) {
        return esc(value).replace(/`/g, "&#96;");
    }

    function ensureStockStyles() {
        if (document.getElementById("orderlift-item-list-stock-style")) return;
        const style = document.createElement("style");
        style.id = "orderlift-item-list-stock-style";
        style.textContent = `
            [data-fieldname='custom_current_company_stock_qty'],[data-field-name='custom_current_company_stock_qty']{font-variant-numeric:tabular-nums;color:#334155;font-weight:600;text-align:right}
            .ol-item-selection-badge{display:inline-flex;align-items:center;height:28px;margin-left:8px;padding:0 10px;border-radius:999px;background:#f1f5f9;color:#475569;font-size:12px;font-weight:700;vertical-align:middle}
            .ol-item-selection-badge.active{background:#dbeafe;color:#1d4ed8}
            .ol-item-price-list-filter{display:inline-flex;align-items:center;gap:6px;margin:6px 0 0 8px;vertical-align:middle}
            .ol-item-price-list-filter label{margin:0;color:#64748b;font-size:12px;font-weight:700;white-space:nowrap}
            .ol-item-price-list-filter select{height:28px;min-width:190px;border:1px solid #d1d5db;border-radius:6px;background:#fff;color:#111827;padding:0 8px;font-size:12px}
        `;
        document.head.appendChild(style);
    }

    function injectQuickStyles() {
        if (document.getElementById("orderlift-item-list-price-helper-style")) return;
        const style = document.createElement("style");
        style.id = "orderlift-item-list-price-helper-style";
        style.textContent = `
            .olq-help{border:1px solid #dbeafe;border-radius:8px;background:#eff6ff;color:#1e3a8a;padding:9px 10px;margin-bottom:10px;font-weight:600}.olq-table-wrap{max-height:520px;overflow:auto;border:1px solid #e5e7eb;border-radius:10px}.olq-table{width:100%;border-collapse:collapse}.olq-table th,.olq-table td{padding:8px;border-bottom:1px solid #edf2f7;vertical-align:middle}.olq-table th{position:sticky;top:0;background:#f8fafc;color:#475569;font-size:11px;text-transform:uppercase;z-index:1}.olq-table input{height:32px;border:1px solid #cbd5e1;border-radius:7px;padding:0 8px;background:#fff}.olq-table input[readonly]{background:#f8fafc;color:#64748b}.olq-table input[data-quick-field='price_list_rate']{text-align:right;min-width:120px}.olq-empty{color:#64748b;text-align:center;padding:18px}.olq-error{border:1px solid #fecaca;border-radius:8px;background:#fef2f2;color:#991b1b;padding:10px}
        `;
        document.head.appendChild(style);
    }
})();
