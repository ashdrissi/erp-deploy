/*
 * Container Load Plan — Clean Planning Dashboard
 *
 * DESIGN RULE: Never reparent Frappe controls. The HTML field renders a
 * read-only dashboard above the standard form. All native controls
 * (Link, Select, Date, Child Table) stay in their natural DOM position
 * so dropdowns, date pickers, awesomplete, and Add Row all work.
 */

frappe.ui.form.on("Container Load Plan", {
    refresh(frm) {
        _renderDashboard(frm);
        _toggleChildColumns(frm);
        _addToolbarButtons(frm);
        _setPageIndicator(frm);
    },

    source_type(frm) {
        _toggleChildColumns(frm);
        _renderDashboard(frm);
    },

    flow_scope: (frm) => _renderDashboard(frm),
    shipping_responsibility: (frm) => _renderDashboard(frm),
    status: (frm) => { _renderDashboard(frm); _setPageIndicator(frm); },
    analysis_status: (frm) => _renderDashboard(frm),
    container_profile: (frm) => _renderDashboard(frm),
    destination_zone: (frm) => _renderDashboard(frm),
    company: (frm) => _renderDashboard(frm),
    departure_date: (frm) => _renderDashboard(frm),
    dispatcher: (frm) => _renderDashboard(frm),
    group_by_customer: (frm) => _renderDashboard(frm),
    shipments_add: (frm) => _renderDashboard(frm),
    shipments_remove: (frm) => _renderDashboard(frm),
});

frappe.ui.form.on("Load Plan Shipment", {
    delivery_note(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.delivery_note) { _renderDashboard(frm); return; }
        frappe.db.get_value("Delivery Note", row.delivery_note,
            ["customer", "custom_total_weight_kg", "custom_total_volume_m3"]
        ).then((r) => {
            const d = r.message || {};
            frappe.model.set_value(cdt, cdn, "customer", d.customer || "");
            frappe.model.set_value(cdt, cdn, "shipment_weight_kg", d.custom_total_weight_kg || 0);
            frappe.model.set_value(cdt, cdn, "shipment_volume_m3", d.custom_total_volume_m3 || 0);
            _renderDashboard(frm);
        });
    },
    purchase_order(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.purchase_order) { _renderDashboard(frm); return; }
        frappe.db.get_value("Purchase Order", row.purchase_order, ["supplier"]).then((r) => {
            frappe.model.set_value(cdt, cdn, "supplier", (r.message || {}).supplier || "");
            _renderDashboard(frm);
        });
    },
    selected: (frm) => _renderDashboard(frm),
    sequence: (frm) => _renderDashboard(frm),
});


/* ═══════════════════════════════════════════════════════
 * Dashboard — rendered in the capacity_dashboard_html field
 * Pure read-only display. No controls reparented.
 * ═══════════════════════════════════════════════════════ */
