(function () {
    const METHOD = "orderlift.orderlift_finance.cash_flow.get_portfolio_data";
    const STYLE_ID = "orderlift-financial-workspace-style";
    const STYLE_URL = "/assets/orderlift/css/financial_workspace_20260815c.css";
    const TABS = [
        ["overview", "Overview", ""],
        ["profitability", "Profitability", "profitability_rows"],
        ["cashflow", "Cash Flow", "cash_flow_rows"],
        ["projects", "Projects", "project_rows"],
        ["standalone", "Standalone Orders", "standalone_order_rows"],
        ["customers", "Customers", "customer_rows"],
        ["monthly", "Monthly", "monthly_rows"],
        ["quality", "Data Quality", "data_quality_rows"],
    ];
    const FILTER_KEYS = ["search", "status", "customer", "project_type", "business_type", "segment", "risk_status", "revenue_forecast_status", "cost_forecast_status", "currency", "horizon", "from_date", "to_date"];
    const SOURCE_DOCTYPES = new Set(["Customer", "Project", "Sales Order", "Sales Invoice", "Purchase Invoice", "Purchase Order", "Payment Entry"]);
    const STATE = {
        activeTab: readQuery("tab") || "overview",
        filters: readFilters(),
        data: null,
        loading: false,
        error: null,
        filtersOpen: false,
        sort: { key: "risk", direction: "desc" },
        requestGeneration: 0,
    };

    const TABLES = {
        profitability: {
            title: "Project & Order Profitability",
            description: "Expected and actual-to-date profit kept separate from cash movement.",
            empty: "No profitability contexts match the current filters.",
            dynamicContext: true,
            columns: [
                column("name", "Project / Order", ["title", "context_name", "name"], "primary"),
                column("customer", "Customer", ["customer"]),
                column("expected_revenue", "Expected Revenue HT", ["expected_revenue_ht"], "money"),
                column("expected_cost", "Expected Cost", ["expected_cost"], "profit_money"),
                column("expected_profit", "Expected Profit", ["expected_profit"], "profit_money"),
                column("expected_margin", "Profit %", ["expected_profit_pct"], "profit_percent"),
                column("actual_profit", "Actual Profit to Date", ["actual_profit_to_date"], "money"),
                column("net_cash", "Net Cash Flow", ["net_cash"], "money"),
                column("funding_gap", "Funding Gap", ["funding_gap"], "money"),
                column("closure", "Forecast Status", [], "closure"),
            ],
        },
        cashflow: {
            title: "Cash Flow by Project & Order",
            description: "Actual cash, forward commitments, and funding requirements for each financial context.",
            empty: "No cash-flow contexts match the current filters.",
            dynamicContext: true,
            columns: [
                column("name", "Project / Order", ["title", "context_name", "name"], "primary"),
                column("customer", "Customer", ["customer"]),
                column("collected", "Collected", ["collected"], "money"),
                column("paid", "Supplier Paid", ["supplier_paid"], "money"),
                column("net_cash", "Net Cash Flow", ["net_cash"], "money"),
                column("expected_inflow", "Expected Inflow", ["committed_inflow"], "money"),
                column("expected_outflow", "Expected Outflow", ["committed_outflow"], "money"),
                column("forecast_outflow", "Forecast Outflow", ["forecast_outflow"], "money"),
                column("funding_gap", "Funding Gap", ["funding_gap"], "money"),
                column("next_event", "Next Cash Event", ["next_cash_event"], "event"),
            ],
        },
        projects: {
            title: "Project Portfolio",
            description: "Project cash position, exposure, and expected funding movement.",
            empty: "No projects match the current filters.",
            contextType: "project",
            columns: [
                column("name", "Project", ["project_name", "title", "name", "context_name"], "primary"),
                column("customer", "Customer", ["customer_name", "customer"]),
                column("status", "Status", ["workflow_status", "status", "project_status"], "status"),
                column("project_type", "Project Type", ["project_type"]),
                column("business_type", "Business Type", ["business_type"]),
                column("collected", "Collected", ["collected", "collected_amount"], "money"),
                column("paid", "Paid", ["supplier_paid", "paid", "paid_amount"], "money"),
                column("expected_profit", "Expected Profit", ["expected_profit"], "money"),
                column("funding_gap", "Funding Gap", ["funding_gap", "gap"], "money"),
                column("risk", "Risk", ["risk_status", "risk", "risk_level"], "status"),
            ],
        },
        standalone: {
            title: "Standalone Orders",
            description: "Sales orders whose financial context is not grouped under a project.",
            empty: "No standalone orders match the current filters.",
            contextType: "sales_order",
            columns: [
                column("name", "Sales Order", ["sales_order", "order_name", "name", "context_name"], "primary"),
                column("customer", "Customer", ["customer_name", "customer"]),
                column("status", "Status", ["workflow_status", "status", "order_status"], "status"),
                column("business_type", "Business Type", ["business_type"]),
                column("collected", "Collected", ["collected", "collected_amount"], "money"),
                column("paid", "Paid", ["supplier_paid", "paid", "paid_amount"], "money"),
                column("expected_inflow", "Expected Inflow", ["committed_inflow", "expected_inflow_13w", "expected_inflow"], "money"),
                column("expected_profit", "Expected Profit", ["expected_profit"], "money"),
                column("funding_gap", "Funding Gap", ["funding_gap", "gap"], "money"),
                column("risk", "Risk", ["risk_status", "risk", "risk_level"], "status"),
            ],
        },
        customers: {
            title: "Customer Exposure",
            description: "Receivables, collection, and concentration by customer.",
            empty: "No customer exposure matches the current filters.",
            documentType: "Customer",
            columns: [
                column("customer", "Customer", ["customer_name", "customer", "name"], "primary"),
                column("contexts", "Contexts", ["context_count", "project_count", "order_count"], "number"),
                column("collected", "Collected", ["collected", "collected_amount"], "money"),
                column("paid", "Supplier Paid", ["supplier_paid", "paid"], "money"),
                column("net", "Net Cash", ["net_cash", "net"], "money"),
                column("expected_profit", "Expected Profit", ["expected_profit"], "money"),
                column("risk", "Risk", ["risk_status", "risk", "risk_level"], "status"),
            ],
        },
        monthly: {
            title: "Monthly Cash Movement",
            description: "Collected, paid, and expected movement by month.",
            empty: "No monthly cash movement is available for this period.",
            columns: [
                column("month", "Month", ["label", "month", "period"], "primary"),
                column("collected", "Actual Inflow", ["actual_inflow", "collected", "inflow"], "money"),
                column("paid", "Actual Outflow", ["actual_outflow", "paid", "outflow"], "money"),
                column("net", "Net", ["net", "net_cash"], "money"),
                column("expected_inflow", "Committed Inflow", ["committed_inflow", "expected_inflow"], "money"),
                column("expected_outflow", "Committed Outflow", ["committed_outflow", "expected_outflow"], "money"),
                column("forecast_outflow", "Forecast Outflow", ["forecast_outflow"], "money"),
            ],
        },
        quality: {
            title: "Data Quality",
            description: "Missing or incomplete source data affecting financial decisions.",
            empty: "No data-quality issues were reported.",
            columns: [
                column("severity", "Severity", ["severity", "level", "status"], "status"),
                column("context", "Context", ["context", "context_name", "name"], "primary"),
                column("issue", "Issue", ["issue", "message", "description"]),
                column("field", "Field", ["field", "fieldname"]),
                column("count", "Records", ["count", "record_count"], "number"),
                column("action", "Recommended Action", ["action", "recommendation"]),
                column("source", "Source Record", ["document_name", "name"], "document"),
            ],
        },
    };

    frappe.pages["sale-financial-dashboard"].on_page_load = function (wrapper) {
        ensureStyles();
        const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Project & Order Finance"), single_column: true });
        wrapper.page = page;
        page.main.addClass("ofw-root");
        hideFrappeHeader(wrapper);
        syncStateFromLocation();
        render(page);
        load(page);
    };

    frappe.pages["sale-financial-dashboard"].on_page_show = function (wrapper) {
        if (!wrapper.page) return;
        wrapper.page.set_title(__("Project & Order Finance"));
        const changed = syncStateFromLocation();
        if (changed.filters || (!STATE.data && !STATE.loading)) load(wrapper.page);
        else if (changed.tab) render(wrapper.page);
    };

    async function load(page) {
        const requestGeneration = ++STATE.requestGeneration;
        STATE.loading = true;
        STATE.error = null;
        render(page);
        try {
            const response = await frappe.call({ method: METHOD, args: { filters: JSON.stringify(STATE.filters) } });
            if (requestGeneration !== STATE.requestGeneration) return;
            STATE.data = response.message || {};
            if (STATE.data.active_filters) STATE.filters = { ...STATE.filters, ...safeFilters(STATE.data.active_filters) };
            updateUrl();
        } catch (error) {
            if (requestGeneration !== STATE.requestGeneration) return;
            STATE.error = error;
            console.warn("Project & Order Finance portfolio failed", error);
        } finally {
            if (requestGeneration !== STATE.requestGeneration) return;
            STATE.loading = false;
            render(page);
        }
    }

    function render(page) {
        const data = STATE.data || {};
        page.set_title(__("Project & Order Finance"));
        page.main.html(`
            <main class="ofw-shell" aria-labelledby="ofw-page-title">
                ${breadcrumb()}
                <header class="ofw-header">
                    <div class="ofw-header-copy">
                        <span class="ofw-eyebrow">${icon("portfolio")}${esc(__("Finance Portfolio"))}</span>
                        <h1 id="ofw-page-title">${esc(__("Project & Order Finance"))}</h1>
                        <p>${esc(__("A decision-focused view of collections, supplier payments, commitments, risk, and short-term funding across projects and standalone sales orders."))}</p>
                    </div>
                    <div class="ofw-header-meta">
                        <span class="ofw-company">${icon("company")}<span>${esc(__("Active company"))}: <strong>${esc(activeCompany(data) || __("Session company"))}</strong></span></span>
                        <button type="button" class="ofw-button" data-refresh ${STATE.loading ? "disabled" : ""}>${icon("refresh")}${esc(__("Refresh"))}</button>
                    </div>
                </header>
                ${tabs(data)}
                ${filterPanel(data)}
                <div class="ofw-live" aria-live="polite" aria-busy="${STATE.loading ? "true" : "false"}">
                    ${STATE.error ? errorState() : STATE.loading ? skeleton() : portfolioContent(data)}
                </div>
            </main>
        `);
        bind(page);
    }

    function breadcrumb() {
        return `<nav class="ofw-breadcrumb" aria-label="${esc(__("Breadcrumb"))}"><a href="/app/home-page">${esc(__("Main Dashboard"))}</a><span aria-hidden="true">/</span><span>${esc(__("Finance"))}</span><span aria-hidden="true">/</span><strong>${esc(__("Project & Order Finance"))}</strong></nav>`;
    }

    function tabs(data) {
        return `<div class="ofw-tabs-wrap"><nav class="ofw-tabs" aria-label="${esc(__("Portfolio views"))}">${TABS.map(([key, label, source]) => {
            const count = source ? rows(data, source).length : null;
            const active = STATE.activeTab === key;
            return `<button type="button" class="ofw-tab" id="ofw-tab-${key}" aria-pressed="${active}" ${active ? 'aria-current="page"' : ""} data-tab="${key}">${esc(__(label))}${count === null ? "" : `<span class="ofw-tab-count">${count}</span>`}</button>`;
        }).join("")}</nav></div>`;
    }

    function filterPanel(data) {
        const options = data.filter_options || data.filters || {};
        return `<section class="ofw-filter-card ${STATE.filtersOpen ? "filters-open" : ""}" aria-label="${esc(__("Portfolio filters"))}">
            <div class="ofw-filter-heading">
                <div class="ofw-filter-title"><strong>${esc(__("Portfolio"))}</strong><small>${activeFilterCount()} ${esc(__("active filters"))}</small></div>
                <label class="ofw-filter-search">${icon("search")}<span class="sr-only">${esc(__("Search portfolio"))}</span><input type="search" data-filter="search" value="${esc(STATE.filters.search)}" placeholder="${esc(__("Search project, order, or customer"))}"></label>
                <button type="button" class="ofw-button compact ofw-filter-toggle" data-toggle-filters aria-expanded="${STATE.filtersOpen}">${icon("filter")}${esc(STATE.filtersOpen ? __("Close filters") : __("Filters"))}${activeFilterCount() ? `<span class="ofw-filter-count">${activeFilterCount()}</span>` : ""}</button>
            </div>
            <div class="ofw-filter-body">
                <div class="ofw-filter-grid">
                    ${select("status", __("Status"), optionList(options, ["workflow_statuses", "statuses", "status", "project_statuses", "order_statuses"]), __("All statuses"))}
                    ${select("customer", __("Customer"), optionList(options, ["customers", "customer"]), __("All customers"))}
                    ${select("project_type", __("Project Type"), optionList(options, ["project_types", "project_type"]), __("All project types"))}
                    ${select("business_type", __("Business Type"), optionList(options, ["business_types", "business_type"]), __("All business types"))}
                    ${select("segment", __("Segment"), optionList(options, ["segments", "crm_segments", "segment"]), __("All segments"))}
                </div>
                <div class="ofw-filter-grid secondary">
                    ${select("risk_status", __("Risk"), optionList(options, ["risk_statuses", "risks", "risk_levels", "risk"]), __("All risk levels"))}
                    ${select("revenue_forecast_status", __("Revenue Forecast"), forecastStatusOptions(), __("Open or final"))}
                    ${select("cost_forecast_status", __("Cost Forecast"), forecastStatusOptions(), __("Open or final"))}
                    ${select("currency", __("Currency"), optionList(options, ["currencies", "currency"]), __("All currencies"))}
                    ${select("horizon", __("Horizon"), horizonOptions(options), __("Default horizon"))}
                    ${input("from_date", __("From Date"), "date")}
                    ${input("to_date", __("To Date"), "date")}
                </div>
                <div class="ofw-filter-actions"><button type="button" class="ofw-button quiet" data-clear-filters>${esc(__("Clear"))}</button><button type="button" class="ofw-button primary" data-apply-filters>${icon("filter")}${esc(__("Apply Filters"))}</button></div>
            </div>
        </section>`;
    }

    function portfolioContent(data) {
        if (!hasPortfolioData(data)) return emptyState(__("No financial portfolio data"), __("No projects, standalone orders, or financial movements match the current filters."));
        const active = TABLES[STATE.activeTab];
        const summary = ["overview", "profitability"].includes(STATE.activeTab) ? profitabilitySummary(data) : summaryCards(data);
        return `${summary}<section id="ofw-panel-${STATE.activeTab}" aria-labelledby="ofw-tab-${STATE.activeTab}">${STATE.activeTab === "overview" ? overview(data) : tablePanel(rows(data, TABS.find((tab) => tab[0] === STATE.activeTab)?.[2]), active, true)}</section>`;
    }

    function profitabilitySummary(data) {
        const summary = data.summary || {};
        const currency = pick(data, ["company_currency"]) || pick(summary, ["currency", "presentation_currency", "base_currency"]);
        const complete = Boolean(summary.profitability_complete);
        return `<section class="ofw-finance-groups" aria-label="${esc(__("Profitability and cash summary"))}">
            ${financeGroup("Expected", "Sales Orders and remaining direct costs", "expected", [
                ["Revenue HT", money(pick(summary, ["expected_revenue_ht"]), currency)],
                ["Revenue TTC", money(pick(summary, ["expected_revenue_ttc"]), currency)],
                ["Cost", complete ? money(pick(summary, ["expected_cost"]), currency) : incompleteValue(summary)],
                ["Profit", complete ? money(pick(summary, ["expected_profit"]), currency) : incompleteValue(summary), complete && Number(summary.expected_profit || 0) < 0],
                ["Profit %", complete ? percent(pick(summary, ["expected_profit_pct"])) : incompleteValue(summary), complete && Number(summary.expected_profit_pct || 0) < 0],
            ])}
            ${financeGroup("Actual to Date", "Submitted invoices, independent of payments", "actual", [
                ["Invoiced HT", money(pick(summary, ["invoiced_revenue_ht"]), currency)],
                ["Invoiced TTC", money(pick(summary, ["invoiced_revenue_ttc"]), currency)],
                ["Actual Cost", money(pick(summary, ["actual_cost_ht"]), currency)],
                ["Profit to Date", money(pick(summary, ["actual_profit_to_date"]), currency), Number(summary.actual_profit_to_date || 0) < 0],
                ["Profit %", percent(pick(summary, ["actual_profit_pct"])), Number(summary.actual_profit_pct || 0) < 0],
            ])}
            ${financeGroup("Cash", "Money received, paid, and required", "cash", [
                ["Collected", money(pick(summary, ["collected"]), currency)],
                ["Supplier Paid", money(pick(summary, ["supplier_paid", "paid"]), currency)],
                ["Net Cash Flow", money(pick(summary, ["net_cash"]), currency), Number(summary.net_cash || 0) < 0],
                ["Expected Outflow", money(expectedOutflow(summary), currency)],
                ["Funding Gap", money(pick(summary, ["funding_gap"]), currency), Number(summary.funding_gap || 0) > 0],
            ])}
        </section>`;
    }

    function financeGroup(title, description, tone, metrics) {
        return `<article class="ofw-finance-group ${tone}"><header><div><span>${esc(__(title))}</span><small>${esc(__(description))}</small></div>${icon(tone === "cash" ? "cash" : tone === "actual" ? "document" : "portfolio")}</header><div class="ofw-finance-metrics">${metrics.map(([label, value, negative]) => `<div><span>${esc(__(label))}</span><strong class="${negative ? "negative" : ""}">${value}</strong></div>`).join("")}</div></article>`;
    }

    function incompleteValue(summary) {
        const count = Number(summary.incomplete_profitability || 0);
        return `<span class="ofw-incomplete">${esc(__("Incomplete"))}${count ? ` · ${number(count)} ${esc(__("contexts"))}` : ""}</span>`;
    }

    function summaryCards(data) {
        const summary = data.summary || {};
        const currency = pick(data, ["company_currency"]) || pick(summary, ["currency", "presentation_currency", "base_currency"]) || "";
        const portfolioRows = [...rows(data, "project_rows"), ...rows(data, "standalone_order_rows")];
        const overdue = portfolioRows.filter((row) => String(row.risk_status || "").toLowerCase() === "overdue").length;
        const qualityCount = rows(data, "data_quality_rows").length;
        const period = horizonLabel(data);
        const cards = [
            ["Collected", ["collected", "total_collected"], "money", "Cash received"],
            ["Paid", ["supplier_paid", "paid", "total_paid"], "money", "Supplier cash paid"],
            ["Net", ["net_cash", "net", "net_position"], "money", "Collected less supplier paid"],
            [`${period} Expected Inflow`, ["expected_inflow_13w", "thirteen_week_expected_inflow", "expected_inflow", "committed_inflow"], "money", `Forward receipts for ${period.toLowerCase()}`],
            [`${period} Expected Outflow`, ["expected_outflow_13w", "thirteen_week_expected_outflow", "expected_outflow"], "outflow", `Commitments and forecast for ${period.toLowerCase()}`],
            ["Funding Gap", ["funding_gap", "gap"], "money", "Peak shortfall"],
            ["At Risk", ["at_risk", "at_risk_count"], "number", "Contexts requiring attention"],
            ["Overdue", ["overdue", "overdue_count"], "number", "Overdue contexts", overdue],
            ["Completeness", ["completeness", "data_completeness", "completeness_pct"], "completeness", `${qualityCount} ${__("quality issues")}`],
        ];
        return `<section class="ofw-kpis" aria-label="${esc(__("Portfolio summary"))}">${cards.map(([label, aliases, type, hint, fallback], index) => {
            const sourceValue = pick(summary, aliases);
            const value = sourceValue === "" ? fallback : sourceValue;
            const negative = Number(value || 0) < 0 || (label === "Funding Gap" && Number(value || 0) > 0);
            const display = type === "money" ? money(value, currency) : type === "outflow" ? money(expectedOutflow(summary), currency) : type === "completeness" ? completenessValue(value) : number(value);
            return `<article class="ofw-kpi ${index < 3 ? "primary" : "secondary"} ${negative ? "negative" : ""}"><span class="ofw-kpi-label">${esc(__(label))}${icon(label === "Funding Gap" || label === "At Risk" || label === "Overdue" ? "alert" : "cash")}</span><strong>${display}</strong><small>${esc(hint)}</small></article>`;
        }).join("")}</section>`;
    }

    function overview(data) {
        const projects = riskFirst(rows(data, "project_rows")).slice(0, 6);
        const orders = riskFirst(rows(data, "standalone_order_rows")).slice(0, 6);
        return `<div class="ofw-overview-grid">${focusPanel(projects, TABLES.projects, "projects")}${focusPanel(orders, TABLES.standalone, "standalone")}</div>${tablePanel(rows(data, "monthly_rows").slice(0, 12), TABLES.monthly, false, "monthly")}`;
    }

    function focusPanel(inputRows, config, targetTab) {
        const total = rows(STATE.data || {}, targetTab === "projects" ? "project_rows" : "standalone_order_rows").length;
        return `<article class="ofw-panel ofw-focus-panel"><header class="ofw-panel-head"><div><h2>${esc(__(config.title))}</h2><p>${esc(__(config.description))}</p></div><button type="button" class="ofw-button compact" data-show-tab="${targetTab}">${esc(__("View all"))}<span class="ofw-button-count">${total}</span>${icon("arrow")}</button></header>${inputRows.length ? `<div class="ofw-focus-list">${inputRows.map((row) => focusRow(row, config)).join("")}</div>` : emptyState(__("Nothing to show"), __(config.empty))}</article>`;
    }

    function focusRow(row, config) {
        const contextName = pick(row, ["context_name", "project", "project_name", "sales_order", "order_name", "name"]);
        const contextType = safeContextType(pick(row, ["context_type"]) || config.contextType);
        const title = pick(row, config.columns[0].aliases) || contextName || "-";
        const customer = pick(row, ["customer_name", "customer"]) || __("No customer");
        const subtype = pick(row, ["project_type", "business_type", "context_type"]);
        const risk = pick(row, ["risk_status", "risk", "risk_level"]);
        const workflowStatus = pick(row, ["workflow_status", "status", "project_status", "order_status"]);
        const profit = pick(row, ["expected_profit"]);
        const netCash = pick(row, ["net_cash"]);
        const currency = pick(row, ["company_currency", "currency", "presentation_currency"]);
        const canOpen = contextType && safeRouteName(contextName);
        return `<button type="button" class="ofw-focus-row" ${canOpen ? `data-open-context data-context-type="${esc(contextType)}" data-context-name="${esc(contextName)}"` : "disabled"}>
            <span class="ofw-focus-mark" aria-hidden="true">${contextType === "Project" ? "P" : "SO"}</span>
            <span class="ofw-focus-copy"><strong title="${esc(title)}">${esc(title)}</strong><small>${esc(customer)}${subtype ? `<span aria-hidden="true">·</span>${esc(subtype)}` : ""}</small></span>
            <span class="ofw-focus-state">${status(risk || workflowStatus)}${risk && workflowStatus ? `<small title="${esc(workflowStatus)}">${esc(workflowStatus)}</small>` : ""}</span>
            <span class="ofw-focus-value"><small>${esc(__("Expected profit"))}</small><strong class="${Number(profit || 0) < 0 ? "negative" : ""}">${row.profitability_complete ? money(profit, currency) : `<span class="ofw-incomplete">${esc(__("Incomplete"))}</span>`}</strong><small>${esc(__("Net cash"))}: ${money(netCash, currency)}</small></span>
            ${icon("arrow")}
        </button>`;
    }

    function tablePanel(inputRows, config, sortable, targetTab) {
        if (!config) return emptyState(__("View unavailable"), __("This portfolio view is not available."));
        const displayRows = sortable ? sortedRows(inputRows, config) : inputRows;
        return `<article class="ofw-panel"><header class="ofw-panel-head"><div><h2>${esc(__(config.title))}</h2><p>${esc(__(config.description))}</p></div>${targetTab ? `<button type="button" class="ofw-button compact" data-show-tab="${targetTab}">${esc(__("View all"))}${icon("arrow")}</button>` : `<span class="ofw-context-pill">${displayRows.length} ${esc(__("rows"))}</span>`}</header>${displayRows.length ? table(displayRows, config, sortable) : emptyState(__("Nothing to show"), __(config.empty))}</article>`;
    }

    function table(inputRows, config, sortable) {
        return `<div class="ofw-table-wrap"><table class="ofw-table"><thead><tr>${config.columns.map((col) => {
            const active = STATE.sort.key === col.key;
            const aria = active ? (STATE.sort.direction === "asc" ? "ascending" : "descending") : "none";
            return `<th scope="col" aria-sort="${aria}" data-align="${col.align}">${sortable ? `<button type="button" class="ofw-sort" data-sort="${col.key}">${esc(__(col.label))}<i aria-hidden="true">${active ? (STATE.sort.direction === "asc" ? "↑" : "↓") : "↕"}</i></button>` : esc(__(col.label))}</th>`;
        }).join("")}</tr></thead><tbody>${inputRows.map((row) => tableRow(row, config)).join("")}</tbody></table></div>`;
    }

    function tableRow(row, config) {
        const contextName = pick(row, ["context_name", "project", "project_name", "sales_order", "order_name", "name"]);
        const contextType = pick(row, ["context_type"]) || config.contextType || "";
        return `<tr>${config.columns.map((col) => `<td data-label="${esc(__(col.label))}" data-align="${col.align}">${cell(row, col, config, contextType, contextName)}</td>`).join("")}</tr>`;
    }

    function cell(row, col, config, contextType, contextName) {
        const value = pick(row, col.aliases);
        if (col.type === "primary") {
            const secondary = pick(row, ["description", "company", "currency", "context_type"]);
            const content = `<span class="ofw-primary-cell"><strong>${esc(value || "-")}</strong>${secondary ? `<small>${esc(secondary)}</small>` : ""}</span>`;
            if (config.documentType && safeRouteName(contextName)) return `<button type="button" class="ofw-primary-action" data-open-document data-doctype="${esc(config.documentType)}" data-name="${esc(contextName)}">${content}</button>`;
            if ((config.contextType || config.dynamicContext) && safeContextType(contextType) && safeRouteName(contextName)) return `<button type="button" class="ofw-primary-action" data-open-context data-context-type="${esc(safeContextType(contextType))}" data-context-name="${esc(contextName)}" aria-label="${esc(__("Open financial detail for {0}", [contextName]))}">${content}</button>`;
            return content;
        }
        if (col.type === "money") return `<span class="ofw-number ${Number(value || 0) < 0 ? "negative" : ""}">${money(value, pick(row, ["company_currency", "currency", "presentation_currency"]))}</span>`;
        if (col.type === "profit_money") return row.profitability_complete ? `<span class="ofw-number ${Number(value || 0) < 0 ? "negative" : ""}">${money(value, pick(row, ["company_currency", "currency", "presentation_currency"]))}</span>` : `<span class="ofw-incomplete">${esc(__("Incomplete"))}</span>`;
        if (col.type === "number") return `<span class="ofw-number">${number(value)}</span>`;
        if (col.type === "percent") return `<span class="ofw-number ${Number(value || 0) < 0 ? "negative" : ""}">${percent(value)}</span>`;
        if (col.type === "profit_percent") return row.profitability_complete ? `<span class="ofw-number ${Number(value || 0) < 0 ? "negative" : ""}">${percent(value)}</span>` : `<span class="ofw-incomplete">${esc(__("Incomplete"))}</span>`;
        if (col.type === "status") return status(value);
        if (col.type === "closure") return closureStatus(row);
        if (col.type === "event") return cashEvent(value);
        if (col.type === "document") return documentLink(row, value);
        return esc(value == null || value === "" ? "-" : value);
    }

    function status(value) {
        const text = String(value || __("Not set"));
        const lower = text.toLowerCase();
        const tone = /critical|high|overdue|blocked|danger|missing/.test(lower) ? "danger" : /medium|warning|risk|partial|pending/.test(lower) ? "warning" : /low|complete|paid|healthy|on track/.test(lower) ? "positive" : "";
        return `<span class="ofw-status ${tone}" title="${esc(text)}">${esc(text)}</span>`;
    }

    function closureStatus(row) {
        const revenue = row.revenue_forecast_final ? __("Revenue Final") : __("Revenue Open");
        const cost = row.cost_forecast_final ? __("Cost Final") : __("Cost Open");
        return `<span class="ofw-closure-pair"><span class="ofw-status ${row.revenue_forecast_final ? "positive" : "warning"}">${esc(revenue)}</span><span class="ofw-status ${row.cost_forecast_final ? "positive" : "warning"}">${esc(cost)}</span></span>`;
    }

    function cashEvent(value) {
        if (!value || typeof value !== "object") return esc(__("No upcoming event"));
        const currency = value.currency || "";
        const direction = value.direction === "outflow" ? __("Pay") : __("Receive");
        return `<span class="ofw-primary-cell"><strong>${esc(value.date || "-")} · ${esc(direction)}</strong><small>${money(value.amount, currency)} · ${esc(value.event_type || "")}</small></span>`;
    }

    function bind(page) {
        page.main.find("[data-refresh]").on("click", () => load(page));
        page.main.find("[data-apply-filters]").on("click", () => { STATE.filters = collectFilters(page); load(page); });
        page.main.find("[data-clear-filters]").on("click", () => { STATE.filters = defaultFilters(); load(page); });
        page.main.find("[data-toggle-filters]").on("click", () => { STATE.filtersOpen = !STATE.filtersOpen; render(page); });
        page.main.find('[data-filter="search"]').on("keydown", (event) => { if (event.key === "Enter") { STATE.filters = collectFilters(page); load(page); } });
        page.main.find("[data-tab], [data-show-tab]").on("click", function () { activateTab(page, $(this).data("tab") || $(this).data("show-tab"), true); });
        page.main.find("[data-tab]").on("keydown", function (event) { handleTabKeys(page, event, this); });
        page.main.find("[data-sort]").on("click", function () {
            const key = String($(this).data("sort"));
            STATE.sort = { key, direction: STATE.sort.key === key && STATE.sort.direction === "asc" ? "desc" : "asc" };
            render(page);
        });
        page.main.find("[data-open-context]").on("click", openContext);
        page.main.find("[data-open-document]").on("click", openDocument);
    }

    function activateTab(page, key, focus) {
        if (!TABS.some((tab) => tab[0] === key)) return;
        STATE.activeTab = key;
        updateUrl();
        render(page);
        if (focus) page.main.find(`[data-tab="${key}"]`).trigger("focus");
    }

    function handleTabKeys(page, event, element) {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        const keys = TABS.map((tab) => tab[0]);
        let index = keys.indexOf($(element).data("tab"));
        if (event.key === "Home") index = 0;
        else if (event.key === "End") index = keys.length - 1;
        else index = (index + (event.key === "ArrowRight" ? 1 : -1) + keys.length) % keys.length;
        activateTab(page, keys[index], true);
    }

    function openContext() {
        const contextType = safeContextType($(this).data("context-type"));
        const contextName = safeRouteName($(this).data("context-name"));
        if (contextType && contextName) frappe.set_route("sale-financial-workspace", contextType, contextName);
    }

    function openDocument() {
        const doctype = safeDoctype($(this).data("doctype"));
        const name = safeRouteName($(this).data("name"));
        if (doctype && name) frappe.set_route("Form", doctype, name);
    }

    function collectFilters(page) {
        const filters = defaultFilters();
        page.main.find("[data-filter]").each(function () { filters[$(this).data("filter")] = String($(this).val() || "").trim(); });
        return filters;
    }

    function input(key, label, type, placeholder) {
        return `<label class="ofw-field"><span>${esc(label)}</span><input type="${type}" data-filter="${key}" value="${esc(STATE.filters[key])}" ${placeholder ? `placeholder="${esc(placeholder)}"` : ""}></label>`;
    }

    function select(key, label, options, placeholder) {
        const values = withSelected(options, STATE.filters[key]);
        return `<label class="ofw-field"><span>${esc(label)}</span><select data-filter="${key}"><option value="">${esc(placeholder)}</option>${values.map((option) => `<option value="${esc(option.value)}" ${option.value === STATE.filters[key] ? "selected" : ""}>${esc(option.label)}</option>`).join("")}</select></label>`;
    }

    function sortedRows(inputRows, config) {
        const columnConfig = config.columns.find((col) => col.key === STATE.sort.key) || config.columns[0];
        const direction = STATE.sort.direction === "asc" ? 1 : -1;
        return [...inputRows].sort((left, right) => compare(pick(left, columnConfig.aliases), pick(right, columnConfig.aliases)) * direction);
    }

    function compare(left, right) {
        const aNumber = Number(left);
        const bNumber = Number(right);
        if (left !== "" && right !== "" && Number.isFinite(aNumber) && Number.isFinite(bNumber)) return aNumber - bNumber;
        return String(left || "").localeCompare(String(right || ""), undefined, { numeric: true, sensitivity: "base" });
    }

    function riskFirst(inputRows) {
        const weights = { "funding gap": 5, overdue: 4, critical: 5, high: 4, medium: 3, warning: 3, "on track": 1, low: 1 };
        return [...inputRows].sort((a, b) => (weights[String(pick(b, ["risk_status", "risk", "risk_level", "severity"]) || "").toLowerCase()] || 0) - (weights[String(pick(a, ["risk_status", "risk", "risk_level", "severity"]) || "").toLowerCase()] || 0));
    }

    function column(key, label, aliases, type = "text") {
        return { key, label, aliases, type, align: ["money", "number", "percent", "profit_money", "profit_percent"].includes(type) ? "right" : "left" };
    }

    function rows(data, key) { return Array.isArray(data[key]) ? data[key] : []; }
    function pick(object, aliases) { for (const key of aliases) if (object && object[key] !== undefined && object[key] !== null) return object[key]; return ""; }
    function activeCompany(data) { return pick(data, ["active_company", "company", "session_company"]) || pick(data.summary || {}, ["company"]); }
    function hasPortfolioData(data) { return TABS.some((tab) => tab[2] && rows(data, tab[2]).length); }

    function optionList(options, keys) {
        const output = [];
        keys.forEach((key) => {
            const value = options[key];
            (Array.isArray(value) ? value : value ? [value] : []).forEach((entry) => {
                const option = typeof entry === "object" ? { value: String(entry.value || entry.name || entry.label || ""), label: String(entry.label || entry.name || entry.value || "") } : { value: String(entry), label: String(entry) };
                if (option.value && !output.some((existing) => existing.value === option.value)) output.push(option);
            });
        });
        return output;
    }

    function horizonOptions(options) {
        const supplied = optionList(options, ["horizons", "horizon"]);
        return supplied.length ? supplied : [["13_weeks", __("13 weeks")], ["monthly", __("12 months")], ["lifetime", __("Lifetime")]].map(([value, label]) => ({ value, label }));
    }

    function forecastStatusOptions() {
        return [{ value: "Open", label: __("Open") }, { value: "Final", label: __("Final") }];
    }

    function horizonLabel(data) {
        const horizon = String(pick(data.active_filters || {}, ["horizon"]) || STATE.filters.horizon || "13_weeks").toLowerCase();
        if (STATE.filters.from_date || STATE.filters.to_date) return __("Selected Period");
        if (["monthly", "12_months"].includes(horizon)) return __("12M");
        if (horizon === "lifetime") return __("Lifetime");
        return __("13W");
    }

    function withSelected(options, selected) {
        const clean = [...options];
        if (selected && !clean.some((option) => option.value === selected)) clean.unshift({ value: selected, label: selected });
        return clean;
    }

    function defaultFilters() { return { search: "", status: "", customer: "", project_type: "", business_type: "", segment: "", risk_status: "", revenue_forecast_status: "", cost_forecast_status: "", currency: "", horizon: "13_weeks", from_date: "", to_date: "" }; }
    function safeFilters(filters) { const output = {}; FILTER_KEYS.forEach((key) => { output[key] = String(filters[key] ?? STATE.filters[key] ?? "").trim(); }); return output; }
    function readFilters() { const filters = defaultFilters(); FILTER_KEYS.forEach((key) => { const value = readQuery(key); if (value) filters[key] = value; }); return filters; }
    function activeFilterCount() { return FILTER_KEYS.filter((key) => STATE.filters[key] && !(key === "horizon" && STATE.filters[key] === "13_weeks")).length; }
    function readQuery(key) { return String(new URLSearchParams(window.location.search || "").get(key) || "").trim(); }

    function syncStateFromLocation() {
        const nextFilters = readFilters();
        const requestedTab = readQuery("tab");
        const nextTab = TABS.some((tab) => tab[0] === requestedTab) ? requestedTab : "overview";
        const changed = { filters: JSON.stringify(nextFilters) !== JSON.stringify(STATE.filters), tab: nextTab !== STATE.activeTab };
        STATE.filters = nextFilters;
        STATE.activeTab = nextTab;
        return changed;
    }

    function updateUrl() {
        const params = new URLSearchParams(window.location.search || "");
        params.delete("company");
        FILTER_KEYS.forEach((key) => { if (STATE.filters[key] && !(key === "horizon" && STATE.filters[key] === "13_weeks")) params.set(key, STATE.filters[key]); else params.delete(key); });
        if (STATE.activeTab !== "overview") params.set("tab", STATE.activeTab); else params.delete("tab");
        window.history.replaceState(null, "", `${window.location.pathname}${params.toString() ? `?${params}` : ""}`);
    }

    function completenessValue(rawValue) {
        if (rawValue === "" || rawValue === undefined || rawValue === null) return esc(__("Not reported"));
        let value = Number(rawValue);
        if (!Number.isFinite(value)) return esc(rawValue);
        if (value > 0 && value <= 1) value *= 100;
        return `${number(value, 1)}%`;
    }

    function expectedOutflow(summary) {
        const direct = Number(pick(summary, ["expected_outflow_13w", "thirteen_week_expected_outflow", "expected_outflow"]) || 0);
        return direct || Number(pick(summary, ["committed_outflow"]) || 0) + Number(pick(summary, ["forecast_outflow"]) || 0);
    }

    function money(value, currency) {
        const amount = typeof value === "object" && value ? Number(value.amount ?? value.value ?? 0) : Number(value || 0);
        const code = String((typeof value === "object" && value ? value.currency : "") || currency || "").trim();
        try { return esc(code ? new Intl.NumberFormat(undefined, { style: "currency", currency: code, maximumFractionDigits: 0 }).format(amount) : number(amount)); }
        catch (_error) { return esc(`${code} ${number(amount)}`.trim()); }
    }

    function documentLink(row, fallback) {
        const doctype = safeDoctype(pick(row, ["reference_doctype", "document_type", "doctype"]));
        const name = safeRouteName(pick(row, ["reference_name", "document_name", "name"]) || fallback);
        if (!doctype || !name) return esc(fallback || "-");
        return `<button type="button" class="ofw-doc-link" data-open-document data-doctype="${esc(doctype)}" data-name="${esc(name)}">${esc(__("Open {0}", [name]))}</button>`;
    }

    function safeContextType(value) { const text = String(value || "").trim().toLowerCase().replace(/[_-]+/g, " "); return text === "project" ? "Project" : ["sales order", "standalone", "standalone order"].includes(text) ? "Sales Order" : ""; }
    function safeDoctype(value) { const text = String(value || "").trim(); return SOURCE_DOCTYPES.has(text) ? text : ""; }
    function safeRouteName(value) { const text = String(value || "").trim(); return text && text.length <= 180 && !/[\u0000-\u001f]/.test(text) ? text : ""; }

    function number(value, precision = 0) { return new Intl.NumberFormat(undefined, { minimumFractionDigits: precision, maximumFractionDigits: precision }).format(Number(value || 0)); }
    function percent(value) { return `${number(value, 1)}%`; }

    function skeleton() {
        return `<span class="sr-only">${esc(__("Loading financial portfolio"))}</span><div class="ofw-skeleton-grid">${Array.from({ length: 8 }, () => '<div class="ofw-skeleton"></div>').join("")}</div><div class="ofw-skeleton large"></div>`;
    }

    function emptyState(title, message) {
        return `<div class="ofw-empty">${icon("empty")}<strong>${esc(title)}</strong><p>${esc(message)}</p></div>`;
    }

    function errorState() {
        const message = STATE.error && (STATE.error.message || STATE.error.exc) ? (STATE.error.message || STATE.error.exc) : __("Check your access or connection, then retry.");
        return `<div class="ofw-error" role="alert">${icon("alert")}<strong>${esc(__("Financial portfolio could not load"))}</strong><p>${esc(message)}</p><button type="button" class="ofw-button primary" data-refresh>${icon("refresh")}${esc(__("Retry"))}</button></div>`;
    }

    function ensureStyles() {
        if (document.getElementById(STYLE_ID)) return;
        const link = document.createElement("link");
        link.id = STYLE_ID;
        link.rel = "stylesheet";
        link.href = STYLE_URL;
        document.head.appendChild(link);
    }

    function hideFrappeHeader(wrapper) {
        $(wrapper).closest(".page-container").find(".page-head").hide();
    }

    function esc(value) { return frappe.utils.escape_html(String(value ?? "")); }

    function icon(name) {
        const icons = {
            portfolio: '<svg class="ofw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a2 2 0 012-2h4a2 2 0 012 2v2M3 12h18"/></svg>',
            company: '<svg class="ofw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 21h18M5 21V8l7-5 7 5v13M9 21v-6h6v6"/></svg>',
            refresh: '<svg class="ofw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M20 6v5h-5M4 18v-5h5"/><path d="M18.5 9A7 7 0 006 6.5L4 11m16 2-2 4.5A7 7 0 015.5 15"/></svg>',
            filter: '<svg class="ofw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M3 5h18l-7 8v5l-4 2v-7L3 5z"/></svg>',
            search: '<svg class="ofw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>',
            cash: '<svg class="ofw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="6" width="18" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/><path d="M7 9v6m10-6v6"/></svg>',
            document: '<svg class="ofw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 3h9l3 3v15H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/></svg>',
            alert: '<svg class="ofw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 3L2.5 20h19L12 3z"/><path d="M12 9v5m0 3h.01"/></svg>',
            arrow: '<svg class="ofw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M5 12h14m-5-5 5 5-5 5"/></svg>',
            empty: '<svg class="ofw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 9h8M8 13h5"/></svg>',
        };
        return icons[name] || "";
    }
})();
