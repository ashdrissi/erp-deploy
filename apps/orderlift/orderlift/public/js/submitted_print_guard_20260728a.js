(function () {
    const PROTECTED_DOCTYPES = [
        "Quotation",
        "Sales Order",
        "Delivery Note",
        "Sales Invoice",
        "Payment Entry",
        "Material Request",
        "Request for Quotation",
        "Supplier Quotation",
        "Purchase Order",
        "Purchase Receipt",
        "Purchase Invoice",
        "Stock Entry",
    ];
    const HIDDEN_CLASS = "orderlift-unsubmitted-print-hidden";

    function isSubmitted(frm) {
        return Number((frm.doc && frm.doc.docstatus) || 0) === 1;
    }

    function showBlockedMessage(frm) {
        frappe.msgprint({
            title: __("Submit Document Before Printing"),
            message: __(
                "This {0} must be submitted before it can be printed or exported as PDF.",
                [__(frm.doctype)]
            ),
            indicator: "orange",
        });
    }

    function installPrintMethodGuard(frm) {
        if (frm.__orderlift_submitted_print_guard || typeof frm.print_doc !== "function") {
            return;
        }

        const originalPrintDoc = frm.print_doc.bind(frm);
        frm.__orderlift_submitted_print_guard = true;
        frm.print_doc = function () {
            if (!isSubmitted(frm)) {
                showBlockedMessage(frm);
                return;
            }
            return originalPrintDoc();
        };
    }

    function updatePrintActions(frm) {
        if (!frm || !frm.page || !frm.page.wrapper) return;

        const wrapper = $(frm.page.wrapper);
        wrapper.find(`.${HIDDEN_CLASS}`).removeClass(HIDDEN_CLASS);
        if (isSubmitted(frm)) return;

        wrapper.find("button, a, .dropdown-item").filter(function () {
            const label = String($(this).text() || "").replace(/\s+/g, " ").trim();
            return label === __("Print") || label === __("PDF");
        }).addClass(HIDDEN_CLASS);
    }

    function enforceSubmittedOnlyPrinting(frm) {
        installPrintMethodGuard(frm);
        updatePrintActions(frm);
        window.setTimeout(() => updatePrintActions(frm), 0);
        window.setTimeout(() => updatePrintActions(frm), 250);
    }

    if (!document.getElementById("orderlift-submitted-print-style")) {
        const style = document.createElement("style");
        style.id = "orderlift-submitted-print-style";
        style.textContent = `.${HIDDEN_CLASS} { display: none !important; }`;
        document.head.appendChild(style);
    }

    PROTECTED_DOCTYPES.forEach((doctype) => {
        frappe.ui.form.on(doctype, {
            refresh(frm) {
                enforceSubmittedOnlyPrinting(frm);
            },
        });
    });
})();
