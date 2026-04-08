(function (global) {
    "use strict";

    const LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
    const LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
    const LOCAL_CSS = "/assets/orderlift/css/sig_map.css?v=20260408e";

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

    function ensureScript(id, src, test) {
        if (test()) return Promise.resolve();
        const existing = document.getElementById(id);
        if (existing) {
            return new Promise((resolve, reject) => {
                existing.addEventListener("load", () => resolve(), { once: true });
                existing.addEventListener("error", () => reject(new Error(`Failed to load script: ${src}`)), { once: true });
            });
        }
        return new Promise((resolve, reject) => {
            const script = document.createElement("script");
            script.id = id;
            script.src = src;
            script.async = true;
            script.onload = resolve;
            script.onerror = () => reject(new Error(`Failed to load script: ${src}`));
            document.head.appendChild(script);
        });
    }

    function ensureLeaflet() {
        return ensureStylesheet("orderlift-sig-map-leaflet-css", LEAFLET_CSS)
            .then(() => ensureScript("orderlift-sig-map-leaflet-js", LEAFLET_JS, () => Boolean(global.L)));
    }

    function renderShell(root) {
        root.innerHTML = `
            <div id="sig-map-root">
                <div class="sig-map-toolbar">
                <div class="sig-map-logo">
                    <span>Project Map</span>
                </div>
                <div class="sig-map-filters">
                    <select id="sig-filter-type" class="sig-filter-select">
                        <option value="">All Types</option>
                        <option value="New Installation">New Installation</option>
                        <option value="Maintenance">Maintenance</option>
                        <option value="Upgrade">Upgrade</option>
                        <option value="Inspection">Inspection</option>
                    </select>
                    <select id="sig-filter-qc" class="sig-filter-select">
                        <option value="">All QC Status</option>
                        <option value="Not Started">Not Started</option>
                        <option value="In Progress">In Progress</option>
                        <option value="Complete">Complete</option>
                        <option value="Blocked">Blocked</option>
                    </select>
                    <select id="sig-filter-status" class="sig-filter-select">
                        <option value="">All Status</option>
                        <option value="Open">Open</option>
                        <option value="Completed">Completed</option>
                        <option value="Cancelled">Cancelled</option>
                    </select>
                    <button id="sig-filter-apply" class="sig-btn sig-btn-primary">Apply</button>
                    <button id="sig-filter-reset" class="sig-btn">Reset</button>
                </div>
                <div class="sig-map-toolbar-right">
                    <span id="sig-project-count" class="sig-map-count">-</span>
                    <a href="/app/project" data-route="List/Project" class="sig-btn">Projects</a>
                    <a href="/app/sig-dashboard" data-route="sig-dashboard" class="sig-btn">Dashboard</a>
                    <a href="/app/sig-qc" data-route="sig-qc" class="sig-btn">Mobile QC</a>
                </div>
            </div>
            <div class="sig-map-body">
                <div id="sig-map" class="sig-map-canvas"></div>
                <div id="sig-map-panel" class="sig-map-panel sig-map-panel-hidden">
                    <button id="sig-panel-close" class="sig-panel-close">✕</button>
                    <div id="sig-panel-content" class="sig-panel-content"></div>
                </div>
            </div>
            <div id="sig-map-loading" class="sig-map-loading">
                <div class="sig-spinner"></div>
                <p>Loading projects...</p>
            </div>
            </div>
        `;
    }

    function mount(root, options) {
        if (!root) return Promise.resolve();

        options = options || {};

        return ensureStylesheet("orderlift-sig-map-css", LOCAL_CSS)
            .then(() => ensureLeaflet())
            .then(() => {
                renderShell(root);
                init(root, options);
            });
    }

    function init(root, options) {
        let map = null;
        let markers = [];
        let allProjects = [];
        let lastBounds = [];

        const preloadProject = options.preloadProject
            || root.dataset.preloadProject
            || new URL(global.location.href).searchParams.get("project")
            || "";

        const QC_COLORS = {
            "Complete": "green",
            "In Progress": "orange",
            "Blocked": "red",
            "Not Started": "gray",
            "": "blue",
        };

        const $ = (selector) => root.querySelector(selector);

        global._sigOpenPanel = function (projectName) {
            const project = allProjects.find((item) => item.name === projectName);
            if (project) openPanel(project);
        };

        global._sigFlyTo = function (projectName) {
            const project = allProjects.find((item) => item.name === projectName);
            if (project && project.latitude && project.longitude && map) {
                map.flyTo([project.latitude, project.longitude], 15, { duration: 1.2 });
            }
        };

        map = L.map($("#sig-map"), {
            center: [31.7917, -7.0926],
            zoom: 6,
            zoomControl: true,
        });

        L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            maxZoom: 19,
        }).addTo(map);

        map.whenReady(() => refreshMapLayout());
        global.addEventListener("resize", () => refreshMapLayout());
        root.addEventListener("click", (event) => {
            const target = event.target.closest("[data-route], [data-page-route], [data-form-doctype]");
            if (!target || !global.frappe) return;

            event.preventDefault();
            if (target.dataset.formDoctype && target.dataset.docname) {
                frappe.set_route("Form", target.dataset.formDoctype, target.dataset.docname);
                return;
            }

            if (target.dataset.pageRoute) {
                frappe.route_options = target.dataset.project ? { project: target.dataset.project } : null;
                frappe.set_route(target.dataset.pageRoute);
                return;
            }

            const route = target.dataset.route;
            if (!route) return;
            if (route.includes("/")) {
                frappe.set_route(...route.split("/"));
            } else {
                frappe.set_route(route);
            }
        });

        $("#sig-filter-apply").addEventListener("click", () => {
            loadProjects({
                project_type: $("#sig-filter-type").value,
                qc_status: $("#sig-filter-qc").value,
                status: $("#sig-filter-status").value,
            });
        });

        $("#sig-filter-reset").addEventListener("click", () => {
            $("#sig-filter-type").value = "";
            $("#sig-filter-qc").value = "";
            $("#sig-filter-status").value = "";
            loadProjects({});
        });

        $("#sig-panel-close").addEventListener("click", () => {
            $("#sig-map-panel").classList.add("sig-map-panel-hidden");
            refreshMapLayout(lastBounds);
        });

        loadProjects({});

        function loadProjects(filters) {
            setLoading(true);
            frappe.call({
                method: "orderlift.orderlift_sig.api.map_api.get_map_projects",
                args: { filters },
                callback(r) {
                    setLoading(false);
                    if (r.exc) return;
                    allProjects = r.message || [];
                    renderMarkers(allProjects);
                    updateCount(allProjects.length);
                    if (preloadProject) {
                        openPanelForProject(preloadProject);
                    }
                },
            });
        }

        function renderMarkers(projects) {
            markers.forEach(({ marker }) => map.removeLayer(marker));
            markers = [];

            const bounds = [];
            projects.forEach((project) => {
                if (!project.latitude || !project.longitude) return;

                const color = QC_COLORS[project.qc_status] || "blue";
                const icon = L.divIcon({
                    className: "",
                    html: `<div class="sig-marker sig-marker-${color}" title="${esc(project.project_name)}"></div>`,
                    iconSize: [28, 28],
                    iconAnchor: [14, 28],
                    popupAnchor: [0, -30],
                });

                const marker = L.marker([project.latitude, project.longitude], { icon })
                    .addTo(map)
                    .bindPopup(buildPopup(project), { maxWidth: 260 });

                marker.on("click", () => openPanel(project));
                markers.push({ project, marker });
                bounds.push([project.latitude, project.longitude]);
            });

            lastBounds = bounds;
            if (bounds.length) {
                refreshMapLayout(bounds);
            } else {
                refreshMapLayout();
            }
        }

        function buildPopup(project) {
            const badgeClass = badgeClassFor(project.qc_status);
            return `
                <div style="font-family:-apple-system,sans-serif;font-size:13px">
                    <div style="font-weight:600;margin-bottom:4px">${esc(project.project_name)}</div>
                    <div style="color:#6c757d;margin-bottom:6px">${esc(project.customer || "")}</div>
                    ${project.city ? `<div>📍 ${esc(project.city)}</div>` : ""}
                    <div style="margin-top:6px">
                        <span class="sig-panel-badge ${badgeClass}">${esc(project.qc_status || "-")}</span>
                    </div>
                    <div style="margin-top:8px">
                        <button onclick='window._sigOpenPanel(${JSON.stringify(project.name)})'
                                style="width:100%;padding:6px;background:#1a73e8;color:#fff;border:none;border-radius:5px;cursor:pointer;font-size:12px">
                            View Details
                        </button>
                    </div>
                </div>`;
        }

        function openPanel(project) {
            const content = $("#sig-panel-content");
            content.innerHTML = `
                <div class="sig-panel-header">
                    <p class="sig-panel-title">${esc(project.project_name)}</p>
                    <p class="sig-panel-subtitle">${esc(project.customer || "")}${project.city ? " · " + esc(project.city) : ""}</p>
                    <span class="sig-panel-badge ${badgeClassFor(project.qc_status)}">${esc(project.qc_status || "Not Started")}</span>
                </div>
                <div class="sig-panel-section">
                    <div class="sig-panel-section-title">Details</div>
                    ${detailRow("Type", project.project_type || "-")}
                    ${detailRow("Status", project.status || "-")}
                    ${detailRow("Address", project.site_address || "-")}
                    ${project.expected_start_date ? detailRow("Start", project.expected_start_date) : ""}
                </div>
                <div class="sig-panel-section">
                    <div class="sig-panel-section-title">QC Checklist</div>
                    <div id="sig-qc-detail"><em style="color:#6c757d">Loading...</em></div>
                </div>
                <div class="sig-panel-actions">
                    <a href="#" data-form-doctype="Project" data-docname="${esc(project.name)}" class="sig-panel-btn sig-panel-btn-primary">Open in ERP</a>
                    <a href="#" data-page-route="sig-qc" data-project="${esc(project.name)}" class="sig-panel-btn">Open Mobile QC</a>
                    ${project.latitude && project.longitude ? `<a href="https://www.google.com/maps?q=${encodeURIComponent(project.latitude + ',' + project.longitude)}" target="_blank" rel="noopener noreferrer" class="sig-panel-btn">Open in Google Maps</a>` : ""}
                    <button onclick='window._sigFlyTo(${JSON.stringify(project.name)})' class="sig-panel-btn">Fly to on Map</button>
                </div>`;

            $("#sig-map-panel").classList.remove("sig-map-panel-hidden");
            refreshMapLayout(lastBounds);

            frappe.call({
                method: "orderlift.orderlift_sig.api.map_api.get_project_qc_summary",
                args: { project_name: project.name },
                callback(r) {
                    if (r.exc || !r.message) return;
                    const detail = $("#sig-qc-detail");
                    if (detail) detail.innerHTML = renderQcSummary(r.message);
                },
            });
        }

        function openPanelForProject(projectName) {
            const found = allProjects.find((project) => project.name === projectName);
            if (!found) return;
            openPanel(found);
            const markerEntry = markers.find((entry) => entry.project.name === projectName);
            if (markerEntry) {
                map.setView([found.latitude, found.longitude], 14);
                markerEntry.marker.openPopup();
            }
        }

        function renderQcSummary(summary) {
            if (!summary.total) return '<em style="color:#6c757d">No QC checklist.</em>';

            const barColor = summary.qc_status === "Complete" ? "#28a745"
                : summary.qc_status === "Blocked" ? "#dc3545"
                    : summary.qc_status === "In Progress" ? "#fd7e14"
                        : "#adb5bd";

            const categories = Object.entries(summary.by_category).map(([category, values]) => `
                <div class="sig-qc-cat">
                    <span class="sig-qc-cat-name">${esc(category)}</span>
                    <span class="sig-qc-cat-count">${values.verified}/${values.total}</span>
                </div>`).join("");

            return `
                <div style="font-size:13px;margin-bottom:4px">
                    <b>${summary.verified}/${summary.total}</b> verified (${summary.pct}%)
                    ${summary.mandatory_unverified ? `<span style="color:#dc3545;margin-left:6px">${summary.mandatory_unverified} mandatory pending</span>` : ""}
                </div>
                <div class="sig-qc-bar-wrap">
                    <div class="sig-qc-bar" style="width:${summary.pct}%;background:${barColor}"></div>
                </div>
                <div class="sig-qc-cats">${categories}</div>`;
        }

        function detailRow(label, value) {
            return `<div style="display:flex;gap:8px;margin-bottom:4px;font-size:13px"><span style="color:#6c757d;min-width:70px">${esc(label)}</span><span>${esc(String(value))}</span></div>`;
        }

        function badgeClassFor(status) {
            return status === "Complete" ? "sig-badge-green"
                : status === "Blocked" ? "sig-badge-red"
                    : status === "In Progress" ? "sig-badge-orange"
                        : "sig-badge-gray";
        }

        function setLoading(on) {
            const loading = $("#sig-map-loading");
            if (loading) loading.classList.toggle("hidden", !on);
        }

        function updateCount(count) {
            const label = $("#sig-project-count");
            if (label) label.textContent = `${count} project${count === 1 ? "" : "s"}`;
        }

        function refreshMapLayout(bounds) {
            if (!map) return;

            const apply = () => {
                map.invalidateSize(false);
                if (bounds && bounds.length) {
                    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
                }
            };

            global.requestAnimationFrame(() => {
                apply();
                global.setTimeout(apply, 120);
                global.setTimeout(apply, 360);
            });
        }
    }

    function esc(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;");
    }

    global.orderliftSigMap = {
        mount,
    };

    function autoMount() {
        const root = document.getElementById("sig-map-root");
        if (!root || root.dataset.autoloadMounted) return;
        root.dataset.autoloadMounted = "1";
        mount(root, {});
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", autoMount);
    } else {
        autoMount();
    }
})(window);
