(function () {
    const PAGE_NAME = "stock-planning-settings-control";
    const API = "orderlift.orderlift_logistics.page.stock_planning_settings_control.stock_planning_settings_control";
    const CHECK_FIELDS = new Set([
        "enabled",
        "partial_pick_list",
        "rely_on_incoming_stock",
        "auto_create_material_request",
        "auto_submit_material_request",
    ]);
    const INT_FIELDS = new Set([
        "reservation_buffer_days",
        "incoming_safety_days",
        "procurement_safety_days",
        "default_procurement_delay_days",
        "alert_days_before_action",
    ]);

    const STATE = {
        companies: [],
        selectedCompany: "",
        canEdit: false,
        settings: {},
        loading: false,
    };

    frappe.pages[PAGE_NAME].on_page_load = function (wrapper) {
        const page = frappe.ui.make_app_page({
            parent: wrapper,
            title: __("Stock Planning Settings"),
            single_column: true,
        });
        wrapper.page = page;
        page.main.addClass("spsc-root");
        injectStyles();
        page.set_primary_action(__("Save Settings"), () => saveSettings(page), "check");
        render(page);
        loadData(page);
    };

    frappe.pages[PAGE_NAME].on_page_show = function (wrapper) {
        if (wrapper.page) loadData(wrapper.page, STATE.selectedCompany);
    };

    async function call(method, args = {}) {
        const response = await frappe.call({ method: `${API}.${method}`, args, freeze: true });
        return response.message || {};
    }

    async function loadData(page, company) {
        STATE.loading = true;
        render(page);
        try {
            const payload = await call("get_page_data", { company: company || "" });
            STATE.companies = payload.companies || [];
            STATE.selectedCompany = payload.selected_company || "";
            STATE.canEdit = Boolean(payload.can_edit);
            STATE.settings = payload.settings || {};
        } catch (error) {
            frappe.msgprint(error.message || __("Could not load stock planning settings."));
        } finally {
            STATE.loading = false;
            render(page);
        }
    }

    async function saveSettings(page) {
        if (!STATE.canEdit) return frappe.msgprint(__("You do not have permission to edit these settings."));
        if (!STATE.selectedCompany) return frappe.msgprint(__("Select a company first."));
        const values = collectValues(page);
        try {
            const result = await call("save_settings", {
                company: STATE.selectedCompany,
                values: JSON.stringify(values),
            });
            STATE.settings = result.settings || values;
            frappe.show_alert({ message: __("Stock planning settings saved"), indicator: "green" });
            render(page);
        } catch (error) {
            frappe.msgprint(error.message || __("Could not save stock planning settings."));
        }
    }

    function render(page) {
        page.main.html(`
            <main class="spsc-shell">
                <nav class="spsc-breadcrumb">
                    <a href="/desk/home-page?sidebar=Main+Dashboard">${__("Warehouse & Stock")}</a>
                    <span>/</span><strong>${__("Stock Planning Settings")}</strong>
                </nav>
                <section class="spsc-hero">
                    <div>
                        <span>${__("Confirmed-order protection")}</span>
                        <h1>${__("Control when stock becomes protected")}</h1>
                        <p>${__("Set the company policy that turns submitted Sales Order demand into Pick List actions. Planning is disabled by default for every company until a manager enables it here.")}</p>
                    </div>
                    <div class="spsc-hero-card">
                        <small>${__("Selected company")}</small>
                        <select data-company ${STATE.loading ? "disabled" : ""}>
                            ${STATE.companies.map((company) => option(company, company, STATE.selectedCompany)).join("")}
                        </select>
                        <strong class="${Number(STATE.settings.enabled || 0) ? "is-on" : "is-off"}">${Number(STATE.settings.enabled || 0) ? __("Planning enabled") : __("Planning disabled")}</strong>
                    </div>
                </section>

                ${STATE.loading ? loadingCard() : renderSettings()}
            </main>
        `);
        bindEvents(page);
    }

    function renderSettings() {
        if (!STATE.selectedCompany) {
            return `<section class="spsc-card"><div class="spsc-empty">${__("No allowed companies were found for your user.")}</div></section>`;
        }
        return `
            <section class="spsc-grid">
                <div class="spsc-card spsc-form-card">
                    <div class="spsc-card-head">
                        <div><h2>${__("Policy")}</h2><p>${__("These controls are saved on the company-scoped Stock Planning Settings record.")}</p></div>
                        <button class="btn btn-primary" data-action="save" ${STATE.canEdit ? "" : "disabled"}>${__("Save Settings")}</button>
                    </div>
                    ${field("enabled", "check", __("Enable Stock Planning"), __("When off, the scheduler keeps settings safe but takes no planning actions."))}
                    <div class="spsc-two-col">
                        ${field("reservation_mode", "select", __("When Stock Protection Is Due"), __("Planner action when confirmed demand reaches its protection date."), ["Manual Alert Only", "Create Draft Pick List", "Create and Submit Pick List"])}
                        ${field("partial_pick_list", "check", __("Allow Partial Pick Lists"), __("Protect what is physically available and keep the balance open."))}
                        ${field("reservation_buffer_days", "number", __("Delivery Preparation Buffer (Days)"), __("Visibility buffer before delivery for final reservation risk."))}
                        ${field("protected_stock_floor_mode", "select", __("Protected Stock Floor"), __("Preserve a warehouse floor before creating Pick Lists."), ["None", "Item Reorder Level"])}
                    </div>
                    <h3>${__("Incoming Stock")}</h3>
                    <div class="spsc-two-col">
                        ${field("rely_on_incoming_stock", "check", __("Rely on Incoming Stock"), __("Let demand wait for incoming stock only when the ETA is safely before delivery."))}
                        ${field("incoming_safety_days", "number", __("Incoming Safety Delay (Days)"), __("Incoming must arrive by Delivery Date minus this delay."))}
                    </div>
                    <h3>${__("Procurement")}</h3>
                    <div class="spsc-two-col">
                        ${field("procurement_safety_days", "number", __("Procurement Safety Delay (Days)"), __("Internal review and approval time before supplier lead time starts."))}
                        ${field("default_procurement_delay_days", "number", __("Fallback Procurement Delay (Days)"), __("Used only when the Item lead time is empty."))}
                        ${field("auto_create_material_request", "check", __("Create Material Requests Automatically"), __("Create Purchase Material Requests for uncovered confirmed demand."))}
                        ${field("auto_submit_material_request", "check", __("Submit Automatic Material Requests"), __("Requires automatic Material Request creation."))}
                    </div>
                    <h3>${__("Alerts")}</h3>
                    ${field("alert_days_before_action", "number", __("Upcoming Action Alert (Days)"), __("Show upcoming planning actions this many days before they are due."))}
                </div>
                <aside class="spsc-card spsc-examples">
                    <h2>${__("How It Works")}</h2>
                    ${example(__("Protection date"), __("Delivery 30 Oct, item lead time 45 days, procurement safety 7 days: Stock Protection Date is 8 Sep. On 8 Sep, the planner protects available stock with a Pick List or raises procurement risk."), true)}
                    ${example(__("Reliable incoming"), __("Delivery 30 Oct and Incoming Safety Delay 15 days means incoming is safe only by 15 Oct. A Purchase Order arriving 10 Oct can cover demand, and that incoming quantity is allocated once."))}
                    ${example(__("Unsafe incoming"), __("A Purchase Order arriving 25 Oct for the same 30 Oct delivery is too late. The order is treated as uncovered because it misses the 15-day safety window."))}
                    ${example(__("Backup check"), __("If incoming is planned for 10 Oct and safety is 15 days, the backup check is 25 Sep. If the stock is not received by then, the planner creates a Pick List from physical stock if available."))}
                    ${example(__("Partial backup"), __("Demand is 10, incoming is late, and only 4 are physically available. With partial Pick Lists enabled, the planner protects 4 and keeps 6 open against incoming/procurement."))}
                    ${example(__("Competing orders"), __("Two submitted Sales Orders need the same incoming batch. Quantity is assigned first to the earliest delivery date, then the oldest submitted order; later orders cannot reuse already allocated incoming."))}
                    <div class="spsc-note">${__("Planner never creates Stock Reservation Entries directly. Reservation happens only when a Pick List is submitted through the existing Pick List reservation hook.")}</div>
                </aside>
            </section>
        `;
    }

    function field(fieldname, type, label, help, options) {
        const value = STATE.settings[fieldname];
        const disabled = STATE.canEdit ? "" : "disabled";
        let control = "";
        if (type === "check") {
            control = `<label class="spsc-switch"><input type="checkbox" data-field="${fieldname}" ${Number(value || 0) ? "checked" : ""} ${disabled}><span></span></label>`;
        } else if (type === "select") {
            control = `<select data-field="${fieldname}" ${disabled}>${(options || []).map((item) => option(item, __(item), value)).join("")}</select>`;
        } else {
            control = `<input type="number" min="0" step="1" data-field="${fieldname}" value="${escapeAttr(value || 0)}" ${disabled}>`;
        }
        return `<label class="spsc-field"><span>${label}</span>${control}<small>${help}</small></label>`;
    }

    function example(title, body, open) {
        return `<details class="spsc-example" ${open ? "open" : ""}><summary>${title}</summary><p>${body}</p></details>`;
    }

    function loadingCard() {
        return `<section class="spsc-card"><div class="spsc-empty">${__("Loading settings...")}</div></section>`;
    }

    function bindEvents(page) {
        page.main.off("change.spsc click.spsc");
        page.main.on("change.spsc", "[data-company]", function () {
            loadData(page, $(this).val());
        });
        page.main.on("click.spsc", "[data-action='save']", () => saveSettings(page));
    }

    function collectValues(page) {
        const values = {};
        page.main.find("[data-field]").each(function () {
            const fieldname = $(this).data("field");
            if (CHECK_FIELDS.has(fieldname)) values[fieldname] = this.checked ? 1 : 0;
            else if (INT_FIELDS.has(fieldname)) values[fieldname] = Number($(this).val() || 0);
            else values[fieldname] = $(this).val();
        });
        return values;
    }

    function option(value, label, selected) {
        return `<option value="${escapeAttr(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(label)}</option>`;
    }

    function escapeHtml(value) {
        return String(value == null ? "" : value).replace(/[&<>"']/g, (char) => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;",
        }[char]));
    }

    function escapeAttr(value) {
        return escapeHtml(value);
    }

    function injectStyles() {
        if (document.getElementById("spsc-styles")) return;
        const style = document.createElement("style");
        style.id = "spsc-styles";
        style.textContent = `
            .spsc-root { background: #f6f7fb; }
            .spsc-shell { max-width: 1240px; margin: 0 auto; padding: 22px; color: #182033; }
            .spsc-breadcrumb { display: flex; gap: 8px; align-items: center; color: #64748b; margin-bottom: 16px; }
            .spsc-breadcrumb a { color: #475569; text-decoration: none; }
            .spsc-hero { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 20px; padding: 28px; border-radius: 22px; background: linear-gradient(135deg, #0f172a, #2563eb); color: white; box-shadow: 0 18px 45px rgba(15, 23, 42, .20); }
            .spsc-hero span { display: inline-block; margin-bottom: 8px; color: #bfdbfe; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; font-size: 12px; }
            .spsc-hero h1 { margin: 0 0 10px; color: white; font-size: 34px; line-height: 1.05; }
            .spsc-hero p { max-width: 740px; margin: 0; color: #dbeafe; font-size: 15px; line-height: 1.6; }
            .spsc-hero-card { align-self: stretch; display: flex; flex-direction: column; justify-content: center; gap: 10px; padding: 18px; border: 1px solid rgba(255,255,255,.20); border-radius: 18px; background: rgba(255,255,255,.12); }
            .spsc-hero-card small { color: #dbeafe; }
            .spsc-hero-card select, .spsc-field select, .spsc-field input[type='number'] { width: 100%; height: 38px; border-radius: 10px; border: 1px solid #d7deea; padding: 0 12px; background: white; color: #182033; }
            .spsc-hero-card strong { display: inline-flex; align-items: center; width: fit-content; padding: 5px 10px; border-radius: 999px; font-size: 12px; }
            .spsc-hero-card strong.is-on { background: #dcfce7; color: #166534; }
            .spsc-hero-card strong.is-off { background: #fee2e2; color: #991b1b; }
            .spsc-grid { display: grid; grid-template-columns: minmax(0, 1fr) 380px; gap: 20px; margin-top: 20px; }
            .spsc-card { background: white; border: 1px solid #e5eaf2; border-radius: 18px; box-shadow: 0 12px 28px rgba(15, 23, 42, .06); }
            .spsc-form-card { padding: 22px; }
            .spsc-card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
            .spsc-card h2 { margin: 0 0 4px; font-size: 20px; }
            .spsc-card h3 { margin: 22px 0 12px; font-size: 15px; color: #334155; }
            .spsc-card p { margin: 0; color: #64748b; }
            .spsc-two-col { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
            .spsc-field { display: block; padding: 14px; border: 1px solid #eef2f7; border-radius: 14px; background: #fbfcff; }
            .spsc-field > span { display: block; margin-bottom: 8px; font-weight: 700; color: #1e293b; }
            .spsc-field small { display: block; margin-top: 8px; min-height: 34px; color: #64748b; line-height: 1.45; }
            .spsc-switch { position: relative; display: inline-block; width: 52px; height: 30px; }
            .spsc-switch input { display: none; }
            .spsc-switch span { position: absolute; inset: 0; border-radius: 999px; background: #cbd5e1; transition: .18s; }
            .spsc-switch span:before { content: ""; position: absolute; width: 24px; height: 24px; left: 3px; top: 3px; border-radius: 50%; background: white; box-shadow: 0 2px 8px rgba(15,23,42,.22); transition: .18s; }
            .spsc-switch input:checked + span { background: #2563eb; }
            .spsc-switch input:checked + span:before { transform: translateX(22px); }
            .spsc-examples { padding: 20px; height: fit-content; position: sticky; top: 74px; }
            .spsc-example { border: 1px solid #e5eaf2; border-radius: 12px; margin-top: 10px; background: #fbfcff; }
            .spsc-example summary { cursor: pointer; padding: 12px 14px; font-weight: 700; color: #1e293b; }
            .spsc-example p { padding: 0 14px 14px; line-height: 1.55; }
            .spsc-note { margin-top: 14px; padding: 12px; border-radius: 12px; background: #eff6ff; color: #1d4ed8; line-height: 1.45; }
            .spsc-empty { padding: 34px; color: #64748b; text-align: center; }
            @media (max-width: 900px) { .spsc-hero, .spsc-grid, .spsc-two-col { grid-template-columns: 1fr; } .spsc-shell { padding: 14px; } .spsc-hero h1 { font-size: 28px; } .spsc-examples { position: static; } }
        `;
        document.head.appendChild(style);
    }
})();
