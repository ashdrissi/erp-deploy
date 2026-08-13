(function () {
    const STORAGE_FIELD = "custom_orderlift_capabilities";
    const PICKER_FIELD = "custom_orderlift_capabilities_picker";
    let capabilityOptionsPromise;

    frappe.ui.form.on("Role", {
        setup(frm) {
            hideStorageField(frm);
        },
        refresh(frm) {
            hideStorageField(frm);
            renderCapabilityPicker(frm);
        },
    });

    function hideStorageField(frm) {
        if (frm.fields_dict[STORAGE_FIELD]) frm.set_df_property(STORAGE_FIELD, "hidden", 1);
    }

    async function renderCapabilityPicker(frm) {
        const field = frm.fields_dict[PICKER_FIELD];
        if (!field) return;
        const $wrapper = field.$wrapper;
        $wrapper.html(`<div class="ol-role-capability-loading">${__("Loading capabilities...")}</div>`);

        try {
            const options = await getCapabilityOptions();
            const selected = new Set(parseCapabilities(frm.doc[STORAGE_FIELD]));
            const canWrite = Boolean((frm.perm || []).some((permission) => permission.write || permission.create));
            $wrapper.html(`
                <div class="ol-role-capability-picker">
                    <div class="ol-role-capability-heading">
                        <div>
                            <strong>${__("Orderlift Capabilities")}</strong>
                            <span>${__("Select the application privileges granted by this role. They are grouped by business responsibility.")}</span>
                        </div>
                        <em>${__("{0} selected", [selected.size])}</em>
                    </div>
                    ${renderCapabilityGroups(options, selected, canWrite)}
                </div>
            `);
            bindPicker(frm, $wrapper);
            injectStyles();
        } catch (error) {
            console.error("Orderlift Role capability picker failed", error);
            $wrapper.html(`<div class="text-muted">${__("Could not load Orderlift capabilities.")}</div>`);
        }
    }

    function getCapabilityOptions() {
        if (!capabilityOptionsPromise) {
            capabilityOptionsPromise = frappe.call({
                method: "orderlift.role_capabilities.get_capability_options",
            }).then((response) => response.message || []);
        }
        return capabilityOptionsPromise;
    }

    function renderCapabilityGroups(options, selected, canWrite) {
        const groups = [];
        const seen = new Set();
        (options || []).forEach((option) => {
            const groupKey = option.group || "other";
            if (!seen.has(groupKey)) {
                seen.add(groupKey);
                groups.push({ key: groupKey, label: option.group_label || groupKey, options: [] });
            }
            groups.find((group) => group.key === groupKey).options.push(option);
        });
        return `<div class="ol-role-capability-groups">${groups.map((group) => `
            <section class="ol-role-capability-group">
                <h4>${escapeHtml(__(group.label))}</h4>
                <div class="ol-role-capability-options">
                    ${group.options.map((option) => renderOption(option, selected, canWrite)).join("")}
                </div>
            </section>
        `).join("")}</div>`;
    }

    function renderOption(option, selected, canWrite) {
        const value = String(option.value || "");
        const checked = selected.has(value) ? "checked" : "";
        const disabled = canWrite ? "" : "disabled";
        return `
            <label class="ol-role-capability-option">
                <input type="checkbox" data-orderlift-capability="${escapeAttr(value)}" ${checked} ${disabled}>
                <span><strong>${escapeHtml(option.label || value)}</strong><small>${escapeHtml(option.description || value)}</small></span>
            </label>
        `;
    }

    function bindPicker(frm, $wrapper) {
        $wrapper.off("change.orderlift-capabilities").on(
            "change.orderlift-capabilities",
            "[data-orderlift-capability]",
            function () {
                const values = $wrapper.find("[data-orderlift-capability]:checked")
                    .map((index, input) => input.dataset.orderliftCapability)
                    .get();
                frm.set_value(STORAGE_FIELD, values.join("\n"));
                $wrapper.find(".ol-role-capability-heading em").text(__("{0} selected", [values.length]));
            }
        );
    }

    function parseCapabilities(value) {
        return String(value || "").replace(/,/g, "\n").split("\n").map((entry) => entry.trim()).filter(Boolean);
    }

    function escapeHtml(value) {
        return frappe.utils.escape_html(String(value == null ? "" : value));
    }

    function escapeAttr(value) {
        return escapeHtml(value).replace(/"/g, "&quot;");
    }

    function injectStyles() {
        if (document.getElementById("ol-role-capability-picker-styles")) return;
        $("<style id='ol-role-capability-picker-styles'>").text(`
            .ol-role-capability-picker{margin:4px 0 18px;padding:16px;border:1px solid var(--border-color);border-radius:12px;background:var(--fg-color)}
            .ol-role-capability-heading{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:12px}.ol-role-capability-heading strong{display:block;color:var(--text-color);font-size:14px}.ol-role-capability-heading span{display:block;margin-top:3px;color:var(--text-muted);font-size:12px}.ol-role-capability-heading em{padding:4px 8px;border-radius:999px;background:var(--control-bg);color:var(--text-muted);font-size:11px;font-style:normal;white-space:nowrap}
            .ol-role-capability-groups{display:grid;gap:12px}.ol-role-capability-group{padding:10px;border:1px solid var(--border-color);border-radius:10px;background:var(--control-bg)}.ol-role-capability-group h4{margin:0 0 8px;color:var(--text-color);font-size:12px;font-weight:600}.ol-role-capability-options{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.ol-role-capability-option{display:flex;gap:10px;align-items:flex-start;margin:0;padding:11px;border:1px solid var(--border-color);border-radius:9px;background:var(--fg-color);cursor:pointer}.ol-role-capability-option:has(input:checked){border-color:var(--primary);background:var(--blue-50)}.ol-role-capability-option input{margin-top:3px}.ol-role-capability-option span strong{display:block;color:var(--text-color);font-size:12px}.ol-role-capability-option span small{display:block;margin-top:2px;color:var(--text-muted);font-size:11px;line-height:1.35}@media(max-width:700px){.ol-role-capability-options{grid-template-columns:1fr}}
        `).appendTo("head");
    }
})();
