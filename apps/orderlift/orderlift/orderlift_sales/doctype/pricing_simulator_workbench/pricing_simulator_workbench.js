frappe.ui.form.on("Pricing Simulator Workbench", {
    refresh(frm) {
        ensureWorkbenchStyles();
        setupWorkbenchQueries(frm);
        loadColumnPrefs();
        frm.set_intro(
            __("Use native source grids to compare dynamic and static unit prices for the same customer and territory context."),
            "blue"
        );

        frm.clear_custom_buttons();
        frm.add_custom_button(__("Load Defaults"), () => loadWorkbenchDefaults(frm), __("Simulator"));
        frm.add_custom_button(__("Run Simulation"), () => runWorkbenchSimulation(frm), __("Simulator"));

        renderWorkbenchResults(frm, {});
        scheduleWorkbenchSimulation(frm);
    },
    view_mode(frm) { scheduleWorkbenchSimulation(frm); },
    customer(frm) { scheduleWorkbenchSimulation(frm); },
    geography_territory(frm) { scheduleWorkbenchSimulation(frm); },
    only_priced_items(frm) { scheduleWorkbenchSimulation(frm); },
    max_items(frm) { scheduleWorkbenchSimulation(frm); },
});

frappe.ui.form.on("Pricing Builder Sourcing Rule", {
    buying_price_list(frm) { if (frm.doctype === "Pricing Simulator Workbench") scheduleWorkbenchSimulation(frm); },
    pricing_scenario(frm) { if (frm.doctype === "Pricing Simulator Workbench") scheduleWorkbenchSimulation(frm); },
    customs_policy(frm) { if (frm.doctype === "Pricing Simulator Workbench") scheduleWorkbenchSimulation(frm); },
    benchmark_policy(frm) { if (frm.doctype === "Pricing Simulator Workbench") scheduleWorkbenchSimulation(frm); },
    is_active(frm) { if (frm.doctype === "Pricing Simulator Workbench") scheduleWorkbenchSimulation(frm); },
    dynamic_sources_add(frm) { if (frm.doctype === "Pricing Simulator Workbench") scheduleWorkbenchSimulation(frm); },
    dynamic_sources_remove(frm) { if (frm.doctype === "Pricing Simulator Workbench") scheduleWorkbenchSimulation(frm); },
});

frappe.ui.form.on("Pricing Simulator Static Source", {
    selling_price_list(frm) { if (frm.doctype === "Pricing Simulator Workbench") scheduleWorkbenchSimulation(frm); },
    is_active(frm) { if (frm.doctype === "Pricing Simulator Workbench") scheduleWorkbenchSimulation(frm); },
    static_sources_add(frm) { if (frm.doctype === "Pricing Simulator Workbench") scheduleWorkbenchSimulation(frm); },
    static_sources_remove(frm) { if (frm.doctype === "Pricing Simulator Workbench") scheduleWorkbenchSimulation(frm); },
});

function setupWorkbenchQueries(frm) {
    frm.set_query("buying_price_list", "dynamic_sources", () => ({ filters: { buying: 1 } }));
    frm.set_query("pricing_scenario", "dynamic_sources", () => ({ filters: {} }));
    frm.set_query("customs_policy", "dynamic_sources", () => ({ filters: { is_active: 1 } }));
    frm.set_query("benchmark_policy", "dynamic_sources", () => ({ filters: { is_active: 1 } }));
    frm.set_query("selling_price_list", "static_sources", () => ({ filters: { selling: 1 } }));
}

