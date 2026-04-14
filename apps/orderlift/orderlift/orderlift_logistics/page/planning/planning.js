const PLANNING_COLORS = {
    SO: "#185FA5",
    PO: "#C17F24",
    QT: "#884DB7",
    DN: "#0D6B50",
};

const PLANNING_CONFIDENCE = {
    committed: { bg: "#D8F2EA", text: "#0D6B50" },
    tentative: { bg: "#FDE8BE", text: "#854F0B" },
    inquiry: { bg: "#EEECEA", text: "#5F5E5A" },
    ready: { bg: "#E0EFFC", text: "#1A5FA3" },
};

frappe.pages["planning"].on_page_load = function (wrapper) {
    wrapper.planning_page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Planning"),
        single_column: true,
    });

    renderPlanningPage(wrapper);
};

frappe.pages["planning"].on_page_show = function (wrapper) {
    stretchPlanningLayout(wrapper);
    const planName = getPlanParam();
    if (!planName) return;

    // If state doesn't exist or plan changed, full re-render
    if (!wrapper._planningState || wrapper._planningState.planName !== planName) {
        renderPlanningPage(wrapper);
    }
};

function getPlanParam() {
    // Route: /app/planning/FLP-00001
    const route = frappe.get_route();
    return route[1] || "";
}

function renderPlanningPage(wrapper) {
    stretchPlanningLayout(wrapper);
    ensurePlanningFonts();
    injectPlanningStyles();

    const planName = getPlanParam();
    if (!planName) {
        wrapper.planning_page.main.html(`
            <div style="padding:60px;text-align:center;font-family:'Outfit',sans-serif;color:#6B6A70;">
                <div style="font-size:18px;font-weight:600;color:#1A1A1E;margin-bottom:8px;">No forecast plan selected</div>
                <div style="margin-bottom:16px;">Open a plan from the Forecast Plans list to start planning.</div>
                <button onclick="frappe.set_route('forecast-plans')" style="padding:8px 20px;border-radius:8px;border:none;background:#0D6B50;color:white;font-size:13px;font-weight:500;cursor:pointer;">Go to Forecast Plans</button>
            </div>
        `);
        return;
    }

    const rootId = "planning-native-root";
    wrapper.planning_page.main.html(`<div id="${rootId}" class="planning-native-root"></div>`);

    const state = {
        wrapper,
        root: wrapper.querySelector(`#${rootId}`),
        planName: planName,
        planDoc: null,
        container: null,
        containerType: "",
        timeline: "This week",
        currentTypeFilter: "ALL",
        currentStatusFilter: "ALL",
        expandedItem: null,
        dragId: null,
        ready: false,
        planItems: [],
        sourceQueue: [],
        containerProfiles: [],
        loading: true,
    };
    wrapper._planningState = state;

    state.root.innerHTML = planningShellHtml(state);
    bindPlanningEvents(state);
    loadPlanData(state);
}

function loadPlanData(state) {
    state.loading = true;
    state.root.querySelector("#planItemsList").innerHTML = `<div style="padding:20px;text-align:center;color:#A0A0A8;font-size:12px;">Loading plan...</div>`;

    frappe.call({
        method: "orderlift.orderlift_logistics.services.forecast_planning.get_plan_detail",
        args: { plan_name: state.planName },
        async: true,
        callback: (r) => {
            const plan = r.message;
            state.planDoc = plan;
            state.container = plan.container;
            state.ready = plan.status === "Ready" || plan.status === "Converted";

            state.planItems = (plan.items || []).map((item) => ({
                id: item.id,
                row_name: item.row_name,
                source_doctype: item.source_doctype,
                type: item.type,
                party: item.party,
                party_type: item.party_type,
                volume: item.volume,
                weight: item.weight,
                confidence: item.confidence,
                date: item.date,
                docstatus: item.docstatus_label,
                itemCount: item.item_count,
                selected: item.selected,
                lineItems: (item.line_items || []).map((li) => ({
                    code: li.item_code,
                    desc: li.item_name || li.item_code,
                    qty: li.qty,
                    vol: li.line_volume_m3,
                    wt: li.line_weight_kg,
                })),
            }));

            // Store allowed doctypes for flow scope filtering
            state.allowedDoctypes = plan.allowed_doctypes || [];

            // Update header
            updateTopbar(state);
            updateTypeTabs(state);
            loadSourceQueue(state);
            loadContainerProfiles(state);
        },
    });
}

function loadSourceQueue(state) {
    const plan = state.planDoc;
    frappe.call({
        method: "orderlift.orderlift_logistics.services.forecast_planning.get_forecast_source_queue",
        args: {
            company: plan.company || undefined,
            flow_scope: plan.flow_scope || undefined,
            shipping_responsibility: plan.shipping_responsibility || undefined,
            destination_zone: plan.destination_zone || undefined,
        },
        async: true,
        callback: (r) => {
            state.sourceQueue = (r.message || []).map((doc) => ({
                id: doc.id,
                source_doctype: doc.source_doctype,
                type: doc.type,
                party: doc.party,
                party_type: doc.party_type,
                volume: doc.volume,
                weight: doc.weight,
                confidence: doc.confidence,
                date: doc.date,
                docstatus: doc.docstatus_label,
                itemCount: doc.item_count,
                lineItems: (doc.line_items || []).map((li) => ({
                    code: li.item_code,
                    desc: li.item_name || li.item_code,
                    qty: li.qty,
                    vol: li.line_volume_m3,
                    wt: li.line_weight_kg,
                })),
            }));
            state.loading = false;
            refreshPlanning(state);
        },
    });
}

function loadContainerProfiles(state) {
    frappe.call({
        method: "orderlift.orderlift_logistics.services.forecast_planning.get_container_profiles",
        async: true,
        callback: (r) => {
            state.containerProfiles = r.message || [];
            renderContainerButtons(state);
        },
    });
}

function getCapacity(state) {
    if (state.container) {
        return { maxVol: state.container.max_volume_m3, maxKg: state.container.max_weight_kg };
    }
    return { maxVol: 67.7, maxKg: 26000 };
}

function updateTopbar(state) {
    const plan = state.planDoc;
    if (!plan) return;

    const crumb = state.root.querySelector(".topbar-crumb");
    if (crumb) crumb.textContent = plan.plan_label || plan.name;

    // Flow scope badge
    const flowBadge = state.root.querySelector("#topFlowBadge");
    if (flowBadge && plan.flow_scope) {
        const flowColors = { Inbound: "#C17F24", Domestic: "#884DB7", Outbound: "#0D6B50" };
        flowBadge.textContent = plan.flow_scope;
        flowBadge.style.background = (flowColors[plan.flow_scope] || "#6B6A70") + "22";
        flowBadge.style.color = flowColors[plan.flow_scope] || "#6B6A70";
        flowBadge.style.display = "";
    } else if (flowBadge) {
        flowBadge.style.display = "none";
    }

    const deadlineInput = state.root.querySelector(".deadline-wrap input[type=date]");
    if (deadlineInput && plan.deadline) deadlineInput.value = plan.deadline;

    const cap = getCapacity(state);
    setText(state, ".kpi-sub-cap-vol", `of ${cap.maxVol.toFixed(1)} m3 capacity`);
    setText(state, ".kpi-sub-cap-wt", `of ${cap.maxKg.toLocaleString()} kg max`);

    // Container card header
    const containerTitle = state.root.querySelector(".card-title-container");
    if (containerTitle && state.container) {
        containerTitle.textContent = `Container - ${state.container.container_name || state.container.container_type || state.container.name}`;
    }
    const cardMeta = state.root.querySelector(".card-meta-container");
    if (cardMeta) {
        cardMeta.innerHTML = `<span>Cap: <strong>${cap.maxVol.toFixed(1)} m3</strong></span><span>Max: <strong>${cap.maxKg.toLocaleString()} kg</strong></span>${plan.departure_date ? `<span>Dep: <strong>${plan.departure_date}</strong></span>` : ""}`;
    }
}

