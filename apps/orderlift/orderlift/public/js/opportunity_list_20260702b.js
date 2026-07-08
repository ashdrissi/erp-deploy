(function () {
    const existingSettings = frappe.listview_settings["Opportunity"] || {};
    const existingOnload = existingSettings.onload;
    let redirectingToReport = false;

    function isReportView(listview) {
        const route = (frappe.get_route && frappe.get_route()) || [];
        const viewName = String(listview?.view_name || listview?.view || route[2] || "").toLowerCase();
        return viewName === "report" || listview?.constructor?.name === "ReportView" || typeof listview?.build_row === "function";
    }

    function defaultOpportunityToReportView(listview) {
        if (!listview || listview.doctype !== "Opportunity" || isReportView(listview) || redirectingToReport) return;
        redirectingToReport = true;
        frappe.set_route("List", "Opportunity", "Report");
        setTimeout(function () { redirectingToReport = false; }, 300);
    }

    function useOpportunityIdAsSubject(listview) {
        if (!listview || !listview.doctype || listview.doctype !== "Opportunity") return;
        applyOpportunityListStyles(listview);

        const subject = listview.columns && listview.columns.find(function (column) { return column.type === "Subject"; });
        if (subject) {
            subject.df = { fieldname: "name", label: __("ID") };
        }
    }

    function applyOpportunityListStyles(listview) {
        if (listview && listview.page && listview.page.wrapper) {
            $(listview.page.wrapper).addClass("orderlift-opportunity-list");
        }
        if (document.getElementById("orderlift-opportunity-list-style")) return;

        $("head").append(
            "<style id=\"orderlift-opportunity-list-style\">" +
            ".orderlift-opportunity-list .list-row-col.list-subject," +
            ".orderlift-opportunity-list .list-header-subject {" +
            "flex: 0 0 250px !important;" +
            "max-width: 250px !important;" +
            "min-width: 250px;" +
            "}" +
            "</style>"
        );
    }

    function patchOpportunityColumnSetup(listview) {
        if (!listview || listview.__orderlift_opportunity_columns_patched) return;
        if (typeof listview.setup_columns !== "function") return;

        var setupColumns = listview.setup_columns.bind(listview);
        listview.setup_columns = function () {
            setupColumns();
            useOpportunityIdAsSubject(listview);
        };
        listview.__orderlift_opportunity_columns_patched = true;
    }

    frappe.listview_settings["Opportunity"] = Object.assign({}, existingSettings, {
        onload: function (listview) {
            if (typeof existingOnload === "function") existingOnload(listview);
            defaultOpportunityToReportView(listview);
            patchOpportunityColumnSetup(listview);
            useOpportunityIdAsSubject(listview);
            if (listview && typeof listview.render_header === "function") listview.render_header();
        },
    });
})();
