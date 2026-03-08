const PB_DEFAULT_COLUMNS = [
    "select",
    "item",
    "item_group",
    "buying_list",
    "origin",
    "base_buy_price",
    "expenses",
    "avg_benchmark",
    "projected_price",
    "override_selling_price",
    "final_margin_pct",
    "published_price",
    "status",
];

const PB_COLUMN_LABELS = {
    select: __("Sel"),
    item: __("Article"),
    item_group: __("Item Group"),
    buying_list: __("Buying List"),
    origin: __("Origin"),
    base_buy_price: __("Base Buy Price"),
    expenses: __("Expenses"),
    avg_benchmark: __("Avg Bench"),
    projected_price: __("Projected Price"),
    override_selling_price: __("Override Selling Price"),
    final_margin_pct: __("Final Margin %"),
    published_price: __("Published Price"),
    status: __("Status"),
};

frappe.pages["pricing-builder"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Pricing Builder"),
        single_column: true,
    });

    const state = {
        page,
        controls: {},
        ruleRows: [],
        rows: [],
        warnings: [],
        summary: {},
        visibleColumns: loadVisibleColumns(),
    };

    injectStyles();
    buildLayout(state);
    addRuleRow(state, {});
};

function buildLayout(state) {
    const root = $(`
        <div class="pb-root">
            <div class="pb-card">
                <div class="pb-card-head">
                    <div>
                        <div class="pb-title">${__("Builder Setup")}</div>
                        <div class="pb-subtitle">${__("Create a new selling price list from buying lists and pricing policies.")}</div>
                    </div>
                    <div class="pb-actions">
                        <button class="btn btn-primary btn-sm" data-action="calculate">${__("Load Items & Calculate")}</button>
                    </div>
                </div>
                <div class="pb-grid" data-role="filters"></div>
            </div>

            <div class="pb-card">
                <div class="pb-card-head">
                    <div>
                        <div class="pb-title">${__("Sourcing Rules (Buying Lists & Policies)")}</div>
                        <div class="pb-subtitle">${__("One row per buying list. Add a blank buying list only if you need a fallback row.")}</div>
                    </div>
                    <div class="pb-actions">
                        <button class="btn btn-default btn-sm" data-action="add-rule">${__("Add Row")}</button>
                    </div>
                </div>
                <div class="pb-table-wrap">
                    <table class="pb-table pb-table--rules">
                        <thead>
                            <tr>
                                <th>${__("Buying Price List")}</th>
                                <th>${__("Expenses Policy")}</th>
                                <th>${__("Customs Policy")}</th>
                                <th>${__("Margin Policy")}</th>
                                <th class="pb-cell-action"></th>
                            </tr>
                        </thead>
                        <tbody data-role="rules-body"></tbody>
                    </table>
                </div>
            </div>

            <div class="pb-card">
                <div class="pb-card-head">
                    <div>
                        <div class="pb-title">${__("Results")}</div>
                        <div class="pb-subtitle" data-role="summary"></div>
                    </div>
                    <div class="pb-actions">
                        <button class="btn btn-default btn-sm" data-action="columns">⚙ ${__("Columns")}</button>
                        <button class="btn btn-default btn-sm" data-action="publish-selected">${__("Publish Selected")}</button>
                        <button class="btn btn-primary btn-sm" data-action="publish-all">${__("Publish All")}</button>
                    </div>
                </div>
                <div class="pb-alerts" data-role="warnings"></div>
                <div class="pb-table-wrap" data-role="results-wrap"></div>
            </div>
        </div>
    `);

    state.page.main.append(root);
    state.root = root;
    state.rulesBody = root.find('[data-role="rules-body"]');
    state.resultsWrap = root.find('[data-role="results-wrap"]');
    state.summaryEl = root.find('[data-role="summary"]');
    state.warningsEl = root.find('[data-role="warnings"]');

    const filterWrap = root.find('[data-role="filters"]');
    state.controls = {
        selling_price_list_name: makeControl(filterWrap, {
            fieldname: "selling_price_list_name",
            label: __("Selling Price List Name"),
            fieldtype: "Data",
            reqd: 1,
            description: __("A new selling price list will be created if this name does not already exist."),
        }),
        item_group: makeControl(filterWrap, {
            fieldname: "item_group",
            label: __("Item Group"),
            fieldtype: "Link",
            options: "Item Group",
        }),
        default_qty: makeControl(filterWrap, {
            fieldname: "default_qty",
            label: __("Qty per Item"),
            fieldtype: "Float",
            default: 1,
        }),
        max_items: makeControl(filterWrap, {
            fieldname: "max_items",
            label: __("Max Items"),
            fieldtype: "Int",
            default: 0,
            description: __("0 loads all items found in the selected buying lists."),
        }),
    };

    root.on("click", '[data-action="add-rule"]', () => addRuleRow(state, {}));
    root.on("click", '[data-action="calculate"]', () => calculateBuilder(state));
    root.on("click", '[data-action="publish-selected"]', () => publishRows(state, true));
    root.on("click", '[data-action="publish-all"]', () => publishRows(state, false));
    root.on("click", '[data-action="columns"]', () => openColumnDialog(state));
    root.on("click", ".pb-remove-rule", function () {
        removeRuleRow(state, $(this).closest("tr").data("rowId"));
    });
    root.on("input", ".pb-override-input", function () {
        const idx = Number($(this).data("rowIndex"));
        const value = flt($(this).val());
        if (!state.rows[idx]) return;
        state.rows[idx].override_selling_price = value || 0;
        state.rows[idx].final_margin_pct = marginPct(value || state.rows[idx].projected_price, state.rows[idx].base_buy_price);
        state.rows[idx].publish_state = publishState(value || state.rows[idx].projected_price, state.rows[idx].published_price);
        renderResults(state);
    });
    root.on("change", ".pb-select-row", function () {
        const idx = Number($(this).data("rowIndex"));
        if (state.rows[idx]) state.rows[idx].selected = $(this).is(":checked") ? 1 : 0;
    });

    renderResults(state);
}

