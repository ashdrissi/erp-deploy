frappe.pages["campaign-manager"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Campaign Manager"),
        single_column: true,
    });

    page.main.addClass("ocm-root");
    injectCampaignManagerStyles();
    renderCampaignManager(page);
    loadCampaignManagerData(page);
    applyCampaignManagerHeader(page);
};

frappe.pages["campaign-manager"].on_page_show = function (wrapper) {
    if (!wrapper.page) return;
    applyCampaignManagerHeader(wrapper.page);
    loadCampaignManagerData(wrapper.page);
};

const OCM_STATE = {
    campaigns: [],
    targets: [],
    statuses: [],
    kpis: {},
    selectedCampaign: null,
    targetSearch: "",
    targetPersonSearch: "",
    targetSegment: "All",
    targetType: "All",
    targetStatus: "All",
    targetOwner: "All",
    targetProgress: "All",
    campaignSearch: "",
    campaignStatus: "All",
    campaignOwner: "All",
    campaignChannel: "All",
};

function applyCampaignManagerHeader(page) {
    page.set_title(__("Campaign Manager"));
    setTimeout(() => {
        if (!frappe.breadcrumbs) return;
        frappe.breadcrumbs.clear();
        frappe.breadcrumbs.append_breadcrumb_element("/app/crm-dashboard", __("CRM"), "title-text");
        frappe.breadcrumbs.append_breadcrumb_element("", __("Campaign Manager"), "title-text");
        frappe.breadcrumbs.toggle(true);
    }, 0);
}

async function loadCampaignManagerData(page, campaign = null) {
    try {
        const selectedCampaign = campaign || OCM_STATE.selectedCampaign;
        const res = await frappe.call({
            method: "orderlift.orderlift_crm.api.campaign.get_manager_data",
            args: selectedCampaign ? { campaign: selectedCampaign } : {},
        });
        const data = res.message || {};
        OCM_STATE.campaigns = (data.campaigns || []).map(normalizeCampaignRow);
        OCM_STATE.kpis = data.kpis || {};
        OCM_STATE.statuses = (data.statuses || []).map((row) => row.name || row.status_label);
        OCM_STATE.selectedCampaign = data.selected_campaign || (OCM_STATE.campaigns[0] && OCM_STATE.campaigns[0].id) || null;
        OCM_STATE.targets = (data.targets || []).map(normalizeTargetRow);
        renderCampaignManager(page);
    } catch (error) {
        console.error("Campaign Manager failed", error);
        OCM_STATE.campaigns = [];
        OCM_STATE.targets = [];
        OCM_STATE.kpis = {};
        renderCampaignManager(page, true);
    }
}

function normalizeCampaignRow(row) {
    return {
        id: row.name,
        title: row.campaign_name || row.name,
        owner: row.campaign_owner || "",
        status: row.status || "Draft",
        channel: row.default_channel || "",
        period: [row.start_date, row.end_date].filter(Boolean).join(" - ") || "-",
        targets: row.target_count || 0,
        opportunities: row.opportunity_count || 0,
        quotationCount: row.quotation_count || 0,
        quotationAmount: row.quotation_amount || 0,
        salesCount: row.sales_order_count || 0,
        salesAmount: row.sales_order_amount || 0,
        updated: row.modified || "",
    };
}

function normalizeTargetRow(row) {
    return {
        id: row.name,
        company: row.display_name || row.party_name,
        refType: row.party_type,
        partyName: row.party_name,
        city: row.city || "",
        className: [row.business_type, row.crm_segment || row.partner_segment].filter(Boolean).join(" / "),
        businessType: row.business_type || "",
        segment: row.crm_segment || row.partner_segment || "",
        status: row.target_status || "",
        lastTouch: row.last_contact_date || "-",
        owner: row.assigned_to || "",
        contact: row.contact || "",
        contactPerson: row.contact_person_name || row.contact || "",
        prospect: row.prospect || "",
        opportunity: row.opportunity || "",
        quotation: row.quotation || "",
        salesOrder: row.sales_order || "",
    };
}

