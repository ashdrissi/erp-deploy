/* Pricing Benchmark Policy – custom form UX */

const SOURCES_HELP = `
<div class="pbp-help-panel pbp-help-sources">
    <div class="pbp-help-icon">📊</div>
    <div class="pbp-help-body">
        <div class="pbp-help-title">${__("What are Benchmark Sources?")}</div>
        <p>${__("Each source is a <strong>Price List</strong> used as benchmark reference. The system now auto-detects whether the policy is market-based, supplier-based, or mixed based on the active source lists you add here. The engine fetches item prices from active sources and combines them using Median / Average / Weighted Average.")}</p>
        <ul>
            <li><strong>${__("Price List")}</strong> — ${__("Select an existing Selling price list (e.g. 'Competitor A Selling')")}</li>
            <li><strong>${__("Label")}</strong> — ${__("A friendly name shown in reports (e.g. 'Competitor A')")}</li>
            <li><strong>${__("Weight")}</strong> — ${__("Only used with Weighted Average. Default 1 = equal trust. Higher = more influence.")}</li>
            <li><strong>${__("Is Active")}</strong> — ${__("Uncheck to temporarily exclude a source without deleting it")}</li>
        </ul>
    </div>
</div>`;

const RULES_HELP = `
<div class="pbp-help-panel pbp-help-rules">
    <div class="pbp-help-icon">🎯</div>
    <div class="pbp-help-body">
        <div class="pbp-help-title">${__("How Ratio-Band Rules Work")}</div>
        <p>${__("The engine computes: <code>ratio = landed_cost ÷ benchmark_reference</code>. A <strong>low ratio</strong> means your cost is much below market — you can charge more margin. A <strong>high ratio</strong> means costs are near market — margin must compress.")}</p>
        <table class="pbp-ratio-example">
            <thead><tr><th>${__("Ratio Range")}</th><th>${__("Meaning")}</th><th>${__("Example Margin")}</th></tr></thead>
            <tbody>
                <tr><td>0.00 – 0.60</td><td>${__("Strong cost advantage")}</td><td class="pbp-margin-high">30%</td></tr>
                <tr><td>0.60 – 0.80</td><td>${__("Moderate position")}</td><td class="pbp-margin-mid">18%</td></tr>
                <tr><td>0.80 – ∞</td><td>${__("Tight / at-market")}</td><td class="pbp-margin-low">8%</td></tr>
            </tbody>
        </table>
        <p style="margin-top:8px;font-size:12px;color:#64748b;">${__("Tip: Set Ratio Max to 0 for 'unlimited' (catches everything above Ratio Min). Use scope filters (Customer Group, Material, Territory) to create targeted rules.")}</p>
    </div>
</div>`;

function benchmarkRuleCustomerGroups(frm) {
    const values = [];
    for (const row of frm.doc.benchmark_rules || []) {
        if (!row.customer_type) {
            continue;
        }
        values.push(row.customer_type);
    }
    return [...new Set(values)];
}

function applyTierModifierCustomerGroupQuery(frm) {
    const groups = benchmarkRuleCustomerGroups(frm);
    const field = frm.fields_dict.tier_modifiers?.grid?.get_field("customer_group");
    if (!field) {
        return;
    }

    field.get_query = () => {
        if (!groups.length) {
            return {};
        }
        return { filters: { name: ["in", groups] } };
    };
    frm.refresh_field("tier_modifiers");
}

frappe.ui.form.on("Pricing Benchmark Policy", {
    refresh(frm) {
        _inject_styles();
        frm.fields_dict.sources_help_html && frm.fields_dict.sources_help_html.$wrapper.html(SOURCES_HELP);
        frm.fields_dict.rules_help_html && frm.fields_dict.rules_help_html.$wrapper.html(RULES_HELP);
        _style_form(frm);
        applyTierModifierCustomerGroupQuery(frm);
    },
    benchmark_rules_add(frm) {
        applyTierModifierCustomerGroupQuery(frm);
    },
    benchmark_rules_remove(frm) {
        applyTierModifierCustomerGroupQuery(frm);
    },
});

frappe.ui.form.on("Pricing Benchmark Rule", {
    customer_type(frm) {
        applyTierModifierCustomerGroupQuery(frm);
    },
});

function _style_form(frm) {
    if (!frm.page || !frm.page.wrapper) return;
    frm.page.wrapper.addClass("pbp-form-root");
}

function _inject_styles() {
    if (document.getElementById("pbp-form-css")) return;
    const style = document.createElement("style");
    style.id = "pbp-form-css";
    style.textContent = `
        /* ── Help Panels ── */
        .pbp-help-panel {
            display: flex;
            gap: 14px;
            background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
            border: 1px solid #bae6fd;
            border-radius: 10px;
            padding: 16px 20px;
            margin-bottom: 14px;
        }
        .pbp-help-sources {
            background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
            border-color: #bae6fd;
        }
        .pbp-help-rules {
            background: linear-gradient(135deg, #fefce8 0%, #fef9c3 100%);
            border-color: #fde68a;
        }
        .pbp-help-icon {
            font-size: 28px;
            flex-shrink: 0;
            margin-top: 2px;
        }
        .pbp-help-body {
            flex: 1;
            min-width: 0;
        }
        .pbp-help-title {
            font-weight: 700;
            font-size: 14px;
            color: #0c4a6e;
            margin-bottom: 6px;
        }
        .pbp-help-rules .pbp-help-title { color: #713f12; }
        .pbp-help-body p {
            font-size: 13px;
            color: #334155;
            margin-bottom: 8px;
            line-height: 1.5;
        }
        .pbp-help-body ul {
            padding-left: 18px;
            margin: 0 0 6px;
        }
        .pbp-help-body li {
            font-size: 12.5px;
            color: #475569;
            margin-bottom: 4px;
            line-height: 1.4;
        }
        .pbp-help-body code {
            background: rgba(0,0,0,0.06);
            padding: 1px 5px;
            border-radius: 4px;
            font-size: 12px;
        }

        /* ── Ratio Example Table ── */
        .pbp-ratio-example {
            width: 100%;
            border-collapse: collapse;
            font-size: 12.5px;
            margin-top: 6px;
        }
        .pbp-ratio-example th {
            background: rgba(0,0,0,0.04);
            padding: 6px 10px;
            text-align: left;
            font-weight: 600;
            color: #64748b;
            border-bottom: 1px solid #e2e8f0;
        }
        .pbp-ratio-example td {
            padding: 6px 10px;
            color: #334155;
            border-bottom: 1px solid #f1f5f9;
        }
        .pbp-margin-high { color: #166534; font-weight: 700; }
        .pbp-margin-mid  { color: #92400e; font-weight: 700; }
        .pbp-margin-low  { color: #991b1b; font-weight: 700; }

        /* ── Form polish ── */
        .pbp-form-root .form-section .section-head {
            font-weight: 700;
            font-size: 14px;
            color: #1e293b;
            padding-bottom: 8px;
            border-bottom: 2px solid #e2e8f0;
        }
    `;
    document.head.appendChild(style);
}
