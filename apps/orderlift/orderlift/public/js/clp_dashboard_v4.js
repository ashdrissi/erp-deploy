/*
 * Container Load Plan — Full Workspace with Mounted Controls
 *
 * STRATEGY:
 *   1. Build an HTML skeleton ONCE in capacity_dashboard_html
 *   2. Mount native Frappe controls into named slots (<div id="clp-slot-xxx">)
 *   3. Update dynamic data (pills, gauges, preview) via targeted .html() on
 *      <div id="clp-dyn-xxx"> containers — never destroying the control slots
 *
 * This preserves Awesomplete dropdowns, date pickers, child table Add Row,
 * and all other Frappe field behaviors.
 */

const _HIDDEN = [
    "naming_series", "analysis_status",
    "total_weight_kg", "total_volume_m3",
    "weight_utilization_pct", "volume_utilization_pct",
    "limiting_factor",
];

const _CONFIG = [
    "container_label", "container_profile", "company", "flow_scope",
    "shipping_responsibility", "source_type", "destination_zone",
    "departure_date", "dispatcher", "status",
];

const _FULL_WIDTH = ["group_by_customer"];

/* ═══════════════════════════════════════════════════════
 * EVENT HANDLERS
 * ═══════════════════════════════════════════════════════ */
frappe.ui.form.on("Container Load Plan", {
    refresh(frm) {
        _hideFields(frm);
        _ensureWorkspace(frm);
        _updateDynamic(frm);
        _toggleChildColumns(frm);
        _addToolbarButtons(frm);
        _setPageIndicator(frm);
    },

    source_type(frm) { _updateDynamic(frm); _toggleChildColumns(frm); },
    flow_scope(frm) { _updateDynamic(frm); _setPageIndicator(frm); },
    shipping_responsibility: (frm) => _updateDynamic(frm),
    status(frm) { _updateDynamic(frm); _setPageIndicator(frm); },
    analysis_status: (frm) => _updateDynamic(frm),
    container_profile: (frm) => _updateDynamic(frm),
    destination_zone: (frm) => _updateDynamic(frm),
    company: (frm) => _updateDynamic(frm),
    departure_date: (frm) => _updateDynamic(frm),
    dispatcher: (frm) => _updateDynamic(frm),
    group_by_customer: (frm) => _updateDynamic(frm),
    shipments_add: (frm) => _updateDynamic(frm),
    shipments_remove: (frm) => _updateDynamic(frm),
});

frappe.ui.form.on("Load Plan Shipment", {
    delivery_note(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.delivery_note) { _updateDynamic(frm); return; }
        frappe.db.get_value("Delivery Note", row.delivery_note,
            ["customer", "custom_total_weight_kg", "custom_total_volume_m3"]
        ).then((r) => {
            const d = r.message || {};
            frappe.model.set_value(cdt, cdn, "customer", d.customer || "");
            frappe.model.set_value(cdt, cdn, "shipment_weight_kg", d.custom_total_weight_kg || 0);
            frappe.model.set_value(cdt, cdn, "shipment_volume_m3", d.custom_total_volume_m3 || 0);
            _updateDynamic(frm);
        });
    },
    purchase_order(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.purchase_order) { _updateDynamic(frm); return; }
        frappe.db.get_value("Purchase Order", row.purchase_order, ["supplier"]).then((r) => {
            frappe.model.set_value(cdt, cdn, "supplier", (r.message || {}).supplier || "");
            _updateDynamic(frm);
        });
    },
    selected: (frm) => _updateDynamic(frm),
    sequence: (frm) => _updateDynamic(frm),
});


/* ═══════════════════════════════════════════════════════
 * WORKSPACE — Build skeleton + mount controls
 * ═══════════════════════════════════════════════════════ */
function _hideFields(frm) {
    _HIDDEN.forEach((fn) => {
        const f = frm.fields_dict[fn];
        if (f && f.wrapper) $(f.wrapper).hide();
    });
}

function _$w(frm) {
    const f = frm.fields_dict.capacity_dashboard_html;
    return f ? f.$wrapper : null;
}

