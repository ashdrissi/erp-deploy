frappe.pages["campaign-editor"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Campaign Builder"),
        single_column: true,
    });

    page.main.addClass("oce-root");
    injectCampaignEditorStyles();
    renderCampaignEditor(page);
    loadCampaignEditorData(page);
    applyCampaignEditorHeader(page);
};

frappe.pages["campaign-editor"].on_page_show = function (wrapper) {
    if (!wrapper.page) return;
    applyCampaignEditorHeader(wrapper.page);
    loadCampaignEditorData(wrapper.page);
};

const OCE_STATE = {
    campaign: null,
    statuses: [],
    businessTypes: [],
    segments: [],
    filterOptions: { price_lists: [], item_groups: [], containers: [] },
    articles: [],
    targets: [],
    targetSearch: "",
    targetBusinessType: "All",
    targetType: "All",
    targetClass: "All",
    targetSelected: "All",
    articleSearch: "",
    articleOnlySelected: false,
    articlePage: 1,
    articlePageSize: 12,
    articleServerStart: 0,
    articleHasMore: false,
    articleLoading: false,
    targetServerStart: 0,
    targetHasMore: false,
    targetLoading: false,
    candidatePageSize: 80,
    activeContentChannel: "WhatsApp",
};

let OCE_ARTICLE_REFRESH_TIMER = null;
let OCE_TARGET_REFRESH_TIMER = null;

function applyCampaignEditorHeader(page) {
    page.set_title(__("Campaign Builder"));
    setTimeout(() => {
        if (!frappe.breadcrumbs) return;
        frappe.breadcrumbs.clear();
        frappe.breadcrumbs.append_breadcrumb_element("/app/campaign-manager", __("Campaign Manager"), "title-text");
        frappe.breadcrumbs.append_breadcrumb_element("", __("Campaign Builder"), "title-text");
        frappe.breadcrumbs.toggle(true);
    }, 0);
}

async function loadCampaignEditorData(page) {
    try {
        const campaign = currentCampaignRoute();
        const res = await frappe.call({
            method: "orderlift.orderlift_crm.api.campaign.get_editor_data",
            args: campaign ? { campaign } : {},
        });
        const data = res.message || {};
        OCE_STATE.campaign = normalizeCampaign(data.campaign || {});
        OCE_STATE.statuses = (data.statuses || []).map((row) => row.name || row.status_label);
        OCE_STATE.businessTypes = data.business_types || [];
        OCE_STATE.segments = data.segments || [];
        OCE_STATE.filterOptions = data.filter_options || { price_lists: [], item_groups: [], containers: [] };
        const articlePaging = data.article_paging || {};
        const targetPaging = data.target_paging || {};
        OCE_STATE.articles = (data.articles || []).map(normalizeArticle);
        OCE_STATE.targets = (data.targets || []).map(normalizeTarget);
        OCE_STATE.articleServerStart = Number(articlePaging.start || 0) + (articlePaging.rows || []).length;
        OCE_STATE.targetServerStart = Number(targetPaging.start || 0) + (targetPaging.rows || []).length;
        OCE_STATE.articleHasMore = Boolean(articlePaging.has_more);
        OCE_STATE.targetHasMore = Boolean(targetPaging.has_more);
        OCE_STATE.targetBusinessType = OCE_STATE.campaign.business_type_filter || "All";
        OCE_STATE.targetClass = OCE_STATE.campaign.crm_segment_filter || OCE_STATE.campaign.partner_segment_filter || "All";
        OCE_STATE.activeContentChannel = normalizeChannel(OCE_STATE.campaign.default_channel);
        OCE_STATE.articlePage = 1;
        renderCampaignEditor(page);
    } catch (error) {
        console.error("Campaign Builder failed", error);
        OCE_STATE.campaign = normalizeCampaign({});
        OCE_STATE.articles = [];
        OCE_STATE.targets = [];
        renderCampaignEditor(page, true);
    }
}

function currentCampaignRoute() {
    const options = frappe.route_options || {};
    const route = frappe.get_route ? frappe.get_route() : [];
    if ((route || [])[0] === "campaign-editor" && !options.campaign) {
        frappe.route_options = null;
        return null;
    }
    return options.campaign || null;
}

function normalizeCampaign(campaign) {
    return {
        name: campaign.name || null,
        campaign_name: campaign.campaign_name || "",
        campaign_owner: campaign.campaign_owner || frappe.session.user,
        campaign_date: campaign.campaign_date || frappe.datetime.now_date(),
        start_date: campaign.start_date || frappe.datetime.now_date(),
        end_date: campaign.end_date || frappe.datetime.now_date(),
        sales_history_from_date: campaign.sales_history_from_date || frappe.datetime.now_date(),
        sales_history_to_date: campaign.sales_history_to_date || frappe.datetime.now_date(),
        default_channel: campaign.default_channel || "WhatsApp",
        target_family: campaign.target_family || "Distribution Partners",
        business_type_filter: campaign.business_type_filter || "",
        crm_segment_filter: campaign.crm_segment_filter || "",
        status: campaign.status || "Draft",
        partner_segment_filter: campaign.partner_segment_filter || "",
        container_filter: campaign.container_filter || "",
        price_list_filter: campaign.price_list_filter || "",
        item_group_filter: campaign.item_group_filter || "",
        supplier_payment_mode_filter: campaign.supplier_payment_mode_filter || "",
        description: campaign.description || "",
        email_subject: campaign.email_subject || "Selected parts offer",
        email_mode: campaign.email_mode || "HTML",
        email_body: campaign.email_body || "",
        whatsapp_text: campaign.whatsapp_text || "",
        call_script: campaign.call_script || "",
    };
}

function normalizeArticle(article) {
    return {
        selected: Boolean(article.selected),
        item_code: article.item_code,
        item_name: article.item_name,
        item_group: article.item_group || "",
        container: article.container || "",
        supplier_payment_mode: article.supplier_payment_mode || "",
        sold_qty_period: article.sold_qty_period || 0,
        available_qty_snapshot: article.available_qty_snapshot || 0,
        price_snapshot: article.price_snapshot || 0,
        display_price: article.display_price !== 0,
        display_available_qty: article.display_available_qty !== 0,
        source_item_price: article.source_item_price || "",
    };
}

