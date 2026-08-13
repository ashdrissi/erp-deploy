frappe.ui.form.on("Purchase Order", {
    refresh(frm) {
        setupPackagingGrid(frm);
        ensurePricingAlertStyles();
        refreshAllPackagingRows(frm, { immediate: true, onlyNewDraft: true });
        schedulePricingAlertRefresh(frm, { immediate: true });
    },

    supplier(frm) {
        schedulePricingAlertRefresh(frm);
    },

    buying_price_list(frm) {
        schedulePricingAlertRefresh(frm);
    },

    items_add(frm, cdt, cdn) {
        setupPackagingGrid(frm);
        if (cdn) {
            schedulePurchaseOrderPackagingRefresh(frm, cdt, cdn, { immediate: true, forceDefault: true });
        }
        schedulePricingAlertRefresh(frm);
    },

    items_remove(frm) {
        schedulePricingAlertRefresh(frm);
    },

    validate(frm) {
        schedulePricingAlertRefresh(frm, { immediate: true });
    },
});


frappe.ui.form.on("Purchase Order Item", {
    item_code(frm, cdt, cdn) {
        schedulePurchaseOrderPackagingRefresh(frm, cdt, cdn, { forceDefault: true });
        schedulePricingAlertRefresh(frm);
    },

    qty(frm, cdt, cdn) {
        schedulePurchaseOrderPackagingRefresh(frm, cdt, cdn);
        schedulePricingAlertRefresh(frm);
    },

    uom(frm, cdt, cdn) {
        schedulePurchaseOrderPackagingRefresh(frm, cdt, cdn);
        schedulePricingAlertRefresh(frm);
    },

    conversion_factor(frm, cdt, cdn) {
        schedulePurchaseOrderPackagingRefresh(frm, cdt, cdn);
        schedulePricingAlertRefresh(frm);
    },

    custom_packaging_profile(frm, cdt, cdn) {
        schedulePurchaseOrderPackagingRefresh(frm, cdt, cdn, { userSelected: true });
    },

    rate(frm) {
        schedulePricingAlertRefresh(frm);
    },

    price_list_rate(frm) {
        schedulePricingAlertRefresh(frm);
    },

    discount_percentage(frm) {
        schedulePricingAlertRefresh(frm);
    },

    discount_amount(frm) {
        schedulePricingAlertRefresh(frm);
    },
});


function schedulePricingAlertRefresh(frm, options = {}) {
    if (!frm?.fields_dict?.custom_pricing_alerts_html) {
        return;
    }

    if (frm.__poPricingAlertsTimer) {
        clearTimeout(frm.__poPricingAlertsTimer);
    }

    const delay = options.immediate ? 0 : 350;
    frm.__poPricingAlertsTimer = setTimeout(() => refreshPricingAlerts(frm), delay);
}


async function refreshPricingAlerts(frm) {
    const field = frm.fields_dict.custom_pricing_alerts_html;
    if (!field) {
        return;
    }

    const rows = (frm.doc.items || []).filter((row) => (row.item_code || "").trim());
    if (!rows.length) {
        frm.__poPricingAlertsRequestId = (frm.__poPricingAlertsRequestId || 0) + 1;
        field.$wrapper.html(renderEmptyState());
        return;
    }

    const requestId = (frm.__poPricingAlertsRequestId || 0) + 1;
    frm.__poPricingAlertsRequestId = requestId;
    field.$wrapper.html(renderLoadingState());

    try {
        const response = await frappe.call({
            method: "orderlift.sales.utils.po_pricing_alerts.get_pricing_alerts",
            args: {
                doc: buildDocPayload(frm.doc),
                items: rows.map(buildItemPayload),
            },
        });

        if (frm.__poPricingAlertsRequestId !== requestId) {
            return;
        }

        const payload = response.message || {};
        const accessResponse = await frappe.call({
            method: "orderlift.orderlift_sales.utils.purchase_order_pricing.get_purchase_price_approval_access",
            args: {
                company: frm.doc.company || "",
                target_currency: frm.doc.currency || "",
                reference_date: frm.doc.transaction_date || frappe.datetime.nowdate(),
            },
        });
        if (frm.__poPricingAlertsRequestId !== requestId) {
            return;
        }
        field.$wrapper.html(renderAlertsPanel(frm, payload, accessResponse.message || {}));
        bindPriceReviewActions(frm);
    } catch (error) {
        if (frm.__poPricingAlertsRequestId !== requestId) {
            return;
        }

        const message = error?.message || __("Could not analyze pricing sources.");
        field.$wrapper.html(renderErrorState(message));
    }
}


