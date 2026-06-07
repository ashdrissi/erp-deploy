(function () {
    const STATE = {
        data: { columns: [], kpis: {}, filters: {} },
        filters: { search: "", company: "All", flow_scope: "All", shipping_responsibility: "All" },
        dragged: null,
        collapsedColumns: {},
        columnCollapseTouched: {},
    };

    frappe.pages["logistics-pipeline"].on_page_load = function (wrapper) {
        const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Logistics Pipeline"), single_column: true });
        wrapper.page = page;
        page.main.addClass("olp-logistics-root");
        injectStyles();
        render(page);
        load(page);
    };

    frappe.pages["logistics-pipeline"].on_page_show = function (wrapper) {
        if (wrapper.page) load(wrapper.page);
    };

    async function load(page) {
        const res = await frappe.call({
            method: "orderlift.orderlift_logistics.page.logistics_pipeline.logistics_pipeline.get_logistics_pipeline_data",
            args: STATE.filters,
        });
        STATE.data = res.message || { columns: [], kpis: {}, filters: {} };
        STATE.filters.company = STATE.data.selected_company || STATE.filters.company;
        applyDefaultCollapsedColumns();
        render(page);
    }

    function render(page) {
        const data = STATE.data || {};
        const kpis = data.kpis || {};
        page.main.html(`
            <div class="llp-shell">
                <nav class="llp-breadcrumb" aria-label="${__("Breadcrumb")}">
                    <a href="/desk/home-page?sidebar=Main+Dashboard">${__("Logistics")}</a>
                    <span class="sep">/</span>
                    <span class="current">${__("Logistics Pipeline")}</span>
                </nav>
                <section class="llp-hero">
                    <div class="llp-hero-copy">
                        <div class="llp-eyebrow">${__("Operations Control Panel")}</div>
                        <h1>${__("Logistics Pipeline")}</h1>
                        <p>${__("Shipment Plans are managed here as the logistics planning pipeline, with route, capacity, timing, and risk context on every card.")}</p>
                    </div>
                    <div class="llp-hero-side">
                        <div class="llp-kpis">
                            ${kpi(kpis.primary_label, kpis.primary_value)}
                            ${kpi(kpis.secondary_label, kpis.secondary_value)}
                            ${kpi(kpis.tertiary_label, kpis.tertiary_value)}
                            ${kpi(kpis.quaternary_label, kpis.quaternary_value)}
                        </div>
                        <button class="llp-create" data-create-plan="1">${__("Create Shipment Plan")}</button>
                    </div>
                </section>
                <section class="llp-filters">
                    <input id="llp-search" type="search" placeholder="${__("Search container, route, zone")}" value="${frappe.utils.escape_html(STATE.filters.search || "")}" />
                    ${select("company", __("Company"), (data.filters || {}).companies || [])}
                    ${select("flow_scope", __("Flow"), (data.filters || {}).flow_scopes || [])}
                    ${select("shipping_responsibility", __("Responsibility"), (data.filters || {}).shipping_responsibilities || [])}
                    <button class="llp-refresh" data-refresh="1">${__("Refresh")}</button>
                </section>
                <section class="llp-board">
                    ${(data.columns || []).map(columnMarkup).join("") || `<div class="llp-empty">${__("No shipment plans found.")}</div>`}
                </section>
            </div>
        `);
        bind(page);
    }

    function bind(page) {
        page.main.find("#llp-search").on("change", function () {
            STATE.filters.search = String($(this).val() || "").trim();
            load(page);
        });
        page.main.find("[data-filter]").on("change", function () {
            STATE.filters[$(this).data("filter")] = $(this).val();
            load(page);
        });
        page.main.find("[data-refresh]").on("click", function () { load(page); });
        page.main.find("[data-toggle-column]").on("click", function (event) {
            event.preventDefault();
            event.stopPropagation();
            const columnName = String($(this).attr("data-toggle-column") || "");
            if (!columnName) return;
            STATE.columnCollapseTouched[columnName] = true;
            STATE.collapsedColumns[columnName] = !STATE.collapsedColumns[columnName];
            render(page);
        });
        page.main.find("[data-create-plan]").on("click", createForecastPlan);
        page.main.find(".llp-card").on("dragstart", function (event) {
            STATE.dragged = { name: $(this).data("name"), stage: $(this).data("stage") };
            event.originalEvent.dataTransfer.effectAllowed = "move";
        });
        page.main.find(".llp-card").on("dragend", function () { STATE.dragged = null; });
        page.main.find(".llp-column").on("dragover", function (event) {
            if (!STATE.dragged) return;
            event.preventDefault();
            $(this).addClass("is-over");
        });
        page.main.find(".llp-column").on("dragleave", function () { $(this).removeClass("is-over"); });
        page.main.find(".llp-column").on("drop", async function (event) {
            event.preventDefault();
            $(this).removeClass("is-over");
            const targetStage = $(this).data("stage");
            if (!STATE.dragged || !targetStage || targetStage === STATE.dragged.stage) return;
            const planName = STATE.dragged.name;
            const targetColumn = findColumn(targetStage);
            if (targetColumn && targetColumn.confirmation_message) {
                showStageMoveConfirmationPopup({
                    documentLabel: __("Shipment Plan"),
                    record: planName,
                    stage: targetStage,
                    message: targetColumn.confirmation_message,
                    onConfirm: () => moveCard(page, planName, targetStage),
                });
                STATE.dragged = null;
                return;
            }
            await moveCard(page, planName, targetStage);
        });
        page.main.find("[data-open]").on("click", function () {
            frappe.set_route("planning", $(this).data("open"));
        });
    }

    function findColumn(stage) {
        return ((STATE.data || {}).columns || []).find((column) => column.name === stage) || null;
    }

    function applyDefaultCollapsedColumns() {
        for (const column of (STATE.data || {}).columns || []) {
            if (!column || !column.name || STATE.columnCollapseTouched[column.name]) continue;
            STATE.collapsedColumns[column.name] = Boolean(column.auto_collapse);
        }
    }

    function showStageMoveConfirmationPopup(details) {
        closeStageMoveConfirmationPopup();
        const modal = $(stageMoveConfirmationMarkup(details));
        $(document.body).append(modal);

        modal.find("[data-stage-error-close]").on("click", closeStageMoveConfirmationPopup);
        modal.find("[data-stage-confirm]").on("click", async function () {
            closeStageMoveConfirmationPopup();
            await details.onConfirm();
        });
        modal.on("mousedown", function (event) {
            if ($(event.target).is(".olp-stage-error-modal")) closeStageMoveConfirmationPopup();
        });
        $(document).on("keydown.llp-stage-confirm", function (event) {
            if (event.key === "Escape") closeStageMoveConfirmationPopup();
        });

        window.requestAnimationFrame(() => modal.addClass("is-visible"));
        modal.find("[data-stage-confirm]").first().trigger("focus");
    }

    function closeStageMoveConfirmationPopup() {
        $(document).off("keydown.llp-stage-confirm");
        $(".olp-stage-error-modal").remove();
    }

    function stageMoveConfirmationMarkup(details) {
        const documentLabel = details.documentLabel || __("Document");
        return `
            <div class="olp-stage-error-modal" role="dialog" aria-modal="true" aria-labelledby="olp-stage-error-title">
                <section class="olp-stage-error-card">
                    <button type="button" class="olp-stage-error-close" data-stage-error-close="1" aria-label="${frappe.utils.escape_html(__("Close"))}">x</button>
                    <div class="olp-stage-error-hero">
                        <div class="olp-stage-error-mark">!</div>
                        <div>
                            <span>${frappe.utils.escape_html(__("Confirm status move"))}</span>
                            <h2 id="olp-stage-error-title">${frappe.utils.escape_html(__("Move this {0}?", [documentLabel]))}</h2>
                            <p>${frappe.utils.escape_html(__("This status has a confirmation message configured in Status Control."))}</p>
                        </div>
                    </div>
                    <div class="olp-stage-error-route">
                        <span>${frappe.utils.escape_html(details.record || "-")}</span>
                        <i></i>
                        <strong>${frappe.utils.escape_html(details.stage || "-")}</strong>
                    </div>
                    <div class="olp-stage-error-body">
                        <span>${frappe.utils.escape_html(__("Before moving"))}</span>
                        <p>${frappe.utils.escape_html(details.message || __("Confirm this status change."))}</p>
                    </div>
                    <div class="olp-stage-error-actions">
                        <button type="button" class="is-secondary" data-stage-error-close="1">${frappe.utils.escape_html(__("Keep card here"))}</button>
                        <button type="button" data-stage-confirm="1">${frappe.utils.escape_html(__("Move to {0}", [details.stage || __("status")]))}</button>
                    </div>
                </section>
            </div>
        `;
    }

    function createForecastPlan() {
        const defaults = {};
        if (STATE.filters.company && STATE.filters.company !== "All") defaults.company = STATE.filters.company;
        if (STATE.filters.flow_scope && STATE.filters.flow_scope !== "All") defaults.flow_scope = STATE.filters.flow_scope;
        if (STATE.filters.shipping_responsibility && STATE.filters.shipping_responsibility !== "All") defaults.shipping_responsibility = STATE.filters.shipping_responsibility;
        openCreateForecastPlanModal(defaults);
    }

    async function openCreateForecastPlanModal(defaults) {
        const dialog = new frappe.ui.Dialog({
            title: __("New Shipment Plan"),
            fields: getCreateForecastPlanFields(defaults || {}),
            primary_action_label: __("Create & Open Planner"),
            primary_action(values) {
                createAndOpenForecastPlan(values, dialog);
            },
        });
        dialog.show();
    }

    function getCreateForecastPlanFields(defaults) {
        return [
            { fieldname: "plan_label", label: __("Plan Label"), fieldtype: "Data", reqd: 1, default: defaults.plan_label || "", description: __("Example: Bangkok Export Apr W3") },
            { fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", reqd: 1, default: defaults.company || "" },
            { fieldname: "column_break_1", fieldtype: "Column Break" },
            {
                fieldname: "container_profile",
                label: __("Container Profile"),
                fieldtype: "Link",
                options: "Container Profile",
                default: defaults.container_profile || "",
                get_query: () => ({ filters: { is_active: 1 } }),
                description: __("Type to search existing profiles or create a new Container Profile."),
            },
            { fieldname: "section_route", fieldtype: "Section Break", label: __("Route") },
            { fieldname: "route_origin", label: __("Origin"), fieldtype: "Data", default: defaults.route_origin || "", description: __("Example: Bangkok, Shanghai") },
            { fieldname: "route_destination", label: __("Destination"), fieldtype: "Data", default: defaults.route_destination || "", description: __("Example: Casablanca, Paris") },
            { fieldname: "column_break_2", fieldtype: "Column Break" },
            { fieldname: "destination_zone", label: __("Destination Zone"), fieldtype: "Data", default: defaults.destination_zone || "", description: __("Example: Casablanca Central") },
            { fieldname: "section_context", fieldtype: "Section Break", label: __("Logistics Context") },
            { fieldname: "flow_scope", label: __("Flow Scope"), fieldtype: "Select", options: "\nInbound\nDomestic\nOutbound", default: defaults.flow_scope || "" },
            { fieldname: "shipping_responsibility", label: __("Shipping Responsibility"), fieldtype: "Select", options: "\nOrderlift\nCustomer", default: defaults.shipping_responsibility || "" },
            { fieldname: "column_break_3", fieldtype: "Column Break" },
            { fieldname: "departure_date", label: __("Departure Date"), fieldtype: "Date", default: defaults.departure_date || "" },
            { fieldname: "deadline", label: __("Deadline"), fieldtype: "Date", default: defaults.deadline || "" },
        ];
    }

    async function createAndOpenForecastPlan(values, dialog) {
        const planLabel = String(values.plan_label || "").trim();
        const company = String(values.company || "").trim();
        if (!planLabel) {
            frappe.throw(__("Plan Label is required"));
            return;
        }
        if (!company) {
            frappe.throw(__("Company is required"));
            return;
        }
        const doc = {
            doctype: "Forecast Load Plan",
            plan_label: planLabel,
            company,
            container_profile: String(values.container_profile || "").trim() || undefined,
            route_origin: String(values.route_origin || "").trim() || undefined,
            route_destination: String(values.route_destination || "").trim() || undefined,
            flow_scope: String(values.flow_scope || "") || undefined,
            shipping_responsibility: String(values.shipping_responsibility || "") || undefined,
            destination_zone: String(values.destination_zone || "").trim() || undefined,
            departure_date: String(values.departure_date || "") || undefined,
            deadline: String(values.deadline || "") || undefined,
        };
        const response = await frappe.call({ method: "frappe.client.insert", args: { doc }, freeze: true });
        if (response.message) {
            dialog.hide();
            frappe.set_route("planning", response.message.name);
        }
    }

    async function moveCard(page, plan, stage) {
        const res = await frappe.call({
            method: "orderlift.orderlift_logistics.page.logistics_pipeline.logistics_pipeline.update_logistics_stage",
            args: { plan, stage },
            freeze: true,
        });
        const message = res.message || {};
        if (message.validation && message.validation.has_issues) {
            frappe.msgprint({
                title: __("Plan is not ready"),
                indicator: "orange",
                message: (message.validation.issues || []).map((issue) => frappe.utils.escape_html(issue.message || issue.type)).join("<br>") || __("Resolve validation issues before moving this container."),
            });
        }
        load(page);
    }

    function kpi(label, value) {
        return `<div class="llp-kpi"><span>${frappe.utils.escape_html(label || "-")}</span><strong>${frappe.utils.escape_html(String(value == null ? "-" : value))}</strong></div>`;
    }

    function select(field, label, options) {
        const selected = STATE.filters[field] || "All";
        return `
            <label><span>${frappe.utils.escape_html(label)}</span><select data-filter="${field}">
                ${["All"].concat(options || []).map((option) => `<option value="${frappe.utils.escape_html(option)}" ${option === selected ? "selected" : ""}>${frappe.utils.escape_html(__(option))}</option>`).join("")}
            </select></label>
        `;
    }

    function columnMarkup(column) {
        const isCollapsed = Boolean(STATE.collapsedColumns[column.name]);
        return `
            <article class="llp-column llp-${String(column.color || "Blue").toLowerCase()} ${isCollapsed ? "is-collapsed" : ""}" data-stage="${frappe.utils.escape_html(column.name)}">
                <header><div><strong>${frappe.utils.escape_html(column.label || column.name)}</strong><span>${(column.cards || []).length} ${__("containers")}</span></div><div class="llp-column-tools">${column.assigned_user ? `<small>${__("Assigns")}: ${frappe.utils.escape_html(column.assigned_user)}</small>` : ""}<button type="button" data-toggle-column="${frappe.utils.escape_html(column.name)}" aria-label="${frappe.utils.escape_html(isCollapsed ? __("Expand column") : __("Collapse column"))}">${isCollapsed ? "+" : "-"}</button></div></header>
                <div class="llp-card-stack">${(column.cards || []).map(cardMarkup).join("") || `<div class="llp-column-empty">${__("Drop containers here")}</div>`}</div>
            </article>
        `;
    }

    function cardMarkup(card) {
        const maxUtil = Math.max(Number(card.weight_utilization_pct || 0), Number(card.volume_utilization_pct || 0));
        return `
            <article class="llp-card" draggable="true" data-name="${frappe.utils.escape_html(card.name)}" data-stage="${frappe.utils.escape_html(card.stage)}">
                <div class="llp-card-head"><button data-open="${frappe.utils.escape_html(card.name)}">${frappe.utils.escape_html(card.title || card.name)}</button><span>${frappe.utils.escape_html(card.stage || "-")}</span></div>
                <p>${frappe.utils.escape_html(card.subtitle || "")}</p>
                <div class="llp-route">${frappe.utils.escape_html(card.route || card.destination_zone || "No route")}</div>
                <div class="llp-dates">
                    <span>${__("Depart")}: ${frappe.utils.escape_html(formatDate(card.departure_date) || "-")}</span>
                    <span>${__("Deadline")}: ${frappe.utils.escape_html(formatDate(card.deadline) || "-")}</span>
                </div>
                <div class="llp-meter"><span style="width:${Math.min(maxUtil, 120)}%"></span></div>
                <div class="llp-meta">
                    <span>${frappe.utils.escape_html(card.company || __("No company"))}</span>
                    <span>${__("W")}: ${Number(card.weight_utilization_pct || 0).toFixed(0)}%</span>
                    <span>${__("V")}: ${Number(card.volume_utilization_pct || 0).toFixed(0)}%</span>
                    <span>${frappe.utils.escape_html(card.item_count || 0)} / ${frappe.utils.escape_html(card.total_item_count || 0)} ${__("items")}</span>
                    <span>${frappe.utils.escape_html(card.source_doc_count || 0)} ${__("docs")}</span>
                    <span>${Number(card.total_weight_kg || 0).toFixed(0)} ${__("kg")}</span>
                    <span>${Number(card.total_volume_m3 || 0).toFixed(2)} ${__("m3")}</span>
                </div>
                <div class="llp-tags">
                    ${[card.flow_scope, card.shipping_responsibility, card.destination_zone].filter(Boolean).map((tag) => `<span>${frappe.utils.escape_html(tag)}</span>`).join("")}
                </div>
                ${(card.risk_flags || []).length ? `<div class="llp-risks">${card.risk_flags.map((risk) => `<strong>${frappe.utils.escape_html(risk)}</strong>`).join("")}</div>` : ""}
                ${card.assigned_user_label ? `<div class="llp-assignment">${__("Task")}: ${frappe.utils.escape_html(card.assigned_user_label)}</div>` : ""}
            </article>
        `;
    }

    function formatDate(value) {
        return value ? frappe.datetime.str_to_user(String(value)) : "";
    }

    function injectStyles() {
        if (document.getElementById("llp-style")) return;
        const style = document.createElement("style");
        style.id = "llp-style";
        style.textContent = `
            @import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;450;500;600;700&family=Geist+Mono:wght@400;500&display=swap');
            .olp-logistics-root { --canvas:#FAFBFC;--canvas-2:#F4F6F8;--surface:#FFFFFF;--surface-2:#F7F8FA;--ink-1000:#0A0E1A;--ink-900:#11151F;--ink-800:#1F2433;--ink-700:#2E3548;--ink-600:#495061;--ink-500:#6B7280;--ink-400:#9099A6;--ink-300:#B8BFC9;--ink-200:#DDE1E7;--ink-150:#E8EBEF;--ink-100:#EFF1F4;--primary-700:#3730A3;--primary-600:#4F46E5;--primary-100:#E0E7FF;--primary-50:#EEF2FF;--success-700:#047857;--success-500:#10B981;--success-100:#D1FAE5;--success-50:#ECFDF5;--info-700:#0369A1;--info-100:#E0F2FE;--info-50:#F0F9FF;--rose-700:#BE123C;--rose-100:#FFE4E6;--rose-50:#FFF1F2;--accent-700:#6D28D9;--accent-600:#7C3AED;--accent-100:#EDE9FE;--accent-50:#F5F3FF;--font-sans:'Geist',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;--font-mono:'Geist Mono','SF Mono',Menlo,monospace;--r-lg:14px;--r-2xl:22px;--shadow-xs:0 1px 2px rgba(15,23,42,.04);--shadow-sm:0 1px 2px rgba(15,23,42,.04),0 2px 4px rgba(15,23,42,.04);--shadow-md:0 2px 4px rgba(15,23,42,.04),0 4px 12px rgba(15,23,42,.05);--ease:cubic-bezier(.32,.72,0,1);background:radial-gradient(circle at 20% 0%,rgba(99,102,241,.05) 0%,transparent 50%),radial-gradient(circle at 80% 30%,rgba(124,58,237,.03) 0%,transparent 50%),linear-gradient(to bottom,var(--canvas) 0%,var(--canvas-2) 100%);font-family:var(--font-sans);font-feature-settings:'cv11','ss01','ss03';-webkit-font-smoothing:antialiased;color:var(--ink-900); }
            .olp-logistics-root *{box-sizing:border-box}.olp-logistics-root button,.olp-logistics-root input,.olp-logistics-root select{font-family:inherit}.llp-shell { max-width:1520px; margin:0 auto; padding:24px 24px 96px; display:grid; gap:18px; min-height:calc(100vh - 112px); }
            .llp-breadcrumb{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--ink-500);font-family:var(--font-mono)}.llp-breadcrumb a{color:var(--ink-500);text-decoration:none}.llp-breadcrumb a:hover{color:var(--ink-800)}.llp-breadcrumb .sep{color:var(--ink-300)}.llp-breadcrumb .current{color:var(--ink-800);font-weight:500}
            .llp-hero { position:relative;display:grid;grid-template-columns:1fr auto;gap:32px;align-items:center;border:1px solid var(--ink-150);border-radius:var(--r-2xl);padding:28px 32px;background:var(--surface);color:var(--ink-1000);box-shadow:var(--shadow-md);overflow:hidden; }.llp-hero::before{content:'';position:absolute;top:0;right:0;width:60%;height:100%;background:radial-gradient(ellipse at top right,rgba(99,102,241,.06) 0%,transparent 60%);pointer-events:none}.llp-hero::after{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,rgba(99,102,241,.4) 30%,rgba(124,58,237,.4) 70%,transparent)}.llp-hero-copy,.llp-hero-side{position:relative;z-index:1}.llp-eyebrow{display:inline-flex;align-items:center;gap:8px;padding:5px 12px;background:var(--primary-50);border:1px solid var(--primary-100);border-radius:999px;font-size:11px;font-weight:500;color:var(--primary-700);margin-bottom:14px}.llp-hero h1 { margin:0 0 8px;font-size:28px;font-weight:600;letter-spacing:-.025em;color:var(--ink-1000);line-height:1.15; }.llp-hero p { margin:0;color:var(--ink-500);font-size:14px;font-weight:400;line-height:1.55;max-width:640px; }
            .llp-kpis { display:grid;grid-template-columns:repeat(4,minmax(112px,1fr));gap:12px; }
            .llp-hero-side { display:grid;gap:12px;justify-items:end; }
            .llp-kpi { min-height:72px;display:flex;flex-direction:column;align-items:flex-start;justify-content:center;gap:2px;border-radius:var(--r-lg);padding:12px;background:var(--surface);border:1px solid var(--ink-150);box-shadow:var(--shadow-xs);transition:all .25s var(--ease); }.llp-kpi:hover{transform:translateY(-2px);box-shadow:var(--shadow-md)}
            .llp-kpi span { display:block;color:var(--ink-500);font-size:11px;font-weight:500; }
            .llp-kpi strong { display:block;color:var(--ink-1000);font-size:20px;font-weight:600;line-height:1.1;font-feature-settings:'tnum'; }
            .llp-filters { display:grid;grid-template-columns:minmax(240px,1fr) repeat(3,minmax(150px,190px)) auto;gap:10px;align-items:end;border:1px solid var(--ink-150);border-radius:var(--r-lg);background:var(--surface);padding:14px;box-shadow:var(--shadow-sm); }
            .llp-filters input,.llp-filters select { width:100%;min-height:38px;border:1px solid var(--ink-200);border-radius:8px;background:var(--surface);padding:0 11px;color:var(--ink-900);font-size:13px;font-weight:400;outline:none;transition:all .2s var(--ease); }.llp-filters input:focus,.llp-filters select:focus{border-color:var(--primary-600);box-shadow:0 0 0 3px rgba(99,102,241,.15)}
            .llp-filters label { display:grid;gap:6px;color:var(--ink-600);font-size:11px;font-weight:500; }
            .llp-refresh,.llp-create { height:38px;border:1px solid transparent;border-radius:10px;padding:0 14px;background:var(--surface);color:var(--ink-700);font-size:13px;font-weight:500;cursor:pointer;transition:all .2s var(--ease); }
            .llp-refresh{border-color:var(--ink-200)}.llp-refresh:hover{background:var(--surface-2);color:var(--ink-900)}.llp-create { background:var(--ink-1000);color:#fff;box-shadow:var(--shadow-sm); }.llp-create:hover{background:var(--ink-800);transform:translateY(-1px)}
            .llp-board { display:grid;grid-template-columns:repeat(6,minmax(260px,1fr));gap:12px;overflow-x:auto;padding-bottom:8px; }
            .llp-column { min-height:520px;border:1px solid var(--ink-150);border-radius:var(--r-lg);background:var(--surface);padding:10px;display:grid;grid-template-rows:auto 1fr;gap:8px;box-shadow:var(--shadow-sm); }
            .llp-column.is-collapsed { min-height: auto; grid-template-rows: auto; }
            .llp-column.is-collapsed .llp-card-stack { display: none; }
            .llp-column.is-over { outline: 3px solid rgba(37,99,235,.24); outline-offset: 2px; }
            .llp-column header { min-height: 52px; display: flex; justify-content: space-between; gap: 8px; align-items: flex-start; border-bottom: 1px solid #e5ebf7; padding-bottom: 8px; }
            .llp-column header strong { display:block;color:var(--ink-1000);font-size:13px;font-weight:600; }
            .llp-column header span, .llp-column header small { color:var(--ink-500);font-size:11px;font-weight:500; }
            .llp-column-tools { display:flex;align-items:center;gap:8px; }
            .llp-column-tools button { width:28px;height:28px;border-radius:8px;border:1px solid var(--ink-200);background:var(--surface);color:var(--ink-700);font-size:16px;font-weight:700;line-height:1;cursor:pointer; }
            .llp-card-stack { display: grid; align-content: start; gap: 8px; }
            .llp-card { border:1px solid var(--ink-150);border-radius:12px;background:var(--surface);padding:10px;cursor:grab;transition:all .25s var(--ease);box-shadow:var(--shadow-xs); }
            .llp-card:active { cursor: grabbing; }
            .llp-card:hover { transform: translateY(-1px); box-shadow: 0 12px 26px rgba(15,23,42,.08); }
            .llp-card-head { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
            .llp-card-head button { border:0;padding:0;background:transparent;color:var(--ink-900);font-size:13px;font-weight:600;text-align:left;cursor:pointer; }
            .llp-card-head span { border-radius:6px;background:var(--info-50);color:var(--info-700);border:1px solid var(--info-100);padding:3px 7px;font-size:11px;font-weight:600;white-space:nowrap; }
            .llp-card p { margin:5px 0 0;color:var(--ink-500);font-size:12px;font-weight:400; }
            .llp-route { margin-top:7px;color:var(--ink-900);font-size:12px;font-weight:600; }
            .llp-dates { margin-top: 7px; display: grid; grid-template-columns: 1fr 1fr; gap: 5px; color: #64748b; font-size: 10px; font-weight: 900; }
            .llp-meter { margin-top: 8px; height: 8px; border-radius: 999px; overflow: hidden; background: #e2e8f0; }
            .llp-meter span { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg,#22c55e,#f97316); }
            .llp-meta, .llp-tags, .llp-risks { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 8px; }
            .llp-meta span, .llp-tags span { border-radius: 999px; background: #f1f5f9; color: #35507c; padding: 4px 7px; font-size: 10px; font-weight: 900; }
            .llp-risks strong { border-radius: 999px; background: #fee2e2; color: #b91c1c; padding: 4px 7px; font-size: 10px; font-weight: 900; }
            .llp-assignment { margin-top: 8px; border-radius: 12px; background: #eef2ff; color: #3730a3; padding: 7px; font-size: 11px; font-weight: 900; }
            .llp-column-empty, .llp-empty { min-height: 120px; border: 1px dashed #cbd5e1; border-radius: 15px; display: flex; align-items: center; justify-content: center; color: #64748b; font-size: 12px; font-weight: 900; }
            .llp-card-head button:focus-visible, .llp-refresh:focus-visible, .llp-create:focus-visible, .llp-filters input:focus-visible, .llp-filters select:focus-visible { outline: 3px solid rgba(37,99,235,.24); outline-offset: 2px; }
            .olp-stage-error-modal { position: fixed; inset: 0; z-index: 1050; display: grid; place-items: center; padding: 24px; background: rgba(15,23,42,.36); backdrop-filter: blur(8px); opacity: 0; transition: opacity .18s ease; }
            .olp-stage-error-modal.is-visible { opacity: 1; }
            .olp-stage-error-card { position: relative; width: min(520px, 100%); overflow: hidden; border-radius: 18px; background: #fff; border: 1px solid #e2e8f0; box-shadow: 0 24px 70px rgba(15,23,42,.24), 0 2px 8px rgba(15,23,42,.06); transform: translateY(8px) scale(.98); transition: transform .18s cubic-bezier(.16, 1, .3, 1); }
            .olp-stage-error-modal.is-visible .olp-stage-error-card { transform: translateY(0) scale(1); }
            .olp-stage-error-close { position: absolute; top: 12px; right: 12px; width: 30px; height: 30px; border: 1px solid #e2e8f0; border-radius: 999px; background: #fff; color: #64748b; font-size: 13px; font-weight: 900; line-height: 1; cursor: pointer; z-index: 2; }
            .olp-stage-error-close:hover, .olp-stage-error-close:focus { background: #f8fafc; color: #0f172a; outline: 3px solid rgba(37,99,235,.12); }
            .olp-stage-error-hero { display: grid; grid-template-columns: 44px minmax(0, 1fr); gap: 12px; padding: 22px 52px 17px 20px; background: #fff; border-bottom: 1px solid #e2e8f0; }
            .olp-stage-error-mark { width: 44px; height: 44px; display: inline-flex; align-items: center; justify-content: center; border-radius: 14px; background: #eff6ff; border: 1px solid #bfdbfe; color: #1d4ed8; font-size: 18px; font-weight: 950; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
            .olp-stage-error-hero span { display: inline-flex; margin-bottom: 4px; color: #1d4ed8; font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: .1em; }
            .olp-stage-error-hero h2 { margin: 0; color: #0f172a; font-size: 19px; line-height: 1.15; font-weight: 850; letter-spacing: -.025em; }
            .olp-stage-error-hero p { margin: 6px 0 0; color: #64748b; font-size: 12px; line-height: 1.45; font-weight: 600; }
            .olp-stage-error-route { display: grid; grid-template-columns: minmax(0, 1fr) 28px minmax(0, 1fr); align-items: center; gap: 8px; margin: 14px 20px 0; padding: 8px; border-radius: 14px; background: #f8fafc; border: 1px solid #eef2f7; }
            .olp-stage-error-route span, .olp-stage-error-route strong { min-width: 0; min-height: 32px; display: inline-flex; align-items: center; justify-content: center; padding: 0 10px; border-radius: 11px; font-size: 11px; font-weight: 850; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            .olp-stage-error-route span { background: #fff; color: #475569; border: 1px solid #e2e8f0; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
            .olp-stage-error-route strong { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }
            .olp-stage-error-route i { height: 2px; border-radius: 999px; background: linear-gradient(90deg, #cbd5e1, #1d4ed8); position: relative; }
            .olp-stage-error-route i::after { content: ""; position: absolute; right: -1px; top: -3px; width: 8px; height: 8px; border-right: 2px solid #1d4ed8; border-top: 2px solid #1d4ed8; transform: rotate(45deg); }
            .olp-stage-error-body { margin: 12px 20px 0; padding: 13px; border-radius: 14px; background: #fff; border: 1px solid #e2e8f0; }
            .olp-stage-error-body > span { display: block; margin-bottom: 9px; color: #64748b; font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: .08em; }
            .olp-stage-error-body p { margin: 0; color: #334155; font-size: 12px; font-weight: 600; line-height: 1.45; }
            .olp-stage-error-actions { display: flex; justify-content: flex-end; gap: 8px; padding: 16px 20px 20px; }
            .olp-stage-error-actions button { min-height: 36px; border: 1px solid #0f172a; border-radius: 12px; background: #0f172a; color: #fff; padding: 0 14px; font-size: 12px; font-weight: 800; cursor: pointer; }
            .olp-stage-error-actions button:hover, .olp-stage-error-actions button:focus { transform: translateY(-1px); outline: 3px solid rgba(15,23,42,.14); }
            .olp-stage-error-actions button.is-secondary { background: #f8fafc; border-color: #e2e8f0; color: #475569; }
            .llp-plan-modal { position: fixed; inset: 0; z-index: 1050; display: grid; place-items: center; padding: 24px; background: rgba(15,23,42,.36); backdrop-filter: blur(8px); opacity: 0; transition: opacity .18s ease; }
            .llp-plan-modal.is-visible { opacity: 1; }
            .llp-plan-modal-card { width: min(720px,100%); max-height: calc(100vh - 48px); overflow: hidden; display: grid; grid-template-rows: auto 1fr auto; border-radius: 18px; background: #fff; border: 1px solid #e2e8f0; box-shadow: 0 24px 70px rgba(15,23,42,.24), 0 2px 8px rgba(15,23,42,.06); }
            .llp-plan-modal-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 18px 20px; border-bottom: 1px solid #eef2f7; }
            .llp-plan-modal-head h2 { margin: 0; color: #0f172a; font-size: 18px; font-weight: 850; letter-spacing: -.02em; }
            .llp-plan-modal-head button { width: 30px; height: 30px; border-radius: 999px; border: 1px solid #e2e8f0; background: #fff; color: #64748b; font-size: 13px; font-weight: 900; cursor: pointer; }
            .llp-plan-modal-body { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 18px 20px; overflow: auto; }
            .llp-plan-field-row { display: grid; gap: 6px; }
            .llp-plan-field-row label { color: #475569; font-size: 11px; font-weight: 800; }
            .llp-plan-field { width: 100%; min-height: 38px; border: 1px solid #dbe3ee; border-radius: 10px; background: #fff; color: #0f172a; padding: 0 11px; font-size: 13px; font-weight: 600; outline: none; }
            .llp-plan-field:focus { border-color: #4f46e5; box-shadow: 0 0 0 3px rgba(79,70,229,.14); }
            .llp-plan-modal-actions { display: flex; justify-content: flex-end; gap: 8px; padding: 14px 20px 18px; border-top: 1px solid #eef2f7; }
            .llp-plan-modal-actions button { min-height: 36px; border: 1px solid #0f172a; border-radius: 12px; background: #0f172a; color: #fff; padding: 0 14px; font-size: 12px; font-weight: 800; cursor: pointer; }
            .llp-plan-modal-actions button.is-secondary { background: #f8fafc; border-color: #e2e8f0; color: #475569; }
            @media (max-width: 1280px) { .llp-hero { grid-template-columns: 1fr; } .llp-hero-side { justify-items: stretch; } .llp-kpis { grid-template-columns: repeat(4,minmax(0,1fr)); } }
            @media (max-width: 1100px) { .llp-filters { grid-template-columns: 1fr; } }
            @media (max-width: 900px) { .llp-shell { padding: 20px 16px 96px; } .llp-kpis { grid-template-columns: repeat(2,minmax(0,1fr)); } }
            @media (max-width: 720px) { .llp-kpis { grid-template-columns: 1fr; } .llp-board { grid-template-columns: repeat(6, 82vw); } .olp-stage-error-modal,.llp-plan-modal { padding: 14px; } .olp-stage-error-hero { grid-template-columns: 1fr; padding-right: 54px; } .olp-stage-error-route,.llp-plan-modal-body { grid-template-columns: 1fr; } .olp-stage-error-route i { display: none; } .olp-stage-error-actions,.llp-plan-modal-actions { display: grid; grid-template-columns: 1fr; } }
        `;
        document.head.appendChild(style);
    }
})();
