(function () {
    frappe.ui.form.on("Agent Pricing Rules", {
        setup(frm) {
            setAgentPricingQueries(frm);
        },
        refresh(frm) {
            setAgentPricingQueries(frm);
        },
    });

    function setAgentPricingQueries(frm) {
        frm.set_query("default_buying_price_list", () => ({
            filters: benchmarkOrTransactionalFilters("Buying"),
        }));
        frm.set_query("selling_price_list", "allocated_price_lists", () => ({
            filters: benchmarkOrTransactionalFilters("Selling"),
        }));
        frm.set_query("benchmark_price_list", "allocated_benchmark_price_lists", () => ({
            filters: benchmarkOrTransactionalFilters("Benchmark"),
        }));
    }

    function benchmarkOrTransactionalFilters(priceListType) {
        const filters = { custom_price_list_type: priceListType };
        if (priceListType === "Buying") filters.buying = 1;
        if (priceListType === "Selling") filters.selling = 1;
        if (frappe.defaults && frappe.defaults.get_default) {
            const company = frappe.defaults.get_default("company");
            if (company) filters.custom_company = company;
        }
        return filters;
    }
})();
