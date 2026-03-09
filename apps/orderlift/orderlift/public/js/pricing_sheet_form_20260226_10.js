function statusBadge(value) {
    const status = value || "";
    const map = {
        OK: "green",
        "Too Low": "orange",
        "Too High": "red",
        "No Benchmark": "gray",
    };
    const color = map[status] || "blue";
    return `<span class="indicator-pill ${color}">${__(status || "-")}</span>`;
}

function marginSourceBadge(value) {
    const src = value || "";
    const map = {
        "Benchmark & Rule": "green",
        "Pricing Rule": "yellow",
        Fallback: "red",
    };
    const color = map[src] || "gray";
    return `<span class="indicator-pill ${color}">${__(src || "-")}</span>`;
}

function isRestrictedAgentUser() {
    const roles = frappe.user_roles || [];
    const isCommercial = roles.includes("Orderlift Commercial");
    const isPrivileged = ["Orderlift Admin", "Sales Manager", "System Manager"].some((role) => roles.includes(role));
    return isCommercial && !isPrivileged;
}

function setGridFieldVisibility(grid, fieldnames, hidden) {
    if (!grid) return;
    fieldnames.forEach((fieldname) => {
        grid.update_docfield_property(fieldname, "hidden", hidden ? 1 : 0);
    });
    grid.refresh();
}

function ensurePricingSheetStyles(frm) {
    const linkId = "pricing-sheet-ux-css";
    const version = "v=20260307-02";
    let link = document.getElementById(linkId);
    if (!link) {
        link = document.createElement("link");
        link.id = linkId;
        link.rel = "stylesheet";
        document.head.appendChild(link);
    }
    const expected = `/assets/orderlift/css/pricing_sheet_20260226_10.css?${version}`;
    if (link.href !== expected) link.href = expected;
}

function renderContextActions(frm) {
    const restrictedAgent = isRestrictedAgentUser();
    const mount = (fieldname, title, actions) => {
        const field = frm.fields_dict[fieldname];
        if (!field || !field.$wrapper) return;

        const id = `ps-actions-${fieldname}`;
        field.$wrapper.prev(`#${id}`).remove();

        const $bar = $(`<div id="${id}" class="ps-actions"><div class="ps-actions-title">${title}</div></div>`);
        actions.forEach((action) => {
            const $btn = $(`<button class="btn btn-default btn-sm">${action.label}</button>`);
            $btn.on("click", async () => {
                try {
                    await action.handler();
                } catch (e) {
                    frappe.msgprint({
                        title: __("Action Failed"),
                        message: e.message || __("Unable to execute action."),
                        indicator: "red",
                    });
                }
            });
            $bar.append($btn);
        });

        field.$wrapper.before($bar);
    };

    // Override count badges on collapsed section labels
    const badgeSections = [
        { field: "scenario_overrides", rows: frm.doc.scenario_overrides || [] },
        { field: "line_overrides", rows: frm.doc.line_overrides || [] },
        { field: "bundle_scenario_rules", rows: frm.doc.bundle_scenario_rules || [] },
    ];
    badgeSections.forEach(({ field, rows }) => {
        const f = frm.fields_dict[field];
        if (!f) return;
        const $head = f.$wrapper.closest(".form-section").find(".section-head");
        $head.find(".ps-override-badge").remove();
        if (rows.length > 0) {
            $head.append(`<span class="ps-override-badge">${rows.length}</span>`);
        }
    });

    const lineActions = [
        {
            label: __("↻ Recalculate"),
            handler: async () => {
                try {
                    await frm.save();
                    frm.refresh_field("lines");
                    renderProjectionDashboard(frm);
                    frappe.show_alert({ message: __("Pricing recalculated"), indicator: "green" });
                } catch (e) {
                    frappe.msgprint({ title: __("Recalculation Failed"), message: __("Could not recalculate."), indicator: "red" });
                }
            },
        },
    ];

    if (!restrictedAgent) {
        lineActions.push(
            {
                label: __("Refresh Base Prices"),
                handler: async () => {
                    if (frm.is_dirty()) await frm.save();
                    await frm.call("refresh_buy_prices");
                    await frm.reload_doc();
                    renderProjectionDashboard(frm);
                    frappe.show_alert({ message: __("Base prices refreshed"), indicator: "green" });
                },
            },
            {
                label: __("Apply Expenses Policy to Rows"),
                handler: async () => {
                    const dialog = new frappe.ui.Dialog({
                        title: __("Apply Expenses Policy"),
                        fields: [
                            {
                                fieldtype: "Link",
                                fieldname: "pricing_scenario",
                                label: __("Expenses Policy"),
                                options: "Pricing Scenario",
                                reqd: 1,
                            },
                        ],
                        primary_action_label: __("Apply"),
                        primary_action: async (values) => {
                            const selected = frm.fields_dict.lines.grid.get_selected_children() || [];
                            const targets = selected.length ? selected : frm.doc.lines || [];
                            targets.forEach((row) => {
                                frappe.model.set_value(row.doctype, row.name, "pricing_scenario", values.pricing_scenario);
                            });
                            dialog.hide();
                            await frm.save();
                            renderProjectionDashboard(frm);
                        },
                    });
                    dialog.show();
                },
            }
        );
    }

    mount("lines", __("Pricing Sheet Actions"), lineActions);

    if (restrictedAgent) {
        return;
    }

    mount("scenario_overrides", __("Scenario Override Actions"), [

        {
            label: __("Load Scenario Values"),
            handler: async () => {
                if (frm.is_dirty()) await frm.save();
                await frm.call("load_scenario_overrides");
                await frm.reload_doc();
                renderProjectionDashboard(frm);
                frappe.show_alert({ message: __("Scenario values loaded"), indicator: "green" });
            },
        },
        {
            label: __("Reset Scenario Overrides"),
            handler: async () => {
                if (frm.is_dirty()) await frm.save();
                await frm.call("reset_scenario_overrides");
                await frm.reload_doc();
                renderProjectionDashboard(frm);
                frappe.show_alert({ message: __("Scenario overrides reset"), indicator: "green" });
            },
        },
        {
            label: __("Prune Stale Overrides"),
            handler: async () => {
                if (frm.is_dirty()) await frm.save();
                await frm.call("prune_stale_scenario_overrides");
                await frm.reload_doc();
                renderProjectionDashboard(frm);
                frappe.show_alert({ message: __("Stale overrides pruned"), indicator: "green" });
            },
        },
    ]);

    mount("line_overrides", __("Line Override Actions"), [
        {
            label: __("Load Line Overrides"),
            handler: async () => {
                if (frm.is_dirty()) await frm.save();
                await frm.call("load_line_overrides");
                await frm.reload_doc();
                renderProjectionDashboard(frm);
                frappe.show_alert({ message: __("Line overrides loaded"), indicator: "green" });
            },
        },
        {
            label: __("Reset Line Overrides"),
            handler: async () => {
                if (frm.is_dirty()) await frm.save();
                await frm.call("reset_line_overrides");
                await frm.reload_doc();
                renderProjectionDashboard(frm);
                frappe.show_alert({ message: __("Line overrides reset"), indicator: "green" });
            },
        },
        {
            label: __("Prune Stale Line Overrides"),
            handler: async () => {
                if (frm.is_dirty()) await frm.save();
                await frm.call("prune_stale_line_overrides");
                await frm.reload_doc();
                renderProjectionDashboard(frm);
                frappe.show_alert({ message: __("Stale line overrides pruned"), indicator: "green" });
            },
        },
    ]);
}

