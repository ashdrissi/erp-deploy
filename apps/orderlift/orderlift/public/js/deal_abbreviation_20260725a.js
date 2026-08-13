(function () {
    const FIELDNAME = "custom_deal_abbreviation";
    const EDITABLE_DOCTYPES = new Set(["Opportunity", "Sales Order", "Project"]);
    const TARGET_DOCTYPES = [
        "Opportunity",
        "Quotation",
        "Sales Order",
        "Project",
        "Material Request",
        "Request for Quotation",
        "Supplier Quotation",
        "Purchase Order",
        "Purchase Receipt",
        "Purchase Invoice",
        "Delivery Note",
        "Sales Invoice",
        "Stock Entry",
        "Forecast Load Plan",
        "Delivery Trip",
        "Pick List",
        "Quality Inspection",
        "Work Order",
        "SAV Ticket",
    ];

    TARGET_DOCTYPES.forEach((doctype) => {
        frappe.ui.form.on(doctype, {
            refresh(frm) {
                renderDealFlag(frm);
            },
            custom_deal_abbreviation(frm) {
                renderDealFlag(frm);
            },
        });
    });

    function renderDealFlag(frm) {
        removeDealFlag(frm);
        if (!frm || !frm.fields_dict || !frm.fields_dict[FIELDNAME]) return;
        injectDealFlagStyles();

        const rawValue = String(frm.doc[FIELDNAME] || "").trim().toUpperCase();
        if (!rawValue && !EDITABLE_DOCTYPES.has(frm.doctype)) return;
        const value = rawValue || __("Not set");
        const tone = rawValue === "MIXED" ? "mixed" : rawValue ? "set" : "empty";
        const title = frappe.utils.escape_html(__("Deal Abbreviation") + `: ${value}`);
        const flag = $(
            `<div class="ol-deal-flag ol-deal-flag-${tone}" role="status" title="${title}">`
            + `<span class="ol-deal-flag-icon">${dealIcon()}</span>`
            + `<strong>${frappe.utils.escape_html(`Deal / ${value}`)}</strong>`
            + "</div>"
        );

        const wrapper = frm.$wrapper || (frm.wrapper ? $(frm.wrapper) : $());
        const tabs = wrapper.find(".form-tabs-list").first();
        if (tabs.length) {
            tabs.before(flag);
        } else if (wrapper.length) {
            wrapper.find(".form-page, .form-layout").first().prepend(flag);
        } else {
            frm.page.inner_toolbar.prepend(flag);
        }
    }

    function removeDealFlag(frm) {
        if (frm && frm.page && frm.page.inner_toolbar) frm.page.inner_toolbar.find(".ol-deal-flag").remove();
        if (frm && frm.$wrapper) frm.$wrapper.find(".ol-deal-flag").remove();
    }

    function dealIcon() {
        return frappe.utils && frappe.utils.icon ? frappe.utils.icon("tag", "sm") : "";
    }

    function injectDealFlagStyles() {
        if (document.getElementById("ol-deal-flag-style")) return;
        const style = document.createElement("style");
        style.id = "ol-deal-flag-style";
        style.textContent = `
            .ol-deal-flag { display:inline-flex; align-items:center; gap:6px; width:max-content; max-width:100%; margin:0 0 6px; padding:5px 10px; border:1px solid #c4b5fd; border-radius:999px; color:#6d28d9; background:linear-gradient(135deg,#f5f3ff,#faf5ff); font-size:11px; line-height:1.2; letter-spacing:.02em; }
            .ol-deal-flag strong { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
            .ol-deal-flag-icon { display:inline-flex; align-items:center; }
            .ol-deal-flag-mixed { color:#c2410c; border-color:#fdba74; background:linear-gradient(135deg,#fff7ed,#fffbeb); }
            .ol-deal-flag-empty { color:#64748b; border-color:#cbd5e1; background:#f8fafc; }
            @media (max-width:767px) { .ol-deal-flag { width:100%; justify-content:center; } }
        `;
        document.head.appendChild(style);
    }
})();
