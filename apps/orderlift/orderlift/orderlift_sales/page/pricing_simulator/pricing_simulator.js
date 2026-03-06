frappe.pages["pricing-simulator"].on_page_load = function (wrapper) {
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
    };

    buildLayout(state);
    loadDefaults(state, false).then(() => runSimulation(state));
};

function buildLayout(state) {
    const { page } = state;

    const controlsWrap = $(
        `<div class="psim-controls">
            <div class="psim-card-head">
                <div class="psim-title">${__("Filters")}</div>
                <div class="psim-actions">
                    <button class="btn btn-default btn-xs" data-action="load-defaults">${__("Use Agent Defaults")}</button>
                    <button class="btn btn-primary btn-xs" data-action="refresh">${__("Refresh")}</button>
                </div>
            </div>
            <div class="psim-grid"></div>
            <div class="psim-hint" data-role="auto-hint"></div>
        </div>`
    );

    const outputWrap = $(
        `<div class="psim-card">
            <div class="psim-card-head">
                <div class="psim-title">${__("Results")}</div>
            </div>
            <div class="psim-output">${__("Run simulation to view dynamic or static pricing outcomes.")}</div>
        </div>`
    );

    page.main.append(controlsWrap);
    page.main.append(outputWrap);

    state.autoHint = controlsWrap.find('[data-role="auto-hint"]');
    state.outputWrap = outputWrap.find(".psim-output");

    const grid = controlsWrap.find(".psim-grid");
    state.controls = {
        customer: makeControl(grid, { fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" }),
        sales_person: makeControl(grid, { fieldname: "sales_person", label: __("Sales Person"), fieldtype: "Link", options: "Sales Person" }),
        view_mode: makeControl(grid, { fieldname: "view_mode", label: __("View"), fieldtype: "Select", options: "Compare (Dynamic vs Static)\nDynamic only\nStatic only", default: "Compare (Dynamic vs Static)" }),
        item_group: makeControl(grid, { fieldname: "item_group", label: __("Item Group Filter"), fieldtype: "Link", options: "Item Group" }),
        default_qty: makeControl(grid, { fieldname: "default_qty", label: __("Default Qty per Item"), fieldtype: "Float", default: 1 }),
        max_items: makeControl(grid, { fieldname: "max_items", label: __("Max Items"), fieldtype: "Int", default: 100 }),
        scenario_policy: makeControl(grid, { fieldname: "scenario_policy", label: __("Scenario Policy Override"), fieldtype: "Link", options: "Pricing Scenario Policy" }),
        pricing_scenario: makeControl(grid, { fieldname: "pricing_scenario", label: __("Pricing Scenario Override"), fieldtype: "Link", options: "Pricing Scenario" }),
        customs_policy: makeControl(grid, { fieldname: "customs_policy", label: __("Customs Policy Override"), fieldtype: "Link", options: "Pricing Customs Policy" }),
        benchmark_policy: makeControl(grid, { fieldname: "benchmark_policy", label: __("Benchmark Policy Override"), fieldtype: "Link", options: "Pricing Benchmark Policy" }),
        static_lists: makeControl(grid, { fieldname: "static_lists", label: __("Static Lists Override"), fieldtype: "Small Text", description: __("Comma-separated selling lists for static simulation." ) }),
    };

    controlsWrap.find('[data-action="load-defaults"]').on("click", () => loadDefaults(state, true));
    controlsWrap.find('[data-action="refresh"]').on("click", () => runSimulation(state));

    Object.values(state.controls).forEach((control) => {
        control.$input?.on("change", () => queueRun(state));
    });
    state.controls.sales_person.$input?.on("change", async () => {
        await loadDefaults(state, false);
        queueRun(state);
    });
}

function makeControl(parent, df) {
    const wrap = $(`<div class="psim-field"></div>`).appendTo(parent);
    const control = frappe.ui.form.make_control({
        parent: wrap,
        df,
        render_input: true,
    });
    control.refresh();
    if (df.default) {
        control.set_value(df.default);
    }
    return control;
}

async function loadDefaults(state, forceToast) {
    const salesPerson = state.controls.sales_person.get_value();
    if (!salesPerson) {
        return;
    }

    const resp = await frappe.call({
        method: "orderlift.orderlift_sales.page.pricing_simulator.pricing_simulator.get_simulation_defaults",
        args: { sales_person: salesPerson, mode: "Auto" },
    });
    const data = resp.message || {};

    if (data.dynamic) {
        if (!state.controls.pricing_scenario.get_value()) {
            state.controls.pricing_scenario.set_value(data.dynamic.pricing_scenario || "");
        }
        if (!state.controls.customs_policy.get_value()) {
            state.controls.customs_policy.set_value(data.dynamic.customs_policy || "");
        }
        if (!state.controls.benchmark_policy.get_value()) {
            state.controls.benchmark_policy.set_value(data.dynamic.benchmark_policy || "");
        }
    }

    if (data.static && !state.controls.static_lists.get_value()) {
        state.controls.static_lists.set_value((data.static.selling_price_lists || []).join(", "));
    }

    state.enabledItemCount = Number(data.enabled_item_count || 0);
    renderAutoHint(state);

    state.defaultsApplied = true;

    if (forceToast) {
        const modeLabel = data.resolved_mode || "Auto";
        frappe.show_alert({ message: __("Defaults loaded ({0})", [modeLabel]), indicator: "green" });
    }
}

function collectPayload(state) {
    return {
        customer: state.controls.customer.get_value() || "",
        sales_person: state.controls.sales_person.get_value() || "",
        scenario_policy: state.controls.scenario_policy.get_value() || "",
        pricing_scenario: state.controls.pricing_scenario.get_value() || "",
        customs_policy: state.controls.customs_policy.get_value() || "",
        benchmark_policy: state.controls.benchmark_policy.get_value() || "",
        selling_price_lists: parseList(state.controls.static_lists.get_value()),
        use_all_enabled_items: 1,
        item_group: state.controls.item_group.get_value() || "",
        default_qty: state.controls.default_qty.get_value() || 1,
        max_items: state.controls.max_items.get_value() || 0,
        items: [],
    };
}

function parseList(value) {
    return String(value || "")
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean);
}

function queueRun(state) {
    if (state.debounce) {
        clearTimeout(state.debounce);
    }
    state.debounce = setTimeout(() => runSimulation(state), 300);
}

async function runSimulation(state) {
    const payload = collectPayload(state);
    const selectedView = state.controls.view_mode.get_value() || "Compare (Dynamic vs Static)";
    const runDynamic = selectedView !== "Static only";
    const runStatic = selectedView !== "Dynamic only";

    state.outputWrap.html(`<div class="psim-loading">${__("Running simulation...")}</div>`);

    try {
        const dynamicResult = runDynamic ? await runSingleMode(payload, "Dynamic") : null;
        const staticResult = runStatic ? await runSingleMode(payload, "Static") : null;

        if (dynamicResult && staticResult) {
            renderComparison(state, payload.items, dynamicResult, staticResult);
        } else {
            renderResults(state, dynamicResult || staticResult || {});
        }
    } catch (e) {
        state.outputWrap.html(`<div class="psim-error">${__("Simulation failed. Check parameters and try again.")}</div>`);
        throw e;
    }
}

function renderAutoHint(state) {
    const count = Number(state.enabledItemCount || 0);
    const text = count > 0
        ? __("Showing auto-simulated table for {0} enabled item(s).", [count])
        : __("All enabled items will be auto-loaded at runtime.");
    state.autoHint.html(`<div class="psim-auto-hint">${frappe.utils.escape_html(text)}</div>`);
}

async function runSingleMode(payload, mode) {
    const req = { ...payload, mode };
    const resp = await frappe.call({
        method: "orderlift.orderlift_sales.page.pricing_simulator.pricing_simulator.run_pricing_simulation",
        args: { payload: req },
    });
    return resp.message || {};
}

function renderComparison(state, inputItems, dynamicData, staticData) {
    const dynRows = Object.fromEntries((dynamicData.rows || []).map((r) => [r.item, r]));
    const staRows = Object.fromEntries((staticData.rows || []).map((r) => [r.item, r]));
    const keys = [...new Set([
        ...(dynamicData.rows || []).map((x) => x.item),
        ...(staticData.rows || []).map((x) => x.item),
    ])];

    const tableRows = keys.map((item) => {
        const d = dynRows[item] || {};
        const s = staRows[item] || {};
        const dynFinal = Number(d.final_sell_unit_price || 0);
        const staPrice = Number(s.selected_price || 0);
        const delta = dynFinal - staPrice;
        const deltaClass = delta >= 0 ? "psim-delta-pos" : "psim-delta-neg";

        return `<tr>
            <td>${frappe.utils.escape_html(item)}</td>
            <td>${frappe.format(d.qty || s.qty || 0, { fieldtype: "Float" })}</td>
            <td>${frappe.utils.escape_html(d.resolved_pricing_scenario || "-")}</td>
            <td>${frappe.format(d.buy_price || 0, { fieldtype: "Currency" })}</td>
            <td>${frappe.format(dynFinal || 0, { fieldtype: "Currency" })}</td>
            <td>${Number(d.margin_pct || 0).toFixed(1)}%</td>
            <td>${frappe.format(staPrice || 0, { fieldtype: "Currency" })}</td>
            <td>${frappe.utils.escape_html(s.selected_price_list || "-")}</td>
            <td>${frappe.format(delta || 0, { fieldtype: "Currency" })}</td>
            <td class="${deltaClass}">${delta >= 0 ? __("Dynamic >= Static") : __("Dynamic < Static")}</td>
        </tr>`;
    }).join("") || `<tr><td colspan="10" class="psim-muted">${__("No comparable rows")}</td></tr>`;

    const combinedWarnings = [
        ...(dynamicData.warnings || []).map((w) => `[Dynamic] ${w}`),
        ...(staticData.warnings || []).map((w) => `[Static] ${w}`),
    ];

    const warningHtml = combinedWarnings.length
        ? `<div class="psim-warnings">${combinedWarnings.map((w) => `<div>• ${frappe.utils.escape_html(w)}</div>`).join("")}</div>`
        : `<div class="psim-clean">${__("No warnings")}</div>`;

    state.outputWrap.html(`
        <div class="psim-mode"><strong>${__("Comparison Matrix: Dynamic vs Static")}</strong></div>
        <div class="psim-metrics">
            ${metricCard(__("Dynamic Total Selling"), frappe.format(dynamicData.summary?.total_selling || 0, { fieldtype: "Currency" }))}
            ${metricCard(__("Static Total Selling"), frappe.format(staticData.summary?.total_selling || 0, { fieldtype: "Currency" }))}
            ${metricCard(__("Dynamic Margin"), `${Number(dynamicData.summary?.global_margin_pct || 0).toFixed(1)}%`)}
            ${metricCard(__("Static Missing Items"), staticData.summary?.missing_items || 0)}
        </div>
        ${warningHtml}
        <div class="psim-table-wrap">
            <table class="psim-table">
                <thead>
                    <tr>
                        <th>${__("Item")}</th>
                        <th>${__("Qty")}</th>
                        <th>${__("Dynamic Scenario")}</th>
                        <th>${__("Dynamic Buy")}</th>
                        <th>${__("Dynamic Final")}</th>
                        <th>${__("Dynamic Margin %")}</th>
                        <th>${__("Static Price")}</th>
                        <th>${__("Static List")}</th>
                        <th>${__("Delta (Dyn-Static)")}</th>
                        <th>${__("Comparison")}</th>
                    </tr>
                </thead>
                <tbody>${tableRows}</tbody>
            </table>
        </div>
    `);
}

function renderResults(state, data) {
    const mode = data.pricing_mode || data.mode || "Dynamic";
    const rows = data.rows || [];
    const summary = data.summary || {};
    const warnings = data.warnings || [];

    const cards = mode === "Static"
        ? `
            ${metricCard(__("Priced Items"), summary.priced_items || 0)}
            ${metricCard(__("Missing Prices"), summary.missing_items || 0)}
            ${metricCard(__("Total Selling"), frappe.format(summary.total_selling || 0, { fieldtype: "Currency" }))}
        `
        : `
            ${metricCard(__("Total Buy"), frappe.format(summary.total_buy || 0, { fieldtype: "Currency" }))}
            ${metricCard(__("Total Expenses"), frappe.format(summary.total_expenses || 0, { fieldtype: "Currency" }))}
            ${metricCard(__("Total Selling"), frappe.format(summary.total_selling || 0, { fieldtype: "Currency" }))}
            ${metricCard(__("Global Margin"), `${Number(summary.global_margin_pct || 0).toFixed(1)}%`)}
        `;

    const tableHead = mode === "Static"
        ? `<tr>
            <th>${__("Item")}</th><th>${__("Qty")}</th><th>${__("Selected List")}</th><th>${__("Selected Price")}</th><th>${__("Line Total")}</th><th>${__("Options")}</th>
        </tr>`
        : `<tr>
            <th>${__("Item")}</th><th>${__("Qty")}</th><th>${__("Scenario")}</th><th>${__("Buy")}</th><th>${__("Benchmark Ref")}</th><th>${__("Ratio")}</th><th>${__("Final Price")}</th><th>${__("Margin %")}</th><th>${__("Source")}</th>
        </tr>`;

    const tableRows = rows.map((row) => (mode === "Static" ? staticRow(row) : dynamicRow(row))).join("") ||
        `<tr><td colspan="9" class="psim-muted">${__("No rows")}</td></tr>`;

    const warningHtml = warnings.length
        ? `<div class="psim-warnings">${warnings.map((w) => `<div>• ${frappe.utils.escape_html(w)}</div>`).join("")}</div>`
        : `<div class="psim-clean">${__("No warnings")}</div>`;

    state.outputWrap.html(`
        <div class="psim-mode">${__("Mode")}: <strong>${frappe.utils.escape_html(mode)}</strong></div>
        <div class="psim-metrics">${cards}</div>
        ${warningHtml}
        <div class="psim-table-wrap">
            <table class="psim-table">
                <thead>${tableHead}</thead>
                <tbody>${tableRows}</tbody>
            </table>
        </div>
    `);
}

function metricCard(label, value) {
    return `<div class="psim-metric"><div class="psim-metric-label">${label}</div><div class="psim-metric-value">${value}</div></div>`;
}

function dynamicRow(row) {
    return `<tr>
        <td>${frappe.utils.escape_html(row.item || "")}</td>
        <td>${frappe.format(row.qty || 0, { fieldtype: "Float" })}</td>
        <td>${frappe.utils.escape_html(row.resolved_pricing_scenario || "-")}</td>
        <td>${frappe.format(row.buy_price || 0, { fieldtype: "Currency" })}</td>
        <td>${row.benchmark_reference ? frappe.format(row.benchmark_reference, { fieldtype: "Currency" }) : "-"}</td>
        <td>${row.benchmark_ratio ? Number(row.benchmark_ratio).toFixed(3) : "-"}</td>
        <td>${frappe.format(row.final_sell_unit_price || 0, { fieldtype: "Currency" })}</td>
        <td>${Number(row.margin_pct || 0).toFixed(1)}%</td>
        <td>${frappe.utils.escape_html(row.margin_source || "-")}</td>
    </tr>`;
}

function staticRow(row) {
    return `<tr>
        <td>${frappe.utils.escape_html(row.item || "")}</td>
        <td>${frappe.format(row.qty || 0, { fieldtype: "Float" })}</td>
        <td>${frappe.utils.escape_html(row.selected_price_list || "-")}</td>
        <td>${frappe.format(row.selected_price || 0, { fieldtype: "Currency" })}</td>
        <td>${frappe.format(row.line_total || 0, { fieldtype: "Currency" })}</td>
        <td>${row.option_count || 0}</td>
    </tr>`;
}

function injectStyles() {
    if (document.getElementById("pricing-simulator-style")) {
        return;
    }

    const style = document.createElement("style");
    style.id = "pricing-simulator-style";
    style.textContent = `
        .psim-root { padding: 0 !important; }
        .psim-controls, .psim-card {
            max-width: 1320px;
            margin: 16px auto;
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 16px;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
        }
        .psim-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
            gap: 10px;
        }
        .psim-actions { margin-top: 12px; display: flex; gap: 8px; }
        .psim-controls .psim-actions { margin-top: 0; }
        .psim-card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .psim-title { font-weight: 700; color: #0f172a; }
        .psim-hint { margin-bottom: 8px; }
        .psim-auto-hint {
            background: #eef2ff;
            color: #3730a3;
            border: 1px solid #c7d2fe;
            border-radius: 8px;
            padding: 8px 10px;
            font-size: 12px;
            font-weight: 600;
        }
        .psim-output { min-height: 90px; }
        .psim-loading { color: #334155; }
        .psim-error { color: #991b1b; font-weight: 600; }
        .psim-mode { margin-bottom: 10px; color: #334155; }
        .psim-metrics {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 10px;
            margin-bottom: 10px;
        }
        .psim-metric {
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 10px;
            background: linear-gradient(135deg, #f8fafc, #eef2ff);
        }
        .psim-metric-label { color: #64748b; font-size: 12px; }
        .psim-metric-value { font-weight: 800; color: #0f172a; margin-top: 4px; }
        .psim-warnings {
            background: #fff7ed;
            color: #9a3412;
            border: 1px solid #fed7aa;
            border-radius: 10px;
            padding: 10px;
            margin-bottom: 10px;
        }
        .psim-clean {
            background: #ecfdf5;
            color: #065f46;
            border: 1px solid #a7f3d0;
            border-radius: 10px;
            padding: 10px;
            margin-bottom: 10px;
        }
        .psim-table-wrap { overflow-x: auto; }
        .psim-table { width: 100%; border-collapse: collapse; font-size: 12px; }
        .psim-table th, .psim-table td { border-bottom: 1px solid #e2e8f0; padding: 8px; white-space: nowrap; }
        .psim-table th { text-transform: uppercase; font-size: 11px; color: #64748b; letter-spacing: .03em; }
        .psim-delta-pos { color: #166534; font-weight: 700; }
        .psim-delta-neg { color: #9a3412; font-weight: 700; }
        .psim-muted { color: #94a3b8; }
        @media (max-width: 900px) {
            .psim-grid { grid-template-columns: 1fr; }
        }
    `;
    document.head.appendChild(style);
}
