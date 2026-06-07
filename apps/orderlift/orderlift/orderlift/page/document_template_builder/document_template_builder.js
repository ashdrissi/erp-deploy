(function () {
    const STATE = { targets: [], template: null, activeStep: "basics", loading: false };
    const FIELD_TYPES = ["Section Break", "Column Break", "Data", "Small Text", "Text", "Text Editor", "Date", "Datetime", "Time", "Int", "Float", "Currency", "Check", "Select", "Link", "Attach", "Attach Image", "HTML"];
    const STATUS_COLORS = ["Gray", "Blue", "Green", "Orange", "Red", "Purple"];
    const STEPS = [
        ["basics", "Basics"],
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
        return { name: "", template_name: "", is_active: 1, display_order: 100, print_title: "", print_header: "", print_footer: "", show_signature_block: 1, targets: [], fields: [], statuses: [{ status_label: "Draft", color: "Gray", is_default: 1, display_order: 1 }] };
    }

    async function load(page) {
        const route = frappe.get_route();
        const name = route[1] || "new";
        const boot = await frappe.call({ method: "orderlift.document_templates.get_template_manager_bootstrap" });
        STATE.targets = (boot.message || {}).targets || [];
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
                    <div class="odtb-actions"><button type="button" class="odtb-secondary" data-back="1">${esc(__("Back to list"))}</button><button type="button" class="odtb-primary" data-save="1">${esc(__("Save Template"))}</button></div>
                </section>
                <section class="odtb-steps">${STEPS.map(([key, label]) => `<button type="button" class="${STATE.activeStep === key ? "active" : ""}" data-step="${esc(key)}"><span>${esc(__(label))}</span></button>`).join("")}</section>
                <section class="odtb-workspace">${stepMarkup(template)}</section>
            </div>
        `);
        bind(page);
    }

    function stepMarkup(template) {
        if (STATE.activeStep === "fields") return fieldsStep(template);
        if (STATE.activeStep === "statuses") return statusesStep(template);
        if (STATE.activeStep === "print") return printStep(template);
        return basicsStep(template);
    }

    function basicsStep(template) {
        return `<article class="odtb-card"><div class="odtb-card-head"><h2>${esc(__("Basics"))}</h2><p>${esc(__("Name and activate this template."))}</p></div><div class="odtb-grid-3">${input("template_name", __("Template Name"), template.template_name, "text", true)}${input("display_order", __("Display Order"), template.display_order || 100, "number")}<label class="odtb-check"><input type="checkbox" data-field="is_active" ${template.is_active ? "checked" : ""}/><span>${esc(__("Active"))}</span></label></div></article>`;
    }

    function targetsStep(template) {
        const selected = new Set((template.targets || []).map((target) => target.target_doctype || target.doctype));
        return `<article class="odtb-card"><div class="odtb-card-head"><h2>${esc(__("Target Documents"))}</h2><p>${esc(__("Choose where this template appears as a document tab."))}</p></div><div class="odtb-target-grid">${STATE.targets.map((target) => `<label class="odtb-target ${selected.has(target.doctype) ? "selected" : ""}"><input type="checkbox" data-target-doctype="${esc(target.doctype)}" ${selected.has(target.doctype) ? "checked" : ""}/><strong>${esc(__(target.label || target.doctype))}</strong><small>${esc(target.doctype)}</small></label>`).join("")}</div></article>`;
    }

    function fieldsStep(template) {
        const rows = template.fields || [];
        return `<article class="odtb-card"><div class="odtb-card-head with-action"><div><h2>${esc(__("Fields & Layout"))}</h2><p>${esc(__("Use Section Break and Column Break to organize long forms. Other rows become fillable fields."))}</p></div><div class="odtb-mini-actions"><button type="button" class="odtb-secondary" data-add-layout="Section Break">${esc(__("Add Section"))}</button><button type="button" class="odtb-secondary" data-add-field="1">${esc(__("Add Field"))}</button></div></div><div class="odtb-field-builder">${rows.length ? rows.map(fieldRow).join("") : emptyRow(__("No fields yet. Add fields or layout sections."))}</div></article>`;
    }

    function fieldRow(row, index) {
        const isLayout = ["Section Break", "Column Break", "HTML"].includes(row.fieldtype);
        return `<article class="odtb-line ${isLayout ? "layout" : ""}" data-field-index="${index}">${input("field_label", __("Label"), row.field_label || "", "text", true, true)}${input("field_key", __("Key"), row.field_key || "", "text", false, true)}<label><span>${esc(__("Type"))}</span><select data-row-field="fieldtype">${options(FIELD_TYPES, row.fieldtype || "Data")}</select></label>${input("display_order", __("Order"), row.display_order || index + 1, "number", false, true)}<label class="odtb-check inline"><input type="checkbox" data-row-field="is_required" ${row.is_required ? "checked" : ""}/><span>${esc(__("Required"))}</span></label>${input("default_value", __("Default"), row.default_value || "", "text", false, true)}${textarea("options", __("Options / Link DocType / HTML"), row.options || "", true)}<button type="button" class="odtb-danger" title="${esc(__("Remove"))}" aria-label="${esc(__("Remove field"))}" data-remove-field="${index}">&times;</button></article>`;
    }

    function statusesStep(template) {
        const rows = template.statuses || [];
        return `<article class="odtb-card"><div class="odtb-card-head with-action"><div><h2>${esc(__("Statuses"))}</h2><p>${esc(__("Configure the status lifecycle for each filled annex document."))}</p></div><button type="button" class="odtb-secondary" data-add-status="1">${esc(__("Add Status"))}</button></div><div class="odtb-status-builder">${rows.map(statusRow).join("")}</div></article>`;
    }

    function statusRow(row, index) {
        return `<article class="odtb-line status" data-status-index="${index}">${input("status_label", __("Status"), row.status_label || "", "text", true, true)}<label><span>${esc(__("Color"))}</span><select data-row-field="color">${options(STATUS_COLORS, row.color || "Gray")}</select></label>${input("display_order", __("Order"), row.display_order || index + 1, "number", false, true)}<label class="odtb-check inline"><input type="checkbox" data-row-field="is_default" ${row.is_default ? "checked" : ""}/><span>${esc(__("Default"))}</span></label><button type="button" class="odtb-danger" title="${esc(__("Remove"))}" aria-label="${esc(__("Remove status"))}" data-remove-status="${index}">&times;</button></article>`;
    }

    function printStep(template) {
        return `<article class="odtb-card"><div class="odtb-card-head"><h2>${esc(__("Print Settings"))}</h2><p>${esc(__("Header and footer are rendered on the generic annex document print format."))}</p></div><div class="odtb-grid-2">${input("print_title", __("Print Title"), template.print_title || "")}<label class="odtb-check"><input type="checkbox" data-field="show_signature_block" ${template.show_signature_block ? "checked" : ""}/><span>${esc(__("Show Signature Block"))}</span></label></div><div class="odtb-grid-2 mt">${textarea("print_header", __("Print Header"), template.print_header || "")}${textarea("print_footer", __("Print Footer"), template.print_footer || "")}</div></article>`;
    }

    function emptyRow(message) { return `<div class="odtb-empty">${esc(message)}</div>`; }

    function bind(page) {
        page.main.find("[data-back]").on("click", () => frappe.set_route("document-template-manager"));
        page.main.find("[data-step]").on("click", function () { collect(page); STATE.activeStep = $(this).data("step"); render(page); });
        page.main.find("[data-add-field]").on("click", () => { collect(page); STATE.template.fields.push({ field_label: "", field_key: "", fieldtype: "Data", display_order: STATE.template.fields.length + 1 }); render(page); });
        page.main.find("[data-add-layout]").on("click", function () { collect(page); const type = $(this).data("add-layout"); STATE.template.fields.push({ field_label: type === "Section Break" ? "New Section" : "Column", field_key: "", fieldtype: type, display_order: STATE.template.fields.length + 1 }); render(page); });
        page.main.find("[data-add-status]").on("click", () => { collect(page); STATE.template.statuses.push({ status_label: "", color: "Gray", is_default: 0, display_order: STATE.template.statuses.length + 1 }); render(page); });
        page.main.find("[data-remove-field]").on("click", function () { collect(page); STATE.template.fields.splice(Number($(this).data("remove-field")), 1); render(page); });
        page.main.find("[data-remove-status]").on("click", function () { collect(page); STATE.template.statuses.splice(Number($(this).data("remove-status")), 1); render(page); });
        page.main.find("[data-save]").on("click", () => save(page));
    }

    function collect(page) {
        const root = page.main;
        if (!STATE.template) STATE.template = blankTemplate();
        ["template_name", "display_order", "print_title", "print_header", "print_footer"].forEach((field) => { const el = root.find(`[data-field="${field}"]`); if (el.length) STATE.template[field] = el.val(); });
        if (root.find('[data-field="is_active"]').length) STATE.template.is_active = root.find('[data-field="is_active"]').is(":checked") ? 1 : 0;
        if (root.find('[data-field="show_signature_block"]').length) STATE.template.show_signature_block = root.find('[data-field="show_signature_block"]').is(":checked") ? 1 : 0;
        if (root.find("[data-target-doctype]").length) STATE.template.targets = root.find("[data-target-doctype]:checked").map(function () { return { target_doctype: $(this).data("target-doctype") }; }).get();
        if (root.find("[data-field-index]").length) STATE.template.fields = root.find("[data-field-index]").map(function () { return collectRow($(this), ["field_label", "field_key", "fieldtype", "options", "is_required", "default_value", "display_order"]); }).get();
        if (root.find("[data-status-index]").length) STATE.template.statuses = root.find("[data-status-index]").map(function () { return collectRow($(this), ["status_label", "color", "is_default", "display_order"]); }).get();
    }

    function collectRow(row, fields) {
        const out = {};
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

    function input(field, label, value, type = "text", required = false, row = false) { return `<label><span>${esc(label)}${required ? " *" : ""}</span><input type="${esc(type)}" ${row ? `data-row-field="${esc(field)}"` : `data-field="${esc(field)}"`} value="${esc(value)}" /></label>`; }
    function textarea(field, label, value, row = false) { return `<label class="odtb-textarea"><span>${esc(label)}</span><textarea ${row ? `data-row-field="${esc(field)}"` : `data-field="${esc(field)}"`}>${esc(value)}</textarea></label>`; }
    function options(values, selected) { return values.map((value) => `<option value="${esc(value)}" ${value === selected ? "selected" : ""}>${esc(__(value))}</option>`).join(""); }
    function esc(value) { return frappe.utils.escape_html(value == null ? "" : String(value)); }

    function injectStyles() {
        if (document.getElementById("odtb-style")) return;
        const style = document.createElement("style");
        style.id = "odtb-style";
        style.textContent = `
            .odtb-root{background:#f6f8fb;min-height:100vh}.odtb-shell{width:min(1440px,100%);margin:0 auto;padding:18px clamp(12px,2vw,24px) 56px;color:#172033}.odtb-breadcrumb{display:flex;align-items:center;gap:7px;margin-bottom:10px;color:#64748b;font-size:12px;font-weight:800}.odtb-breadcrumb a{color:#2563eb;text-decoration:none}.odtb-hero{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;padding:20px 22px;border:1px solid #dbe5ef;border-radius:18px;background:linear-gradient(135deg,#fff 0%,#f0f7ff 100%);box-shadow:0 10px 24px rgba(15,23,42,.055)}.odtb-hero span{display:inline-flex;margin-bottom:6px;color:#2563eb;font-size:11px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.odtb-hero h1{margin:0;font-size:clamp(24px,2.5vw,34px);letter-spacing:-.04em;line-height:1.04}.odtb-hero p{max-width:740px;margin:7px 0 0;color:#475569;font-size:13px;line-height:1.5}.odtb-actions,.odtb-mini-actions{display:flex;gap:8px;flex-wrap:wrap}.odtb-primary,.odtb-secondary{min-height:36px;border-radius:10px;padding:0 14px;font-size:13px;font-weight:900;cursor:pointer}.odtb-primary{border:0;background:#2563eb;color:#fff;box-shadow:0 8px 18px rgba(37,99,235,.2)}.odtb-secondary{border:1px solid #bfdbfe;background:#eff6ff;color:#1d4ed8}.odtb-steps{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:12px}.odtb-steps button{min-height:40px;border:1px solid #dbe5ef;border-radius:12px;background:#fff;color:#475569;font-size:13px;font-weight:900;cursor:pointer}.odtb-steps button.active{border-color:#93c5fd;background:#eff6ff;color:#1d4ed8;box-shadow:0 0 0 2px rgba(37,99,235,.07)}.odtb-workspace{margin-top:12px}.odtb-card{border:1px solid #dbe5ef;border-radius:16px;background:#fff;padding:16px;box-shadow:0 8px 22px rgba(15,23,42,.04)}.odtb-card-head{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;margin-bottom:14px}.odtb-card-head.with-action{align-items:center}.odtb-card h2{margin:0;font-size:17px}.odtb-card p{margin:4px 0 0;color:#64748b;font-size:13px}.odtb-grid-2,.odtb-grid-3{display:grid;gap:12px}.odtb-grid-2{grid-template-columns:repeat(2,minmax(0,1fr))}.odtb-grid-3{grid-template-columns:2fr .8fr auto;align-items:end}.odtb-grid-2.mt{margin-top:12px}.odtb-card label,.odtb-line label{display:grid;gap:5px;color:#334155;font-weight:900;font-size:12px}.odtb-card input,.odtb-card select,.odtb-card textarea,.odtb-line input,.odtb-line select,.odtb-line textarea{width:100%;min-height:36px;border:1px solid #cbd5e1;border-radius:9px;background:#fff;padding:0 10px;color:#172033;font-size:13px}.odtb-card textarea,.odtb-line textarea{min-height:64px;padding:8px 10px;resize:vertical}.odtb-check{display:flex!important;align-items:center;gap:8px;min-height:36px}.odtb-check input[type=checkbox]{appearance:none;-webkit-appearance:none;display:grid;place-items:center;width:16px!important;height:16px!important;min-height:16px!important;margin:0;padding:0!important;border:1px solid #94a3b8!important;border-radius:4px;background:#fff!important;cursor:pointer}.odtb-check input[type=checkbox]:checked{border-color:#2563eb!important;background:#2563eb!important}.odtb-check input[type=checkbox]:checked:before{content:'\\2713';color:#fff;font-size:12px;font-weight:900;line-height:1}.odtb-check.inline{align-self:end;margin-bottom:8px}.odtb-target-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}.odtb-target{position:relative;display:grid;align-content:center;min-height:88px;border:1px solid #dbe5ef;border-radius:14px;background:#f8fafc;padding:14px;cursor:pointer}.odtb-target input{position:absolute;opacity:0}.odtb-target strong{font-size:14px}.odtb-target small{margin-top:4px;color:#64748b;font-weight:800}.odtb-target.selected{border-color:#60a5fa;background:#eff6ff;box-shadow:0 0 0 2px rgba(37,99,235,.08)}.odtb-target.selected:after{content:'\\2713';position:absolute;right:10px;top:10px;display:grid;place-items:center;width:21px;height:21px;border-radius:999px;background:#2563eb;color:#fff;font-size:12px;font-weight:900}.odtb-field-builder,.odtb-status-builder{display:grid;gap:10px}.odtb-line{display:grid;grid-template-columns:minmax(170px,1.2fr) minmax(145px,.9fr) 160px 76px 104px minmax(140px,.8fr) minmax(210px,1fr) 34px;gap:10px;align-items:end;border:1px solid #dbe5ef;border-radius:13px;background:#fff;padding:12px}.odtb-line.layout{background:#f8fbff;border-style:dashed}.odtb-line.status{grid-template-columns:minmax(260px,1.4fr) minmax(170px,.8fr) 90px 110px 34px}.odtb-danger{width:34px;height:34px;border:1px solid #fecaca;border-radius:9px;background:#fff1f2;color:#b91c1c;font-size:18px;font-weight:900;line-height:1;cursor:pointer}.odtb-danger:hover{background:#fee2e2;border-color:#fca5a5}.odtb-empty{border:1px dashed #cbd5e1;border-radius:13px;background:#f8fafc;padding:22px;text-align:center;color:#64748b;font-weight:800}@media(max-width:1100px){.odtb-steps,.odtb-target-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.odtb-grid-2,.odtb-grid-3{grid-template-columns:1fr}.odtb-line,.odtb-line.status{grid-template-columns:1fr 1fr}.odtb-danger{width:100%}}@media(max-width:720px){.odtb-shell{padding:14px 10px 48px}.odtb-hero,.odtb-card-head{display:grid}.odtb-actions,.odtb-mini-actions{width:100%}.odtb-actions button,.odtb-mini-actions button{flex:1}.odtb-steps,.odtb-target-grid,.odtb-line,.odtb-line.status{grid-template-columns:1fr}.odtb-hero h1{font-size:28px}}
        `;
        document.head.appendChild(style);
    }
})();
