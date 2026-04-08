(function (global) {
    "use strict";

    const LOCAL_CSS = "/assets/orderlift/css/sig_dashboard.css?v=20260408b";

    function ensureStylesheet(id, href) {
        if (document.getElementById(id)) return Promise.resolve();
        return new Promise((resolve, reject) => {
            const link = document.createElement("link");
            link.id = id;
            link.rel = "stylesheet";
            link.href = href;
            link.onload = resolve;
            link.onerror = () => reject(new Error(`Failed to load stylesheet: ${href}`));
            document.head.appendChild(link);
        });
    }

    function renderShell(root) {
        root.innerHTML = `
            <div id="sig-dash-root">
                <div class="sig-dash-header">
                    <div class="sig-dash-logo">
                        <span>SIG Dashboard</span>
                    </div>
                    <nav class="sig-dash-nav">
                        <a href="/app/sig-dashboard" class="sig-dash-nav-link is-active">Dashboard</a>
                        <a href="/app/project-map" class="sig-dash-nav-link">Map</a>
                        <a href="/app/project" class="sig-dash-nav-link">Projects</a>
                        <a href="/app/sig-qc" class="sig-dash-nav-link">Mobile QC</a>
                    </nav>
                    <div class="sig-dash-header-right">
                        <span id="sig-dash-last-updated" class="sig-dash-meta"></span>
                        <button id="sig-dash-refresh" class="sig-btn sig-btn-sm">↻ Refresh</button>
                    </div>
                </div>
                <div class="sig-dash-content">
                    <div class="sig-kpi-row" id="sig-kpi-row"></div>
                    <div class="sig-dash-grid">
                        <div class="sig-dash-card">
                            <div class="sig-dash-card-title">Projects by QC Status</div>
                            <div id="sig-chart-qc" class="sig-bar-chart"></div>
                        </div>
                        <div class="sig-dash-card">
                            <div class="sig-dash-card-title">Projects by Type</div>
                            <div id="sig-chart-type" class="sig-bar-chart"></div>
                        </div>
                    </div>
                    <div class="sig-dash-card sig-dash-card-full" id="sig-blocked-card">
                        <div class="sig-dash-card-title">
                            <span class="sig-badge-red sig-badge-sm">⚠</span>
                            Blocked QC - Needs Attention
                        </div>
                        <div id="sig-blocked-list"><em class="sig-meta">Loading...</em></div>
                    </div>
                    <div class="sig-dash-card sig-dash-card-full">
                        <div class="sig-dash-card-title">Active Projects</div>
                        <div id="sig-recent-list"></div>
                    </div>
                </div>
            </div>
        `;
    }

    function mount(root) {
        if (!root) return Promise.resolve();
        return ensureStylesheet("orderlift-sig-dashboard-css", LOCAL_CSS).then(() => {
            renderShell(root);
            init(root);
        });
    }

    function init(root) {
        const QC_COLORS = {
            "Complete": "#28a745",
            "In Progress": "#fd7e14",
            "Blocked": "#dc3545",
            "Not Started": "#adb5bd",
        };

        const $ = (selector) => root.querySelector(selector);

        $("#sig-dash-refresh").addEventListener("click", load);
        load();

        function load() {
            frappe.call({
                method: "orderlift.orderlift_sig.api.dashboard_api.get_dashboard_data",
                callback(r) {
                    if (r.exc || !r.message) return;
                    const data = r.message;
                    renderKpis(data.kpis);
                    renderBarChart("#sig-chart-qc", data.by_qc, "qc_status", QC_COLORS, "#adb5bd");
                    renderBarChart("#sig-chart-type", data.by_type, "project_type", {}, "#1a73e8");
                    renderBlocked(data.blocked_projects);
                    renderRecent(data.recent_projects);
                    const label = $("#sig-dash-last-updated");
                    if (label) label.textContent = `Updated ${new Date().toLocaleTimeString()}`;
                },
            });
        }

        function renderKpis(kpis) {
            const row = $("#sig-kpi-row");
            if (!row) return;

            const cards = [
                { label: "Total Projects", value: kpis.total_projects, cls: "" },
                { label: "Open", value: kpis.open_projects, cls: "kpi-blue" },
                { label: "QC Complete", value: kpis.complete_projects, cls: "kpi-green" },
                { label: "QC Blocked", value: kpis.blocked_qc, cls: "kpi-red" },
                { label: "Geocoded", value: kpis.geocoded, cls: "kpi-orange" },
            ];

            row.innerHTML = cards.map((card) => `
                <div class="sig-kpi-card ${card.cls}">
                    <div class="sig-kpi-label">${esc(card.label)}</div>
                    <div class="sig-kpi-value">${card.value}</div>
                </div>`).join("");
        }

        function renderBarChart(selector, rows, labelKey, colorMap, defaultColor) {
            const el = $(selector);
            if (!el) return;
            if (!rows || !rows.length) {
                el.innerHTML = '<em class="sig-meta">No data.</em>';
                return;
            }
            const max = Math.max(...rows.map((row) => row.cnt));
            el.innerHTML = rows.map((row) => {
                const label = row[labelKey] || "Unspecified";
                const pct = max ? Math.round((row.cnt / max) * 100) : 0;
                const color = colorMap[label] || defaultColor;
                return `
                    <div class="sig-bar-row">
                        <div class="sig-bar-label">${esc(label)}</div>
                        <div class="sig-bar-track">
                            <div class="sig-bar-fill" style="width:${pct}%;background:${color}"></div>
                        </div>
                        <div class="sig-bar-count">${row.cnt}</div>
                    </div>`;
            }).join("");
        }

        function renderBlocked(projects) {
            const el = $("#sig-blocked-list");
            const card = $("#sig-blocked-card");
            if (!el || !card) return;
            if (!projects || !projects.length) {
                card.style.display = "none";
                return;
            }
            card.style.display = "block";
            el.innerHTML = `
                <table class="sig-proj-table">
                    <thead>
                        <tr>
                            <th>Project</th>
                            <th>Customer</th>
                            <th>Type</th>
                            <th>City</th>
                            <th>Modified</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${projects.map((project) => `
                            <tr>
                                <td><a href="/app/project/${encodeURIComponent(project.name)}" target="_blank">${esc(project.project_name)}</a></td>
                                <td>${esc(project.customer || "-")}</td>
                                <td>${project.project_type ? `<span class="sig-badge sig-badge-blue">${esc(project.project_type)}</span>` : "-"}</td>
                                <td>${esc(project.city || "-")}</td>
                                <td>${esc(formatDate(project.modified))}</td>
                            </tr>`).join("")}
                    </tbody>
                </table>`;
        }

        function renderRecent(projects) {
            const el = $("#sig-recent-list");
            if (!el) return;
            if (!projects || !projects.length) {
                el.innerHTML = '<em class="sig-meta">No active projects.</em>';
                return;
            }
            el.innerHTML = `
                <table class="sig-proj-table">
                    <thead>
                        <tr>
                            <th>Project</th>
                            <th>Customer</th>
                            <th>Type</th>
                            <th>QC Status</th>
                            <th>City</th>
                            <th>Map</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${projects.map((project) => {
                            const hasMap = project.latitude && project.longitude;
                            return `
                                <tr>
                                    <td><a href="/app/project/${encodeURIComponent(project.name)}" target="_blank">${esc(project.project_name)}</a></td>
                                    <td>${esc(project.customer || "-")}</td>
                                    <td>${project.project_type ? `<span class="sig-badge sig-badge-blue">${esc(project.project_type)}</span>` : "-"}</td>
                                    <td>${qcBadge(project.qc_status)}</td>
                                    <td>${esc(project.city || "-")}</td>
                                    <td>${hasMap ? `<a href="/app/project-map?project=${encodeURIComponent(project.name)}" target="_blank" title="View on map">📍</a>` : '<span title="Not geocoded" style="color:#adb5bd">-</span>'}</td>
                                </tr>`;
                        }).join("")}
                    </tbody>
                </table>`;
        }

        function qcBadge(status) {
            const cls = status === "Complete" ? "sig-badge-green"
                : status === "Blocked" ? "sig-badge-red"
                    : status === "In Progress" ? "sig-badge-orange"
                        : "sig-badge-gray";
            return `<span class="sig-badge ${cls}">${esc(status || "Not Started")}</span>`;
        }
    }

    function formatDate(value) {
        return value ? value.split(" ")[0] : "-";
    }

    function esc(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;");
    }

    global.orderliftSigDashboard = {
        mount,
    };

    function autoMount() {
        const root = document.getElementById("sig-dashboard-root");
        if (!root || root.dataset.autoloadMounted) return;
        root.dataset.autoloadMounted = "1";
        mount(root);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", autoMount);
    } else {
        autoMount();
    }
})(window);
