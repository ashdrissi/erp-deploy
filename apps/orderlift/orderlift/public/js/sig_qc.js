/* ============================================================
   SIG Mobile QC — /sig-qc
   Touch-optimised QC checklist for field technicians
   ============================================================ */

(function () {
    "use strict";

    // ── State ────────────────────────────────────────────────
    let _project = null;           // full checklist payload
    let _activeCategory = "All";
    let _pendingSave = false;       // dirty flag
    let _saving = false;

    const QC_STATUS_BADGE = {
        "Complete":    "sig-qc-badge-green",
        "In Progress": "sig-qc-badge-orange",
        "Blocked":     "sig-qc-badge-red",
        "Not Started": "sig-qc-badge-gray",
        "":            "sig-qc-badge-gray",
    };

    // ── Init ─────────────────────────────────────────────────
    document.addEventListener("DOMContentLoaded", () => {
        const root = document.getElementById("sig-qc-root");
        const preload = root ? root.dataset.preload : "";

        _loadProjectList();

        if (preload) {
            _loadChecklist(preload);
        }

        document.getElementById("sig-qc-back").addEventListener("click", _goBack);
        document.getElementById("sig-qc-save-btn").addEventListener("click", _saveAll);
        document.getElementById("sig-qc-search").addEventListener("input", _filterPicker);
    });

    // ── Project picker ────────────────────────────────────────

    let _allPickerProjects = [];

    function _loadProjectList() {
        frappe.call({
            method: "orderlift.orderlift_sig.api.map_api.get_map_projects",
            args: { filters: {} },
            callback(r) {
                if (r.exc) return;
                // Include projects even without geocoords for QC purposes
                frappe.call({
                    method: "frappe.client.get_list",
                    args: {
                        doctype: "Project",
                        fields: ["name", "project_name", "customer", "custom_qc_status",
                                 "custom_city", "custom_project_type_ol", "status"],
                        filters: [["status", "!=", "Cancelled"]],
                        order_by: "modified desc",
                        limit: 100,
                    },
                    callback(r2) {
                        if (r2.exc) return;
                        _allPickerProjects = r2.message || [];
                        _renderPickerList(_allPickerProjects);
                    },
                });
            },
        });
    }

    function _filterPicker() {
        const q = (document.getElementById("sig-qc-search").value || "").toLowerCase();
        if (!q) { _renderPickerList(_allPickerProjects); return; }
        const filtered = _allPickerProjects.filter(p =>
            (p.project_name || "").toLowerCase().includes(q) ||
            (p.customer     || "").toLowerCase().includes(q) ||
            (p.custom_city  || "").toLowerCase().includes(q)
        );
        _renderPickerList(filtered);
    }

    function _renderPickerList(projects) {
        const el = document.getElementById("sig-qc-picker-list");
        if (!projects.length) {
            el.innerHTML = `<p class="sig-qc-meta">No projects found.</p>`;
            return;
        }
        el.innerHTML = projects.map(p => {
            const badgeCls = QC_STATUS_BADGE[p.custom_qc_status] || "sig-qc-badge-gray";
            return `
                <div class="sig-qc-picker-item" data-project="${_esc(p.name)}">
                    <div class="sig-qc-picker-item-left">
                        <div class="sig-qc-picker-item-name">${_esc(p.project_name)}</div>
                        <div class="sig-qc-picker-item-sub">
                            ${_esc(p.customer || "")}
                            ${p.custom_city ? " · " + _esc(p.custom_city) : ""}
                            ${p.custom_project_type_ol ? " · " + _esc(p.custom_project_type_ol) : ""}
                        </div>
                    </div>
                    <span class="sig-qc-badge ${badgeCls}">${_esc(p.custom_qc_status || "Not Started")}</span>
                    <span class="sig-qc-picker-arrow">›</span>
                </div>`;
        }).join("");

        el.querySelectorAll(".sig-qc-picker-item").forEach(item => {
            item.addEventListener("click", () => _loadChecklist(item.dataset.project));
        });
    }

    // ── Checklist loading ─────────────────────────────────────

    function _loadChecklist(projectName) {
        frappe.call({
            method: "orderlift.orderlift_sig.api.dashboard_api.get_qc_checklist",
            args: { project_name: projectName },
            callback(r) {
                if (r.exc || !r.message) return;
                _project = r.message;
                _activeCategory = "All";
                _renderChecklist();
                _showScreen("checklist");
            },
        });
    }

    // ── Checklist rendering ───────────────────────────────────

    function _renderChecklist() {
        const p = _project;

        // Topbar
        document.getElementById("sig-qc-topbar-title").textContent =
            p.project_display || p.project_name;
        const badge = document.getElementById("sig-qc-status-badge");
        badge.textContent = p.qc_status || "Not Started";
        badge.className = "sig-qc-badge " + (QC_STATUS_BADGE[p.qc_status] || "sig-qc-badge-gray");

        // Progress
        _updateProgress();

        // Category tabs
        const categories = ["All", ...new Set(p.rows.map(r => r.category || "Other"))];
        const tabsEl = document.getElementById("sig-qc-tabs");
        tabsEl.innerHTML = categories.map(c => `
            <button class="sig-qc-tab ${c === _activeCategory ? "is-active" : ""}"
                    data-cat="${_esc(c)}">${_esc(c)}</button>`).join("");
        tabsEl.querySelectorAll(".sig-qc-tab").forEach(btn => {
            btn.addEventListener("click", () => {
                _activeCategory = btn.dataset.cat;
                tabsEl.querySelectorAll(".sig-qc-tab").forEach(b =>
                    b.classList.toggle("is-active", b.dataset.cat === _activeCategory));
                _renderItems();
            });
        });

        _renderItems();
    }

    function _renderItems() {
        const p = _project;
        const rows = _activeCategory === "All"
            ? p.rows
            : p.rows.filter(r => (r.category || "Other") === _activeCategory);

        const el = document.getElementById("sig-qc-items");
        el.innerHTML = rows.map(row => {
            const verified = row.is_verified ? "is-verified" : "";
            const mandatory = row.is_mandatory ? "is-mandatory" : "";
            return `
                <div class="sig-qc-item ${verified} ${mandatory}" data-row="${_esc(row.name)}">
                    <div class="sig-qc-check">${row.is_verified ? "✓" : ""}</div>
                    <div class="sig-qc-item-body">
                        <div class="sig-qc-item-name">
                            ${_esc(row.item_code)}
                            ${row.is_mandatory ? '<span style="color:#fd7e14;margin-left:4px" title="Mandatory">★</span>' : ""}
                        </div>
                        ${row.description ? `<div class="sig-qc-item-desc">${_esc(row.description)}</div>` : ""}
                        ${row.verified_by ? `<div class="sig-qc-item-meta">Verified by ${_esc(row.verified_by)} ${row.verified_on ? "on " + row.verified_on.split(" ")[0] : ""}</div>` : ""}
                        <div class="sig-qc-remarks-wrap">
                            <textarea class="sig-qc-remarks" data-row="${_esc(row.name)}"
                                      placeholder="Add remarks…"
                                      rows="1">${_esc(row.remarks || "")}</textarea>
                        </div>
                    </div>
                </div>`;
        }).join("");

        // Click to toggle verification
        el.querySelectorAll(".sig-qc-item").forEach(item => {
            // Toggle on click (but not on textarea interaction)
            item.addEventListener("click", (e) => {
                if (e.target.tagName === "TEXTAREA") return;
                const rowName = item.dataset.row;
                const row = p.rows.find(r => r.name === rowName);
                if (!row) return;
                row.is_verified = row.is_verified ? 0 : 1;
                _pendingSave = true;
                _renderChecklist();
            });
        });

        // Remarks change
        el.querySelectorAll(".sig-qc-remarks").forEach(ta => {
            ta.addEventListener("input", () => { _pendingSave = true; });
            // sync remarks value back to row on blur
            ta.addEventListener("blur", () => {
                const rowName = ta.dataset.row;
                const row = p.rows.find(r => r.name === rowName);
                if (row) row.remarks = ta.value;
            });
        });
    }

    function _updateProgress() {
        const rows = _project.rows;
        const total = rows.length;
        const verified = rows.filter(r => r.is_verified).length;
        const pct = total ? Math.round((verified / total) * 100) : 0;

        const qc = _project.qc_status;
        const barColor = qc === "Complete"    ? "#28a745"
                       : qc === "Blocked"     ? "#dc3545"
                       : qc === "In Progress" ? "#fd7e14"
                       : "#adb5bd";

        const bar = document.getElementById("sig-qc-progress-bar");
        if (bar) { bar.style.width = pct + "%"; bar.style.background = barColor; }
        const lbl = document.getElementById("sig-qc-progress-label");
        if (lbl) lbl.textContent = `${verified} / ${total} verified (${pct}%)`;
    }

    // ── Save all (batch sync) ─────────────────────────────────

    async function _saveAll() {
        if (_saving) return;
        _saving = true;
        const btn = document.getElementById("sig-qc-save-btn");
        if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }

        // Sync remarks first from textarea values
        document.querySelectorAll(".sig-qc-remarks").forEach(ta => {
            const row = _project.rows.find(r => r.name === ta.dataset.row);
            if (row) row.remarks = ta.value;
        });

        try {
            // Call sync for each row that has changed
            for (const row of _project.rows) {
                await new Promise((resolve, reject) => {
                    frappe.call({
                        method: "orderlift.orderlift_sig.utils.project_qc.sync_qc_item_verification",
                        args: {
                            project_name: _project.project_name,
                            row_name: row.name,
                            is_verified: row.is_verified ? 1 : 0,
                        },
                        callback(r) {
                            if (r.exc) { reject(r.exc); return; }
                            // Update local QC status from server response
                            if (r.message) {
                                _project.qc_status = r.message.qc_status;
                            }
                            resolve();
                        },
                    });
                });
            }
            _pendingSave = false;
            _renderChecklist();
            _toast("Saved successfully!", "success");
        } catch (err) {
            _toast("Save failed. Please try again.", "error");
        } finally {
            _saving = false;
            if (btn) { btn.disabled = false; btn.textContent = "✓ Save Progress"; }
        }
    }

    // ── Navigation ────────────────────────────────────────────

    function _showScreen(name) {
        document.getElementById("sig-qc-picker").classList.toggle(
            "sig-qc-screen-hidden", name !== "picker");
        document.getElementById("sig-qc-checklist").classList.toggle(
            "sig-qc-screen-hidden", name !== "checklist");
    }

    function _goBack() {
        if (document.getElementById("sig-qc-checklist").classList.contains("sig-qc-screen-hidden")) {
            history.back();
        } else {
            if (_pendingSave) {
                if (!confirm("You have unsaved changes. Discard and go back?")) return;
            }
            _project = null;
            _pendingSave = false;
            _showScreen("picker");
        }
    }

    // ── Toast ─────────────────────────────────────────────────

    function _toast(msg, type) {
        const root = document.getElementById("sig-qc-toast-root");
        const el = document.createElement("div");
        el.className = `sig-qc-toast sig-qc-toast-${type || "info"}`;
        el.textContent = msg;
        root.appendChild(el);
        setTimeout(() => el.classList.add("in"), 10);
        setTimeout(() => {
            el.classList.remove("in");
            setTimeout(() => el.remove(), 300);
        }, 2800);
    }

    // ── Escape helper ─────────────────────────────────────────

    function _esc(s) {
        return String(s == null ? "" : s)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

})();