async function loadWorkbenchDefaults(frm) {
    const response = await frappe.call({
        method: "orderlift.orderlift_sales.page.pricing_simulator.pricing_simulator.get_simulation_defaults",
        args: { sales_person: "", mode: "Auto" },
        freeze: true,
        freeze_message: __("Loading simulator defaults..."),
    });
    const data = response.message || {};
    if (data.dynamic && !(frm.doc.dynamic_sources || []).length && data.dynamic.buying_price_list) {
        frm.add_child("dynamic_sources", {
            buying_price_list: data.dynamic.buying_price_list || "",
            pricing_scenario: data.dynamic.pricing_scenario || "",
            customs_policy: data.dynamic.customs_policy || "",
            benchmark_policy: data.dynamic.benchmark_policy || "",
            is_active: 1,
        });
    }
    if (data.static && !(frm.doc.static_sources || []).length) {
        (data.static.selling_price_lists || []).forEach((name) => {
            frm.add_child("static_sources", { selling_price_list: name, is_active: 1 });
        });
    }
    frm.refresh_field("dynamic_sources");
    frm.refresh_field("static_sources");
    await runWorkbenchSimulation(frm);
}

async function runWorkbenchSimulation(frm) {
    if (frm.__sim_running) return;
    frm.__sim_running = true;
    try {
        const response = await frappe.call({
            method: "orderlift.orderlift_sales.doctype.pricing_simulator_workbench.pricing_simulator_workbench.run_simulation_preview",
            args: {
                payload: JSON.stringify(collectWorkbenchPayload(frm)),
                view_mode: frm.doc.view_mode || "Compare",
            },
        });
        frm.__lastSimulationPayload = response.message || {};
        renderWorkbenchResults(frm, frm.__lastSimulationPayload);
    } catch (e) {
        frm.__lastSimulationPayload = {
            warnings: [e?.message || __("Simulation failed.")],
        };
        renderWorkbenchResults(frm, frm.__lastSimulationPayload);
    } finally {
        frm.__sim_running = false;
    }
}

function scheduleWorkbenchSimulation(frm) {
    clearTimeout(frm.__sim_timer);
    frm.__sim_timer = setTimeout(() => runWorkbenchSimulation(frm), 350);
}

function renderWorkbenchResults(frm, payload) {
    const wrap = frm.get_field("results_html")?.$wrapper;
    if (!wrap) return;
    if (!payload || !Object.keys(payload).length) {
        wrap.html(`
            ${renderContextBar(frm)}
            <div class="pswb-metrics">
                ${metricCard(__("Compared Items"), 0)}
                ${metricCard(__("Dynamic Sources"), (frm.doc.dynamic_sources || []).filter((row) => row.is_active).length)}
                ${metricCard(__("Static Missing"), 0)}
            </div>
            <div class="pswb-empty">${__("Configure source tables above. Results will refresh automatically when values change.")}</div>
            <div class="pswb-table-wrap"><table class="pswb-table"><thead><tr>
                <th>${__("Item")}</th><th>${__("Buying List")}</th><th>${__("Politique Charges")}</th><th>${__("PU Achat")}</th><th>${__("Charges U")}</th><th>${__("Benchmark")}</th><th>${__("Dedouan. U")}</th><th>${__("Modifiers U")}</th><th>${__("PUV Final")}</th><th>${__("Sell List")}</th><th>${__("PTV Brut")}</th>
            </tr></thead><tbody><tr><td colspan="12">${__("No simulation results yet.")}</td></tr></tbody></table></div>
        `);
        return;
    }
    if (payload.view_mode === "Compare") {
        wrap.html(renderWorkbenchComparison(frm, payload.dynamic || {}, payload.static || {}));
        bindColumnControls(frm, "Compare");
        return;
    }
    wrap.html(renderWorkbenchSingle(frm, payload));
    bindColumnControls(frm, payload.pricing_mode || payload.mode || "Dynamic");
}

