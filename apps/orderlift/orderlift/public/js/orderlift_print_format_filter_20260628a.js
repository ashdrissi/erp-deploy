(function () {
    function activeCompany() {
        return window.orderlift?.getActiveCompany?.() || frappe.boot?.orderlift_company_access?.current_company || "";
    }

    function printFormatDoc(name) {
        return window.locals?.["Print Format"]?.[name] || null;
    }

    function allowedForCompany(name, company) {
        if (!name || name === "Standard" || !company) return true;
        const doc = printFormatDoc(name);
        if (!doc) return true;
        const formatCompany = (doc.custom_company || "").trim();
        return formatCompany === company;
    }

    function patchGetPrintFormats() {
        if (!frappe.meta || frappe.meta.__orderlift_print_format_filter_patched) return;
        const original = frappe.meta.get_print_formats;
        if (typeof original !== "function") return;

        frappe.meta.get_print_formats = function (doctype) {
            const formats = original.call(this, doctype) || [];
            const company = activeCompany();
            const seen = new Set();
            return formats.filter((name) => {
                if (seen.has(name)) return false;
                seen.add(name);
                return allowedForCompany(name, company);
            });
        };
        frappe.meta.__orderlift_print_format_filter_patched = true;
    }

    if (typeof frappe.ready === "function") frappe.ready(patchGetPrintFormats);
    patchGetPrintFormats();
})();
