/* ============================================================
   SIG Map — /project-map
   Vanilla JS + Leaflet.js  (no extra deps)
   ============================================================ */

(function () {
    "use strict";

    // ── State ────────────────────────────────────────────────
    let _map = null;
    let _markers = [];           // Array of { project, marker }
    let _allProjects = [];

    const QC_COLORS = {
        "Complete":     "green",
        "In Progress":  "orange",
        "Blocked":      "red",
        "Not Started":  "gray",
        "":             "blue",
    };

    // ── Init ─────────────────────────────────────────────────
    document.addEventListener("DOMContentLoaded", () => {
        _initMap();
        _wireToolbar();
        _loadProjects({});

        // Auto-zoom to project if URL param given
        const urlProject = new URLSearchParams(location.search).get("project");
        if (urlProject) {
            _openPanelForProject(urlProject);
        }
    });

    // ── Map init ─────────────────────────────────────────────
    function _initMap() {
        _map = L.map("sig-map", {
            center: [31.7917, -7.0926],   // Default: Morocco centre
            zoom: 6,
            zoomControl: true,
        });

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 19,
        }).addTo(_map);
    }

    // ── Load projects from API ────────────────────────────────
    function _loadProjects(filters) {
        _setLoading(true);
        frappe.call({
            method: "orderlift.orderlift_sig.api.map_api.get_map_projects",
            args: { filters },
            callback(r) {
                _setLoading(false);
                if (r.exc) return;
                _allProjects = r.message || [];
                _renderMarkers(_allProjects);
                _updateCount(_allProjects.length);
            },
        });
    }

    // ── Render markers ────────────────────────────────────────
    function _renderMarkers(projects) {
        // Clear existing
        _markers.forEach(({ marker }) => _map.removeLayer(marker));
        _markers = [];

        const bounds = [];
        projects.forEach(p => {
            if (!p.latitude || !p.longitude) return;

            const color = QC_COLORS[p.qc_status] || "blue";
            const icon = L.divIcon({
                className: "",
                html: `<div class="sig-marker sig-marker-${color}" title="${_esc(p.project_name)}"></div>`,
                iconSize: [28, 28],
                iconAnchor: [14, 28],
                popupAnchor: [0, -30],
            });

            const marker = L.marker([p.latitude, p.longitude], { icon })
                .addTo(_map)
                .bindPopup(_buildPopup(p), { maxWidth: 260 });

            marker.on("click", () => _openPanel(p));

            _markers.push({ project: p, marker });
            bounds.push([p.latitude, p.longitude]);
        });

        if (bounds.length > 0) {
            _map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
        }
    }

    // ── Popup HTML (compact) ──────────────────────────────────
    function _buildPopup(p) {
        const badgeClass = _badgeClass(p.qc_status);
        return `
            <div style="font-family:-apple-system,sans-serif;font-size:13px">
                <div style="font-weight:600;margin-bottom:4px">${_esc(p.project_name)}</div>
                <div style="color:#6c757d;margin-bottom:6px">${_esc(p.customer || "")}</div>
                ${p.city ? `<div>📍 ${_esc(p.city)}</div>` : ""}
                <div style="margin-top:6px">
                    <span class="sig-panel-badge ${badgeClass}">${_esc(p.qc_status || "—")}</span>
                </div>
                <div style="margin-top:8px">
                    <button onclick="window._sigOpenPanel('${_esc(p.name)}')"
                            style="width:100%;padding:6px;background:#1a73e8;color:#fff;border:none;
                                   border-radius:5px;cursor:pointer;font-size:12px">
                        View Details
                    </button>
                </div>
            </div>`;
    }

    // ── Panel ─────────────────────────────────────────────────
    function _openPanel(p) {
        const panel = document.getElementById("sig-map-panel");
        const content = document.getElementById("sig-panel-content");

        const badgeClass = _badgeClass(p.qc_status);
        content.innerHTML = `
            <div class="sig-panel-header">
                <p class="sig-panel-title">${_esc(p.project_name)}</p>
                <p class="sig-panel-subtitle">${_esc(p.customer || "")}${p.city ? " · " + _esc(p.city) : ""}</p>
                <span class="sig-panel-badge ${badgeClass}">${_esc(p.qc_status || "Not Started")}</span>
            </div>
            <div class="sig-panel-section">
                <div class="sig-panel-section-title">Details</div>
                ${_detailRow("Type", p.project_type || "—")}
                ${_detailRow("Status", p.status || "—")}
                ${_detailRow("Address", p.site_address || "—")}
                ${p.expected_start_date ? _detailRow("Start", p.expected_start_date) : ""}
            </div>
            <div class="sig-panel-section" id="sig-qc-section">
                <div class="sig-panel-section-title">QC Checklist</div>
                <div id="sig-qc-detail"><em style="color:#6c757d">Loading…</em></div>
            </div>
            <div class="sig-panel-actions">
                <a href="/app/project/${encodeURIComponent(p.name)}" target="_blank"
                   class="sig-panel-btn sig-panel-btn-primary">Open in ERP →</a>
                <button onclick="window._sigFlyTo('${_esc(p.name)}')"
                        class="sig-panel-btn">Fly to on Map</button>
            </div>`;

        panel.classList.remove("sig-map-panel-hidden");

        // Load QC summary async
        frappe.call({
            method: "orderlift.orderlift_sig.api.map_api.get_project_qc_summary",
            args: { project_name: p.name },
            callback(r) {
                if (r.exc || !r.message) return;
                const el = document.getElementById("sig-qc-detail");
                if (!el) return;
                el.innerHTML = _renderQCSummary(r.message);
            },
        });

        // Store for fly-to
        panel._currentProject = p;
    }

    function _openPanelForProject(projectName) {
        const found = _allProjects.find(p => p.name === projectName);
        if (found) {
            _openPanel(found);
            const m = _markers.find(m => m.project.name === projectName);
            if (m) {
                _map.setView([found.latitude, found.longitude], 14);
                m.marker.openPopup();
            }
        } else {
            // Not yet loaded — wait
            setTimeout(() => _openPanelForProject(projectName), 500);
        }
    }

    function _renderQCSummary(s) {
        if (!s.total) return `<em style="color:#6c757d">No QC checklist.</em>`;

        const barColor = s.qc_status === "Complete"    ? "#28a745"
                       : s.qc_status === "Blocked"     ? "#dc3545"
                       : s.qc_status === "In Progress" ? "#fd7e14"
                       : "#adb5bd";

        let cats = Object.entries(s.by_category).map(([cat, v]) => `
            <div class="sig-qc-cat">
                <span class="sig-qc-cat-name">${_esc(cat)}</span>
                <span class="sig-qc-cat-count">${v.verified}/${v.total}</span>
            </div>`).join("");

        return `
            <div style="font-size:13px;margin-bottom:4px">
                <b>${s.verified}/${s.total}</b> verified (${s.pct}%)
                ${s.mandatory_unverified ? `<span style="color:#dc3545;margin-left:6px">⚠ ${s.mandatory_unverified} mandatory pending</span>` : ""}
            </div>
            <div class="sig-qc-bar-wrap">
                <div class="sig-qc-bar" style="width:${s.pct}%;background:${barColor}"></div>
            </div>
            <div class="sig-qc-cats">${cats}</div>`;
    }

    function _detailRow(label, value) {
        return `<div style="display:flex;gap:8px;margin-bottom:4px;font-size:13px">
                    <span style="color:#6c757d;min-width:70px">${_esc(label)}</span>
                    <span>${_esc(String(value))}</span>
                </div>`;
    }

    // ── Toolbar wiring ────────────────────────────────────────
    function _wireToolbar() {
        document.getElementById("sig-filter-apply").addEventListener("click", () => {
            _loadProjects({
                project_type: document.getElementById("sig-filter-type").value,
                qc_status:    document.getElementById("sig-filter-qc").value,
                status:       document.getElementById("sig-filter-status").value,
            });
        });

        document.getElementById("sig-filter-reset").addEventListener("click", () => {
            document.getElementById("sig-filter-type").value = "";
            document.getElementById("sig-filter-qc").value = "";
            document.getElementById("sig-filter-status").value = "";
            _loadProjects({});
        });

        document.getElementById("sig-panel-close").addEventListener("click", () => {
            document.getElementById("sig-map-panel").classList.add("sig-map-panel-hidden");
        });
    }

    // ── Global helpers (called from popup HTML) ───────────────
    window._sigOpenPanel = function (projectName) {
        const p = _allProjects.find(x => x.name === projectName);
        if (p) _openPanel(p);
    };

    window._sigFlyTo = function (projectName) {
        const p = _allProjects.find(x => x.name === projectName);
        if (p && p.latitude && p.longitude) {
            _map.flyTo([p.latitude, p.longitude], 15, { duration: 1.2 });
        }
    };

    // ── Helpers ───────────────────────────────────────────────
    function _badgeClass(status) {
        return status === "Complete"   ? "sig-badge-green"
             : status === "Blocked"    ? "sig-badge-red"
             : status === "In Progress"? "sig-badge-orange"
             : "sig-badge-gray";
    }

    function _esc(s) {
        return String(s == null ? "" : s)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function _setLoading(on) {
        const el = document.getElementById("sig-map-loading");
        if (el) el.classList.toggle("hidden", !on);
    }

    function _updateCount(n) {
        const el = document.getElementById("sig-project-count");
        if (el) el.textContent = n + " project" + (n !== 1 ? "s" : "");
    }

})();
