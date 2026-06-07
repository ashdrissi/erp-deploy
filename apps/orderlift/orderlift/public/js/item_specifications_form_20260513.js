frappe.ui.form.on("Item", {
    refresh(frm) {
        setTimeout(() => moveSpecificationFields(frm), 0);
    },
});

function moveSpecificationFields(frm) {
    const section = ((frm.layout && frm.layout.sections) || []).find(
        (entry) => entry.df && entry.df.fieldname === "section_break_gjns"
    );
    const material = frm.fields_dict.custom_material;

    if (!section || !section.wrapper || !material || !material.$wrapper) {
        return;
    }

    const $section = $(section.wrapper);
    const $sectionBody = section.body ? $(section.body) : $section.find(".section-body").first();
    if (!$sectionBody.length) {
        return;
    }

    $section.insertAfter(material.$wrapper.closest(".frappe-control"));
    $sectionBody.attr("data-orderlift-spec-section", "1");

    [
        "custom_weight_kg",
        "custom_volume_m3",
        "custom_length_cm",
        "custom_width_cm",
        "custom_height_cm",
        "custom_inventory_flag",
        "custom_specifications",
    ].forEach((fieldname) => {
        const field = frm.fields_dict[fieldname];
        if (!field || !field.$wrapper || field.$wrapper.closest("[data-orderlift-spec-section]").length) {
            return;
        }
        $sectionBody.append(field.$wrapper);
    });
}
