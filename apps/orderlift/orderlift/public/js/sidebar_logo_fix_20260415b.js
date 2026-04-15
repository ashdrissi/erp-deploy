(function forcePublicSidebarLogo() {
    if (window.__orderlift_sidebar_logo_fix_20260415b_installed) return;
    window.__orderlift_sidebar_logo_fix_20260415b_installed = true;

    var PUBLIC_LOGO_URL = "/assets/infintrix_theme/images/erpleaf-logo.png";
    var WEBSITE_APP_LOGO_URL = "/api/method/orderlift.logo_api.website_app_logo?v=20260415b";
    var WRAPPER_ID = "orderlift-sidebar-brand-logo";

    function getOrCreateWrapper(sidebar) {
        var wrapper = document.getElementById(WRAPPER_ID);
        if (wrapper) return wrapper;

        wrapper = document.createElement("div");
        wrapper.id = WRAPPER_ID;
        wrapper.style.cssText =
            "padding: 16px 16px 8px 16px; text-align: center; border-bottom: 1px solid var(--border-color, #e2e6e9);";

        var link = document.createElement("a");
        link.href = "/app";
        link.style.cssText = "text-decoration: none; display: inline-block;";

        var img = document.createElement("img");
        img.alt = "Orderlift";
        img.style.cssText = "max-width: 140px; max-height: 50px; object-fit: contain; cursor: pointer;";

        link.appendChild(img);
        wrapper.appendChild(link);
        sidebar.insertBefore(wrapper, sidebar.firstChild || null);
        return wrapper;
    }

    function applyLogo() {
        var sidebar = document.querySelector(".body-sidebar");
        if (!sidebar) return;

        var wrapper = getOrCreateWrapper(sidebar);

        var img = wrapper.querySelector("img");
        if (!img) return;

        if (img.getAttribute("src") !== WEBSITE_APP_LOGO_URL) {
            img.setAttribute("src", WEBSITE_APP_LOGO_URL);
            img.src = WEBSITE_APP_LOGO_URL;
        }

        img.onerror = function () {
            img.src = PUBLIC_LOGO_URL;
        };

        if (sidebar.firstChild !== wrapper) {
            sidebar.insertBefore(wrapper, sidebar.firstChild || null);
        }
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
