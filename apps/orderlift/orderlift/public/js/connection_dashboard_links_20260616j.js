(function orderliftConnectionDashboardLinks() {
    if (window.__orderlift_connection_dashboard_links_20260616j_installed) return;
    window.__orderlift_connection_dashboard_links_20260616j_installed = true;

    var METHOD = "orderlift.connection_dashboard_links.get_connection_route";
    var PATCHED_ATTR = "data-orderlift-connection-link-j";
    var OBSERVER_ATTR = "data-orderlift-connection-observer-j";
    var SHORTCUT_ATTR = "data-orderlift-connection-shortcut-j";
    var DASHBOARD_PATCH_FLAG = "__orderliftConnectionDashboardLinks20260616jPatched";
    var observer = null;
    var enhanceTimer = null;

    function currentForm() {
        if (!window.cur_frm) return null;
        if (!cur_frm.doc || cur_frm.doc.__islocal) return null;
        if (!cur_frm.doctype || !(cur_frm.docname || cur_frm.doc.name)) return null;
        return cur_frm;
    }

    function scheduleEnhance() {
        window.clearTimeout(enhanceTimer);
        enhanceTimer = window.setTimeout(enhanceDashboard, 250);
    }

    function enhanceDashboard() {
        var frm = currentForm();
        if (!frm) return;

        injectStyle();
        if (frm.dashboard && frm.dashboard.wrapper) watchDashboard(frm.dashboard.wrapper);
        if (frm.wrapper) watchDashboard(frm.wrapper);

        var $wrapper = $(frm.wrapper || document);
        $wrapper.find(".form-documents .document-link, .document-link, [data-doctype], [data-link-doctype], [data-document-type]").each(function () {
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

        addShortcutChip(frm, $item, $count, targetDoctype, count);
    }

    function addShortcutChip(frm, $item, $count, targetDoctype, count) {
        if ($item.find("[" + SHORTCUT_ATTR + "]").length) return;
        var label = count === 1 ? __("Open") : __("View all");
        var title = count === 1 ? __("Open linked {0}", [targetDoctype]) : __("View linked {0}", [targetDoctype]);
        var $shortcut = $(
            '<button type="button" class="ol-connection-shortcut" ' + SHORTCUT_ATTR + '="1"></button>'
        );
        $shortcut.text(label).attr("title", title).attr("aria-label", title);
        $shortcut.on("click.orderliftConnectionShortcut", function (event) {
            event.preventDefault();
            event.stopImmediatePropagation();
            event.stopPropagation();
            openConnectionList(frm, targetDoctype);
        });
        $count.after($shortcut);
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
            ".ol-connection-shortcut{margin-left:6px;padding:2px 8px;border:1px solid #d8e0ea;border-radius:999px;background:#f8fafc;color:#334155;font-size:11px;font-weight:600;line-height:18px;cursor:pointer;vertical-align:middle;transition:background .16s ease,border-color .16s ease,color .16s ease;}",
            ".ol-connection-shortcut:hover,.ol-connection-shortcut:focus{background:#edf6ff;border-color:#93c5fd;color:#0f4c81;outline:none;}",
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

    window.setInterval(scheduleEnhance, 1500);

    if (window.frappe && frappe.router && frappe.router.on) {
        frappe.router.on("change", scheduleEnhance);
    }
    $(document).on("form-refresh", scheduleEnhance);
    bootstrap(20);
})();
