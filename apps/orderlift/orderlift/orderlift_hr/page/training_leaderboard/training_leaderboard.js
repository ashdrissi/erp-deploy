frappe.pages["training-leaderboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Training Leaderboard"),
        single_column: true,
    });

    page.main.addClass("tlb-root");
    injectStyles();
    state.page = page;
    renderSkeleton(page);
    bindFilters(page);
    loadData(page);
};

const state = {
    page: null,
    filters: {},
    viewer: { is_admin: false, employee: null },
    rows: [],
    weights: {},
};

const ICONS = {
    trophy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></svg>',
    medal: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7.21 15 2.66 7.14a2 2 0 0 1 .13-2.2L4.4 2.8A2 2 0 0 1 6 2h12a2 2 0 0 1 1.6.8l1.6 2.14a2 2 0 0 1 .14 2.2L16.79 15"/><path d="M11 12 5.12 2.2"/><path d="M13 12l5.88-9.8"/><path d="M8 7h8"/><circle cx="12" cy="17" r="5"/><path d="M12 18v-2h-.5"/></svg>',
    award: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="6"/><path d="M15.477 12.89 17 22l-5-3-5 3 1.523-9.11"/></svg>',
    target: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>',
    book: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/></svg>',
    clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
    download: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
    filter: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>',
    close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
    check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
    sparkles: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/><path d="M5 3v4"/><path d="M19 17v4"/><path d="M3 5h4"/><path d="M17 19h4"/></svg>',
};

function renderSkeleton(page) {
    page.main.html(`
        <div class="tlb-wrapper">
            <div class="tlb-hero">
                <div class="tlb-hero-text">
                    <div class="tlb-eyebrow">${__("Orderlift")} · ${__("Performance")}</div>
                    <h1 class="tlb-title">${__("Training Leaderboard")}</h1>
                    <div class="tlb-sub">${__("Ranked by training score — modules studied, quiz performance and recent activity.")}</div>
                </div>
                <div class="tlb-hero-side">
                    <div class="tlb-hero-trophy">${ICONS.trophy}</div>
                    <div id="tlb-weights" class="tlb-weights"></div>
                </div>
            </div>

            <div id="tlb-filters" class="tlb-filters" style="display:none;">
                <div class="tlb-filter-icon">${ICONS.filter}</div>
                <input class="tlb-filter" data-key="department" placeholder="${__("Department")}" />
                <input class="tlb-filter" data-key="designation" placeholder="${__("Designation")}" />
                <input class="tlb-filter" data-key="program" placeholder="${__("Program")}" />
                <button class="tlb-btn-ghost tlb-clear">${__("Clear")}</button>
                <button class="tlb-btn-primary tlb-export">${ICONS.download}<span>${__("Export CSV")}</span></button>
            </div>

            <div id="tlb-podium" class="tlb-podium"></div>

            <div class="tlb-card">
                <div class="tlb-card-head">
                    <div>
                        <div class="tlb-card-title">${__("Full Ranking")}</div>
                        <div class="tlb-card-sub" id="tlb-card-sub">${__("Loading…")}</div>
                    </div>
                </div>
                <div id="tlb-table" class="tlb-table-wrap"><div class="tlb-shimmer">${__("Loading leaderboard…")}</div></div>
            </div>
        </div>
    `);
}

function bindFilters(page) {
    page.main.on("input", ".tlb-filter", function () {
        const key = $(this).data("key");
        state.filters[key] = $(this).val();
        clearTimeout(state.timer);
        state.timer = setTimeout(() => loadData(page), 250);
    });
    page.main.on("click", ".tlb-clear", function () {
        state.filters = {};
        page.main.find(".tlb-filter").val("");
        loadData(page);
    });
    page.main.on("click", ".tlb-export", function () {
        exportCsv();
    });
}

async function loadData(page) {
    try {
        const res = await frappe.call({
            method: "orderlift.orderlift_hr.api.leaderboard.get_leaderboard",
            args: { filters: state.filters },
        });
        const data = res.message || {};
        state.viewer = data.viewer || {};
        state.weights = data.weights || {};
        state.rows = data.rows || [];
        if (state.viewer.is_admin) {
            page.main.find("#tlb-filters").css("display", "flex");
        }
        renderWeights(page, state.weights);
        renderPodium(page, state.rows);
        renderRows(page, state.rows);
    } catch (e) {
        console.warn("Leaderboard: failed to load", e);
        page.main.find("#tlb-table").html(`<div class="tlb-empty">${__("Failed to load leaderboard.")}</div>`);
    }
}

