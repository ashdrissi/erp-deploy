(function () {
    frappe.ui.form.on("Quotation", {
        setup(frm) {
            setupTemplateQuery(frm);
        },
        onload_post_render(frm) {
            applyPresentationTemplateVisibility(frm);
        },
        refresh(frm) {
            setupTemplateQuery(frm);
            refreshTemplateAvailability(frm);
        },
        custom_presentation_mode(frm) {
            refreshTemplateAvailability(frm);
        },
        custom_commercial_presentation_template(frm) {
            if (frm._ol_quote_detail_clearing_template) return;
            refreshTemplateAvailability(frm);
        },
    });

    function isWithoutDetails(frm) {
        return String(frm?.doc?.custom_presentation_mode || "").trim() === "Without details";
    }

    function applyPresentationTemplateVisibility(frm) {
        if (!frm || !frm.set_df_property) return;
        const withoutDetails = isWithoutDetails(frm);
        const availability = frm._ol_quote_detail_availability || null;
        const templatesAvailable = availability ? Boolean((availability.templates || []).length) : true;
        const useTextFallback = withoutDetails && !templatesAvailable;
        if (frm.fields_dict.custom_commercial_designation) {
            frm.set_df_property("custom_commercial_designation", "hidden", withoutDetails && !useTextFallback ? 1 : 0);
            frm.set_df_property("custom_commercial_designation", "reqd", useTextFallback ? 1 : 0);
            frm.set_df_property("custom_commercial_designation", "description", useTextFallback ? __(availability.fallback_reason || "No eligible template is available. Enter the commercial summary text here.") : "");
        }
        if (frm.fields_dict.custom_commercial_presentation_template) {
            frm.set_df_property("custom_commercial_presentation_template", "hidden", withoutDetails && !useTextFallback ? 0 : 1);
            frm.set_df_property("custom_commercial_presentation_template", "reqd", withoutDetails && !useTextFallback && !frm.is_new() ? 1 : 0);
            frm.set_df_property("custom_commercial_presentation_template", "description", withoutDetails && !useTextFallback ? __("Select a template to open the editor, fill the fields, preview the pages, then save the frozen result before submitting.") : "");
        }
        if (frm.fields_dict.custom_commercial_presentation_editor) {
            frm.set_df_property("custom_commercial_presentation_editor", "hidden", withoutDetails && !useTextFallback ? 0 : 1);
        }
    }

    async function refreshTemplateAvailability(frm) {
        applyPresentationTemplateVisibility(frm);
        if (!frm || !isWithoutDetails(frm)) {
            renderInlineEditor(frm, null);
            return;
        }
        if (frm.is_new()) {
            renderInlineEditor(frm, { selected_template: frm.doc.custom_commercial_presentation_template || "", is_new: true });
            return;
        }
        try {
            const res = await frappe.call({
                method: "orderlift.quotation_detail_templates.get_quotation_detail_editor",
                args: { quotation: frm.doc.name, template: frm.doc.custom_commercial_presentation_template || "" },
            });
            const data = res.message || {};
            frm._ol_quote_detail_availability = data;
            if (frm.doc.custom_commercial_presentation_template && !data.selected_template) {
                frm._ol_quote_detail_clearing_template = true;
                await frm.set_value("custom_commercial_presentation_template", "");
                frm._ol_quote_detail_clearing_template = false;
            }
            renderInlineEditor(frm, data);
        } catch (error) {
            console.error("Unable to load commercial presentation availability", error);
            renderInlineEditor(frm, { error: true });
        }
        applyPresentationTemplateVisibility(frm);
    }

    function setupTemplateQuery(frm) {
        if (!frm || !frm.fields_dict || !frm.fields_dict.custom_commercial_presentation_template) return;
        frm.set_query("custom_commercial_presentation_template", () => {
            const company = String(frm.doc.company || "").trim();
            const filters = { is_active: 1 };
            if (company) filters.company = ["in", ["", company]];
            return { filters };
        });
    }

    async function openPresentationDialog(frm, templateName) {
        if (!isWithoutDetails(frm)) {
            frappe.msgprint({ message: __("Select Presentation = Without details before choosing a commercial presentation template."), indicator: "orange" });
            return;
        }
        injectStyles();
        let data;
        try {
            const res = await frappe.call({
                method: "orderlift.quotation_detail_templates.get_quotation_detail_editor",
                args: { quotation: frm.doc.name, template: templateName || frm.doc.custom_commercial_presentation_template || "" },
                freeze: true,
                freeze_message: __("Loading commercial presentation..."),
            });
            data = res.message || {};
        } catch (error) {
            console.error("Unable to load commercial presentation", error);
            frappe.msgprint({ message: __("Unable to load commercial presentation."), indicator: "red" });
            return;
        }

        const dialog = new frappe.ui.Dialog({ title: __("Commercial Presentation"), size: "extra-large", fields: [{ fieldtype: "HTML", fieldname: "body" }] });
        dialog.show();
        dialog.$wrapper && dialog.$wrapper.addClass("ol-quote-detail-dialog-modal");
        renderDialog(frm, dialog, data);
    }

    function renderInlineEditor(frm, data) {
        injectStyles();
        const field = frm?.fields_dict?.custom_commercial_presentation_editor;
        if (!field || !field.$wrapper) return;
        const body = field.$wrapper;
        if (!isWithoutDetails(frm)) {
            body.empty();
            return;
        }
        if (data && data.is_new) {
            body.html(`<div class="ol-quote-detail-inline-empty"><strong>${esc(__("Save the Quotation first"))}</strong><p>${esc(__("After saving, the selected template will show its fillable fields here."))}</p></div>`);
            return;
        }
        if (data && data.error) {
            body.html(`<div class="alert alert-danger">${esc(__("Unable to load the commercial presentation editor."))}</div>`);
            return;
        }
        const selected = data?.selected_template || "";
        const editable = Number(data?.docstatus || 0) === 0;
        body.html(`
            <details class="ol-quote-detail-inline" ${selected ? "open" : ""}>
                <summary><span>${esc(__("Commercial Presentation"))}</span><strong>${esc(selected || __("No template selected"))}</strong></summary>
                ${!editable ? `<div class="alert alert-info">${esc(__("Submitted quotations use the frozen commercial presentation snapshot and cannot be edited."))}</div>` : ""}
                ${data?.fallback_reason ? `<div class="alert alert-warning">${esc(__(data.fallback_reason))}</div>` : ""}
                ${selected ? inlineSummaryMarkup(data, editable) : emptyMarkup(data?.templates || [])}
            </details>
        `);
        body.find("[data-refresh-detail]").on("click", () => refreshTemplateAvailability(frm));
        body.find("[data-open-detail-popup]").on("click", () => openPresentationDialog(frm, selected));
    }

    function inlineSummaryMarkup(data, editable) {
        const blocks = data.blocks || [];
        const required = blocks.filter((block) => block.is_required).length;
        const filled = blocks.filter((block) => block.block_type !== "Page Break" && String(block.value || "").trim()).length;
        const total = blocks.filter((block) => block.block_type !== "Page Break").length;
        return `
            <div class="ol-quote-detail-inline-card">
                <div class="ol-quote-detail-inline-copy">
                    <h4>${esc(data.template?.template_name || data.selected_template || __("Commercial Presentation"))}</h4>
                    <p>${esc(__("Use the popup to fill proposal fields, review the live preview, and save the frozen content used in the PDF."))}</p>
                    <div class="ol-quote-detail-inline-stats"><span>${esc(__("Fields"))}: ${filled}/${total}</span><span>${esc(__("Required"))}: ${required}</span><span>${esc(data.has_snapshot ? __("Snapshot saved") : __("Snapshot not saved"))}</span></div>
                </div>
                <div class="ol-quote-detail-inline-actions">
                    <button type="button" class="btn btn-sm btn-default" data-refresh-detail>${esc(__("Refresh"))}</button>
                    <button type="button" class="btn btn-sm btn-primary" data-open-detail-popup ${editable ? "" : "disabled"}>${esc(__("Commercial Presentation and Details"))}</button>
                </div>
            </div>
        `;
    }

    function renderDialog(frm, dialog, data) {
        const body = dialog.fields_dict.body.$wrapper;
        const editable = Number(data.docstatus || 0) === 0;
        const selected = data.selected_template || "";
        body.html(`
            <div class="ol-quote-detail-dialog">
                <div class="ol-quote-detail-head">
                    <div><span>${esc(__("Without details template"))}</span><h3>${esc(frm.doc.name)}</h3><p>${esc(__("This replaces Commercial Designation. Choose a template, fill the fields, then save the frozen result used in the PDF and summary line."))}</p></div>
                    <div class="ol-quote-detail-actions">
                        <label><span>${esc(__("Template"))}</span><select data-quote-detail-template ${editable ? "" : "disabled"}>${templateOptions(data.templates || [], selected)}</select></label>
                        <button type="button" class="btn btn-sm btn-default" data-refresh-detail ${selected ? "" : "disabled"}>${esc(__("Reload"))}</button>
                        <button type="button" class="btn btn-sm btn-primary" data-save-detail ${editable && selected ? "" : "disabled"}>${esc(__("Save Snapshot"))}</button>
                    </div>
                </div>
                ${!editable ? `<div class="alert alert-info">${esc(__("Submitted quotations use the frozen commercial presentation snapshot and cannot be edited."))}</div>` : ""}
                ${data.fallback_reason ? `<div class="alert alert-warning">${esc(__(data.fallback_reason))}</div>` : ""}
                ${selected ? `<div class="ol-quote-detail-layout"><section class="ol-quote-detail-editor">${blocksMarkup(data.blocks || [], editable)}</section><aside class="ol-quote-detail-preview"><h4>${esc(__("Live Preview"))}</h4><div data-detail-preview></div></aside></div>` : emptyMarkup(data.templates || [])}
            </div>
        `);

        body.find("[data-quote-detail-template]").on("change", async function () {
            const next = $(this).val() || "";
            if (!next) return;
            if (data.has_snapshot) {
                const proceed = await confirmAsync(__("Changing the template reloads the editor from the selected template. Existing saved snapshot values are not carried over. Continue?"));
                if (!proceed) {
                    renderDialog(frm, dialog, data);
                    return;
                }
            }
            dialog.hide();
            openPresentationDialog(frm, next);
        });
        body.find("[data-refresh-detail]").on("click", function () {
            dialog.hide();
            openPresentationDialog(frm, selected);
        });
        body.find("[data-detail-field]").on("input change", () => updatePreview(body, data.blocks || []));
        body.find("[data-save-detail]").on("click", () => saveSnapshot(frm, body, data, dialog));
        updatePreview(body, data.blocks || []);
    }

    function blocksMarkup(blocks, editable) {
        if (!blocks.length) return `<div class="ol-quote-detail-empty">${esc(__("This template has no blocks."))}</div>`;
        return `<div class="ol-quote-detail-blocks">${blocks.map((block) => blockMarkup(block, editable)).join("")}</div>`;
    }

    function blockMarkup(block, editable) {
        if (block.block_type === "Page Break") return `<div class="ol-quote-detail-page-break"><span>${esc(__("Page Break"))}</span></div>`;
        if (block.block_type === "Heading") return `<div class="ol-quote-detail-heading"><input data-detail-field="${esc(block.block_key)}" value="${esc(block.value || block.block_label)}" ${editable && block.allow_manual_override ? "" : "disabled"}/></div>`;

        const value = block.value != null ? block.value : "";
        const source = block.source ? `<small>${esc(__("Source"))}: ${esc(block.source)}</small>` : "";
        const required = block.is_required ? `<em>${esc(__("Required"))}</em>` : "";
        const disabled = editable && block.allow_manual_override ? "" : "disabled";
        const choices = optionLines(block.options || "");
        const control = choices.length && !["Paragraph", "Manual Area", "List"].includes(block.block_type)
            ? `<select data-detail-field="${esc(block.block_key)}" ${disabled}>${choices.map((choice) => `<option value="${esc(choice)}" ${choice === value ? "selected" : ""}>${esc(choice)}</option>`).join("")}</select>`
            : ["Paragraph", "Manual Area", "List"].includes(block.block_type)
                ? `<textarea data-detail-field="${esc(block.block_key)}" ${disabled}>${esc(value)}</textarea>`
                : `<input data-detail-field="${esc(block.block_key)}" value="${esc(value)}" ${disabled}/>`;
        return `<label class="ol-quote-detail-field ${["Paragraph", "Manual Area", "List"].includes(block.block_type) ? "wide" : ""}"><span>${esc(__(block.block_label))}${required}</span>${control}${source}</label>`;
    }

    function optionLines(options) {
        return String(options || "").split("\n").map((row) => row.trim()).filter(Boolean);
    }

    function updatePreview(body, blocks) {
        const preview = body.find("[data-detail-preview]");
        if (!preview.length) return;
        const values = {};
        body.find("[data-detail-field]").each(function () { values[$(this).data("detail-field")] = $(this).val() || ""; });
        preview.html(`<div class="ol-quote-detail-preview-page">${(blocks || []).map((block) => previewBlock(block, values[block.block_key])).join("")}</div>`);
    }

    function previewBlock(block, value) {
        const cleanValue = value != null ? value : (block.value || "");
        if (block.block_type === "Page Break") return `<div class="ol-quote-preview-break"><span>${esc(__("Page Break"))}</span></div>`;
        if (block.block_type === "Heading") return `<h2>${esc(cleanValue || block.block_label)}</h2>`;
        if (block.block_type === "List") {
            const items = String(cleanValue || "").split("\n").map((row) => row.trim()).filter(Boolean);
            return `<div class="ol-quote-preview-block"><strong>${esc(block.block_label)}</strong><ul>${items.map((item) => `<li>${esc(item)}</li>`).join("")}</ul></div>`;
        }
        if (["Key Value", "Quotation Field", "Annex Field"].includes(block.block_type)) return `<div class="ol-quote-preview-kv"><b>${esc(block.block_label)} :</b><span>${esc(cleanValue)}</span></div>`;
        return `<div class="ol-quote-preview-block"><strong>${esc(block.block_label)}</strong><p>${esc(cleanValue)}</p></div>`;
    }

    function emptyMarkup(templates) {
        return `<div class="ol-quote-detail-empty"><strong>${esc(templates.length ? __("Select a template to start") : __("No active templates"))}</strong><p>${esc(templates.length ? __("The selected template will load quotation fields and matching annex values.") : __("Create an active Quotation Detail template from Document Templates first."))}</p></div>`;
    }

    async function saveSnapshot(frm, body, data, dialog) {
        const values = {};
        let missing = "";
        (data.blocks || []).forEach((block) => {
            if (block.block_type === "Page Break") return;
            const control = body.find(`[data-detail-field="${cssEscape(block.block_key)}"]`);
            const value = String(control.val() || "").trim();
            if (block.is_required && !value) missing = missing || block.block_label;
            values[block.block_key] = value;
        });
        if (missing) return frappe.msgprint({ message: __("The field {0} is required.", [missing]), indicator: "red" });

        const template = body.find("[data-quote-detail-template]").val() || data.selected_template || "";
        const res = await frappe.call({
            method: "orderlift.quotation_detail_templates.save_quotation_detail_snapshot",
            args: { quotation: frm.doc.name, template, values: JSON.stringify(values) },
            freeze: true,
            freeze_message: __("Saving commercial presentation..."),
        });
        if (res.message && res.message.snapshot) {
            frappe.show_alert({ message: __("Commercial presentation saved"), indicator: "green" });
            if (dialog) dialog.hide();
            await frm.reload_doc();
        }
    }

    function templateOptions(templates, selected) {
        return [`<option value="">${esc(__("Select template"))}</option>`, ...templates.map((row) => `<option value="${esc(row.name)}" ${row.name === selected ? "selected" : ""}>${esc(row.template_name)}${row.company ? ` - ${esc(row.company)}` : ""}</option>`)].join("");
    }

    function confirmAsync(message) {
        return new Promise((resolve) => {
            frappe.confirm(message, () => resolve(true), () => resolve(false));
        });
    }

    function cssEscape(value) {
        if (window.CSS && CSS.escape) return CSS.escape(String(value));
        return String(value).replace(/"/g, '\\"');
    }

    function esc(value) { return frappe.utils.escape_html(value == null ? "" : String(value)); }

    function injectStyles() {
        if (document.getElementById("ol-quote-detail-dialog-style")) return;
        const style = document.createElement("style");
        style.id = "ol-quote-detail-dialog-style";
        style.textContent = `.ol-quote-detail-dialog-modal .modal-dialog{max-width:min(1180px,calc(100vw - 32px));}.ol-quote-detail-dialog{display:grid;gap:12px;max-height:calc(100vh - 156px);overflow:auto}.ol-quote-detail-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;padding:14px;border:1px solid #dbe5ef;border-radius:16px;background:#f8fbff}.ol-quote-detail-head span{color:#2563eb;font-size:11px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.ol-quote-detail-head h3{margin:3px 0 0}.ol-quote-detail-head p{margin:5px 0 0;color:#64748b}.ol-quote-detail-actions{display:flex;gap:8px;align-items:end;flex-wrap:wrap}.ol-quote-detail-actions label{display:grid;gap:5px;font-size:12px;font-weight:800;color:#475569}.ol-quote-detail-actions select{min-width:260px;min-height:32px;border:1px solid #cbd5e1;border-radius:9px}.ol-quote-detail-blocks{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.ol-quote-detail-field{display:grid;gap:6px;border:1px solid #e2e8f0;border-radius:14px;background:#fff;padding:12px;font-size:12px}.ol-quote-detail-field.wide{grid-column:1/-1}.ol-quote-detail-field span{font-weight:900;color:#334155}.ol-quote-detail-field em{margin-left:6px;color:#dc2626;font-size:10px;font-style:normal}.ol-quote-detail-field small{color:#64748b}.ol-quote-detail-field input,.ol-quote-detail-field textarea,.ol-quote-detail-heading input{width:100%;border:1px solid #cbd5e1;border-radius:10px;padding:8px 10px}.ol-quote-detail-field textarea{min-height:96px}.ol-quote-detail-heading{grid-column:1/-1}.ol-quote-detail-heading input{font-size:16px;font-weight:900;color:#111827;background:#f8fafc}.ol-quote-detail-page-break{grid-column:1/-1;display:flex;align-items:center;gap:8px;color:#64748b;font-size:11px;font-weight:900;text-transform:uppercase}.ol-quote-detail-page-break:before,.ol-quote-detail-page-break:after{content:"";height:1px;background:#cbd5e1;flex:1}.ol-quote-detail-empty{text-align:center;color:#64748b;padding:32px;border:1px dashed #cbd5e1;border-radius:16px}@media(max-width:800px){.ol-quote-detail-head,.ol-quote-detail-actions{display:block}.ol-quote-detail-blocks{grid-template-columns:1fr}.ol-quote-detail-actions select{min-width:100%}}`;
        style.textContent += `.ol-quote-detail-layout{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(320px,.95fr);gap:14px;align-items:start}.ol-quote-detail-editor,.ol-quote-detail-preview{min-width:0}.ol-quote-detail-preview{position:sticky;top:0;border:1px solid #dbe5ef;border-radius:16px;background:#f8fafc;padding:12px}.ol-quote-detail-preview h4{margin:0 0 10px;color:#0f172a;font-weight:900}.ol-quote-detail-field select{width:100%;min-height:36px;border:1px solid #cbd5e1;border-radius:10px;padding:7px 10px;background:#fff}.ol-quote-detail-preview-page{border:1px solid #94a3b8;background:#fff;box-shadow:0 12px 28px rgba(15,23,42,.08);padding:14px;font-family:Arial,sans-serif;color:#1f2937;max-height:58vh;overflow:auto}.ol-quote-detail-preview-page h2{font-size:15px;text-decoration:underline;margin:12px 0 8px}.ol-quote-preview-kv{display:grid;grid-template-columns:38% 1fr;gap:8px;border-bottom:1px solid #e5e7eb;padding:5px 0;font-size:11px}.ol-quote-preview-kv span{min-height:14px;border-bottom:1px dotted #9ca3af}.ol-quote-preview-block{margin:9px 0;font-size:11px;line-height:1.45}.ol-quote-preview-block p{white-space:pre-line;margin:4px 0 0;border:1px dotted #cbd5e1;padding:6px;min-height:28px}.ol-quote-preview-block ul{margin:4px 0 0 18px;padding:0}.ol-quote-preview-break{display:flex;align-items:center;gap:8px;margin:12px 0;color:#64748b;font-size:10px;font-weight:900;text-transform:uppercase}.ol-quote-preview-break:before,.ol-quote-preview-break:after{content:"";height:1px;background:#cbd5e1;flex:1}@media(max-width:980px){.ol-quote-detail-layout{grid-template-columns:1fr}.ol-quote-detail-preview{position:static}}`;
        style.textContent += `.ol-quote-detail-inline{border:1px solid #dbe5ef;border-radius:14px;background:#fff;margin-top:8px;overflow:hidden}.ol-quote-detail-inline summary{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:11px 13px;background:#f8fafc;cursor:pointer}.ol-quote-detail-inline summary span{color:#64748b;font-size:11px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.ol-quote-detail-inline summary strong{color:#172033;font-size:13px}.ol-quote-detail-inline-card{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;padding:13px;border-top:1px solid #e2e8f0}.ol-quote-detail-inline-copy h4{margin:0 0 4px;color:#172033;font-size:15px}.ol-quote-detail-inline-copy p{margin:0;color:#64748b;font-size:12px;line-height:1.45}.ol-quote-detail-inline-stats{display:flex;gap:8px;flex-wrap:wrap;margin-top:9px}.ol-quote-detail-inline-stats span{border:1px solid #e2e8f0;border-radius:999px;background:#f8fafc;color:#475569;padding:3px 8px;font-size:11px;font-weight:800}.ol-quote-detail-inline-actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.ol-quote-detail-inline-empty{border:1px dashed #cbd5e1;border-radius:14px;background:#f8fafc;padding:14px;color:#64748b}.ol-quote-detail-inline-empty strong{display:block;color:#172033;margin-bottom:4px}@media(max-width:760px){.ol-quote-detail-inline-card{display:block}.ol-quote-detail-inline-actions{justify-content:flex-start;margin-top:12px}}`;
        document.head.appendChild(style);
    }
})();
