// Active Pricing Sheet form script loaded via hooks.py doctype_js.

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

function applyNativeLinesGridProperties(frm) {
    const linesGrid = frm.fields_dict.lines && frm.fields_dict.lines.grid;
    if (!linesGrid) return;
    const restrictedAgent = isRestrictedAgentUser();

    const businessListColumns = new Set([
        "item",
        "qty",
        "buy_price",
        "expense_total",
        "customs_applied",
        "margin_total_amount",
        "final_sell_total",
        "max_discount_percent_allowed",
        "discount_percent",
        "discount_amount",
        "discounted_sell_total",
        "commission_amount",
    ]);
    const restrictedColumns = new Set([
        "item",
        "qty",
        "final_sell_unit_price",
        "final_sell_total",
        "max_discount_percent_allowed",
        "discount_percent",
        "discounted_sell_total",
    ]);

    Object.entries(PRICING_SHEET_WORKSPACE_LABELS).forEach(([fieldname, label]) => {
        linesGrid.update_docfield_property(fieldname, "label", __(label));
    });

    (linesGrid.docfields || []).forEach((df) => {
        if (!df || !df.fieldname) return;
        if (["Section Break", "Column Break", "HTML", "Button", "Long Text"].includes(df.fieldtype)) return;
        const visibleSet = restrictedAgent ? restrictedColumns : businessListColumns;
        linesGrid.update_docfield_property(df.fieldname, "in_list_view", visibleSet.has(df.fieldname) ? 1 : 0);
        if (restrictedAgent) {
            linesGrid.update_docfield_property(df.fieldname, "hidden", visibleSet.has(df.fieldname) ? 0 : 1);
        }
    });

    linesGrid.refresh();
    frm.refresh_field("lines");
}

const PRICING_SHEET_WORKSPACE_STORAGE_KEY = "orderlift.pricing-sheet.workspace-columns.v3";
const PRICING_SHEET_AGENT_VISIBLE_COLUMNS = [
    "qty",
    "final_sell_unit_price",
    "final_sell_total",
    "max_discount_percent_allowed",
    "discount_percent",
    "discounted_sell_total",
];
const PRICING_SHEET_WORKSPACE_DEFAULT_COLUMNS = [
    "qty",
    "buy_price",
    "expense_total",
    "customs_applied",
    "tier_modifier_total",
    "zone_modifier_total",
    "margin_total_amount",
    "final_sell_total",
    "max_discount_percent_allowed",
    "discount_percent",
    "discount_amount",
    "discounted_sell_total",
    "commission_amount",
    "benchmark_status",
];
const PRICING_SHEET_WORKSPACE_EDITABLE_TYPES = new Set(["Data", "Currency", "Float", "Int", "Percent", "Check", "Select", "Link"]);
const PRICING_SHEET_WORKSPACE_HIDDEN_FIELDS = new Set(["item"]);
const PRICING_SHEET_WORKSPACE_LABELS = {
    buy_price: "Buy Price",
    base_amount: "Total Buy Price",
    expense_unit_price: "Expenses Unit",
    expense_total: "Expenses",
    customs_unit_amount: "Customs Unit",
    customs_applied: "Customs",
    tier_modifier_amount: "Tier Modifier Unit",
    tier_modifier_total: "Tier Modifier",
    zone_modifier_amount: "Territory Modifier Unit",
    zone_modifier_total: "Territory Modifier",
    margin_unit_amount: "Profit Margin Unit",
    margin_total_amount: "Profit Margin",
    margin_pct: "Profit Margin %",
    projected_unit_price: "Sell Price Unit",
    projected_total_price: "Sell Price",
    manual_sell_unit_price: "Manual Sell Price Unit",
    final_sell_unit_price: "Sell Price Unit",
    final_sell_total: "Sell Total Price",
    max_discount_percent_allowed: "Max Discount %",
    discount_percent: "Discount %",
    discount_amount: "Discount Amount",
    discounted_sell_unit_price: "Discounted Sell Price Unit",
    discounted_sell_total: "Discounted Sell Price",
    commission_rate: "Commission %",
    commission_amount: "Commission",
};

function escapePricingSheetText(value) {
    return frappe.utils.escape_html(String(value ?? ""));
}

function formatPricingSheetCurrency(value) {
    return frappe.format(Number(value || 0), { fieldtype: "Currency" });
}

function formatPricingSheetFloat(value) {
    return frappe.format(Number(value || 0), { fieldtype: "Float" });
}

function formatPricingSheetPercent(value) {
    return `${Number(value || 0).toFixed(1)}%`;
}

function getPricingSheetGrid(frm) {
    return frm.fields_dict.lines && frm.fields_dict.lines.grid;
}

function isManualOverrideActive(row) {
    return Number(row.is_manual_override || 0) === 1 || Number(row.manual_sell_unit_price || 0) > 0;
}

function getPricingSheetWorkspaceAllColumns(frm) {
    const grid = getPricingSheetGrid(frm);
    if (!grid || !Array.isArray(grid.docfields)) {
        return [];
    }
    const restrictedAgent = isRestrictedAgentUser();
    const allowed = new Set(PRICING_SHEET_AGENT_VISIBLE_COLUMNS);

    return grid.docfields
        .filter((df) => {
            if (!df || !df.fieldname || PRICING_SHEET_WORKSPACE_HIDDEN_FIELDS.has(df.fieldname)) {
                return false;
            }
            if (restrictedAgent && !allowed.has(df.fieldname)) {
                return false;
            }
            if (Number(df.hidden || 0) === 1) {
                return false;
            }
            return !["Section Break", "Column Break", "HTML", "Button", "Long Text"].includes(df.fieldtype);
        })
        .map((df) => ({
            fieldname: df.fieldname,
            label: PRICING_SHEET_WORKSPACE_LABELS[df.fieldname] || df.label || df.fieldname,
            fieldtype: df.fieldtype || "Data",
            options: df.options || "",
            read_only: Number(df.read_only || 0) === 1,
            in_list_view: Number(df.in_list_view || 0) === 1,
        }));
}

function getPricingSheetWorkspaceColumn(frm, fieldname) {
    return getPricingSheetWorkspaceAllColumns(frm).find((column) => column.fieldname === fieldname) || null;
}

function canInlineEditPricingSheetWorkspaceColumn(column) {
    return Boolean(column && !column.read_only && PRICING_SHEET_WORKSPACE_EDITABLE_TYPES.has(column.fieldtype));
}

