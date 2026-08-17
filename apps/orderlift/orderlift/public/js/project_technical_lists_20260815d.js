(function () {
    const CORE = "orderlift.orderlift_sig.technical_list";

    frappe.ui.form.on("Project", {
        refresh(frm) {
            renderTechnicalLists(frm);
        },
    });

    async function renderTechnicalLists(frm) {
        const field = frm.get_field("custom_technical_lists_html");
        if (!field || !field.$wrapper) return;
        if (frm.is_new()) {
            field.$wrapper.html(`<div class="ol-tl-empty">${__("Save the Project to view its Sales Order Technical Lists.")}</div>`);
            return;
        }
        field.$wrapper.html(`<div class="ol-tl-empty">${__("Loading Technical Lists...")}</div>`);
        try {
            const response = await frappe.call({ method: `${CORE}.get_project_summaries`, args: { project: frm.doc.name } });
            const rows = response.message || [];
            field.$wrapper.html(markup(rows));
            bind(frm, field.$wrapper, rows);
        } catch (error) {
            console.error("Unable to load Project Technical Lists", error);
            field.$wrapper.html(`<div class="ol-tl-empty text-danger">${__("Technical Lists could not be loaded.")}</div>`);
        }
    }

    function markup(rows) {
        if (!rows.length) return `<div class="ol-tl-empty">${__("No Sales Order Technical Lists are linked to this Project.")}</div>`;
        return `<div class="ol-project-tl-head"><div><strong>${__("Project Technical Lists")}</strong><span>${__("{0} linked", [rows.length])}</span></div><button class="btn btn-xs btn-default" data-project-annexes>${__("Project Annexes")}</button></div><div class="ol-project-tl-list">${rows.map((row) => {
            const revision = row.open_revision || row.current_revision;
            const details = row.active_revision || {};
            const itemScope = revision || row.name;
            return `<section class="ol-project-tl-card"><header><div><button class="btn btn-link btn-xs" data-so="${attr(row.sales_order)}">${esc(row.sales_order)}</button><strong>${esc(row.name)}</strong><span class="ol-project-tl-status">${esc(row.status || "-")}</span><span class="ol-project-tl-item-count">${__("{0} items", [(details.items || []).length])}</span></div><div class="ol-project-tl-actions">${revision ? `<button class="btn btn-default btn-xs" data-revision="${attr(revision)}">${__("Open Revision")}</button><button class="btn btn-default btn-xs" data-technical-annexes="${attr(revision)}">${__("Technical Annexes")}</button>` : ""}</div></header>${itemsMarkup(details.items || [], itemScope)}${annexMarkup(details.annexes || [])}</section>`;
        }).join("")}</div>`;
    }

    function bind(frm, wrapper) {
        wrapper.find("[data-so]").on("click", function () { frappe.set_route("Form", "Sales Order", this.dataset.so); });
        wrapper.find("[data-revision]").on("click", function () { frappe.set_route("Form", "Sales Order Technical List Revision", this.dataset.revision); });
        wrapper.find("[data-project-annexes]").on("click", function () {
            if (typeof window.orderliftOpenAnnexDialog === "function") window.orderliftOpenAnnexDialog(frm);
        });
        wrapper.find("[data-technical-annexes]").on("click", function () {
            if (typeof window.orderliftOpenAnnexDialog !== "function") return;
            window.orderliftOpenAnnexDialog({
                doctype: "Sales Order Technical List Revision",
                doc: { name: this.dataset.technicalAnnexes },
                is_new: () => false,
            });
        });
        wrapper.find("[data-project-toggle-items]").on("click", function () {
            const scope = this.dataset.projectToggleItems;
            const expanded = this.getAttribute("aria-expanded") === "true";
            wrapper.find("[data-project-item-row]").filter(function () {
                return this.dataset.projectItemRow === scope && Number(this.dataset.index) >= 6;
            }).prop("hidden", expanded);
            this.setAttribute("aria-expanded", expanded ? "false" : "true");
            this.textContent = expanded ? __("Show all {0}", [Number(this.dataset.total || 0)]) : __("Show fewer");
        });
    }

    function itemsMarkup(items, scope) {
        if (!items.length) return `<div class="ol-project-tl-empty">${__("No execution items.")}</div>`;
        return `<div class="table-responsive"><table class="table table-bordered"><thead><tr><th>${__("Item")}</th><th>${__("Sales Order Qty")}</th><th>${__("Execution Qty")}</th><th>${__("Variance")}</th><th>${__("Warehouse")}</th><th>${__("Required Date")}</th></tr></thead><tbody>${items.map((row, index) => `<tr data-project-item-row="${attr(scope)}" data-index="${index}" ${index >= 6 ? "hidden" : ""}><td><strong>${esc(row.item_code)}</strong><small>${esc(row.item_name)}</small></td><td><span class="ol-project-tl-qty"><strong>${qty(row.sales_order_qty)}</strong><small>${esc(row.uom)}</small></span></td><td><span class="ol-project-tl-qty is-execution"><strong>${qty(row.execution_qty)}</strong><small>${esc(row.uom)}</small></span></td><td>${qty(row.variance_qty)}</td><td><span class="ol-project-tl-warehouse" title="${attr(row.warehouse || "-")}">${esc(row.warehouse || "-")}</span></td><td><span class="ol-project-tl-date">${esc(row.required_date || "-")}</span></td></tr>`).join("")}</tbody></table></div>${items.length > 6 ? `<div class="ol-project-tl-more"><button type="button" class="btn btn-default btn-xs" data-project-toggle-items="${attr(scope)}" data-total="${items.length}" aria-expanded="false">${__("Show all {0}", [items.length])}</button></div>` : ""}`;
    }

    function annexMarkup(annexes) {
        if (!annexes.length) return "";
        return `<div class="ol-project-tl-annexes">${annexes.map((row) => `<span class="${row.is_complete ? "complete" : "draft"}"><strong>${esc(row.template)}</strong><small>${esc(row.status || __("Draft"))}</small></span>`).join("")}</div>`;
    }

    function esc(value) { return frappe.utils.escape_html(String(value || "")); }
    function attr(value) { return esc(value).replace(/"/g, "&quot;"); }
    function qty(value) { return frappe.format(Number(value || 0), { fieldtype: "Float", precision: 2 }); }

    if (!document.getElementById("ol-project-technical-list-style")) {
        const style = document.createElement("style");
        style.id = "ol-project-technical-list-style";
        style.textContent = `.ol-project-tl-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}.ol-project-tl-list{display:grid;gap:12px}.ol-project-tl-card{border:1px solid #dce5e1;border-radius:12px;background:#fff;overflow:hidden}.ol-project-tl-card>header{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:11px 14px;background:#f8fafc}.ol-project-tl-card header>div:first-child{display:flex;gap:9px;align-items:center;flex-wrap:wrap}.ol-project-tl-card header small{color:#64748b}.ol-project-tl-actions{display:flex;gap:6px}.ol-project-tl-card table{margin:0;min-width:760px}.ol-project-tl-card td small{display:block;color:#64748b}.ol-project-tl-annexes{display:flex;gap:7px;flex-wrap:wrap;padding:10px 12px;border-top:1px solid #e2e8f0}.ol-project-tl-annexes span{display:flex;gap:7px;border:1px solid #dce5e1;border-radius:999px;padding:4px 8px}.ol-project-tl-annexes .complete{border-color:#86efac;background:#f0fdf4}.ol-project-tl-annexes small{color:#64748b}.ol-project-tl-empty,.ol-tl-empty{padding:14px;border:1px dashed #cbd5e1;border-radius:10px;background:#f8fafc;color:#64748b}@media(max-width:760px){.ol-project-tl-card>header{align-items:flex-start;flex-direction:column}}`;
        style.textContent += `
            .ol-project-tl-head,.ol-project-tl-card{font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#111827}.ol-project-tl-head{margin-bottom:7px}.ol-project-tl-head>div{display:flex;align-items:center;gap:7px}.ol-project-tl-head strong{font-size:13px}.ol-project-tl-head span{padding:2px 6px;border-radius:999px;background:#eef1ff;color:#4f6ef7;font-size:9px;font-weight:700}.ol-project-tl-head .btn{min-height:32px;border-radius:7px;color:#334155;font-size:11px;font-weight:700}.ol-project-tl-list{gap:7px}.ol-project-tl-card{border-color:#dfe3ed;border-radius:10px;box-shadow:0 1px 4px rgba(15,23,41,.04)}.ol-project-tl-card>header{gap:9px;padding:7px 9px;border-bottom:1px solid #e8ecf4;background:#fff}.ol-project-tl-card header>div:first-child{gap:6px}.ol-project-tl-card header .btn-link{height:auto;min-height:30px;padding:3px 5px;color:#4f6ef7;font-size:11px;font-weight:800}.ol-project-tl-card header strong{color:#111827;font-size:11px}.ol-project-tl-status{padding:2px 6px;border-radius:999px;background:#eef1ff;color:#4338ca;font-size:8px;font-weight:800;text-transform:uppercase}.ol-project-tl-item-count{color:#334155;font-size:9px;font-weight:700}.ol-project-tl-actions{gap:4px}.ol-project-tl-actions .btn{min-height:30px;border-radius:7px;color:#334155;font-size:10px;font-weight:700}.ol-project-tl-card .table-responsive{margin:0}.ol-project-tl-card table{min-width:760px;table-layout:fixed;color:#111827;font-size:10px}.ol-project-tl-card table th{padding:5px 7px;border-color:#e8ecf4;background:#f8f9fc;color:#334155;font-size:8px;font-weight:800;text-transform:uppercase}.ol-project-tl-card table th:nth-child(1){width:42%}.ol-project-tl-card table th:nth-child(2),.ol-project-tl-card table th:nth-child(3){width:10%}.ol-project-tl-card table th:nth-child(4){width:8%}.ol-project-tl-card table th:nth-child(5){width:18%}.ol-project-tl-card table th:nth-child(6){width:12%}.ol-project-tl-card table td{padding:6px 7px;border-color:#e8ecf4;vertical-align:middle}.ol-project-tl-card table td>strong{display:block;overflow:hidden;color:#111827;font-size:10px;text-overflow:ellipsis;white-space:nowrap}.ol-project-tl-card td>small{display:block;overflow:hidden;margin-top:0;color:#334155;font-size:9px;text-overflow:ellipsis;white-space:nowrap}.ol-project-tl-qty{display:inline-flex;align-items:baseline;gap:3px;white-space:nowrap}.ol-project-tl-qty strong{color:#111827;font-size:10px}.ol-project-tl-qty small{display:inline!important;margin:0!important;color:#334155;font-size:9px}.ol-project-tl-qty.is-execution strong{color:#315e9e}.ol-project-tl-warehouse{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ol-project-tl-date{white-space:nowrap}.ol-project-tl-more{display:flex;justify-content:center;padding:6px;border-top:1px solid #e8ecf4;background:#f8f9fc}.ol-project-tl-more .btn{min-height:30px;border-radius:7px;color:#4f6ef7;font-size:10px;font-weight:700}.ol-project-tl-annexes{gap:4px;padding:6px 8px;border-color:#e8ecf4;background:#fff}.ol-project-tl-annexes span{gap:4px;border-color:#dfe3ed;background:#f8f9fc;padding:2px 6px;color:#111827;font-size:9px}.ol-project-tl-annexes .complete{border-color:#bbf7d0;background:#ecfdf5;color:#166534}.ol-project-tl-annexes small{color:inherit}.ol-project-tl-empty,.ol-tl-empty{padding:10px;border-color:#dfe3ed;background:#fff;color:#334155}
            @media(max-width:760px){.ol-project-tl-card>header{gap:6px;padding:8px}.ol-project-tl-actions{flex-wrap:wrap}.ol-project-tl-actions .btn{min-height:40px}.ol-project-tl-card table{min-width:680px}.ol-project-tl-head .btn,.ol-project-tl-more .btn{min-height:40px}}
        `;
        document.head.appendChild(style);
    }
})();
