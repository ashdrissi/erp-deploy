(function () {
    const PAGE_NAME = "technical-list-manager";
    const API = "orderlift.orderlift_sig.page.technical_list_manager.technical_list_manager";
    const state = {
        rows: [],
        kpis: {},
        options: {},
        pagination: { page: 1, page_length: 20, total: 0, page_count: 1 },
        filters: {
            search: "",
            project: "",
            customer: "",
            business_type: "",
            presence: "",
            docstatus: "",
            workflow_state: "",
            annex_readiness: "",
            procurement_readiness: "",
        },
        currentCompany: "",
        technicalListAvailable: true,
        loading: false,
        creating: "",
        error: "",
        initialized: false,
    };
    let searchTimer = null;

    frappe.pages[PAGE_NAME].on_page_load = function (wrapper) {
        const page = frappe.ui.make_app_page({
            parent: wrapper,
            title: __("Technical Lists"),
            single_column: true,
        });
        wrapper.page = page;
        page.main.addClass("tlm-root");
        injectStyles();
        page.set_primary_action(__("Refresh"), () => load(page), "refresh");
        render(page);
        load(page);
    };

    frappe.pages[PAGE_NAME].on_page_show = function (wrapper) {
        if (wrapper.page && state.initialized) load(wrapper.page);
    };

    async function load(page) {
        state.loading = true;
        state.error = "";
        render(page);
        try {
            const response = await frappe.call({
                method: `${API}.get_manager_data`,
                args: {
                    ...state.filters,
                    page: state.pagination.page,
                    page_length: state.pagination.page_length,
                },
            });
            const data = response.message || {};
            state.rows = data.rows || [];
            state.kpis = data.kpis || {};
            state.options = data.filters || {};
            state.pagination = data.pagination || state.pagination;
            state.currentCompany = data.current_company || "";
            state.technicalListAvailable = data.technical_list_available !== false;
            state.initialized = true;
        } catch (error) {
            console.error("Technical List Manager failed", error);
            state.error = error?.message || __("Unable to load Technical Lists. Refresh and try again.");
            state.rows = [];
        } finally {
            state.loading = false;
            render(page);
        }
    }

    function render(page) {
        page.main.html(`
            <main class="tlm-shell">
                <header class="tlm-header">
                    <div>
                        <div class="tlm-eyebrow">${__("SIG / Project Engineering")}</div>
                        <div class="tlm-title-line">
                            <h1>${__("Technical Lists")}</h1>
                            ${state.currentCompany ? `<span class="tlm-company">${esc(state.currentCompany)}</span>` : ""}
                        </div>
                        <p>${__("Submitted Sales Orders and their open working revision, or the current approved revision when no draft is open.")}</p>
                    </div>
                    <div class="tlm-kpis">
                        ${kpi(__("Orders"), state.kpis.sales_orders)}
                        ${kpi(__("Missing Lists"), state.kpis.missing_lists, "warn")}
                        ${kpi(__("Open Revisions"), state.kpis.open_revisions)}
                        ${kpi(__("Procurement Ready"), state.kpis.procurement_ready, "good")}
                    </div>
                </header>
                ${renderFilters()}
                ${!state.technicalListAvailable && !state.loading ? `<div class="tlm-notice">${__("The Technical List model is not installed yet. Submitted Sales Orders remain visible, but creation is unavailable.")}</div>` : ""}
                ${state.error ? `<div class="tlm-error"><span>${esc(state.error)}</span><button class="btn btn-default btn-xs" data-action="retry">${__("Retry")}</button></div>` : ""}
                ${state.loading ? renderLoading() : renderTable()}
                ${!state.loading && !state.error ? renderPagination() : ""}
            </main>
        `);
        bind(page);
    }

    function renderFilters() {
        return `
            <section class="tlm-filters" aria-label="${attr(__("Technical List filters"))}">
                <label class="tlm-search"><span>${__("Search")}</span><input type="search" data-filter="search" value="${attr(state.filters.search)}" placeholder="${attr(__("Order, customer, project, deal"))}" /></label>
                ${selectFilter("project", __("Project"), textOptions(state.options.projects))}
                ${selectFilter("customer", __("Customer"), textOptions(state.options.customers))}
                ${selectFilter("business_type", __("Business Type"), textOptions(state.options.business_types))}
                ${selectFilter("presence", __("Technical List"), [{ value: "present", label: __("Present") }, { value: "missing", label: __("Missing") }])}
                ${selectFilter("docstatus", __("Revision Docstatus"), state.options.docstatuses || [])}
                ${selectFilter("workflow_state", __("Workflow State"), textOptions(state.options.workflow_states))}
                ${selectFilter("annex_readiness", __("Annex Readiness"), state.options.annex_readiness || [])}
                ${selectFilter("procurement_readiness", __("Procurement Readiness"), state.options.procurement_readiness || [])}
                <button type="button" class="btn btn-default tlm-reset" data-action="reset">${__("Reset")}</button>
            </section>`;
    }

    function selectFilter(name, label, options) {
        const selected = state.filters[name] || "";
        return `<label><span>${esc(label)}</span><select data-filter="${attr(name)}"><option value="">${__("All")}</option>${(options || []).map((option) => {
            const value = String(option.value ?? "");
            return `<option value="${attr(value)}" ${value === selected ? "selected" : ""}>${esc(option.label ?? value)}</option>`;
        }).join("")}</select></label>`;
    }

    function renderTable() {
        if (state.error) return "";
        if (!state.rows.length) {
            return `<section class="tlm-empty"><div class="tlm-empty-mark">TL</div><h3>${__("No submitted Sales Orders match")}</h3><p>${__("Adjust the filters or switch the active company.")}</p><button class="btn btn-default" data-action="reset">${__("Clear filters")}</button></section>`;
        }
        return `
            <section class="tlm-table-card">
                <div class="tlm-table-scroll">
                    <table class="tlm-table">
                        <thead><tr>
                            <th>${__("Sales Order")}</th>
                            <th>${__("Customer / Project")}</th>
                            <th>${__("Business")}</th>
                            <th>${__("Order Status")}</th>
                            <th>${__("Technical List")}</th>
                            <th>${__("Working Revision")}</th>
                            <th>${__("Annex")}</th>
                            <th>${__("Procurement")}</th>
                            <th>${__("Updated")}</th>
                            <th class="tlm-actions-heading">${__("Actions")}</th>
                        </tr></thead>
                        <tbody>${state.rows.map(renderRow).join("")}</tbody>
                    </table>
                </div>
            </section>`;
    }

    function renderRow(row) {
        const actions = row.actions || {};
        const transitions = row.available_transitions || [];
        const revisionState = row.workflow_state || docstatusLabel(row.revision_docstatus);
        const revisionTitle = row.revision_no == null ? row.revision : __("Revision {0}", [row.revision_no]);
        return `<tr>
            <td data-label="${attr(__("Sales Order"))}"><button class="tlm-link" data-route="sales_order" data-row="${attr(row.sales_order)}">${esc(row.sales_order)}</button>${row.deal_abbreviation ? `<small>${esc(row.deal_abbreviation)}</small>` : ""}</td>
            <td data-label="${attr(__("Customer / Project"))}"><strong>${esc(row.customer_name || row.customer || "-")}</strong>${row.project ? `<button class="tlm-sub-link" data-route="project" data-row="${attr(row.sales_order)}">${esc(row.project)}</button>` : `<small>${__("No project")}</small>`}</td>
            <td data-label="${attr(__("Business"))}">${row.business_type ? badge(row.business_type, "neutral") : `<span class="tlm-muted">-</span>`}</td>
            <td data-label="${attr(__("Order Status"))}">${badge(row.order_status || __("Submitted"), "neutral")}</td>
            <td data-label="${attr(__("Technical List"))}">${row.technical_list ? `<strong>${esc(row.technical_list)}</strong>` : badge(__("Missing"), "warn")}</td>
            <td data-label="${attr(__("Working Revision"))}">${row.revision ? `<button class="tlm-link" data-route="revision" data-row="${attr(row.sales_order)}">${esc(revisionTitle)}</button><small>${esc([row.revision_kind, revisionState].filter(Boolean).join(" / "))}</small>${transitions.length ? `<small title="${attr(transitions.join(", "))}">${__("Available")}: ${esc(transitions.join(", "))}</small>` : ""}` : `<span class="tlm-muted">${__("No open or current revision")}</span>`}</td>
            <td data-label="${attr(__("Annex"))}">${readinessBadge(row.annex_readiness)}</td>
            <td data-label="${attr(__("Procurement"))}">${readinessBadge(row.procurement_readiness)}</td>
            <td data-label="${attr(__("Updated"))}"><span class="tlm-date">${shortDate(row.modified)}</span></td>
            <td data-label="${attr(__("Actions"))}" class="tlm-actions">
                ${actions.can_create ? `<button class="btn btn-primary btn-xs" data-action="create" data-row="${attr(row.sales_order)}" ${state.creating ? "disabled" : ""}>${state.creating === row.sales_order ? __("Creating...") : __("Create")}</button>` : ""}
                ${actions.can_open_revision ? `<button class="btn btn-default btn-xs" data-route="revision" data-row="${attr(row.sales_order)}">${__("Open Revision")}</button>` : ""}
                ${actions.can_open_sales_order ? `<button class="btn btn-default btn-xs" data-route="sales_order" data-row="${attr(row.sales_order)}">${__("Open Sales Order")}</button>` : ""}
                ${actions.can_open_project ? `<button class="btn btn-default btn-xs" data-route="project" data-row="${attr(row.sales_order)}">${__("Open Project")}</button>` : ""}
            </td>
        </tr>`;
    }

    function renderLoading() {
        return `<section class="tlm-loading" aria-live="polite"><div class="tlm-spinner"></div><span>${__("Loading submitted Sales Orders...")}</span></section>`;
    }

    function renderPagination() {
        const pagination = state.pagination;
        const start = pagination.total ? (pagination.page - 1) * pagination.page_length + 1 : 0;
        const end = Math.min(pagination.page * pagination.page_length, pagination.total);
        return `<footer class="tlm-pagination"><span>${__("Showing {0}-{1} of {2}", [start, end, pagination.total])}</span><div><button class="btn btn-default btn-sm" data-page="${pagination.page - 1}" ${pagination.page <= 1 ? "disabled" : ""}>${__("Previous")}</button><span>${__("Page {0} of {1}", [pagination.page, pagination.page_count])}</span><button class="btn btn-default btn-sm" data-page="${pagination.page + 1}" ${pagination.page >= pagination.page_count ? "disabled" : ""}>${__("Next")}</button></div></footer>`;
    }

    function bind(page) {
        page.main.find('[data-filter="search"]').on("input", function () {
            state.filters.search = String(this.value || "").trim();
            state.pagination.page = 1;
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => load(page), 250);
        });
        page.main.find("select[data-filter]").on("change", function () {
            state.filters[this.dataset.filter] = this.value || "";
            state.pagination.page = 1;
            load(page);
        });
        page.main.find('[data-action="reset"]').on("click", () => {
            Object.keys(state.filters).forEach((key) => { state.filters[key] = ""; });
            state.pagination.page = 1;
            load(page);
        });
        page.main.find('[data-action="retry"]').on("click", () => load(page));
        page.main.find("[data-page]").on("click", function () {
            const target = Number(this.dataset.page || 1);
            if (target < 1 || target > state.pagination.page_count) return;
            state.pagination.page = target;
            load(page);
        });
        page.main.find("[data-route]").on("click", function () {
            const row = state.rows.find((item) => item.sales_order === this.dataset.row);
            const route = row?.routes?.[this.dataset.route];
            if (route?.length) frappe.set_route(...route);
        });
        page.main.find('[data-action="create"]').on("click", function () {
            createTechnicalList(page, this.dataset.row);
        });
    }

    async function createTechnicalList(page, salesOrder) {
        if (!salesOrder || state.creating) return;
        state.creating = salesOrder;
        render(page);
        try {
            const response = await frappe.call({
                method: `${API}.create_for_sales_order`,
                args: { sales_order: salesOrder },
                freeze: true,
                freeze_message: __("Creating Technical List..."),
            });
            const route = response.message?.route || [];
            frappe.show_alert({ message: __("Technical List created for {0}", [salesOrder]), indicator: "green" });
            if (route.length) frappe.set_route(...route);
            else await load(page);
        } catch (error) {
            frappe.msgprint({
                title: __("Technical List not created"),
                message: error?.message || __("The Technical List could not be created."),
                indicator: "red",
            });
        } finally {
            state.creating = "";
            render(page);
        }
    }

    function textOptions(values) {
        return (values || []).map((value) => ({ value, label: value }));
    }

    function kpi(label, value, tone) {
        return `<div class="tlm-kpi ${tone || ""}"><span>${esc(label)}</span><strong>${esc(value ?? 0)}</strong></div>`;
    }

    function badge(label, tone) {
        return `<span class="tlm-badge ${tone || "neutral"}">${esc(label)}</span>`;
    }

    function readinessBadge(readiness) {
        if (!readiness) return `<span class="tlm-muted">-</span>`;
        const tone = readiness.is_ready === true ? "good" : readiness.is_ready === false ? "warn" : "neutral";
        const summary = readiness.summary ? `<small title="${attr(readiness.summary)}">${esc(readiness.summary)}</small>` : "";
        return `${badge(readiness.label || "-", tone)}${summary}`;
    }

    function docstatusLabel(value) {
        if (value === 0) return __("Draft");
        if (value === 1) return __("Submitted");
        if (value === 2) return __("Cancelled");
        return "";
    }

    function shortDate(value) {
        return value ? frappe.datetime.str_to_user(String(value).slice(0, 10)) : "-";
    }

    function esc(value) {
        return frappe.utils.escape_html(String(value ?? ""));
    }

    function attr(value) {
        return esc(value).replace(/"/g, "&quot;");
    }

    function injectStyles() {
        if (document.getElementById("technical-list-manager-styles")) return;
        const style = document.createElement("style");
        style.id = "technical-list-manager-styles";
        style.textContent = `
            .tlm-root{background:#f4f6f5;color:#17201d;min-height:calc(100vh - 56px)}.tlm-root *{box-sizing:border-box}.tlm-shell{max-width:1580px;margin:0 auto;padding:22px 24px 72px}.tlm-header{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;margin-bottom:18px}.tlm-eyebrow{color:#527167;font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase}.tlm-title-line{display:flex;align-items:center;gap:12px}.tlm-header h1{margin:3px 0 4px;font-size:28px;letter-spacing:-.025em}.tlm-header p{margin:0;color:#66736e;font-size:13px}.tlm-company{display:inline-flex;border:1px solid #b9ccc5;border-radius:999px;background:#e9f2ef;color:#31584b;padding:4px 10px;font-size:11px;font-weight:700}.tlm-kpis{display:grid;grid-template-columns:repeat(4,minmax(100px,1fr));gap:7px}.tlm-kpi{min-width:110px;border:1px solid #dce3e0;border-radius:9px;background:#fff;padding:9px 11px}.tlm-kpi span{display:block;color:#74807c;font-size:10px;font-weight:600;text-transform:uppercase}.tlm-kpi strong{display:block;margin-top:2px;font-size:19px}.tlm-kpi.warn strong{color:#a35618}.tlm-kpi.good strong{color:#237453}.tlm-filters{display:grid;grid-template-columns:minmax(220px,1.35fr) repeat(8,minmax(125px,1fr)) auto;align-items:end;gap:7px;border:1px solid #dce3e0;border-radius:11px 11px 0 0;background:#fff;padding:11px}.tlm-filters label{display:grid;gap:4px;margin:0;min-width:0}.tlm-filters label>span{overflow:hidden;color:#66736e;font-size:10px;font-weight:700;text-overflow:ellipsis;white-space:nowrap}.tlm-filters input,.tlm-filters select{width:100%;height:32px;border:1px solid #d5ddda;border-radius:6px;background:#fff;color:#24302c;padding:0 8px;font-size:12px;outline:none}.tlm-filters input:focus,.tlm-filters select:focus{border-color:#3f7e69;box-shadow:0 0 0 2px rgba(63,126,105,.13)}.tlm-reset{height:32px}.tlm-table-card{border:1px solid #dce3e0;border-top:0;background:#fff}.tlm-table-scroll{overflow:auto}.tlm-table{width:100%;min-width:1250px;border-collapse:collapse;font-size:12px}.tlm-table th{position:sticky;top:0;z-index:1;background:#eef2f0;color:#596762;padding:8px 10px;border-bottom:1px solid #d8e0dd;font-size:10px;font-weight:800;letter-spacing:.04em;text-align:left;text-transform:uppercase;white-space:nowrap}.tlm-table td{padding:9px 10px;border-bottom:1px solid #edf0ef;vertical-align:top}.tlm-table tbody tr:hover{background:#fafcfb}.tlm-table tbody tr:last-child td{border-bottom:0}.tlm-table td strong{display:block;font-weight:650}.tlm-table td small{display:block;max-width:210px;margin-top:3px;overflow:hidden;color:#77837f;font-size:10px;text-overflow:ellipsis;white-space:nowrap}.tlm-link,.tlm-sub-link{border:0;background:none;color:#226650;cursor:pointer;padding:0;text-align:left;font-weight:700}.tlm-link:hover,.tlm-sub-link:hover{text-decoration:underline}.tlm-sub-link{display:block;margin-top:3px;font-size:10px;font-weight:600}.tlm-badge{display:inline-flex;max-width:155px;overflow:hidden;border:1px solid #d7dfdc;border-radius:999px;background:#f1f4f3;color:#4c5c56;padding:3px 7px;font-size:10px;font-weight:700;text-overflow:ellipsis;white-space:nowrap}.tlm-badge.good{border-color:#b9ddcf;background:#e8f6f0;color:#176443}.tlm-badge.warn{border-color:#efd1b6;background:#fff2e7;color:#9a4d13}.tlm-muted,.tlm-date{color:#7b8783}.tlm-actions-heading{text-align:right!important}.tlm-actions{display:flex;min-width:150px;gap:4px;justify-content:flex-end;flex-wrap:wrap}.tlm-actions .btn{font-size:10px}.tlm-pagination{display:flex;align-items:center;justify-content:space-between;border:1px solid #dce3e0;border-top:0;border-radius:0 0 11px 11px;background:#fff;color:#66736e;padding:9px 11px;font-size:11px}.tlm-pagination>div{display:flex;align-items:center;gap:10px}.tlm-loading,.tlm-empty{display:grid;place-items:center;min-height:250px;border:1px solid #dce3e0;border-top:0;border-radius:0 0 11px 11px;background:#fff;color:#6d7975;text-align:center}.tlm-loading{align-content:center;gap:10px}.tlm-spinner{width:24px;height:24px;border:2px solid #d4dfdb;border-top-color:#32715c;border-radius:50%;animation:tlm-spin .8s linear infinite}.tlm-empty{align-content:center}.tlm-empty-mark{display:grid;place-items:center;width:44px;height:44px;margin-bottom:8px;border-radius:12px;background:#e9f2ef;color:#31584b;font-weight:800}.tlm-empty h3{margin:0 0 4px;color:#2d3935}.tlm-empty p{margin:0 0 13px}.tlm-notice,.tlm-error{display:flex;align-items:center;justify-content:space-between;gap:10px;border:1px solid #e8cfaa;background:#fff7e9;color:#80501e;padding:10px 12px;font-size:12px}.tlm-error{border-color:#e8bcbc;background:#fff0f0;color:#962e2e}@keyframes tlm-spin{to{transform:rotate(360deg)}}
            @media(max-width:1350px){.tlm-header{align-items:flex-start;flex-direction:column}.tlm-kpis{width:100%}.tlm-filters{grid-template-columns:repeat(5,minmax(135px,1fr))}.tlm-search{grid-column:span 2}}
            @media(max-width:760px){.tlm-shell{padding:14px 10px 60px}.tlm-title-line{align-items:flex-start;flex-direction:column;gap:5px}.tlm-header h1{font-size:23px}.tlm-kpis{grid-template-columns:repeat(2,1fr)}.tlm-kpi{min-width:0}.tlm-filters{grid-template-columns:repeat(2,minmax(0,1fr));border-radius:10px}.tlm-search{grid-column:1/-1}.tlm-table-card{margin-top:9px;border-top:1px solid #dce3e0;border-radius:10px}.tlm-table{display:block;min-width:0}.tlm-table thead{display:none}.tlm-table tbody,.tlm-table tr,.tlm-table td{display:block;width:100%}.tlm-table tr{padding:9px;border-bottom:1px solid #dce3e0}.tlm-table td{display:grid;grid-template-columns:110px minmax(0,1fr);gap:9px;border:0;padding:5px}.tlm-table td::before{content:attr(data-label);color:#7a8682;font-size:9px;font-weight:800;letter-spacing:.04em;text-transform:uppercase}.tlm-actions{justify-content:flex-start}.tlm-pagination{border-top:1px solid #dce3e0;flex-direction:column;gap:9px;margin-top:9px;border-radius:10px}}
        `;
        document.head.appendChild(style);
    }
})();