function renderCampaignManager(page, hasError = false) {
    const filteredCampaigns = currentCampaigns();
    const selectedCampaign = OCM_STATE.campaigns.find((row) => row.id === OCM_STATE.selectedCampaign);
    const filteredTargets = currentTargets();
    page.main.html(`
        <div class="ocm-shell">
            <section class="ocm-topbar">
                <div class="ocm-title-block">
                    <h1>${__("Campaign Manager")}</h1>
                    <p>${__("Select a campaign, filter targets, and convert them into CRM documents.")}</p>
                </div>
                <div class="ocm-hero-actions">
                    <button class="ocm-btn ocm-btn-ghost" data-route="crm-dashboard">${__("CRM")}</button>
                    <button class="ocm-btn ocm-btn-primary" data-new="1">${__("New Draft")}</button>
                </div>
            </section>

            <section class="ocm-manager-grid">
                <div class="ocm-left-stack">
                    <article class="ocm-panel ocm-kpi-panel ocm-accent-panel">
                        <div class="ocm-panel-head ocm-panel-head-compact">
                            <div>
                                <span class="ocm-section-kicker">${__("Overview")}</span>
                                <h2>${__("Campaign KPIs")}</h2>
                            </div>
                            <span class="ocm-chip">${selectedCampaign ? frappe.utils.escape_html(selectedCampaign.title) : __("No campaign selected")}</span>
                        </div>
                        <div class="ocm-kpi-grid">
                            ${campaignKpiCard("Campaigns", OCM_STATE.kpis.campaign_count || 0, __("open records"))}
                            ${campaignKpiCard("Opp", OCM_STATE.kpis.opportunity_count || 0, __("created"))}
                            ${campaignKpiCard("Quotes", OCM_STATE.kpis.quotation_count || 0, formatMoney(OCM_STATE.kpis.quotation_amount || 0))}
                            ${campaignKpiCard("SO", OCM_STATE.kpis.sales_order_count || 0, formatMoney(OCM_STATE.kpis.sales_order_amount || 0))}
                        </div>
                    </article>

                    <article class="ocm-panel ocm-campaign-panel ocm-selection-panel">
                        <div class="ocm-panel-head ocm-panel-head-compact">
                            <div>
                                <span class="ocm-section-kicker">${__("Campaigns")}</span>
                                <h2>${__("Campaign list")}</h2>
                            </div>
                            <button class="ocm-small-btn" data-new="1">${__("Create")}</button>
                        </div>
                        <div class="ocm-filter-bar">
                            <input id="ocm-campaign-search" type="search" placeholder="${__("Search campaign, owner, channel")}" value="${frappe.utils.escape_html(OCM_STATE.campaignSearch)}" />
                            <select id="ocm-campaign-status">${["All", ...new Set(OCM_STATE.campaigns.map((row) => row.status).filter(Boolean))].map((status) => `<option value="${frappe.utils.escape_html(status)}" ${status === OCM_STATE.campaignStatus ? "selected" : ""}>${frappe.utils.escape_html(__(status))}</option>`).join("")}</select>
                            ${selectMarkup("ocm-campaign-owner", campaignOwnerOptions(), OCM_STATE.campaignOwner)}
                            ${selectMarkup("ocm-campaign-channel", campaignChannelOptions(), OCM_STATE.campaignChannel)}
                            <button class="ocm-clear-btn" data-clear-campaign-filters="1">${__("Reset")}</button>
                        </div>
                        <div class="ocm-table-wrap ocm-campaign-results">${campaignTableMarkup(filteredCampaigns, hasError)}</div>
                    </article>
                </div>

                <article class="ocm-panel ocm-target-panel ocm-work-panel">
                    <div class="ocm-panel-head ocm-target-head">
                        <div>
                            <span class="ocm-section-kicker">${__("Targets")}</span>
                            <h2>${selectedCampaign ? frappe.utils.escape_html(selectedCampaign.title) : __("Targeted companies")}</h2>
                            <p>${__("Inline status changes and direct routes to created commercial documents.")}</p>
                        </div>
                        <div class="ocm-target-tools">
                            <div class="ocm-target-filter-grid">
                                <input id="ocm-target-search" type="search" placeholder="${__("Search company, city, document")}" value="${frappe.utils.escape_html(OCM_STATE.targetSearch)}" />
                                <input id="ocm-target-person-search" type="search" placeholder="${__("Search person, owner, contact")}" value="${frappe.utils.escape_html(OCM_STATE.targetPersonSearch)}" />
                                ${selectMarkup("ocm-target-type", targetTypeOptions(), OCM_STATE.targetType)}
                                ${selectMarkup("ocm-target-status", targetStatusOptions(), OCM_STATE.targetStatus)}
                                ${selectMarkup("ocm-target-owner", targetOwnerOptions(), OCM_STATE.targetOwner)}
                                ${selectMarkup("ocm-target-progress", targetProgressOptions(), OCM_STATE.targetProgress)}
                            </div>
                            <div class="ocm-target-filter-footer">
                                <div class="ocm-segment-tabs" aria-label="Target classification filters">
                                    ${segmentOptions().map((segment) => `<button class="${segment === OCM_STATE.targetSegment ? "active" : ""}" data-segment="${frappe.utils.escape_html(segment)}">${frappe.utils.escape_html(__(segment))}</button>`).join("")}
                                </div>
                                <button class="ocm-clear-btn" data-clear-target-filters="1">${__("Reset filters")}</button>
                            </div>
                        </div>
                    </div>
                    <div class="ocm-table-wrap ocm-target-table-wrap">
                        ${selectedCampaign ? `
                        <table class="ocm-table ocm-target-table">
                            <thead>
                                <tr>
                                    <th>${__("Company")}</th>
                                    <th>${__("Type")}</th>
                                    <th>${__("Status")}</th>
                                    <th>${__("Person / Owner")}</th>
                                    <th>${__("Links")}</th>
                                    <th>${__("Actions")}</th>
                                </tr>
                            </thead>
                            <tbody id="ocm-target-body">${targetRowsMarkup(filteredTargets)}</tbody>
                        </table>` : `<div class="ocm-empty-panel">${__("Select or create a campaign to manage targets.")}</div>`}
                    </div>
                </article>
            </section>
        </div>
    `);

    bindCampaignManagerEvents(page);
}

