const BUILDER_COLUMN_STORAGE_KEY = "orderlift.pricingBuilder.columns.v1";
const BUILDER_DEFAULT_COLUMNS = ["selected", "item", "item_name", "qty", "base_buy_price", "expenses", "customs_amount", "projected_price", "projected_total_price", "margin_amount", "final_sell_unit_price", "override_selling_price", "final_sell_total", "published_price", "status", "actions"];
const BUILDER_HIGHLIGHT_COLUMNS = new Set(["projected_price", "projected_total_price", "final_sell_unit_price", "final_sell_total"]);
const BUILDER_COLUMNS = [
    { key: "selected", label: "Publish", type: "Check", mandatory: true, editable: true },
    { key: "item", label: "Item ref", mandatory: true },
    { key: "item_name", label: "Item Name" },
    { key: "item_group", label: "Item Group" },
    { key: "item_category", label: "Item Category" },
    { key: "material", label: "Material" },
    { key: "customs_tariff_number", label: "Tariff Number" },
    { key: "buying_list", label: "Source Buying Price List" },
    { key: "origin", label: "Origin" },
    { key: "pricing_scenario", label: "Line Expenses Policy" },
    { key: "qty", label: "Qty", type: "Float" },
    { key: "base_buy_price", label: "Base PU", type: "Currency", sensitive: true },
    { key: "expenses", label: "Expenses U", type: "Currency", sensitive: true },
    { key: "customs_base_value", label: "Customs Value", type: "Currency", sensitive: true },
    { key: "customs_value_per_kg", label: "Customs Value Per Kg", type: "Currency", sensitive: true },
    { key: "customs_amount", label: "Customs U", type: "Currency", sensitive: true },
    { key: "projected_price", label: "Total Cost U", type: "Currency", sensitive: true },
    { key: "projected_total_price", label: "Total Cost", type: "Currency", sensitive: true },
    { key: "margin_amount", label: "Margin Unit", type: "Currency" },
    { key: "total_margin_amount", label: "Total Margin Unit", type: "Currency" },
    { key: "avg_benchmark", label: "Benchmark", type: "Currency" },
    { key: "final_sell_unit_price", label: "Sell Price U", type: "Currency" },
    { key: "override_selling_price", label: "Manual Unit Override", type: "Currency", editable: true },
    { key: "final_sell_total", label: "Total Sell Price", type: "Currency" },
    { key: "final_margin_pct", label: "Margin Pct", type: "Percent" },
    { key: "total_margin_pct", label: "Total Margin Pct", type: "Percent" },
    { key: "margin_basis", label: "Margin Basis" },
    { key: "published_price", label: "List Price", type: "Currency" },
    { key: "status", label: "Status" },
    { key: "status_note", label: "Status Note" },
    { key: "customs_policy", label: "Customs Policy" },
    { key: "benchmark_policy", label: "Benchmark Policy" },
    { key: "actions", label: "", mandatory: true },
];

frappe.ui.form.on("Pricing Builder", {
    refresh(frm) {
        ensureBuilderStyles();
        setupQueries(frm);
        setupGridDisplay(frm);
        renderBuilderItemFilters(frm);
        renderBuilderHeader(frm);
        renderSummaryPanel(frm);
        renderWarningsPanel(frm);
        clearMissingBuilderPriceLists(frm);

        frm.clear_custom_buttons();
        frm.add_custom_button(__("Load Items & Calculate"), () => calculateBuilder(frm), __("Builder"));
        frm.add_custom_button(__("Publish Selected"), () => publishBuilder(frm, true), __("Builder"));
        frm.add_custom_button(__("Publish All"), () => publishBuilder(frm, false), __("Builder"));
        frm.add_custom_button(__("Use Existing List"), () => selectExistingSellingList(frm), __("Selling List"));
        frm.add_custom_button(__("Create New List"), () => setNewSellingListName(frm), __("Selling List"));

        frm.page.set_indicator(indicatorLabel(frm), indicatorColor(frm));
        frm.set_intro(
            __("Use sourcing rules to map buying lists to expenses, customs, and profit margin policies, then calculate and publish a static sell list."),
            "blue"
        );
    },
    builder_name(frm) {
        renderBuilderHeader(frm);
    },
    selling_price_list_name(frm) {
        renderBuilderHeader(frm);
        scheduleAutoRecalculate(frm);
    },
    item_group(frm) {
        scheduleAutoRecalculate(frm);
    },
    default_qty(frm) {
        renderBuilderHeader(frm);
        scheduleAutoRecalculate(frm);
    },
    max_items(frm) {
        renderBuilderHeader(frm);
        scheduleAutoRecalculate(frm);
    },
});

async function clearMissingBuilderPriceLists(frm) {
    if (frm.__checking_builder_price_lists) return;
    const refs = [];
    (frm.doc.sourcing_rules || []).forEach((row) => {
        if (row.buying_price_list) refs.push({ row, field: "buying_price_list", value: row.buying_price_list });
    });
    (frm.doc.builder_items || []).forEach((row) => {
        if (row.buying_list) refs.push({ row, field: "buying_list", value: row.buying_list });
    });
    if (!refs.length) return;

    frm.__checking_builder_price_lists = true;
    try {
        const missing = [];
        const uniqueValues = [...new Set(refs.map((ref) => ref.value))];
        const existsMap = {};
        await Promise.all(uniqueValues.map(async (value) => {
            existsMap[value] = Boolean(await frappe.db.exists("Price List", value));
        }));
        refs.forEach((ref) => {
            if (existsMap[ref.value]) return;
            ref.row[ref.field] = "";
            missing.push(ref.value);
        });
        if (missing.length) {
            frm.dirty();
            frm.refresh_field("sourcing_rules");
            frm.refresh_field("builder_items");
            renderBuilderItemsTable(frm);
            renderBuilderItemFilters(frm);
            frappe.show_alert({
                message: __("Cleared deleted buying price list(s): {0}", [[...new Set(missing)].join(", ")]),
                indicator: "orange",
            });
        }
    } finally {
        frm.__checking_builder_price_lists = false;
    }
}

function setupQueries(frm) {
    frm.set_query("buying_price_list", "sourcing_rules", () => ({ filters: { buying: 1 } }));
    frm.set_query("buying_list", "builder_items", () => ({ filters: { buying: 1 } }));
    frm.set_query("item", "builder_items", () => ({ filters: { disabled: 0 } }));
    frm.set_query("pricing_scenario", "sourcing_rules", () => ({ filters: {} }));
    frm.set_query("customs_policy", "sourcing_rules", () => ({ filters: { is_active: 1 } }));
    frm.set_query("benchmark_policy", "sourcing_rules", () => ({ filters: { is_active: 1 } }));
}

