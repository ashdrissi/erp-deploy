// Native Data Import groups consecutive child rows under the preceding parent row.
(function () {
    frappe.ui.form.off("Data Import", "show_report_error_button");

    function childRowsHelp() {
        return __(
            "<b>Importing documents with item lines:</b> Select the parent document type (for example Material Request, Purchase Order, Quotation, or Sales Order). Put parent fields and the first item on row 1. For additional items in the same document, leave every parent field blank and fill only the child-table columns. Any value in a parent field starts a new document."
        );
    }

    frappe.ui.form.on("Data Import", {
        setup(frm) {
            frm.set_query("reference_doctype", () => ({
                query: "orderlift.data_import_access.get_importable_doctypes",
            }));
        },

        refresh(frm) {
            frm.set_intro(childRowsHelp(), "blue");
        },

        show_report_error_button(frm) {
            if (frm.doc.status !== "Error" || !frappe.model.can_read("Error Log")) {
                return;
            }

            return frappe.db
                .get_list("Error Log", {
                    filters: { method: frm.doc.name },
                    fields: ["method", "error"],
                    order_by: "creation desc",
                    limit: 1,
                })
                .then((result) => {
                    if (!result.length) {
                        return;
                    }
                    frm.add_custom_button(__("Report Error"), () => {
                        const fakeXhr = {
                            responseText: JSON.stringify({ exc: result[0].error }),
                        };
                        frappe.request.report_error(fakeXhr, {});
                    });
                });
        },
    });
})();
