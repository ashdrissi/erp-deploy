(function () {
    const DOC_TYPES = ["Opportunity", "Project", "Sales Order"];
    const STATE = {
        documentType: "Opportunity",
        data: { statuses: [], legacy_statuses: [], colors: [] },
        draft: { label: "", sequence: 100, color: "Blue", is_active: 1, is_default: 0, applies_distribution: 1, applies_installation: 1 },
        statusSearch: "",
        statusFilter: "All",
        flowFilter: "All",
    };

    frappe.pages["status-control"].on_page_load = function (wrapper) {
        const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Status Control"), single_column: true });
        wrapper.page = page;
        page.main.addClass("osc-root");
        injectStyles();
        render(page);
        load(page);
        header(page);
    };

    frappe.pages["status-control"].on_page_show = function (wrapper) {
        if (!wrapper.page) return;
        header(wrapper.page);
        load(wrapper.page);
    };

    function header(page) {
        page.set_title(__("Status Control"));
        setTimeout(() => {
            if (!frappe.breadcrumbs) return;
            frappe.breadcrumbs.clear();
            frappe.breadcrumbs.append_breadcrumb_element("/app/crm-dashboard", __("CRM"), "title-text");
            frappe.breadcrumbs.append_breadcrumb_element("", __("Status Control"), "title-text");
            frappe.breadcrumbs.toggle(true);
        }, 0);
    }

    async function load(page) {
        const res = await frappe.call({
            method: "orderlift.orderlift_crm.api.status_control.get_status_control_data",
            args: { document_type: STATE.documentType },
        });
        STATE.data = res.message || { statuses: [], legacy_statuses: [], colors: [] };
        render(page);
    }

    function render(page) {
        const data = STATE.data || {};
        const statuses = data.statuses || [];
        const filteredStatuses = currentStatuses();
        const stats = statusStats(statuses);
        page.main.html(`
            <div class="osc-shell">
                <section class="osc-topbar">
                    <div class="osc-title-block">
                        <h1>${__("Status Control")}</h1>
                        <p>${__("Edit custom pipeline statuses. ERP statuses are read-only context below.")}</p>
                    </div>
                    <div class="osc-top-meta">
                        <span>${__("Document")}: <strong>${frappe.utils.escape_html(STATE.documentType)}</strong></span>
                        <span>${__("Main Field")}: <strong>${frappe.utils.escape_html(data.field_label || "-")}</strong></span>
                        <span>${__("Statuses")}: <strong>${statuses.length}</strong></span>
                        <span>${__("Active")}: <strong>${stats.active}</strong></span>
                    </div>
                </section>

                <section class="osc-tabs">${DOC_TYPES.map((documentType) => `<button class="${documentType === STATE.documentType ? "active" : ""}" data-document-type="${frappe.utils.escape_html(documentType)}">${frappe.utils.escape_html(__(documentType))}</button>`).join("")}</section>

                <section class="osc-summary-strip">
                    ${summaryCard(__("Active"), stats.active, __("selectable values"), "green")}
                    ${summaryCard(__("Inactive"), stats.inactive, __("hidden from users"), "gray")}
                    ${summaryCard(__("Default"), stats.defaultLabel || __("Not set"), __("auto-assigned fallback"), "blue")}
                    ${summaryCard(__("Used"), stats.used, __("documents with status"), "orange")}
                </section>

                <section class="osc-grid">
                    <article class="osc-panel osc-panel--main">
                        <div class="osc-panel-head"><h2>${frappe.utils.escape_html(data.page_title || __("Statuses"))}</h2><span>${__("Dense editor for pipeline statuses")}</span></div>
                        <div class="osc-helper-note">${__("Users move cards with these statuses. ERP legacy statuses remain visible on forms and cards but are not edited here.")}</div>
                        <div class="osc-status-toolbar">
                            <input id="osc-status-search" type="search" placeholder="${__("Search status, color, or usage")}" value="${frappe.utils.escape_html(STATE.statusSearch)}" />
                            <select id="osc-status-filter">
                                ${["All", "Active", "Inactive", "Default", "Used", "Unused"].map((option) => `<option value="${option}" ${option === STATE.statusFilter ? "selected" : ""}>${frappe.utils.escape_html(__(option))}</option>`).join("")}
                            </select>
                            <select id="osc-flow-filter">
                                ${["All", "Distribution", "Installation"].map((option) => `<option value="${option}" ${option === STATE.flowFilter ? "selected" : ""}>${frappe.utils.escape_html(__(option))}</option>`).join("")}
                            </select>
                            <span class="osc-visible-count"><strong>${filteredStatuses.length}</strong> ${__("visible")}</span>
                        </div>
                        <div class="osc-status-card osc-status-card--new">
                            <div class="osc-card-head"><strong>${__("Add New Status")}</strong><span>${__("Creates a new selectable workflow value")}</span></div>
                            ${editorRow("new", STATE.draft, data.colors || ["Blue"])}
                            <div class="osc-row-actions"><button class="osc-btn-primary" data-save-new="1">${__("Add Status")}</button></div>
                        </div>
                        <div class="osc-status-list">${statusListMarkup(filteredStatuses, data.colors || ["Blue"])}</div>
                        <details class="osc-legacy-collapsible">
                            <summary><strong>${__("ERP Legacy Status")}</strong><span>${__("Read-only reference")}</span></summary>
                            <div class="osc-legacy-stack">${(data.legacy_statuses || []).map((group) => `<div class="osc-legacy-box"><strong>${frappe.utils.escape_html(group.label)}</strong><div>${(group.values || []).map((value) => `<span>${frappe.utils.escape_html(value)}</span>`).join("")}</div></div>`).join("") || `<div class="osc-empty">${__("No legacy status metadata available.")}</div>`}</div>
                        </details>
                    </article>
                </section>
            </div>
        `);
        bind(page);
    }

    function bind(page) {
        page.main.find("[data-document-type]").on("click", function () {
            STATE.documentType = $(this).data("document-type");
            STATE.draft = defaultDraft(STATE.documentType);
            STATE.statusSearch = "";
            STATE.statusFilter = "All";
            STATE.flowFilter = "All";
            load(page);
        });
        page.main.find("#osc-status-search").on("input", function () {
            STATE.statusSearch = String($(this).val() || "").trim().toLowerCase();
            updateStatusResults(page);
        });
        page.main.find("#osc-status-filter, #osc-flow-filter").on("change", function () {
            STATE.statusFilter = page.main.find("#osc-status-filter").val();
            STATE.flowFilter = page.main.find("#osc-flow-filter").val();
            updateStatusResults(page);
        });
        page.main.find("[data-save-new]").on("click", async function () {
            STATE.draft = collectRow(page.main.find("[data-row='new']"));
            await saveStatus(STATE.draft, page);
        });
        bindStatusRowActions(page);
    }

    function bindStatusRowActions(page) {
        page.main.find("[data-save-row]").on("click", async function () {
            const row = page.main.find(`.osc-status-row[data-name='${$(this).data("save-row")}']`);
            await saveStatus(collectRow(row), page);
        });
        page.main.find("[data-delete-row]").on("click", async function () {
            const name = $(this).data("delete-row");
            if (!name) return;
            frappe.confirm(
                __("Delete status {0}? This cannot be undone.", [name]),
                async () => {
                    await frappe.call({
                        method: "orderlift.orderlift_crm.api.status_control.delete_status",
                        args: { document_type: STATE.documentType, status_name: name },
                        freeze: true,
                    });
                    frappe.show_alert({ message: __("Deleted {0}", [name]), indicator: "green" });
                    load(page);
                }
            );
        });
    }

    function updateStatusResults(page) {
        const statuses = currentStatuses();
        page.main.find(".osc-status-list").html(statusListMarkup(statuses, (STATE.data || {}).colors || ["Blue"]));
        page.main.find(".osc-visible-count").html(`<strong>${statuses.length}</strong> ${__("visible")}`);
        bindStatusRowActions(page);
    }

    function currentStatuses() {
        return ((STATE.data || {}).statuses || []).filter((status) => {
            const text = `${status.label || status.name} ${status.name || ""} ${status.color || ""}`.toLowerCase();
            const matchesSearch = !STATE.statusSearch || text.includes(STATE.statusSearch);
            const matchesState = STATE.statusFilter === "All"
                || (STATE.statusFilter === "Active" && status.is_active)
                || (STATE.statusFilter === "Inactive" && !status.is_active)
                || (STATE.statusFilter === "Default" && status.is_default)
                || (STATE.statusFilter === "Used" && status.usage_count)
                || (STATE.statusFilter === "Unused" && !status.usage_count);
            const matchesFlow = STATE.flowFilter === "All"
                || (STATE.flowFilter === "Distribution" && status.applies_distribution)
                || (STATE.flowFilter === "Installation" && status.applies_installation);
            return matchesSearch && matchesState && matchesFlow;
        });
    }

    function statusStats(statuses) {
        const active = statuses.filter((status) => status.is_active).length;
        return {
            active,
            inactive: statuses.length - active,
            used: statuses.reduce((total, status) => total + Number(status.usage_count || 0), 0),
            defaultLabel: (statuses.find((status) => status.is_default) || {}).label,
        };
    }

    function summaryCard(label, value, hint, color) {
        return `
            <div class="osc-summary-card osc-summary-${color}">
                <span>${frappe.utils.escape_html(label)}</span>
                <strong>${frappe.utils.escape_html(String(value))}</strong>
                <small>${frappe.utils.escape_html(hint)}</small>
            </div>
        `;
    }

    function statusListMarkup(statuses, colors) {
        return statuses.map((status) => statusRow(status, colors)).join("") || `<div class="osc-empty">${__("No statuses match the current filters.")}</div>`;
    }

    async function saveStatus(payload, page) {
        await frappe.call({
            method: "orderlift.orderlift_crm.api.status_control.save_status",
            args: { document_type: STATE.documentType, payload },
            freeze: true,
        });
        STATE.draft = defaultDraft(STATE.documentType);
        frappe.show_alert({ message: __("Status saved"), indicator: "green" });
        load(page);
    }

    function defaultDraft(documentType) {
        return {
            label: "",
            sequence: 100,
            color: "Blue",
            is_active: 1,
            is_default: 0,
            applies_distribution: documentType === "Project" ? 0 : 1,
            applies_installation: documentType === "Sales Order" ? 0 : 1,
        };
    }

    function collectRow(row) {
        return {
            name: row.data("name") || "",
            label: row.find("[data-field='label']").val(),
            sequence: Number(row.find("[data-field='sequence']").val() || 100),
            color: row.find("[data-field='color']").val(),
            is_active: row.find("[data-field='is_active']").is(":checked") ? 1 : 0,
            is_default: row.find("[data-field='is_default']").is(":checked") ? 1 : 0,
            applies_distribution: row.find("[data-field='applies_distribution']").is(":checked") ? 1 : 0,
            applies_installation: row.find("[data-field='applies_installation']").is(":checked") ? 1 : 0,
        };
    }

    function editorRow(name, row, colors) {
        return `
            <div class="osc-status-row" data-row="${name}" data-name="${frappe.utils.escape_html(row.name || "")}">
                <label class="osc-field"><span>${__("Label")}</span><input data-field="label" type="text" placeholder="${__("Status label")}" value="${frappe.utils.escape_html(row.label || "")}" /></label>
                <label class="osc-field"><span>${__("Order")}</span><input data-field="sequence" type="number" value="${Number(row.sequence || 100)}" /></label>
                <label class="osc-field"><span>${__("Color")}</span><select data-field="color">${(colors || []).map((color) => `<option value="${frappe.utils.escape_html(color)}" ${color === row.color ? "selected" : ""}>${frappe.utils.escape_html(color)}</option>`).join("")}</select></label>
                <div class="osc-switch-group">
                    <label><input data-field="is_active" type="checkbox" ${row.is_active ? "checked" : ""} /> ${__("Active")}</label>
                    <label><input data-field="is_default" type="checkbox" ${row.is_default ? "checked" : ""} /> ${__("Default")}</label>
                    <label><input data-field="applies_distribution" type="checkbox" ${row.applies_distribution ? "checked" : ""} /> ${__("Distribution")}</label>
                    <label><input data-field="applies_installation" type="checkbox" ${row.applies_installation ? "checked" : ""} /> ${__("Installation")}</label>
                </div>
            </div>
        `;
    }

    function statusRow(status, colors) {
        return `
            <div class="osc-status-card">
                <div class="osc-card-head">
                    <strong><span class="osc-color-dot osc-color-${String(status.color || "Blue").toLowerCase()}"></span>${frappe.utils.escape_html(status.label || status.name)}</strong>
                    <span>${__("Used on {0} documents", [status.usage_count || 0])}</span>
                </div>
                ${editorRow(status.name, status, colors)}
                <div class="osc-row-footer">
                    <span>${__("Name")}: ${frappe.utils.escape_html(status.name)}</span>
                    <div class="osc-row-actions">
                        <button class="osc-btn-soft" data-save-row="${frappe.utils.escape_html(status.name)}">${__("Save")}</button>
                        <button class="osc-btn-ghost" data-delete-row="${frappe.utils.escape_html(status.name)}" ${(status.usage_count || status.is_default) ? "disabled" : ""}>${__("Delete")}</button>
                    </div>
                </div>
            </div>
        `;
    }

    function injectStyles() {
        if (document.getElementById("osc-style")) return;
        const style = document.createElement("style");
        style.id = "osc-style";
        style.textContent = `
            .osc-root { background: #f5f7fb; }
            .osc-shell { max-width: 1540px; margin: 0 auto; padding: 12px 16px 16px; display: grid; gap: 10px; }
            .osc-topbar { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 14px; align-items: center; border-radius: 14px; padding: 11px 14px; color: #111827; background: #fff; border: 1px solid #dbe4f4; box-shadow: 0 8px 22px rgba(15,23,42,.04); }
            .osc-title-block h1 { margin: 0; font-size: 20px; font-weight: 900; letter-spacing: -.025em; color: #111827; }
            .osc-title-block p { margin: 2px 0 0; color: #64748b; line-height: 1.4; font-size: 11px; max-width: 760px; font-weight: 800; }
            .osc-top-meta { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
            .osc-top-meta span { display: inline-flex; align-items: center; gap: 6px; min-height: 30px; padding: 0 10px; border-radius: 999px; background: #eff6ff; border: 1px solid #bfdbfe; color: #1d4ed8; font-size: 11px; font-weight: 900; }
            .osc-top-meta strong { color: #111827; }
            .osc-tabs { display: flex; gap: 8px; flex-wrap: wrap; }
            .osc-tabs button { min-height: 34px; border-radius: 999px; border: 1px solid #dbe4f4; background: #fff; padding: 0 13px; font-weight: 900; color: #1f3f75; cursor: pointer; }
            .osc-tabs button.active { background: #1d4ed8; color: #fff; border-color: #1d4ed8; }
            .osc-summary-strip { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 10px; }
            .osc-summary-card { min-height: 82px; border-radius: 16px; border: 1px solid #dbe4f4; background: #fff; padding: 12px; box-shadow: 0 10px 24px rgba(15,23,42,.04); }
            .osc-summary-card span { display: block; color: #64748b; font-size: 10px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
            .osc-summary-card strong { display: block; margin-top: 5px; color: #111827; font-size: 21px; line-height: 1.1; font-weight: 900; letter-spacing: -.03em; }
            .osc-summary-card small { display: block; margin-top: 3px; color: #64748b; font-size: 11px; font-weight: 800; }
            .osc-summary-green { border-color: #bbf7d0; background: #f0fdf4; }
            .osc-summary-gray { border-color: #e2e8f0; background: #f8fafc; }
            .osc-summary-blue { border-color: #bfdbfe; background: #eff6ff; }
            .osc-summary-orange { border-color: #fed7aa; background: #fff7ed; }
            .osc-grid { display: grid; grid-template-columns: 1fr; gap: 12px; }
            .osc-panel { border-radius: 18px; background: #fff; border: 1px solid #dbe4f4; padding: 14px; box-shadow: 0 12px 28px rgba(15,23,42,.05); }
            .osc-panel-head { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; margin-bottom: 10px; }
            .osc-panel-head h2 { margin: 0; font-size: 16px; font-weight: 900; color: #111827; }
            .osc-panel-head span { color: #5f708d; font-size: 11px; font-weight: 800; }
            .osc-helper-note { margin-bottom: 10px; padding: 10px 12px; border-radius: 14px; background: #f8fafc; border: 1px solid #e2e8f0; color: #475569; font-size: 11px; font-weight: 800; line-height: 1.45; }
            .osc-status-toolbar { display: grid; grid-template-columns: minmax(220px,1fr) 140px 150px auto; gap: 8px; margin-bottom: 10px; align-items: center; }
            .osc-status-toolbar input, .osc-status-toolbar select { min-height: 36px; border: 1px solid #dbe4f4; border-radius: 999px; padding: 0 12px; font-weight: 800; color: #1f3f75; background: #fff; outline: none; }
            .osc-visible-count { justify-self: end; color: #64748b; font-size: 11px; font-weight: 900; }
            .osc-visible-count strong { color: #1d4ed8; }
            .osc-status-list { display: grid; gap: 8px; }
            .osc-status-card { border: 1px solid #e5ebf7; border-radius: 14px; padding: 10px; background: #fbfdff; }
            .osc-status-card--new { margin-bottom: 10px; background: #fffdf8; border-color: #fed7aa; }
            .osc-card-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; margin-bottom: 8px; }
            .osc-card-head strong { display: inline-flex; align-items: center; gap: 7px; color: #111827; font-size: 13px; font-weight: 900; }
            .osc-card-head span { color: #64748b; font-size: 11px; font-weight: 800; }
            .osc-color-dot { width: 10px; height: 10px; border-radius: 999px; background: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,.12); }
            .osc-color-gray { background: #64748b; box-shadow: 0 0 0 3px rgba(100,116,139,.12); }
            .osc-color-blue { background: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,.12); }
            .osc-color-green { background: #16a34a; box-shadow: 0 0 0 3px rgba(22,163,74,.12); }
            .osc-color-orange { background: #ea580c; box-shadow: 0 0 0 3px rgba(234,88,12,.12); }
            .osc-color-red { background: #dc2626; box-shadow: 0 0 0 3px rgba(220,38,38,.12); }
            .osc-color-purple { background: #7c3aed; box-shadow: 0 0 0 3px rgba(124,58,237,.12); }
            .osc-status-row { display: grid; grid-template-columns: minmax(190px,1fr) 90px 130px minmax(260px, auto); gap: 8px; align-items: end; }
            .osc-field { display: grid; gap: 4px; color: #64748b; font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: .06em; }
            .osc-field input, .osc-field select { min-height: 36px; border: 1px solid #dbe4f4; border-radius: 10px; padding: 0 10px; font-weight: 800; color: #1f3f75; background: #fff; outline: none; }
            .osc-switch-group { display: flex; gap: 7px; flex-wrap: wrap; align-items: end; }
            .osc-switch-group label { display: inline-flex; align-items: center; gap: 6px; min-height: 36px; padding: 0 10px; border-radius: 10px; border: 1px solid #dbe4f4; background: #fff; font-weight: 900; color: #35507c; font-size: 11px; }
            .osc-row-footer, .osc-row-actions { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
            .osc-row-footer { margin-top: 8px; color: #5f708d; font-size: 11px; font-weight: 800; }
            .osc-btn-primary, .osc-btn-soft, .osc-btn-ghost { min-height: 34px; border-radius: 999px; padding: 0 13px; font-weight: 900; cursor: pointer; font-size: 11px; }
            .osc-btn-primary { border: 0; background: #ea580c; color: #fff; }
            .osc-btn-soft { border: 0; background: #dbeafe; color: #1d4ed8; }
            .osc-btn-ghost { border: 1px solid #dbe4f4; background: #fff; color: #1f3f75; }
            .osc-btn-ghost[disabled] { opacity: .45; cursor: not-allowed; }
            .osc-legacy-stack { display: grid; gap: 8px; }
            .osc-legacy-collapsible { margin-top: 12px; border-radius: 14px; border: 1px solid #dbe4f4; background: #f8fafc; overflow: hidden; }
            .osc-legacy-collapsible summary { display: flex; justify-content: space-between; align-items: center; gap: 10px; min-height: 42px; padding: 0 12px; cursor: pointer; color: #111827; font-weight: 900; }
            .osc-legacy-collapsible summary span { color: #64748b; font-size: 11px; font-weight: 800; }
            .osc-legacy-collapsible .osc-legacy-stack { padding: 0 12px 12px; }
            .osc-legacy-box { border-radius: 14px; background: #fbfdff; border: 1px solid #e5ebf7; padding: 10px; }
            .osc-legacy-box strong { display: block; color: #111827; margin-bottom: 7px; font-size: 12px; }
            .osc-legacy-box div { display: flex; flex-wrap: wrap; gap: 6px; }
            .osc-legacy-box span { display: inline-flex; min-height: 28px; align-items: center; border-radius: 999px; padding: 0 9px; background: #eef2ff; color: #3730a3; font-size: 10px; font-weight: 900; }
            .osc-empty { min-height: 120px; border: 1px dashed #dbe4f4; border-radius: 18px; display: flex; align-items: center; justify-content: center; color: #5f708d; font-weight: 900; }
            .osc-tabs button:focus-visible, .osc-btn-primary:focus-visible, .osc-btn-soft:focus-visible, .osc-btn-ghost:focus-visible, .osc-status-toolbar input:focus-visible, .osc-status-toolbar select:focus-visible, .osc-field input:focus-visible, .osc-field select:focus-visible { outline: 3px solid rgba(37,99,235,.24); outline-offset: 2px; }
            @media (max-width: 1240px) { .osc-topbar, .osc-grid { grid-template-columns: 1fr; } }
            @media (max-width: 900px) { .osc-status-row, .osc-status-toolbar, .osc-summary-strip { grid-template-columns: 1fr; } .osc-visible-count { justify-self: start; } .osc-row-footer, .osc-row-actions, .osc-panel-head { flex-direction: column; align-items: stretch; } }
        `;
        document.head.appendChild(style);
    }
})();