function _ensureWorkspace(frm) {
    const $w = _$w(frm);
    if (!$w) return;

    // If skeleton already exists AND has mounted controls, skip rebuild
    if ($w.find(".clp").length) {
        _mountAll(frm);
        return;
    }

    // Build fresh skeleton
    $w.html(_skeleton());
    _mountAll(frm);
    _bindActions(frm, $w);

    // Collapse empty standard form sections
    setTimeout(() => {
        $(frm.wrapper).find(".form-layout .form-section").each(function () {
            const $sec = $(this);
            const hasVisible = $sec.find(".frappe-control:visible").length;
            if (!hasVisible) $sec.hide();
        });
    }, 50);
}

function _mountAll(frm) {
    _CONFIG.forEach((fn) => _mount(frm, fn, "#clp-slot-" + fn));
    _FULL_WIDTH.forEach((fn) => _mount(frm, fn, "#clp-slot-" + fn));
    _mount(frm, "shipments", "#clp-slot-shipments");
    _mount(frm, "notes", "#clp-slot-notes");
}

function _mount(frm, fieldname, selector) {
    const field = frm.fields_dict[fieldname];
    if (!field || !field.wrapper) return;

    const $slot = _$w(frm).find(selector);
    if (!$slot.length) return;

    const $ctrl = $(field.wrapper).closest(".frappe-control");
    if (!$ctrl.length) return;

    // Already in the right place? Skip
    if ($ctrl.parent().is($slot) || $.contains($slot[0], $ctrl[0])) return;

    $ctrl.show();
    $slot.append($ctrl);
}


/* ═══════════════════════════════════════════════════════
 * DYNAMIC UPDATES — targeted .html() on #clp-dyn-*
 * Never touches the #clp-slot-* containers
 * ═══════════════════════════════════════════════════════ */
function _updateDynamic(frm) {
    const $w = _$w(frm);
    if (!$w || !$w.find(".clp").length) return;

    const doc = frm.doc;
    const sc = _scenario(doc.flow_scope, doc.shipping_responsibility);
    const st = _stats(doc);
    const isPo = doc.source_type === "Purchase Order";

    // Header text
    $w.find("#clp-dyn-title").text(doc.container_label || __("New Container Load Plan"));
    $w.find("#clp-dyn-desc").text(sc.subtitle);
    $w.find("#clp-dyn-pills").html(_pillsHtml(doc, sc));

    // Action button states
    $w.find('[data-action="run-analysis"], [data-action="suggest"]').prop("disabled", !!doc.__islocal);
    $w.find('[data-action="create-prs"]').toggle(!!_canPR(frm));
    $w.find('[data-action="create-trip"]').toggle(!!_canTrip(frm));

    // Metrics strip
    $w.find("#clp-dyn-metrics").html(_metricsHtml(doc, st, isPo));

    // Capacity gauges + KPIs
    $w.find("#clp-dyn-capacity").html(_capacityHtml(doc, st));

    // Shipment badge + preview
    $w.find("#clp-dyn-ship-badge").html(st.selected + "/" + st.total + " " + __("selected"));
    $w.find("#clp-dyn-preview").html(_previewHtml(doc, isPo));

    // Insights
    $w.find("#clp-dyn-insights").html(_insightsHtml(doc));

    // Guide
    $w.find("#clp-dyn-guide").html(_guideHtml(sc));
}


/* ═══════════════════════════════════════════════════════
 * SKELETON — static structure, built once
 * ═══════════════════════════════════════════════════════ */