function normalizeTarget(target) {
    return {
        id: target.name || target.party_name,
        selected: Boolean(target.selected),
        party_type: target.party_type,
        party_name: target.party_name,
        display_name: target.display_name || target.party_name,
        business_type: target.business_type || "",
        crm_segment: target.crm_segment || target.partner_segment || "",
        partner_segment: target.crm_segment || target.partner_segment || "",
        crm_segments: target.crm_segments || [],
        city: target.city || "",
        target_status: target.target_status || "",
        assigned_to: target.assigned_to || "",
        contact_person_name: target.contact_person_name || target.contact || "",
        last_order_date: target.last_order_date || "-",
    };
}

function normalizeChannel(value) {
    return ["Email", "WhatsApp", "Call"].includes(value) ? value : "WhatsApp";
}

function bindCampaignEditorEvents(page) {
    page.main.find("[data-route]").on("click", function () {
        frappe.set_route($(this).data("route"));
    });
    page.main.find("[data-save]").on("click", function () {
        saveEditorCampaign(page, $(this).data("save-mode"));
    });
    page.main.find("[data-reload-articles]").on("click", function () {
        refreshArticles(page);
    });
    page.main.find("[data-reload-targets]").on("click", function () {
        refreshTargets(page);
    });
    page.main.find("[data-field]").on("change", function () {
        const field = $(this).data("field");
        OCE_STATE.campaign[field] = $(this).val();
        if (["sales_history_from_date", "sales_history_to_date", "container_filter", "price_list_filter", "item_group_filter", "supplier_payment_mode_filter"].includes(field)) {
            refreshArticles(page);
        }
        if (field === "default_channel") {
            OCE_STATE.activeContentChannel = normalizeChannel(OCE_STATE.campaign.default_channel);
            renderCampaignEditor(page);
        }
        if (field === "business_type_filter") {
            OCE_STATE.targetBusinessType = OCE_STATE.campaign.business_type_filter || "All";
            OCE_STATE.targetClass = "All";
            OCE_STATE.campaign.crm_segment_filter = "";
            refreshTargets(page);
        }
        if (field === "crm_segment_filter") {
            OCE_STATE.targetClass = OCE_STATE.campaign.crm_segment_filter || "All";
            refreshTargets(page);
        }
    });
    page.main.find("[data-content-channel]").on("click", function () {
        OCE_STATE.activeContentChannel = $(this).data("content-channel");
        renderCampaignEditor(page);
    });
    page.main.find("#oce-target-search").on("input", function () {
        OCE_STATE.targetSearch = String($(this).val() || "").trim().toLowerCase();
        page.main.find("#oce-target-body").html(targetRowsMarkup(currentTargets()));
        bindTargetSelection(page);
        queueTargetRefresh(page);
    });
    page.main.find("#oce-target-type").on("change", function () {
        OCE_STATE.targetType = $(this).val();
        refreshTargets(page);
    });
    page.main.find("#oce-target-business-type").on("change", function () {
        OCE_STATE.targetBusinessType = $(this).val();
        OCE_STATE.targetClass = "All";
        refreshTargets(page);
    });
    page.main.find("#oce-target-class").on("change", function () {
        OCE_STATE.targetClass = $(this).val();
        refreshTargets(page);
    });
    page.main.find("#oce-target-selected").on("change", function () {
        OCE_STATE.targetSelected = $(this).val();
        page.main.find("#oce-target-body").html(targetRowsMarkup(currentTargets()));
        bindTargetSelection(page);
    });
    page.main.find("#oce-article-search").on("input", function () {
        OCE_STATE.articleSearch = String($(this).val() || "").trim().toLowerCase();
        OCE_STATE.articlePage = 1;
        queueArticleRefresh(page);
    });
    page.main.find("#oce-article-page-size").on("change", function () {
        OCE_STATE.articlePageSize = Number($(this).val() || 12);
        OCE_STATE.articlePage = 1;
        renderCampaignEditor(page);
    });
    page.main.find("#oce-article-selected-only").on("change", function () {
        OCE_STATE.articleOnlySelected = Boolean(this.checked);
        OCE_STATE.articlePage = 1;
        renderCampaignEditor(page);
    });
    page.main.find("[data-article-page]").on("click", function () {
        OCE_STATE.articlePage = Number($(this).data("article-page"));
        renderCampaignEditor(page);
    });
    page.main.find("[data-load-more-articles]").on("click", function () {
        refreshArticles(page, true);
    });
    page.main.find("[data-load-more-targets]").on("click", function () {
        refreshTargets(page, true);
    });
    page.main.find("[data-article-bulk]").on("click", function () {
        const bulkAction = $(this).data("article-bulk");
        currentArticles().pageRows.forEach((row) => {
            row.selected = bulkAction === "select";
        });
        renderCampaignEditor(page);
    });
    page.main.find("[data-target-bulk]").on("click", function () {
        const bulkAction = $(this).data("target-bulk");
        currentTargets().forEach((row) => {
            row.selected = bulkAction === "select";
        });
        renderCampaignEditor(page);
    });
    page.main.find(".oce-article-checkbox").on("change", function () {
        const article = OCE_STATE.articles.find((row) => row.item_code === $(this).data("item"));
        if (article) article.selected = Boolean(this.checked);
        renderCampaignEditor(page);
    });
    page.main.find(".oce-article-toggle").on("change", function () {
        const article = OCE_STATE.articles.find((row) => row.item_code === $(this).data("item"));
        if (article) article[$(this).data("field")] = Boolean(this.checked);
        renderCampaignEditor(page);
    });
    bindTargetSelection(page);
}

function bindTargetSelection(page) {
    page.main.find(".oce-target-checkbox").off("change").on("change", function () {
        const target = OCE_STATE.targets.find((row) => row.id === $(this).data("target"));
        if (target) target.selected = Boolean(this.checked);
        renderCampaignEditor(page);
    });
}

async function refreshArticles(page, append = false) {
    if (OCE_STATE.articleLoading) return;
    OCE_STATE.articleLoading = true;
    try {
        const start = append ? OCE_STATE.articleServerStart : 0;
        const res = await frappe.call({
            method: "orderlift.orderlift_crm.api.campaign.get_article_candidate_page",
            args: articleCandidateArgs(start),
        });
        const data = res.message || {};
        const rows = data.rows || [];
        mergeArticleCandidates(rows, append);
        OCE_STATE.articleServerStart = Number(data.start || start) + rows.length;
        OCE_STATE.articleHasMore = Boolean(data.has_more);
        OCE_STATE.articleLoading = false;
        renderCampaignEditor(page);
    } catch (error) {
        console.error(error);
    } finally {
        OCE_STATE.articleLoading = false;
    }
}

