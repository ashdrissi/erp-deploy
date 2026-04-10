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

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function renderSkeleton(page) {
    page.main.html(`
        <div class="sdb-wrap">

            <!-- header row -->
            <div class="sdb-header">
                <div class="sdb-header-left">
                    <div class="sdb-eyebrow">${__("INVENTORY CONTROL")}</div>
                    <div class="sdb-title">${__("Stock & Warehouses")}</div>
                    <div class="sdb-subtitle" id="sdb-subtitle">${__("Loading…")}</div>
                </div>
                <div class="sdb-header-actions">
                    ${hdrBtn("transfer", __("New Transfer"), "/app/stock-entry/new-stock-entry-1?stock_entry_type=Material+Transfer", "ghost")}
                    ${hdrBtn("new", __("New Stock Entry"), "/app/stock-entry/new-stock-entry-1", "primary")}
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
                ${scut("warehouse", __("Warehouses"), "/app/warehouse", "default")}
                ${scut("box", __("Items"), "/app/item", "default")}
                ${scut("transfer", __("All Transfers"), "/app/stock-entry?stock_entry_type=Material+Transfer", "default")}
                ${scut("cart", __("Reorder Levels"), "/app/item-reorder", "default")}
                ${scut("list", __("Stock Ledger"), "/app/stock-ledger", "default")}
                ${scut("rotate", __("Stock Balance"), "/app/stock-balance", "default")}
            </div>

            <!-- Main 3-column grid -->
            <div class="sdb-main-grid">

                <!-- Col 1: Critical stock -->
                <div class="sdb-card">
                    <div class="sdb-card-hd">
                        <div class="sdb-card-title">${IC.alert} ${__("Critical Stock Levels")}</div>
                        <a href="/app/stock-balance" class="sdb-viewall">${__("View all")} ${IC.arrow}</a>
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
                        <a href="/app/stock-entry?stock_entry_type=Material+Transfer" class="sdb-viewall">${__("View all")} ${IC.arrow}</a>
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
    page.main.find(".sdb-hdr-btn").on("click", function () {
        frappe.set_route($(this).data("url").replace(/^\/app\//, "").split("/"));
    });
    // Shortcuts
    page.main.find(".sdb-scut").on("click", function () {
        frappe.set_route($(this).data("url").replace(/^\/app\//, "").split("/"));
    });
}

function hdrBtn(icon, label, url, variant) {
    return `<button class="sdb-hdr-btn sdb-hdr-btn--${variant}" data-url="${url}">
        <span class="sdb-btn-ico">${IC[icon]}</span>${frappe.utils.escape_html(label)}
    </button>`;
}
function scut(icon, label, url, variant) {
    return `<div class="sdb-scut sdb-scut--${variant}" data-url="${url}">
        <span class="sdb-scut-ico">${IC[icon]}</span>
        <span class="sdb-scut-lbl">${frappe.utils.escape_html(label)}</span>
    </div>`;
}

// ─── Data loading ─────────────────────────────────────────────────────────────

async function loadData(page) {
    try {
        const res = await frappe.call({
            method: "orderlift.orderlift_logistics.page.stock_dashboard.stock_dashboard.get_dashboard_data",
        });
        const d = res.message || {};
        renderSubtitle(page, d);
        renderWarehouseCards(page, d.warehouses || []);
        renderKpis(page, d.kpis || {});
        renderCriticalStock(page, d.critical_stock || []);
        renderRotation(page, d.rotation_by_category || []);
        renderAlerts(page, d.alerts || []);
        renderTransfers(page, d.recent_transfers || []);
        renderReorderQueue(page, d.reorder_queue || []);
        renderFlaggedItems(page, d.flagged_items || []);
        renderQcRouting(page, d.qc_routing || []);
    } catch (e) {
        console.warn("Stock Dashboard: failed to load data", e);
        frappe.show_alert({ message: __("Could not load dashboard data"), indicator: "red" });
    }
}

// ─── Subtitle ─────────────────────────────────────────────────────────────────

function renderSubtitle(page, data) {
    const wh_count = (data.warehouses || []).length;
    const items = (data.kpis || {}).total_units || 0;
    page.main.find("#sdb-subtitle").text(
        __("{0} warehouses · {1} active stock units · {2}",
            [wh_count, items.toLocaleString(), frappe.datetime.now_time()])
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
        const barClass = barW > 85 ? "sdb-bar--red" : barW > 65 ? "sdb-bar--amber" : "sdb-bar--green";

        return `
            <div class="sdb-wh-card ${statusClass}" data-wh="${frappe.utils.escape_html(wh.name)}">
                <div class="sdb-wh-top">
                    <div class="sdb-wh-icon">${IC.warehouse}</div>
                    <span class="sdb-wh-status">${statusLabel}</span>
                </div>
                <div class="sdb-wh-name">${frappe.utils.escape_html(wh.label || wh.name)}</div>
                <div class="sdb-bar-track">
                    <div class="sdb-bar-fill ${barClass}" style="width:${barW}%"></div>
                </div>
                <div class="sdb-wh-stats">
                    <div class="sdb-wh-stat">
                        <div class="sdb-wh-val">${(wh.total_units || 0).toLocaleString()}</div>
                        <div class="sdb-wh-lbl">${__("UNITS")}</div>
                    </div>
                    <div class="sdb-wh-stat">
                        <div class="sdb-wh-val">${wh.capacity_pct || 0}%</div>
                        <div class="sdb-wh-lbl">${__("CAPACITY")}</div>
                    </div>
                    <div class="sdb-wh-stat">
                        <div class="sdb-wh-val ${wh.alerts > 0 ? "sdb-val-alert" : ""}">${wh.alerts || 0}</div>
                        <div class="sdb-wh-lbl">${__("ALERTS")}</div>
                    </div>
                </div>
            </div>`;
    }).join(""));

    grid.find(".sdb-wh-card").on("click", function () {
        const wh = $(this).data("wh");
        if (wh) frappe.set_route("query-report", "Stock Balance", { warehouse: wh });
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

    const levelIcon = { error: "🔴", warn: "🟡", info: "🔵", ok: "🟢" };
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
                    <tr class="sdb-row" data-href="/app/stock-entry/${encodeURIComponent(r.name)}">
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
        frappe.set_route("stock-entry", $(this).data("href").split("/").pop());
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
