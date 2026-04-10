frappe.ui.form.on("Container Load Plan", {
    refresh(frm) {
        _toggleChildColumns(frm);
        _renderWorkspace(frm);
        _updatePageIndicator(frm);
    },

    flow_scope(frm) {
        _toggleChildColumns(frm);
        _renderWorkspace(frm);
        _updatePageIndicator(frm);
    },

    shipping_responsibility(frm) {
        _renderWorkspace(frm);
        _updatePageIndicator(frm);
    },

    source_type(frm) {
        _toggleChildColumns(frm);
        _renderWorkspace(frm);
    },

    status(frm) {
        _renderWorkspace(frm);
        _updatePageIndicator(frm);
    },

    analysis_status: _renderWorkspace,
    container_profile: _renderWorkspace,
    destination_zone: _renderWorkspace,
    company: _renderWorkspace,
    departure_date: _renderWorkspace,
    dispatcher: _renderWorkspace,
    group_by_customer: _renderWorkspace,

    shipments_add: _renderWorkspace,
    shipments_remove: _renderWorkspace,
});

frappe.ui.form.on("Load Plan Shipment", {
    delivery_note(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.delivery_note) {
            _renderWorkspace(frm);
            return;
        }

        frappe.db.get_value(
            "Delivery Note",
            row.delivery_note,
            ["customer", "custom_total_weight_kg", "custom_total_volume_m3"]
        ).then((r) => {
            const data = r.message || {};
            frappe.model.set_value(cdt, cdn, "customer", data.customer || "");
            frappe.model.set_value(cdt, cdn, "shipment_weight_kg", data.custom_total_weight_kg || 0);
            frappe.model.set_value(cdt, cdn, "shipment_volume_m3", data.custom_total_volume_m3 || 0);
            _renderWorkspace(frm);
        });
    },

    purchase_order(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.purchase_order) {
            _renderWorkspace(frm);
            return;
        }

        frappe.db.get_value("Purchase Order", row.purchase_order, ["supplier"]).then((r) => {
            const data = r.message || {};
            frappe.model.set_value(cdt, cdn, "supplier", data.supplier || "");
            _renderWorkspace(frm);
        });
    },

    selected: _renderWorkspace,
    sequence: _renderWorkspace,
});

