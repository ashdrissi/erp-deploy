(function () {
    const METHOD = "orderlift.orderlift.page.menu_editor.menu_editor";
    const STATE = { data: { sections: [] }, dirty: false, loading: false, openSections: new Set() };

    frappe.pages["menu-editor"].on_page_load = function (wrapper) {
        const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Menu Editor"), single_column: true });
        wrapper.page = page;
        page.main.addClass("menu-editor-root");
        injectStyles();
        renderLoading(page);
        load(page);
    };

    frappe.pages["menu-editor"].on_page_show = function (wrapper) {
        if (wrapper.page && !STATE.loading) load(wrapper.page);
    };

    async function load(page) {
        STATE.loading = true;
        try {
            const response = await frappe.call({ method: `${METHOD}.get_menu_editor_data` });
            STATE.data = response.message || { sections: [] };
            STATE.dirty = false;
            STATE.openSections = new Set();
            render(page);
        } catch (error) {
            renderError(page, error);
        } finally {
            STATE.loading = false;
        }
    }

    function renderLoading(page) {
        page.main.html(`
            <div class="me-shell">
                <section class="me-hero me-skeleton-panel"><div class="me-shimmer h-lg"></div><div class="me-shimmer h-sm"></div></section>
                <section class="me-layout"><div class="me-shimmer h-xl"></div></section>
            </div>
        `);
    }

    function renderError(page, error) {
        page.main.html(`
            <div class="me-shell">
                <div class="me-error-state">
                    <div class="me-error-icon">${ICONS.lock}</div>
                    <h2>${__("Menu Editor could not load")}</h2>
                    <p>${escapeHtml(error.message || __("Check your permissions or try again."))}</p>
                    <button class="me-btn me-btn-primary" data-retry>${__("Retry")}</button>
                </div>
            </div>
        `);
        page.main.find("[data-retry]").on("click", () => load(page));
    }

    function render(page) {
        const sections = STATE.data.sections || [];
        const totalItems = sections.reduce((count, section) => count + (section.items || []).length, 0);
        page.set_title(__("Menu Editor"));
        page.main.html(`
            <div class="me-shell">
                <nav class="me-breadcrumb" aria-label="${__("Breadcrumb")}">
                    <a href="/desk/home-page?sidebar=Main+Dashboard">${__("Settings")}</a>
                    <span>/</span>
                    <a href="/desk/home-page?sidebar=Main+Dashboard">${__("Administration")}</a>
                    <span>/</span>
                    <strong>${__("Menu Editor")}</strong>
                </nav>
                <section class="me-toolbar">
                    <div class="me-title-line">
                        <span class="me-lock">${ICONS.lock}</span>
                        <div><h1>${__("Menu Editor")}</h1><p>${__("Labels and order only. Routes, roles, targets, and sections are locked.")}</p></div>
                    </div>
                    <div class="me-toolbar-actions">
                        <span><strong>${formatNumber(sections.length)}</strong> ${__("sections")}</span>
                        <span><strong>${formatNumber(totalItems)}</strong> ${__("items")}</span>
                        <span class="${STATE.dirty ? "dirty" : ""}">${STATE.dirty ? __("Unsaved") : __("Saved")}</span>
                        <button class="me-btn me-btn-primary" data-save-menu ${STATE.dirty ? "" : "disabled"}>${ICONS.check}${__("Save")}</button>
                    </div>
                </section>
                <section class="me-layout">
                    <main class="me-sections" role="main">
                        ${sections.map(sectionMarkup).join("") || emptyState()}
                    </main>
                </section>
            </div>
        `);
        bind(page);
    }

    function sectionMarkup(section, index) {
        const items = section.items || [];
        const sectionKeyValue = String(section.key || section.label);
        const sectionKey = escapeHtml(sectionKeyValue);
        const isOpen = STATE.openSections.has(sectionKeyValue);
        const sectionNumber = String(index + 1).padStart(2, "0");
        return `
            <details class="me-section" data-section-key="${sectionKey}" ${isOpen ? "open" : ""}>
                <summary>
                    <div>
                        <span class="me-drag-handle" draggable="true" data-section-drag="${sectionKey}" title="${__("Drag group")}" aria-label="${__("Drag group")}">${ICONS.grip}</span>
                        <span class="me-group-number">${sectionNumber}</span>
                        <span class="me-section-kicker">${__("Section")}</span>
                        <h2>${escapeHtml(section.label)}</h2>
                    </div>
                    <div class="me-section-actions">
                        <button class="me-icon-btn" data-section-move="up" data-section-key="${sectionKey}" aria-label="${__("Move section up")}">${ICONS.chevronUp}</button>
                        <button class="me-icon-btn" data-section-move="down" data-section-key="${sectionKey}" aria-label="${__("Move section down")}">${ICONS.chevronDown}</button>
                        <span class="me-count-pill"><strong>${formatNumber(items.length)}</strong> ${__("items")}</span>
                    </div>
                </summary>
                <div class="me-items">
                    ${items.map((item, index) => itemMarkup(item, index, items.length)).join("")}
                </div>
            </details>
        `;
    }

    function itemMarkup(item, index, total) {
        const key = escapeHtml(item.key);
        const defaultLabel = item.default_label || item.label || "";
        return `
            <div class="me-row" data-menu-row="${key}">
                <div class="me-position"><span>${String(index + 1).padStart(2, "0")}</span></div>
                <div class="me-fields">
                    <label>
                        <span>${__("Label")}</span>
                        <input data-menu-label value="${escapeHtml(item.label)}" maxlength="120" title="${__("Default")}: ${escapeHtml(defaultLabel)}" />
                    </label>
                    <div class="me-row-meta">
                        <span class="me-key">${escapeHtml(item.key)}</span>
                        <span>${__("Default")}: ${escapeHtml(defaultLabel)}</span>
                    </div>
                </div>
                <div class="me-actions">
                    <button class="me-icon-btn" data-move="up" data-key="${key}" aria-label="${__("Move up")}" ${index === 0 ? "disabled" : ""}>${ICONS.chevronUp}</button>
                    <button class="me-icon-btn" data-move="down" data-key="${key}" aria-label="${__("Move down")}" ${index === total - 1 ? "disabled" : ""}>${ICONS.chevronDown}</button>
                    <button class="me-text-btn" data-reset-label data-key="${key}" type="button">${__("Reset")}</button>
                    <input data-menu-order type="hidden" value="${Number(item.menu_order || 0) || index + 1}" />
                </div>
            </div>
        `;
    }

    function bind(page) {
        page.main.find("[data-save-menu]").on("click", () => save(page));
        page.main.find("[data-move]").on("click", function () {
            moveItem(page, $(this).data("move"), $(this).data("key"));
        });
        page.main.find("[data-section-move]").on("click", function (event) {
            event.preventDefault();
            event.stopPropagation();
            moveSection(page, $(this).data("section-move"), $(this).data("section-key"));
        });
        page.main.find("[data-section-drag]").on("click", function (event) {
            event.preventDefault();
            event.stopPropagation();
        });
        page.main.find("[data-section-drag]").on("dragstart", function (event) {
            const sectionKey = String($(this).attr("data-section-drag") || "");
            if (!sectionKey) return;
            const originalEvent = event.originalEvent;
            if (originalEvent && originalEvent.dataTransfer) {
                originalEvent.dataTransfer.effectAllowed = "move";
                originalEvent.dataTransfer.setData("text/plain", sectionKey);
            }
            $(this).closest(".me-section").addClass("dragging");
        });
        page.main.find("[data-section-drag]").on("dragend", function () {
            page.main.find(".me-section").removeClass("dragging drag-over");
        });
        page.main.find(".me-section").on("dragover", function (event) {
            event.preventDefault();
            $(this).addClass("drag-over");
        });
        page.main.find(".me-section").on("dragleave", function () {
            $(this).removeClass("drag-over");
        });
        page.main.find(".me-section").on("drop", function (event) {
            event.preventDefault();
            const originalEvent = event.originalEvent;
            const sourceKey = originalEvent && originalEvent.dataTransfer ? originalEvent.dataTransfer.getData("text/plain") : "";
            const targetKey = String($(this).attr("data-section-key") || "");
            page.main.find(".me-section").removeClass("dragging drag-over");
            moveSectionTo(page, sourceKey, targetKey);
        });
        page.main.find(".me-section").on("toggle", function () {
            const sectionKey = String($(this).data("section-key") || "");
            if (!sectionKey) return;
            if (this.open) STATE.openSections.add(sectionKey);
            else STATE.openSections.delete(sectionKey);
        });
        page.main.find("[data-reset-label]").on("click", function () {
            resetLabel(page, $(this).data("key"));
        });
        page.main.find("[data-menu-label]").on("input", function () {
            $(this).closest(".me-row").addClass("changed");
            setDirty(page, true);
        });
    }

    function moveItem(page, direction, key) {
        for (const section of STATE.data.sections || []) {
            const items = section.items || [];
            const index = items.findIndex((item) => item.key === key);
            const swapIndex = direction === "up" ? index - 1 : index + 1;
            if (index < 0 || swapIndex < 0 || swapIndex >= items.length) continue;
            [items[index], items[swapIndex]] = [items[swapIndex], items[index]];
            STATE.openSections.add(String(section.key || section.label));
            setDirty(page, true, false);
            render(page);
            return;
        }
    }

    function moveSection(page, direction, key) {
        const sections = STATE.data.sections || [];
        const index = sections.findIndex((section) => String(section.key || section.label) === String(key));
        const swapIndex = direction === "up" ? index - 1 : index + 1;
        if (index < 0 || swapIndex < 0 || swapIndex >= sections.length) return;
        [sections[index], sections[swapIndex]] = [sections[swapIndex], sections[index]];
        setDirty(page, true, false);
        render(page);
    }

    function moveSectionTo(page, sourceKey, targetKey) {
        if (!sourceKey || !targetKey || sourceKey === targetKey) return;
        const sections = STATE.data.sections || [];
        const sourceIndex = sections.findIndex((section) => String(section.key || section.label) === String(sourceKey));
        const targetIndex = sections.findIndex((section) => String(section.key || section.label) === String(targetKey));
        if (sourceIndex < 0 || targetIndex < 0) return;
        const [section] = sections.splice(sourceIndex, 1);
        const adjustedTarget = sourceIndex < targetIndex ? targetIndex - 1 : targetIndex;
        sections.splice(adjustedTarget, 0, section);
        setDirty(page, true, false);
        render(page);
    }

    function resetLabel(page, key) {
        const item = findItem(key);
        if (!item) return;
        const row = page.main.find("[data-menu-row]").filter(function () { return $(this).data("menu-row") === key; });
        row.find("[data-menu-label]").val(item.default_label || item.label || "");
        row.addClass("changed");
        setDirty(page, true);
    }

    function renderSortedFromDom(page) {
        const itemsByKey = collectItems(page).reduce((acc, item) => {
            acc[item.key] = item;
            return acc;
        }, {});
        STATE.data.sections = (STATE.data.sections || []).map((section) => ({
            ...section,
            items: (section.items || [])
                .map((item) => ({ ...item, ...itemsByKey[item.key] }))
                .sort((a, b) => Number(a.menu_order || 0) - Number(b.menu_order || 0)),
        }));
        render(page);
    }

    function collectItems(page) {
        const labelsByKey = page.main.find("[data-menu-row]").map(function () {
            return {
                key: String($(this).data("menu-row") || ""),
                label: String($(this).find("[data-menu-label]").val() || "").trim(),
            };
        }).get().reduce((acc, item) => {
            acc[item.key] = item.label;
            return acc;
        }, {});
        const items = [];
        for (const section of STATE.data.sections || []) {
            for (const item of section.items || []) {
                items.push({
                    key: item.key,
                    label: labelsByKey[item.key] != null ? labelsByKey[item.key] : item.label,
                    menu_order: items.length + 1,
                });
            }
        }
        return items;
    }

    async function save(page) {
        const items = collectItems(page);
        try {
            const response = await frappe.call({ method: `${METHOD}.save_menu_editor_data`, args: { items }, freeze: true });
            STATE.data = response.message || STATE.data;
            STATE.dirty = false;
            frappe.show_alert({ message: __("Menu updated. Refreshing Desk..."), indicator: "green" });
            window.setTimeout(() => window.location.reload(), 700);
        } catch (error) {
            frappe.msgprint({ title: __("Menu Save Failed"), message: error.message || __("Could not save menu changes."), indicator: "red" });
        }
    }

    function setDirty(page, dirty, updateButton = true) {
        STATE.dirty = dirty;
        if (!updateButton) return;
        page.main.find("[data-save-menu]").prop("disabled", !dirty);
    }

    function findItem(key) {
        for (const section of STATE.data.sections || []) {
            const item = (section.items || []).find((row) => row.key === key);
            if (item) return item;
        }
        return null;
    }

    function emptyState() {
        return `
            <div class="me-empty-state">
                <div>${ICONS.info}</div>
                <h3>${__("No menu items found")}</h3>
                <p>${__("Run the Main Dashboard setup to seed the controlled menu registry.")}</p>
            </div>
        `;
    }

    function formatNumber(value) {
        return Number(value || 0).toLocaleString();
    }

    function escapeHtml(value) {
        return frappe.utils.escape_html(value == null ? "" : String(value));
    }

    const ICONS = {
        lock: `<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>`,
        check: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 6L9 17l-5-5"/></svg>`,
        info: `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>`,
        spark: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2l1.7 6.3L20 10l-6.3 1.7L12 18l-1.7-6.3L4 10l6.3-1.7L12 2z"/></svg>`,
        chevronUp: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 15l-6-6-6 6"/></svg>`,
        chevronDown: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>`,
        grip: `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="5" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="9" cy="19" r="1"/><circle cx="15" cy="19" r="1"/></svg>`,
    };

    function injectStyles() {
        if (document.getElementById("menu-editor-style")) return;
        const style = document.createElement("style");
        style.id = "menu-editor-style";
        style.textContent = `
            @import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;450;500;600;700&family=Geist+Mono:wght@400;500&display=swap');
            .menu-editor-root { --canvas:#FAFBFC; --canvas-2:#F4F6F8; --surface:#FFFFFF; --surface-2:#F7F8FA; --surface-3:#F0F2F5; --ink-1000:#0A0E1A; --ink-900:#11151F; --ink-800:#1F2433; --ink-700:#2E3548; --ink-600:#495061; --ink-500:#6B7280; --ink-400:#9099A6; --ink-300:#B8BFC9; --ink-200:#DDE1E7; --ink-150:#E8EBEF; --ink-100:#EFF1F4; --primary-700:#3730A3; --primary-600:#4F46E5; --primary-500:#6366F1; --primary-300:#A5B4FC; --primary-100:#E0E7FF; --primary-50:#EEF2FF; --success-700:#047857; --success-600:#059669; --success-500:#10B981; --success-100:#D1FAE5; --success-50:#ECFDF5; --cyan-700:#0E7490; --cyan-500:#06B6D4; --cyan-100:#CFFAFE; --cyan-50:#ECFEFF; --rose-700:#BE123C; --rose-600:#E11D48; --rose-100:#FFE4E6; --rose-50:#FFF1F2; --font-sans:'Geist',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; --font-mono:'Geist Mono','SF Mono',Menlo,monospace; --r-lg:14px; --r-2xl:22px; --shadow-xs:0 1px 2px rgba(15,23,42,.04); --shadow-sm:0 1px 2px rgba(15,23,42,.04),0 2px 4px rgba(15,23,42,.04); --shadow-md:0 2px 4px rgba(15,23,42,.04),0 4px 12px rgba(15,23,42,.05); --shadow-lg:0 4px 8px rgba(15,23,42,.04),0 16px 32px -8px rgba(15,23,42,.08); --ease:cubic-bezier(.32,.72,0,1); --ring:0 0 0 3px rgba(99,102,241,.15); min-height:calc(100vh - 72px); color:var(--ink-900); background:radial-gradient(circle at 15% 0%,rgba(99,102,241,.06) 0%,transparent 48%),radial-gradient(circle at 85% 12%,rgba(6,182,212,.055) 0%,transparent 42%),linear-gradient(to bottom,var(--canvas),var(--canvas-2)); font-family:var(--font-sans); font-feature-settings:'cv11','ss01','ss03'; -webkit-font-smoothing:antialiased; }
            .menu-editor-root * { box-sizing:border-box; } .menu-editor-root svg { width:16px; height:16px; fill:none; stroke:currentColor; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; } .menu-editor-root button,.menu-editor-root input { font-family:inherit; } :where(.menu-editor-root button) { cursor:pointer; }
            .menu-editor-root *::-webkit-scrollbar { width:8px; height:8px; } .menu-editor-root *::-webkit-scrollbar-thumb { background:var(--ink-200); border-radius:4px; } .menu-editor-root *::-webkit-scrollbar-thumb:hover { background:var(--ink-300); }
            .me-shell { max-width:1560px; margin:0 auto; padding:14px 18px 72px; display:grid; gap:10px; }
            .me-breadcrumb { display:flex; align-items:center; gap:6px; font-size:11px; color:var(--ink-500); font-family:var(--font-mono); } .me-breadcrumb a { color:var(--ink-500); text-decoration:none; } .me-breadcrumb a:hover { color:var(--ink-800); } .me-breadcrumb span { color:var(--ink-300); } .me-breadcrumb strong { color:var(--ink-800); font-weight:500; }
            .me-toolbar { position:sticky; top:0; z-index:5; display:flex; justify-content:space-between; gap:12px; align-items:center; padding:10px 12px; border:1px solid var(--ink-150); border-radius:12px; background:rgba(255,255,255,.94); box-shadow:var(--shadow-sm); backdrop-filter:blur(10px); }
            .me-title-line { display:flex; align-items:center; gap:10px; min-width:0; } .me-lock { width:28px; height:28px; display:flex; align-items:center; justify-content:center; flex-shrink:0; border-radius:8px; color:#fff; background:linear-gradient(135deg,var(--primary-600),var(--cyan-500)); } .me-lock svg { width:14px; height:14px; }
            .me-toolbar h1 { margin:0; color:var(--ink-1000); font-size:18px; font-weight:700; letter-spacing:-.02em; line-height:1.15; } .me-toolbar p { margin:2px 0 0; color:var(--ink-500); font-size:12px; line-height:1.3; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
            .me-toolbar-actions { display:flex; align-items:center; justify-content:flex-end; gap:8px; flex-wrap:wrap; } .me-toolbar-actions > span { display:inline-flex; align-items:center; gap:4px; min-height:28px; padding:4px 8px; border:1px solid var(--ink-100); border-radius:8px; background:var(--surface-2); color:var(--ink-500); font-size:11px; font-weight:600; } .me-toolbar-actions strong { color:var(--ink-900); font-weight:700; } .me-toolbar-actions .dirty { color:var(--rose-700); background:var(--rose-50); border-color:var(--rose-100); }
            .me-btn { display:inline-flex; align-items:center; justify-content:center; gap:6px; min-height:30px; padding:6px 11px; border-radius:8px; border:1px solid transparent; font-size:12px; font-weight:700; transition:all .2s var(--ease); } .me-btn svg { width:13px; height:13px; } .me-btn-primary { background:var(--ink-1000); color:#fff; box-shadow:inset 0 1px 0 rgba(255,255,255,.1),var(--shadow-xs); } .me-btn-primary:hover:not(:disabled) { background:var(--ink-800); } .me-btn:disabled { opacity:.48; cursor:not-allowed; }
            .me-layout { display:block; } .me-sections { display:grid; grid-template-columns:repeat(auto-fill,minmax(360px,1fr)); gap:10px; min-width:0; } .me-section { overflow:hidden; min-width:0; border:1px solid var(--ink-150); border-radius:12px; background:var(--surface); box-shadow:var(--shadow-xs); transition:opacity .15s var(--ease), border-color .15s var(--ease), box-shadow .15s var(--ease); } .me-section.dragging { opacity:.48; } .me-section.drag-over { border-color:var(--primary-500); box-shadow:var(--ring),var(--shadow-sm); } .me-section summary { display:flex; align-items:center; justify-content:space-between; gap:8px; padding:9px 11px; background:var(--surface-2); cursor:pointer; list-style:none; } .me-section summary > div:first-child { display:flex; align-items:center; gap:8px; min-width:0; } .me-section[open] summary { border-bottom:1px solid var(--ink-100); } .me-section summary::-webkit-details-marker { display:none; } .me-section-kicker { display:none; } .me-section h2 { margin:0; color:var(--ink-1000); font-size:13px; font-weight:700; letter-spacing:-.01em; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
            .me-group-number { width:25px; height:22px; display:inline-flex; align-items:center; justify-content:center; flex-shrink:0; border:1px solid var(--primary-100); border-radius:7px; background:var(--primary-50); color:var(--primary-700); font-family:var(--font-mono); font-size:10px; font-weight:700; }
            .me-drag-handle { width:22px; height:22px; display:inline-flex; align-items:center; justify-content:center; flex-shrink:0; border:1px solid var(--ink-150); border-radius:7px; background:var(--surface); color:var(--ink-500); cursor:grab; } .me-drag-handle:active { cursor:grabbing; } .me-drag-handle:hover { color:var(--ink-900); border-color:var(--ink-300); background:#fff; } .me-drag-handle svg { width:13px; height:13px; fill:currentColor; stroke:none; }
            .me-section-actions { display:flex; align-items:center; gap:4px; flex-shrink:0; }
            .me-count-pill { display:inline-flex; align-items:center; gap:4px; flex-shrink:0; padding:3px 7px; border:1px solid var(--ink-150); border-radius:999px; background:var(--surface); color:var(--ink-600); font-size:11px; } .me-count-pill strong { color:var(--ink-900); font-weight:700; }
            .me-items { display:grid; } .me-row { display:grid; grid-template-columns:30px minmax(0,1fr) auto; gap:8px; align-items:center; padding:7px 9px; border-bottom:1px solid var(--ink-100); background:#fff; transition:background .18s var(--ease), box-shadow .18s var(--ease); } .me-row:last-child { border-bottom:0; } .me-row:hover { background:var(--surface-2); } .me-row.changed { box-shadow:inset 2px 0 0 var(--primary-600); background:var(--primary-50); }
            .me-position span { width:24px; height:24px; display:inline-flex; align-items:center; justify-content:center; border:1px solid var(--ink-150); border-radius:7px; background:var(--surface); color:var(--ink-500); font-family:var(--font-mono); font-size:10px; font-weight:700; } .me-fields { min-width:0; display:grid; gap:4px; } .me-fields label { display:grid; grid-template-columns:34px minmax(0,1fr); gap:7px; align-items:center; margin:0; } .me-fields label > span { color:var(--ink-500); font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.05em; } .me-fields input { width:100%; height:30px; min-height:30px; padding:5px 8px; border:1px solid var(--ink-200); border-radius:8px; outline:0; background:var(--surface); color:var(--ink-900); font-size:12px; font-weight:600; transition:all .2s var(--ease); } .me-fields input:focus { border-color:var(--primary-500); box-shadow:var(--ring); }
            .me-row-meta { display:flex; flex-wrap:nowrap; gap:5px; min-width:0; color:var(--ink-500); font-size:10px; line-height:1.2; } .me-row-meta span { display:inline-flex; align-items:center; min-width:0; max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; } .me-key { max-width:42%; padding:2px 5px; border:1px solid var(--ink-100); border-radius:5px; background:var(--surface-2); color:var(--ink-500); font-family:var(--font-mono); }
            .me-actions { display:grid; grid-template-columns:26px 26px; gap:4px; align-items:center; justify-content:end; } .me-icon-btn,.me-text-btn { border:1px solid var(--ink-200); background:var(--surface); color:var(--ink-600); transition:all .18s var(--ease); } .me-icon-btn { width:26px; height:26px; display:inline-flex; align-items:center; justify-content:center; border-radius:7px; } .me-icon-btn svg { width:12px; height:12px; } .me-icon-btn:hover:not(:disabled),.me-text-btn:hover { border-color:var(--ink-300); background:var(--ink-1000); color:#fff; } .me-icon-btn:disabled { opacity:.35; cursor:not-allowed; } .me-text-btn { grid-column:1 / -1; min-height:23px; padding:3px 6px; border-radius:7px; font-size:10px; font-weight:700; }
            .me-empty-state,.me-error-state { min-height:420px; display:grid; place-items:center; text-align:center; padding:36px; border:1px solid var(--ink-150); border-radius:var(--r-2xl); background:var(--surface); box-shadow:var(--shadow-md); } .me-empty-state > div,.me-error-icon { color:var(--ink-400); } .me-empty-state svg,.me-error-icon svg { width:34px; height:34px; } .me-empty-state h3,.me-error-state h2 { margin:12px 0 6px; color:var(--ink-1000); font-weight:650; } .me-empty-state p,.me-error-state p { margin:0 0 16px; max-width:430px; color:var(--ink-500); line-height:1.5; }
            .me-shimmer { position:relative; overflow:hidden; border-radius:14px; background:var(--ink-150); } .me-shimmer::after { content:''; position:absolute; inset:0; transform:translateX(-100%); background:linear-gradient(90deg,transparent,rgba(255,255,255,.72),transparent); animation:meShimmer 1.4s infinite; } .h-lg { height:58px; width:55%; } .h-sm { height:20px; width:80%; margin-top:16px; } .h-xl { height:520px; } .me-skeleton-panel { display:block; }
            @keyframes meShimmer { 100% { transform:translateX(100%); } }
            @media (prefers-reduced-motion: reduce) { .menu-editor-root *, .menu-editor-root *::before, .menu-editor-root *::after { animation-duration:.01ms !important; transition-duration:.01ms !important; } }
            @media (max-width:900px) { .me-shell { padding:12px 12px 72px; } .me-toolbar { align-items:flex-start; flex-direction:column; } .me-toolbar-actions { justify-content:flex-start; } .me-sections { grid-template-columns:1fr; } }
            @media (max-width:640px) { .me-toolbar p { white-space:normal; } .me-row { grid-template-columns:28px minmax(0,1fr); } .me-actions { grid-column:2; grid-template-columns:26px 26px minmax(58px,1fr); } .me-text-btn { grid-column:auto; } }
        `;
        document.head.appendChild(style);
    }
})();
