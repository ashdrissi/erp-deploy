frappe.pages["campaign-manager"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Campaign Manager"),
        single_column: true,
    });

    wrapper.page = page;
    page.main.addClass("ocm2-root");
    injectCampaignManagerStyles();
    renderCampaignManager(page);
    loadCampaignManagerData(page);
    applyCampaignManagerHeader(page);
};

frappe.pages["campaign-manager"].on_page_show = function (wrapper) {
    if (!wrapper.page) return;
    applyCampaignManagerHeader(wrapper.page);
    loadCampaignManagerData(wrapper.page, OCM2_STATE.selectedCampaign);
};

const OCM2_STATE = {
    campaigns: [],
    targets: [],
    statuses: [],
    kpis: {},
    selectedCampaign: null,
    selectedCampaignDoc: {},
    loading: false,
    error: "",
    campaignSearch: "",
    campaignStatus: "All",
    campaignChannel: "All",
    showDeletedCampaigns: false,
    targetSearch: "",
    targetType: "All",
    targetStatus: "All",
    targetOwner: "All",
    targetProgress: "All",
    targetSegment: "All",
    expandedTargets: new Set(),
};

let OCM2_TARGET_SEARCH_TIMER = null;
let OCM2_CAMPAIGN_SEARCH_TIMER = null;

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
    OCM2_STATE.loading = true;
    OCM2_STATE.error = "";
    renderCampaignManager(page);

    try {
        const selectedCampaign = campaign || OCM2_STATE.selectedCampaign;
        const res = await frappe.call({
            method: "orderlift.orderlift_crm.api.campaign.get_manager_data",
            args: Object.assign({ include_archived: OCM2_STATE.showDeletedCampaigns ? 1 : 0 }, selectedCampaign ? { campaign: selectedCampaign } : {}),
        });
        const data = res.message || {};
        OCM2_STATE.campaigns = (data.campaigns || []).map(normalizeCampaignRow);
        OCM2_STATE.kpis = data.kpis || {};
        OCM2_STATE.statuses = (data.statuses || []).map((row) => row.name || row.status_label).filter(Boolean);
        OCM2_STATE.selectedCampaign = data.selected_campaign || (OCM2_STATE.campaigns[0] && OCM2_STATE.campaigns[0].id) || null;
        OCM2_STATE.selectedCampaignDoc = normalizeSelectedCampaignDoc(data.selected_campaign_doc || {});
        OCM2_STATE.targets = (data.targets || []).map(normalizeTargetRow);
    } catch (error) {
        console.error("Campaign Manager failed", error);
        OCM2_STATE.error = __("Unable to load campaign data. Refresh and try again.");
        OCM2_STATE.campaigns = [];
        OCM2_STATE.targets = [];
        OCM2_STATE.kpis = {};
        OCM2_STATE.selectedCampaignDoc = {};
    } finally {
        OCM2_STATE.loading = false;
        renderCampaignManager(page);
    }
}

function normalizeCampaignRow(row) {
    return {
        id: row.name,
        title: row.campaign_name || row.name,
        owner: row.campaign_owner || "",
        status: row.status || "Draft",
        channel: normalizeAction(row.campaign_action_type || row.default_channel),
        period: [row.start_date, row.end_date].filter(Boolean).join(" - ") || "-",
        targets: row.target_count || 0,
        opportunities: row.opportunity_count || 0,
        quotationCount: row.quotation_count || 0,
        quotationAmount: row.quotation_amount || 0,
        salesCount: row.sales_order_count || 0,
        salesAmount: row.sales_order_amount || 0,
        updated: row.modified || "",
        archived: Number(row.archived || 0) ? 1 : 0,
    };
}

function normalizeSelectedCampaignDoc(row) {
    return {
        id: row.name || "",
        title: row.campaign_name || row.name || "",
        channel: normalizeAction(row.campaign_action_type || row.default_channel),
        whatsappMode: normalizeWhatsAppMode(row.whatsapp_mode),
        visitDefaultDate: row.visit_default_date || row.campaign_date || "",
    };
}

function normalizeTargetRow(row) {
    const classification = [row.business_type, row.crm_segment || row.partner_segment].filter(Boolean).join(" / ");
    return {
        id: row.name,
        company: row.display_name || row.party_name,
        refType: row.party_type || "",
        partyName: row.party_name || "",
        city: row.city || "",
        classification,
        businessType: row.business_type || "",
        segment: row.crm_segment || row.partner_segment || "",
        status: row.target_status || "",
        lastTouch: row.last_contact_date || "-",
        owner: row.assigned_to || "",
        note: row.target_note || "",
        contact: row.contact || "",
        contactPerson: row.contact_person_name || row.contact || "",
        email: row.email || "",
        mobile: row.mobile_no || "",
        lastOutreachType: row.last_outreach_type || "",
        lastOutreachDate: row.last_outreach_date || "",
        lastEmailQueue: row.last_email_queue || "",
        lastWhatsAppMode: row.last_whatsapp_mode || "",
        visitDate: row.visit_date || "",
        visitStatus: row.visit_status || "",
        visitTodo: row.visit_todo || "",
        prospect: row.prospect || "",
        opportunity: row.opportunity || "",
        quotation: row.quotation || "",
        salesOrder: row.sales_order || "",
    };
}

function renderCampaignManager(page) {
    const campaigns = currentCampaigns();
    const targets = currentTargets();
    const selected = OCM2_STATE.campaigns.find((row) => row.id === OCM2_STATE.selectedCampaign) || null;
    const progress = targetProgressSummary(OCM2_STATE.targets);

    page.main.html(`
        <div class="ocm2-shell">
            <section class="ocm2-command-bar">
                <div class="ocm2-command-main">
                    <span class="ocm2-overline">${__("Campaign Manager")}</span>
                    <h1>${selected ? frappe.utils.escape_html(selected.title) : __("Select a campaign")}</h1>
                    <p>${selected ? frappe.utils.escape_html([selected.status, selected.channel || __("No channel"), selected.period].filter(Boolean).join(" / ")) : __("Select a campaign to review target progress and create linked CRM documents.")}</p>
                </div>
                <div class="ocm2-command-stats">
                    ${miniStat(__("Targets"), OCM2_STATE.targets.length)}
                    ${miniStat(__("Touched"), progress.touched)}
                    ${miniStat(__("Pipeline"), progress.pipeline)}
                    ${miniStat(__("Converted"), progress.converted)}
                </div>
                <div class="ocm2-actions">
                    <button type="button" class="ocm2-btn ocm2-btn-ghost" data-route="crm-dashboard">${buttonContent("arrow-left", __("CRM"))}</button>
                    <button type="button" class="ocm2-btn ocm2-btn-ghost" data-refresh="1">${buttonContent("refresh", __("Refresh"))}</button>
                    <button type="button" class="ocm2-btn ocm2-btn-primary" data-new-campaign="1">${buttonContent("plus", __("New Campaign"))}</button>
                </div>
            </section>

            ${OCM2_STATE.error ? `<div class="ocm2-error" role="alert">${frappe.utils.escape_html(OCM2_STATE.error)}</div>` : ""}

            <section class="ocm2-layout">
                <aside class="ocm2-rail" aria-label="${frappe.utils.escape_html(__("Campaign list"))}">
                    <div class="ocm2-panel-head">
                        <div>
                            <span>${__("Campaigns")}</span>
                            <h2 class="ocm2-campaign-visible-count">${campaigns.length} ${__("visible")}</h2>
                        </div>
                        <button type="button" class="ocm2-icon-btn" data-clear-campaign-filters="1" aria-label="${frappe.utils.escape_html(__("Reset campaign filters"))}">${__("Reset")}</button>
                    </div>
                    <div class="ocm2-rail-filters">
                        <label><span>${__("Search")}</span><input id="ocm2-campaign-search" type="search" value="${frappe.utils.escape_html(OCM2_STATE.campaignSearch)}" placeholder="${frappe.utils.escape_html(__("Name, owner, channel"))}" /></label>
                        <div class="ocm2-filter-pair">
                            ${selectMarkup("ocm2-campaign-status", ["All", ...unique(OCM2_STATE.campaigns.map((row) => row.status))], OCM2_STATE.campaignStatus, __("Status"))}
                            ${selectMarkup("ocm2-campaign-channel", ["All", ...unique(OCM2_STATE.campaigns.map((row) => row.channel))], OCM2_STATE.campaignChannel, __("Channel"))}
                        </div>
                        <label class="ocm2-deleted-toggle"><input type="checkbox" data-show-deleted-campaigns ${OCM2_STATE.showDeletedCampaigns ? "checked" : ""}> <span>${__("Show deleted campaigns")}</span></label>
                    </div>
                    <div class="ocm2-campaign-list">
                        ${OCM2_STATE.loading ? skeletonCards(4) : campaigns.length ? campaigns.map(campaignCard).join("") : emptyPanel(__("No campaigns match the current filters."))}
                    </div>
                </aside>

                <main class="ocm2-workspace" aria-label="${frappe.utils.escape_html(__("Selected campaign workspace"))}">
                    ${selected ? selectedCampaignMarkup(selected, targets, progress) : emptyWorkspaceMarkup()}
                </main>
            </section>
        </div>
    `);

    bindCampaignManagerEvents(page);
}

