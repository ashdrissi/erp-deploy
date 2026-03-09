function getActiveExpenseRows(frm) {
    return (frm.doc.expenses || [])
        .filter((row) => row.is_active)
        .sort((a, b) => (a.sequence || 0) - (b.sequence || 0));
}

function formatExpenseValue(row) {
    const fieldtype = row.type === "Percentage" ? "Percent" : "Currency";
    return frappe.format(row.value || 0, { fieldtype });
}

function getExpenseStats(rows) {
    return rows.reduce(
        (acc, row) => {
            const type = row.type || "Percentage";
            const scope = row.scope || "Per Unit";

            acc.total += 1;
            acc[type] = (acc[type] || 0) + 1;
            acc[scope] = (acc[scope] || 0) + 1;
            return acc;
        },
        { total: 0, Percentage: 0, Fixed: 0, "Per Unit": 0, "Per Line": 0, "Per Sheet": 0 }
    );
}

function renderExpenseGuide(frm) {
    const rows = getActiveExpenseRows(frm);
    const stats = getExpenseStats(rows);
    const transportEnabled = !!frm.doc.transport_is_active;
    const transportMode = frappe.utils.escape_html(frm.doc.transport_allocation_mode || "By Value");
    const transportPrice = frappe.format(frm.doc.transport_container_price || 0, { fieldtype: "Currency" });

    const cards = [
        { label: __("Active Expenses"), value: stats.total, tone: "slate" },
        { label: __("Percentage"), value: stats.Percentage, tone: "green" },
        { label: __("Fixed"), value: stats.Fixed, tone: "amber" },
        { label: __("Per Sheet"), value: stats["Per Sheet"], tone: "blue" },
    ]
        .map(
            (card) => `
                <div class="ep-card is-${card.tone}">
                    <span>${frappe.utils.escape_html(card.label)}</span>
                    <strong>${card.value}</strong>
                </div>
            `
        )
        .join("");

    const flow = rows
        .map(
            (row) => `
                <div class="ep-flow-row">
                    <div class="ep-flow-seq">#${row.sequence || "-"}</div>
                    <div class="ep-flow-body">
                        <div class="ep-flow-head">
                            <strong>${frappe.utils.escape_html(row.label || __("Expense"))}</strong>
                            <span class="ep-pill">${frappe.utils.escape_html(row.type || "Percentage")}</span>
                            <span class="ep-pill">${frappe.utils.escape_html(row.scope || "Per Unit")}</span>
                        </div>
                        <div class="ep-flow-meta">${formatExpenseValue(row)} ${__("on Base Price")}</div>
                        ${row.notes ? `<div class="ep-flow-note">${frappe.utils.escape_html(row.notes)}</div>` : ""}
                    </div>
                </div>
            `
        )
        .join("");

    const transportBadge = transportEnabled
        ? `<span class="ep-chip ep-chip--on">${__("Enabled")}</span>`
        : `<span class="ep-chip ep-chip--off">${__("Disabled")}</span>`;

    const html = `
        <div class="ep-shell">
            <div class="ep-hero">
                <div>
                    <div class="ep-eyebrow">${__("Expenses Policy")}</div>
                    <h3>${frappe.utils.escape_html(frm.doc.scenario_name || __("Untitled policy"))}</h3>
                    <p>${__("This policy defines the base expense stack and optional transport allocation used before margin and runtime modifiers are applied.")}</p>
                </div>
                <div class="ep-transport-box">
                    <div class="ep-transport-head">${__("Transport Allocation")}</div>
                    <div class="ep-transport-state">${transportBadge}</div>
                    <div class="ep-transport-meta">${transportMode} - ${transportPrice}</div>
                </div>
            </div>

            <div class="ep-card-grid">${cards}</div>

            <div class="ep-section">
                <div class="ep-section-head">
                    <strong>${__("Calculation Flow")}</strong>
                    <span>${__("Applied in ascending sequence order")}</span>
                </div>
                <div class="ep-flow-list">
                    ${flow || `<div class="ep-empty">${__("No active expenses yet. Add rows or use one of the starter templates below.")}</div>`}
                </div>
            </div>

            <div class="ep-section ep-section--muted">
                <div class="ep-section-head">
                    <strong>${__("How It Works")}</strong>
                </div>
                <div class="ep-guidance">
                    <div><b>${__("Percentage")}</b>: ${__("compounds on the running unit price.")}</div>
                    <div><b>${__("Fixed / Per Unit")}</b>: ${__("adds the same amount to each unit.")}</div>
                    <div><b>${__("Fixed / Per Line")}</b>: ${__("adds once per pricing line before unit rollup.")}</div>
                    <div><b>${__("Fixed / Per Sheet")}</b>: ${__("is allocated later across matching lines on the sheet.")}</div>
                </div>
            </div>
        </div>
    `;

    frm.fields_dict.expense_help_html.$wrapper.html(html);
}

