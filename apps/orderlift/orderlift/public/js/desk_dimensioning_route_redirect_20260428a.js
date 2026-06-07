(function orderliftDimensioningRouteRedirect() {
    if (window.__orderlift_dimensioning_route_redirect_20260428a_installed) return;
    window.__orderlift_dimensioning_route_redirect_20260428a_installed = true;

    function isOldDimensioningSetRoute(route) {
        if (!route || !route.length) return false;
        if (route[0] === "List" && route[1] === "Dimensioning Set") return true;
        return route[0] === "dimensioning-set" || route[0] === "dimensioning_set";
    }

    function redirectOldDimensioningSetRoute() {
        if (!window.frappe || !frappe.get_route || !frappe.set_route) return;
        var route = frappe.get_route() || [];
        if (!isOldDimensioningSetRoute(route)) return;
        frappe.set_route("dimensioning-set-manager");
    }

    function scheduleRedirect() {
        window.setTimeout(redirectOldDimensioningSetRoute, 0);
    }

    scheduleRedirect();
    if (window.frappe && frappe.router && frappe.router.on) {
        frappe.router.on("change", scheduleRedirect);
    }
})();
