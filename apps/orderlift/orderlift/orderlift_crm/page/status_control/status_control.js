(function () {
    const DOC_TYPES = ["Opportunity", "Project", "Sales Order", "Forecast Load Plan"];
    const DOC_TYPE_LABELS = { "Forecast Load Plan": "Shipment Plan" };
    const STATE = {
        documentType: "Opportunity",
        company: "",
        data: { statuses: [], legacy_statuses: [], colors: [], todo_priorities: [], users: [], predefined_checks: [] },
        draft: { label: "", sequence: 100, color: "Blue", assigned_user: "", todo_priority: "Important Non Urgent", auto_collapse: 0, auto_close_opportunity: 0, required_checks: [], confirmation_message: "", is_active: 1, is_default: 0, applies_distribution: 1, applies_installation: 1 },
        quickActionsDraft: [],
        statusSearch: "",
        statusFilter: "All",
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
            args: { document_type: STATE.documentType, company: STATE.company },
        });
        STATE.data = res.message || { statuses: [], legacy_statuses: [], colors: [], todo_priorities: [], users: [], predefined_checks: [] };
        STATE.company = STATE.data.selected_company || STATE.company || "";
        STATE.quickActionsDraft = [...(STATE.data.selected_quick_actions || [])];
        render(page);
    }

    function render(page) {
        const data = STATE.data || {};
        const statuses = data.statuses || [];
        const filteredStatuses = currentStatuses();
        const stats = statusStats(statuses);
        page.main.html(`
            <div class="osc-shell">
                <nav class="osc-breadcrumb"><a href="/app/main-dashboard">${__("Main Dashboard")}</a><span class="sep">/</span><span class="current">${__("Status Control")}</span></nav>
                <section class="osc-topbar">
                    <div class="osc-title-block">
                        <span class="osc-eyebrow">${__("Operations Control")}</span>
                        <h1>${__("Status Control")}</h1>
                        <p>${__("Edit custom pipeline statuses. ERP statuses are read-only context below.")}</p>
                    </div>
                    <div class="osc-top-meta">
                        <span>${__("Document")}: <strong>${frappe.utils.escape_html(documentTypeLabel(STATE.documentType))}</strong></span>
                        <span>${__("Company")}: <strong>${frappe.utils.escape_html(STATE.company || __("Select first"))}</strong></span>
                        <span>${__("Main Field")}: <strong>${frappe.utils.escape_html(data.field_label || "-")}</strong></span>
                        <span>${__("Statuses")}: <strong>${statuses.length}</strong></span>
                        <span>${__("Active")}: <strong>${stats.active}</strong></span>
                    </div>
                </section>

                <section class="osc-company-bar">
                    <label><span>${__("Company")}</span><select id="osc-company"><option value="">${frappe.utils.escape_html(__("Select company"))}</option>${companyOptions(data.companies || [], STATE.company)}</select></label>
                    <p>${__("Select a company first. Statuses below are only for that company and its users.")}</p>
                </section>

                <section class="osc-tabs">${DOC_TYPES.map((documentType) => `<button class="${documentType === STATE.documentType ? "active" : ""}" data-document-type="${frappe.utils.escape_html(documentType)}">${frappe.utils.escape_html(documentTypeLabel(documentType))}</button>`).join("")}</section>

                <section class="osc-summary-strip">
                    ${summaryCard(__("Active"), stats.active, __("selectable values"), "green")}
                    ${summaryCard(__("Inactive"), stats.inactive, __("hidden from users"), "gray")}
                    ${summaryCard(__("Default"), stats.defaultLabel || __("Not set"), __("auto-assigned fallback"), "blue")}
                    ${summaryCard(__("Used"), stats.used, __("documents with status"), "orange")}
                </section>

                ${quickActionsSection(data)}

                <section class="osc-grid">
                    <article class="osc-panel osc-panel--main">
                        <div class="osc-panel-head"><h2>${frappe.utils.escape_html(data.page_title || __("Statuses"))}</h2><span>${__("Dense editor for pipeline statuses")}</span></div>
                        <div class="osc-helper-note">${__("Users move cards with these statuses. ERP legacy statuses remain visible on forms and cards but are not edited here.")}</div>
                        <div class="osc-status-toolbar">
                            <input id="osc-status-search" type="search" placeholder="${__("Search status, color, or usage")}" value="${frappe.utils.escape_html(STATE.statusSearch)}" />
                            <select id="osc-status-filter">
                                ${["All", "Active", "Inactive", "Default", "Used", "Unused"].map((option) => `<option value="${option}" ${option === STATE.statusFilter ? "selected" : ""}>${frappe.utils.escape_html(__(option))}</option>`).join("")}
                            </select>
                            <span class="osc-visible-count"><strong>${filteredStatuses.length}</strong> ${__("visible")}</span>
                        </div>
                        ${!STATE.company ? `<div class="osc-empty">${__("Select a company before editing statuses.")}</div>` : data.allow_create === false ? "" : `<div class="osc-status-card osc-status-card--new">
                            <div class="osc-card-head"><strong>${__("Add New Status")}</strong><span>${__("Creates a new selectable workflow value")}</span></div>
                            ${editorRow("new", STATE.draft, data.colors || ["Blue"], data.users || [])}
                            <div class="osc-row-actions"><button class="osc-btn-primary" data-save-new="1">${__("Add Status")}</button></div>
                        </div>`}
                        <div class="osc-status-list">${STATE.company ? statusListMarkup(filteredStatuses, data.colors || ["Blue"]) : ""}</div>
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
        page.main.find("#osc-company").on("change", function () {
            STATE.company = String($(this).val() || "");
            STATE.draft = defaultDraft(STATE.documentType);
            setCurrentCompany(page, STATE.company);
        });
        page.main.find("[data-document-type]").on("click", function () {
            STATE.documentType = $(this).data("document-type");
            STATE.draft = defaultDraft(STATE.documentType);
            STATE.statusSearch = "";
            STATE.statusFilter = "All";
            load(page);
        });
        page.main.find("#osc-status-search").on("input", function () {
            STATE.statusSearch = String($(this).val() || "").trim().toLowerCase();
            updateStatusResults(page);
        });
        page.main.find("#osc-status-filter").on("change", function () {
            STATE.statusFilter = page.main.find("#osc-status-filter").val();
            updateStatusResults(page);
        });
        page.main.find("[data-save-new]").on("click", async function () {
            STATE.draft = collectRow(page.main.find("[data-row='new']"));
            await saveStatus(STATE.draft, page);
        });
        page.main.find("[data-quick-action]").on("change", function () {
            STATE.quickActionsDraft = page.main.find("[data-quick-action]:checked").map(function () {
                return String($(this).val() || "");
            }).get();
        });
        page.main.find("[data-save-quick-actions]").on("click", async function () {
            await saveQuickActions(page);
        });
        bindStatusRowActions(page);
    }

    function bindStatusRowActions(page) {
        page.main.find("[data-save-row]").on("click", async function () {
            const key = String($(this).data("save-row") || "");
            const row = page.main.find(".osc-status-row").filter(function () { return String($(this).data("name") || "") === key; }).first();
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
                        args: { document_type: STATE.documentType, status_name: name, company: STATE.company },
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

    function documentTypeLabel(documentType) {
        return __(DOC_TYPE_LABELS[documentType] || documentType);
    }

    function currentStatuses() {
        return ((STATE.data || {}).statuses || []).filter((status) => {
            const text = `${status.label || status.name} ${status.name || ""} ${status.color || ""} ${status.assigned_user || ""} ${status.assigned_user_label || ""} ${status.todo_priority || ""} ${status.confirmation_message || ""}`.toLowerCase();
            const matchesSearch = !STATE.statusSearch || text.includes(STATE.statusSearch);
            const matchesState = STATE.statusFilter === "All"
                || (STATE.statusFilter === "Active" && status.is_active)
                || (STATE.statusFilter === "Inactive" && !status.is_active)
                || (STATE.statusFilter === "Default" && status.is_default)
                || (STATE.statusFilter === "Used" && status.usage_count)
                || (STATE.statusFilter === "Unused" && !status.usage_count);
            return matchesSearch && matchesState;
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

    function quickActionsSection(data) {
        const actions = data.available_quick_actions || [];
        if (!STATE.company) return "";
        if (!actions.length) {
            return `<section class="osc-panel osc-panel--compact"><div class="osc-panel-head"><h2>${__("Card Quick Actions")}</h2><span>${__("No quick actions available for this document type")}</span></div></section>`;
        }
        const selected = new Set(STATE.quickActionsDraft || []);
        return `
            <section class="osc-panel osc-panel--compact">
                <div class="osc-panel-head"><h2>${__("Card Quick Actions")}</h2><span>${__("Company-wide actions for this pipeline document type")}</span></div>
                <div class="osc-helper-note">${__("These buttons appear on every pipeline card for the selected document type and company, regardless of status.")}</div>
                <div class="osc-quick-actions-grid">
                    ${actions.map((action) => `
                        <label class="osc-quick-action-card">
                            <input data-quick-action type="checkbox" value="${frappe.utils.escape_html(action.key)}" ${selected.has(action.key) ? "checked" : ""} />
                            <div>
                                <strong>${frappe.utils.escape_html(__(action.label || action.key))}</strong>
                                <small>${frappe.utils.escape_html(__(action.description || ""))}</small>
                            </div>
                        </label>
                    `).join("")}
                </div>
                <div class="osc-row-actions"><button class="osc-btn-primary" data-save-quick-actions="1">${__("Save Quick Actions")}</button></div>
            </section>
        `;
    }

    function statusListMarkup(statuses, colors) {
        return statuses.map((status) => statusRow(status, colors)).join("") || `<div class="osc-empty">${__("No statuses match the current filters.")}</div>`;
    }

    async function saveStatus(payload, page) {
        if (!STATE.company) {
            frappe.show_alert({ message: __("Select a company first"), indicator: "orange" });
            return;
        }
        payload.company = STATE.company;
        await frappe.call({
            method: "orderlift.orderlift_crm.api.status_control.save_status",
            args: { document_type: STATE.documentType, payload, company: STATE.company },
            freeze: true,
        });
        STATE.draft = defaultDraft(STATE.documentType);
        frappe.show_alert({ message: __("Status saved"), indicator: "green" });
        load(page);
    }

    async function saveQuickActions(page) {
        if (!STATE.company) {
            frappe.show_alert({ message: __("Select a company first"), indicator: "orange" });
            return;
        }
        await frappe.call({
            method: "orderlift.orderlift_crm.api.status_control.save_quick_actions",
            args: {
                document_type: STATE.documentType,
                actions: STATE.quickActionsDraft,
                company: STATE.company,
            },
            freeze: true,
        });
        frappe.show_alert({ message: __("Quick actions saved"), indicator: "green" });
        load(page);
    }

    async function setCurrentCompany(page, company) {
        if (!company) {
            load(page);
            return;
        }
        await frappe.call({
            method: "orderlift.menu_access.set_current_company",
            args: { company },
            freeze: true,
        });
        load(page);
    }

    function defaultDraft(documentType) {
        const showFlowFields = ((STATE.data || {}).show_flow_fields) !== false;
        return {
            label: "",
            sequence: 100,
            color: "Blue",
            assigned_user: "",
            todo_priority: "Important Non Urgent",
            auto_collapse: 0,
            auto_close_opportunity: 0,
            required_checks: [],
            confirmation_message: "",
            is_active: 1,
            is_default: 0,
            applies_distribution: showFlowFields ? (documentType === "Project" ? 0 : 1) : 1,
            applies_installation: showFlowFields ? (documentType === "Sales Order" ? 0 : 1) : 1,
        };
    }

    function collectRow(row) {
        const showFlowFields = ((STATE.data || {}).show_flow_fields) !== false;
        const isNewRow = String(row.data("row") || "") === "new";
        const rowName = isNewRow ? "" : (row.data("name") || "");
        const docname = isNewRow ? "" : (row.data("docname") || rowName || "");
        return {
            name: rowName,
            docname,
            label: row.find("[data-field='label']").val(),
            sequence: Number(row.find("[data-field='sequence']").val() || 100),
            color: row.find("[data-field='color']").val(),
            assigned_user: row.find("[data-field='assigned_user']").val(),
            todo_priority: row.find("[data-field='todo_priority']").val(),
            auto_collapse: row.find("[data-field='auto_collapse']").is(":checked") ? 1 : 0,
            auto_close_opportunity: row.find("[data-field='auto_close_opportunity']").is(":checked") ? 1 : 0,
            required_checks: row.find("[data-field='required_checks']:checked").map(function () { return $(this).val(); }).get(),
            confirmation_message: row.find("[data-field='confirmation_message']").val(),
            is_active: row.find("[data-field='is_active']").is(":checked") ? 1 : 0,
            is_default: row.find("[data-field='is_default']").is(":checked") ? 1 : 0,
            applies_distribution: showFlowFields ? (row.find("[data-field='applies_distribution']").is(":checked") ? 1 : 0) : 1,
            applies_installation: showFlowFields ? (row.find("[data-field='applies_installation']").is(":checked") ? 1 : 0) : 1,
        };
    }

    function editorRow(name, row, colors, users) {
        const data = STATE.data || {};
        const showFlowFields = data.show_flow_fields !== false;
        const showAutoCloseOpportunity = Boolean(data.show_auto_close_opportunity);
        const allowRename = data.allow_rename !== false || !row.name;
        return `
            <div class="osc-status-row" data-row="${name}" data-name="${frappe.utils.escape_html(name || row.name || "")}" data-docname="${frappe.utils.escape_html(row.docname || row.name || "")}">
                <label class="osc-field"><span>${__("Label")}</span><input data-field="label" type="text" placeholder="${__("Status label")}" value="${frappe.utils.escape_html(row.label || "")}" ${allowRename ? "" : "readonly"} /></label>
                <label class="osc-field"><span>${__("Order")}</span><input data-field="sequence" type="number" value="${Number(row.sequence || 100)}" /></label>
                <label class="osc-field"><span>${__("Color")}</span><select data-field="color">${(colors || []).map((color) => `<option value="${frappe.utils.escape_html(color)}" ${color === row.color ? "selected" : ""}>${frappe.utils.escape_html(color)}</option>`).join("")}</select></label>
                <label class="osc-field"><span>${__("Assigned User")}</span><select data-field="assigned_user">${userOptions(users || [], row.assigned_user || "")}</select></label>
                <label class="osc-field"><span>${__("Todo Priority")}</span><select data-field="todo_priority">${priorityOptions((STATE.data || {}).todo_priorities || [], row.todo_priority || "Important Non Urgent")}</select></label>
                <div class="osc-switch-group">
                    <label><input data-field="is_active" type="checkbox" ${row.is_active ? "checked" : ""} /> ${__("Active")}</label>
                    <label><input data-field="is_default" type="checkbox" ${row.is_default ? "checked" : ""} /> ${__("Default")}</label>
                    <label><input data-field="auto_collapse" type="checkbox" ${row.auto_collapse ? "checked" : ""} /> ${__("Collapse by default")}</label>
                    ${showAutoCloseOpportunity ? `<label><input data-field="auto_close_opportunity" type="checkbox" ${row.auto_close_opportunity ? "checked" : ""} /> ${__("Auto close Opportunity")}</label>` : ""}
                    ${showFlowFields ? `<label><input data-field="applies_distribution" type="checkbox" ${row.applies_distribution ? "checked" : ""} /> ${__("Distribution")}</label>
                    <label><input data-field="applies_installation" type="checkbox" ${row.applies_installation ? "checked" : ""} /> ${__("Installation")}</label>` : ""}
                </div>
                ${requiredChecksMarkup(row)}
                ${confirmationMessageMarkup(row)}
            </div>
        `;
    }

    function confirmationMessageMarkup(row) {
        const message = row.confirmation_message || "";
        return `
            <details class="osc-confirmation" ${message ? "open" : ""}>
                <summary><strong>${__("Move confirmation")}</strong><span>${message ? __("Configured") : __("Moves immediately")}</span></summary>
                <label class="osc-field">
                    <span>${__("Confirmation message")}</span>
                    <textarea data-field="confirmation_message" rows="3" placeholder="${frappe.utils.escape_html(__("Shown before moving a card into this status. Leave empty to move immediately."))}">${frappe.utils.escape_html(message)}</textarea>
                </label>
            </details>
        `;
    }

    function requiredChecksMarkup(row) {
        const checks = (STATE.data || {}).predefined_checks || [];
        if (!checks.length) return "";
        const selected = new Set(row.required_checks || []);
        const grouped = checks.reduce((acc, check) => {
            const group = check.group || __("Checks");
            if (!acc[group]) acc[group] = [];
            acc[group].push(check);
            return acc;
        }, {});
        return `
            <details class="osc-checklist" ${selected.size ? "open" : ""}>
                <summary><strong>${__("Required before moving here")}</strong><span>${selected.size ? __("{0} selected", [selected.size]) : __("No checks")}</span></summary>
                <div class="osc-check-groups">
                    ${Object.keys(grouped).map((group) => `
                        <div class="osc-check-group">
                            <h4>${frappe.utils.escape_html(group)}</h4>
                            <div>
                                ${grouped[group].map((check) => `
                                    <label title="${frappe.utils.escape_html(check.description || "")}">
                                        <input data-field="required_checks" type="checkbox" value="${frappe.utils.escape_html(check.key)}" ${selected.has(check.key) ? "checked" : ""} />
                                        <span>${frappe.utils.escape_html(check.label || check.key)}</span>
                                    </label>
                                `).join("")}
                            </div>
                        </div>
                    `).join("")}
                </div>
            </details>
        `;
    }

    function statusRow(status, colors) {
        const colorClass = `osc-status-card--${String(status.color || "Blue").toLowerCase()}`;
        const rowKey = status.docname || status.name;
        return `
            <div class="osc-status-card ${colorClass}">
                <div class="osc-card-head">
                    <strong><span class="osc-color-dot osc-color-${String(status.color || "Blue").toLowerCase()}"></span>${frappe.utils.escape_html(status.label || status.name)}</strong>
                    <span>${__("Used on {0} documents", [status.usage_count || 0])}${(status.required_checks || []).length ? ` · ${__("{0} checks", [(status.required_checks || []).length])}` : ""}</span>
                </div>
                ${editorRow(rowKey, status, colors, (STATE.data || {}).users || [])}
                <div class="osc-row-footer">
                    <span>${__("Name")}: ${frappe.utils.escape_html(status.label || status.name)}</span>
                    <div class="osc-row-actions">
                        <button class="osc-btn-soft" data-save-row="${frappe.utils.escape_html(rowKey)}">${__("Save")}</button>
                         <button class="osc-btn-ghost" data-delete-row="${frappe.utils.escape_html(rowKey)}" ${(status.usage_count || status.is_default || (STATE.data || {}).allow_delete === false) ? "disabled" : ""}>${__("Delete")}</button>
                    </div>
                </div>
            </div>
        `;
    }

    function companyOptions(companies, selectedCompany) {
        const options = [...(companies || [])];
        if (selectedCompany && !options.includes(selectedCompany)) {
            options.unshift(selectedCompany);
        }
        return options
            .map((company) => `<option value="${frappe.utils.escape_html(company)}" ${company === selectedCompany ? "selected" : ""}>${frappe.utils.escape_html(company)}</option>`)
            .join("");
    }

    function userOptions(users, selectedUser) {
        const selected = String(selectedUser || "");
        const hasSelected = !selected || (users || []).some((user) => user.name === selected);
        const fallback = hasSelected ? "" : `<option value="${frappe.utils.escape_html(selected)}" selected>${frappe.utils.escape_html(selected)}</option>`;
        return `
            <option value="">${frappe.utils.escape_html(__("No automatic assignment"))}</option>
            ${fallback}
            ${(users || []).map((user) => `<option value="${frappe.utils.escape_html(user.name)}" ${user.name === selected ? "selected" : ""}>${frappe.utils.escape_html(user.label || user.name)}</option>`).join("")}
        `;
    }

    function priorityOptions(priorities, selectedPriority) {
        const selected = String(selectedPriority || "Important Non Urgent");
        const options = priorities.length ? priorities : ["Important Urgent", "Important Non Urgent", "Non Important Urgent", "Non Important Non Urgent"];
        return options.map((priority) => `<option value="${frappe.utils.escape_html(priority)}" ${priority === selected ? "selected" : ""}>${frappe.utils.escape_html(priority)}</option>`).join("");
    }

    function injectStyles() {
        if (document.getElementById("osc-style")) return;
        const style = document.createElement("style");
        style.id = "osc-style";
        style.textContent = `
            @import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;450;500;600;700&family=Geist+Mono:wght@400;500&display=swap');
            .osc-root { --canvas:#FAFBFC; --canvas-2:#F4F6F8; --surface:#FFFFFF; --surface-2:#F7F8FA; --ink-1000:#0A0E1A; --ink-900:#11151F; --ink-800:#1F2433; --ink-700:#2E3548; --ink-600:#495061; --ink-500:#6B7280; --ink-400:#9099A6; --ink-300:#B8BFC9; --ink-200:#DDE1E7; --ink-150:#E8EBEF; --ink-100:#EFF1F4; --primary-700:#3730A3; --primary-600:#4F46E5; --primary-100:#E0E7FF; --primary-50:#EEF2FF; --success-700:#047857; --success-500:#10B981; --success-100:#D1FAE5; --success-50:#ECFDF5; --info-700:#0369A1; --info-100:#E0F2FE; --info-50:#F0F9FF; --rose-700:#BE123C; --rose-100:#FFE4E6; --rose-50:#FFF1F2; --accent-700:#6D28D9; --accent-600:#7C3AED; --accent-100:#EDE9FE; --accent-50:#F5F3FF; --font-sans:'Geist',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; --font-mono:'Geist Mono','SF Mono',Menlo,monospace; --r-lg:14px; --r-2xl:22px; --shadow-xs:0 1px 2px rgba(15,23,42,.04); --shadow-sm:0 1px 2px rgba(15,23,42,.04),0 2px 4px rgba(15,23,42,.04); --shadow-md:0 2px 4px rgba(15,23,42,.04),0 4px 12px rgba(15,23,42,.05); --ease:cubic-bezier(.32,.72,0,1); color:var(--ink-900); background:radial-gradient(circle at 20% 0%,rgba(99,102,241,.05) 0%,transparent 50%),radial-gradient(circle at 80% 30%,rgba(124,58,237,.03) 0%,transparent 50%),linear-gradient(to bottom,var(--canvas) 0%,var(--canvas-2) 100%); min-height:calc(100vh - 72px); overflow-x: hidden; font-family:var(--font-sans); font-feature-settings:'cv11','ss01','ss03'; -webkit-font-smoothing:antialiased; }
            .osc-root *, .osc-root *::before, .osc-root *::after { box-sizing: border-box; }
            .osc-root button, .osc-root input, .osc-root select, .osc-root textarea { font-family: inherit; }
            .osc-shell { width: 100%; max-width: 1520px; margin: 0 auto; padding: 24px 24px 96px; display: grid; gap: 18px; }
            .osc-breadcrumb { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--ink-500); font-family: var(--font-mono); }
            .osc-breadcrumb a { color: var(--ink-500); text-decoration: none; }
            .osc-breadcrumb a:hover { color: var(--ink-800); }
            .osc-breadcrumb .sep { color: var(--ink-300); }
            .osc-breadcrumb .current { color: var(--ink-800); font-weight: 500; }
            .osc-topbar { position: relative; display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 32px; align-items: center; border-radius: var(--r-2xl); padding: 28px 32px; color: var(--ink-900); background: var(--surface); border: 1px solid var(--ink-150); box-shadow: var(--shadow-md); overflow: hidden; }
            .osc-topbar::before { content: ''; position: absolute; top: 0; right: 0; width: 60%; height: 100%; background: radial-gradient(ellipse at top right,rgba(99,102,241,.06) 0%,transparent 60%); pointer-events: none; }
            .osc-topbar::after { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px; background: linear-gradient(90deg,transparent,rgba(99,102,241,.4) 30%,rgba(124,58,237,.4) 70%,transparent); }
            .osc-title-block, .osc-top-meta { position: relative; z-index: 1; }
            .osc-eyebrow { display: inline-flex; align-items: center; gap: 8px; padding: 5px 12px; background: var(--primary-50); border: 1px solid var(--primary-100); border-radius: 999px; font-size: 11px; font-weight: 500; color: var(--primary-700); margin-bottom: 14px; letter-spacing: .01em; }
            .osc-title-block h1 { margin: 0 0 8px; font-size: 28px; font-weight: 600; line-height: 1.15; letter-spacing: -.025em; color: var(--ink-1000); }
            .osc-title-block p { margin: 0; color: var(--ink-500); line-height: 1.55; font-size: 14px; max-width: 640px; font-weight: 400; }
            .osc-top-meta { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
            .osc-top-meta span { display: inline-flex; align-items: center; gap: 6px; min-height: 34px; padding: 0 12px; border-radius: 10px; background: var(--surface-2); border: 1px solid var(--ink-100); color: var(--ink-500); font-size: 11px; font-weight: 500; font-family: var(--font-mono); }
            .osc-top-meta strong { color: var(--ink-800); font-family: var(--font-sans); font-weight: 600; }
            .osc-company-bar { display: grid; grid-template-columns: minmax(260px, 380px) minmax(0, 1fr); align-items: end; gap: 14px; border: 1px solid var(--ink-150); background: var(--surface); border-radius: var(--r-lg); padding: 14px; box-shadow: var(--shadow-sm); }
            .osc-company-bar label { display: grid; gap: 6px; color: var(--ink-500); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; }
            .osc-company-bar select { min-height: 40px; border: 1px solid var(--ink-200); border-radius: 12px; padding: 0 12px; color: var(--ink-900); background: #fff; font-weight: 700; }
            .osc-company-bar p { margin: 0; color: var(--ink-600); font-size: 13px; line-height: 1.45; }
            .osc-tabs { display: flex; gap: 8px; flex-wrap: wrap; }
            .osc-tabs button { min-height: 38px; border-radius: 10px; border: 1px solid var(--ink-200); background: var(--surface); padding: 0 14px; font-weight: 500; color: var(--ink-700); cursor: pointer; transition: all .2s var(--ease); }
            .osc-tabs button:hover { background: var(--surface-2); color: var(--ink-900); }
            .osc-tabs button.active { background: var(--ink-1000); color: #fff; border-color: var(--ink-1000); box-shadow: var(--shadow-sm); }
            .osc-summary-strip { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 10px; }
            .osc-summary-card { position: relative; min-height: 96px; border-radius: var(--r-lg); border: 1px solid var(--ink-150); background: var(--surface); padding: 16px; box-shadow: var(--shadow-sm); overflow: hidden; }
            .osc-summary-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: var(--ink-400); }
            .osc-summary-card span { display: block; color: var(--ink-500); font-size: 11px; font-weight: 500; letter-spacing: .01em; }
            .osc-summary-card strong { display: block; margin-top: 8px; color: var(--ink-1000); font-size: 24px; line-height: 1.1; font-weight: 600; letter-spacing: -.025em; }
            .osc-summary-card small { display: block; margin-top: 5px; color: var(--ink-500); font-size: 12px; font-weight: 400; }
            .osc-summary-green::before { background: var(--success-500); }
            .osc-summary-gray::before { background: var(--ink-400); }
            .osc-summary-blue::before { background: var(--primary-600); }
            .osc-summary-orange::before { background: var(--accent-600); }
            .osc-grid { display: grid; grid-template-columns: 1fr; gap: 12px; }
            .osc-panel { min-width: 0; border-radius: var(--r-2xl); background: var(--surface); border: 1px solid var(--ink-150); padding: 18px; box-shadow: var(--shadow-md); }
            .osc-panel-head { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; margin-bottom: 10px; }
            .osc-panel-head h2 { margin: 0; font-size: 16px; font-weight: 600; color: var(--ink-1000); letter-spacing: -.015em; }
            .osc-panel-head span { color: var(--ink-500); font-size: 12px; font-weight: 500; }
            .osc-helper-note { margin-bottom: 10px; padding: 10px 12px; border-radius: 14px; background: var(--surface-2); border: 1px solid var(--ink-100); color: var(--ink-600); font-size: 12px; font-weight: 400; line-height: 1.5; }
            .osc-status-toolbar { display: grid; grid-template-columns: minmax(220px,1fr) 140px 150px auto; gap: 8px; margin-bottom: 10px; align-items: center; }
            .osc-status-toolbar input, .osc-status-toolbar select { min-height: 36px; border: 1px solid #dbe4f4; border-radius: 999px; padding: 0 12px; font-weight: 800; color: #1f3f75; background: #fff; outline: none; }
            .osc-visible-count { justify-self: end; color: #64748b; font-size: 11px; font-weight: 900; }
            .osc-visible-count strong { color: #1d4ed8; }
            .osc-panel--compact { padding: 16px 18px; }
            .osc-quick-actions-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 10px; }
            .osc-quick-action-card { display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: 10px; align-items: start; min-height: 74px; padding: 12px; border-radius: 14px; border: 1px solid #dbe4f4; background: #fff; cursor: pointer; }
            .osc-quick-action-card input { margin-top: 4px; }
            .osc-quick-action-card strong { display: block; color: #111827; font-size: 13px; font-weight: 900; }
            .osc-quick-action-card small { display: block; margin-top: 4px; color: #64748b; font-size: 11px; line-height: 1.45; }
            .osc-status-list { display: grid; gap: 8px; }
            .osc-status-card { min-width: 0; overflow: hidden; border: 1px solid #e5ebf7; border-radius: 14px; padding: 10px; background: #fbfdff; }
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
            .osc-status-row { min-width: 0; display: grid; grid-template-columns: minmax(0,1.25fr) minmax(72px,.45fr) minmax(96px,.6fr) minmax(0,1fr) minmax(0,1fr) minmax(0,1.2fr); gap: 8px; align-items: end; }
            .osc-field { display: grid; gap: 4px; color: #64748b; font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: .06em; }
            .osc-field, .osc-field input, .osc-field select, .osc-field textarea { min-width: 0; }
            .osc-field input, .osc-field select { min-height: 36px; border: 1px solid #dbe4f4; border-radius: 10px; padding: 0 10px; font-weight: 800; color: #1f3f75; background: #fff; outline: none; }
            .osc-field textarea { min-height: 76px; border: 1px solid #dbe4f4; border-radius: 12px; padding: 9px 10px; font-weight: 800; color: #1f3f75; background: #fff; outline: none; resize: vertical; text-transform: none; letter-spacing: 0; }
            .osc-switch-group { display: flex; gap: 7px; flex-wrap: wrap; align-items: end; }
            .osc-switch-group label { display: inline-flex; align-items: center; gap: 6px; min-height: 36px; padding: 0 10px; border-radius: 10px; border: 1px solid #dbe4f4; background: #fff; font-weight: 900; color: #35507c; font-size: 11px; }
            .osc-checklist { grid-column: 1 / -1; border-radius: 13px; border: 1px solid #dbe4f4; background: #fff; overflow: hidden; }
            .osc-confirmation { grid-column: 1 / -1; border-radius: 13px; border: 1px solid #dbe4f4; background: #fff; overflow: hidden; }
            .osc-confirmation summary { min-height: 36px; display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 0 11px; cursor: pointer; color: #111827; font-size: 11px; font-weight: 900; }
            .osc-confirmation summary span { color: #64748b; font-size: 10px; }
            .osc-confirmation .osc-field { padding: 9px; border-top: 1px solid #e5ebf7; background: #f8fafc; }
            .osc-checklist summary { min-height: 36px; display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 0 11px; cursor: pointer; color: #111827; font-size: 11px; font-weight: 900; }
            .osc-checklist summary span { color: #64748b; font-size: 10px; }
            .osc-check-groups { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; padding: 9px; border-top: 1px solid #e5ebf7; background: #f8fafc; }
            .osc-check-group { display: grid; gap: 6px; min-width: 0; }
            .osc-check-group h4 { margin: 0; color: #1f3f75; font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: .07em; }
            .osc-check-group div { display: grid; gap: 5px; }
            .osc-check-group label { min-width: 0; display: flex; align-items: center; gap: 7px; min-height: 30px; padding: 5px 7px; border: 1px solid #e5ebf7; border-radius: 10px; background: #fff; color: #35507c; font-size: 10.5px; font-weight: 850; text-transform: none; letter-spacing: 0; }
            .osc-check-group label span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
            .osc-row-footer, .osc-row-actions { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
            .osc-row-footer { margin-top: 8px; color: #5f708d; font-size: 11px; font-weight: 800; }
            .osc-btn-primary, .osc-btn-soft, .osc-btn-ghost { min-height: 34px; border-radius: 10px; padding: 0 13px; font-weight: 500; cursor: pointer; font-size: 12px; transition: all .2s var(--ease); }
            .osc-btn-primary { border: 0; background: var(--ink-1000); color: #fff; box-shadow: var(--shadow-sm); }
            .osc-btn-primary:hover { background: var(--ink-800); transform: translateY(-1px); }
            .osc-btn-soft { border: 0; background: var(--primary-50); color: var(--primary-700); }
            .osc-btn-ghost { border: 1px solid var(--ink-200); background: var(--surface); color: var(--ink-700); }
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
            .osc-tabs button:focus-visible, .osc-btn-primary:focus-visible, .osc-btn-soft:focus-visible, .osc-btn-ghost:focus-visible, .osc-status-toolbar input:focus-visible, .osc-status-toolbar select:focus-visible, .osc-field input:focus-visible, .osc-field select:focus-visible, .osc-field textarea:focus-visible { outline: 3px solid rgba(99,102,241,.15); outline-offset: 2px; }
            @media (max-width: 1240px) { .osc-topbar, .osc-grid { grid-template-columns: 1fr; } }
            @media (max-width: 900px) { .osc-shell { padding: 20px 16px 96px; } .osc-topbar { padding: 22px; } .osc-company-bar, .osc-status-row, .osc-status-toolbar, .osc-summary-strip, .osc-check-groups { grid-template-columns: 1fr; } .osc-visible-count { justify-self: start; } .osc-row-footer, .osc-row-actions, .osc-panel-head { flex-direction: column; align-items: stretch; } }
        `;
        document.head.appendChild(style);
    }
})();