function selectedCampaignMarkup(campaign, targets, progress) {
    return `
        <article class="ocm2-selected-card">
            <div class="ocm2-selected-main">
                <div>
                    <span class="ocm2-overline">${__("Selected Campaign")}</span>
                    <h2>${frappe.utils.escape_html(campaign.title)}</h2>
                    <p>${frappe.utils.escape_html([campaign.owner || __("No owner"), campaign.channel || __("No channel"), campaign.period].filter(Boolean).join(" / "))}</p>
                </div>
                <div class="ocm2-selected-actions">
                    <span class="ocm2-status ${statusClass(campaign.status)}">${frappe.utils.escape_html(campaign.status)}</span>
                    <button type="button" class="ocm2-btn ocm2-btn-ghost" data-edit-campaign="${frappe.utils.escape_html(campaign.id)}">${buttonContent("edit", __("Edit Builder"))}</button>
                    ${campaign.archived ? `<button type="button" class="ocm2-btn ocm2-btn-primary" data-restore-campaign="${frappe.utils.escape_html(campaign.id)}">${buttonContent("restore", __("Restore"))}</button>` : `<button type="button" class="ocm2-btn ocm2-btn-danger" data-archive-campaign="${frappe.utils.escape_html(campaign.id)}">${buttonContent("archive", __("Delete"))}</button>`}
                    ${campaign.channel === "Email" ? `<button type="button" class="ocm2-btn ocm2-btn-ghost" data-bulk-schedule-email="1">${buttonContent("clock", __("Schedule Visible Emails"))}</button>` : ""}
                    ${campaign.channel === "Visit" ? `<button type="button" class="ocm2-btn ocm2-btn-ghost" data-bulk-visit-todos="1">${buttonContent("calendar-check", __("Create Visible Visit ToDos"))}</button>` : ""}
                </div>
            </div>
        </article>

        <article class="ocm2-target-panel">
            <div class="ocm2-target-toolbar">
                <div>
                    <span class="ocm2-overline">${__("Targets")}</span>
                    <h3 class="ocm2-target-visible-count">${targets.length} ${__("visible targets")}</h3>
                </div>
                <button type="button" class="ocm2-icon-btn" data-clear-target-filters="1">${__("Reset filters")}</button>
            </div>
            <div class="ocm2-target-filters">
                <label class="ocm2-wide-filter"><span>${__("Search")}</span><input id="ocm2-target-search" type="search" value="${frappe.utils.escape_html(OCM2_STATE.targetSearch)}" placeholder="${frappe.utils.escape_html(__("Company, contact, city, document"))}" /></label>
                ${selectMarkup("ocm2-target-type", ["All", ...unique(OCM2_STATE.targets.map((row) => row.refType))], OCM2_STATE.targetType, __("Party"))}
                ${selectMarkup("ocm2-target-status", ["All", ...unique(OCM2_STATE.statuses.concat(OCM2_STATE.targets.map((row) => row.status)))], OCM2_STATE.targetStatus, __("Status"))}
                ${selectMarkup("ocm2-target-owner", ["All", ...unique(OCM2_STATE.targets.map((row) => row.owner))], OCM2_STATE.targetOwner, __("Owner"))}
                ${selectMarkup("ocm2-target-progress", targetProgressOptions(), OCM2_STATE.targetProgress, __("Progress"))}
            </div>
            <div class="ocm2-segment-bar" aria-label="${frappe.utils.escape_html(__("Segment filters"))}">
                ${segmentOptions().map((segment) => `<button type="button" class="${segment === OCM2_STATE.targetSegment ? "active" : ""}" data-target-segment="${frappe.utils.escape_html(segment)}">${frappe.utils.escape_html(__(segment))}</button>`).join("")}
            </div>
            <div class="ocm2-target-list">
                ${OCM2_STATE.loading ? skeletonCards(5) : targets.length ? targets.map(targetCard).join("") : emptyPanel(__("No targets match the selected filters."))}
            </div>
        </article>
    `;
}

function miniStat(label, value) {
    return `<span class="ocm2-mini-stat"><em>${frappe.utils.escape_html(label)}</em><strong>${frappe.utils.escape_html(String(value == null ? 0 : value))}</strong></span>`;
}

function emptyWorkspaceMarkup() {
    return `
        <article class="ocm2-empty-workspace">
            <span class="ocm2-overline">${__("No Campaign")}</span>
            <h2>${__("Create or select a campaign")}</h2>
            <p>${__("Campaign targets, progress, and conversion actions will appear here once a campaign is selected.")}</p>
            <button type="button" class="ocm2-btn ocm2-btn-primary" data-new-campaign="1">${buttonContent("plus", __("New Campaign"))}</button>
        </article>
    `;
}

function bindCampaignManagerEvents(page) {
    page.main.find("[data-route]").on("click", function () {
        frappe.set_route($(this).data("route"));
    });
    page.main.find("[data-refresh]").on("click", function () {
        loadCampaignManagerData(page, OCM2_STATE.selectedCampaign);
    });
    page.main.find("[data-new-campaign]").on("click", function () {
        frappe.route_options = null;
        frappe.set_route("campaign-editor");
    });
    page.main.find("[data-edit-campaign]").on("click", function (event) {
        event.stopPropagation();
        openCampaignBuilder($(this).data("edit-campaign"));
    });
    page.main.find("[data-archive-campaign]").on("click", function (event) {
        event.stopPropagation();
        archiveSelectedCampaign(page, $(this).data("archive-campaign"));
    });
    page.main.find("[data-restore-campaign]").on("click", function (event) {
        event.stopPropagation();
        restoreSelectedCampaign(page, $(this).data("restore-campaign"));
    });
    page.main.find("[data-show-deleted-campaigns]").on("change", function () {
        OCM2_STATE.showDeletedCampaigns = this.checked;
        OCM2_STATE.selectedCampaign = null;
        OCM2_STATE.expandedTargets.clear();
        loadCampaignManagerData(page, null);
    });
    bindCampaignSelectionEvents(page);

    page.main.find("#ocm2-campaign-search").on("input", function () {
        OCM2_STATE.campaignSearch = String($(this).val() || "").trim().toLowerCase();
        clearTimeout(OCM2_CAMPAIGN_SEARCH_TIMER);
        OCM2_CAMPAIGN_SEARCH_TIMER = setTimeout(() => updateCampaignList(page), 180);
    });
    page.main.find("#ocm2-campaign-status").on("change", function () {
        OCM2_STATE.campaignStatus = $(this).val();
        updateCampaignList(page);
    });
    page.main.find("#ocm2-campaign-channel").on("change", function () {
        OCM2_STATE.campaignChannel = $(this).val();
        updateCampaignList(page);
    });
    page.main.find("[data-clear-campaign-filters]").on("click", function () {
        OCM2_STATE.campaignSearch = "";
        OCM2_STATE.campaignStatus = "All";
        OCM2_STATE.campaignChannel = "All";
        renderCampaignManager(page);
    });

    page.main.find("#ocm2-target-search").on("input", function () {
        OCM2_STATE.targetSearch = String($(this).val() || "").trim().toLowerCase();
        clearTimeout(OCM2_TARGET_SEARCH_TIMER);
        OCM2_TARGET_SEARCH_TIMER = setTimeout(() => updateTargetList(page), 180);
    });
    page.main.find("#ocm2-target-type, #ocm2-target-status, #ocm2-target-owner, #ocm2-target-progress").on("change", function () {
        OCM2_STATE.targetType = page.main.find("#ocm2-target-type").val();
        OCM2_STATE.targetStatus = page.main.find("#ocm2-target-status").val();
        OCM2_STATE.targetOwner = page.main.find("#ocm2-target-owner").val();
        OCM2_STATE.targetProgress = page.main.find("#ocm2-target-progress").val();
        updateTargetList(page);
    });
    page.main.find("[data-target-segment]").on("click", function () {
        OCM2_STATE.targetSegment = $(this).data("target-segment");
        page.main.find("[data-target-segment]").removeClass("active");
        $(this).addClass("active");
        updateTargetList(page);
    });
    page.main.find("[data-clear-target-filters]").on("click", function () {
        resetTargetFilters();
        renderCampaignManager(page);
    });
    page.main.find("[data-bulk-visit-todos]").on("click", function () {
        bulkCreateVisitTodos(page);
    });
    page.main.find("[data-bulk-schedule-email]").on("click", function () {
        promptScheduleEmail(page, null, currentTargets().map((row) => row.id));
    });

    bindTargetBackendEvents(page);
}

