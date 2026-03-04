/**
 * Custom Desk Theme
 * Minimal mode: only inject custom CSS saved in Theme Settings.
 */

(function () {
    "use strict";

    if (typeof frappe === "undefined") return;

    frappe.provide("custom_desk_theme");

    function inject_custom_css(css) {
        var existing = document.getElementById("cdt-user-custom-css");
        if (existing) existing.remove();

        if (!css || !css.trim()) return;

        var style = document.createElement("style");
        style.id = "cdt-user-custom-css";
        style.type = "text/css";
        style.textContent = css;
        document.head.appendChild(style);
    }

    function load_theme() {
        if (frappe.boot && frappe.boot.custom_desk_theme) {
            inject_custom_css(frappe.boot.custom_desk_theme.custom_css || "");
            return;
        }

        frappe.call({
            method: "custom_desk_theme.custom_desk_theme.doctype.theme_settings.theme_settings.get_theme_settings_api",
            async: true,
            callback: function (r) {
                var css = r && r.message ? r.message.custom_css : "";
                inject_custom_css(css || "");
            },
            error: function () {
                inject_custom_css("");
            },
        });
    }

    $(function () {
        setTimeout(load_theme, 50);
    });

    custom_desk_theme.load = load_theme;
})();