function getPricingSheetWorkspaceQuery(fieldname) {
    if (fieldname === "item") {
        return {
            query: "orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet.stock_item_query",
        };
    }
    if (fieldname === "source_buying_price_list") {
        return { filters: { buying: 1 } };
    }
    return { filters: {} };
}

function getPricingSheetWorkspaceDefaultColumns(frm) {
    const allColumns = getPricingSheetWorkspaceAllColumns(frm);
    const available = new Set(allColumns.map((column) => column.fieldname));
    const preferred = PRICING_SHEET_WORKSPACE_DEFAULT_COLUMNS.filter((fieldname) => available.has(fieldname));
    if (preferred.length) {
        return preferred;
    }

    const visibleNative = allColumns.filter((column) => column.in_list_view).map((column) => column.fieldname);
    if (visibleNative.length) {
        return visibleNative;
    }

    return allColumns.slice(0, 8).map((column) => column.fieldname);
}

function loadPricingSheetWorkspaceColumns() {
    try {
        const raw = window.localStorage.getItem(PRICING_SHEET_WORKSPACE_STORAGE_KEY);
        const parsed = raw ? JSON.parse(raw) : [];
        return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
        return [];
    }
}

function savePricingSheetWorkspaceColumns(fieldnames) {
    try {
        window.localStorage.setItem(PRICING_SHEET_WORKSPACE_STORAGE_KEY, JSON.stringify(fieldnames));
    } catch (e) {
        // Ignore storage failures and keep runtime defaults.
    }
}

function getPricingSheetWorkspaceColumns(frm) {
    if (!frm.__ps_workspace_columns) {
        const stored = loadPricingSheetWorkspaceColumns();
        const valid = stored.filter((fieldname) => getPricingSheetWorkspaceColumn(frm, fieldname));
        frm.__ps_workspace_columns = valid.length
            ? valid
            : getPricingSheetWorkspaceDefaultColumns(frm);
    }

    return frm.__ps_workspace_columns;
}

function setPricingSheetWorkspaceColumns(frm, fieldnames) {
    const normalized = getPricingSheetWorkspaceAllColumns(frm)
        .map((column) => column.fieldname)
        .filter((fieldname) => fieldnames.includes(fieldname));
    frm.__ps_workspace_columns = normalized.length
        ? normalized
        : getPricingSheetWorkspaceDefaultColumns(frm);
    savePricingSheetWorkspaceColumns(frm.__ps_workspace_columns);
}

function getPricingSheetWorkspaceRoot(frm) {
    const linesField = frm.fields_dict.lines;
    if (!linesField || !linesField.$wrapper) {
        return null;
    }

    let $root = linesField.$wrapper.siblings("[data-ps-workspace-root]");
    if (!$root.length) {
        $root = $('<div class="ps-workspace-root" data-ps-workspace-root></div>');
        linesField.$wrapper.before($root);
    }

    return $root;
}

function schedulePricingSheetWorkspaceRefresh(frm) {
    clearTimeout(frm.__ps_workspace_refresh_timer);
    frm.__ps_workspace_refresh_timer = setTimeout(() => renderPricingSheetWorkspace(frm), 60);
}

function bindPricingSheetWorkspaceGridSync(frm) {
    const grid = getPricingSheetGrid(frm);
    if (!grid || !grid.wrapper) {
        return;
    }

    const $gridWrapper = $(grid.wrapper);
    $gridWrapper.off(".psWorkspaceSync");
    $gridWrapper.on(
        "change.psWorkspaceSync input.psWorkspaceSync",
        "input, select, textarea",
        () => schedulePricingSheetWorkspaceRefresh(frm)
    );
    $gridWrapper.on(
        "click.psWorkspaceSync",
        ".grid-add-row, .grid-remove-row, .sortable-handle, .btn-open-row",
        () => schedulePricingSheetWorkspaceRefresh(frm)
    );
}

function getPricingSheetWorkspaceSelectedRows(frm) {
    if (!Array.isArray(frm.__ps_workspace_selected_rows)) {
        frm.__ps_workspace_selected_rows = [];
    }
    return frm.__ps_workspace_selected_rows;
}

function setPricingSheetWorkspaceSelectedRows(frm, rowNames) {
    const valid = new Set((frm.doc.lines || []).map((row) => row.name));
    frm.__ps_workspace_selected_rows = rowNames.filter((rowName) => valid.has(rowName));
}

function togglePricingSheetWorkspaceRowSelection(frm, rowName, selected) {
    const next = new Set(getPricingSheetWorkspaceSelectedRows(frm));
    if (selected) {
        next.add(rowName);
    } else {
        next.delete(rowName);
    }
    setPricingSheetWorkspaceSelectedRows(frm, Array.from(next));
}

async function updatePricingSheetWorkspaceField(frm, rowName, fieldname, value) {
    const row = (frm.doc.lines || []).find((entry) => entry.name === rowName);
    if (!row) {
        return;
    }
    await frappe.model.set_value(row.doctype || "Pricing Sheet Item", row.name, fieldname, value);
    frm.dirty();
    schedulePricingSheetWorkspaceRefresh(frm);
}

