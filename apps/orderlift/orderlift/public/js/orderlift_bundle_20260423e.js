/**
 * Orderlift — Global Desk JS
 * Loaded for all logged-in Desk users via app_include_js in hooks.py
 */

frappe.provide("orderlift");

try {
    if (window.localStorage) {
        window.localStorage.removeItem("_page:crm-dashboard");
    }
} catch (e) {
    // ignore localStorage access issues
}

var ORDERLIFT_CLIENT_SHELL_ROLE = "Orderlift Admin";
var ORDERLIFT_INTERNAL_BYPASS_ROLES = ["System Manager", "Developer"];

// ── Instant boot-flag check (no polling, no flash) ──
// frappe.boot is available synchronously when app_include_js runs.
var __orderlift_is_restricted = (function () {
    try {
        return !!(frappe.boot && frappe.boot.is_restricted_shell_user);
    } catch (e) {
        return false;
    }
})();

// ── Jump off bare /desk or /app immediately ──
// Keeps users from seeing the intermediate desk shell before redirect.
(function redirectBareDeskImmediately() {
    var pathname = (window.location.pathname || "").replace(/\/+$/, "");
    if (pathname !== "/desk" && pathname !== "/app") return;

    var target = "/desk/home-page";
    var current = window.location.pathname + window.location.search + window.location.hash;
    if (current !== target) {
        window.location.replace(target);
    }
})();

// ── Immediate screen blanker for restricted users ──
// Hides all page content BEFORE Frappe renders anything visible.
// Removed once we land on the allowed home page.
(function instantBlanker() {
    if (!__orderlift_is_restricted) return;

    // Keep remover for compatibility, but do not inject a full-page overlay.
    // Server-side and client-side route guards already redirect blocked pages,
    // and the overlay could strand valid refreshes behind an eternal "Loading…".
    window.__orderlift_remove_blanker = function () {
        var el = document.getElementById("orderlift-shell-blanker");
        if (el) el.remove();
    };
})();

// ── Disable fragile sound playback for restricted-shell users ──
(function stabilizeRestrictedUserSounds() {
    if (window.__orderlift_sound_stabilizer_installed) return;
    window.__orderlift_sound_stabilizer_installed = true;

    function patchSounds() {
        if (!window.frappe || !frappe.utils || !frappe.utils.play_sound) return false;
        if (frappe.utils.__orderlift_sound_patch_applied) return true;

        var originalPlaySound = frappe.utils.play_sound;
        frappe.utils.play_sound = function (name) {
            if (orderliftIsClientShellUser() && name === "numpad-touch") return;
            return originalPlaySound.apply(this, arguments);
        };

        frappe.utils.__orderlift_sound_patch_applied = true;
        return true;
    }

    orderliftWhenRolesReady(function () {
        var attempts = 50;
        (function ensurePatch() {
            if (patchSounds() || attempts <= 0) return;
            attempts -= 1;
            setTimeout(ensurePatch, 100);
        })();
    });
})();

function orderliftGetRoles() {
    if (Array.isArray(frappe.user_roles) && frappe.user_roles.length) return frappe.user_roles;
    if (frappe.boot && Array.isArray(frappe.boot.user && frappe.boot.user.roles) && frappe.boot.user.roles.length) {
        return frappe.boot.user.roles;
    }
    if (frappe.boot && Array.isArray(frappe.boot.user_roles) && frappe.boot.user_roles.length) return frappe.boot.user_roles;
    return [];
}

function orderliftHasRole(role) {
    return orderliftGetRoles().indexOf(role) !== -1;
}

function orderliftHasAnyRole(roles) {
    for (var i = 0; i < roles.length; i++) {
        if (orderliftHasRole(roles[i])) return true;
    }
    return false;
}

function orderliftIsClientShellUser() {
    // Fast path: boot flag is instant, no polling needed
    if (__orderlift_is_restricted) return true;
    // Fallback: role-based check (for edge cases where boot flag wasn't set)
    return orderliftHasRole(ORDERLIFT_CLIENT_SHELL_ROLE) && !orderliftHasAnyRole(ORDERLIFT_INTERNAL_BYPASS_ROLES);
}

function orderliftWhenRolesReady(callback, attempts) {
    // If boot flag says restricted, fire immediately — no waiting
    if (__orderlift_is_restricted) {
        callback();
        return;
    }
    var remaining = typeof attempts === "number" ? attempts : 80;
    if (orderliftGetRoles().length) {
        callback();
        return;
    }
    if (remaining <= 0) {
        callback();
        return;
    }
    setTimeout(function () {
        orderliftWhenRolesReady(callback, remaining - 1);
    }, 100);
}

