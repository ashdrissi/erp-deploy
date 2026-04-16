// ── Operations Pipeline — Vue 3 + Tailwind SPA ────────────────────────────

frappe.pages["operations-pipeline"].on_page_load = function (wrapper) {
    wrapper.page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Operations Pipeline"),
        single_column: true,
    });

    const state = { wrapper, page: wrapper.page };
    wrapper._pipelineState = state;

    injectDependencies(state);
    renderSkeleton(state);
};

// ── Dependency Injection ─────────────────────────────────────────────────

function injectDependencies(state) {
    var injected = window.__op_deps_injected;
    if (injected) {
        bootVue(state);
        return;
    }

    // Tailwind config must be set BEFORE the CDN script loads
    window.tailwindConfig = {
        theme: {
            extend: {
                colors: {
                    "bg-app": "#f8f9fa",
                    "border-mid": "#e2e8f0",
                },
            },
        },
    };

    // Tailwind CDN
    var twScript = document.createElement("script");
    twScript.id = "op-tailwind-cdn";
    twScript.src = "https://cdn.tailwindcss.com";
    document.head.appendChild(twScript);

    // Vue 3 from CDN — load after Tailwind
    var vueScript = document.createElement("script");
    vueScript.src = "https://unpkg.com/vue@3/dist/vue.global.prod.js";
    vueScript.onload = function () {
        window.__op_deps_injected = true;
        bootVue(state);
    };
    document.head.appendChild(vueScript);
}

// ── Skeleton ─────────────────────────────────────────────────────────────

function renderSkeleton(state) {
    state.page.main.html(`
        <div id="op-vue-root">
            <div class="flex items-center justify-center" style="height: 100vh;">
                <div class="text-center">
                    <div class="inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mb-3"></div>
                    <div class="text-sm text-gray-500">Loading Operations Pipeline...</div>
                </div>
            </div>
        </div>
    `);
}

// ── Vue Boot ─────────────────────────────────────────────────────────────

