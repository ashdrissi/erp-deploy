(function () {
    const PRICE_LIST_TYPE = "Buying";

    frappe.ui.form.on("Purchase Order", {
        setup(frm) {
            configureQueries(frm);
        },
        refresh(frm) {
            configureQueries(frm);
            addLoadPricesButton(frm);
            applyPurchaseTaxDefault(frm);
            if (frm.doc.supplier && !frm.__orderliftSupplierBuyingLists) {
                syncSupplierBuyingPriceLists(frm, { replaceSelection: !selectedBuyingLists(frm).length });
            }
        },
        company(frm) {
            configureQueries(frm);
            applyPurchaseTaxDefault(frm, { force: true });
            syncSupplierBuyingPriceLists(frm, { replaceSelection: true });
        },
        supplier(frm) {
            syncSupplierBuyingPriceLists(frm, { replaceSelection: true });
        },
        selected_buying_price_lists_add(frm) {
            configureQueries(frm);
        },
        selected_buying_price_lists_remove(frm) {
            syncPrimaryBuyingList(frm);
            configureQueries(frm);
            loadBuyingPrices(frm, { force: false });
        },
        before_submit(frm) {
            const pending = negotiatedRows(frm).filter((row) => !isCurrentPriceReview(row));
            if (!pending.length) return;
            frappe.validated = false;
            frappe.msgprint({
                title: __("Pricing Alerts & Approvals Required"),
                message: __("Review and approve or skip every negotiated price in the Pricing Alerts & Approvals section before submitting this Purchase Order."),
                indicator: "orange",
            });
        },
    });

    frappe.ui.form.on("Pricing Sheet Price List Selection", {
        price_list(frm) {
            if (frm.doctype !== "Purchase Order") return;
            syncPrimaryBuyingList(frm);
            configureQueries(frm);
            loadBuyingPrices(frm, { force: false });
        },
        sequence(frm) {
            if (frm.doctype !== "Purchase Order") return;
            syncPrimaryBuyingList(frm);
            configureQueries(frm);
            loadBuyingPrices(frm, { force: false });
        },
        is_active(frm) {
            if (frm.doctype !== "Purchase Order") return;
            syncPrimaryBuyingList(frm);
            configureQueries(frm);
            loadBuyingPrices(frm, { force: false });
        },
    });

    frappe.ui.form.on("Purchase Order Item", {
        item_code(frm, cdt, cdn) {
            const row = locals[cdt]?.[cdn];
            if (row?.item_code) loadBuyingPrices(frm, { force: true, itemNames: [row.name] });
        },
        qty(frm, cdt, cdn) {
            const row = locals[cdt]?.[cdn];
            if (row?.item_code) loadBuyingPrices(frm, { force: false, itemNames: [row.name] });
        },
        uom(frm, cdt, cdn) {
            const row = locals[cdt]?.[cdn];
            if (row?.item_code) loadBuyingPrices(frm, { force: false, itemNames: [row.name] });
        },
        conversion_factor(frm, cdt, cdn) {
            const row = locals[cdt]?.[cdn];
            if (row?.item_code) loadBuyingPrices(frm, { force: false, itemNames: [row.name] });
        },
        custom_source_buying_price_list(frm, cdt, cdn) {
            const row = locals[cdt]?.[cdn];
            if (row?.item_code) loadBuyingPrices(frm, { force: true, itemNames: [row.name] });
        },
    });

    function configureQueries(frm) {
        if (!frm?.set_query) return;
        const filters = buyingListFilters(frm);
        if (frm.fields_dict?.selected_buying_price_lists) {
            frm.set_query("price_list", "selected_buying_price_lists", () => ({ filters }));
        }
        if (frm.fields_dict?.items) {
            frm.set_query("custom_source_buying_price_list", "items", () => {
                const selected = selectedBuyingLists(frm);
                const sourceFilters = buyingListFilters(frm);
                if (selected.length) sourceFilters.name = ["in", selected];
                return { filters: sourceFilters };
            });
            frm.set_query("item_code", "items", () => {
                const selected = selectedBuyingLists(frm);
                if (!selected.length) return {};
                return {
                    query: "orderlift.orderlift_sales.utils.item_price_tools.item_query_for_transaction_price_list",
                    filters: {
                        price_list: selected[0],
                        price_lists: JSON.stringify(selected),
                        price_list_type: "buying",
                    },
                };
            });
        }
        syncPrimaryBuyingList(frm);
    }

    function buyingListFilters(frm) {
        const filters = { custom_price_list_type: PRICE_LIST_TYPE, buying: 1 };
        if (frm.doc.company) filters.custom_company = frm.doc.company;
        const supplierLists = frm.__orderliftSupplierBuyingLists || [];
        if (frm.doc.supplier) filters.name = ["in", supplierLists.length ? supplierLists : ["__no_supplier_price_lists__"]];
        return filters;
    }

    function selectedBuyingLists(frm) {
        return (frm.doc.selected_buying_price_lists || [])
            .filter((row) => String(row.price_list || "").trim() && Number(row.is_active ?? 1))
            .sort((left, right) => Number(left.sequence || 0) - Number(right.sequence || 0))
            .map((row) => String(row.price_list || "").trim())
            .filter((value, index, values) => values.indexOf(value) === index);
    }

    function syncPrimaryBuyingList(frm) {
        const primary = selectedBuyingLists(frm)[0] || "";
        if ((frm.doc.buying_price_list || "") === primary || frm.__orderliftSyncingPrimaryBuyingList) return;
        frm.__orderliftSyncingPrimaryBuyingList = true;
        frm.set_value("buying_price_list", primary).finally(() => {
            frm.__orderliftSyncingPrimaryBuyingList = false;
        });
    }

    async function syncSupplierBuyingPriceLists(frm, options = {}) {
        if (!frm || Number(frm.doc.docstatus || 0) !== 0 || frm.__orderliftLoadingSupplierBuyingLists) return;
        const supplier = String(frm.doc.supplier || "").trim();
        const company = String(frm.doc.company || "").trim();
        if (!supplier || !company) {
            frm.__orderliftSupplierBuyingLists = [];
            if (options.replaceSelection) {
                frm.clear_table("selected_buying_price_lists");
                syncPrimaryBuyingList(frm);
            }
            configureQueries(frm);
            return;
        }
        frm.__orderliftLoadingSupplierBuyingLists = true;
        try {
            const response = await frappe.call({
                method: "orderlift.orderlift_sales.utils.purchase_order_pricing.get_supplier_buying_price_lists",
                args: { supplier, company },
            });
            if (frm.doc.supplier !== supplier || frm.doc.company !== company) return;
            const rows = response.message || [];
            frm.__orderliftSupplierBuyingLists = rows.map((row) => String(row.price_list || "").trim()).filter(Boolean);
            if (options.replaceSelection) {
                frm.clear_table("selected_buying_price_lists");
                rows.forEach((row, index) => {
                    const child = frm.add_child("selected_buying_price_lists");
                    child.price_list = row.price_list;
                    child.sequence = (index + 1) * 10;
                    child.is_active = 1;
                });
            }
            syncPrimaryBuyingList(frm);
            configureQueries(frm);
            if (options.replaceSelection) {
                frm.refresh_field("selected_buying_price_lists");
                await loadBuyingPrices(frm, { force: false });
            }
        } catch (error) {
            console.error("Unable to load supplier buying price lists", error);
            frappe.msgprint(__("No permitted buying price lists were found for this supplier."));
        } finally {
            frm.__orderliftLoadingSupplierBuyingLists = false;
        }
    }

    function addLoadPricesButton(frm) {
        if (Number(frm.doc.docstatus || 0) !== 0) return;
        frm.add_custom_button(__("Load Buying Prices"), () => loadBuyingPrices(frm, { force: true }), __("Actions"));
    }

    async function loadBuyingPrices(frm, options = {}) {
        if (!frm || Number(frm.doc.docstatus || 0) !== 0 || frm.__orderliftLoadingBuyingPrices) return;
        const selected = selectedBuyingLists(frm);
        const items = (frm.doc.items || []).filter((row) => row.item_code && (!options.itemNames || options.itemNames.includes(row.name)));
        if (!selected.length || !items.length) return;
        frm.__orderliftLoadingBuyingPrices = true;
        try {
            syncPrimaryBuyingList(frm);
            const requestDoc = Object.assign({}, frm.doc, { items });
            const response = await frappe.call({
                method: "orderlift.orderlift_sales.utils.purchase_order_pricing.get_purchase_order_price_candidates",
                args: { doc: requestDoc },
            });
            const candidates = response.message?.rows || {};
            for (const row of items) {
                const candidate = candidates[row.name || row.idx || row.item_code];
                if (candidate) applyCandidate(row, candidate, Boolean(options.force));
            }
            frm.refresh_field("items");
        } catch (error) {
            console.error("Unable to load Purchase Order buying prices", error);
            if (options.force) frappe.msgprint(__("Some items do not have a valid price in the selected buying lists."));
        } finally {
            frm.__orderliftLoadingBuyingPrices = false;
        }
    }

    function applyCandidate(row, candidate, force) {
        const loadedBefore = Number(row.custom_loaded_buying_rate || 0);
        const currentRate = Number(row.rate || 0);
        const negotiated = loadedBefore > 0 && !sameRate(currentRate, loadedBefore);
        const loadedRate = Number(candidate.rate || 0);
        if (force || currentRate <= 0 || !negotiated) {
            frappe.model.set_value(row.doctype, row.name, "rate", loadedRate);
            frappe.model.set_value(row.doctype, row.name, "price_list_rate", loadedRate);
            frappe.model.set_value(row.doctype, row.name, "amount", loadedRate * Number(row.qty || 0));
        }
        const finalRate = force || currentRate <= 0 || !negotiated ? loadedRate : currentRate;
        setValue(row, "custom_source_buying_price_list", candidate.price_list || "");
        setValue(row, "custom_source_item_price", candidate.name || "");
        setValue(row, "custom_loaded_buying_rate", loadedRate);
        setValue(row, "custom_loaded_buying_currency", candidate.source_currency || "");
        setValue(row, "custom_loaded_buying_uom", candidate.uom || "");
        setValue(row, "custom_price_variance_amount", finalRate - loadedRate);
        setValue(row, "custom_price_variance_percent", loadedRate ? ((finalRate - loadedRate) / loadedRate) * 100 : 0);
        if (sameRate(finalRate, loadedRate)) {
            setValue(row, "custom_price_update_decision", "No Change");
            setValue(row, "custom_update_price_list_on_submit", 0);
        } else if (row.custom_price_update_decision === "No Change") {
            setValue(row, "custom_price_update_decision", "Pending");
        }
    }

    function negotiatedRows(frm) {
        return (frm.doc.items || []).filter((row) => {
            const loaded = Number(row.custom_loaded_buying_rate || 0);
            return row.item_code && loaded > 0 && !sameRate(Number(row.rate || 0), loaded);
        });
    }

    function isCurrentPriceReview(row) {
        const decision = String(row.custom_price_update_decision || "");
        return ["Approved", "Skipped"].includes(decision)
            && Boolean(row.custom_price_reviewed_by)
            && Math.abs(Number(row.custom_price_reviewed_rate || 0) - Number(row.rate || 0)) <= 0.000001
            && Math.abs(Number(row.custom_price_reviewed_loaded_rate || 0) - Number(row.custom_loaded_buying_rate || 0)) <= 0.000001;
    }

    function showPriceUpdateApproval(frm, rows) {
        const dialog = new frappe.ui.Dialog({
            title: __("Approve Negotiated Buying Prices"),
            fields: [{
                fieldname: "review",
                fieldtype: "HTML",
                options: renderApprovalRows(rows),
            }],
            primary_action_label: __("Submit Purchase Order"),
            primary_action() {
                rows.forEach((row) => {
                    const update = dialog.$wrapper.find(`[data-po-price-update="${row.name}"]`).is(":checked");
                    setValue(row, "custom_update_price_list_on_submit", update ? 1 : 0);
                    setValue(row, "custom_price_update_decision", update ? "Approved" : "Skipped");
                });
                frm.__orderliftBuyingPriceSubmissionApproved = true;
                dialog.hide();
                frm.save("Submit").finally(() => {
                    frm.__orderliftBuyingPriceSubmissionApproved = false;
                });
            },
        });
        dialog.show();
    }

    function renderApprovalRows(rows) {
        const body = rows.map((row) => {
            const loaded = frappe.format(Number(row.custom_loaded_buying_rate || 0), { fieldtype: "Currency" });
            const negotiated = frappe.format(Number(row.rate || 0), { fieldtype: "Currency" });
            const variance = frappe.format(Number(row.custom_price_variance_amount || 0), { fieldtype: "Currency" });
            return `<tr><td>${frappe.utils.escape_html(row.item_code || "")}</td><td>${frappe.utils.escape_html(row.custom_source_buying_price_list || "")}</td><td>${loaded}</td><td>${negotiated}</td><td>${variance}</td><td><input type="checkbox" data-po-price-update="${frappe.utils.escape_html(row.name)}" checked></td></tr>`;
        }).join("");
        return `<p>${__("Confirm which negotiated rates should update their selected buying price list.")}</p><table class="table table-bordered"><thead><tr><th>${__("Item")}</th><th>${__("Price List")}</th><th>${__("Loaded")}</th><th>${__("Negotiated")}</th><th>${__("Difference")}</th><th>${__("Update")}</th></tr></thead><tbody>${body}</tbody></table>`;
    }

    async function applyPurchaseTaxDefault(frm, options = {}) {
        const isNew = typeof frm?.is_new === "function" ? frm.is_new() : Boolean(frm?.doc?.__islocal);
        if (!frm?.doc?.company || frm.__orderliftLoadingPurchaseTaxDefault || (!options.force && !isNew && frm.doc.taxes_and_charges)) return;
        const company = frm.doc.company;
        frm.__orderliftLoadingPurchaseTaxDefault = true;
        try {
            const response = await frappe.call({
                method: "orderlift.orderlift_sales.utils.tax_inclusive.get_company_default_purchase_taxes_template",
                args: { company },
            });
            const template = String(response.message || "").trim();
            if (!template || frm.doc.company !== company) return;
            await frm.set_value("taxes_and_charges", template);
            if (typeof frm.cscript?.taxes_and_charges === "function") await frm.cscript.taxes_and_charges();
        } catch (error) {
            console.error("Unable to load the default Purchase Tax Template", error);
        } finally {
            frm.__orderliftLoadingPurchaseTaxDefault = false;
        }
    }

    function setValue(row, fieldname, value) {
        if (!row?.doctype || !row?.name || (frappe.meta?.has_field && !frappe.meta.has_field(row.doctype, fieldname))) return;
        frappe.model.set_value(row.doctype, row.name, fieldname, value);
    }

    function sameRate(left, right) {
        return Math.abs(Number(left || 0) - Number(right || 0)) <= 0.000001;
    }
})();