function buildDocPayload(doc) {
    return {
        supplier: doc.supplier || "",
        buying_price_list: doc.buying_price_list || "",
        currency: doc.currency || "",
        conversion_rate: doc.conversion_rate || 1,
        transaction_date: doc.transaction_date || frappe.datetime.nowdate(),
        company: doc.company || "",
    };
}


function buildItemPayload(row) {
    return {
        item_code: row.item_code || "",
        item_name: row.item_name || "",
        qty: row.qty || 0,
        uom: row.uom || "",
        stock_uom: row.stock_uom || "",
        conversion_factor: row.conversion_factor || 1,
        rate: row.rate || 0,
        base_rate: row.base_rate || 0,
        price_list_rate: row.price_list_rate || 0,
        custom_source_buying_price_list: row.custom_source_buying_price_list || "",
        custom_source_buying_rate: row.custom_source_buying_rate || 0,
        custom_loaded_buying_currency: row.custom_loaded_buying_currency || "",
        custom_loaded_buying_rate: row.custom_loaded_buying_rate || 0,
        last_purchase_rate: row.last_purchase_rate || 0,
        discount_percentage: row.discount_percentage || 0,
        discount_amount: row.discount_amount || 0,
    };
}


function setupPackagingGrid(frm) {
    const grid = frm?.fields_dict?.items?.grid;
    if (!grid || grid.__orderliftPackagingConfigured) {
        return;
    }

    const packagingField = grid.get_field("custom_packaging_profile");
    if (packagingField) {
        packagingField.get_query = function (doc, cdt, cdn) {
            const row = locals[cdt][cdn] || {};
            return {
                filters: {
                    parent: row.item_code || "__missing_item__",
                    parenttype: "Item",
                    is_active: 1,
                },
            };
        };
    }

    grid.__orderliftPackagingConfigured = true;
}


function canMutatePackagingSnapshot(frm) {
    return Number(frm?.doc?.docstatus || 0) === 0;
}


function refreshAllPackagingRows(frm, options = {}) {
    if (!canMutatePackagingSnapshot(frm)) {
        return;
    }

    const isNew = typeof frm.is_new === "function" ? frm.is_new() : Boolean(frm.doc?.__islocal);
    if (options.onlyNewDraft && !isNew) {
        return;
    }

    (frm.doc.items || []).forEach((row) => {
        if (!(row.item_code || "").trim()) {
            return;
        }
        schedulePurchaseOrderPackagingRefresh(frm, row.doctype || "Purchase Order Item", row.name, {
            immediate: options.immediate,
            forceDefault: !(row.custom_packaging_profile || "").trim(),
            silent: true,
        });
    });
}


function schedulePurchaseOrderPackagingRefresh(frm, cdt, cdn, options = {}) {
    if (!canMutatePackagingSnapshot(frm) || !cdn) {
        return;
    }

    frm.__poPackagingTimers = frm.__poPackagingTimers || {};
    if (frm.__poPackagingTimers[cdn]) {
        clearTimeout(frm.__poPackagingTimers[cdn]);
    }

    const delay = options.immediate ? 0 : 200;
    frm.__poPackagingTimers[cdn] = setTimeout(() => refreshPurchaseOrderPackagingRow(frm, cdt, cdn, options), delay);
}


async function refreshPurchaseOrderPackagingRow(frm, cdt, cdn, options = {}) {
    if (!canMutatePackagingSnapshot(frm)) {
        return;
    }

    const row = locals?.[cdt]?.[cdn];
    if (!row) {
        return;
    }

    const itemCode = (row.item_code || "").trim();
    if (!itemCode) {
        clearPurchaseOrderPackagingRow(row);
        frm.refresh_field("items");
        return;
    }

    frm.__poPackagingRequestIds = frm.__poPackagingRequestIds || {};
    const requestId = (frm.__poPackagingRequestIds[cdn] || 0) + 1;
    frm.__poPackagingRequestIds[cdn] = requestId;

    const selectedProfile = options.forceDefault ? "" : (row.custom_packaging_profile || "").trim();

    try {
        const response = await frappe.call({
            method: "orderlift.orderlift_logistics.utils.packaging_resolver.resolve_packaging",
            args: {
                item_code: itemCode,
                packaging_profile: selectedProfile || undefined,
                qty: row.qty || 0,
                uom: row.uom || undefined,
            },
        });

        if (!canMutatePackagingSnapshot(frm) || frm.__poPackagingRequestIds[cdn] !== requestId) {
            return;
        }

        const resolution = response.message || {};
        applyPurchaseOrderPackagingResolution(frm, row, resolution, options);
    } catch (error) {
        if (!options.silent) {
            frappe.show_alert({ message: __("Could not resolve packaging for {0}", [itemCode]), indicator: "red" });
        }
    }
}


