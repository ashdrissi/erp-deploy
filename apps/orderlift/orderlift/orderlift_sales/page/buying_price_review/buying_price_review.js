(function () {
    const PAGE_NAME = "buying-price-review";
    const API = "orderlift.orderlift_sales.page.buying_price_review.buying_price_review";
    const state = { rows: [], priceLists: [], targets: {}, status: "Pending", supplier: "", priceList: "", itemCode: "", selected: new Set(), loading: false, message: "" };

    frappe.pages[PAGE_NAME].on_page_load = function (wrapper) {
        const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Buying Price Review"), single_column: true });
        wrapper.page = page;
        page.main.addClass("orderlift-buying-price-review");
        injectStyles();
        page.set_primary_action(__("Refresh"), () => load(page), "refresh");
        render(page);
        load(page);
    };

    frappe.pages[PAGE_NAME].on_page_show = function (wrapper) {
        if (wrapper.page) load(wrapper.page);
    };

    async function load(page) {
        state.loading = true;
        render(page);
        try {
            const response = await call("get_review_data", {
                status: state.status,
                supplier: state.supplier,
                price_list: state.priceList,
                item_code: state.itemCode,
            });
            state.rows = response.rows || [];
            state.priceLists = response.buying_price_lists || [];
            state.targets = Object.fromEntries(state.rows.map((row) => [row.purchase_order_item, row.price_list || ""]));
            state.selected.clear();
            state.message = "";
        } catch (error) {
            state.message = error?.message || __("Could not load buying price reviews.");
        } finally {
            state.loading = false;
            render(page);
        }
    }

    function render(page) {
        page.main.html(`
            <main class="opr-shell">
                <header class="opr-header">
                    <div><div class="opr-eyebrow">${__("Purchasing")}</div><h1>${__("Buying Price Review")}</h1><p>${__("Approve buying price updates and new Item Prices across draft Purchase Orders.")}</p></div>
                    <div class="opr-count">${state.rows.length} ${__("rows")}</div>
                </header>
                <section class="opr-toolbar">
                    <select data-filter="status"><option value="Pending">${__("Pending")}</option><option value="All">${__("All reviewed rows")}</option><option value="Approved">${__("Approved")}</option><option value="Skipped">${__("Skipped")}</option></select>
                    <input data-filter="supplier" value="${attr(state.supplier)}" placeholder="${__("Supplier")}" />
                    <input data-filter="priceList" value="${attr(state.priceList)}" placeholder="${__("Buying Price List")}" />
                    <input data-filter="itemCode" value="${attr(state.itemCode)}" placeholder="${__("Item")}" />
                    <button class="btn btn-default" data-action="filter">${__("Apply Filters")}</button>
                </section>
                ${state.message ? `<div class="alert alert-danger">${esc(state.message)}</div>` : ""}
                ${state.loading ? `<div class="opr-empty">${__("Loading reviews...")}</div>` : renderTable()}
            </main>
        `);
        bind(page);
    }

    function renderTable() {
        if (!state.rows.length) return `<div class="opr-empty">${__("No buying price reviews match the current filters.")}</div>`;
        const allSelected = state.rows.length && state.rows.every((row) => state.selected.has(row.purchase_order_item));
        const rows = state.rows.map((row) => `
            <tr>
                <td><input type="checkbox" data-item="${attr(row.purchase_order_item)}" ${state.selected.has(row.purchase_order_item) ? "checked" : ""} /></td>
                <td><a href="/app/purchase-order/${encodeURIComponent(row.purchase_order)}">${esc(row.purchase_order)}</a></td>
                <td>${esc(row.supplier_name || row.supplier || "")}</td>
                <td>${esc(row.item_code || "")}<div class="text-muted small">${esc(__(row.review_type || "Update Existing Price"))}</div></td>
                <td>${renderTargetList(row)}</td>
                <td>${row.review_type === "Create New Price" ? "-" : money(row.source_rate, row.source_currency || row.po_currency || row.currency)}</td>
                <td>${row.review_type === "Create New Price" ? "-" : money(row.loaded_rate, row.po_currency || row.currency)}</td>
                <td>${money(row.negotiated_rate, row.po_currency || row.currency)}</td>
                <td data-target-price="${attr(row.purchase_order_item)}">${renderTargetPrice(row)}</td>
                <td class="${row.review_type === "Create New Price" ? "" : (Number(row.variance_amount) < 0 ? "opr-good" : "opr-bad")}">${row.review_type === "Create New Price" ? "-" : money(row.variance_amount, row.po_currency || row.currency)}</td>
                <td><span class="opr-status ${row.decision === "Pending" ? "pending" : "reviewed"}">${esc(row.decision)}</span></td>
            </tr>`).join("");
        return `<section class="opr-card"><div class="opr-actions"><label><input type="checkbox" data-action="select-all" ${allSelected ? "checked" : ""} /> ${__("Select all")}</label><button class="btn btn-primary" data-action="approve">${__("Approve & Create/Update Prices")}</button><button class="btn btn-default" data-action="skip">${__("Skip Updates")}</button></div><div class="table-responsive"><table class="table table-bordered"><thead><tr><th></th><th>${__("Purchase Order")}</th><th>${__("Supplier")}</th><th>${__("Item")}</th><th>${__("Target Price List")}</th><th>${__("List price")}</th><th>${__("Loaded in PO")}</th><th>${__("PO Price")}</th><th>${__("Target list price")}</th><th>${__("Difference")}</th><th>${__("Status")}</th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
    }

    function renderTargetList(row) {
        if (row.review_type !== "Create New Price" || row.decision !== "Pending") return esc(row.price_list || "");
        const selected = state.targets[row.purchase_order_item] || "";
        const options = targetPriceLists(row).map((entry) => {
            const name = String(entry.price_list || "");
            const currency = String(entry.currency || "");
            return `<option value="${attr(name)}" ${name === selected ? "selected" : ""}>${esc(name)}${currency ? ` (${esc(currency)})` : ""}</option>`;
        }).join("");
        return `<select class="form-control input-sm" data-target-list="${attr(row.purchase_order_item)}"><option value="">${__("Select target list")}</option>${options}</select>`;
    }

    function targetPriceLists(row) {
        return row.target_price_lists || state.priceLists || [];
    }

    function convertedTargetPrice(row) {
        const selected = state.targets[row.purchase_order_item] || row.price_list || "";
        const details = targetPriceLists(row).find((entry) => String(entry.price_list || "") === selected);
        const exchangeRate = Number(details?.exchange_rate || 0);
        if (!selected || exchangeRate <= 0) return null;
        let rate = Number(row.negotiated_rate || 0) / exchangeRate;
        const sourceUom = String(row.source_uom || row.uom || "");
        const rowUom = String(row.uom || "");
        const stockUom = String(row.stock_uom || "");
        if (sourceUom && sourceUom === stockUom && rowUom && rowUom !== stockUom) {
            rate /= Number(row.conversion_factor || 1) || 1;
        }
        return { rate, currency: details.currency || row.source_currency || "" };
    }

    function renderTargetPrice(row) {
        const converted = convertedTargetPrice(row);
        if (converted) return money(converted.rate, converted.currency);
        const selected = state.targets[row.purchase_order_item] || row.price_list || "";
        return selected ? `<span class="text-danger">${__("No exchange rate")}</span>` : "-";
    }

    function bind(page) {
        page.main.find("[data-filter]").on("change input", function () { state[this.dataset.filter] = this.value; });
        page.main.find('[data-action="filter"]').on("click", () => load(page));
        page.main.find('[data-action="select-all"]').on("change", function () {
            state.rows.forEach((row) => this.checked ? state.selected.add(row.purchase_order_item) : state.selected.delete(row.purchase_order_item));
            render(page);
        });
        page.main.find('input[data-item]').on("change", function () { this.checked ? state.selected.add(this.dataset.item) : state.selected.delete(this.dataset.item); });
        page.main.find("select[data-target-list]").on("change", function () {
            const itemName = this.dataset.targetList;
            state.targets[itemName] = this.value;
            const row = state.rows.find((entry) => entry.purchase_order_item === itemName);
            page.main.find("[data-target-price]").filter(function () {
                return String($(this).attr("data-target-price") || "") === itemName;
            }).html(renderTargetPrice(row));
        });
        page.main.find('[data-action="approve"]').on("click", () => submitSelected(page, "Approved", 1));
        page.main.find('[data-action="skip"]').on("click", () => submitSelected(page, "Skipped", 0));
    }

    function submitSelected(page, decision, attestation) {
        const rows = state.rows.filter((row) => state.selected.has(row.purchase_order_item));
        if (!rows.length) return frappe.msgprint(__("Select at least one review row."));
        if (decision === "Approved") {
            const missingTarget = rows.find((row) => row.review_type === "Create New Price" && !state.targets[row.purchase_order_item]);
            if (missingTarget) return frappe.msgprint(__("Select a target Buying Price List for item {0}.", [missingTarget.item_code]));
        }
        const submit = () => call("review_selected", { decisions: JSON.stringify(rows.map((row) => ({
            purchase_order: row.purchase_order,
            purchase_order_item: row.purchase_order_item,
            decision,
            target_price_list: state.targets[row.purchase_order_item] || row.price_list || "",
        }))), attestation }).then(() => load(page));
        if (decision === "Approved") {
            frappe.confirm(__("I confirm these approved prices may create or update Item Prices in the selected buying lists when the Purchase Orders are submitted."), submit);
        } else {
            submit();
        }
    }

    function call(method, args) {
        return new Promise((resolve, reject) => frappe.call({ method: `${API}.${method}`, args, callback: (response) => resolve(response.message || {}), error: reject }));
    }

    function money(value, currency) {
        const code = String(currency || "").trim();
        const amount = Number(value || 0);
        const formatted = amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        return code ? `${code} ${formatted}` : formatted;
    }

    function esc(value) { return frappe.utils.escape_html(String(value ?? "")); }
    function attr(value) { return esc(value).replace(/"/g, "&quot;"); }

    function injectStyles() {
        if (document.getElementById("orderlift-buying-price-review-styles")) return;
        const style = document.createElement("style");
        style.id = "orderlift-buying-price-review-styles";
        style.textContent = `.opr-shell{max-width:1440px;margin:0 auto;padding:28px}.opr-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:24px}.opr-eyebrow{color:#8a6840;text-transform:uppercase;letter-spacing:.12em;font-size:11px;font-weight:700}.opr-header h1{margin:4px 0;font-family:Georgia,serif;font-size:32px}.opr-header p{color:#667085;margin:0}.opr-count{font-size:24px;font-weight:700}.opr-toolbar,.opr-card{background:#fff;border:1px solid #e6e1d8;border-radius:12px;padding:16px;margin-bottom:16px}.opr-toolbar{display:flex;gap:10px;align-items:center}.opr-toolbar input,.opr-toolbar select{border:1px solid #d8d1c5;border-radius:7px;padding:8px 10px}.opr-actions{display:flex;gap:10px;align-items:center;margin-bottom:14px}.opr-actions label{margin-right:auto}.opr-status{border-radius:999px;padding:3px 9px;font-size:11px;font-weight:700}.opr-status.pending{background:#fff1d6;color:#9a5b00}.opr-status.reviewed{background:#e7f5ec;color:#18733d}.opr-good{color:#18733d}.opr-bad{color:#b54708}.opr-empty{padding:48px;text-align:center;color:#667085;background:#faf9f7;border-radius:10px}@media(max-width:800px){.opr-shell{padding:14px}.opr-header,.opr-toolbar{display:block}.opr-toolbar>*{margin:4px 0;width:100%}.opr-card{overflow:auto}.opr-actions{min-width:700px}}`;
        document.head.appendChild(style);
    }
})();
