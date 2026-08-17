frappe.ui.form.on("Sales Order Technical List Revision", {
    refresh(frm) {
        if (frm.is_new()) return;
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__("Sync Sales Order"), async () => {
                await frappe.call({
                    method: "orderlift.orderlift_sig.technical_list.sync_revision",
                    args: { revision: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Synchronizing Sales Order..."),
                });
                await frm.reload_doc();
            });
        }
        installProcurementActions(frm);
    },
});

frappe.ui.form.on("Sales Order Technical List Item", {
    items_add(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        frappe.model.set_value(cdt, cdn, {
            line_key: row.line_key || newDesignLineKey(),
            execution_qty: row.execution_qty || 1,
            conversion_factor: row.conversion_factor || 1,
            execution_relevant: 1,
        });
    },
    async item_code(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.item_code || row.sales_order_item) return;
        const response = await frappe.db.get_value(
            "Item",
            row.item_code,
            ["item_name", "description", "stock_uom", "is_stock_item"],
        );
        const item = response.message || {};
        await frappe.model.set_value(cdt, cdn, {
            item_name: item.item_name || row.item_code,
            description: item.description || "",
            is_stock_item: Number(item.is_stock_item || 0),
            uom: item.stock_uom || row.uom || "",
            stock_uom: item.stock_uom || "",
            conversion_factor: 1,
            execution_qty: row.execution_qty || 1,
            execution_relevant: 1,
        });
    },
    async uom(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.item_code || !row.uom || row.sales_order_item) return;
        if (row.uom === row.stock_uom) {
            await frappe.model.set_value(cdt, cdn, "conversion_factor", 1);
            return;
        }
        const response = await frappe.db.get_value(
            "UOM Conversion Detail",
            { parent: row.item_code, uom: row.uom },
            "conversion_factor",
        );
        await frappe.model.set_value(
            cdt,
            cdn,
            "conversion_factor",
            Number(response.message?.conversion_factor || 1),
        );
    },
    execution_qty(frm, cdt, cdn) {
        updateTechnicalQuantities(cdt, cdn);
    },
    conversion_factor(frm, cdt, cdn) {
        updateTechnicalQuantities(cdt, cdn);
    },
});

function newDesignLineKey() {
    return `ADD-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

function updateTechnicalQuantities(cdt, cdn) {
    const row = locals[cdt][cdn];
    const executionQty = Number(row.execution_qty || 0);
    const salesOrderQty = Number(row.sales_order_qty || 0);
    const factor = Number(row.conversion_factor || 1);
    frappe.model.set_value(cdt, cdn, {
        variance_qty: executionQty - salesOrderQty,
        execution_stock_qty: executionQty * factor,
    });
}

async function installProcurementActions(frm) {
    if (frm.doc.docstatus !== 1) return;
    const response = await frappe.call({
        method: "orderlift.orderlift_logistics.technical_procurement.get_available_actions",
        args: { reference_doctype: frm.doctype, reference_name: frm.doc.name },
    });
    const payload = response.message || {};
    (payload.actions || []).forEach((action) => {
        frm.add_custom_button(__(action.label), async () => {
            const args = { revision: frm.doc.name, selected_row_ids: JSON.stringify(action.row_ids || []) };
            if (action.adapter_key === "revision_to_purchase_order") {
                const values = await promptTechnicalSupplier();
                if (!values) return;
                args.supplier = values.supplier;
            }
            const METHODS = {
                revision_to_material_request: "orderlift.orderlift_logistics.technical_procurement.create_material_request",
                revision_to_purchase_order: "orderlift.orderlift_logistics.technical_procurement.create_purchase_order",
                revision_to_delivery_note: "orderlift.orderlift_logistics.technical_procurement.create_delivery_note",
            };
            const method = METHODS[action.adapter_key];
            if (!method) {
                frappe.msgprint(__("Unsupported technical procurement action."));
                return;
            }
            const created = await frappe.call({ method, args, freeze: true, freeze_message: __("Creating procurement document...") });
            const result = created.message || {};
            if (result.doctype && result.name) frappe.set_route("Form", result.doctype, result.name);
        }, __("Technical Procurement"));
    });
}

function promptTechnicalSupplier() {
    return new Promise((resolve) => {
        const dialog = new frappe.ui.Dialog({
            title: __("Create Purchase Order"),
            fields: [{ fieldname: "supplier", fieldtype: "Link", options: "Supplier", label: __("Supplier"), reqd: 1 }],
            primary_action_label: __("Create"),
            primary_action(values) {
                dialog.hide();
                resolve(values);
            },
        });
        dialog.$wrapper.on("hidden.bs.modal", () => resolve(null));
        dialog.show();
    });
}