function setupGridDisplay(frm) {
    const rulesGrid = frm.get_field("sourcing_rules").grid;
    const itemsGrid = frm.get_field("builder_items").grid;

    if (rulesGrid) {
        rulesGrid.set_multiple_add("buying_price_list", "pricing_scenario");
        rulesGrid.wrapper.addClass("pb-native-grid");
    }

    if (itemsGrid) {
        const itemLabels = {
            item: __("Item"),
            item_name: __("Item Name"),
            item_group: __("Item Group"),
            item_category: __("Item Category"),
            material: __("Material"),
            customs_tariff_number: __("Tariff Number"),
            buying_list: __("Buying List"),
            origin: __("Origin"),
            base_buy_price: __("PU Achat"),
            expenses: __("Charges U"),
            customs_base_value: __("Customs Value"),
            customs_value_per_kg: __("Value / Kg"),
            customs_amount: __("Dedouan. U"),
            margin_amount: __("Marge U"),
            avg_benchmark: __("Benchmark"),
            projected_price: __("PUV"),
            override_selling_price: __("PUV Override"),
            final_margin_pct: __("Marge %"),
            published_price: __("PTV Brut"),
            status: __("Status"),
            pricing_scenario: __("Politique Charges"),
            customs_policy: __("Politique Douane"),
            benchmark_policy: __("Politique Marge"),
        };
        Object.entries(itemLabels).forEach(([fieldname, label]) => {
            itemsGrid.update_docfield_property(fieldname, "label", label);
        });
        itemsGrid.wrapper.addClass("pb-native-grid pb-results-grid");
        itemsGrid.refresh();
        renderBuilderItemsTable(frm);
    }
}

function renderBuilderItemFilters(frm) {
    const itemsGrid = frm.get_field("builder_items")?.grid;
    if (!itemsGrid?.wrapper) return;

    const rows = frm.doc.builder_items || [];
    const itemGroupOptions = uniqueBuilderValues(rows.map((row) => row.item_group));
    const selectedGroup = (frm.__builderFilterState || {}).item_group || "";
    const itemCategoryOptions = uniqueBuilderValues(rows
        .filter((row) => !selectedGroup || row.item_group === selectedGroup)
        .map((row) => row.item_category));
    const materialOptions = [...new Set(rows.map((row) => (row.material || "").trim()).filter(Boolean))].sort();
    const statusOptions = [...new Set(rows.map((row) => (row.status || "").trim()).filter(Boolean))].sort();
    const state = frm.__builderFilterState || { search: "", item_group: "", item_category: "", material: "", status: "" };
    if (state.item_category && !itemCategoryOptions.includes(state.item_category)) state.item_category = "";
    frm.__builderFilterState = state;

    itemsGrid.wrapper.find(".pb-filterbar").remove();
    const html = $(`
        <div class="pb-filterbar">
            <div class="pb-filterbar-copy">
                <div class="pb-filter-title">${__("Filter Builder Items")}</div>
                <div class="pb-filter-help">${__("Search loaded items and narrow the results table without recalculating the builder.")}</div>
            </div>
            <div class="pb-filter-controls">
                <input class="form-control pb-filter-search" placeholder="${__("Search item, name, group, buying list...")}" value="${frappe.utils.escape_html(state.search || "")}">
                <select class="form-control pb-filter-item-group">
                    <option value="">${__("All Item Groups")}</option>
                    ${itemGroupOptions.map((value) => `<option value="${frappe.utils.escape_html(value)}" ${state.item_group === value ? "selected" : ""}>${frappe.utils.escape_html(value)}</option>`).join("")}
                </select>
                <select class="form-control pb-filter-item-category">
                    <option value="">${__("All Categories")}</option>
                    ${itemCategoryOptions.map((value) => `<option value="${frappe.utils.escape_html(value)}" ${state.item_category === value ? "selected" : ""}>${frappe.utils.escape_html(value)}</option>`).join("")}
                </select>
                <select class="form-control pb-filter-material">
                    <option value="">${__("All Materials")}</option>
                    ${materialOptions.map((value) => `<option value="${frappe.utils.escape_html(value)}" ${state.material === value ? "selected" : ""}>${frappe.utils.escape_html(value)}</option>`).join("")}
                </select>
                <select class="form-control pb-filter-status">
                    <option value="">${__("All Statuses")}</option>
                    ${statusOptions.map((value) => `<option value="${frappe.utils.escape_html(value)}" ${state.status === value ? "selected" : ""}>${frappe.utils.escape_html(value)}</option>`).join("")}
                </select>
                <button class="btn btn-default btn-sm pb-filter-clear">${__("Clear")}</button>
            </div>
        </div>
    `);
    itemsGrid.wrapper.prepend(html);

    html.find(".pb-filter-search").on("input", function () {
        frm.__builderFilterState.search = ($(this).val() || "").trim();
        applyBuilderItemFilters(frm);
    });
    html.find(".pb-filter-item-group").on("change", function () {
        frm.__builderFilterState.item_group = $(this).val() || "";
        frm.__builderFilterState.item_category = "";
        renderBuilderItemFilters(frm);
        applyBuilderItemFilters(frm);
    });
    html.find(".pb-filter-item-category").on("change", function () {
        frm.__builderFilterState.item_category = $(this).val() || "";
        applyBuilderItemFilters(frm);
    });
    html.find(".pb-filter-material").on("change", function () {
        frm.__builderFilterState.material = $(this).val() || "";
        applyBuilderItemFilters(frm);
    });
    html.find(".pb-filter-status").on("change", function () {
        frm.__builderFilterState.status = $(this).val() || "";
        applyBuilderItemFilters(frm);
    });
    html.find(".pb-filter-clear").on("click", function () {
        frm.__builderFilterState = { search: "", item_group: "", item_category: "", material: "", status: "" };
        renderBuilderItemFilters(frm);
        applyBuilderItemFilters(frm);
    });

    applyBuilderItemFilters(frm);
}

function uniqueBuilderValues(values) {
    const out = [];
    const seen = new Set();
    (values || []).forEach((value) => {
        const clean = (value || "").trim();
        if (!clean || seen.has(clean)) return;
        seen.add(clean);
        out.push(clean);
    });
    return out.sort();
}

function applyBuilderItemFilters(frm) {
    const itemsGrid = frm.get_field("builder_items")?.grid;
    if (!itemsGrid) return;
    const state = frm.__builderFilterState || {};
    const search = (state.search || "").toLowerCase();
    const itemGroup = (state.item_group || "").toLowerCase();
    const itemCategory = (state.item_category || "").toLowerCase();
    const material = (state.material || "").toLowerCase();
    const status = (state.status || "").toLowerCase();

    (itemsGrid.grid_rows || []).forEach((gridRow) => {
        const row = gridRow.doc || {};
        const haystack = [
            row.item,
            row.item_name,
            row.item_group,
            row.item_category,
            row.material,
            row.customs_tariff_number,
            row.buying_list,
            row.status,
            row.pricing_scenario,
        ].filter(Boolean).join(" ").toLowerCase();
        const show = (!search || haystack.includes(search))
            && (!itemGroup || (row.item_group || "").toLowerCase() === itemGroup)
            && (!itemCategory || (row.item_category || "").toLowerCase() === itemCategory)
            && (!material || (row.material || "").toLowerCase() === material)
            && (!status || (row.status || "").toLowerCase() === status);
        $(gridRow.wrapper).toggle(show);
    });
    itemsGrid.wrapper.find("[data-pb-row]").each((_, rowEl) => {
        const index = Number(rowEl.getAttribute("data-pb-row"));
        const row = (frm.doc.builder_items || [])[index] || {};
        const haystack = [
            row.item,
            row.item_name,
            row.item_group,
            row.item_category,
            row.material,
            row.customs_tariff_number,
            row.buying_list,
            row.status,
            row.pricing_scenario,
        ].filter(Boolean).join(" ").toLowerCase();
        const show = (!search || haystack.includes(search))
            && (!itemGroup || (row.item_group || "").toLowerCase() === itemGroup)
            && (!itemCategory || (row.item_category || "").toLowerCase() === itemCategory)
            && (!material || (row.material || "").toLowerCase() === material)
            && (!status || (row.status || "").toLowerCase() === status);
        $(rowEl).toggle(show);
    });
    updatePublishAllState(frm);
}