// ── Guard form switching when a grid missed pagination setup ──
(function hardenFormSwitchDoc() {
    if (window.__orderlift_form_switch_doc_guard_installed) return;
    window.__orderlift_form_switch_doc_guard_installed = true;

    function patch() {
        if (!frappe.ui || !frappe.ui.form || !frappe.ui.form.Form) return false;
        if (frappe.ui.form.Form.__orderliftSwitchDocGuardPatched) return true;

        var proto = frappe.ui.form.Form.prototype;
        proto.switch_doc = function (docname) {
            (this.grids || []).forEach(function (grid_obj) {
                if (!grid_obj || !grid_obj.grid) return;

                grid_obj.grid.visible_columns = null;
                if (
                    grid_obj.grid.grid_pagination &&
                    typeof grid_obj.grid.grid_pagination.go_to_page === "function"
                ) {
                    grid_obj.grid.grid_pagination.go_to_page(1, true);
                }
            });

            frappe.ui.form.close_grid_form();
            this.viewers && this.viewers.parent.empty();
            this.docname = docname;
            this.setup_docinfo_change_listener();
        };

        frappe.ui.form.Form.__orderliftSwitchDocGuardPatched = true;
        return true;
    }

    var attempts = 80;
    (function ensurePatch() {
        if (patch() || attempts <= 0) return;
        attempts -= 1;
        setTimeout(ensurePatch, 100);
    })();
})();

