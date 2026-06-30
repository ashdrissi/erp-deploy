frappe.pages["campaign-editor"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Campaign Builder"),
        single_column: true,
    });

    wrapper.page = page;
    page.main.addClass("oce-root");
    injectCampaignEditorStyles();
    renderCampaignEditor(page);
    loadCampaignEditorData(page);
    applyCampaignEditorHeader(page);
};

frappe.pages["campaign-editor"].on_page_show = function (wrapper) {
    if (!wrapper.page) return;
    wrapper.page.main.addClass("oce-root");
    injectCampaignEditorStyles();
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
    activeContentAction: "WhatsApp",
    activeBuilderTab: "identity",
    previewTarget: "",
    renderedPreview: null,
    contentPreflight: null,
};

let OCE_ARTICLE_REFRESH_TIMER = null;
let OCE_TARGET_REFRESH_TIMER = null;
let OCE_CONTENT_PREVIEW_TIMER = null;
let OCE_CONTENT_PREVIEW_TOKEN = 0;

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
        ensurePreviewTarget();
        OCE_STATE.articleServerStart = Number(articlePaging.start || 0) + (articlePaging.rows || []).length;
        OCE_STATE.targetServerStart = Number(targetPaging.start || 0) + (targetPaging.rows || []).length;
        OCE_STATE.articleHasMore = Boolean(articlePaging.has_more);
        OCE_STATE.targetHasMore = Boolean(targetPaging.has_more);
        OCE_STATE.targetBusinessType = OCE_STATE.campaign.business_type_filter || "All";
        OCE_STATE.targetClass = OCE_STATE.campaign.crm_segment_filter || "All";
        OCE_STATE.activeContentAction = normalizeAction(OCE_STATE.campaign.campaign_action_type || OCE_STATE.campaign.default_channel);
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
    const today = defaultDate();
    return {
        name: campaign.name || null,
        campaign_name: campaign.campaign_name || "",
        campaign_owner: campaign.campaign_owner || frappe.session.user,
        campaign_date: campaign.campaign_date || today,
        start_date: campaign.start_date || today,
        end_date: campaign.end_date || today,
        sales_history_from_date: campaign.sales_history_from_date || today,
        sales_history_to_date: campaign.sales_history_to_date || today,
        campaign_action_type: normalizeAction(campaign.campaign_action_type || campaign.default_channel || "WhatsApp"),
        default_channel: channelForAction(campaign.campaign_action_type || campaign.default_channel || "WhatsApp"),
        target_family: campaign.target_family || "Distribution Partners",
        business_type_filter: campaign.business_type_filter || "",
        crm_segment_filter: campaign.crm_segment_filter || "",
        status: campaign.status || "Draft",
        partner_segment_filter: "",
        container_filter: campaign.container_filter || "",
        price_list_filter: campaign.price_list_filter || "",
        item_group_filter: campaign.item_group_filter || "",
        supplier_payment_mode_filter: campaign.supplier_payment_mode_filter || "",
        description: campaign.description || "",
        email_subject: campaign.email_subject || "Selected parts offer",
        email_mode: campaign.email_mode || "HTML",
        email_body: campaign.email_body || "",
        whatsapp_mode: normalizeWhatsAppMode(campaign.whatsapp_mode),
        whatsapp_template: campaign.whatsapp_template || "",
        whatsapp_template_language: campaign.whatsapp_template_language || "fr",
        whatsapp_template_variables: campaign.whatsapp_template_variables || "",
        whatsapp_text: campaign.whatsapp_text || "",
        call_script: campaign.call_script || "",
        visit_subject: campaign.visit_subject || campaign.visit_email_subject || "",
        visit_default_date: campaign.visit_default_date || campaign.campaign_date || today,
        visit_agenda: campaign.visit_agenda || campaign.visit_call_script || campaign.visit_whatsapp_text || campaign.visit_email_body || "",
        other_subject: campaign.other_subject || "",
        other_notes: campaign.other_notes || "",
        visit_email_subject: campaign.visit_email_subject || "",
        visit_email_mode: campaign.visit_email_mode || "HTML",
        visit_email_body: campaign.visit_email_body || "",
        visit_whatsapp_text: campaign.visit_whatsapp_text || "",
        visit_call_script: campaign.visit_call_script || "",
    };
}

function defaultDate() {
    if (frappe.datetime && frappe.datetime.now_date) return frappe.datetime.now_date();
    if (frappe.datetime && frappe.datetime.get_today) return frappe.datetime.get_today();
    return new Date().toISOString().slice(0, 10);
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
        crm_segment: target.crm_segment || "",
        partner_segment: target.partner_segment || "",
        crm_segments: target.crm_segments || [],
        city: target.city || "",
        target_status: target.target_status || "",
        assigned_to: target.assigned_to || "",
        target_note: target.target_note || "",
        contact_person_name: target.contact_person_name || target.contact || "",
        email: target.email || "",
        mobile_no: target.mobile_no || "",
        last_order_date: target.last_order_date || "",
        visit_date: target.visit_date || "",
        visit_status: target.visit_status || "",
        visit_todo: target.visit_todo || "",
    };
}

function normalizeAction(value) {
    return ["Email", "WhatsApp", "Call", "Visit", "Other"].includes(value) ? value : "WhatsApp";
}

function channelForAction(value) {
    const action = normalizeAction(value);
    return ["Email", "WhatsApp", "Call"].includes(action) ? action : "";
}

function normalizeWhatsAppMode(value) {
    if (["Twilio", "Custom Webhook"].includes(value)) return value;
    if (value === "Automated API") return "Custom Webhook";
    return "Manual Click-to-Chat";
}

function isAutomatedWhatsAppMode(value) {
    return ["Twilio", "Custom Webhook"].includes(normalizeWhatsAppMode(value));
}