async function refreshTargets(page, append = false) {
    if (OCE_STATE.targetLoading) return;
    OCE_STATE.targetLoading = true;
    try {
        const start = append ? OCE_STATE.targetServerStart : 0;
        const res = await frappe.call({
            method: "orderlift.orderlift_crm.api.campaign.get_target_candidate_page",
            args: targetCandidateArgs(start),
        });
        const data = res.message || {};
        const rows = data.rows || [];
        mergeTargetCandidates(rows, append);
        OCE_STATE.targetServerStart = Number(data.start || start) + rows.length;
        OCE_STATE.targetHasMore = Boolean(data.has_more);
        OCE_STATE.targetLoading = false;
        renderCampaignEditor(page);
    } catch (error) {
        console.error(error);
    } finally {
        OCE_STATE.targetLoading = false;
    }
}

function queueArticleRefresh(page) {
    clearTimeout(OCE_ARTICLE_REFRESH_TIMER);
    OCE_ARTICLE_REFRESH_TIMER = setTimeout(() => refreshArticles(page), 350);
}

function queueTargetRefresh(page) {
    clearTimeout(OCE_TARGET_REFRESH_TIMER);
    OCE_TARGET_REFRESH_TIMER = setTimeout(() => refreshTargets(page), 350);
}

function articleCandidateArgs(start = 0) {
    return {
        from_date: OCE_STATE.campaign.sales_history_from_date,
        to_date: OCE_STATE.campaign.sales_history_to_date,
        price_list: OCE_STATE.campaign.price_list_filter,
        item_group: OCE_STATE.campaign.item_group_filter,
        container: OCE_STATE.campaign.container_filter,
        supplier_payment_mode: OCE_STATE.campaign.supplier_payment_mode_filter,
        search: OCE_STATE.articleSearch || null,
        limit: OCE_STATE.candidatePageSize,
        start,
    };
}

function targetCandidateArgs(start = 0) {
    return {
        party_type: OCE_STATE.targetType === "All" ? null : OCE_STATE.targetType,
        business_type: OCE_STATE.targetBusinessType === "All" ? null : OCE_STATE.targetBusinessType,
        segment: OCE_STATE.targetClass === "All" ? null : OCE_STATE.targetClass,
        search: OCE_STATE.targetSearch || null,
        limit: OCE_STATE.candidatePageSize,
        start,
    };
}

function mergeArticleCandidates(rows, append = false) {
    const existingMap = new Map(OCE_STATE.articles.map((row) => [row.item_code, row]));
    const incomingCodes = new Set();
    const incomingRows = (rows || []).map((row) => {
        const normalized = normalizeArticle(row);
        incomingCodes.add(normalized.item_code);
        const existing = existingMap.get(normalized.item_code);
        if (!existing) return normalized;
        return {
            ...normalized,
            selected: Boolean(existing.selected || normalized.selected),
            display_price: existing.display_price,
            display_available_qty: existing.display_available_qty,
        };
    });
    if (append) {
        const mergedMap = new Map(OCE_STATE.articles.map((row) => [row.item_code, row]));
        incomingRows.forEach((row) => mergedMap.set(row.item_code, row));
        OCE_STATE.articles = Array.from(mergedMap.values());
        return;
    }
    const selectedRows = OCE_STATE.articles.filter((row) => row.selected && !incomingCodes.has(row.item_code));
    OCE_STATE.articles = incomingRows.concat(selectedRows);
}

function mergeTargetCandidates(rows, append = false) {
    const existingMap = new Map(OCE_STATE.targets.map((row) => [targetKey(row), row]));
    const incomingKeys = new Set();
    const incomingRows = (rows || []).map((row) => {
        const normalized = normalizeTarget(row);
        const key = targetKey(normalized);
        incomingKeys.add(key);
        const existing = existingMap.get(key);
        if (!existing) return normalized;
        return { ...normalized, ...existing, selected: Boolean(existing.selected || normalized.selected) };
    });
    if (append) {
        const mergedMap = new Map(OCE_STATE.targets.map((row) => [targetKey(row), row]));
        incomingRows.forEach((row) => mergedMap.set(targetKey(row), row));
        OCE_STATE.targets = Array.from(mergedMap.values());
        return;
    }
    const selectedRows = OCE_STATE.targets.filter((row) => row.selected && !incomingKeys.has(targetKey(row)));
    OCE_STATE.targets = incomingRows.concat(selectedRows);
}

function targetKey(target) {
    return `${target.party_type || ""}::${target.party_name || ""}`;
}

async function saveEditorCampaign(page, mode = "campaign") {
    const payload = collectCampaignPayload(page);
    if (mode === "draft") {
        payload.status = "Draft";
    }
    try {
        const res = await frappe.call({
            method: "orderlift.orderlift_crm.api.campaign.save_campaign",
            args: { payload: JSON.stringify(payload) },
            freeze: true,
        });
        const savedCampaign = res.message && res.message.campaign ? res.message.campaign : null;
        if (savedCampaign && savedCampaign.name) {
            frappe.route_options = { campaign: savedCampaign.name };
        }
        frappe.show_alert({ message: __("Campaign saved"), indicator: "green" });
        loadCampaignEditorData(page);
    } catch (error) {
        console.error(error);
    }
}

function collectCampaignPayload(page) {
    const payload = { ...OCE_STATE.campaign, name: OCE_STATE.campaign.name };
    page.main.find("[data-field]").each(function () {
        payload[$(this).data("field")] = $(this).val();
    });
    payload.items = OCE_STATE.articles.filter((row) => row.selected);
    payload.targets = OCE_STATE.targets.filter((row) => row.selected);
    return payload;
}

function currentTargets() {
    return OCE_STATE.targets.filter((target) => {
        const text = `${target.display_name} ${target.city} ${target.contact_person_name}`.toLowerCase();
        const matchesSearch = !OCE_STATE.targetSearch || text.includes(OCE_STATE.targetSearch);
        const matchesType = OCE_STATE.targetType === "All" || target.party_type === OCE_STATE.targetType;
        const targetSegments = target.crm_segments && target.crm_segments.length ? target.crm_segments : [{ business_type: target.business_type, segment: target.crm_segment }];
        const matchesBusinessType = OCE_STATE.targetBusinessType === "All" || targetSegments.some((row) => row.business_type === OCE_STATE.targetBusinessType);
        const matchesClass = OCE_STATE.targetClass === "All" || targetSegments.some((row) => row.segment === OCE_STATE.targetClass);
        const matchesSelected = OCE_STATE.targetSelected === "All" || (OCE_STATE.targetSelected === "Selected" ? target.selected : !target.selected);
        return matchesSearch && matchesType && matchesBusinessType && matchesClass && matchesSelected;
    });
}

