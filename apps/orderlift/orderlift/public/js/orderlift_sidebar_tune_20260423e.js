/**
 * Orderlift - Sidebar tune patch
 * Separate versioned asset so browsers fetch sidebar fixes immediately.
 */

(function orderliftSidebarTunePatch() {
    if (window.__orderlift_sidebar_tune_20260423c_installed) return;
    window.__orderlift_sidebar_tune_20260423c_installed = true;

    var STYLE_ID = "orderlift-sidebar-tune-20260423c-style";
    var MAIN_DASHBOARD_KEY = "main dashboard";
    var WORK_COUNT_REFRESH_MS = 60000;
    var workCounts = { open_todos: 0, unread_notifications: 0 };
    var lastWorkCountRefresh = 0;
    var workCountRequest = null;
    var workCountRefreshPending = false;
    var workCountRefreshTimer = null;

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
            ".body-sidebar .item-anchor.orderlift-work-count-anchor { min-width: 0; overflow: hidden; }",
            ".body-sidebar .item-anchor.orderlift-work-count-anchor .sidebar-item-label { min-width: 0; }",
            ".body-sidebar .orderlift-work-count { box-sizing: border-box; flex: 0 0 auto; min-width: 18px; max-width: 48px; height: 18px; margin: 0 6px 0 4px; padding: 0 5px; border: 1px solid transparent; border-radius: 9px; display: inline-flex; align-items: center; justify-content: center; color: #fff; font-size: 10px; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.12); }",
            ".body-sidebar .orderlift-work-count.is-todo { background: var(--blue-500, #3b82f6); border-color: var(--blue-600, #2563eb); }",
            ".body-sidebar .orderlift-work-count.is-notification { background: var(--red-500, #e24c4c); border-color: var(--red-600, #c53030); }",
            ".body-sidebar .orderlift-work-count.is-empty { background: var(--gray-200, #e5e7eb); border-color: var(--gray-300, #d1d5db); color: var(--gray-700, #374151); box-shadow: none; }",
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

    function findSidebarItemByLabel(label) {
        var items = document.querySelectorAll(".body-sidebar .sidebar-item-container");
        for (var i = 0; i < items.length; i++) {
            var itemLabel = normalize(items[i].getAttribute("item-name") || items[i].getAttribute("data-id") || items[i].title);
            if (itemLabel === label) return items[i];
        }
        return null;
    }

    function sidebarLabelForTarget(target, fallback) {
        var items = getCurrentSidebarItems();
        for (var i = 0; i < items.length; i++) {
            if (normalize(items[i].link_to) === target) return normalize(items[i].label) || fallback;
        }
        return fallback;
    }

    function findSidebarItemByTarget(target, fallbackLabel) {
        var slug = frappe.router && frappe.router.slug
            ? frappe.router.slug(target)
            : normalize(target).toLowerCase().replace(/\s+/g, "-");
        var expectedPath = "/app/" + slug;
        var anchors = document.querySelectorAll(".body-sidebar .sidebar-item-container .item-anchor[href]");
        for (var i = 0; i < anchors.length; i++) {
            var href = anchors[i].getAttribute("href") || "";
            var path = href.split("?")[0].replace(/\/$/, "");
            if (path === expectedPath || path.endsWith(expectedPath)) {
                return anchors[i].closest(".sidebar-item-container");
            }
        }
        var item = findSidebarItemByLabel(sidebarLabelForTarget(target, fallbackLabel));
        if (!item && target === "my-todos") item = findSidebarItemByLabel("ToDo");
        return item;
    }

    function renderWorkCount(target, fallbackLabel, count, kind) {
        var item = findSidebarItemByTarget(target, fallbackLabel);
        if (!item) return;
        var anchor = item.querySelector(".item-anchor") || item;
        anchor.classList.add("orderlift-work-count-anchor");
        var badge = item.querySelector(".orderlift-work-count");
        if (!badge) {
            badge = document.createElement("span");
            var control = anchor.querySelector(".sidebar-item-control");
            anchor.insertBefore(badge, control || null);
        }
        badge.className = "orderlift-work-count is-" + kind + (count ? "" : " is-empty");
        badge.textContent = String(count);
        var description = kind === "todo"
            ? __("{0} open ToDos", [count])
            : __("{0} unread notifications", [count]);
        badge.setAttribute("aria-label", description);
        badge.setAttribute("title", description);
    }

    function renderWorkCounts() {
        renderWorkCount("my-todos", "My ToDos", Number(workCounts.open_todos || 0), "todo");
        renderWorkCount("Notification Log", "Notifications", Number(workCounts.unread_notifications || 0), "notification");
    }

    function refreshWorkCounts(force) {
        if (getSidebarKey() !== MAIN_DASHBOARD_KEY) return;
        if (workCountRequest) {
            workCountRefreshPending = workCountRefreshPending || Boolean(force);
            return;
        }
        var now = Date.now();
        if (!force && now - lastWorkCountRefresh < WORK_COUNT_REFRESH_MS) {
            renderWorkCounts();
            return;
        }
        lastWorkCountRefresh = now;
        workCountRequest = frappe.call("orderlift.work_notifications.get_work_counts")
            .then(function (response) {
                workCounts = (response && response.message) || workCounts;
                renderWorkCounts();
            })
            .finally(function () {
                workCountRequest = null;
                if (workCountRefreshPending) {
                    workCountRefreshPending = false;
                    scheduleWorkCountRefresh(0);
                }
            });
    }

    function scheduleWorkCountRefresh(delay) {
        clearTimeout(workCountRefreshTimer);
        workCountRefreshTimer = setTimeout(function () {
            refreshWorkCounts(true);
        }, delay || 0);
    }

    function apply() {
        ensureStyle();
        hideSearchAndNotifications();
        applySectionHeaderIcons();
        renderWorkCounts();
        refreshWorkCounts(false);
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
            scheduleWorkCountRefresh(0);
            setTimeout(function () { scheduleWorkCountRefresh(0); }, 750);
            setTimeout(queueApply, 0);
            setTimeout(queueApply, 150);
            setTimeout(queueApply, 500);
        });
    }

    window.addEventListener("focus", function () {
        scheduleWorkCountRefresh(0);
    });

    if (frappe.realtime && frappe.realtime.on) {
        if (frappe.realtime.doctype_subscribe) {
            frappe.realtime.doctype_subscribe("ToDo");
            frappe.realtime.doctype_subscribe("Notification Log");
        }
        frappe.realtime.on("list_update", function (data) {
            if (data && (data.doctype === "ToDo" || data.doctype === "Notification Log")) {
                scheduleWorkCountRefresh(150);
            }
        });
        frappe.realtime.on("notification", function () {
            scheduleWorkCountRefresh(150);
        });
        frappe.realtime.on("indicator_hide", function () {
            scheduleWorkCountRefresh(150);
        });
    }

    setInterval(function () {
        if (!document.hidden) refreshWorkCounts(true);
    }, WORK_COUNT_REFRESH_MS);

    window.orderliftRefreshWorkCounts = function () {
        scheduleWorkCountRefresh(0);
    };

    if (frappe.ui && frappe.ui.form && frappe.ui.form.on) {
        frappe.ui.form.on("Notification Log", {
            refresh: function (frm) {
                if (frm.doc.read || frm.doc.for_user !== frappe.session.user || frm.__orderliftMarkingRead) return;
                frm.__orderliftMarkingRead = true;
                frappe.call({
                    method: "frappe.desk.doctype.notification_log.notification_log.mark_as_read",
                    args: { docname: frm.doc.name },
                }).then(function () {
                    frm.doc.read = 1;
                    frm.refresh_field("read");
                    scheduleWorkCountRefresh(0);
                }).finally(function () {
                    frm.__orderliftMarkingRead = false;
                });
            },
        });
    }
})();
