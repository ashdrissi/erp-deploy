(function () {
    const FORM_QUERIES = {
        Quotation: { fieldname: "selling_price_list", priceListType: "Selling", itemPriceType: "selling" },
        "Sales Order": { fieldname: "selling_price_list", priceListType: "Selling", itemPriceType: "selling" },
        "Sales Invoice": { fieldname: "selling_price_list", priceListType: "Selling", itemPriceType: "selling" },
        "Delivery Note": { fieldname: "selling_price_list", priceListType: "Selling", itemPriceType: "selling" },
        "Purchase Order": { fieldname: "buying_price_list", priceListType: "Buying", itemPriceType: "buying" },
        "Purchase Invoice": { fieldname: "buying_price_list", priceListType: "Buying", itemPriceType: "buying" },
        "Purchase Receipt": { fieldname: "buying_price_list", priceListType: "Buying", itemPriceType: "buying" },
    };

    Object.entries(FORM_QUERIES).forEach(([doctype, config]) => {
        frappe.ui.form.on(doctype, {
            setup(frm) {
                applyPriceListTypeQuery(frm, config);
                applyTransactionItemQuery(frm, config);
            },
            refresh(frm) {
                applyPriceListTypeQuery(frm, config);
                applyTransactionItemQuery(frm, config);
            },
            selling_price_list(frm) {
                applyTransactionItemQuery(frm, config);
            },
            buying_price_list(frm) {
                applyTransactionItemQuery(frm, config);
            },
        });
    });

    function applyPriceListTypeQuery(frm, config) {
        if (!frm || !frm.set_query || !config || !config.fieldname) return;
        if (!frm.fields_dict || !frm.fields_dict[config.fieldname]) return;
        frm.set_query(config.fieldname, () => ({
            filters: buildFilters(config.priceListType, frm.doc.company || frm.doc.custom_company || ""),
        }));
    }

    function buildFilters(priceListType, company) {
        const filters = { custom_price_list_type: priceListType };
        if (priceListType === "Buying") filters.buying = 1;
        if (priceListType === "Selling") filters.selling = 1;
        if (company) filters.custom_company = company;
        return filters;
    }

    function applyTransactionItemQuery(frm, config) {
        if (!frm || !frm.set_query || !config || !frm.fields_dict || !frm.fields_dict.items) return;
        frm.set_query("item_code", "items", () => {
            const priceList = (frm.doc[config.fieldname] || "").trim();
            if (!priceList) return {};
            return {
                query: "orderlift.orderlift_sales.utils.item_price_tools.item_query_for_transaction_price_list",
                filters: { price_list: priceList, price_list_type: config.itemPriceType || "selling" },
            };
        });
    }
})();
