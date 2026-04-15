(function forceMainDashboardForPlanningRoutes() {
    if (window.__orderlift_main_dashboard_shell_fix_20260414_installed) return;
    window.__orderlift_main_dashboard_shell_fix_20260414_installed = true;

    var TARGET_SIDEBAR = "Main Dashboard";

    function isPlanningRoute() {
        if (!window.frappe || !frappe.get_route) return false;
        var route = frappe.get_route() || [];
        return route[0] === "planning" || route[0] === "forecast-plans";
    }

    function hasTargetSidebar() {
        return !!(
            window.frappe &&
            frappe.boot &&
            frappe.boot.workspace_sidebar_item &&
            frappe.boot.workspace_sidebar_item[TARGET_SIDEBAR.toLowerCase()]
        );
    }

    function forceSidebar(instance) {
        if (!instance || !isPlanningRoute() || !hasTargetSidebar()) return false;
        if (instance.sidebar_title !== TARGET_SIDEBAR) {
            instance.setup(TARGET_SIDEBAR);
        } else if (instance.set_active_workspace_item) {
            instance.set_active_workspace_item();
        }
        return true;
    }

    function patchSidebarClass() {
        if (!window.frappe || !frappe.ui || !frappe.ui.Sidebar) return false;
        if (frappe.ui.Sidebar.__orderliftMainDashboardShellFix20260414Patched) return true;

        var proto = frappe.ui.Sidebar.prototype;
        var originalSetWorkspaceSidebar = proto.set_workspace_sidebar;
        var originalSetSidebarForPage = proto.set_sidebar_for_page;
        var originalShowSidebarForModule = proto.show_sidebar_for_module;

        proto.set_workspace_sidebar = function () {
            if (forceSidebar(this)) return;
            if (originalSetWorkspaceSidebar) {
                return originalSetWorkspaceSidebar.apply(this, arguments);
            }
        };

        proto.set_sidebar_for_page = function () {
            if (forceSidebar(this)) return;
            if (originalSetSidebarForPage) {
                return originalSetSidebarForPage.apply(this, arguments);
            }
        };

        proto.show_sidebar_for_module = function () {
            if (forceSidebar(this)) return;
            if (originalShowSidebarForModule) {
                return originalShowSidebarForModule.apply(this, arguments);
            }
        };

        frappe.ui.Sidebar.__orderliftMainDashboardShellFix20260414Patched = true;
        return true;
    }

    function applyLiveSidebar() {
        if (!window.frappe || !frappe.app || !frappe.app.sidebar) return;
        forceSidebar(frappe.app.sidebar);
    }

    function bootstrap(attempts) {
        if (patchSidebarClass()) {
            applyLiveSidebar();
            return;
        }

        if (attempts <= 0) return;
        setTimeout(function () {
            bootstrap(attempts - 1);
        }, 100);
    }

    bootstrap(80);

    window.addEventListener("popstate", function () {
        setTimeout(applyLiveSidebar, 0);
    });

    if (window.frappe && frappe.router && frappe.router.on) {
        frappe.router.on("change", function () {
            setTimeout(applyLiveSidebar, 0);
        });
    }
})();
