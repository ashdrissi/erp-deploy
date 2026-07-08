(function () {
    const STATE = {
        doc: null,
        refs: {},
        history: [],
        loading: false,
        saving: false,
        error: "",
        filter: "",
        status: "",
        priceListMode: "existing",
        activeTab: "items",
        selectedBreakdownKey: "",
        autosaveStatus: "",
        visibleItemColumns: [],
        itemColumnWidths: {},
        itemColumnFilters: {},
        itemSort: { key: "", direction: "asc" },
        columnConfiguratorOpen: false,
        sourcingRulesOpen: true,
        autoRecalculate: false,
        checkingFreshness: false,
        autoRecalculateStatus: "",
        stalePromptKey: "",
    };
    let autosaveTimer = null;
    let savePromise = null;
    let autoRecalculateTimer = null;
    const SOURCING_RULE_FIELDS = ["buying_price_list", "pricing_scenario", "customs_policy", "benchmark_policy"];
    const NUMERIC_FIELDS = new Set([
        "base_buy_price",
        "expenses",
        "customs_base_value",
        "customs_value_per_kg",
        "customs_amount",
        "customs_weight_kg",
        "customs_line_weight_kg",
        "customs_unit_weight_kg",
        "customs_package_weight_kg",
        "packaging_units_per_package",
        "packaging_package_count",
        "margin_amount",
        "total_margin_amount",
        "avg_benchmark",
        "projected_price",
        "override_selling_price",
        "final_margin_pct",
        "total_margin_pct",
        "target_margin_percent",
        "benchmark_is_fallback",
        "benchmark_rule_max_discount_percent",
        "fallback_max_discount_percent",
        "policy_max_discount_percent",
        "published_price",
        "customs_value_delta",
        "customs_value_delta_tax_rate",
        "customs_value_delta_tax_amount",
    ]);
    const ITEM_LEGACY_COLUMN_STORAGE_KEY = "orderlift.pricing_builder.visible_item_columns.v1";
    const ITEM_COLUMN_STORAGE_KEY = "orderlift.pricing_builder.item_columns.v2";
    const SOURCING_RULE_STORAGE_KEY = "orderlift.pricing_builder.sourcing_rules_open.v1";
    const AUTO_RECALCULATE_STORAGE_KEY = "orderlift.pricing_builder.auto_recalculate.v1";
    const AUTO_RECALCULATE_INTERVAL_MS = 60000;
    const ITEM_COLUMN_CATEGORIES = [
        ["article", () => __("Article")],
        ["source", () => __("Source")],
        ["cost", () => __("Cost")],
        ["customs", () => __("Customs")],
        ["margin", () => __("Margin & Benchmark")],
        ["publish", () => __("Publish & Status")],
    ];
    const ITEM_TABLE_COLUMNS = [
        { key: "row_number", label: () => __("#"), width: 58, locked: true, defaultVisible: true, align: "center", noSort: true, noFilter: true, render: (row, entry) => String(toNumber(entry.visibleIndex) + 1) },
        { key: "selected", label: () => __("Select"), width: 74, locked: true, defaultVisible: true, align: "center", render: (row) => `<input type="checkbox" data-item-field="selected" ${toNumber(row.selected) ? "checked" : ""}>` },
        { key: "item", label: () => __("Item"), width: 190, locked: true, defaultVisible: true, render: (row) => itemCell(row) },
        { key: "item_name", label: () => __("Name"), width: 240, minWidth: 96, defaultVisible: true, wrap: true, render: (row) => escapeHtml(row.item_name || "") },
        { key: "item_group", label: () => __("Item Group"), width: 190, minWidth: 96, defaultVisible: false, wrap: true, render: (row) => escapeHtml(row.item_group || "") },
        { key: "item_category", label: () => __("Categories d'article"), width: 190, minWidth: 96, defaultVisible: true, wrap: true, render: (row) => escapeHtml(row.item_category || "") },
        { key: "material", label: () => __("Material"), width: 140, minWidth: 88, defaultVisible: false, wrap: true, render: (row) => escapeHtml(row.material || "") },
        { key: "customs_tariff_number", label: () => __("Tariff"), width: 130, defaultVisible: false, render: (row) => escapeHtml(row.customs_tariff_number || "") },
        { key: "origin", label: () => __("Origin"), width: 120, minWidth: 78, defaultVisible: false, wrap: true, render: (row) => escapeHtml(row.origin || "") },
        { key: "buying_list", label: () => __("Buying List"), width: 190, minWidth: 96, defaultVisible: true, wrap: true, render: (row) => escapeHtml(row.buying_list || "") },
        { key: "base_buy_price", label: () => __("Base PU"), width: 120, defaultVisible: true, render: (row) => money(row.base_buy_price) },
        { key: "expenses", label: () => __("Expenses U"), width: 120, defaultVisible: true, render: (row) => money(row.expenses) },
        { key: "customs_amount", label: () => __("Customs U"), width: 120, defaultVisible: true, render: (row) => money(row.customs_amount) },
        { key: "customs_base_value", label: () => __("Customs Value"), width: 140, defaultVisible: false, render: (row) => money(row.customs_base_value) },
        { key: "customs_value_per_kg", label: () => __("Value / Kg"), width: 130, defaultVisible: false, render: (row) => money(row.customs_value_per_kg) },
        { key: "customs_weight_kg", label: () => __("Customs Weight U"), width: 150, defaultVisible: false, render: (row) => `${toNumber(row.customs_weight_kg).toFixed(3)} kg` },
        { key: "customs_line_weight_kg", label: () => __("Line Customs Weight"), width: 170, defaultVisible: false, render: (row) => `${toNumber(row.customs_line_weight_kg).toFixed(3)} kg` },
        { key: "customs_unit_weight_kg", label: () => __("Unit Customs Weight"), width: 170, defaultVisible: false, render: (row) => `${toNumber(row.customs_unit_weight_kg).toFixed(3)} kg` },
        { key: "customs_package_weight_kg", label: () => __("Package Weight"), width: 150, defaultVisible: false, render: (row) => `${toNumber(row.customs_package_weight_kg).toFixed(3)} kg` },
        { key: "packaging_units_per_package", label: () => __("Units / Package"), width: 150, defaultVisible: false, render: (row) => toNumber(row.packaging_units_per_package).toFixed(2) },
        { key: "packaging_package_count", label: () => __("Package Count"), width: 140, defaultVisible: false, render: (row) => toNumber(row.packaging_package_count).toFixed(2) },
        { key: "packaging_profile_source", label: () => __("Packaging Source"), width: 160, defaultVisible: false, render: (row) => escapeHtml(row.packaging_profile_source || "") },
        { key: "customs_basis", label: () => __("Customs Basis"), width: 210, defaultVisible: false, wrap: true, render: (row) => escapeHtml(row.customs_basis || "") },
        { key: "customs_value_delta", label: () => __("Customs Delta"), width: 140, defaultVisible: false, render: (row) => money(row.customs_value_delta) },
        { key: "customs_value_delta_tax_rate", label: () => __("Delta Tax Rate"), width: 140, defaultVisible: false, render: (row) => `${toNumber(row.customs_value_delta_tax_rate).toFixed(2)}%` },
        { key: "customs_value_delta_tax_amount", label: () => __("Delta Tax U"), width: 140, defaultVisible: false, render: (row) => money(row.customs_value_delta_tax_amount) },
        { key: "cost_total", label: () => __("Total Cost U"), width: 130, defaultVisible: true, strong: true, render: (row) => money(costBeforeMargin(row)) },
        { key: "margin_amount", label: () => __("Margin U"), width: 120, defaultVisible: true, render: (row) => money(row.margin_amount) },
        { key: "total_margin_amount", label: () => __("Total Margin U"), width: 140, defaultVisible: false, render: (row) => money(row.total_margin_amount) },
        { key: "avg_benchmark", label: () => __("Benchmark"), width: 130, defaultVisible: false, render: (row) => money(row.avg_benchmark) },
        { key: "projected_price", label: () => __("Calculated Sell U"), width: 150, defaultVisible: false, render: (row) => money(row.projected_price) },
        { key: "sell_price", label: () => __("Sell Price U"), width: 130, defaultVisible: true, strong: true, render: (row) => money(finalSellUnit(row)) },
        { key: "override_selling_price", label: () => __("Override"), width: 158, defaultVisible: true, render: (row, entry) => overrideCell(row, entry) },
        { key: "published_price", label: () => __("List Price"), width: 130, defaultVisible: true, render: (row) => listPriceCell(row) },
        { key: "final_margin_pct", label: () => __("Margin %"), width: 110, defaultVisible: false, render: (row) => `${toNumber(row.final_margin_pct).toFixed(2)}%` },
        { key: "total_margin_pct", label: () => __("Total Margin %"), width: 140, defaultVisible: false, render: (row) => `${toNumber(row.total_margin_pct).toFixed(2)}%` },
        { key: "target_margin_percent", label: () => __("Target Margin %"), width: 150, defaultVisible: false, render: (row) => `${toNumber(row.target_margin_percent).toFixed(2)}%` },
        { key: "margin_basis", label: () => __("Margin Basis"), width: 140, defaultVisible: false, render: (row) => escapeHtml(row.margin_basis || "") },
        { key: "benchmark_is_fallback", label: () => __("Benchmark Fallback"), width: 160, defaultVisible: false, render: (row) => toNumber(row.benchmark_is_fallback) ? __("Yes") : __("No") },
        { key: "benchmark_rule_label", label: () => __("Benchmark Rule"), width: 300, defaultVisible: false, wrap: true, render: (row) => escapeHtml(row.benchmark_rule_label || "") },
        { key: "benchmark_rule_max_discount_percent", label: () => __("Rule Max Discount %"), width: 170, defaultVisible: false, render: (row) => `${toNumber(row.benchmark_rule_max_discount_percent).toFixed(2)}%` },
        { key: "fallback_max_discount_percent", label: () => __("Fallback Max Discount %"), width: 190, defaultVisible: false, render: (row) => `${toNumber(row.fallback_max_discount_percent).toFixed(2)}%` },
        { key: "policy_max_discount_percent", label: () => __("Policy Max Discount %"), width: 180, defaultVisible: false, render: (row) => `${toNumber(row.policy_max_discount_percent).toFixed(2)}%` },
        { key: "pricing_scenario", label: () => __("Pricing Scenario"), width: 190, minWidth: 96, defaultVisible: false, wrap: true, render: (row) => escapeHtml(row.pricing_scenario || "") },
        { key: "customs_policy", label: () => __("Customs Policy"), width: 190, minWidth: 96, defaultVisible: false, wrap: true, render: (row) => escapeHtml(row.customs_policy || "") },
        { key: "benchmark_policy", label: () => __("Benchmark Policy"), width: 190, minWidth: 96, defaultVisible: false, wrap: true, render: (row) => escapeHtml(row.benchmark_policy || "") },
        { key: "status", label: () => __("Status"), width: 130, defaultVisible: true, render: (row) => `<span class="pbb-pill ${statusClass(displayStatus(row) || "Draft")}" title="${escapeHtml(row.status_note || "")}">${escapeHtml(displayStatus(row) || "Draft")}</span>` },
        { key: "status_note", label: () => __("Status Note"), width: 300, defaultVisible: false, wrap: true, render: (row) => escapeHtml(row.status_note || "") },
    ];

    frappe.pages["pricing-builder-builder"].on_page_load = function (wrapper) {
        const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Pricing Builder"), single_column: true });
        wrapper.page = page;
        page.main.addClass("pbb-root");
        injectStyles();
        STATE.sourcingRulesOpen = readSourcingRulesOpen();
        STATE.autoRecalculate = readAutoRecalculate();
        applyHeader(page);
        load(page, currentName());
    };

    frappe.pages["pricing-builder-builder"].on_page_show = function (wrapper) {
        if (!wrapper.page) return;
        applyHeader(wrapper.page);
        STATE.autoRecalculate = readAutoRecalculate();
        load(wrapper.page, currentName());
    };

    frappe.pages["pricing-builder-builder"].on_page_hide = function () {
        stopAutoRecalculateLoop();
    };

    function currentName() {
        const route = frappe.get_route() || [];
        return route[1] || "new";
    }

    function applyHeader(page) {
        page.set_title(__("Pricing Builder"));
        page.set_primary_action(__("Save"), () => save(page));
    }

    async function load(page, name) {
        stopAutoRecalculateLoop();
        STATE.loading = true;
        STATE.error = "";
        render(page);
        try {
            const res = await frappe.call({
                method: "orderlift.orderlift_sales.page.pricing_builder_builder.pricing_builder_builder.get_builder_page_data",
                args: { name: name || "new" },
            });
            const data = res.message || {};
            STATE.doc = normalizeDoc(data.doc || {});
            STATE.refs = data.references || {};
            STATE.history = data.history || [];
            STATE.priceListMode = resolvePriceListMode(STATE.doc, STATE.refs);
            ensureBreakdownSelection();
            startOpenRefreshFlow(page, name);
        } catch (error) {
            console.error("Pricing Builder load failed", error);
            STATE.error = __("Unable to load this builder.");
            STATE.doc = null;
        } finally {
            STATE.loading = false;
            render(page);
        }
    }

    async function save(page, options) {
        if (!STATE.doc) return null;
        if (STATE.saving) return savePromise;
        options = options || {};
        syncVisibleInputs(page);
        if (options.autosave) {
            const blockReason = autosaveBlockReason(STATE.doc);
            if (blockReason) {
                STATE.autosaveStatus = blockReason;
                return null;
            }
        }
        const draftRuleRows = options.autosave ? (STATE.doc.sourcing_rules || []).filter(isBlankSourcingRule).map(cloneSourcingRule) : [];
        STATE.saving = true;
        STATE.autosaveStatus = options.autosave ? __("Autosaving...") : __("Saving...");
        if (options.render !== false) render(page);
        savePromise = (async () => {
            const res = await frappe.call({
                method: "orderlift.orderlift_sales.page.pricing_builder_builder.pricing_builder_builder.save_builder_page_doc",
                args: { payload: STATE.doc, create_history: 1, history_label: options.historyLabel || (options.autosave ? __("Autosaved") : __("Saved")) },
                freeze: Boolean(options && options.freeze),
                freeze_message: __("Saving builder..."),
            });
            STATE.doc = normalizeDoc((res.message || {}).doc || {});
            if (draftRuleRows.length) {
                STATE.doc.sourcing_rules = (STATE.doc.sourcing_rules || []).concat(draftRuleRows);
            }
            STATE.history = (res.message || {}).history || STATE.history || [];
            ensureBreakdownSelection();
            if (!options.noRoute && STATE.doc.name && currentName() !== STATE.doc.name) {
                frappe.set_route("pricing-builder-builder", STATE.doc.name);
            }
            STATE.autosaveStatus = options.autosave ? __("Autosaved") : __("Saved");
            if (!options.autosave && options.showCustomsAlert !== false) showCustomsIssueAlert(customsIssueRows(customsReviewRows()), __("Customs Review"));
            return STATE.doc;
        })();
        try {
            return await savePromise;
        } finally {
            STATE.saving = false;
            savePromise = null;
            if (options.render !== false) render(page);
        }
    }

    async function saveLatest(page, options) {
        clearTimeout(autosaveTimer);
        if (savePromise) await savePromise;
        syncVisibleInputs(page);
        return save(page, options || {});
    }

    async function calculate(page, options) {
        options = options || {};
        const freeze = options.freeze !== false;
        const doc = await save(page, { freeze, showCustomsAlert: false, render: options.renderSave !== false, noRoute: options.noRoute });
        if (!doc || !doc.name || doc.name === "new") return;
        const res = await frappe.call({
            method: "orderlift.orderlift_sales.page.pricing_builder_builder.pricing_builder_builder.calculate_builder_page_doc",
            args: { name: doc.name },
            freeze,
            freeze_message: __("Calculating builder prices..."),
        });
        STATE.doc = normalizeDoc((res.message || {}).doc || {});
        STATE.history = (res.message || {}).history || [];
        ensureBreakdownSelection();
        if (options.showCustomsAlert !== false) showCustomsIssueAlert(customsIssueRows(customsReviewRows()), __("Customs Review"));
        if (options.status) STATE.autoRecalculateStatus = options.status;
        render(page, { preserveScroll: Boolean(options.preserveScroll) });
        return STATE.doc;
    }

    async function checkFreshness(page) {
        if (!STATE.doc || STATE.doc.name === "new" || STATE.checkingFreshness) return;
        const checkKey = `${STATE.doc.name}:${STATE.doc.modified || ""}`;
        if (STATE.stalePromptKey === checkKey) return;
        STATE.checkingFreshness = true;
        STATE.autoRecalculateStatus = __("Checking latest calculation...");
        render(page, { preserveScroll: true });
        try {
            const res = await frappe.call({
                method: "orderlift.orderlift_sales.page.pricing_builder_builder.pricing_builder_builder.compare_recalculated_builder_page_doc",
                args: { name: STATE.doc.name },
            });
            const out = res.message || {};
            if (!out.changed) {
                STATE.autoRecalculateStatus = __("Current calculation is up to date");
                return;
            }
            STATE.stalePromptKey = checkKey;
            const summary = staleSummary(out.summary || {});
            frappe.confirm(
                __("This builder has newer calculated values available. Recalculate now?{0}", [summary ? `<br><br>${summary}` : ""]),
                async () => calculate(page, { freeze: true, status: __("Recalculated after freshness check"), preserveScroll: true, noRoute: true })
            );
        } catch (error) {
            console.warn("Pricing Builder freshness check failed", error);
            STATE.autoRecalculateStatus = __("Freshness check failed");
        } finally {
            STATE.checkingFreshness = false;
            render(page, { preserveScroll: true });
        }
    }

    function staleSummary(summary) {
        const parts = [];
        if (summary.total_items_changed) parts.push(__("items: {0}", [summary.total_items_changed]));
        if (summary.price_changes) parts.push(__("price changes: {0}", [summary.price_changes]));
        if (summary.status_changes) parts.push(__("status changes: {0}", [summary.status_changes]));
        if (summary.warning_changed) parts.push(__("warnings changed"));
        return parts.length ? escapeHtml(parts.join(" | ")) : "";
    }

    async function autoRecalculateNow(page) {
        if (!STATE.autoRecalculate || !STATE.doc || STATE.doc.name === "new" || STATE.loading || STATE.saving) return;
        STATE.autoRecalculateStatus = __("Auto recalculating...");
        render(page, { preserveScroll: true });
        try {
            await calculate(page, { freeze: false, showCustomsAlert: false, status: __("Auto recalculated {0}", [frappe.datetime.now_time()]), renderSave: false, preserveScroll: true, noRoute: true });
        } catch (error) {
            console.error("Pricing Builder auto recalculation failed", error);
            STATE.autoRecalculateStatus = __("Auto recalculation failed");
            render(page, { preserveScroll: true });
        }
    }

    function startOpenRefreshFlow(page, name) {
        stopAutoRecalculateLoop();
        if (!STATE.doc || STATE.doc.name === "new" || (name || "new") === "new") return;
        if (STATE.autoRecalculate) {
            setTimeout(() => autoRecalculateNow(page), 0);
            autoRecalculateTimer = setInterval(() => autoRecalculateNow(page), AUTO_RECALCULATE_INTERVAL_MS);
        } else {
            setTimeout(() => checkFreshness(page), 0);
        }
    }

    function stopAutoRecalculateLoop() {
        if (autoRecalculateTimer) clearInterval(autoRecalculateTimer);
        autoRecalculateTimer = null;
    }

    async function publish(page, selectedOnly, selectedRows) {
        if (!STATE.doc || !STATE.doc.selling_price_list_name) {
            frappe.throw(__("Enter the Selling Price List Name before publishing."));
        }
        const doc = await saveLatest(page, { freeze: true, showCustomsAlert: false });
        if (!doc || !doc.name || doc.name === "new") return;
        const rowsToPublish = selectedRows || selectedPublishRows(doc);
        const response = await frappe.call({
            method: "orderlift.orderlift_sales.page.pricing_builder_builder.pricing_builder_builder.publish_builder_page_doc",
            args: { name: doc.name, selected_only: selectedOnly ? 1 : 0, selected_rows: selectedOnly ? rowsToPublish : null },
            freeze: true,
            freeze_message: __("Publishing prices..."),
        });
        const out = (response.message || {}).publish || {};
        STATE.doc = normalizeDoc((response.message || {}).doc || STATE.doc || {});
        STATE.history = (response.message || {}).history || STATE.history || [];
        frappe.show_alert({
            message: [
                __("Price List: {0}", [out.price_list || doc.selling_price_list_name]),
                __("Created: {0}", [out.created || 0]),
                __("Updated: {0}", [out.updated || 0]),
                __("Skipped: {0}", [out.skipped || 0]),
            ].join(" | "),
            indicator: (out.errors || []).length ? "orange" : "green",
        }, 8);
        ensureBreakdownSelection();
        render(page);
    }

    async function previewPublish(page) {
        if (!STATE.doc || !STATE.doc.selling_price_list_name) {
            frappe.throw(__("Select or enter the target Selling Price List before publishing."));
        }
        const doc = await saveLatest(page, { freeze: true, showCustomsAlert: false, render: false, historyLabel: __("Saved before publish") });
        if (!doc || !doc.name || doc.name === "new") return;
        const selectedRows = (doc.builder_items || []).filter((row) => toNumber(row.selected));
        if (!selectedRows.length) {
            frappe.msgprint({ title: __("No Items Selected"), message: __("Select at least one Builder Item before publishing."), indicator: "orange" });
            return;
        }
        const selectedRowsPayload = selectedRows.map(selectedPublishRow);
        const isUpdate = (STATE.refs.selling_price_lists || []).includes(doc.selling_price_list_name);
        const customsIssues = customsIssueRows(selectedRows);
        const customsAlert = customsIssues.length ? customsIssueHtml(customsIssues) : "";
        const rowsHtml = selectedRows.slice(0, 120).map((row) => {
            const nextPrice = finalSellUnit(row);
            const delta = nextPrice - toNumber(row.published_price);
            return `<tr><td><strong>${escapeHtml(row.item)}</strong><small>${escapeHtml(row.item_name || "")}</small></td><td>${money(row.published_price)}</td><td>${previewNewPriceCell(row, nextPrice)}</td><td class="${delta < 0 ? "pbb-negative" : "pbb-positive"}">${money(delta)}</td><td>${escapeHtml(row.status || "")}</td></tr>`;
        }).join("");
        const overflowNote = selectedRows.length > 120 ? `<p class="pbb-preview-note">${__("Showing first 120 of {0} selected items.", [selectedRows.length])}</p>` : "";
        const dialog = new frappe.ui.Dialog({
            title: __("Preview & Publish"),
            size: "extra-large",
            fields: [{ fieldtype: "HTML", fieldname: "preview" }],
            primary_action_label: isUpdate ? __("Confirm Update") : __("Confirm Publish"),
            primary_action: () => {
                frappe.confirm(
                    isUpdate
                        ? __("This will update {0} selected item prices in existing list {1}. Continue?", [selectedRows.length, doc.selling_price_list_name])
                        : __("This will publish {0} selected item prices to new list {1}. Continue?", [selectedRows.length, doc.selling_price_list_name]),
                    async () => {
                        dialog.hide();
                        if (isUpdate) {
                            frappe.show_alert({ message: __("Updating existing selling list {0}.", [doc.selling_price_list_name]), indicator: "orange" }, 6);
                        }
                        await publish(page, true, selectedRowsPayload);
                    }
                );
            },
        });
        dialog.fields_dict.preview.$wrapper.html(`
            <div class="pbb-preview-dialog">
                <div class="pbb-preview-target ${isUpdate ? "update" : "new"}">
                    <span>${isUpdate ? __("Update Existing List") : __("Create New List")}</span>
                    <strong>${escapeHtml(doc.selling_price_list_name)}</strong>
                    <em>${__("Selected items: {0}", [selectedRows.length])}</em>
                </div>
                ${isUpdate ? `<div class="pbb-update-alert">${__("Existing Item Prices in this list may be changed. Review the current and new prices before confirming.")}</div>` : ""}
                <div class="pbb-preview-table-wrap"><table class="pbb-preview-table"><thead><tr><th>${__("Item")}</th><th>${__("Current")}</th><th>${__("New")}</th><th>${__("Change")}</th><th>${__("Status")}</th></tr></thead><tbody>${rowsHtml}</tbody></table></div>
                ${overflowNote}
                ${customsAlert}
            </div>`);
        dialog.show();
    }

    function previewNewPriceCell(row, nextPrice) {
        const override = toNumber(row.override_selling_price);
        const label = override > 0 ? `<small class="pbb-preview-override">${escapeHtml(__("Manual override"))}</small>` : "";
        return `<strong>${money(nextPrice)}</strong>${label}`;
    }

    function selectedPublishRows(doc) {
        return ((doc || {}).builder_items || []).filter((row) => toNumber(row.selected)).map(selectedPublishRow);
    }

    function selectedPublishRow(row) {
        return { item: row.item || "", buying_list: row.buying_list || "" };
    }

    function customsReviewRows() {
        const rows = (STATE.doc || {}).builder_items || [];
        const selected = rows.filter((row) => toNumber(row.selected));
        return selected.length ? selected : rows;
    }

    function customsIssueRows(rows) {
        return (rows || []).map((row) => {
            if (!String(row.customs_policy || "").trim()) return null;
            const basis = String(row.customs_basis || "");
            const usedFallback = basis.toLowerCase().includes("weight fallback");
            const zeroCustoms = toNumber(row.customs_amount) <= 0;
            if (!usedFallback && !zeroCustoms) return null;
            return {
                item: row.item || "",
                item_name: row.item_name || "",
                reason: usedFallback
                    ? __("Weight missing; customs calculated from buying amount")
                    : __("Customs policy is set but customs amount is zero"),
                customs_policy: row.customs_policy || "",
                customs_basis: basis || "-",
            };
        }).filter(Boolean);
    }

    function customsIssueHtml(issues) {
        const rows = (issues || []).slice(0, 12).map((issue) => `<li><strong>${escapeHtml(issue.item)}</strong> ${escapeHtml(issue.item_name || "")}<br><small>${escapeHtml(issue.reason)} | ${escapeHtml(issue.customs_policy)} | ${escapeHtml(issue.customs_basis)}</small></li>`).join("");
        const overflow = (issues || []).length > 12 ? `<p>${__("Showing first 12 of {0} affected item(s).", [issues.length])}</p>` : "";
        return `<div class="pbb-customs-alert" role="alert"><strong>${__("Customs review needed")}</strong><p>${__("These items have a customs policy but customs is missing, zero, or calculated using the buying-amount fallback.")}</p><ul>${rows}</ul>${overflow}</div>`;
    }

    function showCustomsIssueAlert(issues, title) {
        if (!(issues || []).length) return;
        frappe.msgprint({
            title: title || __("Customs Review"),
            message: customsIssueHtml(issues),
            indicator: "orange",
        });
    }

    function render(page, options) {
        options = options || {};
        const previousScroll = getScrollState(page);
        if (STATE.loading) {
            page.main.html(`<div class="pbb-shell">${skeleton()}</div>`);
            restoreScrollState(page, previousScroll, options);
            return;
        }
        if (STATE.error) {
            page.main.html(`<div class="pbb-shell"><div class="pbb-error">${escapeHtml(STATE.error)}</div></div>`);
            restoreScrollState(page, previousScroll, options);
            return;
        }
        const doc = STATE.doc || normalizeDoc({});
        page.main.html(`
            <div class="pbb-shell">
                ${referenceLists()}
                <section class="pbb-hero">
                    <div><button type="button" class="pbb-link" data-back>${__("Back to builders")}</button><h1>${escapeHtml(doc.builder_name || __("New Pricing Builder"))}</h1><p>${escapeHtml(doc.selling_price_list_name || __("No selling price list selected"))}</p></div>
                    <div class="pbb-hero-actions">
                        <label class="pbb-auto-recalc"><input type="checkbox" data-auto-recalculate ${STATE.autoRecalculate ? "checked" : ""}><span>${__("Auto recalculate")}</span></label>
                        <span class="pbb-auto-recalc-status">${escapeHtml(STATE.autoRecalculateStatus || (STATE.autoRecalculate ? __("Runs while this builder is open") : __("Checks for stale prices on open")))}</span>
                        <span class="pbb-autosave-status">${escapeHtml(STATE.autosaveStatus || __("Autosave enabled"))}</span>
                    </div>
                </section>
                <section class="pbb-grid compact">
                    <div class="pbb-card pbb-setup">${setupPanel(doc)}</div>
                    <div class="pbb-card">${summaryPanel(doc)}</div>
                </section>
                <section class="pbb-card">${rulesPanel(doc)}</section>
                <section class="pbb-card">${builderTabsPanel(doc)}</section>
                <section class="pbb-card">${warningsPanel(doc)}</section>
            </div>`);
        bind(page);
        restoreScrollState(page, previousScroll, options);
    }

    function setupPanel(doc) {
        return `<h2>${__("Builder Setup")}</h2>
            <div class="pbb-fields">
                ${field("builder_name", __("Builder Name"), doc.builder_name, "text")}
                ${sellingPriceListField(doc)}
            </div>
            ${exchangeRatePanel(doc)}`;
    }

    function sellingPriceListField(doc) {
        if (STATE.priceListMode === "new") {
            return `<label class="pbb-price-list-field"><span>${__("Selling Price List")}</span><div class="pbb-price-list-mode new"><select data-price-list-mode><option value="existing">${__("Update Existing List")}</option><option value="new" selected>${__("Create New List")}</option></select><input data-parent-field="selling_price_list_name" type="text" value="${escapeHtml(doc.selling_price_list_name || "")}" placeholder="${escapeHtml(__("New list name"))}"><select data-parent-field="target_currency">${currencyOptions(doc.target_currency || defaultTargetCurrency())}</select></div><small>${escapeHtml(__("New list will be created in {0} for {1}.", [targetCurrency(doc), STATE.refs.current_company || __("current company")]))}</small></label>`;
        }
        const options = (STATE.refs.selling_price_lists || []).map((value) => `<option value="${escapeHtml(value)}" ${value === doc.selling_price_list_name ? "selected" : ""}>${escapeHtml(priceListLabel(value, "selling"))}</option>`).join("");
        return `<label class="pbb-price-list-field"><span>${__("Selling Price List")}</span><div class="pbb-price-list-mode existing"><select data-price-list-mode><option value="existing" selected>${__("Update Existing List")}</option><option value="new">${__("Create New List")}</option></select><select data-parent-field="selling_price_list_name"><option value="">${__("Select existing list")}</option>${options}</select></div><small>${escapeHtml(doc.selling_price_list_name ? __("Target Currency: {0}", [targetCurrency(doc)]) : __("Choose an existing list to use its configured currency."))}</small></label>`;
    }

    function exchangeRatePanel(doc) {
        const summary = doc.exchange_rate_summary || {};
        const rates = summary.rates || [];
        const target = summary.target_currency || targetCurrency(doc);
        if (!rates.length) {
            return `<details class="pbb-rate-details"><summary><span>${escapeHtml(__("Exchange rates"))}</span><small>${escapeHtml(__("Target Currency: {0} | no conversion needed", [target || "-"]))}</small></summary><p>${escapeHtml(__("No currency conversion is needed for the current active sourcing rules."))}</p></details>`;
        }
        return `<details class="pbb-rate-details"><summary><span>${escapeHtml(__("Exchange Rates Used"))}</span><small>${escapeHtml(__("Target Currency: {0} | synced from system Currency Exchange records", [target || "-"]))}</small></summary><div class="pbb-rate-list">${rates.map(exchangeRateRow).join("")}</div></details>`;
    }

    function exchangeRateRow(row) {
        const missing = toNumber(row.missing);
        const rate = missing ? __("Missing") : toNumber(row.exchange_rate).toFixed(6);
        const detail = missing ? (row.message || __("Add a Currency Exchange record before calculating/publishing.")) : [row.source || __("Currency Exchange"), row.rate_date || ""].filter(Boolean).join(" | ");
        return `<div class="pbb-rate-row ${missing ? "missing" : ""}"><span><em>${escapeHtml(row.usage || __("Source"))}</em><strong>${escapeHtml(row.price_list || "-")}</strong></span><span><em>${escapeHtml(__("Pair"))}</em><strong>${escapeHtml((row.from_currency || "-") + " -> " + (row.to_currency || "-"))}</strong></span><span><em>${escapeHtml(__("Rate"))}</em><strong>${escapeHtml(rate)}</strong></span><small>${escapeHtml(detail)}</small></div>`;
    }

    function rulesPanel(doc) {
        const rows = doc.sourcing_rules || [];
        const table = `<div class="pbb-table-wrap"><table class="pbb-rules-table"><thead><tr><th>${__("Active")}</th><th>${__("Buying Price List")}</th><th>${__("Expenses Policy")}</th><th>${__("Customs Policy")}</th><th>${__("Margin Policy")}</th><th></th></tr></thead><tbody>
            ${rows.length ? rows.map(ruleRow).join("") : `<tr><td colspan="6" class="pbb-empty-cell">${__("No rules yet. Add at least one active rule before calculating.")}</td></tr>`}
            </tbody></table></div>`;
        return `<div class="pbb-section-head pbb-collapsible-head"><div><h2>${__("Sourcing Rules")}</h2><p>${__("Map each buying list to the expenses, customs, and margin policies used during calculation.")}</p></div><div class="pbb-inline-actions"><button type="button" class="pbb-btn ghost" data-toggle-rules aria-expanded="${STATE.sourcingRulesOpen ? "true" : "false"}">${STATE.sourcingRulesOpen ? __("Hide") : __("Show")}</button><button type="button" class="pbb-btn ghost" data-add-rule>${__("Add Rule")}</button><button type="button" class="pbb-btn primary" data-calculate>${__("Load Items & Calculate")}</button></div></div>
            ${STATE.sourcingRulesOpen ? table : `<div class="pbb-collapsed-note">${__("{0} sourcing rule(s) hidden. Use Show to edit buying list mappings.", [rows.length])}</div>`}`;
    }

    function ruleRow(row, index) {
        return `<tr data-rule-row="${index}">
            <td><input type="checkbox" data-rule-field="is_active" ${toNumber(row.is_active) ? "checked" : ""}></td>
            <td>${cellInput("buying_price_list", row.buying_price_list, "pbb-buying-lists")}</td>
            <td>${cellInput("pricing_scenario", row.pricing_scenario, "pbb-scenarios")}</td>
            <td>${cellInput("customs_policy", row.customs_policy, "pbb-customs")}</td>
            <td>${cellInput("benchmark_policy", row.benchmark_policy, "pbb-benchmarks")}</td>
            <td><button type="button" class="pbb-icon-btn" data-delete-rule="${index}">${__("Remove")}</button></td>
        </tr>`;
    }

    function builderTabsPanel(doc) {
        const tabs = [
            ["items", __("Items")],
            ["breakdown", __("Breakdown")],
            ["history", __("History")],
        ];
        const body = STATE.activeTab === "breakdown" ? breakdownPanel(doc) : STATE.activeTab === "history" ? historyPanel(doc) : itemsPanel(doc);
        return `<div class="pbb-tabs">${tabs.map(([key, label]) => `<button type="button" class="${STATE.activeTab === key ? "active" : ""}" data-tab="${key}">${escapeHtml(label)}</button>`).join("")}</div>${body}`;
    }

    function itemsPanel(doc) {
        const rows = filteredItems(doc.builder_items || []);
        const columns = itemTableColumns();
        return `<div class="pbb-section-head"><div><h2>${__("Builder Items")}</h2><p>${__("Review calculated costs, sell prices, selection, and manual sell price overrides.")}</p></div><div class="pbb-inline-actions"><button type="button" class="pbb-btn ghost" data-select-all>${__("Select All")}</button><button type="button" class="pbb-btn ghost" data-clear-selected>${__("Clear Selection")}</button><button type="button" class="pbb-btn primary" data-preview-publish>${__("Preview & Publish")}</button></div></div>
            <div class="pbb-filters"><input type="search" data-filter value="${escapeHtml(STATE.filter)}" placeholder="${escapeHtml(__("Search item, name, group, buying list..."))}"><select data-status-filter><option value="">${__("All statuses")}</option>${statusOptions(doc).map((value) => `<option value="${escapeHtml(value)}" ${STATE.status === value ? "selected" : ""}>${escapeHtml(value)}</option>`).join("")}</select><button type="button" class="pbb-btn ghost" data-clear-column-filters ${hasItemColumnFilters() ? "" : "disabled"}>${__("Clear Column Filters")}</button></div>
            ${columnConfigurator()}
            <div class="pbb-table-wrap pbb-items-scroll"><table class="pbb-items-table" style="min-width:${itemTableMinWidth(columns)}px"><thead><tr>${columns.map(itemHeaderCell).join("")}</tr><tr class="pbb-column-filter-row">${columns.map(itemFilterCell).join("")}</tr></thead><tbody>
            ${rows.length ? rows.map((entry) => itemRow(entry, columns)).join("") : `<tr><td colspan="${columns.length}" class="pbb-empty-cell">${__("No calculated items yet. Save setup, then calculate.")}</td></tr>`}
            </tbody></table></div>${itemTableFooter(doc, rows)}`;
    }

    function itemTableFooter(doc, visibleRows) {
        const allRows = (doc.builder_items || []);
        const selectedCount = allRows.filter((row) => toNumber(row.selected)).length;
        const sourceLists = activeSourceBuyingLists(doc);
        return `<div class="pbb-items-footer"><span>${escapeHtml(__("Showing {0} of {1} loaded items", [visibleRows.length, allRows.length]))}</span><span>${escapeHtml(__("Selected: {0}", [selectedCount]))}</span><span title="${escapeHtml(sourceLists.join(", "))}">${escapeHtml(__("Source buying lists: {0}", [sourceLists.length ? sourceLists.join(", ") : "-"]))}</span></div>`;
    }

    function activeSourceBuyingLists(doc) {
        const seen = new Set();
        const out = [];
        (doc.sourcing_rules || []).forEach((row) => {
            if (row.is_active != null && !toNumber(row.is_active)) return;
            const value = String(row.buying_price_list || "").trim();
            if (!value || seen.has(value)) return;
            seen.add(value);
            out.push(value);
        });
        return out;
    }


    function breakdownPanel(doc) {
        const rows = doc.builder_items || [];
        if (!rows.length) return `<div class="pbb-empty-cell pbb-breakdown-empty">${__("Calculate items first to view selling price breakdowns.")}</div>`;
        ensureBreakdownSelection();
        const selected = selectedBreakdownEntry();
        const row = selected.row || rows[0] || {};
        const qty = toNumber(doc.default_qty) || 1;
        const costUnit = costBeforeMargin(row);
        const sellUnit = finalSellUnit(row);
        const breakdown = parseCalculationBreakdown(row.calculation_breakdown_json);
        const options = rows.map((candidate, index) => {
            const key = builderItemKey(candidate, index);
            const label = [candidate.item, candidate.item_name].filter(Boolean).join(" - ") || key;
            return `<option value="${escapeHtml(label)}" data-key="${escapeHtml(key)}"></option>`;
        }).join("");
        const selectedLabel = [row.item, row.item_name].filter(Boolean).join(" - ") || STATE.selectedBreakdownKey;
        return `<div class="pbb-breakdown-panel">
            <div class="pbb-breakdown-head"><label class="pbb-breakdown-selector"><span>${__("Select Item")}</span><input data-breakdown-search list="pbb-breakdown-items" value="${escapeHtml(selectedLabel)}" placeholder="${escapeHtml(__("Search item..."))}"><datalist id="pbb-breakdown-items">${options}</datalist></label><div class="pbb-breakdown-selected"><strong>${escapeHtml(row.item || "-")}</strong><small>${escapeHtml(row.item_name || "")}</small></div></div>
            <div class="pbb-breakdown-metrics">
                ${breakdownMetric(__("Base PU"), money(row.base_buy_price))}
                ${breakdownMetric(__("Expenses U"), money(row.expenses))}
                ${breakdownMetric(__("Customs U"), money(row.customs_amount))}${toNumber(row.customs_value_delta_tax_amount) > 0 ? breakdownMetric(__("Delta Tax U"), money(row.customs_value_delta_tax_amount)) : ""}
                ${breakdownMetric(__("Total Cost U"), money(costUnit), "highlight")}
                ${breakdownMetric(__("Margin U"), money(row.margin_amount))}
                ${breakdownMetric(__("Total Margin U"), money(row.total_margin_amount))}
                ${breakdownMetric(__("Sell Price U"), money(sellUnit), "highlight")}
                ${breakdownMetric(__("Total Sell"), money(sellUnit * qty))}
                ${breakdownMetric(__("Margin %"), `${toNumber(row.final_margin_pct).toFixed(2)}%`)}
                ${breakdownMetric(__("Total Margin %"), `${toNumber(row.total_margin_pct).toFixed(2)}%`)}
            </div>
            ${priceStory(row, breakdown, qty)}
            <div class="pbb-breakdown-grid">
                <div class="pbb-breakdown-details">
                    ${detail(__("Buying List"), row.buying_list)}${detail(__("Pricing Scenario"), row.pricing_scenario)}${detail(__("Customs Policy"), row.customs_policy)}${detail(__("Benchmark Policy"), row.benchmark_policy)}${detail(__("Benchmark Rule"), row.benchmark_rule_label || (toNumber(row.benchmark_is_fallback) ? __("Fallback Margin") : ""))}${detail(__("Margin Basis"), row.margin_basis)}${detail(__("Policy Max Discount"), `${toNumber(row.policy_max_discount_percent).toFixed(2)}%`)}${detail(__("Benchmark"), money(row.avg_benchmark))}${detail(__("Item Category"), row.item_category)}${detail(__("Tariff"), row.customs_tariff_number)}${detail(__("Material"), row.material)}${detail(__("Origin"), row.origin)}${detail(__("Customs Weight U"), `${toNumber(row.customs_weight_kg).toFixed(3)} kg`)}${detail(__("Line Customs Weight"), `${toNumber(row.customs_line_weight_kg).toFixed(3)} kg`)}${detail(__("Package Weight"), `${toNumber(row.customs_package_weight_kg).toFixed(3)} kg`)}${detail(__("Units / Package"), toNumber(row.packaging_units_per_package).toFixed(2))}${detail(__("Package Count"), toNumber(row.packaging_package_count).toFixed(2))}${detail(__("Packaging Source"), row.packaging_profile_source)}${detail(__("Customs Basis"), row.customs_basis)}${detail(__("Status"), row.status_note || row.status)}
                </div>
                <div class="pbb-calculation-stack">${calculationSections(row, breakdown, qty)}</div>
            </div>
        </div>`;
    }

    function parseCalculationBreakdown(value) {
        if (value && typeof value === "object") return value;
        const text = String(value || "").trim();
        if (!text) return {};
        try {
            return JSON.parse(text) || {};
        } catch (error) {
            return {};
        }
    }

    function priceStory(row, breakdown, qty) {
        const summary = breakdown.summary || {};
        const base = pickNumber(summary.base_unit, row.base_buy_price);
        const expenses = pickNumber(summary.expenses_unit, row.expenses);
        const customs = pickNumber(summary.customs_unit, row.customs_amount);
        const margin = pickNumber(summary.margin_unit, row.margin_amount);
        const calculated = pickNumber(summary.projected_unit, row.projected_price);
        const override = toNumber(row.override_selling_price);
        const finalUnit = override > 0 ? override : calculated;
        const overrideNote = override > 0 ? `<small>${__("Manual override replaces the calculated sell price.")}</small>` : "";
        return `<div class="pbb-price-story">
            <strong>${__("Price formula")}</strong>
            <div class="pbb-price-formula">
                ${formulaChip(__("Base"), money(base))}<b>+</b>${formulaChip(__("Expenses"), money(expenses))}<b>+</b>${formulaChip(__("Customs"), money(customs))}<b>+</b>${formulaChip(__("Margin"), money(margin))}<b>=</b>${formulaChip(__("Calculated"), money(calculated), "highlight")}${override > 0 ? `<b>${__("then")}</b>${formulaChip(__("Override"), money(finalUnit), "highlight")}` : ""}
            </div>
            ${overrideNote}
            <em>${escapeHtml(__("Qty {0}: total sell {1}", [qty, money(finalUnit * qty)]))}</em>
        </div>`;
    }

    function formulaChip(label, value, tone) {
        return `<span class="${tone || ""}"><em>${escapeHtml(label)}</em><strong>${escapeHtml(value)}</strong></span>`;
    }

    function calculationSections(row, breakdown, qty) {
        return [expensesSection(row, breakdown.expenses || {}, qty), customsSection(row, breakdown.customs || {}, qty), marginSection(row, breakdown.margin || {}, qty)].join("");
    }

    function expensesSection(row, expenses, qty) {
        const steps = Array.isArray(expenses.steps) ? expenses.steps : [];
        const rows = steps.length ? steps.map((step) => `<tr><td>${escapeHtml(step.label || __("Expense"))}</td><td>${expenseFormula(step, qty)}</td><td>${money(step.unit_amount)}</td></tr>`).join("") : `<tr><td colspan="3">${escapeHtml(__("No expense steps applied."))}</td></tr>`;
        return `<section class="pbb-calc-section">
            <h3>${__("Expenses")}</h3>
            <p>${escapeHtml(__("Policy: {0}. Total expenses per unit: {1}.", [expenses.policy || row.pricing_scenario || "-", money(pickNumber(expenses.unit, row.expenses))]))}</p>
            ${calcTable([__("Step"), __("Formula"), __("Unit Impact")], rows)}
        </section>`;
    }

    function customsSection(row, customs, qty) {
        const total = pickNumber(customs.total, toNumber(row.customs_amount) * qty);
        const unit = pickNumber(customs.unit, row.customs_amount);
        const rate = toNumber(customs.rate_percent);
        const rateLabel = customs.component_display ? `${escapeHtml(customs.component_display)}% = ${percent(rate)}` : percent(rate);
        const deltaTaxAmount = toNumber(customs.customs_value_delta_tax_amount);
        const hasDeltaTax = deltaTaxAmount > 0;
        const baseCustomsTotal = hasDeltaTax ? pickNumber(customs.base_customs_total, total - deltaTaxAmount) : total;
        const baseCustomsUnit = hasDeltaTax ? pickNumber(customs.base_customs_unit, baseCustomsTotal / (qty || 1)) : unit;
        const formula = total > 0 ? customsFormula(customs, baseCustomsTotal, rateLabel, qty, hasDeltaTax, deltaTaxAmount) : escapeHtml(customs.warning || __("No customs amount applied."));
        let detailRows = `${detail(__("Tariff"), customs.tariff_number || row.customs_tariff_number)}${detail(__("Material"), customs.material || row.material)}${detail(__("Basis"), customs.basis || row.customs_basis)}${detail(__("Weight"), `${toNumber(customs.weight_kg || row.customs_line_weight_kg).toFixed(3)} kg`)}${detail(__("Value / Kg"), money(customs.value_per_kg || row.customs_value_per_kg))}${detail(__("Rate"), rateLabel)}${detail(__("Total"), money(total))}${detail(__("Per Unit"), money(unit))}`;
        if (hasDeltaTax) {
            const deltaRate = toNumber(customs.customs_value_delta_tax_rate);
            const delta = toNumber(customs.customs_value_delta);
            detailRows += `${detail(__("Base Customs"), money(baseCustomsTotal))}${detail(__("Base Customs U"), money(baseCustomsUnit))}${detail(__("Delta"), `(${money(customs.base_value)} − ${money(delta > 0 ? customs.base_value - delta : 0)}) = ${money(delta)}`)}${detail(__("Delta Tax Rate"), `${deltaRate.toFixed(2)}%`)}${detail(__("Delta Tax"), money(deltaTaxAmount))}${detail(__("Delta Tax U"), money(deltaTaxAmount / (qty || 1)))}`;
            if (customs.customs_value_delta_tax_template) detailRows += `${detail(__("Delta Tax Template"), escapeHtml(customs.customs_value_delta_tax_template))}`;
        }
        return `<section class="pbb-calc-section">
            <h3>${__("Customs")}</h3>
            <p>${escapeHtml(__("Policy: {0}. Unit customs: {1}.", [customs.policy || row.customs_policy || "-", money(unit)]))}</p>
            <div class="pbb-calc-note">${formula}</div>
            <div class="pbb-calc-facts">
                ${detailRows}
            </div>
        </section>`;
    }

    function marginSection(row, margin) {
        const target = pickNumber(margin.target_margin_percent, row.target_margin_percent);
        const unit = pickNumber(margin.unit, row.margin_amount);
        const basisAmount = pickNumber(margin.basis_amount, margin.basis === "Base Price" ? row.base_buy_price : costBeforeMargin(row));
        const selected = toNumber(margin.is_fallback) ? fallbackMarginText(margin) : benchmarkMarginText(margin);
        return `<section class="pbb-calc-section">
            <h3>${__("Margin")}</h3>
            <p>${selected}</p>
            <div class="pbb-calc-note">${marginFormula(margin.basis || row.margin_basis, basisAmount, target, unit)}</div>
            <div class="pbb-calc-facts">
                ${detail(__("Policy"), margin.policy_name || margin.policy || row.benchmark_policy)}${detail(__("Basis"), margin.basis || row.margin_basis)}${detail(__("Target"), percent(target))}${detail(__("Benchmark"), money(margin.benchmark_reference || row.avg_benchmark))}${detail(__("Ratio"), toNumber(margin.ratio).toFixed(4))}${detail(__("Max Discount"), percent(margin.max_discount_percent || row.policy_max_discount_percent))}${detail(__("Margin U"), money(unit))}
            </div>
        </section>`;
    }

    function expenseFormula(step, qty) {
        const type = String(step.type || "");
        const scope = String(step.scope || "");
        if (type === "Percentage") return `${money(step.basis)} × ${percent(step.value)}`;
        if (scope === "Per Line") return `${money(step.value)} ÷ ${qty}`;
        if (scope === "Per Sheet") return `${money(step.value)} ÷ ${qty}`;
        return `${money(step.value)} ${escapeHtml(scope || __("Per Unit"))}`;
    }

    function customsFormula(customs, baseCustomsTotal, rateLabel, qty, hasDeltaTax, deltaTaxAmount) {
        const buyAmount = toNumber(customs.base_value) - toNumber(customs.customs_value_delta || 0);
        if (hasDeltaTax) {
            const delta = toNumber(customs.customs_value_delta);
            const deltaRate = toNumber(customs.customs_value_delta_tax_rate);
            const baseCustomsUnit = baseCustomsTotal / (qty || 1);
            const deltaTaxUnit = deltaTaxAmount / (qty || 1);
            if (customs.mode === "buying_amount_fallback") {
                return `${escapeHtml(__("Buying amount fallback"))}: ${money(customs.base_value)} × ${rateLabel} = ${money(baseCustomsTotal)}; ${money(baseCustomsTotal)} ÷ ${qty} = ${money(baseCustomsUnit)} / ${escapeHtml(__("unit"))}<br><strong>${__("Delta Tax")}:</strong> (${money(customs.base_value)} − ${money(buyAmount)}) = ${money(delta)}; ${money(delta)} × ${percent(deltaRate)} = ${money(deltaTaxAmount)}; ${money(deltaTaxAmount)} ÷ ${qty} = ${money(deltaTaxUnit)} / ${escapeHtml(__("unit"))}`;
            }
            return `${toNumber(customs.weight_kg).toFixed(3)} kg × ${money(customs.value_per_kg)} = ${money(customs.base_value)}; ${money(customs.base_value)} × ${rateLabel} = ${money(baseCustomsTotal)}; ${money(baseCustomsTotal)} ÷ ${qty} = ${money(baseCustomsUnit)} / ${escapeHtml(__("unit"))}<br><strong>${__("Delta Tax")}:</strong> (${money(customs.base_value)} − ${money(buyAmount)}) = ${money(delta)}; ${money(delta)} × ${percent(deltaRate)} = ${money(deltaTaxAmount)}; ${money(deltaTaxAmount)} ÷ ${qty} = ${money(deltaTaxUnit)} / ${escapeHtml(__("unit"))}`;
        }
        if (customs.mode === "buying_amount_fallback") {
            return `${escapeHtml(__("Buying amount fallback"))}: ${money(customs.base_value)} × ${rateLabel} = ${money(baseCustomsTotal)}; ${money(baseCustomsTotal)} ÷ ${qty} = ${money(baseCustomsTotal / qty)} / ${escapeHtml(__("unit"))}`;
        }
        return `${toNumber(customs.weight_kg).toFixed(3)} kg × ${money(customs.value_per_kg)} = ${money(customs.base_value)}; ${money(customs.base_value)} × ${rateLabel} = ${money(baseCustomsTotal)}; ${money(baseCustomsTotal)} ÷ ${qty} = ${money(baseCustomsTotal / qty)} / ${escapeHtml(__("unit"))}`;
    }

    function benchmarkMarginText(margin) {
        return escapeHtml(__("Benchmark rule selected: {0}. Ratio = landed cost {1} ÷ benchmark {2} = {3}.", [margin.rule_label || "-", money(margin.landed_cost), money(margin.benchmark_reference), toNumber(margin.ratio).toFixed(4)]));
    }

    function fallbackMarginText(margin) {
        const warning = (Array.isArray(margin.warnings) && margin.warnings.length) ? margin.warnings[0] : __("benchmark data was not sufficient");
        return escapeHtml(__("Fallback margin used: {0}", [warning]));
    }

    function marginFormula(basis, basisAmount, target, unit) {
        if (basis === "Sale Price") return `${escapeHtml(__("Sale Price basis"))}: ${money(basisAmount)} × ${percent(target)} ÷ (1 - ${percent(target)}) = ${money(unit)}`;
        return `${escapeHtml(basis || __("Base Price"))}: ${money(basisAmount)} × ${percent(target)} = ${money(unit)}`;
    }

    function calcTable(headers, bodyRows) {
        return `<div class="pbb-component-table-wrap"><table class="pbb-component-table pbb-calc-table"><thead><tr>${headers.map((header) => `<th>${escapeHtml(header)}</th>`).join("")}</tr></thead><tbody>${bodyRows}</tbody></table></div>`;
    }

    function historyPanel(doc) {
        const rows = STATE.history || [];
        if (doc.name === "new") return `<div class="pbb-empty-cell pbb-breakdown-empty">${__("Save the builder first to start history tracking.")}</div>`;
        if (!rows.length) return `<div class="pbb-empty-cell pbb-breakdown-empty">${__("No history snapshots yet. Autosave will create snapshots after changes.")}</div>`;
        return `<div class="pbb-history-list">${rows.map((row) => `<article class="pbb-history-row"><div><strong>${escapeHtml(row.action || __("Saved"))}</strong><span>${escapeHtml(formatDateTime(row.creation))}</span><p>${escapeHtml(row.summary || "")}</p></div><button type="button" class="pbb-btn ghost" data-rollback="${escapeHtml(row.name)}">${__("Rollback")}</button></article>`).join("")}</div>`;
    }

    function itemRow(entry, columns) {
        const row = entry.row;
        const index = entry.index;
        return `<tr data-item-row="${index}">${columns.map((column) => itemBodyCell(column, row, entry)).join("")}</tr>`;
    }

    function itemCell(row) {
        const item = row.item || "";
        return `<div class="pbb-item-cell">
            <button type="button" class="pbb-item-link" data-open-item="${escapeHtml(item)}"><strong>${escapeHtml(item || "-")}</strong><small>${escapeHtml(row.item_group || "")}</small></button>
            <div class="pbb-item-popover" role="tooltip">
                <div class="pbb-item-popover-head"><strong>${escapeHtml(item || "-")}</strong><button type="button" data-open-item="${escapeHtml(item)}">${__("Open")}</button></div>
                <span class="pbb-item-popover-name">${escapeHtml(row.item_name || "")}</span>
                <dl>
                    <dt>${__("Group")}</dt><dd>${escapeHtml(row.item_group || "-")}</dd>
                    <dt>${__("Category")}</dt><dd>${escapeHtml(row.item_category || "-")}</dd>
                    <dt>${__("Material")}</dt><dd>${escapeHtml(row.material || "-")}</dd>
                    <dt>${__("Tariff")}</dt><dd>${escapeHtml(row.customs_tariff_number || "-")}</dd>
                    <dt>${__("Buying List")}</dt><dd>${escapeHtml(row.buying_list || "-")}</dd>
                </dl>
            </div>
        </div>`;
    }

    function listPriceCell(row) {
        const override = toNumber(row.override_selling_price);
        if (override > 0) {
            return `<span class="pbb-list-price is-overridden" title="${escapeHtml(__("Manual override will be published as the list price."))}"><strong>${money(override)}</strong><small>${__("Manual override")}</small></span>`;
        }
        return `<span class="pbb-list-price"><strong>${money(row.published_price)}</strong><small>${__("Current list")}</small></span>`;
    }

    function overrideCell(row, entry) {
        const index = entry ? entry.index : 0;
        return `<div class="pbb-override-cell"><input type="number" step="0.01" min="0" value="${escapeHtml(row.override_selling_price || 0)}" data-item-field="override_selling_price"><button type="button" class="pbb-override-apply" data-apply-override="${escapeHtml(index)}" title="${escapeHtml(__("Validate manual override"))}" aria-label="${escapeHtml(__("Validate manual override"))}">&#10003;</button></div>`;
    }

    function itemTableColumns() {
        ensureItemColumnState();
        const visible = new Set(STATE.visibleItemColumns || []);
        const columns = normalizeItemColumnKeys(STATE.visibleItemColumns || defaultItemColumnKeys())
            .map((key) => ITEM_TABLE_COLUMNS.find((column) => column.key === key))
            .filter((column) => column && (column.locked || visible.has(column.key)));
        return columns.length ? columns : defaultItemColumnKeys().map((key) => ITEM_TABLE_COLUMNS.find((column) => column.key === key)).filter(Boolean);
    }

    function itemHeaderCell(column) {
        const sort = STATE.itemSort || {};
        const isSorted = sort.key === column.key;
        const direction = isSorted && sort.direction === "desc" ? "desc" : "asc";
        const sortText = isSorted ? (direction === "desc" ? "down" : "up") : "";
        if (column.noSort) return `<th data-column="${escapeHtml(column.key)}" class="${column.align === "center" ? "pbb-align-center" : ""}" style="${itemColumnStyle(column)}"><span class="pbb-sort-btn static"><span>${escapeHtml(column.label())}</span></span><span class="pbb-column-width-badge">${escapeHtml(String(itemColumnWidth(column)))}px</span><span class="pbb-column-resizer" data-resize-column="${escapeHtml(column.key)}" title="${escapeHtml(__("Drag to resize. Double-click to reset."))}" aria-hidden="true"></span></th>`;
        return `<th data-column="${escapeHtml(column.key)}" class="${column.align === "center" ? "pbb-align-center" : ""}" style="${itemColumnStyle(column)}" aria-sort="${isSorted ? (direction === "desc" ? "descending" : "ascending") : "none"}"><button type="button" class="pbb-sort-btn" data-sort-column="${escapeHtml(column.key)}"><span>${escapeHtml(column.label())}</span><em>${escapeHtml(sortText)}</em></button><span class="pbb-column-width-badge">${escapeHtml(String(itemColumnWidth(column)))}px</span><span class="pbb-column-resizer" data-resize-column="${escapeHtml(column.key)}" title="${escapeHtml(__("Drag to resize. Double-click to reset."))}" aria-hidden="true"></span></th>`;
    }

    function itemFilterCell(column) {
        const value = (STATE.itemColumnFilters || {})[column.key] || "";
        if (column.noFilter || column.key === "selected") return `<th data-column="${escapeHtml(column.key)}" class="pbb-column-filter-cell pbb-align-center" style="${itemColumnStyle(column)}"><span class="pbb-filter-lock">${__("Filter")}</span></th>`;
        if (["item_group", "item_category"].includes(column.key)) {
            const options = builderItemFilterOptions(column.key);
            return `<th data-column="${escapeHtml(column.key)}" class="pbb-column-filter-cell" style="${itemColumnStyle(column)}"><select data-column-filter="${escapeHtml(column.key)}" aria-label="${escapeHtml(__("Filter {0}", [column.label()]))}"><option value="">${escapeHtml(__("All"))}</option>${options.map((option) => `<option value="${escapeHtml(option)}" ${option === value ? "selected" : ""}>${escapeHtml(option)}</option>`).join("")}</select></th>`;
        }
        return `<th data-column="${escapeHtml(column.key)}" class="pbb-column-filter-cell" style="${itemColumnStyle(column)}"><input type="search" data-column-filter="${escapeHtml(column.key)}" value="${escapeHtml(value)}" placeholder="${escapeHtml(itemFilterPlaceholder(column))}" aria-label="${escapeHtml(__("Filter {0}", [column.label()]))}"></th>`;
    }

    function builderItemFilterOptions(key) {
        const selectedGroup = String((STATE.itemColumnFilters || {}).item_group || "").trim();
        const values = (STATE.doc?.builder_items || [])
            .filter((row) => key !== "item_category" || !selectedGroup || row.item_group === selectedGroup)
            .map((row) => row[key]);
        return uniqueBuilderItemOptions(values);
    }

    function uniqueBuilderItemOptions(values) {
        const out = [];
        const seen = new Set();
        (values || []).forEach((value) => {
            const clean = String(value || "").trim();
            if (!clean || seen.has(clean)) return;
            seen.add(clean);
            out.push(clean);
        });
        return out.sort((a, b) => a.localeCompare(b));
    }

    function itemFilterPlaceholder(column) {
        return itemColumnSupportsNumericFilter(column) ? __("Filter e.g. >0") : __("Filter");
    }

    function itemBodyCell(column, row, entry) {
        const classes = [column.align === "center" ? "pbb-align-center" : "", column.wrap ? "pbb-wrap" : "", column.strong ? "pbb-money-strong" : ""].filter(Boolean).join(" ");
        return `<td data-column="${escapeHtml(column.key)}" class="${classes}" style="${itemColumnStyle(column)}">${column.render(row, entry)}</td>`;
    }

    function itemColumnStyle(column) {
        const width = itemColumnWidth(column);
        const minWidth = column.minWidth || 72;
        return `width:${width}px;min-width:${minWidth}px`;
    }

    function itemColumnWidth(column) {
        ensureItemColumnState();
        return clampNumber(STATE.itemColumnWidths[column.key] || column.width || 130, column.minWidth || 72, 420);
    }

    function itemTableMinWidth(columns) {
        return Math.max(720, (columns || []).reduce((total, column) => total + itemColumnWidth(column), 0));
    }

    function columnConfigurator() {
        ensureItemColumnState();
        const visible = new Set(STATE.visibleItemColumns || []);
        const visibleCount = itemTableColumns().length;
        const totalCount = ITEM_TABLE_COLUMNS.length;
        const selectedOrder = itemTableColumns().map((column) => {
            const locked = column.locked;
            return `<div class="pbb-column-order-row ${locked ? "locked" : ""}" data-column-order-row="${escapeHtml(column.key)}"><span>${escapeHtml(column.label())}</span><small>${escapeHtml(itemColumnCategoryLabel(column))} · ${escapeHtml(__("{0}px", [itemColumnWidth(column)]))}</small><button type="button" class="pbb-icon-btn" data-column-reset-width="${escapeHtml(column.key)}">${__("Width")}</button><button type="button" class="pbb-icon-btn" data-column-up="${escapeHtml(column.key)}" ${locked ? "disabled" : ""}>${__("Up")}</button><button type="button" class="pbb-icon-btn" data-column-down="${escapeHtml(column.key)}" ${locked ? "disabled" : ""}>${__("Down")}</button></div>`;
        }).join("");
        const groupedColumns = ITEM_COLUMN_CATEGORIES.map(([category, label]) => {
            const groupColumns = ITEM_TABLE_COLUMNS.filter((column) => itemColumnCategory(column) === category);
            if (!groupColumns.length) return "";
            return `<div class="pbb-column-group"><h3>${escapeHtml(label())}</h3><div class="pbb-column-list">${groupColumns.map((column) => {
                const checked = column.locked || visible.has(column.key);
                return `<label class="${column.locked ? "locked" : ""}"><input type="checkbox" data-item-column="${escapeHtml(column.key)}" ${checked ? "checked" : ""} ${column.locked ? "disabled" : ""}><span>${escapeHtml(column.label())}</span>${column.locked ? `<small>${__("Required")}</small>` : ""}</label>`;
            }).join("")}</div></div>`;
        }).join("");
        return `<details class="pbb-column-config" data-column-config ${STATE.columnConfiguratorOpen ? "open" : ""}>
            <summary><span>${__("Columns")}</span><em>${escapeHtml(__("{0} of {1} visible", [visibleCount, totalCount]))}</em></summary>
            <div class="pbb-column-config-panel">
                <div class="pbb-column-config-head"><strong>${__("Choose table columns")}</strong><button type="button" class="pbb-btn ghost" data-reset-columns>${__("Reset")}</button></div>
                <div class="pbb-column-config-grid"><div><h3>${__("Selected order")}</h3><div class="pbb-column-order-list">${selectedOrder}</div></div><div>${groupedColumns}</div></div>
            </div>
        </details>`;
    }

    function ensureItemColumnState() {
        if (STATE.visibleItemColumns && STATE.visibleItemColumns.length) return;
        const config = readItemColumnConfig();
        STATE.visibleItemColumns = config.columns;
        STATE.itemColumnWidths = config.widths || {};
        STATE.itemColumnFilters = config.filters || {};
        STATE.itemSort = config.sort || { key: "", direction: "asc" };
    }

    function readItemColumnConfig() {
        const validKeys = new Set(ITEM_TABLE_COLUMNS.map((column) => column.key));
        let stored = null;
        try {
            stored = JSON.parse(window.localStorage.getItem(ITEM_COLUMN_STORAGE_KEY) || "null");
        } catch (error) {
            stored = null;
        }
        if (Array.isArray(stored)) {
            return { columns: normalizeItemColumnKeys(stored.filter((key) => validKeys.has(key))), widths: {}, filters: {}, sort: { key: "", direction: "asc" } };
        }
        if (stored && typeof stored === "object") {
            return {
                columns: normalizeItemColumnKeys(((stored.columns || []).length ? stored.columns : defaultItemColumnKeys()).filter((key) => validKeys.has(key))),
                widths: normalizeItemColumnWidths(stored.widths || {}),
                filters: normalizeItemColumnFilters(stored.filters || {}),
                sort: normalizeItemSort(stored.sort || {}),
            };
        }
        try {
            const legacy = JSON.parse(window.localStorage.getItem(ITEM_LEGACY_COLUMN_STORAGE_KEY) || "[]");
            if (Array.isArray(legacy) && legacy.length) {
                return { columns: normalizeItemColumnKeys(legacy.filter((key) => validKeys.has(key))), widths: {}, filters: {}, sort: { key: "", direction: "asc" } };
            }
        } catch (error) {
            // Ignore old malformed local preferences.
        }
        return { columns: normalizeItemColumnKeys(defaultItemColumnKeys()), widths: {}, filters: {}, sort: { key: "", direction: "asc" } };
    }

    function saveItemColumnConfig() {
        try {
            window.localStorage.setItem(ITEM_COLUMN_STORAGE_KEY, JSON.stringify({
                columns: normalizeItemColumnKeys(STATE.visibleItemColumns || []),
                widths: normalizeItemColumnWidths(STATE.itemColumnWidths || {}),
                filters: normalizeItemColumnFilters(STATE.itemColumnFilters || {}),
                sort: normalizeItemSort(STATE.itemSort || {}),
            }));
        } catch (error) {
            // Browser storage can be unavailable in private windows; keep the in-memory preference.
        }
    }

    function normalizeItemColumnKeys(keys) {
        const out = [];
        const lockedKeys = ITEM_TABLE_COLUMNS.filter((column) => column.locked).map((column) => column.key);
        lockedKeys.forEach((key) => out.push(key));
        (keys || []).forEach((key) => {
            const column = ITEM_TABLE_COLUMNS.find((candidate) => candidate.key === key);
            if (column && !column.locked && !out.includes(key)) out.push(key);
        });
        return out;
    }

    function normalizeItemColumnWidths(widths) {
        const out = {};
        (ITEM_TABLE_COLUMNS || []).forEach((column) => {
            const width = clampNumber((widths || {})[column.key], 68, 720);
            if (width) out[column.key] = width;
        });
        return out;
    }

    function normalizeItemColumnFilters(filters) {
        const out = {};
        (ITEM_TABLE_COLUMNS || []).forEach((column) => {
            const value = String((filters || {})[column.key] || "").trim();
            if (value && column.key !== "selected") out[column.key] = value;
        });
        return out;
    }

    function normalizeItemSort(sort) {
        const key = (sort || {}).key || "";
        if (!ITEM_TABLE_COLUMNS.some((column) => column.key === key)) return { key: "", direction: "asc" };
        return { key, direction: (sort || {}).direction === "desc" ? "desc" : "asc" };
    }

    function defaultItemColumnKeys() {
        return ITEM_TABLE_COLUMNS.filter((column) => column.locked || column.defaultVisible).map((column) => column.key);
    }

    function setItemColumnVisible(key, visible) {
        const column = ITEM_TABLE_COLUMNS.find((candidate) => candidate.key === key);
        if (!column || column.locked) return;
        const keys = normalizeItemColumnKeys(STATE.visibleItemColumns || defaultItemColumnKeys()).filter((candidate) => candidate !== key);
        if (visible) keys.push(key);
        STATE.visibleItemColumns = normalizeItemColumnKeys(keys);
        saveItemColumnConfig();
    }

    function resetItemColumns() {
        STATE.visibleItemColumns = defaultItemColumnKeys();
        STATE.itemColumnWidths = {};
        STATE.itemColumnFilters = {};
        STATE.itemSort = { key: "", direction: "asc" };
        saveItemColumnConfig();
    }

    function moveItemColumn(key, delta) {
        const column = ITEM_TABLE_COLUMNS.find((candidate) => candidate.key === key);
        if (!column || column.locked) return;
        const keys = normalizeItemColumnKeys(STATE.visibleItemColumns || defaultItemColumnKeys());
        const lockedCount = ITEM_TABLE_COLUMNS.filter((candidate) => candidate.locked).length;
        const index = keys.indexOf(key);
        const nextIndex = Math.max(lockedCount, Math.min(keys.length - 1, index + delta));
        if (index < lockedCount || nextIndex === index) return;
        keys.splice(index, 1);
        keys.splice(nextIndex, 0, key);
        STATE.visibleItemColumns = normalizeItemColumnKeys(keys);
        saveItemColumnConfig();
    }

    function toggleItemSort(key) {
        if (!ITEM_TABLE_COLUMNS.some((column) => column.key === key)) return;
        const current = STATE.itemSort || {};
        if (current.key !== key) STATE.itemSort = { key, direction: "asc" };
        else if (current.direction === "asc") STATE.itemSort = { key, direction: "desc" };
        else STATE.itemSort = { key: "", direction: "asc" };
        saveItemColumnConfig();
    }

    function bindItemColumnResize(page) {
        page.main.find("[data-resize-column]").on("dblclick", function (event) {
            event.preventDefault();
            event.stopPropagation();
            resetItemColumnWidth(page, $(this).attr("data-resize-column"));
        });
        page.main.find("[data-resize-column]").on("pointerdown", function (event) {
            event.preventDefault();
            event.stopPropagation();
            const key = $(this).attr("data-resize-column");
            const column = ITEM_TABLE_COLUMNS.find((candidate) => candidate.key === key);
            if (!column) return;
            const startX = event.clientX;
            const startWidth = itemColumnWidth(column);
            document.body.classList.add("pbb-column-resizing");
            $(document).off("pointermove.pbbResize pointerup.pbbResize pointercancel.pbbResize");
            $(document).on("pointermove.pbbResize", (moveEvent) => {
                const width = clampNumber(startWidth + moveEvent.clientX - startX, column.minWidth || 68, 720) || column.width || 130;
                STATE.itemColumnWidths[key] = width;
                applyItemColumnWidth(page, key, width);
            });
            $(document).on("pointerup.pbbResize pointercancel.pbbResize", () => {
                $(document).off("pointermove.pbbResize pointerup.pbbResize pointercancel.pbbResize");
                document.body.classList.remove("pbb-column-resizing");
                saveItemColumnConfig();
            });
        });
    }

    function applyItemColumnWidth(page, key, width) {
        const column = ITEM_TABLE_COLUMNS.find((candidate) => candidate.key === key) || {};
        page.main.find(`[data-column="${cssEscape(key)}"]`).css({ width: `${width}px`, minWidth: `${column.minWidth || 72}px` });
        const table = page.main.find(".pbb-items-table");
        if (table.length) table.css("min-width", `${itemTableMinWidth(itemTableColumns())}px`);
    }

    function resetItemColumnWidth(page, key) {
        const column = ITEM_TABLE_COLUMNS.find((candidate) => candidate.key === key);
        if (!column) return;
        delete STATE.itemColumnWidths[key];
        const width = itemColumnWidth(column);
        applyItemColumnWidth(page, key, width);
        saveItemColumnConfig();
    }

    function itemColumnCategory(column) {
        const key = column.key;
        if (["selected", "published_price", "status", "status_note"].includes(key)) return "publish";
        if (["buying_list", "origin", "pricing_scenario"].includes(key)) return "source";
        if (["base_buy_price", "expenses", "cost_total", "projected_price", "sell_price", "override_selling_price"].includes(key)) return "cost";
        if (["customs_tariff_number", "customs_amount", "customs_base_value", "customs_value_per_kg", "customs_weight_kg", "customs_line_weight_kg", "customs_unit_weight_kg", "customs_package_weight_kg", "packaging_units_per_package", "packaging_package_count", "packaging_profile_source", "customs_basis", "customs_policy", "customs_value_delta", "customs_value_delta_tax_rate", "customs_value_delta_tax_amount"].includes(key)) return "customs";
        if (["margin_amount", "total_margin_amount", "avg_benchmark", "final_margin_pct", "total_margin_pct", "target_margin_percent", "margin_basis", "benchmark_is_fallback", "benchmark_rule_label", "benchmark_rule_max_discount_percent", "fallback_max_discount_percent", "policy_max_discount_percent", "benchmark_policy"].includes(key)) return "margin";
        return "article";
    }

    function itemColumnCategoryLabel(column) {
        const category = itemColumnCategory(column);
        const match = ITEM_COLUMN_CATEGORIES.find(([key]) => key === category);
        return match ? match[1]() : __("Article");
    }

    function readSourcingRulesOpen() {
        try {
            const stored = window.localStorage.getItem(SOURCING_RULE_STORAGE_KEY);
            return stored === null ? true : stored !== "0";
        } catch (error) {
            return true;
        }
    }

    function saveSourcingRulesOpen(open) {
        try {
            window.localStorage.setItem(SOURCING_RULE_STORAGE_KEY, open ? "1" : "0");
        } catch (error) {
            // Local preference only.
        }
    }

    function readAutoRecalculate() {
        try {
            return window.localStorage.getItem(AUTO_RECALCULATE_STORAGE_KEY) === "1";
        } catch (error) {
            return false;
        }
    }

    function saveAutoRecalculate(enabled) {
        try {
            window.localStorage.setItem(AUTO_RECALCULATE_STORAGE_KEY, enabled ? "1" : "0");
        } catch (error) {
            // Local preference only.
        }
    }

    function summaryPanel(doc) {
        const cards = [
            [__("Items"), doc.total_items],
            [__("Ready"), doc.ready_items],
            [__("Changed"), doc.changed_items],
            [__("New"), doc.new_items],
            [__("Missing"), doc.missing_items],
        ];
        return `<div class="pbb-summary-compact"><strong>${__("Summary")}</strong>${cards.map(([label, value]) => `<span><em>${escapeHtml(label)}</em>${escapeHtml(value || 0)}</span>`).join("")}</div>`;
    }

    function warningsPanel(doc) {
        const rows = String(doc.warnings_html || "").split("\n").map((row) => row.trim()).filter(Boolean);
        if (!rows.length) return `<h2>${__("Warnings")}</h2><div class="pbb-warning empty">${__("No warnings. The builder is ready to calculate or publish.")}</div>`;
        return `<details class="pbb-warning-details"><summary><h2>${__("Warnings")}</h2><span>${escapeHtml(__("{0} warning(s)", [rows.length]))}</span></summary><div class="pbb-warning"><ul>${rows.map((row) => `<li>${escapeHtml(row)}</li>`).join("")}</ul></div></details>`;
    }

    function bind(page) {
        page.main.find("[data-back]").on("click", () => frappe.set_route("pricing-builder-manager"));
        page.main.find("[data-native]").on("click", () => STATE.doc.name !== "new" && frappe.set_route("Form", "Pricing Builder", STATE.doc.name));
        page.main.find("[data-save]").on("click", () => save(page, { freeze: true }));
        page.main.find("[data-calculate]").on("click", () => calculate(page));
        page.main.find("[data-preview-publish]").on("click", () => previewPublish(page));
        page.main.find("[data-auto-recalculate]").on("change", function () {
            STATE.autoRecalculate = $(this).is(":checked");
            saveAutoRecalculate(STATE.autoRecalculate);
            STATE.autoRecalculateStatus = STATE.autoRecalculate ? __("Auto recalculate enabled while this builder is open") : __("Auto recalculate disabled") ;
            if (STATE.autoRecalculate) startOpenRefreshFlow(page, STATE.doc ? STATE.doc.name : "new");
            else stopAutoRecalculateLoop();
            render(page, { preserveScroll: true });
        });
        page.main.find("[data-tab]").on("click", function () { STATE.activeTab = $(this).attr("data-tab") || "items"; render(page); });
        page.main.find("[data-toggle-rules]").on("click", function () {
            syncVisibleInputs(page);
            STATE.sourcingRulesOpen = !STATE.sourcingRulesOpen;
            saveSourcingRulesOpen(STATE.sourcingRulesOpen);
            render(page);
        });
        page.main.find("[data-column-config]").on("toggle", function () { STATE.columnConfiguratorOpen = this.open; });
        page.main.find("[data-sort-column]").on("click", function () {
            toggleItemSort($(this).attr("data-sort-column"));
            render(page);
        });
        page.main.find("[data-item-column]").on("change", function () {
            setItemColumnVisible($(this).attr("data-item-column"), $(this).is(":checked"));
            STATE.columnConfiguratorOpen = true;
            render(page);
        });
        page.main.find("[data-column-up]").on("click", function () {
            moveItemColumn($(this).attr("data-column-up"), -1);
            STATE.columnConfiguratorOpen = true;
            render(page);
        });
        page.main.find("[data-column-down]").on("click", function () {
            moveItemColumn($(this).attr("data-column-down"), 1);
            STATE.columnConfiguratorOpen = true;
            render(page);
        });
        page.main.find("[data-column-reset-width]").on("click", function () {
            resetItemColumnWidth(page, $(this).attr("data-column-reset-width"));
            STATE.columnConfiguratorOpen = true;
            render(page);
        });
        page.main.find("[data-reset-columns]").on("click", function () {
            resetItemColumns();
            STATE.columnConfiguratorOpen = true;
            render(page);
        });
        bindItemColumnResize(page);
        page.main.find("[data-open-item]").on("click", function (event) {
            event.preventDefault();
            event.stopPropagation();
            const item = String($(this).attr("data-open-item") || "").trim();
            if (item) frappe.set_route("Form", "Item", item);
        });
        page.main.find("[data-breakdown-search]").on("change", function () { selectBreakdownBySearchValue(page, $(this).val()); });
        page.main.find("[data-breakdown-search]").on("keydown", function (event) {
            if (event.key === "Enter") selectBreakdownBySearchValue(page, $(this).val());
        });
        page.main.find("[data-rollback]").on("click", function () { rollbackHistory(page, $(this).attr("data-rollback")); });
        page.main.find("[data-price-list-mode]").on("change", function () {
            STATE.priceListMode = $(this).val() || "existing";
            if (STATE.priceListMode === "existing" && !(STATE.refs.selling_price_lists || []).includes(STATE.doc.selling_price_list_name)) {
                STATE.doc.selling_price_list_name = "";
                scheduleAutosave(page);
            }
            if (STATE.priceListMode === "new" && !STATE.doc.target_currency) {
                STATE.doc.target_currency = defaultTargetCurrency();
            }
            render(page);
        });
        page.main.find("[data-parent-field]").on("input change", function () {
            const fieldname = $(this).attr("data-parent-field");
            STATE.doc[fieldname] = numericParentField(fieldname) ? toNumber($(this).val()) : String($(this).val() || "").trim();
            if (fieldname === "selling_price_list_name" && STATE.priceListMode === "existing") {
                STATE.doc.target_currency = listCurrency(STATE.doc.selling_price_list_name, "selling") || STATE.doc.target_currency || defaultTargetCurrency();
            }
            scheduleAutosave(page);
        });
        page.main.find("[data-add-rule]").on("click", () => {
            syncVisibleInputs(page);
            STATE.doc.sourcing_rules.push(blankSourcingRule());
            STATE.autosaveStatus = __("Fill the Sourcing Rule to save it");
            render(page);
        });
        page.main.find("[data-delete-rule]").on("click", function () {
            syncVisibleInputs(page);
            STATE.doc.sourcing_rules.splice(Number($(this).attr("data-delete-rule")), 1);
            render(page);
            scheduleAutosave(page);
        });
        page.main.find("[data-rule-row]").on("input change", "input", function () {
            const row = STATE.doc.sourcing_rules[Number($(this).closest("[data-rule-row]").attr("data-rule-row"))];
            if (!row) return;
            const fieldname = $(this).attr("data-rule-field");
            row[fieldname] = fieldname === "is_active" ? ($(this).is(":checked") ? 1 : 0) : String($(this).val() || "").trim();
            scheduleAutosave(page);
        });
        page.main.find("[data-item-row]").on("input change", "input", function () {
            const row = STATE.doc.builder_items[Number($(this).closest("[data-item-row]").attr("data-item-row"))];
            const fieldname = $(this).attr("data-item-field");
            row[fieldname] = fieldname === "selected" ? ($(this).is(":checked") ? 1 : 0) : toNumber($(this).val());
            scheduleAutosave(page);
        });
        page.main.find("[data-apply-override]").on("click", function () {
            applyOverride(page, Number($(this).attr("data-apply-override")));
        });
        page.main.find("[data-select-all]").on("click", () => { filteredItems(STATE.doc.builder_items || []).forEach((entry) => { entry.row.selected = 1; }); render(page); scheduleAutosave(page); });
        page.main.find("[data-clear-selected]").on("click", () => { filteredItems(STATE.doc.builder_items || []).forEach((entry) => { entry.row.selected = 0; }); render(page); scheduleAutosave(page); });
        page.main.find("[data-filter]").on("input", function () { STATE.filter = String($(this).val() || "").trim(); render(page, { focusFilter: true, preserveScroll: true }); });
        page.main.find("[data-status-filter]").on("change", function () { STATE.status = String($(this).val() || "").trim(); render(page); });
        page.main.find("[data-column-filter]").on("input change", function () {
            setItemColumnFilter($(this).attr("data-column-filter"), $(this).val());
            render(page, { focusColumnFilter: $(this).attr("data-column-filter"), preserveScroll: true });
        });
        page.main.find("[data-clear-column-filters]").on("click", function () {
            STATE.itemColumnFilters = {};
            saveItemColumnConfig();
            render(page, { resetItemsTop: true });
        });
    }

    async function rollbackHistory(page, historyName) {
        if (!historyName || !STATE.doc || STATE.doc.name === "new") return;
        frappe.confirm(__("Rollback this builder to the selected history point? Current changes will be saved as a rollback snapshot."), async () => {
            const res = await frappe.call({
                method: "orderlift.orderlift_sales.page.pricing_builder_builder.pricing_builder_builder.rollback_builder_history",
                args: { name: STATE.doc.name, history_name: historyName },
                freeze: true,
                freeze_message: __("Rolling back builder..."),
            });
            STATE.doc = normalizeDoc((res.message || {}).doc || {});
            STATE.history = (res.message || {}).history || [];
            STATE.priceListMode = resolvePriceListMode(STATE.doc, STATE.refs);
            STATE.autosaveStatus = __("Rolled back");
            ensureBreakdownSelection();
            render(page);
        });
    }

    function scheduleAutosave(page) {
        if (!STATE.doc || STATE.loading) return;
        clearTimeout(autosaveTimer);
        STATE.autosaveStatus = __("Unsaved changes");
        autosaveTimer = setTimeout(() => {
            save(page, { autosave: true, render: false, historyLabel: __("Autosaved") }).then(() => {
                const status = page.main.find(".pbb-autosave-status");
                if (status.length) status.text(STATE.autosaveStatus || __("Autosaved"));
            });
        }, 900);
    }

    function applyOverride(page, index) {
        const row = ((STATE.doc || {}).builder_items || [])[index];
        if (!row) return;
        const input = page.main.find(`[data-item-row="${index}"] [data-item-field="override_selling_price"]`).get(0);
        const rawValue = input ? input.value : row.override_selling_price;
        const value = toNumber(rawValue);
        if (value < 0) {
            frappe.msgprint({ title: __("Invalid Override"), message: __("Manual override cannot be negative."), indicator: "red" });
            return;
        }
        row.override_selling_price = value;
        STATE.autosaveStatus = value > 0 ? __("Manual override validated") : __("Manual override cleared");
        render(page, { preserveScroll: true });
        scheduleAutosave(page);
    }

    function autosaveBlockReason(doc) {
        if (!String(doc.builder_name || "").trim()) {
            return __("Enter Builder Name to enable autosave");
        }
        if (!String(doc.selling_price_list_name || "").trim()) {
            return __("Select or enter Selling Price List to enable autosave");
        }
        if (!hasSourcingRule(doc)) {
            return __("Add a Sourcing Rule to enable autosave");
        }
        return "";
    }

    function hasSourcingRule(doc) {
        return (doc.sourcing_rules || []).some((row) => {
            return SOURCING_RULE_FIELDS.some((fieldname) => String(row[fieldname] || "").trim());
        });
    }

    function syncVisibleInputs(page) {
        if (!STATE.doc || !page || !page.main) return;
        page.main.find("[data-parent-field]").each(function () {
            const fieldname = $(this).attr("data-parent-field");
            STATE.doc[fieldname] = numericParentField(fieldname) ? toNumber($(this).val()) : String($(this).val() || "").trim();
        });
        page.main.find("[data-rule-row]").each(function () {
            const row = STATE.doc.sourcing_rules[Number($(this).attr("data-rule-row"))];
            if (!row) return;
            $(this).find("[data-rule-field]").each(function () {
                const fieldname = $(this).attr("data-rule-field");
                row[fieldname] = fieldname === "is_active" ? ($(this).is(":checked") ? 1 : 0) : String($(this).val() || "").trim();
            });
        });
        page.main.find("[data-item-row]").each(function () {
            const row = STATE.doc.builder_items[Number($(this).attr("data-item-row"))];
            if (!row) return;
            $(this).find("[data-item-field]").each(function () {
                const fieldname = $(this).attr("data-item-field");
                row[fieldname] = fieldname === "selected" ? ($(this).is(":checked") ? 1 : 0) : toNumber($(this).val());
            });
        });
    }

    function blankSourcingRule() {
        return { is_active: 1, buying_price_list: "", pricing_scenario: "", customs_policy: "", benchmark_policy: "" };
    }

    function cloneSourcingRule(row) {
        return Object.assign(blankSourcingRule(), row || {});
    }

    function isBlankSourcingRule(row) {
        return !SOURCING_RULE_FIELDS.some((fieldname) => String((row || {})[fieldname] || "").trim());
    }

    function selectBreakdownBySearchValue(page, value) {
        const search = String(value || "").trim().toLowerCase();
        if (!search) return;
        const rows = (STATE.doc || {}).builder_items || [];
        const match = rows.map((row, index) => ({ row, index, key: builderItemKey(row, index), label: [row.item, row.item_name].filter(Boolean).join(" - ") })).find((entry) => {
            const label = String(entry.label || "").toLowerCase();
            return label === search || String(entry.row.item || "").toLowerCase() === search;
        }) || rows.map((row, index) => ({ row, index, key: builderItemKey(row, index), label: [row.item, row.item_name].filter(Boolean).join(" - ") })).find((entry) => String(entry.label || "").toLowerCase().includes(search));
        if (!match) return;
        STATE.selectedBreakdownKey = match.key;
        render(page);
    }

    function normalizeDoc(doc) {
        const out = Object.assign({ name: "new", builder_name: "", selling_price_list_name: "", target_currency: defaultTargetCurrency(), item_group: "", default_qty: 1, max_items: 0, exchange_rate_summary: {}, sourcing_rules: [], builder_items: [] }, doc || {});
        if (!out.target_currency) out.target_currency = defaultTargetCurrency();
        out.sourcing_rules = (out.sourcing_rules || []).map(cloneSourcingRule);
        out.builder_items = (out.builder_items || []).map((row) => {
            const clean = Object.assign({ selected: 0 }, row || {});
            NUMERIC_FIELDS.forEach((field) => { clean[field] = toNumber(clean[field]); });
            clean.selected = toNumber(clean.selected) ? 1 : 0;
            return clean;
        });
        return out;
    }

    function getScrollState(page) {
        const itemScroller = page.main.find(".pbb-items-scroll").get(0);
        return {
            windowTop: window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop || 0,
            itemsTop: itemScroller ? itemScroller.scrollTop : 0,
            itemsLeft: itemScroller ? itemScroller.scrollLeft : 0,
            ancestors: getAncestorScrollState(page),
        };
    }

    function getAncestorScrollState(page) {
        const states = [];
        const main = page && page.main ? page.main.get(0) : null;
        let node = main ? main.parentElement : null;
        while (node && node !== document.body && node !== document.documentElement) {
            if (node.scrollHeight > node.clientHeight || node.scrollWidth > node.clientWidth) {
                states.push({ el: node, top: node.scrollTop || 0, left: node.scrollLeft || 0 });
            }
            node = node.parentElement;
        }
        return states;
    }

    function restoreScrollState(page, state, options) {
        options = options || {};
        const restorePositions = () => {
            ((state || {}).ancestors || []).forEach((entry) => {
                if (!entry || !entry.el) return;
                entry.el.scrollTop = entry.top || 0;
                entry.el.scrollLeft = entry.left || 0;
            });
            window.scrollTo(0, (state || {}).windowTop || 0);
            const itemScroller = page.main.find(".pbb-items-scroll").get(0);
            if (itemScroller) {
                itemScroller.scrollTop = options.resetItemsTop ? 0 : ((state || {}).itemsTop || 0);
                itemScroller.scrollLeft = (state || {}).itemsLeft || 0;
            }
        };
        requestAnimationFrame(() => {
            restorePositions();
            if (options.focusFilter) focusItemsSearch(page);
            if (options.focusColumnFilter) focusColumnFilter(page, options.focusColumnFilter);
            if (options.preserveScroll) requestAnimationFrame(restorePositions);
        });
    }

    function focusItemsSearch(page) {
        requestAnimationFrame(() => {
            const input = page.main.find("[data-filter]").get(0);
            if (!input) return;
            input.focus({ preventScroll: true });
            const length = input.value.length;
            input.setSelectionRange(length, length);
        });
    }

    function focusColumnFilter(page, key) {
        requestAnimationFrame(() => {
            const input = page.main.find(`[data-column-filter="${cssEscape(key)}"]`).get(0);
            if (!input) return;
            input.focus({ preventScroll: true });
            const length = input.value.length;
            input.setSelectionRange(length, length);
        });
    }

    function filteredItems(rows) {
        const search = STATE.filter.toLowerCase();
        const status = STATE.status.toLowerCase();
        const columnFilters = activeItemColumnFilters();
        const filtered = rows.map((row, index) => ({ row, index })).filter((entry) => {
            const row = entry.row;
            const haystack = [
                row.item,
                row.item_name,
                row.item_group,
                row.item_category,
                row.material,
                row.customs_tariff_number,
                row.origin,
                row.buying_list,
                displayStatus(row),
                row.status_note,
                row.pricing_scenario,
                row.customs_policy,
                row.benchmark_policy,
                row.benchmark_rule_label,
                row.packaging_profile_source,
                row.customs_basis,
            ].filter(Boolean).join(" ").toLowerCase();
            return (!search || haystack.includes(search)) && (!status || String(displayStatus(row) || "").toLowerCase() === status) && rowMatchesColumnFilters(row, columnFilters);
        });
        return sortItemEntries(filtered).map((entry, visibleIndex) => Object.assign({}, entry, { visibleIndex }));
    }

    function setItemColumnFilter(key, value) {
        if (!ITEM_TABLE_COLUMNS.some((column) => column.key === key)) return;
        STATE.itemColumnFilters = Object.assign({}, STATE.itemColumnFilters || {});
        const text = String(value || "").trim();
        if (text) STATE.itemColumnFilters[key] = text;
        else delete STATE.itemColumnFilters[key];
        if (key === "item_group") pruneBuilderItemCategoryFilter();
        saveItemColumnConfig();
    }

    function pruneBuilderItemCategoryFilter() {
        const category = String((STATE.itemColumnFilters || {}).item_category || "").trim();
        if (!category) return;
        if (!builderItemFilterOptions("item_category").includes(category)) delete STATE.itemColumnFilters.item_category;
    }

    function hasItemColumnFilters() {
        return Object.keys(activeItemColumnFilters()).length > 0;
    }

    function activeItemColumnFilters() {
        pruneBuilderItemCategoryFilter();
        return normalizeItemColumnFilters(STATE.itemColumnFilters || {});
    }

    function rowMatchesColumnFilters(row, filters) {
        for (const [key, value] of Object.entries(filters || {})) {
            const column = ITEM_TABLE_COLUMNS.find((candidate) => candidate.key === key);
            if (!column) continue;
            if (itemColumnSupportsNumericFilter(column) && numericFilterHasOperator(value)) {
                if (!matchesNumericColumnFilter(itemFilterValue(column, row), value)) return false;
                continue;
            }
            const actual = String(itemFilterValue(column, row)).toLowerCase();
            if (["item_group", "item_category"].includes(key)) {
                if (actual !== String(value || "").toLowerCase()) return false;
                continue;
            }
            if (!actual.includes(String(value || "").toLowerCase())) return false;
        }
        return true;
    }

    function itemColumnSupportsNumericFilter(column) {
        return !!column && (NUMERIC_FIELDS.has(column.key) || ["cost_total", "sell_price"].includes(column.key));
    }

    function numericFilterHasOperator(value) {
        return /^\s*(>=|<=|>|<|=)/.test(String(value || ""));
    }

    function matchesNumericColumnFilter(actualValue, expression) {
        const parsed = parseNumericColumnFilter(expression);
        if (!parsed) return String(actualValue == null ? "" : actualValue).toLowerCase().includes(String(expression || "").toLowerCase());
        const actual = toNumber(actualValue);
        if (parsed.operator === ">") return actual > parsed.value;
        if (parsed.operator === ">=") return actual >= parsed.value;
        if (parsed.operator === "<") return actual < parsed.value;
        if (parsed.operator === "<=") return actual <= parsed.value;
        return Math.abs(actual - parsed.value) < 0.0000001;
    }

    function parseNumericColumnFilter(expression) {
        const match = String(expression || "").trim().match(/^(>=|<=|>|<|=)\s*(-?\d+(?:[.,]\d+)?)$/);
        if (!match) return null;
        const value = Number(match[2].replace(",", "."));
        if (!Number.isFinite(value)) return null;
        return { operator: match[1], value };
    }

    function itemFilterValue(column, row) {
        if (column.key === "cost_total") return costBeforeMargin(row);
        if (column.key === "sell_price") return finalSellUnit(row);
        if (column.key === "published_price") return toNumber(row.override_selling_price) > 0 ? toNumber(row.override_selling_price) : toNumber(row.published_price);
        if (column.key === "row_number") return "";
        if (NUMERIC_FIELDS.has(column.key)) return toNumber(row[column.key]);
        return row[column.key] == null ? "" : row[column.key];
    }

    function sortItemEntries(entries) {
        const sort = normalizeItemSort(STATE.itemSort || {});
        if (!sort.key) return entries;
        const column = ITEM_TABLE_COLUMNS.find((candidate) => candidate.key === sort.key);
        if (!column) return entries;
        const direction = sort.direction === "desc" ? -1 : 1;
        return entries.slice().sort((left, right) => compareItemValues(itemSortValue(column, left.row), itemSortValue(column, right.row)) * direction);
    }

    function itemSortValue(column, row) {
        if (column.key === "cost_total") return costBeforeMargin(row);
        if (column.key === "sell_price") return finalSellUnit(row);
        if (column.key === "published_price") return itemFilterValue(column, row);
        if (column.key === "row_number") return 0;
        if (NUMERIC_FIELDS.has(column.key)) return toNumber(row[column.key]);
        return String(row[column.key] == null ? "" : row[column.key]).toLowerCase();
    }

    function compareItemValues(left, right) {
        if (typeof left === "number" || typeof right === "number") return toNumber(left) - toNumber(right);
        return String(left || "").localeCompare(String(right || ""));
    }

    function statusOptions(doc) {
        return [...new Set((doc.builder_items || []).map((row) => displayStatus(row)).filter(Boolean))].sort();
    }

    function ensureBreakdownSelection() {
        const rows = (STATE.doc || {}).builder_items || [];
        if (!rows.length) {
            STATE.selectedBreakdownKey = "";
            return;
        }
        const exists = rows.some((row, index) => builderItemKey(row, index) === STATE.selectedBreakdownKey);
        if (!STATE.selectedBreakdownKey || !exists) STATE.selectedBreakdownKey = builderItemKey(rows[0], 0);
    }

    function selectedBreakdownEntry() {
        const rows = (STATE.doc || {}).builder_items || [];
        return rows.map((row, index) => ({ row, index, key: builderItemKey(row, index) })).find((entry) => entry.key === STATE.selectedBreakdownKey) || { row: rows[0] || {}, index: 0 };
    }

    function builderItemKey(row, index) {
        return `${index}:${row.item || ""}`;
    }

    function breakdownMetric(label, value, tone) {
        return `<span class="pbb-breakdown-metric ${tone || ""}"><em>${escapeHtml(label)}</em><strong>${escapeHtml(value)}</strong></span>`;
    }

    function detail(label, value) {
        return `<span><em>${escapeHtml(label)}</em><strong>${escapeHtml(value || "-")}</strong></span>`;
    }

    function customsSourceDetail(row) {
        const parts = [row.customs_policy || "-"];
        const weight = toNumber(row.customs_weight_kg);
        const units = toNumber(row.packaging_units_per_package);
        if (weight > 0) parts.push(`${weight.toFixed(3)} kg/u`);
        if (units > 0) parts.push(`${units.toFixed(2)} u/pkg`);
        return parts.join(" | ");
    }

    function field(fieldname, label, value, type, list) {
        return `<label><span>${escapeHtml(label)}</span><input data-parent-field="${escapeHtml(fieldname)}" ${list ? `list="${escapeHtml(list)}"` : ""} type="${type}" value="${escapeHtml(value == null ? "" : value)}"></label>`;
    }

    function cellInput(fieldname, value, list) {
        return `<input data-rule-field="${escapeHtml(fieldname)}" list="${escapeHtml(list)}" value="${escapeHtml(value || "")}">`;
    }

    function referenceLists() {
        const lists = [
            ["pbb-buying-lists", STATE.refs.buying_price_lists],
            ["pbb-selling-lists", (STATE.refs.selling_price_lists || []).map((value) => priceListLabel(value, "selling"))],
            ["pbb-scenarios", STATE.refs.pricing_scenarios],
            ["pbb-customs", STATE.refs.customs_policies],
            ["pbb-benchmarks", STATE.refs.benchmark_policies],
            ["pbb-item-groups", STATE.refs.item_groups],
        ];
        return lists.map(([id, values]) => `<datalist id="${id}">${(values || []).map((value) => `<option value="${escapeHtml(value)}"></option>`).join("")}</datalist>`).join("");
    }

    function resolvePriceListMode(doc, refs) {
        const target = (doc.selling_price_list_name || "").trim();
        if (!target) return "existing";
        return (refs.selling_price_lists || []).includes(target) ? "existing" : "new";
    }
    function targetCurrency(doc) {
        if (STATE.priceListMode === "existing" && doc && doc.selling_price_list_name) {
            return listCurrency(doc.selling_price_list_name, "selling") || doc.target_currency || defaultTargetCurrency();
        }
        return (doc && doc.target_currency) || defaultTargetCurrency();
    }
    function defaultTargetCurrency() {
        return STATE.refs.company_currency || (frappe.defaults && frappe.defaults.get_default && frappe.defaults.get_default("currency")) || "";
    }
    function priceListLabel(value, kind) {
        const currency = listCurrency(value, kind);
        return currency ? `${value} (${currency})` : value;
    }
    function listCurrency(value, kind) {
        const meta = kind === "buying" ? STATE.refs.buying_price_list_meta : STATE.refs.selling_price_list_meta;
        return ((meta || {})[value] || {}).currency || "";
    }
    function currencyOptions(selected) {
        const current = selected || defaultTargetCurrency();
        const currencies = Array.from(new Set([current].concat(STATE.refs.currencies || []).filter(Boolean)));
        return currencies.map((currency) => `<option value="${escapeHtml(currency)}" ${currency === current ? "selected" : ""}>${escapeHtml(currency)}</option>`).join("");
    }
    function numericParentField(fieldname) { return ["default_qty", "max_items"].includes(fieldname); }
    function toNumber(value) { const num = Number(value || 0); return Number.isFinite(num) ? num : 0; }
    function pickNumber(value, fallback) { const num = Number(value); return Number.isFinite(num) ? num : toNumber(fallback); }
    function percent(value) { return `${toNumber(value).toFixed(2)}%`; }
    function clampNumber(value, min, max) { const num = Number(value || 0); return Number.isFinite(num) && num > 0 ? Math.max(min, Math.min(max, num)) : 0; }
    function cssEscape(value) { return window.CSS && CSS.escape ? CSS.escape(String(value || "")) : String(value || "").replace(/"/g, "\\\""); }
    function costBeforeMargin(row) { return toNumber(row.base_buy_price) + toNumber(row.expenses) + toNumber(row.customs_amount); }
    function finalSellUnit(row) { return toNumber(row.override_selling_price) || toNumber(row.projected_price); }
    function money(value) { return window.orderlift?.formatCurrency ? window.orderlift.formatCurrency(value) : normalizeCurrencyText(textFromHtml(frappe.format(toNumber(value), { fieldtype: "Currency" }))); }

    function normalizeCurrencyText(value) {
        return String(value || "")
            .replace(/[\u200e\u200f\u202a-\u202e]/g, "")
            .replace(/د\.م\./g, window.orderlift?.getActiveCompanyCurrency?.() || "MAD")
            .replace(/\s+/g, " ")
            .trim();
    }
    function displayStatus(row) {
        const status = String((row || {}).status || "").trim();
        if (status !== "Missing Rule" && toNumber((row || {}).base_buy_price) <= 0) return "Missing Buy Price";
        return status || "Ready";
    }
    function textFromHtml(value) {
        const wrapper = document.createElement("div");
        wrapper.innerHTML = String(value == null ? "" : value);
        return (wrapper.textContent || wrapper.innerText || "").trim();
    }
    function formatDateTime(value) {
        if (!value) return "-";
        try {
            return frappe.datetime.prettyDate(String(value).split(".")[0]);
        } catch (error) {
            return String(value);
        }
    }
    function escapeHtml(value) { return frappe.utils.escape_html(String(value == null ? "" : value)); }
    function statusClass(status) {
        const normalized = String(status || "").toLowerCase();
        if (normalized.includes("missing")) return "bad";
        if (normalized.includes("benchmark")) return "warn";
        if (normalized.includes("ready")) return "ok";
        return "neutral";
    }
    function skeleton() { return `<div class="pbb-skeleton large"></div><div class="pbb-skeleton"></div><div class="pbb-skeleton"></div>`; }

    function injectStyles() {
        if (document.getElementById("pbb-style")) return;
        const style = document.createElement("style");
        style.id = "pbb-style";
        style.textContent = `.pbb-root{background:#f6f8fb;color:#0f172a}.pbb-shell{max-width:1540px;margin:0 auto;padding:22px;display:grid;gap:16px}.pbb-hero,.pbb-card{border:1px solid #e2e8f0;border-radius:18px;background:#fff;box-shadow:0 4px 18px rgba(15,23,42,.05)}.pbb-hero{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:20px}.pbb-hero h1{margin:4px 0;font-size:24px}.pbb-hero p{margin:0;color:#64748b}.pbb-link{border:0;background:transparent;color:#2563eb;font-weight:800;padding:0}.pbb-hero-actions,.pbb-inline-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.pbb-btn{height:34px;border:1px solid transparent;border-radius:10px;padding:0 12px;font-weight:800}.pbb-btn.primary{background:#111827;color:#fff}.pbb-btn.ghost{background:#fff;border-color:#cbd5e1;color:#334155}.pbb-btn.danger{background:#7f1d1d;color:#fff}.pbb-btn:disabled{opacity:.45}.pbb-grid{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(320px,.7fr);gap:16px}.pbb-card{padding:16px}.pbb-card h2{margin:0 0 12px;font-size:16px}.pbb-fields{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:12px}.pbb-fields label{display:grid;gap:5px;margin:0}.pbb-fields span,.pbb-summary em{font-size:11px;font-weight:900;color:#64748b;text-transform:uppercase}.pbb-fields input,.pbb-rules-table input,.pbb-items-table input,.pbb-filters input,.pbb-filters select{height:34px;border:1px solid #cbd5e1;border-radius:9px;padding:0 9px;background:#fff}.pbb-section-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin-bottom:12px}.pbb-section-head p{margin:2px 0 0;color:#64748b}.pbb-summary{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}.pbb-summary span{display:grid;gap:4px;border:1px solid #edf2f7;border-radius:12px;background:#f8fafc;padding:12px}.pbb-summary strong{font-size:20px}.pbb-table-wrap{overflow:auto;border:1px solid #e5e7eb;border-radius:13px}.pbb-items-scroll{max-height:620px}.pbb-rules-table,.pbb-items-table{width:100%;border-collapse:separate;border-spacing:0}.pbb-rules-table th,.pbb-rules-table td,.pbb-items-table th,.pbb-items-table td{border-bottom:1px solid #edf2f7;padding:9px;text-align:left;vertical-align:middle;white-space:nowrap}.pbb-rules-table th,.pbb-items-table th{position:sticky;top:0;background:#f8fafc;z-index:1;font-size:11px;text-transform:uppercase;color:#475569}.pbb-rules-table input:not([type=checkbox]){min-width:190px}.pbb-items-table small{display:block;color:#64748b}.pbb-items-table input[type=number]{width:110px}.pbb-empty-cell{text-align:center!important;color:#64748b;padding:28px!important}.pbb-filters{display:grid;grid-template-columns:minmax(260px,1fr) 220px;gap:10px;margin-bottom:10px}.pbb-pill{display:inline-flex;border-radius:999px;padding:3px 8px;font-size:11px;font-weight:900}.pbb-pill.ok{background:#dcfce7;color:#166534}.pbb-pill.warn{background:#ffedd5;color:#9a3412}.pbb-pill.bad{background:#fee2e2;color:#991b1b}.pbb-pill.neutral{background:#e2e8f0;color:#334155}.pbb-money-strong{font-weight:900;color:#111827}.pbb-icon-btn{border:0;background:#fee2e2;color:#991b1b;border-radius:8px;height:28px;padding:0 9px;font-size:12px;font-weight:800}.pbb-warning{border:1px solid #fed7aa;background:#fff7ed;color:#9a3412;border-radius:13px;padding:12px}.pbb-warning.empty{border-color:#bbf7d0;background:#f0fdf4;color:#166534}.pbb-warning ul{margin:0;padding-left:18px}.pbb-error{border:1px solid #fecaca;background:#fef2f2;color:#991b1b;border-radius:14px;padding:16px}.pbb-skeleton{height:180px;border-radius:18px;background:linear-gradient(90deg,#eef2f7,#fff,#eef2f7);background-size:220% 100%;animation:pbb-shimmer 1.2s infinite}.pbb-skeleton.large{height:110px}@keyframes pbb-shimmer{0%{background-position:120% 0}100%{background-position:-120% 0}}@media(max-width:1100px){.pbb-hero,.pbb-section-head{display:grid}.pbb-grid,.pbb-fields,.pbb-summary,.pbb-filters{grid-template-columns:1fr}.pbb-hero-actions{justify-content:flex-start}}`;
        style.textContent += `
            .pbb-root,.pbb-root *,.pbb-root *::before,.pbb-root *::after{box-sizing:border-box}.pbb-root{overflow-x:hidden}.pbb-shell,.pbb-card,.pbb-grid,.pbb-table-wrap{min-width:0;max-width:100%}.pbb-shell{width:100%;padding-left:18px;padding-right:18px}.pbb-grid.compact{grid-template-columns:minmax(0,1fr) minmax(300px,.45fr)}.pbb-fields{grid-template-columns:minmax(260px,.45fr) minmax(320px,.55fr)}.pbb-fields input,.pbb-fields select,.pbb-price-list-mode select{width:100%;height:34px;border:1px solid #cbd5e1;border-radius:9px;background:#fff;padding:0 9px}.pbb-price-list-field{min-width:0}.pbb-price-list-mode{display:grid;grid-template-columns:minmax(190px,.45fr) minmax(220px,.55fr);gap:8px;min-width:0}.pbb-table-wrap{display:block;overflow-x:auto!important;overflow-y:auto;-webkit-overflow-scrolling:touch}.pbb-items-scroll{max-height:640px}.pbb-items-table{width:max-content;min-width:1560px;table-layout:fixed}.pbb-items-table th,.pbb-items-table td{white-space:nowrap}.pbb-items-table th:nth-child(1),.pbb-items-table td:nth-child(1){width:74px;text-align:center}.pbb-items-table th:nth-child(2),.pbb-items-table td:nth-child(2){width:170px}.pbb-items-table th:nth-child(3),.pbb-items-table td:nth-child(3){width:240px;white-space:normal}.pbb-items-table th:nth-child(4),.pbb-items-table td:nth-child(4){width:190px}.pbb-items-table input[type=number]{width:116px}.pbb-rules-table{width:max-content;min-width:1120px}.pbb-root input[type='checkbox']{appearance:none!important;-webkit-appearance:none!important;display:inline-grid!important;place-content:center!important;width:18px!important;height:18px!important;min-width:18px!important;min-height:18px!important;margin:0!important;padding:0!important;border:1.5px solid #94a3b8!important;border-radius:6px!important;background:#fff!important;background-image:none!important;background-repeat:no-repeat!important;box-shadow:none!important;cursor:pointer}.pbb-root input[type='checkbox']::before{content:"";width:9px;height:9px;transform:scale(0);transition:transform .12s ease-in-out;clip-path:polygon(14% 44%,0 65%,45% 100%,100% 16%,80% 0,38% 62%);background:#fff}.pbb-root input[type='checkbox']:checked{border-color:#111827!important;background:#111827!important}.pbb-root input[type='checkbox']:checked::before{transform:scale(1)}.pbb-preview-dialog{display:grid;gap:12px}.pbb-preview-target{display:grid;gap:4px;border:1px solid #dbeafe;border-radius:14px;background:#eff6ff;color:#1e3a8a;padding:12px}.pbb-preview-target.update{border-color:#fed7aa;background:#fff7ed;color:#9a3412}.pbb-preview-target span{font-size:11px;font-weight:900;text-transform:uppercase}.pbb-preview-target strong{font-size:18px}.pbb-preview-target em{font-style:normal;font-size:12px}.pbb-update-alert{border:1px solid #fed7aa;background:#fffbeb;color:#92400e;border-radius:12px;padding:10px;font-weight:700}.pbb-preview-table-wrap{max-height:52vh;overflow:auto;border:1px solid #e2e8f0;border-radius:12px}.pbb-preview-table{width:100%;min-width:760px;border-collapse:separate;border-spacing:0}.pbb-preview-table th,.pbb-preview-table td{border-bottom:1px solid #edf2f7;padding:9px;text-align:left;vertical-align:top}.pbb-preview-table th{position:sticky;top:0;background:#f8fafc;color:#475569;font-size:11px;text-transform:uppercase}.pbb-preview-table small{display:block;color:#64748b}.pbb-preview-note{margin:0;color:#64748b;font-size:12px}.pbb-positive{color:#047857;font-weight:800}.pbb-negative{color:#b91c1c;font-weight:800}@media(max-width:1100px){.pbb-grid.compact,.pbb-fields,.pbb-price-list-mode{grid-template-columns:1fr}.pbb-shell{padding-left:12px;padding-right:12px}}
            .pbb-autosave-status{display:inline-flex;align-items:center;min-height:30px;border:1px solid #e2e8f0;border-radius:999px;background:#f8fafc;color:#64748b;padding:0 11px;font-size:12px;font-weight:800}.pbb-summary-compact{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.pbb-summary-compact>strong{font-size:13px}.pbb-summary-compact span{display:inline-flex;align-items:center;gap:5px;border:1px solid #edf2f7;border-radius:999px;background:#f8fafc;padding:5px 9px;font-weight:900}.pbb-summary-compact em{font-style:normal;color:#64748b;font-size:10px;text-transform:uppercase}.pbb-tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px;border:1px solid #e2e8f0;border-radius:14px;background:#f8fafc;padding:6px}.pbb-tabs button{height:32px;border:1px solid transparent;border-radius:10px;background:transparent;color:#475569;padding:0 12px;font-weight:900}.pbb-tabs button.active{background:#111827;color:#fff}.pbb-breakdown-panel{display:grid;gap:12px}.pbb-breakdown-head{display:grid;grid-template-columns:1fr;gap:8px;align-items:start;min-width:0}.pbb-breakdown-selector{display:grid;gap:5px;margin:0;min-width:0;max-width:100%}.pbb-breakdown-selector span{font-size:11px;font-weight:900;color:#64748b;text-transform:uppercase}.pbb-breakdown-selector input{width:100%;max-width:100%;min-width:0;height:38px;border:1px solid #cbd5e1;border-radius:10px;background:#fff;padding:0 12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.pbb-breakdown-selector input:focus{border-color:#6366f1;box-shadow:0 0 0 3px rgba(99,102,241,.14);outline:none}.pbb-breakdown-selected{display:flex;align-items:center;gap:10px;min-width:0;border:1px solid #edf2f7;border-radius:12px;background:#f8fafc;padding:9px 12px}.pbb-breakdown-selected strong{display:block;flex:0 0 auto;font-size:16px;color:#111827}.pbb-breakdown-selected small{display:block;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#64748b;font-size:13px}.pbb-breakdown-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.pbb-breakdown-metric{display:grid;gap:4px;border:1px solid #edf2f7;border-radius:12px;background:#f8fafc;padding:10px}.pbb-breakdown-metric.highlight{border-color:#c7d2fe;background:#eef2ff}.pbb-breakdown-metric em{font-style:normal;color:#64748b;font-size:10px;font-weight:900;text-transform:uppercase}.pbb-breakdown-metric strong{font-size:15px}.pbb-breakdown-grid{display:grid;grid-template-columns:minmax(240px,.45fr) minmax(0,1fr);gap:12px}.pbb-breakdown-details{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.pbb-breakdown-details span{display:grid;gap:3px;border:1px solid #edf2f7;border-radius:10px;background:#fff;padding:8px}.pbb-breakdown-details em{font-style:normal;color:#64748b;font-size:10px;font-weight:900;text-transform:uppercase}.pbb-breakdown-details strong{font-size:12px;overflow:hidden;text-overflow:ellipsis}.pbb-component-table-wrap{overflow:auto;border:1px solid #e2e8f0;border-radius:12px}.pbb-component-table{width:100%;min-width:660px;border-collapse:separate;border-spacing:0}.pbb-component-table th,.pbb-component-table td{border-bottom:1px solid #edf2f7;padding:8px;text-align:left;white-space:nowrap}.pbb-component-table th{background:#f8fafc;color:#64748b;font-size:10px;text-transform:uppercase}.pbb-history-list{display:grid;gap:8px}.pbb-history-row{display:flex;align-items:center;justify-content:space-between;gap:10px;border:1px solid #e2e8f0;border-radius:12px;background:#fff;padding:10px}.pbb-history-row strong{display:block;font-size:13px}.pbb-history-row span{display:block;color:#64748b;font-size:11px}.pbb-history-row p{margin:2px 0 0;color:#475569;font-size:12px}.pbb-breakdown-empty{border:1px dashed #cbd5e1;border-radius:12px;background:#f8fafc}@media(max-width:1100px){.pbb-breakdown-grid{grid-template-columns:1fr}.pbb-breakdown-metrics,.pbb-breakdown-details{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:640px){.pbb-breakdown-metrics,.pbb-breakdown-details{grid-template-columns:1fr}.pbb-breakdown-selected{display:grid;gap:3px}}
        `;
        style.textContent += `
            .pbb-column-config{position:relative;margin:0 0 12px}.pbb-column-config>summary{display:inline-flex;align-items:center;gap:8px;min-height:34px;border:1px solid #cbd5e1;border-radius:10px;background:#fff;color:#334155;padding:0 12px;font-weight:900;cursor:pointer;list-style:none}.pbb-column-config>summary::-webkit-details-marker{display:none}.pbb-column-config>summary span{color:#111827}.pbb-column-config>summary em{font-style:normal;color:#64748b;font-size:12px;font-weight:800}.pbb-column-config-panel{position:absolute;z-index:25;top:42px;left:0;width:min(720px,calc(100vw - 48px));max-height:430px;overflow:auto;border:1px solid #cbd5e1;border-radius:14px;background:#fff;box-shadow:0 18px 45px rgba(15,23,42,.18);padding:14px}.pbb-column-config-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px}.pbb-column-config-head strong{font-size:13px;color:#111827}.pbb-column-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:8px}.pbb-column-list label{display:flex;align-items:center;gap:8px;min-height:36px;margin:0;border:1px solid #e2e8f0;border-radius:10px;background:#f8fafc;padding:7px 9px;font-weight:800;color:#334155}.pbb-column-list label.locked{background:#eef2ff;color:#3730a3}.pbb-column-list label span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.pbb-column-list label small{margin-left:auto;color:#64748b;font-size:10px;text-transform:uppercase}.pbb-items-table th,.pbb-items-table td{white-space:nowrap!important;vertical-align:middle}.pbb-items-table .pbb-wrap{white-space:normal!important}.pbb-align-center{text-align:center!important}
            .pbb-collapsed-note{border:1px dashed #cbd5e1;border-radius:12px;background:#f8fafc;color:#64748b;padding:14px;font-weight:800}.pbb-customs-alert{border:1px solid #fed7aa;border-radius:12px;background:#fff7ed;color:#9a3412;padding:12px;margin:0 0 12px}.pbb-customs-alert strong{display:block;margin-bottom:4px;color:#7c2d12}.pbb-customs-alert p{margin:0 0 8px}.pbb-customs-alert ul{margin:0;padding-left:18px}.pbb-customs-alert li{margin:6px 0}.pbb-customs-alert small{color:#9a3412}.pbb-items-table th{position:sticky;top:0;z-index:8;background:#f8fafc;box-shadow:0 1px 0 #e5e7eb,0 4px 10px rgba(15,23,42,.06)}.pbb-sort-btn{display:flex;align-items:center;justify-content:space-between;gap:6px;width:100%;min-height:28px;border:0;background:transparent;color:inherit;font:inherit;font-weight:900;text-align:left;padding:0 10px 0 0;cursor:pointer}.pbb-sort-btn em{min-width:24px;color:#64748b;font-style:normal;font-size:10px;text-transform:uppercase}.pbb-column-resizer{position:absolute;top:0;right:0;width:8px;height:100%;cursor:col-resize;touch-action:none}.pbb-column-resizer::after{content:"";position:absolute;top:8px;bottom:8px;left:3px;width:1px;background:#cbd5e1}.pbb-column-resizer:hover::after{background:#2563eb}.pbb-column-config-grid{display:grid;grid-template-columns:minmax(220px,.45fr) minmax(280px,.55fr);gap:14px}.pbb-column-config-grid h3,.pbb-column-group h3{margin:0 0 8px;font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.04em}.pbb-column-order-list{display:grid;gap:6px}.pbb-column-order-row{display:grid;grid-template-columns:minmax(0,1fr) auto auto auto;gap:6px;align-items:center;border:1px solid #e2e8f0;border-radius:10px;background:#fff;padding:6px 7px}.pbb-column-order-row.locked{background:#eef2ff}.pbb-column-order-row span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:900}.pbb-column-order-row small{color:#64748b;font-size:10px}.pbb-column-group{display:grid;gap:8px;margin-bottom:12px}@media(max-width:900px){.pbb-column-config-panel{position:static;width:100%;margin-top:8px}.pbb-column-config-grid{grid-template-columns:1fr}}
        `;
        style.textContent += `
            .pbb-column-config-panel{width:min(780px,calc(100vw - 48px))}.pbb-column-config-grid{grid-template-columns:minmax(260px,.48fr) minmax(280px,.52fr)!important}.pbb-column-order-row{grid-template-columns:minmax(0,1fr) minmax(82px,auto) auto auto auto!important}.pbb-column-filter-row th{position:sticky;top:36px;z-index:7;background:#fff;box-shadow:0 1px 0 #e5e7eb}.pbb-column-filter-cell input{width:100%;height:28px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;padding:0 8px;font-size:11px}.pbb-filter-lock{display:inline-flex;color:#94a3b8;font-size:10px;font-weight:900;text-transform:uppercase}.pbb-sort-btn{padding-right:24px!important}.pbb-column-width-badge{display:none;position:absolute;right:12px;bottom:3px;border-radius:999px;background:#e0f2fe;color:#075985;padding:1px 5px;font-size:9px;font-weight:900}.pbb-items-table th:hover .pbb-column-width-badge,.pbb-column-resizing .pbb-column-width-badge{display:inline-flex}.pbb-column-resizer{right:-3px!important;width:14px!important}.pbb-column-resizer::after{left:6px!important;width:2px!important;border-radius:99px}.pbb-column-resizer:hover::after,.pbb-column-resizing .pbb-column-resizer::after{background:#2563eb!important}.pbb-column-resizing{cursor:col-resize!important;user-select:none}.pbb-item-cell{position:relative;display:inline-block;min-width:0}.pbb-item-link{display:grid;gap:2px;max-width:100%;border:0;background:transparent;color:#1d4ed8;text-align:left;padding:0;cursor:pointer}.pbb-item-link strong{text-decoration:underline;text-underline-offset:2px}.pbb-item-link small{color:#64748b;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.pbb-item-popover{display:none;position:absolute;z-index:40;top:calc(100% + 8px);left:0;width:300px;border:1px solid #cbd5e1;border-radius:14px;background:#fff;box-shadow:0 18px 45px rgba(15,23,42,.18);padding:12px;white-space:normal;color:#0f172a}.pbb-item-cell:hover .pbb-item-popover,.pbb-item-cell:focus-within .pbb-item-popover{display:grid;gap:8px}.pbb-item-popover span{color:#475569;font-size:12px}.pbb-item-popover dl{display:grid;grid-template-columns:82px minmax(0,1fr);gap:5px 8px;margin:0}.pbb-item-popover dt{color:#64748b;font-size:10px;font-weight:900;text-transform:uppercase}.pbb-item-popover dd{margin:0;min-width:0;overflow:hidden;text-overflow:ellipsis}.pbb-item-popover button{justify-self:start;min-height:30px;border:1px solid #cbd5e1;border-radius:9px;background:#f8fafc;color:#1d4ed8;padding:0 10px;font-weight:900}.pbb-list-price{display:grid;gap:1px}.pbb-list-price strong{font-weight:900}.pbb-list-price small{color:#64748b;font-size:10px;font-weight:800}.pbb-list-price.is-overridden strong,.pbb-list-price.is-overridden small{color:#047857}.pbb-filters{grid-template-columns:minmax(240px,1fr) minmax(170px,220px) auto!important;align-items:center}@media(max-width:900px){.pbb-filters{grid-template-columns:1fr!important}.pbb-item-popover{position:fixed;left:16px;right:16px;top:auto;bottom:16px;width:auto}}
        `;
        style.textContent += `
            .pbb-column-resizer{z-index:20!important}.pbb-items-table th[data-column="item_category"] .pbb-column-resizer{right:-5px!important;width:18px!important;z-index:24!important}.pbb-items-table th[data-column="item_category"] .pbb-sort-btn{padding-right:28px!important}
        `;
        style.textContent += `
            .pbb-column-filter-cell select{width:100%;height:28px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;padding:0 8px;font-size:11px}
        `;
        style.textContent += `
            .pbb-item-popover{width:244px!important;gap:7px!important;border-radius:11px!important;padding:9px!important;box-shadow:0 12px 28px rgba(15,23,42,.16)!important}.pbb-item-popover-head{display:flex;align-items:center;justify-content:space-between;gap:8px;min-width:0}.pbb-item-popover-head strong{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px}.pbb-item-popover-head button{height:24px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;color:#1d4ed8;padding:0 8px;font-size:11px;font-weight:900}.pbb-item-popover-name{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#475569;font-size:11px}.pbb-item-popover dl{display:grid!important;grid-template-columns:64px minmax(0,1fr)!important;gap:3px 7px!important;margin:0!important;font-size:11px!important}.pbb-item-popover dt{color:#64748b!important;font-weight:900!important;text-transform:uppercase!important}.pbb-item-popover dd{margin:0!important;min-width:0!important;overflow:hidden!important;text-overflow:ellipsis!important;white-space:nowrap!important;color:#0f172a!important}
        `;
        style.textContent += `
            .pbb-price-story{display:grid;gap:8px;border:1px solid #bfdbfe;border-radius:14px;background:#eff6ff;padding:12px;color:#0f172a}.pbb-price-story>strong{font-size:13px}.pbb-price-story>em,.pbb-price-story>small{color:#475569;font-style:normal;font-weight:800}.pbb-price-formula{display:flex;align-items:center;gap:7px;flex-wrap:wrap}.pbb-price-formula span{display:inline-grid;gap:2px;border:1px solid #dbeafe;border-radius:11px;background:#fff;padding:7px 9px;min-width:94px}.pbb-price-formula span.highlight{border-color:#93c5fd;background:#dbeafe}.pbb-price-formula em{font-size:10px;color:#64748b;font-style:normal;text-transform:uppercase;font-weight:900}.pbb-price-formula strong{font-size:13px}.pbb-price-formula b{color:#1d4ed8}.pbb-calculation-stack{display:grid;gap:10px;min-width:0}.pbb-calc-section{display:grid;gap:8px;border:1px solid #e2e8f0;border-radius:13px;background:#fff;padding:12px}.pbb-calc-section h3{margin:0;font-size:14px}.pbb-calc-section p{margin:0;color:#475569;line-height:1.45}.pbb-calc-note{border:1px dashed #cbd5e1;border-radius:11px;background:#f8fafc;padding:9px;color:#0f172a;font-weight:800;line-height:1.45}.pbb-calc-facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:7px}.pbb-calc-facts>span{display:grid;gap:2px;border:1px solid #edf2f7;border-radius:10px;background:#f8fafc;padding:7px}.pbb-calc-facts em{font-size:10px;color:#64748b;font-style:normal;text-transform:uppercase;font-weight:900}.pbb-calc-facts strong{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px}.pbb-calc-table th,.pbb-calc-table td{font-size:12px}.pbb-calc-table td:nth-child(2){white-space:normal;color:#334155}.pbb-calc-table td:nth-child(3){font-weight:900;text-align:right}
        `;
        style.textContent += `
            .pbb-sort-btn.static{cursor:default;justify-content:center;padding-right:0!important}.pbb-items-footer{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:8px;color:#475569;font-size:12px;font-weight:800}.pbb-items-footer span{display:inline-flex;align-items:center;min-height:28px;border:1px solid #e2e8f0;border-radius:999px;background:#f8fafc;padding:0 10px;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
        `;
        style.textContent += `
            .pbb-override-cell{display:grid;grid-template-columns:minmax(86px,1fr) 30px;gap:5px;align-items:center}.pbb-override-cell input{width:100%!important;min-width:0!important}.pbb-override-apply{height:30px;width:30px;border:1px solid #86efac;border-radius:9px;background:#f0fdf4;color:#166534;font-weight:900;line-height:1;cursor:pointer}.pbb-override-apply:hover{background:#dcfce7;border-color:#22c55e}.pbb-override-apply:focus{outline:2px solid #22c55e;outline-offset:2px}
        `;
        style.textContent += `
            .pbb-warning-details>summary{display:flex;align-items:center;justify-content:space-between;gap:12px;cursor:pointer;list-style:none}.pbb-warning-details>summary::-webkit-details-marker{display:none}.pbb-warning-details>summary h2{margin:0}.pbb-warning-details>summary span{display:inline-flex;align-items:center;min-height:28px;border:1px solid #fed7aa;border-radius:999px;background:#fff7ed;color:#9a3412;padding:0 10px;font-size:12px;font-weight:900}.pbb-warning-details .pbb-warning{margin-top:10px}
        `;
        style.textContent += `
            .pbb-auto-recalc{display:inline-flex;align-items:center;gap:7px;min-height:30px;margin:0;border:1px solid #bfdbfe;border-radius:999px;background:#eff6ff;color:#1e40af;padding:0 10px;font-size:12px;font-weight:900}.pbb-auto-recalc-status{display:inline-flex;align-items:center;min-height:30px;border:1px solid #e0e7ff;border-radius:999px;background:#eef2ff;color:#3730a3;padding:0 11px;font-size:12px;font-weight:800}
        `;
        style.textContent += `
            .pbb-fields{grid-template-columns:minmax(180px,.25fr) minmax(0,.75fr)!important}.pbb-price-list-mode.existing{grid-template-columns:minmax(150px,.28fr) minmax(360px,.72fr)!important}.pbb-price-list-mode.new{grid-template-columns:minmax(150px,.28fr) minmax(280px,.52fr) minmax(120px,.2fr)!important}.pbb-price-list-field small{white-space:normal;color:#64748b;font-size:12px;font-weight:800}
        `;
        style.textContent += `
            .pbb-rate-details{margin-top:4px;border:1px solid #e2e8f0;border-radius:10px;background:#f8fafc;padding:0}.pbb-rate-details>summary{display:flex;align-items:center;gap:8px;min-height:30px;padding:0 10px;cursor:pointer;list-style:none}.pbb-rate-details>summary::-webkit-details-marker{display:none}.pbb-rate-details>summary span{font-size:11px;font-weight:900;color:#334155;text-transform:uppercase}.pbb-rate-details>summary small{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#64748b;font-size:11px;font-weight:800}.pbb-rate-details p{margin:0;padding:0 10px 9px;color:#64748b;font-size:12px;font-weight:800}.pbb-rate-list{display:grid;gap:5px;padding:0 8px 8px}.pbb-rate-row{display:grid;grid-template-columns:minmax(130px,.35fr) minmax(110px,.25fr) minmax(90px,.18fr) minmax(150px,.22fr);gap:7px;align-items:center;border:1px solid #e2e8f0;border-radius:9px;background:#fff;padding:6px 8px;font-size:12px}.pbb-rate-row.missing{border-color:#fed7aa;background:#fff7ed}.pbb-rate-row span{display:grid;gap:1px;min-width:0}.pbb-rate-row em{font-size:9px;color:#64748b;font-style:normal;text-transform:uppercase;font-weight:900}.pbb-rate-row strong,.pbb-rate-row small{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.pbb-rate-row small{color:#475569;font-weight:800}
        `;
        style.textContent += `
            .pbb-preview-override{display:block;margin-top:2px;color:#7c3aed;font-size:11px;font-weight:900}
        `;
        document.head.appendChild(style);
    }
})();
