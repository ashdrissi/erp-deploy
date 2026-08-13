(function () {
    const TOOL_FIELD = "custom_dimensioning_tool";
    const SET_FIELD = "custom_dimensioning_set";
    const MULTIPLIER_FIELD = "custom_dimensioning_multiplier";
    const INPUTS_FIELD = "custom_dimensioning_inputs_json";

    ["Opportunity", "Quotation"].forEach((doctype) => {
        frappe.ui.form.on(doctype, {
            setup(frm) {
                frm.set_query(SET_FIELD, () => ({ filters: { is_active: 1 } }));
            },
            refresh(frm) {
                renderDimensioningDocumentTool(frm);
            },
            custom_dimensioning_set(frm) {
                frm.__orderlift_dimensioning_config = null;
                frm.__orderlift_dimensioning_complete = false;
                frm.set_value(INPUTS_FIELD, "");
                renderDimensioningDocumentTool(frm);
            },
        });
    });

    async function renderDimensioningDocumentTool(frm) {
        const field = frm.get_field(TOOL_FIELD);
        if (!field?.$wrapper) return;
        const $root = field.$wrapper.empty();
        if (!canEditDocument(frm)) {
            $root.html(panelHtml(__("Dimensioning"), __("Open an editable draft to configure and add items."), ""));
            return;
        }
        const setName = String(frm.doc[SET_FIELD] || "").trim();
        if (!setName) {
            $root.html(panelHtml(__("Dimensioning"), __("Select a Dimensioning Set to configure and add items."), ""));
            return;
        }

        if (frm.__orderlift_dimensioning_complete) {
            $root.html(panelHtml(
                __("Dimensioning complete"),
                __("Items were added. The Dimensioning helper is finished for this run."),
                `<button class="btn btn-xs btn-default" type="button" data-dimensioning-reconfigure>${__("Configure again")}</button>`
            ));
            $root.find("[data-dimensioning-reconfigure]").on("click", () => {
                frm.__orderlift_dimensioning_complete = false;
                renderDimensioningDocumentTool(frm);
            });
            return;
        }

        try {
            const config = await loadConfig(frm, setName);
            if (!config || String(frm.doc[SET_FIELD] || "") !== setName) return;
            const values = normalizedValues(config, parseInputs(frm.doc[INPUTS_FIELD]));
            $root.html(toolHtml(config, values));
            bindToolEvents(frm, $root, config);
        } catch (error) {
            $root.html(panelHtml(__("Dimensioning unavailable"), error.message || __("Unable to load this Dimensioning Set."), ""));
        }
    }

    async function loadConfig(frm, setName) {
        if (frm.__orderlift_dimensioning_config?.name === setName) return frm.__orderlift_dimensioning_config;
        const response = await frappe.call({
            method: "orderlift.orderlift_sales.doctype.dimensioning_set.dimensioning_set.get_dimensioning_set_payload",
            args: { set_name: setName },
        });
        frm.__orderlift_dimensioning_config = (response.message || {}).set || null;
        return frm.__orderlift_dimensioning_config;
    }

    function toolHtml(config, values) {
        const controls = (config.fields || []).map((field) => inputHtml(field, values[field.field_key])).join("");
        return `
            <div class="orderlift-dimensioning-document-tool">
                <div class="orderlift-dimensioning-head">
                    <div><strong>${escapeHtml(config.set_name || config.name)}</strong><span>${__("Configure items from the selected Dimensioning Set.")}</span></div>
                    <div><button class="btn btn-xs btn-default" type="button" data-dimensioning-reset>${__("Reset")}</button><button class="btn btn-xs btn-default" type="button" data-dimensioning-preview>${__("Preview")}</button><button class="btn btn-xs btn-primary" type="button" data-dimensioning-add>${__("Add Items")}</button></div>
                </div>
                <div class="orderlift-dimensioning-inputs">${controls}</div>
                <div class="orderlift-dimensioning-preview" data-dimensioning-preview-box>${__("Preview the generated items before adding them.")}</div>
            </div>
        `;
    }

    function panelHtml(title, message, action) {
        return `<div class="orderlift-dimensioning-document-tool"><div class="orderlift-dimensioning-head"><div><strong>${escapeHtml(title)}</strong><span>${escapeHtml(message)}</span></div><div>${action}</div></div></div>`;
    }

    function inputHtml(field, value) {
        const key = escapeHtml(field.field_key || "");
        const label = escapeHtml(field.label || field.field_key || "");
        if (field.field_type === "Select") {
            const options = Array.isArray(field.options) ? field.options : String(field.options || "").split("\n").filter(Boolean);
            return `<label><span>${label}</span><select data-dimensioning-input="${key}">${options.map((option) => `<option value="${escapeHtml(option)}" ${String(value ?? "") === option ? "selected" : ""}>${escapeHtml(option)}</option>`).join("")}</select></label>`;
        }
        if (field.field_type === "Check") {
            return `<label class="orderlift-dimensioning-check"><input type="checkbox" data-dimensioning-input="${key}" ${value ? "checked" : ""}><span>${label}</span></label>`;
        }
        const type = ["Int", "Float"].includes(field.field_type) ? "number" : "text";
        const step = field.field_type === "Int" ? "1" : "any";
        return `<label><span>${label}</span><input type="${type}" step="${step}" data-dimensioning-input="${key}" value="${escapeHtml(String(value ?? ""))}"></label>`;
    }

    function bindToolEvents(frm, $root, config) {
        $root.find("[data-dimensioning-input]").on("change input", function () {
            const values = collectValues($root);
            frm.set_value(INPUTS_FIELD, JSON.stringify(values));
        });
        $root.find("[data-dimensioning-reset]").on("click", async () => {
            await frm.set_value(INPUTS_FIELD, JSON.stringify(normalizedValues(config, {})));
            await frm.set_value(MULTIPLIER_FIELD, 1);
            renderDimensioningDocumentTool(frm);
        });
        $root.find("[data-dimensioning-preview]").on("click", () => previewItems(frm, $root, config));
        $root.find("[data-dimensioning-add]").on("click", async () => {
            const items = await previewItems(frm, $root, config);
            if (!items?.length) return;
            await addItems(frm, config, items);
            frm.__orderlift_dimensioning_complete = true;
            renderDimensioningDocumentTool(frm);
        });
    }

    async function previewItems(frm, $root, config) {
        const values = collectValues($root);
        const multiplier = Math.max(1, Math.trunc(Number(frm.doc[MULTIPLIER_FIELD] || 1)));
        await frm.set_value(INPUTS_FIELD, JSON.stringify(values));
        const response = await frappe.call({
            method: "orderlift.orderlift_sales.doctype.dimensioning_set.dimensioning_set.preview_dimensioning_set",
            args: { set_name: config.name, input_values_json: JSON.stringify(values), multiplier },
            freeze: true,
        });
        const items = (response.message || {}).items || [];
        const unresolved = items.filter((row) => row.missing_item || row.resolution_warning);
        const $box = $root.find("[data-dimensioning-preview-box]");
        $box.html(items.length ? items.map((row) => `<div><strong>${escapeHtml(row.item || row.rule_label || __("Unresolved item"))}</strong><span>${escapeHtml(row.item_name || row.resolution_warning || "")} x ${__("Qty")}=${escapeHtml(String(row.qty || 0))}</span></div>`).join("") : __("No items generated."));
        if (unresolved.length) {
            frappe.msgprint({ title: __("Dimensioning needs review"), message: unresolved.map((row) => escapeHtml(row.resolution_warning || row.rule_label || "")).join("<br>"), indicator: "orange" });
            return [];
        }
        return items;
    }

    async function addItems(frm, config, items) {
        const existing = (frm.doc.items || []).filter((row) => row.custom_dimensioning_set === config.name);
        if (existing.length) {
            const replace = await confirmAsync(__("Replace {0} existing item(s) generated by this Dimensioning Set?", [existing.length]));
            if (!replace) return;
            const names = new Set(existing.map((row) => row.name));
            frm.doc.items = (frm.doc.items || []).filter((row) => !names.has(row.name));
        }
        for (const item of items) {
            const row = frm.add_child("items");
            await frappe.model.set_value(row.doctype, row.name, "item_code", item.item);
            await frappe.model.set_value(row.doctype, row.name, "qty", Number(item.qty || 1));
            if (frappe.meta.has_field(row.doctype, "uom") && item.stock_uom) await frappe.model.set_value(row.doctype, row.name, "uom", item.stock_uom);
            if (frappe.meta.has_field(row.doctype, "custom_presentation_role")) row.custom_presentation_role = "Include in commercial summary";
            if (frappe.meta.has_field(row.doctype, "custom_dimensioning_set")) row.custom_dimensioning_set = config.name;
            if (frappe.meta.has_field(row.doctype, "custom_dimensioning_rule_label")) row.custom_dimensioning_rule_label = item.rule_label || "";
        }
        frm.refresh_field("items");
        frappe.show_alert({ message: __("Dimensioning items added"), indicator: "green" });
    }

    function normalizedValues(config, current) {
        const values = {};
        (config.fields || []).forEach((field) => {
            const raw = Object.prototype.hasOwnProperty.call(current, field.field_key) ? current[field.field_key] : field.default_value;
            values[field.field_key] = field.field_type === "Check" ? [1, "1", true, "true"].includes(raw) : raw ?? "";
        });
        return values;
    }

    function collectValues($root) {
        const values = {};
        $root.find("[data-dimensioning-input]").each(function () {
            values[this.dataset.dimensioningInput] = this.type === "checkbox" ? this.checked : this.value;
        });
        return values;
    }

    function parseInputs(raw) {
        try { return JSON.parse(raw || "{}"); } catch (error) { return {}; }
    }

    function confirmAsync(message) {
        return new Promise((resolve) => frappe.confirm(message, () => resolve(true), () => resolve(false)));
    }

    function canEditDocument(frm) {
        if (Number(frm.doc.docstatus || 0) !== 0) return false;
        const permissions = (frm.perm || [])[0] || {};
        return Boolean(frm.is_new() ? permissions.create : permissions.write);
    }

    function escapeHtml(value) {
        return frappe.utils.escape_html(String(value ?? ""));
    }

    if (!document.getElementById("orderlift-dimensioning-document-tool-style")) {
        const style = document.createElement("style");
        style.id = "orderlift-dimensioning-document-tool-style";
        style.textContent = `.orderlift-dimensioning-document-tool{border:1px solid var(--border-color,#d1d8dd);border-radius:12px;background:var(--fg-color,#fff);padding:12px;margin:8px 0}.orderlift-dimensioning-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.orderlift-dimensioning-head>div{display:flex;gap:8px;flex-wrap:wrap}.orderlift-dimensioning-head>div:first-child{display:grid;gap:2px}.orderlift-dimensioning-head span{color:var(--text-muted,#6b7280);font-size:12px}.orderlift-dimensioning-inputs{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;margin-top:12px}.orderlift-dimensioning-inputs label{display:grid;gap:4px}.orderlift-dimensioning-inputs label>span{font-size:11px;font-weight:700;color:var(--text-muted,#6b7280)}.orderlift-dimensioning-inputs input,.orderlift-dimensioning-inputs select{min-height:36px;border:1px solid var(--border-color,#d1d8dd);border-radius:8px;padding:0 9px;background:var(--control-bg,#fff)}.orderlift-dimensioning-check{align-content:center;grid-template-columns:auto 1fr!important}.orderlift-dimensioning-preview{display:grid;gap:5px;margin-top:12px;padding:9px;border-radius:8px;background:var(--subtle-fg,#f8fafc);font-size:12px}.orderlift-dimensioning-preview>div{display:flex;justify-content:space-between;gap:12px}@media(max-width:767px){.orderlift-dimensioning-head{align-items:stretch;flex-direction:column}}`;
        document.head.appendChild(style);
    }
})();
