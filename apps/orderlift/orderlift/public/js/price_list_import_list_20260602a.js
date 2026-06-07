(function () {
    const settings = frappe.listview_settings["Price List"] = frappe.listview_settings["Price List"] || {};
    settings.add_fields = Array.from(new Set([...(settings.add_fields || []), "custom_pricing_builder", "custom_company", "buying", "selling"]));
    settings.formatters = Object.assign({}, settings.formatters || {}, {
        custom_pricing_builder(value, df, doc) {
            return priceListSourceHtml(doc || { custom_pricing_builder: value });
        },
    });
    settings.get_indicator = function (doc) {
        const builder = String((doc || {}).custom_pricing_builder || "").trim();
        if (builder) return [__("Builder: {0}", [builder]), "blue", `custom_pricing_builder,=,${builder}`];
        return [__("Manual"), "gray", "custom_pricing_builder,is,not set"];
    };

    settings.onload = function (listview) {
        listview.page.add_inner_button(__("Duplicate Price List"), async () => {
            const checked = typeof listview.get_checked_items === "function" ? listview.get_checked_items() : [];
            const sourcePriceList = checked.length === 1 ? checked[0].name : "";
            let context = {};
            try {
                const response = await frappe.call({
                    method: "orderlift.orderlift_sales.utils.price_list_import.get_price_list_import_context",
                });
                context = response.message || {};
            } catch (error) {
                console.error("Orderlift Price List import context failed", error);
            }
            showDuplicateDialog(sourcePriceList, context);
        });
    };

    function priceListSourceHtml(doc) {
        const builder = String((doc || {}).custom_pricing_builder || "").trim();
        if (!builder) return `<span class="indicator-pill gray">${frappe.utils.escape_html(__("Manual"))}</span>`;
        return `<span class="indicator-pill blue">${frappe.utils.escape_html(__("Builder"))}: ${frappe.utils.escape_html(builder)}</span>`;
    }

    function showDuplicateDialog(sourcePriceList, context) {
        const companies = context.companies || [];
        const dialog = new frappe.ui.Dialog({
            title: sourcePriceList ? __("Duplicate Price List") : __("Import from Existing List"),
            fields: [
                {
                    fieldname: "source_price_list",
                    fieldtype: "Link",
                    label: __("Source Price List"),
                    options: "Price List",
                    default: sourcePriceList || "",
                    reqd: 1,
                },
                {
                    fieldname: "target_company",
                    fieldtype: "Link",
                    label: __("Target Company"),
                    options: "Company",
                    default: context.current_company || "",
                    reqd: 1,
                    get_query: () => ({ filters: companies.length ? { name: ["in", companies] } : {} }),
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