function _renderWorkspace(frm) {
    const htmlField = frm.fields_dict.capacity_dashboard_html;
    if (!htmlField) return;

    const scenario = _getScenarioConfig(frm.doc.flow_scope, frm.doc.shipping_responsibility);
    const stats = _getPlanStats(frm.doc);
    const html = `
        <section class="ol-clp-workspace ${scenario.rootClass}">
            <div class="ol-clp-subbar">
                <div class="ol-clp-subbar-left">
                    <div class="ol-clp-breadcrumb">${__("Container Load Plans")} / ${frappe.utils.escape_html(frm.doc.name || __("New"))}</div>
                    <div class="ol-clp-title-row">
                        <div>
                            <h2 class="ol-clp-page-title">${frappe.utils.escape_html(frm.doc.container_label || __("New Container Load Plan"))}</h2>
                            <p class="ol-clp-page-subtitle">${frappe.utils.escape_html(scenario.subtitle)}</p>
                        </div>
                        <div class="ol-clp-title-pills">
                            <span class="ol-clp-pill ${scenario.badgeClass}">${frappe.utils.escape_html(frm.doc.flow_scope || __("Unclassified"))}</span>
                            <span class="ol-clp-pill ol-clp-pill--neutral">${frappe.utils.escape_html(frm.doc.shipping_responsibility || __("Unassigned"))}</span>
                            <span class="ol-clp-pill ${_analysisClass(frm.doc.analysis_status)}">${frappe.utils.escape_html(_analysisLabel(frm.doc.analysis_status))}</span>
                        </div>
                    </div>
                </div>
                <div class="ol-clp-toolbar">
                    ${_layoutButtonHtml("run-analysis", __("Run Analysis"), frm.doc.__islocal)}
                    ${_layoutButtonHtml("suggest-shipments", __("Suggest"), frm.doc.__islocal)}
                    ${_layoutButtonHtml("open-cockpit", __("Cockpit"), false, "secondary")}
                    ${_layoutButtonHtml("create-prs", __("Draft PRs"), !_canCreateDraftPRs(frm), "secondary")}
                    ${_layoutButtonHtml("create-trip", __("Delivery Trip"), !_canCreateTrip(frm), "secondary")}
                </div>
            </div>

            <div class="ol-clp-stats-row">
                ${_miniMetricHtml(__("Flow"), frm.doc.flow_scope || __("Not set"), scenario.metricTone)}
                ${_miniMetricHtml(__("Source"), frm.doc.source_type || __("Not set"), "soft")}
                ${_miniMetricHtml(__("Destination Zone"), frm.doc.destination_zone || __("Not set"), "soft")}
                ${_miniMetricHtml(__("Departure"), _displayValue(frm.doc.departure_date), "soft")}
                ${_miniMetricHtml(__("Rows"), String(stats.totalShipments), "soft")}
                ${_miniMetricHtml(__("Selected"), String(stats.selectedShipments), "soft")}
            </div>

            <div class="ol-clp-layout-grid">
                <div class="ol-clp-main-column">
                    <section class="ol-clp-card ol-clp-card--config">
                        <div class="ol-clp-section-head">
                            <div>
                                <h3>${__("Plan Configuration")}</h3>
                                <p>${__("Edit the actual logistics fields below. The form controls remain fully functional.")}</p>
                            </div>
                        </div>
                        <div id="ol-clp-config-grid" class="ol-clp-config-grid"></div>
                    </section>

                    <section class="ol-clp-card ol-clp-card--shipments">
                        <div class="ol-clp-section-head">
                            <div>
                                <h3>${__("Shipments")}</h3>
                                <p>${frappe.utils.escape_html(_shipmentSubtitle(frm.doc))}</p>
                            </div>
                            <span class="ol-clp-chip">${stats.selectedShipments}/${stats.totalShipments} ${__("selected")}</span>
                        </div>
                        <div class="ol-clp-source-preview">${_shipmentPreviewHtml(frm.doc)}</div>
                        <div id="ol-clp-shipments-slot" class="ol-clp-slot ol-clp-slot--grid"></div>
                    </section>

                    <section class="ol-clp-card ol-clp-card--notes">
                        <div class="ol-clp-section-head">
                            <div>
                                <h3>${__("Notes & Internal Context")}</h3>
                                <p>${__("Capture dispatcher instructions, handoff details, or shipment caveats for the team.")}</p>
                            </div>
                        </div>
                        <div id="ol-clp-notes-slot" class="ol-clp-slot"></div>
                    </section>
                </div>

                <aside class="ol-clp-side-column">
                    <section class="ol-clp-card ol-clp-card--capacity">
                        <div class="ol-clp-section-head">
                            <div>
                                <h3>${__("Capacity")}</h3>
                                <p>${__("Real-time utilization of the current selected rows in this load plan.")}</p>
                            </div>
                        </div>
                        ${_capacityWidgetHtml(frm.doc)}
                    </section>

                    <section class="ol-clp-card ol-clp-card--meta">
                        <div class="ol-clp-section-head">
                            <div>
                                <h3>${__("Document Insights")}</h3>
                                <p>${__("Quick context for ownership, profile, and planning posture.")}</p>
                            </div>
                        </div>
                        <div class="ol-clp-meta-grid">
                            ${_metaTileHtml(__("Container Profile"), frm.doc.container_profile || __("Not selected"))}
                            ${_metaTileHtml(__("Company"), frm.doc.company || __("Not selected"))}
                            ${_metaTileHtml(__("Dispatcher"), frm.doc.dispatcher || __("Unassigned"))}
                            ${_metaTileHtml(__("Grouping"), frm.doc.group_by_customer ? __("Customer-first") : __("Standard"))}
                        </div>
                    </section>

                    <section class="ol-clp-card ol-clp-card--guide">
                        <div class="ol-clp-section-head">
                            <div>
                                <h3>${__("Scenario Guide")}</h3>
                                <p>${__("What the team should do next for this specific logistics mode.")}</p>
                            </div>
                        </div>
                        <div class="ol-clp-guide-text">${frappe.utils.escape_html(scenario.guidance)}</div>
                        <ul class="ol-clp-guide-list">
                            ${scenario.steps.map((step) => `<li>${frappe.utils.escape_html(step)}</li>`).join("")}
                        </ul>
                    </section>
                </aside>
            </div>
        </section>
    `;

    htmlField.$wrapper.html(html);
    _mountControl(frm, "container_label", "#ol-clp-config-grid");
    _mountControl(frm, "container_profile", "#ol-clp-config-grid");
    _mountControl(frm, "company", "#ol-clp-config-grid");
    _mountControl(frm, "flow_scope", "#ol-clp-config-grid");
    _mountControl(frm, "shipping_responsibility", "#ol-clp-config-grid");
    _mountControl(frm, "source_type", "#ol-clp-config-grid");
    _mountControl(frm, "destination_zone", "#ol-clp-config-grid");
    _mountControl(frm, "departure_date", "#ol-clp-config-grid");
    _mountControl(frm, "dispatcher", "#ol-clp-config-grid");
    _mountControl(frm, "status", "#ol-clp-config-grid");
    _mountControl(frm, "group_by_customer", "#ol-clp-config-grid");
    _mountControl(frm, "shipments", "#ol-clp-shipments-slot");
    _mountControl(frm, "notes", "#ol-clp-notes-slot");
    _bindLayoutActions(frm, htmlField.$wrapper);
}