function bindCampaignManagerEvents(page) {
    page.main.find("[data-route]").on("click", function () {
        frappe.set_route($(this).data("route"));
    });
    page.main.find("[data-new]").on("click", function () {
        frappe.route_options = null;
        frappe.set_route("campaign-editor");
    });
    page.main.find("#ocm-campaign-search").on("input", function () {
        OCM_STATE.campaignSearch = String($(this).val() || "").trim().toLowerCase();
        updateCampaignResults(page);
    });
    page.main.find("#ocm-campaign-status").on("change", function () {
        OCM_STATE.campaignStatus = $(this).val();
        updateCampaignResults(page);
    });
    page.main.find("#ocm-campaign-owner").on("change", function () {
        OCM_STATE.campaignOwner = $(this).val();
        updateCampaignResults(page);
    });
    page.main.find("#ocm-campaign-channel").on("change", function () {
        OCM_STATE.campaignChannel = $(this).val();
        updateCampaignResults(page);
    });
    page.main.find("[data-clear-campaign-filters]").on("click", function () {
        OCM_STATE.campaignSearch = "";
        OCM_STATE.campaignStatus = "All";
        OCM_STATE.campaignOwner = "All";
        OCM_STATE.campaignChannel = "All";
        renderCampaignManager(page);
    });
    bindCampaignTableEvents(page);
    bindTargetFilterEvents(page);
    bindInlineTargetEvents(page);
}

function updateCampaignResults(page) {
    page.main.find(".ocm-campaign-results").html(campaignTableMarkup(currentCampaigns(), false));
    bindCampaignTableEvents(page);
}

function bindCampaignTableEvents(page) {
    page.main.find(".ocm-campaign-row").on("click", function () {
        const campaign = $(this).data("campaign");
        if (!campaign || campaign === OCM_STATE.selectedCampaign) return;
        OCM_STATE.selectedCampaign = campaign;
        resetTargetFilters();
        loadCampaignManagerData(page, campaign);
    });
    page.main.find(".ocm-edit-campaign").on("click", function (event) {
        event.stopPropagation();
        frappe.route_options = { campaign: $(this).data("campaign") };
        frappe.set_route("campaign-editor");
    });
}

