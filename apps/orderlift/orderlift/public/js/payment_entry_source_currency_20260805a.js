(function () {
    if (window.__orderliftPaymentEntrySourceCurrencyRegistered) return;
    window.__orderliftPaymentEntrySourceCurrencyRegistered = true;

    const SOURCE_CURRENCY = "custom_source_document_currency";
    const SOURCE_AMOUNT = "custom_source_payment_amount";
    const SOURCE_RATE = "custom_source_to_company_exchange_rate";
    const COMPANY_AMOUNT = "custom_converted_company_amount";

    function refreshSourcePayment(frm) {
        const sourceCurrency = frm.doc[SOURCE_CURRENCY];
        const companyCurrency = frappe.get_doc(":Company", frm.doc.company)?.default_currency;
        frm.set_df_property(SOURCE_RATE, "read_only", sourceCurrency === companyCurrency ? 1 : 0);
        if (sourceCurrency && companyCurrency) {
            frm.set_df_property(
                SOURCE_RATE,
                "description",
                __(`1 ${sourceCurrency} = [rate] ${companyCurrency}`)
            );
        }
        frm.set_currency_labels([SOURCE_AMOUNT], sourceCurrency);
        frm.set_currency_labels([COMPANY_AMOUNT], companyCurrency);
    }

    function syncSourcePayment(frm) {
        if (
            frm.doc.docstatus !== 0 ||
            !frm.doc[SOURCE_CURRENCY] ||
            !flt(frm.doc[SOURCE_AMOUNT]) ||
            !flt(frm.doc[SOURCE_RATE])
        ) {
            return;
        }

        const requestId = (frm.__orderliftSourcePaymentRequestId || 0) + 1;
        frm.__orderliftSourcePaymentRequestId = requestId;
        frappe.call({
            method: "orderlift.orderlift_finance.payment_entry_currency.preview_source_currency_payment",
            args: { doc: frm.doc },
            callback: function (response) {
                if (requestId !== frm.__orderliftSourcePaymentRequestId || !response.message) return;
                const values = response.message;
                const references = values.references || [];
                delete values.references;
                Object.assign(frm.doc, values);
                references.forEach((value) => {
                    const row = (frm.doc.references || []).find((candidate) => candidate.name === value.name);
                    if (row) row.allocated_amount = value.allocated_amount;
                });
                frm.dirty();
                frm.refresh_fields();
                refreshSourcePayment(frm);
            },
        });
    }

    function clearSourcePaymentIfNoReferences(frm) {
        if ((frm.doc.references || []).some((row) => row.reference_name)) return;
        frm.set_value({
            [SOURCE_CURRENCY]: null,
            [SOURCE_AMOUNT]: 0,
            [SOURCE_RATE]: 0,
            [COMPANY_AMOUNT]: 0,
        });
    }

    frappe.ui.form.on("Payment Entry", {
        refresh: refreshSourcePayment,
        paid_from: syncSourcePayment,
        paid_to: syncSourcePayment,
        payment_type: syncSourcePayment,
        posting_date: syncSourcePayment,
        custom_source_payment_amount: syncSourcePayment,
        custom_source_to_company_exchange_rate: syncSourcePayment,
    });

    frappe.ui.form.on("Payment Entry Reference", {
        references_remove: clearSourcePaymentIfNoReferences,
    });
})();