function makeControl(parent, df) {
    const wrap = $('<div class="pb-field"></div>').appendTo(parent);
    const control = frappe.ui.form.make_control({ parent: wrap, df, render_input: true });
    control.refresh();
    if (df.default !== undefined) control.set_value(df.default);
    return control;
}

function addRuleRow(state, values) {
    const rowId = `r${Date.now()}${Math.floor(Math.random() * 1000)}`;
    const tr = $(`
        <tr data-row-id="${rowId}">
            <td class="pb-cell-buying"></td>
            <td class="pb-cell-scenario"></td>
            <td class="pb-cell-customs"></td>
            <td class="pb-cell-benchmark"></td>
            <td class="pb-cell-action"><button class="btn btn-xs btn-danger pb-remove-rule">${__("Remove")}</button></td>
        </tr>
    `);
    state.rulesBody.append(tr);

    const controls = {
        buying_price_list: makeControl(tr.find(".pb-cell-buying"), {
            fieldname: `buying_price_list_${rowId}`,
            fieldtype: "Link",
            options: "Price List",
            label: "",
            get_query: () => ({ filters: { buying: 1 } }),
        }),
        pricing_scenario: makeControl(tr.find(".pb-cell-scenario"), {
            fieldname: `pricing_scenario_${rowId}`,
            fieldtype: "Link",
            options: "Pricing Scenario",
            label: "",
        }),
        customs_policy: makeControl(tr.find(".pb-cell-customs"), {
            fieldname: `customs_policy_${rowId}`,
            fieldtype: "Link",
            options: "Pricing Customs Policy",
            label: "",
            get_query: () => ({ filters: { is_active: 1 } }),
        }),
        benchmark_policy: makeControl(tr.find(".pb-cell-benchmark"), {
            fieldname: `benchmark_policy_${rowId}`,
            fieldtype: "Link",
            options: "Pricing Benchmark Policy",
            label: "",
            get_query: () => ({ filters: { is_active: 1 } }),
        }),
    };

    Object.entries(values || {}).forEach(([key, value]) => {
        if (controls[key]) controls[key].set_value(value);
    });

    state.ruleRows.push({ rowId, tr, controls });
}