function _renderDashboard(frm) {
    const $html = frm.fields_dict.capacity_dashboard_html;
    if (!$html) return;

    const sc = _scenario(frm.doc.flow_scope, frm.doc.shipping_responsibility);
    const st = _stats(frm.doc);
    const isPo = frm.doc.source_type === "Purchase Order";

    $html.$wrapper.html(`
<div class="clp">
    <!-- ── Header Row ── -->
    <div class="clp-header">
        <div class="clp-header__left">
            <div class="clp-header__breadcrumb">${__("Container Load Plans")} / ${_esc(frm.doc.name || __("New"))}</div>
            <h2 class="clp-header__title">${_esc(frm.doc.container_label || __("New Container Load Plan"))}</h2>
            <p class="clp-header__desc">${_esc(sc.subtitle)}</p>
        </div>
        <div class="clp-header__right">
            <div class="clp-header__pills">
                <span class="clp-pill clp-pill--${sc.tone}">${_esc(frm.doc.flow_scope || __("Unclassified"))}</span>
                <span class="clp-pill clp-pill--muted">${_esc(frm.doc.shipping_responsibility || __("Unassigned"))}</span>
                <span class="clp-pill clp-pill--${_analysisTone(frm.doc.analysis_status)}">${_esc(_analysisLabel(frm.doc.analysis_status))}</span>
            </div>
            <div class="clp-header__actions">
                <button class="clp-btn clp-btn--primary" data-action="run-analysis" ${frm.doc.__islocal ? "disabled" : ""}>${__("Run Analysis")}</button>
                <button class="clp-btn clp-btn--primary" data-action="suggest" ${frm.doc.__islocal ? "disabled" : ""}>${__("Suggest")}</button>
                <button class="clp-btn clp-btn--ghost" data-action="cockpit">${__("Cockpit")}</button>
            </div>
        </div>
    </div>

    <!-- ── Metrics Strip ── -->
    <div class="clp-metrics">
        ${_metricCard(__("Source"), isPo ? __("Purchase Order") : __("Delivery Note"))}
        ${_metricCard(__("Destination"), _esc(frm.doc.destination_zone || "—"))}
        ${_metricCard(__("Departure"), frm.doc.departure_date || "—")}
        ${_metricCard(__("Status"), _esc(frm.doc.status || __("Planning")))}
        ${_metricCard(__("Rows"), String(st.total))}
        ${_metricCard(__("Selected"), String(st.selected))}
    </div>

    <!-- ── Two-Column Layout ── -->
    <div class="clp-columns">
        <div class="clp-col-main">
            <!-- Capacity Card -->
            <div class="clp-card">
                <div class="clp-card__head">
                    <h3>${__("Capacity Utilization")}</h3>
                    <span class="clp-pill clp-pill--${_analysisTone(frm.doc.analysis_status)} clp-pill--sm">${_esc(_analysisLabel(frm.doc.analysis_status))}</span>
                </div>
                <div class="clp-gauges">
                    ${_gauge(__("Weight"), st.wPct, `${st.totalW.toFixed(1)} kg ${__("loaded")}`)}
                    ${_gauge(__("Volume"), st.vPct, `${st.totalV.toFixed(3)} m³ ${__("loaded")}`)}
                </div>
                <div class="clp-kpi-row">
                    ${_kpi(__("Partners"), String(st.partners))}
                    ${_kpi(__("Limiting"), frm.doc.limiting_factor || __("Balanced"))}
                    ${_kpi(__("Profile"), frm.doc.container_profile || "—")}
                    ${_kpi(__("Company"), frm.doc.company || "—")}
                </div>
            </div>

            <!-- Shipment Preview -->
            <div class="clp-card">
                <div class="clp-card__head">
                    <h3>${__("Shipment Preview")}</h3>
                    <span class="clp-card__badge">${st.selected}/${st.total} ${__("selected")}</span>
                </div>
                ${_shipmentTable(frm.doc, isPo)}
            </div>
        </div>

        <div class="clp-col-side">
            <!-- Scenario Guide -->
            <div class="clp-card clp-card--guide">
                <div class="clp-card__head"><h3>${__("Scenario Guide")}</h3></div>
                <p class="clp-guide__text">${_esc(sc.guidance)}</p>
                <ol class="clp-guide__steps">
                    ${sc.steps.map(s => `<li>${_esc(s)}</li>`).join("")}
                </ol>
            </div>

            <!-- Quick Actions -->
            <div class="clp-card">
                <div class="clp-card__head"><h3>${__("Quick Actions")}</h3></div>
                <div class="clp-actions-stack">
                    <button class="clp-btn clp-btn--block clp-btn--outline" data-action="run-analysis" ${frm.doc.__islocal ? "disabled" : ""}>
                        <span class="clp-btn__icon">⟳</span> ${__("Recalculate Totals")}
                    </button>
                    <button class="clp-btn clp-btn--block clp-btn--outline" data-action="suggest" ${frm.doc.__islocal ? "disabled" : ""}>
                        <span class="clp-btn__icon">✦</span> ${__("Auto-Suggest Shipments")}
                    </button>
                    ${_canCreatePRs(frm) ? `<button class="clp-btn clp-btn--block clp-btn--outline" data-action="create-prs"><span class="clp-btn__icon">📋</span> ${__("Draft Purchase Receipts")}</button>` : ""}
                    ${_canCreateTrip(frm) ? `<button class="clp-btn clp-btn--block clp-btn--outline" data-action="create-trip"><span class="clp-btn__icon">🚛</span> ${__("Create Delivery Trip")}</button>` : ""}
                </div>
            </div>
        </div>
    </div>
</div>
    `);

    // Bind action buttons
    $html.$wrapper.off("click", ".clp-btn[data-action]");
    $html.$wrapper.on("click", ".clp-btn[data-action]", async function () {
        if ($(this).is("[disabled]")) return;
        const a = $(this).data("action");
        if (a === "run-analysis") await _doAnalysis(frm);
        else if (a === "suggest") await _doSuggest(frm);
        else if (a === "cockpit") frappe.set_route("logistics-hub-cockpit");
        else if (a === "create-prs") await _doPRs(frm);
        else if (a === "create-trip") await _doTrip(frm);
    });
}


