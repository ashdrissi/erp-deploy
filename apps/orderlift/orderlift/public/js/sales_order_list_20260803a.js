(function () {
    function shortStatus(value) {
        const text = String(value || "").trim();
        if (!text) return text;
        const separator = text.lastIndexOf(" - ");
        return separator >= 0 ? text.slice(separator + 3) : text;
    }

    function textHtml(value) {
        return `<span>${frappe.utils.escape_html(String(value || ""))}</span>`;
    }

    const settings = frappe.listview_settings["Sales Order"] || {};
    settings.add_fields = Array.from(new Set([
        ...(settings.add_fields || []),
        "customer_name",
        "custom_orderlift_order_status",
        "owner",
    ]));
    settings.formatters = settings.formatters || {};
    settings.formatters.custom_orderlift_order_status = (value) => textHtml(shortStatus(value));
    settings.formatters.owner = (value) => textHtml(value);
    frappe.listview_settings["Sales Order"] = settings;
})();
