(function orderliftHomePageScrollFix() {
    if (window.__orderlift_home_page_scroll_fix_20260520a_installed) return;
    window.__orderlift_home_page_scroll_fix_20260520a_installed = true;

    var STYLE_ID = "orderlift-home-page-scroll-fix-20260520a";
    var HOME_ROUTES = { "home-page": true, "orderlift-home": true };

    function currentRouteName() {
        if (window.frappe && frappe.get_route) {
            var route = frappe.get_route() || [];
            return String(route[0] || "");
        }
        var match = String(window.location.pathname || "").match(/\/(?:app|desk)\/([^/?#]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function isHomeRoute() {
        return !!HOME_ROUTES[currentRouteName()];
    }

    function ensureStyle() {
        if (document.getElementById(STYLE_ID)) return;
        var style = document.createElement("style");
        style.id = STYLE_ID;
        style.textContent = [
            "body.orderlift-home-scroll-unlocked #page-home-page,",
            "body.orderlift-home-scroll-unlocked #page-orderlift-home { overflow:hidden!important; height:100%!important; max-height:none!important; }",
            "body.orderlift-home-scroll-unlocked #page-home-page .page-body,",
            "body.orderlift-home-scroll-unlocked #page-home-page .layout-main,",
            "body.orderlift-home-scroll-unlocked #page-orderlift-home .page-body,",
            "body.orderlift-home-scroll-unlocked #page-orderlift-home .layout-main { min-height:0!important; height:100%!important; max-height:none!important; overflow:hidden!important; }",
            "body.orderlift-home-scroll-unlocked #page-home-page .layout-main-section-wrapper,",
            "body.orderlift-home-scroll-unlocked #page-orderlift-home .layout-main-section-wrapper,",
            "body.orderlift-home-scroll-unlocked #page-home-page .layout-main-section,",
            "body.orderlift-home-scroll-unlocked #page-orderlift-home .layout-main-section { min-height:0!important; height:100%!important; max-height:none!important; overflow-y:auto!important; overflow-x:hidden!important; -webkit-overflow-scrolling:touch; }",
            "body.orderlift-home-scroll-unlocked #page-home-page .hp-wrap,",
            "body.orderlift-home-scroll-unlocked #page-orderlift-home .hdb-wrap { min-height:calc(100vh - 72px); padding-bottom:120px; }",
        ].join("\n");
        document.head.appendChild(style);
    }

    function resetInlineScrollLocks(root) {
        if (!root) return;
        var selectors = [".page-body", ".layout-main", ".layout-main-section-wrapper", ".layout-main-section"];
        for (var i = 0; i < selectors.length; i++) {
            var nodes = root.querySelectorAll(selectors[i]);
            for (var j = 0; j < nodes.length; j++) {
                nodes[j].style.removeProperty("overflow");
                nodes[j].style.removeProperty("overflow-y");
                nodes[j].style.removeProperty("height");
                nodes[j].style.removeProperty("max-height");
            }
        }
    }

    function applyScrollUnlock() {
        ensureStyle();
        if (!document.body) return;
        if (!isHomeRoute()) {
            document.body.classList.remove("orderlift-home-scroll-unlocked");
            return;
        }
        document.body.classList.add("orderlift-home-scroll-unlocked");
        resetInlineScrollLocks(document.getElementById("page-home-page"));
        resetInlineScrollLocks(document.getElementById("page-orderlift-home"));
    }

    function queueApply() {
        setTimeout(applyScrollUnlock, 0);
        setTimeout(applyScrollUnlock, 150);
        setTimeout(applyScrollUnlock, 500);
    }

    ensureStyle();
    queueApply();
    window.addEventListener("popstate", queueApply);
    window.addEventListener("pageshow", queueApply);

    if (document.body) {
        new MutationObserver(queueApply).observe(document.body, { childList: true, subtree: true });
    } else {
        document.addEventListener("DOMContentLoaded", queueApply);
    }

    if (window.frappe && frappe.router && frappe.router.on) {
        frappe.router.on("change", queueApply);
    }
})();
