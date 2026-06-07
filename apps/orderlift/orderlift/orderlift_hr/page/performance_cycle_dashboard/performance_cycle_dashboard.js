frappe.pages["performance-cycle-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Performance Cycle Dashboard"),
        single_column: true,
    });
    page.main.addClass("hr-root perf-theme pcd-root");
    injectStyles();
    state.page = page;
    renderSkeleton(page);
    bind(page);
    bootstrap(page);
};

const state = {
    page: null,
    cycles: [],
    profiles: [],
    metrics: [],
    cycle: null,
    profile: null,
    grid: { employees: [], metrics: [], snapshots: {} },
};

const ICONS = {
    users: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    target: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>',
    activity: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
    sync: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4-4.64 4.36A9 9 0 0 1 3.51 15"/></svg>',
    refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>',
    award: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="6"/><path d="M15.477 12.89 17 22l-5-3-5 3 1.523-9.11"/></svg>',
};

function injectStyles() {
    if (document.getElementById("pcd-styles")) return;
    const css = `
    .pcd-status { font-size: 12px; color: var(--hr-muted); margin-left: 6px; align-self: center; }
    .pcd-grid-wrap { overflow-x: auto; max-height: 70vh; }
    table.pcd-grid {
        border-collapse: separate;
        border-spacing: 0;
        font-size: 12px;
        min-width: 100%;
    }
    table.pcd-grid th, table.pcd-grid td {
        border-bottom: 1px solid var(--hr-line-soft);
        border-right: 1px solid var(--hr-line-soft);
        padding: 10px 12px;
        text-align: center;
        white-space: nowrap;
    }
    table.pcd-grid thead th {
        background: var(--hr-bg);
        color: var(--hr-muted);
        font-weight: 700;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: .06em;
        position: sticky;
        top: 0;
        z-index: 3;
        border-bottom: 2px solid var(--hr-line);
    }
    table.pcd-grid thead th .pcd-th-cat {
        font-size: 9px;
        opacity: .65;
        margin-top: 2px;
        font-weight: 600;
        text-transform: none;
        letter-spacing: 0;
    }
    table.pcd-grid td.emp {
        text-align: left;
        background: var(--hr-card);
        position: sticky;
        left: 0;
        z-index: 2;
        border-right: 2px solid var(--hr-line);
        min-width: 200px;
    }
    table.pcd-grid thead th.emp-th {
        position: sticky;
        left: 0;
        z-index: 4;
        background: var(--hr-bg);
        text-align: left;
        border-right: 2px solid var(--hr-line);
    }
    table.pcd-grid tr:hover td.emp { background: var(--hr-primary-50); }
    table.pcd-grid tr:hover td:not(.emp) { background: var(--hr-line-soft); }
    .pcd-val-hint {
        font-size: 10px;
        color: var(--hr-muted);
        margin-top: 3px;
    }
    .pcd-dash { color: var(--hr-line); font-weight: 600; }
    `;
    const tag = document.createElement("style");
    tag.id = "pcd-styles";
    tag.textContent = css;
    document.head.appendChild(tag);
}

