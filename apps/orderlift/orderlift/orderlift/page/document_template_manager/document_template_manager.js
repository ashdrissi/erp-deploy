(function () {
    const STATE = { targets: [], templates: [], search: "", target: "All", status: "All" };

    frappe.pages["document-template-manager"].on_page_load = function (wrapper) {
        const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Document Templates"), single_column: true });
        wrapper.page = page;
        page.main.addClass("odtm-root");
        injectStyles();
        render(page);
        load(page);
    };

    frappe.pages["document-template-manager"].on_page_show = function (wrapper) {
        if (wrapper.page) load(wrapper.page);
    };

    async function load(page) {
        const res = await frappe.call({ method: "orderlift.document_templates.get_template_manager_bootstrap" });
        const message = res.message || {};
        STATE.targets = message.targets || [];
        STATE.templates = message.templates || [];
        render(page);
    }

    function render(page) {
        const rows = filteredTemplates();
        page.main.html(`
            <div class="odtm-shell">
                <nav class="odtm-breadcrumb" aria-label="${esc(__("Breadcrumb"))}">
                    <a href="/desk/home-page?sidebar=Main+Dashboard">${esc(__("Administration"))}</a>
                    <span>/</span>
                    <strong>${esc(__("Document Templates"))}</strong>
                </nav>
                <section class="odtm-hero">
                    <div>
                        <span>${esc(__("Annexed Documents"))}</span>
                        <h1>${esc(__("Document Templates"))}</h1>
                        <p>${esc(__("Manage reusable annex templates. Select target documents directly in the list, then open the builder for fields, statuses, and print settings."))}</p>
                    </div>
                    <button type="button" class="odtm-primary" data-new-template="1">${esc(__("New Template"))}</button>
                </section>
                <section class="odtm-toolbar">
                    <input type="search" data-search value="${esc(STATE.search)}" placeholder="${esc(__("Search templates"))}" />
                    <select data-target-filter><option value="All">${esc(__("All Documents"))}</option>${STATE.targets.map((target) => `<option value="${esc(target.doctype)}" ${STATE.target === target.doctype ? "selected" : ""}>${esc(__(target.label || target.doctype))}</option>`).join("")}</select>
                    <select data-status-filter><option value="All" ${STATE.status === "All" ? "selected" : ""}>${esc(__("All Statuses"))}</option><option value="Active" ${STATE.status === "Active" ? "selected" : ""}>${esc(__("Active"))}</option><option value="Inactive" ${STATE.status === "Inactive" ? "selected" : ""}>${esc(__("Inactive"))}</option></select>
                    <button type="button" class="odtm-secondary" data-refresh="1">${esc(__("Refresh"))}</button>
                </section>
                <section class="odtm-summary">
                    ${metric(STATE.templates.length, __("Templates"))}
                    ${metric(STATE.templates.filter((row) => row.is_active).length, __("Active"))}
                    ${metric(STATE.targets.length, __("Supported Documents"))}
                </section>
                <section class="odtm-list-card">
                    <div class="odtm-list-head">
                        <h2>${esc(__("Template List"))}</h2>
                        <span>${rows.length} ${esc(__("shown"))}</span>
                    </div>
                    ${rows.length ? tableMarkup(rows) : emptyMarkup()}
                </section>
            </div>
        `);
        bind(page);
    }

    function filteredTemplates() {
        const needle = String(STATE.search || "").trim().toLowerCase();
        return (STATE.templates || []).filter((template) => {
            if (needle && !String(template.template_name || "").toLowerCase().includes(needle)) return false;
            if (STATE.status === "Active" && !template.is_active) return false;
            if (STATE.status === "Inactive" && template.is_active) return false;
            if (STATE.target !== "All" && !(template.targets || []).some((target) => target.doctype === STATE.target)) return false;
            return true;
        });
    }

    function tableMarkup(rows) {
        return `
            <div class="odtm-table-wrap">
                <table class="odtm-table">
                    <thead><tr><th>${esc(__("Template"))}</th><th>${esc(__("Target Documents"))}</th><th>${esc(__("Fields"))}</th><th>${esc(__("Statuses"))}</th><th>${esc(__("State"))}</th><th></th></tr></thead>
                    <tbody>${rows.map(rowMarkup).join("")}</tbody>
                </table>
            </div>
        `;
    }

    function rowMarkup(template) {
        const selected = new Set((template.targets || []).map((target) => target.doctype));
        return `
            <tr>
                <td><strong>${esc(template.template_name)}</strong><small>${esc(template.name)}</small></td>
                <td>${targetChecks(template, selected)}</td>
                <td>${Number(template.field_count || 0)}</td>
                <td>${Number(template.status_count || 0)}</td>
                <td><span class="odtm-state ${template.is_active ? "green" : "gray"}">${esc(template.is_active ? __("Active") : __("Inactive"))}</span></td>
                <td class="right"><button type="button" class="odtm-secondary small" data-open-template="${esc(template.name)}">${esc(__("Open Builder"))}</button></td>
            </tr>
        `;
    }

    function targetChecks(template, selected) {
        return `<div class="odtm-target-checks" data-template-targets="${esc(template.name)}">${STATE.targets.map((target) => `<label class="${selected.has(target.doctype) ? "selected" : ""}"><input type="checkbox" data-template-target="${esc(template.name)}" value="${esc(target.doctype)}" ${selected.has(target.doctype) ? "checked" : ""}/><span>${esc(__(target.label || target.doctype))}</span></label>`).join("")}</div>`;
    }

    function emptyMarkup() {
        return `
            <div class="odtm-empty">
                <strong>${esc(__("No templates yet"))}</strong>
                <p>${esc(__("Create the first annexed document template, then assign it to Opportunity, Project, Quotation, Sales Order, or Shipment Plan."))}</p>
                <button type="button" class="odtm-primary" data-new-template="1">${esc(__("Create Template"))}</button>
            </div>
        `;
    }

    function metric(value, label) {
        return `<article><strong>${esc(value)}</strong><span>${esc(label)}</span></article>`;
    }

    function bind(page) {
        page.main.find("[data-new-template]").on("click", () => frappe.set_route("document-template-builder", "new"));
        page.main.find("[data-open-template]").on("click", function () { frappe.set_route("document-template-builder", $(this).data("open-template")); });
        page.main.find("[data-refresh]").on("click", () => load(page));
        page.main.find("[data-search]").on("change", function () { STATE.search = $(this).val(); render(page); });
        page.main.find("[data-target-filter]").on("change", function () { STATE.target = $(this).val(); render(page); });
        page.main.find("[data-status-filter]").on("change", function () { STATE.status = $(this).val(); render(page); });
        page.main.find("[data-template-target]").on("change", function () { updateTargets(page, $(this).data("template-target")); });
    }

    async function updateTargets(page, templateName) {
        const selected = page.main.find("[data-template-target]:checked").filter(function () { return $(this).data("template-target") === templateName; }).map(function () { return $(this).val(); }).get();
        try {
            const res = await frappe.call({ method: "orderlift.document_templates.update_template_targets", args: { name: templateName, targets: JSON.stringify(selected) }, freeze: true, freeze_message: __("Updating target documents...") });
            const message = res.message || {};
            STATE.targets = message.targets || STATE.targets;
            STATE.templates = message.templates || STATE.templates;
            frappe.show_alert({ message: __("Target documents updated"), indicator: "green" });
            render(page);
        } catch (error) {
            load(page);
        }
    }

    function esc(value) { return frappe.utils.escape_html(value == null ? "" : String(value)); }

    function injectStyles() {
        if (document.getElementById("odtm-style")) return;
        const style = document.createElement("style");
        style.id = "odtm-style";
        style.textContent = `
            .odtm-root{background:#f6f8fb;min-height:100vh}.odtm-shell{width:min(1360px,100%);margin:0 auto;padding:22px clamp(14px,2vw,28px) 64px;color:#172033}.odtm-breadcrumb{display:flex;align-items:center;gap:8px;margin-bottom:12px;color:#64748b;font-size:12px;font-weight:800}.odtm-breadcrumb a{color:#2563eb;text-decoration:none}.odtm-hero{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;padding:22px;border:1px solid #dbe5ef;border-radius:20px;background:linear-gradient(135deg,#fff 0%,#eef6ff 100%);box-shadow:0 12px 28px rgba(15,23,42,.06)}.odtm-hero span{display:inline-flex;margin-bottom:7px;color:#2563eb;font-size:11px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.odtm-hero h1{margin:0;font-size:clamp(26px,3vw,36px);letter-spacing:-.04em;line-height:1.04}.odtm-hero p{max-width:820px;margin:8px 0 0;color:#475569;font-size:14px;line-height:1.55}.odtm-primary,.odtm-secondary{min-height:38px;border-radius:11px;padding:0 14px;font-size:13px;font-weight:900;cursor:pointer}.odtm-primary{border:0;background:#2563eb;color:#fff;box-shadow:0 9px 18px rgba(37,99,235,.2)}.odtm-secondary{border:1px solid #bfdbfe;background:#eff6ff;color:#1d4ed8}.odtm-secondary.small{min-height:32px;border-radius:9px;font-size:12px;white-space:nowrap}.odtm-toolbar{display:grid;grid-template-columns:minmax(260px,1fr) 220px 170px auto;gap:10px;margin-top:14px}.odtm-toolbar input,.odtm-toolbar select{min-height:38px;border:1px solid #cbd5e1;border-radius:11px;background:#fff;padding:0 11px;font-size:13px}.odtm-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:12px}.odtm-summary article{border:1px solid #dbe5ef;border-radius:15px;background:#fff;padding:14px;box-shadow:0 8px 20px rgba(15,23,42,.04)}.odtm-summary strong{display:block;font-size:23px;line-height:1}.odtm-summary span{display:block;margin-top:5px;color:#64748b;font-size:12px;font-weight:800}.odtm-list-card{margin-top:14px;border:1px solid #dbe5ef;border-radius:18px;background:#fff;box-shadow:0 10px 26px rgba(15,23,42,.045);overflow:hidden}.odtm-list-head{display:flex;justify-content:space-between;align-items:center;padding:16px 18px;border-bottom:1px solid #e2e8f0}.odtm-list-head h2{margin:0;font-size:18px}.odtm-list-head span{color:#64748b;font-size:12px;font-weight:800}.odtm-table-wrap{overflow:auto}.odtm-table{width:100%;border-collapse:collapse}.odtm-table th{padding:11px 14px;background:#f8fafc;color:#475569;font-size:11px;text-align:left;text-transform:uppercase;letter-spacing:.06em}.odtm-table td{padding:13px 14px;border-top:1px solid #eef2f7;vertical-align:top}.odtm-table td strong{display:block;font-size:14px}.odtm-table td small{display:block;margin-top:4px;color:#64748b;font-size:11px}.odtm-table .right{text-align:right}.odtm-target-checks{display:flex;flex-wrap:wrap;gap:6px;max-width:560px}.odtm-target-checks label{display:inline-flex;align-items:center;gap:6px;min-height:28px;border:1px solid #dbe5ef;border-radius:999px;background:#f8fafc;padding:0 9px;color:#334155;font-size:12px;font-weight:800;cursor:pointer}.odtm-target-checks label.selected{border-color:#93c5fd;background:#eff6ff;color:#1d4ed8}.odtm-target-checks input{appearance:none;-webkit-appearance:none;display:grid;place-items:center;width:14px;height:14px;margin:0;border:1px solid #94a3b8;border-radius:4px;background:#fff}.odtm-target-checks input:checked{border-color:#2563eb;background:#2563eb}.odtm-target-checks input:checked:before{content:'\\2713';color:#fff;font-size:10px;font-weight:900;line-height:1}.odtm-state{display:inline-flex;align-items:center;min-height:24px;border-radius:999px;padding:0 9px;font-size:12px;font-weight:900}.odtm-state.green{background:#dcfce7;color:#166534}.odtm-state.gray{background:#e2e8f0;color:#475569}.odtm-empty{display:grid;justify-items:center;gap:8px;padding:42px 18px;text-align:center}.odtm-empty strong{font-size:18px}.odtm-empty p{max-width:540px;margin:0;color:#64748b}@media(max-width:920px){.odtm-toolbar,.odtm-summary{grid-template-columns:1fr}.odtm-hero{display:grid}.odtm-table{min-width:980px}}@media(max-width:640px){.odtm-shell{padding:14px 10px 48px}.odtm-hero{padding:18px}.odtm-primary,.odtm-secondary{width:100%}}
        `;
        document.head.appendChild(style);
    }
})();