function bindCampaignSelectionEvents(page) {
    page.main.find("[data-campaign]").off("click").on("click", function () {
        const campaign = $(this).data("campaign");
        if (!campaign || campaign === OCM2_STATE.selectedCampaign) return;
        OCM2_STATE.selectedCampaign = campaign;
        OCM2_STATE.expandedTargets.clear();
        resetTargetFilters();
        loadCampaignManagerData(page, campaign);
    });
    page.main.find("[data-open-campaign]").off("click").on("click", function (event) {
        event.stopPropagation();
        openCampaignBuilder($(this).data("open-campaign"));
    });
}

function updateCampaignList(page) {
    const campaigns = currentCampaigns();
    page.main.find(".ocm2-campaign-visible-count").text(`${campaigns.length} ${__("visible")}`);
    page.main.find(".ocm2-campaign-list").html(campaigns.length ? campaigns.map(campaignCard).join("") : emptyPanel(__("No campaigns match the current filters.")));
    bindCampaignSelectionEvents(page);
}

function updateTargetList(page) {
    const targets = currentTargets();
    page.main.find(".ocm2-target-visible-count").text(`${targets.length} ${__("visible targets")}`);
    page.main.find(".ocm2-target-list").html(targets.length ? targets.map(targetCard).join("") : emptyPanel(__("No targets match the selected filters.")));
    bindTargetBackendEvents(page);
}

function bindTargetBackendEvents(page) {
    page.main.find("[data-toggle-target-card]").off("click").on("click", function () {
        const targetId = $(this).data("toggle-target-card");
        if (!targetId) return;
        if (OCM2_STATE.expandedTargets.has(targetId)) {
            OCM2_STATE.expandedTargets.delete(targetId);
        } else {
            OCM2_STATE.expandedTargets.add(targetId);
        }
        updateTargetList(page);
    });

    page.main.find(".ocm2-target-status").off("change").on("change", async function () {
        const targetId = $(this).data("target");
        const target = OCM2_STATE.targets.find((row) => row.id === targetId);
        if (!target || !OCM2_STATE.selectedCampaign) return;
        const nextStatus = $(this).val();
        target.status = nextStatus;
        try {
            await frappe.call({
                method: "orderlift.orderlift_crm.api.campaign.update_target_status",
                args: { campaign: OCM2_STATE.selectedCampaign, target_row: target.id, status: nextStatus },
            });
            frappe.show_alert({ message: __("Target status changed to {0}", [nextStatus]), indicator: "blue" });
            loadCampaignManagerData(page, OCM2_STATE.selectedCampaign);
        } catch (error) {
            console.error(error);
            loadCampaignManagerData(page, OCM2_STATE.selectedCampaign);
        }
    });

    page.main.find("[data-target-action]").off("click").on("click", async function () {
        const targetId = $(this).data("target");
        const action = $(this).data("target-action");
        const methodByAction = {
            prospect: "orderlift.orderlift_crm.api.campaign.create_prospect_from_target",
            opportunity: "orderlift.orderlift_crm.api.campaign.create_opportunity_from_target",
            quotation: "orderlift.orderlift_crm.api.campaign.create_quotation_from_target",
        };
        const method = methodByAction[action];
        if (!method || !targetId || !OCM2_STATE.selectedCampaign) return;
        try {
            const res = await frappe.call({
                method,
                args: { campaign: OCM2_STATE.selectedCampaign, target_row: targetId },
                freeze: true,
            });
            const created = res.message && res.message.name ? res.message.name : __("document");
            frappe.show_alert({ message: __("Created {0}", [created]), indicator: "green" });
            loadCampaignManagerData(page, OCM2_STATE.selectedCampaign);
        } catch (error) {
            console.error(error);
        }
    });

    page.main.find("[data-campaign-action]").off("click").on("click", async function () {
        if (this.disabled) return;
        const targetId = $(this).data("target");
        const action = $(this).data("campaign-action");
        if (!targetId || !OCM2_STATE.selectedCampaign) return;
        if (action === "schedule-email") {
            promptScheduleEmail(page, targetId);
            return;
        }
        await runCampaignAction(page, targetId, action);
    });

    page.main.find("[data-visit-date]").off("change").on("change", async function () {
        const targetId = $(this).data("visit-date");
        const visitDate = $(this).val();
        if (!targetId || !OCM2_STATE.selectedCampaign) return;
        try {
            await frappe.call({
                method: "orderlift.orderlift_crm.api.campaign.update_target_visit",
                args: { campaign: OCM2_STATE.selectedCampaign, target_row: targetId, visit_date: visitDate, visit_status: visitDate ? "Planned" : "" },
            });
            frappe.show_alert({ message: __("Visit date saved"), indicator: "blue" });
            loadCampaignManagerData(page, OCM2_STATE.selectedCampaign);
        } catch (error) {
            console.error(error);
            loadCampaignManagerData(page, OCM2_STATE.selectedCampaign);
        }
    });

    page.main.find("[data-doctype][data-name]").off("click").on("click", function () {
        frappe.set_route("Form", $(this).data("doctype"), $(this).data("name"));
    });

    page.main.find("[data-target-note]").off("change blur").on("change blur", async function () {
        const targetId = $(this).data("target-note");
        const target = OCM2_STATE.targets.find((row) => row.id === targetId);
        if (!target || !OCM2_STATE.selectedCampaign) return;
        const nextNote = String($(this).val() || "");
        if (nextNote === target.note) return;
        target.note = nextNote;
        try {
            await frappe.call({
                method: "orderlift.orderlift_crm.api.campaign.update_target_note",
                args: { campaign: OCM2_STATE.selectedCampaign, target_row: target.id, note: nextNote },
            });
            frappe.show_alert({ message: __("Target note saved"), indicator: "blue" });
        } catch (error) {
            console.error(error);
            loadCampaignManagerData(page, OCM2_STATE.selectedCampaign);
        }
    });
}

async function runCampaignAction(page, targetId, action) {
    const actionMap = {
        "send-email": { method: "orderlift.orderlift_crm.api.campaign.send_campaign_email", args: {} },
        "send-whatsapp-api": { method: "orderlift.orderlift_crm.api.campaign.send_campaign_whatsapp_template", args: {} },
        "mark-whatsapp": { method: "orderlift.orderlift_crm.api.campaign.mark_target_outreach", args: { outreach_type: "WhatsApp" } },
        "mark-call": { method: "orderlift.orderlift_crm.api.campaign.mark_target_outreach", args: { outreach_type: "Call" } },
        "mark-other": { method: "orderlift.orderlift_crm.api.campaign.mark_target_outreach", args: { outreach_type: "Other" } },
        "create-visit-todo": { method: "orderlift.orderlift_crm.api.campaign.create_visit_todo", args: {} },
    };
    if (action === "open-whatsapp") {
        try {
            const proceed = await ensureCampaignActionReady("WhatsApp", [targetId], __("Open WhatsApp for this target?"));
            if (!proceed) return;
            const res = await frappe.call({
                method: "orderlift.orderlift_crm.api.campaign.get_whatsapp_click_to_chat",
                args: { campaign: OCM2_STATE.selectedCampaign, target_row: targetId },
                freeze: true,
            });
            const data = res.message || {};
            if (data.url) window.open(data.url, "_blank", "noopener");
            frappe.show_alert({ message: __("WhatsApp opened. Mark contacted after sending."), indicator: "green" });
        } catch (error) {
            console.error(error);
        }
        return;
    }
    const config = actionMap[action];
    if (!config) return;
    try {
        if (["send-email", "send-whatsapp-api"].includes(action)) {
            const actionType = action === "send-email" ? "Email" : "WhatsApp";
            const label = action === "send-email" ? __("Send email to this target?") : __("Send WhatsApp template to this target?");
            const proceed = await ensureCampaignActionReady(actionType, [targetId], label);
            if (!proceed) return;
        }
        await frappe.call({
            method: config.method,
            args: { campaign: OCM2_STATE.selectedCampaign, target_row: targetId, ...config.args },
            freeze: true,
        });
        frappe.show_alert({ message: __("Campaign action completed"), indicator: "green" });
        loadCampaignManagerData(page, OCM2_STATE.selectedCampaign);
    } catch (error) {
        console.error(error);
    }
}

function promptScheduleEmail(page, targetId = null, targetRows = null) {
    const rows = (targetRows || [targetId]).filter(Boolean);
    if (!rows.length) {
        frappe.show_alert({ message: __("No visible targets to schedule."), indicator: "orange" });
        return;
    }
    ensureCampaignActionReady("Email", rows, targetRows ? __("Schedule email for visible targets?") : __("Schedule email for this target?")).then((proceed) => {
        if (!proceed) return;
        promptScheduleEmailAfterPreflight(page, targetId, targetRows);
    });
}

