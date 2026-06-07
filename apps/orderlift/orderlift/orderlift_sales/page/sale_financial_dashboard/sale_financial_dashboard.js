(function () {
    const METHOD = "orderlift.orderlift_sales.page.sale_financial_dashboard.sale_financial_dashboard.get_dashboard_data";
    const FILTER_KEYS = ["company", "business_type", "crm_segment", "currency", "sales_status", "project_status", "from_date", "to_date", "search"];
    const STATE = {
        filters: readFiltersFromUrl(),
        data: null,
        loading: false,
        error: null,
    };

    const SFD_ICONS = {
        money: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="14" height="10" rx="2"/><circle cx="10" cy="10" r="2"/><path d="M6 8v4M14 8v4"/></svg>`,
        project: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h12v12H4z"/><path d="M7 8h6M7 11h4"/></svg>`,
        chart: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 16V4"/><path d="M4 16h12"/><path d="M7 13V9M10 13V6M13 13v-3"/></svg>`,
        filter: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 4h14l-5 6v4l-4 2v-6L3 4z"/></svg>`,
        refresh: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M16 7a6 6 0 1 0 1 4"/><path d="M16 3v4h-4"/></svg>`,
        arrow: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 10h12"/><path d="M11 5l5 5-5 5"/></svg>`,
        search: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="9" r="6"/><path d="M14 14l3 3"/></svg>`,
    };

    frappe.pages["sale-financial-dashboard"].on_page_load = function (wrapper) {
        const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Sale Financial Dashboard"), single_column: true });
        wrapper.page = page;
        page.main.addClass("sfd-root");
        injectSaleFinancialStyles();
        render(page);
        loadDashboard(page);
    };

    frappe.pages["sale-financial-dashboard"].on_page_show = function (wrapper) {
        if (!wrapper.page) return;
        wrapper.page.set_title(__("Sale Financial Dashboard"));
        if (!STATE.data && !STATE.loading) loadDashboard(wrapper.page);
    };

    async function loadDashboard(page) {
        STATE.loading = true;
        STATE.error = null;
        render(page);
        try {
            const res = await frappe.call({ method: METHOD, args: { filters: STATE.filters } });
            STATE.data = res.message || {};
            STATE.filters = { ...defaultFilters(), ...(STATE.data.active_filters || STATE.filters) };
            updateUrlFilters();
        } catch (error) {
            STATE.error = error;
            console.warn("Sale Financial Dashboard failed", error);
        } finally {
            STATE.loading = false;
            render(page);
        }
    }

    function render(page) {
        const data = STATE.data || {};
        const filters = STATE.filters || defaultFilters();
        const totals = data.currency_totals || [];
        page.set_title(__("Sale Financial Dashboard"));
        page.main.html(`
            <div class="sfd-wrapper">
                <nav class="sfd-breadcrumb" aria-label="${__("Breadcrumb")}">
                    <a href="/desk/home-page?sidebar=Main+Dashboard">${__("Main Dashboard")}</a>
                    <span>/</span>
                    <a href="/desk/home-page?sidebar=Main+Dashboard">${__("Finance")}</a>
                    <span>/</span>
                    <strong>${__("Sale Financial Dashboard")}</strong>
                </nav>

                <section class="sfd-hero">
                    <div class="sfd-hero-copy">
                        <div class="sfd-eyebrow">${__("Orderlift · Business Finance")}</div>
                        <h1>${__("Sale Financial Dashboard")}</h1>
                        <p>${__("Revenue, charges, margins, projects, and operating context filtered by company, business type, segment, status, date, and currency.")}</p>
                        <div class="sfd-active-filters">${activeFilterChips(filters)}</div>
                    </div>
                    <div class="sfd-hero-panel">
                        <span>${__("Gross Margin")}</span>
                        <strong>${moneyList(totals, "margin")}</strong>
                        <small>${marginPctLabel(totals)}</small>
                    </div>
                </section>

                ${filterPanel(data, filters)}
                ${STATE.error ? errorBanner(STATE.error) : ""}
                ${STATE.loading ? skeletonMarkup() : dashboardMarkup(data)}
            </div>
        `);
        bind(page);
    }

    function filterPanel(data, filters) {
        const options = data.filter_options || {};
        return `
            <section class="sfd-filter-card" aria-label="${__("Dashboard filters")}">
                <div class="sfd-filter-head">
                    <div><span class="sfd-filter-icon">${SFD_ICONS.filter}</span><strong>${__("Filters")}</strong><small>${activeFilterCount(filters)} ${__("active")}</small></div>
                    <div class="sfd-filter-actions">
                        <button type="button" class="sfd-btn ghost" data-period="month">${__("This Month")}</button>
                        <button type="button" class="sfd-btn ghost" data-period="quarter">${__("Quarter")}</button>
                        <button type="button" class="sfd-btn ghost" data-period="year">${__("Year")}</button>
                    </div>
                </div>
                <div class="sfd-filter-grid">
                    ${selectField("company", __("Company"), companyOptions(options.companies || data.companies || []), filters.company, __("All companies"))}
                    ${selectField("business_type", __("Business Type"), options.business_types || [], filters.business_type, __("All types"))}
                    ${selectField("crm_segment", __("CRM Segment"), options.segments || [], filters.crm_segment, __("All segments"))}
                    ${selectField("currency", __("Currency"), options.currencies || [], filters.currency, __("All currencies"))}
                    ${selectField("sales_status", __("Sales Order Status"), options.sales_order_statuses || [], filters.sales_status, __("All sales statuses"))}
                    ${selectField("project_status", __("Project Status"), options.project_statuses || [], filters.project_status, __("All project statuses"))}
                    ${inputField("from_date", __("From"), "date", filters.from_date)}
                    ${inputField("to_date", __("To"), "date", filters.to_date)}
                    <label class="sfd-field sfd-field-search"><span>${__("Search")}</span><div>${SFD_ICONS.search}<input data-filter-field="search" type="search" value="${escapeHtml(filters.search)}" placeholder="${__("Customer, supplier, project, order")}" /></div></label>
                </div>
                <div class="sfd-filter-footer">
                    <button type="button" class="sfd-btn secondary" data-clear-filters>${__("Clear")}</button>
                    <button type="button" class="sfd-btn primary" data-apply-filters>${__("Apply Filters")}</button>
                    <button type="button" class="sfd-btn icon" data-refresh aria-label="${__("Refresh dashboard")}">${SFD_ICONS.refresh}<span>${__("Refresh")}</span></button>
                </div>
            </section>
        `;
    }

    function dashboardMarkup(data) {
        const kpis = data.kpis || {};
        const totals = data.currency_totals || [];
        return `
            <section class="sfd-kpis">
                ${kpiCard("money", __("Revenue"), moneyList(totals, "revenue"), __("submitted Sales Orders"))}
                ${kpiCard("money", __("Charges"), moneyList(totals, "charges"), __("submitted Purchase Orders"))}
                ${kpiCard("chart", __("Gross Margin"), moneyList(totals, "margin"), marginPctLabel(totals))}
                ${kpiCard("project", __("Sales Orders"), kpis.sales_orders || 0, __("submitted"))}
                ${kpiCard("project", __("Projects"), kpis.projects || 0, `${kpis.blocked_projects || 0} ${__("blocked")}`)}
                ${kpiCard("project", __("Purchase Orders"), kpis.purchase_orders || 0, __("charges"))}
            </section>

            <section class="sfd-grid sfd-grid-main">
                <article class="sfd-card sfd-card-strong">
                    <header><div><strong>${__("Currency Performance")}</strong><small>${__("Revenue, charges, and margin by transaction currency")}</small></div></header>
                    <div class="sfd-card-body">${currencyTotalsMarkup(totals)}</div>
                </article>
                <article class="sfd-card">
                    <header><div><strong>${__("Business Type Mix")}</strong><small>${__("Distribution, installation, maintenance, and unassigned work")}</small></div></header>
                    <div class="sfd-card-body">${summaryRows(data.by_business_type || [])}</div>
                </article>
            </section>

            <section class="sfd-grid sfd-grid-main reverse">
                <article class="sfd-card">
                    <header><div><strong>${__("Company Scoreboard")}</strong><small>${__("Company-level operating view")}</small></div></header>
                    <div class="sfd-card-body">${companyRows(data.by_company || [])}</div>
                </article>
                <article class="sfd-card">
                    <header><div><strong>${__("CRM Segment Mix")}</strong><small>${__("Revenue and workload by active customer segment")}</small></div></header>
                    <div class="sfd-card-body">${summaryRows(data.by_segment || [])}</div>
                </article>
            </section>

            <section class="sfd-grid">
                <article class="sfd-card"><header><div><strong>${__("Sales Order Status")}</strong><small>${__("Submitted order workflow")}</small></div></header><div class="sfd-card-body">${statusBars(data.sales_order_statuses || [])}</div></article>
                <article class="sfd-card"><header><div><strong>${__("Project Status")}</strong><small>${__("Execution and installation follow-up")}</small></div></header><div class="sfd-card-body">${statusBars(data.project_statuses || [])}</div></article>
            </section>

            <section class="sfd-grid sfd-grid-recent">
                <article class="sfd-card"><header><div><strong>${__("Recent Sales Orders")}</strong><small>${__("Latest matching submitted orders")}</small></div><a href="/app/sales-order">${__("Open")} ${SFD_ICONS.arrow}</a></header><div class="sfd-card-body">${recentList(data.recent_sales_orders || [])}</div></article>
                <article class="sfd-card"><header><div><strong>${__("Recent Projects")}</strong><small>${__("Latest matching execution records")}</small></div><a href="/app/project">${__("Open")} ${SFD_ICONS.arrow}</a></header><div class="sfd-card-body">${recentList(data.recent_projects || [])}</div></article>
                <article class="sfd-card"><header><div><strong>${__("Recent Charges")}</strong><small>${__("Latest matching purchase charges")}</small></div><a href="/app/purchase-order">${__("Open")} ${SFD_ICONS.arrow}</a></header><div class="sfd-card-body">${recentList(data.recent_charges || [])}</div></article>
            </section>
        `;
    }

    function kpiCard(icon, label, value, sub) {
        return `<article class="sfd-kpi"><span>${SFD_ICONS[icon] || ""}</span><strong>${escapeHtml(value)}</strong><em>${escapeHtml(label)}</em><small>${escapeHtml(sub)}</small></article>`;
    }

    function currencyTotalsMarkup(rows) {
        if (!rows.length) return emptyState(__("No submitted financial documents match these filters."));
        const max = Math.max(...rows.flatMap((row) => [Math.abs(row.revenue || 0), Math.abs(row.charges || 0), Math.abs(row.margin || 0)]), 1);
        return `<div class="sfd-money-stack">${rows.map((row) => `
            <section class="sfd-money-card">
                <div class="sfd-money-head"><strong>${escapeHtml(row.currency || __("Currency"))}</strong><span class="${Number(row.margin || 0) < 0 ? "negative" : "positive"}">${formatNumber(row.margin_pct || 0)}%</span></div>
                ${moneyBar(__("Revenue"), row.revenue, max, "revenue")}
                ${moneyBar(__("Charges"), row.charges, max, "charges")}
                ${moneyBar(__("Margin"), row.margin, max, Number(row.margin || 0) < 0 ? "negative" : "margin")}
            </section>
        `).join("")}</div>`;
    }

    function moneyBar(label, value, max, tone) {
        const width = Math.max(3, Math.min(100, (Math.abs(Number(value || 0)) / max) * 100));
        return `<div class="sfd-money-bar-row"><div><span>${escapeHtml(label)}</span><strong>${formatNumber(value || 0)}</strong></div><div class="sfd-bar-track"><i class="${tone}" style="width:${width}%"></i></div></div>`;
    }

    function summaryRows(rows) {
        if (!rows.length) return emptyState(__("No matching summary data."));
        return `<div class="sfd-summary-stack">${rows.map((row) => {
            const primary = primaryAmount(row.amounts || []);
            return `<section class="sfd-summary-row">
                <div class="sfd-summary-main"><strong>${escapeHtml(row.label || __("Unassigned"))}</strong><small>${row.projects || 0} ${__("projects")} · ${row.sales_orders || 0} ${__("sales orders")} · ${row.purchase_orders || 0} ${__("charges")}</small></div>
                <div class="sfd-summary-money"><strong>${escapeHtml(primary.margin)}</strong><small>${escapeHtml(primary.revenue)} ${__("revenue")}</small></div>
            </section>`;
        }).join("")}</div>`;
    }

    function companyRows(rows) {
        if (!rows.length) return emptyState(__("No company data matches these filters."));
        return `<div class="sfd-company-table">${rows.map((row) => {
            const primary = primaryAmount(row.amounts || []);
            return `<section class="sfd-company-row">
                <div><strong>${escapeHtml(row.label || "")}</strong><small>${escapeHtml(row.currency || "")}</small></div>
                <span>${row.sales_orders || 0}<small>${__("SO")}</small></span>
                <span>${row.projects || 0}<small>${__("Projects")}</small></span>
                <span>${row.purchase_orders || 0}<small>${__("PO")}</small></span>
                <div class="sfd-company-money"><strong>${escapeHtml(primary.margin)}</strong><small>${escapeHtml(primary.revenue)} ${__("revenue")}</small></div>
            </section>`;
        }).join("")}</div>`;
    }

    function statusBars(rows) {
        if (!rows.length) return emptyState(__("No status data."));
        const max = Math.max(...rows.map((row) => Number(row.value || 0)), 1);
        return `<div class="sfd-status-stack">${rows.map((row) => `<div class="sfd-status-row"><div><span>${escapeHtml(row.label || "")}</span><strong>${row.value || 0}</strong></div><div class="sfd-status-track"><i style="width:${Math.max(5, ((row.value || 0) / max) * 100)}%"></i></div></div>`).join("")}</div>`;
    }

    function recentList(rows) {
        if (!rows.length) return emptyState(__("No recent records match these filters."));
        return `<div class="sfd-recent-list">${rows.map((row) => `<a class="sfd-recent-row" href="${escapeHtml(row.link || "#")}"><strong>${escapeHtml(row.label || "")}</strong><span>${escapeHtml(row.meta || "")}${row.currency ? ` · ${escapeHtml(row.currency)} ${formatNumber(row.amount || 0)}` : ""}</span></a>`).join("")}</div>`;
    }

    function bind(page) {
        page.main.find("[data-refresh]").on("click", () => loadDashboard(page));
        page.main.find("[data-apply-filters]").on("click", () => applyFilters(page));
        page.main.find("[data-clear-filters]").on("click", () => {
            STATE.filters = defaultFilters();
            loadDashboard(page);
        });
        page.main.find("[data-period]").on("click", function () {
            STATE.filters = { ...collectFilters(page), ...periodRange($(this).data("period")) };
            loadDashboard(page);
        });
        page.main.find('[data-filter-field="search"]').on("keydown", function (event) {
            if (event.key === "Enter") applyFilters(page);
        });
    }

    function applyFilters(page) {
        STATE.filters = collectFilters(page);
        loadDashboard(page);
    }

    function collectFilters(page) {
        const filters = defaultFilters();
        page.main.find("[data-filter-field]").each(function () {
            filters[$(this).data("filter-field")] = String($(this).val() || "").trim();
        });
        return filters;
    }

    function selectField(key, label, options, value, allLabel) {
        const cleanOptions = withSelected(options, value);
        return `<label class="sfd-field"><span>${escapeHtml(label)}</span><select data-filter-field="${key}"><option value="">${escapeHtml(allLabel)}</option>${cleanOptions.map((option) => `<option value="${escapeHtml(option)}" ${option === value ? "selected" : ""}>${escapeHtml(option)}</option>`).join("")}</select></label>`;
    }

    function inputField(key, label, type, value) {
        return `<label class="sfd-field"><span>${escapeHtml(label)}</span><input data-filter-field="${key}" type="${type}" value="${escapeHtml(value || "")}" /></label>`;
    }

    function companyOptions(companies) {
        return (companies || []).map((company) => company.name).filter(Boolean);
    }

    function withSelected(options, selected) {
        const clean = [...new Set((options || []).filter(Boolean).map(String))];
        if (selected && !clean.includes(selected)) clean.unshift(selected);
        return clean;
    }

    function activeFilterChips(filters) {
        const labels = {
            company: __("Company"),
            business_type: __("Type"),
            crm_segment: __("Segment"),
            currency: __("Currency"),
            sales_status: __("SO Status"),
            project_status: __("Project Status"),
            from_date: __("From"),
            to_date: __("To"),
            search: __("Search"),
        };
        const chips = FILTER_KEYS.filter((key) => filters[key]).map((key) => `<span>${escapeHtml(labels[key])}: <strong>${escapeHtml(filters[key])}</strong></span>`);
        return chips.join("") || `<span>${__("All reporting companies and business contexts")}</span>`;
    }

    function activeFilterCount(filters) {
        return FILTER_KEYS.filter((key) => filters[key]).length;
    }

    function periodRange(period) {
        if (period === "year") {
            const now = new Date();
            return { from_date: `${now.getFullYear()}-01-01`, to_date: isoDate(now) };
        }
        if (period === "quarter") {
            const now = new Date();
            const quarterStartMonth = Math.floor(now.getMonth() / 3) * 3;
            return { from_date: isoDate(new Date(now.getFullYear(), quarterStartMonth, 1)), to_date: isoDate(now) };
        }
        if (period === "month") {
            const now = new Date();
            return { from_date: isoDate(new Date(now.getFullYear(), now.getMonth(), 1)), to_date: isoDate(now) };
        }
        return { from_date: "", to_date: "" };
    }

    function defaultFilters() {
        return { company: "", business_type: "", crm_segment: "", currency: "", sales_status: "", project_status: "", from_date: "", to_date: "", search: "" };
    }

    function readFiltersFromUrl() {
        const filters = defaultFilters();
        const params = new URLSearchParams(window.location.search || "");
        FILTER_KEYS.forEach((key) => {
            filters[key] = String(params.get(key) || "").trim();
        });
        return filters;
    }

    function updateUrlFilters() {
        const params = new URLSearchParams(window.location.search || "");
        FILTER_KEYS.forEach((key) => {
            if (STATE.filters[key]) params.set(key, STATE.filters[key]);
            else params.delete(key);
        });
        const query = params.toString();
        window.history.replaceState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
    }

    function primaryAmount(amounts) {
        const row = [...(amounts || [])].sort((a, b) => Math.abs((b.revenue || 0) + (b.charges || 0)) - Math.abs((a.revenue || 0) + (a.charges || 0)))[0];
        if (!row) return { revenue: "0", margin: "0" };
        return { revenue: `${row.currency || ""} ${formatNumber(row.revenue || 0)}`.trim(), margin: `${row.currency || ""} ${formatNumber(row.margin || 0)}`.trim() };
    }

    function moneyList(rows, key) {
        return (rows || []).map((row) => `${row.currency || ""} ${formatNumber(row[key] || 0)}`.trim()).join(" · ") || "0";
    }

    function marginPctLabel(rows) {
        if (!rows || !rows.length) return __("no margin yet");
        if (rows.length === 1) return `${formatNumber(rows[0].margin_pct || 0)}% ${__("margin")}`;
        return __("multi-currency margin") + ` · ${rows.length}`;
    }

    function errorBanner(error) {
        return `<div class="sfd-error"><strong>${__("Dashboard could not load")}</strong><span>${escapeHtml(error.message || __("Check permissions or try again."))}</span></div>`;
    }

    function skeletonMarkup() {
        return `<section class="sfd-kpis">${Array.from({ length: 6 }, () => `<div class="sfd-kpi sfd-shimmer"></div>`).join("")}</section><section class="sfd-grid sfd-grid-main"><article class="sfd-card sfd-shimmer big"></article><article class="sfd-card sfd-shimmer big"></article></section>`;
    }

    function emptyState(message) {
        return `<div class="sfd-empty">${escapeHtml(message || "")}</div>`;
    }

    function formatNumber(value) {
        return frappe.format(Number(value || 0), { fieldtype: "Float", precision: 0 }, { only_value: true });
    }

    function isoDate(date) {
        return date.toISOString().slice(0, 10);
    }

    function escapeHtml(value) {
        return frappe.utils.escape_html(String(value ?? ""));
    }

    function injectSaleFinancialStyles() {
        if (document.getElementById("sfd-styles")) return;
        const style = document.createElement("style");
        style.id = "sfd-styles";
        style.textContent = `
            .sfd-root{background:linear-gradient(180deg,#f8fafc 0%,#eef2ff 100%);min-height:calc(100vh - 88px);color:#0f172a}.sfd-wrapper{max-width:1440px;margin:0 auto;padding:20px 24px 32px}.sfd-breadcrumb{display:flex;align-items:center;gap:8px;margin:0 0 14px;color:#64748b;font-size:12px}.sfd-breadcrumb a{color:#475569;text-decoration:none}.sfd-breadcrumb strong{color:#0f172a}.sfd-hero,.sfd-filter-card,.sfd-card,.sfd-kpi{background:rgba(255,255,255,.92);border:1px solid rgba(148,163,184,.18);box-shadow:0 18px 52px rgba(15,23,42,.08);backdrop-filter:blur(12px)}
            .sfd-hero{border-radius:28px;padding:26px;display:grid;grid-template-columns:minmax(0,1fr) minmax(260px,360px);gap:22px;align-items:stretch;margin-bottom:16px;background:radial-gradient(circle at top left,rgba(99,102,241,.18),transparent 34%),rgba(255,255,255,.92)}.sfd-eyebrow{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#4f46e5;font-weight:800}.sfd-hero h1{margin:5px 0 8px;font-size:34px;line-height:1.08;letter-spacing:-.03em;color:#0f172a}.sfd-hero p{max-width:820px;margin:0;color:#475569;line-height:1.6}.sfd-active-filters{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}.sfd-active-filters span{border:1px solid rgba(99,102,241,.16);background:#eef2ff;color:#4338ca;border-radius:999px;padding:7px 10px;font-size:12px}.sfd-hero-panel{border-radius:22px;background:linear-gradient(135deg,#312e81,#4338ca);color:#fff;padding:20px;display:flex;flex-direction:column;justify-content:center}.sfd-hero-panel span{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#c7d2fe}.sfd-hero-panel strong{margin-top:8px;font-size:27px;line-height:1.18}.sfd-hero-panel small{margin-top:8px;color:#ddd6fe}
            .sfd-filter-card{border-radius:24px;padding:18px;margin-bottom:16px}.sfd-filter-head,.sfd-filter-footer{display:flex;align-items:center;justify-content:space-between;gap:14px}.sfd-filter-head>div:first-child{display:flex;align-items:center;gap:9px}.sfd-filter-head strong{font-size:16px}.sfd-filter-head small{color:#64748b}.sfd-filter-icon svg{width:18px;height:18px;color:#4f46e5}.sfd-filter-actions,.sfd-filter-footer{display:flex;flex-wrap:wrap;gap:8px}.sfd-filter-grid{display:grid;grid-template-columns:repeat(6,minmax(140px,1fr));gap:12px;margin-top:14px}.sfd-field{display:flex;flex-direction:column;gap:6px;min-width:0}.sfd-field span{font-size:12px;font-weight:800;color:#475569}.sfd-field select,.sfd-field input{width:100%;min-height:42px;border:1px solid rgba(148,163,184,.35);border-radius:13px;background:#fff;color:#0f172a;padding:0 11px;outline:none}.sfd-field select:focus,.sfd-field input:focus{border-color:#4f46e5;box-shadow:0 0 0 3px rgba(79,70,229,.14)}.sfd-field-search{grid-column:span 2}.sfd-field-search div{position:relative}.sfd-field-search svg{position:absolute;left:11px;top:11px;width:18px;height:18px;color:#64748b}.sfd-field-search input{padding-left:38px}.sfd-filter-footer{margin-top:14px;justify-content:flex-end}.sfd-btn{min-height:42px;border-radius:13px;border:1px solid rgba(148,163,184,.28);padding:0 14px;background:#fff;color:#334155;font-weight:800;display:inline-flex;align-items:center;gap:8px;cursor:pointer}.sfd-btn:hover{box-shadow:0 10px 24px rgba(15,23,42,.08)}.sfd-btn.primary{background:#4f46e5;border-color:#4f46e5;color:#fff}.sfd-btn.secondary{background:#f8fafc}.sfd-btn.ghost{min-height:34px;background:#eef2ff;color:#4338ca}.sfd-btn.icon svg{width:17px;height:17px}
            .sfd-kpis{display:grid;grid-template-columns:repeat(6,minmax(150px,1fr));gap:14px;margin-bottom:16px}.sfd-kpi{border-radius:20px;padding:16px;min-height:136px}.sfd-kpi>span svg{width:21px;height:21px;color:#4f46e5}.sfd-kpi strong{display:block;margin-top:12px;font-size:24px;line-height:1.12;color:#0f172a;word-break:break-word}.sfd-kpi em{display:block;margin-top:7px;font-style:normal;font-weight:800;color:#1e293b}.sfd-kpi small{display:block;margin-top:5px;color:#64748b}.sfd-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-bottom:16px}.sfd-grid-main{grid-template-columns:minmax(0,1.08fr) minmax(0,.92fr)}.sfd-grid-main.reverse{grid-template-columns:minmax(0,.92fr) minmax(0,1.08fr)}.sfd-grid-recent{grid-template-columns:repeat(3,minmax(0,1fr))}.sfd-card{border-radius:24px;overflow:hidden;min-height:170px}.sfd-card.big{min-height:320px}.sfd-card header{padding:18px 20px 10px;display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.sfd-card header strong{display:block;font-size:16px;color:#0f172a}.sfd-card header small{display:block;margin-top:3px;color:#64748b}.sfd-card header a{display:inline-flex;align-items:center;gap:6px;color:#4f46e5;text-decoration:none;font-weight:800}.sfd-card header svg{width:15px;height:15px}.sfd-card-body{padding:0 16px 16px}.sfd-card-strong{background:linear-gradient(180deg,#fff,#f8fafc)}
            .sfd-money-stack,.sfd-summary-stack,.sfd-status-stack,.sfd-recent-list,.sfd-company-table{display:flex;flex-direction:column;gap:10px}.sfd-money-card,.sfd-summary-row,.sfd-company-row,.sfd-recent-row{border:1px solid rgba(148,163,184,.18);background:#f8fafc;border-radius:16px}.sfd-money-card{padding:14px}.sfd-money-head,.sfd-summary-row,.sfd-company-row,.sfd-status-row>div:first-child{display:flex;align-items:center;justify-content:space-between;gap:12px}.sfd-money-head strong{font-size:18px}.sfd-money-head span{font-weight:900;border-radius:999px;padding:5px 9px;background:#ecfdf5;color:#15803d}.sfd-money-head span.negative{background:#fef2f2;color:#b91c1c}.sfd-money-bar-row{margin-top:12px}.sfd-money-bar-row>div:first-child{display:flex;justify-content:space-between;gap:12px;margin-bottom:6px}.sfd-money-bar-row span,.sfd-status-row span{color:#64748b}.sfd-money-bar-row strong,.sfd-status-row strong{font-variant-numeric:tabular-nums}.sfd-bar-track,.sfd-status-track{height:8px;border-radius:999px;background:#e2e8f0;overflow:hidden}.sfd-bar-track i,.sfd-status-track i{display:block;height:100%;border-radius:999px;background:#4f46e5}.sfd-bar-track i.charges{background:#f59e0b}.sfd-bar-track i.margin{background:#16a34a}.sfd-bar-track i.negative{background:#dc2626}.sfd-summary-row{padding:13px 14px}.sfd-summary-main strong{display:block}.sfd-summary-main small,.sfd-summary-money small,.sfd-company-row small{display:block;margin-top:3px;color:#64748b;font-size:12px}.sfd-summary-money{text-align:right}.sfd-summary-money strong,.sfd-company-money strong{font-variant-numeric:tabular-nums}.sfd-company-row{display:grid;grid-template-columns:minmax(180px,1fr) 68px 82px 68px minmax(130px,.7fr);align-items:center;padding:12px 14px;gap:10px}.sfd-company-row>span{font-weight:900;text-align:center}.sfd-company-money{text-align:right}.sfd-status-row{padding:9px 0;border-bottom:1px solid rgba(226,232,240,.9)}.sfd-recent-row{display:block;text-decoration:none;padding:13px 14px}.sfd-recent-row strong{display:block;color:#111827}.sfd-recent-row span{display:block;margin-top:5px;color:#64748b;font-size:12px;line-height:1.45}.sfd-recent-row:hover{border-color:rgba(79,70,229,.34);background:#eef2ff}.sfd-empty{border:1px dashed rgba(148,163,184,.35);border-radius:16px;padding:24px;text-align:center;color:#64748b;background:#f8fafc}.sfd-error{display:flex;gap:10px;align-items:center;border-radius:16px;border:1px solid #fecaca;background:#fef2f2;color:#991b1b;padding:12px 14px;margin-bottom:16px}.sfd-error span{color:#b91c1c}.sfd-shimmer{position:relative;overflow:hidden;min-height:128px}.sfd-shimmer:after{content:"";position:absolute;inset:0;transform:translateX(-100%);background:linear-gradient(90deg,transparent,rgba(255,255,255,.78),transparent);animation:sfdShimmer 1.4s infinite}@keyframes sfdShimmer{100%{transform:translateX(100%)}}
            @media(max-width:1200px){.sfd-filter-grid{grid-template-columns:repeat(3,minmax(150px,1fr))}.sfd-kpis{grid-template-columns:repeat(3,minmax(170px,1fr))}.sfd-grid,.sfd-grid-main,.sfd-grid-main.reverse,.sfd-grid-recent{grid-template-columns:1fr}.sfd-hero{grid-template-columns:1fr}.sfd-company-row{grid-template-columns:minmax(180px,1fr) repeat(3,70px) minmax(130px,.7fr)}}
            @media(max-width:760px){.sfd-wrapper{padding:16px 12px 28px}.sfd-hero{padding:20px;border-radius:22px}.sfd-hero h1{font-size:28px}.sfd-filter-head,.sfd-filter-footer{align-items:stretch;flex-direction:column}.sfd-filter-actions,.sfd-filter-footer{width:100%}.sfd-btn{justify-content:center;flex:1}.sfd-filter-grid{grid-template-columns:1fr}.sfd-field-search{grid-column:auto}.sfd-kpis{grid-template-columns:1fr}.sfd-summary-row{align-items:flex-start;flex-direction:column}.sfd-summary-money{text-align:left}.sfd-company-row{grid-template-columns:1fr 1fr 1fr;align-items:start}.sfd-company-row>div:first-child,.sfd-company-money{grid-column:1/-1;text-align:left}.sfd-error{align-items:flex-start;flex-direction:column}}
            @media(prefers-reduced-motion:reduce){.sfd-shimmer:after{animation:none}.sfd-btn:hover,.sfd-recent-row:hover{box-shadow:none}}
        `;
        document.head.appendChild(style);
    }
})();
