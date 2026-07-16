frappe.pages["dimensioning-set-manager"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Dimensioning Sets"),
        single_column: true,
    });

    wrapper.page = page;
    page.main.addClass("odm-root");
    injectDimensioningManagerStyles();
    renderDimensioningManager(page);
    loadDimensioningManagerData(page);
    applyDimensioningManagerHeader(page);
};

frappe.pages["dimensioning-set-manager"].on_page_show = function (wrapper) {
    if (!wrapper.page) return;
    applyDimensioningManagerHeader(wrapper.page);
    loadDimensioningManagerData(wrapper.page);
};

const ODM_STATE = {
    sets: [],
    loading: false,
    error: "",
    search: "",
    status: "All",
};

let ODM_SEARCH_TIMER = null;

function applyDimensioningManagerHeader(page) {
    page.set_title(__("Dimensioning Sets"));
    page.set_primary_action(__("New Dimensioning Set"), () => openDimensioningBuilderForCreate());
    setTimeout(() => {
        if (!frappe.breadcrumbs) return;
        frappe.breadcrumbs.clear();
        frappe.breadcrumbs.append_breadcrumb_element("/desk/home-page", __("Sales"), "title-text");
        frappe.breadcrumbs.append_breadcrumb_element("", __("Dimensioning Sets"), "title-text");
        frappe.breadcrumbs.toggle(true);
    }, 0);
}

async function loadDimensioningManagerData(page) {
    ODM_STATE.loading = true;
    ODM_STATE.error = "";
    renderDimensioningManager(page);
    try {
        const res = await frappe.call({
            method: "orderlift.orderlift_sales.doctype.dimensioning_set.dimensioning_set.get_dimensioning_manager_data",
        });
        ODM_STATE.sets = (res.message || {}).sets || [];
    } catch (error) {
        console.error("Dimensioning Sets failed", error);
        ODM_STATE.error = __("Unable to load Dimensioning Sets. Refresh and try again.");
        ODM_STATE.sets = [];
    } finally {
        ODM_STATE.loading = false;
        renderDimensioningManager(page);
    }
}

function renderDimensioningManager(page) {
    const sets = currentDimensioningSets();
    const activeCount = ODM_STATE.sets.filter((row) => row.is_active).length;
    const questionCount = ODM_STATE.sets.reduce((total, row) => total + Number(row.question_count || 0), 0);
    const articleCount = ODM_STATE.sets.reduce((total, row) => total + Number(row.article_count || 0), 0);
    page.main.html(`
        <div class="odm-shell">
            <section class="odm-command-bar">
                <div class="odm-command-main">
                    <span>${__("Dimensioning")}</span>
                    <h1>${__("Dimensioning Sets")}</h1>
                    <p>${__("Manage guided quote forms. Create a set, then edit its questions, rules, and generated articles in the builder.")}</p>
                </div>
                <div class="odm-command-stats">
                    ${metricCard(__("Sets"), ODM_STATE.sets.length)}
                    ${metricCard(__("Active"), activeCount)}
                    ${metricCard(__("Questions"), questionCount)}
                    ${metricCard(__("Articles"), articleCount)}
                </div>
                <div class="odm-actions">
                    <button type="button" class="odm-btn odm-btn-ghost" data-refresh="1">${__("Refresh")}</button>
                    <button type="button" class="odm-btn odm-btn-primary" data-new-set="1">${__("New Set")}</button>
                </div>
            </section>
            ${ODM_STATE.error ? `<div class="odm-error">${frappe.utils.escape_html(ODM_STATE.error)}</div>` : ""}
            <section class="odm-panel">
                <div class="odm-panel-head">
                    <div><span>${__("Sets")}</span><h2>${sets.length} ${__("visible")}</h2></div>
                    <button type="button" class="odm-link-btn" data-clear-filters="1">${__("Reset filters")}</button>
                </div>
                <div class="odm-filters">
                    <label class="odm-wide-filter"><span>${__("Search")}</span><input id="odm-search" type="search" value="${frappe.utils.escape_html(ODM_STATE.search)}" placeholder="${frappe.utils.escape_html(__("Set name or description"))}" /></label>
                    <label><span>${__("Status")}</span><select id="odm-status"><option value="All" ${ODM_STATE.status === "All" ? "selected" : ""}>${__("All")}</option><option value="Active" ${ODM_STATE.status === "Active" ? "selected" : ""}>${__("Active")}</option><option value="Inactive" ${ODM_STATE.status === "Inactive" ? "selected" : ""}>${__("Inactive")}</option></select></label>
                </div>
                <div class="odm-set-list">
                    ${ODM_STATE.loading ? skeletonCards(5) : sets.length ? sets.map(setCard).join("") : emptyPanel(__("No Dimensioning Sets match the current filters."))}
                </div>
            </section>
        </div>
    `);
    bindDimensioningManagerEvents(page);
}

