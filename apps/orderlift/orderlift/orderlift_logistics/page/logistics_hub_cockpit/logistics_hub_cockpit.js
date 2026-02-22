frappe.provide("orderlift.logistics_cockpit");

frappe.pages["logistics-hub-cockpit"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Logistics Hub Cockpit"),
        single_column: true,
    });

    orderlift.logistics_cockpit.instance = new orderlift.logistics_cockpit.Cockpit(page);
};

orderlift.logistics_cockpit.Cockpit = class Cockpit {
    constructor(page) {
        this.page = page;
        this.loadPlan = null;
        this.setupControls();
        this.renderShell();
    }

    setupControls() {
        this.loadPlanControl = this.page.add_field({
            label: __("Container Load Plan"),
            fieldname: "container_load_plan",
            fieldtype: "Link",
            options: "Container Load Plan",
            reqd: 1,
            change: () => {
                this.loadPlan = this.loadPlanControl.get_value();
                if (this.loadPlan) this.refresh();
            },
        });

        this.page.set_primary_action(__("Auto-Suggest"), () => this.autoSuggest(), "magic");
        this.page.set_secondary_action(__("Refresh"), () => this.refresh());

        this.page.add_menu_item(__("Open Load Plan"), () => {
            if (!this.loadPlan) return;
            frappe.set_route("Form", "Container Load Plan", this.loadPlan);
        });
    }

    renderShell() {
        const html = `
            <div class="ol-cockpit-wrap">
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
        this.renderQueue(this.data.queue || []);
        this.renderActive(this.data.shipments || []);
    }

    renderCenter(plan) {
        const weightPct = Number(plan.weight_utilization_pct || 0);
        const volumePct = Number(plan.volume_utilization_pct || 0);
        const weightColor = this.utilizationColor(weightPct);
        const volumeColor = this.utilizationColor(volumePct);

        const html = `
            <div class="ol-cockpit-card">
                <div class="ol-cockpit-title-row">
                    <div>
                        <div class="ol-cockpit-title">${frappe.utils.escape_html(plan.container_label || this.loadPlan || "")}</div>
                        <div class="ol-cockpit-sub">${frappe.utils.escape_html(plan.container_profile_label || "")} - ${frappe.utils.escape_html(plan.destination_zone || "")}</div>
                    </div>
                    <div class="ol-cockpit-status">${frappe.utils.escape_html(plan.analysis_status || "ok")}</div>
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

                <div class="ol-cockpit-meta">${__("Limiting Factor")}: <b>${frappe.utils.escape_html(plan.limiting_factor || "n/a")}</b></div>
            </div>
        `;

        this.page.main.find("#ol-cockpit-center").html(html);
    }

    renderQueue(queue) {
        const rows = queue
            .map((row) => {
                return `
                    <article class="ol-cockpit-item">
                        <div class="ol-cockpit-item-title">${frappe.utils.escape_html(row.delivery_note)}</div>
                        <div class="ol-cockpit-item-sub">${frappe.utils.escape_html(row.customer || "-")} - ${frappe.utils.escape_html(row.destination_zone || "")}</div>
                        <div class="ol-cockpit-item-metrics">${Number(row.total_weight_kg || 0).toFixed(3)} kg | ${Number(row.total_volume_m3 || 0).toFixed(3)} m3</div>
                        <div class="ol-cockpit-item-actions">
                            <button class="btn btn-xs btn-primary" data-action="add" data-dn="${frappe.utils.escape_html(row.delivery_note)}">${__("Add")}</button>
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
    }

    renderActive(shipments) {
        const rows = shipments
            .map((row) => {
                const checked = Number(row.selected || 0) ? "checked" : "";
                return `
                    <article class="ol-cockpit-item active">
                        <div class="ol-cockpit-item-title">${frappe.utils.escape_html(row.delivery_note)}</div>
                        <div class="ol-cockpit-item-sub">${frappe.utils.escape_html(row.customer || "-")}</div>
                        <div class="ol-cockpit-item-metrics">${Number(row.shipment_weight_kg || 0).toFixed(3)} kg | ${Number(row.shipment_volume_m3 || 0).toFixed(3)} m3</div>
                        <div class="ol-cockpit-item-actions">
                            <label class="ol-inline-check"><input type="checkbox" data-action="toggle" data-dn="${frappe.utils.escape_html(row.delivery_note)}" ${checked}> ${__("Include")}</label>
                            <button class="btn btn-xs btn-default" data-action="remove" data-dn="${frappe.utils.escape_html(row.delivery_note)}">${__("Remove")}</button>
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
};