function applyPurchaseOrderPackagingResolution(frm, row, resolution, options = {}) {
    if (!canMutatePackagingSnapshot(frm)) {
        return;
    }

    const resolvedProfileName = resolution.resolved_profile_name || "";
    const explicitSelection = options.userSelected && !!(row.custom_packaging_profile || "").trim();
    const source = explicitSelection ? "selected" : (resolution.resolved_source || "item_fallback");

    let changed = false;
    if (!explicitSelection && resolvedProfileName) {
        changed = setRowValue(row, "custom_packaging_profile", resolvedProfileName) || changed;
    }

    changed = setRowValue(row, "custom_packaging_profile_source", source) || changed;
    changed = setRowValue(row, "custom_packaging_uom", resolution.resolved_uom || "") || changed;
    changed = setRowValue(row, "custom_packaging_type", resolution.packaging_type || "") || changed;
    changed = setRowValue(row, "custom_units_per_package", resolution.units_per_package || 0) || changed;
    changed = setRowValue(row, "custom_package_count", resolution.package_count || 0) || changed;
    changed = setRowValue(row, "custom_package_weight_kg", resolution.weight_kg || 0) || changed;
    changed = setRowValue(row, "custom_package_volume_m3", resolution.volume_m3 || 0) || changed;

    if (changed) {
        frm.dirty();
        frm.refresh_field("items");
    }

    const warnings = resolution.warnings || [];
    if (warnings.length && !options.silent) {
        frappe.show_alert({ message: warnings[0], indicator: "orange" });
    }
}


function clearPurchaseOrderPackagingRow(row) {
    setRowValue(row, "custom_packaging_profile", "");
    setRowValue(row, "custom_packaging_profile_source", "");
    setRowValue(row, "custom_packaging_uom", "");
    setRowValue(row, "custom_packaging_type", "");
    setRowValue(row, "custom_units_per_package", 0);
    setRowValue(row, "custom_package_count", 0);
    setRowValue(row, "custom_package_weight_kg", 0);
    setRowValue(row, "custom_package_volume_m3", 0);
}


function setRowValue(row, key, value) {
    const current = row[key];
    if (isNumericPackagingField(key)) {
        if (Math.abs(Number(current || 0) - Number(value || 0)) <= 1e-9) {
            return false;
        }
        row[key] = value;
        return true;
    }
    if (String(current ?? "") === String(value ?? "")) {
        return false;
    }
    row[key] = value;
    return true;
}


function isNumericPackagingField(key) {
    return [
        "custom_units_per_package",
        "custom_package_count",
        "custom_package_weight_kg",
        "custom_package_volume_m3",
    ].includes(key);
}


function renderAlertsPanel(frm, payload, access = {}) {
    const summary = payload.summary || {};
    const alerts = payload.alerts || [];
    const settings = payload.settings || {};

    const summaryParts = [
        `${summary.price_list_count || 0} ${__("from Item Price")} ${summary.price_list_name ? `[${escapeHtml(summary.price_list_name)}]` : ""}`.trim(),
        `${summary.last_purchase_count || 0} ${__("from Last Purchase")}`,
        `${summary.manual_count || 0} ${__("Manual")}`,
    ];

    const signalParts = [];
    if (summary.expired_count) {
        signalParts.push(`<span class="ol-po-alert-pill warning">${summary.expired_count} ${__("Expired")}</span>`);
    }
    if (summary.stale_count) {
        signalParts.push(`<span class="ol-po-alert-pill warning">${summary.stale_count} ${__("Stale")}</span>`);
    }
    if (summary.unknown_count) {
        signalParts.push(`<span class="ol-po-alert-pill danger">${summary.unknown_count} ${__("No Reference")}</span>`);
    }
    if (summary.cheaper_suppliers_count) {
        signalParts.push(`<span class="ol-po-alert-pill info">${summary.cheaper_suppliers_count} ${__("Better Supplier")}</span>`);
    }

    const intro = summary.is_all_clean
        ? `<div class="ol-po-alert-status success">${__("All items are using current pricing references based on the active Purchase Order data.")}</div>`
        : `<div class="ol-po-alert-status warning">${__("Review the alerts below before submitting this Purchase Order.")}</div>`;

    const body = alerts.length
        ? renderAlertCards(frm, alerts, settings)
        : `<div class="ol-po-alert-empty success">${__("No pricing issues detected.")}</div>`;

    return `
        <div class="ol-po-pricing-alerts-root">
            <div class="ol-po-pricing-alerts-header">
                <div>
                    <div class="ol-po-pricing-alerts-title">${__("Pricing Sources")}</div>
                    <div class="ol-po-pricing-alerts-summary">${summaryParts.join(" · ")}</div>
                </div>
                <div class="ol-po-pricing-alerts-signals">${signalParts.join("")}</div>
            </div>
            ${intro}
            ${renderPriceApprovalSection(frm, access)}
            ${body}
        </div>
    `;
}