function promptScheduleEmailAfterPreflight(page, targetId = null, targetRows = null) {
    frappe.prompt(
        [{ fieldname: "scheduled_at", fieldtype: "Datetime", label: __("Send After"), reqd: 1 }],
        async (values) => {
            try {
                let result = null;
                if (targetRows) {
                    const res = await frappe.call({
                        method: "orderlift.orderlift_crm.api.campaign.bulk_schedule_campaign_email",
                        args: { campaign: OCM2_STATE.selectedCampaign, target_rows: JSON.stringify(targetRows), scheduled_at: values.scheduled_at },
                        freeze: true,
                    });
                    result = res.message;
                } else {
                    const res = await frappe.call({
                        method: "orderlift.orderlift_crm.api.campaign.send_campaign_email",
                        args: { campaign: OCM2_STATE.selectedCampaign, target_row: targetId, scheduled_at: values.scheduled_at },
                        freeze: true,
                    });
                    result = { success: [{ result: res.message }], errors: [] };
                }
                showBulkActionResult(result, __("Email scheduled"));
                loadCampaignManagerData(page, OCM2_STATE.selectedCampaign);
            } catch (error) {
                console.error(error);
            }
        },
        __("Schedule Campaign Email"),
        __("Schedule")
    );
}

async function ensureCampaignActionReady(actionType, targetRows, confirmationMessage) {
    if (!OCM2_STATE.selectedCampaign) return false;
    try {
        const res = await frappe.call({
            method: "orderlift.orderlift_crm.api.campaign.get_campaign_send_preflight",
            args: { campaign: OCM2_STATE.selectedCampaign, target_rows: JSON.stringify(targetRows || []), action_type: actionType },
            freeze: true,
        });
        const preflight = res.message || {};
        const blockers = preflightMessages(preflight, "blockers");
        if (blockers.length) {
            frappe.msgprint({
                title: __("Campaign is not ready"),
                indicator: "red",
                message: `<ul>${blockers.slice(0, 12).map((message) => `<li>${frappe.utils.escape_html(message)}</li>`).join("")}</ul>`,
            });
            return false;
        }
        const warnings = preflightMessages(preflight, "warnings");
        const detail = `${preflight.ready_count || 0}/${preflight.target_count || 0} ${__("targets ready")}`;
        const message = warnings.length
            ? `${frappe.utils.escape_html(confirmationMessage)}<br><br><strong>${frappe.utils.escape_html(detail)}</strong><ul>${warnings.slice(0, 8).map((warning) => `<li>${frappe.utils.escape_html(warning)}</li>`).join("")}</ul>`
            : `${frappe.utils.escape_html(confirmationMessage)}<br><br><strong>${frappe.utils.escape_html(detail)}</strong>`;
        return await confirmAsync(message);
    } catch (error) {
        console.error(error);
        return false;
    }
}

function preflightMessages(preflight, fieldname) {
    const campaignMessages = preflight[`campaign_${fieldname}`] || [];
    const targetMessages = (preflight.targets || []).flatMap((target) => (target[fieldname] || []).map((message) => `${target.label}: ${message}`));
    return campaignMessages.concat(targetMessages);
}

function confirmAsync(message) {
    return new Promise((resolve) => {
        frappe.confirm(message, () => resolve(true), () => resolve(false));
    });
}

function showBulkActionResult(result, fallbackMessage) {
    const success = (result && result.success) || [];
    const errors = (result && result.errors) || [];
    if (!errors.length) {
        frappe.show_alert({ message: `${fallbackMessage}: ${success.length || 1}`, indicator: "green" });
        return;
    }
    frappe.msgprint({
        title: fallbackMessage,
        indicator: errors.length ? "orange" : "green",
        message: `
            <div>${frappe.utils.escape_html(__("Success"))}: <strong>${success.length}</strong></div>
            <div>${frappe.utils.escape_html(__("Errors"))}: <strong>${errors.length}</strong></div>
            <ul>${errors.slice(0, 8).map((row) => `<li>${frappe.utils.escape_html(row.label || row.target || "")}: ${frappe.utils.escape_html(row.error || "")}</li>`).join("")}</ul>
        `,
    });
}

async function bulkCreateVisitTodos(page) {
    const targetRows = currentTargets().filter((row) => row.visitDate).map((row) => row.id);
    if (!targetRows.length) {
        frappe.show_alert({ message: __("No visible targets have visit dates."), indicator: "orange" });
        return;
    }
    try {
        await frappe.call({
            method: "orderlift.orderlift_crm.api.campaign.bulk_create_visit_todos",
            args: { campaign: OCM2_STATE.selectedCampaign, target_rows: JSON.stringify(targetRows) },
            freeze: true,
        });
        frappe.show_alert({ message: __("Visit ToDos created or updated"), indicator: "green" });
        loadCampaignManagerData(page, OCM2_STATE.selectedCampaign);
    } catch (error) {
        console.error(error);
    }
}

function archiveSelectedCampaign(page, campaign) {
    if (!campaign) return;
    frappe.confirm(
        __("Delete this campaign? It will move to Deleted Campaigns and can be restored later."),
        async () => {
            try {
                await frappe.call({
                    method: "orderlift.orderlift_crm.api.campaign.archive_campaign",
                    args: { campaign },
                    freeze: true,
                });
                frappe.show_alert({ message: __("Campaign deleted"), indicator: "green" });
                OCM2_STATE.selectedCampaign = null;
                OCM2_STATE.expandedTargets.clear();
                await loadCampaignManagerData(page, null);
            } catch (error) {
                console.error(error);
            }
        }
    );
}

async function restoreSelectedCampaign(page, campaign) {
    if (!campaign) return;
    try {
        await frappe.call({
            method: "orderlift.orderlift_crm.api.campaign.restore_campaign",
            args: { campaign },
            freeze: true,
        });
        frappe.show_alert({ message: __("Campaign restored"), indicator: "green" });
        OCM2_STATE.showDeletedCampaigns = false;
        await loadCampaignManagerData(page, campaign);
    } catch (error) {
        console.error(error);
    }
}

function currentCampaigns() {
    return OCM2_STATE.campaigns.filter((campaign) => {
        const searchable = `${campaign.title} ${campaign.owner} ${campaign.channel} ${campaign.period}`.toLowerCase();
        return (!OCM2_STATE.campaignSearch || searchable.includes(OCM2_STATE.campaignSearch))
            && (OCM2_STATE.campaignStatus === "All" || campaign.status === OCM2_STATE.campaignStatus)
            && (OCM2_STATE.campaignChannel === "All" || campaign.channel === OCM2_STATE.campaignChannel);
    });
}

function currentTargets() {
    return OCM2_STATE.targets.filter((target) => {
        const searchable = `${target.company} ${target.partyName} ${target.city} ${target.classification} ${target.status} ${target.contactPerson} ${target.email} ${target.mobile} ${target.owner} ${target.note} ${target.visitDate} ${target.visitTodo} ${target.prospect} ${target.opportunity} ${target.quotation} ${target.salesOrder}`.toLowerCase();
        return (!OCM2_STATE.targetSearch || searchable.includes(OCM2_STATE.targetSearch))
            && (OCM2_STATE.targetType === "All" || target.refType === OCM2_STATE.targetType)
            && (OCM2_STATE.targetStatus === "All" || target.status === OCM2_STATE.targetStatus)
            && (OCM2_STATE.targetOwner === "All" || target.owner === OCM2_STATE.targetOwner)
            && (OCM2_STATE.targetProgress === "All" || targetProgressLabel(target) === OCM2_STATE.targetProgress)
            && (OCM2_STATE.targetSegment === "All" || target.classification === OCM2_STATE.targetSegment || target.segment === OCM2_STATE.targetSegment);
    });
}

function campaignCard(campaign) {
    const selected = campaign.id === OCM2_STATE.selectedCampaign;
    return `
        <button type="button" class="ocm2-campaign-card ${selected ? "active" : ""}" data-campaign="${frappe.utils.escape_html(campaign.id)}">
            <span class="ocm2-status ${statusClass(campaign.status)}">${frappe.utils.escape_html(campaign.status)}</span>
            ${campaign.archived ? `<span class="ocm2-status deleted">${frappe.utils.escape_html(__("Deleted"))}</span>` : ""}
            <strong>${frappe.utils.escape_html(campaign.title)}</strong>
            <small>${frappe.utils.escape_html(campaign.owner || __("No owner"))} / ${frappe.utils.escape_html(campaign.channel || __("No channel"))}</small>
            <span class="ocm2-card-metrics">
                <em>${campaign.targets} ${__("targets")}</em>
                <em>${campaign.opportunities} ${__("opp")}</em>
                <em>${campaign.salesCount} ${__("SO")}</em>
            </span>
            <span class="ocm2-card-footer"><span>${frappe.utils.escape_html(campaign.period)}</span><span data-open-campaign="${frappe.utils.escape_html(campaign.id)}">${__("Edit")}</span></span>
        </button>
    `;
}

