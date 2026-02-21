/**
 * Orderlift — Global Desk JS
 * Loaded for all logged-in Desk users via app_include_js in hooks.py
 */

frappe.provide("orderlift");

// ── Rename "ERPNext" → "Orderlift" everywhere in the UI ──
(function renameERPNext() {
    function doReplace() {
        document.querySelectorAll(
            ".header-subtitle, .sidebar-item-label, span, div, p, a, h1, h2, h3, h4, h5, h6, label"
        ).forEach(function (el) {
            if (el.childNodes.length === 1 && el.childNodes[0].nodeType === 3) {
                var txt = el.textContent.trim();
                if (txt === "ERPNext") {
                    el.textContent = "Orderlift";
                } else if (txt === "ERPNext Settings") {
                    el.textContent = "Orderlift Settings";
                }
            }
        });
    }
    if (document.body) {
        new MutationObserver(doReplace).observe(document.body, {
            childList: true,
            subtree: true,
        });
    } else {
        document.addEventListener("DOMContentLoaded", function () {
            new MutationObserver(doReplace).observe(document.body, {
                childList: true,
                subtree: true,
            });
        });
    }
})();

orderlift = {
    /**
     * Open the SIG project map page from anywhere in Desk.
     */
    open_project_map: function () {
        frappe.set_route("project-map");
    },

    /**
     * Format a number as a French-style currency string.
     * e.g. 12345.6 → "12 345,60 MAD"
     */
    format_currency_fr: function (amount, currency) {
        currency = currency || "MAD";
        return (
            new Intl.NumberFormat("fr-FR", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            }).format(amount) +
            " " +
            currency
        );
    },
};