function _skeleton() {
    return `
<section class="clp">
    <div class="clp-header">
        <div class="clp-header-left">
            <h2 class="clp-title" id="clp-dyn-title"></h2>
            <p class="clp-desc" id="clp-dyn-desc"></p>
        </div>
        <div class="clp-header-right">
            <div id="clp-dyn-pills" class="clp-pills"></div>
            <div class="clp-header-btns">
                <button class="clp-btn clp-btn--primary" data-action="run-analysis">${__("Run Analysis")}</button>
                <button class="clp-btn clp-btn--primary" data-action="suggest">${__("Suggest")}</button>
                <button class="clp-btn clp-btn--ghost" data-action="cockpit">${__("Cockpit")}</button>
            </div>
        </div>
    </div>

    <div id="clp-dyn-metrics" class="clp-metrics"></div>

    <div class="clp-columns">
        <div class="clp-col-main">
            <div class="clp-card">
                <div class="clp-card-head">
                    <div>
                        <h3>${__("Plan Configuration")}</h3>
                        <p>${__("All fields are fully editable — dropdowns, links, and dates work natively.")}</p>
                    </div>
                </div>
                <div class="clp-fields">
                    ${_CONFIG.map((fn) => '<div id="clp-slot-' + fn + '" class="clp-field"></div>').join("")}
                    ${_FULL_WIDTH.map((fn) => '<div id="clp-slot-' + fn + '" class="clp-field clp-field--full"></div>').join("")}
                </div>
            </div>

            <div class="clp-card">
                <div class="clp-card-head">
                    <div>
                        <h3>${__("Shipments")}</h3>
                        <p>${__("Source documents grouped into this container plan. Use Add Row below.")}</p>
                    </div>
                    <span id="clp-dyn-ship-badge" class="clp-badge"></span>
                </div>
                <div id="clp-dyn-preview"></div>
                <div id="clp-slot-shipments" class="clp-grid-slot"></div>
            </div>

            <div class="clp-card">
                <div class="clp-card-head">
                    <div>
                        <h3>${__("Notes & Instructions")}</h3>
                        <p>${__("Internal context for the logistics team.")}</p>
                    </div>
                </div>
                <div id="clp-slot-notes" class="clp-notes-slot"></div>
            </div>
        </div>

        <aside class="clp-col-side">
            <div class="clp-card">
                <div class="clp-card-head">
                    <div>
                        <h3>${__("Capacity")}</h3>
                        <p>${__("Real-time utilization of selected rows.")}</p>
                    </div>
                </div>
                <div id="clp-dyn-capacity"></div>
            </div>

            <div class="clp-card">
                <div class="clp-card-head"><div><h3>${__("Document Insights")}</h3></div></div>
                <div id="clp-dyn-insights"></div>
            </div>

            <div class="clp-card clp-card--guide">
                <div class="clp-card-head"><div><h3>${__("Scenario Guide")}</h3></div></div>
                <div id="clp-dyn-guide"></div>
            </div>

            <div class="clp-card">
                <div class="clp-card-head"><div><h3>${__("Quick Actions")}</h3></div></div>
                <div class="clp-side-actions">
                    <button class="clp-btn clp-btn--block clp-btn--outline" data-action="run-analysis">⟳ ${__("Recalculate Totals")}</button>
                    <button class="clp-btn clp-btn--block clp-btn--outline" data-action="suggest">✦ ${__("Auto-Suggest Shipments")}</button>
                    <button class="clp-btn clp-btn--block clp-btn--outline" data-action="create-prs" style="display:none">📋 ${__("Draft Purchase Receipts")}</button>
                    <button class="clp-btn clp-btn--block clp-btn--outline" data-action="create-trip" style="display:none">🚛 ${__("Create Delivery Trip")}</button>
                </div>
            </div>
        </aside>
    </div>
</section>`;
}


/* ═══════════════════════════════════════════════════════
 * DYNAMIC HTML GENERATORS
 * ═══════════════════════════════════════════════════════ */
function _esc(v) { return frappe.utils.escape_html(v || ""); }

function _pillsHtml(doc, sc) {
    return '<span class="clp-pill clp-pill--' + sc.tone + '">' + _esc(doc.flow_scope || __("Unclassified")) + '</span>'
         + '<span class="clp-pill clp-pill--muted">' + _esc(doc.shipping_responsibility || __("Unassigned")) + '</span>'
         + '<span class="clp-pill clp-pill--' + _aTone(doc.analysis_status) + '">' + _esc(_aLabel(doc.analysis_status)) + '</span>';
}

function _metricsHtml(doc, st, isPo) {
    return _mCard(__("Source"), isPo ? __("Purchase Order") : __("Delivery Note"))
         + _mCard(__("Destination"), doc.destination_zone || "—")
         + _mCard(__("Departure"), doc.departure_date || "—")
         + _mCard(__("Status"), doc.status || __("Planning"))
         + _mCard(__("Rows"), String(st.total))
         + _mCard(__("Selected"), String(st.selected));
}

