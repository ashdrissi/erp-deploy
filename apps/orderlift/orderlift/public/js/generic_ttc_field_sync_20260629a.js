frappe.ui.form.on("Sales Order", {
    refresh: function (frm) {
        syncDocTTCFields(frm);
    },
    taxes_and_charges: function (frm) {
        if (frm.is_new() || !frm.doc.__unsaved) {
            setTimeout(function () { syncDocTTCFields(frm); }, 500);
        }
    },
});

frappe.ui.form.on("Sales Order Item", {
    rate: function (frm, cdt, cdn) {
        syncDocTTCFields(frm);
    },
    qty: function (frm, cdt, cdn) {
        syncDocTTCFields(frm);
    },
});

frappe.ui.form.on("Delivery Note", {
    refresh: function (frm) {
        syncDocTTCFields(frm);
    },
    taxes_and_charges: function (frm) {
        if (frm.is_new() || !frm.doc.__unsaved) {
            setTimeout(function () { syncDocTTCFields(frm); }, 500);
        }
    },
});

frappe.ui.form.on("Delivery Note Item", {
    rate: function (frm, cdt, cdn) {
        syncDocTTCFields(frm);
    },
    qty: function (frm, cdt, cdn) {
        syncDocTTCFields(frm);
    },
});

frappe.ui.form.on("Sales Invoice", {
    refresh: function (frm) {
        syncDocTTCFields(frm);
    },
    taxes_and_charges: function (frm) {
        if (frm.is_new() || !frm.doc.__unsaved) {
            setTimeout(function () { syncDocTTCFields(frm); }, 500);
        }
    },
});

frappe.ui.form.on("Sales Invoice Item", {
    rate: function (frm, cdt, cdn) {
        syncDocTTCFields(frm);
    },
    qty: function (frm, cdt, cdn) {
        syncDocTTCFields(frm);
    },
});

frappe.ui.form.on("Purchase Order", {
    refresh: function (frm) {
        syncDocTTCFields(frm);
    },
    taxes_and_charges: function (frm) {
        if (frm.is_new() || !frm.doc.__unsaved) {
            setTimeout(function () { syncDocTTCFields(frm); }, 500);
        }
    },
});

frappe.ui.form.on("Purchase Order Item", {
    rate: function (frm, cdt, cdn) {
        syncDocTTCFields(frm);
    },
    qty: function (frm, cdt, cdn) {
        syncDocTTCFields(frm);
    },
});

frappe.ui.form.on("Purchase Invoice", {
    refresh: function (frm) {
        syncDocTTCFields(frm);
    },
    taxes_and_charges: function (frm) {
        if (frm.is_new() || !frm.doc.__unsaved) {
            setTimeout(function () { syncDocTTCFields(frm); }, 500);
        }
    },
});

frappe.ui.form.on("Purchase Invoice Item", {
    rate: function (frm, cdt, cdn) {
        syncDocTTCFields(frm);
    },
    qty: function (frm, cdt, cdn) {
        syncDocTTCFields(frm);
    },
});

frappe.ui.form.on("Purchase Receipt", {
    refresh: function (frm) {
        syncDocTTCFields(frm);
    },
    taxes_and_charges: function (frm) {
        if (frm.is_new() || !frm.doc.__unsaved) {
            setTimeout(function () { syncDocTTCFields(frm); }, 500);
        }
    },
});

frappe.ui.form.on("Purchase Receipt Item", {
    rate: function (frm, cdt, cdn) {
        syncDocTTCFields(frm);
    },
    qty: function (frm, cdt, cdn) {
        syncDocTTCFields(frm);
    },
});

frappe.ui.form.on("Supplier Quotation", {
    refresh: function (frm) {
        syncDocTTCFields(frm);
    },
    taxes_and_charges: function (frm) {
        if (frm.is_new() || !frm.doc.__unsaved) {
            setTimeout(function () { syncDocTTCFields(frm); }, 500);
        }
    },
});

frappe.ui.form.on("Supplier Quotation Item", {
    rate: function (frm, cdt, cdn) {
        syncDocTTCFields(frm);
    },
    qty: function (frm, cdt, cdn) {
        syncDocTTCFields(frm);
    },
});

function syncDocTTCFields(frm) {
    if (!frm || !frm.doc || !frm.doc.items) return;
    if (Number(frm.doc.docstatus || 0) !== 0) return;
    if (frm.setting_dependency || frm._sync_ttc_in_progress) return;
    frm._sync_ttc_in_progress = true;
    try {
        var totalTaxRate = docTotalTaxRate(frm);
        (frm.doc.items || []).forEach(function (row) {
            if (!row || !("custom_pu_ttc" in row)) return;
            var rate = Number(row.rate || 0);
            var qty = Number(row.qty || 1) || 1;
            var amount = rate * qty;
            var taxAmount = roundTTC(amount * totalTaxRate / 100);
            var puTtc = roundTTC(rate * (1 + totalTaxRate / 100));
            var ptTtc = roundTTC(amount * (1 + totalTaxRate / 100));
            // Round + only write when actually changed. This handler runs on
            // refresh (which fires after every save); writing unrounded floats
            // (e.g. 11.856000000000002) never matched the stored value, so the
            // form re-dirtied after every save (endless "Not Saved").
            setTTCFieldIfChanged(row, "custom_applied_taxes", taxAmount);
            setTTCFieldIfChanged(row, "custom_pu_ttc", puTtc);
            setTTCFieldIfChanged(row, "custom_pt_ttc", ptTtc);
        });
    } finally {
        frm._sync_ttc_in_progress = false;
    }
}

function roundTTC(value) {
    return Math.round((Number(value) || 0) * 100) / 100;
}

function setTTCFieldIfChanged(row, field, value) {
    if (!(field in row)) return;
    if (Math.abs(Number(row[field] || 0) - Number(value || 0)) < 0.005) return;
    frappe.model.set_value(row.doctype, row.name, field, value);
}

function docTotalTaxRate(frm) {
    var taxes = frm.doc.taxes || [];
    var total = 0;
    taxes.forEach(function (t) {
        if (t.charge_type !== "Actual") {
            total += Number(t.rate || 0);
        }
    });
    return total;
}
