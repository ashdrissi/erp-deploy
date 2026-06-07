frappe.pages["performance-leaderboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Performance Leaderboard"),
        single_column: true,
    });
    page.main.addClass("hr-root perf-theme plb-root");
    injectStyles();
    state.page = page;
    renderSkeleton(page);
    bindFilters(page);
    bootstrap(page);
};

const state = {
    page: null,
    cycle: null,
    cycles: [],
    rows: [],
    admin: false,
    filters: {},
    categories: [],
    metrics: [],
    metricsByCategory: {},
    metricsById: {},
    view: { category: "ALL", sort: { key: "rank", dir: "asc" } },
};

const ICONS = {
    trophy:
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></svg>',
    medal:
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7.21 15 2.66 7.14a2 2 0 0 1 .13-2.2L4.4 2.8A2 2 0 0 1 6 2h12a2 2 0 0 1 1.6.8l1.6 2.14a2 2 0 0 1 .14 2.2L16.79 15"/><circle cx="12" cy="17" r="5"/></svg>',
    award:
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="6"/><path d="M15.477 12.89 17 22l-5-3-5 3 1.523-9.11"/></svg>',
    download:
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
    close:
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
    target:
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>',
    users:
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    activity:
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
    arrow:
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>',
};

const CATEGORY_PALETTE = {
    Sales: "#1570EF",
    CRM: "#7F56D9",
    Quotations: "#06AED4",
    Operations: "#039855",
    Training: "#DC6803",
    Quality: "#D92D20",
    Attendance: "#6941C6",
    Other: "#667085",
};

function catColor(cat) {
    return CATEGORY_PALETTE[cat] || "#667085";
}