function bindCampaignEditorEvents(page) {
    page.main.find("[data-route]").on("click", function () {
        frappe.set_route($(this).data("route"));
    });
    page.main.find("[data-builder-tab]").on("click", function () {
        OCE_STATE.activeBuilderTab = $(this).data("builder-tab");
        renderCampaignEditor(page);
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
        if (field === "campaign_action_type") {
            OCE_STATE.campaign.campaign_action_type = normalizeAction(OCE_STATE.campaign.campaign_action_type);
            OCE_STATE.campaign.default_channel = channelForAction(OCE_STATE.campaign.campaign_action_type);
            OCE_STATE.activeContentAction = OCE_STATE.campaign.campaign_action_type;
            OCE_STATE.renderedPreview = null;
            OCE_STATE.contentPreflight = null;
            renderCampaignEditor(page);
        }
        if (field === "email_mode" || field === "whatsapp_mode") {
            if (field === "whatsapp_mode") OCE_STATE.campaign.whatsapp_mode = normalizeWhatsAppMode(OCE_STATE.campaign.whatsapp_mode);
            OCE_STATE.renderedPreview = null;
            OCE_STATE.contentPreflight = null;
            renderCampaignEditor(page);
        }
        if (field === "business_type_filter") {
            OCE_STATE.targetBusinessType = OCE_STATE.campaign.business_type_filter || "All";
            OCE_STATE.targetClass = "All";
            OCE_STATE.campaign.crm_segment_filter = "";
            renderCampaignEditor(page);
        }
        if (field === "crm_segment_filter") {
            OCE_STATE.targetClass = OCE_STATE.campaign.crm_segment_filter || "All";
        }
    });
    page.main.find("[data-apply-article-filters]").on("click", function () {
        refreshArticles(page);
    });
    page.main.find("[data-reset-article-filters]").on("click", function () {
        resetArticleFilters(page);
    });
    page.main.find("[data-apply-target-filters]").on("click", function () {
        refreshTargets(page);
    });
    page.main.find("[data-reset-target-filters]").on("click", function () {
        resetTargetFilters(page);
    });
    page.main.find(".oce-live-field").on("input", function () {
        const field = $(this).data("field");
        OCE_STATE.campaign[field] = $(this).val();
        updateContentPreview(page);
    });
    page.main.find("#oce-preview-target").on("change", function () {
        OCE_STATE.previewTarget = $(this).val();
        OCE_STATE.renderedPreview = null;
        OCE_STATE.contentPreflight = null;
        updateContentPreview(page);
    });
    page.main.find("[data-email-tool]").on("click", function () {
        applyEmailTool(page, $(this).data("email-tool"));
    });
    page.main.find("[data-email-convert]").on("click", function () {
        convertEmailContent(page, $(this).data("email-convert"));
    });
    page.main.find("[data-email-upload-image]").on("click", function () {
        insertEmailImageFromUpload(page);
    });
    page.main.find("#oce-target-search").on("input", function () {
        OCE_STATE.targetSearch = String($(this).val() || "").trim().toLowerCase();
        page.main.find("#oce-target-body").html(targetRowsMarkup(currentTargets()));
        bindTargetSelection(page);
        queueTargetRefresh(page);
    });
    page.main.find("#oce-target-type").on("change", function () {
        OCE_STATE.targetType = $(this).val();
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

function resetArticleFilters(page) {
    Object.assign(OCE_STATE.campaign, {
        sales_history_from_date: defaultDate(),
        sales_history_to_date: defaultDate(),
        container_filter: "",
        price_list_filter: "",
        item_group_filter: "",
        supplier_payment_mode_filter: "",
    });
    OCE_STATE.articleSearch = "";
    OCE_STATE.articleOnlySelected = false;
    OCE_STATE.articlePage = 1;
    refreshArticles(page);
}

function resetTargetFilters(page) {
    OCE_STATE.campaign.business_type_filter = "";
    OCE_STATE.campaign.crm_segment_filter = "";
    OCE_STATE.targetSearch = "";
    OCE_STATE.targetBusinessType = "All";
    OCE_STATE.targetType = "All";
    OCE_STATE.targetClass = "All";
    OCE_STATE.targetSelected = "All";
    refreshTargets(page);
}

function updateContentPreview(page) {
    page.main.find("#oce-content-preview").html(contentPreviewMarkup(OCE_STATE.campaign || normalizeCampaign({})));
    queueRenderedContentPreview(page);
}

function queueRenderedContentPreview(page) {
    if (OCE_STATE.activeBuilderTab !== "content") return;
    clearTimeout(OCE_CONTENT_PREVIEW_TIMER);
    OCE_CONTENT_PREVIEW_TIMER = setTimeout(() => refreshRenderedContentPreview(page), 350);
}

async function refreshRenderedContentPreview(page) {
    const payload = collectCampaignPayload(page);
    const token = ++OCE_CONTENT_PREVIEW_TOKEN;
    const targetRows = payload.targets.map((row) => row.id || row.name || row.party_name).filter(Boolean);
    try {
        const [previewRes, preflightRes] = await Promise.all([
            frappe.call({
                method: "orderlift.orderlift_crm.api.campaign.render_campaign_content_from_payload",
                args: { payload: JSON.stringify(payload), target_row: OCE_STATE.previewTarget || null, action_type: OCE_STATE.activeContentAction },
            }),
            frappe.call({
                method: "orderlift.orderlift_crm.api.campaign.get_campaign_send_preflight",
                args: { payload: JSON.stringify(payload), target_rows: JSON.stringify(targetRows), action_type: OCE_STATE.activeContentAction },
            }),
        ]);
        if (token !== OCE_CONTENT_PREVIEW_TOKEN) return;
        OCE_STATE.renderedPreview = previewRes.message || null;
        OCE_STATE.contentPreflight = preflightRes.message || null;
        page.main.find("#oce-content-preview").html(contentPreviewMarkup(OCE_STATE.campaign || normalizeCampaign({})));
        page.main.find("#oce-content-readiness").html(contentPreflightMarkup());
    } catch (error) {
        console.error("Rendered campaign preview failed", error);
    }
}

function applyEmailTool(page, tool) {
    const emailBodyField = activeContentFields().email_body;
    const textarea = page.main.find(`[data-field="${emailBodyField}"]`).get(0);
    if (!textarea) return;
    const snippets = {
        bold: ["<strong>", "</strong>"],
        italic: ["<em>", "</em>"],
        paragraph: ["<p>", "</p>"],
        heading: ["<h2>", "</h2>"],
        heading_large: ["<h1>", "</h1>"],
        bullet: ["<ul>\n<li>", "</li>\n</ul>"],
        ordered: ["<ol>\n<li>", "</li>\n</ol>"],
        link: ['<a href="https://">', "</a>"],
        button: ['<a href="https://" style="display:inline-block;padding:12px 18px;border-radius:999px;background:#083344;color:#ffffff;text-decoration:none;font-weight:700;">', "</a>"],
        divider: ['<hr style="border:0;border-top:1px solid #e2e8f0;margin:24px 0;">', ""],
        table: ['<table><thead><tr><th>', '</th></tr></thead><tbody><tr><td>Value</td></tr></tbody></table>'],
        break: ["<br>", ""],
        image_url: ['<img src="https://" alt="" style="max-width:100%;height:auto;border-radius:12px;">', ""],
        first_name: ["{{ first_name }}", ""],
        contact_name: ["{{ contact_name }}", ""],
        company: ["{{ company }}", ""],
        articles: ["{{ selected_articles }}", ""],
        visit_date: ["{{ visit_date }}", ""],
    };
    const pair = snippets[tool];
    if (!pair) return;
    const start = textarea.selectionStart || 0;
    const end = textarea.selectionEnd || 0;
    const before = textarea.value.slice(0, start);
    const selected = textarea.value.slice(start, end);
    const after = textarea.value.slice(end);
    textarea.value = `${before}${pair[0]}${selected}${pair[1]}${after}`;
    textarea.focus();
    textarea.selectionStart = start + pair[0].length;
    textarea.selectionEnd = start + pair[0].length + selected.length;
    OCE_STATE.campaign[emailBodyField] = textarea.value;
    updateContentPreview(page);
}

function convertEmailContent(page, action) {
    const textarea = page.main.find('[data-field="email_body"]').get(0);
    if (!textarea) return;
    if (action === "html_to_text") {
        textarea.value = htmlToText(textarea.value);
        OCE_STATE.campaign.email_mode = "Text";
        OCE_STATE.campaign.email_body = textarea.value;
        renderCampaignEditor(page);
        return;
    }
    if (action === "text_to_html") {
        textarea.value = textToHtml(textarea.value);
        OCE_STATE.campaign.email_mode = "HTML";
        OCE_STATE.campaign.email_body = textarea.value;
        renderCampaignEditor(page);
        return;
    }
    if (action === "clean_html") {
        textarea.value = cleanEmailHtml(textarea.value);
        OCE_STATE.campaign.email_mode = "HTML";
        OCE_STATE.campaign.email_body = textarea.value;
        renderCampaignEditor(page);
    }
}

function insertEmailImageFromUpload(page) {
    if (frappe.ui && frappe.ui.FileUploader) {
        new frappe.ui.FileUploader({
            restrictions: { allowed_file_types: ["image/*"] },
            on_success(file) {
                const url = file.file_url || file.file_name || "";
                if (!url) return;
                insertEmailSnippet(page, `<img src="${frappe.utils.escape_html(url)}" alt="" style="max-width:100%;height:auto;border-radius:12px;">`, "");
            },
        });
        return;
    }
    frappe.prompt(
        [{ fieldname: "image_url", fieldtype: "Data", label: __("Image URL"), reqd: 1 }],
        (values) => insertEmailSnippet(page, `<img src="${frappe.utils.escape_html(values.image_url)}" alt="" style="max-width:100%;height:auto;border-radius:12px;">`, ""),
        __("Insert Image"),
        __("Insert")
    );
}

function insertEmailSnippet(page, before, after = "") {
    const textarea = page.main.find('[data-field="email_body"]').get(0);
    if (!textarea) return;
    const start = textarea.selectionStart || 0;
    const end = textarea.selectionEnd || 0;
    const selected = textarea.value.slice(start, end);
    textarea.value = `${textarea.value.slice(0, start)}${before}${selected}${after}${textarea.value.slice(end)}`;
    OCE_STATE.campaign.email_body = textarea.value;
    textarea.focus();
    updateContentPreview(page);
}

function htmlToText(value) {
    if (!value) return "";
    const parser = new DOMParser();
    const doc = parser.parseFromString(value, "text/html");
    doc.querySelectorAll("br").forEach((node) => node.replaceWith("\n"));
    doc.querySelectorAll("p,div,li,tr,h1,h2,h3").forEach((node) => node.append("\n"));
    return (doc.body.textContent || "").replace(/\n{3,}/g, "\n\n").trim();
}

function textToHtml(value) {
    return String(value || "")
        .split(/\n{2,}/)
        .map((block) => `<p>${frappe.utils.escape_html(block).replace(/\n/g, "<br>")}</p>`)
        .join("\n");
}

function cleanEmailHtml(value) {
    if (!value) return "";
    const parser = new DOMParser();
    const doc = parser.parseFromString(value, "text/html");
    doc.querySelectorAll("script,style,iframe,object,embed").forEach((node) => node.remove());
    doc.querySelectorAll("*").forEach((node) => {
        [...node.attributes].forEach((attr) => {
            if (/^on/i.test(attr.name)) node.removeAttribute(attr.name);
        });
    });
    return (doc.body.innerHTML || "").trim();
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

function ensurePreviewTarget() {
    const selectedTargets = OCE_STATE.targets.filter((row) => row.selected);
    if (selectedTargets.some((row) => row.id === OCE_STATE.previewTarget)) return;
    OCE_STATE.previewTarget = selectedTargets.length ? selectedTargets[0].id : "";
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
    payload.campaign_action_type = normalizeAction(payload.campaign_action_type || OCE_STATE.activeContentAction || payload.default_channel || "WhatsApp");
    payload.default_channel = channelForAction(payload.campaign_action_type);
    payload.whatsapp_mode = normalizeWhatsAppMode(payload.whatsapp_mode);
    payload.partner_segment_filter = "";
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
    const campaign = OCE_STATE.campaign || normalizeCampaign({});
    const businessType = OCE_STATE.targetBusinessType === "All" ? campaign.business_type_filter : OCE_STATE.targetBusinessType;
    return (OCE_STATE.segments || [])
        .filter((row) => !businessType || businessType === "All" || row.business_type === businessType)
        .map((row) => row.name);
}

function campaignField(fieldname) {
    const campaign = OCE_STATE.campaign || normalizeCampaign({});
    return campaign[fieldname] || "";
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
    const action = OCE_STATE.activeContentAction;
    if (action === "Email") {
        return `
            <label class="oce-label">${__("Email subject")}</label>
            <input class="oce-content-select oce-live-field" data-field="email_subject" value="${frappe.utils.escape_html(campaign.email_subject || "")}" />
            <label class="oce-label">${__("Email mode")}</label>
            <select class="oce-content-select" data-field="email_mode">
                <option value="HTML" ${(campaign.email_mode || "HTML") === "HTML" ? "selected" : ""}>${__("HTML")}</option>
                <option value="Text" ${campaign.email_mode === "Text" ? "selected" : ""}>${__("Text")}</option>
            </select>
            <div class="oce-editor-toolbar" aria-label="${frappe.utils.escape_html(__("Email editing tools"))}">
                <button type="button" data-email-tool="paragraph">${__("Paragraph")}</button>
                <button type="button" data-email-tool="heading_large">${__("H1")}</button>
                <button type="button" data-email-tool="bold">${__("Bold")}</button>
                <button type="button" data-email-tool="italic">${__("Italic")}</button>
                <button type="button" data-email-tool="heading">${__("Heading")}</button>
                <button type="button" data-email-tool="bullet">${__("Bullets")}</button>
                <button type="button" data-email-tool="ordered">${__("Numbers")}</button>
                <button type="button" data-email-tool="link">${__("Link")}</button>
                <button type="button" data-email-tool="button">${__("CTA")}</button>
                <button type="button" data-email-tool="divider">${__("Divider")}</button>
                <button type="button" data-email-tool="table">${__("Table")}</button>
                <button type="button" data-email-tool="image_url">${__("Image URL")}</button>
                <button type="button" data-email-upload-image="1">${__("Upload Image")}</button>
                <button type="button" data-email-tool="break">${__("Break")}</button>
                <button type="button" data-email-tool="first_name">${__("First name")}</button>
                <button type="button" data-email-tool="contact_name">${__("Contact")}</button>
                <button type="button" data-email-tool="company">${__("Company")}</button>
                <button type="button" data-email-tool="articles">${__("Articles")}</button>
                <button type="button" data-email-tool="visit_date">${__("Visit date")}</button>
            </div>
            <div class="oce-editor-toolbar oce-editor-toolbar--soft" aria-label="${frappe.utils.escape_html(__("Email conversion tools"))}">
                <button type="button" data-email-convert="text_to_html">${__("Text to HTML")}</button>
                <button type="button" data-email-convert="html_to_text">${__("HTML to Text")}</button>
                <button type="button" data-email-convert="clean_html">${__("Clean HTML")}</button>
            </div>
            <label class="oce-label">${__("Email text / HTML")}</label>
            <textarea class="oce-textarea oce-email-textarea oce-live-field" data-field="email_body">${frappe.utils.escape_html(campaign.email_body || "")}</textarea>
        `;
    }
    if (action === "WhatsApp") {
        const mode = normalizeWhatsAppMode(campaign.whatsapp_mode);
        return `
            <label class="oce-label">${__("WhatsApp mode")}</label>
            <select class="oce-content-select" data-field="whatsapp_mode">
                <option value="Manual Click-to-Chat" ${mode === "Manual Click-to-Chat" ? "selected" : ""}>${__("Manual Click-to-Chat")}</option>
                <option value="Twilio" ${mode === "Twilio" ? "selected" : ""}>${__("Twilio")}</option>
                <option value="Custom Webhook" ${mode === "Custom Webhook" ? "selected" : ""}>${__("Custom Webhook")}</option>
            </select>
            ${whatsappModeFieldsMarkup(campaign, mode)}
        `;
    }
    if (action === "Call") {
        return `
            <label class="oce-label">${__("Call script")}</label>
            <textarea class="oce-textarea oce-call-textarea oce-live-field" data-field="call_script">${frappe.utils.escape_html(campaign.call_script || "")}</textarea>
        `;
    }
    if (action === "Visit") {
        return `
            <label class="oce-label">${__("Visit subject")}</label>
            <input class="oce-content-select oce-live-field" data-field="visit_subject" value="${frappe.utils.escape_html(campaign.visit_subject || "")}" />
            <label class="oce-label">${__("Default visit date")}</label>
            <input class="oce-content-select" type="date" data-field="visit_default_date" value="${frappe.utils.escape_html(campaign.visit_default_date || "")}" />
            <label class="oce-label">${__("Visit agenda")}</label>
            <textarea class="oce-textarea oce-call-textarea oce-live-field" data-field="visit_agenda">${frappe.utils.escape_html(campaign.visit_agenda || "")}</textarea>
            <div class="oce-channel-banner">${__("Target-specific visit dates and ToDos are managed from Campaign Manager.")}</div>
        `;
    }
    return `
        <label class="oce-label">${__("Other subject")}</label>
        <input class="oce-content-select oce-live-field" data-field="other_subject" value="${frappe.utils.escape_html(campaign.other_subject || "")}" />
        <label class="oce-label">${__("Other notes")}</label>
        <textarea class="oce-textarea oce-call-textarea oce-live-field" data-field="other_notes">${frappe.utils.escape_html(campaign.other_notes || "")}</textarea>
    `;
}

function whatsappModeFieldsMarkup(campaign, mode) {
    if (mode === "Manual Click-to-Chat") {
        return `
            <div class="oce-channel-banner">${__("Manual mode opens WhatsApp Web/Desktop with a prefilled message. The user sends it manually.")}</div>
            <label class="oce-label">${__("WhatsApp text")}</label>
            <textarea class="oce-textarea oce-live-field" data-field="whatsapp_text">${frappe.utils.escape_html(campaign.whatsapp_text || "")}</textarea>
        `;
    }
    if (mode === "Twilio") {
        return `
            <div class="oce-channel-banner">${__("Twilio mode sends a Meta-approved template. Use the Twilio Content SID as the template.")}</div>
            <div class="oce-template-grid">
                <label class="oce-template-wide"><span>${__("Twilio Content SID")}</span><input class="oce-live-field" data-field="whatsapp_template" value="${frappe.utils.escape_html(campaign.whatsapp_template || "")}" placeholder="HXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" /></label>
                <label><span>${__("Language")}</span><input class="oce-live-field" data-field="whatsapp_template_language" value="${frappe.utils.escape_html(campaign.whatsapp_template_language || "fr")}" /></label>
                <label class="oce-template-wide"><span>${__("Content variables")}</span><textarea class="oce-live-field" data-field="whatsapp_template_variables" placeholder='${frappe.utils.escape_html('{"1":"{{ contact_name }}","2":"{{ campaign_name }}"}') }'>${frappe.utils.escape_html(campaign.whatsapp_template_variables || "")}</textarea></label>
            </div>
        `;
    }
    return `
        <div class="oce-channel-banner">${__("Custom Webhook mode sends this payload to the configured webhook, such as Make.com.")}</div>
        <label class="oce-label">${__("Webhook message")}</label>
        <textarea class="oce-textarea oce-live-field" data-field="whatsapp_text">${frappe.utils.escape_html(campaign.whatsapp_text || "")}</textarea>
        <div class="oce-template-grid">
            <label><span>${__("Template name")}</span><input class="oce-live-field" data-field="whatsapp_template" value="${frappe.utils.escape_html(campaign.whatsapp_template || "")}" placeholder="${frappe.utils.escape_html(__("Optional approved template name"))}" /></label>
            <label><span>${__("Language")}</span><input class="oce-live-field" data-field="whatsapp_template_language" value="${frappe.utils.escape_html(campaign.whatsapp_template_language || "fr")}" /></label>
            <label class="oce-template-wide"><span>${__("Webhook variables")}</span><textarea class="oce-live-field" data-field="whatsapp_template_variables" placeholder='${frappe.utils.escape_html('{"1":"{{ contact_name }}","2":"{{ campaign_name }}"}') }'>${frappe.utils.escape_html(campaign.whatsapp_template_variables || "")}</textarea></label>
        </div>
    `;
}

function activeContentFields() {
    return {
        email_subject: "email_subject",
        email_mode: "email_mode",
        email_body: "email_body",
        whatsapp_text: "whatsapp_text",
        call_script: "call_script",
    };
}

function contentPreviewMarkup(campaign, selectedArticles = []) {
    const action = OCE_STATE.activeContentAction;
    const rendered = OCE_STATE.renderedPreview && OCE_STATE.renderedPreview.action_type === action ? OCE_STATE.renderedPreview : null;
    if (action === "Email") {
        const subject = (rendered && rendered.subject) || campaign.email_subject || __("No subject");
        const body = (rendered && rendered.body) || campaign.email_body || `<p>${__("Add email content to preview it here.")}</p>`;
        const emailMode = campaign.email_mode || "HTML";
        return `
            <div class="oce-preview-head"><span>${rendered ? __("Rendered Email Preview") : __("Email Preview")}</span><strong>${frappe.utils.escape_html(subject)}</strong></div>
            ${emailMode === "HTML" ? `<iframe class="oce-html-preview" sandbox srcdoc="${frappe.utils.escape_html(emailPreviewDocument(body))}"></iframe>` : `<pre class="oce-text-preview">${frappe.utils.escape_html(body)}</pre>`}
        `;
    }
    if (action === "Visit") {
        return `
            <div class="oce-preview-head"><span>${__("Visit Preview")}</span><strong>${frappe.utils.escape_html(campaign.visit_subject || __("No subject"))}</strong></div>
            <pre class="oce-text-preview">${frappe.utils.escape_html(campaign.visit_agenda || __("Add a visit agenda to preview it here."))}</pre>
        `;
    }
    if (action === "Call") {
        return `
            <div class="oce-preview-head"><span>${__("Call Preview")}</span><strong>${selectedArticles.length} ${__("articles")}</strong></div>
            <pre class="oce-text-preview">${frappe.utils.escape_html(campaign.call_script || __("Add a call script to preview it here."))}</pre>
        `;
    }
    if (action === "Other") {
        return `
            <div class="oce-preview-head"><span>${__("Other Preview")}</span><strong>${frappe.utils.escape_html(campaign.other_subject || __("No subject"))}</strong></div>
            <pre class="oce-text-preview">${frappe.utils.escape_html(campaign.other_notes || __("Add notes for this campaign action."))}</pre>
        `;
    }
    return `
        <div class="oce-preview-head"><span>${__("WhatsApp Preview")}</span><strong>${frappe.utils.escape_html(normalizeWhatsAppMode(campaign.whatsapp_mode))}</strong></div>
        <div class="oce-phone-preview">
            <div class="oce-phone-top"></div>
            <div class="oce-message-bubble">${frappe.utils.escape_html(activePreviewText(campaign, rendered).slice(0, 420))}</div>
            <div class="oce-preview-items">
                ${selectedArticles.length ? selectedArticles.slice(0, 5).map((row) => `<span>${frappe.utils.escape_html(row.item_code)} - ${row.display_available_qty ? `${row.available_qty_snapshot} ${__("available")}` : __("qty hidden")} - ${row.display_price ? formatMoney(row.price_snapshot) : __("price hidden")}</span>`).join("") : `<span>${__("No selected articles yet")}</span>`}
            </div>
            ${rendered && rendered.variables ? `<pre class="oce-whatsapp-vars">${frappe.utils.escape_html(JSON.stringify(rendered.variables, null, 2))}</pre>` : ""}
        </div>
    `;
}

function emailPreviewDocument(body) {
    return `<!doctype html><html><head><meta charset="utf-8"><style>body{margin:0;padding:18px;font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#0f172a;background:#fff;line-height:1.55}a{color:#0891b2}img{max-width:100%;height:auto}table{border-collapse:collapse;width:100%}td,th{border:1px solid #e2e8f0;padding:8px}</style></head><body>${body}</body></html>`;
}

function activePreviewText(campaign, rendered = null) {
    if (rendered) {
        return rendered.text || rendered.template || rendered.script || rendered.agenda || rendered.notes || "";
    }
    if (OCE_STATE.activeContentAction === "Email") {
        return campaign.email_body || campaign.email_subject || __("Add email content to preview it here.");
    }
    if (OCE_STATE.activeContentAction === "Call") {
        return campaign.call_script || __("Add a call script to preview it here.");
    }
    if (OCE_STATE.activeContentAction === "Visit") {
        return campaign.visit_agenda || campaign.visit_subject || __("Add a visit agenda to preview it here.");
    }
    if (OCE_STATE.activeContentAction === "Other") {
        return campaign.other_notes || campaign.other_subject || __("Add notes to preview them here.");
    }
    const whatsappMode = normalizeWhatsAppMode(campaign.whatsapp_mode);
    if (whatsappMode === "Twilio") {
        return [campaign.whatsapp_template || __("Add Twilio Content SID"), campaign.whatsapp_template_variables || __("Add template variables")].filter(Boolean).join("\n");
    }
    if (whatsappMode === "Custom Webhook") {
        return campaign.whatsapp_text || campaign.whatsapp_template || __("Add webhook message or template.");
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
    const action = normalizeAction(campaign.campaign_action_type || campaign.default_channel);
    if (action === "Email") return Boolean(stripHtml(campaign.email_body || ""));
    if (action === "WhatsApp") {
        const mode = normalizeWhatsAppMode(campaign.whatsapp_mode);
        if (mode === "Twilio") return Boolean((campaign.whatsapp_template || "").trim());
        if (mode === "Custom Webhook") return Boolean((campaign.whatsapp_text || "").trim() || (campaign.whatsapp_template || "").trim());
        return Boolean((campaign.whatsapp_text || "").trim());
    }
    if (action === "Call") return Boolean((campaign.call_script || "").trim());
    if (action === "Visit") return Boolean((campaign.visit_subject || "").trim() || (campaign.visit_agenda || "").trim());
    if (action === "Other") return Boolean((campaign.other_subject || "").trim() || (campaign.other_notes || "").trim());
    return false;
}

function stripHtml(value) {
    const div = document.createElement("div");
    div.innerHTML = value || "";
    return (div.textContent || div.innerText || "").trim();
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
            <td>${formatMoney(article.price_snapshot || 0)}</td>
            <td><label class="oce-check-pill"><input class="oce-article-toggle" type="checkbox" data-item="${frappe.utils.escape_html(article.item_code)}" data-field="display_price" ${article.display_price ? "checked" : ""}> ${__("Price")}</label><label class="oce-check-pill"><input class="oce-article-toggle" type="checkbox" data-item="${frappe.utils.escape_html(article.item_code)}" data-field="display_available_qty" ${article.display_available_qty ? "checked" : ""}> ${__("Qty")}</label></td>
        </tr>
    `;
}

function formatMoney(value) {
    return window.orderlift?.formatCurrency ? window.orderlift.formatCurrency(value) : Number(value || 0).toLocaleString();
}

function targetRowsMarkup(rows) {
    if (!rows.length) {
        return `<tr><td class="oce-empty-row" colspan="10">${__("No targets match the current filters.")}</td></tr>`;
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
            <td>${frappe.utils.escape_html(target.email || "-")}</td>
            <td>${frappe.utils.escape_html(target.mobile_no || "-")}</td>
            <td><span class="oce-status-pill">${frappe.utils.escape_html(target.target_status || "-")}</span></td>
        </tr>
    `).join("");
}

function renderCampaignEditor(page) {
    if (!OCE_STATE.campaign) {
        OCE_STATE.campaign = normalizeCampaign({});
    }
    const campaign = OCE_STATE.campaign;
    const selectedArticles = OCE_STATE.articles.filter((row) => row.selected);
    const selectedTargets = OCE_STATE.targets.filter((row) => row.selected);
    const readiness = campaignReadiness(campaign, selectedArticles, selectedTargets);
    const readinessHint = readiness.missing.length ? `${__("Missing")}: ${readiness.missing.join(", ")}` : __("Ready to run");
    page.main.html(`
        <div class="oce-shell">
            <section class="oce-topbar">
                <div class="oce-title-block">
                    <span>${__("Commercial Campaigns")}</span>
                    <h1>${campaign.name ? frappe.utils.escape_html(campaign.campaign_name || campaign.name) : __("Campaign Builder")}</h1>
                    <p>${__("Build identity, audience, offer articles, and outreach content from one focused workspace.")}</p>
                </div>
                <div class="oce-top-actions">
                    <span><strong>${selectedTargets.length}</strong> ${__("targets")}</span>
                    <span><strong>${selectedArticles.length}</strong> ${__("articles")}</span>
                    <span><strong>${readiness.score}/4</strong> ${frappe.utils.escape_html(readinessHint)}</span>
                </div>
            </section>

            <section class="oce-tab-shell">
                <nav class="oce-builder-tabs" aria-label="${frappe.utils.escape_html(__("Campaign builder sections"))}">
                    ${builderTabsMarkup(readiness, selectedArticles.length, selectedTargets.length)}
                </nav>
                ${activeBuilderTabMarkup(campaign, selectedArticles, selectedTargets, readiness)}
            </section>

            <div class="oce-sticky-actions">
                <button class="oce-btn oce-btn-ghost" data-route="campaign-manager">${__("Cancel")}</button>
                <button class="oce-btn oce-btn-soft" data-save="1" data-save-mode="draft">${__("Save Draft")}</button>
                <button class="oce-btn oce-btn-primary" data-save="1" data-save-mode="campaign">${__("Save Campaign")}</button>
            </div>
        </div>
    `);

    bindCampaignEditorEvents(page);
    if (OCE_STATE.activeBuilderTab === "content") {
        ensurePreviewTarget();
        queueRenderedContentPreview(page);
    }
}

function builderTabsMarkup(readiness, selectedArticleCount, selectedTargetCount) {
    const tabs = [
        { key: "identity", label: __("Campaign"), meta: OCE_STATE.campaign.status || __("Draft") },
        { key: "articles", label: __("Articles"), meta: selectedArticleCount },
        { key: "targets", label: __("Targets"), meta: selectedTargetCount },
        { key: "content", label: __("Content"), meta: `${readiness.score}/4` },
        { key: "summary", label: __("Summary"), meta: readiness.missing.length ? readiness.missing.length : __("Ready") },
    ];
    return tabs.map((tab) => `
        <button type="button" class="${OCE_STATE.activeBuilderTab === tab.key ? "active" : ""}" data-builder-tab="${tab.key}">
            <span>${frappe.utils.escape_html(tab.label)}</span>
            <strong>${frappe.utils.escape_html(String(tab.meta))}</strong>
        </button>
    `).join("");
}

function activeBuilderTabMarkup(campaign, selectedArticles, selectedTargets, readiness) {
    if (OCE_STATE.activeBuilderTab === "articles") return articlesTabMarkup(campaign);
    if (OCE_STATE.activeBuilderTab === "targets") return targetsTabMarkup();
    if (OCE_STATE.activeBuilderTab === "content") return contentTabMarkup(campaign, selectedArticles);
    if (OCE_STATE.activeBuilderTab === "summary") return summaryTabMarkup(campaign, selectedArticles, selectedTargets, readiness);
    return identityTabMarkup(campaign);
}

function identityTabMarkup(campaign) {
    return `
        <article class="oce-panel oce-tab-panel">
            <div class="oce-panel-head">
                <div><span class="oce-kicker">${__("Campaign")}</span><h2>${__("Identity, owner, and schedule")}</h2></div>
                <span class="oce-status">${frappe.utils.escape_html(campaign.status)}</span>
            </div>
            <div class="oce-setup-grid">
                ${formGroup(__("Identity"), __("Name, owner, status, and default outreach channel."), `
                    ${formField("campaign_name", __("Campaign name"), campaign.campaign_name)}
                    ${formField("campaign_owner", __("Person in charge"), campaign.campaign_owner)}
                    ${selectField("status", __("Campaign status"), ["Draft", "Ready", "Running", "Paused", "Closed"], campaign.status)}
                    ${selectField("campaign_action_type", __("Campaign type"), ["WhatsApp", "Email", "Call", "Visit", "Other"], campaign.campaign_action_type)}
                `)}
                ${formGroup(__("Schedule"), __("Campaign timing and execution window."), `
                    ${formField("campaign_date", __("Campaign date"), campaign.campaign_date, "date")}
                    ${formField("start_date", __("Start date"), campaign.start_date, "date")}
                    ${formField("end_date", __("End date"), campaign.end_date, "date")}
                `)}
            </div>
            <div class="oce-description-row">
                <label class="oce-field oce-wide-field">
                    <span>${__("Campaign description")}</span>
                    <textarea class="oce-small-textarea" data-field="description">${frappe.utils.escape_html(campaign.description)}</textarea>
                </label>
            </div>
        </article>
    `;
}

function articlesTabMarkup(campaign) {
    const articleView = currentArticles();
    return `
        <article class="oce-panel oce-tab-panel">
            <div class="oce-panel-head">
                <div><span class="oce-kicker">${__("Article Selection")}</span><h2>${__("Search, filter, and select offer articles")}</h2></div>
                <div class="oce-panel-actions">
                    <button class="oce-link-btn" data-apply-article-filters="1">${__("Apply Filters")}</button>
                    <button class="oce-link-btn" data-reset-article-filters="1">${__("Reset")}</button>
                    <button class="oce-link-btn" data-reload-articles="1">${__("Refresh")}</button>
                </div>
            </div>
            <div class="oce-standard-filters">
                <label class="oce-field oce-wide-filter"><span>${__("Search")}</span><input id="oce-article-search" type="search" placeholder="${__("Article code, name, or item group")}" value="${frappe.utils.escape_html(OCE_STATE.articleSearch)}" /></label>
                ${formField("sales_history_from_date", __("Sales history from"), campaign.sales_history_from_date, "date")}
                ${formField("sales_history_to_date", __("Sales history to"), campaign.sales_history_to_date, "date")}
                ${optionSelectField("container_filter", __("Container"), OCE_STATE.filterOptions.containers.map((row) => row.name), campaign.container_filter)}
                ${optionSelectField("price_list_filter", __("Price list"), OCE_STATE.filterOptions.price_lists.map((row) => row.name), campaign.price_list_filter)}
                ${optionSelectField("item_group_filter", __("Item group"), OCE_STATE.filterOptions.item_groups.map((row) => row.name), campaign.item_group_filter)}
                ${selectField("supplier_payment_mode_filter", __("Supplier payment"), ["", "Paid Before Delivery", "Supplier Payment Delay"], campaign.supplier_payment_mode_filter)}
            </div>
            <div class="oce-selection-toolbar">
                <strong>${articleView.rows.filter((row) => row.selected).length} ${__("selected")}</strong>
                <select id="oce-article-page-size" class="oce-compact-select">
                    ${[8, 12, 20].map((size) => `<option value="${size}" ${size === OCE_STATE.articlePageSize ? "selected" : ""}>${size} ${__("per page")}</option>`).join("")}
                </select>
                <label class="oce-inline-check"><input id="oce-article-selected-only" type="checkbox" ${OCE_STATE.articleOnlySelected ? "checked" : ""} /> ${__("Selected only")}</label>
                <button class="oce-link-btn" data-article-bulk="select">${__("Select visible")}</button>
                <button class="oce-link-btn" data-article-bulk="clear">${__("Clear visible")}</button>
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
    `;
}

function targetsTabMarkup() {
    const filteredTargets = currentTargets();
    return `
        <article class="oce-panel oce-tab-panel">
            <div class="oce-panel-head oce-target-head">
                <div><span class="oce-kicker">${__("Audience Selection")}</span><h2>${__("Filter CRM parties and select campaign targets")}</h2></div>
                <div class="oce-target-summary"><strong>${filteredTargets.length}</strong><span>${__("visible")}</span></div>
            </div>
            <div class="oce-standard-filters oce-target-standard-filters">
                <label class="oce-field oce-wide-filter"><span>${__("Search")}</span><input id="oce-target-search" type="search" placeholder="${__("Company, city, contact, or document")}" value="${frappe.utils.escape_html(OCE_STATE.targetSearch)}" /></label>
                <label class="oce-field"><span>${__("Party type")}</span>${compactSelect("oce-target-type", ["All", "Lead", "Prospect", "Customer"], OCE_STATE.targetType)}</label>
                ${optionSelectField("business_type_filter", __("Business type"), OCE_STATE.businessTypes.map((row) => row.name), campaignField("business_type_filter"))}
                ${optionSelectField("crm_segment_filter", __("CRM segment"), currentSegmentOptions(), campaignField("crm_segment_filter"))}
                <label class="oce-field"><span>${__("Selection")}</span>${compactSelect("oce-target-selected", ["All", "Selected", "Not selected"], OCE_STATE.targetSelected)}</label>
            </div>
            <div class="oce-selection-toolbar">
                <strong>${OCE_STATE.targets.filter((row) => row.selected).length} ${__("selected")}</strong>
                <span class="oce-pagination-meta">${OCE_STATE.targets.length} ${__("loaded candidates")}</span>
                <button class="oce-link-btn" data-apply-target-filters="1">${__("Apply Filters")}</button>
                <button class="oce-link-btn" data-reset-target-filters="1">${__("Reset")}</button>
                <button class="oce-link-btn" data-reload-targets="1">${__("Refresh")}</button>
                <button class="oce-link-btn" data-load-more-targets="1" ${!OCE_STATE.targetHasMore || OCE_STATE.targetLoading ? "disabled" : ""}>${OCE_STATE.targetLoading ? __("Loading") : __("Load more candidates")}</button>
                <button class="oce-link-btn" data-target-bulk="select">${__("Select visible")}</button>
                <button class="oce-link-btn" data-target-bulk="clear">${__("Clear visible")}</button>
            </div>
            <div class="oce-table-wrap oce-target-table-wrap">
                ${OCE_STATE.targets.length ? `<table class="oce-table oce-target-table"><thead><tr><th>${__("Select")}</th><th>${__("Company")}</th><th>${__("Party")}</th><th>${__("Type")}</th><th>${__("Segment")}</th><th>${__("City")}</th><th>${__("Contact")}</th><th>${__("Email")}</th><th>${__("Mobile")}</th><th>${__("Status")}</th></tr></thead><tbody id="oce-target-body">${targetRowsMarkup(filteredTargets)}</tbody></table>` : `<div class="oce-empty-panel">${__("No Lead, Prospect, or Customer records available for selection.")}</div>`}
            </div>
        </article>
    `;
}

function contentTabMarkup(campaign, selectedArticles) {
    ensurePreviewTarget();
    return `
        <article class="oce-panel oce-tab-panel oce-content-panel">
            <div class="oce-panel-head">
                <div><span class="oce-kicker">${__("Campaign Content")}</span><h2>${__("Message editor and live preview")}</h2></div>
                <span class="oce-status">${frappe.utils.escape_html(OCE_STATE.activeContentAction)}</span>
            </div>
            <div class="oce-channel-banner">${__("Editing only the selected campaign type: {0}.", [OCE_STATE.activeContentAction])}</div>
            <div id="oce-content-readiness">${contentPreflightMarkup()}</div>
            <div class="oce-content-grid">
                <section class="oce-content-editor">${activeContentMarkup(campaign)}</section>
                <section class="oce-content-preview-shell">
                    ${previewTargetMarkup()}
                    <div id="oce-content-preview" class="oce-content-preview">${contentPreviewMarkup(campaign, selectedArticles)}</div>
                </section>
            </div>
        </article>
    `;
}

function previewTargetMarkup() {
    const selectedTargets = OCE_STATE.targets.filter((row) => row.selected);
    if (!selectedTargets.length) {
        return `<div class="oce-preview-target-bar">${__("Select at least one target to preview rendered personalization.")}</div>`;
    }
    return `
        <label class="oce-preview-target-bar">
            <span>${__("Preview as target")}</span>
            <select id="oce-preview-target">
                ${selectedTargets.map((target) => `<option value="${frappe.utils.escape_html(target.id)}" ${target.id === OCE_STATE.previewTarget ? "selected" : ""}>${frappe.utils.escape_html(target.display_name || target.party_name)}</option>`).join("")}
            </select>
        </label>
    `;
}

function contentPreflightMarkup() {
    const preflight = OCE_STATE.contentPreflight;
    if (!preflight) {
        return `<div class="oce-readiness oce-readiness-neutral">${__("Rendered readiness will appear after preview refreshes.")}</div>`;
    }
    const blockers = [
        ...(preflight.campaign_blockers || []),
        ...((preflight.targets || []).flatMap((row) => (row.blockers || []).map((message) => `${row.label}: ${message}`))),
    ];
    const warnings = [
        ...(preflight.campaign_warnings || []),
        ...((preflight.targets || []).flatMap((row) => (row.warnings || []).map((message) => `${row.label}: ${message}`))),
    ];
    if (!blockers.length && !warnings.length) {
        return `<div class="oce-readiness oce-readiness-ok">${__("Ready")}: ${preflight.ready_count}/${preflight.target_count} ${__("selected targets can receive this outreach.")}</div>`;
    }
    return `
        <div class="oce-readiness ${blockers.length ? "oce-readiness-blocked" : "oce-readiness-warning"}">
            <strong>${blockers.length ? __("Needs attention before sending") : __("Warnings")}</strong>
            <ul>
                ${blockers.concat(warnings).slice(0, 8).map((message) => `<li>${frappe.utils.escape_html(message)}</li>`).join("")}
            </ul>
        </div>
    `;
}

function summaryTabMarkup(campaign, selectedArticles, selectedTargets, readiness) {
    return `
        <article class="oce-panel oce-tab-panel">
            <div class="oce-panel-head">
                <div><span class="oce-kicker">${__("Summary")}</span><h2>${__("Review before saving")}</h2></div>
                <span class="oce-status">${readiness.score}/4</span>
            </div>
            <div class="oce-summary-grid">
                ${summaryCard(__("Campaign"), campaign.campaign_name || __("Untitled"), [campaign.status, campaign.campaign_action_type, campaign.campaign_owner].filter(Boolean).join(" / "))}
                ${summaryCard(__("Audience"), `${selectedTargets.length} ${__("selected targets")}`, [campaign.business_type_filter || __("All business types"), campaign.crm_segment_filter || __("All segments")].join(" / "))}
                ${summaryCard(__("Articles"), `${selectedArticles.length} ${__("selected articles")}`, [campaign.price_list_filter || __("All price lists"), campaign.item_group_filter || __("All groups")].join(" / "))}
                ${summaryCard(__("Readiness"), readiness.missing.length ? __("Needs attention") : __("Ready"), readiness.missing.length ? `${__("Missing")}: ${readiness.missing.join(", ")}` : __("Campaign has the minimum required inputs."))}
            </div>
            <div class="oce-summary-preview">${contentPreviewMarkup(campaign, selectedArticles)}</div>
        </article>
    `;
}

function summaryCard(label, value, helper) {
    return `<section class="oce-summary-card"><span>${frappe.utils.escape_html(label)}</span><strong>${frappe.utils.escape_html(value)}</strong><em>${frappe.utils.escape_html(helper || "-")}</em></section>`;
}

function injectCampaignEditorStyles() {
    const style = document.getElementById("oce-campaign-editor-style") || document.createElement("style");
    style.id = "oce-campaign-editor-style";
    style.textContent = `
        .oce-root { background: #f4f7fb; }
        .oce-shell { min-height: calc(100vh - 56px); max-width: none; margin: 0; padding: 14px 18px 22px; color: #0f172a; }
        .oce-topbar { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 14px; align-items: center; margin-bottom: 12px; padding: 14px 16px; border-radius: 18px; background: #fff; border: 1px solid #dfe8f3; box-shadow: 0 10px 28px rgba(15,23,42,.06); }
        .oce-title-block span { display: inline-flex; color: #0891b2; font-size: 10px; font-weight: 900; letter-spacing: .13em; text-transform: uppercase; }
        .oce-title-block h1 { margin: 2px 0 3px; font-size: 21px; font-weight: 900; letter-spacing: -.025em; color: #0f172a; }
        .oce-title-block p { margin: 0; color: #64748b; font-size: 12px; font-weight: 750; line-height: 1.4; }
        .oce-top-actions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
        .oce-top-actions span { display: inline-flex; align-items: center; gap: 6px; min-height: 30px; padding: 0 10px; border-radius: 999px; border: 1px solid #bae6fd; background: #ecfeff; color: #0e7490; font-size: 11px; font-weight: 900; }
        .oce-top-actions strong { color: #0f172a; }
        .oce-eyebrow, .oce-kicker { display: inline-flex; color: #0891b2; font-size: 10px; font-weight: 900; letter-spacing: .12em; text-transform: uppercase; }
        .oce-tab-shell { display: grid; gap: 12px; }
        .oce-builder-tabs { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; padding: 8px; border: 1px solid #dfe8f3; border-radius: 18px; background: #fff; box-shadow: 0 8px 24px rgba(15,23,42,.04); }
        .oce-builder-tabs button { min-height: 54px; display: flex; justify-content: space-between; align-items: center; gap: 10px; border: 1px solid #e2e8f0; border-radius: 14px; background: #f8fafc; color: #475569; padding: 0 12px; font-weight: 900; cursor: pointer; }
        .oce-builder-tabs button.active { background: #083344; color: #fff; border-color: #083344; box-shadow: 0 12px 24px rgba(8,51,68,.18); }
        .oce-builder-tabs button strong { min-width: 28px; min-height: 24px; display: inline-flex; align-items: center; justify-content: center; border-radius: 999px; background: rgba(255,255,255,.8); color: #0f172a; padding: 0 8px; font-size: 11px; }
        .oce-builder-tabs button.active strong { background: #22d3ee; color: #082f49; }
        .oce-grid { display: grid; grid-template-columns: minmax(0,1fr) 390px; gap: 16px; align-items: start; }
        .oce-main, .oce-side { display: grid; gap: 16px; }
        .oce-side { position: sticky; top: 72px; }
        .oce-panel { background: rgba(255,255,255,.98); border-radius: 20px; border: 1px solid #dfe8f3; box-shadow: 0 14px 38px rgba(15,23,42,.07); overflow: hidden; }
        .oce-tab-panel { min-height: 520px; }
        .oce-panel-head { display: flex; justify-content: space-between; gap: 14px; align-items: center; padding: 15px 16px; border-bottom: 1px solid #e7edf5; }
        .oce-panel-head h2 { margin: 3px 0 0; font-size: 17px; color: #0f172a; font-weight: 900; letter-spacing: -.02em; }
        .oce-status, .oce-status-pill { display: inline-flex; align-items: center; min-height: 26px; padding: 0 9px; border-radius: 999px; background: #dbeafe; color: #1d4ed8; font-size: 11px; font-weight: 900; }
        .oce-setup-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 12px; padding: 14px 16px; }
        .oce-form-group { border: 1px solid #e2e8f0; border-radius: 16px; background: #f8fafc; overflow: hidden; }
        .oce-form-group-head { padding: 12px 12px 0; }
        .oce-form-group-head strong { display: block; color: #0f172a; font-size: 13px; font-weight: 900; }
        .oce-form-group-head span { display: block; margin-top: 3px; color: #64748b; font-size: 11px; font-weight: 800; line-height: 1.35; }
        .oce-form-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 12px; padding: 14px 16px; }
        .oce-form-grid--grouped { grid-template-columns: repeat(2, minmax(0,1fr)); padding: 12px; }
        .oce-description-row { padding: 0 16px 16px; }
        .oce-field { display: grid; gap: 6px; font-weight: 900; color: #475569; font-size: 11px; }
        .oce-field input, .oce-field select, .oce-textarea, .oce-small-textarea, .oce-content-select, .oce-compact-select { min-height: 38px; border: 1px solid #d8e2ee; border-radius: 12px; padding: 0 11px; color: #0f172a; background: #fff; font-weight: 800; outline: none; width: 100%; }
        .oce-small-textarea { min-height: 70px; padding: 11px; line-height: 1.45; resize: vertical; }
        .oce-filter-bar { display: flex; gap: 8px; flex-wrap: wrap; padding: 12px 16px 0; }
        .oce-panel-actions, .oce-article-toolbar, .oce-target-actions-bar, .oce-selection-toolbar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
        .oce-panel-actions { justify-content: flex-end; }
        .oce-article-toolbar, .oce-target-actions-bar, .oce-selection-toolbar { padding: 12px 16px 0; }
        .oce-standard-filters { display: grid; grid-template-columns: minmax(260px, 1.2fr) repeat(3, minmax(150px, .7fr)); gap: 10px; padding: 14px 16px 0; align-items: end; }
        .oce-standard-filters .oce-field { min-width: 0; }
        .oce-wide-filter { grid-column: span 2; }
        .oce-selection-toolbar { justify-content: flex-end; border-top: 1px solid #eef2f7; margin-top: 14px; padding-top: 12px; }
        .oce-selection-toolbar strong { margin-right: auto; color: #0f172a; font-size: 12px; font-weight: 900; }
        .oce-article-toolbar input { min-width: 240px; min-height: 38px; border: 1px solid #d8e2ee; border-radius: 999px; padding: 0 13px; font-weight: 800; background: #fff; outline: none; }
        .oce-inline-check { display: inline-flex; align-items: center; gap: 6px; min-height: 36px; border: 1px solid #d8e2ee; border-radius: 999px; padding: 0 12px; background: #f8fafc; font-weight: 900; color: #0f3b61; }
        .oce-filter-pill { min-height: 36px; border: 1px solid #d8e2ee; background: #f8fafc; color: #0f172a; border-radius: 999px; padding: 0 12px; display: inline-flex; align-items: center; gap: 7px; cursor: pointer; }
        .oce-filter-pill span { color: #64748b; font-size: 11px; font-weight: 900; }
        .oce-link-btn { border: 1px solid #d8e2ee; background: #f8fafc; min-height: 32px; border-radius: 999px; padding: 0 11px; font-weight: 900; color: #0f3b61; cursor: pointer; font-size: 11px; }
        .oce-link-btn[disabled] { opacity: .45; cursor: not-allowed; }
        .oce-table-wrap { overflow-x: auto; padding: 12px 16px 16px; }
        .oce-table { width: 100%; border-collapse: collapse; min-width: 900px; }
        .oce-table th { position: sticky; top: 0; text-align: left; color: #64748b; background: #f8fafc; font-size: 10px; text-transform: uppercase; letter-spacing: .08em; padding: 9px 8px; border-bottom: 1px solid #e2e8f0; }
        .oce-table td { border-bottom: 1px solid #eef2f7; padding: 10px 8px; vertical-align: middle; font-size: 12px; color: #0f172a; }
        .oce-table tr.selected td { background: #ecfeff; }
        .oce-table td strong, .oce-table td span { display: block; }
        .oce-table td span { color: #64748b; font-size: 11px; margin-top: 2px; }
        .oce-payment-chip, .oce-check-pill { display: inline-flex !important; align-items: center; gap: 4px; margin: 0 5px 0 0 !important; border-radius: 999px; padding: 5px 8px; background: #f1f5f9; color: #475569 !important; font-weight: 900; font-size: 10px !important; }
        .oce-target-head { align-items: center; }
        .oce-target-summary { display: flex; align-items: baseline; gap: 5px; color: #64748b; }
        .oce-target-summary strong { color: #0891b2; font-size: 22px; }
        .oce-target-filter-bar { display: grid; grid-template-columns: minmax(220px,1fr) 120px 150px 150px 150px; gap: 8px; padding: 12px 16px 0; }
        .oce-target-standard-filters { grid-template-columns: minmax(260px, 1.2fr) repeat(4, minmax(140px, .7fr)); }
        .oce-target-filter-bar input { min-height: 38px; border: 1px solid #d8e2ee; border-radius: 999px; padding: 0 13px; font-weight: 800; background: #fff; outline: none; }
        .oce-target-table-wrap { max-height: 430px; overflow: auto; }
        .oce-empty-row, .oce-empty-panel { text-align: center; color: #64748b; padding: 26px !important; font-weight: 800; }
        .oce-content-panel { padding-bottom: 14px; }
        .oce-content-tabs { display: grid; grid-template-columns: repeat(3,1fr); gap: 8px; padding: 12px 16px 0; }
        .oce-content-tabs button { min-height: 36px; border: 1px solid #d8e2ee; background: #f8fafc; border-radius: 999px; color: #0f3b61; font-weight: 900; cursor: pointer; }
        .oce-content-tabs button.active { background: #083344; color: #fff; border-color: #083344; }
        .oce-channel-banner { margin: 12px 16px 0; padding: 10px 12px; border-radius: 14px; background: #ecfeff; color: #0e7490; font-size: 11px; font-weight: 900; }
        .oce-content-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(360px, .75fr); gap: 14px; padding: 14px 16px 16px; }
        .oce-content-editor, .oce-content-preview, .oce-content-preview-shell { min-width: 0; border: 1px solid #e2e8f0; border-radius: 16px; background: #f8fafc; overflow: hidden; }
        .oce-content-preview-shell { display: grid; align-content: start; gap: 0; }
        .oce-content-preview { border: 0; border-radius: 0; }
        .oce-preview-target-bar { display: grid; gap: 6px; margin: 0; padding: 12px 14px; border-bottom: 1px solid #e2e8f0; background: #fff; color: #64748b; font-size: 11px; font-weight: 900; }
        .oce-preview-target-bar select { min-height: 36px; border: 1px solid #d8e2ee; border-radius: 11px; background: #f8fafc; color: #0f172a; padding: 0 10px; font-weight: 850; }
        .oce-readiness { margin: 12px 16px 0; padding: 10px 12px; border-radius: 14px; font-size: 11px; font-weight: 850; }
        .oce-readiness ul { margin: 6px 0 0 16px; padding: 0; }
        .oce-readiness-neutral { background: #f8fafc; color: #64748b; border: 1px solid #e2e8f0; }
        .oce-readiness-ok { background: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
        .oce-readiness-warning { background: #fef3c7; color: #92400e; border: 1px solid #fde68a; }
        .oce-readiness-blocked { background: #fff1f2; color: #be123c; border: 1px solid #fecdd3; }
        .oce-label { display: block; padding: 12px 16px 6px; font-weight: 900; color: #475569; font-size: 11px; }
        .oce-content-select { margin: 0 16px; width: calc(100% - 32px); }
        .oce-textarea { margin: 0 16px; width: calc(100% - 32px); min-height: 104px; padding: 11px; line-height: 1.45; resize: vertical; }
        .oce-email-textarea { min-height: 280px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
        .oce-call-textarea { min-height: 88px; }
        .oce-template-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 10px; padding: 12px 16px 16px; }
        .oce-template-grid label { display: grid; gap: 6px; margin: 0; color: #475569; font-size: 11px; font-weight: 900; }
        .oce-template-grid input, .oce-template-grid textarea { min-height: 38px; border: 1px solid #d8e2ee; border-radius: 12px; padding: 9px 11px; color: #0f172a; background: #fff; font-weight: 800; outline: none; width: 100%; }
        .oce-template-grid textarea { min-height: 74px; resize: vertical; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; }
        .oce-template-wide { grid-column: 1 / -1; }
        .oce-editor-toolbar { display: flex; gap: 6px; flex-wrap: wrap; padding: 12px 16px 0; }
        .oce-editor-toolbar button { min-height: 30px; border: 1px solid #d8e2ee; border-radius: 999px; background: #fff; color: #0f3b61; padding: 0 10px; font-size: 11px; font-weight: 900; cursor: pointer; }
        .oce-preview-head { display: grid; gap: 4px; padding: 12px 14px; border-bottom: 1px solid #e2e8f0; background: #fff; }
        .oce-preview-head span { color: #64748b; font-size: 10px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }
        .oce-preview-head strong { color: #0f172a; font-size: 13px; font-weight: 900; }
        .oce-html-preview { width: 100%; height: 420px; border: 0; background: #fff; }
        .oce-text-preview { min-height: 360px; margin: 0; padding: 16px; white-space: pre-wrap; color: #0f172a; background: #fff; font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
        .oce-phone-preview { margin: 16px; border-radius: 24px; border: 8px solid #0f172a; background: #f8fafc; padding: 15px; min-height: 250px; }
        .oce-phone-top { width: 66px; height: 6px; border-radius: 99px; background: #334155; margin: 0 auto 18px; }
        .oce-message-bubble { background: #dcfce7; color: #14532d; padding: 12px; border-radius: 16px 16px 4px 16px; font-weight: 800; line-height: 1.42; font-size: 12px; }
        .oce-whatsapp-vars { margin: 12px 0 0; border: 1px solid #bbf7d0; border-radius: 12px; background: #f0fdf4; color: #14532d; padding: 10px; font-size: 11px; white-space: pre-wrap; }
        .oce-preview-items { display: grid; gap: 7px; margin-top: 12px; }
        .oce-preview-items span { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 9px; color: #334155; font-size: 11px; font-weight: 900; }
        .oce-summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; padding: 14px 16px; }
        .oce-summary-card { min-height: 92px; display: grid; gap: 5px; align-content: start; border: 1px solid #e2e8f0; border-radius: 16px; background: #f8fafc; padding: 13px; }
        .oce-summary-card span { color: #64748b; font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: .09em; }
        .oce-summary-card strong { color: #0f172a; font-size: 16px; font-weight: 900; }
        .oce-summary-card em { color: #64748b; font-size: 11px; font-style: normal; font-weight: 750; }
        .oce-summary-preview { margin: 0 16px 16px; border: 1px solid #e2e8f0; border-radius: 16px; overflow: hidden; background: #f8fafc; }
        .oce-sticky-actions { position: sticky; bottom: 12px; z-index: 5; display: grid; grid-template-columns: 1fr 1fr auto; gap: 9px; margin-top: 12px; padding: 10px; border: 1px solid #dfe8f3; border-radius: 18px; background: rgba(255,255,255,.94); box-shadow: 0 14px 34px rgba(15,23,42,.12); backdrop-filter: blur(8px); }
        .oce-sticky-actions .oce-btn-primary { grid-column: 1 / -1; }
        .oce-btn { border: 0; min-height: 42px; border-radius: 999px; padding: 0 14px; font-weight: 900; cursor: pointer; }
        .oce-btn-primary { background: #083344; color: #fff; box-shadow: 0 12px 26px rgba(8,51,68,.2); }
        .oce-btn-soft { background: #ecfeff; color: #0e7490; }
        .oce-btn-ghost { background: #fff; color: #0f172a; border: 1px solid #d8e2ee; }
        .oce-pagination-bar { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 0 16px 16px; }
        .oce-pagination-meta { color: #64748b; font-size: 11px; font-weight: 900; }
        .oce-pagination-actions { display: flex; gap: 8px; }
        .oce-field input:focus-visible, .oce-field select:focus-visible, .oce-textarea:focus-visible, .oce-small-textarea:focus-visible, .oce-content-select:focus-visible, .oce-compact-select:focus-visible, .oce-article-toolbar input:focus-visible, .oce-target-filter-bar input:focus-visible, .oce-link-btn:focus-visible, .oce-btn:focus-visible, .oce-content-tabs button:focus-visible, .oce-builder-tabs button:focus-visible, .oce-editor-toolbar button:focus-visible { outline: 3px solid rgba(8,145,178,.22); outline-offset: 2px; }
        @media (max-width: 1240px) { .oce-grid, .oce-topbar, .oce-content-grid, .oce-standard-filters, .oce-target-standard-filters { grid-template-columns: repeat(2, minmax(0, 1fr)); } .oce-top-actions { justify-content: flex-start; } .oce-side { position: static; } .oce-form-grid, .oce-setup-grid { grid-template-columns: repeat(2, minmax(0,1fr)); } .oce-summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .oce-wide-filter { grid-column: 1 / -1; } }
        @media (max-width: 780px) { .oce-shell { padding: 12px; } .oce-builder-tabs, .oce-form-grid, .oce-form-grid--grouped, .oce-setup-grid, .oce-target-filter-bar, .oce-standard-filters, .oce-target-standard-filters, .oce-sticky-actions, .oce-summary-grid { grid-template-columns: 1fr; } .oce-wide-filter { grid-column: auto; } .oce-panel-head, .oce-pagination-bar { flex-direction: column; align-items: stretch; } .oce-panel-actions, .oce-selection-toolbar { justify-content: flex-start; } }
    `;
    document.head.appendChild(style);
}
