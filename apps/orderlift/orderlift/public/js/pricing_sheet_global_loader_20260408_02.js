(function () {
    var LATEST_SCRIPT = "/assets/orderlift/js/pricing_sheet_form_20260406_46.js?v=20260408-global-loader-02";
    var FLAG = "__orderlift_pricing_sheet_latest_loaded_v2";

    function isPricingSheetRoute() {
        var route = (frappe.get_route && frappe.get_route()) || [];
        return route[0] === "Form" && route[1] === "Pricing Sheet";
    }

    function refreshCurrentPricingSheet() {
        if (window.cur_frm && cur_frm.doctype === "Pricing Sheet") {
            try {
                cur_frm.refresh();
            } catch (e) {
                // no-op
            }
        }
    }

    function ensureLatestPricingSheetWorkspace() {
        if (!isPricingSheetRoute()) {
            return;
        }

        if (window[FLAG]) {
            setTimeout(refreshCurrentPricingSheet, 50);
            setTimeout(refreshCurrentPricingSheet, 300);
            return;
        }

        window[FLAG] = true;
        frappe.require([LATEST_SCRIPT], function () {
            setTimeout(refreshCurrentPricingSheet, 50);
            setTimeout(refreshCurrentPricingSheet, 300);
            setTimeout(refreshCurrentPricingSheet, 800);
        });
    }

    $(document).on("app_ready route-change", function () {
        setTimeout(ensureLatestPricingSheetWorkspace, 50);
        setTimeout(ensureLatestPricingSheetWorkspace, 250);
        setTimeout(ensureLatestPricingSheetWorkspace, 700);
    });

    setTimeout(ensureLatestPricingSheetWorkspace, 250);
})();
