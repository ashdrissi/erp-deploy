frappe.ui.form.on("Pricing Customs Policy", {
    refresh(frm) {
        const sections = (frm.layout && frm.layout.sections) || [];
        const helpSection = sections.find(
            (section) => section.df && section.df.fieldname === "customs_rules_help_section"
        );

        if (helpSection && typeof helpSection.collapse === "function") {
            helpSection.collapse();
        }
    },
});