function targetCard(target) {
    const campaignAction = normalizeAction(OCM2_STATE.selectedCampaignDoc.channel);
    const expanded = OCM2_STATE.expandedTargets.has(target.id);
    const targetSummary = [target.partyName, target.city, target.classification].filter(Boolean).join(" / ") || "-";
    return `
        <article class="ocm2-target-card ${expanded ? "is-expanded" : "is-collapsed"}">
            <div class="ocm2-target-main">
                <div class="ocm2-target-copy">
                    <span class="ocm2-party">${frappe.utils.escape_html(target.refType || "-")}</span>
                    <h4>${frappe.utils.escape_html(target.company || "-")}</h4>
                    <p title="${frappe.utils.escape_html(targetSummary)}">${frappe.utils.escape_html(targetSummary)}</p>
                </div>
                <div class="ocm2-target-controls">
                    ${targetStatusSelect(target)}
                    <button type="button" class="ocm2-target-toggle" data-toggle-target-card="${frappe.utils.escape_html(target.id)}" aria-expanded="${expanded ? "true" : "false"}">${buttonContent(expanded ? "chevron-up" : "chevron-down", expanded ? __("Hide") : __("Details"))}</button>
                </div>
            </div>
            <div class="ocm2-target-details" ${expanded ? "" : "hidden"}>
                <div class="ocm2-target-meta">
                    <span><strong>${__("Contact")}</strong>${frappe.utils.escape_html(target.contactPerson || "-")}</span>
                    <span><strong>${__("Email")}</strong>${frappe.utils.escape_html(target.email || __("Missing"))}</span>
                    <span><strong>${__("Mobile")}</strong>${frappe.utils.escape_html(target.mobile || __("Missing"))}</span>
                    <span><strong>${__("Owner")}</strong>${frappe.utils.escape_html(target.owner || "-")}</span>
                    <span><strong>${__("Last touch")}</strong>${frappe.utils.escape_html(target.lastTouch || "-")}</span>
                    ${campaignAction === "Visit" ? `<span><strong>${__("Visit")}</strong>${frappe.utils.escape_html(target.visitDate || __("No date"))}${target.visitTodo ? ` / ${frappe.utils.escape_html(target.visitTodo)}` : ""}</span>` : ""}
                </div>
                ${campaignAction === "Visit" ? visitControls(target) : ""}
                <label class="ocm2-target-note"><span>${__("Note")}</span><textarea data-target-note="${frappe.utils.escape_html(target.id)}" placeholder="${frappe.utils.escape_html(__("Add a note for this target"))}">${frappe.utils.escape_html(target.note || "")}</textarea></label>
                <div class="ocm2-outreach-row">
                    ${campaignActionButtons(target, campaignAction)}
                </div>
                <div class="ocm2-doc-row">
                    ${docChip("Prospect", "Prospect", target.prospect)}
                    ${docChip("Opp", "Opportunity", target.opportunity)}
                    ${docChip("Quote", "Quotation", target.quotation)}
                    ${docChip("SO", "Sales Order", target.salesOrder)}
                    ${!target.prospect && target.refType === "Lead" ? `<button type="button" data-target-action="prospect" data-target="${frappe.utils.escape_html(target.id)}">${buttonContent("user-plus", __("Create Prospect"))}</button>` : ""}
                    ${target.opportunity ? "" : `<button type="button" data-target-action="opportunity" data-target="${frappe.utils.escape_html(target.id)}">${buttonContent("target", __("Create Opp"))}</button>`}
                    ${target.quotation ? "" : `<button type="button" data-target-action="quotation" data-target="${frappe.utils.escape_html(target.id)}">${buttonContent("file-text", __("Create Quote"))}</button>`}
                </div>
            </div>
        </article>
    `;
}

function campaignActionButtons(target, action) {
    if (action === "Email") {
        const emailDisabledTitle = target.email ? "" : `title="${frappe.utils.escape_html(__("Missing email address"))}"`;
        return `
            <button type="button" ${target.email ? "" : "disabled"} ${emailDisabledTitle} data-campaign-action="send-email" data-target="${frappe.utils.escape_html(target.id)}">${buttonContent("mail", __("Send Email"))}</button>
            <button type="button" ${target.email ? "" : "disabled"} ${emailDisabledTitle} data-campaign-action="schedule-email" data-target="${frappe.utils.escape_html(target.id)}">${buttonContent("clock", __("Schedule Email"))}</button>
        `;
    }
    if (action === "WhatsApp") {
        const mobileDisabledTitle = target.mobile ? "" : `title="${frappe.utils.escape_html(__("Missing mobile number"))}"`;
        return `
            <button type="button" ${target.mobile ? "" : "disabled"} ${mobileDisabledTitle} data-campaign-action="open-whatsapp" data-target="${frappe.utils.escape_html(target.id)}">${buttonContent("message-circle", __("Open WhatsApp"))}</button>
            ${isAutomatedWhatsAppMode(OCM2_STATE.selectedCampaignDoc.whatsappMode) ? `<button type="button" ${target.mobile ? "" : "disabled"} ${mobileDisabledTitle} data-campaign-action="send-whatsapp-api" data-target="${frappe.utils.escape_html(target.id)}">${buttonContent("send", __("Send Template"))}</button>` : ""}
            <button type="button" data-campaign-action="mark-whatsapp" data-target="${frappe.utils.escape_html(target.id)}">${buttonContent("check", __("Mark Contacted"))}</button>
        `;
    }
    if (action === "Call") {
        return `<button type="button" data-campaign-action="mark-call" data-target="${frappe.utils.escape_html(target.id)}">${buttonContent("phone", __("Mark Called"))}</button>`;
    }
    if (action === "Visit") {
        return `<button type="button" ${target.visitDate ? "" : "disabled"} data-campaign-action="create-visit-todo" data-target="${frappe.utils.escape_html(target.id)}">${buttonContent("calendar-check", target.visitTodo ? __("Update Visit ToDo") : __("Create Visit ToDo"))}</button>`;
    }
    return `<button type="button" data-campaign-action="mark-other" data-target="${frappe.utils.escape_html(target.id)}">${buttonContent("check", __("Mark Other Done"))}</button>`;
}

function visitControls(target) {
    return `
        <div class="ocm2-visit-row">
            <label><span>${__("Visit date")}</span><input type="date" data-visit-date="${frappe.utils.escape_html(target.id)}" value="${frappe.utils.escape_html(target.visitDate || OCM2_STATE.selectedCampaignDoc.visitDefaultDate || "")}" /></label>
            ${target.visitTodo ? docChip("ToDo", "ToDo", target.visitTodo) : `<span class="ocm2-muted">${__("No visit ToDo yet")}</span>`}
        </div>
    `;
}

function targetStatusSelect(target) {
    const options = unique(OCM2_STATE.statuses.concat(target.status ? [target.status] : []));
    if (!options.length) return `<span class="ocm2-muted">${__("No statuses")}</span>`;
    return `<select class="ocm2-target-status" data-target="${frappe.utils.escape_html(target.id)}">${options.map((status) => `<option value="${frappe.utils.escape_html(status)}" ${status === target.status ? "selected" : ""}>${frappe.utils.escape_html(status)}</option>`).join("")}</select>`;
}

function docChip(label, doctype, name) {
    if (!name) return "";
    const iconByDoctype = {
        Prospect: "users",
        Opportunity: "target",
        Quotation: "file-text",
        "Sales Order": "shopping-bag",
        ToDo: "check-square",
    };
    return `<button type="button" class="ocm2-doc-chip" data-doctype="${frappe.utils.escape_html(doctype)}" data-name="${frappe.utils.escape_html(name)}">${buttonContent(iconByDoctype[doctype] || "file-text", `${label} ${shortName(name)}`)}</button>`;
}

function buttonContent(icon, label) {
    return `${iconSvg(icon)}<span>${frappe.utils.escape_html(label)}</span>`;
}

