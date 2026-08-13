(function () {
    const STASH_PREFIX = "orderlift:sales_invoice_mode_items:";
    const MODE_FIELD = "custom_invoice_mode";

    frappe.ui.form.on("Sales Invoice", {
        refresh(frm) {
            hideStockInvoiceFields(frm);
            if (!frm.is_new()) return;
            setupModeChooser(frm);
        },
        onload_post_render(frm) {
            hideStockInvoiceFields(frm);
        },
        customer(frm) {
            if (!frm.is_new()) return;
            setupModeChooser(frm);
        },
    });

    function setupModeChooser(frm) {
        stashInitialItems(frm);
        renderModeBanner(frm);
        addModeButtons(frm);
    }

    function stashInitialItems(frm) {
        if (frm.__orderlift_mode_stashed) return;
        frm.__orderlift_mode_stashed = true;
        if ((frm.doc[MODE_FIELD] || "").trim()) return;
        const rows = (frm.doc.items || []).map((row) => Object.assign({}, row));
        if (!rows.length) return;
        sessionStorage.setItem(stashKey(frm), JSON.stringify(rows));
        frm.clear_table("items");
        frm.refresh_field("items");
        frm.dirty();
    }

    function renderModeBanner(frm) {
        const wrapper = getBannerWrapper(frm);
        if (!wrapper) return;
        const mode = frm.doc[MODE_FIELD] || "";
        const label = mode ? __("Selected invoice mode: {0}", [mode]) : __("Choose how to build this Sales Invoice before adding lines.");
        wrapper.innerHTML = `
            <div class="ol-si-mode-banner ${mode ? "is-selected" : ""}">
                <div class="ol-si-mode-copy">
                    <strong>${frappe.utils.escape_html(label)}</strong>
                    <span>${frappe.utils.escape_html(__("Items, advance, and custom invoice modes keep the invoice lines explicit."))}</span>
                </div>
                <div class="ol-si-mode-actions">
                    <button class="btn btn-sm btn-primary" type="button" data-ol-si-mode="items">${frappe.utils.escape_html(__("Invoice Based on Items"))}</button>
                    <button class="btn btn-sm btn-default" type="button" data-ol-si-mode="advance">${frappe.utils.escape_html(__("Invoice Based on Advance"))}</button>
                    <button class="btn btn-sm btn-default" type="button" data-ol-si-mode="custom">${frappe.utils.escape_html(__("Custom Invoice"))}</button>
                </div>
            </div>
        `;
        wrapper.querySelector('[data-ol-si-mode="items"]')?.addEventListener("click", () => chooseItemsMode(frm));
        wrapper.querySelector('[data-ol-si-mode="advance"]')?.addEventListener("click", () => chooseAdvanceMode(frm));
        wrapper.querySelector('[data-ol-si-mode="custom"]')?.addEventListener("click", () => chooseCustomMode(frm));
        ensureStyles();
    }

    function getBannerWrapper(frm) {
        if (frm.__orderlift_mode_banner) return frm.__orderlift_mode_banner;
        const anchor = frm.fields_dict.items && frm.fields_dict.items.wrapper;
        if (!anchor) return null;
        const wrapper = document.createElement("div");
        wrapper.className = "ol-si-mode-wrapper";
        anchor.parentNode.insertBefore(wrapper, anchor);
        frm.__orderlift_mode_banner = wrapper;
        return wrapper;
    }

    function addModeButtons(frm) {
        if (frm.__orderlift_mode_buttons_added) return;
        frm.__orderlift_mode_buttons_added = true;
        // Keep the workflow in the form banner instead of burying it in the toolbar.
    }

    function hideStockInvoiceFields(frm) {
        ["scan_barcode", "last_scanned_warehouse", "update_stock", "set_warehouse", "set_target_warehouse"].forEach((fieldname) => {
            if (!frm.fields_dict[fieldname]) return;
            frm.set_df_property(fieldname, "hidden", 1);
            frm.toggle_display(fieldname, false);
        });
    }

    function chooseItemsMode(frm) {
        const stashed = getStashedItems(frm);
        frm.clear_table("items");
        stashed.forEach((row) => {
            const child = frm.add_child("items");
            copyRow(row, child);
        });
        clearAdvanceHeader(frm);
        frappe.model.set_value(frm.doctype, frm.doc.name, MODE_FIELD, "Items");
        frm.refresh_field("items");
        renderModeBanner(frm);
        frm.dirty();
    }

    async function chooseAdvanceMode(frm) {
        if (!frm.doc.customer || !frm.doc.company) {
            frappe.msgprint(__("Select Customer and Company before choosing an advance invoice."));
            return;
        }
        const defaults = await getDefaults(frm);
        const options = await getAdvanceOptions(frm);
        if (!options.length) {
            frappe.msgprint(__("No paid or scheduled advances are available for this customer."));
            return;
        }
        const optionLabels = options.map(formatAdvanceOption);
        const optionsByLabel = Object.fromEntries(options.map((row, index) => [optionLabels[index], row]));
        const dialog = new frappe.ui.Dialog({
            title: __("Invoice Based on Advance"),
            fields: [
                { fieldtype: "HTML", fieldname: "advance_preview" },
                {
                    fieldtype: "Select",
                    fieldname: "advance_key",
                    label: __("Advance"),
                    reqd: 1,
                    options: optionLabels.join("\n"),
                },
                { fieldtype: "Currency", fieldname: "amount", label: __("Amount HT"), reqd: 1 },
                {
                    fieldtype: "Link",
                    fieldname: "income_account",
                    label: __("Income Account"),
                    options: "Account",
                    default: defaults.income_account || "",
                    reqd: 1,
                    get_query: () => ({ filters: { company: frm.doc.company, is_group: 0 } }),
                },
                {
                    fieldtype: "Link",
                    fieldname: "cost_center",
                    label: __("Cost Center"),
                    options: "Cost Center",
                    default: defaults.cost_center || "",
                    get_query: () => ({ filters: { company: frm.doc.company, is_group: 0 } }),
                },
            ],
            primary_action_label: __("Use Advance"),
            primary_action: async (values) => {
                const option = optionsByLabel[values.advance_key];
                const payload = await buildAdvancePayload(option, values);
                applySingleRowPayload(frm, payload);
                dialog.hide();
            },
        });
        dialog.fields_dict.advance_key.df.onchange = () => {
            const option = optionsByLabel[dialog.get_value("advance_key")];
            if (option) dialog.set_value("amount", option.available_amount);
        };
        dialog.show();
        dialog.fields_dict.advance_preview.$wrapper.html(renderAdvancePreview(options));
        dialog.set_value("advance_key", optionLabels[0]);
        dialog.set_value("amount", options[0].available_amount);
    }

    async function chooseCustomMode(frm) {
        if (!frm.doc.company) {
            frappe.msgprint(__("Select Company before creating a custom invoice."));
            return;
        }
        const defaults = await getDefaults(frm);
        const dialog = new frappe.ui.Dialog({
            title: __("Custom Invoice"),
            fields: [
                { fieldtype: "Data", fieldname: "item_name", label: __("Designation"), reqd: 1 },
                { fieldtype: "Small Text", fieldname: "description", label: __("Description") },
                { fieldtype: "Currency", fieldname: "amount", label: __("Amount HT"), reqd: 1 },
                {
                    fieldtype: "Link",
                    fieldname: "income_account",
                    label: __("Income Account"),
                    options: "Account",
                    default: defaults.income_account || "",
                    reqd: 1,
                    get_query: () => ({ filters: { company: frm.doc.company, is_group: 0 } }),
                },
                {
                    fieldtype: "Link",
                    fieldname: "cost_center",
                    label: __("Cost Center"),
                    options: "Cost Center",
                    default: defaults.cost_center || "",
                    get_query: () => ({ filters: { company: frm.doc.company, is_group: 0 } }),
                },
            ],
            primary_action_label: __("Create Line"),
            primary_action: async (values) => {
                const payload = await buildCustomPayload(values);
                applySingleRowPayload(frm, payload);
                dialog.hide();
            },
        });
        dialog.show();
    }

    function applySingleRowPayload(frm, payload) {
        frm.clear_table("items");
        const child = frm.add_child("items");
        copyRow(payload.row || {}, child);
        Object.entries(payload.header || {}).forEach(([fieldname, value]) => {
            frappe.model.set_value(frm.doctype, frm.doc.name, fieldname, value || "");
        });
        frm.refresh_field("items");
        renderModeBanner(frm);
        frm.dirty();
    }

    function clearAdvanceHeader(frm) {
        ["custom_advance_payment_entry", "custom_advance_sales_order", "custom_advance_payment_schedule_row"].forEach((fieldname) => {
            if (frm.fields_dict[fieldname]) frappe.model.set_value(frm.doctype, frm.doc.name, fieldname, "");
        });
    }

    async function getAdvanceOptions(frm) {
        const response = await frappe.call({
            method: "orderlift.orderlift_sales.sales_invoice_modes.get_available_advance_options",
            args: {
                customer: frm.doc.customer,
                company: frm.doc.company,
                sales_orders: JSON.stringify(sourceSalesOrders(frm)),
            },
        });
        return response.message || [];
    }

    async function getDefaults(frm) {
        const response = await frappe.call({
            method: "orderlift.orderlift_sales.sales_invoice_modes.get_invoice_mode_defaults",
            args: { company: frm.doc.company },
        });
        return response.message || {};
    }

    async function buildAdvancePayload(option, values) {
        const response = await frappe.call({
            method: "orderlift.orderlift_sales.sales_invoice_modes.build_advance_invoice_payload",
            args: {
                option,
                amount: values.amount,
                income_account: values.income_account,
                cost_center: values.cost_center,
            },
        });
        return response.message || {};
    }

    async function buildCustomPayload(values) {
        const response = await frappe.call({
            method: "orderlift.orderlift_sales.sales_invoice_modes.build_custom_invoice_payload",
            args: values,
        });
        return response.message || {};
    }

    function sourceSalesOrders(frm) {
        return Array.from(new Set((getStashedItems(frm).concat(frm.doc.items || [])).map((row) => row.sales_order).filter(Boolean)));
    }

    function formatAdvanceOption(row) {
        const amount = format_currency(row.available_amount, row.currency || frmCurrency());
        const date = row.posting_date ? ` - ${row.posting_date}` : "";
        return `${row.source_label}: ${row.reference}${date} (${amount})`;
    }

    function renderAdvancePreview(options) {
        const rows = options
            .map((row) => `<tr><td>${frappe.utils.escape_html(row.source_label || "")}</td><td>${frappe.utils.escape_html(row.reference || "")}</td><td class="text-right">${frappe.utils.escape_html(format_currency(row.available_amount, row.currency || frmCurrency()))}</td></tr>`)
            .join("");
        return `<div class="small text-muted" style="margin-bottom:8px">${frappe.utils.escape_html(__("Paid advances are shown first, followed by scheduled Sales Order advances."))}</div><div style="max-height:180px;overflow:auto"><table class="table table-bordered table-condensed"><thead><tr><th>${frappe.utils.escape_html(__("Type"))}</th><th>${frappe.utils.escape_html(__("Reference"))}</th><th class="text-right">${frappe.utils.escape_html(__("Available"))}</th></tr></thead><tbody>${rows}</tbody></table></div>`;
    }

    function frmCurrency() {
        return frappe.defaults.get_default("currency") || "";
    }

    function getStashedItems(frm) {
        try {
            return JSON.parse(sessionStorage.getItem(stashKey(frm)) || "[]");
        } catch (error) {
            console.warn("Unable to read stashed invoice items", error);
            return [];
        }
    }

    function stashKey(frm) {
        const token = frm.doc.__islocal ? frm.doc.name : frm.doc.name || "new";
        return `${STASH_PREFIX}${token}`;
    }

    function copyRow(source, target) {
        Object.keys(source || {}).forEach((key) => {
            if (["doctype", "name", "parent", "parentfield", "parenttype", "idx", "__unsaved"].includes(key)) return;
            target[key] = source[key];
        });
    }

    function ensureStyles() {
        if (document.getElementById("ol-si-mode-styles")) return;
        const style = document.createElement("style");
        style.id = "ol-si-mode-styles";
        style.textContent = `
            .ol-si-mode-wrapper{margin:10px 0 12px}.ol-si-mode-banner{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;padding:12px 14px;border:1px solid var(--border-color);border-radius:12px;background:var(--control-bg);color:var(--text-color)}.ol-si-mode-copy{display:grid;gap:3px;min-width:240px}.ol-si-mode-banner strong{font-size:13px}.ol-si-mode-banner span{font-size:12px;color:var(--text-muted)}.ol-si-mode-actions{display:flex;gap:8px;flex-wrap:wrap}.ol-si-mode-banner.is-selected{border-color:var(--primary);background:var(--blue-50)}
        `;
        document.head.appendChild(style);
    }
})();
