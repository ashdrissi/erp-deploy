frappe.ui.form.on("Pricing Builder", {
    refresh(frm) {
        ensureBuilderStyles();
        setupQueries(frm);
        setupGridDisplay(frm);
        renderBuilderHeader(frm);
        renderSummaryPanel(frm);
        renderWarningsPanel(frm);

        frm.clear_custom_buttons();
        frm.add_custom_button(__("Load Items & Calculate"), () => calculateBuilder(frm), __("Builder"));
        frm.add_custom_button(__("Publish Selected"), () => publishBuilder(frm, true), __("Builder"));
        frm.add_custom_button(__("Publish All"), () => publishBuilder(frm, false), __("Builder"));

        frm.page.set_indicator(indicatorLabel(frm), indicatorColor(frm));
        frm.set_intro(
            __("Use sourcing rules to map buying lists to expenses, customs, and margin & benchmark policies, then calculate and publish a static selling list without runtime tier modifiers."),
            "blue"
        );
    },
    builder_name(frm) {
        renderBuilderHeader(frm);
    },
    selling_price_list_name(frm) {
        renderBuilderHeader(frm);
        scheduleAutoRecalculate(frm);
    },
    item_group(frm) {
        scheduleAutoRecalculate(frm);
    },
    default_qty(frm) {
        renderBuilderHeader(frm);
        scheduleAutoRecalculate(frm);
    },
    max_items(frm) {
        renderBuilderHeader(frm);
        scheduleAutoRecalculate(frm);
    },
});

function setupQueries(frm) {
    frm.set_query("buying_price_list", "sourcing_rules", () => ({ filters: { buying: 1 } }));
    frm.set_query("pricing_scenario", "sourcing_rules", () => ({ filters: {} }));
    frm.set_query("customs_policy", "sourcing_rules", () => ({ filters: { is_active: 1 } }));
    frm.set_query("benchmark_policy", "sourcing_rules", () => ({ filters: { is_active: 1 } }));
}

function setupGridDisplay(frm) {
    const rulesGrid = frm.get_field("sourcing_rules").grid;
    const itemsGrid = frm.get_field("builder_items").grid;

    if (rulesGrid) {
        rulesGrid.set_multiple_add("buying_price_list", "pricing_scenario");
        rulesGrid.wrapper.addClass("pb-native-grid");
    }

    if (itemsGrid) {
        itemsGrid.wrapper.addClass("pb-native-grid pb-results-grid");
    }
}

function renderBuilderHeader(frm) {
    const name = frappe.utils.escape_html(frm.doc.builder_name || frm.doc.name || __("New Pricing Builder"));
    const priceList = frappe.utils.escape_html(frm.doc.selling_price_list_name || __("Not set yet"));
    const qty = frappe.format(frm.doc.default_qty || 1, { fieldtype: "Float" });
    const maxItems = cint(frm.doc.max_items || 0) > 0 ? frappe.utils.escape_html(String(frm.doc.max_items)) : __("All");

    frm.get_field("builder_header_html").$wrapper.html(`
        <div class="pb-hero">
            <div class="pb-hero-copy">
                <div class="pb-eyebrow">${__("Static Selling List Builder")}</div>
                <h2>${name}</h2>
                <p>${__("Build a clean base sell list from buying prices, expenses policies, customs, and margin benchmarks before runtime tier adjustments.")}</p>
                <div class="pb-hero-stats">
                    <div class="pb-stat-card">
                    <span>${__("Selling List")}</span>
                    <strong>${priceList}</strong>
                    </div>
                    <div class="pb-stat-card">
                    <span>${__("Qty / Item")}</span>
                    <strong>${qty}</strong>
                    </div>
                    <div class="pb-stat-card">
                    <span>${__("Max Items")}</span>
                    <strong>${maxItems}</strong>
                    </div>
                </div>
            </div>
        </div>
    `);
}

