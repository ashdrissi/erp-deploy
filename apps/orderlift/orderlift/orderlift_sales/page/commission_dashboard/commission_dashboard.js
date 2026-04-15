frappe.pages["commission-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Commissions"),
        single_column: true,
    });

    if (page.set_breadcrumbs) page.set_breadcrumbs(__("Main Dashboard"));

    const state = makeInitialState();
    page.main.addClass("cdb-root");
    page.set_primary_action(__("Refresh"), () => loadCommissionDashboard(page, state));
    injectCommissionDashboardStyles();
    renderCommissionDashboard(page, state);
    loadCommissionDashboard(page, state);
};

const CDB_DASHBOARD_METHOD = "orderlift.orderlift_sales.page.commission_dashboard.commission_dashboard.get_dashboard_data";
const CDB_UPDATE_METHOD = "orderlift.orderlift_sales.page.commission_dashboard.commission_dashboard.update_commission";

const CDB_ICON = {
    agent: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="6" r="3.5"/><path d="M3 17c1.4-3.4 4-5 7-5s5.6 1.6 7 5"/></svg>`,
    quote: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3h10a2 2 0 0 1 2 2v12l-3-2-2 2-2-2-2 2-3-2V5a2 2 0 0 1 2-2z"/><line x1="7" y1="7" x2="13" y2="7"/><line x1="7" y1="10" x2="13" y2="10"/></svg>`,
    order: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="14" height="12" rx="2"/><line x1="6" y1="8" x2="14" y2="8"/><line x1="6" y1="11" x2="12" y2="11"/></svg>`,
    coin: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="10" cy="5" rx="5.5" ry="2.5"/><path d="M4.5 5v6c0 1.4 2.5 2.5 5.5 2.5s5.5-1.1 5.5-2.5V5"/><path d="M4.5 8c0 1.4 2.5 2.5 5.5 2.5s5.5-1.1 5.5-2.5"/></svg>`,
    check: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="4,10 8,14 16,6"/></svg>`,
    clock: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="10" r="7.5"/><polyline points="10,6 10,10 13,12"/></svg>`,
    board: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="14" height="14" rx="2"/><line x1="7" y1="3" x2="7" y2="17"/><line x1="13" y1="3" x2="13" y2="17"/><line x1="3" y1="8" x2="17" y2="8"/></svg>`,
    payout: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M16 6H4a2 2 0 0 0-2 2v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2z"/><circle cx="10" cy="10" r="2.2"/><path d="M6 10h.01M14 10h.01"/></svg>`,
};

function makeInitialState() {
    return {
        rows: [],
        filters: {
            agent: "",
            status: "",
            payout: "",
        },
        ledger: {
            query: "",
            status: "",
            payout: "",
            page: 1,
            pageSize: 4,
        },
        ui: {
            menuOpenFor: "",
            drawerFor: "",
            drawerDraft: null,
        },
        loading: false,
        loaded: false,
    };
}

function loadCommissionDashboard(page, state) {
    state.loading = true;
    renderCommissionDashboard(page, state);
    frappe.call({
        method: CDB_DASHBOARD_METHOD,
        freeze: false,
        callback: (response) => {
            state.rows = response.message?.rows || [];
            state.loaded = true;
            state.loading = false;
            if (state.ui.drawerFor && !state.rows.some((row) => row.name === state.ui.drawerFor)) {
                state.ui.drawerFor = "";
                state.ui.drawerDraft = null;
            }
            renderCommissionDashboard(page, state);
        },
        error: () => {
            state.loaded = true;
            state.loading = false;
            renderCommissionDashboard(page, state);
            frappe.show_alert({ message: __("Unable to load commission dashboard data."), indicator: "red" });
        },
    });
}