function injectStyles() {
    if (document.getElementById("plb-styles")) return;
    const css = `
    .plb-kpi-trend { font-size: 11px; color: var(--hr-muted); margin-top: 4px; display: flex; align-items: center; gap: 4px; }
    .plb-chip-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
    .plb-cat-pill {
        height: 32px;
        padding: 0 14px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 600;
        background: var(--hr-card);
        border: 1px solid var(--hr-line);
        color: var(--hr-text);
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        transition: all .15s;
    }
    .plb-cat-pill:hover { border-color: var(--hr-primary); background: var(--hr-primary-50); }
    .plb-cat-pill.is-active {
        background: var(--hr-primary);
        color: #fff;
        border-color: var(--hr-primary);
        box-shadow: 0 4px 12px rgba(21,112,239,0.18);
    }
    .plb-cat-pill .plb-pill-dot {
        width: 8px; height: 8px; border-radius: 50%;
    }
    .plb-cat-pill .plb-pill-count {
        font-size: 11px;
        background: var(--hr-line-soft);
        color: var(--hr-muted);
        padding: 1px 7px;
        border-radius: 999px;
        font-weight: 700;
    }
    .plb-cat-pill.is-active .plb-pill-count { background: rgba(255,255,255,0.22); color: #fff; }
    .plb-score-cell { min-width: 180px; }
    .plb-score-val { font-weight: 700; color: var(--hr-primary-700); font-size: 14px; margin-bottom: 4px; }
    .plb-cat-stack {
        display: flex;
        height: 8px;
        border-radius: 999px;
        overflow: hidden;
        background: var(--hr-line-soft);
        margin-top: 4px;
        min-width: 160px;
    }
    .plb-cat-stack-seg {
        height: 100%;
        min-width: 2px;
    }
    .plb-cat-legend { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
    .plb-cat-legend-item {
        display: inline-flex; align-items: center; gap: 4px;
        font-size: 10px; color: var(--hr-muted);
    }
    .plb-cat-legend-dot { width: 6px; height: 6px; border-radius: 50%; }
    .plb-metric-cell {
        text-align: center;
        min-width: 92px;
    }
    .plb-metric-cell .plb-metric-score {
        font-weight: 700;
        font-size: 13px;
        color: var(--hr-dark);
    }
    .plb-metric-cell .plb-metric-display {
        font-size: 11px;
        color: var(--hr-muted);
        margin-top: 2px;
    }
    .plb-sort-btn {
        background: transparent;
        border: none;
        padding: 0;
        font: inherit;
        cursor: pointer;
        color: inherit;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }
    .plb-sort-btn:hover { color: var(--hr-primary); }
    .plb-sort-ind { width: 10px; height: 10px; opacity: .4; transition: transform .15s; }
    .plb-sort-btn.is-asc .plb-sort-ind { transform: rotate(180deg); opacity: 1; }
    .plb-sort-btn.is-desc .plb-sort-ind { opacity: 1; }
    .plb-drill-cat {
        background: var(--hr-card);
        border: 1px solid var(--hr-line);
        border-radius: 14px;
        overflow: hidden;
        margin-bottom: 12px;
    }
    .plb-drill-cat-head {
        padding: 12px 16px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid var(--hr-line);
        background: var(--hr-bg);
    }
    .plb-drill-cat-title { font-weight: 700; font-size: 13px; color: var(--hr-dark); display: inline-flex; align-items: center; gap: 8px; }
    .plb-drill-cat-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
    .plb-drill-cat-avg {
        font-size: 13px;
        font-weight: 700;
        color: var(--hr-primary-700);
    }
    .plb-drill-metrics { padding: 4px 0; }
    .plb-drill-metric {
        padding: 10px 16px;
        border-bottom: 1px solid var(--hr-line-soft);
        display: grid;
        grid-template-columns: 1fr auto;
        gap: 6px;
        align-items: center;
    }
    .plb-drill-metric:last-child { border-bottom: none; }
    .plb-drill-metric-name { font-weight: 600; font-size: 13px; color: var(--hr-dark); }
    .plb-drill-metric-meta { font-size: 11px; color: var(--hr-muted); margin-top: 2px; }
    .plb-drill-metric-meta b { color: var(--hr-text); }
    .plb-drill-metric-score {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 56px;
        padding: 4px 10px;
        border-radius: 8px;
        font-weight: 700;
        font-size: 13px;
    }
    .plb-drill-metric-bar {
        grid-column: 1 / -1;
        height: 4px;
        border-radius: 999px;
        background: var(--hr-line-soft);
        overflow: hidden;
        margin-top: 6px;
    }
    .plb-drill-metric-bar-fill { height: 100%; border-radius: 999px; }
    .plb-th-sub { font-size: 10px; opacity: .65; font-weight: 500; text-transform: none; letter-spacing: 0; margin-top: 2px; }
    `;
    const tag = document.createElement("style");
    tag.id = "plb-styles";
    tag.textContent = css;
    document.head.appendChild(tag);
}