function renderContainerButtons(state) {
    const grid = state.root.querySelector(".ct-grid");
    if (!grid || !state.containerProfiles.length) return;

    grid.innerHTML = state.containerProfiles.map((cp) => {
        const active = state.container && state.container.name === cp.name;
        return `<button class="ct-btn ${active ? "active" : ""}" data-action="select-ct" data-value="${escapeHtml(cp.name)}">${escapeHtml(cp.container_name || cp.container_type || cp.name)}</button>`;
    }).join("");
}

function planningShellHtml(state) {
    const plan = state.planDoc;
    const planLabel = plan ? plan.plan_label : state.planName;
    return `
        <div class="app" id="planning-app">
            <div class="topbar">
                <div class="topbar-icon">
                    <svg viewBox="0 0 24 24"><rect x="2" y="7" width="20" height="12" rx="2"></rect><path d="M2 11h20M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                </div>
                <span class="topbar-title">Load Forecast Planner</span>
                <span class="topbar-sep">/</span>
                <span class="topbar-crumb">${escapeHtml(planLabel)}</span>
                <span class="topbar-flow-badge" id="topFlowBadge"></span>
                <div class="topbar-space"></div>
                <button class="topbar-back-btn" data-action="back-to-list">
                    <svg viewBox="0 0 24 24" width="12" height="12"><path d="M19 12H5M12 19l-7-7 7-7"></path></svg>
                    All Plans
                </button>
                <span class="status-pill" id="topStatusPill">PLANNING</span>
                <div class="deadline-wrap">
                    <span class="deadline-label">Deadline</span>
                    <input type="date" value="">
                </div>
                <button class="btn-ready" data-action="open-modal">
                    <svg viewBox="0 0 24 24"><path d="M5 12l5 5L20 7"></path></svg>
                    Move to Ready
                </button>
            </div>

            <div class="kpi-strip">
                <div class="kpi"><div class="kpi-label">Forecast Volume</div><div class="kpi-value accent" id="kpiFill"></div><div class="kpi-sub kpi-sub-cap-vol">of — m3 capacity</div></div>
                <div class="kpi"><div class="kpi-label">Fill %</div><div class="kpi-value" id="kpiPct"></div><div class="kpi-sub" id="kpiFree"></div></div>
                <div class="kpi"><div class="kpi-label">Total Weight</div><div class="kpi-value" id="kpiWeight"></div><div class="kpi-sub kpi-sub-cap-wt">of — kg max</div></div>
                <div class="kpi"><div class="kpi-label">Documents</div><div class="kpi-value teal" id="kpiDocs"></div><div class="kpi-sub" id="kpiCommitted"></div></div>
                <div class="kpi"><div class="kpi-label">Next Departure</div><div class="kpi-value" id="kpiDeparture">—</div><div class="kpi-sub">Based on plan</div></div>
            </div>

            <div class="main">
                <aside class="sidebar">
                    <div class="sb-section">
                        <div class="sb-label">Container Profile</div>
                        <div class="ct-grid"></div>
                    </div>
                    <div class="sb-section">
                        <div class="sb-label">Confidence Level</div>
                        <div class="conf-list">
                            ${confidenceRow("c1", "Committed", 0, true)}
                            ${confidenceRow("c2", "Tentative", 0, true)}
                            ${confidenceRow("c3", "Inquiry", 0, true)}
                            ${confidenceRow("c4", "Ready", 0, true)}
                        </div>
                    </div>
                    <div class="sb-section">
                        <div class="sb-label">Quick Stats</div>
                        <div class="sb-stats">
                            <div class="sb-stat-row"><span class="sb-stat-label">Remaining space</span><span class="sb-stat-val" id="sbFree"></span></div>
                            <div class="sb-stat-row"><span class="sb-stat-label">Weight used</span><span class="sb-stat-val" id="sbWeight"></span></div>
                            <div class="sb-stat-row"><span class="sb-stat-label">Queued docs</span><span class="sb-stat-val" id="sbQueued"></span></div>
                        </div>
                    </div>
                </aside>

                <div class="center" id="dropTarget">
                    <div class="card">
                        <div class="card-header">
                            <div class="card-title">
                                <svg viewBox="0 0 24 24"><rect x="2" y="7" width="20" height="12" rx="2"></rect><path d="M2 11h20"></path></svg>
                                <span class="card-title-container">Container</span>
                            </div>
                            <div class="card-meta card-meta-container"></div>
                        </div>
                        <div class="viz-body">
                            <div class="fill-legend" id="fillLegend"></div>
                            <div class="container-svg-wrap">
                                <svg id="containerSvg" width="100%" viewBox="0 0 500 90" preserveAspectRatio="none" style="display:block;border-radius:6px;overflow:hidden;"></svg>
                            </div>
                            <div class="fill-stats">
                                <div class="fill-stat"><div class="fill-stat-label">Volume loaded</div><div class="fill-stat-val warn" id="fsVol"></div></div>
                                <div class="fill-stat"><div class="fill-stat-label">Fill percentage</div><div class="fill-stat-val" id="fsPct"></div></div>
                                <div class="fill-stat"><div class="fill-stat-label">Space remaining</div><div class="fill-stat-val teal" id="fsFree"></div></div>
                            </div>
                        </div>
                    </div>

                    <div class="card" id="planItemsCard">
                        <div class="card-header">
                            <div class="card-title">
                                <svg viewBox="0 0 24 24"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"></path><rect x="9" y="3" width="6" height="4" rx="1"></rect></svg>
                                Items in Plan
                            </div>
                            <div class="items-count-badge" id="itemCount"></div>
                        </div>
                        <div style="padding:10px 14px 14px;">
                            <div id="planItemsList"></div>
                            <div class="drop-zone" id="dropZone">
                                <svg viewBox="0 0 24 24"><path d="M12 19V5M5 12l7-7 7 7"></path></svg>
                                Drag documents here or use Add to Plan
                                <div class="drop-zone-hint">Drop Sales Orders, Purchase Orders, Quotations, or Delivery Notes</div>
                            </div>
                        </div>
                    </div>
                </div>

                <aside class="source-panel">
                    <div class="sp-header">
                        <div class="sp-title">Source Queue <span class="sp-title-count" id="queueCount"></span></div>
                        <div class="type-tabs">
                            ${filterTypeButton("ALL", "All", true)}
                            ${filterTypeButton("SO", "SO")}
                            ${filterTypeButton("PO", "PO")}
                            ${filterTypeButton("QT", "QT")}
                            ${filterTypeButton("DN", "DN")}
                        </div>
                        <div class="status-toggle">
                            ${filterStatusButton("ALL", "All", true)}
                            ${filterStatusButton("DRAFT", "Draft")}
                            ${filterStatusButton("SUBMITTED", "Submitted")}
                        </div>
                    </div>
                    <div class="sp-list" id="sourceList"></div>
                </aside>
            </div>

            <div class="modal-overlay" id="modalOverlay">
                <div class="modal">
                    <div class="modal-title">
                        <svg viewBox="0 0 24 24"><path d="M9 11l3 3L22 4"></path><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>
                        Move to Ready - Create CLP
                    </div>
                    <div class="modal-desc">This will generate a Container Load Plan from all committed and ready Delivery Notes / Purchase Orders in this forecast. Draft and inquiry-only items will be excluded.</div>
                    <div class="modal-summary">
                        <div class="modal-row"><span>Container</span><strong id="mContainer"></strong></div>
                        <div class="modal-row"><span>Eligible documents</span><strong id="mDocs"></strong></div>
                        <div class="modal-row"><span>Total volume</span><strong id="mVol"></strong></div>
                        <div class="modal-row"><span>Total weight</span><strong id="mWeight"></strong></div>
                        <hr class="modal-divider">
                        <div class="modal-row"><span>Planned departure</span><strong id="mDeparture"></strong></div>
                        <div class="modal-row"><span>Deadline</span><strong id="mDeadline"></strong></div>
                    </div>
                    <div class="modal-actions">
                        <button class="btn-cancel" data-action="close-modal">Keep Planning</button>
                        <button class="btn-confirm" data-action="confirm-ready">Create Container Load Plan →</button>
                    </div>
                </div>
            </div>

            <div class="success-toast" id="toast">
                <div class="toast-icon">✓</div>
                <span id="toastMsg">CLP created successfully</span>
            </div>
        </div>
    `;
}