function applyFormLayoutClass(frm) {
    if (!frm || !frm.page || !frm.page.wrapper) return;

    frm.page.wrapper.addClass("pricing-sheet-page");
    frm.$wrapper && frm.$wrapper.addClass("pricing-sheet-form-root");

    const $mainSection = frm.$wrapper ? frm.$wrapper.closest(".layout-main-section") : null;
    if ($mainSection && $mainSection.length) {
        $mainSection.addClass("pricing-sheet-main-section");
        const $mainWrapper = $mainSection.closest(".layout-main-section-wrapper");
        if ($mainWrapper && $mainWrapper.length) {
            $mainWrapper.addClass("pricing-sheet-main-wrapper");
        }
    }
}

function applyModeLayout(frm) {
    const mode = frm.doc.resolved_mode || "";
    const isStatic = mode === "Static";
    const restrictedAgent = isRestrictedAgentUser();

    // Mode indicator badge in page subtitle area
    frm.page.wrapper.find(".ps-mode-badge").remove();
    const badgeColor = isStatic ? "#6366f1" : "#16a34a";
    const badgeLabel = isStatic ? "📋 Static" : "⚙ Dynamic";
    frm.page.wrapper.find(".page-form.flex-between, .page-head .page-title").first()
        .append(`<span class="ps-mode-badge" style="background:${badgeColor};color:#fff;border-radius:20px;padding:2px 12px;font-size:11px;font-weight:700;margin-left:10px;display:inline-block;vertical-align:middle;">${badgeLabel}</span>`);

    // Dynamic-only fields — visible only in dynamic mode
    const dynamicFields = ["benchmark_policy", "customs_policy",
        "pricing_scenario", "minimum_margin_percent", "strict_margin_guard",
        "product_bundle"];
    // Static-only fields
    const staticFields = ["selected_price_list"];

    dynamicFields.forEach(fn => frm.toggle_display(fn, !isStatic));
    staticFields.forEach(fn => frm.toggle_display(fn, isStatic));

    if (restrictedAgent) {
        [
            "pricing_scenario", "benchmark_policy", "customs_policy", "selected_price_list",
            "minimum_margin_percent", "strict_margin_guard", "product_bundle", "scenario_mappings",
            "heading_bundle_rules", "bundle_scenario_rules", "heading_scenario_overrides", "scenario_overrides",
            "heading_line_overrides", "line_overrides", "section_runtime", "total_buy", "total_expenses",
            "applied_customs_policy", "applied_benchmark_policy", "customs_total_applied",
        ].forEach((fieldname) => frm.toggle_display(fieldname, false));
    }

    const linesGrid = frm.fields_dict.lines && frm.fields_dict.lines.grid;
    if (linesGrid) {
        setGridFieldVisibility(linesGrid, [
            "source_buying_price_list", "pricing_scenario", "resolved_pricing_scenario", "resolved_scenario_rule",
            "resolved_margin_rule", "scenario_source", "has_scenario_override", "has_line_override", "buy_price",
            "buy_price_missing", "buy_price_message", "base_amount", "expense_unit_price", "expense_total",
            "projected_unit_price", "projected_total_price", "manual_sell_unit_price", "margin_pct",
            "customs_material", "customs_weight_kg", "customs_rate_per_kg", "customs_rate_percent",
            "customs_by_kg", "customs_by_percent", "customs_applied", "customs_basis",
            "transport_allocation_mode", "transport_container_type", "transport_basis_total", "transport_numerator",
            "transport_allocated", "price_floor_violation", "benchmark_price", "benchmark_delta_abs",
            "benchmark_delta_pct", "benchmark_status", "benchmark_note", "benchmark_reference",
            "benchmark_source_count", "benchmark_ratio", "benchmark_method", "resolved_benchmark_rule",
            "margin_source", "tier_modifier_amount", "zone_modifier_amount", "pricing_breakdown_json",
            "breakdown_preview", "static_list_price"
        ], restrictedAgent);
    }

    // Collapse override sections in static mode (not relevant)
    if (isStatic || restrictedAgent) {
        const sectionFieldnames = [
            "heading_bundle_rules",
            "heading_scenario_overrides",
            "heading_line_overrides",
            "section_runtime",
        ];
        const sections = (frm.layout && frm.layout.sections) || [];
        sectionFieldnames.forEach(fieldname => {
            const section = sections.find(s => s.df && s.df.fieldname === fieldname);
            if (section && typeof section.collapse === "function") section.collapse();
        });
    }
}


