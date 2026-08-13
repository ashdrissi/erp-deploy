(function () {
    function buyingPriceListFilters(frm) {
        const filters = { enabled: 1, custom_price_list_type: "Buying" };
        if (frm.doc.company) filters.custom_company = frm.doc.company;
        return filters;
    }

    frappe.ui.form.on("Purchase Agent Rules", {
        setup(frm) {
            frm.set_query("purchase_user", () => ({ filters: { enabled: 1, user_type: "System User" } }));
            frm.set_query("buying_price_list", "allowed_buying_price_lists", () => ({ filters: buyingPriceListFilters(frm) }));
        },
        company(frm) {
            frm.refresh_field("allowed_buying_price_lists");
        },
    });
})();
