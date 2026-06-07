frappe.pages["training-center"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Training Center"),
        single_column: true,
    });

    page.main.addClass("tc-root");
    injectStyles();
    renderSkeleton(page);
    loadData(page);
};

// ── Icons (inline SVG, currentColor) ─────────────────────────────────────────
const ICONS = {
    book:     `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h7a3 3 0 0 1 3 3v14"/><path d="M20 4h-7a3 3 0 0 0-3 3v14"/></svg>`,
    play:     `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polygon points="6,4 20,12 6,20" fill="currentColor"/></svg>`,
    check:    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="4,12 10,18 20,6"/></svg>`,
    chevron:  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9,6 15,12 9,18"/></svg>`,
    award:    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="9" r="6"/><path d="M9 15l-1.5 6L12 18l4.5 3L15 15"/></svg>`,
    clock:    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><polyline points="12,7 12,12 16,14"/></svg>`,
    trophy:   `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 4h10v5a5 5 0 0 1-10 0V4z"/><path d="M5 6H2v2a3 3 0 0 0 3 3"/><path d="M19 6h3v2a3 3 0 0 1-3 3"/><path d="M9 20h6"/><path d="M12 15v5"/></svg>`,
    target:   `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/></svg>`,
    pdf:      `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M7 3h7l5 5v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M14 3v5h5"/><text x="8.5" y="18" font-size="6" font-family="ui-sans-serif" font-weight="700" fill="currentColor" stroke="none">PDF</text></svg>`,
    video:    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="6" width="14" height="12" rx="2"/><polygon points="17,9 22,6 22,18 17,15" fill="currentColor"/></svg>`,
    excel:    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M7 3h7l5 5v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M14 3v5h5"/><path d="M9 12l5 6M14 12l-5 6"/></svg>`,
    image:    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><polyline points="3,18 9,12 14,17 21,10"/></svg>`,
    link:     `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10 14a4 4 0 0 1 0-6l2-2a4 4 0 0 1 6 6l-1 1"/><path d="M14 10a4 4 0 0 1 0 6l-2 2a4 4 0 0 1-6-6l1-1"/></svg>`,
    note:     `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4h11l3 3v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z"/><path d="M8 10h8M8 14h8M8 18h5"/></svg>`,
    close:    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/></svg>`,
};

function fileIcon(type) {
    if (type === "PDF") return ICONS.pdf;
    if (type === "Excel") return ICONS.excel;
    if (type === "Image") return ICONS.image;
    if (type === "Video URL") return ICONS.video;
    if (type === "External Link") return ICONS.link;
    if (type === "Note") return ICONS.note;
    return ICONS.note;
}

function fileAccent(type) {
    if (type === "PDF") return "tc-file--pdf";
    if (type === "Excel") return "tc-file--excel";
    if (type === "Image") return "tc-file--image";
    if (type === "Video URL") return "tc-file--video";
    if (type === "External Link") return "tc-file--link";
    return "tc-file--note";
}

function initials(text) {
    if (!text) return "?";
    return text.trim().split(/\s+/).slice(0, 2).map((w) => w[0] || "").join("").toUpperCase() || text[0].toUpperCase();
}

function programCover(name) {
    // Deterministic pastel gradient from the program name's char codes.
    const seed = (name || "").split("").reduce((acc, c) => acc + c.charCodeAt(0), 0) || 7;
    const hue1 = seed % 360;
    const hue2 = (hue1 + 40) % 360;
    return `linear-gradient(135deg, hsl(${hue1} 76% 62%) 0%, hsl(${hue2} 70% 48%) 100%)`;
}

// ── Skeleton ─────────────────────────────────────────────────────────────────
function renderSkeleton(page) {
    const hour = new Date().getHours();
    const greeting = hour < 12 ? __("Good morning") : hour < 18 ? __("Good afternoon") : __("Good evening");
    const userName = (frappe.session && frappe.boot && frappe.boot.user && frappe.boot.user.first_name) || frappe.session.user.split("@")[0];

    page.main.html(`
        <div class="tc-wrap">
            <header class="tc-header">
                <div>
                    <div class="tc-eyebrow">${__("Learning Center")}</div>
                    <h1 class="tc-title">${greeting}, ${frappe.utils.escape_html(userName)}</h1>
                    <p class="tc-sub">${__("Pick up where you left off and keep your streak alive.")}</p>
                </div>
                <div class="tc-header-meta" id="tc-header-meta"></div>
            </header>

            <section class="tc-kpis" id="tc-kpis"></section>

            <section id="tc-next-section" class="tc-section">
                <div class="tc-section-head">
                    <h2 class="tc-section-title">${__("Continue where you left off")}</h2>
                </div>
                <div id="tc-next"></div>
            </section>

            <div id="tc-empty" class="tc-empty" style="display:none;"></div>

            <section class="tc-section">
                <div class="tc-section-head">
                    <h2 class="tc-section-title">${__("My Programs")}</h2>
                </div>
                <div id="tc-programs" class="tc-program-grid"></div>
            </section>
        </div>

        <div id="tc-modal" class="tc-modal" style="display:none;">
            <div class="tc-modal-backdrop"></div>
            <div class="tc-modal-card" role="dialog"></div>
        </div>
    `);
}

// ── Data ─────────────────────────────────────────────────────────────────────
async function loadData(page) {
    try {
        const res = await frappe.call({ method: "orderlift.orderlift_hr.api.training.get_training_center_data" });
        const data = res.message || {};
        renderHeaderMeta(page, data.stats || {});
        renderKpis(page, data.stats || {});
        renderNext(page, data.next_module);
        renderPrograms(page, data.programs || []);
        if (!(data.programs || []).length) renderEmpty(page);
        else page.main.find("#tc-empty").hide();
    } catch (e) {
        console.warn("Training Center: load failed", e);
        renderEmpty(page);
    }
}

function renderHeaderMeta(page, stats) {
    page.main.find("#tc-header-meta").html(`
        <div class="tc-streak">
            <span class="tc-streak-label">${__("Last activity")}</span>
            <span class="tc-streak-value">${stats.last_activity ? frappe.datetime.prettyDate(stats.last_activity) : "—"}</span>
        </div>
    `);
}

function renderKpis(page, stats) {
    const items = [
        { label: __("Modules completed"), value: `${stats.module_completion_pct ?? 0}%`, icon: ICONS.check,  variant: "green",  hint: `${stats.modules_completed ?? 0}/${stats.modules_total ?? 0} ${__("required")}` },
        { label: __("Quiz average"),      value: `${stats.quiz_average_pct ?? 0}%`,      icon: ICONS.award,  variant: "indigo", hint: __("Across taken quizzes") },
        { label: __("Modules done"),      value: `${stats.modules_completed ?? 0}`,      icon: ICONS.target, variant: "orange", hint: __("All-time") },
        { label: __("Active streak"),     value: stats.last_activity ? frappe.datetime.prettyDate(stats.last_activity) : "—", icon: ICONS.clock, variant: "purple", hint: __("Keep going!") },
    ];
    page.main.find("#tc-kpis").html(items.map((kpi) => `
        <div class="tc-kpi">
            <div class="tc-kpi-icon tc-kpi-icon--${kpi.variant}">${kpi.icon}</div>
            <div class="tc-kpi-label">${kpi.label}</div>
            <div class="tc-kpi-value">${kpi.value}</div>
            <div class="tc-kpi-hint">${kpi.hint}</div>
        </div>
    `).join(""));
}

function renderNext(page, next) {
    if (!next) {
        page.main.find("#tc-next-section").hide();
        return;
    }
    page.main.find("#tc-next-section").show();
    page.main.find("#tc-next").html(`
        <a class="tc-next" data-module="${frappe.utils.escape_html(next.module)}">
            <div class="tc-next-thumb" style="background:${programCover(next.program)}">
                <span class="tc-next-thumb-initials">${initials(next.program)}</span>
                <span class="tc-next-play">${ICONS.play}</span>
            </div>
            <div class="tc-next-body">
                <div class="tc-next-eyebrow">${__("Up next")} · ${frappe.utils.escape_html(next.program)}</div>
                <div class="tc-next-title">${frappe.utils.escape_html(next.title)}</div>
                <div class="tc-next-meta">${__("Click to open the module and continue")}</div>
            </div>
            <div class="tc-next-arrow">${ICONS.chevron}</div>
        </a>
    `);
    page.main.find(".tc-next").on("click", function () {
        openProgramByNext(page, $(this).data("module"), next.program);
    });
}

function renderPrograms(page, programs) {
    if (!programs.length) {
        page.main.find("#tc-programs").html("");
        return;
    }
    state.programs = programs;
    page.main.find("#tc-programs").html(programs.map(programCard).join(""));
    page.main.find(".tc-card").on("click", function () {
        openProgram(page, $(this).data("program"));
    });
}

function programCard(program) {
    const total = (program.required_total || 0);
    const done = (program.required_done || 0);
    const levels = (program.levels || []).length;
    const modules = (program.levels || []).reduce((a, lvl) => a + (lvl.modules || []).length, 0)
                  + (program.flat_modules || []).length;
    const descPlain = stripTags(program.description || "");
    return `
        <div class="tc-card" data-program="${frappe.utils.escape_html(program.program_name)}">
            <div class="tc-card-thumb" style="background:${programCover(program.program_name)}">
                <span class="tc-card-thumb-initials">${initials(program.program_name)}</span>
                <span class="tc-card-thumb-badge">${__("Training")}</span>
            </div>
            <div class="tc-card-body">
                <div class="tc-card-meta">
                    <span class="tc-card-tag">${__("Program")}</span>
                    <span class="tc-card-meta-dot">·</span>
                    <span>${levels} ${__("Levels")} · ${modules} ${__("Modules")}</span>
                </div>
                <h3 class="tc-card-title">${frappe.utils.escape_html(program.program_name)}</h3>
                ${descPlain ? `<p class="tc-card-desc">${frappe.utils.escape_html(descPlain).slice(0, 140)}${descPlain.length > 140 ? "…" : ""}</p>` : ""}
                <div class="tc-card-progress">
                    <div class="tc-card-progress-meta">
                        <span>${__("Progress")}</span>
                        <strong>${program.completion_pct ?? 0}%</strong>
                    </div>
                    <div class="tc-bar"><div class="tc-bar-fill" style="width:${program.completion_pct ?? 0}%"></div></div>
                </div>
                <div class="tc-card-footer">
                    <span class="tc-card-footer-meta">${done}/${total} ${__("required")}</span>
                    <span class="tc-card-cta">${__("Continue")} ${ICONS.chevron}</span>
                </div>
            </div>
        </div>
    `;
}

function renderEmpty(page) {
    page.main.find("#tc-empty").show().html(`
        <div class="tc-empty-card">
            <div class="tc-empty-icon">${ICONS.book}</div>
            <div class="tc-empty-title">${__("No training programs are assigned to you yet.")}</div>
            <div class="tc-empty-sub">${__("Once HR assigns programs to your department or directly to you, they will appear here.")}</div>
        </div>
    `);
    page.main.find("#tc-programs").html("");
    page.main.find("#tc-next-section").hide();
}

// ── Program modal ────────────────────────────────────────────────────────────
const state = { page: null, programs: [], activeProgram: null, activeModule: null };

function openProgram(page, programName) {
    const program = (state.programs || []).find((p) => p.program_name === programName);
    if (!program) return;
    state.activeProgram = program;
    state.activeModule = null;
    renderProgramModal(page, program);
    showModal(page);
}

function openProgramByNext(page, moduleName, programName) {
    const program = (state.programs || []).find((p) => p.program_name === programName);
    if (program) {
        state.activeProgram = program;
        state.activeModule = null;
        renderProgramModal(page, program);
        showModal(page);
        openModuleDetail(page, moduleName);
    } else {
        openModuleDetail(page, moduleName);
    }
}

function showModal(page) {
    page.main.find("#tc-modal").show();
    document.body.style.overflow = "hidden";
}

function hideModal(page) {
    page.main.find("#tc-modal").hide();
    document.body.style.overflow = "";
    state.activeProgram = null;
    state.activeModule = null;
}

function renderProgramModal(page, program) {
    const levels = (program.levels || []).map(levelBlock).join("");
    const flat = (program.flat_modules || []).length
        ? `<div class="tc-lvl">
              <div class="tc-lvl-head"><span class="tc-lvl-name">${__("Modules")}</span></div>
              <div class="tc-mod-grid">${(program.flat_modules || []).map(moduleCard).join("")}</div>
           </div>`
        : "";
    const card = page.main.find("#tc-modal .tc-modal-card");
    card.html(`
        <div class="tc-modal-main">
            <div class="tc-modal-hero" style="background:${programCover(program.program_name)}">
                <button class="tc-modal-close" id="tc-modal-close">${ICONS.close}</button>
                <div class="tc-modal-hero-inner">
                    <div class="tc-modal-hero-eyebrow">${__("Program")}</div>
                    <h2 class="tc-modal-hero-title">${frappe.utils.escape_html(program.program_name)}</h2>
                    <p class="tc-modal-hero-sub">${frappe.utils.escape_html(stripTags(program.description || "")) || __("Structured learning path with levels, modules and quizzes.")}</p>
                </div>
            </div>
            <div class="tc-modal-body">
                ${levels}
                ${flat}
            </div>
        </div>
        <aside class="tc-modal-side" id="tc-modal-side">
            ${sideRail(program, null)}
        </aside>
        <div class="tc-modal-backdrop-click"></div>
    `);
    wireModal(page, card);
}

function levelBlock(level) {
    return `
        <div class="tc-lvl">
            <div class="tc-lvl-head">
                <span class="tc-lvl-name">${frappe.utils.escape_html(level.level_name)}</span>
                <span class="tc-lvl-pct">${level.completion_pct ?? 0}%</span>
            </div>
            <div class="tc-mod-grid">${(level.modules || []).map(moduleCard).join("")}</div>
        </div>
    `;
}

function moduleCard(mod) {
    const done = !!mod.studied;
    return `
        <div class="tc-mod ${done ? "tc-mod--done" : ""}" data-module="${frappe.utils.escape_html(mod.name)}">
            <div class="tc-mod-icon">${done ? ICONS.check : ICONS.book}</div>
            <div class="tc-mod-title">${frappe.utils.escape_html(mod.title)}</div>
            <div class="tc-mod-meta">
                ${mod.has_quiz ? `<span class="tc-chip tc-chip--quiz">${__("Quiz")}</span>` : ""}
                ${done ? `<span class="tc-chip tc-chip--done">${__("Studied")}</span>` : `<span class="tc-chip tc-chip--todo">${__("To do")}</span>`}
            </div>
        </div>
    `;
}

function sideRail(program, mod) {
    const pct = program.completion_pct ?? 0;
    return `
        <div class="tc-side-title">${__("Status & action")}</div>
        <div class="tc-side-card">
            <div class="tc-side-eyebrow">${__("Overall progress")}</div>
            <div class="tc-side-progress-row">
                <span class="tc-side-progress-label">${__("Completion")}</span>
                <span class="tc-side-progress-value">${pct}%</span>
            </div>
            <div class="tc-bar"><div class="tc-bar-fill" style="width:${pct}%"></div></div>
        </div>
        ${mod ? `
            <div class="tc-side-card tc-side-card--active">
                <div class="tc-side-eyebrow tc-side-eyebrow--accent">${__("Active module")}</div>
                <div class="tc-side-mod-title">${frappe.utils.escape_html(mod.title || "")}</div>
                <div class="tc-side-mod-meta">${ICONS.clock} ${mod.estimated_minutes ? `${mod.estimated_minutes} ${__("min")}` : __("Self-paced")}</div>
            </div>` : `
            <div class="tc-side-card tc-side-card--hint">
                <div class="tc-side-eyebrow">${__("Tip")}</div>
                <div class="tc-side-hint">${__("Pick a module on the left to view files and take its quiz.")}</div>
            </div>`}
        <div class="tc-side-action" id="tc-side-action"></div>
    `;
}

function wireModal(page, card) {
    card.find("#tc-modal-close, .tc-modal-backdrop-click").on("click", () => hideModal(page));
    card.find(".tc-mod").on("click", function () {
        openModuleDetail(page, $(this).data("module"));
    });
    page.main.find("#tc-modal .tc-modal-backdrop").off("click").on("click", () => hideModal(page));
}

// ── Module detail (in-modal) ─────────────────────────────────────────────────
async function openModuleDetail(page, moduleName) {
    if (!moduleName) return;
    const card = page.main.find("#tc-modal .tc-modal-card");
    card.find(".tc-modal-body").html(`<div class="tc-loading">${__("Loading…")}</div>`);
    try {
        const res = await frappe.call({ method: "orderlift.orderlift_hr.api.training.get_module_detail", args: { module: moduleName } });
        const data = res.message || {};
        state.activeModule = data;
        renderModuleDetail(page, data);
    } catch (e) {
        card.find(".tc-modal-body").html(`<div class="tc-empty-card"><div class="tc-empty-title">${__("Failed to load module.")}</div></div>`);
    }
}

function renderModuleDetail(page, data) {
    const card = page.main.find("#tc-modal .tc-modal-card");
    const mod = data.module || {};
    const files = data.files || [];
    const quiz = data.quiz;
    const studied = !!(data.progress && data.progress.studied);

    const filesHtml = files.length
        ? `<div class="tc-files-grid">${files.map(fileCard).join("")}</div>`
        : `<div class="tc-empty-card tc-empty-card--inline"><div class="tc-empty-title">${__("No files attached.")}</div></div>`;

    const quizHtml = quiz ? `
        <div class="tc-quiz-card">
            <div class="tc-quiz-card-icon">${ICONS.award}</div>
            <div class="tc-quiz-card-body">
                <div class="tc-quiz-card-title">${frappe.utils.escape_html(quiz.quiz_name)}</div>
                <div class="tc-quiz-card-meta">
                    ${__("Pass")}: ${quiz.pass_percentage}%
                    · ${quiz.unlimited_attempts ? __("Unlimited attempts") : `${__("Attempts left")}: ${quiz.attempts_remaining}`}
                </div>
            </div>
            <button class="tc-btn tc-btn--ghost tc-launch-quiz" data-quiz="${frappe.utils.escape_html(quiz.name)}" ${quiz.attempts_remaining === 0 ? "disabled" : ""}>${__("Start quiz")}</button>
        </div>` : "";

    card.find(".tc-modal-body").html(`
        <button class="tc-back" id="tc-back-to-program">${ICONS.chevron} ${__("Back to program")}</button>
        <div class="tc-detail">
            <div class="tc-detail-cover" style="background:${programCover(mod.program || "")}">
                <div class="tc-detail-cover-inner">
                    <div class="tc-detail-cover-eyebrow">${__("Module")} · ${frappe.utils.escape_html(mod.program || "")}</div>
                    <h2 class="tc-detail-cover-title">${frappe.utils.escape_html(mod.title || "")}</h2>
                </div>
                ${studied ? `<div class="tc-detail-cover-badge">${ICONS.check}${__("Studied")}</div>` : ""}
            </div>

            <div class="tc-detail-section">
                <div class="tc-detail-section-title">${__("Module resources")}</div>
                ${filesHtml}
            </div>

            ${mod.description ? `<div class="tc-detail-section"><div class="tc-detail-section-title">${__("About")}</div><div class="tc-detail-text">${mod.description}</div></div>` : ""}

            ${quizHtml}
        </div>
    `);

    // Side rail updated
    card.find("#tc-modal-side").html(sideRail(state.activeProgram || {}, mod));

    // Action button (sidebar bottom)
    const actionBtn = `<button class="tc-btn tc-btn--primary tc-mark-studied" data-module="${frappe.utils.escape_html(mod.name)}" ${studied ? "disabled" : ""}>
        ${studied ? `${ICONS.check} ${__("Already studied")}` : (quiz ? __("Mark as Studied") : __("Mark as Studied"))}
    </button>`;
    card.find("#tc-side-action").html(actionBtn);

    card.find("#tc-back-to-program").on("click", () => renderProgramModal(page, state.activeProgram));
    card.find(".tc-mark-studied").on("click", async function () {
        const btn = $(this);
        btn.prop("disabled", true);
        try {
            await frappe.call({ method: "orderlift.orderlift_hr.api.training.mark_module_studied", args: { module: btn.data("module") } });
            frappe.show_alert({ message: __("Module marked as studied"), indicator: "green" });
            hideModal(page);
            loadData(page);
        } catch (e) {
            btn.prop("disabled", false);
            frappe.show_alert({ message: __("Failed to update progress"), indicator: "red" });
        }
    });
    card.find(".tc-launch-quiz").on("click", function () {
        launchQuiz(page, $(this).data("quiz"));
    });
}

function fileCard(file) {
    const t = file.file_type;
    const accent = fileAccent(t);
    const title = frappe.utils.escape_html(file.title || "—");
    const href = (t === "PDF" || t === "Excel" || t === "Image") ? file.attachment :
                  (t === "Video URL" || t === "External Link") ? file.url : null;
    if (t === "Note") {
        return `<div class="tc-file ${accent}">
            <div class="tc-file-icon">${fileIcon(t)}</div>
            <div class="tc-file-body">
                <div class="tc-file-type">${t}</div>
                <div class="tc-file-title">${title}</div>
                ${file.note_body ? `<div class="tc-file-note">${file.note_body}</div>` : ""}
            </div>
        </div>`;
    }
    return `<a class="tc-file ${accent}" href="${frappe.utils.escape_html(href || "#")}" target="_blank" rel="noopener">
        <div class="tc-file-icon">${fileIcon(t)}</div>
        <div class="tc-file-body">
            <div class="tc-file-type">${t}</div>
            <div class="tc-file-title">${title}</div>
        </div>
        <div class="tc-file-go">${ICONS.chevron}</div>
    </a>`;
}

// ── Quiz runner (in-modal) ───────────────────────────────────────────────────
async function launchQuiz(page, quizName) {
    if (!quizName) return;
    const card = page.main.find("#tc-modal .tc-modal-card");
    card.find(".tc-modal-body").html(`<div class="tc-loading">${__("Preparing quiz…")}</div>`);
    try {
        const res = await frappe.call({ method: "orderlift.orderlift_hr.api.training.start_quiz", args: { quiz: quizName } });
        renderQuizRunner(page, res.message || {});
    } catch (e) {
        frappe.show_alert({ message: e.message || __("Failed to start quiz"), indicator: "red" });
        hideModal(page);
    }
}

function renderQuizRunner(page, data) {
    const card = page.main.find("#tc-modal .tc-modal-card");
    const quiz = data.quiz || {};
    const questions = data.questions || [];
    card.find(".tc-modal-body").html(`
        <button class="tc-back" id="tc-back-to-module">${ICONS.chevron} ${__("Back")}</button>
        <div class="tc-quiz-run" data-attempt="${frappe.utils.escape_html(data.attempt || "")}">
            <div class="tc-quiz-run-head">
                <div class="tc-quiz-run-eyebrow">${__("Quiz")}</div>
                <h2 class="tc-quiz-run-title">${frappe.utils.escape_html(quiz.quiz_name || "Quiz")}</h2>
                <div class="tc-quiz-run-meta">${__("Pass")}: ${quiz.pass_percentage}% · ${__("Attempt")} ${quiz.attempts_used}${quiz.attempts_limit ? "/" + quiz.attempts_limit : ""}</div>
            </div>
            ${questions.map(questionBlock).join("")}
        </div>
    `);
    card.find("#tc-side-action").html(`<button class="tc-btn tc-btn--primary" id="tc-submit-quiz">${__("Submit quiz")}</button>`);
    card.find("#tc-back-to-module").on("click", () => {
        if (state.activeModule) renderModuleDetail(page, state.activeModule);
        else renderProgramModal(page, state.activeProgram);
    });
    card.find("#tc-submit-quiz").on("click", () => submitQuiz(page, data));
}

function questionBlock(q) {
    const isMulti = q.question_type === "Multiple Choice";
    const inputName = `q_${frappe.utils.escape_html(q.name)}`;
    const inputType = isMulti ? "checkbox" : "radio";
    return `
        <div class="tc-q" data-question="${frappe.utils.escape_html(q.name)}" data-type="${frappe.utils.escape_html(q.question_type)}">
            <div class="tc-q-text">${frappe.utils.escape_html(q.question_text)}</div>
            <div class="tc-q-opts">
                ${(q.options || []).map((opt) => `
                    <label class="tc-q-opt">
                        <input type="${inputType}" name="${inputName}" value="${frappe.utils.escape_html(opt.name)}" />
                        <span class="tc-q-opt-mark"></span>
                        <span class="tc-q-opt-text">${frappe.utils.escape_html(opt.option_text)}</span>
                    </label>`).join("")}
            </div>
        </div>
    `;
}

async function submitQuiz(page, data) {
    const card = page.main.find("#tc-modal .tc-modal-card");
    const attempt = card.find(".tc-quiz-run").data("attempt");
    const answers = [];
    card.find(".tc-q").each(function () {
        const question = $(this).data("question");
        const selected = $(this).find("input:checked").map(function () { return $(this).val(); }).get();
        answers.push({ question, selected_options: selected });
    });
    try {
        const res = await frappe.call({
            method: "orderlift.orderlift_hr.api.training.submit_quiz_attempt",
            args: { attempt, answers_json: JSON.stringify(answers) },
        });
        const result = res.message || {};
        const passed = !!result.passed;
        card.find(".tc-modal-body").html(`
            <div class="tc-result tc-result--${passed ? "pass" : "fail"}">
                <div class="tc-result-emoji">${passed ? ICONS.trophy : ICONS.book}</div>
                <h2 class="tc-result-title">${passed ? __("Quiz passed!") : __("Not quite there yet")}</h2>
                <p class="tc-result-sub">${__("You scored")} <strong>${(result.score_percentage || 0).toFixed(1)}%</strong></p>
                <span class="tc-result-pill">${passed ? __("Passed") : __("Failed — try again")}</span>
                <div class="tc-result-actions">
                    <button class="tc-btn tc-btn--primary" id="tc-close-after">${__("Close")}</button>
                </div>
            </div>
        `);
        card.find("#tc-side-action").html("");
        card.find("#tc-close-after").on("click", () => { hideModal(page); loadData(page); });
    } catch (e) {
        frappe.show_alert({ message: e.message || __("Failed to submit"), indicator: "red" });
    }
}

function stripTags(html) {
    if (!html) return "";
    const d = document.createElement("div");
    d.innerHTML = html;
    return (d.textContent || d.innerText || "").trim();
}

// ── Styles ───────────────────────────────────────────────────────────────────
function injectStyles() {
    if (document.getElementById("tc-styles")) return;
    const style = document.createElement("style");
    style.id = "tc-styles";
    style.textContent = `
:root {
    --tc-primary: #7F56D9;
    --tc-primary-50: #F4EBFF;
    --tc-primary-100: #E9D7FE;
    --tc-primary-600: #7F56D9;
    --tc-primary-700: #6941C6;
    --tc-dark: #101828;
    --tc-text: #344054;
    --tc-muted: #667085;
    --tc-line: #EAECF0;
    --tc-bg: #F9FAFB;
    --tc-card: #FFFFFF;
    --tc-green-50: #ECFDF3;
    --tc-green-100: #D1FADF;
    --tc-green-600: #039855;
    --tc-green-700: #027A48;
    --tc-orange-50: #FFF6ED;
    --tc-orange-600: #DC6803;
    --tc-purple-50: #F9F5FF;
    --tc-purple-600: #6941C6;
    --tc-red-50: #FEF3F2;
    --tc-red-600: #D92D20;
    --tc-shadow-sm: 0 1px 2px rgba(16, 24, 40, 0.04);
    --tc-shadow-md: 0 4px 8px -2px rgba(16, 24, 40, 0.08), 0 2px 4px -2px rgba(16, 24, 40, 0.06);
    --tc-shadow-lg: 0 12px 24px -8px rgba(16, 24, 40, 0.10), 0 8px 16px -8px rgba(16, 24, 40, 0.08);
    --tc-shadow-xl: 0 20px 40px -10px rgba(16, 24, 40, 0.15);
}
.tc-root { background: var(--tc-bg); min-height: calc(100vh - 88px); }
.tc-wrap { max-width: 1240px; margin: 0 auto; padding: 32px 24px 64px; color: var(--tc-text); }

/* Header */
.tc-header { display: flex; justify-content: space-between; align-items: flex-end; gap: 24px; margin-bottom: 32px; flex-wrap: wrap; }
.tc-eyebrow { font-size: 11px; letter-spacing: .14em; text-transform: uppercase; color: var(--tc-primary-700); font-weight: 700; }
.tc-title { font-size: 30px; line-height: 1.15; font-weight: 700; color: var(--tc-dark); margin: 4px 0 6px; letter-spacing: -0.02em; }
.tc-sub { color: var(--tc-muted); margin: 0; }
.tc-streak { background: var(--tc-card); border: 1px solid var(--tc-line); border-radius: 12px; padding: 12px 18px; box-shadow: var(--tc-shadow-sm); text-align: right; }
.tc-streak-label { display: block; font-size: 10px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: var(--tc-muted); }
.tc-streak-value { display: block; font-size: 16px; font-weight: 700; color: var(--tc-dark); margin-top: 2px; }

/* KPIs */
.tc-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; margin-bottom: 36px; }
.tc-kpi { background: var(--tc-card); border: 1px solid var(--tc-line); border-radius: 14px; padding: 20px; box-shadow: var(--tc-shadow-sm); transition: box-shadow .2s, transform .2s; }
.tc-kpi:hover { box-shadow: var(--tc-shadow-md); transform: translateY(-1px); }
.tc-kpi-icon { width: 40px; height: 40px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; margin-bottom: 14px; }
.tc-kpi-icon svg { width: 22px; height: 22px; }
.tc-kpi-icon--green  { background: var(--tc-green-50);  color: var(--tc-green-600); }
.tc-kpi-icon--indigo { background: var(--tc-primary-50); color: var(--tc-primary-700); }
.tc-kpi-icon--orange { background: var(--tc-orange-50); color: var(--tc-orange-600); }
.tc-kpi-icon--purple { background: var(--tc-purple-50); color: var(--tc-purple-600); }
.tc-kpi-label { font-size: 11px; letter-spacing: .12em; text-transform: uppercase; color: var(--tc-muted); font-weight: 700; }
.tc-kpi-value { font-size: 28px; font-weight: 700; color: var(--tc-dark); margin-top: 4px; letter-spacing: -0.02em; }
.tc-kpi-hint { font-size: 12px; color: var(--tc-muted); margin-top: 6px; }

