(function () {
    const SUPPORTED_DOCTYPES = ["Opportunity", "Project", "Quotation", "Sales Order", "Forecast Load Plan"];

    SUPPORTED_DOCTYPES.forEach((doctype) => {
        frappe.ui.form.on(doctype, {
            refresh(frm) {
                if (!frm || frm.is_new()) return;
                frm.add_custom_button(__("Fiches annexes"), () => openAnnexDialog(frm));
            },
        });
    });

    async function openAnnexDialog(frm) {
        injectStyles();
        let bundle;
        try {
            const res = await frappe.call({
                method: "orderlift.document_templates.get_annex_bundle",
                args: { reference_doctype: frm.doctype, reference_name: frm.doc.name },
                freeze: true,
                freeze_message: __("Chargement des fiches annexes..."),
            });
            bundle = res.message || { templates: [] };
        } catch (error) {
            console.error("Unable to load annex document templates", error);
            frappe.msgprint({ message: __("Impossible de charger les fiches annexes."), indicator: "red" });
            return;
        }

        const entries = bundle.templates || [];
        const state = { active: entries[0] ? entries[0].template.name : "" };
        const dialog = new frappe.ui.Dialog({
            title: __("Fiches annexes"),
            size: "extra-large",
            fields: [{ fieldtype: "HTML", fieldname: "body" }],
        });
        dialog.show();
        renderDialog(frm, dialog, entries, state);
    }

    function renderDialog(frm, dialog, entries, state) {
        const body = dialog.fields_dict.body.$wrapper;
        if (!entries.length) {
            body.html(`<div class="ol-annex-dialog-empty">${esc(__("Aucune fiche annexe configurée pour ce document."))}</div>`);
            return;
        }

        const activeEntry = entries.find((entry) => entry.template.name === state.active) || entries[0];
        state.active = activeEntry.template.name;
        body.html(`
            <div class="ol-annex-dialog">
                <aside class="ol-annex-dialog-list">
                    <div class="ol-annex-dialog-list-head">
                        <span>${esc(__("Fiches"))}</span>
                        <strong>${entries.length}</strong>
                    </div>
                    ${entries.map((entry) => templateButton(entry, state.active)).join("")}
                </aside>
                <section class="ol-annex-dialog-panel">
                    ${panelMarkup(activeEntry)}
                </section>
            </div>
        `);

        body.find("[data-annex-template-switch]").on("click", function () {
            state.active = $(this).data("annex-template-switch");
            renderDialog(frm, dialog, entries, state);
        });
        body.find("[data-annex-save]").on("click", function () {
            saveAnnex(frm, dialog, entries, state, $(this).data("annex-save"));
        });
        body.find("[data-annex-print]").on("click", function () {
            const entry = entries.find((row) => row.template.name === $(this).data("annex-print"));
            const annexName = entry && entry.annex && entry.annex.name;
            if (!annexName) return;
            window.open(`/printview?doctype=Orderlift%20Annex%20Document&name=${encodeURIComponent(annexName)}&format=Orderlift%20Annex%20Document&no_letterhead=0`, "_blank");
        });
    }

    function templateButton(entry, active) {
        const template = entry.template;
        const annex = entry.annex || {};
        const isActive = template.name === active;
        const fieldCount = Number((template.fields || []).filter((field) => !["Section Break", "Column Break", "HTML"].includes(field.fieldtype)).length);
        return `
            <button type="button" class="ol-annex-dialog-item ${isActive ? "active" : ""}" data-annex-template-switch="${esc(template.name)}">
                <span class="ol-annex-dialog-item-kicker">${esc(__("Fiche annexe"))}</span>
                <strong>${esc(__(template.template_name))}</strong>
                <span class="ol-annex-dialog-item-meta"><em>${esc(__(annex.status || getDefaultStatus(template)))}</em><small>${fieldCount} ${esc(__("champs"))}</small></span>
            </button>
        `;
    }

    function panelMarkup(entry) {
        const template = entry.template;
        const annex = entry.annex || { values: {} };
        return `
            <div class="ol-annex-dialog-head">
                <div>
                    <span>${esc(__("Fiche annexe"))}</span>
                    <h3>${esc(__(template.template_name))}</h3>
                    <p>${esc(__("Complétez les informations liées à ce document, puis enregistrez ou imprimez la fiche."))}</p>
                </div>
                <div class="ol-annex-dialog-actions">
                    <label><span>${esc(__("Statut"))}</span><select data-annex-status="${esc(template.name)}">${statusOptions(template, annex.status)}</select></label>
                    <button type="button" class="btn btn-sm btn-default" data-annex-save="${esc(template.name)}">${esc(__("Enregistrer"))}</button>
                    <button type="button" class="btn btn-sm btn-primary" data-annex-print="${esc(template.name)}" ${annex.name ? "" : "disabled"}>${esc(__("Imprimer"))}</button>
                </div>
            </div>
            <div class="ol-annex-dialog-fields">
                ${(template.fields || []).map((field) => fieldMarkup(template, field, annex.values || {})).join("") || `<div class="ol-annex-dialog-empty">${esc(__("Aucun champ configuré pour cette fiche."))}</div>`}
            </div>
        `;
    }

    function statusOptions(template, current) {
        const statuses = template.statuses && template.statuses.length ? template.statuses : [{ status_label: "Brouillon", is_default: 1 }];
        const selected = current || getDefaultStatus(template);
        return statuses.map((row) => `<option value="${esc(row.status_label)}" ${row.status_label === selected ? "selected" : ""}>${esc(__(row.status_label))}</option>`).join("");
    }

    function getDefaultStatus(template) {
        const statuses = template.statuses || [];
        const status = statuses.find((row) => row.is_default) || statuses[0];
        return status ? status.status_label : "Brouillon";
    }

    function fieldMarkup(template, field, values) {
        if (field.fieldtype === "Section Break") {
            return `<div class="ol-annex-dialog-section"><h4>${esc(__(field.field_label))}</h4>${field.options ? `<p>${esc(field.options)}</p>` : ""}</div>`;
        }
        if (field.fieldtype === "Column Break") return "";
        if (field.fieldtype === "HTML") return `<div class="ol-annex-dialog-html">${field.options || field.default_value || ""}</div>`;

        const value = values[field.field_key] != null ? values[field.field_key] : (field.default_value || "");
        const common = `data-annex-template="${esc(template.name)}" data-annex-field="${esc(field.field_key)}"`;
        const required = field.is_required ? `<em>${esc(__("Obligatoire"))}</em>` : "";
        let control = "";
        if (["Small Text", "Text", "Text Editor"].includes(field.fieldtype)) {
            control = `<textarea ${common}>${esc(value)}</textarea>`;
        } else if (field.fieldtype === "Select") {
            const options = String(field.options || "").split("\n").map((row) => row.trim()).filter(Boolean);
            control = `<select ${common}>${options.map((option) => `<option value="${esc(option)}" ${option === value ? "selected" : ""}>${esc(__(option))}</option>`).join("")}</select>`;
        } else if (field.fieldtype === "Check") {
            control = `<label class="ol-annex-dialog-check"><input type="checkbox" ${common} ${["1", "true", "True", true].includes(value) ? "checked" : ""} /> <span>${esc(__("Oui"))}</span></label>`;
        } else if (field.fieldtype === "Link") {
            control = `<input type="text" ${common} value="${esc(value)}" placeholder="${esc(field.options || __("Nom du document lié"))}" />`;
        } else if (field.fieldtype === "Attach" || field.fieldtype === "Attach Image") {
            control = `<input type="text" ${common} value="${esc(value)}" placeholder="${esc(__("URL ou chemin du fichier"))}" />`;
        } else {
            const type = field.fieldtype === "Date" ? "date" : (field.fieldtype === "Datetime" ? "datetime-local" : (field.fieldtype === "Time" ? "time" : (["Int", "Float", "Currency"].includes(field.fieldtype) ? "number" : "text")));
            control = `<input type="${type}" ${common} value="${esc(value)}" />`;
        }
        const wide = ["Small Text", "Text", "Text Editor", "Attach Image"].includes(field.fieldtype);
        return `<label class="ol-annex-dialog-field ${wide ? "wide" : ""}"><span>${esc(__(field.field_label))}${required}</span>${control}</label>`;
    }

    async function saveAnnex(frm, dialog, entries, state, templateName) {
        const entry = entries.find((row) => row.template.name === templateName);
        if (!entry) return;

        const body = dialog.fields_dict.body.$wrapper;
        const values = {};
        let missing = "";
        (entry.template.fields || []).forEach((field) => {
            if (["Section Break", "Column Break", "HTML"].includes(field.fieldtype)) return;
            const control = body.find(`[data-annex-template="${cssEscape(templateName)}"][data-annex-field="${cssEscape(field.field_key)}"]`);
            const value = field.fieldtype === "Check" ? (control.is(":checked") ? "1" : "0") : String(control.val() || "").trim();
            if (field.is_required && !value) missing = missing || field.field_label;
            values[field.field_key] = value;
        });
        if (missing) {
            frappe.msgprint({ message: __("Le champ {0} est obligatoire.", [missing]), indicator: "red" });
            return;
        }

        const status = body.find(`[data-annex-status="${cssEscape(templateName)}"]`).val() || getDefaultStatus(entry.template);
        const res = await frappe.call({
            method: "orderlift.document_templates.save_annex_document",
            args: { reference_doctype: frm.doctype, reference_name: frm.doc.name, template: templateName, status, values: JSON.stringify(values) },
            freeze: true,
            freeze_message: __("Enregistrement de la fiche annexe..."),
        });
        if (res.message && res.message.annex) {
            entry.annex = res.message.annex;
            frappe.show_alert({ message: __("Fiche annexe enregistrée"), indicator: "green" });
            renderDialog(frm, dialog, entries, state);
        }
    }

    function cssEscape(value) {
        if (window.CSS && CSS.escape) return CSS.escape(String(value));
        return String(value).replace(/"/g, '\\"');
    }

    function esc(value) { return frappe.utils.escape_html(value == null ? "" : String(value)); }

    function injectStyles() {
        if (document.getElementById("ol-annex-dialog-style")) return;
        const style = document.createElement("style");
        style.id = "ol-annex-dialog-style";
        style.textContent = `
            .modal-xl .ol-annex-dialog{margin:-8px -8px 0}.ol-annex-dialog{display:grid;grid-template-columns:280px minmax(0,1fr);min-height:620px;max-height:72vh;border:1px solid #dbe5ef;border-radius:18px;overflow:hidden;background:#fff;box-shadow:0 14px 34px rgba(15,23,42,.08)}.ol-annex-dialog-list{display:grid;align-content:start;gap:9px;padding:14px;background:linear-gradient(180deg,#f8fbff 0%,#f8fafc 100%);border-right:1px solid #e2e8f0;overflow:auto}.ol-annex-dialog-list-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:2px;padding:8px 2px;color:#64748b}.ol-annex-dialog-list-head span{font-size:11px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.ol-annex-dialog-list-head strong{display:grid;place-items:center;min-width:28px;height:24px;border-radius:999px;background:#dbeafe;color:#1d4ed8;font-size:12px}.ol-annex-dialog-item{display:grid;gap:6px;width:100%;border:1px solid #dbe5ef;border-radius:14px;background:#fff;padding:12px;text-align:left;cursor:pointer;transition:border-color .16s ease,box-shadow .16s ease,background .16s ease}.ol-annex-dialog-item:hover{border-color:#bfdbfe;box-shadow:0 8px 18px rgba(15,23,42,.05)}.ol-annex-dialog-item.active{border-color:#60a5fa;background:#eff6ff;box-shadow:0 0 0 2px rgba(37,99,235,.08)}.ol-annex-dialog-item-kicker{color:#2563eb;font-size:10px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.ol-annex-dialog-item strong{color:#172033;font-size:14px;line-height:1.25}.ol-annex-dialog-item-meta{display:flex;gap:7px;align-items:center;justify-content:space-between}.ol-annex-dialog-item-meta em{border-radius:999px;background:#e2e8f0;color:#475569;padding:3px 8px;font-style:normal;font-size:11px;font-weight:900}.ol-annex-dialog-item.active .ol-annex-dialog-item-meta em{background:#dbeafe;color:#1d4ed8}.ol-annex-dialog-item-meta small{color:#64748b;font-size:11px;font-weight:800}.ol-annex-dialog-panel{min-width:0;padding:0;overflow:auto;background:#fff}.ol-annex-dialog-head{position:sticky;top:0;z-index:2;display:flex;justify-content:space-between;gap:16px;align-items:flex-start;padding:18px 18px 14px;background:rgba(255,255,255,.96);border-bottom:1px solid #e2e8f0;backdrop-filter:blur(8px)}.ol-annex-dialog-head>div>span{display:block;margin-bottom:4px;color:#2563eb;font-size:10px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.ol-annex-dialog-head h3{margin:0;color:#0f172a;font-size:22px;font-weight:900;letter-spacing:-.02em}.ol-annex-dialog-head p{max-width:620px;margin:5px 0 0;color:#64748b;font-size:12px;line-height:1.45}.ol-annex-dialog-actions{display:flex;gap:8px;align-items:end;flex-wrap:wrap;justify-content:flex-end}.ol-annex-dialog-actions label{display:grid;gap:4px;min-width:190px;margin:0;color:#334155;font-size:11px;font-weight:900}.ol-annex-dialog-actions .btn{height:34px;font-weight:800}.ol-annex-dialog-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;padding:16px 18px 22px}.ol-annex-dialog-field{display:grid;gap:6px;margin:0;color:#334155;font-size:12px;font-weight:900}.ol-annex-dialog-field.wide{grid-column:1/-1}.ol-annex-dialog-field span{display:flex;gap:6px;align-items:center}.ol-annex-dialog-field em{font-style:normal;color:#b91c1c;font-size:10px}.ol-annex-dialog-field input,.ol-annex-dialog-field select,.ol-annex-dialog-field textarea,.ol-annex-dialog-actions select{min-height:38px;border:1px solid #cbd5e1;border-radius:10px;background:#fff;padding:0 10px;color:#0f172a;font-size:12px;outline:0;transition:border-color .16s ease,box-shadow .16s ease}.ol-annex-dialog-field input:focus,.ol-annex-dialog-field select:focus,.ol-annex-dialog-field textarea:focus,.ol-annex-dialog-actions select:focus{border-color:#60a5fa;box-shadow:0 0 0 3px rgba(96,165,250,.18)}.ol-annex-dialog-field textarea{min-height:86px;padding:9px 10px;resize:vertical}.ol-annex-dialog-section{grid-column:1/-1;margin-top:8px;padding:13px 14px;border:1px solid #dbeafe;border-radius:14px;background:linear-gradient(135deg,#eff6ff 0%,#fff 100%)}.ol-annex-dialog-section h4{margin:0;color:#172033;font-size:15px;font-weight:900}.ol-annex-dialog-section p{margin:4px 0 0;color:#64748b}.ol-annex-dialog-html{grid-column:1/-1;border:1px solid #e2e8f0;border-radius:12px;background:#f8fafc;padding:11px}.ol-annex-dialog-check{display:flex!important;align-items:center;gap:8px;min-height:38px;margin:0}.ol-annex-dialog-check input{width:16px!important;height:16px!important;min-height:16px!important;accent-color:#2563eb}.ol-annex-dialog-empty{display:grid;place-items:center;min-height:260px;border:1px dashed #cbd5e1;border-radius:14px;background:#f8fafc;color:#64748b;font-weight:800;text-align:center}@media(max-width:900px){.ol-annex-dialog{grid-template-columns:1fr;max-height:none}.ol-annex-dialog-list{border-right:0;border-bottom:1px solid #e2e8f0}.ol-annex-dialog-fields{grid-template-columns:1fr}.ol-annex-dialog-head{display:grid}.ol-annex-dialog-actions{justify-content:stretch}.ol-annex-dialog-actions label,.ol-annex-dialog-actions button{width:100%}}
        `;
        document.head.appendChild(style);
    }
})();
