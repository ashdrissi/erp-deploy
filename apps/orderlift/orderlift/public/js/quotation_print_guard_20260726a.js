(function () {
    const HIDDEN_CLASS = "orderlift-draft-print-hidden";

    function submitted(frm) {
        return Number((frm.doc && frm.doc.docstatus) || 0) === 1;
    }

    function showBlockedMessage() {
        frappe.msgprint({
            title: __("Submit Quotation Before Printing"),
            message: __("This Quotation must be submitted before it can be printed or exported as PDF."),
            indicator: "orange",
        });
    }

    function installPrintMethodGuard(frm) {
        if (frm.__orderlift_original_print_doc || typeof frm.print_doc !== "function") return;
        frm.__orderlift_original_print_doc = frm.print_doc.bind(frm);
        frm.print_doc = function () {
            if (!submitted(frm)) {
                showBlockedMessage();
                return;
            }
            return frm.__orderlift_original_print_doc();
        };
    }

    function updatePrintActions(frm) {
        if (!frm || !frm.page || !frm.page.wrapper) return;
        const wrapper = $(frm.page.wrapper);
        wrapper.find(`.${HIDDEN_CLASS}`).removeClass(HIDDEN_CLASS);
        wrapper.find(".ol-print-shortcut, .ol-print-shortcut-group").remove();
        if (submitted(frm)) return;

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

    if (!document.getElementById("orderlift-draft-print-style")) {
        const style = document.createElement("style");
        style.id = "orderlift-draft-print-style";
        style.textContent = `.${HIDDEN_CLASS} { display: none !important; }`;
        document.head.appendChild(style);
    }

    frappe.ui.form.on("Quotation", {
        refresh(frm) {
            enforceSubmittedOnlyPrinting(frm);
        },
    });
})();
