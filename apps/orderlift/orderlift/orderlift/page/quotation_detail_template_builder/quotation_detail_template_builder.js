(function () {
    const STATE = { template: null, blockTypes: [], quotationFields: [], annexTemplates: [], allowedCompanies: [], expandedBlocks: new Set(), loading: false };
    const DEFAULT_BLOCK = { block_label: "", block_key: "", block_type: "Paragraph", source_field: "", annex_template: "", annex_field_key: "", default_value: "", options: "", is_required: 0, allow_manual_override: 1, display_order: 100 };

    frappe.pages["quotation-detail-template-builder"].on_page_load = function (wrapper) {
        const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Quotation Detail Template Builder"), single_column: true });
        wrapper.page = page;
        page.main.addClass("oqtb-root");
        hideFrappeHeader(wrapper);
        injectStyles();
        load(page);
    };

    frappe.pages["quotation-detail-template-builder"].on_page_show = function (wrapper) {
        if (wrapper.page) load(wrapper.page);
    };

    function blankTemplate() {
        return { name: "", template_name: "", is_active: 1, company: "", display_order: 100, description: "", blocks: [] };
    }

    async function load(page) {
        const route = frappe.get_route();
        const name = route[1] || "new";
        const boot = await frappe.call({ method: "orderlift.quotation_detail_templates.get_quotation_template_manager_bootstrap" });
        STATE.blockTypes = (boot.message || {}).block_types || [];
        STATE.quotationFields = (boot.message || {}).quotation_fields || [];
        STATE.annexTemplates = (boot.message || {}).annex_templates || [];
        STATE.allowedCompanies = (boot.message || {}).allowed_companies || [];
        if (name && name !== "new") {
            const res = await frappe.call({ method: "orderlift.quotation_detail_templates.get_quotation_template", args: { name } });
            STATE.template = res.message || blankTemplate();
        } else if (!STATE.template || STATE.template.name) {
            STATE.template = blankTemplate();
        }
        render(page);
    }

    function render(page) {
        const template = STATE.template || blankTemplate();
        page.main.html(`
            <div class="oqtb-shell">
                <section class="oqtb-topbar"><div class="oqtb-topbar-left"><button type="button" class="oqtb-back-button" data-back aria-label="${esc(__("Back"))}">${icon("back")}</button><div><span class="oqtb-badge">${icon("file")}${esc(__("Quotation Details"))}</span><h1>${esc(template.template_name || __("New Quotation Template"))}</h1></div></div><div class="oqtb-actions"><button type="button" class="oqtb-secondary" data-preview-template>${icon("eye")}${esc(__("Preview"))}</button><button type="button" class="oqtb-primary" data-save>${icon("save")}${esc(__("Save Template"))}</button></div></section>
                <div class="oqtb-section-label">${icon("settings")}${esc(__("Template Settings"))}</div>
                <section class="oqtb-card oqtb-setup-card"><div class="oqtb-setup-body"><div class="oqtb-grid-3">${input("template_name", __("Template Name"), template.template_name, "text", true)}${selectInput("company", __("Company"), companyOptions(), template.company || "", false, __("All Companies"))}${input("display_order", __("Display Order"), template.display_order || 100, "number")}</div><div class="oqtb-description-row">${textarea("description", __("Description"), template.description || "")}</div></div><div class="oqtb-setup-footer"><label class="oqtb-active-toggle"><input type="checkbox" data-field="is_active" ${template.is_active ? "checked" : ""}/><span class="oqtb-toggle-track"><i></i></span><strong>${esc(__("Active"))}</strong></label><span class="oqtb-status-pill"><i></i>${esc(template.is_active ? __("Active") : __("Inactive"))}</span></div></section>
                <section class="oqtb-block-section"><div class="oqtb-blocks-heading"><h2>${icon("grid")}${esc(__("Blocks"))}<span>${Number((template.blocks || []).length)} ${esc(__("blocks"))}</span></h2><p>${icon("info")}${esc(__("Use Page Break to split pages. Annex Field reads the matching annex from the Quotation first, then the linked Opportunity."))}</p></div><div class="oqtb-builder-layout"><div class="oqtb-blocks">${(template.blocks || []).length ? template.blocks.map(blockRow).join("") : `<div class="oqtb-empty">${esc(__("No blocks yet."))}</div>`}</div>${blockToolbarMarkup()}</div></section>
            </div>
        `);
        bind(page);
    }

    function hideFrappeHeader(wrapper) {
        $(wrapper).closest(".page-container").find(".page-head").hide();
    }

    function blockRow(row, index) {
        const type = row.block_type || "Paragraph";
        const label = row.block_label || type;
        const isAnnex = type === "Annex Field";
        const isQuotation = type === "Quotation Field";
        const usesExternalSource = isAnnex || isQuotation;
        const hasResolvedSource = (isAnnex && row.annex_template && row.annex_field_key) || (isQuotation && row.source_field);
        return `
            <article class="oqtb-block-card ${typeClass(type)} ${STATE.expandedBlocks.has(index) ? "expanded" : ""}" data-block-index="${index}">
                <div class="oqtb-block-card-head" data-toggle-block="${index}">
                    <span class="oqtb-drag-handle">${icon("drag")}</span>
                    <div class="oqtb-block-title-wrap">
                        <span class="oqtb-type-pill">${esc(__(type))}</span>
                        <strong>${esc(label)}</strong>
                    </div>
                    <span class="oqtb-order-pill">#${index + 1}</span>
                    <span class="oqtb-chevron">${icon("chevron")}</span>
                    <button type="button" class="oqtb-danger" data-remove-block="${index}" title="${esc(__("Remove block"))}" aria-label="${esc(__("Remove block"))}">&times;</button>
                </div>
                ${type === "Page Break" ? `<div class="oqtb-block-card-body oqtb-page-break-panel"><span></span>${icon("break")}<strong>${esc(__("Page break in PDF"))}</strong><span></span></div>` : `<div class="oqtb-block-card-body">
                    <section class="oqtb-block-setup">
                        <div class="oqtb-fieldset-grid four">
                            ${input("block_label", __("Label"), row.block_label || "", "text", true, true)}
                            ${input("block_key", __("Key"), row.block_key || "", "text", false, true)}
                            <label><span>${esc(__("Type"))}</span><select data-row-field="block_type">${options(STATE.blockTypes, type)}</select></label>
                            ${input("display_order", __("Order"), row.display_order || index + 1, "number", false, true)}
                        </div>
                    </section>
                    <div class="oqtb-subsection-grid">
                        <section class="oqtb-fieldset source">
                            <i class="oqtb-section-accent"></i><h3>${esc(__("Data Source"))}</h3>
                            ${sourceControls(row, type)}
                        </section>
                        <section class="oqtb-fieldset rules">
                            <i class="oqtb-section-accent"></i><h3>${esc(__("Rules"))}</h3>
                            <div class="oqtb-rule-row">
                                <label class="oqtb-check inline"><input type="checkbox" data-row-field="is_required" ${row.is_required ? "checked" : ""}/><span>${esc(__("Required"))}</span></label>
                                <label class="oqtb-check inline"><input type="checkbox" data-row-field="allow_manual_override" ${row.allow_manual_override ? "checked" : ""}/><span>${esc(__("Manual override"))}</span></label>
                            </div>
                        </section>
                    </div>
                    ${usesExternalSource ? sourceContentNotice(hasResolvedSource) : contentControls(row, type)}
                </div>`}
            </article>
        `;
    }

    function sourceControls(row, type) {
        if (type === "Quotation Field") {
            return `<div class="oqtb-fieldset-grid one">${selectInput("source_field", __("Quotation Field"), quotationFieldOptions(), row.source_field || "", true, __("Choose a Quotation field"))}<p class="oqtb-help">${esc(__("Pick the native Quotation field by label. The printed value will come from that field on the Quotation."))}</p></div>`;
        }
        if (type === "Annex Field") {
            return `<div class="oqtb-fieldset-grid two">${selectInput("annex_template", __("Annex Template"), annexTemplateOptions(), row.annex_template || "", true, __("Choose annex template"))}${selectInput("annex_field_key", __("Annex Field"), annexFieldOptions(row.annex_template), row.annex_field_key || "", true, __("Choose annex field"))}</div><p class="oqtb-help">${esc(__("Choose the annex template first, then the field from that template. No internal field key typing is required."))}</p>`;
        }
        return `<div class="oqtb-source-empty">${esc(__("This block uses its own text or options. No document source is required."))}</div>`;
    }

    function contentControls(row, type) {
        const optionsLabel = type === "List" ? __("List Choices") : __("Choices / Helper Options");
        const optionsHint = type === "List"
            ? __("Enter one list item per line. Each line becomes a bullet in the proposal.")
            : __("Optional. Use one choice per line only when this block should show a dropdown while filling the Quotation.");
        return `<section class="oqtb-fieldset content"><i class="oqtb-section-accent"></i><h3>${esc(__("Text & Choices"))}</h3><div class="oqtb-fieldset-grid two">${textarea("default_value", __("Default Text"), row.default_value || "", true)}${textarea("options", optionsLabel, row.options || "", true, optionsHint)}</div></section>`;
    }

    function sourceContentNotice(configured) {
        const title = configured ? __("Resolved by source") : __("Select a source above");
        const message = configured
            ? __("This block reads from the selected source. Default text and manual option lists are not needed.")
            : __("Choose the source field above. Source-backed blocks do not use default text or option lists.");
        return `<section class="oqtb-fieldset content muted"><i class="oqtb-section-accent"></i><h3>${esc(title)}</h3><p>${esc(message)}</p></section>`;
    }

    function bind(page) {
        page.main.find("[data-back]").on("click", () => frappe.set_route("document-template-manager"));
        page.main.find("[data-save]").on("click", () => save(page));
        page.main.find("[data-preview-template]").on("click", () => openPreview(page));
        page.main.find("[data-add-block]").on("click", function () { collect(page); const type = $(this).data("add-block"); const index = STATE.template.blocks.length; STATE.template.blocks.push({ ...DEFAULT_BLOCK, block_type: type, block_label: defaultBlockLabel(type), display_order: index + 1 }); STATE.expandedBlocks = new Set([index]); render(page); });
        page.main.find("[data-toggle-block]").on("click", function () { collect(page); const index = Number($(this).data("toggle-block")); const expanded = new Set(STATE.expandedBlocks); expanded.has(index) ? expanded.delete(index) : expanded.add(index); STATE.expandedBlocks = expanded; render(page); });
        page.main.find("[data-remove-block]").on("click", function (event) { event.stopPropagation(); collect(page); STATE.template.blocks.splice(Number($(this).data("remove-block")), 1); STATE.expandedBlocks = new Set(); render(page); });
        page.main.find('[data-row-field="block_type"],[data-row-field="annex_template"]').on("change", function () { collect(page); render(page); });
        page.main.find('[data-link-doctype]').each(function () {
            const $input = $(this);
            frappe.ui.form.make_control({ parent: $input.parent(), df: { fieldtype: "Link", options: $input.data("link-doctype"), fieldname: $input.data("field") || $input.data("row-field"), label: $input.data("label") }, render_input: true });
        });
    }

    function collect(page) {
        const root = page.main;
        if (!STATE.template) STATE.template = blankTemplate();
        ["template_name", "company", "display_order", "description"].forEach((field) => { const el = root.find(`[data-field="${field}"]`); if (el.length) STATE.template[field] = el.val(); });
        if (root.find('[data-field="is_active"]').length) STATE.template.is_active = root.find('[data-field="is_active"]').is(":checked") ? 1 : 0;
        if (root.find("[data-block-index]").length) STATE.template.blocks = root.find("[data-block-index]").map(function () { const index = Number($(this).data("block-index")); return collectRow($(this), STATE.template.blocks[index]); }).get();
    }

    function collectRow(row, existing = {}) {
        const out = { ...existing };
        ["block_label", "block_key", "block_type", "source_field", "annex_template", "annex_field_key", "default_value", "options", "is_required", "allow_manual_override", "display_order"].forEach((field) => {
            const el = row.find(`[data-row-field="${field}"]`);
            if (el.length) out[field] = el.attr("type") === "checkbox" ? (el.is(":checked") ? 1 : 0) : el.val();
        });
        return out;
    }

    async function save(page) {
        collect(page);
        if (!String(STATE.template.template_name || "").trim()) return frappe.msgprint({ message: __("Template name is required."), indicator: "red" });
        const res = await frappe.call({ method: "orderlift.quotation_detail_templates.save_quotation_template", args: { payload: JSON.stringify(STATE.template) }, freeze: true });
        STATE.template = (res.message || {}).template || STATE.template;
        frappe.show_alert({ message: __("Template saved"), indicator: "green" });
        if (STATE.template.name) frappe.set_route("quotation-detail-template-builder", STATE.template.name);
        render(page);
    }

    function openPreview(page) {
        collect(page);
        const template = STATE.template || blankTemplate();
        const dialog = new frappe.ui.Dialog({ title: __("Quotation Detail Preview"), size: "extra-large", fields: [{ fieldtype: "HTML", fieldname: "body" }] });
        dialog.show();
        dialog.fields_dict.body.$wrapper.html(quotationPreviewMarkup(template));
    }

    function quotationPreviewMarkup(template) {
        const blocks = template.blocks || [];
        return `<div class="oqtb-preview-page"><div class="oqtb-preview-doc-head"><strong>${esc(template.template_name || __("Commercial Presentation"))}</strong><span>${esc(__("Preview uses template defaults and sample empty lines."))}</span></div>${blocks.map(previewBlock).join("")}</div>`;
    }

    function previewBlock(block) {
        if (block.block_type === "Page Break") return `<div class="oqtb-preview-page-break"><span>${esc(__("Page Break"))}</span></div>`;
        if (block.block_type === "Heading") return `<h2 class="oqtb-preview-heading">${esc(block.default_value || block.block_label)}</h2>`;
        if (block.block_type === "List") return `<div class="oqtb-preview-block"><b>${esc(block.block_label)}</b><ul>${String(block.default_value || block.options || "").split("\n").filter(Boolean).map((row) => `<li>${esc(row)}</li>`).join("") || `<li>${esc(__("List item"))}</li>`}</ul></div>`;
        if (["Key Value", "Quotation Field", "Annex Field"].includes(block.block_type)) return `<div class="oqtb-preview-kv"><b>${esc(block.block_label)} :</b><span>${esc(block.default_value || "")}</span></div>`;
        return `<div class="oqtb-preview-block"><b>${esc(block.block_label)}</b><p>${esc(block.default_value || "")}</p></div>`;
    }

    function input(field, label, value, type = "text", required = false, row = false) { return `<label><span>${esc(label)}${required ? " *" : ""}</span><input type="${esc(type)}" ${row ? `data-row-field="${esc(field)}"` : `data-field="${esc(field)}"`} value="${esc(value)}" /></label>`; }
    function textarea(field, label, value, row = false, helper = "") { return `<label class="oqtb-textarea"><span>${esc(label)}</span><textarea ${row ? `data-row-field="${esc(field)}"` : `data-field="${esc(field)}"`}>${esc(value)}</textarea>${helper ? `<small>${esc(helper)}</small>` : ""}</label>`; }
    function linkInput(field, label, doctype, value, row = false) { return `<label><span>${esc(label)}</span><input type="text" ${row ? `data-row-field="${esc(field)}"` : `data-field="${esc(field)}"`} value="${esc(value)}" placeholder="${esc(doctype)}" /></label>`; }
    function selectInput(field, label, choices, value, row = false, placeholder = "") { return `<label><span>${esc(label)}</span><select ${row ? `data-row-field="${esc(field)}"` : `data-field="${esc(field)}"`}><option value="">${esc(placeholder || __("Select"))}</option>${choices.map((choice) => `<option value="${esc(choice.value)}" ${choice.value === value ? "selected" : ""}>${esc(choice.label)}</option>`).join("")}</select></label>`; }
    function options(values, selected) { return values.map((value) => `<option value="${esc(value)}" ${value === selected ? "selected" : ""}>${esc(__(value))}</option>`).join(""); }
    function companyOptions() { return (STATE.allowedCompanies || []).map((company) => ({ value: company, label: company })); }
    function quotationFieldOptions() { return STATE.quotationFields.map((field) => ({ value: field.fieldname, label: `${field.label || field.fieldname} (${field.fieldname})` })); }
    function annexTemplateOptions() { return STATE.annexTemplates.map((template) => ({ value: template.name, label: template.template_name || template.name })); }
    function annexFieldOptions(templateName) { const template = STATE.annexTemplates.find((row) => row.name === templateName); return ((template && template.fields) || []).map((field) => ({ value: field.field_key, label: `${field.field_label || field.field_key} (${field.fieldtype || "Data"})` })); }
    function defaultBlockLabel(type) {
        if (type === "Page Break") return "Page Break";
        if (type === "Key Value") return "New Field";
        if (type === "Quotation Field") return "Quotation Field";
        if (type === "Annex Field") return "Annex Field";
        return "New " + type;
    }
    function blockToolbarMarkup() {
        return `<aside class="oqtb-block-toolbar"><div class="oqtb-palette-title">${icon("plus")}${esc(__("Add Block"))}</div>${toolbarGroup("Content", [
            ["Heading", "Heading", "Section title", "type-heading"],
            ["Paragraph", "Text", "Long proposal text", "type-text"],
            ["Key Value", "Field", "Label and value row", "type-field"],
            ["List", "List", "Bullet points", "type-list"],
        ])}${toolbarGroup("Sources", [
            ["Quotation Field", "Quotation", "Read from Quotation", "type-source"],
            ["Annex Field", "Annex", "Read from annex", "type-source"],
        ])}${toolbarGroup("Layout", [
            ["Manual Area", "Manual Area", "Editable notes", "type-layout"],
            ["Page Break", "Page Break", "Start next page", "type-layout oqtb-add-break"],
        ])}</aside>`;
    }
    function toolbarGroup(label, actions) {
        const buttons = actions.map((action) => toolbarButton(action[0], action[1], action[2], action[3] || "")).join("");
        return `<div class="oqtb-toolbar-group"><span>${esc(__(label))}</span><div class="oqtb-toolbar-buttons">${buttons}</div></div>`;
    }
    function toolbarButton(type, label, hint, extraClass) {
        if (STATE.blockTypes.length && !STATE.blockTypes.includes(type)) return "";
        return `<button type="button" class="oqtb-secondary oqtb-add-tile ${esc(extraClass)}" data-add-block="${esc(type)}">${icon(blockIcon(type))}<span><strong>${esc(__(label))}</strong><small>${esc(__(hint))}</small></span></button>`;
    }
    function blockIcon(type) {
        if (type === "Heading") return "heading";
        if (type === "Paragraph") return "text";
        if (type === "Key Value") return "field";
        if (type === "List") return "list";
        if (type === "Quotation Field" || type === "Annex Field") return "source";
        if (type === "Page Break") return "break";
        return "edit";
    }
    function typeClass(type) {
        return `type-${String(type || "Paragraph").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}`;
    }
    function esc(value) { return frappe.utils.escape_html(value == null ? "" : String(value)); }

    function icon(name) {
        const icons = {
            back: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>',
            file: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
            eye: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>',
            save: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>',
            settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9c.2.65.77 1.09 1.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>',
            plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>',
            info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
            grid: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
            heading: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h10M4 18h7"/></svg>',
            text: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h10"/></svg>',
            field: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 9h4M7 15h10"/></svg>',
            list: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>',
            source: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>',
            break: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16M4 17h16"/><path d="M12 9v6"/><path d="M9 12h6"/></svg>',
            edit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4 12.5-12.5z"/></svg>',
            drag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="9" cy="5" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="9" cy="19" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="19" r="1"/></svg>',
            chevron: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="6 9 12 15 18 9"/></svg>',
        };
        return icons[name] || "";
    }

    function injectStyles() {
        if (document.getElementById("oqtb-style-clean")) return;
        const style = document.createElement("style");
        style.id = "oqtb-style-clean";
        style.textContent = `
            .oqtb-root {
                --bg: #eef1f7;
                --surface: #fff;
                --surface-muted: #f6f7fb;
                --border: #dfe3ed;
                --border-light: #e8ecf4;
                --text: #111827;
                --muted: #5b6582;
                --faint: #8c93a8;
                --accent: #4f6ef7;
                --accent-bg: #eef1ff;
                --gradient: linear-gradient(135deg, #4f6ef7, #7c5cf5);
                --green: #16a34a;
                --green-bg: #ecfdf5;
                --orange: #d97706;
                --orange-bg: #fffbeb;
                --orange-border: #fde68a;
                --teal: #0f766e;
                --teal-bg: #f0fdfa;
                --red: #ef4444;
                --red-bg: #fef2f2;
                min-height: 100vh;
                background: var(--bg);
                color: var(--text);
                font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            }
            .oqtb-shell { width: 100%; max-width: 1880px; margin: 0 auto; padding: 0 44px 72px; }
            .oqtb-topbar { display: flex; align-items: center; justify-content: space-between; gap: 24px; margin: 0 -44px 24px; padding: 28px 44px; background: #fff; border-bottom: 1px solid var(--border-light); box-shadow: 0 2px 7px rgba(15, 23, 41, .05); }
            .oqtb-topbar-left { display: flex; align-items: center; gap: 22px; min-width: 0; }
            .oqtb-back-button { display: inline-flex; align-items: center; justify-content: center; width: 54px; height: 54px; flex: 0 0 54px; border: 1px solid var(--border); border-radius: 14px; background: #fff; color: var(--muted); cursor: pointer; }
            .oqtb-back-button:hover { color: var(--accent); border-color: var(--accent); background: var(--accent-bg); }
            .oqtb-back-button svg { width: 21px; height: 21px; }
            .oqtb-badge { display: inline-flex; align-items: center; gap: 6px; margin-bottom: 7px; padding: 4px 12px; border-radius: 999px; background: var(--accent-bg); color: var(--accent); font-size: 12px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; }
            .oqtb-badge svg { width: 14px; height: 14px; }
            .oqtb-topbar h1 { margin: 0; font-size: 25px; line-height: 1.2; font-weight: 800; letter-spacing: -.02em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            .oqtb-actions { display: flex; align-items: center; gap: 12px; flex-shrink: 0; }
            .oqtb-primary, .oqtb-secondary { display: inline-flex; align-items: center; justify-content: center; gap: 8px; min-height: 52px; padding: 0 22px; border-radius: 13px; font-size: 16px; font-weight: 700; cursor: pointer; transition: color .15s, background .15s, border-color .15s, box-shadow .15s; }
            .oqtb-primary { border: 0; background: var(--gradient); color: #fff; box-shadow: 0 5px 14px rgba(79, 110, 247, .28); }
            .oqtb-primary:hover { box-shadow: 0 8px 20px rgba(79, 110, 247, .34); }
            .oqtb-secondary { border: 1px solid var(--border); background: #fff; color: var(--muted); }
            .oqtb-secondary:hover { color: var(--accent); border-color: var(--accent); background: var(--accent-bg); }
            .oqtb-primary svg, .oqtb-secondary svg { width: 19px; height: 19px; }
            .oqtb-section-label { display: flex; align-items: center; gap: 9px; margin: 0 0 16px 4px; color: var(--faint); font-size: 15px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; }
            .oqtb-section-label svg { width: 20px; height: 20px; }
            .oqtb-card { background: var(--surface); border: 1px solid var(--border-light); border-radius: 19px; box-shadow: 0 5px 15px rgba(15, 23, 41, .06); }
            .oqtb-setup-card { overflow: hidden; margin-bottom: 40px; }
            .oqtb-setup-body { padding: 32px 36px 28px; }
            .oqtb-grid-3 { display: grid; grid-template-columns: minmax(0, 1fr) 290px 120px; gap: 20px; }
            .oqtb-description-row { margin-top: 22px; }
            .oqtb-card label { display: grid; gap: 8px; min-width: 0; color: var(--faint); font-size: 13px; font-weight: 800; letter-spacing: .04em; text-transform: uppercase; }
            .oqtb-card input, .oqtb-card select, .oqtb-card textarea { width: 100%; min-width: 0; min-height: 52px; padding: 11px 16px; border: 1px solid var(--border); border-radius: 12px; outline: 0; background: #fff; color: var(--text); font: inherit; font-size: 16px; }
            .oqtb-card input:focus, .oqtb-card select:focus, .oqtb-card textarea:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(79, 110, 247, .1); }
            .oqtb-textarea textarea { min-height: 90px; resize: vertical; }
            .oqtb-setup-footer { display: flex; align-items: center; justify-content: space-between; padding: 18px 36px; border-top: 1px solid var(--border-light); background: var(--surface-muted); }
            .oqtb-active-toggle { display: inline-flex !important; flex-direction: row !important; align-items: center; gap: 10px !important; color: var(--text) !important; font-size: 16px !important; letter-spacing: 0 !important; text-transform: none !important; cursor: pointer; }
            .oqtb-active-toggle input { position: absolute; opacity: 0; pointer-events: none; }
            .oqtb-toggle-track { position: relative; width: 48px; height: 28px; border-radius: 999px; background: #cfd5e2; transition: background .15s; }
            .oqtb-toggle-track i { position: absolute; top: 3px; left: 3px; width: 22px; height: 22px; border-radius: 50%; background: #fff; box-shadow: 0 1px 4px rgba(0, 0, 0, .16); transition: transform .15s; }
            .oqtb-active-toggle input:checked + .oqtb-toggle-track { background: var(--accent); }
            .oqtb-active-toggle input:checked + .oqtb-toggle-track i { transform: translateX(20px); }
            .oqtb-status-pill { display: inline-flex; align-items: center; gap: 7px; padding: 6px 13px; border: 1px solid #bbf7d0; border-radius: 999px; background: var(--green-bg); color: #15803d; font-size: 13px; font-weight: 700; }
            .oqtb-status-pill i { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
            .oqtb-block-section { background: transparent; }
            .oqtb-blocks-heading { margin-bottom: 22px; }
            .oqtb-blocks-heading h2 { display: flex; align-items: center; gap: 11px; margin: 0; font-size: 23px; font-weight: 800; }
            .oqtb-blocks-heading h2 > svg { width: 25px; height: 25px; color: var(--accent); }
            .oqtb-blocks-heading h2 span { margin-left: 10px; color: var(--accent); font-size: 16px; font-weight: 700; }
            .oqtb-blocks-heading p { display: flex; align-items: center; gap: 10px; max-width: 1060px; margin: 16px 0 0; padding: 14px 18px; border: 1px solid var(--border-light); border-radius: 12px; background: #f5f7fb; color: var(--faint); font-size: 15px; line-height: 1.5; }
            .oqtb-blocks-heading p svg { width: 18px; height: 18px; flex: 0 0 18px; }
            .oqtb-builder-layout { display: grid; grid-template-columns: minmax(0, 1fr) 420px; gap: 32px; align-items: start; }
            .oqtb-blocks { display: grid; gap: 18px; min-width: 0; }
            .oqtb-empty { padding: 36px; border: 1px dashed var(--border); border-radius: 16px; background: rgba(255, 255, 255, .55); color: var(--faint); text-align: center; }
            .oqtb-block-toolbar { position: sticky; top: 20px; width: 420px; overflow: hidden; border: 1px solid var(--border-light); border-radius: 19px; background: #fff; box-shadow: 0 6px 18px rgba(15, 23, 41, .07); }
            .oqtb-palette-title { display: flex; align-items: center; gap: 10px; padding: 22px 24px; border-bottom: 1px solid var(--border-light); font-size: 19px; font-weight: 800; }
            .oqtb-palette-title svg { width: 21px; height: 21px; color: var(--accent); }
            .oqtb-toolbar-group { padding: 20px 24px; }
            .oqtb-toolbar-group + .oqtb-toolbar-group { border-top: 1px solid var(--border-light); }
            .oqtb-toolbar-group > span { display: block; margin-bottom: 11px; color: var(--faint); font-size: 12px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
            .oqtb-toolbar-buttons { display: grid; gap: 9px; }
            .oqtb-add-tile { display: grid; grid-template-columns: 21px minmax(0, 1fr); align-items: center; gap: 10px; min-height: 58px; padding: 10px 15px; border: 1px solid var(--border-light); border-radius: 11px; background: #fff; color: var(--text); text-align: left; cursor: pointer; }
            .oqtb-add-tile > svg { width: 19px; height: 19px; color: var(--faint); }
            .oqtb-add-tile > span { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; min-width: 0; }
            .oqtb-add-tile strong { font-size: 16px; color: var(--text); }
            .oqtb-add-tile small { color: var(--faint); font-size: 13px; font-weight: 500; white-space: nowrap; }
            .oqtb-add-tile:hover { border-color: var(--accent); background: var(--accent-bg); }
            .oqtb-add-tile.type-source { border-color: var(--orange-border); background: var(--orange-bg); }
            .oqtb-add-tile.type-source > svg { color: var(--orange); }
            .oqtb-add-tile.type-layout { border-color: #bdebe4; background: var(--teal-bg); }
            .oqtb-add-tile.type-layout > svg { color: var(--teal); }
            .oqtb-add-break { border-style: dashed; }
            .oqtb-block-card { overflow: hidden; border: 1px solid var(--border-light); border-radius: 18px; background: #fff; box-shadow: 0 5px 14px rgba(15, 23, 41, .06); }
            .oqtb-block-card-head { display: grid; grid-template-columns: 22px minmax(0, 1fr) auto auto auto; align-items: center; gap: 14px; min-height: 84px; padding: 16px 24px; cursor: pointer; }
            .oqtb-block-card-head:hover { background: #fafbfe; }
            .oqtb-drag-handle { display: flex; color: #c2c8d5; }
            .oqtb-drag-handle svg { width: 18px; height: 18px; }
            .oqtb-block-title-wrap { display: flex; align-items: center; gap: 15px; min-width: 0; }
            .oqtb-block-title-wrap strong { min-width: 0; overflow: hidden; color: var(--text); font-size: 18px; font-weight: 800; text-overflow: ellipsis; white-space: nowrap; }
            .oqtb-type-pill { flex: 0 0 auto; padding: 6px 12px; border-radius: 999px; font-size: 12px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; }
            .type-heading .oqtb-type-pill { background: var(--accent-bg); color: var(--accent); }
            .type-paragraph .oqtb-type-pill { background: #f3f0ff; color: #7c5cf5; }
            .type-key-value .oqtb-type-pill { border: 1px solid var(--orange-border); background: var(--orange-bg); color: #92400e; }
            .type-list .oqtb-type-pill { background: var(--teal-bg); color: var(--teal); }
            .type-quotation-field .oqtb-type-pill, .type-annex-field .oqtb-type-pill { border: 1px solid var(--orange-border); background: var(--orange-bg); color: #b45309; }
            .type-manual-area .oqtb-type-pill { background: var(--teal-bg); color: var(--teal); }
            .type-page-break .oqtb-type-pill { background: var(--red-bg); color: var(--red); }
            .oqtb-order-pill { display: inline-flex; align-items: center; justify-content: center; min-width: 45px; height: 32px; padding: 0 9px; border-radius: 999px; background: #f3f5fa; color: var(--faint); font-size: 14px; font-weight: 800; }
            .oqtb-chevron { display: flex; color: var(--faint); transition: transform .18s; }
            .oqtb-chevron svg { width: 20px; height: 20px; }
            .oqtb-block-card.expanded .oqtb-chevron { transform: rotate(180deg); }
            .oqtb-danger { display: inline-flex; align-items: center; justify-content: center; width: 34px; height: 34px; border: 0; border-radius: 9px; background: transparent; color: #c4cad5; font-size: 25px; cursor: pointer; }
            .oqtb-danger:hover { background: var(--red-bg); color: var(--red); }
            .oqtb-block-card-body { display: none; padding: 24px 30px 28px; border-top: 1px solid var(--border-light); background: var(--surface-muted); }
            .oqtb-block-card.expanded .oqtb-block-card-body { display: block; }
            .oqtb-block-setup { padding-bottom: 22px; border-bottom: 1px solid var(--border-light); }
            .oqtb-block-card label { display: grid; gap: 8px; min-width: 0; color: var(--faint); font-size: 12px; font-weight: 800; letter-spacing: .04em; text-transform: uppercase; }
            .oqtb-block-card input, .oqtb-block-card select, .oqtb-block-card textarea { width: 100%; min-width: 0; min-height: 52px; padding: 11px 16px; border: 1px solid var(--border); border-radius: 12px; outline: 0; background: #fff; color: var(--text); font: inherit; font-size: 15px; }
            .oqtb-block-card input:focus, .oqtb-block-card select:focus, .oqtb-block-card textarea:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(79, 110, 247, .1); }
            .oqtb-block-card textarea { min-height: 86px; resize: vertical; }
            .oqtb-subsection-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(320px, .72fr); gap: 20px; margin-top: 24px; }
            .oqtb-fieldset { position: relative; min-width: 0; padding: 22px 24px; border: 1px solid var(--border-light); border-radius: 14px; background: #fff; box-shadow: 0 2px 6px rgba(15, 23, 41, .04); }
            .oqtb-fieldset.content { margin-top: 20px; }
            .oqtb-section-accent { display: block; width: 44px; height: 4px; margin: 0 0 16px; border-radius: 999px; background: var(--accent); }
            .oqtb-fieldset.source .oqtb-section-accent { background: #f0a329; }
            .oqtb-fieldset.rules .oqtb-section-accent { background: #e55353; }
            .oqtb-fieldset h3 { margin: 0 0 14px; color: var(--faint); font-size: 12px; font-weight: 800; letter-spacing: .07em; text-transform: uppercase; }
            .oqtb-fieldset-grid { display: grid; gap: 12px; }
            .oqtb-fieldset-grid.four { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) 210px 90px; }
            .oqtb-fieldset-grid.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .oqtb-fieldset-grid.one { grid-template-columns: 1fr; }
            .oqtb-source-empty { padding: 15px 17px; border: 1px dashed var(--border); border-radius: 10px; background: #fafbfe; color: var(--muted); font-size: 14px; }
            .oqtb-rule-row { display: grid; gap: 0; }
            .oqtb-check.inline { display: flex; flex-direction: row; align-items: center; gap: 10px; min-height: 48px; padding: 8px 0; border: 0; border-radius: 0; color: var(--text); font-size: 15px; text-transform: none; letter-spacing: 0; }
            .oqtb-check.inline + .oqtb-check.inline { border-top: 1px solid var(--border-light); }
            .oqtb-check.inline input[type="checkbox"] { width: 18px; height: 18px; min-height: 18px; padding: 0; accent-color: var(--accent); }
            .oqtb-help, .oqtb-textarea small { margin-top: 7px; color: var(--faint); font-size: 12px; line-height: 1.45; }
            .oqtb-page-break-panel { align-items: center; gap: 16px; min-height: 145px; color: var(--faint); }
            .oqtb-block-card.expanded .oqtb-page-break-panel { display: flex; }
            .oqtb-page-break-panel > span { height: 1px; flex: 1; background: #d8deea; }
            .oqtb-page-break-panel > svg { width: 26px; height: 26px; }
            .oqtb-page-break-panel > strong { font-size: 16px; font-weight: 600; white-space: nowrap; }
            .oqtb-preview-page { max-width: 190mm; min-height: 250mm; margin: 0 auto; padding: 12mm 14mm; border: 1px solid #374151; color: #1f2937; font-family: Arial, sans-serif; }
            .oqtb-preview-doc-head { display: flex; justify-content: space-between; gap: 18px; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 2px solid #0f2340; }
            .oqtb-preview-heading { margin: 14px 0 8px; font-size: 15px; text-decoration: underline; }
            .oqtb-preview-kv { display: grid; grid-template-columns: 34% 1fr; gap: 8px; padding: 6px 0; border-bottom: 1px solid #e5e7eb; }
            .oqtb-preview-block { margin: 10px 0; line-height: 1.45; }
            .oqtb-preview-page-break { display: flex; align-items: center; gap: 8px; margin: 16px 0; color: #64748b; font-size: 11px; font-weight: 900; text-transform: uppercase; }
            @media (max-width: 1200px) {
                .oqtb-builder-layout { grid-template-columns: 1fr; }
                .oqtb-block-toolbar { position: static; width: 100%; }
                .oqtb-toolbar-buttons { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                .oqtb-subsection-grid { grid-template-columns: 1fr; }
            }
            @media (max-width: 760px) {
                .oqtb-shell { padding: 0 14px 48px; }
                .oqtb-topbar { align-items: flex-start; margin: 0 -14px 20px; padding: 18px 14px; }
                .oqtb-topbar h1 { font-size: 18px; white-space: normal; }
                .oqtb-actions { flex-direction: column; align-items: stretch; }
                .oqtb-primary, .oqtb-secondary { min-height: 44px; padding: 0 14px; font-size: 14px; }
                .oqtb-grid-3, .oqtb-fieldset-grid.four, .oqtb-fieldset-grid.two { grid-template-columns: 1fr; }
                .oqtb-setup-body { padding: 22px 18px; }
                .oqtb-setup-footer { padding: 16px 18px; }
                .oqtb-toolbar-buttons { grid-template-columns: 1fr; }
                .oqtb-block-card-head { grid-template-columns: 18px minmax(0, 1fr) auto auto; padding: 14px; }
                .oqtb-block-title-wrap { flex-wrap: wrap; gap: 7px; }
                .oqtb-block-title-wrap strong { width: 100%; font-size: 16px; }
                .oqtb-order-pill { display: none; }
            }
        `;
        style.textContent += `
            .oqtb-shell { max-width: 1540px; padding: 0 30px 52px; }
            .oqtb-topbar { margin: 0 -30px 18px; padding: 18px 30px; }
            .oqtb-topbar-left { gap: 15px; }
            .oqtb-back-button { width: 42px; height: 42px; flex-basis: 42px; border-radius: 10px; }
            .oqtb-back-button svg { width: 17px; height: 17px; }
            .oqtb-badge { margin-bottom: 4px; padding: 3px 9px; font-size: 10px; }
            .oqtb-badge svg { width: 12px; height: 12px; }
            .oqtb-topbar h1 { font-size: 20px; }
            .oqtb-actions { gap: 8px; }
            .oqtb-primary, .oqtb-secondary { min-height: 42px; padding: 0 16px; border-radius: 10px; font-size: 13px; }
            .oqtb-primary svg, .oqtb-secondary svg { width: 16px; height: 16px; }
            .oqtb-section-label { gap: 7px; margin-bottom: 11px; font-size: 12px; }
            .oqtb-section-label svg { width: 16px; height: 16px; }
            .oqtb-setup-card { margin-bottom: 26px; border-radius: 15px; }
            .oqtb-setup-body { padding: 22px 24px 18px; }
            .oqtb-grid-3 { grid-template-columns: minmax(0, 1fr) 230px 95px; gap: 14px; }
            .oqtb-description-row { margin-top: 15px; }
            .oqtb-card label { gap: 5px; font-size: 11px; }
            .oqtb-card input, .oqtb-card select, .oqtb-card textarea { min-height: 42px; padding: 8px 12px; border-radius: 9px; font-size: 13px; }
            .oqtb-textarea textarea { min-height: 68px; }
            .oqtb-setup-footer { padding: 12px 24px; }
            .oqtb-active-toggle { font-size: 13px !important; }
            .oqtb-toggle-track { width: 40px; height: 23px; }
            .oqtb-toggle-track i { top: 3px; left: 3px; width: 17px; height: 17px; }
            .oqtb-active-toggle input:checked + .oqtb-toggle-track i { transform: translateX(17px); }
            .oqtb-status-pill { padding: 4px 10px; font-size: 11px; }
            .oqtb-blocks-heading { margin-bottom: 15px; }
            .oqtb-blocks-heading h2 { gap: 8px; font-size: 18px; }
            .oqtb-blocks-heading h2 > svg { width: 20px; height: 20px; }
            .oqtb-blocks-heading h2 span { margin-left: 7px; font-size: 13px; }
            .oqtb-blocks-heading p { max-width: 850px; margin-top: 10px; padding: 10px 13px; border-radius: 9px; font-size: 12px; }
            .oqtb-builder-layout { grid-template-columns: minmax(0, 1fr) 330px; gap: 22px; }
            .oqtb-blocks { gap: 12px; }
            .oqtb-block-toolbar { width: 330px; border-radius: 15px; }
            .oqtb-palette-title { gap: 8px; padding: 15px 18px; font-size: 15px; }
            .oqtb-palette-title svg { width: 17px; height: 17px; }
            .oqtb-toolbar-group { padding: 14px 18px; }
            .oqtb-toolbar-group > span { margin-bottom: 7px; font-size: 10px; }
            .oqtb-toolbar-buttons { gap: 6px; }
            .oqtb-add-tile { grid-template-columns: 17px minmax(0, 1fr); min-height: 44px; padding: 7px 11px; border-radius: 8px; }
            .oqtb-add-tile > svg { width: 15px; height: 15px; }
            .oqtb-add-tile strong { font-size: 13px; }
            .oqtb-add-tile small { font-size: 10px; }
            .oqtb-block-card { border-radius: 14px; }
            .oqtb-block-card-head { grid-template-columns: 18px minmax(0, 1fr) auto auto auto; gap: 10px; min-height: 62px; padding: 11px 17px; }
            .oqtb-drag-handle svg { width: 15px; height: 15px; }
            .oqtb-block-title-wrap { gap: 10px; }
            .oqtb-block-title-wrap strong { font-size: 14px; }
            .oqtb-type-pill { padding: 4px 9px; font-size: 9px; }
            .oqtb-order-pill { min-width: 38px; height: 26px; font-size: 11px; }
            .oqtb-chevron svg { width: 17px; height: 17px; }
            .oqtb-danger { width: 28px; height: 28px; font-size: 21px; }
            .oqtb-block-card-body { padding: 17px 20px 20px; }
            .oqtb-block-setup { padding-bottom: 15px; }
            .oqtb-block-card label { gap: 5px; font-size: 10px; }
            .oqtb-block-card input, .oqtb-block-card select, .oqtb-block-card textarea { min-height: 40px; padding: 8px 11px; border-radius: 9px; font-size: 13px; }
            .oqtb-block-card textarea { min-height: 66px; }
            .oqtb-fieldset-grid.four { grid-template-columns: minmax(0, 1fr) minmax(0, .8fr) 170px 72px; gap: 9px; }
            .oqtb-subsection-grid { grid-template-columns: minmax(0, 1fr) minmax(250px, .65fr); gap: 13px; margin-top: 16px; }
            .oqtb-fieldset { padding: 15px 17px; border-radius: 11px; }
            .oqtb-fieldset.content { margin-top: 13px; }
            .oqtb-section-accent { width: 34px; height: 3px; margin-bottom: 11px; }
            .oqtb-fieldset h3 { margin-bottom: 9px; font-size: 10px; }
            .oqtb-source-empty { padding: 11px 13px; font-size: 12px; }
            .oqtb-check.inline { min-height: 38px; padding: 6px 0; font-size: 12px; }
            .oqtb-page-break-panel { min-height: 100px; }
            .oqtb-page-break-panel > svg { width: 20px; height: 20px; }
            .oqtb-page-break-panel > strong { font-size: 13px; }
            .oqtb-root input[type="checkbox"] { appearance: none !important; -webkit-appearance: none !important; width: 17px !important; height: 17px !important; min-width: 17px !important; min-height: 17px !important; margin: 0 !important; padding: 0 !important; border: 1px solid #cbd2df !important; border-radius: 4px !important; background: #fff !important; box-shadow: none !important; }
            .oqtb-root input[type="checkbox"]::before, .oqtb-root input[type="checkbox"]::after { content: none !important; display: none !important; }
            .oqtb-root input[type="checkbox"]:checked { border-color: var(--accent) !important; background-color: var(--accent) !important; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 14 14'%3E%3Cpath d='M3 7.2 5.6 10 11 4.2' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") !important; background-position: center !important; background-repeat: no-repeat !important; background-size: 13px 13px !important; }
            .oqtb-active-toggle input[type="checkbox"] { position: absolute !important; width: 1px !important; height: 1px !important; min-width: 1px !important; min-height: 1px !important; opacity: 0 !important; pointer-events: none !important; }
        `;
        document.head.appendChild(style);
    }

    function injectLegacyStyles() {
        if (document.getElementById("oqtb-style")) return;
        const style = document.createElement("style");
        style.id = "oqtb-style";
        style.textContent = `.oqtb-root{background:#f6f8fb;min-height:100vh}.oqtb-shell{width:min(1440px,100%);margin:0 auto;padding:18px clamp(12px,2vw,24px) 56px;color:#172033}.oqtb-breadcrumb{display:flex;gap:7px;margin-bottom:10px;color:#64748b;font-size:12px;font-weight:800}.oqtb-breadcrumb a{color:#2563eb;text-decoration:none}.oqtb-hero,.oqtb-card{border:1px solid #dbe5ef;border-radius:18px;background:#fff;box-shadow:0 10px 24px rgba(15,23,42,.055)}.oqtb-hero{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;padding:20px 22px;background:linear-gradient(135deg,#fff 0%,#f0f7ff 100%)}.oqtb-hero span{color:#2563eb;font-size:11px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.oqtb-hero h1{margin:5px 0 0;font-size:clamp(24px,2.5vw,34px);letter-spacing:-.04em}.oqtb-hero p{max-width:780px;margin:7px 0 0;color:#475569;font-size:13px}.oqtb-actions{display:flex;gap:8px;flex-wrap:wrap}.oqtb-primary,.oqtb-secondary{min-height:36px;border-radius:10px;padding:0 14px;font-size:13px;font-weight:900;cursor:pointer}.oqtb-primary{border:0;background:#2563eb;color:#fff}.oqtb-secondary{border:1px solid #bfdbfe;background:#eff6ff;color:#1d4ed8}.oqtb-card{padding:16px;margin-top:12px}.oqtb-grid-3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.oqtb-grid-2{display:grid;grid-template-columns:2fr 1fr;gap:12px}.mt{margin-top:12px}.oqtb-card label{display:grid;gap:5px;font-size:12px;font-weight:800;color:#475569}.oqtb-card input,.oqtb-card select,.oqtb-card textarea{min-height:36px;border:1px solid #cbd5e1;border-radius:10px;padding:8px 10px;background:#fff}.oqtb-textarea{grid-column:1/-1}.oqtb-textarea textarea{min-height:82px}.oqtb-check{display:flex!important;align-items:center;gap:8px}.oqtb-check input{min-height:auto}.oqtb-check.inline{align-self:end}.oqtb-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:12px}.oqtb-head h2{margin:0}.oqtb-head p{margin:5px 0 0;color:#64748b}.oqtb-blocks{display:grid;gap:10px}.oqtb-block{position:relative;display:grid;grid-template-columns:1.2fr 1fr 160px 90px;gap:10px;border:1px solid #e2e8f0;border-radius:14px;padding:12px;background:#f8fafc}.oqtb-danger{position:absolute;right:8px;top:8px;border:0;background:#fee2e2;color:#991b1b;border-radius:999px;width:26px;height:26px;font-weight:900}.oqtb-empty{padding:24px;text-align:center;color:#64748b}@media(max-width:900px){.oqtb-hero,.oqtb-head{display:block}.oqtb-grid-3,.oqtb-grid-2,.oqtb-block{grid-template-columns:1fr}.oqtb-actions{margin-top:10px}}`;
        style.textContent += `.oqtb-shell,.oqtb-card,.oqtb-block,.oqtb-block *{min-width:0}.oqtb-block{grid-template-columns:minmax(180px,1.2fr) minmax(130px,.8fr) minmax(140px,.8fr) 88px;align-items:end;overflow:hidden}.oqtb-block label{min-width:0}.oqtb-block input,.oqtb-block select,.oqtb-block textarea{width:100%;max-width:100%;min-width:0}.oqtb-block .oqtb-textarea{grid-column:1/-1}.oqtb-actions{max-width:100%;justify-content:flex-end}.oqtb-preview-page{max-width:190mm;margin:0 auto;border:1px solid #374151;padding:12mm 14mm;font-family:Arial,sans-serif;color:#1f2937;min-height:250mm}.oqtb-preview-doc-head{display:flex;justify-content:space-between;gap:18px;border-bottom:2px solid #0F2340;padding-bottom:8px;margin-bottom:12px}.oqtb-preview-doc-head strong{font-size:18px;color:#0F2340;text-transform:uppercase}.oqtb-preview-doc-head span{font-size:10px;color:#64748b}.oqtb-preview-heading{font-size:15px;text-decoration:underline;margin:14px 0 8px}.oqtb-preview-kv{display:grid;grid-template-columns:34% 1fr;gap:8px;border-bottom:1px solid #e5e7eb;padding:6px 0}.oqtb-preview-kv span{min-height:15px;border-bottom:1px dotted #9ca3af}.oqtb-preview-block{margin:10px 0;line-height:1.45}.oqtb-preview-block p{white-space:pre-line;min-height:32px;border:1px dotted #9ca3af;padding:5px}.oqtb-preview-page-break{display:flex;align-items:center;gap:8px;margin:16px 0;color:#64748b;font-size:11px;font-weight:900;text-transform:uppercase}.oqtb-preview-page-break:before,.oqtb-preview-page-break:after{content:"";height:1px;background:#cbd5e1;flex:1}@media(max-width:900px){.oqtb-block,.oqtb-grid-3,.oqtb-grid-2{grid-template-columns:1fr}.oqtb-head{display:block}.oqtb-actions{justify-content:flex-start;margin-top:10px}}`;
        style.textContent += `.oqtb-check input[type="checkbox"],.oqtb-block .oqtb-check input[type="checkbox"]{appearance:auto!important;width:18px!important;height:18px!important;min-width:18px!important;min-height:18px!important;max-width:18px!important;padding:0!important;margin:0!important;border-radius:4px;accent-color:#2563eb;flex:0 0 18px}.oqtb-check{min-height:44px;padding:8px 10px;border:1px solid #e2e8f0;border-radius:12px;background:#f8fafc}.oqtb-check.inline{min-height:36px;background:#fff}.oqtb-block{border-color:#dbe5ef;background:linear-gradient(180deg,#fff 0%,#fbfdff 100%);box-shadow:0 8px 18px rgba(15,23,42,.035)}.oqtb-block:hover{border-color:#bfdbfe;box-shadow:0 10px 22px rgba(37,99,235,.07)}.oqtb-block label span{color:#334155}.oqtb-card input:focus,.oqtb-card select:focus,.oqtb-card textarea:focus{outline:0;border-color:#60a5fa;box-shadow:0 0 0 3px rgba(37,99,235,.11)}`;
        style.textContent += `.oqtb-blocks{display:grid;gap:16px}.oqtb-block-card{border:1px solid #cbdff7;border-radius:18px;background:#fff;box-shadow:0 14px 32px rgba(15,23,42,.07);overflow:hidden}.oqtb-block-card-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;padding:14px 16px;background:linear-gradient(135deg,#0f2340 0%,#1d4ed8 100%);color:#fff}.oqtb-block-card-head>div{display:grid;gap:4px;min-width:0}.oqtb-block-card-head strong{font-size:16px;line-height:1.25;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.oqtb-block-card-head small{color:#bfdbfe;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.06em}.oqtb-type-pill{width:max-content;border:1px solid rgba(255,255,255,.28);border-radius:999px;background:rgba(255,255,255,.14);padding:3px 9px;color:#fff!important;font-size:10px!important;font-weight:900!important;letter-spacing:.08em;text-transform:uppercase}.oqtb-block-card-head .oqtb-danger{width:34px;height:34px;min-height:34px;border-radius:10px;background:rgba(239,68,68,.14);border:1px solid rgba(254,202,202,.55);color:#fff}.oqtb-block-card-body{display:grid;grid-template-columns:minmax(0,1fr) minmax(280px,.42fr);gap:12px;padding:14px;background:#f8fbff}.oqtb-fieldset{min-width:0;border:1px solid #dbeafe;border-radius:15px;background:#fff;padding:12px;box-shadow:0 6px 14px rgba(15,23,42,.035)}.oqtb-fieldset h3{margin:0 0 10px;color:#1e3a8a;font-size:12px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.oqtb-fieldset.setup,.oqtb-fieldset.content{grid-column:1/-1}.oqtb-fieldset-grid{display:grid;gap:10px}.oqtb-fieldset-grid.four{grid-template-columns:minmax(220px,1.3fr) minmax(160px,.9fr) minmax(150px,.8fr) 90px}.oqtb-fieldset-grid.three{grid-template-columns:repeat(3,minmax(0,1fr))}.oqtb-fieldset-grid.two{grid-template-columns:repeat(2,minmax(0,1fr))}.oqtb-rule-row{display:grid;gap:8px}.oqtb-block-card label{min-width:0}.oqtb-block-card label span{color:#475569;font-size:12px;font-weight:900}.oqtb-block-card input,.oqtb-block-card select,.oqtb-block-card textarea{width:100%;max-width:100%;min-width:0}.oqtb-block-card .oqtb-textarea{grid-column:auto}.oqtb-block-card .oqtb-textarea textarea{min-height:110px}.oqtb-block-card .oqtb-check{display:flex!important;align-items:center}.oqtb-block-card .oqtb-check input[type="checkbox"]{appearance:auto!important;width:18px!important;height:18px!important;min-width:18px!important;min-height:18px!important;padding:0!important;accent-color:#2563eb}.oqtb-fieldset.source{border-left:4px solid #38bdf8}.oqtb-fieldset.rules{border-left:4px solid #f59e0b}.oqtb-fieldset.content{border-left:4px solid #22c55e}@media(max-width:1100px){.oqtb-block-card-body,.oqtb-fieldset-grid.four,.oqtb-fieldset-grid.three,.oqtb-fieldset-grid.two{grid-template-columns:1fr}.oqtb-block-card-head strong{white-space:normal}}`;
        style.textContent += `.oqtb-fieldset-grid.one{grid-template-columns:1fr}.oqtb-help,.oqtb-textarea small{display:block;margin:7px 0 0;color:#64748b;font-size:11px;line-height:1.45}.oqtb-source-empty{border:1px dashed #cbd5e1;border-radius:12px;background:#f8fafc;color:#64748b;padding:12px;font-size:12px}.oqtb-fieldset.muted{border-style:dashed;background:#f8fafc;color:#64748b}.oqtb-fieldset.muted p{margin:0;font-size:12px;line-height:1.45}.oqtb-block-card{border-color:#d9e2ef;box-shadow:0 10px 24px rgba(15,23,42,.045)}.oqtb-block-card-head{background:#f8fafc!important;color:#172033!important;border-bottom:1px solid #e2e8f0}.oqtb-block-card-head small{color:#64748b!important}.oqtb-type-pill{background:#eef6ff!important;border-color:#bfdbfe!important;color:#1d4ed8!important}.oqtb-block-card-head .oqtb-danger{background:#fff!important;border-color:#fecaca!important;color:#b91c1c!important}.oqtb-block-card-body{background:#fbfdff}.oqtb-fieldset h3{color:#334155}.oqtb-fieldset.source{border-left-color:#7dd3fc}.oqtb-fieldset.rules{border-left-color:#fbbf24}.oqtb-fieldset.content{border-left-color:#86efac}.oqtb-primary{background:#2563eb}.oqtb-secondary{background:#f8fafc;border-color:#cbd5e1;color:#334155}`;
        style.textContent += `.oqtb-block-section{padding:14px}.oqtb-head{align-items:stretch;border:1px solid #e2e8f0;border-radius:14px;background:#f8fafc;padding:12px;margin-bottom:14px}.oqtb-head-copy{min-width:260px;max-width:720px}.oqtb-head-copy h2{font-size:20px}.oqtb-head-copy p{font-size:12px;line-height:1.45}.oqtb-block-toolbar{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:stretch;min-width:360px}.oqtb-add-buttons{display:grid;grid-template-columns:repeat(3,minmax(120px,1fr));gap:8px}.oqtb-block-toolbar .oqtb-secondary{min-height:38px;white-space:nowrap}.oqtb-add-break{border-style:dashed;background:#fff;color:#0f766e}.oqtb-blocks{gap:12px}.oqtb-block-card{position:relative;border-radius:14px;border-color:#cbd5e1}.oqtb-block-card:before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:#93c5fd}.oqtb-block-card:nth-child(4n+2):before{background:#86efac}.oqtb-block-card:nth-child(4n+3):before{background:#fbbf24}.oqtb-block-card:nth-child(4n+4):before{background:#c4b5fd}.oqtb-block-card-head{padding:10px 14px 10px 16px}.oqtb-block-card-head>div{gap:3px}.oqtb-block-card-head strong{font-size:14px}.oqtb-type-pill{padding:2px 8px;font-size:9px!important}.oqtb-block-card-head .oqtb-danger{width:30px;height:30px;min-height:30px}.oqtb-block-card-body{grid-template-columns:minmax(0,1fr) minmax(240px,.38fr);gap:9px;padding:10px 10px 10px 14px}.oqtb-fieldset{padding:10px;border-radius:12px;box-shadow:none}.oqtb-fieldset h3{margin-bottom:7px;font-size:11px}.oqtb-fieldset-grid{gap:8px}.oqtb-fieldset-grid.four{grid-template-columns:minmax(180px,1.2fr) minmax(140px,.85fr) minmax(145px,.8fr) 80px}.oqtb-card input,.oqtb-card select,.oqtb-card textarea{min-height:34px;padding:7px 9px}.oqtb-textarea textarea{min-height:64px}.oqtb-check{min-height:38px;padding:7px 9px}.oqtb-rule-row{gap:6px}@media(max-width:1100px){.oqtb-head{display:grid}.oqtb-block-toolbar{min-width:0;width:100%;grid-template-columns:1fr}.oqtb-add-buttons{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:700px){.oqtb-add-buttons{grid-template-columns:1fr}.oqtb-block-card-body,.oqtb-fieldset-grid.four,.oqtb-fieldset-grid.two{grid-template-columns:1fr}}`;
        style.textContent += `.oqtb-block-toolbar{width:min(620px,100%);min-width:0;display:grid!important;grid-template-columns:1fr;gap:8px;align-self:stretch}.oqtb-toolbar-group{border:1px solid #e2e8f0;border-radius:12px;background:#fff;padding:8px}.oqtb-toolbar-group>span{display:block;margin:0 0 6px;color:#64748b;font-size:10px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.oqtb-toolbar-buttons{display:grid;grid-template-columns:repeat(auto-fit,minmax(128px,1fr));gap:7px}.oqtb-add-tile{min-height:48px!important;height:auto!important;padding:7px 9px!important;display:grid;gap:2px;align-content:center;text-align:left;white-space:normal!important;line-height:1.15}.oqtb-add-tile strong{font-size:12px;color:#1f2937}.oqtb-add-tile small{font-size:10px;font-weight:700;color:#64748b}.oqtb-add-break{border-style:dashed!important;background:#f0fdfa!important;color:#0f766e!important}.oqtb-add-break strong{color:#0f766e}.oqtb-head{display:grid;grid-template-columns:minmax(280px,1fr) minmax(360px,620px);align-items:start}.oqtb-head-copy{min-width:0}.oqtb-head-copy p{max-width:680px}@media(max-width:980px){.oqtb-head{grid-template-columns:1fr}.oqtb-block-toolbar{width:100%}}@media(max-width:560px){.oqtb-toolbar-buttons{grid-template-columns:1fr}.oqtb-add-tile{text-align:center}}`;
        style.textContent += `.oqtb-root{--oqtb-bg:#f0f2f7;--oqtb-surface:#fff;--oqtb-muted-surface:#f5f6fa;--oqtb-hover:#f8f9fc;--oqtb-border:#dfe3ed;--oqtb-border-light:#e8ecf4;--oqtb-text:#0f1729;--oqtb-muted:#5b6582;--oqtb-faint:#8c93a8;--oqtb-accent:#4f6ef7;--oqtb-accent-bg:#eef1ff;--oqtb-grad:linear-gradient(135deg,#4f6ef7,#7c5cf5);--oqtb-purple:#7c5cf5;--oqtb-purple-bg:#f3f0ff;--oqtb-orange:#f59e0b;--oqtb-orange-bg:#fffbeb;--oqtb-orange-bdr:#fde68a;--oqtb-teal:#14b8a6;--oqtb-teal-bg:#f0fdfa;--oqtb-green:#22c55e;--oqtb-green-bg:#ecfdf5;--oqtb-red:#ef4444;--oqtb-red-bg:#fef2f2;background:var(--oqtb-bg);font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.oqtb-shell{width:min(1200px,100%);padding:16px 24px 64px;color:var(--oqtb-text)}.oqtb-breadcrumb{display:flex;align-items:center;gap:7px;margin-bottom:12px;color:var(--oqtb-faint);font-weight:600}.oqtb-breadcrumb a{display:inline-flex;align-items:center;gap:5px;color:var(--oqtb-muted)}.oqtb-breadcrumb svg{width:15px;height:15px}.oqtb-hero{position:sticky;top:0;z-index:10;margin:0 -24px 18px;padding:12px 24px;border-width:0 0 1px;border-color:var(--oqtb-border-light);border-radius:0;background:rgba(255,255,255,.96);box-shadow:0 1px 4px rgba(15,23,41,.06);backdrop-filter:saturate(1.2) blur(8px)}.oqtb-hero span{display:inline-flex;align-items:center;gap:5px;margin-bottom:2px;border-radius:999px;background:var(--oqtb-accent-bg);color:var(--oqtb-accent);padding:2px 8px;font-size:10px}.oqtb-hero span svg{width:12px;height:12px}.oqtb-hero h1{font-size:16px;font-weight:800;letter-spacing:-.01em}.oqtb-hero p{display:none}.oqtb-actions{gap:8px}.oqtb-primary,.oqtb-secondary{display:inline-flex;align-items:center;justify-content:center;gap:6px;border-radius:10px;font-weight:700}.oqtb-primary{background:var(--oqtb-grad);box-shadow:0 2px 8px rgba(79,110,247,.3)}.oqtb-primary:hover{transform:translateY(-1px);box-shadow:0 4px 14px rgba(79,110,247,.35)}.oqtb-secondary{border-color:var(--oqtb-border);background:#fff;color:var(--oqtb-muted)}.oqtb-secondary:hover{border-color:var(--oqtb-accent);color:var(--oqtb-accent);background:var(--oqtb-accent-bg)}.oqtb-primary svg,.oqtb-secondary svg{width:15px;height:15px}.oqtb-section-label{display:flex;align-items:center;gap:6px;margin:0 0 8px 2px;color:var(--oqtb-faint);font-size:11px;font-weight:800;letter-spacing:.06em;text-transform:uppercase}.oqtb-section-label svg{width:14px;height:14px}.oqtb-card{border-color:var(--oqtb-border-light);border-radius:14px;box-shadow:0 1px 4px rgba(15,23,41,.06),0 1px 2px rgba(15,23,41,.03)}.oqtb-setup-card{overflow:hidden;padding:0}.oqtb-setup-card>.oqtb-grid-3{padding:20px 22px 0}.oqtb-setup-card>.oqtb-grid-2{padding:0 22px 20px}.oqtb-card label{font-size:11px;letter-spacing:.03em;text-transform:uppercase;color:var(--oqtb-faint)}.oqtb-card input,.oqtb-card select,.oqtb-card textarea{border-color:var(--oqtb-border);border-radius:8px;color:var(--oqtb-text);transition:all .15s cubic-bezier(.4,0,.2,1)}.oqtb-card input:focus,.oqtb-card select:focus,.oqtb-card textarea:focus{border-color:var(--oqtb-accent);box-shadow:0 0 0 3px rgba(79,110,247,.1)}.oqtb-block-section{padding:0;background:transparent;border:0;box-shadow:none}.oqtb-head{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:20px;align-items:start;border:0;background:transparent;padding:0;margin:24px 0 16px}.oqtb-head-copy h2{display:flex;align-items:center;gap:8px;font-size:15px;font-weight:800}.oqtb-head-copy h2:before{content:"";width:18px;height:18px;border-radius:5px;background:var(--oqtb-accent-bg);box-shadow:inset 0 0 0 5px var(--oqtb-accent-bg)}.oqtb-head-copy p{margin-top:8px;padding:8px 14px;border:1px solid var(--oqtb-border-light);border-radius:8px;background:var(--oqtb-muted-surface);color:var(--oqtb-faint);font-size:12px}.oqtb-block-toolbar{position:sticky;top:72px;width:300px!important;border:1px solid var(--oqtb-border-light);border-radius:14px;background:#fff;box-shadow:0 1px 4px rgba(15,23,41,.06),0 1px 2px rgba(15,23,41,.03);overflow:hidden}.oqtb-palette-title{display:flex;align-items:center;gap:8px;padding:14px 16px;border-bottom:1px solid var(--oqtb-border-light);font-size:13px;font-weight:800}.oqtb-palette-title svg{width:16px;height:16px;color:var(--oqtb-accent)}.oqtb-toolbar-group{border:0;border-radius:0;padding:12px 16px;background:#fff}.oqtb-toolbar-group+.oqtb-toolbar-group{border-top:1px solid var(--oqtb-border-light)}.oqtb-toolbar-group>span{margin-bottom:6px;color:var(--oqtb-faint);font-size:9px;letter-spacing:.08em}.oqtb-toolbar-buttons{display:flex;flex-direction:column;gap:5px}.oqtb-add-tile{grid-template-columns:auto minmax(0,1fr);display:grid!important;align-items:center;gap:8px;min-height:42px!important;border-color:var(--oqtb-border-light)!important;border-radius:8px!important;background:#fff!important;color:var(--oqtb-text)!important;text-align:left!important;cursor:pointer;transition:all .15s cubic-bezier(.4,0,.2,1)}.oqtb-add-tile>svg{width:15px;height:15px;color:var(--oqtb-faint);flex-shrink:0}.oqtb-add-tile strong{font-size:12px;color:var(--oqtb-text)}.oqtb-add-tile small{font-size:10px;color:var(--oqtb-faint);font-weight:500}.oqtb-add-tile:hover{transform:translateX(2px);border-color:var(--oqtb-accent)!important;background:var(--oqtb-accent-bg)!important;color:var(--oqtb-accent)!important}.oqtb-add-tile:hover svg,.oqtb-add-tile:hover strong{color:var(--oqtb-accent)}.oqtb-add-tile.type-source{border-color:var(--oqtb-orange-bdr)!important;background:var(--oqtb-orange-bg)!important}.oqtb-add-tile.type-source svg,.oqtb-add-tile.type-source:hover strong{color:var(--oqtb-orange)}.oqtb-add-tile.type-layout{border-color:#c4f0e6!important;background:var(--oqtb-teal-bg)!important}.oqtb-add-tile.type-layout svg,.oqtb-add-tile.type-layout:hover strong{color:#0f766e}.oqtb-add-break{border-style:dashed!important}.oqtb-blocks{display:grid;gap:12px}.oqtb-block-card{border-color:var(--oqtb-border-light);border-radius:14px;box-shadow:0 1px 4px rgba(15,23,41,.06),0 1px 2px rgba(15,23,41,.03)}.oqtb-block-card:hover{box-shadow:0 4px 16px rgba(15,23,41,.07)}.oqtb-block-card:before{display:none}.oqtb-block-card-head{padding:12px 16px;background:#fff!important;color:var(--oqtb-text)!important}.oqtb-block-card-head:hover{background:var(--oqtb-hover)!important}.oqtb-type-pill{border:0!important;border-radius:999px!important;padding:3px 9px!important;background:var(--oqtb-accent-bg)!important;color:var(--oqtb-accent)!important;font-size:10px!important}.oqtb-block-card-head strong{font-size:13px}.oqtb-block-card-body{padding:16px 18px;background:var(--oqtb-muted-surface);grid-template-columns:minmax(0,1fr) minmax(220px,.42fr)}.oqtb-fieldset{border-color:var(--oqtb-border-light);border-radius:10px;box-shadow:0 1px 2px rgba(15,23,41,.04)}.oqtb-fieldset h3{font-size:10px;color:var(--oqtb-faint);letter-spacing:.06em}.oqtb-fieldset.source{border-left-color:var(--oqtb-orange)}.oqtb-fieldset.rules{border-left-color:var(--oqtb-red)}.oqtb-fieldset.content{border-left-color:var(--oqtb-accent)}.oqtb-check{border-color:var(--oqtb-border-light);border-radius:8px;background:#fff;text-transform:none;letter-spacing:0;color:var(--oqtb-text)}.oqtb-check input[type="checkbox"]{accent-color:var(--oqtb-accent)}@media(max-width:980px){.oqtb-shell{padding:12px}.oqtb-hero{position:relative;margin:0 0 16px;padding:16px;border:1px solid var(--oqtb-border-light);border-radius:14px}.oqtb-hero p{display:block}.oqtb-head{grid-template-columns:1fr}.oqtb-block-toolbar{position:static;width:100%!important}.oqtb-toolbar-buttons{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}.oqtb-block-card-body{grid-template-columns:1fr}}@media(max-width:640px){.oqtb-hero{display:block}.oqtb-actions{justify-content:flex-start;margin-top:12px}.oqtb-grid-3,.oqtb-grid-2{grid-template-columns:1fr}.oqtb-toolbar-buttons{grid-template-columns:1fr}}`;
        style.textContent += `.oqtb-root .page-head,.oqtb-root .page-title{display:none!important}.oqtb-root{background:#eef1f7!important}.oqtb-shell{width:100%!important;max-width:1848px!important;margin:0 auto!important;padding:32px 44px 72px!important}.oqtb-breadcrumb{display:none!important}.oqtb-hero{position:static!important;top:auto!important;margin:-32px -44px 28px!important;padding:26px 44px!important;border:0!important;border-bottom:1px solid var(--oqtb-border-light)!important;border-radius:0!important;background:#fff!important;box-shadow:0 2px 6px rgba(15,23,41,.06)!important}.oqtb-hero h1{margin:3px 0 0!important;font-size:26px!important;line-height:1.2!important}.oqtb-hero span{height:30px!important;padding:5px 13px!important;font-size:12px!important}.oqtb-actions .oqtb-secondary,.oqtb-actions .oqtb-primary{min-height:52px!important;padding:0 22px!important;border-radius:13px!important;font-size:16px!important}.oqtb-section-label{margin:0 0 16px 4px!important;font-size:15px!important}.oqtb-setup-card{border-radius:18px!important;margin-bottom:40px!important}.oqtb-setup-card>.oqtb-grid-3{grid-template-columns:minmax(0,1fr) 290px 112px!important;padding:32px 36px 0!important}.oqtb-setup-card>.oqtb-grid-2{grid-template-columns:1fr!important;padding:0 36px 32px!important}.oqtb-setup-card .oqtb-check{margin-top:16px!important;max-width:220px!important}.oqtb-card label{font-size:13px!important}.oqtb-card input,.oqtb-card select,.oqtb-card textarea{min-height:52px!important;border-radius:12px!important;font-size:16px!important;padding:11px 16px!important}.oqtb-textarea textarea{min-height:90px!important}.oqtb-block-section{margin-top:0!important;padding:0!important}.oqtb-head-copy{max-width:none!important;margin-bottom:18px!important}.oqtb-head-copy h2{display:flex!important;align-items:center!important;gap:10px!important;margin:0!important;font-size:24px!important}.oqtb-head-copy h2>svg{width:25px!important;height:25px!important;color:var(--oqtb-accent)!important}.oqtb-head-copy h2 span{margin-left:14px!important;color:var(--oqtb-accent)!important;font-size:16px!important;font-weight:700!important}.oqtb-head-copy h2:before{display:none!important}.oqtb-head-copy p{max-width:1000px!important;margin:16px 0 0!important;padding:14px 22px!important;border-radius:12px!important;background:#f5f7fb!important;color:#8c93a8!important;font-size:18px!important;line-height:1.45!important}.oqtb-builder-layout{display:grid!important;grid-template-columns:minmax(0,1fr) 420px!important;gap:32px!important;align-items:start!important}.oqtb-blocks{min-width:0!important;display:grid!important;gap:20px!important}.oqtb-block-toolbar{position:sticky!important;top:24px!important;width:420px!important;min-width:0!important;border-radius:18px!important;box-shadow:0 8px 22px rgba(15,23,41,.08)!important}.oqtb-palette-title{padding:22px 24px!important;font-size:20px!important}.oqtb-palette-title svg{width:23px!important;height:23px!important}.oqtb-toolbar-group{padding:22px 24px!important}.oqtb-toolbar-group>span{font-size:13px!important;margin-bottom:12px!important}.oqtb-toolbar-buttons{gap:10px!important}.oqtb-add-tile{min-height:58px!important;border-radius:11px!important;padding:12px 16px!important}.oqtb-add-tile>svg{width:20px!important;height:20px!important}.oqtb-add-tile strong{font-size:17px!important}.oqtb-add-tile small{font-size:13px!important}.oqtb-block-card{border:1px solid var(--oqtb-border-light)!important;border-radius:18px!important;background:#fff!important;box-shadow:0 6px 16px rgba(15,23,41,.07)!important;overflow:hidden!important}.oqtb-block-card-head{display:grid!important;grid-template-columns:22px auto minmax(0,1fr) auto auto auto!important;align-items:center!important;gap:14px!important;min-height:84px!important;padding:18px 26px!important;cursor:pointer!important;background:#fff!important;border-bottom:0!important;color:var(--oqtb-text)!important}.oqtb-drag-handle{display:flex!important;color:#c4cad7!important}.oqtb-drag-handle svg{width:18px!important;height:18px!important}.oqtb-block-title-wrap{display:flex!important;align-items:center!important;gap:16px!important;min-width:0!important}.oqtb-block-title-wrap strong{font-size:20px!important;font-weight:800!important;overflow:hidden!important;text-overflow:ellipsis!important;white-space:nowrap!important}.oqtb-type-pill{border:0!important;border-radius:999px!important;padding:7px 13px!important;font-size:13px!important;letter-spacing:.06em!important;flex:0 0 auto!important}.oqtb-block-card.type-heading .oqtb-type-pill{background:#eef1ff!important;color:#4f6ef7!important}.oqtb-block-card.type-paragraph .oqtb-type-pill{background:#f3f0ff!important;color:#7c5cf5!important}.oqtb-block-card.type-key-value .oqtb-type-pill{background:#fffbeb!important;color:#92400e!important;border:1px solid #fde68a!important}.oqtb-block-card.type-list .oqtb-type-pill{background:#f0fdfa!important;color:#0f766e!important}.oqtb-block-card.type-quotation-field .oqtb-type-pill,.oqtb-block-card.type-annex-field .oqtb-type-pill{background:#fff8e1!important;color:#b45309!important;border:1px solid #fde68a!important}.oqtb-block-card.type-manual-area .oqtb-type-pill{background:#eafaf7!important;color:#0f766e!important}.oqtb-block-card.type-page-break .oqtb-type-pill{background:#fef2f2!important;color:#ef4444!important}.oqtb-order-pill{display:inline-flex!important;align-items:center!important;justify-content:center!important;min-width:48px!important;height:34px!important;border-radius:999px!important;background:#f3f5fb!important;color:#8c93a8!important;font-size:16px!important;font-weight:800!important}.oqtb-chevron{display:flex!important;color:#8c93a8!important;transition:transform .18s cubic-bezier(.4,0,.2,1)!important}.oqtb-chevron svg{width:22px!important;height:22px!important}.oqtb-block-card.expanded .oqtb-chevron{transform:rotate(180deg)!important}.oqtb-danger{width:34px!important;height:34px!important;min-height:34px!important;border-radius:10px!important;border:0!important;background:transparent!important;color:#c4cad7!important;font-size:28px!important;line-height:1!important}.oqtb-danger:hover{background:#fef2f2!important;color:#ef4444!important}.oqtb-block-card-body{display:none!important;padding:22px 26px 28px!important;background:#f5f6fa!important;border-top:1px solid var(--oqtb-border-light)!important;grid-template-columns:minmax(0,1fr) 430px!important;gap:18px!important}.oqtb-block-card.expanded .oqtb-block-card-body{display:grid!important}.oqtb-fieldset{border-radius:14px!important;padding:18px!important}.oqtb-fieldset.setup,.oqtb-fieldset.content{grid-column:1/-1!important}.oqtb-fieldset-grid.four{grid-template-columns:minmax(0,1fr) minmax(0,1fr) minmax(220px,.7fr) 110px!important}.oqtb-fieldset-grid.two{grid-template-columns:repeat(2,minmax(0,1fr))!important}.oqtb-source-empty{font-size:15px!important;padding:16px 20px!important}.oqtb-help,.oqtb-textarea small{font-size:13px!important}.oqtb-check.inline{min-height:50px!important}@media(max-width:1200px){.oqtb-builder-layout{grid-template-columns:1fr!important}.oqtb-block-toolbar{position:static!important;width:100%!important}.oqtb-toolbar-buttons{display:grid!important;grid-template-columns:repeat(auto-fit,minmax(190px,1fr))!important}.oqtb-block-card-body{grid-template-columns:1fr!important}}@media(max-width:760px){.oqtb-shell{padding:18px 14px 48px!important}.oqtb-hero{margin:-18px -14px 20px!important;padding:18px 14px!important;display:block!important}.oqtb-actions{justify-content:flex-start!important;margin-top:14px!important}.oqtb-setup-card>.oqtb-grid-3,.oqtb-setup-card>.oqtb-grid-2{grid-template-columns:1fr!important;padding-left:18px!important;padding-right:18px!important}.oqtb-block-card-head{grid-template-columns:18px minmax(0,1fr) auto auto!important}.oqtb-block-title-wrap{grid-column:2/3;gap:8px;flex-wrap:wrap}.oqtb-order-pill{grid-column:3}.oqtb-chevron{grid-column:4}.oqtb-danger{grid-column:4;grid-row:2}.oqtb-fieldset-grid.four,.oqtb-fieldset-grid.two{grid-template-columns:1fr!important}}`;
        style.textContent += `.oqtb-block-card-head{grid-template-columns:22px minmax(0,1fr) auto auto auto!important}.oqtb-block-title-wrap{grid-column:auto!important}.oqtb-order-pill{grid-column:auto!important}.oqtb-chevron{grid-column:auto!important}@media(max-width:760px){.oqtb-block-card-head{grid-template-columns:18px minmax(0,1fr) auto auto!important}.oqtb-block-title-wrap{grid-column:2/3!important}.oqtb-order-pill{grid-column:3!important}.oqtb-chevron{grid-column:4!important}.oqtb-danger{grid-column:4!important;grid-row:2!important}}`;
        document.head.appendChild(style);
    }
})();