function currentSegmentOptions() {
    const businessType = OCE_STATE.targetBusinessType === "All" ? OCE_STATE.campaign.business_type_filter : OCE_STATE.targetBusinessType;
    return (OCE_STATE.segments || [])
        .filter((row) => !businessType || businessType === "All" || row.business_type === businessType)
        .map((row) => row.name);
}

function currentArticles() {
    const rows = OCE_STATE.articles.filter((article) => {
        const text = `${article.item_code} ${article.item_name} ${article.item_group}`.toLowerCase();
        const matchesSearch = !OCE_STATE.articleSearch || text.includes(OCE_STATE.articleSearch);
        const matchesSelection = !OCE_STATE.articleOnlySelected || article.selected;
        return matchesSearch && matchesSelection;
    });
    const totalPages = Math.max(1, Math.ceil(rows.length / OCE_STATE.articlePageSize));
    if (OCE_STATE.articlePage > totalPages) OCE_STATE.articlePage = totalPages;
    const start = (OCE_STATE.articlePage - 1) * OCE_STATE.articlePageSize;
    return {
        rows,
        totalPages,
        currentPage: OCE_STATE.articlePage,
        pageRows: rows.slice(start, start + OCE_STATE.articlePageSize),
    };
}

function activeContentMarkup(campaign) {
    const channel = OCE_STATE.activeContentChannel;
    if (channel === "Email") {
        return `
            <label class="oce-label">${__("Email subject")}</label>
            <input class="oce-content-select" data-field="email_subject" value="${frappe.utils.escape_html(campaign.email_subject)}" />
            <label class="oce-label">${__("Email mode")}</label>
            <select class="oce-content-select" data-field="email_mode">
                <option value="HTML" ${campaign.email_mode === "HTML" ? "selected" : ""}>${__("HTML")}</option>
                <option value="Text" ${campaign.email_mode === "Text" ? "selected" : ""}>${__("Text")}</option>
            </select>
            <label class="oce-label">${__("Email text / HTML")}</label>
            <textarea class="oce-textarea oce-email-textarea" data-field="email_body">${frappe.utils.escape_html(campaign.email_body)}</textarea>
        `;
    }
    if (channel === "Call") {
        return `
            <label class="oce-label">${__("Call script")}</label>
            <textarea class="oce-textarea oce-call-textarea" data-field="call_script">${frappe.utils.escape_html(campaign.call_script)}</textarea>
        `;
    }
    return `
        <label class="oce-label">${__("WhatsApp text")}</label>
        <textarea class="oce-textarea" data-field="whatsapp_text">${frappe.utils.escape_html(campaign.whatsapp_text)}</textarea>
    `;
}

function activePreviewText(campaign) {
    if (OCE_STATE.activeContentChannel === "Email") {
        return campaign.email_body || campaign.email_subject || __("Add email content to preview it here.");
    }
    if (OCE_STATE.activeContentChannel === "Call") {
        return campaign.call_script || __("Add a call script to preview it here.");
    }
    return campaign.whatsapp_text || __("Add WhatsApp text to preview it here.");
}

function formField(fieldname, label, value, type = "text") {
    return `<label class="oce-field"><span>${frappe.utils.escape_html(label)}</span><input data-field="${fieldname}" type="${type}" value="${frappe.utils.escape_html(value || "")}" /></label>`;
}

function selectField(fieldname, label, options, value) {
    return `<label class="oce-field"><span>${frappe.utils.escape_html(label)}</span><select data-field="${fieldname}">${options.map((option) => `<option value="${frappe.utils.escape_html(option)}" ${option === value ? "selected" : ""}>${frappe.utils.escape_html(__(option || "All"))}</option>`).join("")}</select></label>`;
}

function optionSelectField(fieldname, label, options, value) {
    return `<label class="oce-field"><span>${frappe.utils.escape_html(label)}</span><select data-field="${fieldname}"><option value="">${__("All")}</option>${options.map((option) => `<option value="${frappe.utils.escape_html(option)}" ${option === value ? "selected" : ""}>${frappe.utils.escape_html(option)}</option>`).join("")}</select></label>`;
}

function compactSelect(id, options, value) {
    return `<select id="${id}" class="oce-compact-select">${options.map((option) => `<option value="${frappe.utils.escape_html(option)}" ${option === value ? "selected" : ""}>${frappe.utils.escape_html(__(option))}</option>`).join("")}</select>`;
}

function formGroup(title, helper, fieldsMarkup) {
    return `
        <section class="oce-form-group">
            <div class="oce-form-group-head">
                <strong>${frappe.utils.escape_html(title)}</strong>
                <span>${frappe.utils.escape_html(helper)}</span>
            </div>
            <div class="oce-form-grid oce-form-grid--grouped">${fieldsMarkup}</div>
        </section>
    `;
}

function campaignReadiness(campaign, selectedArticles, selectedTargets) {
    const checks = [
        { ok: Boolean((campaign.campaign_name || "").trim()), label: __("name") },
        { ok: selectedTargets.length > 0, label: __("targets") },
        { ok: selectedArticles.length > 0, label: __("articles") },
        { ok: campaignHasContent(campaign), label: __("content") },
    ];
    return {
        score: checks.filter((check) => check.ok).length,
        missing: checks.filter((check) => !check.ok).map((check) => check.label),
    };
}

function campaignHasContent(campaign) {
    return Boolean((campaign.email_subject || "").trim() || (campaign.email_body || "").trim() || (campaign.whatsapp_text || "").trim() || (campaign.call_script || "").trim());
}

function filterPill(label, value) {
    return `<button class="oce-filter-pill"><span>${frappe.utils.escape_html(__(label))}</span><strong>${frappe.utils.escape_html(value)}</strong></button>`;
}