function getPricingSheetWorkspaceSummary(frm) {
    const lines = frm.doc.lines || [];
    const restrictedAgent = isRestrictedAgentUser();
    const totalBuy = lines.reduce((sum, row) => sum + Number(row.base_amount || 0), 0);
    const totalExpenses = lines.reduce((sum, row) => sum + Number(row.expense_total || 0), 0);
    const totalCustoms = lines.reduce((sum, row) => sum + Number(row.customs_applied || 0), 0);
    const totalTierModifiers = lines.reduce((sum, row) => sum + Number(row.tier_modifier_total || 0), 0);
    const totalTerritoryModifiers = lines.reduce((sum, row) => sum + Number(row.zone_modifier_total || 0), 0);
    const totalPolicyMargin = lines.reduce((sum, row) => sum + Number(row.margin_total_amount || 0), 0);
    const costBeforeMargin = totalBuy + totalExpenses + totalCustoms + totalTierModifiers + totalTerritoryModifiers;
    const finalSell = lines.reduce((sum, row) => sum + Number(row.final_sell_total || 0), 0);
    const totalDiscount = lines.reduce((sum, row) => sum + Number(row.discount_amount || 0), 0);
    const discountedSell = lines.reduce((sum, row) => sum + Number(row.discounted_sell_total || row.final_sell_total || 0), 0);
    const totalCommission = lines.reduce((sum, row) => sum + Number(row.commission_amount || 0), 0);
    const effectiveMargin = discountedSell - costBeforeMargin;
    const policyMarginWeightedBase = lines.reduce((sum, row) => sum + (Number(row.base_amount || 0) * Number(row.margin_pct || 0)), 0);
    const totalPolicyBase = lines.reduce((sum, row) => sum + Number(row.base_amount || 0), 0);
    const policyMarginPercent = totalPolicyBase ? (policyMarginWeightedBase / totalPolicyBase) : 0;

    const fullSummary = [
        {
            label: __("Buy Price"),
            value: formatPricingSheetCurrency(totalBuy),
        },
        {
            label: __("Expenses"),
            value: formatPricingSheetCurrency(totalExpenses),
        },
        {
            label: __("Customs"),
            value: formatPricingSheetCurrency(totalCustoms),
        },
        {
            label: __("Tier Modifier"),
            value: formatPricingSheetCurrency(totalTierModifiers),
        },
        {
            label: __("Territory Modifier"),
            value: formatPricingSheetCurrency(totalTerritoryModifiers),
        },
        {
            label: __("Profit Margin"),
            value: formatPricingSheetCurrency(totalPolicyMargin),
        },
        {
            label: __("Final Sell Price"),
            value: formatPricingSheetCurrency(finalSell),
        },
        {
            label: __("Total Discount"),
            value: formatPricingSheetCurrency(totalDiscount),
        },
        {
            label: __("Discounted Sell Price"),
            value: formatPricingSheetCurrency(discountedSell),
        },
        {
            label: __("Commission"),
            value: formatPricingSheetCurrency(totalCommission),
        },
        {
            label: __("Net Profit Margin"),
            value: formatPricingSheetCurrency(effectiveMargin),
        },
        {
            label: __("Profit Margin %"),
            value: formatPricingSheetPercent(policyMarginPercent),
        },
    ];

    if (!restrictedAgent) {
        return fullSummary;
    }

    return [
        {
            label: __("Items"),
            value: String(lines.length),
        },
        {
            label: __("Sell Total Price"),
            value: formatPricingSheetCurrency(finalSell),
        },
        {
            label: __("Max Discount"),
            value: formatPricingSheetPercent(Math.max(0, ...lines.map((row) => Number(row.max_discount_percent_allowed || 0)), 0)),
        },
        {
            label: __("Discounted Sell Price"),
            value: formatPricingSheetCurrency(discountedSell),
        },
    ];
}

function getPricingSheetWorkspaceAlerts(frm) {
    const alerts = [];
    const projectionWarnings = (frm.doc.projection_warnings || "").trim();
    if (projectionWarnings) {
        alerts.push({
            tone: "warning",
            title: __("Projection warnings"),
            body: escapePricingSheetText(projectionWarnings),
        });
    }

    (frm.doc.lines || []).forEach((row) => {
        if (["Too Low", "Too High", "No Benchmark"].includes(row.benchmark_status)) {
            alerts.push({
                tone: "danger",
                title: `${escapePricingSheetText(row.item || row.idx || __("Line"))} · ${__("Benchmark")}`,
                body: escapePricingSheetText(row.benchmark_note || row.benchmark_status),
            });
        }
        if (isManualOverrideActive(row)) {
            alerts.push({
                tone: "info",
                title: `${escapePricingSheetText(row.item || row.idx || __("Line"))} · ${__("Manual sell override")}`,
                body: formatPricingSheetCurrency(row.manual_sell_unit_price || 0),
            });
        }
        if (Number(row.discount_percent || 0) > 0) {
            alerts.push({
                tone: "info",
                title: `${escapePricingSheetText(row.item || row.idx || __("Line"))} · ${__("Agent discount")}`,
                body: `${formatPricingSheetPercent(row.discount_percent || 0)} / ${formatPricingSheetCurrency(row.discount_amount || 0)}`,
            });
        }
        if (Number(row.price_floor_violation || 0) === 1) {
            alerts.push({
                tone: "danger",
                title: `${escapePricingSheetText(row.item || row.idx || __("Line"))} · ${__("Price floor")}`,
                body: __("This line is below the configured price floor."),
            });
        }
    });

    return alerts;
}

function getPricingSheetWorkspaceBreakdownRows(frm) {
    if (isRestrictedAgentUser()) {
        return [];
    }
    return (frm.doc.lines || []).map((row) => {
        let steps = [];
        try {
            steps = JSON.parse(row.pricing_breakdown_json || "[]");
        } catch (e) {
            steps = [];
        }

        if (!Array.isArray(steps)) {
            steps = [];
        }

        return {
            row,
            steps: steps.filter((step) => step && (step.label || step.amount || step.value)),
        };
    }).filter((entry) => entry.steps.length || entry.row.expense_total || entry.row.margin_total_amount || entry.row.customs_applied);
}

function getPricingSheetWorkspaceBreakdownHtml(frm) {
    const entries = getPricingSheetWorkspaceBreakdownRows(frm);
    if (!entries.length) {
        return `
            <div class="ps-workspace-empty">
                <div class="ps-workspace-empty-title">${__("No calculation breakdown yet")}</div>
            </div>
        `;
    }

    return `
        <div class="ps-workspace-breakdown-grid">
            ${entries.map(({ row, steps }) => `
                <div class="ps-workspace-breakdown-card">
                    <div class="ps-workspace-breakdown-head">
                        <div>
                            <div class="ps-workspace-breakdown-title">${escapePricingSheetText(row.item || __("Line"))}</div>
                            <div class="ps-workspace-breakdown-meta">#${escapePricingSheetText(row.idx || "")} · ${escapePricingSheetText(row.line_type || __("Standard"))}</div>
                        </div>
                        <div class="ps-workspace-breakdown-final">${formatPricingSheetCurrency(row.discounted_sell_total || row.final_sell_total || row.projected_total_price || 0)}</div>
                    </div>
                    <div class="ps-workspace-breakdown-list">
                        ${steps.map((step) => `
                            <div class="ps-workspace-breakdown-row">
                                <span>
                                    ${escapePricingSheetText(step.label || __("Step"))}
                                    ${getPricingSheetWorkspaceBreakdownMeta(step)}
                                </span>
                                <strong>${getPricingSheetWorkspaceBreakdownAmount(step)}</strong>
                            </div>
                        `).join("")}
                    </div>
                </div>
            `).join("")}
        </div>
    `;
}