function bindTargetFilterEvents(page) {
    page.main.find("#ocm-target-search").on("input", function () {
        OCM_STATE.targetSearch = String($(this).val() || "").trim().toLowerCase();
        updateTargetResults(page);
    });
    page.main.find("#ocm-target-person-search").on("input", function () {
        OCM_STATE.targetPersonSearch = String($(this).val() || "").trim().toLowerCase();
        updateTargetResults(page);
    });
    page.main.find("#ocm-target-type, #ocm-target-status, #ocm-target-owner, #ocm-target-progress").on("change", function () {
        OCM_STATE.targetType = page.main.find("#ocm-target-type").val();
        OCM_STATE.targetStatus = page.main.find("#ocm-target-status").val();
        OCM_STATE.targetOwner = page.main.find("#ocm-target-owner").val();
        OCM_STATE.targetProgress = page.main.find("#ocm-target-progress").val();
        updateTargetResults(page);
    });
    page.main.find("[data-segment]").on("click", function () {
        OCM_STATE.targetSegment = $(this).data("segment");
        page.main.find("[data-segment]").removeClass("active");
        $(this).addClass("active");
        updateTargetResults(page);
    });
    page.main.find("[data-clear-target-filters]").on("click", function () {
        resetTargetFilters();
        renderCampaignManager(page);
    });
}

function updateTargetResults(page) {
    const rows = currentTargets();
    page.main.find("#ocm-target-body").html(targetRowsMarkup(rows));
    page.main.find(".ocm-target-summary strong").text(rows.length);
    bindInlineTargetEvents(page);
}

function resetTargetFilters() {
    OCM_STATE.targetSearch = "";
    OCM_STATE.targetPersonSearch = "";
    OCM_STATE.targetSegment = "All";
    OCM_STATE.targetType = "All";
    OCM_STATE.targetStatus = "All";
    OCM_STATE.targetOwner = "All";
    OCM_STATE.targetProgress = "All";
}

function bindInlineTargetEvents(page) {
    page.main.find(".ocm-status-select").off("change").on("change", async function () {
        const targetId = $(this).data("target");
        const target = OCM_STATE.targets.find((row) => row.id === targetId);
        if (!target || !OCM_STATE.selectedCampaign) return;
        target.status = $(this).val();
        try {
            await frappe.call({
                method: "orderlift.orderlift_crm.api.campaign.update_target_status",
                args: { campaign: OCM_STATE.selectedCampaign, target_row: target.id, status: target.status },
            });
            frappe.show_alert({ message: __("Target status changed to {0}", [target.status]), indicator: "blue" });
        } catch (error) {
            console.error(error);
            loadCampaignManagerData(page, OCM_STATE.selectedCampaign);
        }
    });

    page.main.find("[data-action]").off("click").on("click", async function () {
        const targetId = $(this).data("target");
        const action = $(this).data("action");
        const target = OCM_STATE.targets.find((row) => row.id === targetId);
        if (!target || !OCM_STATE.selectedCampaign) return;
        const methodByAction = {
            "Create Prospect": "orderlift.orderlift_crm.api.campaign.create_prospect_from_target",
            "Create Opportunity": "orderlift.orderlift_crm.api.campaign.create_opportunity_from_target",
            "Create Quotation": "orderlift.orderlift_crm.api.campaign.create_quotation_from_target",
        };
        try {
            const res = await frappe.call({
                method: methodByAction[action],
                args: { campaign: OCM_STATE.selectedCampaign, target_row: target.id },
                freeze: true,
            });
            frappe.show_alert({ message: __("Created {0}", [res.message && res.message.name ? res.message.name : action]), indicator: "green" });
            loadCampaignManagerData(page, OCM_STATE.selectedCampaign);
        } catch (error) {
            console.error(error);
        }
    });

    page.main.find("[data-doctype][data-name]").off("click").on("click", function () {
        frappe.set_route("Form", $(this).data("doctype"), $(this).data("name"));
    });
}

function currentCampaigns() {
    return OCM_STATE.campaigns.filter((campaign) => {
        const matchesSearch = !OCM_STATE.campaignSearch || `${campaign.title} ${campaign.owner} ${campaign.channel} ${campaign.period}`.toLowerCase().includes(OCM_STATE.campaignSearch);
        const matchesStatus = OCM_STATE.campaignStatus === "All" || campaign.status === OCM_STATE.campaignStatus;
        const matchesOwner = OCM_STATE.campaignOwner === "All" || campaign.owner === OCM_STATE.campaignOwner;
        const matchesChannel = OCM_STATE.campaignChannel === "All" || campaign.channel === OCM_STATE.campaignChannel;
        return matchesSearch && matchesStatus && matchesOwner && matchesChannel;
    });
}

