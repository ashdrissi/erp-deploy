(function () {
    const PARTY_DOCTYPES = ["Lead", "Prospect", "Customer"];
    let OPPORTUNITY_STATUS_COLORS = null;
    let OPPORTUNITY_STATUS_COLORS_PROMISE = null;

    PARTY_DOCTYPES.forEach((doctype) => {
        frappe.ui.form.on(doctype, {
            refresh(frm) {
                setupPartySegmentQueries(frm);
                renderPartyClassificationBar(frm);
                renderCampaignHistory(frm);
            },
            custom_crm_segments_add(frm) {
                setupPartySegmentQueries(frm);
                renderPartyClassificationBar(frm);
            },
            custom_crm_segments_remove(frm) {
                renderPartyClassificationBar(frm);
            },
        });
    });

    frappe.ui.form.on("Opportunity", {
        refresh(frm) {
            setupOpportunitySegmentQueries(frm);
            renderOpportunityStatusBar(frm);
            loadOpportunityStatusColors().then(() => renderOpportunityStatusBar(frm));
        },
        sales_stage(frm) {
            renderOpportunityStatusBar(frm);
        },
        status(frm) {
            renderOpportunityStatusBar(frm);
        },
        custom_crm_business_type(frm) {
            if (frm.doc.custom_crm_segment) {
                frm.set_value("custom_crm_segment", "");
            }
            renderOpportunityStatusBar(frm);
        },
        custom_crm_segment(frm) {
            renderOpportunityStatusBar(frm);
        },
    });

    frappe.ui.form.on("CRM Segment Assignment", {
        business_type(frm, cdt, cdn) {
            const row = locals[cdt][cdn];
            if (row.segment) {
                frappe.model.set_value(cdt, cdn, "segment", "");
            }
        },
        segment(frm) {
            renderPartyClassificationBar(frm);
        },
        is_primary(frm) {
            renderPartyClassificationBar(frm);
        },
    });

    function setupPartySegmentQueries(frm) {
        if (!frm.fields_dict.custom_crm_segments) return;
        frm.set_query("business_type", "custom_crm_segments", () => ({ filters: { is_active: 1 } }));
        frm.set_query("segment", "custom_crm_segments", (_doc, cdt, cdn) => {
            const row = locals[cdt][cdn] || {};
            const filters = { is_active: 1 };
            if (row.business_type) {
                filters.business_type = row.business_type;
            }
            return { filters };
        });
    }

    function setupOpportunitySegmentQueries(frm) {
        frm.set_query("custom_crm_business_type", () => ({ filters: { is_active: 1 } }));
        frm.set_query("custom_crm_segment", () => {
            const filters = { is_active: 1 };
            if (frm.doc.custom_crm_business_type) {
                filters.business_type = frm.doc.custom_crm_business_type;
            }
            return { filters };
        });
    }

    function renderPartyClassificationBar(frm) {
        injectCrmClassificationStyles();
        frm.page.inner_toolbar.find(".ol-crm-classification-bar").remove();
        const segments = frm.doc.custom_crm_segments || [];
        const businessTypes = unique(segments.map((row) => row.business_type).filter(Boolean));
        const segmentNames = unique(segments.map((row) => row.segment).filter(Boolean));
        const chips = [
            crmChip(__("CRM Type"), businessTypes.length ? businessTypes.join(" + ") : __("Not set"), "type"),
            crmChip(__("Segments"), segmentNames.length ? segmentNames.join(" + ") : __("Not set"), "segment"),
        ];
        if (frm.doc.customer_group) {
            chips.push(crmChip(__("Customer Group"), frm.doc.customer_group, "legacy"));
        }
        frm.page.inner_toolbar.prepend(`<div class="ol-crm-classification-bar">${chips.join("")}</div>`);
    }

    function renderOpportunityStatusBar(frm) {
        injectCrmClassificationStyles();
        frm.page.inner_toolbar.find(".ol-opportunity-status-bar").remove();
        const chips = [
            crmChip(__("Opportunity Status"), frm.doc.sales_stage || __("Not set"), "status"),
            crmChip(__("Type"), frm.doc.custom_crm_business_type || __("Not set"), "type"),
            crmChip(__("Segment"), frm.doc.custom_crm_segment || __("Not set"), "segment"),
        ];
        frm.page.inner_toolbar.prepend(`<div class="ol-opportunity-status-bar">${chips.join("")}</div>`);
    }

    async function renderCampaignHistory(frm) {
        if (frm.is_new()) return;
        injectCrmClassificationStyles();
        const wrapper = frm.dashboard && frm.dashboard.wrapper;
        if (!wrapper) return;
        wrapper.find(".ol-campaign-history-panel").remove();
        wrapper.append(`<div class="ol-campaign-history-panel"><div class="ol-history-loading">${__("Loading campaign history...")}</div></div>`);
        try {
            const res = await frappe.call({
                method: "orderlift.orderlift_crm.api.campaign.get_party_campaign_history",
                args: { party_type: frm.doctype, party_name: frm.doc.name },
            });
            const rows = res.message || [];
            wrapper.find(".ol-campaign-history-panel").html(campaignHistoryMarkup(rows));
            wrapper.find(".ol-campaign-history-panel [data-route-doctype]").on("click", function (event) {
                event.preventDefault();
                frappe.set_route("Form", $(this).data("route-doctype"), $(this).data("route-name"));
            });
        } catch (error) {
            console.error("Campaign history failed", error);
            wrapper.find(".ol-campaign-history-panel").html(`<div class="ol-history-empty">${__("Unable to load campaign history.")}</div>`);
        }
    }

    function campaignHistoryMarkup(rows) {
        if (!rows.length) {
            return `<div class="ol-history-head"><strong>${__("Campaign History")}</strong><span>${__("No campaign targets yet")}</span></div>`;
        }
        return `
            <div class="ol-history-head"><strong>${__("Campaign History")}</strong><span>${rows.length} ${__("target records")}</span></div>
            <div class="ol-history-table-wrap">
                <table class="ol-history-table">
                    <thead><tr><th>${__("Campaign")}</th><th>${__("Type")}</th><th>${__("Segment")}</th><th>${__("Follow-up")}</th><th>${__("Assigned")}</th><th>${__("Last Contact")}</th><th>${__("Docs")}</th></tr></thead>
                    <tbody>${rows.map(historyRow).join("")}</tbody>
                </table>
            </div>
        `;
    }

    function historyRow(row) {
        const docs = (row.docs || []).map((doc) => `
            <a href="#" data-route-doctype="${frappe.utils.escape_html(doc.doctype)}" data-route-name="${frappe.utils.escape_html(doc.name)}">
                ${frappe.utils.escape_html(doc.doctype)} <span>${frappe.utils.escape_html(doc.status || "-")}</span>
            </a>
        `).join("");
        return `
            <tr>
                <td><a href="#" data-route-doctype="Partner Campaign" data-route-name="${frappe.utils.escape_html(row.campaign)}"><strong>${frappe.utils.escape_html(row.campaign_name || row.campaign)}</strong><span>${frappe.utils.escape_html(row.campaign_date || "-")} · ${frappe.utils.escape_html(row.campaign_status || "-")}</span></a></td>
                <td>${frappe.utils.escape_html(row.business_type || "-")}</td>
                <td>${frappe.utils.escape_html(row.crm_segment || "-")}</td>
                <td>${frappe.utils.escape_html(row.target_status || "-")}</td>
                <td>${frappe.utils.escape_html(row.assigned_to || "-")}</td>
                <td>${frappe.utils.escape_html(row.last_contact_date || "-")}</td>
                <td><div class="ol-history-docs">${docs || `<span>${__("No outcome docs")}</span>`}</div></td>
            </tr>
        `;
    }

    function crmChip(label, value, tone) {
        const color = indicatorColor(label, value, tone);
        const displayValue = value === __("Not set") ? `${label} ${__("not set")}` : value;
        return `
            <span class="indicator-pill no-indicator-dot whitespace-nowrap ${color}">
                <span>${frappe.utils.escape_html(displayValue)}</span>
            </span>
        `;
    }

    function loadOpportunityStatusColors() {
        if (OPPORTUNITY_STATUS_COLORS) return Promise.resolve(OPPORTUNITY_STATUS_COLORS);
        if (!OPPORTUNITY_STATUS_COLORS_PROMISE) {
            OPPORTUNITY_STATUS_COLORS_PROMISE = frappe.call({
                method: "orderlift.orderlift_crm.api.status_control.get_status_control_data",
                args: { document_type: "Opportunity" },
            }).then((res) => {
                OPPORTUNITY_STATUS_COLORS = {};
                ((res.message && res.message.statuses) || []).forEach((row) => {
                    if (row.name) {
                        OPPORTUNITY_STATUS_COLORS[row.name] = statusColorClass(row.color);
                    }
                });
                return OPPORTUNITY_STATUS_COLORS;
            }).catch((error) => {
                console.error("Unable to load Opportunity status colors", error);
                OPPORTUNITY_STATUS_COLORS = {};
                return OPPORTUNITY_STATUS_COLORS;
            });
        }
        return OPPORTUNITY_STATUS_COLORS_PROMISE;
    }

    function indicatorColor(label, value, tone) {
        const cleanLabel = String(label || "").toLowerCase();
        const cleanValue = String(value || "").toLowerCase();
        if (!cleanValue || cleanValue.includes("not set")) return "gray";
        if (tone === "status" && OPPORTUNITY_STATUS_COLORS && OPPORTUNITY_STATUS_COLORS[value]) {
            return OPPORTUNITY_STATUS_COLORS[value];
        }
        if (tone === "type") {
            if (cleanValue.includes("installation")) return "purple";
            if (cleanValue.includes("distribution")) return "blue";
            return "gray";
        }
        if (tone === "segment") {
            if (cleanValue.includes("grossiste")) return "green";
            if (cleanValue.includes("revendeur")) return "blue";
            if (cleanValue.includes("installateur")) return "orange";
            if (cleanValue.includes("promoteur")) return "purple";
            if (cleanValue.includes("individu")) return "gray";
            return "green";
        }
        if (cleanLabel.includes("erp")) {
            if (["won", "completed", "converted"].some((status) => cleanValue.includes(status))) return "green";
            if (["lost", "cancelled"].some((status) => cleanValue.includes(status))) return "red";
            if (["closed", "on hold"].some((status) => cleanValue.includes(status))) return "gray";
            return "blue";
        }
        if (["lost", "blocked"].some((status) => cleanValue.includes(status))) return "red";
        if (["won", "project", "done", "completed"].some((status) => cleanValue.includes(status))) return "green";
        if (["study"].some((status) => cleanValue.includes(status))) return "purple";
        if (["visit", "negotiation"].some((status) => cleanValue.includes(status))) return "orange";
        return "blue";
    }

    function statusColorClass(color) {
        const clean = String(color || "").trim().toLowerCase();
        return ["gray", "blue", "green", "orange", "red", "purple"].includes(clean) ? clean : "blue";
    }

    function unique(values) {
        return [...new Set(values)];
    }

    function injectCrmClassificationStyles() {
        if (document.getElementById("ol-crm-classification-style")) return;
        const style = document.createElement("style");
        style.id = "ol-crm-classification-style";
        style.textContent = `
            .ol-crm-classification-bar, .ol-opportunity-status-bar { display:flex; gap:8px; flex-wrap:wrap; margin:0 0 8px; }
            .ol-campaign-history-panel { margin:12px 0; border:1px solid #e2e8f0; border-radius:12px; background:#fff; overflow:hidden; }
            .ol-history-head { display:flex; justify-content:space-between; gap:10px; align-items:center; padding:10px 12px; background:#f8fafc; border-bottom:1px solid #e2e8f0; }
            .ol-history-head strong { color:#111827; font-size:13px; }
            .ol-history-head span, .ol-history-loading, .ol-history-empty { color:#64748b; font-size:11px; font-weight:800; }
            .ol-history-loading, .ol-history-empty { padding:12px; }
            .ol-history-table-wrap { overflow-x:auto; }
            .ol-history-table { width:100%; min-width:880px; border-collapse:collapse; }
            .ol-history-table th { text-align:left; font-size:10px; color:#64748b; text-transform:uppercase; letter-spacing:.06em; padding:8px 10px; border-bottom:1px solid #e2e8f0; }
            .ol-history-table td { padding:9px 10px; border-bottom:1px solid #f1f5f9; vertical-align:top; font-size:12px; }
            .ol-history-table td a { color:#1d4ed8; font-weight:900; text-decoration:none; }
            .ol-history-table td a span, .ol-history-table td strong + span { display:block; color:#64748b; font-size:10px; font-weight:800; margin-top:2px; }
            .ol-history-docs { display:flex; gap:5px; flex-wrap:wrap; }
            .ol-history-docs a, .ol-history-docs > span { border-radius:999px; background:#eef2ff; color:#3730a3; padding:4px 7px; font-size:10px; font-weight:900; }
        `;
        document.head.appendChild(style);
    }
})();