function renderCommissionDashboard(page, state) {
    const rows = getFilteredRows(state);
    const agents = buildAgentRows(rows);
    const ledgerState = getLedgerState(rows, state.ledger);
    const drawerRow = state.rows.find((row) => row.name === state.ui.drawerFor) || null;

    page.main.html(`
        <div class="cdb-shell">
            <section class="cdb-hero">
                <div class="cdb-hero-left">
                    <div class="cdb-hero-eyebrow">${__("Orderlift · Main Dashboard · Commission Ops")}</div>
                    <div class="cdb-hero-greeting">${__("Commissions cockpit")}</div>
                    <div class="cdb-hero-sub">${__("UI-only validation screen for sales-order driven commissions, payout follow-up, and agent operations.")}</div>
                </div>
                <div class="cdb-hero-right">
                    <div class="cdb-hero-stat"><div class="cdb-hero-stat-val">${agents.length}</div><div class="cdb-hero-stat-label">${__("Agents")}</div></div>
                    <div class="cdb-hero-divider"></div>
                    <div class="cdb-hero-stat"><div class="cdb-hero-stat-val">${formatCurrency(sum(rows, "commission_amount", (row) => row.status === "To Pay"))}</div><div class="cdb-hero-stat-label">${__("To Pay")}</div></div>
                    <div class="cdb-hero-divider"></div>
                    <div class="cdb-hero-stat"><div class="cdb-hero-stat-val">${formatCurrency(sum(rows, "commission_amount", (row) => row.payout_state === "Paid"))}</div><div class="cdb-hero-stat-label">${__("Paid")}</div></div>
                    <div class="cdb-hero-divider"></div>
                    <div class="cdb-hero-stat"><div class="cdb-hero-stat-val cdb-hero-stat-val--warn">${sumMax(agents, "delayed_orders")}</div><div class="cdb-hero-stat-label">${__("Delayed")}</div></div>
                </div>
            </section>

            <section class="cdb-shortcuts-grid">
                ${shortcutCard("board", __("Commission Dashboard"), "/app/commission-dashboard", "primary")}
                ${shortcutCard("payout", __("Sales Commissions"), "/app/sales-commission")}
                ${shortcutCard("order", __("Sales Orders"), "/app/sales-order")}
                ${shortcutCard("quote", __("Quotations"), "/app/quotation")}
            </section>

            <section class="cdb-filters">
                <label><span>${__("Agent")}</span><select data-cdb-filter="agent">${renderSelectOptions(uniqueValues(state.rows, "agent"), state.filters.agent, __("All agents"))}</select></label>
                <label><span>${__("Commission Status")}</span><select data-cdb-filter="status">${renderSelectOptions(uniqueValues(state.rows, "status"), state.filters.status, __("All statuses"))}</select></label>
                <label><span>${__("Payout")}</span><select data-cdb-filter="payout">${renderSelectOptions(uniqueValues(state.rows, "payout_state"), state.filters.payout, __("All payouts"))}</select></label>
            </section>

            <section class="cdb-kpis">
                ${renderKpiCard("quote", __("Quotations"), sumMax(agents, "quotations"), __("commercial pipeline"))}
                ${renderKpiCard("order", __("Sales Orders"), sumMax(agents, "sales_orders"), __("validated order base"))}
                ${renderKpiCard("check", __("Paid Orders"), sumMax(agents, "paid_orders"), __("invoice settled flows"))}
                ${renderKpiCard("clock", __("Unpaid Orders"), sumMax(agents, "unpaid_orders"), __("still waiting collection"))}
                ${renderKpiCard("clock", __("Delayed Orders"), sumMax(agents, "delayed_orders"), __("priority follow-up"))}
                ${renderKpiCard("check", __("Completed Orders"), sumMax(agents, "completed_orders"), __("fully completed flows"))}
                ${renderKpiCard("coin", __("Approved Commissions"), formatCurrency(sum(rows, "commission_amount", (row) => row.status === "Approved")), __("auto-created from confirmed orders"))}
                ${renderKpiCard("coin", __("To Pay Commissions"), formatCurrency(sum(rows, "commission_amount", (row) => row.status === "To Pay")), __("order paid, waiting payout"))}
                ${renderKpiCard("coin", __("Paid Commissions"), formatCurrency(sum(rows, "commission_amount", (row) => row.payout_state === "Paid")), __("already disbursed"))}
            </section>

            <section class="cdb-grid">
                <div class="cdb-card">
                    <div class="cdb-card-head">
                        <div>
                            <h2>${__("Agents overview")}</h2>
                            <div class="cdb-caption">${__("Operational view by salesperson")}</div>
                        </div>
                    </div>
                    <div class="cdb-table-wrap">${renderAgentsTable(agents)}</div>
                </div>

                <div class="cdb-side">
                    <div class="cdb-card">
                        <div class="cdb-card-head">
                            <div>
                                <h2>${__("Exceptions")}</h2>
                                <div class="cdb-caption">${__("Priority actions to validate with users")}</div>
                            </div>
                        </div>
                        <div>${renderAlerts(rows, agents)}</div>
                    </div>
                </div>
            </section>

            <section class="cdb-card cdb-card--ledger">
                <div class="cdb-card-head">
                    <div>
                        <h2>${__("Commission ledger")}</h2>
                        <div class="cdb-caption">${__("Live commission data with read-only rows, menu actions, and a payout details drawer.")}</div>
                    </div>
                </div>
                <div class="cdb-ledger-tools">${renderLedgerToolbar(rows, state.ledger)}</div>
                <div class="cdb-table-wrap">${renderLedgerTable(ledgerState.rows, state.ui.menuOpenFor)}</div>
                <div class="cdb-ledger-footer">${renderLedgerPagination(ledgerState)}</div>
            </section>
            ${renderCommissionDrawer(drawerRow, state.ui.drawerDraft)}
        </div>
    `);

    bindInteractions(page, state, rows);
}