function renderWorkbenchComparison(frm, dynamicData, staticData) {
    const dynRows = Object.fromEntries((dynamicData.rows || []).map((r) => [r.item, r]));
    const staRows = Object.fromEntries((staticData.rows || []).map((r) => [r.item, r]));
    const keys = [...new Set([...(dynamicData.rows || []).map((x) => x.item), ...(staticData.rows || []).map((x) => x.item)])];
    const rows = keys.map((item) => {
        const d = dynRows[item] || {};
        const s = staRows[item] || {};
        return `
            <tr>
                <td>${linkToDoc("Item", item)}</td>
                <td>${escapeHtml(d.material || s.material || "-")}</td>
                <td>${escapeHtml(d.source_buying_price_list || "-")}</td>
                <td>${escapeHtml(d.resolved_pricing_scenario || "-")}</td>
                <td>${fmtCurrency(d.buy_price)}</td>
                <td>${fmtCurrency(d.customs_applied)}</td>
                <td>${fmtCurrency(d.tier_modifier_amount)}</td>
                <td>${fmtCurrency(d.zone_modifier_amount)}</td>
                <td><strong>${fmtCurrency(d.final_sell_unit_price)}</strong></td>
                <td>${escapeHtml(s.selected_price_list || "-")}</td>
                <td><strong>${fmtCurrency(s.selected_price)}</strong></td>
            </tr>
        `;
    }).join("");
    const columns = getVisibleColumns("Compare");
    const headers = columns.map((col) => `<th>${escapeHtml(col.label)}</th>`).join("");
    const rowHtml = keys.map((item) => {
        const d = dynRows[item] || {};
        const s = staRows[item] || {};
        return `<tr>${columns.map((col) => `<td>${renderColumnValue(col.key, { item, d, s, compare: true })}</td>`).join("")}</tr>`;
    }).join("");
    return `
        ${renderContextBarFromPayload(dynamicData, staticData, "Compare", frm)}
        <div class="pswb-metrics">
            ${metricCard(__("Compared Items"), keys.length)}
            ${metricCard(__("Dynamic Sources"), dynamicData.summary?.policy_count || 0)}
            ${metricCard(__("Static Missing"), staticData.summary?.missing_items || 0)}
        </div>
        ${renderWorkbenchWarnings([...(dynamicData.warnings || []).map((w) => `[Dynamic] ${w}`), ...(staticData.warnings || []).map((w) => `[Static] ${w}`)])}
        ${renderColumnConfigurator("Compare")}
        <div class="pswb-table-wrap"><table class="pswb-table"><thead><tr>${headers}</tr></thead><tbody>${rowHtml || `<tr><td colspan="${columns.length}">${__("No comparable items.")}</td></tr>`}</tbody></table></div>
    `;
}

function renderWorkbenchSingle(frm, data) {
    const mode = data.pricing_mode || data.mode || "Dynamic";
    if (mode === "Static") {
        const columns = getVisibleColumns("Static");
        const headers = columns.map((col) => `<th>${escapeHtml(col.label)}</th>`).join("");
        const rows = (data.rows || []).map((row) => `<tr>${columns.map((col) => `<td>${renderColumnValue(col.key, row)}</td>`).join("")}</tr>`).join("");
        return `
            ${renderContextBarFromPayload(null, data, "Static", frm)}
            <div class="pswb-metrics">
                ${metricCard(__("Priced Items"), data.summary?.priced_items || 0)}
                ${metricCard(__("Missing Prices"), data.summary?.missing_items || 0)}
                ${metricCard(__("Sell Lists"), data.summary?.selling_lists_count || 0)}
            </div>
            ${renderWorkbenchWarnings(data.warnings || [])}
            ${renderColumnConfigurator("Static")}
            <div class="pswb-table-wrap"><table class="pswb-table"><thead><tr>${headers}</tr></thead><tbody>${rows || `<tr><td colspan="${columns.length}">${__("No static rows.")}</td></tr>`}</tbody></table></div>
        `;
    }

    const columns = getVisibleColumns("Dynamic");
    const headers = columns.map((col) => `<th>${escapeHtml(col.label)}</th>`).join("");
    const rows = (data.rows || []).map((row) => `<tr>${columns.map((col) => `<td>${renderColumnValue(col.key, row)}</td>`).join("")}</tr>`).join("");
    return `
        ${renderContextBarFromPayload(data, null, "Dynamic", frm)}
        <div class="pswb-metrics">
            ${metricCard(__("Simulated Items"), data.summary?.item_count || (data.rows || []).length)}
            ${metricCard(__("Policies"), data.summary?.policy_count || 0)}
            ${metricCard(__("Marge %"), `${Number(data.summary?.global_margin_pct || 0).toFixed(1)}%`)}
        </div>
        ${renderWorkbenchWarnings(data.warnings || [])}
        ${renderColumnConfigurator("Dynamic")}
        <div class="pswb-table-wrap"><table class="pswb-table"><thead><tr>${headers}</tr></thead><tbody>${rows || `<tr><td colspan="${columns.length}">${__("No dynamic rows.")}</td></tr>`}</tbody></table></div>
    `;
}

