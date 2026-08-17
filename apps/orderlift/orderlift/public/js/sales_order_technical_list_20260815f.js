(function () {
    const CORE = "orderlift.orderlift_sig.technical_list";
    const PROCUREMENT = "orderlift.orderlift_logistics.technical_procurement";

    frappe.ui.form.on("Sales Order", {
        refresh(frm) {
            renderTechnicalList(frm);
        },
    });

    async function renderTechnicalList(frm) {
        const field = frm.get_field("custom_technical_list_html");
        if (!field || !field.$wrapper) return;
        if (frm.is_new()) {
            field.$wrapper.html(emptyMessage(__("Save and submit the Sales Order before creating its Technical List.")));
            return;
        }
        field.$wrapper.html(loadingMarkup());
        try {
            const response = await frappe.call({
                method: `${CORE}.get_sales_order_summary`,
                args: { sales_order: frm.doc.name },
            });
            const data = response.message || {};
            field.$wrapper.html(summaryMarkup(data));
            bindSummary(frm, field.$wrapper, data);
            if (data.eligible) {
                await installProcurementActions(frm, data);
            }
        } catch (error) {
            console.error("Unable to load Sales Order Technical List", error);
            field.$wrapper.html(emptyMessage(__("The Technical List status could not be loaded."), true));
        }
    }

    function summaryMarkup(data) {
        const list = data.technical_list;
        if (!data.eligible) {
            return `<div class="ol-tl-state-card is-neutral"><div class="ol-tl-state-copy"><span>${__("Technical execution")}</span><strong>${__("Technical List not required")}</strong><p>${esc(data.eligibility_reason || __("This Sales Order is outside the configured scope."))}</p></div><button class="btn btn-default" data-tl-manager>${__("Open Manager")}</button></div>`;
        }
        if (!list) {
            return `<div class="ol-tl-state-card is-warning"><div class="ol-tl-state-marker" aria-hidden="true"></div><div class="ol-tl-state-copy"><span>${__("Action required")}</span><strong>${__("Prepare the Technical List")}</strong><p>${__("Procurement and delivery documents remain blocked until a revision is reviewed and submitted.")}</p></div><div class="ol-tl-actions"><button class="btn btn-primary" data-tl-create>${__("Create Technical List")}</button><button class="btn btn-default" data-tl-manager>${__("Open Manager")}</button></div></div>`;
        }
        const active = list.open_revision || list.current_revision;
        const revision = list.active_revision || {};
        const items = revision.items || [];
        const approved = Number(revision.docstatus) === 1 && revision.is_current;
        const requiredAnnexes = Number(revision.required_annex_count || list.required_annex_count || 0);
        const completedAnnexes = Number(revision.completed_annex_count || list.completed_annex_count || 0);
        const status = approved ? __("Submitted") : __("Draft");
        const annexStatus = requiredAnnexes
            ? __("{0}/{1} annexes ready", [completedAnnexes, requiredAnnexes])
            : __("No required annexes");
        return `<div class="ol-project-tl-head ol-sales-tl-head"><div><strong>${__("Sales Order Technical List")}</strong><span>${esc(annexStatus)}</span></div><button class="btn btn-xs btn-default" data-tl-manager>${__("Open Manager")}</button></div><div class="ol-project-tl-list"><section class="ol-project-tl-card ol-sales-tl-card"><header><div><strong>${esc(list.name)}</strong>${active ? `<span class="ol-sales-tl-revision">${esc(active)}</span>` : ""}<span class="ol-project-tl-status">${esc(status)}</span><span class="ol-project-tl-item-count">${__("{0} items", [items.length])}</span></div><div class="ol-project-tl-actions">${active ? `<button class="btn btn-default btn-xs" data-tl-open="${attr(active)}">${__("Open Revision")}</button><button class="btn btn-default btn-xs" data-tl-annexes="${attr(active)}">${__("Technical Annexes")}</button>` : ""}${!active ? `<button class="btn btn-primary btn-xs" data-tl-new-revision="${attr(list.name)}">${__("Create Revision")}</button>` : ""}${list.current_revision && !list.open_revision ? `<button class="btn btn-default btn-xs" data-tl-new-revision="${attr(list.name)}">${__("New Revision")}</button>` : ""}</div></header>${active ? executionItemsMarkup(items) : missingRevisionMarkup()}${annexSummaryMarkup(revision.annexes || [])}</section></div>`;
    }

    function bindSummary(frm, wrapper, data) {
        wrapper.find("[data-tl-manager]").on("click", () => frappe.set_route("technical-list-manager"));
        wrapper.find("[data-tl-open]").on("click", function () {
            frappe.set_route("Form", "Sales Order Technical List Revision", this.dataset.tlOpen);
        });
        wrapper.find("[data-tl-annexes]").on("click", function () {
            openTechnicalAnnexes(this.dataset.tlAnnexes);
        });
        wrapper.find("[data-tl-create]").on("click", async () => {
            const response = await frappe.call({
                method: `${CORE}.create_for_sales_order`,
                args: { sales_order: frm.doc.name },
                freeze: true,
                freeze_message: __("Creating Technical List..."),
            });
            const revision = response.message?.revision?.name;
            if (revision) frappe.set_route("Form", "Sales Order Technical List Revision", revision);
            else frm.reload_doc();
        });
        wrapper.find("[data-tl-new-revision]").on("click", async function () {
            const response = await frappe.call({
                method: `${CORE}.create_revision`,
                args: { technical_list: this.dataset.tlNewRevision },
                freeze: true,
                freeze_message: __("Creating revision..."),
            });
            if (response.message?.name) frappe.set_route("Form", "Sales Order Technical List Revision", response.message.name);
        });
        bindExecutionControls(wrapper);
    }

    async function installProcurementActions(frm, data) {
        let payload = {};
        try {
            const response = await frappe.call({
                method: `${PROCUREMENT}.get_available_actions`,
                args: { reference_doctype: "Sales Order", reference_name: frm.doc.name },
            });
            payload = response.message || {};
        } catch (error) {
            console.error("Unable to load Technical List procurement actions", error);
        }
        frm.__orderliftTechnicalProcurement = payload;
        installNativeCreateGuard(frm, data, payload);
    }

    const ADAPTER_METHODS = {
        revision_to_material_request: "orderlift.orderlift_logistics.technical_procurement.create_material_request",
        revision_to_purchase_order: "orderlift.orderlift_logistics.technical_procurement.create_purchase_order",
        revision_to_delivery_note: "orderlift.orderlift_logistics.technical_procurement.create_delivery_note",
    };

    async function runProcurementAction(action, payload) {
        const args = {
            revision: payload.revision,
            selected_row_ids: JSON.stringify(action.row_ids || []),
        };
        if (action.adapter_key === "revision_to_purchase_order") {
            const values = await promptSupplier();
            if (!values) return;
            args.supplier = values.supplier;
        }
        const method = ADAPTER_METHODS[action.adapter_key];
        if (!method) {
            frappe.msgprint(__("Unsupported technical procurement action."));
            return;
        }
        const response = await frappe.call({ method, args, freeze: true, freeze_message: __("Creating document...") });
        const result = response.message || {};
        if (result.doctype && result.name) frappe.set_route("Form", result.doctype, result.name);
    }

    function promptSupplier() {
        return new Promise((resolve) => {
            const dialog = new frappe.ui.Dialog({
                title: __("Create Purchase Order"),
                fields: [{ fieldname: "supplier", fieldtype: "Link", options: "Supplier", label: __("Supplier"), reqd: 1 }],
                primary_action_label: __("Create"),
                primary_action(values) { dialog.hide(); resolve(values); },
            });
            dialog.$wrapper.on("hidden.bs.modal", () => resolve(null));
            dialog.show();
        });
    }

    function installNativeCreateGuard(frm, data, payload) {
        const root = frm.page?.wrapper?.get?.(0) || frm.page?.wrapper?.[0];
        if (!root) return;
        if (frm.__orderliftTechnicalCreateGuard) {
            root.removeEventListener("click", frm.__orderliftTechnicalCreateGuard, true);
        }
        const labels = ["Material Request", "Request for Raw Materials", "Purchase Order", "Request for Quotation", "Pick List", "Delivery Note"];
        const handler = (event) => {
            const control = event.target.closest("a,button");
            if (!control || !isCreateMenuControl(control)) return;
            const label = labels.find((value) => String(control.textContent || "").trim() === __(value));
            if (!label) return;
            const approved = Boolean(payload.revision && data.technical_list?.current_revision);
            if (!approved) {
                event.preventDefault();
                event.stopImmediatePropagation();
                showApprovalMessage(label === "Request for Raw Materials" ? "Material Request" : label);
                return;
            }
            if (["Material Request", "Request for Raw Materials"].includes(label)) {
                event.preventDefault();
                event.stopImmediatePropagation();
                const action = (payload.actions || []).find((row) => row.adapter_key === "revision_to_material_request");
                if (action) runProcurementAction(action, payload);
                else frappe.msgprint(__("The approved Technical List has no remaining quantity for a Material Request."));
                return;
            }
            if (label === "Delivery Note") {
                event.preventDefault();
                event.stopImmediatePropagation();
                const action = (payload.actions || []).find((row) => row.adapter_key === "revision_to_delivery_note");
                if (action) runProcurementAction(action, payload);
                else frappe.msgprint(__("The approved Technical List has no remaining quantity for a Delivery Note."));
                return;
            }
            if (["Purchase Order", "Request for Quotation"].includes(label)) {
                event.preventDefault();
                event.stopImmediatePropagation();
                frappe.msgprint(__("Create the Material Request from the approved Technical List, then continue the normal purchasing flow."));
            }
        };
        frm.__orderliftTechnicalCreateGuard = handler;
        root.addEventListener("click", handler, true);
    }

    function isCreateMenuControl(control) {
        const menu = control.closest(".dropdown-menu");
        if (!menu) return false;
        const group = menu.parentElement;
        const toggle = group?.querySelector?.(".dropdown-toggle");
        return !toggle || String(toggle.textContent || "").trim() === __("Create");
    }

    function showApprovalMessage(doctype) {
        frappe.msgprint({
            title: __("Technical List approval required"),
            message: __("No approved Technical List yet. Submit the Technical List before creating {0}.", [doctype]),
            indicator: "orange",
        });
    }

    function openTechnicalAnnexes(revision) {
        if (!revision || typeof window.orderliftOpenAnnexDialog !== "function") return;
        window.orderliftOpenAnnexDialog({
            doctype: "Sales Order Technical List Revision",
            doc: { name: revision },
            is_new: () => false,
        });
    }

    function executionItemsMarkup(items) {
        if (!items.length) return `<div class="ol-tl-empty">${__("No execution items are available.")}</div>`;
        return `<div class="table-responsive"><table class="table table-bordered"><thead><tr><th>${__("Item")}</th><th>${__("Sales Order Qty")}</th><th>${__("Execution Qty")}</th><th>${__("Variance")}</th><th>${__("Warehouse")}</th><th>${__("Required Date")}</th></tr></thead><tbody>${items.map((row, index) => executionRowMarkup(row, index)).join("")}</tbody></table></div>${items.length > 6 ? `<div class="ol-project-tl-more"><button type="button" class="btn btn-default btn-xs" data-tl-toggle-items data-total="${items.length}" aria-expanded="false">${__("Show all {0}", [items.length])}</button></div>` : ""}`;
    }

    function missingRevisionMarkup() {
        return `<div class="ol-tl-empty"><strong>${__("No revision created yet")}</strong><span>${__("Create a revision to prepare the execution items.")}</span></div>`;
    }

    function executionRowMarkup(row, index) {
        return `<tr data-tl-item-row data-index="${index}" ${index >= 6 ? "hidden" : ""}><td><strong>${esc(row.item_code)}</strong><small>${esc(row.item_name || __("Unnamed item"))}</small></td><td><span class="ol-project-tl-qty"><strong>${qty(row.sales_order_qty)}</strong><small>${esc(row.uom)}</small></span></td><td><span class="ol-project-tl-qty is-execution"><strong>${qty(row.execution_qty)}</strong><small>${esc(row.uom)}</small></span></td><td>${signedQty(row.variance_qty)}</td><td><span class="ol-project-tl-warehouse" title="${attr(row.warehouse || __("Not set"))}">${esc(row.warehouse || __("Not set"))}</span></td><td><span class="ol-project-tl-date">${esc(row.required_date || __("Not set"))}</span></td></tr>`;
    }

    function annexSummaryMarkup(annexes) {
        if (!annexes.length) return "";
        return `<div class="ol-project-tl-annexes">${annexes.map((row) => `<span class="${row.is_complete ? "complete" : "draft"}"><strong>${esc(row.template_name || row.template)}</strong><small>${esc(row.status || __("Draft"))}</small></span>`).join("")}</div>`;
    }

    function bindExecutionControls(wrapper) {
        const toggle = wrapper.find("[data-tl-toggle-items]");
        toggle.on("click", function () {
            const expanded = this.getAttribute("aria-expanded") === "true";
            wrapper.find("[data-tl-item-row]").filter(function () {
                return Number(this.dataset.index) >= 6;
            }).prop("hidden", expanded);
            this.setAttribute("aria-expanded", expanded ? "false" : "true");
            this.textContent = expanded ? __("Show all {0}", [Number(this.dataset.total || 0)]) : __("Show fewer");
        });
    }

    function emptyMessage(message, danger) {
        return `<div class="ol-tl-empty ${danger ? "is-danger" : ""}"><strong>${danger ? __("Unable to load") : __("Technical List")}</strong><span>${esc(message)}</span></div>`;
    }

    function loadingMarkup() { return `<div class="ol-tl-skeleton" aria-label="${attr(__("Loading Technical List"))}"><i></i><i></i><i></i></div>`; }

    function esc(value) { return frappe.utils.escape_html(value == null ? "" : String(value)); }
    function attr(value) { return esc(value).replace(/"/g, "&quot;"); }
    function qty(value) { return frappe.format(Number(value || 0), { fieldtype: "Float", precision: 2 }); }
    function signedQty(value) { const number = Number(value || 0); return `${number > 0 ? "+" : ""}${qty(number)}`; }

    if (!document.getElementById("ol-technical-list-form-style")) {
        const style = document.createElement("style");
        style.id = "ol-technical-list-form-style";
        style.textContent = `
            .ol-tl-workspace{--tl-border:var(--border-color,#d9e2e8);--tl-surface:var(--card-bg,#fff);--tl-muted:var(--subtle-fg,#64748b);--tl-soft:var(--subtle-accent,#f6f8fa);display:grid;gap:14px;color:var(--text-color,#1e293b)}
            .ol-tl-hero,.ol-tl-panel,.ol-tl-state-card{border:1px solid var(--tl-border);border-radius:14px;background:var(--tl-surface);box-shadow:0 8px 24px rgba(15,23,42,.045)}
            .ol-tl-hero{position:relative;overflow:hidden;padding:20px}.ol-tl-hero:before{position:absolute;inset:0 auto 0 0;width:4px;background:#d97706;content:""}.ol-tl-hero.is-approved:before{background:#16865e}.ol-tl-hero-top{display:flex;justify-content:space-between;gap:24px;align-items:flex-start}.ol-tl-heading{max-width:720px}.ol-tl-eyebrow{display:flex;gap:8px;align-items:center;color:var(--tl-muted);font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase}.ol-tl-eyebrow i{width:4px;height:4px;border-radius:50%;background:#94a3b8}.ol-tl-title-line{display:flex;gap:10px;align-items:center;margin-top:6px}.ol-tl-title-line h3{margin:0;font-size:22px;line-height:1.25;letter-spacing:-.02em}.ol-tl-title-line .ol-tl-state-pill{border:1px solid #fbbf24;border-radius:999px;background:#fffbeb;color:#92400e;padding:3px 8px;font-size:10px;font-weight:800;text-transform:uppercase}.is-approved .ol-tl-state-pill{border-color:#86efac;background:#f0fdf4;color:#166534}.ol-tl-heading p{margin:7px 0 0;color:var(--tl-muted);line-height:1.55}.ol-tl-actions{display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap}.ol-tl-actions .btn,.ol-tl-panel-head .btn,.ol-tl-state-card .btn{min-height:38px;padding:7px 12px}.ol-tl-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:20px}.ol-tl-kpi{min-width:0;border:1px solid var(--tl-border);border-radius:10px;background:var(--tl-soft);padding:11px 12px}.ol-tl-kpi>span,.ol-tl-panel-head>div>span{display:block;color:var(--tl-muted);font-size:10px;font-weight:800;letter-spacing:.055em;text-transform:uppercase}.ol-tl-kpi strong{display:block;margin-top:3px;font-size:20px;font-variant-numeric:tabular-nums}.ol-tl-kpi small{display:block;overflow:hidden;margin-top:1px;color:var(--tl-muted);text-overflow:ellipsis;white-space:nowrap}.ol-tl-kpi.is-warning strong{color:#a16207}.ol-tl-kpi.is-success strong{color:#167052}.ol-tl-readiness{display:grid;grid-template-columns:minmax(180px,1fr) minmax(220px,2fr);gap:18px;align-items:center;margin-top:14px;padding-top:14px;border-top:1px solid var(--tl-border)}.ol-tl-readiness span{display:block;color:var(--tl-muted);font-size:10px;font-weight:700;text-transform:uppercase}.ol-tl-readiness strong{display:block;margin-top:2px;font-size:12px}.ol-tl-progress{height:7px;border-radius:999px;background:#e2e8f0;overflow:hidden}.ol-tl-progress i{display:block;height:100%;border-radius:inherit;background:#16865e;transition:width .2s ease-out}.ol-tl-panel{overflow:hidden}.ol-tl-panel-head{display:flex;justify-content:space-between;gap:20px;align-items:center;padding:16px 18px}.ol-tl-panel-head h4{margin:3px 0 2px;font-size:17px}.ol-tl-panel-head p{margin:0;color:var(--tl-muted);line-height:1.4}.ol-tl-count{display:grid;place-items:center;min-width:38px;height:30px;border-radius:999px;background:#e8eefc;color:#31549a;font-size:13px}.ol-tl-toolbar{display:flex;justify-content:space-between;gap:12px;align-items:center;border-top:1px solid var(--tl-border);border-bottom:1px solid var(--tl-border);background:var(--tl-soft);padding:10px 14px}.ol-tl-search{position:relative;min-width:220px;margin:0}.ol-tl-search:before{position:absolute;top:50%;left:11px;width:11px;height:11px;border:1.5px solid #64748b;border-radius:50%;content:"";transform:translateY(-60%)}.ol-tl-search:after{position:absolute;top:20px;left:21px;width:5px;height:1.5px;background:#64748b;content:"";transform:rotate(45deg)}.ol-tl-search input{width:100%;height:36px;border:1px solid var(--tl-border);border-radius:8px;background:var(--tl-surface);padding:0 10px 0 31px;font-size:13px;outline:none}.ol-tl-search input:focus{border-color:#587bb5;box-shadow:0 0 0 3px rgba(37,99,235,.12)}.ol-tl-filters{display:flex;gap:5px;flex-wrap:wrap}.ol-tl-filters button{min-height:34px;border:1px solid transparent;border-radius:8px;background:transparent;color:var(--tl-muted);padding:5px 9px;font-size:12px;font-weight:700;cursor:pointer}.ol-tl-filters button:hover{background:rgba(148,163,184,.12)}.ol-tl-filters button:focus-visible{outline:2px solid #2563eb;outline-offset:2px}.ol-tl-filters button.active{border-color:#b9cae8;background:#e8eefc;color:#264c8c}.ol-tl-filters button span{margin-left:3px;font-variant-numeric:tabular-nums}.ol-tl-table{width:100%;border-collapse:collapse}.ol-tl-table th{padding:9px 12px;background:var(--tl-soft);color:var(--tl-muted);font-size:10px;font-weight:800;text-align:left;text-transform:uppercase}.ol-tl-table td{padding:11px 12px;border-top:1px solid var(--tl-border);vertical-align:middle}.ol-tl-table tbody tr{transition:background .16s ease}.ol-tl-table tbody tr:hover{background:rgba(148,163,184,.07)}.ol-tl-table tr[hidden]{display:none}.ol-tl-table tr.is-excluded{opacity:.62}.ol-tl-item-identity{display:grid;gap:2px;min-width:150px}.ol-tl-item-identity strong{font-size:12px}.ol-tl-item-identity span,.ol-tl-number span{color:var(--tl-muted);font-size:11px}.ol-tl-number strong{font-size:13px;font-variant-numeric:tabular-nums}.ol-tl-number.is-emphasis strong{color:#315e9e}.ol-tl-number.has-variance strong{color:#a16207}.ol-tl-warehouse,.ol-tl-date{font-size:12px}.ol-tl-change{display:inline-flex;gap:5px;align-items:center;border-radius:999px;background:#e2e8f0;color:#475569;padding:4px 8px;font-size:10px;font-weight:800;text-transform:capitalize;white-space:nowrap}.ol-tl-change i,.ol-tl-annex-state i{width:6px;height:6px;border-radius:50%;background:currentColor}.ol-tl-change.added{background:#dbeafe;color:#1d4ed8}.ol-tl-change.modified{background:#fef3c7;color:#92400e}.ol-tl-change.excluded{background:#fee2e2;color:#991b1b}.ol-tl-filter-empty{padding:24px;text-align:center;color:var(--tl-muted)}.ol-tl-annex-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;border-top:1px solid var(--tl-border);padding:14px}.ol-tl-annex-grid article{min-width:0;border:1px solid var(--tl-border);border-radius:10px;background:var(--tl-soft);padding:12px}.ol-tl-annex-grid article.is-complete{border-color:#a7d9c4}.ol-tl-annex-state{display:flex;gap:5px;align-items:center;color:#a16207;font-size:10px;font-weight:800;text-transform:uppercase}.ol-tl-annex-grid .is-complete .ol-tl-annex-state{color:#167052}.ol-tl-annex-grid article>strong{display:block;overflow:hidden;margin-top:7px;text-overflow:ellipsis;white-space:nowrap}.ol-tl-annex-grid article>p{margin:2px 0 9px;color:var(--tl-muted);font-size:11px}.ol-tl-annex-grid footer{display:flex;justify-content:space-between;gap:8px;color:var(--tl-muted);font-size:11px}.ol-tl-annex-grid footer em{font-style:normal;font-weight:700}.ol-tl-state-card{display:flex;gap:18px;align-items:center;padding:18px}.ol-tl-state-card.is-warning{border-left:4px solid #d97706}.ol-tl-state-marker{width:10px;height:10px;border-radius:50%;background:#d97706;box-shadow:0 0 0 6px #fef3c7}.ol-tl-state-copy{flex:1}.ol-tl-state-copy>span{color:var(--tl-muted);font-size:10px;font-weight:800;text-transform:uppercase}.ol-tl-state-copy strong{display:block;margin-top:2px;font-size:18px}.ol-tl-state-copy p{margin:3px 0 0;color:var(--tl-muted)}.ol-tl-empty{display:grid;gap:3px;border:1px dashed var(--border-color,#cbd5e1);border-radius:12px;background:var(--subtle-accent,#f8fafc);padding:18px;color:var(--subtle-fg,#64748b)}.ol-tl-empty strong{color:var(--text-color,#334155)}.ol-tl-empty.is-danger{border-color:#fecaca;background:#fef2f2;color:#991b1b}.ol-tl-skeleton{display:grid;gap:9px;border:1px solid var(--border-color,#d9e2e8);border-radius:14px;padding:18px}.ol-tl-skeleton i{display:block;height:16px;border-radius:6px;background:linear-gradient(90deg,#eef2f6 25%,#f8fafc 50%,#eef2f6 75%);background-size:200% 100%;animation:ol-tl-shimmer 1.25s infinite}.ol-tl-skeleton i:nth-child(1){width:38%;height:24px}.ol-tl-skeleton i:nth-child(2){width:70%}.ol-tl-skeleton i:nth-child(3){width:100%;height:72px}@keyframes ol-tl-shimmer{to{background-position:-200% 0}}@media(prefers-reduced-motion:reduce){.ol-tl-progress i,.ol-tl-table tbody tr{transition:none}.ol-tl-skeleton i{animation:none}}@media(max-width:980px){.ol-tl-hero-top{flex-direction:column}.ol-tl-actions{justify-content:flex-start}.ol-tl-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.ol-tl-annex-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.ol-tl-toolbar{align-items:stretch;flex-direction:column}.ol-tl-search{width:100%}}@media(max-width:680px){.ol-tl-workspace{gap:10px}.ol-tl-hero{padding:16px}.ol-tl-title-line{align-items:flex-start;flex-direction:column}.ol-tl-title-line h3{font-size:19px}.ol-tl-actions{display:grid;grid-template-columns:1fr 1fr;width:100%}.ol-tl-actions .btn{width:100%;min-height:44px}.ol-tl-kpis{grid-template-columns:1fr 1fr}.ol-tl-kpi{padding:10px}.ol-tl-readiness{grid-template-columns:1fr;gap:8px}.ol-tl-panel-head{align-items:flex-start;flex-direction:column}.ol-tl-panel-head .btn{width:100%;min-height:44px}.ol-tl-filters{display:grid;grid-template-columns:1fr 1fr}.ol-tl-filters button{min-height:42px}.ol-tl-table thead{display:none}.ol-tl-table,.ol-tl-table tbody,.ol-tl-table tr,.ol-tl-table td{display:block;width:100%}.ol-tl-table tr{border-top:1px solid var(--tl-border);padding:8px 12px}.ol-tl-table td{display:grid;grid-template-columns:108px minmax(0,1fr);gap:10px;align-items:start;border:0;padding:6px 0}.ol-tl-table td:before{content:attr(data-label);color:var(--tl-muted);font-size:10px;font-weight:800;text-transform:uppercase}.ol-tl-item-identity{min-width:0}.ol-tl-annex-grid{grid-template-columns:1fr}.ol-tl-state-card{align-items:flex-start;flex-direction:column}.ol-tl-state-marker{margin:4px 0 0 4px}.ol-tl-state-card .ol-tl-actions{display:flex}.ol-tl-search input{height:44px;font-size:16px}}
        `;
        style.textContent += `
            .ol-tl-workspace{--tl-border:#dfe3ed;--tl-surface:#fff;--tl-muted:#334155;--tl-soft:#f8f9fc;gap:8px;color:#111827;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
            .ol-tl-hero,.ol-tl-panel,.ol-tl-state-card{border-color:var(--tl-border);border-radius:10px;box-shadow:0 1px 4px rgba(15,23,41,.04)}
            .ol-tl-hero{padding:10px 12px}.ol-tl-hero:before{width:3px;background:#f59e0b}.ol-tl-hero.is-approved:before{background:#16a34a}.ol-tl-hero-top{gap:12px;align-items:center}.ol-tl-heading{max-width:none;min-width:0}.ol-tl-title-line{gap:7px;margin:0}.ol-tl-title-line h3{color:#111827;font-size:15px;white-space:nowrap}.ol-tl-title-line .ol-tl-state-pill{padding:2px 6px;font-size:9px}.ol-tl-eyebrow{gap:6px;margin-top:3px;color:#4f6ef7;font-size:9px;letter-spacing:.03em}.ol-tl-eyebrow i{background:#7c5cf5}.ol-tl-heading p{display:none}.ol-tl-actions{gap:5px;flex-wrap:nowrap}.ol-tl-actions .btn,.ol-tl-panel-head .btn,.ol-tl-state-card .btn{min-height:32px;padding:4px 9px;border-radius:7px;font-size:11px;font-weight:700;white-space:nowrap}
            .ol-tl-summary-row{display:flex;align-items:center;gap:10px;margin-top:8px;padding-top:8px;border-top:1px solid #e8ecf4}.ol-tl-kpis{display:flex;align-items:center;gap:0;margin:0;min-width:0;flex:1}.ol-tl-kpi{display:inline-flex;align-items:center;gap:5px;min-width:0;padding:0 10px;border:0;border-right:1px solid #dfe3ed;border-radius:0;background:transparent;white-space:nowrap}.ol-tl-kpi:first-child{padding-left:0}.ol-tl-kpi:last-child{border-right:0}.ol-tl-kpi small{color:#334155;font-size:9px;font-weight:700;text-transform:uppercase}.ol-tl-kpi strong{overflow:hidden;margin:0;color:#111827;font-size:11px;text-overflow:ellipsis}.ol-tl-kpi.is-warning strong{color:#92400e}.ol-tl-kpi.is-success strong{color:#166534}.ol-tl-progress{width:90px;height:4px;flex:0 0 90px;background:#e8ecf4}.ol-tl-progress i{background:linear-gradient(90deg,#4f6ef7,#7c5cf5)}
            .ol-tl-panel-head{gap:10px;padding:8px 10px}.ol-tl-panel-head>div>span{color:#4f6ef7;font-size:8px}.ol-tl-panel-head h4{display:flex;align-items:center;gap:6px;margin:0;color:#111827;font-size:13px}.ol-tl-panel-head h4 b{display:inline-flex;align-items:center;justify-content:center;min-width:22px;height:20px;padding:0 6px;border-radius:999px;background:#eef1ff;color:#4f6ef7;font-size:9px}.ol-tl-panel-head p{display:none}.ol-tl-toolbar{gap:7px;padding:6px 8px;background:#f8f9fc}.ol-tl-search{min-width:180px}.ol-tl-search input{height:30px;border-color:#dfe3ed;color:#111827;font-size:11px}.ol-tl-search:after{top:17px}.ol-tl-filters{gap:2px}.ol-tl-filters button{min-height:28px;padding:2px 7px;color:#334155;font-size:9px}.ol-tl-filters button.active{border-color:#c7d2fe;background:#eef1ff;color:#4338ca}.ol-tl-table{min-width:900px;table-layout:fixed}.ol-tl-table th{padding:6px 8px;background:#f8f9fc;color:#334155;font-size:8px}.ol-tl-table th:nth-child(1){width:30%}.ol-tl-table th:nth-child(2),.ol-tl-table th:nth-child(3),.ol-tl-table th:nth-child(4){width:9%}.ol-tl-table th:nth-child(5){width:19%}.ol-tl-table th:nth-child(6){width:14%}.ol-tl-table th:nth-child(7){width:10%}.ol-tl-table td{padding:6px 8px;color:#111827}.ol-tl-item-identity{gap:0}.ol-tl-item-identity strong,.ol-tl-number strong{color:#111827;font-size:10px}.ol-tl-item-identity span{overflow:hidden;color:#334155;font-size:9px;text-overflow:ellipsis;white-space:nowrap}.ol-tl-number{white-space:nowrap}.ol-tl-number span{display:inline;margin-left:3px;color:#334155;font-size:9px}.ol-tl-warehouse{display:block;overflow:hidden;color:#111827;font-size:10px;text-overflow:ellipsis;white-space:nowrap}.ol-tl-date{color:#111827;font-size:10px;white-space:nowrap}.ol-tl-change{padding:2px 5px;font-size:8px}.ol-tl-unchanged{color:#64748b}
            .ol-tl-annex-grid{grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;padding:7px}.ol-tl-annex-grid article{border-color:#dfe3ed;border-radius:7px;background:#f8f9fc;padding:6px 8px}.ol-tl-annex-state{font-size:8px}.ol-tl-annex-grid article>strong{margin-top:3px;color:#111827;font-size:10px}.ol-tl-annex-grid article>p{display:none}.ol-tl-annex-grid footer{margin-top:3px;color:#334155;font-size:8px}.ol-tl-empty{padding:10px;border-color:#dfe3ed;background:#fff;color:#334155}.ol-tl-empty strong{color:#111827}
            @media(max-width:980px){.ol-tl-hero-top{align-items:flex-start}.ol-tl-actions{flex-wrap:wrap}.ol-tl-summary-row{align-items:flex-start;flex-direction:column}.ol-tl-progress{width:100%;flex-basis:4px}.ol-tl-annex-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
            @media(max-width:680px){.ol-tl-hero{padding:10px}.ol-tl-title-line h3{white-space:normal}.ol-tl-actions{display:flex}.ol-tl-actions .btn{width:auto;min-height:40px}.ol-tl-kpis{display:grid;grid-template-columns:1fr 1fr;width:100%}.ol-tl-kpi{padding:4px 7px;border-right:0}.ol-tl-kpi:first-child{padding-left:7px}.ol-tl-panel-head{padding:8px}.ol-tl-panel-head .btn{min-height:40px}.ol-tl-toolbar{padding:6px}.ol-tl-search input{height:40px}.ol-tl-filters button{min-height:40px}.ol-tl-table{min-width:0;table-layout:auto}.ol-tl-table tr{padding:5px 9px}.ol-tl-table td{grid-template-columns:92px minmax(0,1fr);padding:3px 0}.ol-tl-annex-grid{grid-template-columns:1fr}}
        `;
        style.textContent += `
            .ol-project-tl-head,.ol-project-tl-card{font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#111827}.ol-project-tl-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:7px}.ol-project-tl-head>div{display:flex;align-items:center;gap:7px}.ol-project-tl-head strong{font-size:13px}.ol-project-tl-head span{padding:2px 6px;border-radius:999px;background:#eef1ff;color:#4f6ef7;font-size:9px;font-weight:700}.ol-project-tl-head .btn{min-height:32px;border-radius:7px;color:#334155;font-size:11px;font-weight:700}.ol-project-tl-list{display:grid;gap:7px}.ol-project-tl-card{overflow:hidden;border:1px solid #dfe3ed;border-radius:10px;background:#fff;box-shadow:0 1px 4px rgba(15,23,41,.04)}.ol-project-tl-card>header{display:flex;justify-content:space-between;align-items:center;gap:9px;padding:7px 9px;border-bottom:1px solid #e8ecf4;background:#fff}.ol-project-tl-card header>div:first-child{display:flex;align-items:center;gap:6px;flex-wrap:wrap}.ol-project-tl-card header strong{color:#111827;font-size:11px}.ol-sales-tl-revision{color:#4f6ef7;font-size:10px;font-weight:800}.ol-project-tl-status{padding:2px 6px;border-radius:999px;background:#eef1ff;color:#4338ca;font-size:8px;font-weight:800;text-transform:uppercase}.ol-project-tl-item-count{color:#334155;font-size:9px;font-weight:700}.ol-project-tl-actions{display:flex;gap:4px}.ol-project-tl-actions .btn{min-height:30px;border-radius:7px;color:#334155;font-size:10px;font-weight:700}.ol-project-tl-actions .btn-primary{color:#fff}.ol-project-tl-card .table-responsive{margin:0}.ol-project-tl-card table{width:100%;min-width:760px;margin:0;table-layout:fixed;color:#111827;font-size:10px}.ol-project-tl-card table th{padding:5px 7px;border-color:#e8ecf4;background:#f8f9fc;color:#334155;font-size:8px;font-weight:800;text-transform:uppercase}.ol-project-tl-card table th:nth-child(1){width:42%}.ol-project-tl-card table th:nth-child(2),.ol-project-tl-card table th:nth-child(3){width:10%}.ol-project-tl-card table th:nth-child(4){width:8%}.ol-project-tl-card table th:nth-child(5){width:18%}.ol-project-tl-card table th:nth-child(6){width:12%}.ol-project-tl-card table td{padding:6px 7px;border-color:#e8ecf4;vertical-align:middle}.ol-project-tl-card table td>strong{display:block;overflow:hidden;color:#111827;font-size:10px;text-overflow:ellipsis;white-space:nowrap}.ol-project-tl-card td>small{display:block;overflow:hidden;margin-top:0;color:#334155;font-size:9px;text-overflow:ellipsis;white-space:nowrap}.ol-project-tl-qty{display:inline-flex;align-items:baseline;gap:3px;white-space:nowrap}.ol-project-tl-qty strong{color:#111827;font-size:10px}.ol-project-tl-qty small{display:inline!important;margin:0!important;color:#334155;font-size:9px}.ol-project-tl-qty.is-execution strong{color:#315e9e}.ol-project-tl-warehouse{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ol-project-tl-date{white-space:nowrap}.ol-project-tl-more{display:flex;justify-content:center;padding:6px;border-top:1px solid #e8ecf4;background:#f8f9fc}.ol-project-tl-more .btn{min-height:30px;border-radius:7px;color:#4f6ef7;font-size:10px;font-weight:700}.ol-project-tl-annexes{display:flex;gap:4px;flex-wrap:wrap;padding:6px 8px;border-top:1px solid #e8ecf4;background:#fff}.ol-project-tl-annexes span{display:flex;gap:4px;border:1px solid #dfe3ed;border-radius:999px;background:#f8f9fc;padding:2px 6px;color:#111827;font-size:9px}.ol-project-tl-annexes .complete{border-color:#bbf7d0;background:#ecfdf5;color:#166534}.ol-project-tl-annexes small{color:inherit}.ol-sales-tl-card .ol-tl-empty{border:0;border-radius:0}
            @media(max-width:760px){.ol-project-tl-card>header{align-items:flex-start;flex-direction:column;gap:6px;padding:8px}.ol-project-tl-actions{flex-wrap:wrap}.ol-project-tl-actions .btn{min-height:40px}.ol-project-tl-card table{min-width:680px}.ol-project-tl-head .btn,.ol-project-tl-more .btn{min-height:40px}}
        `;
        document.head.appendChild(style);
    }
})();
