/**
 * Orderlift - Sidebar tune patch
 * Separate versioned asset so browsers fetch sidebar fixes immediately.
 */

(function orderliftSidebarTunePatch() {
    if (window.__orderlift_sidebar_tune_20260423c_installed) return;
    window.__orderlift_sidebar_tune_20260423c_installed = true;

    var STYLE_ID = "orderlift-sidebar-tune-20260423c-style";
    var MAIN_DASHBOARD_KEY = "main dashboard";

    function normalize(value) {
        return String(value || "").trim();
    }

    function getSidebar() {
        return frappe.app && frappe.app.sidebar;
    }

    function getSidebarTitle() {
        var bodySidebar = document.querySelector(".body-sidebar");
        var sidebar = getSidebar();
        return normalize(
            (bodySidebar && bodySidebar.getAttribute("data-title")) ||
            (sidebar && (sidebar.workspace_title || sidebar.sidebar_title)) ||
            ""
        );
    }

    function getSidebarKey() {
        return getSidebarTitle().toLowerCase();
    }

    function getCurrentSidebarItems() {
        var title = getSidebarTitle();
        var workspaceSidebar = frappe.boot && frappe.boot.workspace_sidebar_item;
        var data = workspaceSidebar && workspaceSidebar[title];
        return data && Array.isArray(data.items) ? data.items : [];
    }

    function ensureStyle() {
        if (document.getElementById(STYLE_ID)) return;

        var style = document.createElement("style");
        style.id = STYLE_ID;
        style.textContent = [
            ".body-sidebar .orderlift-hidden-sidebar-node { display: none !important; }",
            ".body-sidebar .standard-items-sections.orderlift-empty-standard-items { display: none !important; }",
            ".body-sidebar .section-break.orderlift-section-break-with-icon { display: flex; align-items: center; gap: 8px; }",
            ".body-sidebar .section-break .orderlift-section-break-icon { display: inline-flex; align-items: center; flex: 0 0 auto; color: var(--text-color, var(--gray-700)); }",
            ".body-sidebar .section-break .sidebar-item-label { flex: 1 1 auto; }",
            ".body-sidebar .section-break .sidebar-item-control { margin-left: auto; }",
        ].join("\n");
        document.head.appendChild(style);
    }

    function hideSearchAndNotifications() {
        var standardSections = document.querySelector(".body-sidebar .standard-items-sections");
        if (!standardSections) return;

        var selectors = [
            ".navbar-search-bar",
            ".sidebar-notification",
            "#navbar-modal-search",
            "[title='Search']",
            "[title='Notification']",
        ];

        for (var i = 0; i < selectors.length; i++) {
            var nodes = standardSections.querySelectorAll(selectors[i]);
            for (var j = 0; j < nodes.length; j++) {
                nodes[j].classList.add("orderlift-hidden-sidebar-node");
                nodes[j].style.display = "none";
            }
        }

        var visibleChildren = Array.prototype.filter.call(standardSections.children || [], function (node) {
            return !node.classList.contains("orderlift-hidden-sidebar-node") && node.offsetParent !== null;
        });

        if (!visibleChildren.length) {
            standardSections.classList.add("orderlift-empty-standard-items");
        }
    }

    function getSectionIconMap() {
        var items = getCurrentSidebarItems();
        var iconMap = {};

        for (var i = 0; i < items.length; i++) {
            var item = items[i] || {};
            if (item.type === "Section Break" && item.label && item.icon) {
                iconMap[item.label] = item.icon;
            }
        }

        return iconMap;
    }

    function applySectionHeaderIcons() {
        var iconMap = getSectionIconMap();
        var sections = document.querySelectorAll(".body-sidebar .sidebar-item-container.section-item");

        for (var i = 0; i < sections.length; i++) {
            var section = sections[i];
            var label = normalize(section.getAttribute("item-name") || section.getAttribute("data-id") || section.title);
            var icon = iconMap[label];
            var anchor = section.querySelector(".section-break");

            if (!label || !icon || !anchor) continue;

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

    function apply() {
        ensureStyle();
        hideSearchAndNotifications();
        applySectionHeaderIcons();
    }

    var queued = false;
    function queueApply() {
        if (queued) return;
        queued = true;
        requestAnimationFrame(function () {
            queued = false;
            apply();
        });
    }

    var attempts = 160;
    (function keepApplying() {
        queueApply();
        if (attempts <= 0) return;
        attempts -= 1;
        setTimeout(keepApplying, 250);
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
            setTimeout(queueApply, 150);
            setTimeout(queueApply, 500);
        });
    }
})();