function collectWorkbenchPayload(frm) {
    return {
        customer: (frm.doc.customer || "").trim(),
        sales_person: "",
        geography_territory: (frm.doc.geography_territory || "").trim(),
        selling_price_lists: (frm.doc.static_sources || [])
            .filter((row) => (row.selling_price_list || "").trim() && cint(row.is_active))
            .map((row) => row.selling_price_list),
        sourcing_rules: (frm.doc.dynamic_sources || [])
            .filter((row) => (row.buying_price_list || "").trim() && cint(row.is_active))
            .map((row) => ({
                buying_price_list: row.buying_price_list,
                pricing_scenario: row.pricing_scenario,
                customs_policy: row.customs_policy,
                benchmark_policy: row.benchmark_policy,
                is_active: row.is_active,
            })),
        use_all_enabled_items: 1,
        default_qty: 1,
        max_items: cint(frm.doc.max_items || 0),
        only_priced_items: cint(frm.doc.only_priced_items || 0),
        items: [],
    };
}

const DEFAULT_COLUMNS = {
    Compare: ["item", "buying_list", "expenses_policy", "dyn_buy", "expenses", "dyn_customs", "benchmark_price", "dyn_tier_mod", "dyn_territory_mod", "dyn_margin", "dyn_final", "static_list", "static_price", "static_margin"],
    Dynamic: ["item", "buying_list", "expenses_policy", "buy", "expenses", "customs", "benchmark_price", "tier_mod", "territory_mod", "margin_unit", "final", "margin"],
    Static: ["item", "static_list", "reference_buy", "static_price", "static_margin", "options"],
};

const COLUMN_DEFS = {
    Compare: [
        { key: "item", label: __("Item") },
        { key: "buying_list", label: __("Buying List") },
        { key: "expenses_policy", label: __("Politique Charges") },
        { key: "customs_policy", label: __("Politique Douane") },
        { key: "benchmark_policy", label: __("Politique Marge") },
        { key: "dyn_buy", label: __("PU Achat") },
        { key: "expenses", label: __("Charges U") },
        { key: "dyn_customs", label: __("Dedouan. U") },
        { key: "dyn_tier_mod", label: __("Tier Mod") },
        { key: "dyn_territory_mod", label: __("Territory Mod") },
        { key: "benchmark_price", label: __("Benchmark") },
        { key: "dyn_margin", label: __("Marge U") },
        { key: "dyn_final", label: __("PUV Final") },
        { key: "static_list", label: __("Sell List") },
        { key: "static_price", label: __("PTV Brut") },
        { key: "static_margin", label: __("Marge % statique") },
    ],
    Dynamic: [
        { key: "item", label: __("Item") },
        { key: "buying_list", label: __("Buying List") },
        { key: "expenses_policy", label: __("Politique Charges") },
        { key: "customs_policy", label: __("Politique Douane") },
        { key: "benchmark_policy", label: __("Politique Marge") },
        { key: "buy", label: __("PU Achat") },
        { key: "expenses", label: __("Charges U") },
        { key: "customs", label: __("Dedouan. U") },
        { key: "tier_mod", label: __("Tier Mod") },
        { key: "territory_mod", label: __("Territory Mod") },
        { key: "benchmark_price", label: __("Benchmark") },
        { key: "margin_unit", label: __("Marge U") },
        { key: "final", label: __("PUV Final") },
        { key: "margin", label: __("Marge %") },
    ],
    Static: [
        { key: "item", label: __("Item") },
        { key: "static_list", label: __("Sell List") },
        { key: "reference_buy", label: __("PU Achat") },
        { key: "static_price", label: __("PTV Brut") },
        { key: "static_margin", label: __("Marge % statique") },
        { key: "options", label: __("Options") },
    ],
};