function _mountControl(frm, fieldname, targetSelector) {
    const field = frm.fields_dict[fieldname];
    if (!field) return;

    const $target = frm.fields_dict.capacity_dashboard_html.$wrapper.find(targetSelector);
    if (!$target.length) return;

    const $control = $(field.wrapper).closest('.frappe-control');
    if (!$control.length) return;

    $control.addClass("ol-clp-mounted-control");
    if (fieldname === "shipments") {
        $control.addClass("ol-clp-grid-control");
    }
    if (fieldname === "notes") {
        $control.addClass("ol-clp-notes-control");
    }
    $target.append($control);
}

function _bindLayoutActions(frm, $wrapper) {
    $wrapper.off("click", ".ol-clp-layout-btn");
    $wrapper.on("click", ".ol-clp-layout-btn", async function () {
        if ($(this).is("[disabled]")) return;
        const action = $(this).data("action");

        if (action === "run-analysis") {
            await _runAnalysis(frm);
        } else if (action === "suggest-shipments") {
            await _suggestShipments(frm);
        } else if (action === "open-cockpit") {
            frappe.set_route("logistics-hub-cockpit");
        } else if (action === "create-prs") {
            await _createDraftPRs(frm);
        } else if (action === "create-trip") {
            await _createDeliveryTrip(frm);
        }
    });
}

