function renderExpenseGuide(frm) {
    const rows = (frm.doc.expenses || []).filter((row) => row.is_active);
    const pills = rows
        .map(
            (row) =>
                `<span style="display:inline-block;padding:6px 10px;border:1px solid #d9dee8;border-radius:999px;margin:4px 6px 0 0;background:#f8fafc;">${frappe.utils.escape_html(
                    row.label || "Expense"
                )}: ${frappe.format(row.value || 0, { fieldtype: row.type === "Percentage" ? "Percent" : "Currency" })} on ${
                    row.applies_to || "Running Total"
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
            <div style="margin-top:10px;">${pills || "<span style='font-size:12px;color:#64748b;'>No active expense yet.</span>"}</div>
        </div>
    `;

    frm.fields_dict.expense_help_html.$wrapper.html(html);
}

frappe.ui.form.on("Pricing Scenario", {
    refresh(frm) {
        frm.add_custom_button(__("Add Starter Expenses"), () => {
            if ((frm.doc.expenses || []).length) {
                frappe.show_alert({ message: __("Expenses already exist"), indicator: "orange" });
                return;
            }

            [
                ["Freight", "Percentage", 8, "Base Price"],
                ["Insurance", "Percentage", 1.5, "Running Total"],
                ["Handling", "Fixed", 12, "Running Total"],
                ["Commercial Margin", "Percentage", 15, "Running Total"],
            ].forEach(([label, type, value, applies_to]) => {
                const row = frm.add_child("expenses");
                row.label = label;
                row.type = type;
                row.value = value;
                row.applies_to = applies_to;
                row.is_active = 1;
            });

            frm.refresh_field("expenses");
            renderExpenseGuide(frm);
            frappe.show_alert({ message: __("Starter expenses added"), indicator: "green" });
        });

        renderExpenseGuide(frm);
    },
});

frappe.ui.form.on("Pricing Scenario Expense", {
    label: renderExpenseGuide,
    type: renderExpenseGuide,
    value: renderExpenseGuide,
    applies_to: renderExpenseGuide,
    is_active: renderExpenseGuide,
    expenses_remove: renderExpenseGuide,
});
