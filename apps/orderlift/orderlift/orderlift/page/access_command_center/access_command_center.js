(function () {
    const METHOD = "orderlift.orderlift.page.access_command_center.access_command_center";
    const BASE_PERMISSION_ROLE = "All";
    const PERMISSION_FIELDS = ["select", "read", "write", "create", "delete", "submit", "cancel", "amend", "report", "import", "export", "print", "email", "share"];
    const TABS = [
        ["users", "Users"],
        ["roles", "Roles"],
        ["policy", "How Access Works"],
        ["menu", "Menu Access"],
        ["matrix", "Permissions Matrix"],
        ["reports", "Report Access"],
        ["audit", "Audit Log"],
    ];
    let matrixSearchTimer = null;
    let reportSearchTimer = null;
    const STATE = {
        activeTab: "users",
        search: "",
        userFilter: "all",
        doctypeSearch: "",
        reportSearch: "",
        matrixSearchInput: "",
        matrixSearchPending: false,
        selectedRole: "System Manager",
        selectedUser: "",
        selectedUserDetail: null,
        data: null,
        matrixDraft: {},
        matrixDraftRole: "",
        matrixView: "grouped",
        matrixExpandedGroups: {},
        reportExpandedGroups: {},
        selectedReports: {},
        hiddenUserColumns: [],
        loading: false,
    };

    frappe.pages["access-command-center"].on_page_load = function (wrapper) {
        const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Access Command Center"), single_column: true });
        wrapper.page = page;
        page.main.addClass("acc-root");
        injectStyles();
        renderLoading(page);
        load(page);
    };

    frappe.pages["access-command-center"].on_page_show = function (wrapper) {
        if (wrapper.page && !STATE.data) load(wrapper.page);
    };

    async function load(page) {
        STATE.loading = true;
        try {
            const res = await frappe.call({
                method: `${METHOD}.get_access_command_center_data`,
                args: { search: STATE.search, selected_role: STATE.selectedRole, report_search: STATE.reportSearch },
            });
            STATE.data = res.message || {};
            STATE.selectedRole = STATE.data.selected_role || STATE.selectedRole;
            const users = STATE.data.users || [];
            if (STATE.selectedUser && !users.some((user) => user.name === STATE.selectedUser)) {
                STATE.selectedUser = users[0]?.name || "";
                STATE.selectedUserDetail = null;
            }
            if (!STATE.selectedUser && users.length) STATE.selectedUser = users[0].name;
            if (STATE.selectedUser) await loadUserDetail(STATE.selectedUser, false);
            render(page);
        } catch (error) {
            renderError(page, error);
        } finally {
            STATE.loading = false;
        }
    }

    async function loadUserDetail(userName, shouldRender, page) {
        if (!userName) return;
        STATE.selectedUser = userName;
        try {
            const res = await frappe.call({ method: `${METHOD}.get_user_detail`, args: { user_name: userName } });
            STATE.selectedUserDetail = res.message || null;
            if (shouldRender && page) render(page);
        } catch (error) {
            frappe.msgprint({ title: __("User Detail Failed"), message: error.message || __("Could not load user."), indicator: "red" });
        }
    }

    function renderLoading(page) {
        page.main.html(`
            <div class="acc-shell">
                <section class="acc-hero acc-skeleton-panel"><div class="acc-shimmer h-lg"></div><div class="acc-shimmer h-sm"></div></section>
                <section class="acc-kpis">${Array.from({ length: 8 }, () => `<div class="acc-kpi acc-shimmer-card"></div>`).join("")}</section>
                <section class="acc-workspace acc-skeleton-panel"><div class="acc-shimmer h-xl"></div></section>
            </div>
        `);
    }

    function renderError(page, error) {
        page.main.html(`
            <div class="acc-shell">
                <div class="acc-error-state">
                    <div class="acc-error-icon">${ICONS.shield}</div>
                    <h2>${__("Access Command Center could not load")}</h2>
                    <p>${escapeHtml(error.message || __("Check your permissions or try again."))}</p>
                    <button class="acc-btn acc-btn-primary" data-retry>${__("Retry")}</button>
                </div>
            </div>
        `);
        page.main.find("[data-retry]").on("click", () => load(page));
    }

    function render(page) {
        const data = STATE.data || {};
        const showUserDetailPanel = STATE.activeTab === "users";
        page.set_title(__("Access Command Center"));
        page.main.html(`
            <div class="acc-shell">
                <nav class="acc-breadcrumb" aria-label="${__("Breadcrumb")}">
                    <a href="/desk/home-page?sidebar=Main+Dashboard">${__("Settings")}</a>
                    <span class="sep">/</span>
                    <a href="/desk/home-page?sidebar=Main+Dashboard">${__("Administration")}</a>
                    <span class="sep">/</span>
                    <span class="current">${__("Access Command Center")}</span>
                </nav>
                ${heroMarkup(data)}
                ${kpiMarkup(data.summary || {})}
                ${tabsMarkup()}
                <section class="acc-workspace ${showUserDetailPanel ? "acc-workspace-users" : "acc-workspace-focus"}">
                    <main class="acc-center-panel" role="main">
                        ${centerMarkup(data)}
                    </main>
                    ${showUserDetailPanel ? `<aside class="acc-detail-panel">${detailPanelMarkup(data)}</aside>` : ""}
                </section>
            </div>
        `);
        bind(page);
        updateStickySaveBar(page);
    }

    function heroMarkup(data) {
        return `
            <section class="acc-hero">
                <div class="acc-hero-copy">
                    <div class="acc-eyebrow"><span>${ICONS.shield}</span>${__("Admin Control Panel")}</div>
                    <h1>${__("Access Command Center")}</h1>
                    <p>${__("Manage ERP users, business roles, menu access, company access, and role permissions from one secure control cockpit.")}</p>
                    <div class="acc-hero-meta">
                        <span class="acc-status-dot safe"></span><strong>${__("Security status")}</strong><span>${__("Protected server-side checks active")}</span>
                        <span class="acc-meta-divider"></span><strong>${__("Last permission sync")}</strong><span>${formatDate(data.last_sync)}</span>
                    </div>
                </div>
                <div class="acc-hero-actions">
                    <label class="acc-global-search">
                        <span>${ICONS.search}</span>
                        <input type="search" data-global-search placeholder="${__("Search users, roles, pages, reports")}" value="${escapeHtml(STATE.search)}" aria-label="${__("Search access records")}" />
                    </label>
                    <div class="acc-action-row">
                        <button class="acc-btn acc-btn-secondary" data-export>${ICONS.download}${__("Export")}</button>
                        <button class="acc-btn acc-btn-primary" data-new-user>${ICONS.plus}${__("Invite User")}</button>
                    </div>
                </div>
            </section>
        `;
    }

    function kpiMarkup(summary) {
        const cards = [
            ["total_users", "Total Users", "All ERP identities", "blue", ICONS.users],
            ["active_users", "Active Users", "Can access the ERP", "green", ICONS.check],
            ["disabled_users", "Disabled Users", "Blocked from login", "gray", ICONS.lock],
            ["custom_roles", "Business Roles", "Managed access roles", "violet", ICONS.spark],
            ["admin_users", "Admin Access", "High-access users", "amber", ICONS.warning],
            ["pending_reviews", "Pending Reviews", "Queued access review", "blue", ICONS.review],
            ["recent_permission_changes", "Permission Changes", "Recent tracked updates", "red", ICONS.activity],
        ];
        return `<section class="acc-kpis">${cards.map(([key, label, helper, color, icon]) => `
            <article class="acc-kpi acc-kpi-${color}" tabindex="0">
                <div class="acc-kpi-icon">${icon}</div>
                <div><span>${escapeHtml(__(label))}</span><strong>${formatNumber(summary[key] || 0)}</strong><small>${escapeHtml(__(helper))}</small></div>
            </article>
        `).join("")}</section>`;
    }

    function tabsMarkup() {
        return `<nav class="acc-tabs" aria-label="${__("Access command sections")}">${TABS.map(([key, label]) => `
            <button class="${STATE.activeTab === key ? "active" : ""}" data-tab="${key}" aria-selected="${STATE.activeTab === key ? "true" : "false"}">${escapeHtml(__(label))}</button>
        `).join("")}</nav>`;
    }

    function centerMarkup(data) {
        if (STATE.activeTab === "users") return usersTableMarkup(data);
        if (STATE.activeTab === "roles") return rolesMarkup(data.roles || [], __("All Roles"), true);
        if (STATE.activeTab === "policy") return policyMarkup();
        if (STATE.activeTab === "menu") return menuAccessMarkup(data);
        if (STATE.activeTab === "matrix") return matrixMarkup(data);
        if (STATE.activeTab === "reports") return reportsAccessManagerMarkup(data);
        if (STATE.activeTab === "audit") return auditMarkup(data.audit_log || []);
        return usersTableMarkup(data.users || []);
    }

    function usersTableMarkup(data) {
        const allUsers = data.users || [];
        const users = filterUsers(allUsers, STATE.userFilter);
        return panelShell(__("User Management"), __("Search, review, and update ERP identities with role-aware safety checks."), `
            <div class="acc-user-control-strip">
                <div class="acc-smart-filter-block">
                    <div class="acc-strip-label"><span>${ICONS.filter}</span>${__("Smart Filters")}</div>
                    <div class="acc-filter-chip-row" role="group" aria-label="${__("Filter users")}">
                        ${userFilterChip("all", __("All"), allUsers.length)}
                        ${userFilterChip("enabled", __("Active"), allUsers.filter((user) => user.enabled).length)}
                        ${userFilterChip("disabled", __("Disabled"), allUsers.filter((user) => !user.enabled).length)}
                        ${userFilterChip("admin", __("Admin"), allUsers.filter((user) => ["Admin Level", "High Access"].includes(user.access_level)).length)}
                    </div>
                </div>
                ${roleCategorySummaryMarkup(data.roles || [])}
            </div>
            <div class="acc-table-toolbar">
                <span class="acc-count-pill"><strong>${users.length}</strong> ${__("visible users")}${users.length !== allUsers.length ? ` <span>${__("of")} ${allUsers.length}</span>` : ""}</span>
                <button class="acc-btn acc-btn-secondary" data-bulk-roles>${__("Bulk Role Assignment")}</button>
                <button class="acc-btn acc-btn-ghost" data-column-note>${__("Columns")}</button>
            </div>
            <div class="acc-table-wrap">
                <table class="acc-table">
                    <thead><tr><th><input type="checkbox" data-select-all-users aria-label="${__("Select all users")}" /></th><th>${__("User")}</th><th class="${userColumnHidden("status")}">${__("Status")}</th><th class="${userColumnHidden("type")}">${__("Type")}</th><th class="${userColumnHidden("main_role")}">${__("Main Role")}</th><th class="${userColumnHidden("roles")}">${__("Roles")}</th><th class="${userColumnHidden("last_login")}">${__("Last Login")}</th><th class="${userColumnHidden("access")}">${__("Access")}</th><th>${__("Actions")}</th></tr></thead>
                    <tbody>${users.map(userRow).join("") || tableEmpty(__("No users found"), __("Try another search or create a new user."))}</tbody>
                </table>
            </div>
        `);
    }

    function userFilterChip(key, label, count) {
        return `<button class="acc-filter-chip ${STATE.userFilter === key ? "active" : ""}" data-filter-users="${key}" aria-pressed="${STATE.userFilter === key ? "true" : "false"}"><span>${escapeHtml(label)}</span><strong>${formatNumber(count)}</strong></button>`;
    }

    function filterUsers(users, filter) {
        if (filter === "enabled") return users.filter((user) => user.enabled);
        if (filter === "disabled") return users.filter((user) => !user.enabled);
        if (filter === "admin") return users.filter((user) => ["Admin Level", "High Access"].includes(user.access_level));
        return users;
    }

    function roleCategorySummaryMarkup(roles) {
        const categories = [
            [__("System"), roles.filter((role) => role.is_system).length, ""],
            [__("Custom"), roles.filter((role) => role.is_custom).length, ""],
            [__("High Access"), roles.filter((role) => role.access_level !== "Managed Access").length, "danger"],
        ];
        return `<div class="acc-role-category-strip" aria-label="${__("Role Categories")}">
            <div class="acc-strip-label"><span>${ICONS.role}</span>${__("Roles")}</div>
            <div class="acc-role-category-row">${categories.map(([label, count, tone]) => `<div class="acc-role-category ${tone}"><strong>${formatNumber(count)}</strong><span>${escapeHtml(label)}</span></div>`).join("")}</div>
        </div>`;
    }

    function rolesMarkup(roles, title, allowCreate) {
        return panelShell(title, __("Review protected system roles, editable custom roles, assigned users, and risk classification."), `
            <div class="acc-table-toolbar">
                <span class="acc-count-pill"><strong>${roles.length}</strong> ${__("visible roles")}</span>
                ${allowCreate ? `<button class="acc-btn acc-btn-primary" data-new-role>${ICONS.plus}${__("New Custom Role")}</button>` : `<button class="acc-btn acc-btn-secondary" data-new-role>${ICONS.plus}${__("Create Custom Role")}</button>`}
            </div>
            <div class="acc-card-grid">${roles.map(roleCard).join("") || emptyState(__("No roles found"), __("No roles match the current search."), ICONS.role)}</div>
        `);
    }

    function menuAccessMarkup(data) {
        const roles = availableRoles();
        const selectedRole = STATE.selectedRole || (roles[0] && roles[0].name) || "";
        const grouped = groupBySection(data.menu_access || []);
        const selectedCount = (data.menu_access || []).filter((item) => menuItemSelectedForRole(item, selectedRole)).length;
        return panelShell(__("Menu Access"), __("Control which Main Dashboard sections and links each role can see. Platform admin roles still bypass menu restrictions."), `
            <div class="acc-matrix-toolbar">
                <label><span>${__("Role")}</span><select data-menu-role-selector>${roles.map((role) => `<option value="${escapeHtml(role.name)}" ${role.name === selectedRole ? "selected" : ""}>${escapeHtml(role.name)}</option>`).join("")}</select></label>
                <span class="acc-count-pill"><strong>${selectedCount}</strong> ${__("visible menu items")}</span>
                <button class="acc-btn acc-btn-primary" data-save-menu-access>${__("Save Menu Access")}</button>
            </div>
            <div class="acc-menu-grid">
                ${Object.keys(grouped).map((section) => menuSectionMarkup(section, grouped[section], selectedRole)).join("") || emptyState(__("No menu rules"), __("Run migration or refresh menu rules."), ICONS.role)}
            </div>
        `);
    }

    function menuSectionMarkup(section, items, selectedRole) {
        return `<article class="acc-access-card acc-menu-section-card">
            <h3>${escapeHtml(section)}</h3>
            <p>${items.length} ${__("managed links")}</p>
            <div class="acc-role-toggle-list acc-menu-toggle-list">
                ${items.map((item) => {
                    const checked = menuItemSelectedForRole(item, selectedRole);
                    const helper = [item.link_type, item.link_to || item.url].filter(Boolean).join(" · ");
                    return `<label class="acc-role-toggle ${checked ? "selected" : ""}"><input type="checkbox" data-menu-key="${escapeHtml(item.key)}" ${checked ? "checked" : ""} /><span><strong>${escapeHtml(item.label)}</strong><small>${escapeHtml(helper)}</small></span>${item.enabled ? "" : badge(__("Disabled"), "gray")}</label>`;
                }).join("")}
            </div>
        </article>`;
    }

    function policyMarkup() {
        const gateCards = [
            [__("1"), __("Role says yes"), __("The role must allow this document and action."), __("Example: no Quotation permission means no linked Quotations.")],
            [__("2"), __("Company matches"), __("The record must belong to an allowed company."), __("No selected company means no company documents.")],
            [__("3"), __("Business type matches"), __("Distribution / Installation narrows records inside the company."), __("Blank business type stays visible.")],
            [__("4"), __("Special scope matches"), __("Warehouse and price-list rules apply where relevant."), __("Stock uses warehouses. Catalogue uses allowed price lists.")],
            [__("5"), __("Concerned link exists"), __("If concerned-only is on, the user must be business owner, assigned, responsible, or linked through an allowed source document."), __("Opportunity uses opportunity_owner; Customer uses account manager, Sales Team, assignments, or visible Opportunities.")],
        ];
        const chains = [
            [__("Sales"), __("Opportunity -> Quotation -> Sales Order -> Sales Invoice / Delivery Note")],
            [__("Purchasing"), __("Sales Order / Project -> Material Request -> Purchase Order -> Purchase Receipt / Purchase Invoice")],
            [__("Campaigns"), __("Campaign owner, assigned campaign target, or target linked to a visible Lead, Prospect, Customer, Opportunity, Quotation, or Sales Order")],
            [__("SAV"), __("Assigned technician or linked Customer, Sales Order, Delivery Note, Sales Invoice, Purchase Receipt, or Project")],
            [__("Pricing"), __("Pricing Sheet owner, sales person, linked Opportunity, or visible Lead / Prospect / Customer")],
        ];
        const examples = [
            [__("Agent commissions"), __("A sales agent sees only commissions for their own Sales Person. Managers can see broader team data.")],
            [__("Items in catalogue"), __("A restricted static agent sees an item only when that item has a price in one of the selected allowed selling price lists.")],
            [__("Price lists"), __("Price List and Item Price rows are limited to allowed selling, buying, or benchmark lists.")],
            [__("Purchase orders"), __("A purchase user with concerned-only access sees owned, assigned, or linked Purchase Orders. A sales user still needs Purchase Order permission first.")],
            [__("SAV tickets"), __("A ticket is visible if it is assigned to the user or connected to a document the user is allowed to see.")],
            [__("Customer records"), __("A visible sale does not reveal the Customer unless the role also grants Customer access.")],
            [__("Pipeline assignments"), __("Assignments use Orderlift ToDos and linked-document policy, not native DocShare or if_owner.")],
        ];
        const hiddenReasons = [
            __("The role does not allow this document type or action."),
            __("The record belongs to another company."),
            __("The record has a business type outside the user's scope."),
            __("The user is not business owner, assigned, responsible, or connected through an allowed source document."),
            __("The record uses a warehouse or price list outside the user's special scope."),
            __("The record is related to another document, but the role lacks permission for this related document type."),
        ];
        return panelShell(__("How Access Works"), __("A plain-language guide for why a user can or cannot see business records."), `
            <div class="acc-policy-grid">
                <article class="acc-policy-card acc-policy-hero-card">
                    <span class="acc-policy-kicker">${__("Fast Rule")}</span>
                    <h3>${__("No role, no record. No link, no record.")}</h3>
                    <p>${__("Access is a chain of yes/no gates. The user must pass role, company, business type, special scope, and concerned-document checks. Related records never bypass role permission.")}</p>
                </article>
                <article class="acc-policy-card">
                    <h3>${__("Can This User See It?")}</h3>
                    <div class="acc-policy-steps">
                        ${gateCards.map(([step, title, text, example]) => `<div class="acc-policy-step"><strong>${escapeHtml(step)}</strong><span><b>${escapeHtml(title)}</b><small>${escapeHtml(text)}</small><em>${escapeHtml(example)}</em></span></div>`).join("")}
                    </div>
                </article>
                <article class="acc-policy-card">
                    <h3>${__("Document Chains")}</h3>
                    <div class="acc-policy-examples">
                        ${chains.map(([title, text]) => `<div><b>${escapeHtml(title)}</b><small>${escapeHtml(text)}</small></div>`).join("")}
                    </div>
                </article>
                <article class="acc-policy-card">
                    <h3>${__("Real Examples")}</h3>
                    <div class="acc-policy-examples">
                        ${examples.map(([title, text]) => `<div><b>${escapeHtml(title)}</b><small>${escapeHtml(text)}</small></div>`).join("")}
                    </div>
                </article>
                <article class="acc-policy-card acc-policy-wide">
                    <h3>${__("Why Is It Hidden?")}</h3>
                    <div class="acc-policy-checklist">
                        ${hiddenReasons.map((reason) => `<span>${ICONS.lock}${escapeHtml(reason)}</span>`).join("")}
                    </div>
                </article>
                <article class="acc-policy-card acc-policy-wide acc-policy-cheat-card">
                    <h3>${__("Admin Controls")}</h3>
                    <div class="acc-policy-cheats">
                        <span><b>${__("Menu Access")}</b><small>${__("Controls what links appear in Main Dashboard.")}</small></span>
                        <span><b>${__("Permissions Matrix")}</b><small>${__("Controls what records and actions each role can use.")}</small></span>
                        <span><b>${__("User Panel")}</b><small>${__("Controls roles, companies, warehouses, business types, and concerned-only mode.")}</small></span>
                        <span><b>${__("Agent Pricing Rules")}</b><small>${__("Controls allocated selling, buying, and benchmark price lists.")}</small></span>
                    </div>
                </article>
                <article class="acc-policy-card acc-policy-wide acc-policy-cheat-card">
                    <h3>${__("Capabilities")}</h3>
                    <p>${__("Capabilities are role-level flags that override specific pricing and access gates. They are currently in shadow mode — legacy hardcoded role checks remain authoritative until the site flag <code>orderlift_use_role_capabilities</code> is enabled.")}</p>
                    <div class="acc-policy-cheats">
                        <span><b>${__("Privileged Pricing")}</b><small>${__("See all active-company price lists without agent allocation caps. Access item cost and margin data.")}</small></span>
                        <span><b>${__("Quotation Override")}</b><small>${__("Set any price or discount on quotations and pricing sheets. Bypass max-discount caps, floor-price validation, and auto-repricing.")}</small></span>
                        <span><b>${__("Purchasing Access")}</b><small>${__("View buying price lists and supplier cost data. Gated behind purchase roles.")}</small></span>
                    </div>
                </article>
            </div>
        `);
    }

    function matrixMarkup(data) {
        const matrix = data.permission_matrix || { rows: [] };
        const roles = permissionMatrixRoles();
        const selectedRoleLabel = selectedPermissionRoleLabel();
        const dirtyCount = Object.keys(STATE.matrixDraft).length;
        const allRows = functionalMatrixRows(matrix.rows || []);
        const displayRows = filteredMatrixRows(allRows, STATE.doctypeSearch);
        const groups = groupedMatrixRows(displayRows);
        const searchValue = STATE.matrixSearchInput || STATE.doctypeSearch;
        const searchActive = Boolean(normalizeMatrixSearch(STATE.doctypeSearch).length);
        const autoExpandGroups = searchActive && displayRows.length <= 80 && groups.length <= 6;
        const bodyMarkup = STATE.matrixView === "technical"
            ? displayRows.map((row) => matrixRow(row)).join("")
            : groups.map((group) => matrixGroup(group, autoExpandGroups)).join("");
        return panelShell(__("Permissions Matrix"), __("Control read, edit, create, remove, approval, import, export, and sharing access through safe Custom DocPerm overrides."), `
            ${generalPermissionSummary(allRows)}
            <div class="acc-matrix-toolbar">
                <label><span>${__("Permission Scope")}</span><select data-role-selector>${roles.map((role) => `<option value="${escapeHtml(role.name)}" ${role.name === STATE.selectedRole ? "selected" : ""}>${escapeHtml(role.label || role.name)}</option>`).join("")}</select></label>
                <label><span>${__("Search groups, modules, doctypes")}</span><input data-doctype-search type="search" value="${escapeHtml(searchValue)}" placeholder="${__("Item, Catalog, Child Table, high...")}" /></label>
                ${searchActive ? `<button class="acc-row-action" data-clear-doctype-search>${__("Clear Search")}</button>` : ""}
                <label><span>${__("View")}</span><select data-matrix-view><option value="grouped" ${STATE.matrixView !== "technical" ? "selected" : ""}>${__("Business Groups")}</option><option value="technical" ${STATE.matrixView === "technical" ? "selected" : ""}>${__("Technical DocTypes")}</option></select></label>
                <span class="acc-matrix-search-status ${STATE.matrixSearchPending ? "active" : ""}" data-matrix-search-status>${STATE.matrixSearchPending ? `<b></b>${__("Searching")}` : ""}</span>
                <span class="acc-source-legend"><b class="custom"></b>${__("Role")} <b class="standard"></b>${__("Base")} <b class="none"></b>${__("No access")}</span>
                <span class="acc-count-pill">${__("Editing")} <strong>${escapeHtml(selectedRoleLabel)}</strong></span>
                <span class="acc-count-pill"><strong>${displayRows.length}</strong>${searchActive ? `/${allRows.length}` : ""} ${__("doctypes")} · <strong>${groups.length}</strong> ${__("groups")}</span>
            </div>
            <div class="acc-matrix-wrap">
                <table class="acc-matrix">
                    <thead><tr><th class="sticky-col">${__("DocType")}</th><th>${__("Level")}</th><th>${__("Source")}</th><th>${__("Risk")}</th>${PERMISSION_FIELDS.map((field) => `<th>${labelPermission(field)}</th>`).join("")}<th>${__("Action")}</th></tr></thead>
                    <tbody>${bodyMarkup || tableEmpty(__("No permissions found"), __("Try another role or search."))}</tbody>
                </table>
            </div>
            <div class="acc-page-report-grid">
                ${pageAccessMarkup(data.page_access || [])}
                ${reportAccessMarkup(data.report_access || [])}
            </div>
            ${dirtyCount ? `<div class="acc-inline-warning">${ICONS.warning}<span>${__("You have unsaved matrix changes. Use Review Changes before saving.")}</span></div>` : ""}
        `);
    }

    function generalPermissionSummary(rows) {
        const generalRows = (rows || []).filter((row) => row.group_key === "general_permissions");
        const activeGeneral = generalRows.filter((row) => rowHasPermission(row)).length;
        return `
            <div class="acc-inline-warning">
                ${ICONS.shield}
                <span><strong>${__("General Permissions")}</strong> ${__("are common permissions shown inside the selected role. Checking boxes here saves access for the selected role only.")}</span>
                <span class="acc-count-pill"><strong>${activeGeneral}</strong>/<strong>${generalRows.length}</strong> ${__("active in selected role")}</span>
            </div>
        `;
    }

    function filteredMatrixRows(rows, search) {
        const tokens = normalizeMatrixSearch(search);
        if (!tokens.length) return rows || [];
        const groupMatches = new Set();
        (rows || []).forEach((row) => {
            const groupText = matrixGroupSearchText(row);
            if (tokens.every((token) => groupText.includes(token))) groupMatches.add(row.group_key || `module:${row.module || "Unassigned"}`);
        });
        return (rows || []).filter((row) => {
            const groupKey = row.group_key || `module:${row.module || "Unassigned"}`;
            if (groupMatches.has(groupKey)) return true;
            const rowText = matrixSearchText(row);
            return tokens.every((token) => rowText.includes(token));
        });
    }

    function normalizeMatrixSearch(search) {
        return String(search || "").toLowerCase().trim().split(/\s+/).filter(Boolean);
    }

    function matrixSearchText(row) {
        return [
            row.doctype,
            row.module,
            row.group_label,
            row.group_key,
            row.group_relation,
            row.group_parent_doctype,
            row.source,
            row.source_label,
            row.source_role,
            row.group_key === "general_permissions" ? "general permissions common role" : "",
            row.risk,
            Number(row.is_child_table || 0) ? "child table child" : "primary parent",
            Number(row.is_custom_doctype || 0) ? "custom doctype" : "standard doctype",
        ].filter(Boolean).join(" ").toLowerCase();
    }

    function matrixGroupSearchText(row) {
        return [row.module, row.group_label, row.group_key].filter(Boolean).join(" ").toLowerCase();
    }

    function groupedMatrixRows(rows) {
        const groups = new Map();
        (rows || []).forEach((row) => {
            const key = row.group_key || `module:${row.module || "Unassigned"}`;
            if (!groups.has(key)) {
                groups.set(key, {
                    key,
                    label: row.group_label || row.module || __("Unassigned"),
                    order: Number(row.group_order ?? 1000),
                    module: row.module || "",
                    rows: [],
                });
            }
            groups.get(key).rows.push(row);
        });
        return Array.from(groups.values()).sort((a, b) => {
            if (a.order !== b.order) return a.order - b.order;
            return String(a.label).localeCompare(String(b.label));
        });
    }

    function matrixGroup(group, autoExpand) {
        const expanded = Boolean(STATE.matrixExpandedGroups[group.key]) || Boolean(autoExpand);
        const activeCount = group.rows.filter(rowHasPermission).length;
        const childCount = group.rows.filter((row) => Number(row.is_child_table || 0)).length;
        const customCount = group.rows.filter((row) => row.can_reset || STATE.matrixDraft[row.row_key || `${row.doctype}::${row.permlevel || 0}`]).length;
        const risk = groupRisk(group.rows);
        return `
            <tr class="acc-matrix-group-row risk-${risk}" data-matrix-group="${escapeHtml(group.key)}">
                <td class="sticky-col">
                    <button class="acc-group-toggle" data-toggle-matrix-group="${escapeHtml(group.key)}" aria-expanded="${expanded ? "true" : "false"}"><span>${expanded ? "-" : "+"}</span><strong>${escapeHtml(group.label)}</strong></button>
                    <small>${activeCount}/${group.rows.length} ${__("active")} · ${childCount} ${__("child tables")} · ${customCount} ${__("custom/draft")}</small>
                </td>
                <td>${badge(String(group.rows.length), "gray")}</td>
                <td>${groupSourceBadge(group.rows)}</td>
                <td>${badge(risk, risk === "critical" ? "red" : risk === "high" ? "amber" : risk === "medium" ? "blue" : "gray")}</td>
                ${PERMISSION_FIELDS.map((field) => groupPermissionToggle(group, field)).join("")}
                <td><button class="acc-row-action" data-toggle-matrix-group="${escapeHtml(group.key)}">${expanded ? __("Collapse") : __("Expand")}</button></td>
            </tr>
            ${expanded ? group.rows.map((row) => matrixRow(row, true)).join("") : ""}
        `;
    }

    function groupPermissionToggle(group, field) {
        const state = groupPermissionState(group.rows, field);
        const title = state.disabled ? __("Disabled for this group") : __("Apply {0} to all visible DocTypes in this group", [labelPermission(field)]);
        return `<td><label class="acc-perm-toggle acc-group-perm-toggle ${state.disabled ? "disabled" : ""}" title="${escapeHtml(title)}"><input type="checkbox" data-group-permission-field="${field}" data-group-key="${escapeHtml(group.key)}" ${state.checked ? "checked" : ""} data-mixed="${state.mixed ? 1 : 0}" ${state.disabled ? "disabled" : ""} /><span></span></label></td>`;
    }

    function groupPermissionState(rows, field) {
        const editable = (rows || []).filter((row) => !(row.disabled_permission_fields || []).includes(field) && !isInheritedBaseField(row, field));
        if (!editable.length) return { checked: false, mixed: false, disabled: true };
        const checkedCount = editable.filter((row) => Number(rowPermissionValues(row)[field] || 0)).length;
        return { checked: checkedCount === editable.length, mixed: checkedCount > 0 && checkedCount < editable.length, disabled: false };
    }

    function rowPermissionValues(row) {
        const rowKey = row.row_key || `${row.doctype}::${row.permlevel || 0}`;
        return STATE.matrixDraft[rowKey] || row.effective || {};
    }

    function groupRisk(rows) {
        const rank = { critical: 0, high: 1, medium: 2, low: 3 };
        return (rows || []).reduce((current, row) => (rank[row.risk] < rank[current] ? row.risk : current), "low");
    }

    function groupSourceBadge(rows) {
        if ((rows || []).some((row) => row.source === "mixed")) return sourceBadge("mixed");
        if ((rows || []).some((row) => row.source === "direct")) return sourceBadge("direct");
        if ((rows || []).some((row) => row.source === "base")) return sourceBadge("base");
        return sourceBadge("none");
    }

    function functionalMatrixRows(rows) {
        const byDoctype = new Map();
        (rows || []).forEach((row) => {
            if (!row.doctype) return;
            const existing = byDoctype.get(row.doctype);
            if (!existing || matrixRowRank(row) < matrixRowRank(existing)) byDoctype.set(row.doctype, row);
        });
        return Array.from(byDoctype.values());
    }

    function matrixRowRank(row) {
        const sourceRank = { mixed: 0, direct: 1, base: 2, none: 3 }[row.source] ?? 4;
        const activeRank = hasEffectivePermission(row) ? 0 : 1;
        return sourceRank * 100 + activeRank * 10 + Number(row.permlevel || 0);
    }

    function hasEffectivePermission(row) {
        const effective = row.effective || {};
        return PERMISSION_FIELDS.some((field) => Number(effective[field] || 0));
    }

    function rowHasPermission(row) {
        const values = rowPermissionValues(row);
        return PERMISSION_FIELDS.some((field) => Number(values[field] || 0));
    }

    function menuItemSelectedForRole(item, role) {
        if (!item || !role || !item.enabled) return false;
        const allowedRoles = item.allowed_roles || [];
        const deniedRoles = item.denied_roles || [];
        if (deniedRoles.includes(role)) return false;
        return allowedRoles.includes(role) || allowedRoles.includes("All");
    }

    function detailPanelMarkup(data) {
        const user = STATE.selectedUserDetail;
        const roles = availableRoles();
        const companies = data.companies || [];
        if (!user) return emptyState(__("No user selected"), __("Select a user to review details, roles, permissions, and warnings."), ICONS.users);
        const assigned = new Set(user.roles || []);
        const assignedCompanies = new Set(user.allowed_companies || []);
        const warehouses = data.warehouses || [];
        const assignedWarehouses = new Set(user.allowed_warehouses || []);
        const businessTypes = data.business_types || [];
        const assignedBusinessTypes = new Set(user.allowed_business_types || []);
        const scopedBusinessTypes = businessTypesForCompanies(data, assignedCompanies);
        const scopedWarehouses = warehousesForCompanies(warehouses, assignedCompanies);
        return `
            <div class="acc-detail-head">
                <div class="acc-avatar">${initials(user.full_name || user.email)}</div>
                <div><h2>${escapeHtml(user.full_name || user.name)}</h2><p>${escapeHtml(user.email || user.name)}</p></div>
            </div>
            <div class="acc-detail-status-row">
                ${badge(user.enabled ? __("Active") : __("Disabled"), user.enabled ? "green" : "gray")}
                ${badge(user.user_type || __("User"), "blue")}
                ${badge(user.access_level || __("Managed Access"), user.access_level === "Admin Level" ? "red" : user.access_level === "High Access" ? "amber" : "blue")}
            </div>
            ${(user.warnings || []).map((warning) => `<div class="acc-warning-card">${ICONS.warning}<span>${escapeHtml(warning)}</span></div>`).join("")}
            <div class="acc-detail-section">
                <h3>${__("User Details")}</h3>
                <label class="acc-field"><span>${__("Full Name")}</span><input data-user-field="full_name" value="${escapeHtml(user.full_name || "")}" /></label>
                <label class="acc-field"><span>${__("User Type")}</span><select data-user-field="user_type"><option ${user.user_type === "System User" ? "selected" : ""}>System User</option><option ${user.user_type === "Website User" ? "selected" : ""}>Website User</option></select></label>
                <label class="acc-toggle-line"><input data-user-field="enabled" type="checkbox" ${user.enabled ? "checked" : ""} /> ${__("User is enabled")}</label>
                <label class="acc-toggle-line"><input data-user-field="custom_owned_documents_only" type="checkbox" ${user.custom_owned_documents_only ? "checked" : ""} /> ${__("Owned / assigned CRM documents only")}</label>
                <button class="acc-btn acc-btn-primary full" data-save-user>${__("Save User Details")}</button>
                <button class="acc-btn acc-btn-danger full" data-delete-user>${__("Delete User")}</button>
            </div>
            <div class="acc-detail-section">
                <h3>${__("Assigned Roles")}</h3>
                <div class="acc-role-toggle-list">${roles.map((role) => `<label class="acc-role-toggle ${assigned.has(role.name) ? "selected" : ""}"><input type="checkbox" data-user-role="${escapeHtml(role.name)}" ${assigned.has(role.name) ? "checked" : ""} /><span>${escapeHtml(role.name)}</span>${role.is_protected ? badge(__("Protected"), "gray") : ""}</label>`).join("")}</div>
                <button class="acc-btn acc-btn-secondary full" data-save-user-roles>${__("Review and Save Roles")}</button>
            </div>
            <div class="acc-detail-section">
                <h3>${__("Company Access")}</h3>
                <div class="acc-role-toggle-list acc-company-toggle-list">${companies.map((company) => companyAccessRow(company, assignedCompanies, user.default_company)).join("") || `<div class="acc-empty-inline">${__("No companies found.")}</div>`}</div>
                <button class="acc-btn acc-btn-secondary full" data-save-user-companies>${__("Save Company Access")}</button>
            </div>
            <div class="acc-detail-section">
                <h3>${__("Warehouse Access")}</h3>
                <p class="acc-section-hint">${__("Warehouses are filtered by selected companies. Leave all unchecked for company-level warehouse access.")}</p>
                <div class="acc-role-toggle-list acc-warehouse-toggle-list">${scopedWarehouses.map((warehouse) => warehouseAccessRow(warehouse, assignedWarehouses)).join("") || `<div class="acc-empty-inline">${__("Select company access first to choose warehouses.")}</div>`}</div>
                <button class="acc-btn acc-btn-secondary full" data-save-user-warehouses>${__("Save Warehouse Access")}</button>
            </div>
            <div class="acc-detail-section">
                <h3>${__("Business Type Access")}</h3>
                <p class="acc-section-hint">${__("Business types are filtered by selected companies, so Distribution users cannot receive Installation-only access.")}</p>
                <div class="acc-role-toggle-list acc-business-type-toggle-list">${scopedBusinessTypes.map((businessType) => businessTypeAccessRow(businessType, assignedBusinessTypes)).join("") || `<div class="acc-empty-inline">${__("Select company access first to choose business types.")}</div>`}</div>
                <button class="acc-btn acc-btn-secondary full" data-save-user-business-types>${__("Save Business Type Access")}</button>
            </div>
        `;
    }

    function selectedCompanySet(page) {
        const root = page && page.main ? page.main : $(document);
        const checked = root.find("[data-user-company]:checked").map(function () { return $(this).data("user-company"); }).get();
        if (checked.length) return new Set(checked);
        return new Set((STATE.selectedUserDetail || {}).allowed_companies || []);
    }

    function refreshCompanyScopedAccessOptions(page) {
        if (!STATE.selectedUserDetail || !STATE.data) return;
        const companySet = selectedCompanySet(page);
        const currentWarehouses = new Set(page.main.find("[data-user-warehouse]:checked").map(function () { return $(this).data("user-warehouse"); }).get());
        const currentBusinessTypes = new Set(page.main.find("[data-user-business-type]:checked").map(function () { return $(this).data("user-business-type"); }).get());
        const warehouses = warehousesForCompanies(STATE.data.warehouses || [], companySet);
        const businessTypes = businessTypesForCompanies(STATE.data, companySet);
        page.main.find(".acc-warehouse-toggle-list").html(
            warehouses.map((warehouse) => warehouseAccessRow(warehouse, currentWarehouses)).join("") || `<div class="acc-empty-inline">${__("Select company access first to choose warehouses.")}</div>`
        );
        page.main.find(".acc-business-type-toggle-list").html(
            businessTypes.map((businessType) => businessTypeAccessRow(businessType, currentBusinessTypes)).join("") || `<div class="acc-empty-inline">${__("Select company access first to choose business types.")}</div>`
        );
    }

    function businessTypesForCompanies(data, companySet) {
        const companies = data.companies || [];
        const selected = companySet || new Set();
        const values = [];
        companies.forEach((company) => {
            if (!selected.has(company.name)) return;
            (company.business_types || []).forEach((businessType) => {
                if (businessType && !values.includes(businessType)) values.push(businessType);
            });
        });
        return values.sort();
    }

    function warehousesForCompanies(warehouses, companySet) {
        const selected = companySet || new Set();
        return (warehouses || []).filter((warehouse) => selected.has(warehouse.company));
    }

    function businessTypeAccessRow(businessType, assignedBusinessTypes) {
        const isAssigned = assignedBusinessTypes.has(businessType);
        return `<label class="acc-role-toggle ${isAssigned ? "selected" : ""}"><input type="checkbox" data-user-business-type="${escapeHtml(businessType)}" ${isAssigned ? "checked" : ""} /><span>${escapeHtml(businessType)}</span></label>`;
    }

    function warehouseAccessRow(warehouse, assignedWarehouses) {
        const name = warehouse.name || "";
        const isAssigned = assignedWarehouses.has(name);
        const label = warehouse.warehouse_name && warehouse.warehouse_name !== name ? `${warehouse.warehouse_name} (${name})` : name;
        return `<label class="acc-role-toggle ${isAssigned ? "selected" : ""}"><input type="checkbox" data-user-warehouse="${escapeHtml(name)}" data-user-warehouse-company="${escapeHtml(warehouse.company || "")}" ${isAssigned ? "checked" : ""} /><span>${escapeHtml(label)}</span><small>${escapeHtml(warehouse.company || "")}</small></label>`;
    }

    function auditMarkup(rows) {
        return panelShell(__("Audit Log"), __("Review business-scope Access Command Center changes."), `
            <div class="acc-audit-list">${rows.map((row) => `
                <article class="acc-audit-item risk-${row.risk || "medium"}">
                    <div class="acc-audit-dot"></div>
                    <div><strong>${escapeHtml(row.summary || __("Access record changed"))}</strong><p>${escapeHtml(row.target_type)}: ${escapeHtml(row.target)} · ${__("by")} ${escapeHtml(row.actor)}</p><small>${formatDate(row.modified)}</small></div>
                    <span class="acc-badge ${row.risk === "high" ? "danger" : "warning"}">${escapeHtml(row.risk || "medium")}</span>
                </article>
            `).join("") || emptyState(__("No audit activity"), __("Business access changes will appear here after updates."), ICONS.activity)}</div>
        `);
    }

    function panelShell(title, subtitle, content) {
        return `<section class="acc-panel"><div class="acc-panel-head"><div><h2>${escapeHtml(title)}</h2><p>${escapeHtml(subtitle)}</p></div><button class="acc-icon-btn" data-refresh aria-label="${__("Refresh")}">${ICONS.refresh}</button></div>${content}</section>`;
    }

    function userRow(user) {
        return `<tr class="${user.name === STATE.selectedUser ? "selected" : ""}" data-user-row="${escapeHtml(user.name)}"><td><input type="checkbox" data-select-user="${escapeHtml(user.name)}" aria-label="${__("Select user")}" /></td><td><div class="acc-user-cell"><span class="acc-avatar small">${initials(user.full_name || user.name)}</span><div><strong>${escapeHtml(user.full_name || user.name)}</strong><small>${escapeHtml(user.email || user.name)}</small></div></div></td><td class="${userColumnHidden("status")}">${badge(user.enabled ? __("Active") : __("Disabled"), user.enabled ? "green" : "gray")}</td><td class="${userColumnHidden("type")}">${escapeHtml(user.user_type || "-")}</td><td class="${userColumnHidden("main_role")}">${roleChip(user.main_role)}</td><td class="${userColumnHidden("roles")}"><strong>${user.role_count || 0}</strong></td><td class="${userColumnHidden("last_login")}">${formatDate(user.last_login)}</td><td class="${userColumnHidden("access")}">${badge(user.access_level || __("Managed"), accessBadgeColor(user.access_level))}</td><td><button class="acc-row-action" data-view-user="${escapeHtml(user.name)}">${__("Details")}</button></td></tr>`;
    }

    function miniUser(user) {
        return `<button class="acc-mini-user ${user.name === STATE.selectedUser ? "active" : ""}" data-view-user="${escapeHtml(user.name)}"><span class="acc-avatar tiny">${initials(user.full_name || user.name)}</span><span><strong>${escapeHtml(user.full_name || user.name)}</strong><small>${escapeHtml(user.main_role || user.user_type || "")}</small></span></button>`;
    }

    function companyAccessRow(company, assignedCompanies, defaultCompany) {
        const isAssigned = assignedCompanies.has(company.name);
        const isDefault = company.name === defaultCompany;
        const businessTypes = (company.business_types || []).map((type) => `<span>${escapeHtml(type)}</span>`).join("") || `<span>${__("No business types")}</span>`;
        return `<div class="acc-company-row ${isDefault ? "is-default" : ""}"><label class="acc-role-toggle ${isAssigned ? "selected" : ""}"><input type="checkbox" data-user-company="${escapeHtml(company.name)}" ${isAssigned ? "checked" : ""} /><span>${escapeHtml(company.name)}</span><small class="acc-company-business-types">${businessTypes}</small></label><button type="button" class="acc-default-company-btn ${isDefault ? "active" : ""}" data-make-default-company="${escapeHtml(company.name)}">${isDefault ? __("Default") : __("Make Default")}</button></div>`;
    }

    function roleCard(role) {
        const customActions = role.is_protected
            ? `<a class="acc-text-link" href="/app/role/${encodeURIComponent(role.name)}">${__("Open Role form")}</a>`
            : `<div class="acc-role-actions"><button class="acc-btn acc-btn-secondary" data-edit-role="${escapeHtml(role.name)}">${__("Edit")}</button><button class="acc-btn acc-btn-danger" data-delete-role="${escapeHtml(role.name)}" ${role.users ? "disabled" : ""}>${__("Delete")}</button></div>`;
        const capabilityLabels = roleCapabilityLabels(role.capabilities || []);
        return `<article class="acc-role-card ${role.access_level === "Admin Level" ? "critical" : role.access_level === "High Access" ? "elevated" : ""}"><div class="acc-card-top"><div class="acc-card-icon">${ICONS.role}</div><div class="acc-role-badges">${badge(role.is_system ? __("System") : __("Custom"), role.is_system ? "blue" : "violet")}${role.is_protected ? badge(__("Protected"), "gray") : badge(__("Editable"), "green")}</div></div><h3>${escapeHtml(role.name)}</h3><p>${role.access_level === "Admin Level" ? __("Administrator-level role. Changes require review.") : role.access_level === "High Access" ? __("High access role with elevated permissions.") : __("Managed business access role.")}</p><div class="acc-role-capability-row">${capabilityLabels.map((label) => badge(label, "blue")).join("") || badge(__("No app capabilities"), "gray")}</div><div class="acc-card-metrics"><span><strong>${role.users || 0}</strong>${__("users")}</span><span><strong>${role.disabled ? __("Off") : __("On")}</strong>${__("status")}</span></div><div class="acc-role-card-actions"><button class="acc-btn acc-btn-secondary full" data-tab-jump="matrix" data-role-jump="${escapeHtml(role.name)}">${__("Open Matrix")}</button>${customActions}</div></article>`;
    }

    function matrixRow(row, isGroupedChild) {
        const rowKey = row.row_key || `${row.doctype}::${row.permlevel || 0}`;
        const draft = rowPermissionValues(row);
        const disabledFields = new Set(row.disabled_permission_fields || []);
        return `<tr class="risk-${row.risk} ${STATE.matrixDraft[rowKey] ? "draft" : ""} ${isGroupedChild ? "acc-matrix-child-row" : ""}" data-matrix-row="${escapeHtml(rowKey)}" data-doctype="${escapeHtml(row.doctype)}" data-permlevel="${row.permlevel || 0}"><td class="sticky-col"><div class="acc-doctype-cell"><strong>${escapeHtml(row.doctype)}</strong><small>${escapeHtml(row.module || "")} ${row.group_relation ? " · " + escapeHtml(row.group_relation) : ""}${row.is_custom_doctype ? " · " + __("Custom DocType") : ""}${row.is_child_table ? " · " + __("Child Table") : ""} · ${escapeHtml(matrixSourceLabel(row))}</small></div></td><td>${badge(String(row.permlevel || 0), "gray")}</td><td>${sourceBadge(row.source)}</td><td>${badge(row.risk || "low", row.risk === "critical" ? "red" : row.risk === "high" ? "amber" : row.risk === "medium" ? "blue" : "gray")}</td>${PERMISSION_FIELDS.map((field) => {
            const inherited = isInheritedBaseField(row, field);
            const disabled = disabledFields.has(field) || inherited;
            const title = disabledFields.has(field) ? __("Disabled for Orderlift-managed business documents") : inherited ? __("Already active from inherited base access. Role-specific changes cannot remove inherited access.") : labelPermission(field);
            return `<td><label class="acc-perm-toggle ${disabled ? "disabled" : ""}" title="${escapeHtml(title)}"><input type="checkbox" data-permission-field="${field}" ${draft[field] && !disabledFields.has(field) ? "checked" : ""} ${disabled ? "disabled" : ""} /><span></span></label></td>`;
        }).join("")}<td>${matrixRowAction(row)}</td></tr>`;
    }

    function matrixSourceLabel(row) {
        if (row.source === "mixed") return __("Inherited + Role");
        if (row.source === "base") return __("Inherited");
        if (row.source === "direct") return __("Role-specific");
        return __("No access");
    }

    function matrixRowAction(row) {
        if (row.can_reset) return `<button class="acc-row-action" data-reset-docperm="${escapeHtml(row.doctype)}" data-reset-permlevel="${row.permlevel || 0}">${__("Reset")}</button>`;
        if (row.source === "base" || row.source === "mixed") {
            return `<button class="acc-row-action" disabled>${__("Inherited")}</button>`;
        }
        return `<button class="acc-row-action" disabled>${__("Reset")}</button>`;
    }

    function pageAccessMarkup(rows) {
        return `<article class="acc-access-card"><h3>${__("Page Access")}</h3><p>${__("Pages use role access, not CRUD permissions.")}</p>${rows.slice(0, 8).map((row) => `<div class="acc-access-row"><span><strong>${escapeHtml(row.title || row.name)}</strong><small>${escapeHtml(row.module || "")}</small></span><span>${(row.roles || []).slice(0, 3).map(roleChip).join("") || badge(__("No roles"), "gray")}</span><button class="acc-row-action" data-edit-page-access="${escapeHtml(row.name)}">${__("Edit")}</button></div>`).join("") || emptyMini(__("No pages found"))}</article>`;
    }

    function reportAccessMarkup(rows) {
        return `<article class="acc-access-card"><h3>${__("Report Access")}</h3><p>${__("Reports also use role access rows.")}</p>${rows.slice(0, 8).map((row) => `<div class="acc-access-row"><span><strong>${escapeHtml(row.name)}</strong><small>${escapeHtml(row.ref_doctype || row.report_type || "")}</small></span><span>${(row.roles || []).slice(0, 3).map(roleChip).join("") || badge(__("No roles"), "gray")}</span><button class="acc-row-action" data-edit-report-access="${escapeHtml(row.name)}">${__("Edit")}</button></div>`).join("") || emptyMini(__("No reports found"))}</article>`;
    }

    function reportsAccessManagerMarkup(data) {
        const roles = availableRoles();
        const selectedRole = STATE.selectedRole || (roles[0] && roles[0].name) || "";
        const rows = data.report_access || [];
        const granted = rows.filter((row) => (row.roles || []).includes(selectedRole)).length;
        const groups = groupedReportRows(rows);
        const selectedCount = selectedReportNames().length;
        const searchActive = Boolean(String(STATE.reportSearch || "").trim());
        return panelShell(__("Report Access"), __("Grant roles to ERPNext and Orderlift reports. Report access is separate from DocType permissions."), `
            <div class="acc-matrix-toolbar">
                <label><span>${__("Role")}</span><select data-role-selector>${roles.map((role) => `<option value="${escapeHtml(role.name)}" ${role.name === selectedRole ? "selected" : ""}>${escapeHtml(role.name)}</option>`).join("")}</select></label>
                <label><span>${__("Search reports")}</span><input data-report-search type="search" value="${escapeHtml(STATE.reportSearch)}" placeholder="${__("General Ledger, GL Entry, Sales...")}" /></label>
                ${STATE.reportSearch ? `<button class="acc-row-action" data-clear-report-search>${__("Clear Search")}</button>` : ""}
                <button class="acc-row-action" data-report-bulk="grant" ${selectedCount ? "" : "disabled"}>${__("Grant Selected")}</button>
                <button class="acc-row-action danger" data-report-bulk="revoke" ${selectedCount ? "" : "disabled"}>${__("Revoke Selected")}</button>
                <button class="acc-row-action" data-clear-report-selection ${selectedCount ? "" : "disabled"}>${__("Clear Selection")}</button>
                <span class="acc-count-pill"><strong>${granted}</strong> ${__("granted to")} ${escapeHtml(selectedRole || __("role"))} · <strong>${rows.length}</strong> ${__("visible reports")}</span>
                <span class="acc-count-pill"><strong>${selectedCount}</strong> ${__("selected")}</span>
            </div>
            <div class="acc-table-wrap">
                <table class="acc-table acc-report-table">
                    <thead><tr><th><input type="checkbox" data-select-all-reports aria-label="${__("Select all visible reports")}" /></th><th>${__("Allowed")}</th><th>${__("Report")}</th><th>${__("Ref DocType")}</th><th>${__("Type")}</th><th>${__("Roles")}</th><th>${__("DocType Check")}</th><th>${__("Action")}</th></tr></thead>
                    <tbody>${groups.map((group) => reportGroupRow(group, selectedRole, searchActive)).join("") || tableEmpty(__("No reports found"), __("Search for a report name or reference DocType."))}</tbody>
                </table>
            </div>
        `);
    }

    function groupedReportRows(rows) {
        const groups = new Map();
        (rows || []).forEach((row) => {
            const key = row.ref_doctype || row.report_type || __("Other Reports");
            if (!groups.has(key)) groups.set(key, { key, label: key, rows: [] });
            groups.get(key).rows.push(row);
        });
        return Array.from(groups.values()).sort((a, b) => String(a.label).localeCompare(String(b.label)));
    }

    function reportGroupRow(group, selectedRole, searchActive) {
        const expanded = Boolean(STATE.reportExpandedGroups[group.key]) || searchActive;
        const allowedCount = group.rows.filter((row) => (row.roles || []).includes(selectedRole)).length;
        const selectedCount = group.rows.filter((row) => STATE.selectedReports[row.name]).length;
        return `
            <tr class="acc-report-group-row" data-report-group="${escapeHtml(group.key)}">
                <td><input type="checkbox" data-select-report-group="${escapeHtml(group.key)}" ${selectedCount === group.rows.length ? "checked" : ""} /></td>
                <td colspan="2"><button class="acc-group-toggle" data-toggle-report-group="${escapeHtml(group.key)}" aria-expanded="${expanded ? "true" : "false"}"><span>${expanded ? "-" : "+"}</span><strong>${escapeHtml(group.label)}</strong></button><small>${allowedCount}/${group.rows.length} ${__("allowed")} · ${selectedCount} ${__("selected")}</small></td>
                <td colspan="3"><button class="acc-row-action" data-report-group-bulk="grant" data-report-group-name="${escapeHtml(group.key)}">${__("Grant Group")}</button> <button class="acc-row-action danger" data-report-group-bulk="revoke" data-report-group-name="${escapeHtml(group.key)}">${__("Revoke Group")}</button></td>
                <td>${badge(String(group.rows.length), "gray")}</td>
                <td><button class="acc-row-action" data-toggle-report-group="${escapeHtml(group.key)}">${expanded ? __("Collapse") : __("Expand")}</button></td>
            </tr>
            ${expanded ? group.rows.map((row) => reportAccessRow(row, selectedRole)).join("") : ""}
        `;
    }

    function reportAccessRow(row, selectedRole) {
        const roles = row.roles || [];
        const isAllowed = roles.includes(selectedRole);
        const docTypeOk = reportRefDoctypeStatus(row.ref_doctype);
        return `<tr data-report-row="${escapeHtml(row.name)}">
            <td><input type="checkbox" data-select-report="${escapeHtml(row.name)}" ${STATE.selectedReports[row.name] ? "checked" : ""} /></td>
            <td><input type="checkbox" data-toggle-report-role="${escapeHtml(row.name)}" ${isAllowed ? "checked" : ""} ${!selectedRole ? "disabled" : ""} /></td>
            <td><div class="acc-user-cell"><div><strong>${escapeHtml(row.name)}</strong><small>${row.is_standard ? __("Standard report") : __("Custom report")}</small></div></div></td>
            <td>${escapeHtml(row.ref_doctype || "-")}</td>
            <td>${badge(row.report_type || __("Report"), "blue")}</td>
            <td>${roles.slice(0, 4).map(roleChip).join("") || badge(__("No roles"), "gray")}${roles.length > 4 ? badge(`+${roles.length - 4}`, "gray") : ""}</td>
            <td>${docTypeOk}</td>
            <td><button class="acc-row-action" data-edit-report-access="${escapeHtml(row.name)}">${__("Edit Roles")}</button></td>
        </tr>`;
    }

    function reportRefDoctypeStatus(refDoctype) {
        if (!refDoctype) return badge(__("No Ref DocType"), "gray");
        const rows = (((STATE.data || {}).permission_matrix || {}).rows || []).filter((row) => row.doctype === refDoctype);
        const hasReadReport = rows.some((row) => Number((row.effective || {}).read || 0) && Number((row.effective || {}).report || 0));
        if (hasReadReport) return badge(__("Read + Report"), "green");
        return badge(__("Needs DocPerm"), "amber");
    }

    function bind(page) {
        page.main.find("[data-tab]").on("click", function () { STATE.activeTab = $(this).data("tab"); render(page); });
        page.main.find("[data-refresh]").on("click", () => load(page));
        page.main.find("[data-global-search]").on("keydown", function (event) {
            if (event.key !== "Enter") return;
            STATE.search = String($(this).val() || "").trim();
            clearMatrixDraft();
            load(page);
        });
        page.main.find("[data-new-user]").on("click", () => openCreateUserDialog(page));
        page.main.find("[data-filter-users]").on("click", function () {
            STATE.userFilter = String($(this).data("filter-users") || "all");
            render(page);
        });
        page.main.find("[data-new-role]").on("click", () => openRoleDialog(page));
        page.main.find("[data-edit-role]").on("click", function () {
            const roleName = $(this).data("edit-role");
            const role = ((STATE.data || {}).roles || []).find((row) => row.name === roleName);
            openRoleDialog(page, role);
        });
        page.main.find("[data-delete-role]").on("click", function () { deleteCustomRole(page, $(this).data("delete-role")); });
        page.main.find("[data-export]").on("click", () => exportActiveTab());
        page.main.find("[data-select-all-users]").on("change", function () { page.main.find("[data-select-user]").prop("checked", $(this).is(":checked")); });
        page.main.find("[data-view-user], [data-user-row]").on("click", async function (event) {
            event.stopPropagation();
            if ($(event.target).is("input")) return;
            await loadUserDetail($(this).data("view-user") || $(this).data("user-row"), true, page);
        });
        page.main.find("[data-role-selector]").on("change", function () { STATE.selectedRole = $(this).val(); clearMatrixDraft(); load(page); });
        page.main.find("[data-menu-role-selector]").on("change", function () { STATE.selectedRole = $(this).val(); clearMatrixDraft(); load(page); });
        page.main.find("[data-matrix-view]").on("change", function () { STATE.matrixView = $(this).val() || "grouped"; render(page); });
        page.main.find("[data-doctype-search]").on("input", function () {
            STATE.matrixSearchInput = String($(this).val() || "");
            STATE.matrixSearchPending = true;
            page.main.find("[data-matrix-search-status]").addClass("active").html(`<b></b>${__("Searching")}`);
            clearTimeout(matrixSearchTimer);
            matrixSearchTimer = setTimeout(() => {
                STATE.doctypeSearch = STATE.matrixSearchInput;
                STATE.matrixSearchPending = false;
                render(page);
                focusMatrixSearch(page);
            }, 320);
        });
        page.main.find("[data-doctype-search]").on("keydown", function (event) {
            if (event.key !== "Escape") return;
            STATE.doctypeSearch = "";
            STATE.matrixSearchInput = "";
            STATE.matrixSearchPending = false;
            clearTimeout(matrixSearchTimer);
            render(page);
            focusMatrixSearch(page);
        });
        page.main.find("[data-clear-doctype-search]").on("click", function () {
            STATE.doctypeSearch = "";
            STATE.matrixSearchInput = "";
            STATE.matrixSearchPending = false;
            clearTimeout(matrixSearchTimer);
            render(page);
            focusMatrixSearch(page);
        });
        page.main.find("[data-toggle-matrix-group]").on("click", function () {
            const groupKey = String($(this).data("toggle-matrix-group") || "");
            if (!groupKey) return;
            const scrollState = captureScrollState(page);
            STATE.matrixExpandedGroups[groupKey] = !STATE.matrixExpandedGroups[groupKey];
            render(page);
            restoreScrollState(page, scrollState);
        });
        page.main.find("[data-group-permission-field]").each(function () { this.indeterminate = Number($(this).data("mixed") || 0) === 1; });
        page.main.find("[data-group-permission-field]").on("change", function () {
            applyGroupPermission(page, String($(this).data("group-key") || ""), String($(this).data("group-permission-field") || ""), $(this).is(":checked"));
        });
        page.main.find("[data-tab-jump]").on("click", function () {
            STATE.activeTab = $(this).data("tab-jump");
            if ($(this).data("role-jump")) STATE.selectedRole = $(this).data("role-jump");
            clearMatrixDraft();
            load(page);
        });
        page.main.find("[data-matrix-row] [data-permission-field]").on("change", function () {
            const scrollState = captureScrollState(page);
            const row = $(this).closest("[data-matrix-row]");
            const rowKey = row.data("matrix-row");
            const values = matrixDraftValues(row);
            STATE.matrixDraft[rowKey] = values;
            STATE.matrixDraftRole = STATE.selectedRole;
            row.addClass("draft");
            updateStickySaveBar(page);
            restoreScrollState(page, scrollState);
        });
        page.main.find("[data-reset-docperm]").on("click", function () { resetDocPerm(page, $(this).data("reset-docperm"), $(this).data("reset-permlevel")); });
        page.main.find("[data-edit-page-access]").on("click", function () { openAccessRolesDialog(page, "Page", $(this).data("edit-page-access")); });
        page.main.find("[data-edit-report-access]").on("click", function () { openAccessRolesDialog(page, "Report", $(this).data("edit-report-access")); });
        page.main.find("[data-toggle-report-role]").on("change", function () { saveReportRoleToggle(page, $(this).data("toggle-report-role"), $(this).is(":checked")); });
        page.main.find("[data-toggle-report-group]").on("click", function () {
            const groupKey = String($(this).data("toggle-report-group") || "");
            if (!groupKey) return;
            STATE.reportExpandedGroups[groupKey] = !STATE.reportExpandedGroups[groupKey];
            render(page);
        });
        page.main.find("[data-select-report]").on("change", function () {
            const reportName = String($(this).data("select-report") || "");
            if (!reportName) return;
            if ($(this).is(":checked")) STATE.selectedReports[reportName] = true;
            else delete STATE.selectedReports[reportName];
            render(page);
        });
        page.main.find("[data-select-all-reports]").on("change", function () {
            const checked = $(this).is(":checked");
            ((STATE.data || {}).report_access || []).forEach((row) => {
                if (checked) STATE.selectedReports[row.name] = true;
                else delete STATE.selectedReports[row.name];
            });
            render(page);
        });
        page.main.find("[data-select-report-group]").on("change", function () {
            const groupKey = String($(this).data("select-report-group") || "");
            const checked = $(this).is(":checked");
            reportRowsForGroup(groupKey).forEach((row) => {
                if (checked) STATE.selectedReports[row.name] = true;
                else delete STATE.selectedReports[row.name];
            });
            render(page);
        });
        page.main.find("[data-report-bulk]").on("click", function () {
            saveReportRoleBulk(page, selectedReportNames(), String($(this).data("report-bulk") || "grant") === "grant");
        });
        page.main.find("[data-report-group-bulk]").on("click", function () {
            const names = reportRowsForGroup(String($(this).data("report-group-name") || "")).map((row) => row.name);
            saveReportRoleBulk(page, names, String($(this).data("report-group-bulk") || "grant") === "grant");
        });
        page.main.find("[data-clear-report-selection]").on("click", function () {
            STATE.selectedReports = {};
            render(page);
        });
        page.main.find("[data-report-search]").on("input", function () {
            STATE.reportSearch = String($(this).val() || "");
            clearTimeout(reportSearchTimer);
            reportSearchTimer = setTimeout(() => load(page), 320);
        });
        page.main.find("[data-report-search]").on("keydown", function (event) {
            if (event.key !== "Escape") return;
            STATE.reportSearch = "";
            clearTimeout(reportSearchTimer);
            load(page);
        });
        page.main.find("[data-clear-report-search]").on("click", function () {
            STATE.reportSearch = "";
            clearTimeout(reportSearchTimer);
            load(page);
        });
        page.main.find("[data-review-save]").on("click", () => reviewAndSaveMatrix(page));
        page.main.find("[data-clear-draft]").on("click", () => { clearMatrixDraft(); render(page); });
        page.main.find("[data-save-user]").on("click", () => saveUserDetails(page));
        page.main.find("[data-delete-user]").on("click", () => deleteSelectedUser(page));
        page.main.find("[data-save-user-roles]").on("click", () => reviewAndSaveUserRoles(page));
        page.main.find("[data-user-company]").on("change", () => refreshCompanyScopedAccessOptions(page));
        page.main.find("[data-save-user-companies]").on("click", () => reviewAndSaveUserCompanies(page));
        page.main.find("[data-make-default-company]").on("click", function () { reviewAndSaveUserCompanies(page, String($(this).data("make-default-company") || "")); });
        page.main.find("[data-save-user-warehouses]").on("click", () => reviewAndSaveUserWarehouses(page));
        page.main.find("[data-save-user-business-types]").on("click", () => reviewAndSaveUserBusinessTypes(page));
        page.main.find("[data-save-menu-access]").on("click", () => reviewAndSaveMenuAccess(page));
        page.main.find("[data-bulk-roles]").on("click", () => openBulkRoleDialog(page));
        page.main.find("[data-column-note]").on("click", () => openColumnDialog(page));
    }

    function applyGroupPermission(page, groupKey, field, enabled) {
        if (!groupKey || !field) return;
        const scrollState = captureScrollState(page);
        const rows = filteredMatrixRows(functionalMatrixRows(((STATE.data || {}).permission_matrix || {}).rows || []), STATE.doctypeSearch)
            .filter((row) => (row.group_key || `module:${row.module || "Unassigned"}`) === groupKey);
        rows.forEach((row) => {
            if ((row.disabled_permission_fields || []).includes(field)) return;
            if (isInheritedBaseField(row, field)) return;
            const rowKey = row.row_key || `${row.doctype}::${row.permlevel || 0}`;
            const values = { ...(row.direct || {}) };
            values[field] = enabled ? 1 : 0;
            values.doctype = row.doctype;
            values.permlevel = Number(row.permlevel || 0);
            values.role = STATE.selectedRole;
            STATE.matrixDraft[rowKey] = values;
        });
        STATE.matrixDraftRole = STATE.selectedRole;
        render(page);
        updateStickySaveBar(page);
        restoreScrollState(page, scrollState);
    }

    function matrixDraftValues(rowElement) {
        const rowKey = rowElement.data("matrix-row");
        const rowData = matrixRowByKey(rowKey) || {};
        const values = { ...(rowData.direct || {}) };
        rowElement.find("[data-permission-field]").each(function () {
            const field = String($(this).data("permission-field") || "");
            if (!field) return;
            if ((rowData.disabled_permission_fields || []).includes(field)) {
                values[field] = 0;
            } else if (isInheritedBaseField(rowData, field)) {
                values[field] = Number((rowData.direct || {})[field] || 0);
            } else {
                values[field] = $(this).is(":checked") ? 1 : 0;
            }
        });
        values.doctype = rowElement.data("doctype");
        values.permlevel = Number(rowElement.data("permlevel") || 0);
        values.role = STATE.selectedRole;
        return values;
    }

    function matrixRowByKey(rowKey) {
        return (((STATE.data || {}).permission_matrix || {}).rows || []).find((row) => (row.row_key || `${row.doctype}::${row.permlevel || 0}`) === rowKey);
    }

    function focusMatrixSearch(page) {
        const input = page.main.find("[data-doctype-search]").get(0);
        if (!input) return;
        input.focus();
        const length = input.value.length;
        try {
            input.setSelectionRange(length, length);
        } catch (error) {
            // Some browsers do not support selection on search inputs.
        }
    }

    async function saveUserDetails(page) {
        const panel = page.main.find(".acc-detail-panel");
        const payload = { name: STATE.selectedUser, audit_note: __("Access Command Center user detail update") };
        panel.find("[data-user-field]").each(function () {
            const field = $(this).data("user-field");
            payload[field] = $(this).attr("type") === "checkbox" ? ($(this).is(":checked") ? 1 : 0) : $(this).val();
        });
        await frappe.call({ method: `${METHOD}.save_user_basic_info`, args: { payload }, freeze: true });
        frappe.show_alert({ message: __("User details saved"), indicator: "green" });
        await load(page);
    }

    function deleteSelectedUser(page) {
        if (!STATE.selectedUser) return;
        frappe.confirm(
            __("Delete user {0}? This cannot be undone and is only allowed for non-system business users.", [STATE.selectedUser]),
            async () => {
                await frappe.call({ method: `${METHOD}.delete_user`, args: { user_name: STATE.selectedUser, audit_note: __("Access Command Center user deletion") }, freeze: true });
                frappe.show_alert({ message: __("User deleted"), indicator: "green" });
                STATE.selectedUser = "";
                STATE.selectedUserDetail = null;
                await load(page);
            }
        );
    }

    function openCreateUserDialog(page) {
        const roleOptions = scopedRoleOptions();
        const dialog = new frappe.ui.Dialog({
            title: __("Invite User"),
            fields: [
                { fieldname: "email", label: __("Email"), fieldtype: "Data", reqd: 1 },
                { fieldname: "full_name", label: __("Full Name"), fieldtype: "Data" },
                { fieldname: "user_type", label: __("User Type"), fieldtype: "Select", options: "System User\nWebsite User", default: "System User" },
                { fieldname: "main_role", label: __("Initial Role"), fieldtype: "Select", options: roleOptions, default: roleOptions[0] || "" },
                { fieldname: "enabled", label: __("Enabled"), fieldtype: "Check", default: 1 },
                { fieldname: "send_welcome_email", label: __("Send Welcome Email"), fieldtype: "Check", default: 0 },
            ],
            primary_action_label: __("Create User"),
            primary_action: async (values) => {
                const payload = {
                    email: values.email,
                    full_name: values.full_name,
                    user_type: values.user_type,
                    enabled: values.enabled ? 1 : 0,
                    send_welcome_email: values.send_welcome_email ? 1 : 0,
                    roles: values.main_role ? [values.main_role] : [],
                    audit_note: __("Access Command Center user creation"),
                };
                await frappe.call({ method: `${METHOD}.create_user`, args: { payload }, freeze: true });
                STATE.selectedUser = values.email;
                dialog.hide();
                frappe.show_alert({ message: __("User created"), indicator: "green" });
                await load(page);
            },
        });
        dialog.show();
    }

    function openRoleDialog(page, role) {
        if (role && role.is_protected) {
            frappe.msgprint({ title: __("Protected Role"), message: __("System and protected roles cannot be edited here. Create a custom role or use the Role form."), indicator: "orange" });
            return;
        }
        const assignedCapabilities = new Set((role && role.capabilities) || []);
        const capabilityOptions = ((STATE.data || {}).role_capabilities || []).map((capability) => ({
            label: capability.label || capability.value,
            value: capability.value,
            checked: assignedCapabilities.has(capability.value),
        }));
        const dialog = new frappe.ui.Dialog({
            title: role ? __("Edit Custom Role") : __("New Custom Role"),
            fields: [
                { fieldname: "name", label: __("Role Name"), fieldtype: "Data", reqd: 1, read_only: role ? 1 : 0, default: role ? role.name : "" },
                { fieldname: "desk_access", label: __("Desk Access"), fieldtype: "Check", default: role ? role.desk_access : 1 },
                { fieldname: "disabled", label: __("Disabled"), fieldtype: "Check", default: role ? role.disabled : 0 },
                { fieldname: "two_factor_auth", label: __("Require Two-Factor Auth"), fieldtype: "Check", default: 0 },
                { fieldname: "capabilities", label: __("Orderlift Capabilities"), fieldtype: "MultiCheck", options: capabilityOptions, columns: 1, description: __("Capabilities are shadow-checked for now; legacy hardcoded role checks remain authoritative until the site flag is enabled.") },
            ],
            primary_action_label: role ? __("Save Role") : __("Create Role"),
            primary_action: async (values) => {
                const selectedCapabilities = getDialogMultiCheckValues(dialog, "capabilities", values.capabilities);
                const payload = {
                    current_name: role ? role.name : "",
                    name: values.name,
                    desk_access: values.desk_access ? 1 : 0,
                    disabled: values.disabled ? 1 : 0,
                    two_factor_auth: values.two_factor_auth ? 1 : 0,
                    capabilities: selectedCapabilities,
                    audit_note: role ? __("Access Command Center role edit") : __("Access Command Center role creation"),
                };
                await frappe.call({ method: `${METHOD}.save_role`, args: { payload }, freeze: true });
                dialog.hide();
                frappe.show_alert({ message: role ? __("Role saved") : __("Role created"), indicator: "green" });
                await load(page);
            },
        });
        dialog.show();
    }

    function deleteCustomRole(page, roleName) {
        if (!roleName) return;
        frappe.confirm(
            __("Delete custom role {0}? This is only allowed when no users are assigned to it.", [roleName]),
            async () => {
                await frappe.call({ method: `${METHOD}.delete_role`, args: { role_name: roleName, audit_note: __("Access Command Center role deletion") }, freeze: true });
                frappe.show_alert({ message: __("Role deleted"), indicator: "green" });
                await load(page);
            }
        );
    }

    function openBulkRoleDialog(page) {
        const users = getSelectedUsers(page);
        if (!users.length) {
            frappe.msgprint({ title: __("No Users Selected"), message: __("Select one or more users from the table before running a bulk role update."), indicator: "orange" });
            return;
        }
        const roleOptions = scopedRoleOptions();
        const dialog = new frappe.ui.Dialog({
            title: __("Bulk Role Assignment"),
            fields: [
                { fieldname: "role", label: __("Role"), fieldtype: "Select", options: roleOptions, default: roleOptions[0] || "", reqd: 1 },
                { fieldname: "action", label: __("Action"), fieldtype: "Select", options: "add\nremove", default: "add", reqd: 1 },
                { fieldname: "note", label: __("Reason / Audit Note"), fieldtype: "Small Text", reqd: 1 },
            ],
            primary_action_label: __("Apply to {0} Users", [users.length]),
            primary_action: async (values) => {
                await frappe.call({ method: `${METHOD}.bulk_update_user_roles`, args: { user_names: users, role: values.role, action: values.action, audit_note: values.note }, freeze: true });
                dialog.hide();
                frappe.show_alert({ message: __("Bulk role update applied"), indicator: "green" });
                await load(page);
            },
        });
        dialog.show();
    }

    function scopedRoleOptions() {
        return availableRoles().map((role) => role.name).filter(Boolean);
    }

    function availableRoles() {
        const data = STATE.data || {};
        return data.all_roles || data.roles || [];
    }

    function permissionMatrixRoles() {
        return availableRoles().filter((role) => role.name !== BASE_PERMISSION_ROLE);
    }

    function selectedPermissionRoleLabel() {
        const role = permissionMatrixRoles().find((item) => item.name === STATE.selectedRole);
        return (role && (role.label || role.name)) || STATE.selectedRole;
    }

    function isInheritedBaseField(row, field) {
        if (!row || row.is_base_role || STATE.selectedRole === BASE_PERMISSION_ROLE) return false;
        return Number(((row.base || {})[field]) || 0) === 1;
    }

    function roleCapabilityLabels(values) {
        const labels = new Map(((STATE.data || {}).role_capabilities || []).map((capability) => [capability.value, capability.label || capability.value]));
        return (values || []).map((value) => labels.get(value) || value).filter(Boolean);
    }

    function clearMatrixDraft() {
        STATE.matrixDraft = {};
        STATE.matrixDraftRole = "";
    }

    function openColumnDialog(page) {
        const columns = [
            ["status", "Status"],
            ["type", "Type"],
            ["main_role", "Main Role"],
            ["roles", "Roles"],
            ["last_login", "Last Login"],
            ["access", "Access"],
        ];
        const dialog = new frappe.ui.Dialog({
            title: __("User Table Columns"),
            fields: columns.map(([key, label]) => ({ fieldname: key, label: __(label), fieldtype: "Check", default: STATE.hiddenUserColumns.includes(key) ? 0 : 1 })),
            primary_action_label: __("Apply Columns"),
            primary_action: (values) => {
                STATE.hiddenUserColumns = columns.filter(([key]) => !values[key]).map(([key]) => key);
                dialog.hide();
                render(page);
            },
        });
        dialog.show();
    }

    function openAccessRolesDialog(page, parenttype, name) {
        const rows = parenttype === "Page" ? ((STATE.data || {}).page_access || []) : ((STATE.data || {}).report_access || []);
        const row = rows.find((item) => item.name === name);
        const assigned = new Set((row && row.roles) || []);
        const roles = availableRoles().map((role) => ({ label: role.name, value: role.name, checked: assigned.has(role.name) }));
        const dialog = new frappe.ui.Dialog({
            title: parenttype === "Page" ? __("Edit Page Access") : __("Edit Report Access"),
            fields: [
                { fieldname: "target", label: parenttype, fieldtype: "Data", read_only: 1, default: name },
                { fieldname: "roles", label: __("Allowed Roles"), fieldtype: "MultiCheck", options: roles, columns: 2 },
                { fieldname: "note", label: __("Reason / Audit Note"), fieldtype: "Small Text", reqd: 1 },
            ],
            primary_action_label: __("Save Access"),
            primary_action: async (values) => {
                const selectedRoles = getDialogMultiCheckValues(dialog, "roles", values.roles);
                const method = parenttype === "Page" ? "save_page_access" : "save_report_access";
                const args = parenttype === "Page"
                    ? { page_name: name, roles: selectedRoles, audit_note: values.note }
                    : { report_name: name, roles: selectedRoles, audit_note: values.note };
                await frappe.call({ method: `${METHOD}.${method}`, args, freeze: true });
                dialog.hide();
                frappe.show_alert({ message: __("Access roles saved"), indicator: "green" });
                await load(page);
            },
        });
        dialog.show();
    }

    async function saveReportRoleToggle(page, reportName, enabled) {
        const row = ((STATE.data || {}).report_access || []).find((item) => item.name === reportName);
        if (!row || !STATE.selectedRole) return;
        const roles = new Set(row.roles || []);
        if (enabled) roles.add(STATE.selectedRole);
        else roles.delete(STATE.selectedRole);
        await frappe.call({
            method: `${METHOD}.save_report_access`,
            args: {
                report_name: reportName,
                roles: Array.from(roles),
                audit_note: enabled
                    ? __(`Access Command Center granted ${STATE.selectedRole} report access`)
                    : __(`Access Command Center revoked ${STATE.selectedRole} report access`),
            },
            freeze: true,
        });
        frappe.show_alert({ message: enabled ? __("Report access granted") : __("Report access revoked"), indicator: "green" });
        await load(page);
    }

    function selectedReportNames() {
        const visible = new Set(((STATE.data || {}).report_access || []).map((row) => row.name));
        return Object.keys(STATE.selectedReports || {}).filter((name) => visible.has(name));
    }

    function reportRowsForGroup(groupKey) {
        return ((STATE.data || {}).report_access || []).filter((row) => (row.ref_doctype || row.report_type || __("Other Reports")) === groupKey);
    }

    async function saveReportRoleBulk(page, reportNames, enabled) {
        if (!STATE.selectedRole || !reportNames.length) return;
        const action = enabled ? __("grant") : __("revoke");
        frappe.confirm(
            __("{0} {1} report access for role {2}?", [action, reportNames.length, STATE.selectedRole]),
            async () => {
                await frappe.call({
                    method: `${METHOD}.save_report_role_access`,
                    args: {
                        report_names: reportNames,
                        role: STATE.selectedRole,
                        enabled: enabled ? 1 : 0,
                        audit_note: enabled
                            ? __("Access Command Center bulk report grant")
                            : __("Access Command Center bulk report revoke"),
                    },
                    freeze: true,
                });
                STATE.selectedReports = {};
                frappe.show_alert({ message: enabled ? __("Report access granted") : __("Report access revoked"), indicator: "green" });
                await load(page);
            }
        );
    }

    function reviewAndSaveUserRoles(page) {
        const roles = page.main.find("[data-user-role]:checked").map(function () { return $(this).data("user-role"); }).get();
        frappe.confirm(
            __("Save {0} role assignment(s) for {1}? Critical access changes will be audited.", [roles.length, STATE.selectedUser]),
            async () => {
                await frappe.call({ method: `${METHOD}.save_user_roles`, args: { user_name: STATE.selectedUser, roles, audit_note: __("Access Command Center role assignment update") }, freeze: true });
                frappe.show_alert({ message: __("User roles saved"), indicator: "green" });
                await load(page);
            }
        );
    }

    function reviewAndSaveUserCompanies(page, defaultCompanyOverride = "") {
        const companies = page.main.find("[data-user-company]:checked").map(function () { return $(this).data("user-company"); }).get();
        const defaultCompany = String(defaultCompanyOverride || ((STATE.selectedUserDetail || {}).default_company || ""));
        if (defaultCompany && !companies.includes(defaultCompany)) companies.push(defaultCompany);
        frappe.confirm(
            __("Save {0} company assignment(s) for {1}? Users without assigned companies will not see company-scoped data unless they have admin access.", [companies.length, STATE.selectedUser]),
            async () => {
                await frappe.call({ method: `${METHOD}.save_user_companies`, args: { user_name: STATE.selectedUser, companies, default_company: defaultCompany, audit_note: __("Access Command Center company assignment update") }, freeze: true });
                frappe.show_alert({ message: __("Company access saved"), indicator: "green" });
                await load(page);
            }
        );
    }

    function reviewAndSaveUserBusinessTypes(page) {
        const businessTypes = page.main.find("[data-user-business-type]:checked").map(function () { return $(this).data("user-business-type"); }).get();
        const message = businessTypes.length
            ? __("Restrict {0} to {1} business type(s)? They will only see records of those business types within their assigned companies (untagged records stay visible).", [STATE.selectedUser, businessTypes.length])
            : __("Clear all business-type restrictions for {0}? They will see every business type within their assigned companies.", [STATE.selectedUser]);
        frappe.confirm(
            message,
            async () => {
                await frappe.call({ method: `${METHOD}.save_user_business_types`, args: { user_name: STATE.selectedUser, business_types: businessTypes, audit_note: __("Access Command Center business type assignment update") }, freeze: true });
                frappe.show_alert({ message: __("Business type access saved"), indicator: "green" });
                await load(page);
            }
        );
    }

    function reviewAndSaveUserWarehouses(page) {
        const warehouses = page.main.find("[data-user-warehouse]:checked").map(function () { return $(this).data("user-warehouse"); }).get();
        const message = warehouses.length
            ? __("Restrict {0} to {1} warehouse(s)? Stock, warehouse, and ledger views will only show those warehouses.", [STATE.selectedUser, warehouses.length])
            : __("Clear warehouse restrictions for {0}? They will see company-level warehouse stock again.", [STATE.selectedUser]);
        frappe.confirm(
            message,
            async () => {
                await frappe.call({ method: `${METHOD}.save_user_warehouses`, args: { user_name: STATE.selectedUser, warehouses, audit_note: __("Access Command Center warehouse assignment update") }, freeze: true });
                frappe.show_alert({ message: __("Warehouse access saved"), indicator: "green" });
                await load(page);
            }
        );
    }

    function reviewAndSaveMenuAccess(page) {
        const role = STATE.selectedRole;
        const menuKeys = page.main.find("[data-menu-key]:checked").map(function () { return $(this).data("menu-key"); }).get();
        frappe.confirm(
            __("Save {0} visible menu item(s) for role {1}?", [menuKeys.length, role]),
            async () => {
                await frappe.call({ method: `${METHOD}.save_menu_access_for_role`, args: { role, menu_keys: menuKeys, audit_note: __("Access Command Center menu access update") }, freeze: true });
                frappe.show_alert({ message: __("Menu access saved"), indicator: "green" });
                await load(page);
            }
        );
    }

    function reviewAndSaveMatrix(page) {
        const changes = Object.keys(STATE.matrixDraft);
        if (!changes.length) return;
        if (STATE.matrixDraftRole && STATE.matrixDraftRole !== STATE.selectedRole) {
            frappe.msgprint({ title: __("Role Changed"), message: __("Discard the current matrix draft and edit the selected role again before saving."), indicator: "orange" });
            return;
        }
        frappe.confirm(
            __("Apply {0} permission override(s) for {1}? A Custom DocPerm record will be saved for each changed DocType.", [changes.length, selectedPermissionRoleLabel()]),
            async () => {
                const payload = changes.map((rowKey) => STATE.matrixDraft[rowKey]).filter(Boolean);
                await frappe.call({
                    method: `${METHOD}.save_custom_docperms`,
                    args: { role: STATE.selectedRole, changes: payload, audit_note: __("Access Command Center permission matrix update") },
                    freeze: true,
                });
                clearMatrixDraft();
                frappe.show_alert({ message: __("Permission overrides saved"), indicator: "green" });
                await load(page);
            }
        );
    }

    function resetDocPerm(page, doctypeName, permlevel) {
        frappe.confirm(
            __("Reset custom permission override for {0} and role {1}? The system permission will become effective again.", [doctypeName, STATE.selectedRole]),
            async () => {
                await frappe.call({ method: `${METHOD}.delete_custom_docperm`, args: { role: STATE.selectedRole, doctype_name: doctypeName, permlevel: Number(permlevel || 0), audit_note: __("Access Command Center permission reset") }, freeze: true });
                frappe.show_alert({ message: __("Custom override reset"), indicator: "green" });
                await load(page);
            }
        );
    }

    function updateStickySaveBar(page) {
        page.main.find(".acc-save-bar").remove();
        const markup = stickySaveBarMarkup();
        if (markup) page.main.append(markup);
        page.main.find("[data-review-save]").on("click", () => reviewAndSaveMatrix(page));
        page.main.find("[data-clear-draft]").on("click", () => { clearMatrixDraft(); render(page); });
    }

    function captureScrollState(page) {
        const matrix = page.main.find(".acc-matrix-wrap").get(0);
        return {
            windowX: window.scrollX,
            windowY: window.scrollY,
            matrixLeft: matrix ? matrix.scrollLeft : 0,
            matrixTop: matrix ? matrix.scrollTop : 0,
        };
    }

    function restoreScrollState(page, state) {
        requestAnimationFrame(() => {
            const matrix = page.main.find(".acc-matrix-wrap").get(0);
            if (matrix) {
                matrix.scrollLeft = state.matrixLeft;
                matrix.scrollTop = state.matrixTop;
            }
            window.scrollTo(state.windowX, state.windowY);
        });
    }

    function getSelectedUsers(page) {
        return page.main.find("[data-select-user]:checked").map(function () { return $(this).data("select-user"); }).get();
    }

    function getDialogMultiCheckValues(dialog, fieldname, fallback) {
        const field = dialog.get_field(fieldname);
        if (field && typeof field.get_checked_options === "function") return field.get_checked_options();
        if (field && field.$wrapper) {
            const checked = field.$wrapper.find("input:checked").map(function () { return $(this).val(); }).get();
            if (checked.length) return checked;
        }
        return Array.isArray(fallback) ? fallback : [];
    }

    function exportActiveTab() {
        const data = STATE.data || {};
        const exporters = {
            users: data.users || [],
            roles: data.roles || [],
            menu: data.menu_access || [],
            matrix: (data.permission_matrix || {}).rows || [],
            audit: data.audit_log || [],
        };
        const rows = exporters[STATE.activeTab] || [];
        if (!rows.length) {
            frappe.show_alert({ message: __("Nothing to export in this tab."), indicator: "orange" });
            return;
        }
        const columns = Object.keys(rows[0]).filter((key) => typeof rows[0][key] !== "object");
        const csvRows = [columns.join(","), ...rows.map((row) => columns.map((key) => csvCell(row[key])).join(","))];
        const blob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8;" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = `access-command-center-${STATE.activeTab}.csv`;
        link.click();
        URL.revokeObjectURL(link.href);
    }

    function csvCell(value) {
        const raw = String(value == null ? "" : value);
        const safe = /^[=+\-@]/.test(raw) ? `'${raw}` : raw;
        const text = safe.replace(/"/g, '""');
        return /[",\n]/.test(text) ? `"${text}"` : text;
    }

    function stickySaveBarMarkup() {
        const dirty = Object.keys(STATE.matrixDraft).length;
        if (!dirty) return "";
        return `<div class="acc-save-bar"><div><strong>${dirty}</strong> ${__("unsaved permission change(s)")}<span>${__("Review before applying to prevent accidental access changes.")}</span></div><button class="acc-btn acc-btn-ghost" data-clear-draft>${__("Discard")}</button><button class="acc-btn acc-btn-primary" data-review-save>${__("Review Changes")}</button></div>`;
    }

    function badge(text, color) { return `<span class="acc-badge ${color || "gray"}">${escapeHtml(text || "")}</span>`; }
    function groupBySection(items) { return items.reduce((acc, item) => { const section = item.section || __("Other"); (acc[section] = acc[section] || []).push(item); return acc; }, {}); }
    function userColumnHidden(key) { return STATE.hiddenUserColumns.includes(key) ? "acc-hidden-col" : ""; }
    function roleChip(role) { return `<span class="acc-role-chip">${escapeHtml(role || __("No Role"))}</span>`; }
    function sourceBadge(source, label) {
        const text = label || (source === "mixed" ? __("Base + Role") : source === "direct" ? __("Role") : source === "base" ? __("Base") : __("None"));
        const color = source === "mixed" ? "violet" : source === "direct" ? "blue" : source === "base" ? "green" : "gray";
        return badge(text, color);
    }
    function accessBadgeColor(level) { return level === "Admin Level" ? "red" : level === "High Access" ? "amber" : level === "No Access" ? "gray" : "blue"; }
    function labelPermission(field) { return escapeHtml(__(field.replace("_", " ").replace(/^./, (letter) => letter.toUpperCase()))); }
    function tableEmpty(title, subtitle) { return `<tr><td colspan="24">${emptyState(title, subtitle, ICONS.search)}</td></tr>`; }
    function emptyMini(text) { return `<div class="acc-empty-inline">${escapeHtml(text)}</div>`; }
    function emptyState(title, subtitle, icon) { return `<div class="acc-empty-state"><div>${icon || ICONS.search}</div><h3>${escapeHtml(title)}</h3><p>${escapeHtml(subtitle)}</p></div>`; }
    function formatNumber(value) { return Number(value || 0).toLocaleString(); }
    function formatDate(value) { if (!value) return "-"; try { return frappe.datetime.str_to_user(String(value).split(".")[0]); } catch (e) { return String(value); } }
    function initials(value) { return String(value || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "?"; }
    function escapeHtml(value) { return frappe.utils.escape_html(String(value == null ? "" : value)); }

    const ICONS = {
        shield: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l7 3v5c0 4.6-2.9 8.7-7 10-4.1-1.3-7-5.4-7-10V6l7-3z"/><path d="M9 12l2 2 4-5"/></svg>`,
        users: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
        role: `<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M8 10h8M8 14h5"/></svg>`,
        search: `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>`,
        plus: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>`,
        download: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12"/><path d="M7 10l5 5 5-5"/><path d="M5 21h14"/></svg>`,
        check: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 6L9 17l-5-5"/></svg>`,
        lock: `<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>`,
        spark: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2l1.7 6.3L20 10l-6.3 1.7L12 18l-1.7-6.3L4 10l6.3-1.7L12 2z"/></svg>`,
        warning: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l10 18H2L12 3z"/><path d="M12 9v5"/><path d="M12 18h.01"/></svg>`,
        review: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 4h16v16H4z"/><path d="M8 9h8M8 13h5M8 17h7"/></svg>`,
        activity: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12h4l3-8 4 16 3-8h4"/></svg>`,
        filter: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16M7 12h10M10 19h4"/></svg>`,
        profile: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 4h16v16H4z"/><circle cx="12" cy="10" r="3"/><path d="M7 18c1-3 9-3 10 0"/></svg>`,
        refresh: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 4v6h-6"/></svg>`,
        arrow: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14"/><path d="M13 6l6 6-6 6"/></svg>`,
    };

    function injectStyles() {
        if (document.getElementById("acc-styles")) return;
        const style = document.createElement("style");
        style.id = "acc-styles";
        style.textContent = `
            @import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;450;500;600;700&family=Geist+Mono:wght@400;500&display=swap');
            .acc-root { --canvas:#FAFBFC; --canvas-2:#F4F6F8; --surface:#FFFFFF; --surface-2:#F7F8FA; --surface-3:#F0F2F5; --ink-1000:#0A0E1A; --ink-900:#11151F; --ink-800:#1F2433; --ink-700:#2E3548; --ink-600:#495061; --ink-500:#6B7280; --ink-400:#9099A6; --ink-300:#B8BFC9; --ink-200:#DDE1E7; --ink-150:#E8EBEF; --ink-100:#EFF1F4; --ink-50:#F5F6F8; --primary-700:#3730A3; --primary-600:#4F46E5; --primary-500:#6366F1; --primary-300:#A5B4FC; --primary-100:#E0E7FF; --primary-50:#EEF2FF; --success-700:#047857; --success-600:#059669; --success-500:#10B981; --success-100:#D1FAE5; --success-50:#ECFDF5; --info-700:#0369A1; --info-600:#0284C7; --info-100:#E0F2FE; --info-50:#F0F9FF; --accent-700:#6D28D9; --accent-600:#7C3AED; --accent-500:#8B5CF6; --accent-100:#EDE9FE; --accent-50:#F5F3FF; --rose-700:#BE123C; --rose-600:#E11D48; --rose-100:#FFE4E6; --rose-50:#FFF1F2; --cyan-700:#0E7490; --cyan-500:#06B6D4; --cyan-100:#CFFAFE; --cyan-50:#ECFEFF; --font-sans:'Geist',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; --font-mono:'Geist Mono','SF Mono',Menlo,monospace; --r-lg:14px; --r-2xl:22px; --shadow-xs:0 1px 2px rgba(15,23,42,.04); --shadow-sm:0 1px 2px rgba(15,23,42,.04),0 2px 4px rgba(15,23,42,.04); --shadow-md:0 2px 4px rgba(15,23,42,.04),0 4px 12px rgba(15,23,42,.05); --shadow-lg:0 4px 8px rgba(15,23,42,.04),0 16px 32px -8px rgba(15,23,42,.08); --ease:cubic-bezier(.32,.72,0,1); --ring:0 0 0 3px rgba(99,102,241,.15); color:var(--ink-900); background:radial-gradient(circle at 20% 0%,rgba(99,102,241,.05) 0%,transparent 50%),radial-gradient(circle at 80% 30%,rgba(124,58,237,.03) 0%,transparent 50%),linear-gradient(to bottom,var(--canvas) 0%,var(--canvas-2) 100%); min-height:calc(100vh - 72px); font-family:var(--font-sans); font-feature-settings:'cv11','ss01','ss03'; -webkit-font-smoothing:antialiased; }
            .acc-root * { box-sizing:border-box; } .acc-root svg { width:16px; height:16px; fill:none; stroke:currentColor; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; } .acc-root button, .acc-root input, .acc-root select { font-family:inherit; } :where(.acc-root button) { cursor:pointer; border:0; background:none; }
            .acc-root *::-webkit-scrollbar { width:8px; height:8px; } .acc-root *::-webkit-scrollbar-thumb { background:var(--ink-200); border-radius:4px; } .acc-root *::-webkit-scrollbar-thumb:hover { background:var(--ink-300); }
            .acc-shell { max-width:1520px; margin:0 auto; padding:24px 24px 96px; display:grid; gap:18px; }
            .acc-breadcrumb { display:flex; align-items:center; gap:8px; margin-bottom:0; font-size:12px; color:var(--ink-500); font-family:var(--font-mono); } .acc-breadcrumb a { color:var(--ink-500); text-decoration:none; } .acc-breadcrumb a:hover { color:var(--ink-800); } .acc-breadcrumb .sep { color:var(--ink-300); } .acc-breadcrumb .current { color:var(--ink-800); font-weight:500; }
            .acc-hero { position:relative; background:var(--surface); border:1px solid var(--ink-150); border-radius:var(--r-2xl); padding:28px 32px; display:grid; grid-template-columns:1fr auto; gap:32px; align-items:center; overflow:hidden; box-shadow:var(--shadow-md); }
            .acc-hero::before { content:''; position:absolute; top:0; right:0; width:60%; height:100%; background:radial-gradient(ellipse at top right,rgba(99,102,241,.06) 0%,transparent 60%); pointer-events:none; } .acc-hero::after { content:''; position:absolute; top:0; left:0; right:0; height:1px; background:linear-gradient(90deg,transparent,rgba(99,102,241,.4) 30%,rgba(124,58,237,.4) 70%,transparent); } .acc-hero-copy,.acc-hero-actions { position:relative; z-index:1; }
            .acc-eyebrow { display:inline-flex; align-items:center; gap:8px; padding:5px 12px 5px 6px; background:var(--primary-50); border:1px solid var(--primary-100); border-radius:999px; font-size:11px; font-weight:500; color:var(--primary-700); margin-bottom:14px; letter-spacing:.01em; } .acc-eyebrow span { width:22px; height:22px; border-radius:999px; background:linear-gradient(135deg,var(--primary-600),var(--accent-600)); display:flex; align-items:center; justify-content:center; color:#fff; box-shadow:0 2px 8px rgba(99,102,241,.35); } .acc-eyebrow svg { width:12px; height:12px; }
            .acc-hero h1 { margin:0 0 8px; font-size:28px; font-weight:600; line-height:1.15; letter-spacing:-.025em; color:var(--ink-1000); } .acc-hero p { margin:0 0 18px; font-size:14px; color:var(--ink-500); line-height:1.55; max-width:640px; }
            .acc-hero-meta { display:inline-flex; align-items:center; gap:10px; flex-wrap:wrap; font-size:12px; color:var(--ink-600); background:var(--surface-2); border:1px solid var(--ink-100); border-radius:10px; padding:10px 14px; } .acc-hero-meta strong { color:var(--ink-800); font-weight:500; margin-left:4px; } .acc-hero-meta strong:first-of-type { margin-left:0; } .acc-hero-meta span:not(.acc-status-dot):not(.acc-meta-divider) { color:var(--ink-500); font-family:var(--font-mono); font-size:11px; } .acc-meta-divider { width:1px; height:12px; background:var(--ink-200); }
            .acc-status-dot { width:8px; height:8px; border-radius:50%; position:relative; flex-shrink:0; display:inline-block; } .acc-status-dot.safe { background:var(--success-500); box-shadow:0 0 0 3px var(--success-100); } .acc-status-dot.safe::after { content:''; position:absolute; inset:-2px; border-radius:50%; background:var(--success-500); opacity:.4; animation:accPing 2s ease-out infinite; } @keyframes accPing { 0%{transform:scale(1);opacity:.4} 75%,100%{transform:scale(2.4);opacity:0} }
            .acc-hero-actions { display:flex; flex-direction:column; gap:12px; align-items:flex-end; } .acc-action-row { display:flex; gap:8px; }
            .acc-global-search { display:flex; align-items:center; gap:10px; width:380px; background:var(--surface); border:1px solid var(--ink-200); border-radius:12px; padding:0 14px; height:42px; box-shadow:var(--shadow-xs); transition:all .2s var(--ease); } .acc-global-search:focus-within { border-color:var(--primary-300); box-shadow:var(--ring),var(--shadow-sm); } .acc-global-search > span { color:var(--ink-400); display:flex; } .acc-global-search input { flex:1; border:0; outline:0; background:transparent; font-size:13px; color:var(--ink-900); } .acc-global-search input::placeholder { color:var(--ink-400); }
            .acc-btn { display:inline-flex; align-items:center; justify-content:center; gap:6px; padding:9px 14px; border-radius:10px; font-size:13px; font-weight:500; letter-spacing:-.005em; transition:all .2s var(--ease); border:1px solid transparent; white-space:nowrap; height:38px; } .acc-btn:focus-visible,.acc-icon-btn:focus-visible,.acc-row-action:focus-visible,.acc-filter-chip:focus-visible { outline:0; box-shadow:var(--ring); } .acc-btn svg { width:14px; height:14px; } .acc-btn.full { width:100%; }
            .acc-btn-primary { background:var(--ink-1000); color:#fff; box-shadow:inset 0 1px 0 rgba(255,255,255,.1),var(--shadow-sm); } .acc-btn-primary:hover { background:var(--ink-800); transform:translateY(-1px); box-shadow:inset 0 1px 0 rgba(255,255,255,.1),var(--shadow-md); } .acc-btn-secondary { background:var(--surface); border-color:var(--ink-200); color:var(--ink-700); } .acc-btn-secondary:hover { border-color:var(--ink-300); background:var(--surface-2); color:var(--ink-900); } .acc-btn-ghost { background:transparent; color:var(--ink-600); } .acc-btn-ghost:hover { background:var(--surface-2); color:var(--ink-900); } .acc-btn-danger { background:var(--rose-50); border-color:var(--rose-100); color:var(--rose-700); } .acc-btn-danger:hover { background:var(--rose-600); border-color:var(--rose-600); color:#fff; } .acc-btn:disabled { opacity:.45; cursor:not-allowed; transform:none; }
            .acc-kpis { display:grid; grid-template-columns:repeat(8,1fr); gap:12px; } .acc-kpi { position:relative; background:var(--surface); border:1px solid var(--ink-150); border-radius:var(--r-lg); padding:14px; display:flex; align-items:flex-start; gap:10px; cursor:pointer; transition:all .25s var(--ease); overflow:hidden; } .acc-kpi::before { content:''; position:absolute; top:0; left:0; width:100%; height:2px; transform:scaleX(0); transform-origin:left; transition:transform .3s var(--ease); } .acc-kpi:hover { border-color:var(--ink-200); transform:translateY(-2px); box-shadow:var(--shadow-md); } .acc-kpi:hover::before { transform:scaleX(1); }
            .acc-kpi-icon,.acc-card-icon { width:32px; height:32px; border-radius:8px; display:flex; align-items:center; justify-content:center; flex-shrink:0; } .acc-kpi-icon svg { width:16px; height:16px; } .acc-kpi > div:last-child { display:flex; flex-direction:column; min-width:0; flex:1; } .acc-kpi span { font-size:11px; color:var(--ink-500); font-weight:500; margin-bottom:2px; } .acc-kpi strong { font-size:22px; font-weight:600; color:var(--ink-1000); letter-spacing:-.025em; line-height:1.1; font-feature-settings:'tnum'; margin-bottom:2px; } .acc-kpi small { font-size:10px; color:var(--ink-400); line-height:1.3; }
            .acc-kpi-blue::before{background:#0EA5E9}.acc-kpi-blue .acc-kpi-icon{background:var(--info-50);color:var(--info-700);border:1px solid var(--info-100)} .acc-kpi-green::before{background:var(--success-500)}.acc-kpi-green .acc-kpi-icon{background:var(--success-50);color:var(--success-700);border:1px solid var(--success-100)} .acc-kpi-gray::before{background:var(--ink-400)}.acc-kpi-gray .acc-kpi-icon{background:var(--ink-50);color:var(--ink-600);border:1px solid var(--ink-100)} .acc-kpi-indigo::before{background:var(--primary-500)}.acc-kpi-indigo .acc-kpi-icon{background:var(--primary-50);color:var(--primary-700);border:1px solid var(--primary-100)} .acc-kpi-violet::before{background:var(--accent-500)}.acc-kpi-violet .acc-kpi-icon{background:var(--accent-50);color:var(--accent-700);border:1px solid var(--accent-100)} .acc-kpi-amber::before{background:var(--cyan-500)}.acc-kpi-amber .acc-kpi-icon{background:var(--cyan-50);color:var(--cyan-700);border:1px solid var(--cyan-100)} .acc-kpi-red::before{background:var(--rose-600)}.acc-kpi-red .acc-kpi-icon{background:var(--rose-50);color:var(--rose-700);border:1px solid var(--rose-100)}
            .acc-tabs { display:flex; gap:2px; background:var(--surface); border:1px solid var(--ink-150); border-radius:12px; padding:4px; overflow-x:auto; scrollbar-width:none; box-shadow:var(--shadow-xs); } .acc-tabs::-webkit-scrollbar { display:none; } .acc-tabs button { flex-shrink:0; padding:8px 14px; border-radius:8px; font-size:13px; font-weight:500; color:var(--ink-600); transition:all .2s var(--ease); letter-spacing:-.005em; } .acc-tabs button:hover:not(.active) { background:var(--surface-2); color:var(--ink-900); } .acc-tabs button.active { background:var(--ink-1000); color:#fff; box-shadow:var(--shadow-sm); }
            .acc-workspace { display:grid; gap:16px; align-items:start; } .acc-workspace-users { grid-template-columns:minmax(0,1fr) minmax(340px,.34fr); } .acc-workspace-focus { grid-template-columns:minmax(0,1fr); } .acc-workspace-focus .acc-center-panel { width:100%; } .acc-center-panel,.acc-panel,.acc-detail-panel { min-width:0; }
            .acc-rail-card,.acc-panel,.acc-detail-panel,.acc-access-card { background:var(--surface); border:1px solid var(--ink-150); border-radius:var(--r-lg); box-shadow:var(--shadow-sm); } .acc-rail-card { padding:14px; box-shadow:var(--shadow-xs); }
            .acc-rail-title { display:flex; align-items:center; gap:8px; font-size:11px; font-weight:600; color:var(--ink-700); text-transform:uppercase; letter-spacing:.1em; margin-bottom:12px; } .acc-rail-title span { width:22px; height:22px; border-radius:6px; background:var(--primary-50); color:var(--primary-700); display:flex; align-items:center; justify-content:center; border:1px solid var(--primary-100); } .acc-rail-title svg { width:12px; height:12px; }
            .acc-user-control-strip { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:8px; align-items:center; padding:8px 16px; background:linear-gradient(180deg,var(--surface),var(--surface-2)); border-bottom:1px solid var(--ink-100); }
            .acc-smart-filter-block,.acc-role-category-strip { display:flex; align-items:center; gap:8px; min-width:0; padding:6px 8px; background:rgba(255,255,255,.62); border:1px solid var(--ink-100); border-radius:10px; box-shadow:none; }
            .acc-role-category-strip { flex-shrink:0; }
            .acc-strip-label { display:flex; align-items:center; gap:5px; font-size:9.5px; font-weight:700; color:var(--ink-600); text-transform:uppercase; letter-spacing:.07em; white-space:nowrap; }
            .acc-strip-label span { width:18px; height:18px; border-radius:5px; background:var(--primary-50); color:var(--primary-700); display:flex; align-items:center; justify-content:center; border:1px solid var(--primary-100); }
            .acc-strip-label svg { width:10px; height:10px; }
            .acc-filter-chip-row { display:flex; flex-wrap:wrap; gap:5px; min-width:0; } .acc-filter-chip { display:inline-flex; align-items:center; gap:5px; min-height:26px; padding:3px 7px; background:var(--surface-2); border:1px solid var(--ink-150); border-radius:999px; font-size:11px; font-weight:600; color:var(--ink-600); transition:all .2s var(--ease); } .acc-filter-chip strong { min-width:18px; height:18px; padding:0 5px; display:inline-flex; align-items:center; justify-content:center; border-radius:999px; background:var(--surface); color:var(--ink-700); font-size:10px; font-feature-settings:'tnum'; border:1px solid var(--ink-100); } .acc-filter-chip:hover { border-color:var(--ink-200); color:var(--ink-900); background:var(--surface); transform:translateY(-1px); } .acc-filter-chip.active { background:var(--ink-1000); color:#fff; border-color:var(--ink-1000); } .acc-filter-chip.active strong { color:var(--ink-1000); border-color:rgba(255,255,255,.24); }
            .acc-mini-list { display:flex; flex-direction:column; gap:2px; max-height:360px; overflow-y:auto; margin:-4px; padding:4px; } .acc-mini-user { display:flex; align-items:center; gap:10px; padding:8px; border-radius:8px; background:transparent; transition:all .2s var(--ease); text-align:left; width:100%; border:1px solid transparent; color:var(--ink-900); } .acc-mini-user:hover { background:var(--surface-2); } .acc-mini-user.active { background:var(--primary-50); border-color:var(--primary-100); } .acc-mini-user > span:last-child { display:flex; flex-direction:column; min-width:0; flex:1; } .acc-mini-user strong { font-size:12px; font-weight:500; color:var(--ink-900); line-height:1.3; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; } .acc-mini-user small { font-size:11px; color:var(--ink-500); line-height:1.3; } .acc-mini-user.active strong { color:var(--primary-700); }
            .acc-avatar { width:36px; height:36px; border-radius:10px; background:linear-gradient(135deg,var(--primary-500),var(--accent-600)); display:flex; align-items:center; justify-content:center; color:#fff; font-size:13px; font-weight:600; letter-spacing:.02em; flex-shrink:0; box-shadow:var(--shadow-xs),inset 0 1px 0 rgba(255,255,255,.2); } .acc-avatar.small { width:28px; height:28px; border-radius:8px; font-size:11px; } .acc-avatar.tiny { width:24px; height:24px; border-radius:6px; font-size:10px; } .acc-mini-user:nth-child(2n) .acc-avatar,.acc-table tbody tr:nth-child(2n) .acc-avatar { background:linear-gradient(135deg,var(--info-600),var(--primary-500)); } .acc-mini-user:nth-child(3n) .acc-avatar,.acc-table tbody tr:nth-child(3n) .acc-avatar { background:linear-gradient(135deg,var(--accent-600),#EC4899); } .acc-mini-user:nth-child(4n) .acc-avatar,.acc-table tbody tr:nth-child(4n) .acc-avatar { background:linear-gradient(135deg,var(--success-500),var(--info-600)); } .acc-table tbody tr:nth-child(5n) .acc-avatar { background:linear-gradient(135deg,#06B6D4,var(--info-600)); }
            .acc-role-category-row { display:flex; gap:5px; } .acc-role-category { display:flex; align-items:center; gap:5px; min-height:26px; padding:3px 7px; background:var(--surface-2); border:1px solid var(--ink-100); border-radius:999px; margin-bottom:0; } .acc-role-category strong { font-size:12px; font-weight:700; color:var(--ink-1000); font-feature-settings:'tnum'; letter-spacing:-.02em; } .acc-role-category span { font-size:10px; color:var(--ink-500); font-weight:600; white-space:nowrap; } .acc-role-category.danger { background:var(--rose-50); border-color:var(--rose-100); } .acc-role-category.danger strong,.acc-role-category.danger span { color:var(--rose-700); }
            .acc-panel { overflow:hidden; } .acc-panel-head { display:flex; align-items:center; justify-content:space-between; padding:18px 20px; border-bottom:1px solid var(--ink-100); gap:16px; } .acc-panel-head h2 { margin:0 0 2px; font-size:16px; font-weight:600; color:var(--ink-1000); letter-spacing:-.015em; } .acc-panel-head p { margin:0; font-size:12px; color:var(--ink-500); }
            .acc-icon-btn { width:34px; height:34px; border-radius:8px; background:var(--surface); border:1px solid var(--ink-200); color:var(--ink-500); display:inline-flex; align-items:center; justify-content:center; transition:all .2s var(--ease); } .acc-icon-btn:hover { color:var(--ink-900); border-color:var(--ink-300); background:var(--surface-2); } .acc-icon-btn svg { width:14px; height:14px; }
            .acc-table-toolbar,.acc-matrix-toolbar { display:flex; align-items:center; gap:8px; padding:12px 20px; background:var(--surface-2); border-bottom:1px solid var(--ink-100); flex-wrap:wrap; } .acc-count-pill { display:inline-flex; align-items:center; gap:5px; padding:5px 10px; background:var(--surface); border:1px solid var(--ink-150); border-radius:999px; font-size:12px; color:var(--ink-600); margin-right:auto; } .acc-count-pill strong { font-weight:600; color:var(--ink-900); font-feature-settings:'tnum'; }
            .acc-table-wrap,.acc-matrix-wrap { overflow:auto; max-height:680px; overscroll-behavior:contain; } .acc-table,.acc-matrix { width:100%; border-collapse:collapse; font-size:13px; } .acc-table thead th,.acc-matrix thead th { background:var(--surface-2); color:var(--ink-500); font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:.06em; text-align:left; padding:10px 12px; border-bottom:1px solid var(--ink-100); white-space:nowrap; position:sticky; top:0; z-index:4; } .acc-table thead th:first-child { width:34px; padding-left:16px; } .acc-table thead th:last-child { text-align:right; padding-right:16px; }
            .acc-table tbody td,.acc-matrix tbody td { padding:12px 12px; border-bottom:1px solid var(--ink-100); color:var(--ink-700); vertical-align:middle; white-space:nowrap; } .acc-table tbody td:first-child { padding-left:16px; } .acc-table tbody td:last-child { text-align:right; padding-right:16px; } .acc-table tbody tr,.acc-matrix tbody tr { transition:background .15s var(--ease); cursor:pointer; background:#fff; } .acc-table tbody tr:hover,.acc-matrix tbody tr:hover { background:var(--surface-2); } .acc-table tbody tr.selected { background:var(--primary-50); } .acc-table tbody tr.selected:hover { background:var(--primary-100); } .acc-matrix tbody tr.draft { background:var(--primary-50); box-shadow:inset 3px 0 0 var(--primary-600); } .acc-table tbody tr:last-child td { border-bottom:0; } .sticky-col { position:sticky; left:0; z-index:3; background:inherit; box-shadow:1px 0 0 var(--ink-100); } .acc-hidden-col { display:none; }
            .acc-table input[type='checkbox'],.acc-role-toggle input[type='checkbox'] { appearance:none; width:16px; height:16px; border:1.5px solid var(--ink-300); border-radius:4px; background:var(--surface); cursor:pointer; position:relative; transition:all .15s var(--ease); flex-shrink:0; } .acc-table input[type='checkbox']:hover,.acc-role-toggle input[type='checkbox']:hover { border-color:var(--primary-500); } .acc-table input[type='checkbox']:checked,.acc-role-toggle input[type='checkbox']:checked { background:var(--primary-600); border-color:var(--primary-600); } .acc-table input[type='checkbox']:checked::after,.acc-role-toggle input[type='checkbox']:checked::after { content:''; position:absolute; left:4px; top:1px; width:5px; height:9px; border:solid #fff; border-width:0 2px 2px 0; transform:rotate(45deg); }
            .acc-user-cell { display:flex; align-items:center; gap:10px; } .acc-user-cell > div { display:flex; flex-direction:column; min-width:0; } .acc-user-cell strong { font-size:13px; font-weight:500; color:var(--ink-900); line-height:1.3; } .acc-user-cell small { font-size:11px; color:var(--ink-500); line-height:1.3; }
            .acc-badge { display:inline-flex; align-items:center; gap:5px; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:600; letter-spacing:.01em; white-space:nowrap; border:1px solid; min-height:0; text-transform:none; } .acc-badge::before { content:''; width:5px; height:5px; border-radius:50%; flex-shrink:0; } .acc-badge.green { background:var(--success-50); color:var(--success-700); border-color:var(--success-100); } .acc-badge.green::before { background:var(--success-600); } .acc-badge.blue,.acc-badge.system { background:var(--info-50); color:var(--info-700); border-color:var(--info-100); } .acc-badge.blue::before,.acc-badge.system::before { background:var(--info-600); } .acc-badge.red,.acc-badge.danger { background:var(--rose-50); color:var(--rose-700); border-color:var(--rose-100); } .acc-badge.red::before,.acc-badge.danger::before { background:var(--rose-600); } .acc-badge.amber,.acc-badge.warning { background:var(--cyan-50); color:var(--cyan-700); border-color:var(--cyan-100); } .acc-badge.amber::before,.acc-badge.warning::before { background:var(--cyan-500); } .acc-badge.gray { background:var(--ink-50); color:var(--ink-600); border-color:var(--ink-100); } .acc-badge.gray::before { background:var(--ink-400); } .acc-badge.violet,.acc-badge.custom { background:var(--accent-50); color:var(--accent-700); border-color:var(--accent-100); } .acc-badge.violet::before,.acc-badge.custom::before { background:var(--accent-600); }
            .acc-role-chip { display:inline-flex; align-items:center; padding:4px 9px; background:var(--accent-50); color:var(--accent-700); border:1px solid var(--accent-100); border-radius:6px; font-size:11px; font-weight:500; max-width:160px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; } .acc-row-action { padding:5px 10px; background:var(--surface); border:1px solid var(--ink-200); border-radius:7px; font-size:12px; font-weight:500; color:var(--ink-700); transition:all .2s var(--ease); min-height:0; } .acc-row-action:hover { background:var(--ink-1000); border-color:var(--ink-1000); color:#fff; } .acc-row-action.danger { color:var(--rose-700); border-color:var(--rose-100); background:var(--rose-50); } .acc-row-action.danger:hover { color:#fff; background:var(--rose-600); border-color:var(--rose-600); } .acc-row-action:disabled { opacity:.45; cursor:not-allowed; }
            .acc-detail-panel { position:sticky; top:20px; max-height:calc(100vh - 40px); overflow-y:auto; } .acc-detail-head { display:flex; align-items:center; gap:12px; padding:18px; background:radial-gradient(ellipse at top right,rgba(99,102,241,.08) 0%,transparent 70%),var(--surface); border-bottom:1px solid var(--ink-100); } .acc-detail-head .acc-avatar { width:42px; height:42px; border-radius:12px; font-size:14px; } .acc-detail-head h2 { margin:0; font-size:16px; font-weight:600; color:var(--ink-1000); letter-spacing:-.015em; line-height:1.2; } .acc-detail-head p { margin:2px 0 0; font-size:11px; color:var(--ink-500); font-family:var(--font-mono); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:210px; }
            .acc-detail-status-row { display:flex; flex-wrap:wrap; gap:6px; padding:12px 18px; background:var(--surface-2); border-bottom:1px solid var(--ink-100); } .acc-warning-card,.acc-inline-warning { display:flex; align-items:flex-start; gap:10px; margin:12px 18px 0; padding:11px 12px; background:var(--rose-50); border:1px solid var(--rose-100); border-radius:10px; font-size:12px; color:var(--rose-700); line-height:1.4; } .acc-warning-card svg,.acc-inline-warning svg { width:14px; height:14px; flex-shrink:0; margin-top:1px; } .acc-warning-card + .acc-warning-card { margin-top:8px; background:var(--primary-50); border-color:var(--primary-100); color:var(--primary-700); } .acc-inline-warning { margin:0 18px 18px; }
            .acc-detail-section { padding:16px 18px; border-top:1px solid var(--ink-100); display:block; } .acc-detail-section:first-of-type { border-top:0; } .acc-detail-section h3 { margin:0 0 12px; font-size:11px; font-weight:600; color:var(--ink-700); text-transform:uppercase; letter-spacing:.1em; }
            .acc-field { display:flex; flex-direction:column; gap:6px; margin-bottom:12px; } .acc-field span { font-size:11px; font-weight:500; color:var(--ink-600); text-transform:none; letter-spacing:0; } .acc-field input,.acc-field select,.acc-matrix-toolbar select,.acc-matrix-toolbar input { padding:9px 11px; border:1px solid var(--ink-200); border-radius:8px; font-size:13px; color:var(--ink-900); background:var(--surface); transition:all .2s var(--ease); outline:0; min-height:38px; font-weight:400; } .acc-field input:focus,.acc-field select:focus,.acc-matrix-toolbar select:focus,.acc-matrix-toolbar input:focus { border-color:var(--primary-500); box-shadow:var(--ring); } .acc-field select,.acc-matrix-toolbar select { appearance:none; background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236B7280' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'/></svg>"); background-repeat:no-repeat; background-position:right 11px center; padding-right:32px; cursor:pointer; }
            .acc-toggle-line { display:flex; align-items:center; gap:10px; padding:10px 12px; background:var(--surface-2); border:1px solid var(--ink-100); border-radius:8px; font-size:13px; color:var(--ink-700); cursor:pointer; margin-bottom:12px; transition:all .2s var(--ease); } .acc-toggle-line input[type='checkbox'] { appearance:none; width:32px; height:18px; background:var(--ink-200); border-radius:999px; position:relative; cursor:pointer; transition:background .2s var(--ease); flex-shrink:0; } .acc-toggle-line input[type='checkbox']::after { content:''; position:absolute; top:2px; left:2px; width:14px; height:14px; background:#fff; border-radius:50%; transition:transform .2s var(--ease); box-shadow:var(--shadow-xs); } .acc-toggle-line input[type='checkbox']:checked { background:var(--success-500); } .acc-toggle-line input[type='checkbox']:checked::after { transform:translateX(14px); }
            .acc-role-toggle-list { display:flex; flex-direction:column; gap:4px; max-height:360px; overflow-y:auto; margin:0 -4px 12px; padding:4px; border:1px solid var(--ink-100); border-radius:10px; background:var(--surface-2); } .acc-role-toggle { display:grid; grid-template-columns:16px 1fr auto; align-items:center; gap:10px; padding:7px 10px; border-radius:7px; background:transparent; cursor:pointer; transition:all .15s var(--ease); font-size:12px; color:var(--ink-700); border:1px solid transparent; } .acc-role-toggle:hover { background:var(--surface); border-color:var(--ink-100); } .acc-role-toggle.selected { background:var(--surface); border-color:var(--primary-100); } .acc-role-toggle.selected span:first-of-type { color:var(--primary-700); font-weight:500; } .acc-role-toggle .acc-badge { font-size:9px; padding:2px 5px; }
            .acc-company-row { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:6px; align-items:center; } .acc-company-row .acc-role-toggle { margin:0; align-items:flex-start; } .acc-company-row.is-default .acc-role-toggle { border-color:var(--success-100); background:var(--success-50); } .acc-company-business-types { grid-column:2 / 4; display:flex; gap:4px; flex-wrap:wrap; margin-top:4px; } .acc-company-business-types span { display:inline-flex; border-radius:999px; background:var(--primary-50); color:var(--primary-700); border:1px solid var(--primary-100); padding:2px 6px; font-size:9px; font-weight:800; } .acc-default-company-btn { min-height:31px; border:1px solid var(--ink-200); border-radius:8px; background:var(--surface); color:var(--ink-600); padding:0 9px; font-size:10px; font-weight:700; cursor:pointer; white-space:nowrap; } .acc-default-company-btn:hover { border-color:var(--primary-100); color:var(--primary-700); background:var(--primary-50); } .acc-default-company-btn.active { border-color:var(--success-100); color:var(--success-700); background:var(--success-50); cursor:default; }
            .acc-card-grid { padding:16px; display:grid; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); gap:12px; } .acc-role-card { border-radius:14px; padding:14px; background:var(--surface); border:1px solid var(--ink-150); box-shadow:var(--shadow-xs); } .acc-role-card.elevated { border-color:var(--cyan-100); background:var(--cyan-50); } .acc-role-card.critical { border-color:var(--rose-100); background:var(--rose-50); } .acc-card-top { display:flex; justify-content:space-between; gap:10px; align-items:start; } .acc-role-badges { display:flex; flex-wrap:wrap; gap:5px; justify-content:flex-end; } .acc-role-card h3 { margin:12px 0 5px; color:var(--ink-1000); font-size:15px; font-weight:600; } .acc-role-card p,.acc-access-card p { margin:0 0 12px; color:var(--ink-500); font-size:12px; line-height:1.45; } .acc-role-capability-row { display:flex; flex-wrap:wrap; gap:5px; margin:0 0 12px; } .acc-card-metrics { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin:12px 0; } .acc-card-metrics span { border-radius:10px; padding:10px; background:var(--surface-2); color:var(--ink-500); font-size:10px; font-weight:500; text-transform:uppercase; } .acc-card-metrics strong { display:block; color:var(--ink-1000); font-size:18px; } .acc-role-card-actions { display:grid; gap:8px; } .acc-role-actions { display:grid; grid-template-columns:1fr 1fr; gap:8px; } .acc-text-link { display:inline-flex; align-items:center; justify-content:center; min-height:34px; border-radius:8px; color:var(--ink-600); background:var(--surface-2); border:1px solid var(--ink-100); font-size:12px; font-weight:500; text-decoration:none; } .acc-text-link:hover { color:var(--ink-900); border-color:var(--ink-200); text-decoration:none; }
            .acc-matrix-toolbar label { display:flex; flex-direction:column; gap:5px; color:var(--ink-600); font-size:11px; font-weight:500; } .acc-source-legend { display:inline-flex; gap:6px; align-items:center; color:var(--ink-500); font-size:11px; font-weight:500; } .acc-source-legend b { width:9px; height:9px; border-radius:999px; display:inline-block; } .acc-source-legend .custom { background:var(--accent-600); } .acc-source-legend .standard { background:var(--primary-600); } .acc-source-legend .none { background:var(--ink-400); } .acc-doctype-cell strong,.acc-doctype-cell small { display:block; } .acc-doctype-cell small { color:var(--ink-500); font-size:10px; font-weight:500; margin-top:2px; }
            .acc-matrix-search-status { display:inline-flex; align-items:center; gap:6px; min-width:86px; min-height:26px; padding:4px 8px; border-radius:999px; color:var(--ink-500); font-size:11px; font-weight:700; } .acc-matrix-search-status:empty { display:none; } .acc-matrix-search-status.active { background:var(--primary-50); color:var(--primary-700); border:1px solid var(--primary-100); } .acc-matrix-search-status b { width:12px; height:12px; border-radius:999px; border:2px solid var(--primary-100); border-top-color:var(--primary-600); animation:accSpin .75s linear infinite; } @keyframes accSpin { to { transform:rotate(360deg); } }
            .acc-matrix-group-row td { background:linear-gradient(180deg,var(--surface),var(--surface-2)); border-top:1px solid var(--ink-150); } .acc-matrix-group-row .sticky-col { box-shadow:1px 0 0 var(--ink-100), inset 3px 0 0 var(--primary-500); } .acc-matrix-group-row small { display:block; margin-top:4px; color:var(--ink-500); font-size:10px; font-weight:600; } .acc-group-toggle { display:inline-flex; align-items:center; gap:9px; color:var(--ink-1000); text-align:left; } .acc-group-toggle span { width:20px; height:20px; display:inline-flex; align-items:center; justify-content:center; border-radius:6px; background:var(--primary-50); color:var(--primary-700); border:1px solid var(--primary-100); font-size:14px; font-weight:700; line-height:1; } .acc-group-toggle strong { font-size:13px; font-weight:700; letter-spacing:-.01em; } .acc-matrix-child-row td { background:#fff; } .acc-matrix-child-row .sticky-col { padding-left:30px; } .acc-matrix-child-row .acc-doctype-cell strong::before { content:'>'; color:var(--ink-400); margin-right:8px; font-weight:600; } .acc-group-perm-toggle input:indeterminate + span { background:linear-gradient(90deg,var(--primary-600) 0 50%,var(--ink-200) 50% 100%); } .acc-group-perm-toggle input:indeterminate + span::after { transform:translateX(7px); }
            .acc-report-group-row td { background:linear-gradient(180deg,var(--surface),var(--surface-2)); border-top:1px solid var(--ink-150); } .acc-report-group-row small { display:block; margin-top:4px; color:var(--ink-500); font-size:10px; font-weight:600; } .acc-report-table tbody .acc-report-group-row:hover { background:var(--surface-2); }
            .acc-perm-toggle.disabled { opacity:.42; cursor:not-allowed; } .acc-perm-toggle.disabled input,.acc-perm-toggle.disabled span { cursor:not-allowed; }
            .acc-perm-toggle { position:relative; display:inline-flex; width:38px; height:24px; align-items:center; justify-content:center; cursor:pointer; } .acc-perm-toggle input { position:absolute; inset:2px; width:34px; height:20px; margin:0; opacity:0; z-index:1; cursor:pointer; } .acc-perm-toggle span { width:34px; height:20px; border-radius:999px; background:var(--ink-200); position:relative; transition:background .18s var(--ease); } .acc-perm-toggle span::after { content:''; position:absolute; width:16px; height:16px; left:2px; top:2px; border-radius:999px; background:#fff; box-shadow:0 2px 6px rgba(15,23,42,.2); transition:transform .18s var(--ease); } .acc-perm-toggle input:checked + span { background:var(--primary-600); } .acc-perm-toggle input:checked + span::after { transform:translateX(14px); }
            .acc-page-report-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; padding:14px; background:var(--surface-2); } .acc-access-card { padding:14px; box-shadow:none; } .acc-access-card h3 { margin:0 0 4px; color:var(--ink-1000); font-size:14px; font-weight:600; } .acc-access-row { display:flex; justify-content:space-between; gap:10px; align-items:center; border-top:1px solid var(--ink-100); padding:9px 0; } .acc-access-row strong,.acc-access-row small { display:block; } .acc-access-row small { color:var(--ink-500); font-size:10px; }
            .acc-menu-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:12px; padding:14px; background:var(--surface-2); } .acc-menu-section-card { min-width:0; } .acc-menu-toggle-list { max-height:420px; } .acc-role-toggle strong,.acc-role-toggle small { display:block; } .acc-role-toggle small { margin-top:2px; color:var(--ink-500); font-size:10px; font-weight:500; line-height:1.25; }
            .acc-policy-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; padding:16px; background:var(--surface-2); } .acc-policy-card { padding:18px; border:1px solid var(--ink-150); border-radius:16px; background:var(--surface); box-shadow:var(--shadow-xs); } .acc-policy-card h3 { margin:0 0 9px; color:var(--ink-1000); font-size:15px; font-weight:650; letter-spacing:-.015em; } .acc-policy-card p { margin:0; color:var(--ink-500); font-size:13px; line-height:1.55; } .acc-policy-wide { grid-column:1 / -1; } .acc-policy-hero-card { background:radial-gradient(circle at 100% 0%,rgba(99,102,241,.14),transparent 44%),linear-gradient(135deg,var(--ink-1000),var(--ink-800)); color:#fff; border-color:rgba(255,255,255,.12); box-shadow:var(--shadow-md); } .acc-policy-hero-card h3 { color:#fff; font-size:20px; } .acc-policy-hero-card p { color:rgba(255,255,255,.76); max-width:780px; } .acc-policy-kicker { display:inline-flex; margin-bottom:10px; padding:4px 9px; border-radius:999px; background:rgba(255,255,255,.1); color:#fff; border:1px solid rgba(255,255,255,.16); font-size:10px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
            .acc-policy-steps { display:grid; gap:8px; } .acc-policy-step { display:grid; grid-template-columns:28px minmax(0,1fr); gap:10px; padding:10px; border:1px solid var(--ink-100); border-radius:12px; background:var(--surface-2); } .acc-policy-step > strong { width:28px; height:28px; display:inline-flex; align-items:center; justify-content:center; border-radius:999px; background:var(--primary-50); color:var(--primary-700); border:1px solid var(--primary-100); font-size:12px; } .acc-policy-step b,.acc-policy-examples b,.acc-policy-cheats b { display:block; margin-bottom:3px; color:var(--ink-900); font-size:12px; font-weight:650; } .acc-policy-step small,.acc-policy-examples small,.acc-policy-cheats small { display:block; color:var(--ink-500); font-size:11px; line-height:1.42; } .acc-policy-step em { display:block; margin-top:6px; color:var(--primary-700); font-size:10.5px; font-style:normal; font-weight:600; }
            .acc-policy-note { display:flex; gap:9px; align-items:flex-start; margin-top:14px; padding:11px 12px; border-radius:12px; background:var(--primary-50); border:1px solid var(--primary-100); color:var(--primary-700); font-size:12px; line-height:1.45; } .acc-policy-note svg { flex-shrink:0; width:15px; height:15px; margin-top:1px; } .acc-policy-examples { display:grid; gap:8px; } .acc-policy-examples > div { padding:10px 11px; border-left:3px solid var(--primary-500); background:var(--surface-2); border-radius:0 10px 10px 0; }
            .acc-policy-checklist { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; } .acc-policy-checklist span { display:flex; gap:8px; align-items:flex-start; padding:10px 11px; border:1px solid var(--ink-100); border-radius:12px; background:var(--surface); color:var(--ink-700); font-size:12px; line-height:1.4; } .acc-policy-checklist svg { flex-shrink:0; width:14px; height:14px; margin-top:1px; color:var(--rose-600); } .acc-policy-cheat-card { background:linear-gradient(180deg,var(--surface),var(--primary-50)); } .acc-policy-cheats { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:10px; } .acc-policy-cheats span { padding:12px; border-radius:12px; background:rgba(255,255,255,.74); border:1px solid var(--primary-100); }
            .acc-empty-inline { padding:16px; background:var(--surface-2); border:1px dashed var(--ink-200); border-radius:10px; text-align:center; font-size:12px; color:var(--ink-500); font-style:italic; }
            .acc-audit-list { display:grid; gap:10px; padding:16px; } .acc-audit-item { display:grid; grid-template-columns:22px minmax(0,1fr) auto; gap:10px; border-radius:14px; padding:12px; background:var(--surface); border:1px solid var(--ink-150); } .acc-audit-dot { width:10px; height:10px; border-radius:999px; background:var(--primary-600); margin-top:5px; box-shadow:0 0 0 5px rgba(99,102,241,.12); } .acc-audit-item.risk-high .acc-audit-dot { background:var(--rose-600); box-shadow:0 0 0 5px rgba(225,29,72,.12); } .acc-audit-item strong { color:var(--ink-900); } .acc-audit-item p { margin:3px 0; color:var(--ink-500); font-size:12px; } .acc-audit-item small { color:var(--ink-400); font-weight:500; }
            .acc-empty-state { min-height:170px; display:grid; place-items:center; text-align:center; padding:28px; color:var(--ink-500); } .acc-empty-state svg { width:34px; height:34px; color:var(--ink-400); } .acc-empty-state h3 { margin:10px 0 4px; color:var(--ink-900); font-weight:600; } .acc-empty-state p { margin:0; max-width:420px; line-height:1.5; } .acc-error-state { min-height:420px; border-radius:var(--r-2xl); background:var(--surface); border:1px solid var(--ink-150); display:grid; place-items:center; text-align:center; padding:36px; box-shadow:var(--shadow-md); } .acc-error-state h2 { margin:12px 0 6px; color:var(--ink-1000); font-weight:600; } .acc-error-state p { color:var(--ink-500); }
            .acc-save-bar { position:fixed; left:50%; bottom:18px; transform:translateX(-50%); z-index:20; width:min(760px,calc(100vw - 32px)); border-radius:18px; padding:12px; display:flex; align-items:center; gap:10px; justify-content:space-between; background:rgba(10,14,26,.96); color:#fff; border:1px solid rgba(255,255,255,.14); box-shadow:0 24px 70px rgba(15,23,42,.34); } .acc-save-bar span { display:block; color:#DDE1E7; font-size:11px; margin-top:2px; } .acc-save-bar .acc-btn-ghost { color:#fff; } .acc-save-bar .acc-btn-ghost:hover { background:rgba(255,255,255,.12); color:#fff; }
            .acc-shimmer,.acc-shimmer-card { position:relative; overflow:hidden; background:var(--ink-150); border-radius:14px; } .acc-shimmer::after,.acc-shimmer-card::after { content:''; position:absolute; inset:0; transform:translateX(-100%); background:linear-gradient(90deg,transparent,rgba(255,255,255,.72),transparent); animation:accShimmer 1.4s infinite; } .h-lg { height:58px; width:55%; } .h-sm { height:20px; width:80%; margin-top:16px; } .h-xl { height:460px; } .acc-skeleton-panel { padding:22px; }
            @keyframes accShimmer { 100% { transform:translateX(100%); } }
            @media (prefers-reduced-motion: reduce) { .acc-root *, .acc-root *::before, .acc-root *::after { animation-duration:.01ms !important; transition-duration:.01ms !important; } }
            @media (max-width:1280px) { .acc-kpis { grid-template-columns:repeat(4,1fr); } .acc-workspace-users { grid-template-columns:minmax(0,1fr) minmax(320px,.38fr); gap:14px; } .acc-user-control-strip { grid-template-columns:1fr; } .acc-role-category-strip { width:100%; } .acc-shell { padding-left:18px; padding-right:18px; } }
            @media (max-width:1080px) { .acc-workspace-users { grid-template-columns:minmax(0,1fr); } .acc-detail-panel { position:static; max-height:none; } }
            @media (max-width:900px) { .acc-shell { padding:20px 16px 96px; } .acc-hero { grid-template-columns:1fr; padding:22px; } .acc-hero-actions { align-items:stretch; } .acc-global-search { width:100%; } .acc-kpis { grid-template-columns:repeat(2,1fr); } .acc-workspace { grid-template-columns:1fr; } .acc-smart-filter-block,.acc-role-category-strip { align-items:flex-start; flex-direction:column; } .acc-page-report-grid,.acc-policy-grid,.acc-policy-checklist,.acc-policy-cheats { grid-template-columns:1fr; } }
            @media (max-width:640px) { .acc-kpis { grid-template-columns:1fr; } .acc-action-row { flex-direction:column; } .acc-save-bar { align-items:stretch; flex-direction:column; } .acc-policy-grid { padding:12px; } }
        `;
        document.head.appendChild(style);
    }
})();