function renderWeights(page, weights) {
    const pct = (v) => Math.round((v || 0) * 100);
    page.main.find("#tlb-weights").html(`
        <div class="tlb-weight-row">
            <div class="tlb-weight-chip"><span class="tlb-weight-dot tlb-weight-mod"></span>${__("Modules")} <strong>${pct(weights.module)}%</strong></div>
            <div class="tlb-weight-chip"><span class="tlb-weight-dot tlb-weight-quiz"></span>${__("Quizzes")} <strong>${pct(weights.quiz)}%</strong></div>
            <div class="tlb-weight-chip"><span class="tlb-weight-dot tlb-weight-rec"></span>${__("Recency")} <strong>${pct(weights.recency)}%</strong></div>
        </div>
    `);
}

function renderPodium(page, rows) {
    const podiumWrap = page.main.find("#tlb-podium");
    if (!rows.length) {
        podiumWrap.empty();
        return;
    }
    const top3 = rows.slice(0, 3);
    while (top3.length < 3) top3.push(null);
    const [first, second, third] = top3;
    podiumWrap.html(`
        <div class="tlb-podium-grid">
            ${podiumCard(second, 2, "silver")}
            ${podiumCard(first, 1, "gold")}
            ${podiumCard(third, 3, "bronze")}
        </div>
    `);
    podiumWrap.find(".tlb-podium-card[data-employee]").on("click", function () {
        if (state.viewer.is_admin) {
            openEmployeeDrill($(this).data("employee"));
        }
    });
}

function podiumCard(row, rank, tier) {
    if (!row) {
        return `<div class="tlb-podium-card tlb-podium-empty tlb-podium-${tier}">
            <div class="tlb-podium-rank">#${rank}</div>
            <div class="tlb-podium-name">${__("—")}</div>
        </div>`;
    }
    const initialsText = initials(row.employee_name);
    const isFirst = rank === 1;
    const medal = tier === "gold" ? ICONS.trophy : ICONS.medal;
    const dataAttr = state.viewer.is_admin ? `data-employee="${frappe.utils.escape_html(row.employee)}"` : "";
    const clickable = state.viewer.is_admin ? "tlb-clickable" : "";
    return `
        <div class="tlb-podium-card tlb-podium-${tier} ${isFirst ? "tlb-podium-first" : ""} ${row.is_self ? "tlb-podium-self" : ""} ${clickable}" ${dataAttr}>
            <div class="tlb-podium-badge">${medal}</div>
            <div class="tlb-podium-rank">#${rank}</div>
            <div class="tlb-podium-avatar tlb-avatar-${tier}">${initialsText}</div>
            <div class="tlb-podium-name" title="${frappe.utils.escape_html(row.employee_name)}">${frappe.utils.escape_html(row.employee_name)}</div>
            <div class="tlb-podium-meta">${frappe.utils.escape_html(row.department || "—")}</div>
            <div class="tlb-podium-score">${row.total_score}</div>
            <div class="tlb-podium-stats">
                <span>${__("Modules")} <strong>${row.module_completion_pct}%</strong></span>
                <span>${__("Quiz")} <strong>${row.quiz_average_pct}%</strong></span>
            </div>
        </div>
    `;
}

function renderRows(page, rows) {
    const sub = rows.length
        ? __("Showing {0} employees", [rows.length])
        : __("No employees match these filters.");
    page.main.find("#tlb-card-sub").text(sub);

    if (!rows.length) {
        page.main.find("#tlb-table").html(`<div class="tlb-empty">${ICONS.target}<div>${__("No employees match these filters.")}</div></div>`);
        return;
    }
    const isAdmin = state.viewer.is_admin;
    const headers = isAdmin
        ? [__("Rank"), __("Employee"), __("Score"), __("Modules"), __("Quiz Avg"), __("Recency"), __("Last activity")]
        : [__("Rank"), __("Employee"), __("Score"), __("Modules"), __("Quiz Avg")];
    page.main.find("#tlb-table").html(`
        <table class="tlb-table">
            <thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead>
            <tbody>
                ${rows.map((row) => isAdmin ? adminRow(row) : employeeRow(row)).join("")}
            </tbody>
        </table>
    `);
    if (isAdmin) {
        page.main.find(".tlb-row").on("click", function () {
            openEmployeeDrill($(this).data("employee"));
        });
    }
}

