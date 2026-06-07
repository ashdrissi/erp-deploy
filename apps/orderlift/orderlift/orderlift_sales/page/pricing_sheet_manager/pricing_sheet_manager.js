(function () {
    const STATE = {
        sheets: [],
        kpis: {},
        filters: { customers: [], modes: [] },
        search: "",
        customer: "All",
        mode: "All",
        attention: "",
        loading: false,
        error: "",
        selectedSheets: new Set(),
        currentCompany: "",
    };

    const ATTENTION_LABELS = {
        missing_benchmark: __("Missing Benchmark Policy"),
        missing_customs: __("Missing Customs Policy"),
        warnings: __("Sheets With Warnings"),
    };

    let searchTimer = null;

    frappe.pages["pricing-sheet-manager"].on_page_load = function (wrapper) {
        const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Pricing Sheets"), single_column: true });
        wrapper.page = page;
        page.main.addClass("psm-root");
        injectStyles();
        applyHeader(page);
        syncAttentionFromUrl();
        render(page);
        load(page);
    };

    frappe.pages["pricing-sheet-manager"].on_page_show = function (wrapper) {
        if (!wrapper.page) return;
        applyHeader(wrapper.page);
        syncAttentionFromUrl();
        load(wrapper.page);
    };

    function applyHeader(page) {
        page.set_title(__("Pricing Sheets"));
        page.set_primary_action(__("New Pricing Sheet"), () => openBuilderForCreate());
        setTimeout(() => {
            if (!frappe.breadcrumbs) return;
            frappe.breadcrumbs.clear();
            frappe.breadcrumbs.append_breadcrumb_element("/app/pricing-dashboard", __("Pricing"), "title-text");
            frappe.breadcrumbs.append_breadcrumb_element("", __("Pricing Sheets"), "title-text");
            frappe.breadcrumbs.toggle(true);
        }, 0);
    }

    async function load(page) {
        STATE.loading = true;
        STATE.error = "";
        render(page);
        try {
            const res = await frappe.call({
                method: "orderlift.orderlift_sales.page.pricing_sheet_manager.pricing_sheet_manager.get_pricing_sheet_manager_data",
                args: { search: STATE.search, customer: STATE.customer, mode: STATE.mode, attention: STATE.attention },
            });
            const data = res.message || {};
            STATE.sheets = data.sheets || [];
            STATE.kpis = data.kpis || {};
            STATE.filters = data.filters || { customers: [], modes: [] };
            STATE.currentCompany = data.current_company || "";
            pruneSelectedSheets();
        } catch (error) {
            console.error("Pricing Sheet Manager failed", error);
            STATE.error = __("Unable to load Pricing Sheets. Refresh and try again.");
            STATE.sheets = [];
        } finally {
            STATE.loading = false;
            render(page);
        }
    }

    function render(page) {
        const kpis = STATE.kpis || {};
        page.main.html(`
            <div class="psm-shell">
                <nav class="psm-breadcrumb" aria-label="${__("Breadcrumb")}">
                    <a href="/desk/home-page?sidebar=Main+Dashboard">${__("Sales")}</a>
                    <span class="sep">/</span>
                    <span class="current">${__("Pricing Sheets")}</span>
                </nav>
                <section class="psm-hero">
                    <div class="psm-hero-copy">
                        <span>${__("Orderlift Pricing")}</span>
                        <h1>${__("Pricing Sheets")}</h1>
                        <p>${escapeHtml(STATE.currentCompany ? __("Filtered by company: {0}", [STATE.currentCompany]) : __("Create, open, and quote from the custom pricing workspace."))}</p>
                    </div>
                    <div class="psm-kpis">
                        ${kpi(__("Sheets"), kpis.total_sheets)}
                        ${kpi(__("This Month"), kpis.sheets_this_month)}
                        ${kpi(__("Total HT"), formatCurrency(kpis.total_selling))}
                        ${kpi(__("Warnings"), kpis.warning_sheets)}
                    </div>
                    <div class="psm-hero-actions">
                        <button type="button" class="psm-btn psm-btn-primary" data-new-sheet>${__("New")}</button>
                        <button type="button" class="psm-btn psm-btn-ghost" data-refresh>${__("Refresh")}</button>
                    </div>
                </section>
                <section class="psm-toolbar">
                    <label class="psm-wide"><span>${__("Search")}</span><input id="psm-search" type="search" value="${escapeHtml(STATE.search)}" placeholder="${escapeHtml(__("Sheet, customer, sales person"))}" /></label>
                    ${select("psm-customer", __("Customer"), STATE.customer, ["All"].concat(STATE.filters.customers || []))}
                    ${select("psm-mode", __("Mode"), STATE.mode, ["All"].concat(STATE.filters.modes || []))}
                    <label class="psm-select-all"><span>${__("Select")}</span><button type="button" class="psm-btn psm-btn-ghost" data-select-all-sheets>${allVisibleSelected() ? __("Clear All") : __("Select All")}</button></label>
                    <button type="button" class="psm-btn psm-btn-danger" data-delete-selected-sheets ${STATE.selectedSheets.size ? "" : "disabled"}>${__("Delete Selected")} ${STATE.selectedSheets.size ? `(${STATE.selectedSheets.size})` : ""}</button>
                    <button type="button" class="psm-btn psm-btn-ghost" data-reset>${__("Reset")}</button>
                </section>
                ${attentionFilter()}
                ${STATE.error ? `<div class="psm-error">${escapeHtml(STATE.error)}</div>` : ""}
                <section class="psm-list">
                    ${STATE.loading ? skeleton(6) : STATE.sheets.length ? STATE.sheets.map(card).join("") : emptyState()}
                </section>
            </div>
        `);
        bind(page);
    }

    function bind(page) {
        page.main.find("[data-new-sheet]").on("click", openBuilderForCreate);
        page.main.find("[data-refresh]").on("click", () => load(page));
        page.main.find("[data-reset]").on("click", () => {
            STATE.search = "";
            STATE.customer = "All";
            STATE.mode = "All";
            STATE.attention = "";
            STATE.selectedSheets.clear();
            clearAttentionParam();
            load(page);
        });
        page.main.find("[data-select-all-sheets]").on("click", () => {
            if (allVisibleSelected()) {
                STATE.selectedSheets.clear();
            } else {
                (STATE.sheets || []).forEach((row) => STATE.selectedSheets.add(row.name));
            }
            render(page);
        });
        page.main.find("[data-select-sheet]").on("change", function () {
            const name = $(this).attr("data-select-sheet");
            if (!name) return;
            if (this.checked) STATE.selectedSheets.add(name);
            else STATE.selectedSheets.delete(name);
            render(page);
        });
        page.main.find("[data-delete-selected-sheets]").on("click", () => deleteSelectedSheets(page));
        page.main.find("[data-clear-attention]").on("click", () => {
            STATE.attention = "";
            clearAttentionParam();
            load(page);
        });
        page.main.find("#psm-search").on("input", function () {
            STATE.search = String($(this).val() || "").trim();
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => load(page), 220);
        });
        page.main.find("#psm-customer").on("change", function () {
            STATE.customer = $(this).val() || "All";
            load(page);
        });
        page.main.find("#psm-mode").on("change", function () {
            STATE.mode = $(this).val() || "All";
            load(page);
        });
        page.main.find("[data-open-sheet]").on("click", function () {
            openBuilderForSheet($(this).attr("data-open-sheet"));
        });
        page.main.find("[data-generate-quote]").on("click", function () {
            generateQuotation(page, $(this).attr("data-generate-quote"));
        });
    }

    function card(row) {
        const warnings = Number(row.warning_count || 0);
        const mode = row.resolved_mode || "Draft";
        return `
            <article class="psm-card ${STATE.selectedSheets.has(row.name) ? "is-selected" : ""}">
                <div class="psm-card-main">
                    <label class="psm-card-check" aria-label="${escapeHtml(__("Select Pricing Sheet"))}"><input type="checkbox" data-select-sheet="${escapeHtml(row.name)}" ${STATE.selectedSheets.has(row.name) ? "checked" : ""}></label>
                    <div>
                        <span class="psm-status ${warnings ? "warn" : "ok"}">${warnings ? `${warnings} ${__("warning(s)")}` : __("Ready")}</span>
                        <h3>${escapeHtml(row.sheet_name || row.name)}</h3>
                        <p>${escapeHtml([row.custom_company, row.customer, row.sales_person, row.crm_business_type, row.crm_segment].filter(Boolean).join(" - ") || __("No commercial context yet"))}</p>
                    </div>
                    <div class="psm-card-actions">
                        <button type="button" class="psm-btn psm-btn-primary" data-open-sheet="${escapeHtml(row.name)}">${__("Open")}</button>
                        <button type="button" class="psm-btn psm-btn-ghost" data-generate-quote="${escapeHtml(row.name)}">${__("Quote")}</button>
                    </div>
                </div>
                <div class="psm-card-meta">
                    ${meta(__("Mode"), mode)}
                    ${meta(__("Lines"), row.line_count || 0)}
                    ${meta(__("Base"), formatCurrency(row.total_buy))}
                    ${meta(__("Margin"), `${Number(row.margin_pct || 0).toFixed(1)}%`)}
                    ${meta(__("Final HT"), formatCurrency(row.total_selling))}
                    ${meta(__("After Discount"), formatCurrency(row.discounted_total || row.total_selling))}
                    ${meta(__("Discount"), formatCurrency(row.discount_total))}
                    ${meta(__("Commission"), formatCurrency(row.commission_total))}
                    ${meta(__("Updated"), shortDate(row.modified))}
                </div>
                ${row.warnings ? `<div class="psm-warning">${escapeHtml(String(row.warnings).split("\n")[0])}</div>` : ""}
            </article>
        `;
    }

    async function generateQuotation(page, sheetName) {
        frappe.confirm(__("Generate a Quotation from this Pricing Sheet?"), async () => {
            const res = await frappe.call({
                method: "orderlift.orderlift_sales.page.pricing_sheet_manager.pricing_sheet_manager.generate_pricing_sheet_quotation",
                args: { pricing_sheet: sheetName },
                freeze: true,
            });
            const quotation = (res.message || {}).quotation;
            if (quotation) {
                frappe.show_alert({ message: __("Quotation {0} created", [quotation]), indicator: "green" });
                frappe.set_route("Form", "Quotation", quotation);
            } else {
                load(page);
            }
        });
    }

    async function deleteSelectedSheets(page) {
        pruneSelectedSheets();
        const names = Array.from(STATE.selectedSheets || []);
        if (!names.length) return;
        frappe.confirm(__("Delete {0} selected Pricing Sheet(s)? This cannot be undone.", [names.length]), async () => {
            try {
                const res = await frappe.call({
                    method: "orderlift.orderlift_sales.page.pricing_sheet_manager.pricing_sheet_manager.delete_pricing_sheets",
                    args: { pricing_sheets: JSON.stringify(names) },
                    freeze: true,
                });
                const out = res.message || {};
                STATE.selectedSheets.clear();
                if ((out.errors || []).length) {
                    frappe.msgprint({
                        title: __("Some Pricing Sheets were not deleted"),
                        message: (out.errors || []).join("<br>"),
                        indicator: "orange",
                    });
                }
                frappe.show_alert({ message: __("Deleted {0} Pricing Sheet(s)", [(out.deleted || []).length]), indicator: "green" });
                load(page);
            } catch (error) {
                frappe.msgprint({ title: __("Delete failed"), message: error.message || __("Unable to delete selected Pricing Sheets."), indicator: "red" });
            }
        });
    }

    function allVisibleSelected() {
        const rows = STATE.sheets || [];
        return Boolean(rows.length) && rows.every((row) => STATE.selectedSheets.has(row.name));
    }

    function pruneSelectedSheets() {
        const visible = new Set((STATE.sheets || []).map((row) => row.name));
        Array.from(STATE.selectedSheets || []).forEach((name) => {
            if (!visible.has(name)) STATE.selectedSheets.delete(name);
        });
    }

    function openBuilderForCreate() {
        frappe.route_options = { new_pricing_sheet: true };
        frappe.set_route("pricing-sheet-builder");
    }

    function openBuilderForSheet(name) {
        frappe.set_route("pricing-sheet-builder", name);
    }

    function syncAttentionFromUrl() {
        const params = new URLSearchParams(window.location.search || "");
        const attention = params.get("attention") || "";
        STATE.attention = ATTENTION_LABELS[attention] ? attention : "";
    }

    function clearAttentionParam() {
        const url = new URL(window.location.href);
        if (!url.searchParams.has("attention")) return;
        url.searchParams.delete("attention");
        window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
    }

    function attentionFilter() {
        if (!STATE.attention) return "";
        return `
            <div class="psm-attention">
                <span>${__("Filtered by")}</span>
                <strong>${escapeHtml(ATTENTION_LABELS[STATE.attention])}</strong>
                <button type="button" data-clear-attention>${__("Clear")}</button>
            </div>`;
    }

    function kpi(label, value) {
        return `<span class="psm-kpi"><em>${escapeHtml(label)}</em><strong>${escapeHtml(value == null ? "-" : String(value))}</strong></span>`;
    }

    function meta(label, value) {
        return `<span><em>${escapeHtml(label)}</em><strong>${escapeHtml(value == null ? "-" : String(value))}</strong></span>`;
    }

    function select(id, label, selected, options) {
        return `<label><span>${escapeHtml(label)}</span><select id="${id}">${(options || []).map((option) => `<option value="${escapeHtml(option)}" ${option === selected ? "selected" : ""}>${escapeHtml(__(option))}</option>`).join("")}</select></label>`;
    }

    function skeleton(count) {
        return Array.from({ length: count }, () => `<div class="psm-skeleton"></div>`).join("");
    }

    function emptyState() {
        return `<div class="psm-empty"><h3>${__("No Pricing Sheets found")}</h3><p>${__("Create a new sheet or reset filters to see existing work.")}</p><button type="button" class="psm-btn psm-btn-primary" data-new-sheet>${__("New Sheet")}</button></div>`;
    }

    function formatCurrency(value) {
        return textFromHtml(frappe.format(Number(value || 0), { fieldtype: "Currency" }));
    }

    function textFromHtml(value) {
        const wrapper = document.createElement("div");
        wrapper.innerHTML = String(value == null ? "" : value);
        return (wrapper.textContent || wrapper.innerText || "").trim();
    }

    function shortDate(value) {
        return value ? String(value).slice(0, 10) : "-";
    }

    function escapeHtml(value) {
        return frappe.utils.escape_html(String(value == null ? "" : value));
    }

    function injectStyles() {
        if (document.getElementById("psm-style")) return;
        const style = document.createElement("style");
        style.id = "psm-style";
        style.textContent = `
            @import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;450;500;600;700&family=Geist+Mono:wght@400;500&display=swap');
            .psm-root{--canvas:#FAFBFC;--canvas-2:#F4F6F8;--surface:#FFFFFF;--surface-2:#F7F8FA;--ink-1000:#0A0E1A;--ink-900:#11151F;--ink-700:#2E3548;--ink-600:#495061;--ink-500:#6B7280;--ink-400:#9099A6;--ink-300:#B8BFC9;--ink-200:#DDE1E7;--ink-150:#E8EBEF;--ink-100:#EFF1F4;--primary-700:#3730A3;--primary-600:#4F46E5;--primary-100:#E0E7FF;--primary-50:#EEF2FF;--success-700:#047857;--success-500:#10B981;--success-100:#D1FAE5;--success-50:#ECFDF5;--info-700:#0369A1;--info-100:#E0F2FE;--info-50:#F0F9FF;--rose-700:#BE123C;--rose-100:#FFE4E6;--rose-50:#FFF1F2;--accent-700:#6D28D9;--accent-600:#7C3AED;--accent-100:#EDE9FE;--accent-50:#F5F3FF;--font-sans:'Geist',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;--font-mono:'Geist Mono','SF Mono',Menlo,monospace;--r-lg:14px;--r-2xl:22px;--shadow-xs:0 1px 2px rgba(15,23,42,.04);--shadow-sm:0 1px 2px rgba(15,23,42,.04),0 2px 4px rgba(15,23,42,.04);--shadow-md:0 2px 4px rgba(15,23,42,.04),0 4px 12px rgba(15,23,42,.05);--ease:cubic-bezier(.32,.72,0,1);background:radial-gradient(circle at 20% 0%,rgba(99,102,241,.05) 0%,transparent 50%),radial-gradient(circle at 80% 30%,rgba(124,58,237,.03) 0%,transparent 50%),linear-gradient(to bottom,var(--canvas) 0%,var(--canvas-2) 100%);font-family:var(--font-sans);font-feature-settings:'cv11','ss01','ss03';-webkit-font-smoothing:antialiased;color:var(--ink-900)}.psm-root *{box-sizing:border-box}.psm-root button,.psm-root input,.psm-root select{font-family:inherit}.psm-shell{max-width:1520px;margin:0 auto;min-height:calc(100vh - 56px);padding:24px 24px 96px;color:var(--ink-900);display:grid;gap:18px}
            .psm-breadcrumb{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--ink-500);font-family:var(--font-mono)}.psm-breadcrumb a{color:var(--ink-500);text-decoration:none}.psm-breadcrumb a:hover{color:var(--ink-800)}.psm-breadcrumb .sep{color:var(--ink-300)}.psm-breadcrumb .current{color:var(--ink-800);font-weight:500}
            .psm-hero{position:relative;display:grid;grid-template-columns:1fr auto auto;gap:28px;align-items:center;border:1px solid var(--ink-150);border-radius:var(--r-2xl);background:var(--surface);color:var(--ink-1000);padding:28px 32px;box-shadow:var(--shadow-md);overflow:hidden}.psm-hero::before{content:'';position:absolute;top:0;right:0;width:60%;height:100%;background:radial-gradient(ellipse at top right,rgba(99,102,241,.06) 0%,transparent 60%);pointer-events:none}.psm-hero::after{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,rgba(99,102,241,.4) 30%,rgba(124,58,237,.4) 70%,transparent)}.psm-hero-copy,.psm-kpis,.psm-hero-actions{position:relative;z-index:1}.psm-hero-copy span{display:inline-flex;align-items:center;gap:8px;padding:5px 12px;background:var(--primary-50);border:1px solid var(--primary-100);border-radius:999px;font-size:11px;font-weight:500;color:var(--primary-700);margin-bottom:14px}.psm-hero-copy h1{margin:0 0 8px;font-size:28px;line-height:1.15;font-weight:600;letter-spacing:-.025em;color:var(--ink-1000)}.psm-hero-copy p{margin:0;color:var(--ink-500);font-size:14px;font-weight:400;line-height:1.55;max-width:640px}
            .psm-kpis{display:grid;grid-template-columns:repeat(4,minmax(112px,1fr));gap:12px}.psm-kpi{min-height:72px;display:flex;flex-direction:column;align-items:flex-start;justify-content:center;gap:2px;border:1px solid var(--ink-150);border-radius:var(--r-lg);background:var(--surface);padding:12px;box-shadow:var(--shadow-xs);transition:all .25s var(--ease)}.psm-kpi:hover{transform:translateY(-2px);box-shadow:var(--shadow-md)}.psm-kpi em{font-size:11px;font-style:normal;font-weight:500;color:var(--ink-500)}.psm-kpi strong{font-size:20px;font-weight:600;color:var(--ink-1000);line-height:1.1;font-feature-settings:'tnum'}
            .psm-hero-actions,.psm-card-actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.psm-btn{height:38px;border:1px solid transparent;border-radius:10px;padding:0 14px;font-size:13px;font-weight:500;cursor:pointer;transition:all .2s var(--ease);white-space:nowrap}.psm-btn:disabled{opacity:.55;cursor:not-allowed;transform:none!important}.psm-btn-primary{background:var(--ink-1000);color:#fff;box-shadow:var(--shadow-sm)}.psm-btn-primary:hover{background:var(--ink-800);transform:translateY(-1px)}.psm-btn-ghost{background:var(--surface);color:var(--ink-700);border-color:var(--ink-200)}.psm-btn-ghost:hover{background:var(--surface-2);color:var(--ink-900)}.psm-btn-danger{background:var(--rose-50);color:var(--rose-700);border-color:var(--rose-100)}.psm-btn-danger:hover{background:var(--rose-100);transform:translateY(-1px)}
            .psm-toolbar{display:grid;grid-template-columns:minmax(260px,1fr) 220px 160px 110px auto auto;gap:10px;align-items:end;border:1px solid var(--ink-150);border-radius:var(--r-lg);background:var(--surface);padding:14px;box-shadow:var(--shadow-sm)}.psm-toolbar label{display:grid;gap:6px;margin:0}.psm-toolbar label span{font-size:11px;font-weight:500;color:var(--ink-600)}.psm-toolbar input,.psm-toolbar select{min-height:38px;border:1px solid var(--ink-200);border-radius:8px;background:var(--surface);color:var(--ink-900);padding:0 11px;font-size:13px;font-weight:400;outline:none;transition:all .2s var(--ease)}.psm-toolbar input:focus,.psm-toolbar select:focus{border-color:var(--primary-600);box-shadow:0 0 0 3px rgba(99,102,241,.15)}.psm-select-all .psm-btn{width:100%}
            .psm-attention{display:flex;align-items:center;gap:8px;width:max-content;max-width:100%;border:1px solid var(--primary-100);background:var(--primary-50);border-radius:999px;padding:7px 10px;color:var(--primary-700);font-size:12px;font-weight:500}.psm-attention span{color:var(--ink-500)}.psm-attention strong{font-weight:600}.psm-attention button{border:0;background:transparent;color:var(--primary-700);font-size:12px;font-weight:600;cursor:pointer;padding:0}.psm-attention button:hover{text-decoration:underline}
            .psm-error{border:1px solid var(--rose-100);background:var(--rose-50);color:var(--rose-700);border-radius:12px;padding:12px 14px;font-size:13px;font-weight:500}.psm-list{display:grid;gap:12px}.psm-card{display:grid;gap:12px;border:1px solid var(--ink-150);border-radius:var(--r-lg);background:var(--surface);padding:14px;box-shadow:var(--shadow-sm);transition:all .25s var(--ease)}.psm-card:hover{transform:translateY(-2px);box-shadow:var(--shadow-md);border-color:var(--ink-200)}.psm-card-main{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:14px;align-items:start}.psm-status{display:inline-flex;align-items:center;gap:5px;margin-bottom:8px;border-radius:6px;padding:3px 8px;font-size:11px;font-weight:600;border:1px solid}.psm-status::before{content:'';width:5px;height:5px;border-radius:50%}.psm-status.ok{background:var(--success-50);color:var(--success-700);border-color:var(--success-100)}.psm-status.ok::before{background:var(--success-500)}.psm-status.warn{background:var(--rose-50);color:var(--rose-700);border-color:var(--rose-100)}.psm-status.warn::before{background:#E11D48}.psm-card h3{margin:0;color:var(--ink-1000);font-size:16px;font-weight:600;line-height:1.25}.psm-card p{margin:4px 0 0;color:var(--ink-500);font-size:12px;font-weight:400}.psm-card-meta{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}.psm-card-meta span{display:grid;gap:3px;border-radius:10px;background:var(--surface-2);border:1px solid var(--ink-100);padding:10px;color:var(--ink-500);font-size:10px;font-weight:500;text-transform:uppercase}.psm-card-meta strong{color:var(--ink-1000);font-size:14px;font-weight:600;text-transform:none;font-feature-settings:'tnum'}.psm-card-meta em{font-style:normal}.psm-warning{border:1px solid var(--rose-100);background:var(--rose-50);border-radius:10px;padding:10px 12px;color:var(--rose-700);font-weight:500;font-size:12px}.psm-empty{min-height:260px;display:grid;place-items:center;text-align:center;border:1px dashed var(--ink-200);border-radius:var(--r-2xl);background:var(--surface);padding:28px;color:var(--ink-500)}.psm-empty h3{margin:0;color:var(--ink-900);font-weight:600}.psm-empty p{margin:4px 0 12px}.psm-skeleton{min-height:126px;border-radius:var(--r-lg);background:linear-gradient(90deg,var(--ink-150) 0%,var(--surface) 45%,var(--ink-150) 90%);background-size:220% 100%;animation:psm-shimmer 1.1s linear infinite}@keyframes psm-shimmer{to{background-position:-220% 0}}
            .psm-shell{padding:14px 18px 72px;gap:10px}.psm-breadcrumb{font-size:11px}.psm-hero{padding:14px 18px;gap:16px;border-radius:16px;grid-template-columns:minmax(0,1fr) auto auto}.psm-hero-copy span{margin-bottom:6px;padding:3px 9px;font-size:10px}.psm-hero-copy h1{margin-bottom:3px;font-size:20px}.psm-hero-copy p{font-size:12px;line-height:1.35}.psm-kpis{gap:7px;grid-template-columns:repeat(4,minmax(86px,1fr))}.psm-kpi{min-height:50px;padding:8px 9px;border-radius:10px}.psm-kpi em{font-size:10px}.psm-kpi strong{font-size:15px}.psm-btn{height:32px;border-radius:8px;padding:0 10px;font-size:12px}.psm-toolbar{padding:9px;gap:8px;border-radius:12px;grid-template-columns:minmax(240px,1fr) 180px 135px auto}.psm-toolbar label{gap:4px}.psm-toolbar label span{font-size:10px}.psm-toolbar input,.psm-toolbar select{min-height:32px;border-radius:7px;font-size:12px}.psm-list{gap:7px}.psm-card{padding:9px 10px;border-radius:12px;gap:7px}.psm-card:hover{transform:none}.psm-card-main{grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:center}.psm-status{margin-bottom:4px;padding:2px 7px;font-size:10px}.psm-card h3{font-size:14px}.psm-card p{margin-top:2px;font-size:11px}.psm-card-actions{gap:6px}.psm-card-meta{grid-template-columns:repeat(9,minmax(0,1fr));gap:6px}.psm-card-meta span{padding:6px 8px;border-radius:8px;font-size:9px}.psm-card-meta strong{font-size:12px}.psm-warning{padding:7px 9px;font-size:11px}.psm-empty{min-height:180px}.psm-skeleton{min-height:84px;border-radius:12px}
            .psm-card.is-selected{border-color:var(--primary-100);background:var(--primary-50)}.psm-card-main{grid-template-columns:34px minmax(0,1fr) auto}.psm-card-check{display:grid;place-items:center;width:30px;height:30px;border:1px solid var(--ink-150);border-radius:9px;background:var(--surface);margin:0}.psm-card-check input{appearance:none;-webkit-appearance:none;display:inline-grid;place-content:center;width:18px;height:18px;margin:0;padding:0;border:1.5px solid var(--ink-300);border-radius:6px;background:var(--surface);cursor:pointer;transition:all .15s var(--ease)}.psm-card-check input::after{content:'';width:9px;height:9px;transform:scale(0);transition:transform .12s var(--ease);background:#fff;clip-path:polygon(14% 44%,0 58%,38% 96%,100% 20%,86% 8%,36% 68%)}.psm-card-check input:checked{border-color:var(--primary-600);background:var(--primary-600)}.psm-card-check input:checked::after{transform:scale(1)}.psm-card-check input:focus-visible{outline:3px solid rgba(99,102,241,.16);outline-offset:2px}.psm-toolbar{grid-template-columns:minmax(240px,1fr) 180px 135px 100px auto auto}
            @media(max-width:1280px){.psm-hero{grid-template-columns:1fr}.psm-hero-actions,.psm-card-actions{justify-content:flex-start}.psm-kpis{grid-template-columns:repeat(4,minmax(0,1fr))}}@media(max-width:900px){.psm-shell{padding:12px 12px 72px}.psm-hero,.psm-toolbar,.psm-card-main{grid-template-columns:1fr}.psm-kpis,.psm-card-meta{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:640px){.psm-kpis,.psm-card-meta{grid-template-columns:1fr}}
        `;
        document.head.appendChild(style);
    }
})();
