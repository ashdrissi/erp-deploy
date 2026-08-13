frappe.ui.form.on("Sales Order", {
    refresh: function (frm) {
        syncDocTTCFields(frm);
        applySalesPrecisionDisplay(frm);
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
        if (frm.is_new()) {
            syncDocTTCFields(frm);
        }
        applySalesPrecisionDisplay(frm);
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
        if (frm.is_new()) {
            syncDocTTCFields(frm);
        }
        applySalesPrecisionDisplay(frm);
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
        if (frm.is_new()) {
            syncDocTTCFields(frm);
        }
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
        if (frm.is_new()) {
            syncDocTTCFields(frm);
        }
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
        if (frm.is_new()) {
            syncDocTTCFields(frm);
        }
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
            var taxAmount = amount * totalTaxRate / 100;
            var puTtc = rate * (1 + totalTaxRate / 100);
            var ptTtc = amount * (1 + totalTaxRate / 100);
            setTTCFieldIfChanged(row, "custom_applied_taxes", taxAmount);
            setTTCFieldIfChanged(row, "custom_pu_ttc", puTtc);
            setTTCFieldIfChanged(row, "custom_pt_ttc", ptTtc);
        });
    } finally {
        frm._sync_ttc_in_progress = false;
    }
}

function setTTCFieldIfChanged(row, field, value) {
    if (!(field in row)) return;
    if (Math.abs(Number(row[field] || 0) - Number(value || 0)) < 1e-9) return;
    frappe.model.set_value(row.doctype, row.name, field, value);
}

function applySalesPrecisionDisplay(frm) {
    if (!frm || !["Sales Order", "Delivery Note", "Sales Invoice"].includes(frm.doctype)) return;
    var grid = frm.fields_dict && frm.fields_dict.items && frm.fields_dict.items.grid;
    if (!grid || !grid.get_field) return;
    [
        ["rate", "PU HT"],
        ["amount", "PT HT"],
        ["custom_applied_taxes", "Taxes"],
        ["custom_pu_ttc", "PU TTC"],
        ["custom_pt_ttc", "PT TTC"],
    ].forEach(function (entry) {
        var fieldname = entry[0];
        var field = grid.get_field(fieldname);
        if (!field) return;
        grid.update_docfield_property(fieldname, "label", __(entry[1]));
        grid.update_docfield_property(fieldname, "precision", "9");
        field.formatter = function (value) {
            if (frappe.format) {
                return frappe.format(Number(value || 0), { fieldtype: "Currency", precision: 2 });
            }
            return Number(value || 0).toFixed(2);
        };
    });
    ["qty", "stock_qty", "conversion_factor"].forEach(function (fieldname) {
        var field = grid.get_field(fieldname);
        if (!field) return;
        field.formatter = function (value) {
            return Number(value || 0).toFixed(2);
        };
    });
    grid.refresh();
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