function _getScenarioConfig(flowScope, responsibility) {
    const flow = flowScope || "Unclassified";
    const resp = responsibility || "Unassigned";

    if (flow === "Inbound") {
        return {
            rootClass: "is-inbound",
            badgeClass: "ol-clp-pill--blue",
            metricTone: "accent-blue",
            subtitle: __("Plan supplier-side inbound consolidation, then transition cleanly into receiving and QC in Morocco."),
            guidance: __("Inbound plans should be built from Purchase Orders, filled carefully for capacity, and only converted into draft Purchase Receipts when the import leg is operationally confirmed."),
            steps: [
                __("Lock the container profile and source type before adding supplier lines."),
                __("Use Suggest to build a balanced inbound mix without overloading capacity."),
                __("Only create draft Purchase Receipts once the inbound leg is loading, in transit, or delivered."),
            ],
        };
    }

    if (flow === "Domestic") {
        return {
            rootClass: "is-domestic",
            badgeClass: "ol-clp-pill--green",
            metricTone: "accent-green",
            subtitle: __("Coordinate Morocco distribution runs with a cleaner planning view before creating the final Delivery Trip."),
            guidance: __("Domestic plans should stay tightly aligned with route/vehicle execution. Keep only the delivery notes that truly belong in the same run."),
            steps: [
                __("Validate destination zone, dispatcher, and local grouping strategy."),
                __("Use the shipment grid to sequence and curate the actual distribution run."),
                __("Create the Delivery Trip only after the domestic plan is operationally confirmed."),
            ],
        };
    }

    if (flow === "Outbound" && resp === "Customer") {
        return {
            rootClass: "is-customer",
            badgeClass: "ol-clp-pill--rose",
            metricTone: "accent-rose",
            subtitle: __("Customer-managed export means Orderlift prepares the shipment, but does not own the transport execution flow."),
            guidance: __("This scenario should remain mostly advisory. The system should emphasize readiness, not generate extra internal logistics execution steps."),
            steps: [
                __("Use the plan only for visibility and packaging readiness, not for operational dispatch."),
                __("Do not create Delivery Trip or extra shipping execution records unless the responsibility changes."),
            ],
        };
    }

    return {
        rootClass: "is-outbound",
        badgeClass: "ol-clp-pill--orange",
        metricTone: "accent-orange",
        subtitle: __("Organize outbound loads cleanly before handoff to execution when Orderlift manages the shipment or local leg."),
        guidance: __("Outbound plans should be operationally crisp: the right source documents, the right sequence, and a clear view of remaining capacity before execution starts."),
        steps: [
            __("Keep source documents limited to the delivery notes that genuinely belong in the same outbound movement."),
            __("Run analysis after every major shipment change to keep utilization current."),
            __("Create Delivery Trip only when Orderlift is handling the local execution leg."),
        ],
    };
}

function _getPlanStats(doc) {
    const rows = doc.shipments || [];
    const selectedRows = rows.filter((row) => Number(row.selected || 0));
    const partnerField = doc.source_type === "Purchase Order" ? "supplier" : "customer";
    const partners = new Set(rows.map((row) => row[partnerField]).filter(Boolean));

    return {
        totalShipments: rows.length,
        selectedShipments: selectedRows.length,
        totalWeight: Number(doc.total_weight_kg || 0),
        totalVolume: Number(doc.total_volume_m3 || 0),
        weightPct: Number(doc.weight_utilization_pct || 0),
        volumePct: Number(doc.volume_utilization_pct || 0),
        uniquePartners: partners.size,
    };
}

function _capacityWidgetHtml(doc) {
    const stats = _getPlanStats(doc);
    return `
        <div class="ol-clp-capacity-stack">
            ${_gaugeHtml(__("Weight"), stats.weightPct, `${stats.totalWeight.toFixed(1)} kg`, __("loaded"))}
            ${_gaugeHtml(__("Volume"), stats.volumePct, `${stats.totalVolume.toFixed(3)} m³`, __("loaded"))}
            <div class="ol-clp-metric-grid">
                ${_metaTileHtml(__("Selected Rows"), String(stats.selectedShipments))}
                ${_metaTileHtml(__("Total Rows"), String(stats.totalShipments))}
                ${_metaTileHtml(__("Partners"), String(stats.uniquePartners))}
                ${_metaTileHtml(__("Limiting Factor"), doc.limiting_factor || __("Balanced"))}
            </div>
        </div>
    `;
}