function renderPriceApprovalSection(frm, access) {
    const rows = (frm.doc.items || []).filter(requiresPriceReview);
    if (!rows.length) {
        return `<section class="ol-po-price-approval success"><strong>${__("Pricing Alerts & Approvals")}</strong><div>${__("No buying price changes require approval.")}</div></section>`;
    }

    const canApprove = Boolean(access.can_approve);
    const targetLists = access.buying_price_lists || [];
    const pending = rows.filter((row) => !isCurrentPriceReview(row));
    const cardsHtml = rows.map((row) => {
        const isNew = isManualNewPrice(row);
        const status = isCurrentPriceReview(row) ? (row.custom_price_update_decision || "Reviewed") : "Pending";
        const approveLabel = isNew ? __("Approve & Create Price") : __("Approve & Update Price List");
        const action = status === "Pending" && canApprove && !frm.doc.__islocal
            ? `<button class="btn btn-sm btn-primary ol-po-price-review" data-decision="Approved" data-item="${escapeHtml(row.name)}">${approveLabel}</button><button class="btn btn-sm btn-default ol-po-price-review" data-decision="Skipped" data-item="${escapeHtml(row.name)}">${__("Skip Update")}</button>`
            : "";
        const sourceCurrency = row.custom_loaded_buying_currency || frm.doc.currency || "";
        const poCurrency = frm.doc.currency || "";
        const type = isNew ? __("Create New Price") : __("Update Existing Price");
        const selectedList = String(row.custom_source_buying_price_list || "");
        const targetDetails = targetLists.find((entry) => String(entry.price_list || "") === selectedList);
        const selector = isNew && canApprove && status === "Pending" && !frm.doc.__islocal
            ? renderTargetPriceListSelect(row, targetLists)
            : `<div class="ol-po-source-list-name">${escapeHtml(selectedList || __("Not selected"))}</div>`;
        const metrics = isNew
            ? `<div class="ol-po-price-metric"><span class="ol-po-metric-value">${formatCurrency(frm, row.rate, poCurrency)}</span><small>${__("PO unit price")}</small></div><div class="ol-po-price-metric"><span class="ol-po-metric-value">${escapeHtml(row.uom || "-")}</span><small>${__("Price UOM")}</small></div>`
            : `<div class="ol-po-price-metric"><span class="ol-po-metric-value">${formatCurrency(frm, row.custom_source_buying_rate, sourceCurrency)}</span><small>${__("Current list price")}</small></div><div class="ol-po-price-metric"><span class="ol-po-metric-value">${formatCurrency(frm, row.rate, poCurrency)}</span><small>${__("PO unit price")}</small></div><div class="ol-po-price-metric"><span class="ol-po-metric-value">${formatCurrency(frm, livePriceDifference(row), poCurrency)}</span><small>${__("Difference from loaded")}</small></div>`;
        return `
            <article class="ol-po-price-review-card ${isNew ? "is-new" : "is-update"}">
                <header class="ol-po-price-review-card-header">
                    <div>
                        <strong>${escapeHtml(row.item_code || "")}</strong>
                        <span>${type}</span>
                    </div>
                    <span class="ol-po-alert-pill ${status === "Pending" ? "warning" : "success"}">${__(status)}</span>
                </header>
                <div class="ol-po-price-review-content">
                    <div class="ol-po-price-target-block">
                        <label>${isNew ? __("Target Buying Price List") : __("Source Buying Price List")}</label>
                        ${selector}
                        <div class="ol-po-conversion-preview" data-conversion-preview="${escapeHtml(row.name)}">
                            ${renderConversionPreview(frm, row, targetDetails, isNew)}
                        </div>
                    </div>
                    <div class="ol-po-price-metrics ${isNew ? "is-new" : ""}">${metrics}</div>
                </div>
                ${action ? `<footer class="ol-po-price-review-actions">${action}</footer>` : ""}
            </article>`;
    }).join("");
    const note = frm.doc.__islocal
        ? __("Save this Purchase Order before reviewing negotiated prices.")
        : canApprove
            ? __("Approve each price only after confirming that it may create or update an Item Price in the target buying list.")
            : __("Pending privileged pricing approval. You can see the alert but cannot create or update buying prices.");
    return `<section class="ol-po-price-approval ${pending.length ? "warning" : "success"}"><div class="ol-po-price-approval-header"><strong>${__("Pricing Alerts & Approvals")}</strong><span>${pending.length} ${__("pending")}</span></div><p>${note}</p><div class="ol-po-price-review-list">${cardsHtml}</div></section>`;
}


