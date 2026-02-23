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
    const scenarioCounts = {};
    lines.forEach((row) => {
        const key = row.resolved_pricing_scenario || row.pricing_scenario || frm.doc.pricing_scenario || "Unresolved";
        scenarioCounts[key] = (scenarioCounts[key] || 0) + 1;
    });
    const scenarioPills = Object.entries(scenarioCounts)
        .map(([name, count]) => {
            return `<span style="display:inline-block;padding:4px 8px;border:1px solid #cbd5e1;border-radius:999px;margin-right:6px;background:#f8fafc;">${frappe.utils.escape_html(name)} (${count})</span>`;
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

    const html = `
        <div style="border:1px solid #e2e8f0;border-radius:14px;padding:14px;background:#ffffff;margin-bottom:10px;">
            <div style="display:grid;grid-template-columns:repeat(4,minmax(120px,1fr));gap:10px;">
                <div style="border:1px solid #e5e7eb;border-radius:10px;padding:10px;background:#f8fafc;">
                    <div style="font-size:11px;color:#64748b;">${__("Total Base")}</div>
                    <div style="font-size:18px;font-weight:700;">${frappe.format(totalBase, { fieldtype: "Currency" })}</div>
                </div>
                <div style="border:1px solid #e5e7eb;border-radius:10px;padding:10px;background:#fff7ed;">
                    <div style="font-size:11px;color:#9a3412;">${__("Total Expenses")}</div>
                    <div style="font-size:18px;font-weight:700;">${frappe.format(totalExpenses, { fieldtype: "Currency" })}</div>
                </div>
                <div style="border:1px solid #e5e7eb;border-radius:10px;padding:10px;background:#ecfdf5;">
                    <div style="font-size:11px;color:#166534;">${__("Total Final")}</div>
                    <div style="font-size:18px;font-weight:700;">${frappe.format(totalFinal, { fieldtype: "Currency" })}</div>
                </div>
                <div style="border:1px solid #e5e7eb;border-radius:10px;padding:10px;background:#eff6ff;">
                    <div style="font-size:11px;color:#1d4ed8;">${__("Average Markup")}</div>
                    <div style="font-size:18px;font-weight:700;">${frappe.format(avgMarkup, { fieldtype: "Percent" })}</div>
                </div>
            </div>
            <div style="margin-top:10px;font-size:12px;color:#334155;">${scenarioPills || `<span style="color:#64748b;">${__("No resolved scenario")}</span>`}</div>
            ${warningBlock}
        </div>
        <div style="display:grid;grid-template-columns:2fr 1fr;gap:10px;">
            <div style="border:1px solid #e2e8f0;border-radius:14px;overflow:hidden;background:#fff;">
                <table style="width:100%;border-collapse:collapse;">
                    <thead style="background:#f8fafc;">
                        <tr>
                            <th style="text-align:left;padding:8px;border-bottom:1px solid #e2e8f0;">${__("Item")}</th>
                            <th style="text-align:left;padding:8px;border-bottom:1px solid #e2e8f0;">${__("Scenario")}</th>
                            <th style="text-align:right;padding:8px;border-bottom:1px solid #e2e8f0;">${__("Qty")}</th>
                            <th style="text-align:right;padding:8px;border-bottom:1px solid #e2e8f0;">${__("Base")}</th>
                            <th style="text-align:right;padding:8px;border-bottom:1px solid #e2e8f0;">${__("Projected")}</th>
                            <th style="text-align:right;padding:8px;border-bottom:1px solid #e2e8f0;">${__("Final")}</th>
                            <th style="text-align:left;padding:8px;border-bottom:1px solid #e2e8f0;">${__("Flags")}</th>
                            <th style="text-align:left;padding:8px;border-bottom:1px solid #e2e8f0;">${__("Expense Flow")}</th>
                            <th style="text-align:right;padding:8px;border-bottom:1px solid #e2e8f0;">${__("Detail")}</th>
                        </tr>
                    </thead>
                    <tbody>${rowsHtml}</tbody>
                </table>
            </div>
            <div style="border:1px solid #e2e8f0;border-radius:14px;overflow:hidden;background:#fff;">
                <div style="padding:8px 10px;background:#f8fafc;font-weight:600;">${__("Expense Impact")}</div>
                <table style="width:100%;border-collapse:collapse;">
                    <thead>
                        <tr>
                            <th style="text-align:left;padding:8px;border-bottom:1px solid #e2e8f0;">${__("Expense")}</th>
                            <th style="text-align:right;padding:8px;border-bottom:1px solid #e2e8f0;">${__("Contribution")}</th>
                        </tr>
                    </thead>
                    <tbody>${impacts || `<tr><td colspan="2" style="padding:8px;color:#64748b;">${__("No data")}</td></tr>`}</tbody>
                </table>
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
        frm.fields_dict.lines.grid.get_field("benchmark_status").formatter = (value) => statusBadge(value);
    },

    refresh(frm) {
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

        frm.add_custom_button(__("Refresh Base Prices"), async () => {
            if (frm.is_dirty()) {
                await frm.save();
            }
            await frm.call("refresh_buy_prices");
            await frm.reload_doc();
            renderProjectionDashboard(frm);
            frappe.show_alert({ message: __("Base prices refreshed"), indicator: "green" });
        });

        frm.add_custom_button(__("Load Scenario Values"), async () => {
            if (frm.is_dirty()) {
                await frm.save();
            }
            await frm.call("load_scenario_overrides");
            await frm.reload_doc();
            renderProjectionDashboard(frm);
            frappe.show_alert({ message: __("Scenario values loaded"), indicator: "green" });
        });

        frm.add_custom_button(__("Reset Scenario Overrides"), async () => {
            if (frm.is_dirty()) {
                await frm.save();
            }
            await frm.call("reset_scenario_overrides");
            await frm.reload_doc();
            renderProjectionDashboard(frm);
            frappe.show_alert({ message: __("Scenario overrides reset"), indicator: "green" });
        });

        frm.add_custom_button(__("Apply Scenario to Rows"), () => {
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
                ],
                primary_action_label: __("Add"),
                primary_action: async (values) => {
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