function applyDashboardSectionClass(frm) {
    const field = frm.fields_dict.projection_dashboard;
    if (!field || !field.$wrapper) return;

    const $section = field.$wrapper.closest(".form-section");
    if ($section && $section.length) {
        $section.addClass("ps-dashboard-section");
    }
}

function collapseAdvancedSections(frm) {
    const sectionFieldnames = [
        "heading_bundle_rules",
        "heading_scenario_overrides",
        "heading_line_overrides",
        "section_runtime",
    ];

    const sections = (frm.layout && frm.layout.sections) || [];
    sectionFieldnames.forEach((fieldname) => {
        const section = sections.find((entry) => entry.df && entry.df.fieldname === fieldname);
        if (!section) {
            return;
        }

        if (typeof section.collapse === "function") {
            section.collapse();
        }
    });
}

// ── Dashboard helpers ─────────────────────────────────────────────────────────

function psMarginBadge(pct) {
    const v = Number(pct || 0);
    const cls = v >= 20 ? "ps-mgn-good" : v >= 10 ? "ps-mgn-mid" : "ps-mgn-bad";
    return `<span class="${cls}">${v.toFixed(1)}%</span>`;
}

function psDashLink(doctype, name, label) {
    if (!name) return frappe.utils.escape_html(label || "—");
    const url = `/app/${frappe.router.slug(doctype)}/${encodeURIComponent(name)}`;
    return `<a href="${url}" class="ps-item-link" target="_blank" title="Open ${frappe.utils.escape_html(name)}">${frappe.utils.escape_html(label || name)}</a>`;
}

function psSmartWarnings(raw) {
    if (!raw || !raw.trim()) return `<div class="ps-warn-clean">✓ No warnings</div>`;

    const INFO_RE = /auto-loaded|filtered out/i;
    const BENCH_RE = /Only\s+\d+ benchmark source\(s\) for (.+?);/i;
    const infoLines = [], configLines = [];
    const benchItems = {};

    for (const line of raw.split("\n")) {
        const msg = line.replace(/^\[(Dynamic|Static)\]\s*/i, "").trim();
        if (!msg) continue;
        const bm = msg.match(BENCH_RE);
        if (bm) { (benchItems[bm[1]] = benchItems[bm[1]] || true); continue; }
        if (INFO_RE.test(msg)) infoLines.push(msg);
        else configLines.push(msg);
    }
    const bCount = Object.keys(benchItems).length;
    if (bCount) configLines.push(`${bCount} item(s) have no benchmark sources — comparison disabled`);

    let html = "";
    if (infoLines.length)
        html += `<div class="ps-warn-info">ℹ ${infoLines.map((l) => frappe.utils.escape_html(l)).join(" · ")}</div>`;
    if (configLines.length) {
        const rows = configLines.map((w) => `<div>• ${frappe.utils.escape_html(w)}</div>`).join("");
        html += `<details class="ps-warn-block"><summary class="ps-warn-summary">⚠ ${configLines.length} warning(s)</summary><div class="ps-warn-body">${rows}</div></details>`;
    }
    return html || `<div class="ps-warn-clean">✓ No warnings</div>`;
}

function aggregateExpenseImpact(lines) {
    const totals = {};
    (lines || []).forEach((row) => {
        if (!row.pricing_breakdown_json) {
            return;
        }
        try {
            const steps = JSON.parse(row.pricing_breakdown_json || "[]");
            steps.forEach((step) => {
                const label = step.label || __("Component");
                const lineDelta = (step.delta_unit || 0) * (row.qty || 0) + (step.delta_line || 0) + (step.delta_sheet || 0);
                totals[label] = (totals[label] || 0) + lineDelta;
            });
        } catch (e) {
            // ignore malformed breakdown rows
        }
    });
    return Object.entries(totals).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
}

function showBreakdownDialog(row) {
    const title = `${__("Expense Breakdown")} - ${row.item || "-"}`;
    const steps = JSON.parse(row.pricing_breakdown_json || "[]");
    const rows =
        steps
            .map(
                (step) => `
        <tr>
            <td>${frappe.utils.escape_html(step.label || "-")}</td>
            <td>${frappe.utils.escape_html(step.type || "-")}</td>
            <td>${frappe.utils.escape_html(step.scope || "Per Unit")}</td>
            <td style="text-align:right;">${frappe.format(step.basis || 0, { fieldtype: "Currency" })}</td>
            <td style="text-align:right;">${frappe.format((step.delta_unit || 0) + (step.delta_line || 0), {
                    fieldtype: "Currency",
                })}</td>
            <td style="text-align:right;">${frappe.format(step.running_total || 0, { fieldtype: "Currency" })}</td>
        </tr>
    `
            )
            .join("") || `<tr><td colspan="6">${__("No breakdown")}</td></tr>`;

    const dialog = new frappe.ui.Dialog({
        title,
        fields: [
            {
                fieldname: "html",
                fieldtype: "HTML",
                options: `
                    <div style="max-height:420px;overflow:auto;">
                        <table style="width:100%;border-collapse:collapse;">
                            <thead>
                                <tr>
                                    <th style="text-align:left;">${__("Label")}</th>
                                    <th style="text-align:left;">${__("Type")}</th>
                                    <th style="text-align:left;">${__("Scope")}</th>
                                    <th style="text-align:right;">${__("Basis")}</th>
                                    <th style="text-align:right;">${__("Delta")}</th>
                                    <th style="text-align:right;">${__("Running")}</th>
                                </tr>
                            </thead>
                            <tbody>${rows}</tbody>
                        </table>
                    </div>
                `,
            },
        ],
        primary_action_label: __("Close"),
        primary_action: () => dialog.hide(),
    });
    dialog.show();
}

