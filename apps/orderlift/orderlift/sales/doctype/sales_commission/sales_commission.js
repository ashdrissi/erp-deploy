// Copyright (c) 2026, Syntax Line and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sales Commission", {
    refresh: function (frm) {
        // "Mark as Paid" button — only visible on submitted, approved commissions
        if (frm.doc.docstatus === 1 && frm.doc.status === "Approved") {
            frm.add_custom_button(
                __("Mark as Paid"),
                function () {
                    frappe.prompt(
                        [
                            {
                                label: __("Payment Date"),
                                fieldname: "payment_date",
                                fieldtype: "Date",
                                default: frappe.datetime.get_today(),
                                reqd: 1,
                            },
                            {
                                label: __("Payment Reference"),
                                fieldname: "payment_reference",
                                fieldtype: "Data",
                                description: __(
                                    "Bank transfer reference or payment entry number"
                                ),
                            },
                        ],
                        function (values) {
                            frm.call("mark_as_paid", {
                                payment_date: values.payment_date,
                                payment_reference: values.payment_reference,
                            }).then(function () {
                                frm.reload_doc();
                            });
                        },
                        __("Payment Details"),
                        __("Confirm Payment")
                    );
                },
                __("Actions")
            );
        }

        // Color-coded status indicator
        if (frm.doc.status === "Pending") {
            frm.page.set_indicator(__("Pending"), "orange");
        } else if (frm.doc.status === "Approved") {
            frm.page.set_indicator(__("Approved"), "blue");
        } else if (frm.doc.status === "Paid") {
            frm.page.set_indicator(__("Paid"), "green");
        } else if (frm.doc.status === "Cancelled") {
            frm.page.set_indicator(__("Cancelled"), "red");
        }
    },

    commission_rate: function (frm) {
        _recalculate(frm);
    },

    base_amount: function (frm) {
        _recalculate(frm);
    },

    sales_order: function (frm) {
        // Auto-fetch customer when sales order is selected
        if (frm.doc.sales_order) {
            frappe.db.get_value(
                "Sales Order",
                frm.doc.sales_order,
                ["customer", "customer_name", "project", "company"],
                function (r) {
                    if (r) {
                        frm.set_value("customer", r.customer);
                        frm.set_value("customer_name", r.customer_name);
                        if (r.project) {
                            frm.set_value("project", r.project);
                        }
                        if (!frm.doc.company) {
                            frm.set_value("company", r.company);
                        }
                    }
                }
            );
        }
    },
});

function _recalculate(frm) {
    if (frm.doc.base_amount && frm.doc.commission_rate) {
        var amount = frm.doc.base_amount * (frm.doc.commission_rate / 100);
        frm.set_value("commission_amount", flt(amount, 2));
    }
}
