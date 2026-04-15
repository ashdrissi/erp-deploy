// ─── Pricing Simulator ────────────────────────────────────────────────────────
// UX/UI improvements:
//   • Collapsible compact filter panel (4-col grid) with localStorage persistence
//   • Clear all / Agent defaults / Run buttons in header
//   • Tab-style view switcher (Compare / Dynamic / Static)
//   • Auto-collapse filters after first run
//   • In-table search with highlighted match terms
//   • Sortable column headers
//   • Row count + last-run timestamp
//   • Color-coded margin badges (green/amber/red)
//   • Totals footer row
//   • CSV export button
//   • Animated spinner loading state
//   • Styled empty state when no results
//   • Keyboard shortcut: Enter = Run, Escape = toggle filters
// ──────────────────────────────────────────────────────────────────────────────

const LS_KEY = "psim_filters_v3";
const LS_OPEN = "psim_filters_open";

frappe.pages["pricing-simulator"].on_page_load = function () {
    frappe.set_route("List", "Pricing Simulator Workbench");
    return;
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Pricing Simulator"),
        single_column: true,
    });

    page.main.addClass("psim-root");
    injectStyles();

    const state = {
        page,
        enabledItemCount: 0,
        defaultsApplied: false,
        debounce: null,
        sortCol: null,
        sortDir: 1,
        lastRows: [],
        lastMode: null,
        lastSummary: null,
        viewMode: "Compare (Dynamic vs Static)",
        dynamicSources: [{ buying_price_list: "", pricing_scenario: "", customs_policy: "", benchmark_policy: "", is_active: 1 }],
        staticLists: [""],
        tableFilters: { material: "", source: "" },
    };

    buildLayout(state);
    restoreFilters(state);
    loadDefaults(state, false).then(() => runSimulation(state));

    $(document).on("keydown.psim", (e) => {
        if (e.key === "Enter" && !$(e.target).is("textarea, input")) runSimulation(state);
        if (e.key === "Escape") toggleFilters(state);
    });
    page.main.on("remove", () => $(document).off("keydown.psim"));
};

// ─── Layout ───────────────────────────────────────────────────────────────────