function bindInteractions(page, state) {
    page.main.find("[data-cdb-filter]").on("change", (event) => {
        const key = event.currentTarget.getAttribute("data-cdb-filter");
        state.filters[key] = event.currentTarget.value || "";
        state.ledger.page = 1;
        state.ui.menuOpenFor = "";
        renderCommissionDashboard(page, state);
    });

    page.main.find("[data-cdb-ledger-query]").on("input", (event) => {
        state.ledger.query = event.currentTarget.value || "";
        state.ledger.page = 1;
        state.ui.menuOpenFor = "";
        renderCommissionDashboard(page, state);
    });

    page.main.find("[data-cdb-ledger-filter]").on("change", (event) => {
        const key = event.currentTarget.getAttribute("data-cdb-ledger-filter");
        state.ledger[key] = event.currentTarget.value || "";
        state.ledger.page = 1;
        state.ui.menuOpenFor = "";
        renderCommissionDashboard(page, state);
    });

    page.main.find("[data-cdb-page]").on("click", (event) => {
        const pageNumber = Number(event.currentTarget.getAttribute("data-cdb-page") || 1);
        state.ledger.page = pageNumber > 0 ? pageNumber : 1;
        state.ui.menuOpenFor = "";
        renderCommissionDashboard(page, state);
    });

    page.main.find(".cdb-shortcut").on("click", function () {
        const url = $(this).data("url");
        if (url) window.location.href = url;
    });

    page.main.find("[data-cdb-toggle-menu]").on("click", (event) => {
        const name = event.currentTarget.getAttribute("data-cdb-toggle-menu") || "";
        state.ui.menuOpenFor = state.ui.menuOpenFor === name ? "" : name;
        renderCommissionDashboard(page, state);
    });

    page.main.find("[data-cdb-open-drawer]").on("click", (event) => {
        state.ui.drawerFor = event.currentTarget.getAttribute("data-cdb-open-drawer") || "";
        const row = state.rows.find((item) => item.name === state.ui.drawerFor);
        state.ui.drawerDraft = row ? {
            status: row.status,
            payout_state: row.payout_state,
            payment_reference: row.payment_reference || "",
            note: row.note || "",
        } : null;
        state.ui.menuOpenFor = "";
        renderCommissionDashboard(page, state);
    });

    page.main.find("[data-cdb-close-drawer]").on("click", () => {
        state.ui.drawerFor = "";
        state.ui.drawerDraft = null;
        renderCommissionDashboard(page, state);
    });

    page.main.find("[data-cdb-drawer-field]").on("input change", (event) => {
        const fieldname = event.currentTarget.getAttribute("data-cdb-drawer-field");
        if (!fieldname) return;
        state.ui.drawerDraft = state.ui.drawerDraft || {};
        state.ui.drawerDraft[fieldname] = event.currentTarget.value || "";
    });

    page.main.find("[data-cdb-save-drawer]").on("click", () => {
        if (!state.ui.drawerFor || !state.ui.drawerDraft) return;
        persistCommissionUpdate(page, state, {
            name: state.ui.drawerFor,
            status: state.ui.drawerDraft.status,
            payout_state: state.ui.drawerDraft.payout_state,
            payment_reference: state.ui.drawerDraft.payment_reference,
            notes: state.ui.drawerDraft.note,
        }, __("Commission details saved"), { closeDrawer: true });
    });

    page.main.find("[data-cdb-quick]").on("click", (event) => {
        const action = event.currentTarget.getAttribute("data-cdb-quick");
        const name = event.currentTarget.getAttribute("data-name") || "";
        const payload = buildQuickActionPayload(name, action);
        if (!payload) return;
        persistCommissionUpdate(page, state, payload, __("Commission updated"));
    });
}

function buildQuickActionPayload(name, action) {
    if (!name) return;
    if (action === "approve") {
        return { name, status: "Approved", payout_state: "Unpaid" };
    }
    if (action === "to-pay") {
        return { name, status: "To Pay", payout_state: "Unpaid" };
    }
    if (action === "pay") {
        return { name, status: "Paid", payout_state: "Paid" };
    }
    return null;
}

function persistCommissionUpdate(page, state, payload, successMessage, options = {}) {
    state.ui.menuOpenFor = "";
    frappe.call({
        method: CDB_UPDATE_METHOD,
        args: payload,
        freeze: true,
        callback: () => {
            if (options.closeDrawer) {
                state.ui.drawerFor = "";
                state.ui.drawerDraft = null;
            }
            loadCommissionDashboard(page, state);
            frappe.show_alert({ message: successMessage, indicator: "green" });
        },
    });
}

function getFilteredRows(state) {
    return state.rows.filter((row) => {
        if (state.filters.agent && row.agent !== state.filters.agent) return false;
        if (state.filters.status && row.status !== state.filters.status) return false;
        if (state.filters.payout && row.payout_state !== state.filters.payout) return false;
        return true;
    });
}

function buildAgentRows(rows) {
    const buckets = new Map();

    rows.forEach((row) => {
        if (!buckets.has(row.agent)) {
            buckets.set(row.agent, {
                agent: row.agent,
                quotations: Number(row.quotation_count || 0),
                sales_orders: 0,
                paid_orders: 0,
                unpaid_orders: 0,
                delayed_orders: 0,
                completed_orders: 0,
                approved_count: 0,
                approved_amount: 0,
                to_pay_count: 0,
                to_pay_amount: 0,
                paid_amount: 0,
                _all_orders: new Set(),
                _paid_orders: new Set(),
                _unpaid_orders: new Set(),
                _delayed_orders: new Set(),
                _completed_orders: new Set(),
            });
        }

        const bucket = buckets.get(row.agent);
        const salesOrder = row.sales_order || row.name;
        bucket.quotations = Math.max(bucket.quotations, Number(row.quotation_count || 0));
        bucket._all_orders.add(salesOrder);
        if (row.order_paid) bucket._paid_orders.add(salesOrder);
        else bucket._unpaid_orders.add(salesOrder);
        if (row.order_delayed) bucket._delayed_orders.add(salesOrder);
        if (row.order_completed) bucket._completed_orders.add(salesOrder);
        if (row.status === "Approved") {
            bucket.approved_count += 1;
            bucket.approved_amount += row.commission_amount;
        } else if (row.status === "To Pay") {
            bucket.to_pay_count += 1;
            bucket.to_pay_amount += row.commission_amount;
        } else if (row.status === "Paid") {
            bucket.paid_amount += row.commission_amount;
        }
    });

    return Array.from(buckets.values()).map((bucket) => ({
        ...bucket,
        sales_orders: bucket._all_orders.size,
        paid_orders: bucket._paid_orders.size,
        unpaid_orders: bucket._unpaid_orders.size,
        delayed_orders: bucket._delayed_orders.size,
        completed_orders: bucket._completed_orders.size,
    })).sort((a, b) => b.sales_orders - a.sales_orders);
}

