frappe.ui.form.on("Pricing Simulator Workbench", {
    refresh(frm) {
        ensureWorkbenchStyles();
        setupWorkbenchQueries(frm);
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
    if (frm.is_new()) await frm.save();
    const response = await frm.call("load_defaults");
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
    await frm.save();
    await runWorkbenchSimulation(frm);
}

async function runWorkbenchSimulation(frm) {
    if (frm.is_new()) return;
    if (frm.__sim_running) return;
    frm.__sim_running = true;
    try {
        await frm.save();
        const response = await frm.call("run_simulation");
        renderWorkbenchResults(frm, response.message || {});
    } catch (e) {
        renderWorkbenchResults(frm, {
            warnings: [e?.message || __("Simulation failed.")],
        });
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
            <div class="pswb-metrics">
                ${metricCard(__("Compared Items"), 0)}
                ${metricCard(__("Avg Dyn Margin"), "0.0%")}
                ${metricCard(__("Static Missing"), 0)}
            </div>
            <div class="pswb-empty">${__("Configure source tables above. Results will refresh automatically when values change.")}</div>
            <div class="pswb-table-wrap"><table class="pswb-table"><thead><tr>
                <th>${__("Item")}</th><th>${__("Material")}</th><th>${__("Buying List")}</th><th>${__("Scenario")}</th><th>${__("Dyn Buy")}</th><th>${__("Dyn Customs")}</th><th>${__("Tier Mod")}</th><th>${__("Territory Mod")}</th><th>${__("Dyn Final")}</th><th>${__("Static List")}</th><th>${__("Static Price")}</th>
            </tr></thead><tbody><tr><td colspan="11">${__("No simulation results yet.")}</td></tr></tbody></table></div>
        `);
        return;
    }
    if (payload.view_mode === "Compare") {
        wrap.html(renderWorkbenchComparison(payload.dynamic || {}, payload.static || {}));
        return;
    }
    wrap.html(renderWorkbenchSingle(payload));
}

function renderWorkbenchComparison(dynamicData, staticData) {
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
    return `
        <div class="pswb-metrics">
            ${metricCard(__("Compared Items"), keys.length)}
            ${metricCard(__("Avg Dyn Margin"), `${Number(dynamicData.summary?.global_margin_pct || 0).toFixed(1)}%`)}
            ${metricCard(__("Static Missing"), staticData.summary?.missing_items || 0)}
        </div>
        ${renderWorkbenchWarnings([...(dynamicData.warnings || []).map((w) => `[Dynamic] ${w}`), ...(staticData.warnings || []).map((w) => `[Static] ${w}`)])}
        <div class="pswb-table-wrap"><table class="pswb-table"><thead><tr>
            <th>${__("Item")}</th><th>${__("Material")}</th><th>${__("Buying List")}</th><th>${__("Scenario")}</th><th>${__("Dyn Buy")}</th><th>${__("Dyn Customs")}</th><th>${__("Tier Mod")}</th><th>${__("Territory Mod")}</th><th>${__("Dyn Final")}</th><th>${__("Static List")}</th><th>${__("Static Price")}</th>
        </tr></thead><tbody>${rows || `<tr><td colspan="11">${__("No comparable items.")}</td></tr>`}</tbody></table></div>
    `;
}

function renderWorkbenchSingle(data) {
    const mode = data.pricing_mode || data.mode || "Dynamic";
    if (mode === "Static") {
        const rows = (data.rows || []).map((row) => `
            <tr>
                <td>${linkToDoc("Item", row.item)}</td>
                <td>${escapeHtml(row.material || "-")}</td>
                <td>${escapeHtml(row.selected_price_list || "-")}</td>
                <td><strong>${fmtCurrency(row.selected_price)}</strong></td>
                <td>${row.option_count || 0}</td>
            </tr>
        `).join("");
        return `
            <div class="pswb-metrics">
                ${metricCard(__("Priced"), data.summary?.priced_items || 0)}
                ${metricCard(__("Missing"), data.summary?.missing_items || 0)}
                ${metricCard(__("Loaded Lists"), data.summary?.selling_lists_count || 0)}
            </div>
            ${renderWorkbenchWarnings(data.warnings || [])}
            <div class="pswb-table-wrap"><table class="pswb-table"><thead><tr><th>${__("Item")}</th><th>${__("Material")}</th><th>${__("List")}</th><th>${__("Price")}</th><th>${__("Options")}</th></tr></thead><tbody>${rows || `<tr><td colspan="5">${__("No static rows.")}</td></tr>`}</tbody></table></div>
        `;
    }

    const rows = (data.rows || []).map((row) => `
        <tr>
            <td>${linkToDoc("Item", row.item)}</td>
            <td>${escapeHtml(row.material || "-")}</td>
            <td>${escapeHtml(row.source_buying_price_list || "-")}</td>
            <td>${escapeHtml(row.resolved_pricing_scenario || "-")}</td>
            <td>${fmtCurrency(row.buy_price)}</td>
            <td>${fmtCurrency(row.customs_applied)}</td>
            <td>${fmtCurrency(row.tier_modifier_amount)}</td>
            <td>${fmtCurrency(row.zone_modifier_amount)}</td>
            <td>${fmtCurrency(row.benchmark_reference)}</td>
            <td><strong>${fmtCurrency(row.final_sell_unit_price)}</strong></td>
            <td>${Number(row.margin_pct || 0).toFixed(1)}%</td>
            <td>${escapeHtml(row.applied_benchmark_policy || "-")}</td>
        </tr>
    `).join("");
    return `
        <div class="pswb-metrics">
            ${metricCard(__("Simulated Items"), data.summary?.item_count || (data.rows || []).length)}
            ${metricCard(__("Policies"), data.summary?.policy_count || 0)}
            ${metricCard(__("Global Margin"), `${Number(data.summary?.global_margin_pct || 0).toFixed(1)}%`)}
        </div>
        ${renderWorkbenchWarnings(data.warnings || [])}
        <div class="pswb-table-wrap"><table class="pswb-table"><thead><tr><th>${__("Item")}</th><th>${__("Material")}</th><th>${__("Buying List")}</th><th>${__("Scenario")}</th><th>${__("Buy")}</th><th>${__("Customs")}</th><th>${__("Tier Mod")}</th><th>${__("Territory Mod")}</th><th>${__("Bench Ref")}</th><th>${__("Final")}</th><th>${__("Margin")}</th><th>${__("Policy")}</th></tr></thead><tbody>${rows || `<tr><td colspan="12">${__("No dynamic rows.")}</td></tr>`}</tbody></table></div>
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
        .pswb-metric{padding:12px 14px;border-radius:12px;background:#fff;border:1px solid #e2e8f0}
        .pswb-metric span{display:block;font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:#64748b;margin-bottom:6px}
        .pswb-metric strong{font-size:20px;color:#0f172a}
        .pswb-table-wrap{overflow:auto;border:1px solid #e2e8f0;border-radius:12px;background:#fff}
        .pswb-table{width:100%;border-collapse:collapse;font-size:12px}
        .pswb-table th,.pswb-table td{padding:8px;border-bottom:1px solid #f1f5f9;white-space:nowrap}
        .pswb-table th{background:#f8fafc;color:#64748b;text-transform:uppercase;letter-spacing:.05em;font-size:10px}
        @media (max-width:900px){.pswb-metrics{grid-template-columns:1fr}}
    `;
    document.head.appendChild(style);
}