function _mCard(label, value) {
    return '<div class="clp-metric"><div class="clp-metric-label">' + _esc(label) + '</div><div class="clp-metric-value">' + _esc(value) + '</div></div>';
}

function _capacityHtml(doc, st) {
    return _gHtml(__("Weight"), st.wPct, st.totalW.toFixed(1) + " kg " + __("loaded"))
         + _gHtml(__("Volume"), st.vPct, st.totalV.toFixed(3) + " m³ " + __("loaded"))
         + '<div class="clp-kpis">'
         + _kpi(__("Selected"), String(st.selected))
         + _kpi(__("Total"), String(st.total))
         + _kpi(__("Partners"), String(st.partners))
         + _kpi(__("Limiting"), doc.limiting_factor || __("Balanced"))
         + '</div>';
}

function _gHtml(label, pct, sub) {
    var cls = pct > 100 ? "clp-gauge--danger" : pct > 85 ? "clp-gauge--warn" : "clp-gauge--ok";
    return '<div class="clp-gauge"><div class="clp-gauge-head"><span class="clp-gauge-label">' + _esc(label) + '</span><span class="clp-gauge-pct">' + pct.toFixed(1) + '%</span></div>'
         + '<div class="clp-gauge-track"><div class="clp-gauge-fill ' + cls + '" style="width:' + Math.min(pct, 100) + '%"></div></div>'
         + '<div class="clp-gauge-sub">' + _esc(sub) + '</div></div>';
}

function _kpi(label, value) {
    return '<div class="clp-kpi"><div class="clp-kpi-value">' + _esc(value) + '</div><div class="clp-kpi-label">' + _esc(label) + '</div></div>';
}

function _insightsHtml(doc) {
    return '<div class="clp-meta-grid">'
         + _tile(__("Container Profile"), doc.container_profile || "—")
         + _tile(__("Company"), doc.company || "—")
         + _tile(__("Dispatcher"), doc.dispatcher || __("Unassigned"))
         + _tile(__("Grouping"), doc.group_by_customer ? __("By Customer") : __("Standard"))
         + '</div>';
}

function _tile(label, value) {
    return '<div class="clp-meta-tile"><div class="clp-meta-label">' + _esc(label) + '</div><div class="clp-meta-value">' + _esc(value) + '</div></div>';
}

function _guideHtml(sc) {
    return '<p class="clp-guide-text">' + _esc(sc.guidance) + '</p>'
         + '<ol class="clp-guide-steps">' + sc.steps.map(function(s) { return '<li>' + _esc(s) + '</li>'; }).join('') + '</ol>';
}

function _previewHtml(doc, isPo) {
    var rows = (doc.shipments || []).slice().sort(function(a, b) { return (a.sequence || 0) - (b.sequence || 0); });
    if (!rows.length) return '<div class="clp-empty">' + __("No rows yet. Use the Add Row button below or click Suggest.") + '</div>';
    var sH = isPo ? __("Purchase Order") : __("Delivery Note");
    var pH = isPo ? __("Supplier") : __("Customer");
    var body = rows.map(function(r) {
        var src = isPo ? (r.purchase_order || "—") : (r.delivery_note || "—");
        var p = isPo ? (r.supplier || "—") : (r.customer || "—");
        var sel = Number(r.selected || 0);
        return '<tr><td class="clp-src">' + _esc(src) + '</td><td>' + _esc(p)
             + '</td><td>' + Number(r.shipment_weight_kg || 0).toFixed(1) + ' kg</td>'
             + '<td>' + Number(r.shipment_volume_m3 || 0).toFixed(3) + ' m³</td>'
             + '<td><span class="clp-seq">' + (Number(r.sequence || 0) || "—") + '</span></td>'
             + '<td><span class="clp-pill-sm ' + (sel ? "is-in" : "is-out") + '">' + (sel ? __("Selected") : __("Excluded")) + '</span></td></tr>';
    }).join('');
    return '<div class="clp-table-wrap"><table class="clp-table"><thead><tr><th>' + sH + '</th><th>' + pH + '</th><th>'
         + __("Weight") + '</th><th>' + __("Volume") + '</th><th>' + __("Seq") + '</th><th>' + __("Status") + '</th></tr></thead><tbody>'
         + body + '</tbody></table></div>';
}


