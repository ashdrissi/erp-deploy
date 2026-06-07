/**
 * Orderlift - keep business users in the Main Dashboard sidebar.
 *
 * Frappe can switch to a route's matching Workspace Sidebar after navigation
 * (for example SIG or Gestion de Projets). Orderlift access control is applied
 * to Main Dashboard, so business users should never receive or switch to the
 * section-specific sidebars.
 */
(function lockOrderliftMainSidebar() {
    if (window.__orderlift_main_sidebar_lock_20260429a_installed) return;
    window.__orderlift_main_sidebar_lock_20260429a_installed = true;

    var TARGET_SIDEBAR = "Main Dashboard";
    var BUSINESS_ROLES = [
        "Orderlift Admin",
        "Sales User",
        "Pricing Manager",
        "Logistics User",
        "Finance User",
        "Installation User",
        "Service User",
    ];
    var BYPASS_ROLES = ["Administrator", "System Manager", "Developer"];
    var forcing = false;

    function getRoles() {
        if (window.orderliftGetRoles) return window.orderliftGetRoles();
        if (window.frappe && Array.isArray(frappe.user_roles)) return frappe.user_roles;
        if (window.frappe && frappe.boot && frappe.boot.user && Array.isArray(frappe.boot.user.roles)) {
            return frappe.boot.user.roles;
        }
        if (window.frappe && frappe.boot && Array.isArray(frappe.boot.user_roles)) return frappe.boot.user_roles;
        return [];
    }

    function hasAnyRole(candidates) {
        var roles = getRoles();
        for (var i = 0; i < candidates.length; i++) {
            if (roles.indexOf(candidates[i]) !== -1) return true;
        }
        return false;
    }

    function shouldLock() {
        if (!window.frappe || !frappe.boot) return false;
        if (frappe.boot.is_restricted_shell_user) return true;
        return hasAnyRole(BUSINESS_ROLES) && !hasAnyRole(BYPASS_ROLES);
    }

    function getWorkspaceSidebars() {
        return window.frappe && frappe.boot && frappe.boot.workspace_sidebar_item;
    }

    function getMainSidebarData() {
        var sidebars = getWorkspaceSidebars();
        if (!sidebars) return null;
        return sidebars[TARGET_SIDEBAR] || sidebars[TARGET_SIDEBAR.toLowerCase()] || null;
    }

    function pruneBootSidebars() {
        if (!shouldLock()) return false;
        var mainSidebar = getMainSidebarData();
        if (!mainSidebar) return false;
        frappe.boot.workspace_sidebar_item = {};
        frappe.boot.workspace_sidebar_item[TARGET_SIDEBAR] = mainSidebar;
        return true;
    }

    function forceMainSidebar(instance) {
        if (forcing || !pruneBootSidebars() || !instance) return false;
        var currentTitle = String(instance.workspace_title || instance.sidebar_title || "").trim();
        if (currentTitle !== TARGET_SIDEBAR && typeof instance.setup === "function") {
            forcing = true;
            try {
                instance.setup(TARGET_SIDEBAR);
            } finally {
                forcing = false;
            }
            return true;
        }
        if (typeof instance.set_active_workspace_item === "function") {
            instance.set_active_workspace_item();
        }
        return true;
    }

    function patchSidebarClass() {
        if (!window.frappe || !frappe.ui || !frappe.ui.Sidebar) return false;
        if (frappe.ui.Sidebar.__orderliftMainSidebarLock20260429aPatched) return true;

        var proto = frappe.ui.Sidebar.prototype;
        var originalSetWorkspaceSidebar = proto.set_workspace_sidebar;
        var originalSetSidebarForPage = proto.set_sidebar_for_page;
        var originalShowSidebarForModule = proto.show_sidebar_for_module;

        proto.set_workspace_sidebar = function () {
            if (forceMainSidebar(this)) return;
            return originalSetWorkspaceSidebar ? originalSetWorkspaceSidebar.apply(this, arguments) : undefined;
        };

        proto.set_sidebar_for_page = function () {
            if (forceMainSidebar(this)) return;
            return originalSetSidebarForPage ? originalSetSidebarForPage.apply(this, arguments) : undefined;
        };

        proto.show_sidebar_for_module = function () {
            if (forceMainSidebar(this)) return;
            return originalShowSidebarForModule ? originalShowSidebarForModule.apply(this, arguments) : undefined;
        };

        frappe.ui.Sidebar.__orderliftMainSidebarLock20260429aPatched = true;
        return true;
    }

    function applyLiveSidebar() {
        pruneBootSidebars();
        if (window.frappe && frappe.app && frappe.app.sidebar) {
            forceMainSidebar(frappe.app.sidebar);
        }
    }

    function bootstrap(attempts) {
        pruneBootSidebars();
        if (patchSidebarClass()) {
            applyLiveSidebar();
            return;
        }
        if (attempts <= 0) return;
        setTimeout(function () {
            bootstrap(attempts - 1);
        }, 100);
    }

    bootstrap(100);

    window.addEventListener("popstate", function () {
        setTimeout(applyLiveSidebar, 0);
        setTimeout(applyLiveSidebar, 150);
    });

    if (window.frappe && frappe.router && frappe.router.on) {
        frappe.router.on("change", function () {
            setTimeout(applyLiveSidebar, 0);
            setTimeout(applyLiveSidebar, 150);
            setTimeout(applyLiveSidebar, 500);
        });
    }
})();