function bindPlanningEvents(state) {
    const root = state.root;
    root.onclick = (event) => {
        const actionNode = event.target.closest("[data-action]");
        if (!actionNode) return;

        const action = actionNode.dataset.action;
        if (action === "open-modal") openModal(state);
        if (action === "close-modal") closeModal(state);
        if (action === "confirm-ready") confirmReady(state);
        if (action === "select-ct") selectContainerProfile(state, actionNode);
        if (action === "filter-type") selectTypeFilter(state, actionNode);
        if (action === "filter-status") selectStatusFilter(state, actionNode);
        if (action === "add-to-plan") addToPlan(state, actionNode.dataset.id, actionNode.dataset.doctype);
        if (action === "remove-item") removeItem(state, actionNode.dataset.id);
        if (action === "toggle-expand") toggleExpand(state, actionNode.dataset.id);
        if (action === "back-to-list") frappe.set_route("forecast-plans");
    };

    root.onchange = (event) => {
        if (event.target.matches("input[type='checkbox'][data-action='filter-conf']")) {
            refreshPlanning(state);
        }
    };

    root.ondragstart = (event) => {
        const card = event.target.closest(".src-card[data-id]");
        if (!card || card.classList.contains("in-plan")) return;
        state.dragId = card.dataset.id;
        state.dragDoctype = card.dataset.doctype;
        if (event.dataTransfer) event.dataTransfer.effectAllowed = "copy";
    };

    const dropZone = root.querySelector("#dropZone");
    dropZone.ondragover = (event) => {
        event.preventDefault();
        dropZone.classList.add("drag-over");
    };
    dropZone.ondragleave = () => dropZone.classList.remove("drag-over");
    dropZone.ondrop = (event) => {
        event.preventDefault();
        dropZone.classList.remove("drag-over");
        if (state.dragId) {
            addToPlan(state, state.dragId, state.dragDoctype);
            state.dragId = null;
            state.dragDoctype = null;
        }
    };
}

function refreshPlanning(state) {
    renderContainerSvg(state);
    renderLegend(state);
    renderKpis(state);
    renderPlanItems(state);
    renderSourceQueue(state);
    updateConfidenceCounts(state);
}

function renderContainerSvg(state) {
    const cap = getCapacity(state);
    const totals = getTotals(state.planItems, cap);
    const fillRatio = Math.min(totals.vol / cap.maxVol, 1);
    const svgWidth = 500;
    const innerWidth = svgWidth - 50;
    const fillWidth = Math.round(innerWidth * fillRatio);
    let svg = "";
    let x = 0;

    state.planItems.forEach((item) => {
        const width = Math.max(Math.round(innerWidth * item.volume / cap.maxVol), 2);
        const color = PLANNING_COLORS[item.type] || "#999";
        svg += `<rect x="${x}" y="0" width="${width}" height="90" fill="${color}" opacity="0.75"></rect>`;
        if (width > 30) {
            const shortId = item.id.split("-").slice(-1)[0];
            svg += `<text x="${x + width / 2}" y="32" text-anchor="middle" font-size="9" fill="white" font-family="DM Mono, monospace" font-weight="500">${escapeHtml(shortId)}</text>`;
            svg += `<text x="${x + width / 2}" y="46" text-anchor="middle" font-size="9" fill="rgba(255,255,255,0.75)" font-family="DM Mono, monospace">${item.volume.toFixed(1)}m3</text>`;
        }
        x += width;
    });

    if (fillWidth < innerWidth) {
        svg += `<rect x="${x}" y="0" width="${innerWidth - x}" height="90" fill="#F4F3F0"></rect>`;
        svg += `<text x="${x + (innerWidth - x) / 2}" y="50" text-anchor="middle" font-size="11" fill="#C0BFB8" font-family="Outfit, sans-serif">Empty ${(100 - fillRatio * 100).toFixed(1)}%</text>`;
    }

    for (let rib = 60; rib < innerWidth; rib += 55) {
        svg += `<line x1="${rib}" y1="0" x2="${rib}" y2="90" stroke="rgba(0,0,0,0.07)" stroke-width="1"></line>`;
    }

    svg += `<rect x="${innerWidth}" y="0" width="50" height="90" fill="#E8E6E0"></rect>`;
    svg += `<line x1="${innerWidth + 25}" y1="0" x2="${innerWidth + 25}" y2="90" stroke="#C8C6C0" stroke-width="1"></line>`;
    svg += `<circle cx="${innerWidth + 12}" cy="45" r="4" fill="none" stroke="#B0AEA8" stroke-width="1.5"></circle>`;
    svg += `<circle cx="${innerWidth + 38}" cy="45" r="4" fill="none" stroke="#B0AEA8" stroke-width="1.5"></circle>`;
    svg += `<rect x="0" y="0" width="${svgWidth}" height="90" fill="none" stroke="#C8C6C0" stroke-width="1.5" rx="4"></rect>`;

    state.root.querySelector("#containerSvg").innerHTML = svg;
}

function renderLegend(state) {
    const html = state.planItems.map((item) => `
        <div class="fill-legend-item"><div class="fill-dot" style="background:${PLANNING_COLORS[item.type] || "#999"}"></div><span>${escapeHtml(item.id)} · ${item.volume.toFixed(1)} m3</span></div>
    `).join("") + `<div class="fill-legend-item"><div class="fill-dot" style="background:#E8E6E0;border:1px solid #C8C6C0"></div><span>Empty space</span></div>`;
    state.root.querySelector("#fillLegend").innerHTML = html;
}