function removeRuleRow(state, rowId) {
    if (state.ruleRows.length <= 1) {
        frappe.show_alert({ message: __("Keep at least one sourcing rule row."), indicator: "orange" });
        return;
    }
    state.ruleRows = state.ruleRows.filter((row) => {
        if (row.rowId === rowId) {
            row.tr.remove();
            return false;
        }
        return true;
    });
}

function collectRules(state) {
    return state.ruleRows.map((row) => ({
        buying_price_list: row.controls.buying_price_list.get_value() || "",
        pricing_scenario: row.controls.pricing_scenario.get_value() || "",
        customs_policy: row.controls.customs_policy.get_value() || "",
        benchmark_policy: row.controls.benchmark_policy.get_value() || "",
        is_active: 1,
    }));
}

async function calculateBuilder(state) {
    const payload = {
        selling_price_list_name: state.controls.selling_price_list_name.get_value() || "",
        item_group: state.controls.item_group.get_value() || "",
        default_qty: state.controls.default_qty.get_value() || 1,
        max_items: state.controls.max_items.get_value() || 0,
        sourcing_rules: collectRules(state),
    };

    state.page.set_indicator(__("Calculating"), "orange");
    try {
        const response = await frappe.call({
            method: "orderlift.orderlift_sales.page.pricing_builder.pricing_builder.calculate_builder",
            args: { payload: JSON.stringify(payload) },
            freeze: true,
            freeze_message: __("Calculating builder prices..."),
        });
        const message = response.message || {};
        state.rows = (message.rows || []).map((row) => ({
            ...row,
            selected: ["Ready", "No Benchmark"].includes(row.status) ? 1 : 0,
        }));
        state.warnings = message.warnings || [];
        state.summary = message.summary || {};
        renderResults(state);
        state.page.set_indicator(__("Ready"), "green");
    } catch (error) {
        state.page.set_indicator(__("Error"), "red");
        throw error;
    }
}

function renderResults(state) {
    renderSummary(state);
    renderWarnings(state);

    if (!state.rows.length) {
        state.resultsWrap.html(`<div class="pb-empty">${__("Add sourcing rules and run the builder.")}</div>`);
        return;
    }

    const visibleColumns = state.visibleColumns.filter((key) => PB_COLUMN_LABELS[key]);
    const thead = visibleColumns.map((key) => {
        const cls = isNumericColumn(key) ? ' class="is-num"' : "";
        return `<th${cls}>${PB_COLUMN_LABELS[key]}</th>`;
    }).join("");

    const body = state.rows.map((row, index) => {
        const finalPrice = flt(row.override_selling_price || 0) || flt(row.projected_price || 0);
        const badgeClass = badgeClassForStatus(row.status);
        const cells = visibleColumns.map((key) => renderCell(key, row, index, finalPrice, badgeClass));
        return `<tr>${cells.join("")}</tr>`;
    }).join("");

    state.resultsWrap.html(`
        <table class="pb-table pb-table--results">
            <thead><tr>${thead}</tr></thead>
            <tbody>${body}</tbody>
        </table>
    `);
}