function renderProjectionDashboard(frm) {
    if (!frm.fields_dict.projection_dashboard) {
        return;
    }

    const lines = frm.doc.lines || [];
    const totalBase = frm.doc.total_buy || 0;
    const totalExpenses = frm.doc.total_expenses || 0;
    const totalFinal = frm.doc.total_selling || 0;
    const avgMarkup = totalBase > 0 ? (totalFinal / totalBase - 1) * 100 : 0;
    const warnings = frm.doc.projection_warnings || "";
    const restrictedAgent = isRestrictedAgentUser();
    const pricingPolicy = frm.doc.applied_benchmark_policy || frm.doc.benchmark_policy || "";
    const customsPolicy = frm.doc.applied_customs_policy || frm.doc.customs_policy || "";
    const customsTotalApplied = frm.doc.customs_total_applied || 0;
    const salesPerson = frm.doc.sales_person || "";
    const geography = frm.doc.geography_territory || "";

    const scenarioCounts = {};
    lines.forEach((row) => {
        const key = row.resolved_pricing_scenario || row.pricing_scenario || frm.doc.pricing_scenario || "Unresolved";
        scenarioCounts[key] = (scenarioCounts[key] || 0) + 1;
    });
    const scenarioPills = Object.entries(scenarioCounts)
        .map(([name, count]) =>
            `<a href="/app/pricing-scenario/${encodeURIComponent(name)}" target="_blank" class="ps-scenario-chip" title="Open ${frappe.utils.escape_html(name)}">${frappe.utils.escape_html(name)}<strong>${count}</strong></a>`
        ).join("");

    const rowsHtml = lines
        .map((row, index) => {
            const itemCell = psDashLink("Item", row.item, row.item);
            const scnCell = psDashLink("Pricing Scenario", row.resolved_pricing_scenario || row.pricing_scenario, row.resolved_pricing_scenario || row.pricing_scenario || "—");
            const scnOverride = row.has_scenario_override ? `<span class="indicator-pill orange ps-ovr-pill">${__("Edited")}</span>` : "";
            const floor = row.price_floor_violation ? `<span class="indicator-pill red ps-ovr-pill">${__("Floor")}</span>` : "";
            const preview = frappe.utils.escape_html(row.breakdown_preview || __("No expenses"));
            if (restrictedAgent) {
                return `
                    <tr>
                        <td>${itemCell}</td>
                        <td style="text-align:right;">${frappe.format(row.qty || 0, { fieldtype: "Float" })}</td>
                        <td style="text-align:right;"><strong>${frappe.format(row.final_sell_unit_price || 0, { fieldtype: "Currency" })}</strong></td>
                        <td style="text-align:right;">${frappe.format(row.final_sell_total || 0, { fieldtype: "Currency" })}</td>
                    </tr>
                `;
            }
            return `
                <tr>
                    <td>${itemCell}</td>
                    <td>${scnCell} ${scnOverride}</td>
                    <td style="text-align:right;">${frappe.format(row.qty || 0, { fieldtype: "Float" })}</td>
                    <td style="text-align:right;">${frappe.format(row.buy_price || 0, { fieldtype: "Currency" })}</td>
                    <td style="text-align:right;">${frappe.format(row.expense_unit_price || 0, { fieldtype: "Currency" })}</td>
                    <td style="text-align:right;">${frappe.format(row.expense_total || 0, { fieldtype: "Currency" })}</td>
                    <td style="text-align:right;">${frappe.format(row.projected_unit_price || 0, { fieldtype: "Currency" })}</td>
                    <td style="text-align:right;"><strong>${frappe.format(row.final_sell_unit_price || 0, { fieldtype: "Currency" })}</strong></td>
                    <td>${psMarginBadge(row.margin_pct)}</td>
                    <td>${floor}</td>
                    <td>${preview}</td>
                    <td style="text-align:right;"><button class="btn btn-xs btn-default" data-breakdown-index="${index}">${__("View")}</button></td>
                </tr>
            `;
        }).join("") ||
        `<tr><td colspan="${restrictedAgent ? 4 : 12}" style="color:#64748b;">${__("No pricing lines yet.")}</td></tr>`;

    const impacts = aggregateExpenseImpact(lines)
        .slice(0, 6)
        .map(
            ([label, value]) =>
                `<tr><td>${frappe.utils.escape_html(label)}</td><td style="text-align:right;">${frappe.format(value, {
                    fieldtype: "Currency",
                })}</td></tr>`
        )
        .join("");

    const customsRows =
        lines
            .map((row) => {
                const material = frappe.utils.escape_html(row.customs_material || "-");
                const basis = frappe.utils.escape_html(row.customs_basis || "-");
                return `
                    <tr>
                        <td>${frappe.utils.escape_html(row.item || "-")}</td>
                        <td>${material}</td>
                        <td style="text-align:right;">${frappe.format(row.customs_weight_kg || 0, { fieldtype: "Float" })}</td>
                        <td style="text-align:right;">${frappe.format(row.qty || 0, { fieldtype: "Float" })}</td>
                        <td style="text-align:right;">${frappe.format(row.base_amount || 0, { fieldtype: "Currency" })}</td>
                        <td style="text-align:right;">${frappe.format(row.customs_by_kg || 0, { fieldtype: "Currency" })}</td>
                        <td style="text-align:right;">${frappe.format(row.customs_by_percent || 0, { fieldtype: "Currency" })}</td>
                        <td style="text-align:right;font-weight:700;">${frappe.format(row.customs_applied || 0, {
                    fieldtype: "Currency",
                })}</td>
                        <td>${basis}</td>
                    </tr>
                `;
            })
            .join("") || `<tr><td colspan="9" style="padding:8px;color:#64748b;">${__("No customs data")}</td></tr>`;

    const warningBlock = psSmartWarnings(warnings);

    ensurePricingSheetStyles(frm);

    const isStatic = (frm.doc.resolved_mode === "Static");
    const dashId = `ps-dash-${frm.doc.name || "new"}`.replace(/[^a-z0-9-]/gi, "_");

    const html = `
    <div class="ps-shell" id="${dashId}">

        <!-- KPI strip -->
        <div class="ps-kpi-grid ps-kpi-strip">
            ${!restrictedAgent ? `<div class="ps-kpi ps-kpi--base">
                <div class="ps-kpi-label">📦 ${isStatic ? __("Buy Price (Info)") : __("Total Base")}</div>
                <div class="ps-kpi-value">${frappe.format(totalBase, { fieldtype: "Currency" })}</div>
            </div>` : ""}
            ${!isStatic && !restrictedAgent ? `<div class="ps-kpi ps-kpi--exp">
                <div class="ps-kpi-label">⚙ ${__("Expenses")}</div>
                <div class="ps-kpi-value">${frappe.format(totalExpenses, { fieldtype: "Currency" })}</div>
            </div>` : isStatic ? `<div class="ps-kpi ps-kpi--margin" style="background:#ede9fe;">
                <div class="ps-kpi-label">📋 ${__("Price List")}</div>
                <div class="ps-kpi-value" style="font-size:13px;color:#4f46e5;">${frappe.utils.escape_html(frm.doc.selected_price_list || "—")}</div>
            </div>` : ""}
            <div class="ps-kpi ps-kpi--final">
                <div class="ps-kpi-label">💰 ${__("Total Final")}</div>
                <div class="ps-kpi-value">${frappe.format(totalFinal, { fieldtype: "Currency" })}</div>
            </div>
            <div class="ps-kpi ps-kpi--margin">
                <div class="ps-kpi-label">📈 ${__("Avg Markup")}</div>
                <div class="ps-kpi-value">${Number(avgMarkup).toFixed(1)}%</div>
            </div>
        </div>

        <!-- Tab bar -->
        <div class="ps-dash-tabs">
            <button class="ps-dash-tab ps-dash-tab--active" data-tab="overview" data-dash="${dashId}">
                🧭 ${__("Overview")}
            </button>
            <button class="ps-dash-tab" data-tab="lines" data-dash="${dashId}">
                📋 ${__("Lines")} <span class="ps-preview-count">${lines.length}</span>
            </button>
            ${!isStatic && !restrictedAgent ? `
            <button class="ps-dash-tab" data-tab="adjustments" data-dash="${dashId}">
                🔧 ${__("Adjustments")}
            </button>
            <button class="ps-dash-tab" data-tab="customs" data-dash="${dashId}">
                🛃 ${__("Customs")}
            </button>` : ""}
        </div>

        <!-- Tab: Overview -->
        <div class="ps-dash-panel ps-dash-panel--active" data-panel="overview" data-dash="${dashId}">
            <!-- Scenario pills -->
            <div class="ps-chip-row">
                ${restrictedAgent ? `<span class="ps-scenario-chip" style="color:#64748b;">${__("Pricing configuration applied automatically")}</span>` : (scenarioPills || `<span class="ps-scenario-chip" style="color:#64748b;">${__("No resolved scenario")}</span>`)}
            </div>
            <!-- Policy context -->
            <div class="ps-chip-row">
                <span class="ps-scenario-chip"><span class="ps-chip-key">👤</span> ${frappe.utils.escape_html(salesPerson || "—")}</span>
                <span class="ps-scenario-chip"><span class="ps-chip-key">🌍</span> ${frappe.utils.escape_html(geography || "—")}</span>
                ${!restrictedAgent && pricingPolicy ? `<a href="/app/pricing-benchmark-policy/${encodeURIComponent(pricingPolicy)}"  target="_blank" class="ps-scenario-chip ps-chip-link"><span class="ps-chip-key">🎯</span> ${frappe.utils.escape_html(pricingPolicy)}</a>` : ""}
                ${!restrictedAgent && customsPolicy ? `<a href="/app/pricing-customs-policy/${encodeURIComponent(customsPolicy)}"   target="_blank" class="ps-scenario-chip ps-chip-link"><span class="ps-chip-key">🛃</span> ${frappe.utils.escape_html(customsPolicy)}</a>` : ""}
                ${!restrictedAgent ? `<span class="ps-scenario-chip"><span class="ps-chip-key">💵</span> ${frappe.format(customsTotalApplied, { fieldtype: "Currency" })}</span>` : ""}
            </div>
            <!-- Warnings -->
            ${warningBlock}
        </div>

        <!-- Tab: Lines -->
        <div class="ps-dash-panel" data-panel="lines" data-dash="${dashId}">
            <div class="ps-preview-scroll">
                <table class="ps-table">
                    <thead>
                        <tr>
                            <th>${__("Item")}</th>
                            ${restrictedAgent ? `
                            <th style="text-align:right;">${__("Qty")}</th>
                            <th style="text-align:right;">${__("Final Unit")}</th>
                            <th style="text-align:right;">${__("Final Total")}</th>
                            ` : `
                            <th>${__("Expenses Policy")}</th>
                            <th style="text-align:right;">${__("Qty")}</th>
                            <th style="text-align:right;">${__("Base")}</th>
                            <th style="text-align:right;">${__("Exp/Unit")}</th>
                            <th style="text-align:right;">${__("Exp Total")}</th>
                            <th style="text-align:right;">${__("Projected")}</th>
                            <th style="text-align:right;">${__("Final")}</th>
                            <th>${__("Margin")}</th>
                            <th>${__("Flags")}</th>
                            <th>${__("Expense Flow")}</th>
                            <th style="text-align:right;">${__("Detail")}</th>
                            `}
                        </tr>
                    </thead>
                    <tbody>${rowsHtml}</tbody>
                </table>
            </div>
        </div>

        <!-- Tab: Adjustments -->
        <div class="ps-dash-panel" data-panel="adjustments" data-dash="${dashId}">
            <table class="ps-table">
                <thead><tr>
                    <th>${__("Component")}</th>
                    <th style="text-align:right;">${__("Total Impact")}</th>
                </tr></thead>
                <tbody>${impacts || `<tr><td colspan="2" style="padding:12px;color:#64748b;text-align:center;">${__("No adjustment data yet — run Recalculate.")}</td></tr>`}</tbody>
            </table>
        </div>

        <!-- Tab: Customs -->
        <div class="ps-dash-panel" data-panel="customs" data-dash="${dashId}">
            <div class="ps-preview-scroll">
                <table class="ps-table">
                    <thead><tr>
                        <th>${__("Item")}</th>
                        <th>${__("Material")}</th>
                        <th style="text-align:right;">${__("W (kg)")}</th>
                        <th style="text-align:right;">${__("Qty")}</th>
                        <th style="text-align:right;">${__("Base")}</th>
                        <th style="text-align:right;">${__("By Kg")}</th>
                        <th style="text-align:right;">${__("By %")}</th>
                        <th style="text-align:right;">${__("Max")}</th>
                        <th>${__("Basis")}</th>
                    </tr></thead>
                    <tbody>${customsRows}</tbody>
                </table>
            </div>
        </div>

    </div>
    `;

    frm.fields_dict.projection_dashboard.$wrapper.html(html);

    // Tab switching — scoped to this dashId
    frm.fields_dict.projection_dashboard.$wrapper.find(".ps-dash-tab").on("click", function () {
        const tab = $(this).data("tab");
        const root = frm.fields_dict.projection_dashboard.$wrapper.find(`#${dashId}`);
        root.find(".ps-dash-tab").removeClass("ps-dash-tab--active");
        root.find(".ps-dash-panel").removeClass("ps-dash-panel--active");
        $(this).addClass("ps-dash-tab--active");
        root.find(`[data-panel="${tab}"]`).addClass("ps-dash-panel--active");
    });

    // Breakdown detail button
    frm.fields_dict.projection_dashboard.$wrapper.find("[data-breakdown-index]").on("click", function () {
        const i = Number($(this).attr("data-breakdown-index"));
        const row = lines[i];
        if (row) showBreakdownDialog(row);
    });
}


