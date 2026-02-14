Y/**
 * Orderlift — Custom Desk Theme JS v2
 * ============================================================
 * - Applies dark/light/auto mode based on Theme Settings
 * - Injects custom CSS from Theme Settings
 * - Applies dynamic color overrides (primary, sidebar)
 * - Adds a dark/light toggle to the navbar
 * - Replaces logo + branded welcome
 * ============================================================
 */

frappe.provide("custom_desk_theme");

$(document).ready(function () {
    _load_and_apply_theme();
});

/**
 * Load theme settings from boot data or API, then apply.
 */
function _load_and_apply_theme() {
    // boot_session hook populates frappe.boot with theme settings
    var settings = frappe.boot.custom_desk_theme || null;

    if (settings) {
        _apply_theme(settings);
    } else {
        // Fallback: fetch via API
        frappe.call({
            method: "custom_desk_theme.custom_desk_theme.doctype.theme_settings.theme_settings.get_theme_settings_api",
            async: true,
            callback: function (r) {
                if (r && r.message) {
                    _apply_theme(r.message);
                } else {
                    // Use defaults
                    _apply_theme({
                        theme_mode: "Auto",
                        primary_color: "#00D4B4",
                        sidebar_bg_dark: "#0D1528",
                        sidebar_bg_light: "#FFFFFF",
                        custom_css: ""
                    });
                }
            }
        });
    }
}

/**
 * Apply theme based on settings.
 */
function _apply_theme(settings) {
    // 1. Determine and apply theme mode
    _apply_mode(settings.theme_mode);

    // 2. Apply color overrides
    _apply_colors(settings);

    // 3. Inject custom CSS
    _inject_custom_css(settings.custom_css);

    // 4. Add toggle button to navbar
    _add_toggle_button(settings.theme_mode);

    // 5. Replace logo
    _replace_navbar_logo();

    // 6. Branded workspace welcome
    _add_branded_home();
}

/**
 * Set data-theme attribute based on mode.
 */
function _apply_mode(mode) {
    if (mode === "Dark") {
        document.documentElement.setAttribute("data-theme", "dark");
    } else if (mode === "Light") {
        document.documentElement.setAttribute("data-theme", "light");
    } else {
        // Auto — respect system preference
        var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
        document.documentElement.setAttribute("data-theme", prefersDark ? "dark" : "light");

        // Listen for changes
        window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function (e) {
            document.documentElement.setAttribute("data-theme", e.matches ? "dark" : "light");
        });
    }
}

/**
 * Override CSS variables with colors from Theme Settings.
 */
function _apply_colors(settings) {
    var root = document.documentElement;
    var isDark = root.getAttribute("data-theme") === "dark";

    if (settings.primary_color) {
        root.style.setProperty("--primary", settings.primary_color);
        root.style.setProperty("--primary-color", settings.primary_color);
        root.style.setProperty("--btn-primary", settings.primary_color);
    }

    if (isDark && settings.sidebar_bg_dark) {
        root.style.setProperty("--sidebar-bg", settings.sidebar_bg_dark);
    } else if (!isDark && settings.sidebar_bg_light) {
        root.style.setProperty("--sidebar-bg", settings.sidebar_bg_light);
    }
}

/**
 * Inject user-defined custom CSS.
 */
function _inject_custom_css(css) {
    if (!css) return;

    // Remove old injection if exists
    var existing = document.getElementById("custom-desk-theme-user-css");
    if (existing) existing.remove();

    var style = document.createElement("style");
    style.id = "custom-desk-theme-user-css";
    style.textContent = css;
    document.head.appendChild(style);
}

/**
 * Add a dark/light toggle button in the navbar.
 */
function _add_toggle_button(currentMode) {
    // Don't add if already exists
    if (document.getElementById("theme-toggle-btn")) return;

    var isDark = document.documentElement.getAttribute("data-theme") === "dark";
    var icon = isDark ? "☀️" : "🌙";

    var $btn = $(
        '<li class="nav-item">' +
        '<a class="nav-link" id="theme-toggle-btn" href="#" title="Toggle dark/light mode" ' +
        'style="font-size:16px;padding:8px 10px;cursor:pointer;text-decoration:none;">' +
        icon +
        '</a>' +
        '</li>'
    );

    $btn.on("click", function (e) {
        e.preventDefault();
        var current = document.documentElement.getAttribute("data-theme");
        var next = current === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", next);

        // Update icon
        $("#theme-toggle-btn").text(next === "dark" ? "☀️" : "🌙");

        // Re-apply sidebar colors
        frappe.call({
            method: "custom_desk_theme.custom_desk_theme.doctype.theme_settings.theme_settings.get_theme_settings_api",
            async: true,
            callback: function (r) {
                if (r && r.message) {
                    _apply_colors(r.message);
                }
            }
        });
    });

    // Append to navbar
    var $navRight = $(".navbar-right, .navbar .navbar-nav:last-child");
    if ($navRight.length) {
        $navRight.prepend($btn);
    }
}

/**
 * Replace navbar logo with Orderlift logo.
 */
function _replace_navbar_logo() {
    var $logo = $(".navbar-brand .app-logo");
    if ($logo.length) {
        $logo.attr("src", "/assets/orderlift/images/orderlift_logo.png");
        $logo.css({ "max-height": "28px" });
    }

    var $brand = $(".navbar-brand");
    if ($brand.length && !$logo.length) {
        $brand.css("background-image", "none");
        $brand.html(
            '<img src="/assets/orderlift/images/orderlift_logo.png" ' +
            'class="app-logo" style="max-height:28px;" alt="Orderlift">'
        );
    }
}

/**
 * Add branded welcome banner on workspace / home.
 */
function _add_branded_home() {
    frappe.after_ajax(function () {
        var $workspace = $(".workspace-container");
        if (!$workspace.length || $("#orderlift-welcome").length) return;

        var user_name = frappe.session.user_fullname || "User";
        var first_name = user_name.split(" ")[0];

        var hour = new Date().getHours();
        var greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

        var $welcome = $(
            '<div id="orderlift-welcome" style="' +
            "padding: 20px 24px;" +
            "margin-bottom: 20px;" +
            "background: linear-gradient(135deg, #0B1120 0%, #162036 60%, var(--primary) 100%);" +
            "border-radius: 12px;" +
            "color: #FFFFFF;" +
            "box-shadow: 0 4px 12px rgba(0, 20, 40, 0.3);" +
            '">' +
            '<h3 style="margin:0 0 4px 0;font-size:18px;font-weight:600;color:#FFFFFF;">' +
            greeting + ", " + first_name + "!" +
            "</h3>" +
            '<p style="margin:0;font-size:13px;color:rgba(255,255,255,0.7);">' +
            "Welcome to Order Lift ERP — your elevator parts management hub." +
            "</p>" +
            "</div>"
        );

        $workspace.prepend($welcome);
    });
}
