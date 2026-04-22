frappe.ui.form.on("Purchase Order", {
    refresh(frm) {
        setupPackagingGrid(frm);
        ensurePricingAlertStyles();
        refreshAllPackagingRows(frm, { immediate: true });
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
        field.$wrapper.html(renderAlertsPanel(frm, payload));
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


function refreshAllPackagingRows(frm, options = {}) {
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
    if (!cdn) {
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

        if (frm.__poPackagingRequestIds[cdn] !== requestId) {
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
    if (String(current ?? "") === String(value ?? "")) {
        return false;
    }
    row[key] = value;
    return true;
}


function renderAlertsPanel(frm, payload) {
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
            ${body}
        </div>
    `;
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


function formatCurrency(frm, value) {
    const options = { fieldtype: "Currency" };
    if (frm?.doc?.currency) {
        options.options = frm.doc.currency;
    }
    return frappe.format(value || 0, options);
}


function formatPercent(value) {
    return Number(value || 0).toFixed(1).replace(/\.0$/, "");
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
            padding: 14px 16px;
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
    `;
    document.head.appendChild(style);
}