/* ═══════════════════════════════════════════════════════
 * SCENARIO CONFIG
 * ═══════════════════════════════════════════════════════ */
function _scenario(flow, resp) {
    if (flow === "Inbound") return {
        tone: "blue",
        subtitle: __("Consolidate supplier purchases into this inbound container before receiving and QC."),
        guidance: __("Build from Purchase Orders. Only create draft Purchase Receipts when the shipment is confirmed."),
        steps: [__("Lock container profile before adding PO lines."), __("Use Suggest to optimise capacity."), __("Create Purchase Receipts after loading confirmed.")],
    };
    if (flow === "Domestic") return {
        tone: "green",
        subtitle: __("Batch local distribution deliveries for Morocco routing and dispatch."),
        guidance: __("Keep only delivery notes that belong in the same physical run, then create a Delivery Trip."),
        steps: [__("Validate zone, dispatcher, grouping."), __("Sequence shipments for routing."), __("Create Delivery Trip once confirmed.")],
    };
    if (flow === "Outbound" && resp === "Customer") return {
        tone: "rose",
        subtitle: __("Customer-managed export — Orderlift prepares but does not own transport."),
        guidance: __("Advisory plan only. Avoid creating execution records unless responsibility changes."),
        steps: [__("Use for packaging readiness only."), __("Do not create Delivery Trip.")],
    };
    return {
        tone: "slate",
        subtitle: __("Plan outbound container loads when Orderlift manages the shipment."),
        guidance: __("Source from Delivery Notes, optimise capacity, create Delivery Trip for the local leg."),
        steps: [__("Add delivery notes for this movement."), __("Run analysis after changes."), __("Create Delivery Trip for Orderlift-managed legs.")],
    };
}


/* ═══════════════════════════════════════════════════════
 * STATS + ANALYSIS HELPERS
 * ═══════════════════════════════════════════════════════ */
function _stats(doc) {
    var rows = doc.shipments || [];
    var sel = rows.filter(function(r) { return Number(r.selected || 0); });
    var pf = doc.source_type === "Purchase Order" ? "supplier" : "customer";
    var ps = new Set(rows.map(function(r) { return r[pf]; }).filter(Boolean));
    return {
        total: rows.length, selected: sel.length, partners: ps.size,
        totalW: Number(doc.total_weight_kg || 0), totalV: Number(doc.total_volume_m3 || 0),
        wPct: Number(doc.weight_utilization_pct || 0), vPct: Number(doc.volume_utilization_pct || 0),
    };
}

function _aTone(s) {
    return s === "over_capacity" ? "danger" : s === "incomplete_data" ? "warning" : "success";
}
function _aLabel(s) {
    return s === "over_capacity" ? __("Over Capacity") : s === "incomplete_data" ? __("Incomplete Data") : __("Ready");
}


/* ═══════════════════════════════════════════════════════
 * ACTION BINDING + SERVER CALLS
 * ═══════════════════════════════════════════════════════ */
function _bindActions(frm, $el) {
    $el.off("click", ".clp-btn[data-action]");
    $el.on("click", ".clp-btn[data-action]", async function () {
        if ($(this).is("[disabled]")) return;
        var a = $(this).data("action");
        if (a === "run-analysis") await _doAnalysis(frm);
        else if (a === "suggest") await _doSuggest(frm);
        else if (a === "cockpit") frappe.set_route("logistics-hub-cockpit");
        else if (a === "create-prs") await _doPRs(frm);
        else if (a === "create-trip") await _doTrip(frm);
    });
}

