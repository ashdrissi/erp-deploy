/**
 * Orderlift — Custom Desk Theme JS
 * ============================================================
 * Loaded for all logged-in Desk users via app_include_js.
 *
 * Responsibilities:
 *   1. Replace the Frappe navbar logo with Orderlift's logo
 *   2. Add a branded welcome message on the Home workspace
 *   3. Smooth page transitions
 *   4. Ensure compatibility with Frappe's dark mode toggle
 * ============================================================
 */

frappe.provide("custom_desk_theme");

$(document).ready(function () {
    // ---- 1. Replace Navbar Logo ----
    _replace_navbar_logo();

    // ---- 2. Branded Home Message ----
    _add_branded_home();

    // ---- 3. Page transition listener ----
    $(document).on("page-change", function () {
        _smooth_page_in();
    });
});

/**
 * Replace the default Frappe logo in the navbar with Orderlift's logo.
 * Falls back gracefully if the logo element is not found.
 */
function _replace_navbar_logo() {
    var $logo = $(".navbar-brand .app-logo");
    if ($logo.length) {
        $logo.attr("src", "/assets/orderlift/images/orderlift_logo.png");
        $logo.css({
            "max-height": "28px",
            "filter": "brightness(0) invert(1)",
            "opacity": "0.95",
        });
    }

    // Also handle cases where the logo is an <a> with background-image
    var $brand = $(".navbar-brand");
    if ($brand.length && !$logo.length) {
        $brand.css("background-image", "none");
        $brand.html(
            '<img src="/assets/orderlift/images/orderlift_logo.png" ' +
            'class="app-logo" style="max-height:28px;filter:brightness(0) invert(1);opacity:0.95;" ' +
            'alt="Orderlift">'
        );
    }
}

/**
 * Add a branded welcome header to the Home/Workspace page.
 */
function _add_branded_home() {
    // Wait for workspace to load
    frappe.after_ajax(function () {
        var $workspace = $(".workspace-container");
        if (!$workspace.length) return;

        // Only add once
        if ($("#orderlift-welcome").length) return;

        var user_name = frappe.session.user_fullname || "User";
        var first_name = user_name.split(" ")[0];

        // Determine greeting based on time
        var hour = new Date().getHours();
        var greeting;
        if (hour < 12) {
            greeting = "Good morning";
        } else if (hour < 18) {
            greeting = "Good afternoon";
        } else {
            greeting = "Good evening";
        }

        var $welcome = $(
            '<div id="orderlift-welcome" style="' +
            "padding: 20px 24px;" +
            "margin-bottom: 20px;" +
            "background: linear-gradient(135deg, #1A1D26 0%, #2D3148 60%, #E8772E 100%);" +
            "border-radius: 12px;" +
            "color: #FFFFFF;" +
            "box-shadow: 0 4px 12px rgba(30, 33, 48, 0.2);" +
            '">' +
            '<h3 style="margin:0 0 4px 0;font-size:18px;font-weight:600;color:#FFFFFF;">' +
            greeting + ", " + first_name + "!" +
            "</h3>" +
            '<p style="margin:0;font-size:13px;color:rgba(255,255,255,0.7);">' +
            "Welcome to Orderlift ERP — your elevator parts management hub." +
            "</p>" +
            "</div>"
        );

        $workspace.prepend($welcome);
    });
}

/**
 * Smooth fade-in for page transitions.
 */
function _smooth_page_in() {
    var $main = $(".layout-main");
    if (!$main.length) return;

    $main.css("opacity", "0");
    setTimeout(function () {
        $main.css({
            "opacity": "1",
            "transition": "opacity 0.15s ease",
        });
    }, 30);
}