function _shipmentPreviewHtml(doc) {
    const rows = (doc.shipments || []).slice().sort((a, b) => Number(a.sequence || 0) - Number(b.sequence || 0));
    const isPo = doc.source_type === "Purchase Order";
    if (!rows.length) {
        return `<div class="ol-clp-preview-empty">${__("No rows added yet. Save the plan, use Suggest, or add source rows below.")}</div>`;
    }

    return `
        <div class="ol-clp-preview-table-wrap">
            <table class="ol-clp-preview-table">
                <thead>
                    <tr>
                        <th>${__("Source")}</th>
                        <th>${__(isPo ? "Supplier" : "Customer")}</th>
                        <th>${__("Weight")}</th>
                        <th>${__("Volume")}</th>
                        <th>${__("Seq")}</th>
                        <th>${__("State")}</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows.map((row) => `
                        <tr>
                            <td>
                                <div class="ol-clp-preview-source">${frappe.utils.escape_html(isPo ? (row.purchase_order || "—") : (row.delivery_note || "—"))}</div>
                                <div class="ol-clp-preview-type">${frappe.utils.escape_html(doc.source_type || "")}</div>
                            </td>
                            <td>${frappe.utils.escape_html(isPo ? (row.supplier || "—") : (row.customer || "—"))}</td>
                            <td>${Number(row.shipment_weight_kg || 0).toFixed(1)} kg</td>
                            <td>${Number(row.shipment_volume_m3 || 0).toFixed(3)} m³</td>
                            <td><span class="ol-clp-seq">${Number(row.sequence || 0) || "—"}</span></td>
                            <td><span class="ol-clp-row-pill ${Number(row.selected || 0) ? "is-selected" : "is-muted"}">${Number(row.selected || 0) ? __("Selected") : __("Excluded")}</span></td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        </div>
    `;
}

function _shipmentSubtitle(doc) {
    if (doc.source_type === "Purchase Order") {
        return __("Purchase Orders and inbound supplier rows that belong to this container plan.");
    }
    return __("Delivery Notes grouped into this plan, with sequence and inclusion controlled from the grid below.");
}

function _layoutButtonHtml(action, label, disabled, tone) {
    const klass = tone === "secondary" ? "ol-clp-layout-btn is-secondary" : "ol-clp-layout-btn";
    return `<button type="button" class="${klass}" data-action="${frappe.utils.escape_html(action)}" ${disabled ? "disabled" : ""}>${frappe.utils.escape_html(label)}</button>`;
}

function _miniMetricHtml(label, value, tone) {
    return `
        <div class="ol-clp-mini ${tone ? `is-${tone}` : ""}">
            <div class="ol-clp-mini-label">${frappe.utils.escape_html(label)}</div>
            <div class="ol-clp-mini-value">${frappe.utils.escape_html(value)}</div>
        </div>
    `;
}

function _metaTileHtml(label, value) {
    return `
        <div class="ol-clp-meta-tile">
            <div class="ol-clp-meta-label">${frappe.utils.escape_html(label)}</div>
            <div class="ol-clp-meta-value">${frappe.utils.escape_html(value)}</div>
        </div>
    `;
}

function _gaugeHtml(label, pct, value, suffix) {
    return `
        <div class="ol-clp-gauge-block">
            <div class="ol-clp-gauge-head">
                <span class="ol-clp-gauge-title">${frappe.utils.escape_html(label)}</span>
                <span class="ol-clp-gauge-pct">${pct.toFixed(1)}%</span>
            </div>
            <div class="ol-clp-gauge-track"><div class="ol-clp-gauge-fill ${_fillClass(pct)}" style="width:${Math.min(pct, 100)}%"></div></div>
            <div class="ol-clp-gauge-caption">${frappe.utils.escape_html(value)} ${frappe.utils.escape_html(suffix)}</div>
        </div>
    `;
}

function _fillClass(pct) {
    if (pct > 100) return "is-danger";
    if (pct > 85) return "is-warning";
    return "is-ok";
}

function _analysisClass(status) {
    if (status === "over_capacity") return "ol-clp-pill--danger";
    if (status === "incomplete_data") return "ol-clp-pill--warning";
    return "ol-clp-pill--success";
}

function _analysisLabel(status) {
    if (status === "over_capacity") return __("Over Capacity");
    if (status === "incomplete_data") return __("Incomplete Data");
    return __("Ready");
}

function _displayValue(value) {
    return value || __("Not set");
}

async function _runAnalysis(frm) {
    if (frm.doc.__islocal) {
        frappe.show_alert({ message: __("Save the plan before running analysis."), indicator: "orange" });
        return;
    }

    await frappe.call({
        method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.run_load_plan_analysis",
        args: { load_plan_name: frm.doc.name },
        freeze: true,
        freeze_message: __("Running logistics analysis..."),
    });
    await frm.reload_doc();
}

async function _suggestShipments(frm) {
    if (frm.doc.__islocal) {
        frappe.show_alert({ message: __("Save the plan before suggesting shipments."), indicator: "orange" });
        return;
    }

    const r = await frappe.call({
        method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.suggest_shipments",
        args: { load_plan_name: frm.doc.name },
        freeze: true,
        freeze_message: __("Finding best shipment mix..."),
    });

    const selected = (r.message && r.message.selected) || [];
    if (!selected.length) {
        frappe.show_alert({ message: __("No fitting suggestions found for this plan."), indicator: "orange" });
        return;
    }

    if (frm.doc.source_type === "Purchase Order") {
        frappe.msgprint({
            title: __("Inbound Suggestions"),
            message: __("Inbound suggestions are available in the planning engine, but appending Purchase Orders from the form will be wired next."),
            indicator: "blue",
        });
        return;
    }

    const dnList = selected.map((row) => row.delivery_note).filter(Boolean);
    await frappe.call({
        method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.append_shipments",
        args: { load_plan_name: frm.doc.name, delivery_notes: dnList },
        freeze: true,
        freeze_message: __("Appending suggested shipments..."),
    });
    await frm.reload_doc();
    frappe.show_alert({ message: __("Suggested shipments added."), indicator: "green" });
}

async function _createDraftPRs(frm) {
    const proceed = await _confirmAsync(__("Create draft Purchase Receipts for the Purchase Orders in this inbound plan?"));
    if (!proceed) return;

    const r = await frappe.call({
        method: "orderlift.logistics.utils.inbound_receipt.create_draft_purchase_receipts",
        args: { load_plan_name: frm.doc.name },
        freeze: true,
        freeze_message: __("Creating draft Purchase Receipts..."),
    });
    if (r.message) {
        frappe.msgprint({
            title: __("Purchase Receipts"),
            message: r.message.message,
            indicator: "green",
        });
    }
    await frm.reload_doc();
}

async function _createDeliveryTrip(frm) {
    const proceed = await _confirmAsync(__("Create a Delivery Trip for the Delivery Notes currently grouped in this plan?"));
    if (!proceed) return;

    const r = await frappe.call({
        method: "orderlift.logistics.utils.domestic_dispatch.create_delivery_trip_from_load_plan",
        args: { load_plan_name: frm.doc.name },
        freeze: true,
        freeze_message: __("Creating Delivery Trip..."),
    });
    if (r.message && r.message.delivery_trip) {
        frappe.set_route("Form", "Delivery Trip", r.message.delivery_trip);
    }
}

function _canCreateDraftPRs(frm) {
    return (
        frm.doc.docstatus === 1
        && frm.doc.flow_scope === "Inbound"
        && frm.doc.source_type === "Purchase Order"
        && ["Loading", "In Transit", "Delivered"].includes(frm.doc.status)
    );
}

function _canCreateTrip(frm) {
    return (
        frm.doc.docstatus === 1
        && frm.doc.source_type === "Delivery Note"
        && (frm.doc.flow_scope === "Domestic" || (frm.doc.flow_scope === "Outbound" && frm.doc.shipping_responsibility === "Orderlift"))
    );
}

function _toggleChildColumns(frm) {
    const grid = frm.fields_dict.shipments && frm.fields_dict.shipments.grid;
    if (!grid) return;

    const isPo = frm.doc.source_type === "Purchase Order";
    grid.update_docfield_property("delivery_note", "hidden", isPo ? 1 : 0);
    grid.update_docfield_property("purchase_order", "hidden", isPo ? 0 : 1);
    grid.update_docfield_property("customer", "hidden", isPo ? 1 : 0);
    grid.update_docfield_property("supplier", "hidden", isPo ? 0 : 1);
    frm.refresh_fields();
}

function _updatePageIndicator(frm) {
    const flow = frm.doc.flow_scope || "Planning";
    const status = frm.doc.analysis_status;
    const color = status === "over_capacity"
        ? "red"
        : status === "incomplete_data"
            ? "orange"
            : flow === "Inbound"
                ? "blue"
                : flow === "Domestic"
                    ? "green"
                    : "orange";
    frm.page.set_indicator(__(flow), color);
}

function _confirmAsync(message) {
    return new Promise((resolve) => {
        frappe.confirm(message, () => resolve(true), () => resolve(false));
    });
}