function ensureScenarioLayoutStyles() {
    if (document.getElementById("pricing-scenario-layout-style")) {
        return;
    }

    const style = document.createElement("style");
    style.id = "pricing-scenario-layout-style";
    style.textContent = `
        .ps-scenario-flow-fullwidth .section-body > .form-column { width: 100%; max-width: 100%; flex: 0 0 100%; }
        .ps-scenario-flow-fullwidth .section-body > .form-column:empty { display: none; }
        .ps-scenario-flow-fullwidth .grid-field { width: 100%; }
        .ep-shell { display: grid; gap: 14px; }
        .ep-hero { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(260px, 0.8fr); gap: 14px; padding: 18px; border: 1px solid #dbe4ea; border-radius: 18px; background: linear-gradient(135deg, #fff8ef 0%, #eef7f3 100%); }
        .ep-eyebrow { font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: #64748b; margin-bottom: 8px; }
        .ep-hero h3 { margin: 0 0 8px; font-size: 26px; line-height: 1.05; color: #102a43; }
        .ep-hero p { margin: 0; color: #486581; max-width: 60ch; }
        .ep-transport-box { padding: 14px; border-radius: 16px; background: rgba(255,255,255,.72); border: 1px solid rgba(255,255,255,.85); box-shadow: 0 10px 30px rgba(16,42,67,.08); }
        .ep-transport-head { font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: #64748b; margin-bottom: 8px; }
        .ep-transport-state { margin-bottom: 10px; }
        .ep-transport-meta { font-size: 14px; font-weight: 600; color: #102a43; }
        .ep-chip { display: inline-flex; align-items: center; padding: 5px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }
        .ep-chip--on { background: #dcfce7; color: #166534; }
        .ep-chip--off { background: #e2e8f0; color: #475569; }
        .ep-card-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
        .ep-card { padding: 14px; border-radius: 14px; border: 1px solid #e2e8f0; background: #fff; }
        .ep-card span { display: block; margin-bottom: 8px; font-size: 11px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; color: #64748b; }
        .ep-card strong { font-size: 24px; line-height: 1; color: #0f172a; }
        .ep-card.is-green { background: #f0fdf4; border-color: #bbf7d0; }
        .ep-card.is-amber { background: #fffbeb; border-color: #fde68a; }
        .ep-card.is-blue { background: #eff6ff; border-color: #bfdbfe; }
        .ep-card.is-slate { background: #f8fafc; border-color: #e2e8f0; }
        .ep-section { padding: 16px; border-radius: 16px; background: #fff; border: 1px solid #e2e8f0; }
        .ep-section--muted { background: #f8fafc; }
        .ep-section-head { display: flex; justify-content: space-between; gap: 10px; align-items: center; margin-bottom: 12px; }
        .ep-section-head strong { color: #102a43; }
        .ep-section-head span { font-size: 12px; color: #64748b; }
        .ep-flow-list { display: grid; gap: 10px; }
        .ep-flow-row { display: grid; grid-template-columns: 64px minmax(0, 1fr); gap: 12px; padding: 12px; border-radius: 14px; background: #f8fafc; border: 1px solid #e2e8f0; }
        .ep-flow-seq { display: flex; align-items: center; justify-content: center; border-radius: 12px; background: #102a43; color: #fff; font-size: 13px; font-weight: 700; }
        .ep-flow-head { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 6px; }
        .ep-pill { display: inline-flex; padding: 3px 8px; border-radius: 999px; background: #e2e8f0; color: #334155; font-size: 11px; font-weight: 700; }
        .ep-flow-meta { color: #102a43; font-size: 13px; font-weight: 600; }
        .ep-flow-note { margin-top: 6px; color: #64748b; font-size: 12px; }
        .ep-guidance { display: grid; gap: 8px; color: #475569; font-size: 13px; }
        .ep-empty { padding: 18px; border-radius: 14px; border: 1px dashed #cbd5e1; color: #64748b; background: #fff; }
        @media (max-width: 900px) {
            .ep-hero { grid-template-columns: 1fr; }
            .ep-card-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }
    `;
    document.head.appendChild(style);
}