function renderSkeleton(page) {
    page.main.html(`
        <div class="hr-wrap">
            <div class="hr-hero">
                <div>
                    <div class="hr-eyebrow">${__("Orderlift")} · ${__("Performance")}</div>
                    <h1 class="hr-title">${__("Performance Leaderboard")}</h1>
                    <div class="hr-sub">${__(
                        "Cycle ranking by weighted metric score across sales, CRM, operations, training and attendance.",
                    )}</div>
                </div>
                <div class="hr-hero-side">
                    <select id="plb-cycle" class="hr-select" style="min-width:240px;">
                        <option>${__("Loading…")}</option>
                    </select>
                </div>
            </div>

            <div class="hr-kpis" id="plb-kpis" style="display:none;">
                <div class="hr-kpi">
                    <div class="hr-kpi-icon hr-kpi-icon--indigo">${ICONS.users}</div>
                    <div class="hr-kpi-label">${__("Employees")}</div>
                    <div class="hr-kpi-value" id="plb-kpi-emp">—</div>
                    <div class="hr-kpi-hint" id="plb-kpi-emp-hint">${__("Ranked in this cycle")}</div>
                </div>
                <div class="hr-kpi">
                    <div class="hr-kpi-icon hr-kpi-icon--green">${ICONS.activity}</div>
                    <div class="hr-kpi-label">${__("Median Score")}</div>
                    <div class="hr-kpi-value" id="plb-kpi-median">—</div>
                    <div class="hr-kpi-hint"><span id="plb-kpi-band-text">—</span></div>
                </div>
                <div class="hr-kpi">
                    <div class="hr-kpi-icon hr-kpi-icon--amber">${ICONS.trophy}</div>
                    <div class="hr-kpi-label">${__("Top Performer")}</div>
                    <div class="hr-kpi-value" id="plb-kpi-top">—</div>
                    <div class="hr-kpi-hint" id="plb-kpi-top-name">—</div>
                </div>
                <div class="hr-kpi">
                    <div class="hr-kpi-icon hr-kpi-icon--purple">${ICONS.target}</div>
                    <div class="hr-kpi-label">${__("Metrics Tracked")}</div>
                    <div class="hr-kpi-value" id="plb-kpi-metric">—</div>
                    <div class="hr-kpi-hint" id="plb-kpi-cat-hint">—</div>
                </div>
            </div>

            <div class="hr-toolbar" id="plb-toolbar" style="display:none;">
                <input class="hr-filter plb-filter" data-key="department" placeholder="${__("Department")}" />
                <input class="hr-filter plb-filter" data-key="designation" placeholder="${__("Designation")}" />
                <button class="hr-btn hr-btn--ghost" id="plb-clear">${__("Clear")}</button>
                <div class="hr-toolbar-spacer"></div>
                <button class="hr-btn hr-btn--primary" id="plb-export">${ICONS.download}<span>${__("Export CSV")}</span></button>
            </div>

            <div id="plb-cat-chips" class="plb-chip-row" style="display:none;"></div>

            <div id="plb-podium" class="hr-podium hr-podium--flat"></div>

            <div class="hr-card">
                <div class="hr-card-head">
                    <div>
                        <div class="hr-card-title" id="plb-card-title">${__("Full Ranking")}</div>
                        <div class="hr-card-sub" id="plb-card-sub">${__("Loading…")}</div>
                    </div>
                </div>
                <div id="plb-table" class="hr-table-wrap">
                    <div class="hr-empty">
                        ${ICONS.target}
                        <div class="hr-empty-title">${__("Pick an appraisal cycle")}</div>
                        <div class="hr-empty-sub">${__("Select a cycle above to view the leaderboard.")}</div>
                    </div>
                </div>
            </div>
        </div>
    `);
}

function bindFilters(page) {
    page.main.on("change", "#plb-cycle", function () {
        state.cycle = $(this).val();
        loadData();
    });
    page.main.on("input", ".plb-filter", function () {
        const key = $(this).data("key");
        state.filters[key] = $(this).val();
        clearTimeout(state._t);
        state._t = setTimeout(loadData, 250);
    });
    page.main.on("click", "#plb-clear", function () {
        state.filters = {};
        page.main.find(".plb-filter").val("");
        loadData();
    });
    page.main.on("click", "#plb-export", exportCsv);
    page.main.on("click", ".plb-drilldown-btn", function (e) {
        e.stopPropagation();
        const emp = $(this).data("employee");
        openDrilldown(emp);
    });
    page.main.on("click", ".hr-podium-card--clickable", function () {
        const emp = $(this).data("employee");
        if (emp) openDrilldown(emp);
    });
    page.main.on("click", ".plb-row[data-employee]", function () {
        if (!state.admin) return;
        const emp = $(this).data("employee");
        if (emp) openDrilldown(emp);
    });
    page.main.on("click", ".plb-cat-pill", function () {
        const cat = $(this).data("category");
        if (cat == null) return;
        state.view.category = cat;
        renderChips();
        renderTable(state.rows);
    });
    page.main.on("click", ".plb-sort-btn", function () {
        const key = $(this).data("sort");
        if (!key) return;
        if (state.view.sort.key === key) {
            state.view.sort.dir = state.view.sort.dir === "asc" ? "desc" : "asc";
        } else {
            state.view.sort.key = key;
            state.view.sort.dir = key === "rank" ? "asc" : "desc";
        }
        renderTable(state.rows);
    });
}