function renderKpis(state) {
    const cap = getCapacity(state);
    const totals = getTotals(state.planItems, cap);
    const committedCount = state.planItems.filter((item) => item.confidence === "committed" || item.confidence === "ready").length;
    const lineTotal = state.planItems.reduce((sum, item) => sum + (item.lineItems || []).length, 0);

    setText(state, "#kpiFill", `${totals.vol.toFixed(1)} m3`);
    setText(state, "#kpiPct", `${totals.pct.toFixed(1)}%`);
    setText(state, "#kpiFree", `${totals.free.toFixed(1)} m3 free`);
    setText(state, "#kpiWeight", `${totals.wt.toLocaleString()} kg`);
    setText(state, "#kpiDocs", String(state.planItems.length));
    setText(state, "#kpiCommitted", `${committedCount} committed`);
    if (state.planDoc && state.planDoc.departure_date) {
        setText(state, "#kpiDeparture", state.planDoc.departure_date);
    }
    setText(state, "#fsVol", `${totals.vol.toFixed(1)} m3`);
    setText(state, "#fsPct", `${totals.pct.toFixed(1)}%`);
    setText(state, "#fsFree", `${totals.free.toFixed(1)} m3`);
    setText(state, "#sbFree", `${totals.free.toFixed(1)} m3`);
    setText(state, "#sbWeight", `${((totals.wt / cap.maxKg) * 100).toFixed(1)}%`);
    setText(state, "#sbQueued", `${state.sourceQueue.length} docs`);
    setText(state, "#itemCount", `${state.planItems.length} documents · ${lineTotal} line items`);

    // Modal summary
    const eligible = state.planItems.filter((item) =>
        (item.confidence === "committed" || item.confidence === "ready")
        && (item.source_doctype === "Delivery Note" || item.source_doctype === "Purchase Order" || !item.source_doctype)
    );
    const eligibleVol = eligible.reduce((s, i) => s + i.volume, 0);
    const eligibleWt = eligible.reduce((s, i) => s + i.weight, 0);
    setText(state, "#mDocs", `${eligible.length} committed/ready`);
    setText(state, "#mVol", `${eligibleVol.toFixed(1)} m3 (${cap.maxVol > 0 ? (eligibleVol / cap.maxVol * 100).toFixed(1) : 0}%)`);
    setText(state, "#mWeight", `${eligibleWt.toLocaleString()} kg`);
    setText(state, "#mContainer", state.container ? (state.container.container_name || state.container.name) : "—");
    setText(state, "#mDeparture", state.planDoc ? (state.planDoc.departure_date || "—") : "—");
    setText(state, "#mDeadline", state.planDoc ? (state.planDoc.deadline || "—") : "—");

    const pill = state.root.querySelector("#topStatusPill");
    if (pill) {
        pill.textContent = state.ready ? "READY" : "PLANNING";
        pill.classList.toggle("ready", state.ready);
    }
}

function updateTypeTabs(state) {
    const abbrMap = { "Quotation": "QT", "Sales Order": "SO", "Purchase Order": "PO", "Delivery Note": "DN" };
    const allowedAbbrs = new Set((state.allowedDoctypes || []).map((dt) => abbrMap[dt] || ""));

    state.root.querySelectorAll(".type-tabs .tt").forEach((btn) => {
        const val = btn.dataset.value;
        if (val === "ALL") return; // always show All
        if (allowedAbbrs.size && !allowedAbbrs.has(val)) {
            btn.style.display = "none";
        } else {
            btn.style.display = "";
        }
    });

    // If current filter hidden, reset to ALL
    if (state.currentTypeFilter !== "ALL" && allowedAbbrs.size && !allowedAbbrs.has(state.currentTypeFilter)) {
        state.currentTypeFilter = "ALL";
        state.root.querySelectorAll(".type-tabs .tt").forEach((b) => b.classList.remove("active"));
        const allBtn = state.root.querySelector('.type-tabs .tt[data-value="ALL"]');
        if (allBtn) allBtn.classList.add("active");
    }
}

function updateConfidenceCounts(state) {
    const all = state.planItems.concat(state.sourceQueue);
    const counts = { committed: 0, tentative: 0, inquiry: 0, ready: 0 };
    all.forEach((item) => { if (counts.hasOwnProperty(item.confidence)) counts[item.confidence]++; });

    const confList = state.root.querySelector(".conf-list");
    if (!confList) return;
    const cnts = confList.querySelectorAll(".conf-cnt");
    if (cnts[0]) cnts[0].textContent = counts.committed;
    if (cnts[1]) cnts[1].textContent = counts.tentative;
    if (cnts[2]) cnts[2].textContent = counts.inquiry;
    if (cnts[3]) cnts[3].textContent = counts.ready;
}

function renderPlanItems(state) {
    const list = state.root.querySelector("#planItemsList");
    if (!state.planItems.length) {
        list.innerHTML = "";
        return;
    }
    list.innerHTML = state.planItems.map((item) => {
        const conf = PLANNING_CONFIDENCE[item.confidence] || PLANNING_CONFIDENCE.inquiry;
        const expanded = state.expandedItem === item.id;
        const rows = (item.lineItems || []).map((line) => `
            <tr>
                <td class="mono">${escapeHtml(line.code)}</td>
                <td>${escapeHtml(line.desc)}</td>
                <td class="muted" style="text-align:right">${line.qty}</td>
                <td class="mono" style="text-align:right">${(line.vol || 0).toFixed(3)}</td>
                <td class="mono" style="text-align:right">${(line.wt || 0).toFixed(1)}</td>
            </tr>
        `).join("");

        return `
            <div class="plan-item ${expanded ? "expanded" : ""}" data-action="toggle-expand" data-id="${escapeHtml(item.id)}">
                <div class="item-bar" style="background:${PLANNING_COLORS[item.type] || "#999"}"></div>
                <div class="item-info">
                    <div class="item-docnum">${escapeHtml(item.id)}</div>
                    <div class="item-party">${escapeHtml(item.party)}</div>
                </div>
                <span class="item-conf-badge" style="background:${conf.bg};color:${conf.text}">${escapeHtml(item.confidence)}</span>
                <div class="item-vol"><div class="item-vol-num">${item.volume.toFixed(1)}</div><div class="item-vol-unit">m3</div></div>
                <div class="item-expand-icon"><svg viewBox="0 0 24 24"><polyline points="9 18 15 12 9 6"></polyline></svg></div>
                <button class="item-remove" data-action="remove-item" data-id="${escapeHtml(item.id)}">×</button>
            </div>
            <div class="item-detail-panel ${expanded ? "show" : ""}" id="detail-${escapeHtml(item.id)}">
                <div class="detail-header">
                    <div class="detail-title">${escapeHtml(item.id)} — ${escapeHtml(item.party)}</div>
                </div>
                <table class="detail-table">
                    <thead><tr><th>Code</th><th>Description</th><th style="text-align:right">Qty</th><th style="text-align:right">Vol m3</th><th style="text-align:right">Wt kg</th></tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        `;
    }).join("");
}

function renderSourceQueue(state) {
    const planIds = new Set(state.planItems.map((item) => item.id));
    const filtered = state.sourceQueue.filter((doc) => {
        if (state.currentTypeFilter !== "ALL" && doc.type !== state.currentTypeFilter) return false;
        if (state.currentStatusFilter === "DRAFT" && doc.docstatus !== "Draft") return false;
        if (state.currentStatusFilter === "SUBMITTED" && doc.docstatus !== "Submitted") return false;
        return true;
    });

    setText(state, "#queueCount", `${filtered.length} documents`);

    state.root.querySelector("#sourceList").innerHTML = filtered.map((doc) => {
        const inPlan = planIds.has(doc.id);
        const conf = PLANNING_CONFIDENCE[doc.confidence] || PLANNING_CONFIDENCE.inquiry;

        return `
            <div class="src-card ${inPlan ? "in-plan" : ""}" draggable="true" data-id="${escapeHtml(doc.id)}" data-doctype="${escapeHtml(doc.source_doctype || "")}">
                <div class="drag-hint"><span></span><span></span><span></span></div>
                <div class="src-card-top">
                    <span class="src-docnum">${escapeHtml(doc.id)}</span>
                    <span class="src-type-badge badge-${escapeHtml(doc.type)}">${escapeHtml(doc.type)}</span>
                </div>
                <div class="src-party">${escapeHtml(doc.party)}</div>
                <div class="src-metrics">
                    <div class="src-metric"><strong>${(doc.volume || 0).toFixed(1)}</strong> m3</div>
                    <div class="src-metric"><strong>${Math.round(doc.weight || 0).toLocaleString()}</strong> kg</div>
                    <div class="src-metric"><strong>${doc.itemCount || 0}</strong> items</div>
                </div>
                <div class="src-footer">
                    <span class="item-conf-badge" style="background:${conf.bg};color:${conf.text};padding:2px 7px;border-radius:20px;font-size:9.5px;font-weight:500">${escapeHtml(doc.confidence)}</span>
                    <span class="src-date">${escapeHtml(doc.docstatus)} · ${escapeHtml(doc.date)}</span>
                </div>
                <button class="btn-add-plan" data-action="add-to-plan" data-id="${escapeHtml(doc.id)}" data-doctype="${escapeHtml(doc.source_doctype || "")}">
                    <svg viewBox="0 0 24 24" width="12" height="12"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                    Add to Plan
                </button>
            </div>
        `;
    }).join("");
}