/* ═══════════════════════════════════════════
 * Helper renderers
 * ═══════════════════════════════════════════ */
function _esc(v) { return frappe.utils.escape_html(v || ""); }

function _metricCard(label, value) {
    return `<div class="clp-metric"><div class="clp-metric__label">${_esc(label)}</div><div class="clp-metric__value">${_esc(value)}</div></div>`;
}

function _gauge(label, pct, sub) {
    const cls = pct > 100 ? "clp-gauge--danger" : pct > 85 ? "clp-gauge--warning" : "clp-gauge--ok";
    return `
        <div class="clp-gauge">
            <div class="clp-gauge__head">
                <span class="clp-gauge__label">${_esc(label)}</span>
                <span class="clp-gauge__pct">${pct.toFixed(1)}%</span>
            </div>
            <div class="clp-gauge__track"><div class="clp-gauge__fill ${cls}" style="width:${Math.min(pct, 100)}%"></div></div>
            <div class="clp-gauge__sub">${_esc(sub)}</div>
        </div>`;
}

function _kpi(label, value) {
    return `<div class="clp-kpi"><div class="clp-kpi__value">${_esc(value)}</div><div class="clp-kpi__label">${_esc(label)}</div></div>`;
}

function _shipmentTable(doc, isPo) {
    const rows = (doc.shipments || []).slice().sort((a, b) => (a.sequence || 0) - (b.sequence || 0));
    if (!rows.length) {
        return `<div class="clp-empty">${__("No shipment rows yet. Use the table below or click Suggest to auto-fill.")}</div>`;
    }
    const srcH = isPo ? __("Purchase Order") : __("Delivery Note");
    const partH = isPo ? __("Supplier") : __("Customer");
    return `
        <div class="clp-table-wrap">
            <table class="clp-table">
                <thead><tr>
                    <th>${srcH}</th><th>${partH}</th><th>${__("Weight")}</th><th>${__("Volume")}</th><th>${__("Seq")}</th><th>${__("Status")}</th>
                </tr></thead>
                <tbody>${rows.map(r => {
                    const src = isPo ? (r.purchase_order || "—") : (r.delivery_note || "—");
                    const part = isPo ? (r.supplier || "—") : (r.customer || "—");
                    const sel = Number(r.selected || 0);
                    return `<tr>
                        <td><span class="clp-table__src">${_esc(src)}</span></td>
                        <td>${_esc(part)}</td>
                        <td>${Number(r.shipment_weight_kg || 0).toFixed(1)} kg</td>
                        <td>${Number(r.shipment_volume_m3 || 0).toFixed(3)} m³</td>
                        <td><span class="clp-table__seq">${Number(r.sequence || 0) || "—"}</span></td>
                        <td><span class="clp-table__pill ${sel ? "is-in" : "is-out"}">${sel ? __("Selected") : __("Excluded")}</span></td>
                    </tr>`;
                }).join("")}</tbody>
            </table>
        </div>`;
}


