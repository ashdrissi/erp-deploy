// ─── Stock & Warehouses Dashboard ─────────────────────────────────────────────
// Premium landing page for inventory control.
// Sections: hero + warehouse cards · KPI strip · critical stock list ·
//           rotation by category · live alerts · recent transfers · reorder queue
// ─────────────────────────────────────────────────────────────────────────────

frappe.pages["stock-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Stock & Warehouses"),
        single_column: true,
    });

    page.main.addClass("sdb-root");
    injectStyles();
    renderSkeleton(page);
    loadData(page);

    // Refresh button in page header
    page.add_action_item(__("Refresh"), () => {
        loadData(page);
        frappe.show_alert({ message: __("Refreshed"), indicator: "green" });
    });
};

// ─── SVG icons ───────────────────────────────────────────────────────────────

const IC = {
    warehouse: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M2 8l8-5 8 5v9a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V8z"/><rect x="7" y="11" width="6" height="7"/></svg>`,
    box: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M17 4L10 2 3 4v8l7 4 7-4V4z"/><line x1="10" y1="2" x2="10" y2="14"/><line x1="3" y1="7" x2="17" y2="7"/></svg>`,
    receipt: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v14l4-2 2 2 2-2 4 2V4a2 2 0 0 0-2-2z"/><polyline points="7,10 9,12 13,8"/></svg>`,
    alert: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2L2 17h16L10 2z"/><line x1="10" y1="9" x2="10" y2="12"/><circle cx="10" cy="14.5" r=".7" fill="currentColor" stroke="none"/></svg>`,
    trend: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><polyline points="3,15 8,9 12,12 17,5"/><polyline points="13,5 17,5 17,9"/></svg>`,
    transit: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="7" width="14" height="9" rx="1"/><path d="M15 10h2l2 3v3h-4V10z"/><circle cx="5" cy="18" r="1.5" fill="currentColor" stroke="none"/><circle cx="15" cy="18" r="1.5" fill="currentColor" stroke="none"/></svg>`,
    transfer: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="7" x2="16" y2="7"/><polyline points="11,3 16,7 11,11"/><line x1="16" y1="13" x2="4" y2="13"/><polyline points="9,9 4,13 9,17"/></svg>`,
    rotate: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M16.5 3.5A8 8 0 1 1 3.5 16.5"/><polyline points="16.5,3.5 16.5,8 12,8"/></svg>`,
    check: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="4,10 8,14 16,6"/></svg>`,
    arrow: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="10" x2="16" y2="10"/><polyline points="11,5 16,10 11,15"/></svg>`,
    cart: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M2 2h2l2.4 10.4A2 2 0 1 0 8 15h9a2 2 0 1 0 0-4H7L5 2H2z"/><circle cx="8" cy="17" r="1.2" fill="currentColor" stroke="none"/><circle cx="16" cy="17" r="1.2" fill="currentColor" stroke="none"/></svg>`,
    new: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><line x1="10" y1="4" x2="10" y2="16"/><line x1="4" y1="10" x2="16" y2="10"/></svg>`,
    list: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><line x1="3" y1="6" x2="17" y2="6"/><line x1="3" y1="10" x2="17" y2="10"/><line x1="3" y1="14" x2="13" y2="14"/></svg>`,
    clock: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="10" cy="10" r="8"/><polyline points="10,5 10,10 13,13"/></svg>`,
};

const SDB_STATE = {
    context: {},
    warehouses: [],
    itemGroups: [],
    stockRows: [],
    stockStart: 0,
    stockLimit: 80,
    stockHasMore: false,
    stockLoading: false,
    stockFilters: {
        search: "",
        warehouse: "",
        item_group: "",
        stock_status: "in_stock",
        sort_by: "actual_qty",
        sort_dir: "desc",
    },
};

let stockSearchTimer = null;

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function renderSkeleton(page) {
    page.main.html(`
        <div class="sdb-wrap">
            <nav class="sdb-breadcrumb" aria-label="${__("Breadcrumb")}">
                <a href="/desk/home-page?sidebar=Main+Dashboard">${__("Operations")}</a>
                <span class="sep">/</span>
                <a href="/desk/home-page?sidebar=Main+Dashboard">${__("Warehouse & Stock")}</a>
                <span class="sep">/</span>
                <span class="current">${__("Stock Dashboard")}</span>
            </nav>

            <!-- header row -->
            <div class="sdb-header">
                <div class="sdb-header-left">
                    <div class="sdb-title-row">
                        <div class="sdb-eyebrow"><span>${IC.warehouse}</span>${__("Inventory Control")}</div>
                        <h1 class="sdb-title">${__("Stock & Warehouses")}</h1>
                    </div>
                    <div class="sdb-subtitle" id="sdb-subtitle">${__("Loading…")}</div>
                </div>
                <div class="sdb-header-actions">
                    ${hdrBtn("receipt", __("New Purchase Receipt"), "new-purchase-receipt", "ghost")}
                    ${hdrBtn("cart", __("New Delivery Note"), "new-delivery-note", "ghost")}
                    ${hdrBtn("new", __("New Stock Entry"), "new-stock-entry", "primary")}
                </div>
            </div>

            <!-- warehouse cards -->
            <div class="sdb-wh-grid" id="sdb-wh-grid">
                ${[1, 2, 3, 4, 5].map(() => `<div class="sdb-wh-card sdb-shimmer-card"></div>`).join("")}
            </div>

            <!-- KPI strip -->
            <div class="sdb-kpi-strip" id="sdb-kpi-strip">
                ${[1, 2, 3, 4].map(() => `<div class="sdb-kpi sdb-shimmer-kpi"></div>`).join("")}
            </div>

            <!-- Shortcuts -->
            <div class="sdb-shortcuts">
                ${scut("warehouse", __("Warehouses"), "warehouses", "default")}
                ${scut("box", __("Items"), "items", "default")}
                ${scut("transfer", __("Stock Entries"), "transfers", "default")}
                ${scut("list", __("Stock Ledger (Moves)"), "stock-ledger", "default")}
            </div>

            <div class="sdb-card sdb-stock-card">
                <div class="sdb-card-hd sdb-stock-hd">
                    <div>
                        <div class="sdb-card-title">${IC.box} ${__("Stock Balance")}</div>
                    </div>
                    <div class="sdb-stock-head-actions">
                        <button class="sdb-hdr-btn sdb-hdr-btn--ghost" type="button" data-stock-reset>${__("Reset")}</button>
                        <button class="sdb-hdr-btn sdb-hdr-btn--ghost" type="button" data-stock-refresh>${__("Refresh")}</button>
                    </div>
                </div>
                <div class="sdb-stock-tools">
                    <input class="sdb-stock-search" data-stock-search placeholder="${__("Search item code, name, or group")}">
                    <select class="sdb-stock-warehouse" data-stock-warehouse>
                        <option value="">${__("All warehouses")}</option>
                    </select>
                    <select class="sdb-stock-warehouse" data-stock-item-group>
                        <option value="">${__("All item groups")}</option>
                    </select>
                    <select class="sdb-stock-warehouse" data-stock-status>
                        <option value="in_stock">${__("In stock")}</option>
                        <option value="all">${__("All statuses")}</option>
                        <option value="low">${__("Low stock")}</option>
                        <option value="reserved">${__("Fully reserved")}</option>
                        <option value="out">${__("Out of stock")}</option>
                    </select>
                </div>
                <div id="sdb-stock-overview" class="sdb-table-wrap">
                    <div class="sdb-shimmer-block" style="height:260px;margin:16px;border-radius:8px;"></div>
                </div>
            </div>

            <div class="sdb-card sdb-plan-card">
                <div class="sdb-card-hd sdb-plan-hd">
                    <div>
                        <div class="sdb-card-title">${IC.clock} ${__("Confirmed Order Stock Planning")}</div>
                        <div class="sdb-plan-subtitle">${__("Incoming allocation, Pick List protection dates, and confirmed-order shortages.")}</div>
                    </div>
                    <div class="sdb-plan-actions">
                        <a class="sdb-hdr-btn sdb-hdr-btn--ghost" href="/app/stock-demand-plan">${__("Open Plans")}</a>
                        <a class="sdb-hdr-btn sdb-hdr-btn--ghost" data-plan-settings href="/app/stock-planning-settings-control">${__("Settings")}</a>
                        <button class="sdb-hdr-btn sdb-hdr-btn--primary" type="button" data-plan-run>${__("Run Planning")}</button>
                    </div>
                </div>
                <div id="sdb-plan-summary" class="sdb-plan-summary"></div>
                <div id="sdb-stock-planning" class="sdb-table-wrap">
                    <div class="sdb-shimmer-block" style="height:220px;margin:16px;border-radius:8px;"></div>
                </div>
            </div>

            <!-- Main 3-column grid -->
            <div class="sdb-main-grid">

                <!-- Col 1: Critical stock -->
                <div class="sdb-card">
                    <div class="sdb-card-hd">
                        <div class="sdb-card-title">${IC.alert} ${__("Critical Stock Levels")}</div>
                        <a href="#" class="sdb-viewall" data-stock-route="stock-balance">${__("View all")} ${IC.arrow}</a>
                    </div>
                    <div id="sdb-critical" class="sdb-critical-list">
                        <div class="sdb-shimmer-block" style="height:260px;margin:16px 16px;border-radius:8px;"></div>
                    </div>
                </div>

                <!-- Col 2: Rotation by category -->
                <div class="sdb-card">
                    <div class="sdb-card-hd">
                        <div class="sdb-card-title">${IC.rotate} ${__("Stock Rotation by Category")}</div>
                        <a href="/app/stock-analytics" class="sdb-viewall">${__("Details")} ${IC.arrow}</a>
                    </div>
                    <div id="sdb-rotation" class="sdb-rotation-list">
                        <div class="sdb-shimmer-block" style="height:260px;margin:16px;border-radius:8px;"></div>
                    </div>
                </div>

                <!-- Col 3: Live alerts -->
                <div class="sdb-card">
                    <div class="sdb-card-hd">
                        <div class="sdb-card-title">${IC.alert} ${__("Live Alerts")}</div>
                        <span class="sdb-badge-live" id="sdb-alert-count">—</span>
                    </div>
                    <div id="sdb-alerts" class="sdb-alerts-list">
                        <div class="sdb-shimmer-block" style="height:260px;margin:16px;border-radius:8px;"></div>
                    </div>
                </div>

            </div>

            <!-- Bottom 2-col -->
            <div class="sdb-bottom-grid">

                <!-- Transfers -->
                <div class="sdb-card">
                    <div class="sdb-card-hd">
                        <div class="sdb-card-title">${IC.transfer} ${__("Recent Transfers")}</div>
                        <a href="#" class="sdb-viewall" data-stock-route="transfers">${__("View all")} ${IC.arrow}</a>
                    </div>
                    <div id="sdb-transfers" class="sdb-table-wrap">
                        <div class="sdb-shimmer-block" style="height:200px;margin:16px;border-radius:8px;"></div>
                    </div>
                </div>

                <!-- Reorder queue -->
                <div class="sdb-card">
                    <div class="sdb-card-hd">
                        <div class="sdb-card-title">${IC.cart} ${__("Reorder Queue")}</div>
                        <span class="sdb-badge-urgent" id="sdb-reorder-count"></span>
                    </div>
                    <div id="sdb-reorder" class="sdb-reorder-list">
                        <div class="sdb-shimmer-block" style="height:200px;margin:16px;border-radius:8px;"></div>
                    </div>
                </div>

            </div>

            <div class="sdb-bottom-grid sdb-bottom-grid--phase1">

                <div class="sdb-card">
                    <div class="sdb-card-hd">
                        <div class="sdb-card-title">${IC.alert} ${__("Flagged Inventory")}</div>
                        <a href="/app/item" class="sdb-viewall">${__("Items")} ${IC.arrow}</a>
                    </div>
                    <div id="sdb-flagged" class="sdb-flagged-list">
                        <div class="sdb-shimmer-block" style="height:180px;margin:16px;border-radius:8px;"></div>
                    </div>
                </div>

                <div class="sdb-card">
                    <div class="sdb-card-hd">
                        <div class="sdb-card-title">${IC.receipt} ${__("QC Routing Receipts")}</div>
                        <a href="/app/purchase-receipt" class="sdb-viewall">${__("Receipts")} ${IC.arrow}</a>
                    </div>
                    <div id="sdb-qc-routing" class="sdb-qc-routing-list">
                        <div class="sdb-shimmer-block" style="height:180px;margin:16px;border-radius:8px;"></div>
                    </div>
                </div>

            </div>

        </div>
    `);

    // Wire header buttons
    page.main.find("[data-stock-route]").on("click", function (event) {
        event.preventDefault();
        routeStockTarget(page, $(this).data("stock-route"));
    });
}

function hdrBtn(icon, label, route, variant) {
    return `<button class="sdb-hdr-btn sdb-hdr-btn--${variant}" data-stock-route="${route}">
        <span class="sdb-btn-ico">${IC[icon]}</span>${frappe.utils.escape_html(label)}
    </button>`;
}
function scut(icon, label, route, variant) {
    return `<div class="sdb-scut sdb-scut--${variant}" data-stock-route="${route}">
        <span class="sdb-scut-ico">${IC[icon]}</span>
        <span class="sdb-scut-lbl">${frappe.utils.escape_html(label)}</span>
    </div>`;
}

function routeStockTarget(page, route) {
    if (route === "new-purchase-receipt") {
        frappe.new_doc("Purchase Receipt");
        return;
    }
    if (route === "new-delivery-note") {
        frappe.new_doc("Delivery Note");
        return;
    }
    if (route === "new-stock-entry") {
        frappe.new_doc("Stock Entry");
        return;
    }
    if (route === "warehouses") {
        frappe.set_route("List", "Warehouse");
        return;
    }
    if (route === "items") {
        frappe.set_route("List", "Item");
        return;
    }
    if (route === "transfers") {
        openStockEntryHistoryDialog({});
        return;
    }
    if (route === "stock-balance") {
        loadStockOverview(page, { reset: true });
        return;
    }
    if (route === "stock-ledger") {
        openMovementHistoryDialog({});
    }
}

// ─── Data loading ─────────────────────────────────────────────────────────────

async function loadData(page) {
    try {
        const res = await frappe.call({
            method: "orderlift.orderlift_logistics.page.stock_dashboard.stock_dashboard.get_dashboard_data",
            args: { filters: JSON.stringify({ company: getActiveCompany() || "" }) },
        });
        const d = res.message || {};
        SDB_STATE.context = d.context || {};
        SDB_STATE.warehouses = d.warehouses || [];
        SDB_STATE.itemGroups = d.item_groups || [];
        renderSubtitle(page, d);
        renderWarehouseCards(page, SDB_STATE.warehouses);
        renderKpis(page, d.kpis || {});
        populateStockFilters(page, SDB_STATE);
        wireStockOverviewFilters(page);
        SDB_STATE.stockRows = d.stock_overview || [];
        SDB_STATE.stockStart = SDB_STATE.stockRows.length;
        SDB_STATE.stockHasMore = SDB_STATE.stockRows.length >= 120;
        renderStockOverview(page, SDB_STATE.stockRows, { append: false });
        renderCriticalStock(page, d.critical_stock || []);
        renderRotation(page, d.rotation_by_category || []);
        renderAlerts(page, d.alerts || []);
        renderTransfers(page, d.recent_transfers || []);
        renderReorderQueue(page, d.reorder_queue || []);
        renderFlaggedItems(page, d.flagged_items || []);
        renderQcRouting(page, d.qc_routing || []);
        renderStockPlanning(page, d.stock_planning || {});
    } catch (e) {
        console.warn("Stock Dashboard: failed to load data", e);
        frappe.show_alert({ message: __("Could not load dashboard data"), indicator: "red" });
    }
}

const STOCK_PLAN_TONES = {
    success: { cls: "sdb-plan-status--success" },
    info: { cls: "sdb-plan-status--info" },
    warn: { cls: "sdb-plan-status--warn" },
    error: { cls: "sdb-plan-status--error" },
    neutral: { cls: "sdb-plan-status--neutral" },
};

function renderStockPlanning(page, planning) {
    const context = SDB_STATE.context || {};
    const summary = planning.summary || {};
    const rows = planning.rows || [];
    const canManage = Boolean(context.can_manage_stock_planning);
    page.main.find("[data-plan-settings], [data-plan-run]").toggle(canManage);
    page.main.find("[data-plan-run]").off("click").on("click", async () => {
        try {
            await frappe.call({
                method: "orderlift.orderlift_logistics.stock_planning.recalculate_current_company",
                freeze: true,
                freeze_message: __("Recalculating confirmed demand and creating due Pick Lists..."),
            });
            frappe.show_alert({ message: __("Stock planning recalculated"), indicator: "green" });
            await loadData(page);
        } catch (error) {
            console.error("Stock planning recalculation failed", error);
        }
    });

    const summaryEl = page.main.find("#sdb-plan-summary");
    if (!planning.enabled) {
        summaryEl.html(`<div class="sdb-plan-disabled">${__("Stock planning is disabled for the active company. A Stock Manager can review the settings before activation.")}</div>`);
    } else {
        summaryEl.html([
            planMetric(__("Open Plans"), summary.total || 0, "neutral"),
            planMetric(__("Due"), summary.due || 0, (summary.due || 0) ? "warn" : "success"),
            planMetric(__("Waiting Incoming"), summary.waiting_incoming || 0, "info"),
            planMetric(__("Partial"), summary.partial || 0, (summary.partial || 0) ? "warn" : "neutral"),
            planMetric(__("Shortages"), summary.shortage || 0, (summary.shortage || 0) ? "error" : "success"),
            planMetric(__("Fully Reserved"), summary.fully_reserved || 0, "success"),
        ].join(""));
    }

    const el = page.main.find("#sdb-stock-planning");
    if (!rows.length) {
        el.html(`<div class="sdb-empty">${IC.check}<p>${planning.enabled ? __("No confirmed stock demand plans yet.") : __("Enable planning to create plans from submitted Sales Orders.")}</p></div>`);
        return;
    }
    el.html(`
        <table class="sdb-table sdb-plan-table">
            <thead><tr>
                <th>${__("ORDER / ITEM")}</th>
                <th>${__("DELIVERY")}</th>
                <th>${__("STATUS")}</th>
                <th class="sdb-num" title="${frappe.utils.escape_html(__("Confirmed demand quantity still to protect."))}">${__("DEMAND")}</th>
                <th class="sdb-num" title="${frappe.utils.escape_html(__("Incoming quantity safely allocated to this demand."))}">${__("INCOMING")}</th>
                <th class="sdb-num" title="${frappe.utils.escape_html(__("Quantity protected by Pick Lists (draft or submitted)."))}">${__("PICK LIST")}</th>
                <th class="sdb-num" title="${frappe.utils.escape_html(__("Demand not covered by physical stock, reservations, or safe incoming."))}">${__("SHORTAGE")}</th>
                <th>${__("NEXT ACTION")}</th>
            </tr></thead>
            <tbody>${rows.map(planRowMarkup).join("")}</tbody>
        </table>
        <div class="sdb-table-hint">${__("Hover a column header to see its definition.")}</div>
    `);
}

function planMetric(label, value, tone) {
    return `<div class="sdb-plan-metric sdb-plan-metric--${tone}"><span>${frappe.utils.escape_html(label)}</span><strong>${formatQty(value)}</strong></div>`;
}

function planRowMarkup(row) {
    const tone = STOCK_PLAN_TONES[row.tone] || STOCK_PLAN_TONES.neutral;
    const risk = row.risk_message ? `<small title="${frappe.utils.escape_html(row.risk_message)}">${frappe.utils.escape_html(row.risk_message)}</small>` : "";
    const pickLink = row.latest_pick_list
        ? `<a href="${frappe.utils.escape_html(row.pick_list_link || "#")}">${frappe.utils.escape_html(row.latest_pick_list)}</a>`
        : formatQty(row.pick_list_qty);
    return `<tr>
        <td><a class="sdb-tlink" href="${frappe.utils.escape_html(row.sales_order_link)}">${frappe.utils.escape_html(row.sales_order)}</a><small>${frappe.utils.escape_html(row.item_code)}${row.customer ? ` · ${frappe.utils.escape_html(row.customer)}` : ""}</small></td>
        <td class="sdb-nowrap">${planningDate(row.delivery_date)}</td>
        <td><span class="sdb-plan-status ${tone.cls}">${frappe.utils.escape_html(row.planning_status || __("Not Due"))}</span></td>
        <td class="sdb-num">${formatQty(row.required_qty)}</td>
        <td class="sdb-num">${formatQty(row.incoming_allocated_qty)}</td>
        <td class="sdb-num">${pickLink}</td>
        <td class="sdb-num ${Number(row.shortage_qty || 0) > 0 ? "sdb-qty-red" : ""}">${formatQty(row.shortage_qty)}</td>
        <td><a href="${frappe.utils.escape_html(row.plan_link)}">${planningDate(row.next_action_date) || __("View")}</a>${risk}</td>
    </tr>`;
}