function renderBuilderItemsTable(frm) {
    const itemsGrid = frm.get_field("builder_items")?.grid;
    if (!itemsGrid?.wrapper) return;
    const rows = frm.doc.builder_items || [];
    itemsGrid.wrapper.find(".pb-custom-table-wrap").remove();
    if (!rows.length) {
        itemsGrid.wrapper.removeClass("pb-custom-table-active");
        return;
    }

    itemsGrid.wrapper.addClass("pb-custom-table-active");
    ensureBuilderBreakdownSelection(frm);
    const columns = activeBuilderColumns(frm);
    const activeTab = builderActiveTab(frm);
    const html = `
        <div class="pb-custom-table-wrap">
            <div class="pb-custom-table-toolbar">
                <div>
                    <div class="pb-filter-title">${__("Builder Items")}</div>
                    <div class="pb-filter-help">${__("Use the frontend table for review, publish selection, overrides, and bulk cleanup.")}</div>
                </div>
                <div class="pb-custom-table-actions">
                    <button type="button" class="btn btn-default btn-sm" data-pb-columns>${__("Columns")}</button>
                    <button type="button" class="btn btn-default btn-sm" data-pb-publish-clear>${__("Clear Publish")}</button>
                </div>
            </div>
            <div class="pb-custom-tabs">
                <button type="button" class="${activeTab === "items" ? "active" : ""}" data-pb-tab="items">${__("Items")}</button>
                <button type="button" class="${activeTab === "breakdown" ? "active" : ""}" data-pb-tab="breakdown">${__("Breakdown")}</button>
            </div>
            ${activeTab === "breakdown" ? builderBreakdownPanel(frm) : `
                <div class="pb-line-table-scroll">
                    <table class="pb-line-table">
                        <thead><tr>${columns.map((column) => builderHeaderCell(frm, column)).join("")}</tr></thead>
                        <tbody>${rows.map((row, index) => builderLineRow(frm, row, index, columns)).join("")}</tbody>
                    </table>
                </div>`}
        </div>`;
    itemsGrid.wrapper.prepend(html);
    bindBuilderItemsTable(frm);
}

function builderActiveTab(frm) {
    if (!["items", "breakdown"].includes(frm.__builderActiveTab)) frm.__builderActiveTab = "items";
    return frm.__builderActiveTab;
}

function ensureBuilderBreakdownSelection(frm) {
    const rows = frm.doc.builder_items || [];
    if (!rows.length) {
        frm.__builderBreakdownKey = "";
        return;
    }
    const currentExists = rows.some((row, index) => builderRowKey(row, index) === frm.__builderBreakdownKey);
    if (!frm.__builderBreakdownKey || !currentExists) {
        frm.__builderBreakdownKey = builderRowKey(rows[0], 0);
    }
}

function builderBreakdownPanel(frm) {
    const rows = frm.doc.builder_items || [];
    const selectedKey = frm.__builderBreakdownKey || "";
    const selected = rows.map((row, index) => ({ row, index, key: builderRowKey(row, index) })).find((entry) => entry.key === selectedKey) || { row: rows[0], index: 0, key: builderRowKey(rows[0], 0) };
    const row = selected.row || {};
    const qty = flt(frm.doc.default_qty || 1) || 1;
    const finalUnit = flt(row.override_selling_price || 0) || flt(row.projected_price || 0);
    const finalTotal = finalUnit * qty;
    const costUnit = builderCostUnit(row);
    const marginUnit = builderActualMarginAmount(row);
    const costTotal = costUnit * qty;
    const options = rows.map((candidate, index) => {
        const key = builderRowKey(candidate, index);
        const label = [candidate.item, candidate.item_name].filter(Boolean).join(" - ") || key;
        return `<option value="${frappe.utils.escape_html(key)}" ${key === selected.key ? "selected" : ""}>${frappe.utils.escape_html(label)}</option>`;
    }).join("");
    return `
        <div class="pb-breakdown-panel">
            <div class="pb-breakdown-head">
                <label>
                    <span>${frappe.utils.escape_html(__("Select Item"))}</span>
                    <select class="form-control" data-pb-breakdown-select>${options}</select>
                </label>
                <div>
                    <strong>${frappe.utils.escape_html(row.item || "-")}</strong>
                    <small>${frappe.utils.escape_html(row.item_name || "")}</small>
                </div>
            </div>
            <div class="pb-breakdown-metrics">
                ${builderBreakdownMetric(__("Base PU"), formatBuilderCurrency(row.base_buy_price))}
                ${builderBreakdownMetric(__("Expenses U"), formatBuilderCurrency(row.expenses))}
                ${builderBreakdownMetric(__("Customs U"), formatBuilderCurrency(row.customs_amount))}
                ${builderBreakdownMetric(__("Total Cost U"), formatBuilderCurrency(costUnit), true)}
                ${builderBreakdownMetric(__("Margin U"), formatBuilderCurrency(marginUnit))}
                ${builderBreakdownMetric(__("Sell Price U"), formatBuilderCurrency(finalUnit), true)}
                ${builderBreakdownMetric(__("Total Cost"), formatBuilderCurrency(costTotal))}
                ${builderBreakdownMetric(__("Total Sell"), formatBuilderCurrency(finalTotal), true)}
                ${builderBreakdownMetric(__("Published/List Price"), formatBuilderCurrency(row.published_price))}
                ${builderBreakdownMetric(__("Benchmark"), formatBuilderCurrency(row.avg_benchmark))}
            </div>
            <div class="pb-breakdown-steps">
                ${builderBreakdownStep(__("Buying Source"), row.buying_list || "-")}
                ${builderBreakdownStep(__("Expenses Policy"), row.pricing_scenario || "-")}
                ${builderBreakdownStep(__("Customs Policy"), row.customs_policy || "-")}
                ${builderBreakdownStep(__("Margin Policy"), row.benchmark_policy || "-")}
                ${builderBreakdownStep(__("Item Category"), row.item_category || "-")}
                ${builderBreakdownStep(__("Material"), row.material || "-")}
                ${builderBreakdownStep(__("Tariff Number"), row.customs_tariff_number || "-")}
                ${builderBreakdownStep(__("Status"), row.status_note || row.status || "-")}
            </div>
        </div>`;
}