async function bootstrap(page) {
    try {
        const res = await frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Appraisal Cycle",
                fields: ["name", "cycle_name", "start_date", "end_date", "status"],
                order_by: "start_date desc",
                limit_page_length: 50,
            },
        });
        state.cycles = res.message || [];
        const opts = state.cycles
            .map(
                (c) =>
                    `<option value="${frappe.utils.escape_html(c.name)}">${frappe.utils.escape_html(
                        c.cycle_name || c.name,
                    )} · ${c.start_date || ""}</option>`,
            )
            .join("");
        page.main.find("#plb-cycle").html(opts || `<option value="">${__("No cycles")}</option>`);
        if (state.cycles.length) {
            state.cycle = state.cycles[0].name;
            page.main.find("#plb-cycle").val(state.cycle);
            loadData();
        }
    } catch (e) {
        console.warn("bootstrap failed", e);
    }
}

async function loadData() {
    if (!state.cycle) return;
    state.page.main.find("#plb-table").html(`<div class="hr-empty"><div class="hr-empty-sub">${__("Loading…")}</div></div>`);
    state.page.main.find("#plb-podium").html("");
    try {
        const res = await frappe.call({
            method: "orderlift.orderlift_hr.api.performance.get_performance_leaderboard",
            args: { appraisal_cycle: state.cycle, filters: state.filters },
        });
        const data = res.message || {};
        state.admin = !!data.admin;
        state.rows = data.rows || [];
        state.categories = data.categories || [];
        state.metrics = data.metrics || [];
        state.metricsByCategory = {};
        state.metricsById = {};
        state.metrics.forEach((m) => {
            state.metricsById[m.metric] = m;
            (state.metricsByCategory[m.category] = state.metricsByCategory[m.category] || []).push(m);
        });
        if (state.admin) {
            state.page.main.find("#plb-toolbar").css("display", "flex");
            state.page.main.find("#plb-kpis").css("display", "grid");
            state.page.main.find("#plb-cat-chips").css("display", "flex");
            updateKpis(state.rows, state.metrics, state.categories);
            renderChips();
        } else {
            state.page.main.find("#plb-kpis").hide();
            state.page.main.find("#plb-cat-chips").hide();
        }
        renderPodium(state.rows);
        renderTable(state.rows);
    } catch (e) {
        state.page.main
            .find("#plb-table")
            .html(`<div class="hr-empty"><div class="hr-empty-title">${__("Failed to load")}</div><div class="hr-empty-sub">${__("Could not fetch leaderboard.")}</div></div>`);
    }
}

function updateKpis(rows, metrics, categories) {
    const m = state.page.main;
    const count = rows.length;
    const scores = rows.map((r) => r.score || 0).sort((a, b) => a - b);
    const median = count
        ? count % 2
            ? scores[(count - 1) / 2]
            : (scores[count / 2 - 1] + scores[count / 2]) / 2
        : 0;
    const top = rows[0];
    m.find("#plb-kpi-emp").text(count || "—");
    m.find("#plb-kpi-emp-hint").text(
        rows.filter((r) => (r.score || 0) >= 60).length + " " + __("scoring ≥ 60"),
    );
    m.find("#plb-kpi-median").text(count ? median.toFixed(1) : "—");
    const bandLabel =
        median >= 80
            ? __("Strong — most are on target")
            : median >= 60
            ? __("Healthy")
            : median >= 40
            ? __("Mixed — review middle band")
            : __("Below par — needs attention");
    m.find("#plb-kpi-band-text").text(count ? bandLabel : "—");
    m.find("#plb-kpi-top").text(top ? (top.score || 0).toFixed(1) : "—");
    m.find("#plb-kpi-top-name").text(top ? top.employee_name || top.employee : "—");
    m.find("#plb-kpi-metric").text(metrics.length || "—");
    m.find("#plb-kpi-cat-hint").text(`${categories.length} ${__("categories")}`);
}