function planningDate(value) {
    return value ? frappe.datetime.str_to_user(value) : "";
}

// ─── Subtitle ─────────────────────────────────────────────────────────────────

function renderSubtitle(page, data) {
    const wh_count = (data.warehouses || []).length;
    const items = (data.kpis || {}).total_units || 0;
    page.main.find("#sdb-subtitle").text(
        __("{0} · {1} warehouses · {2} active stock units · {3}",
            [(data.context || {}).company || __("No active company"), wh_count, items.toLocaleString(), frappe.datetime.now_time()])
    );
}

// ─── Warehouse cards ──────────────────────────────────────────────────────────

function renderWarehouseCards(page, warehouses) {
    const grid = page.main.find("#sdb-wh-grid");
    if (!warehouses.length) {
        grid.html(`<div class="sdb-empty-inline">${__("No warehouses configured.")}</div>`);
        return;
    }

    grid.html(warehouses.map(wh => {
        const statusClass = { ok: "sdb-wh--ok", warn: "sdb-wh--warn", alert: "sdb-wh--alert" }[wh.status] || "sdb-wh--ok";
        const statusLabel = { ok: "OK", warn: "WARN", alert: "ALERT" }[wh.status] || "OK";
        const barW = Math.min(wh.capacity_pct || 0, 100);

        return `
            <div class="sdb-wh-card ${statusClass}" data-wh="${frappe.utils.escape_html(wh.name)}" data-company="${frappe.utils.escape_html(wh.company || "")}">
                <div class="sdb-wh-top">
                    <div class="sdb-wh-icon">${IC.warehouse}</div>
                    <div class="sdb-wh-name">${frappe.utils.escape_html(wh.label || wh.name)}</div>
                    <span class="sdb-wh-status">${statusLabel}</span>
                </div>
                <div class="sdb-wh-stats">
                    <div class="sdb-wh-stat">
                        <div class="sdb-wh-val">${(wh.total_units || 0).toLocaleString()}</div>
                        <div class="sdb-wh-lbl">${__("Units")}</div>
                    </div>
                    <div class="sdb-wh-stat">
                        <div class="sdb-wh-val">${wh.capacity_pct || 0}%</div>
                        <div class="sdb-wh-lbl">${__("Stocked Item Coverage")}</div>
                    </div>
                    <div class="sdb-wh-stat">
                        <div class="sdb-wh-val ${wh.alerts > 0 ? "sdb-val-alert" : ""}">${wh.alerts || 0}</div>
                        <div class="sdb-wh-lbl">${__("Alerts")}</div>
                    </div>
                </div>
            </div>`;
    }).join(""));

    grid.find(".sdb-wh-card").on("click", function () {
        const wh = $(this).data("wh");
        if (!wh) return;
        page.main.find("[data-stock-warehouse]").val(wh);
        loadStockOverview(page, { reset: true });
    });
}

// ─── KPI strip ────────────────────────────────────────────────────────────────

function renderKpis(page, kpis) {
    const strip = page.main.find("#sdb-kpi-strip");
    const defs = [
        { icon: "box", label: __("Total Stock Units"), value: (kpis.total_units || 0).toLocaleString(), sub: __("across all warehouses"), badge: null },
        { icon: "alert", label: __("Stockout Alerts"), value: kpis.stockout_alerts ?? 0, sub: __("need immediate reorder"), badge: (kpis.stockout_alerts || 0) > 0 ? "error" : null },
        { icon: "box", label: __("Low Stock Items"), value: kpis.low_stock_items ?? 0, sub: __("below reorder threshold"), badge: (kpis.low_stock_items || 0) > 0 ? "warn" : null },
        { icon: "rotate", label: __("Avg Stock Rotation"), value: `${kpis.avg_rotation ?? "—"}x`, sub: __("last 90 days"), badge: null },
    ];

    strip.html(defs.map((d, i) => `
        <div class="sdb-kpi" style="animation-delay:${i * 70}ms">
            <div class="sdb-kpi-top">
                <span class="sdb-kpi-ico">${IC[d.icon]}</span>
                ${d.badge ? `<span class="sdb-kpi-badge sdb-kpi-badge--${d.badge}">${d.value > 0 ? "▲ " + d.value : ""}</span>` : ""}
            </div>
            <div class="sdb-kpi-val ${d.badge === "error" ? "sdb-kpi-val--error" : d.badge === "warn" ? "sdb-kpi-val--warn" : ""}">${d.value}</div>
            <div class="sdb-kpi-lbl">${d.label}</div>
            <div class="sdb-kpi-sub">${d.sub}</div>
        </div>
    `).join(""));

    strip.find(".sdb-kpi").each(function (i) {
        setTimeout(() => $(this).addClass("sdb-kpi--in"), i * 70);
    });
}

// ─── Stock overview ───────────────────────────────────────────────────────────

function getActiveCompany() {
    return window.orderlift && typeof window.orderlift.getActiveCompany === "function" ? window.orderlift.getActiveCompany() : "";
}

function populateStockFilters(page, state) {
    const select = page.main.find("[data-stock-warehouse]");
    const currentWarehouse = select.val() || "";
    const warehouseOptions = [`<option value="">${__("All warehouses")}</option>`].concat(
        (state.warehouses || []).map((wh) => {
            const name = wh.name || "";
            const label = wh.label || name;
            return `<option value="${frappe.utils.escape_html(name)}">${frappe.utils.escape_html(label)}</option>`;
        })
    );
    select.html(warehouseOptions.join(""));
    if (currentWarehouse) select.val(currentWarehouse);

    const itemGroupSelect = page.main.find("[data-stock-item-group]");
    const currentGroup = itemGroupSelect.val() || "";
    const groupOptions = [`<option value="">${__("All item groups")}</option>`].concat(
        (state.itemGroups || []).map((group) => `<option value="${frappe.utils.escape_html(group)}">${frappe.utils.escape_html(group)}</option>`)
    );
    itemGroupSelect.html(groupOptions.join(""));
    if (currentGroup) itemGroupSelect.val(currentGroup);

    page.main.find("[data-stock-status]").val(state.stockFilters.stock_status || "in_stock");
}

function wireStockOverviewFilters(page) {
    page.main.find("[data-stock-refresh]").off("click").on("click", () => loadStockOverview(page, { reset: true }));
    page.main.find("[data-stock-reset]").off("click").on("click", () => resetStockFilters(page));
    page.main.find("[data-stock-warehouse], [data-stock-item-group], [data-stock-status]").off("change").on("change", () => loadStockOverview(page, { reset: true }));
    page.main.find("[data-stock-search]").off("input keydown").on("input", function () {
        window.clearTimeout(stockSearchTimer);
        stockSearchTimer = window.setTimeout(() => {
            SDB_STATE.stockFilters.search = $(this).val() || "";
            loadStockOverview(page, { reset: true });
        }, 250);
    }).on("keydown", function (event) {
        if (event.key === "Enter") {
            window.clearTimeout(stockSearchTimer);
            SDB_STATE.stockFilters.search = $(this).val() || "";
            loadStockOverview(page, { reset: true });
        }
    });
}

function collectStockOverviewFilters(page) {
    return {
        company: SDB_STATE.context.company || getActiveCompany() || "",
        search: page.main.find("[data-stock-search]").val() || "",
        warehouse: page.main.find("[data-stock-warehouse]").val() || "",
        item_group: page.main.find("[data-stock-item-group]").val() || "",
        stock_status: page.main.find("[data-stock-status]").val() || "in_stock",
        sort_by: SDB_STATE.stockFilters.sort_by || "actual_qty",
        sort_dir: SDB_STATE.stockFilters.sort_dir || "desc",
        start: SDB_STATE.stockStart || 0,
        limit: SDB_STATE.stockLimit,
    };
}

function resetStockFilters(page) {
    SDB_STATE.stockFilters = {
        search: "",
        warehouse: "",
        item_group: "",
        stock_status: "in_stock",
        sort_by: "actual_qty",
        sort_dir: "desc",
    };
    page.main.find("[data-stock-search]").val("");
    page.main.find("[data-stock-warehouse]").val("");
    page.main.find("[data-stock-item-group]").val("");
    page.main.find("[data-stock-status]").val("in_stock");
    loadStockOverview(page, { reset: true });
}

async function loadStockOverview(page, options = {}) {
    const target = page.main.find("#sdb-stock-overview");
    if (!options.append) {
        target.html(`<div class="sdb-shimmer-block" style="height:220px;margin:16px;border-radius:8px;"></div>`);
        SDB_STATE.stockRows = [];
        SDB_STATE.stockStart = 0;
    }
    try {
        const res = await frappe.call({
            method: "orderlift.orderlift_logistics.page.stock_dashboard.stock_dashboard.get_stock_overview",
            args: collectStockOverviewFilters(page),
        });
        const payload = res.message || {};
        const rows = payload.rows || [];
        if (options.append) {
            SDB_STATE.stockRows = SDB_STATE.stockRows.concat(rows);
        } else {
            SDB_STATE.stockRows = rows;
        }
        SDB_STATE.stockStart = SDB_STATE.stockRows.length;
        SDB_STATE.stockHasMore = SDB_STATE.stockStart < (payload.total || SDB_STATE.stockRows.length);
        renderStockOverview(page, SDB_STATE.stockRows, { append: false });
    } catch (e) {
        console.warn("Stock Dashboard: failed to load stock overview", e);
        target.html(`<div class="sdb-empty">${IC.alert}<p>${__("Could not load item stock quantities.")}</p></div>`);
    }
}

