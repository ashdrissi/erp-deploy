(function () {
    const PAGE_NAME = "buying-price-builder";
    const STORAGE_KEY = "orderlift_buying_price_builder_v2";
    const API = "orderlift.orderlift_sales.page.buying_price_builder.buying_price_builder";

    const STATE = {
        sourcePriceList: "",
        selectedPriceLists: [],
        priceLists: [],
        addItemQuery: "",
        addItemSelection: [],
        itemOptions: [],
        itemMap: {},
        itemDropdownOpen: false,
        priceListDropdownOpen: false,
        workingItems: [],
        applyPct: 0,
        applyPctScope: "selected",
        fixedPercent: null,
        workingSelection: [],
        formulaSourceOptions: [],
        formulaTargetOptions: [],
        newFormula: { name: "", source: "", sourceQuery: "", sourceDropdownOpen: false, targets: [], targetPcts: {}, targetQuery: "", targetDropdownOpen: false, pct: 0, checked: true },
        editingFormulaName: "",
        manualPrices: {},
        formulas: [],
        previewRows: [],
        warnings: [],
        isLoading: true,
        isPreviewLoading: false,
        activeTab: "items",
        saveMode: "new",
        newPriceList: "",
        updatePriceList: "",
        message: "",
    };

    frappe.pages[PAGE_NAME].on_page_load = function (wrapper) {
        const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Buying Price Builder"), single_column: true });
        wrapper.page = page;
        page.main.addClass("bpb-root");
        injectStyles();
        loadDraft();
        applyHeader(page);
        render(page);
        loadInitialData(page);
    };

    frappe.pages[PAGE_NAME].on_page_show = function (wrapper) {
        if (!wrapper.page) return;
        applyHeader(wrapper.page);
        render(wrapper.page);
        if (!STATE.priceLists.length) loadInitialData(wrapper.page);
    };

    function applyHeader(page) {
        page.set_title(__("Buying Price Builder"));
        page.set_primary_action(__("Validate Save"), () => validateSave(page), "check");
        setTimeout(() => {
            if (!frappe.breadcrumbs) return;
            frappe.breadcrumbs.clear();
            frappe.breadcrumbs.append_breadcrumb_element("/desk/home-page?sidebar=Main+Dashboard", __("Items & Price Lists"), "title-text");
            frappe.breadcrumbs.append_breadcrumb_element("", __("Buying Price Builder"), "title-text");
            frappe.breadcrumbs.toggle(true);
        }, 0);
    }

    async function loadInitialData(page) {
        STATE.isLoading = true;
        render(page);
        try {
            const payload = await callBackend("get_builder_payload");
            STATE.priceLists = payload.price_lists || [];
            STATE.formulas = (payload.formula_rules || []).map(normalizeRule);
            const names = getPriceListNames();
            if (!STATE.sourcePriceList && names.length) STATE.sourcePriceList = names[0];
            if (!STATE.updatePriceList && names.length) STATE.updatePriceList = names[0];
            if (!STATE.selectedPriceLists.length && STATE.sourcePriceList) STATE.selectedPriceLists = [STATE.sourcePriceList];
            await Promise.all([searchItems(page, ""), searchFormulaSources(page, ""), searchFormulaTargets(page, "")]);
            await refreshPreview(page);
        } catch (error) {
            console.error("Buying Price Builder load failed", error);
            STATE.message = error.message || __("Could not load Buying Price Builder data.");
        } finally {
            STATE.isLoading = false;
            render(page);
        }
    }

    function callBackend(method, args = {}) {
        return new Promise((resolve, reject) => {
            frappe.call({
                method: `${API}.${method}`,
                args,
                callback: (response) => resolve(response.message || {}),
                error: (error) => reject(error),
            });
        });
    }

    async function searchItems(page, query) {
        const rows = await callBackend("search_items", { query, source_price_list: STATE.sourcePriceList, limit: 500 });
        STATE.itemOptions = (rows || []).map(normalizeItem);
        rememberItems(STATE.itemOptions);
        if (page) render(page);
    }

    async function searchFormulaSources(page, query) {
        const rows = await callBackend("search_items", { query, source_price_list: STATE.sourcePriceList, limit: 500 });
        STATE.formulaSourceOptions = (rows || []).map(normalizeItem);
        rememberItems(STATE.formulaSourceOptions);
        if (!STATE.newFormula.source && STATE.formulaSourceOptions.length) STATE.newFormula.source = STATE.formulaSourceOptions[0].code;
        if (page) render(page);
    }

    async function searchFormulaTargets(page, query) {
        const rows = await callBackend("search_items", { query, source_price_list: STATE.sourcePriceList, limit: 500 });
        STATE.formulaTargetOptions = (rows || []).map(normalizeItem);
        rememberItems(STATE.formulaTargetOptions);
        if (page) render(page);
    }

    async function refreshPreview(page) {
        if (!STATE.sourcePriceList || !STATE.workingItems.length) {
            STATE.previewRows = [];
            STATE.warnings = [];
            if (page) render(page);
            return;
        }
        STATE.isPreviewLoading = true;
        if (page) render(page);
        try {
            const payload = await callBackend("calculate_preview", { payload: JSON.stringify(buildServerPayload()) });
            STATE.previewRows = (payload.rows || []).map(normalizePreviewRow);
            STATE.warnings = [];
            rememberItems(STATE.previewRows);
        } catch (error) {
            console.error("Buying Price Builder preview failed", error);
            STATE.message = error.message || __("Could not refresh price preview.");
        } finally {
            STATE.isPreviewLoading = false;
            if (page) render(page);
        }
    }

    async function applyPriceListSelection(page) {
        const priceLists = STATE.selectedPriceLists.length ? STATE.selectedPriceLists : STATE.sourcePriceList ? [STATE.sourcePriceList] : [];
        if (!priceLists.length) {
            STATE.message = __("Select at least one buying price list.");
            render(page);
            return;
        }
        STATE.isLoading = true;
        render(page);
        try {
            const rows = await callBackend("get_items_from_price_lists", { price_lists: JSON.stringify(priceLists), limit: 5000 });
            const items = (rows || []).map(normalizeItem);
            rememberItems(items);
            STATE.itemOptions = items;
            STATE.addItemSelection = items.map((item) => item.code).filter(Boolean);
            STATE.workingItems = [...STATE.addItemSelection];
            STATE.workingSelection = [...STATE.workingItems];
            STATE.sourcePriceList = priceLists[0];
            STATE.priceListDropdownOpen = false;
            STATE.message = __(`${STATE.workingItems.length} article(s) loaded from selected buying price list(s).`);
            await refreshPreview(page);
        } finally {
            STATE.isLoading = false;
            render(page);
        }
    }

    function scheduleItemSearch(page) {
        clearTimeout(STATE.itemSearchTimer);
        STATE.itemSearchTimer = setTimeout(() => searchItems(page, STATE.addItemQuery), 250);
    }

    function scheduleFormulaSourceSearch(page) {
        clearTimeout(STATE.sourceSearchTimer);
        STATE.sourceSearchTimer = setTimeout(() => searchFormulaSources(page, STATE.newFormula.sourceQuery || ""), 250);
    }

    function scheduleFormulaTargetSearch(page) {
        clearTimeout(STATE.targetSearchTimer);
        STATE.targetSearchTimer = setTimeout(() => searchFormulaTargets(page, STATE.newFormula.targetQuery || ""), 250);
    }

    function buildServerPayload() {
        return {
            source_price_list: STATE.sourcePriceList,
            item_codes: STATE.workingItems,
            manual_prices: STATE.manualPrices,
            formula_rules: STATE.formulas,
            fixed_percent: STATE.fixedPercent || {},
            save_mode: STATE.saveMode,
            target_price_list: STATE.saveMode === "new" ? STATE.newPriceList : STATE.updatePriceList,
        };
    }

    function render(page) {
        const preview = calculatePreview();
        const checkedFormulaCount = STATE.formulas.filter((rule) => rule.checked).length;
        const changedCount = preview.filter((row) => row.delta !== 0).length;

        page.main.html(`
            <main class="bpb-shell">
                <section class="bpb-header">
                    <div>
                        <span>${__("Buying prices")}</span>
                        <h1>${__("Build a supplier price list")}</h1>
                    </div>
                    <div class="bpb-kpis">
                        ${kpi(preview.length, __("Items"))}
                        ${kpi(checkedFormulaCount, __("Active formulas"))}
                        ${kpi(changedCount, __("Changed"))}
                    </div>
                </section>
                ${STATE.isLoading || STATE.isPreviewLoading ? `<div class="bpb-status-line">${STATE.isLoading ? __("Loading buying price builder data...") : __("Refreshing price preview...")}</div>` : ""}

                <section class="bpb-workflow">
                    <section class="bpb-main">
                        <div class="bpb-card bpb-add-card">
                            <div class="bpb-card-title">
                                <strong>${__("1. Add item")}</strong>
                                <small>${__("Search by category, brand, item group, code, or name. Checked articles become the working list.")}</small>
                            </div>
                            <div class="bpb-add-row">
                                <div class="bpb-check-dropdown ${STATE.itemDropdownOpen ? "is-open" : ""}">
                                    <button type="button" class="bpb-dropdown-button" data-action="toggle-item-dropdown">
                                        <span>${escapeHtml(selectedItemLabel())}</span>
                                        <em>${__("Select items")}</em>
                                    </button>
                                    <div class="bpb-dropdown-panel">
                                        <input class="bpb-input" data-field="addItemQuery" value="${escapeAttr(STATE.addItemQuery)}" placeholder="${__("Search category, brand, group, item")}" />
                                        <div class="bpb-mini-actions">
                                            <button type="button" class="bpb-link-btn" data-action="select-visible-items">${__("Select all")}</button>
                                            <button type="button" class="bpb-link-btn" data-action="deselect-visible-items">${__("Deselect all")}</button>
                                        </div>
                                        <div class="bpb-checkbox-list" data-item-options>${renderArticleCheckboxes()}</div>
                                    </div>
                                </div>
                                <button class="bpb-btn bpb-btn-primary" data-action="apply-item-selection">${__("Apply selection")}</button>
                            </div>
                        </div>

                        <div class="bpb-card bpb-controls bpb-price-list-controls">
                            <label><span>${__("Add from buying price list")}</span>${renderPriceListDropdown()}</label>
                            <button class="bpb-btn bpb-btn-primary" data-action="apply-price-list-selection">${__("Apply selection")}</button>
                        </div>

                        <div class="bpb-card bpb-controls bpb-pct-controls">
                            <label><span>${__("Fixed % adjustment")}</span><input data-field="applyPct" type="number" step="0.01" value="${escapeAttr(STATE.applyPct)}" /></label>
                            <label><span>${__("Apply to")}</span><select data-field="applyPctScope"><option value="selected" ${STATE.applyPctScope === "selected" ? "selected" : ""}>${__("Selected rows")}</option><option value="all" ${STATE.applyPctScope === "all" ? "selected" : ""}>${__("All rows")}</option></select></label>
                            <button class="bpb-btn bpb-btn-primary" data-action="apply-fixed-pct">${__("Apply fixed %")}</button>
                        </div>

                        <div class="bpb-card bpb-tab-card">
                            ${renderTabBar(checkedFormulaCount)}
                            ${STATE.activeTab === "formulas" ? renderFormulaTab() : renderItemsTab(preview)}
                        </div>

                        <div class="bpb-card bpb-save-card">
                            <div class="bpb-card-title"><strong>${__("3. Save result")}</strong><small>${__("Choose whether the final values create a new buying price list or update an existing one.")}</small></div>
                            <div class="bpb-save-grid">
                                <label class="bpb-radio"><input type="radio" name="save_mode" value="new" ${STATE.saveMode === "new" ? "checked" : ""} /> ${__("Save in new price list")}</label>
                                <input class="bpb-input" data-field="newPriceList" value="${escapeAttr(STATE.newPriceList)}" ${STATE.saveMode !== "new" ? "disabled" : ""} />
                                <label class="bpb-radio"><input type="radio" name="save_mode" value="update" ${STATE.saveMode === "update" ? "checked" : ""} /> ${__("Update price list")}</label>
                                <select data-field="updatePriceList" ${STATE.saveMode !== "update" ? "disabled" : ""}>${getPriceListNames().map((name) => option(name, STATE.updatePriceList)).join("")}</select>
                            </div>
                            <div class="bpb-actions">
                                <button class="bpb-btn bpb-btn-ghost" data-action="copy-summary">${__("Copy summary")}</button>
                                <button class="bpb-btn bpb-btn-primary" data-action="validate-save">${__("Validate save flow")}</button>
                            </div>
                        </div>
                    </section>
                </section>
                ${STATE.message ? `<div class="bpb-toast" role="status">${escapeHtml(STATE.message)}</div>` : ""}
            </main>
        `);
        bindEvents(page);
    }

    function renderArticleCheckboxes() {
        const rows = visibleArticles();
        return rows.map((item) => `
            <label class="bpb-checkbox-row">
                <input type="checkbox" data-item-check="${escapeAttr(item.code)}" ${STATE.addItemSelection.includes(item.code) ? "checked" : ""} />
                <span><strong>${escapeHtml(item.code)}</strong><small>${escapeHtml(item.name)} · ${escapeHtml(item.category)} · ${escapeHtml(item.itemGroup)}</small></span>
                <em>${escapeHtml(item.brand)}</em>
            </label>
        `).join("") || `<div class="bpb-empty">${__("No article found")}</div>`;
    }

    function renderPriceListDropdown() {
        return `
            <div class="bpb-check-dropdown ${STATE.priceListDropdownOpen ? "is-open" : ""}">
                <button type="button" class="bpb-dropdown-button" data-action="toggle-price-list-dropdown">
                    <span>${escapeHtml(selectedPriceListsLabel())}</span>
                    <em>${__("Select lists")}</em>
                </button>
                <div class="bpb-dropdown-panel bpb-dropdown-panel-compact">
                    <div class="bpb-mini-actions">
                        <button type="button" class="bpb-link-btn" data-action="select-all-price-lists">${__("Select all price lists")}</button>
                        <button type="button" class="bpb-link-btn" data-action="deselect-all-price-lists">${__("Clear price lists")}</button>
                    </div>
                    ${renderPriceListCheckboxes()}
                </div>
            </div>
        `;
    }

    function renderPriceListCheckboxes() {
        const names = getPriceListNames();
        if (!names.length) return `<div class="bpb-empty">${__("No buying price list found")}</div>`;
        return names.map((name) => `
            <button type="button" class="bpb-select-row bpb-price-list-row ${STATE.selectedPriceLists.includes(name) ? "is-selected" : ""}" data-price-list-pick="${escapeAttr(name)}">
                <span class="bpb-select-check" aria-hidden="true">${STATE.selectedPriceLists.includes(name) ? "✓" : ""}</span>
                <span><strong>${escapeHtml(name)}</strong><small>${__("Buying source")}</small></span>
            </button>
        `).join("");
    }

    function renderTabBar(checkedFormulaCount) {
        return `
            <div class="bpb-tab-bar">
                <button type="button" class="bpb-tab ${STATE.activeTab === "items" ? "is-active" : ""}" data-action="show-items-tab">${__("Working list")}</button>
                <button type="button" class="bpb-tab ${STATE.activeTab === "formulas" ? "is-active" : ""}" data-action="show-formulas-tab">${__("Formulas")} <span>${checkedFormulaCount}</span></button>
            </div>
        `;
    }

    function renderItemsTab(preview) {
        return `
            <div class="bpb-card-title bpb-title-row">
                <div><strong>${__("2. Edit working list")}</strong><small>${__("Use source prices or enter manual prices. Formula targets are recalculated automatically.")}</small></div>
                <div class="bpb-title-actions">
                    <button class="bpb-btn bpb-btn-ghost" data-action="select-all-working">${__("Select all")}</button>
                    <button class="bpb-btn bpb-btn-ghost" data-action="deselect-all-working">${__("Deselect all")}</button>
                    <button class="bpb-btn bpb-btn-ghost" data-action="reset-list">${__("Reset list")}</button>
                </div>
            </div>
            <div class="bpb-table-wrap">
                <table class="bpb-table">
                    <thead><tr><th></th><th>${__("Item")}</th><th>${__("Brand")}</th><th>${__("Base")}</th><th>${__("Manual")}</th><th>${__("Formula")}</th><th>${__("Final")}</th><th></th></tr></thead>
                    <tbody>${renderWorkingRows(preview)}</tbody>
                </table>
            </div>
        `;
    }

    function renderFormulaTab() {
        return `
            <div class="bpb-card-title">
                <strong>${__("2. Saved formulas")}</strong>
                <small>${__("Create formulas and check the ones that should auto-update linked item prices in the working list.")}</small>
            </div>
            <div class="bpb-formula-builder">
                <label><span>${__("Rule name")}</span><input class="bpb-input" data-new-formula="name" value="${escapeAttr(STATE.newFormula.name)}" placeholder="${__("Rule name")}" /></label>
                <label class="bpb-formula-source-picker"><span>${__("Source item")}</span>${renderFormulaSourceDropdown()}</label>
                <label class="bpb-formula-target-picker"><span>${__("Target articles")}</span>${renderFormulaTargetDropdown()}</label>
                <label><span>${__("Default %")}</span><input class="bpb-input" data-new-formula="pct" type="number" step="0.01" value="${escapeAttr(STATE.newFormula.pct)}" /></label>
                <label class="bpb-radio"><input type="checkbox" data-new-formula="checked" ${STATE.newFormula.checked ? "checked" : ""} /> ${__("Active")}</label>
                <button class="bpb-btn bpb-btn-primary" data-action="create-formula">${STATE.editingFormulaName ? __("Update rule") : __("Create formula")}</button>
                ${STATE.editingFormulaName ? `<button class="bpb-btn bpb-btn-ghost" data-action="cancel-formula-edit">${__("Cancel edit")}</button>` : ""}
            </div>
            <div class="bpb-formulas">${renderFormulaRows()}</div>
        `;
    }

    function renderFormulaRows() {
        return STATE.formulas.map((rule, index) => `
            <div class="bpb-formula-row">
                <label class="bpb-formula-toggle"><input type="checkbox" data-formula-check="${index}" ${rule.checked ? "checked" : ""} /><span><strong>${escapeHtml(rule.ruleName || rule.rule_name || rule.label || rule.source)}</strong><small>${escapeHtml(formatRuleTargets(rule))} = ${escapeHtml(rule.source)}</small></span></label>
                <div class="bpb-row-actions">
                    <button type="button" class="bpb-link-btn" data-formula-edit="${index}">${__("Edit")}</button>
                    <button type="button" class="bpb-link-btn bpb-danger-link" data-formula-delete="${index}">${__("Delete")}</button>
                </div>
            </div>
        `).join("");
    }

    function renderFormulaTargetDropdown() {
        return `
            <div class="bpb-check-dropdown ${STATE.newFormula.targetDropdownOpen ? "is-open" : ""}">
                <button type="button" class="bpb-dropdown-button" data-action="toggle-formula-target-dropdown">
                    <span>${escapeHtml(formulaTargetsLabel())}</span>
                    <em>${__("Select targets")}</em>
                </button>
                <div class="bpb-dropdown-panel bpb-dropdown-panel-wide">
                    <input class="bpb-input" data-new-formula="targetQuery" value="${escapeAttr(STATE.newFormula.targetQuery)}" placeholder="${__("Search target articles")}" />
                    <div class="bpb-mini-actions">
                        <button type="button" class="bpb-link-btn" data-action="select-visible-formula-targets">${__("Select all")}</button>
                        <button type="button" class="bpb-link-btn" data-action="deselect-visible-formula-targets">${__("Deselect all")}</button>
                    </div>
                    <div class="bpb-checkbox-list" data-formula-target-options>${renderFormulaTargetCheckboxes()}</div>
                </div>
            </div>
        `;
    }

    function renderFormulaSourceDropdown() {
        return `
            <div class="bpb-check-dropdown ${STATE.newFormula.sourceDropdownOpen ? "is-open" : ""}">
                <button type="button" class="bpb-dropdown-button" data-action="toggle-formula-source-dropdown">
                    <span>${escapeHtml(formulaSourceLabel())}</span>
                    <em>${__("Select source")}</em>
                </button>
                <div class="bpb-dropdown-panel bpb-dropdown-panel-wide">
                    <input class="bpb-input" data-new-formula="sourceQuery" value="${escapeAttr(STATE.newFormula.sourceQuery || "")}" placeholder="${__("Search source article")}" />
                    <div class="bpb-checkbox-list" data-formula-source-options>${renderFormulaSourceRows()}</div>
                </div>
            </div>
        `;
    }

    function renderFormulaSourceRows() {
        return visibleFormulaSources().map((item) => `
            <button type="button" class="bpb-select-row ${item.code === STATE.newFormula.source ? "is-selected" : ""}" data-formula-source-pick="${escapeAttr(item.code)}">
                <span class="bpb-select-check" aria-hidden="true">${item.code === STATE.newFormula.source ? "✓" : ""}</span>
                <span><strong>${escapeHtml(item.code)}</strong><small>${escapeHtml(item.name)} · ${escapeHtml(item.category)} · ${escapeHtml(item.itemGroup)}</small></span>
                <em>${escapeHtml(item.brand)}</em>
            </button>
        `).join("") || `<div class="bpb-empty">${__("No source article found")}</div>`;
    }

    function renderFormulaTargetCheckboxes() {
        return visibleFormulaTargets().map((item) => `
            <label class="bpb-checkbox-row">
                <input type="checkbox" data-formula-target-check="${escapeAttr(item.code)}" ${normalizeNewFormulaTargets().includes(item.code) ? "checked" : ""} />
                <span><strong>${escapeHtml(item.code)}</strong><small>${escapeHtml(item.name)} · ${escapeHtml(item.category)} · ${escapeHtml(item.itemGroup)}</small></span>
                <em>${escapeHtml(item.brand)}</em>
                ${normalizeNewFormulaTargets().includes(item.code) ? `<input class="bpb-target-pct" data-formula-target-pct="${escapeAttr(item.code)}" type="number" step="0.01" value="${escapeAttr(getFormulaTargetPct(item.code))}" aria-label="${__("Target percentage")}" />` : ""}
            </label>
        `).join("") || `<div class="bpb-empty">${__("No target article found")}</div>`;
    }

    function renderWorkingRows(preview) {
        if (!preview.length) return `<tr><td colspan="8" class="bpb-empty-cell">${__("Add items to start building a buying price list.")}</td></tr>`;
        return preview.map((row) => {
            return `
                <tr>
                    <td><input type="checkbox" data-working-check="${escapeAttr(row.code)}" ${STATE.workingSelection.includes(row.code) ? "checked" : ""} /></td>
                    <td><strong>${escapeHtml(row.code)}</strong><small>${escapeHtml(row.name)} · ${escapeHtml(row.uom)}</small></td>
                    <td>${escapeHtml(row.brand || "-")}</td>
                    <td class="bpb-num">${formatMoney(row.listPrice)}</td>
                    <td><input class="bpb-price-input" data-manual-price="${escapeAttr(row.code)}" type="number" step="0.01" value="${escapeAttr(getManualPrice(row.code))}" placeholder="${escapeAttr(formatMoney(row.listPrice))}" ${row.formulaLabel ? "disabled" : ""} /></td>
                    <td>${row.formulaLabel ? `<span class="bpb-formula-chip">${escapeHtml(row.formulaLabel)}</span>` : `<span class="bpb-muted">${__("None")}</span>`}</td>
                    <td><strong class="bpb-num">${formatMoney(row.finalPrice)}</strong><small class="${row.delta >= 0 ? "bpb-up" : "bpb-down"}">${formatMoney(row.delta)}</small></td>
                    <td><button class="bpb-icon-btn" data-remove-code="${escapeAttr(row.code)}" aria-label="${__("Remove item")}">×</button></td>
                </tr>
            `;
        }).join("");
    }

    function bindEvents(page) {
        page.main.find("[data-field]").on("input change", function (event) {
            const field = this.dataset.field;
            STATE[field] = field === "applyPct" ? Number(this.value || 0) : this.value;
            if (field === "newPriceList" || field === "updatePriceList") {
                return;
            }
            if (field === "addItemQuery" && event.type === "input") {
                scheduleItemSearch(page);
                return;
            }
            render(page);
        });
        page.main.find("[data-field='addItemQuery']").on("keydown", function (event) {
            if (event.key !== "Enter") return;
            event.preventDefault();
            handleAction(page, "apply-item-selection");
        });
        bindItemCheckboxes(page);
        page.main.find("[data-working-check]").on("change", function () {
            toggleWorkingSelection(this.dataset.workingCheck, this.checked);
        });
        page.main.find("[data-new-formula]").on("input change", function () {
            const field = this.dataset.newFormula;
            STATE.newFormula[field] = field === "pct" ? Number(this.value || 0) : field === "checked" ? this.checked : this.value;
            if (field === "targetQuery") {
                scheduleFormulaTargetSearch(page);
            } else if (field === "sourceQuery") {
                scheduleFormulaSourceSearch(page);
            } else if (field === "source") {
                STATE.newFormula.targets = normalizeNewFormulaTargets().filter((code) => code !== STATE.newFormula.source);
                render(page);
            }
        });
        bindFormulaTargetCheckboxes(page);
        bindFormulaSourceRows(page);
        page.main.find("[data-formula-target-pct]").on("input", function () {
            STATE.newFormula.targetPcts = STATE.newFormula.targetPcts || {};
            STATE.newFormula.targetPcts[this.dataset.formulaTargetPct] = Number(this.value || 0);
        });
        page.main.find("[data-price-list-pick]").on("click", function () {
            togglePriceListSelection(this.dataset.priceListPick);
            render(page);
        });
        page.main.find("[data-manual-price]").on("input", function () {
            if (this.value === "") delete STATE.manualPrices[this.dataset.manualPrice];
            else STATE.manualPrices[this.dataset.manualPrice] = Number(this.value || 0);
            refreshPreview(page);
        });
        page.main.find("[data-formula-check]").on("change", function () {
            STATE.formulas[Number(this.dataset.formulaCheck)].checked = this.checked;
            refreshPreview(page);
        });
        page.main.find("[data-formula-edit]").on("click", function () {
            editFormulaRule(Number(this.dataset.formulaEdit));
            render(page);
        });
        page.main.find("[data-formula-delete]").on("click", function () {
            deleteFormulaRule(page, Number(this.dataset.formulaDelete));
        });
        page.main.find("input[name='save_mode']").on("change", function () {
            STATE.saveMode = this.value;
            render(page);
        });
        page.main.find("[data-action]").on("click", function () {
            handleAction(page, this.dataset.action);
        });
        page.main.find("[data-remove-code]").on("click", function () {
            removeWorkingItem(this.dataset.removeCode);
            refreshPreview(page);
        });
    }

    function bindItemCheckboxes(page) {
        page.main.find("[data-item-check]").off("change").on("change", function () {
            toggleItemSelection(this.dataset.itemCheck, this.checked);
        });
    }

    function bindFormulaTargetCheckboxes(page) {
        page.main.find("[data-formula-target-check]").off("change").on("change", function () {
            toggleFormulaTarget(this.dataset.formulaTargetCheck, this.checked);
            render(page);
        });
    }

    function bindFormulaSourceRows(page) {
        page.main.find("[data-formula-source-pick]").off("click").on("click", function () {
            STATE.newFormula.source = this.dataset.formulaSourcePick;
            STATE.newFormula.sourceQuery = "";
            STATE.newFormula.sourceDropdownOpen = false;
            STATE.newFormula.targets = normalizeNewFormulaTargets().filter((code) => code !== STATE.newFormula.source);
            render(page);
        });
    }

    async function handleAction(page, action) {
        if (action === "toggle-item-dropdown") {
            STATE.itemDropdownOpen = !STATE.itemDropdownOpen;
            STATE.priceListDropdownOpen = false;
        } else if (action === "toggle-price-list-dropdown") {
            STATE.priceListDropdownOpen = !STATE.priceListDropdownOpen;
            STATE.itemDropdownOpen = false;
        } else if (action === "toggle-formula-target-dropdown") {
            STATE.newFormula.targetDropdownOpen = !STATE.newFormula.targetDropdownOpen;
            STATE.newFormula.sourceDropdownOpen = false;
        } else if (action === "toggle-formula-source-dropdown") {
            STATE.newFormula.sourceDropdownOpen = !STATE.newFormula.sourceDropdownOpen;
            STATE.newFormula.targetDropdownOpen = false;
        } else if (action === "show-items-tab") {
            STATE.activeTab = "items";
        } else if (action === "show-formulas-tab") {
            STATE.activeTab = "formulas";
        } else if (action === "select-visible-items") {
            selectVisibleItems(true);
        } else if (action === "deselect-visible-items") {
            selectVisibleItems(false);
        } else if (action === "select-all-price-lists") {
            selectAllPriceLists(true);
        } else if (action === "deselect-all-price-lists") {
            selectAllPriceLists(false);
        } else if (action === "apply-item-selection") {
            applyItemSelection();
            await refreshPreview(page);
        } else if (action === "select-all-working") {
            STATE.workingSelection = [...STATE.workingItems];
        } else if (action === "deselect-all-working") {
            STATE.workingSelection = [];
        } else if (action === "apply-fixed-pct") {
            applyFixedPct();
            await refreshPreview(page);
        } else if (action === "apply-price-list-selection") {
            await applyPriceListSelection(page);
        } else if (action === "select-visible-formula-targets") {
            selectVisibleFormulaTargets(true);
        } else if (action === "deselect-visible-formula-targets") {
            selectVisibleFormulaTargets(false);
        } else if (action === "create-formula") {
            await createFormula(page);
        } else if (action === "cancel-formula-edit") {
            resetFormulaBuilder();
        } else if (action === "reset-list") {
            STATE.workingItems = [];
            STATE.addItemSelection = [];
            STATE.workingSelection = [];
            STATE.previewRows = [];
            STATE.fixedPercent = null;
            STATE.message = __("Working list cleared.");
        } else if (action === "copy-summary") {
            copySummary();
            STATE.message = __("Summary copied.");
        } else if (action === "validate-save") {
            await validateSave(page);
        }
        render(page);
    }

    function calculatePreview() {
        return STATE.previewRows || [];
    }

    async function validateSave(page) {
        const target = STATE.saveMode === "new" ? STATE.newPriceList : STATE.updatePriceList;
        if (!target) {
            STATE.message = __("Choose a target buying price list before saving.");
            if (page) render(page);
            return;
        }
        const result = await callBackend("save_result", { payload: JSON.stringify(buildServerPayload()) });
        STATE.message = __(`Saved ${result.created || 0} new and updated ${result.updated || 0} Item Price row(s).`);
        STATE.warnings = result.warnings || [];
        frappe.msgprint({ title: __("Buying prices saved"), indicator: "green", message: STATE.message });
        await refreshPreview(page);
    }

    function saveDraft() {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({
            sourcePriceList: STATE.sourcePriceList,
            selectedPriceLists: STATE.selectedPriceLists,
            applyPct: STATE.applyPct,
            applyPctScope: STATE.applyPctScope,
            workingItems: STATE.workingItems,
            addItemSelection: STATE.addItemSelection,
            workingSelection: STATE.workingSelection,
            manualPrices: STATE.manualPrices,
            formulas: STATE.formulas,
            newFormula: STATE.newFormula,
            activeTab: STATE.activeTab,
            saveMode: STATE.saveMode,
            newPriceList: STATE.newPriceList,
            updatePriceList: STATE.updatePriceList,
        }));
    }

    function loadDraft() {
        try {
            const draft = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
            Object.assign(STATE, draft);
            STATE.addItemSelection = Array.from(new Set([...(STATE.workingItems || []), ...(Array.isArray(STATE.addItemSelection) ? STATE.addItemSelection : [])]));
            STATE.selectedPriceLists = Array.isArray(STATE.selectedPriceLists) ? STATE.selectedPriceLists : (STATE.sourcePriceList ? [STATE.sourcePriceList] : []);
            STATE.workingSelection = Array.isArray(STATE.workingSelection) ? STATE.workingSelection : [...STATE.workingItems];
            STATE.formulas = (STATE.formulas || []).map(normalizeRule);
            STATE.newFormula = normalizeNewFormula(STATE.newFormula);
        } catch (error) {
            console.warn("Buying Price Builder draft ignored", error);
        }
    }

    function copySummary() {
        const payload = { target: STATE.saveMode === "new" ? STATE.newPriceList : STATE.updatePriceList, rows: calculatePreview().map((row) => ({ item_code: row.code, final_price: row.finalPrice })) };
        if (navigator.clipboard) navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    }

    function removeWorkingItem(code) {
        STATE.workingItems = STATE.workingItems.filter((itemCode) => itemCode !== code);
        STATE.addItemSelection = STATE.addItemSelection.filter((itemCode) => itemCode !== code);
        STATE.workingSelection = STATE.workingSelection.filter((itemCode) => itemCode !== code);
    }

    function visibleArticles() {
        return STATE.itemOptions || [];
    }

    function articleSearchText(item) {
        return `${item.code} ${item.name} ${item.brand} ${item.category} ${item.itemGroup}`.toLowerCase();
    }

    function selectVisibleItems(checked) {
        const visibleCodes = visibleArticles().map((item) => item.code);
        if (checked) {
            STATE.addItemSelection = Array.from(new Set([...STATE.addItemSelection, ...visibleCodes]));
            STATE.message = __(`${visibleCodes.length} visible article(s) selected.`);
        } else {
            STATE.addItemSelection = STATE.addItemSelection.filter((code) => !visibleCodes.includes(code));
            STATE.message = __(`${visibleCodes.length} visible article(s) deselected.`);
        }
    }

    function applyItemSelection() {
        STATE.workingItems = STATE.addItemSelection.filter(Boolean);
        STATE.workingSelection = [...STATE.workingItems];
        STATE.itemDropdownOpen = false;
        STATE.message = __(`${STATE.workingItems.length} article(s) in the working list.`);
    }

    function togglePriceListSelection(name) {
        if (!name) return;
        if (STATE.selectedPriceLists.includes(name)) {
            STATE.selectedPriceLists = STATE.selectedPriceLists.filter((priceList) => priceList !== name);
        } else {
            STATE.selectedPriceLists.push(name);
        }
        STATE.sourcePriceList = STATE.selectedPriceLists[0] || name;
        if (!STATE.updatePriceList) STATE.updatePriceList = STATE.sourcePriceList;
    }

    function selectAllPriceLists(checked) {
        const names = getPriceListNames();
        if (checked) {
            STATE.selectedPriceLists = names;
            STATE.sourcePriceList = names[0] || "";
            if (!STATE.updatePriceList) STATE.updatePriceList = STATE.sourcePriceList;
            STATE.message = __(`${names.length} available buying price list(s) selected.`);
        } else {
            STATE.selectedPriceLists = [];
            STATE.message = __("Buying price list selection cleared.");
        }
    }

    function toggleWorkingSelection(code, checked) {
        if (checked && !STATE.workingSelection.includes(code)) {
            STATE.workingSelection.push(code);
        } else if (!checked) {
            STATE.workingSelection = STATE.workingSelection.filter((itemCode) => itemCode !== code);
        }
    }

    function applyFixedPct() {
        const targets = STATE.applyPctScope === "all" ? STATE.workingItems : STATE.workingSelection;
        const uniqueTargets = Array.from(new Set(targets)).filter((code) => STATE.workingItems.includes(code));
        if (!uniqueTargets.length) {
            STATE.message = __("Select at least one working-list row or choose All rows.");
            return;
        }
        uniqueTargets.forEach((code) => {
            delete STATE.manualPrices[code];
        });
        STATE.fixedPercent = { scope: STATE.applyPctScope === "all" ? "all" : "selected", item_codes: uniqueTargets, pct: Number(STATE.applyPct || 0) };
        STATE.message = __(`Fixed % applied to ${uniqueTargets.length} row(s).`);
    }

    async function createFormula(page) {
        const source = STATE.newFormula.source;
        const targets = normalizeNewFormulaTargets().filter((code) => code && code !== source);
        if (!source || !targets.length) {
            STATE.message = __("Choose one source item and at least one different target article.");
            return;
        }
        const targetRules = targets.map((code) => ({ code, pct: getFormulaTargetPct(code) }));
        const name = (STATE.newFormula.name || `${targets.length} target(s) from ${source}`).trim();
        const rule = await callBackend("save_formula_rule", { payload: JSON.stringify({
            docname: STATE.editingFormulaName,
            rule_name: name,
            targets: targetRules,
            source,
            checked: Boolean(STATE.newFormula.checked),
        }) });
        const normalized = normalizeRule(rule);
        const wasEditing = Boolean(STATE.editingFormulaName);
        const existingIndex = STATE.formulas.findIndex((row) => row.name === normalized.name || row.id === normalized.name);
        if (existingIndex >= 0) STATE.formulas.splice(existingIndex, 1, normalized);
        else STATE.formulas.unshift(normalized);
        resetFormulaBuilder(source);
        STATE.message = wasEditing ? __("Formula rule updated.") : __("Multi-article formula rule created.");
        await refreshPreview(page);
    }

    function editFormulaRule(index) {
        const rule = STATE.formulas[index];
        if (!rule) return;
        const targetRows = normalizeRuleTargetRows(rule);
        const targetPcts = {};
        targetRows.forEach((row) => {
            targetPcts[row.code] = row.pct;
        });
        STATE.editingFormulaName = rule.name || "";
        STATE.newFormula = {
            name: rule.ruleName || rule.rule_name || rule.label || "",
            source: rule.source || "",
            sourceQuery: "",
            sourceDropdownOpen: false,
            targets: targetRows.map((row) => row.code),
            targetPcts,
            targetQuery: "",
            targetDropdownOpen: false,
            pct: 0,
            checked: rule.checked !== false,
        };
        STATE.message = __("Editing formula rule.");
    }

    function deleteFormulaRule(page, index) {
        const rule = STATE.formulas[index];
        if (!rule) return;
        frappe.confirm(__("Delete formula rule {0}?").replace("{0}", rule.ruleName || rule.rule_name || rule.name || ""), async () => {
            await callBackend("delete_formula_rule", { name: rule.name });
            STATE.formulas.splice(index, 1);
            if (STATE.editingFormulaName === rule.name) resetFormulaBuilder();
            STATE.message = __("Formula rule deleted.");
            await refreshPreview(page);
        });
    }

    function resetFormulaBuilder(source) {
        STATE.editingFormulaName = "";
        STATE.newFormula = { name: "", source: source || STATE.newFormula.source || "", sourceQuery: "", sourceDropdownOpen: false, targets: [], targetPcts: {}, targetQuery: "", targetDropdownOpen: false, pct: 0, checked: true };
    }

    function normalizeRule(rule) {
        return { ...rule, ruleName: rule.rule_name || rule.ruleName || rule.label || rule.name || "Formula rule", targets: normalizeRuleTargetRows(rule) };
    }

    function normalizeRuleTargetRows(rule) {
        if (Array.isArray(rule.targets)) {
            return rule.targets.map((target) => typeof target === "string" ? { code: target, pct: Number(rule.pct || 0) } : { code: target.code, pct: Number(target.pct || 0) }).filter((target) => target.code);
        }
        return rule.target ? [{ code: rule.target, pct: Number(rule.pct || 0) }] : [];
    }

    function normalizeRuleTargets(rule) {
        return normalizeRuleTargetRows(rule).map((target) => target.code);
    }

    function formatRuleTargets(rule) {
        return normalizeRuleTargetRows(rule).map((target) => `${target.code} ${formatSignedPct(target.pct)}`).join(", ");
    }

    function normalizeNewFormula(formula) {
        const source = formula?.source || "";
        const targetRows = normalizeRuleTargetRows(formula || { targets: [], pct: formula?.pct || 0 });
        const targetPcts = { ...(formula?.targetPcts || {}) };
        targetRows.forEach((target) => {
            targetPcts[target.code] = Number(targetPcts[target.code] ?? target.pct ?? formula?.pct ?? 0);
        });
        return {
            name: formula?.name || formula?.label || "",
            source,
            sourceQuery: formula?.sourceQuery || "",
            sourceDropdownOpen: Boolean(formula?.sourceDropdownOpen),
            targets: targetRows.map((target) => target.code),
            targetPcts,
            targetQuery: formula?.targetQuery || "",
            targetDropdownOpen: Boolean(formula?.targetDropdownOpen),
            pct: Number(formula?.pct || 0),
            checked: formula?.checked !== false,
        };
    }

    function normalizeNewFormulaTargets() {
        STATE.newFormula.targets = Array.isArray(STATE.newFormula.targets) ? STATE.newFormula.targets : [];
        return STATE.newFormula.targets;
    }

    function visibleFormulaTargets() {
        return (STATE.formulaTargetOptions || []).filter((item) => item.code !== STATE.newFormula.source);
    }

    function visibleFormulaSources() {
        return STATE.formulaSourceOptions || [];
    }

    function formulaSourceLabel() {
        const source = articleByCode(STATE.newFormula.source);
        return source ? `${source.code} - ${source.name}` : __("No source selected");
    }

    function formulaTargetsLabel() {
        const targets = normalizeNewFormulaTargets();
        if (!targets.length) return __("No targets checked");
        if (targets.length === 1) return targets[0];
        return __(`${targets.length} targets checked`);
    }

    function toggleFormulaTarget(code, checked) {
        const targets = normalizeNewFormulaTargets();
        STATE.newFormula.targetPcts = STATE.newFormula.targetPcts || {};
        if (checked && !targets.includes(code)) {
            targets.push(code);
            STATE.newFormula.targetPcts[code] = getFormulaTargetPct(code);
        } else if (!checked) {
            STATE.newFormula.targets = targets.filter((targetCode) => targetCode !== code);
        }
    }

    function selectVisibleFormulaTargets(checked) {
        const visibleCodes = visibleFormulaTargets().map((item) => item.code);
        const targets = normalizeNewFormulaTargets();
        if (checked) {
            STATE.newFormula.targets = Array.from(new Set([...targets, ...visibleCodes]));
            STATE.newFormula.targetPcts = STATE.newFormula.targetPcts || {};
            visibleCodes.forEach((code) => {
                STATE.newFormula.targetPcts[code] = getFormulaTargetPct(code);
            });
            STATE.message = __(`${visibleCodes.length} visible target article(s) selected.`);
        } else {
            STATE.newFormula.targets = targets.filter((code) => !visibleCodes.includes(code));
            STATE.message = __(`${visibleCodes.length} visible target article(s) deselected.`);
        }
    }

    function getFormulaTargetPct(code) {
        STATE.newFormula.targetPcts = STATE.newFormula.targetPcts || {};
        return Number(STATE.newFormula.targetPcts[code] ?? STATE.newFormula.pct ?? 0);
    }

    function toggleItemSelection(code, checked) {
        if (checked && !STATE.addItemSelection.includes(code)) {
            STATE.addItemSelection.push(code);
        } else if (!checked) {
            STATE.addItemSelection = STATE.addItemSelection.filter((itemCode) => itemCode !== code);
        }
    }

    function selectedItemLabel() {
        if (!STATE.addItemSelection.length) return __("No items checked");
        if (STATE.addItemSelection.length === 1) return STATE.addItemSelection[0];
        return __(`${STATE.addItemSelection.length} items checked`);
    }

    function selectedPriceListsLabel() {
        if (!STATE.selectedPriceLists.length) return __("Select buying price list");
        if (STATE.selectedPriceLists.length === 1) return STATE.selectedPriceLists[0];
        return __(`${STATE.selectedPriceLists.length} price lists selected`);
    }

    function hasManualPrice(code) {
        return Object.prototype.hasOwnProperty.call(STATE.manualPrices, code);
    }

    function getManualPrice(code) {
        return hasManualPrice(code) ? Number(STATE.manualPrices[code] || 0) : "";
    }

    function articleByCode(code) {
        return STATE.itemMap[code] || null;
    }

    function getPriceListNames() {
        return (STATE.priceLists || []).map((row) => typeof row === "string" ? row : row.name).filter(Boolean);
    }

    function rememberItems(items) {
        (items || []).forEach((item) => {
            if (item.code) STATE.itemMap[item.code] = item;
        });
    }

    function normalizeItem(row) {
        return {
            code: row.item_code || row.code || row.name || "",
            name: row.item_name || row.name || row.item_code || row.code || "",
            brand: row.brand || "",
            category: row.category || "",
            itemGroup: row.item_group || row.itemGroup || "",
            uom: row.uom || row.stock_uom || "",
            listPrice: Number(row.list_price || row.listPrice || 0),
        };
    }

    function normalizePreviewRow(row) {
        const item = normalizeItem(row);
        return {
            ...item,
            listPrice: Number(row.list_price || 0),
            chosen: Number(row.chosen_price || row.chosen || 0),
            finalPrice: Number(row.final_price || 0),
            delta: Number(row.delta || 0),
            formulaLabel: row.formula_rule ? `${row.formula_rule}: ${row.formula_source || ""} ${formatSignedPct(row.formula_percent || 0)}` : "",
        };
    }

    function option(value, selected) {
        return `<option value="${escapeAttr(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(value)}</option>`;
    }

    function kpi(value, label) {
        return `<article><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></article>`;
    }

    function formatMoney(value) {
        return Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
    }

    function formatSignedPct(value) {
        const number = Number(value || 0);
        return `${number >= 0 ? "+" : ""}${number.toLocaleString(undefined, { maximumFractionDigits: 2 })}%`;
    }

    function roundMoney(value) {
        return Math.round(Number(value || 0) * 100) / 100;
    }

    function escapeHtml(value) {
        return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
    }

    function escapeAttr(value) {
        return escapeHtml(value);
    }

    function injectStyles() {
        if (document.getElementById("buying-price-builder-styles-v3")) return;
        const style = document.createElement("style");
        style.id = "buying-price-builder-styles-v3";
        style.textContent = `
            .bpb-root{background:#f6f8fb;min-height:100vh;color:#0f172a}.bpb-shell{--line:#d9e2ec;--muted:#64748b;--primary:#2563eb;--green:#047857;--red:#b91c1c;display:grid;gap:10px;padding:12px 14px 60px}.bpb-header{display:flex;align-items:center;justify-content:space-between;gap:12px;border:1px solid var(--line);border-radius:14px;background:#fff;padding:11px 13px;box-shadow:0 3px 12px rgba(15,23,42,.04)}.bpb-header span{color:var(--primary);font-size:10px;font-weight:900;text-transform:uppercase}.bpb-header h1{margin:2px 0 0;font-size:19px;letter-spacing:-.02em}.bpb-kpis{display:flex;gap:7px}.bpb-kpis article{min-width:76px;border:1px solid #e2e8f0;border-radius:10px;padding:6px 8px;background:#fff}.bpb-kpis strong{display:block;font-size:16px;line-height:1}.bpb-kpis span{display:block;margin-top:3px;color:#64748b;font-size:10px;text-transform:none}.bpb-workflow{display:grid;grid-template-columns:310px minmax(0,1fr);gap:10px}.bpb-card{border:1px solid var(--line);border-radius:14px;background:#fff;padding:11px;box-shadow:0 3px 12px rgba(15,23,42,.035)}.bpb-card-title{display:grid;gap:1px;margin-bottom:9px}.bpb-title-row{display:flex;align-items:center;justify-content:space-between;gap:10px}.bpb-card-title strong{font-size:14px}.bpb-card-title small{color:var(--muted);font-size:11px}.bpb-main{display:grid;gap:10px}.bpb-controls,.bpb-save-grid{display:grid;grid-template-columns:minmax(220px,1fr) 150px auto;gap:8px;align-items:end}.bpb-controls label,.bpb-save-grid label{display:grid;gap:4px;margin:0;color:#334155;font-size:11px;font-weight:800}.bpb-input,.bpb-controls select,.bpb-controls input,.bpb-table select,.bpb-price-input,.bpb-save-grid select{min-height:32px;border:1px solid #cbd5e1;border-radius:9px;background:#fff;padding:0 8px;font-size:12px;outline:0}.bpb-input:focus,.bpb-controls select:focus,.bpb-controls input:focus,.bpb-table select:focus,.bpb-price-input:focus,.bpb-save-grid select:focus{border-color:var(--primary);box-shadow:0 0 0 2px rgba(37,99,235,.12)}.bpb-btn{min-height:32px;border:1px solid transparent;border-radius:9px;padding:0 10px;font-size:11px;font-weight:850;cursor:pointer}.bpb-btn-primary{background:var(--primary);color:#fff}.bpb-btn-ghost{background:#fff;border-color:#cbd5e1;color:#1e293b}.bpb-full{width:100%;margin-top:8px}.bpb-pick-list{display:grid;gap:5px;max-height:480px;overflow:auto;margin-top:8px}.bpb-pick-row{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:7px;align-items:center;border:1px solid #e2e8f0;border-radius:10px;padding:7px;background:#fff;cursor:pointer}.bpb-pick-row strong{display:block;font-size:12px}.bpb-pick-row small{display:block;color:var(--muted);font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.bpb-pick-row em{font-style:normal;color:#1d4ed8;background:#eff6ff;border:1px solid #dbeafe;border-radius:999px;padding:2px 6px;font-size:10px;font-weight:800}.bpb-formula-drawer{padding:0}.bpb-formula-drawer summary{display:grid;grid-template-columns:auto auto minmax(0,1fr);gap:8px;align-items:center;padding:10px 11px;cursor:pointer}.bpb-formula-drawer summary span{border:1px solid #bfdbfe;background:#eff6ff;color:#1d4ed8;border-radius:999px;padding:2px 8px;font-size:10px;font-weight:900}.bpb-formula-drawer summary em{color:var(--muted);font-size:11px;font-style:normal}.bpb-formulas{display:grid;gap:5px;border-top:1px solid #e2e8f0;padding:8px 10px}.bpb-formula-row{display:grid;grid-template-columns:auto minmax(0,1fr);gap:8px;align-items:center;border:1px solid #e2e8f0;border-radius:10px;padding:7px}.bpb-formula-row strong{display:block;font-size:12px}.bpb-formula-row small{display:block;color:var(--muted);font-size:10px}.bpb-table-wrap{overflow:auto;border:1px solid #e2e8f0;border-radius:10px}.bpb-table{width:100%;min-width:930px;border-collapse:separate;border-spacing:0}.bpb-table th{background:#f8fafc;color:#475569;text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.05em;padding:7px;border-bottom:1px solid #e2e8f0}.bpb-table td{padding:7px;border-bottom:1px solid #edf2f7;vertical-align:middle;font-size:12px}.bpb-table tr:last-child td{border-bottom:0}.bpb-table td strong{display:block}.bpb-table td small{display:block;margin-top:1px;color:var(--muted);font-size:10px}.bpb-num{font-variant-numeric:tabular-nums}.bpb-price-input{width:110px}.bpb-formula-chip{display:inline-flex;border:1px solid #bbf7d0;background:#f0fdf4;color:#047857;border-radius:999px;padding:2px 7px;font-size:10px;font-weight:850}.bpb-muted{color:var(--muted)}.bpb-up{color:var(--green)!important}.bpb-down{color:var(--red)!important}.bpb-icon-btn{width:28px;height:28px;border:1px solid #fecaca;border-radius:8px;background:#fff;color:#b91c1c;font-size:16px;font-weight:900;cursor:pointer}.bpb-save-card{display:grid;gap:9px}.bpb-save-grid{grid-template-columns:190px minmax(220px,1fr) 160px minmax(220px,1fr)}.bpb-radio{display:flex!important;grid-auto-flow:column;align-items:center;gap:6px}.bpb-actions{display:flex;justify-content:flex-end;gap:7px}.bpb-toast{position:fixed;right:18px;bottom:18px;z-index:50;border:1px solid #bfdbfe;background:#eff6ff;color:#1d4ed8;border-radius:12px;padding:9px 11px;box-shadow:0 12px 30px rgba(15,23,42,.16);font-size:12px;font-weight:850}.bpb-empty,.bpb-empty-cell{text-align:center;color:var(--muted);padding:18px;background:#f8fafc}@media(max-width:1100px){.bpb-workflow{grid-template-columns:1fr}.bpb-controls,.bpb-save-grid{grid-template-columns:1fr 1fr}.bpb-picker{order:2}}@media(max-width:720px){.bpb-header{align-items:flex-start;flex-direction:column}.bpb-kpis{width:100%;display:grid;grid-template-columns:repeat(3,1fr)}.bpb-controls,.bpb-save-grid{grid-template-columns:1fr}.bpb-actions{justify-content:flex-start}.bpb-formula-drawer summary{grid-template-columns:1fr}.bpb-pick-list{max-height:260px}}
        `;
        style.textContent += `
            .bpb-workflow{grid-template-columns:1fr}.bpb-add-row{display:grid;grid-template-columns:minmax(260px,1fr) auto;gap:8px;align-items:end}@media(max-width:900px){.bpb-add-row{grid-template-columns:1fr}}
        `;
        style.textContent += `
            .bpb-tab-card{display:grid;gap:10px}.bpb-tab-bar{display:flex;gap:6px;border-bottom:1px solid #e2e8f0;padding-bottom:8px}.bpb-tab{min-height:32px;border:1px solid #cbd5e1;border-radius:999px;background:#fff;color:#334155;padding:0 12px;font-size:12px;font-weight:900;cursor:pointer}.bpb-tab.is-active{border-color:#2563eb;background:#eff6ff;color:#1d4ed8}.bpb-tab span{display:inline-flex;align-items:center;justify-content:center;min-width:18px;height:18px;margin-left:6px;border-radius:999px;background:#dbeafe;font-size:10px}
        `;
        style.textContent += `
            .bpb-check-dropdown{position:relative;min-width:0}.bpb-dropdown-button{display:flex;align-items:center;justify-content:space-between;gap:10px;width:100%;min-height:32px;border:1px solid #cbd5e1;border-radius:9px;background:#fff;padding:0 9px;color:#0f172a;text-align:left;cursor:pointer}.bpb-dropdown-button span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px;font-weight:900}.bpb-dropdown-button em{color:#64748b;font-size:10px;font-style:normal;font-weight:800}.bpb-dropdown-panel{display:none;position:absolute;left:0;right:0;top:calc(100% + 6px);z-index:30;border:1px solid #cbd5e1;border-radius:12px;background:#fff;padding:8px;box-shadow:0 18px 40px rgba(15,23,42,.18)}.bpb-check-dropdown.is-open .bpb-dropdown-panel{display:grid;gap:7px}.bpb-dropdown-panel-compact{min-width:260px;right:auto}.bpb-checkbox-list{display:grid;gap:6px;max-height:280px;overflow:auto}.bpb-checkbox-row{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:8px;align-items:center;border:1px solid #e2e8f0;border-radius:10px;padding:7px;margin:0;cursor:pointer}.bpb-checkbox-row strong{display:block;font-size:12px}.bpb-checkbox-row small{display:block;color:#64748b;font-size:10px}.bpb-checkbox-row em{color:#475569;font-size:10px;font-style:normal;font-weight:800}
        `;
        style.textContent += `
            .bpb-mini-actions,.bpb-title-actions{display:flex;flex-wrap:wrap;gap:6px}.bpb-link-btn{border:0;background:transparent;color:#2563eb;font-size:11px;font-weight:900;padding:2px 4px;cursor:pointer}.bpb-formula-builder{display:grid;grid-template-columns:minmax(180px,1.3fr) minmax(150px,1fr) minmax(150px,1fr) 90px auto auto;gap:8px;align-items:end;border:1px solid #e2e8f0;border-radius:12px;background:#f8fafc;padding:9px}.bpb-formula-builder label{display:grid;gap:4px;margin:0;color:#334155;font-size:11px;font-weight:800}.bpb-formula-builder select{min-height:32px;border:1px solid #cbd5e1;border-radius:9px;background:#fff;padding:0 8px;font-size:12px;outline:0}.bpb-pct-controls{grid-template-columns:minmax(180px,1fr) minmax(160px,220px) auto}.bpb-price-list-controls{grid-template-columns:minmax(260px,1fr) auto}@media(max-width:900px){.bpb-formula-builder,.bpb-pct-controls,.bpb-price-list-controls{grid-template-columns:1fr}.bpb-title-actions{width:100%}}
        `;
        style.textContent += `
            .bpb-formula-target-picker .bpb-checkbox-row{grid-template-columns:auto minmax(0,1fr) auto 82px}.bpb-target-pct{min-height:28px;border:1px solid #cbd5e1;border-radius:8px;padding:0 7px;font-size:12px;text-align:right}
        `;
        style.textContent += `
            .bpb-select-row{display:grid;grid-template-columns:22px minmax(0,1fr) auto;gap:10px;align-items:center;width:100%;min-height:44px;border:1px solid #e2e8f0;border-radius:12px;background:#fff;padding:9px 10px;color:#0f172a;text-align:left;cursor:pointer}.bpb-select-row:hover,.bpb-select-row.is-selected{border-color:#93c5fd;background:#eff6ff}.bpb-select-row strong{display:block;font-size:13px}.bpb-select-row small{display:block;color:#64748b;font-size:11px;line-height:1.35}.bpb-select-row em{color:#475569;font-size:10px;font-style:normal;font-weight:800}.bpb-select-check{display:grid;place-items:center;width:20px;height:20px;border:1px solid #bfdbfe;border-radius:6px;background:#fff;color:#2563eb;font-size:13px;font-weight:900}.bpb-select-row.is-selected .bpb-select-check{background:#2563eb;border-color:#2563eb;color:#fff}.bpb-price-list-row{grid-template-columns:22px minmax(0,1fr)}.bpb-formula-source-picker .bpb-dropdown-panel,.bpb-formula-target-picker .bpb-dropdown-panel-wide{width:min(920px,calc(100vw - 56px));right:auto}.bpb-formula-source-picker .bpb-checkbox-list,.bpb-formula-target-picker .bpb-checkbox-list{max-height:min(460px,58vh)}
        `;
        style.textContent += `
            .bpb-root{background:linear-gradient(180deg,#f8fafc 0%,#eef4fb 100%);min-height:100dvh}.bpb-shell{width:min(100%,1440px);margin:0 auto;padding:20px clamp(16px,2vw,28px) 72px;gap:16px}.bpb-main{gap:16px}.bpb-card{border-color:#dbe5ef;border-radius:18px;padding:16px;box-shadow:0 10px 28px rgba(15,23,42,.055)}.bpb-header{border-radius:20px;padding:18px 20px;box-shadow:0 12px 32px rgba(15,23,42,.065)}.bpb-header h1{font-size:clamp(22px,2.2vw,30px);line-height:1.12}.bpb-header span{font-size:11px;letter-spacing:.08em}.bpb-kpis{gap:10px}.bpb-kpis article{min-width:104px;border-radius:14px;padding:10px 12px}.bpb-kpis strong{font-size:20px}.bpb-kpis span{font-size:11px}.bpb-card-title{gap:4px;margin-bottom:12px}.bpb-card-title strong{font-size:15px}.bpb-card-title small{font-size:12px;line-height:1.45}.bpb-title-row{align-items:flex-start}.bpb-add-row{grid-template-columns:minmax(360px,1fr) minmax(148px,max-content);gap:10px}.bpb-controls,.bpb-price-list-controls,.bpb-pct-controls{gap:12px}.bpb-price-list-controls{grid-template-columns:minmax(360px,1fr) max-content}.bpb-pct-controls{grid-template-columns:minmax(240px,1fr) minmax(200px,260px) max-content}.bpb-save-grid{grid-template-columns:max-content minmax(260px,1fr) max-content minmax(240px,320px);gap:10px 12px}.bpb-btn,.bpb-dropdown-button,.bpb-input,.bpb-controls select,.bpb-controls input,.bpb-save-grid select,.bpb-formula-builder select{min-height:40px}.bpb-btn{padding:0 16px;border-radius:11px}.bpb-dropdown-button{border-radius:12px;padding:0 12px}.bpb-dropdown-button span{font-size:13px}.bpb-dropdown-button em{font-size:11px}.bpb-dropdown-panel{top:calc(100% + 8px);padding:12px;border-radius:16px;max-width:min(720px,calc(100vw - 48px))}.bpb-dropdown-panel-compact{min-width:min(360px,calc(100vw - 48px))}.bpb-checkbox-list{max-height:min(380px,52vh);gap:8px}.bpb-checkbox-row{min-height:44px;gap:10px;padding:9px 10px;border-radius:12px}.bpb-checkbox-row strong{font-size:13px}.bpb-checkbox-row small{font-size:11px;line-height:1.35}.bpb-mini-actions{justify-content:flex-end;padding:0 2px}.bpb-link-btn{min-height:28px;padding:0 8px;border-radius:8px}.bpb-link-btn:hover{background:#eff6ff}.bpb-tab-card{gap:14px}.bpb-tab-bar{gap:8px;padding-bottom:10px;overflow:auto}.bpb-tab{min-height:40px;padding:0 16px}.bpb-title-actions{justify-content:flex-end}.bpb-table-wrap{border:1px solid #e2e8f0;border-radius:14px;overflow:auto}.bpb-table{min-width:980px}.bpb-table th{height:40px}.bpb-table th,.bpb-table td{padding:10px 12px}.bpb-price-input{width:128px;min-height:36px}.bpb-icon-btn{width:34px;height:34px;border-radius:10px}.bpb-formula-builder{grid-template-columns:minmax(220px,1.2fr) minmax(180px,1fr) minmax(280px,1.4fr) minmax(110px,.5fr) max-content max-content;gap:12px;padding:12px;border-radius:14px}.bpb-formula-target-picker .bpb-checkbox-row{grid-template-columns:auto minmax(220px,1fr) minmax(64px,max-content) 96px}.bpb-target-pct{min-height:34px;border-radius:10px}.bpb-formula-row{min-height:48px;padding:10px 12px;border-radius:12px}.bpb-actions{gap:10px;margin-top:14px}.bpb-toast{right:24px;bottom:24px;border-radius:14px;padding:12px 16px}.bpb-empty,.bpb-empty-cell{padding:24px}@media(max-width:1100px){.bpb-save-grid,.bpb-formula-builder{grid-template-columns:1fr 1fr}.bpb-price-list-controls,.bpb-pct-controls{grid-template-columns:1fr auto}.bpb-title-row{display:grid}.bpb-title-actions{justify-content:flex-start}}@media(max-width:760px){.bpb-shell{padding:14px 10px 56px;gap:12px}.bpb-card{padding:12px;border-radius:14px}.bpb-header{padding:14px;border-radius:16px}.bpb-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));width:100%}.bpb-kpis article{min-width:0}.bpb-add-row,.bpb-price-list-controls,.bpb-pct-controls,.bpb-save-grid,.bpb-formula-builder{grid-template-columns:1fr}.bpb-dropdown-panel{position:fixed;left:12px;right:12px;top:auto;bottom:18px;max-width:none;max-height:72vh;overflow:auto}.bpb-formula-target-picker .bpb-checkbox-row{grid-template-columns:auto minmax(0,1fr) 72px}.bpb-formula-target-picker .bpb-checkbox-row em{display:none}.bpb-table{min-width:860px}.bpb-title-actions .bpb-btn{flex:1 1 auto}.bpb-actions{display:grid}.bpb-toast{left:12px;right:12px;bottom:12px}}
        `;
        style.textContent += `
            .bpb-formula-source-picker .bpb-dropdown-panel,.bpb-formula-target-picker .bpb-dropdown-panel-wide{width:min(920px,calc(100vw - 56px));max-width:min(920px,calc(100vw - 56px));right:auto}@media(max-width:760px){.bpb-formula-source-picker .bpb-dropdown-panel,.bpb-formula-target-picker .bpb-dropdown-panel-wide{width:auto;max-width:none;right:12px}}
        `;
        style.textContent += `
            .bpb-root{overflow-x:clip}.bpb-formula-source-picker,.bpb-formula-target-picker{position:relative;min-width:0}.bpb-formula-source-picker .bpb-dropdown-panel,.bpb-formula-target-picker .bpb-dropdown-panel-wide{width:min(680px,calc(100vw - 72px));max-width:min(680px,calc(100vw - 72px));left:0;right:auto;transform:none}.bpb-formula-target-picker .bpb-dropdown-panel-wide{left:auto;right:0}.bpb-formula-builder .bpb-radio{display:flex!important;align-items:center;justify-content:center;min-height:40px;margin:0;padding:0 12px;border:1px solid #cbd5e1;border-radius:11px;background:#fff;color:#334155;line-height:1.2}.bpb-formula-builder .bpb-radio input{margin:0 7px 0 0}.bpb-save-grid .bpb-radio{display:flex!important;align-items:center;min-height:40px;margin:0;padding:0 12px;border:1px solid #e2e8f0;border-radius:11px;background:#f8fafc;line-height:1.2}.bpb-save-grid .bpb-radio input{margin:0 8px 0 0}@media(max-width:1100px){.bpb-formula-source-picker .bpb-dropdown-panel,.bpb-formula-target-picker .bpb-dropdown-panel-wide{left:0;right:auto;width:min(620px,calc(100vw - 48px));max-width:min(620px,calc(100vw - 48px))}}@media(max-width:760px){.bpb-root{overflow-x:hidden}.bpb-formula-source-picker .bpb-dropdown-panel,.bpb-formula-target-picker .bpb-dropdown-panel-wide{left:12px;right:12px;width:auto;max-width:none;transform:none}.bpb-formula-builder .bpb-radio,.bpb-save-grid .bpb-radio{justify-content:flex-start}}
        `;
        style.textContent += `
            .bpb-formula-row{display:flex;align-items:center;justify-content:space-between;gap:12px}.bpb-formula-toggle{display:flex;align-items:center;gap:10px;min-width:0;margin:0;flex:1}.bpb-formula-toggle span{min-width:0}.bpb-row-actions{display:flex;align-items:center;gap:6px;flex-shrink:0}.bpb-danger-link{color:#b91c1c}.bpb-danger-link:hover{background:#fef2f2}@media(max-width:760px){.bpb-formula-row{align-items:stretch;flex-direction:column}.bpb-row-actions{justify-content:flex-end}}
        `;
        document.head.appendChild(style);
    }
})();