function renderChips() {
    if (!state.admin) return;
    const m = state.page.main;
    const counts = { ALL: state.metrics.length };
    state.categories.forEach((c) => {
        counts[c] = (state.metricsByCategory[c] || []).length;
    });
    const items = [
        {
            key: "ALL",
            label: __("All categories"),
            color: "var(--hr-primary)",
        },
        ...state.categories.map((c) => ({ key: c, label: c, color: catColor(c) })),
    ];
    const html = items
        .map(
            (it) => `
            <button class="plb-cat-pill ${state.view.category === it.key ? "is-active" : ""}" data-category="${frappe.utils.escape_html(it.key)}">
                <span class="plb-pill-dot" style="background:${it.color}"></span>
                ${frappe.utils.escape_html(it.label)}
                <span class="plb-pill-count">${counts[it.key] || 0}</span>
            </button>`,
        )
        .join("");
    m.find("#plb-cat-chips").html(html);
}

function initials(name) {
    if (!name) return "?";
    const parts = String(name).split(/\s+/).filter(Boolean);
    if (!parts.length) return "?";
    return (parts[0][0] + (parts[1] ? parts[1][0] : "")).toUpperCase();
}

function renderPodium(rows) {
    const top = rows.slice(0, 3);
    if (!top.length) {
        state.page.main.find("#plb-podium").html("");
        return;
    }
    const ranked = [null, null, null];
    top.forEach((r) => {
        if (r.rank === 1) ranked[1] = r;
        else if (r.rank === 2) ranked[0] = r;
        else if (r.rank === 3) ranked[2] = r;
    });
    const variant = ["silver", "gold", "bronze"];
    const html = ranked
        .map((r, i) => {
            if (!r) {
                return `<div class="hr-podium-card hr-podium-card--${variant[i]} hr-podium-card--empty">
                    <div class="hr-podium-rank">—</div>
                </div>`;
            }
            const isFirst = r.rank === 1;
            const classes = [
                "hr-podium-card",
                `hr-podium-card--${variant[i]}`,
                isFirst ? "hr-podium-card--first" : "",
                state.admin ? "hr-podium-card--clickable" : "",
                r.is_self ? "hr-podium-card--self" : "",
            ]
                .filter(Boolean)
                .join(" ");
            const badge =
                r.rank === 1
                    ? ICONS.trophy
                    : r.rank === 2
                    ? ICONS.medal
                    : ICONS.award;
            const topCat = Object.entries(r.categories || {}).sort((a, b) => b[1] - a[1])[0];
            const topCatStr = topCat ? `${topCat[0]} · ${topCat[1].toFixed(0)}` : "—";
            return `<div class="${classes}" data-employee="${frappe.utils.escape_html(r.employee)}">
                <div class="hr-podium-badge">${badge}</div>
                <div class="hr-podium-rank">#${r.rank}</div>
                <div class="hr-podium-avatar hr-podium-avatar--${variant[i]}">${initials(r.employee_name || r.employee)}</div>
                <div class="hr-podium-name">${frappe.utils.escape_html(r.employee_name || r.employee)}</div>
                <div class="hr-podium-meta">${frappe.utils.escape_html(r.department || "—")}</div>
                <div class="hr-podium-score">${(r.score || 0).toFixed(1)}</div>
                <div class="hr-podium-stats">
                    <span>${__("Top")} <strong>${frappe.utils.escape_html(topCatStr)}</strong></span>
                    <span>${__("Metrics")} <strong>${r.metric_count || 0}</strong></span>
                </div>
            </div>`;
        })
        .join("");
    state.page.main.find("#plb-podium").html(html);
}

function sortRows(rows) {
    const { key, dir } = state.view.sort;
    const mul = dir === "asc" ? 1 : -1;
    const get = (r) => {
        if (key === "rank") return r.rank;
        if (key === "score") return r.score || 0;
        if (key === "name") return (r.employee_name || r.employee || "").toLowerCase();
        if (key.startsWith("cat:")) return r.categories?.[key.slice(4)] ?? -1;
        if (key.startsWith("metric:")) return r.metric_scores?.[key.slice(7)]?.score ?? -1;
        return 0;
    };
    return [...rows].sort((a, b) => {
        const va = get(a), vb = get(b);
        if (va === vb) return 0;
        if (typeof va === "string") return va.localeCompare(vb) * mul;
        return (va < vb ? -1 : 1) * mul;
    });
}