// ---------------------------------------------------------------------------
// Actions: add / remove / convert — all call backend
// ---------------------------------------------------------------------------

function addToPlan(state, id, sourceDoctype) {
    if (!id || state.planItems.some((item) => item.id === id)) return;

    // Resolve source_doctype from queue if not passed
    if (!sourceDoctype) {
        const queueItem = state.sourceQueue.find((d) => d.id === id);
        if (queueItem) sourceDoctype = queueItem.source_doctype;
    }
    if (!sourceDoctype) {
        // Infer from prefix
        if (id.startsWith("SAL-QTN") || id.startsWith("QTN")) sourceDoctype = "Quotation";
        else if (id.startsWith("SAL-ORD") || id.startsWith("SO-")) sourceDoctype = "Sales Order";
        else if (id.startsWith("PUR-ORD") || id.startsWith("PO-")) sourceDoctype = "Purchase Order";
        else if (id.startsWith("MAT-DN") || id.startsWith("DN-")) sourceDoctype = "Delivery Note";
    }

    frappe.call({
        method: "orderlift.orderlift_logistics.services.forecast_planning.add_item_to_plan",
        args: { plan_name: state.planName, source_doctype: sourceDoctype, source_name: id },
        async: true,
        freeze: true,
        freeze_message: __("Adding to plan..."),
        callback: (r) => {
            applyPlanDetail(state, r.message);
            refreshPlanning(state);
        },
        error: () => {
            frappe.show_alert({ message: __("Could not add to plan"), indicator: "red" });
        },
    });
}

function removeItem(state, id) {
    frappe.call({
        method: "orderlift.orderlift_logistics.services.forecast_planning.remove_item_from_plan",
        args: { plan_name: state.planName, source_name: id },
        async: true,
        freeze: true,
        freeze_message: __("Removing..."),
        callback: (r) => {
            if (state.expandedItem === id) state.expandedItem = null;
            applyPlanDetail(state, r.message);
            refreshPlanning(state);
        },
    });
}

function applyPlanDetail(state, plan) {
    if (!plan) return;
    state.planDoc = plan;
    state.container = plan.container;
    state.planItems = (plan.items || []).map((item) => {
        const cfg_abbr = { "Quotation": "QT", "Sales Order": "SO", "Purchase Order": "PO", "Delivery Note": "DN" };
        return {
            id: item.id,
            row_name: item.row_name,
            source_doctype: item.source_doctype,
            type: item.type || cfg_abbr[item.source_doctype] || "??",
            party: item.party,
            party_type: item.party_type,
            volume: item.volume,
            weight: item.weight,
            confidence: item.confidence,
            date: item.date,
            docstatus: item.docstatus_label,
            itemCount: item.item_count,
            selected: item.selected,
            lineItems: (item.line_items || []).map((li) => ({
                code: li.item_code,
                desc: li.item_name || li.item_code,
                qty: li.qty,
                vol: li.line_volume_m3,
                wt: li.line_weight_kg,
            })),
        };
    });
    updateTopbar(state);
}

function selectContainerProfile(state, node) {
    const profileName = node.dataset.value;
    setActive(state.root, ".ct-btn", node);

    // Update forecast plan container_profile via backend
    frappe.call({
        method: "frappe.client.set_value",
        args: { doctype: "Forecast Load Plan", name: state.planName, fieldname: "container_profile", value: profileName },
        async: true,
        callback: () => {
            // Reload plan to get updated container capacity
            loadPlanData(state);
        },
    });
}

function selectTypeFilter(state, node) {
    state.currentTypeFilter = node.dataset.value;
    setActive(state.root, ".tt", node);
    renderSourceQueue(state);
}

function selectStatusFilter(state, node) {
    state.currentStatusFilter = node.dataset.value;
    setActive(state.root, ".st", node);
    renderSourceQueue(state);
}

function toggleExpand(state, id) {
    state.expandedItem = state.expandedItem === id ? null : id;
    renderPlanItems(state);
}

function openModal(state) {
    renderKpis(state); // Refresh modal numbers
    state.root.querySelector("#modalOverlay").classList.add("show");
}

function closeModal(state) {
    state.root.querySelector("#modalOverlay").classList.remove("show");
}

