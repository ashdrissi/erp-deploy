/**
 * Orderlift — Global Desk JS
 * Loaded for all logged-in Desk users via app_include_js in hooks.py
 */

frappe.provide("orderlift");

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
