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

    const PRICE_OVERRIDE_ROLES = new Set(["Administrator", "System Manager", "Orderlift Admin", "Orderlift Business Admin"]);

    function canOverrideQuotationPricing() {
        var roles = frappe.user_roles || [];
        if (!roles.length && frappe.boot && frappe.boot.user && Array.isArray(frappe.boot.user.roles)) {
            return frappe.boot.user.roles.some(function (role) { return PRICE_OVERRIDE_ROLES.has(role); });
        }
        return roles.some(function (role) { return PRICE_OVERRIDE_ROLES.has(role); });
    }

    Object.entries(FORM_QUERIES).forEach(([doctype, config]) => {
        frappe.ui.form.on(doctype, {
            setup(frm) {
                applyPriceListTypeQuery(frm, config);
                applyTransactionItemQuery(frm, config);
                if (doctype === "Quotation") {
                    applyQuotationSelectedPriceListQuery(frm);
                    applyQuotationItemSourcePriceListQuery(frm);
                    clearUnselectedQuotationPrimaryPriceList(frm);
                }
            },
            refresh(frm) {
                applyPriceListTypeQuery(frm, config);
                applyTransactionItemQuery(frm, config);
                if (doctype === "Quotation") {
                    applyQuotationSelectedPriceListQuery(frm);
                    applyQuotationItemSourcePriceListQuery(frm);
                    clearUnselectedQuotationPrimaryPriceList(frm);
                    syncQuotationPrimarySellingPriceList(frm);
                    // NOTE: do NOT re-price items here. refresh() fires after every
                    // save, and refreshQuotationItemPrices() set_values rate/
                    // price_list_rate/amount, which re-dirties the form -> endless
                    // "Not Saved" loop. Re-pricing runs only on explicit price-list
                    // changes (selling_price_list / selected_selling_price_lists /
                    // per-item source_selling_price_list handlers below).
                }
            },
            selling_price_list(frm) {
                if (doctype === "Quotation") {
                    refreshQuotationItemPrices(frm);
                }
                applyTransactionItemQuery(frm, config);
            },
            buying_price_list(frm) {
                applyTransactionItemQuery(frm, config);
            },
            selected_selling_price_lists_add(frm) {
                if (doctype !== "Quotation") return;
                applyQuotationSelectedPriceListQuery(frm);
            },
            selected_selling_price_lists_remove(frm) {
                if (doctype !== "Quotation") return;
                syncQuotationPrimarySellingPriceList(frm);
                refreshQuotationItemPrices(frm);
                applyTransactionItemQuery(frm, FORM_QUERIES.Quotation);
            },
        });
    });

    frappe.ui.form.on("Pricing Sheet Price List Selection", {
        price_list(frm) {
            if (frm.doctype !== "Quotation") return;
            syncQuotationPrimarySellingPriceList(frm);
            refreshQuotationItemPrices(frm);
            applyTransactionItemQuery(frm, FORM_QUERIES.Quotation);
        },
        sequence(frm) {
            if (frm.doctype !== "Quotation") return;
            syncQuotationPrimarySellingPriceList(frm);
            refreshQuotationItemPrices(frm);
            applyTransactionItemQuery(frm, FORM_QUERIES.Quotation);
        },
        is_active(frm) {
            if (frm.doctype !== "Quotation") return;
            syncQuotationPrimarySellingPriceList(frm);
            refreshQuotationItemPrices(frm);
            applyTransactionItemQuery(frm, FORM_QUERIES.Quotation);
        },
    });

    frappe.ui.form.on("Quotation Item", {
        async item_code(frm, cdt, cdn) {
            if (!frm || frm.doctype !== "Quotation") return;
            const row = locals[cdt] && locals[cdt][cdn];
            if (!row || !row.item_code) return;
            await resolveQuotationItemPrice(frm, row);
        },
        async source_selling_price_list(frm, cdt, cdn) {
            if (!frm || frm.doctype !== "Quotation") return;
            const row = locals[cdt] && locals[cdt][cdn];
            if (!row || !row.item_code || !row.source_selling_price_list) return;
            await resolveQuotationItemPrice(frm, row, { priceLists: [row.source_selling_price_list] });
        },
    });

    function applyPriceListTypeQuery(frm, config) {
        if (!frm || !frm.set_query || !config || !config.fieldname) return;
        if (!frm.fields_dict || !frm.fields_dict[config.fieldname]) return;
        frm.set_query(config.fieldname, () => ({
            filters: buildFilters(config.priceListType, frm.doc.company || frm.doc.custom_company || ""),
        }));
    }

    function applyQuotationSelectedPriceListQuery(frm) {
        if (!frm || !frm.set_query || !frm.fields_dict || !frm.fields_dict.selected_selling_price_lists) return;
        frm.set_query("price_list", "selected_selling_price_lists", () => ({
            filters: buildFilters("Selling", frm.doc.company || frm.doc.custom_company || ""),
        }));
    }

    function applyQuotationItemSourcePriceListQuery(frm) {
        if (!frm || !frm.set_query || !frm.fields_dict || !frm.fields_dict.items) return;
        frm.set_query("source_selling_price_list", "items", () => {
            const priceLists = quotationSelectedPriceLists(frm);
            const filters = buildFilters("Selling", frm.doc.company || frm.doc.custom_company || "");
            if (priceLists.length) filters.name = ["in", priceLists];
            return { filters };
        });
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
            const priceLists = transactionPriceLists(frm, config);
            if (!priceLists.length) return {};
            return {
                query: "orderlift.orderlift_sales.utils.item_price_tools.item_query_for_transaction_price_list",
                filters: {
                    price_list: priceLists[0],
                    price_lists: JSON.stringify(priceLists),
                    price_list_type: config.itemPriceType || "selling",
                },
            };
        });
    }

    function transactionPriceLists(frm, config) {
        if (frm.doctype === "Quotation") {
            const selected = quotationSelectedPriceLists(frm);
            if (selected.length) return selected;
        }
        const priceList = String(frm.doc[config.fieldname] || "").trim();
        return priceList ? [priceList] : [];
    }

    function quotationSelectedPriceLists(frm) {
        return (frm.doc.selected_selling_price_lists || [])
            .filter((row) => String(row.price_list || "").trim() && cint(row.is_active) !== 0)
            .sort((left, right) => Number(left.sequence || 0) - Number(right.sequence || 0))
            .map((row) => String(row.price_list || "").trim())
            .filter((value, index, arr) => value && arr.indexOf(value) === index);
    }

    function clearUnselectedQuotationPrimaryPriceList(frm) {
        if (!frm || frm.doctype !== "Quotation") return;
        if (quotationSelectedPriceLists(frm).length) return;
        if (!String(frm.doc.selling_price_list || "").trim()) return;
        frm.__orderlift_syncing_primary_selling_price_list = true;
        frm.set_value("selling_price_list", "").finally(() => {
            frm.__orderlift_syncing_primary_selling_price_list = false;
        });
    }

    function syncQuotationPrimarySellingPriceList(frm) {
        if (!frm || frm.doctype !== "Quotation") return;
        const selected = quotationSelectedPriceLists(frm);
        const primary = selected[0] || "";
        if ((frm.doc.selling_price_list || "") === primary) return;
        frm.__orderlift_syncing_primary_selling_price_list = true;
        frm.set_value("selling_price_list", primary).finally(() => {
            frm.__orderlift_syncing_primary_selling_price_list = false;
        });
    }

    async function refreshQuotationItemPrices(frm) {
        if (!frm || frm.doctype !== "Quotation") return;
        if (Number(frm.doc.docstatus || 0) !== 0) return;
        const itemCodes = (frm.doc.items || []).map((row) => String(row.item_code || "").trim()).filter(Boolean);
        const priceLists = quotationSelectedPriceLists(frm);
        if (!itemCodes.length || !priceLists.length) return;
        try {
            const res = await frappe.call({
                method: "orderlift.orderlift_sales.utils.item_price_tools.get_transaction_item_prices",
                args: {
                    item_codes: JSON.stringify(itemCodes),
                    price_lists: JSON.stringify(priceLists),
                    price_list_type: "selling",
                },
            });
            const rows = (res.message || {}).rows || {};
            for (const row of frm.doc.items || []) {
                if (!row.item_code || !rows[row.item_code]) continue;
                applyResolvedQuotationPrice(frm, row, rows[row.item_code]);
            }
            frm.refresh_field("items");
        } catch (error) {
            console.error("Unable to refresh Quotation item prices", error);
        }
    }

    async function resolveQuotationItemPrice(frm, row, options = {}) {
        const priceLists = options.priceLists || quotationSelectedPriceLists(frm);
        if (!priceLists.length) return;
        try {
            const res = await frappe.call({
                method: "orderlift.orderlift_sales.utils.item_price_tools.get_transaction_item_prices",
                args: {
                    item_codes: JSON.stringify([row.item_code]),
                    price_lists: JSON.stringify(priceLists),
                    price_list_type: "selling",
                },
            });
            const payload = ((res.message || {}).rows || {})[row.item_code];
            if (!payload) return;
            applyResolvedQuotationPrice(frm, row, payload);
            frm.refresh_field("items");
        } catch (error) {
            console.error("Unable to resolve Quotation item price", error);
        }
    }

    function applyResolvedQuotationPrice(frm, row, payload) {
        const rate = Number(payload.price_list_rate || 0);
        const qty = Number(row.qty || 1) || 1;
        const maxDiscount = Number(payload.max_discount_percent || 0);
        const commissionRate = Number(payload.commission_rate || 0);
        const isAdminOverride = canOverrideQuotationPricing();
        let netRate = 0;
        let discount = Number(row.source_discount_percent || row.discount_percentage || 0);
        if (!Number.isFinite(discount) || discount < 0) discount = 0;
        netRate = rate * (1 - discount / 100);
        if (!isAdminOverride) {
            const floor = rate * (1 - maxDiscount / 100);
            if (netRate + 0.000001 < floor) netRate = floor;
        }
        discount = rate > 0 ? Math.max((1 - netRate / rate) * 100, 0) : 0;
        if (!isAdminOverride && discount > maxDiscount) {
            discount = maxDiscount;
            netRate = rate * (1 - discount / 100);
        }
        const commissionAmount = commissionFor(rate, qty, discount, maxDiscount, commissionRate, netRate);
        beginQuotationPriceMutation(frm);
        try {
            frappe.model.set_value(row.doctype, row.name, "price_list_rate", rate);
            frappe.model.set_value(row.doctype, row.name, "rate", netRate);
            frappe.model.set_value(row.doctype, row.name, "amount", netRate * qty);
            if ("discount_percentage" in row) row.discount_percentage = discount;
            setChildValue(row, "source_selling_price_list", payload.price_list || "");
            setChildValue(row, "source_price_list_sell_rate", rate);
            setChildValue(row, "source_gross_sell_rate", rate);
            setChildValue(row, "source_max_discount_percent", maxDiscount);
            setChildValue(row, "source_discount_percent", discount);
            setChildValue(row, "source_discount_amount", Math.max(rate - netRate, 0));
            setChildValue(row, "source_discounted_sell_rate", netRate);
            setChildValue(row, "source_commission_rate", commissionRate);
            setChildValue(row, "source_commission_amount", commissionAmount);
            if (frm.doc.selling_price_list !== payload.price_list && payload.price_list) {
                const selected = quotationSelectedPriceLists(frm);
                if (!selected.length) frm.set_value("selling_price_list", payload.price_list);
            }
        } finally {
            endQuotationPriceMutation(frm);
        }
    }

    function beginQuotationPriceMutation(frm) {
        if (frm) frm.__orderlift_applying_quotation_price = true;
    }

    function endQuotationPriceMutation(frm) {
        window.setTimeout(function () {
            if (frm) frm.__orderlift_applying_quotation_price = false;
        }, 0);
    }

    function setChildValue(row, fieldname, value) {
        if (!row || !row.doctype || !row.name || !childFieldExists(row.doctype, fieldname)) return;
        frappe.model.set_value(row.doctype, row.name, fieldname, value);
    }

    function childFieldExists(doctype, fieldname) {
        if (!frappe.meta || !frappe.meta.has_field) return true;
        return Boolean(frappe.meta.has_field(doctype, fieldname));
    }

    function commissionFor(priceListRate, qty, discountPercent, maxDiscountPercent, commissionRate, actualUnitPrice) {
        const listRate = Number(priceListRate || 0);
        const actualRate = Number(actualUnitPrice || 0);
        const quantity = Number(qty || 1) || 1;
        const effectiveDiscount = listRate > 0 && actualRate < listRate ? Math.max((1 - actualRate / listRate) * 100, 0) : Number(discountPercent || 0);
        const unusedDiscount = Math.max(Number(maxDiscountPercent || 0) - effectiveDiscount, 0);
        const baseCommission = listRate * quantity * (unusedDiscount / 100) * (Number(commissionRate || 0) / 100);
        const upliftCommission = Math.max(actualRate - listRate, 0) * quantity * 0.2;
        return baseCommission + upliftCommission;
    }

    function cint(value) {
        return Number(value || 0);
    }
})();
