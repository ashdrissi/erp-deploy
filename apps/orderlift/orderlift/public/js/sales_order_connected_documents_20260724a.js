(function () {
    frappe.ui.form.on("Sales Order", {
        refresh(frm) {
            renderConnectedDocuments(frm);
        },
    });

    function renderConnectedDocuments(frm) {
        const field = frm.get_field("custom_documents_html");
        if (!field || !field.$wrapper) return;
        ensureStyles();
        if (frm.is_new()) {
            field.$wrapper.html(`<div class="ol-sodocs-empty">${__("Save the Sales Order to see its linked documents.")}</div>`);
            return;
        }
        field.$wrapper.html(`<div class="ol-sodocs-empty">${__("Loading linked documents...")}</div>`);
        frappe.call({
            method: "orderlift.orderlift_crm.api.pipeline.get_sales_order_documents",
            args: { sales_order: frm.doc.name },
        }).then((response) => {
            field.$wrapper.html(documentsMarkup(response.message || {}));
            field.$wrapper.find("[data-open-doc]").on("click", function () {
                const doctype = $(this).data("open-doc");
                const name = $(this).data("open-name");
                if (doctype && name) frappe.set_route("Form", String(doctype), String(name));
            });
        }).catch((error) => {
            console.error("Unable to load Sales Order linked documents", error);
            field.$wrapper.html(`<div class="ol-sodocs-empty text-danger">${__("Could not load linked documents.")}</div>`);
        });
    }

    function documentsMarkup(data) {
        const opportunity = data.opportunity;
        const groups = data.groups || [];
        const total = Number(data.total || 0);
        if (!opportunity && !groups.length) {
            return `<div class="ol-sodocs-empty">${__("No linked documents yet.")}</div>`;
        }
        const opportunityCard = opportunity ? `
            <button type="button" class="ol-sodocs-opportunity" data-open-doc="Opportunity" data-open-name="${escapeHtml(opportunity.name)}">
                ${badge("Opportunity")}
                <span class="ol-sodocs-opportunity-copy">
                    <small>${__("Source Opportunity")}</small>
                    <strong>${escapeHtml(opportunity.title || opportunity.name)}</strong>
                    <span>${escapeHtml(opportunity.name)}</span>
                </span>
                <span class="ol-sodocs-opportunity-meta">
                    <span class="ol-sodocs-status ${statusClass(opportunity.status)}">${escapeHtml(opportunity.status || "-")}</span>
                    ${opportunity.amount ? `<strong>${format_currency(opportunity.amount)}</strong>` : ""}
                </span>
            </button>` : "";
        const groupCards = groups.map((group) => `
            <section class="ol-sodocs-group">
                <header>${badge(group.doctype)}<strong>${escapeHtml(group.label)}</strong><span>${group.items.length}</span></header>
                ${group.items.map((item) => `
                    <button type="button" class="ol-sodocs-row" data-open-doc="${escapeHtml(group.doctype)}" data-open-name="${escapeHtml(item.name)}">
                        <span>${escapeHtml(item.name)}</span>
                        <small class="ol-sodocs-status ${statusClass(item.status)}">${escapeHtml(item.status || "-")}</small>
                    </button>`).join("")}
            </section>`).join("");
        return `
            <div class="ol-sodocs">
                <div class="ol-sodocs-head"><h4>${__("Linked Documents")}</h4><span>${total} ${__("linked")}</span></div>
                ${opportunityCard}
                <div class="ol-sodocs-grid">${groupCards}</div>
            </div>`;
    }

    function badge(doctype) {
        const values = {
            Opportunity: ["OPP", "#6366f1"],
            Quotation: ["QTN", "#0ea5e9"],
            Project: ["PRJ", "#16a34a"],
            "Material Request": ["MR", "#0891b2"],
            "Purchase Order": ["PO", "#a855f7"],
            "Purchase Receipt": ["PR", "#ca8a04"],
            "Purchase Invoice": ["PINV", "#be123c"],
            "Pick List": ["PICK", "#0369a1"],
            "Delivery Note": ["DN", "#f59e0b"],
            "Sales Invoice": ["INV", "#ef4444"],
            "Payment Entry": ["PAY", "#0d9488"],
            "Work Order": ["WO", "#b45309"],
        }[doctype] || ["DOC", "#64748b"];
        return `<span class="ol-sodocs-badge" style="background:${values[1]}">${values[0]}</span>`;
    }

    function statusClass(status) {
        const value = String(status || "").toLowerCase();
        if (/(paid|completed|ordered|delivered|closed|approved|submitted|received)/.test(value)) return "is-green";
        if (/(lost|cancel|rejected|return|overdue|unpaid|expired)/.test(value)) return "is-red";
        if (/(draft|open|pending|partial|to deliver|to receive|to bill)/.test(value)) return "is-amber";
        return "is-gray";
    }

    function escapeHtml(value) {
        return frappe.utils.escape_html(String(value || ""));
    }

    function ensureStyles() {
        if (document.getElementById("ol-sales-order-documents-style")) return;
        const style = document.createElement("style");
        style.id = "ol-sales-order-documents-style";
        style.textContent = `
            .ol-sodocs { margin-top:8px; }
            .ol-sodocs-head { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
            .ol-sodocs-head h4 { margin:0; font-size:15px; font-weight:700; color:#1f272e; }
            .ol-sodocs-head > span { font-size:11px; color:#64748b; background:#f1f5f9; padding:3px 10px; border-radius:999px; font-weight:600; }
            .ol-sodocs-empty { padding:18px; color:#64748b; background:#f8fafc; border:1px dashed #d8e2ee; border-radius:10px; text-align:center; }
            .ol-sodocs-opportunity { width:100%; display:flex; align-items:center; gap:14px; padding:14px 16px; border:1px solid #e2e8f0; border-left:4px solid #6366f1; border-radius:12px; background:linear-gradient(180deg,#fbfbff,#fff); margin-bottom:16px; text-align:left; }
            .ol-sodocs-opportunity:hover, .ol-sodocs-row:hover { background:#f8fafc; }
            .ol-sodocs-opportunity-copy { display:flex; flex-direction:column; flex:1; min-width:0; }
            .ol-sodocs-opportunity-copy small { color:#6366f1; font-size:10px; text-transform:uppercase; letter-spacing:.07em; font-weight:700; }
            .ol-sodocs-opportunity-copy strong { color:#1f272e; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
            .ol-sodocs-opportunity-copy span { color:#94a3b8; font-size:11px; }
            .ol-sodocs-opportunity-meta { display:flex; flex-direction:column; align-items:flex-end; gap:6px; }
            .ol-sodocs-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:14px; }
            .ol-sodocs-group { border:1px solid #e6edf3; border-radius:12px; background:#fff; overflow:hidden; }
            .ol-sodocs-group header { display:flex; align-items:center; gap:8px; padding:10px 12px; background:#f8fafc; border-bottom:1px solid #eef2f6; }
            .ol-sodocs-group header strong { flex:1; color:#334155; font-size:12px; }
            .ol-sodocs-group header > span:last-child { background:#e2e8f0; color:#475569; border-radius:999px; padding:1px 9px; font-size:11px; font-weight:700; }
            .ol-sodocs-badge { min-width:36px; height:24px; padding:0 6px; border-radius:7px; display:inline-flex; align-items:center; justify-content:center; font-size:9.5px; font-weight:800; color:#fff; letter-spacing:.03em; }
            .ol-sodocs-row { width:100%; display:flex; align-items:center; justify-content:space-between; gap:8px; padding:9px 12px; border:0; border-bottom:1px solid #f1f5f9; background:#fff; text-align:left; }
            .ol-sodocs-row:last-child { border-bottom:0; }
            .ol-sodocs-row > span { color:#1d4ed8; font-size:12.5px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
            .ol-sodocs-status { font-size:10px; font-weight:700; padding:2px 8px; border-radius:999px; white-space:nowrap; }
            .ol-sodocs-status.is-green { background:#dcfce7; color:#15803d; }
            .ol-sodocs-status.is-red { background:#fee2e2; color:#b91c1c; }
            .ol-sodocs-status.is-amber { background:#fef3c7; color:#b45309; }
            .ol-sodocs-status.is-gray { background:#eef2f6; color:#475569; }
        `;
        document.head.appendChild(style);
    }
})();
