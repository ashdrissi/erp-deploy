/* Pricing Margin Policy – custom form UX */

const BENCHMARK_HELP = `
<div class="pmp-help-panel">
    <div class="pmp-help-icon">⚡</div>
    <div class="pmp-help-body">
        <div class="pmp-help-title">${__("How Margin Modes Work")}</div>
        <table class="pmp-mode-table">
            <thead>
                <tr>
                    <th>${__("Mode")}</th>
                    <th>${__("What Happens")}</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><span class="pmp-mode-badge pmp-profile">${__("Profile-Based")}</span></td>
                    <td>${__("Uses the <strong>Margin Rules</strong> table below. Margin is selected by matching customer type, territory, tier, sales person, etc. This is the original behaviour.")}</td>
                </tr>
                <tr>
                    <td><span class="pmp-mode-badge pmp-benchmark">${__("Benchmark-Driven")}</span></td>
                    <td>${__("Ignores margin rules. Computes <code>ratio = landed_cost ÷ benchmark</code> and selects margin from <strong>ratio-band rules</strong> in the linked Benchmark Policy. Falls back to Fallback Margin % if benchmark data is insufficient.")}</td>
                </tr>
                <tr>
                    <td><span class="pmp-mode-badge pmp-hybrid">${__("Benchmark then Profile")}</span></td>
                    <td>${__("Tries benchmark first. If benchmark data is unavailable or no rule matches, falls back to the profile-based Margin Rules. Best of both worlds.")}</td>
                </tr>
            </tbody>
        </table>
        <p class="pmp-help-tip">💡 ${__("Tip: Start with <strong>Benchmark then Profile</strong> to test benchmarking while keeping profile rules as a safety net.")}</p>
    </div>
</div>`;

frappe.ui.form.on("Pricing Margin Policy", {
    refresh(frm) {
        _inject_pmp_styles();
        if (frm.fields_dict.benchmark_help_html) {
            frm.fields_dict.benchmark_help_html.$wrapper.html(BENCHMARK_HELP);
        }
        _style_pmp_form(frm);
    },

    margin_mode(frm) {
        _update_mode_indicator(frm);
    },
});

function _update_mode_indicator(frm) {
    const mode = frm.doc.margin_mode || "Profile-Based";
    const colors = {
        "Profile-Based": "yellow",
        "Benchmark-Driven": "green",
        "Benchmark then Profile": "blue",
    };
    frm.page.set_indicator(mode, colors[mode] || "gray");
}

function _style_pmp_form(frm) {
    if (!frm.page || !frm.page.wrapper) return;
    frm.page.wrapper.addClass("pmp-form-root");
    _update_mode_indicator(frm);
}

function _inject_pmp_styles() {
    if (document.getElementById("pmp-form-css")) return;
    const style = document.createElement("style");
    style.id = "pmp-form-css";
    style.textContent = `
        /* ── Help Panel ── */
        .pmp-help-panel {
            display: flex;
            gap: 14px;
            background: linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%);
            border: 1px solid #d8b4fe;
            border-radius: 10px;
            padding: 16px 20px;
            margin-bottom: 14px;
        }
        .pmp-help-icon {
            font-size: 28px;
            flex-shrink: 0;
            margin-top: 2px;
        }
        .pmp-help-body { flex: 1; min-width: 0; }
        .pmp-help-title {
            font-weight: 700;
            font-size: 14px;
            color: #581c87;
            margin-bottom: 10px;
        }
        .pmp-help-body p { font-size: 13px; color: #334155; margin: 0; line-height: 1.5; }
        .pmp-help-body code {
            background: rgba(0,0,0,0.06);
            padding: 1px 5px;
            border-radius: 4px;
            font-size: 12px;
        }
        .pmp-help-tip {
            margin-top: 10px !important;
            padding: 8px 12px;
            background: #f0fdf4;
            border-radius: 8px;
            border: 1px solid #bbf7d0;
            font-size: 12.5px !important;
            color: #166534 !important;
        }

        /* ── Mode Table ── */
        .pmp-mode-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            margin-bottom: 6px;
        }
        .pmp-mode-table th {
            background: rgba(0,0,0,0.04);
            padding: 8px 12px;
            text-align: left;
            font-weight: 600;
            color: #64748b;
            border-bottom: 1px solid #e2e8f0;
        }
        .pmp-mode-table td {
            padding: 10px 12px;
            color: #334155;
            border-bottom: 1px solid #f1f5f9;
            vertical-align: top;
            line-height: 1.5;
        }
        .pmp-mode-badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 6px;
            font-size: 11.5px;
            font-weight: 700;
            white-space: nowrap;
        }
        .pmp-profile   { background: #fef3c7; color: #92400e; }
        .pmp-benchmark  { background: #d1fae5; color: #065f46; }
        .pmp-hybrid     { background: #dbeafe; color: #1e40af; }

        /* ── Form polish ── */
        .pmp-form-root .form-section .section-head {
            font-weight: 700;
            font-size: 14px;
            color: #1e293b;
            padding-bottom: 8px;
            border-bottom: 2px solid #e2e8f0;
        }
    `;
    document.head.appendChild(style);
}
