/* Purchase Order live stock overview.
 *
 * Shows current company stock and supplier-side stock for the ordered items so
 * the purchaser can see whether the goods already exist before buying. Nothing
 * is persisted; the read-only tables and item-grid columns refresh on form load
 * and on item/supplier changes with a guarded sync that never dirties the form.
 */
frappe.ui.form.on("Purchase Order", {
    refresh(frm) {
        refreshPurchaseOrderStockOverview(frm);
    },
    supplier(frm) {
        schedulePurchaseOrderStockOverviewRefresh(frm);
    },
    items_add() {
        const frm = cur_frm;
        if (frm) schedulePurchaseOrderStockOverviewRefresh(frm);
    },
    items_remove() {
        const frm = cur_frm;
        if (frm) schedulePurchaseOrderStockOverviewRefresh(frm);
    },
});

frappe.ui.form.on("Purchase Order Item", {
    item_code(frm) {
        schedulePurchaseOrderStockOverviewRefresh(frm);
    },
});

const PURCHASE_ORDER_STOCK_METHOD = "orderlift.orderlift_sales.utils.item_price_tools.get_transaction_stock_snapshot";

function schedulePurchaseOrderStockOverviewRefresh(frm) {
    if (!frm || !frm.fields_dict) return;
    if (!frm.fields_dict.custom_warehouse_stock_snapshot
        && !frm.fields_dict.custom_shared_company_stock
        && !hasPurchaseOrderItemStockField(frm)) return;
    window.clearTimeout(frm.__orderlift_stock_overview_timer);
    frm.__orderlift_stock_overview_timer = window.setTimeout(() => refreshPurchaseOrderStockOverview(frm), 300);
}

async function refreshPurchaseOrderStockOverview(frm) {
    if (!frm || frm.__orderlift_refreshing_stock_overview) return;
    const itemCodes = purchaseOrderItemCodes(frm);
    if (!itemCodes.length) {
        setPurchaseOrderStockOverview(frm, [], {}, {}, []);
        return;
    }
    frm.__orderlift_refreshing_stock_overview = true;
    try {
        const buyingPriceLists = purchaseOrderPriceLists(frm.doc.selected_buying_price_lists)
            .concat(purchaseOrderPriceLists(frm.doc.custom_source_buying_price_lists))
            .concat((frm.doc.items || []).map((row) => String(row.custom_source_buying_price_list || "").trim()).filter(Boolean));
        if (frm.doc.buying_price_list) buyingPriceLists.push(String(frm.doc.buying_price_list).trim());
        const response = await frappe.call({
            method: PURCHASE_ORDER_STOCK_METHOD,
            args: {
                item_codes: JSON.stringify(itemCodes),
                company: frm.doc.company || "",
                buying_price_lists: JSON.stringify(buyingPriceLists),
                supplier: frm.doc.supplier || "",
            },
        });
        const payload = response.message || {};
        setPurchaseOrderStockOverview(frm, payload.rows || [], payload.totals || {}, payload.item_totals || {}, payload.shared_rows || []);
    } catch (error) {
        console.error("Orderlift Purchase Order stock overview failed", error);
    } finally {
        frm.__orderlift_refreshing_stock_overview = false;
    }
}

function purchaseOrderPriceLists(rows) {
    const out = [];
    (rows || []).forEach((row) => {
        const name = String(row.price_list || "").trim();
        if (name && !out.includes(name)) out.push(name);
    });
    return out;
}

function purchaseOrderItemCodes(frm) {
    const out = [];
    (frm.doc.items || []).forEach((row) => {
        const itemCode = String(row.item_code || "").trim();
        if (itemCode && !out.includes(itemCode)) out.push(itemCode);
    });
    return out;
}

function setPurchaseOrderStockOverview(frm, rows, totals, itemTotals, sharedRows) {
    const wasUnsaved = frm.doc && frm.doc.__unsaved;
    var changed = false;
    if (frm.fields_dict.custom_warehouse_stock_snapshot) {
        changed = syncPurchaseOrderStockSnapshotTable(frm, rows || []) || changed;
    }
    if (frm.fields_dict.custom_shared_company_stock) {
        changed = syncPurchaseOrderSharedCompanyStockTable(frm, sharedRows || []) || changed;
    }
    if (hasPurchaseOrderItemStockField(frm)) {
        const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
        const hasAvail = Boolean(grid && grid.get_field && grid.get_field("custom_available_after_so_qty"));
        const hasProjected = Boolean(grid && grid.get_field && grid.get_field("custom_projected_available_qty"));
        (frm.doc.items || []).forEach((row) => {
            const itemCode = String(row.item_code || "").trim();
            const outlook = (itemTotals || {})[itemCode] || {};
            const nextQty = Number((totals || {})[itemCode] || 0);
            if (Math.abs(Number(row.custom_current_company_stock_qty || 0) - nextQty) >= 0.000001) {
                row.custom_current_company_stock_qty = nextQty;
                changed = true;
            }
            if (hasAvail) {
                const nextAvail = Number(outlook.available_after_so || 0);
                if (Math.abs(Number(row.custom_available_after_so_qty || 0) - nextAvail) >= 0.000001) {
                    row.custom_available_after_so_qty = nextAvail;
                    changed = true;
                }
            }
            if (hasProjected) {
                const nextProjected = Number(outlook.projected_available || 0);
                if (Math.abs(Number(row.custom_projected_available_qty || 0) - nextProjected) >= 0.000001) {
                    row.custom_projected_available_qty = nextProjected;
                    changed = true;
                }
            }
        });
        if (changed) frm.refresh_field("items");
    }
    if (changed && !wasUnsaved && frm.doc) {
        frm.doc.__unsaved = 0;
        frm.wrapper && $(frm.wrapper).find(".indicator-pill.red, .indicator-pill.orange").remove();
    }
}