/* ═══════════════════════════════════════════
 * Scenario config
 * ═══════════════════════════════════════════ */
function _scenario(flow, resp) {
    if (flow === "Inbound") return {
        tone: "blue", subtitle: __("Consolidate supplier purchases into this inbound container before receiving and QC."),
        guidance: __("Build the plan from Purchase Orders. Only create draft Purchase Receipts when the shipment is confirmed."),
        steps: [__("Lock container profile before adding PO lines."), __("Use Suggest to optimise capacity."), __("Create Purchase Receipts after loading is confirmed.")],
    };
    if (flow === "Domestic") return {
        tone: "green", subtitle: __("Batch local distribution deliveries for Morocco routing and dispatch."),
        guidance: __("Keep only delivery notes that belong in the same physical run, then create a Delivery Trip."),
        steps: [__("Validate zone, dispatcher, and grouping."), __("Sequence shipments for optimal routing."), __("Create Delivery Trip once the plan is confirmed.")],
    };
    if (flow === "Outbound" && resp === "Customer") return {
        tone: "rose", subtitle: __("Customer-managed export — Orderlift prepares but does not own transport."),
        guidance: __("This plan is advisory. Avoid creating execution records unless responsibility changes."),
        steps: [__("Use for packaging readiness only."), __("Do not create Delivery Trip or shipping records.")],
    };
    return {
        tone: "slate", subtitle: __("Plan outbound container loads when Orderlift manages the shipment."),
        guidance: __("Source from Delivery Notes, optimise for capacity, and create a Delivery Trip for the local leg."),
        steps: [__("Add delivery notes that belong in this outbound movement."), __("Run analysis after changes."), __("Create Delivery Trip for Orderlift-managed local legs.")],
    };
}


/* ═══════════════════════════════════════════
 * Stats helper
 * ═══════════════════════════════════════════ */
function _stats(doc) {
    const rows = doc.shipments || [];
    const sel = rows.filter(r => Number(r.selected || 0));
    const pf = doc.source_type === "Purchase Order" ? "supplier" : "customer";
    const ps = new Set(rows.map(r => r[pf]).filter(Boolean));
    return {
        total: rows.length, selected: sel.length, partners: ps.size,
        totalW: Number(doc.total_weight_kg || 0), totalV: Number(doc.total_volume_m3 || 0),
        wPct: Number(doc.weight_utilization_pct || 0), vPct: Number(doc.volume_utilization_pct || 0),
    };
}


/* ═══════════════════════════════════════════
 * Analysis helpers
 * ═══════════════════════════════════════════ */
function _analysisTone(s) {
    if (s === "over_capacity") return "danger";
    if (s === "incomplete_data") return "warning";
    return "success";
}
function _analysisLabel(s) {
    if (s === "over_capacity") return __("Over Capacity");
    if (s === "incomplete_data") return __("Incomplete Data");
    return __("Ready");
}


/* ═══════════════════════════════════════════
 * Toolbar buttons (standard Frappe buttons)
 * ═══════════════════════════════════════════ */
function _addToolbarButtons(frm) {
    if (frm.doc.__islocal) return;
    frm.add_custom_button(__("Run Analysis"), () => _doAnalysis(frm), __("Planning"));
    frm.add_custom_button(__("Suggest Shipments"), () => _doSuggest(frm), __("Planning"));
    if (_canCreatePRs(frm)) frm.add_custom_button(__("Create Draft Purchase Receipts"), () => _doPRs(frm), __("Actions"));
    if (_canCreateTrip(frm)) frm.add_custom_button(__("Create Delivery Trip"), () => _doTrip(frm), __("Actions"));
}


/* ═══════════════════════════════════════════
 * Permission helpers
 * ═══════════════════════════════════════════ */
function _canCreatePRs(frm) {
    return frm.doc.docstatus === 1 && frm.doc.flow_scope === "Inbound"
        && frm.doc.source_type === "Purchase Order"
        && ["Loading", "In Transit", "Delivered"].includes(frm.doc.status);
}
function _canCreateTrip(frm) {
    return frm.doc.docstatus === 1 && frm.doc.source_type === "Delivery Note"
        && (frm.doc.flow_scope === "Domestic" || (frm.doc.flow_scope === "Outbound" && frm.doc.shipping_responsibility === "Orderlift"));
}


