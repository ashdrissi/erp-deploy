(function orderliftConnectionDashboardLinks() {
    if (window.__orderlift_connection_dashboard_links_20260616a_installed) return;
    window.__orderlift_connection_dashboard_links_20260616a_installed = true;

    var METHOD = "orderlift.connection_dashboard_links.get_connection_route";
    var PATCHED_ATTR = "data-orderlift-connection-link";
    var OBSERVER_ATTR = "data-orderlift-connection-observer";
    var DASHBOARD_PATCH_FLAG = "__orderliftConnectionDashboardLinks20260616aPatched";
    var observer = null;
    var enhanceTimer = null;

    function currentForm() {
        if (!window.frappe || !frappe.get_route || !window.cur_frm) return null;
        var route = frappe.get_route();
        if (!route || route[0] !== "Form" || !route[1] || !route[2]) return null;
        var docname = cur_frm.docname || (cur_frm.doc && cur_frm.doc.name);
        if (cur_frm.doctype !== route[1] || docname !== route[2]) return null;
        if (!cur_frm.doc || cur_frm.doc.__islocal) return null;
        return cur_frm;
    }

    function scheduleEnhance() {
        window.clearTimeout(enhanceTimer);
        enhanceTimer = window.setTimeout(enhanceDashboard, 250);
    }

    function enhanceDashboard() {
        var frm = currentForm();
        if (!frm || !frm.dashboard || !frm.dashboard.wrapper) return;

        injectStyle();
        watchDashboard(frm.dashboard.wrapper);

        var $wrapper = $(frm.dashboard.wrapper);
        $wrapper.find(".document-link, [data-doctype], [data-link-doctype], [data-document-type]").each(function () {
            patchConnectionItem(frm, $(this));
        });
    }

    function watchDashboard(wrapper) {
        var node = $(wrapper).get(0);
        if (!node || node.getAttribute(OBSERVER_ATTR)) return;
        node.setAttribute(OBSERVER_ATTR, "1");
        if (!window.MutationObserver) return;
        if (observer) observer.disconnect();
        observer = new MutationObserver(function () {
            scheduleEnhance();
        });
        observer.observe(node, { attributes: true, childList: true, characterData: true, subtree: true });
    }

    function patchConnectionItem(frm, $item) {
        if (!$item || !$item.length || $item.attr(PATCHED_ATTR)) return;

        var targetDoctype = getTargetDoctype($item);
        if (!targetDoctype || targetDoctype === frm.doctype) return;

        var $count = getCountElement($item);
        var count = parseCount($count.length ? $count.text() : $item.text());
        if (!$count.length || !count) return;

        $item.attr(PATCHED_ATTR, "1");
        $count
            .addClass("ol-connection-count-link")
            .attr("title", __("Open linked {0}", [targetDoctype]))
            .off("click.orderliftConnectionLinks")
            .on("click.orderliftConnectionLinks", function (event) {
                event.preventDefault();
                event.stopImmediatePropagation();
                event.stopPropagation();
                openConnectionList(frm, targetDoctype);
            });
    }

    function getTargetDoctype($item) {
        var attrs = ["doctype", "link-doctype", "document-type", "target-doctype"];
        for (var i = 0; i < attrs.length; i++) {
            var value = cleanDoctype($item.attr("data-" + attrs[i]) || $item.data(attrs[i]));
            if (value) return value;
        }

        var $withData = $item.find("[data-doctype], [data-link-doctype], [data-document-type], [data-target-doctype]").first();
        if ($withData.length) return getTargetDoctype($withData);

        var label = $item.find(".document-link-name, .document-link-title, .link-title, a").first().text();
        return cleanDoctype(label);
    }

    function cleanDoctype(value) {
        value = String(value || "").replace(/\(\s*\d+\s*\)/g, "").trim();
        return value && value.length < 80 ? value : "";
    }

    function getCountElement($item) {
        var selectors = ".badge-link, .document-link-count, .document-link-badge, .count, .badge, .indicator-pill, [data-count]";
        var $matches = $item.find(selectors).addBack(selectors).filter(function () {
            return parseCount($(this).attr("data-count") || $(this).text()) > 0;
        });
        return $matches.last();
    }

    function parseCount(value) {
        var match = String(value || "").match(/\d+/);
        return match ? parseInt(match[0], 10) || 0 : 0;
    }

    function openConnectionList(frm, targetDoctype) {
        frappe.call({
            method: METHOD,
            args: {
                source_doctype: frm.doctype,
                source_name: frm.docname || (frm.doc && frm.doc.name),
                target_doctype: targetDoctype,
            },
            freeze: true,
            freeze_message: __("Loading linked {0}...", [targetDoctype]),
        }).then(function (res) {
            var data = res.message || {};
            if (!data.count) {
                frappe.show_alert({ message: __("No linked {0} found", [targetDoctype]), indicator: "orange" });
                return;
            }
            var names = data.names || (data.route_options && data.route_options.name && data.route_options.name[1]) || [];
            if (data.count === 1 && names.length === 1) {
                clearCurrentUrlQuery();
                frappe.set_route("Form", data.target_doctype || targetDoctype, names[0]);
                return;
            }
            frappe.route_options = data.route_options || {};
            clearCurrentUrlQuery();
            frappe.set_route("List", data.target_doctype || targetDoctype, "List");
        }).catch(function () {
            frappe.show_alert({ message: __("Unable to open linked {0}", [targetDoctype]), indicator: "red" });
        });
    }

    function clearCurrentUrlQuery() {
        if (!window.history || !window.location.search) return;
        window.history.replaceState(null, "", window.location.pathname + window.location.hash);
    }

    function injectStyle() {
        if (document.getElementById("orderlift-connection-dashboard-links-style")) return;
        var style = document.createElement("style");
        style.id = "orderlift-connection-dashboard-links-style";
        style.textContent = [
            ".ol-connection-count-link{cursor:pointer!important;text-decoration:underline;text-underline-offset:2px;}",
            ".ol-connection-count-link:hover{filter:brightness(.92);}",
        ].join("\n");
        document.head.appendChild(style);
    }

    function patchFrappeDashboardClass() {
        if (!window.frappe || !frappe.ui || !frappe.ui.form || !frappe.ui.form.Dashboard) return false;
        var proto = frappe.ui.form.Dashboard.prototype;
        if (proto[DASHBOARD_PATCH_FLAG]) return true;

        var originalRenderLinks = proto.render_links;
        var originalSetBadgeCountCommon = proto.set_badge_count_common;

        proto.render_links = function () {
            var result = originalRenderLinks ? originalRenderLinks.apply(this, arguments) : undefined;
            scheduleEnhance();
            return result;
        };

        proto.set_badge_count_common = function () {
            var result = originalSetBadgeCountCommon ? originalSetBadgeCountCommon.apply(this, arguments) : undefined;
            scheduleEnhance();
            return result;
        };

        proto[DASHBOARD_PATCH_FLAG] = true;
        return true;
    }

    function bootstrap(attempts) {
        if (patchFrappeDashboardClass()) {
            scheduleEnhance();
            return;
        }
        if (attempts > 0) {
            window.setTimeout(function () {
                bootstrap(attempts - 1);
            }, 300);
        }
    }

    if (window.frappe && frappe.router && frappe.router.on) {
        frappe.router.on("change", scheduleEnhance);
    }
    $(document).on("form-refresh", scheduleEnhance);
    bootstrap(20);
})();
