(function () {
    function replaceCloseWithLost(frm) {
        if (!frm || frm.is_new() || Number(frm.doc.docstatus || 0) !== 0) return;

        frm.remove_custom_button(__("Close"));
        frm.remove_custom_button(__("Mark as Lost"));

        const canWrite = Boolean(frm.perm && frm.perm[0] && frm.perm[0].write);
        if (!canWrite || frm.doc.status !== "Open") return;

        frm.add_custom_button(__("Mark as Lost"), () => {
            frm.trigger("set_as_lost_dialog");
        });
    }

    frappe.ui.form.on("Opportunity", {
        refresh(frm) {
            replaceCloseWithLost(frm);
            window.setTimeout(() => replaceCloseWithLost(frm), 0);
        },
    });
})();
