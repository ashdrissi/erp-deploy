function renderExpenseGuide(frm) {
    const rows = (frm.doc.expenses || [])
        .filter((row) => row.is_active)
        .sort((a, b) => (a.sequence || 0) - (b.sequence || 0));
    const pills = rows
        .map(
            (row) =>
                `<span style="display:inline-block;padding:6px 10px;border:1px solid #d9dee8;border-radius:999px;margin:4px 6px 0 0;background:#f8fafc;">${frappe.utils.escape_html(
                    row.label || "Expense"
                )} (#${row.sequence || "-"}): ${frappe.format(row.value || 0, { fieldtype: row.type === "Percentage" ? "Percent" : "Currency" })} on ${
                    row.applies_to || "Base Price"
                } (${row.scope || "Per Unit"})
                }</span>`
        )
        .join("");

    const html = `
        <div style="border:1px solid #e2e8f0;border-radius:12px;padding:14px;background:#ffffff;">
            <div style="font-weight:600;font-size:14px;margin-bottom:8px;">Pricing Flow</div>
            <div style="font-size:12px;color:#475569;line-height:1.6;">
                Final Unit Price = Base Price + sequential expenses.<br>
                <b>Percentage</b>: basis * value / 100 &nbsp;|&nbsp; <b>Fixed</b>: add exact amount.
            </div>
            <div style="font-size:12px;color:#334155;line-height:1.6;margin-top:8px;">
                <b>Transport Allocation</b>: ${frm.doc.transport_is_active ? "Enabled" : "Disabled"}<br>
                ${frappe.utils.escape_html(frm.doc.transport_allocation_mode || "By Value")} | Container Price: ${frappe.format(
                    frm.doc.transport_container_price || 0,
                    { fieldtype: "Currency" }
                )}
            </div>
            <div style="margin-top:10px;">${pills || "<span style='font-size:12px;color:#64748b;'>No active expense yet.</span>"}</div>
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
        .ps-scenario-flow-fullwidth .section-body > .form-column {
            width: 100%;
            max-width: 100%;
            flex: 0 0 100%;
        }

        .ps-scenario-flow-fullwidth .section-body > .form-column:empty {
            display: none;
        }

        .ps-scenario-flow-fullwidth .grid-field {
            width: 100%;
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

frappe.ui.form.on("Pricing Scenario", {
    refresh(frm) {
        ensureScenarioLayoutStyles();
        applyFlowSectionFullWidth(frm);

        frm.add_custom_button(__("Add Starter Expenses"), () => {
            if ((frm.doc.expenses || []).length) {
                frappe.show_alert({ message: __("Expenses already exist"), indicator: "orange" });
                return;
            }

            [
                ["Freight", "Percentage", 8, "Base Price"],
                ["Insurance", "Percentage", 1.5, "Base Price"],
                ["Handling", "Fixed", 12, "Base Price"],
                ["Commercial Margin", "Percentage", 15, "Base Price"],
            ].forEach(([label, type, value, applies_to], index) => {
                const row = frm.add_child("expenses");
                row.sequence = (index + 1) * 10;
                row.label = label;
                row.type = type;
                row.value = value;
                row.applies_to = applies_to;
                row.scope = "Per Unit";
                row.is_active = 1;
            });

            frm.refresh_field("expenses");
            renderExpenseGuide(frm);
            applyFlowSectionFullWidth(frm);
            frappe.show_alert({ message: __("Starter expenses added"), indicator: "green" });
        });

        renderExpenseGuide(frm);
        applyFlowSectionFullWidth(frm);
    },

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
    expenses_remove: renderExpenseGuide,
});
