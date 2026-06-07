frappe.ui.form.on("Item", {
    setup(frm) {
        scheduleSpecificationLayout(frm);
    },
    onload(frm) {
        scheduleSpecificationLayout(frm);
    },
    refresh(frm) {
        scheduleSpecificationLayout(frm);
    },
});

function scheduleSpecificationLayout(frm) {
    [0, 100, 400, 1000].forEach((delay) => {
        setTimeout(() => moveSpecificationFields(frm), delay);
    });
}

function moveSpecificationFields(frm) {
    const section = findSpecificationSection(frm);
    const material = frm.fields_dict.custom_material;

    if (!section || !material || !material.$wrapper) {
        return;
    }

    const $section = $(section.wrapper || section.$wrapper);
    const $body = getSectionBody(section, $section);
    const $material = material.$wrapper.closest(".frappe-control");

    if (!$section.length || !$body.length || !$material.length) {
        return;
    }

    setSectionTitle($section, "Spécifications");
    $section.attr("data-orderlift-spec-section", "1");
    $body.attr("data-orderlift-spec-body", "1");
    $section.insertAfter($material);

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
        if (!field || !field.$wrapper) {
            return;
        }
        const $control = field.$wrapper.closest(".frappe-control");
        if (!$control.length || $control.closest("[data-orderlift-spec-body]").length) {
            return;
        }
        $body.append($control);
    });

    collapseSpecificationSection(section, $section);
}

function findSpecificationSection(frm) {
    const sections = (frm.layout && frm.layout.sections) || [];
    return sections.find((entry) => entry.df && entry.df.fieldname === "section_break_gjns")
        || sections.find((entry) => entry.df && entry.df.label === "Spécifications");
}

function getSectionBody(section, $section) {
    if (section.body) {
        return $(section.body);
    }
    return $section.find(".section-body, .form-section, .section-body-wrapper").first();
}

function setSectionTitle($section, label) {
    const $title = $section.find(".section-head, .section-title, .h6, .form-section-heading").first();
    if ($title.length) {
        $title.text(__(label));
    }
}

function collapseSpecificationSection(section, $section) {
    if ($section.attr("data-orderlift-spec-collapsed") === "1") {
        return;
    }

    if (typeof section.collapse === "function") {
        section.collapse();
    } else {
        $section.find(".section-body, .form-section, .section-body-wrapper").first().hide();
        $section.addClass("collapsed hide-control");
    }

    $section.attr("data-orderlift-spec-collapsed", "1");
}
