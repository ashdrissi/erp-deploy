/* Pricing Dashboard – Master Simulation & Benchmark View */
frappe.pages["pricing-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Pricing Dashboard"),
        single_column: true,
    });

    page.main.addClass("pd-root");
    _inject_pd_styles();

    // Filters
    page.add_field({
        fieldname: "pricing_scenario",
        label: __("Scenario"),
        fieldtype: "Link",
        options: "Pricing Scenario",
        change: () => _refresh(page),
    });
    page.add_field({
        fieldname: "customer",
        label: __("Customer"),
        fieldtype: "Link",
        options: "Customer",
        change: () => _refresh(page),
    });
    page.add_field({
        fieldname: "pricing_sheet",
        label: __("Pricing Sheet"),
        fieldtype: "Link",
        options: "Pricing Sheet",
        change: () => _refresh(page),
    });

    page.set_primary_action(__("Refresh"), () => _refresh(page), "refresh");

    // Initial load
    _refresh(page);
};

async function _refresh(page) {
    const filters = {
        pricing_scenario: page.fields_dict.pricing_scenario.get_value(),
        customer: page.fields_dict.customer.get_value(),
        pricing_sheet: page.fields_dict.pricing_sheet.get_value(),
    };

    page.main.find(".pd-content").remove();
    page.main.append(`<div class="pd-content"><div class="pd-loading"><div class="pd-spinner"></div><span>${__("Loading pricing data…")}</span></div></div>`);

    try {
        const r = await frappe.call({
            method: "orderlift.orderlift_sales.page.pricing_dashboard.pricing_dashboard.get_dashboard_data",
            args: { filters },
        });
        const data = r.message || {};
        _render(page, data);
    } catch (e) {
        page.main.find(".pd-content").html(`<div class="pd-error">${__("Failed to load dashboard data.")}</div>`);
    }
}