function syncPurchaseOrderStockSnapshotTable(frm, rows) {
    const fieldname = "custom_warehouse_stock_snapshot";
    const nextRows = (rows || []).map(normalizePurchaseOrderStockRow);
    if (purchaseOrderStockRowsMatch(frm.doc[fieldname] || [], nextRows)) return false;
    frappe.model.clear_table(frm.doc, fieldname);
    nextRows.forEach((values) => {
        const child = frappe.model.add_child(frm.doc, "Orderlift Transaction Warehouse Stock", fieldname);
        Object.assign(child, values);
    });
    frm.refresh_field(fieldname);
    return true;
}

function syncPurchaseOrderSharedCompanyStockTable(frm, rows) {
    const fieldname = "custom_shared_company_stock";
    const nextRows = (rows || []).map(normalizePurchaseOrderSharedRow);
    if (purchaseOrderSharedRowsMatch(frm.doc[fieldname] || [], nextRows)) return false;
    frappe.model.clear_table(frm.doc, fieldname);
    nextRows.forEach((values) => {
        const child = frappe.model.add_child(frm.doc, "Orderlift Shared Company Stock", fieldname);
        Object.assign(child, values);
    });
    frm.refresh_field(fieldname);
    return true;
}

function normalizePurchaseOrderStockRow(row) {
    return {
        item_code: row.item_code || "",
        item_name: row.item_name || "",
        warehouse: row.warehouse || "",
        actual_qty: Number(row.actual_qty || 0),
        available_after_so_qty: Number(row.available_after_so_qty || 0),
        projected_available_qty: Number(row.projected_available_qty || 0),
    };
}

function normalizePurchaseOrderSharedRow(row) {
    return {
        company: row.company || "",
        item_code: row.item_code || "",
        item_name: row.item_name || "",
        warehouse: row.warehouse || "",
        actual_qty: Number(row.actual_qty || 0),
        available_after_so_qty: Number(row.available_after_so_qty || 0),
        projected_available_qty: Number(row.projected_available_qty || 0),
    };
}

function purchaseOrderStockRowsMatch(currentRows, nextRows) {
    const current = (currentRows || []).map(normalizePurchaseOrderStockRow);
    if (current.length !== nextRows.length) return false;
    return current.every((row, index) => {
        const next = nextRows[index] || {};
        return row.item_code === next.item_code
            && row.item_name === next.item_name
            && row.warehouse === next.warehouse
            && Math.abs(Number(row.actual_qty || 0) - Number(next.actual_qty || 0)) < 0.000001
            && Math.abs(Number(row.available_after_so_qty || 0) - Number(next.available_after_so_qty || 0)) < 0.000001
            && Math.abs(Number(row.projected_available_qty || 0) - Number(next.projected_available_qty || 0)) < 0.000001;
    });
}

function purchaseOrderSharedRowsMatch(currentRows, nextRows) {
    const current = (currentRows || []).map(normalizePurchaseOrderSharedRow);
    if (current.length !== nextRows.length) return false;
    return current.every((row, index) => {
        const next = nextRows[index] || {};
        return row.company === next.company
            && row.item_code === next.item_code
            && row.warehouse === next.warehouse
            && Math.abs(Number(row.actual_qty || 0) - Number(next.actual_qty || 0)) < 0.000001
            && Math.abs(Number(row.available_after_so_qty || 0) - Number(next.available_after_so_qty || 0)) < 0.000001
            && Math.abs(Number(row.projected_available_qty || 0) - Number(next.projected_available_qty || 0)) < 0.000001;
    });
}

function hasPurchaseOrderItemStockField(frm) {
    const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
    return Boolean(grid && grid.get_field && grid.get_field("custom_current_company_stock_qty"));
}
