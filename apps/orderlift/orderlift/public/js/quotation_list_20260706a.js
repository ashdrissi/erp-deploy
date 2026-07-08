(function () {
    const existingSettings = frappe.listview_settings["Quotation"] || {};
    const existingOnload = existingSettings.onload;

    function isReportView(listview) {
        const route = (frappe.get_route && frappe.get_route()) || [];
        const viewName = String(listview?.view_name || listview?.view || route[2] || "").toLowerCase();
        return viewName === "report" || listview?.constructor?.name === "ReportView" || typeof listview?.build_row === "function";
    }

    function fieldColumn(fieldname, label) {
        const df = frappe.meta.get_docfield("Quotation", fieldname) || { fieldname, label: label || fieldname };
        return { type: "Field", df };
    }

    function useQuotationIdAsSubject(listview) {
        if (!listview || !listview.doctype || listview.doctype !== "Quotation" || isReportView(listview)) return;
        applyQuotationListStyles(listview);

        const configuredColumns = configuredListColumns(listview);
        if (configuredColumns.length) {
            listview.columns = configuredColumns;
            return;
        }

        const subject = listview.columns && listview.columns.find((column) => column.type === "Subject");
        if (subject) {
            subject.df = { fieldname: "name", label: __("ID") };
        }
        listview.columns = (listview.columns || []).filter((column) => {
            return !(column.type === "Field" && column.df && column.df.fieldname === "name");
        });
    }

    function configuredListColumns(listview) {
        const fields = configuredListFields(listview);
        if (!fields.length) return [];

        const columns = [
            { type: "Subject", df: { fieldname: "name", label: __("ID") } },
            { type: "Tag" },
        ];
        fields.forEach((field) => {
            const fieldname = field.fieldname;
            if (!fieldname || fieldname === "name") return;
            if (fieldname === "status_field") {
                columns.push({ type: "Status" });
                return;
            }
            columns.push(fieldColumn(fieldname, field.label));
        });
        return columns;
    }

    function configuredListFields(listview) {
        if (!listview || !listview.list_view_settings || !listview.list_view_settings.fields) return [];
        try {
            return JSON.parse(listview.list_view_settings.fields) || [];
        } catch (error) {
            console.warn("Unable to parse Quotation List View Settings fields", error);
            return [];
        }
    }

    function applyQuotationListStyles(listview) {
        if (listview && listview.page && listview.page.wrapper) {
            $(listview.page.wrapper).addClass("orderlift-quotation-list");
        }
        if (document.getElementById("orderlift-quotation-list-style")) return;

        $("head").append(`
            <style id="orderlift-quotation-list-style">
                .orderlift-quotation-list .list-row-col.list-subject,
                .orderlift-quotation-list .list-header-subject {
                    flex: 0 0 250px !important;
                    max-width: 250px !important;
                    min-width: 250px;
                }
                .orderlift-quotation-list .list-row-col.opportunity {
                    flex: 0 0 230px !important;
                    max-width: 230px !important;
                    min-width: 230px;
                }
                .orderlift-quotation-list .list-subject a,
                .orderlift-quotation-list .list-row-col.opportunity a,
                .orderlift-quotation-list .list-row-col.opportunity .ellipsis {
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }
            </style>
        `);
    }

    function patchQuotationColumnSetup(listview) {
        if (!listview || isReportView(listview) || listview.__orderlift_quotation_columns_patched) return;
        if (typeof listview.setup_columns !== "function") return;

        const setupColumns = listview.setup_columns.bind(listview);
        listview.setup_columns = function () {
            setupColumns();
            useQuotationIdAsSubject(listview);
        };
        listview.__orderlift_quotation_columns_patched = true;
    }

    frappe.listview_settings["Quotation"] = Object.assign({}, existingSettings, {
        onload(listview) {
            if (typeof existingOnload === "function") existingOnload(listview);
            if (isReportView(listview)) return;
            patchQuotationColumnSetup(listview);
            useQuotationIdAsSubject(listview);
            if (listview && typeof listview.render_header === "function") listview.render_header();
        },
    });
})();