function buildLayout(state) {
    const { page } = state;
    const savedOpen = localStorage.getItem(LS_OPEN) !== "0";

    // ── Filter panel ──
    const controlsWrap = $(`
            <div class="psim-controls">
                <div class="psim-card-head psim-card-head--clickable" data-role="filter-toggle">
                    <div class="psim-title">
                        <svg class="psim-chevron ${savedOpen ? "psim-chevron--open" : ""}" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="4 6 8 10 12 6"/></svg>
                        <span>${__("Filters")}</span>
                        <span class="psim-filter-summary" data-role="filter-summary"></span>
                    </div>
                    <div class="psim-actions" onclick="event.stopPropagation()">
                        <span class="psim-kbd-hint">↵ ${__("Run")}  Esc ${__("Toggle")}</span>
                        <button class="psim-btn-ghost" data-action="clear">⊘ ${__("Clear")}</button>
                        <button class="btn btn-default btn-xs" data-action="load-defaults">${__("Agent Defaults")}</button>
                        <button class="btn btn-primary btn-xs psim-run-btn" data-action="refresh">▶ ${__("Run")}</button>
                    </div>
                </div>
                <div class="psim-collapse-body" style="${savedOpen ? "" : "display:none"}">
                    <div class="psim-grid"></div>
                    <div class="psim-source-grid">
                        <div class="psim-source-card" data-role="dynamic-sources"></div>
                        <div class="psim-source-card" data-role="static-sources"></div>
                    </div>
                    <div class="psim-hint" data-role="auto-hint"></div>
                </div>
            </div>
        `);

    // ── View tabs ──
    const tabs = $(`
            <div class="psim-tabs" data-role="tabs">
                <button class="psim-tab psim-tab--active" data-view="Compare (Dynamic vs Static)">${__("Compare")}</button>
                <button class="psim-tab" data-view="Dynamic only">${__("Dynamic")}</button>
                <button class="psim-tab" data-view="Static only">${__("Static")}</button>
            </div>
        `);

    // ── Results panel ──
    const outputWrap = $(`
            <div class="psim-card">
                <div class="psim-card-head">
                    <div class="psim-title">
                        ${__("Results")}
                        <span class="psim-row-count" data-role="row-count"></span>
                        <span class="psim-last-run" data-role="last-run"></span>
                    </div>
                    <div class="psim-actions">
                        <input type="search" class="psim-search" placeholder="🔍 ${__("Search items…")}" data-role="search">
                        <button class="psim-btn-ghost" data-action="export" title="${__("Export CSV")}">⬇ CSV</button>
                    </div>
                </div>
                <div class="psim-output psim-empty-state" data-role="output">
                    <div class="psim-empty-icon">📊</div>
                    <div class="psim-empty-text">${__("Configure filters and click Run to simulate pricing.")}</div>
                </div>
            </div>
        `);

    page.main.append(controlsWrap);
    page.main.append(tabs);
    page.main.append(outputWrap);

    state.autoHint = controlsWrap.find('[data-role="auto-hint"]');
    state.outputWrap = outputWrap.find('[data-role="output"]');
    state.rowCount = outputWrap.find('[data-role="row-count"]');
    state.lastRunEl = outputWrap.find('[data-role="last-run"]');
    state.filterSummary = controlsWrap.find('[data-role="filter-summary"]');
    state.searchInput = outputWrap.find('[data-role="search"]');
    state.tabsEl = tabs;

    // ── Build filter controls ──
    const grid = controlsWrap.find(".psim-grid");
    state.controls = {
        customer: makeControl(grid, { fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" }),
        geography_territory: makeControl(grid, { fieldname: "geography_territory", label: __("Territory"), fieldtype: "Link", options: "Territory" }),
        only_priced_items: makeControl(grid, { fieldname: "only_priced_items", label: __("Only Priced Items"), fieldtype: "Check", default: 1 }),
        max_items: makeControl(grid, { fieldname: "max_items", label: __("Max Items"), fieldtype: "Int", default: 100 }),
    };
    state.dynamicSourcesWrap = controlsWrap.find('[data-role="dynamic-sources"]');
    state.staticSourcesWrap = controlsWrap.find('[data-role="static-sources"]');
    renderSourceConfigurators(state);

    // ── Bindings ──
    controlsWrap.find('[data-role="filter-toggle"]').on("click", () => toggleFilters(state));
    controlsWrap.find('[data-action="load-defaults"]').on("click", () => loadDefaults(state, true));
    controlsWrap.find('[data-action="refresh"]').on("click", () => runSimulation(state));
    controlsWrap.find('[data-action="clear"]').on("click", () => clearFilters(state));

    outputWrap.find('[data-action="export"]').on("click", () => exportCsv(state));

    tabs.find(".psim-tab").on("click", function () {
        state.viewMode = $(this).data("view");
        tabs.find(".psim-tab").removeClass("psim-tab--active");
        $(this).addClass("psim-tab--active");
        runSimulation(state);
    });

    Object.values(state.controls).forEach((c) => {
        c.$input?.on("change", () => { persistFilters(state); queueRun(state); });
    });
    state.searchInput.on("input", () => filterTableRows(state));
}

function makeControl(parent, df) {
    const wrap = $(`<div class="psim-field"></div>`).appendTo(parent);
    const ctl = frappe.ui.form.make_control({ parent: wrap, df, render_input: true });
    ctl.refresh();
    if (df.default !== undefined) ctl.set_value(df.default);
    return ctl;
}

// ─── Filter panel helpers ──────────────────────────────────────────────────────

function toggleFilters(state) {
    const body = state.page.main.find(".psim-collapse-body");
    const chevron = state.page.main.find(".psim-chevron");
    const isOpen = body.is(":visible");
    body.slideToggle(180);
    chevron.toggleClass("psim-chevron--open", !isOpen);
    localStorage.setItem(LS_OPEN, isOpen ? "0" : "1");
}

function collapseFilters(state) {
    const body = state.page.main.find(".psim-collapse-body");
    const chevron = state.page.main.find(".psim-chevron");
    if (body.is(":visible")) {
        body.slideUp(180);
        chevron.removeClass("psim-chevron--open");
        localStorage.setItem(LS_OPEN, "0");
    }
}

// ─── Persistence ──────────────────────────────────────────────────────────────

function persistFilters(state) {
    const vals = {};
    Object.entries(state.controls).forEach(([k, c]) => { vals[k] = c.get_value(); });
    syncSourceStateFromDoc(state);
    vals.dynamic_sources = state.dynamicSources;
    vals.static_lists = state.staticLists;
    localStorage.setItem(LS_KEY, JSON.stringify(vals));
    updateFilterSummary(state, vals);
}

function restoreFilters(state) {
    try {
        const saved = JSON.parse(localStorage.getItem(LS_KEY) || "{}");
        Object.entries(saved).forEach(([k, v]) => {
            if (k === "dynamic_sources") state.dynamicSources = Array.isArray(v) ? v : [];
            else if (k === "static_lists") state.staticLists = Array.isArray(v) ? v : [];
            else if (state.controls[k] && v !== null && v !== undefined && v !== "")
                state.controls[k].set_value(v);
        });
        renderSourceConfigurators(state);
        updateFilterSummary(state, saved);
    } catch (_) { }
}

function clearFilters(state) {
    Object.values(state.controls).forEach((c) => c.set_value(""));
    ["max_items", "only_priced_items"].forEach((k) => {
        const df = state.controls[k]?.df;
        if (df?.default !== undefined) state.controls[k].set_value(df.default);
    });
    localStorage.removeItem(LS_KEY);
    state.dynamicSources = [];
    state.staticLists = [];
    renderSourceConfigurators(state);
    state.filterSummary.text("");
}

function updateFilterSummary(state, vals) {
    const active = Object.entries(vals).filter(([k, v]) => {
        if (!v && v !== 0) return false;
        const df = state.controls[k]?.df;
        return df?.default === undefined || String(v) !== String(df.default);
    }).length;
    state.filterSummary.text(active > 0 ? `${active} active` : "");
}

// ─── Defaults ─────────────────────────────────────────────────────────────────

async function loadDefaults(state, forceToast) {
    const resp = await frappe.call({
        method: "orderlift.orderlift_sales.page.pricing_simulator.pricing_simulator.get_simulation_defaults",
        args: { sales_person: "", mode: "Auto" },
    });
    const data = resp.message || {};

    if (data.dynamic) {
        if (!state.dynamicSources.length && data.dynamic.buying_price_list) {
            state.dynamicSources = [{
                buying_price_list: data.dynamic.buying_price_list || "",
                pricing_scenario: data.dynamic.pricing_scenario || "",
                customs_policy: data.dynamic.customs_policy || "",
                benchmark_policy: data.dynamic.benchmark_policy || "",
                is_active: 1,
            }];
        }
    }
    if (data.static && !state.staticLists.length)
        state.staticLists = (data.static.selling_price_lists || []).slice();

    state.enabledItemCount = Number(data.enabled_item_count || 0);
    renderAutoHint(state);
    renderSourceConfigurators(state);
    state.defaultsApplied = true;

    if (forceToast)
        frappe.show_alert({ message: __("Defaults loaded ({0})", [data.resolved_mode || "Auto"]), indicator: "green" });
}

// ─── Simulation ───────────────────────────────────────────────────────────────

function collectPayload(state) {
    return {
        customer: state.controls.customer.get_value() || "",
        sales_person: "",
        geography_territory: state.controls.geography_territory.get_value() || "",
        selling_price_lists: state.staticLists.slice(),
        sourcing_rules: state.dynamicSources.slice(),
        use_all_enabled_items: 1,
        item_group: "",
        item_search: "",
        material: "",
        default_qty: 1,
        max_items: state.controls.max_items.get_value() || 0,
        only_priced_items: Number(state.controls.only_priced_items.get_value() || 0),
        items: [],
    };
}

function renderSourceConfigurators(state) {
    syncSourceDoc(state);
    renderDynamicSourceGrid(state);
    renderStaticSourceGrid(state);
}

function syncSourceDoc(state) {
    state.simDoc = {
        doctype: "Pricing Simulator UI",
        name: "Pricing Simulator UI",
        dynamic_sources: (state.dynamicSources || []).map((row) => ({
            doctype: "Pricing Builder Sourcing Rule",
            buying_price_list: row.buying_price_list || row.source_buying_price_list || "",
            pricing_scenario: row.pricing_scenario || "",
            customs_policy: row.customs_policy || "",
            benchmark_policy: row.benchmark_policy || "",
            is_active: row.is_active ? 1 : 0,
        })),
        static_sources: (state.staticLists || []).map((value) => ({
            doctype: "Pricing Simulator Static Source",
            selling_price_list: value || "",
            is_active: 1,
        })),
    };
    state.simFrm = {
        doc: state.simDoc,
        docname: state.simDoc.name,
        fields_dict: {},
        script_manager: { trigger() {}, make() {} },
        cur_grid: null,
        get_field(fieldname) { return this.fields_dict[fieldname]; },
        refresh_field(fieldname) { this.fields_dict[fieldname]?.refresh?.(); },
    };
}

function syncSourceStateFromDoc(state) {
    if (!state.simDoc) return;
    state.dynamicSources = (state.simDoc.dynamic_sources || []).map((row) => ({
        buying_price_list: row.buying_price_list || row.source_buying_price_list || "",
        pricing_scenario: row.pricing_scenario || "",
        customs_policy: row.customs_policy || "",
        benchmark_policy: row.benchmark_policy || "",
        is_active: row.is_active ? 1 : 0,
    })).filter((row) => row.buying_price_list || row.pricing_scenario || row.customs_policy || row.benchmark_policy || row.is_active);
    state.staticLists = (state.simDoc.static_sources || []).map((row) => row.selling_price_list || "").filter(Boolean);
}

function renderDynamicSourceGrid(state) {
    const wrap = state.dynamicSourcesWrap;
    if (!wrap?.length) return;
    wrap.html(`
        <div class="psim-source-head">
            <div>
                <div class="psim-source-title">${__("Dynamic Sources")}</div>
                <div class="psim-source-help">${__("Map buying price lists to expenses, customs, and margin policies like the builder.")}</div>
            </div>
        </div>
        <div class="psim-native-grid" data-native-grid="dynamic"></div>
    `);
    mountNativeGrid(state, wrap.find('[data-native-grid="dynamic"]')[0], {
        fieldname: 'dynamic_sources',
        label: __('Dynamic Sources'),
        options: 'Pricing Builder Sourcing Rule'
    });
}

function renderStaticSourceGrid(state) {
    const wrap = state.staticSourcesWrap;
    if (!wrap?.length) return;
    wrap.html(`
        <div class="psim-source-head">
            <div>
                <div class="psim-source-title">${__("Static Selling Lists")}</div>
                <div class="psim-source-help">${__("Choose one or more selling lists to simulate static pricing with the same item filters.")}</div>
            </div>
        </div>
        <div class="psim-native-grid" data-native-grid="static"></div>
    `);
    mountNativeGrid(state, wrap.find('[data-native-grid="static"]')[0], {
        fieldname: 'static_sources',
        label: __('Static Selling Lists'),
        options: 'Pricing Simulator Static Source'
    });
}

function mountNativeGrid(state, parent, df) {
    if (!parent) return;
    const docfield = {
        fieldname: df.fieldname,
        fieldtype: 'Table',
        label: df.label,
        options: df.options,
        cannot_add_rows: false,
        in_place_edit: true,
    };
    frappe.model.with_doctype(df.options, () => {
        $(parent).empty();
        const grid = new frappe.ui.form.Grid({
            frm: state.simFrm,
            df: docfield,
            parent: $(parent),
        });
        grid.make();
        grid.refresh();
        state.simFrm.fields_dict[df.fieldname] = { grid, refresh: () => grid.refresh() };
        bindNativeGridChanges(state, grid);
    });
}

function bindNativeGridChanges(state, control) {
    const wrapper = $(control.wrapper || control.$wrapper || control.parent || []);
    if (!wrapper.length) return;
    wrapper.off('.psimgrid');
    wrapper.on('change.psimgrid input.psimgrid click.psimgrid', () => {
        setTimeout(() => {
            syncSourceStateFromDoc(state);
            persistFilters(state);
            queueRun(state);
        }, 0);
    });
}

function parseList(value) {
    return String(value || "").split(",").map((x) => x.trim()).filter(Boolean);
}

function queueRun(state) {
    if (state.debounce) clearTimeout(state.debounce);
    state.debounce = setTimeout(() => runSimulation(state), 400);
}

async function runSimulation(state) {
    persistFilters(state);
    const payload = collectPayload(state);
    const runDynamic = state.viewMode !== "Static only";
    const runStatic = state.viewMode !== "Dynamic only";

    state.outputWrap.removeClass("psim-empty-state").html(`
            <div class="psim-loading">
                <div class="psim-spinner"></div>
                <span>${__("Running simulation…")}</span>
            </div>
        `);
    state.rowCount.text("");
    state.lastRunEl.text("");

    try {
        const [dynamicResult, staticResult] = await Promise.all([
            runDynamic ? runSingleMode(payload, "Dynamic") : Promise.resolve(null),
            runStatic ? runSingleMode(payload, "Static") : Promise.resolve(null),
        ]);

        if (dynamicResult && staticResult) {
            renderComparison(state, dynamicResult, staticResult);
        } else {
            renderResults(state, dynamicResult || staticResult || {});
        }

        // Timestamp
        const now = frappe.datetime.now_time();
        state.lastRunEl.text(`${__("Last run")}: ${now}`);

        // Auto-collapse filters
        collapseFilters(state);
    } catch (e) {
        state.outputWrap.html(`<div class="psim-error">⚠ ${__("Simulation failed. Check parameters and try again.")}</div>`);
        throw e;
    }
}

async function runSingleMode(payload, mode) {
    const resp = await frappe.call({
        method: "orderlift.orderlift_sales.page.pricing_simulator.pricing_simulator.run_pricing_simulation",
        args: { payload: { ...payload, mode } },
    });
    return resp.message || {};
}

// ─── Rendering ────────────────────────────────────────────────────────────────

function renderAutoHint(state) {
    const count = Number(state.enabledItemCount || 0);
    const text = count > 0
        ? __("Auto-simulating {0} enabled item(s).", [count])
        : __("All enabled items will be auto-loaded at runtime.");
    state.autoHint.html(`<div class="psim-auto-hint">${frappe.utils.escape_html(text)}</div>`);
}

function metricCard(label, value, accent) {
    return `<div class="psim-metric psim-metric--${accent || "blue"}">
            <div class="psim-metric-label">${label}</div>
            <div class="psim-metric-value">${value}</div>
        </div>`;
}

function marginBadge(pct) {
    const v = Number(pct || 0);
    const cls = v >= 20 ? "psim-mgn-good" : v >= 10 ? "psim-mgn-mid" : "psim-mgn-bad";
    return `<span class="${cls}">${v.toFixed(1)}%</span>`;
}

function highlight(text, q) {
    if (!q) return frappe.utils.escape_html(text);
    const escaped = frappe.utils.escape_html(text);
    const regex = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
    return escaped.replace(regex, `<mark class="psim-hl">$1</mark>`);
}

// ── Comparison ──
function renderComparison(state, dynamicData, staticData) {
    const dynRows = Object.fromEntries((dynamicData.rows || []).map((r) => [r.item, r]));
    const staRows = Object.fromEntries((staticData.rows || []).map((r) => [r.item, r]));
    let keys = [...new Set([
        ...(dynamicData.rows || []).map((x) => x.item),
        ...(staticData.rows || []).map((x) => x.item),
    ])];

    if (Number(state.controls.only_priced_items.get_value() || 0) === 1) {
        keys = keys.filter((item) => {
            const d = dynRows[item] || {};
            const s = staRows[item] || {};
            return Number(d.buy_price || 0) > 0 || Number(s.selected_price || 0) > 0;
        });
    }

    state.lastRows = keys.map((item) => {
        const d = dynRows[item] || {};
        const s = staRows[item] || {};
        return { item, d, s, dynFinal: Number(d.final_sell_unit_price || 0), staPrice: Number(s.selected_price || 0) };
    });
    state.lastMode = "comparison";
    state.lastSummary = { dynamic: dynamicData.summary || {}, static: staticData.summary || {} };

    const warnings = [
        ...(dynamicData.warnings || []).map((w) => `[Dynamic] ${w}`),
        ...(staticData.warnings || []).map((w) => `[Static] ${w}`),
    ];

    state.outputWrap.html(`
            <div class="psim-metrics">
                ${metricCard(__("Compared Items"), state.lastRows.length || 0, "blue")}
                ${metricCard(__("Average Dynamic Profit Margin"), `${Number(dynamicData.summary?.global_margin_pct || 0).toFixed(1)}%`, "green")}
                ${metricCard(__("Missing Static Prices"), staticData.summary?.missing_items || 0, "amber")}
            </div>
            ${renderWarnings(warnings)}
            ${renderResultFilters(state, state.lastRows, "comparison")}
            <div class="psim-table-wrap">
                <table class="psim-table">
                    <thead>
                        <tr>
                            ${thSort("item", __("Item"))}
                            ${thSort("material", __("Material"))}
                            ${thSort("source", __("Buying List"))}
                            ${thSort("scenario", __("Expenses Policy"))}
                            ${thSort("buy", __("Dynamic Buy Price"))}
                            ${thSort("customs", __("Dynamic Customs"))}
                            ${thSort("customsValue", __("Customs Value"))}
                            ${thSort("tier", __("Tier Modifier"))}
                            ${thSort("territory", __("Territory Modifier"))}
                            ${thSort("dynFinal", __("Dynamic Sell Price"))}
                            ${thSort("staticList", __("Sell List"))}
                            ${thSort("staPrice", __("Static Sell Price"))}
                        </tr>
                    </thead>
                    <tbody id="psim-tbody"></tbody>
                    <tfoot id="psim-tfoot"></tfoot>
                </table>
            </div>
        `);

    bindSortHeaders(state);
    renderComparisonRows(state);
}

function renderComparisonRows(state) {
    const q = (state.searchInput.val() || "").toLowerCase().trim();
    let rows = state.lastRows.slice();
    if (q) rows = rows.filter((r) => r.item.toLowerCase().includes(q));
    rows = applyResultFilters(state, rows);

    if (state.sortCol) {
        rows.sort((a, b) => {
            const va = compSortVal(a, state.sortCol);
            const vb = compSortVal(b, state.sortCol);
            return state.sortDir * (va < vb ? -1 : va > vb ? 1 : 0);
        });
    }

    const tbody = state.outputWrap.find("#psim-tbody");
    const tfoot = state.outputWrap.find("#psim-tfoot");

    if (!rows.length) {
        tbody.html(`<tr><td colspan="12" class="psim-muted">${emptyRow()}</td></tr>`);
        tfoot.html("");
        state.rowCount.text("");
        return;
    }

    tbody.html(rows.map(({ item, d, s, dynFinal, staPrice }) => {
        return `<tr>
                <td>${docLink("Item", item, item, q)}</td>
                <td>${frappe.utils.escape_html(d.material || s.material || "—")}</td>
                <td>${frappe.utils.escape_html(d.source_buying_price_list || "—")}</td>
                <td><span class="psim-pill">${frappe.utils.escape_html(d.resolved_pricing_scenario || "—")}</span></td>
                <td>${frappe.format(d.buy_price || 0, { fieldtype: "Currency" })}</td>
                <td>${frappe.format(d.customs_applied || 0, { fieldtype: "Currency" })}</td>
                <td>${frappe.format(d.customs_base_value || 0, { fieldtype: "Currency" })}</td>
                <td>${frappe.format(d.tier_modifier_amount || 0, { fieldtype: "Currency" })}</td>
                <td>${frappe.format(d.zone_modifier_amount || 0, { fieldtype: "Currency" })}</td>
                <td><strong>${frappe.format(dynFinal, { fieldtype: "Currency" })}</strong></td>
                <td>${frappe.utils.escape_html(s.selected_price_list || "—")}</td>
                <td>${frappe.format(staPrice, { fieldtype: "Currency" })}</td>
            </tr>`;
    }).join(""));

    const avgMargin = rows.length
        ? rows.reduce((s, r) => s + Number(r.d?.margin_pct || 0), 0) / rows.length
        : 0;
    tfoot.html(`<tr class="psim-tfoot-row">
            <td><strong>${__("Totals")}</strong></td>
            <td colspan="9"></td>
            <td>${marginBadge(avgMargin)}</td>
            <td></td>
        </tr>`);

    state.rowCount.text(`${rows.length} ${__("items")}`);
}

// ── Single mode ──
function renderResults(state, data) {
    const mode = data.pricing_mode || data.mode || "Dynamic";
    const rows = data.rows || [];
    const summary = data.summary || {};
    const warnings = data.warnings || [];

    state.lastRows = rows;
    state.lastMode = mode;
    state.lastSummary = summary;

    const cards = mode === "Static"
        ? `${metricCard(__("Priced Items"), summary.priced_items || 0, "green")}
            ${metricCard(__("Missing Prices"), summary.missing_items || 0, "amber")}
            ${metricCard(__("Sell Lists"), (summary.selling_lists_count || 0), "blue")}`
        : `${metricCard(__("Simulated Items"), rows.length || 0, "indigo")}
            ${metricCard(__("Policies"), summary.policy_count || 0, "amber")}
            ${metricCard(__("Average Profit Margin"), `${Number(summary.global_margin_pct || 0).toFixed(1)}%`, "green")}`;

    const thead = mode === "Static"
        ? `<tr>${thSort("item", __("Item"))}${thSort("material", __("Material"))}${thSort("selected_price_list", __("Sell List"))}${thSort("selected_price", __("Sell Price"))}${thSort("option_count", __("Options"))}</tr>`
        : `<tr>${thSort("item", __("Item"))}${thSort("material", __("Material"))}${thSort("source_buying_price_list", __("Buying List"))}${thSort("resolved_pricing_scenario", __("Expenses Policy"))}${thSort("buy_price", __("Buy Price"))}${thSort("customs_applied", __("Customs"))}${thSort("customs_base_value", __("Customs Value"))}${thSort("tier_modifier_amount", __("Tier Modifier"))}${thSort("zone_modifier_amount", __("Territory Modifier"))}${thSort("benchmark_reference", __("Benchmark Price"))}${thSort("final_sell_unit_price", __("Sell Price"))}${thSort("margin_pct", __("Profit Margin %"))}${thSort("applied_benchmark_policy", __("Profit Margin Policy"))}</tr>`;

    state.outputWrap.html(`
            <div class="psim-metrics">${cards}</div>
            ${renderWarnings(warnings)}
            ${renderResultFilters(state, rows, mode)}
            <div class="psim-table-wrap">
                <table class="psim-table">
                    <thead>${thead}</thead>
                    <tbody id="psim-tbody"></tbody>
                    <tfoot id="psim-tfoot"></tfoot>
                </table>
            </div>
        `);

    bindSortHeaders(state);
    renderSingleRows(state);
}

function renderSingleRows(state) {
    const q = (state.searchInput.val() || "").toLowerCase().trim();
    let rows = state.lastRows.slice();
    if (q) rows = rows.filter((r) => (r.item || "").toLowerCase().includes(q));
    rows = applyResultFilters(state, rows);

    if (state.sortCol) {
        rows.sort((a, b) => {
            const va = a[state.sortCol] ?? "";
            const vb = b[state.sortCol] ?? "";
            return state.sortDir * (va < vb ? -1 : va > vb ? 1 : 0);
        });
    }

    const tbody = state.outputWrap.find("#psim-tbody");
    const tfoot = state.outputWrap.find("#psim-tfoot");
    const mode = state.lastMode;

    if (!rows.length) {
        const colspan = mode === "Static" ? 5 : 13;
        tbody.html(`<tr><td colspan="${colspan}" class="psim-muted">${emptyRow(__("No items match your search."))}</td></tr>`);
        tfoot.html("");
        state.rowCount.text("");
        return;
    }

    tbody.html(rows.map((row) => mode === "Static" ? staticRow(row, q) : dynamicRow(row, q)).join(""));

    if (mode !== "Static") {
         const avgMargin = rows.length ? rows.reduce((s, r) => s + Number(r.margin_pct || 0), 0) / rows.length : 0;
         tfoot.html(`<tr class="psim-tfoot-row">
                <td><strong>${__("Average")}</strong></td>
                <td colspan="10"></td>
                <td>${marginBadge(avgMargin)}</td>
                <td></td>
            </tr>`);
    } else {
        tfoot.html("");
    }

    state.rowCount.text(`${rows.length} ${__("items")}`);
}

function filterTableRows(state) {
    if (state.lastMode === "comparison") renderComparisonRows(state);
    else if (state.lastMode) renderSingleRows(state);
}

function renderResultFilters(state, rows, mode) {
    const materials = [...new Set((rows || []).map((r) => r.material || r.d?.material || r.s?.material).filter(Boolean))].sort();
    const sources = mode === "Static"
        ? [...new Set((rows || []).map((r) => r.selected_price_list).filter(Boolean))].sort()
        : mode === "comparison"
            ? [...new Set((rows || []).map((r) => r.d?.source_buying_price_list || r.s?.selected_price_list).filter(Boolean))].sort()
            : [...new Set((rows || []).map((r) => r.source_buying_price_list || r.applied_benchmark_policy).filter(Boolean))].sort();
    const current = state.tableFilters || { material: "", source: "" };
    setTimeout(() => bindResultFilters(state), 0);
    return `
        <div class="psim-result-filters">
            <div class="psim-result-filter-copy">${__("Table Filters")}</div>
            <div class="psim-result-filter-controls">
                <select class="form-control" data-result-filter="material">
                    <option value="">${__("All Materials")}</option>
                    ${materials.map((value) => `<option value="${frappe.utils.escape_html(value)}" ${current.material === value ? "selected" : ""}>${frappe.utils.escape_html(value)}</option>`).join("")}
                </select>
                <select class="form-control" data-result-filter="source">
                    <option value="">${mode === "Static" ? __("All Selling Lists") : __("All Sources")}</option>
                    ${sources.map((value) => `<option value="${frappe.utils.escape_html(value)}" ${current.source === value ? "selected" : ""}>${frappe.utils.escape_html(value)}</option>`).join("")}
                </select>
                <button class="btn btn-default btn-sm" data-clear-result-filters>${__("Clear")}</button>
            </div>
        </div>
    `;
}

function bindResultFilters(state) {
    state.outputWrap.find('[data-result-filter]').off('change').on('change', function () {
        state.tableFilters[$(this).data('resultFilter')] = $(this).val() || "";
        filterTableRows(state);
    });
    state.outputWrap.find('[data-clear-result-filters]').off('click').on('click', function () {
        state.tableFilters = { material: "", source: "" };
        filterTableRows(state);
    });
}

function applyResultFilters(state, rows) {
    const material = (state.tableFilters?.material || "").toLowerCase();
    const source = (state.tableFilters?.source || "").toLowerCase();
    return (rows || []).filter((row) => {
        const rowMaterial = (row.material || row.d?.material || row.s?.material || "").toLowerCase();
        const rowSource = (row.source_buying_price_list || row.selected_price_list || row.applied_benchmark_policy || row.d?.source_buying_price_list || row.s?.selected_price_list || "").toLowerCase();
        return (!material || rowMaterial === material) && (!source || rowSource === source);
    });
}

// ── Sort helpers ──
function thSort(col, label) {
    return `<th data-col="${col}" class="psim-th-sort">${label}<span class="psim-sort-icon" data-col="${col}"></span></th>`;
}

function bindSortHeaders(state) {
    state.outputWrap.find(".psim-th-sort").on("click", function () {
        const col = $(this).data("col");
        state.sortDir = state.sortCol === col ? state.sortDir * -1 : 1;
        state.sortCol = col;
        state.outputWrap.find(".psim-sort-icon").html("");
        $(this).find(".psim-sort-icon").html(state.sortDir === 1 ? " ↑" : " ↓");
        filterTableRows(state);
    });
}

function compSortVal(row, col) {
    const m = {
        item: row.item,
        material: row.d?.material || row.s?.material || "",
        source: row.d?.source_buying_price_list || "",
        dynFinal: row.dynFinal, staPrice: row.staPrice,
        margin: Number(row.d?.margin_pct || 0),
        scenario: row.d?.resolved_pricing_scenario || "",
        buy: Number(row.d?.buy_price || 0),
        customs: Number(row.d?.customs_applied || 0),
        customsValue: Number(row.d?.customs_base_value || 0),
        tier: Number(row.d?.tier_modifier_amount || 0),
        territory: Number(row.d?.zone_modifier_amount || 0),
        staticList: row.s?.selected_price_list || "",
    };
    return m[col] ?? "";
}

// ── Row renderers ──

function docLink(doctype, name, display, q) {
    if (!name) return display ? frappe.utils.escape_html(display) : "—";
    const label = display || name;
    const highlighted = q ? highlight(label, q) : frappe.utils.escape_html(label);
    const url = `/app/${frappe.router.slug(doctype)}/${encodeURIComponent(name)}`;
    return `<a href="${url}" class="psim-link" title="Open ${frappe.utils.escape_html(name)}" target="_blank">${highlighted}</a>`;
}

function dynamicRow(row, q) {
    const policy = row.applied_benchmark_policy || "";
    const rule = row.resolved_benchmark_rule || "";
    const ruleTitle = rule ? ` title="Rule: ${frappe.utils.escape_html(rule)}"` : "";
    return `<tr>
            <td>${docLink("Item", row.item || "", row.item, q)}</td>
            <td>${frappe.utils.escape_html(row.material || "—")}</td>
            <td>${frappe.utils.escape_html(row.source_buying_price_list || "—")}</td>
            <td>${docLink("Pricing Scenario", row.resolved_pricing_scenario, row.resolved_pricing_scenario, null)}</td>
            <td>${frappe.format(row.buy_price || 0, { fieldtype: "Currency" })}</td>
            <td>${frappe.format(row.customs_applied || 0, { fieldtype: "Currency" })}</td>
            <td>${frappe.format(row.customs_base_value || 0, { fieldtype: "Currency" })}</td>
            <td>${frappe.format(row.tier_modifier_amount || 0, { fieldtype: "Currency" })}</td>
            <td>${frappe.format(row.zone_modifier_amount || 0, { fieldtype: "Currency" })}</td>
            <td>${row.benchmark_reference ? frappe.format(row.benchmark_reference, { fieldtype: "Currency" }) : "—"}</td>
            <td><strong>${frappe.format(row.final_sell_unit_price || 0, { fieldtype: "Currency" })}</strong></td>
            <td>${marginBadge(row.margin_pct)}</td>
            <td${ruleTitle}>${docLink("Pricing Benchmark Policy", policy, policy, null)}</td>
        </tr>`;
}

function staticRow(row, q) {
    return `<tr>
            <td>${docLink("Item", row.item || "", row.item, q)}</td>
            <td>${frappe.utils.escape_html(row.material || "—")}</td>
            <td>${row.selected_price_list
            ? `<a href="/app/item-price?price_list=${encodeURIComponent(row.selected_price_list)}" class="psim-link" target="_blank" title="View Item Prices for ${frappe.utils.escape_html(row.selected_price_list)}">${frappe.utils.escape_html(row.selected_price_list)}</a>`
            : "—"}</td>
            <td>${frappe.format(row.selected_price || 0, { fieldtype: "Currency" })}</td>
            <td>${row.option_count || 0}</td>
        </tr>`;
}

// ── Warnings / empty ──
function renderWarnings(warnings) {
    if (!warnings || !warnings.length)
        return `<div class="psim-clean">✓ ${__("No warnings")}</div>`;

    // Patterns to classify
    const INFO_RE = /auto-loaded|filtered out/i;
    const BENCH_RE = /Only\s+\d+ benchmark source\(s\) for (.+?);/i;

    const infoLines = [];
    const configLines = [];
    const benchItems = { Dynamic: [], Static: [] };

    for (const raw of warnings) {
        const modeMatch = raw.match(/^\[(Dynamic|Static)\]\s*/i);
        const mode = modeMatch ? modeMatch[1] : "Dynamic";
        const msg = raw.replace(/^\[(Dynamic|Static)\]\s*/i, "").trim();

        const benchMatch = msg.match(BENCH_RE);
        if (benchMatch) {
            (benchItems[mode] = benchItems[mode] || []).push(benchMatch[1]);
            continue;
        }
        if (INFO_RE.test(msg)) {
            infoLines.push(msg);
        } else {
            configLines.push(msg);
        }
    }

    // Aggregate per-item benchmark noise into one line
    for (const [mode, items] of Object.entries(benchItems)) {
        if (items.length) {
            configLines.push(
                `${items.length} ${mode} item(s) have no benchmark sources — comparison disabled (${items.join(", ")})`
            );
        }
    }

    let html = "";

    // Info row — subtle single line, no orange
    if (infoLines.length) {
        html += `<div class="psim-info-row">ℹ ${infoLines.map((l) => frappe.utils.escape_html(l)).join(" · ")}</div>`;
    }

    // Config warnings — collapsed by default
    if (configLines.length) {
        const rows = configLines.map((w) => `<div>• ${frappe.utils.escape_html(w)}</div>`).join("");
        html += `<details class="psim-warn-block">
            <summary class="psim-warn-summary">⚠ ${configLines.length} ${__("warning(s)")}</summary>
            <div class="psim-warn-body">${rows}</div>
        </details>`;
    }

    return html || `<div class="psim-clean">✓ ${__("No warnings")}</div>`;
}

function emptyRow(msg) {
    return `<div class="psim-empty-inner">
            <div class="psim-empty-icon">🔍</div>
            <div class="psim-empty-text">${msg || __("No rows")}</div>
        </div>`;
}

// ─── CSV Export ───────────────────────────────────────────────────────────────

function exportCsv(state) {
    if (!state.lastRows || !state.lastRows.length) {
        frappe.show_alert({ message: __("No data to export."), indicator: "orange" });
        return;
    }

    let headers, rowsFn;

    if (state.lastMode === "comparison") {
        headers = ["Item", "Qty", "Expenses Policy", "Dynamic Buy Price", "Dynamic Sell Price", "Dynamic Profit Margin %", "Static Sell Price", "Delta", "Winner"];
        rowsFn = (r) => [
            r.item,
            r.d?.qty || r.s?.qty || 0,
            r.d?.resolved_pricing_scenario || "",
            r.d?.buy_price || 0,
            r.dynFinal,
            Number(r.d?.margin_pct || 0).toFixed(2),
            r.staPrice,
            (r.dynFinal - r.staPrice).toFixed(2),
            r.dynFinal >= r.staPrice ? "Dynamic" : "Static",
        ];
    } else if (state.lastMode === "Static") {
        headers = ["Item", "Material", "Sell List", "Sell Price", "Options"];
        rowsFn = (r) => [r.item, r.material || "", r.selected_price_list, r.selected_price, r.option_count];
    } else {
        headers = ["Item", "Material", "Buying List", "Expenses Policy", "Buy Price", "Customs", "Customs Value", "Tier Modifier", "Territory Modifier", "Benchmark Price", "Sell Price", "Profit Margin %", "Profit Margin Policy"];
        rowsFn = (r) => [
            r.item, r.material || "", r.source_buying_price_list || "",
            r.resolved_pricing_scenario,
            r.buy_price, r.customs_applied, r.customs_base_value, r.tier_modifier_amount, r.zone_modifier_amount, r.benchmark_reference,
            r.final_sell_unit_price,
            Number(r.margin_pct || 0).toFixed(2),
            r.applied_benchmark_policy || "",
        ];
    }

    const csv = [headers, ...state.lastRows.map(rowsFn)]
        .map((row) => row.map((v) => `"${String(v ?? "").replace(/"/g, '""')}"`).join(","))
        .join("\n");

    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `pricing_simulation_${frappe.datetime.now_date()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
}

// ─── Styles ───────────────────────────────────────────────────────────────────

function injectStyles() {
    if (document.getElementById("pricing-simulator-style")) return;
    const style = document.createElement("style");
    style.id = "pricing-simulator-style";
    style.textContent = `
        .psim-root { padding: 0 !important; }

        /* Page wrapper — gives the whole page some breathing room */
        .psim-root .page-content,
        .psim-root .page-body { padding: 0 !important; }

        /* Cards */
        .psim-controls, .psim-card {
            max-width: 1320px;
            margin: 14px auto;
            background: #fff;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 14px 20px;
            box-shadow: 0 1px 4px rgba(15,23,42,.07);
        }
        .psim-controls { margin-bottom: 0; border-bottom-left-radius: 0; border-bottom-right-radius: 0; border-bottom: none; }
        .psim-card     { margin-top: 0; border-top-left-radius: 0; border-top-right-radius: 0; }

        /* Tab strip — visually bridges controls ↔ results */
        .psim-tabs {
            max-width: 1320px;
            margin: 0 auto;
            display: flex;
            gap: 4px;
            padding: 8px 20px;
            background: #f8fafc;
            border-left: 1px solid #e2e8f0;
            border-right: 1px solid #e2e8f0;
        }
        .psim-tab {
            padding: 5px 18px; border-radius: 20px; border: none;
            font-size: 12px; font-weight: 600; cursor: pointer;
            background: transparent; color: #64748b;
            transition: background .15s, color .15s;
        }
        .psim-tab:hover   { background: #e2e8f0; color: #334155; }
        .psim-tab--active { background: #6366f1; color: #fff !important; }


            /* Card head */
            .psim-card-head { display: flex; justify-content: space-between; align-items: center; min-height: 32px; }
            .psim-card-head--clickable {
                cursor: pointer; user-select: none; border-radius: 8px;
                padding: 4px 6px; margin: -4px -6px;
                transition: background .15s;
            }
            .psim-card-head--clickable:hover { background: #f8fafc; }

            .psim-title { font-weight: 700; font-size: 13px; color: #0f172a; display: flex; align-items: center; gap: 6px; }

            .psim-filter-summary {
                font-size: 11px; font-weight: 600; color: #6366f1;
                background: #eef2ff; padding: 1px 7px; border-radius: 10px;
            }

            /* Chevron */
            .psim-chevron { width: 14px; height: 14px; color: #94a3b8; flex-shrink: 0; transition: transform .2s; }
            .psim-chevron--open { transform: rotate(180deg); }

            /* Actions */
            .psim-actions { display: flex; gap: 6px; align-items: center; }
            .psim-btn-ghost {
                border: none; background: none; cursor: pointer;
                font-size: 11px; color: #64748b; padding: 3px 8px;
                border-radius: 6px; font-weight: 600;
                transition: background .15s, color .15s;
            }
            .psim-btn-ghost:hover { background: #f1f5f9; color: #334155; }
            .psim-run-btn { min-width: 60px; }
            .psim-kbd-hint { font-size: 10px; color: #94a3b8; white-space: nowrap; }

            /* Filter grid — 4 columns compact */
            .psim-collapse-body { margin-top: 10px; }
            .psim-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px 12px; }
            .psim-source-grid { display:grid; grid-template-columns:1.35fr 1fr; gap:12px; margin-top:12px; }
            .psim-source-card { border:1px solid #e2e8f0; border-radius:10px; padding:12px; background:#f8fafc; }
            .psim-source-head { display:flex; justify-content:space-between; gap:10px; align-items:flex-start; margin-bottom:10px; }
            .psim-source-title { font-size:12px; font-weight:800; color:#0f172a; text-transform:uppercase; letter-spacing:.05em; }
            .psim-source-help { font-size:11px; color:#64748b; margin-top:4px; }
            .psim-source-list { display:grid; gap:8px; }
            .psim-source-table-wrap { border:1px solid #e2e8f0; border-radius:10px; overflow:auto; background:#fff; }
            .psim-source-table { width:100%; border-collapse:collapse; font-size:12px; }
            .psim-source-table th, .psim-source-table td { border-bottom:1px solid #f1f5f9; padding:8px; vertical-align:top; }
            .psim-source-table th { background:#f8fafc; color:#64748b; text-transform:uppercase; letter-spacing:.05em; font-size:10px; }
            .psim-source-cell .form-group { margin-bottom:0; }
            .psim-static-cell .form-group { margin-bottom:0; }
            .psim-source-empty { color:#94a3b8; font-size:12px; padding:10px; border:1px dashed #cbd5e1; border-radius:8px; background:#fff; }
            .psim-source-check { margin:0; white-space:nowrap; font-size:11px; color:#475569; }
            .psim-static-add { margin-bottom:10px; }
            .psim-result-filters { display:flex; justify-content:space-between; gap:10px; align-items:center; padding:10px 12px; margin:0 0 10px; border:1px solid #e2e8f0; border-radius:10px; background:#f8fafc; }
            .psim-result-filter-copy { font-size:11px; text-transform:uppercase; letter-spacing:.05em; color:#64748b; font-weight:700; }
            .psim-result-filter-controls { display:grid; grid-template-columns:minmax(170px,.8fr) minmax(170px,.8fr) auto; gap:8px; align-items:center; }
            .psim-field .control-label { font-size: 11px !important; margin-bottom: 2px !important; color: #475569; }
            .psim-field .form-control   { height: 28px !important; font-size: 12px !important; padding: 2px 8px !important; }
            .psim-field .link-btn       { line-height: 28px !important; }
            .psim-field .like-disabled-input { height: 28px !important; line-height: 28px !important; font-size: 12px !important; }

            /* Auto hint */
            .psim-hint { margin-top: 8px; }
            .psim-auto-hint {
                background: #eef2ff; color: #3730a3;
                border: 1px solid #c7d2fe; border-radius: 6px;
                padding: 5px 10px; font-size: 11px; font-weight: 600;
            }

            /* Results header */
            .psim-row-count { font-size: 11px; font-weight: 400; color: #94a3b8; }
            .psim-last-run  { font-size: 10px; color: #cbd5e1; margin-left: 4px; }
            .psim-search {
                height: 28px !important; font-size: 12px !important;
                padding: 2px 12px !important; width: 200px !important;
                border-radius: 20px !important; border: 1px solid #e2e8f0 !important;
                outline: none !important;
            }
            .psim-search:focus { border-color: #6366f1 !important; box-shadow: 0 0 0 2px #eef2ff !important; }

            /* Loading */
            .psim-loading { display: flex; align-items: center; gap: 10px; padding: 24px; color: #64748b; font-size: 13px; }
            .psim-spinner {
                width: 20px; height: 20px;
                border: 2px solid #e2e8f0;
                border-top-color: #6366f1;
                border-radius: 50%;
                animation: psim-spin .7s linear infinite;
            }
            @keyframes psim-spin { to { transform: rotate(360deg); } }
            .psim-error { color: #991b1b; font-weight: 600; padding: 16px; }

            /* Empty state */
            .psim-empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100px; }
            .psim-empty-icon  { font-size: 32px; opacity: .4; }
            .psim-empty-text  { color: #94a3b8; font-size: 13px; margin-top: 6px; text-align: center; }
            .psim-empty-inner { text-align: center; padding: 16px; }

            /* KPI metrics */
            .psim-metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 8px; margin-bottom: 10px; }
            .psim-metric { border-radius: 10px; padding: 10px 14px; border-left: 3px solid; }
            .psim-metric--blue   { background: #eff6ff; border-color: #3b82f6; color: #1d4ed8; }
            .psim-metric--green  { background: #f0fdf4; border-color: #22c55e; color: #166534; }
            .psim-metric--amber  { background: #fffbeb; border-color: #f59e0b; color: #92400e; }
            .psim-metric--indigo { background: #eef2ff; border-color: #6366f1; color: #4338ca; }
            .psim-metric-label   { font-size: 11px; opacity: .7; }
            .psim-metric-value   { font-weight: 800; font-size: 17px; margin-top: 2px; }

            /* Warnings */
        .psim-info-row {
            font-size: 11px; color: #64748b;
            padding: 5px 0; margin-bottom: 6px;
            border-bottom: 1px dashed #e2e8f0;
        }
        .psim-warn-block {
            border: 1px solid #fed7aa; border-radius: 8px;
            background: #fff7ed; margin-bottom: 10px;
            overflow: hidden;
        }
        .psim-warn-summary {
            cursor: pointer; padding: 7px 12px;
            font-size: 12px; font-weight: 700;
            color: #9a3412; list-style: none;
            display: flex; align-items: center; gap: 6px;
        }
        .psim-warn-summary::-webkit-details-marker { display: none; }
        .psim-warn-body {
            padding: 8px 12px; font-size: 11px;
            color: #9a3412; border-top: 1px solid #fed7aa;
            line-height: 1.7;
        }
        .psim-warn-more { margin-top: 6px; }
        .psim-warn-more summary { cursor: pointer; font-weight: 700; }
        .psim-clean { background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; border-radius: 8px; padding: 7px 12px; margin-bottom: 10px; font-size: 12px; }

            /* Links */
        .psim-link { color: #4f46e5; text-decoration: none; font-weight: 600; }
        .psim-link:hover { text-decoration: underline; color: #3730a3; }

        /* Table */
        .psim-table-wrap { overflow-x: auto; }
            .psim-table { width: 100%; border-collapse: collapse; font-size: 12px; }
            .psim-table th, .psim-table td { border-bottom: 1px solid #f1f5f9; padding: 6px 8px; white-space: nowrap; }
            .psim-table th { text-transform: uppercase; font-size: 10px; color: #94a3b8; letter-spacing: .05em; background: #f8fafc; position: sticky; top: 0; z-index: 1; }
            .psim-table tbody tr:hover { background: #fafbfc; }
            .psim-th-sort { cursor: pointer; }
            .psim-th-sort:hover { color: #475569 !important; background: #f1f5f9; }
            .psim-sort-icon { color: #6366f1; font-style: normal; }
            .psim-tfoot-row td { border-top: 2px solid #e2e8f0; border-bottom: none; font-weight: 700; background: #f8fafc; }

            /* Badges / pills */
            .psim-mgn-good { background: #dcfce7; color: #166534; border-radius: 4px; padding: 1px 6px; font-weight: 700; font-size: 11px; }
            .psim-mgn-mid  { background: #fef3c7; color: #92400e; border-radius: 4px; padding: 1px 6px; font-weight: 700; font-size: 11px; }
            .psim-mgn-bad  { background: #fee2e2; color: #991b1b; border-radius: 4px; padding: 1px 6px; font-weight: 700; font-size: 11px; }
            .psim-pill { background: #f1f5f9; color: #475569; border-radius: 4px; padding: 1px 6px; font-size: 11px; }
            .psim-src  { background: #f8fafc; color: #64748b; border-radius: 4px; padding: 1px 6px; font-size: 11px; border: 1px solid #e2e8f0; }
            .psim-winner { font-weight: 700; font-size: 11px; }

            /* Delta */
            .psim-delta-pos { color: #166534; }
            .psim-delta-neg { color: #9a3412; }

            /* Search highlight */
            .psim-hl { background: #fef9c3; border-radius: 2px; padding: 0 1px; font-style: normal; }

            /* Muted cell */
            .psim-muted { color: #94a3b8; text-align: center; padding: 0 !important; }

            /* Responsive */
            @media (max-width: 1100px) { .psim-grid { grid-template-columns: repeat(3, 1fr); } .psim-source-grid{grid-template-columns:1fr;} .psim-result-filters{display:grid;} .psim-result-filter-controls{grid-template-columns:1fr 1fr auto;} }
            @media (max-width: 800px)  { .psim-grid { grid-template-columns: repeat(2, 1fr); } .psim-result-filter-controls{grid-template-columns:1fr;} }
            @media (max-width: 500px)  { .psim-grid { grid-template-columns: 1fr; } .psim-search { width: 130px !important; } .psim-kbd-hint { display: none; } }
        `;
    document.head.appendChild(style);
}