function getPricingSheetWorkspaceBreakdownAmount(step) {
    const deltaUnit = Number(step.delta_unit || 0);
    const deltaLine = Number(step.delta_line || 0);
    const deltaSheet = Number(step.delta_sheet || 0);
    const total = deltaUnit + deltaLine + deltaSheet;

    if (total) {
        return formatPricingSheetCurrency(total);
    }

    if ((step.type || "").trim().toLowerCase() === "percentage") {
        return formatPricingSheetPercent(step.value || 0);
    }

    return formatPricingSheetCurrency(step.value || 0);
}

function getPricingSheetWorkspaceBreakdownMeta(step) {
    const parts = [];
    if ((step.type || "").trim().toLowerCase() === "percentage") {
        parts.push(formatPricingSheetPercent(step.value || 0));
    }
    if (step.scope) {
        parts.push(__(step.scope));
    }
    if (step.applies_to && step.applies_to !== "Base Price") {
        parts.push(__(step.applies_to));
    }
    if (!parts.length) {
        return "";
    }

    return `<small class="ps-workspace-breakdown-step-meta">${escapePricingSheetText(parts.join(" · "))}</small>`;
}

function getPricingSheetWorkspaceAlertsHtml(frm) {
    const alerts = getPricingSheetWorkspaceAlerts(frm);
    if (!alerts.length) {
        return `
            <div class="ps-workspace-empty">
                <div class="ps-workspace-empty-title">${__("No alerts")}</div>
            </div>
        `;
    }

    return `
        <div class="ps-workspace-alert-list">
            ${alerts.map((alert) => `
                <div class="ps-workspace-alert-card is-${alert.tone}">
                    <div class="ps-workspace-alert-title">${alert.title}</div>
                    <div class="ps-workspace-alert-body">${alert.body}</div>
                </div>
            `).join("")}
        </div>
    `;
}

function focusPricingSheetNativeGrid(frm) {
    const field = frm.fields_dict.lines;
    if (!field || !field.$wrapper || !field.$wrapper.length) {
        return;
    }

    const element = field.$wrapper.get(0);
    element.scrollIntoView({ behavior: "smooth", block: "start" });
    field.$wrapper.addClass("ps-native-grid-target");
    clearTimeout(frm.__ps_native_grid_focus_timer);
    frm.__ps_native_grid_focus_timer = setTimeout(() => field.$wrapper.removeClass("ps-native-grid-target"), 1400);
}

function openPricingSheetLineEditor(frm, rowName) {
    if (!rowName) {
        return;
    }

    frm.refresh_field("lines");
    focusPricingSheetNativeGrid(frm);

    const openRow = () => {
        const grid = getPricingSheetGrid(frm);
        if (!grid) {
            return false;
        }
        const gridRow = grid.grid_rows_by_docname && grid.grid_rows_by_docname[rowName];
        if (gridRow && typeof gridRow.toggle_view === "function") {
            gridRow.toggle_view(true);
            return true;
        }
        return false;
    };

    if (!openRow()) {
        setTimeout(openRow, 0);
    }
}

function addPricingSheetLine(frm) {
    const row = frm.add_child("lines", { qty: 1 });
    frm.refresh_field("lines");
    frm.dirty();
    frm.__ps_workspace_focus = { rowName: row.name, fieldname: "item" };
    setPricingSheetWorkspaceSelectedRows(frm, [row.name]);
    schedulePricingSheetWorkspaceRefresh(frm);
}

function deletePricingSheetLine(frm, rowName) {
    const row = (frm.doc.lines || []).find((entry) => entry.name === rowName);
    if (!row) {
        return;
    }

    frappe.confirm(
        __("Remove line {0}?", [row.item || row.idx || row.name]),
        () => {
            frappe.model.clear_doc(row.doctype || "Pricing Sheet Item", row.name);
            frm.refresh_field("lines");
            frm.dirty();
            setPricingSheetWorkspaceSelectedRows(
                frm,
                getPricingSheetWorkspaceSelectedRows(frm).filter((selected) => selected !== row.name)
            );
            schedulePricingSheetWorkspaceRefresh(frm);
        }
    );
}

function deletePricingSheetWorkspaceSelectedRows(frm) {
    const selected = getPricingSheetWorkspaceSelectedRows(frm);
    if (!selected.length) {
        return;
    }

    frappe.confirm(
        __("Remove {0} selected row(s)?", [selected.length]),
        () => {
            selected.forEach((rowName) => {
                const row = (frm.doc.lines || []).find((entry) => entry.name === rowName);
                if (row) {
                    frappe.model.clear_doc(row.doctype || "Pricing Sheet Item", row.name);
                }
            });
            frm.refresh_field("lines");
            frm.dirty();
            setPricingSheetWorkspaceSelectedRows(frm, []);
            schedulePricingSheetWorkspaceRefresh(frm);
        }
    );
}

function getPricingSheetWorkspaceDisplayValue(frm, row, column) {
    if (!column) {
        return "";
    }

    const value = row[column.fieldname];
    if (column.fieldname === "benchmark_status") {
        return statusBadge(value);
    }
    if (column.fieldname === "margin_pct") {
        return psMarginBadge(derivePolicyMarginPercent(row, frm.doc.resolved_mode === "Static"));
    }
    if (column.fieldname === "margin_source") {
        return marginSourceBadge(value);
    }
    if (column.fieldtype === "Currency") {
        return formatPricingSheetCurrency(value || 0);
    }
    if (["Float", "Int"].includes(column.fieldtype)) {
        return formatPricingSheetFloat(value || 0);
    }
    if (column.fieldtype === "Percent") {
        return formatPricingSheetPercent(value || 0);
    }
    if (column.fieldtype === "Check") {
        return Number(value || 0) === 1 ? __("Yes") : "";
    }
    return escapePricingSheetText(value || "");
}