function articleRow(article) {
    return `
        <tr>
            <td><input class="oce-article-checkbox" type="checkbox" data-item="${frappe.utils.escape_html(article.item_code)}" ${article.selected ? "checked" : ""} /></td>
            <td><strong>${frappe.utils.escape_html(article.item_code)}</strong><span>${frappe.utils.escape_html(article.item_name)}</span></td>
            <td>${frappe.utils.escape_html(article.item_group || "-")}</td>
            <td>${frappe.utils.escape_html(article.container || "-")}</td>
            <td><span class="oce-payment-chip">${frappe.utils.escape_html(article.supplier_payment_mode || "-")}</span></td>
            <td>${article.sold_qty_period || 0}</td>
            <td>${article.available_qty_snapshot || 0}</td>
            <td>${Number(article.price_snapshot || 0).toLocaleString()} DH</td>
            <td><label class="oce-check-pill"><input class="oce-article-toggle" type="checkbox" data-item="${frappe.utils.escape_html(article.item_code)}" data-field="display_price" ${article.display_price ? "checked" : ""}> ${__("Price")}</label><label class="oce-check-pill"><input class="oce-article-toggle" type="checkbox" data-item="${frappe.utils.escape_html(article.item_code)}" data-field="display_available_qty" ${article.display_available_qty ? "checked" : ""}> ${__("Qty")}</label></td>
        </tr>
    `;
}

function targetRowsMarkup(rows) {
    if (!rows.length) {
        return `<tr><td class="oce-empty-row" colspan="8">${__("No targets match the current filters.")}</td></tr>`;
    }
    return rows.map((target) => `
        <tr class="${target.selected ? "selected" : ""}">
            <td><input class="oce-target-checkbox" type="checkbox" data-target="${frappe.utils.escape_html(target.id)}" ${target.selected ? "checked" : ""} /></td>
            <td><strong>${frappe.utils.escape_html(target.display_name)}</strong><span>${frappe.utils.escape_html(target.party_name)}</span></td>
            <td>${frappe.utils.escape_html(target.party_type)}</td>
            <td>${frappe.utils.escape_html(target.business_type || "-")}</td>
            <td>${frappe.utils.escape_html(target.crm_segment || target.partner_segment || "-")}</td>
            <td>${frappe.utils.escape_html(target.city || "-")}</td>
            <td>${frappe.utils.escape_html(target.contact_person_name || "-")}</td>
            <td><span class="oce-status-pill">${frappe.utils.escape_html(target.target_status || "-")}</span></td>
        </tr>
    `).join("");
}