function renderKpiCard(icon, label, value, sublabel) {
    return `
        <div class="cdb-kpi">
            <div class="cdb-kpi-top"><span class="cdb-kpi-icon">${CDB_ICON[icon]}</span></div>
            <div class="cdb-kpi-value">${value}</div>
            <div class="cdb-kpi-label">${label}</div>
            <div class="cdb-kpi-sub">${sublabel}</div>
        </div>
    `;
}

function renderAgentsTable(rows) {
    if (!rows.length) return emptyState(__("No agents match the selected filters."));

    return `
        <table class="cdb-table cdb-table--agents">
            <thead>
                <tr>
                    <th>${__("Agent")}</th>
                    <th>${__("Quot.")}</th>
                    <th>${__("SO")}</th>
                    <th>${__("Paid")}</th>
                    <th>${__("Unpaid")}</th>
                    <th>${__("Delayed")}</th>
                    <th>${__("Completed")}</th>
                    <th>${__("Approved")}</th>
                    <th>${__("Approved Amt")}</th>
                    <th>${__("To Pay")}</th>
                    <th>${__("To Pay Amt")}</th>
                    <th>${__("Paid Amt")}</th>
                </tr>
            </thead>
            <tbody>
                ${rows.map((row) => `
                    <tr>
                        <td><strong>${escape(row.agent)}</strong></td>
                        <td>${row.quotations}</td>
                        <td>${row.sales_orders}</td>
                        <td>${row.paid_orders}</td>
                        <td>${row.unpaid_orders}</td>
                        <td><span class="cdb-pill cdb-pill--danger">${row.delayed_orders}</span></td>
                        <td>${row.completed_orders}</td>
                        <td>${row.approved_count}</td>
                        <td>${formatCurrency(row.approved_amount)}</td>
                        <td>${row.to_pay_count}</td>
                        <td>${formatCurrency(row.to_pay_amount)}</td>
                        <td>${formatCurrency(row.paid_amount)}</td>
                    </tr>
                `).join("")}
            </tbody>
        </table>
    `;
}

function renderAlerts(rows, agents) {
    const alerts = [];
    const delayed = sumMax(agents, "delayed_orders");
    const approvedWaitingPayment = sum(rows, "commission_amount", (row) => row.status === "Approved");
    const toPayUnpaid = sum(rows, "commission_amount", (row) => row.status === "To Pay" && row.payout_state === "Unpaid");

    if (approvedWaitingPayment) {
        alerts.push({ tone: "info", title: __("Approved commissions waiting customer payment"), body: __("{0} are attached to confirmed orders that are not yet fully paid.", [formatCurrency(approvedWaitingPayment)]) });
    }
    if (toPayUnpaid) {
        alerts.push({ tone: "warn", title: __("Commissions ready to pay"), body: __("{0} are now payable and waiting treasury payout.", [formatCurrency(toPayUnpaid)]) });
    }
    if (delayed) {
        alerts.push({ tone: "danger", title: __("Delayed orders still impact commission timing"), body: __(`UI preview highlights ${delayed} delayed order(s) that should stay visible in the real dashboard.`) });
    }

    if (!alerts.length) return emptyState(__("No blocking commission exceptions in this UI preview."));
    return alerts.map((item) => `
        <div class="cdb-alert cdb-alert--${item.tone}">
            <div class="cdb-alert-title">${item.title}</div>
            <div class="cdb-alert-body">${item.body}</div>
        </div>
    `).join("");
}

function renderLedgerToolbar(rows, ledger) {
    return `
        <div class="cdb-ledger-status-guide">
            <span>${statusPill("Approved")} ${__("created automatically when the Sales Order is confirmed")}</span>
            <span>${statusPill("To Pay")} ${__("used when the Sales Order is paid and commission becomes payable")}</span>
            <span>${statusPill("Paid")} ${__("used after the commission is actually disbursed")}</span>
        </div>
        <div class="cdb-ledger-toolbar">
            <label class="cdb-ledger-search">
                <span>${__("Search")}</span>
                <input type="text" value="${escape(ledger.query || "")}" placeholder="${escape(__("Search commission, agent, customer, SO, invoice"))}" data-cdb-ledger-query>
            </label>
            <label>
                <span>${__("Status")}</span>
                <select data-cdb-ledger-filter="status">${renderSelectOptions(uniqueValues(rows, "status"), ledger.status, __("All statuses"))}</select>
            </label>
            <label>
                <span>${__("Payout")}</span>
                <select data-cdb-ledger-filter="payout">${renderSelectOptions(uniqueValues(rows, "payout_state"), ledger.payout, __("All payouts"))}</select>
            </label>
        </div>
    `;
}

