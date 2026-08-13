(function () {
    const PAGE_NAME = "stock-rate-review";
    const API = "orderlift.orderlift_logistics.utils.stock_rate_review";
    const STATE = {
        rows: [],
        kpis: {},
        canSubmit: {},
        selected: new Set(),
        rates: {},
        filters: { doctype: "", status: "", search: "" },
        loading: false,
    };

    frappe.pages[PAGE_NAME].on_page_load = function (wrapper) {
        const page = frappe.ui.make_app_page({
            parent: wrapper,
            title: __("Stock Rate Review"),
            single_column: true,
        });
        wrapper.page = page;
        page.main.addClass("srr-root");
        injectStyles();
        page.set_primary_action(__("Refresh Suggestions"), () => refreshSuggestions(page), "refresh");
        render(page);
        loadRows(page);
    };

    frappe.pages[PAGE_NAME].on_page_show = function (wrapper) {
        if (wrapper.page) loadRows(wrapper.page);
    };

    async function call(method, args = {}) {
        const response = await frappe.call({ method: `${API}.${method}`, args, freeze: true });
        return response.message || {};
    }

    async function loadRows(page) {
        STATE.loading = true;
        render(page);
        try {
            const payload = await call("get_review_payload", { filters: JSON.stringify(STATE.filters) });
            STATE.rows = payload.rows || [];
            STATE.kpis = payload.kpis || {};
            STATE.canSubmit = payload.can_submit || {};
            STATE.selected.clear();
            STATE.rates = {};
        } catch (error) {
            frappe.msgprint(error.message || __("Could not load stock rate review."));
        } finally {
            STATE.loading = false;
            render(page);
        }
    }

    function render(page) {
        page.main.html(`
            <main class="srr-shell">
                <nav class="srr-breadcrumb">
                    <a href="/desk/home-page?sidebar=Main+Dashboard">${__("Warehouse & Stock")}</a>
                    <span>/</span><strong>${__("Stock Rate Review")}</strong>
                </nav>
                <section class="srr-hero">
                    <div><span>${__("Inventory valuation")}</span><h1>${__("Complete stock rates in bulk")}</h1><p>${__("Warehouse quantities stay in their native documents. Review missing or provisional values here. Approval of a submitted row confirms its posted rate; changing it requires the normal ERPNext correction flow.")}</p></div>
                    <div class="srr-kpis">
                        ${kpi(STATE.kpis.missing || 0, __("Missing"), "danger")}
                        ${kpi(STATE.kpis.provisional || 0, __("Provisional"), "warning")}
                        ${kpi(STATE.kpis.ready || 0, __("Valued drafts"), "success")}
                        ${kpi(STATE.kpis.submitted_provisional || 0, __("Submitted to review"), "info")}
                    </div>
                </section>
                <section class="srr-card">
                    <div class="srr-toolbar">
                        <select data-filter="doctype">
                            ${option("", __("All documents"), STATE.filters.doctype)}
                            ${option("Stock Entry", __("Stock Entry"), STATE.filters.doctype)}
                            ${option("Purchase Receipt", __("Purchase Receipt"), STATE.filters.doctype)}
                        </select>
                        <select data-filter="status">
                            ${option("", __("All statuses"), STATE.filters.status)}
                            ${option("Missing Rate", __("Missing Rate"), STATE.filters.status)}
                            ${option("Provisional Rate", __("Provisional Rate"), STATE.filters.status)}
                            ${option("Approved Rate", __("Approved Rate"), STATE.filters.status)}
                        </select>
                        <input data-filter="search" value="${escapeAttr(STATE.filters.search)}" placeholder="${__("Search document, item, supplier")}">
                        <button class="btn btn-default" data-action="filter">${__("Apply filters")}</button>
                    </div>
                    <div class="srr-actions">
                        <button class="btn btn-primary" data-action="save">${__("Save selected rates")}</button>
                        <button class="btn btn-default" data-action="approve">${__("Approve current rates")}</button>
                        <button class="btn btn-default" data-action="submit">${__("Submit ready documents")}</button>
                        <span>${selectedLabel()}</span>
                    </div>
                    <div class="srr-table-wrap">
                        ${STATE.loading ? `<div class="srr-empty">${__("Loading rate review...")}</div>` : renderTable()}
                    </div>
                </section>
            </main>
        `);
        bindEvents(page);
    }

    function renderTable() {
        if (!STATE.rows.length) return `<div class="srr-empty"><strong>${__("No rates need review")}</strong><span>${__("Missing and provisional stock rates will appear here.")}</span></div>`;
        return `
            <table class="srr-table">
                <thead><tr>
                    <th><input type="checkbox" data-action="select-all"></th>
                    <th>${__("Status")}</th><th>${__("Document")}</th><th>${__("Item")}</th>
                    <th>${__("Qty")}</th><th>${__("Warehouse")}</th><th>${__("Source")}</th>
                    <th>${__("Current")}</th><th>${__("Suggested")}</th><th>${__("Final rate")}</th>
                </tr></thead>
                <tbody>${STATE.rows.map(renderRow).join("")}</tbody>
            </table>`;
    }

    function renderRow(row) {
        const key = rowKey(row);
        const rate = Object.prototype.hasOwnProperty.call(STATE.rates, key)
            ? STATE.rates[key]
            : Number(row.current_rate || row.suggested_rate || 0);
        const submitted = Number(row.docstatus) === 1;
        return `<tr class="${submitted ? "is-submitted" : ""}">
            <td><input type="checkbox" data-select="${escapeAttr(key)}" ${STATE.selected.has(key) ? "checked" : ""}></td>
            <td>${statusBadge(row.status)}${submitted ? `<small>${__("Submitted")}</small>` : ""}</td>
            <td><button class="srr-link" data-open-doctype="${escapeAttr(row.doctype)}" data-open-document="${escapeAttr(row.document)}">${escapeHtml(row.document)}</button><small>${escapeHtml(row.party || row.purpose || row.doctype)} · ${escapeHtml(row.posting_date)}</small></td>
            <td><strong>${escapeHtml(row.item_code)}</strong><small>${escapeHtml(row.item_name)}</small></td>
            <td>${formatNumber(row.qty)} <small>${escapeHtml(row.uom)}</small></td>
            <td>${escapeHtml(row.warehouse || "-")}</td>
            <td>${escapeHtml(row.source || "-")}<small>${escapeHtml(row.source_detail || "")}</small></td>
            <td>${formatRate(row.current_rate)}</td>
            <td>${formatRate(row.suggested_rate)}</td>
            <td>${row.editable
                ? `<input class="srr-rate" type="number" min="0" step="0.01" data-rate="${escapeAttr(key)}" value="${escapeAttr(rate || "")}">`
                : `<strong>${formatRate(row.current_rate)}</strong>`}</td>
        </tr>`;
    }

    function bindEvents(page) {
        page.main.off("change.srr input.srr click.srr");
        page.main.on("change.srr", "[data-filter]", function () {
            STATE.filters[$(this).data("filter")] = $(this).val();
        });
        page.main.on("input.srr", "[data-filter='search']", function () {
            STATE.filters.search = $(this).val();
        });
        page.main.on("input.srr", "[data-rate]", function () {
            STATE.rates[$(this).data("rate")] = Number($(this).val() || 0);
        });
        page.main.on("change.srr", "[data-select]", function () {
            const key = $(this).data("select");
            this.checked ? STATE.selected.add(key) : STATE.selected.delete(key);
            page.main.find(".srr-actions span").text(selectedLabel());
        });
        page.main.on("change.srr", "[data-action='select-all']", function () {
            STATE.selected.clear();
            if (this.checked) STATE.rows.forEach((row) => STATE.selected.add(rowKey(row)));
            render(page);
        });
        page.main.on("click.srr", "[data-action='filter']", () => loadRows(page));
        page.main.on("click.srr", "[data-action='save']", () => saveSelected(page));
        page.main.on("click.srr", "[data-action='approve']", () => approveSelected(page));
        page.main.on("click.srr", "[data-action='submit']", () => submitSelected(page));
        page.main.on("click.srr", "[data-open-document]", function () {
            frappe.set_route("Form", $(this).data("open-doctype"), $(this).data("open-document"));
        });
    }

    async function saveSelected(page) {
        const rows = selectedRows().filter((row) => row.editable).map((row) => ({
            doctype: row.doctype,
            document: row.document,
            row_name: row.row_name,
            rate: Number(STATE.rates[rowKey(row)] || row.current_rate || row.suggested_rate || 0),
        })).filter((row) => row.rate > 0);
        if (!rows.length) return frappe.msgprint(__("Select editable rows and enter a positive final rate."));
        const result = await call("save_rates", { rows: JSON.stringify(rows) });
        frappe.show_alert({ message: __("{0} rate rows saved", [result.updated_rows || 0]), indicator: "green" });
        await loadRows(page);
    }

    async function approveSelected(page) {
        const rows = selectedRows().filter((row) => Number(row.current_rate) > 0);
        if (!rows.length) return frappe.msgprint(__("Select rows that already have a positive current rate."));
        const result = await call("approve_current_rates", { rows: JSON.stringify(rows) });
        frappe.show_alert({ message: __("{0} rate rows approved", [result.approved_rows || 0]), indicator: "green" });
        await loadRows(page);
    }

    async function submitSelected(page) {
        const documents = [];
        const seen = new Set();
        selectedRows().filter((row) => row.editable).forEach((row) => {
            const key = `${row.doctype}::${row.document}`;
            if (seen.has(key)) return;
            seen.add(key);
            documents.push({ doctype: row.doctype, document: row.document });
        });
        if (!documents.length) return frappe.msgprint(__("Select rows from ready draft documents."));
        const result = await call("submit_documents", { documents: JSON.stringify(documents) });
        frappe.show_alert({ message: __("{0} documents submitted", [(result.submitted || []).length]), indicator: "green" });
        await loadRows(page);
    }

    async function refreshSuggestions(page) {
        const result = await call("refresh_suggestions");
        frappe.show_alert({ message: __("{0} documents refreshed", [result.refreshed_documents || 0]), indicator: "blue" });
        await loadRows(page);
    }

    function selectedRows() {
        return STATE.rows.filter((row) => STATE.selected.has(rowKey(row)));
    }

    function rowKey(row) {
        return `${row.doctype}::${row.document}::${row.row_name}`;
    }

    function selectedLabel() {
        return __("{0} selected", [STATE.selected.size]);
    }

    function kpi(value, label, tone) {
        return `<article class="${tone}"><strong>${value}</strong><span>${label}</span></article>`;
    }

    function statusBadge(status) {
        const tone = status === "Missing Rate" ? "danger" : status === "Provisional Rate" ? "warning" : "success";
        return `<span class="srr-badge ${tone}">${escapeHtml(__(status || "Unknown"))}</span>`;
    }

    function option(value, label, current) {
        return `<option value="${escapeAttr(value)}" ${value === current ? "selected" : ""}>${escapeHtml(label)}</option>`;
    }

    function formatRate(value) {
        return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 });
    }

    function formatNumber(value) {
        return Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 3 });
    }

    function escapeHtml(value) {
        return frappe.utils.escape_html(String(value == null ? "" : value));
    }

    function escapeAttr(value) {
        return escapeHtml(value).replace(/"/g, "&quot;");
    }

    function injectStyles() {
        if (document.getElementById("srr-styles")) return;
        $("<style id='srr-styles'>").text(`
            .srr-root{background:#f2f5f7;min-height:100vh}.srr-shell{max-width:1500px;margin:0 auto;padding:18px 18px 56px;color:#17212b}.srr-breadcrumb{display:flex;gap:8px;align-items:center;margin-bottom:12px;color:#6b7785;font-size:12px}.srr-breadcrumb a{color:#176b87}.srr-hero{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:20px;align-items:center;padding:22px;border:1px solid #d8e2e8;border-radius:18px;background:linear-gradient(135deg,#fff 0%,#edf7f8 100%);box-shadow:0 14px 34px rgba(20,47,63,.06)}.srr-hero>div>span{color:#0f7490;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.08em}.srr-hero h1{margin:5px 0 7px;font-size:30px;letter-spacing:-.035em}.srr-hero p{max-width:760px;margin:0;color:#5d6a76}.srr-kpis{display:grid;grid-template-columns:repeat(4,minmax(100px,1fr));gap:8px}.srr-kpis article{min-width:108px;padding:12px;border:1px solid #dbe5ea;border-radius:13px;background:#fff}.srr-kpis strong{display:block;font-size:23px}.srr-kpis span{color:#64717d;font-size:10px;font-weight:700;text-transform:uppercase}.srr-kpis .danger strong{color:#b42318}.srr-kpis .warning strong{color:#b54708}.srr-kpis .success strong{color:#087443}.srr-kpis .info strong{color:#176b87}.srr-card{margin-top:14px;border:1px solid #d8e2e8;border-radius:16px;background:#fff;overflow:hidden;box-shadow:0 10px 28px rgba(20,47,63,.05)}.srr-toolbar,.srr-actions{display:flex;gap:9px;align-items:center;padding:12px 14px;border-bottom:1px solid #e4eaee}.srr-toolbar select,.srr-toolbar input{height:36px;border:1px solid #ccd7de;border-radius:8px;background:#fff;padding:0 10px}.srr-toolbar input{min-width:280px;flex:1}.srr-actions span{margin-left:auto;color:#687580;font-size:12px}.srr-table-wrap{overflow:auto}.srr-table{width:100%;border-collapse:collapse;white-space:nowrap}.srr-table th{position:sticky;top:0;z-index:1;padding:10px;background:#f7f9fa;color:#65727d;font-size:10px;text-align:left;text-transform:uppercase}.srr-table td{padding:10px;border-top:1px solid #edf1f3;vertical-align:middle;font-size:12px}.srr-table tr:hover td{background:#fafcfc}.srr-table tr.is-submitted td{background:#fbfbf8}.srr-table small{display:block;margin-top:3px;color:#7a8792;font-size:10px}.srr-link{padding:0;border:0;background:none;color:#126d8a;font-weight:700;cursor:pointer}.srr-rate{width:120px;height:32px;border:1px solid #bccbd3;border-radius:7px;padding:0 8px;text-align:right}.srr-badge{display:inline-flex;padding:4px 7px;border-radius:999px;font-size:10px;font-weight:800}.srr-badge.danger{background:#feeceb;color:#b42318}.srr-badge.warning{background:#fff2dc;color:#9a5500}.srr-badge.success{background:#e5f7ed;color:#087443}.srr-empty{display:grid;place-items:center;gap:6px;min-height:260px;color:#77838d}.srr-empty strong{color:#33414c;font-size:17px}@media(max-width:900px){.srr-hero{grid-template-columns:1fr}.srr-kpis{grid-template-columns:repeat(2,1fr)}.srr-toolbar,.srr-actions{flex-wrap:wrap}.srr-toolbar input{min-width:100%}}
        `).appendTo("head");
    }
})();
