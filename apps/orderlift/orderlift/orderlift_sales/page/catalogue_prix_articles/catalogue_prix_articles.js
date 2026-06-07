(function () {
    const PAGE_NAME = "catalogue-prix-articles";
    const API = "orderlift.orderlift_sales.page.catalogue_prix_articles.catalogue_prix_articles";
    const COLUMN_STORAGE_KEY = "orderlift.catalogue_prix_articles.columns.v2";
    const STATE_STORAGE_KEY = "orderlift.catalogue_prix_articles.state.v1";
    const PAGE_SIZES = [20, 50, 100, 200, 500];
    const DEFAULT_VISIBLE_COLUMNS = ["_select", "_row_number", "item_code", "image", "item_category", "item_group", "item_name", "brand", "uom", "stock_qty", "stock_available"];
    const STATE = {
        boot: {},
        priceLists: [],
        selectedPriceLists: [],
        rows: [],
        kpis: {},
        filters: { in_stock_only: false, show_missing_prices: true },
        selectedItems: [],
        tableSearch: "",
        columnFilters: {},
        columnWidths: {},
        visibleColumns: [],
        pagination: { page: 1, pageSize: 50 },
        sort: { key: "", direction: "asc" },
        priceListDropdownOpen: false,
        priceListSearch: "",
        columnConfigOpen: false,
        loading: false,
        error: "",
        message: "",
    };
    let currentPage = null;

    window.addEventListener("beforeunload", () => saveState());

    frappe.pages[PAGE_NAME].on_page_load = function (wrapper) {
        const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Catalogue Prix Articles"), single_column: true });
        wrapper.page = page;
        currentPage = page;
        page.main.addClass("cpa-root");
        injectStyles();
        readColumnConfig();
        readSavedState();
        applyHeader(page);
        render(page);
        loadBootstrap(page);
    };

    frappe.pages[PAGE_NAME].on_page_hide = function () {
        saveState();
    };

    frappe.pages[PAGE_NAME].on_page_show = function (wrapper) {
        if (!wrapper.page) return;
        currentPage = wrapper.page;
        applyHeader(wrapper.page);
        if (!STATE.priceLists.length) loadBootstrap(wrapper.page);
    };

    function applyHeader(page) {
        page.set_title(__("Catalogue Prix Articles"));
        page.set_primary_action(__("Générer PDF"), () => downloadPdf(), "file");
    }

    async function loadBootstrap(page) {
        STATE.loading = true;
        STATE.error = "";
        render(page);
        try {
            const res = await frappe.call({ method: `${API}.get_catalogue_bootstrap` });
            const boot = res.message || {};
            STATE.boot = boot;
            STATE.priceLists = boot.price_lists || [];
            if (hideStockQty()) STATE.filters.in_stock_only = false;
            normalizeSelectedPriceLists();
            if (!STATE.selectedPriceLists.length) {
                STATE.selectedPriceLists = STATE.priceLists.slice(0, 3).map((row) => row.name).filter(Boolean);
            }
            await loadRows(page);
        } catch (error) {
            console.error("Catalogue Prix Articles bootstrap failed", error);
            STATE.error = __("Impossible de charger le catalogue. Réessayez.");
        } finally {
            STATE.loading = false;
            render(page);
        }
    }

    async function loadRows(page) {
        if (!STATE.selectedPriceLists.length) {
            STATE.rows = [];
            STATE.kpis = {};
            STATE.message = STATE.boot.restricted_agent
                ? __("Aucune liste de prix de vente active n'est allouée à votre profil agent.")
                : __("Sélectionnez au moins une liste de prix de vente.");
            render(page);
            return;
        }
        if (hideStockQty()) STATE.filters.in_stock_only = false;
        STATE.loading = true;
        STATE.error = "";
        STATE.message = "";
        render(page);
        try {
            const res = await frappe.call({
                method: `${API}.get_catalogue_rows`,
                args: {
                    price_lists: JSON.stringify(STATE.selectedPriceLists),
                    filters: JSON.stringify(STATE.filters),
                },
            });
            const payload = res.message || {};
            STATE.rows = payload.rows || [];
            STATE.kpis = payload.kpis || {};
            pruneSelectedItems();
            saveState();
        } catch (error) {
            console.error("Catalogue Prix Articles load failed", error);
            STATE.error = error.message || __("Impossible de charger les articles du catalogue.");
        } finally {
            STATE.loading = false;
            render(page);
        }
    }

    function render(page, options = {}) {
        const kpis = STATE.kpis || {};
        page.main.html(`
            <div class="cpa-shell">
                <section class="cpa-hero">
                    <div><span>${esc(__("Orderlift Pricing"))}</span><h1>${esc(__("Catalogue Prix Articles"))}</h1><p>${esc(__("Générez un tableau d'articles avec images, catégories, marques, UOM, stock total et colonnes de prix dynamiques."))}</p></div>
                    <div class="cpa-kpis">
                        ${kpi(__("Articles"), kpis.items)}
                        ${kpi(__("Listes"), kpis.price_lists)}
                        ${kpi(__("En Stock"), kpis.in_stock)}
                        ${kpi(__("Sans Prix"), kpis.missing_price_rows)}
                    </div>
                    <div class="cpa-actions"><button type="button" class="cpa-btn primary" data-refresh>${esc(__("Actualiser"))}</button><button type="button" class="cpa-btn ghost" data-generate-pdf>${esc(__("Générer PDF"))}</button><button type="button" class="cpa-btn ghost" data-export>${esc(__("Exporter CSV"))}</button></div>
                </section>
                <section class="cpa-card">${selectionAndFilterPanel()}</section>
                ${STATE.error ? `<div class="cpa-error">${esc(STATE.error)}</div>` : ""}
                ${STATE.message ? `<div class="cpa-message">${esc(STATE.message)}</div>` : ""}
                <section class="cpa-card">${tablePanel()}</section>
            </div>
        `);
        bind(page);
        restoreFocus(options.focusSelector);
    }

    function selectionAndFilterPanel() {
        const help = STATE.boot.restricted_agent
            ? __("Vos articles sont limités aux listes de prix allouées dans vos règles agent.")
            : __("Choisissez les listes de prix de vente. Les filtres d'articles sont directement dans les colonnes du tableau.");
        return `<div class="cpa-card-head compact"><div><h2>${esc(__("Paramètres Catalogue"))}</h2><p>${esc(help)}</p></div><div class="cpa-inline-actions"><button type="button" class="cpa-btn ghost" data-reset>${esc(__("Réinitialiser"))}</button><button type="button" class="cpa-btn primary" data-refresh>${esc(__("Actualiser"))}</button></div></div>
            <div class="cpa-fields cpa-fields-price-only">
                <label class="cpa-price-list-field"><span>${esc(__("Listes de prix de vente"))}</span>${priceListDropdown()}</label>
                ${hideStockQty() ? "" : `<label class="cpa-check cpa-filter-check"><input type="checkbox" data-catalogue-filter="in_stock_only" ${STATE.filters.in_stock_only ? "checked" : ""}><span>${esc(__("Articles en stock seulement"))}</span></label>`}
                <label class="cpa-check cpa-filter-check"><input type="checkbox" data-catalogue-filter="with_price_only" ${STATE.filters.show_missing_prices === false ? "checked" : ""}><span>${esc(__("Articles avec prix seulement"))}</span></label>
            </div>`;
    }

    function priceListDropdown() {
        const rows = visiblePriceLists().map((row) => {
            const selected = STATE.selectedPriceLists.includes(row.name);
            return `<label class="cpa-dropdown-row ${selected ? "selected" : ""}"><input type="checkbox" data-price-list="${attr(row.name)}" ${selected ? "checked" : ""}><span><strong>${esc(row.name)}</strong><small>${esc(row.currency || "")}</small></span></label>`;
        }).join("") || `<div class="cpa-empty-mini">${esc(__("Aucune liste trouvée."))}</div>`;
        return `<div class="cpa-price-dropdown ${STATE.priceListDropdownOpen ? "open" : ""}">
            <button type="button" class="cpa-dropdown-button" data-toggle-price-list-dropdown><span>${esc(selectedPriceListLabel())}</span><em>${esc(__("Choisir"))}</em></button>
            <div class="cpa-dropdown-panel">
                <input type="search" data-price-list-search value="${attr(STATE.priceListSearch)}" placeholder="${attr(__("Filtrer les listes"))}">
                <div class="cpa-mini-actions"><button type="button" class="cpa-link-btn" data-select-visible-price-lists>${esc(__("Tout visible"))}</button><button type="button" class="cpa-link-btn" data-clear-price-lists>${esc(__("Vider"))}</button></div>
                <div class="cpa-dropdown-list">${rows}</div>
            </div>
        </div>`;
    }

    function visiblePriceLists() {
        const needle = String(STATE.priceListSearch || "").trim().toLowerCase();
        return (STATE.priceLists || []).filter((row) => !needle || String(row.name || "").toLowerCase().includes(needle));
    }

    function selectedPriceListLabel() {
        const selected = STATE.selectedPriceLists || [];
        if (!selected.length) return __("Aucune liste sélectionnée");
        if (selected.length === 1) return selected[0];
        return __("{0} listes sélectionnées", [selected.length]);
    }

    function tablePanel() {
        const columns = tableColumns();
        const rows = filteredRows();
        const pageRows = paginatedRows(rows);
        return `<div class="cpa-card-head"><div><h2>${esc(__("Tableau catalogue"))}</h2><p>${esc(__("Filtres compacts par colonne, tri, sélection, redimensionnement et configuration des colonnes."))}</p></div><div class="cpa-inline-actions"><span class="cpa-count">${esc(__("{0} de {1} ligne(s)", [rows.length, STATE.rows.length]))}</span><span class="cpa-count soft">${esc(__("{0} sélectionnée(s)", [selectedItemSet().size]))}</span></div></div>
            <div class="cpa-table-toolbar"><button type="button" class="cpa-btn ghost" data-clear-table-filters ${hasTableFilters() ? "" : "disabled"}>${esc(__("Effacer filtres"))}</button>${paginationControls(rows.length, pageRows)}</div>
            ${columnConfigurator(columns)}
            <div class="cpa-table-wrap"><table class="cpa-table" style="min-width:${tableMinWidth(columns)}px"><thead><tr>${columns.map((column) => headerCell(column, pageRows.rows)).join("")}</tr></thead><tbody>${tableRows(columns, pageRows.rows, pageRows.start)}</tbody></table></div>`;
    }

    function baseColumns() {
        const columns = [
            { key: "_select", label: "", width: 46, minWidth: 44, locked: true, noSort: true, noFilter: true, align: "center", render: (row) => `<input type="checkbox" class="cpa-row-check" data-select-item="${attr(row.item_code)}" ${isSelected(row.item_code) ? "checked" : ""} aria-label="${attr(__("Sélectionner {0}", [row.item_code || ""]))}">`, exportValue: (row) => isSelected(row.item_code) ? "1" : "" },
            { key: "_row_number", label: __("N°"), width: 58, minWidth: 50, locked: true, noSort: true, noFilter: true, align: "right", render: (_row, _column, rowNumber) => esc(rowNumber), exportValue: (_row, _column, rowNumber) => rowNumber },
            { key: "item_code", label: "CODE", width: 130, locked: true, render: (row) => `<button type="button" class="cpa-item-link" data-open-item="${attr(row.item_code)}">${esc(row.item_code || "-")}</button>` },
            { key: "image", label: __("Image"), width: 88, align: "center", noSort: true, noFilter: true, render: (row) => imageCell(row), exportValue: (row) => row.image || "" },
            { key: "item_category", label: __("Catégorie d'article"), width: 190, render: textCell("item_category") },
            { key: "item_group", label: __("Groupe d'item"), width: 210, render: textCell("item_group") },
            { key: "item_name", label: __("Nom d'Item"), width: 280, wrap: true, render: textCell("item_name") },
            { key: "brand", label: __("Marque"), width: 130, render: textCell("brand") },
            { key: "uom", label: __("UOM"), width: 90, render: textCell("uom") },
            { key: "stock_qty", label: __("Qté Stock Totale"), width: 140, align: "right", render: (row) => esc(formatQty(row.stock_qty)), sortValue: (row) => toNumber(row.stock_qty), exportValue: (row) => row.stock_qty },
            { key: "stock_available", label: __("Disponibilité Stock"), width: 160, align: "center", render: (row) => `<span class="cpa-pill ${row.stock_available === "OUI" ? "ok" : "bad"}">${esc(row.stock_available || "NON")}</span>` },
        ];
        return hideStockQty() ? columns.filter((column) => column.key !== "stock_qty") : columns;
    }

    function tableColumns() {
        const priceMeta = priceListMetaMap();
        const priceColumns = (STATE.selectedPriceLists || []).map((name) => ({
            key: `price:${name}`,
            label: name,
            priceList: name,
            currency: (priceMeta[name] || {}).currency || "",
            width: 150,
            locked: true,
            align: "right",
            render: (row, column) => {
                const value = (row.prices || {})[column.priceList];
                return value == null ? `<span class="cpa-muted">-</span>` : esc(money(value, column.currency));
            },
            sortValue: (row, column) => {
                const value = (row.prices || {})[column.priceList];
                return value == null ? -1 : toNumber(value);
            },
            exportValue: (row, column) => (row.prices || {})[column.priceList] == null ? "" : (row.prices || {})[column.priceList],
        }));
        const columns = [...baseColumns(), ...priceColumns];
        ensureColumnConfig(columns);
        const visible = new Set(STATE.visibleColumns || []);
        return columns.filter((column) => column.locked || visible.has(column.key));
    }

    function tableRows(columns, rows, start) {
        if (STATE.loading) return `<tr><td colspan="${columns.length}" class="cpa-empty-cell">${esc(__("Chargement du catalogue..."))}</td></tr>`;
        if (!rows.length) return `<tr><td colspan="${columns.length}" class="cpa-empty-cell">${esc(__("Aucun article trouvé pour cette sélection."))}</td></tr>`;
        return rows.map((row, index) => `<tr>${columns.map((column) => bodyCell(column, row, start + index + 1)).join("")}</tr>`).join("");
    }

    function headerCell(column, pageRows) {
        if (column.key === "_select") {
            const pageCodes = (pageRows || []).map((row) => row.item_code).filter(Boolean);
            const selected = selectedItemSet();
            const checked = pageCodes.length > 0 && pageCodes.every((code) => selected.has(code));
            const indeterminate = !checked && pageCodes.some((code) => selected.has(code));
            return `<th data-column="${attr(column.key)}" class="cpa-align-center cpa-select-head" style="${columnStyle(column)}"><input type="checkbox" data-select-page ${checked ? "checked" : ""} ${indeterminate ? "data-indeterminate=\"1\"" : ""} ${pageCodes.length ? "" : "disabled"} aria-label="${attr(__("Sélectionner les lignes visibles"))}"></th>`;
        }
        const sorted = STATE.sort.key === column.key;
        const direction = sorted && STATE.sort.direction === "desc" ? "desc" : "asc";
        const sortText = sorted ? (direction === "desc" ? "down" : "up") : "";
        const label = esc(column.label);
        const classes = [column.align === "right" ? "cpa-align-right" : "", column.align === "center" ? "cpa-align-center" : ""].filter(Boolean).join(" ");
        const labelHtml = column.noSort
            ? `<span class="cpa-sort-btn static"><span>${label}</span></span>`
            : `<button type="button" class="cpa-sort-btn" data-sort-column="${attr(column.key)}"><span>${label}</span><em>${esc(sortText)}</em></button>`;
        return `<th data-column="${attr(column.key)}" class="${classes}" style="${columnStyle(column)}"><div class="cpa-th-inner">${labelHtml}${filterControl(column)}</div><span class="cpa-column-resizer" data-resize-column="${attr(column.key)}"></span></th>`;
    }

    function filterControl(column) {
        if (column.noFilter) return `<span class="cpa-filter-spacer"></span>`;
        const value = (STATE.columnFilters || {})[column.key] || "";
        return `<input class="cpa-header-filter" type="search" data-column-filter="${attr(column.key)}" value="${attr(value)}" placeholder="${attr(__("Filtrer"))}" aria-label="${attr(__("Filtrer {0}", [column.label]))}">`;
    }

    function bodyCell(column, row, rowNumber) {
        const classes = [column.align === "right" ? "cpa-align-right cpa-num" : "", column.align === "center" ? "cpa-align-center" : "", column.wrap ? "cpa-wrap" : ""].filter(Boolean).join(" ");
        return `<td data-column="${attr(column.key)}" class="${classes}" style="${columnStyle(column)}">${column.render(row, column, rowNumber)}</td>`;
    }

    function filteredRows() {
        const columns = allColumnsForFiltering();
        const tableSearch = String(STATE.tableSearch || "").trim().toLowerCase();
        const columnFilters = activeColumnFilters();
        let rows = (STATE.rows || []).filter((row) => {
            if (tableSearch && !rowSearchText(row, columns).includes(tableSearch)) return false;
            for (const [key, value] of Object.entries(columnFilters)) {
                const column = columns.find((candidate) => candidate.key === key);
                if (!column) continue;
                if (!String(columnFilterValue(row, column)).toLowerCase().includes(String(value).toLowerCase())) return false;
            }
            return true;
        });
        rows = sortRows(rows, columns);
        return rows;
    }

    function paginatedRows(rows) {
        const pageSize = normalizePageSize(STATE.pagination.pageSize);
        const pageCount = Math.max(1, Math.ceil((rows || []).length / pageSize));
        const page = clampNumber(STATE.pagination.page || 1, 1, pageCount);
        STATE.pagination.page = page;
        STATE.pagination.pageSize = pageSize;
        const start = (page - 1) * pageSize;
        return { rows: (rows || []).slice(start, start + pageSize), page, pageSize, pageCount, start };
    }

    function paginationControls(total, pageRows) {
        const start = total ? pageRows.start + 1 : 0;
        const end = Math.min(total, pageRows.start + pageRows.rows.length);
        const options = PAGE_SIZES.map((size) => `<option value="${size}" ${size === pageRows.pageSize ? "selected" : ""}>${size}</option>`).join("");
        return `<div class="cpa-pagination"><label><span>${esc(__("Afficher"))}</span><select data-page-size>${options}</select></label><span class="cpa-page-range">${esc(__("{0}-{1} sur {2}", [start, end, total]))}</span><button type="button" class="cpa-page-btn" data-page-prev ${pageRows.page <= 1 ? "disabled" : ""}>${esc(__("Préc."))}</button><span class="cpa-page-number">${esc(__("Page {0}/{1}", [pageRows.page, pageRows.pageCount]))}</span><button type="button" class="cpa-page-btn" data-page-next ${pageRows.page >= pageRows.pageCount ? "disabled" : ""}>${esc(__("Suiv."))}</button></div>`;
    }

    function normalizePageSize(value) {
        const size = Number(value || 50);
        return PAGE_SIZES.includes(size) ? size : 50;
    }

    function sortRows(rows, columns) {
        const sort = STATE.sort || {};
        if (!sort.key) return rows;
        const column = columns.find((candidate) => candidate.key === sort.key);
        if (!column) return rows;
        const direction = sort.direction === "desc" ? -1 : 1;
        return rows.slice().sort((left, right) => compareValues(sortValue(left, column), sortValue(right, column)) * direction);
    }

    function allColumnsForFiltering() {
        const priceMeta = priceListMetaMap();
        return [...baseColumns(), ...(STATE.selectedPriceLists || []).map((name) => ({ key: `price:${name}`, priceList: name, currency: (priceMeta[name] || {}).currency || "" }))];
    }

    function hideStockQty() {
        return Boolean(STATE.boot?.restricted_agent || STATE.kpis?.hide_stock_qty);
    }

    function defaultVisibleColumns() {
        return DEFAULT_VISIBLE_COLUMNS.filter((key) => !hideStockQty() || key !== "stock_qty");
    }

    function rowSearchText(row, columns) {
        return columns.map((column) => columnFilterValue(row, column)).filter(Boolean).join(" ").toLowerCase();
    }

    function columnFilterValue(row, column) {
        if (column.key.startsWith("price:")) {
            const value = (row.prices || {})[column.priceList];
            return value == null ? "" : value;
        }
        if (column.key === "stock_qty") return formatQty(row.stock_qty);
        return row[column.key] == null ? "" : row[column.key];
    }

    function sortValue(row, column) {
        if (typeof column.sortValue === "function") return column.sortValue(row, column);
        return String(columnFilterValue(row, column)).toLowerCase();
    }

    function compareValues(left, right) {
        if (typeof left === "number" || typeof right === "number") return toNumber(left) - toNumber(right);
        return String(left || "").localeCompare(String(right || ""));
    }

    function columnConfigurator(columns) {
        const all = allColumnsForFiltering();
        const visible = new Set(STATE.visibleColumns || []);
        const checks = all.map((column) => {
            const locked = column.locked || column.key.startsWith("price:");
            const checked = locked || visible.has(column.key);
            return `<label class="${locked ? "locked" : ""}"><input type="checkbox" data-item-column="${attr(column.key)}" ${checked ? "checked" : ""} ${locked ? "disabled" : ""}><span>${esc(column.label || column.key.split(":", 2)[1] || column.key)}</span>${locked ? `<small>${esc(__("Requis"))}</small>` : ""}</label>`;
        }).join("");
        return `<details class="cpa-column-config" data-column-config ${STATE.columnConfigOpen ? "open" : ""}><summary><span>${esc(__("Colonnes"))}</span><em>${esc(__("{0} visibles", [columns.length]))}</em></summary><div class="cpa-column-panel"><div class="cpa-column-head"><strong>${esc(__("Configurer les colonnes"))}</strong><button type="button" class="cpa-btn ghost" data-reset-columns>${esc(__("Reset"))}</button></div><div class="cpa-column-list">${checks}</div></div></details>`;
    }

    function imageCell(row) {
        const image = String(row.image || "").trim();
        if (!image) return `<span class="cpa-no-image">${esc(__("Aucune"))}</span>`;
        return `<span class="cpa-image-frame"><img src="${attr(image)}" alt="${attr(row.item_name || row.item_code || __("Image article"))}" loading="lazy"></span>`;
    }

    function textCell(fieldname) {
        return (row) => esc(row[fieldname] || "");
    }

    function bind(page) {
        page.main.find("[data-refresh]").on("click", () => loadRows(page));
        page.main.find("[data-export]").on("click", () => exportCsv());
        page.main.find("[data-generate-pdf]").on("click", () => downloadPdf());
        page.main.find("[data-reset]").on("click", () => {
            STATE.filters = { in_stock_only: false, show_missing_prices: true };
            STATE.columnFilters = {};
            STATE.sort = { key: "", direction: "asc" };
            STATE.pagination.page = 1;
            STATE.selectedItems = [];
            STATE.selectedPriceLists = STATE.priceLists.slice(0, 3).map((row) => row.name).filter(Boolean);
            saveState();
            loadRows(page);
        });
        page.main.find("[data-toggle-price-list-dropdown]").on("click", () => { STATE.priceListDropdownOpen = !STATE.priceListDropdownOpen; render(page); });
        page.main.find("[data-price-list-search]").on("input", function () { STATE.priceListSearch = String($(this).val() || ""); render(page, { focusSelector: "[data-price-list-search]" }); });
        page.main.find("[data-select-visible-price-lists]").on("click", () => {
            const visible = visiblePriceLists().map((row) => row.name).filter(Boolean);
            STATE.selectedPriceLists = Array.from(new Set([...(STATE.selectedPriceLists || []), ...visible]));
            STATE.pagination.page = 1;
            saveState();
            loadRows(page);
        });
        page.main.find("[data-clear-price-lists]").on("click", () => { STATE.selectedPriceLists = []; STATE.pagination.page = 1; saveState(); loadRows(page); });
        page.main.find("[data-price-list]").on("change", function () {
            const name = $(this).attr("data-price-list");
            if (this.checked && !STATE.selectedPriceLists.includes(name)) STATE.selectedPriceLists.push(name);
            if (!this.checked) STATE.selectedPriceLists = STATE.selectedPriceLists.filter((value) => value !== name);
            STATE.pagination.page = 1;
            saveState();
            loadRows(page);
        });
        page.main.find("[data-catalogue-filter]").on("change", function () {
            const filter = $(this).attr("data-catalogue-filter");
            if (filter === "in_stock_only") STATE.filters.in_stock_only = this.checked;
            if (filter === "with_price_only") STATE.filters.show_missing_prices = !this.checked;
            STATE.pagination.page = 1;
            saveState();
            loadRows(page);
        });
        page.main.find("[data-column-filter]").on("input change", function () {
            applyColumnFilterInput(page, this);
        }).on("paste", function () {
            setTimeout(() => applyColumnFilterInput(page, this), 0);
        });
        page.main.find("[data-clear-table-filters]").on("click", () => { STATE.columnFilters = {}; STATE.pagination.page = 1; saveState(); render(page); });
        page.main.find("[data-sort-column]").on("click", function () { toggleSort($(this).attr("data-sort-column")); STATE.pagination.page = 1; saveState(); render(page); });
        page.main.find("[data-column-config]").on("toggle", function () { STATE.columnConfigOpen = this.open; });
        page.main.find("[data-item-column]").on("change", function () { toggleColumn($(this).attr("data-item-column"), this.checked); render(page); });
        page.main.find("[data-reset-columns]").on("click", () => { resetColumns(); render(page); });
        page.main.find("[data-resize-column]").on("mousedown", function (event) { startColumnResize(event, $(this).attr("data-resize-column")); });
        page.main.find("[data-page-size]").on("change", function () { STATE.pagination.pageSize = Number($(this).val() || 50); STATE.pagination.page = 1; saveState(); render(page); });
        page.main.find("[data-page-prev]").on("click", () => { STATE.pagination.page = Math.max(1, STATE.pagination.page - 1); saveState(); render(page); });
        page.main.find("[data-page-next]").on("click", () => { STATE.pagination.page += 1; saveState(); render(page); });
        page.main.find("[data-select-item]").on("change", function () { toggleSelectedItem($(this).attr("data-select-item"), this.checked); render(page); });
        page.main.find("[data-select-page]").each(function () { this.indeterminate = $(this).attr("data-indeterminate") === "1"; }).on("change", function () { togglePageSelection(paginatedRows(filteredRows()).rows, this.checked); render(page); });
        page.main.find("[data-open-item]").on("click", function () {
            const item = $(this).attr("data-open-item");
            if (item) frappe.set_route("Form", "Item", item);
        });
    }

    function priceListMetaMap() {
        const out = {};
        (STATE.priceLists || []).forEach((row) => { out[row.name] = row; });
        return out;
    }

    function applyColumnFilterInput(page, input) {
        const key = $(input).attr("data-column-filter");
        const value = String($(input).val() || "").trim();
        STATE.columnFilters = Object.assign({}, STATE.columnFilters || {});
        if (value) STATE.columnFilters[key] = value;
        else delete STATE.columnFilters[key];
        STATE.pagination.page = 1;
        saveState();
        render(page, { focusSelector: `[data-column-filter="${selectorAttr(key)}"]` });
    }

    function readSavedState() {
        try {
            const raw = localStorage.getItem(STATE_STORAGE_KEY);
            if (!raw) return;
            const saved = JSON.parse(raw) || {};
            if (Array.isArray(saved.selectedPriceLists)) STATE.selectedPriceLists = saved.selectedPriceLists.filter(Boolean);
            if (saved.filters && typeof saved.filters === "object") {
                STATE.filters = Object.assign({ in_stock_only: false, show_missing_prices: true }, saved.filters);
            }
            if (saved.columnFilters && typeof saved.columnFilters === "object") STATE.columnFilters = saved.columnFilters;
            if (saved.sort && typeof saved.sort === "object") STATE.sort = Object.assign({ key: "", direction: "asc" }, saved.sort);
            if (saved.pagination && typeof saved.pagination === "object") {
                STATE.pagination.pageSize = normalizePageSize(saved.pagination.pageSize);
                STATE.pagination.page = Math.max(1, Number(saved.pagination.page || 1));
            }
        } catch (error) {
            console.warn("Catalogue Prix Articles saved state ignored", error);
        }
    }

    function saveState() {
        try {
            localStorage.setItem(STATE_STORAGE_KEY, JSON.stringify({
                selectedPriceLists: STATE.selectedPriceLists || [],
                filters: STATE.filters || {},
                columnFilters: activeColumnFilters(),
                sort: STATE.sort || { key: "", direction: "asc" },
                pagination: { page: Math.max(1, Number(STATE.pagination.page || 1)), pageSize: normalizePageSize(STATE.pagination.pageSize) },
            }));
        } catch (error) {
            console.warn("Catalogue Prix Articles state was not saved", error);
        }
    }

    function normalizeSelectedPriceLists() {
        const available = new Set((STATE.priceLists || []).map((row) => row.name).filter(Boolean));
        STATE.selectedPriceLists = (STATE.selectedPriceLists || []).filter((name) => available.has(name));
    }

    function exportCsv() {
        const rows = filteredRows();
        if (!rows.length) {
            frappe.show_alert({ message: __("Aucune donnée à exporter."), indicator: "orange" });
            return;
        }
        const columns = tableColumns();
        const lines = [columns.map((column) => csvCell(column.label)).join(",")];
        rows.forEach((row, index) => lines.push(columns.map((column) => csvCell(exportValue(column, row, index + 1))).join(",")));
        const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = `catalogue-prix-articles-${frappe.datetime.get_today()}.csv`;
        link.click();
        URL.revokeObjectURL(link.href);
    }

    function downloadPdf() {
        if (!STATE.selectedPriceLists.length) {
            frappe.show_alert({ message: __("Sélectionnez au moins une liste de prix de vente."), indicator: "orange" });
            return;
        }
        saveState();
        const selected = selectedItemsInFilteredRows();
        if (!selected.length) {
            openPdf([]);
            return;
        }
        frappe.confirm(
            __("Générer le PDF avec les {0} ligne(s) sélectionnée(s) seulement ?", [selected.length]),
            () => openPdf(selected),
            () => openPdf([])
        );
    }

    function openPdf(itemCodes) {
        const params = new URLSearchParams();
        params.set("price_lists", JSON.stringify(STATE.selectedPriceLists));
        params.set("filters", JSON.stringify(STATE.filters));
        params.set("columns", JSON.stringify(tableColumns().map((column) => column.key)));
        params.set("table_search", STATE.tableSearch || "");
        params.set("column_filters", JSON.stringify(activeColumnFilters()));
        if (itemCodes.length) params.set("item_codes", JSON.stringify(itemCodes));
        window.open(`/api/method/${API}.download_catalogue_pdf?${params.toString()}`, "_blank");
    }

    function selectedItemsInFilteredRows() {
        const selected = selectedItemSet();
        return filteredRows().map((row) => row.item_code).filter((itemCode) => selected.has(itemCode));
    }

    function exportValue(column, row, rowNumber) {
        if (typeof column.exportValue === "function") return column.exportValue(row, column, rowNumber);
        return columnFilterValue(row, column);
    }

    function csvCell(value) {
        const text = String(value == null ? "" : value).replace(/"/g, '""');
        return /[",\n]/.test(text) ? `"${text}"` : text;
    }

    function toggleSort(key) {
        if (STATE.sort.key === key) {
            STATE.sort.direction = STATE.sort.direction === "asc" ? "desc" : "asc";
        } else {
            STATE.sort = { key, direction: "asc" };
        }
    }

    function activeColumnFilters() {
        const out = {};
        Object.entries(STATE.columnFilters || {}).forEach(([key, value]) => {
            const text = String(value || "").trim();
            if (text) out[key] = text;
        });
        return out;
    }

    function hasTableFilters() {
        return Object.keys(activeColumnFilters()).length > 0;
    }

    function selectedItemSet() {
        return new Set(STATE.selectedItems || []);
    }

    function isSelected(itemCode) {
        return selectedItemSet().has(itemCode);
    }

    function toggleSelectedItem(itemCode, checked) {
        if (!itemCode) return;
        const selected = selectedItemSet();
        if (checked) selected.add(itemCode);
        else selected.delete(itemCode);
        STATE.selectedItems = Array.from(selected);
    }

    function togglePageSelection(rows, checked) {
        const selected = selectedItemSet();
        (rows || []).forEach((row) => {
            if (!row.item_code) return;
            if (checked) selected.add(row.item_code);
            else selected.delete(row.item_code);
        });
        STATE.selectedItems = Array.from(selected);
    }

    function pruneSelectedItems() {
        const valid = new Set((STATE.rows || []).map((row) => row.item_code).filter(Boolean));
        STATE.selectedItems = (STATE.selectedItems || []).filter((itemCode) => valid.has(itemCode));
    }

    function ensureColumnConfig(columns) {
        if (!STATE.visibleColumns || !STATE.visibleColumns.length) readColumnConfig();
        const valid = new Set(columns.map((column) => column.key));
        STATE.visibleColumns = (STATE.visibleColumns || defaultVisibleColumns()).filter((key) => valid.has(key));
        if (hideStockQty()) STATE.visibleColumns = STATE.visibleColumns.filter((key) => key !== "stock_qty");
        if (!STATE.visibleColumns.length) STATE.visibleColumns = defaultVisibleColumns().filter((key) => valid.has(key));
    }

    function readColumnConfig() {
        try {
            const raw = localStorage.getItem(COLUMN_STORAGE_KEY);
            const parsed = raw ? JSON.parse(raw) : {};
            STATE.visibleColumns = Array.isArray(parsed.visibleColumns) && parsed.visibleColumns.length ? parsed.visibleColumns : defaultVisibleColumns();
            STATE.columnWidths = parsed.columnWidths || {};
        } catch (error) {
            STATE.visibleColumns = defaultVisibleColumns();
            STATE.columnWidths = {};
        }
    }

    function saveColumnConfig() {
        localStorage.setItem(COLUMN_STORAGE_KEY, JSON.stringify({ visibleColumns: STATE.visibleColumns || [], columnWidths: STATE.columnWidths || {} }));
    }

    function toggleColumn(key, checked) {
        if (hideStockQty() && key === "stock_qty") return;
        const visible = new Set(STATE.visibleColumns || []);
        if (checked) visible.add(key);
        else visible.delete(key);
        STATE.visibleColumns = Array.from(visible);
        saveColumnConfig();
    }

    function resetColumns() {
        STATE.visibleColumns = defaultVisibleColumns();
        STATE.columnWidths = {};
        saveColumnConfig();
    }

    function columnWidth(column) {
        return clampNumber(STATE.columnWidths[column.key] || column.width || 130, column.minWidth || 70, 460);
    }

    function columnStyle(column) {
        const width = columnWidth(column);
        return `width:${width}px;min-width:${width}px`;
    }

    function tableMinWidth(columns) {
        return Math.max(760, (columns || []).reduce((total, column) => total + columnWidth(column), 0));
    }

    function startColumnResize(event, key) {
        event.preventDefault();
        const column = allColumnsForFiltering().find((candidate) => candidate.key === key);
        if (!column) return;
        const startX = event.clientX;
        const startWidth = columnWidth(column);
        document.body.classList.add("cpa-column-resizing");
        const move = (moveEvent) => {
            STATE.columnWidths[key] = clampNumber(startWidth + moveEvent.clientX - startX, 70, 460);
            const style = document.querySelector("style#cpa-live-widths") || document.createElement("style");
            style.id = "cpa-live-widths";
            style.textContent = `[data-column=\"${cssEscape(key)}\"]{width:${STATE.columnWidths[key]}px!important;min-width:${STATE.columnWidths[key]}px!important}`;
            if (!style.parentNode) document.head.appendChild(style);
        };
        const up = () => {
            document.removeEventListener("mousemove", move);
            document.removeEventListener("mouseup", up);
            document.body.classList.remove("cpa-column-resizing");
            const style = document.getElementById("cpa-live-widths");
            if (style) style.remove();
            saveColumnConfig();
            if (currentPage) render(currentPage);
        };
        document.addEventListener("mousemove", move);
        document.addEventListener("mouseup", up);
    }

    function kpi(label, value) { return `<span class="cpa-kpi"><em>${esc(label)}</em><strong>${esc(value == null ? "-" : String(value))}</strong></span>`; }
    function money(value, currency) { return `${toNumber(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}${currency ? ` ${currency}` : ""}`; }
    function formatQty(value) { return toNumber(value).toLocaleString(undefined, { maximumFractionDigits: 3 }); }
    function toNumber(value) { const num = Number(value || 0); return Number.isFinite(num) ? num : 0; }
    function clampNumber(value, min, max) { const num = Number(value || 0); return Number.isFinite(num) ? Math.max(min, Math.min(max, num)) : min; }
    function cssEscape(value) { return window.CSS && CSS.escape ? CSS.escape(String(value || "")) : String(value || "").replace(/"/g, "\\\""); }
    function selectorAttr(value) { return String(value || "").replace(/\\/g, "\\\\").replace(/"/g, "\\\""); }
    function esc(value) { return frappe.utils.escape_html(String(value == null ? "" : value)); }
    function attr(value) { return esc(value).replace(/`/g, "&#96;"); }

    function restoreFocus(selector) {
        if (!selector) return;
        requestAnimationFrame(() => {
            const element = document.querySelector(selector);
            if (!element) return;
            element.focus();
            if (typeof element.setSelectionRange === "function") {
                const end = String(element.value || "").length;
                element.setSelectionRange(end, end);
            }
        });
    }

    function injectStyles() {
        if (document.getElementById("cpa-style")) return;
        const style = document.createElement("style");
        style.id = "cpa-style";
        style.textContent = `
            .cpa-root{background:#f6f8fb;color:#0f172a}.cpa-root,.cpa-root *,.cpa-root *::before,.cpa-root *::after{box-sizing:border-box}.cpa-shell{width:100%;max-width:1540px;margin:0 auto;padding:22px 18px 72px;display:grid;gap:16px}.cpa-hero,.cpa-card{border:1px solid #e2e8f0;border-radius:18px;background:#fff;box-shadow:0 4px 18px rgba(15,23,42,.05)}.cpa-hero{display:grid;grid-template-columns:minmax(0,1fr) auto auto;align-items:center;gap:16px;padding:20px}.cpa-hero span{display:block;color:#2563eb;font-size:11px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.cpa-hero h1{margin:4px 0;font-size:24px}.cpa-hero p{margin:0;color:#64748b;line-height:1.5}.cpa-kpis{display:grid;grid-template-columns:repeat(4,minmax(88px,1fr));gap:8px}.cpa-kpi{display:grid;gap:4px;border:1px solid #edf2f7;border-radius:12px;background:#f8fafc;padding:10px 12px}.cpa-kpi em{font-style:normal;color:#64748b;font-size:10px;font-weight:900;text-transform:uppercase}.cpa-kpi strong{font-size:20px}.cpa-actions,.cpa-inline-actions,.cpa-mini-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.cpa-btn{min-height:34px;border:1px solid transparent;border-radius:10px;padding:0 12px;font-weight:900;cursor:pointer}.cpa-btn.primary{background:#111827;color:#fff}.cpa-btn.ghost{background:#fff;border-color:#cbd5e1;color:#334155}.cpa-btn:disabled{opacity:.45;cursor:not-allowed}.cpa-card{padding:16px;min-width:0}.cpa-card-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin-bottom:12px}.cpa-card h2{margin:0;font-size:16px}.cpa-card p{margin:3px 0 0;color:#64748b;line-height:1.45}.cpa-fields{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.cpa-fields label:not(.cpa-check){display:grid;gap:5px;margin:0}.cpa-fields span{font-size:11px;font-weight:900;color:#64748b;text-transform:uppercase}.cpa-fields input,.cpa-fields select,.cpa-table-toolbar input,.cpa-filter-cell input,.cpa-dropdown-panel input{width:100%;height:34px;border:1px solid #cbd5e1;border-radius:9px;background:#fff;padding:0 9px}.cpa-price-list-field{grid-column:span 2;min-width:0}.cpa-check{display:flex;align-items:center;gap:8px;min-height:34px;margin:0;border:1px solid #e2e8f0;border-radius:10px;background:#f8fafc;padding:0 10px}.cpa-root input[type='checkbox']{appearance:none!important;-webkit-appearance:none!important;display:inline-grid!important;place-content:center!important;width:18px!important;height:18px!important;min-width:18px!important;margin:0!important;border:1.5px solid #94a3b8!important;border-radius:6px!important;background:#fff!important;cursor:pointer}.cpa-root input[type='checkbox']::before{content:"";width:9px;height:9px;transform:scale(0);border-radius:3px;background:#2563eb}.cpa-root input[type='checkbox']:checked{border-color:#2563eb!important;background:#eff6ff!important}.cpa-root input[type='checkbox']:checked::before{transform:scale(1)}.cpa-price-dropdown{position:relative;min-width:0}.cpa-dropdown-button{width:100%;height:38px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:center;border:1px solid #cbd5e1;border-radius:10px;background:#fff;padding:0 11px;text-align:left;font-weight:900}.cpa-dropdown-button span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#0f172a;text-transform:none;font-size:13px}.cpa-dropdown-button em{font-style:normal;color:#2563eb;font-size:11px}.cpa-dropdown-panel{display:none;position:absolute;z-index:30;top:44px;left:0;width:min(520px,calc(100vw - 56px));max-height:430px;overflow:auto;border:1px solid #cbd5e1;border-radius:14px;background:#fff;box-shadow:0 18px 45px rgba(15,23,42,.18);padding:12px}.cpa-price-dropdown.open .cpa-dropdown-panel{display:grid;gap:9px}.cpa-dropdown-list{display:grid;gap:6px}.cpa-dropdown-row{display:grid;grid-template-columns:22px minmax(0,1fr);align-items:center;gap:9px;min-height:40px;margin:0;border:1px solid #e2e8f0;border-radius:10px;background:#fff;padding:7px 9px;cursor:pointer}.cpa-dropdown-row.selected{border-color:#93c5fd;background:#eff6ff}.cpa-dropdown-row strong,.cpa-dropdown-row small{display:block;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.cpa-dropdown-row small{color:#64748b;font-size:11px}.cpa-link-btn{border:0;background:transparent;color:#1d4ed8;font-weight:900;padding:0;cursor:pointer}.cpa-table-toolbar{display:grid;grid-template-columns:minmax(260px,1fr) auto;gap:8px;margin-bottom:10px}.cpa-column-config{position:relative;margin:0 0 10px}.cpa-column-config>summary{display:inline-flex;align-items:center;gap:8px;min-height:34px;border:1px solid #cbd5e1;border-radius:10px;background:#fff;color:#334155;padding:0 12px;font-weight:900;cursor:pointer;list-style:none}.cpa-column-config>summary::-webkit-details-marker{display:none}.cpa-column-config em{font-style:normal;color:#64748b;font-size:12px}.cpa-column-panel{position:absolute;z-index:25;top:42px;left:0;width:min(720px,calc(100vw - 48px));max-height:420px;overflow:auto;border:1px solid #cbd5e1;border-radius:14px;background:#fff;box-shadow:0 18px 45px rgba(15,23,42,.18);padding:14px}.cpa-column-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px}.cpa-column-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:8px}.cpa-column-list label{display:flex;align-items:center;gap:8px;min-height:36px;margin:0;border:1px solid #e2e8f0;border-radius:10px;background:#f8fafc;padding:7px 9px;font-weight:800;color:#334155}.cpa-column-list label.locked{background:#eef2ff;color:#3730a3}.cpa-column-list label span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.cpa-column-list label small{margin-left:auto;color:#64748b;font-size:10px;text-transform:uppercase}.cpa-table-wrap{overflow:auto;border:1px solid #e5e7eb;border-radius:13px;max-height:680px}.cpa-table{width:max-content;border-collapse:separate;border-spacing:0;table-layout:fixed}.cpa-table th{position:sticky;top:0;z-index:8;background:#f8fafc;color:#334155;font-size:11px;text-transform:uppercase;letter-spacing:.03em;box-shadow:0 1px 0 #e5e7eb}.cpa-column-filter-row th{top:36px;z-index:7;background:#fff}.cpa-table th,.cpa-table td{position:relative;padding:9px 10px;border-bottom:1px solid #edf2f7;text-align:left;white-space:nowrap;vertical-align:middle;overflow:hidden;text-overflow:ellipsis}.cpa-table td{font-size:12px}.cpa-table tr:hover td{background:#f8fafc}.cpa-sort-btn{display:flex;align-items:center;justify-content:space-between;gap:6px;width:100%;min-height:26px;border:0;background:transparent;color:inherit;font:inherit;font-weight:900;text-align:left;padding:0 14px 0 0;cursor:pointer}.cpa-sort-btn.static{cursor:default}.cpa-sort-btn em{min-width:24px;color:#64748b;font-style:normal;font-size:10px}.cpa-column-resizer{position:absolute;top:0;right:-3px;width:12px;height:100%;cursor:col-resize}.cpa-column-resizer::after{content:"";position:absolute;top:8px;bottom:8px;left:5px;width:2px;border-radius:99px;background:#cbd5e1}.cpa-column-resizer:hover::after,.cpa-column-resizing .cpa-column-resizer::after{background:#2563eb}.cpa-column-resizing{cursor:col-resize!important;user-select:none}.cpa-filter-cell input{height:28px;font-size:11px}.cpa-filter-cell span{color:#94a3b8;font-size:10px;font-weight:900;text-transform:uppercase}.cpa-image-cell,.cpa-align-center{text-align:center!important}.cpa-align-right{text-align:right!important}.cpa-wrap{white-space:normal!important}.cpa-image-cell img{width:48px;height:48px;object-fit:contain;border:1px solid #e2e8f0;border-radius:10px;background:#fff}.cpa-no-image{display:inline-flex;align-items:center;justify-content:center;width:48px;height:48px;border:1px dashed #cbd5e1;border-radius:10px;color:#94a3b8;font-size:10px;font-weight:900}.cpa-item-link{border:0;background:transparent;color:#1d4ed8;font-weight:900;text-decoration:underline;text-underline-offset:2px;padding:0;cursor:pointer}.cpa-num{font-variant-numeric:tabular-nums;font-weight:900}.cpa-muted{color:#94a3b8}.cpa-pill{display:inline-flex;align-items:center;justify-content:center;min-height:26px;border-radius:999px;padding:0 9px;font-size:11px;font-weight:900}.cpa-pill.ok{background:#dcfce7;color:#166534}.cpa-pill.bad{background:#fee2e2;color:#991b1b}.cpa-count{display:inline-flex;align-items:center;min-height:30px;border:1px solid #e2e8f0;border-radius:999px;background:#f8fafc;color:#475569;padding:0 10px;font-weight:900}.cpa-error,.cpa-message{border-radius:12px;padding:12px 14px;font-weight:800}.cpa-error{border:1px solid #fecaca;background:#fef2f2;color:#991b1b}.cpa-message{border:1px solid #bfdbfe;background:#eff6ff;color:#1d4ed8}.cpa-empty-cell,.cpa-empty-mini{text-align:center;color:#64748b;font-weight:800;padding:22px}.cpa-empty-mini{padding:14px}
            .cpa-card-head.compact{margin-bottom:10px}.cpa-fields.cpa-fields-price-only{grid-template-columns:minmax(280px,560px)}.cpa-table-toolbar{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:0 0 10px}.cpa-pagination{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-left:auto}.cpa-pagination label{display:flex;align-items:center;gap:6px;margin:0;color:#64748b;font-size:12px;font-weight:800}.cpa-pagination select{height:32px;border:1px solid #cbd5e1;border-radius:9px;background:#fff;padding:0 8px}.cpa-page-range,.cpa-page-number{color:#475569;font-size:12px;font-weight:800}.cpa-page-btn{height:32px;border:1px solid #cbd5e1;border-radius:9px;background:#fff;color:#334155;font-weight:900;padding:0 9px;cursor:pointer}.cpa-page-btn:disabled{opacity:.45;cursor:not-allowed}.cpa-count.soft{background:#eff6ff;color:#1d4ed8}.cpa-table th{vertical-align:top;padding:7px 8px}.cpa-table td{height:66px;vertical-align:middle}.cpa-th-inner{display:grid;gap:5px;align-content:start;min-height:54px}.cpa-sort-btn{min-height:18px;line-height:1.15}.cpa-header-filter{width:100%;height:28px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;padding:0 7px;font-size:11px;color:#0f172a}.cpa-header-filter:focus{border-color:#2563eb;box-shadow:0 0 0 2px rgba(37,99,235,.12);outline:none}.cpa-filter-spacer{display:block;height:28px}.cpa-select-head{vertical-align:middle!important}.cpa-select-head input,.cpa-row-check{width:16px;height:16px;margin:0;accent-color:#2563eb}.cpa-image-frame{width:58px;height:58px;margin:0 auto;border:1px solid #e2e8f0;border-radius:10px;background:#fff;display:flex;align-items:center;justify-content:center;overflow:hidden}.cpa-image-frame img{display:block;width:54px!important;height:54px!important;max-width:54px!important;max-height:54px!important;object-fit:contain}.cpa-no-image{display:flex;align-items:center;justify-content:center;width:58px;height:58px;margin:0 auto;border:1px dashed #cbd5e1;border-radius:10px;color:#94a3b8;font-size:10px;font-weight:800}.cpa-table tbody tr:has(.cpa-row-check:checked){background:#f8fbff}
            .cpa-fields.cpa-fields-price-only{grid-template-columns:minmax(280px,560px) max-content max-content;align-items:end}.cpa-filter-check{min-height:34px;align-self:end}
            @media(max-width:1100px){.cpa-hero{grid-template-columns:1fr}.cpa-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.cpa-fields{grid-template-columns:repeat(2,minmax(0,1fr))}.cpa-price-list-field{grid-column:span 2}}
            @media(max-width:640px){.cpa-shell{padding:14px 12px 72px}.cpa-fields,.cpa-table-toolbar{grid-template-columns:1fr}.cpa-price-list-field{grid-column:auto}.cpa-kpis{grid-template-columns:1fr}.cpa-card-head{display:grid}.cpa-actions,.cpa-inline-actions{align-items:stretch}.cpa-btn{width:100%}}
        `;
        document.head.appendChild(style);
    }
})();