function renderLedgerTable(rows, menuOpenFor) {
    if (!rows.length) return emptyState(__("No commission rows match the selected ledger filters."));

    return `
        <table class="cdb-table cdb-table--ledger">
            <thead>
                <tr>
                    <th>${__("Commission")}</th>
                    <th>${__("Agent")}</th>
                    <th>${__("Customer")}</th>
                    <th>${__("Sales Order")}</th>
                    <th>${__("Invoice")}</th>
                    <th>${__("Workflow")}</th>
                    <th>${__("Payout")}</th>
                    <th>${__("Payment Ref")}</th>
                    <th>${__("Amount")}</th>
                    <th>${__("Actions")}</th>
                </tr>
            </thead>
            <tbody>
                ${rows.map((row) => `
                    <tr>
                        <td><span class="cdb-row-strong">${escape(row.name)}</span></td>
                        <td>${escape(row.agent)}</td>
                        <td>${escape(row.customer)}</td>
                        <td>${docLink("sales-order", row.sales_order)}</td>
                        <td>${row.sales_invoice ? docLink("sales-invoice", row.sales_invoice) : `<span class="cdb-muted">${__("Waiting")}</span>`}</td>
                        <td>${renderWorkflowCell(row)}</td>
                        <td>${renderPayoutCell(row)}</td>
                        <td>${row.payment_reference ? `<span class="cdb-ref-text">${escape(row.payment_reference)}</span>` : `<span class="cdb-muted">-</span>`}</td>
                        <td><strong>${formatCurrency(row.commission_amount)}</strong></td>
                        <td>${renderActionCell(row, menuOpenFor === row.name)}</td>
                    </tr>
                `).join("")}
            </tbody>
        </table>
    `;
}

function renderWorkflowCell(row) {
    return `
        <div class="cdb-state-cell">
            ${statusPill(row.status)}
            <span class="cdb-state-help">${escape(getWorkflowHelpText(row.status))}</span>
        </div>
    `;
}

function renderPayoutCell(row) {
    return `
        <div class="cdb-state-cell">
            ${statusPill(row.payout_state)}
            <span class="cdb-state-help">${escape(row.payout_state === "Paid" ? __("Disbursed") : __("Waiting payout"))}</span>
        </div>
    `;
}

function renderActionCell(row, isMenuOpen) {
    return `
        <div class="cdb-action-stack cdb-action-stack--menu-only">
            <div class="cdb-row-menu-wrap">
                <button class="cdb-row-menu-btn" type="button" aria-label="${escape(__("More actions"))}" data-cdb-toggle-menu="${escape(row.name)}">...</button>
                ${isMenuOpen ? renderRowMenu(row) : ""}
            </div>
        </div>
    `;
}

function renderRowMenu(row) {
    return `
        <div class="cdb-row-menu">
            <button type="button" data-cdb-quick="approve" data-name="${escape(row.name)}">${__("Set Approved")}</button>
            <button type="button" data-cdb-quick="to-pay" data-name="${escape(row.name)}">${__("Set To Pay")}</button>
            <button type="button" data-cdb-quick="pay" data-name="${escape(row.name)}">${__("Mark Paid")}</button>
            <button type="button" data-cdb-open-drawer="${escape(row.name)}">${__("Edit payout details")}</button>
            <a href="/app/sales-order/${encodeURIComponent(row.sales_order || "")}">${__("Open Sales Order")}</a>
            ${row.sales_invoice ? `<a href="/app/sales-invoice/${encodeURIComponent(row.sales_invoice)}">${__("Open Invoice")}</a>` : ""}
            <a href="/app/sales-commission/${encodeURIComponent(row.name)}">${__("Open Commission")}</a>
        </div>
    `;
}

function renderCommissionDrawer(row, draft = null) {
    if (!row) return "";
    const values = {
        status: draft?.status || row.status,
        payout_state: draft?.payout_state || row.payout_state,
        payment_reference: draft?.payment_reference ?? row.payment_reference ?? "",
        note: draft?.note ?? row.note ?? "",
    };
    return `
        <div class="cdb-drawer-backdrop" data-cdb-close-drawer></div>
        <aside class="cdb-drawer">
            <div class="cdb-drawer-head">
                <div>
                    <div class="cdb-drawer-eyebrow">${__("Commission Details")}</div>
                    <h3>${escape(row.name)}</h3>
                    <div class="cdb-drawer-sub">${escape(row.agent)} · ${escape(row.customer)}</div>
                </div>
                <button type="button" class="cdb-drawer-close" data-cdb-close-drawer>${__("Close")}</button>
            </div>
            <div class="cdb-drawer-body">
                <div class="cdb-drawer-stats">
                    <div class="cdb-mini-stat"><span>${__("Workflow")}</span><strong>${statusPill(row.status)}</strong></div>
                    <div class="cdb-mini-stat"><span>${__("Payout")}</span><strong>${statusPill(row.payout_state)}</strong></div>
                    <div class="cdb-mini-stat"><span>${__("Sales Order")}</span><strong>${escape(row.sales_order)}</strong></div>
                    <div class="cdb-mini-stat"><span>${__("Invoice")}</span><strong>${escape(row.sales_invoice || __("Waiting"))}</strong></div>
                </div>
                <div class="cdb-drawer-form">
                    <label>
                        <span>${__("Workflow Status")}</span>
                        <select data-cdb-drawer-field="status">
                            ${renderSelectOptions(["Approved", "To Pay", "Paid"], values.status, null, false)}
                        </select>
                    </label>
                    <label>
                        <span>${__("Payout Status")}</span>
                        <select data-cdb-drawer-field="payout_state">
                            ${renderSelectOptions(["Unpaid", "Paid"], values.payout_state, null, false)}
                        </select>
                    </label>
                    <label>
                        <span>${__("Payment Reference")}</span>
                        <input type="text" value="${escape(values.payment_reference)}" data-cdb-drawer-field="payment_reference" placeholder="${escape(__("TRF-00001"))}">
                    </label>
                    <label>
                        <span>${__("Ops Note")}</span>
                        <textarea rows="4" data-cdb-drawer-field="note" placeholder="${escape(__("Record payout or blocker note"))}">${escape(values.note)}</textarea>
                    </label>
                    <div class="cdb-drawer-actions">
                        <button type="button" class="cdb-inline-action cdb-inline-action--primary" data-cdb-save-drawer>${__("Save changes")}</button>
                    </div>
                </div>
            </div>
        </aside>
    `;
}