function bindDimensioningManagerEvents(page) {
    page.main.find("[data-refresh]").on("click", () => loadDimensioningManagerData(page));
    page.main.find("[data-new-set]").on("click", () => openDimensioningBuilderForCreate());
    page.main.find("[data-edit-set]").on("click", function () {
        openDimensioningBuilderForSet($(this).data("edit-set"));
    });
    page.main.find("[data-duplicate-set]").on("click", function () {
        duplicateDimensioningSet(page, $(this).data("duplicate-set"));
    });
    page.main.find("[data-delete-set]").on("click", function () {
        confirmDeleteDimensioningSet(page, $(this).data("delete-set"));
    });
    page.main.find("[data-clear-filters]").on("click", () => {
        ODM_STATE.search = "";
        ODM_STATE.status = "All";
        renderDimensioningManager(page);
    });
    page.main.find("#odm-search").on("input", function () {
        ODM_STATE.search = String($(this).val() || "").trim().toLowerCase();
        clearTimeout(ODM_SEARCH_TIMER);
        ODM_SEARCH_TIMER = setTimeout(() => renderDimensioningManager(page), 160);
    });
    page.main.find("#odm-status").on("change", function () {
        ODM_STATE.status = $(this).val();
        renderDimensioningManager(page);
    });
}

function currentDimensioningSets() {
    return ODM_STATE.sets.filter((row) => {
        const searchable = `${row.set_name || ""} ${row.description || ""} ${row.name || ""}`.toLowerCase();
        const statusMatches = ODM_STATE.status === "All" || (ODM_STATE.status === "Active" ? row.is_active : !row.is_active);
        return statusMatches && (!ODM_STATE.search || searchable.includes(ODM_STATE.search));
    });
}

function setCard(row) {
    return `
        <article class="odm-set-card">
            <div class="odm-set-main">
                <div>
                    <span class="odm-status ${row.is_active ? "is-active" : "is-inactive"}">${row.is_active ? __("Active") : __("Inactive")}</span>
                    <h3>${frappe.utils.escape_html(row.set_name || row.name)}</h3>
                    <p>${frappe.utils.escape_html(row.description || __("No description yet"))}</p>
                </div>
                <div class="odm-set-actions">
                    <button type="button" class="odm-btn odm-btn-ghost" data-duplicate-set="${frappe.utils.escape_html(row.name)}">${__("Duplicate")}</button>
                    <button type="button" class="odm-btn odm-btn-ghost odm-btn-danger" data-delete-set="${frappe.utils.escape_html(row.name)}">${__("Delete")}</button>
                    <button type="button" class="odm-btn odm-btn-primary" data-edit-set="${frappe.utils.escape_html(row.name)}">${__("Open Builder")}</button>
                </div>
            </div>
            <div class="odm-set-meta">
                <span><strong>${frappe.utils.escape_html(String(row.question_count || 0))}</strong>${__("questions")}</span>
                <span><strong>${frappe.utils.escape_html(String(row.rule_group_count || 0))}</strong>${__("rules")}</span>
                <span><strong>${frappe.utils.escape_html(String(row.article_count || 0))}</strong>${__("articles")}</span>
                <span><strong>${frappe.utils.escape_html(shortDate(row.modified))}</strong>${__("updated")}</span>
            </div>
        </article>
    `;
}

function openDimensioningBuilderForCreate() {
    frappe.set_route("dimensioning-set-builder", "new");
}

function openDimensioningBuilderForSet(setName) {
    const row = ODM_STATE.sets.find((entry) => entry.name === setName) || {};
    const displayName = String(row.set_name || setName).trim() || setName;
    frappe.set_route("dimensioning-set-builder", displayName, setName);
}