function _render(page, data) {
    const k = data.kpis || {};
    const items = data.items || [];
    const sheets = data.sheets || [];

    const marginSourcePills = Object.entries(k.margin_sources || {})
        .map(([src, count]) => {
            const colors = { Benchmark: "#d1fae5", Profile: "#fef3c7", Fallback: "#fee2e2", Unknown: "#f1f5f9" };
            const textColors = { Benchmark: "#065f46", Profile: "#92400e", Fallback: "#991b1b", Unknown: "#64748b" };
            return `<span class="pd-pill" style="background:${colors[src] || colors.Unknown};color:${textColors[src] || textColors.Unknown}">${__(src)} <strong>${count}</strong></span>`;
        })
        .join("");

    const statusPills = Object.entries(k.status_counts || {})
        .map(([st, count]) => {
            const colors = { OK: "#d1fae5", "Too Low": "#fef3c7", "Too High": "#fee2e2", "No Benchmark": "#f1f5f9" };
            const textColors = { OK: "#065f46", "Too Low": "#92400e", "Too High": "#991b1b", "No Benchmark": "#64748b" };
            return `<span class="pd-pill" style="background:${colors[st] || "#f1f5f9"};color:${textColors[st] || "#64748b"}">${__(st)} <strong>${count}</strong></span>`;
        })
        .join("");

    const itemRows = items
        .map((i) => {
            const statusColor = { OK: "green", "Too Low": "orange", "Too High": "red", "No Benchmark": "gray" }[i.benchmark_status] || "gray";
            const sourceColor = { Benchmark: "green", Profile: "yellow", Fallback: "red" }[i.margin_source] || "gray";
            const ratioDisplay = i.benchmark_ratio ? i.benchmark_ratio.toFixed(3) : "-";
            return `
                <tr>
                    <td class="pd-cell-item">
                        <a href="/app/item/${encodeURIComponent(i.item)}">${frappe.utils.escape_html(i.item)}</a>
                    </td>
                    <td>${frappe.utils.escape_html(i.scenario || "-")}</td>
                    <td class="pd-cell-right">${frappe.format(i.qty, { fieldtype: "Float" })}</td>
                    <td class="pd-cell-right">${frappe.format(i.buy_price, { fieldtype: "Currency" })}</td>
                    <td class="pd-cell-right">${frappe.format(i.projected, { fieldtype: "Currency" })}</td>
                    <td class="pd-cell-right pd-cell-bold">${frappe.format(i.final_price, { fieldtype: "Currency" })}</td>
                    <td class="pd-cell-right">${i.margin_pct.toFixed(1)}%</td>
                    <td class="pd-cell-right">${i.benchmark_ref ? frappe.format(i.benchmark_ref, { fieldtype: "Currency" }) : "-"}</td>
                    <td class="pd-cell-right pd-cell-mono">${ratioDisplay}</td>
                    <td><span class="indicator-pill ${statusColor}">${__(i.benchmark_status || "-")}</span></td>
                    <td><span class="indicator-pill ${sourceColor}">${__(i.margin_source || "-")}</span></td>
                    <td class="pd-cell-sheet">
                        <a href="/app/pricing-sheet/${encodeURIComponent(i.sheet)}">${frappe.utils.escape_html(i.sheet_name || i.sheet)}</a>
                    </td>
                </tr>`;
        })
        .join("") || `<tr><td colspan="12" class="pd-empty">${__("No pricing data found. Try adjusting filters or create a Pricing Sheet first.")}</td></tr>`;

    const html = `
    <div class="pd-content">
        <!-- KPI Cards -->
        <div class="pd-kpi-row">
            <div class="pd-kpi pd-kpi-blue">
                <div class="pd-kpi-icon">📦</div>
                <div class="pd-kpi-body">
                    <div class="pd-kpi-value">${k.total_items || 0}</div>
                    <div class="pd-kpi-label">${__("Item Lines")}</div>
                </div>
            </div>
            <div class="pd-kpi pd-kpi-slate">
                <div class="pd-kpi-icon">📋</div>
                <div class="pd-kpi-body">
                    <div class="pd-kpi-value">${k.total_sheets || 0}</div>
                    <div class="pd-kpi-label">${__("Pricing Sheets")}</div>
                </div>
            </div>
            <div class="pd-kpi pd-kpi-green">
                <div class="pd-kpi-icon">📊</div>
                <div class="pd-kpi-body">
                    <div class="pd-kpi-value">${(k.avg_margin || 0).toFixed(1)}%</div>
                    <div class="pd-kpi-label">${__("Avg Margin")}</div>
                </div>
            </div>
            <div class="pd-kpi pd-kpi-amber">
                <div class="pd-kpi-icon">🎯</div>
                <div class="pd-kpi-body">
                    <div class="pd-kpi-value">${(k.benchmark_coverage || 0).toFixed(0)}%</div>
                    <div class="pd-kpi-label">${__("Benchmark Coverage")}</div>
                </div>
            </div>
            <div class="pd-kpi pd-kpi-purple">
                <div class="pd-kpi-icon">⚖️</div>
                <div class="pd-kpi-body">
                    <div class="pd-kpi-value">${(k.avg_ratio || 0).toFixed(3)}</div>
                    <div class="pd-kpi-label">${__("Avg Cost/Benchmark Ratio")}</div>
                </div>
            </div>
            <div class="pd-kpi pd-kpi-teal">
                <div class="pd-kpi-icon">🔀</div>
                <div class="pd-kpi-body">
                    <div class="pd-kpi-value">${k.scenarios_count || 0}</div>
                    <div class="pd-kpi-label">${__("Scenarios in Use")}</div>
                </div>
            </div>
        </div>

        <!-- Financial Summary -->
        <div class="pd-summary-row">
            <div class="pd-summary-card">
                <div class="pd-summary-label">${__("Total Buy Value")}</div>
                <div class="pd-summary-value">${frappe.format(k.total_buy || 0, { fieldtype: "Currency" })}</div>
            </div>
            <div class="pd-summary-card">
                <div class="pd-summary-label">${__("Total Sell Value")}</div>
                <div class="pd-summary-value pd-summary-green">${frappe.format(k.total_sell || 0, { fieldtype: "Currency" })}</div>
            </div>
            <div class="pd-summary-card">
                <div class="pd-summary-label">${__("Gross Margin")}</div>
                <div class="pd-summary-value pd-summary-blue">${frappe.format((k.total_sell || 0) - (k.total_buy || 0), { fieldtype: "Currency" })}</div>
            </div>
        </div>

        <!-- Margin Sources & Status Distribution -->
        <div class="pd-distrib-row">
            <div class="pd-distrib-card">
                <div class="pd-distrib-title">${__("Margin Source Distribution")}</div>
                <div class="pd-pill-row">${marginSourcePills || `<span class="pd-muted">${__("No data")}</span>`}</div>
            </div>
            <div class="pd-distrib-card">
                <div class="pd-distrib-title">${__("Benchmark Status Distribution")}</div>
                <div class="pd-pill-row">${statusPills || `<span class="pd-muted">${__("No data")}</span>`}</div>
            </div>
        </div>

        <!-- Item Table -->
        <div class="pd-table-card">
            <div class="pd-table-header">
                <div class="pd-table-title">${__("Item Simulation & Benchmark View")}</div>
                <div class="pd-table-count">${items.length} ${__("items")}</div>
            </div>
            <div class="pd-table-scroll">
                <table class="pd-table">
                    <thead>
                        <tr>
                            <th>${__("Item")}</th>
                            <th>${__("Scenario")}</th>
                            <th class="pd-th-right">${__("Qty")}</th>
                            <th class="pd-th-right">${__("Buy Price")}</th>
                            <th class="pd-th-right">${__("Projected")}</th>
                            <th class="pd-th-right">${__("Final Price")}</th>
                            <th class="pd-th-right">${__("Margin %")}</th>
                            <th class="pd-th-right">${__("Benchmark Ref")}</th>
                            <th class="pd-th-right">${__("Ratio")}</th>
                            <th>${__("Status")}</th>
                            <th>${__("Source")}</th>
                            <th>${__("Sheet")}</th>
                        </tr>
                    </thead>
                    <tbody>${itemRows}</tbody>
                </table>
            </div>
        </div>
    </div>`;

    page.main.find(".pd-content").remove();
    page.main.append(html);
}

