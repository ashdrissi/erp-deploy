(function () {
    if (window.__orderlift_price_list_import_20260602c_installed) return;
    window.__orderlift_price_list_import_20260602c_installed = true;

    frappe.ui.form.on("Price List", {
        refresh(frm) {
            addItemPricesReportButton(frm);
            addDuplicateButton(frm);
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
})();