function getPricingSheetWorkspaceCellHtml(frm, row, column) {
    const value = row[column.fieldname];
    const alignClass = ["Currency", "Float", "Int", "Percent"].includes(column.fieldtype) ? "is-right" : "";
    if (!canInlineEditPricingSheetWorkspaceColumn(column)) {
        return `
            <td class="${alignClass}">
                <div class="ps-workspace-display-value">${getPricingSheetWorkspaceDisplayValue(frm, row, column)}</div>
            </td>
        `;
    }

    if (column.fieldtype === "Link") {
        return `
            <td>
                <div class="ps-workspace-link-host" data-ps-link-editor="1" data-row-name="${row.name}" data-fieldname="${column.fieldname}"></div>
            </td>
        `;
    }

    if (column.fieldtype === "Check") {
        return `
            <td>
                <label class="ps-workspace-inline-check">
                    <input type="checkbox" data-ps-cell-check="1" data-row-name="${row.name}" data-fieldname="${column.fieldname}" ${Number(value || 0) === 1 ? "checked" : ""}>
                </label>
            </td>
        `;
    }

    if (column.fieldtype === "Select") {
        const options = String(column.options || "")
            .split("\n")
            .map((option) => option.trim())
            .filter((option, index, list) => index === 0 || option || list[0] !== "");
        return `
            <td>
                <select class="ps-workspace-cell-input ${alignClass}" data-ps-cell-select="1" data-row-name="${row.name}" data-fieldname="${column.fieldname}">
                    ${options.map((option) => {
                        const selected = String(value || "") === option ? "selected" : "";
                        return `<option value="${escapePricingSheetText(option)}" ${selected}>${escapePricingSheetText(option || "-")}</option>`;
                    }).join("")}
                </select>
            </td>
        `;
    }

    const inputType = ["Float", "Currency", "Int", "Percent"].includes(column.fieldtype) ? "number" : "text";
    const step = column.fieldtype === "Int" ? "1" : "any";
    const fieldClass = column.fieldname === "qty" ? "ps-workspace-cell-input is-qty" : "ps-workspace-cell-input";
    return `
        <td>
            <input
                class="${fieldClass} ${alignClass}"
                data-ps-cell-input="1"
                data-row-name="${row.name}"
                data-fieldname="${column.fieldname}"
                type="${inputType}"
                step="${step}"
                value="${escapePricingSheetText(value ?? "")}">
        </td>
    `;
}

function getPricingSheetWorkspaceTableHtml(frm) {
    const lines = frm.doc.lines || [];
    const selectedFieldnames = getPricingSheetWorkspaceColumns(frm);
    const columns = getPricingSheetWorkspaceAllColumns(frm).filter((column) => selectedFieldnames.includes(column.fieldname));
    const selectedRows = new Set(getPricingSheetWorkspaceSelectedRows(frm));

    if (!lines.length) {
        return `
            <div class="ps-workspace-empty">
                <div class="ps-workspace-empty-title">${__("No items")}</div>
            </div>
        `;
    }

    const headerHtml = columns.map((column) => `
        <th class="${["Currency", "Float", "Int", "Percent"].includes(column.fieldtype) ? "is-right" : ""}">${escapePricingSheetText(__(column.label))}</th>
    `).join("");

    const bodyHtml = lines.map((row, index) => {
        const cellsHtml = columns.map((column) => getPricingSheetWorkspaceCellHtml(frm, row, column)).join("");

        return `
            <tr class="${selectedRows.has(row.name) ? "is-selected" : ""}" data-ps-row-name="${row.name}">
                <td class="ps-workspace-select-cell">
                    <input type="checkbox" data-ps-select-row="${row.name}" ${selectedRows.has(row.name) ? "checked" : ""}>
                </td>
                <td>
                    <div class="ps-workspace-item-cell">
                        <div class="ps-workspace-link-host ps-workspace-item-link" data-ps-link-editor="1" data-row-name="${row.name}" data-fieldname="item"></div>
                        <div class="ps-workspace-item-meta">
                            <span>#${escapePricingSheetText(row.idx || index + 1)}</span>
                            <span>${escapePricingSheetText(row.line_type || __("Standard"))}</span>
                        </div>
                    </div>
                </td>
                ${cellsHtml}
            </tr>
        `;
    }).join("");

    const allSelected = lines.length && selectedRows.size === lines.length;
    const selectedCount = selectedRows.size;

    return `
        <div class="ps-workspace-table-wrap">
            <table class="ps-workspace-table">
                <thead>
                    <tr>
                        <th class="ps-workspace-select-cell"><input type="checkbox" data-ps-select-all="1" ${allSelected ? "checked" : ""}></th>
                        <th>${__("Item")}</th>
                        ${headerHtml}
                    </tr>
                </thead>
                <tbody>${bodyHtml}</tbody>
            </table>
        </div>
        <div class="ps-workspace-footer">
            <div class="ps-workspace-footer-meta">${__("{0} selected", [selectedCount])}</div>
            <div class="ps-workspace-footer-actions">
                <div class="ps-workspace-column-menu">
                    <button class="btn btn-default btn-xs" type="button" data-ps-toggle-columns>${__("Columns")}</button>
                    <div class="ps-workspace-column-popover ${Boolean(frm.__ps_workspace_columns_open) ? "is-open" : ""}">
                        <div class="ps-workspace-column-title">${__("Columns")}</div>
                        ${getPricingSheetWorkspaceAllColumns(frm).map((column) => {
                            const checked = getPricingSheetWorkspaceColumns(frm).includes(column.fieldname) ? "checked" : "";
                            return `
                                <label class="ps-workspace-column-option">
                                    <input type="checkbox" data-ps-column="${column.fieldname}" ${checked}>
                                    <span>${escapePricingSheetText(__(column.label))}</span>
                                </label>
                            `;
                        }).join("")}
                    </div>
                </div>
                <button class="btn btn-default btn-xs" type="button" data-ps-delete-selected ${selectedCount ? "" : "disabled"}>${__("Delete")}</button>
                <button class="btn btn-primary btn-xs" type="button" data-ps-add-line>${__("Add Row")}</button>
            </div>
        </div>
    `;
}