/* Section heading */
.tc-section { margin-bottom: 36px; }
.tc-section-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.tc-section-title { font-size: 18px; font-weight: 700; color: var(--tc-dark); letter-spacing: -0.01em; margin: 0; }

/* Continue card */
.tc-next { display: flex; align-items: center; gap: 18px; background: var(--tc-card); border: 1px solid var(--tc-line); border-radius: 16px; padding: 16px; box-shadow: var(--tc-shadow-sm); cursor: pointer; text-decoration: none !important; color: inherit; transition: box-shadow .2s, transform .2s; }
.tc-next:hover { box-shadow: var(--tc-shadow-md); transform: translateY(-1px); color: inherit; }
.tc-next-thumb { position: relative; width: 96px; height: 72px; border-radius: 10px; overflow: hidden; flex-shrink: 0; display: flex; align-items: center; justify-content: center; color: #fff; }
.tc-next-thumb-initials { font-weight: 700; font-size: 22px; opacity: .9; letter-spacing: .04em; }
.tc-next-play { position: absolute; right: 6px; bottom: 6px; width: 26px; height: 26px; border-radius: 50%; background: rgba(255,255,255,.95); color: var(--tc-primary-700); display: inline-flex; align-items: center; justify-content: center; box-shadow: var(--tc-shadow-sm); }
.tc-next-play svg { width: 12px; height: 12px; }
.tc-next-body { flex: 1; min-width: 0; }
.tc-next-eyebrow { font-size: 11px; letter-spacing: .12em; text-transform: uppercase; color: var(--tc-primary-700); font-weight: 700; }
.tc-next-title { font-size: 18px; font-weight: 700; color: var(--tc-dark); margin: 4px 0; letter-spacing: -0.01em; }
.tc-next-meta { font-size: 13px; color: var(--tc-muted); }
.tc-next-arrow { color: var(--tc-muted); }
.tc-next-arrow svg { width: 22px; height: 22px; }

/* Program grid */
.tc-program-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 24px; }
.tc-card { background: var(--tc-card); border: 1px solid var(--tc-line); border-radius: 16px; overflow: hidden; box-shadow: var(--tc-shadow-sm); cursor: pointer; transition: box-shadow .2s, transform .2s; display: flex; flex-direction: column; }
.tc-card:hover { box-shadow: var(--tc-shadow-md); transform: translateY(-2px); }
.tc-card-thumb { position: relative; height: 144px; display: flex; align-items: center; justify-content: center; color: #fff; }
.tc-card-thumb-initials { font-size: 44px; font-weight: 700; letter-spacing: .06em; opacity: .85; text-shadow: 0 2px 12px rgba(0,0,0,.18); }
.tc-card-thumb-badge { position: absolute; top: 12px; left: 12px; background: rgba(255,255,255,.92); color: var(--tc-dark); padding: 4px 10px; border-radius: 6px; font-size: 10px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }
.tc-card-body { padding: 18px 20px 20px; flex: 1; display: flex; flex-direction: column; }
.tc-card-meta { display: flex; align-items: center; gap: 8px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .12em; color: var(--tc-muted); }
.tc-card-tag { color: var(--tc-primary-700); }
.tc-card-meta-dot { color: var(--tc-line); }
.tc-card-title { font-size: 18px; font-weight: 700; color: var(--tc-dark); margin: 8px 0 6px; line-height: 1.3; letter-spacing: -0.01em; }
.tc-card-desc { color: var(--tc-muted); font-size: 13px; line-height: 1.6; margin: 0 0 14px; }
.tc-card-progress { margin-top: auto; }
.tc-card-progress-meta { display: flex; justify-content: space-between; font-size: 12px; font-weight: 600; color: var(--tc-muted); margin-bottom: 8px; }
.tc-card-progress-meta strong { color: var(--tc-dark); }
.tc-bar { height: 6px; background: var(--tc-line); border-radius: 999px; overflow: hidden; }
.tc-bar-fill { height: 100%; background: linear-gradient(90deg, var(--tc-primary-600), #B692F6); border-radius: 999px; transition: width .3s ease; }
.tc-card-footer { display: flex; justify-content: space-between; align-items: center; margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--tc-line); }
.tc-card-footer-meta { font-size: 12px; color: var(--tc-muted); font-weight: 600; }
.tc-card-cta { color: var(--tc-primary-700); font-weight: 700; font-size: 12px; letter-spacing: .12em; text-transform: uppercase; display: inline-flex; align-items: center; gap: 4px; }
.tc-card-cta svg { width: 14px; height: 14px; }

/* Empty state */
.tc-empty { margin-bottom: 32px; }
.tc-empty-card { background: var(--tc-card); border: 1px solid var(--tc-line); border-radius: 16px; padding: 48px 32px; text-align: center; box-shadow: var(--tc-shadow-sm); }
.tc-empty-card--inline { padding: 20px; }
.tc-empty-icon { width: 56px; height: 56px; border-radius: 14px; background: var(--tc-primary-50); color: var(--tc-primary-700); margin: 0 auto 16px; display: inline-flex; align-items: center; justify-content: center; }
.tc-empty-icon svg { width: 28px; height: 28px; }
.tc-empty-title { font-weight: 700; color: var(--tc-dark); }
.tc-empty-sub { color: var(--tc-muted); margin-top: 6px; font-size: 13px; }

/* Modal */
.tc-modal { position: fixed; inset: 0; z-index: 1050; display: flex; align-items: center; justify-content: center; padding: 24px; }
.tc-modal-backdrop { position: absolute; inset: 0; background: rgba(16, 24, 40, 0.55); backdrop-filter: blur(4px); }
.tc-modal-card { position: relative; background: var(--tc-card); width: 100%; max-width: 1100px; height: min(86vh, 820px); border-radius: 20px; box-shadow: var(--tc-shadow-xl); overflow: hidden; display: grid; grid-template-columns: 1fr 360px; }
.tc-modal-main { overflow-y: auto; }
.tc-modal-hero { position: relative; min-height: 200px; padding: 32px 32px 28px; color: #fff; display: flex; flex-direction: column; justify-content: flex-end; }
.tc-modal-hero::after { content: ""; position: absolute; inset: 0; background: linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,.25) 100%); pointer-events: none; }
.tc-modal-hero-inner { position: relative; z-index: 2; }
.tc-modal-hero-eyebrow { font-size: 11px; letter-spacing: .14em; text-transform: uppercase; opacity: .85; font-weight: 700; }
.tc-modal-hero-title { font-size: 28px; font-weight: 700; margin: 6px 0 4px; letter-spacing: -0.02em; color:#fff; }
.tc-modal-hero-sub { opacity: .92; margin: 0; font-size: 14px; max-width: 720px; }
.tc-modal-close { position: absolute; top: 16px; right: 16px; width: 36px; height: 36px; border-radius: 10px; background: rgba(255,255,255,.95); border: none; color: var(--tc-dark); display: inline-flex; align-items: center; justify-content: center; cursor: pointer; box-shadow: var(--tc-shadow-sm); z-index: 3; }
.tc-modal-close:hover { background: #fff; }
.tc-modal-close svg { width: 18px; height: 18px; }
.tc-modal-body { padding: 28px 32px 40px; }
.tc-loading { padding: 80px; text-align: center; color: var(--tc-muted); }

/* Side rail */
.tc-modal-side { background: var(--tc-bg); border-left: 1px solid var(--tc-line); padding: 28px 24px; overflow-y: auto; display: flex; flex-direction: column; gap: 16px; }
.tc-side-title { font-size: 18px; font-weight: 700; color: var(--tc-dark); margin: 0 0 4px; letter-spacing: -0.01em; }
.tc-side-card { background: var(--tc-card); border: 1px solid var(--tc-line); border-radius: 14px; padding: 18px; box-shadow: var(--tc-shadow-sm); }
.tc-side-card--active { border-left: 4px solid var(--tc-primary); }
.tc-side-eyebrow { font-size: 10px; letter-spacing: .14em; text-transform: uppercase; font-weight: 700; color: var(--tc-muted); margin-bottom: 10px; }
.tc-side-eyebrow--accent { color: var(--tc-primary-700); }
.tc-side-progress-row { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }
.tc-side-progress-label { font-size: 12px; font-weight: 600; color: var(--tc-text); }
.tc-side-progress-value { font-size: 22px; font-weight: 700; color: var(--tc-primary-700); letter-spacing: -0.01em; }
.tc-side-mod-title { font-size: 14px; font-weight: 700; color: var(--tc-dark); line-height: 1.35; margin-bottom: 8px; }
.tc-side-mod-meta { font-size: 11px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--tc-muted); display: inline-flex; align-items: center; gap: 6px; }
.tc-side-mod-meta svg { width: 12px; height: 12px; }
.tc-side-card--hint .tc-side-hint { font-size: 13px; color: var(--tc-text); line-height: 1.5; }
.tc-side-action { margin-top: auto; padding-top: 16px; border-top: 1px solid var(--tc-line); }

/* Levels & module cards */
.tc-lvl { margin-bottom: 28px; }
.tc-lvl-head { display: flex; justify-content: space-between; align-items: center; padding-bottom: 10px; margin-bottom: 14px; border-bottom: 1px solid var(--tc-line); }
.tc-lvl-name { font-size: 16px; font-weight: 700; color: var(--tc-dark); letter-spacing: -0.01em; }
.tc-lvl-pct { font-size: 11px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: var(--tc-muted); padding: 4px 10px; background: var(--tc-bg); border: 1px solid var(--tc-line); border-radius: 999px; }
.tc-mod-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 14px; }
.tc-mod { background: var(--tc-card); border: 1px solid var(--tc-line); border-radius: 12px; padding: 16px; cursor: pointer; transition: box-shadow .2s, transform .2s, border-color .2s; box-shadow: var(--tc-shadow-sm); }
.tc-mod:hover { box-shadow: var(--tc-shadow-md); transform: translateY(-1px); border-color: var(--tc-primary-100); }
.tc-mod--done { background: var(--tc-green-50); border-color: var(--tc-green-100); }
.tc-mod-icon { width: 36px; height: 36px; border-radius: 9px; background: var(--tc-bg); color: var(--tc-muted); display: inline-flex; align-items: center; justify-content: center; margin-bottom: 10px; }
.tc-mod-icon svg { width: 18px; height: 18px; }
.tc-mod--done .tc-mod-icon { background: #fff; color: var(--tc-green-600); box-shadow: var(--tc-shadow-sm); }
.tc-mod-title { font-size: 14px; font-weight: 700; color: var(--tc-dark); line-height: 1.4; margin-bottom: 8px; }
.tc-mod--done .tc-mod-title { color: var(--tc-green-700); }
.tc-mod-meta { display: flex; gap: 6px; flex-wrap: wrap; }
.tc-chip { display: inline-flex; align-items: center; padding: 2px 8px; border-radius: 999px; font-size: 10px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; }
.tc-chip--done  { background: #fff; color: var(--tc-green-700); border: 1px solid var(--tc-green-100); }
.tc-chip--todo  { background: #fff; color: var(--tc-muted); border: 1px solid var(--tc-line); }
.tc-chip--quiz  { background: var(--tc-primary-50); color: var(--tc-primary-700); }

/* Back nav */
.tc-back { background: none; border: none; color: var(--tc-muted); font-weight: 700; font-size: 11px; letter-spacing: .14em; text-transform: uppercase; padding: 6px 0 14px; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
.tc-back svg { width: 14px; height: 14px; transform: rotate(180deg); }
.tc-back:hover { color: var(--tc-dark); }

/* Detail */
.tc-detail-cover { position: relative; min-height: 200px; border-radius: 16px; padding: 28px; color: #fff; overflow: hidden; }
.tc-detail-cover::after { content: ""; position: absolute; inset: 0; background: linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,.32) 100%); }
.tc-detail-cover-inner { position: relative; z-index: 2; }
.tc-detail-cover-eyebrow { font-size: 11px; letter-spacing: .14em; text-transform: uppercase; opacity: .9; font-weight: 700; }
.tc-detail-cover-title { font-size: 26px; font-weight: 700; margin: 6px 0 0; letter-spacing: -0.02em; color:#fff; }
.tc-detail-cover-badge { position: absolute; top: 20px; right: 20px; background: var(--tc-green-50); color: var(--tc-green-700); padding: 6px 12px; border-radius: 999px; font-size: 11px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; display: inline-flex; align-items: center; gap: 4px; z-index: 3; }
.tc-detail-cover-badge svg { width: 12px; height: 12px; }
.tc-detail-section { margin-top: 24px; }
.tc-detail-section-title { font-size: 11px; letter-spacing: .14em; text-transform: uppercase; color: var(--tc-muted); font-weight: 700; margin-bottom: 14px; }
.tc-detail-text { color: var(--tc-text); line-height: 1.6; }

/* Files grid */
.tc-files-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
.tc-file { display: flex; align-items: center; gap: 12px; padding: 12px 14px; background: var(--tc-card); border: 1px solid var(--tc-line); border-radius: 12px; text-decoration: none !important; color: var(--tc-text); transition: border-color .2s, box-shadow .2s; box-shadow: var(--tc-shadow-sm); }
.tc-file:hover { border-color: var(--tc-primary-100); box-shadow: var(--tc-shadow-md); color: var(--tc-text); }
.tc-file-icon { width: 36px; height: 36px; border-radius: 9px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
.tc-file-icon svg { width: 20px; height: 20px; }
.tc-file--pdf .tc-file-icon { background: var(--tc-red-50); color: var(--tc-red-600); }
.tc-file--excel .tc-file-icon { background: var(--tc-green-50); color: var(--tc-green-600); }
.tc-file--image .tc-file-icon { background: var(--tc-orange-50); color: var(--tc-orange-600); }
.tc-file--video .tc-file-icon { background: var(--tc-primary-50); color: var(--tc-primary-700); }
.tc-file--link  .tc-file-icon { background: #EFF8FF; color: #1570EF; }
.tc-file--note  .tc-file-icon { background: var(--tc-bg); color: var(--tc-muted); }
.tc-file-body { flex: 1; min-width: 0; }
.tc-file-type { font-size: 10px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--tc-muted); }
.tc-file-title { font-size: 13px; font-weight: 700; color: var(--tc-dark); margin-top: 2px; white-space: nowrap; text-overflow: ellipsis; overflow: hidden; }
.tc-file-note { font-size: 12px; color: var(--tc-text); margin-top: 6px; line-height: 1.5; max-height: 80px; overflow: hidden; }
.tc-file-go { color: var(--tc-muted); }
.tc-file-go svg { width: 16px; height: 16px; }

/* Quiz card */
.tc-quiz-card { display: flex; align-items: center; gap: 14px; padding: 16px; background: var(--tc-primary-50); border: 1px solid var(--tc-primary-100); border-radius: 14px; margin-top: 24px; }
.tc-quiz-card-icon { width: 40px; height: 40px; border-radius: 10px; background: #fff; color: var(--tc-primary-700); display: inline-flex; align-items: center; justify-content: center; box-shadow: var(--tc-shadow-sm); }
.tc-quiz-card-icon svg { width: 22px; height: 22px; }
.tc-quiz-card-body { flex: 1; }
.tc-quiz-card-title { font-size: 15px; font-weight: 700; color: var(--tc-primary-700); }
.tc-quiz-card-meta { font-size: 12px; color: var(--tc-primary-700); opacity: .85; margin-top: 4px; }

/* Buttons */
.tc-btn { border: none; border-radius: 10px; padding: 12px 18px; font-weight: 700; font-size: 13px; letter-spacing: .04em; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; gap: 6px; transition: filter .15s, transform .15s, box-shadow .15s; width: 100%; }
.tc-btn:disabled { opacity: .55; cursor: not-allowed; }
.tc-btn--primary { background: var(--tc-primary); color: #fff; box-shadow: 0 6px 18px rgba(127, 86, 217, 0.28); }
.tc-btn--primary:hover:not(:disabled) { filter: brightness(1.06); transform: translateY(-1px); }
.tc-btn--ghost { background: #fff; color: var(--tc-primary-700); border: 1px solid var(--tc-primary-100); width: auto; padding: 10px 16px; }
.tc-btn--ghost:hover:not(:disabled) { background: var(--tc-primary-50); }
.tc-btn svg { width: 14px; height: 14px; }

/* Quiz runner */
.tc-quiz-run-head { margin-bottom: 22px; }
.tc-quiz-run-eyebrow { font-size: 11px; letter-spacing: .14em; text-transform: uppercase; color: var(--tc-primary-700); font-weight: 700; }
.tc-quiz-run-title { font-size: 24px; font-weight: 700; color: var(--tc-dark); letter-spacing: -0.02em; margin: 4px 0 4px; }
.tc-quiz-run-meta { font-size: 13px; color: var(--tc-muted); }
.tc-q { background: var(--tc-card); border: 1px solid var(--tc-line); border-radius: 14px; padding: 20px; margin-bottom: 14px; box-shadow: var(--tc-shadow-sm); }
.tc-q-text { font-size: 15px; font-weight: 700; color: var(--tc-dark); margin-bottom: 14px; line-height: 1.5; }
.tc-q-opts { display: flex; flex-direction: column; gap: 8px; }
.tc-q-opt { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border: 1px solid var(--tc-line); border-radius: 10px; cursor: pointer; transition: border-color .2s, background .2s; }
.tc-q-opt:hover { border-color: var(--tc-primary-100); background: var(--tc-primary-50); }
.tc-q-opt input { display: none; }
.tc-q-opt-mark { width: 18px; height: 18px; border-radius: 50%; border: 2px solid var(--tc-line); flex-shrink: 0; position: relative; transition: border-color .2s, background .2s; }
.tc-q-opt input[type="checkbox"] + .tc-q-opt-mark { border-radius: 5px; }
.tc-q-opt input:checked + .tc-q-opt-mark { border-color: var(--tc-primary); background: var(--tc-primary); }
.tc-q-opt input:checked + .tc-q-opt-mark::after { content: ""; position: absolute; inset: 3px; border-radius: 50%; background: #fff; }
.tc-q-opt input[type="checkbox"]:checked + .tc-q-opt-mark::after { border-radius: 1px; inset: 4px; clip-path: polygon(14% 44%, 0 65%, 50% 100%, 100% 16%, 80% 0%, 43% 62%); background: #fff; }
.tc-q-opt-text { color: var(--tc-text); font-size: 14px; }

/* Result */
.tc-result { text-align: center; padding: 40px 24px; }
.tc-result-emoji { width: 96px; height: 96px; border-radius: 24px; margin: 0 auto 18px; display: inline-flex; align-items: center; justify-content: center; }
.tc-result-emoji svg { width: 48px; height: 48px; }
.tc-result--pass .tc-result-emoji { background: var(--tc-green-50); color: var(--tc-green-600); }
.tc-result--fail .tc-result-emoji { background: var(--tc-red-50); color: var(--tc-red-600); }
.tc-result-title { font-size: 28px; font-weight: 700; color: var(--tc-dark); letter-spacing: -0.02em; margin: 4px 0; }
.tc-result-sub { color: var(--tc-muted); font-size: 15px; margin: 0 0 16px; }
.tc-result-pill { display: inline-block; padding: 8px 18px; border-radius: 999px; font-size: 11px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }
.tc-result--pass .tc-result-pill { background: var(--tc-green-600); color: #fff; }
.tc-result--fail .tc-result-pill { background: var(--tc-red-600); color: #fff; }
.tc-result-actions { margin-top: 28px; display: flex; justify-content: center; }
.tc-result-actions .tc-btn { width: auto; padding: 12px 32px; }

/* Mobile */
@media (max-width: 880px) {
    .tc-modal-card { grid-template-columns: 1fr; height: 92vh; }
    .tc-modal-side { border-left: none; border-top: 1px solid var(--tc-line); }
    .tc-program-grid { grid-template-columns: 1fr; }
    .tc-header { flex-direction: column; align-items: flex-start; }
}
`;
    document.head.appendChild(style);
}
