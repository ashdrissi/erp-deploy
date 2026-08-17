(function () {
    const SUPPORTED_DOCTYPES = ["Opportunity", "Project", "Quotation", "Sales Order", "Forecast Load Plan", "Sales Order Technical List Revision"];
    const WORKSPACE_DOCTYPES = new Set(["Project", "Quotation", "Sales Order", "Sales Order Technical List Revision"]);
    const WORKSPACE_JS = "/assets/orderlift/js/fiches_annexes_workspace_20260816a.js";
    const WORKSPACE_CSS = "/assets/orderlift/css/fiches_annexes_workspace_20260816a.css";
    let workspacePromise;

    SUPPORTED_DOCTYPES.forEach((doctype) => {
        frappe.ui.form.on(doctype, {
            refresh(frm) {
                if (!frm || frm.is_new()) return;
                if (!WORKSPACE_DOCTYPES.has(doctype)) {
                    frm.add_custom_button(__("Fiches annexes"), () => openAnnexDialog(frm));
                }
                if (WORKSPACE_DOCTYPES.has(doctype)) mountAnnexWorkspace(frm);
            },
        });
    });

    async function openAnnexDialog(request, options) {
        const normalized = normalizeRequest(request, options);
        const frm = normalized.frm;
        const dialogOptions = normalized.options;
        if (!frm.doctype || !frm.doc.name) {
            frappe.msgprint({ message: __("Save the document before opening its annexes."), indicator: "orange" });
            return;
        }
        injectStyles();
        let bundle;
        try {
            const res = await frappe.call({
                method: "orderlift.document_templates.get_annex_bundle",
                args: {
                    reference_doctype: frm.doctype,
                    reference_name: frm.doc.name,
                    annex_name: dialogOptions.annexName || "",
                },
                freeze: true,
                freeze_message: __("Chargement des fiches annexes..."),
            });
            bundle = res.message || { templates: [] };
        } catch (error) {
            console.error("Unable to load annex document templates", error);
            frappe.msgprint({ message: __("Impossible de charger les fiches annexes."), indicator: "red" });
            return;
        }

        let entries = bundle.templates || [];
        const focusedEntry = entries.find((entry) => {
            if (dialogOptions.annexName) return annexName(entry) === dialogOptions.annexName;
            return dialogOptions.templateName && entry.template && entry.template.name === dialogOptions.templateName;
        });
        if ((dialogOptions.annexName || dialogOptions.templateName) && !focusedEntry) {
            frappe.msgprint({ message: __("The requested annex is not available on this document."), indicator: "orange" });
            return;
        }
        if (focusedEntry && dialogOptions.onlyAnnex) entries = [focusedEntry];
        const state = {
            active: focusedEntry ? focusedEntry.template.name : (entries[0] ? entries[0].template.name : ""),
            readOnly: Boolean(dialogOptions.readOnly || bundle.read_only),
            onChange: dialogOptions.onChange,
        };
        const dialog = new frappe.ui.Dialog({
            title: dialogOptions.title || __("Fiches annexes"),
            size: "extra-large",
            fields: [{ fieldtype: "HTML", fieldname: "body" }],
        });
        dialog.show();
        dialog.$wrapper && dialog.$wrapper.addClass("ol-annex-dialog-modal");
        renderDialog(frm, dialog, entries, state);
    }

    window.orderliftOpenAnnexDialog = openAnnexDialog;

    function normalizeRequest(request, options) {
        const source = request || {};
        const requestOptions = source.options || {};
        const explicitOptions = options || {};
        const pick = (...keys) => {
            for (const values of [explicitOptions, requestOptions, source]) {
                for (const key of keys) {
                    if (values[key] !== undefined && values[key] !== null) return values[key];
                }
            }
            return undefined;
        };
        const mergedOptions = {
            ...requestOptions,
            ...explicitOptions,
            annexName: pick("annexName", "annex_name", "focusAnnex", "focus_annex") || "",
            templateName: pick("templateName", "template_name", "focusTemplate", "focus_template") || "",
            onlyAnnex: Boolean(pick("onlyAnnex", "only_annex")),
            readOnly: pick("readOnly", "read_only"),
            title: pick("title") || "",
            onChange: pick("onChange", "on_change"),
        };
        const candidate = source.frm || source;
        const frm = candidate.doctype && candidate.doc
            ? candidate
            : { doctype: candidate.doctype || "", doc: candidate.doc || { name: "" }, is_new: () => false };
        return { frm, options: mergedOptions };
    }

    function annexName(entry) {
        if (!entry) return "";
        if (typeof entry.annex === "string") return entry.annex;
        return (entry.annex && entry.annex.name) || entry.annex_name || "";
    }

    function mountAnnexWorkspace(frm) {
        loadAnnexWorkspace().then((workspace) => workspace && workspace.mount(frm)).catch((error) => {
            console.error("Unable to initialize the annex workspace", error);
        });
    }

    function loadAnnexWorkspace() {
        if (window.orderliftAnnexWorkspace) return Promise.resolve(window.orderliftAnnexWorkspace);
        if (workspacePromise) return workspacePromise;
        if (!document.querySelector(`link[href="${WORKSPACE_CSS}"]`)) {
            const link = document.createElement("link");
            link.rel = "stylesheet";
            link.href = WORKSPACE_CSS;
            document.head.appendChild(link);
        }
        workspacePromise = new Promise((resolve, reject) => {
            const existing = document.querySelector(`script[src="${WORKSPACE_JS}"]`);
            const script = existing || document.createElement("script");
            const complete = () => resolve(window.orderliftAnnexWorkspace);
            script.addEventListener("load", complete, { once: true });
            script.addEventListener("error", () => reject(new Error("Annex workspace asset failed to load")), { once: true });
            if (!existing) {
                script.src = WORKSPACE_JS;
                document.head.appendChild(script);
            } else if (window.orderliftAnnexWorkspace) {
                complete();
            }
        }).catch((error) => {
            workspacePromise = null;
            throw error;
        });
        return workspacePromise;
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
                    ${panelMarkup(activeEntry, state.readOnly)}
                </section>
            </div>
        `);
        bindFileControls(body, frm);
        if (state.readOnly) {
            body.find("[data-annex-status],[data-annex-field],[data-annex-upload],[data-annex-clear-file]").prop("disabled", true);
        }

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

    function bindFileControls(root, frm) {
        root.find("[data-annex-upload]").on("click", function (event) {
            event.preventDefault();
            const control = $(this).closest("[data-annex-file-control]");
            const imageOnly = Number($(this).data("image-only")) === 1;
            new frappe.ui.FileUploader({
                doctype: frm.doctype,
                docname: frm.doc.name,
                restrictions: imageOnly ? { allowed_file_types: ["image/*"] } : {},
                on_success(file) {
                    const url = file.file_url || file.file_name || "";
                    if (!url) return;
                    control.find("input[type=hidden]").val(url);
                    control.find(".ol-annex-dialog-file-preview").html(imageOnly ? `<img src="${esc(url)}" alt="" />` : `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(String(url).split("/").pop() || url)}</a>`);
                    control.find("[data-annex-upload]").text(__("Remplacer"));
                    control.find("[data-annex-clear-file]").prop("hidden", false);
                },
            });
        });
        root.find("[data-annex-clear-file]").on("click", function (event) {
            event.preventDefault();
            const control = $(this).closest("[data-annex-file-control]");
            control.find("input[type=hidden]").val("");
            control.find(".ol-annex-dialog-file-preview").html(`<span>${esc(__("Aucun fichier"))}</span>`);
            control.find("[data-annex-upload]").text(__("Téléverser"));
            $(this).prop("hidden", true);
        });
    }

    function templateButton(entry, active) {
        const template = entry.template;
        const annex = entry.annex || {};
        const isActive = template.name === active;
        const fieldCount = Number((template.fields || []).filter((field) => !["Section Break", "Column Break", "HTML"].includes(field.fieldtype)).length);
        return `
            <button type="button" class="ol-annex-dialog-item ${isActive ? "active" : ""}" data-annex-template-switch="${esc(template.name)}" aria-pressed="${isActive ? "true" : "false"}">
                <span class="ol-annex-dialog-item-kicker">${esc(__("Fiche annexe"))}</span>
                <strong>${esc(__(template.template_name))}</strong>
                <span class="ol-annex-dialog-item-meta"><em>${esc(__(annex.status || getDefaultStatus(template)))}</em><small>${fieldCount} ${esc(__("champs"))}</small></span>
            </button>
        `;
    }

    function panelMarkup(entry, readOnly) {
        const template = entry.template;
        const annex = entry.annex || { values: {} };
        return `
            <div class="ol-annex-dialog-head">
                <div>
                    <span>${esc(__("Fiche annexe"))}</span>
                    <h3>${esc(__(template.template_name))}</h3>
                    <p>${esc(__(readOnly ? "Cette fiche est figée ou affichée depuis une phase précédente. Elle est en lecture seule." : "Complétez les informations liées à ce document, puis enregistrez ou imprimez la fiche."))}</p>
                </div>
                <div class="ol-annex-dialog-actions">
                    <label><span>${esc(__("Statut"))}</span><select data-annex-status="${esc(template.name)}">${statusOptions(template, annex.status)}</select></label>
                    ${readOnly ? "" : `<button type="button" class="btn btn-sm btn-default" data-annex-save="${esc(template.name)}">${esc(__("Enregistrer"))}</button>`}
                    <button type="button" class="btn btn-sm btn-primary" data-annex-print="${esc(template.name)}" ${annex.name ? "" : "disabled"}>${esc(__("Imprimer"))}</button>
                </div>
            </div>
            <div class="ol-annex-dialog-fields">
                ${fieldsMarkup(template, annex.values || {}) || `<div class="ol-annex-dialog-empty">${esc(__("Aucun champ configuré pour cette fiche."))}</div>`}
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
        if (field.fieldtype === "HTML") return `<div class="ol-annex-dialog-html">${field.options || field.default_value || ""}</div>`;

        const rawValue = values[field.field_key] != null ? values[field.field_key] : (field.default_value || "");
        const value = controlValue(field.fieldtype, rawValue);
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
        } else if (["Attach", "Attach Image", "Signature"].includes(field.fieldtype)) {
            control = fileControl(field, value, common);
        } else {
            const type = field.fieldtype === "Date" ? "date" : (field.fieldtype === "Datetime" ? "datetime-local" : (field.fieldtype === "Time" ? "time" : (["Int", "Float", "Currency"].includes(field.fieldtype) ? "number" : "text")));
            control = `<input type="${type}" ${common} value="${esc(value)}" />`;
        }
        const wide = ["Small Text", "Text", "Text Editor", "Attach", "Attach Image", "Signature", "HTML"].includes(field.fieldtype);
        return `<label class="ol-annex-dialog-field ${wide ? "wide" : ""}"><span>${esc(__(field.field_label))}${required}</span>${control}</label>`;
    }

    function fieldsMarkup(template, values) {
        return splitFieldLayout(template.fields || []).map((section) => `
            <section class="ol-annex-dialog-dynamic-section">
                ${section.label ? `<div class="ol-annex-dialog-section"><h4>${esc(__(section.label))}</h4>${section.description ? `<p>${esc(section.description)}</p>` : ""}</div>` : ""}
                <div class="ol-annex-dialog-columns columns-${Math.min(section.columns.length, 2)}">
                    ${section.columns.map((column) => `<div class="ol-annex-dialog-column">${column.map((field) => fieldMarkup(template, field, values)).join("")}</div>`).join("")}
                </div>
            </section>
        `).join("");
    }

    function splitFieldLayout(fields) {
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
        return sections;
    }

    function fileControl(field, value, common) {
        const image = ["Attach Image", "Signature"].includes(field.fieldtype);
        return `<div class="ol-annex-dialog-file" data-annex-file-control>
            <input type="hidden" ${common} value="${esc(value)}" />
            <div class="ol-annex-dialog-file-preview">${filePreviewMarkup(field, value)}</div>
            <div class="ol-annex-dialog-file-actions">
                <button type="button" class="btn btn-sm btn-default" data-annex-upload data-image-only="${image ? 1 : 0}">${esc(__(value ? "Remplacer" : "Téléverser"))}</button>
                <button type="button" class="btn btn-sm btn-default" data-annex-clear-file ${value ? "" : "hidden"}>${esc(__("Effacer"))}</button>
            </div>
        </div>`;
    }

    function filePreviewMarkup(field, value) {
        if (!value) return `<span>${esc(__(field.fieldtype === "Signature" ? "Aucune signature" : "Aucun fichier"))}</span>`;
        if (["Attach Image", "Signature"].includes(field.fieldtype)) return `<img src="${esc(value)}" alt="${esc(field.field_label)}" />`;
        return `<a href="${esc(value)}" target="_blank" rel="noopener">${esc(String(value).split("/").pop() || value)}</a>`;
    }

    async function saveAnnex(frm, dialog, entries, state, templateName) {
        const entry = entries.find((row) => row.template.name === templateName);
        if (!entry) return;

        const body = dialog.fields_dict.body.$wrapper;
        const values = {};
        let missing = "";
        const status = body.find(`[data-annex-status="${cssEscape(templateName)}"]`).val() || getDefaultStatus(entry.template);
        const selectedStatus = (entry.template.statuses || []).find((row) => row.status_label === status);
        const completing = Boolean(selectedStatus && selectedStatus.is_complete);
        (entry.template.fields || []).forEach((field) => {
            if (["Section Break", "Column Break", "HTML"].includes(field.fieldtype)) return;
            const control = body.find(`[data-annex-template="${cssEscape(templateName)}"][data-annex-field="${cssEscape(field.field_key)}"]`);
            let value = field.fieldtype === "Check" ? (control.is(":checked") ? "1" : "0") : String(control.val() || "").trim();
            if (field.fieldtype === "Datetime") value = value.replace("T", " ");
            const requiredMissing = field.required_value_mode === "Checked"
                ? !["1", "true", "True"].includes(value)
                : !value;
            if (completing && field.is_required && requiredMissing) missing = missing || field.field_label;
            values[field.field_key] = value;
        });
        if (missing) {
            frappe.msgprint({ message: __("Le champ {0} est obligatoire.", [missing]), indicator: "red" });
            return;
        }

        const res = await frappe.call({
            method: "orderlift.document_templates.save_annex_document",
            args: {
                reference_doctype: frm.doctype,
                reference_name: frm.doc.name,
                template: templateName,
                status,
                values: JSON.stringify(values),
                annex_name: annexName(entry),
                expected_modified: entry.annex && entry.annex.modified,
                expect_absent: annexName(entry) ? 0 : 1,
            },
            freeze: true,
            freeze_message: __("Enregistrement de la fiche annexe..."),
        });
        if (res.message && res.message.annex) {
            entry.annex = res.message.annex;
            frappe.show_alert({ message: __("Fiche annexe enregistrée"), indicator: "green" });
            renderDialog(frm, dialog, entries, state);
            if (typeof state.onChange === "function") {
                Promise.resolve(state.onChange(res.message.annex)).catch((error) => {
                    console.error("Unable to refresh the annex workspace", error);
                });
            }
        }
    }

    function cssEscape(value) {
        if (window.CSS && CSS.escape) return CSS.escape(String(value));
        return String(value).replace(/"/g, '\\"');
    }

    function controlValue(fieldtype, value) {
        const text = value == null ? "" : String(value);
        if (fieldtype === "Datetime") return text.replace(" ", "T");
        return text;
    }

    function esc(value) { return frappe.utils.escape_html(value == null ? "" : String(value)); }

    function injectStyles() {
        if (document.getElementById("ol-annex-dialog-style")) return;
        const style = document.createElement("style");
        style.id = "ol-annex-dialog-style";
        style.textContent = `
            .modal-xl .ol-annex-dialog{margin:-8px -8px 0}.ol-annex-dialog{display:grid;grid-template-columns:280px minmax(0,1fr);min-height:620px;max-height:72vh;border:1px solid #dbe5ef;border-radius:18px;overflow:hidden;background:#fff;box-shadow:0 14px 34px rgba(15,23,42,.08)}.ol-annex-dialog-list{display:grid;align-content:start;gap:9px;padding:14px;background:linear-gradient(180deg,#f8fbff 0%,#f8fafc 100%);border-right:1px solid #e2e8f0;overflow:auto}.ol-annex-dialog-list-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:2px;padding:8px 2px;color:#64748b}.ol-annex-dialog-list-head span{font-size:11px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.ol-annex-dialog-list-head strong{display:grid;place-items:center;min-width:28px;height:24px;border-radius:999px;background:#dbeafe;color:#1d4ed8;font-size:12px}.ol-annex-dialog-item{display:grid;gap:6px;width:100%;border:1px solid #dbe5ef;border-radius:14px;background:#fff;padding:12px;text-align:left;cursor:pointer;transition:border-color .16s ease,box-shadow .16s ease,background .16s ease}.ol-annex-dialog-item:hover{border-color:#bfdbfe;box-shadow:0 8px 18px rgba(15,23,42,.05)}.ol-annex-dialog-item.active{border-color:#60a5fa;background:#eff6ff;box-shadow:0 0 0 2px rgba(37,99,235,.08)}.ol-annex-dialog-item-kicker{color:#2563eb;font-size:10px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.ol-annex-dialog-item strong{color:#172033;font-size:14px;line-height:1.25}.ol-annex-dialog-item-meta{display:flex;gap:7px;align-items:center;justify-content:space-between}.ol-annex-dialog-item-meta em{border-radius:999px;background:#e2e8f0;color:#475569;padding:3px 8px;font-style:normal;font-size:11px;font-weight:900}.ol-annex-dialog-item.active .ol-annex-dialog-item-meta em{background:#dbeafe;color:#1d4ed8}.ol-annex-dialog-item-meta small{color:#64748b;font-size:11px;font-weight:800}.ol-annex-dialog-panel{min-width:0;padding:0;overflow:auto;background:#fff}.ol-annex-dialog-head{position:sticky;top:0;z-index:2;display:flex;justify-content:space-between;gap:16px;align-items:flex-start;padding:18px 18px 14px;background:rgba(255,255,255,.96);border-bottom:1px solid #e2e8f0;backdrop-filter:blur(8px)}.ol-annex-dialog-head>div>span{display:block;margin-bottom:4px;color:#2563eb;font-size:10px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.ol-annex-dialog-head h3{margin:0;color:#0f172a;font-size:22px;font-weight:900;letter-spacing:-.02em}.ol-annex-dialog-head p{max-width:620px;margin:5px 0 0;color:#64748b;font-size:12px;line-height:1.45}.ol-annex-dialog-actions{display:flex;gap:8px;align-items:end;flex-wrap:wrap;justify-content:flex-end}.ol-annex-dialog-actions label{display:grid;gap:4px;min-width:190px;margin:0;color:#334155;font-size:11px;font-weight:900}.ol-annex-dialog-actions .btn{height:34px;font-weight:800}.ol-annex-dialog-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;padding:16px 18px 22px}.ol-annex-dialog-field{display:grid;gap:6px;margin:0;color:#334155;font-size:12px;font-weight:900}.ol-annex-dialog-field.wide{grid-column:1/-1}.ol-annex-dialog-field span{display:flex;gap:6px;align-items:center}.ol-annex-dialog-field em{font-style:normal;color:#b91c1c;font-size:10px}.ol-annex-dialog-field input,.ol-annex-dialog-field select,.ol-annex-dialog-field textarea,.ol-annex-dialog-actions select{min-height:38px;border:1px solid #cbd5e1;border-radius:10px;background:#fff;padding:0 10px;color:#0f172a;font-size:12px;outline:0;transition:border-color .16s ease,box-shadow .16s ease}.ol-annex-dialog-field input:focus,.ol-annex-dialog-field select:focus,.ol-annex-dialog-field textarea:focus,.ol-annex-dialog-actions select:focus{border-color:#60a5fa;box-shadow:0 0 0 3px rgba(96,165,250,.18)}.ol-annex-dialog-field textarea{min-height:86px;padding:9px 10px;resize:vertical}.ol-annex-dialog-section{grid-column:1/-1;margin-top:8px;padding:13px 14px;border:1px solid #dbeafe;border-radius:14px;background:linear-gradient(135deg,#eff6ff 0%,#fff 100%)}.ol-annex-dialog-section h4{margin:0;color:#172033;font-size:15px;font-weight:900}.ol-annex-dialog-section p{margin:4px 0 0;color:#64748b}.ol-annex-dialog-html{grid-column:1/-1;border:1px solid #e2e8f0;border-radius:12px;background:#f8fafc;padding:11px}.ol-annex-dialog-check{display:flex!important;align-items:center;gap:8px;min-height:38px;margin:0}.ol-annex-dialog-check input{width:16px!important;height:16px!important;min-height:16px!important;accent-color:#2563eb}.ol-annex-dialog-empty{display:grid;place-items:center;min-height:260px;border:1px dashed #cbd5e1;border-radius:14px;background:#f8fafc;color:#64748b;font-weight:800;text-align:center}@media(max-width:900px){.ol-annex-dialog{grid-template-columns:1fr;max-height:none}.ol-annex-dialog-list{border-right:0;border-bottom:1px solid #e2e8f0}.ol-annex-dialog-fields{grid-template-columns:1fr}.ol-annex-dialog-head{display:grid}.ol-annex-dialog-actions{justify-content:stretch}.ol-annex-dialog-actions label,.ol-annex-dialog-actions button{width:100%}}
        `;
        style.textContent += `
            .ol-annex-dialog-modal .modal-dialog{max-width:min(1200px,calc(100vw - 32px));margin-top:16px;margin-bottom:16px;}
            .ol-annex-dialog-modal .modal-content{max-height:calc(100vh - 32px);display:flex;flex-direction:column;overflow:hidden;}
            .ol-annex-dialog-modal .modal-body{min-height:0;overflow:hidden;padding-bottom:12px;}
            .ol-annex-dialog-modal .modal-body .frappe-control,
            .ol-annex-dialog-modal .modal-body .control-input-wrapper,
            .ol-annex-dialog-modal .modal-body .control-value,
            .ol-annex-dialog-modal [data-fieldname="body"]{min-height:0;height:100%;}
            .modal-dialog.modal-xl:has(.ol-annex-dialog), .modal-dialog.modal-extra-large:has(.ol-annex-dialog){max-width:min(1200px,calc(100vw - 32px));}
            .modal-dialog:has(.ol-annex-dialog){margin-top:16px;margin-bottom:16px;}
            .modal-content:has(.ol-annex-dialog){max-height:calc(100vh - 32px);display:flex;flex-direction:column;overflow:hidden;}
            .modal-content:has(.ol-annex-dialog) .modal-body{min-height:0;overflow:hidden;padding-bottom:12px;}
            .modal-content:has(.ol-annex-dialog) .modal-body .frappe-control,
            .modal-content:has(.ol-annex-dialog) .modal-body .control-input-wrapper,
            .modal-content:has(.ol-annex-dialog) .modal-body .control-value,
            .modal-content:has(.ol-annex-dialog) [data-fieldname="body"]{min-height:0;height:100%;}
            .modal-xl .ol-annex-dialog,
            .modal-extra-large .ol-annex-dialog,
            .ol-annex-dialog{min-height:0;height:calc(100vh - 154px);max-height:calc(100vh - 154px);}
            .ol-annex-dialog-list,.ol-annex-dialog-panel{min-height:0;max-height:100%;overscroll-behavior:contain;}
            .ol-annex-dialog-fields{padding-bottom:18px;}
            @media (max-width: 767px){.modal-dialog:has(.ol-annex-dialog){margin:8px}.modal-xl .ol-annex-dialog,.modal-extra-large .ol-annex-dialog,.ol-annex-dialog{height:calc(100vh - 120px);max-height:calc(100vh - 120px);grid-template-columns:1fr}.ol-annex-dialog-list{max-height:220px;border-right:0;border-bottom:1px solid #e2e8f0}.ol-annex-dialog-panel{max-height:none}}
        `;
        style.textContent += `
            .ol-annex-dialog-fields{display:block}.ol-annex-dialog-dynamic-section+.ol-annex-dialog-dynamic-section{margin-top:14px}.ol-annex-dialog-columns{display:grid;grid-template-columns:1fr;gap:14px}.ol-annex-dialog-columns.columns-2{grid-template-columns:repeat(2,minmax(0,1fr))}.ol-annex-dialog-column{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;align-content:start}.ol-annex-dialog-columns.columns-2 .ol-annex-dialog-column{grid-template-columns:1fr}.ol-annex-dialog-file{display:grid;gap:7px;padding:8px;border:1px solid #e2e8f0;border-radius:10px;background:#f8fafc}.ol-annex-dialog-file-preview{display:flex;align-items:center;justify-content:center;min-height:42px;color:#64748b;font-weight:600}.ol-annex-dialog-file-preview img{display:block;max-width:100%;max-height:150px;object-fit:contain}.ol-annex-dialog-file-preview a{word-break:break-all}.ol-annex-dialog-file-actions{display:flex;gap:6px;justify-content:flex-end}@media(max-width:767px){.ol-annex-dialog-columns.columns-2,.ol-annex-dialog-column{grid-template-columns:1fr}}
        `;
        document.head.appendChild(style);
    }
})();