function currentTargets() {
    return OCM_STATE.targets.filter((target) => {
        const matchesSegment = OCM_STATE.targetSegment === "All" || target.className === OCM_STATE.targetSegment;
        const searchable = `${target.company} ${target.partyName} ${target.city} ${target.className} ${target.status} ${target.prospect} ${target.opportunity} ${target.quotation} ${target.salesOrder}`.toLowerCase();
        const personSearchable = `${target.contactPerson} ${target.contact} ${target.owner}`.toLowerCase();
        const matchesSearch = !OCM_STATE.targetSearch || searchable.includes(OCM_STATE.targetSearch);
        const matchesPerson = !OCM_STATE.targetPersonSearch || personSearchable.includes(OCM_STATE.targetPersonSearch);
        const matchesType = OCM_STATE.targetType === "All" || target.refType === OCM_STATE.targetType;
        const matchesStatus = OCM_STATE.targetStatus === "All" || target.status === OCM_STATE.targetStatus;
        const matchesOwner = OCM_STATE.targetOwner === "All" || target.owner === OCM_STATE.targetOwner;
        const matchesProgress = OCM_STATE.targetProgress === "All" || targetProgressLabel(target) === OCM_STATE.targetProgress;
        return matchesSegment && matchesSearch && matchesPerson && matchesType && matchesStatus && matchesOwner && matchesProgress;
    });
}

function selectMarkup(id, options, value) {
    return `<select id="${frappe.utils.escape_html(id)}">${options.map((option) => `<option value="${frappe.utils.escape_html(option)}" ${option === value ? "selected" : ""}>${frappe.utils.escape_html(__(option))}</option>`).join("")}</select>`;
}

function campaignOwnerOptions() {
    return ["All", ...new Set(OCM_STATE.campaigns.map((row) => row.owner).filter(Boolean))];
}

function campaignChannelOptions() {
    return ["All", ...new Set(OCM_STATE.campaigns.map((row) => row.channel).filter(Boolean))];
}

function targetTypeOptions() {
    return ["All", ...new Set(OCM_STATE.targets.map((row) => row.refType).filter(Boolean))];
}

function targetStatusOptions() {
    return ["All", ...new Set(OCM_STATE.targets.map((row) => row.status).filter(Boolean))];
}

function targetOwnerOptions() {
    return ["All", ...new Set(OCM_STATE.targets.map((row) => row.owner).filter(Boolean))];
}

function targetProgressOptions() {
    return ["All", "No document", "Has prospect", "Has opportunity", "Has quote", "Has sales order"];
}

function targetProgressLabel(target) {
    if (target.salesOrder) return "Has sales order";
    if (target.quotation) return "Has quote";
    if (target.opportunity) return "Has opportunity";
    if (target.prospect) return "Has prospect";
    return "No document";
}

function segmentOptions() {
    const segments = ["All", ...new Set(OCM_STATE.targets.map((row) => row.className).filter(Boolean))];
    if (!segments.includes(OCM_STATE.targetSegment)) OCM_STATE.targetSegment = "All";
    return segments;
}

function campaignKpiCard(label, value, hint) {
    return `
        <div class="ocm-kpi-card">
            <div class="ocm-kpi-value">${frappe.utils.escape_html(String(value))}</div>
            <div class="ocm-kpi-label">${frappe.utils.escape_html(__(label))}</div>
            <div class="ocm-kpi-hint">${frappe.utils.escape_html(String(hint))}</div>
        </div>
    `;
}

function campaignRow(campaign) {
    return `
        <tr class="ocm-campaign-row ${campaign.id === OCM_STATE.selectedCampaign ? "selected" : ""}" data-campaign="${frappe.utils.escape_html(campaign.id)}">
            <td><strong>${frappe.utils.escape_html(campaign.title)}</strong><span>${frappe.utils.escape_html(campaign.id)} - ${__("Owner")}: ${frappe.utils.escape_html(campaign.owner || "-")}</span></td>
            <td><span class="ocm-pill status-${String(campaign.status || "draft").toLowerCase().replace(/\s+/g, "-")}">${frappe.utils.escape_html(campaign.status)}</span></td>
            <td>${frappe.utils.escape_html(campaign.channel || "-")}</td>
            <td>${frappe.utils.escape_html(campaign.period || "-")}</td>
            <td>${campaign.targets}</td>
            <td>${campaign.opportunities}</td>
            <td>${campaign.quotationCount}<span>${formatMoney(campaign.quotationAmount)}</span></td>
            <td><button class="ocm-link-btn ocm-edit-campaign" data-campaign="${frappe.utils.escape_html(campaign.id)}">${campaign.salesCount} / ${formatMoney(campaign.salesAmount)}</button></td>
        </tr>
    `;
}

