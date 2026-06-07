(function () {
    const SUPPORTED_DOCTYPES = ["Opportunity", "Project", "Quotation", "Sales Order", "Forecast Load Plan"];
    const HOST_CLASS = "ol-annex-host";

    SUPPORTED_DOCTYPES.forEach((doctype) => {
        frappe.ui.form.on(doctype, {
            refresh(frm) {
                renderAnnexTabs(frm);
            },
        });
    });

    async function renderAnnexTabs(frm) {
        if (!frm || frm.is_new()) {
            removeHost(frm);
            return;
        }
        injectStyles();
        let bundle;
        try {
            const res = await frappe.call({
                method: "orderlift.document_templates.get_annex_bundle",
                args: { reference_doctype: frm.doctype, reference_name: frm.doc.name },
            });
            bundle = res.message || { templates: [] };
        } catch (error) {
            console.error("Unable to load annex document templates", error);
            return;
        }
        drawTabs(frm, bundle.templates || []);
    }

    function removeHost(frm) {
        if (!frm || !frm.$wrapper) return;
        frm.$wrapper.find(`.${HOST_CLASS}`).remove();
        removeDynamicTabs(frm, new Set());
    }

    function ensureHost(frm, template) {
        const fieldname = tabFieldname(template.name);
        let host = frm.$wrapper.find(`[data-annex-host="${cssEscape(template.name)}"]`);
        if (host.length) return host;

        host = $(`<div class="${HOST_CLASS}" data-annex-host="${esc(template.name)}"></div>`);
        const tab = ensureTemplateTab(frm, template, fieldname);
        if (tab && tab.wrapper) {
            $(tab.wrapper).addClass("ol-annex-frappe-tab").append(host);
        } else {
            const layout = frm.$wrapper.find(".form-layout").first();
            if (layout.length) layout.append(host);
            else frm.$wrapper.append(host);
        }
        return host;
    }

    function ensureTemplateTab(frm, template, fieldname) {
        if (!frm.layout || !frm.layout.make_tab || !frm.layout.tabs_content || !frm.layout.tab_link_container) return null;
        const existing = (frm.layout.tabs || []).find((tab) => tab.df && tab.df.fieldname === fieldname);
        if (existing) return existing;

        const tab = frm.layout.make_tab({
            fieldtype: "Tab Break",
            fieldname,
            label: template.template_name,
        });
        tab.is_orderlift_annex = true;
        tab.tab_link && tab.tab_link.addClass("ol-annex-form-tab");
        tab.wrapper && $(tab.wrapper).attr("data-orderlift-annex-tab", template.name);
        return tab;
    }

    function removeDynamicTabs(frm, keepFieldnames) {
        if (!frm || !frm.layout || !frm.layout.tabs) return;
        frm.layout.tabs = frm.layout.tabs.filter((tab) => {
            if (!tab.is_orderlift_annex || keepFieldnames.has(tab.df.fieldname)) return true;
            tab.tab_link && tab.tab_link.parent().remove();
            tab.wrapper && $(tab.wrapper).remove();
            return false;
        });
    }

    function drawTabs(frm, entries) {
        if (!entries.length) {
            removeHost(frm);
            return;
        }
        const keep = new Set(entries.map((entry) => tabFieldname(entry.template.name)));
        removeDynamicTabs(frm, keep);
        entries.forEach((entry) => drawTemplateTab(frm, entry));
    }

    function drawTemplateTab(frm, entry) {
        const host = ensureHost(frm, entry.template);
        host.html(`
            <section class="ol-annex-shell">
                <div class="ol-annex-head">
                    <div>
                        <span>${esc(__("Annexed Documents"))}</span>
                        <h3>${esc(__(entry.template.template_name))}</h3>
                    </div>
                    <small>${esc(__(entry.annex && entry.annex.status ? entry.annex.status : "Draft"))}</small>
                </div>
                <div class="ol-annex-panels">
                    ${panelMarkup(entry, true)}
                </div>
            </section>
        `);
        bindTabs(frm, host, [entry]);
    }

    function panelMarkup(entry, active) {
        const template = entry.template;
        const annex = entry.annex || { values: {} };
        const isActive = active === true || template.name === active;
        return `
            <article class="ol-annex-panel ${isActive ? "active" : ""}" data-annex-panel="${esc(template.name)}">
                <div class="ol-annex-toolbar">
                    <label><span>${esc(__("Status"))}</span><select data-annex-status="${esc(template.name)}">${statusOptions(template, annex.status)}</select></label>
                    <div class="ol-annex-actions">
                        <button type="button" class="btn btn-sm btn-default" data-annex-save="${esc(template.name)}">${esc(__("Save"))}</button>
                        <button type="button" class="btn btn-sm btn-primary" data-annex-print="${esc(template.name)}" ${annex.name ? "" : "disabled"}>${esc(__("Print"))}</button>
                    </div>
                </div>
                <div class="ol-annex-fields">
                    ${(template.fields || []).map((field) => fieldMarkup(template, field, annex.values || {})).join("") || `<div class="ol-annex-empty">${esc(__("No fields configured for this template."))}</div>`}
                </div>
            </article>
        `;
    }

    function statusOptions(template, current) {
        const statuses = template.statuses && template.statuses.length ? template.statuses : [{ status_label: "Draft" }];
        const selected = current || statuses.find((row) => row.is_default)?.status_label || statuses[0].status_label;
        return statuses.map((row) => `<option value="${esc(row.status_label)}" ${row.status_label === selected ? "selected" : ""}>${esc(__(row.status_label))}</option>`).join("");
    }

    function fieldMarkup(template, field, values) {
        if (field.fieldtype === "Section Break") {
            return `<div class="ol-annex-section"><h4>${esc(__(field.field_label))}</h4>${field.options ? `<p>${esc(field.options)}</p>` : ""}</div>`;
        }
        if (field.fieldtype === "Column Break") {
            return `<div class="ol-annex-column-break" aria-hidden="true"></div>`;
        }
        if (field.fieldtype === "HTML") {
            return `<div class="ol-annex-html">${field.options || field.default_value || ""}</div>`;
        }
        const value = values[field.field_key] != null ? values[field.field_key] : (field.default_value || "");
        const common = `data-annex-template="${esc(template.name)}" data-annex-field="${esc(field.field_key)}"`;
        const required = field.is_required ? `<em>${esc(__("Required"))}</em>` : "";
        let control = "";
        if (field.fieldtype === "Small Text" || field.fieldtype === "Text" || field.fieldtype === "Text Editor") {
            control = `<textarea ${common}>${esc(value)}</textarea>`;
        } else if (field.fieldtype === "Select") {
            const options = String(field.options || "").split("\n").map((row) => row.trim()).filter(Boolean);
            control = `<select ${common}>${options.map((option) => `<option value="${esc(option)}" ${option === value ? "selected" : ""}>${esc(__(option))}</option>`).join("")}</select>`;
        } else if (field.fieldtype === "Check") {
            control = `<label class="ol-annex-checkbox"><input type="checkbox" ${common} ${["1", "true", "True", true].includes(value) ? "checked" : ""} /> <span>${esc(__("Yes"))}</span></label>`;
        } else if (field.fieldtype === "Link") {
            control = `<input type="text" ${common} value="${esc(value)}" placeholder="${esc(field.options || __("Linked document name"))}" />`;
        } else if (field.fieldtype === "Attach" || field.fieldtype === "Attach Image") {
            control = `<input type="text" ${common} value="${esc(value)}" placeholder="${esc(__("File URL or attachment path"))}" />`;
        } else {
            const type = field.fieldtype === "Date" ? "date" : (field.fieldtype === "Datetime" ? "datetime-local" : (field.fieldtype === "Time" ? "time" : (["Int", "Float", "Currency"].includes(field.fieldtype) ? "number" : "text")));
            control = `<input type="${type}" ${common} value="${esc(value)}" />`;
        }
        return `<label class="ol-annex-field"><span>${esc(__(field.field_label))}${required}</span>${control}</label>`;
    }

    function bindTabs(frm, host, entries) {
        host.find("[data-annex-save]").on("click", function () {
            saveAnnex(frm, host, entries, $(this).data("annex-save"));
        });
        host.find("[data-annex-print]").on("click", async function () {
            const template = $(this).data("annex-print");
            const entry = entries.find((row) => row.template.name === template);
            const annexName = entry && entry.annex && entry.annex.name;
            if (!annexName) return;
            window.open(`/printview?doctype=Orderlift%20Annex%20Document&name=${encodeURIComponent(annexName)}&format=Orderlift%20Annex%20Document&no_letterhead=0`, "_blank");
        });
    }

    async function saveAnnex(frm, host, entries, templateName) {
        const entry = entries.find((row) => row.template.name === templateName);
        if (!entry) return;
        const values = {};
        let missing = "";
        (entry.template.fields || []).forEach((field) => {
            if (["Section Break", "Column Break", "HTML"].includes(field.fieldtype)) return;
            const control = host.find(`[data-annex-template="${cssEscape(templateName)}"][data-annex-field="${cssEscape(field.field_key)}"]`);
            let value = "";
            if (field.fieldtype === "Check") value = control.is(":checked") ? "1" : "0";
            else value = String(control.val() || "").trim();
            if (field.is_required && !value) missing = missing || field.field_label;
            values[field.field_key] = value;
        });
        if (missing) {
            frappe.msgprint({ message: __("Field {0} is required.", [missing]), indicator: "red" });
            return;
        }
        const status = host.find(`[data-annex-status="${cssEscape(templateName)}"]`).val() || "Draft";
        const res = await frappe.call({
            method: "orderlift.document_templates.save_annex_document",
            args: {
                reference_doctype: frm.doctype,
                reference_name: frm.doc.name,
                template: templateName,
                status,
                values: JSON.stringify(values),
            },
            freeze: true,
        });
        if (res.message && res.message.annex) {
            entry.annex = res.message.annex;
            frappe.show_alert({ message: __("Annex document saved"), indicator: "green" });
            drawTabs(frm, entries);
        }
    }

    function cssEscape(value) {
        if (window.CSS && CSS.escape) return CSS.escape(String(value));
        return String(value).replace(/"/g, '\\"');
    }

    function tabFieldname(name) {
        return `ol_annex_${String(name || "template").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "template"}`;
    }

    function esc(value) { return frappe.utils.escape_html(value == null ? "" : String(value)); }

    function injectStyles() {
        if (document.getElementById("ol-annex-tabs-style")) return;
        const style = document.createElement("style");
        style.id = "ol-annex-tabs-style";
        style.textContent = `
            .ol-annex-host{margin-top:18px}.ol-annex-shell{border:1px solid #dbe5ef;border-radius:16px;background:#fff;overflow:hidden;box-shadow:0 8px 24px rgba(15,23,42,.055)}.ol-annex-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;padding:14px 16px;background:linear-gradient(135deg,#fff 0%,#eff6ff 100%);border-bottom:1px solid #dbeafe}.ol-annex-head span{display:block;margin-bottom:3px;color:#2563eb;font-size:10px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.ol-annex-head h3{margin:0;font-size:16px;font-weight:900}.ol-annex-head small{color:#64748b;font-weight:800}.ol-annex-tabbar{display:flex;gap:8px;overflow:auto;padding:10px 12px;border-bottom:1px solid #e2e8f0;background:#f8fafc}.ol-annex-tab{display:grid;gap:2px;min-width:148px;border:1px solid #dbe5ef;border-radius:12px;background:#fff;padding:9px 11px;text-align:left;cursor:pointer}.ol-annex-tab.active{border-color:#93c5fd;background:#eff6ff;box-shadow:0 0 0 2px rgba(37,99,235,.08)}.ol-annex-tab strong{font-size:12px;color:#172033}.ol-annex-tab span{font-size:10px;color:#64748b;font-weight:800}.ol-annex-panels{padding:14px}.ol-annex-panel{display:none}.ol-annex-panel.active{display:block}.ol-annex-toolbar{display:flex;justify-content:space-between;gap:14px;align-items:end;margin-bottom:13px}.ol-annex-toolbar label{display:grid;gap:4px;min-width:210px;margin:0;color:#334155;font-size:11px;font-weight:800}.ol-annex-actions{display:flex;gap:7px}.ol-annex-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.ol-annex-field{display:grid;gap:5px;margin:0;color:#334155;font-size:11px;font-weight:800}.ol-annex-field span{display:flex;gap:6px;align-items:center}.ol-annex-field em{font-style:normal;color:#b91c1c;font-size:10px}.ol-annex-field input,.ol-annex-field select,.ol-annex-field textarea,.ol-annex-toolbar select{min-height:38px;border:1px solid #cbd5e1;border-radius:10px;background:#fff;padding:0 9px;color:#0f172a;font-size:12px;outline:0}.ol-annex-field textarea{min-height:82px;padding:8px 9px;resize:vertical}.ol-annex-field input:focus,.ol-annex-field select:focus,.ol-annex-field textarea:focus,.ol-annex-toolbar select:focus{border-color:#2563eb;box-shadow:0 0 0 2px rgba(37,99,235,.12)}.ol-annex-checkbox{display:flex!important;align-items:center;gap:8px;min-height:38px}.ol-annex-checkbox input{width:auto;min-height:0}.ol-annex-section{grid-column:1/-1;margin-top:8px;padding:12px 14px;border-left:4px solid #2563eb;border-radius:12px;background:#eff6ff}.ol-annex-section h4{margin:0;color:#1e3a8a;font-size:14px}.ol-annex-section p{margin:4px 0 0;color:#475569;font-size:12px}.ol-annex-column-break{display:none}.ol-annex-html{grid-column:1/-1;padding:12px 14px;border:1px solid #e2e8f0;border-radius:12px;background:#f8fafc}.ol-annex-empty{grid-column:1/-1;padding:12px;border:1px dashed #cbd5e1;border-radius:12px;background:#f8fafc;color:#64748b}@media(max-width:760px){.ol-annex-toolbar{display:grid}.ol-annex-fields{grid-template-columns:1fr}.ol-annex-actions{display:grid;grid-template-columns:1fr 1fr}.ol-annex-toolbar label{min-width:0}}
        `;
        document.head.appendChild(style);
    }
})();