function confirmReady(state) {
    closeModal(state);
    frappe.call({
        method: "orderlift.orderlift_logistics.services.forecast_planning.convert_to_clp",
        args: { plan_name: state.planName },
        async: true,
        freeze: true,
        freeze_message: __("Creating Container Load Plan..."),
        callback: (r) => {
            const result = r.message;
            state.ready = true;
            renderKpis(state);

            const toast = state.root.querySelector("#toast");
            const toastMsg = state.root.querySelector("#toastMsg");
            if (toastMsg) toastMsg.textContent = `${result.clp_name} created successfully — status moved to Converted`;
            toast.classList.add("show");
            window.setTimeout(() => toast.classList.remove("show"), 4500);
        },
        error: () => {
            frappe.show_alert({ message: __("Conversion failed — check eligible documents"), indicator: "red" });
        },
    });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getTotals(planItems, cap) {
    if (!cap) cap = { maxVol: 67.7, maxKg: 26000 };
    const vol = planItems.reduce((sum, item) => sum + (item.volume || 0), 0);
    const wt = planItems.reduce((sum, item) => sum + (item.weight || 0), 0);
    return {
        vol,
        wt,
        pct: cap.maxVol > 0 ? (vol / cap.maxVol) * 100 : 0,
        free: cap.maxVol - vol,
    };
}

function setActive(root, selector, activeNode) {
    root.querySelectorAll(selector).forEach((node) => node.classList.remove("active"));
    activeNode.classList.add("active");
}

function setText(state, selector, value) {
    const node = state.root.querySelector(selector);
    if (node) node.textContent = value;
}

function confidenceRow(id, label, count, checked) {
    return `<div class="conf-row"><input type="checkbox" id="${id}" data-action="filter-conf" ${checked ? "checked" : ""}><label for="${id}">${label}</label><span class="conf-cnt">${count}</span></div>`;
}

function filterTypeButton(value, label, active) {
    return `<button class="tt ${active ? "active" : ""}" data-action="filter-type" data-value="${value}">${label}</button>`;
}

function filterStatusButton(value, label, active) {
    return `<button class="st ${active ? "active" : ""}" data-action="filter-status" data-value="${value}">${label}</button>`;
}

function ensurePlanningFonts() {
    if (document.getElementById("planning-font-outfit")) return;
    const link = document.createElement("link");
    link.id = "planning-font-outfit";
    link.rel = "stylesheet";
    link.href = "https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600&family=DM+Mono:wght@400;500&display=swap";
    document.head.appendChild(link);
}

function injectPlanningStyles() {
    if (document.getElementById("orderlift-planning-native-style")) return;

    const style = document.createElement("style");
    style.id = "orderlift-planning-native-style";
    style.textContent = `
        .planning-native-root {
          --bg: #F4F3F0;
          --surface: #FFFFFF;
          --sidebar-bg: #17181C;
          --accent: #C17F24;
          --accent-lt: #FDE8BE;
          --teal: #0D6B50;
          --teal-lt: #D8F2EA;
          --blue: #1A5FA3;
          --blue-lt: #E0EFFC;
          --red: #A02C2C;
          --red-lt: #FBEAEA;
          --gray-lt: #EEECEA;
          --border: rgba(0,0,0,0.09);
          --border-md: rgba(0,0,0,0.15);
          --text: #1A1A1E;
          --muted: #6B6A70;
          --hint: #A0A0A8;
          --r: 8px;
          --r-lg: 12px;
          --font: 'Outfit', sans-serif;
          --mono: 'DM Mono', monospace;
          height: calc(100vh - 88px);
          min-height: calc(100vh - 88px);
          overflow: hidden;
          background: var(--bg);
          font-family: var(--font);
          color: var(--text);
        }
        .planning-native-root *{box-sizing:border-box;margin:0;padding:0;}
        .planning-native-root button{font-family:var(--font);cursor:pointer;}
        .planning-native-root input{font-family:var(--font);}
        .planning-native-root ::-webkit-scrollbar{width:4px;height:4px;}
        .planning-native-root ::-webkit-scrollbar-track{background:transparent;}
        .planning-native-root ::-webkit-scrollbar-thumb{background:rgba(0,0,0,0.14);border-radius:4px;}
        .planning-native-root .app{display:flex;flex-direction:column;height:100%;overflow:hidden;position:relative;}
        .planning-native-root .topbar{height:50px;background:var(--surface);border-bottom:0.5px solid var(--border-md);display:flex;align-items:center;padding:0 18px;gap:14px;flex-shrink:0;z-index:10;}
        .planning-native-root .topbar-icon{width:30px;height:30px;background:var(--accent);border-radius:7px;display:flex;align-items:center;justify-content:center;flex-shrink:0;}
        .planning-native-root .topbar-icon svg{width:16px;height:16px;fill:none;stroke:white;stroke-width:2;}
        .planning-native-root .topbar-title{font-size:14px;font-weight:600;color:var(--text);}
        .planning-native-root .topbar-sep{color:var(--hint);font-size:12px;}
        .planning-native-root .topbar-crumb{font-size:12px;color:var(--muted);}
        .planning-native-root .topbar-flow-badge{padding:2px 8px;border-radius:20px;font-size:10px;font-weight:600;letter-spacing:.3px;display:none;}
        .planning-native-root .topbar-space{flex:1;}
        .planning-native-root .topbar-back-btn{padding:5px 12px;border-radius:var(--r);border:0.5px solid var(--border);background:transparent;font-size:11px;color:var(--muted);display:flex;align-items:center;gap:5px;transition:all .13s;}
        .planning-native-root .topbar-back-btn:hover{background:var(--bg);color:var(--text);}
        .planning-native-root .topbar-back-btn svg{stroke:currentColor;fill:none;stroke-width:2;}
        .planning-native-root .status-pill{padding:3px 10px;border-radius:20px;font-size:11px;font-weight:500;background:var(--accent-lt);color:var(--accent);}
        .planning-native-root .status-pill.ready{background:var(--teal-lt);color:var(--teal);}
        .planning-native-root .deadline-wrap{display:flex;align-items:center;gap:7px;background:var(--bg);border:0.5px solid var(--border-md);border-radius:var(--r);padding:5px 11px;}
        .planning-native-root .deadline-label{font-size:10px;font-weight:600;color:var(--hint);text-transform:uppercase;letter-spacing:.5px;}
        .planning-native-root .deadline-wrap input[type=date]{border:none;background:transparent;font-family:var(--mono);font-size:12px;color:var(--text);outline:none;cursor:pointer;}
        .planning-native-root .btn-ready{padding:7px 15px;background:var(--teal);color:white;border:none;border-radius:var(--r);font-size:12px;font-weight:500;display:flex;align-items:center;gap:5px;transition:opacity .15s;}
        .planning-native-root .btn-ready:hover{opacity:.84;}
        .planning-native-root .btn-ready svg{width:13px;height:13px;stroke:white;fill:none;stroke-width:2;}
        .planning-native-root .kpi-strip{display:grid;grid-template-columns:repeat(5,1fr);background:var(--surface);border-bottom:0.5px solid var(--border-md);flex-shrink:0;}
        .planning-native-root .kpi{padding:9px 18px;border-right:0.5px solid var(--border);}
        .planning-native-root .kpi:last-child{border-right:none;}
        .planning-native-root .kpi-label{font-size:9.5px;font-weight:600;color:var(--hint);text-transform:uppercase;letter-spacing:.6px;margin-bottom:2px;}
        .planning-native-root .kpi-value{font-size:18px;font-weight:600;line-height:1.2;color:var(--text);}
        .planning-native-root .kpi-value.accent{color:var(--accent);}
        .planning-native-root .kpi-value.teal{color:var(--teal);}
        .planning-native-root .kpi-sub{font-size:10px;color:var(--hint);margin-top:1px;}
        .planning-native-root .main{display:grid;grid-template-columns:210px 1fr 310px;height:calc(100% - 50px - 52px);overflow:hidden;}
        .planning-native-root .sidebar{background:var(--sidebar-bg);overflow-y:auto;padding:14px 0;}
        .planning-native-root .sb-section{padding:0 13px 14px;border-bottom:0.5px solid rgba(255,255,255,.06);}
        .planning-native-root .sb-section:last-child{border-bottom:none;}
        .planning-native-root .sb-label{font-size:9.5px;font-weight:600;color:rgba(255,255,255,.28);text-transform:uppercase;letter-spacing:.7px;margin-bottom:8px;padding-top:10px;}
        .planning-native-root .ct-grid{display:grid;grid-template-columns:1fr 1fr;gap:5px;}
        .planning-native-root .ct-btn{padding:7px 4px;border-radius:var(--r);border:0.5px solid rgba(255,255,255,.1);background:transparent;color:rgba(255,255,255,.45);font-size:11px;font-weight:500;transition:all .15s;text-align:center;}
        .planning-native-root .ct-btn:hover{background:rgba(255,255,255,.06);color:rgba(255,255,255,.75);}
        .planning-native-root .ct-btn.active{background:var(--accent);border-color:var(--accent);color:white;}
        .planning-native-root .flow-list{display:flex;flex-direction:column;gap:3px;}
        .planning-native-root .flow-btn{display:flex;align-items:center;gap:8px;padding:6px 9px;border-radius:var(--r);border:none;background:transparent;color:rgba(255,255,255,.45);font-size:12px;transition:all .15s;text-align:left;}
        .planning-native-root .flow-btn:hover{background:rgba(255,255,255,.05);color:rgba(255,255,255,.75);}
        .planning-native-root .flow-btn.active{background:rgba(255,255,255,.1);color:white;}
        .planning-native-root .flow-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;}
        .planning-native-root .conf-list{display:flex;flex-direction:column;gap:5px;}
        .planning-native-root .conf-row{display:flex;align-items:center;gap:7px;padding:4px 7px;border-radius:6px;cursor:pointer;transition:background .12s;}
        .planning-native-root .conf-row:hover{background:rgba(255,255,255,.05);}
        .planning-native-root .conf-row input[type=checkbox]{width:13px;height:13px;accent-color:var(--accent);cursor:pointer;flex-shrink:0;}
        .planning-native-root .conf-row label{font-size:11.5px;color:rgba(255,255,255,.55);cursor:pointer;flex:1;}
        .planning-native-root .conf-cnt{font-size:9.5px;font-family:var(--mono);color:rgba(255,255,255,.25);background:rgba(255,255,255,.07);padding:1px 5px;border-radius:4px;}
        .planning-native-root .sb-stats{display:flex;flex-direction:column;gap:6px;margin-top:4px;}
        .planning-native-root .sb-stat-row{display:flex;justify-content:space-between;align-items:center;padding:5px 8px;background:rgba(255,255,255,.04);border-radius:6px;}
        .planning-native-root .sb-stat-label{font-size:10.5px;color:rgba(255,255,255,.35);}
        .planning-native-root .sb-stat-val{font-size:11px;font-family:var(--mono);font-weight:500;color:rgba(255,255,255,.65);}
        .planning-native-root .center{overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:12px;}
        .planning-native-root .card{background:var(--surface);border:0.5px solid var(--border-md);border-radius:var(--r-lg);}
        .planning-native-root .card-header{padding:11px 15px;border-bottom:0.5px solid var(--border);display:flex;align-items:center;justify-content:space-between;}
        .planning-native-root .card-title{font-size:12.5px;font-weight:600;display:flex;align-items:center;gap:7px;}
        .planning-native-root .card-title svg{width:14px;height:14px;stroke:var(--muted);fill:none;stroke-width:2;}
        .planning-native-root .card-meta{display:flex;gap:14px;font-size:11px;color:var(--muted);}
        .planning-native-root .card-meta strong{color:var(--text);}
        .planning-native-root .viz-body{padding:15px;}
        .planning-native-root .fill-legend{display:flex;gap:14px;margin-bottom:10px;flex-wrap:wrap;}
        .planning-native-root .fill-legend-item{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--muted);}
        .planning-native-root .fill-dot{width:9px;height:9px;border-radius:2px;flex-shrink:0;}
        .planning-native-root .container-svg-wrap{width:100%;margin-bottom:12px;}
        .planning-native-root .fill-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:14px;}
        .planning-native-root .fill-stat{background:var(--bg);border-radius:var(--r);padding:9px 12px;}
        .planning-native-root .fill-stat-label{font-size:10px;color:var(--hint);margin-bottom:2px;}
        .planning-native-root .fill-stat-val{font-size:16px;font-weight:600;color:var(--text);}
        .planning-native-root .fill-stat-val.warn{color:var(--accent);}
        .planning-native-root .fill-stat-val.teal{color:var(--teal);}
        .planning-native-root .items-count-badge{font-size:10px;font-family:var(--mono);background:var(--bg);border:0.5px solid var(--border-md);padding:2px 7px;border-radius:20px;color:var(--muted);}
        .planning-native-root .plan-item{display:flex;align-items:center;gap:9px;padding:8px 10px;border:0.5px solid var(--border);border-radius:var(--r);margin-bottom:6px;background:var(--bg);cursor:pointer;transition:all .14s;}
        .planning-native-root .plan-item:hover{border-color:var(--border-md);background:white;transform:translateX(2px);}
        .planning-native-root .plan-item.expanded{border-color:var(--border-md);background:white;}
        .planning-native-root .item-bar{width:3px;height:34px;border-radius:2px;flex-shrink:0;}
        .planning-native-root .item-info{flex:1;min-width:0;}
        .planning-native-root .item-docnum{font-family:var(--mono);font-size:11px;font-weight:500;color:var(--text);}
        .planning-native-root .item-party{font-size:11px;color:var(--muted);margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
        .planning-native-root .item-conf-badge{padding:2px 7px;border-radius:20px;font-size:9.5px;font-weight:500;flex-shrink:0;}
        .planning-native-root .item-vol{text-align:right;flex-shrink:0;min-width:56px;}
        .planning-native-root .item-vol-num{font-family:var(--mono);font-size:12px;font-weight:500;color:var(--text);}
        .planning-native-root .item-vol-unit{font-size:9.5px;color:var(--hint);}
        .planning-native-root .item-remove{width:20px;height:20px;border-radius:50%;border:0.5px solid var(--border);background:transparent;display:flex;align-items:center;justify-content:center;font-size:13px;color:var(--hint);transition:all .13s;flex-shrink:0;line-height:1;}
        .planning-native-root .item-remove:hover{background:var(--red-lt);border-color:rgba(160,44,44,.3);color:var(--red);}
        .planning-native-root .item-expand-icon{width:16px;height:16px;color:var(--hint);transition:transform .2s;flex-shrink:0;display:flex;align-items:center;justify-content:center;}
        .planning-native-root .item-expand-icon svg{width:12px;height:12px;stroke:currentColor;fill:none;stroke-width:2;}
        .planning-native-root .plan-item.expanded .item-expand-icon{transform:rotate(90deg);}
        .planning-native-root .item-detail-panel{background:white;border:0.5px solid var(--border-md);border-radius:var(--r);overflow:hidden;margin-top:-4px;margin-bottom:6px;display:none;}
        .planning-native-root .item-detail-panel.show{display:block;}
        .planning-native-root .detail-header{padding:10px 14px 8px;border-bottom:0.5px solid var(--border);display:flex;align-items:center;justify-content:space-between;}
        .planning-native-root .detail-title{font-size:12px;font-weight:600;}
        .planning-native-root .detail-table{width:100%;border-collapse:collapse;font-size:11.5px;}
        .planning-native-root .detail-table th{padding:5px 12px;text-align:left;font-size:9.5px;font-weight:600;color:var(--hint);text-transform:uppercase;letter-spacing:.4px;border-bottom:0.5px solid var(--border);}
        .planning-native-root .detail-table td{padding:7px 12px;border-bottom:0.5px solid rgba(0,0,0,.04);color:var(--text);}
        .planning-native-root .detail-table tr:last-child td{border-bottom:none;}
        .planning-native-root .detail-table .mono{font-family:var(--mono);font-size:11px;}
        .planning-native-root .detail-table .muted{color:var(--muted);}
        .planning-native-root .drop-zone{border:1.5px dashed var(--border-md);border-radius:var(--r-lg);padding:22px;text-align:center;color:var(--hint);font-size:12.5px;transition:all .15s;display:flex;flex-direction:column;align-items:center;gap:7px;}
        .planning-native-root .drop-zone svg{width:24px;height:24px;stroke:var(--hint);fill:none;stroke-width:1.5;}
        .planning-native-root .drop-zone.drag-over{border-color:var(--accent);background:var(--accent-lt);color:var(--accent);}
        .planning-native-root .drop-zone.drag-over svg{stroke:var(--accent);}
        .planning-native-root .drop-zone-hint{font-size:11px;color:var(--hint);}
        .planning-native-root .source-panel{background:var(--surface);border-left:0.5px solid var(--border-md);display:flex;flex-direction:column;overflow:hidden;}
        .planning-native-root .sp-header{padding:11px 12px 9px;border-bottom:0.5px solid var(--border);flex-shrink:0;}
        .planning-native-root .sp-title{font-size:13px;font-weight:600;margin-bottom:9px;display:flex;align-items:center;justify-content:space-between;}
        .planning-native-root .sp-title-count{font-size:10px;font-family:var(--mono);color:var(--hint);font-weight:400;}
        .planning-native-root .type-tabs{display:flex;gap:3px;background:var(--bg);padding:3px;border-radius:var(--r);margin-bottom:8px;}
        .planning-native-root .tt{flex:1;padding:4px 5px;border-radius:5px;border:none;background:transparent;font-family:var(--font);font-size:11px;font-weight:500;color:var(--muted);transition:all .13s;text-align:center;}
        .planning-native-root .tt.active{background:var(--surface);color:var(--text);box-shadow:0 1px 3px rgba(0,0,0,.08);}
        .planning-native-root .status-toggle{display:flex;gap:4px;}
        .planning-native-root .st{padding:4px 11px;border-radius:20px;border:0.5px solid var(--border);background:transparent;font-family:var(--font);font-size:11px;color:var(--muted);transition:all .13s;}
        .planning-native-root .st.active{background:var(--text);color:white;border-color:var(--text);}
        .planning-native-root .sp-list{flex:1;overflow-y:auto;padding:9px 10px;}
        .planning-native-root .src-card{border:0.5px solid var(--border);border-radius:var(--r-lg);padding:10px 11px;margin-bottom:7px;cursor:grab;transition:all .15s;background:var(--surface);position:relative;}
        .planning-native-root .src-card:hover{border-color:var(--border-md);transform:translateY(-1px);box-shadow:0 2px 7px rgba(0,0,0,.06);}
        .planning-native-root .src-card:active{cursor:grabbing;transform:scale(.98);}
        .planning-native-root .src-card.in-plan{opacity:.38;pointer-events:none;}
        .planning-native-root .src-card-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:5px;}
        .planning-native-root .src-docnum{font-family:var(--mono);font-size:11px;font-weight:500;color:var(--text);}
        .planning-native-root .src-type-badge{padding:2px 6px;border-radius:4px;font-size:9.5px;font-weight:600;letter-spacing:.2px;}
        .planning-native-root .badge-SO{background:var(--blue-lt);color:var(--blue);}
        .planning-native-root .badge-PO{background:#EAF3DE;color:#3B6D11;}
        .planning-native-root .badge-QT{background:var(--accent-lt);color:#854F0B;}
        .planning-native-root .badge-DN{background:var(--teal-lt);color:var(--teal);}
        .planning-native-root .src-party{font-size:12px;font-weight:500;color:var(--text);margin-bottom:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
        .planning-native-root .src-metrics{display:flex;gap:14px;margin-bottom:7px;}
        .planning-native-root .src-metric{font-size:11px;color:var(--muted);}
        .planning-native-root .src-metric strong{font-weight:600;color:var(--text);}
        .planning-native-root .src-footer{display:flex;align-items:center;justify-content:space-between;}
        .planning-native-root .src-date{font-size:10px;color:var(--hint);font-family:var(--mono);}
        .planning-native-root .drag-hint{position:absolute;top:10px;right:11px;opacity:.3;display:flex;flex-direction:column;gap:2px;}
        .planning-native-root .drag-hint span{display:block;width:13px;height:1.5px;background:var(--muted);border-radius:2px;}
        .planning-native-root .btn-add-plan{width:100%;margin-top:8px;padding:6px 10px;border-radius:var(--r);border:0.5px solid var(--border);background:var(--bg);font-size:11px;font-weight:500;color:var(--muted);display:flex;align-items:center;justify-content:center;gap:5px;transition:all .14s;}
        .planning-native-root .btn-add-plan:hover{background:var(--accent);border-color:var(--accent);color:white;}
        .planning-native-root .btn-add-plan svg{width:12px;height:12px;stroke:currentColor;fill:none;stroke-width:2.5;}
        .planning-native-root .conf-committed{background:var(--teal-lt);color:var(--teal);}
        .planning-native-root .conf-tentative{background:var(--accent-lt);color:#854F0B;}
        .planning-native-root .conf-inquiry{background:var(--gray-lt);color:#5F5E5A;}
        .planning-native-root .conf-ready{background:var(--blue-lt);color:var(--blue);}
        .planning-native-root .modal-overlay{display:none;position:absolute;inset:0;background:rgba(0,0,0,.45);z-index:200;align-items:center;justify-content:center;}
        .planning-native-root .modal-overlay.show{display:flex;}
        .planning-native-root .modal{background:var(--surface);border-radius:var(--r-lg);padding:24px;width:400px;border:0.5px solid var(--border-md);}
        .planning-native-root .modal-title{font-size:15px;font-weight:600;margin-bottom:6px;display:flex;align-items:center;gap:8px;}
        .planning-native-root .modal-title svg{width:18px;height:18px;stroke:var(--teal);fill:none;stroke-width:2;}
        .planning-native-root .modal-desc{font-size:12.5px;color:var(--muted);line-height:1.65;margin-bottom:15px;}
        .planning-native-root .modal-summary{background:var(--bg);border-radius:var(--r);padding:12px 14px;margin-bottom:16px;}
        .planning-native-root .modal-row{display:flex;justify-content:space-between;padding:3px 0;font-size:12px;}
        .planning-native-root .modal-row span{color:var(--muted);}
        .planning-native-root .modal-row strong{color:var(--text);font-family:var(--mono);font-weight:500;}
        .planning-native-root .modal-divider{border:none;border-top:0.5px solid var(--border);margin:6px 0;}
        .planning-native-root .modal-actions{display:flex;gap:8px;justify-content:flex-end;}
        .planning-native-root .btn-cancel{padding:8px 16px;border-radius:var(--r);border:0.5px solid var(--border);background:transparent;font-size:13px;color:var(--muted);}
        .planning-native-root .btn-cancel:hover{background:var(--bg);}
        .planning-native-root .btn-confirm{padding:8px 20px;border-radius:var(--r);border:none;background:var(--teal);font-size:13px;font-weight:500;color:white;}
        .planning-native-root .btn-confirm:hover{opacity:.85;}
        .planning-native-root .success-toast{position:absolute;bottom:20px;left:50%;transform:translateX(-50%);background:#17181C;color:white;padding:10px 20px;border-radius:var(--r);font-size:12.5px;font-weight:500;display:none;align-items:center;gap:8px;z-index:300;white-space:nowrap;}
        .planning-native-root .success-toast.show{display:flex;}
        .planning-native-root .toast-icon{width:16px;height:16px;background:var(--teal);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:10px;flex-shrink:0;}
    `;

    document.head.appendChild(style);
}

function stretchPlanningLayout(wrapper) {
    [
        wrapper.querySelector(".page-body"),
        wrapper.querySelector(".page-wrapper"),
        wrapper.querySelector(".page-content"),
        wrapper.querySelector(".layout-main"),
        wrapper.querySelector(".layout-main-section-wrapper"),
        wrapper.querySelector(".layout-main-section"),
    ].filter(Boolean).forEach((node) => {
        node.style.height = "100%";
        node.style.minHeight = "100%";
    });

    const pageBody = wrapper.querySelector(".container.page-body");
    if (pageBody) pageBody.style.maxWidth = "100%";

    const mainSection = wrapper.querySelector(".layout-main-section");
    if (mainSection) mainSection.style.padding = "0";

    const pageRoot = wrapper.closest(".content.page-container");
    if (pageRoot) pageRoot.style.height = "calc(100vh - 88px)";
}

function escapeHtml(value) {
    return frappe.utils.escape_html(value == null ? "" : String(value));
}
