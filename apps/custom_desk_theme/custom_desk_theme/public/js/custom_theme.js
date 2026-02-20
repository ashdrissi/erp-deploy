/**
 * Orderlift — Custom Desk Theme JS v2.1
 * ============================================================
 * Robust version: always fetches settings via API on page load,
 * applies dark/light mode, injects color overrides and custom CSS.
 * ============================================================
 */

(function () {
    "use strict";

    // Wait for Frappe to be fully ready
    if (typeof frappe === "undefined") return;

    frappe.provide("custom_desk_theme");

    // Run after DOM + Frappe are both ready
    $(function () {
        // Small delay to ensure frappe.call is available
        setTimeout(function () {
            load_theme();
        }, 100);
    });

    function load_theme() {
        // Try boot data first (fastest)
        if (frappe.boot && frappe.boot.custom_desk_theme) {
            apply_all(frappe.boot.custom_desk_theme);
            return;
        }

        // Fallback: direct API call
        frappe.call({
            method: "custom_desk_theme.custom_desk_theme.doctype.theme_settings.theme_settings.get_theme_settings_api",
            async: true,
            callback: function (r) {
                if (r && r.message) {
                    apply_all(r.message);
                } else {
                    apply_all(get_defaults());
                }
            },
            error: function () {
                apply_all(get_defaults());
            }
        });
    }

    function get_defaults() {
        return {
            theme_mode: "Light",
            primary_color: "#2B44FF",
            sidebar_bg_dark: "#0F172A",
            sidebar_bg_light: "#FFFFFF",
            custom_css: ""
        };
    }

    function apply_all(settings) {
        apply_mode(settings.theme_mode || "Light");
        apply_colors(settings);
        inject_custom_css(settings.custom_css || "");
        add_toggle_button();
        move_branding_to_sidebar();
    }

    /* ---- Branding Move ---- */
    function move_branding_to_sidebar() {
        if (document.querySelector(".sidebar-branding")) return;

        var sidebar = document.querySelector(".desk-sidebar");
        if (!sidebar) return;

        var logo = document.querySelector(".navbar-brand.navbar-home") ||
            document.querySelector(".navbar .navbar-brand");

        if (logo) {
            var container = document.createElement("div");
            container.className = "sidebar-branding";

            // Clone the logo so we don't break the original just yet
            var newLogo = logo.cloneNode(true);
            newLogo.style.display = "block";

            container.appendChild(newLogo);
            sidebar.insertBefore(container, sidebar.firstChild);
        }
    }

    /* ---- Theme Mode ---- */
    function apply_mode(mode) {
        var html = document.documentElement;
        if (mode === "Dark") {
            html.setAttribute("data-theme", "dark");
        } else if (mode === "Light") {
            html.setAttribute("data-theme", "light");
        } else {
            // Auto
            var dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
            html.setAttribute("data-theme", dark ? "dark" : "light");
            try {
                window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function (e) {
                    html.setAttribute("data-theme", e.matches ? "dark" : "light");
                });
            } catch (e) { /* ignore */ }
        }
    }

    /* ---- Color Overrides ---- */
    function apply_colors(settings) {
        var root = document.documentElement;
        var isDark = root.getAttribute("data-theme") === "dark";

        // Primary / accent color
        if (settings.primary_color) {
            var c = settings.primary_color;
            root.style.setProperty("--primary", c);
            root.style.setProperty("--primary-color", c);
            root.style.setProperty("--btn-primary", c);
            root.style.setProperty("--sidebar-text-active", c);

            // Compute a slightly darker version for hover
            root.style.setProperty("--btn-primary-dark", darken(c, 15));
        }

        // Sidebar background
        if (isDark && settings.sidebar_bg_dark) {
            root.style.setProperty("--sidebar-bg", settings.sidebar_bg_dark);
            root.style.setProperty("--navbar-bg", settings.sidebar_bg_dark);
        } else if (!isDark && settings.sidebar_bg_light) {
            root.style.setProperty("--sidebar-bg", settings.sidebar_bg_light);
        }
    }

    /* ---- Custom CSS Injection ---- */
    function inject_custom_css(css) {
        // Remove previous injection
        var el = document.getElementById("cdt-user-custom-css");
        if (el) el.remove();

        if (!css || !css.trim()) return;

        var style = document.createElement("style");
        style.id = "cdt-user-custom-css";
        style.setAttribute("type", "text/css");
        style.textContent = css;
        document.head.appendChild(style);
    }

    /* ---- Toggle Button ---- */
    function add_toggle_button() {
        if (document.getElementById("cdt-theme-toggle")) return;

        var isDark = document.documentElement.getAttribute("data-theme") === "dark";

        var btn = document.createElement("button");
        btn.id = "cdt-theme-toggle";
        btn.title = "Toggle dark/light mode";
        btn.textContent = isDark ? "☀️" : "🌙";
        btn.style.cssText = "background:none;border:none;font-size:18px;cursor:pointer;padding:6px 10px;line-height:1;";

        btn.addEventListener("click", function () {
            var current = document.documentElement.getAttribute("data-theme");
            var next = current === "dark" ? "light" : "dark";
            document.documentElement.setAttribute("data-theme", next);
            btn.textContent = next === "dark" ? "☀️" : "🌙";

            // Re-fetch and re-apply colors for the new mode
            frappe.call({
                method: "custom_desk_theme.custom_desk_theme.doctype.theme_settings.theme_settings.get_theme_settings_api",
                async: true,
                callback: function (r) {
                    if (r && r.message) apply_colors(r.message);
                }
            });
        });

        // Insert into navbar
        var navbar = document.querySelector(".navbar .navbar-right") ||
            document.querySelector(".navbar .container > .navbar-collapse .navbar-nav:last-child");
        if (navbar) {
            var li = document.createElement("li");
            li.className = "nav-item";
            li.appendChild(btn);
            navbar.insertBefore(li, navbar.firstChild);
        }
    }

    /* ---- Helpers ---- */
    function darken(hex, percent) {
        // Simple hex color darkener
        try {
            hex = hex.replace("#", "");
            var r = parseInt(hex.substring(0, 2), 16);
            var g = parseInt(hex.substring(2, 4), 16);
            var b = parseInt(hex.substring(4, 6), 16);
            r = Math.max(0, Math.round(r * (1 - percent / 100)));
            g = Math.max(0, Math.round(g * (1 - percent / 100)));
            b = Math.max(0, Math.round(b * (1 - percent / 100)));
            return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
        } catch (e) {
            return hex;
        }
    }

    // Expose for debugging
    custom_desk_theme.load = load_theme;
    custom_desk_theme.apply_all = apply_all;
})();
