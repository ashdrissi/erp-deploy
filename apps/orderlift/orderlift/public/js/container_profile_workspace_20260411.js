/* ── Container Profile — Rich form intro card ─────────────────────────────── */

(function () {
    /* ── Inline keyframes (injected once) ─────────────────────────────────── */
    const ANIM_ID = "ol-cp-anim-style";
    if (!document.getElementById(ANIM_ID)) {
        const style = document.createElement("style");
        style.id = ANIM_ID;
        style.textContent = `
            @keyframes ol-cp-fadeup {
                from { opacity: 0; transform: translateY(10px); }
                to   { opacity: 1; transform: translateY(0); }
            }
            @keyframes ol-cp-bar-grow {
                from { width: 0 !important; }
            }
            .ol-cp-root { animation: ol-cp-fadeup 320ms cubic-bezier(.25,.46,.45,.94) both; }
            .ol-cp-bar-fill { animation: ol-cp-bar-grow 600ms cubic-bezier(.25,.46,.45,.94) both; }
            .ol-cp-stat-card:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(15,23,42,.10) !important; }
            .ol-cp-stat-card { transition: transform 180ms, box-shadow 180ms; }
            .ol-cp-zone-pill:hover { opacity: .8; }
        `;
        document.head.appendChild(style);
    }

    /* ── Container-type theme map ─────────────────────────────────────────── */
    const TYPE_THEME = {
        "20ft":            { bg: "#EFF6FF", accent: "#2563EB", border: "#BFDBFE", icon: "📦" },
        "40ft":            { bg: "#EEF2FF", accent: "#4338CA", border: "#C7D2FE", icon: "🏗️"  },
        "12m3 Van":        { bg: "#F0FDFA", accent: "#0D9488", border: "#99F6E4", icon: "🚐" },
        "Standard Truck":  { bg: "#FFFBEB", accent: "#B45309", border: "#FDE68A", icon: "🚛" },
        "Custom":          { bg: "#F8FAFC", accent: "#475569", border: "#E2E8F0", icon: "⚙️"  },
    };
    const DEFAULT_THEME = { bg: "#F8FAFC", accent: "#475569", border: "#E2E8F0", icon: "📦" };

    /* ── Format helpers ───────────────────────────────────────────────────── */
    function fmtWeight(v) {
        const n = Number(v || 0);
        return n >= 1000
            ? (n / 1000).toFixed(1).replace(/\.0$/, "") + " t"
            : n.toFixed(0) + " kg";
    }
    function fmtVolume(v) {
        return Number(v || 0).toFixed(1) + " m³";
    }
    function fmtDate(d) {
        if (!d) return null;
        try {
            return new Date(d).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
        } catch (_) { return d; }
    }
    function esc(s) {
        return frappe.utils.escape_html(String(s || ""));
    }

    /* ── Render ───────────────────────────────────────────────────────────── */
    function renderCapacityCard(frm) {
        const doc = frm.doc;
        const theme = TYPE_THEME[doc.container_type] || DEFAULT_THEME;

        const isActive = !!doc.is_active;
        const activePill = isActive
            ? `<span style="display:inline-flex;align-items:center;gap:5px;background:#F0FDF4;color:#15803D;border:1px solid #BBF7D0;font-size:11px;font-weight:700;padding:3px 10px;border-radius:999px;letter-spacing:.04em;">
                   <span style="width:6px;height:6px;border-radius:50%;background:#22C55E;display:inline-block;"></span>ACTIVE
               </span>`
            : `<span style="display:inline-flex;align-items:center;gap:5px;background:#F1F5F9;color:#64748B;border:1px solid #E2E8F0;font-size:11px;font-weight:700;padding:3px 10px;border-radius:999px;letter-spacing:.04em;">
                   <span style="width:6px;height:6px;border-radius:50%;background:#94A3B8;display:inline-block;"></span>INACTIVE
               </span>`;

        /* ── Zone pills ─── */
        const zonesRaw = String(doc.allowed_zones || "").trim();
        const zones = zonesRaw ? zonesRaw.split(",").map(z => z.trim()).filter(Boolean) : [];
        const zoneCount = zones.length;
        const zonePillsHtml = zones.length
            ? zones.map(z => `
                <span class="ol-cp-zone-pill" style="display:inline-flex;align-items:center;background:${theme.bg};color:${theme.accent};border:1px solid ${theme.border};font-size:11px;font-weight:700;padding:3px 10px;border-radius:999px;letter-spacing:.02em;cursor:default;">
                    ${esc(z)}
                </span>`).join("")
            : `<span style="font-size:12px;color:#94A3B8;font-style:italic;">All zones</span>`;

        /* ── Date range ─── */
        const fromDate = fmtDate(doc.active_from);
        const toDate   = fmtDate(doc.active_to);
        const dateRangeHtml = (fromDate || toDate)
            ? `<div style="display:flex;align-items:center;gap:8px;font-size:12px;color:#64748B;">
                   <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                   <span>${fromDate ? __("From") + " <b>" + esc(fromDate) + "</b>" : ""}${fromDate && toDate ? " &nbsp;→&nbsp; " : ""}${toDate ? (fromDate ? "" : __("Until") + " ") + "<b>" + esc(toDate) + "</b>" : ""}</span>
               </div>`
            : "";

        /* ── Stat cards ─── */
        function statCard(label, value, unit, svgPath, color, delay) {
            return `
                <div class="ol-cp-stat-card" style="
                    flex:1; min-width:110px; background:#fff; border:1px solid #F1F5F9;
                    border-radius:16px; padding:16px 18px; display:flex; flex-direction:column;
                    gap:6px; box-shadow:0 1px 4px rgba(15,23,42,.05);
                    animation: ol-cp-fadeup 320ms ${delay}ms cubic-bezier(.25,.46,.45,.94) both;">
                    <div style="width:34px;height:34px;border-radius:10px;background:${color}1a;color:${color};display:flex;align-items:center;justify-content:center;">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${svgPath}</svg>
                    </div>
                    <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#94A3B8;">${label}</div>
                    <div style="font-size:22px;font-weight:900;color:#0F172A;line-height:1;">${esc(value)}</div>
                    <div style="font-size:11px;color:#94A3B8;font-weight:500;">${esc(unit)}</div>
                </div>`;
        }

        const weightKg = Number(doc.max_weight_kg || 0);
        const volumeM3 = Number(doc.max_volume_m3 || 0);
        const costRank = Number(doc.cost_rank || 100);
        const density = weightKg > 0 && volumeM3 > 0 ? (weightKg / volumeM3) : 0;

        // Weight: show kg or tonnes
        const weightDisplay = weightKg >= 1000
            ? (weightKg / 1000).toFixed(1).replace(/\.0$/, "")
            : weightKg.toFixed(0);
        const weightUnit = weightKg >= 1000 ? "tonnes max" : "kg max";

        const statsHtml = `
            <div style="display:flex;gap:10px;flex-wrap:wrap;">
                ${statCard(
                    "Max Weight", weightDisplay, weightUnit,
                    `<circle cx="12" cy="5" r="3"/><path d="M6.5 8a2 2 0 0 0-1.905 1.46L2.1 18.5A2 2 0 0 0 4 21h16a2 2 0 0 0 1.925-2.54L19.4 9.5A2 2 0 0 0 17.48 8Z"/>`,
                    "#3B82F6", 0
                )}
                ${statCard(
                    "Max Volume", volumeM3.toFixed(1), "m³ max",
                    `<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>`,
                    "#6366F1", 60
                )}
                ${statCard(
                    "Cost Rank", String(costRank), costRank <= 50 ? "preferred" : costRank <= 100 ? "standard" : "fallback",
                    `<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>`,
                    costRank <= 50 ? "#10B981" : costRank <= 100 ? "#F59E0B" : "#94A3B8", 120
                )}
                ${statCard(
                    "Density", density ? density.toFixed(0) : "0", "kg / m³",
                    `<path d="M12 3v18"/><path d="M6 9l6-6 6 6"/><path d="M6 15l6 6 6-6"/>`,
                    "#EC4899", 180
                )}
            </div>`;

        /* ── Capacity bar visual ─── */
        const weightBar = Math.min((weightKg / 30000) * 100, 100);
        const volumeBar = Math.min((volumeM3 / 100) * 100, 100);

        const barsHtml = `
            <div style="display:flex;flex-direction:column;gap:10px;">
                <div>
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;">
                        <span style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:#64748B;">Weight capacity</span>
                        <span style="font-size:12px;font-weight:700;color:#0F172A;">${fmtWeight(doc.max_weight_kg)}</span>
                    </div>
                    <div style="height:6px;background:#F1F5F9;border-radius:3px;overflow:hidden;">
                        <div class="ol-cp-bar-fill" style="height:100%;width:${weightBar.toFixed(1)}%;background:linear-gradient(90deg,#3B82F6,#2563EB);border-radius:3px;"></div>
                    </div>
                </div>
                <div>
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;">
                        <span style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:#64748B;">Volume capacity</span>
                        <span style="font-size:12px;font-weight:700;color:#0F172A;">${fmtVolume(doc.max_volume_m3)}</span>
                    </div>
                    <div style="height:6px;background:#F1F5F9;border-radius:3px;overflow:hidden;">
                        <div class="ol-cp-bar-fill" style="height:100%;width:${volumeBar.toFixed(1)}%;background:linear-gradient(90deg,#6366F1,#4338CA);border-radius:3px;animation-delay:100ms;"></div>
                    </div>
                </div>
            </div>`;

        /* ── Full card HTML ─── */
        const html = `
            <div class="ol-cp-root" style="
                border-radius: 18px;
                overflow: hidden;
                border: 1px solid ${theme.border};
                background: #fff;
                box-shadow: 0 2px 12px rgba(15,23,42,.06);
                margin-bottom: 4px;
            ">
                <!-- Hero header -->
                <div style="
                    background: linear-gradient(135deg, ${theme.bg} 0%, #fff 60%);
                    border-bottom: 1px solid ${theme.border};
                    padding: 20px 24px;
                    display: flex;
                    align-items: flex-start;
                    justify-content: space-between;
                    gap: 16px;
                    flex-wrap: wrap;
                ">
                    <div style="display:flex;align-items:center;gap:14px;min-width:0;">
                        <div style="
                            width:48px; height:48px; border-radius:14px;
                            background:${theme.accent}18; color:${theme.accent};
                            display:flex; align-items:center; justify-content:center;
                            font-size:22px; flex-shrink:0;
                            border: 1px solid ${theme.border};
                        ">${theme.icon}</div>
                        <div style="min-width:0;">
                            <div style="font-size:18px;font-weight:800;color:#0F172A;margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                                ${esc(doc.container_name || doc.name || "")}
                            </div>
                            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                                ${doc.container_code ? `<span style="font-size:12px;color:#64748B;font-weight:500;font-family:monospace;">${esc(doc.container_code)}</span>` : ""}
                                ${doc.container_type ? `<span style="font-size:11px;font-weight:700;padding:2px 8px;border-radius:6px;background:${theme.accent}18;color:${theme.accent};border:1px solid ${theme.border};">${esc(doc.container_type)}</span>` : ""}
                            </div>
                        </div>
                    </div>
                    <div style="flex-shrink:0;">
                        ${activePill}
                    </div>
                </div>

                <!-- Stats row -->
                <div style="padding: 20px 24px; border-bottom: 1px solid #F8FAFC;">
                    ${statsHtml}
                </div>

                <!-- Capacity bars -->
                <div style="padding: 16px 24px; border-bottom: 1px solid #F8FAFC; background:#FAFBFC;">
                    ${barsHtml}
                </div>

                <!-- Footer: zones + dates -->
                <div style="padding: 14px 24px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;">
                    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                        <span style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#94A3B8;">Zones</span>
                        ${zonePillsHtml}
                    </div>
                    ${dateRangeHtml}
                </div>

                <!-- Bottom insight row -->
                <div style="padding: 14px 24px; border-top: 1px solid #F8FAFC; background:#FFFCFA; display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px;">
                    <div style="background:#fff;border:1px solid #F1F5F9;border-radius:12px;padding:12px 14px;">
                        <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#94A3B8;">Coverage</div>
                        <div style="font-size:16px;font-weight:800;color:#0F172A;margin-top:4px;">${zoneCount || "All"}</div>
                        <div style="font-size:11px;color:#64748B;margin-top:2px;">${zoneCount ? __("allowed zones") : __("all zones allowed")}</div>
                    </div>
                    <div style="background:#fff;border:1px solid #F1F5F9;border-radius:12px;padding:12px 14px;">
                        <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#94A3B8;">Profile Mode</div>
                        <div style="font-size:16px;font-weight:800;color:#0F172A;margin-top:4px;">${isActive ? __("Dispatch Ready") : __("Standby")}</div>
                        <div style="font-size:11px;color:#64748B;margin-top:2px;">${isActive ? __("available for recommendation") : __("excluded from planning")}</div>
                    </div>
                    <div style="background:#fff;border:1px solid #F1F5F9;border-radius:12px;padding:12px 14px;">
                        <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#94A3B8;">Quick Action</div>
                        <div style="font-size:16px;font-weight:800;color:${theme.accent};margin-top:4px;">${__("Review Plans")}</div>
                        <div style="font-size:11px;color:#64748B;margin-top:2px;">${__("open linked load plans from toolbar")}</div>
                    </div>
                </div>
            </div>
        `;

        frm.set_intro(html, false);
    }

    /* ── Frappe form bindings ─────────────────────────────────────────────── */
    frappe.ui.form.on("Container Profile", {
        refresh(frm) {
            renderCapacityCard(frm);

            if (!frm.doc.__islocal) {
                frm.add_custom_button(__("View Load Plans"), () => {
                    frappe.route_options = { container_profile: frm.doc.name };
                    frappe.set_route("List", "Container Load Plan");
                });
            }
        },

        container_name:  renderCapacityCard,
        container_code:  renderCapacityCard,
        container_type:  renderCapacityCard,
        max_weight_kg:   renderCapacityCard,
        max_volume_m3:   renderCapacityCard,
        is_active:       renderCapacityCard,
        allowed_zones:   renderCapacityCard,
        active_from:     renderCapacityCard,
        active_to:       renderCapacityCard,
        cost_rank:       renderCapacityCard,
    });
})();