async function duplicateDimensioningSet(page, setName) {
    if (!setName) return;
    try {
        const payloadRes = await frappe.call({
            method: "orderlift.orderlift_sales.doctype.dimensioning_set.dimensioning_set.get_dimensioning_builder_payload",
            args: { set_name: setName },
            freeze: true,
        });
        const payload = (payloadRes.message || {}).set;
        if (!payload) return;
        payload.name = "";
        payload.set_name = __("Copy of {0}", [payload.set_name || setName]);
        const saveRes = await frappe.call({
            method: "orderlift.orderlift_sales.doctype.dimensioning_set.dimensioning_set.save_dimensioning_builder_payload",
            args: { payload: JSON.stringify(payload) },
            freeze: true,
        });
        const duplicated = (saveRes.message || {}).set || {};
        frappe.show_alert({ message: __("Dimensioning Set duplicated"), indicator: "green" });
        await loadDimensioningManagerData(page);
        if (duplicated.name) openDimensioningBuilderForSet(duplicated.name);
    } catch (error) {
        frappe.msgprint({
            title: __("Duplicate failed"),
            message: extractDimensioningManagerError(error) || __("Unable to duplicate this Dimensioning Set."),
            indicator: "red",
        });
    }
}

function confirmDeleteDimensioningSet(page, setName) {
    if (!setName) return;
    frappe.confirm(
        __("Delete Dimensioning Set {0}? This cannot be undone.", [setName]),
        async () => {
            try {
                await frappe.call({
                    method: "orderlift.orderlift_sales.doctype.dimensioning_set.dimensioning_set.delete_dimensioning_set",
                    args: { set_name: setName },
                    freeze: true,
                });
                frappe.show_alert({ message: __("Dimensioning Set deleted"), indicator: "green" });
                await loadDimensioningManagerData(page);
            } catch (error) {
                frappe.msgprint({
                    title: __("Delete failed"),
                    message: extractDimensioningManagerError(error) || __("Unable to delete this Dimensioning Set."),
                    indicator: "red",
                });
            }
        }
    );
}

function extractDimensioningManagerError(error) {
    const raw = error?._server_messages || error?.message || error?.responseJSON?._server_messages || error?.responseJSON?.message || "";
    if (!raw) return "";
    try {
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed.map((entry) => extractDimensioningManagerError({ message: entry })).filter(Boolean).join(" ") : parsed.message || String(parsed);
    } catch (e) {
        return $("<div>").html(String(raw)).text().trim();
    }
}

function metricCard(label, value) {
    return `<span class="odm-metric"><em>${frappe.utils.escape_html(label)}</em><strong>${frappe.utils.escape_html(String(value == null ? 0 : value))}</strong></span>`;
}

function skeletonCards(count) {
    return Array.from({ length: count }, () => `<div class="odm-skeleton"></div>`).join("");
}

function emptyPanel(message) {
    return `<div class="odm-empty">${frappe.utils.escape_html(message)}</div>`;
}

function shortDate(value) {
    return value ? String(value).slice(0, 10) : "-";
}