function rankBadge(rank) {
    let cls = "tlb-rank";
    if (rank === 1) cls += " tlb-rank-gold";
    else if (rank === 2) cls += " tlb-rank-silver";
    else if (rank === 3) cls += " tlb-rank-bronze";
    return `<span class="${cls}">${rank}</span>`;
}

function employeeCell(row) {
    return `
        <div class="tlb-emp">
            <div class="tlb-emp-avatar">${initials(row.employee_name)}</div>
            <div class="tlb-emp-text">
                <div class="tlb-emp-name">${frappe.utils.escape_html(row.employee_name)}${row.is_self ? `<span class="tlb-self-pill">${__("You")}</span>` : ""}</div>
                <div class="tlb-emp-meta">${frappe.utils.escape_html(row.department || "—")}${row.designation ? " · " + frappe.utils.escape_html(row.designation) : ""}</div>
            </div>
        </div>
    `;
}

function scoreCell(value) {
    return `<div class="tlb-score">${value}</div>`;
}

function progressCell(pct, sub) {
    const safe = Math.max(0, Math.min(100, pct || 0));
    return `
        <div class="tlb-progress-cell">
            <div class="tlb-progress-bar"><div class="tlb-progress-fill" style="width:${safe}%"></div></div>
            <div class="tlb-progress-text">${sub}</div>
        </div>
    `;
}

function adminRow(row) {
    return `
        <tr class="tlb-row ${row.is_self ? "tlb-row-self" : ""}" data-employee="${frappe.utils.escape_html(row.employee)}">
            <td>${rankBadge(row.rank)}</td>
            <td>${employeeCell(row)}</td>
            <td>${scoreCell(row.total_score)}</td>
            <td>${progressCell(row.module_completion_pct, `${row.modules_completed}/${row.modules_total} · ${row.module_completion_pct}%`)}</td>
            <td><span class="tlb-pill tlb-pill-quiz">${row.quiz_average_pct}%</span></td>
            <td><span class="tlb-pill tlb-pill-rec">${row.recent_activity_score}</span></td>
            <td class="tlb-muted">${row.last_activity ? frappe.datetime.prettyDate(row.last_activity) : "—"}</td>
        </tr>
    `;
}

function employeeRow(row) {
    return `
        <tr class="${row.is_self ? "tlb-row-self" : ""}">
            <td>${rankBadge(row.rank)}</td>
            <td>${employeeCell(row)}</td>
            <td>${scoreCell(row.total_score)}</td>
            <td>${progressCell(row.module_completion_pct, `${row.module_completion_pct}%`)}</td>
            <td><span class="tlb-pill tlb-pill-quiz">${row.quiz_average_pct}%</span></td>
        </tr>
    `;
}