function getVisibleColumns(mode) {
    const current = window.__pswbColumns || {};
    const keys = current[mode] || DEFAULT_COLUMNS[mode] || [];
    const defsByKey = Object.fromEntries((COLUMN_DEFS[mode] || []).map((col) => [col.key, col]));
    return keys.map((key) => defsByKey[key]).filter(Boolean);
}

function loadColumnPrefs() {
    if (window.__pswbColumnPrefsLoaded) return;
    window.__pswbColumnPrefsLoaded = true;
    try {
        window.__pswbColumns = JSON.parse(localStorage.getItem("pswb_columns") || "{}") || {};
        window.__pswbColumnsOpen = JSON.parse(localStorage.getItem("pswb_columns_open") || "{}") || {};
    } catch (e) {
        window.__pswbColumns = {};
        window.__pswbColumnsOpen = {};
    }
}

function saveColumnPrefs() {
    localStorage.setItem("pswb_columns", JSON.stringify(window.__pswbColumns || {}));
    localStorage.setItem("pswb_columns_open", JSON.stringify(window.__pswbColumnsOpen || {}));
}

function renderColumnConfigurator(mode) {
    const defs = COLUMN_DEFS[mode] || [];
    const selected = new Set((window.__pswbColumns || {})[mode] || DEFAULT_COLUMNS[mode] || []);
    const isOpen = !!((window.__pswbColumnsOpen || {})[mode]);
    return `
        <details class="pswb-columns" ${isOpen ? "open" : ""} data-col-details="${mode}">
            <summary>${__("Columns")}</summary>
            <div class="pswb-column-grid">
                ${defs.map((col) => `<div class="pswb-column-option"><label><input type="checkbox" data-col-mode="${mode}" data-col-key="${col.key}" ${selected.has(col.key) ? "checked" : ""}> <span>${escapeHtml(col.label)}</span></label><span class="pswb-column-order"><button type="button" data-col-move="up" data-col-mode="${mode}" data-col-key="${col.key}">↑</button><button type="button" data-col-move="down" data-col-mode="${mode}" data-col-key="${col.key}">↓</button></span></div>`).join("")}
            </div>
        </details>
    `;
}

function bindColumnControls(frm, mode) {
    const wrap = frm.get_field("results_html")?.$wrapper;
    if (!wrap) return;
    wrap.find("[data-col-details]").off("toggle").on("toggle", function () {
        const modeKey = $(this).data("colDetails");
        window.__pswbColumnsOpen = { ...(window.__pswbColumnsOpen || {}), [modeKey]: this.open };
        saveColumnPrefs();
    });
    wrap.find("[data-col-key]").off("change").on("change", function () {
        const targetMode = $(this).data("colMode");
        const key = $(this).data("colKey");
        const current = { ...(window.__pswbColumns || {}) };
        const set = new Set(current[targetMode] || DEFAULT_COLUMNS[targetMode] || []);
        if ($(this).is(":checked")) set.add(key);
        else set.delete(key);
        current[targetMode] = Array.from(set);
        window.__pswbColumns = current;
        window.__pswbColumnsOpen = { ...(window.__pswbColumnsOpen || {}), [targetMode]: true };
        saveColumnPrefs();
        renderWorkbenchResults(frm, frm.__lastSimulationPayload || {});
    });
    wrap.find("[data-col-move]").off("click").on("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const targetMode = $(this).data("colMode");
        const key = $(this).data("colKey");
        const direction = $(this).data("colMove");
        const current = { ...(window.__pswbColumns || {}) };
        const list = [...(current[targetMode] || DEFAULT_COLUMNS[targetMode] || [])];
        const idx = list.indexOf(key);
        if (idx === -1) return;
        const swap = direction === "up" ? idx - 1 : idx + 1;
        if (swap < 0 || swap >= list.length) return;
        [list[idx], list[swap]] = [list[swap], list[idx]];
        current[targetMode] = list;
        window.__pswbColumns = current;
        window.__pswbColumnsOpen = { ...(window.__pswbColumnsOpen || {}), [targetMode]: true };
        saveColumnPrefs();
        renderWorkbenchResults(frm, frm.__lastSimulationPayload || {});
    });
    frm.__lastRenderedMode = mode;
}