function renderLedgerPagination(ledgerState) {
    if (!ledgerState.total) return emptyState(__("No ledger rows to paginate."));
    const pageButtons = Array.from({ length: ledgerState.totalPages }, (_, index) => {
        const page = index + 1;
        return `<button type="button" class="cdb-page-btn ${page === ledgerState.page ? "is-active" : ""}" data-cdb-page="${page}">${page}</button>`;
    }).join("");
    return `
        <div class="cdb-pagination-meta">${__("Showing {0}-{1} of {2}", [ledgerState.start, ledgerState.end, ledgerState.total])}</div>
        <div class="cdb-pagination-pages">${pageButtons}</div>
    `;
}

function renderSelectOptions(values, selectedValue, emptyLabel, includeEmpty = true) {
    const list = includeEmpty ? ["", ...values] : values;
    return list.map((value, index) => {
        const label = includeEmpty && index === 0 ? emptyLabel : value;
        const selected = value === selectedValue ? "selected" : "";
        return `<option value="${escape(value || "")}" ${selected}>${escape(label || "")}</option>`;
    }).join("");
}

function getLedgerState(rows, ledger) {
    const query = (ledger.query || "").trim().toLowerCase();
    const filtered = rows.filter((row) => {
        if (ledger.status && row.status !== ledger.status) return false;
        if (ledger.payout && row.payout_state !== ledger.payout) return false;
        if (!query) return true;
        return [row.name, row.agent, row.customer, row.sales_order, row.sales_invoice]
            .filter(Boolean)
            .some((value) => String(value).toLowerCase().includes(query));
    });
    const pageSize = Number(ledger.pageSize || 4);
    const total = filtered.length;
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    const page = Math.min(Math.max(1, Number(ledger.page || 1)), totalPages);
    const startIndex = (page - 1) * pageSize;
    const pageRows = filtered.slice(startIndex, startIndex + pageSize);
    return {
        rows: pageRows,
        total,
        totalPages,
        page,
        start: total ? startIndex + 1 : 0,
        end: total ? startIndex + pageRows.length : 0,
    };
}

function uniqueValues(rows, fieldname) {
    return [...new Set(rows.map((row) => row[fieldname]).filter(Boolean))];
}

function statusPill(value) {
    const tone = {
        Approved: "info",
        "To Pay": "warn",
        Paid: "success",
        Unpaid: "neutral",
    }[value] || "neutral";
    return `<span class="cdb-pill cdb-pill--${tone}">${escape(value)}</span>`;
}

function getWorkflowHelpText(status) {
    if (status === "Approved") return __("SO confirmed");
    if (status === "To Pay") return __("Order paid");
    if (status === "Paid") return __("Commission paid");
    return "";
}

function docLink(route, name) {
    return `<a href="/app/${route}/${encodeURIComponent(name || "")}" class="cdb-link">${escape(name || "")}</a>`;
}

function shortcutCard(icon, label, url, variant) {
    return `
        <button class="cdb-shortcut cdb-shortcut--${variant || "default"}" data-url="${escape(url)}" type="button">
            <span class="cdb-shortcut-icon">${CDB_ICON[icon] || ""}</span>
            <span class="cdb-shortcut-label">${escape(label)}</span>
        </button>
    `;
}

function emptyState(message) {
    return `<div class="cdb-empty">${escape(message)}</div>`;
}

function sum(rows, fieldname, predicate) {
    return rows.reduce((total, row) => total + (predicate && !predicate(row) ? 0 : Number(row[fieldname] || 0)), 0);
}

function sumMax(rows, fieldname) {
    return rows.reduce((total, row) => total + Number(row[fieldname] || 0), 0);
}

function formatCurrency(value) {
    return frappe.format(value || 0, { fieldtype: "Currency" }, { only_value: true });
}

function escape(value) {
    return frappe.utils.escape_html(value == null ? "" : String(value));
}

