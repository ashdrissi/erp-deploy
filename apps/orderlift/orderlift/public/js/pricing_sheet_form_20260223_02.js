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

function ensurePricingSheetStyles(frm) {
    const linkId = "pricing-sheet-ux-css";
    if (document.getElementById(linkId)) {
        return;
    }

    const link = document.createElement("link");
    link.id = linkId;
    link.rel = "stylesheet";
    link.href = "/assets/orderlift/css/pricing_sheet_20260224_01.css?v=20260224-01";
    document.head.appendChild(link);
}

function renderContextActions(frm) {
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

    mount("lines", __("Pricing Sheet Actions"), [
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
            label: __("Apply Scenario to Rows"),
            handler: async () => {
                const dialog = new frappe.ui.Dialog({
                    title: __("Apply Scenario"),
                    fields: [
                        {
                            fieldtype: "Link",
                            fieldname: "pricing_scenario",
                            label: __("Pricing Scenario"),
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
        },
    ]);

    mount("scenario_overrides", __("Scenario Override Actions"), [
        {
            label: __("Preview Margin Rule"),
            handler: async () => {
                const policy = frm.doc.applied_margin_policy || frm.doc.margin_policy || "-";
                const rule = frm.doc.applied_margin_rule || __("No active rule matched");
                frappe.msgprint({
                    title: __("Margin Rule Preview"),
                    message: `<b>${__("Policy")}</b>: ${frappe.utils.escape_html(policy)}<br><b>${__("Rule")}</b>: ${frappe.utils.escape_html(rule)}`,
                    indicator: "blue",
                });
            },
        },
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

function aggregateExpenseImpact(lines) {
    const totals = {};
    (lines || []).forEach((row) => {
        if (!row.pricing_breakdown_json) {
            return;
        }
        try {
            const steps = JSON.parse(row.pricing_breakdown_json || "[]");
            steps.forEach((step) => {
                const label = step.label || __("Expense");
                const unitDelta = (step.delta_unit || 0) + (step.delta_line || 0);
                const lineDelta = unitDelta * (row.qty || 0) + (step.delta_sheet || 0);
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
    const topRows = lines.slice(0, 8);
    const totalBase = frm.doc.total_buy || 0;
    const totalExpenses = frm.doc.total_expenses || 0;
    const totalFinal = frm.doc.total_selling || 0;
    const avgMarkup = totalBase > 0 ? (totalFinal / totalBase - 1) * 100 : 0;
    const warnings = frm.doc.projection_warnings || "";
    const marginPolicy = frm.doc.applied_margin_policy || frm.doc.margin_policy || "";
    const marginRule = frm.doc.applied_margin_rule || "";
    const scenarioCounts = {};
    lines.forEach((row) => {
        const key = row.resolved_pricing_scenario || row.pricing_scenario || frm.doc.pricing_scenario || "Unresolved";
        scenarioCounts[key] = (scenarioCounts[key] || 0) + 1;
    });
    const scenarioPills = Object.entries(scenarioCounts)
        .map(([name, count]) => {
            return `<span class="ps-scenario-chip">${frappe.utils.escape_html(name)}<strong>${count}</strong></span>`;
        })
        .join("");

    const rowsHtml =
        topRows
            .map((row, index) => {
                const item = frappe.utils.escape_html(row.item || "-");
                const preview = frappe.utils.escape_html(row.breakdown_preview || __("No expenses"));
                const floor = row.price_floor_violation ? `<span class="indicator-pill red">${__("Floor")}</span>` : "";
                const scn = frappe.utils.escape_html(row.resolved_pricing_scenario || row.pricing_scenario || "-");
                const scnOverride = row.has_scenario_override ? `<span class="indicator-pill orange">${__("Edited")}</span>` : "";
                return `
                    <tr>
                        <td>${item}</td>
                        <td>${scn} ${scnOverride}</td>
                        <td style="text-align:right;">${frappe.format(row.qty || 0, { fieldtype: "Float" })}</td>
                        <td style="text-align:right;">${frappe.format(row.buy_price || 0, { fieldtype: "Currency" })}</td>
                        <td style="text-align:right;">${frappe.format(row.projected_unit_price || 0, { fieldtype: "Currency" })}</td>
                        <td style="text-align:right;">${frappe.format(row.final_sell_unit_price || 0, { fieldtype: "Currency" })}</td>
                        <td>${floor}</td>
                        <td>${preview}</td>
                        <td style="text-align:right;"><button class="btn btn-xs btn-default" data-breakdown-index="${index}">${__("View")}</button></td>
                    </tr>
                `;
            })
            .join("") ||
        `<tr><td colspan="9" style="color:#64748b;">${__("No pricing lines yet.")}</td></tr>`;

    const impacts = aggregateExpenseImpact(lines)
        .slice(0, 6)
        .map(
            ([label, value]) =>
                `<tr><td>${frappe.utils.escape_html(label)}</td><td style="text-align:right;">${frappe.format(value, {
                    fieldtype: "Currency",
                })}</td></tr>`
        )
        .join("");

    const warningBlock = warnings
        ? `<div style="border:1px solid #fed7aa;background:#fff7ed;color:#9a3412;padding:10px;border-radius:10px;margin:10px 0;white-space:pre-line;">${frappe.utils.escape_html(
              warnings
          )}</div>`
        : "";

    ensurePricingSheetStyles(frm);

    const html = `
        <div class="ps-shell">
        <div class="ps-card ps-card-pad" style="margin-bottom:10px;">
            <div class="ps-kpi-grid">
                <div class="ps-kpi" style="background:#f8fafc;">
                    <div class="ps-kpi-label" style="color:#64748b;">${__("Total Base")}</div>
                    <div class="ps-kpi-value">${frappe.format(totalBase, { fieldtype: "Currency" })}</div>
                </div>
                <div class="ps-kpi" style="background:#fff7ed;">
                    <div class="ps-kpi-label" style="color:#9a3412;">${__("Total Expenses")}</div>
                    <div class="ps-kpi-value">${frappe.format(totalExpenses, { fieldtype: "Currency" })}</div>
                </div>
                <div class="ps-kpi" style="background:#ecfdf5;">
                    <div class="ps-kpi-label" style="color:#166534;">${__("Total Final")}</div>
                    <div class="ps-kpi-value">${frappe.format(totalFinal, { fieldtype: "Currency" })}</div>
                </div>
                <div class="ps-kpi" style="background:#eff6ff;">
                    <div class="ps-kpi-label" style="color:#1d4ed8;">${__("Average Markup")}</div>
                    <div class="ps-kpi-value">${frappe.format(avgMarkup, { fieldtype: "Percent" })}</div>
                </div>
            </div>
            <div style="margin-top:10px;font-size:12px;color:#334155;">${scenarioPills || `<span style="color:#64748b;">${__("No resolved scenario")}</span>`}</div>
            <div style="margin-top:6px;font-size:12px;color:#334155;">
                <span class="ps-scenario-chip"><strong>${__("Margin Policy")}</strong> ${frappe.utils.escape_html(marginPolicy || "-")}</span>
                <span class="ps-scenario-chip"><strong>${__("Margin Rule")}</strong> ${frappe.utils.escape_html(marginRule || __("No rule"))}</span>
            </div>
            ${warningBlock}
        </div>
        <div class="ps-grid-two">
            <div class="ps-card ps-table-wrap">
                <table class="ps-table">
                    <thead style="background:#f8fafc;">
                        <tr>
                            <th style="text-align:left;">${__("Item")}</th>
                            <th style="text-align:left;">${__("Scenario")}</th>
                            <th style="text-align:right;">${__("Qty")}</th>
                            <th style="text-align:right;">${__("Base")}</th>
                            <th style="text-align:right;">${__("Projected")}</th>
                            <th style="text-align:right;">${__("Final")}</th>
                            <th style="text-align:left;">${__("Flags")}</th>
                            <th style="text-align:left;">${__("Expense Flow")}</th>
                            <th style="text-align:right;">${__("Detail")}</th>
                        </tr>
                    </thead>
                    <tbody>${rowsHtml}</tbody>
                </table>
                <div class="ps-overflow-hint">${__("Tip: Scroll horizontally for all pricing columns on smaller screens.")}</div>
            </div>
            <div class="ps-card ps-table-wrap">
                <div style="padding:8px 10px;background:#f8fafc;font-weight:600;">${__("Expense Impact")}</div>
                <table class="ps-table">
                    <thead>
                        <tr>
                            <th style="text-align:left;">${__("Expense")}</th>
                            <th style="text-align:right;">${__("Contribution")}</th>
                        </tr>
                    </thead>
                    <tbody>${impacts || `<tr><td colspan="2" style="padding:8px;color:#64748b;">${__("No data")}</td></tr>`}</tbody>
                </table>
            </div>
        </div>
        </div>
    `;

    frm.fields_dict.projection_dashboard.$wrapper.html(html);
    frm.fields_dict.projection_dashboard.$wrapper.find("[data-breakdown-index]").on("click", function () {
        const i = Number($(this).attr("data-breakdown-index"));
        const row = topRows[i];
        if (row) {
            showBreakdownDialog(row);
        }
    });
}

async function openQuotationPreview(frm) {
    const preview = await frm.call("get_quotation_preview");
    const data = preview.message || {};
    const details = `
        ${__("Total Base")}: ${frappe.format(data.total_buy || 0, { fieldtype: "Currency" })}<br>
        ${__("Total Final")}: ${frappe.format(data.total_final || 0, { fieldtype: "Currency" })}<br>
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

frappe.ui.form.on("Pricing Sheet", {
    setup(frm) {
        const queryConfig = () => ({
            query: "orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet.stock_item_query",
        });

        frm.set_query("item", "lines", queryConfig);
        frm.set_query("pricing_scenario", "lines", () => ({ filters: {} }));
        frm.set_query("margin_policy", () => ({ filters: { is_active: 1 } }));
        frm.fields_dict.lines.grid.get_field("benchmark_status").formatter = (value) => statusBadge(value);
    },

    refresh(frm) {
        applyFormLayoutClass(frm);

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
    },

    margin_policy(frm) {
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