function applyFlowSectionFullWidth(frm) {
    const field = frm.fields_dict.expense_help_html;
    if (!field || !field.$wrapper) {
        return;
    }

    const $section = field.$wrapper.closest(".form-section");
    if ($section && $section.length) {
        $section.addClass("ps-scenario-flow-fullwidth");
    }
}

function addExpenseTemplateRows(frm, rows, successMessage) {
    if ((frm.doc.expenses || []).length) {
        frappe.confirm(
            __("This will append starter rows to the existing expenses. Continue?"),
            () => {
                rows.forEach((data, index) => {
                    const row = frm.add_child("expenses");
                    row.sequence = data.sequence || (index + 1) * 10;
                    row.label = data.label;
                    row.type = data.type;
                    row.value = data.value;
                    row.applies_to = "Base Price";
                    row.scope = data.scope || "Per Unit";
                    row.is_active = 1;
                    row.notes = data.notes || "";
                });
                frm.refresh_field("expenses");
                renderExpenseGuide(frm);
                frappe.show_alert({ message: successMessage, indicator: "green" });
            }
        );
        return;
    }

    rows.forEach((data, index) => {
        const row = frm.add_child("expenses");
        row.sequence = data.sequence || (index + 1) * 10;
        row.label = data.label;
        row.type = data.type;
        row.value = data.value;
        row.applies_to = "Base Price";
        row.scope = data.scope || "Per Unit";
        row.is_active = 1;
        row.notes = data.notes || "";
    });
    frm.refresh_field("expenses");
    renderExpenseGuide(frm);
    frappe.show_alert({ message: successMessage, indicator: "green" });
}

function addStarterButtons(frm) {
    frm.add_custom_button(__("Starter Import"), () => {
        addExpenseTemplateRows(
            frm,
            [
                { label: "Freight", type: "Percentage", value: 8, scope: "Per Unit" },
                { label: "Insurance", type: "Percentage", value: 1.5, scope: "Per Unit" },
                { label: "Handling", type: "Fixed", value: 12, scope: "Per Unit" },
            ],
            __("Import starter expenses added")
        );
    }, __("Templates"));

    frm.add_custom_button(__("Landed Import"), () => {
        addExpenseTemplateRows(
            frm,
            [
                { label: "Port Charges", type: "Fixed", value: 150, scope: "Per Line" },
                { label: "Inspection", type: "Fixed", value: 40, scope: "Per Line" },
                { label: "Documentation", type: "Fixed", value: 120, scope: "Per Sheet" },
            ],
            __("Landed-cost helper expenses added")
        );
    }, __("Templates"));
}

frappe.ui.form.on("Pricing Scenario", {
    refresh(frm) {
        ensureScenarioLayoutStyles();
        applyFlowSectionFullWidth(frm);
        addStarterButtons(frm);
        renderExpenseGuide(frm);
    },

    scenario_name: renderExpenseGuide,
    transport_is_active: renderExpenseGuide,
    transport_allocation_mode: renderExpenseGuide,
    transport_container_price: renderExpenseGuide,
});

frappe.ui.form.on("Pricing Scenario Expense", {
    sequence: renderExpenseGuide,
    label: renderExpenseGuide,
    type: renderExpenseGuide,
    value: renderExpenseGuide,
    applies_to: renderExpenseGuide,
    scope: renderExpenseGuide,
    is_active: renderExpenseGuide,
    notes: renderExpenseGuide,
    expenses_remove: renderExpenseGuide,
});