function injectCommissionDashboardStyles() {
    if (document.getElementById("cdb-styles")) return;

    const style = document.createElement("style");
    style.id = "cdb-styles";
    style.textContent = `
        .cdb-root { background: linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%); min-height: calc(100vh - 88px); }
        .cdb-wrapper, .layout-main-section { background: transparent; }
        .cdb-shell { max-width: 1320px; margin: 0 auto; padding: 24px; display: grid; gap: 20px; }
        .cdb-hero, .cdb-card, .cdb-shortcut, .cdb-kpi, .cdb-filters { background: rgba(255,255,255,0.88); border: 1px solid rgba(148,163,184,0.16); box-shadow: 0 18px 50px rgba(15,23,42,0.08); }
        .cdb-hero { border-radius: 24px; padding: 28px; display: flex; justify-content: space-between; gap: 24px; }
        .cdb-hero-eyebrow { font-size: 12px; letter-spacing: .12em; text-transform: uppercase; color: #64748b; margin-bottom: 6px; }
        .cdb-hero-greeting { font-size: 32px; font-weight: 700; color: #0f172a; }
        .cdb-hero-sub { color: #475569; margin-top: 6px; max-width: 720px; }
        .cdb-hero-right { display: flex; align-items: center; gap: 18px; }
        .cdb-hero-divider { width: 1px; align-self: stretch; background: rgba(148,163,184,0.2); }
        .cdb-hero-stat { min-width: 120px; }
        .cdb-hero-stat-val { font-size: 28px; font-weight: 700; color: #111827; text-align: center; }
        .cdb-hero-stat-val--warn { color: #c2410c; }
        .cdb-hero-stat-label { font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: .08em; text-align: center; }
        .cdb-shortcuts-grid, .cdb-kpis { display: grid; gap: 14px; }
        .cdb-shortcuts-grid { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
        .cdb-shortcut { border-radius: 18px; padding: 18px; display: flex; align-items: center; gap: 12px; cursor: pointer; transition: transform .16s ease, box-shadow .16s ease; }
        .cdb-shortcut:hover { transform: translateY(-2px); box-shadow: 0 24px 60px rgba(15,23,42,0.12); }
        .cdb-shortcut--primary { background: linear-gradient(135deg, #4338ca, #3730a3); color: #fff; }
        .cdb-shortcut-icon svg, .cdb-kpi-icon svg { width: 20px; height: 20px; }
        .cdb-shortcut-label { font-weight: 600; }
        .cdb-filters { border-radius: 18px; padding: 14px; display: grid; grid-template-columns: repeat(3, minmax(0, 220px)); gap: 12px; }
        .cdb-filters label { display: grid; gap: 6px; font-size: 12px; font-weight: 700; color: #475569; }
        .cdb-filters select, .cdb-control-grid input, .cdb-control-grid textarea { border: 1px solid #cbd5e1; border-radius: 10px; background: #fff; min-height: 38px; padding: 8px 10px; font-size: 13px; color: #0f172a; width: 100%; }
        .cdb-control-grid textarea { min-height: 84px; resize: vertical; }
        .cdb-kpis { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
        .cdb-kpi { border-radius: 18px; padding: 18px; }
        .cdb-kpi-top { margin-bottom: 12px; color: #475569; }
        .cdb-kpi-value { font-size: 28px; font-weight: 700; color: #0f172a; }
        .cdb-kpi-label { margin-top: 4px; font-weight: 600; color: #1e293b; }
        .cdb-kpi-sub { margin-top: 6px; font-size: 12px; color: #64748b; }
        .cdb-grid { display: grid; grid-template-columns: 1.2fr .8fr; gap: 18px; }
        .cdb-side { display: grid; gap: 18px; }
        .cdb-card { border-radius: 22px; overflow: hidden; }
        .cdb-card-head { padding: 18px 20px 12px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
        .cdb-card-head h2 { margin: 0; font-size: 18px; color: #0f172a; }
        .cdb-caption { color: #64748b; font-size: 12px; margin-top: 4px; }
        .cdb-table-wrap { overflow: auto; }
        .cdb-table { width: 100%; border-collapse: collapse; font-size: 12px; }
        .cdb-table th, .cdb-table td { padding: 12px 14px; border-top: 1px solid rgba(226,232,240,0.85); text-align: left; white-space: nowrap; }
        .cdb-table th { font-size: 11px; letter-spacing: .06em; text-transform: uppercase; color: #64748b; background: #f8fafc; position: sticky; top: 0; z-index: 1; }
        .cdb-table tbody tr:hover { background: #fafcff; }
        .cdb-row-strong { font-weight: 700; color: #0f172a; }
        .cdb-pill { display: inline-flex; align-items: center; padding: 4px 9px; border-radius: 999px; font-size: 11px; font-weight: 700; }
        .cdb-pill--success { background: #dcfce7; color: #166534; }
        .cdb-pill--warn { background: #fef3c7; color: #92400e; }
        .cdb-pill--danger { background: #fee2e2; color: #991b1b; }
        .cdb-pill--info { background: #dbeafe; color: #1d4ed8; }
        .cdb-pill--neutral { background: #e2e8f0; color: #334155; }
        .cdb-alert { margin: 0 14px 14px; padding: 14px; border-radius: 16px; border: 1px solid rgba(226,232,240,0.9); background: rgba(248,250,252,0.95); }
        .cdb-alert--danger { border-left: 4px solid #dc2626; }
        .cdb-alert--warn { border-left: 4px solid #f59e0b; }
        .cdb-alert--info { border-left: 4px solid #3b82f6; }
        .cdb-alert-title { font-weight: 700; color: #0f172a; }
        .cdb-alert-body { margin-top: 4px; color: #475569; font-size: 12px; }
        .cdb-ledger-tools { padding: 0 20px 14px; }
        .cdb-ledger-status-guide { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 12px; color: #475569; font-size: 12px; }
        .cdb-ledger-toolbar { display: grid; grid-template-columns: minmax(260px, 1.2fr) repeat(2, minmax(180px, .5fr)); gap: 12px; }
        .cdb-ledger-toolbar label { display: grid; gap: 6px; font-size: 12px; font-weight: 700; color: #475569; }
        .cdb-ledger-toolbar input, .cdb-ledger-toolbar select, .cdb-inline-select, .cdb-inline-input, .cdb-drawer-form input, .cdb-drawer-form select, .cdb-drawer-form textarea { border: 1px solid #cbd5e1; border-radius: 10px; background: #fff; min-height: 36px; padding: 0 10px; font-size: 13px; color: #0f172a; width: 100%; }
        .cdb-drawer-form textarea { min-height: 110px; padding: 10px; resize: vertical; }
        .cdb-inline-input { min-width: 140px; }
        .cdb-state-cell { display: grid; gap: 8px; min-width: 132px; }
        .cdb-state-help { font-size: 11px; color: #64748b; }
        .cdb-inline-select { min-width: 132px; }
        .cdb-action-stack { display: flex; align-items: center; gap: 8px; min-width: 44px; justify-content: center; }
        .cdb-action-stack--menu-only { width: 100%; }
        .cdb-inline-action { border: 1px solid #cbd5e1; background: #fff; color: #4338ca; cursor: pointer; padding: 8px 12px; border-radius: 10px; font-weight: 700; font-size: 12px; text-align: center; }
        .cdb-inline-action--primary { background: linear-gradient(135deg, #4338ca, #3730a3); color: #fff; border-color: transparent; }
        .cdb-inline-action--ghost { color: #475569; }
        .cdb-ref-text { font-weight: 600; color: #334155; }
        .cdb-row-menu-wrap { position: relative; }
        .cdb-row-menu-btn { border: 1px solid #cbd5e1; background: #fff; color: #475569; width: 36px; height: 36px; border-radius: 10px; cursor: pointer; font-weight: 800; letter-spacing: .08em; }
        .cdb-row-menu { position: absolute; right: 0; top: calc(100% + 6px); min-width: 210px; background: #fff; border: 1px solid rgba(203,213,225,.95); border-radius: 14px; box-shadow: 0 24px 60px rgba(15,23,42,.16); padding: 8px; display: grid; z-index: 3; }
        .cdb-row-menu button, .cdb-row-menu a { border: 0; background: transparent; text-align: left; padding: 9px 10px; border-radius: 10px; color: #0f172a; font-size: 13px; text-decoration: none; cursor: pointer; }
        .cdb-row-menu button:hover, .cdb-row-menu a:hover { background: #f8fafc; }
        .cdb-drawer-backdrop { position: fixed; inset: 0; background: rgba(15,23,42,.26); z-index: 20; }
        .cdb-drawer { position: fixed; top: 0; right: 0; width: min(460px, 100vw); height: 100vh; background: #fff; box-shadow: -24px 0 60px rgba(15,23,42,.18); z-index: 21; display: grid; grid-template-rows: auto 1fr; }
        .cdb-drawer-head { padding: 22px 22px 16px; border-bottom: 1px solid rgba(226,232,240,.9); display: flex; justify-content: space-between; gap: 12px; align-items: start; }
        .cdb-drawer-eyebrow { font-size: 11px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; color: #64748b; }
        .cdb-drawer-head h3 { margin: 6px 0 4px; font-size: 22px; color: #0f172a; }
        .cdb-drawer-sub { color: #64748b; font-size: 13px; }
        .cdb-drawer-close { border: 1px solid #cbd5e1; background: #fff; color: #334155; min-height: 36px; padding: 0 12px; border-radius: 10px; cursor: pointer; font-weight: 700; }
        .cdb-drawer-body { padding: 18px 22px 22px; overflow: auto; display: grid; gap: 16px; }
        .cdb-drawer-stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
        .cdb-mini-stat { padding: 12px; border-radius: 14px; background: rgba(248,250,252,0.95); border: 1px solid rgba(148,163,184,0.16); }
        .cdb-mini-stat span { display: block; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: #64748b; margin-bottom: 6px; }
        .cdb-mini-stat strong { color: #0f172a; }
        .cdb-drawer-form { display: grid; gap: 12px; }
        .cdb-drawer-form label { display: grid; gap: 6px; font-size: 12px; font-weight: 700; color: #475569; }
        .cdb-ledger-footer { padding: 14px 20px 20px; display: flex; justify-content: space-between; align-items: center; gap: 12px; border-top: 1px solid rgba(226,232,240,0.85); }
        .cdb-pagination-meta { color: #64748b; font-size: 12px; }
        .cdb-pagination-pages { display: flex; gap: 8px; flex-wrap: wrap; }
        .cdb-page-btn { border: 1px solid #cbd5e1; background: #fff; color: #334155; min-width: 34px; height: 34px; border-radius: 10px; cursor: pointer; font-weight: 700; }
        .cdb-page-btn.is-active { background: linear-gradient(135deg, #4338ca, #3730a3); color: #fff; border-color: transparent; }
        .cdb-empty { padding: 28px 18px; text-align: center; color: #64748b; }
        .cdb-link { color: #4338ca; font-weight: 600; text-decoration: none; }
        .cdb-link:hover, .cdb-inline-action:hover { text-decoration: underline; }
        .cdb-muted { color: #94a3b8; }
        @media (max-width: 980px) {
            .cdb-hero, .cdb-hero-right, .cdb-grid { flex-direction: column; grid-template-columns: 1fr; align-items: flex-start; }
            .cdb-hero-right { width: 100%; }
            .cdb-hero-divider { display: none; }
        }
        @media (max-width: 760px) {
            .cdb-shell { padding: 12px; }
            .cdb-filters, .cdb-ledger-toolbar { grid-template-columns: 1fr; }
            .cdb-ledger-status-guide { flex-direction: column; gap: 8px; }
            .cdb-ledger-footer { flex-direction: column; align-items: stretch; }
            .cdb-drawer-stats { grid-template-columns: 1fr; }
        }
    `;
    document.head.appendChild(style);
}