function _inject_pd_styles() {
    if (document.getElementById("pd-dashboard-css")) return;
    const s = document.createElement("style");
    s.id = "pd-dashboard-css";
    s.textContent = `
    .pd-root { padding: 0 !important; }
    .pd-content { padding: 20px 24px; max-width: 1400px; margin: 0 auto; }

    /* Loading */
    .pd-loading { display:flex; align-items:center; gap:12px; padding:60px; justify-content:center; color:#64748b; font-size:14px; }
    .pd-spinner { width:24px; height:24px; border:3px solid #e2e8f0; border-top:3px solid #3b82f6; border-radius:50%; animation:pd-spin 0.8s linear infinite; }
    @keyframes pd-spin { to { transform:rotate(360deg); } }
    .pd-error { padding:40px; text-align:center; color:#991b1b; font-size:14px; }

    /* KPI Cards */
    .pd-kpi-row {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 14px;
        margin-bottom: 18px;
    }
    .pd-kpi {
        display: flex;
        align-items: center;
        gap: 14px;
        padding: 18px 20px;
        border-radius: 14px;
        border: 1px solid transparent;
        transition: transform 0.15s, box-shadow 0.15s;
    }
    .pd-kpi:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,0.08); }
    .pd-kpi-blue   { background: linear-gradient(135deg, #eff6ff, #dbeafe); border-color: #bfdbfe; }
    .pd-kpi-slate  { background: linear-gradient(135deg, #f8fafc, #f1f5f9); border-color: #e2e8f0; }
    .pd-kpi-green  { background: linear-gradient(135deg, #f0fdf4, #dcfce7); border-color: #bbf7d0; }
    .pd-kpi-amber  { background: linear-gradient(135deg, #fffbeb, #fef3c7); border-color: #fde68a; }
    .pd-kpi-purple { background: linear-gradient(135deg, #faf5ff, #f3e8ff); border-color: #e9d5ff; }
    .pd-kpi-teal   { background: linear-gradient(135deg, #f0fdfa, #ccfbf1); border-color: #99f6e4; }
    .pd-kpi-icon { font-size: 28px; flex-shrink: 0; }
    .pd-kpi-body { min-width: 0; }
    .pd-kpi-value { font-size: 22px; font-weight: 800; color: #1e293b; line-height: 1.2; }
    .pd-kpi-label { font-size: 12px; color: #64748b; margin-top: 2px; font-weight: 500; }

    /* Financial summary */
    .pd-summary-row {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 14px;
        margin-bottom: 18px;
    }
    .pd-summary-card {
        background: #fff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px 20px;
        text-align: center;
    }
    .pd-summary-label { font-size: 12px; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
    .pd-summary-value { font-size: 24px; font-weight: 800; color: #1e293b; margin-top: 4px; }
    .pd-summary-green { color: #166534 !important; }
    .pd-summary-blue  { color: #1d4ed8 !important; }

    /* Distribution */
    .pd-distrib-row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 14px;
        margin-bottom: 18px;
    }
    .pd-distrib-card {
        background: #fff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 14px 18px;
    }
    .pd-distrib-title { font-size: 13px; font-weight: 700; color: #334155; margin-bottom: 10px; }
    .pd-pill-row { display: flex; flex-wrap: wrap; gap: 8px; }
    .pd-pill { padding: 4px 12px; border-radius: 8px; font-size: 12px; font-weight: 600; display: inline-flex; align-items: center; gap: 6px; }
    .pd-muted { color: #94a3b8; font-size: 12px; }

    /* Table */
    .pd-table-card {
        background: #fff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        overflow: hidden;
    }
    .pd-table-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 14px 20px;
        background: linear-gradient(135deg, #f8fafc, #f1f5f9);
        border-bottom: 1px solid #e2e8f0;
    }
    .pd-table-title { font-weight: 700; font-size: 14px; color: #1e293b; }
    .pd-table-count { font-size: 12px; color: #64748b; font-weight: 600; background: #e2e8f0; padding: 3px 10px; border-radius: 6px; }
    .pd-table-scroll { overflow-x: auto; }
    .pd-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 12.5px;
    }
    .pd-table thead { background: #f8fafc; }
    .pd-table th {
        padding: 10px 14px;
        text-align: left;
        font-weight: 700;
        color: #64748b;
        font-size: 11.5px;
        text-transform: uppercase;
        letter-spacing: 0.3px;
        border-bottom: 2px solid #e2e8f0;
        white-space: nowrap;
    }
    .pd-th-right { text-align: right !important; }
    .pd-table td {
        padding: 10px 14px;
        color: #334155;
        border-bottom: 1px solid #f1f5f9;
        white-space: nowrap;
    }
    .pd-table tbody tr:hover { background: #f8fafc; }
    .pd-cell-right { text-align: right; }
    .pd-cell-bold { font-weight: 700; color: #1e293b; }
    .pd-cell-mono { font-family: "SF Mono", "Consolas", monospace; font-size: 12px; }
    .pd-cell-item a { color: #2563eb; font-weight: 600; text-decoration: none; }
    .pd-cell-item a:hover { text-decoration: underline; }
    .pd-cell-sheet a { color: #64748b; font-size: 11px; text-decoration: none; }
    .pd-cell-sheet a:hover { color: #2563eb; }
    .pd-empty { text-align: center; padding: 40px !important; color: #94a3b8; font-size: 13px; }

    @media (max-width: 768px) {
        .pd-kpi-row { grid-template-columns: repeat(2, 1fr); }
        .pd-distrib-row { grid-template-columns: 1fr; }
        .pd-summary-row { grid-template-columns: 1fr; }
    }
    `;
    document.head.appendChild(s);
}
