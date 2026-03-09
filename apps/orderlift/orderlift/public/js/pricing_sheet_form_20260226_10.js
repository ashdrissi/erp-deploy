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
        {
            label: __("Add from Bundle"),
            handler: async () => openAddFromBundleDialog(frm),
        },
    ];

    mount("lines", __("Pricing Sheet Actions"), lineActions);
}

function openAddFromBundleDialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __("Add from Bundle"),
        fields: [
            {
                label: __("Product Bundle"),
                fieldname: "product_bundle",
                fieldtype: "Link",
                options: "Product Bundle",
                reqd: 1,
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
                        __("Both mode with both detail flags enabled will include summary and components in detailed quotation. Continue?"),
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
}

function parseDimensioningValues(frm) {
    try {
        const parsed = JSON.parse(frm.doc.dimensioning_inputs_json || "{}");
        return parsed && typeof parsed === "object" ? parsed : {};
    } catch (e) {
        return {};
    }
}

function normalizeDimensioningValues(setConfig, currentValues) {
    const values = { ...(currentValues || {}) };
    (setConfig.fields || []).forEach((field) => {
        if (values[field.field_key] !== undefined) {
            return;
        }
        if ((field.field_type || "").toLowerCase() === "check") {
            values[field.field_key] = [1, true, "1", "true", "yes", "on"].includes(field.default_value);
            return;
        }
        values[field.field_key] = field.default_value ?? "";
    });
    return values;
}

function collectDimensioningValues($root, setConfig) {
    const values = {};
    (setConfig.fields || []).forEach((field) => {
        const key = field.field_key;
        const input = $root.find(`[data-dimensioning-key="${key}"]`);
        const type = (field.field_type || "Float").toLowerCase();
        if (!input.length) {
            return;
        }
        if (type === "check") {
            values[key] = input.is(":checked");
            return;
        }
        values[key] = input.val();
    });
    return values;
}

function ensureDimensioningToolStyles() {
    if (document.getElementById("pricing-sheet-dimensioning-styles")) return;
    const style = document.createElement("style");
    style.id = "pricing-sheet-dimensioning-styles";
    style.textContent = `
        .od-shell{display:grid;gap:12px;padding:16px;border:1px solid #dbe4ea;border-radius:18px;background:linear-gradient(135deg,#fff8ef 0%,#f6fbf9 100%)}
        .od-hero{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}
        .od-eyebrow{font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#64748b;margin-bottom:6px}
        .od-title{font-size:22px;font-weight:700;line-height:1.05;color:#102a43}
        .od-copy{margin-top:6px;font-size:13px;color:#486581;max-width:56ch}
        .od-actions{display:flex;gap:8px;flex-wrap:wrap}
        .od-tip-row{display:flex;gap:8px;flex-wrap:wrap}
        .od-tip{display:inline-flex;padding:5px 10px;border-radius:999px;background:#eff6ff;border:1px solid #bfdbfe;color:#1d4ed8;font-size:12px;font-weight:600}
        .od-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
        .od-field-card{padding:12px;border-radius:14px;background:rgba(255,255,255,.78);border:1px solid rgba(203,213,225,.9)}
        .od-field-label{display:block;margin-bottom:6px}
        .od-field-meta{margin-top:6px;font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.05em}
        .od-field-help{margin-top:4px}
        .od-preview{padding:14px;border-radius:14px;background:#fff;border:1px solid #e2e8f0;color:#475569}
        .od-preview-title{font-weight:700;color:#102a43;margin-bottom:10px}
        .od-preview-list{display:grid;gap:8px}
        .od-preview-row{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:10px 12px;border-radius:12px;background:#f8fafc;border:1px solid #e2e8f0}
        .od-preview-rule{font-size:12px;color:#64748b;margin-top:2px}
        .od-preview-qty{font-size:16px;font-weight:700;color:#0f172a}
        @media (max-width:900px){.od-hero{flex-direction:column}.od-grid{grid-template-columns:1fr}}
    `;
    document.head.appendChild(style);
}

async function renderDimensioningTool(frm) {
    const field = frm.get_field("dimensioning_inputs_html");
    if (!field || !field.$wrapper) {
        return;
    }
    ensureDimensioningToolStyles();

    if (!frm.doc.dimensioning_set) {
        field.$wrapper.html(`<div class="text-muted small">${__("Selectionnez un set de dimensionnement pour afficher les caracteristiques a renseigner.")}</div>`);
        return;
    }

    const response = await frappe.call({
        method: "orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet.get_dimensioning_set_payload",
        args: { set_name: frm.doc.dimensioning_set },
    });
    const setConfig = (response.message || {}).set;
    if (!setConfig) {
        field.$wrapper.html(`<div class="text-danger small">${__("Impossible de charger le set de dimensionnement selectionne.")}</div>`);
        return;
    }

    const values = normalizeDimensioningValues(setConfig, parseDimensioningValues(frm));
    frm.doc.dimensioning_inputs_json = JSON.stringify(values);

    const rowsHtml = (setConfig.fields || []).map((cfg) => {
        const type = (cfg.field_type || "Float").toLowerCase();
        const value = values[cfg.field_key];
        let control = "";
        if (type === "select") {
            const options = (cfg.options || []).map((opt) => {
                const selected = String(value || "") === String(opt) ? "selected" : "";
                return `<option value="${frappe.utils.escape_html(opt)}" ${selected}>${frappe.utils.escape_html(opt)}</option>`;
            }).join("");
            control = `<select class="form-control" data-dimensioning-key="${cfg.field_key}">${options}</select>`;
        } else if (type === "check") {
            control = `<label class="checkbox" style="margin:8px 0 0;"><input type="checkbox" data-dimensioning-key="${cfg.field_key}" ${value ? "checked" : ""}> <span>${__("Enabled")}</span></label>`;
        } else {
            const inputType = type === "int" || type === "float" ? "number" : "text";
            const step = type === "int" ? "1" : "any";
            control = `<input type="${inputType}" step="${step}" class="form-control" data-dimensioning-key="${cfg.field_key}" value="${frappe.utils.escape_html(String(value ?? ""))}">`;
        }
        return `
            <div class="od-field-card">
                <label class="control-label od-field-label">${frappe.utils.escape_html(cfg.label || cfg.field_key)}${cfg.is_required ? " *" : ""}</label>
                ${control}
                ${cfg.help_text ? `<div class="small text-muted od-field-help">${frappe.utils.escape_html(cfg.help_text)}</div>` : ""}
            </div>
        `;
    }).join("");

    field.$wrapper.html(`
        <div class="od-shell">
            <div class="od-hero">
                <div>
                    <div class="od-eyebrow">${__("Outil de dimensionnement")}</div>
                    <div class="od-title">${frappe.utils.escape_html(setConfig.set_name || setConfig.name)}</div>
                    <div class="od-copy">${frappe.utils.escape_html(setConfig.description || __("Renseignez les caracteristiques du projet, previsualisez les articles generes, puis ajoutez-les a la fiche tarifaire."))}</div>
                </div>
                <div class="od-actions">
                    <button class="btn btn-default btn-sm" type="button" data-dimensioning-preview>${__("Apercu des articles")}</button>
                    <button class="btn btn-default btn-sm" type="button" data-dimensioning-reset>${__("Reinitialiser")}</button>
                    <button class="btn btn-primary btn-sm" type="button" data-dimensioning-add>${__("Ajouter les articles")}</button>
                </div>
            </div>
            <div class="od-tip-row">
                <span class="od-tip">${__("1. Renseigner les caracteristiques")}</span>
                <span class="od-tip">${__("2. Previsualiser les articles")}</span>
                <span class="od-tip">${__("3. Ajouter les lignes")}</span>
            </div>
            <div class="od-grid">${rowsHtml || `<div class="text-muted small">${__("Aucune caracteristique n'est configuree dans ce set.")}</div>`}</div>
            <div class="od-preview" data-dimensioning-preview-box>${__("Cliquez sur Apercu des articles pour voir ce qui sera genere avant insertion.")}</div>
        </div>
    `);

    const $root = field.$wrapper;
    $root.find("[data-dimensioning-key]").on("change input", () => {
        const currentValues = collectDimensioningValues($root, setConfig);
        frm.doc.dimensioning_inputs_json = JSON.stringify(currentValues);
        renderDimensioningPreviewBox($root, frm.doc.dimensioning_set, currentValues);
    });

    $root.find("[data-dimensioning-reset]").on("click", async () => {
        frm.doc.dimensioning_inputs_json = JSON.stringify(normalizeDimensioningValues(setConfig, {}));
        await renderDimensioningTool(frm);
    });

    $root.find("[data-dimensioning-preview]").on("click", async () => {
        const currentValues = collectDimensioningValues($root, setConfig);
        frm.doc.dimensioning_inputs_json = JSON.stringify(currentValues);
        await renderDimensioningPreviewBox($root, frm.doc.dimensioning_set, currentValues);
    });

    $root.find("[data-dimensioning-add]").on("click", async () => {
        const currentValues = collectDimensioningValues($root, setConfig);
        frm.doc.dimensioning_inputs_json = JSON.stringify(currentValues);
        if (frm.is_dirty()) {
            await frm.save();
        }
        await frm.call("add_dimensioning_items", {
            input_values_json: JSON.stringify(currentValues),
            replace_existing_generated: 1,
        });
        await frm.reload_doc();
        renderProjectionDashboard(frm);
        await renderDimensioningTool(frm);
        frappe.show_alert({ message: __("Articles de dimensionnement ajoutes"), indicator: "green" });
    });

    await renderDimensioningPreviewBox($root, frm.doc.dimensioning_set, values);
}

async function renderDimensioningPreviewBox($root, setName, currentValues) {
    const box = $root.find("[data-dimensioning-preview-box]");
    if (!box.length) return;
    box.html(`<span class="text-muted">${__("Preparation de l'apercu...")}</span>`);

    try {
        const response = await frappe.call({
            method: "orderlift.orderlift_sales.doctype.dimensioning_set.dimensioning_set.preview_dimensioning_set",
            args: {
                set_name: setName,
                input_values_json: JSON.stringify(currentValues || {}),
            },
        });
        const items = (response.message || {}).items || [];
        if (!items.length) {
            box.html(`<span class="text-muted">${__("Aucun article ne correspond aux caracteristiques saisies.")}</span>`);
            return;
        }
        box.html(`
            <div class="od-preview-title">${__("Apercu des articles generes")}</div>
            <div class="od-preview-list">
                ${items.map((row) => `
                    <div class="od-preview-row">
                        <div>
                            <strong>${frappe.utils.escape_html(row.item || "-")}</strong>
                            <div class="od-preview-rule">${frappe.utils.escape_html(row.rule_label || __("Regle automatique"))}</div>
                        </div>
                        <div class="od-preview-qty">${frappe.format(row.qty || 0, { fieldtype: "Float" })}</div>
                    </div>
                `).join("")}
            </div>
        `);
    } catch (e) {
        box.html(`<span class="text-danger">${__("L'apercu a echoue. Verifiez le set selectionne et les caracteristiques renseignees.")}</span>`);
    }
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
        "pricing_scenario", "minimum_margin_percent", "strict_margin_guard"];
    // Static-only fields
    const staticFields = ["selected_price_list"];

    dynamicFields.forEach(fn => frm.toggle_display(fn, !isStatic));
    staticFields.forEach(fn => frm.toggle_display(fn, isStatic));

    if (restrictedAgent) {
        [
            "pricing_scenario", "benchmark_policy", "customs_policy", "selected_price_list",
            "minimum_margin_percent", "strict_margin_guard", "scenario_mappings",
            "section_runtime", "total_buy", "total_expenses",
            "applied_customs_policy", "applied_benchmark_policy", "customs_total_applied",
        ].forEach((fieldname) => frm.toggle_display(fieldname, false));
    }

    const linesGrid = frm.fields_dict.lines && frm.fields_dict.lines.grid;
    if (linesGrid) {
        setGridFieldVisibility(linesGrid, [
            "source_buying_price_list", "pricing_scenario", "resolved_pricing_scenario", "resolved_scenario_rule",
            "resolved_margin_rule", "scenario_source", "has_scenario_override", "has_line_override", "buy_price",
            "buy_price_missing", "buy_price_message", "base_amount", "expense_unit_price", "expense_total",
            "customs_unit_amount", "margin_unit_amount", "margin_total_amount", "projected_unit_price", "projected_total_price", "manual_sell_unit_price", "margin_pct",
            "customs_material", "customs_weight_kg", "customs_rate_per_kg", "customs_rate_percent",
            "customs_by_kg", "customs_by_percent", "customs_applied", "customs_basis", "tier_modifier_total", "zone_modifier_total",
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
                <div class="ps-kpi-label">⚙ ${__("Additions")}</div>
                <div class="ps-kpi-value">${frappe.format(totalExpenses, { fieldtype: "Currency" })}</div>
            </div>` : isStatic ? `<div class="ps-kpi ps-kpi--margin" style="background:#ede9fe;">
                <div class="ps-kpi-label">📋 ${__("Price List")}</div>
                <div class="ps-kpi-value" style="font-size:13px;color:#4f46e5;">${frappe.utils.escape_html(frm.doc.selected_price_list || "—")}</div>
            </div>` : ""}
            <div class="ps-kpi ps-kpi--final">
                <div class="ps-kpi-label">💰 ${__("Total Final HT")}</div>
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
                            <th style="text-align:right;">${__("Final Total HT")}</th>
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
        ${__("Total Final HT")}: ${frappe.format(data.total_final || 0, { fieldtype: "Currency" })}<br>
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
        frm.set_query("dimensioning_set", () => ({ filters: { is_active: 1 } }));
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
        renderDimensioningTool(frm);
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

    dimensioning_set(frm) {
        frm.doc.dimensioning_inputs_json = "";
        renderDimensioningTool(frm);
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
