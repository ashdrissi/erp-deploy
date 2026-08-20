(function () {
    const STATE = { targets: [], availableTargets: [], template: null, activeStep: "basics", expandedFields: new Set(), loading: false };
    const FIELD_TYPES = ["Section Break", "Column Break", "Data", "Small Text", "Text", "Text Editor", "Date", "Datetime", "Time", "Int", "Float", "Currency", "Check", "Select", "Link", "Attach", "Attach Image", "Signature", "HTML"];
    const STATUS_COLORS = ["Gray", "Blue", "Green", "Orange", "Red", "Purple"];
    const COPY_DESTINATIONS = {
        Opportunity: ["Sales Order", "Sales Order Technical List Revision"],
        Quotation: ["Sales Order", "Sales Order Technical List Revision"],
        "Sales Order": ["Project", "Sales Order Technical List Revision"],
    };
    const STEPS = [
        ["basics", "Basics"],
        ["targets", "Target Documents"],
        ["fields", "Fields & Layout"],
        ["statuses", "Statuses"],
        ["print", "Print"],
    ];

    frappe.pages["document-template-builder"].on_page_load = function (wrapper) {
        const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Document Template Builder"), single_column: true });
        wrapper.page = page;
        page.main.addClass("odtb-root");
        injectStyles();
        load(page);
    };

    frappe.pages["document-template-builder"].on_page_show = function (wrapper) {
        if (wrapper.page) load(wrapper.page);
    };

    function blankTemplate() {
        return { name: "", template_name: "", is_active: 1, display_order: 100, print_title: "", print_header: "", print_footer: "", targets: [], fields: [], statuses: [{ status_label: "", color: "Gray", is_default: 1, is_complete: 0, display_order: 1 }] };
    }

    async function load(page) {
        const route = frappe.get_route();
        const name = route[1] || "new";
        const boot = await frappe.call({ method: "orderlift.document_templates.get_template_manager_bootstrap" });
        STATE.targets = (boot.message || {}).targets || [];
        STATE.availableTargets = (boot.message || {}).available_targets || [];
        if (name && name !== "new") {
            const res = await frappe.call({ method: "orderlift.document_templates.get_template", args: { name } });
            STATE.template = res.message || blankTemplate();
        } else if (!STATE.template || STATE.template.name) {
            STATE.template = blankTemplate();
        }
        render(page);
    }

    function render(page) {
        const template = STATE.template || blankTemplate();
        page.main.html(`
            <div class="odtb-shell">
                <nav class="odtb-breadcrumb"><a href="/app/document-template-manager">${esc(__("Document Templates"))}</a><span>/</span><strong>${esc(template.name || __("New Template"))}</strong></nav>
                <section class="odtb-hero">
                    <div><span>${esc(__("Template Builder"))}</span><h1>${esc(template.template_name || __("New Template"))}</h1><p>${esc(__("Build the form tab users will fill inside each target document."))}</p></div>
                    <div class="odtb-actions"><button type="button" class="odtb-secondary" data-back="1">${esc(__("Back to list"))}</button><button type="button" class="odtb-secondary" data-preview-template="1">${esc(__("Preview"))}</button>${template.name ? `<button type="button" class="btn btn-danger btn-sm" data-delete-template="1">${esc(__("Delete Template"))}</button>` : ""}<button type="button" class="odtb-primary" data-save="1">${esc(__("Save Template"))}</button></div>
                </section>
                <section class="odtb-steps">${STEPS.map(([key, label]) => `<button type="button" class="${STATE.activeStep === key ? "active" : ""}" data-step="${esc(key)}"><span>${esc(__(label))}</span></button>`).join("")}</section>
                <section class="odtb-workspace">${stepMarkup(template)}</section>
            </div>
        `);
        bind(page);
    }

    function stepMarkup(template) {
        if (STATE.activeStep === "targets") return targetsStep(template);
        if (STATE.activeStep === "fields") return fieldsStep(template);
        if (STATE.activeStep === "statuses") return statusesStep(template);
        if (STATE.activeStep === "print") return printStep(template);
        return basicsStep(template);
    }

    function basicsStep(template) {
        return `<article class="odtb-card"><div class="odtb-card-head"><h2>${esc(__("Basics"))}</h2><p>${esc(__("Name and activate this template."))}</p></div><div class="odtb-grid-3">${input("template_name", __("Template Name"), template.template_name, "text", true)}${input("display_order", __("Display Order"), template.display_order || 100, "number")}<label class="odtb-check"><input type="checkbox" data-field="is_active" ${template.is_active ? "checked" : ""}/><span>${esc(__("Active"))}</span></label></div></article>`;
    }

    function targetsStep(template) {
        const rows = template.targets || [];
        const selected = new Set(rows.map((target) => target.target_doctype || target.doctype));
        const available = STATE.availableTargets.filter((doctype) => !selected.has(doctype));
        return `<article class="odtb-card"><div class="odtb-card-head with-action"><div><h2>${esc(__("Target Documents"))}</h2><p>${esc(__("Choose where this annex is filled, then choose where its filled copy goes after submit."))}</p></div><div class="odtb-mini-actions"><select data-new-target><option value="">${esc(__("Select DocType"))}</option>${options(available, "")}</select><button type="button" class="odtb-secondary" data-add-target="1">${esc(__("Add Target"))}</button></div></div><div class="odtb-status-builder">${rows.length ? rows.map(targetRow).join("") : emptyRow(__("Add at least one target DocType."))}</div></article>`;
    }

    function targetRow(row, index) {
        const doctype = row.target_doctype || row.doctype || "";
        return `<article class="odtb-status-card" data-target-index="${index}"><div class="odtb-status-fields target-settings"><label><span>${esc(__("DocType"))}</span><input data-row-field="target_doctype" value="${esc(doctype)}" readonly /></label>${input("display_order", __("Order"), row.display_order || index + 1, "number", false, true)}${copyDestinationControls(row, doctype)}${check("must_be_complete", __("Must Be Complete Before Submit"), row.must_be_complete, __("This document cannot be submitted until this annex, or its configured copy, is complete."))}</div><button type="button" class="odtb-danger" data-remove-target="${index}">&times;</button></article>`;
    }

    function copyDestinationControls(row, doctype) {
        const destinations = COPY_DESTINATIONS[doctype] || [];
        const selected = new Set(parseCopyDestinations(row));
        if (!destinations.length) {
            return `<div class="odtb-copy-targets muted"><span>${esc(__("Copy To After Submit"))}</span><p>${esc(__("No downstream copy target for this document."))}</p></div>`;
        }
        const hint = doctype === "Opportunity"
            ? __("Opportunity annexes are shared to draft Quotations automatically. On Quotation submit, copy the filled annex to:")
            : __("When this document is submitted, copy the filled annex to:");
        return `<div class="odtb-copy-targets"><span>${esc(__("Copy To After Submit"))}</span><p>${esc(hint)}</p><div>${destinations.map((target) => `<label class="odtb-copy-chip"><input type="checkbox" data-copy-destination="${esc(target)}" ${selected.has(target) ? "checked" : ""}/><span>${esc(__(target))}</span></label>`).join("")}</div></div>`;
    }

    function parseCopyDestinations(row) {
        const raw = row.copy_to_doctypes || "";
        if (Array.isArray(raw)) return raw.filter(Boolean);
        const values = String(raw || "").split(/[\n,]+/).map((value) => value.trim()).filter(Boolean);
        if (!values.length && (row.copy_after_submit || row.allow_execution_copy || row.allow_import_from_sales_order)) {
            return COPY_DESTINATIONS[row.target_doctype || row.doctype] || [];
        }
        return values;
    }

    function fieldsStep(template) {
        const rows = template.fields || [];
        return `<article class="odtb-card"><div class="odtb-card-head with-action"><div><h2>${esc(__("Fields & Layout"))}</h2><p>${esc(__("Use sections and column breaks to build a dynamic one- or two-column document."))}</p></div><div class="odtb-mini-actions"><button type="button" class="odtb-secondary" data-add-layout="Section Break">${esc(__("Section"))}</button><button type="button" class="odtb-secondary" data-add-layout="Column Break">${esc(__("Column"))}</button><button type="button" class="odtb-secondary" data-add-field="1">${esc(__("Field"))}</button><button type="button" class="odtb-secondary" data-add-special="Attach">${esc(__("File"))}</button><button type="button" class="odtb-secondary" data-add-special="Signature">${esc(__("Signature"))}</button><button type="button" class="odtb-secondary" data-add-layout="HTML">${esc(__("Advanced HTML"))}</button></div></div><div class="odtb-field-builder">${rows.length ? rows.map(fieldRow).join("") : emptyRow(__("No fields yet. Add fields or layout sections."))}</div></article>`;
    }

    function fieldRow(row, index) {
        const isLayout = ["Section Break", "Column Break", "HTML"].includes(row.fieldtype);
        const type = row.fieldtype || "Data";
        const label = row.field_label || type;
        return `
            <article class="odtb-field-card ${isLayout ? "layout" : ""} ${fieldTypeClass(type)} ${STATE.expandedFields.has(index) ? "expanded" : ""}" data-field-index="${index}">
                <div class="odtb-field-card-head" data-toggle-field="${index}">
                    <span class="odtb-drag-handle">${fieldIcon("drag")}</span>
                    <div class="odtb-field-title-wrap">
                        <span class="odtb-type-pill">${esc(__(type))}</span>
                        <strong>${esc(label)}</strong>
                    </div>
                    <span class="odtb-order-pill">#${index + 1}</span>
                    <span class="odtb-chevron">${fieldIcon("chevron")}</span>
                    <button type="button" class="odtb-danger" title="${esc(__("Remove"))}" aria-label="${esc(__("Remove field"))}" data-remove-field="${index}">&times;</button>
                </div>
                <div class="odtb-field-card-body">
                    <section class="odtb-fieldset setup">
                        <h3>${esc(__("Field Setup"))}</h3>
                        <div class="odtb-fieldset-grid four">
                            ${input("field_label", __("Label"), row.field_label || "", "text", true, true)}
                            ${readonlyInput("field_key", __("Key (automatic)"), row.field_key || automaticFieldKey(row.field_label, index), true, !row.field_key)}
                            <label><span>${esc(__("Type"))}</span><select data-row-field="fieldtype">${options(FIELD_TYPES, type)}</select></label>
                            ${input("display_order", __("Order"), row.display_order || index + 1, "number", false, true)}
                        </div>
                    </section>
                    ${fieldMainControls(row, type)}
                    ${fieldAdvancedControls(row, type)}
                </div>
            </article>
        `;
    }

    function fieldMainControls(row, type) {
        if (["Section Break", "Column Break", "HTML"].includes(type)) return "";
        return `<section class="odtb-fieldset rules"><h3>${esc(__("Validation"))}</h3><label class="odtb-check inline"><input type="checkbox" data-row-field="is_required" ${row.is_required ? "checked" : ""}/><span>${esc(__("Required"))}</span></label>${type === "Check" ? `<label><span>${esc(__("Required Value"))}</span><select data-row-field="required_value_mode">${options(["Present", "Checked"], row.required_value_mode || "Present")}</select></label>` : ""}</section>`;
    }

    function fieldAdvancedControls(row, type) {
        let controls = "";
        if (type === "HTML") {
            controls = textarea("options", __("HTML Content"), row.options || row.default_value || "", true);
        } else if (type === "Section Break") {
            controls = textarea("options", __("Section Description"), row.options || "", true);
        } else if (type === "Column Break") {
            controls = `<p class="odtb-advanced-note">${esc(__("Starts the second column in the current section."))}</p>`;
        } else {
            const parts = [input("source_field", __("Prefill From Document Field"), row.source_field || "", "text", false, true)];
            if (type === "Select") parts.push(textarea("options", __("Choices (one per line)"), row.options || "", true));
            if (type === "Link") parts.push(input("options", __("Linked DocType"), row.options || "", "text", false, true));
            if (!["Attach", "Attach Image", "Signature", "Check"].includes(type)) {
                parts.push(input("default_value", __("Default Value"), row.default_value || "", "text", false, true));
            }
            controls = `<div class="odtb-fieldset-grid two">${parts.join("")}</div>`;
        }
        return `<details class="odtb-advanced"><summary>${esc(__(type === "HTML" ? "HTML Settings" : "Advanced Settings"))}</summary><div class="odtb-advanced-body">${controls}</div></details>`;
    }

    function statusesStep(template) {
        const rows = template.statuses || [];
        return `<article class="odtb-card"><div class="odtb-card-head with-action"><div><h2>${esc(__("Statuses"))}</h2><p>${esc(__("Configure the status lifecycle for each filled annex document."))}</p></div><button type="button" class="odtb-secondary" data-add-status="1">${esc(__("Add Status"))}</button></div><div class="odtb-status-builder">${rows.map(statusRow).join("")}</div></article>`;
    }

    function statusRow(row, index) {
        return `<article class="odtb-status-card" data-status-index="${index}"><div class="odtb-status-fields">${input("status_label", __("Status"), row.status_label || "", "text", true, true)}<label><span>${esc(__("Color"))}</span><select data-row-field="color">${options(STATUS_COLORS, row.color || "Gray")}</select></label>${input("display_order", __("Order"), row.display_order || index + 1, "number", false, true)}${check("is_default", __("Default"), row.is_default)}${check("is_complete", __("Complete"), row.is_complete)}</div><button type="button" class="odtb-danger" title="${esc(__("Remove"))}" aria-label="${esc(__("Remove status"))}" data-remove-status="${index}">&times;</button></article>`;
    }

    function printStep(template) {
        return `<article class="odtb-card"><div class="odtb-card-head"><h2>${esc(__("Print Settings"))}</h2><p>${esc(__("The title, header, footer, fields, columns, attachments, and signatures are rendered from this template."))}</p></div><div class="odtb-grid-2">${input("print_title", __("Print Title"), template.print_title || "")}</div><div class="odtb-grid-2 mt">${textarea("print_header", __("Print Header"), template.print_header || "")}${textarea("print_footer", __("Print Footer"), template.print_footer || "")}</div></article>`;
    }

    function emptyRow(message) { return `<div class="odtb-empty">${esc(message)}</div>`; }

    function bind(page) {
        page.main.find("[data-back]").on("click", () => frappe.set_route("document-template-manager"));
        page.main.find("[data-step]").on("click", function () { collect(page); STATE.activeStep = $(this).data("step"); render(page); });
        page.main.find("[data-add-field]").on("click", () => { collect(page); const index = STATE.template.fields.length; STATE.template.fields.push({ field_label: "", field_key: "", fieldtype: "Data", display_order: index + 1 }); STATE.expandedFields = new Set([index]); render(page); });
        page.main.find("[data-add-target]").on("click", () => { collect(page); const doctype = page.main.find("[data-new-target]").val(); if (!doctype) return; STATE.template.targets.push({ target_doctype: doctype, allow_direct_creation: 1, copy_after_submit: 0, must_be_complete: 0, display_order: STATE.template.targets.length + 1 }); render(page); });
        page.main.find("[data-add-layout]").on("click", function () { collect(page); const type = $(this).data("add-layout"); const index = STATE.template.fields.length; const labels = { "Section Break": "New Section", "Column Break": "New Column", HTML: "Advanced HTML" }; STATE.template.fields.push({ field_label: labels[type] || type, field_key: "", fieldtype: type, display_order: index + 1 }); STATE.expandedFields = new Set([index]); render(page); });
        page.main.find("[data-add-special]").on("click", function () { collect(page); const type = $(this).data("add-special"); const index = STATE.template.fields.length; STATE.template.fields.push({ field_label: type === "Signature" ? "New Signature" : "New Attachment", field_key: "", fieldtype: type, display_order: index + 1 }); STATE.expandedFields = new Set([index]); render(page); });
        page.main.find("[data-toggle-field]").on("click", function () { collect(page); const index = Number($(this).data("toggle-field")); const expanded = new Set(STATE.expandedFields); expanded.has(index) ? expanded.delete(index) : expanded.add(index); STATE.expandedFields = expanded; render(page); });
        page.main.find("[data-add-status]").on("click", () => { collect(page); STATE.template.statuses.push({ status_label: "", color: "Gray", is_default: 0, is_complete: 0, display_order: STATE.template.statuses.length + 1 }); render(page); });
        page.main.find("[data-remove-target]").on("click", function () { collect(page); STATE.template.targets.splice(Number($(this).data("remove-target")), 1); render(page); });
        page.main.find("[data-remove-field]").on("click", function (event) { event.stopPropagation(); collect(page); STATE.template.fields.splice(Number($(this).data("remove-field")), 1); STATE.expandedFields = new Set(); render(page); });
        page.main.find("[data-remove-status]").on("click", function () { collect(page); STATE.template.statuses.splice(Number($(this).data("remove-status")), 1); render(page); });
        page.main.find("[data-save]").on("click", () => save(page));
        page.main.find("[data-preview-template]").on("click", () => openPreview(page));
        page.main.find("[data-delete-template]").on("click", () => confirmDelete(page));
        page.main.find('[data-row-field="fieldtype"]').on("change", function () { collect(page); render(page); });
        page.main.find('[data-row-field="field_label"]').on("input", function () {
            const key = $(this).closest("[data-field-index]").find('[data-row-field="field_key"]');
            if (Number(key.data("auto-key")) === 1) key.val(uniqueVisibleFieldKey($(this).val(), key));
        });
    }

    function collect(page) {
        const root = page.main;
        if (!STATE.template) STATE.template = blankTemplate();
        ["template_name", "display_order", "print_title", "print_header", "print_footer"].forEach((field) => { const el = root.find(`[data-field="${field}"]`); if (el.length) STATE.template[field] = el.val(); });
        if (root.find('[data-field="is_active"]').length) STATE.template.is_active = root.find('[data-field="is_active"]').is(":checked") ? 1 : 0;
        if (root.find("[data-target-index]").length) STATE.template.targets = root.find("[data-target-index]").map(function () { const index = Number($(this).data("target-index")); const row = collectRow($(this), ["target_doctype", "must_be_complete", "display_order"], STATE.template.targets[index]); const copyTo = $(this).find("[data-copy-destination]:checked").map(function () { return $(this).data("copy-destination"); }).get(); row.copy_to_doctypes = copyTo.join("\n"); row.allow_direct_creation = 1; row.copy_after_submit = copyTo.length ? 1 : 0; row.allow_execution_copy = copyTo.includes("Sales Order Technical List Revision") ? 1 : 0; row.allow_import_from_sales_order = 0; row.required_for_revision = 0; row.default_selected = 0; return row; }).get();
        if (root.find("[data-field-index]").length) STATE.template.fields = root.find("[data-field-index]").map(function () { const index = Number($(this).data("field-index")); return collectRow($(this), ["field_label", "field_key", "fieldtype", "options", "source_field", "is_required", "required_value_mode", "default_value", "display_order"], STATE.template.fields[index]); }).get();
        if (root.find("[data-status-index]").length) STATE.template.statuses = root.find("[data-status-index]").map(function () { return collectRow($(this), ["status_label", "color", "is_default", "is_complete", "display_order"]); }).get();
    }

    function collectRow(row, fields, existing = {}) {
        const out = { ...existing };
        fields.forEach((field) => { const el = row.find(`[data-row-field="${field}"]`); if (el.length) out[field] = el.attr("type") === "checkbox" ? (el.is(":checked") ? 1 : 0) : el.val(); });
        return out;
    }

    async function save(page) {
        collect(page);
        if (!String(STATE.template.template_name || "").trim()) return frappe.msgprint({ message: __("Template name is required."), indicator: "red" });
        const res = await frappe.call({ method: "orderlift.document_templates.save_template", args: { payload: JSON.stringify(STATE.template) }, freeze: true });
        STATE.template = (res.message || {}).template || STATE.template;
        frappe.show_alert({ message: __("Template saved"), indicator: "green" });
        if (STATE.template.name) frappe.set_route("document-template-builder", STATE.template.name);
        render(page);
    }

    function openPreview(page) {
        collect(page);
        const template = STATE.template || blankTemplate();
        const dialog = new frappe.ui.Dialog({ title: __("Annex Template Preview"), size: "extra-large", fields: [{ fieldtype: "HTML", fieldname: "body" }] });
        dialog.show();
        dialog.fields_dict.body.$wrapper.html(annexPreviewMarkup(template));
    }

    function annexPreviewMarkup(template) {
        const fields = template.fields || [];
        return `<div class="odtb-preview-page"><div class="odtb-preview-header"><div class="odtb-preview-logo"><strong>${esc(__("Company identity"))}</strong></div><div><h1>${esc(template.print_title || template.template_name || __("Annex Document"))}</h1></div></div>${template.print_header ? `<div class="odtb-preview-template-html">${template.print_header}</div>` : ""}${previewFieldsMarkup(fields)}${template.print_footer ? `<div class="odtb-preview-template-html">${template.print_footer}</div>` : ""}</div>`;
    }

    function previewFieldsMarkup(fields) {
        const sections = [];
        let section = { label: "", description: "", columns: [[]] };
        const push = () => {
            if (section.label || section.columns.some((column) => column.length)) sections.push(section);
        };
        fields.forEach((field) => {
            if (field.fieldtype === "Section Break") {
                push();
                section = { label: field.field_label || "", description: field.options || "", columns: [[]] };
            } else if (field.fieldtype === "Column Break") {
                if (section.columns.length < 2) section.columns.push([]);
            } else {
                section.columns[section.columns.length - 1].push(field);
            }
        });
        push();
        return sections.map((item) => `<section class="odtb-preview-dynamic-section">${item.label ? `<div class="odtb-preview-section"><span>${esc(item.label)}</span></div>${item.description ? `<p class="odtb-preview-description">${esc(item.description)}</p>` : ""}` : ""}<div class="odtb-preview-columns columns-${item.columns.length}">${item.columns.map((column) => `<div class="odtb-preview-column">${column.map(previewField).join("")}</div>`).join("")}</div></section>`).join("");
    }

    function previewField(field) {
        if (field.fieldtype === "HTML") return `<div class="odtb-preview-wide">${field.options || field.default_value || ""}</div>`;
        if (field.fieldtype === "Check") return `<div class="odtb-preview-field"><b>${esc(field.field_label)} :</b><span class="odtb-preview-check"><i></i> Oui <i></i> Non</span></div>`;
        if (field.fieldtype === "Signature") return `<div class="odtb-preview-signature"><b>${esc(field.field_label)}</b><span></span></div>`;
        const wide = ["Small Text", "Text", "Text Editor", "Attach", "Attach Image"].includes(field.fieldtype);
        return `<div class="odtb-preview-field ${wide ? "wide" : ""}"><b>${esc(field.field_label)} :</b><span></span></div>`;
    }

    function confirmDelete(page) {
        const template = STATE.template;
        if (!template || !template.name) return;
        const dialog = new frappe.ui.Dialog({
            title: __("Permanently Delete Template"),
            fields: [
                {
                    fieldtype: "HTML",
                    options: `<div class="alert alert-danger"><strong>${esc(__("This cannot be undone."))}</strong><br>${esc(__("Templates with historical annex documents cannot be deleted."))}</div>`,
                },
                {
                    fieldname: "confirmation",
                    fieldtype: "Data",
                    label: __("Type the template name to confirm"),
                    reqd: 1,
                },
            ],
            primary_action_label: __("Permanently Delete"),
            primary_action: async (values) => {
                if (String(values.confirmation || "").trim() !== template.template_name) {
                    frappe.msgprint({ message: __("The template name does not match."), indicator: "red" });
                    return;
                }
                const res = await frappe.call({
                    method: "orderlift.document_templates.delete_template",
                    args: { name: template.name },
                    freeze: true,
                    freeze_message: __("Deleting template and saved annex documents..."),
                });
                dialog.hide();
                frappe.show_alert({ message: __("Template deleted"), indicator: "green" });
                frappe.set_route("document-template-manager");
            },
        });
        dialog.show();
    }

    function input(field, label, value, type = "text", required = false, row = false) { return `<label><span>${esc(label)}${required ? " *" : ""}</span><input type="${esc(type)}" ${row ? `data-row-field="${esc(field)}"` : `data-field="${esc(field)}"`} value="${esc(value)}" /></label>`; }
    function check(field, label, checked, description = "") { return `<label class="odtb-check inline" title="${esc(description)}"><input type="checkbox" data-row-field="${esc(field)}" ${checked ? "checked" : ""}/><span>${esc(label)}</span></label>`; }
    function readonlyInput(field, label, value, row = false, autoKey = false) { return `<label class="odtb-readonly"><span>${esc(label)}</span><input type="text" ${row ? `data-row-field="${esc(field)}"` : `data-field="${esc(field)}"`} data-auto-key="${autoKey ? 1 : 0}" value="${esc(value)}" readonly tabindex="-1" /></label>`; }
    function textarea(field, label, value, row = false) { return `<label class="odtb-textarea"><span>${esc(label)}</span><textarea ${row ? `data-row-field="${esc(field)}"` : `data-field="${esc(field)}"`}>${esc(value)}</textarea></label>`; }
    function options(values, selected) { return values.map((value) => `<option value="${esc(value)}" ${value === selected ? "selected" : ""}>${esc(__(value))}</option>`).join(""); }
    function esc(value) { return frappe.utils.escape_html(value == null ? "" : String(value)); }
    function normalizeFieldKey(value) { return String(value || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "field"; }
    function automaticFieldKey(value, index) {
        const base = normalizeFieldKey(value);
        const used = new Set((STATE.template.fields || []).map((field, fieldIndex) => fieldIndex === index ? "" : (field.field_key || normalizeFieldKey(field.field_label))).filter(Boolean));
        let key = base;
        let suffix = 2;
        while (used.has(key)) key = `${base}_${suffix++}`;
        return key;
    }
    function uniqueVisibleFieldKey(value, currentInput) {
        const base = normalizeFieldKey(value);
        const used = new Set($('[data-row-field="field_key"]').not(currentInput).map(function () { return $(this).val(); }).get().filter(Boolean));
        let key = base;
        let suffix = 2;
        while (used.has(key)) key = `${base}_${suffix++}`;
        return key;
    }
    function fieldTypeClass(type) {
        if (["Section Break", "Column Break", "HTML"].includes(type)) return "type-layout";
        if (["Small Text", "Text", "Text Editor"].includes(type)) return "type-text";
        if (["Attach", "Attach Image", "Signature"].includes(type)) return "type-attach";
        if (type === "Check") return "type-check";
        return "type-data";
    }
    function fieldIcon(name) {
        if (name === "drag") return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="9" cy="5" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="9" cy="19" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="19" r="1"/></svg>';
        return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="6 9 12 15 18 9"/></svg>';
    }

    function injectStyles() {
        if (document.getElementById("odtb-style")) return;
        const style = document.createElement("style");
        style.id = "odtb-style";
        style.textContent = `
            .odtb-root{background:#f6f8fb;min-height:100vh}.odtb-shell{width:min(1440px,100%);margin:0 auto;padding:18px clamp(12px,2vw,24px) 56px;color:#172033}.odtb-breadcrumb{display:flex;align-items:center;gap:7px;margin-bottom:10px;color:#64748b;font-size:12px;font-weight:800}.odtb-breadcrumb a{color:#2563eb;text-decoration:none}.odtb-hero{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;padding:20px 22px;border:1px solid #dbe5ef;border-radius:18px;background:linear-gradient(135deg,#fff 0%,#f0f7ff 100%);box-shadow:0 10px 24px rgba(15,23,42,.055)}.odtb-hero span{display:inline-flex;margin-bottom:6px;color:#2563eb;font-size:11px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.odtb-hero h1{margin:0;font-size:clamp(24px,2.5vw,34px);letter-spacing:-.04em;line-height:1.04}.odtb-hero p{max-width:740px;margin:7px 0 0;color:#475569;font-size:13px;line-height:1.5}.odtb-actions,.odtb-mini-actions{display:flex;gap:8px;flex-wrap:wrap}.odtb-primary,.odtb-secondary{min-height:36px;border-radius:10px;padding:0 14px;font-size:13px;font-weight:900;cursor:pointer}.odtb-primary{border:0;background:#2563eb;color:#fff;box-shadow:0 8px 18px rgba(37,99,235,.2)}.odtb-secondary{border:1px solid #bfdbfe;background:#eff6ff;color:#1d4ed8}.odtb-steps{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:12px}.odtb-steps button{min-height:40px;border:1px solid #dbe5ef;border-radius:12px;background:#fff;color:#475569;font-size:13px;font-weight:900;cursor:pointer}.odtb-steps button.active{border-color:#93c5fd;background:#eff6ff;color:#1d4ed8;box-shadow:0 0 0 2px rgba(37,99,235,.07)}.odtb-workspace{margin-top:12px}.odtb-card{border:1px solid #dbe5ef;border-radius:16px;background:#fff;padding:16px;box-shadow:0 8px 22px rgba(15,23,42,.04)}.odtb-card-head{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;margin-bottom:14px}.odtb-card-head.with-action{align-items:center}.odtb-card h2{margin:0;font-size:17px}.odtb-card p{margin:4px 0 0;color:#64748b;font-size:13px}.odtb-grid-2,.odtb-grid-3{display:grid;gap:12px}.odtb-grid-2{grid-template-columns:repeat(2,minmax(0,1fr))}.odtb-grid-3{grid-template-columns:2fr .8fr auto;align-items:end}.odtb-grid-2.mt{margin-top:12px}.odtb-card label,.odtb-line label{display:grid;gap:5px;color:#334155;font-weight:900;font-size:12px}.odtb-card input,.odtb-card select,.odtb-card textarea,.odtb-line input,.odtb-line select,.odtb-line textarea{width:100%;min-height:36px;border:1px solid #cbd5e1;border-radius:9px;background:#fff;padding:0 10px;color:#172033;font-size:13px}.odtb-card textarea,.odtb-line textarea{min-height:64px;padding:8px 10px;resize:vertical}.odtb-check{display:flex!important;align-items:center;gap:8px;min-height:36px}.odtb-check input[type=checkbox]{appearance:none;-webkit-appearance:none;display:grid;place-items:center;width:16px!important;height:16px!important;min-height:16px!important;margin:0;padding:0!important;border:1px solid #94a3b8!important;border-radius:4px;background:#fff!important;cursor:pointer}.odtb-check input[type=checkbox]:checked{border-color:#2563eb!important;background:#2563eb!important}.odtb-check input[type=checkbox]:checked:before{content:'\\2713';color:#fff;font-size:12px;font-weight:900;line-height:1}.odtb-check.inline{align-self:end;margin-bottom:8px}.odtb-target-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}.odtb-target{position:relative;display:grid;align-content:center;min-height:88px;border:1px solid #dbe5ef;border-radius:14px;background:#f8fafc;padding:14px;cursor:pointer}.odtb-target input{position:absolute;opacity:0}.odtb-target strong{font-size:14px}.odtb-target small{margin-top:4px;color:#64748b;font-weight:800}.odtb-target.selected{border-color:#60a5fa;background:#eff6ff;box-shadow:0 0 0 2px rgba(37,99,235,.08)}.odtb-target.selected:after{content:'\\2713';position:absolute;right:10px;top:10px;display:grid;place-items:center;width:21px;height:21px;border-radius:999px;background:#2563eb;color:#fff;font-size:12px;font-weight:900}.odtb-field-builder,.odtb-status-builder{display:grid;gap:10px}.odtb-line{display:grid;grid-template-columns:minmax(170px,1.2fr) minmax(145px,.9fr) 160px 76px 104px minmax(140px,.8fr) minmax(210px,1fr) 34px;gap:10px;align-items:end;border:1px solid #dbe5ef;border-radius:13px;background:#fff;padding:12px}.odtb-line.layout{background:#f8fbff;border-style:dashed}.odtb-line.status{grid-template-columns:minmax(260px,1.4fr) minmax(170px,.8fr) 90px 110px 34px}.odtb-danger{width:34px;height:34px;border:1px solid #fecaca;border-radius:9px;background:#fff1f2;color:#b91c1c;font-size:18px;font-weight:900;line-height:1;cursor:pointer}.odtb-danger:hover{background:#fee2e2;border-color:#fca5a5}.odtb-empty{border:1px dashed #cbd5e1;border-radius:13px;background:#f8fafc;padding:22px;text-align:center;color:#64748b;font-weight:800}@media(max-width:1100px){.odtb-steps,.odtb-target-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.odtb-grid-2,.odtb-grid-3{grid-template-columns:1fr}.odtb-line,.odtb-line.status{grid-template-columns:1fr 1fr}.odtb-danger{width:100%}}@media(max-width:720px){.odtb-shell{padding:14px 10px 48px}.odtb-hero,.odtb-card-head{display:grid}.odtb-actions,.odtb-mini-actions{width:100%}.odtb-actions button,.odtb-mini-actions button{flex:1}.odtb-steps,.odtb-target-grid,.odtb-line,.odtb-line.status{grid-template-columns:1fr}.odtb-hero h1{font-size:28px}}
        `;
        style.textContent += `
            .odtb-shell,.odtb-card,.odtb-line,.odtb-line *{min-width:0}.odtb-line{grid-template-columns:minmax(180px,1.2fr) minmax(130px,.8fr) minmax(130px,.8fr) minmax(180px,1fr) 88px minmax(120px,.7fr);align-items:end}.odtb-line label{min-width:0}.odtb-line input,.odtb-line select,.odtb-line textarea{width:100%;max-width:100%;min-width:0}.odtb-line .odtb-textarea{grid-column:1/-1}.odtb-actions .btn{min-height:36px;border-radius:10px;font-weight:900}.odtb-preview-page{max-width:190mm;margin:0 auto;border:1px solid #374151;padding:8px 10px;font-family:Arial,sans-serif;font-size:10.5px;color:#1f2937}.odtb-preview-header{display:grid;grid-template-columns:48mm 1fr;border:1px solid #6b7280;min-height:29mm}.odtb-preview-logo{border-right:1px solid #6b7280;display:grid;align-content:center;justify-items:center;text-align:center}.odtb-preview-logo strong{font-size:18px;line-height:.9}.odtb-preview-logo span{font-size:9px}.odtb-preview-header h1{text-align:center;font-family:Georgia,serif;color:#374151}.odtb-preview-meta{display:grid;grid-template-columns:34mm 1fr 28mm 1fr;gap:3px 10px;padding:0 8px}.odtb-preview-meta span,.odtb-preview-field span{border-bottom:1px dotted #9ca3af;min-height:14px}.odtb-preview-section{text-align:center;margin:9px 0 4px}.odtb-preview-section span{display:inline-block;border:1px solid #6b7280;background:#f3f4f6;padding:2px 18px;font-weight:700}.odtb-preview-field{display:grid;grid-template-columns:38% 1fr;gap:5px;border-left:1px solid #6b7280;border-right:1px solid #6b7280;padding:4px 7px}.odtb-preview-field.wide{grid-template-columns:24% 1fr}.odtb-preview-check{border-bottom:0!important;display:flex;gap:8px}.odtb-preview-check i{width:10px;height:10px;border:1px solid #374151;display:inline-block}.odtb-preview-wide{border:1px solid #6b7280;padding:6px}.odtb-preview-signatures{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px}.odtb-preview-signatures div{height:25mm;border:1px solid #6b7280;text-align:center;font-weight:700;padding-top:5px}.odtb-preview-footer{text-align:center;margin-top:8px;font-size:10px;line-height:1.4}@media(max-width:900px){.odtb-line{grid-template-columns:1fr}.odtb-steps{grid-template-columns:1fr 1fr}.odtb-card-head{display:block}.odtb-mini-actions{margin-top:10px}}
        `;
        style.textContent += `.odtb-check input[type="checkbox"],.odtb-line .odtb-check input[type="checkbox"],.odtb-target input[type="checkbox"]{appearance:auto!important;width:18px!important;height:18px!important;min-width:18px!important;min-height:18px!important;max-width:18px!important;padding:0!important;margin:0!important;border-radius:4px;accent-color:#2563eb;flex:0 0 18px}.odtb-check{min-height:44px;padding:8px 10px;border:1px solid #e2e8f0;border-radius:12px;background:#f8fafc}.odtb-check.inline{min-height:36px;background:#fff}.odtb-target{position:relative;overflow:hidden}.odtb-line{border-color:#dbe5ef;background:linear-gradient(180deg,#fff 0%,#fbfdff 100%);box-shadow:0 8px 18px rgba(15,23,42,.035)}.odtb-line:hover{border-color:#bfdbfe;box-shadow:0 10px 22px rgba(37,99,235,.07)}.odtb-card input:focus,.odtb-card select:focus,.odtb-card textarea:focus{outline:0;border-color:#60a5fa;box-shadow:0 0 0 3px rgba(37,99,235,.11)}.odtb-preview-check i{border-radius:2px;background:#fff}`;
        style.textContent += `.odtb-field-builder,.odtb-status-builder{display:grid;gap:16px}.odtb-field-card,.odtb-status-card{border:1px solid #cbdff7;border-radius:18px;background:#fff;box-shadow:0 14px 32px rgba(15,23,42,.07);overflow:hidden}.odtb-field-card-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;padding:14px 16px;background:linear-gradient(135deg,#0f2340 0%,#1d4ed8 100%);color:#fff}.odtb-field-card-head>div{display:grid;gap:4px;min-width:0}.odtb-field-card-head strong{font-size:16px;line-height:1.25;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.odtb-field-card-head small{color:#bfdbfe;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.06em}.odtb-type-pill{width:max-content;border:1px solid rgba(255,255,255,.28);border-radius:999px;background:rgba(255,255,255,.14);padding:3px 9px;color:#fff!important;font-size:10px!important;font-weight:900!important;letter-spacing:.08em;text-transform:uppercase}.odtb-field-card-head .odtb-danger{width:34px;height:34px;min-height:34px;border-radius:10px;background:rgba(239,68,68,.14);border:1px solid rgba(254,202,202,.55);color:#fff}.odtb-field-card-body{display:grid;grid-template-columns:minmax(0,1fr) minmax(230px,.38fr);gap:12px;padding:14px;background:#f8fbff}.odtb-fieldset{min-width:0;border:1px solid #dbeafe;border-radius:15px;background:#fff;padding:12px;box-shadow:0 6px 14px rgba(15,23,42,.035)}.odtb-fieldset h3{margin:0 0 10px;color:#1e3a8a;font-size:12px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.odtb-fieldset.setup,.odtb-fieldset.content{grid-column:1/-1}.odtb-fieldset-grid{display:grid;gap:10px}.odtb-fieldset-grid.three{grid-template-columns:minmax(220px,1.2fr) minmax(160px,.9fr) minmax(160px,.8fr)}.odtb-fieldset-grid.two{grid-template-columns:repeat(2,minmax(0,1fr))}.odtb-fieldset-grid.two-tight{grid-template-columns:minmax(0,1fr) 90px}.odtb-fieldset.source{border-left:4px solid #38bdf8}.odtb-fieldset.rules{border-left:4px solid #f59e0b}.odtb-fieldset.content{border-left:4px solid #22c55e}.odtb-field-card label{min-width:0}.odtb-field-card label span,.odtb-status-card label span{color:#475569;font-size:12px;font-weight:900}.odtb-field-card input,.odtb-field-card select,.odtb-field-card textarea,.odtb-status-card input,.odtb-status-card select{width:100%;max-width:100%;min-width:0}.odtb-field-card .odtb-textarea{grid-column:auto}.odtb-field-card .odtb-textarea textarea{min-height:96px}.odtb-field-card .odtb-check input[type="checkbox"],.odtb-status-card .odtb-check input[type="checkbox"]{appearance:auto!important;width:18px!important;height:18px!important;min-width:18px!important;min-height:18px!important;padding:0!important;accent-color:#2563eb}.odtb-status-card{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:end;padding:14px;background:#f8fbff}.odtb-status-fields{display:grid;grid-template-columns:minmax(180px,1fr) minmax(140px,.7fr) 90px minmax(150px,.7fr);gap:10px;align-items:end}.odtb-status-card .odtb-danger{align-self:end}@media(max-width:1100px){.odtb-field-card-body,.odtb-fieldset-grid.three,.odtb-fieldset-grid.two,.odtb-fieldset-grid.two-tight,.odtb-status-card,.odtb-status-fields{grid-template-columns:1fr}.odtb-field-card-head strong{white-space:normal}}`;
        style.textContent += `
            .odtb-field-card { border: 1px solid #e4e7f0; border-radius: 15px; background: #fff; box-shadow: 0 4px 12px rgba(15, 23, 41, .06); }
            .odtb-field-card-head { display: grid; grid-template-columns: 20px minmax(0, 1fr) auto auto auto; align-items: center; gap: 12px; min-height: 70px; padding: 13px 18px; border: 0; background: #fff !important; color: #111827 !important; cursor: pointer; }
            .odtb-field-card-head:hover { background: #f8f9fc !important; }
            .odtb-drag-handle { display: flex; color: #c1c7d4; }
            .odtb-drag-handle svg { width: 17px; height: 17px; }
            .odtb-field-title-wrap { display: flex !important; flex-direction: row; align-items: center; gap: 12px !important; min-width: 0; }
            .odtb-field-title-wrap strong { min-width: 0; overflow: hidden; color: #111827; font-size: 15px; font-weight: 800; text-overflow: ellipsis; white-space: nowrap; }
            .odtb-type-pill { flex: 0 0 auto; width: auto; padding: 5px 10px; border: 0; border-radius: 999px; font-size: 10px !important; font-weight: 800 !important; letter-spacing: .05em; text-transform: uppercase; }
            .odtb-field-card.type-data .odtb-type-pill { background: #eef1ff !important; color: #4f6ef7 !important; }
            .odtb-field-card.type-text .odtb-type-pill { background: #f3f0ff !important; color: #7c5cf5 !important; }
            .odtb-field-card.type-layout .odtb-type-pill { background: #fef2f2 !important; color: #ef4444 !important; }
            .odtb-field-card.type-check .odtb-type-pill { background: #ecfdf5 !important; color: #15803d !important; }
            .odtb-field-card.type-attach .odtb-type-pill { background: #fffbeb !important; color: #b45309 !important; }
            .odtb-order-pill { display: inline-flex; align-items: center; justify-content: center; min-width: 42px; height: 29px; padding: 0 8px; border-radius: 999px; background: #f3f5fa; color: #8c93a8; font-size: 12px; font-weight: 800; }
            .odtb-chevron { display: flex; color: #8c93a8; transition: transform .18s cubic-bezier(.4, 0, .2, 1); }
            .odtb-chevron svg { width: 18px; height: 18px; }
            .odtb-field-card.expanded .odtb-chevron { transform: rotate(180deg); }
            .odtb-field-card-head .odtb-danger { display: inline-flex; align-items: center; justify-content: center; width: 31px; height: 31px; min-height: 31px; border: 0; border-radius: 8px; background: transparent !important; color: #c1c7d4 !important; font-size: 23px; }
            .odtb-field-card-head .odtb-danger:hover { background: #fef2f2 !important; color: #ef4444 !important; }
            .odtb-field-card-body { display: none; grid-template-columns: minmax(0, 1fr) minmax(250px, .42fr); gap: 14px; padding: 18px 20px 22px; border-top: 1px solid #e8ecf4; background: #f5f6fa; }
            .odtb-field-card.expanded .odtb-field-card-body { display: grid; }
            .odtb-fieldset { border-color: #e4e7f0; border-radius: 12px; box-shadow: 0 1px 3px rgba(15, 23, 41, .04); }
            .odtb-fieldset.setup, .odtb-fieldset.content { grid-column: 1 / -1; }
            @media (max-width: 900px) {
                .odtb-field-card-body { grid-template-columns: 1fr; }
                .odtb-field-card-head { grid-template-columns: 18px minmax(0, 1fr) auto auto; }
                .odtb-order-pill { display: none; }
                .odtb-field-title-wrap { flex-wrap: wrap; gap: 6px !important; }
                .odtb-field-title-wrap strong { width: 100%; }
            }
        `;
        style.textContent += `
            .odtb-shell { width: min(1280px, 100%); padding: 14px 18px 44px; }
            .odtb-breadcrumb { margin-bottom: 8px; font-size: 11px; }
            .odtb-hero { padding: 15px 18px; border-radius: 14px; }
            .odtb-hero span { margin-bottom: 4px; font-size: 9px; }
            .odtb-hero h1 { font-size: 21px; }
            .odtb-hero p { margin-top: 4px; font-size: 11px; }
            .odtb-actions, .odtb-mini-actions { gap: 6px; }
            .odtb-primary, .odtb-secondary, .odtb-actions .btn { min-height: 32px; padding: 0 11px; border-radius: 8px; font-size: 11px; }
            .odtb-steps { gap: 6px; margin-top: 9px; }
            .odtb-steps button { min-height: 34px; border-radius: 9px; font-size: 11px; }
            .odtb-workspace { margin-top: 9px; }
            .odtb-card { padding: 13px; border-radius: 13px; }
            .odtb-card-head { gap: 10px; margin-bottom: 10px; }
            .odtb-card h2 { font-size: 15px; }
            .odtb-card-head p { margin-top: 3px; font-size: 11px; }
            .odtb-grid-3, .odtb-grid-2 { gap: 9px; }
            .odtb-card label { gap: 4px; font-size: 10px; }
            .odtb-card input, .odtb-card select, .odtb-card textarea { min-height: 34px; padding: 6px 9px; border-radius: 8px; font-size: 12px; }
            .odtb-textarea textarea { min-height: 58px; }
            .odtb-target-grid { gap: 8px; }
            .odtb-target { min-height: 62px; padding: 10px; border-radius: 10px; }
            .odtb-target strong { font-size: 12px; }
            .odtb-target small { font-size: 10px; }
            .odtb-field-builder, .odtb-status-builder { gap: 10px; }
            .odtb-field-card { border-radius: 12px; }
            .odtb-field-card-head { grid-template-columns: 17px minmax(0, 1fr) auto auto auto; gap: 9px; min-height: 54px; padding: 9px 13px; }
            .odtb-drag-handle svg { width: 14px; height: 14px; }
            .odtb-field-title-wrap { gap: 8px !important; }
            .odtb-field-title-wrap strong { font-size: 12px; }
            .odtb-type-pill { padding: 3px 8px; font-size: 8px !important; }
            .odtb-order-pill { min-width: 34px; height: 23px; font-size: 10px; }
            .odtb-chevron svg { width: 15px; height: 15px; }
            .odtb-field-card-head .odtb-danger { width: 25px; height: 25px; min-height: 25px; font-size: 19px; }
            .odtb-field-card-body { grid-template-columns: minmax(0, 1fr) minmax(190px, .35fr); gap: 9px; padding: 11px 13px 14px; }
            .odtb-fieldset { padding: 10px; border-radius: 9px; }
            .odtb-fieldset h3 { margin-bottom: 7px; font-size: 9px; }
            .odtb-fieldset-grid { gap: 7px; }
            .odtb-fieldset-grid.three { grid-template-columns: minmax(160px, 1.2fr) minmax(130px, .9fr) minmax(130px, .8fr); }
            .odtb-fieldset-grid.four { grid-template-columns: minmax(160px, 1.2fr) minmax(130px, .8fr) minmax(130px, .8fr) 72px; }
            .odtb-fieldset-grid.two-tight { grid-template-columns: minmax(0, 1fr) 72px; }
            .odtb-readonly input { background: #f5f6fa !important; color: #6b7280 !important; cursor: default; }
            .odtb-advanced { grid-column: 1 / -1; overflow: hidden; border: 1px solid #e4e7f0; border-radius: 9px; background: #fff; }
            .odtb-advanced summary { padding: 9px 11px; color: #5b6582; font-size: 10px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; cursor: pointer; }
            .odtb-advanced[open] summary { border-bottom: 1px solid #e8ecf4; background: #f8f9fc; }
            .odtb-advanced-body { padding: 11px; }
            .odtb-advanced-note { margin: 0; color: #6b7280; font-size: 11px; }
            .odtb-preview-signature { display: grid; grid-template-rows: auto 1fr; min-height: 25mm; border: 1px solid #6b7280; text-align: center; }
            .odtb-preview-signature b { padding: 4px; border-bottom: 1px solid #d1d5db; }
            .odtb-preview-template-html { margin: 8px 0; padding: 6px; border: 1px solid #d1d5db; }
            .odtb-preview-dynamic-section { margin-top: 8px; }
            .odtb-preview-description { margin: 0 0 5px; color: #6b7280; text-align: center; }
            .odtb-preview-columns { display: flex; align-items: flex-start; gap: 8px; padding: 6px; border: 1px solid #6b7280; }
            .odtb-preview-column { display: grid; flex: 1 1 0; gap: 4px; min-width: 0; }
            .odtb-preview-columns .odtb-preview-field { border: 0; }
            .odtb-check { min-height: 34px; padding: 6px 8px; border-radius: 9px; }
            .odtb-check.inline { min-height: 31px; }
            .odtb-status-card { padding: 10px; border-radius: 11px; }
            .odtb-status-fields { gap: 8px; }
            .odtb-status-fields.target-settings { grid-template-columns: minmax(180px, .9fr) 78px minmax(300px, 1.3fr) minmax(220px, .9fr); }
            .odtb-copy-targets { display: grid; gap: 5px; min-height: 34px; padding: 7px 9px; border: 1px solid #e2e8f0; border-radius: 9px; background: #f8fafc; }
            .odtb-copy-targets > span { color: #475569; font-size: 10px; font-weight: 900; }
            .odtb-copy-targets p { margin: 0; color: #64748b; font-size: 10px; line-height: 1.35; }
            .odtb-copy-targets > div { display: flex; flex-wrap: wrap; gap: 6px; }
            .odtb-copy-targets.muted { align-content: center; }
            .odtb-copy-chip { display: inline-flex !important; grid-template-columns: none !important; align-items: center; gap: 6px !important; min-height: 28px; padding: 4px 8px; border: 1px solid #dbeafe; border-radius: 999px; background: #fff; font-size: 10px !important; }
            .odtb-copy-chip input[type="checkbox"] { width: 14px !important; height: 14px !important; min-width: 14px !important; min-height: 14px !important; }
            .odtb-empty { padding: 24px; font-size: 11px; }
            .odtb-root input[type="checkbox"] { appearance: none !important; -webkit-appearance: none !important; width: 16px !important; height: 16px !important; min-width: 16px !important; min-height: 16px !important; max-width: 16px !important; margin: 0 !important; padding: 0 !important; border: 1px solid #cbd2df !important; border-radius: 4px !important; background: #fff !important; box-shadow: none !important; }
            .odtb-root input[type="checkbox"]::before, .odtb-root input[type="checkbox"]::after { content: none !important; display: none !important; }
            .odtb-root input[type="checkbox"]:checked { border-color: #4f6ef7 !important; background-color: #4f6ef7 !important; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 14 14'%3E%3Cpath d='M3 7.2 5.6 10 11 4.2' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") !important; background-position: center !important; background-repeat: no-repeat !important; background-size: 12px 12px !important; }
        `;
        document.head.appendChild(style);
    }
})();
