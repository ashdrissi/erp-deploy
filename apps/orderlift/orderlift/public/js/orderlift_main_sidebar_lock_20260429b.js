/**
 * Orderlift - force business users to stay in the Main Dashboard sidebar.
 *
 * Frappe picks a sidebar by matching the current route against every
 * Workspace Sidebar. That can switch users into SIG, HR, Finance, or other
 * section sidebars after clicking a page. Orderlift access rules are applied
 * to Main Dashboard, so business users must always render that sidebar.
 */
(function lockOrderliftMainSidebar() {
    if (window.__orderlift_main_sidebar_lock_20260429b_installed) return;
    window.__orderlift_main_sidebar_lock_20260429b_installed = true;

    var TARGET_SIDEBAR = "Main Dashboard";
    var TARGET_KEY = TARGET_SIDEBAR.toLowerCase();
    var BUSINESS_ROLES = [
        "Orderlift Admin",
        "Sales User",
        "Pricing Manager",
        "Logistics User",
        "Finance User",
        "Installation User",
        "Service User",
    ];
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
        if (frappe.session && frappe.session.user === "Administrator") return true;
        if (frappe.boot.is_restricted_shell_user) return true;
        return hasAnyRole(BUSINESS_ROLES);
    }

    function getWorkspaceSidebars() {
        return window.frappe && frappe.boot && frappe.boot.workspace_sidebar_item;
    }

    function getMainSidebarData() {
        var sidebars = getWorkspaceSidebars();
        if (!sidebars) return null;
        return sidebars[TARGET_KEY] || sidebars[TARGET_SIDEBAR] || null;
    }

    function pruneBootSidebars() {
        if (!shouldLock()) return false;
        var sidebars = getWorkspaceSidebars();
        var mainSidebar = getMainSidebarData();
        if (!sidebars || !mainSidebar) return false;

        Object.keys(sidebars).forEach(function (key) {
            if (key !== TARGET_SIDEBAR && key !== TARGET_SIDEBAR.toLowerCase()) {
                delete sidebars[key];
            }
        });
        sidebars[TARGET_KEY] = mainSidebar;
        return true;
    }

    function refreshLiveSidebarIndexes(instance) {
        if (!instance || !pruneBootSidebars()) return;
        instance.all_sidebar_items = frappe.boot.workspace_sidebar_item;
        instance.preferred_sidebars = [TARGET_SIDEBAR];
        instance.sidebar_module_map = {};
    }

    function forceMainSidebar(instance) {
        if (forcing || !instance || !pruneBootSidebars()) return false;
        refreshLiveSidebarIndexes(instance);

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
        if (frappe.ui.Sidebar.__orderliftMainSidebarLock20260429bPatched) return true;

        var proto = frappe.ui.Sidebar.prototype;
        var originalSetup = proto.setup;
        var originalGetWorkspaceSidebars = proto.get_workspace_sidebars;
        var originalSetWorkspaceSidebar = proto.set_workspace_sidebar;
        var originalSetSidebarForPage = proto.set_sidebar_for_page;
        var originalShowSidebarForModule = proto.show_sidebar_for_module;

        proto.setup = function (workspaceTitle) {
            if (shouldLock()) {
                pruneBootSidebars();
                workspaceTitle = TARGET_SIDEBAR;
            }
            var result = originalSetup ? originalSetup.call(this, workspaceTitle) : undefined;
            refreshLiveSidebarIndexes(this);
            return result;
        };

        proto.get_workspace_sidebars = function (linkTo) {
            if (shouldLock() && getMainSidebarData()) {
                return [TARGET_SIDEBAR];
            }
            return originalGetWorkspaceSidebars ? originalGetWorkspaceSidebars.apply(this, arguments) : [];
        };

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

        frappe.ui.Sidebar.__orderliftMainSidebarLock20260429bPatched = true;
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