function mountPricingSheetWorkspaceLinkEditors(frm, $root) {
    $root.find("[data-ps-link-editor]").each((_, element) => {
        const host = element;
        const rowName = host.getAttribute("data-row-name");
        const fieldname = host.getAttribute("data-fieldname");
        const row = (frm.doc.lines || []).find((entry) => entry.name === rowName);
        const column = fieldname === "item"
            ? { fieldname: "item", label: __("Item"), fieldtype: "Link", options: "Item", read_only: false }
            : getPricingSheetWorkspaceColumn(frm, fieldname);
        if (!row || !column) {
            return;
        }

        host.innerHTML = "";
        const control = frappe.ui.form.make_control({
            parent: host,
            only_input: true,
            render_input: true,
            df: {
                fieldname,
                fieldtype: "Link",
                label: column.label,
                options: column.options,
                get_query: () => getPricingSheetWorkspaceQuery(fieldname),
                change: async function () {
                    if (host.dataset.psLinkSync === "1") {
                        return;
                    }
                    const nextValue = control.get_value() || "";
                    if (String(row[fieldname] || "") === String(nextValue)) {
                        return;
                    }
                    await updatePricingSheetWorkspaceField(frm, rowName, fieldname, nextValue);
                },
            },
        });
        control.refresh();
        host.dataset.psLinkSync = "1";
        control.set_value(row[fieldname] || "");
        setTimeout(() => {
            delete host.dataset.psLinkSync;
        }, 0);
        if (control.$input) {
            control.$input.addClass("ps-workspace-cell-input ps-workspace-link-input");
            control.$input.attr("autocomplete", "off");
        }

        const focusState = frm.__ps_workspace_focus;
        if (focusState && focusState.rowName === rowName && focusState.fieldname === fieldname && control.$input) {
            setTimeout(() => control.$input.trigger("focus"), 0);
            frm.__ps_workspace_focus = null;
        }
    });
}

function bindPricingSheetWorkspaceInlineInputs(frm, $root) {
    const commitValue = async (element) => {
        const rowName = element.getAttribute("data-row-name");
        const fieldname = element.getAttribute("data-fieldname");
        const column = getPricingSheetWorkspaceColumn(frm, fieldname);
        if (!rowName || !fieldname || !column) {
            return;
        }

        let value;
        if (element.hasAttribute("data-ps-cell-check")) {
            value = element.checked ? 1 : 0;
        } else {
            value = element.value;
            if (["Currency", "Float", "Int", "Percent"].includes(column.fieldtype)) {
                value = value === "" ? 0 : value;
            }
        }

        await updatePricingSheetWorkspaceField(frm, rowName, fieldname, value);
    };

    $root.find("[data-ps-cell-input], [data-ps-cell-select], [data-ps-cell-check]").on("change", async (event) => {
        await commitValue(event.currentTarget);
    });

    $root.find("[data-ps-cell-input]").on("keydown", async (event) => {
        if (event.key !== "Enter") {
            return;
        }
        event.preventDefault();
        await commitValue(event.currentTarget);
        event.currentTarget.blur();
    });
}

function renderPricingSheetWorkspace(frm) {
    const $root = getPricingSheetWorkspaceRoot(frm);
    if (!$root || !$root.length) {
        return;
    }

    setPricingSheetWorkspaceSelectedRows(frm, getPricingSheetWorkspaceSelectedRows(frm));
    const activeTab = frm.__ps_workspace_tab || "items";
    const restrictedAgent = isRestrictedAgentUser();
    const summaryCards = getPricingSheetWorkspaceSummary(frm).map((card) => `
        <div class="ps-workspace-kpi-card">
            <div class="ps-workspace-kpi-label">${escapePricingSheetText(card.label)}</div>
            <div class="ps-workspace-kpi-value">${card.value}</div>
        </div>
    `).join("");

    $root.html(`
        <section class="ps-workspace-shell">
            <div class="ps-workspace-header">
                <div class="ps-workspace-eyebrow">${__("Pricing Dashboard")}</div>
            </div>
            <div class="ps-workspace-kpi-grid">${summaryCards}</div>
            <div class="ps-workspace-tabs">
                <button class="ps-workspace-tab ${activeTab === "items" ? "is-active" : ""}" type="button" data-ps-tab="items">${__("Items")}</button>
                ${restrictedAgent ? "" : `<button class="ps-workspace-tab ${activeTab === "breakdown" ? "is-active" : ""}" type="button" data-ps-tab="breakdown">${__("Breakdown")}</button><button class="ps-workspace-tab ${activeTab === "alerts" ? "is-active" : ""}" type="button" data-ps-tab="alerts">${__("Alerts")}</button>`}
            </div>
            <div class="ps-workspace-panels">
                <div class="ps-workspace-panel ${activeTab === "items" ? "is-active" : ""}" data-ps-panel="items">
                    ${getPricingSheetWorkspaceTableHtml(frm)}
                </div>
                <div class="ps-workspace-panel ${!restrictedAgent && activeTab === "breakdown" ? "is-active" : ""}" data-ps-panel="breakdown">
                    ${getPricingSheetWorkspaceBreakdownHtml(frm)}
                </div>
                <div class="ps-workspace-panel ${!restrictedAgent && activeTab === "alerts" ? "is-active" : ""}" data-ps-panel="alerts">
                    ${getPricingSheetWorkspaceAlertsHtml(frm)}
                </div>
            </div>
        </section>
    `);

    $root.find("[data-ps-tab]").on("click", (event) => {
        frm.__ps_workspace_tab = event.currentTarget.getAttribute("data-ps-tab") || "items";
        renderPricingSheetWorkspace(frm);
    });

    $root.find("[data-ps-toggle-columns]").on("click", () => {
        frm.__ps_workspace_columns_open = !frm.__ps_workspace_columns_open;
        renderPricingSheetWorkspace(frm);
    });

    $root.find("[data-ps-column]").on("change", (event) => {
        const fieldname = event.currentTarget.getAttribute("data-ps-column");
        const next = new Set(getPricingSheetWorkspaceColumns(frm));
        if (event.currentTarget.checked) {
            next.add(fieldname);
        } else {
            next.delete(fieldname);
        }
        setPricingSheetWorkspaceColumns(frm, Array.from(next));
        renderPricingSheetWorkspace(frm);
    });

    $root.find("[data-ps-add-line]").on("click", () => addPricingSheetLine(frm));
    $root.find("[data-ps-delete-selected]").on("click", () => {
        deletePricingSheetWorkspaceSelectedRows(frm);
    });

    $root.find("[data-ps-select-all]").on("change", (event) => {
        setPricingSheetWorkspaceSelectedRows(
            frm,
            event.currentTarget.checked ? (frm.doc.lines || []).map((row) => row.name) : []
        );
        renderPricingSheetWorkspace(frm);
    });

    $root.find("[data-ps-select-row]").on("change", (event) => {
        togglePricingSheetWorkspaceRowSelection(
            frm,
            event.currentTarget.getAttribute("data-ps-select-row"),
            event.currentTarget.checked
        );
        renderPricingSheetWorkspace(frm);
    });

    $root.find("[data-ps-row-name]").on("click", (event) => {
        if ($(event.target).closest("button, input, label, a, select, textarea, .awesomplete").length) {
            return;
        }
        const rowName = event.currentTarget.getAttribute("data-ps-row-name");
        const isSelected = getPricingSheetWorkspaceSelectedRows(frm).includes(rowName);
        togglePricingSheetWorkspaceRowSelection(frm, rowName, !isSelected);
        renderPricingSheetWorkspace(frm);
    });

    mountPricingSheetWorkspaceLinkEditors(frm, $root);
    bindPricingSheetWorkspaceInlineInputs(frm, $root);
}