function renderTargetPriceListSelect(row, priceLists) {
    const selected = String(row.custom_source_buying_price_list || "");
    const options = priceLists.map((entry) => {
        const name = String(entry.price_list || "");
        const currency = String(entry.currency || "");
        const exchangeRate = Number(entry.exchange_rate || 0);
        return `<option value="${escapeHtml(name)}" data-currency="${escapeHtml(currency)}" data-exchange-rate="${exchangeRate}" ${name === selected ? "selected" : ""}>${escapeHtml(name)}${currency ? ` (${escapeHtml(currency)})` : ""}</option>`;
    }).join("");
    return `<select class="form-control ol-po-target-price-list" data-item="${escapeHtml(row.name)}" aria-label="${__("Target Buying Price List")}"><option value="">${__("Select target list")}</option>${options}</select>`;
}


function convertedTargetPrice(row, details) {
    const exchangeRate = Number(details?.exchange_rate || 0);
    if (exchangeRate <= 0) return null;
    let rate = Number(row?.rate || 0) / exchangeRate;
    const sourceUom = String(row?.custom_loaded_buying_uom || row?.uom || "");
    const rowUom = String(row?.uom || "");
    const stockUom = String(row?.stock_uom || "");
    if (sourceUom && sourceUom === stockUom && rowUom && rowUom !== stockUom) {
        rate /= Number(row?.conversion_factor || 1) || 1;
    }
    return rate;
}


function renderConversionPreview(frm, row, details, isNew = true) {
    if (!details?.price_list) {
        return `<span class="ol-po-conversion-empty">${isNew ? __("Select a list to preview the stored Item Price.") : __("Exchange-rate preview unavailable.")}</span>`;
    }
    const exchangeRate = Number(details.exchange_rate || 0);
    const sourceCurrency = String(details.currency || "");
    const poCurrency = String(frm?.doc?.currency || "");
    const converted = convertedTargetPrice(row, details);
    if (converted === null) {
        return `<span class="ol-po-conversion-error">${__("No exchange rate is available for this target list.")}</span>`;
    }
    const rateText = sourceCurrency === poCurrency
        ? __("Same currency, no conversion")
        : __("1 {0} = {1} {2}", [sourceCurrency, poCurrency, Number(exchangeRate).toLocaleString(undefined, { maximumFractionDigits: 4 })]);
    return `<div><small>${isNew ? __("New Item Price to store") : __("Updated Item Price to store")}</small><strong>${formatCurrency(frm, converted, sourceCurrency)}</strong><span>${rateText}</span></div>`;
}


function bindPriceReviewActions(frm) {
    const wrapper = frm.fields_dict?.custom_pricing_alerts_html?.$wrapper;
    if (!wrapper) return;
    wrapper.off("change.orderliftPriceReview", ".ol-po-target-price-list");
    wrapper.on("change.orderliftPriceReview", ".ol-po-target-price-list", function () {
        const select = $(this);
        const itemName = String(select.data("item") || "");
        const row = (frm.doc.items || []).find((item) => item.name === itemName);
        const option = this.options[this.selectedIndex];
        const details = option?.value ? {
            price_list: option.value,
            currency: option.dataset.currency || "",
            exchange_rate: Number(option.dataset.exchangeRate || 0),
        } : null;
        wrapper.find(".ol-po-conversion-preview").filter(function () {
            return String($(this).attr("data-conversion-preview") || "") === itemName;
        }).html(renderConversionPreview(frm, row, details, true));
    });
    wrapper.off("click.orderliftPriceReview", ".ol-po-price-review");
    wrapper.on("click.orderliftPriceReview", ".ol-po-price-review", function () {
        const button = $(this);
        const decision = button.data("decision");
        const itemName = button.data("item");
        if (decision === "Approved") {
            const row = (frm.doc.items || []).find((item) => item.name === itemName);
            const targetPriceList = isManualNewPrice(row)
                ? String(wrapper.find(`.ol-po-target-price-list[data-item="${itemName}"]`).val() || "")
                : String(row?.custom_source_buying_price_list || "");
            if (isManualNewPrice(row) && !targetPriceList) {
                frappe.msgprint(__("Select a target Buying Price List before approving this new price."));
                return;
            }
            frappe.confirm(
                __("I confirm this approved price may create or update an Item Price in the selected buying list when the Purchase Order is submitted."),
                () => submitPriceReview(frm, itemName, decision, 1, targetPriceList),
            );
        } else {
            submitPriceReview(frm, itemName, decision, 0, "");
        }
    });
}


