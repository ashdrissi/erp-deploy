(function () {
    const PRIVILEGED_ROLES = new Set(["Orderlift Admin", "System Manager", "Administrator"]);

    function userHasPrivilegedRole() {
        const roles = frappe.user_roles();
        for (let i = 0; i < roles.length; i++) {
            if (PRIVILEGED_ROLES.has(roles[i])) return true;
        }
        return false;
    }

    const RATE_FIELDS = [
        "basic_rate",
        "basic_amount",
        "valuation_rate",
        "set_basic_rate_manually",
        "allow_zero_valuation_rate",
        "rates_section",
    ];

    function hideRateFields(frm) {
        if (userHasPrivilegedRole()) return;
        RATE_FIELDS.forEach(function (fieldname) {
            const df = frappe.meta.get_docfield("Stock Entry Detail", fieldname);
            if (df) {
                df.hidden = 1;
                df.__orderlift_rate_hidden = true;
            }
        });
    }

    function restoreRateFields(frm) {
        if (!userHasPrivilegedRole()) return;
        RATE_FIELDS.forEach(function (fieldname) {
            const df = frappe.meta.get_docfield("Stock Entry Detail", fieldname);
            if (df && df.__orderlift_rate_hidden) {
                df.hidden = 0;
                df.__orderlift_rate_hidden = false;
            }
        });
    }

    frappe.ui.form.on("Stock Entry", {
        onload(frm) {
            restoreRateFields(frm);
        },
        refresh(frm) {
            if (frm.is_new() || frm.doc.docstatus === 0) {
                hideRateFields(frm);
            }
        },
    });
})();
