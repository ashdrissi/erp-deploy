frappe.ui.form.on("Pricing Scenario Policy", {
    refresh(frm) {
        frm.set_intro(
            __(
                "Rules map an incoming source buying list to a pricing scenario, with optional customs and pricing policy overrides. Leave fields blank to create broader fallback rules, and keep one lowest-specificity active rule as the default catch-all."
            ),
            "blue"
        );
    },
});