function ensurePricingSheetStyles(frm) {
    const linkId = "pricing-sheet-ux-css";
    const version = "v=20260409-77";
    let link = document.getElementById(linkId);
    if (!link) {
        link = document.createElement("link");
        link.id = linkId;
        link.rel = "stylesheet";
        document.head.appendChild(link);
    }
    const expected = `/assets/orderlift/css/pricing_sheet_20260409_68.css?${version}`;
    if (link.href !== expected) link.href = expected;
}


function resolveSuggestedBuyingPriceList(frm, row) {
    const explicit = ((row && row.source_buying_price_list) || "").trim();
    if (explicit) {
        return explicit;
    }

    const mappedLists = [...new Set((frm.doc.scenario_mappings || [])
        .filter((entry) => Number(entry.is_active ?? 1) !== 0)
        .map((entry) => (entry.source_buying_price_list || "").trim())
        .filter(Boolean))];

    if (mappedLists.length === 1) {
        return mappedLists[0];
    }

    return "";
}

function highlightPricingSheetSidebar() {
    const items = document.querySelectorAll('.desk-sidebar .standard-sidebar-item');
    items.forEach((item) => item.classList.remove('ps-route-selected'));

    const candidate = Array.from(items).find((item) => {
        const text = (item.textContent || '').trim();
        const href = item.querySelector('a')?.getAttribute('href') || '';
        return text.includes('Pricing Sheet') || href.includes('/app/pricing-sheet');
    });

    if (candidate) {
        candidate.classList.add('ps-route-selected');
    }
}

function sanitizeLineResolutionFields(frm) {
    (frm.doc.lines || []).forEach((row) => {
        if ((row.resolved_pricing_scenario || '').trim() === '__NO_EXPENSES_POLICY__') {
            row.resolved_pricing_scenario = '';
        }
        if ((row.scenario_source || '').trim() === 'Simulator Fallback') {
            row.scenario_source = 'Draft Fallback';
        }
        if ((row.scenario_source || '').trim() === 'Sheet Mapping') {
            row.scenario_source = 'Policy Rule';
        }
    });
}

function hasActivePolicyMappings(frm) {
    return (frm.doc.scenario_mappings || []).some((row) => Number(row.is_active ?? 1) !== 0);
}

function getFallbackPolicyMapping(frm) {
    return (frm.doc.scenario_mappings || []).find((row) => {
        return Number(row.is_active ?? 1) !== 0 && !((row.source_buying_price_list || "").trim());
    });
}

