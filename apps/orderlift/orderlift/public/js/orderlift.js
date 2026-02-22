/**
 * Orderlift — Global Desk JS
 * Loaded for all logged-in Desk users via app_include_js in hooks.py
 */

frappe.provide("orderlift");

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

    function injectLogo() {
        var sidebar = document.querySelector(".body-sidebar");
        if (!sidebar) return false;
        if (document.getElementById("orderlift-sidebar-brand-logo")) return true;

        // Get logo URL from Frappe boot data or the navbar brand image
        var logoUrl = "";
        if (window.frappe && frappe.boot) {
            logoUrl = frappe.boot.app_logo_url || "";
        }
        if (!logoUrl) {
            var navLogo = document.querySelector(".navbar-brand .app-logo, .brand-logo");
            if (navLogo) logoUrl = navLogo.src || "";
        }
        if (!logoUrl) return false;

        // Create the logo container
        var wrapper = document.createElement("div");
        wrapper.id = "orderlift-sidebar-brand-logo";
        wrapper.style.cssText =
            "padding: 16px 16px 8px 16px; text-align: center; border-bottom: 1px solid var(--border-color, #e2e6e9);";

        var img = document.createElement("img");
        img.src = logoUrl;
        img.alt = "Orderlift";
        img.style.cssText = "max-width: 140px; max-height: 50px; object-fit: contain;";
        wrapper.appendChild(img);

        // Insert before the sidebar-header (first child of .body-sidebar)
        var sidebarHeader = sidebar.querySelector(".sidebar-header");
        if (sidebarHeader) {
            sidebarHeader.parentElement.insertBefore(wrapper, sidebarHeader);
        } else {
            sidebar.insertBefore(wrapper, sidebar.firstChild);
        }
        return true;
    }

    // Try immediately, then watch for sidebar render
    if (!injectLogo()) {
        var observer = new MutationObserver(function () {
            if (injectLogo()) observer.disconnect();
        });
        var target = document.body || document.documentElement;
        observer.observe(target, { childList: true, subtree: true });
    }
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