function renderCell(key, row, index, finalPrice, badgeClass) {
    if (key === "select") {
        return `<td><input type="checkbox" class="pb-select-row" data-row-index="${index}" ${Number(row.selected || 0) ? "checked" : ""}></td>`;
    }
    if (key === "item") {
        return `<td><div class="pb-item-code">${frappe.utils.escape_html(row.item || "")}</div><div class="pb-item-name">${frappe.utils.escape_html(row.item_name || "")}</div></td>`;
    }
    if (key === "item_group") {
        return `<td>${frappe.utils.escape_html(row.item_group || "-")}</td>`;
    }
    if (key === "buying_list") {
        return `<td>${frappe.utils.escape_html(row.buying_list || "")}</td>`;
    }
    if (key === "origin") {
        return `<td>${frappe.utils.escape_html(row.origin || "-")}</td>`;
    }
    if (key === "base_buy_price") {
        return `<td class="is-num">${fmtCurrency(row.base_buy_price)}</td>`;
    }
    if (key === "expenses") {
        return `<td class="is-num">${fmtCurrency(row.expenses)}</td>`;
    }
    if (key === "avg_benchmark") {
        return `<td class="is-num">${fmtCurrency(row.avg_benchmark)}</td>`;
    }
    if (key === "projected_price") {
        return `<td class="is-num">${fmtCurrency(row.projected_price)}</td>`;
    }
    if (key === "override_selling_price") {
        return `<td class="is-num"><input type="number" step="0.01" min="0" class="pb-override-input" data-row-index="${index}" value="${flt(row.override_selling_price || 0) || ""}"></td>`;
    }
    if (key === "final_margin_pct") {
        return `<td class="is-num">${frappe.format(row.final_margin_pct || marginPct(finalPrice, row.base_buy_price), { fieldtype: "Percent" })}</td>`;
    }
    if (key === "published_price") {
        return `<td class="is-num">${fmtCurrency(row.published_price)}</td>`;
    }
    if (key === "status") {
        return `<td><span class="pb-badge ${badgeClass}">${frappe.utils.escape_html(row.status || "Ready")}</span><div class="pb-note">${frappe.utils.escape_html(row.publish_state || "")}${row.status_note ? ` - ${frappe.utils.escape_html(row.status_note)}` : ""}</div></td>`;
    }
    return `<td></td>`;
}

function renderSummary(state) {
    const s = state.summary || {};
    state.summaryEl.text(
        __(
            "Items: {0} | Ready: {1} | Changed: {2} | New: {3} | Missing: {4}",
            [s.item_count || 0, s.ready_count || 0, s.changed_count || 0, s.new_count || 0, s.missing_count || 0]
        )
    );
}

function renderWarnings(state) {
    if (!state.warnings.length) {
        state.warningsEl.empty();
        return;
    }
    state.warningsEl.html(state.warnings.map((msg) => `<div class="pb-warning">${frappe.utils.escape_html(msg)}</div>`).join(""));
}

async function publishRows(state, selectedOnly) {
    const name = state.controls.selling_price_list_name.get_value() || "";
    if (!name) {
        frappe.throw(__("Enter the Selling Price List Name before publishing."));
    }
    if (!state.rows.length) {
        frappe.throw(__("Run the builder before publishing."));
    }

    const response = await frappe.call({
        method: "orderlift.orderlift_sales.page.pricing_builder.pricing_builder.publish_builder_prices",
        args: {
            payload: JSON.stringify({
                selling_price_list_name: name,
                selected_only: selectedOnly ? 1 : 0,
                rows: state.rows,
            }),
        },
        freeze: true,
        freeze_message: __("Publishing prices..."),
    });

    const out = response.message || {};
    const parts = [
        __("Price List: {0}", [out.price_list || name]),
        __("Created: {0}", [out.created || 0]),
        __("Updated: {0}", [out.updated || 0]),
        __("Skipped: {0}", [out.skipped || 0]),
    ];
    if ((out.errors || []).length) parts.push(__("Errors: {0}", [(out.errors || []).length]));
    frappe.show_alert({ message: parts.join(" | "), indicator: (out.errors || []).length ? "orange" : "green" }, 8);
    await calculateBuilder(state);
}

function openColumnDialog(state) {
    const dialog = new frappe.ui.Dialog({
        title: __("Choose Visible Columns"),
        fields: Object.keys(PB_COLUMN_LABELS).map((key) => ({
            fieldtype: "Check",
            fieldname: key,
            label: PB_COLUMN_LABELS[key],
            default: state.visibleColumns.includes(key) ? 1 : 0,
        })),
        primary_action_label: __("Apply"),
        primary_action(values) {
            const selected = Object.keys(PB_COLUMN_LABELS).filter((key) => values[key]);
            state.visibleColumns = selected.length ? selected : [...PB_DEFAULT_COLUMNS];
            saveVisibleColumns(state.visibleColumns);
            dialog.hide();
            renderResults(state);
        },
    });
    dialog.show();
}

