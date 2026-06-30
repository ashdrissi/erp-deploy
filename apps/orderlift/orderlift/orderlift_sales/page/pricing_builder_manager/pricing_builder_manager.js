(function () {
    const STATE = { builders: [], kpis: {}, search: "", loading: false, error: "", selectedBuilders: new Set() };
    let searchTimer = null;

    frappe.pages["pricing-builder-manager"].on_page_load = function (wrapper) {
        const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Selling Price List Builder"), single_column: true });
        wrapper.page = page;
        page.main.addClass("pbm-root");
        injectStyles();
        applyHeader(page);
        render(page);
        load(page);
    };

    frappe.pages["pricing-builder-manager"].on_page_show = function (wrapper) {
        if (!wrapper.page) return;
        applyHeader(wrapper.page);
        load(wrapper.page);
    };

    function applyHeader(page) {
        page.set_title(__("Selling Price List Builder"));
        page.set_primary_action(__("New Builder"), () => openBuilder(""));
    }

    async function load(page) {
        STATE.loading = true;
        STATE.error = "";
        render(page);
        try {
            const res = await frappe.call({
                method: "orderlift.orderlift_sales.page.pricing_builder_manager.pricing_builder_manager.get_pricing_builder_manager_data",
                args: { search: STATE.search },
            });
            const data = res.message || {};
            STATE.builders = data.builders || [];
            STATE.kpis = data.kpis || {};
            pruneSelectedBuilders();
        } catch (error) {
            console.error("Pricing Builder Manager failed", error);
            STATE.error = __("Unable to load Selling Price List Builders. Refresh and try again.");
            STATE.builders = [];
        } finally {
            STATE.loading = false;
            render(page);
        }
    }

    function render(page) {
        const kpis = STATE.kpis || {};
        page.main.html(`
            <div class="pbm-shell">
                <section class="pbm-hero">
                    <div><span>${__("Orderlift Pricing")}</span><h1>${__("Selling Price List Builder")}</h1><p>${__("Create or update static selling price lists from buying prices, expenses, customs, and margin policies.")}</p></div>
                    <div class="pbm-kpis">
                        ${kpi(__("Builders"), kpis.total_builders)}
                        ${kpi(__("This Month"), kpis.builders_this_month)}
                        ${kpi(__("Items"), kpis.total_items)}
                        ${kpi(__("Missing"), kpis.missing_items)}
                    </div>
                    <div class="pbm-actions"><button type="button" class="pbm-btn primary" data-new>${__("New")}</button><button type="button" class="pbm-btn ghost" data-refresh>${__("Refresh")}</button></div>
                </section>
                <section class="pbm-toolbar"><label><span>${__("Search")}</span><input id="pbm-search" type="search" value="${escapeHtml(STATE.search)}" placeholder="${escapeHtml(__("Builder or selling list"))}"></label><button type="button" class="pbm-btn ghost" data-select-all>${allVisibleSelected() ? __("Clear All") : __("Select All")}</button><button type="button" class="pbm-btn primary" data-recalculate-selected ${STATE.selectedBuilders.size ? "" : "disabled"}>${__("Recalculate")} ${STATE.selectedBuilders.size ? `(${STATE.selectedBuilders.size})` : ""}</button><button type="button" class="pbm-btn ghost" data-duplicate-selected ${STATE.selectedBuilders.size ? "" : "disabled"}>${__("Duplicate")} ${STATE.selectedBuilders.size ? `(${STATE.selectedBuilders.size})` : ""}</button><button type="button" class="pbm-btn danger" data-delete-selected ${STATE.selectedBuilders.size ? "" : "disabled"}>${__("Delete")} ${STATE.selectedBuilders.size ? `(${STATE.selectedBuilders.size})` : ""}</button><button type="button" class="pbm-btn ghost" data-reset>${__("Reset")}</button></section>
                ${STATE.error ? `<div class="pbm-error">${escapeHtml(STATE.error)}</div>` : ""}
                <section class="pbm-list">${STATE.loading ? skeleton(5) : STATE.builders.length ? STATE.builders.map(card).join("") : emptyState()}</section>
            </div>`);
        bind(page);
    }

    function bind(page) {
        page.main.find("[data-new]").on("click", () => openBuilder(""));
        page.main.find("[data-refresh]").on("click", () => load(page));
        page.main.find("[data-reset]").on("click", () => { STATE.search = ""; STATE.selectedBuilders.clear(); load(page); });
        page.main.find("[data-select-all]").on("click", () => {
            if (allVisibleSelected()) STATE.selectedBuilders.clear();
            else (STATE.builders || []).forEach((row) => STATE.selectedBuilders.add(row.name));
            render(page);
        });
        page.main.find("[data-select-builder]").on("change", function () {
            const name = $(this).attr("data-select-builder");
            if (!name) return;
            if (this.checked) STATE.selectedBuilders.add(name);
            else STATE.selectedBuilders.delete(name);
            render(page);
        });
        page.main.find("[data-delete-selected]").on("click", () => deleteBuilders(page, Array.from(STATE.selectedBuilders || [])));
        page.main.find("[data-recalculate-selected]").on("click", () => recalculateBuilders(page, Array.from(STATE.selectedBuilders || [])));
        page.main.find("[data-duplicate-selected]").on("click", () => duplicateSelectedBuilders(page));
        page.main.find("#pbm-search").on("input", function () {
            STATE.search = String($(this).val() || "").trim();
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => load(page), 220);
        });
        page.main.find("[data-open]").on("click", function () { openBuilder($(this).attr("data-open")); });
        page.main.find("[data-recalculate]").on("click", function () { recalculateBuilders(page, [$(this).attr("data-recalculate")]); });
        page.main.find("[data-duplicate]").on("click", function () { duplicateBuilder(page, $(this).attr("data-duplicate")); });
        page.main.find("[data-delete]").on("click", function () { deleteBuilders(page, [$(this).attr("data-delete")]); });
    }

    function card(row) {
        const selected = STATE.selectedBuilders.has(row.name);
        return `<article class="pbm-card ${selected ? "is-selected" : ""}">
            <div class="pbm-card-main"><label class="pbm-card-check" aria-label="${escapeHtml(__("Select Pricing Builder"))}"><input type="checkbox" data-select-builder="${escapeHtml(row.name)}" ${selected ? "checked" : ""}></label><div><span class="pbm-status ${row.missing_items ? "warn" : "ok"}">${row.missing_items ? __("Needs Review") : __("Ready")}</span><h3>${escapeHtml(row.builder_name || row.name)}</h3><p>${escapeHtml(row.selling_price_list_name || __("No selling list set"))}</p></div><div class="pbm-card-actions"><button type="button" class="pbm-btn primary" data-open="${escapeHtml(row.name)}">${__("Open")}</button><button type="button" class="pbm-btn ghost" data-recalculate="${escapeHtml(row.name)}">${__("Recalculate")}</button><button type="button" class="pbm-btn ghost" data-duplicate="${escapeHtml(row.name)}">${__("Duplicate")}</button><button type="button" class="pbm-btn danger" data-delete="${escapeHtml(row.name)}">${__("Delete")}</button></div></div>
            <div class="pbm-card-meta">${meta(__("Items"), row.total_items)}${meta(__("Ready"), row.ready_items)}${meta(__("Changed"), row.changed_items)}${meta(__("New"), row.new_items)}${meta(__("Missing"), row.missing_items)}${meta(__("Updated"), shortDate(row.modified))}</div>
            ${row.warnings ? `<div class="pbm-warning">${escapeHtml(String(row.warnings).split("\n")[0])}</div>` : ""}
        </article>`;
    }

    async function duplicateBuilder(page, name) {
        if (!name) return;
        const res = await frappe.call({
            method: "orderlift.orderlift_sales.page.pricing_builder_manager.pricing_builder_manager.duplicate_pricing_builder",
            args: { name },
            freeze: true,
            freeze_message: __("Duplicating Pricing Builder..."),
        });
        const builder = (res.message || {}).builder || {};
        frappe.show_alert({ message: __("Duplicated Pricing Builder {0}", [builder.name || ""]), indicator: "green" });
        load(page);
    }

    async function duplicateSelectedBuilders(page) {
        pruneSelectedBuilders();
        const names = Array.from(STATE.selectedBuilders || []);
        if (!names.length) return;
        frappe.confirm(__("Duplicate {0} selected Pricing Builder(s)?", [names.length]), async () => {
            let created = 0;
            for (const name of names) {
                await frappe.call({
                    method: "orderlift.orderlift_sales.page.pricing_builder_manager.pricing_builder_manager.duplicate_pricing_builder",
                    args: { name },
                    freeze: true,
                    freeze_message: __("Duplicating Pricing Builders..."),
                });
                created += 1;
            }
            STATE.selectedBuilders.clear();
            frappe.show_alert({ message: __("Duplicated {0} Pricing Builder(s)", [created]), indicator: "green" });
            load(page);
        });
    }

    async function recalculateBuilders(page, names) {
        names = (names || []).filter(Boolean);
        if (!names.length) return;
        frappe.confirm(__("Recalculate {0} Pricing Builder(s)?", [names.length]), async () => {
            const res = await frappe.call({
                method: "orderlift.orderlift_sales.page.pricing_builder_manager.pricing_builder_manager.recalculate_pricing_builders",
                args: { pricing_builders: JSON.stringify(names) },
                freeze: true,
                freeze_message: __("Recalculating Pricing Builders..."),
            });
            const out = res.message || {};
            STATE.selectedBuilders.clear();
            if ((out.errors || []).length) {
                frappe.msgprint({ title: __("Some Pricing Builders were not recalculated"), message: (out.errors || []).join("<br>"), indicator: "orange" });
            }
            frappe.show_alert({ message: __("Recalculated {0} Pricing Builder(s)", [(out.recalculated || []).length]), indicator: "green" });
            load(page);
        });
    }

    async function deleteBuilders(page, names) {
        names = (names || []).filter(Boolean);
        if (!names.length) return;
        frappe.confirm(__("Delete {0} Pricing Builder(s)? This cannot be undone.", [names.length]), async () => {
            const res = await frappe.call({
                method: "orderlift.orderlift_sales.page.pricing_builder_manager.pricing_builder_manager.delete_pricing_builders",
                args: { pricing_builders: JSON.stringify(names) },
                freeze: true,
                freeze_message: __("Deleting Pricing Builders..."),
            });
            const out = res.message || {};
            STATE.selectedBuilders.clear();
            if ((out.errors || []).length) {
                frappe.msgprint({ title: __("Some Pricing Builders were not deleted"), message: (out.errors || []).join("<br>"), indicator: "orange" });
            }
            frappe.show_alert({ message: __("Deleted {0} Pricing Builder(s)", [(out.deleted || []).length]), indicator: "green" });
            load(page);
        });
    }

    function allVisibleSelected() {
        const rows = STATE.builders || [];
        return Boolean(rows.length) && rows.every((row) => STATE.selectedBuilders.has(row.name));
    }

    function pruneSelectedBuilders() {
        const visible = new Set((STATE.builders || []).map((row) => row.name));
        Array.from(STATE.selectedBuilders || []).forEach((name) => {
            if (!visible.has(name)) STATE.selectedBuilders.delete(name);
        });
    }

    function openBuilder(name) { frappe.set_route("pricing-builder-builder", name || "new"); }
    function kpi(label, value) { return `<span class="pbm-kpi"><em>${escapeHtml(label)}</em><strong>${escapeHtml(value == null ? "-" : String(value))}</strong></span>`; }
    function meta(label, value) { return `<span><em>${escapeHtml(label)}</em><strong>${escapeHtml(value == null ? "-" : String(value))}</strong></span>`; }
    function skeleton(count) { return Array.from({ length: count }, () => `<div class="pbm-skeleton"></div>`).join(""); }
    function emptyState() { return `<div class="pbm-empty"><h3>${__("No builders found")}</h3><p>${__("Create a builder to publish static selling price lists.")}</p><button type="button" class="pbm-btn primary" data-new>${__("New Builder")}</button></div>`; }
    function shortDate(value) { return value ? String(value).slice(0, 10) : "-"; }
    function escapeHtml(value) { return frappe.utils.escape_html(String(value == null ? "" : value)); }

    function injectStyles() {
        if (document.getElementById("pbm-style")) return;
        const style = document.createElement("style");
        style.id = "pbm-style";
        style.textContent = `.pbm-root{background:#f6f8fb;color:#0f172a}.pbm-shell{max-width:1480px;margin:0 auto;padding:24px;display:grid;gap:16px}.pbm-hero,.pbm-toolbar,.pbm-card,.pbm-empty{border:1px solid #e2e8f0;border-radius:18px;background:#fff;box-shadow:0 4px 18px rgba(15,23,42,.05)}.pbm-hero{display:grid;grid-template-columns:1fr auto auto;gap:20px;align-items:center;padding:24px}.pbm-hero span{display:inline-block;border:1px solid #e0e7ff;border-radius:999px;background:#eef2ff;color:#3730a3;padding:4px 10px;font-size:11px;font-weight:700}.pbm-hero h1{margin:10px 0 4px;font-size:26px}.pbm-hero p{margin:0;color:#64748b}.pbm-kpis{display:grid;grid-template-columns:repeat(4,110px);gap:8px}.pbm-kpi,.pbm-card-meta span{display:grid;gap:4px;border:1px solid #edf2f7;border-radius:12px;background:#f8fafc;padding:10px}.pbm-kpi em,.pbm-card-meta em{font-style:normal;color:#64748b;font-size:10px;font-weight:800;text-transform:uppercase}.pbm-kpi strong,.pbm-card-meta strong{font-size:16px}.pbm-actions,.pbm-card-main{display:flex;gap:10px;align-items:center;justify-content:space-between}.pbm-btn{height:36px;border:1px solid transparent;border-radius:10px;padding:0 13px;font-weight:700}.pbm-btn.primary{background:#111827;color:#fff}.pbm-btn.ghost{background:#fff;border-color:#cbd5e1;color:#334155}.pbm-toolbar{display:grid;grid-template-columns:1fr auto;gap:10px;padding:14px}.pbm-toolbar label{display:grid;gap:5px;margin:0}.pbm-toolbar span{font-size:11px;font-weight:800;color:#64748b}.pbm-toolbar input{height:36px;border:1px solid #cbd5e1;border-radius:9px;padding:0 10px}.pbm-list{display:grid;gap:10px}.pbm-card{display:grid;gap:12px;padding:14px}.pbm-status{display:inline-flex;border-radius:999px;padding:3px 8px;font-size:11px;font-weight:800}.pbm-status.ok{background:#dcfce7;color:#166534}.pbm-status.warn{background:#ffedd5;color:#9a3412}.pbm-card h3{margin:5px 0 2px;font-size:16px}.pbm-card p{margin:0;color:#64748b}.pbm-card-meta{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px}.pbm-warning,.pbm-error{border:1px solid #fed7aa;background:#fff7ed;color:#9a3412;border-radius:12px;padding:10px}.pbm-empty{min-height:220px;display:grid;place-items:center;text-align:center;padding:28px}.pbm-skeleton{height:116px;border-radius:18px;background:linear-gradient(90deg,#eef2f7,#fff,#eef2f7);background-size:220% 100%;animation:pbm-shimmer 1.2s infinite}@keyframes pbm-shimmer{0%{background-position:120% 0}100%{background-position:-120% 0}}@media(max-width:980px){.pbm-hero,.pbm-toolbar{grid-template-columns:1fr}.pbm-kpis,.pbm-card-meta{grid-template-columns:repeat(2,minmax(0,1fr))}.pbm-actions{justify-content:flex-start}}`;
        style.textContent += `.pbm-toolbar{grid-template-columns:minmax(260px,1fr) auto auto auto auto auto;align-items:end}.pbm-btn.danger{background:#7f1d1d;color:#fff}.pbm-btn:disabled{opacity:.45;cursor:not-allowed}.pbm-card.is-selected{border-color:#a5b4fc;background:#eef2ff}.pbm-card-main{display:grid;grid-template-columns:34px minmax(0,1fr) auto;gap:10px;align-items:center}.pbm-card-actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.pbm-card-check{display:grid;place-items:center;width:30px;height:30px;border:1px solid #cbd5e1;border-radius:9px;background:#fff;margin:0}.pbm-card-check input{appearance:none;-webkit-appearance:none;display:inline-grid;place-content:center;width:18px;height:18px;margin:0;border:1.5px solid #94a3b8;border-radius:6px;background:#fff;cursor:pointer}.pbm-card-check input::after{content:"";width:9px;height:9px;transform:scale(0);background:#fff;clip-path:polygon(14% 44%,0 58%,38% 96%,100% 20%,86% 8%,36% 68%)}.pbm-card-check input:checked{border-color:#4f46e5;background:#4f46e5}.pbm-card-check input:checked::after{transform:scale(1)}@media(max-width:1100px){.pbm-toolbar{grid-template-columns:1fr}.pbm-card-main{grid-template-columns:34px minmax(0,1fr)}.pbm-card-actions{grid-column:2;justify-content:flex-start}}`;
        document.head.appendChild(style);
    }
})();