function sortableStockHeader(label, field, numeric = false, title = "") {
    const active = SDB_STATE.stockFilters.sort_by === field;
    const direction = SDB_STATE.stockFilters.sort_dir || "desc";
    return `<th class="${numeric ? "sdb-num" : ""}"${title ? ` title="${frappe.utils.escape_html(title)}"` : ""}>
        <button type="button" class="sdb-sort-head ${active ? "is-active" : ""}" data-stock-sort-column="${field}">
            <span>${label}</span>
            <span class="sdb-sort-arrows" aria-hidden="true">
                <span class="${active && direction === "asc" ? "is-active" : ""}">&uarr;</span>
                <span class="${active && direction === "desc" ? "is-active" : ""}">&darr;</span>
            </span>
        </button>
    </th>`;
}

function applyStockColumnSort(page, field) {
    if (SDB_STATE.stockFilters.sort_by === field) {
        SDB_STATE.stockFilters.sort_dir = SDB_STATE.stockFilters.sort_dir === "asc" ? "desc" : "asc";
    } else {
        SDB_STATE.stockFilters.sort_by = field;
        SDB_STATE.stockFilters.sort_dir = ["item_code", "item_name"].includes(field) ? "asc" : "desc";
    }
    loadStockOverview(page, { reset: true });
}

function renderStockOverview(page, rows, options = {}) {
    const el = page.main.find("#sdb-stock-overview");
    if (!rows.length) {
        el.html(`<div class="sdb-empty">${IC.box}<p>${__("No stocked items matched these filters.")}</p></div>`);
        return;
    }

    el.html(`
        <table class="sdb-table sdb-stock-table">
            <thead><tr>
                ${sortableStockHeader(__("Item"), "item_name", false, __("Item code, name, and group."))}
                ${sortableStockHeader(__("On Hand"), "actual_qty", true, __("Current physical quantity in the warehouses (Bin)."))}
                ${sortableStockHeader(__("Available After SO"), "available_qty", true, __("On Hand minus Open SO Qty: what remains for new demand."))}
                ${sortableStockHeader(__("Open SO Qty"), "reserved_qty", true, __("Open confirmed demand from submitted Sales Orders (Technical List quantities when a submitted revision exists)."))}
                ${sortableStockHeader(__("To Reserve"), "to_be_reserved", true, __("What the planner would reserve today, computed from the current Stock Planning Settings."))}
                ${sortableStockHeader(__("Usable Incoming"), "usable_incoming", true, __("Safely dated incoming Purchase Order quantity, based on the current Stock Planning Settings."))}
                ${sortableStockHeader(__("Projected Available"), "projected_available", true, __("On Hand minus To Reserve plus Usable Incoming."))}
                ${sortableStockHeader(__("Shortage"), "shortage", true, __("Open demand not covered by reservation or usable incoming."))}
                ${sortableStockHeader(__("Reserved Stock"), "physically_reserved_qty", true, __("Physically reserved quantity (submitted Pick Lists)."))}
                ${sortableStockHeader(__("Incoming"), "ordered_qty", true, __("Ordered quantity expected into stock from open Purchase Orders."))}
                ${sortableStockHeader(__("Incoming Date"), "incoming_date", false, __("Earliest pending Purchase Order date."))}
                ${sortableStockHeader(__("Earliest Delivery"), "earliest_delivery", false, __("Earliest delivery date of the open confirmed Sales Orders."))}
                ${sortableStockHeader(__("Open SOs"), "open_so_count", true, __("Distinct open confirmed Sales Orders for this item."))}
                ${sortableStockHeader(__("Lead Time"), "lead_time_days", true, __("Item procurement lead time in days."))}
                ${sortableStockHeader(__("Supplier"), "supplier", false, __("First Item Supplier."))}
                ${SDB_STATE.context.can_view_valuation ? sortableStockHeader(__("Value"), "stock_value", true, __("Total stock value at the warehouse valuation rate.")) : ""}
                ${sortableStockHeader(__("Warehouses"), "warehouse_count", false, __("Number of warehouses with non-zero stock for this item."))}
            </tr></thead>
            <tbody>${rows.map((row) => renderStockOverviewRow(row)).join("")}</tbody>
        </table>
        <div class="sdb-table-hint">${__("Hover a column header to see its definition.")}</div>
    `);

    el.find("[data-stock-sort-column]").on("click", function () {
        applyStockColumnSort(page, $(this).data("stock-sort-column"));
    });

    el.find(".sdb-stock-row").on("click", function (event) {
        if ($(event.target).is("a")) return;
        const item = $(this).data("item");
        const warehouse = page.main.find("[data-stock-warehouse]").val() || "";
        if (item) openItemDetailDialog(page, item, warehouse);
    });

    const loadMore = page.main.find("[data-stock-load-more]");
    if (SDB_STATE.stockHasMore && !loadMore.length) {
        el.after(`<div class="sdb-stock-footer"><button type="button" class="sdb-hdr-btn sdb-hdr-btn--ghost" data-stock-load-more>${__("Load more")}</button></div>`);
    }
    page.main.find(".sdb-stock-footer").toggle(SDB_STATE.stockHasMore);
    page.main.find("[data-stock-load-more]").off("click").on("click", () => {
        SDB_STATE.stockFilters.search = page.main.find("[data-stock-search]").val() || "";
        loadStockOverview(page, { append: true });
    });
}

function renderStockOverviewRow(row) {
    const statusClass = row.status === "out" ? "sdb-stock-status--out" : row.status === "reserved" ? "sdb-stock-status--reserved" : "sdb-stock-status--available";
    const warehouseSummary = row.warehouse_summary || __("No warehouse stock");
    const valueCell = SDB_STATE.context.can_view_valuation
        ? `<td class="sdb-num">${formatMoney(row.stock_value || ((row.actual_qty || 0) * (row.avg_valuation_rate || 0)))}</td>`
        : "";
    const toReserve = Number(row.to_be_reserved || 0);
    const shortage = Number(row.shortage || 0);
    return `
        <tr class="sdb-row sdb-stock-row" data-item="${frappe.utils.escape_html(row.item_code || "")}">
            <td>
                <div class="sdb-stock-item-name">${frappe.utils.escape_html(row.item_name || row.item_code || "")}</div>
                <div class="sdb-stock-item-code">
                    <a href="/app/item/${encodeURIComponent(row.item_code || "")}">${frappe.utils.escape_html(row.item_code || "")}</a>
                    ${row.item_group ? ` · ${frappe.utils.escape_html(row.item_group)}` : ""}
                </div>
            </td>
            <td class="sdb-num"><strong>${formatQty(row.actual_qty)}</strong> <span>${frappe.utils.escape_html(row.stock_uom || "")}</span></td>
            <td class="sdb-num"><span class="sdb-stock-status ${statusClass}">${formatQty(row.available_qty)}</span></td>
            <td class="sdb-num">${formatQty(row.sales_order_reserved_qty ?? row.reserved_qty)}</td>
            <td class="sdb-num ${toReserve > 0 ? "sdb-qty-amber" : ""}">${formatQty(row.to_be_reserved)}</td>
            <td class="sdb-num">${formatQty(row.usable_incoming)}</td>
            <td class="sdb-num"><strong>${formatQty(row.projected_available)}</strong></td>
            <td class="sdb-num ${shortage > 0 ? "sdb-qty-red" : ""}">${formatQty(row.shortage)}</td>
            <td class="sdb-num">${formatQty(row.physically_reserved_qty)}</td>
            <td class="sdb-num">${formatQty(row.ordered_qty)}</td>
            <td class="sdb-nowrap">${planningDate(row.incoming_date)}</td>
            <td class="sdb-nowrap">${planningDate(row.earliest_delivery)}</td>
            <td class="sdb-num">${row.open_so_count || 0}</td>
            <td class="sdb-num">${row.lead_time_days ? `${row.lead_time_days} ${__("d")}` : ""}</td>
            <td>${row.supplier ? frappe.utils.escape_html(row.supplier) : ""}</td>
            ${valueCell}
            <td>
                <div class="sdb-stock-wh-count">${row.warehouse_count || 0} ${__("warehouse(s)")}</div>
                <div class="sdb-stock-wh-summary" title="${frappe.utils.escape_html(warehouseSummary)}">${frappe.utils.escape_html(warehouseSummary)}</div>
            </td>
        </tr>
    `;
}

function formatQty(value) {
    const number = Number(value) || 0;
    return number.toLocaleString(undefined, { maximumFractionDigits: Number.isInteger(number) ? 0 : 2 });
}