function renderSummaryPanel(frm) {
    const cards = [
        { label: __("Total Items"), value: cint(frm.doc.total_items || 0), tone: "slate" },
        { label: __("Ready"), value: cint(frm.doc.ready_items || 0), tone: "green" },
        { label: __("Changed"), value: cint(frm.doc.changed_items || 0), tone: "amber" },
        { label: __("New"), value: cint(frm.doc.new_items || 0), tone: "blue" },
        { label: __("Missing"), value: cint(frm.doc.missing_items || 0), tone: "red" },
    ];

    frm.get_field("summary_panel_html").$wrapper.html(`
        <div class="pb-summary-grid">
            ${cards
                .map(
                    (card) => `
                <div class="pb-summary-card is-${card.tone}">
                    <span>${card.label}</span>
                    <strong>${card.value}</strong>
                </div>`
                )
                .join("")}
        </div>
    `);
}

function renderWarningsPanel(frm) {
    const warnings = (frm.doc.warnings_html || "")
        .split("\n")
        .map((row) => row.trim())
        .filter(Boolean);

    if (!warnings.length) {
        frm.get_field("warnings_panel_html").$wrapper.html(`
            <div class="pb-warning-box is-empty">${__("No warnings. The builder is ready to calculate or publish.")}</div>
        `);
        return;
    }

    frm.get_field("warnings_panel_html").$wrapper.html(`
        <div class="pb-warning-box">
            <div class="pb-warning-title">${__("Review Before Publish")}</div>
            <ul>${warnings.map((warning) => `<li>${frappe.utils.escape_html(warning)}</li>`).join("")}</ul>
        </div>
    `);
}

function indicatorLabel(frm) {
    if (cint(frm.doc.missing_items || 0) > 0) return __("Needs Review");
    if (cint(frm.doc.changed_items || 0) > 0 || cint(frm.doc.new_items || 0) > 0) return __("Ready to Publish");
    if (cint(frm.doc.total_items || 0) > 0) return __("Calculated");
    return __("Draft");
}

function indicatorColor(frm) {
    if (cint(frm.doc.missing_items || 0) > 0) return "orange";
    if (cint(frm.doc.changed_items || 0) > 0 || cint(frm.doc.new_items || 0) > 0) return "green";
    if (cint(frm.doc.total_items || 0) > 0) return "blue";
    return "gray";
}

async function calculateBuilder(frm) {
    if (frm.__pricing_builder_running) return;
    frm.__pricing_builder_running = true;
    await frm.save();
    try {
        await frappe.call({
            method: "orderlift.orderlift_sales.doctype.pricing_builder.pricing_builder.calculate_builder_doc",
            args: { name: frm.doc.name },
            freeze: true,
            freeze_message: __("Calculating builder prices..."),
        });
        await frm.reload_doc();
    } finally {
        frm.__pricing_builder_running = false;
    }
}

async function publishBuilder(frm, selectedOnly) {
    if (!frm.doc.selling_price_list_name) {
        frappe.throw(__("Enter the Selling Price List Name before publishing."));
    }
    await frm.save();
    const response = await frappe.call({
        method: "orderlift.orderlift_sales.doctype.pricing_builder.pricing_builder.publish_builder_doc",
        args: { name: frm.doc.name, selected_only: selectedOnly ? 1 : 0 },
        freeze: true,
        freeze_message: __("Publishing prices..."),
    });
    const out = response.message || {};
    frappe.show_alert(
        {
            message: [
                __("Price List: {0}", [out.price_list || frm.doc.selling_price_list_name]),
                __("Created: {0}", [out.created || 0]),
                __("Updated: {0}", [out.updated || 0]),
                __("Skipped: {0}", [out.skipped || 0]),
            ].join(" | "),
            indicator: (out.errors || []).length ? "orange" : "green",
        },
        8
    );
    await frm.reload_doc();
}

function scheduleAutoRecalculate(frm) {
    if (frm.is_new() || frm.__pricing_builder_running) return;
    clearTimeout(frm.__pricing_builder_auto_timer);
    frm.__pricing_builder_auto_timer = setTimeout(() => {
        if (frm.__pricing_builder_running) return;
        calculateBuilder(frm);
    }, 450);
}

frappe.ui.form.on("Pricing Builder Item", {
    override_selling_price(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        const effectivePrice = flt(row.override_selling_price || 0) || flt(row.projected_price || 0);
        const buyPrice = flt(row.base_buy_price || 0);
        const marginPct = buyPrice > 0 ? ((effectivePrice - buyPrice) / buyPrice) * 100 : 0;
        frappe.model.set_value(cdt, cdn, "final_margin_pct", marginPct);
    },
});