function renderCampaignEditor(page) {
    const campaign = OCE_STATE.campaign || normalizeCampaign({});
    const filteredTargets = currentTargets();
    const selectedArticles = OCE_STATE.articles.filter((row) => row.selected);
    const selectedTargets = OCE_STATE.targets.filter((row) => row.selected);
    const articleView = currentArticles();
    const readiness = campaignReadiness(campaign, selectedArticles, selectedTargets);
    const readinessHint = readiness.missing.length ? `${__("Missing")}: ${readiness.missing.join(", ")}` : __("Ready to run");
    page.main.html(`
        <div class="oce-shell">
            <section class="oce-topbar">
                <div class="oce-title-block">
                    <h1>${campaign.name ? frappe.utils.escape_html(campaign.campaign_name || campaign.name) : __("Campaign Builder")}</h1>
                    <p>${__("Build targets, articles, and outreach content from one focused page.")}</p>
                </div>
                <div class="oce-top-actions">
                    <span><strong>${selectedTargets.length}</strong> ${__("targets")}</span>
                    <span><strong>${selectedArticles.length}</strong> ${__("articles")}</span>
                    <span><strong>${readiness.score}/4</strong> ${frappe.utils.escape_html(readinessHint)}</span>
                </div>
            </section>

            <section class="oce-grid">
                <div class="oce-main">
                    <article class="oce-panel">
                        <div class="oce-panel-head">
                            <div><span class="oce-kicker">${__("Step 1")}</span><h2>${__("Campaign setup")}</h2></div>
                            <span class="oce-status">${frappe.utils.escape_html(campaign.status)}</span>
                        </div>
                        <div class="oce-setup-grid">
                            ${formGroup(__("Identity"), __("Name, owner, status, and default outreach channel."), `
                                ${formField("campaign_name", __("Campaign name"), campaign.campaign_name)}
                                ${formField("campaign_owner", __("Person in charge"), campaign.campaign_owner)}
                                ${selectField("status", __("Campaign status"), ["Draft", "Ready", "Running", "Paused", "Closed"], campaign.status)}
                                ${selectField("default_channel", __("Default channel"), ["WhatsApp", "Email", "Call"], campaign.default_channel)}
                            `)}
                            ${formGroup(__("Schedule"), __("Campaign timing plus the sales-history window used for article ranking."), `
                                ${formField("campaign_date", __("Campaign date"), campaign.campaign_date, "date")}
                                ${formField("start_date", __("Start date"), campaign.start_date, "date")}
                                ${formField("end_date", __("End date"), campaign.end_date, "date")}
                                ${formField("sales_history_from_date", __("Sales history from"), campaign.sales_history_from_date, "date")}
                                ${formField("sales_history_to_date", __("Sales history to"), campaign.sales_history_to_date, "date")}
                            `)}
                            ${formGroup(__("Audience Rules"), __("Use CRM classification as the targeting source of truth."), `
                                ${optionSelectField("business_type_filter", __("Business type"), OCE_STATE.businessTypes.map((row) => row.name), campaign.business_type_filter)}
                                ${optionSelectField("crm_segment_filter", __("CRM segment"), currentSegmentOptions(), campaign.crm_segment_filter)}
                            `)}
                            ${formGroup(__("Article Rules"), __("Limit candidate articles by inventory, price list, category, and supplier terms."), `
                                ${optionSelectField("container_filter", __("Container"), OCE_STATE.filterOptions.containers.map((row) => row.name), campaign.container_filter)}
                                ${optionSelectField("price_list_filter", __("Price list"), OCE_STATE.filterOptions.price_lists.map((row) => row.name), campaign.price_list_filter)}
                                ${optionSelectField("item_group_filter", __("Item group"), OCE_STATE.filterOptions.item_groups.map((row) => row.name), campaign.item_group_filter)}
                                ${selectField("supplier_payment_mode_filter", __("Supplier payment mode"), ["", "Paid Before Delivery", "Supplier Payment Delay"], campaign.supplier_payment_mode_filter)}
                            `)}
                        </div>
                        <div class="oce-description-row">
                            <label class="oce-field oce-wide-field">
                                <span>${__("Campaign description")}</span>
                                <textarea class="oce-small-textarea" data-field="description">${frappe.utils.escape_html(campaign.description)}</textarea>
                            </label>
                        </div>
                    </article>

                    <article class="oce-panel">
                        <div class="oce-panel-head">
                            <div><span class="oce-kicker">${__("Step 2")}</span><h2>${__("Articles and sales history")}</h2></div>
                            <button class="oce-link-btn" data-reload-articles="1">${__("Refresh Articles")}</button>
                        </div>
                        <div class="oce-article-toolbar">
                            <input id="oce-article-search" type="search" placeholder="${__("Search article or group")}" value="${frappe.utils.escape_html(OCE_STATE.articleSearch)}" />
                            <select id="oce-article-page-size" class="oce-compact-select">
                                ${[8, 12, 20].map((size) => `<option value="${size}" ${size === OCE_STATE.articlePageSize ? "selected" : ""}>${size} ${__("per page")}</option>`).join("")}
                            </select>
                            <label class="oce-inline-check"><input id="oce-article-selected-only" type="checkbox" ${OCE_STATE.articleOnlySelected ? "checked" : ""} /> ${__("Selected only")}</label>
                            <button class="oce-link-btn" data-article-bulk="select">${__("Select page")}</button>
                            <button class="oce-link-btn" data-article-bulk="clear">${__("Clear page")}</button>
                        </div>
                        <div class="oce-filter-bar">
                            ${filterPill("Sales period", `${campaign.sales_history_from_date || "-"} - ${campaign.sales_history_to_date || "-"}`)}
                            ${filterPill("Container", campaign.container_filter || __("All containers"))}
                            ${filterPill("Price list", campaign.price_list_filter || __("All price lists"))}
                            ${filterPill("Item group", campaign.item_group_filter || __("All item groups"))}
                        </div>
                        <div class="oce-table-wrap">
                            ${articleView.rows.length ? `<table class="oce-table"><thead><tr><th>${__("Use")}</th><th>${__("Article")}</th><th>${__("Group")}</th><th>${__("Container")}</th><th>${__("Payment")}</th><th>${__("Sold")}</th><th>${__("Stock")}</th><th>${__("Price")}</th><th>${__("Visible")}</th></tr></thead><tbody>${articleView.pageRows.map(articleRow).join("")}</tbody></table>` : `<div class="oce-empty-panel">${__("No article candidates match the current filters.")}</div>`}
                        </div>
                        <div class="oce-pagination-bar">
                            <div class="oce-pagination-meta">${articleView.rows.length} ${__("articles")} · ${__("Page")} ${articleView.currentPage}/${articleView.totalPages}</div>
                            <div class="oce-pagination-actions">
                                <button class="oce-link-btn" data-article-page="${Math.max(1, articleView.currentPage - 1)}" ${articleView.currentPage <= 1 ? "disabled" : ""}>${__("Previous")}</button>
                                <button class="oce-link-btn" data-article-page="${Math.min(articleView.totalPages, articleView.currentPage + 1)}" ${articleView.currentPage >= articleView.totalPages ? "disabled" : ""}>${__("Next")}</button>
                                <button class="oce-link-btn" data-load-more-articles="1" ${!OCE_STATE.articleHasMore || OCE_STATE.articleLoading ? "disabled" : ""}>${OCE_STATE.articleLoading ? __("Loading") : __("Load more candidates")}</button>
                            </div>
                        </div>
                    </article>

                    <article class="oce-panel">
                        <div class="oce-panel-head oce-target-head">
                            <div><span class="oce-kicker">${__("Step 3")}</span><h2>${__("Target selection")}</h2></div>
                            <div class="oce-target-summary"><strong>${filteredTargets.length}</strong><span>${__("visible")}</span></div>
                        </div>
                        <div class="oce-target-filter-bar">
                            <input id="oce-target-search" type="search" placeholder="${__("Search company, city, contact")}" value="${frappe.utils.escape_html(OCE_STATE.targetSearch)}" />
                            ${compactSelect("oce-target-type", ["All", "Lead", "Prospect", "Customer"], OCE_STATE.targetType)}
                            ${compactSelect("oce-target-business-type", ["All", ...OCE_STATE.businessTypes.map((row) => row.name)], OCE_STATE.targetBusinessType)}
                            ${compactSelect("oce-target-class", ["All", ...new Set(currentSegmentOptions().concat(OCE_STATE.targets.map((row) => row.crm_segment || row.partner_segment).filter(Boolean)))], OCE_STATE.targetClass)}
                            ${compactSelect("oce-target-selected", ["All", "Selected", "Not selected"], OCE_STATE.targetSelected)}
                        </div>
                        <div class="oce-target-actions-bar">
                            <span class="oce-pagination-meta">${OCE_STATE.targets.length} ${__("loaded candidates")}</span>
                            <button class="oce-link-btn" data-reload-targets="1">${__("Refresh Targets")}</button>
                            <button class="oce-link-btn" data-load-more-targets="1" ${!OCE_STATE.targetHasMore || OCE_STATE.targetLoading ? "disabled" : ""}>${OCE_STATE.targetLoading ? __("Loading") : __("Load more candidates")}</button>
                            <button class="oce-link-btn" data-target-bulk="select">${__("Select visible")}</button>
                            <button class="oce-link-btn" data-target-bulk="clear">${__("Clear visible")}</button>
                        </div>
                        <div class="oce-table-wrap oce-target-table-wrap">
                            ${OCE_STATE.targets.length ? `<table class="oce-table oce-target-table"><thead><tr><th>${__("Select")}</th><th>${__("Company")}</th><th>${__("Party")}</th><th>${__("Type")}</th><th>${__("Segment")}</th><th>${__("City")}</th><th>${__("Contact")}</th><th>${__("Status")}</th></tr></thead><tbody id="oce-target-body">${targetRowsMarkup(filteredTargets)}</tbody></table>` : `<div class="oce-empty-panel">${__("No Lead, Prospect, or Customer records available for selection.")}</div>`}
                        </div>
                    </article>
                </div>

                <aside class="oce-side">
                    <article class="oce-panel oce-content-panel">
                        <div class="oce-panel-head"><div><span class="oce-kicker">${__("Step 4")}</span><h2>${__("Campaign content")}</h2></div></div>
                        <div class="oce-content-tabs">
                            ${["Email", "WhatsApp", "Call"].map((channel) => `<button class="${channel === OCE_STATE.activeContentChannel ? "active" : ""}" data-content-channel="${channel}">${__(channel)}</button>`).join("")}
                        </div>
                        <div class="oce-channel-banner">${__("Right column is currently linked to the selected campaign channel: {0}", [OCE_STATE.activeContentChannel])}</div>
                        ${activeContentMarkup(campaign)}
                    </article>

                    <article class="oce-panel oce-preview-panel">
                        <div class="oce-panel-head"><div><span class="oce-kicker">${__("Preview")}</span><h2>${__("Selected offer snapshot")}</h2></div></div>
                        <div class="oce-phone-preview">
                            <div class="oce-phone-top"></div>
                            <div class="oce-message-bubble">${frappe.utils.escape_html(activePreviewText(campaign).slice(0, 220))}</div>
                            <div class="oce-preview-items">
                                ${selectedArticles.length ? selectedArticles.slice(0, 4).map((row) => `<span>${frappe.utils.escape_html(row.item_code)} - ${row.display_available_qty ? `${row.available_qty_snapshot} ${__("available")}` : __("qty hidden")} - ${row.display_price ? `${Number(row.price_snapshot).toLocaleString()} DH` : __("price hidden")}</span>`).join("") : `<span>${__("No selected articles yet")}</span>`}
                            </div>
                        </div>
                    </article>

                    <div class="oce-sticky-actions">
                        <button class="oce-btn oce-btn-ghost" data-route="campaign-manager">${__("Cancel")}</button>
                        <button class="oce-btn oce-btn-soft" data-save="1" data-save-mode="draft">${__("Save Draft")}</button>
                        <button class="oce-btn oce-btn-primary" data-save="1" data-save-mode="campaign">${__("Save Campaign")}</button>
                    </div>
                </aside>
            </section>
        </div>
    `);

    bindCampaignEditorEvents(page);
}