function sortIndicator(key) {
    const active = state.view.sort.key === key;
    const cls = active ? (state.view.sort.dir === "asc" ? "is-asc" : "is-desc") : "";
    return `<svg class="plb-sort-ind ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>`;
}

function sortHeader(label, key, sub) {
    const active = state.view.sort.key === key;
    const cls = active ? (state.view.sort.dir === "asc" ? "is-asc" : "is-desc") : "";
    return `<button class="plb-sort-btn ${cls}" data-sort="${key}">${label}${sub ? `<div class="plb-th-sub">${sub}</div>` : ""}<svg class="plb-sort-ind ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg></button>`;
}

function bandClass(score) {
    if (score == null) return "hr-score-band hr-score-band--0";
    if (score >= 80) return "hr-score-band hr-score-band--3";
    if (score >= 60) return "hr-score-band hr-score-band--2";
    if (score >= 40) return "hr-score-band hr-score-band--1";
    return "hr-score-band hr-score-band--0";
}

function bandHex(score) {
    if (score >= 80) return "#039855";
    if (score >= 60) return "#7C9A3E";
    if (score >= 40) return "#DC6803";
    return "#D92D20";
}

function renderTable(rows) {
    if (!rows.length) {
        state.page.main
            .find("#plb-table")
            .html(`<div class="hr-empty">${ICONS.target}
                <div class="hr-empty-title">${__("No data for this cycle yet")}</div>
                <div class="hr-empty-sub">${__("Ask the admin to recompute snapshots from the Cycle Dashboard.")}</div>
            </div>`);
        state.page.main.find("#plb-card-sub").text(__("0 employees"));
        return;
    }
    const sorted = sortRows(rows);
    state.page.main.find("#plb-card-sub").text(`${sorted.length} ${__("employees ranked")}`);

    const cat = state.view.category;
    const isAllView = cat === "ALL";
    state.page.main
        .find("#plb-card-title")
        .text(isAllView ? __("Full Ranking") : `${__("Detail")} · ${cat}`);

    let columnDefs;
    if (isAllView) {
        columnDefs = (state.categories || []).map((c) => ({ key: `cat:${c}`, label: c, kind: "category", color: catColor(c) }));
    } else if (state.admin && (state.metricsByCategory[cat] || []).length) {
        columnDefs = state.metricsByCategory[cat].map((m) => ({
            key: `metric:${m.metric}`,
            label: m.metric_name,
            sub: m.unit || "",
            kind: "metric",
            metric: m.metric,
            color: catColor(cat),
        }));
    } else {
        columnDefs = [];
    }

    const head = `<thead><tr>
        <th style="width:64px;">${sortHeader(__("Rank"), "rank")}</th>
        <th>${sortHeader(__("Employee"), "name")}</th>
        <th class="plb-score-cell">${sortHeader(__("Score"), "score", isAllView ? __("Weighted average") : `${cat} ${__("avg")}`)}</th>
        ${columnDefs
            .map(
                (d) =>
                    `<th style="text-align:${d.kind === "metric" ? "center" : "left"};">${sortHeader(
                        frappe.utils.escape_html(d.label),
                        d.key,
                        d.sub ? frappe.utils.escape_html(d.sub) : "",
                    )}</th>`,
            )
            .join("")}
        ${state.admin ? `<th></th>` : ""}
    </tr></thead>`;

    const body = sorted
        .map((r) => {
            const cells = columnDefs
                .map((d) => {
                    if (d.kind === "category") {
                        const v = r.categories && r.categories[d.key.slice(4)];
                        if (v == null) return `<td><span class="hr-chip">—</span></td>`;
                        return `<td><span class="${bandClass(v)}">${v.toFixed(1)}</span></td>`;
                    }
                    const ms = r.metric_scores && r.metric_scores[d.metric];
                    if (!ms) return `<td class="plb-metric-cell"><span class="hr-chip">—</span></td>`;
                    return `<td class="plb-metric-cell">
                        <div class="plb-metric-score">${(ms.score || 0).toFixed(0)}</div>
                        <div class="plb-metric-display">${frappe.utils.escape_html(ms.value_display || "")}</div>
                    </td>`;
                })
                .join("");
            const actions = state.admin
                ? `<td><button class="hr-btn hr-btn--ghost plb-drilldown-btn" data-employee="${frappe.utils.escape_html(r.employee)}" style="height:30px; padding:0 12px; font-size:12px;">${__("Detail")}</button></td>`
                : "";
            const rankCls =
                r.rank === 1
                    ? "hr-rank hr-rank--gold"
                    : r.rank === 2
                    ? "hr-rank hr-rank--silver"
                    : r.rank === 3
                    ? "hr-rank hr-rank--bronze"
                    : "hr-rank";
            const selfCls = r.is_self ? "hr-table-row hr-table-row--self plb-row" : "hr-table-row plb-row";
            // category stack visualisation only in ALL view
            const stack = isAllView
                ? (() => {
                      const entries = (state.categories || [])
                          .map((c) => ({ cat: c, v: r.categories?.[c] || 0 }))
                          .filter((e) => e.v > 0);
                      const total = entries.reduce((s, e) => s + e.v, 0) || 1;
                      const segs = entries
                          .map(
                              (e) =>
                                  `<div class="plb-cat-stack-seg" style="width:${(e.v / total) * 100}%; background:${catColor(e.cat)}" title="${frappe.utils.escape_html(e.cat)}: ${e.v.toFixed(1)}"></div>`,
                          )
                          .join("");
                      return `<div class="plb-cat-stack">${segs}</div>`;
                  })()
                : `<div class="hr-bar"><div class="hr-bar-fill" style="width:${Math.min(100, r.score || 0)}%"></div></div>`;
            return `<tr class="${selfCls}" data-employee="${frappe.utils.escape_html(r.employee)}">
                <td><span class="${rankCls}">${r.rank}</span></td>
                <td>
                    <div class="hr-emp">
                        <div class="hr-emp-avatar">${initials(r.employee_name || r.employee)}</div>
                        <div class="hr-emp-text">
                            <div class="hr-emp-name">${frappe.utils.escape_html(r.employee_name || r.employee)}${
                r.is_self ? `<span class="hr-self-pill">${__("You")}</span>` : ""
            }</div>
                            <div class="hr-emp-meta">${frappe.utils.escape_html(r.department || "—")}${
                r.designation ? ` · ${frappe.utils.escape_html(r.designation)}` : ""
            }</div>
                        </div>
                    </div>
                </td>
                <td class="plb-score-cell">
                    <div class="plb-score-val">${(r.score || 0).toFixed(1)}</div>
                    ${stack}
                </td>
                ${cells}
                ${actions}
            </tr>`;
        })
        .join("");
    state.page.main
        .find("#plb-table")
        .html(`<table class="hr-table">${head}<tbody>${body}</tbody></table>`);
}