function renderSkeleton(page) {
    page.main.html(`
        <div class="hr-wrap">
            <div class="hr-hero">
                <div>
                    <div class="hr-eyebrow">${__("Orderlift")} · ${__("Performance")}</div>
                    <h1 class="hr-title">${__("Performance Cycle Dashboard")}</h1>
                    <div class="hr-sub">${__("Recompute metrics, sync to ERPNext Goals and preview Appraisal-ready scores before signing.")}</div>
                </div>
            </div>

            <div class="hr-kpis" id="pcd-kpis">
                <div class="hr-kpi">
                    <div class="hr-kpi-icon hr-kpi-icon--indigo">${ICONS.users}</div>
                    <div class="hr-kpi-label">${__("Employees")}</div>
                    <div class="hr-kpi-value" id="pcd-kpi-emp">—</div>
                    <div class="hr-kpi-hint">${__("In selected cycle")}</div>
                </div>
                <div class="hr-kpi">
                    <div class="hr-kpi-icon hr-kpi-icon--purple">${ICONS.target}</div>
                    <div class="hr-kpi-label">${__("Metrics")}</div>
                    <div class="hr-kpi-value" id="pcd-kpi-metric">—</div>
                    <div class="hr-kpi-hint">${__("Tracked this cycle")}</div>
                </div>
                <div class="hr-kpi">
                    <div class="hr-kpi-icon hr-kpi-icon--green">${ICONS.activity}</div>
                    <div class="hr-kpi-label">${__("Average Score")}</div>
                    <div class="hr-kpi-value" id="pcd-kpi-avg">—</div>
                    <div class="hr-kpi-hint">${__("Weighted across all metrics")}</div>
                </div>
                <div class="hr-kpi">
                    <div class="hr-kpi-icon hr-kpi-icon--amber">${ICONS.award}</div>
                    <div class="hr-kpi-label">${__("Top Score")}</div>
                    <div class="hr-kpi-value" id="pcd-kpi-top">—</div>
                    <div class="hr-kpi-hint" id="pcd-kpi-top-name">—</div>
                </div>
            </div>

            <div class="hr-toolbar">
                <select id="pcd-cycle" class="hr-select"><option>${__("Loading…")}</option></select>
                <select id="pcd-profile" class="hr-select"><option value="">${__("Auto-resolve profile")}</option></select>
                <button id="pcd-recompute" class="hr-btn hr-btn--primary">${ICONS.refresh}<span>${__("Recompute all")}</span></button>
                <button id="pcd-sync-goals" class="hr-btn hr-btn--secondary">${ICONS.sync}<span>${__("Sync to Goals")}</span></button>
                <span id="pcd-status" class="pcd-status"></span>
            </div>

            <div class="hr-card">
                <div class="hr-card-head">
                    <div>
                        <div class="hr-card-title">${__("Employees × Metrics")}</div>
                        <div class="hr-card-sub" id="pcd-grid-sub">${__("Pick a cycle to view the grid.")}</div>
                    </div>
                </div>
                <div id="pcd-grid" class="pcd-grid-wrap">
                    <div class="hr-empty">
                        ${ICONS.target}
                        <div class="hr-empty-title">${__("Pick a cycle to view the grid")}</div>
                        <div class="hr-empty-sub">${__("Run Recompute all to populate snapshots for every appraisee.")}</div>
                    </div>
                </div>
            </div>
        </div>
    `);
}

function bind(page) {
    page.main.on("change", "#pcd-cycle", function () {
        state.cycle = $(this).val();
        loadGrid();
    });
    page.main.on("change", "#pcd-profile", function () {
        state.profile = $(this).val() || null;
        loadGrid();
    });
    page.main.on("click", "#pcd-recompute", recompute);
    page.main.on("click", "#pcd-sync-goals", syncGoals);
}

async function bootstrap(page) {
    try {
        const [cycles, profiles] = await Promise.all([
            frappe.call({
                method: "frappe.client.get_list",
                args: {
                    doctype: "Appraisal Cycle",
                    fields: ["name", "cycle_name", "start_date", "status"],
                    order_by: "start_date desc",
                    limit_page_length: 50,
                },
            }),
            frappe.call({
                method: "frappe.client.get_list",
                args: {
                    doctype: "Performance Profile",
                    fields: ["name", "profile_name", "target_department"],
                    filters: { is_active: 1 },
                    limit_page_length: 50,
                },
            }),
        ]);
        state.cycles = cycles.message || [];
        state.profiles = profiles.message || [];
        page.main.find("#pcd-cycle").html(
            state.cycles
                .map(
                    (c) =>
                        `<option value="${frappe.utils.escape_html(c.name)}">${frappe.utils.escape_html(
                            c.cycle_name || c.name,
                        )} · ${c.status || ""}</option>`,
                )
                .join("") || `<option value="">${__("No cycles")}</option>`,
        );
        const profileOpts = state.profiles
            .map(
                (p) =>
                    `<option value="${frappe.utils.escape_html(p.name)}">${frappe.utils.escape_html(
                        p.profile_name,
                    )}</option>`,
            )
            .join("");
        page.main.find("#pcd-profile").append(profileOpts);
        if (state.cycles.length) {
            state.cycle = state.cycles[0].name;
            page.main.find("#pcd-cycle").val(state.cycle);
            loadGrid();
        }
    } catch (e) {
        console.warn("bootstrap failed", e);
    }
}