function ensureFallbackPolicyMapping(frm, selected) {
    if (!selected || !selected.pricing_scenario) {
        return;
    }

    let row = getFallbackPolicyMapping(frm);
    if (!row && !hasActivePolicyMappings(frm)) {
        frm.add_child("scenario_mappings", {
            source_buying_price_list: "",
            pricing_scenario: selected.pricing_scenario,
            customs_policy: selected.customs_policy || "",
            benchmark_policy: selected.benchmark_policy || "",
            priority: 10,
            is_active: 1,
            notes: __("Fallback mapping"),
        });
        frm.refresh_field("scenario_mappings");
        return;
    }

    if (!row) {
        return;
    }

    let changed = false;
    if (!row.pricing_scenario && selected.pricing_scenario) {
        row.pricing_scenario = selected.pricing_scenario;
        changed = true;
    }
    if (!row.customs_policy && selected.customs_policy) {
        row.customs_policy = selected.customs_policy;
        changed = true;
    }
    if (!row.benchmark_policy && selected.benchmark_policy) {
        row.benchmark_policy = selected.benchmark_policy;
        changed = true;
    }
    if (!row.priority) {
        row.priority = 10;
        changed = true;
    }
    if (changed) {
        frm.refresh_field("scenario_mappings");
    }
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

function applyLinesSectionClass(frm) {
    const field = frm.fields_dict.lines;
    if (!field || !field.$wrapper) return;

    const $section = field.$wrapper.closest(".form-section");
    if ($section && $section.length) {
        $section.addClass("ps-lines-section");
    }
}

function applyPricingStrategyVisibility(frm) {
    const isStatic = frm.doc.resolved_mode === "Static";
    frm.set_df_property("pricing_scenario", "reqd", 0);
    ["pricing_scenario", "benchmark_policy", "customs_policy"].forEach((fieldname) => {
        frm.toggle_display(fieldname, false);
    });

    const anchorField = frm.fields_dict.pricing_scenario || frm.fields_dict.selected_price_list;
    if (!anchorField || !anchorField.$wrapper) return;

    const $section = anchorField.$wrapper.closest(".form-section");
    if ($section && $section.length) {
        $section.toggle(isStatic);
    }
}

function applyModeLayout(frm) {
    const mode = frm.doc.resolved_mode || "";
    const isStatic = mode === "Static";
    const restrictedAgent = isRestrictedAgentUser();

    applyNativeLinesGridProperties(frm);

    // Mode indicator badge in page subtitle area
    frm.page.wrapper.find(".ps-mode-badge").remove();
    const badgeColor = isStatic ? "#6366f1" : "#16a34a";
    const badgeLabel = isStatic ? "📋 Static" : "⚙ Dynamic";
    frm.page.wrapper.find(".page-form.flex-between, .page-head .page-title").first()
        .append(`<span class="ps-mode-badge" style="background:${badgeColor};color:#fff;border-radius:20px;padding:2px 12px;font-size:11px;font-weight:700;margin-left:10px;display:inline-block;vertical-align:middle;">${badgeLabel}</span>`);

    // Dynamic-only fields — visible only in dynamic mode
    const dynamicFields = ["benchmark_policy", "customs_policy", "pricing_scenario"];
    // Static-only fields
    const staticFields = ["selected_price_list"];

    dynamicFields.forEach(fn => frm.toggle_display(fn, !isStatic));
    staticFields.forEach(fn => frm.toggle_display(fn, isStatic));

    if (restrictedAgent) {
        [
            "pricing_scenario", "benchmark_policy", "customs_policy", "selected_price_list",
            "scenario_mappings",
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

function psMarginBadge(pct) {
    const v = Number(pct || 0);
    const cls = v >= 20 ? "ps-mgn-good" : v >= 10 ? "ps-mgn-mid" : "ps-mgn-bad";
    return `<span class="${cls}">${v.toFixed(1)}%</span>`;
}

function derivePolicyMarginPercent(row, isStatic) {
    if (isStatic) {
        return Number(row.margin_pct || 0);
    }

    const ruleText = (row.resolved_benchmark_rule || "").trim();
    const ruleMatch = ruleText.match(/:\s*([0-9.]+)%/);
    if (ruleMatch) {
        return Number(ruleMatch[1] || 0);
    }

    try {
        const steps = JSON.parse(row.pricing_breakdown_json || "[]");
        const policyStep = steps.find((step) => {
            const label = String(step.label || "");
            return label.startsWith("Dynamic Margin") || label.startsWith("Fallback Margin");
        });
        if (policyStep && String(policyStep.type || "").toLowerCase() === "percentage") {
            return Number(policyStep.value || 0);
        }
    } catch (e) {
        // ignore malformed breakdown payload
    }

    return Number(row.margin_pct || 0);
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

    if (isRestrictedAgentUser()) {
        ensureFallbackPolicyMapping(frm, context.selected || {});
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
        if (frm.fields_dict.lines.grid.get_field("margin_pct")) {
            frm.fields_dict.lines.grid.get_field("margin_pct").formatter = (value, df, options, doc) => {
                return psMarginBadge(derivePolicyMarginPercent(doc || {}, frm.doc.resolved_mode === "Static"));
            };
        }
        if (frm.fields_dict.lines.grid.get_field("margin_source")) {
            frm.fields_dict.lines.grid.get_field("margin_source").formatter = (value) => marginSourceBadge(value);
        }
    },

    refresh(frm) {
        ensurePricingSheetStyles(frm);
        sanitizeLineResolutionFields(frm);
        applyFormLayoutClass(frm);
        applyLinesSectionClass(frm);
        bindPricingSheetWorkspaceGridSync(frm);
        renderPricingSheetWorkspace(frm);
        applyModeLayout(frm);
        applyPricingStrategyVisibility(frm);
        highlightPricingSheetSidebar();
        $(document).off("keydown.psheet");

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

        renderDimensioningTool(frm);
        setTimeout(() => collapseAdvancedSections(frm), 0);
        if (frm.doc.sales_person) {
            frm.events.sales_person(frm);
        }
    },

    validate(frm) {
        sanitizeLineResolutionFields(frm);
        schedulePricingSheetWorkspaceRefresh(frm);
    },

    before_save(frm) {
        sanitizeLineResolutionFields(frm);
        frm.refresh_field("lines");
        schedulePricingSheetWorkspaceRefresh(frm);
    },

    lines_add(frm) {
        schedulePricingSheetWorkspaceRefresh(frm);
    },

    lines_remove(frm) {
        schedulePricingSheetWorkspaceRefresh(frm);
    },

    async customer(frm) {
        if (!frm.doc.customer) {
            frm.set_value("customer_type", "");
            frm.set_value("tier", "");
            return;
        }

        const response = await frappe.db.get_value("Customer", frm.doc.customer, ["customer_group", "tier"]);
        const values = response.message || {};
        await frm.set_value("customer_type", values.customer_group || "");
        await frm.set_value("tier", values.tier || "");
    },

    dimensioning_set(frm) {
        frm.doc.dimensioning_inputs_json = "";
        renderDimensioningTool(frm);
    },

    async sales_person(frm) {
        await applyAgentDynamicDefaults(frm);
    },
});

frappe.ui.form.on("Pricing Sheet Item", {
    item(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.item) {
            schedulePricingSheetWorkspaceRefresh(frm);
            return;
        }

        const resolvedBuyingList = resolveSuggestedBuyingPriceList(frm, row);
        if (!row.source_buying_price_list && resolvedBuyingList) {
            frappe.model.set_value(cdt, cdn, "source_buying_price_list", resolvedBuyingList);
        }

        frappe.call({
            method: "orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet.get_item_pricing_defaults",
            args: {
                item_code: row.item,
                pricing_scenario: row.pricing_scenario,
                source_buying_price_list: resolvedBuyingList || row.source_buying_price_list,
            },
            callback: (r) => {
                const data = r.message || {};
                if (!row.buy_price || row.buy_price <= 0) {
                    frappe.model.set_value(cdt, cdn, "buy_price", data.buy_price || 0);
                }
                if (!row.display_group) {
                    frappe.model.set_value(cdt, cdn, "display_group", data.item_group || "Ungrouped");
                }
                frm.refresh_field("lines");
                schedulePricingSheetWorkspaceRefresh(frm);
            },
        });
    },

    source_buying_price_list(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.item) {
            schedulePricingSheetWorkspaceRefresh(frm);
            return;
        }

        const resolvedBuyingList = resolveSuggestedBuyingPriceList(frm, row);

        frappe.call({
            method: "orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet.get_item_pricing_defaults",
            args: {
                item_code: row.item,
                pricing_scenario: row.pricing_scenario,
                source_buying_price_list: resolvedBuyingList || row.source_buying_price_list,
            },
            callback: (r) => {
                const data = r.message || {};
                frappe.model.set_value(cdt, cdn, "buy_price", data.buy_price || 0);
                frm.refresh_field("lines");
                schedulePricingSheetWorkspaceRefresh(frm);
            },
        });
    },

    qty(frm) {
        schedulePricingSheetWorkspaceRefresh(frm);
    },

    display_group(frm) {
        schedulePricingSheetWorkspaceRefresh(frm);
    },

    pricing_scenario(frm) {
        schedulePricingSheetWorkspaceRefresh(frm);
    },

    manual_sell_unit_price(frm) {
        schedulePricingSheetWorkspaceRefresh(frm);
    },

    discount_percent(frm) {
        schedulePricingSheetWorkspaceRefresh(frm);
    },

    show_in_detail(frm) {
        schedulePricingSheetWorkspaceRefresh(frm);
    },

    form_render(frm) {
        schedulePricingSheetWorkspaceRefresh(frm);
    },
});
