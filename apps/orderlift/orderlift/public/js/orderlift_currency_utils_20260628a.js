(function () {
    window.orderlift = window.orderlift || {};

    function companyAccess() {
        return (frappe.boot && frappe.boot.orderlift_company_access) || {};
    }

    function activeCompany() {
        const access = companyAccess();
        return access.current_company || access.user_default_company || "";
    }

    function activeCompanyCurrency() {
        const access = companyAccess();
        const company = activeCompany();
        const currencies = access.company_currencies || {};
        return (company && currencies[company]) || frappe.defaults?.get_default?.("currency") || "";
    }

    function plainText(html) {
        const div = document.createElement("div");
        div.innerHTML = html == null ? "" : String(html);
        return div.textContent || div.innerText || "";
    }

    function cleanCurrencyText(value, currency) {
        const targetCurrency = currency || activeCompanyCurrency();
        return String(value || "")
            .replace(/[\u200e\u200f\u202a-\u202e]/g, "")
            .replace(/د\.م\./g, targetCurrency)
            .replace(/\s+/g, " ")
            .trim();
    }

    function formatCurrency(value, currency) {
        const targetCurrency = currency || activeCompanyCurrency();
        const df = { fieldtype: "Currency" };
        if (targetCurrency) df.currency = targetCurrency;
        return cleanCurrencyText(plainText(frappe.format(Number(value || 0), df)), targetCurrency);
    }

    function formatCurrencyFr(value, currency) {
        const targetCurrency = currency || activeCompanyCurrency();
        const formatted = Number(value || 0).toLocaleString("fr-FR", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
        return `${formatted}${targetCurrency ? ` ${targetCurrency}` : ""}`;
    }

    window.orderlift.getActiveCompany = activeCompany;
    window.orderlift.getActiveCompanyCurrency = activeCompanyCurrency;
    window.orderlift.cleanCurrencyText = cleanCurrencyText;
    window.orderlift.formatCurrency = formatCurrency;
    window.orderlift.formatCurrencyFr = formatCurrencyFr;
})();