function builderBreakdownMetric(label, value, highlight) {
    return `<span class="pb-breakdown-metric ${highlight ? "highlight" : ""}"><em>${frappe.utils.escape_html(label)}</em><strong>${frappe.utils.escape_html(value == null ? "-" : String(value))}</strong></span>`;
}

function builderBreakdownStep(label, value) {
    return `<span class="pb-breakdown-step"><em>${frappe.utils.escape_html(label)}</em><strong>${frappe.utils.escape_html(value == null || value === "" ? "-" : String(value))}</strong></span>`;
}

function builderHeaderCell(frm, column) {
    if (column.key === "selected") {
        return `<th class="pb-col-check"><label class="pb-header-check"><input type="checkbox" data-pb-publish-all aria-label="${frappe.utils.escape_html(__("Toggle all publish rows"))}"><span>${frappe.utils.escape_html(__(column.label || ""))}</span></label></th>`;
    }
    return `<th class="pb-col-${frappe.utils.escape_html(column.key)}">${frappe.utils.escape_html(__(column.label || ""))}</th>`;
}

function builderLineRow(frm, row, index, columns) {
    const key = builderRowKey(row, index);
    const selected = cint(row.selected || 0) === 1;
    return `<tr data-pb-row="${index}" data-pb-key="${frappe.utils.escape_html(key)}" class="${selected ? "is-selected" : ""}">${columns.map((column) => builderLineCell(frm, column, row, index, key)).join("")}</tr>`;
}

function builderLineCell(frm, column, row, index, key) {
    const value = builderCellValue(frm, row, column.key);
    if (column.key === "selected") {
        return `<td class="pb-col-check"><input type="checkbox" data-pb-field="selected" data-pb-row-index="${index}" ${cint(row.selected || 0) ? "checked" : ""} aria-label="${frappe.utils.escape_html(__("Publish row"))}"></td>`;
    }
    if (column.key === "override_selling_price") {
        return `<td><input class="form-control input-sm pb-line-input" type="number" step="any" data-pb-field="override_selling_price" data-pb-row-index="${index}" value="${frappe.utils.escape_html(row.override_selling_price || 0)}"></td>`;
    }
    if (column.key === "actions") {
        return `<td class="pb-col-actions"><button type="button" class="pb-icon-btn" data-pb-delete-row="${index}" aria-label="${frappe.utils.escape_html(__("Delete row"))}">&times;</button></td>`;
    }
    if (column.key === "item") {
        return `<td class="pb-line-item"><strong>${frappe.utils.escape_html(row.item || "-")}</strong>${row.status_note ? `<small>${frappe.utils.escape_html(row.status_note)}</small>` : ""}</td>`;
    }
    if (column.type === "Currency") {
        return `<td class="pb-money ${BUILDER_HIGHLIGHT_COLUMNS.has(column.key) ? "pb-cell-highlight" : ""}">${frappe.utils.escape_html(formatBuilderCurrency(value))}</td>`;
    }
    if (column.type === "Percent") {
        return `<td class="pb-number">${Number(value || 0).toFixed(1)}%</td>`;
    }
    if (column.type === "Float") {
        return `<td class="pb-number">${frappe.utils.escape_html(textFromHtml(frappe.format(value || 0, { fieldtype: "Float" })))}</td>`;
    }
    if (column.type === "Check") {
        return `<td><span class="pb-mini-badge">${Number(value || 0) ? __("Yes") : __("No")}</span></td>`;
    }
    if (column.key === "status") {
        return `<td><span class="pb-status-badge ${builderStatusClass(value)}">${frappe.utils.escape_html(value || "-")}</span></td>`;
    }
    return `<td>${frappe.utils.escape_html(value == null || value === "" ? "-" : value)}</td>`;
}

function bindBuilderItemsTable(frm) {
    const wrapper = frm.get_field("builder_items")?.grid?.wrapper;
    if (!wrapper) return;
    wrapper.find("[data-pb-tab]").on("click", function () {
        frm.__builderActiveTab = this.getAttribute("data-pb-tab") || "items";
        renderBuilderItemsTable(frm);
        applyBuilderItemFilters(frm);
    });
    wrapper.find("[data-pb-breakdown-select]").on("change", function () {
        frm.__builderBreakdownKey = this.value || "";
        renderBuilderItemsTable(frm);
        applyBuilderItemFilters(frm);
    });
    wrapper.find("[data-pb-columns]").on("click", () => openBuilderColumnDialog(frm));
    updatePublishAllState(frm);
    wrapper.find("[data-pb-publish-all]").on("change", function () {
        setVisibleBuilderPublishState(frm, this.checked ? 1 : 0);
    });
    wrapper.find("[data-pb-publish-clear]").on("click", () => setVisibleBuilderPublishState(frm, 0));
    wrapper.find("[data-pb-delete-row]").on("click", function () {
        deleteBuilderRows(frm, [Number(this.getAttribute("data-pb-delete-row"))]);
    });
    wrapper.find("[data-pb-field]").on("input change", function () {
        const index = Number(this.getAttribute("data-pb-row-index"));
        const field = this.getAttribute("data-pb-field");
        const row = (frm.doc.builder_items || [])[index];
        if (!row || !field) return;
        const value = this.type === "checkbox" ? (this.checked ? 1 : 0) : flt(this.value || 0);
        if (row.doctype && row.name) frappe.model.set_value(row.doctype, row.name, field, value);
        else row[field] = value;
        if (field === "override_selling_price") {
            const marginPct = builderActualMarginPct(row);
            const totalMarginPct = marginPct;
            if (row.doctype && row.name) frappe.model.set_value(row.doctype, row.name, "final_margin_pct", marginPct);
            else row.final_margin_pct = marginPct;
            if (row.doctype && row.name) frappe.model.set_value(row.doctype, row.name, "total_margin_pct", totalMarginPct);
            else row.total_margin_pct = totalMarginPct;
        }
        frm.dirty();
        setTimeout(() => {
            renderBuilderItemsTable(frm);
            applyBuilderItemFilters(frm);
        }, 0);
    });
}

function setVisibleBuilderPublishState(frm, value) {
    const wrapper = frm.get_field("builder_items")?.grid?.wrapper;
    const rows = frm.doc.builder_items || [];
    const visibleRows = wrapper?.find("[data-pb-row]:visible") || [];
    visibleRows.each((_, rowEl) => {
        const index = Number(rowEl.getAttribute("data-pb-row"));
        const row = rows[index];
        if (!row) return;
        row.selected = value ? 1 : 0;
    });
    frm.dirty();
    renderBuilderItemsTable(frm);
    applyBuilderItemFilters(frm);
}