async function openQuotationPreview(frm) {
    const preview = await frm.call("get_quotation_preview");
    const data = preview.message || {};
    const details = `
        ${__("Total Base")}: ${frappe.format(data.total_buy || 0, { fieldtype: "Currency" })}<br>
        ${__("Total Final")}: ${frappe.format(data.total_final || 0, { fieldtype: "Currency" })}<br>
        ${__("Customs Total")}: ${frappe.format(data.customs_total || 0, { fieldtype: "Currency" })}<br>
        ${__("Lines")}: ${data.line_count || 0}<br>
        ${__("Detailed Rows")}: ${data.detailed_count || 0}<br>
        ${__("Grouped Rows")}: ${data.grouped_count || 0}
    `;
    const warnings = data.warnings ? `<pre style="white-space:pre-wrap;">${frappe.utils.escape_html(data.warnings)}</pre>` : "";

    return new Promise((resolve) => {
        const dialog = new frappe.ui.Dialog({
            title: __("Quotation Preview"),
            fields: [{ fieldname: "html", fieldtype: "HTML", options: `<div>${details}${warnings}</div>` }],
            primary_action_label: __("Generate"),
            primary_action: () => {
                dialog.hide();
                resolve(true);
            },
            secondary_action_label: __("Cancel"),
            secondary_action: () => {
                dialog.hide();
                resolve(false);
            },
        });
        dialog.show();
    });
}