function iconSvg(icon) {
    const icons = {
        archive: `<path d="M21 8v13H3V8"></path><path d="M1 3h22v5H1Z"></path><path d="M10 12h4"></path>`,
        "arrow-left": `<path d="M19 12H5"></path><path d="m12 19-7-7 7-7"></path>`,
        calendar: `<path d="M8 2v4"></path><path d="M16 2v4"></path><rect x="3" y="4" width="18" height="18" rx="2"></rect><path d="M3 10h18"></path>`,
        "calendar-check": `<path d="M8 2v4"></path><path d="M16 2v4"></path><rect x="3" y="4" width="18" height="18" rx="2"></rect><path d="M3 10h18"></path><path d="m9 16 2 2 4-5"></path>`,
        check: `<path d="m20 6-11 11-5-5"></path>`,
        "check-square": `<rect x="3" y="3" width="18" height="18" rx="2"></rect><path d="m9 12 2 2 4-5"></path>`,
        "chevron-down": `<path d="m6 9 6 6 6-6"></path>`,
        "chevron-up": `<path d="m18 15-6-6-6 6"></path>`,
        clock: `<circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path>`,
        edit: `<path d="M12 20h9"></path><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"></path>`,
        "file-text": `<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"></path><path d="M14 2v6h6"></path><path d="M8 13h8"></path><path d="M8 17h5"></path>`,
        mail: `<rect x="3" y="5" width="18" height="14" rx="2"></rect><path d="m3 7 9 6 9-6"></path>`,
        "message-circle": `<path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.7 8.7 0 0 1-4-.9L3 20l1.2-4.4a8.4 8.4 0 1 1 16.8-4.1Z"></path>`,
        phone: `<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.2a2 2 0 0 1 2.1-.5c.9.3 1.8.6 2.8.7A2 2 0 0 1 22 16.9Z"></path>`,
        plus: `<path d="M12 5v14"></path><path d="M5 12h14"></path>`,
        refresh: `<path d="M21 12a9 9 0 0 1-15 6.7"></path><path d="M3 12a9 9 0 0 1 15-6.7"></path><path d="M3 5v6h6"></path><path d="M21 19v-6h-6"></path>`,
        restore: `<path d="M3 12a9 9 0 1 0 3-6.7"></path><path d="M3 4v6h6"></path>`,
        send: `<path d="m22 2-7 20-4-9-9-4Z"></path><path d="M22 2 11 13"></path>`,
        "shopping-bag": `<path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z"></path><path d="M3 6h18"></path><path d="M16 10a4 4 0 0 1-8 0"></path>`,
        target: `<circle cx="12" cy="12" r="9"></circle><circle cx="12" cy="12" r="5"></circle><circle cx="12" cy="12" r="1"></circle>`,
        "user-plus": `<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M19 8v6"></path><path d="M22 11h-6"></path>`,
        users: `<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M22 21v-2a4 4 0 0 0-3-3.9"></path><path d="M16 3.1a4 4 0 0 1 0 7.8"></path>`,
    };
    const paths = icons[icon] || icons.check;
    return `<svg class="ocm2-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${paths}</svg>`;
}

function selectMarkup(id, options, value, label) {
    return `
        <label>
            <span>${frappe.utils.escape_html(label)}</span>
            <select id="${frappe.utils.escape_html(id)}">
                ${options.filter(Boolean).map((option) => `<option value="${frappe.utils.escape_html(option)}" ${option === value ? "selected" : ""}>${frappe.utils.escape_html(__(option))}</option>`).join("")}
            </select>
        </label>
    `;
}

function kpiCard(label, value, hint) {
    return `<div class="ocm2-kpi"><span>${frappe.utils.escape_html(label)}</span><strong>${frappe.utils.escape_html(String(value))}</strong><em>${frappe.utils.escape_html(hint)}</em></div>`;
}

function progressCard(label, value, hint) {
    return `<div class="ocm2-progress-card"><span>${frappe.utils.escape_html(label)}</span><strong>${frappe.utils.escape_html(String(value))}</strong><em>${frappe.utils.escape_html(hint)}</em></div>`;
}

function skeletonCards(count) {
    return Array.from({ length: count }, () => `<div class="ocm2-skeleton"></div>`).join("");
}

function emptyPanel(message) {
    return `<div class="ocm2-empty">${frappe.utils.escape_html(message)}</div>`;
}

function targetProgressSummary(targets) {
    return {
        touched: targets.filter((target) => !["", "To Contact"].includes(target.status)).length,
        pipeline: targets.filter((target) => target.prospect || target.opportunity).length,
        converted: targets.filter((target) => target.salesOrder).length,
    };
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
    const options = ["All", ...unique(OCM2_STATE.targets.map((row) => row.classification || row.segment))];
    if (!options.includes(OCM2_STATE.targetSegment)) OCM2_STATE.targetSegment = "All";
    return options;
}

function resetTargetFilters() {
    OCM2_STATE.targetSearch = "";
    OCM2_STATE.targetType = "All";
    OCM2_STATE.targetStatus = "All";
    OCM2_STATE.targetOwner = "All";
    OCM2_STATE.targetProgress = "All";
    OCM2_STATE.targetSegment = "All";
}

function openCampaignBuilder(campaign) {
    frappe.route_options = campaign ? { campaign } : null;
    frappe.set_route("campaign-editor");
}

function statusClass(status) {
    const clean = String(status || "draft").toLowerCase();
    if (["running", "closed"].includes(clean)) return `is-${clean}`;
    if (["ready", "paused"].includes(clean)) return `is-${clean}`;
    return "is-draft";
}

function normalizeAction(value) {
    return ["Email", "WhatsApp", "Call", "Visit", "Other"].includes(value) ? value : "WhatsApp";
}

function normalizeWhatsAppMode(value) {
    if (["Twilio", "Custom Webhook"].includes(value)) return value;
    if (value === "Automated API") return "Custom Webhook";
    return "Manual Click-to-Chat";
}

function isAutomatedWhatsAppMode(value) {
    return ["Twilio", "Custom Webhook", "Automated API"].includes(value);
}

function shortName(name) {
    const parts = String(name || "").split("-").filter(Boolean);
    return parts.length ? parts[parts.length - 1] : String(name || "").slice(-6);
}

function unique(values) {
    return [...new Set((values || []).filter(Boolean))];
}

function formatMoney(value) {
    if (window.orderlift?.formatCurrency) return window.orderlift.formatCurrency(value);
    return Number(value || 0).toLocaleString();
}

