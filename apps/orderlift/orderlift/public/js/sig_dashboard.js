/* ============================================================
   SIG Dashboard — /sig-dashboard
   ============================================================ */

(function () {
    "use strict";

    const QC_COLORS = {
        "Complete":    "#28a745",
        "In Progress": "#fd7e14",
        "Blocked":     "#dc3545",
        "Not Started": "#adb5bd",
    };
    const TYPE_COLOR = "#1a73e8";

    document.addEventListener("DOMContentLoaded", () => {
        _load();
        document.getElementById("sig-dash-refresh").addEventListener("click", _load);
    });

    function _load() {
        frappe.call({
            method: "orderlift.orderlift_sig.api.dashboard_api.get_dashboard_data",
            callback(r) {
                if (r.exc || !r.message) return;
                const d = r.message;
                _renderKpis(d.kpis);
                _renderBarChart("sig-chart-qc", d.by_qc, "qc_status", QC_COLORS, "#adb5bd");
                _renderBarChart("sig-chart-type", d.by_type, "project_type", {}, TYPE_COLOR);
                _renderBlocked(d.blocked_projects);
                _renderRecent(d.recent_projects);
                const el = document.getElementById("sig-dash-last-updated");
                if (el) el.textContent = "Updated " + new Date().toLocaleTimeString();
            },
        });
    }

    // ── KPIs ──────────────────────────────────────────────────

    function _renderKpis(k) {
        const row = document.getElementById("sig-kpi-row");
        if (!row) return;

        const cards = [
            { label: "Total Projects",  value: k.total_projects,   cls: "" },
            { label: "Open",            value: k.open_projects,    cls: "kpi-blue" },
            { label: "QC Complete",     value: k.complete_projects, cls: "kpi-green" },
            { label: "QC Blocked",      value: k.blocked_qc,       cls: "kpi-red" },
            { label: "Geocoded",        value: k.geocoded,         cls: "kpi-orange" },
        ];

        row.innerHTML = cards.map(c => `
            <div class="sig-kpi-card ${c.cls}">
                <div class="sig-kpi-label">${_esc(c.label)}</div>
                <div class="sig-kpi-value">${c.value}</div>
            </div>`).join("");
    }

    // ── Bar charts ─────────────────────────────────────────────

    function _renderBarChart(containerId, rows, labelKey, colorMap, defaultColor) {
        const el = document.getElementById(containerId);
        if (!el) return;
        if (!rows || !rows.length) {
            el.innerHTML = `<em class="sig-meta">No data.</em>`;
            return;
        }
        const max = Math.max(...rows.map(r => r.cnt));
        el.innerHTML = rows.map(r => {
            const label = r[labelKey] || "Unspecified";
            const pct = max ? Math.round((r.cnt / max) * 100) : 0;
            const color = colorMap[label] || defaultColor;
            return `
                <div class="sig-bar-row">
                    <div class="sig-bar-label">${_esc(label)}</div>
                    <div class="sig-bar-track">
                        <div class="sig-bar-fill" style="width:${pct}%;background:${color}"></div>
                    </div>
                    <div class="sig-bar-count">${r.cnt}</div>
                </div>`;
        }).join("");
    }

    // ── Blocked projects ───────────────────────────────────────

    function _renderBlocked(projects) {
        const el = document.getElementById("sig-blocked-list");
        if (!el) return;
        const card = document.getElementById("sig-blocked-card");

        if (!projects || !projects.length) {
            if (card) card.style.display = "none";
            return;
        }
        if (card) card.style.display = "";
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
                    ${projects.map(p => `
                        <tr>
                            <td><a href="/app/project/${encodeURIComponent(p.name)}" target="_blank">
                                ${_esc(p.project_name)}
                            </a></td>
                            <td>${_esc(p.customer || "—")}</td>
                            <td>${p.project_type ? `<span class="sig-badge sig-badge-blue">${_esc(p.project_type)}</span>` : "—"}</td>
                            <td>${_esc(p.city || "—")}</td>
                            <td>${_esc(_fmtDate(p.modified))}</td>
                        </tr>`).join("")}
                </tbody>
            </table>`;
    }

    // ── Recent active projects ─────────────────────────────────

    function _renderRecent(projects) {
        const el = document.getElementById("sig-recent-list");
        if (!el) return;
        if (!projects || !projects.length) {
            el.innerHTML = `<em class="sig-meta">No active projects.</em>`;
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
                    ${projects.map(p => {
                        const badge = _qcBadge(p.qc_status);
                        const hasMap = p.latitude && p.longitude;
                        return `
                            <tr>
                                <td><a href="/app/project/${encodeURIComponent(p.name)}" target="_blank">
                                    ${_esc(p.project_name)}
                                </a></td>
                                <td>${_esc(p.customer || "—")}</td>
                                <td>${p.project_type ? `<span class="sig-badge sig-badge-blue">${_esc(p.project_type)}</span>` : "—"}</td>
                                <td>${badge}</td>
                                <td>${_esc(p.city || "—")}</td>
                                <td>${hasMap
                                    ? `<a href="/project-map?project=${encodeURIComponent(p.name)}" target="_blank" title="View on map">📍</a>`
                                    : `<span title="Not geocoded" style="color:#adb5bd">—</span>`}
                                </td>
                            </tr>`;
                    }).join("")}
                </tbody>
            </table>`;
    }

    // ── Helpers ───────────────────────────────────────────────

    function _qcBadge(status) {
        const cls = status === "Complete"    ? "sig-badge-green"
                  : status === "Blocked"     ? "sig-badge-red"
                  : status === "In Progress" ? "sig-badge-orange"
                  : "sig-badge-gray";
        return `<span class="sig-badge ${cls}">${_esc(status || "Not Started")}</span>`;
    }

    function _fmtDate(dt) {
        if (!dt) return "—";
        return dt.split(" ")[0];
    }

    function _esc(s) {
        return String(s == null ? "" : s)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

})();