frappe.ui.form.on("Pricing Builder Sourcing Rule", {
    buying_price_list(frm) {
        scheduleAutoRecalculate(frm);
    },
    pricing_scenario(frm) {
        scheduleAutoRecalculate(frm);
    },
    customs_policy(frm) {
        scheduleAutoRecalculate(frm);
    },
    benchmark_policy(frm) {
        scheduleAutoRecalculate(frm);
    },
    is_active(frm) {
        scheduleAutoRecalculate(frm);
    },
    sourcing_rules_add(frm) {
        scheduleAutoRecalculate(frm);
    },
    sourcing_rules_remove(frm) {
        scheduleAutoRecalculate(frm);
    },
});

function ensureBuilderStyles() {
    if (document.getElementById("pricing-builder-form-styles")) return;
    $("<style id='pricing-builder-form-styles'>\
        .pb-hero{display:block;padding:18px 20px;border-radius:16px;background:linear-gradient(135deg,#f7f4ec 0%,#e8f1ef 100%);border:1px solid #d7e4df;margin-bottom:8px;}\
        .pb-eyebrow{font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#6b7280;margin-bottom:8px;}\
        .pb-hero h2{margin:0 0 8px;font-size:26px;line-height:1.1;color:#14213d;}\
        .pb-hero p{margin:0;color:#475569;max-width:52ch;}\
        .pb-hero-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:14px;}\
        .pb-stat-card{padding:12px 14px;border-radius:14px;background:rgba(255,255,255,.7);backdrop-filter:blur(6px);border:1px solid rgba(255,255,255,.65);box-shadow:0 8px 24px rgba(20,33,61,.06);}\
        .pb-stat-card span{display:block;font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:#64748b;margin-bottom:6px;}\
        .pb-stat-card strong{display:block;font-size:15px;color:#0f172a;word-break:break-word;}\
        .pb-summary-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin:8px 0 2px;}\
        .pb-summary-card{padding:14px;border-radius:14px;border:1px solid #e5e7eb;background:#fff;}\
        .pb-summary-card span{display:block;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:#64748b;margin-bottom:8px;}\
        .pb-summary-card strong{font-size:24px;line-height:1;color:#0f172a;}\
        .pb-summary-card.is-green{background:#f0fdf4;border-color:#bbf7d0;}\
        .pb-summary-card.is-amber{background:#fffbeb;border-color:#fde68a;}\
        .pb-summary-card.is-blue{background:#eff6ff;border-color:#bfdbfe;}\
        .pb-summary-card.is-red{background:#fef2f2;border-color:#fecaca;}\
        .pb-summary-card.is-slate{background:#f8fafc;border-color:#e2e8f0;}\
        .pb-warning-box{padding:14px 16px;border-radius:14px;background:#fff7ed;border:1px solid #fdba74;color:#9a3412;margin:8px 0 2px;}\
        .pb-warning-box.is-empty{background:#f8fafc;border-color:#e2e8f0;color:#475569;}\
        .pb-warning-title{font-weight:700;margin-bottom:8px;}\
        .pb-warning-box ul{margin:0;padding-left:18px;}\
        .pb-warning-box li+li{margin-top:6px;}\
        .pb-native-grid .grid-heading-row{background:#f8fafc;border-bottom:1px solid #e2e8f0;}\
        .pb-native-grid .grid-heading-row .grid-row{font-weight:700;color:#475569;}\
        .pb-native-grid .grid-body .rows{border-radius:12px;overflow:hidden;}\
        .pb-results-grid .grid-body .data-row:nth-child(odd){background:#fcfcfd;}\
        .pb-results-grid .grid-body .data-row:hover{background:#f8fafc;}\
        .pb-results-grid .grid-static-col{font-weight:600;}\
        @media (max-width:900px){.pb-summary-grid{grid-template-columns:repeat(2,minmax(0,1fr));}.pb-hero-stats{grid-template-columns:1fr;}.pb-hero h2{font-size:22px;}}\
    </style>").appendTo(document.head);
}
