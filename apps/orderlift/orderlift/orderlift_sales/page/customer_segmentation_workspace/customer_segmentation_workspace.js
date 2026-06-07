(function () {
    const STATE = {
        loading: false,
        saving: false,
        companies: [],
        currentCompany: "",
        activeCompany: "",
        engines: {},
        results: [],
    };

    const METHOD = "orderlift.orderlift_sales.doctype.customer_segmentation_engine.customer_segmentation_engine";
    const VARIABLES = ["", "Revenue (12 months)", "RFM Score", "Customer Age (Days)", "Total Orders"];
    const OPERATORS = ["", "\u2265 (greater or equal)", "> (greater than)", "\u2264 (less or equal)", "< (less than)", "= (equals)", "\u2260 (not equal)"];
    const LINK_FIELDS = {
        business_type_filter: "CRM Business Type",
        crm_segment_filter: "CRM Segment",
    };
    const TABLE_LINK_FIELDS = {
        segmentation_rules: { designated_segment: "Pricing Tier" },
        tier_modifiers: { business_type: "CRM Business Type", crm_segment: "CRM Segment", tier: "Pricing Tier" },
        zone_modifiers: { territory: "Territory" },
    };

    frappe.pages["customer-segmentation-workspace"].on_page_load = function (wrapper) {
        const page = frappe.ui.make_app_page({
            parent: wrapper,
            title: __("Customer Segmentation Engine"),
            single_column: true,
        });
        wrapper.page = page;
        page.main.addClass("cse-root");
        injectStyles();
        applyHeader(page);
        loadWorkspace(page);
    };

    frappe.pages["customer-segmentation-workspace"].on_page_show = function (wrapper) {
        if (!wrapper.page) return;
        applyHeader(wrapper.page);
    };

    function applyHeader(page) {
        page.set_title(__("Customer Segmentation Engine"));
        page.clear_actions_menu();
        page.set_primary_action(__("Save"), () => saveActive(page));
        page.add_action_item(__("Calculate Segments"), () => calculateActive(page));
        page.add_action_item(__("Apply Segments"), () => applyActive(page));
        setTimeout(() => {
            if (!frappe.breadcrumbs) return;
            frappe.breadcrumbs.clear();
            frappe.breadcrumbs.append_breadcrumb_element("/desk/home-page?sidebar=Main+Dashboard", __("Policies"), "title-text");
            frappe.breadcrumbs.append_breadcrumb_element("", __("Customer Segmentation"), "title-text");
            frappe.breadcrumbs.toggle(true);
        }, 0);
    }

    async function loadWorkspace(page) {
        STATE.loading = true;
        render(page);
        try {
            const res = await frappe.call({ method: `${METHOD}.get_segmentation_workspace` });
            const data = res.message || {};
            STATE.companies = data.companies || [];
            STATE.currentCompany = data.current_company || "";
            STATE.engines = {};
            (data.tabs || []).forEach((engine) => {
                if (engine.company) STATE.engines[engine.company] = engine;
            });
            STATE.activeCompany = STATE.currentCompany || STATE.companies[0] || "";
            STATE.results = [];
        } catch (error) {
            console.error("Customer Segmentation Engine load failed", error);
            frappe.msgprint(__("Unable to load segmentation workspace."));
        } finally {
            STATE.loading = false;
            render(page);
        }
    }

    function render(page) {
        const engine = activeEngine();
        page.main.html(`
            <div class="cse-shell">
                <section class="cse-hero">
                    <div>
                        <div class="cse-kicker">${__("Company Pricing Governance")}</div>
                        <h2>${__("Customer Segmentation Engine")}</h2>
                        <p>${__("Manage one segmentation policy per company, including dynamic tier assignment and global tier or territory price modifiers.")}</p>
                    </div>
                    <div class="cse-hero-actions">
                        <button class="btn btn-default" data-action="calculate">${__("Calculate")}</button>
                        <button class="btn btn-primary" data-action="save">${__("Save")}</button>
                    </div>
                </section>
                ${STATE.loading ? skeleton() : workspace(engine)}
            </div>
        `);
        bind(page);
    }

    function workspace(engine) {
        if (!STATE.companies.length) {
            return `<div class="cse-empty">${__("No company access is configured for this user.")}</div>`;
        }
        if (!engine) {
            return `<div class="cse-empty">${__("Select a company to manage segmentation.")}</div>${companyTabs()}`;
        }
        return `
            ${companyTabs()}
            <section class="cse-card cse-config">
                <div class="cse-grid two">
                    ${inputField("engine_name", __("Engine Name"), engine.engine_name)}
                    ${checkboxField("is_active", __("Active"), engine.is_active)}
                    ${linkField("business_type_filter", __("Business Type Filter"), engine.business_type_filter, "CRM Business Type")}
                    ${linkField("crm_segment_filter", __("CRM Segment Filter"), engine.crm_segment_filter, "CRM Segment")}
                </div>
                ${textareaField("description", __("Notes"), engine.description)}
            </section>
            ${rulesTable(engine)}
            ${tierModifiersTable(engine)}
            ${zoneModifiersTable(engine)}
            ${resultsPanel()}
        `;
    }

    function companyTabs() {
        return `<section class="cse-tabs">${STATE.companies.map((company) => `
            <button class="cse-tab ${company === STATE.activeCompany ? "active" : ""}" data-company-tab="${escapeAttr(company)}">
                ${escapeHtml(company)}
            </button>
        `).join("")}</section>`;
    }

    function inputField(field, label, value, placeholder) {
        return `
            <label class="cse-field">
                <span>${escapeHtml(label)}</span>
                <input class="form-control" data-field="${field}" value="${escapeAttr(value || "")}" placeholder="${escapeAttr(placeholder || "")}">
            </label>
        `;
    }

    function linkField(field, label, value, options) {
        return `
            <div class="cse-field">
                <span>${escapeHtml(label)}</span>
                <div class="cse-link-control" data-link-field="${escapeAttr(field)}" data-link-options="${escapeAttr(options)}" data-link-value="${escapeAttr(value || "")}"></div>
            </div>
        `;
    }

    function textareaField(field, label, value) {
        return `
            <label class="cse-field cse-wide">
                <span>${escapeHtml(label)}</span>
                <textarea class="form-control" rows="2" data-field="${field}">${escapeHtml(value || "")}</textarea>
            </label>
        `;
    }

    function checkboxField(field, label, value) {
        return `
            <label class="cse-check">
                <input type="checkbox" data-field="${field}" ${Number(value) ? "checked" : ""}>
                <span>${escapeHtml(label)}</span>
            </label>
        `;
    }

    function rulesTable(engine) {
        const rows = engine.segmentation_rules || [];
        return editableTable({
            title: __("Segmentation Rules"),
            table: "segmentation_rules",
            empty: __("No segmentation rules configured."),
            columns: [
                { field: "designated_segment", label: __("Assign Tier"), width: "160px", type: "link", options: "Pricing Tier" },
                { field: "priority", label: __("Priority"), width: "80px", type: "number" },
                { field: "is_default", label: __("Catch-All"), width: "80px", type: "check" },
                { field: "is_active", label: __("Active"), width: "80px", type: "check" },
                { field: "variable_1", label: __("If"), type: "select", options: VARIABLES },
                { field: "operator_1", label: __("Is"), type: "select", options: OPERATORS },
                { field: "value_1", label: __("Value"), type: "number" },
                { field: "connector", label: __("And/Or"), type: "select", options: ["", "AND", "OR"] },
                { field: "variable_2", label: __("If 2"), type: "select", options: VARIABLES },
                { field: "operator_2", label: __("Is 2"), type: "select", options: OPERATORS },
                { field: "value_2", label: __("Value 2"), type: "number" },
            ],
            rows,
        });
    }

    function tierModifiersTable(engine) {
        const rows = engine.tier_modifiers || [];
        return editableTable({
            title: __("Global Tier Modifiers"),
            table: "tier_modifiers",
            empty: __("No global tier modifiers configured."),
            columns: [
                { field: "business_type", label: __("Business Type"), type: "link", options: "CRM Business Type" },
                { field: "crm_segment", label: __("CRM Segment"), type: "link", options: "CRM Segment" },
                { field: "tier", label: __("Tier"), type: "link", options: "Pricing Tier" },
                { field: "modifier_amount", label: __("Amount"), type: "number" },
                { field: "modifier_type", label: __("Type"), type: "select", options: ["Fixed", "Percentage"] },
                { field: "is_active", label: __("Active"), type: "check", width: "80px" },
            ],
            rows,
        });
    }

    function zoneModifiersTable(engine) {
        const rows = engine.zone_modifiers || [];
        return editableTable({
            title: __("Global Territory Modifiers"),
            table: "zone_modifiers",
            empty: __("No territory modifiers configured."),
            columns: [
                { field: "territory", label: __("Territory"), type: "link", options: "Territory" },
                { field: "modifier_amount", label: __("Amount"), type: "number" },
                { field: "modifier_type", label: __("Type"), type: "select", options: ["Fixed", "Percentage"] },
                { field: "is_active", label: __("Active"), type: "check", width: "80px" },
            ],
            rows,
        });
    }

    function editableTable({ title, table, columns, rows, empty }) {
        return `
            <section class="cse-card">
                <div class="cse-card-head">
                    <h3>${escapeHtml(title)}</h3>
                    <button class="btn btn-default btn-xs" data-add-row="${table}">${__("Add Row")}</button>
                </div>
                <div class="cse-table-wrap">
                    <table class="table table-bordered cse-table">
                        <thead><tr>${columns.map((col) => `<th style="width:${escapeAttr(col.width || "auto")}">${escapeHtml(col.label)}</th>`).join("")}<th></th></tr></thead>
                        <tbody>
                            ${rows.length ? rows.map((row, index) => tableRow(table, columns, row, index)).join("") : `<tr><td colspan="${columns.length + 1}" class="text-muted">${escapeHtml(empty)}</td></tr>`}
                        </tbody>
                    </table>
                </div>
            </section>
        `;
    }

    function tableRow(table, columns, row, index) {
        return `<tr data-table-row="${table}" data-index="${index}">
            ${columns.map((col) => `<td>${cellControl(table, index, col, row[col.field])}</td>`).join("")}
            <td><button class="btn btn-danger btn-xs" data-delete-row="${table}" data-index="${index}">${__("Remove")}</button></td>
        </tr>`;
    }

    function cellControl(table, index, col, value) {
        if (col.type === "check") {
            return `<input type="checkbox" data-row-field="${col.field}" data-table="${table}" data-index="${index}" ${Number(value) ? "checked" : ""}>`;
        }
        if (col.type === "select") {
            return `<select class="form-control input-xs" data-row-field="${col.field}" data-table="${table}" data-index="${index}">
                ${(col.options || []).map((option) => `<option value="${escapeAttr(option)}" ${option === value ? "selected" : ""}>${escapeHtml(option)}</option>`).join("")}
            </select>`;
        }
        if (col.type === "link") {
            return `<div class="cse-link-control cse-link-control-table" data-row-link-field="${escapeAttr(col.field)}" data-table="${escapeAttr(table)}" data-index="${index}" data-link-options="${escapeAttr(col.options)}" data-link-value="${escapeAttr(value || "")}"></div>`;
        }
        return `<input class="form-control input-xs" ${col.type === "number" ? "type=\"number\" step=\"any\"" : ""} data-row-field="${col.field}" data-table="${table}" data-index="${index}" value="${escapeAttr(displayValue(value))}">`;
    }

    function resultsPanel() {
        if (!STATE.results.length) return "";
        return `
            <section class="cse-card">
                <div class="cse-card-head"><h3>${__("Latest Calculation")}</h3></div>
                <div class="cse-results">
                    ${STATE.results.slice(0, 25).map((row) => `
                        <div class="cse-result-row">
                            <strong>${escapeHtml(row.customer_name || row.customer || "")}</strong>
                            <span>${escapeHtml(row.assigned_segment || __("No tier"))}</span>
                            <small>${escapeHtml(row.confidence || "")}</small>
                        </div>
                    `).join("")}
                </div>
            </section>
        `;
    }

    function skeleton() {
        return `<div class="cse-card cse-empty">${__("Loading segmentation workspace...")}</div>`;
    }

    function bind(page) {
        const root = page.main;
        root.find("[data-company-tab]").on("click", function () {
            STATE.activeCompany = $(this).attr("data-company-tab") || "";
            STATE.results = [];
            render(page);
        });
        root.find("[data-action='save']").on("click", () => saveActive(page));
        root.find("[data-action='calculate']").on("click", () => calculateActive(page));
        root.find("[data-field]").on("input change", function () {
            const engine = activeEngine();
            if (!engine) return;
            const field = $(this).attr("data-field");
            engine[field] = this.type === "checkbox" ? (this.checked ? 1 : 0) : $(this).val();
        });
        root.find("[data-row-field]").on("input change", function () {
            const engine = activeEngine();
            if (!engine) return;
            const table = $(this).attr("data-table");
            const field = $(this).attr("data-row-field");
            const index = Number($(this).attr("data-index"));
            const row = (engine[table] || [])[index];
            if (!row) return;
            row[field] = this.type === "checkbox" ? (this.checked ? 1 : 0) : $(this).val();
        });
        root.find("[data-add-row]").on("click", function () {
            const engine = activeEngine();
            const table = $(this).attr("data-add-row");
            if (!engine || !table) return;
            engine[table] = engine[table] || [];
            engine[table].push(defaultRow(table, engine[table].length));
            render(page);
        });
        root.find("[data-delete-row]").on("click", function () {
            const engine = activeEngine();
            const table = $(this).attr("data-delete-row");
            const index = Number($(this).attr("data-index"));
            if (!engine || !engine[table]) return;
            engine[table].splice(index, 1);
            render(page);
        });
        initLinkControls(page);
    }

    function initLinkControls(page) {
        const root = page.main;
        root.find("[data-link-field]").each(function () {
            const $wrap = $(this);
            const field = $wrap.attr("data-link-field");
            const options = $wrap.attr("data-link-options") || LINK_FIELDS[field];
            if (!field || !options) return;
            makeLinkControl($wrap, {
                fieldname: field,
                options,
                value: $wrap.attr("data-link-value") || "",
                on_change: (value) => {
                    const engine = activeEngine();
                    if (engine) engine[field] = value || "";
                },
            });
        });
        root.find("[data-row-link-field]").each(function () {
            const $wrap = $(this);
            const table = $wrap.attr("data-table");
            const field = $wrap.attr("data-row-link-field");
            const index = Number($wrap.attr("data-index"));
            const options = $wrap.attr("data-link-options") || ((TABLE_LINK_FIELDS[table] || {})[field]);
            if (!table || !field || !options) return;
            makeLinkControl($wrap, {
                fieldname: `${table}_${index}_${field}`,
                options,
                value: $wrap.attr("data-link-value") || "",
                on_change: (value) => {
                    const engine = activeEngine();
                    const row = engine && (engine[table] || [])[index];
                    if (row) row[field] = value || "";
                },
            });
        });
    }

    function makeLinkControl($wrap, { fieldname, options, value, on_change }) {
        const control = frappe.ui.form.make_control({
            parent: $wrap,
            df: {
                fieldname,
                fieldtype: "Link",
                options,
                only_select: true,
                get_query: () => linkQuery(options),
                onchange: () => on_change(control.get_value()),
            },
            render_input: true,
        });
        control.refresh();
        control.set_value(value || "");
        control.$input.on("change", () => on_change(control.get_value()));
        return control;
    }

    function linkQuery(options) {
        if (["CRM Business Type", "CRM Segment", "Pricing Tier"].includes(options)) {
            return { filters: { is_active: 1 } };
        }
        return {};
    }

    function defaultRow(table, index) {
        if (table === "segmentation_rules") {
            return { designated_segment: "", priority: (index + 1) * 10, is_default: 0, is_active: 1, variable_1: "", operator_1: "", value_1: 0, connector: "", variable_2: "", operator_2: "", value_2: 0 };
        }
        if (table === "tier_modifiers") {
            return { business_type: "", crm_segment: "", tier: "", modifier_amount: 0, modifier_type: "Fixed", is_active: 1 };
        }
        return { territory: "", modifier_amount: 0, modifier_type: "Fixed", is_active: 1 };
    }

    async function saveActive(page) {
        const company = STATE.activeCompany;
        const engine = activeEngine();
        if (!company || !engine) return;
        STATE.saving = true;
        try {
            const res = await frappe.call({
                method: `${METHOD}.save_company_segmentation`,
                args: { company, payload: JSON.stringify(engine) },
            });
            STATE.engines[company] = (res.message || {}).engine || engine;
            frappe.show_alert({ message: __("Segmentation engine saved."), indicator: "green" });
            render(page);
        } finally {
            STATE.saving = false;
        }
    }

    async function calculateActive(page) {
        const company = STATE.activeCompany;
        if (!company) return;
        const res = await frappe.call({ method: `${METHOD}.calculate_company_segmentation`, args: { company } });
        STATE.results = (res.message || {}).results || [];
        if ((res.message || {}).engine) STATE.engines[company] = res.message.engine;
        render(page);
    }

    async function applyActive(page) {
        const company = STATE.activeCompany;
        if (!company) return;
        frappe.confirm(__("Apply calculated tiers to matching customers for {0}?", [company]), async () => {
            const res = await frappe.call({ method: `${METHOD}.apply_company_segmentation`, args: { company } });
            STATE.results = (res.message || {}).results || [];
            if ((res.message || {}).engine) STATE.engines[company] = res.message.engine;
            render(page);
        });
    }

    function activeEngine() {
        return STATE.engines[STATE.activeCompany] || null;
    }

    function displayValue(value) {
        return value == null ? "" : value;
    }

    function escapeHtml(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function escapeAttr(value) {
        return escapeHtml(value);
    }

    function injectStyles() {
        if (document.getElementById("customer-segmentation-engine-style")) return;
        const style = document.createElement("style");
        style.id = "customer-segmentation-engine-style";
        style.textContent = `
            .cse-root { background: #f6f7fb; }
            .cse-shell { max-width: 1320px; margin: 0 auto; padding: 18px; }
            .cse-hero { display: flex; justify-content: space-between; gap: 16px; align-items: center; padding: 22px; border-radius: 16px; background: linear-gradient(135deg, #111827, #1e3a8a); color: white; margin-bottom: 14px; }
            .cse-hero h2 { margin: 4px 0 6px; color: white; font-size: 24px; }
            .cse-hero p { margin: 0; max-width: 760px; color: rgba(255,255,255,.78); }
            .cse-kicker { text-transform: uppercase; letter-spacing: .08em; font-size: 11px; color: #bfdbfe; }
            .cse-hero-actions { display: flex; gap: 8px; }
            .cse-tabs { display: flex; gap: 8px; overflow-x: auto; margin: 14px 0; }
            .cse-tab { border: 1px solid #dbe2ef; background: white; border-radius: 999px; padding: 8px 14px; color: #334155; }
            .cse-tab.active { background: #1d4ed8; color: white; border-color: #1d4ed8; }
            .cse-card { background: white; border: 1px solid #e5e7eb; border-radius: 14px; box-shadow: 0 8px 24px rgba(15, 23, 42, .06); padding: 16px; margin-bottom: 14px; overflow: visible; }
            .cse-card-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; }
            .cse-card-head h3 { margin: 0; font-size: 16px; font-weight: 700; color: #111827; }
            .cse-grid.two { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
            .cse-field span { display: block; font-weight: 600; color: #374151; margin-bottom: 6px; }
            .cse-field.cse-wide { display: block; margin-top: 12px; }
            .cse-check { display: flex; align-items: center; gap: 8px; padding-top: 28px; font-weight: 600; }
            .cse-table-wrap { overflow: visible; }
            .cse-table { min-width: 900px; margin-bottom: 0; }
            .cse-table th { background: #f8fafc; color: #475569; font-size: 12px; white-space: nowrap; }
            .cse-table td { vertical-align: middle; }
            .cse-link-control .awesomplete ul { z-index: 10000; min-width: 220px; max-height: 260px; overflow-y: auto; }
            .cse-results { display: grid; gap: 8px; }
            .cse-result-row { display: grid; grid-template-columns: 1fr auto auto; gap: 10px; align-items: center; padding: 10px 12px; border: 1px solid #e5e7eb; border-radius: 10px; }
            .cse-result-row span { color: #1d4ed8; font-weight: 700; }
            .cse-empty { color: #64748b; text-align: center; padding: 32px; }
            @media (max-width: 768px) { .cse-shell { padding: 10px; } .cse-hero { display: block; } .cse-hero-actions { margin-top: 14px; } .cse-grid.two { grid-template-columns: 1fr; } }
        `;
        document.head.appendChild(style);
    }
})();