function injectDimensioningManagerStyles() {
    if (document.getElementById("odm-dimensioning-manager-style")) return;
    const style = document.createElement("style");
    style.id = "odm-dimensioning-manager-style";
    style.textContent = `
        .odm-root { background: #f4f7fb; }
        .odm-shell { min-height: calc(100vh - 56px); padding: 14px 18px 22px; color: #0f172a; }
        .odm-command-bar { display: grid; grid-template-columns: minmax(260px,1fr) minmax(360px,.9fr) auto; gap: 14px; align-items: center; padding: 14px 16px; border: 1px solid #dfe8f3; border-radius: 20px; background: #fff; box-shadow: 0 12px 32px rgba(15,23,42,.07); }
        .odm-command-main span, .odm-panel-head span { display: inline-flex; color: #0891b2; font-size: 10px; font-weight: 900; letter-spacing: .13em; text-transform: uppercase; }
        .odm-command-main h1 { margin: 3px 0 2px; color: #0f172a; font-size: 22px; line-height: 1.12; letter-spacing: -.035em; font-weight: 900; }
        .odm-command-main p { margin: 0; color: #64748b; font-size: 12px; line-height: 1.4; font-weight: 780; }
        .odm-command-stats { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 8px; }
        .odm-metric { min-height: 54px; display: grid; align-content: center; gap: 3px; border: 1px solid #e2e8f0; border-radius: 14px; background: #f8fafc; padding: 8px 10px; }
        .odm-metric em { color: #64748b; font-size: 9px; font-style: normal; font-weight: 900; text-transform: uppercase; letter-spacing: .08em; }
        .odm-metric strong { color: #0f172a; font-size: 18px; line-height: 1; font-weight: 900; }
        .odm-actions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
        .odm-btn, .odm-link-btn { min-height: 38px; border: 0; border-radius: 999px; padding: 0 14px; font-weight: 900; cursor: pointer; }
        .odm-btn-primary { background: #083344; color: #fff; box-shadow: 0 10px 22px rgba(8,51,68,.2); }
        .odm-btn-ghost, .odm-link-btn { background: #f8fafc; color: #0f3b61; border: 1px solid #d8e2ee; }
        .odm-btn-danger { color: #be123c; border-color: #fecdd3; background: #fff1f2; }
        .odm-btn-danger:hover { background: #ffe4e6; }
        .odm-error { margin-top: 12px; border: 1px solid #fecdd3; background: #fff1f2; color: #9f1239; border-radius: 14px; padding: 11px 13px; font-weight: 850; }
        .odm-panel { margin-top: 14px; border: 1px solid #dfe8f3; border-radius: 22px; background: rgba(255,255,255,.98); box-shadow: 0 14px 38px rgba(15,23,42,.07); overflow: hidden; }
        .odm-panel-head { display: flex; justify-content: space-between; gap: 12px; align-items: center; padding: 14px; border-bottom: 1px solid #e7edf5; }
        .odm-panel-head h2 { margin: 3px 0 0; color: #0f172a; font-size: 16px; font-weight: 900; letter-spacing: -.025em; }
        .odm-filters { display: grid; grid-template-columns: minmax(260px,1fr) 180px; gap: 10px; padding: 12px 14px; border-bottom: 1px solid #e7edf5; align-items: end; }
        .odm-filters label { display: grid; gap: 5px; margin: 0; }
        .odm-filters label span { color: #64748b; font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: .08em; }
        .odm-filters input, .odm-filters select { min-height: 40px; width: 100%; border: 1px solid #d8e2ee; border-radius: 13px; background: #f8fafc; color: #102033; padding: 0 11px; font-size: 12px; font-weight: 800; outline: none; }
        .odm-set-list { display: grid; gap: 10px; padding: 12px; }
        .odm-set-card { display: grid; gap: 12px; border: 1px solid #e0e8f2; border-radius: 18px; background: #fff; padding: 13px; }
        .odm-set-main { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 14px; align-items: start; }
        .odm-set-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
        .odm-status { display: inline-flex; margin-bottom: 6px; border-radius: 999px; padding: 3px 8px; font-size: 10px; font-weight: 900; }
        .odm-status.is-active { background: #dcfce7; color: #166534; }
        .odm-status.is-inactive { background: #fef3c7; color: #92400e; }
        .odm-set-card h3 { margin: 0; color: #0f172a; font-size: 16px; font-weight: 900; line-height: 1.2; }
        .odm-set-card p { margin: 4px 0 0; color: #64748b; font-size: 12px; font-weight: 750; line-height: 1.4; }
        .odm-set-meta { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 8px; }
        .odm-set-meta span { display: grid; gap: 2px; border-radius: 12px; background: #f8fafc; padding: 8px; color: #64748b; font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: .06em; }
        .odm-set-meta strong { color: #0f172a; font-size: 14px; letter-spacing: 0; text-transform: none; }
        .odm-empty { min-height: 170px; display: grid; place-items: center; text-align: center; padding: 24px; color: #64748b; font-weight: 850; }
        .odm-skeleton { min-height: 112px; border-radius: 17px; background: linear-gradient(90deg,#eef2f7 0%,#f8fafc 45%,#eef2f7 90%); background-size: 220% 100%; animation: odm-shimmer 1.1s linear infinite; }
        @keyframes odm-shimmer { to { background-position: -220% 0; } }
        @media (max-width: 980px) { .odm-command-bar, .odm-filters { grid-template-columns: 1fr; } .odm-command-stats, .odm-set-meta { grid-template-columns: repeat(2,minmax(0,1fr)); } .odm-actions { justify-content: flex-start; } .odm-set-main { grid-template-columns: 1fr; } }
    `;
    document.head.appendChild(style);
}