function campaignTableMarkup(rows, hasError) {
    if (!rows.length) {
        return `<div class="ocm-empty-panel">${hasError ? __("Unable to load campaigns right now.") : __("No Partner Campaign records match the current filters.")}</div>`;
    }
    return `
        <table class="ocm-table ocm-campaign-table">
            <thead>
                <tr>
                    <th>${__("Campaign")}</th>
                    <th>${__("Status")}</th>
                    <th>${__("Channel")}</th>
                    <th>${__("Period")}</th>
                    <th>${__("Targets")}</th>
                    <th>${__("Opp")}</th>
                    <th>${__("Quote")}</th>
                    <th>${__("SO / Edit")}</th>
                </tr>
            </thead>
            <tbody>${rows.map(campaignRow).join("")}</tbody>
        </table>
    `;
}

function targetRowsMarkup(rows) {
    if (!rows.length) {
        return `<tr><td colspan="6" class="ocm-empty-row">${__("No targets match the current filters.")}</td></tr>`;
    }
    return rows.map(targetRow).join("");
}

function targetRow(target) {
    return `
        <tr>
            <td><strong>${frappe.utils.escape_html(target.company)}</strong><span>${frappe.utils.escape_html(target.partyName || "")} - ${frappe.utils.escape_html(target.city || "-")}</span></td>
            <td>${frappe.utils.escape_html(target.refType || "")}<span>${frappe.utils.escape_html(target.className || "")}</span></td>
            <td>${targetStatusSelect(target)}</td>
            <td><strong>${frappe.utils.escape_html(target.contactPerson || "-")}</strong><span>${__("Owner")}: ${frappe.utils.escape_html(target.owner || "-")} - ${__("Last touch")}: ${frappe.utils.escape_html(target.lastTouch || "-")}</span></td>
            <td><div class="ocm-doc-links">${docChip("Prospect", "Prospect", target.prospect)}${docChip("Opp", "Opportunity", target.opportunity)}${docChip("QTN", "Quotation", target.quotation)}${docChip("SO", "Sales Order", target.salesOrder)}</div></td>
            <td>
                <div class="ocm-target-actions">
                    ${target.refType === "Lead" && !target.prospect ? `<button data-action="Create Prospect" data-target="${frappe.utils.escape_html(target.id)}">${__("Prospect")}</button>` : ""}
                    ${target.opportunity ? `<button data-doctype="Opportunity" data-name="${frappe.utils.escape_html(target.opportunity)}">${__("Open Opp")}</button>` : `<button data-action="Create Opportunity" data-target="${frappe.utils.escape_html(target.id)}">${__("Create Opp")}</button>`}
                    ${target.quotation ? `<button data-doctype="Quotation" data-name="${frappe.utils.escape_html(target.quotation)}">${__("Open Quote")}</button>` : `<button data-action="Create Quotation" data-target="${frappe.utils.escape_html(target.id)}">${__("Create Quote")}</button>`}
                </div>
            </td>
        </tr>
    `;
}

function targetStatusSelect(target) {
    const options = OCM_STATE.statuses.map((status) => `<option value="${frappe.utils.escape_html(status)}" ${status === target.status ? "selected" : ""}>${frappe.utils.escape_html(status)}</option>`).join("");
    return `<select class="ocm-status-select" data-target="${frappe.utils.escape_html(target.id)}">${options}</select>`;
}

function docChip(label, doctype, name) {
    if (!name) return "";
    return `<button class="ocm-doc-chip" data-doctype="${frappe.utils.escape_html(doctype)}" data-name="${frappe.utils.escape_html(name)}">${frappe.utils.escape_html(label)} ${frappe.utils.escape_html(name)}</button>`;
}

function formatMoney(value) {
    return `${Number(value || 0).toLocaleString()} DH`;
}