function updatePublishAllState(frm) {
    const wrapper = frm.get_field("builder_items")?.grid?.wrapper;
    if (!wrapper) return;
    const visibleRows = wrapper.find("[data-pb-row]:visible");
    const checkbox = wrapper.find("[data-pb-publish-all]");
    if (!checkbox.length) return;
    const rows = frm.doc.builder_items || [];
    let checked = 0;
    visibleRows.each((_, rowEl) => {
        const index = Number(rowEl.getAttribute("data-pb-row"));
        if (cint((rows[index] || {}).selected || 0)) checked += 1;
    });
    checkbox.prop("checked", Boolean(visibleRows.length && checked === visibleRows.length));
    checkbox.prop("indeterminate", Boolean(checked > 0 && checked < visibleRows.length));
}

function deleteBuilderRows(frm, indexes) {
    const rows = frm.doc.builder_items || [];
    [...new Set(indexes || [])].sort((a, b) => b - a).forEach((index) => {
        if (index >= 0 && index < rows.length) rows.splice(index, 1);
    });
    rows.forEach((row, index) => { row.idx = index + 1; });
    frm.dirty();
    frm.refresh_field("builder_items");
    renderBuilderItemsTable(frm);
    renderBuilderItemFilters(frm);
}

function builderRowKey(row, index) {
    return row?.name || `row-${index}`;
}

function builderCellValue(frm, row, key) {
    const qty = flt(frm.doc.default_qty || 1) || 1;
    const projected = flt(row.projected_price || 0);
    const finalUnit = flt(row.override_selling_price || 0) || projected;
    if (key === "qty") return qty;
    if (key === "projected_price") return builderCostUnit(row);
    if (key === "projected_total_price") return builderCostUnit(row) * qty;
    if (key === "margin_amount" || key === "total_margin_amount") return builderActualMarginAmount(row);
    if (key === "final_margin_pct" || key === "total_margin_pct") return builderActualMarginPct(row);
    if (key === "final_sell_unit_price") return finalUnit;
    if (key === "final_sell_total") return finalUnit * qty;
    return row[key];
}

function builderCostUnit(row) {
    return flt(row.base_buy_price || 0) + flt(row.expenses || 0) + flt(row.customs_amount || 0);
}

function builderActualMarginAmount(row) {
    const finalUnit = flt(row.override_selling_price || 0) || flt(row.projected_price || 0);
    return finalUnit - builderCostUnit(row);
}

function builderActualMarginPct(row) {
    return builderMarginPct(row, builderActualMarginAmount(row));
}

function builderMarginPct(row, marginAmount) {
    const basis = String(row.margin_basis || "Base Price").trim() || "Base Price";
    const amount = flt(marginAmount || 0);
    let denominator = flt(row.base_buy_price || 0);
    if (basis === "Loaded Cost") denominator = builderCostUnit(row);
    if (basis === "Sale Price") denominator = builderCostUnit(row) + amount;
    return denominator > 0 ? (amount / denominator) * 100 : 0;
}

function activeBuilderColumns(frm) {
    return normalizeBuilderColumns(frm.__builderColumns || loadBuilderColumns())
        .map((key) => BUILDER_COLUMNS.find((column) => column.key === key))
        .filter(Boolean);
}

function loadBuilderColumns() {
    try {
        const raw = window.localStorage?.getItem(BUILDER_COLUMN_STORAGE_KEY);
        const parsed = raw ? JSON.parse(raw) : null;
        if (Array.isArray(parsed) && parsed.length) return normalizeBuilderColumns(parsed);
    } catch (error) {
        // Local preference only; ignore storage failures.
    }
    return BUILDER_DEFAULT_COLUMNS.slice();
}

function saveBuilderColumns(columns) {
    try {
        window.localStorage?.setItem(BUILDER_COLUMN_STORAGE_KEY, JSON.stringify(normalizeBuilderColumns(columns || BUILDER_DEFAULT_COLUMNS)));
    } catch (error) {
        // Local preference only; ignore storage failures.
    }
}

function normalizeBuilderColumns(columns) {
    const available = new Set(BUILDER_COLUMNS.map((column) => column.key));
    const normalized = [];
    (columns || []).forEach((key) => {
        if (available.has(key) && !normalized.includes(key)) normalized.push(key);
    });
    if (!normalized.includes("item")) normalized.unshift("item");
    if (!normalized.includes("selected")) normalized.unshift("selected");
    if (!normalized.includes("actions")) normalized.push("actions");
    return normalized.filter((key) => available.has(key));
}

function openBuilderColumnDialog(frm) {
    const selected = new Set(normalizeBuilderColumns(frm.__builderColumns || loadBuilderColumns()));
    const dialog = new frappe.ui.Dialog({
        title: __("Builder Table Columns"),
        fields: [{ fieldtype: "HTML", fieldname: "columns_html" }],
        primary_action_label: __("Apply"),
        primary_action: () => {
            const ordered = [];
            dialog.$wrapper.find("[data-pb-column-key]").each((_, row) => {
                const key = row.getAttribute("data-pb-column-key");
                const column = BUILDER_COLUMNS.find((item) => item.key === key);
                const checked = row.querySelector("input")?.checked;
                if (column?.mandatory || checked) ordered.push(key);
            });
            frm.__builderColumns = normalizeBuilderColumns(ordered.length ? ordered : BUILDER_DEFAULT_COLUMNS);
            saveBuilderColumns(frm.__builderColumns);
            dialog.hide();
            renderBuilderItemsTable(frm);
            applyBuilderItemFilters(frm);
        },
    });
    dialog.show();
    const selectedColumns = orderedBuilderColumnOptions(selected).map((column) => `
        <div class="pb-column-option" draggable="${column.mandatory ? "false" : "true"}" data-pb-column-key="${frappe.utils.escape_html(column.key)}">
            <span class="pb-drag-handle">${column.mandatory ? "" : "::"}</span>
            <label><input type="checkbox" ${column.mandatory || selected.has(column.key) ? "checked" : ""} ${column.mandatory ? "disabled" : ""}> ${frappe.utils.escape_html(__(column.label || ""))}</label>
        </div>`).join("");
    dialog.fields_dict.columns_html.$wrapper.html(`<div class="pb-column-list">${selectedColumns}</div>`);
    bindBuilderColumnDrag(dialog.fields_dict.columns_html.$wrapper);
}

function orderedBuilderColumnOptions(selected) {
    const known = new Set();
    const ordered = [];
    normalizeBuilderColumns([...selected]).forEach((key) => {
        const column = BUILDER_COLUMNS.find((item) => item.key === key);
        if (column && !known.has(key)) {
            known.add(key);
            ordered.push(column);
        }
    });
    BUILDER_COLUMNS.forEach((column) => {
        if (!known.has(column.key)) ordered.push(column);
    });
    return ordered;
}

