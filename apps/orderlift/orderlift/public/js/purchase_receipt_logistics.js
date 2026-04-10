frappe.ui.form.on("Purchase Receipt", {
    refresh(frm) {
        if (frm.is_new()) return;

        if (frm.doc.custom_qc_routed) {
            frm.dashboard.add_indicator(__("QC Routed"), "green");
        }

        frm.add_custom_button(__("View QC Routing"), async () => {
            const r = await frappe.call({
                method: "orderlift.logistics.utils.stock_router.get_purchase_receipt_routing_summary",
                args: { purchase_receipt_name: frm.doc.name },
            });

            const data = r.message || {};
            const transfers = (data.transfers || []).map((row) => {
                const status = row.docstatus === 1 ? __("Submitted") : row.docstatus === 2 ? __("Cancelled") : __("Draft");
                return `
                    <tr>
                        <td><a href="/app/stock-entry/${encodeURIComponent(row.name)}">${frappe.utils.escape_html(row.name)}</a></td>
                        <td>${frappe.utils.escape_html(row.to_warehouse || "-")}</td>
                        <td>${frappe.utils.escape_html(status)}</td>
                    </tr>`;
            }).join("");

            const listHtml = (rows, emptyLabel) => rows.length
                ? `<ul style="margin:0;padding-left:18px">${rows.map((row) => `<li>${frappe.utils.escape_html(row.item_code)} <span style="color:#94a3b8">x ${row.qty}</span></li>`).join("")}</ul>`
                : `<div style="color:#94a3b8">${frappe.utils.escape_html(emptyLabel)}</div>`;

            const d = new frappe.ui.Dialog({
                title: __("QC Routing Summary"),
                size: "large",
            });
            d.$body.html(`
                <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-bottom:16px;">
                    <div style="padding:12px;border:1px solid #e2e8f0;border-radius:10px;background:#f8fafc;">
                        <div style="font-weight:700;margin-bottom:6px;">${__("Routing Status")}</div>
                        <div>${data.qc_routed ? __("Purchase Receipt has been routed.") : __("Purchase Receipt has not been routed yet.")}</div>
                        <div style="margin-top:8px;color:${data.real_warehouse ? '#0f766e' : '#dc2626'}">${__("REAL warehouse")}: ${frappe.utils.escape_html(data.real_warehouse || __("Missing"))}</div>
                        <div style="color:${data.return_warehouse ? '#0f766e' : '#dc2626'}">${__("RETURN warehouse")}: ${frappe.utils.escape_html(data.return_warehouse || __("Missing"))}</div>
                    </div>
                    <div style="padding:12px;border:1px solid #e2e8f0;border-radius:10px;background:#f8fafc;">
                        <div style="font-weight:700;margin-bottom:6px;">${__("Quality Inspection Counts")}</div>
                        <div>${__("Passed")}: ${(data.passed || []).length}</div>
                        <div>${__("Failed")}: ${(data.failed || []).length}</div>
                        <div>${__("No QC linked")}: ${(data.no_qi || []).length}</div>
                        <div style="margin-top:6px">${__("Transfers created")}: ${(data.transfers || []).length}</div>
                    </div>
                </div>

                <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-bottom:16px;">
                    <div style="padding:12px;border:1px solid #e2e8f0;border-radius:10px;">
                        <div style="font-weight:700;margin-bottom:6px;">${__("Passed Items")}</div>
                        ${listHtml(data.passed || [], __("No passed items"))}
                    </div>
                    <div style="padding:12px;border:1px solid #e2e8f0;border-radius:10px;">
                        <div style="font-weight:700;margin-bottom:6px;">${__("Failed Items")}</div>
                        ${listHtml(data.failed || [], __("No failed items"))}
                    </div>
                    <div style="padding:12px;border:1px solid #e2e8f0;border-radius:10px;">
                        <div style="font-weight:700;margin-bottom:6px;">${__("No QC Linked")}</div>
                        ${listHtml(data.no_qi || [], __("All items have QC links"))}
                    </div>
                </div>

                <div style="padding:12px;border:1px solid #e2e8f0;border-radius:10px;">
                    <div style="font-weight:700;margin-bottom:8px;">${__("Routing Transfers")}</div>
                    ${(data.transfers || []).length
                        ? `<table class="table table-bordered"><thead><tr><th>${__("Stock Entry")}</th><th>${__("Destination")}</th><th>${__("Status")}</th></tr></thead><tbody>${transfers}</tbody></table>`
                        : `<div style="color:#94a3b8">${__("No routing transfers found for this Purchase Receipt.")}</div>`}
                </div>
            `);
            d.show();
        }, __("Logistics"));
    },
});