function renderColumnValue(key, row) {
    const d = row.d || row;
    const s = row.s || {};
    if (key === "item") return linkToDoc("Item", row.item || d.item);
    if (key === "material") return escapeHtml(d.material || s.material || "-");
    if (key === "buying_list") return escapeHtml(d.source_buying_price_list || "-");
    if (key === "scenario" || key === "expenses_policy") return escapeHtml(d.expenses_policy || d.resolved_pricing_scenario || "-");
    if (key === "customs_policy") return escapeHtml(d.customs_policy || "-");
    if (key === "benchmark_policy") return escapeHtml(d.benchmark_policy || d.applied_benchmark_policy || "-");
    if (key === "dyn_buy" || key === "buy") return fmtCurrency(d.buy_price);
    if (key === "expenses") return fmtCurrency(d.expense_unit_price);
    if (key === "dyn_customs" || key === "customs") return fmtCurrency(d.customs_applied);
    if (key === "dyn_tier_mod" || key === "tier_mod") return fmtCurrency(d.tier_modifier_amount);
    if (key === "dyn_territory_mod" || key === "territory_mod") return fmtCurrency(d.zone_modifier_amount);
    if (key === "dyn_margin") return `${Number(d.margin_pct || 0).toFixed(1)}%`;
    if (key === "dyn_final" || key === "final") return `<strong>${fmtCurrency(d.final_sell_unit_price)}</strong>`;
    if (key === "static_list") return escapeHtml(s.selected_price_list || row.selected_price_list || "-");
    if (key === "static_price") return `<strong>${fmtCurrency(s.selected_price || row.selected_price)}</strong>`;
    if (key === "reference_buy") return fmtCurrency(row.reference_buy_price);
    if (key === "static_margin") return `${Number((s.static_margin_pct ?? row.static_margin_pct) || 0).toFixed(1)}%`;
    if (key === "bench_ref" || key === "benchmark_price") return fmtCurrency(d.benchmark_reference);
    if (key === "margin_unit") return fmtCurrency(d.margin_unit_amount);
    if (key === "margin") return `${Number(d.margin_pct || 0).toFixed(1)}%`;
    if (key === "options") return row.option_count || 0;
    return "-";
}

function renderContextBar(frm) {
    return renderContextBarFromPayload(null, null, frm.doc.view_mode || "Compare", frm);
}

function renderContextBarFromPayload(dynamicData, staticData, mode, frm = null) {
    const sourceDoc = frm?.doc || null;
    const customer = sourceDoc?.customer || "-";
    const territory = sourceDoc?.geography_territory || "-";
    const dynamicSources = sourceDoc ? (sourceDoc.dynamic_sources || []).filter((row) => row.is_active).map((row) => row.buying_price_list).filter(Boolean) : [];
    const staticLists = sourceDoc ? (sourceDoc.static_sources || []).filter((row) => row.is_active).map((row) => row.selling_price_list).filter(Boolean) : [];
    return `
        <div class="pswb-context">
            <div class="pswb-context-chip"><span>${__("Mode")}</span><strong>${escapeHtml(mode || "Compare")}</strong></div>
            <div class="pswb-context-chip"><span>${__("Customer")}</span><strong>${escapeHtml(customer)}</strong></div>
            <div class="pswb-context-chip"><span>${__("Territory")}</span><strong>${escapeHtml(territory)}</strong></div>
            <div class="pswb-context-chip"><span>${__("Dynamic Sources")}</span><strong>${escapeHtml(dynamicSources.join(", ") || "-")}</strong></div>
            <div class="pswb-context-chip"><span>${__("Static Lists")}</span><strong>${escapeHtml(staticLists.join(", ") || "-")}</strong></div>
        </div>
    `;
}

