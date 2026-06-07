(function orderliftMainDashboardSidebarUrl() {
    if (window.__orderlift_main_dashboard_sidebar_url_20260427_installed) return;
    window.__orderlift_main_dashboard_sidebar_url_20260427_installed = true;

    var SIDEBAR_NAME = "Main Dashboard";
    var SIDEBAR_PARAM = "sidebar";
    var BARE_DESK_PATHS = { "/desk": true, "/app": true };

    function isDeskPath(pathname) {
        return pathname === "/desk" || pathname === "/app" || pathname.indexOf("/desk/") === 0 || pathname.indexOf("/app/") === 0;
    }

    function withMainDashboardSidebar(urlLike) {
        var url = new URL(urlLike || window.location.href, window.location.origin);
        var pathname = url.pathname.replace(/\/+$/, "") || "/";
        if (!isDeskPath(pathname)) return "";
        if (BARE_DESK_PATHS[pathname]) url.pathname = "/desk/home-page";
        url.searchParams.set(SIDEBAR_PARAM, SIDEBAR_NAME);
        return url.pathname + url.search + url.hash;
    }

    function normalizeCurrentUrl() {
        var target = withMainDashboardSidebar(window.location.href);
        if (!target) return;
        var current = window.location.pathname + window.location.search + window.location.hash;
        if (current !== target) window.history.replaceState(window.history.state, "", target);
    }

    function patchHistoryMethod(methodName) {
        var original = window.history[methodName];
        if (!original || original.__orderlift_sidebar_patched) return;
        window.history[methodName] = function (state, title, url) {
            if (url) {
                var target = withMainDashboardSidebar(url);
                if (target) url = target;
            }
            return original.call(this, state, title, url);
        };
        window.history[methodName].__orderlift_sidebar_patched = true;
    }

    normalizeCurrentUrl();
    patchHistoryMethod("pushState");
    patchHistoryMethod("replaceState");

    window.addEventListener("popstate", normalizeCurrentUrl);
    document.addEventListener("visibilitychange", function () {
        if (!document.hidden) normalizeCurrentUrl();
    });
    if (window.frappe && frappe.router && frappe.router.on) {
        frappe.router.on("change", function () {
            setTimeout(normalizeCurrentUrl, 0);
        });
    }
})();