function injectCampaignManagerStyles() {
    if (document.getElementById("ocm-campaign-manager-style")) return;
    const style = document.createElement("style");
    style.id = "ocm-campaign-manager-style";
    style.textContent = `
        .ocm-root { background: linear-gradient(180deg, #eef6ff 0%, #f8fafc 42%, #f4f7fb 100%); }
        .ocm-shell { max-width: 1540px; margin: 0 auto; padding: 12px 18px 18px; color: #102033; }
        .ocm-topbar { display: flex; justify-content: space-between; gap: 18px; align-items: center; padding: 11px 14px; border-radius: 14px; background: #fff; border: 1px solid #dbe7f3; box-shadow: 0 8px 22px rgba(30,64,105,.05); }
        .ocm-title-block h1 { margin: 0; font-size: 20px; font-weight: 900; letter-spacing: -.025em; color: #102033; }
        .ocm-title-block p { margin: 2px 0 0; color: #61738a; font-size: 11px; font-weight: 800; line-height: 1.35; }
        .ocm-eyebrow, .ocm-section-kicker { display: inline-flex; font-size: 10px; font-weight: 900; letter-spacing: .12em; text-transform: uppercase; color: #67e8f9; }
        .ocm-hero-actions { display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
        .ocm-btn, .ocm-small-btn, .ocm-link-btn, .ocm-clear-btn { border: 0; border-radius: 999px; min-height: 38px; padding: 0 15px; font-weight: 900; cursor: pointer; }
        .ocm-btn-primary { background: #0f2f5f; color: #fff; box-shadow: 0 10px 24px rgba(15,47,95,.14); }
        .ocm-btn-ghost { background: #f8fafc; color: #0f2f5f; border: 1px solid #dbe7f3; }
        .ocm-manager-grid { display: grid; grid-template-columns: minmax(380px, .75fr) minmax(620px, 1.25fr); gap: 16px; margin-top: 16px; }
        .ocm-left-stack { display: grid; gap: 16px; }
        .ocm-panel { background: rgba(255,255,255,.98); border: 1px solid #dbe7f3; border-radius: 20px; box-shadow: 0 14px 38px rgba(30, 64, 105, .07); overflow: hidden; }
        .ocm-accent-panel { border-color: #bae6fd; background: linear-gradient(180deg, #f0f9ff, #fff); }
        .ocm-selection-panel { border-left: 5px solid #0f2f5f; }
        .ocm-work-panel { border-left: 5px solid #0891b2; }
        .ocm-panel-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 14px; padding: 16px; border-bottom: 1px solid #e5edf6; }
        .ocm-panel-head h2 { margin: 3px 0 0; font-size: 17px; letter-spacing: -0.02em; color: #102033; }
        .ocm-panel-head p { margin: 4px 0 0; max-width: 440px; color: #61738a; line-height: 1.45; font-size: 12px; }
        .ocm-chip { display: inline-flex; align-items: center; min-height: 26px; padding: 0 10px; border-radius: 999px; background: #e0f2fe; color: #075985; font-size: 11px; font-weight: 900; }
        .ocm-small-btn, .ocm-link-btn { background: #0f2f5f; color: #fff; min-height: 34px; }
        .ocm-kpi-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 10px; padding: 12px; }
        .ocm-kpi-card { min-height: 78px; padding: 13px; border-radius: 15px; background: #fff; border: 1px solid #d9e9f9; }
        .ocm-kpi-value { font-size: 24px; line-height: 1; font-weight: 900; letter-spacing: -0.04em; color: #0f2f5f; }
        .ocm-kpi-label { margin-top: 7px; font-weight: 900; color: #102033; font-size: 12px; }
        .ocm-kpi-hint { margin-top: 3px; color: #61738a; font-size: 11px; line-height: 1.3; }
        .ocm-filter-bar { display: grid; grid-template-columns: minmax(220px,1fr) 130px 150px 130px auto; gap: 8px; padding: 12px 12px 0; align-items: center; }
        .ocm-filter-bar input, .ocm-filter-bar select, .ocm-target-tools input, .ocm-target-tools select, .ocm-status-select { min-height: 36px; border: 1px solid #dbe7f3; border-radius: 999px; padding: 0 13px; font-weight: 800; outline: none; background: #fff; color: #102033; }
        .ocm-clear-btn { min-height: 34px; background: #f1f5f9; color: #0f2f5f; border: 1px solid #dbe7f3; font-size: 11px; }
        .ocm-table-wrap { overflow-x: auto; padding: 10px 12px 12px; }
        .ocm-target-table-wrap { max-height: 560px; overflow: auto; }
        .ocm-table { width: 100%; min-width: 760px; border-collapse: collapse; }
        .ocm-table th { position: sticky; top: 0; z-index: 1; text-align: left; padding: 9px 8px; background: #f8fafc; color: #64748b; font-size: 10px; text-transform: uppercase; letter-spacing: .08em; border-bottom: 1px solid #e2e8f0; }
        .ocm-table td { padding: 10px 8px; border-bottom: 1px solid #eef2f7; vertical-align: middle; color: #24364b; font-size: 12px; }
        .ocm-table td strong { display: block; color: #102033; font-size: 12px; }
        .ocm-table td span { display: block; margin-top: 2px; color: #64748b; font-size: 11px; }
        .ocm-campaign-row { cursor: pointer; }
        .ocm-campaign-row.selected td { background: #e0f2fe; box-shadow: inset 4px 0 0 #0891b2; }
        .ocm-pill { display: inline-flex !important; margin: 0 !important; align-items: center; border-radius: 999px; padding: 5px 8px; font-weight: 900; font-size: 11px !important; }
        .status-running { background: #dcfce7 !important; color: #166534 !important; }
        .status-ready, .status-draft, .status-paused { background: #fef3c7 !important; color: #92400e !important; }
        .status-closed { background: #e0e7ff !important; color: #3730a3 !important; }
        .ocm-target-head { align-items: center; }
        .ocm-target-tools { display: grid; gap: 9px; min-width: min(720px, 100%); }
        .ocm-target-filter-grid { display: grid; grid-template-columns: minmax(190px,1.2fr) minmax(190px,1.1fr) 112px 132px 136px 142px; gap: 8px; }
        .ocm-target-filter-footer { display: flex; align-items: center; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
        .ocm-segment-tabs { display: flex; flex-wrap: wrap; gap: 7px; justify-content: flex-end; }
        .ocm-segment-tabs button { border: 1px solid #dbe7f3; background: #fff; border-radius: 999px; min-height: 30px; padding: 0 10px; font-weight: 900; color: #536579; cursor: pointer; font-size: 11px; }
        .ocm-segment-tabs button.active { background: #0f2f5f; color: #fff; border-color: #0f2f5f; }
        .ocm-doc-links { display: flex; gap: 5px; flex-wrap: wrap; }
        .ocm-doc-chip { display: inline-flex; border: 0; border-radius: 8px; padding: 5px 7px; background: #eef6ff; color: #075985; font-weight: 900; font-size: 10px; cursor: pointer; }
        .ocm-target-actions { display: flex; gap: 6px; flex-wrap: nowrap; justify-content: flex-end; }
        .ocm-target-actions button { min-height: 30px; border: 1px solid #dbe7f3; background: #f8fafc; color: #0f2f5f; border-radius: 999px; padding: 0 9px; font-weight: 900; cursor: pointer; font-size: 11px; }
        .ocm-filter-bar input:focus-visible, .ocm-filter-bar select:focus-visible, .ocm-target-tools input:focus-visible, .ocm-target-tools select:focus-visible, .ocm-btn:focus-visible, .ocm-small-btn:focus-visible, .ocm-link-btn:focus-visible, .ocm-clear-btn:focus-visible, .ocm-segment-tabs button:focus-visible, .ocm-target-actions button:focus-visible, .ocm-doc-chip:focus-visible { outline: 3px solid rgba(8,145,178,.22); outline-offset: 2px; }
        .ocm-empty-row, .ocm-empty-panel { text-align: center; color: #64748b; padding: 28px 16px; font-weight: 800; }
        @media (max-width: 1320px) { .ocm-target-filter-grid { grid-template-columns: repeat(3, minmax(0,1fr)); } }
        @media (max-width: 1200px) { .ocm-manager-grid { grid-template-columns: 1fr; } }
        @media (max-width: 720px) { .ocm-shell { padding: 12px; } .ocm-topbar, .ocm-panel-head { flex-direction: column; align-items: stretch; } .ocm-kpi-grid { grid-template-columns: repeat(2, minmax(0,1fr)); } .ocm-target-tools { min-width: 0; } .ocm-filter-bar, .ocm-target-filter-grid { grid-template-columns: 1fr; } .ocm-segment-tabs, .ocm-hero-actions, .ocm-target-filter-footer { justify-content: flex-start; } }
    `;
    document.head.appendChild(style);
}