function renderWorkbenchWarnings(warnings) {
    if (!warnings || !warnings.length) return `<div class="pswb-clean">${__("No warnings")}</div>`;
    return `<div class="pswb-warn">${warnings.map((w) => `<div>• ${escapeHtml(w)}</div>`).join("")}</div>`;
}

function linkToDoc(doctype, name) {
    if (!name) return "-";
    return `<a href="/app/${frappe.router.slug(doctype)}/${encodeURIComponent(name)}" target="_blank">${escapeHtml(name)}</a>`;
}

function fmtCurrency(value) {
    return frappe.format(value || 0, { fieldtype: "Currency" });
}

function escapeHtml(value) {
    return frappe.utils.escape_html(String(value || ""));
}

function metricCard(label, value) {
    return `<div class="pswb-metric"><span>${escapeHtml(label)}</span><strong>${value}</strong></div>`;
}

function ensureWorkbenchStyles() {
    if (document.getElementById("pricing-simulator-workbench-styles")) return;
    const style = document.createElement("style");
    style.id = "pricing-simulator-workbench-styles";
    style.textContent = `
        .pswb-empty,.pswb-clean,.pswb-warn{padding:12px 14px;border-radius:12px;background:#f8fafc;border:1px solid #e2e8f0;margin-bottom:10px}
        .pswb-warn{background:#fff7ed;border-color:#fdba74;color:#9a3412}
        .pswb-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:10px}
        .pswb-context{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-bottom:10px}
        .pswb-context-chip{padding:10px 12px;border-radius:12px;background:#f8fafc;border:1px solid #e2e8f0}
        .pswb-context-chip span{display:block;font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:#64748b;margin-bottom:4px}
        .pswb-context-chip strong{font-size:13px;color:#0f172a}
        .pswb-metric{padding:12px 14px;border-radius:12px;background:#fff;border:1px solid #e2e8f0}
        .pswb-metric span{display:block;font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:#64748b;margin-bottom:6px}
        .pswb-metric strong{font-size:20px;color:#0f172a}
        .pswb-columns{margin:0 0 10px;padding:10px 12px;border:1px solid #e2e8f0;border-radius:12px;background:#fff}
        .pswb-columns summary{cursor:pointer;font-size:12px;font-weight:700;color:#0f172a}
        .pswb-column-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:10px}
        .pswb-column-option{display:flex;justify-content:space-between;gap:8px;align-items:center;font-size:12px;color:#475569;padding:6px 8px;border-radius:10px;background:#f8fafc;border:1px solid #e2e8f0}
        .pswb-column-option label{display:flex;gap:8px;align-items:center;margin:0;flex:1}
        .pswb-column-order{display:flex;gap:4px}
        .pswb-column-order button{border:1px solid #d1d5db;background:#fff;border-radius:6px;padding:0 6px;cursor:pointer}
        .pswb-table-wrap{overflow:auto;border:1px solid #e2e8f0;border-radius:12px;background:#fff}
        .pswb-table{width:100%;border-collapse:collapse;font-size:12px}
        .pswb-table th,.pswb-table td{padding:8px;border-bottom:1px solid #f1f5f9;white-space:nowrap}
        .pswb-table th{background:#f8fafc;color:#64748b;text-transform:uppercase;letter-spacing:.05em;font-size:10px}
        @media (max-width:900px){.pswb-metrics,.pswb-column-grid,.pswb-context{grid-template-columns:1fr}}
    `;
    document.head.appendChild(style);
}
