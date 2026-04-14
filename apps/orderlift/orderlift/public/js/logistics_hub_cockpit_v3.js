/* =============================================================================
   Logistics Hub Cockpit v2 — Vanilla JS IIFE Workspace Bundle
   Exports: window.orderliftCockpitV2.mount(root, options)
   ============================================================================= */
(function (global) {
    "use strict";

    /* ── SVG icon helpers ─────────────────────────────────────────────────── */
    const SVG = {
        truck: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="3" width="15" height="13"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>`,
        dashboard: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>`,
        package: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="16.5" y1="9.4" x2="7.5" y2="4.21"/><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>`,
        trending: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>`,
        bell: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>`,
        user: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`,
        search: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>`,
        mapPin: `<svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>`,
        calendar: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`,
        container: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>`,
        magic: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="14.5 17.5 3 6 3 3 6 3 17.5 14.5"/><line x1="13" y1="19" x2="19" y2="13"/><line x1="16" y1="16" x2="20" y2="20"/><line x1="19" y1="21" x2="21" y2="19"/></svg>`,
        zap: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
        alertTriangle: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
        checkCircle: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
        clock: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
        weight: `<svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="5" r="3"/><path d="M6.5 8a2 2 0 0 0-1.905 1.46L2.1 18.5A2 2 0 0 0 4 21h16a2 2 0 0 0 1.925-2.54L19.4 9.5A2 2 0 0 0 17.48 8Z"/></svg>`,
        cube: `<svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>`,
        x: `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
        plus: `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>`,
    };

    /* ── Helpers ──────────────────────────────────────────────────────────── */
    function esc(s) {
        return (frappe && frappe.utils) ? frappe.utils.escape_html(String(s || "")) : String(s || "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    }
    function __(s, r) { return (global.__ || (x => x))(s, r); }
    function flt(v) { return Number(v || 0); }

    /* ── Status helpers ───────────────────────────────────────────────────── */
    function statusClass(status) {
        const s = String(status || "").toLowerCase().replace(/_/g, "-").replace(/\s+/g, "-");
        const map = {
            "planning": "planning",
            "ready": "ready",
            "loading": "loading",
            "in-transit": "in-transit",
            "delivered": "delivered",
            "cancelled": "cancelled",
            "ok": "ok",
            "over-capacity": "over-capacity",
            "incomplete-data": "incomplete",
            "incomplete": "incomplete",
        };
        return "clpv2-status " + ("clpv2-status-" + (map[s] || "planning"));
    }

    function analysisClass(status) {
        const s = String(status || "").toLowerCase();
        if (s === "over_capacity") return "danger";
        if (s === "incomplete_data") return "warn";
        return "ok";
    }

    function gaugeColorClass(pct) {
        if (pct >= 95) return "danger";
        if (pct >= 75) return "warn";
        return "";
    }

    function gaugeFillClass(pct) {
        if (pct >= 95) return "danger";
        if (pct >= 75) return "warn";
        return "blue";
    }

    function daysUntil(dateStr) {
        if (!dateStr) return null;
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const dep = new Date(dateStr);
        dep.setHours(0, 0, 0, 0);
        return Math.round((dep - today) / 86400000);
    }

    function formatDaysLabel(days) {
        return days === 1 ? __("1 day") : `${days} ${__("days")}`;
    }

    function formatDepartureSoon(days) {
        return days === 1
            ? __("This container departs in 1 day.")
            : `${__("This container departs in")} ${days} ${__("days")}.`;
    }

    function efficiencyPct(weightPct, volumePct) {
        return Math.round((flt(weightPct) + flt(volumePct)) / 2);
    }

    /* ── CSS loader ───────────────────────────────────────────────────────── */
    function ensureStylesheet(id, href) {
        if (document.getElementById(id)) return Promise.resolve();
        return new Promise((resolve, reject) => {
            const link = document.createElement("link");
            link.id = id;
            link.rel = "stylesheet";
            link.href = href;
            link.onload = resolve;
            link.onerror = () => reject(new Error("Failed to load " + href));
            document.head.appendChild(link);
        });
    }

    /* ══════════════════════════════════════════════════════════════════════
       CockpitV2 — main class
       ══════════════════════════════════════════════════════════════════════ */
    class CockpitV2 {
        constructor(root, options) {
            this.root = root;
            this.options = options || {};

            // State
            this.plans = [];
            this.selectedPlanId = this.options.preloadPlan || null;
            this.cockpitData = null;
            this.activeTab = "overview";
            this.sidebarQuery = "";
            this.manageQuery = "";
            this._realtimeHandler = null;
            this._subscribedPlan = null;

            this._renderShell();
            this._bindSidebarSearch();
            this._loadAllPlans();
        }

        /* ── Shell HTML ──────────────────────────────────────────────────── */
        _renderShell() {
            this.root.innerHTML = `
                <div class="clpv2-root" id="clpv2-root">

                    <!-- Panel 1: Icon Nav -->
                    <nav class="clpv2-icon-nav">
                        <div class="clpv2-nav-logo" title="Orderlift Logistics">
                            ${SVG.truck}
                        </div>
                        <div class="clpv2-nav-items">
                            <button class="clpv2-nav-btn active" title="${__("Cockpit")}" data-nav="cockpit">
                                ${SVG.dashboard}
                            </button>
                            <button class="clpv2-nav-btn" title="${__("Load Plans")}" data-nav="list">
                                ${SVG.package}
                            </button>
                            <button class="clpv2-nav-btn" title="${__("Analytics")}" data-nav="analytics">
                                ${SVG.trending}
                            </button>
                        </div>
                        <div class="clpv2-nav-footer">
                            <button class="clpv2-nav-btn clpv2-nav-bell" title="${__("Notifications")}">
                                ${SVG.bell}
                            </button>
                            <div class="clpv2-nav-avatar" title="${__("User")}">
                                ${SVG.user}
                            </div>
                        </div>
                    </nav>

                    <!-- Panel 2: Timeline Sidebar -->
                    <aside class="clpv2-sidebar">
                        <div class="clpv2-sidebar-header">
                            <p class="clpv2-sidebar-title">${__("Load Plans")}</p>
                            <div class="clpv2-search-wrap">
                                <span class="clpv2-search-icon">${SVG.search}</span>
                                <input id="clpv2-sidebar-search" class="clpv2-search-input" placeholder="${__("Search plans...")}" />
                            </div>
                        </div>
                        <div id="clpv2-timeline-list" class="clpv2-timeline-list clpv2-scroll"></div>
                    </aside>

                    <!-- Panel 3: Main Content -->
                    <main class="clpv2-main">
                        <div id="clpv2-header" class="clpv2-header">
                            <div class="clpv2-header-left">
                                <div class="clpv2-header-icon">${SVG.container}</div>
                                <div>
                                    <div class="clpv2-header-title" id="clpv2-header-title">${__("Select a Load Plan")}</div>
                                    <div class="clpv2-header-sub" id="clpv2-header-sub"></div>
                                </div>
                            </div>
                            <div class="clpv2-tabs" id="clpv2-tabs" style="display:none;">
                                <button class="clpv2-tab active" data-tab="overview">${__("Overview")}</button>
                                <button class="clpv2-tab" data-tab="manage">${__("Manage")}</button>
                            </div>
                            <div class="clpv2-header-right" id="clpv2-header-actions" style="display:none;">
                                <button class="clpv2-btn clpv2-btn-ghost" id="clpv2-btn-autosuggest">
                                    ${SVG.magic} ${__("Auto-Suggest")}
                                </button>
                                <button class="clpv2-btn clpv2-btn-primary" id="clpv2-btn-analysis">
                                    ${SVG.zap} ${__("Run Analysis")}
                                </button>
                            </div>
                        </div>
                        <div id="clpv2-content-area" class="clpv2-content clpv2-scroll">
                            ${this._noSelectionHtml()}
                        </div>
                    </main>
                </div>
            `;

            // Bind nav buttons
            this.root.querySelectorAll("[data-nav]").forEach(btn => {
                btn.addEventListener("click", () => this._handleNavClick(btn.dataset.nav));
            });

            // Bind tab pills
            this.root.querySelectorAll("[data-tab]").forEach(btn => {
                btn.addEventListener("click", () => this._switchTab(btn.dataset.tab));
            });

            // Bind action buttons
            const autoBtn = this.root.querySelector("#clpv2-btn-autosuggest");
            const analysisBtn = this.root.querySelector("#clpv2-btn-analysis");
            if (autoBtn) autoBtn.addEventListener("click", () => this._autoSuggest());
            if (analysisBtn) analysisBtn.addEventListener("click", () => this._runAnalysis());
        }

        _noSelectionHtml() {
            return `
                <div class="clpv2-empty" style="margin-top: 60px;">
                    <div class="clpv2-empty-icon">${SVG.package}</div>
                    <div class="clpv2-empty-title">${__("No plan selected")}</div>
                    <div class="clpv2-empty-hint">${__("Pick a container load plan from the timeline on the left to get started.")}</div>
                </div>
            `;
        }

        /* ── Nav ─────────────────────────────────────────────────────────── */
        _handleNavClick(nav) {
            if (nav === "list") {
                frappe.set_route("List", "Container Load Plan");
            } else if (nav === "analytics") {
                this._showAnalytics();
            }
            // "cockpit" = no-op (already here)
        }

        /* ── Sidebar search ──────────────────────────────────────────────── */
        _bindSidebarSearch() {
            // Will be bound after root is in DOM; use event delegation
            this.root.addEventListener("input", (e) => {
                if (e.target.id === "clpv2-sidebar-search") {
                    this.sidebarQuery = e.target.value.trim().toLowerCase();
                    this._renderTimeline();
                }
            });
        }

        /* ── Load all plans ──────────────────────────────────────────────── */
        async _loadAllPlans() {
            try {
                const r = await frappe.call({
                    method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.get_load_plans_list",
                    freeze: false,
                });
                this.plans = r.message || [];
                this._renderTimeline();

                // Auto-select preload plan or first plan
                if (this.selectedPlanId) {
                    this._selectPlan(this.selectedPlanId);
                } else if (this.plans.length) {
                    this._selectPlan(this.plans[0].name);
                }
            } catch (err) {
                console.error("CockpitV2: failed to load plans", err);
            }
        }

        /* ── Timeline sidebar ────────────────────────────────────────────── */
        _renderTimeline() {
            const list = this.root.querySelector("#clpv2-timeline-list");
            if (!list) return;

            const query = this.sidebarQuery;
            const filtered = query
                ? this.plans.filter(p =>
                    String(p.container_label || p.name || "").toLowerCase().includes(query) ||
                    String(p.destination_zone || "").toLowerCase().includes(query) ||
                    String(p.departure_date || "").includes(query)
                )
                : this.plans;

            if (!filtered.length) {
                list.innerHTML = `
                    <div class="clpv2-manage-empty" style="padding-top:40px;">
                        <div class="clpv2-manage-empty-icon">📦</div>
                        <div class="clpv2-manage-empty-label">${__("No plans found")}</div>
                        <div class="clpv2-manage-empty-hint">${__("Try a different search term")}</div>
                    </div>
                `;
                return;
            }

            list.innerHTML = filtered.map((plan, idx) => {
                const isSelected = plan.name === this.selectedPlanId;
                const isLast = idx === filtered.length - 1;
                const weightPct = flt(plan.weight_utilization_pct);
                const volumePct = flt(plan.volume_utilization_pct);

                return `
                    <div class="clpv2-timeline-item${isSelected ? " selected" : ""}" data-plan="${esc(plan.name)}">
                        ${!isLast ? `<div class="clpv2-timeline-line"></div>` : ""}
                        <div class="clpv2-timeline-dot"></div>
                        <button class="clpv2-plan-card" data-plan="${esc(plan.name)}">
                            <div class="clpv2-plan-card-top">
                                <span class="clpv2-plan-date">${esc(plan.departure_date || "—")}</span>
                                <span class="${statusClass(plan.status)}">${esc(plan.status || "planning")}</span>
                            </div>
                            <div class="clpv2-plan-name">${esc(plan.container_label || plan.name)}</div>
                            ${plan.destination_zone ? `
                                <div class="clpv2-plan-dest">
                                    ${SVG.mapPin}
                                    <span>${esc(plan.destination_zone)}</span>
                                </div>` : ""}
                            <div class="clpv2-plan-bars">
                                <div class="clpv2-plan-bar-wrap" title="${__("Weight")} ${weightPct.toFixed(1)}%">
                                    <div class="clpv2-plan-bar-fill weight" style="width:${Math.min(weightPct, 100)}%"></div>
                                </div>
                                <div class="clpv2-plan-bar-wrap" title="${__("Volume")} ${volumePct.toFixed(1)}%">
                                    <div class="clpv2-plan-bar-fill volume" style="width:${Math.min(volumePct, 100)}%"></div>
                                </div>
                            </div>
                        </button>
                    </div>
                `;
            }).join("");

            // Bind plan card clicks
            list.querySelectorAll("[data-plan]").forEach(el => {
                el.addEventListener("click", () => this._selectPlan(el.dataset.plan));
            });
        }

        /* ── Select a plan ───────────────────────────────────────────────── */
        async _selectPlan(planId) {
            if (this.selectedPlanId === planId && this.cockpitData) return;

            this.selectedPlanId = planId;
            this._renderTimeline(); // update selected state in sidebar
            this._showSkeleton();

            // Unsubscribe from previous realtime
            this._unsubscribeRealtime();

            try {
                const r = await frappe.call({
                    method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.get_cockpit_data",
                    args: { load_plan_name: planId },
                    freeze: false,
                });
                this.cockpitData = r.message || {};
                this._renderPlanHeader(this.cockpitData.plan || {});
                this._renderCurrentTab();
                this._subscribeRealtime();
            } catch (err) {
                console.error("CockpitV2: failed to load cockpit data", err);
                frappe.show_alert({ message: __("Failed to load plan data"), indicator: "red" });
            }
        }

        /* ── Plan header ─────────────────────────────────────────────────── */
        _renderPlanHeader(plan) {
            const titleEl = this.root.querySelector("#clpv2-header-title");
            const subEl = this.root.querySelector("#clpv2-header-sub");
            const tabsEl = this.root.querySelector("#clpv2-tabs");
            const actionsEl = this.root.querySelector("#clpv2-header-actions");

            if (titleEl) titleEl.textContent = plan.container_label || this.selectedPlanId || "";
            if (subEl) subEl.textContent = [plan.name || this.selectedPlanId, plan.container_profile_label].filter(Boolean).join(" · ");
            if (tabsEl) tabsEl.style.display = "";
            if (actionsEl) actionsEl.style.display = "";
        }

        /* ── Tab switching ───────────────────────────────────────────────── */
        _switchTab(tab) {
            this.activeTab = tab;
            this.root.querySelectorAll("[data-tab]").forEach(btn => {
                btn.classList.toggle("active", btn.dataset.tab === tab);
            });
            this._renderCurrentTab();
        }

        _renderCurrentTab() {
            if (this.activeTab === "manage") {
                this._renderManageTab();
            } else {
                this._renderOverviewTab();
            }
        }

        /* ── Skeleton ────────────────────────────────────────────────────── */
        _showSkeleton() {
            const area = this.root.querySelector("#clpv2-content-area");
            if (!area) return;
            const skItem = (w = "100%") => `<div class="ol-skeleton-line" style="height:12px;width:${w};border-radius:4px;background:linear-gradient(90deg,#edf2f7 25%,#e2e8f0 50%,#edf2f7 75%);background-size:200% 100%;animation:ol-shimmer 1.4s infinite;margin-bottom:8px;"></div>`;
            area.innerHTML = `
                <div style="padding:4px 0 20px;">
                    <div style="display:grid;grid-template-columns:1fr 1fr 2fr;gap:16px;margin-bottom:24px;">
                        ${[1,2,3].map(() => `<div class="ol-skeleton-card" style="border:1px solid #e8eef5;border-radius:18px;padding:20px;background:#fff;">${skItem("40%")}${skItem("60%")}${skItem("80%")}</div>`).join("")}
                    </div>
                    <div style="display:grid;grid-template-columns:1fr 340px;gap:20px;">
                        <div class="ol-skeleton-card" style="border:1px solid #e8eef5;border-radius:18px;padding:20px;background:#fff;">
                            ${[1,2,3,4].map(() => skItem()).join("")}
                        </div>
                        <div>
                            <div class="ol-skeleton-card" style="border:1px solid #e8eef5;border-radius:18px;padding:20px;background:#fff;margin-bottom:16px;">${skItem("70%")}${skItem("50%")}</div>
                            <div class="ol-skeleton-card" style="border:1px solid #e8eef5;border-radius:18px;padding:20px;background:#fff;">${skItem("70%")}${skItem("50%")}</div>
                        </div>
                    </div>
                </div>
            `;
        }

        /* ── Overview Tab ────────────────────────────────────────────────── */
        _renderOverviewTab() {
            const plan = (this.cockpitData && this.cockpitData.plan) || {};
            const shipments = (this.cockpitData && this.cockpitData.shipments) || [];
            const area = this.root.querySelector("#clpv2-content-area");
            if (!area) return;

            const weightPct = flt(plan.weight_utilization_pct);
            const volumePct = flt(plan.volume_utilization_pct);
            const maxWeight = flt(plan.max_weight_kg);
            const maxVolume = flt(plan.max_volume_m3);
            const usedWeight = flt(plan.total_weight_kg);
            const usedVolume = flt(plan.total_volume_m3);
            const days = daysUntil(plan.departure_date);
            const daysLabel = days === null ? __("—")
                : days < 0 ? __("Departed")
                : days === 0 ? __("Today")
                : days === 1 ? __("Tomorrow")
                : formatDaysLabel(days);
            const daysClass = days !== null && days <= 3 ? "warn" : days !== null && days < 0 ? "danger" : "";
            const analysisStatusCls = analysisClass(plan.analysis_status);
            const efficiency = efficiencyPct(weightPct, volumePct);
            const effClass = efficiency >= 80 ? "ok" : efficiency >= 50 ? "warn" : "danger";
            const limitFactor = plan.limiting_factor || "—";

            // KPI row
            const kpiHtml = `
                <div class="clpv2-kpi-row">
                    <!-- Departure card -->
                    <div class="clpv2-kpi-card">
                        <div class="clpv2-kpi-card-top">
                            <div>
                                <div class="clpv2-kpi-eyebrow">${__("Departure")}</div>
                                <div class="clpv2-kpi-value" style="font-size:20px;">${esc(plan.departure_date || "—")}</div>
                            </div>
                            <div class="clpv2-kpi-icon clpv2-kpi-icon-blue">${SVG.calendar}</div>
                        </div>
                        <div class="clpv2-kpi-sub ${daysClass}">${SVG.clock} ${daysLabel}</div>
                    </div>

                    <!-- Shipments card -->
                    <div class="clpv2-kpi-card">
                        <div class="clpv2-kpi-card-top">
                            <div>
                                <div class="clpv2-kpi-eyebrow">${__("Shipments")}</div>
                                <div class="clpv2-kpi-value">${shipments.length}</div>
                            </div>
                            <div class="clpv2-kpi-icon clpv2-kpi-icon-indigo">${SVG.package}</div>
                        </div>
                        <div class="clpv2-kpi-sub ${analysisStatusCls}">
                            ${analysisStatusCls === "ok" ? SVG.checkCircle : SVG.alertTriangle}
                            ${esc(plan.analysis_status || "ok")}
                        </div>
                    </div>

                    <!-- Utilization card (spans 2 col) -->
                    <div class="clpv2-kpi-card">
                        <div class="clpv2-kpi-card-top" style="margin-bottom:12px;">
                            <div class="clpv2-kpi-eyebrow">${__("Utilization")}</div>
                            <div class="clpv2-kpi-icon clpv2-kpi-icon-slate">${SVG.trending}</div>
                        </div>
                        <div class="clpv2-util-grid">
                            <div>
                                <div class="clpv2-gauge-label-row">
                                    <span class="clpv2-gauge-label">${SVG.weight} ${__("Weight")}</span>
                                    <span class="clpv2-gauge-pct">${weightPct.toFixed(1)}%</span>
                                </div>
                                <div class="clpv2-gauge-track">
                                    <div class="clpv2-gauge-fill ${gaugeFillClass(weightPct)}" style="width:${Math.min(weightPct, 100)}%"></div>
                                </div>
                                <div class="clpv2-gauge-sub"><span>${usedWeight.toFixed(1)} kg</span><span>${maxWeight.toFixed(1)} kg</span></div>
                            </div>
                            <div>
                                <div class="clpv2-gauge-label-row">
                                    <span class="clpv2-gauge-label">${SVG.cube} ${__("Volume")}</span>
                                    <span class="clpv2-gauge-pct">${volumePct.toFixed(1)}%</span>
                                </div>
                                <div class="clpv2-gauge-track">
                                    <div class="clpv2-gauge-fill ${gaugeFillClass(volumePct) === "blue" ? "indigo" : gaugeFillClass(volumePct)}" style="width:${Math.min(volumePct, 100)}%"></div>
                                </div>
                                <div class="clpv2-gauge-sub"><span>${usedVolume.toFixed(1)} m³</span><span>${maxVolume.toFixed(1)} m³</span></div>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            // Shipment rows
            const shipmentsHtml = shipments.length
                ? shipments.map(s => `
                    <div class="clpv2-shipment-card">
                        <div class="clpv2-shipment-icon">${SVG.package}</div>
                        <div class="clpv2-shipment-info">
                            <div class="clpv2-shipment-dn">
                                ${esc(s.delivery_note)}
                                ${Number(s.selected) ? `<span class="${statusClass("ok")}" style="font-size:9px;">${__("incl")}</span>` : ""}
                            </div>
                            <div class="clpv2-shipment-customer">${esc(s.customer || "—")}</div>
                        </div>
                        <div class="clpv2-shipment-metrics">
                            <div class="clpv2-metric-block">
                                <div class="clpv2-metric-value">${SVG.weight} ${flt(s.shipment_weight_kg).toFixed(1)}</div>
                                <div class="clpv2-metric-label">kg</div>
                            </div>
                            <div class="clpv2-metric-block">
                                <div class="clpv2-metric-value">${SVG.cube} ${flt(s.shipment_volume_m3).toFixed(2)}</div>
                                <div class="clpv2-metric-label">m³</div>
                            </div>
                        </div>
                    </div>
                `).join("")
                : `
                    <div class="clpv2-empty">
                        <div class="clpv2-empty-icon">${SVG.package}</div>
                        <div class="clpv2-empty-title">${__("No shipments loaded")}</div>
                        <div class="clpv2-empty-hint">${__("Switch to the Manage tab to add shipments to this container.")}</div>
                    </div>
                `;

            // Optimization card
            const optimizeHtml = `
                <div class="clpv2-optimize-card">
                    <div class="clpv2-optimize-eyebrow">${__("LOAD OPTIMIZATION")}</div>
                    <div class="clpv2-optimize-score-row">
                        <span class="clpv2-optimize-score-label">${__("Efficiency")}</span>
                        <span class="clpv2-optimize-score-value ${effClass}">${efficiency}%</span>
                    </div>
                    <div class="clpv2-optimize-bar-track">
                        <div class="clpv2-optimize-bar-fill ${effClass}" style="width:${Math.min(efficiency, 100)}%"></div>
                    </div>
                    <div class="clpv2-optimize-tip">
                        ${__("Limiting factor")}: <em>${esc(limitFactor)}</em>
                        ${analysisStatusCls === "ok" ? "<br>" + __("Container loading looks optimal.") : ""}
                        ${analysisStatusCls === "warn" ? "<br>" + __("Some shipments may have missing dimension data.") : ""}
                        ${analysisStatusCls === "danger" ? "<br>" + __("Container is over capacity — remove shipments.") : ""}
                    </div>
                </div>
            `;

            // Alerts card
            const alerts = this._buildAlerts(plan, days);
            const alertsHtml = `
                <div class="clpv2-alerts-card">
                    <div class="clpv2-alerts-title">${__("Alerts")}</div>
                    ${alerts.length
                        ? alerts.map(a => `
                            <div class="clpv2-alert ${a.type}">
                                <div class="clpv2-alert-icon">${a.type === "danger" ? SVG.alertTriangle : SVG.alertTriangle}</div>
                                <div>
                                    <div class="clpv2-alert-title">${a.title}</div>
                                    <div class="clpv2-alert-text">${a.text}</div>
                                </div>
                            </div>
                        `).join("")
                        : `<div class="clpv2-no-alerts">${__("No alerts — all good!")}</div>`
                    }
                </div>
            `;

            area.innerHTML = `
                ${kpiHtml}
                <div class="clpv2-content-grid">
                    <div>
                        <div class="clpv2-section-header">
                            <span class="clpv2-section-title">${__("Included Shipments")}</span>
                            <span class="clpv2-section-count">${shipments.length}</span>
                        </div>
                        ${shipmentsHtml}
                    </div>
                    <div class="clpv2-right-panel">
                        ${optimizeHtml}
                        ${alertsHtml}
                    </div>
                </div>
            `;
        }

        _buildAlerts(plan, days) {
            const alerts = [];
            const analysisStatus = String(plan.analysis_status || "").toLowerCase();
            if (analysisStatus === "over_capacity") {
                alerts.push({ type: "danger", title: __("Over Capacity"), text: __("This container exceeds weight or volume limits.") });
            }
            if (analysisStatus === "incomplete_data") {
                alerts.push({ type: "warn", title: __("Incomplete Data"), text: __("Some shipments are missing weight or volume data.") });
            }
            if (days !== null && days >= 0 && days <= 3) {
                alerts.push({ type: "warn", title: __("Departure Soon"), text: formatDepartureSoon(days) });
            }
            return alerts;
        }

        /* ── Manage Tab ──────────────────────────────────────────────────── */
        _renderManageTab() {
            const area = this.root.querySelector("#clpv2-content-area");
            if (!area) return;
            const plan = (this.cockpitData && this.cockpitData.plan) || {};
            const weightPct = flt(plan.weight_utilization_pct);
            const volumePct = flt(plan.volume_utilization_pct);
            const maxWeight = flt(plan.max_weight_kg);
            const maxVolume = flt(plan.max_volume_m3);
            const usedWeight = flt(plan.total_weight_kg);
            const usedVolume = flt(plan.total_volume_m3);
            const weightState = gaugeColorClass(weightPct);
            const volumeState = gaugeColorClass(volumePct);

            area.innerHTML = `
                <div style="height:100%;display:flex;flex-direction:column;">
                    <div class="clpv2-manage-search">
                        ${SVG.search}
                        <input id="clpv2-manage-search-input" placeholder="${__("Search delivery note or customer...")}" value="${esc(this.manageQuery)}" />
                    </div>
                    <div class="clpv2-manage-grid" id="clpv2-manage-grid">
                        <!-- Queue column -->
                        <div class="clpv2-manage-col">
                            <div class="clpv2-manage-col-head">
                                <span class="clpv2-manage-col-title">${__("Pending Queue")}</span>
                                <span class="clpv2-manage-col-chip" id="clpv2-manage-queue-count">0</span>
                            </div>
                            <div id="clpv2-manage-queue-list" class="clpv2-manage-list clpv2-scroll"></div>
                        </div>
                        <!-- Active column -->
                        <div class="clpv2-manage-col">
                            <div class="clpv2-manage-col-head">
                                <span class="clpv2-manage-col-title">${__("Loaded")}</span>
                                <span class="clpv2-manage-col-chip" id="clpv2-manage-active-count">0</span>
                            </div>
                            <div class="clpv2-cap-strip" id="clpv2-cap-strip">
                                <div class="clpv2-cap-gauge ${weightState}">
                                    <div class="clpv2-cap-gauge-top">
                                        <span class="clpv2-cap-gauge-label">${__("Weight")}</span>
                                        <span class="clpv2-cap-gauge-pct">${weightPct.toFixed(1)}%</span>
                                    </div>
                                    <div class="clpv2-cap-gauge-track">
                                        <div class="clpv2-cap-gauge-fill" style="width:${Math.min(weightPct, 100)}%"></div>
                                    </div>
                                    <div class="clpv2-cap-caption">${usedWeight.toFixed(1)} / ${maxWeight.toFixed(1)} kg</div>
                                </div>
                                <div class="clpv2-cap-gauge ${volumeState}">
                                    <div class="clpv2-cap-gauge-top">
                                        <span class="clpv2-cap-gauge-label">${__("Volume")}</span>
                                        <span class="clpv2-cap-gauge-pct">${volumePct.toFixed(1)}%</span>
                                    </div>
                                    <div class="clpv2-cap-gauge-track">
                                        <div class="clpv2-cap-gauge-fill" style="width:${Math.min(volumePct, 100)}%"></div>
                                    </div>
                                    <div class="clpv2-cap-caption">${usedVolume.toFixed(1)} / ${maxVolume.toFixed(1)} m³</div>
                                </div>
                            </div>
                            <div id="clpv2-manage-active-list" class="clpv2-manage-list clpv2-scroll"></div>
                        </div>
                    </div>
                </div>
            `;

            // Bind manage search
            const manageSearch = area.querySelector("#clpv2-manage-search-input");
            if (manageSearch) {
                manageSearch.addEventListener("input", () => {
                    this.manageQuery = manageSearch.value.trim().toLowerCase();
                    this._renderManageLists();
                });
            }

            this._renderManageLists();
        }

        _renderManageLists() {
            const queue = this._filterRows((this.cockpitData && this.cockpitData.queue) || [], this.manageQuery, ["delivery_note", "customer", "destination_zone"]);
            const shipments = this._filterRows((this.cockpitData && this.cockpitData.shipments) || [], this.manageQuery, ["delivery_note", "customer"]);
            this._renderQueueList(queue);
            this._renderActiveList(shipments);
        }

        _filterRows(rows, query, keys) {
            if (!query) return rows;
            return rows.filter(row => keys.some(k => String(row[k] || "").toLowerCase().includes(query)));
        }

        _renderQueueList(queue) {
            const listEl = this.root.querySelector("#clpv2-manage-queue-list");
            const countEl = this.root.querySelector("#clpv2-manage-queue-count");
            if (!listEl) return;

            if (countEl) countEl.textContent = String(queue.length);

            if (!queue.length) {
                listEl.innerHTML = `
                    <div class="clpv2-manage-empty">
                        <div class="clpv2-manage-empty-icon">📦</div>
                        <div class="clpv2-manage-empty-label">${__("Queue is empty")}</div>
                        <div class="clpv2-manage-empty-hint">${__("No pending shipments for this zone")}</div>
                    </div>`;
                return;
            }

            listEl.innerHTML = queue.map(row => `
                <article class="clpv2-queue-card" draggable="true" data-dn="${esc(row.delivery_note)}">
                    <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:6px;">
                        <div>
                            <div class="clpv2-card-dn">${esc(row.delivery_note)}</div>
                            <div class="clpv2-card-customer">${esc(row.customer || "—")}</div>
                        </div>
                        ${row.destination_zone ? `<span class="clpv2-zone-pill">${esc(row.destination_zone)}</span>` : ""}
                    </div>
                    <div class="clpv2-card-badges">
                        <span class="clpv2-card-badge">${SVG.weight} ${flt(row.total_weight_kg).toFixed(1)} kg</span>
                        <span class="clpv2-card-badge">${SVG.cube} ${flt(row.total_volume_m3).toFixed(2)} m³</span>
                    </div>
                    <div class="clpv2-card-footer">
                        <button class="clpv2-btn-add-card" style="width:100%;" data-action="add" data-dn="${esc(row.delivery_note)}">${SVG.plus} ${__("Add to Container")}</button>
                    </div>
                </article>
            `).join("");

            // Add button clicks
            listEl.querySelectorAll("[data-action='add']").forEach(btn => {
                btn.addEventListener("click", () => this._addShipment(btn.dataset.dn));
            });

            // DnD drag from queue
            listEl.querySelectorAll("article.clpv2-queue-card").forEach(card => {
                card.addEventListener("dragstart", (e) => {
                    e.dataTransfer.setData("text/plain", card.dataset.dn);
                    e.dataTransfer.setData("application/ol-source", "queue");
                    card.classList.add("dragging");
                    const activeList = this.root.querySelector("#clpv2-manage-active-list");
                    if (activeList) activeList.classList.add("dropzone-active");
                });
                card.addEventListener("dragend", () => {
                    card.classList.remove("dragging");
                    const activeList = this.root.querySelector("#clpv2-manage-active-list");
                    if (activeList) activeList.classList.remove("dropzone-active");
                });
            });
        }

        _renderActiveList(shipments) {
            const listEl = this.root.querySelector("#clpv2-manage-active-list");
            const countEl = this.root.querySelector("#clpv2-manage-active-count");
            if (!listEl) return;

            const ordered = [...shipments].sort((a, b) => (a.sequence || 0) - (b.sequence || 0));
            if (countEl) countEl.textContent = String(ordered.length);

            if (!ordered.length) {
                listEl.innerHTML = `
                    <div class="clpv2-manage-empty">
                        <div class="clpv2-manage-empty-icon">📋</div>
                        <div class="clpv2-manage-empty-label">${__("Container is empty")}</div>
                        <div class="clpv2-manage-empty-hint">${__("Drag or add shipments from the queue")}</div>
                    </div>`;
            } else {
                listEl.innerHTML = ordered.map((row, idx) => {
                    const checked = Number(row.selected || 0) ? "checked" : "";
                    return `
                        <article class="clpv2-active-card" draggable="true" data-dn="${esc(row.delivery_note)}" data-sequence="${row.sequence || 0}">
                            <div style="display:flex;align-items:flex-start;gap:8px;">
                                <div class="clpv2-seq-badge">${idx + 1}</div>
                                <div style="flex:1;min-width:0;">
                                    <div class="clpv2-card-dn">${esc(row.delivery_note)}</div>
                                    <div class="clpv2-card-customer">${esc(row.customer || "—")}</div>
                                </div>
                            </div>
                            <div class="clpv2-card-badges">
                                <span class="clpv2-card-badge">${SVG.weight} ${flt(row.shipment_weight_kg).toFixed(1)} kg</span>
                                <span class="clpv2-card-badge">${SVG.cube} ${flt(row.shipment_volume_m3).toFixed(2)} m³</span>
                            </div>
                            <div class="clpv2-card-footer">
                                <label style="display:flex;align-items:center;gap:4px;cursor:pointer;margin:0;flex:1;">
                                    <input type="checkbox" data-action="toggle" data-dn="${esc(row.delivery_note)}" ${checked} style="cursor:pointer;" />
                                    <span style="font-size:11px;color:#94A3B8;">${__("Include")}</span>
                                </label>
                                <button class="clpv2-btn-remove-card" data-action="remove" data-dn="${esc(row.delivery_note)}">${SVG.x} ${__("Remove")}</button>
                            </div>
                        </article>
                    `;
                }).join("");
            }

            // Remove & toggle button bindings
            listEl.querySelectorAll("[data-action='remove']").forEach(btn => {
                btn.addEventListener("click", () => this._removeShipment(btn.dataset.dn));
            });
            listEl.querySelectorAll("[data-action='toggle']").forEach(input => {
                input.addEventListener("change", () => this._toggleShipment(input.dataset.dn, input.checked ? 1 : 0));
            });

            // DnD: drop zone (queue items + reorder)
            listEl.addEventListener("dragover", (e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = "move";
                const target = e.target.closest("article.clpv2-active-card");
                if (target) {
                    listEl.querySelectorAll(".drop-target").forEach(el => el.classList.remove("drop-target"));
                    target.classList.add("drop-target");
                }
            });
            listEl.addEventListener("dragleave", (e) => {
                if (!listEl.contains(e.relatedTarget)) {
                    listEl.querySelectorAll(".drop-target").forEach(el => el.classList.remove("drop-target"));
                }
            });
            listEl.addEventListener("drop", async (e) => {
                e.preventDefault();
                listEl.querySelectorAll(".drop-target").forEach(el => el.classList.remove("drop-target"));
                const dn = e.dataTransfer.getData("text/plain");
                const source = e.dataTransfer.getData("application/ol-source");
                if (!dn) return;
                if (source === "queue") {
                    await this._addShipment(dn);
                } else if (source === "active") {
                    await this._reorderByDrop(dn, e);
                }
            });

            // DnD: drag within active (reorder)
            listEl.querySelectorAll("article.clpv2-active-card").forEach(card => {
                card.addEventListener("dragstart", (e) => {
                    e.dataTransfer.setData("text/plain", card.dataset.dn);
                    e.dataTransfer.setData("application/ol-source", "active");
                    card.classList.add("dragging");
                });
                card.addEventListener("dragend", () => card.classList.remove("dragging"));
            });
        }

        /* ── Shipment actions ────────────────────────────────────────────── */
        async _addShipment(dn) {
            await frappe.call({
                method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.append_shipments",
                args: { load_plan_name: this.selectedPlanId, delivery_notes: [dn] },
                freeze: true,
            });
            await this._refreshData();
        }

        async _removeShipment(dn) {
            await frappe.call({
                method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.remove_shipment",
                args: { load_plan_name: this.selectedPlanId, delivery_note: dn },
                freeze: true,
            });
            await this._refreshData();
        }

        async _toggleShipment(dn, selected) {
            await frappe.call({
                method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.set_shipment_selected",
                args: { load_plan_name: this.selectedPlanId, delivery_note: dn, selected },
                freeze: false,
            });
            await this._refreshData();
        }

        async _reorderByDrop(draggedDn, dropEvent) {
            const listEl = this.root.querySelector("#clpv2-manage-active-list");
            if (!listEl) return;
            const articles = Array.from(listEl.querySelectorAll("article.clpv2-active-card[data-dn]"));
            const dropTarget = dropEvent.target.closest("article.clpv2-active-card");
            if (!dropTarget || dropTarget.dataset.dn === draggedDn) return;

            const dns = articles.map(el => el.dataset.dn).filter(d => d !== draggedDn);
            const insertIdx = dns.indexOf(dropTarget.dataset.dn);
            const rect = dropTarget.getBoundingClientRect();
            const after = dropEvent.clientY > rect.top + rect.height / 2;
            if (insertIdx === -1) {
                dns.push(draggedDn);
            } else {
                dns.splice(after ? insertIdx + 1 : insertIdx, 0, draggedDn);
            }

            await frappe.call({
                method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.reorder_shipments",
                args: { load_plan_name: this.selectedPlanId, delivery_notes_ordered: dns },
            });
            await this._refreshData();
        }

        /* ── Refresh ─────────────────────────────────────────────────────── */
        async _refreshData() {
            if (!this.selectedPlanId) return;
            try {
                const r = await frappe.call({
                    method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.get_cockpit_data",
                    args: { load_plan_name: this.selectedPlanId },
                    freeze: false,
                });
                this.cockpitData = r.message || {};
                this._renderPlanHeader(this.cockpitData.plan || {});
                this._renderCurrentTab();

                // Also refresh sidebar utilization bars
                const planObj = this.cockpitData.plan || {};
                const idx = this.plans.findIndex(p => p.name === this.selectedPlanId);
                if (idx !== -1) {
                    this.plans[idx].weight_utilization_pct = planObj.weight_utilization_pct;
                    this.plans[idx].volume_utilization_pct = planObj.volume_utilization_pct;
                    this.plans[idx].status = planObj.status;
                    this._renderTimeline();
                }
            } catch (err) {
                console.error("CockpitV2: refresh failed", err);
            }
        }

        /* ── Auto-suggest ────────────────────────────────────────────────── */
        async _autoSuggest() {
            if (!this.selectedPlanId) return;
            const r = await frappe.call({
                method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.suggest_shipments",
                args: { load_plan_name: this.selectedPlanId },
                freeze: true,
                freeze_message: __("Building optimal shipment combination..."),
            });
            const selected = (r.message && r.message.selected) || [];
            if (!selected.length) {
                frappe.show_alert({ message: __("No fitting shipments found"), indicator: "orange" });
                return;
            }
            await frappe.call({
                method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.append_shipments",
                args: {
                    load_plan_name: this.selectedPlanId,
                    delivery_notes: selected.map(x => x.delivery_note),
                },
                freeze: true,
            });
            await this._refreshData();
            frappe.show_alert({ message: __("Auto-suggest added {0} shipments", [selected.length]), indicator: "green" });
        }

        /* ── Run analysis ────────────────────────────────────────────────── */
        async _runAnalysis() {
            if (!this.selectedPlanId) return;
            await frappe.call({
                method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.run_load_plan_analysis",
                args: { load_plan_name: this.selectedPlanId },
                freeze: true,
                freeze_message: __("Running analysis..."),
            });
            await this._refreshData();
        }

        /* ── Realtime ────────────────────────────────────────────────────── */
        _subscribeRealtime() {
            if (!this.selectedPlanId || this._subscribedPlan === this.selectedPlanId) return;
            frappe.realtime.doc_subscribe("Container Load Plan", this.selectedPlanId);
            this._subscribedPlan = this.selectedPlanId;
            this._realtimeHandler = (data) => {
                if (!data || data.load_plan !== this.selectedPlanId) return;
                if (data.user === frappe.session.user) return;
                frappe.show_alert({
                    message: __("Load plan updated by {0}", [esc(data.user_fullname || data.user)]),
                    indicator: "blue",
                });
                this._refreshData();
            };
            frappe.realtime.on("load_plan_updated", this._realtimeHandler);
        }

        _unsubscribeRealtime() {
            if (this._subscribedPlan) {
                frappe.realtime.doc_unsubscribe("Container Load Plan", this._subscribedPlan);
                this._subscribedPlan = null;
            }
            if (this._realtimeHandler) {
                frappe.realtime.off("load_plan_updated", this._realtimeHandler);
                this._realtimeHandler = null;
            }
        }

        /* ── Zone overview dialog ────────────────────────────────────────── */
        async _showZoneOverview() {
            const company = this.cockpitData && this.cockpitData.plan && this.cockpitData.plan.company;
            const r = await frappe.call({
                method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.preview_consolidation",
                args: { company: company || null },
                freeze: true,
                freeze_message: __("Calculating zone consolidation..."),
            });
            const zones = r.message || [];
            if (!zones.length) { frappe.msgprint(__("No pending delivery notes found.")); return; }
            const rows = zones.map(z => {
                const planSummary = z.plans.length
                    ? z.plans.map(p => `<div class="ol-zone-plan-row"><span class="ol-zone-container">${esc(p.container_name)}</span><span class="ol-zone-util">${flt(p.weight_utilization_pct).toFixed(1)}%W / ${flt(p.volume_utilization_pct).toFixed(1)}%V</span><span class="ol-zone-count">${p.shipment_count} DNs</span></div>`).join("")
                    : `<div class="ol-zone-empty-plan">${__("No fitting container found")}</div>`;
                const leftoverHtml = z.leftover_count > 0 ? `<div class="ol-zone-leftover">${z.leftover_count} ${__("DN(s) unassigned")}</div>` : "";
                return `<div class="ol-zone-card"><div class="ol-zone-header"><span class="ol-zone-name">${esc(z.zone)}</span><span class="ol-zone-badge">${z.pending_dn_count} ${__("pending")} | ${flt(z.total_weight_kg).toFixed(1)} kg | ${flt(z.total_volume_m3).toFixed(1)} m³</span></div><div class="ol-zone-plans">${planSummary}</div>${leftoverHtml}</div>`;
            }).join("");
            const d = new frappe.ui.Dialog({ title: __("Zone Consolidation Overview"), size: "large" });
            d.body.innerHTML = `<div class="ol-zone-overview">${rows}</div>`;
            d.show();
        }

        /* ── Analytics dialog ────────────────────────────────────────────── */
        async _showAnalytics() {
            const r = await frappe.call({
                method: "orderlift.orderlift_logistics.doctype.container_load_plan.container_load_plan.get_utilization_trends",
                args: { days: 30 },
                freeze: true,
                freeze_message: __("Loading analytics..."),
            });
            const data = r.message || {};
            if (!data.plan_count) { frappe.msgprint(__("No completed load plans found in the last 30 days.")); return; }
            const byZoneRows = (data.by_zone || []).map(z =>
                `<tr><td>${esc(z.zone)}</td><td>${z.count}</td><td>${flt(z.avg_weight_pct).toFixed(1)}%</td><td>${flt(z.avg_volume_pct).toFixed(1)}%</td></tr>`
            ).join("");
            const factorHtml = Object.entries(data.by_limiting_factor || {}).map(([k, v]) =>
                `<span class="ol-factor-pill ${k}">${esc(k)}: ${v}</span>`
            ).join(" ");
            const html = `
                <div class="ol-analytics-wrap">
                    <div class="ol-analytics-kpis">
                        <div class="ol-kpi-card"><div class="ol-kpi-label">${__("Plans (30 days)")}</div><div class="ol-kpi-value">${data.plan_count}</div></div>
                        <div class="ol-kpi-card"><div class="ol-kpi-label">${__("Avg Weight Util")}</div><div class="ol-kpi-value small">${flt(data.avg_weight_pct).toFixed(1)}%</div></div>
                        <div class="ol-kpi-card"><div class="ol-kpi-label">${__("Avg Volume Util")}</div><div class="ol-kpi-value small">${flt(data.avg_volume_pct).toFixed(1)}%</div></div>
                    </div>
                    <div class="ol-analytics-section-title">${__("Limiting Factor Distribution")}</div>
                    <div class="ol-analytics-factors">${factorHtml}</div>
                    <div class="ol-analytics-section-title">${__("By Zone (last 30 days)")}</div>
                    <table class="table table-bordered ol-analytics-table">
                        <thead><tr><th>${__("Zone")}</th><th>${__("Plans")}</th><th>${__("Avg Weight %")}</th><th>${__("Avg Volume %")}</th></tr></thead>
                        <tbody>${byZoneRows}</tbody>
                    </table>
                </div>`;
            const d = new frappe.ui.Dialog({ title: __("Load Plan Analytics — Last 30 Days"), size: "large" });
            d.body.innerHTML = html;
            d.show();
        }

        /* ── Open in form ────────────────────────────────────────────────── */
        openForm() {
            if (!this.selectedPlanId) return;
            frappe.set_route("Form", "Container Load Plan", this.selectedPlanId);
        }

        /* ── Cleanup ─────────────────────────────────────────────────────── */
        destroy() {
            this._unsubscribeRealtime();
        }
    }

    /* ══════════════════════════════════════════════════════════════════════
       Public API
       ══════════════════════════════════════════════════════════════════════ */
    function mount(root, options) {
        return ensureStylesheet(
            "orderlift-cockpit-v2-css",
            "/assets/orderlift/css/logistics_hub_cockpit_v2.css"
        ).then(() => {
            const instance = new CockpitV2(root, options || {});
            root._cockpitV2Instance = instance;
            return instance;
        });
    }

    global.orderliftCockpitV2 = { mount };

})(window);