function setAgentPolicyQueries(frm, context) {
    const isDynamic = (context || {}).pricing_mode === "Dynamic Calculation Engine";
    const scenarios = (context || {}).allowed_pricing_scenarios || [];
    const benchmarks = (context || {}).allowed_benchmark_policies || [];
    const customs = (context || {}).allowed_customs_policies || [];

    frm.set_query("pricing_scenario", "lines", () => ({ filters: {} }));
    frm.set_query("source_buying_price_list", "scenario_mappings", () => ({ filters: { buying: 1 } }));
    frm.set_query("pricing_scenario", () => {
        if (isDynamic && scenarios.length) {
            return { filters: { name: ["in", scenarios] } };
        }
        return { filters: {} };
    });
    frm.set_query("pricing_scenario", "scenario_mappings", () => {
        if (isDynamic && scenarios.length) {
            return { filters: { name: ["in", scenarios] } };
        }
        return { filters: {} };
    });

    frm.set_query("benchmark_policy", () => {
        if (isDynamic && benchmarks.length) {
            return { filters: { is_active: 1, name: ["in", benchmarks] } };
        }
        return { filters: { is_active: 1 } };
    });
    frm.set_query("benchmark_policy", "scenario_mappings", () => {
        if (isDynamic && benchmarks.length) {
            return { filters: { is_active: 1, name: ["in", benchmarks] } };
        }
        return { filters: { is_active: 1 } };
    });

    frm.set_query("customs_policy", () => {
        if (isDynamic && customs.length) {
            return { filters: { is_active: 1, name: ["in", customs] } };
        }
        return { filters: { is_active: 1 } };
    });
    frm.set_query("customs_policy", "scenario_mappings", () => {
        if (isDynamic && customs.length) {
            return { filters: { is_active: 1, name: ["in", customs] } };
        }
        return { filters: { is_active: 1 } };
    });
}