async function submitPriceReview(frm, itemName, decision, attestation, targetPriceList) {
    try {
        await frappe.call({
            method: "orderlift.orderlift_sales.utils.purchase_order_pricing.set_purchase_order_price_review_decisions",
            args: {
                decisions: JSON.stringify([{
                    purchase_order: frm.doc.name,
                    purchase_order_item: itemName,
                    decision,
                    target_price_list: targetPriceList || "",
                }]),
                attestation,
            },
        });
        await frm.reload_doc();
        schedulePricingAlertRefresh(frm, { immediate: true });
    } catch (error) {
        frappe.msgprint(error?.message || __("Could not save the pricing approval."));
    }
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


function isManualNewPrice(row) {
    return Boolean(row?.item_code)
        && Number(row.rate || 0) > 0
        && Number(row.custom_loaded_buying_rate || 0) <= 0
        && !String(row.custom_source_item_price || "").trim();
}


function requiresPriceReview(row) {
    if (!row?.item_code) return false;
    const loaded = Number(row.custom_loaded_buying_rate || 0);
    return (loaded > 0 && !sameRate(Number(row.rate || 0), loaded)) || isManualNewPrice(row);
}


function livePriceDifference(row) {
    return Number(row?.rate || 0) - Number(row?.custom_loaded_buying_rate || 0);
}


function renderAlertCards(frm, alerts, settings) {
    const cards = alerts.map((alert) => renderAlertCard(frm, alert, settings)).join("");
    if (alerts.length > 5) {
        return `
            <details class="ol-po-alert-details" open>
                <summary>${__("View {0} pricing alerts", [alerts.length])}</summary>
                <div class="ol-po-alert-grid">${cards}</div>
            </details>
        `;
    }
    return `<div class="ol-po-alert-grid">${cards}</div>`;
}


function renderAlertCard(frm, alert, settings) {
    const tone = alert.severity || "info";
    const meta = [];

    if (alert.rate) {
        meta.push(`${__("Current Rate")}: ${formatCurrency(frm, alert.rate)}`);
    }
    if (alert.valid_upto) {
        meta.push(`${__("Valid Until")}: ${escapeHtml(alert.valid_upto)}`);
    }
    if (alert.days_since) {
        meta.push(`${__("Age")}: ${escapeHtml(String(alert.days_since))} ${__("days")}`);
    }
    if (alert.threshold_days) {
        meta.push(`${__("Threshold")}: ${escapeHtml(String(alert.threshold_days))} ${__("days")}`);
    }
    if (alert.supplier) {
        meta.push(`${__("Supplier")}: ${escapeHtml(alert.supplier)}`);
    }
    if (alert.savings_percent) {
        meta.push(`${__("Savings")}: ${escapeHtml(formatPercent(alert.savings_percent))}%`);
    }
    if (alert.purchase_order) {
        meta.push(`${__("Reference PO")}: <a href="/app/purchase-order/${encodeURIComponent(alert.purchase_order)}">${escapeHtml(alert.purchase_order)}</a>`);
    }
    if (alert.packing_unit) {
        meta.push(`${__("Packing Unit")}: ${escapeHtml(String(alert.packing_unit))}`);
    }

    return `
        <div class="ol-po-alert-card ${tone}">
            <div class="ol-po-alert-card-header">
                <div class="ol-po-alert-item">${escapeHtml(alert.item_code || "")}</div>
                <div class="ol-po-alert-type">${escapeHtml(alertLabel(alert.type))}</div>
            </div>
            <div class="ol-po-alert-name">${escapeHtml(alert.item_name || "")}</div>
            <div class="ol-po-alert-message">${escapeHtml(alert.message || "")}</div>
            ${meta.length ? `<div class="ol-po-alert-meta">${meta.join(" · ")}</div>` : ""}
        </div>
    `;
}


function renderLoadingState() {
    return `<div class="ol-po-alert-empty">${__("Analyzing pricing sources...")}</div>`;
}


function renderEmptyState() {
    return `<div class="ol-po-alert-empty">${__("Add items to see pricing source alerts.")}</div>`;
}


function renderErrorState(message) {
    return `<div class="ol-po-alert-empty error">${escapeHtml(message)}</div>`;
}


function alertLabel(type) {
    const labels = {
        analysis_error: __("Analysis Error"),
        expired_price_list: __("Expired Price List"),
        stale_last_purchase: __("Stale Last Purchase"),
        manual_override: __("Manual Override"),
        no_reference: __("No Reference"),
        better_supplier_available: __("Better Supplier"),
        packing_unit_mismatch: __("Packing Unit"),
    };
    return labels[type] || __("Alert");
}


function formatCurrency(frm, value, currency) {
    const code = String(currency || frm?.doc?.currency || "").trim();
    const amount = Number(value || 0);
    const formatted = amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return code ? `${code} ${formatted}` : formatted;
}


function formatPercent(value) {
    return Number(value || 0).toFixed(1).replace(/\.0$/, "");
}


function sameRate(left, right) {
    return Math.abs(Number(left || 0) - Number(right || 0)) <= 0.000001;
}


function escapeHtml(value) {
    return frappe.utils.escape_html(String(value || ""));
}


function ensurePricingAlertStyles() {
    if (document.getElementById("ol-po-pricing-alerts-css")) {
        return;
    }

    const style = document.createElement("style");
    style.id = "ol-po-pricing-alerts-css";
    style.textContent = `
        .ol-po-pricing-alerts-root {
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 11px 12px;
            background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
            margin-bottom: 16px;
        }
        .ol-po-pricing-alerts-header {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            align-items: flex-start;
            margin-bottom: 10px;
        }
        .ol-po-pricing-alerts-title {
            font-size: 15px;
            font-weight: 700;
            color: #0f172a;
        }
        .ol-po-pricing-alerts-summary {
            color: #475569;
            font-size: 12px;
            margin-top: 2px;
        }
        .ol-po-pricing-alerts-signals {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            justify-content: flex-end;
        }
        .ol-po-alert-pill {
            padding: 4px 8px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 600;
            border: 1px solid transparent;
        }
        .ol-po-alert-pill.warning { background: #fff7ed; color: #9a3412; border-color: #fdba74; }
        .ol-po-alert-pill.danger { background: #fef2f2; color: #b91c1c; border-color: #fca5a5; }
        .ol-po-alert-pill.info { background: #eff6ff; color: #1d4ed8; border-color: #93c5fd; }
        .ol-po-alert-status {
            border-radius: 10px;
            padding: 10px 12px;
            font-size: 12px;
            margin-bottom: 12px;
            border: 1px solid transparent;
        }
        .ol-po-alert-status.success { background: #ecfdf5; border-color: #86efac; color: #166534; }
        .ol-po-alert-status.warning { background: #fffbeb; border-color: #fcd34d; color: #92400e; }
        .ol-po-alert-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 10px;
        }
        .ol-po-alert-card {
            border-radius: 12px;
            padding: 12px;
            border: 1px solid transparent;
            background: #fff;
        }
        .ol-po-alert-card.danger { border-color: #fca5a5; background: #fff1f2; }
        .ol-po-alert-card.warning { border-color: #fdba74; background: #fff7ed; }
        .ol-po-alert-card.info { border-color: #93c5fd; background: #eff6ff; }
        .ol-po-alert-card-header {
            display: flex;
            justify-content: space-between;
            gap: 8px;
            align-items: center;
            margin-bottom: 4px;
        }
        .ol-po-alert-item {
            font-weight: 700;
            color: #0f172a;
        }
        .ol-po-alert-type {
            font-size: 11px;
            color: #475569;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        .ol-po-alert-name {
            color: #334155;
            font-size: 12px;
            margin-bottom: 6px;
        }
        .ol-po-alert-message {
            color: #0f172a;
            font-size: 13px;
            line-height: 1.45;
        }
        .ol-po-alert-meta {
            margin-top: 8px;
            color: #475569;
            font-size: 11px;
            line-height: 1.5;
        }
        .ol-po-alert-empty {
            border: 1px dashed #cbd5e1;
            border-radius: 10px;
            padding: 12px;
            color: #64748b;
            font-size: 12px;
            background: #fff;
        }
        .ol-po-alert-empty.success { color: #166534; border-color: #86efac; background: #ecfdf5; }
        .ol-po-alert-empty.error { color: #b91c1c; border-color: #fca5a5; background: #fef2f2; }
        .ol-po-alert-details summary {
            cursor: pointer;
            color: #334155;
            font-weight: 600;
            margin-bottom: 10px;
        }
        .ol-po-price-approval {
            border: 1px solid #cbd5e1;
            border-radius: 10px;
            padding: 9px;
            margin: 10px 0;
        }
        .ol-po-price-approval.warning { background: #fffbeb; border-color: #fcd34d; }
        .ol-po-price-approval.success { background: #ecfdf5; border-color: #86efac; }
        .ol-po-price-approval-header { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 6px; }
        .ol-po-price-approval p { color: #475569; font-size: 12px; margin: 0 0 10px; }
        .ol-po-price-review-list { display: grid; gap: 8px; }
        .ol-po-price-review-card {
            overflow: hidden;
            border: 1px solid #dbe3ec;
            border-left: 4px solid #64748b;
            border-radius: 10px;
            background: #fff;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
        }
        .ol-po-price-review-card.is-new { border-left-color: #2563eb; }
        .ol-po-price-review-card.is-update { border-left-color: #d97706; }
        .ol-po-price-review-card-header {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 12px;
            padding: 8px 10px;
            border-bottom: 1px solid #edf1f5;
        }
        .ol-po-price-review-card-header div { display: grid; gap: 2px; }
        .ol-po-price-review-card-header strong { color: #0f172a; font-size: 14px; }
        .ol-po-price-review-card-header div > span { color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }
        .ol-po-price-review-content {
            display: grid;
            grid-template-columns: minmax(250px, 1.2fr) minmax(260px, 1.5fr);
            gap: 9px;
            padding: 9px 10px;
        }
        .ol-po-price-target-block { display: grid; align-content: start; gap: 5px; }
        .ol-po-price-target-block > label { margin: 0; color: #334155; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; }
        .ol-po-target-price-list { min-height: 36px; border-color: #94a3b8; font-weight: 600; }
        .ol-po-target-price-list:focus { border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37, 99, 235, .15); }
        .ol-po-source-list-name { min-height: 36px; display: flex; align-items: center; padding: 7px 9px; border: 1px solid #dbe3ec; border-radius: 6px; background: #f8fafc; color: #1e293b; font-weight: 600; }
        .ol-po-conversion-preview { min-height: 54px; padding: 7px 9px; border: 1px solid #bfdbfe; border-radius: 7px; background: #eff6ff; }
        .ol-po-conversion-preview > div { display: grid; grid-template-columns: 1fr auto; gap: 2px 12px; align-items: end; }
        .ol-po-conversion-preview small { color: #475569; font-size: 11px; }
        .ol-po-conversion-preview strong { color: #1d4ed8; font-size: 16px; font-variant-numeric: tabular-nums; }
        .ol-po-conversion-preview span { grid-column: 1 / -1; color: #475569; font-size: 11px; }
        .ol-po-conversion-empty { display: block; color: #64748b; line-height: 1.5; }
        .ol-po-conversion-error { display: block; color: #b91c1c; font-weight: 600; line-height: 1.5; }
        .ol-po-price-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
        .ol-po-price-metrics.is-new { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .ol-po-price-metric { min-height: 62px; display: flex; flex-direction: column; justify-content: center; gap: 2px; padding: 8px; border: 1px solid #e2e8f0; border-radius: 7px; background: #f8fafc; }
        .ol-po-metric-value { color: #0f172a; font-size: 14px; font-weight: 700; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
        .ol-po-metric-value.muted { color: #64748b; font-size: 13px; }
        .ol-po-price-metric small { color: #64748b; font-size: 11px; line-height: 1.35; }
        .ol-po-price-review-actions { display: flex; justify-content: flex-end; gap: 6px; padding: 7px 10px; border-top: 1px solid #edf1f5; background: #f8fafc; }
        .ol-po-price-review-actions .btn { min-height: 32px; margin: 0; }
        @media (max-width: 900px) {
            .ol-po-price-review-content { grid-template-columns: 1fr; }
        }
        @media (max-width: 560px) {
            .ol-po-pricing-alerts-root { padding: 12px; }
            .ol-po-pricing-alerts-header, .ol-po-price-approval-header { align-items: flex-start; flex-direction: column; }
            .ol-po-pricing-alerts-signals { justify-content: flex-start; }
            .ol-po-price-review-content { padding: 12px; }
            .ol-po-price-metrics { grid-template-columns: 1fr; }
            .ol-po-price-metric { min-height: 68px; }
            .ol-po-target-price-list { min-height: 44px; font-size: 16px; }
            .ol-po-price-review-actions { flex-direction: column; }
            .ol-po-price-review-actions .btn { width: 100%; min-height: 44px; }
        }
    `;
    document.head.appendChild(style);
}
