(function () {
    const STATE = {
        columns: [],
        kpis: {},
        filters: { owners: [], sources: [], companies: [] },
        search: "",
        owner: "All",
        source: "All",
        company: "All",
        businessType: "All",
        dragged: null,
        collapsedColumns: {},
        focusedColumn: "",
    };

    frappe.pages["opportunity-pipeline"].on_page_load = function (wrapper) {
        const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Opportunity Pipeline"), single_column: true });
        wrapper.page = page;
        page.main.addClass("olp-root");
        injectPipelineStyles();
        renderPage(page);
        loadData(page);
        applyHeader(page);
    };

    frappe.pages["opportunity-pipeline"].on_page_show = function (wrapper) {
        if (!wrapper.page) return;
        applyHeader(wrapper.page);
        loadData(wrapper.page);
    };

    function applyHeader(page) {
        page.set_title(__("Opportunity Pipeline"));
        setTimeout(() => {
            if (!frappe.breadcrumbs) return;
            frappe.breadcrumbs.clear();
            frappe.breadcrumbs.append_breadcrumb_element("/app/crm-dashboard", __("CRM"), "title-text");
            frappe.breadcrumbs.append_breadcrumb_element("", __("Opportunity Pipeline"), "title-text");
            frappe.breadcrumbs.toggle(true);
        }, 0);
    }

    async function loadData(page) {
        try {
            const res = await frappe.call({
                method: "orderlift.orderlift_crm.api.pipeline.get_opportunity_pipeline_data",
                args: {
                    search: STATE.search,
                    owner: STATE.owner,
                    source: STATE.source,
                    company: STATE.company,
                    business_type: STATE.businessType,
                },
            });
            const data = res.message || {};
            STATE.columns = data.columns || [];
            STATE.kpis = data.kpis || {};
            STATE.filters = data.filters || { owners: [], sources: [], companies: [], business_types: [] };
            renderPage(page);
        } catch (error) {
            console.error("Opportunity Pipeline failed", error);
            STATE.columns = [];
            STATE.kpis = {};
            renderPage(page, true);
        }
    }

    function renderPage(page, hasError = false) {
        const totalCards = STATE.columns.reduce((sum, column) => sum + (column.cards || []).length, 0);
        page.main.html(`
            <div class="olp-shell">
                <section class="olp-hero">
                    <div class="olp-hero-copy">
                        <div class="olp-eyebrow">${__("Orderlift CRM")}</div>
                        <h1>${__("Opportunity Pipeline")}</h1>
                        <p>${__("Move cards by Opportunity Status, while every card keeps the related ERP document statuses visible for quick judgment.")}</p>
                    </div>
                    <div class="olp-hero-kpis">
                        ${kpi(STATE.kpis.primary_label, STATE.kpis.primary_value)}
                        ${kpi(STATE.kpis.secondary_label, STATE.kpis.secondary_value)}
                        ${kpi(STATE.kpis.tertiary_label, STATE.kpis.tertiary_value)}
                        ${kpi(STATE.kpis.quaternary_label, STATE.kpis.quaternary_value)}
                    </div>
                </section>
                <section class="olp-toolbar">
                    <div class="olp-filter-row olp-filter-row--wide">
                        ${filterInput("olp-search", __("Search"), STATE.search, __("Opportunity, customer, source"), "search")}
                        ${filterCombo("olp-owner", __("Owner"), STATE.owner === "All" ? "" : STATE.owner, __("All owners"), STATE.filters.owners || [])}
                        ${filterCombo("olp-source", __("Source"), STATE.source === "All" ? "" : STATE.source, __("All sources"), STATE.filters.sources || [])}
                        ${filterSelect("olp-business-type", __("Type"), ["All", "Distribution", "Installation", ...(STATE.filters.business_types || []).filter((value) => !["Distribution", "Installation"].includes(value))], STATE.businessType, __("All business types"))}
                        ${filterCombo("olp-company", __("Company"), STATE.company === "All" ? "" : STATE.company, __("All companies"), STATE.filters.companies || [])}
                        <button data-refresh="1">${__("Refresh")}</button>
                    </div>
                </section>
                <section class="olp-stage-strip">
                    ${STATE.columns.map(stageSummaryMarkup).join("")}
                </section>
                <section class="olp-board">
                    ${STATE.columns.length ? STATE.columns.map(columnMarkup).join("") : `<div class="olp-empty-board">${hasError ? __("Unable to load the Opportunity pipeline right now.") : __("No statuses or opportunities are available yet.")}</div>`}
                </section>
                ${totalCards ? "" : `<div class="olp-empty-note">${__("There are currently no opportunities matching the selected filters.")}</div>`}
            </div>
        `);
        bindEvents(page);
    }

    function bindEvents(page) {
        page.main.find("[data-refresh]").on("click", () => loadData(page));
        page.main.find("#olp-search").on("input", function () {
            STATE.search = String($(this).val() || "").trim();
            loadData(page);
        });
        bindCombo(page, "#olp-owner", "owner");
        bindCombo(page, "#olp-source", "source");
        bindCombo(page, "#olp-company", "company");
        page.main.find("#olp-business-type").on("change", function () {
            STATE.businessType = $(this).val();
            loadData(page);
        });
        page.main.find("[data-stage-jump]").on("click", function () {
            const columnName = String($(this).attr("data-stage-jump") || "");
            if (!columnName) return;
            STATE.focusedColumn = columnName;
            page.main.find(".olp-stage-summary").removeClass("is-focused");
            page.main.find(`.olp-stage-summary[data-stage-jump="${cssEscape(columnName)}"]`).addClass("is-focused");
            const target = page.main.find(`.olp-column[data-column="${cssEscape(columnName)}"]`).get(0);
            if (target) {
                target.scrollIntoView({ behavior: "smooth", inline: "start", block: "nearest" });
                page.main.find(".olp-column").removeClass("is-focused");
                $(target).addClass("is-focused");
                setTimeout(() => $(target).removeClass("is-focused"), 1200);
            }
        });
        page.main.find("[data-toggle-column]").on("click", function (event) {
            event.preventDefault();
            event.stopPropagation();
            const columnName = String($(this).attr("data-toggle-column") || "");
            if (!columnName) return;
            STATE.collapsedColumns[columnName] = !STATE.collapsedColumns[columnName];
            renderPage(page);
        });
        page.main.find(".olp-card").on("click", function (event) {
            if ($(event.target).closest(".olp-docs-block").length) return;
            frappe.set_route("Form", "Opportunity", $(this).data("name"));
        });
        page.main.find(".olp-docs-section a").on("click", function (event) {
            event.preventDefault();
            event.stopPropagation();
            frappe.set_route("Form", $(this).data("doctype"), $(this).data("name"));
        });
        page.main.find("[data-doc-group-toggle]").on("click", function (event) {
            event.preventDefault();
            event.stopPropagation();
            const group = $(this).closest(".olp-doc-group");
            group.siblings(".olp-doc-group").removeClass("is-open");
            group.toggleClass("is-open");
        });
        page.main.find(".olp-card").on("dragstart", function (event) {
            STATE.dragged = $(this).data("name");
            event.originalEvent.dataTransfer.effectAllowed = "move";
            event.originalEvent.dataTransfer.setData("text/plain", STATE.dragged);
            $(this).addClass("dragging");
        });
        page.main.find(".olp-card").on("dragend", function () {
            $(this).removeClass("dragging");
            page.main.find(".olp-column").removeClass("drop-ready");
        });
        page.main.find(".olp-column[data-column!='__unassigned__']").on("dragover", function (event) {
            event.preventDefault();
            $(this).addClass("drop-ready");
        });
        page.main.find(".olp-column[data-column!='__unassigned__']").on("dragleave", function () {
            $(this).removeClass("drop-ready");
        });
        page.main.find(".olp-column[data-column!='__unassigned__']").on("drop", async function (event) {
            event.preventDefault();
            const stage = $(this).data("column");
            const name = STATE.dragged;
            $(this).removeClass("drop-ready");
            if (!name || !stage) return;
            try {
                await frappe.call({
                    method: "orderlift.orderlift_crm.api.pipeline.update_opportunity_stage",
                    args: { opportunity: name, stage },
                    freeze: true,
                });
                frappe.show_alert({ message: __("Opportunity {0} moved to {1}", [name, stage]), indicator: "green" });
                loadData(page);
            } finally {
                STATE.dragged = null;
            }
        });
        page.main.off("mousedown.olp-combo").on("mousedown.olp-combo", function (event) {
            if (!$(event.target).closest(".olp-combo").length) {
                page.main.find(".olp-combo").removeClass("is-open");
            }
            if (!$(event.target).closest(".olp-doc-group").length) {
                page.main.find(".olp-doc-group").removeClass("is-open");
            }
        });
    }

    function bindCombo(page, selector, stateKey) {
        const input = page.main.find(selector);
        const combo = input.closest(".olp-combo");
        const menu = combo.find(".olp-combo-menu");
        const applyValue = (value) => {
            input.val(value || "");
            STATE[stateKey] = cleanFilterValue(value);
            combo.removeClass("is-open");
            loadData(page);
        };

        input.on("focus input", function () {
            STATE[stateKey] = cleanFilterValue($(this).val());
            combo.addClass("is-open");
            filterComboMenu(combo, $(this).val());
        });
        input.on("change", function () {
            applyValue($(this).val());
        });
        input.on("keydown", function (event) {
            if (event.key === "Enter") {
                event.preventDefault();
                applyValue($(this).val());
            } else if (event.key === "Escape") {
                combo.removeClass("is-open");
            }
        });
        combo.find("[data-combo-toggle]").on("mousedown", function (event) {
            event.preventDefault();
            event.stopPropagation();
            combo.toggleClass("is-open");
            filterComboMenu(combo, input.val());
        });
        menu.find("[data-combo-option]").on("mousedown", function (event) {
            event.preventDefault();
            event.stopPropagation();
            applyValue($(this).attr("data-combo-option") || "");
        });
    }

    function filterComboMenu(combo, query) {
        const needle = String(query || "").trim().toLowerCase();
        let visible = 0;
        combo.find("[data-combo-option]").each(function () {
            const value = String($(this).attr("data-combo-option") || "").toLowerCase();
            const label = $(this).text().toLowerCase();
            const isVisible = !needle || !value || value.includes(needle) || label.includes(needle);
            $(this).toggle(isVisible);
            if (isVisible) visible += 1;
        });
        combo.find(".olp-combo-empty").toggle(visible === 0);
    }

    function columnMarkup(column) {
        const isCollapsed = Boolean(STATE.collapsedColumns[column.name]);
        const escapedName = frappe.utils.escape_html(column.name);
        const escapedLabel = frappe.utils.escape_html(column.label);
        return `
            <article class="olp-column stage-${color(column.color)} ${isCollapsed ? "is-collapsed" : ""}" data-column="${escapedName}">
                <div class="olp-column-head" title="${escapedLabel}">
                    <h2>${escapedLabel}</h2>
                    <span>${(column.cards || []).length}</span>
                    <button type="button" class="olp-column-toggle" data-toggle-column="${escapedName}" aria-label="${frappe.utils.escape_html(isCollapsed ? __("Expand column") : __("Collapse column"))}">${isCollapsed ? "+" : "−"}</button>
                </div>
                <div class="olp-card-stack">
                    ${(column.cards || []).length ? column.cards.map(cardMarkup).join("") : `<div class="olp-empty-column">${column.name === "__unassigned__" ? __("Statuses not set yet") : __("Drop cards here")}</div>`}
                </div>
            </article>
        `;
    }

    function stageSummaryMarkup(column) {
        const count = (column.cards || []).length;
        return `
            <button type="button" class="olp-stage-summary stage-${color(column.color)} ${count ? "has-cards" : "is-empty"} ${STATE.focusedColumn === column.name ? "is-focused" : ""}" data-stage-jump="${frappe.utils.escape_html(column.name)}" title="${frappe.utils.escape_html(__("Jump to {0}", [column.label]))}">
                <strong>${frappe.utils.escape_html(column.label)}</strong>
                <span>${count}</span>
            </button>
        `;
    }

    function cssEscape(value) {
        if (window.CSS && CSS.escape) return CSS.escape(value);
        return String(value).replace(/"/g, "\\\"");
    }

    function cardMarkup(card) {
        const erpStatus = metricValue(card, "ERP Status") || card.legacy_status || "-";
        const probability = metricValue(card, "Probability") || "0%";
        const owner = metricValue(card, "Owner") || card.owner || "-";
        const amount = Number(card.amount || 0);
        const probabilityPct = probabilityNumber(probability);
        return `
            <div class="olp-card" draggable="true" data-name="${frappe.utils.escape_html(card.name)}">
                <header class="olp-record-hero">
                    <div class="olp-record-topbar">
                        <span class="olp-id-pill">${frappe.utils.escape_html(card.name)}</span>
                        <div class="olp-stage-block">
                            <div class="olp-stage-info">
                                <span>${__("Stage")}</span>
                                <strong class="status-${docTone(erpStatus)}">${frappe.utils.escape_html(erpStatus)}</strong>
                            </div>
                            <div class="olp-dial ${probabilityTone(probability)}" style="--pct:${probabilityPct};" title="${frappe.utils.escape_html(__("Probability"))}: ${frappe.utils.escape_html(probability)}">
                                <span>${frappe.utils.escape_html(probability)}</span>
                            </div>
                        </div>
                    </div>
                    <div class="olp-signal status-${docTone(erpStatus)}"><i></i>${frappe.utils.escape_html(statusSignal(erpStatus))}</div>
                    <h3>${frappe.utils.escape_html(card.title || card.name)}</h3>
                    <p>${frappe.utils.escape_html(card.subtitle || "-")}</p>
                    <div class="olp-meta-strip">
                        <div class="olp-owner-card" title="${frappe.utils.escape_html(owner)}">
                            <span class="olp-owner-avatar">${frappe.utils.escape_html(ownerInitials(owner))}</span>
                            <span class="olp-owner-copy"><strong>${frappe.utils.escape_html(owner)}</strong><small>${__("Account owner")}</small></span>
                        </div>
                        <div class="olp-value-block ${amount ? "" : "is-empty"}"><span>${__("Value")}</span><strong>${amount ? `${amount.toLocaleString()} DH` : __("Not set")}</strong></div>
                    </div>
                </header>
                ${extraMetricsMarkup(card)}
                ${tagsMarkup(card.tags || [])}
                ${docsMarkup(card.docs || [])}
            </div>
        `;
    }

    function tagsMarkup(tags) {
        const cleanTags = (tags || []).filter(Boolean);
        if (!cleanTags.length) return "";
        return `
            <div class="olp-tags-row">
                <span class="olp-tag-label">${__("Tags")}</span>
                ${cleanTags.map((tag) => `<span class="olp-tag"><i></i>${frappe.utils.escape_html(String(tag))}</span>`).join("")}
            </div>
        `;
    }

    function metricValue(card, label) {
        const metric = (card.metrics || []).find((entry) => String(entry.label || "") === label);
        return metric ? String(metric.value || "") : "";
    }

    function extraMetricsMarkup(card) {
        const reserved = new Set(["ERP Status", "Probability", "Owner"]);
        const metrics = (card.metrics || []).filter((metric) => !reserved.has(String(metric.label || "")));
        if (!metrics.length) return "";
        return `<div class="olp-card-meta">${metrics.map((metric) => `<span>${frappe.utils.escape_html(metric.label)}: ${frappe.utils.escape_html(String(metric.value || "-"))}</span>`).join("")}</div>`;
    }

    function probabilityTone(value) {
        const percentage = probabilityNumber(value);
        if (percentage >= 80) return "is-high";
        if (percentage >= 45) return "is-medium";
        return "is-low";
    }

    function statusSignal(status) {
        const clean = String(status || "").toLowerCase();
        if (["converted", "won", "completed", "ordered"].some((value) => clean.includes(value))) return __("Converted opportunity");
        if (["lost", "cancelled", "closed"].some((value) => clean.includes(value))) return __("Closed opportunity");
        if (["open", "quotation", "replied"].some((value) => clean.includes(value))) return __("Open opportunity");
        return __("Opportunity status");
    }

    function probabilityNumber(value) {
        return Math.max(0, Math.min(100, Number(String(value || "").replace("%", "")) || 0));
    }

    function ownerInitials(owner) {
        const clean = String(owner || "").trim();
        if (!clean || clean === "-") return "--";
        const parts = clean.includes("@") ? clean.split("@")[0].split(/[._-]+/) : clean.split(/\s+/);
        return parts.filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
    }

    function docsMarkup(docs) {
        if (!docs.length) {
            return `<section class="olp-docs-section"><div class="olp-docs-empty">${__("No related documents yet")}</div></section>`;
        }
        return `
            <section class="olp-docs-section">
                <div class="olp-docs-titlebar">
                    <h4>${__("ERP Documents")}</h4>
                    <span>${docs.length} ${__("linked")}</span>
                </div>
                <div class="olp-doc-list">
                    ${groupDocs(docs).map(docGroupMarkup).join("")}
                </div>
            </section>
        `;
    }

    function groupDocs(docs) {
        const groups = [];
        docs.forEach((doc) => {
            const key = doc.doctype || doc.label || "Document";
            let group = groups.find((entry) => entry.key === key);
            if (!group) {
                group = { key, label: doc.label || doc.doctype || "Document", docs: [] };
                groups.push(group);
            }
            group.docs.push(doc);
        });
        return groups;
    }

    function docGroupMarkup(group) {
        if (group.docs.length === 1) {
            return docMarkup(group.docs[0]);
        }
        const label = group.label || group.key || "Document";
        const tone = docTone(groupStatusSummary(group.docs));
        return `
            <div class="olp-doc-group">
                <button type="button" class="olp-doc-group-trigger ${group.docs.length > 1 ? "is-featured" : ""}" data-doc-group-toggle="1" aria-label="${frappe.utils.escape_html(__("Show {0} documents", [label]))}">
                    <span class="olp-doc-typebox">${frappe.utils.escape_html(docAbbr(label))}<em>${group.docs.length}</em></span>
                    <span class="olp-doc-group-copy">
                        <strong>${group.docs.length} ${frappe.utils.escape_html(label)}</strong>
                        <em>${frappe.utils.escape_html(groupStatusSummary(group.docs))}</em>
                    </span>
                    <span class="olp-doc-row-status status-${tone}">${frappe.utils.escape_html(groupStatusSummary(group.docs))}</span>
                    <span class="olp-doc-arrow">›</span>
                </button>
                <div class="olp-doc-group-panel">
                    <div class="olp-doc-group-panel-head">
                        <span>${frappe.utils.escape_html(label)}</span>
                        <strong>${group.docs.length}</strong>
                    </div>
                    <div class="olp-doc-group-items">
                        ${group.docs.map((doc) => docMarkup(doc, true)).join("")}
                    </div>
                </div>
            </div>
        `;
    }

    function groupStatusSummary(docs) {
        const statuses = unique(docs.map((doc) => String(doc.status || "-")).filter(Boolean));
        if (!statuses.length) return __("No status");
        if (statuses.length === 1) return statuses[0];
        if (statuses.length <= 2) return statuses.join(" · ");
        return __("{0} statuses", [statuses.length]);
    }

    function docMarkup(doc, grouped = false) {
        const doctype = String(doc.doctype || "");
        const name = String(doc.name || "");
        const label = String(doc.label || doctype || "Doc");
        const status = String(doc.status || "-");
        const title = `${label}: ${name} · ${status}`;
        return `
            <a href="#" class="olp-doc-chip ${grouped ? "is-grouped" : ""} status-${docTone(status)}" data-doctype="${frappe.utils.escape_html(doctype)}" data-name="${frappe.utils.escape_html(name)}" title="${frappe.utils.escape_html(title)}">
                <span class="olp-doc-type">${frappe.utils.escape_html(grouped ? shortDocName(name) : docAbbr(label || doctype))}</span>
                <span class="olp-doc-status">${frappe.utils.escape_html(status)}</span>
            </a>
        `;
    }

    function shortDocName(name) {
        const clean = String(name || "");
        const parts = clean.split("-").filter(Boolean);
        return parts.length ? parts[parts.length - 1] : clean.slice(-6) || "DOC";
    }

    function docAbbr(value) {
        const map = {
            "Quotation": "QTN",
            "Sales Order": "SO",
            "Project": "PRJ",
            "Material Request": "MR",
            "Purchase Order": "PO",
            "Delivery Note": "DN",
            "Sales Invoice": "SI",
        };
        return map[value] || String(value || "DOC").split(/\s+/).map((part) => part[0]).join("").slice(0, 4).toUpperCase();
    }

    function docTone(status) {
        const clean = String(status || "").toLowerCase();
        if (["completed", "paid", "received"].some((value) => clean.includes(value))) return "green";
        if (["cancelled", "closed", "blocked"].some((value) => clean.includes(value))) return "red";
        if (["draft", "pending"].some((value) => clean.includes(value))) return "gray";
        if (["to deliver", "to bill", "overdue"].some((value) => clean.includes(value))) return "orange";
        return "blue";
    }

    function kpi(label, value) {
        return `<div class="olp-kpi"><span>${frappe.utils.escape_html(String(label || "-"))}</span><strong>${frappe.utils.escape_html(String(value == null ? "-" : value))}</strong></div>`;
    }

    function filterInput(id, label, value, placeholder, type = "text", listId = "") {
        const listAttr = listId ? ` list="${frappe.utils.escape_html(listId)}"` : "";
        return `
            <label class="olp-filter-field" for="${frappe.utils.escape_html(id)}">
                <span>${frappe.utils.escape_html(label)}</span>
                <input id="${frappe.utils.escape_html(id)}" type="${frappe.utils.escape_html(type)}" placeholder="${frappe.utils.escape_html(placeholder)}" value="${frappe.utils.escape_html(value)}"${listAttr} />
            </label>
        `;
    }

    function filterCombo(id, label, value, placeholder, options) {
        const cleanOptions = unique(options || []);
        return `
            <label class="olp-filter-field" for="${frappe.utils.escape_html(id)}">
                <span>${frappe.utils.escape_html(label)}</span>
                <div class="olp-combo">
                    <input id="${frappe.utils.escape_html(id)}" type="text" placeholder="${frappe.utils.escape_html(placeholder)}" value="${frappe.utils.escape_html(value)}" autocomplete="off" />
                    <button type="button" class="olp-combo-toggle" data-combo-toggle="${frappe.utils.escape_html(id)}" aria-label="${frappe.utils.escape_html(__("Show options"))}">⌄</button>
                    <div class="olp-combo-menu">
                        <button type="button" data-combo-option="">${frappe.utils.escape_html(placeholder)}</button>
                        ${cleanOptions.map((option) => `<button type="button" data-combo-option="${frappe.utils.escape_html(option)}">${frappe.utils.escape_html(option)}</button>`).join("")}
                        <div class="olp-combo-empty">${frappe.utils.escape_html(__("No matching options"))}</div>
                    </div>
                </div>
            </label>
        `;
    }

    function filterSelect(id, label, options, value, allLabel) {
        return `
            <label class="olp-filter-field" for="${frappe.utils.escape_html(id)}">
                <span>${frappe.utils.escape_html(label)}</span>
                <select id="${frappe.utils.escape_html(id)}">
                    ${options.map((option) => `<option value="${frappe.utils.escape_html(option)}" ${option === value ? "selected" : ""}>${frappe.utils.escape_html(option === "All" ? allLabel : __(option || "All"))}</option>`).join("")}
                </select>
            </label>
        `;
    }

    function unique(values) {
        return [...new Set(values.filter(Boolean))];
    }

    function cleanFilterValue(value) {
        const clean = String(value || "").trim();
        return clean || "All";
    }

    function color(value) {
        return String(value || "Blue").toLowerCase();
    }

    function injectPipelineStyles() {
        if (document.getElementById("olp-shared-style")) return;
        const style = document.createElement("style");
        style.id = "olp-shared-style";
        style.textContent = `
            .olp-root { background: #f5f6fa; font-family: InterVariable, Inter, -apple-system, system-ui, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif; }
            .olp-shell { max-width: none; margin: 0; padding: 0; color: #0f172a; }
            .olp-hero { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; padding: 14px 24px 12px; background: #fff; border-bottom: 1px solid #e2e8f0; }
            .olp-hero-copy { min-width: 280px; max-width: 620px; }
            .olp-eyebrow { display: inline-flex; color: #00b0c8; font-size: 10px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }
            .olp-hero h1 { margin: 2px 0 3px; color: #0f172a; font-size: 21px; line-height: 1.15; font-weight: 800; letter-spacing: -.025em; }
            .olp-hero p { margin: 0; color: #64748b; line-height: 1.45; font-size: 12px; }
            .olp-hero-kpis { display: grid; grid-template-columns: repeat(4, minmax(118px, 1fr)); gap: 8px; width: min(760px, 58vw); }
            .olp-kpi { min-height: 58px; border-radius: 14px; background: #fff; border: 1px solid #e2e8f0; padding: 9px 11px; box-shadow: 0 1px 2px rgba(15,23,42,.04); }
            .olp-kpi span { display: block; color: #94a3b8; font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: .08em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            .olp-kpi strong { display: block; margin-top: 4px; font-size: 18px; color: #0f172a; letter-spacing: -.025em; font-weight: 800; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            .olp-toolbar { padding: 11px 24px; background: #fff; border-bottom: 1px solid #e2e8f0; }
            .olp-filter-row { display: grid; gap: 8px; align-items: end; }
            .olp-filter-row--wide { grid-template-columns: minmax(240px, 1.35fr) minmax(128px, .72fr) minmax(128px, .72fr) minmax(140px, .8fr) minmax(148px, .85fr) auto; }
            .olp-filter-field { display: grid; gap: 4px; min-width: 0; margin: 0; }
            .olp-filter-field span { color: #94a3b8; font-size: 10px; font-weight: 800; line-height: 1; text-transform: uppercase; letter-spacing: .08em; }
            .olp-filter-row input, .olp-filter-row select, .olp-filter-row > button { min-height: 36px; border: 1px solid #e2e8f0; background: #f8fafc; color: #334155; border-radius: 12px; padding: 0 11px; font-size: 12px; font-weight: 650; outline: none; transition: border-color .16s ease, box-shadow .16s ease, background .16s ease, color .16s ease; }
            .olp-filter-row input, .olp-filter-row select { width: 100%; }
            .olp-filter-row input:focus, .olp-filter-row select:focus { background: #fff; border-color: #00b0c8; box-shadow: 0 0 0 4px rgba(0,176,200,.1); }
            .olp-filter-row > button { cursor: pointer; background: #0f172a; border-color: #0f172a; color: #fff; font-weight: 800; padding: 0 14px; }
            .olp-filter-row > button:hover { background: #00b0c8; border-color: #00b0c8; }
            .olp-combo { position: relative; }
            .olp-combo input { padding-right: 34px; }
            .olp-combo-toggle { position: absolute; right: 4px; top: 4px; width: 28px; height: 28px; border: 0; border-radius: 9px; background: transparent; color: #94a3b8; font-size: 14px; line-height: 1; cursor: pointer; }
            .olp-combo-toggle:hover { background: #e2e8f0; color: #0f172a; }
            .olp-combo-menu { display: none; position: absolute; left: 0; right: 0; top: calc(100% + 6px); z-index: 30; width: 100%; max-height: 240px; overflow-y: auto; padding: 5px; border: 1px solid #e2e8f0; border-radius: 12px; background: #fff; box-shadow: 0 18px 38px rgba(15,23,42,.14); }
            .olp-combo.is-open .olp-combo-menu { display: grid; gap: 2px; }
            .olp-combo-menu button { width: 100%; min-height: 32px; border: 0; border-radius: 9px; background: #fff; color: #334155; padding: 0 9px; text-align: left; font-size: 12px; font-weight: 650; cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
            .olp-combo-menu button:hover { background: #ecfeff; color: #0e7490; }
            .olp-combo-empty { display: none; min-height: 32px; align-items: center; padding: 8px 9px; color: #94a3b8; font-size: 12px; font-weight: 650; }
            .olp-stage-strip { display: flex; gap: 8px; overflow-x: auto; padding: 10px 24px; background: #fff; border-bottom: 1px solid #e2e8f0; }
            .olp-stage-summary { flex: 0 0 150px; position: relative; border-radius: 12px; background: #f8fafc; border: 1px solid #e2e8f0; padding: 9px 10px 9px 12px; overflow: hidden; text-align: left; cursor: pointer; transition: transform .18s cubic-bezier(.16, 1, .3, 1), border-color .18s ease, background .18s ease, box-shadow .18s ease; }
            .olp-stage-summary:hover, .olp-stage-summary:focus { transform: translateY(-1px); background: #fff; border-color: #a5f3fc; box-shadow: 0 0 0 3px rgba(0,176,200,.08); outline: none; }
            .olp-stage-summary.is-empty { opacity: .62; }
            .olp-stage-summary.is-focused { background: #ecfeff; border-color: #67e8f9; box-shadow: 0 0 0 3px rgba(0,176,200,.12); }
            .olp-stage-summary::before { content: ""; position: absolute; left: 0; top: 8px; bottom: 8px; width: 3px; border-radius: 999px; background: #00b0c8; }
            .olp-stage-summary strong, .olp-stage-summary span { display: block; }
            .olp-stage-summary strong { color: #334155; font-size: 11px; font-weight: 800; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            .olp-stage-summary span { margin-top: 3px; color: #94a3b8; font-size: 10px; font-weight: 800; }
            .olp-board { display: flex; gap: 16px; overflow-x: auto; padding: 18px 24px 26px; align-items: stretch; scroll-snap-type: x mandatory; scroll-padding-inline: 24px; overscroll-behavior-x: contain; scrollbar-width: thin; scrollbar-color: #cbd5e1 transparent; }
            .olp-board::-webkit-scrollbar, .olp-card-stack::-webkit-scrollbar, .olp-combo-menu::-webkit-scrollbar, .olp-docs::-webkit-scrollbar, .olp-doc-group-items::-webkit-scrollbar { width: 4px; height: 4px; }
            .olp-board::-webkit-scrollbar-track, .olp-card-stack::-webkit-scrollbar-track, .olp-combo-menu::-webkit-scrollbar-track, .olp-docs::-webkit-scrollbar-track, .olp-doc-group-items::-webkit-scrollbar-track { background: transparent; }
            .olp-board::-webkit-scrollbar-thumb, .olp-card-stack::-webkit-scrollbar-thumb, .olp-combo-menu::-webkit-scrollbar-thumb, .olp-docs::-webkit-scrollbar-thumb, .olp-doc-group-items::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 999px; }
            .olp-board::-webkit-scrollbar-thumb:hover, .olp-card-stack::-webkit-scrollbar-thumb:hover, .olp-combo-menu::-webkit-scrollbar-thumb:hover, .olp-docs::-webkit-scrollbar-thumb:hover, .olp-doc-group-items::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
            .olp-column { flex: 0 0 288px; min-height: 560px; padding: 0; scroll-snap-align: start; scroll-snap-stop: always; transition: flex-basis .28s cubic-bezier(.16, 1, .3, 1), transform .22s cubic-bezier(.16, 1, .3, 1), background .18s ease; }
            .olp-column.is-focused .olp-column-head { box-shadow: 0 0 0 3px rgba(0,176,200,.12); border-radius: 14px; }
            .olp-column.stage-blue .olp-column-head::before, .olp-stage-summary.stage-blue::before { background: #00b0c8; }
            .olp-column.stage-green .olp-column-head::before, .olp-stage-summary.stage-green::before { background: #10b981; }
            .olp-column.stage-orange .olp-column-head::before, .olp-stage-summary.stage-orange::before { background: #f59e0b; }
            .olp-column.stage-purple .olp-column-head::before, .olp-stage-summary.stage-purple::before { background: #8b5cf6; }
            .olp-column.stage-red .olp-column-head::before, .olp-stage-summary.stage-red::before { background: #ef4444; }
            .olp-column.stage-gray .olp-column-head::before, .olp-stage-summary.stage-gray::before { background: #94a3b8; }
            .olp-column.drop-ready .olp-card-stack { background: rgba(0,176,200,.08); box-shadow: inset 0 0 0 2px rgba(0,176,200,.18); }
            .olp-column-head { position: sticky; top: 0; z-index: 2; display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 10px; padding: 0 2px 0 10px; }
            .olp-column-head::before { content: ""; flex: 0 0 4px; width: 4px; height: 18px; border-radius: 999px; background: #00b0c8; }
            .olp-column-head h2 { flex: 1; margin: 0; color: #475569; font-size: 11px; font-weight: 900; letter-spacing: .09em; text-transform: uppercase; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            .olp-column-head span { display: inline-flex; min-width: 24px; height: 22px; align-items: center; justify-content: center; border-radius: 999px; background: #e2e8f0; color: #475569; font-size: 10px; font-weight: 900; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
            .olp-column-toggle { flex: 0 0 24px; width: 24px; height: 24px; border: 1px solid #e2e8f0; border-radius: 8px; background: #fff; color: #64748b; display: inline-flex; align-items: center; justify-content: center; font-size: 15px; line-height: 1; font-weight: 900; cursor: pointer; transition: transform .18s cubic-bezier(.16, 1, .3, 1), background .16s ease, border-color .16s ease, color .16s ease, box-shadow .16s ease; }
            .olp-column-toggle:hover, .olp-column-toggle:focus { background: #ecfeff; border-color: #a5f3fc; color: #0e7490; box-shadow: 0 0 0 3px rgba(0,176,200,.1); outline: none; }
            .olp-column-toggle:active { transform: scale(.92); }
            .olp-column.is-collapsed { flex-basis: 58px; }
            .olp-column.is-collapsed.drop-ready { background: rgba(0,176,200,.08); border-radius: 16px; box-shadow: inset 0 0 0 2px rgba(0,176,200,.16); }
            .olp-column.is-collapsed .olp-column-head { min-height: 230px; margin-bottom: 0; padding: 8px 0; flex-direction: column; justify-content: flex-start; gap: 8px; background: #fff; border: 1px solid #e2e8f0; border-radius: 16px; box-shadow: 0 1px 2px rgba(15,23,42,.04); }
            .olp-column.is-collapsed .olp-column-head::before { flex-basis: 22px; width: 4px; height: 22px; }
            .olp-column.is-collapsed .olp-column-head h2 { flex: 0 1 auto; writing-mode: vertical-rl; transform: rotate(180deg); max-height: 132px; max-width: 24px; color: #64748b; text-align: center; text-overflow: ellipsis; }
            .olp-column.is-collapsed .olp-column-head span { min-width: 24px; }
            .olp-column.is-collapsed .olp-card-stack { display: none; }
            .olp-card-stack { display: grid; gap: 10px; min-height: 520px; max-height: calc(100vh - 265px); overflow-y: auto; border-radius: 16px; padding: 2px 2px 6px; transition: background .2s cubic-bezier(.16, 1, .3, 1), box-shadow .2s cubic-bezier(.16, 1, .3, 1); scrollbar-width: thin; scrollbar-color: #cbd5e1 transparent; }
            .olp-card { position: relative; overflow: hidden; border-radius: 15px; background: radial-gradient(circle at 100% 0%, rgba(99,102,241,.05), transparent 34%), #fff; border: 1px solid #e2e8f0; padding: 11px; box-shadow: 0 1px 2px rgba(15,23,42,.04); cursor: grab; transition: transform .22s cubic-bezier(.16, 1, .3, 1), box-shadow .22s cubic-bezier(.16, 1, .3, 1), border-color .18s ease, opacity .18s ease; }
            .olp-card::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: #00b0c8; opacity: 0; transition: opacity .18s ease; }
            .olp-card:hover { transform: translateY(-1px); border-color: rgba(0,176,200,.35); box-shadow: 0 10px 24px rgba(15,23,42,.08); }
            .olp-card:hover::before { opacity: 1; }
            .olp-card.dragging { opacity: .62; cursor: grabbing; }
            .olp-confidence { position: absolute; top: 9px; right: 9px; width: 58px; display: grid; gap: 2px; padding: 5px 6px 6px; border-radius: 11px; background: rgba(255,255,255,.9); border: 1px solid #e2e8f0; box-shadow: 0 8px 18px rgba(15,23,42,.06); backdrop-filter: blur(10px); }
            .olp-confidence span { color: #94a3b8; font-size: 6px; font-weight: 900; line-height: 1; text-transform: uppercase; letter-spacing: .08em; }
            .olp-confidence strong { color: #0f172a; font-size: 13px; font-weight: 900; line-height: 1; letter-spacing: -.04em; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
            .olp-confidence::after { content: ""; height: 2px; border-radius: 999px; background: #e2e8f0; grid-column: 1; grid-row: 3; }
            .olp-confidence i { position: relative; z-index: 1; display: block; height: 2px; max-width: 100%; border-radius: 999px; grid-column: 1; grid-row: 3; }
            .olp-confidence.is-high i { background: #059669; }
            .olp-confidence.is-medium i { background: #d97706; }
            .olp-confidence.is-low i { background: #64748b; }
            .olp-card-headline { display: flex; align-items: center; gap: 6px; min-width: 0; padding-right: 66px; }
            .olp-code { border-radius: 7px; padding: 3px 6px; font-size: 8px; font-weight: 800; line-height: 1.2; }
            .olp-code { background: #f8fafc; border: 1px solid #e2e8f0; color: #64748b; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
            .olp-card h3 { margin: 9px 68px 3px 0; color: #0f172a; font-size: 13px; font-weight: 850; letter-spacing: -.02em; line-height: 1.18; }
            .olp-card p { margin: 0; color: #94a3b8; line-height: 1.35; font-size: 10px; font-weight: 600; }
            .olp-card-business-row { display: grid; grid-template-columns: minmax(0, .9fr) minmax(0, 1.1fr); gap: 6px; margin-top: 9px; }
            .olp-value-block, .olp-owner-card { min-width: 0; min-height: 40px; border: 1px solid #eef2f7; border-radius: 11px; background: rgba(248,250,252,.72); padding: 6px; }
            .olp-value-block { display: grid; align-content: center; gap: 2px; }
            .olp-value-block span, .olp-owner-copy small { color: #94a3b8; font-size: 7px; font-weight: 900; line-height: 1; text-transform: uppercase; letter-spacing: .08em; }
            .olp-value-block strong { color: #0f172a; font-size: 10px; font-weight: 900; line-height: 1.1; letter-spacing: -.02em; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            .olp-value-block.is-empty strong { color: #94a3b8; font-family: inherit; font-size: 10px; }
            .olp-owner-card { display: grid; grid-template-columns: 25px minmax(0, 1fr); align-items: center; gap: 6px; }
            .olp-owner-avatar { width: 25px; height: 25px; border-radius: 8px; display: inline-flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #4f46e5, #7c3aed); color: #fff; font-size: 9px; font-weight: 900; box-shadow: inset 0 1px 0 rgba(255,255,255,.18), 0 6px 14px rgba(79,70,229,.18); }
            .olp-owner-copy { min-width: 0; display: grid; gap: 2px; }
            .olp-owner-copy strong { min-width: 0; color: #334155; font-size: 10px; font-weight: 850; line-height: 1.1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
            .olp-status-badge { min-width: 0; max-width: 76px; display: inline-flex; align-items: center; border-radius: 999px; padding: 3px 7px; font-size: 8px; font-weight: 900; line-height: 1.2; text-transform: uppercase; letter-spacing: .04em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
            .olp-status-badge.status-green { background: #ecfdf5; border: 1px solid #bbf7d0; color: #047857; }
            .olp-status-badge.status-orange { background: #fffbeb; border: 1px solid #fde68a; color: #b45309; }
            .olp-status-badge.status-red { background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; }
            .olp-status-badge.status-blue { background: #ecfeff; border: 1px solid #a5f3fc; color: #0e7490; }
            .olp-status-badge.status-gray { background: #f8fafc; border: 1px solid #e2e8f0; color: #64748b; }
            .olp-card-meta { display: grid; gap: 4px; margin-top: 10px; border-radius: 12px; background: #f8fafc; border: 1px solid #eef2f7; padding: 8px; }
            .olp-card-meta span { color: #64748b; font-size: 10px; font-weight: 700; }
            .olp-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
            .olp-tags span { border-radius: 7px; background: #f8fafc; border: 1px solid #e2e8f0; color: #64748b; padding: 3px 6px; font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; }
            .olp-docs-block { margin-top: 10px; border-top: 1px solid #f1f5f9; padding-top: 9px; }
            .olp-docs-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
            .olp-docs-head span { color: #94a3b8; font-size: 9px; font-weight: 900; text-transform: uppercase; letter-spacing: .08em; }
            .olp-docs-head strong { min-width: 20px; height: 18px; display: inline-flex; align-items: center; justify-content: center; border-radius: 999px; background: #e2e8f0; color: #475569; font-size: 9px; font-weight: 900; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
            .olp-docs { display: flex; flex-wrap: wrap; gap: 5px; max-height: 190px; overflow-y: auto; padding-right: 2px; scrollbar-width: thin; scrollbar-color: #cbd5e1 transparent; }
            .olp-docs--empty { margin-top: 10px; border-top: 1px solid #f1f5f9; padding-top: 10px; }
            .olp-doc-group { display: grid; gap: 5px; width: 100%; }
            .olp-doc-group-trigger { width: 100%; min-height: 34px; display: grid; grid-template-columns: 34px minmax(0, 1fr) auto; align-items: center; gap: 7px; border: 1px solid #e2e8f0; border-radius: 10px; background: #f8fafc; color: #334155; padding: 4px 6px 4px 4px; text-align: left; cursor: pointer; transition: background .16s ease, border-color .16s ease, box-shadow .16s ease, transform .16s cubic-bezier(.16, 1, .3, 1); }
            .olp-doc-group-trigger:hover, .olp-doc-group-trigger:focus { background: #fff; border-color: #a5f3fc; box-shadow: 0 0 0 3px rgba(0,176,200,.08); outline: none; }
            .olp-doc-group-trigger:active { transform: scale(.99); }
            .olp-doc-group-type { min-width: 30px; height: 24px; display: inline-flex; align-items: center; justify-content: center; border-radius: 8px; background: #0f172a; color: #fff; font-size: 9px; font-weight: 900; letter-spacing: .06em; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
            .olp-doc-group-copy { min-width: 0; display: grid; gap: 1px; }
            .olp-doc-group-copy strong { color: #0f172a; font-size: 10px; font-weight: 900; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            .olp-doc-group-copy em { color: #94a3b8; font-size: 9px; font-style: normal; font-weight: 800; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            .olp-doc-group-count { min-width: 22px; height: 20px; display: inline-flex; align-items: center; justify-content: center; border-radius: 999px; background: #e2e8f0; color: #475569; font-size: 9px; font-weight: 900; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
            .olp-doc-group-panel { display: none; padding: 6px; border: 1px solid #e2e8f0; border-radius: 10px; background: #fff; box-shadow: inset 0 1px 0 rgba(15,23,42,.03); }
            .olp-doc-group.is-open .olp-doc-group-panel { display: grid; gap: 6px; }
            .olp-doc-group-panel-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 0 1px; }
            .olp-doc-group-panel-head span { color: #64748b; font-size: 9px; font-weight: 900; text-transform: uppercase; letter-spacing: .08em; }
            .olp-doc-group-panel-head strong { min-width: 18px; height: 16px; display: inline-flex; align-items: center; justify-content: center; border-radius: 999px; background: #e2e8f0; color: #475569; font-size: 9px; font-weight: 900; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
            .olp-doc-group-items { display: grid; gap: 3px; max-height: 145px; overflow-y: auto; padding-right: 2px; scrollbar-width: thin; scrollbar-color: #cbd5e1 transparent; }
            .olp-doc-chip, .olp-docs-empty { display: inline-flex; align-items: center; min-width: 0; color: #475569; background: #f8fafc; border: 1px solid #e2e8f0; text-decoration: none; border-radius: 8px; font-weight: 850; font-size: 9px; transition: transform .16s cubic-bezier(.16, 1, .3, 1), border-color .16s ease, color .16s ease, background .16s ease; }
            .olp-doc-chip { max-width: 100%; overflow: hidden; }
            .olp-doc-chip.is-grouped { width: 100%; }
            .olp-doc-chip:hover, .olp-doc-chip:focus { transform: translateY(-1px); color: #0e7490; border-color: #a5f3fc; background: #ecfeff; outline: none; }
            .olp-doc-type { flex: 0 0 auto; min-width: 28px; padding: 4px 5px; border-right: 1px solid currentColor; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; opacity: .78; text-align: center; }
            .olp-doc-status { min-width: 0; padding: 4px 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
            .olp-doc-chip.status-green { background: #ecfdf5; border-color: #bbf7d0; color: #047857; }
            .olp-doc-chip.status-orange { background: #fffbeb; border-color: #fde68a; color: #b45309; }
            .olp-doc-chip.status-red { background: #fef2f2; border-color: #fecaca; color: #b91c1c; }
            .olp-doc-chip.status-blue { background: #ecfeff; border-color: #a5f3fc; color: #0e7490; }
            .olp-doc-chip.status-gray { background: #f8fafc; border-color: #e2e8f0; color: #64748b; }
            .olp-docs-empty { justify-content: center; width: 100%; min-height: 30px; padding: 6px 8px; color: #94a3b8; font-weight: 800; }
            .olp-card { border-radius: 18px; padding: 0; background: #fff; border-color: #e8ebef; box-shadow: 0 4px 8px rgba(15,23,42,.04), 0 16px 32px -18px rgba(15,23,42,.14); }
            .olp-card:hover { border-color: #c7d2fe; box-shadow: 0 4px 8px rgba(15,23,42,.04), 0 18px 40px -18px rgba(15,23,42,.18); }
            .olp-record-hero { padding: 15px 15px 13px; background: radial-gradient(ellipse at top right, rgba(99,102,241,.07) 0%, transparent 58%), #fff; }
            .olp-record-topbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 13px; }
            .olp-id-pill { display: inline-flex; align-items: center; max-width: 158px; min-width: 0; padding: 5px 9px; border: 1px solid #e8ebef; border-radius: 999px; background: #f7f8fa; color: #495061; font-size: 9px; font-weight: 650; line-height: 1.1; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            .olp-stage-block { display: inline-flex; align-items: center; gap: 9px; flex: 0 0 auto; }
            .olp-stage-info { display: grid; gap: 1px; text-align: right; }
            .olp-stage-info span { color: #6b7280; font-size: 8px; font-weight: 800; text-transform: uppercase; letter-spacing: .08em; }
            .olp-stage-info strong { display: inline-flex; align-items: center; justify-content: flex-end; gap: 5px; max-width: 78px; color: #495061; font-size: 10px; font-weight: 800; line-height: 1.1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            .olp-stage-info strong::before { content: ""; width: 6px; height: 6px; flex: 0 0 6px; border-radius: 999px; background: currentColor; box-shadow: 0 0 0 3px rgba(221,225,231,.7); }
            .olp-stage-info strong.status-green { color: #047857; }
            .olp-stage-info strong.status-orange { color: #b45309; }
            .olp-stage-info strong.status-red { color: #be123c; }
            .olp-stage-info strong.status-blue { color: #0369a1; }
            .olp-stage-info strong.status-gray { color: #6b7280; }
            .olp-dial { position: relative; width: 38px; height: 38px; border-radius: 999px; background: conic-gradient(#6366f1 calc(var(--pct) * 1%), #eff1f4 0); box-shadow: inset 0 0 0 1px #e8ebef; }
            .olp-dial::before { content: ""; position: absolute; inset: 4px; border-radius: inherit; background: #fff; box-shadow: inset 0 0 0 1px #eff1f4; }
            .olp-dial span { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: #11151f; font-size: 9px; font-weight: 800; letter-spacing: -.02em; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
            .olp-dial.is-high { background: conic-gradient(#059669 calc(var(--pct) * 1%), #eff1f4 0); }
            .olp-dial.is-medium { background: conic-gradient(#7c3aed calc(var(--pct) * 1%), #eff1f4 0); }
            .olp-dial.is-low { background: conic-gradient(#6b7280 calc(var(--pct) * 1%), #eff1f4 0); }
            .olp-signal { display: inline-flex; align-items: center; gap: 5px; margin-bottom: 9px; padding: 3px 8px; border-radius: 999px; background: #ecfdf5; border: 1px solid #d1fae5; color: #047857; font-size: 9px; font-weight: 750; }
            .olp-signal i { width: 5px; height: 5px; border-radius: 999px; background: currentColor; box-shadow: 0 0 0 3px rgba(5,150,105,.12); }
            .olp-signal.status-red { background: #fff1f2; border-color: #ffe4e6; color: #be123c; }
            .olp-signal.status-orange { background: #fffbeb; border-color: #fde68a; color: #b45309; }
            .olp-signal.status-blue { background: #f0f9ff; border-color: #bae6fd; color: #0369a1; }
            .olp-signal.status-gray { background: #f5f6f8; border-color: #e8ebef; color: #6b7280; }
            .olp-record-hero h3 { margin: 0 0 4px; color: #0a0e1a; font-size: 15px; font-weight: 750; letter-spacing: -.025em; line-height: 1.16; }
            .olp-record-hero p { margin: 0; color: #6b7280; font-size: 10.5px; font-weight: 500; line-height: 1.36; }
            .olp-meta-strip { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-top: 12px; padding-top: 10px; border-top: 1px solid #eff1f4; }
            .olp-owner-card { min-width: 0; display: grid; grid-template-columns: 27px minmax(0, 1fr); gap: 8px; align-items: center; border: 0; background: transparent; padding: 0; }
            .olp-owner-avatar { width: 27px; height: 27px; border-radius: 9px; background: linear-gradient(135deg, #6366f1, #7c3aed); color: #fff; font-size: 10px; font-weight: 800; box-shadow: inset 0 1px 0 rgba(255,255,255,.22), 0 6px 14px rgba(99,102,241,.18); }
            .olp-owner-copy { min-width: 0; display: grid; gap: 1px; }
            .olp-owner-copy strong { min-width: 0; color: #11151f; font-size: 10.5px; font-weight: 650; line-height: 1.15; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
            .olp-owner-copy small { color: #6b7280; font-size: 9px; font-weight: 600; letter-spacing: 0; text-transform: none; }
            .olp-value-block { min-width: 76px; min-height: 0; display: grid; gap: 1px; justify-items: end; border: 0; background: transparent; padding: 0; }
            .olp-value-block span { color: #6b7280; font-size: 8px; font-weight: 800; text-transform: uppercase; letter-spacing: .08em; }
            .olp-value-block strong { color: #11151f; font-size: 10.5px; font-weight: 800; line-height: 1.1; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; white-space: nowrap; }
            .olp-value-block.is-empty strong { color: #9099a6; font-family: inherit; }
            .olp-tags-row { display: flex; align-items: center; gap: 6px; padding: 9px 15px; background: #f7f8fa; border-top: 1px solid #eff1f4; border-bottom: 1px solid #eff1f4; overflow-x: auto; scrollbar-width: none; }
            .olp-tags-row::-webkit-scrollbar { display: none; }
            .olp-tag-label { flex: 0 0 auto; color: #9099a6; font-size: 8px; font-weight: 900; text-transform: uppercase; letter-spacing: .1em; }
            .olp-tag { flex: 0 0 auto; display: inline-flex; align-items: center; gap: 5px; padding: 4px 8px; border: 1px solid #e8ebef; border-radius: 8px; background: #fff; color: #495061; font-size: 10px; font-weight: 650; }
            .olp-tag i { width: 5px; height: 5px; border-radius: 999px; background: #6366f1; }
            .olp-docs-section { padding: 13px 15px 14px; }
            .olp-docs-titlebar { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 9px; }
            .olp-docs-titlebar h4 { margin: 0; color: #1f2433; font-size: 9.5px; font-weight: 850; text-transform: uppercase; letter-spacing: .1em; }
            .olp-docs-titlebar span { flex: 0 0 auto; padding: 2px 7px; border: 1px solid #eff1f4; border-radius: 999px; background: #f5f6f8; color: #495061; font-size: 9px; font-weight: 700; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
            .olp-doc-list { display: grid; gap: 7px; max-height: 248px; overflow-y: auto; padding-right: 2px; scrollbar-width: thin; scrollbar-color: #cbd5e1 transparent; }
            .olp-doc-group-trigger, .olp-doc-list > .olp-doc-chip { width: 100%; min-height: 40px; display: grid; grid-template-columns: 34px minmax(0, 1fr) auto 10px; align-items: center; gap: 9px; padding: 8px 9px 8px 8px; border: 1px solid #e8ebef; border-radius: 12px; background: #fff; color: #2e3548; text-align: left; cursor: pointer; transition: transform .2s cubic-bezier(.16, 1, .3, 1), box-shadow .2s cubic-bezier(.16, 1, .3, 1), border-color .16s ease, background .16s ease; }
            .olp-doc-group-trigger:hover, .olp-doc-list > .olp-doc-chip:hover { transform: translateX(2px); border-color: #c7d2fe; background: #eef2ff; box-shadow: 0 1px 2px rgba(15,23,42,.04), 0 4px 12px rgba(15,23,42,.05); }
            .olp-doc-group-trigger.is-featured { background: linear-gradient(135deg, #0a0e1a 0%, #11151f 100%); border-color: #0a0e1a; color: #fff; box-shadow: 0 8px 22px -12px rgba(15,23,42,.36); }
            .olp-doc-group-trigger.is-featured .olp-doc-group-copy strong, .olp-doc-group-trigger.is-featured .olp-doc-group-copy em, .olp-doc-group-trigger.is-featured .olp-doc-arrow { color: rgba(255,255,255,.92); }
            .olp-doc-typebox, .olp-doc-type { position: relative; width: 30px; height: 30px; display: inline-flex; align-items: center; justify-content: center; border-radius: 8px; background: #f0f9ff; border: 1px solid #e0f2fe; color: #0369a1; font-size: 9px; font-weight: 850; letter-spacing: .04em; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; padding: 0; }
            .olp-doc-group-trigger.is-featured .olp-doc-typebox { background: linear-gradient(135deg, #4f46e5, #7c3aed); border-color: rgba(255,255,255,.18); color: #fff; box-shadow: inset 0 1px 0 rgba(255,255,255,.16), 0 4px 12px rgba(99,102,241,.34); }
            .olp-doc-typebox em { position: absolute; top: -5px; right: -5px; min-width: 16px; height: 16px; padding: 0 4px; display: inline-flex; align-items: center; justify-content: center; border-radius: 999px; border: 2px solid #0a0e1a; background: #fff; color: #0a0e1a; font-size: 8px; font-style: normal; font-weight: 900; }
            .olp-doc-group-copy { min-width: 0; display: grid; gap: 1px; }
            .olp-doc-group-copy strong { color: #11151f; font-size: 10.5px; font-weight: 800; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            .olp-doc-group-copy em { color: #6b7280; font-size: 9px; font-style: normal; font-weight: 650; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            .olp-doc-row-status, .olp-doc-status { display: inline-flex; align-items: center; gap: 4px; max-width: 68px; padding: 3px 6px; border-radius: 7px; font-size: 8.5px; font-weight: 800; line-height: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            .olp-doc-row-status::before, .olp-doc-status::before { content: ""; width: 5px; height: 5px; flex: 0 0 5px; border-radius: 999px; background: currentColor; }
            .olp-doc-row-status.status-green, .olp-doc-status.status-green { background: #ecfdf5; border: 1px solid #d1fae5; color: #047857; }
            .olp-doc-row-status.status-orange, .olp-doc-status.status-orange { background: #f5f3ff; border: 1px solid #ddd6fe; color: #6d28d9; }
            .olp-doc-row-status.status-red, .olp-doc-status.status-red { background: #fff1f2; border: 1px solid #ffe4e6; color: #be123c; }
            .olp-doc-row-status.status-blue, .olp-doc-status.status-blue { background: #eef2ff; border: 1px solid #e0e7ff; color: #3730a3; }
            .olp-doc-row-status.status-gray, .olp-doc-status.status-gray { background: #f5f6f8; border: 1px solid #e8ebef; color: #6b7280; }
            .olp-doc-arrow { color: #9099a6; font-size: 16px; line-height: 1; transition: transform .18s ease, color .18s ease; }
            .olp-doc-group-trigger:hover .olp-doc-arrow, .olp-doc-list > .olp-doc-chip:hover::after { transform: translateX(2px); color: #4f46e5; }
            .olp-doc-list > .olp-doc-chip { grid-template-columns: 34px minmax(0, 1fr) 10px; text-decoration: none; }
            .olp-doc-list > .olp-doc-chip::after { content: "›"; color: #9099a6; font-size: 16px; transition: transform .18s ease, color .18s ease; }
            .olp-doc-chip.is-grouped { min-height: 28px; grid-template-columns: 38px minmax(0, 1fr); padding: 5px 7px; border-radius: 9px; }
            .olp-doc-chip.is-grouped::after { display: none; }
            .olp-doc-list > .olp-doc-chip .olp-doc-status { max-width: none; justify-content: flex-start; }
            .olp-doc-chip.is-grouped .olp-doc-type { width: auto; height: auto; min-width: 30px; background: transparent; border: 0; color: inherit; justify-content: flex-start; }
            .olp-doc-chip.is-grouped .olp-doc-status { max-width: 100%; }
            .olp-doc-group-panel { display: none; padding: 6px; border: 1px solid #e8ebef; border-radius: 12px; background: #fff; }
            .olp-doc-group.is-open .olp-doc-group-panel { display: grid; gap: 6px; }
            .olp-empty-column, .olp-empty-board, .olp-empty-note { min-height: 100px; border: 1px dashed #cbd5e1; border-radius: 14px; display: flex; align-items: center; justify-content: center; color: #94a3b8; font-weight: 800; font-size: 11px; padding: 20px; background: rgba(255,255,255,.6); }
            .olp-empty-board { min-width: 320px; min-height: 180px; background: rgba(255,255,255,.72); }
            .olp-empty-note { min-height: 0; margin: 0 24px 18px; background: #fff; }
            @media (max-width: 1240px) { .olp-hero { flex-direction: column; gap: 12px; } .olp-hero-kpis { width: 100%; } .olp-filter-row--wide { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
            @media (prefers-reduced-motion: no-preference) { .olp-board { scroll-behavior: smooth; } }
            @media (prefers-reduced-motion: reduce) { .olp-board { scroll-behavior: auto; } .olp-column, .olp-card, .olp-column-toggle, .olp-card-stack { transition: none; } }
            @media (max-width: 760px) { .olp-hero, .olp-toolbar, .olp-stage-strip { padding-left: 14px; padding-right: 14px; } .olp-board { padding: 16px 14px 22px; scroll-padding-inline: 14px; } .olp-hero-kpis, .olp-filter-row--wide { grid-template-columns: 1fr; } .olp-column { flex-basis: 280px; } .olp-column.is-collapsed { flex-basis: 58px; } }
        `;
        document.head.appendChild(style);
    }
})();