function loadVisibleColumns() {
    try {
        const raw = JSON.parse(localStorage.getItem("pricing_builder_columns") || "[]");
        const valid = raw.filter((key) => PB_COLUMN_LABELS[key]);
        return valid.length ? valid : [...PB_DEFAULT_COLUMNS];
    } catch (e) {
        return [...PB_DEFAULT_COLUMNS];
    }
}

function saveVisibleColumns(columns) {
    localStorage.setItem("pricing_builder_columns", JSON.stringify(columns));
}

function isNumericColumn(key) {
    return ["base_buy_price", "expenses", "avg_benchmark", "projected_price", "override_selling_price", "final_margin_pct", "published_price"].includes(key);
}

function fmtCurrency(value) {
    return frappe.format(value || 0, { fieldtype: "Currency" });
}

function marginPct(sellPrice, buyPrice) {
    if (flt(buyPrice) <= 0) return 0;
    return ((flt(sellPrice) - flt(buyPrice)) / flt(buyPrice)) * 100;
}

function publishState(finalPrice, publishedPrice) {
    const nextPrice = flt(finalPrice || 0);
    const current = flt(publishedPrice || 0);
    if (current <= 0) return "New";
    if (Math.abs(nextPrice - current) < 0.0001) return "Same";
    return "Changed";
}

function badgeClassForStatus(status) {
    if (status === "Ready") return "is-green";
    if (status === "No Benchmark") return "is-amber";
    return "is-red";
}

function injectStyles() {
    if (document.getElementById("pricing-builder-styles")) return;
    $("<style id='pricing-builder-styles'>\
        .pb-root{display:grid;gap:16px;padding:12px 0 28px;}\
        .pb-card{background:#fff;border:1px solid var(--border-color, #d1d8dd);border-radius:12px;overflow:hidden;}\
        .pb-card-head{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px 16px;border-bottom:1px solid #eef2f7;flex-wrap:wrap;}\
        .pb-title{font-size:15px;font-weight:600;color:#1f2937;}\
        .pb-subtitle{font-size:12px;color:#6b7280;margin-top:2px;}\
        .pb-actions{display:flex;gap:8px;flex-wrap:wrap;}\
        .pb-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;padding:16px;}\
        .pb-field{min-width:0;}\
        .pb-table-wrap{overflow:auto;padding:0 16px 16px;}\
        .pb-table{width:100%;border-collapse:collapse;min-width:1100px;}\
        .pb-table th,.pb-table td{padding:9px 10px;border-bottom:1px solid #eef2f7;vertical-align:top;background:#fff;}\
        .pb-table th{font-size:12px;font-weight:600;color:#6b7280;background:#f9fafb;position:sticky;top:0;z-index:1;}\
        .pb-table .is-num{text-align:right;}\
        .pb-cell-action{width:90px;text-align:right;}\
        .pb-empty{text-align:center;color:#6b7280;padding:18px 12px;}\
        .pb-warning{padding:10px 14px;margin:10px 16px 0;background:#fff7ed;border:1px solid #fdba74;border-radius:10px;color:#9a3412;font-size:12px;}\
        .pb-badge{display:inline-block;padding:3px 8px;border-radius:999px;font-size:11px;font-weight:600;}\
        .pb-badge.is-green{background:#dcfce7;color:#166534;}\
        .pb-badge.is-amber{background:#fef3c7;color:#92400e;}\
        .pb-badge.is-red{background:#fee2e2;color:#991b1b;}\
        .pb-item-code{font-weight:600;color:#111827;}\
        .pb-item-name{font-size:12px;color:#6b7280;}\
        .pb-note{font-size:11px;color:#6b7280;margin-top:4px;max-width:260px;white-space:normal;}\
        .pb-override-input{width:120px;padding:6px 8px;border:1px solid #cbd5e1;border-radius:6px;text-align:right;background:#fff;}\
        .pb-table--rules{min-width:860px;}\
        .pb-table--rules .frappe-control{margin-bottom:0;}\
        @media (max-width:768px){.pb-card-head{align-items:flex-start;}.pb-table{min-width:840px;}}\
    </style>").appendTo(document.head);
}
