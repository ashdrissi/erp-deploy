(function orderliftMainDashboardSidebarUrl() {
    if (window.__orderlift_main_dashboard_sidebar_url_20260427b_installed) return;
    window.__orderlift_main_dashboard_sidebar_url_20260427b_installed = true;

    var SIDEBAR_NAME = "Main Dashboard";
    var SIDEBAR_PARAM = "sidebar";
    var BARE_DESK_PATHS = { "/desk": true, "/app": true };

    function isDeskPath(pathname) {
        return pathname === "/desk" || pathname === "/app" || pathname.indexOf("/desk/") === 0 || pathname.indexOf("/app/") === 0;
    }

    function withMainDashboardSidebar(urlLike) {
        var url = new URL(urlLike || window.location.href, window.location.origin);
        var pathname = url.pathname.replace(/\/+$/, "") || "/";
        if (!isDeskPath(pathname)) return "";
        if (BARE_DESK_PATHS[pathname]) url.pathname = "/desk/home-page";
        url.searchParams.set(SIDEBAR_PARAM, SIDEBAR_NAME);
        return url.pathname + url.search + url.hash;
    }

    function normalizeCurrentUrl() {
        var target = withMainDashboardSidebar(window.location.href);
        if (!target) return;
        var current = window.location.pathname + window.location.search + window.location.hash;
        if (current !== target) window.history.replaceState(window.history.state, "", target);
    }

    function patchHistoryMethod(methodName) {
        var original = window.history[methodName];
        if (!original || original.__orderlift_sidebar_patched) return;
        window.history[methodName] = function (state, title, url) {
            if (url) {
                var target = withMainDashboardSidebar(url);
                if (target) url = target;
            }
            return original.call(this, state, title, url);
        };
        window.history[methodName].__orderlift_sidebar_patched = true;
    }

    function isNewDimensioningSetName(name) {
        return !name || String(name).indexOf("new-dimensioning-set") === 0;
    }

    function openDimensioningSetBuilder(setName) {
        if (!setName || isNewDimensioningSetName(setName)) return;
        if (!window.frappe || !frappe.set_route) return;
        frappe.route_options = { dimensioning_set: setName };
        frappe.set_route("dimensioning-set-builder");
    }

    function prepareNewDimensioningSetForm(frm) {
        if (!frm || !frm.is_new || !frm.is_new()) return;
        if (frm.__orderlift_dimensioning_new_form_prepared) return;
        frm.__orderlift_dimensioning_new_form_prepared = true;

        var visibleFields = { set_name: true };
        (frm.meta.fields || []).forEach(function (field) {
            if (!field.fieldname) return;
            frm.toggle_display(field.fieldname, !!visibleFields[field.fieldname]);
        });

        frm.clear_custom_buttons();
        frm.set_intro(__("Name the set, then save to continue in the guided Dimensioning Set Builder."), "blue");
        frm.page.clear_primary_action();
        frm.page.set_primary_action(__("Create in Builder"), function () {
            frm.__orderlift_dimensioning_create_in_builder = true;
            frm.save();
        });
    }

    function redirectDimensioningSetRoute() {
        if (!window.frappe || !frappe.get_route) return;
        var route = frappe.get_route() || [];
        if (route[0] !== "Form" || route[1] !== "Dimensioning Set") return;
        if (isNewDimensioningSetName(route[2])) {
            setTimeout(function () {
                prepareNewDimensioningSetForm(window.cur_frm);
            }, 200);
            return;
        }
        openDimensioningSetBuilder(route[2]);
    }

    function installDimensioningSetFormHandlers() {
        if (!window.frappe || !frappe.ui || !frappe.ui.form || window.__orderlift_dimensioning_set_form_handlers_installed) return;
        window.__orderlift_dimensioning_set_form_handlers_installed = true;
        frappe.ui.form.on("Dimensioning Set", {
            refresh: function (frm) {
                if (frm.is_new()) {
                    prepareNewDimensioningSetForm(frm);
                    return;
                }
                openDimensioningSetBuilder(frm.doc.name);
            },
            after_save: function (frm) {
                if (!frm.__orderlift_dimensioning_create_in_builder) return;
                frm.__orderlift_dimensioning_create_in_builder = false;
                openDimensioningSetBuilder(frm.doc.name);
            },
        });
    }

    normalizeCurrentUrl();
    patchHistoryMethod("pushState");
    patchHistoryMethod("replaceState");
    installDimensioningSetFormHandlers();

    window.addEventListener("popstate", function () {
        normalizeCurrentUrl();
        redirectDimensioningSetRoute();
    });
    document.addEventListener("visibilitychange", function () {
        if (!document.hidden) {
            normalizeCurrentUrl();
            redirectDimensioningSetRoute();
        }
    });
    if (window.frappe && frappe.router && frappe.router.on) {
        frappe.router.on("change", function () {
            setTimeout(function () {
                normalizeCurrentUrl();
                installDimensioningSetFormHandlers();
                redirectDimensioningSetRoute();
            }, 0);
        });
    }
})();