function updateKpis(rows, metricCount) {
    const empCount = rows.length;
    const scores = rows.map((r) => r.score || 0);
    const avg = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
    const top = rows[0];
    state.page.main.find("#pcd-kpi-emp").text(empCount || "—");
    state.page.main.find("#pcd-kpi-metric").text(metricCount || "—");
    state.page.main.find("#pcd-kpi-avg").text(empCount ? avg.toFixed(1) : "—");
    state.page.main.find("#pcd-kpi-top").text(top ? (top.score || 0).toFixed(1) : "—");
    state.page.main.find("#pcd-kpi-top-name").text(top ? top.employee_name || top.employee : "—");
}

async function loadGrid() {
    if (!state.cycle) return;
    state.page.main.find("#pcd-grid").html(`<div class="hr-empty"><div class="hr-empty-sub">${__("Loading…")}</div></div>`);
    state.page.main.find("#pcd-grid-sub").text(__("Loading…"));
    try {
        const board = await frappe.call({
            method: "orderlift.orderlift_hr.api.performance.get_performance_leaderboard",
            args: { appraisal_cycle: state.cycle },
        });
        const rows = (board.message && board.message.rows) || [];
        if (!rows.length) {
            updateKpis([], 0);
            state.page.main
                .find("#pcd-grid")
                .html(`<div class="hr-empty">${ICONS.target}
                    <div class="hr-empty-title">${__("No snapshots yet")}</div>
                    <div class="hr-empty-sub">${__("Hit Recompute all to compute snapshots for every appraisee in this cycle.")}</div>
                </div>`);
            state.page.main.find("#pcd-grid-sub").text(__("0 employees · 0 metrics"));
            return;
        }
        const details = await Promise.all(
            rows.map((r) =>
                frappe.call({
                    method: "orderlift.orderlift_hr.api.performance.get_employee_performance",
                    args: { employee: r.employee, appraisal_cycle: state.cycle },
                }),
            ),
        );
        const metricSet = new Set();
        const metricMeta = {};
        const byEmployee = {};
        rows.forEach((r, idx) => {
            const drow = (details[idx] && details[idx].message && details[idx].message.rows) || [];
            byEmployee[r.employee] = { name: r.employee_name || r.employee, department: r.department, rows: drow };
            drow.forEach((m) => {
                metricSet.add(m.metric);
                metricMeta[m.metric] = { name: m.metric_name, category: m.category };
            });
        });
        const metrics = Array.from(metricSet).sort((a, b) => {
            const ca = (metricMeta[a] || {}).category || "";
            const cb = (metricMeta[b] || {}).category || "";
            if (ca !== cb) return ca.localeCompare(cb);
            return a.localeCompare(b);
        });
        updateKpis(rows, metrics.length);
        renderGrid(rows, metrics, metricMeta, byEmployee);
        state.page.main
            .find("#pcd-grid-sub")
            .text(`${rows.length} ${__("employees")} · ${metrics.length} ${__("metrics")}`);
    } catch (e) {
        state.page.main
            .find("#pcd-grid")
            .html(`<div class="hr-empty"><div class="hr-empty-title">${__("Failed to load")}</div></div>`);
    }
}