function injectCampaignEditorStyles() {
    if (document.getElementById("oce-campaign-editor-style")) return;
    const style = document.createElement("style");
    style.id = "oce-campaign-editor-style";
    style.textContent = `
        .oce-root { background: #f6f2ed; }
        .oce-shell { max-width: 1500px; margin: 0 auto; padding: 12px 18px 18px; color: #172033; }
        .oce-topbar { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 14px; align-items: center; margin-bottom: 12px; padding: 11px 14px; border-radius: 14px; background: #fff; border: 1px solid #eadfd2; box-shadow: 0 8px 22px rgba(124,69,20,.05); }
        .oce-title-block h1 { margin: 0; font-size: 20px; font-weight: 900; letter-spacing: -.025em; color: #172033; }
        .oce-title-block p { margin: 2px 0 0; color: #7a6a5b; font-size: 11px; font-weight: 800; line-height: 1.35; }
        .oce-top-actions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
        .oce-top-actions span { display: inline-flex; align-items: center; gap: 6px; min-height: 30px; padding: 0 10px; border-radius: 999px; border: 1px solid #fed7aa; background: #fff7ed; color: #9a3412; font-size: 11px; font-weight: 900; }
        .oce-top-actions strong { color: #172033; }
        .oce-eyebrow, .oce-kicker { display: inline-flex; color: #f59e0b; font-size: 10px; font-weight: 900; letter-spacing: .12em; text-transform: uppercase; }
        .oce-grid { display: grid; grid-template-columns: minmax(0,1fr) 390px; gap: 16px; align-items: start; }
        .oce-main, .oce-side { display: grid; gap: 16px; }
        .oce-side { position: sticky; top: 72px; }
        .oce-panel { background: rgba(255,255,255,.98); border-radius: 20px; border: 1px solid #eadfd2; box-shadow: 0 14px 36px rgba(124, 69, 20, .07); overflow: hidden; }
        .oce-panel-head { display: flex; justify-content: space-between; gap: 14px; align-items: center; padding: 15px 16px; border-bottom: 1px solid #f0e5da; }
        .oce-panel-head h2 { margin: 3px 0 0; font-size: 17px; color: #172033; font-weight: 900; letter-spacing: -.02em; }
        .oce-status, .oce-status-pill { display: inline-flex; align-items: center; min-height: 26px; padding: 0 9px; border-radius: 999px; background: #ffedd5; color: #9a3412; font-size: 11px; font-weight: 900; }
        .oce-setup-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 12px; padding: 14px 16px; }
        .oce-form-group { border: 1px solid #f0e5da; border-radius: 16px; background: #fffaf5; overflow: hidden; }
        .oce-form-group-head { padding: 12px 12px 0; }
        .oce-form-group-head strong { display: block; color: #172033; font-size: 13px; font-weight: 900; }
        .oce-form-group-head span { display: block; margin-top: 3px; color: #7a6a5b; font-size: 11px; font-weight: 800; line-height: 1.35; }
        .oce-form-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 12px; padding: 14px 16px; }
        .oce-form-grid--grouped { grid-template-columns: repeat(2, minmax(0,1fr)); padding: 12px; }
        .oce-description-row { padding: 0 16px 16px; }
        .oce-field { display: grid; gap: 6px; font-weight: 900; color: #5b6574; font-size: 11px; }
        .oce-field input, .oce-field select, .oce-textarea, .oce-small-textarea, .oce-content-select, .oce-compact-select { min-height: 38px; border: 1px solid #e5d8ca; border-radius: 12px; padding: 0 11px; color: #172033; background: #fffaf5; font-weight: 800; outline: none; width: 100%; }
        .oce-small-textarea { min-height: 70px; padding: 11px; line-height: 1.45; resize: vertical; }
        .oce-filter-bar { display: flex; gap: 8px; flex-wrap: wrap; padding: 12px 16px 0; }
        .oce-article-toolbar, .oce-target-actions-bar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; padding: 12px 16px 0; }
        .oce-article-toolbar input { min-width: 240px; min-height: 38px; border: 1px solid #e5d8ca; border-radius: 999px; padding: 0 13px; font-weight: 800; background: #fffaf5; outline: none; }
        .oce-inline-check { display: inline-flex; align-items: center; gap: 6px; min-height: 36px; border: 1px solid #e5d8ca; border-radius: 999px; padding: 0 12px; background: #fffaf5; font-weight: 900; color: #7a4a18; }
        .oce-filter-pill { min-height: 36px; border: 1px solid #e5d8ca; background: #fffaf5; color: #172033; border-radius: 999px; padding: 0 12px; display: inline-flex; align-items: center; gap: 7px; cursor: pointer; }
        .oce-filter-pill span { color: #7a6a5b; font-size: 11px; font-weight: 900; }
        .oce-link-btn { border: 1px solid #e5d8ca; background: #fffaf5; min-height: 32px; border-radius: 999px; padding: 0 11px; font-weight: 900; color: #7a4a18; cursor: pointer; font-size: 11px; }
        .oce-link-btn[disabled] { opacity: .45; cursor: not-allowed; }
        .oce-table-wrap { overflow-x: auto; padding: 12px 16px 16px; }
        .oce-table { width: 100%; border-collapse: collapse; min-width: 900px; }
        .oce-table th { position: sticky; top: 0; text-align: left; color: #7a6a5b; background: #fff7ed; font-size: 10px; text-transform: uppercase; letter-spacing: .08em; padding: 9px 8px; border-bottom: 1px solid #eadfd2; }
        .oce-table td { border-bottom: 1px solid #f0e5da; padding: 10px 8px; vertical-align: middle; font-size: 12px; color: #172033; }
        .oce-table tr.selected td { background: #fff7ed; }
        .oce-table td strong, .oce-table td span { display: block; }
        .oce-table td span { color: #7a6a5b; font-size: 11px; margin-top: 2px; }
        .oce-payment-chip, .oce-check-pill { display: inline-flex !important; align-items: center; gap: 4px; margin: 0 5px 0 0 !important; border-radius: 999px; padding: 5px 8px; background: #f1f5f9; color: #475569 !important; font-weight: 900; font-size: 10px !important; }
        .oce-target-head { align-items: center; }
        .oce-target-summary { display: flex; align-items: baseline; gap: 5px; color: #7a6a5b; }
        .oce-target-summary strong { color: #ea580c; font-size: 22px; }
        .oce-target-filter-bar { display: grid; grid-template-columns: minmax(220px,1fr) 120px 150px 150px 150px; gap: 8px; padding: 12px 16px 0; }
        .oce-target-filter-bar input { min-height: 38px; border: 1px solid #e5d8ca; border-radius: 999px; padding: 0 13px; font-weight: 800; background: #fffaf5; outline: none; }
        .oce-target-table-wrap { max-height: 430px; overflow: auto; }
        .oce-empty-row, .oce-empty-panel { text-align: center; color: #7a6a5b; padding: 26px !important; font-weight: 800; }
        .oce-content-panel { padding-bottom: 14px; }
        .oce-content-tabs { display: grid; grid-template-columns: repeat(3,1fr); gap: 8px; padding: 12px 16px 0; }
        .oce-content-tabs button { min-height: 34px; border: 1px solid #e5d8ca; background: #fffaf5; border-radius: 999px; color: #7a4a18; font-weight: 900; cursor: pointer; }
        .oce-content-tabs button.active { background: #231f20; color: #fff; border-color: #231f20; }
        .oce-channel-banner { margin: 12px 16px 0; padding: 10px 12px; border-radius: 14px; background: #fff7ed; color: #9a3412; font-size: 11px; font-weight: 900; }
        .oce-label { display: block; padding: 12px 16px 6px; font-weight: 900; color: #5b6574; font-size: 11px; }
        .oce-content-select { margin: 0 16px; width: calc(100% - 32px); }
        .oce-textarea { margin: 0 16px; width: calc(100% - 32px); min-height: 104px; padding: 11px; line-height: 1.45; resize: vertical; }
        .oce-email-textarea { min-height: 120px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
        .oce-call-textarea { min-height: 88px; }
        .oce-phone-preview { margin: 16px; border-radius: 24px; border: 8px solid #231f20; background: #f8fafc; padding: 15px; min-height: 250px; }
        .oce-phone-top { width: 66px; height: 6px; border-radius: 99px; background: #334155; margin: 0 auto 18px; }
        .oce-message-bubble { background: #dcfce7; color: #14532d; padding: 12px; border-radius: 16px 16px 4px 16px; font-weight: 800; line-height: 1.42; font-size: 12px; }
        .oce-preview-items { display: grid; gap: 7px; margin-top: 12px; }
        .oce-preview-items span { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 9px; color: #334155; font-size: 11px; font-weight: 900; }
        .oce-sticky-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; }
        .oce-sticky-actions .oce-btn-primary { grid-column: 1 / -1; }
        .oce-btn { border: 0; min-height: 42px; border-radius: 999px; padding: 0 14px; font-weight: 900; cursor: pointer; }
        .oce-btn-primary { background: #ea580c; color: #fff; box-shadow: 0 12px 26px rgba(234,88,12,.2); }
        .oce-btn-soft { background: #ffedd5; color: #9a3412; }
        .oce-btn-ghost { background: #fff; color: #172033; border: 1px solid #eadfd2; }
        .oce-pagination-bar { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 0 16px 16px; }
        .oce-pagination-meta { color: #7a6a5b; font-size: 11px; font-weight: 900; }
        .oce-pagination-actions { display: flex; gap: 8px; }
        .oce-field input:focus-visible, .oce-field select:focus-visible, .oce-textarea:focus-visible, .oce-small-textarea:focus-visible, .oce-content-select:focus-visible, .oce-compact-select:focus-visible, .oce-article-toolbar input:focus-visible, .oce-target-filter-bar input:focus-visible, .oce-link-btn:focus-visible, .oce-btn:focus-visible, .oce-content-tabs button:focus-visible { outline: 3px solid rgba(234,88,12,.24); outline-offset: 2px; }
        @media (max-width: 1240px) { .oce-grid, .oce-topbar { grid-template-columns: 1fr; } .oce-top-actions { justify-content: flex-start; } .oce-side { position: static; } .oce-form-grid, .oce-setup-grid { grid-template-columns: repeat(2, minmax(0,1fr)); } }
        @media (max-width: 780px) { .oce-shell { padding: 12px; } .oce-form-grid, .oce-form-grid--grouped, .oce-setup-grid, .oce-target-filter-bar, .oce-sticky-actions { grid-template-columns: 1fr; } .oce-panel-head, .oce-pagination-bar { flex-direction: column; align-items: stretch; } }
    `;
    document.head.appendChild(style);
}
