(function () {
    const STATE = { activeTab: "quotation", targets: [], annexes: [], quotationTemplates: [], allowedCompanies: [], search: "", target: "All", status: "All" };

    frappe.pages["document-template-manager"].on_page_load = function (wrapper) {
        const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Document Templates"), single_column: true });
        wrapper.page = page;
        page.main.addClass("odtm-root");
        hideFrappeHeader(wrapper);
        injectStyles();
        render(page);
        load(page);
    };

    frappe.pages["document-template-manager"].on_page_show = function (wrapper) {
        if (wrapper.page) load(wrapper.page);
    };

    async function load(page) {
        const [annexRes, quoteRes] = await Promise.all([
            frappe.call({ method: "orderlift.document_templates.get_template_manager_bootstrap" }),
            frappe.call({ method: "orderlift.quotation_detail_templates.get_quotation_template_manager_bootstrap" }),
        ]);
        const annex = annexRes.message || {};
        const quotation = quoteRes.message || {};
        STATE.targets = annex.targets || [];
        STATE.annexes = annex.templates || [];
        STATE.quotationTemplates = quotation.templates || [];
        STATE.allowedCompanies = quotation.allowed_companies || [];
        render(page);
    }

    function render(page) {
        const rows = filteredRows();
        const isQuotation = STATE.activeTab === "quotation";
        page.main.html(`
            <div class="odtm-shell">
                <nav class="odtm-breadcrumb"><a href="/desk/home-page?sidebar=Main+Dashboard">${icon("home")}</a>${icon("chevron")}<a href="/desk/home-page?sidebar=Main+Dashboard">${esc(__("Administration"))}</a>${icon("chevron")}<strong>${esc(__("Document Templates"))}</strong></nav>
                <section class="odtm-hero">
                    <div><span>${icon("file")}${esc(isQuotation ? __("Quotation Details") : __("Annexed Documents"))}</span><h1>${esc(__("Document Templates"))}</h1><p>${esc(isQuotation ? __("Build the dynamic proposal pages inserted into Quotation PDFs before the financial offer.") : __("Manage reusable annex templates filled from supported documents."))}</p></div>
                    <button type="button" class="odtm-primary" data-new-template="1">${icon("plus")}${esc(isQuotation ? __("New Quotation Template") : __("New Annex Template"))}</button>
                </section>
                <section class="odtm-tabs">
                    ${tabButton("quotation", __("Quotation Details"), STATE.quotationTemplates.length)}
                    ${tabButton("annexes", __("Annexes"), STATE.annexes.length)}
                </section>
                <section class="odtm-summary">
                    ${metric(isQuotation ? STATE.quotationTemplates.length : STATE.annexes.length, __("Templates"), "file", "blue")}
                    ${metric((isQuotation ? STATE.quotationTemplates : STATE.annexes).filter((row) => row.is_active).length, __("Active"), "check", "green")}
                    ${metric(isQuotation ? __("Inline PDF") : STATE.targets.length, isQuotation ? __("Output") : __("Supported Documents"), "grid", "purple")}
                </section>
                <section class="odtm-toolbar">
                    <div class="odtm-search">${icon("search")}<input type="search" data-search value="${esc(STATE.search)}" placeholder="${esc(__("Search templates"))}" /></div>
                    ${isQuotation ? companyFilter() : targetFilter()}
                    <select data-status-filter><option value="All" ${STATE.status === "All" ? "selected" : ""}>${esc(__("All Statuses"))}</option><option value="Active" ${STATE.status === "Active" ? "selected" : ""}>${esc(__("Active"))}</option><option value="Inactive" ${STATE.status === "Inactive" ? "selected" : ""}>${esc(__("Inactive"))}</option></select>
                    <button type="button" class="odtm-secondary odtm-refresh" data-refresh="1" title="${esc(__("Refresh"))}">${icon("refresh")}</button>
                </section>
                <section class="odtm-list-card"><div class="odtm-list-head"><h2>${esc(isQuotation ? __("Quotation Detail Templates") : __("Annex Templates"))}<span>${rows.length} ${esc(__("shown"))}</span></h2></div>${rows.length ? tableMarkup(rows, isQuotation) : emptyMarkup(isQuotation)}</section>
            </div>
        `);
        bind(page);
    }

    function hideFrappeHeader(wrapper) {
        $(wrapper).closest(".page-container").find(".page-head").hide();
    }

    function tabButton(key, label, count) {
        return `<button type="button" class="${STATE.activeTab === key ? "active" : ""}" data-tab="${esc(key)}"><strong>${esc(label)}</strong><span>${Number(count || 0)}</span></button>`;
    }

    function filteredRows() {
        const rows = STATE.activeTab === "quotation" ? STATE.quotationTemplates : STATE.annexes;
        const needle = String(STATE.search || "").trim().toLowerCase();
        return (rows || []).filter((template) => {
            if (needle && !String(template.template_name || "").toLowerCase().includes(needle)) return false;
            if (STATE.status === "Active" && !template.is_active) return false;
            if (STATE.status === "Inactive" && template.is_active) return false;
            if (STATE.activeTab === "quotation" && STATE.target !== "All" && (template.company || "") !== STATE.target) return false;
            if (STATE.activeTab === "annexes" && STATE.target !== "All" && !(template.targets || []).some((target) => target.doctype === STATE.target)) return false;
            return true;
        });
    }

    function companyFilter() {
        const companies = Array.from(new Set((STATE.quotationTemplates || []).map((row) => row.company).filter(Boolean))).sort();
        return `<select data-target-filter><option value="All">${esc(__("All Companies"))}</option>${companies.map((company) => `<option value="${esc(company)}" ${STATE.target === company ? "selected" : ""}>${esc(company)}</option>`).join("")}</select>`;
    }

    function targetFilter() {
        return `<select data-target-filter><option value="All">${esc(__("All Documents"))}</option>${STATE.targets.map((target) => `<option value="${esc(target.doctype)}" ${STATE.target === target.doctype ? "selected" : ""}>${esc(__(target.label || target.doctype))}</option>`).join("")}</select>`;
    }

    function tableMarkup(rows, isQuotation) {
        return `<div class="odtm-table-wrap"><table class="odtm-table"><colgroup><col class="odtm-col-template"><col class="odtm-col-company"><col class="odtm-col-count"><col class="odtm-col-state"><col class="odtm-col-actions"></colgroup><thead><tr><th>${esc(__("Template"))}</th><th>${esc(isQuotation ? __("Company") : __("Target Documents"))}</th><th>${esc(isQuotation ? __("Blocks") : __("Fields"))}</th><th>${esc(__("State"))}</th><th class="right">${esc(__("Actions"))}</th></tr></thead><tbody>${rows.map((row) => isQuotation ? quotationRow(row) : annexRow(row)).join("")}</tbody></table></div>`;
    }

    function quotationRow(template) {
        return `<tr><td><div class="odtm-template-cell"><span class="odtm-row-icon">${icon("file")}</span><div><strong>${esc(template.template_name)}</strong><small>${esc(template.description || template.name)}</small></div></div></td><td><span class="odtm-company">${icon("home")}${esc(template.company || __("All Companies"))}</span></td><td><span class="odtm-count-pill">${icon("grid")}${Number(template.block_count || 0)}</span></td><td><span class="odtm-state ${template.is_active ? "green" : "gray"}"><i></i>${esc(template.is_active ? __("Active") : __("Inactive"))}</span></td><td class="right"><div class="odtm-row-actions"><button type="button" class="odtm-secondary small odtm-action-open" data-open-quotation-template="${esc(template.name)}">${icon("edit")}${esc(__("Open Builder"))}</button><button type="button" class="odtm-secondary small" data-copy-quotation-template="${esc(template.name)}">${icon("copy")}${esc(__("Copy to Company"))}</button><button type="button" class="odtm-delete" data-delete-template="1" data-delete-quotation-template="${esc(template.name)}" aria-label="${esc(__("Delete"))}">${icon("trash")}</button></div></td></tr>`;
    }

    function annexRow(template) {
        const selected = new Set((template.targets || []).map((target) => target.doctype));
        return `<tr><td><div class="odtm-template-cell"><span class="odtm-row-icon">${icon("file")}</span><div><strong>${esc(template.template_name)}</strong><small>${esc(template.name)}</small></div></div></td><td>${targetChecks(template, selected)}</td><td><span class="odtm-count-pill">${icon("grid")}${Number(template.field_count || 0)}</span></td><td><span class="odtm-state ${template.is_active ? "green" : "gray"}"><i></i>${esc(template.is_active ? __("Active") : __("Inactive"))}</span></td><td class="right"><div class="odtm-row-actions"><button type="button" class="odtm-secondary small odtm-action-open" data-open-annex-template="${esc(template.name)}">${icon("edit")}${esc(__("Open Builder"))}</button><button type="button" class="odtm-delete" data-delete-template="1" data-delete-annex-template="${esc(template.name)}" aria-label="${esc(__("Delete"))}">${icon("trash")}</button></div></td></tr>`;
    }

    function targetChecks(template, selected) {
        return `<div class="odtm-target-checks" data-template-targets="${esc(template.name)}">${STATE.targets.map((target) => `<label class="${selected.has(target.doctype) ? "selected" : ""}"><input type="checkbox" data-template-target="${esc(template.name)}" value="${esc(target.doctype)}" ${selected.has(target.doctype) ? "checked" : ""}/><span>${esc(__(target.label || target.doctype))}</span></label>`).join("")}</div>`;
    }

    function emptyMarkup(isQuotation) {
        return `<div class="odtm-empty"><strong>${esc(__("No templates yet"))}</strong><p>${esc(isQuotation ? __("Create a quotation detail template to generate proposal pages before the financial quotation.") : __("Create the first annexed document template."))}</p><button type="button" class="odtm-primary" data-new-template="1">${esc(__("Create Template"))}</button></div>`;
    }

    function metric(value, label, iconName, tone) { return `<article><div class="odtm-metric-icon ${esc(tone || "blue")}">${icon(iconName)}</div><div><strong>${esc(value)}</strong><span>${esc(label)}</span></div></article>`; }

    function bind(page) {
        page.main.find("[data-tab]").on("click", function () { STATE.activeTab = $(this).data("tab"); STATE.target = "All"; render(page); });
        page.main.find("[data-new-template]").on("click", () => frappe.set_route(STATE.activeTab === "quotation" ? "quotation-detail-template-builder" : "document-template-builder", "new"));
        page.main.find("[data-open-quotation-template]").on("click", function () { frappe.set_route("quotation-detail-template-builder", $(this).data("open-quotation-template")); });
        page.main.find("[data-copy-quotation-template]").on("click", function () { openCopyQuotationDialog(page, $(this).data("copy-quotation-template")); });
        page.main.find("[data-open-annex-template]").on("click", function () { frappe.set_route("document-template-builder", $(this).data("open-annex-template")); });
        page.main.find("[data-delete-quotation-template]").on("click", function () { confirmDeleteQuotation(page, $(this).data("delete-quotation-template")); });
        page.main.find("[data-delete-annex-template]").on("click", function () { confirmDeleteAnnex(page, $(this).data("delete-annex-template")); });
        page.main.find("[data-refresh]").on("click", () => load(page));
        page.main.find("[data-search]").on("change", function () { STATE.search = $(this).val(); render(page); });
        page.main.find("[data-target-filter]").on("change", function () { STATE.target = $(this).val(); render(page); });
        page.main.find("[data-status-filter]").on("change", function () { STATE.status = $(this).val(); render(page); });
        page.main.find("[data-template-target]").on("change", function () { updateTargets(page, $(this).data("template-target")); });
    }

    function openCopyQuotationDialog(page, templateName) {
        const template = (STATE.quotationTemplates || []).find((row) => row.name === templateName);
        if (!template) return;
        const companies = (STATE.allowedCompanies || []).filter((company) => company && company !== (template.company || ""));
        if (!companies.length) {
            frappe.msgprint({ message: __("No other allowed company is available for this copy."), indicator: "orange" });
            return;
        }
        const defaultCompany = companies[0];
        const dialog = new frappe.ui.Dialog({
            title: __("Copy Quotation Template to Company"),
            fields: [
                { fieldtype: "HTML", options: `<div class="alert alert-info"><strong>${esc(template.template_name)}</strong><br>${esc(__("The copy keeps all blocks and sources, and is scoped to the selected company."))}</div>` },
                { fieldname: "company", fieldtype: "Select", label: __("Target Company"), options: companies.join("\n"), default: defaultCompany, reqd: 1 },
                { fieldname: "template_name", fieldtype: "Data", label: __("New Template Name"), default: `${template.template_name} - ${defaultCompany}`, description: __("Leave as-is or rename. If the name exists, a number is appended automatically.") },
            ],
            primary_action_label: __("Copy Template"),
            primary_action: async (values) => {
                const res = await frappe.call({
                    method: "orderlift.quotation_detail_templates.copy_quotation_template_to_company",
                    args: { name: template.name, company: values.company, template_name: values.template_name || "" },
                    freeze: true,
                    freeze_message: __("Copying template..."),
                });
                const message = res.message || {};
                STATE.quotationTemplates = message.templates || STATE.quotationTemplates;
                STATE.allowedCompanies = message.allowed_companies || STATE.allowedCompanies;
                dialog.hide();
                frappe.show_alert({ message: __("Template copied"), indicator: "green" });
                render(page);
            },
        });
        dialog.show();
        dialog.fields_dict.company.$input.on("change", function () {
            const company = $(this).val() || "";
            if (!dialog.get_value("template_name") || String(dialog.get_value("template_name")).startsWith(`${template.template_name} - `)) {
                dialog.set_value("template_name", `${template.template_name} - ${company}`);
            }
        });
    }

    async function updateTargets(page, templateName) {
        const selected = page.main.find("[data-template-target]:checked").filter(function () { return $(this).data("template-target") === templateName; }).map(function () { return $(this).val(); }).get();
        try {
            const res = await frappe.call({ method: "orderlift.document_templates.update_template_targets", args: { name: templateName, targets: JSON.stringify(selected) }, freeze: true });
            const message = res.message || {};
            STATE.targets = message.targets || STATE.targets;
            STATE.annexes = message.templates || STATE.annexes;
            frappe.show_alert({ message: __("Target documents updated"), indicator: "green" });
            render(page);
        } catch (error) { load(page); }
    }

    function confirmDeleteQuotation(page, templateName) {
        const template = (STATE.quotationTemplates || []).find((row) => row.name === templateName);
        if (!template) return;
        confirmDelete(template.template_name, __("This deletes only the reusable quotation detail template. Saved quotation snapshots remain frozen."), async () => {
            await frappe.call({ method: "orderlift.quotation_detail_templates.delete_quotation_template", args: { name: template.name }, freeze: true });
            frappe.show_alert({ message: __("Template deleted"), indicator: "green" });
            load(page);
        });
    }

    function confirmDeleteAnnex(page, templateName) {
        const template = (STATE.annexes || []).find((row) => row.name === templateName);
        if (!template) return;
        confirmDelete(template.template_name, __("This permanently deletes the template and every saved annex document created from it."), async () => {
            const res = await frappe.call({ method: "orderlift.document_templates.delete_template", args: { name: template.name }, freeze: true, freeze_message: __("Deleting template and saved annex documents...") });
            const annexCount = Number((res.message || {}).annex_count || 0);
            frappe.show_alert({ message: __("Template deleted ({0} annex documents removed)", [annexCount]), indicator: "green" });
            load(page);
        });
    }

    function confirmDelete(templateName, warning, onConfirm) {
        const dialog = new frappe.ui.Dialog({
            title: __("Permanently Delete Template"),
            fields: [{ fieldtype: "HTML", options: `<div class="alert alert-danger"><strong>${esc(__("This cannot be undone."))}</strong><br>${esc(warning)}</div>` }, { fieldname: "confirmation", fieldtype: "Data", label: __("Type the template name to confirm"), reqd: 1 }],
            primary_action_label: __("Permanently Delete"),
            primary_action: async (values) => {
                if (String(values.confirmation || "").trim() !== templateName) return frappe.msgprint({ message: __("The template name does not match."), indicator: "red" });
                await onConfirm();
                dialog.hide();
            },
        });
        dialog.show();
    }

    function esc(value) { return frappe.utils.escape_html(value == null ? "" : String(value)); }

    function icon(name) {
        const icons = {
            home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>',
            chevron: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="9 18 15 12 9 6"/></svg>',
            file: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
            plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>',
            search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
            refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/></svg>',
            check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
            grid: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
            edit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>',
            copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>',
            trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>',
        };
        return icons[name] || "";
    }

    function injectStyles() {
        if (document.getElementById("odtm-style-clean")) return;
        const style = document.createElement("style");
        style.id = "odtm-style-clean";
        style.textContent = `
            .odtm-root {
                --bg: #f3f5fa;
                --surface: #fff;
                --border: #dfe3ed;
                --border-light: #e8ecf4;
                --text: #111827;
                --muted: #5b6582;
                --faint: #8c93a8;
                --accent: #4f6ef7;
                --accent-bg: #eef1ff;
                --gradient: linear-gradient(135deg, #4f6ef7, #7c5cf5);
                --purple: #7c5cf5;
                --purple-bg: #f3f0ff;
                --green: #16a34a;
                --green-bg: #ecfdf5;
                --red: #ef4444;
                --red-bg: #fef2f2;
                min-height: 100vh;
                background: var(--bg);
                color: var(--text);
                font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            }
            .odtm-shell { width: 100%; max-width: 1880px; margin: 0 auto; padding: 30px 40px 64px; }
            .odtm-breadcrumb { display: flex; align-items: center; gap: 8px; margin-bottom: 24px; color: var(--faint); font-size: 15px; font-weight: 600; }
            .odtm-breadcrumb a { display: inline-flex; align-items: center; color: var(--faint); text-decoration: none; }
            .odtm-breadcrumb a:hover { color: var(--accent); }
            .odtm-breadcrumb strong { color: var(--muted); }
            .odtm-breadcrumb svg { width: 16px; height: 16px; }
            .odtm-hero { position: relative; display: flex; align-items: center; justify-content: space-between; gap: 28px; min-height: 220px; padding: 32px 38px; overflow: hidden; border: 1px solid var(--border-light); border-radius: 20px; background: #fff; box-shadow: 0 5px 16px rgba(15, 23, 41, .06); }
            .odtm-hero::before { content: ""; position: absolute; inset: 0 0 auto; height: 4px; background: var(--gradient); }
            .odtm-hero > div { min-width: 0; }
            .odtm-hero span { display: inline-flex; align-items: center; gap: 7px; margin-bottom: 16px; padding: 6px 14px; border-radius: 999px; background: var(--accent-bg); color: var(--accent); font-size: 13px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; }
            .odtm-hero span svg { width: 16px; height: 16px; }
            .odtm-hero h1 { margin: 0; color: var(--text); font-size: 32px; line-height: 1.15; font-weight: 800; letter-spacing: -.025em; }
            .odtm-hero p { max-width: 740px; margin: 12px 0 0; color: var(--muted); font-size: 18px; line-height: 1.55; }
            .odtm-primary { display: inline-flex; align-items: center; justify-content: center; gap: 9px; min-height: 54px; padding: 0 26px; border: 0; border-radius: 14px; background: var(--gradient); color: #fff; font-size: 17px; font-weight: 700; white-space: nowrap; cursor: pointer; box-shadow: 0 6px 16px rgba(79, 110, 247, .28); }
            .odtm-primary svg { width: 20px; height: 20px; }
            .odtm-tabs { display: inline-flex; gap: 4px; margin-top: 26px; padding: 5px; border: 1px solid var(--border-light); border-radius: 14px; background: #fff; box-shadow: 0 3px 10px rgba(15, 23, 41, .05); }
            .odtm-tabs button { display: inline-flex; align-items: center; gap: 12px; min-height: 50px; padding: 0 22px; border: 0; border-radius: 10px; background: transparent; color: var(--muted); font-size: 17px; font-weight: 700; white-space: nowrap; cursor: pointer; }
            .odtm-tabs button.active { background: var(--accent-bg); color: var(--accent); }
            .odtm-tabs span { display: inline-flex; align-items: center; justify-content: center; min-width: 30px; height: 30px; padding: 0 8px; border-radius: 999px; background: #f0f2f8; color: var(--muted); font-size: 14px; }
            .odtm-tabs button.active span { background: var(--accent); color: #fff; }
            .odtm-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; margin-top: 24px; }
            .odtm-summary article { display: flex; align-items: center; gap: 17px; min-height: 104px; padding: 22px 26px; border: 1px solid var(--border-light); border-radius: 16px; background: #fff; box-shadow: 0 4px 12px rgba(15, 23, 41, .05); }
            .odtm-metric-icon { display: inline-flex; align-items: center; justify-content: center; width: 50px; height: 50px; flex: 0 0 50px; border-radius: 12px; }
            .odtm-metric-icon svg { width: 24px; height: 24px; }
            .odtm-metric-icon.blue { background: var(--accent-bg); color: var(--accent); }
            .odtm-metric-icon.green { background: var(--green-bg); color: var(--green); }
            .odtm-metric-icon.purple { background: var(--purple-bg); color: var(--purple); }
            .odtm-summary strong { display: block; color: var(--text); font-size: 25px; line-height: 1.15; font-weight: 800; white-space: nowrap; }
            .odtm-summary span { display: block; margin-top: 4px; color: var(--faint); font-size: 15px; white-space: nowrap; }
            .odtm-toolbar { display: grid; grid-template-columns: minmax(280px, 1fr) 215px 190px 56px; gap: 12px; margin-top: 24px; }
            .odtm-search { position: relative; min-width: 0; }
            .odtm-search svg { position: absolute; top: 50%; left: 17px; width: 20px; height: 20px; transform: translateY(-50%); color: var(--faint); pointer-events: none; }
            .odtm-toolbar input, .odtm-toolbar select { width: 100%; min-height: 56px; padding: 0 16px; border: 1px solid var(--border); border-radius: 13px; outline: 0; background: #fff; color: var(--text); font: inherit; font-size: 16px; }
            .odtm-search input { padding-left: 50px; }
            .odtm-toolbar input:focus, .odtm-toolbar select:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(79, 110, 247, .1); }
            .odtm-secondary { display: inline-flex; align-items: center; justify-content: center; gap: 7px; min-height: 40px; padding: 0 14px; border: 1px solid var(--border); border-radius: 10px; background: #fff; color: var(--muted); font-size: 14px; font-weight: 700; white-space: nowrap; cursor: pointer; }
            .odtm-secondary:hover { border-color: var(--accent); background: var(--accent-bg); color: var(--accent); }
            .odtm-secondary svg { width: 17px; height: 17px; }
            .odtm-refresh { width: 56px; min-height: 56px; padding: 0; }
            .odtm-list-card { margin-top: 20px; overflow: hidden; border: 1px solid var(--border-light); border-radius: 20px; background: #fff; box-shadow: 0 5px 15px rgba(15, 23, 41, .06); }
            .odtm-list-head { display: flex; align-items: center; min-height: 76px; padding: 0 30px; border-bottom: 1px solid var(--border-light); }
            .odtm-list-head h2 { display: flex; align-items: center; gap: 14px; margin: 0; color: var(--text); font-size: 20px; font-weight: 800; }
            .odtm-list-head h2 span { padding: 5px 11px; border-radius: 999px; background: var(--accent-bg); color: var(--accent); font-size: 13px; font-weight: 700; white-space: nowrap; }
            .odtm-table-wrap { width: 100%; overflow-x: auto; }
            .odtm-table { width: 100%; min-width: 1220px; border-collapse: collapse; table-layout: fixed; }
            .odtm-col-template { width: 38%; }
            .odtm-col-company { width: 17%; }
            .odtm-col-count { width: 9%; }
            .odtm-col-state { width: 10%; }
            .odtm-col-actions { width: 26%; }
            .odtm-table th { padding: 16px 30px; border-bottom: 1px solid var(--border-light); background: #f8f9fc; color: var(--faint); font-size: 12px; font-weight: 800; letter-spacing: .07em; text-align: left; text-transform: uppercase; white-space: nowrap; }
            .odtm-table td { height: 110px; padding: 18px 30px; border-bottom: 1px solid var(--border-light); vertical-align: middle; }
            .odtm-table tr:last-child td { border-bottom: 0; }
            .odtm-table .right { text-align: right; }
            .odtm-template-cell { display: flex; align-items: center; gap: 16px; min-width: 0; }
            .odtm-template-cell > div { min-width: 0; }
            .odtm-row-icon { display: inline-flex; align-items: center; justify-content: center; width: 50px; height: 50px; flex: 0 0 50px; border-radius: 12px; background: var(--accent-bg); color: var(--accent); }
            .odtm-row-icon svg { width: 23px; height: 23px; }
            .odtm-template-cell strong { display: block; overflow: hidden; color: var(--text); font-size: 16px; font-weight: 800; text-overflow: ellipsis; white-space: nowrap; }
            .odtm-template-cell small { display: -webkit-box; max-width: 520px; margin-top: 5px; overflow: hidden; color: var(--faint); font-size: 14px; line-height: 1.4; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
            .odtm-company { display: inline-flex; align-items: center; gap: 7px; color: var(--muted); font-size: 14px; white-space: nowrap; }
            .odtm-company svg { width: 17px; height: 17px; flex: 0 0 17px; color: var(--faint); }
            .odtm-count-pill { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 999px; background: var(--purple-bg); color: var(--purple); font-size: 14px; font-weight: 800; white-space: nowrap; }
            .odtm-count-pill svg { width: 16px; height: 16px; }
            .odtm-state { display: inline-flex; align-items: center; gap: 7px; padding: 6px 12px; border-radius: 999px; font-size: 14px; font-weight: 800; white-space: nowrap; }
            .odtm-state i { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
            .odtm-state.green { border: 1px solid #bbf7d0; background: var(--green-bg); color: #15803d; }
            .odtm-state.gray { background: #f1f5f9; color: var(--muted); }
            .odtm-row-actions { display: flex; align-items: center; justify-content: flex-end; gap: 9px; min-width: max-content; }
            .odtm-row-actions .small { min-height: 44px; padding: 0 15px; border-radius: 10px; font-size: 14px; }
            .odtm-action-open { border-color: transparent; background: var(--accent-bg); color: var(--accent); }
            .odtm-action-open:hover { background: var(--accent); color: #fff; }
            .odtm-delete { display: inline-flex; align-items: center; justify-content: center; width: 44px; height: 44px; flex: 0 0 44px; padding: 0; border: 1px solid var(--border); border-radius: 10px; background: #fff; color: var(--faint); cursor: pointer; }
            .odtm-delete:hover { border-color: var(--red); background: var(--red-bg); color: var(--red); }
            .odtm-delete svg { width: 18px; height: 18px; }
            .odtm-target-checks { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
            .odtm-target-checks label { display: inline-flex; align-items: center; gap: 6px; padding: 5px 9px; border: 1px solid var(--border); border-radius: 999px; color: var(--muted); font-size: 12px; white-space: nowrap; }
            .odtm-target-checks label.selected { border-color: #bfc9ff; background: var(--accent-bg); color: var(--accent); }
            .odtm-empty { padding: 46px; color: var(--faint); text-align: center; }
            .odtm-empty strong { display: block; color: var(--text); font-size: 18px; }
            .odtm-empty p { margin: 8px 0 16px; }
            @media (max-width: 900px) {
                .odtm-shell { padding: 18px 14px 48px; }
                .odtm-hero { display: block; min-height: 0; padding: 26px; }
                .odtm-primary { margin-top: 20px; }
                .odtm-summary { grid-template-columns: 1fr; }
                .odtm-toolbar { grid-template-columns: 1fr; }
                .odtm-refresh { width: 100%; }
                .odtm-tabs { display: flex; width: 100%; }
                .odtm-tabs button { flex: 1; justify-content: space-between; }
            }
        `;
        style.textContent += `
            .odtm-shell { max-width: 1540px; padding: 22px 30px 48px; }
            .odtm-breadcrumb { margin-bottom: 16px; font-size: 13px; }
            .odtm-hero { min-height: 154px; padding: 24px 28px; border-radius: 16px; }
            .odtm-hero span { margin-bottom: 10px; padding: 4px 11px; font-size: 11px; }
            .odtm-hero h1 { font-size: 25px; }
            .odtm-hero p { max-width: 650px; margin-top: 8px; font-size: 15px; }
            .odtm-primary { min-height: 44px; padding: 0 19px; border-radius: 11px; font-size: 14px; }
            .odtm-primary svg { width: 17px; height: 17px; }
            .odtm-tabs { margin-top: 18px; padding: 4px; border-radius: 11px; }
            .odtm-tabs button { min-height: 40px; padding: 0 16px; border-radius: 8px; font-size: 14px; }
            .odtm-tabs span { min-width: 24px; height: 24px; font-size: 12px; }
            .odtm-summary { gap: 12px; margin-top: 16px; }
            .odtm-summary article { min-height: 78px; padding: 15px 18px; border-radius: 13px; }
            .odtm-metric-icon { width: 40px; height: 40px; flex-basis: 40px; border-radius: 10px; }
            .odtm-metric-icon svg { width: 19px; height: 19px; }
            .odtm-summary strong { font-size: 20px; }
            .odtm-summary span { margin-top: 2px; font-size: 12px; }
            .odtm-toolbar { grid-template-columns: minmax(240px, 1fr) 185px 165px 44px; gap: 9px; margin-top: 16px; }
            .odtm-toolbar input, .odtm-toolbar select { min-height: 44px; border-radius: 10px; font-size: 14px; }
            .odtm-search svg { left: 14px; width: 17px; height: 17px; }
            .odtm-search input { padding-left: 42px; }
            .odtm-refresh { width: 44px; min-height: 44px; }
            .odtm-list-card { margin-top: 14px; border-radius: 16px; }
            .odtm-list-head { min-height: 58px; padding: 0 22px; }
            .odtm-list-head h2 { gap: 10px; font-size: 16px; }
            .odtm-list-head h2 span { padding: 3px 9px; font-size: 11px; }
            .odtm-table { min-width: 1050px; }
            .odtm-col-template { width: 37%; }
            .odtm-col-company { width: 17%; }
            .odtm-col-count { width: 8%; }
            .odtm-col-state { width: 10%; }
            .odtm-col-actions { width: 28%; }
            .odtm-table th { padding: 11px 22px; font-size: 10px; }
            .odtm-table td { height: 84px; padding: 13px 22px; }
            .odtm-row-icon { width: 40px; height: 40px; flex-basis: 40px; border-radius: 10px; }
            .odtm-row-icon svg { width: 19px; height: 19px; }
            .odtm-template-cell { gap: 12px; }
            .odtm-template-cell strong { font-size: 14px; }
            .odtm-template-cell small { margin-top: 3px; font-size: 12px; }
            .odtm-company, .odtm-count-pill, .odtm-state { font-size: 12px; }
            .odtm-count-pill, .odtm-state { padding: 4px 9px; }
            .odtm-row-actions { gap: 7px; }
            .odtm-row-actions .small { min-height: 36px; padding: 0 11px; border-radius: 8px; font-size: 12px; }
            .odtm-delete { width: 36px; height: 36px; flex-basis: 36px; border-radius: 8px; }
            .odtm-delete svg { width: 15px; height: 15px; }
            .odtm-root input[type="checkbox"] { appearance: none !important; -webkit-appearance: none !important; width: 17px !important; height: 17px !important; min-width: 17px !important; min-height: 17px !important; margin: 0 !important; padding: 0 !important; border: 1px solid #cbd2df !important; border-radius: 4px !important; background: #fff !important; box-shadow: none !important; }
            .odtm-root input[type="checkbox"]::before, .odtm-root input[type="checkbox"]::after { content: none !important; display: none !important; }
            .odtm-root input[type="checkbox"]:checked { border-color: var(--accent) !important; background-color: var(--accent) !important; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 14 14'%3E%3Cpath d='M3 7.2 5.6 10 11 4.2' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") !important; background-position: center !important; background-repeat: no-repeat !important; background-size: 13px 13px !important; }
        `;
        document.head.appendChild(style);
    }

    function injectLegacyStyles() {
        if (document.getElementById("odtm-style")) return;
        const style = document.createElement("style");
        style.id = "odtm-style";
        style.textContent = `.odtm-root{background:#f6f8fb;min-height:100vh}.odtm-shell{width:min(1360px,100%);margin:0 auto;padding:22px clamp(14px,2vw,28px) 64px;color:#172033}.odtm-breadcrumb{display:flex;align-items:center;gap:8px;margin-bottom:12px;color:#64748b;font-size:12px;font-weight:800}.odtm-breadcrumb a{color:#2563eb;text-decoration:none}.odtm-hero{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;padding:22px;border:1px solid #dbe5ef;border-radius:20px;background:linear-gradient(135deg,#fff 0%,#eef6ff 100%);box-shadow:0 12px 28px rgba(15,23,42,.06)}.odtm-hero span{display:inline-flex;margin-bottom:7px;color:#2563eb;font-size:11px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.odtm-hero h1{margin:0;font-size:clamp(26px,3vw,36px);letter-spacing:-.04em;line-height:1.04}.odtm-hero p{max-width:820px;margin:8px 0 0;color:#475569;font-size:14px;line-height:1.55}.odtm-primary,.odtm-secondary{min-height:38px;border-radius:11px;padding:0 14px;font-size:13px;font-weight:900;cursor:pointer}.odtm-primary{border:0;background:#2563eb;color:#fff;box-shadow:0 9px 18px rgba(37,99,235,.2)}.odtm-secondary{border:1px solid #bfdbfe;background:#eff6ff;color:#1d4ed8}.odtm-secondary.small{min-height:32px;border-radius:9px;font-size:12px;white-space:nowrap}.odtm-tabs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:14px}.odtm-tabs button{display:flex;justify-content:space-between;align-items:center;min-height:44px;border:1px solid #dbe5ef;border-radius:14px;background:#fff;padding:0 14px;color:#475569;font-weight:900}.odtm-tabs button.active{border-color:#60a5fa;background:#eff6ff;color:#1d4ed8}.odtm-tabs span{border-radius:999px;background:#e2e8f0;padding:3px 9px;font-size:12px}.odtm-toolbar{display:grid;grid-template-columns:minmax(260px,1fr) 220px 170px auto;gap:10px;margin-top:14px}.odtm-toolbar input,.odtm-toolbar select{min-height:38px;border:1px solid #cbd5e1;border-radius:11px;background:#fff;padding:0 11px;font-size:13px}.odtm-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:12px}.odtm-summary article{border:1px solid #dbe5ef;border-radius:15px;background:#fff;padding:14px;box-shadow:0 8px 20px rgba(15,23,42,.04)}.odtm-summary strong{display:block;font-size:23px;line-height:1}.odtm-summary span{display:block;margin-top:5px;color:#64748b;font-size:12px;font-weight:800}.odtm-list-card{margin-top:14px;border:1px solid #dbe5ef;border-radius:18px;background:#fff;box-shadow:0 10px 24px rgba(15,23,42,.05);overflow:hidden}.odtm-list-head{display:flex;justify-content:space-between;align-items:center;padding:15px 17px;border-bottom:1px solid #e2e8f0}.odtm-list-head h2{margin:0;font-size:16px}.odtm-table-wrap{overflow:auto}.odtm-table{width:100%;border-collapse:collapse}.odtm-table th,.odtm-table td{padding:12px 14px;border-bottom:1px solid #edf2f7;text-align:left;vertical-align:top;font-size:13px}.odtm-table th{background:#f8fafc;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.06em}.odtm-table small{display:block;margin-top:3px;color:#64748b}.odtm-table .right{text-align:right;white-space:nowrap}.odtm-state{display:inline-flex;border-radius:999px;padding:4px 9px;font-size:11px;font-weight:900}.odtm-state.green{background:#dcfce7;color:#166534}.odtm-state.gray{background:#e2e8f0;color:#475569}.odtm-target-checks{display:flex;flex-wrap:wrap;gap:6px}.odtm-target-checks label{display:inline-flex;gap:5px;align-items:center;border:1px solid #dbe5ef;border-radius:999px;padding:4px 8px;background:#fff;font-size:11px;font-weight:800}.odtm-target-checks label.selected{background:#eff6ff;border-color:#93c5fd;color:#1d4ed8}.odtm-empty{padding:32px;text-align:center;color:#64748b}.odtm-empty strong{display:block;color:#172033;font-size:18px;margin-bottom:6px}@media(max-width:800px){.odtm-hero{display:block}.odtm-toolbar,.odtm-summary,.odtm-tabs{grid-template-columns:1fr}.odtm-primary{margin-top:12px}.odtm-table .right{text-align:left}}`;
        style.textContent += `.odtm-root{--odtm-bg:#f5f6fa;--odtm-surface:#fff;--odtm-border:#e4e7f0;--odtm-border-light:#eef1f8;--odtm-text:#0f1729;--odtm-muted:#5b6582;--odtm-faint:#8c93a8;--odtm-accent:#4f6ef7;--odtm-accent-bg:#eef1ff;--odtm-grad:linear-gradient(135deg,#4f6ef7,#7c5cf5);--odtm-purple:#7c5cf5;--odtm-purple-bg:#f3f0ff;--odtm-green:#22c55e;--odtm-green-bg:#ecfdf5;--odtm-red:#ef4444;--odtm-red-bg:#fef2f2;background:var(--odtm-bg);font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.odtm-shell{width:min(1200px,100%);padding:16px 24px 48px;color:var(--odtm-text)}.odtm-breadcrumb{gap:6px;margin-bottom:14px;color:var(--odtm-faint);font-weight:500}.odtm-breadcrumb svg{width:13px;height:13px;opacity:.65}.odtm-breadcrumb a{color:var(--odtm-faint)}.odtm-breadcrumb a:hover{color:var(--odtm-accent)}.odtm-breadcrumb strong{color:var(--odtm-muted)}.odtm-hero{position:relative;overflow:hidden;border-color:var(--odtm-border-light);border-radius:14px;background:var(--odtm-surface);box-shadow:0 1px 2px rgba(15,23,41,.04);padding:20px 24px;margin-bottom:16px}.odtm-hero:before{content:"";position:absolute;top:0;left:0;right:0;height:3px;background:var(--odtm-grad)}.odtm-hero span{align-items:center;gap:6px;margin-bottom:6px;border-radius:999px;background:var(--odtm-accent-bg);color:var(--odtm-accent);padding:3px 10px;font-size:10px}.odtm-hero span svg{width:12px;height:12px}.odtm-hero h1{font-size:20px;letter-spacing:-.02em}.odtm-hero p{max-width:520px;font-size:13px;color:var(--odtm-muted)}.odtm-primary{display:inline-flex;align-items:center;gap:6px;min-height:36px;border-radius:10px;background:var(--odtm-grad);font-weight:700;box-shadow:0 2px 8px rgba(79,110,247,.3);transition:all .25s cubic-bezier(.4,0,.2,1)}.odtm-primary:hover{transform:translateY(-1px);box-shadow:0 4px 14px rgba(79,110,247,.35)}.odtm-primary svg,.odtm-secondary svg,.odtm-delete svg{width:15px;height:15px}.odtm-tabs{display:flex;width:fit-content;gap:2px;margin-bottom:14px;background:var(--odtm-surface);border:1px solid var(--odtm-border-light);border-radius:10px;padding:3px;box-shadow:0 1px 2px rgba(15,23,41,.04)}.odtm-tabs button{min-height:34px;border:0;border-radius:7px;padding:0 14px;background:transparent;color:var(--odtm-muted);font-weight:500;gap:8px}.odtm-tabs button:hover{background:#f8f9fc;color:var(--odtm-text)}.odtm-tabs button.active{background:var(--odtm-accent-bg);color:var(--odtm-accent);font-weight:700}.odtm-tabs span{background:var(--odtm-border-light);min-width:20px;text-align:center}.odtm-tabs button.active span{background:var(--odtm-accent);color:#fff}.odtm-summary article{display:flex;align-items:center;gap:12px;border-color:var(--odtm-border-light);border-radius:10px;padding:14px 16px;box-shadow:0 1px 2px rgba(15,23,41,.04);transition:all .25s cubic-bezier(.4,0,.2,1)}.odtm-summary article:hover{box-shadow:0 4px 12px rgba(15,23,41,.06);transform:translateY(-1px)}.odtm-metric-icon{width:36px;height:36px;border-radius:8px;display:flex;align-items:center;justify-content:center;flex-shrink:0}.odtm-metric-icon svg{width:18px;height:18px}.odtm-metric-icon.blue{background:var(--odtm-accent-bg);color:var(--odtm-accent)}.odtm-metric-icon.green{background:var(--odtm-green-bg);color:var(--odtm-green)}.odtm-metric-icon.purple{background:var(--odtm-purple-bg);color:var(--odtm-purple)}.odtm-summary strong{font-size:18px}.odtm-summary span{font-size:11px;color:var(--odtm-faint)}.odtm-toolbar{display:flex;align-items:center;gap:8px;margin-bottom:12px}.odtm-search{flex:1;position:relative}.odtm-search svg{position:absolute;left:12px;top:50%;transform:translateY(-50%);width:16px;height:16px;color:var(--odtm-faint);pointer-events:none}.odtm-search input{width:100%;padding-left:36px!important}.odtm-toolbar input,.odtm-toolbar select{border-color:var(--odtm-border);border-radius:10px;color:var(--odtm-text);transition:all .15s cubic-bezier(.4,0,.2,1)}.odtm-toolbar input:focus,.odtm-toolbar select:focus{outline:0;border-color:var(--odtm-accent);box-shadow:0 0 0 3px rgba(79,110,247,.1)}.odtm-refresh{width:36px;padding:0;display:inline-flex;align-items:center;justify-content:center;border-color:var(--odtm-border);background:#fff;color:var(--odtm-muted)}.odtm-refresh:hover{border-color:var(--odtm-accent);color:var(--odtm-accent);background:var(--odtm-accent-bg)}.odtm-list-card{border-color:var(--odtm-border-light);border-radius:14px;box-shadow:0 1px 4px rgba(15,23,41,.06),0 1px 2px rgba(15,23,41,.03)}.odtm-list-head{padding:14px 20px}.odtm-list-head h2{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:700}.odtm-table th{padding:10px 20px;background:#f8f9fc;color:var(--odtm-faint);font-size:10px;font-weight:700}.odtm-table td{padding:14px 20px;font-size:13px}.odtm-table tr:hover{background:#f8f9fc}.odtm-template-cell{display:flex;align-items:center;gap:12px}.odtm-row-icon{width:36px;height:36px;border-radius:8px;background:var(--odtm-accent-bg);color:var(--odtm-accent);display:flex;align-items:center;justify-content:center;flex-shrink:0}.odtm-row-icon svg{width:17px;height:17px}.odtm-company{display:inline-flex;align-items:center;gap:5px;color:var(--odtm-muted);font-size:12px}.odtm-company svg{width:14px;height:14px;color:var(--odtm-faint)}.odtm-count-pill{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:999px;background:var(--odtm-purple-bg);color:var(--odtm-purple);font-size:12px;font-weight:700}.odtm-count-pill svg{width:13px;height:13px}.odtm-state i{width:6px;height:6px;border-radius:50%;background:currentColor}.odtm-secondary.small{display:inline-flex;align-items:center;gap:5px;border-radius:7px;font-weight:600}.odtm-action-open{background:var(--odtm-accent-bg);border-color:transparent;color:var(--odtm-accent)}.odtm-action-open:hover{background:var(--odtm-accent);color:#fff}.odtm-delete{display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;padding:0;border-radius:7px;border:1px solid var(--odtm-border);background:#fff;color:var(--odtm-faint)}.odtm-delete:hover{background:var(--odtm-red-bg);border-color:var(--odtm-red);color:var(--odtm-red)}@media(max-width:860px){.odtm-shell{padding:12px}.odtm-hero{display:block}.odtm-tabs,.odtm-toolbar{width:100%;flex-direction:column;align-items:stretch}.odtm-tabs button{justify-content:space-between}.odtm-summary{grid-template-columns:1fr}.odtm-table .right{white-space:normal}.odtm-table td{padding:12px}}`;
        document.head.appendChild(style);
    }
})();