function formatMoney(value) {
    const number = Number(value) || 0;
    return frappe.format ? frappe.format(number, { fieldtype: "Currency" }) : number.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function movementQtyMarkup(value) {
    const number = Number(value) || 0;
    const cls = number > 0 ? "is-in" : number < 0 ? "is-out" : "is-neutral";
    return `<span class="sdb-delta ${cls}">${number > 0 ? "+" : ""}${formatQty(number)}</span>`;
}

function entryStatusMarkup(status) {
    const config = STATUS_CFG[status] || STATUS_CFG.draft;
    return `<span class="sdb-status ${config.cls}">${config.label}</span>`;
}

function dialogHtml(title, bodyHtml, extraClasses = "") {
    const dialog = new frappe.ui.Dialog({
        title,
        size: "extra-large",
        fields: [{ fieldtype: "HTML", fieldname: "body" }],
        primary_action_label: __("Close"),
        primary_action: () => dialog.hide(),
    });
    dialog.show();
    if (extraClasses) dialog.$wrapper && dialog.$wrapper.addClass(extraClasses);
    dialog.fields_dict.body.$wrapper.html(bodyHtml);
    return dialog;
}

function statsMarkup(items) {
    return `<div class="sdb-modal-stats">${items.map((item) => `
        <div class="sdb-modal-stat"${item.help ? ` title="${frappe.utils.escape_html(item.help)}"` : ""}>
            <span>${frappe.utils.escape_html(item.label)}</span>
            <strong>${item.value}</strong>
        </div>
    `).join("")}</div>`;
}

function optionMarkup(value, label, selected) {
    return `<option value="${frappe.utils.escape_html(value)}" ${value === selected ? "selected" : ""}>${frappe.utils.escape_html(label)}</option>`;
}

function warehouseOptions(selected) {
    return [optionMarkup("", __("All warehouses"), selected)].concat(
        (SDB_STATE.warehouses || []).map((warehouse) => optionMarkup(warehouse.name || "", warehouse.label || warehouse.name || "", selected))
    ).join("");
}

async function openItemDetailDialog(page, itemCode, warehouse) {
    const dialog = dialogHtml(__("Loading item..."), `<div class="sdb-empty">${IC.box}<p>${__("Loading item details...")}</p></div>`, "sdb-modal");
    try {
        const res = await frappe.call({
            method: "orderlift.orderlift_logistics.page.stock_dashboard.stock_dashboard.get_item_stock_details",
            args: {
                item_code: itemCode,
                warehouse: warehouse || "",
                filters: JSON.stringify({ company: SDB_STATE.context.company || getActiveCompany() || "", warehouse: warehouse || "" }),
            },
            freeze: false,
        });
        const payload = res.message || {};
        renderItemDetailDialog(dialog, payload);
    } catch (error) {
        dialog.fields_dict.body.$wrapper.html(`<div class="sdb-empty"><p>${frappe.utils.escape_html(error.message || __("Could not load item details."))}</p></div>`);
    }
}

function renderItemDetailDialog(dialog, payload) {
    const item = payload.item || {};
    const summary = payload.summary || {};
    const rows = payload.warehouses || [];
    const movements = payload.movements || [];
    const canView = payload.context && payload.context.can_view_valuation;
    dialog.set_title(`${item.item_code || item.name || "Item"} · ${item.item_name || ""}`);
    dialog.fields_dict.body.$wrapper.html(`
        <div class="sdb-modal-shell">
            <div class="sdb-modal-identity">
                <div class="sdb-modal-identity-icon">${IC.box}</div>
                <div class="sdb-modal-identity-copy">
                    <strong>${frappe.utils.escape_html(item.item_name || item.item_code || item.name || "")}</strong>
                    <span>${frappe.utils.escape_html(item.item_code || item.name || "")}</span>
                </div>
                <div class="sdb-modal-tags">
                    <span>${frappe.utils.escape_html(item.item_group || __("No item group"))}</span>
                    <span>${frappe.utils.escape_html(item.stock_uom || __("No UOM"))}</span>
                    <span>${frappe.utils.escape_html((payload.context || {}).company || "")}</span>
                </div>
            </div>
            ${statsMarkup([
                { label: __("On hand"), value: formatQty(summary.actual_qty), help: __("Current physical quantity in the warehouses.") },
                { label: __("Available After SO"), value: formatQty(summary.available_qty), help: __("On hand minus open confirmed Sales Order demand.") },
                { label: __("Reserved SO"), value: formatQty(summary.sales_order_reserved_qty), help: __("Open confirmed demand from submitted Sales Orders.") },
                { label: __("Reserved stock"), value: formatQty(summary.physically_reserved_qty), help: __("Physically reserved quantity from submitted Pick Lists.") },
                { label: __("Incoming"), value: formatQty(summary.ordered_qty), help: __("Ordered quantity expected into stock.") },
                { label: __("Warehouses"), value: formatQty(summary.warehouse_count), help: __("Number of warehouses with non-zero stock.") },
                ...(canView ? [{ label: __("Stock value"), value: formatMoney(summary.stock_value || 0), help: __("Total stock value at the valuation rate.") }] : []),
            ])}
            <div class="sdb-modal-grid">
                <section class="sdb-modal-card">
                    <h4>${__("Warehouse Breakdown")}</h4>
                    ${rows.length ? `<table class="sdb-table sdb-modal-table"><thead><tr><th>${__("Warehouse")}</th><th class="sdb-num" title="${frappe.utils.escape_html(__("Current physical quantity in the warehouse."))}">${__("On hand")}</th><th class="sdb-num" title="${frappe.utils.escape_html(__("On hand minus open confirmed Sales Order demand for this warehouse."))}">${__("Available After SO")}</th><th class="sdb-num" title="${frappe.utils.escape_html(__("Open confirmed demand from submitted Sales Orders."))}">${__("Reserved SO")}</th><th class="sdb-num" title="${frappe.utils.escape_html(__("Ordered quantity expected into this warehouse."))}">${__("Incoming")}</th>${canView ? `<th class="sdb-num" title="${frappe.utils.escape_html(__("Stock value at the warehouse valuation rate."))}">${__("Value")}</th>` : ""}</tr></thead><tbody>${rows.map((row) => `<tr><td>${frappe.utils.escape_html(row.warehouse_name || row.warehouse || "")}</td><td class="sdb-num">${formatQty(row.actual_qty)}</td><td class="sdb-num">${formatQty(row.available_qty)}</td><td class="sdb-num">${formatQty(row.sales_order_reserved_qty)}</td><td class="sdb-num">${formatQty(row.ordered_qty)}</td>${canView ? `<td class="sdb-num">${formatMoney(row.stock_value || 0)}</td>` : ""}</tr>`).join("")}</tbody></table>` : `<div class="sdb-empty-inline">${__("No warehouse rows found.")}</div>`}
                </section>
                <section class="sdb-modal-card">
                    <div class="sdb-modal-card-head"><h4>${__("Recent Movements")}</h4><button type="button" class="sdb-hdr-btn sdb-hdr-btn--ghost" data-item-movements>${__("View all")}</button></div>
                    ${movements.length ? `<table class="sdb-table sdb-modal-table"><thead><tr><th>${__("Date")}</th><th>${__("Voucher")}</th><th>${__("Warehouse")}</th><th class="sdb-num">${__("Qty")}</th>${canView ? `<th class="sdb-num">${__("Value")}</th>` : ""}</tr></thead><tbody>${movements.map((row) => `<tr><td>${frappe.utils.escape_html((row.posting_date || "") + " " + (row.posting_time || ""))}</td><td><strong>${frappe.utils.escape_html(row.voucher_type || "")}</strong><br><small>${frappe.utils.escape_html(row.voucher_no || "")}</small></td><td>${frappe.utils.escape_html(row.warehouse || "")}</td><td class="sdb-num">${movementQtyMarkup(row.actual_qty)}</td>${canView ? `<td class="sdb-num">${formatMoney(row.stock_value_difference || 0)}</td>` : ""}</tr>`).join("")}</tbody></table>` : `<div class="sdb-empty-inline">${__("No movements found.")}</div>`}
                </section>
            </div>
        </div>
    `);
    dialog.fields_dict.body.$wrapper.find("[data-item-movements]").on("click", () => {
        openMovementHistoryDialog({ item_code: item.item_code || item.name || "" });
    });
}

function renderStockMovementDialog(dialog, payload, title) {
    const rows = payload.rows || [];
    const canView = payload.context && payload.context.can_view_valuation;
    const filters = dialog._sdbFilters || {};
    dialog.set_title(title);
    dialog.fields_dict.body.$wrapper.html(`
        <div class="sdb-modal-shell">
            <div class="sdb-modal-tools">
                <input type="date" data-move-from value="${frappe.utils.escape_html(filters.from_date || "")}" aria-label="${__("From date")}">
                <input type="date" data-move-to value="${frappe.utils.escape_html(filters.to_date || "")}" aria-label="${__("To date")}">
                <input data-move-search value="${frappe.utils.escape_html(filters.search || "")}" placeholder="${__("Item or voucher")}">
                <select data-move-warehouse>${warehouseOptions(filters.warehouse || "")}</select>
                <select data-move-voucher>
                    ${optionMarkup("", __("All movement types"), filters.voucher_type || "")}
                    ${["Purchase Receipt", "Delivery Note", "Stock Entry", "Stock Reconciliation", "Purchase Invoice"].map((value) => optionMarkup(value, __(value), filters.voucher_type || "")).join("")}
                </select>
                <select data-move-direction>
                    ${optionMarkup("", __("Incoming and outgoing"), filters.direction || "")}
                    ${optionMarkup("in", __("Incoming only"), filters.direction || "")}
                    ${optionMarkup("out", __("Outgoing only"), filters.direction || "")}
                </select>
                <select data-move-sort>
                    ${optionMarkup("newest", __("Newest first"), filters.sort || "newest")}
                    ${optionMarkup("oldest", __("Oldest first"), filters.sort || "newest")}
                </select>
                <button type="button" class="sdb-hdr-btn sdb-hdr-btn--primary" data-move-apply>${__("Apply")}</button>
            </div>
            ${statsMarkup([
                { label: __("Rows"), value: formatQty(rows.length) },
                ...(canView ? [{ label: __("Valuation visible"), value: __("Yes") }] : []),
            ])}
            <section class="sdb-modal-card">
                <h4>${__("Movement History")}</h4>
                ${rows.length ? `<table class="sdb-table sdb-modal-table"><thead><tr><th>${__("Date")}</th><th>${__("Item")}</th><th>${__("Voucher")}</th><th>${__("Warehouse")}</th><th class="sdb-num">${__("Qty")}</th><th class="sdb-num">${__("Balance")}</th>${canView ? `<th class="sdb-num">${__("Value")}</th>` : ""}</tr></thead><tbody>${rows.map((row) => `<tr><td>${frappe.utils.escape_html((row.posting_date || "") + " " + (row.posting_time || ""))}</td><td><strong>${frappe.utils.escape_html(row.item_code || "")}</strong><br><small>${frappe.utils.escape_html(row.item_name || "")}</small></td><td><strong>${frappe.utils.escape_html(row.voucher_type || "")}</strong><br><small>${frappe.utils.escape_html(row.voucher_no || "")}</small></td><td>${frappe.utils.escape_html(row.warehouse || "")}</td><td class="sdb-num">${movementQtyMarkup(row.actual_qty)}</td><td class="sdb-num">${formatQty(row.qty_after_transaction)}</td>${canView ? `<td class="sdb-num">${formatMoney(row.stock_value_difference || 0)}</td>` : ""}</tr>`).join("")}</tbody></table>` : `<div class="sdb-empty-inline">${__("No movements found.")}</div>`}
            </section>
        </div>
    `);
    dialog.fields_dict.body.$wrapper.find("[data-move-apply]").on("click", () => {
        const body = dialog.fields_dict.body.$wrapper;
        dialog._sdbFilters = {
            ...dialog._sdbFilters,
            from_date: body.find("[data-move-from]").val() || "",
            to_date: body.find("[data-move-to]").val() || "",
            search: body.find("[data-move-search]").val() || "",
            warehouse: body.find("[data-move-warehouse]").val() || "",
            voucher_type: body.find("[data-move-voucher]").val() || "",
            direction: body.find("[data-move-direction]").val() || "",
            sort: body.find("[data-move-sort]").val() || "newest",
        };
        loadMovementHistoryDialog(dialog);
    });
    return dialog;
}

async function openMovementHistoryDialog(extraFilters = {}) {
    const dialog = dialogHtml(__("Stock Movement History"), `<div class="sdb-empty">${IC.list}<p>${__("Loading movement history...")}</p></div>`, "sdb-modal");
    dialog._sdbFilters = {
        from_date: frappe.datetime.add_months(frappe.datetime.now_date(), -3),
        to_date: frappe.datetime.now_date(),
        sort: "newest",
        ...extraFilters,
    };
    await loadMovementHistoryDialog(dialog);
    return dialog;
}

async function loadMovementHistoryDialog(dialog) {
    try {
        dialog.fields_dict.body.$wrapper.html(`<div class="sdb-empty">${IC.list}<p>${__("Loading movement history...")}</p></div>`);
        const res = await frappe.call({
            method: "orderlift.orderlift_logistics.page.stock_dashboard.stock_dashboard.get_stock_movement_history",
            args: {
                filters: JSON.stringify({ company: SDB_STATE.context.company || getActiveCompany() || "", ...(dialog._sdbFilters || {}) }),
                limit: 120,
                start: 0,
            },
        });
        const payload = res.message || {};
        renderStockMovementDialog(dialog, payload, __("Stock Movement History"));
    } catch (error) {
        dialog.fields_dict.body.$wrapper.html(`<div class="sdb-empty"><p>${frappe.utils.escape_html(error.message || __("Could not load movement history."))}</p></div>`);
    }
}

async function openStockEntryHistoryDialog(extraFilters = {}) {
    const dialog = dialogHtml(__("Stock Entry History"), `<div class="sdb-empty">${IC.transfer}<p>${__("Loading stock entries...")}</p></div>`, "sdb-modal");
    dialog._sdbFilters = {
        from_date: frappe.datetime.add_months(frappe.datetime.now_date(), -3),
        to_date: frappe.datetime.now_date(),
        ...extraFilters,
    };
    await loadStockEntryHistoryDialog(dialog);
    return dialog;
}

async function loadStockEntryHistoryDialog(dialog) {
    try {
        dialog.fields_dict.body.$wrapper.html(`<div class="sdb-empty">${IC.transfer}<p>${__("Loading stock entries...")}</p></div>`);
        const res = await frappe.call({
            method: "orderlift.orderlift_logistics.page.stock_dashboard.stock_dashboard.get_stock_entry_history",
            args: {
                filters: JSON.stringify({ company: SDB_STATE.context.company || getActiveCompany() || "", ...(dialog._sdbFilters || {}) }),
                limit: 80,
                start: 0,
            },
        });
        const payload = res.message || {};
        const rows = payload.rows || [];
        const filters = dialog._sdbFilters || {};
        dialog.fields_dict.body.$wrapper.html(`
            <div class="sdb-modal-shell">
                <div class="sdb-modal-tools">
                    <input type="date" data-entry-from value="${frappe.utils.escape_html(filters.from_date || "")}" aria-label="${__("From date")}">
                    <input type="date" data-entry-to value="${frappe.utils.escape_html(filters.to_date || "")}" aria-label="${__("To date")}">
                    <input data-entry-search value="${frappe.utils.escape_html(filters.search || "")}" placeholder="${__("Entry number or type")}">
                    <select data-entry-warehouse>${warehouseOptions(filters.warehouse || "")}</select>
                    <select data-entry-type>
                        ${optionMarkup("", __("All entry types"), filters.stock_entry_type || "")}
                        ${["Material Transfer", "Material Receipt", "Material Issue", "Repack", "Manufacture"].map((value) => optionMarkup(value, __(value), filters.stock_entry_type || "")).join("")}
                    </select>
                    <select data-entry-status>
                        ${optionMarkup("", __("All statuses"), String(filters.docstatus ?? ""))}
                        ${optionMarkup("0", __("Draft"), String(filters.docstatus ?? ""))}
                        ${optionMarkup("1", __("Submitted"), String(filters.docstatus ?? ""))}
                        ${optionMarkup("2", __("Cancelled"), String(filters.docstatus ?? ""))}
                    </select>
                    <button type="button" class="sdb-hdr-btn sdb-hdr-btn--primary" data-entry-apply>${__("Apply")}</button>
                </div>
                ${statsMarkup([{ label: __("Rows"), value: formatQty(rows.length) }])}
                <section class="sdb-modal-card">
                    <h4>${__("Stock Entries")}</h4>
                    ${rows.length ? `<table class="sdb-table sdb-modal-table"><thead><tr><th>${__("Entry")}</th><th>${__("Type")}</th><th>${__("Date")}</th><th>${__("From → To")}</th><th class="sdb-num">${__("Qty")}</th><th>${__("Status")}</th></tr></thead><tbody>${rows.map((row) => `<tr class="sdb-entry-row" data-entry="${frappe.utils.escape_html(row.name)}"><td><strong>${frappe.utils.escape_html(row.name)}</strong></td><td>${frappe.utils.escape_html(row.stock_entry_type || row.purpose || "")}</td><td>${frappe.utils.escape_html(row.posting_date || "")}</td><td>${frappe.utils.escape_html((row.from_warehouse || "—") + " → " + (row.to_warehouse || "—"))}</td><td class="sdb-num">${formatQty(row.total_qty)}</td><td>${entryStatusMarkup(row.status)}</td></tr>`).join("")}</tbody></table>` : `<div class="sdb-empty-inline">${__("No stock entries found.")}</div>`}
                </section>
            </div>
        `);
        dialog.fields_dict.body.$wrapper.find(".sdb-entry-row").on("click", async function () {
            const entry = $(this).data("entry");
            if (entry) await openStockEntryDetailDialog(entry);
        });
        dialog.fields_dict.body.$wrapper.find("[data-entry-apply]").on("click", () => {
            const body = dialog.fields_dict.body.$wrapper;
            dialog._sdbFilters = {
                from_date: body.find("[data-entry-from]").val() || "",
                to_date: body.find("[data-entry-to]").val() || "",
                search: body.find("[data-entry-search]").val() || "",
                warehouse: body.find("[data-entry-warehouse]").val() || "",
                stock_entry_type: body.find("[data-entry-type]").val() || "",
                docstatus: body.find("[data-entry-status]").val(),
            };
            loadStockEntryHistoryDialog(dialog);
        });
    } catch (error) {
        dialog.fields_dict.body.$wrapper.html(`<div class="sdb-empty"><p>${frappe.utils.escape_html(error.message || __("Could not load stock entries."))}</p></div>`);
    }
}

async function openStockEntryDetailDialog(stockEntry) {
    const dialog = dialogHtml(stockEntry, `<div class="sdb-empty">${IC.transfer}<p>${__("Loading stock entry...")}</p></div>`, "sdb-modal");
    try {
        const res = await frappe.call({
            method: "orderlift.orderlift_logistics.page.stock_dashboard.stock_dashboard.get_stock_entry_details",
            args: { stock_entry: stockEntry },
        });
        const payload = res.message || {};
        const header = payload.header || {};
        const rows = payload.rows || [];
        const canView = payload.context && payload.context.can_view_valuation;
        dialog.set_title(`${header.name || stockEntry} · ${header.stock_entry_type || ""}`);
        dialog.fields_dict.body.$wrapper.html(`
            <div class="sdb-modal-shell">
                ${statsMarkup([
                    { label: __("Items"), value: formatQty(rows.length) },
                    { label: __("Qty"), value: formatQty(header.total_qty || 0) },
                    ...(canView ? [{ label: __("Value"), value: formatMoney(header.total_value || 0) }] : []),
                ])}
                <section class="sdb-modal-card">
                    <h4>${__("Entry Details")}</h4>
                    <div class="sdb-modal-meta">${frappe.utils.escape_html(header.stock_entry_type || "")} · ${frappe.utils.escape_html(header.posting_date || "")}</div>
                    ${rows.length ? `<table class="sdb-table sdb-modal-table"><thead><tr><th>${__("Item")}</th><th>${__("Source")}</th><th>${__("Target")}</th><th class="sdb-num">${__("Qty")}</th>${canView ? `<th class="sdb-num">${__("Rate")}</th><th class="sdb-num">${__("Amount")}</th>` : ""}</tr></thead><tbody>${rows.map((row) => `<tr><td>${frappe.utils.escape_html(row.item_code || "")}<br><small>${frappe.utils.escape_html(row.item_name || "")}</small></td><td>${frappe.utils.escape_html(row.s_warehouse || "")}</td><td>${frappe.utils.escape_html(row.t_warehouse || "")}</td><td class="sdb-num">${formatQty(row.transfer_qty || row.qty)}</td>${canView ? `<td class="sdb-num">${formatMoney(row.basic_rate || row.valuation_rate || 0)}</td><td class="sdb-num">${formatMoney(row.amount || 0)}</td>` : ""}</tr>`).join("")}</tbody></table>` : `<div class="sdb-empty-inline">${__("No rows available.")}</div>`}
                </section>
            </div>
        `);
    } catch (error) {
        dialog.fields_dict.body.$wrapper.html(`<div class="sdb-empty"><p>${frappe.utils.escape_html(error.message || __("Could not load stock entry detail."))}</p></div>`);
    }
    return dialog;
}

// ─── Critical stock ───────────────────────────────────────────────────────────

function renderCriticalStock(page, rows) {
    const el = page.main.find("#sdb-critical");
    if (!rows.length) {
        el.html(`<div class="sdb-empty">${IC.check}<p>${__("No critical stock items.")}</p></div>`);
        return;
    }

    el.html(`<div class="sdb-crit-list">${rows.map(r => {
        const barColor = r.status === "stockout" ? "sdb-bar--red" : r.status === "critical" ? "sdb-bar--amber" : "sdb-bar--yellow";
        const qtyClass = r.status === "stockout" ? "sdb-qty-red" : r.status === "critical" ? "sdb-qty-amber" : "";
        return `
            <div class="sdb-crit-row" title="${frappe.utils.escape_html(r.warehouse)}">
                <div class="sdb-crit-info">
                    <div class="sdb-crit-name">${frappe.utils.escape_html(r.item_name || r.item_code)}</div>
                    <div class="sdb-crit-code">${frappe.utils.escape_html(r.item_code)}</div>
                </div>
                <div class="sdb-crit-right">
                    <div class="sdb-crit-qty ${qtyClass}">${r.actual_qty} / ${r.reorder_level} <span class="sdb-crit-min">min</span></div>
                    <div class="sdb-bar-track sdb-bar-track--sm">
                        <div class="sdb-bar-fill ${barColor}" style="width:${r.pct}%"></div>
                    </div>
                </div>
            </div>`;
    }).join("")}</div>`);
}

// ─── Rotation by category ─────────────────────────────────────────────────────

const ROT_COLORS = { fast: "#10b981", normal: "#6366f1", slow: "#f59e0b", dead: "#f43f5e" };

function renderRotation(page, rows) {
    const el = page.main.find("#sdb-rotation");
    if (!rows.length) {
        el.html(`<div class="sdb-empty">${IC.rotate}<p>${__("No rotation data yet.")}</p></div>`);
        return;
    }
    const maxRot = Math.max(...rows.map(r => r.rotation), 1);

    el.html(`
        <div class="sdb-rot-list">
            ${rows.map(r => {
        const w = Math.max((r.rotation / maxRot) * 100, 4);
        const color = ROT_COLORS[r.speed] || "#6366f1";
        return `
                    <div class="sdb-rot-row">
                        <div class="sdb-rot-name">${frappe.utils.escape_html(r.category || "—")}</div>
                        <div class="sdb-rot-bar-wrap">
                            <div class="sdb-rot-bar" style="width:${w}%;background:${color}"></div>
                        </div>
                        <div class="sdb-rot-val">${r.rotation.toFixed(1)}x</div>
                    </div>`;
    }).join("")}
        </div>
        <div class="sdb-rot-legend">
            <span class="sdb-leg"><span class="sdb-leg-dot" style="background:#10b981"></span>${__("Fast (>6x)")}</span>
            <span class="sdb-leg"><span class="sdb-leg-dot" style="background:#6366f1"></span>${__("Normal (3–6x)")}</span>
            <span class="sdb-leg"><span class="sdb-leg-dot" style="background:#f59e0b"></span>${__("Slow (<3x)")}</span>
            <span class="sdb-leg"><span class="sdb-leg-dot" style="background:#f43f5e"></span>${__("Dead (<1x)")}</span>
        </div>
    `);
}

// ─── Live alerts ──────────────────────────────────────────────────────────────

function renderAlerts(page, alerts) {
    page.main.find("#sdb-alert-count").text(
        alerts.length ? `${alerts.length} ${__("active")}` : ""
    ).toggleClass("sdb-badge-live--red", alerts.length > 0);

    const el = page.main.find("#sdb-alerts");
    if (!alerts.length) {
        el.html(`<div class="sdb-empty">${IC.check}<p>${__("No active alerts.")}</p></div>`);
        return;
    }

    el.html(`<div class="sdb-alert-list">${alerts.map(a => `
        <div class="sdb-alert sdb-alert--${a.level || "warn"}">
            <div class="sdb-alert-hd">
                <span class="sdb-alert-ico">${IC.alert}</span>
                <strong>${frappe.utils.escape_html(a.title)}</strong>
            </div>
            <div class="sdb-alert-msg">${frappe.utils.escape_html(a.message)}</div>
            ${a.sub ? `<div class="sdb-alert-sub">${frappe.utils.escape_html(a.sub)}</div>` : ""}
            ${a.link ? `<a class="sdb-alert-lnk" href="${frappe.utils.escape_html(a.link)}">${IC.arrow}</a>` : ""}
        </div>
    `).join("")}</div>`);
}

// ─── Recent transfers ─────────────────────────────────────────────────────────

const STATUS_CFG = {
    draft: { label: __("Draft"), cls: "sdb-status--draft" },
    submitted: { label: __("Submitted"), cls: "sdb-status--submitted" },
    cancelled: { label: __("Cancelled"), cls: "sdb-status--cancelled" },
};

function renderTransfers(page, rows) {
    const el = page.main.find("#sdb-transfers");
    if (!rows.length) {
        el.html(`<div class="sdb-empty">${IC.transfer}<p>${__("No recent transfers.")}</p></div>`);
        return;
    }

    el.html(`
        <table class="sdb-table">
            <thead><tr>
                <th>${__("TRANSFER")}</th>
                <th>${__("FROM → TO")}</th>
                <th>${__("ITEMS")}</th>
                <th>${__("STATUS")}</th>
                <th>${__("DATE")}</th>
            </tr></thead>
            <tbody>${rows.map(r => {
        const cfg = STATUS_CFG[r.status] || STATUS_CFG.draft;
        const from = (r.from_warehouse || "").split(" - ")[0] || "—";
        const to = (r.to_warehouse || "").split(" - ")[0] || "—";
        return `
                    <tr class="sdb-row" data-stock-entry="${frappe.utils.escape_html(r.name)}">
                        <td><a class="sdb-tlink" href="/app/stock-entry/${encodeURIComponent(r.name)}">${frappe.utils.escape_html(r.name)}</a></td>
                        <td class="sdb-muted">${frappe.utils.escape_html(from)} → ${frappe.utils.escape_html(to)}</td>
                        <td><strong class="sdb-icount">${r.item_count} ${__("items")}</strong></td>
                        <td><span class="sdb-status ${cfg.cls}">${cfg.label}</span></td>
                        <td class="sdb-muted sdb-nowrap">${frappe.datetime.prettyDate(r.date)}</td>
                    </tr>`;
    }).join("")}</tbody>
        </table>
    `);

    el.find(".sdb-row").on("click", function (e) {
        if ($(e.target).is("a")) return;
        frappe.set_route("Form", "Stock Entry", $(this).data("stock-entry"));
    });
}

// ─── Reorder queue ────────────────────────────────────────────────────────────

function renderReorderQueue(page, rows) {
    page.main.find("#sdb-reorder-count").text(
        rows.length ? `${rows.length} ${__("urgent")}` : ""
    ).toggleClass("sdb-badge-urgent--red", rows.length > 0);

    const el = page.main.find("#sdb-reorder");
    if (!rows.length) {
        el.html(`<div class="sdb-empty">${IC.check}<p>${__("No items need reordering.")}</p></div>`);
        return;
    }

    el.html(`<div class="sdb-reorder-items">${rows.map(r => `
        <div class="sdb-reorder-item">
            <div class="sdb-reorder-info">
                <div class="sdb-reorder-name">${frappe.utils.escape_html(r.item_name || r.item_code)}</div>
                <div class="sdb-reorder-code">${frappe.utils.escape_html(r.item_code)} · ${frappe.utils.escape_html((r.warehouse || "").split(" - ")[0])}</div>
                <div class="sdb-reorder-meta">${r.supplier ? frappe.utils.escape_html(r.supplier) : __("No supplier configured")}</div>
            </div>
            <div class="sdb-reorder-right">
                <div class="sdb-reorder-qty ${r.stockout ? "sdb-qty-red" : "sdb-qty-amber"}">
                    ${r.actual_qty} / ${r.reorder_level}
                    ${r.stockout ? '<span class="sdb-reorder-tag sdb-reorder-tag--stockout">STOCKOUT</span>' : ""}
                </div>
                ${r.existing_po
                    ? `<a class="sdb-reorder-btn" href="/app/purchase-order/${encodeURIComponent(r.existing_po)}">${__("Open Draft PO")}</a>`
                    : r.supplier
                        ? `<a class="sdb-reorder-btn" href="/app/purchase-order/new-purchase-order-1">${__("Create PO")}</a>`
                        : `<span class="sdb-reorder-missing">${__("Missing Supplier")}</span>`}
            </div>
        </div>
    `).join("")}</div>`);
}

function renderFlaggedItems(page, rows) {
    const el = page.main.find("#sdb-flagged");
    if (!rows.length) {
        el.html(`<div class="sdb-empty">${IC.check}<p>${__("No items are currently flagged.")}</p></div>`);
        return;
    }

    el.html(`<div class="sdb-flagged-items">${rows.map(r => `
        <a class="sdb-flagged-item" href="/app/item/${encodeURIComponent(r.item_code)}">
            <div class="sdb-flagged-info">
                <div class="sdb-flagged-name">${frappe.utils.escape_html(r.item_name || r.item_code)}</div>
                <div class="sdb-flagged-code">${frappe.utils.escape_html(r.item_code)}${r.item_group ? ` · ${frappe.utils.escape_html(r.item_group)}` : ""}</div>
            </div>
            <span class="sdb-flag-pill sdb-flag-pill--${(r.flag || '').toLowerCase().replace(/\s+/g, '-')}">${frappe.utils.escape_html(r.flag || "")}</span>
        </a>
    `).join("")}</div>`);
}

function renderQcRouting(page, rows) {
    const el = page.main.find("#sdb-qc-routing");
    if (!rows.length) {
        el.html(`<div class="sdb-empty">${IC.receipt}<p>${__("No purchase receipts yet.")}</p></div>`);
        return;
    }

    el.html(`<div class="sdb-qc-items">${rows.map(r => `
        <a class="sdb-qc-item" href="/app/purchase-receipt/${encodeURIComponent(r.name)}">
            <div class="sdb-qc-info">
                <div class="sdb-qc-name">${frappe.utils.escape_html(r.name)}</div>
                <div class="sdb-qc-code">${frappe.utils.escape_html(r.supplier || __("No supplier"))}${r.warehouse ? ` · ${frappe.utils.escape_html(r.warehouse)}` : ""}</div>
            </div>
            <div class="sdb-qc-right">
                <span class="sdb-status ${r.qc_routed ? 'sdb-status--submitted' : 'sdb-status--draft'}">${r.qc_routed ? __("QC Routed") : __("Pending")}</span>
                <span class="sdb-qc-sub">${__("Transfers")}: ${r.transfer_count || 0}</span>
            </div>
        </a>
    `).join("")}</div>`);
}

// ─── Styles ───────────────────────────────────────────────────────────────────

function injectStyles() {
    if (document.getElementById("sdb-styles")) return;
    const s = document.createElement("style");
    s.id = "sdb-styles";
    s.textContent = `
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;450;500;600;700&family=Geist+Mono:wght@400;500&display=swap');
/* ── Root ── */
.sdb-root { background: var(--bg-color,#f4f6f9); }
.sdb-wrap { max-width: 1440px; margin: 0 auto; padding: 20px 28px 60px; }

/* ── Header ── */
.sdb-header { display:flex; align-items:flex-start; justify-content:space-between; flex-wrap:wrap; gap:16px; margin-bottom:20px; }
.sdb-eyebrow { font-size:11px; font-weight:700; letter-spacing:1.2px; color:#6366f1; text-transform:uppercase; margin-bottom:4px; }
.sdb-title   { font-size:28px; font-weight:800; color:var(--heading-color,#1a1f2e); line-height:1.1; }
.sdb-subtitle{ font-size:13px; color:var(--text-muted,#8c95a6); margin-top:4px; }

/* Header buttons */
.sdb-header-actions { display:flex; gap:10px; align-items:center; padding-top:4px; }
.sdb-hdr-btn {
    display:inline-flex; align-items:center; gap:7px;
    padding:9px 16px; border-radius:10px; font-size:13px; font-weight:600;
    cursor:pointer; border:1px solid; transition:all .15s;
}
.sdb-hdr-btn--ghost   { background:var(--card-bg,#fff); border-color:var(--border-color,#e2e8f0); color:var(--text-color,#334155); }
.sdb-hdr-btn--ghost:hover { border-color:#6366f1; color:#6366f1; }
.sdb-hdr-btn--primary { background:#6366f1; border-color:#6366f1; color:#fff; }
.sdb-hdr-btn--primary:hover { background:#4f46e5; }
.sdb-btn-ico { display:inline-flex; }
.sdb-btn-ico svg { width:15px; height:15px; }
.sdb-hdr-btn--ghost .sdb-btn-ico svg { stroke:var(--text-muted,#64748b); }
.sdb-hdr-btn--ghost:hover .sdb-btn-ico svg { stroke:#6366f1; }
.sdb-hdr-btn--primary .sdb-btn-ico svg { stroke:#fff; }

/* ── Warehouse cards ── */
.sdb-wh-grid {
    display:grid;
    grid-template-columns:repeat(auto-fill, minmax(200px,1fr));
    gap:12px; margin-bottom:16px;
}
.sdb-wh-card {
    background:var(--card-bg,#fff);
    border:1px solid var(--border-color,#e8ecf0);
    border-radius:14px; padding:16px;
    cursor:pointer; transition:box-shadow .15s, transform .15s;
}
.sdb-wh-card:hover { box-shadow:0 6px 20px rgba(0,0,0,.1); transform:translateY(-2px); }
.sdb-wh--ok    { border-top: 3px solid #10b981; }
.sdb-wh--warn  { border-top: 3px solid #f59e0b; }
.sdb-wh--alert { border-top: 3px solid #f43f5e; }
.sdb-wh-top { display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }
.sdb-wh-icon { display:inline-flex; }
.sdb-wh-icon svg { width:18px; height:18px; stroke:var(--text-muted,#64748b); }
.sdb-wh-status {
    font-size:10px; font-weight:800; letter-spacing:.8px;
    padding:2px 7px; border-radius:999px;
}
.sdb-wh--ok    .sdb-wh-status { background:#d1fae5; color:#065f46; }
.sdb-wh--warn  .sdb-wh-status { background:#fef3c7; color:#92400e; }
.sdb-wh--alert .sdb-wh-status { background:#fee2e2; color:#991b1b; }
.sdb-wh-name { font-size:13px; font-weight:700; color:var(--heading-color,#1a1f2e); margin-bottom:10px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.sdb-bar-track { height:5px; background:var(--bg-color,#f1f5f9); border-radius:99px; overflow:hidden; margin-bottom:10px; }
.sdb-bar-track--sm { height:4px; }
.sdb-bar-fill { height:100%; border-radius:99px; transition:width .4s ease; }
.sdb-bar--green { background:#10b981; }
.sdb-bar--amber { background:#f59e0b; }
.sdb-bar--red   { background:#f43f5e; }
.sdb-bar--yellow{ background:#eab308; }
.sdb-wh-stats { display:grid; grid-template-columns:repeat(3,1fr); gap:4px; }
.sdb-wh-stat { text-align:center; }
.sdb-wh-val { font-size:16px; font-weight:800; color:var(--heading-color,#1a1f2e); }
.sdb-val-alert { color:#f43f5e; }
.sdb-wh-lbl { font-size:9px; font-weight:700; letter-spacing:.6px; color:var(--text-muted,#94a3b8); }

/* Shimmer warehouse */
.sdb-shimmer-card {
    min-height:130px;
    background:linear-gradient(90deg,#f1f5f9 25%,#e8ecf2 37%,#f1f5f9 63%);
    background-size:400% 100%; animation:sdb-shimmer 1.4s infinite;
    border-radius:14px;
}

/* ── KPI strip ── */
.sdb-kpi-strip {
    display:grid; grid-template-columns:repeat(4,1fr);
    gap:12px; margin-bottom:16px;
}
@media(max-width:768px){.sdb-kpi-strip{grid-template-columns:repeat(2,1fr);}}
.sdb-kpi {
    background:var(--card-bg,#fff); border:1px solid var(--border-color,#e8ecf0);
    border-radius:12px; padding:18px;
    opacity:0; transform:translateY(10px);
    transition:opacity .3s,transform .3s;
}
.sdb-kpi--in   { opacity:1; transform:translateY(0); }
.sdb-shimmer-kpi {
    opacity:1; transform:none; min-height:110px; border-radius:12px;
    background:linear-gradient(90deg,#f1f5f9 25%,#e8ecf2 37%,#f1f5f9 63%);
    background-size:400% 100%; animation:sdb-shimmer 1.4s infinite;
}
.sdb-kpi-top  { display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }
.sdb-kpi-ico  { display:inline-flex; width:30px; height:30px; background:#f1f5f9; border-radius:8px; align-items:center; justify-content:center; }
.sdb-kpi-ico svg { width:15px; height:15px; stroke:#6366f1; }
.sdb-kpi-badge { font-size:11px; font-weight:700; padding:2px 7px; border-radius:999px; }
.sdb-kpi-badge--error { background:#fee2e2; color:#dc2626; }
.sdb-kpi-badge--warn  { background:#fef3c7; color:#d97706; }
.sdb-kpi-val  { font-size:30px; font-weight:800; color:var(--heading-color,#1a1f2e); line-height:1; margin-bottom:4px; }
.sdb-kpi-val--error { color:#dc2626; }
.sdb-kpi-val--warn  { color:#d97706; }
.sdb-kpi-lbl  { font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.5px; color:var(--text-muted,#64748b); margin-bottom:3px; }
.sdb-kpi-sub  { font-size:11.5px; color:var(--text-muted,#94a3b8); }

/* ── Shortcuts ── */
.sdb-shortcuts { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:20px; }
.sdb-scut {
    display:flex; align-items:center; gap:8px;
    background:var(--card-bg,#fff); border:1px solid var(--border-color,#e8ecf0);
    border-radius:10px; padding:10px 16px; cursor:pointer;
    font-size:12.5px; font-weight:600; color:var(--text-color,#334155);
    transition:border-color .15s, box-shadow .15s, transform .15s;
}
.sdb-scut:hover { border-color:#6366f1; box-shadow:0 4px 14px rgba(99,102,241,.15); transform:translateY(-1px); }
.sdb-scut-ico { display:inline-flex; }
.sdb-scut-ico svg { width:15px; height:15px; stroke:var(--text-muted,#64748b); }
.sdb-scut:hover .sdb-scut-ico svg { stroke:#6366f1; }

/* ── Stock overview ── */
.sdb-stock-card { margin-bottom:16px; }
.sdb-stock-hd { align-items:flex-start; gap:14px; }
.sdb-card-subtitle { color:var(--text-muted,#64748b); font-size:11.5px; margin-top:4px; max-width:70ch; }
.sdb-stock-tools { display:flex; align-items:center; gap:10px; flex-wrap:wrap; padding:12px 16px; border-bottom:1px solid var(--border-color,#f1f5f9); background:var(--subtle-bg,#f8fafc); }
.sdb-stock-search { min-width:260px; flex:1; }
.sdb-stock-search, .sdb-stock-warehouse { background:var(--card-bg,#fff); border:1px solid var(--border-color,#dbe3ec); border-radius:9px; color:var(--text-color,#334155); font-size:12.5px; min-height:36px; padding:7px 10px; }
.sdb-stock-warehouse { min-width:190px; }
.sdb-stock-check { align-items:center; color:var(--text-muted,#64748b); display:inline-flex; font-size:12px; font-weight:650; gap:6px; margin:0; white-space:nowrap; }
.sdb-stock-table td { vertical-align:top; }
.sdb-stock-table .sdb-num { text-align:right; white-space:nowrap; }
.sdb-stock-item-name { color:var(--heading-color,#1a1f2e); font-size:12.5px; font-weight:750; max-width:360px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.sdb-stock-item-code { color:var(--text-muted,#94a3b8); font-size:11px; margin-top:2px; }
.sdb-stock-item-code a { color:#6366f1; font-weight:750; text-decoration:none; }
.sdb-stock-status { border-radius:999px; display:inline-block; font-weight:800; min-width:56px; padding:3px 8px; text-align:center; }
.sdb-stock-status--available { background:#dcfce7; color:#166534; }
.sdb-stock-status--reserved { background:#fef3c7; color:#92400e; }
.sdb-stock-status--out { background:#fee2e2; color:#991b1b; }
.sdb-stock-wh-count { color:var(--text-color,#334155); font-size:12px; font-weight:750; }
.sdb-stock-wh-summary { color:var(--text-muted,#94a3b8); font-size:11px; max-width:420px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
@media(max-width:760px){.sdb-stock-hd{display:block}.sdb-stock-hd .sdb-viewall{margin-top:10px}.sdb-stock-search,.sdb-stock-warehouse{min-width:100%;}.sdb-stock-table .sdb-num{text-align:left;}}

/* ── Layout grids ── */
.sdb-main-grid {
    display:grid; grid-template-columns:1fr 1fr 340px;
    gap:16px; margin-bottom:16px;
}
@media(max-width:1100px){.sdb-main-grid{grid-template-columns:1fr 1fr;}}
@media(max-width:700px){.sdb-main-grid{grid-template-columns:1fr;}}
.sdb-bottom-grid {
    display:grid; grid-template-columns:1fr 380px;
    gap:16px;
}
@media(max-width:900px){.sdb-bottom-grid{grid-template-columns:1fr;}}
.sdb-bottom-grid--phase1 { grid-template-columns:1fr 1fr; }
@media(max-width:900px){.sdb-bottom-grid--phase1{grid-template-columns:1fr;}}

/* ── Card ── */
.sdb-card {
    background:var(--card-bg,#fff); border:1px solid var(--border-color,#e8ecf0);
    border-radius:14px; overflow:hidden; box-shadow:0 1px 4px rgba(0,0,0,.04);
}
.sdb-card-hd {
    display:flex; align-items:center; justify-content:space-between;
    padding:14px 18px; border-bottom:1px solid var(--border-color,#f1f5f9);
}
.sdb-card-title {
    display:flex; align-items:center; gap:7px;
    font-size:13px; font-weight:700; color:var(--heading-color,#1a1f2e);
}
.sdb-card-title svg { width:14px; height:14px; stroke:#6366f1; }
.sdb-viewall {
    display:inline-flex; align-items:center; gap:4px;
    font-size:12px; font-weight:600; color:#6366f1; text-decoration:none;
    transition:gap .15s;
}
.sdb-viewall:hover { gap:7px; }
.sdb-viewall svg { width:12px; height:12px; stroke:#6366f1; }

/* Badges */
.sdb-badge-live {
    font-size:11px; font-weight:700; padding:2px 8px; border-radius:999px;
    background:#f1f5f9; color:var(--text-muted,#64748b);
}
.sdb-badge-live--red { background:#fee2e2; color:#dc2626; }
.sdb-badge-urgent {
    font-size:11px; font-weight:700; padding:2px 8px; border-radius:999px;
    background:#f1f5f9; color:var(--text-muted,#64748b);
}
.sdb-badge-urgent--red { background:#fef3c7; color:#d97706; }

/* ── Critical stock ── */
.sdb-crit-list { padding:8px 16px 16px; }
.sdb-crit-row {
    display:flex; justify-content:space-between; align-items:center;
    padding:10px 0; border-bottom:1px solid var(--border-color,#f8fafc);
    gap:12px;
}
.sdb-crit-row:last-child { border-bottom:none; }
.sdb-crit-info { flex:1; min-width:0; }
.sdb-crit-name { font-size:12.5px; font-weight:600; color:var(--heading-color,#1a1f2e); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.sdb-crit-code { font-size:11px; color:var(--text-muted,#94a3b8); }
.sdb-crit-right { text-align:right; min-width:120px; }
.sdb-crit-qty  { font-size:12px; font-weight:700; margin-bottom:5px; }
.sdb-crit-min  { font-weight:400; color:var(--text-muted,#94a3b8); font-size:11px; }
.sdb-qty-red   { color:#dc2626; }
.sdb-qty-amber { color:#d97706; }

/* ── Rotation ── */
.sdb-rot-list { padding:12px 18px 4px; }
.sdb-rot-row  { display:flex; align-items:center; gap:10px; margin-bottom:10px; }
.sdb-rot-name { font-size:12px; font-weight:600; color:var(--text-color,#334155); width:130px; flex-shrink:0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.sdb-rot-bar-wrap { flex:1; height:8px; background:var(--bg-color,#f1f5f9); border-radius:99px; overflow:hidden; }
.sdb-rot-bar  { height:100%; border-radius:99px; transition:width .4s ease; }
.sdb-rot-val  { font-size:12px; font-weight:700; color:var(--heading-color,#1a1f2e); width:36px; text-align:right; }
.sdb-rot-legend { display:flex; flex-wrap:wrap; gap:10px; padding:4px 18px 14px; }
.sdb-leg  { display:flex; align-items:center; gap:5px; font-size:11px; color:var(--text-muted,#64748b); }
.sdb-leg-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }

/* ── Alerts ── */
.sdb-alert-list { padding:10px 12px; display:flex; flex-direction:column; gap:9px; }
.sdb-alert {
    display:flex; flex-direction:column; gap:4px;
    padding:12px 14px; border-radius:10px; border:1px solid; position:relative;
}
.sdb-alert--error { background:#fff5f5; border-color:#fecaca; }
.sdb-alert--warn  { background:#fffbeb; border-color:#fde68a; }
.sdb-alert--info  { background:#eff6ff; border-color:#bfdbfe; }
.sdb-alert-hd     { display:flex; align-items:center; gap:7px; font-size:12.5px; }
.sdb-alert-ico    { display:inline-flex; flex-shrink:0; }
.sdb-alert--error .sdb-alert-ico svg { width:14px; height:14px; stroke:#dc2626; }
.sdb-alert--warn  .sdb-alert-ico svg { width:14px; height:14px; stroke:#d97706; }
.sdb-alert--info  .sdb-alert-ico svg { width:14px; height:14px; stroke:#3b82f6; }
.sdb-alert-msg  { font-size:11.5px; color:var(--text-color,#475569); padding-left:21px; }
.sdb-alert-sub  { font-size:11px; color:var(--text-muted,#94a3b8); padding-left:21px; font-style:italic; }
.sdb-alert-lnk  { position:absolute; top:12px; right:12px; display:inline-flex; }
.sdb-alert-lnk svg { width:13px; height:13px; stroke:#6366f1; }

/* ── Table ── */
.sdb-table-wrap { overflow-x:auto; }
.sdb-table-hint { font-size:11px; color:var(--text-muted,#94a3b8); padding:2px 14px 10px; }
.sdb-table { width:100%; border-collapse:collapse; font-size:13px; }
.sdb-table thead tr { background:var(--subtle-bg,#f8fafc); }
.sdb-table th {
    text-align:left; padding:9px 16px;
    font-size:10.5px; font-weight:700; text-transform:uppercase; letter-spacing:.5px;
    color:var(--text-muted,#64748b); border-bottom:1px solid var(--border-color,#e8ecf0);
    white-space:nowrap;
}
.sdb-table td {
    padding:11px 16px; border-bottom:1px solid var(--border-color,#f1f5f9);
    color:var(--text-color,#334155); vertical-align:middle;
}
.sdb-table tbody tr:last-child td { border-bottom:none; }
.sdb-row { cursor:pointer; transition:background .1s; }
.sdb-row:hover td { background:#fafbff; }
.sdb-tlink { font-weight:700; color:#6366f1; text-decoration:none; }
.sdb-tlink:hover { text-decoration:underline; }
.sdb-icount { color:#6366f1; }
.sdb-muted  { color:var(--text-muted,#94a3b8); }
.sdb-nowrap { white-space:nowrap; }

.sdb-status {
    display:inline-block; padding:3px 10px; border-radius:999px;
    font-size:11.5px; font-weight:600;
}
.sdb-status--draft     { background:#f1f5f9; color:#475569; }
.sdb-status--submitted { background:#d1fae5; color:#065f46; }
.sdb-status--cancelled { background:#fee2e2; color:#991b1b; }

/* ── Reorder queue ── */
.sdb-reorder-items { padding:10px 14px; display:flex; flex-direction:column; gap:10px; }
.sdb-reorder-item {
    display:flex; justify-content:space-between; align-items:center;
    padding:12px 14px; background:var(--bg-color,#f8fafc);
    border-radius:10px; gap:12px;
}
.sdb-reorder-name { font-size:12.5px; font-weight:700; color:var(--heading-color,#1a1f2e); margin-bottom:2px; }
.sdb-reorder-code { font-size:11px; color:var(--text-muted,#94a3b8); }
.sdb-reorder-meta { font-size:11px; color:var(--text-muted,#64748b); margin-top:3px; }
.sdb-reorder-right { text-align:right; flex-shrink:0; display:flex; flex-direction:column; align-items:flex-end; gap:6px; }
.sdb-reorder-qty   { font-size:13px; font-weight:700; }
.sdb-reorder-tag   { display:inline-block; font-size:9.5px; font-weight:800; letter-spacing:.6px; padding:1px 7px; border-radius:999px; }
.sdb-reorder-tag--stockout { background:#fee2e2; color:#dc2626; }
.sdb-reorder-btn {
    display:inline-block; padding:5px 14px;
    background:#6366f1; color:#fff; border-radius:7px;
    font-size:11.5px; font-weight:700; text-decoration:none; text-align:center;
    transition:background .15s;
}
.sdb-reorder-btn:hover { background:#4f46e5; }
.sdb-reorder-missing { font-size:11px; font-weight:700; color:#dc2626; }

/* ── Phase 1 operator cards ── */
.sdb-flagged-items, .sdb-qc-items { padding:10px 14px; display:flex; flex-direction:column; gap:10px; }
.sdb-flagged-item, .sdb-qc-item {
    display:flex; justify-content:space-between; align-items:center;
    padding:12px 14px; background:var(--bg-color,#f8fafc);
    border-radius:10px; gap:12px; text-decoration:none;
}
.sdb-flagged-name, .sdb-qc-name { font-size:12.5px; font-weight:700; color:var(--heading-color,#1a1f2e); margin-bottom:2px; }
.sdb-flagged-code, .sdb-qc-code, .sdb-qc-sub { font-size:11px; color:var(--text-muted,#94a3b8); }
.sdb-qc-right { text-align:right; display:flex; flex-direction:column; align-items:flex-end; gap:6px; }
.sdb-flag-pill {
    display:inline-block; padding:4px 10px; border-radius:999px;
    font-size:11px; font-weight:700; white-space:nowrap;
}
.sdb-flag-pill--slow-moving { background:#fef3c7; color:#b45309; }
.sdb-flag-pill--overstock { background:#dbeafe; color:#1d4ed8; }
.sdb-flag-pill--dormant { background:#fee2e2; color:#b91c1c; }

/* ── Utilities ── */
.sdb-shimmer-block {
    background:linear-gradient(90deg,#f1f5f9 25%,#e8ecf2 37%,#f1f5f9 63%);
    background-size:400% 100%; animation:sdb-shimmer 1.4s infinite;
}
@keyframes sdb-shimmer { 0%{background-position:100% 50%} 100%{background-position:0 50%} }
.sdb-empty {
    display:flex; flex-direction:column; align-items:center;
    padding:36px 20px; text-align:center;
    color:var(--text-muted,#94a3b8); font-size:13px; gap:10px;
}
.sdb-empty svg { width:32px; height:32px; stroke:#cbd5e1; }
.sdb-empty-inline { padding:16px; color:var(--text-muted,#94a3b8); font-size:13px; }

/* ── Access Command Center visual system ── */
.sdb-root { --canvas:#FAFBFC; --canvas-2:#F4F6F8; --surface:#FFFFFF; --surface-2:#F7F8FA; --surface-3:#F0F2F5; --ink-1000:#0A0E1A; --ink-900:#11151F; --ink-800:#1F2433; --ink-700:#2E3548; --ink-600:#495061; --ink-500:#6B7280; --ink-400:#9099A6; --ink-300:#B8BFC9; --ink-200:#DDE1E7; --ink-150:#E8EBEF; --ink-100:#EFF1F4; --ink-50:#F5F6F8; --primary-700:#3730A3; --primary-600:#4F46E5; --primary-500:#6366F1; --primary-300:#A5B4FC; --primary-100:#E0E7FF; --primary-50:#EEF2FF; --success-700:#047857; --success-600:#059669; --success-500:#10B981; --success-100:#D1FAE5; --success-50:#ECFDF5; --info-700:#0369A1; --info-600:#0284C7; --info-100:#E0F2FE; --info-50:#F0F9FF; --accent-700:#6D28D9; --accent-600:#7C3AED; --accent-500:#8B5CF6; --accent-100:#EDE9FE; --accent-50:#F5F3FF; --rose-700:#BE123C; --rose-600:#E11D48; --rose-100:#FFE4E6; --rose-50:#FFF1F2; --cyan-700:#0E7490; --cyan-500:#06B6D4; --cyan-100:#CFFAFE; --cyan-50:#ECFEFF; --font-sans:'Geist',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; --font-mono:'Geist Mono','SF Mono',Menlo,monospace; --r-lg:14px; --r-2xl:22px; --shadow-xs:0 1px 2px rgba(15,23,42,.04); --shadow-sm:0 1px 2px rgba(15,23,42,.04),0 2px 4px rgba(15,23,42,.04); --shadow-md:0 2px 4px rgba(15,23,42,.04),0 4px 12px rgba(15,23,42,.05); --shadow-lg:0 4px 8px rgba(15,23,42,.04),0 16px 32px -8px rgba(15,23,42,.08); --ease:cubic-bezier(.32,.72,0,1); --ring:0 0 0 3px rgba(99,102,241,.15); background:radial-gradient(circle at 20% 0%,rgba(99,102,241,.05) 0%,transparent 50%),radial-gradient(circle at 80% 30%,rgba(124,58,237,.03) 0%,transparent 50%),linear-gradient(to bottom,var(--canvas) 0%,var(--canvas-2) 100%); color:var(--ink-900); font-family:var(--font-sans); font-feature-settings:'cv11','ss01','ss03'; -webkit-font-smoothing:antialiased; min-height:calc(100vh - 72px); }
.sdb-root * { box-sizing:border-box; }
.sdb-root svg { fill:none; stroke:currentColor; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; }
.sdb-root button,.sdb-root input,.sdb-root select { font-family:inherit; }
.sdb-root *::-webkit-scrollbar { width:8px; height:8px; }
.sdb-root *::-webkit-scrollbar-thumb { background:var(--ink-200); border-radius:4px; }
.sdb-root *::-webkit-scrollbar-thumb:hover { background:var(--ink-300); }
.sdb-wrap { display:grid; gap:18px; margin:0 auto; max-width:1520px; padding:24px 24px 96px; }
.sdb-breadcrumb { align-items:center; color:var(--ink-500); display:flex; font-family:var(--font-mono); font-size:12px; gap:8px; }
.sdb-breadcrumb a { color:var(--ink-500); text-decoration:none; }
.sdb-breadcrumb a:hover { color:var(--ink-800); }
.sdb-breadcrumb .sep { color:var(--ink-300); }
.sdb-breadcrumb .current { color:var(--ink-800); font-weight:500; }
.sdb-header { align-items:center; background:var(--surface); border:1px solid var(--ink-150); border-radius:var(--r-lg); box-shadow:var(--shadow-sm); display:grid; gap:18px; grid-template-columns:1fr auto; margin-bottom:0; overflow:hidden; padding:14px 18px; position:relative; }
.sdb-header::before { background:radial-gradient(ellipse at top right,rgba(99,102,241,.06) 0%,transparent 60%); content:''; height:100%; pointer-events:none; position:absolute; right:0; top:0; width:60%; }
.sdb-header::after { background:linear-gradient(90deg,transparent,rgba(99,102,241,.4) 30%,rgba(124,58,237,.4) 70%,transparent); content:''; height:1px; left:0; position:absolute; right:0; top:0; }
.sdb-header-left,.sdb-header-actions { position:relative; z-index:1; }
.sdb-title-row { align-items:center; display:flex; flex-wrap:wrap; gap:10px; margin-bottom:8px; }
.sdb-eyebrow { align-items:center; background:var(--primary-50); border:1px solid var(--primary-100); border-radius:999px; color:var(--primary-700); display:inline-flex; font-size:10px; font-weight:500; gap:6px; letter-spacing:.01em; margin:0; padding:3px 9px 3px 4px; text-transform:none; }
.sdb-eyebrow span { align-items:center; background:linear-gradient(135deg,var(--primary-600),var(--accent-600)); border-radius:999px; box-shadow:0 2px 8px rgba(99,102,241,.35); color:#fff; display:flex; height:18px; justify-content:center; width:18px; }
.sdb-eyebrow svg { height:12px; width:12px; }
.sdb-title { color:var(--ink-1000); font-size:22px; font-weight:600; letter-spacing:-.025em; line-height:1.15; margin:0; }
.sdb-header-left p { color:var(--ink-500); font-size:14px; line-height:1.55; margin:0 0 18px; max-width:700px; }
.sdb-subtitle { color:var(--ink-500); display:inline-flex; font-family:var(--font-mono); font-size:10.5px; margin-top:0; padding:0; }
.sdb-header-actions { align-items:center; display:flex; flex-direction:row; flex-wrap:wrap; gap:8px; justify-content:flex-end; padding-top:0; }
.sdb-hdr-btn { align-items:center; border:1px solid transparent; border-radius:10px; cursor:pointer; display:inline-flex; font-size:13px; font-weight:500; gap:6px; height:38px; justify-content:center; letter-spacing:-.005em; padding:9px 14px; transition:all .2s var(--ease); white-space:nowrap; }
.sdb-hdr-btn:focus-visible,.sdb-scut:focus-visible,.sdb-stock-search:focus,.sdb-stock-warehouse:focus { outline:0; box-shadow:var(--ring); }
.sdb-hdr-btn--primary { background:var(--ink-1000); border-color:var(--ink-1000); box-shadow:inset 0 1px 0 rgba(255,255,255,.1),var(--shadow-sm); color:#fff; }
.sdb-hdr-btn--primary:hover { background:var(--ink-800); box-shadow:inset 0 1px 0 rgba(255,255,255,.1),var(--shadow-md); transform:translateY(-1px); }
.sdb-hdr-btn--ghost { background:var(--surface); border-color:var(--ink-200); color:var(--ink-700); }
.sdb-hdr-btn--ghost:hover { background:var(--surface-2); border-color:var(--ink-300); color:var(--ink-900); transform:translateY(-1px); }
.sdb-kpi-strip { display:grid; gap:8px; grid-template-columns:repeat(4,1fr); margin-bottom:0; }
.sdb-kpi { align-items:center; background:var(--surface); border:1px solid var(--ink-150); border-radius:10px; box-shadow:none; cursor:pointer; display:grid; gap:2px 8px; grid-template-columns:28px auto; opacity:0; overflow:hidden; padding:9px 11px; position:relative; transform:translateY(10px); transition:all .25s var(--ease); }
.sdb-kpi::before { background:var(--primary-500); content:''; height:2px; left:0; position:absolute; top:0; transform:scaleX(0); transform-origin:left; transition:transform .3s var(--ease); width:100%; }
.sdb-kpi:hover { border-color:var(--ink-200); box-shadow:var(--shadow-md); transform:translateY(-2px); }
.sdb-kpi:hover::before { transform:scaleX(1); }
.sdb-kpi--in { opacity:1; transform:translateY(0); }
.sdb-kpi-top { grid-row:1 / span 3; margin:0; }
.sdb-kpi-ico { align-items:center; background:var(--primary-50); border:1px solid var(--primary-100); border-radius:7px; color:var(--primary-700); display:flex; flex-shrink:0; height:28px; justify-content:center; width:28px; }
.sdb-kpi-ico svg { height:14px; stroke:currentColor; width:14px; }
.sdb-kpi-val { color:var(--ink-1000); font-feature-settings:'tnum'; font-size:17px; font-weight:600; letter-spacing:-.02em; line-height:1; margin:0; }
.sdb-kpi-lbl { color:var(--ink-500); font-size:10px; font-weight:500; letter-spacing:0; margin:0; text-transform:none; }
.sdb-kpi-sub { color:var(--ink-400); font-size:9px; line-height:1.2; }
.sdb-kpi-val--error { color:var(--rose-600); }
.sdb-kpi-val--warn { color:var(--cyan-700); }
.sdb-shortcuts { background:var(--surface); border:1px solid var(--ink-150); border-radius:12px; box-shadow:var(--shadow-xs); display:flex; flex-wrap:wrap; gap:2px; margin-bottom:0; padding:4px; }
.sdb-scut { background:transparent; border:0; border-radius:8px; color:var(--ink-600); font-size:13px; font-weight:500; gap:7px; padding:8px 14px; transition:all .2s var(--ease); }
.sdb-scut:hover { background:var(--surface-2); border-color:transparent; box-shadow:none; color:var(--ink-900); transform:none; }
.sdb-scut-ico svg { height:14px; stroke:currentColor; width:14px; }
.sdb-card { background:var(--surface); border:1px solid var(--ink-150); border-radius:var(--r-lg); box-shadow:var(--shadow-sm); overflow:hidden; }
.sdb-card-hd { border-bottom:1px solid var(--ink-100); padding:18px 20px; }
.sdb-card-title { color:var(--ink-1000); font-size:16px; font-weight:600; gap:8px; letter-spacing:-.015em; }
.sdb-card-title svg { color:var(--primary-700); height:16px; stroke:currentColor; width:16px; }
.sdb-card-subtitle { color:var(--ink-500); font-size:12px; line-height:1.45; margin-top:4px; }
.sdb-viewall { color:var(--ink-600); font-size:12px; font-weight:500; gap:5px; }
.sdb-viewall:hover { color:var(--ink-900); text-decoration:none; }
.sdb-viewall svg { stroke:currentColor; }
.sdb-wh-grid { display:grid; gap:8px; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); margin-bottom:0; }
.sdb-wh-card { align-items:center; background:var(--surface); border:1px solid var(--ink-150); border-radius:10px; box-shadow:var(--shadow-xs); cursor:pointer; display:grid; gap:12px; grid-template-columns:minmax(170px,1fr) auto; padding:9px 11px; transition:all .25s var(--ease); }
.sdb-wh-card:hover { border-color:var(--ink-200); box-shadow:var(--shadow-md); transform:translateY(-2px); }
.sdb-wh--ok,.sdb-wh--warn,.sdb-wh--alert { border-top:1px solid var(--ink-150); }
.sdb-wh-top { align-items:center; display:flex; gap:8px; margin:0; min-width:0; }
.sdb-wh-icon { align-items:center; background:var(--info-50); border:1px solid var(--info-100); border-radius:7px; color:var(--info-700); display:flex; flex:0 0 auto; height:28px; justify-content:center; width:28px; }
.sdb-wh-icon svg { height:14px; stroke:currentColor; width:14px; }
.sdb-wh-status,.sdb-badge-live,.sdb-badge-urgent { border:1px solid; border-radius:6px; font-size:11px; font-weight:600; letter-spacing:.01em; padding:3px 8px; text-transform:none; }
.sdb-wh--ok .sdb-wh-status { background:var(--success-50); border-color:var(--success-100); color:var(--success-700); }
.sdb-wh--warn .sdb-wh-status,.sdb-badge-urgent--red { background:var(--cyan-50); border-color:var(--cyan-100); color:var(--cyan-700); }
.sdb-wh--alert .sdb-wh-status,.sdb-badge-live--red { background:var(--rose-50); border-color:var(--rose-100); color:var(--rose-700); }
.sdb-wh-name { color:var(--ink-1000); flex:1; font-size:13px; font-weight:600; letter-spacing:-.01em; margin:0; min-width:0; }
.sdb-wh-stats { display:flex; gap:14px; grid-template-columns:none; }
.sdb-wh-stat { align-items:baseline; display:flex; gap:4px; text-align:left; }
.sdb-wh-val { color:var(--ink-1000); font-feature-settings:'tnum'; font-size:14px; font-weight:600; }
.sdb-wh-lbl { color:var(--ink-400); font-size:9px; font-weight:500; letter-spacing:0; }
.sdb-bar-track { background:var(--ink-100); }
.sdb-bar--green { background:var(--success-500); }
.sdb-bar--amber,.sdb-bar--yellow { background:var(--cyan-500); }
.sdb-bar--red { background:var(--rose-600); }
.sdb-stock-tools,.sdb-table thead tr,.sdb-table thead th { background:var(--surface-2); }
.sdb-stock-tools { border-bottom:1px solid var(--ink-100); padding:12px 20px; }
.sdb-stock-head-actions { align-items:center; display:flex; gap:6px; }
.sdb-stock-head-actions .sdb-hdr-btn { font-size:11px; height:32px; padding:6px 10px; }
.sdb-stock-search,.sdb-stock-warehouse { background:var(--surface); border:1px solid var(--ink-200); border-radius:8px; color:var(--ink-900); font-size:13px; min-height:38px; outline:0; padding:9px 11px; transition:all .2s var(--ease); }
.sdb-stock-search:focus,.sdb-stock-warehouse:focus { border-color:var(--primary-500); }
.sdb-stock-check { color:var(--ink-600); font-size:12px; font-weight:500; }
.sdb-table-wrap { max-height:680px; overflow:auto; overscroll-behavior:contain; }
.sdb-table { font-size:13px; }
.sdb-table th { background:var(--surface-2); border-bottom:1px solid var(--ink-100); color:var(--ink-500); font-size:11px; font-weight:600; letter-spacing:.06em; padding:10px 12px; position:sticky; top:0; z-index:4; }
.sdb-plan-card { overflow:hidden; }
.sdb-plan-hd { align-items:center; display:flex; flex-wrap:wrap; gap:12px; justify-content:space-between; }
.sdb-plan-subtitle { color:var(--ink-500); font-size:12px; margin-top:4px; }
.sdb-plan-actions { align-items:center; display:flex; flex-wrap:wrap; gap:7px; }
.sdb-plan-actions .sdb-hdr-btn { font-size:11px; height:32px; padding:6px 10px; text-decoration:none; }
.sdb-plan-summary { background:var(--surface-2); border-bottom:1px solid var(--ink-100); display:grid; gap:8px; grid-template-columns:repeat(6,minmax(110px,1fr)); padding:12px 16px; }
.sdb-plan-metric { background:var(--surface); border:1px solid var(--ink-150); border-radius:9px; display:flex; flex-direction:column; gap:2px; padding:9px 11px; }
.sdb-plan-metric span { color:var(--ink-500); font-size:10px; font-weight:600; text-transform:uppercase; }
.sdb-plan-metric strong { color:var(--ink-1000); font-size:18px; }
.sdb-plan-metric--success { border-left:3px solid var(--success-500); }
.sdb-plan-metric--info { border-left:3px solid var(--primary-500); }
.sdb-plan-metric--warn { border-left:3px solid var(--cyan-500); }
.sdb-plan-metric--error { border-left:3px solid var(--rose-600); }
.sdb-plan-disabled { background:var(--cyan-50); border:1px solid var(--cyan-100); border-radius:9px; color:var(--cyan-700); font-size:12px; grid-column:1/-1; padding:10px 12px; }
.sdb-plan-table td small { color:var(--ink-500); display:block; font-size:10.5px; line-height:1.35; margin-top:3px; max-width:300px; }
.sdb-plan-status { border:1px solid; border-radius:999px; display:inline-flex; font-size:10px; font-weight:700; padding:4px 8px; white-space:nowrap; }
.sdb-plan-status--success { background:var(--success-50); border-color:var(--success-100); color:var(--success-700); }
.sdb-plan-status--info { background:var(--primary-50); border-color:var(--primary-100); color:var(--primary-700); }
.sdb-plan-status--warn { background:var(--cyan-50); border-color:var(--cyan-100); color:var(--cyan-700); }
.sdb-plan-status--error { background:var(--rose-50); border-color:var(--rose-100); color:var(--rose-700); }
.sdb-plan-status--neutral { background:var(--surface-2); border-color:var(--ink-150); color:var(--ink-600); }
.sdb-sort-head { align-items:center; background:transparent; border:0; color:inherit; cursor:pointer; display:inline-flex; font:inherit; gap:5px; justify-content:flex-start; letter-spacing:inherit; padding:0; text-transform:inherit; width:100%; }
.sdb-num .sdb-sort-head { justify-content:flex-end; }
.sdb-sort-head:hover,.sdb-sort-head.is-active { color:var(--primary-700); }
.sdb-sort-arrows { display:inline-flex; flex-direction:column; font-size:8px; line-height:7px; opacity:.38; }
.sdb-sort-arrows span.is-active { color:var(--primary-700); font-weight:800; opacity:1; }
.sdb-sort-head:focus-visible { border-radius:4px; box-shadow:var(--ring); outline:0; }
.sdb-table td { border-bottom:1px solid var(--ink-100); color:var(--ink-700); padding:12px; }
.sdb-table tbody tr { background:#fff; transition:background .15s var(--ease); }
.sdb-row:hover td { background:var(--surface-2); }
.sdb-tlink,.sdb-stock-item-code a,.sdb-icount { color:var(--primary-600); }
.sdb-muted,.sdb-stock-item-code,.sdb-stock-wh-summary,.sdb-reorder-code,.sdb-reorder-meta,.sdb-flagged-code,.sdb-qc-code,.sdb-qc-sub { color:var(--ink-500); }
.sdb-stock-item-name,.sdb-crit-name,.sdb-reorder-name,.sdb-flagged-name,.sdb-qc-name { color:var(--ink-1000); font-weight:600; letter-spacing:-.01em; }
.sdb-stock-status { border:1px solid; border-radius:6px; font-size:11px; font-weight:600; min-width:56px; padding:3px 8px; }
.sdb-stock-status--available,.sdb-status--submitted { background:var(--success-50); border-color:var(--success-100); color:var(--success-700); }
.sdb-stock-status--reserved,.sdb-status--draft { background:var(--cyan-50); border-color:var(--cyan-100); color:var(--cyan-700); }
.sdb-stock-status--out,.sdb-status--cancelled { background:var(--rose-50); border-color:var(--rose-100); color:var(--rose-700); }
.sdb-stock-wh-count { color:var(--ink-700); font-weight:600; }
.sdb-main-grid,.sdb-bottom-grid,.sdb-bottom-grid--phase1 { gap:16px; }
.sdb-stock-footer { display:flex; justify-content:center; padding:14px 0 4px; }
.sdb-modal .modal-dialog { max-width:min(1320px, calc(100vw - 24px)); }
.sdb-modal .modal-content { max-height:calc(100vh - 32px); overflow:hidden; }
.sdb-modal .modal-body { background:var(--surface-2); max-height:calc(100vh - 142px); overflow:auto; overscroll-behavior:contain; }
.sdb-modal-shell { display:grid; gap:16px; }
.sdb-modal-identity { align-items:center; background:linear-gradient(135deg,var(--surface),var(--primary-50)); border:1px solid var(--primary-100); border-radius:14px; display:flex; gap:12px; padding:14px; }
.sdb-modal-identity-icon { align-items:center; background:var(--primary-600); border-radius:10px; color:#fff; display:flex; flex:0 0 auto; height:40px; justify-content:center; width:40px; }
.sdb-modal-identity-icon svg { height:20px; width:20px; }
.sdb-modal-identity-copy { display:grid; flex:1; gap:2px; min-width:0; }
.sdb-modal-identity-copy strong { color:var(--ink-1000); font-size:15px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.sdb-modal-identity-copy span { color:var(--ink-500); font-family:var(--font-mono); font-size:11px; }
.sdb-modal-tags { display:flex; flex-wrap:wrap; gap:6px; justify-content:flex-end; }
.sdb-modal-tags span { background:var(--surface); border:1px solid var(--ink-150); border-radius:999px; color:var(--ink-600); font-size:10px; padding:4px 8px; }
.sdb-modal-tools { align-items:center; background:var(--surface); border:1px solid var(--ink-150); border-radius:12px; display:flex; flex-wrap:wrap; gap:8px; padding:10px; }
.sdb-modal-tools input,.sdb-modal-tools select { background:var(--surface); border:1px solid var(--ink-200); border-radius:8px; color:var(--ink-900); font-size:12px; min-height:36px; padding:7px 9px; }
.sdb-modal-tools input:not([type="date"]) { flex:1; min-width:180px; }
.sdb-modal-stats { display:grid; gap:12px; grid-template-columns:repeat(auto-fit, minmax(140px, 1fr)); }
.sdb-modal-stat { background:var(--surface); border:1px solid var(--ink-150); border-radius:12px; box-shadow:var(--shadow-xs); padding:12px 14px; }
.sdb-modal-stat span { color:var(--ink-500); display:block; font-size:11px; margin-bottom:4px; text-transform:uppercase; }
.sdb-modal-stat strong { color:var(--ink-1000); font-size:18px; }
.sdb-modal-grid { display:grid; gap:16px; grid-template-columns:1fr 1fr; }
.sdb-modal-card { background:var(--surface); border:1px solid var(--ink-150); border-radius:14px; padding:14px; }
.sdb-modal-card h4 { color:var(--ink-1000); font-size:15px; font-weight:600; margin:0 0 10px; }
.sdb-modal-card-head { align-items:center; display:flex; justify-content:space-between; margin-bottom:10px; }
.sdb-modal-card-head h4 { margin:0; }
.sdb-modal-meta { color:var(--ink-500); font-size:12px; margin-bottom:10px; }
.sdb-modal-table { margin-top:8px; }
.sdb-modal-table small { color:var(--ink-500); display:block; }
.sdb-modal-table tbody tr:hover td { background:var(--primary-50); }
.sdb-entry-row { cursor:pointer; }
.sdb-delta { border:1px solid; border-radius:6px; display:inline-block; font-weight:700; min-width:58px; padding:3px 7px; text-align:right; }
.sdb-delta.is-in { background:var(--success-50); border-color:var(--success-100); color:var(--success-700); }
.sdb-delta.is-out { background:var(--rose-50); border-color:var(--rose-100); color:var(--rose-700); }
.sdb-delta.is-neutral { background:var(--surface-2); border-color:var(--ink-150); color:var(--ink-600); }
.sdb-modal-card .sdb-empty-inline { padding:10px 0; }
.sdb-modal .modal-footer { background:var(--surface); border-top:1px solid var(--ink-100); }
@media(max-width:900px){.sdb-modal-grid{grid-template-columns:1fr}.sdb-modal-tools>*{flex:1 1 180px}.sdb-modal-identity{align-items:flex-start;flex-wrap:wrap}.sdb-modal-tags{justify-content:flex-start;width:100%}}
.sdb-crit-list,.sdb-rot-list,.sdb-alert-list,.sdb-reorder-items,.sdb-flagged-items,.sdb-qc-items { padding:14px; }
.sdb-crit-row,.sdb-reorder-item,.sdb-flagged-item,.sdb-qc-item,.sdb-alert { background:var(--surface); border:1px solid var(--ink-150); border-radius:14px; }
.sdb-reorder-item,.sdb-flagged-item,.sdb-qc-item { padding:12px; }
.sdb-alert--error { background:var(--rose-50); border-color:var(--rose-100); }
.sdb-alert--warn { background:var(--cyan-50); border-color:var(--cyan-100); }
.sdb-alert--info { background:var(--info-50); border-color:var(--info-100); }
.sdb-status,.sdb-flag-pill { border:1px solid; border-radius:6px; font-size:11px; font-weight:600; padding:3px 8px; }
.sdb-flag-pill--slow-moving { background:var(--cyan-50); border-color:var(--cyan-100); color:var(--cyan-700); }
.sdb-flag-pill--overstock { background:var(--info-50); border-color:var(--info-100); color:var(--info-700); }
.sdb-flag-pill--dormant { background:var(--rose-50); border-color:var(--rose-100); color:var(--rose-700); }
.sdb-empty { color:var(--ink-500); }
.sdb-shimmer-block,.sdb-shimmer-card,.sdb-shimmer-kpi { background:var(--ink-150); overflow:hidden; position:relative; }
.sdb-shimmer-block::after,.sdb-shimmer-card::after,.sdb-shimmer-kpi::after { animation:sdb-shimmer 1.4s infinite; background:linear-gradient(90deg,transparent,rgba(255,255,255,.72),transparent); content:''; inset:0; position:absolute; transform:translateX(-100%); }
@keyframes sdb-shimmer { 100% { transform:translateX(100%); } }
@media (prefers-reduced-motion: reduce) { .sdb-root *, .sdb-root *::before, .sdb-root *::after { animation-duration:.01ms !important; transition-duration:.01ms !important; } }
@media(max-width:1280px){.sdb-wrap{padding-left:18px;padding-right:18px}.sdb-kpi-strip{grid-template-columns:repeat(2,1fr)}.sdb-main-grid{grid-template-columns:1fr 1fr}.sdb-bottom-grid{grid-template-columns:1fr}.sdb-plan-summary{grid-template-columns:repeat(3,1fr)}}
@media(max-width:900px){.sdb-wrap{padding:20px 16px 96px}.sdb-header{grid-template-columns:1fr;padding:14px 16px}.sdb-header-actions{align-items:stretch}.sdb-kpi-strip,.sdb-main-grid,.sdb-bottom-grid,.sdb-bottom-grid--phase1{grid-template-columns:1fr}.sdb-plan-summary{grid-template-columns:repeat(2,1fr)}.sdb-plan-actions{width:100%}.sdb-stock-hd{align-items:flex-start;display:flex;flex-direction:row;flex-wrap:wrap;gap:10px}.sdb-stock-head-actions{margin-left:auto}.sdb-stock-search,.sdb-stock-warehouse{min-width:100%}}
@media(max-width:640px){.sdb-header-actions{width:100%}.sdb-hdr-btn{width:100%}.sdb-shortcuts{display:grid;grid-template-columns:1fr}.sdb-stock-table .sdb-num{text-align:left}}

/* Dark mode */
[data-theme-mode="dark"] .sdb-shimmer-block,
[data-theme-mode="dark"] .sdb-shimmer-card,
[data-theme-mode="dark"] .sdb-shimmer-kpi {
    background:linear-gradient(90deg,#22263a 25%,#2a2f48 37%,#22263a 63%);
    background-size:400% 100%; animation:sdb-shimmer 1.4s infinite;
}
[data-theme-mode="dark"] .sdb-row:hover td { background:rgba(99,102,241,.06); }
[data-theme-mode="dark"] .sdb-reorder-item { background:var(--bg-color); }
    `;
    document.head.appendChild(s);
}
