frappe.provide("orderlift.logistics_cockpit");

frappe.pages["logistics-hub-cockpit"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Logistics Hub Cockpit"),
        single_column: true,
    });

    orderlift.logistics_cockpit.instance = new orderlift.logistics_cockpit.Cockpit(page);
};

frappe.pages["logistics-hub-cockpit"].on_page_show = function () {
    if (orderlift.logistics_cockpit.instance) {
        orderlift.logistics_cockpit.instance._subscribeRealtime();
    }
};

frappe.pages["logistics-hub-cockpit"].on_page_hide = function () {
    if (orderlift.logistics_cockpit.instance) {
        orderlift.logistics_cockpit.instance._unsubscribeRealtime();
    }
};

orderlift.logistics_cockpit.Cockpit = class Cockpit {
    constructor(page) {
        this.page = page;
        this.loadPlan = null;
        this._realtimeHandler = null;
        this._subscribedPlan  = null;
        this.setupControls();
        this.renderShell();
        this.bootstrapFromRoute();
    }

    setupControls() {
        this.loadPlanControl = this.page.add_field({
            label: __("Container Load Plan"),
            fieldname: "container_load_plan",
            fieldtype: "Link",
            options: "Container Load Plan",
            reqd: 1,
            change: () => {
                const newPlan = this.loadPlanControl.get_value();
                if (newPlan === this.loadPlan) return;
                this._unsubscribeRealtime();
                this.loadPlan = newPlan;
                if (this.loadPlan) {
                    this.refresh();
                    this._subscribeRealtime();
                }
            },
        });

        this.page.set_primary_action(__("Auto-Suggest"), () => this.autoSuggest(), "magic");
        this.page.set_secondary_action(__("Refresh"), () => this.refresh());

        this.page.add_menu_item(__("Open Load Plan"), () => {
            if (!this.loadPlan) return;
            frappe.set_route("Form", "Container Load Plan", this.loadPlan);
        });

        this.page.add_menu_item(__("Run Analysis"), async () => {
            if (!this.loadPlan) return;
            await frappe.call({
                method:
                    "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.run_load_plan_analysis",
                args: { load_plan_name: this.loadPlan },
                freeze: true,
                freeze_message: __("Running analysis..."),
            });
            await this.refresh();
        });

        this.page.add_menu_item(__("Zone Overview"), () => this.showZoneOverview());
        this.page.add_menu_item(__("View Analytics"), () => this.showAnalytics());
    }

    bootstrapFromRoute() {
        const routeOptions = frappe.route_options || {};
        const fromRoute = routeOptions.container_load_plan || routeOptions.name;
        if (fromRoute) {
            this.loadPlan = fromRoute;
            this.loadPlanControl.set_value(fromRoute);
            this.refresh();
        }
    }

    renderShell() {
        const html = `
            <div class="ol-cockpit-wrap">
                <div class="ol-cockpit-toolbar">
                    <div class="ol-cockpit-search-wrap">
                        <input id="ol-cockpit-search" class="ol-cockpit-search" placeholder="${__("Search Delivery Note or customer")}" />
                    </div>
                    <div class="ol-cockpit-toolbar-right">
                        <span class="ol-cockpit-legend"><i class="dot ok"></i>${__("Healthy")}</span>
                        <span class="ol-cockpit-legend"><i class="dot warn"></i>${__("Watch")}</span>
                        <span class="ol-cockpit-legend"><i class="dot danger"></i>${__("Critical")}</span>
                    </div>
                </div>
                <div class="ol-cockpit-center" id="ol-cockpit-center"></div>
                <div class="ol-cockpit-grid">
                    <section class="ol-cockpit-col">
                        <div class="ol-cockpit-head">
                            <h4>${__("Pending Queue")}</h4>
                            <span id="ol-queue-count" class="ol-cockpit-chip">0</span>
                        </div>
                        <div id="ol-queue-list" class="ol-cockpit-list"></div>
                    </section>
                    <section class="ol-cockpit-col">
                        <div class="ol-cockpit-head">
                            <h4>${__("Active Container")}</h4>
                            <span id="ol-active-count" class="ol-cockpit-chip">0</span>
                        </div>
                        <div id="ol-active-list" class="ol-cockpit-list"></div>
                    </section>
                </div>
            </div>
        `;

        $(html).appendTo(this.page.main);
        this.page.main.find("#ol-cockpit-search").on("input", () => this.renderLists());
    }

    async refresh() {
        if (!this.loadPlan) {
            frappe.show_alert({ message: __("Select a Container Load Plan"), indicator: "orange" });
            return;
        }

        const r = await frappe.call({
            method:
                "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.get_cockpit_data",
            args: { load_plan_name: this.loadPlan },
            freeze: true,
            freeze_message: __("Refreshing dispatcher cockpit..."),
        });

        this.data = r.message || {};
        this.renderCenter(this.data.plan || {});
        this.renderLists();
    }

    renderCenter(plan) {
        const weightPct = Number(plan.weight_utilization_pct || 0);
        const volumePct = Number(plan.volume_utilization_pct || 0);
        const maxWeight = Number(plan.max_weight_kg || 0);
        const maxVolume = Number(plan.max_volume_m3 || 0);
        const usedWeight = Number(plan.total_weight_kg || 0);
        const usedVolume = Number(plan.total_volume_m3 || 0);
        const remainingWeight = Math.max(maxWeight - usedWeight, 0);
        const remainingVolume = Math.max(maxVolume - usedVolume, 0);
        const weightColor = this.utilizationColor(weightPct);
        const volumeColor = this.utilizationColor(volumePct);
        const statusClass = this.analysisStatusClass(plan.analysis_status);
        const factorClass = this.factorClass(plan.limiting_factor);
        const queueCount = (this.data.queue || []).length;
        const activeCount = (this.data.shipments || []).length;

        const html = `
            <div class="ol-cockpit-card">
                <div class="ol-cockpit-title-row">
                    <div>
                        <div class="ol-cockpit-title">${frappe.utils.escape_html(plan.container_label || this.loadPlan || "")}</div>
                        <div class="ol-cockpit-sub">${frappe.utils.escape_html(plan.container_profile_label || "")} | ${frappe.utils.escape_html(plan.destination_zone || "-")} | ${frappe.utils.escape_html(plan.departure_date || "")}</div>
                    </div>
                    <div class="ol-cockpit-status ${statusClass}">${frappe.utils.escape_html(plan.analysis_status || "ok")}</div>
                </div>

                <div class="ol-cockpit-kpi-grid">
                    <div class="ol-kpi-card">
                        <div class="ol-kpi-label">${__("Pending Queue")}</div>
                        <div class="ol-kpi-value">${queueCount}</div>
                    </div>
                    <div class="ol-kpi-card">
                        <div class="ol-kpi-label">${__("Loaded Shipments")}</div>
                        <div class="ol-kpi-value">${activeCount}</div>
                    </div>
                    <div class="ol-kpi-card">
                        <div class="ol-kpi-label">${__("Remaining Weight")}</div>
                        <div class="ol-kpi-value small">${remainingWeight.toFixed(3)} kg</div>
                    </div>
                    <div class="ol-kpi-card">
                        <div class="ol-kpi-label">${__("Remaining Volume")}</div>
                        <div class="ol-kpi-value small">${remainingVolume.toFixed(3)} m3</div>
                    </div>
                </div>

                <div class="ol-cockpit-meter-grid">
                    <div>
                        <div class="ol-cockpit-meter-label">${__("Weight")}</div>
                        <div class="ol-cockpit-meter">
                            <div class="ol-cockpit-meter-fill" style="width:${Math.min(weightPct, 100)}%;background:${weightColor};"></div>
                        </div>
                        <div class="ol-cockpit-meter-sub">${Number(plan.total_weight_kg || 0).toFixed(3)} / ${Number(plan.max_weight_kg || 0).toFixed(3)} kg (${weightPct.toFixed(2)}%)</div>
                    </div>
                    <div>
                        <div class="ol-cockpit-meter-label">${__("Volume")}</div>
                        <div class="ol-cockpit-meter">
                            <div class="ol-cockpit-meter-fill" style="width:${Math.min(volumePct, 100)}%;background:${volumeColor};"></div>
                        </div>
                        <div class="ol-cockpit-meter-sub">${Number(plan.total_volume_m3 || 0).toFixed(3)} / ${Number(plan.max_volume_m3 || 0).toFixed(3)} m3 (${volumePct.toFixed(2)}%)</div>
                    </div>
                </div>

                <div class="ol-cockpit-meta">${__("Limiting Factor")}: <span class="ol-factor-pill ${factorClass}">${frappe.utils.escape_html(plan.limiting_factor || "n/a")}</span></div>
            </div>
        `;

        this.page.main.find("#ol-cockpit-center").html(html);
        this.renderStackedBars(plan, this.data.shipments || []);
    }

    renderLists() {
        const query = String(this.page.main.find("#ol-cockpit-search").val() || "").trim().toLowerCase();
        const queue = this.filterRows(this.data.queue || [], query, ["delivery_note", "customer", "destination_zone"]);
        const shipments = this.filterRows(this.data.shipments || [], query, ["delivery_note", "customer"]);
        this.renderQueue(queue);
        this.renderActive(shipments);
    }

    filterRows(rows, query, keys) {
        if (!query) return rows;
        return rows.filter((row) => keys.some((key) => String(row[key] || "").toLowerCase().includes(query)));
    }

    renderQueue(queue) {
        const rows = queue
            .map((row) => {
                return `
                    <article class="ol-cockpit-item ol-draggable" draggable="true" data-dn="${frappe.utils.escape_html(row.delivery_note)}">
                        <div class="ol-cockpit-item-title">${frappe.utils.escape_html(row.delivery_note)}</div>
                        <div class="ol-cockpit-item-sub">${frappe.utils.escape_html(row.customer || "-")} - ${frappe.utils.escape_html(row.destination_zone || "")}</div>
                        <div class="ol-cockpit-item-badges">
                            ${this.metricBadge("W", row.total_weight_kg, "kg")}
                            ${this.metricBadge("V", row.total_volume_m3, "m3")}
                        </div>
                        <div class="ol-cockpit-item-metrics">${Number(row.total_weight_kg || 0).toFixed(3)} kg | ${Number(row.total_volume_m3 || 0).toFixed(3)} m3</div>
                        <div class="ol-cockpit-item-actions">
                            <button class="btn btn-xs btn-primary ol-btn-add" data-action="add" data-dn="${frappe.utils.escape_html(row.delivery_note)}">${__("Add to Container")}</button>
                        </div>
                    </article>
                `;
            })
            .join("");

        const list = this.page.main.find("#ol-queue-list");
        list.html(rows || `<div class="ol-cockpit-empty">${__("No pending shipments in this zone.")}</div>`);
        this.page.main.find("#ol-queue-count").text(String(queue.length));

        list.find("button[data-action='add']").on("click", async (e) => {
            const dn = $(e.currentTarget).attr("data-dn");
            await this.addShipment(dn);
        });

        // DnD: drag from queue to active
        list.find("article.ol-draggable").on("dragstart", (e) => {
            const dn = $(e.currentTarget).attr("data-dn");
            e.originalEvent.dataTransfer.setData("text/plain", dn);
            e.originalEvent.dataTransfer.setData("application/ol-source", "queue");
            e.currentTarget.classList.add("ol-dragging");
            this.page.main.find("#ol-active-list")[0].classList.add("ol-dropzone-active");
        });
        list.find("article.ol-draggable").on("dragend", (e) => {
            e.currentTarget.classList.remove("ol-dragging");
            this.page.main.find("#ol-active-list")[0].classList.remove("ol-dropzone-active");
        });
    }

    renderActive(shipments) {
        // Sort shipments by sequence order (defensive sort, server also sorts)
        const ordered = [...shipments].sort((a, b) => (a.sequence || 0) - (b.sequence || 0));

        const rows = ordered
            .map((row) => {
                const checked = Number(row.selected || 0) ? "checked" : "";
                return `
                    <article class="ol-cockpit-item active ol-draggable" draggable="true" data-sequence="${row.sequence || 0}" data-dn="${frappe.utils.escape_html(row.delivery_note)}">
                        <div class="ol-cockpit-item-title">${frappe.utils.escape_html(row.delivery_note)}</div>
                        <div class="ol-cockpit-item-sub">${frappe.utils.escape_html(row.customer || "-")}</div>
                        <div class="ol-cockpit-item-badges">
                            ${this.metricBadge("W", row.shipment_weight_kg, "kg")}
                            ${this.metricBadge("V", row.shipment_volume_m3, "m3")}
                        </div>
                        <div class="ol-cockpit-item-metrics">${Number(row.shipment_weight_kg || 0).toFixed(3)} kg | ${Number(row.shipment_volume_m3 || 0).toFixed(3)} m3</div>
                        <div class="ol-cockpit-item-actions">
                            <label class="ol-inline-check"><input type="checkbox" data-action="toggle" data-dn="${frappe.utils.escape_html(row.delivery_note)}" ${checked}> ${__("Include")}</label>
                            <button class="btn btn-xs btn-default ol-btn-remove" data-action="remove" data-dn="${frappe.utils.escape_html(row.delivery_note)}">${__("Remove")}</button>
                        </div>
                    </article>
                `;
            })
            .join("");

        const list = this.page.main.find("#ol-active-list");
        list.html(rows || `<div class="ol-cockpit-empty">${__("No shipment in active container.")}</div>`);
        this.page.main.find("#ol-active-count").text(String(shipments.length));

        list.find("button[data-action='remove']").on("click", async (e) => {
            const dn = $(e.currentTarget).attr("data-dn");
            await this.removeShipment(dn);
        });
        list.find("input[data-action='toggle']").on("change", async (e) => {
            const dn = $(e.currentTarget).attr("data-dn");
            const selected = e.currentTarget.checked ? 1 : 0;
            await this.toggleShipment(dn, selected);
        });

        // DnD: drop zone for queue items and reorder within active
        const listEl = list[0];
        listEl.addEventListener("dragover", (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
            const target = e.target.closest("article.ol-cockpit-item");
            if (target) {
                listEl.querySelectorAll(".ol-drop-target").forEach(el => el.classList.remove("ol-drop-target"));
                target.classList.add("ol-drop-target");
            }
        });

        listEl.addEventListener("dragleave", (e) => {
            if (!listEl.contains(e.relatedTarget)) {
                listEl.querySelectorAll(".ol-drop-target").forEach(el => el.classList.remove("ol-drop-target"));
            }
        });

        listEl.addEventListener("drop", async (e) => {
            e.preventDefault();
            listEl.querySelectorAll(".ol-drop-target").forEach(el => el.classList.remove("ol-drop-target"));
            const dn = e.dataTransfer.getData("text/plain");
            const source = e.dataTransfer.getData("application/ol-source");
            if (!dn) return;
            if (source === "queue") {
                await this.addShipment(dn);
            } else if (source === "active") {
                await this._reorderByDrop(dn, e);
            }
        });

        // DnD: drag within active list (reorder)
        list.find("article.ol-draggable").on("dragstart", (e) => {
            const dn = $(e.currentTarget).attr("data-dn");
            e.originalEvent.dataTransfer.setData("text/plain", dn);
            e.originalEvent.dataTransfer.setData("application/ol-source", "active");
            e.currentTarget.classList.add("ol-dragging");
        });
        list.find("article.ol-draggable").on("dragend", (e) => {
            e.currentTarget.classList.remove("ol-dragging");
        });
    }

    async addShipment(deliveryNote) {
        await frappe.call({
            method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.append_shipments",
            args: { load_plan_name: this.loadPlan, delivery_notes: [deliveryNote] },
            freeze: true,
        });
        await this.refresh();
    }

    async removeShipment(deliveryNote) {
        await frappe.call({
            method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.remove_shipment",
            args: { load_plan_name: this.loadPlan, delivery_note: deliveryNote },
            freeze: true,
        });
        await this.refresh();
    }

    async toggleShipment(deliveryNote, selected) {
        await frappe.call({
            method:
                "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.set_shipment_selected",
            args: { load_plan_name: this.loadPlan, delivery_note: deliveryNote, selected },
            freeze: false,
        });
        await this.refresh();
    }

    async autoSuggest() {
        if (!this.loadPlan) {
            frappe.show_alert({ message: __("Select a Container Load Plan"), indicator: "orange" });
            return;
        }

        const r = await frappe.call({
            method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.suggest_shipments",
            args: { load_plan_name: this.loadPlan },
            freeze: true,
            freeze_message: __("Building optimal shipment combination..."),
        });

        const selected = (r.message && r.message.selected) || [];
        if (!selected.length) {
            frappe.show_alert({ message: __("No fitting shipments found"), indicator: "orange" });
            return;
        }

        await frappe.call({
            method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.append_shipments",
            args: {
                load_plan_name: this.loadPlan,
                delivery_notes: selected.map((x) => x.delivery_note),
            },
            freeze: true,
        });
        await this.refresh();
        frappe.show_alert({ message: __("Auto-suggest added {0} shipments", [selected.length]), indicator: "green" });
    }

    utilizationColor(pct) {
        const value = Number(pct || 0);
        if (value >= 95) return "#d64545";
        if (value >= 75) return "#f39c12";
        return "#2e9f57";
    }

    analysisStatusClass(status) {
        const value = String(status || "").toLowerCase();
        if (value === "over_capacity") return "danger";
        if (value === "incomplete_data") return "warn";
        return "ok";
    }

    factorClass(factor) {
        const value = String(factor || "").toLowerCase();
        if (value === "weight") return "weight";
        if (value === "volume") return "volume";
        if (value === "both") return "both";
        return "neutral";
    }

    metricBadge(prefix, value, unit) {
        const amount = Number(value || 0).toFixed(3);
        return `<span class="ol-badge-metric"><b>${prefix}</b> ${amount} ${unit}</span>`;
    }

    async _reorderByDrop(draggedDn, dropEvent) {
        const list = this.page.main.find("#ol-active-list")[0];
        const articles = Array.from(list.querySelectorAll("article.ol-cockpit-item[data-dn]"));
        const dropTarget = dropEvent.target.closest("article.ol-cockpit-item");
        if (!dropTarget || dropTarget.getAttribute("data-dn") === draggedDn) return;

        const dns = articles.map(el => el.getAttribute("data-dn")).filter(d => d !== draggedDn);
        const insertIdx = dns.indexOf(dropTarget.getAttribute("data-dn"));
        const rect = dropTarget.getBoundingClientRect();
        const after = dropEvent.clientY > rect.top + rect.height / 2;
        if (insertIdx === -1) {
            dns.push(draggedDn);
        } else {
            dns.splice(after ? insertIdx + 1 : insertIdx, 0, draggedDn);
        }

        await frappe.call({
            method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.reorder_shipments",
            args: { load_plan_name: this.loadPlan, delivery_notes_ordered: dns },
        });
        await this.refresh();
    }

    renderStackedBars(plan, shipments) {
        const PALETTE = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#84cc16", "#f97316", "#ec4899", "#6366f1"];
        const maxWeight = Number(plan.max_weight_kg || 0);
        const maxVolume = Number(plan.max_volume_m3 || 0);
        if (!maxWeight && !maxVolume) return;

        const activeShipments = shipments.filter(s => Number(s.selected));
        if (!activeShipments.length) return;

        const weightSegs = activeShipments.map((s, i) => ({
            dn: s.delivery_note,
            label: s.customer || s.delivery_note,
            pct: maxWeight > 0 ? Math.min((Number(s.shipment_weight_kg || 0) / maxWeight) * 100, 100) : 0,
            color: PALETTE[i % PALETTE.length],
        }));

        const volumeSegs = activeShipments.map((s, i) => ({
            dn: s.delivery_note,
            label: s.customer || s.delivery_note,
            pct: maxVolume > 0 ? Math.min((Number(s.shipment_volume_m3 || 0) / maxVolume) * 100, 100) : 0,
            color: PALETTE[i % PALETTE.length],
        }));

        const buildBar = (segs, totalPct) => {
            const filledPct = Math.min(totalPct, 100);
            const remainPct = Math.max(100 - filledPct, 0);
            const segHtml = segs.map(s =>
                s.pct > 0
                    ? `<div class="ol-stack-seg" style="width:${s.pct.toFixed(3)}%;background:${s.color};" title="${frappe.utils.escape_html(s.label)}: ${s.pct.toFixed(1)}%"></div>`
                    : ""
            ).join("");
            const remainHtml = remainPct > 0
                ? `<div class="ol-stack-seg ol-stack-remain" style="width:${remainPct.toFixed(3)}%;"></div>`
                : "";
            return `<div class="ol-stack-bar">${segHtml}${remainHtml}</div>`;
        };

        const weightTotalPct = Number(plan.weight_utilization_pct || 0);
        const volumeTotalPct = Number(plan.volume_utilization_pct || 0);

        const legendHtml = activeShipments.map((s, i) =>
            `<span class="ol-stack-legend-item">
                <span class="ol-stack-dot" style="background:${PALETTE[i % PALETTE.length]};"></span>
                ${frappe.utils.escape_html(s.delivery_note)}
            </span>`
        ).join("");

        const html = `
            <div class="ol-stack-wrap">
                <div class="ol-stack-row">
                    <div class="ol-stack-label">${__("Weight by shipment")}</div>
                    ${buildBar(weightSegs, weightTotalPct)}
                </div>
                <div class="ol-stack-row">
                    <div class="ol-stack-label">${__("Volume by shipment")}</div>
                    ${buildBar(volumeSegs, volumeTotalPct)}
                </div>
                <div class="ol-stack-legend">${legendHtml}</div>
            </div>
        `;

        this.page.main.find("#ol-cockpit-center .ol-cockpit-meter-grid").after(html);
    }

    _subscribeRealtime() {
        if (!this.loadPlan || this._subscribedPlan === this.loadPlan) return;
        frappe.realtime.doc_subscribe("Container Load Plan", this.loadPlan);
        this._subscribedPlan = this.loadPlan;
        this._realtimeHandler = (data) => {
            if (!data || data.load_plan !== this.loadPlan) return;
            if (data.user === frappe.session.user) return;
            frappe.show_alert({
                message: __("Load plan updated by {0}", [frappe.utils.escape_html(data.user_fullname || data.user)]),
                indicator: "blue",
            });
            this.refresh();
        };
        frappe.realtime.on("load_plan_updated", this._realtimeHandler);
    }

    _unsubscribeRealtime() {
        if (this._subscribedPlan) {
            frappe.realtime.doc_unsubscribe("Container Load Plan", this._subscribedPlan);
            this._subscribedPlan = null;
        }
        if (this._realtimeHandler) {
            frappe.realtime.off("load_plan_updated", this._realtimeHandler);
            this._realtimeHandler = null;
        }
    }

    async showZoneOverview() {
        const company = this.loadPlan
            ? (this.data && this.data.plan && this.data.plan.company) || null
            : null;

        const r = await frappe.call({
            method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.preview_consolidation",
            args: { company },
            freeze: true,
            freeze_message: __("Calculating zone consolidation..."),
        });

        const zones = r.message || [];
        if (!zones.length) {
            frappe.msgprint(__("No pending delivery notes found."));
            return;
        }

        const rows = zones.map(z => {
            const planSummary = z.plans.length
                ? z.plans.map(p =>
                    `<div class="ol-zone-plan-row">
                        <span class="ol-zone-container">${frappe.utils.escape_html(p.container_name)}</span>
                        <span class="ol-zone-util">${p.weight_utilization_pct.toFixed(1)}%W / ${p.volume_utilization_pct.toFixed(1)}%V</span>
                        <span class="ol-zone-count">${p.shipment_count} DNs</span>
                    </div>`
                  ).join("")
                : `<div class="ol-zone-empty-plan">${__("No fitting container found")}</div>`;

            const leftoverHtml = z.leftover_count > 0
                ? `<div class="ol-zone-leftover">${z.leftover_count} ${__("DN(s) unassigned")}</div>`
                : "";

            return `
                <div class="ol-zone-card">
                    <div class="ol-zone-header">
                        <span class="ol-zone-name">${frappe.utils.escape_html(z.zone)}</span>
                        <span class="ol-zone-badge">${z.pending_dn_count} ${__("pending")} | ${z.total_weight_kg.toFixed(1)} kg | ${z.total_volume_m3.toFixed(1)} m³</span>
                    </div>
                    <div class="ol-zone-plans">${planSummary}</div>
                    ${leftoverHtml}
                </div>
            `;
        }).join("");

        const d = new frappe.ui.Dialog({
            title: __("Zone Consolidation Overview"),
            size: "large",
        });
        d.body.innerHTML = `<div class="ol-zone-overview">${rows}</div>`;
        d.show();
    }

    async showAnalytics() {
        const r = await frappe.call({
            method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.get_utilization_trends",
            args: { days: 30 },
            freeze: true,
            freeze_message: __("Loading analytics..."),
        });

        const data = r.message || {};
        if (!data.plan_count) {
            frappe.msgprint(__("No completed load plans found in the last 30 days."));
            return;
        }

        const byZoneRows = (data.by_zone || []).map(z =>
            `<tr>
                <td>${frappe.utils.escape_html(z.zone)}</td>
                <td>${z.count}</td>
                <td>${z.avg_weight_pct.toFixed(1)}%</td>
                <td>${z.avg_volume_pct.toFixed(1)}%</td>
            </tr>`
        ).join("");

        const factorHtml = Object.entries(data.by_limiting_factor || {}).map(([k, v]) =>
            `<span class="ol-factor-pill ${k}">${frappe.utils.escape_html(k)}: ${v}</span>`
        ).join(" ");

        const html = `
            <div class="ol-analytics-wrap">
                <div class="ol-analytics-kpis">
                    <div class="ol-kpi-card">
                        <div class="ol-kpi-label">${__("Plans (30 days)")}</div>
                        <div class="ol-kpi-value">${data.plan_count}</div>
                    </div>
                    <div class="ol-kpi-card">
                        <div class="ol-kpi-label">${__("Avg Weight Util")}</div>
                        <div class="ol-kpi-value small">${data.avg_weight_pct.toFixed(1)}%</div>
                    </div>
                    <div class="ol-kpi-card">
                        <div class="ol-kpi-label">${__("Avg Volume Util")}</div>
                        <div class="ol-kpi-value small">${data.avg_volume_pct.toFixed(1)}%</div>
                    </div>
                </div>
                <div class="ol-analytics-section-title">${__("Limiting Factor Distribution")}</div>
                <div class="ol-analytics-factors">${factorHtml}</div>
                <div class="ol-analytics-section-title">${__("By Zone (last 30 days)")}</div>
                <table class="table table-bordered ol-analytics-table">
                    <thead><tr><th>${__("Zone")}</th><th>${__("Plans")}</th><th>${__("Avg Weight %")}</th><th>${__("Avg Volume %")}</th></tr></thead>
                    <tbody>${byZoneRows}</tbody>
                </table>
            </div>
        `;

        const d = new frappe.ui.Dialog({
            title: __("Load Plan Analytics — Last 30 Days"),
            size: "large",
        });
        d.body.innerHTML = html;
        d.show();
    }
};