function bootVue(state) {
    const { createApp, ref, reactive, computed, onMounted, nextTick, watch } = Vue;

    // ── Utilities ───────────────────────────────────────────────────

    function cn(...classes) {
        return classes.filter(Boolean).join(" ");
    }

    function formatCurrency(val) {
        if (!val) return "—";
        var html = frappe.format(val, { fieldtype: "Currency" });
        // frappe.format returns wrapped HTML — extract plain text
        var div = document.createElement("div");
        div.innerHTML = html;
        return div.textContent || div.innerText || "—";
    }

    function formatDate(dateStr) {
        if (!dateStr) return "";
        return frappe.datetime.str_to_user(dateStr);
    }

    function buildTree(graph, rootId) {
        if (!graph || !graph.nodes) return null;
        const rawNodes = new Map();
        graph.nodes.forEach(node => {
            rawNodes.set(node.id, { ...node });
        });

        const outgoing = new Map();
        (graph.edges || []).forEach(edge => {
            if (!rawNodes.has(edge.from) || !rawNodes.has(edge.to)) return;
            if (!outgoing.has(edge.from)) outgoing.set(edge.from, []);
            outgoing.get(edge.from).push(edge);
        });

        const rootNode = rawNodes.get(rootId) || graph.nodes[0] || null;
        if (!rootNode) return null;

        const relationWeight = {
            fulfillment: 4,
            downstream: 3,
            related: 2,
            sub_branch: 1,
            "sub-branch": 1,
        };

        const bestParent = new Map();
        const bestDepth = new Map([[rootNode.id, 0]]);
        const queue = [rootNode.id];
        const queued = new Set([rootNode.id]);

        while (queue.length) {
            const currentId = queue.shift();
            queued.delete(currentId);
            const currentDepth = bestDepth.get(currentId) || 0;

            for (const edge of outgoing.get(currentId) || []) {
                if (edge.to === rootNode.id) continue;

                const nextDepth = currentDepth + 1;
                const nextWeight = relationWeight[edge.relation] || 0;
                const existing = bestParent.get(edge.to);
                const shouldReplace = !existing
                    || nextWeight > existing.weight
                    || (nextWeight === existing.weight && nextDepth > existing.depth);

                if (shouldReplace) {
                    bestParent.set(edge.to, {
                        parent: currentId,
                        relation: edge.relation,
                        weight: nextWeight,
                        depth: nextDepth,
                    });
                    bestDepth.set(edge.to, nextDepth);
                    if (!queued.has(edge.to)) {
                        queue.push(edge.to);
                        queued.add(edge.to);
                    }
                }
            }
        }

        const treeNodes = new Map();
        rawNodes.forEach((node, id) => {
            treeNodes.set(id, { ...node, children: [], subBranches: [] });
        });

        for (const [childId, info] of bestParent.entries()) {
            const parent = treeNodes.get(info.parent);
            const child = treeNodes.get(childId);
            if (!parent || !child) continue;
            if (info.relation === "sub-branch") {
                parent.subBranches.push(child);
            } else {
                parent.children.push(child);
            }
        }

        return cleanupTraceTree(treeNodes.get(rootNode.id) || null, rootNode.title || rootNode.id);
    }

    function lineageStepPriority(node) {
        const priority = {
            "Lead": 5,
            "Opportunity": 10,
            "Quotation": 20,
            "Sales Order": 30,
            "Pick List": 35,
            "Material Request": 36,
            "Delivery Note": 40,
            "Purchase Order": 40,
            "Purchase Receipt": 45,
            "Sales Invoice": 50,
            "Purchase Invoice": 50,
            "Payment Entry": 60,
        };
        return priority[node?.doctype] || 0;
    }

    function resolveLineageRootId(graph, focusedId) {
        if (!graph?.nodes?.length) return focusedId || null;

        const nodesById = new Map(graph.nodes.map((node) => [node.id, node]));
        const incomingFulfillment = new Map();

        (graph.edges || []).forEach((edge) => {
            if (edge.relation !== "fulfillment") return;
            if (!nodesById.has(edge.from) || !nodesById.has(edge.to)) return;
            if (!incomingFulfillment.has(edge.to)) incomingFulfillment.set(edge.to, []);
            incomingFulfillment.get(edge.to).push(edge.from);
        });

        let currentId = focusedId || graph.root_node_id || graph.nodes[0]?.id || null;
        const seen = new Set();

        while (currentId && !seen.has(currentId)) {
            seen.add(currentId);
            const predecessors = (incomingFulfillment.get(currentId) || []).filter((nodeId) => !seen.has(nodeId));
            if (!predecessors.length) break;

            predecessors.sort((leftId, rightId) => {
                const leftNode = nodesById.get(leftId);
                const rightNode = nodesById.get(rightId);
                const priorityDiff = lineageStepPriority(leftNode) - lineageStepPriority(rightNode);
                if (priorityDiff) return priorityDiff;

                const leftDate = leftNode?.date || "";
                const rightDate = rightNode?.date || "";
                if (leftDate !== rightDate) return String(leftDate).localeCompare(String(rightDate));

                return String(leftId).localeCompare(String(rightId));
            });

            currentId = predecessors[0];
        }

        return currentId || focusedId || graph.root_node_id || graph.nodes[0]?.id || null;
    }

    function cleanupTraceTree(node, referenceTitle) {
        if (!node) return null;

        const cleanBranch = (children) => {
            return (children || []).map((child) => cleanupTraceTree(child, referenceTitle)).flatMap((child) => {
                if (!child) return [];
                if (shouldFlattenCustomerBridge(child, referenceTitle)) {
                    return [...(child.children || []), ...(child.subBranches || [])];
                }
                return [child];
            });
        };

        node.children = cleanBranch(node.children);
        node.subBranches = cleanBranch(node.subBranches);
        return node;
    }

    function shouldFlattenCustomerBridge(node, referenceTitle) {
        const hasDescendants = (node.children && node.children.length > 0) || (node.subBranches && node.subBranches.length > 0);
        return node.type === "CUSTOMER" && hasDescendants && !!referenceTitle && (node.title || node.id) === referenceTitle;
    }

    function computeStageFromDoc(doctype, status) {
        // Maps a document to one of 6 Kanban columns
        if (["Converted", "Lost", "Cancelled", "Closed"].includes(status)) return "closed";
        if (status === "Delivered" || status === "Return Issued") return "delivered";

        // Needs Attention — overdue, open SAV, failed QC
        const needsAttention = status === "Overdue" || status === "On Hold" || status === "Rejected";
        if (needsAttention && doctype !== "Lead") return "needs_attention";

        if (["Delivered", "Completed"].includes(status)) return "delivered";
        if (["To Deliver and Bill", "To Bill", "To Receive and Bill", "To Receive"].includes(status)) return "fulfilling";
        if (["Submitted", "Open", "Running", "Work In Progress", "In Transit"].includes(status)) return "in_progress";
        return "new_triage";
    }

    // ── DOC_REGISTRY ────────────────────────────────────────────────

    const DOC_REGISTRY = {
        LEAD: { label: "Lead", color: "text-cyan-700 border-cyan-200 bg-cyan-50" },
        OPP: { label: "Opportunity", color: "text-indigo-600 border-indigo-200 bg-indigo-50" },
        QTN: { label: "Quotation", color: "text-slate-600 border-slate-200 bg-slate-50" },
        SO: { label: "Sales Order", color: "text-emerald-600 border-emerald-200 bg-emerald-50" },
        DN: { label: "Delivery Note", color: "text-amber-600 border-amber-200 bg-amber-50" },
        PRJ: { label: "Project", color: "text-cyan-600 border-cyan-200 bg-cyan-50" },
        SAV: { label: "Warranty Claim", color: "text-rose-600 border-rose-200 bg-rose-50" },
        PO: { label: "Purchase Order", color: "text-orange-600 border-orange-200 bg-orange-50" },
        PR: { label: "Purchase Receipt", color: "text-teal-600 border-teal-200 bg-teal-50" },
        DT: { label: "Delivery Trip", color: "text-slate-500 border-slate-200 bg-slate-50" },
        QC: { label: "Quality Inspection", color: "text-rose-600 border-rose-200 bg-rose-50" },
        INV: { label: "Sales Invoice", color: "text-purple-600 border-purple-200 bg-purple-50" },
        PAYMENT: { label: "Payment Entry", color: "text-emerald-600 border-emerald-200 bg-emerald-50" },
        NCR: { label: "Non-Conformance", color: "text-rose-600 border-rose-200 bg-rose-50" },
        TIMESHEET: { label: "Timesheet", color: "text-slate-500 border-slate-200 bg-slate-50" },
        MAT_REQ: { label: "Material Request", color: "text-amber-600 border-amber-200 bg-amber-50" },
        CREDIT_NOTE: { label: "Credit Note", color: "text-purple-600 border-purple-200 bg-purple-50" },
        SALES_INVOICE: { label: "Sales Invoice", color: "text-purple-600 border-purple-200 bg-purple-50" },
        PURCHASE_INVOICE: { label: "Purchase Invoice", color: "text-purple-600 border-purple-200 bg-purple-50" },
        COMMUNICATION: { label: "Communication", color: "text-cyan-700 border-cyan-200 bg-cyan-50" },
        SERIAL_NO: { label: "Serial Number", color: "text-slate-500 border-slate-200 bg-slate-50" },
        PICK_LIST: { label: "Pick List", color: "text-amber-600 border-amber-200 bg-amber-50" },
        ISSUE: { label: "Issue", color: "text-rose-600 border-rose-200 bg-rose-50" },
        MAINT_SCHEDULE: { label: "Maint. Schedule", color: "text-emerald-600 border-emerald-200 bg-emerald-50" },
        MAINT_VISIT: { label: "Maint. Visit", color: "text-emerald-600 border-emerald-200 bg-emerald-50" },
        STOCK_ENTRY: { label: "Stock Entry", color: "text-slate-500 border-slate-200 bg-slate-50" },
        WORK_ORDER: { label: "Work Order", color: "text-amber-600 border-amber-200 bg-amber-50" },
        TASK: { label: "Task", color: "text-slate-500 border-slate-200 bg-slate-50" },
        CUSTOMER: { label: "Customer", color: "text-cyan-700 border-cyan-200 bg-cyan-50" },
        SUPPLIER: { label: "Supplier", color: "text-orange-700 border-orange-200 bg-orange-50" },
    };

    const STAGES = [
        { key: "new_triage", label: "New / Triage" },
        { key: "in_progress", label: "In Progress" },
        { key: "fulfilling", label: "Fulfilling" },
        { key: "delivered", label: "Delivered" },
        { key: "needs_attention", label: "Needs Attention" },
        { key: "closed", label: "Closed" },
    ];

    const PIPELINE_TABS = [
        {
            key: "overview",
            label: "Overview",
            description: "Bird's eye view across all operations",
            columns: STAGES,
        },
        {
            key: "crm_sales",
            label: "CRM & Sales",
            description: "Lead to order revenue pipeline",
            columns: [
                { key: "new", label: "New" },
                { key: "qualified", label: "Qualified" },
                { key: "quoted", label: "Quoted" },
                { key: "ordered", label: "Ordered" },
                { key: "closed", label: "Closed" },
            ],
        },
        {
            key: "fulfillment",
            label: "Fulfillment",
            description: "Picking, shipping, and delivery execution",
            columns: [
                { key: "to_pick", label: "To Pick" },
                { key: "to_ship", label: "To Ship" },
                { key: "in_transit", label: "In Transit" },
                { key: "delivered", label: "Delivered" },
                { key: "returned", label: "Returned" },
            ],
        },
        {
            key: "buying",
            label: "Buying",
            description: "Procurement and inbound receipt flow",
            columns: [
                { key: "requested", label: "Requested" },
                { key: "ordered", label: "Ordered" },
                { key: "received", label: "Received" },
                { key: "billed", label: "Billed" },
                { key: "closed", label: "Closed" },
            ],
        },
        {
            key: "accounting",
            label: "Accounting",
            description: "Invoices and money movements",
            columns: [
                { key: "unbilled", label: "Unbilled" },
                { key: "draft", label: "Draft" },
                { key: "overdue", label: "Overdue" },
                { key: "settled", label: "Settled" },
            ],
        },
        {
            key: "after_sales",
            label: "After-Sales",
            description: "Warranty, service, and maintenance",
            columns: [
                { key: "open", label: "Open" },
                { key: "in_progress", label: "In Progress" },
                { key: "on_hold", label: "On Hold" },
                { key: "resolved", label: "Resolved" },
                { key: "closed", label: "Closed" },
            ],
        },
    ];

    const DOC_DOMAIN = {
        Lead: "crm_sales",
        Opportunity: "crm_sales",
        Quotation: "crm_sales",
        "Sales Order": "crm_sales",
        "Delivery Note": "fulfillment",
        "Delivery Trip": "fulfillment",
        "Pick List": "fulfillment",
        "Material Request": "buying",
        "Purchase Order": "buying",
        "Purchase Receipt": "buying",
        "Sales Invoice": "accounting",
        "Purchase Invoice": "accounting",
        "Payment Entry": "accounting",
        "SAV Ticket": "after_sales",
        Issue: "after_sales",
        "Maintenance Schedule": "after_sales",
        "Maintenance Visit": "after_sales",
    };

    const TERMINAL_STATUSES = new Set([
        "Cancelled", "Closed", "Completed", "Converted", "Delivered",
        "Fully Completed", "Lost", "Resolved", "Return Issued", "Paid",
    ]);

    function getDealDomain(doctype) {
        return DOC_DOMAIN[doctype] || null;
    }

    function resolveTabStage(deal, tabKey) {
        const status = deal.status || "";
        const doctype = deal.doctype || "";
        const overdue = !!deal.overdue;

        if (tabKey === "overview") return deal.column || "in_progress";

        if (tabKey === "crm_sales") {
            if (doctype === "Lead") return TERMINAL_STATUSES.has(status) ? "closed" : "new";
            if (doctype === "Opportunity") return TERMINAL_STATUSES.has(status) ? "closed" : "qualified";
            if (doctype === "Quotation") {
                if (["Cancelled", "Lost"].includes(status)) return "closed";
                if (["Ordered", "Partially Ordered"].includes(status)) return "ordered";
                return "quoted";
            }
            if (doctype === "Sales Order") return TERMINAL_STATUSES.has(status) ? "closed" : "ordered";
            return null;
        }

        if (tabKey === "fulfillment") {
            if (doctype === "Pick List") return TERMINAL_STATUSES.has(status) ? "to_ship" : "to_pick";
            if (doctype === "Delivery Trip") {
                if (status === "In Transit") return "in_transit";
                if (status === "Completed") return "delivered";
                return "to_ship";
            }
            if (doctype === "Delivery Note") {
                if (status === "Return Issued") return "returned";
                if (["Draft", "Open"].includes(status)) return "to_ship";
                return "delivered";
            }
            return null;
        }

        if (tabKey === "buying") {
            if (doctype === "Material Request") {
                if (TERMINAL_STATUSES.has(status) || ["Stopped", "Received", "Transferred", "Issued"].includes(status)) {
                    return "closed";
                }
                if (["Ordered", "Partially Ordered"].includes(status)) return "ordered";
                return "requested";
            }
            if (doctype === "Purchase Order") {
                if (TERMINAL_STATUSES.has(status)) return "closed";
                if (status === "To Bill") return "billed";
                return "ordered";
            }
            if (doctype === "Purchase Receipt") return TERMINAL_STATUSES.has(status) ? "closed" : "received";
            return null;
        }

        if (tabKey === "accounting") {
            if (doctype === "Payment Entry") return status === "Completed" ? "settled" : "draft";
            if (["Sales Invoice", "Purchase Invoice"].includes(doctype)) {
                if (status === "Draft") return "draft";
                if (["Paid", "Credit Note Issued"].includes(status)) return "settled";
                if (overdue || status === "Overdue") return "overdue";
                return "unbilled";
            }
            return null;
        }

        if (tabKey === "after_sales") {
            if (["Closed", "Cancelled"].includes(status)) return "closed";
            if (status === "Resolved") return "resolved";
            if (["On Hold", "Blocked"].includes(status)) return "on_hold";
            if (["Assigned", "In Progress", "Work In Progress", "Open", "Replied"].includes(status)) {
                return status === "Open" ? "open" : "in_progress";
            }
            return "open";
        }

        return null;
    }

    function progressForStage(stageKey) {
        const stageProgress = {
            new: 10,
            qualified: 25,
            quoted: 45,
            ordered: 70,
            to_pick: 20,
            to_ship: 40,
            in_transit: 65,
            delivered: 90,
            returned: 100,
            requested: 15,
            received: 70,
            billed: 85,
            unbilled: 40,
            draft: 20,
            overdue: 55,
            settled: 100,
            open: 15,
            on_hold: 35,
            resolved: 85,
            new_triage: 10,
            in_progress: 30,
            fulfilling: 60,
            needs_attention: 40,
            closed: 100,
        };
        return stageProgress[stageKey] || 30;
    }

    function normalizeText(value) {
        return String(value || "").trim().toLowerCase();
    }

    function uniqueSorted(values) {
        return [...new Set((values || []).filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b)));
    }

    function parseFilterDate(value) {
        if (!value) return null;
        const parsed = new Date(String(value).replace(" ", "T"));
        if (Number.isNaN(parsed.getTime())) return null;
        return new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate());
    }

    function isWithinDateRange(value, startDate, endDate) {
        const current = parseFilterDate(value);
        if (!current) return false;
        const start = parseFilterDate(startDate);
        const end = parseFilterDate(endDate);
        if (start && current < start) return false;
        if (end && current > end) return false;
        return true;
    }

    function dealNeedsAttention(deal) {
        return !!(deal.blocked || deal.overdue || deal.status === "Overdue" || deal.openSavCount > 0 || deal.qcFailed);
    }

    function dealHasPaymentPending(deal) {
        const status = normalizeText(deal.status);
        if (deal.doctype === "Payment Entry") return status !== "completed";
        if (["Sales Invoice", "Purchase Invoice"].includes(deal.doctype)) {
            return !["paid", "credit note issued", "cancelled"].includes(status);
        }
        if (["Sales Order", "Purchase Order"].includes(deal.doctype)) {
            return ["submitted", "ordered", "to bill", "to deliver and bill", "to receive and bill"].includes(status);
        }
        return false;
    }

    function dealHasQCPending(deal) {
        if (deal.qcFailed) return true;
        return deal.doctype === "Quality Inspection" && normalizeText(deal.status) !== "completed";
    }

    function isDraftStatus(statusLabel) {
        return normalizeText(statusLabel) === "draft";
    }

    function isCancelledStatus(statusLabel) {
        return ["cancelled", "lost"].includes(normalizeText(statusLabel));
    }

    function filterTraceGraph(graph, rootNodeId, filters) {
        if (!graph) return null;

        let edges = [...(graph.edges || [])];
        if (filters.mainSpineOnly) {
            edges = edges.filter((edge) => edge.relation === "fulfillment");
        }

        const connectedIds = new Set([rootNodeId || graph.root_node_id]);
        edges.forEach((edge) => {
            connectedIds.add(edge.from);
            connectedIds.add(edge.to);
        });

        let nodes = (graph.nodes || []).filter((node) => {
            if (node.id === rootNodeId || node.id === graph.root_node_id) return true;
            if (filters.hideDraft && isDraftStatus(node.status_label)) return false;
            if (filters.hideCancelled && isCancelledStatus(node.status_label)) return false;
            if (filters.mainSpineOnly && !connectedIds.has(node.id)) return false;
            return true;
        });

        const nodeIds = new Set(nodes.map((node) => node.id));
        edges = edges.filter((edge) => nodeIds.has(edge.from) && nodeIds.has(edge.to));

        return {
            nodes,
            edges,
            root_node_id: rootNodeId || graph.root_node_id,
        };
    }

    function traceAlertClass(tone) {
        const tones = {
            cyan: "bg-cyan-50 text-cyan-700 border-cyan-200",
            amber: "bg-amber-50 text-amber-700 border-amber-200",
            rose: "bg-rose-50 text-rose-700 border-rose-200",
            emerald: "bg-emerald-50 text-emerald-700 border-emerald-200",
            slate: "bg-slate-50 text-slate-700 border-slate-200",
        };
        return tones[tone] || tones.slate;
    }

    function statusPillClass(statusLabel, statusCode) {
        const value = (statusLabel || "").toLowerCase();
        if (["paid", "completed", "closed", "converted", "resolved", "received"].includes(value)) {
            return "bg-emerald-50 text-emerald-700 border-emerald-200";
        }
        if (["draft"].includes(value)) {
            return "bg-slate-50 text-slate-700 border-slate-200";
        }
        if (["open", "pending", "initiated"].includes(value)) {
            return "bg-cyan-50 text-cyan-700 border-cyan-200";
        }
        if (["submitted", "ordered", "to receive", "to bill", "to deliver and bill", "to receive and bill", "in progress", "work in progress", "delivered"].includes(value)) {
            return "bg-amber-50 text-amber-700 border-amber-200";
        }
        if (["cancelled", "lost", "rejected", "overdue", "on hold", "blocked"].includes(value)) {
            return "bg-rose-50 text-rose-700 border-rose-200";
        }
        if (statusCode === "completed") return "bg-emerald-50 text-emerald-700 border-emerald-200";
        if (statusCode === "blocked" || statusCode === "warning") return "bg-rose-50 text-rose-700 border-rose-200";
        if (statusCode === "active") return "bg-cyan-50 text-cyan-700 border-cyan-200";
        return "bg-slate-50 text-slate-600 border-slate-200";
    }

    // ── SVG Icons (inline, no lucide dependency) ────────────────────

    const ICONS = {
        LEAD: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`,
        OPP: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>`,
        QTN: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`,
        SO: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`,
        DN: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="1" y="3" width="15" height="13" rx="1"/><polygon points="16 8 20 11 20 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>`,
        PRJ: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>`,
        SAV: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
        PO: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="1" y="4" width="22" height="16" rx="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>`,
        PR: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
        DT: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>`,
        QC: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
        INV: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="2" y="4" width="20" height="16" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>`,
        PAYMENT: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>`,
        NCR: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
        TIMESHEET: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
        MAT_REQ: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>`,
        CREDIT_NOTE: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 5 5 12 12 19"/></svg>`,
        SALES_INVOICE: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="2" y="4" width="20" height="16" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>`,
        PURCHASE_INVOICE: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="2" y="4" width="20" height="16" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>`,
        COMMUNICATION: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>`,
        SERIAL_NO: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="4" y1="9" x2="20" y2="9"/><line x1="4" y1="15" x2="20" y2="15"/><line x1="10" y1="3" x2="8" y2="21"/><line x1="16" y1="3" x2="14" y2="21"/></svg>`,
        PICK_LIST: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>`,
        ISSUE: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
        MAINT_SCHEDULE: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>`,
        MAINT_VISIT: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>`,
        STOCK_ENTRY: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>`,
        WORK_ORDER: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 9h6v6H9z"/><path d="M9 1v3"/><path d="M15 1v3"/><path d="M9 20v3"/><path d="M15 20v3"/><path d="M20 9h3"/><path d="M20 14h3"/><path d="M1 9h3"/><path d="M1 14h3"/></svg>`,
        TASK: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>`,
        CUSTOMER: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
    };

    function icon(type, cls) {
        const svg = ICONS[type] || ICONS.SO;
        return svg.replace("<svg", `<svg class="${cls || "w-5 h-5"}"`);
    }

    // ── Vue Components ──────────────────────────────────────────────

    // Badge Component
    const Badge = {
        props: { type: { type: String, default: "SO" } },
        template: `
            <span :class="cn('px-2 py-0.5 rounded-md text-[9px] font-bold uppercase border tracking-wider', registry.color)">
                {{ registry.label }}
            </span>
        `,
        setup(props) {
            const registry = computed(() => DOC_REGISTRY[props.type] || { label: props.type, color: "text-slate-500 border-slate-200 bg-slate-50" });
            return { registry, cn };
        }
    };

    // StatusIcon Component
    const StatusIcon = {
        props: { status: { type: String, default: "pending" } },
        template: `<div :class="cn('w-2 h-2 rounded-full shrink-0', colors[status] || colors.pending)"></div>`,
        setup() {
            const colors = {
                active: "bg-[#00b0c8] shadow-[0_0_8px_rgba(0,176,200,0.45)]",
                completed: "bg-emerald-500",
                pending: "bg-slate-300",
                blocked: "bg-rose-500 animate-pulse",
                warning: "bg-amber-500",
            };
            return { colors, cn };
        }
    };

    // SpineNode Component (recursive)
    const SpineNode = {
        name: "SpineNode",
        props: {
            node: { type: Object, required: true },
            onOpen: { type: Function, default: null },
            focusedId: { type: String, default: null },
        },
        components: { Badge, StatusIcon },
        template: `
            <div ref="nodeEl" class="relative">
                <div :class="cn(
                    'flex items-start gap-4 group py-3 rounded-2xl transition-all duration-200',
                    isFocused ? 'px-4 bg-cyan-100/80 border border-cyan-300 shadow-[0_12px_32px_rgba(0,176,200,0.18)]' : ''
                )">
                    <!-- Spine Connector -->
                    <div class="absolute left-[23px] top-0 bottom-0 w-px bg-slate-200 group-last:bottom-1/2"></div>

                    <!-- Node Icon -->
                    <div :class="cn(
                        'relative z-10 w-12 h-12 rounded-xl border flex items-center justify-center shadow-sm transition-all duration-300 group-hover:scale-110 group-hover:shadow-md',
                        isFocused ? 'border-cyan-600 ring-4 ring-cyan-200 bg-cyan-50 shadow-[0_0_0_1px_rgba(8,145,178,0.08)]' : node.status === 'active' ? 'border-[#00b0c8] ring-4 ring-cyan-50 bg-white' : 'border-slate-200 bg-white'
                    )">
                        <span class="opacity-80" v-html="iconSVG"></span>
                        <div class="absolute -bottom-1 -right-1">
                            <StatusIcon :status="node.status" />
                        </div>
                    </div>

                    <!-- Node Content -->
                    <div class="flex-1 min-w-0 pt-1 cursor-pointer" @click.stop="openNode">
                        <div class="flex items-center justify-between gap-3 mb-1">
                            <div class="flex items-center gap-2 min-w-0">
                                <Badge :type="node.type" />
                                <span :class="cn('text-sm font-bold tracking-tight', isFocused ? 'text-cyan-950' : 'text-slate-900')">{{ node.id }}</span>
                                <span v-if="isFocused" class="px-2 py-0.5 rounded-md text-[9px] font-bold border border-cyan-700 bg-cyan-700 text-white uppercase tracking-wider shadow-sm">Focused</span>
                            </div>
                            <div class="flex items-center gap-2 shrink-0">
                                <span v-if="node.status_label" :class="cn('px-2 py-0.5 rounded-md text-[9px] font-bold border', statusPillClass(node.status_label, node.status))">{{ node.status_label }}</span>
                                <span class="text-[10px] font-mono font-medium text-slate-400">{{ node.date }}</span>
                            </div>
                        </div>
                        <h4 :class="cn('text-xs font-semibold truncate', isFocused ? 'text-cyan-900' : 'text-slate-700')">{{ node.title }}</h4>
                        <p v-if="node.details" :class="cn('text-[10px] mt-1 leading-relaxed', isFocused ? 'text-cyan-800/80' : 'text-slate-400')">{{ node.details }}</p>

                        <div v-if="node.assignee" class="flex items-center gap-2 mt-2">
                            <div class="w-5 h-5 rounded-full bg-blue-600 flex items-center justify-center text-[8px] font-bold text-white">
                                {{ node.assignee.initials }}
                            </div>
                            <span class="text-[10px] font-medium text-slate-500">{{ node.assignee.name }}</span>
                        </div>

                        <!-- Sub-branches (Parallel flows) -->
                        <div v-if="node.subBranches && node.subBranches.length > 0" class="mt-3 ml-4 border-l-2 border-slate-100 pl-4 space-y-3">
                            <div class="text-[9px] font-bold text-slate-400 uppercase tracking-widest mb-2">Parallel Flows</div>
                            <div v-for="sub in node.subBranches" :key="sub.id" @click.stop="onOpen && onOpen(sub)" class="flex items-center gap-3 p-2 bg-slate-50 rounded-lg border border-slate-100 cursor-pointer hover:border-cyan-200 hover:bg-cyan-50/40 transition-colors">
                                <Badge :type="sub.type" />
                                <span class="text-[10px] font-bold text-slate-600">{{ sub.id }}</span>
                                <span v-if="sub.status_label" :class="cn('px-2 py-0.5 rounded-md text-[8px] font-bold border ml-auto', statusPillClass(sub.status_label, sub.status))">{{ sub.status_label }}</span>
                                <StatusIcon :status="sub.status" />
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Children -->
                <div v-if="node.children && node.children.length > 0" class="ml-6 border-l-2 border-slate-100 pl-6">
                    <SpineNode
                        v-for="child in node.children"
                        :key="child.id"
                        :node="child"
                        :on-open="onOpen"
                        :focused-id="focusedId"
                    />
                </div>
            </div>
        `,
        setup(props) {
            const nodeEl = ref(null);
            const isFocused = computed(() => !!props.focusedId && props.node.id === props.focusedId);
            const iconSVG = computed(() => {
                const svg = ICONS[props.node.type] || ICONS.SO;
                const colorClass = props.node.type === "PAYMENT" ? "text-emerald-500" :
                                   props.node.type === "NCR" ? "text-rose-500" : "";
                return svg.replace("<svg", `<svg class="w-5 h-5 ${colorClass}"`);
            });
            onMounted(() => {
                if (!isFocused.value) return;
                nextTick(() => {
                    nodeEl.value?.scrollIntoView({ block: "center", behavior: "smooth" });
                });
            });
            const openNode = () => {
                if (props.onOpen) props.onOpen(props.node);
            };
            return { node: props.node, cn, nodeEl, isFocused, iconSVG, statusPillClass, openNode, onOpen: props.onOpen, focusedId: props.focusedId };
        }
    };

    // HealthSummary Component
    const HealthSummary = {
        props: { deal: { type: Object, required: true } },
        components: { StatusIcon },
        template: `
            <div class="grid grid-cols-2 gap-2">
                <!-- Payment -->
                <div :class="cn('p-3 rounded-xl border transition-colors',
                    metrics.payment === 'Settled' ? 'bg-emerald-50 border-emerald-100' : 'bg-slate-50 border-slate-100')">
                    <div class="flex items-center justify-between mb-1">
                        <span :class="cn('text-[8px] font-black uppercase tracking-widest',
                            metrics.payment === 'Settled' ? 'text-emerald-600' : 'text-slate-600')">Payment</span>
                        <span v-html="icon('PAYMENT', 'w-3 h-3 ' + (metrics.payment === 'Settled' ? 'text-emerald-500' : 'text-slate-400'))"></span>
                    </div>
                    <div :class="cn('text-xs font-bold', metrics.payment === 'Settled' ? 'text-emerald-900' : 'text-slate-900')">{{ metrics.payment }}</div>
                    <div class="text-[9px] text-slate-500 mt-0.5">{{ metrics.payment === 'Settled' ? '100% Received' : 'Awaiting Entry' }}</div>
                </div>

                <!-- Quality -->
                <div :class="cn('p-3 rounded-xl border transition-colors',
                    metrics.quality === 'Passed' ? 'bg-blue-50 border-blue-100' :
                    metrics.quality === 'Warning' ? 'bg-rose-50 border-rose-100' : 'bg-slate-50 border-slate-100')">
                    <div class="flex items-center justify-between mb-1">
                        <span :class="cn('text-[8px] font-black uppercase tracking-widest',
                            metrics.quality === 'Passed' ? 'text-blue-600' :
                            metrics.quality === 'Warning' ? 'text-rose-600' : 'text-slate-600')">Quality</span>
                        <span v-html="icon('QC', 'w-3 h-3 ' + (metrics.quality === 'Passed' ? 'text-blue-500' : metrics.quality === 'Warning' ? 'text-rose-500' : 'text-slate-400'))"></span>
                    </div>
                    <div :class="cn('text-xs font-bold', metrics.quality === 'Passed' ? 'text-blue-900' : metrics.quality === 'Warning' ? 'text-rose-900' : 'text-slate-900')">{{ metrics.quality }}</div>
                    <div class="text-[9px] text-slate-500 mt-0.5">{{ metrics.qcCount }} Inspections</div>
                </div>

                <!-- Time -->
                <div :class="cn('p-3 rounded-xl border transition-colors',
                    metrics.time === 'On Track' ? 'bg-amber-50 border-amber-100' : 'bg-rose-50 border-rose-100')">
                    <div class="flex items-center justify-between mb-1">
                        <span :class="cn('text-[8px] font-black uppercase tracking-widest',
                            metrics.time === 'On Track' ? 'text-amber-600' : 'text-rose-600')">Time</span>
                        <span v-html="icon('TIMESHEET', 'w-3 h-3 ' + (metrics.time === 'On Track' ? 'text-amber-500' : 'text-rose-500'))"></span>
                    </div>
                    <div :class="cn('text-xs font-bold', metrics.time === 'On Track' ? 'text-amber-900' : 'text-rose-900')">{{ metrics.time }}</div>
                    <div class="text-[9px] text-slate-500 mt-0.5">SLA: {{ deal.slaStatus.toUpperCase() }}</div>
                </div>

                <!-- SAV -->
                <div :class="cn('p-3 rounded-xl border transition-colors',
                    metrics.savCount === 0 ? 'bg-slate-50 border-slate-100' : 'bg-rose-50 border-rose-100')">
                    <div class="flex items-center justify-between mb-1">
                        <span :class="cn('text-[8px] font-black uppercase tracking-widest',
                            metrics.savCount === 0 ? 'text-slate-600' : 'text-rose-600')">SAV</span>
                        <span v-html="icon('SAV', 'w-3 h-3 ' + (metrics.savCount === 0 ? 'text-slate-500' : 'text-rose-500'))"></span>
                    </div>
                    <div :class="cn('text-xs font-bold', metrics.savCount === 0 ? 'text-slate-900' : 'text-rose-900')">{{ metrics.savCount === 0 ? 'None' : 'Active' }}</div>
                    <div class="text-[9px] text-slate-500 mt-0.5">{{ metrics.savCount }} Open Tickets</div>
                </div>
            </div>
        `,
        setup(props) {
            const nodes = computed(() => props.deal.graph ? props.deal.graph.nodes : []);
            const metrics = computed(() => ({
                payment: nodes.value.some(n => n.type === "PAYMENT" && n.status === "completed") ? "Settled" : "Pending",
                quality: nodes.value.some(n => n.type === "NCR") ? "Warning" :
                         nodes.value.some(n => n.type === "QC" && n.status === "completed") ? "Passed" : "Pending",
                time: props.deal.slaStatus === "ok" ? "On Track" : props.deal.slaStatus === "warning" ? "Delayed" : "Breached",
                savCount: nodes.value.filter(n => n.type === "SAV" && n.status !== "completed").length,
                qcCount: nodes.value.filter(n => n.type === "QC").length,
            }));
            return { metrics, nodes, cn, icon };
        }
    };

    // DealCard Component
    const DealCard = {
        props: { deal: { type: Object, required: true }, selected: { type: Boolean, default: false } },
        emits: ["select"],
        components: { Badge },
        template: `
            <div :class="cn(
                'bg-white border border-slate-200 p-4 cursor-pointer relative overflow-hidden group rounded-xl transition-all duration-200 hover:shadow-md hover:border-cyan-200',
                selected && 'ring-2 ring-[#00b0c8] border-transparent shadow-lg'
            )" @click="$emit('select', deal)">
                <div class="absolute top-0 left-0 w-1 h-full bg-[#00b0c8] opacity-0 group-hover:opacity-100 transition-opacity"></div>

                <div class="flex items-center justify-between mb-3">
                    <Badge :type="rootType" />
                    <div :class="cn(
                        'w-2 h-2 rounded-full',
                        deal.healthScore > 80 ? 'bg-emerald-500' : deal.healthScore > 50 ? 'bg-amber-500' : 'bg-rose-500 animate-pulse'
                    )"></div>
                </div>

                <h4 class="text-sm font-bold text-slate-900 mb-1 group-hover:text-cyan-700 transition-colors truncate">{{ deal.customer }}</h4>
                <div class="text-xs font-medium text-slate-400 mb-3">{{ deal.id }}</div>

                <div class="text-lg font-black font-mono text-slate-900 tracking-tight mb-4" v-html="formattedValue"></div>

                <!-- Progress Bar -->
                <div class="space-y-1.5 mb-4">
                    <div class="flex justify-between text-[9px] font-bold text-slate-400 uppercase">
                        <span>Progress</span>
                        <span>{{ deal.progress }}%</span>
                    </div>
                    <div class="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div :class="cn(
                            'h-full rounded-full transition-all duration-500',
                            deal.healthScore > 80 ? 'bg-emerald-500' : deal.healthScore > 50 ? 'bg-amber-500' : 'bg-rose-500'
                        )" :style="{ width: deal.progress + '%' }"></div>
                    </div>
                </div>

                <div class="flex flex-wrap gap-1.5">
                    <span v-if="deal.status" :class="cn('px-2 py-0.5 rounded-md text-[9px] font-bold border uppercase tracking-wider', statusPillClass(deal.status, deal.blocked ? 'blocked' : 'active'))">
                        {{ deal.status }}
                    </span>
                    <span v-for="tag in deal.tags" :key="tag"
                        class="px-2 py-0.5 bg-slate-50 border border-slate-100 text-[9px] font-bold text-slate-500 rounded uppercase tracking-wider">
                        {{ tag }}
                    </span>
                </div>

                <div v-if="deal.blocked" class="mt-3 p-2 bg-rose-50 border border-rose-100 rounded-lg flex items-center gap-2 text-[10px] font-bold text-rose-600">
                    <span v-html="icon('NCR', 'w-3 h-3')"></span>
                    <span>Blocked: {{ deal.blockedReason }}</span>
                </div>
            </div>
        `,
        setup(props) {
            const DOCTYPE_TO_CODE = {
                "Lead": "LEAD", "Opportunity": "OPP", "Quotation": "QTN",
                "Sales Order": "SO", "Purchase Order": "PO",
                "Delivery Note": "DN", "Delivery Trip": "DT",
                "Sales Invoice": "SALES_INVOICE", "Purchase Invoice": "PURCHASE_INVOICE",
                "Purchase Receipt": "PR", "Payment Entry": "PAYMENT",
                "Project": "PRJ", "SAV Ticket": "SAV",
                "Quality Inspection": "QC", "Timesheet": "TIMESHEET",
                "Work Order": "WORK_ORDER", "Material Request": "MAT_REQ",
                "Pick List": "PICK_LIST", "Issue": "ISSUE",
                "Maintenance Schedule": "MAINT_SCHEDULE", "Maintenance Visit": "MAINT_VISIT",
                "Serial No": "SERIAL_NO", "Stock Entry": "STOCK_ENTRY",
                "Customer": "CUSTOMER",
                "Supplier": "SUPPLIER",
                "Communication": "COMMUNICATION",
            };
            const rootType = computed(() => {
                if (props.deal.graph && props.deal.graph.nodes && props.deal.graph.nodes.length > 0) {
                    const rootNode = props.deal.graph.nodes.find(n => n.id === props.deal.rootNodeId);
                    if (rootNode) return rootNode.type;
                }
                return DOCTYPE_TO_CODE[props.deal.doctype] || "SO";
            });
            const formattedValue = computed(() => formatCurrency(props.deal.value));
            return { cn, rootType, formattedValue, icon, statusPillClass };
        }
    };

    // ── Main App ────────────────────────────────────────────────────

    createApp({
        components: { Badge, StatusIcon, SpineNode, DealCard },
        setup() {
            const view = ref("pipeline");
            const activePipelineTab = ref("overview");
            const searchQuery = ref("");
            const showMoreFilters = ref(false);
            const deals = ref([]);
            const selectedDeal = ref(null);
            const loading = ref(true);
            const traceLoading = ref(false);
            const traceData = ref(null);
            const projectedTree = ref(null);
            const traceRenderNonce = ref(0);
            const filters = reactive({
                customer: "",
                startDate: "",
                endDate: "",
                attentionOnly: false,
                project: "",
                company: "",
                flowScope: "",
                status: "",
                rootDoctype: "",
                owner: "",
                paymentPendingOnly: false,
                openSavOnly: false,
                qcPendingOnly: false,
                hideDraft: false,
                hideCancelled: false,
                mainSpineOnly: false,
            });

            // Get state from the wrapper (set in on_page_load)
            function getState() {
                return window._pipelineState;
            }

            // Add Frappe menu items (once)
            var st = getState();
            if (st && st.page && !st._menuAdded) {
                st._menuAdded = true;
                st.page.add_menu_item("Refresh", function () { loadPipelineData(); });
                st.page.add_field({
                    fieldname: "flow_scope",
                    fieldtype: "Select",
                    label: __("Flow Scope"),
                    options: ["All", "Inbound", "Domestic", "Outbound"],
                    default: "All",
                    change: function () { loadPipelineData(); },
                });
                st.page.add_field({
                    fieldname: "date_filter",
                    fieldtype: "Select",
                    label: __("Date Filter"),
                    options: ["All", "Today", "This Week", "This Month"],
                    default: "All",
                    change: function () { loadPipelineData(); },
                });
            }

            const tabScopedDeals = computed(() => {
                if (activePipelineTab.value === "overview") return deals.value;
                return deals.value.filter((deal) => deal.domain === activePipelineTab.value);
            });

            const customerOptions = computed(() => uniqueSorted(deals.value.map((deal) => deal.customer)));
            const projectOptions = computed(() => uniqueSorted(deals.value.map((deal) => deal.project)));
            const companyOptions = computed(() => uniqueSorted(deals.value.map((deal) => deal.company)));
            const ownerOptions = computed(() => uniqueSorted(deals.value.map((deal) => deal.owner)));
            const statusOptions = computed(() => uniqueSorted(deals.value.map((deal) => deal.status)));
            const rootDoctypeOptions = computed(() => uniqueSorted(deals.value.map((deal) => deal.doctype)));

            const filteredDeals = computed(() => {
                return tabScopedDeals.value.filter((deal) => {
                    if (filters.customer && deal.customer !== filters.customer) {
                        return false;
                    }
                    if ((filters.startDate || filters.endDate) && !isWithinDateRange(deal.date, filters.startDate, filters.endDate)) {
                        return false;
                    }
                    if (filters.hideDraft && isDraftStatus(deal.status)) {
                        return false;
                    }
                    if (filters.attentionOnly && !dealNeedsAttention(deal)) {
                        return false;
                    }
                    if (filters.project && !normalizeText(deal.project).includes(normalizeText(filters.project))) {
                        return false;
                    }
                    if (filters.company && deal.company !== filters.company) {
                        return false;
                    }
                    if (filters.flowScope && deal.flowScope !== filters.flowScope) {
                        return false;
                    }
                    if (filters.status && deal.status !== filters.status) {
                        return false;
                    }
                    if (filters.rootDoctype && deal.doctype !== filters.rootDoctype) {
                        return false;
                    }
                    if (filters.owner && deal.owner !== filters.owner) {
                        return false;
                    }
                    if (filters.paymentPendingOnly && !dealHasPaymentPending(deal)) {
                        return false;
                    }
                    if (filters.openSavOnly && !(deal.openSavCount > 0)) {
                        return false;
                    }
                    if (filters.qcPendingOnly && !dealHasQCPending(deal)) {
                        return false;
                    }
                    return true;
                });
            });

            const searchedDeals = computed(() => {
                const q = searchQuery.value.toLowerCase();
                if (!q) return filteredDeals.value;
                return filteredDeals.value.filter(d =>
                    (d.customer || "").toLowerCase().includes(q) ||
                    d.id.toLowerCase().includes(q)
                );
            });

            const activeTabConfig = computed(() => {
                return PIPELINE_TABS.find(tab => tab.key === activePipelineTab.value) || PIPELINE_TABS[0];
            });

            const visibleDeals = computed(() => {
                return searchedDeals.value
                    .map((deal) => {
                        const stage = resolveTabStage(deal, activePipelineTab.value);
                        return stage ? {
                            ...deal,
                            stage,
                            progress: progressForStage(stage),
                        } : null;
                    })
                    .filter(Boolean);
            });

            const columnsWithCounts = computed(() => {
                return activeTabConfig.value.columns.map(s => ({
                    ...s,
                    count: visibleDeals.value.filter(d => d.stage === s.key).length,
                }));
            });

            const flowData = computed(() => {
                if (!activeTraceData.value || !activeTraceData.value.nodes) return [];
                return activeTraceData.value.nodes
                    .filter(n => n.value)
                    .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
                    .map(n => ({
                        name: n.id.split("-").pop() || n.id,
                        value: parseFloat((n.value || "0").toString().replace(/[^0-9.]/g, "")) || 0,
                    }));
            });

            const selectedTraceAlerts = computed(() => {
                if (!selectedDeal.value || !activeTraceData.value) return [];

                const nodes = activeTraceData.value.nodes || [];
                const alerts = [];

                const paymentPending = nodes.some((n) => n.type === "PAYMENT" && n.status !== "completed");
                if (paymentPending) {
                    alerts.push({ label: __("Payment Pending"), tone: "amber" });
                }

                const openSavCount = nodes.filter((n) => n.type === "SAV" && n.status !== "completed").length;
                if (openSavCount > 0) {
                    alerts.push({ label: __(`Open SAV: ${openSavCount}`), tone: "rose" });
                }

                const qcNodes = nodes.filter((n) => n.type === "QC");
                const qcPending = qcNodes.length > 0 && !qcNodes.some((n) => n.status === "completed");
                if (qcPending) {
                    alerts.push({ label: __("QC Pending"), tone: "amber" });
                }

                if (selectedDeal.value.blocked) {
                    alerts.push({ label: __(selectedDeal.value.blockedReason || "Blocked"), tone: "rose" });
                }

                if (selectedDeal.value.overdue || selectedDeal.value.status === "Overdue") {
                    alerts.push({ label: __("Overdue"), tone: "rose" });
                }

                if (!alerts.length && selectedDeal.value.status) {
                    alerts.push({ label: __(selectedDeal.value.status), tone: "slate" });
                }

                return alerts;
            });

            const selectedTraceMetaCards = computed(() => {
                if (!selectedDeal.value || !activeTraceData.value) return [];

                const cards = [];
                const nodes = activeTraceData.value.nodes || [];
                const doctype = selectedDeal.value.doctype;
                const hasPayments = nodes.some((n) => n.type === "PAYMENT");
                const paid = nodes.some((n) => n.type === "PAYMENT" && n.status === "completed");
                const qcNodes = nodes.filter((n) => n.type === "QC");
                const qcPassed = qcNodes.some((n) => n.status === "completed");
                const savCount = nodes.filter((n) => n.type === "SAV" && n.status !== "completed").length;

                if (selectedDeal.value.value) {
                    cards.push({
                        label: __("Value"),
                        value: formatCurrency(selectedDeal.value.value),
                        tone: "slate",
                    });
                }

                cards.push({
                    label: __("Docs Linked"),
                    value: String(nodes.length || 0),
                    tone: "slate",
                });

                if (selectedDeal.value.date) {
                    cards.push({
                        label: __("Date"),
                        value: selectedDeal.value.date,
                        tone: "slate",
                    });
                }

                if (["Sales Order", "Sales Invoice", "Purchase Order", "Purchase Invoice"].includes(doctype) || hasPayments) {
                    cards.push({
                        label: __("Payment"),
                        value: paid ? __("Settled") : __("Pending"),
                        tone: paid ? "emerald" : "amber",
                    });
                }

                if (qcNodes.length) {
                    cards.push({
                        label: __("Quality"),
                        value: qcPassed ? __("Passed") : __("Pending"),
                        tone: qcPassed ? "emerald" : "amber",
                    });
                }

                if (savCount) {
                    cards.push({
                        label: __("Open SAV"),
                        value: String(savCount),
                        tone: "rose",
                    });
                }

                if (selectedDeal.value.overdue || selectedDeal.value.status === "Overdue") {
                    cards.push({
                        label: __("Attention"),
                        value: __("Overdue"),
                        tone: "rose",
                    });
                }

                return cards.slice(0, 6);
            });

            const focusedTraceNodeId = computed(() => {
                return (selectedDeal.value && selectedDeal.value.id) || (traceData.value && traceData.value.root_node_id) || null;
            });

            const activeTraceData = computed(() => {
                if (!traceData.value) return null;
                const rootNodeId = focusedTraceNodeId.value || traceData.value.root_node_id;
                return filterTraceGraph(traceData.value, rootNodeId, filters);
            });

            const activeProjectedTree = computed(() => {
                if (!activeTraceData.value) return null;
                const lineageRootId = resolveLineageRootId(
                    activeTraceData.value,
                    focusedTraceNodeId.value || activeTraceData.value.root_node_id
                );
                return buildTree(
                    { nodes: activeTraceData.value.nodes, edges: activeTraceData.value.edges },
                    lineageRootId
                );
            });

            const traceRenderKey = computed(() => [
                traceRenderNonce.value,
                filters.hideDraft,
                filters.hideCancelled,
                filters.mainSpineOnly,
            ].join("-"));

            const moreFiltersCount = computed(() => [
                filters.project,
                filters.company,
                filters.flowScope,
                filters.status,
                filters.rootDoctype,
                filters.owner,
                filters.paymentPendingOnly,
                filters.openSavOnly,
                filters.qcPendingOnly,
                filters.hideDraft,
                filters.hideCancelled,
                filters.mainSpineOnly,
            ].filter(Boolean).length);

            function loadPipelineData() {
                loading.value = true;
                var s = getState();
                var flowScopeEl = s && s.page ? s.page.fields_dict.flow_scope : null;
                var dateFilterEl = s && s.page ? s.page.fields_dict.date_filter : null;
                var flowScope = flowScopeEl ? (flowScopeEl.get_value() === "All" ? null : flowScopeEl.get_value()) : null;
                var dateFilter = dateFilterEl ? (dateFilterEl.get_value() || "All").toLowerCase() : "all";

                frappe.call({
                    method: "orderlift.orderlift_logistics.page.operations_pipeline.operations_pipeline.get_pipeline_data",
                    args: {
                        company: null,
                        flow_scope: flowScope,
                        shipping_responsibility: null,
                        date_filter: dateFilter,
                    },
                    callback: (r) => {
                        if (r.message) {
                            deals.value = (r.message.cards || []).map(card => ({
                                id: card.name,
                                doctype: card.doctype,
                                domain: getDealDomain(card.doctype),
                                customer: card.customer,
                                stage: mapColumnToStage(card.column),
                                column: card.column,
                                value: card.value,
                                date: card.date,
                                company: card.company || "",
                                project: card.project || (card.doctype === "Project" ? card.name : ""),
                                owner: card.owner || "",
                                flowScope: card.flow_scope || "",
                                tags: [card.flow_scope, card.shipping_resp].filter(Boolean),
                                healthScore: computeHealthScore(card),
                                slaStatus: computeSLA(card),
                                progress: progressForStage(card.column),
                                blocked: card.status === "On Hold" || card.qc_failed,
                                blockedReason: card.qc_failed ? "QC Failed" : card.status === "On Hold" ? "On Hold" : undefined,
                                rootNodeId: card.name,
                                status: card.status,
                                overdue: !!card.overdue,
                                openSavCount: card.open_sav_count || 0,
                                qcFailed: !!card.qc_failed,
                                graph: { nodes: [], edges: [] }, // placeholder, loaded on trace open
                            }));
                        }
                        loading.value = false;
                    },
                    error: () => { loading.value = false; }
                });
            }

            function mapColumnToStage(col) {
                const map = {
                    new_triage: "new_triage",
                    in_progress: "in_progress",
                    fulfilling: "fulfilling",
                    delivered: "delivered",
                    needs_attention: "needs_attention",
                    closed: "closed",
                };
                return map[col] || "in_progress";
            }

            function computeHealthScore(card) {
                let score = 80;
                if (card.overdue) score -= 20;
                if (card.open_sav_count) score -= card.open_sav_count * 15;
                if (card.qc_failed) score -= 25;
                if (card.status === "Overdue") score -= 15;
                return Math.max(0, Math.min(100, score));
            }

            function computeSLA(card) {
                if (card.open_sav_count > 0) return "breached";
                if (card.overdue || card.status === "Overdue") return "warning";
                if (card.qc_failed) return "warning";
                return "ok";
            }

            function loadTraceData(deal) {
                traceLoading.value = true;
                traceData.value = null;
                projectedTree.value = null;
                const doctype = deal.doctype || inferDoctype(deal.id);

                frappe.call({
                    method: "orderlift.orderlift_logistics.page.operations_pipeline.operations_pipeline.get_trace_data",
                    args: {
                        entity_type: doctype,
                        entity_name: deal.id,
                    },
                    callback: (r) => {
                        if (r.message) {
                            setTraceState(
                                { nodes: r.message.nodes, edges: r.message.edges, root_node_id: r.message.root_node_id },
                                r.message.root_node_id
                            );
                            // Enrich the deal with trace graph
                            deal.graph = {
                                nodes: r.message.nodes,
                                edges: r.message.edges,
                            };
                            deal.rootNodeId = r.message.root_node_id;
                            if (selectedDeal.value && selectedDeal.value.id === deal.id) {
                                selectedDeal.value = deal;
                            }
                        }
                        traceLoading.value = false;
                    },
                    error: () => { traceLoading.value = false; }
                });
            }

            function cloneTraceGraph(graph) {
                return {
                    nodes: (graph?.nodes || []).map((node) => ({ ...node })),
                    edges: (graph?.edges || []).map((edge) => ({ ...edge })),
                    root_node_id: graph?.root_node_id,
                };
            }

            function setTraceState(graph, rootNodeId) {
                const cloned = cloneTraceGraph(graph);
                traceData.value = cloned;
                projectedTree.value = buildTree(
                    { nodes: cloned.nodes, edges: cloned.edges },
                    rootNodeId || cloned.root_node_id
                );
                traceRenderNonce.value += 1;
            }

            function resetFilters() {
                filters.customer = "";
                filters.startDate = "";
                filters.endDate = "";
                filters.attentionOnly = false;
                filters.project = "";
                filters.company = "";
                filters.flowScope = "";
                filters.status = "";
                filters.rootDoctype = "";
                filters.owner = "";
                filters.paymentPendingOnly = false;
                filters.openSavOnly = false;
                filters.qcPendingOnly = false;
                filters.hideDraft = false;
                filters.hideCancelled = false;
                filters.mainSpineOnly = false;
            }

            function inferDoctype(name) {
                if (name.startsWith("SO-") || name.startsWith("SAL-ORD")) return "Sales Order";
                if (name.startsWith("QTN-") || name.startsWith("QUT-")) return "Quotation";
                if (name.startsWith("DN-") || name.startsWith("DEL-")) return "Delivery Note";
                if (name.startsWith("PRJ-") || name.startsWith("PROJ-")) return "Project";
                if (name.startsWith("SAV-")) return "SAV Ticket";
                if (name.startsWith("PO-") || name.startsWith("PUR-ORD")) return "Purchase Order";
                if (name.startsWith("SI-") || name.startsWith("SINV-")) return "Sales Invoice";
                if (name.startsWith("PAY-") || name.startsWith("PAY-")) return "Payment Entry";
                if (name.startsWith("QC-") || name.startsWith("QI-")) return "Quality Inspection";
                if (name.startsWith("DT-")) return "Delivery Trip";
                if (name.startsWith("LEAD-") || name.startsWith("CRM-")) return "Lead";
                if (name.startsWith("OPP-")) return "Opportunity";
                if (name.startsWith("PR-") && name.includes("PUR-REC")) return "Purchase Receipt";
                if (name.startsWith("TS-")) return "Timesheet";
                if (name.startsWith("WO-")) return "Work Order";
                if (name.startsWith("MAT-REQ")) return "Material Request";
                if (name.startsWith("ISS")) return "Issue";
                if (name.startsWith("COMM-")) return "Communication";
                // Fallback: try Sales Order first
                return "Sales Order";
            }

            function selectDeal(deal) {
                selectedDeal.value = deal;
                if (!deal.graph || !deal.graph.nodes || deal.graph.nodes.length === 0) {
                    loadTraceData(deal);
                } else {
                    setTraceState({
                        nodes: deal.graph.nodes,
                        edges: deal.graph.edges,
                        root_node_id: deal.id,
                    }, deal.id);
                }
            }

            function openInERPNext() {
                if (!selectedDeal.value) return;
                const doctype = selectedDeal.value.doctype || inferDoctype(selectedDeal.value.id);
                if (doctype === "Forecast Load Plan") {
                    frappe.set_route("planning", selectedDeal.value.id);
                } else {
                    frappe.set_route("Form", doctype, selectedDeal.value.id);
                }
            }

            const selectedOpenLabel = computed(() => {
                if (!selectedDeal.value) return __("Open Document");
                const doctype = selectedDeal.value.doctype || inferDoctype(selectedDeal.value.id);
                return __("Open {0}", [doctype]);
            });

            function openDocPreview(node) {
                if (!node || !node.doctype || !node.id) return;

                frappe.call({
                    method: "orderlift.orderlift_logistics.page.operations_pipeline.operations_pipeline.get_document_preview",
                    args: {
                        doctype: node.doctype,
                        name: node.id,
                    },
                    callback: (r) => {
                        const preview = r.message;
                        if (!preview) return;

                        const escape = (value) => frappe.utils.escape_html(String(value || ""));
                        const fields = (preview.fields || []).map((field) => `
                            <div class="row" style="margin-bottom:10px;">
                                <div class="col-xs-4 text-muted small">${escape(field.label)}</div>
                                <div class="col-xs-8">${escape(field.value)}</div>
                            </div>
                        `).join("");

                        const valueHtml = preview.value ? `
                            <div class="row" style="margin-bottom:12px;">
                                <div class="col-xs-4 text-muted small">Value</div>
                                <div class="col-xs-8"><strong>${escape(formatCurrency(preview.value))}</strong></div>
                            </div>
                        ` : "";

                        const d = new frappe.ui.Dialog({
                            title: `${preview.doctype}: ${preview.name}`,
                            size: "large",
                            fields: [
                                {
                                    fieldtype: "HTML",
                                    fieldname: "preview_html",
                                    options: `
                                        <div class="frappe-card" style="padding:16px; background:#fff; border:1px solid #e5e7eb; border-radius:12px;">
                                            <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:12px; margin-bottom:14px;">
                                                <div>
                                                    <div style="font-size:18px; font-weight:700; color:#111827;">${escape(preview.title || preview.name)}</div>
                                                    <div style="margin-top:6px; display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
                                                        <span class="indicator-pill blue">${escape(preview.doctype)}</span>
                                                        ${preview.status ? `<span class="indicator-pill green">${escape(preview.status)}</span>` : ""}
                                                        ${preview.date ? `<span class="text-muted small">${escape(preview.date)}</span>` : ""}
                                                    </div>
                                                </div>
                                            </div>
                                            ${valueHtml}
                                            <div>${fields || '<div class="text-muted small">No preview fields available.</div>'}</div>
                                        </div>
                                    `,
                                },
                            ],
                            primary_action_label: __("Open {0}", [preview.doctype]),
                            primary_action: () => {
                                d.hide();
                                frappe.set_route("Form", preview.doctype, preview.name);
                            },
                        });
                        d.show();
                    },
                });
            }

            // Greeting
            const greeting = computed(() => {
                const hour = new Date().getHours();
                if (hour < 12) return __("Good morning");
                if (hour < 18) return __("Good afternoon");
                return __("Good evening");
            });

            const today = computed(() => frappe.datetime.str_to_user(frappe.datetime.now_date()));

            watch([view, searchedDeals], ([nextView, nextDeals]) => {
                if (!nextDeals.length) {
                    selectedDeal.value = null;
                    traceData.value = null;
                    projectedTree.value = null;
                    return;
                }

                const currentId = selectedDeal.value && selectedDeal.value.id;
                const stillVisible = currentId && nextDeals.some((deal) => deal.id === currentId);
                if (!stillVisible) {
                    if (nextView === "trace") {
                        selectDeal(nextDeals[0]);
                    } else {
                        selectedDeal.value = null;
                        traceData.value = null;
                        projectedTree.value = null;
                    }
                }
            }, { immediate: true });

            // Lifecycle
            onMounted(() => {
                loadPipelineData();
            });

            return {
                view, activePipelineTab, searchQuery, showMoreFilters, filters, deals, selectedDeal, loading, traceLoading, traceData, projectedTree,
                traceRenderNonce, tabScopedDeals, filteredDeals, searchedDeals, visibleDeals, activeTabConfig, columnsWithCounts, flowData, selectedTraceAlerts, selectedTraceMetaCards, focusedTraceNodeId, activeTraceData, activeProjectedTree, traceRenderKey, moreFiltersCount, greeting, today,
                customerOptions, projectOptions, companyOptions, ownerOptions, statusOptions, rootDoctypeOptions,
                selectDeal, openInERPNext, openDocPreview, selectedOpenLabel, resetFilters,
                cn, DOC_REGISTRY, icon, STAGES, PIPELINE_TABS, formatCurrency, formatDate, buildTree, statusPillClass, traceAlertClass,
            };
        },
        template: `
            <div class="min-h-screen bg-[#f5f6fa] text-slate-900 font-sans antialiased">
                <!-- Topbar -->
                <header class="h-14 bg-white border-b border-border-mid px-6 flex items-center justify-between sticky top-0 z-50">
                    <div class="w-64"></div>
                    <div class="flex-1 flex justify-center">
                        <nav class="flex items-center gap-1 bg-slate-100 p-1 rounded-lg">
                            <button
                                @click="view = 'pipeline'"
                                :class="cn('px-4 py-1.5 text-xs font-bold rounded-md transition-all',
                                    view === 'pipeline' ? 'bg-white text-cyan-700 shadow-sm' : 'text-slate-500 hover:text-slate-700')">
                                Pipeline
                            </button>
                            <button
                                @click="view = 'trace'"
                                :class="cn('px-4 py-1.5 text-xs font-bold rounded-md transition-all',
                                    view === 'trace' ? 'bg-white text-cyan-700 shadow-sm' : 'text-slate-500 hover:text-slate-700')">
                                Trace Graph
                            </button>
                        </nav>
                    </div>

                    <div class="w-64 flex items-center justify-end gap-4">
                        <div class="relative">
                            <span class="absolute left-3 top-1/2 -translate-y-1/2" v-html="icon('LEAD', 'w-4 h-4 text-slate-400')"></span>
                            <input
                                type="text"
                                v-model="searchQuery"
                                placeholder="Search deals, docs, customers..."
                                class="w-64 h-9 bg-slate-100 border border-transparent focus:bg-white focus:border-cyan-500 focus:ring-4 focus:ring-cyan-500/10 rounded-xl pl-10 pr-4 text-xs outline-none transition-all">
                        </div>
                    </div>
                </header>

                <main class="flex-1 min-h-0 flex flex-col overflow-hidden">
                    <div class="bg-white border-b border-border-mid px-6 py-3">
                        <div class="flex items-start justify-between gap-6 mb-3">
                            <div>
                                <h2 class="text-xl font-bold tracking-tight text-slate-900">{{ activeTabConfig.key === 'overview' ? 'Operations Board' : activeTabConfig.label }}</h2>
                                <p class="text-xs text-slate-500 mt-1">{{ activeTabConfig.description }}</p>
                            </div>
                            <div class="text-right text-[11px] text-slate-500">
                                <div class="font-semibold text-slate-700">{{ view === 'pipeline' ? 'Pipeline View' : 'Trace Graph' }}</div>
                                <div>{{ searchedDeals.length }} visible entities</div>
                            </div>
                        </div>

                        <div class="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                            <div class="flex flex-wrap gap-2">
                                <button
                                    v-for="tab in PIPELINE_TABS"
                                    :key="tab.key"
                                    @click="activePipelineTab = tab.key"
                                    :class="cn(
                                        'px-4 py-2 rounded-xl text-xs font-bold border transition-all',
                                        activePipelineTab === tab.key
                                            ? 'bg-slate-900 text-white border-slate-900 shadow-lg shadow-slate-200'
                                            : 'bg-white text-slate-600 border-slate-200 hover:border-cyan-200 hover:text-cyan-700'
                                    )">
                                    {{ tab.label }}
                                </button>
                            </div>

                            <div class="flex flex-wrap items-center justify-end gap-2 xl:ml-auto">
                                <div class="relative min-w-[13rem]">
                                    <select
                                        v-model="filters.customer"
                                        class="h-9 w-full appearance-none bg-white border border-slate-200 rounded-xl pl-3 pr-9 text-xs font-medium text-slate-700 outline-none focus:border-cyan-500 focus:ring-4 focus:ring-cyan-500/10">
                                        <option value="">All customers</option>
                                        <option v-for="customer in customerOptions" :key="customer" :value="customer">{{ customer }}</option>
                                    </select>
                                    <span class="pointer-events-none absolute inset-y-0 right-3 flex items-center text-slate-400 text-[10px]">▾</span>
                                </div>
                                <input
                                    type="date"
                                    v-model="filters.startDate"
                                    class="h-9 bg-slate-50 border border-slate-200 rounded-xl px-3 text-xs outline-none focus:bg-white focus:border-cyan-500 focus:ring-4 focus:ring-cyan-500/10">
                                <input
                                    type="date"
                                    v-model="filters.endDate"
                                    class="h-9 bg-slate-50 border border-slate-200 rounded-xl px-3 text-xs outline-none focus:bg-white focus:border-cyan-500 focus:ring-4 focus:ring-cyan-500/10">
                                <button
                                    @click="filters.attentionOnly = !filters.attentionOnly"
                                    :class="cn(
                                        'h-9 px-3 rounded-xl text-xs font-bold border transition-all',
                                        filters.attentionOnly
                                            ? 'bg-[#00b0c8] text-white border-[#00b0c8] shadow-sm'
                                            : 'bg-white text-slate-600 border-slate-200 hover:border-cyan-200 hover:text-cyan-700'
                                    )">
                                    Attention Only
                                </button>
                                <button
                                    @click="showMoreFilters = !showMoreFilters"
                                    :class="cn(
                                        'h-9 px-3 rounded-xl text-xs font-bold border transition-all flex items-center gap-2',
                                        showMoreFilters
                                            ? 'bg-slate-900 text-white border-slate-900'
                                            : 'bg-white text-slate-600 border-slate-200 hover:border-cyan-200 hover:text-cyan-700'
                                    )">
                                    <span>More Filters</span>
                                    <span v-if="moreFiltersCount" class="px-1.5 py-0.5 rounded-full bg-white/15 text-[10px]">{{ moreFiltersCount }}</span>
                                </button>
                            </div>
                        </div>

                        <div v-if="showMoreFilters" class="mt-3 w-full">
                            <div class="w-full bg-slate-50 border border-slate-200 rounded-2xl p-4 space-y-4">
                                <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
                                    <div>
                                        <div class="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">Project</div>
                                        <input
                                            type="text"
                                            v-model="filters.project"
                                            list="op-project-options"
                                            placeholder="Any project"
                                            class="w-full h-9 bg-white border border-slate-200 rounded-xl px-3 text-xs outline-none focus:border-cyan-500 focus:ring-4 focus:ring-cyan-500/10">
                                        <datalist id="op-project-options">
                                            <option v-for="project in projectOptions" :key="project" :value="project"></option>
                                        </datalist>
                                    </div>
                                    <div>
                                        <div class="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">Company</div>
                                        <select v-model="filters.company" class="w-full h-9 bg-white border border-slate-200 rounded-xl px-3 text-xs outline-none focus:border-cyan-500 focus:ring-4 focus:ring-cyan-500/10">
                                            <option value="">All companies</option>
                                            <option v-for="company in companyOptions" :key="company" :value="company">{{ company }}</option>
                                        </select>
                                    </div>
                                    <div>
                                        <div class="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">Flow Scope</div>
                                        <select v-model="filters.flowScope" class="w-full h-9 bg-white border border-slate-200 rounded-xl px-3 text-xs outline-none focus:border-cyan-500 focus:ring-4 focus:ring-cyan-500/10">
                                            <option value="">All scopes</option>
                                            <option value="Inbound">Inbound</option>
                                            <option value="Domestic">Domestic</option>
                                            <option value="Outbound">Outbound</option>
                                        </select>
                                    </div>
                                    <div>
                                        <div class="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">Status</div>
                                        <select v-model="filters.status" class="w-full h-9 bg-white border border-slate-200 rounded-xl px-3 text-xs outline-none focus:border-cyan-500 focus:ring-4 focus:ring-cyan-500/10">
                                            <option value="">All statuses</option>
                                            <option v-for="status in statusOptions" :key="status" :value="status">{{ status }}</option>
                                        </select>
                                    </div>
                                    <div>
                                        <div class="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">Root Doctype</div>
                                        <select v-model="filters.rootDoctype" class="w-full h-9 bg-white border border-slate-200 rounded-xl px-3 text-xs outline-none focus:border-cyan-500 focus:ring-4 focus:ring-cyan-500/10">
                                            <option value="">All doctypes</option>
                                            <option v-for="doctype in rootDoctypeOptions" :key="doctype" :value="doctype">{{ doctype }}</option>
                                        </select>
                                    </div>
                                    <div>
                                        <div class="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">Owner</div>
                                        <select v-model="filters.owner" class="w-full h-9 bg-white border border-slate-200 rounded-xl px-3 text-xs outline-none focus:border-cyan-500 focus:ring-4 focus:ring-cyan-500/10">
                                            <option value="">All owners</option>
                                            <option v-for="owner in ownerOptions" :key="owner" :value="owner">{{ owner }}</option>
                                        </select>
                                    </div>
                                    <label class="flex items-center gap-3 h-9 px-3 rounded-xl bg-white border border-slate-200 text-xs font-semibold text-slate-600 cursor-pointer">
                                        <input type="checkbox" v-model="filters.paymentPendingOnly" class="rounded border-slate-300 text-cyan-600 focus:ring-cyan-500">
                                        <span>Payment Pending</span>
                                    </label>
                                    <label class="flex items-center gap-3 h-9 px-3 rounded-xl bg-white border border-slate-200 text-xs font-semibold text-slate-600 cursor-pointer">
                                        <input type="checkbox" v-model="filters.openSavOnly" class="rounded border-slate-300 text-cyan-600 focus:ring-cyan-500">
                                        <span>Open SAV</span>
                                    </label>
                                    <label class="flex items-center gap-3 h-9 px-3 rounded-xl bg-white border border-slate-200 text-xs font-semibold text-slate-600 cursor-pointer">
                                        <input type="checkbox" v-model="filters.qcPendingOnly" class="rounded border-slate-300 text-cyan-600 focus:ring-cyan-500">
                                        <span>QC Pending</span>
                                    </label>
                                </div>

                                <div class="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                                    <div class="flex flex-wrap items-center gap-2">
                                        <span class="text-[10px] font-bold uppercase tracking-widest text-slate-400">Display</span>
                                        <label class="flex items-center gap-2 h-8 px-3 rounded-full bg-white border border-slate-200 text-[11px] font-semibold text-slate-600 cursor-pointer">
                                            <input type="checkbox" v-model="filters.hideDraft" class="rounded border-slate-300 text-cyan-600 focus:ring-cyan-500">
                                            <span>Hide Draft</span>
                                        </label>
                                    </div>
                                    <div v-if="view === 'trace'" class="flex flex-wrap items-center gap-2">
                                        <span class="text-[10px] font-bold uppercase tracking-widest text-slate-400">Trace</span>
                                        <label class="flex items-center gap-2 h-8 px-3 rounded-full bg-white border border-slate-200 text-[11px] font-semibold text-slate-600 cursor-pointer">
                                            <input type="checkbox" v-model="filters.hideCancelled" class="rounded border-slate-300 text-cyan-600 focus:ring-cyan-500">
                                            <span>Hide Cancelled</span>
                                        </label>
                                        <label class="flex items-center gap-2 h-8 px-3 rounded-full bg-white border border-slate-200 text-[11px] font-semibold text-slate-600 cursor-pointer">
                                            <input type="checkbox" v-model="filters.mainSpineOnly" class="rounded border-slate-300 text-cyan-600 focus:ring-cyan-500">
                                            <span>Main Spine Only</span>
                                        </label>
                                    </div>
                                    <div class="flex justify-end">
                                        <button @click="resetFilters" class="h-9 px-3 rounded-xl bg-white border border-slate-200 text-xs font-bold text-slate-600 hover:border-cyan-200 hover:text-cyan-700 transition-all">
                                            Reset Filters
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="flex-1 flex overflow-hidden">
                    <!-- Pipeline View -->
                    <div v-show="view === 'pipeline'" class="flex-1 flex gap-4 px-8 py-6 overflow-x-auto snap-x pb-2">
                        <div v-for="stage in columnsWithCounts" :key="stage.key" class="flex-none w-72 snap-start flex flex-col">
                            <div class="flex items-center justify-between mb-4 px-2">
                                <div class="flex items-center gap-2">
                                    <div class="w-1 h-4 bg-[#00b0c8] rounded-full"></div>
                                    <h3 class="text-xs font-black text-slate-500 uppercase tracking-widest">{{ stage.label }}</h3>
                                </div>
                                <span :class="cn(
                                    'px-2 py-0.5 rounded-full text-[10px] font-black font-mono',
                                    stage.count > 5 ? 'bg-rose-50 text-rose-600' : 'bg-slate-200 text-slate-600'
                                )">{{ stage.count }}</span>
                            </div>

                            <div class="flex-1 space-y-3 overflow-y-auto pr-2">
                                <div v-if="loading" class="text-center py-12 text-slate-400 text-xs">Loading...</div>
                                <DealCard
                                    v-for="deal in visibleDeals.filter(d => d.stage === stage.key)"
                                    :key="deal.id"
                                    :deal="deal"
                                    :selected="selectedDeal && selectedDeal.id === deal.id"
                                    @select="selectDeal"
                                />
                                <div v-if="!loading && visibleDeals.filter(d => d.stage === stage.key).length === 0" class="text-center py-8 text-slate-300 text-xs">
                                    No deals
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Trace Panel (Slide-in) -->
                    <transition name="slide-right">
                        <div v-if="selectedDeal && view === 'pipeline'" class="w-[760px] xl:w-[860px] bg-white border-l border-border-mid shadow-2xl z-40 flex flex-col shrink-0">
                            <div class="p-6 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                                <div>
                                    <h2 class="font-semibold text-xl font-bold text-slate-900 tracking-tight">Document Trace</h2>
                                    <div class="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-widest mt-1">
                                        {{ selectedDeal.id }} · {{ selectedDeal.customer }}
                                    </div>
                                </div>
                                <div class="flex items-center gap-2">
                                    <button
                                        @click="view = 'trace'"
                                        class="flex items-center gap-2 px-3 py-1.5 bg-[#00b0c8] text-white text-[10px] font-bold rounded-lg hover:bg-[#0097ad] transition-all">
                                        <span>Full Trace</span>
                                    </button>
                                    <button
                                        @click="selectedDeal = null"
                                        class="p-2 hover:bg-slate-200 rounded-xl transition-colors text-slate-400">
                                        ✕
                                    </button>
                                </div>
                            </div>

                            <div class="flex-1 overflow-y-auto p-6 space-y-8">
                                <div v-if="traceLoading" class="text-center py-12 text-slate-400 text-xs">Loading trace...</div>
                                <template v-else-if="activeTraceData">
                                    <div v-if="selectedTraceAlerts.length" class="flex flex-wrap gap-2">
                                        <span v-for="alert in selectedTraceAlerts" :key="alert.label" :class="cn('px-3 py-1 rounded-full text-[10px] font-bold border', traceAlertClass(alert.tone))">
                                            {{ alert.label }}
                                        </span>
                                    </div>

                                    <!-- Spine -->
                                    <div class="relative">
                                        <div class="flex items-center gap-3 mb-6">
                                            <div class="w-1 h-4 bg-[#00b0c8] rounded-full"></div>
                                            <h3 class="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Lineage Spine</h3>
                                        </div>
                                        <div class="bg-white border border-slate-100 rounded-2xl p-6 shadow-sm">
                                            <SpineNode v-if="activeProjectedTree" :key="'slide-trace-' + traceRenderKey" :node="activeProjectedTree" :on-open="openDocPreview" :focused-id="focusedTraceNodeId" />
                                        </div>
                                    </div>

                                    <!-- Smart Link Registry -->
                                    <div class="space-y-4">
                                        <div class="flex items-center justify-between">
                                            <h3 class="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Smart Link Registry</h3>
                                        </div>
                                        <div class="grid grid-cols-1 gap-2">
                                            <div v-for="(edge, i) in (activeTraceData.edges || []).slice(0, 15)" :key="i"
                                                class="flex items-center gap-3 p-3 bg-slate-50 rounded-xl border border-slate-100 group hover:border-cyan-200 transition-colors">
                                                <div class="w-8 h-8 rounded-lg bg-white border border-slate-200 flex items-center justify-center shadow-sm">
                                                    <span class="text-slate-400 text-xs">→</span>
                                                </div>
                                                <div class="flex-1 min-w-0">
                                                    <div class="flex items-center gap-2">
                                                        <span class="text-[10px] font-bold text-slate-700">
                                                            {{ DOC_REGISTRY[(activeTraceData.nodes.find(n => n.id === edge.from) || {}).type]?.label || edge.from }}
                                                        </span>
                                                        <span class="text-slate-300 text-xs">→</span>
                                                        <span class="text-[10px] font-bold text-slate-700">
                                                            {{ DOC_REGISTRY[(activeTraceData.nodes.find(n => n.id === edge.to) || {}).type]?.label || edge.to }}
                                                        </span>
                                                    </div>
                                                    <p class="text-[9px] text-slate-400 mt-0.5">{{ edge.relation }}</p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    <!-- Communications -->
                                    <div class="space-y-4">
                                        <div class="flex items-center justify-between">
                                            <h3 class="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Communications</h3>
                                        </div>
                                        <div class="space-y-2">
                                            <template v-if="(activeTraceData.nodes || []).filter(n => n.type === 'COMMUNICATION').length > 0">
                                                <div v-for="comm in (activeTraceData.nodes || []).filter(n => n.type === 'COMMUNICATION')" :key="comm.id"
                                                    class="p-3 bg-white border border-slate-100 rounded-xl shadow-sm hover:shadow-md transition-shadow">
                                                    <div class="flex items-center justify-between mb-1">
                                                        <span class="text-[8px] font-black text-cyan-700 uppercase tracking-widest">Email</span>
                                                        <span class="text-[9px] text-slate-400">{{ comm.date }}</span>
                                                    </div>
                                                    <div class="text-[10px] font-bold text-slate-800">{{ comm.title }}</div>
                                                    <div class="text-[9px] text-slate-500 mt-1">Ref: {{ comm.id }}</div>
                                                </div>
                                            </template>
                                            <div v-else class="p-4 text-center border border-dashed border-slate-200 rounded-xl">
                                                <p class="text-[10px] text-slate-400">No linked communications found</p>
                                            </div>
                                        </div>
                                    </div>
                                </template>
                            </div>

                            <div class="p-6 border-t border-slate-100 bg-white flex gap-3">
                                <button @click="openInERPNext"
                                    class="flex-1 flex items-center justify-center gap-2 py-3 bg-slate-900 text-white text-xs font-bold rounded-xl hover:bg-slate-800 transition-all shadow-lg shadow-slate-200">
                                    <span>{{ selectedOpenLabel }}</span>
                                </button>
                            </div>
                        </div>
                    </transition>

                    <!-- Full Trace View -->
                    <div v-show="view === 'trace'" class="flex-1 flex flex-col bg-white">
                        <div class="flex-1 flex overflow-hidden">
                            <!-- Sidebar -->
                            <div class="w-96 xl:w-[28rem] border-r border-slate-100 flex flex-col bg-white">
                                <div class="p-6 border-b border-slate-100">
                                    <div class="flex items-start justify-between gap-4 mb-4">
                                        <div>
                                            <h3 class="font-semibold text-lg font-bold">Entity Tracer</h3>
                                            <p class="text-[11px] text-slate-500 mt-1">Select any document on the left. The full lineage spine stays on the right.</p>
                                        </div>
                                        <div class="text-right text-[10px] text-slate-400 uppercase tracking-widest">{{ searchedDeals.length }} entities</div>
                                    </div>
                                    <div class="relative">
                                        <input
                                            type="text"
                                            v-model="searchQuery"
                                            placeholder="Search deals..."
                                            class="w-full h-8 bg-slate-50 border border-slate-100 rounded-lg pl-9 pr-3 text-[11px] outline-none focus:ring-2 focus:ring-cyan-500/10 focus:border-cyan-500">
                                    </div>
                                </div>
                                <div class="flex-1 overflow-y-auto">
                                    <div v-if="loading" class="p-4 text-center text-slate-400 text-xs">Loading...</div>
                                    <div
                                        v-for="deal in searchedDeals"
                                        :key="deal.id"
                                        @click="selectDeal(deal)"
                                        :class="cn(
                                            'p-4 border-b border-slate-50 cursor-pointer transition-all hover:bg-slate-50',
                                            selectedDeal && selectedDeal.id === deal.id && 'bg-cyan-50 border-r-4 border-r-[#00b0c8]'
                                        )">
                                        <div class="flex items-start justify-between gap-3 mb-2">
                                            <div class="flex items-center gap-2 min-w-0">
                                                <div :class="cn('w-2 h-2 rounded-full shrink-0',
                                                    deal.healthScore > 80 ? 'bg-emerald-500' : deal.healthScore > 50 ? 'bg-amber-500' : 'bg-rose-500')"></div>
                                                <span class="text-xs font-bold text-slate-900 truncate">{{ deal.customer || deal.id }}</span>
                                            </div>
                                        </div>
                                        <div class="flex items-center justify-between gap-3">
                                            <div class="text-[10px] font-mono text-slate-400 truncate">{{ deal.id }}</div>
                                            <div class="text-[10px] text-slate-400 shrink-0">{{ deal.date }}</div>
                                        </div>
                                        <div class="mt-2 flex items-center gap-2 text-[10px] text-slate-500">
                                            <span class="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-semibold">{{ deal.doctype }}</span>
                                            <span v-if="deal.status" :class="cn('px-2 py-0.5 rounded-md text-[9px] font-bold border', statusPillClass(deal.status))">{{ deal.status }}</span>
                                        </div>
                                    </div>
                                    <div v-if="!loading && !searchedDeals.length" class="p-6 text-center text-slate-400 text-xs">No entities found</div>
                                </div>
                            </div>

                            <!-- Main Graph Area -->
                            <div class="flex-1 bg-slate-50/50 p-8 overflow-y-auto">
                                <div v-if="!selectedDeal" class="h-full flex flex-col items-center justify-center text-center space-y-4">
                                    <div class="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center text-3xl">🗺</div>
                                    <h3 class="font-semibold text-xl font-bold text-slate-400">No entity available</h3>
                                    <p class="text-sm text-slate-300 max-w-xs">The left panel will automatically open the first matching entity when results exist.</p>
                                </div>

                                <div v-else-if="!traceLoading && activeTraceData" class="max-w-6xl mx-auto space-y-8">
                                    <div class="flex items-end justify-between">
                                        <div>
                                            <h2 class="font-semibold text-3xl font-bold tracking-tight text-slate-900">{{ selectedDeal.customer }}</h2>
                                            <div class="flex items-center gap-3 mt-2 flex-wrap">
                                                <span class="text-xs font-mono font-bold text-cyan-700 bg-cyan-50 px-2 py-0.5 rounded">{{ selectedDeal.id }}</span>
                                                <span v-if="selectedDeal.status" :class="cn('px-2 py-0.5 rounded-md text-[10px] font-bold border', statusPillClass(selectedDeal.status))">{{ selectedDeal.status }}</span>
                                                <span class="text-xs text-slate-400 font-medium">Lineage Trace & Value Flow</span>
                                            </div>
                                            <div v-if="selectedTraceAlerts.length" class="flex flex-wrap gap-2 mt-4">
                                                <span v-for="alert in selectedTraceAlerts" :key="alert.label" :class="cn('px-3 py-1 rounded-full text-[10px] font-bold border', traceAlertClass(alert.tone))">
                                                    {{ alert.label }}
                                                </span>
                                            </div>
                                            <div v-if="selectedTraceMetaCards.length" class="grid grid-cols-2 xl:grid-cols-4 gap-3 mt-4">
                                                <div v-for="card in selectedTraceMetaCards" :key="card.label" :class="cn('bg-white border rounded-xl px-3 py-2 shadow-sm', traceAlertClass(card.tone))">
                                                    <div class="text-[9px] font-bold uppercase tracking-widest opacity-70 mb-1">{{ card.label }}</div>
                                                    <div class="text-sm font-black font-mono text-slate-900">{{ card.value }}</div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    <div class="space-y-8">
                                            <div class="bg-white border border-slate-100 rounded-3xl p-10 shadow-sm">
                                                <div class="flex items-center gap-3 mb-8">
                                                    <div class="w-1 h-5 bg-[#00b0c8] rounded-full"></div>
                                                    <h3 class="text-xs font-black text-slate-400 uppercase tracking-[0.2em]">Lineage Spine</h3>
                                                </div>
                                                <SpineNode v-if="activeProjectedTree" :key="'full-trace-' + traceRenderKey" :node="activeProjectedTree" :on-open="openDocPreview" :focused-id="focusedTraceNodeId" />
                                             </div>
                                     </div>
                                </div>

                                <div v-else-if="traceLoading" class="h-full flex items-center justify-center">
                                    <div class="text-center">
                                        <div class="inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mb-3"></div>
                                        <div class="text-sm text-slate-400">Loading trace...</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    </div>
                </main>
            </div>
        `
    }).mount("#op-vue-root");
}

// ── CSS Injection ──────────────────────────────────────────────────────────

function injectPipelineStyles() {
    if (document.getElementById("op-pipeline-vue-styles")) return;

    const style = document.createElement("style");
    style.id = "op-pipeline-vue-styles";
    style.textContent = `
        /* Slide-right transition for trace panel */
        .slide-right-enter-active,
        .slide-right-leave-active {
            transition: transform 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        }
        .slide-right-enter-from,
        .slide-right-leave-to {
            transform: translateX(100%);
        }

        /* Custom scrollbar */
        .overflow-y-auto::-webkit-scrollbar { width: 4px; }
        .overflow-y-auto::-webkit-scrollbar-track { background: transparent; }
        .overflow-y-auto::-webkit-scrollbar-thumb { background: #e2e8f0; border-radius: 10px; }
        .overflow-y-auto::-webkit-scrollbar-thumb:hover { background: #cbd5e0; }

        /* Horizontal scrollbar for pipeline */
        .overflow-x-auto::-webkit-scrollbar { height: 4px; }
        .overflow-x-auto::-webkit-scrollbar-track { background: transparent; }
        .overflow-x-auto::-webkit-scrollbar-thumb { background: #e2e8f0; border-radius: 10px; }

        /* Inline SVG icon sizing */
        span svg { width: 1em; height: 1em; vertical-align: -0.125em; }
    `;
    document.head.appendChild(style);
}

injectPipelineStyles();