// ── Lock business admin users into Main Dashboard shell ──
(function lockBusinessAdminShell() {
    if (window.__orderlift_business_admin_shell_lock_installed) return;
    window.__orderlift_business_admin_shell_lock_installed = true;

    function shouldLock() {
        return orderliftIsClientShellUser();
    }

    var TARGET_PATH = "/desk/home-page";
    var TARGET_URL = "/desk/home-page";
    var BLOCKED_PATH_SLUGS = {
        desk: true,
        app: false,
        workspace: true,
        workspaces: true,
        accounting: true,
        organization: true,
        payables: true,
        pricing: true,
        "pricing-&-quotations": true,
        receivables: true,
        tools: true,
        selling: true,
        stock: true,
        "frappe-hr": true,
        framework: true,
        website: true,
        invoicing: true,
        payments: true,
        "financial-reports": true,
        "accounts-setup": true,
        taxes: true,
        banking: true,
        budget: true,
        "share-management": true,
        subscription: true,
        account: true,
        "journal-entry": true,
        "payment-ledger-entry": true,
        "general-ledger": true,
        "trial-balance": true,
        "balance-sheet": true,
        "profit-and-loss-statement": true,
        "bank-account": true,
        "cost-center": true,
        "mode-of-payment": true,
        "fiscal-year": true,
        "payment-reconciliation": true,
    };
    var BLOCKED_ROUTE_SLUGS = {
        Workspaces: true,
        workspace: true,
        workspaces: true,
        accounting: true,
        organization: true,
        payables: true,
        pricing: true,
        receivables: true,
        tools: true,
        selling: true,
        stock: true,
        website: true,
        invoicing: true,
        payments: true,
        "financial-reports": true,
        "accounts-setup": true,
        taxes: true,
        banking: true,
        budget: true,
        "share-management": true,
        subscription: true,
    };

    function redirectHome() {
        if (window.location.pathname === TARGET_PATH) {
            // We're on the allowed page — remove blanker
            if (window.__orderlift_remove_blanker) window.__orderlift_remove_blanker();
            return;
        }
        window.location.replace(TARGET_URL);
    }

    function getPathSlug() {
        var pathname = (window.location.pathname || "").replace(/\/+$/, "");
        if (pathname === "/desk") return "desk";
        if (pathname.startsWith("/desk/")) {
            return pathname.replace(/^\/desk\//, "").split("/")[0].toLowerCase();
        }
        if (pathname.startsWith("/app/")) {
            return pathname.replace(/^\/app\//, "").split("/")[0].toLowerCase();
        }
        return "";
    }

    function guardPath() {
        var slug = getPathSlug();
        if (BLOCKED_PATH_SLUGS[slug]) {
            redirectHome();
        }
    }

    function guardRoute() {
        if (!frappe.get_route) return;
        var route = frappe.get_route() || [];
        var type = route[0];
        var page = route[1];
        if (BLOCKED_ROUTE_SLUGS[type]) {
            redirectHome();
            return;
        }
        if (page && BLOCKED_ROUTE_SLUGS[String(page).toLowerCase()]) {
            redirectHome();
        }
    }


    orderliftWhenRolesReady(function () {
        if (!shouldLock()) return;
        guardPath();
        setTimeout(guardRoute, 0);
        window.addEventListener("popstate", function () {
            setTimeout(function () {
                guardPath();
                guardRoute();
            }, 0);
        });
        if (frappe.router && frappe.router.on) {
            frappe.router.on("change", function () {
                setTimeout(function () {
                    guardPath();
                    guardRoute();
                }, 0);
            });
        }
    });
})();

// ── Simplify toolbar chrome for business admin users ──
(function simplifyBusinessAdminMenus() {
    if (window.__orderlift_business_admin_menu_cleanup_installed) return;
    window.__orderlift_business_admin_menu_cleanup_installed = true;

    function shouldSimplify() {
        return orderliftIsClientShellUser();
    }

    var HIDDEN_MENU_LABELS = {
        Desktop: true,
        Workspaces: true,
        Website: true,
        Reload: true,
        "Toggle Full Width": true,
        "Toggle Theme": true,
        Help: true,
        "Edit Profile": true,
        About: true,
        "Frappe Support": true,
        "Reset Desktop Layout": true,
        "Clear Demo Data": true,
    };
    var BLOCKED_WORKSPACE_SLUGS = {
        accounting: true,
        organization: true,
        selling: true,
        stock: true,
        invoicing: true,
        payments: true,
        "financial-reports": true,
        "accounts-setup": true,
        taxes: true,
        banking: true,
        budget: true,
        "share-management": true,
        subscription: true,
    };

    function normalizeLabel(text) {
        return (text || "").replace(/\s+/g, " ").trim();
    }

    function hideWorkspaceDropdown() {
        var dropdown = document.querySelector(".infintrix-workspace-dropdown-container");
        if (dropdown) dropdown.style.display = "none";
    }

    function hideUserMenuItems() {
        var selectors = [".dropdown-item", ".menu-item", ".menu-item-label", "a", "button"];
        for (var s = 0; s < selectors.length; s++) {
            var elements = document.querySelectorAll(selectors[s]);
            for (var i = 0; i < elements.length; i++) {
                var el = elements[i];
                var label = normalizeLabel(el.textContent || el.innerText);
                if (!HIDDEN_MENU_LABELS[label]) continue;

                var item = el.closest("li, a, button, .menu-item, .dropdown-item") || el;
                if (item) item.style.display = "none";
            }
        }
    }

    function guardWorkspaceRoutes() {
        var route = frappe.get_route ? frappe.get_route() : [];
        var type = route && route[0];
        var page = route && route[1];
        if (type !== "Workspaces" || !page) return;

        if (BLOCKED_WORKSPACE_SLUGS[String(page).toLowerCase()]) {
            frappe.set_route("home-page");
        }
    }

    var queued = false;
    function queueCleanup() {
        if (queued) return;
        queued = true;
        requestAnimationFrame(function () {
            queued = false;
            hideWorkspaceDropdown();
            hideUserMenuItems();
            guardWorkspaceRoutes();
        });
    }


    orderliftWhenRolesReady(function () {
        if (!shouldSimplify()) return;
        if (document.body) {
            new MutationObserver(queueCleanup).observe(document.body, {
                childList: true,
                subtree: true,
            });
        }

        queueCleanup();
        if (frappe.router && frappe.router.on) {
            frappe.router.on("change", queueCleanup);
        }
    });
})();

// ── Filter sidebar header dropdown for business admin users ──
(function filterBusinessAdminSidebarDropdown() {
    if (window.__orderlift_business_admin_dropdown_patch_installed) return;
    window.__orderlift_business_admin_dropdown_patch_installed = true;

    function shouldDisable() {
        return orderliftIsClientShellUser();
    }

    var BLOCKED_DROPDOWN_ITEMS = {
        desktop: true,
        workspaces: true,
        website: true,
    };

    function normalizeDropdownKey(value) {
        return String(value || "").replace(/\s+/g, " ").trim().toLowerCase();
    }

    function filterDropdownItems(instance) {
        if (!instance || !Array.isArray(instance.dropdown_items)) return;

        var filtered = [];
        for (var i = 0; i < instance.dropdown_items.length; i++) {
            var item = instance.dropdown_items[i];
            if (!item) continue;

            if (item.is_divider) {
                if (filtered.length && !filtered[filtered.length - 1].is_divider) {
                    filtered.push(item);
                }
                continue;
            }

            var nameKey = normalizeDropdownKey(item.name);
            var labelKey = normalizeDropdownKey(item.label);
            if (BLOCKED_DROPDOWN_ITEMS[nameKey] || BLOCKED_DROPDOWN_ITEMS[labelKey]) {
                continue;
            }

            filtered.push(item);
        }

        while (filtered.length && filtered[filtered.length - 1].is_divider) {
            filtered.pop();
        }

        instance.dropdown_items = filtered;
        instance.sibling_workspaces = [];
    }

    function patchSidebarHeaderClass() {
        if (!frappe.ui || !frappe.ui.SidebarHeader || frappe.ui.SidebarHeader.__orderliftBusinessAdminPatched) {
            return !!(frappe.ui && frappe.ui.SidebarHeader);
        }

        var proto = frappe.ui.SidebarHeader.prototype;
        var originalMake = proto.make;
        var originalSetupAppSwitcher = proto.setup_app_switcher;
        var originalPopulate = proto.populate_dropdown_menu;

        proto.fetch_related_icons = function () {
            if (shouldDisable()) return [];
            return [];
        };

        proto.get_help_siblings = function () {
            if (shouldDisable()) return [];
            return [];
        };

        proto.setup_app_switcher = function () {
            if (shouldDisable()) {
                filterDropdownItems(this);
            }
            return originalSetupAppSwitcher ? originalSetupAppSwitcher.apply(this, arguments) : undefined;
        };

        proto.populate_dropdown_menu = function () {
            if (shouldDisable()) {
                filterDropdownItems(this);
                if (this.dropdown_menu && this.dropdown_menu.length) {
                    this.dropdown_menu.empty();
                }
            }
            return originalPopulate ? originalPopulate.apply(this, arguments) : undefined;
        };

        proto.make = function () {
            if (shouldDisable()) {
                filterDropdownItems(this);
            }
            var result = originalMake ? originalMake.apply(this, arguments) : undefined;
            return result;
        };

        frappe.ui.SidebarHeader.__orderliftBusinessAdminPatched = true;
        return true;
    }

    function patchLiveSidebar() {
        var sidebarHeader = frappe.app && frappe.app.sidebar && frappe.app.sidebar.sidebar_header;
        if (sidebarHeader) {
            filterDropdownItems(sidebarHeader);
            if (sidebarHeader.dropdown_menu && sidebarHeader.dropdown_menu.length) {
                sidebarHeader.dropdown_menu.empty();
            }
            if (typeof sidebarHeader.populate_dropdown_menu === "function") {
                sidebarHeader.populate_dropdown_menu();
            }
            if (typeof sidebarHeader.setup_select_options === "function") {
                sidebarHeader.setup_select_options();
            }
        }
    }

    orderliftWhenRolesReady(function () {
        if (!shouldDisable()) return;

        var attempts = 80;
        function ensurePatch() {
            var patched = patchSidebarHeaderClass();
            patchLiveSidebar();
            if (!patched && attempts > 0) {
                attempts -= 1;
                setTimeout(ensurePatch, 100);
            }
        }

        ensurePatch();
        if (frappe.router && frappe.router.on) {
            frappe.router.on("change", function () {
                setTimeout(patchLiveSidebar, 0);
            });
        }
    });
})();

// ── Remove workspace items from Desk search for client users ──
(function filterClientShellSearchResults() {
    if (window.__orderlift_client_search_filter_installed) return;
    window.__orderlift_client_search_filter_installed = true;

    function shouldFilter() {
        return orderliftIsClientShellUser();
    }

    function isBlockedSearchOption(option) {
        if (!option) return false;

        var route = option.route || [];
        var routeType = Array.isArray(route) ? String(route[0] || "") : "";
        var routeTarget = Array.isArray(route) ? String(route[1] || "").toLowerCase() : "";
        var value = String(option.value || "").toLowerCase();
        var label = String(option.label || "").toLowerCase();
        var iconLabel = String(option.icon_data && option.icon_data.label || "").toLowerCase();

        if (routeType === "Workspaces" || routeType === "workspace" || routeTarget === "workspace") {
            return true;
        }

        if (routeTarget === "workspaces") {
            return true;
        }

        if (value.indexOf(" workspace") !== -1 || label.indexOf(" workspace") !== -1) {
            return true;
        }

        if (option.type === "Desktop Icon") {
            return iconLabel !== "main dashboard";
        }

        return false;
    }

    function filterOptions(options) {
        if (!Array.isArray(options)) return options;
        return options.filter(function (option) {
            return !isBlockedSearchOption(option);
        });
    }

    function patchSearchUtils() {
        if (!frappe.search || !frappe.search.utils || frappe.search.utils.__orderliftClientSearchPatched) {
            return !!(frappe.search && frappe.search.utils);
        }

        var utils = frappe.search.utils;
        var originalGetRecentPages = utils.get_recent_pages;
        var originalGetFrequentLinks = utils.get_frequent_links;
        var originalGetDesktopIcons = utils.get_desktop_icons;
        var originalHideResults = utils.hide_results;

        utils.get_recent_pages = function () {
            var options = originalGetRecentPages ? originalGetRecentPages.apply(this, arguments) : [];
            return shouldFilter() ? filterOptions(options) : options;
        };

        utils.get_frequent_links = function () {
            var options = originalGetFrequentLinks ? originalGetFrequentLinks.apply(this, arguments) : [];
            return shouldFilter() ? filterOptions(options) : options;
        };

        utils.get_desktop_icons = function () {
            var options = originalGetDesktopIcons ? originalGetDesktopIcons.apply(this, arguments) : [];
            return shouldFilter() ? filterOptions(options) : options;
        };

        utils.hide_results = function (options) {
            if (shouldFilter() && Array.isArray(options)) {
                for (var i = options.length - 1; i >= 0; i--) {
                    if (isBlockedSearchOption(options[i])) {
                        options.splice(i, 1);
                    }
                }
            }
            if (originalHideResults) {
                return originalHideResults.apply(this, arguments);
            }
        };

        utils.__orderliftClientSearchPatched = true;
        return true;
    }

    orderliftWhenRolesReady(function () {
        if (!shouldFilter()) return;

        var attempts = 80;
        function ensurePatch() {
            var patched = patchSearchUtils();
            if (!patched && attempts > 0) {
                attempts -= 1;
                setTimeout(ensurePatch, 100);
            }
        }

        ensurePatch();
    });
})();

// ── Remove built-in Frappe CRM promo banner from CRM sidebar ──
(function suppressCrmSidebarPromo() {
    if (window.__orderlift_crm_sidebar_promo_patch_installed) return;
    window.__orderlift_crm_sidebar_promo_patch_installed = true;

    function patchSidebarClass() {
        if (!frappe.ui || !frappe.ui.Sidebar || frappe.ui.Sidebar.__orderliftCrmPromoPatched) {
            return !!(frappe.ui && frappe.ui.Sidebar);
        }

        var proto = frappe.ui.Sidebar.prototype;
        proto.get_crm_banner = function () {
            return;
        };

        var originalSetupPromotionalBanners = proto.setup_promotional_banners;
        proto.setup_promotional_banners = function () {
            var result = originalSetupPromotionalBanners ? originalSetupPromotionalBanners.apply(this, arguments) : undefined;
            if (this.$promotional_banners && this.sidebar_title === "CRM") {
                this.$promotional_banners.empty().hide();
            }
            return result;
        };

        frappe.ui.Sidebar.__orderliftCrmPromoPatched = true;
        return true;
    }

    function patchLiveSidebar() {
        var sidebar = frappe.app && frappe.app.sidebar;
        if (!sidebar || sidebar.sidebar_title !== "CRM") return;
        if (sidebar.$promotional_banners) {
            sidebar.$promotional_banners.empty().hide();
        }
    }

    var attempts = 80;
    (function ensurePatch() {
        var patched = patchSidebarClass();
        patchLiveSidebar();
        if (!patched && attempts > 0) {
            attempts -= 1;
            setTimeout(ensurePatch, 100);
        }
    })();

    if (frappe.router && frappe.router.on) {
        frappe.router.on("change", function () {
            setTimeout(patchLiveSidebar, 0);
        });
    }
})();

// ── Guard sidebar_app quick-link workspace rendering ──
(function hardenSidebarAppWorkspaceRouting() {
    if (window.__orderlift_sidebar_app_workspace_guard_installed) return;
    window.__orderlift_sidebar_app_workspace_guard_installed = true;

    function captureBaseShowPage() {
        if (!frappe.views || !frappe.views.Workspace || !frappe.views.Workspace.prototype.show_page) {
            return false;
        }

        if (!frappe.views.Workspace.__orderliftBaseShowPage) {
            frappe.views.Workspace.__orderliftBaseShowPage = frappe.views.Workspace.prototype.show_page;
        }

        return true;
    }

    function patch() {
        if (!frappe.views || !frappe.views.Workspace || !frappe.views.Workspace.prototype.show_page) {
            return false;
        }

        var proto = frappe.views.Workspace.prototype;
        var currentShowPage = proto.show_page;
        var baseShowPage = frappe.views.Workspace.__orderliftBaseShowPage || currentShowPage;

        if (currentShowPage.__orderliftSidebarAppGuardWrapped) {
            return true;
        }

        proto.show_page = function (page) {
            if (!page) {
                return;
            }

            if (!Array.isArray(this.public_pages)) {
                this.public_pages = [];
            }

            if (!Array.isArray(this.private_pages)) {
                this.private_pages = [];
            }

            if (!Array.isArray(this.public_pages) || !Array.isArray(this.private_pages)) {
                return baseShowPage.apply(this, arguments);
            }

            if (!this.public_pages.length && !this.private_pages.length) {
                return baseShowPage.apply(this, arguments);
            }

            return currentShowPage.apply(this, arguments);
        };

        proto.show_page.__orderliftSidebarAppGuardWrapped = true;
        return true;
    }

    function maintainPatch(remaining) {
        captureBaseShowPage();
        patch();
        if (remaining <= 0) return;
        setTimeout(function () {
            maintainPatch(remaining - 1);
        }, 250);
    }

    maintainPatch(200);

    if (frappe.router && frappe.router.on) {
        frappe.router.on("change", function () {
            setTimeout(patch, 0);
        });
    }
})();

// ── Tidy sidebar chrome and Main Dashboard sections ──
(function tuneDeskSidebar() {
    if (window.__orderlift_sidebar_tune_installed) return;
    window.__orderlift_sidebar_tune_installed = true;

    var MAIN_DASHBOARD_KEY = "main dashboard";
    var STYLE_ID = "orderlift-sidebar-tune-style";

    function getSidebar() {
        return frappe.app && frappe.app.sidebar;
    }

    function getSidebarTitle() {
        var sidebar = getSidebar();
        var bodySidebar = document.querySelector(".body-sidebar");
        var title = (bodySidebar && bodySidebar.getAttribute("data-title")) ||
            (sidebar && (sidebar.workspace_title || sidebar.sidebar_title)) ||
            "";
        return String(title || "").trim();
    }

    function getSidebarKey() {
        return getSidebarTitle().toLowerCase();
    }

    function ensureStyle() {
        if (document.getElementById(STYLE_ID)) return;

        var style = document.createElement("style");
        style.id = STYLE_ID;
        style.textContent = [
            ".body-sidebar .orderlift-hidden-standard-item { display: none !important; }",
            ".body-sidebar .standard-items-sections.orderlift-standard-items-hidden { display: none !important; }",
            ".body-sidebar .section-break.orderlift-section-break-with-icon { display: flex; align-items: center; gap: 8px; }",
            ".body-sidebar .section-break .orderlift-section-break-icon { display: inline-flex; align-items: center; color: var(--text-color, var(--gray-700)); }",
            ".body-sidebar .section-break .sidebar-item-label { flex: 1; }",
        ].join("\n");
        document.head.appendChild(style);
    }

    function getMainDashboardSectionIcons() {
        var workspaces = frappe.boot && frappe.boot.workspace_sidebar_item;
        var sidebarData = workspaces && workspaces["Main Dashboard"];
        var items = sidebarData && sidebarData.items;
        var currentSection = "";
        var iconBySection = {};

        if (!Array.isArray(items)) {
            return iconBySection;
        }

        for (var i = 0; i < items.length; i++) {
            var item = items[i] || {};
            if (item.type === "Section Break") {
                currentSection = String(item.label || "");
                if (currentSection && item.icon) {
                    iconBySection[currentSection] = item.icon;
                }
                continue;
            }

            if (!currentSection || !item.child || iconBySection[currentSection] || !item.icon) {
                continue;
            }

            iconBySection[currentSection] = item.icon;
        }

        return iconBySection;
    }

    function hideStandardSidebarItems() {
        var standardSections = document.querySelector(".body-sidebar .standard-items-sections");
        if (!standardSections) return;

        var selectors = [".navbar-search-bar", ".sidebar-notification"];
        for (var i = 0; i < selectors.length; i++) {
            var node = standardSections.querySelector(selectors[i]);
            if (node) {
                node.classList.add("orderlift-hidden-standard-item");
            }
        }

        if (!standardSections.querySelector(".sidebar-item-container:not(.orderlift-hidden-standard-item)")) {
            standardSections.classList.add("orderlift-standard-items-hidden");
        } else {
            standardSections.classList.remove("orderlift-standard-items-hidden");
        }
    }

    function decorateMainDashboardSections() {
        if (getSidebarKey() !== MAIN_DASHBOARD_KEY) return;

        var iconBySection = getMainDashboardSectionIcons();
        var sections = document.querySelectorAll(".body-sidebar .sidebar-item-container.section-item");

        for (var i = 0; i < sections.length; i++) {
            var section = sections[i];
            var sectionName = section.getAttribute("item-name") || section.getAttribute("data-id") || section.title || "";
            var icon = iconBySection[sectionName];
            var anchor = section.querySelector(".section-break");

            if (!icon || !anchor) continue;

            anchor.classList.add("orderlift-section-break-with-icon");

            var iconHost = anchor.querySelector(".orderlift-section-break-icon");
            if (!iconHost) {
                iconHost = document.createElement("span");
                iconHost.className = "orderlift-section-break-icon";
                anchor.insertBefore(iconHost, anchor.firstChild);
            }

            iconHost.innerHTML = frappe.utils.icon(
                icon,
                "sm",
                "",
                "",
                "text-ink-gray-7 current-color",
                true
            );
        }
    }

    function applySidebarTweaks() {
        ensureStyle();
        hideStandardSidebarItems();
        decorateMainDashboardSections();
    }

    var queued = false;
    function queueApply() {
        if (queued) return;
        queued = true;
        requestAnimationFrame(function () {
            queued = false;
            applySidebarTweaks();
        });
    }

    var attempts = 120;
    (function maintainPatch() {
        queueApply();
        if (attempts <= 0) return;
        attempts -= 1;
        setTimeout(maintainPatch, 250);
    })();

    if (document.body) {
        new MutationObserver(queueApply).observe(document.body, {
            childList: true,
            subtree: true,
        });
    } else {
        document.addEventListener("DOMContentLoaded", queueApply);
    }

    if (frappe.router && frappe.router.on) {
        frappe.router.on("change", function () {
            setTimeout(queueApply, 0);
            setTimeout(queueApply, 120);
        });
    }
})();

// ── Rename ERPNext/Frappe Framework labels in Desk UI ──
(function renameBranding() {
    if (window.__orderlift_global_branding_override_installed) return;
    window.__orderlift_global_branding_override_installed = true;

    var replacements = [
        [/ERPNext/gi, "Orderlift"],
        [/Frappe Framework/gi, "Orderlift Platform"],
    ];

    function replaceText(value) {
        if (!value) return value;
        var out = String(value);
        for (var i = 0; i < replacements.length; i++) {
            out = out.replace(replacements[i][0], replacements[i][1]);
        }
        return out;
    }

    function doReplace(root) {
        var host = root || document.body;
        if (!host) return;

        var walker = document.createTreeWalker(host, NodeFilter.SHOW_TEXT, null);
        var node;
        while ((node = walker.nextNode())) {
            var parentTag = node.parentElement && node.parentElement.tagName;
            if (!parentTag) continue;
            if (parentTag === "SCRIPT" || parentTag === "STYLE" || parentTag === "NOSCRIPT") continue;
            var next = replaceText(node.nodeValue);
            if (next !== node.nodeValue) node.nodeValue = next;
        }

        var elements = host.querySelectorAll
            ? host.querySelectorAll("[title], [aria-label], [placeholder], a[href*='frappeframework.com']")
            : [];
        for (var j = 0; j < elements.length; j++) {
            var el = elements[j];
            if (el.hasAttribute("title")) el.setAttribute("title", replaceText(el.getAttribute("title")));
            if (el.hasAttribute("aria-label")) el.setAttribute("aria-label", replaceText(el.getAttribute("aria-label")));
            if (el.hasAttribute("placeholder")) el.setAttribute("placeholder", replaceText(el.getAttribute("placeholder")));
            if (el.tagName === "A" && /frappeframework\.com/i.test(el.getAttribute("href") || "")) {
                el.style.display = "none";
            }
        }

        var title = replaceText(document.title || "");
        if (title !== document.title) document.title = title;
    }

    doReplace(document.body);

    var queued = false;
    function queueReplace() {
        if (queued) return;
        queued = true;
        setTimeout(function () {
            queued = false;
            doReplace(document.body);
        }, 0);
    }

    if (document.body) {
        new MutationObserver(queueReplace).observe(document.body, {
            childList: true,
            subtree: true,
            characterData: true,
        });
    } else {
        document.addEventListener("DOMContentLoaded", function () {
            new MutationObserver(queueReplace).observe(document.body, {
                childList: true,
                subtree: true,
                characterData: true,
            });
            queueReplace();
        });
    }
})();

// ── Brand logo above the sidebar header ──
(function addSidebarBrandLogo() {
    if (window.__orderlift_sidebar_logo_installed) return;
    window.__orderlift_sidebar_logo_installed = true;

    var PUBLIC_FALLBACK_LOGO = "/assets/infintrix_theme/images/erpleaf-logo.png";

    function resolveSidebarLogoUrl(rawUrl) {
        var logoUrl = rawUrl || "";
        if (!logoUrl) return PUBLIC_FALLBACK_LOGO;
        if (logoUrl.indexOf("/private/files/") !== -1) return PUBLIC_FALLBACK_LOGO;
        return logoUrl;
    }

    function ensureLogo() {
        var sidebar = document.querySelector(".body-sidebar");
        if (!sidebar) return;

        // Get or create the logo wrapper
        var wrapper = document.getElementById("orderlift-sidebar-brand-logo");
        if (!wrapper) {
            // Get logo URL from Frappe boot data or the navbar brand image
            var logoUrl = "";
            if (window.frappe && frappe.boot) {
                logoUrl = resolveSidebarLogoUrl(frappe.boot.app_logo_url || "");
            }
            if (!logoUrl) {
                var navLogo = document.querySelector(".navbar-brand .app-logo, .brand-logo");
                if (navLogo) logoUrl = resolveSidebarLogoUrl(navLogo.src || "");
            }
            if (!logoUrl) {
                logoUrl = PUBLIC_FALLBACK_LOGO;
            }
            if (!logoUrl) return;

            wrapper = document.createElement("div");
            wrapper.id = "orderlift-sidebar-brand-logo";
            wrapper.style.cssText =
                "padding: 5px 6px 5px; text-align: center; border-bottom: 1px solid var(--border-color, #e2e6e9);";

            var link = document.createElement("a");
            link.href = "/app";
            link.style.cssText = "text-decoration: none; display: inline-block;";

            var img = document.createElement("img");
            img.src = logoUrl;
            img.alt = "Orderlift";
            img.style.cssText = "max-width: 85px; max-height: 50px; object-fit: contain; cursor: pointer;";
            img.onerror = function () {
                if (img.src.indexOf(PUBLIC_FALLBACK_LOGO) !== -1) return;
                img.src = PUBLIC_FALLBACK_LOGO;
            };
            link.appendChild(img);
            wrapper.appendChild(link);
        }

        var existingImg = wrapper.querySelector("img");
        if (existingImg) {
            var safeSrc = resolveSidebarLogoUrl(existingImg.getAttribute("src") || existingImg.src || "");
            if (existingImg.src !== safeSrc) {
                existingImg.src = safeSrc;
            }
        }

        // Always ensure logo is the FIRST child of .body-sidebar
        // (Frappe's sidebar_header.js uses prependTo which pushes us down)
        if (sidebar.firstChild !== wrapper) {
            sidebar.insertBefore(wrapper, sidebar.firstChild);
        }
    }

    // Persistent observer — keeps repositioning after Frappe re-renders sidebar header
    var queued = false;
    function queueEnsure() {
        if (queued) return;
        queued = true;
        requestAnimationFrame(function () {
            queued = false;
            ensureLogo();
        });
    }

    if (document.body) {
        new MutationObserver(queueEnsure).observe(document.body, {
            childList: true,
            subtree: true,
        });
    }
    queueEnsure();
})();

orderlift = {
    /**
     * Open the SIG project map page from anywhere in Desk.
     */
    open_project_map: function () {
        frappe.set_route("project-map");
    },

    /**
     * Format a number as a French-style currency string.
     * e.g. 12345.6 → "12 345,60 MAD"
     */
    format_currency_fr: function (amount, currency) {
        currency = currency || "MAD";
        return (
            new Intl.NumberFormat("fr-FR", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            }).format(amount) +
            " " +
            currency
        );
    },
};
