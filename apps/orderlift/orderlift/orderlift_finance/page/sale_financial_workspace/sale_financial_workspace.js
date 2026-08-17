(function () {
    const METHOD = "orderlift.orderlift_finance.cash_flow.get_cash_flow_detail";
    const STYLE_ID = "orderlift-financial-workspace-style";
    const STYLE_URL = "/assets/orderlift/css/financial_workspace_20260815c.css";
    const SOURCE_DOCTYPES = new Set(["Project", "Sales Order", "Sales Invoice", "Purchase Invoice", "Purchase Order", "Payment Entry"]);
    const TABS = [
        ["overview", "Overview"],
        ["profitability", "Profitability"],
        ["timeline", "Cash Flow"],
        ["receivables", "Receivables"],
        ["payables", "Payables & Commitments"],
        ["documents", "Documents"],
        ["quality", "Data Quality"],
    ];
    const STATE = {
        contextType: "",
        contextName: "",
        activeTab: readQuery("tab") || "overview",
        horizon: readQuery("horizon") || "13_weeks",
        fromDate: readQuery("from_date"),
        toDate: readQuery("to_date"),
        data: null,
        loading: false,
        error: null,
        filtersOpen: false,
        requestGeneration: 0,
    };

    const TABLES = {
        events: {
            title: "Event Ledger",
            description: "Dated cash events and commitments in financial sequence.",
            empty: "No cash events are available for this context.",
            columns: [
                col("date", "Date", ["date", "posting_date", "due_date", "event_date"]),
                col("event", "Event", ["label", "event", "event_type", "type"], "primary"),
                col("period", "Period", ["period_status"], "status"),
                col("layer", "Layer", ["layer"], "status"),
                col("document", "Source", ["reference_name", "document_name", "name"], "document"),
                col("confidence", "Confidence", ["confidence"], "status"),
                col("inflow", "Inflow", ["inflow"], "money"),
                col("outflow", "Outflow", ["outflow"], "money"),
            ],
        },
        receivables: {
            title: "Receivables",
            description: "Customer invoices and open collection exposure.",
            empty: "No receivables are linked to this financial context.",
            columns: [
                col("document", "Invoice / Source", ["reference_name", "document_name", "name"], "document"),
                col("due_date", "Cash Date", ["date", "due_date"]),
                col("event", "Event", ["event_type", "type"]),
                col("layer", "Layer", ["layer"], "status"),
                col("confidence", "Confidence", ["confidence"], "status"),
                col("amount", "Expected Inflow", ["amount"], "money"),
                col("source_amount", "Source Amount", ["source_amount"], "source_money"),
            ],
        },
        payables: {
            title: "Payables & Commitments",
            description: "Supplier invoices, purchase commitments, and expected cash requirements.",
            empty: "No payables or commitments are linked to this financial context.",
            columns: [
                col("document", "Invoice / Commitment", ["reference_name", "document_name", "name"], "document"),
                col("due_date", "Cash Date", ["date", "due_date", "schedule_date"]),
                col("event", "Event", ["event_type", "type"]),
                col("layer", "Layer", ["layer"], "status"),
                col("confidence", "Confidence", ["confidence"], "status"),
                col("amount", "Expected Outflow", ["amount"], "money"),
                col("source_amount", "Source Amount", ["source_amount"], "source_money"),
            ],
        },
        documents: {
            title: "Source Documents",
            description: "Read-only source records supporting this financial view.",
            empty: "No source documents are linked to this context.",
            columns: [
                col("type", "Document Type", ["doctype", "document_type", "type"]),
                col("document", "Document", ["document_name", "name"], "document"),
                col("open", "Action", ["name"], "action"),
            ],
        },
        quality: {
            title: "Data Quality",
            description: "Source gaps that may affect cash-flow completeness or timing.",
            empty: "No data-quality issues were reported for this context.",
            columns: [
                col("severity", "Severity", ["severity", "level", "status"], "status"),
                col("issue", "Issue", ["issue", "message", "description"], "primary"),
                col("source", "Source", ["source", "document_type", "doctype"]),
                col("document", "Document", ["document_name", "name"], "document"),
                col("code", "Code", ["code"]),
            ],
        },
    };

    frappe.pages["sale-financial-workspace"].on_page_load = function (wrapper) {
        ensureStyles();
        const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Project & Order Finance Detail"), single_column: true });
        wrapper.page = page;
        page.main.addClass("ofw-root");
        hideFrappeHeader(wrapper);
        syncStateFromLocation();
        render(page);
        load(page);
    };

    frappe.pages["sale-financial-workspace"].on_page_show = function (wrapper) {
        if (!wrapper.page) return;
        const changed = syncStateFromLocation();
        if (changed.request || (!STATE.data && !STATE.loading)) load(wrapper.page);
        else if (changed.tab) render(wrapper.page);
    };

    async function load(page) {
        const requestGeneration = ++STATE.requestGeneration;
        if (!STATE.contextType || !STATE.contextName) {
            STATE.error = { message: __("Choose a project or standalone order from the finance portfolio.") };
            STATE.data = null;
            STATE.loading = false;
            render(page);
            return;
        }
        STATE.loading = true;
        STATE.error = null;
        render(page);
        try {
            const response = await frappe.call({
                method: METHOD,
                args: {
                    context_type: STATE.contextType,
                    context_name: STATE.contextName,
                    horizon: STATE.horizon,
                    from_date: STATE.fromDate,
                    to_date: STATE.toDate,
                },
            });
            if (requestGeneration !== STATE.requestGeneration) return;
            STATE.data = response.message || {};
            updateUrl();
        } catch (error) {
            if (requestGeneration !== STATE.requestGeneration) return;
            STATE.error = error;
            console.warn("Project & Order Finance detail failed", error);
        } finally {
            if (requestGeneration !== STATE.requestGeneration) return;
            STATE.loading = false;
            render(page);
        }
    }

    function resolveContext() {
        const route = frappe.get_route ? frappe.get_route() : [];
        STATE.contextType = safeContextType(decode(route[1] || readQuery("context_type")));
        STATE.contextName = safeRouteName(decode(route[2] || readQuery("context_name")));
    }

    function render(page) {
        const data = STATE.data || {};
        const identity = data.identity || {};
        const title = safeTitle(pick(identity, ["title", "project_name", "order_name", "context_name", "name"]) || STATE.contextName || __("Financial Detail"));
        page.set_title(title);
        page.main.html(`
            <main class="ofw-shell" aria-labelledby="ofw-detail-title">
                ${breadcrumb(title)}
                <header class="ofw-header">
                    <div class="ofw-header-copy">
                        <span class="ofw-eyebrow">${icon("cashflow")}${esc(contextLabel())}</span>
                        <h1 id="ofw-detail-title">${esc(title)}</h1>
                        <p>${esc(identityDescription(identity))}</p>
                    </div>
                    <div class="ofw-header-meta">
                        <span class="ofw-company">${icon("company")}<span>${esc(__("Active company"))}: <strong>${esc(pick(identity, ["company"]) || pick(data, ["active_company", "company"]) || __("Session company"))}</strong></span></span>
                        ${status(pick(identity, ["risk", "risk_level", "status"]))}
                        <button type="button" class="ofw-button" data-back>${icon("back")}${esc(__("Portfolio"))}</button>
                        <button type="button" class="ofw-button" data-refresh ${STATE.loading ? "disabled" : ""}>${icon("refresh")}${esc(__("Refresh"))}</button>
                    </div>
                </header>
                ${tabs()}
                ${detailFilters(data)}
                <div class="ofw-live" aria-live="polite" aria-busy="${STATE.loading ? "true" : "false"}">
                    ${STATE.error ? errorState() : STATE.loading ? skeleton() : detailContent(data)}
                </div>
            </main>
        `);
        bind(page);
    }

    function breadcrumb(title) {
        return `<nav class="ofw-breadcrumb" aria-label="${esc(__("Breadcrumb"))}"><a href="/app/sale-financial-dashboard">${esc(__("Project & Order Finance"))}</a><span aria-hidden="true">/</span><strong>${esc(title)}</strong></nav>`;
    }

    function tabs() {
        return `<div class="ofw-tabs-wrap"><nav class="ofw-tabs" aria-label="${esc(__("Financial detail views"))}">${TABS.map(([key, label]) => {
            const active = STATE.activeTab === key;
            return `<button type="button" class="ofw-tab" id="ofw-detail-tab-${key}" aria-pressed="${active}" ${active ? 'aria-current="page"' : ""} data-tab="${key}">${esc(__(label))}</button>`;
        }).join("")}</nav></div>`;
    }

    function detailFilters(data) {
        const options = (data.filter_options || {}).horizons || [];
        const horizons = options.length ? options : [
            { value: "13_weeks", label: __("13 weeks") },
            { value: "monthly", label: __("12 months") },
            { value: "lifetime", label: __("Lifetime") },
        ];
        return `<section class="ofw-filter-card ofw-period-card ${STATE.filtersOpen ? "filters-open" : ""}" aria-label="${esc(__("Cash-flow period"))}"><div class="ofw-filter-heading"><div class="ofw-filter-title"><strong>${esc(__("Cash-flow period"))}</strong><small>${esc(periodDescription(data))}</small></div><button type="button" class="ofw-button compact ofw-filter-toggle" data-toggle-filters aria-expanded="${STATE.filtersOpen}">${icon("calendar")}${esc(STATE.filtersOpen ? __("Close period") : __("Change period"))}</button></div><div class="ofw-filter-body"><div class="ofw-filter-grid secondary">
            <label class="ofw-field"><span>${esc(__("Horizon"))}</span><select data-detail-filter="horizon">${horizons.map((entry) => { const value = typeof entry === "object" ? String(entry.value || entry.name || entry.label || "") : String(entry); const label = typeof entry === "object" ? String(entry.label || entry.name || entry.value || "") : __("{0} weeks", [entry]); return `<option value="${esc(value)}" ${value === STATE.horizon ? "selected" : ""}>${esc(label)}</option>`; }).join("")}</select></label>
            <label class="ofw-field"><span>${esc(__("From Date"))}</span><input type="date" data-detail-filter="from_date" value="${esc(STATE.fromDate)}"></label>
            <label class="ofw-field"><span>${esc(__("To Date"))}</span><input type="date" data-detail-filter="to_date" value="${esc(STATE.toDate)}"></label>
            <button type="button" class="ofw-button primary" data-apply-period>${esc(__("Apply Period"))}</button>
        </div></div></section>`;
    }

    function detailContent(data) {
        if (!hasDetailData(data)) return emptyState(__("No financial detail"), __("No cash-flow records are available for this context and period."));
        const summary = ["overview", "profitability"].includes(STATE.activeTab) ? profitabilitySummary(data) : kpiStrip(data);
        return `${summary}<div class="ofw-detail-layout"><section class="ofw-detail-main" id="ofw-detail-panel-${STATE.activeTab}" aria-labelledby="ofw-detail-tab-${STATE.activeTab}">${activePanel(data)}</section>${alertsPanel(data.alerts || [], data)}</div>`;
    }

    function profitabilitySummary(data) {
        const profit = data.profitability || {};
        const expected = profit.expected || {};
        const actual = profit.actual || {};
        const cash = profit.cash || {};
        const currency = profit.currency || pick(data.identity || {}, ["company_currency", "currency"]);
        const complete = Boolean(expected.complete);
        return `<section class="ofw-finance-groups" aria-label="${esc(__("Expected, actual, and cash summary"))}">
            ${financeGroup("Expected", "Sales Orders and remaining direct costs", "expected", [
                ["Revenue HT", money(expected.revenue_ht, currency)],
                ["Revenue TTC", money(expected.revenue_ttc, currency)],
                ["Cost", complete ? money(expected.cost, currency) : incompleteValue()],
                ["Profit", complete ? money(expected.profit, currency) : incompleteValue(), complete && Number(expected.profit || 0) < 0],
                ["Profit %", complete ? percent(expected.profit_pct) : incompleteValue(), complete && Number(expected.profit_pct || 0) < 0],
            ])}
            ${financeGroup("Actual to Date", "Submitted invoices, independent of payments", "actual", [
                ["Invoiced HT", money(actual.revenue_ht, currency)],
                ["Invoiced TTC", money(actual.revenue_ttc, currency)],
                ["Actual Cost", money(actual.cost, currency)],
                ["Profit to Date", money(actual.profit, currency), Number(actual.profit || 0) < 0],
                ["Profit %", percent(actual.profit_pct), Number(actual.profit_pct || 0) < 0],
            ])}
            ${financeGroup("Cash", "Payments are not revenue or cost", "cash", [
                ["Collected", money(cash.collected, currency)],
                ["Supplier Paid", money(cash.supplier_paid, currency)],
                ["Net Cash Flow", money(cash.net_cash, currency), Number(cash.net_cash || 0) < 0],
                ["Expected Outflow", money(Number(cash.committed_outflow || 0) + Number(cash.forecast_outflow || 0), currency)],
                ["Funding Gap", money(cash.funding_gap, currency), Number(cash.funding_gap || 0) > 0],
            ])}
        </section>`;
    }

    function financeGroup(title, description, tone, metrics) {
        return `<article class="ofw-finance-group ${tone}"><header><div><span>${esc(__(title))}</span><small>${esc(__(description))}</small></div>${icon(tone === "cash" ? "cash" : tone === "actual" ? "document" : "cashflow")}</header><div class="ofw-finance-metrics">${metrics.map(([label, value, negative]) => `<div><span>${esc(__(label))}</span><strong class="${negative ? "negative" : ""}">${value}</strong></div>`).join("")}</div></article>`;
    }

    function incompleteValue() {
        return `<span class="ofw-incomplete">${esc(__("Incomplete"))}</span>`;
    }

    function kpiStrip(data) {
        const kpis = data.kpis || {};
        const identity = data.identity || {};
        const currency = pick(identity, ["company_currency", "currency"]) || pick(kpis, ["currency", "presentation_currency", "base_currency"]);
        const period = horizonLabel(data);
        const cards = [
            ["Collected", ["collected", "total_collected"]],
            ["Paid", ["supplier_paid", "paid", "total_paid"]],
            ["Net", ["net_cash", "net", "net_position"]],
            [`${period} Expected Inflow`, ["committed_inflow", "expected_inflow", "expected_inflow_13w"]],
            [`${period} Expected Outflow`, ["expected_outflow", "expected_outflow_13w"], "outflow"],
            ["Funding Gap", ["funding_gap", "gap"]],
            ["At Risk", ["at_risk", "at_risk_amount"], "risk"],
            ["Overdue", ["overdue", "overdue_amount"], "overdue"],
            ["Completeness", ["completeness", "data_completeness", "completeness_pct"], "completeness"],
        ];
        return `<section class="ofw-kpis" aria-label="${esc(__("Financial KPIs"))}">${cards.map(([label, aliases, type], index) => {
            const value = type === "completeness" ? completenessMetric(data, aliases) : pick(kpis, aliases);
            const negative = Number(value || 0) < 0 || (label === "Funding Gap" && Number(value || 0) > 0);
            const display = type === "outflow" ? money(expectedOutflow(kpis), currency) : type === "risk" ? esc(pick(identity, ["risk_status"]) || __("Not set")) : type === "overdue" ? number(overdueEventCount(data)) : type === "completeness" ? completenessValue(value) : money(value, currency);
            const hint = type === "completeness" ? __("{0} quality issues", [(data.data_quality || []).length]) : __("Current context");
            return `<article class="ofw-kpi ${index < 3 ? "primary" : "secondary"} ${negative ? "negative" : ""}"><span class="ofw-kpi-label">${esc(__(label))}${icon(label === "Funding Gap" || label === "At Risk" || label === "Overdue" ? "alert" : "cash")}</span><strong>${display}</strong><small>${esc(hint)}</small></article>`;
        }).join("")}</section>`;
    }

    function activePanel(data) {
        const bounded = eventRows(boundedEvents(data), data);
        if (STATE.activeTab === "profitability") return profitabilityPanel(data);
        if (STATE.activeTab === "timeline") return `${timelinePanel(data.buckets || [], data)}${tablePanel(bounded, TABLES.events)}`;
        if (STATE.activeTab === "receivables") return tablePanel(data.receivables || [], TABLES.receivables);
        if (STATE.activeTab === "payables") return tablePanel(data.payables || [], TABLES.payables);
        if (STATE.activeTab === "documents") return tablePanel(data.documents || [], TABLES.documents);
        if (STATE.activeTab === "quality") return tablePanel(data.data_quality || [], TABLES.quality);
        return `${timelinePanel((data.buckets || []).slice(0, 13), data)}<div class="ofw-overview-grid">${moneyFocusPanel((data.receivables || []).slice(0, 5), TABLES.receivables, "receivables", "inflow")}${moneyFocusPanel((data.payables || []).slice(0, 5), TABLES.payables, "payables", "outflow")}</div>${tablePanel(bounded.slice(0, 8), TABLES.events, "timeline")}`;
    }

    function profitabilityPanel(data) {
        const profit = data.profitability || {};
        const revenue = profit.revenue || {};
        const costs = profit.costs || {};
        const expected = profit.expected || {};
        const actual = profit.actual || {};
        const closure = profit.closure || {};
        const currency = profit.currency || pick(data.identity || {}, ["company_currency", "currency"]);
        return `${closurePanel(closure, revenue, costs, currency)}<div class="ofw-overview-grid">
            ${bridgePanel("Revenue", "HT drives profit; TTC drives customer cash.", [
                ["Ordered HT", money(revenue.ordered_ht, currency)],
                ["Ordered TTC", money(revenue.ordered_ttc, currency)],
                ["Invoiced HT", money(revenue.invoiced_ht, currency)],
                ["Invoiced TTC", money(revenue.invoiced_ttc, currency)],
                ["Remaining HT", money(revenue.remaining_ht, currency)],
                ["Expected Taxes", money(expected.taxes, currency)],
            ])}
            ${bridgePanel("Costs", "Real documents replace theoretical direct costs once.", [
                ["Sales Order Baseline", money(costs.baseline, currency)],
                ["Actual PI Cost", money(costs.actual, currency)],
                ["Committed PO Cost", money(costs.committed, currency)],
                ["Remaining Forecast", money(costs.forecast, currency)],
                ["Expected Total Cost", expected.complete ? money(costs.expected, currency) : incompleteValue()],
                ["Actual Profit to Date", money(actual.profit, currency), Number(actual.profit || 0) < 0],
            ])}
        </div><div class="ofw-profit-note"><strong>${esc(__("Profit and cash are independent."))}</strong><span>${esc(__("Expected Profit uses revenue HT minus direct expected costs. Net Cash Flow uses customer receipts minus supplier payments."))}</span></div>`;
    }

    function bridgePanel(title, description, metrics) {
        return `<article class="ofw-panel ofw-bridge-panel"><header class="ofw-panel-head"><div><h2>${esc(__(title))}</h2><p>${esc(__(description))}</p></div></header><div class="ofw-bridge-metrics">${metrics.map(([label, value, negative]) => `<div><span>${esc(__(label))}</span><strong class="${negative ? "negative" : ""}">${value}</strong></div>`).join("")}</div></article>`;
    }

    function closurePanel(closure, revenue, costs, currency) {
        const canManage = Boolean(closure.can_manage);
        return `<article class="ofw-panel ofw-closure-panel"><header class="ofw-panel-head"><div><h2>${esc(__("Forecast Closure"))}</h2><p>${esc(__("Explicitly remove only the remaining theoretical revenue or cost."))}</p></div></header><div class="ofw-closure-grid">
            ${closureControl("revenue", closure.revenue_final, canManage, __("Revenue Forecast"), __("Remaining uninvoiced revenue"), money(revenue.remaining_ht, currency))}
            ${closureControl("cost", closure.cost_final, canManage, __("Cost Forecast"), __("Remaining uncovered cost"), money(costs.forecast, currency))}
        </div></article>`;
    }

    function closureControl(key, isFinal, canManage, label, description, value) {
        const state = isFinal ? __("Final") : __("Open");
        const action = isFinal ? __("Reopen") : __("Mark Final");
        return `<section class="ofw-closure-control"><div><span>${esc(label)}</span>${status(state)}<small>${esc(description)}: <strong>${value}</strong></small></div>${canManage ? `<button type="button" class="ofw-button ${isFinal ? "" : "primary"}" data-set-forecast="${key}" data-final-value="${isFinal ? 0 : 1}">${esc(action)}</button>` : ""}</section>`;
    }

    function moneyFocusPanel(rows, config, targetTab, direction) {
        const allRows = (STATE.data || {})[targetTab];
        const total = Array.isArray(allRows) ? allRows.length : rows.length;
        return `<article class="ofw-panel ofw-focus-panel"><header class="ofw-panel-head"><div><h2>${esc(__(config.title))}</h2><p>${esc(__(config.description))}</p></div><button type="button" class="ofw-button compact" data-show-tab="${targetTab}">${esc(__("View all"))}<span class="ofw-button-count">${total}</span>${icon("arrow")}</button></header>${rows.length ? `<div class="ofw-money-list">${rows.map((row) => moneyFocusRow(row, direction)).join("")}</div>` : emptyState(__("Nothing to show"), __(config.empty))}</article>`;
    }

    function moneyFocusRow(row, direction) {
        const date = pick(row, ["date", "due_date", "schedule_date"]);
        const layer = pick(row, ["layer"]);
        const confidence = pick(row, ["confidence"]);
        const amountValue = pick(row, ["amount"]);
        const currency = pick(row, ["company_currency", "currency", "presentation_currency"]);
        return `<div class="ofw-money-row"><span class="ofw-money-mark ${direction}">${icon(direction === "inflow" ? "inflow" : "outflow")}</span><span class="ofw-money-copy">${documentLink(row, pick(row, ["reference_name", "document_name", "name"]))}<small>${esc(date || __("No cash date"))}${layer ? `<span aria-hidden="true">·</span>${esc(layer)}` : ""}${confidence ? `<span aria-hidden="true">·</span>${esc(confidence)}` : ""}</small></span><strong class="ofw-money-value ${direction}">${direction === "outflow" ? "−" : "+"}${money(amountValue, currency)}</strong></div>`;
    }

    function timelinePanel(buckets, data) {
        return `<article class="ofw-panel"><header class="ofw-panel-head"><div><h2>${esc(__("Cash & Funding Position"))}</h2><p>${esc(__("Expected inflow and outflow bars with cumulative funding position."))}</p></div><span class="ofw-context-pill">${buckets.length} ${esc(__("periods"))}</span></header>${buckets.length ? `${chart(buckets, data)}${bucketTable(buckets, data)}` : emptyState(__("No timeline data"), __("No cash buckets are available for this period."))}</article>`;
    }

    function chart(buckets, data) {
        const width = 900;
        const height = 245;
        const left = 38;
        const right = 18;
        const top = 18;
        const bottom = 38;
        const baseline = top + (height - top - bottom) / 2;
        const usableHeight = (height - top - bottom) / 2 - 8;
        const values = buckets.flatMap((row) => [Math.abs(bucketInflow(row)), Math.abs(bucketOutflow(row)), Math.abs(bucketPosition(row))]);
        const max = Math.max(...values, 1);
        const slot = (width - left - right) / buckets.length;
        const barWidth = Math.max(3, Math.min(16, slot * .26));
        const y = (value) => baseline - (Number(value || 0) / max) * usableHeight;
        const line = buckets.map((row, index) => `${left + slot * index + slot / 2},${y(bucketPosition(row))}`).join(" ");
        const marks = buckets.map((row, index) => {
            const center = left + slot * index + slot / 2;
            const inflowY = y(bucketInflow(row));
            const outflowY = y(-bucketOutflow(row));
            const showLabel = buckets.length <= 13 || index % Math.ceil(buckets.length / 10) === 0;
            return `<rect class="ofw-chart-inflow" x="${center - barWidth - 1}" y="${Math.min(baseline, inflowY)}" width="${barWidth}" height="${Math.max(1, Math.abs(baseline - inflowY))}" rx="2"/><rect class="ofw-chart-outflow" x="${center + 1}" y="${Math.min(baseline, outflowY)}" width="${barWidth}" height="${Math.max(1, Math.abs(baseline - outflowY))}" rx="2"/>${showLabel ? `<text class="ofw-chart-label" x="${center}" y="${height - 13}" text-anchor="middle">${esc(shortLabel(row, index))}</text>` : ""}`;
        }).join("");
        const first = amount(buckets[0], ["opening_position"]);
        const last = bucketPosition(buckets[buckets.length - 1]);
        const min = Math.min(first, ...buckets.map(bucketPosition));
        const currency = pick(buckets.find((row) => row.company_currency || row.currency) || {}, ["company_currency", "currency"]) || pick((STATE.data || {}).identity || {}, ["company_currency", "currency"]);
        const interval = intervalTerms(data);
        const positionSummary = __("Funding position starts at {0}, reaches a minimum of {1}, and ends at {2}.", [moneyText(first, currency), moneyText(min, currency), moneyText(last, currency)]);
        return `<div class="ofw-chart"><div class="ofw-chart-legend" aria-hidden="true"><span><i></i>${esc(__("Inflow"))}</span><span class="outflow"><i></i>${esc(__("Outflow"))}</span><span class="position"><i></i>${esc(__("Cumulative position"))}</span></div><div class="ofw-chart-plot"><svg viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="ofw-chart-title ofw-chart-desc"><title id="ofw-chart-title">${esc(__("{0} cash and cumulative funding position", [interval.adjective]))}</title><desc id="ofw-chart-desc">${esc(positionSummary)}</desc><line class="ofw-chart-grid" x1="${left}" y1="${top}" x2="${width - right}" y2="${top}"/><line class="ofw-chart-zero" x1="${left}" y1="${baseline}" x2="${width - right}" y2="${baseline}"/><line class="ofw-chart-grid" x1="${left}" y1="${height - bottom}" x2="${width - right}" y2="${height - bottom}"/>${marks}<polyline class="ofw-chart-line" points="${line}"/></svg></div></div><p class="ofw-chart-summary">${esc(__("{0} Exact {1} values follow in the accessible table. Overdue commitments are carried into the first selected period.", [positionSummary, interval.singular.toLowerCase()]))}</p>`;
    }

    function bucketTable(buckets, data) {
        const interval = intervalTerms(data);
        const config = { columns: [col("period", interval.singular, ["label", "week", "period", "date"], "primary"), col("inflow", "Inflow", ["inflow"], "money"), col("outflow", "Outflow", ["outflow"], "money"), col("net", "Net", ["net"], "money"), col("position", "Cumulative Position", ["position"], "money")] };
        const normalized = buckets.map((row) => ({ ...row, inflow: bucketInflow(row), outflow: bucketOutflow(row), net: bucketInflow(row) - bucketOutflow(row), position: bucketPosition(row) }));
        return `<div class="ofw-note"><strong>${esc(__("{0} chart data", [interval.adjective]))}</strong> ${esc(__("This table is the text alternative for the chart."))}</div>${table(normalized, config)}`;
    }

    function alertsPanel(alerts, data) {
        const currency = pick(data.identity || {}, ["company_currency", "currency"]);
        return `<aside class="ofw-alerts" aria-label="${esc(__("Decision alerts"))}"><div class="ofw-alerts-head"><strong>${esc(__("Decision Alerts"))}</strong></div>${alerts.length ? `<div class="ofw-alert-list">${alerts.map((alert) => { const severity = String(pick(alert, ["severity", "level"]) || "warning").toLowerCase(); const type = pick(alert, ["title", "label", "alert_type", "type"]); const message = pick(alert, ["message", "description", "detail"]) || alertMessage(type, alert.amount, currency); return `<article class="ofw-alert ${/critical|high|danger/.test(severity) ? "danger" : ""}"><strong>${esc(humanize(type) || __("Attention required"))}</strong><p>${esc(message)}</p>${pick(alert, ["action", "recommendation"]) ? `<span class="ofw-alert-meta">${esc(__("Decision"))}: ${esc(pick(alert, ["action", "recommendation"]))}</span>` : ""}</article>`; }).join("")}</div>` : `<div class="ofw-alert-empty">${esc(__("No decision alerts for this context."))}</div>`}</aside>`;
    }

    function tablePanel(rows, config, targetTab) {
        return `<article class="ofw-panel"><header class="ofw-panel-head"><div><h2>${esc(__(config.title))}</h2><p>${esc(__(config.description))}</p></div>${targetTab ? `<button type="button" class="ofw-button compact" data-show-tab="${targetTab}">${esc(__("View all"))}${icon("arrow")}</button>` : `<span class="ofw-context-pill">${rows.length} ${esc(__("rows"))}</span>`}</header>${rows.length ? table(rows, config) : emptyState(__("Nothing to show"), __(config.empty))}</article>`;
    }

    function table(rows, config) {
        return `<div class="ofw-table-wrap"><table class="ofw-table"><thead><tr>${config.columns.map((column) => `<th scope="col" data-align="${column.align}">${esc(__(column.label))}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${config.columns.map((column) => `<td data-label="${esc(__(column.label))}" data-align="${column.align}">${cell(row, column)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    }

    function cell(row, column) {
        const value = pick(row, column.aliases);
        if (column.type === "primary") return `<span class="ofw-primary-cell"><strong>${esc(value || "-")}</strong>${pick(row, ["description", "event_type", "currency"]) ? `<small>${esc(pick(row, ["description", "event_type", "currency"]))}</small>` : ""}</span>`;
        if (column.type === "money") return `<span class="ofw-number ${Number(value || 0) < 0 ? "negative" : ""}">${money(value, pick(row, ["company_currency", "currency", "presentation_currency"]))}</span>`;
        if (column.type === "source_money") return `<span class="ofw-number">${money(value, pick(row, ["source_currency", "currency"]))}</span>`;
        if (column.type === "number") return `<span class="ofw-number">${number(value)}</span>`;
        if (column.type === "status") return status(value);
        if (column.type === "document") return documentLink(row, value);
        if (column.type === "action") return documentAction(row);
        return esc(value == null || value === "" ? "-" : value);
    }

    function documentLink(row, fallback) {
        const doctype = pick(row, ["reference_doctype", "doctype", "document_type"]);
        const name = pick(row, ["reference_name", "document_name", "name"]) || fallback;
        if (!safeDoctype(doctype) || !safeRouteName(name)) return esc(fallback || "-");
        return `<button type="button" class="ofw-doc-link" data-open-document data-doctype="${esc(doctype)}" data-name="${esc(name)}">${esc(name)}${icon("external")}</button>`;
    }

    function documentAction(row) {
        const doctype = pick(row, ["reference_doctype", "doctype", "document_type"]);
        const name = pick(row, ["reference_name", "document_name", "name"]);
        return safeDoctype(doctype) && safeRouteName(name) ? `<button type="button" class="ofw-doc-link" data-open-document data-doctype="${esc(doctype)}" data-name="${esc(name)}">${esc(__("Open source"))}${icon("external")}</button>` : `<span>${esc(__("Unavailable"))}</span>`;
    }

    function status(value) {
        const text = String(value || __("Not set"));
        const lower = text.toLowerCase();
        const tone = /critical|high|overdue|blocked|danger|missing/.test(lower) ? "danger" : /medium|warning|risk|partial|pending/.test(lower) ? "warning" : /low|complete|paid|healthy|on track/.test(lower) ? "positive" : "";
        return `<span class="ofw-status ${tone}" title="${esc(text)}">${esc(text)}</span>`;
    }

    function bind(page) {
        page.main.find("[data-back]").on("click", () => frappe.set_route("sale-financial-dashboard"));
        page.main.find("[data-refresh]").on("click", () => load(page));
        page.main.find("[data-toggle-filters]").on("click", () => { STATE.filtersOpen = !STATE.filtersOpen; render(page); });
        page.main.find("[data-apply-period]").on("click", () => {
            STATE.horizon = String(page.main.find('[data-detail-filter="horizon"]').val() || "13_weeks");
            STATE.fromDate = String(page.main.find('[data-detail-filter="from_date"]').val() || "");
            STATE.toDate = String(page.main.find('[data-detail-filter="to_date"]').val() || "");
            load(page);
        });
        page.main.find("[data-tab], [data-show-tab]").on("click", function () { activateTab(page, $(this).data("tab") || $(this).data("show-tab"), true); });
        page.main.find("[data-tab]").on("keydown", function (event) { handleTabKeys(page, event, this); });
        page.main.find("[data-open-document]").on("click", function () {
            const doctype = safeDoctype($(this).data("doctype"));
            const name = safeRouteName($(this).data("name"));
            if (doctype && name) frappe.set_route("Form", doctype, name);
        });
        page.main.find("[data-set-forecast]").on("click", function () { setForecastFinality(page, this); });
    }

    function setForecastFinality(page, element) {
        const forecast = String($(element).data("set-forecast") || "");
        const isFinal = Number($(element).data("final-value")) === 1;
        if (!["revenue", "cost"].includes(forecast)) return;
        const message = isFinal
            ? forecast === "revenue"
                ? __("Mark revenue final? Remaining uninvoiced Sales Order revenue and its theoretical cash inflow will be removed. Existing invoices and receivables remain.")
                : __("Mark costs final? Remaining uncovered theoretical cost and its cash outflow will be removed. Existing Purchase Orders, invoices, and payables remain.")
            : __("Reopen the {0} forecast and recalculate remaining theoretical amounts from source documents?", [forecast]);
        frappe.confirm(message, async () => {
            const response = await frappe.call({
                method: "orderlift.orderlift_finance.cash_flow.set_forecast_finality",
                args: {
                    context_type: STATE.contextType,
                    context_name: STATE.contextName,
                    forecast,
                    is_final: isFinal ? 1 : 0,
                },
                freeze: true,
                freeze_message: __("Updating forecast..."),
            });
            STATE.data = response.message || STATE.data;
            frappe.show_alert({ message: __("{0} forecast updated", [forecast === "revenue" ? __("Revenue") : __("Cost")]), indicator: "green" });
            render(page);
        });
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

    function updateUrl() {
        const params = new URLSearchParams(window.location.search || "");
        params.delete("company");
        params.delete("context_type");
        params.delete("context_name");
        if (STATE.activeTab !== "overview") params.set("tab", STATE.activeTab); else params.delete("tab");
        if (STATE.horizon && STATE.horizon !== "13_weeks") params.set("horizon", STATE.horizon); else params.delete("horizon");
        if (STATE.fromDate) params.set("from_date", STATE.fromDate); else params.delete("from_date");
        if (STATE.toDate) params.set("to_date", STATE.toDate); else params.delete("to_date");
        window.history.replaceState(null, "", `${window.location.pathname}${params.toString() ? `?${params}` : ""}`);
    }

    function syncStateFromLocation() {
        const beforeRequest = [STATE.contextType, STATE.contextName, STATE.horizon, STATE.fromDate, STATE.toDate].join("\u0001");
        const beforeTab = STATE.activeTab;
        resolveContext();
        STATE.horizon = readQuery("horizon") || "13_weeks";
        STATE.fromDate = readQuery("from_date");
        STATE.toDate = readQuery("to_date");
        const requestedTab = readQuery("tab");
        STATE.activeTab = TABS.some((tab) => tab[0] === requestedTab) ? requestedTab : "overview";
        return {
            request: beforeRequest !== [STATE.contextType, STATE.contextName, STATE.horizon, STATE.fromDate, STATE.toDate].join("\u0001"),
            tab: beforeTab !== STATE.activeTab,
        };
    }

    function identityDescription(identity) {
        const values = [pick(identity, ["customer_name", "customer"]), pick(identity, ["status"]), pick(identity, ["project_type"]), pick(identity, ["business_type"]), pick(identity, ["segment", "crm_segment"])].filter(Boolean);
        return values.length ? values.join(" · ") : __("Read-only cash-flow detail, commitments, source documents, and decision alerts.");
    }

    function periodDescription(data) {
        const horizon = data.horizon || {};
        const from = String(horizon.from_date || STATE.fromDate || "").slice(0, 10);
        const to = String(horizon.to_date || STATE.toDate || "").slice(0, 10);
        return from || to ? [from || __("Start"), to || __("Today")].join(" → ") : __("{0} rolling view", [horizonLabel(data)]);
    }

    function contextLabel() {
        return /sales.?order|standalone/i.test(STATE.contextType) ? __("Standalone Order Finance") : __("Project Finance");
    }

    function completenessValue(rawValue) {
        if (rawValue === "" || rawValue === undefined || rawValue === null) return esc(__("Not reported"));
        let value = Number(rawValue);
        if (!Number.isFinite(value)) return esc(rawValue);
        if (value > 0 && value <= 1) value *= 100;
        return `${number(value, 1)}%`;
    }

    function completenessMetric(data, aliases) {
        for (const source of [data.kpis || {}, data.identity || {}, data]) {
            const value = pick(source, aliases);
            if (value !== "") return value;
        }
        return (data.data_quality || []).length ? 0 : 100;
    }

    function col(key, label, aliases, type = "text") { return { key, label, aliases, type, align: ["money", "number"].includes(type) ? "right" : "left" }; }
    function pick(object, aliases) { for (const key of aliases) if (object && object[key] !== undefined && object[key] !== null) return object[key]; return ""; }
    function amount(row, aliases) { return Number(pick(row, aliases) || 0); }
    function bucketInflow(row) { return amount(row, ["actual_inflow"]) + amount(row, ["committed_inflow"]) || amount(row, ["inflow", "expected_inflow"]); }
    function bucketOutflow(row) { return amount(row, ["actual_outflow"]) + amount(row, ["committed_outflow"]) + amount(row, ["forecast_outflow"]) || amount(row, ["outflow", "expected_outflow"]); }
    function bucketPosition(row) { return amount(row, ["closing_position", "cumulative", "funding_position", "position"]); }
    function expectedOutflow(kpis) { return amount(kpis, ["committed_outflow"]) + amount(kpis, ["forecast_outflow"]) || amount(kpis, ["expected_outflow", "expected_outflow_13w"]); }
    function overdueEventCount(data) { return eventRows(boundedEvents(data), data).filter((row) => row.period_status === "Overdue carried forward").length; }
    function boundedEvents(data) {
        const buckets = Array.isArray(data.buckets) ? data.buckets : [];
        const bucketEvents = buckets.flatMap((bucket) => Array.isArray(bucket.events) ? bucket.events : []);
        const source = bucketEvents.length ? bucketEvents : (Array.isArray(data.events) ? data.events : []);
        const bounds = data.horizon || {};
        const start = String(bounds.from_date || STATE.fromDate || "").slice(0, 10);
        const end = String(bounds.to_date || STATE.toDate || "").slice(0, 10);
        const filtered = bucketEvents.length ? source : source.filter((row) => {
            const eventDate = String(row.date || "").slice(0, 10);
            return eventDate && ((!start || eventDate >= start) && (!end || eventDate <= end) || (start && eventDate < start && row.layer !== "actual"));
        });
        const seen = new Set();
        return filtered.filter((row) => { const key = String(row.id || [row.date, row.event_type, row.reference_doctype, row.reference_name, row.direction, row.amount].join("|")); if (seen.has(key)) return false; seen.add(key); return true; });
    }
    function eventRows(rows, data) {
        const start = String((data.horizon || {}).from_date || STATE.fromDate || "").slice(0, 10);
        return rows.map((row) => ({ ...row, period_status: start && String(row.date || "").slice(0, 10) < start && row.layer !== "actual" ? "Overdue carried forward" : "Selected period", inflow: row.direction === "inflow" ? row.amount : 0, outflow: row.direction === "outflow" ? row.amount : 0 }));
    }
    function humanize(value) { return String(value || "").replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase()); }
    function alertMessage(type, value, currency) { return `${humanize(type) || __("Financial attention required")}: ${moneyText(value, currency)}.`; }
    function shortLabel(row, index) { return String(pick(row, ["short_label", "label", "week", "period"]) || `P${index + 1}`).slice(0, 12); }
    function readQuery(key) { return String(new URLSearchParams(window.location.search || "").get(key) || "").trim(); }
    function decode(value) { try { return decodeURIComponent(String(value || "")); } catch (_error) { return String(value || ""); } }

    function moneyText(value, currency) {
        const amountValue = typeof value === "object" && value ? Number(value.amount ?? value.value ?? 0) : Number(value || 0);
        const code = String((typeof value === "object" && value ? value.currency : "") || currency || "").trim();
        try { return code ? new Intl.NumberFormat(undefined, { style: "currency", currency: code, maximumFractionDigits: 0 }).format(amountValue) : number(amountValue); }
        catch (_error) { return `${code} ${number(amountValue)}`.trim(); }
    }

    function money(value, currency) { return esc(moneyText(value, currency)); }

    function horizonLabel(data) {
        const mode = String((data.horizon || {}).mode || STATE.horizon || "13_weeks").toLowerCase();
        if (mode === "custom" || STATE.fromDate || STATE.toDate) return __("Selected Period");
        if (["monthly", "12_months"].includes(mode)) return __("12M");
        if (mode === "lifetime") return __("Lifetime");
        return __("13W");
    }

    function intervalTerms(data) {
        const interval = String((data.horizon || {}).interval || (["monthly", "lifetime"].includes(STATE.horizon) ? "month" : "week")).toLowerCase();
        return interval === "month" ? { singular: __("Month"), adjective: __("Monthly") } : { singular: __("Week"), adjective: __("Weekly") };
    }

    function hasDetailData(data) {
        return Boolean(data.identity && safeRouteName(pick(data.identity, ["context_name", "name"])) && (data.profitability || ["buckets", "events", "receivables", "payables", "documents", "data_quality"].some((key) => Array.isArray(data[key]) && data[key].length)));
    }

    function safeTitle(value) { const text = String(value || "").replace(/[\u0000-\u001f]/g, " ").trim(); return text.slice(0, 180) || __("Financial Detail"); }
    function safeContextType(value) { const text = String(value || "").trim().toLowerCase().replace(/[_-]+/g, " "); return text === "project" ? "Project" : ["sales order", "standalone", "standalone order"].includes(text) ? "Sales Order" : ""; }
    function safeDoctype(value) { const text = String(value || "").trim(); return SOURCE_DOCTYPES.has(text) ? text : ""; }
    function safeRouteName(value) { const text = String(value || "").trim(); return text && text.length <= 180 && !/[\u0000-\u001f]/.test(text) ? text : ""; }

    function number(value, precision = 0) { return new Intl.NumberFormat(undefined, { minimumFractionDigits: precision, maximumFractionDigits: precision }).format(Number(value || 0)); }
    function percent(value) { return `${number(value, 1)}%`; }

    function skeleton() {
        return `<span class="sr-only">${esc(__("Loading financial detail"))}</span><div class="ofw-skeleton-grid">${Array.from({ length: 8 }, () => '<div class="ofw-skeleton"></div>').join("")}</div><div class="ofw-skeleton large"></div>`;
    }

    function emptyState(title, message) { return `<div class="ofw-empty">${icon("empty")}<strong>${esc(title)}</strong><p>${esc(message)}</p></div>`; }

    function errorState() {
        const message = STATE.error && (STATE.error.message || STATE.error.exc) ? (STATE.error.message || STATE.error.exc) : __("Check your access or connection, then retry.");
        const canRetry = STATE.contextType && STATE.contextName;
        return `<div class="ofw-error" role="alert">${icon("alert")}<strong>${esc(__("Financial detail could not load"))}</strong><p>${esc(message)}</p>${canRetry ? `<button type="button" class="ofw-button primary" data-refresh>${icon("refresh")}${esc(__("Retry"))}</button>` : `<button type="button" class="ofw-button primary" data-back>${icon("back")}${esc(__("Return to portfolio"))}</button>`}</div>`;
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
            cashflow: '<svg class="ofw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 18V6m0 12h16"/><path d="M7 14l4-4 3 2 5-6"/></svg>',
            company: '<svg class="ofw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 21h18M5 21V8l7-5 7 5v13M9 21v-6h6v6"/></svg>',
            back: '<svg class="ofw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M19 12H5m6-6-6 6 6 6"/></svg>',
            refresh: '<svg class="ofw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M20 6v5h-5M4 18v-5h5"/><path d="M18.5 9A7 7 0 006 6.5L4 11m16 2-2 4.5A7 7 0 015.5 15"/></svg>',
            calendar: '<svg class="ofw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></svg>',
            cash: '<svg class="ofw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="6" width="18" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/><path d="M7 9v6m10-6v6"/></svg>',
            document: '<svg class="ofw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 3h9l3 3v15H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/></svg>',
            inflow: '<svg class="ofw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 4v16M6 10l6-6 6 6"/></svg>',
            outflow: '<svg class="ofw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 4v16M6 14l6 6 6-6"/></svg>',
            alert: '<svg class="ofw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 3L2.5 20h19L12 3z"/><path d="M12 9v5m0 3h.01"/></svg>',
            arrow: '<svg class="ofw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M5 12h14m-5-5 5 5-5 5"/></svg>',
            external: '<svg class="ofw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 3h7v7M10 14 21 3"/><path d="M21 14v5a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h5"/></svg>',
            empty: '<svg class="ofw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 9h8M8 13h5"/></svg>',
        };
        return icons[name] || "";
    }
})();