function exportCsv() {
    if (!state.rows.length) return;
    const cat = state.view.category;
    let header, columnDefs;
    if (cat === "ALL") {
        columnDefs = (state.categories || []).map((c) => ({ key: c, label: c, kind: "category" }));
    } else {
        columnDefs = (state.metricsByCategory[cat] || []).map((m) => ({ key: m.metric, label: m.metric_name, kind: "metric" }));
    }
    header = ["Rank", "Employee", "Department", "Score", ...columnDefs.map((d) => d.label)];
    const lines = [header.map(csvCell).join(",")];
    for (const r of sortRows(state.rows)) {
        const cols = [
            r.rank,
            r.employee_name || r.employee,
            r.department || "",
            r.score,
            ...columnDefs.map((d) =>
                d.kind === "category" ? r.categories?.[d.key] ?? "" : r.metric_scores?.[d.key]?.score ?? "",
            ),
        ];
        lines.push(cols.map(csvCell).join(","));
    }
    const blob = new Blob([lines.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `performance-${state.cycle}${cat === "ALL" ? "" : "-" + cat}.csv`;
    a.click();
    URL.revokeObjectURL(url);
}

function csvCell(value) {
    const s = String(value ?? "");
    if (s.includes(",") || s.includes('"') || s.includes("\n")) {
        return `"${s.replaceAll('"', '""')}"`;
    }
    return s;
}

async function openDrilldown(employee) {
    if (!employee || !state.cycle) return;
    const back = $('<div class="hr-drawer-backdrop"></div>').appendTo("body");
    const drawer = $(`<div class="hr-drawer">
        <div class="hr-drawer-card">
            <div class="hr-drawer-head">
                <div>
                    <div class="hr-drawer-title">${__("Loading…")}</div>
                    <div class="hr-drawer-sub">${frappe.utils.escape_html(employee)}</div>
                </div>
                <button class="hr-drawer-close" type="button">${ICONS.close}</button>
            </div>
            <div class="plb-drill-body"><div class="hr-empty"><div class="hr-empty-sub">${__("Loading metrics…")}</div></div></div>
        </div>
    </div>`).appendTo("body");
    const close = () => {
        drawer.remove();
        back.remove();
    };
    back.on("click", close);
    drawer.on("click", ".hr-drawer-close", close);

    try {
        const res = await frappe.call({
            method: "orderlift.orderlift_hr.api.performance.get_employee_performance",
            args: { employee, appraisal_cycle: state.cycle },
        });
        const rows = (res.message && res.message.rows) || [];
        const row = state.rows.find((r) => r.employee === employee);
        const name = row?.employee_name || employee;
        drawer.find(".hr-drawer-title").text(name);
        drawer
            .find(".hr-drawer-sub")
            .html(`${frappe.utils.escape_html(row?.department || "—")} · ${rows.length} ${__("metrics")} · ${__("Score")} <b>${row?.score?.toFixed(1) || "—"}</b>`);

        // Group by category
        const groups = {};
        rows.forEach((m) => {
            (groups[m.category || "Other"] = groups[m.category || "Other"] || []).push(m);
        });
        const sortedCats = Object.keys(groups).sort();
        const blocks = sortedCats
            .map((c) => {
                const items = groups[c];
                const avg = items.reduce((s, m) => s + (m.score || 0), 0) / (items.length || 1);
                const metricsHtml = items
                    .map((m) => {
                        const score = m.score || 0;
                        const target = m.target_value;
                        const targetStr =
                            target != null && !isNaN(target) ? `${__("Target")}: <b>${target}</b> · ` : "";
                        return `<div class="plb-drill-metric">
                            <div>
                                <div class="plb-drill-metric-name">${frappe.utils.escape_html(m.metric_name)}</div>
                                <div class="plb-drill-metric-meta">${targetStr}${__("Actual")}: <b>${frappe.utils.escape_html(m.value_display || "—")}</b></div>
                            </div>
                            <div class="plb-drill-metric-score ${bandClass(score)}">${score.toFixed(0)}</div>
                            <div class="plb-drill-metric-bar"><div class="plb-drill-metric-bar-fill" style="width:${Math.min(100, score)}%; background:${bandHex(score)}"></div></div>
                        </div>`;
                    })
                    .join("");
                return `<div class="plb-drill-cat">
                    <div class="plb-drill-cat-head">
                        <div class="plb-drill-cat-title"><span class="plb-drill-cat-dot" style="background:${catColor(c)}"></span>${frappe.utils.escape_html(c)} <span class="hr-chip" style="margin-left:6px;">${items.length}</span></div>
                        <div class="plb-drill-cat-avg">${__("Avg")}: ${avg.toFixed(1)}</div>
                    </div>
                    <div class="plb-drill-metrics">${metricsHtml}</div>
                </div>`;
            })
            .join("");
        drawer
            .find(".plb-drill-body")
            .html(
                rows.length
                    ? blocks
                    : `<div class="hr-empty"><div class="hr-empty-sub">${__("No snapshots yet.")}</div></div>`,
            );
    } catch (e) {
        drawer.find(".hr-drawer-title").text(__("Failed to load"));
    }
}