async function applyAgentDynamicDefaults(frm) {
    setAgentPolicyQueries(frm, null);
    if (!frm.doc.sales_person) {
        return;
    }

    const response = await frappe.call({
        method: "orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet.get_agent_dynamic_defaults",
        args: { sales_person: frm.doc.sales_person },
    });
    const context = response.message || {};
    setAgentPolicyQueries(frm, context);

    if (context.pricing_mode !== "Dynamic Calculation Engine") {
        return;
    }

    const selected = context.selected || {};
    if (selected.pricing_scenario) {
        await frm.set_value("pricing_scenario", selected.pricing_scenario);
    }
    if (selected.benchmark_policy) {
        await frm.set_value("benchmark_policy", selected.benchmark_policy);
    }
    if (selected.customs_policy) {
        await frm.set_value("customs_policy", selected.customs_policy);
    }
}

frappe.ui.form.on("Pricing Sheet", {
    setup(frm) {
        const queryConfig = () => ({
            query: "orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet.stock_item_query",
        });

        frm.set_query("item", "lines", queryConfig);
        frm.set_query("source_buying_price_list", "lines", () => ({ filters: { buying: 1 } }));
        setAgentPolicyQueries(frm, null);
        frm.fields_dict.lines.grid.get_field("benchmark_status").formatter = (value) => statusBadge(value);
        if (frm.fields_dict.lines.grid.get_field("margin_source")) {
            frm.fields_dict.lines.grid.get_field("margin_source").formatter = (value) => marginSourceBadge(value);
        }
    },

    refresh(frm) {
        applyFormLayoutClass(frm);
        applyDashboardSectionClass(frm);
        applyModeLayout(frm);

        frm.add_custom_button(__("Recalculate"), async () => {
            try {
                await frm.save();
                frm.refresh_field("lines");
                renderProjectionDashboard(frm);
                frappe.show_alert({ message: __("Pricing recalculated"), indicator: "green" });
            } catch (e) {
                frappe.msgprint({
                    title: __("Recalculation Failed"),
                    message: __("Unable to save and recalculate this Pricing Sheet."),
                    indicator: "red",
                });
            }
        });

        frm.add_custom_button(__("Queue Recalculate"), async () => {
            if (frm.is_dirty()) {
                await frm.save();
            }
            const r = await frm.call("queue_recalculate");
            frappe.show_alert({ message: __("Recalculation queued ({0})", [r.message.job_id || "-"]), indicator: "blue" });
        });

        frm.add_custom_button(__("Add from Bundle"), () => {
            const dialog = new frappe.ui.Dialog({
                title: __("Add from Bundle"),
                fields: [
                    {
                        label: __("Product Bundle"),
                        fieldname: "product_bundle",
                        fieldtype: "Link",
                        options: "Product Bundle",
                        reqd: 1,
                        default: frm.doc.product_bundle,
                    },
                    { label: __("Multiplier"), fieldname: "multiplier", fieldtype: "Float", default: 1 },
                    {
                        label: __("Replace Existing Lines"),
                        fieldname: "replace_existing_lines",
                        fieldtype: "Check",
                        default: 0,
                    },
                    {
                        label: __("Default Show In Detail"),
                        fieldname: "default_show_in_detail",
                        fieldtype: "Check",
                        default: 1,
                    },
                    {
                        label: __("Default Display Group Source"),
                        fieldname: "default_display_group_source",
                        fieldtype: "Select",
                        options: "Bundle Name\nItem Group",
                        default: "Item Group",
                    },
                    {
                        label: __("Line Mode"),
                        fieldname: "line_mode",
                        fieldtype: "Select",
                        options: "Exploded\nBundle Single\nBoth",
                        default: "Exploded",
                    },
                    {
                        label: __("Include Summary In Detail"),
                        fieldname: "include_summary_in_detail",
                        fieldtype: "Check",
                        default: 1,
                    },
                    {
                        label: __("Include Components In Detail"),
                        fieldname: "include_components_in_detail",
                        fieldtype: "Check",
                        default: 1,
                    },
                ],
                primary_action_label: __("Add"),
                primary_action: async (values) => {
                    const bothMode = values.line_mode === "Both";
                    const summaryInDetail = Number(values.include_summary_in_detail || 0) === 1;
                    const componentsInDetail = Number(values.include_components_in_detail || 0) === 1;

                    if (bothMode && summaryInDetail && componentsInDetail) {
                        const confirmed = await new Promise((resolve) => {
                            frappe.confirm(
                                __(
                                    "Both mode with both detail flags enabled will include summary and components in detailed quotation. Continue?"
                                ),
                                () => resolve(true),
                                () => resolve(false)
                            );
                        });
                        if (!confirmed) {
                            return;
                        }
                    }

                    if (frm.is_dirty()) {
                        await frm.save();
                    }
                    await frm.call("add_from_bundle", values);
                    dialog.hide();
                    await frm.reload_doc();
                    renderProjectionDashboard(frm);
                    frappe.show_alert({ message: __("Bundle items imported"), indicator: "green" });
                },
            });
            dialog.show();
        });

        if (!frm.is_new()) {
            frm.page.set_primary_action(__("Generate Quotation"), async () => {
                try {
                    if (frm.is_dirty()) {
                        await frm.save();
                    }
                    const approved = await openQuotationPreview(frm);
                    if (!approved) {
                        return;
                    }
                    const r = await frm.call("generate_quotation");
                    const quotationName = r.message;
                    if (!quotationName) {
                        frappe.throw(__("Quotation was not created."));
                    }
                    frappe.show_alert({ message: __("Quotation {0} created", [quotationName]), indicator: "green" });
                    frappe.set_route("Form", "Quotation", quotationName);
                } catch (e) {
                    frappe.msgprint({
                        title: __("Generation Failed"),
                        message: e.message || __("Unable to generate Quotation."),
                        indicator: "red",
                    });
                }
            });
        }

        renderProjectionDashboard(frm);
        renderContextActions(frm);
        setTimeout(() => collapseAdvancedSections(frm), 0);
        if (frm.doc.sales_person) {
            frm.events.sales_person(frm);
        }

        // Keyboard shortcut: Ctrl+Shift+R = Recalculate
        $(document).off("keydown.psheet").on("keydown.psheet", async (e) => {
            if (e.ctrlKey && e.shiftKey && e.key === "R" && frm.doc.doctype === "Pricing Sheet") {
                e.preventDefault();
                try {
                    await frm.save();
                    renderProjectionDashboard(frm);
                    frappe.show_alert({ message: __("Pricing recalculated"), indicator: "green" });
                } catch (_) { }
            }
        });
    },

    async customer(frm) {
        if (!frm.doc.customer) {
            frm.set_value("customer_type", "");
            frm.set_value("tier", "");
            renderProjectionDashboard(frm);
            return;
        }

        const response = await frappe.db.get_value("Customer", frm.doc.customer, ["customer_group", "tier"]);
        const values = response.message || {};
        await frm.set_value("customer_type", values.customer_group || "");
        await frm.set_value("tier", values.tier || "");
        renderProjectionDashboard(frm);
    },

    benchmark_policy(frm) {
        renderProjectionDashboard(frm);
    },

    customs_policy(frm) {
        renderProjectionDashboard(frm);
    },

    async sales_person(frm) {
        await applyAgentDynamicDefaults(frm);
        renderProjectionDashboard(frm);
    },

    geography_territory(frm) {
        renderProjectionDashboard(frm);
    },

    lines_remove(frm) {
        renderProjectionDashboard(frm);
    },
});

