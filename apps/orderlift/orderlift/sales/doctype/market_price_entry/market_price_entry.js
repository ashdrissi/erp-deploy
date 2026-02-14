// Copyright (c) 2026, Syntax Line and contributors
// For license information, please see license.txt

frappe.ui.form.on("Market Price Entry", {
    refresh: function (frm) {
        // Show price comparison indicator
        if (frm.doc.price_difference_percent) {
            var pct = frm.doc.price_difference_percent;
            if (pct > 10) {
                frm.dashboard.set_headline(
                    __("Market price is {0}% higher than ours", [pct.toFixed(1)]),
                    "green"
                );
            } else if (pct < -10) {
                frm.dashboard.set_headline(
                    __("Market price is {0}% lower than ours", [Math.abs(pct).toFixed(1)]),
                    "red"
                );
            } else {
                frm.dashboard.set_headline(
                    __("Market price is within 10% of ours ({0}%)", [pct.toFixed(1)]),
                    "blue"
                );
            }
        }
    },

    item_code: function (frm) {
        if (frm.doc.item_code) {
            frappe.model.with_doctype("Item", function () {
                var hasCostField = frappe.meta.has_field("Item", "custom_current_cost_price");

                if (!hasCostField) {
                    frm.set_value("our_current_price", 0);
                    _recalculate_difference(frm);
                    return;
                }

                // Fetch our current cost price for immediate comparison
                frappe.db.get_value("Item", frm.doc.item_code, "custom_current_cost_price", function (r) {
                    frm.set_value("our_current_price", (r && r.custom_current_cost_price) || 0);
                    _recalculate_difference(frm);
                });
            });
        }
    },

    market_price: function (frm) {
        _recalculate_difference(frm);
    },
});

function _recalculate_difference(frm) {
    var market = frm.doc.market_price || 0;
    var ours = frm.doc.our_current_price || 0;

    frm.set_value("price_difference", market - ours);

    if (ours > 0) {
        frm.set_value("price_difference_percent", ((market - ours) / ours) * 100);
    } else {
        frm.set_value("price_difference_percent", 0);
    }
}