function injectCampaignManagerStyles() {
    if (document.getElementById("ocm2-campaign-manager-style")) return;
    const style = document.createElement("style");
    style.id = "ocm2-campaign-manager-style";
    style.textContent = `
        .ocm2-root { background: linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%); }
        .ocm2-shell { max-width: 1840px; min-height: calc(100vh - 56px); margin: 0 auto; padding: 10px 14px 18px; color: #0f172a; }
        .ocm2-command-bar { display: grid; grid-template-columns: minmax(260px, 1fr) minmax(280px, .58fr) auto; gap: 10px; align-items: center; padding: 10px 12px; border: 1px solid #dbe7f3; border-left: 4px solid #0891b2; border-radius: 14px; background: linear-gradient(135deg, #ffffff 0%, #f8fbff 100%); box-shadow: 0 8px 24px rgba(15, 23, 42, .055); }
        .ocm2-command-main { min-width: 0; }
        .ocm2-command-main h1 { margin: 1px 0; color: #0f172a; font-size: 18px; line-height: 1.08; letter-spacing: -.035em; font-weight: 900; overflow-wrap: anywhere; }
        .ocm2-command-main p { margin: 0; color: #475569; font-size: 11px; line-height: 1.35; font-weight: 780; }
        .ocm2-command-stats { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 6px; }
        .ocm2-mini-stat { min-height: 36px; display: grid; align-content: center; justify-items: center; gap: 1px; border: 1px solid #dbe7f3; border-radius: 10px; background: rgba(255,255,255,.9); padding: 4px 7px; text-align: center; }
        .ocm2-mini-stat em { color: #64748b; font-size: 8px; font-style: normal; font-weight: 900; text-transform: uppercase; letter-spacing: .08em; }
        .ocm2-mini-stat strong { color: #0f172a; font-size: 14px; line-height: 1; font-weight: 900; }
        .ocm2-title-block span, .ocm2-overline { display: inline-flex; color: #8be8f1; font-size: 10px; font-weight: 900; letter-spacing: .13em; text-transform: uppercase; }
        .ocm2-title-block h1 { margin: 4px 0 3px; color: #fff; font-size: 25px; line-height: 1.1; letter-spacing: -.035em; font-weight: 900; }
        .ocm2-title-block p { margin: 0; max-width: 760px; color: rgba(255,255,255,.75); font-size: 12px; line-height: 1.45; font-weight: 750; }
        .ocm2-actions { display: grid; grid-template-columns: repeat(3, minmax(76px, 104px)); gap: 6px; justify-content: end; align-items: stretch; min-width: 0; }
        .ocm2-actions .ocm2-btn-primary { grid-column: auto; }
        .ocm2-selected-actions { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; justify-content: flex-end; max-width: 540px; min-width: 0; }
        .ocm2-doc-row, .ocm2-outreach-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(82px, 112px)); gap: 5px; justify-content: center; align-items: center; min-width: 0; }
        .ocm2-btn, .ocm2-icon-btn, .ocm2-doc-row button, .ocm2-outreach-row button, .ocm2-segment-bar button { min-height: 28px; display: inline-flex; align-items: center; justify-content: center; gap: 4px; max-width: 100%; min-width: 0; border: 0; border-radius: 10px; padding: 3px 8px; font-size: 10px; line-height: 1.05; font-weight: 900; white-space: normal; text-align: center; cursor: pointer; transition: transform .18s ease, border-color .18s ease, background .18s ease, color .18s ease; }
        .ocm2-btn > span, .ocm2-doc-row button > span, .ocm2-outreach-row button > span, .ocm2-target-controls button > span { min-width: 0; max-width: 82px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; text-overflow: ellipsis; }
        .ocm2-icon { width: 12px; height: 12px; flex: 0 0 12px; }
        .ocm2-btn:hover, .ocm2-icon-btn:hover, .ocm2-doc-row button:hover, .ocm2-outreach-row button:hover, .ocm2-segment-bar button:hover { transform: translateY(-1px); }
        .ocm2-btn-primary { background: #083344; color: #fff; box-shadow: 0 7px 16px rgba(8,51,68,.16); }
        .ocm2-btn-ghost { background: #f8fafc; color: #0f3b61; border: 1px solid #d8e2ee; }
        .ocm2-btn-danger { background: #fff1f2; color: #be123c; border: 1px solid #fecdd3; }
        .ocm2-error { margin-top: 12px; border: 1px solid #fecdd3; background: #fff1f2; color: #9f1239; border-radius: 14px; padding: 11px 13px; font-weight: 850; }
        .ocm2-kpi-grid { display: none; }
        .ocm2-kpi, .ocm2-progress-card { display: grid; align-content: center; justify-items: center; gap: 2px; min-height: 52px; padding: 7px 8px; border: 1px solid #dfe8f3; border-radius: 14px; background: #fff; text-align: center; box-shadow: 0 7px 20px rgba(15,23,42,.045); }
        .ocm2-kpi span, .ocm2-progress-card span, .ocm2-panel-head span, .ocm2-target-toolbar span { color: #64748b; font-size: 9px; font-weight: 900; text-transform: uppercase; letter-spacing: .1em; }
        .ocm2-kpi strong, .ocm2-progress-card strong { color: #0f172a; font-size: 16px; line-height: 1; font-weight: 900; letter-spacing: -.04em; }
        .ocm2-kpi em, .ocm2-progress-card em { color: #64748b; font-size: 9px; font-style: normal; font-weight: 750; }
        .ocm2-layout { display: grid; grid-template-columns: 310px minmax(0,1fr); gap: 10px; margin-top: 10px; align-items: start; }
        .ocm2-rail, .ocm2-selected-card, .ocm2-target-panel, .ocm2-empty-workspace { border: 1px solid #dbe7f3; border-radius: 14px; background: rgba(255,255,255,.98); box-shadow: 0 10px 24px rgba(15,23,42,.055); overflow: hidden; }
        .ocm2-rail { position: sticky; top: 68px; max-height: calc(100vh - 92px); display: grid; grid-template-rows: auto auto minmax(0,1fr); }
        .ocm2-panel-head, .ocm2-target-toolbar { display: flex; justify-content: space-between; gap: 10px; align-items: center; padding: 9px 10px; border-bottom: 1px solid #e7edf5; background: #fff; }
        .ocm2-panel-head h2, .ocm2-target-toolbar h3 { margin: 2px 0 0; color: #0f172a; font-size: 14px; font-weight: 900; letter-spacing: -.025em; }
        .ocm2-icon-btn { height: 26px; min-height: 26px; background: #f1f5f9; color: #0f3b61; border: 1px solid #d9e3ee; font-size: 10px; }
        .ocm2-rail-filters, .ocm2-target-filters { display: grid; gap: 6px; padding: 8px 10px; border-bottom: 1px solid #e7edf5; background: #f8fafc; }
        .ocm2-filter-pair { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 8px; }
        .ocm2-rail label, .ocm2-target-filters label { display: grid; gap: 4px; min-width: 0; margin: 0; }
        .ocm2-rail label span, .ocm2-target-filters label span { color: #64748b; font-size: 9px; font-weight: 900; text-transform: uppercase; letter-spacing: .08em; }
        .ocm2-rail input:not([type="checkbox"]), .ocm2-rail select, .ocm2-target-filters input:not([type="checkbox"]), .ocm2-target-filters select, .ocm2-target-status { height: 30px; min-height: 30px; max-height: 30px; width: 100%; border: 1px solid #d8e2ee; border-radius: 9px; background: #f8fafc; color: #102033; padding: 0 8px; font-size: 10.5px; line-height: 30px; font-weight: 800; outline: none; }
        .ocm2-rail input:not([type="checkbox"]):focus, .ocm2-rail select:focus, .ocm2-target-filters input:not([type="checkbox"]):focus, .ocm2-target-filters select:focus, .ocm2-target-status:focus { border-color: #0891b2; background: #fff; box-shadow: 0 0 0 4px rgba(8,145,178,.1); }
        .ocm2-deleted-toggle { display: flex !important; grid-template-columns: none !important; align-items: center; gap: 7px; color: #475569; font-size: 10px; font-weight: 900; }
        .ocm2-deleted-toggle input { appearance: none !important; -webkit-appearance: none !important; display: inline-grid !important; place-content: center !important; width: 14px !important; height: 14px !important; min-width: 14px !important; min-height: 14px !important; max-height: 14px !important; flex: 0 0 14px; margin: 0; padding: 0; border: 1.5px solid #94a3b8 !important; border-radius: 4px !important; background: #fff !important; background-image: none !important; background-repeat: no-repeat !important; box-shadow: none !important; cursor: pointer; }
        .ocm2-deleted-toggle input::before { content: ""; width: 7px; height: 7px; transform: scale(0); transition: transform .12s ease; background: #fff; clip-path: polygon(14% 44%, 0 58%, 38% 96%, 100% 20%, 86% 8%, 36% 68%); }
        .ocm2-deleted-toggle input:checked { border-color: #0891b2 !important; background: #0891b2 !important; }
        .ocm2-deleted-toggle input:checked::before { transform: scale(1); }
        .ocm2-deleted-toggle input:focus-visible { outline: 3px solid rgba(8,145,178,.16); outline-offset: 2px; }
        .ocm2-deleted-toggle span { text-transform: none !important; letter-spacing: 0 !important; }
        .ocm2-campaign-list { display: grid; gap: 6px; padding: 8px; overflow-y: auto; background: #fbfdff; }
        .ocm2-campaign-card { display: grid; gap: 5px; width: 100%; text-align: left; border: 1px solid #d6e0eb; border-left: 3px solid transparent; border-radius: 12px; background: #fff; padding: 8px 9px; cursor: pointer; }
        .ocm2-campaign-card.active { border-color: #06b6d4; border-left-color: #0891b2; background: #f0fdff; box-shadow: 0 6px 18px rgba(8,145,178,.08); }
        .ocm2-campaign-card strong { color: #0f172a; font-size: 12px; font-weight: 900; line-height: 1.18; }
        .ocm2-campaign-card small { color: #475569; font-size: 10px; line-height: 1.25; font-weight: 780; }
        .ocm2-card-metrics, .ocm2-card-footer, .ocm2-target-meta { display: flex; gap: 5px; flex-wrap: wrap; align-items: center; }
        .ocm2-card-metrics em { border-radius: 999px; background: #f1f5f9; color: #475569; padding: 3px 7px; font-size: 9px; font-style: normal; font-weight: 900; }
        .ocm2-card-footer { justify-content: space-between; color: #64748b; font-size: 9px; font-weight: 850; }
        .ocm2-card-footer span:last-child { color: #0369a1; }
        .ocm2-workspace { display: grid; gap: 10px; min-width: 0; }
        .ocm2-selected-card { padding: 10px 12px; border-left: 4px solid #0891b2; background: linear-gradient(135deg, #ffffff 0%, #f8fbff 100%); }
        .ocm2-selected-main { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
        .ocm2-selected-main > div:first-child { min-width: 0; }
        .ocm2-selected-main h2, .ocm2-empty-workspace h2 { margin: 2px 0; color: #0f172a; font-size: 15px; line-height: 1.14; font-weight: 900; letter-spacing: -.03em; overflow-wrap: anywhere; }
        .ocm2-selected-main p, .ocm2-empty-workspace p { margin: 0; color: #475569; font-size: 10.5px; font-weight: 800; line-height: 1.3; }
        .ocm2-status { justify-self: start; display: inline-flex; align-items: center; justify-content: center; min-height: 21px; padding: 0 7px; border-radius: 999px; font-size: 8.5px; font-weight: 900; text-align: center; }
        .ocm2-selected-actions .ocm2-status { flex: 0 0 auto; min-width: 56px; }
        .ocm2-status.is-running, .ocm2-status.is-closed { background: #dcfce7; color: #166534; }
        .ocm2-status.is-ready { background: #dbeafe; color: #1d4ed8; }
        .ocm2-status.is-paused, .ocm2-status.is-draft { background: #fef3c7; color: #92400e; }
        .ocm2-status.deleted { background: #fee2e2; color: #991b1b; }
        .ocm2-campaign-card .ocm2-status { justify-self: start; padding: 0 7px; }
        .ocm2-progress-grid { display: none; }
        .ocm2-target-filters { grid-template-columns: minmax(220px,1.55fr) repeat(4,minmax(100px,.48fr)); align-items: end; }
        .ocm2-wide-filter { min-width: 0; }
        .ocm2-segment-bar { display: flex; gap: 5px; flex-wrap: wrap; justify-content: flex-start; padding: 7px 10px; border-bottom: 1px solid #e7edf5; background: #fff; }
        .ocm2-segment-bar button { height: 26px; min-height: 26px; min-width: 52px; border: 1px solid #d8e2ee; border-radius: 10px; background: #f8fafc; color: #475569; padding: 2px 10px; font-size: 10px; white-space: nowrap; }
        .ocm2-segment-bar button.active { background: #083344; color: #fff; border-color: #083344; }
        .ocm2-target-list { display: grid; gap: 6px; padding: 8px; max-height: calc(100vh - 236px); overflow-y: auto; background: #fbfdff; }
        .ocm2-target-card { display: grid; gap: 6px; border: 1px solid #d3deea; border-left: 3px solid #dbeafe; border-radius: 12px; background: #fff; padding: 8px; box-shadow: 0 4px 12px rgba(15,23,42,.026); }
        .ocm2-target-card.is-expanded { border-color: #38bdf8; border-left-color: #0891b2; background: #fcfeff; box-shadow: 0 8px 22px rgba(15,23,42,.045); }
        .ocm2-target-main { display: grid; grid-template-columns: minmax(0,1fr) minmax(220px,240px); gap: 10px; align-items: center; }
        .ocm2-target-copy, .ocm2-target-controls { min-width: 0; }
        .ocm2-target-controls { display: grid; grid-template-columns: minmax(112px, 1fr) minmax(92px, .72fr); gap: 6px; align-self: stretch; align-content: center; }
        .ocm2-target-controls .ocm2-target-status { height: 28px; min-height: 28px; max-height: 28px; border-radius: 10px; padding: 0 7px; font-size: 10px; line-height: 28px; text-align: center; }
        .ocm2-target-controls button { min-height: 28px; display: inline-flex; align-items: center; justify-content: center; gap: 4px; min-width: 0; border: 1px solid #cbd5e1; border-radius: 10px; background: #f8fafc; color: #0f3b61; padding: 3px 7px; font-size: 10px; line-height: 1.05; font-weight: 900; white-space: normal; text-align: center; cursor: pointer; }
        .ocm2-target-details { display: grid; gap: 6px; padding-top: 1px; }
        .ocm2-party { display: inline-flex; margin-bottom: 3px; border-radius: 999px; background: #e0f2fe; color: #075985; padding: 2px 6px; font-size: 9px; line-height: 1.1; font-weight: 900; }
        .ocm2-target-main h4 { margin: 0; color: #0f172a; font-size: 12.5px; line-height: 1.15; font-weight: 900; overflow-wrap: anywhere; }
        .ocm2-target-main p { margin: 2px 0 0; color: #475569; font-size: 10px; line-height: 1.25; font-weight: 800; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .ocm2-target-meta { justify-content: center; }
        .ocm2-target-meta span { flex: 1 1 104px; min-width: 0; display: grid; justify-items: center; gap: 1px; border: 1px solid #e2e8f0; border-radius: 9px; background: #f8fafc; padding: 5px 6px; color: #1e293b; font-size: 9.5px; line-height: 1.2; font-weight: 800; text-align: center; overflow-wrap: anywhere; }
        .ocm2-target-meta strong, .ocm2-target-note span { color: #475569; font-size: 9px; text-transform: uppercase; letter-spacing: .08em; }
        .ocm2-visit-row { display: grid; grid-template-columns: minmax(138px, 180px) minmax(0,1fr); gap: 6px; align-items: center; border: 1px solid #d8e2ee; border-radius: 11px; background: #f8fafc; padding: 6px; }
        .ocm2-visit-row label { display: grid; gap: 5px; margin: 0; color: #475569; font-size: 9px; text-transform: uppercase; letter-spacing: .08em; font-weight: 900; }
        .ocm2-visit-row input { height: 28px; min-height: 28px; border: 1px solid #d8e2ee; border-radius: 9px; background: #fff; color: #102033; padding: 0 7px; font-size: 10.5px; font-weight: 800; outline: none; }
        .ocm2-target-note { display: grid; gap: 5px; margin: 0; }
        .ocm2-target-note textarea { min-height: 36px; border: 1px solid #d8e2ee; border-radius: 10px; background: #f8fafc; color: #102033; padding: 6px 8px; font-size: 10.5px; font-weight: 750; resize: vertical; outline: none; }
        .ocm2-target-note textarea:focus { border-color: #0891b2; background: #fff; box-shadow: 0 0 0 4px rgba(8,145,178,.1); }
        .ocm2-doc-row { justify-content: center; }
        .ocm2-doc-row button, .ocm2-outreach-row button { width: 100%; min-height: 29px; border: 1px solid #cbd5e1; background: #f8fafc; color: #0f3b61; padding: 3px 7px; font-size: 10px; }
        .ocm2-outreach-row button:first-child { background: #083344; color: #fff; border-color: #083344; }
        .ocm2-outreach-row button[disabled] { opacity: .45; cursor: not-allowed; transform: none; }
        .ocm2-doc-chip { background: #ecfeff !important; color: #155e75 !important; }
        .ocm2-empty, .ocm2-empty-workspace { min-height: 170px; display: grid; place-items: center; gap: 8px; text-align: center; padding: 24px; color: #64748b; font-weight: 850; }
        .ocm2-empty-workspace { min-height: 440px; align-content: center; }
        .ocm2-skeleton { min-height: 86px; border-radius: 17px; background: linear-gradient(90deg, #eef2f7 0%, #f8fafc 45%, #eef2f7 90%); background-size: 220% 100%; animation: ocm2-shimmer 1.1s linear infinite; }
        .ocm2-muted { color: #94a3b8; font-size: 11px; font-weight: 900; }
        .ocm2-btn:focus-visible, .ocm2-icon-btn:focus-visible, .ocm2-doc-row button:focus-visible, .ocm2-outreach-row button:focus-visible, .ocm2-target-controls button:focus-visible, .ocm2-segment-bar button:focus-visible, .ocm2-campaign-card:focus-visible { outline: 3px solid rgba(34,211,238,.28); outline-offset: 2px; }
        @keyframes ocm2-shimmer { to { background-position: -220% 0; } }
        @media (prefers-reduced-motion: reduce) { .ocm2-skeleton { animation: none; } .ocm2-btn, .ocm2-icon-btn, .ocm2-doc-row button, .ocm2-outreach-row button, .ocm2-target-controls button, .ocm2-segment-bar button { transition: none; } }
        @media (max-width: 1280px) { .ocm2-layout { grid-template-columns: 340px minmax(0,1fr); } .ocm2-target-filters { grid-template-columns: repeat(3,minmax(0,1fr)); } .ocm2-wide-filter { grid-column: 1 / -1; } }
        @media (max-width: 980px) { .ocm2-command-bar { grid-template-columns: 1fr; } .ocm2-selected-main { flex-direction: column; align-items: stretch; } .ocm2-kpi-grid, .ocm2-progress-grid { grid-template-columns: repeat(2,minmax(0,1fr)); } .ocm2-layout { grid-template-columns: 1fr; } .ocm2-rail { position: static; max-height: none; } .ocm2-campaign-list { max-height: 340px; } .ocm2-target-list { max-height: none; } }
        @media (max-width: 680px) { .ocm2-shell { padding: 12px; } .ocm2-actions, .ocm2-selected-actions { align-items: stretch; } .ocm2-actions .ocm2-btn, .ocm2-selected-actions .ocm2-btn { width: 100%; } .ocm2-kpi-grid, .ocm2-progress-grid, .ocm2-filter-pair, .ocm2-target-filters, .ocm2-target-main { grid-template-columns: 1fr; } }
    `;
    document.head.appendChild(style);
}
