(function forcePublicSidebarLogo() {
    if (window.__orderlift_sidebar_logo_fix_20260415_installed) return;
    window.__orderlift_sidebar_logo_fix_20260415_installed = true;

    var PUBLIC_LOGO_URL = "/assets/infintrix_theme/images/erpleaf-logo.png";
    var WEBSITE_APP_LOGO_URL = "/api/method/orderlift.logo_api.website_app_logo";

    function resolveLogoUrl() {
        return WEBSITE_APP_LOGO_URL + "?v=20260415";
    }

    function applyLogo() {
        var wrapper = document.getElementById("orderlift-sidebar-brand-logo");
        if (!wrapper) return;

        var img = wrapper.querySelector("img");
        if (!img) return;

        var targetUrl = resolveLogoUrl();

        if (img.getAttribute("src") !== targetUrl) {
            img.setAttribute("src", targetUrl);
            img.src = targetUrl;
        }

        img.onerror = function () {
            img.src = PUBLIC_LOGO_URL;
        };
    }

    function queueApply() {
        setTimeout(applyLogo, 0);
    }

    if (document.body) {
        new MutationObserver(queueApply).observe(document.body, {
            childList: true,
            subtree: true,
        });
    }

    queueApply();
    window.addEventListener("popstate", queueApply);

    if (window.frappe && frappe.router && frappe.router.on) {
        frappe.router.on("change", queueApply);
    }
})();
