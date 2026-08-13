/**
 * Orderlift — company focus for list views.
 *
 * Each scoped doctype list is STRICTLY focused on the active company: every load
 * forces the company filter to the active company, overriding any stale/different
 * value (e.g. a saved filter holding the previously-active company after a switch).
 * To view another company, switch via the sidebar switcher — the single source of
 * truth. The server permission query (allowed companies) remains the hard backstop.
 *
 * Customer and Supplier are exceptions: their visible Company filter still follows
 * the active session company, but internal party records use represents_company for
 * the company they represent. The visible filter is translated only in request args
 * so Company = Installation returns internal counterparties representing other
 * companies that Installation is allowed to transact with.
 */

(function () {
    let companyContextReady = false;
    let companyContextPromise = null;

    // doctype -> company fieldname
    const FIELD = {
        Supplier: "custom_company",
        "Price List": "custom_company",
        Opportunity: "company",
        Quotation: "company",
        "Sales Order": "company",
        "Sales Invoice": "company",
        "Purchase Order": "company",
        "Purchase Invoice": "company",
        "Purchase Receipt": "company",
        "Delivery Note": "company",
        "Payment Entry": "company",
        "Stock Entry": "company",
        "Material Request": "company",
        "Request for Quotation": "company",
        Project: "company",
        "Forecast Load Plan": "company",
        "Sales Commission": "company",
        "Pricing Sheet": "custom_company",
        "Pricing Scenario": "custom_company",
        "Pricing Benchmark Policy": "company",
        "Pricing Customs Policy": "company",
        "Customer Segmentation Engine": "custom_company",
        "Partner Campaign": "custom_company",
        "Portal Customer Group Policy": "custom_company",
        "Portal Quote Request": "custom_company",
        "Stock Planning Settings": "company",
        "Stock Demand Plan": "company",
    };

    const COUNTERPARTY_FOCUS = new Set(["Customer", "Supplier"]);

    function context() {
        return (window.frappe && frappe.boot && frappe.boot.orderlift_company_access) || {};
    }

    function activeCompany() {
        const ctx = context();
        return ctx.current_company || "";
    }

    function withFreshContext(callback) {
        if (companyContextReady || !window.frappe || !frappe.call) {
            callback();
            return;
        }
        if (!companyContextPromise) {
            companyContextPromise = Promise.resolve(frappe.call({
                method: "orderlift.menu_access.get_current_company_access_payload",
            })).then((response) => {
                const payload = response && response.message;
                if (payload && window.frappe && frappe.boot) {
                    frappe.boot.orderlift_company_access = payload;
                }
            }).catch((error) => {
                console.warn("company_scope: unable to refresh company context", error);
            }).then(() => {
                companyContextReady = true;
            });
        }
        companyContextPromise.then(callback);
    }

    function isCorrect(row, field, company) {
        return Array.isArray(row) && row[1] === field && row[2] === "=" && row[3] === company;
    }

    function companyEqualsValue(row, field) {
        return Array.isArray(row) && row[1] === field && row[2] === "=" ? row[3] || "" : "";
    }

    function isGeneratedCounterpartyFilter(row) {
        return Array.isArray(row) && (row[1] === "is_internal_customer" || row[1] === "is_internal_supplier" || row[1] === "represents_company");
    }

    function internalField(doctype) {
        return doctype === "Customer" ? "is_internal_customer" : "is_internal_supplier";
    }

    function translateCounterpartyFilters(doctype, field, filters) {
        const translated = [];
        (filters || []).forEach((row) => {
            if (companyEqualsValue(row, field)) return;
            if (!isGeneratedCounterpartyFilter(row)) translated.push(row);
        });
        return translated;
    }

    function installCounterpartyFilterTranslation(listview, field) {
        if (!listview || listview.__orderlift_counterparty_filter_translation) return;
        if (typeof listview.get_filters_for_args !== "function") return;
        const original = listview.get_filters_for_args.bind(listview);
        listview.get_filters_for_args = function () {
            return translateCounterpartyFilters(listview.doctype, field, original());
        };
        listview.__orderlift_counterparty_filter_translation = true;
    }

    function refreshOnceForCompany(listview, company) {
        if (
            !listview ||
            !listview.__orderlift_initial_refresh_complete ||
            listview.__orderlift_company_focus_pending !== company ||
            listview.__orderlift_company_focus_refreshed === company
        ) return;
        listview.__orderlift_company_focus_pending = "";
        listview.__orderlift_company_focus_refreshed = company;
        window.setTimeout(() => {
            if (activeCompany() === company && typeof listview.refresh === "function") {
                listview.last_args = null;
                listview.refresh();
            }
        }, 0);
    }

    function enforceFocus(listview, field) {
        if (!companyContextReady) {
            withFreshContext(() => enforceFocus(listview, field));
            return;
        }
        const company = activeCompany();
        if (!company || !listview) return;
        if (listview.__orderlift_company_focus_enforcing) return;
        listview.__orderlift_company_focus_enforcing = true;

        try {
            // 1) Correct the seed array applied on first render. onload runs before
            //    filter_area is populated from listview.filters (base_list.js), so
            //    rewriting the seed here makes the active company win over any saved
            //    (possibly stale) company filter.
            if (Array.isArray(listview.filters)) {
                listview.filters = listview.filters.filter((row) => !(Array.isArray(row) && row[1] === field));
                listview.filters.push([listview.doctype, field, "=", company]);
            }

            // 2) If filter_area is already populated (re-entry / soft route/report
            //    view restore), override a stale value: add() alone won't replace an
            //    existing one (exists()), so remove then add.
            if (!listview.filter_area) {
                listview.__orderlift_company_focus_enforcing = false;
                return;
            }
            const live = (listview.filter_area.get() || []).find((row) => row[1] === field);
            if (live && !isCorrect(live, field, company)) {
                listview.__orderlift_company_focus_pending = company;
                Promise.resolve(listview.filter_area.remove(field)).then(() => {
                    return listview.filter_area.add([[listview.doctype, field, "=", company]], false);
                }).then(() => {
                    refreshOnceForCompany(listview, company);
                }).finally(() => {
                    listview.__orderlift_company_focus_enforcing = false;
                });
            } else if (!live) {
                listview.__orderlift_company_focus_pending = company;
                Promise.resolve(listview.filter_area.add([[listview.doctype, field, "=", company]], false))
                    .then(() => refreshOnceForCompany(listview, company))
                    .finally(() => {
                        listview.__orderlift_company_focus_enforcing = false;
                    });
            } else {
                listview.__orderlift_company_focus_enforcing = false;
                refreshOnceForCompany(listview, company);
            }
        } catch (error) {
            console.error("company_scope: unable to enforce list focus", error);
            listview.__orderlift_company_focus_enforcing = false;
        }
    }

    function enforceCounterpartyFocus(listview, field) {
        if (!companyContextReady) {
            withFreshContext(() => enforceCounterpartyFocus(listview, field));
            return;
        }
        const company = activeCompany();
        if (!company || !listview) return;
        installCounterpartyFilterTranslation(listview, field);
        if (listview.__orderlift_company_focus_enforcing) return;
        listview.__orderlift_company_focus_enforcing = true;

        try {
            if (Array.isArray(listview.filters)) {
                listview.filters = listview.filters
                    .filter((row) => !companyEqualsValue(row, field) && !isGeneratedCounterpartyFilter(row));
                listview.filters.push([listview.doctype, field, "=", company]);
            }
            if (!listview.filter_area) {
                listview.__orderlift_company_focus_enforcing = false;
                return;
            }

            const currentRows = listview.filter_area.get() || [];
            const live = currentRows.find((row) => row[1] === field);
            if (live && isCorrect(live, field, company) && !currentRows.some(isGeneratedCounterpartyFilter)) {
                listview.__orderlift_company_focus_enforcing = false;
                refreshOnceForCompany(listview, company);
                return;
            }

            Promise.resolve(listview.filter_area.remove(field)).then(() => {
                return Promise.resolve(listview.filter_area.remove("is_internal_customer"));
            }).then(() => {
                return Promise.resolve(listview.filter_area.remove("is_internal_supplier"));
            }).then(() => {
                return Promise.resolve(listview.filter_area.remove("represents_company"));
            }).then(() => {
                return listview.filter_area.add([[listview.doctype, field, "=", company]], false);
            }).then(() => {
                refreshOnceForCompany(listview, company);
            }).finally(() => {
                listview.__orderlift_company_focus_enforcing = false;
            });
        } catch (error) {
            console.error("company_scope: unable to enforce party counterparty focus", error);
            listview.__orderlift_company_focus_enforcing = false;
        }
    }

    function installFocusSettings() {
        frappe.provide("frappe.listview_settings");

        Object.keys(FIELD).forEach((doctype) => {
            const field = FIELD[doctype];
            const marker = COUNTERPARTY_FOCUS.has(doctype) ? `counterparty:${field}` : field;
            const existing = frappe.listview_settings[doctype] || {};
            if (existing.__orderlift_company_focus_installed === marker) return;

            const previousOnload = existing.onload;
            const previousRefresh = existing.refresh;
            existing.onload = function (listview) {
                if (typeof previousOnload === "function") previousOnload(listview);
                listview.__orderlift_initial_refresh_complete = false;
                if (COUNTERPARTY_FOCUS.has(doctype)) {
                    enforceCounterpartyFocus(listview, field);
                } else {
                    enforceFocus(listview, field);
                }
            };
            existing.refresh = function (listview) {
                if (typeof previousRefresh === "function") previousRefresh(listview);
                listview.__orderlift_initial_refresh_complete = true;
                if (COUNTERPARTY_FOCUS.has(doctype)) {
                    enforceCounterpartyFocus(listview, field);
                } else {
                    enforceFocus(listview, field);
                }
            };
            existing.__orderlift_company_focus_installed = marker;
            frappe.listview_settings[doctype] = existing;
        });
    }

    function scheduleInstall() {
        installFocusSettings();
        window.setTimeout(installFocusSettings, 250);
        window.setTimeout(installFocusSettings, 1000);
    }

    scheduleInstall();

    if (frappe.router && frappe.router.on) {
        frappe.router.on("change", scheduleInstall);
    }

    let attempts = 80;
    (function keepInstalled() {
        installFocusSettings();
        attempts -= 1;
        if (attempts > 0) window.setTimeout(keepInstalled, 250);
    })();
})();
