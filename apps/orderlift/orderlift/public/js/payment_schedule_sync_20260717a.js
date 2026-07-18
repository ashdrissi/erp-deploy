(function () {
    const SUPPORTED_DOCTYPES = ["Quotation", "Sales Order", "Sales Invoice"];

    function canRecalculate(frm) {
        return Number(frm?.doc?.docstatus || 0) === 0 && Array.isArray(frm?.doc?.payment_schedule);
    }

    function currencyPrecision() {
        return cint(frappe?.boot?.sysdefaults?.currency_precision || 2);
    }

    function documentTotal(frm) {
        const roundedTotal = flt(frm?.doc?.rounded_total || 0);
        return roundedTotal || flt(frm?.doc?.grand_total || 0);
    }

    function rounded(value, precision) {
        const factor = Math.pow(10, precision);
        return Math.round((flt(value) + Number.EPSILON) * factor) / factor;
    }

    async function recalculatePaymentSchedule(frm, options = {}) {
        if (!canRecalculate(frm)) return;

        const rows = frm.doc.payment_schedule || [];
        if (!rows.length) return;

        const total = documentTotal(frm);
        const precision = currencyPrecision();
        const portionsTotal = rows.reduce((sum, row) => sum + flt(row.invoice_portion || 0), 0);
        const amounts = rows.map((row) => rounded(total * flt(row.invoice_portion || 0) / 100, precision));

        // When the schedule is exactly 100%, put any currency rounding residue on
        // the final instalment so the schedule always reconciles to Grand Total.
        if (Math.abs(portionsTotal - 100) <= 0.0001 && amounts.length) {
            const previous = amounts.slice(0, -1).reduce((sum, amount) => sum + amount, 0);
            amounts[amounts.length - 1] = rounded(total - previous, precision);
        }

        const updates = [];
        rows.forEach((row, index) => {
            if (Math.abs(flt(row.payment_amount || 0) - amounts[index]) <= Math.pow(10, -precision) / 2) return;
            updates.push(frappe.model.set_value(row.doctype, row.name, "payment_amount", amounts[index]));
        });
        await Promise.all(updates);
        frm.refresh_field("payment_schedule");

        if (options.notify) {
            frappe.show_alert({
                message: __("Payment Schedule recalculated from the current document total."),
                indicator: "green",
            });
        }
    }

    function addRecalculateButton(frm) {
        if (!canRecalculate(frm) || !(frm.doc.payment_schedule || []).length) return;
        frm.add_custom_button(
            __("Recalculate Payment Schedule"),
            () => recalculatePaymentSchedule(frm, { notify: true }),
            __("Tools")
        );
    }

    SUPPORTED_DOCTYPES.forEach((doctype) => {
        frappe.ui.form.on(doctype, {
            refresh(frm) {
                addRecalculateButton(frm);
            },
            rounded_total(frm) {
                recalculatePaymentSchedule(frm);
            },
            grand_total(frm) {
                recalculatePaymentSchedule(frm);
            },
        });
    });

    frappe.ui.form.on("Payment Schedule", {
        invoice_portion(frm, cdt, cdn) {
            recalculatePaymentSchedule(frm);
        },
    });
})();