function initials(text) {
    if (!text) return "??";
    const parts = String(text).trim().split(/\s+/);
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function exportCsv() {
    if (!(state.rows || []).length) return;
    const isAdmin = state.viewer.is_admin;
    const headers = isAdmin
        ? ["Rank", "Employee", "Employee Name", "Department", "Designation", "Score", "Modules Done", "Modules Total", "Modules %", "Quiz Avg %", "Recency", "Last Activity"]
        : ["Rank", "Employee Name", "Department", "Score", "Modules %", "Quiz Avg %"];
    const lines = [headers.join(",")];
    state.rows.forEach((row) => {
        const cols = isAdmin
            ? [row.rank, row.employee, row.employee_name, row.department || "", row.designation || "", row.total_score, row.modules_completed, row.modules_total, row.module_completion_pct, row.quiz_average_pct, row.recent_activity_score, row.last_activity || ""]
            : [row.rank, row.employee_name, row.department || "", row.total_score, row.module_completion_pct, row.quiz_average_pct];
        lines.push(cols.map(csvCell).join(","));
    });
    const csv = lines.join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "training-leaderboard.csv";
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
}

function csvCell(value) {
    const s = String(value ?? "");
    if (s.includes(",") || s.includes('"') || s.includes("\n")) {
        return `"${s.replaceAll('"', '""')}"`;
    }
    return s;
}

async function openEmployeeDrill(employeeName) {
    if (!employeeName) return;
    try {
        const res = await frappe.call({
            method: "orderlift.orderlift_hr.api.training.get_training_center_data",
            args: { employee: employeeName },
        });
        const data = res.message || {};
        const programs = data.programs || [];
        const stats = data.stats || {};
        const html = `
            <div class="tlb-drawer-card">
                <div class="tlb-drawer-head">
                    <div class="tlb-drawer-head-left">
                        <div class="tlb-drawer-avatar">${initials(employeeName)}</div>
                        <div>
                            <div class="tlb-drawer-title">${frappe.utils.escape_html(employeeName)}</div>
                            <div class="tlb-drawer-sub">${__("Module completion")}: <strong>${stats.module_completion_pct ?? 0}%</strong> · ${__("Quiz avg")}: <strong>${stats.quiz_average_pct ?? 0}%</strong></div>
                        </div>
                    </div>
                    <button class="tlb-drawer-close" id="tlb-drawer-close" aria-label="${__("Close")}">${ICONS.close}</button>
                </div>
                <div class="tlb-drawer-body">
                    ${programs.length ? programs.map(programDrill).join("") : `<div class="tlb-empty">${ICONS.book}<div>${__("No assigned programs.")}</div></div>`}
                </div>
            </div>
        `;
        let backdrop = $("#tlb-drawer-backdrop");
        if (!backdrop.length) {
            backdrop = $('<div id="tlb-drawer-backdrop" class="tlb-drawer-backdrop"></div>').appendTo("body");
            backdrop.on("click", function (e) {
                if (e.target === this) closeDrawer();
            });
        }
        let drawer = $("#tlb-drawer");
        if (!drawer.length) drawer = $('<div id="tlb-drawer" class="tlb-drawer"></div>').appendTo("body");
        drawer.html(html);
        backdrop.show();
        drawer.show();
        drawer.find("#tlb-drawer-close").on("click", closeDrawer);
    } catch (e) {
        frappe.show_alert({ message: __("Failed to load employee drilldown"), indicator: "red" });
    }
}

function closeDrawer() {
    $("#tlb-drawer").hide();
    $("#tlb-drawer-backdrop").hide();
}

function programDrill(program) {
    const levels = (program.levels || []).map((lvl) => `
        <div class="tlb-drill-level">
            <div class="tlb-drill-level-head">
                <span class="tlb-drill-level-title">${frappe.utils.escape_html(lvl.level_name)}</span>
                <span class="tlb-drill-pct">${lvl.completion_pct}%</span>
            </div>
            <div class="tlb-drill-bar"><div class="tlb-drill-bar-fill" style="width:${Math.max(0, Math.min(100, lvl.completion_pct || 0))}%"></div></div>
            <div class="tlb-drill-mods">${(lvl.modules || []).map(drillModule).join("")}</div>
        </div>
    `).join("");
    const flat = (program.flat_modules || []).map(drillModule).join("");
    const pct = Math.max(0, Math.min(100, program.completion_pct || 0));
    return `
        <div class="tlb-drill-program">
            <div class="tlb-drill-program-head">
                <div class="tlb-drill-program-title">${frappe.utils.escape_html(program.program_name)}</div>
                <div class="tlb-drill-program-pct">${program.completion_pct}%</div>
            </div>
            <div class="tlb-drill-bar tlb-drill-bar-lg"><div class="tlb-drill-bar-fill" style="width:${pct}%"></div></div>
            ${levels}
            ${flat ? `<div class="tlb-drill-flat">${flat}</div>` : ""}
        </div>
    `;
}

function drillModule(module) {
    const dot = module.studied ? "tlb-dot-done" : "tlb-dot-todo";
    const icon = module.studied ? ICONS.check : "";
    return `<div class="tlb-drill-mod ${module.studied ? "tlb-drill-mod-done" : ""}"><span class="tlb-dot ${dot}">${icon}</span><span>${frappe.utils.escape_html(module.title)}</span></div>`;
}

function injectStyles() {
    if (document.getElementById("tlb-styles")) return;
    const style = document.createElement("style");
    style.id = "tlb-styles";
    style.textContent = `
        :root {
            --tlb-primary: #7F56D9;
            --tlb-primary-700: #6941C6;
            --tlb-primary-50: #F4EBFF;
            --tlb-ink: #101828;
            --tlb-ink-2: #344054;
            --tlb-ink-3: #667085;
            --tlb-border: #EAECF0;
            --tlb-bg: #F9FAFB;
            --tlb-card: #ffffff;
            --tlb-gold: #f59e0b;
            --tlb-silver: #94a3b8;
            --tlb-bronze: #b45309;
        }
        .tlb-root { background: linear-gradient(180deg, #faf5ff 0%, #f8fafc 50%, #f1f5f9 100%); min-height: calc(100vh - 88px); }
        .tlb-root svg { width: 1em; height: 1em; display: inline-block; vertical-align: -0.125em; }
        .tlb-wrapper { max-width: 1280px; margin: 0 auto; padding: 28px 24px; }

        /* HERO */
        .tlb-hero {
            background: linear-gradient(135deg, #ffffff 0%, #faf5ff 100%);
            border: 1px solid var(--tlb-border);
            border-radius: 24px;
            padding: 28px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 24px;
            box-shadow: 0 20px 50px rgba(109,40,217,0.08);
            margin-bottom: 22px;
        }
        .tlb-eyebrow { font-size: 11px; letter-spacing: .14em; text-transform: uppercase; color: var(--tlb-primary); font-weight: 700; }
        .tlb-title { font-size: 30px; font-weight: 800; color: var(--tlb-ink); margin: 6px 0 0; letter-spacing: -.02em; }
        .tlb-sub { color: var(--tlb-ink-3); margin-top: 8px; font-size: 14px; max-width: 560px; line-height: 1.5; }
        .tlb-hero-side { display: flex; align-items: center; gap: 18px; }
        .tlb-hero-trophy {
            width: 64px; height: 64px;
            border-radius: 20px;
            background: linear-gradient(135deg, #fef3c7 0%, #fbbf24 100%);
            display: flex; align-items: center; justify-content: center;
            color: #92400e;
            font-size: 30px;
            box-shadow: 0 12px 24px rgba(245,158,11,0.25);
        }

        /* WEIGHTS */
        .tlb-weights { display: flex; }
        .tlb-weight-row { display: flex; gap: 8px; flex-wrap: wrap; }
        .tlb-weight-chip {
            background: #0f172a; color: #f8fafc;
            padding: 8px 14px; border-radius: 999px;
            font-size: 12px; font-weight: 500;
            display: inline-flex; align-items: center; gap: 8px;
        }
        .tlb-weight-chip strong { color: #fff; font-weight: 700; }
        .tlb-weight-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
        .tlb-weight-mod { background: #a78bfa; }
        .tlb-weight-quiz { background: #34d399; }
        .tlb-weight-rec { background: #fbbf24; }

        /* FILTERS */
        .tlb-filters {
            background: #fff; border: 1px solid var(--tlb-border);
            border-radius: 14px; padding: 10px 14px;
            display: flex; align-items: center; gap: 10px;
            margin-bottom: 22px;
            box-shadow: 0 4px 12px rgba(15,23,42,0.04);
            flex-wrap: wrap;
        }
        .tlb-filter-icon { color: var(--tlb-ink-3); font-size: 18px; display: inline-flex; }
        .tlb-filter {
            flex: 1 1 160px; min-width: 140px; max-width: 220px;
            border: 1px solid var(--tlb-border); border-radius: 10px;
            padding: 8px 12px; font-size: 13px; color: var(--tlb-ink);
            background: #fff;
            transition: border-color .15s, box-shadow .15s;
        }
        .tlb-filter:focus { outline: none; border-color: var(--tlb-primary); box-shadow: 0 0 0 3px var(--tlb-primary-50); }
        .tlb-btn-ghost, .tlb-btn-primary {
            border: none; border-radius: 10px; padding: 8px 14px;
            font-size: 13px; font-weight: 600; cursor: pointer;
            display: inline-flex; align-items: center; gap: 8px;
            transition: transform .1s, background .15s;
        }
        .tlb-btn-ghost { background: #f1f5f9; color: var(--tlb-ink-2); }
        .tlb-btn-ghost:hover { background: #e2e8f0; }
        .tlb-btn-primary { background: var(--tlb-primary); color: #fff; }
        .tlb-btn-primary:hover { background: var(--tlb-primary-700); }
        .tlb-btn-primary:active { transform: translateY(1px); }

        /* PODIUM */
        .tlb-podium { margin-bottom: 24px; }
        .tlb-podium-grid {
            display: grid;
            grid-template-columns: 1fr 1.1fr 1fr;
            gap: 16px;
            align-items: end;
        }
        .tlb-podium-card {
            position: relative;
            background: #fff;
            border: 1px solid var(--tlb-border);
            border-radius: 20px;
            padding: 22px 18px 20px;
            text-align: center;
            box-shadow: 0 12px 28px rgba(15,23,42,0.06);
            transition: transform .15s, box-shadow .15s;
        }
        .tlb-podium-card.tlb-clickable { cursor: pointer; }
        .tlb-podium-card.tlb-clickable:hover { transform: translateY(-3px); box-shadow: 0 18px 36px rgba(15,23,42,0.10); }
        .tlb-podium-empty { opacity: .55; }
        .tlb-podium-first {
            background: linear-gradient(180deg, var(--tlb-primary) 0%, var(--tlb-primary-700) 100%);
            color: #fff;
            border: none;
            box-shadow: 0 20px 40px rgba(109,40,217,0.35);
            padding: 28px 18px 24px;
            transform: translateY(-8px);
        }
        .tlb-podium-first .tlb-podium-name,
        .tlb-podium-first .tlb-podium-score,
        .tlb-podium-first .tlb-podium-rank { color: #fff; }
        .tlb-podium-first .tlb-podium-meta { color: rgba(255,255,255,0.85); }
        .tlb-podium-first .tlb-podium-stats { color: rgba(255,255,255,0.95); }
        .tlb-podium-first .tlb-podium-stats strong { color: #fff; }
        .tlb-podium-self { outline: 3px solid #fbbf24; outline-offset: -3px; }
        .tlb-podium-badge {
            position: absolute; top: -14px; left: 50%; transform: translateX(-50%);
            width: 40px; height: 40px;
            background: #fff; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            font-size: 18px;
            box-shadow: 0 6px 14px rgba(15,23,42,0.12);
        }
        .tlb-podium-gold .tlb-podium-badge { color: #d97706; }
        .tlb-podium-silver .tlb-podium-badge { color: #64748b; }
        .tlb-podium-bronze .tlb-podium-badge { color: #b45309; }
        .tlb-podium-first .tlb-podium-badge { background: #fef3c7; color: #92400e; width: 48px; height: 48px; font-size: 22px; top: -18px; }
        .tlb-podium-rank { font-size: 12px; font-weight: 700; color: var(--tlb-ink-3); letter-spacing: .08em; text-transform: uppercase; margin-top: 14px; }
        .tlb-podium-avatar {
            width: 64px; height: 64px;
            margin: 10px auto 12px;
            border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            font-size: 22px; font-weight: 700;
            background: #f1f5f9; color: var(--tlb-ink);
            border: 3px solid #fff;
            box-shadow: 0 6px 14px rgba(15,23,42,0.10);
        }
        .tlb-podium-first .tlb-podium-avatar {
            background: rgba(255,255,255,0.18);
            color: #fff;
            border-color: rgba(255,255,255,0.25);
            width: 76px; height: 76px;
            font-size: 26px;
        }
        .tlb-avatar-gold { background: linear-gradient(135deg, #fde68a 0%, #f59e0b 100%); color: #78350f; }
        .tlb-avatar-silver { background: linear-gradient(135deg, #e2e8f0 0%, #94a3b8 100%); color: #0f172a; }
        .tlb-avatar-bronze { background: linear-gradient(135deg, #fed7aa 0%, #c2410c 100%); color: #7c2d12; }
        .tlb-podium-name {
            font-size: 15px; font-weight: 700; color: var(--tlb-ink);
            margin-bottom: 4px;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .tlb-podium-meta { font-size: 12px; color: var(--tlb-ink-3); margin-bottom: 12px; }
        .tlb-podium-score {
            font-size: 32px; font-weight: 800; color: var(--tlb-ink);
            line-height: 1; letter-spacing: -.02em;
        }
        .tlb-podium-first .tlb-podium-score { font-size: 40px; }
        .tlb-podium-stats {
            margin-top: 14px;
            display: flex; justify-content: space-around;
            font-size: 11px; color: var(--tlb-ink-3); letter-spacing: .04em; text-transform: uppercase;
        }
        .tlb-podium-stats strong { display: block; font-size: 14px; font-weight: 700; color: var(--tlb-ink); margin-top: 2px; text-transform: none; letter-spacing: 0; }

        /* CARD WRAPPING TABLE */
        .tlb-card {
            background: #fff;
            border: 1px solid var(--tlb-border);
            border-radius: 20px;
            box-shadow: 0 14px 32px rgba(15,23,42,0.06);
            overflow: hidden;
        }
        .tlb-card-head {
            padding: 18px 24px;
            border-bottom: 1px solid var(--tlb-border);
            display: flex; justify-content: space-between; align-items: center;
            background: linear-gradient(180deg, #fff 0%, #faf5ff 100%);
        }
        .tlb-card-title { font-size: 16px; font-weight: 700; color: var(--tlb-ink); }
        .tlb-card-sub { font-size: 12px; color: var(--tlb-ink-3); margin-top: 2px; }

        /* TABLE */
        .tlb-table-wrap { overflow-x: auto; }
        .tlb-table { width: 100%; border-collapse: collapse; }
        .tlb-table th {
            text-align: left; padding: 14px 20px;
            background: #faf5ff;
            border-bottom: 1px solid var(--tlb-border);
            color: var(--tlb-ink-3); font-size: 11px;
            text-transform: uppercase; letter-spacing: .08em; font-weight: 700;
        }
        .tlb-table td {
            padding: 14px 20px;
            border-bottom: 1px solid #f1f5f9;
            color: var(--tlb-ink-2);
            vertical-align: middle;
        }
        .tlb-table tr:last-child td { border-bottom: none; }
        .tlb-row { cursor: pointer; transition: background .12s; }
        .tlb-row:hover { background: var(--tlb-primary-50); }
        .tlb-row-self { background: #fffbeb; }
        .tlb-row-self:hover { background: #fef3c7; }

        .tlb-rank {
            display: inline-flex; min-width: 32px; height: 32px;
            align-items: center; justify-content: center;
            border-radius: 10px;
            font-weight: 700; font-size: 13px;
            background: #f1f5f9; color: var(--tlb-ink);
        }
        .tlb-rank-gold { background: linear-gradient(135deg, #fde68a 0%, #f59e0b 100%); color: #78350f; }
        .tlb-rank-silver { background: linear-gradient(135deg, #e2e8f0 0%, #94a3b8 100%); color: #0f172a; }
        .tlb-rank-bronze { background: linear-gradient(135deg, #fed7aa 0%, #c2410c 100%); color: #fff; }

        .tlb-emp { display: flex; align-items: center; gap: 12px; }
        .tlb-emp-avatar {
            width: 38px; height: 38px; border-radius: 50%;
            background: linear-gradient(135deg, #ede9fe 0%, #c4b5fd 100%);
            color: var(--tlb-primary-700);
            font-weight: 700; font-size: 13px;
            display: flex; align-items: center; justify-content: center;
            flex-shrink: 0;
        }
        .tlb-emp-text { min-width: 0; }
        .tlb-emp-name { font-weight: 600; color: var(--tlb-ink); font-size: 14px; display: flex; align-items: center; gap: 8px; }
        .tlb-emp-meta { font-size: 12px; color: var(--tlb-ink-3); margin-top: 2px; }
        .tlb-self-pill {
            font-size: 10px; font-weight: 700; letter-spacing: .04em;
            text-transform: uppercase;
            background: #fbbf24; color: #78350f;
            padding: 2px 8px; border-radius: 999px;
        }

        .tlb-score { font-size: 18px; font-weight: 800; color: var(--tlb-ink); letter-spacing: -.02em; }

        .tlb-progress-cell { min-width: 140px; }
        .tlb-progress-bar { height: 6px; background: #f1f5f9; border-radius: 999px; overflow: hidden; }
        .tlb-progress-fill { height: 100%; background: linear-gradient(90deg, var(--tlb-primary) 0%, #a78bfa 100%); border-radius: 999px; }
        .tlb-progress-text { font-size: 11px; color: var(--tlb-ink-3); margin-top: 6px; }

        .tlb-pill {
            display: inline-block; padding: 4px 10px; border-radius: 999px;
            font-size: 12px; font-weight: 600;
        }
        .tlb-pill-quiz { background: #ecfdf5; color: #047857; }
        .tlb-pill-rec { background: #fffbeb; color: #b45309; }

        .tlb-muted { color: var(--tlb-ink-3); font-size: 12px; }

        .tlb-empty {
            padding: 56px 24px; text-align: center; color: var(--tlb-ink-3);
            display: flex; flex-direction: column; align-items: center; gap: 12px;
        }
        .tlb-empty svg { font-size: 36px; color: #cbd5e1; }
        .tlb-shimmer { padding: 56px 24px; text-align: center; color: var(--tlb-ink-3); }

        /* DRAWER */
        .tlb-drawer-backdrop {
            position: fixed; inset: 0;
            background: rgba(15,23,42,0.45);
            backdrop-filter: blur(4px);
            z-index: 1009;
            display: none;
        }
        .tlb-drawer {
            position: fixed; top: 0; right: 0; bottom: 0;
            width: min(560px, 100%);
            background: var(--tlb-bg);
            box-shadow: -20px 0 60px rgba(15,23,42,0.20);
            z-index: 1010;
            overflow-y: auto;
            display: none;
        }
        .tlb-drawer-card { padding: 22px; }
        .tlb-drawer-head {
            display: flex; justify-content: space-between; align-items: center;
            background: #fff; border: 1px solid var(--tlb-border);
            border-radius: 16px;
            padding: 16px 18px;
            margin-bottom: 16px;
        }
        .tlb-drawer-head-left { display: flex; align-items: center; gap: 12px; }
        .tlb-drawer-avatar {
            width: 48px; height: 48px; border-radius: 50%;
            background: linear-gradient(135deg, #ede9fe 0%, #c4b5fd 100%);
            color: var(--tlb-primary-700);
            font-weight: 700; font-size: 16px;
            display: flex; align-items: center; justify-content: center;
        }
        .tlb-drawer-title { font-weight: 700; font-size: 17px; color: var(--tlb-ink); }
        .tlb-drawer-sub { font-size: 12px; color: var(--tlb-ink-3); margin-top: 4px; }
        .tlb-drawer-close {
            background: #f1f5f9; border: none; border-radius: 10px;
            width: 36px; height: 36px;
            display: flex; align-items: center; justify-content: center;
            color: var(--tlb-ink-2); cursor: pointer;
            transition: background .15s;
        }
        .tlb-drawer-close:hover { background: #e2e8f0; }
        .tlb-drawer-body { display: flex; flex-direction: column; gap: 14px; }

        .tlb-drill-program {
            background: #fff; border: 1px solid var(--tlb-border);
            border-radius: 16px; padding: 16px 18px;
        }
        .tlb-drill-program-head {
            display: flex; justify-content: space-between; align-items: baseline;
            margin-bottom: 10px;
        }
        .tlb-drill-program-title { font-weight: 700; font-size: 15px; color: var(--tlb-ink); }
        .tlb-drill-program-pct { font-weight: 700; color: var(--tlb-primary); font-size: 13px; }
        .tlb-drill-bar { height: 6px; background: #f1f5f9; border-radius: 999px; overflow: hidden; margin-bottom: 14px; }
        .tlb-drill-bar-lg { height: 8px; }
        .tlb-drill-bar-fill { height: 100%; background: linear-gradient(90deg, var(--tlb-primary) 0%, #a78bfa 100%); }

        .tlb-drill-level { margin-top: 10px; padding: 10px 12px; background: var(--tlb-bg); border-radius: 12px; }
        .tlb-drill-level-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; }
        .tlb-drill-level-title { font-weight: 600; color: var(--tlb-ink-2); font-size: 13px; }
        .tlb-drill-pct { font-weight: 600; color: var(--tlb-ink-3); font-size: 12px; }
        .tlb-drill-mods { margin-top: 8px; display: flex; flex-direction: column; gap: 4px; }
        .tlb-drill-flat { display: flex; flex-direction: column; gap: 4px; margin-top: 8px; }
        .tlb-drill-mod {
            padding: 6px 4px;
            color: var(--tlb-ink-2);
            display: flex; align-items: center; gap: 10px;
            font-size: 13px;
        }
        .tlb-drill-mod-done { color: var(--tlb-ink-3); text-decoration: line-through; }
        .tlb-dot {
            width: 18px; height: 18px;
            border-radius: 50%;
            display: inline-flex; align-items: center; justify-content: center;
            flex-shrink: 0;
        }
        .tlb-dot-done { background: #d1fae5; color: #047857; }
        .tlb-dot-done svg { width: 12px; height: 12px; }
        .tlb-dot-todo { background: transparent; border: 2px solid #cbd5e1; }

        /* RESPONSIVE */
        @media (max-width: 960px) {
            .tlb-podium-grid { grid-template-columns: 1fr; }
            .tlb-podium-first { transform: none; order: -1; }
        }
        @media (max-width: 768px) {
            .tlb-wrapper { padding: 18px 14px; }
            .tlb-hero { flex-direction: column; align-items: flex-start; gap: 18px; padding: 22px; }
            .tlb-hero-side { width: 100%; justify-content: space-between; }
            .tlb-title { font-size: 24px; }
            .tlb-drawer { width: 100%; }
            .tlb-table th:nth-child(6), .tlb-table td:nth-child(6),
            .tlb-table th:nth-child(7), .tlb-table td:nth-child(7) { display: none; }
        }
    `;
    document.head.appendChild(style);
}