frappe.ui.form.on("Pricing Sheet Item", {
    item(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.item) {
            return;
        }

        frappe.call({
            method: "orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet.get_item_pricing_defaults",
            args: {
                item_code: row.item,
                pricing_scenario: row.pricing_scenario || frm.doc.pricing_scenario,
                source_buying_price_list: row.source_buying_price_list,
            },
            callback: (r) => {
                const data = r.message || {};
                if (!row.buy_price || row.buy_price <= 0) {
                    frappe.model.set_value(cdt, cdn, "buy_price", data.buy_price || 0);
                }
                if (!row.display_group) {
                    frappe.model.set_value(cdt, cdn, "display_group", data.item_group || "Ungrouped");
                }
                renderProjectionDashboard(frm);
            },
        });
    },

    qty(frm) {
        renderProjectionDashboard(frm);
    },

    buy_price(frm) {
        renderProjectionDashboard(frm);
    },

    manual_sell_unit_price(frm) {
        renderProjectionDashboard(frm);
    },

    pricing_scenario(frm) {
        renderProjectionDashboard(frm);
    },

    source_buying_price_list(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.item) {
            renderProjectionDashboard(frm);
            return;
        }

        frappe.call({
            method: "orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet.get_item_pricing_defaults",
            args: {
                item_code: row.item,
                pricing_scenario: row.pricing_scenario || frm.doc.pricing_scenario,
                source_buying_price_list: row.source_buying_price_list,
            },
            callback: (r) => {
                const data = r.message || {};
                frappe.model.set_value(cdt, cdn, "buy_price", data.buy_price || 0);
                renderProjectionDashboard(frm);
            },
        });
    },
});

frappe.ui.form.on("Pricing Sheet Scenario Override", {
    override_value(frm) {
        renderProjectionDashboard(frm);
    },
    scenario_overrides_remove(frm) {
        renderProjectionDashboard(frm);
    },
});

frappe.ui.form.on("Pricing Sheet Line Override", {
    line_override_value(frm) {
        renderProjectionDashboard(frm);
    },
    line_overrides_remove(frm) {
        renderProjectionDashboard(frm);
    },
});

frappe.ui.form.on("Pricing Sheet Bundle Scenario", {
    bundle(frm) {
        renderProjectionDashboard(frm);
    },
    pricing_scenario(frm) {
        renderProjectionDashboard(frm);
    },
    bundle_scenario_rules_remove(frm) {
        renderProjectionDashboard(frm);
    },
});

frappe.ui.form.on("Pricing Sheet Scenario Mapping", {
    source_buying_price_list(frm) {
        renderProjectionDashboard(frm);
    },
    pricing_scenario(frm) {
        renderProjectionDashboard(frm);
    },
    customs_policy(frm) {
        renderProjectionDashboard(frm);
    },
    benchmark_policy(frm) {
        renderProjectionDashboard(frm);
    },
    scenario_mappings_remove(frm) {
        renderProjectionDashboard(frm);
    },
});
