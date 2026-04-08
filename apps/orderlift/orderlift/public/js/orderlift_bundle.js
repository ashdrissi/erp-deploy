/**
 * Orderlift — Global Desk JS
 * Loaded for all logged-in Desk users via app_include_js in hooks.py
 */

frappe.provide("orderlift");

var ORDERLIFT_CLIENT_SHELL_ROLE = "Orderlift Client User";
var ORDERLIFT_INTERNAL_BYPASS_ROLES = ["System Manager", "Developer"];

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
    return orderliftHasRole(ORDERLIFT_CLIENT_SHELL_ROLE) && !orderliftHasAnyRole(ORDERLIFT_INTERNAL_BYPASS_ROLES);
}

function orderliftWhenRolesReady(callback, attempts) {
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

// ── Keep sidebar context in Desk URLs (except excluded routes) ──
(function injectSidebarQueryParam() {
    if (window.__orderlift_sidebar_url_injector_installed) return;
    window.__orderlift_sidebar_url_injector_installed = true;

    var TARGET_SIDEBAR = "Main Dashboard";
    var EXCLUDED_PREFIXES = ["/desk/workspace", "/desk/workspace-sidebar"];
    var EXCLUDED_SLUGS = ["build"];

    function isExcluded(pathname) {
        if (!pathname || !pathname.startsWith("/desk")) return true;

        for (var i = 0; i < EXCLUDED_PREFIXES.length; i++) {
            if (pathname.startsWith(EXCLUDED_PREFIXES[i])) return true;
        }

        var slug = pathname.replace(/^\/desk\/?/, "").split("/")[0] || "";
        slug = slug.toLowerCase();
        return EXCLUDED_SLUGS.indexOf(slug) !== -1;
    }

    function ensureSidebarOnCurrentUrl() {
        try {
            var url = new URL(window.location.href);
            if (isExcluded(url.pathname)) return;

            if (url.searchParams.get("sidebar") !== TARGET_SIDEBAR) {
                url.searchParams.set("sidebar", TARGET_SIDEBAR);
                window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
            }
        } catch (e) {
            // no-op
        }
    }

    function decorateDeskLinks(root) {
        var scope = root || document;
        var links = scope.querySelectorAll ? scope.querySelectorAll('a[href^="/desk/"]') : [];
        for (var i = 0; i < links.length; i++) {
            var link = links[i];
            var href = link.getAttribute("href");
            if (!href) continue;

            try {
                var url = new URL(href, window.location.origin);
                if (isExcluded(url.pathname)) continue;
                url.searchParams.set("sidebar", TARGET_SIDEBAR);
                link.setAttribute("href", url.pathname + url.search + url.hash);
            } catch (e) {
                // ignore invalid href
            }
        }
    }

    var originalPushState = window.history.pushState;
    window.history.pushState = function () {
        var result = originalPushState.apply(this, arguments);
        setTimeout(ensureSidebarOnCurrentUrl, 0);
        return result;
    };

    var originalReplaceState = window.history.replaceState;
    window.history.replaceState = function () {
        var result = originalReplaceState.apply(this, arguments);
        setTimeout(ensureSidebarOnCurrentUrl, 0);
        return result;
    };

    window.addEventListener("popstate", function () {
        setTimeout(ensureSidebarOnCurrentUrl, 0);
    });

    var queued = false;
    function queueDecorate() {
        if (queued) return;
        queued = true;
        requestAnimationFrame(function () {
            queued = false;
            ensureSidebarOnCurrentUrl();
            decorateDeskLinks(document.body);
        });
    }

    if (document.body) {
        new MutationObserver(queueDecorate).observe(document.body, {
            childList: true,
            subtree: true,
        });
    }

    ensureSidebarOnCurrentUrl();
    decorateDeskLinks(document.body);
})();

// ── Lock business admin users into Main Dashboard shell ──
(function lockBusinessAdminShell() {
    if (window.__orderlift_business_admin_shell_lock_installed) return;
    window.__orderlift_business_admin_shell_lock_installed = true;

    function shouldLock() {
        return orderliftIsClientShellUser();
    }

    var TARGET_PATH = "/desk/home-page";
    var TARGET_URL = "/desk/home-page?sidebar=Main+Dashboard";
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
        if (window.location.pathname === TARGET_PATH && window.location.search.indexOf("sidebar=Main+Dashboard") !== -1) {
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
        "Session Defaults": true,
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

// ── Disable sidebar header dropdown for business admin users ──
(function disableBusinessAdminSidebarDropdown() {
    if (window.__orderlift_business_admin_dropdown_patch_installed) return;
    window.__orderlift_business_admin_dropdown_patch_installed = true;

    function shouldDisable() {
        return orderliftIsClientShellUser();
    }

    function hideHeaderDropdown(instance) {
        if (!instance) return;

        try {
            instance.sibling_workspaces = [];
            instance.dropdown_items = [];

            if (instance.$drop_icon && instance.$drop_icon.length) {
                instance.$drop_icon.hide();
            }

            if (instance.dropdown_menu && instance.dropdown_menu.length) {
                instance.dropdown_menu.empty().hide();
            }

            if (instance.wrapper && instance.wrapper.length) {
                instance.wrapper.find(".drop-icon, .sidebar-header-menu").hide();
            }
        } catch (e) {
            // no-op
        }
    }

    function patchSidebarHeaderClass() {
        if (!frappe.ui || !frappe.ui.SidebarHeader || frappe.ui.SidebarHeader.__orderliftBusinessAdminPatched) {
            return !!(frappe.ui && frappe.ui.SidebarHeader);
        }

        var proto = frappe.ui.SidebarHeader.prototype;
        var originalMake = proto.make;
        var originalToggle = proto.toggle_dropdown_menu;

        proto.fetch_related_icons = function () {
            if (shouldDisable()) return [];
            return [];
        };

        proto.get_help_siblings = function () {
            if (shouldDisable()) return [];
            return [];
        };

        proto.setup_app_switcher = function () {
            if (shouldDisable()) return;
        };

        proto.populate_dropdown_menu = function () {
            if (shouldDisable()) {
                hideHeaderDropdown(this);
                return;
            }
        };

        proto.toggle_dropdown_menu = function () {
            if (shouldDisable()) {
                hideHeaderDropdown(this);
                return;
            }
            if (originalToggle) {
                return originalToggle.apply(this, arguments);
            }
        };

        proto.make = function () {
            var result = originalMake ? originalMake.apply(this, arguments) : undefined;
            if (shouldDisable()) {
                hideHeaderDropdown(this);
            }
            return result;
        };

        frappe.ui.SidebarHeader.__orderliftBusinessAdminPatched = true;
        return true;
    }

    function patchLiveSidebar() {
        var sidebarHeader = frappe.app && frappe.app.sidebar && frappe.app.sidebar.sidebar_header;
        if (sidebarHeader) {
            hideHeaderDropdown(sidebarHeader);
        }

        var liveNodes = document.querySelectorAll(".sidebar-header .drop-icon, .sidebar-header-menu");
        for (var i = 0; i < liveNodes.length; i++) {
            liveNodes[i].style.display = "none";
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

    function ensureLogo() {
        var sidebar = document.querySelector(".body-sidebar");
        if (!sidebar) return;

        // Get or create the logo wrapper
        var wrapper = document.getElementById("orderlift-sidebar-brand-logo");
        if (!wrapper) {
            // Get logo URL from Frappe boot data or the navbar brand image
            var logoUrl = "";
            if (window.frappe && frappe.boot) {
                logoUrl = frappe.boot.app_logo_url || "";
            }
            if (!logoUrl) {
                var navLogo = document.querySelector(".navbar-brand .app-logo, .brand-logo");
                if (navLogo) logoUrl = navLogo.src || "";
            }
            if (!logoUrl) {
                logoUrl = "/assets/infintrix_theme/images/erpleaf-logo.png";
            }
            if (!logoUrl) return;

            wrapper = document.createElement("div");
            wrapper.id = "orderlift-sidebar-brand-logo";
            wrapper.style.cssText =
                "padding: 16px 16px 8px 16px; text-align: center; border-bottom: 1px solid var(--border-color, #e2e6e9);";

            var link = document.createElement("a");
            link.href = "/app";
            link.style.cssText = "text-decoration: none; display: inline-block;";

            var img = document.createElement("img");
            img.src = logoUrl;
            img.alt = "Orderlift";
            img.style.cssText = "max-width: 140px; max-height: 50px; object-fit: contain; cursor: pointer;";
            link.appendChild(img);
            wrapper.appendChild(link);
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
