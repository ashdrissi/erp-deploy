(function () {
    "use strict";

    const METHOD = "orderlift.annex_chain.get_annex_workspace";
    const COPY_METHOD = "orderlift.annex_chain.create_execution_copy";
    const FIELD_BY_DOCTYPE = {
        Quotation: "custom_fiches_annexes_html",
        "Sales Order": "custom_fiches_annexes_html",
        Project: "custom_fiches_annexes_html",
        "Sales Order Technical List Revision": "fiches_annexes_html",
    };
    const states = new WeakMap();

    async function mount(frm) {
        const fieldname = frm && FIELD_BY_DOCTYPE[frm.doctype];
        const field = fieldname && frm.get_field && frm.get_field(fieldname);
        if (!field || !field.$wrapper) return;

        const root = field.$wrapper.get(0);
        let state = states.get(root);
        const reference = `${frm.doctype}::${frm.doc && frm.doc.name}`;
        if (!state || state.reference !== reference) {
            state = { reference, activePhase: "", sourceByPhase: {}, request: 0, payload: null };
            states.set(root, state);
        }
        state.frm = frm;
        state.root = field.$wrapper;

        if (isNew(frm)) {
            state.root.html(stateMarkup("empty", __("Save this document to view its annexes.")));
            return;
        }
        await load(state);
    }

    async function load(state) {
        const request = ++state.request;
        state.root.html(loadingMarkup());
        try {
            const response = await frappe.call({
                method: METHOD,
                args: {
                    reference_doctype: state.frm.doctype,
                    reference_name: state.frm.doc.name,
                },
            });
            if (request !== state.request || states.get(state.root.get(0)) !== state) return;
            state.payload = normalizePayload(response.message || {});
            if (!state.payload.phases.some((phase) => phase.key === state.activePhase)) {
                state.activePhase = state.payload.phases[0] ? state.payload.phases[0].key : "";
            }
            render(state);
        } catch (error) {
            if (request !== state.request || states.get(state.root.get(0)) !== state) return;
            console.error("Unable to load the annex workspace", error);
            state.root.html(errorMarkup());
            state.root.find("[data-fa-retry]").on("click", () => load(state));
        }
    }

    function normalizePayload(payload) {
        const phases = (Array.isArray(payload.phases) ? payload.phases : []).map((phase, index) => {
            const key = String(phase.key || `phase-${index + 1}`);
            const rawEntries = phase.entries || phase.annexes || phase.rows || [];
            const entries = (Array.isArray(rawEntries) ? rawEntries : []).map((entry, entryIndex) => normalizeEntry(entry, key, entryIndex));
            const sources = normalizeSources(phase.sources, entries);
            return {
                ...phase,
                key,
                label: phase.label || key,
                count: phase.count == null ? entries.length : Number(phase.count || 0),
                entries,
                sources,
            };
        });
        return { phases, capabilities: payload.capabilities || {} };
    }

    function normalizeSources(sources, entries) {
        const rows = Array.isArray(sources) ? sources : [];
        const normalized = rows.map((source, index) => normalizeSource(source, index));
        const seen = new Set(normalized.map((source) => source.key));
        entries.forEach((entry, index) => {
            const source = sourceFromEntry(entry, index);
            if (source.key && !seen.has(source.key)) {
                normalized.push(source);
                seen.add(source.key);
            }
        });
        return normalized.map((source) => ({
            ...source,
            count: source.count == null
                ? entries.filter((entry, index) => sourceFromEntry(entry, index).key === source.key).length
                : source.count,
        }));
    }

    function normalizeEntry(entry, phaseKey, index) {
        const row = entry || {};
        const source = sourceFromEntry(row, index);
        const annex = annexName(row);
        const identity = annex || row.key || row.template_name || row.label || `annex-${index + 1}`;
        return {
            ...row,
            source_key: source.key,
            source_doctype: source.doctype,
            source_name: source.name,
            source_label: source.label,
            _ui_key: `${phaseKey}::${source.key}::${identity}::${index}`,
        };
    }

    function normalizeSource(source, index) {
        if (typeof source === "string") return { key: source, label: source, doctype: "", name: source, count: null };
        const row = source || {};
        const doctype = row.doctype || row.source_doctype || "";
        const name = row.name || row.source_name || "";
        return {
            ...row,
            key: String(row.key || sourceKey(doctype, name) || `source-${index + 1}`),
            label: row.label || row.source_label || name || doctype || __("Source"),
            doctype,
            name,
            count: row.count == null ? null : Number(row.count || 0),
        };
    }

    function sourceFromEntry(entry, index) {
        const nested = entry.source || entry.reference || {};
        const doctype = entry.source_doctype || nested.doctype || "";
        const name = entry.source_name || nested.name || "";
        return {
            key: String(entry.source_key || sourceKey(doctype, name) || `entry-source-${index + 1}`),
            label: entry.source_label || nested.label || name || doctype || __("Current document"),
            doctype,
            name,
            count: null,
        };
    }

    function render(state) {
        const phases = state.payload.phases;
        if (!phases.length) {
            state.root.html(stateMarkup("empty", __("No annex phases are available for this document.")));
            return;
        }
        const active = phases.find((phase) => phase.key === state.activePhase) || phases[0];
        state.activePhase = active.key;
        const selectedSource = validSource(active, state.sourceByPhase[active.key]);
        state.sourceByPhase[active.key] = selectedSource;
        const entries = selectedSource === "all"
            ? active.entries
            : active.entries.filter((entry, index) => sourceFromEntry(entry, index).key === selectedSource);
        const tabId = domId(state.reference, active.key);

        state.root.html(`
            <section class="ol-fa-workspace" aria-label="${attr(__("Annex workspace"))}">
                <header class="ol-fa-head">
                    <div><strong>${esc(__("Fiches annexes"))}</strong><span>${esc(__("Document chain"))}</span></div>
                    <button type="button" class="ol-fa-icon-button" data-fa-refresh aria-label="${attr(__("Refresh annexes"))}" title="${attr(__("Refresh"))}">${icon("refresh")}</button>
                </header>
                <div class="ol-fa-tabs" role="tablist" aria-label="${attr(__("Annex phases"))}">
                    ${phases.map((phase) => phaseTab(phase, phase.key === active.key, state.reference)).join("")}
                </div>
                <div id="${attr(tabId)}-panel" class="ol-fa-panel" role="tabpanel" tabindex="0" aria-labelledby="${attr(tabId)}-tab">
                    ${sourceControls(active, selectedSource)}
                    ${entries.length ? tableMarkup(entries, state, active) : filteredEmptyMarkup(active, selectedSource)}
                </div>
            </section>
        `);
        bind(state);
    }

    function phaseTab(phase, active, reference) {
        const id = domId(reference, phase.key);
        const count = Number(phase.count || 0);
        return `<button type="button" id="${attr(id)}-tab" role="tab" aria-label="${attr(__("{0}: {1} annexes", [phase.label, count]))}" aria-selected="${active ? "true" : "false"}" aria-controls="${attr(id)}-panel" tabindex="${active ? "0" : "-1"}" class="${active ? "active" : ""}" data-fa-phase="${attr(phase.key)}"><span>${esc(__(phase.label))}</span><b aria-hidden="true">${count}</b></button>`;
    }

    function sourceControls(phase, selected) {
        if (phase.sources.length < 2) return "";
        const options = [{ key: "all", label: __("All sources"), count: phase.count }, ...phase.sources];
        return `<div class="ol-fa-sources" role="group" aria-label="${attr(__("Filter by source document"))}">
            <div class="ol-fa-source-chips">${options.map((source) => `<button type="button" class="${source.key === selected ? "active" : ""}" data-fa-source="${attr(source.key)}" aria-pressed="${source.key === selected ? "true" : "false"}"><span>${esc(source.label)}</span>${source.count == null ? "" : `<b>${Number(source.count || 0)}</b>`}</button>`).join("")}</div>
            <label class="ol-fa-source-select"><span>${esc(__("Source"))}</span><select data-fa-source-select>${options.map((source) => `<option value="${attr(source.key)}" ${source.key === selected ? "selected" : ""}>${esc(source.label)}</option>`).join("")}</select></label>
        </div>`;
    }

    function tableMarkup(entries, state, phase) {
        return `<div class="ol-fa-table-wrap"><table class="ol-fa-table">
            <caption>${esc(__("Annexes in the selected phase and source"))}</caption>
            <thead><tr><th>${esc(__("Document"))}</th><th>${esc(__("Source"))}</th><th>${esc(__("Status"))}</th><th>${esc(__("Updated"))}</th><th class="right">${esc(__("Actions"))}</th></tr></thead>
            <tbody>${entries.map((entry) => entryMarkup(entry, state, phase)).join("")}</tbody>
        </table></div>`;
    }

    function entryMarkup(entry, state, phase) {
        const key = entry._ui_key;
        const editable = Boolean(entry.editable) && !entry.read_only_reason;
        const complete = Boolean(entry.is_complete);
        const source = entry.source_label || entry.source_name || entry.source_doctype || __("Current document");
        const status = entry.status || (complete ? __("Complete") : __("Draft"));
        const revision = executionRevision(entry, phase, state.payload.capabilities, state.frm);
        const canCopy = Boolean(entry.can_copy_to_execution) && Boolean(revision) && Boolean(annexName(entry));
        const canOpen = Boolean(annexName(entry) || (editable && entry.template));
        const reason = entry.read_only_reason || (!annexName(entry) ? __("The annex has not been created yet.") : "");
        return `<tr data-fa-entry="${attr(key)}">
            <td data-label="${attr(__("Document"))}"><div class="ol-fa-document"><span>${icon("file")}</span><div><strong>${esc(entry.template_name || entry.label || entry.key || __("Annex"))}</strong><small>${esc(annexName(entry) || entry.key || __("Not created"))}</small></div></div></td>
            <td data-label="${attr(__("Source"))}"><span class="ol-fa-source" title="${attr(source)}">${esc(source)}</span></td>
            <td data-label="${attr(__("Status"))}"><span class="ol-fa-status ${complete ? "complete" : "draft"}"><i aria-hidden="true"></i>${esc(status)}</span>${reason ? `<small class="ol-fa-reason" title="${attr(reason)}">${esc(reason)}</small>` : ""}</td>
            <td data-label="${attr(__("Updated"))}"><time class="ol-fa-updated" datetime="${attr(entry.modified || "")}">${esc(formatModified(entry.modified))}</time></td>
            <td data-label="${attr(__("Actions"))}" class="right"><div class="ol-fa-actions">
                <button type="button" class="ol-fa-action primary" data-fa-open="${attr(key)}" ${canOpen ? "" : "disabled"}>${icon(editable ? "edit" : "view")}<span>${esc(editable ? (annexName(entry) ? __("Edit") : __("Start")) : __("View"))}</span></button>
                ${entry.can_print ? `<button type="button" class="ol-fa-action icon" data-fa-print="${attr(key)}" ${annexName(entry) ? "" : "disabled"} aria-label="${attr(__("Print"))}" title="${attr(__("Print"))}">${icon("print")}</button>` : ""}
                ${entry.can_copy_to_execution ? `<button type="button" class="ol-fa-action" data-fa-copy="${attr(key)}" ${canCopy ? "" : "disabled"} title="${attr(canCopy ? __("Copy to execution") : __("No target execution revision is available."))}">${icon("copy")}<span>${esc(__("Copy to execution"))}</span></button>` : ""}
            </div></td>
        </tr>`;
    }

    function filteredEmptyMarkup(phase, selectedSource) {
        const message = selectedSource === "all"
            ? __("No annexes are available in this phase.")
            : __("No annexes are available for this source document.");
        return stateMarkup("empty compact", message, phase.label);
    }

    function bind(state) {
        state.root.find("[data-fa-refresh]").on("click", () => load(state));
        state.root.find("[data-fa-phase]").on("click", function () {
            state.activePhase = String(this.dataset.faPhase || "");
            render(state);
        }).on("keydown", function (event) {
            if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
            event.preventDefault();
            const tabs = state.root.find("[data-fa-phase]").get();
            const current = tabs.indexOf(this);
            let next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : current + (event.key === "ArrowRight" ? 1 : -1);
            next = (next + tabs.length) % tabs.length;
            tabs[next].focus();
            tabs[next].click();
            state.root.find(`[data-fa-phase="${cssEscape(tabs[next].dataset.faPhase || "")}"]`).trigger("focus");
        });
        state.root.find("[data-fa-source]").on("click", function () {
            state.sourceByPhase[state.activePhase] = String(this.dataset.faSource || "all");
            render(state);
        });
        state.root.find("[data-fa-source-select]").on("change", function () {
            state.sourceByPhase[state.activePhase] = String(this.value || "all");
            render(state);
        });
        state.root.find("[data-fa-open]").on("click", function () {
            const entry = findEntry(state, this.dataset.faOpen);
            if (entry) openEntry(state, entry);
        });
        state.root.find("[data-fa-print]").on("click", function () {
            const entry = findEntry(state, this.dataset.faPrint);
            if (entry) printEntry(entry);
        });
        state.root.find("[data-fa-copy]").on("click", function () {
            const entry = findEntry(state, this.dataset.faCopy);
            if (entry) copyToExecution(state, entry, this);
        });
    }

    function openEntry(state, entry) {
        if (typeof window.orderliftOpenAnnexDialog !== "function") {
            frappe.msgprint({ message: __("The annex viewer is not available."), indicator: "orange" });
            return;
        }
        const doctype = entry.source_doctype || state.frm.doctype;
        const name = entry.source_name || state.frm.doc.name;
        window.orderliftOpenAnnexDialog({
            doctype,
            doc: { name },
            is_new: () => false,
            annexName: annexName(entry),
            templateName: entry.template || "",
            onlyAnnex: Boolean(entry.template),
            readOnly: !entry.editable || Boolean(entry.read_only_reason),
            title: entry.template_name || __("Fiche annexe"),
            onChange: async () => {
                if (state.frm.doctype === "Sales Order Technical List Revision") {
                    await state.frm.reload_doc();
                    return;
                }
                await load(state);
            },
        });
    }

    function printEntry(entry) {
        const name = annexName(entry);
        if (!name) return;
        window.open(`/printview?doctype=Orderlift%20Annex%20Document&name=${encodeURIComponent(name)}&format=Orderlift%20Annex%20Document&no_letterhead=0`, "_blank", "noopener");
    }

    async function copyToExecution(state, entry, button) {
        const phase = state.payload.phases.find((row) => row.key === state.activePhase) || {};
        const revision = executionRevision(entry, phase, state.payload.capabilities, state.frm);
        const sourceAnnex = annexName(entry);
        if (!revision || !sourceAnnex) return;
        button.disabled = true;
        try {
            await frappe.call({
                method: COPY_METHOD,
                args: { revision, source_annex: sourceAnnex },
                freeze: true,
                freeze_message: __("Copying annex to execution..."),
            });
            frappe.show_alert({ message: __("Annex copied to execution"), indicator: "green" });
            await load(state);
        } catch (error) {
            button.disabled = false;
            console.error("Unable to copy annex to execution", error);
        }
    }

    function executionRevision(entry, phase, capabilities, frm) {
        if (frm.doctype === "Sales Order Technical List Revision") return frm.doc.name;
        return entry.execution_revision || phase.execution_revision || capabilities.execution_revision || capabilities.current_revision || capabilities.revision || "";
    }

    function findEntry(state, key) {
        const phase = state.payload.phases.find((row) => row.key === state.activePhase);
        return phase && phase.entries.find((entry) => entry._ui_key === String(key || ""));
    }

    function annexName(entry) {
        if (!entry) return "";
        if (typeof entry.annex === "string") return entry.annex;
        return (entry.annex && entry.annex.name) || entry.annex_name || "";
    }

    function validSource(phase, selected) {
        return selected === "all" || phase.sources.some((source) => source.key === selected) ? (selected || "all") : "all";
    }

    function sourceKey(doctype, name) {
        return doctype || name ? `${doctype || "Document"}::${name || ""}` : "";
    }

    function cssEscape(value) {
        if (window.CSS && CSS.escape) return CSS.escape(String(value));
        return String(value).replace(/"/g, '\\"');
    }

    function formatModified(value) {
        if (!value) return __("Not available");
        try {
            if (frappe.datetime && frappe.datetime.str_to_user) return frappe.datetime.str_to_user(value);
        } catch (error) {
            console.debug("Unable to format annex modified date", error);
        }
        return String(value);
    }

    function loadingMarkup() {
        return `<div class="ol-fa-state loading" role="status" aria-live="polite"><span class="ol-fa-spinner" aria-hidden="true"></span><div><strong>${esc(__("Loading annexes"))}</strong><small>${esc(__("Reading the document chain..."))}</small></div></div>`;
    }

    function errorMarkup() {
        return `<div class="ol-fa-state error" role="alert"><div><strong>${esc(__("Annexes could not be loaded"))}</strong><small>${esc(__("Check your connection or permissions, then try again."))}</small></div><button type="button" class="btn btn-default btn-xs" data-fa-retry>${esc(__("Retry"))}</button></div>`;
    }

    function stateMarkup(classes, message, title) {
        return `<div class="ol-fa-state ${attr(classes)}"><div><strong>${esc(title || __("Fiches annexes"))}</strong><small>${esc(message)}</small></div></div>`;
    }

    function domId(reference, key) {
        return `ol-fa-${String(reference + key).replace(/[^a-zA-Z0-9_-]/g, "-")}`;
    }

    function isNew(frm) {
        return typeof frm.is_new === "function" ? frm.is_new() : Boolean(frm.is_new);
    }

    function esc(value) { return frappe.utils.escape_html(value == null ? "" : String(value)); }
    function attr(value) { return esc(value).replace(/"/g, "&quot;"); }

    function icon(name) {
        const icons = {
            file: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6"/></svg>',
            refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 11a8 8 0 10-2.34 5.66"/><path d="M20 4v7h-7"/></svg>',
            edit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 013 3L8 18l-4 1 1-4z"/></svg>',
            view: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z"/><circle cx="12" cy="12" r="3"/></svg>',
            print: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9V2h12v7"/><path d="M6 18H4a2 2 0 01-2-2v-5a2 2 0 012-2h16a2 2 0 012 2v5a2 2 0 01-2 2h-2"/><path d="M6 14h12v8H6z"/></svg>',
            copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>',
        };
        return icons[name] || "";
    }

    window.orderliftAnnexWorkspace = {
        mount,
        reload(frm) { return mount(frm); },
    };
})();
