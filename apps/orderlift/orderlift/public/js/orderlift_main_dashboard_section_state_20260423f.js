/**
 * Orderlift - Main Dashboard section state normalizer.
 * Ensures Main Dashboard sections start consistently collapsed,
 * without repeatedly fighting user toggles after render.
 */

(function normalizeMainDashboardSectionState() {
    if (window.__orderlift_main_dashboard_section_state_20260423f_installed) return;
    window.__orderlift_main_dashboard_section_state_20260423f_installed = true;

    var MAIN_DASHBOARD_KEY = "main dashboard";

    function getSidebar() {
        return frappe.app && frappe.app.sidebar;
    }

    function getSidebarBody() {
        return document.querySelector(".body-sidebar");
    }

    function getSidebarKey() {
        var body = getSidebarBody();
        var sidebar = getSidebar();
        var title = (body && body.getAttribute("data-title")) ||
            (sidebar && (sidebar.workspace_title || sidebar.sidebar_title)) ||
            "";
        return String(title || "").trim().toLowerCase();
    }

    function readSectionState() {
        try {
            var raw = window.localStorage && window.localStorage.getItem("section-breaks-state");
            return raw ? JSON.parse(raw) : {};
        } catch (e) {
            return {};
        }
    }

    function writeSectionState(state) {
        try {
            if (!window.localStorage) return;
            window.localStorage.setItem("section-breaks-state", JSON.stringify(state));
        } catch (e) {
            // ignore storage failures
        }
    }

    function clearMainDashboardState() {
        var state = readSectionState();
        if (!Object.prototype.hasOwnProperty.call(state, MAIN_DASHBOARD_KEY)) {
            return;
        }

        delete state[MAIN_DASHBOARD_KEY];
        writeSectionState(state);
    }

    function collapseSectionsOnce() {
        var sidebar = getSidebar();
        var body = getSidebarBody();
        if (!sidebar || !body || getSidebarKey() !== MAIN_DASHBOARD_KEY || !Array.isArray(sidebar.items)) {
            return;
        }

        if (body.dataset.orderliftMainDashboardCollapsedOnce === "1") {
            return;
        }

        clearMainDashboardState();

        var collapsedLabels = {};
        for (var i = 0; i < sidebar.items.length; i++) {
            var item = sidebar.items[i];
            if (!item || !item.item || item.item.type !== "Section Break") continue;
            if (!item.$drop_icon || !item.$drop_icon.length) continue;

            if (typeof item.close === "function") {
                item.close();
                collapsedLabels[item.item.label] = true;
            }
        }

        var state = readSectionState();
        state[MAIN_DASHBOARD_KEY] = collapsedLabels;
        writeSectionState(state);
        body.dataset.orderliftMainDashboardCollapsedOnce = "1";
    }

    function resetMarkerWhenLeaving() {
        var body = getSidebarBody();
        if (!body) return;
        if (getSidebarKey() === MAIN_DASHBOARD_KEY) return;
        delete body.dataset.orderliftMainDashboardCollapsedOnce;
    }

    var queued = false;
    function queueNormalize() {
        if (queued) return;
        queued = true;
        requestAnimationFrame(function () {
            queued = false;
            resetMarkerWhenLeaving();
            collapseSectionsOnce();
        });
    }

    var attempts = 80;
    (function prime() {
        queueNormalize();
        if (attempts <= 0) return;
        attempts -= 1;
        setTimeout(prime, 200);
    })();

    if (document.body) {
        new MutationObserver(queueNormalize).observe(document.body, {
            childList: true,
            subtree: true,
        });
    }

    if (frappe.router && frappe.router.on) {
        frappe.router.on("change", function () {
            var body = getSidebarBody();
            if (body) {
                delete body.dataset.orderliftMainDashboardCollapsedOnce;
            }
            setTimeout(queueNormalize, 0);
            setTimeout(queueNormalize, 150);
        });
    }
})();