function bindBuilderColumnDrag(wrapper) {
    let dragged = null;
    wrapper.find("[data-pb-column-key]").on("dragstart", function (event) {
        dragged = this;
        event.originalEvent.dataTransfer.effectAllowed = "move";
    });
    wrapper.find("[data-pb-column-key]").on("dragover", function (event) {
        event.preventDefault();
        if (!dragged || dragged === this) return;
        const rect = this.getBoundingClientRect();
        const after = event.originalEvent.clientY > rect.top + rect.height / 2;
        this.parentNode.insertBefore(dragged, after ? this.nextSibling : this);
    });
    wrapper.find("[data-pb-column-key]").on("dragend", () => { dragged = null; });
}

function formatBuilderCurrency(value) {
    if (window.orderlift?.formatCurrency) return window.orderlift.formatCurrency(value);
    return normalizeCurrencyText(textFromHtml(frappe.format(Number(value || 0), { fieldtype: "Currency" })));
}

function normalizeCurrencyText(value) {
    return String(value || "")
        .replace(/[\u200e\u200f\u202a-\u202e]/g, "")
        .replace(/د\.م\./g, window.orderlift?.getActiveCompanyCurrency?.() || "MAD")
        .replace(/\s+/g, " ")
        .trim();
}

function textFromHtml(value) {
    const wrapper = document.createElement("div");
    wrapper.innerHTML = String(value == null ? "" : value);
    return (wrapper.textContent || wrapper.innerText || "").trim();
}

function builderStatusClass(value) {
    const status = String(value || "").toLowerCase();
    if (status.includes("missing")) return "is-warning";
    if (status.includes("benchmark")) return "is-info";
    if (status.includes("ready")) return "is-ready";
    return "";
}

function renderBuilderHeader(frm) {
    const name = frappe.utils.escape_html(frm.doc.builder_name || frm.doc.name || __("New Pricing Builder"));
    const priceList = frappe.utils.escape_html(frm.doc.selling_price_list_name || __("Not set yet"));
    const qty = frappe.format(frm.doc.default_qty || 1, { fieldtype: "Float" });
    const maxItems = cint(frm.doc.max_items || 0) > 0 ? frappe.utils.escape_html(String(frm.doc.max_items)) : __("All");

    frm.get_field("builder_header_html").$wrapper.html(`
        <div class="pb-hero">
            <div class="pb-hero-copy">
                <div class="pb-eyebrow">${__("Static Sell List Builder")}</div>
                <h2>${name}</h2>
                <p>${__("Build a clean sell list from buy prices, expenses policies, customs policies, and profit margin policies.")}</p>
                <div class="pb-hero-stats">
                    <div class="pb-stat-card">
                    <span>${__("Sell List")}</span>
                    <strong>${priceList}</strong>
                    </div>
                    <div class="pb-stat-card">
                    <span>${__("Qty / Item")}</span>
                    <strong>${qty}</strong>
                    </div>
                    <div class="pb-stat-card">
                    <span>${__("Max Items")}</span>
                    <strong>${maxItems}</strong>
                    </div>
                </div>
            </div>
        </div>
    `);
}

function renderSummaryPanel(frm) {
    const cards = [
        { label: __("Total Items"), value: cint(frm.doc.total_items || 0), tone: "slate" },
        { label: __("Ready"), value: cint(frm.doc.ready_items || 0), tone: "green" },
        { label: __("Changed"), value: cint(frm.doc.changed_items || 0), tone: "amber" },
        { label: __("New"), value: cint(frm.doc.new_items || 0), tone: "blue" },
        { label: __("Missing"), value: cint(frm.doc.missing_items || 0), tone: "red" },
    ];

    frm.get_field("summary_panel_html").$wrapper.html(`
        <div class="pb-summary-grid">
            ${cards
                .map(
                    (card) => `
                <div class="pb-summary-card is-${card.tone}">
                    <span>${card.label}</span>
                    <strong>${card.value}</strong>
                </div>`
                )
                .join("")}
        </div>
    `);
}

function renderWarningsPanel(frm) {
    const warnings = (frm.doc.warnings_html || "")
        .split("\n")
        .map((row) => row.trim())
        .filter(Boolean);

    if (!warnings.length) {
        frm.get_field("warnings_panel_html").$wrapper.html(`
            <div class="pb-warning-box is-empty">${__("No warnings. The builder is ready to calculate or publish.")}</div>
        `);
        return;
    }

    frm.get_field("warnings_panel_html").$wrapper.html(`
        <div class="pb-warning-box">
            <div class="pb-warning-title">${__("Review Before Publish")}</div>
            <ul>${warnings.map((warning) => `<li>${frappe.utils.escape_html(warning)}</li>`).join("")}</ul>
        </div>
    `);
}

function indicatorLabel(frm) {
    if (cint(frm.doc.missing_items || 0) > 0) return __("Needs Review");
    if (cint(frm.doc.changed_items || 0) > 0 || cint(frm.doc.new_items || 0) > 0) return __("Ready to Publish");
    if (cint(frm.doc.total_items || 0) > 0) return __("Calculated");
    return __("Draft");
}

function indicatorColor(frm) {
    if (cint(frm.doc.missing_items || 0) > 0) return "orange";
    if (cint(frm.doc.changed_items || 0) > 0 || cint(frm.doc.new_items || 0) > 0) return "green";
    if (cint(frm.doc.total_items || 0) > 0) return "blue";
    return "gray";
}

async function calculateBuilder(frm) {
    if (frm.__pricing_builder_running) return;
    frm.__pricing_builder_running = true;
    try {
        await saveIfNeeded(frm);
        await frappe.call({
            method: "orderlift.orderlift_sales.doctype.pricing_builder.pricing_builder.calculate_builder_doc",
            args: { name: frm.doc.name },
            freeze: true,
            freeze_message: __("Calculating builder prices..."),
        });
        await frm.reload_doc();
    } finally {
        frm.__pricing_builder_running = false;
    }
}

async function publishBuilder(frm, selectedOnly) {
    if (!frm.doc.selling_price_list_name) {
        frappe.throw(__("Enter the Selling Price List Name before publishing."));
    }
    await saveIfNeeded(frm);
    const response = await frappe.call({
        method: "orderlift.orderlift_sales.doctype.pricing_builder.pricing_builder.publish_builder_doc",
        args: { name: frm.doc.name, selected_only: selectedOnly ? 1 : 0 },
        freeze: true,
        freeze_message: __("Publishing prices..."),
    });
    const out = response.message || {};
    frappe.show_alert(
        {
            message: [
                __("Price List: {0}", [out.price_list || frm.doc.selling_price_list_name]),
                __("Created: {0}", [out.created || 0]),
                __("Updated: {0}", [out.updated || 0]),
                __("Skipped: {0}", [out.skipped || 0]),
            ].join(" | "),
            indicator: (out.errors || []).length ? "orange" : "green",
        },
        8
    );
    await frm.reload_doc();
}