async function _doAnalysis(frm) {
    if (frm.doc.__islocal) { frappe.show_alert({ message: __("Save first"), indicator: "orange" }); return; }
    await frappe.call({ method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.run_load_plan_analysis", args: { load_plan_name: frm.doc.name }, freeze: true, freeze_message: __("Running analysis…") });
    await frm.reload_doc();
}

async function _doSuggest(frm) {
    if (frm.doc.__islocal) { frappe.show_alert({ message: __("Save first"), indicator: "orange" }); return; }
    var r = await frappe.call({ method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.suggest_shipments", args: { load_plan_name: frm.doc.name }, freeze: true, freeze_message: __("Finding best mix…") });
    var sel = (r.message && r.message.selected) || [];
    if (!sel.length) { frappe.show_alert({ message: __("No fitting suggestions."), indicator: "orange" }); return; }
    if (frm.doc.source_type === "Purchase Order") {
        frappe.msgprint({ title: __("Inbound"), message: __("PO append coming in next release."), indicator: "blue" });
        return;
    }
    var dns = sel.map(function(x) { return x.delivery_note; }).filter(Boolean);
    await frappe.call({ method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.append_shipments", args: { load_plan_name: frm.doc.name, delivery_notes: dns }, freeze: true, freeze_message: __("Adding…") });
    await frm.reload_doc();
    frappe.show_alert({ message: __("Shipments added."), indicator: "green" });
}

async function _doPRs(frm) {
    if (!await _confirm(__("Create draft Purchase Receipts?"))) return;
    var r = await frappe.call({ method: "orderlift.logistics.utils.inbound_receipt.create_draft_purchase_receipts", args: { load_plan_name: frm.doc.name }, freeze: true, freeze_message: __("Creating…") });
    if (r.message) frappe.msgprint({ title: __("Purchase Receipts"), message: r.message.message, indicator: "green" });
    await frm.reload_doc();
}

async function _doTrip(frm) {
    if (!await _confirm(__("Create Delivery Trip?"))) return;
    var r = await frappe.call({ method: "orderlift.logistics.utils.domestic_dispatch.create_delivery_trip_from_load_plan", args: { load_plan_name: frm.doc.name }, freeze: true, freeze_message: __("Creating…") });
    if (r.message && r.message.delivery_trip) frappe.set_route("Form", "Delivery Trip", r.message.delivery_trip);
}

function _confirm(msg) { return new Promise(function(res) { frappe.confirm(msg, function() { res(true); }, function() { res(false); }); }); }


/* ═══════════════════════════════════════════════════════
 * PERMISSION HELPERS
 * ═══════════════════════════════════════════════════════ */
function _canPR(frm) {
    return frm.doc.docstatus === 1 && frm.doc.flow_scope === "Inbound"
        && frm.doc.source_type === "Purchase Order"
        && ["Loading", "In Transit", "Delivered"].indexOf(frm.doc.status) !== -1;
}
function _canTrip(frm) {
    return frm.doc.docstatus === 1 && frm.doc.source_type === "Delivery Note"
        && (frm.doc.flow_scope === "Domestic" || (frm.doc.flow_scope === "Outbound" && frm.doc.shipping_responsibility === "Orderlift"));
}


/* ═══════════════════════════════════════════════════════
 * TOOLBAR + CHILD TABLE + PAGE INDICATOR
 * ═══════════════════════════════════════════════════════ */
function _addToolbarButtons(frm) {
    if (frm.doc.__islocal) return;
    frm.add_custom_button(__("Run Analysis"), function() { _doAnalysis(frm); }, __("Planning"));
    frm.add_custom_button(__("Suggest Shipments"), function() { _doSuggest(frm); }, __("Planning"));
    if (_canPR(frm)) frm.add_custom_button(__("Draft Purchase Receipts"), function() { _doPRs(frm); }, __("Actions"));
    if (_canTrip(frm)) frm.add_custom_button(__("Create Delivery Trip"), function() { _doTrip(frm); }, __("Actions"));
}

function _toggleChildColumns(frm) {
    var g = frm.fields_dict.shipments && frm.fields_dict.shipments.grid;
    if (!g) return;
    var po = frm.doc.source_type === "Purchase Order";
    g.update_docfield_property("delivery_note", "hidden", po ? 1 : 0);
    g.update_docfield_property("purchase_order", "hidden", po ? 0 : 1);
    g.update_docfield_property("customer", "hidden", po ? 1 : 0);
    g.update_docfield_property("supplier", "hidden", po ? 0 : 1);
}

function _setPageIndicator(frm) {
    var f = frm.doc.flow_scope || "Planning";
    var s = frm.doc.analysis_status;
    var c = s === "over_capacity" ? "red" : s === "incomplete_data" ? "orange"
          : f === "Inbound" ? "blue" : f === "Domestic" ? "green" : "purple";
    frm.page.set_indicator(__(f), c);
}
