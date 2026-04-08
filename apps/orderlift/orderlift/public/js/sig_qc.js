(function (global) {
    "use strict";

    const LOCAL_CSS = "/assets/orderlift/css/sig_qc.css?v=20260408c";

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

    function renderShell(root, preloadProject) {
        root.innerHTML = `
            <div id="sig-qc-root" data-preload-project="${esc(preloadProject || "")}">
                <div class="sig-qc-topbar">
                    <button id="sig-qc-back" class="sig-qc-icon-btn" title="Back">←</button>
                    <span class="sig-qc-topbar-title" id="sig-qc-topbar-title">QC Checklist</span>
                    <div class="sig-qc-topbar-right">
                        <span id="sig-qc-status-badge" class="sig-qc-badge"></span>
                    </div>
                </div>
                <div id="sig-qc-picker" class="sig-qc-screen">
                    <div class="sig-qc-picker-body">
                        <h2 class="sig-qc-picker-title">Select Project</h2>
                        <div class="sig-qc-search-wrap">
                            <input id="sig-qc-search" type="text" class="sig-qc-search" placeholder="Search project name or customer..." autocomplete="off">
                        </div>
                        <div id="sig-qc-picker-list" class="sig-qc-picker-list">
                            <p class="sig-qc-meta">Loading projects...</p>
                        </div>
                    </div>
                </div>
                <div id="sig-qc-checklist" class="sig-qc-screen sig-qc-screen-hidden">
                    <div class="sig-qc-progress-wrap">
                        <div id="sig-qc-progress-bar" class="sig-qc-progress-bar"></div>
                    </div>
                    <div class="sig-qc-progress-label" id="sig-qc-progress-label"></div>
                    <div class="sig-qc-tabs" id="sig-qc-tabs"></div>
                    <div id="sig-qc-items" class="sig-qc-items"></div>
                    <div class="sig-qc-fab-wrap">
                        <button id="sig-qc-save-btn" class="sig-qc-fab">✓ Save Progress</button>
                    </div>
                </div>
                <div id="sig-qc-toast-root"></div>
            </div>
        `;
    }

    function mount(root, options) {
        if (!root) return Promise.resolve();
        options = options || {};
        const preloadProject = options.preloadProject
            || (global.frappe && frappe.route_options && frappe.route_options.project)
            || new URL(global.location.href).searchParams.get("project")
            || "";
        return ensureStylesheet("orderlift-sig-qc-css", LOCAL_CSS).then(() => {
            renderShell(root, preloadProject);
            init(root, preloadProject);
        });
    }

    function init(root, preloadProject) {
        let project = null;
        let activeCategory = "All";
        let pendingSave = false;
        let saving = false;
        let allPickerProjects = [];

        const QC_STATUS_BADGE = {
            "Complete": "sig-qc-badge-green",
            "In Progress": "sig-qc-badge-orange",
            "Blocked": "sig-qc-badge-red",
            "Not Started": "sig-qc-badge-gray",
            "": "sig-qc-badge-gray",
        };

        const $ = (selector) => root.querySelector(selector);

        $("#sig-qc-back").addEventListener("click", goBack);
        $("#sig-qc-save-btn").addEventListener("click", saveAll);
        $("#sig-qc-search").addEventListener("input", filterPicker);

        loadProjectList();
        if (preloadProject) {
            loadChecklist(preloadProject);
        }

        function loadProjectList() {
            frappe.call({
                method: "frappe.client.get_list",
                args: {
                    doctype: "Project",
                    fields: [
                        "name",
                        "project_name",
                        "customer",
                        "custom_qc_status",
                        "custom_city",
                        "custom_project_type_ol",
                        "status",
                    ],
                    filters: [["status", "!=", "Cancelled"]],
                    order_by: "modified desc",
                    limit: 100,
                },
                callback(r) {
                    if (r.exc) return;
                    allPickerProjects = r.message || [];
                    renderPickerList(allPickerProjects);
                },
            });
        }

        function filterPicker() {
            const query = ($("#sig-qc-search").value || "").toLowerCase();
            if (!query) {
                renderPickerList(allPickerProjects);
                return;
            }
            renderPickerList(allPickerProjects.filter((item) => {
                return (item.project_name || "").toLowerCase().includes(query)
                    || (item.customer || "").toLowerCase().includes(query)
                    || (item.custom_city || "").toLowerCase().includes(query);
            }));
        }

        function renderPickerList(projects) {
            const el = $("#sig-qc-picker-list");
            if (!projects.length) {
                el.innerHTML = '<p class="sig-qc-meta">No projects found.</p>';
                return;
            }

            el.innerHTML = projects.map((item) => {
                const badgeCls = QC_STATUS_BADGE[item.custom_qc_status] || "sig-qc-badge-gray";
                return `
                    <div class="sig-qc-picker-item" data-project="${esc(item.name)}">
                        <div class="sig-qc-picker-item-left">
                            <div class="sig-qc-picker-item-name">${esc(item.project_name)}</div>
                            <div class="sig-qc-picker-item-sub">
                                ${esc(item.customer || "")}
                                ${item.custom_city ? " · " + esc(item.custom_city) : ""}
                                ${item.custom_project_type_ol ? " · " + esc(item.custom_project_type_ol) : ""}
                            </div>
                        </div>
                        <span class="sig-qc-badge ${badgeCls}">${esc(item.custom_qc_status || "Not Started")}</span>
                        <span class="sig-qc-picker-arrow">›</span>
                    </div>`;
            }).join("");

            el.querySelectorAll(".sig-qc-picker-item").forEach((item) => {
                item.addEventListener("click", () => loadChecklist(item.dataset.project));
            });
        }

        function loadChecklist(projectName) {
            frappe.call({
                method: "orderlift.orderlift_sig.api.dashboard_api.get_qc_checklist",
                args: { project_name: projectName },
                callback(r) {
                    if (r.exc || !r.message) return;
                    project = r.message;
                    activeCategory = "All";
                    renderChecklist();
                    showScreen("checklist");
                },
            });
        }

        function renderChecklist() {
            $("#sig-qc-topbar-title").textContent = project.project_display || project.project_name;
            const badge = $("#sig-qc-status-badge");
            badge.textContent = project.qc_status || "Not Started";
            badge.className = `sig-qc-badge ${QC_STATUS_BADGE[project.qc_status] || "sig-qc-badge-gray"}`;

            updateProgress();

            const categories = ["All", ...new Set(project.rows.map((row) => row.category || "Other"))];
            const tabs = $("#sig-qc-tabs");
            tabs.innerHTML = categories.map((category) => `
                <button class="sig-qc-tab ${category === activeCategory ? "is-active" : ""}" data-cat="${esc(category)}">${esc(category)}</button>`).join("");

            tabs.querySelectorAll(".sig-qc-tab").forEach((button) => {
                button.addEventListener("click", () => {
                    activeCategory = button.dataset.cat;
                    renderChecklist();
                });
            });

            renderItems();
        }

        function renderItems() {
            const rows = activeCategory === "All"
                ? project.rows
                : project.rows.filter((row) => (row.category || "Other") === activeCategory);

            const el = $("#sig-qc-items");
            el.innerHTML = rows.map((row) => `
                <div class="sig-qc-item ${row.is_verified ? "is-verified" : ""} ${row.is_mandatory ? "is-mandatory" : ""}" data-row="${esc(row.name)}">
                    <div class="sig-qc-check">${row.is_verified ? "✓" : ""}</div>
                    <div class="sig-qc-item-body">
                        <div class="sig-qc-item-name">
                            ${esc(row.item_code)}
                            ${row.is_mandatory ? '<span style="color:#fd7e14;margin-left:4px" title="Mandatory">★</span>' : ""}
                        </div>
                        ${row.description ? `<div class="sig-qc-item-desc">${esc(row.description)}</div>` : ""}
                        ${row.verified_by ? `<div class="sig-qc-item-meta">Verified by ${esc(row.verified_by)} ${row.verified_on ? "on " + row.verified_on.split(" ")[0] : ""}</div>` : ""}
                        <div class="sig-qc-remarks-wrap">
                            <textarea class="sig-qc-remarks" data-row="${esc(row.name)}" placeholder="Add remarks..." rows="1">${esc(row.remarks || "")}</textarea>
                        </div>
                    </div>
                </div>`).join("");

            el.querySelectorAll(".sig-qc-item").forEach((item) => {
                item.addEventListener("click", (event) => {
                    if (event.target.tagName === "TEXTAREA") return;
                    const row = project.rows.find((entry) => entry.name === item.dataset.row);
                    if (!row) return;
                    row.is_verified = row.is_verified ? 0 : 1;
                    pendingSave = true;
                    renderChecklist();
                });
            });

            el.querySelectorAll(".sig-qc-remarks").forEach((textarea) => {
                textarea.addEventListener("input", () => {
                    pendingSave = true;
                });
                textarea.addEventListener("blur", () => {
                    const row = project.rows.find((entry) => entry.name === textarea.dataset.row);
                    if (row) row.remarks = textarea.value;
                });
            });
        }

        function updateProgress() {
            const total = project.rows.length;
            const verified = project.rows.filter((row) => row.is_verified).length;
            const pct = total ? Math.round((verified / total) * 100) : 0;

            const color = project.qc_status === "Complete" ? "#28a745"
                : project.qc_status === "Blocked" ? "#dc3545"
                    : project.qc_status === "In Progress" ? "#fd7e14"
                        : "#adb5bd";

            const bar = $("#sig-qc-progress-bar");
            bar.style.width = `${pct}%`;
            bar.style.background = color;
            $("#sig-qc-progress-label").textContent = `${verified} / ${total} verified (${pct}%)`;
        }

        async function saveAll() {
            if (saving || !project) return;
            saving = true;
            const btn = $("#sig-qc-save-btn");
            btn.disabled = true;
            btn.textContent = "Saving...";

            root.querySelectorAll(".sig-qc-remarks").forEach((textarea) => {
                const row = project.rows.find((entry) => entry.name === textarea.dataset.row);
                if (row) row.remarks = textarea.value;
            });

            try {
                const response = await new Promise((resolve, reject) => {
                    frappe.call({
                        method: "orderlift.orderlift_sig.utils.project_qc.save_qc_checklist",
                        args: {
                            project_name: project.project_name,
                            rows: project.rows.map((row) => ({
                                name: row.name,
                                is_verified: row.is_verified ? 1 : 0,
                                remarks: row.remarks || "",
                            })),
                        },
                        callback(r) {
                            if (r.exc) {
                                reject(r.exc);
                                return;
                            }
                            resolve(r.message || {});
                        },
                    });
                });
                project.qc_status = response.qc_status || project.qc_status;
                pendingSave = false;
                renderChecklist();
                toast("Saved successfully!", "success");
            } catch (error) {
                toast("Save failed. Please try again.", "error");
            } finally {
                saving = false;
                btn.disabled = false;
                btn.textContent = "✓ Save Progress";
            }
        }

        function showScreen(name) {
            $("#sig-qc-picker").classList.toggle("sig-qc-screen-hidden", name !== "picker");
            $("#sig-qc-checklist").classList.toggle("sig-qc-screen-hidden", name !== "checklist");
        }

        function goBack() {
            if ($("#sig-qc-checklist").classList.contains("sig-qc-screen-hidden")) {
                global.history.back();
                return;
            }
            if (pendingSave && !global.confirm("You have unsaved changes. Discard and go back?")) {
                return;
            }
            project = null;
            pendingSave = false;
            showScreen("picker");
        }

        function toast(message, type) {
            const toastRoot = $("#sig-qc-toast-root");
            const el = document.createElement("div");
            el.className = `sig-qc-toast sig-qc-toast-${type || "info"}`;
            el.textContent = message;
            toastRoot.appendChild(el);
            setTimeout(() => el.classList.add("in"), 10);
            setTimeout(() => {
                el.classList.remove("in");
                setTimeout(() => el.remove(), 300);
            }, 2800);
        }
    }

    function esc(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;");
    }

    global.orderliftSigQc = {
        mount,
    };

    function autoMount() {
        const root = document.getElementById("sig-qc-page-shell");
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