function selectExistingSellingList(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __("Update Existing Selling List"),
        fields: [
            {
                label: __("Selling Price List"),
                fieldname: "price_list",
                fieldtype: "Link",
                options: "Price List",
                reqd: 1,
                get_query: () => ({ filters: { selling: 1 } }),
            },
        ],
        primary_action_label: __("Use This List"),
        primary_action: (values) => {
            if (!values?.price_list) return;
            frm.set_value("selling_price_list_name", values.price_list);
            dialog.hide();
            frappe.show_alert({ message: __("Publishing will update {0}", [values.price_list]), indicator: "blue" });
        },
    });
    dialog.show();
}

function setNewSellingListName(frm) {
    const suggested = cleanSellingListName(frm.doc.selling_price_list_name || frm.doc.builder_name || frm.doc.name || "");
    const dialog = new frappe.ui.Dialog({
        title: __("Create New Selling List"),
        fields: [
            {
                label: __("New Selling Price List Name"),
                fieldname: "price_list_name",
                fieldtype: "Data",
                default: suggested,
                reqd: 1,
                description: __("The list is created when you publish selected/all rows."),
            },
        ],
        primary_action_label: __("Use New Name"),
        primary_action: async (values) => {
            const name = cleanSellingListName(values?.price_list_name || "");
            if (!name) return;
            if (await frappe.db.exists("Price List", name)) {
                frappe.msgprint({
                    title: __("Price List Exists"),
                    message: __("{0} already exists. Use 'Use Existing List' to update it, or enter a different new name.", [frappe.utils.escape_html(name)]),
                    indicator: "orange",
                });
                return;
            }
            frm.set_value("selling_price_list_name", name);
            dialog.hide();
            frappe.show_alert({ message: __("Publishing will create {0}", [name]), indicator: "green" });
        },
    });
    dialog.show();
}

function cleanSellingListName(value) {
    return String(value || "").trim();
}

async function saveIfNeeded(frm) {
    if (frm.is_new() || frm.is_dirty()) {
        await frm.save();
    }
}

function scheduleAutoRecalculate(frm) {
    if (frm.is_new() || frm.__pricing_builder_running) return;
    clearTimeout(frm.__pricing_builder_auto_timer);
    frm.__pricing_builder_auto_timer = setTimeout(() => {
        if (frm.__pricing_builder_running) return;
        calculateBuilder(frm);
    }, 450);
}

frappe.ui.form.on("Pricing Builder Item", {
    item(frm) {
        scheduleAutoRecalculate(frm);
        setTimeout(() => renderBuilderItemFilters(frm), 0);
    },
    buying_list(frm) {
        scheduleAutoRecalculate(frm);
        setTimeout(() => renderBuilderItemFilters(frm), 0);
    },
    override_selling_price(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        const marginPct = builderActualMarginPct(row);
        frappe.model.set_value(cdt, cdn, "final_margin_pct", marginPct);
        frappe.model.set_value(cdt, cdn, "total_margin_pct", marginPct);
        setTimeout(() => renderBuilderItemFilters(frm), 0);
    },
});

frappe.ui.form.on("Pricing Builder Sourcing Rule", {
    buying_price_list(frm) {
        scheduleAutoRecalculate(frm);
    },
    pricing_scenario(frm) {
        scheduleAutoRecalculate(frm);
    },
    customs_policy(frm) {
        scheduleAutoRecalculate(frm);
    },
    benchmark_policy(frm) {
        scheduleAutoRecalculate(frm);
    },
    is_active(frm) {
        scheduleAutoRecalculate(frm);
    },
    sourcing_rules_add(frm) {
        scheduleAutoRecalculate(frm);
    },
    sourcing_rules_remove(frm) {
        scheduleAutoRecalculate(frm);
    },
    builder_items_add(frm) {
        setTimeout(() => renderBuilderItemFilters(frm), 0);
    },
    builder_items_remove(frm) {
        setTimeout(() => renderBuilderItemFilters(frm), 0);
    },
});