function initials(name) {
    if (!name) return "?";
    const parts = String(name).split(/\s+/).filter(Boolean);
    if (!parts.length) return "?";
    return (parts[0][0] + (parts[1] ? parts[1][0] : "")).toUpperCase();
}

function renderGrid(rows, metrics, meta, byEmployee) {
    const header = [
        `<th class="emp-th">${__("Employee")}</th>`,
        ...metrics.map((m) => {
            const mm = meta[m] || {};
            return `<th title="${frappe.utils.escape_html(m)}">${frappe.utils.escape_html(mm.name || m)}<div class="pcd-th-cat">${frappe.utils.escape_html(mm.category || "")}</div></th>`;
        }),
    ].join("");
    const body = rows
        .map((r) => {
            const drow = byEmployee[r.employee] && byEmployee[r.employee].rows;
            const byMetric = {};
            (drow || []).forEach((m) => (byMetric[m.metric] = m));
            const cells = metrics
                .map((m) => {
                    const v = byMetric[m];
                    if (!v) return `<td><span class="pcd-dash">—</span></td>`;
                    const score = v.score || 0;
                    const band = score >= 80 ? 3 : score >= 60 ? 2 : score >= 40 ? 1 : 0;
                    return `<td>
                        <span class="hr-score-band hr-score-band--${band}">${score.toFixed(0)}</span>
                        <div class="pcd-val-hint">${frappe.utils.escape_html(v.value_display || "")}</div>
                    </td>`;
                })
                .join("");
            return `<tr>
                <td class="emp">
                    <div class="hr-emp">
                        <div class="hr-emp-avatar">${initials(r.employee_name || r.employee)}</div>
                        <div class="hr-emp-text">
                            <div class="hr-emp-name">${frappe.utils.escape_html(r.employee_name || r.employee)}</div>
                            <div class="hr-emp-meta">${frappe.utils.escape_html(r.department || "—")}</div>
                        </div>
                    </div>
                </td>${cells}
            </tr>`;
        })
        .join("");
    state.page.main
        .find("#pcd-grid")
        .html(`<table class="pcd-grid"><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table>`);
}

async function recompute() {
    if (!state.cycle) return;
    const btn = state.page.main.find("#pcd-recompute");
    btn.prop("disabled", true);
    setStatus(__("Recomputing…"));
    try {
        const res = await frappe.call({
            method: "orderlift.orderlift_hr.api.performance.recompute_cycle",
            args: { appraisal_cycle: state.cycle, profile: state.profile },
        });
        const count = (res.message && res.message.count) || 0;
        frappe.show_alert({ message: `${__("Recomputed")} ${count} ${__("employees")}`, indicator: "green" });
        loadGrid();
    } catch (e) {
        frappe.show_alert({ message: __("Recompute failed"), indicator: "red" });
    } finally {
        btn.prop("disabled", false);
        setStatus("");
    }
}

async function syncGoals() {
    if (!state.cycle) return;
    const btn = state.page.main.find("#pcd-sync-goals");
    btn.prop("disabled", true);
    setStatus(__("Syncing to Goals…"));
    try {
        const res = await frappe.call({
            method: "orderlift.orderlift_hr.api.performance.sync_snapshots_to_goals",
            args: { appraisal_cycle: state.cycle, profile: state.profile },
        });
        const written = (res.message && res.message.written) || 0;
        const skipped = (res.message && res.message.skipped) || 0;
        frappe.show_alert({
            message: `${__("Goals written")}: ${written} · ${__("Skipped")} (no KRA): ${skipped}`,
            indicator: "green",
        });
    } catch (e) {
        frappe.show_alert({ message: __("Goal sync failed"), indicator: "red" });
    } finally {
        btn.prop("disabled", false);
        setStatus("");
    }
}

function setStatus(text) {
    state.page.main.find("#pcd-status").text(text);
}