/* ═══════════════════════════════════════════
 * Server actions
 * ═══════════════════════════════════════════ */
async function _doAnalysis(frm) {
    if (frm.doc.__islocal) { frappe.show_alert({ message: __("Save first"), indicator: "orange" }); return; }
    await frappe.call({ method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.run_load_plan_analysis", args: { load_plan_name: frm.doc.name }, freeze: true, freeze_message: __("Running analysis…") });
    await frm.reload_doc();
}

async function _doSuggest(frm) {
    if (frm.doc.__islocal) { frappe.show_alert({ message: __("Save first"), indicator: "orange" }); return; }
    const r = await frappe.call({ method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.suggest_shipments", args: { load_plan_name: frm.doc.name }, freeze: true, freeze_message: __("Finding best mix…") });
    const sel = (r.message && r.message.selected) || [];
    if (!sel.length) { frappe.show_alert({ message: __("No fitting suggestions."), indicator: "orange" }); return; }
    if (frm.doc.source_type === "Purchase Order") {
        frappe.msgprint({ title: __("Inbound Suggestions"), message: __("PO suggestion append is coming in the next release."), indicator: "blue" });
        return;
    }
    const dns = sel.map(r => r.delivery_note).filter(Boolean);
    await frappe.call({ method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.append_shipments", args: { load_plan_name: frm.doc.name, delivery_notes: dns }, freeze: true, freeze_message: __("Adding shipments…") });
    await frm.reload_doc();
    frappe.show_alert({ message: __("Suggested shipments added."), indicator: "green" });
}

async function _doPRs(frm) {
    const ok = await _confirm(__("Create draft Purchase Receipts for the POs in this plan?"));
    if (!ok) return;
    const r = await frappe.call({ method: "orderlift.logistics.utils.inbound_receipt.create_draft_purchase_receipts", args: { load_plan_name: frm.doc.name }, freeze: true, freeze_message: __("Creating…") });
    if (r.message) frappe.msgprint({ title: __("Purchase Receipts"), message: r.message.message, indicator: "green" });
    await frm.reload_doc();
}

async function _doTrip(frm) {
    const ok = await _confirm(__("Create a Delivery Trip from this plan?"));
    if (!ok) return;
    const r = await frappe.call({ method: "orderlift.logistics.utils.domestic_dispatch.create_delivery_trip_from_load_plan", args: { load_plan_name: frm.doc.name }, freeze: true, freeze_message: __("Creating…") });
    if (r.message && r.message.delivery_trip) frappe.set_route("Form", "Delivery Trip", r.message.delivery_trip);
}

function _confirm(msg) { return new Promise(res => frappe.confirm(msg, () => res(true), () => res(false))); }


/* ═══════════════════════════════════════════
 * Child table column toggle + page indicator
 * ═══════════════════════════════════════════ */
function _toggleChildColumns(frm) {
    const g = frm.fields_dict.shipments && frm.fields_dict.shipments.grid;
    if (!g) return;
    const po = frm.doc.source_type === "Purchase Order";
    g.update_docfield_property("delivery_note", "hidden", po ? 1 : 0);
    g.update_docfield_property("purchase_order", "hidden", po ? 0 : 1);
    g.update_docfield_property("customer", "hidden", po ? 1 : 0);
    g.update_docfield_property("supplier", "hidden", po ? 0 : 1);
    frm.refresh_fields();
}

function _setPageIndicator(frm) {
    const f = frm.doc.flow_scope || "Planning";
    const s = frm.doc.analysis_status;
    const c = s === "over_capacity" ? "red" : s === "incomplete_data" ? "orange" : f === "Inbound" ? "blue" : f === "Domestic" ? "green" : "purple";
    frm.page.set_indicator(__(f), c);
}