function ensureBuilderStyles() {
    if (document.getElementById("pricing-builder-form-styles")) return;
    $("<style id='pricing-builder-form-styles'>\
        .pb-hero{display:block;padding:18px 20px;border-radius:16px;background:linear-gradient(135deg,#f7f4ec 0%,#e8f1ef 100%);border:1px solid #d7e4df;margin-bottom:8px;}\
        .pb-eyebrow{font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#6b7280;margin-bottom:8px;}\
        .pb-hero h2{margin:0 0 8px;font-size:26px;line-height:1.1;color:#14213d;}\
        .pb-hero p{margin:0;color:#475569;max-width:52ch;}\
        .pb-hero-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:14px;}\
        .pb-stat-card{padding:12px 14px;border-radius:14px;background:rgba(255,255,255,.7);backdrop-filter:blur(6px);border:1px solid rgba(255,255,255,.65);box-shadow:0 8px 24px rgba(20,33,61,.06);}\
        .pb-stat-card span{display:block;font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:#64748b;margin-bottom:6px;}\
        .pb-stat-card strong{display:block;font-size:15px;color:#0f172a;word-break:break-word;}\
        .pb-summary-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin:8px 0 2px;}\
        .pb-summary-card{padding:14px;border-radius:14px;border:1px solid #e5e7eb;background:#fff;}\
        .pb-summary-card span{display:block;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:#64748b;margin-bottom:8px;}\
        .pb-summary-card strong{font-size:24px;line-height:1;color:#0f172a;}\
        .pb-summary-card.is-green{background:#f0fdf4;border-color:#bbf7d0;}\
        .pb-summary-card.is-amber{background:#fffbeb;border-color:#fde68a;}\
        .pb-summary-card.is-blue{background:#eff6ff;border-color:#bfdbfe;}\
        .pb-summary-card.is-red{background:#fef2f2;border-color:#fecaca;}\
        .pb-summary-card.is-slate{background:#f8fafc;border-color:#e2e8f0;}\
        .pb-warning-box{padding:14px 16px;border-radius:14px;background:#fff7ed;border:1px solid #fdba74;color:#9a3412;margin:8px 0 2px;}\
        .pb-warning-box.is-empty{background:#f8fafc;border-color:#e2e8f0;color:#475569;}\
        .pb-warning-title{font-weight:700;margin-bottom:8px;}\
        .pb-warning-box ul{margin:0;padding-left:18px;}\
        .pb-warning-box li+li{margin-top:6px;}\
        .pb-filterbar{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;padding:12px 14px;margin:0 0 10px;border:1px solid #e2e8f0;border-radius:14px;background:#f8fafc;}\
        .pb-filter-title{font-size:12px;font-weight:800;letter-spacing:.05em;text-transform:uppercase;color:#0f172a;margin-bottom:4px;}\
        .pb-filter-help{font-size:12px;color:#64748b;max-width:42ch;}\
        .pb-filter-controls{display:grid;grid-template-columns:minmax(240px,1.5fr) minmax(160px,.8fr) minmax(160px,.8fr) auto;gap:8px;align-items:center;}\
        .pb-custom-table-active .grid-heading-row,.pb-custom-table-active .grid-body,.pb-custom-table-active .grid-footer,.pb-custom-table-active .grid-buttons,.pb-custom-table-active .grid-empty{display:none!important;}\
        .pb-custom-table-wrap{border:1px solid #e2e8f0;border-radius:14px;background:#fff;margin:0 0 10px;overflow:hidden;}\
        .pb-custom-table-toolbar{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:12px 14px;background:#f8fafc;border-bottom:1px solid #e2e8f0;}\
        .pb-custom-table-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap;justify-content:flex-end;}\
        .pb-custom-tabs{display:flex;gap:6px;padding:10px 12px;border-bottom:1px solid #e2e8f0;background:#fff;}\
        .pb-custom-tabs button{border:1px solid #e2e8f0;border-radius:999px;background:#fff;color:#475569;padding:6px 12px;font-size:12px;font-weight:700;}\
        .pb-custom-tabs button.active{background:#111827;border-color:#111827;color:#fff;}\
        .pb-breakdown-panel{display:grid;gap:14px;padding:14px;background:#f8fafc;}\
        .pb-breakdown-head{display:grid;grid-template-columns:minmax(280px,.45fr) minmax(0,1fr);gap:12px;align-items:end;}\
        .pb-breakdown-head label{display:grid;gap:6px;margin:0;color:#64748b;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.04em;}\
        .pb-breakdown-head strong{display:block;color:#0f172a;font-size:18px;font-weight:800;}\
        .pb-breakdown-head small{display:block;color:#64748b;margin-top:3px;}\
        .pb-breakdown-metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;}\
        .pb-breakdown-metric{display:grid;gap:6px;border:1px solid #e2e8f0;border-radius:12px;background:#fff;padding:11px 12px;}\
        .pb-breakdown-metric.highlight{background:#eef2ff;border-color:#c7d2fe;}\
        .pb-breakdown-metric em{font-style:normal;color:#64748b;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.04em;}\
        .pb-breakdown-metric strong{color:#0f172a;font-size:14px;font-weight:800;font-variant-numeric:tabular-nums;}\
        .pb-breakdown-steps{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;}\
        .pb-breakdown-step{display:grid;gap:4px;border:1px solid #e5e7eb;border-radius:10px;background:#fff;padding:9px 10px;}\
        .pb-breakdown-step em{font-style:normal;color:#64748b;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.04em;}\
        .pb-breakdown-step strong{color:#1f2937;font-size:12px;font-weight:700;word-break:break-word;}\
        .pb-line-table-scroll{overflow:auto;max-width:100%;}\
        .pb-line-table{width:max-content;min-width:1600px;border-collapse:separate;border-spacing:0;}\
        .pb-line-table th{position:sticky;top:0;background:#f8fafc;border-bottom:1px solid #e2e8f0;color:#64748b;font-size:11px;font-weight:700;text-align:left;padding:10px;white-space:nowrap;z-index:1;}\
        .pb-line-table td{border-bottom:1px solid #edf2f7;padding:9px 10px;vertical-align:middle;font-size:12px;}\
        .pb-line-table tbody tr:nth-child(odd){background:#fcfcfd;}\
        .pb-line-table tbody tr:hover{background:#f8fafc;}\
        .pb-line-table tbody tr.is-selected{background:#eff6ff;}\
        .pb-line-table input[type='checkbox']{appearance:none;-webkit-appearance:none;display:inline-grid;place-content:center;width:18px;height:18px;min-width:18px;min-height:18px;margin:0;padding:0;border:1.5px solid #cbd5e1;border-radius:6px;background:#fff;cursor:pointer;transition:all .15s ease;}\
        .pb-line-table input[type='checkbox']::after{content:'';width:9px;height:9px;transform:scale(0);transition:transform .12s ease;background:#fff;clip-path:polygon(14% 44%,0 58%,38% 96%,100% 20%,86% 8%,36% 68%);}\
        .pb-line-table input[type='checkbox']:checked{border-color:#4f46e5;background:#4f46e5;}\
        .pb-line-table input[type='checkbox']:checked::after{transform:scale(1);}\
        .pb-line-table input[type='checkbox']:focus-visible{outline:3px solid rgba(99,102,241,.16);outline-offset:2px;}\
        .pb-line-input{min-width:110px;height:32px;}\
        .pb-col-select,.pb-col-check,.pb-col-actions{text-align:center;width:46px;}\
        .pb-line-item{min-width:220px;}\
        .pb-line-item strong{display:block;color:#0f172a;font-weight:700;}\
        .pb-line-item small{display:block;margin-top:3px;color:#b45309;max-width:260px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}\
        .pb-money,.pb-number{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;color:#0f172a;font-weight:600;}\
        .pb-cell-highlight{background:#eef2ff;color:#3730a3;}\
        .pb-mini-badge,.pb-status-badge{display:inline-flex;align-items:center;min-height:24px;border-radius:999px;padding:0 8px;font-size:11px;font-weight:700;background:#f1f5f9;color:#475569;white-space:nowrap;}\
        .pb-status-badge.is-ready{background:#dcfce7;color:#166534;}\
        .pb-status-badge.is-warning{background:#ffedd5;color:#9a3412;}\
        .pb-status-badge.is-info{background:#e0f2fe;color:#075985;}\
        .pb-icon-btn{width:30px;height:30px;border:1px solid #fecaca;border-radius:8px;background:#fef2f2;color:#b91c1c;font-size:18px;line-height:1;}\
        .pb-column-list{display:grid;gap:6px;max-height:60vh;overflow:auto;padding:4px;}\
        .pb-column-option{display:grid;grid-template-columns:28px minmax(0,1fr);align-items:center;gap:8px;border:1px solid #e2e8f0;border-radius:9px;background:#fff;padding:8px 10px;cursor:grab;}\
        .pb-column-option:active{cursor:grabbing;}\
        .pb-drag-handle{color:#94a3b8;font-family:monospace;font-size:12px;}\
        .pb-column-option label{margin:0;color:#1f2937;font-size:13px;font-weight:500;}\
        .pb-native-grid .grid-heading-row{background:#f8fafc;border-bottom:1px solid #e2e8f0;}\
        .pb-native-grid .grid-heading-row .grid-row{font-weight:700;color:#475569;}\
        .pb-native-grid .grid-body .rows{border-radius:12px;overflow:hidden;}\
        .pb-results-grid .grid-body .data-row:nth-child(odd){background:#fcfcfd;}\
        .pb-results-grid .grid-body .data-row:hover{background:#f8fafc;}\
        .pb-results-grid .grid-static-col{font-weight:600;}\
        @media (max-width:900px){.pb-summary-grid{grid-template-columns:repeat(2,minmax(0,1fr));}.pb-hero-stats{grid-template-columns:1fr;}.pb-filterbar,.pb-custom-table-toolbar,.pb-breakdown-head{display:grid;grid-template-columns:1fr;}.pb-filter-controls{grid-template-columns:1fr;}.pb-custom-table-actions{justify-content:flex-start;}.pb-breakdown-metrics,.pb-breakdown-steps{grid-template-columns:repeat(2,minmax(0,1fr));}.pb-hero h2{font-size:22px;}}\
    </style>").appendTo(document.head);
}
