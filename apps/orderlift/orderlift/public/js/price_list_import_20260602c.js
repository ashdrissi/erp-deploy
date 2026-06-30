(function () {
    if (window.__orderlift_price_list_import_20260602c_installed) return;
    window.__orderlift_price_list_import_20260602c_installed = true;

    frappe.ui.form.on("Price List", {
        refresh(frm) {
            addItemPricesReportButton(frm);
            addDuplicateButton(frm);
            _toggle_sharing_table(frm);
            _render_sharing_info(frm);
            setTimeout(function () { _filter_company_in_sharing(frm); }, 100);
        },
        custom_price_list_type(frm) {
            if (frm.doc.docstatus !== 0) return;
            _toggle_sharing_table(frm);
        },
        custom_company(frm) {
            if (frm.doc.docstatus !== 0) return;
            _toggle_sharing_table(frm);
            setTimeout(function () { _filter_company_in_sharing(frm); }, 100);
        },
    });

    frappe.ui.form.on("Price List Sharing", {
        form_render(frm, cdt, cdn) {
            _filter_company_in_sharing(frm);
        },
        company(frm, cdt, cdn) {
            _filter_company_in_sharing(frm);
        },
    });

    function addItemPricesReportButton(frm) {
        if (frm.is_new() || !frm.doc.name) return;
        frm.add_custom_button(__("View Item Prices"), () => {
            frappe.route_options = { price_list: frm.doc.name };
            frappe.set_route("List", "Item Price", "Report");
        });
    }

    async function addDuplicateButton(frm) {
        if (frm.__orderlift_price_list_import_loading) return;
        frm.__orderlift_price_list_import_loading = true;
        try {
            const response = await frappe.call({
                method: "orderlift.orderlift_sales.utils.price_list_import.get_price_list_import_context",
            });
            const context = response.message || {};
            const label = frm.is_new() ? __("Import from Existing List") : __("Duplicate Price List");
            frm.add_custom_button(label, () => showDuplicateDialog({
                sourcePriceList: frm.is_new() ? "" : frm.doc.name,
                sourceCompany: frm.is_new() ? "" : (frm.doc.custom_company || ""),
                context,
            }));
        } catch (error) {
            console.error("Orderlift Price List import context failed", error);
            frm.add_custom_button(frm.is_new() ? __("Import from Existing List") : __("Duplicate Price List"), () => showDuplicateDialog({}));
        } finally {
            frm.__orderlift_price_list_import_loading = false;
        }
    }

    window.orderliftShowPriceListDuplicateDialog = showDuplicateDialog;

    function showDuplicateDialog(options = {}) {
        const context = options.context || {};
        const sourcePriceList = options.sourcePriceList || "";
        const sourceCompany = options.sourceCompany || "";
        const companies = context.companies || [];
        const defaultTargetCompany = context.current_company || sourceCompany || "";
        const dialog = new frappe.ui.Dialog({
            title: sourcePriceList ? __("Duplicate Price List") : __("Import from Existing List"),
            fields: [
                {
                    fieldname: "source_price_list",
                    fieldtype: "Link",
                    label: __("Source Price List"),
                    options: "Price List",
                    default: sourcePriceList,
                    read_only: sourcePriceList ? 1 : 0,
                    reqd: 1,
                },
                {
                    fieldname: "target_company",
                    fieldtype: "Link",
                    label: __("Target Company"),
                    options: "Company",
                    default: defaultTargetCompany,
                    reqd: 1,
                    get_query: () => ({ filters: companyFilters(companies) }),
                    description: __("Choose the company that will own the new Price List."),
                },
                {
                    fieldname: "target_price_list_name",
                    fieldtype: "Data",
                    label: __("New Price List Name"),
                    reqd: 1,
                    description: __("Enter a unique Price List name. No suffix is added automatically."),
                },
                {
                    fieldname: "copy_item_prices",
                    fieldtype: "Check",
                    label: __("Copy all Item Prices from the source list"),
                    default: 1,
                    read_only: 1,
                },
                {
                    fieldname: "confirm_html",
                    fieldtype: "HTML",
                    options: `<div class="text-muted" style="line-height:1.5">${frappe.utils.escape_html(__("This creates a new Price List in the target company and copies every Item Price row from the source Price List. Existing Price Lists are never overwritten."))}</div>`,
                },
            ],
            primary_action_label: __("Create Duplicate"),
            primary_action(values) {
                frappe.confirm(
                    __("Create Price List {0} for company {1} and copy all Item Prices from {2}?", [
                        values.target_price_list_name,
                        values.target_company || "-",
                        values.source_price_list || "-",
                    ]),
                    async () => {
                        const result = await duplicatePriceList(values);
                        dialog.hide();
                        if (result.price_list) {
                            frappe.set_route("Form", "Price List", result.price_list);
                        }
                    }
                );
            },
        });
        dialog.show();
    }

    function companyFilters(companies) {
        return companies.length ? { name: ["in", companies] } : {};
    }

    async function duplicatePriceList(values) {
        const response = await frappe.call({
            method: "orderlift.orderlift_sales.utils.price_list_import.import_price_list_from_existing",
            args: {
                source_price_list: values.source_price_list,
                target_price_list_name: values.target_price_list_name,
                target_company: values.target_company,
                copy_item_prices: 1,
            },
            freeze: true,
            freeze_message: __("Creating duplicate Price List..."),
        });
        const result = response.message || {};
        frappe.show_alert({
            message: __("Created {0} with {1} Item Prices.", [
                result.price_list || values.target_price_list_name,
                result.item_prices_created || 0,
            ]),
            indicator: "green",
        }, 8);
        return result;
    }

    function _toggle_sharing_table(frm) {
        const isShared = frm.doc.custom_is_shared_from && frm.doc.custom_is_shared_from.trim();
        const isSelling = frm.doc.custom_price_list_type === "Selling";
        const hasCompany = frm.doc.custom_company && frm.doc.custom_company.trim();
        const sharingField = frm.get_field("custom_price_list_sharing");
        if (!sharingField) return;
        if (!isSelling || !hasCompany || isShared) {
            sharingField.df.hidden = 1;
        } else {
            sharingField.df.hidden = 0;
        }
        sharingField.refresh();
        _filter_company_in_sharing(frm);
    }

    function _filter_company_in_sharing(frm) {
        const grid = frm.fields_dict && frm.fields_dict.custom_price_list_sharing
            && frm.fields_dict.custom_price_list_sharing.grid;
        if (!grid) return;
        const ownCompany = (frm.doc.custom_company || "").trim();
        if (grid.get_field("company")) {
            grid.get_field("company").get_query = function () {
                return {
                    filters: {
                        name: ["!=", ownCompany],
                    },
                };
            };
        }
        if (grid.get_field("shared_price_list")) {
            grid.get_field("shared_price_list").get_query = function () {
                return {
                    filters: {
                        custom_price_list_type: "Buying",
                        custom_is_shared_from: ["is", "set"],
                    },
                };
            };
        }
    }

    function _render_sharing_info(frm) {
        const sharedFrom = (frm.doc.custom_is_shared_from || "").trim();
        if (!sharedFrom) return;
        const sharedOn = frm.doc.custom_shared_on
            ? frappe.datetime.str_to_user(frm.doc.custom_shared_on)
            : frm.doc.creation
                ? frappe.datetime.str_to_user(frm.doc.creation)
                : "";
        frappe.db.get_value("Price List", sharedFrom, "custom_company", function (r) {
            const sourceCompany = (r && r.custom_company) ? r.custom_company : "";
            const html = '<div class="form-section card-section" style="margin-bottom:15px">'
                + '<div class="clearfix"><h6 class="uppercase">' + __("Sharing Info") + '</h6></div>'
                + '<div class="row"><div class="col-sm-4"><div class="form-group">'
                + '<label>' + __("Shared From") + '</label>'
                + '<div><a href="#Form/Price List/' + sharedFrom + '">' + sharedFrom + '</a></div>'
                + '</div></div>'
                + '<div class="col-sm-4"><div class="form-group">'
                + '<label>' + __("Source Company") + '</label>'
                + '<div>' + (sourceCompany || "") + '</div>'
                + '</div></div>'
                + '<div class="col-sm-4"><div class="form-group">'
                + '<label>' + __("Shared On") + '</label>'
                + '<div>' + (sharedOn || "") + '</div>'
                + '</div></div></div>';
            const sharingField = frm.get_field("custom_price_list_sharing");
            if (sharingField && sharingField.wrapper) {
                sharingField.wrapper.closest(".form-section").insertAdjacentHTML(
                    "beforebegin", html
                );
            } else if (frm.fields_dict.custom_company && frm.fields_dict.custom_company.wrapper) {
                frm.fields_dict.custom_company.wrapper.closest(".form-section").insertAdjacentHTML(
                    "afterend", html
                );
            }
        });
    }
})();
