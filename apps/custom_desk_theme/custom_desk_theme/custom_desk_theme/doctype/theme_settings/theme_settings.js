// Theme Settings — Form Script
// After saving, apply the new theme settings instantly

frappe.ui.form.on("Theme Settings", {
    after_save: function (frm) {
        // Re-apply theme immediately without full page reload
        var settings = {
            theme_mode: frm.doc.theme_mode || "Light",
            primary_color: frm.doc.primary_color || "#00D4B4",
            sidebar_bg_dark: frm.doc.sidebar_bg_dark || "#0D1528",
            sidebar_bg_light: frm.doc.sidebar_bg_light || "#FFFFFF",
            custom_css: frm.doc.custom_css || ""
        };

        if (typeof custom_desk_theme !== "undefined" && custom_desk_theme.apply_all) {
            custom_desk_theme.apply_all(settings);
            frappe.show_alert({
                message: __("Theme updated! Other pages will reflect changes on reload."),
                indicator: "green"
            }, 5);
        } else {
            frappe.show_alert({
                message: __("Theme saved. Please refresh the page to see changes."),
                indicator: "blue"
            }, 5);
        }
    }
});
