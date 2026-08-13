(function () {
    const PRICE_LIST_TYPE = "Buying";

    frappe.ui.form.on("Purchase Order", {
        setup(frm) {
            configureQueries(frm);
            hideRedundantNativePriceListCurrency(frm);
            frm.__orderliftPreviousCurrency = frm.doc.currency || "";
            loadPurchasePriceAccess(frm);
        },
        refresh(frm) {
            configureQueries(frm);
            hideRedundantNativePriceListCurrency(frm);
            addLoadPricesButton(frm);
            frm.__orderliftPreviousCurrency = frm.doc.currency || frm.__orderliftPreviousCurrency || "";
            if (frm.doc.supplier && !frm.__orderliftSupplierBuyingLists) {
                syncSupplierBuyingPriceLists(frm, { replaceSelection: !selectedBuyingLists(frm).length });
            }
        },
        company(frm) {
            clearRowSourceLocks(frm);
            hideRedundantNativePriceListCurrency(frm);
            configureQueries(frm);
            syncSupplierBuyingPriceLists(frm, { replaceSelection: true });
        },
        supplier(frm) {
            clearRowSourceLocks(frm);
            hideRedundantNativePriceListCurrency(frm);
            syncSupplierBuyingPriceLists(frm, { replaceSelection: true });
        },
        buying_price_list(frm) {
            hideRedundantNativePriceListCurrency(frm);
        },
        currency(frm) {
            hideRedundantNativePriceListCurrency(frm);
            handlePurchaseCurrencyChange(frm);
        },
        transaction_date(frm) {
            hideRedundantNativePriceListCurrency(frm);
            syncSupplierBuyingPriceLists(frm, { replaceSelection: false, reloadPrices: true });
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
        async price_list(frm, cdt, cdn) {
            if (frm.doctype !== "Purchase Order") return;
            const selectedRow = locals[cdt]?.[cdn];
            if (selectedRow) {
                selectedRow.source_currency = "";
                selectedRow.exchange_rate = 0;
                selectedRow.exchange_rate_source = "System";
            }
            await syncSupplierBuyingPriceLists(frm, { replaceSelection: false });
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
        exchange_rate(frm, cdt, cdn) {
            if (frm.doctype !== "Purchase Order" || frm.__orderliftSyncingExchangeRates) return;
            handleManualExchangeRate(frm, locals[cdt]?.[cdn]);
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
            if (!row?.item_code) return;
            setValue(row, "custom_lock_buying_price_source", row.custom_source_buying_price_list ? 1 : 0);
            clearBuyingPriceSourceSnapshot(row);
            loadBuyingPrices(frm, { force: true, itemNames: [row.name] });
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
            hideRedundantNativePriceListCurrency(frm);
        });
    }

    async function syncSupplierBuyingPriceLists(frm, options = {}) {
        if (!frm || Number(frm.doc.docstatus || 0) !== 0) return;
        const supplier = String(frm.doc.supplier || "").trim();
        const company = String(frm.doc.company || "").trim();
        const targetCurrency = String(frm.doc.currency || "").trim();
        const referenceDate = frm.doc.transaction_date || frappe.datetime.nowdate();
        const requestId = Number(frm.__orderliftSupplierListRequestId || 0) + 1;
        frm.__orderliftSupplierListRequestId = requestId;
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
                args: {
                    supplier,
                    company,
                    target_currency: targetCurrency,
                    reference_date: referenceDate,
                },
            });
            if (
                frm.__orderliftSupplierListRequestId !== requestId
                || frm.doc.supplier !== supplier
                || frm.doc.company !== company
                || String(frm.doc.currency || "").trim() !== targetCurrency
                || (frm.doc.transaction_date || frappe.datetime.nowdate()) !== referenceDate
            ) return;
            const rows = response.message || [];
            frm.__orderliftSupplierBuyingLists = rows.map((row) => String(row.price_list || "").trim()).filter(Boolean);
            frm.__orderliftSyncingExchangeRates = true;
            if (options.replaceSelection) {
                frm.clear_table("selected_buying_price_lists");
                rows.forEach((row, index) => {
                    const child = frm.add_child("selected_buying_price_lists");
                    child.price_list = row.price_list;
                    child.source_currency = row.source_currency || "";
                    child.exchange_rate = Number(row.exchange_rate || 0);
                    child.exchange_rate_source = row.exchange_rate_source || "System";
                    child.sequence = (index + 1) * 10;
                    child.is_active = 1;
                });
            } else {
                const details = Object.fromEntries(rows.map((row) => [row.price_list, row]));
                (frm.doc.selected_buying_price_lists || []).forEach((child) => {
                    const source = details[child.price_list];
                    if (!source) return;
                    child.source_currency = source.source_currency || "";
                    if (child.exchange_rate_source !== "Manual") {
                        child.exchange_rate = Number(source.exchange_rate || 0);
                        child.exchange_rate_source = "System";
                    }
                });
            }
            frm.__orderliftSyncingExchangeRates = false;
            syncPrimaryBuyingList(frm);
            hideRedundantNativePriceListCurrency(frm);
            configureQueries(frm);
            frm.refresh_field("selected_buying_price_lists");
            if (options.replaceSelection || options.reloadPrices) {
                await loadBuyingPrices(frm, { force: false });
            }
        } catch (error) {
            console.error("Unable to load supplier buying price lists", error);
            frappe.msgprint(__("No permitted buying price lists were found for this supplier."));
        } finally {
            if (frm.__orderliftSupplierListRequestId === requestId) {
                frm.__orderliftSyncingExchangeRates = false;
                frm.__orderliftLoadingSupplierBuyingLists = false;
            }
        }
    }

    function addLoadPricesButton(frm) {
        if (Number(frm.doc.docstatus || 0) !== 0) return;
        frm.add_custom_button(__("Load Buying Prices"), () => loadBuyingPrices(frm, { force: true }), __("Actions"));
    }

    function hideRedundantNativePriceListCurrency(frm) {
        const apply = () => {
            ["price_list_currency", "plc_conversion_rate"].forEach((fieldname) => {
                if (!frm.fields_dict?.[fieldname]) return;
                frm.set_df_property(fieldname, "hidden", 1);
                frm.toggle_display(fieldname, false);
            });
        };
        apply();
        clearTimeout(frm.__orderliftHideNativePriceListCurrencyTimer);
        frm.__orderliftHideNativePriceListCurrencyTimer = setTimeout(apply, 300);
    }

    async function loadBuyingPrices(frm, options = {}) {
        if (!frm || Number(frm.doc.docstatus || 0) !== 0) return;
        const selected = selectedBuyingLists(frm);
        const items = (frm.doc.items || []).filter((row) => row.item_code && (!options.itemNames || options.itemNames.includes(row.name)));
        if (!selected.length || !items.length) return;
        frm.__orderliftBuyingPriceRequestIds = frm.__orderliftBuyingPriceRequestIds || {};
        const requestTokens = {};
        items.forEach((row) => {
            const key = row.name || row.idx || row.item_code;
            const token = Number(frm.__orderliftBuyingPriceRequestIds[key] || 0) + 1;
            frm.__orderliftBuyingPriceRequestIds[key] = token;
            requestTokens[key] = token;
        });
        const signature = buyingPriceRequestSignature(frm, items);
        frm.__orderliftLoadingBuyingPrices = true;
        try {
            syncPrimaryBuyingList(frm);
            const requestDoc = Object.assign({}, frm.doc, { items });
            const response = await frappe.call({
                method: "orderlift.orderlift_sales.utils.purchase_order_pricing.get_purchase_order_price_candidates",
                args: { doc: requestDoc },
            });
            if (
                !Object.entries(requestTokens).every(
                    ([key, token]) => frm.__orderliftBuyingPriceRequestIds[key] === token
                )
                || buyingPriceRequestSignature(frm, items) !== signature
            ) return;
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
            if (Object.entries(requestTokens).every(
                ([key, token]) => frm.__orderliftBuyingPriceRequestIds[key] === token
            )) {
                frm.__orderliftLoadingBuyingPrices = false;
            }
        }
    }

    function applyCandidate(row, candidate, force) {
        const loadedBefore = Number(row.custom_loaded_buying_rate || 0);
        const currentRate = Number(row.rate || 0);
        const negotiated = loadedBefore > 0 && !sameRate(currentRate, loadedBefore);
        const loadedRate = roundRateForRow(candidate.rate, row);
        if (force || currentRate <= 0 || !negotiated) {
            frappe.model.set_value(row.doctype, row.name, "rate", loadedRate);
            frappe.model.set_value(row.doctype, row.name, "amount", loadedRate * Number(row.qty || 0));
        }
        frappe.model.set_value(row.doctype, row.name, "price_list_rate", loadedRate);
        const finalRate = force || currentRate <= 0 || !negotiated ? loadedRate : currentRate;
        row.custom_source_buying_price_list = candidate.price_list || "";
        setValue(row, "custom_source_item_price", candidate.name || "");
        setValue(row, "custom_source_buying_rate", Number(candidate.source_rate || 0));
        setValue(row, "custom_loaded_buying_rate", loadedRate);
        setValue(row, "custom_loaded_buying_currency", candidate.source_currency || "");
        setValue(row, "custom_loaded_buying_uom", candidate.uom || "");
        setValue(row, "custom_price_variance_amount", finalRate - loadedRate);
        setValue(row, "custom_price_variance_percent", loadedRate ? ((finalRate - loadedRate) / loadedRate) * 100 : 0);
        if (sameRate(finalRate, loadedRate)) {
            setValue(row, "custom_price_update_decision", "No Change");
            setValue(row, "custom_update_price_list_on_submit", 0);
        } else if (!sameRate(loadedBefore, loadedRate) || row.custom_price_update_decision === "No Change") {
            setValue(row, "custom_price_update_decision", "Pending");
            clearPriceReview(row);
        }
    }

    async function loadPurchasePriceAccess(frm) {
        try {
            const response = await frappe.call({
                method: "orderlift.orderlift_sales.utils.purchase_order_pricing.get_purchase_price_approval_access",
            });
            frm.__orderliftCanOverrideExchangeRate = Boolean(response.message?.can_override_exchange_rate);
        } catch (error) {
            frm.__orderliftCanOverrideExchangeRate = false;
        }
    }

    async function handleManualExchangeRate(frm, row) {
        if (!row?.price_list) return;
        if (frm.__orderliftCanOverrideExchangeRate === undefined) await loadPurchasePriceAccess(frm);
        if (!frm.__orderliftCanOverrideExchangeRate) {
            frappe.msgprint(__("Only Purchase Managers or privileged pricing users can override buying-list exchange rates."));
            await syncSupplierBuyingPriceLists(frm, { replaceSelection: false, reloadPrices: true });
            return;
        }
        const rate = Number(row.exchange_rate || 0);
        if (rate <= 0) {
            frappe.msgprint(__("Exchange Rate must be greater than zero."));
            return;
        }
        frm.__orderliftSyncingExchangeRates = true;
        (frm.doc.selected_buying_price_lists || []).forEach((candidate) => {
            if (candidate.source_currency !== row.source_currency) return;
            candidate.exchange_rate = rate;
            candidate.exchange_rate_source = "Manual";
        });
        frm.__orderliftSyncingExchangeRates = false;
        frm.refresh_field("selected_buying_price_lists");
        await loadBuyingPrices(frm, { force: false });
    }

    function handlePurchaseCurrencyChange(frm) {
        if (frm.__orderliftRestoringCurrency) return;
        const previousCurrency = String(frm.__orderliftPreviousCurrency || "").trim();
        const nextCurrency = String(frm.doc.currency || "").trim();
        if (!previousCurrency || !nextCurrency || previousCurrency === nextCurrency) {
            frm.__orderliftPreviousCurrency = nextCurrency;
            syncSupplierBuyingPriceLists(frm, { replaceSelection: false, reloadPrices: true });
            return;
        }
        const applyChange = async () => {
            try {
                negotiatedRows(frm).forEach((row) => {
                    clearPriceReview(row);
                    setValue(row, "custom_price_update_decision", "Pending");
                });
                (frm.doc.selected_buying_price_lists || []).forEach((row) => {
                    row.exchange_rate_source = "System";
                });
                frm.__orderliftPreviousCurrency = nextCurrency;
                await syncSupplierBuyingPriceLists(frm, { replaceSelection: false, reloadPrices: true });
                if (typeof frm.cscript?.calculate_taxes_and_totals === "function") {
                    frm.cscript.calculate_taxes_and_totals();
                }
            } catch (error) {
                console.error("Unable to change Purchase Order currency", error);
                restoreCurrency(frm, previousCurrency);
            }
        };
        if (!(frm.doc.items || []).some((row) => row.item_code)) {
            applyChange();
            return;
        }
        frappe.confirm(
            __("Changing purchasing currency will refresh source exchange rates, reprice loaded references, and clear existing price approvals. Continue?"),
            applyChange,
            () => restoreCurrency(frm, previousCurrency),
        );
    }

    function restoreCurrency(frm, currency) {
        frm.__orderliftRestoringCurrency = true;
        frm.set_value("currency", currency).finally(() => {
            frm.__orderliftRestoringCurrency = false;
            frm.__orderliftPreviousCurrency = currency;
        });
    }

    function clearPriceReview(row) {
        setValue(row, "custom_update_price_list_on_submit", 0);
        setValue(row, "custom_price_reviewed_by", "");
        setValue(row, "custom_price_reviewed_on", "");
        setValue(row, "custom_price_reviewed_rate", 0);
        setValue(row, "custom_price_reviewed_loaded_rate", 0);
        setValue(row, "custom_price_reviewed_source_buying_price_list", "");
        setValue(row, "custom_price_reviewed_source_currency", "");
        setValue(row, "custom_price_review_attestation", 0);
    }

    function clearBuyingPriceSourceSnapshot(row) {
        setValue(row, "custom_source_item_price", "");
        setValue(row, "custom_source_buying_rate", 0);
        setValue(row, "custom_loaded_buying_rate", 0);
        setValue(row, "custom_loaded_buying_currency", "");
        setValue(row, "custom_loaded_buying_uom", row.uom || "");
        setValue(row, "custom_price_variance_amount", 0);
        setValue(row, "custom_price_variance_percent", 0);
        setValue(row, "custom_price_update_decision", "Pending");
        clearPriceReview(row);
    }

    function clearRowSourceLocks(frm) {
        (frm.doc.items || []).forEach((row) => {
            row.custom_lock_buying_price_source = 0;
            row.custom_source_buying_price_list = "";
            row.custom_source_item_price = "";
        });
        frm.refresh_field("items");
    }

    function buyingPriceRequestSignature(frm, rows) {
        return JSON.stringify({
            supplier: frm.doc.supplier || "",
            company: frm.doc.company || "",
            currency: frm.doc.currency || "",
            transaction_date: frm.doc.transaction_date || "",
            lists: (frm.doc.selected_buying_price_lists || []).map((row) => [
                row.price_list || "",
                Number(row.is_active ?? 1),
                Number(row.sequence || 0),
                Number(row.exchange_rate || 0),
                row.exchange_rate_source || "",
            ]),
            items: rows.map((row) => [
                row.name || "",
                row.item_code || "",
                row.uom || "",
                row.stock_uom || "",
                Number(row.qty || 0),
                Number(row.conversion_factor || 0),
                row.custom_source_buying_price_list || "",
                Number(row.custom_lock_buying_price_source || 0),
            ]),
        });
    }

    function roundRateForRow(value, row) {
        const digits = typeof precision === "function" ? precision("rate", row) : 9;
        return typeof flt === "function" ? flt(value || 0, digits) : Number(Number(value || 0).toFixed(digits));
    }

    function negotiatedRows(frm) {
        return (frm.doc.items || []).filter((row) => {
            const loaded = Number(row.custom_loaded_buying_rate || 0);
            const manualNew = row.item_code
                && Number(row.rate || 0) > 0
                && loaded <= 0
                && !String(row.custom_source_item_price || "").trim();
            return row.item_code && ((loaded > 0 && !sameRate(Number(row.rate || 0), loaded)) || manualNew);
        });
    }

    function isCurrentPriceReview(row) {
        const decision = String(row.custom_price_update_decision || "");
        return ["Approved", "Skipped"].includes(decision)
            && Boolean(row.custom_price_reviewed_by)
            && Math.abs(Number(row.custom_price_reviewed_rate || 0) - Number(row.rate || 0)) <= 0.000001
            && Math.abs(Number(row.custom_price_reviewed_loaded_rate || 0) - Number(row.custom_loaded_buying_rate || 0)) <= 0.000001
            && String(row.custom_price_reviewed_source_buying_price_list || "") === String(row.custom_source_buying_price_list || "")
            && String(row.custom_price_reviewed_source_currency || "") === String(row.custom_loaded_buying_currency || "");
    }

    function showPriceUpdateApproval(frm, rows) {
        const dialog = new frappe.ui.Dialog({
            title: __("Approve Negotiated Buying Prices"),
            fields: [{
                fieldname: "review",
                fieldtype: "HTML",
                options: renderApprovalRows(frm, rows),
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

    function renderApprovalRows(frm, rows) {
        const body = rows.map((row) => {
            const sourceCurrency = row.custom_loaded_buying_currency || "";
            const poCurrency = frm?.doc?.currency || "";
            const listPrice = frappe.format(Number(row.custom_source_buying_rate || 0), { fieldtype: "Currency", options: sourceCurrency });
            const loaded = frappe.format(Number(row.custom_loaded_buying_rate || 0), { fieldtype: "Currency", options: poCurrency });
            const negotiated = frappe.format(Number(row.rate || 0), { fieldtype: "Currency", options: poCurrency });
            const variance = frappe.format(Number(row.custom_price_variance_amount || 0), { fieldtype: "Currency", options: poCurrency });
            return `<tr><td>${frappe.utils.escape_html(row.item_code || "")}</td><td>${frappe.utils.escape_html(row.custom_source_buying_price_list || "")}</td><td>${listPrice}</td><td>${loaded}</td><td>${negotiated}</td><td>${variance}</td><td><input type="checkbox" data-po-price-update="${frappe.utils.escape_html(row.name)}" checked></td></tr>`;
        }).join("");
        return `<p>${__("Confirm which negotiated rates should update their selected buying price list.")}</p><table class="table table-bordered"><thead><tr><th>${__("Item")}</th><th>${__("Price List")}</th><th>${__("List price")}</th><th>${__("Loaded in PO")}</th><th>${__("Negotiated")}</th><th>${__("Difference")}</th><th>${__("Update")}</th></tr></thead><tbody>${body}</tbody></table>`;
    }

    function setValue(row, fieldname, value) {
        if (!row?.doctype || !row?.name || (frappe.meta?.has_field && !frappe.meta.has_field(row.doctype, fieldname))) return;
        frappe.model.set_value(row.doctype, row.name, fieldname, value);
    }

    function sameRate(left, right) {
        return Math.abs(Number(left || 0) - Number(right || 0)) <= 0.000001;
    }
})();
