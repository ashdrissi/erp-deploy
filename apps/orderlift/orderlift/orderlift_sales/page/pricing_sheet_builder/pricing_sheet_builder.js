(function () {
    const STATE = {
        sheet: blankSheet(),
        active: "setup",
        loading: false,
        saving: false,
        error: "",
        loadedRouteKey: "",
        historyCollapsed: true,
        itemsCollapsed: false,
        dimensioning: null,
        dimensioningValues: {},
        dimensioningPreview: [],
        dimensioningPreviewCollapsed: true,
        selectedLineKeys: new Set(),
        customerPricingContext: null,
        applyingCustomerPricingContext: false,
        marginBasis: "Loaded Cost",
    };

    const NAV = [
        { key: "setup", label: "Setup", step: "01" },
        { key: "items", label: "Items", step: "02" },
        { key: "breakdown", label: "Price Breakdown", step: "03" },
        { key: "quotation", label: "Quotation", step: "04" },
    ];

    const COLUMN_STORAGE_KEY_PREFIX = "orderlift.pricingSheetBuilder.columns.v4";
    const DEFAULT_LINE_COLUMNS = ["__select", "item", "item_name", "qty", "buy_price", "expense_unit_price", "customs_unit_amount", "projected_unit_price", "projected_total_price", "margin_unit_amount", "margin_source", "margin_basis", "final_sell_unit_price", "manual_sell_unit_price", "final_sell_total", "discount_percent", "discounted_sell_total", "custom_applied_taxes", "custom_pu_ttc", "custom_pt_ttc", "actions"];
    const AGENT_LINE_COLUMNS = ["__select", "item", "item_name", "qty", "resolved_selling_price_list", "final_sell_unit_price", "manual_sell_unit_price", "final_sell_total", "max_discount_percent_allowed", "discount_percent", "discounted_sell_total", "custom_applied_taxes", "custom_pu_ttc", "custom_pt_ttc", "commission_rate", "commission_amount", "actions"];
    const ADMIN_STATIC_LINE_COLUMNS = ["__select", "item", "item_name", "qty", "resolved_selling_price_list", "static_list_price", "final_sell_unit_price", "manual_sell_unit_price", "final_sell_total", "max_discount_percent_allowed", "discount_percent", "discounted_sell_total", "custom_applied_taxes", "custom_pu_ttc", "custom_pt_ttc", "commission_rate", "commission_amount", "builder_margin_percent", "target_margin_percent", "margin_source", "margin_basis", "resolved_margin_rule", "builder_price_overridden", "pricing_builder", "builder_source_buying_price_list", "resolved_benchmark_rule", "actions"];
    const HIGHLIGHT_COLUMNS = new Set(["projected_unit_price", "projected_total_price", "final_sell_unit_price", "final_sell_total", "discounted_sell_total", "custom_applied_taxes", "custom_pu_ttc", "custom_pt_ttc"]);
    const STATIC_MODE_HIDDEN_COLUMNS = new Set(["customs_unit_amount", "margin_unit_amount"]);
    const SENSITIVE_PRICING_COLUMNS = new Set(["margin_unit_amount", "margin_total_amount", "margin_pct", "margin_basis", "margin_source", "total_margin_unit_amount", "total_margin_total_amount", "total_margin_pct", "resolved_margin_rule", "target_margin_percent", "builder_margin_percent", "buy_price", "source_buying_price_list", "pricing_scenario", "resolved_pricing_scenario", "resolved_scenario_rule", "resolved_benchmark_rule", "scenario_source", "expense_unit_price", "expense_total", "customs_unit_amount", "customs_total_percent", "projected_unit_price", "projected_total_price"]);
    const LINE_COLUMNS = [
        { key: "__select", label: "", mandatory: true },
        { key: "item", label: "Item ref", mandatory: true },
        { key: "item_name", label: "Item Name" },
        { key: "source_buying_price_list", label: "Source Buying Price List", type: "Link", options: "Price List", sensitive: true },
        { key: "pricing_scenario", label: "Line Expenses Policy", type: "Link", options: "Pricing Scenario" },
        { key: "resolved_pricing_scenario", label: "Resolved Expenses Policy" },
        { key: "resolved_scenario_rule", label: "Resolved Policy Rule" },
        { key: "resolved_margin_rule", label: "Resolved Margin Rule" },
        { key: "scenario_source", label: "Expenses Policy Source" },
        { key: "has_scenario_override", label: "Has Scenario Override", type: "Check" },
        { key: "has_line_override", label: "Has Line Override", type: "Check" },
        { key: "source_bundle", label: "Source Bundle" },
        { key: "dimensioning_set", label: "Dimensioning Set" },
        { key: "dimensioning_rule_label", label: "Dimensioning Rule" },
        { key: "line_type", label: "Line Type" },
        { key: "bundle_group_id", label: "Bundle Group ID" },
        { key: "qty", label: "Qty", type: "Float", editable: true },
        { key: "buy_price", label: "Base PU", type: "Currency", editable: true, sensitive: true },
        { key: "buy_price_missing", label: "Base Price Missing", type: "Check" },
        { key: "buy_price_message", label: "Base Price Message" },
        { key: "display_group", label: "Display Group", editable: true },
        { key: "base_amount", label: "Base PT HT", type: "Currency" },
        { key: "expense_unit_price", label: "Expenses U", type: "Currency", sensitive: true },
        { key: "expense_total", label: "Charges PT HT", type: "Currency" },
        { key: "customs_unit_amount", label: "Customs U", type: "Currency", sensitive: true },
        { key: "margin_unit_amount", label: "Margin Unit", type: "Currency" },
        { key: "margin_total_amount", label: "Margin Total", type: "Currency" },
        { key: "total_margin_unit_amount", label: "Total Margin Unit", type: "Currency" },
        { key: "total_margin_total_amount", label: "Total Margin Total", type: "Currency" },
        { key: "projected_unit_price", label: "Total Cost U", type: "Currency", sensitive: true },
        { key: "projected_total_price", label: "Total Cost", type: "Currency", sensitive: true },
        { key: "manual_sell_unit_price", label: "Manual Unit Override", type: "Currency", editable: true },
        { key: "is_manual_override", label: "Is Manual Override", type: "Check" },
        { key: "final_sell_unit_price", label: "Sell Price U", type: "Currency" },
        { key: "final_sell_total", label: "Total Sell Price", type: "Currency" },
        { key: "max_discount_percent_allowed", label: "Max Discount %", type: "Percent" },
        { key: "discount_percent", label: "Discount %", type: "Percent", editable: true },
        { key: "discount_amount", label: "Discount Amount", type: "Currency" },
        { key: "discounted_sell_unit_price", label: "Discounted Sell Unit", type: "Currency" },
        { key: "discounted_sell_total", label: "Total After Discount", type: "Currency" },
        { key: "custom_applied_taxes", label: "Applied Taxes", type: "Currency" },
        { key: "custom_pu_ttc", label: "PU TTC", type: "Currency" },
        { key: "custom_pt_ttc", label: "PT TTC", type: "Currency" },
        { key: "commission_rate", label: "Commission %", type: "Percent" },
        { key: "commission_amount", label: "Commission Amount", type: "Currency" },
        { key: "margin_pct", label: "Margin Pct", type: "Percent" },
        { key: "total_margin_pct", label: "Total Margin Pct", type: "Percent" },
        { key: "margin_basis", label: "Margin Basis" },
        { key: "target_margin_percent", label: "Target Margin %", type: "Percent" },
        { key: "builder_margin_percent", label: "Builder Margin %", type: "Percent" },
        { key: "builder_price_overridden", label: "Builder Price Overridden", type: "Check" },
        { key: "pricing_builder", label: "Pricing Builder", type: "Link", options: "Pricing Builder" },
        { key: "builder_source_buying_price_list", label: "Builder Source Buying List", type: "Link", options: "Price List" },
        { key: "customs_material", label: "Material" },
        { key: "customs_tariff_number", label: "Tariff Number" },
        { key: "customs_weight_kg", label: "Customs Weight Kg", type: "Float" },
        { key: "customs_value_per_kg", label: "Customs Value Per Kg", type: "Currency" },
        { key: "customs_base_value", label: "Customs Value", type: "Currency" },
        { key: "customs_total_percent", label: "Customs Total Percent", type: "Percent" },
        { key: "customs_rate_per_kg", label: "Customs Rate Per Kg", type: "Currency" },
        { key: "customs_rate_percent", label: "Customs Rate Percent", type: "Percent" },
        { key: "customs_by_kg", label: "Customs By Kg", type: "Currency" },
        { key: "customs_by_percent", label: "Customs By Percent", type: "Currency" },
        { key: "customs_applied", label: "Customs Total", type: "Currency" },
        { key: "packaging_profile_source", label: "Packaging Source" },
        { key: "customs_basis", label: "Customs Basis" },
        { key: "transport_allocation_mode", label: "Transport Allocation Mode" },
        { key: "transport_container_type", label: "Transport Container Type" },
        { key: "transport_basis_total", label: "Transport Basis Total", type: "Float" },
        { key: "transport_numerator", label: "Transport Numerator", type: "Float" },
        { key: "transport_allocated", label: "Transport Allocated", type: "Currency" },
        { key: "price_floor_violation", label: "Price Floor Violation", type: "Check" },
        { key: "benchmark_price", label: "Benchmark Price", type: "Currency" },
        { key: "benchmark_delta_abs", label: "Benchmark Delta Abs", type: "Currency" },
        { key: "benchmark_delta_pct", label: "Benchmark Delta Pct", type: "Percent" },
        { key: "benchmark_status", label: "Benchmark Status" },
        { key: "benchmark_note", label: "Benchmark Note" },
        { key: "benchmark_reference", label: "Benchmark Reference", type: "Currency" },
        { key: "benchmark_source_count", label: "Benchmark Sources", type: "Int" },
        { key: "benchmark_ratio", label: "Benchmark Ratio", type: "Float" },
        { key: "benchmark_method", label: "Benchmark Method" },
        { key: "resolved_benchmark_rule", label: "Benchmark Rule" },
        { key: "margin_source", label: "Margin Source" },
        { key: "tier_modifier_amount", label: "Tier Modifier Unit", type: "Currency" },
        { key: "tier_modifier_total", label: "Tier Modifier Total", type: "Currency" },
        { key: "zone_modifier_amount", label: "Territory Modifier Unit", type: "Currency" },
        { key: "zone_modifier_total", label: "Territory Modifier Total", type: "Currency" },
        { key: "breakdown_preview", label: "Breakdown Preview" },
        { key: "static_list_price", label: "List Price", type: "Currency" },
        { key: "resolved_selling_price_list", label: "Resolved Selling List" },
        { key: "actions", label: "", mandatory: true },
    ];

    STATE.lineColumns = loadLineColumns();
    let dimensioningPreviewTimer = null;
    let autoPriceTimer = null;

    frappe.pages["pricing-sheet-builder"].on_page_load = function (wrapper) {
        const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Pricing Sheet Builder"), single_column: true });
        wrapper.page = page;
        page.main.addClass("psb-root");
        injectStyles();
        applyHeader(page);
        render(page);
        loadInitial(page);
    };

    frappe.pages["pricing-sheet-builder"].on_page_show = function (wrapper) {
        if (!wrapper.page) return;
        applyHeader(wrapper.page);
        loadInitial(wrapper.page);
    };

    function blankSheet() {
        return {
            name: "",
            is_new: 1,
            sheet_name: "",
            custom_company: "",
            party_type: "Customer",
            party_name: "",
            customer: "",
            opportunity: "",
            sales_person: "",
            crm_business_type: "",
            crm_segment: "",
            geography_territory: "",
            pricing_scenario: "",
            benchmark_policy: "",
            customs_policy: "",
            taxes_and_charges_template: "",
            selected_price_list: "",
            selected_selling_price_lists: [],
            pricing_mode: "Dynamic",
            output_mode: "Avec details",
            dimensioning_set: "",
            dimensioning_inputs_json: "",
            resolved_mode: "Draft",
            total_buy: 0,
            total_expenses: 0,
            total_selling: 0,
            customs_total_applied: 0,
            projection_warnings: "",
            quotation_preview: {},
            user_context: {},
            history: [],
            scenario_mappings: [],
            lines: [],
            source_quotation: "",
            link_source_quotation: 0,
        };
    }

    function applyHeader(page) {
        page.set_title(__("Pricing Sheet Builder"));
        page.clear_actions_menu();
        page.set_primary_action(__("Save"), () => save(page));
        page.add_action_item(__("Save Now"), () => save(page));
        page.add_action_item(__("Delete Pricing Sheet"), () => confirmDeletePricingSheet(page));
        page.add_action_item(__("Back to Pricing Sheets"), () => frappe.set_route("pricing-sheet-manager"));
        setTimeout(() => {
            if (!frappe.breadcrumbs) return;
            frappe.breadcrumbs.clear();
            frappe.breadcrumbs.append_breadcrumb_element("/app/pricing-sheet-manager", __("Pricing Sheets"), "title-text");
            frappe.breadcrumbs.append_breadcrumb_element("", __("Builder"), "title-text");
            frappe.breadcrumbs.toggle(true);
        }, 0);
    }

    async function loadInitial(page) {
        const params = new URLSearchParams(window.location.search || "");
        const shouldCreate = Boolean(frappe.route_options?.new_pricing_sheet || params.get("new_pricing_sheet"));
        const routeSheetName = currentRouteSheetName();
        const sheetName = shouldCreate ? "" : (routeSheetName || frappe.route_options?.pricing_sheet || params.get("pricing_sheet") || "");
        const routeOpportunity = shouldCreate ? (frappe.route_options?.opportunity || params.get("opportunity") || "") : "";
        const routeAutoSave = shouldCreate && Boolean(frappe.route_options?.auto_save_pricing_sheet || params.get("auto_save_pricing_sheet"));
        const routePrefill = shouldCreate ? {
            company: frappe.route_options?.company || params.get("company") || "",
            party_type: frappe.route_options?.party_type || params.get("party_type") || "",
            party_name: frappe.route_options?.party_name || params.get("party_name") || "",
            source_quotation: frappe.route_options?.source_quotation || params.get("source_quotation") || "",
            link_source_quotation: frappe.route_options?.link_source_quotation || params.get("link_source_quotation") || "",
        } : {};
        const routeKey = shouldCreate || !sheetName ? "__new__" : sheetName;
        if (frappe.route_options) {
            frappe.route_options.new_pricing_sheet = null;
            frappe.route_options.pricing_sheet = null;
            frappe.route_options.opportunity = null;
            frappe.route_options.auto_save_pricing_sheet = null;
            frappe.route_options.company = null;
            frappe.route_options.party_type = null;
            frappe.route_options.party_name = null;
            frappe.route_options.source_quotation = null;
            frappe.route_options.link_source_quotation = null;
        }
        if (STATE.loadedRouteKey === routeKey && !STATE.loading) return;
        STATE.loadedRouteKey = routeKey;
        await load(page, sheetName, routeOpportunity, routeAutoSave, routePrefill);
    }

    function currentRouteSheetName() {
        const route = frappe.get_route ? frappe.get_route() : [];
        return route && route[0] === "pricing-sheet-builder" ? (route[1] || "") : "";
    }

    function syncRouteAfterSave(sheetName) {
        if (!sheetName || currentRouteSheetName() === sheetName) return;
        STATE.loadedRouteKey = sheetName;
        frappe.set_route("pricing-sheet-builder", sheetName);
    }

    async function load(page, sheetName, routeOpportunity, routeAutoSave, routePrefill = {}) {
        STATE.loading = true;
        STATE.error = "";
        let autoSaveAfterLoad = false;
        render(page);
        try {
            const res = await frappe.call({
                method: "orderlift.orderlift_sales.page.pricing_sheet_builder.pricing_sheet_builder.get_pricing_sheet_builder_payload",
                args: { pricing_sheet: sheetName || "" },
            });
            STATE.sheet = { ...blankSheet(), ...((res.message || {}).sheet || {}) };
            STATE.sheet.pricing_mode = resolvePricingMode(STATE.sheet);
            STATE.marginBasis = (res.message || {}).sheet?.margin_basis || STATE.marginBasis;
            STATE.lineColumns = loadLineColumns();
            STATE.selectedLineKeys.clear();
            ensureLineClientIds();
            pruneSelectedLineKeys();
            ensurePriceListMappingTable();
            STATE.dimensioning = null;
            STATE.dimensioningValues = parseDimensioningValues();
            STATE.dimensioningPreview = [];
            STATE.customerPricingContext = null;
            applyRoutePrefill(routePrefill);
            if (routePrefill.source_quotation) {
                await applyQuotationContext(page, routePrefill.source_quotation);
            }
            normalizePartyFields();
            if (STATE.sheet.party_name) {
                await applyPartyPricingContext(page, { silent: true, renderAfter: false });
            }
            if (routeOpportunity && !STATE.sheet.opportunity) {
                STATE.sheet.opportunity = routeOpportunity;
                await applyOpportunityContext(page);
                autoSaveAfterLoad = Boolean(routeAutoSave && !STATE.sheet.name);
            }
            if (STATE.sheet.dimensioning_set) {
                await loadDimensioningConfig(page, false);
            }
        } catch (error) {
            console.error("Pricing Sheet Builder failed", error);
            STATE.error = __("Unable to load the Pricing Sheet Builder.");
        } finally {
            STATE.loading = false;
            render(page);
            if (autoSaveAfterLoad) {
                const saved = await save(page, { silent: true, freeze: false });
                if (saved) frappe.show_alert({ message: __("Pricing Sheet created from opportunity"), indicator: "green" });
            } else {
                scheduleAutoPrice(page);
            }
        }
    }

    function applyRoutePrefill(prefill) {
        if (!prefill || STATE.sheet.name) return;
        if (prefill.company) STATE.sheet.custom_company = prefill.company;
        if (prefill.party_type) STATE.sheet.party_type = prefill.party_type;
        if (prefill.party_name) STATE.sheet.party_name = prefill.party_name;
        if (prefill.source_quotation) STATE.sheet.source_quotation = prefill.source_quotation;
        STATE.sheet.link_source_quotation = prefill.link_source_quotation ? 1 : 0;
        if (prefill.source_quotation && !STATE.sheet.sheet_name) STATE.sheet.sheet_name = `${__("Pricing Sheet")} - ${prefill.source_quotation}`;
    }

    async function applyQuotationContext(page, quotation) {
        if (!quotation || STATE.sheet.name) return;
        try {
            const res = await frappe.call({
                method: "orderlift.orderlift_sales.page.pricing_sheet_builder.pricing_sheet_builder.get_quotation_pricing_sheet_source",
                args: { quotation },
            });
            const source = res.message || {};
            STATE.sheet.source_quotation = source.quotation || quotation;
            STATE.sheet.custom_company = source.company || STATE.sheet.custom_company;
            STATE.sheet.party_type = source.party_type || STATE.sheet.party_type || "Customer";
            STATE.sheet.party_name = source.party_name || STATE.sheet.party_name || "";
            STATE.sheet.customer = source.customer || (STATE.sheet.party_type === "Customer" ? STATE.sheet.party_name : "");
            STATE.sheet.opportunity = source.opportunity || STATE.sheet.opportunity || "";
            STATE.sheet.crm_business_type = source.crm_business_type || STATE.sheet.crm_business_type || "";
            STATE.sheet.crm_segment = source.crm_segment || STATE.sheet.crm_segment || "";
            STATE.sheet.geography_territory = source.geography_territory || STATE.sheet.geography_territory || "";
            STATE.sheet.taxes_and_charges_template = source.taxes_and_charges_template || STATE.sheet.taxes_and_charges_template || "";
            STATE.sheet.selected_price_list = source.selected_price_list || STATE.sheet.selected_price_list || "";
            if ((source.selected_selling_price_lists || []).length) {
                STATE.sheet.selected_selling_price_lists = source.selected_selling_price_lists;
                STATE.sheet.pricing_mode = "Static";
            }
            if ((source.lines || []).length) {
                STATE.sheet.lines = source.lines.map(normalizeSourceLine);
                ensureLineClientIds();
            }
            if (!STATE.sheet.sheet_name) STATE.sheet.sheet_name = source.title || `${__("Pricing Sheet")} - ${quotation}`;
        } catch (error) {
            frappe.msgprint({ title: __("Quotation failed"), message: error.message || __("Unable to load Quotation context."), indicator: "red" });
        }
    }

    function render(page) {
        const sheet = STATE.sheet || blankSheet();
        page.main.html(`
            <div class="psb-shell">
                <nav class="psb-breadcrumb" aria-label="${__("Breadcrumb")}">
                    <a href="/desk/home-page?sidebar=Main+Dashboard">${__("Sales")}</a>
                    <span class="sep">/</span>
                    <a href="/desk/pricing-sheet-manager?sidebar=Main+Dashboard">${__("Pricing Sheets")}</a>
                    <span class="sep">/</span>
                    <span class="current">${__("Builder")}</span>
                </nav>
                ${hero(sheet)}
                ${canViewSensitivePricing() ? marginBasisInfo(sheet) : ""}
                ${STATE.error ? `<div class="psb-error">${escapeHtml(STATE.error)}</div>` : ""}
                <section class="psb-tabs">${NAV.map(navItem).join("")}</section>
                <main class="psb-editor">${STATE.loading ? skeleton() : activeSection()}</main>
                ${bottomBar()}
            </div>
        `);
        bind(page);
        mountLinkControls(page);
    }

    function hero(sheet) {
        const lines = sheet.lines || [];
        const finalTotal = Number(sheet.total_selling || 0);
        const totalBuy = lines.reduce((t, r) => t + Number(r.buy_price || 0) * Number(r.qty || 1), 0);
        const totalExpenses = lines.reduce((t, r) => t + Number(r.expense_total || 0), 0);
        const totalCustoms = lines.reduce((t, r) => t + Number(r.customs_applied || 0), 0);
        const totalCost = totalBuy + totalExpenses + totalCustoms;
        const discountedTotal = lines.reduce((total, row) => total + Number(row.discounted_sell_total || row.final_sell_total || 0), 0);
        const totalTax = lines.reduce((total, row) => total + Number(row.custom_applied_taxes || 0), 0);
        const totalTtc = lines.reduce((total, row) => total + Number(row.custom_pt_ttc || row.discounted_sell_total || row.final_sell_total || 0), 0);
        const commissionTotal = lines.reduce((total, row) => total + Number(row.commission_amount || 0), 0);
        const marginPct = sheetTotalMarginPct(sheet);
        const warnings = String(sheet.projection_warnings || "").split("\n").filter(Boolean).length;
        return `
            <section class="psb-hero">
                <div>
                    <div class="psb-eyebrow">${__("Commercial Builder")}</div>
                    <h1>${escapeHtml(sheet.sheet_name || __("New Pricing Sheet"))}</h1>
                    <p>${escapeHtml([sheet.custom_company, partyLabel(sheet), sheet.sales_person, sheet.resolved_mode].filter(Boolean).join(" - ") || __("Prepare party context, add priced items, then generate the quotation."))}</p>
                </div>
                <div class="psb-hero-kpis">
                    ${metric(__("Lines"), lines.length)}
                    ${canViewSensitivePricing() ? metric(__("Buy Price"), formatCurrency(totalBuy)) : ""}
                    ${canViewSensitivePricing() ? metric(__("Expenses"), formatCurrency(totalExpenses)) : ""}
                    ${canViewSensitivePricing() ? metric(__("Customs"), formatCurrency(totalCustoms)) : ""}
                    ${canViewSensitivePricing() ? metric(__("Cost HT"), formatCurrency(totalCost), "accent") : ""}
                    ${metric(__("Final Price"), formatCurrency(finalTotal), "accent")}
                    ${metric(__("Discount"), formatCurrency(finalTotal - discountedTotal))}
                    ${metric(__("After Discount"), formatCurrency(discountedTotal), "accent")}
                    ${canViewSensitivePricing() ? marginMetric(STATE.marginBasis, marginPct) : ""}
                    ${metric(__("Commission"), formatCurrency(commissionTotal))}
                    ${metric(__("Taxes"), formatCurrency(totalTax))}
                    ${metric(__("TTC"), formatCurrency(totalTtc), "accent")}
                    ${metric(__("Warnings"), warnings)}
                </div>
            </section>
        `;
    }

    function sheetTotalMarginPct(sheet) {
        const totalSell = Number(sheet.total_selling || 0);
        const totalBuy = (sheet.lines || []).reduce((t, r) => t + Number(r.buy_price || 0) * Number(r.qty || 1), 0);
        const totalExpenses = (sheet.lines || []).reduce((t, r) => t + Number(r.expense_total || 0), 0);
        const totalCustoms = (sheet.lines || []).reduce((t, r) => t + Number(r.customs_applied || 0), 0);
        const totalCost = totalBuy + totalExpenses + totalCustoms;
        const marginAmount = totalSell - totalCost;
        const basis = STATE.marginBasis || "Loaded Cost";
        let denominator;
        if (basis === "Base Price") denominator = totalBuy;
        else if (basis === "Sale Price") denominator = totalSell;
        else denominator = totalCost;
        return denominator > 0 ? (marginAmount / denominator) * 100 : 0;
    }

    function partyLabel(sheet) {
        const partyType = sheet.party_type || (sheet.customer ? "Customer" : "");
        const partyName = sheet.party_name || sheet.customer || "";
        return [partyType, partyName].filter(Boolean).join(": ");
    }

    function marginBasisInfo(sheet) {
        const lines = sheet.lines || [];
        const mode = resolvePricingMode(sheet);
        if (mode === "Static") {
            const info = new Map();
            lines.forEach((row) => {
                const list = row.resolved_selling_price_list || row.source_selling_price_list || "";
                if (!list) return;
                const basis = row.margin_basis || "";
                if (!info.has(list)) info.set(list, { basis, hasStamps: false });
                if (row.pricing_builder) info.get(list).hasStamps = true;
            });
            if (!info.size) return "";
            return `<section class="psb-card psb-margin-info"><div class="psb-section-head"><h2>${__("Margin Sources")}</h2><p>${__("Selling price lists used and the margin basis applied by each.")}</p></div><div class="psb-margin-source-list">${Array.from(info.entries()).map(([list, detail]) => `<span><strong>${escapeHtml(list)}</strong><small>${detail.hasStamps ? escapeHtml(detail.basis || __("Dynamic")) : __("Unstamped")}</small></span>`).join("")}</div></section>`;
        }
        // Dynamic mode: show basis from policy
        const bases = new Set(lines.map((row) => row.margin_basis || "").filter(Boolean));
        if (!bases.size) return "";
        const policyBasis = sheet.margin_basis || "";
        return `<section class="psb-card psb-margin-info"><div class="psb-section-head"><h2>${__("Margin Basis")}</h2><p>${__("Margin calculated using: {0}. Selector above shows the same margin in other bases for comparison.", [escapeHtml(bases.has(policyBasis) ? policyBasis : Array.from(bases).join(", ") || __("policy default"))])}</p></div></section>`;
    }

    function navItem(item) {
        return `
            <button type="button" class="psb-nav-item ${STATE.active === item.key ? "active" : ""}" data-nav="${item.key}">
                <span>${escapeHtml(item.step)}</span><strong>${escapeHtml(__(item.label))}</strong>
            </button>
        `;
    }

    function activeSection() {
        if (STATE.active === "items") return itemsSection();
        if (STATE.active === "breakdown") return breakdownSection();
        if (STATE.active === "quotation") return quotationSection();
        return setupSection();
    }

    function setupSection() {
        const sheet = STATE.sheet;
        const mode = resolvePricingMode(sheet);
        const canEditPricingSource = Boolean(sheet.user_context?.can_edit_pricing_source ?? true);
        const canEditPricingMode = Boolean(sheet.user_context?.can_edit_pricing_mode ?? canEditPricingSource);
        const canEditSalesPerson = Boolean(sheet.user_context?.can_edit_sales_person ?? true);
        return `
            <section class="psb-card">
                <div class="psb-section-head">
                    <div><h2>${__("Party and pricing context")}</h2><p>${__("This is the commercial header used by the pricing engine and quotation generation.")}</p></div>
                    <span class="psb-badge">${escapeHtml(sheet.resolved_mode || "Draft")}</span>
                </div>
                <div class="psb-form-grid two">
                    ${textField("sheet_name", __("Sheet name"), sheet.sheet_name, true)}
                    ${linkField("custom_company", __("Company"), "Company", sheet.custom_company, false, true)}
                    ${selectField("party_type", __("Party Type"), sheet.party_type || "Customer", ["Customer", "Lead", "Prospect"])}
                    ${linkField("party_name", __("Party"), sheet.party_type || "Customer", sheet.party_name || sheet.customer, true)}
                    ${linkField("opportunity", __("Opportunity"), "Opportunity", sheet.opportunity)}
                    ${linkField("sales_person", __("Sales Person"), "Sales Person", sheet.sales_person, false, !canEditSalesPerson)}
                    ${linkField("geography_territory", __("Territory"), "Territory", sheet.geography_territory)}
                    ${linkField("taxes_and_charges_template", __("Sales Taxes Template"), "Sales Taxes and Charges Template", sheet.taxes_and_charges_template)}
                    ${linkField("crm_business_type", __("Business Type"), "CRM Business Type", sheet.crm_business_type)}
                    ${linkField("crm_segment", __("CRM Segment"), "CRM Segment", sheet.crm_segment)}
                </div>
                ${customerPricingContextNotice(sheet)}
            </section>
            ${pricingSourceSection(sheet, mode, canEditPricingSource, canEditPricingMode)}
            ${historySection(sheet)}
        `;
    }

    function pricingSourceSection(sheet, mode, canEditPricingSource, canEditPricingMode) {
        if (!canEditPricingSource) return agentPricingNotice(sheet);
        if (!canEditPricingMode) {
            return `<section class="psb-card psb-mode-card">
                <div class="psb-section-head">
                    <div><h2>${__("Pricing source")}</h2><p>${__("Pricing mode is managed by your assigned agent rule.")}</p></div>
                    <span class="psb-badge">${escapeHtml(mode)}</span>
                </div>
                ${mode === "Static" ? staticPriceListPanel(sheet) : agentPricingNotice(sheet)}
            </section>`;
        }
        return `<section class="psb-card psb-mode-card">
            <div class="psb-section-head">
                <div><h2>${__("Pricing source")}</h2><p>${__("Choose one engine for this sheet. Dynamic uses buying price lists and policy mappings; static uses one published selling price list.")}</p></div>
            </div>
            <div class="psb-mode-switch">
                ${modeCard("Dynamic", mode, __("Dynamic calculation"), __("Buying price lists + expenses, customs, and margin policies."))}
                ${modeCard("Static", mode, __("Static selling price"), __("Published selling price list, with quotation prices taken from Item Price."))}
            </div>
            ${mode === "Static" ? staticPriceListPanel(sheet) : policyMappingPanel(sheet)}
        </section>`;
    }

    function agentPricingNotice(sheet) {
        const commission = Number(sheet.user_context?.commission_rate || 0);
        return `
            <section class="psb-card psb-agent-card">
                <div class="psb-section-head">
                    <div><h2>${__("Agent pricing applied")}</h2><p>${__("Pricing source is managed by your assigned agent rule.")}</p></div>
                    <span class="psb-badge">${escapeHtml(sheet.user_context?.sales_person || __("Agent"))}</span>
                </div>
                <div class="psb-agent-limits">
                    ${metric(__("Commission"), `${commission.toFixed(1)}%`)}
                </div>
            </section>`;
    }

    function customerPricingContextNotice(sheet) {
        if (!(sheet.party_name || sheet.customer)) return "";
        const context = STATE.customerPricingContext || {};
        const selected = context.selected || {};
        const segments = context.segments || [];
        const businessType = selected.business_type || sheet.crm_business_type || "";
        const crmSegment = selected.crm_segment || sheet.crm_segment || "";
        const tierNotice = customerPricingTierNotice(sheet, context);

        if (!segments.length || (!businessType && !crmSegment)) {
            return `
                <div class="psb-context-note warning">
                    <strong>${__("Missing CRM context for this party.")}</strong>
                    ${tierNotice}
                    <span>${__("Add Business Type and CRM Segment rows on the selected party. This builder will only allow contexts assigned to that party.")}</span>
                </div>`;
        }

        return `
            <div class="psb-context-note">
                <strong>${__("Loaded party CRM pricing context")}</strong>
                ${tierNotice}
                <span>${escapeHtml(businessType || __("missing"))} / ${escapeHtml(crmSegment || __("missing"))}${context.has_multiple ? ` - ${__("multiple contexts available")}` : ""}</span>
            </div>`;
    }

    function customerPricingTierNotice(sheet, context) {
        const tier = context.tier || sheet.tier || "";
        const tierMode = context.tier_mode || "";
        const tierSource = context.tier_source || "";
        const tierMessage = context.tier_message || "";
        const source = tierMode || tierSource || __("Manual");
        const sourceDetail = tierSource && tierSource !== tierMode ? ` - ${escapeHtml(tierSource)}` : "";
        return `
            <span><strong>${__("Pricing Tier")}:</strong> ${escapeHtml(tier || __("not assigned"))}</span>
            <span><strong>${__("Tier Source")}:</strong> ${escapeHtml(source)}${sourceDetail}</span>
            ${tierMessage ? `<span>${escapeHtml(tierMessage)}</span>` : ""}
        `;
    }

    function historySection(sheet) {
        const events = sheet.history || [];
        const collapsed = STATE.historyCollapsed;
        return `
            <section class="psb-card psb-history-card ${collapsed ? "is-collapsed" : ""}">
                <div class="psb-section-head">
                    <div><h2>${__("Change history")}</h2><p>${__("Recent Pricing Sheet saves from Frappe's version log.")}</p></div>
                    <button type="button" class="psb-history-toggle" data-toggle-history>
                        ${escapeHtml(collapsed ? __("Show history") : __("Hide history"))}
                        <span>${escapeHtml(events.length ? __("{0} event(s)", [events.length]) : __("New sheet"))}</span>
                    </button>
                </div>
                <div class="psb-history-content">
                    ${events.length ? `<div class="psb-history-list">${events.map(historyEvent).join("")}</div>` : `<div class="psb-muted">${__("Save this Pricing Sheet to start recording history.")}</div>`}
                </div>
            </section>`;
    }

    function historyEvent(event) {
        return `
            <article class="psb-history-event">
                <span class="psb-history-dot"></span>
                <div>
                    <strong>${escapeHtml(event.label || __("Changed"))}</strong>
                    <p>${escapeHtml(event.summary || __("Pricing Sheet updated."))}</p>
                </div>
                <aside>
                    <span>${escapeHtml(event.actor || "-")}</span>
                    <time>${escapeHtml(formatDateTime(event.modified))}</time>
                </aside>
            </article>`;
    }

    function modeCard(value, current, title, description) {
        return `
            <label class="psb-mode-option ${value === current ? "active" : ""}">
                <input type="radio" name="psb-pricing-mode" data-pricing-mode value="${escapeHtml(value)}" ${value === current ? "checked" : ""}>
                <strong>${escapeHtml(title)}</strong>
                <span>${escapeHtml(description)}</span>
            </label>`;
    }

    function staticPriceListPanel(sheet) {
        const rows = selectedSellingPriceLists(sheet);
        return `
            <div class="psb-static-panel psb-static-panel-lists">
                <div class="psb-static-list-head">
                    <div><strong>${__("Selling Price Lists")}</strong><span>${__("Selected lists define item availability. When an item exists in multiple lists, the first active list by sequence wins.")}</span></div>
                    <button type="button" class="psb-btn ghost" data-add-selling-list>${__("Add Selling List")}</button>
                </div>
                <div class="psb-selling-list-rows">
                    ${rows.length ? rows.map(sellingPriceListRow).join("") : `<div class="psb-map-empty">${__("No selling price lists selected yet.")}</div>`}
                </div>
                <p>${__("Static mode prices each line from the selected selling lists, applies global tier/territory modifiers, then applies line discount and commission. Max discount comes from the stamped selling Item Price.")}</p>
            </div>`;
    }

    function sellingPriceListRow(row, index) {
        return `
            <article class="psb-selling-list-row" data-selling-index="${index}">
                <span>${String(index + 1).padStart(2, "0")}</span>
                <div data-selling-list-link="price_list" data-selling-index="${index}" data-options="Price List"></div>
                <label><small>${__("Sequence")}</small><input type="number" data-selling-list-field="sequence" data-selling-index="${index}" value="${escapeHtml(row.sequence || (index + 1) * 10)}"></label>
                <label class="psb-check"><input type="checkbox" data-selling-list-field="is_active" data-selling-index="${index}" ${Number(row.is_active ?? 1) ? "checked" : ""}> ${__("Active")}</label>
                <button type="button" class="psb-icon-btn" data-delete-selling-list="${index}" aria-label="${escapeHtml(__("Remove selling list"))}">&times;</button>
            </article>`;
    }

    function policyMappingPanel(sheet) {
        const mappings = sheet.scenario_mappings || [];
        return `
            <div class="psb-policy-card">
                <div class="psb-section-head">
                    <div><h2>${__("Price list mappings")}</h2><p>${__("Add one row per buying price list. Leave Buying Price List blank only when you intentionally want a fallback for unmatched lines.")}</p></div>
                    <button type="button" class="psb-btn ghost" data-add-mapping>${__("Add Price List")}</button>
                </div>
                <div class="psb-map-list">
                    ${mappings.length ? mappings.map(mappingRow).join("") : `<div class="psb-map-empty">${__("No price list mappings yet. Add one row per buying price list.")}</div>`}
                </div>
            </div>
        `;
    }

    function mappingRow(row, index) {
        const rowTitle = row.source_buying_price_list || __("Select buying price list");
        return `
            <article class="psb-map-card" data-map-index="${index}">
                <div class="psb-map-row-head">
                    <span>${String(index + 1).padStart(2, "0")}</span>
                    <strong>${escapeHtml(rowTitle)}</strong>
                    <em>${row.source_buying_price_list ? __("Buying list rule") : __("Blank buying list becomes a fallback rule")}</em>
                </div>
                <div class="psb-map-fields">
                    ${mappingField(index, "source_buying_price_list", __("Buying Price List"), "Price List", row.source_buying_price_list)}
                    ${mappingField(index, "pricing_scenario", __("Expenses Policy"), "Pricing Scenario", row.pricing_scenario)}
                    ${mappingField(index, "customs_policy", __("Customs Policy"), "Pricing Customs Policy", row.customs_policy)}
                    ${mappingField(index, "benchmark_policy", __("Margin Policy"), "Pricing Benchmark Policy", row.benchmark_policy)}
                </div>
                <div class="psb-map-controls">
                    <label class="psb-map-priority"><span>${__("Priority")}</span><input type="number" data-map-field="priority" data-map-index="${index}" value="${escapeHtml(row.priority || 10)}"></label>
                    <label class="psb-check compact"><input type="checkbox" data-map-field="is_active" data-map-index="${index}" ${Number(row.is_active ?? 1) ? "checked" : ""}><span>${__("Active")}</span></label>
                    <button type="button" class="psb-icon-btn" data-delete-mapping="${index}" aria-label="${escapeHtml(__("Delete mapping"))}">&times;</button>
                </div>
            </article>
        `;
    }

    function mappingField(index, field, label, options, value) {
        return `
            <label class="psb-map-field">
                <span>${escapeHtml(label)}</span>
                ${mappingLink(index, field, options, value)}
            </label>`;
    }

    function mappingLink(index, field, options, value) {
        return `<div data-map-link="${field}" data-map-index="${index}" data-options="${escapeHtml(options)}" data-value="${escapeHtml(value || "")}"></div>`;
    }

    function itemsSection() {
        const collapsed = STATE.itemsCollapsed;
        const lines = STATE.sheet.lines || [];
        return `
            <section class="psb-card psb-items-card ${collapsed ? "is-collapsed" : ""}">
                <div class="psb-section-head">
                    <button type="button" class="psb-collapse-title" data-toggle-items>
                        <span>${collapsed ? "+" : "-"}</span>
                        <div><h2>${__("Build quotation lines")}</h2><p>${lines.length} ${__("line(s)")} · ${formatCurrency(STATE.sheet.total_selling)}</p></div>
                    </button>
                    <div class="psb-actions">
                        <button type="button" class="psb-btn ghost" data-columns>${__("Columns")}</button>
                        <button type="button" class="psb-btn ghost" data-bulk-quantity ${selectedLineCount() ? "" : "disabled"}>${__("Bulk Quantity")}</button>
                        <button type="button" class="psb-btn danger" data-delete-selected-lines ${selectedLineCount() ? "" : "disabled"}>${__("Delete Selected")} ${selectedLineCount() ? `(${selectedLineCount()})` : ""}</button>
                        <button type="button" class="psb-btn ghost" data-load-opportunity-items>${__("Load Opportunity Items")}</button>
                        <button type="button" class="psb-btn ghost" data-add-multiple>${__("Add Multiple")}</button>
                        <button type="button" class="psb-btn ghost" data-add-line>${__("Add Line")}</button>
                        <button type="button" class="psb-btn ghost" data-add-bundle>${__("Add Bundle")}</button>
                    </div>
                </div>
                <div class="psb-items-body">
                    ${dimensioningPanel()}
                    ${lineTable()}
                </div>
            </section>
        `;
    }

    function dimensioningPanel() {
        const cfg = STATE.dimensioning;
        return `
            <div class="psb-dim-panel">
                <div class="psb-dim-head">
                    <div><span>${__("Dimensioning")}</span><strong>${__("Generate technical articles")}</strong>${cfg ? dimensioningSummary(cfg) : ""}</div>
                    ${linkField("dimensioning_set", __("Dimensioning Set"), "Dimensioning Set", STATE.sheet.dimensioning_set)}
                </div>
                ${STATE.sheet.dimensioning_set ? dimensioningInputs() : `<div class="psb-muted">${__("Select a Dimensioning Set to show guided inputs here.")}</div>`}
            </div>
        `;
    }

    function dimensioningSummary(cfg) {
        const questions = (cfg.fields || []).length;
        const ruleGroups = (cfg.rule_groups || []).length;
        const articles = (cfg.rule_groups || []).reduce((total, group) => total + ((group.articles || []).length), 0);
        return `<small class="psb-dim-summary"><b>${questions}</b> ${__("questions")} · <b>${ruleGroups}</b> ${__("rules")} · <b>${articles}</b> ${__("articles")}</small>`;
    }

    function dimensioningInputs() {
        const cfg = STATE.dimensioning;
        if (!cfg) return `<div class="psb-muted">${__("Loading dimensioning form...")}</div>`;
        const hasRules = (cfg.rule_groups || []).some((group) => (group.articles || []).length);
        const fields = (cfg.fields || []).map((field) => {
            const type = String(field.field_type || "Data").toLowerCase();
            const value = STATE.dimensioningValues[field.field_key];
            let control = "";
            if (type === "select") {
                control = `<select data-dim-key="${escapeHtml(field.field_key)}">${(field.options || []).map((option) => `<option value="${escapeHtml(option)}" ${String(value || "") === String(option) ? "selected" : ""}>${escapeHtml(option)}</option>`).join("")}</select>`;
            } else if (type === "check") {
                control = `<label class="psb-check"><input type="checkbox" data-dim-key="${escapeHtml(field.field_key)}" ${value ? "checked" : ""}> <span>${__("Enabled")}</span></label>`;
            } else {
                control = `<input type="${type === "int" || type === "float" ? "number" : "text"}" step="${type === "int" ? "1" : "any"}" data-dim-key="${escapeHtml(field.field_key)}" value="${escapeHtml(value == null ? "" : value)}">`;
            }
            return `<label class="psb-field"><span>${escapeHtml(field.label || field.field_key)}${field.is_required ? " *" : ""}</span>${control}${field.help_text ? `<small>${escapeHtml(field.help_text)}</small>` : ""}</label>`;
        }).join("");
        return `
            <div class="psb-dim-grid">${fields || `<div class="psb-muted">${__("This Dimensioning Set has no questionnaire yet. Open the builder and add Form Questions.")}</div>`}</div>
            <div class="psb-dim-actions">
                <button type="button" class="psb-btn ghost" data-preview-dim ${hasRules ? "" : "disabled"}>${__("Preview Articles")}</button>
                <button type="button" class="psb-btn primary" data-add-dim ${STATE.dimensioningPreview.length ? "" : "disabled"}>${__("Add Generated Lines")}</button>
            </div>
            ${hasRules ? "" : `<div class="psb-muted">${__("This set has no article rules yet, so it cannot generate items.")}</div>`}
            ${dimensioningPreviewPanel()}
        `;
    }

    function dimensioningPreviewPanel() {
        const count = (STATE.dimensioningPreview || []).length;
        const collapsed = STATE.dimensioningPreviewCollapsed;
        return `
            <div class="psb-preview-panel">
                <button type="button" class="psb-preview-toggle" data-toggle-dim-preview>
                    <span>${count ? __("{0} generated article(s) ready", [count]) : __("Generated article preview")}</span>
                    <strong>${collapsed ? __("Show") : __("Hide")}</strong>
                </button>
                ${collapsed ? "" : `<div class="psb-preview">${dimensioningPreview()}</div>`}
            </div>`;
    }

    function dimensioningPreview() {
        const rows = STATE.dimensioningPreview || [];
        if (!rows.length) return `<span>${__("Preview generated articles before insertion.")}</span>`;
        return `
            <div class="psb-preview-table-wrap">
                <table class="psb-preview-table">
                    <thead>
                        <tr>
                            <th>${escapeHtml(__("Item Code"))}</th>
                            <th>${escapeHtml(__("Item Name"))}</th>
                            <th>${escapeHtml(__("Qty"))}</th>
                            <th>${escapeHtml(__("UOM"))}</th>
                            <th>${escapeHtml(__("Display Group"))}</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows.map(dimensioningPreviewRow).join("")}
                    </tbody>
                </table>
            </div>`;
    }

    function dimensioningPreviewRow(row) {
        return `
            <tr>
                <td><strong>${escapeHtml(row.item || "-")}</strong>${row.item_group ? `<small>${escapeHtml(row.item_group)}</small>` : ""}</td>
                <td>${escapeHtml(row.item_name || "-")}${row.description ? `<small>${escapeHtml(textFromHtml(row.description))}</small>` : ""}</td>
                <td class="psb-number">${escapeHtml(textFromHtml(frappe.format(row.qty || 0, { fieldtype: "Float" })))}</td>
                <td>${escapeHtml(row.stock_uom || "-")}</td>
                <td>${escapeHtml(row.display_group || "-")}</td>
            </tr>`;
    }

    function lineTable() {
        ensureLineClientIds();
        const lines = STATE.sheet.lines || [];
        const columns = activeLineColumns();
        if (!lines.length) {
            return `<div class="psb-empty"><h3>${__("No lines yet")}</h3><p>${__("Add a line, load Opportunity items, import a bundle, or use dimensioning to generate article rows.")}</p><button type="button" class="psb-btn primary" data-add-line>${__("Add First Line")}</button></div>`;
        }
        return `
            <div class="psb-line-table-wrap">
                <table class="psb-line-table">
                    <colgroup>${columns.map(lineColumnCol).join("")}</colgroup>
                    <thead><tr>${columns.map(lineHeaderCell).join("")}</tr></thead>
                    <tbody>${lines.map((row, index) => lineRow(row, index, columns)).join("")}</tbody>
                </table>
            </div>
        `;
    }

    function lineHeaderCell(column) {
        if (column.key === "__select") {
            return `<th class="psb-col-select"><input type="checkbox" data-select-all-lines aria-label="${escapeHtml(__("Select all lines"))}"></th>`;
        }
        return `<th class="psb-col-${column.key}">${escapeHtml(__(lineColumnLabel(column)))}</th>`;
    }

    function lineColumnLabel(column) {
        if (isStaticPricingMode()) {
            if (column.key === "static_list_price") return "List Price U";
            if (column.key === "expense_unit_price") return "Modifiers U";
            if (column.key === "expense_total") return "Modifiers Total";
            if (column.key === "projected_unit_price") return "Static Price U";
            if (column.key === "projected_total_price") return "Static Total";
            if (column.key === "builder_margin_percent") return "Margin %";
        }
        return column.label;
    }

    function lineColumnCol(column) {
        return `<col class="psb-col-${escapeHtml(column.key)}">`;
    }

    function lineRow(row, index, columns) {
        const key = lineKey(row, index);
        return `<tr data-line-index="${index}" data-line-key="${escapeHtml(key)}" class="${STATE.selectedLineKeys.has(key) ? "is-selected" : ""}">${columns.map((column) => lineCell(column.key, row, index)).join("")}</tr>`;
    }

    function lineCell(key, row, index) {
        const money = (value) => `<td class="psb-money ${HIGHLIGHT_COLUMNS.has(key) ? "psb-cell-highlight" : ""}">${formatCurrency(value)}</td>`;
        const column = LINE_COLUMNS.find((item) => item.key === key) || {};
        if (key === "__select") return `<td class="psb-col-select"><input type="checkbox" data-select-line="${escapeHtml(lineKey(row, index))}" ${STATE.selectedLineKeys.has(lineKey(row, index)) ? "checked" : ""} aria-label="${escapeHtml(__("Select line"))}"></td>`;
        if (key === "item") return `<td class="psb-line-item"><div data-line-link="item" data-line-index="${index}" data-options="Item"></div>${row.buy_price_missing ? `<small class="psb-danger">${escapeHtml(row.buy_price_message || __("Missing buy price"))}</small>` : ""}</td>`;
        if (key === "item_name") return `<td class="psb-item-name">${escapeHtml(row.item_name || "-")}</td>`;
        if (key === "qty") return `<td><input type="number" step="any" data-line-field="qty" data-line-index="${index}" value="${escapeHtml(row.qty || 1)}"></td>`;
        if (key === "display_group") return `<td><input type="text" data-line-field="display_group" data-line-index="${index}" value="${escapeHtml(row.display_group || "")}"></td>`;
        if (key === "source_buying_price_list") return `<td><div data-line-link="source_buying_price_list" data-line-index="${index}" data-options="Price List"></div></td>`;
        if (key === "pricing_scenario") return `<td><div data-line-link="pricing_scenario" data-line-index="${index}" data-options="Pricing Scenario"></div></td>`;
        if (key === "buy_price" && isStaticPricingMode()) return money(staticBaseUnit(row));
        if (key === "base_amount" && isStaticPricingMode()) return money(staticBaseTotal(row));
        if (key === "expense_unit_price" && isStaticPricingMode()) return money(staticModifierUnit(row));
        if (key === "expense_total" && isStaticPricingMode()) return money(staticModifierTotal(row));
        if (key === "buy_price") return `<td><input type="number" step="any" data-line-field="buy_price" data-line-index="${index}" value="${escapeHtml(row.buy_price || 0)}"></td>`;
        if (key === "manual_sell_unit_price") return `<td><input type="number" step="any" data-line-field="manual_sell_unit_price" data-line-index="${index}" value="${escapeHtml(row.manual_sell_unit_price || 0)}"><small class="psb-discount-cap">${__("Min")} ${formatCurrency(manualOverrideFloor(row))}</small></td>`;
        if (key === "discount_percent") return `<td><input type="number" step="any" min="0" max="${escapeHtml(resolveMaxDiscount(row))}" data-line-field="discount_percent" data-line-index="${index}" value="${escapeHtml(row.discount_percent || 0)}"><small class="psb-discount-cap">${__("Max")} ${Number(resolveMaxDiscount(row)).toFixed(1)}%</small></td>`;
        if (key === "projected_unit_price") return money(lineCostUnit(row));
        if (key === "projected_total_price") return money(lineCostTotal(row));
        if (isStaticPricingMode() && ["builder_margin_percent", "target_margin_percent", "margin_pct"].includes(key) && !row.pricing_builder) return `<td class="psb-number">${__("N/A")}</td>`;
        if (column.type === "Currency") return money(row[key]);
        if (column.type === "Percent") return `<td class="psb-number">${escapeHtml(`${Number(row[key] || 0).toFixed(1)}%`)}</td>`;
        if (column.type === "Float") return `<td class="psb-number">${escapeHtml(frappe.format(row[key] || 0, { fieldtype: "Float" }))}</td>`;
        if (column.type === "Int") return `<td class="psb-number">${escapeHtml(String(Number(row[key] || 0)))}</td>`;
        if (column.type === "Check") return `<td><span class="psb-mini-badge">${Number(row[key] || 0) ? __("Yes") : __("No")}</span></td>`;
        if (key === "benchmark_status") return `<td><span class="psb-mini-badge">${escapeHtml(row.benchmark_status || "-")}</span></td>`;
        if (key === "dimensioning_rule_label") return `<td class="psb-dim-rule">${escapeHtml(row.dimensioning_rule_label || "-")}</td>`;
        if (key === "actions") return `<td><button type="button" class="psb-icon-btn" data-delete-line="${index}" aria-label="${escapeHtml(__("Delete line"))}">&times;</button></td>`;
        return `
            <td>${escapeHtml(row[key] || "")}</td>
        `;
    }

    function breakdownSection() {
        const lines = STATE.sheet.lines || [];
        return `
            <section class="psb-card psb-breakdown-card">
                <div class="psb-section-head">
                    <div><h2>${__("Price breakdown")}</h2><p>${__("Review the per-item pricing build-up, discounts, and commission calculation. Commission = unused allowed discount x selling total x commission rate.")}</p></div>
                </div>
                ${lines.length ? `<div class="psb-breakdown-list">${lines.map(breakdownCard).join("")}</div>` : `<div class="psb-muted">${__("Add quotation lines to see the price breakdown.")}</div>`}
            </section>`;
    }

    function breakdownCard(row, index) {
        const steps = parseBreakdownSteps(row);
        const details = breakdownDetailRows(row, steps);
        return `
            <article class="psb-breakdown-row">
                <div class="psb-breakdown-head">
                    <span>${String(index + 1).padStart(2, "0")}</span>
                    <div><strong>${escapeHtml(row.item || "-")}</strong><p>${escapeHtml(row.item_name || row.dimensioning_rule_label || "")}</p></div>
                    <em>${escapeHtml(frappe.format(row.qty || 0, { fieldtype: "Float" }))}</em>
                </div>
                <div class="psb-breakdown-metrics">
                    ${breakdownMetric(__("Sell Price U"), formatCurrency(row.final_sell_unit_price), true)}
                    ${breakdownMetric(__("Manual Override"), formatCurrency(row.manual_sell_unit_price))}
                    ${breakdownMetric(__("Total Sell"), formatCurrency(row.final_sell_total), true)}
                    ${breakdownMetric(__("Allowed Discount"), `${Number(resolveMaxDiscount(row)).toFixed(1)}%`)}
                    ${breakdownMetric(__("Discount"), `${Number(row.discount_percent || 0).toFixed(1)}%`)}
                    ${breakdownMetric(__("Unused Discount"), `${unusedDiscountPercent(row).toFixed(1)}%`)}
                    ${breakdownMetric(__("After Discount"), formatCurrency(row.discounted_sell_total || row.final_sell_total), true)}
                    ${breakdownMetric(__("Commission"), formatCurrency(row.commission_amount))}
                    ${isRestrictedAgent() ? "" : breakdownMetric(isStaticPricingMode() ? __("Modifiers U") : __("Expenses U"), formatCurrency(isStaticPricingMode() ? staticModifierUnit(row) : row.expense_unit_price))}
                    ${isRestrictedAgent() ? "" : breakdownMetric(isStaticPricingMode() ? __("Static Price U") : __("Total Cost U"), formatCurrency(lineCostUnit(row)), true)}
                    ${(!canViewSensitivePricing() || isRestrictedAgent() || isStaticPricingMode()) ? "" : breakdownMetric(__("Margin U"), formatCurrency(row.margin_unit_amount))}
                    ${(!canViewSensitivePricing() || isRestrictedAgent() || isStaticPricingMode()) ? "" : breakdownMetric(__("Margin %"), `${Number(row.margin_pct || 0).toFixed(1)}%`)}
                    ${(!canViewSensitivePricing() || isRestrictedAgent() || isStaticPricingMode()) ? "" : breakdownMetric(__("Margin Basis"), escapeHtml(row.margin_basis || "Base Price"))}
                    ${(!canViewSensitivePricing() || isRestrictedAgent() || !isStaticPricingMode()) ? "" : breakdownMetric(__("Margin %"), row.pricing_builder ? `${Number(row.builder_margin_percent || 0).toFixed(1)}%` : __("N/A"))}
                    ${(!canViewSensitivePricing() || isRestrictedAgent() || !isStaticPricingMode()) ? "" : breakdownMetric(__("Target Margin %"), row.pricing_builder ? `${Number(row.target_margin_percent || 0).toFixed(1)}% ${__("on")} ${escapeHtml(row.margin_basis || "Base Price")}` : __("N/A"))}
                    ${(!canViewSensitivePricing() || isRestrictedAgent() || isStaticPricingMode()) ? "" : breakdownMetric(__("Total Margin U"), formatCurrency(row.total_margin_unit_amount || totalMarginUnit(row)))}
                    ${isRestrictedAgent() || isStaticPricingMode() ? "" : breakdownMetric(__("Total Margin %"), `${Number(row.total_margin_pct || row.margin_pct || 0).toFixed(1)}%`)}
                </div>
                ${details.length && canViewSensitivePricing() && !isRestrictedAgent() ? `<div class="psb-breakdown-detail-wrap"><table class="psb-breakdown-detail"><thead><tr><th>${__("Component")}</th><th>${__("Unit")}</th><th>${__("Line")}</th><th>${__("Source")}</th></tr></thead><tbody>${details.map(breakdownDetailRow).join("")}</tbody></table></div>` : ""}
                ${steps.length && canViewSensitivePricing() && !isRestrictedAgent() ? `<div class="psb-sub-expenses"><strong>${__("Sub Expenses")}</strong><div class="psb-breakdown-steps">${steps.map(breakdownStep).join("")}</div></div>` : ""}
            </article>`;
    }

    function breakdownMetric(label, value, highlight) {
        return `<span class="psb-breakdown-metric ${highlight ? "highlight" : ""}"><em>${escapeHtml(label)}</em><strong>${escapeHtml(value)}</strong></span>`;
    }

    function breakdownStep(step) {
        return `
            <span class="psb-breakdown-step">
                <strong>${escapeHtml(step.label || step.type || __("Step"))}</strong>
                <em>${escapeHtml(formatCurrency(step.running_total || step.delta_unit || 0))}</em>
            </span>`;
    }

    function breakdownDetailRows(row, steps) {
        const qty = Number(row.qty || 0) || 1;
        const rows = [breakdownBaseRow(row, qty)];
        (steps || []).forEach((step) => {
            const lineAmount = Number(step.delta_sheet || 0) || Number(step.delta_line || 0) || (Number(step.delta_unit || 0) * qty);
            const unitAmount = Number(step.delta_unit || 0) || (qty ? Number(step.delta_line || step.delta_sheet || 0) / qty : 0);
            if (!lineAmount && !unitAmount) return;
            rows.push({ label: step.label || step.type || __("Expense"), unit: unitAmount, line: lineAmount, source: breakdownStepSource(step), tone: breakdownStepTone(step) });
        });
        if (Number(row.discount_amount || 0)) {
            rows.push({ label: __("Discount"), unit: -(Number(row.discount_amount || 0) / qty), line: -Number(row.discount_amount || 0), source: `${Number(row.discount_percent || 0).toFixed(1)}%`, tone: "discount" });
        }
        if (Number(row.commission_amount || 0)) {
            rows.push({ label: __("Commission"), unit: Number(row.commission_amount || 0) / qty, line: Number(row.commission_amount || 0), source: `${unusedDiscountPercent(row).toFixed(1)}% x ${Number(row.commission_rate || 0).toFixed(1)}%`, tone: "commission" });
        }
        rows.push({ label: __("Final Sell"), unit: Number(row.final_sell_unit_price || 0), line: Number(row.final_sell_total || 0), source: row.is_manual_override ? __("Manual override") : __("Calculated"), tone: "final" });
        return rows;
    }

    function breakdownBaseRow(row, qty) {
        if (isStaticPricingMode()) {
            const unit = staticBaseUnit(row);
            return {
                label: __("Static List Price"),
                unit,
                line: unit * qty,
                source: row.resolved_selling_price_list || firstActiveSellingPriceList() || "-",
                tone: "base",
            };
        }
        return {
            label: __("Base Buying Price"),
            unit: Number(row.buy_price || 0),
            line: row.base_amount == null ? Number(row.buy_price || 0) * qty : Number(row.base_amount || 0),
            source: row.source_buying_price_list || "-",
            tone: "base",
        };
    }

    function breakdownDetailRow(row) {
        return `<tr class="${escapeHtml(row.tone || "")}"><td>${escapeHtml(row.label || "-")}</td><td>${formatCurrency(row.unit)}</td><td>${formatCurrency(row.line)}</td><td>${escapeHtml(row.source || "-")}</td></tr>`;
    }

    function breakdownStepSource(step) {
        const source = String(step.override_source || "");
        if (source === "transport_policy") return __("Transport allocation");
        if (source === "storage_policy") return __("Storage allocation");
        if (source === "pricing_policy") return __("Margin policy");
        if (source === "tier_modifier") return __("Tier modifier");
        if (source === "zone_modifier") return __("Zone modifier");
        if (step.customs_tariff_number) return `${__("Customs")} ${step.customs_tariff_number}`;
        if (step.storage_volume_m3) return `${Number(step.storage_volume_m3 || 0).toFixed(3)} m3`;
        return step.scope || step.applies_to || "-";
    }

    function breakdownStepTone(step) {
        const source = String(step.override_source || "");
        if (source === "pricing_policy") return "margin";
        if (source === "transport_policy" || source === "storage_policy") return "expense";
        if (source === "tier_modifier" || source === "zone_modifier") return "modifier";
        if (step.customs_tariff_number) return "customs";
        return "expense";
    }

    function parseBreakdownSteps(row) {
        try {
            const parsed = JSON.parse(row.pricing_breakdown_json || "[]");
            return Array.isArray(parsed) ? parsed : [];
        } catch (error) {
            return [];
        }
    }

    function quotationSection() {
        const preview = STATE.sheet.quotation_preview || {};
        const warnings = STATE.sheet.projection_warnings || preview.warnings || "";
        return `
            <section class="psb-card">
                <div class="psb-section-head">
                    <div><h2>${__("Quotation preview")}</h2><p>${__("Review totals and line visibility before generating the ERPNext Quotation document.")}</p></div>
                    <button type="button" class="psb-btn primary" data-generate>${__("Generate Quotation")}</button>
                </div>
                <div class="psb-quote-grid">
                    ${quoteMetric(__("Lines"), preview.line_count || (STATE.sheet.lines || []).length)}
                    ${quoteMetric(__("Quotation Rows"), preview.detailed_count || 0)}
                    ${quoteMetric(__("Groups"), preview.grouped_count || 0)}
                    ${quoteMetric(__("Final HT"), formatCurrency(STATE.sheet.total_selling))}
                    ${quoteMetric(__("Applied Taxes"), formatCurrency(preview.total_tax || 0))}
                    ${quoteMetric(__("Final TTC"), formatCurrency(preview.total_ttc || 0))}
                </div>
                ${warnings ? `<div class="psb-warning"><strong>${__("Warnings")}</strong><pre>${escapeHtml(warnings)}</pre></div>` : `<div class="psb-ok">${__("No pricing warnings on the last calculation.")}</div>`}
            </section>
        `;
    }

    function bottomBar() {
        return `
            <div class="psb-bottom-bar">
                <button type="button" class="psb-btn ghost" data-manager>${__("Pricing Sheets")}</button>
                <button type="button" class="psb-btn ghost" data-add-line>${__("Add Line")}</button>
                <button type="button" class="psb-btn primary" data-save>${STATE.saving ? __("Saving...") : __("Save")}</button>
                <button type="button" class="psb-btn dark" data-generate>${__("Generate Quotation")}</button>
                ${STATE.sheet.name ? `<button type="button" class="psb-btn danger" data-delete-sheet>${__("Delete PS")}</button>` : ""}
            </div>
        `;
    }

    function bind(page) {
        page.main.find("[data-nav]").on("click", function () {
            STATE.active = $(this).attr("data-nav") || "setup";
            render(page);
        });
        page.main.find("[data-manager]").on("click", () => frappe.set_route("pricing-sheet-manager"));
        page.main.find("[data-save]").on("click", () => save(page));
        page.main.find("[data-generate]").on("click", () => generateQuotation(page));
        page.main.find("[data-delete-sheet]").on("click", () => confirmDeletePricingSheet(page));
        page.main.find("[data-columns]").on("click", () => openColumnDialog(page));
        page.main.find("[data-toggle-history]").on("click", () => {
            STATE.historyCollapsed = !STATE.historyCollapsed;
            render(page);
        });
        page.main.find("[data-toggle-items]").on("click", () => {
            STATE.itemsCollapsed = !STATE.itemsCollapsed;
            render(page);
        });
        page.main.find("[data-pricing-mode]").on("change", function () {
            STATE.sheet.pricing_mode = $(this).val() || "Dynamic";
            if (STATE.sheet.pricing_mode === "Static") {
                STATE.sheet.scenario_mappings = [];
                ensureStaticSellingPriceLists();
            } else {
                STATE.sheet.selected_price_list = "";
                STATE.sheet.selected_selling_price_lists = [];
                ensurePriceListMappingTable();
            }
            STATE.lineColumns = loadLineColumns();
            render(page);
            scheduleAutoPrice(page);
        });
        page.main.find("[data-add-mapping]").on("click", () => {
            STATE.sheet.scenario_mappings = STATE.sheet.scenario_mappings || [];
            STATE.sheet.scenario_mappings.push(defaultPolicyMapping());
            render(page);
        });
        page.main.find("[data-delete-mapping]").on("click", function () {
            STATE.sheet.scenario_mappings.splice(Number($(this).attr("data-delete-mapping")), 1);
            render(page);
        });
        page.main.find("[data-add-selling-list]").on("click", () => {
            STATE.sheet.selected_selling_price_lists = selectedSellingPriceLists(STATE.sheet);
            STATE.sheet.selected_selling_price_lists.push({ price_list: "", sequence: (STATE.sheet.selected_selling_price_lists.length + 1) * 10, is_active: 1 });
            render(page);
        });
        page.main.find("[data-delete-selling-list]").on("click", function () {
            STATE.sheet.selected_selling_price_lists = selectedSellingPriceLists(STATE.sheet);
            STATE.sheet.selected_selling_price_lists.splice(Number($(this).attr("data-delete-selling-list")), 1);
            STATE.sheet.selected_price_list = firstActiveSellingPriceList();
            render(page);
            scheduleAutoPrice(page);
        });
        page.main.find("[data-selling-list-field]").on("input change", function (event) {
            const index = Number($(this).attr("data-selling-index"));
            const rows = selectedSellingPriceLists(STATE.sheet);
            const row = rows[index];
            if (!row) return;
            const field = $(this).attr("data-selling-list-field");
            row[field] = $(this).attr("type") === "checkbox" ? (this.checked ? 1 : 0) : Number($(this).val() || 0);
            STATE.sheet.selected_selling_price_lists = rows;
            STATE.sheet.selected_price_list = firstActiveSellingPriceList();
            if (event.type === "change") scheduleAutoPrice(page);
        });
        page.main.find("[data-map-field]").on("input change", function (event) {
            const mapping = (STATE.sheet.scenario_mappings || [])[Number($(this).attr("data-map-index"))];
            if (!mapping) return;
            const field = $(this).attr("data-map-field");
            mapping[field] = $(this).attr("type") === "checkbox" ? (this.checked ? 1 : 0) : $(this).val();
            if (event.type === "change") scheduleAutoPrice(page);
        });
        page.main.find("[data-add-line]").on("click", () => {
            STATE.sheet.lines = STATE.sheet.lines || [];
            STATE.sheet.lines.push({ item: "", qty: 1, display_group: "", show_in_detail: 1, line_type: "Standard" });
            STATE.active = "items";
            render(page);
        });
        page.main.find("[data-delete-line]").on("click", function () {
            const index = Number($(this).attr("data-delete-line"));
            deleteLinesByIndex([index]);
            render(page);
            scheduleAutoPrice(page);
        });
        page.main.find("[data-bulk-quantity]").on("click", () => openBulkQuantityDialog(page));
        page.main.find("[data-load-opportunity-items]").on("click", () => openOpportunityItemsDialog(page));
        page.main.find("[data-add-multiple]").on("click", () => openAddMultipleDialog(page));
        page.main.find("[data-delete-selected-lines]").on("click", () => confirmDeleteSelectedLines(page));
        page.main.find("[data-select-all-lines]").on("change", function () {
            ensureLineClientIds();
            if (this.checked) {
                (STATE.sheet.lines || []).forEach((line, index) => STATE.selectedLineKeys.add(lineKey(line, index)));
            } else {
                STATE.selectedLineKeys.clear();
            }
            render(page);
        });
        page.main.find("[data-select-line]").on("change", function () {
            const key = $(this).attr("data-select-line");
            if (!key) return;
            if (this.checked) STATE.selectedLineKeys.add(key);
            else STATE.selectedLineKeys.delete(key);
            render(page);
        });
        page.main.find("[data-add-bundle]").on("click", () => openBundleDialog(page));
        page.main.find("[data-sheet-field]").on("input change", function () {
            const field = $(this).attr("data-sheet-field");
            STATE.sheet[field] = $(this).val();
            if (field === "party_type") {
                STATE.sheet.party_name = "";
                STATE.sheet.customer = "";
                STATE.sheet.opportunity = "";
                STATE.customerPricingContext = null;
                render(page);
            }
            if (field === "margin_basis") {
                STATE.marginBasis = $(this).val();
                render(page);
            }
        });
        page.main.find("[data-line-field]").on("input change", function (event) {
            const field = $(this).attr("data-line-field");
            const index = Number($(this).attr("data-line-index"));
            const line = STATE.sheet.lines[index];
            if (!line) return;
            if ($(this).attr("type") === "checkbox") {
                line[field] = this.checked ? 1 : 0;
            } else if (field === "discount_percent") {
                const maxDiscount = resolveMaxDiscount(line);
                const nextValue = Math.min(Math.max(Number($(this).val() || 0), 0), maxDiscount);
                line[field] = nextValue;
                if (nextValue !== Number($(this).val() || 0)) {
                    $(this).val(nextValue);
                    frappe.show_alert({ message: __("Discount capped at {0}%", [maxDiscount.toFixed(1)]), indicator: "orange" });
                }
            } else if (field === "manual_sell_unit_price") {
                const requested = Number($(this).val() || 0);
                const floor = manualOverrideFloor(line);
                const nextValue = requested > 0 && floor > 0 && requested < floor ? floor : requested;
                line[field] = nextValue;
                if (nextValue !== requested) {
                    $(this).val(nextValue);
                    frappe.show_alert({ message: __("Manual unit override raised to minimum {0}", [formatCurrency(floor)]), indicator: "orange" });
                }
            } else {
                line[field] = $(this).val();
            }
            if (event.type === "change") scheduleAutoPrice(page);
        });
        page.main.find("[data-dim-key]").on("input change", function () {
            const key = $(this).attr("data-dim-key");
            STATE.dimensioningValues[key] = $(this).attr("type") === "checkbox" ? this.checked : $(this).val();
            STATE.sheet.dimensioning_inputs_json = JSON.stringify(STATE.dimensioningValues || {});
            scheduleDimensioningPreview(page);
        });
        page.main.find("[data-toggle-dim-preview]").on("click", () => {
            STATE.dimensioningPreviewCollapsed = !STATE.dimensioningPreviewCollapsed;
            render(page);
        });
        page.main.find("[data-preview-dim]").on("click", () => previewDimensioning(page, { expand: true, showEmptyMessage: true }));
        page.main.find("[data-add-dim]").on("click", () => addDimensioning(page));
    }

    function mountLinkControls(page) {
        page.main.find("[data-link-field]").each((_, host) => {
            const field = host.getAttribute("data-link-field");
            const options = host.getAttribute("data-options");
            const readOnly = host.getAttribute("data-read-only") === "1";
            mountLink(host, options, STATE.sheet[field] || "", async (value) => {
                if (readOnly) return;
                const nextValue = value || "";
                if ((STATE.sheet[field] || "") === nextValue) return;
                STATE.sheet[field] = nextValue;
                if (field === "opportunity") {
                    await applyOpportunityContext(page);
                    scheduleAutoPrice(page);
                    return;
                }
                if (field === "party_name") {
                    STATE.sheet.opportunity = "";
                    STATE.sheet.customer = STATE.sheet.party_type === "Customer" ? nextValue : "";
                    await applyPartyPricingContext(page, { business_type: "", crm_segment: "" });
                    scheduleAutoPrice(page);
                    return;
                }
                if (field === "crm_business_type") {
                    STATE.sheet.crm_segment = "";
                    await applyPartyPricingContext(page, { business_type: nextValue, crm_segment: "", silent: true });
                    scheduleAutoPrice(page);
                    return;
                }
                if (field === "crm_segment") {
                    await applyPartyPricingContext(page, { business_type: STATE.sheet.crm_business_type, crm_segment: nextValue, silent: true });
                    scheduleAutoPrice(page);
                    return;
                }
                if (field === "dimensioning_set") {
                    STATE.dimensioning = null;
                    STATE.dimensioningPreview = [];
                    STATE.sheet.dimensioning_inputs_json = "";
                    loadDimensioningConfig(page, true);
                    return;
                }
                scheduleAutoPrice(page);
            }, getSheetLinkQuery(field), readOnly);
        });
        page.main.find("[data-line-link]").each((_, host) => {
            const field = host.getAttribute("data-line-link");
            const index = Number(host.getAttribute("data-line-index"));
            const options = host.getAttribute("data-options");
            const line = STATE.sheet.lines[index];
            if (!line) return;
            mountLink(host, options, line[field] || "", (value) => {
                const nextValue = value || "";
                if ((line[field] || "") === nextValue) return;
                line[field] = nextValue;
                if (field === "item") {
                    updateLineItemName(page, line, nextValue).catch((error) => console.error("Item name lookup failed", error));
                }
                scheduleAutoPrice(page);
            }, getLineLinkQuery(field, line));
        });
        page.main.find("[data-selling-list-link]").each((_, host) => {
            const index = Number(host.getAttribute("data-selling-index"));
            const options = host.getAttribute("data-options");
            const rows = selectedSellingPriceLists(STATE.sheet);
            const row = rows[index];
            if (!row) return;
            mountLink(host, options, row.price_list || "", (value) => {
                const nextValue = value || "";
                if ((row.price_list || "") === nextValue) return;
                rows[index].price_list = nextValue;
                STATE.sheet.selected_selling_price_lists = rows;
                STATE.sheet.selected_price_list = firstActiveSellingPriceList();
                scheduleAutoPrice(page);
            }, priceListQuery("selling"));
        });
        page.main.find("[data-map-link]").each((_, host) => {
            const field = host.getAttribute("data-map-link");
            const index = Number(host.getAttribute("data-map-index"));
            const options = host.getAttribute("data-options");
            const mapping = (STATE.sheet.scenario_mappings || [])[index];
            if (!mapping) return;
            mountLink(host, options, mapping[field] || "", (value) => {
                const nextValue = value || "";
                if ((mapping[field] || "") === nextValue) return;
                mapping[field] = nextValue;
                scheduleAutoPrice(page);
            }, getMappingLinkQuery(field));
        });
    }

    function scheduleAutoPrice(page) {
        clearTimeout(autoPriceTimer);
        if (!canAutoPrice()) return;
        autoPriceTimer = setTimeout(() => {
            autoSaveAndPrice(page).catch((error) => console.error("Pricing Sheet auto pricing failed", error));
        }, 650);
    }

    function canAutoPrice() {
        if (STATE.loading || STATE.saving) return false;
        if (!STATE.sheet || !(STATE.sheet.party_name || STATE.sheet.customer)) return false;
        return (STATE.sheet.lines || []).some((line) => String(line.item || "").trim());
    }

    async function autoSaveAndPrice(page) {
        if (!canAutoPrice()) return;
        await save(page, { silent: true, freeze: false });
    }

    function mountLink(host, options, value, onChange, getQuery, readOnly = false) {
        host.innerHTML = "";
        let syncing = true;
        const fieldname = host.getAttribute("data-link-field")
            || host.getAttribute("data-line-link")
            || host.getAttribute("data-selling-list-link")
            || host.getAttribute("data-map-link")
            || "link_value";
        const control = frappe.ui.form.make_control({
            parent: host,
            only_input: true,
            render_input: true,
            df: {
                fieldname,
                fieldtype: "Link",
                options,
                read_only: readOnly ? 1 : 0,
                get_query: getQuery,
                change: () => { if (!syncing) onChange(control.get_value() || ""); },
            },
        });
        if (getQuery) {
            control.get_query = getQuery;
            control.df.get_query = getQuery;
        }
        control.refresh();
        control.set_value(value || "");
        setTimeout(() => { syncing = false; }, 0);
        if (control.$input) control.$input.addClass("psb-link-input");
        if (readOnly && control.$input) control.$input.prop("disabled", true).addClass("disabled");
    }

    function getSheetLinkQuery(field) {
        if (field === "party_name") {
            return () => ({
                query: "orderlift.orderlift_sales.page.pricing_sheet_builder.pricing_sheet_builder.party_query",
                filters: {
                    party_type: STATE.sheet.party_type || "Customer",
                    company: STATE.sheet.custom_company || STATE.sheet?.user_context?.current_company || "",
                    business_type: STATE.sheet.crm_business_type || "",
                    crm_segment: STATE.sheet.crm_segment || "",
                },
            });
        }
        if (field === "opportunity") {
            return () => {
                const filters = { docstatus: ["<", 2] };
                const company = STATE.sheet.custom_company || STATE.sheet?.user_context?.current_company || "";
                if (company) filters.company = company;
                return { filters };
            };
        }
        if (field === "crm_business_type") {
            return () => {
                const filters = { is_active: 1 };
                const allowed = customerContextBusinessTypes();
                if (STATE.sheet.party_name || STATE.sheet.customer) filters.name = ["in", allowed.length ? allowed : ["__none__"]];
                return { filters };
            };
        }
        if (field === "crm_segment") {
            return () => {
                const filters = { is_active: 1 };
                const allowed = customerContextSegments();
                if (STATE.sheet.party_name || STATE.sheet.customer) {
                    filters.name = ["in", allowed.length ? allowed : ["__none__"]];
                } else if (STATE.sheet.crm_business_type) {
                    filters.business_type = STATE.sheet.crm_business_type;
                }
                return { filters };
            };
        }
        if (field === "taxes_and_charges_template") {
            return () => {
                const filters = { disabled: 0 };
                const company = STATE.sheet.custom_company || STATE.sheet?.user_context?.current_company || "";
                if (company) filters.company = company;
                return { filters };
            };
        }
        return undefined;
    }

    function getLineLinkQuery(field, line) {
        if (field === "item") {
            return () => {
                const mode = resolvePricingMode(STATE.sheet);
                const priceLists = mode === "Static" ? activeStaticSellingPriceLists() : activeDynamicBuyingPriceLists(line);
                if (!priceLists.length) return { filters: { name: ["in", ["__none__"]] } };
                return {
                    query: "orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet.priced_item_query",
                    filters: { price_lists: priceLists, buying: mode === "Static" ? 0 : 1 },
                };
            };
        }
        if (field === "source_buying_price_list") {
            return priceListQuery("buying");
        }
        return undefined;
    }

    function getMappingLinkQuery(field) {
        if (field === "source_buying_price_list") return priceListQuery("buying");
        return undefined;
    }

    function priceListQuery(kind) {
        return () => {
            const filters = {};
            if (kind === "buying") filters.buying = 1;
            if (kind === "selling") filters.selling = 1;
            const company = STATE.sheet?.custom_company || STATE.sheet?.user_context?.current_company || "";
            if (company) filters.custom_company = company;
            if (kind === "selling" && isRestrictedAgent()) {
                const allowed = (STATE.sheet?.user_context?.selling_price_lists || []).filter(Boolean);
                filters.name = ["in", allowed.length ? allowed : ["__none__"]];
            }
            return { filters };
        };
    }

    function customerContextRows() {
        return (STATE.customerPricingContext || {}).segments || [];
    }

    function customerContextBusinessTypes() {
        return [...new Set(customerContextRows().map((row) => row.business_type).filter(Boolean))];
    }

    function customerContextSegments() {
        const businessType = STATE.sheet.crm_business_type || "";
        return [...new Set(
            customerContextRows()
                .filter((row) => !businessType || row.business_type === businessType)
                .map((row) => row.crm_segment)
                .filter(Boolean)
        )];
    }

    function normalizePartyFields() {
        STATE.sheet.party_type = STATE.sheet.party_type || (STATE.sheet.customer ? "Customer" : "Customer");
        STATE.sheet.party_name = STATE.sheet.party_name || STATE.sheet.customer || "";
        STATE.sheet.customer = STATE.sheet.party_type === "Customer" ? STATE.sheet.party_name : "";
    }

    async function applyCustomerPricingContext(page, options = {}) {
        return applyPartyPricingContext(page, options);
    }

    async function applyPartyPricingContext(page, options = {}) {
        if (STATE.applyingCustomerPricingContext) return;
        STATE.applyingCustomerPricingContext = true;
        try {
            normalizePartyFields();
            if (!STATE.sheet.party_name) {
                STATE.customerPricingContext = null;
                STATE.sheet.customer_type = "";
                STATE.sheet.tier = "";
                STATE.sheet.crm_business_type = "";
                STATE.sheet.crm_segment = "";
                if (options.renderAfter !== false) render(page);
                return;
            }

            const response = await frappe.call({
                method: "orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet.get_party_pricing_context",
                args: {
                    party_type: STATE.sheet.party_type || "Customer",
                    party_name: STATE.sheet.party_name,
                    business_type: options.business_type !== undefined ? options.business_type : STATE.sheet.crm_business_type,
                    crm_segment: options.crm_segment !== undefined ? options.crm_segment : STATE.sheet.crm_segment,
                },
            });
            const context = response.message || {};
            const selected = context.selected || {};
            STATE.customerPricingContext = context;
            STATE.sheet.customer_type = context.customer_type || "";
            STATE.sheet.tier = context.tier || "";
            STATE.sheet.customer = STATE.sheet.party_type === "Customer" ? STATE.sheet.party_name : "";
            STATE.sheet.crm_business_type = selected.business_type || "";
            STATE.sheet.crm_segment = selected.crm_segment || "";

            if (context.has_multiple && !options.silent) {
                frappe.show_alert({
                    message: __("Party has multiple CRM contexts. Choices are limited to this party's assigned Business Types and Segments."),
                    indicator: "blue",
                });
            }
            if (options.renderAfter !== false) render(page);
        } finally {
            STATE.applyingCustomerPricingContext = false;
        }
    }

    async function applyOpportunityContext(page) {
        if (!STATE.sheet.opportunity) {
            render(page);
            return;
        }
        try {
            const res = await frappe.call({
                method: "orderlift.orderlift_sales.page.pricing_sheet_builder.pricing_sheet_builder.get_opportunity_pricing_sheet_source",
                args: { opportunity: STATE.sheet.opportunity },
                freeze: true,
            });
            const source = res.message || {};
            STATE.sheet.opportunity = source.opportunity || STATE.sheet.opportunity;
            STATE.sheet.custom_company = source.company || STATE.sheet.custom_company;
            STATE.sheet.party_type = source.party_type || STATE.sheet.party_type || "Customer";
            STATE.sheet.party_name = source.party_name || STATE.sheet.party_name || source.customer || "";
            STATE.sheet.customer = source.customer || STATE.sheet.customer;
            normalizePartyFields();
            STATE.sheet.crm_business_type = source.crm_business_type || STATE.sheet.crm_business_type;
            STATE.sheet.crm_segment = source.crm_segment || STATE.sheet.crm_segment;
            STATE.sheet.geography_territory = source.geography_territory || STATE.sheet.geography_territory;
            if ((source.items || []).length) {
                STATE.sheet.lines = source.items.map(normalizeSourceLine);
                ensureLineClientIds();
            }
            if (!STATE.sheet.sheet_name && source.title) STATE.sheet.sheet_name = source.title;
            if (STATE.sheet.party_name) await applyPartyPricingContext(page, { silent: true, renderAfter: false });
            frappe.show_alert({ message: __("Opportunity context loaded. {0} item(s) available.", [(source.items || []).length]), indicator: "blue" });
        } catch (error) {
            frappe.msgprint({ title: __("Opportunity failed"), message: error.message || __("Unable to load Opportunity context."), indicator: "red" });
        }
        render(page);
    }

    function normalizeSourceLine(line) {
        return {
            ...line,
            qty: Number(line.qty || 1) || 1,
            show_in_detail: 1,
            line_type: line.line_type || "Standard",
        };
    }

    async function updateLineItemName(page, line, itemCode) {
        if (!itemCode) {
            line.item_name = "";
            render(page);
            return;
        }
        const expectedItem = itemCode;
        const res = await frappe.db.get_value("Item", itemCode, "item_name");
        if ((line.item || "") !== expectedItem) return;
        line.item_name = (res.message || {}).item_name || itemCode;
        render(page);
    }

    async function save(page, options = {}) {
        if (STATE.saving) return;
        STATE.saving = true;
        let ok = false;
        if (!options.silent) render(page);
        try {
            const res = await frappe.call({
                method: "orderlift.orderlift_sales.page.pricing_sheet_builder.pricing_sheet_builder.save_pricing_sheet_builder_payload",
                args: { payload: JSON.stringify(payloadForSave()) },
                freeze: options.freeze !== false,
            });
            STATE.sheet = { ...blankSheet(), ...((res.message || {}).sheet || {}) };
            STATE.sheet.pricing_mode = resolvePricingMode(STATE.sheet);
            ensurePriceListMappingTable();
            STATE.dimensioningValues = parseDimensioningValues();
            syncRouteAfterSave(STATE.sheet.name || (res.message || {}).name);
            ok = true;
            if ((res.message || {}).link_warning) {
                frappe.show_alert({ message: (res.message || {}).link_warning, indicator: "orange" });
            }
            if (!options.silent) frappe.show_alert({ message: __("Pricing Sheet saved"), indicator: "green" });
        } catch (error) {
            if (options.silent) {
                console.warn("Pricing Sheet auto pricing skipped", error);
            } else {
                frappe.msgprint({ title: __("Save Failed"), message: error.message || __("Unable to save Pricing Sheet."), indicator: "red" });
            }
        } finally {
            STATE.saving = false;
            render(page);
        }
        return ok;
    }

    function payloadForSave() {
        const sheet = { ...STATE.sheet };
        const mode = resolvePricingMode(sheet);
        sheet.pricing_mode = mode;
        sheet.output_mode = "Avec details";
        sheet.lines = (STATE.sheet.lines || []).map((line) => ({ ...line, show_in_detail: 1 }));
        sheet.pricing_scenario = "";
        sheet.customs_policy = "";
        sheet.user_context = undefined;
        sheet.history = undefined;
        sheet.quotation_preview = undefined;
        sheet.source_quotation = STATE.sheet.source_quotation || "";
        sheet.link_source_quotation = STATE.sheet.link_source_quotation ? 1 : 0;
        if (mode === "Dynamic") {
            sheet.selected_price_list = "";
            sheet.benchmark_policy = "";
        } else if (!activeStaticSellingPriceLists().length) {
            ensureStaticSellingPriceLists();
            sheet.selected_selling_price_lists = selectedSellingPriceLists(STATE.sheet);
            sheet.selected_price_list = firstActiveSellingPriceList();
        }
        sheet.scenario_mappings = mode === "Dynamic" ? (STATE.sheet.scenario_mappings || []).map((mapping) => ({
            ...mapping,
            business_type: "",
            crm_segment: "",
        })) : [];
        sheet.dimensioning_inputs_json = JSON.stringify(STATE.dimensioningValues || parseDimensioningValues() || {});
        return sheet;
    }

    function defaultPolicyMapping() {
        return {
            source_buying_price_list: "",
            pricing_scenario: "",
            customs_policy: "",
            benchmark_policy: "",
            business_type: "",
            crm_segment: "",
            priority: 10,
            is_active: 1,
            notes: STATE.sheet.scenario_mappings?.length ? "" : __("Fallback mapping"),
        };
    }

    function ensureLineClientIds() {
        STATE.sheet.lines = STATE.sheet.lines || [];
        STATE.sheet.lines.forEach((line, index) => {
            if (!line._client_id) line._client_id = line.name || `line-${Date.now()}-${index}-${Math.random().toString(36).slice(2, 8)}`;
        });
    }

    function lineKey(row, index) {
        return row?._client_id || row?.name || `line-${index}`;
    }

    function selectedLineCount() {
        pruneSelectedLineKeys();
        return STATE.selectedLineKeys.size;
    }

    function pruneSelectedLineKeys() {
        const valid = new Set((STATE.sheet.lines || []).map((line, index) => lineKey(line, index)));
        Array.from(STATE.selectedLineKeys || []).forEach((key) => {
            if (!valid.has(key)) STATE.selectedLineKeys.delete(key);
        });
    }

    function confirmDeleteSelectedLines(page) {
        pruneSelectedLineKeys();
        const count = STATE.selectedLineKeys.size;
        if (!count) return;
        frappe.confirm(__("Delete {0} selected line(s)?", [count]), () => {
            deleteSelectedLines();
            render(page);
            scheduleAutoPrice(page);
        });
    }

    function deleteSelectedLines() {
        const selected = new Set(STATE.selectedLineKeys || []);
        STATE.sheet.lines = (STATE.sheet.lines || []).filter((line, index) => !selected.has(lineKey(line, index)));
        STATE.selectedLineKeys.clear();
    }

    function deleteLinesByIndex(indexes) {
        const remove = new Set(indexes || []);
        STATE.sheet.lines = (STATE.sheet.lines || []).filter((line, index) => !remove.has(index));
        pruneSelectedLineKeys();
    }

    function ensurePriceListMappingTable() {
        STATE.sheet.scenario_mappings = STATE.sheet.scenario_mappings || [];
        STATE.sheet.selected_selling_price_lists = selectedSellingPriceLists(STATE.sheet);
        STATE.sheet.selected_price_list = firstActiveSellingPriceList();
    }

    function ensureStaticSellingPriceLists() {
        STATE.sheet.selected_selling_price_lists = selectedSellingPriceLists(STATE.sheet);
        if (STATE.sheet.selected_selling_price_lists.some((row) => Number(row.is_active ?? 1) && row.price_list)) {
            STATE.sheet.selected_price_list = firstActiveSellingPriceList();
            return;
        }
        const fallback = availableStaticSellingPriceLists()[0] || "";
        if (!fallback) return;
        STATE.sheet.selected_selling_price_lists = [{ price_list: fallback, sequence: 10, is_active: 1 }];
        STATE.sheet.selected_price_list = fallback;
    }

    function selectedSellingPriceLists(sheet) {
        const rows = [];
        const seen = new Set();
        (sheet?.selected_selling_price_lists || []).forEach((row, index) => {
            const priceList = String(row.price_list || "").trim();
            const key = priceList || `__blank_${index}`;
            if (priceList && seen.has(priceList)) return;
            if (priceList) seen.add(priceList);
            rows.push({
                price_list: priceList,
                sequence: Number(row.sequence || (index + 1) * 10),
                is_active: Number(row.is_active ?? 1) ? 1 : 0,
            });
        });
        const legacy = String(sheet?.selected_price_list || "").trim();
        if (legacy && !seen.has(legacy)) rows.push({ price_list: legacy, sequence: rows.length * 10 + 10, is_active: 1 });
        rows.sort((a, b) => Number(a.sequence || 0) - Number(b.sequence || 0));
        return rows;
    }

    function activeStaticSellingPriceLists() {
        const selected = selectedSellingPriceLists(STATE.sheet)
            .filter((row) => Number(row.is_active ?? 1) && row.price_list)
            .map((row) => row.price_list);
        if (selected.length) return selected;
        return availableStaticSellingPriceLists();
    }

    function availableStaticSellingPriceLists() {
        const agentLists = (STATE.sheet?.user_context?.selling_price_lists || []).filter(Boolean);
        if (agentLists.length) return agentLists;
        return (STATE.sheet?.user_context?.all_selling_price_lists || []).filter(Boolean);
    }

    function activeDynamicBuyingPriceLists(line) {
        const lineList = String(line?.source_buying_price_list || "").trim();
        if (lineList) return [lineList];
        const seen = new Set();
        const lists = [];
        (STATE.sheet.scenario_mappings || []).forEach((row) => {
            if (!Number(row.is_active ?? 1)) return;
            const priceList = String(row.source_buying_price_list || "").trim();
            if (!priceList || seen.has(priceList)) return;
            seen.add(priceList);
            lists.push(priceList);
        });
        return lists.length ? lists : (STATE.sheet?.user_context?.allowed_buying_price_lists || []).filter(Boolean);
    }

    function firstActiveSellingPriceList() {
        return activeStaticSellingPriceLists()[0] || "";
    }

    function resolvePricingMode(sheet) {
        const agentMode = sheet?.user_context?.agent_pricing_mode || "";
        if (isRestrictedAgent() && agentMode) return agentMode === sheet?.user_context?.static_pricing_mode ? "Static" : "Dynamic";
        const mode = (sheet?.pricing_mode || "").trim();
        if (mode === "Static" || mode === "Dynamic") return mode;
        if ((sheet?.resolved_mode || "") === "Static" || ((sheet?.selected_price_list || (sheet?.selected_selling_price_lists || []).length) && !(sheet?.scenario_mappings || []).length)) return "Static";
        return "Dynamic";
    }

    function activeLineColumns() {
        if (isRestrictedAgent()) return AGENT_LINE_COLUMNS.map((key) => LINE_COLUMNS.find((column) => column.key === key)).filter(Boolean);
        const columns = normalizeLineColumns(STATE.lineColumns || defaultLineColumns());
        const modeColumns = isStaticPricingMode()
            ? columns.map((key) => key === "buy_price" ? "static_list_price" : key)
            : columns;
        return modeColumns
            .filter((key) => !isStaticPricingMode() || !STATIC_MODE_HIDDEN_COLUMNS.has(key))
            .filter((key) => canViewSensitivePricing() || !SENSITIVE_PRICING_COLUMNS.has(key))
            .filter((key, index) => modeColumns.indexOf(key) === index)
            .map((key) => LINE_COLUMNS.find((column) => column.key === key))
            .filter(Boolean);
    }

    function defaultLineColumns() {
        if (isRestrictedAgent()) return AGENT_LINE_COLUMNS.slice();
        if (isStaticPricingMode()) return ADMIN_STATIC_LINE_COLUMNS.slice();
        return DEFAULT_LINE_COLUMNS.slice();
    }

    function availableLineColumns() {
        return LINE_COLUMNS.filter((column) => {
            if (isRestrictedAgent() && !AGENT_LINE_COLUMNS.includes(column.key)) return false;
            if (!canViewSensitivePricing() && SENSITIVE_PRICING_COLUMNS.has(column.key)) return false;
            return true;
        });
    }

    function isRestrictedAgent() {
        return Boolean(STATE.sheet?.user_context?.is_restricted_agent);
    }

    function canViewSensitivePricing() {
        return Boolean(STATE.sheet?.user_context?.can_view_sensitive_pricing);
    }

    function isStaticPricingMode() {
        return resolvePricingMode(STATE.sheet) === "Static";
    }

    function resolveMaxDiscount(row) {
        return Number(row.max_discount_percent_allowed || 0);
    }

    function unusedDiscountPercent(row) {
        return Math.max(resolveMaxDiscount(row) - Number(row.discount_percent || 0), 0);
    }

    function manualOverrideFloor(row) {
        const reference = Number(row.projected_unit_price || row.static_list_price || 0);
        if (!reference) return 0;
        return reference * (1 - (resolveMaxDiscount(row) / 100));
    }

    function lineCostUnit(row) {
        if (isStaticPricingMode()) {
            const projected = Number(row.projected_unit_price || 0);
            return projected || Number(row.final_sell_unit_price || 0) || staticBaseUnit(row);
        }
        return Number(row.buy_price || 0)
            + Number(row.expense_unit_price || 0)
            + Number(row.customs_unit_amount || 0);
    }

    function lineCostTotal(row) {
        const qty = Number(row.qty || 0);
        if (isStaticPricingMode()) {
            const projected = Number(row.projected_total_price || 0);
            return projected || lineCostUnit(row) * qty;
        }
        const base = row.base_amount == null ? Number(row.buy_price || 0) * qty : Number(row.base_amount || 0);
        const expenses = row.expense_total == null ? Number(row.expense_unit_price || 0) * qty : Number(row.expense_total || 0);
        return base + expenses + Number(row.customs_applied || 0);
    }

    function staticBaseUnit(row) {
        return Number(row.static_list_price || 0);
    }

    function staticBaseTotal(row) {
        return staticBaseUnit(row) * Number(row.qty || 0);
    }

    function staticModifierUnit(row) {
        return lineCostUnit(row) - staticBaseUnit(row);
    }

    function totalMarginUnit(row) {
        return Number(row.margin_unit_amount || 0)
            + Number(row.tier_modifier_amount || 0)
            + Number(row.zone_modifier_amount || 0);
    }

    function staticModifierTotal(row) {
        return staticModifierUnit(row) * Number(row.qty || 0);
    }

    function openColumnDialog(page) {
        const selected = new Set(isRestrictedAgent() ? AGENT_LINE_COLUMNS : (STATE.lineColumns || defaultLineColumns()));
        const dialog = new frappe.ui.Dialog({
            title: __("Line Table Columns"),
            fields: [{ fieldtype: "HTML", fieldname: "columns_html" }],
            primary_action_label: __("Apply"),
            primary_action: () => {
                const ordered = [];
                dialog.$wrapper.find("[data-column-key]").each((_, row) => {
                    const key = row.getAttribute("data-column-key");
                    const column = availableLineColumns().find((item) => item.key === key);
                    const checked = row.querySelector("input")?.checked;
                    if (column?.mandatory || checked) ordered.push(key);
                });
                STATE.lineColumns = ordered.length ? ordered : defaultLineColumns();
                saveLineColumns(STATE.lineColumns);
                dialog.hide();
                render(page);
            },
        });
        dialog.show();
        const html = orderedColumnOptions(selected).map((column) => `
            <div class="psb-column-option" draggable="${column.mandatory ? "false" : "true"}" data-column-key="${escapeHtml(column.key)}">
                <span class="psb-drag-handle">${column.mandatory ? "" : "::"}</span>
                <label><input type="checkbox" ${column.mandatory || selected.has(column.key) ? "checked" : ""} ${column.mandatory ? "disabled" : ""}> ${escapeHtml(__(column.label))}</label>
            </div>`).join("");
        dialog.fields_dict.columns_html.$wrapper.html(`<div class="psb-column-list">${html}</div>`);
        bindColumnDrag(dialog.fields_dict.columns_html.$wrapper);
    }

    function orderedColumnOptions(selected) {
        const known = new Set();
        const ordered = [];
        (STATE.lineColumns || []).forEach((key) => {
            const column = availableLineColumns().find((item) => item.key === key);
            if (column && !known.has(key)) {
                known.add(key);
                ordered.push(column);
            }
        });
        availableLineColumns().forEach((column) => {
            if (!known.has(column.key)) ordered.push(column);
        });
        return ordered.filter((column) => column.mandatory || selected.has(column.key) || !selected.has(column.key));
    }

    function bindColumnDrag(wrapper) {
        let dragged = null;
        wrapper.find("[data-column-key]").on("dragstart", function (event) {
            dragged = this;
            event.originalEvent.dataTransfer.effectAllowed = "move";
        });
        wrapper.find("[data-column-key]").on("dragover", function (event) {
            event.preventDefault();
            if (!dragged || dragged === this) return;
            const rect = this.getBoundingClientRect();
            const after = event.originalEvent.clientY > rect.top + rect.height / 2;
            this.parentNode.insertBefore(dragged, after ? this.nextSibling : this);
        });
        wrapper.find("[data-column-key]").on("dragend", () => { dragged = null; });
    }

    function openBulkQuantityDialog(page) {
        pruneSelectedLineKeys();
        const selected = Array.from(STATE.selectedLineKeys || []);
        if (!selected.length) return;

        const dialog = new frappe.ui.Dialog({
            title: __("Apply Quantity to Selected Items"),
            fields: [
                {
                    fieldname: "qty",
                    fieldtype: "Float",
                    label: __("Quantity"),
                    reqd: 1,
                    default: 1,
                    description: __("This will update {0} selected item row(s).", [selected.length]),
                },
            ],
            primary_action_label: __("Apply Quantity"),
            primary_action(values) {
                const qty = Number(values.qty || 0);
                if (qty > 0) {
                    const selectedSet = new Set(selected);
                    (STATE.sheet.lines || []).forEach((line, index) => {
                        if (selectedSet.has(lineKey(line, index))) {
                            line.qty = qty;
                        }
                    });
                    STATE.selectedLineKeys.clear();
                    render(page);
                    scheduleAutoPrice(page);
                }
                dialog.hide();
            },
        });
        dialog.show();
    }

    function openOpportunityItemsDialog(page) {
        if (!STATE.sheet.opportunity) {
            frappe.msgprint({
                title: __("Choose Opportunity"),
                message: __("Select an Opportunity in Setup before loading its items."),
                indicator: "orange",
            });
            STATE.active = "setup";
            render(page);
            return;
        }
        const dialog = new frappe.ui.Dialog({
            title: __("Load Opportunity Items"),
            fields: [
                {
                    fieldname: "replace_existing",
                    fieldtype: "Check",
                    label: __("Replace existing Pricing Sheet lines"),
                    default: 0,
                    description: __("Leave unchecked to append Opportunity items to the current lines."),
                },
            ],
            primary_action_label: __("Load Items"),
            primary_action: async (values) => {
                if (!(await save(page)) || !STATE.sheet.name) return;
                const res = await frappe.call({
                    method: "orderlift.orderlift_sales.page.pricing_sheet_builder.pricing_sheet_builder.import_opportunity_items_to_pricing_sheet",
                    args: {
                        pricing_sheet: STATE.sheet.name,
                        opportunity: STATE.sheet.opportunity,
                        replace_existing: values.replace_existing ? 1 : 0,
                        pricing_mode: resolvePricingMode(STATE.sheet),
                    },
                    freeze: true,
                });
                STATE.sheet = { ...blankSheet(), ...((res.message || {}).sheet || {}) };
                STATE.sheet.pricing_mode = resolvePricingMode(STATE.sheet);
                ensurePriceListMappingTable();
                ensureLineClientIds();
                dialog.hide();
                STATE.active = "items";
                render(page);
                frappe.show_alert({ message: __("Loaded {0} Opportunity item(s)", [(res.message || {}).imported_count || 0]), indicator: "green" });
            },
        });
        dialog.show();
    }

    function openAddMultipleDialog(page) {
        const dialog = new frappe.ui.Dialog({
            title: __("Add Multiple Items"),
            fields: [
                {
                    fieldname: "source_type",
                    fieldtype: "Select",
                    label: __("Add items from"),
                    options: "Filter & Select\nPrice List\nItem Group",
                    default: "Filter & Select",
                },
                {
                    fieldname: "item_group",
                    fieldtype: "Link",
                    options: "Item Group",
                    label: __("Item Group"),
                    depends_on: "eval:doc.source_type==='Item Group'",
                },
                {
                    fieldname: "price_list",
                    fieldtype: "Link",
                    options: "Price List",
                    label: __("Price List"),
                    depends_on: "eval:doc.source_type==='Price List'",
                    get_query: isStaticPricingMode() ? (() => {
                        const allowed = activeStaticSellingPriceLists();
                        return allowed.length ? { filters: [["Price List", "name", "in", allowed]] } : {};
                    }) : undefined,
                }
            ],
            primary_action_label: __("Get Items"),
            primary_action(values) {
                dialog.hide();
                if (values.source_type === "Price List" && values.price_list) {
                    frappe.call({
                        method: "frappe.client.get_list",
                        args: {
                            doctype: "Item Price",
                            filters: { price_list: values.price_list },
                            fields: ["item_code"],
                            limit_page_length: 500
                        },
                        callback: function(r) {
                            if (r.message && r.message.length) {
                                const item_codes = [...new Set(r.message.map(row => row.item_code))];
                                insertMultipleItems(page, item_codes);
                            } else {
                                frappe.msgprint(__("No items found in Price List: {0}", [values.price_list]));
                            }
                        }
                    });
                } else {
                    const staticPriceLists = isStaticPricingMode() ? activeStaticSellingPriceLists() : [];
                    if (isStaticPricingMode() && !staticPriceLists.length) {
                        frappe.msgprint({
                            title: __("Choose Selling Price Lists"),
                            message: __("Select at least one active Selling Price List in Setup before adding static items."),
                            indicator: "orange",
                        });
                        return;
                    }
                    const itemSelector = new frappe.ui.form.MultiSelectDialog({
                        doctype: "Item",
                        target: page.main,
                        setters: {
                            item_group: values.item_group || undefined
                        },
                        get_query: isStaticPricingMode() ? (() => ({
                            query: "orderlift.orderlift_sales.doctype.pricing_sheet.pricing_sheet.priced_item_query",
                            filters: {
                                price_lists: staticPriceLists,
                                buying: 0,
                                item_group: values.item_group || "",
                            },
                        })) : undefined,
                        add_filters_group: 1,
                        action(selections) {
                            if (selections && selections.length) {
                                insertMultipleItems(page, selections);
                            }
                            itemSelector.dialog.hide();
                        }
                    });
                }
            }
        });
        dialog.show();
    }

    async function insertMultipleItems(page, itemCodes) {
        if (!itemCodes || !itemCodes.length) return;
        frappe.show_alert({ message: __("Adding {0} items...", [itemCodes.length]), indicator: "blue" });
        STATE.sheet.lines = STATE.sheet.lines || [];
        
        // Chunk API requests to not overload DB if huge amount
        const chunks = [];
        for (let i = 0; i < itemCodes.length; i += 50) {
            chunks.push(itemCodes.slice(i, i + 50));
        }

        for (const chunk of chunks) {
            const res = await frappe.call({
                method: "frappe.client.get_list",
                args: {
                    doctype: "Item",
                    filters: { name: ["in", chunk] },
                    fields: ["name", "item_name"]
                }
            });
            const nameMap = {};
            if (res.message) {
                res.message.forEach(row => { nameMap[row.name] = row.item_name; });
            }
            
            for (const itemCode of chunk) {
                STATE.sheet.lines.push({ 
                    item: itemCode, 
                    item_name: nameMap[itemCode] || itemCode, 
                    qty: 1, 
                    display_group: "", 
                    show_in_detail: 1, 
                    line_type: "Standard" 
                });
            }
        }

        STATE.active = "items";
        render(page);
        scheduleAutoPrice(page);
        frappe.show_alert({ message: __("Successfully added {0} items.", [itemCodes.length]), indicator: "green" });
    }

    async function openBundleDialog(page) {
        const dialog = new frappe.ui.Dialog({
            title: __("Add from Bundle"),
            fields: [
                { label: __("Product Bundle"), fieldname: "product_bundle", fieldtype: "Link", options: "Product Bundle", reqd: 1 },
                { label: __("Multiplier"), fieldname: "multiplier", fieldtype: "Float", default: 1 },
                { label: __("Replace Existing Lines"), fieldname: "replace_existing_lines", fieldtype: "Check", default: 0 },
                { label: __("Display Group Source"), fieldname: "default_display_group_source", fieldtype: "Select", options: "Item Group\nBundle Name", default: "Item Group" },
                { label: __("Line Mode"), fieldname: "line_mode", fieldtype: "Select", options: "Exploded\nBundle Single\nBoth", default: "Exploded" },
            ],
            primary_action_label: __("Add Bundle"),
            primary_action: async (values) => {
                if (!(await save(page)) || !STATE.sheet.name) return;
                const res = await frappe.call({
                    method: "orderlift.orderlift_sales.page.pricing_sheet_builder.pricing_sheet_builder.add_bundle_to_pricing_sheet",
                    args: { pricing_sheet: STATE.sheet.name, options: JSON.stringify({ ...(values || {}), pricing_mode: resolvePricingMode(STATE.sheet) }) },
                    freeze: true,
                });
                STATE.sheet = { ...blankSheet(), ...((res.message || {}).sheet || {}) };
                STATE.sheet.pricing_mode = resolvePricingMode(STATE.sheet);
                ensurePriceListMappingTable();
                dialog.hide();
                render(page);
                frappe.show_alert({ message: __("Bundle imported"), indicator: "green" });
            },
        });
        dialog.show();
    }

    async function loadDimensioningConfig(page, rerender) {
        if (!STATE.sheet.dimensioning_set) {
            STATE.dimensioning = null;
            if (rerender) render(page);
            return;
        }
        try {
            const res = await frappe.call({
                method: "orderlift.orderlift_sales.doctype.dimensioning_set.dimensioning_set.get_dimensioning_set_payload",
                args: { set_name: STATE.sheet.dimensioning_set },
            });
            STATE.dimensioning = (res.message || {}).set;
            STATE.dimensioningValues = normalizeDimensioningValues(STATE.dimensioning, parseDimensioningValues());
            STATE.sheet.dimensioning_inputs_json = JSON.stringify(STATE.dimensioningValues || {});
            if (hasDimensioningRules()) {
                await previewDimensioning(page, { render: false, freeze: false, collect: false });
                STATE.dimensioningPreviewCollapsed = true;
            }
        } catch (error) {
            console.error("Dimensioning config failed", error);
            STATE.dimensioning = null;
        }
        if (rerender) render(page);
    }

    async function previewDimensioning(page, options = {}) {
        if (!STATE.sheet.dimensioning_set) return;
        if (options.collect !== false) collectDimensioningValues(page);
        const res = await frappe.call({
            method: "orderlift.orderlift_sales.doctype.dimensioning_set.dimensioning_set.preview_dimensioning_set",
            args: { set_name: STATE.sheet.dimensioning_set, input_values_json: JSON.stringify(STATE.dimensioningValues || {}) },
            freeze: options.freeze !== false,
        });
        STATE.dimensioningPreview = (res.message || {}).items || [];
        if (options.expand) STATE.dimensioningPreviewCollapsed = false;
        if (options.showEmptyMessage && !STATE.dimensioningPreview.length) {
            frappe.show_alert({ message: __("No generated articles matched the current inputs."), indicator: "orange" });
        }
        if (options.render !== false) render(page);
    }

    function scheduleDimensioningPreview(page) {
        clearTimeout(dimensioningPreviewTimer);
        if (!STATE.sheet.dimensioning_set || !hasDimensioningRules()) return;
        dimensioningPreviewTimer = setTimeout(() => {
            previewDimensioning(page, { freeze: false }).catch((error) => console.error("Dimensioning preview failed", error));
        }, 350);
    }

    function hasDimensioningRules() {
        return ((STATE.dimensioning || {}).rule_groups || []).some((group) => (group.articles || []).length);
    }

    async function addDimensioning(page) {
        collectDimensioningValues(page);
        if (!(await save(page)) || !STATE.sheet.name) return;
        const res = await frappe.call({
            method: "orderlift.orderlift_sales.page.pricing_sheet_builder.pricing_sheet_builder.add_dimensioning_to_pricing_sheet",
            args: {
                pricing_sheet: STATE.sheet.name,
                dimensioning_set: STATE.sheet.dimensioning_set,
                input_values_json: JSON.stringify(STATE.dimensioningValues || {}),
                replace_existing_generated: 1,
                pricing_mode: resolvePricingMode(STATE.sheet),
            },
            freeze: true,
        });
        STATE.sheet = { ...blankSheet(), ...((res.message || {}).sheet || {}) };
        STATE.sheet.pricing_mode = resolvePricingMode(STATE.sheet);
        ensurePriceListMappingTable();
        STATE.dimensioningValues = parseDimensioningValues();
        frappe.show_alert({ message: __("Dimensioning lines added"), indicator: "green" });
        render(page);
    }

    async function generateQuotation(page) {
        if (!(await save(page)) || !STATE.sheet.name) return;
        frappe.confirm(__("Generate the Quotation now?"), async () => {
            const res = await frappe.call({
                method: "orderlift.orderlift_sales.page.pricing_sheet_builder.pricing_sheet_builder.generate_builder_quotation",
                args: { pricing_sheet: STATE.sheet.name, pricing_mode: resolvePricingMode(STATE.sheet) },
                freeze: true,
            });
            const quotation = (res.message || {}).quotation;
            if (quotation) {
                frappe.show_alert({ message: __("Quotation {0} created", [quotation]), indicator: "green" });
                frappe.set_route("Form", "Quotation", quotation);
            }
        });
    }

    function confirmDeletePricingSheet(page) {
        const sheetName = STATE.sheet.name;
        if (!sheetName) {
            frappe.msgprint({
                title: __("Nothing to delete"),
                message: __("Save or load a Pricing Sheet before deleting it."),
                indicator: "orange",
            });
            return;
        }
        frappe.confirm(
            __("Delete Pricing Sheet {0}? This cannot be undone.", [sheetName]),
            async () => {
                try {
                    await frappe.call({
                        method: "orderlift.orderlift_sales.page.pricing_sheet_builder.pricing_sheet_builder.delete_pricing_sheet_builder",
                        args: { pricing_sheet: sheetName },
                        freeze: true,
                    });
                    frappe.show_alert({ message: __("Pricing Sheet deleted"), indicator: "green" });
                    frappe.set_route("pricing-sheet-manager");
                } catch (error) {
                    frappe.msgprint({
                        title: __("Delete failed"),
                        message: error.message || __("Unable to delete this Pricing Sheet."),
                        indicator: "red",
                    });
                }
            }
        );
    }

    function collectDimensioningValues(page) {
        const values = {};
        page.main.find("[data-dim-key]").each((_, input) => {
            const key = input.getAttribute("data-dim-key");
            values[key] = input.type === "checkbox" ? input.checked : input.value;
        });
        STATE.dimensioningValues = values;
        STATE.sheet.dimensioning_inputs_json = JSON.stringify(values || {});
        return values;
    }

    function parseDimensioningValues() {
        try {
            const parsed = JSON.parse(STATE.sheet.dimensioning_inputs_json || "{}");
            return parsed && typeof parsed === "object" ? parsed : {};
        } catch (error) {
            return {};
        }
    }

    function normalizeDimensioningValues(config, current) {
        const values = { ...(current || {}) };
        ((config || {}).fields || []).forEach((field) => {
            if (values[field.field_key] !== undefined) return;
            if (String(field.field_type || "").toLowerCase() === "check") {
                values[field.field_key] = [1, true, "1", "true", "yes", "on"].includes(field.default_value);
            } else {
                values[field.field_key] = field.default_value || "";
            }
        });
        return values;
    }

    function textField(fieldname, label, value, required) {
        return `<label class="psb-field"><span>${escapeHtml(label)}${required ? " *" : ""}</span><input data-sheet-field="${fieldname}" value="${escapeHtml(value || "")}"></label>`;
    }

    function linkField(fieldname, label, options, value, required, readOnly = false) {
        return `<label class="psb-field"><span>${escapeHtml(label)}${required ? " *" : ""}</span><div data-link-field="${fieldname}" data-options="${escapeHtml(options)}" data-value="${escapeHtml(value || "")}" data-read-only="${readOnly ? 1 : 0}"></div></label>`;
    }

    function selectField(fieldname, label, value, options) {
        return `<label class="psb-field"><span>${escapeHtml(label)}</span><select data-sheet-field="${fieldname}">${(options || []).map((option) => `<option value="${escapeHtml(option)}" ${option === value ? "selected" : ""}>${escapeHtml(__(option))}</option>`).join("")}</select></label>`;
    }

    function metric(label, value, tone) {
        return `<div class="psb-metric ${tone || ""}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value == null ? "-" : String(value))}</strong></div>`;
    }

    function marginMetric(basis, pct) {
        const options = ["Base Price", "Loaded Cost", "Sale Price"];
        return `<div class="psb-metric psb-margin-metric"><span>${escapeHtml(__("Margin"))}</span><strong>
            <select class="psb-margin-basis-select" data-sheet-field="margin_basis" style="font-size:11px;font-weight:500;border:none;background:transparent;cursor:pointer;color:var(--ink-1000);max-width:110px;">
                ${options.map((opt) => `<option value="${escapeHtml(opt)}" ${opt === basis ? "selected" : ""}>${escapeHtml(opt)}</option>`).join("")}
            </select>
            <span class="psb-margin-value">${escapeHtml(pct.toFixed(1))}%</span>
        </strong></div>`;
    }

    function quoteMetric(label, value) {
        return `<div class="psb-quote-metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value == null ? "-" : String(value))}</strong></div>`;
    }

    function skeleton() {
        return `<div class="psb-skeleton"></div><div class="psb-skeleton small"></div>`;
    }

    function loadLineColumns() {
        try {
            const raw = window.localStorage?.getItem(lineColumnStorageKey());
            const parsed = raw ? JSON.parse(raw) : null;
            if (Array.isArray(parsed) && parsed.length) return normalizeLineColumns(parsed);
        } catch (error) {
            // Local preference only; ignore storage failures.
        }
        return defaultLineColumns();
    }

    function normalizeLineColumns(columns) {
        const aliases = { final: "final_sell_total", detail: "" };
        const available = new Set(availableLineColumns().map((column) => column.key));
        const normalized = [];
        (columns || []).forEach((key) => {
            const nextKey = aliases[key] || key;
            if (available.has(nextKey) && !normalized.includes(nextKey)) normalized.push(nextKey);
        });
        LINE_COLUMNS.filter((column) => column.mandatory).forEach((column) => {
            if (!normalized.includes(column.key)) normalized.push(column.key);
        });
        return normalized.length ? normalized : defaultLineColumns();
    }

    function saveLineColumns(columns) {
        try {
            window.localStorage?.setItem(lineColumnStorageKey(), JSON.stringify(normalizeLineColumns(columns || defaultLineColumns())));
        } catch (error) {
            // Local preference only; ignore storage failures.
        }
    }

    function lineColumnStorageKey() {
        if (isRestrictedAgent()) return `${COLUMN_STORAGE_KEY_PREFIX}.agent`;
        return `${COLUMN_STORAGE_KEY_PREFIX}.admin.${isStaticPricingMode() ? "static" : "dynamic"}`;
    }

    function formatCurrency(value) {
        return window.orderlift?.formatCurrency ? window.orderlift.formatCurrency(value) : textFromHtml(frappe.format(Number(value || 0), { fieldtype: "Currency" }));
    }

    function formatDateTime(value) {
        if (!value) return "-";
        try {
            return frappe.datetime.prettyDate(String(value).split(".")[0]);
        } catch (error) {
            return String(value);
        }
    }

    function textFromHtml(value) {
        const wrapper = document.createElement("div");
        wrapper.innerHTML = String(value == null ? "" : value);
        return (wrapper.textContent || wrapper.innerText || "").trim();
    }

    function escapeHtml(value) {
        return frappe.utils.escape_html(String(value == null ? "" : value));
    }

    function injectStyles() {
        if (document.getElementById("psb-style")) return;
        const style = document.createElement("style");
        style.id = "psb-style";
        style.textContent = `
            @import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;450;500;600;700&family=Geist+Mono:wght@400;500&display=swap');
            .psb-root{--canvas:#FAFBFC;--canvas-2:#F4F6F8;--surface:#FFFFFF;--surface-2:#F7F8FA;--surface-3:#F0F2F5;--ink-1000:#0A0E1A;--ink-900:#11151F;--ink-800:#1F2433;--ink-700:#2E3548;--ink-600:#495061;--ink-500:#6B7280;--ink-400:#9099A6;--ink-300:#B8BFC9;--ink-200:#DDE1E7;--ink-150:#E8EBEF;--ink-100:#EFF1F4;--primary-700:#3730A3;--primary-600:#4F46E5;--primary-500:#6366F1;--primary-100:#E0E7FF;--primary-50:#EEF2FF;--success-700:#047857;--success-500:#10B981;--success-100:#D1FAE5;--success-50:#ECFDF5;--info-700:#0369A1;--info-100:#E0F2FE;--info-50:#F0F9FF;--accent-700:#6D28D9;--accent-600:#7C3AED;--accent-100:#EDE9FE;--accent-50:#F5F3FF;--rose-700:#BE123C;--rose-100:#FFE4E6;--rose-50:#FFF1F2;--font-sans:'Geist',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;--font-mono:'Geist Mono','SF Mono',Menlo,monospace;--r-lg:14px;--r-2xl:22px;--shadow-xs:0 1px 2px rgba(15,23,42,.04);--shadow-sm:0 1px 2px rgba(15,23,42,.04),0 2px 4px rgba(15,23,42,.04);--shadow-md:0 2px 4px rgba(15,23,42,.04),0 4px 12px rgba(15,23,42,.05);--shadow-lg:0 4px 8px rgba(15,23,42,.04),0 16px 32px -8px rgba(15,23,42,.08);--ease:cubic-bezier(.32,.72,0,1);background:radial-gradient(circle at 20% 0%,rgba(99,102,241,.05) 0%,transparent 50%),radial-gradient(circle at 80% 30%,rgba(124,58,237,.03) 0%,transparent 50%),linear-gradient(to bottom,var(--canvas) 0%,var(--canvas-2) 100%);color:var(--ink-900);font-family:var(--font-sans);font-feature-settings:'cv11','ss01','ss03';-webkit-font-smoothing:antialiased;overflow-x:hidden}.psb-root *,.psb-root *::before,.psb-root *::after{box-sizing:border-box}.psb-root button,.psb-root input,.psb-root select,.psb-root textarea{font-family:inherit}.psb-root button{cursor:pointer}
            .psb-shell{max-width:1520px;margin:0 auto;min-height:calc(100vh - 56px);padding:24px 24px 104px;display:grid;gap:18px;color:var(--ink-900)}.psb-breadcrumb{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--ink-500);font-family:var(--font-mono)}.psb-breadcrumb a{color:var(--ink-500);text-decoration:none}.psb-breadcrumb a:hover{color:var(--ink-800)}.psb-breadcrumb .sep{color:var(--ink-300)}.psb-breadcrumb .current{color:var(--ink-800);font-weight:500}
            .psb-hero{position:relative;display:grid;grid-template-columns:minmax(0,1fr) minmax(420px,.9fr);gap:32px;align-items:center;border:1px solid var(--ink-150);border-radius:var(--r-2xl);background:var(--surface);color:var(--ink-1000);padding:28px 32px;box-shadow:var(--shadow-md);overflow:hidden}.psb-hero::before{content:'';position:absolute;top:0;right:0;width:60%;height:100%;background:radial-gradient(ellipse at top right,rgba(99,102,241,.06) 0%,transparent 60%);pointer-events:none}.psb-hero::after{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,rgba(99,102,241,.4) 30%,rgba(124,58,237,.4) 70%,transparent)}.psb-hero>div{position:relative;z-index:1}.psb-eyebrow{display:inline-flex;align-items:center;gap:8px;padding:5px 12px;background:var(--primary-50);border:1px solid var(--primary-100);border-radius:999px;color:var(--primary-700);font-size:11px;font-weight:500;letter-spacing:.01em;margin-bottom:14px;text-transform:none}.psb-hero h1{margin:0 0 8px;color:var(--ink-1000);font-size:28px;font-weight:600;line-height:1.15;letter-spacing:-.025em}.psb-hero p{margin:0;color:var(--ink-500);font-size:14px;font-weight:400;line-height:1.55;max-width:640px}.psb-hero-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.psb-metric{position:relative;min-height:86px;border:1px solid var(--ink-150);border-radius:var(--r-lg);background:var(--surface);padding:14px;display:grid;align-content:center;gap:6px;box-shadow:var(--shadow-xs);overflow:hidden;transition:all .25s var(--ease)}.psb-metric::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--primary-500)}.psb-metric:hover{transform:translateY(-2px);box-shadow:var(--shadow-md)}.psb-metric span{color:var(--ink-500);font-size:11px;font-weight:500;letter-spacing:.01em;text-transform:none}.psb-metric strong{color:var(--ink-1000);font-size:20px;font-weight:600;line-height:1.1;font-feature-settings:'tnum'}.psb-metric.accent::before{background:var(--accent-600)}
            .psb-workspace{display:grid;grid-template-columns:220px minmax(0,1fr);gap:16px;align-items:start}.psb-nav{position:sticky;top:72px;align-self:start;border:1px solid var(--ink-150);border-radius:var(--r-2xl);background:var(--surface);padding:10px;display:grid;gap:8px;box-shadow:var(--shadow-sm)}.psb-nav-item{min-height:58px;border:1px solid transparent;border-radius:12px;background:var(--surface-2);color:var(--ink-700);text-align:left;padding:10px 12px;transition:all .2s var(--ease)}.psb-nav-item span{display:block;color:var(--ink-500);font-family:var(--font-mono);font-size:10px;font-weight:500}.psb-nav-item strong{display:block;margin-top:3px;color:var(--ink-900);font-size:13px;font-weight:600}.psb-nav-item:hover{background:var(--primary-50);border-color:var(--primary-100)}.psb-nav-item.active{background:var(--ink-1000);border-color:var(--ink-1000);box-shadow:var(--shadow-sm)}.psb-nav-item.active span,.psb-nav-item.active strong{color:#fff}
            .psb-card{min-width:0;border:1px solid var(--ink-150);border-radius:var(--r-2xl);background:var(--surface);padding:18px;box-shadow:var(--shadow-md);display:grid;gap:16px}.psb-section-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px}.psb-section-head h2{margin:0;color:var(--ink-1000);font-size:17px;font-weight:600;letter-spacing:-.015em}.psb-section-head p{margin:4px 0 0;color:var(--ink-500);font-size:13px;font-weight:400;line-height:1.5}.psb-actions{display:flex;flex-wrap:wrap;gap:8px;justify-content:flex-end}.psb-badge{display:inline-flex;align-items:center;min-height:28px;border:1px solid var(--primary-100);border-radius:999px;background:var(--primary-50);color:var(--primary-700);padding:0 10px;font-size:11px;font-weight:600}
            .psb-form-grid{display:grid;gap:12px}.psb-form-grid.two{grid-template-columns:repeat(2,minmax(0,1fr))}.psb-field{display:grid;gap:6px;margin:0;color:var(--ink-600);font-size:11px;font-weight:500}.psb-field input,.psb-field select,.psb-field textarea,.psb-link-input{width:100%;min-height:38px;border:1px solid var(--ink-200);border-radius:8px;background:var(--surface);color:var(--ink-900);padding:0 11px;font-size:13px;font-weight:400;outline:none;transition:all .2s var(--ease)}.psb-field input:focus,.psb-field select:focus,.psb-link-input:focus{border-color:var(--primary-600);box-shadow:0 0 0 3px rgba(99,102,241,.15)}.psb-field small{color:var(--ink-500);font-size:11px;font-weight:400}.psb-check{display:inline-flex;align-items:center;gap:7px;margin:0;color:var(--ink-700);font-size:12px;font-weight:500}.psb-check.compact{justify-content:center}
            .psb-dim-panel{border:1px solid var(--ink-100);border-radius:var(--r-lg);background:var(--surface-2);padding:14px;display:grid;gap:12px}.psb-dim-head{display:grid;grid-template-columns:minmax(0,1fr) minmax(280px,.6fr);gap:14px;align-items:end}.psb-dim-head span{display:block;color:var(--primary-700);font-size:11px;font-weight:600}.psb-dim-head strong{display:block;color:var(--ink-1000);font-size:15px;font-weight:600}.psb-dim-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.psb-dim-actions{display:flex;gap:8px;flex-wrap:wrap}.psb-preview{display:grid;gap:6px;color:var(--ink-500);font-size:12px}.psb-preview-table-wrap{overflow:auto;border:1px solid var(--ink-100);border-radius:12px;background:var(--surface)}.psb-preview-table{width:100%;min-width:980px;border-collapse:separate;border-spacing:0}.psb-preview-table th{position:sticky;top:0;background:var(--surface-2);border-bottom:1px solid var(--ink-100);color:var(--ink-500);font-size:10px;font-weight:600;text-align:left;padding:8px 10px;white-space:nowrap}.psb-preview-table td{border-bottom:1px solid var(--ink-100);padding:8px 10px;vertical-align:top;color:var(--ink-700);font-size:12px}.psb-preview-table tr:last-child td{border-bottom:0}.psb-preview-table strong{display:block;color:var(--ink-900);font-size:12px;font-weight:600}.psb-preview-table small{display:block;margin-top:2px;color:var(--ink-400);font-size:10px;line-height:1.25;max-width:320px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.psb-preview-table .psb-number{font-family:var(--font-mono);color:var(--ink-900);font-weight:600;text-align:right;white-space:nowrap}.psb-col-select{width:42px;text-align:center}.psb-col-select input[type='checkbox']{appearance:none;-webkit-appearance:none;display:inline-grid;place-content:center;width:18px!important;height:18px!important;min-width:18px!important;min-height:18px!important;margin:0;padding:0;border:1.5px solid var(--ink-300);border-radius:6px;background:var(--surface);cursor:pointer;transition:all .15s var(--ease)}.psb-col-select input[type='checkbox']::after{content:'';width:9px;height:9px;transform:scale(0);transition:transform .12s var(--ease);background:#fff;clip-path:polygon(14% 44%,0 58%,38% 96%,100% 20%,86% 8%,36% 68%)}.psb-col-select input[type='checkbox']:checked{border-color:var(--primary-600);background:var(--primary-600)}.psb-col-select input[type='checkbox']:checked::after{transform:scale(1)}.psb-col-select input[type='checkbox']:focus-visible{outline:3px solid rgba(99,102,241,.16);outline-offset:2px}.psb-line-table tr.is-selected td{background:var(--primary-50)}.psb-btn:disabled{opacity:.55;cursor:not-allowed}
            .psb-agent-limits{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.psb-collapse-title{display:flex;align-items:flex-start;gap:9px;border:0;background:transparent;text-align:left;padding:0;color:inherit}.psb-collapse-title>span{display:grid;place-items:center;width:24px;height:24px;border:1px solid var(--ink-150);border-radius:8px;background:var(--surface-2);color:var(--ink-700);font-weight:700}.psb-items-card.is-collapsed .psb-items-body{display:none}.psb-line-table-wrap{overflow:auto;border:1px solid var(--ink-100);border-radius:var(--r-lg);background:var(--surface)}.psb-line-table{width:100%;border-collapse:separate;border-spacing:0;min-width:980px}.psb-line-table th{position:sticky;top:0;background:var(--surface-2);border-bottom:1px solid var(--ink-100);color:var(--ink-500);font-size:11px;font-weight:600;text-align:left;padding:10px}.psb-line-table td{border-bottom:1px solid var(--ink-100);padding:9px 10px;vertical-align:middle}.psb-line-table tr:last-child td{border-bottom:0}.psb-line-table input{width:100%;min-height:34px;border:1px solid var(--ink-200);border-radius:8px;background:var(--surface);color:var(--ink-900);padding:0 9px;font-size:12px;outline:none}.psb-line-item{min-width:220px}.psb-item-name{min-width:180px;color:var(--ink-700);font-size:12px}.psb-money{text-align:right;color:var(--ink-1000);font-weight:600;font-feature-settings:'tnum';white-space:nowrap}.psb-cell-highlight{background:var(--primary-50);color:var(--primary-700);border-left:1px solid var(--primary-100);border-right:1px solid var(--primary-100)}.psb-discount-cap{display:block;margin-top:3px;color:var(--ink-400);font-size:9px;white-space:nowrap}.psb-danger{display:block;margin-top:5px;color:var(--rose-700);font-size:11px;font-weight:500}.psb-icon-btn{width:30px;height:30px;border:1px solid var(--rose-100);border-radius:8px;background:var(--rose-50);color:var(--rose-700);font-size:18px;line-height:1}
            .psb-line-table-wrap:focus-within{overflow:visible;position:relative;z-index:50}.psb-line-table-wrap .awesomplete{width:100%}.psb-line-table-wrap .awesomplete>ul{z-index:1000}
            .psb-quote-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.psb-quote-metric{position:relative;border:1px solid var(--ink-150);border-radius:var(--r-lg);background:var(--surface);padding:16px;box-shadow:var(--shadow-xs);overflow:hidden}.psb-quote-metric::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--primary-500)}.psb-quote-metric span{display:block;color:var(--ink-500);font-size:11px;font-weight:500}.psb-quote-metric strong{display:block;margin-top:8px;color:var(--ink-1000);font-size:22px;font-weight:600;font-feature-settings:'tnum'}.psb-warning,.psb-error{border:1px solid var(--rose-100);background:var(--rose-50);color:var(--rose-700);border-radius:12px;padding:12px 14px;font-size:13px;font-weight:500}.psb-warning pre{white-space:pre-wrap;margin:8px 0 0;color:inherit;font-family:var(--font-mono);font-size:11px}.psb-ok{border:1px solid var(--success-100);background:var(--success-50);color:var(--success-700);border-radius:12px;padding:12px 14px;font-size:13px;font-weight:500}.psb-muted{border:1px dashed var(--ink-200);border-radius:12px;background:var(--surface);color:var(--ink-500);padding:12px;font-size:13px;text-align:center}.psb-empty{min-height:260px;display:grid;place-items:center;text-align:center;border:1px dashed var(--ink-200);border-radius:var(--r-lg);background:var(--surface-2);padding:28px}.psb-empty h3{margin:0;color:var(--ink-1000);font-size:18px;font-weight:600}.psb-empty p{margin:6px 0 14px;color:var(--ink-500);font-size:13px}.psb-skeleton{min-height:220px;border-radius:var(--r-2xl);background:linear-gradient(90deg,var(--ink-100),var(--surface),var(--ink-100));background-size:220% 100%;animation:psb-shimmer 1.2s infinite}.psb-skeleton.small{min-height:90px}@keyframes psb-shimmer{0%{background-position:120% 0}100%{background-position:-120% 0}}
            .psb-btn{height:38px;border:1px solid transparent;border-radius:10px;padding:0 14px;font-size:13px;font-weight:500;transition:all .2s var(--ease);white-space:nowrap}.psb-btn.primary,.psb-btn.dark{background:var(--ink-1000);color:#fff;box-shadow:var(--shadow-sm)}.psb-btn.primary:hover,.psb-btn.dark:hover{background:var(--ink-800);transform:translateY(-1px)}.psb-btn.ghost{background:var(--surface);color:var(--ink-700);border-color:var(--ink-200)}.psb-btn.ghost:hover{background:var(--surface-2);color:var(--ink-900)}.psb-btn.danger{background:var(--rose-50);color:var(--rose-700);border-color:var(--rose-100)}.psb-btn.danger:hover{background:var(--rose-100);transform:translateY(-1px)}.psb-bottom-bar{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:20;display:flex;gap:8px;align-items:center;justify-content:center;border:1px solid var(--ink-150);border-radius:16px;background:rgba(255,255,255,.92);backdrop-filter:blur(14px);box-shadow:var(--shadow-lg);padding:10px}.psb-btn:focus-visible,.psb-nav-item:focus-visible,.psb-icon-btn:focus-visible,.psb-field input:focus-visible,.psb-field select:focus-visible,.psb-line-table input:focus-visible{outline:3px solid rgba(99,102,241,.15);outline-offset:2px}
            .psb-shell{padding:14px 18px 84px;gap:10px}.psb-breadcrumb{font-size:11px}.psb-hero{grid-template-columns:minmax(0,1fr) auto;padding:14px 18px;border-radius:16px;gap:18px}.psb-eyebrow{margin-bottom:6px;padding:3px 9px;font-size:10px}.psb-hero h1{margin-bottom:3px;font-size:20px}.psb-hero p{font-size:12px;line-height:1.35}.psb-hero-kpis{grid-template-columns:repeat(4,minmax(92px,1fr));gap:8px}.psb-metric{min-height:54px;padding:9px 10px;border-radius:10px}.psb-metric strong{font-size:15px}.psb-metric span{font-size:10px}.psb-tabs{display:flex;gap:6px;flex-wrap:wrap;border:1px solid var(--ink-150);border-radius:14px;background:var(--surface);padding:6px;box-shadow:var(--shadow-sm)}.psb-nav-item{min-height:34px;border-radius:9px;padding:0 11px;display:inline-flex;align-items:center;gap:7px}.psb-nav-item span{font-size:10px}.psb-nav-item strong{margin-top:0;font-size:12px}.psb-editor{display:grid;gap:10px}.psb-card{padding:12px;border-radius:14px;gap:10px}.psb-section-head h2{font-size:15px}.psb-section-head p{font-size:11px;margin-top:2px}.psb-form-grid{gap:8px}.psb-form-grid.two{grid-template-columns:repeat(3,minmax(0,1fr))}.psb-field{gap:4px;font-size:10px}.psb-field input,.psb-field select,.psb-field textarea,.psb-link-input{min-height:32px;border-radius:7px;font-size:12px}.psb-btn{height:32px;border-radius:8px;padding:0 10px;font-size:12px}.psb-dim-panel{padding:10px;border-radius:12px;gap:8px}.psb-dim-head{grid-template-columns:minmax(0,1fr) minmax(240px,.45fr);gap:10px}.psb-dim-summary{display:block;margin-top:2px;color:var(--ink-500);font-size:11px;font-weight:400}.psb-dim-grid{grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.psb-preview-row{padding:6px 8px;border-radius:8px}.psb-policy-card{gap:8px}.psb-map-head,.psb-map-row{display:grid;grid-template-columns:minmax(150px,1fr) minmax(150px,1fr) minmax(150px,1fr) minmax(160px,1fr) minmax(130px,.8fr) minmax(130px,.8fr) 72px 78px 34px;gap:6px;align-items:center}.psb-map-head{color:var(--ink-500);font-size:10px;font-weight:600;padding:0 2px}.psb-map-list{display:grid;gap:6px}.psb-map-row{border:1px solid var(--ink-100);border-radius:10px;background:var(--surface-2);padding:6px}.psb-map-row input{min-height:32px;border:1px solid var(--ink-200);border-radius:7px;padding:0 8px;background:var(--surface);font-size:12px}.psb-line-table{min-width:1120px}.psb-line-table th{padding:7px 8px;font-size:10px}.psb-line-table td{padding:6px 8px}.psb-line-table input{min-height:30px;font-size:12px}.psb-line-item{min-width:190px}.psb-mini-badge{display:inline-flex;border:1px solid var(--ink-100);border-radius:999px;background:var(--surface-2);padding:2px 7px;color:var(--ink-600);font-size:10px;font-weight:600;white-space:nowrap}.psb-number{text-align:right;font-feature-settings:'tnum';font-weight:600}.psb-dim-rule{max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--ink-600);font-size:11px}.psb-icon-btn{width:28px;height:28px;border-radius:7px}.psb-quote-grid{gap:8px}.psb-quote-metric{padding:10px;border-radius:10px}.psb-quote-metric strong{font-size:17px}.psb-bottom-bar{bottom:10px;padding:7px;border-radius:12px}.psb-btn:disabled{opacity:.45;cursor:not-allowed;transform:none!important}
            .psb-map-table-wrap{overflow:auto;border:1px solid var(--ink-100);border-radius:12px;background:var(--surface)}.psb-map-table{width:100%;min-width:1180px;border-collapse:separate;border-spacing:0}.psb-map-table th{position:sticky;top:0;z-index:1;background:var(--surface-2);border-bottom:1px solid var(--ink-100);color:var(--ink-500);font-size:10px;font-weight:600;text-align:left;padding:7px 8px;white-space:nowrap}.psb-map-table td{border-bottom:1px solid var(--ink-100);padding:6px 8px;vertical-align:middle}.psb-map-table tr:last-child td{border-bottom:0}.psb-map-table td:nth-child(7){width:72px}.psb-map-table td:nth-child(8){width:82px}.psb-map-table td:last-child{width:36px;text-align:right}.psb-map-table input[type='number']{width:64px;min-height:30px;border:1px solid var(--ink-200);border-radius:7px;padding:0 8px;background:var(--surface);font-size:12px}.psb-map-table .psb-link-input{min-height:30px;font-size:12px}.psb-map-empty{text-align:center;color:var(--ink-500);font-size:12px;font-weight:500;padding:18px!important}.psb-map-table .psb-check{justify-content:center}
            .psb-mode-card{gap:12px}.psb-mode-switch{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.psb-mode-option{position:relative;display:grid;gap:4px;margin:0;border:1px solid var(--ink-150);border-radius:12px;background:var(--surface-2);padding:12px 12px 12px 38px;cursor:pointer;transition:all .2s var(--ease)}.psb-mode-option input{position:absolute;left:12px;top:14px}.psb-mode-option strong{color:var(--ink-900);font-size:13px;font-weight:600}.psb-mode-option span{color:var(--ink-500);font-size:11px;line-height:1.4}.psb-mode-option.active{border-color:var(--primary-100);background:var(--primary-50);box-shadow:var(--shadow-xs)}.psb-static-panel{display:grid;grid-template-columns:minmax(280px,420px) minmax(0,1fr);gap:12px;align-items:end;border:1px solid var(--ink-100);border-radius:12px;background:var(--surface-2);padding:12px}.psb-static-panel p{margin:0;color:var(--ink-500);font-size:12px;line-height:1.45}
            .psb-static-panel-lists{grid-template-columns:1fr;align-items:stretch}.psb-static-list-head{display:flex;align-items:center;justify-content:space-between;gap:10px}.psb-static-list-head strong{display:block;color:var(--ink-1000);font-size:13px}.psb-static-list-head span{display:block;color:var(--ink-500);font-size:11px}.psb-selling-list-rows{display:grid;gap:8px}.psb-selling-list-row{display:grid;grid-template-columns:36px minmax(220px,1fr) 96px 92px 34px;gap:8px;align-items:end;border:1px solid var(--ink-100);border-radius:10px;background:var(--surface);padding:8px}.psb-selling-list-row>span{display:grid;place-items:center;height:32px;border-radius:8px;background:var(--primary-50);color:var(--primary-700);font-family:var(--font-mono);font-size:11px;font-weight:600}.psb-selling-list-row label{margin:0;color:var(--ink-500);font-size:10px}.psb-selling-list-row input[type='number']{width:100%;min-height:32px;border:1px solid var(--ink-200);border-radius:8px;background:var(--surface);padding:0 8px;font-size:12px}
            .psb-map-list{display:grid;gap:8px}.psb-map-card{display:grid;grid-template-columns:minmax(170px,.75fr) minmax(0,2.4fr) auto;gap:10px;align-items:end;border:1px solid var(--ink-100);border-radius:12px;background:linear-gradient(180deg,var(--surface),var(--surface-2));padding:10px;box-shadow:var(--shadow-xs)}.psb-map-row-head{align-self:stretch;display:grid;align-content:center;gap:3px;border-right:1px solid var(--ink-100);padding-right:10px}.psb-map-row-head span{width:max-content;border-radius:999px;background:var(--primary-50);border:1px solid var(--primary-100);color:var(--primary-700);padding:2px 7px;font-family:var(--font-mono);font-size:10px;font-weight:600}.psb-map-row-head strong{color:var(--ink-1000);font-size:13px;font-weight:600;line-height:1.25}.psb-map-row-head em{color:var(--ink-500);font-size:10px;font-style:normal}.psb-map-fields{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:8px}.psb-map-field{display:grid;gap:4px;margin:0}.psb-map-field span,.psb-map-priority span{color:var(--ink-500);font-size:10px;font-weight:600}.psb-map-field .psb-link-input{min-height:32px;border-radius:8px;font-size:12px}.psb-map-controls{display:flex;align-items:end;gap:7px}.psb-map-priority{display:grid;gap:4px;margin:0}.psb-map-priority input{width:62px;min-height:32px;border:1px solid var(--ink-200);border-radius:8px;background:var(--surface);padding:0 8px;font-size:12px}.psb-map-controls .psb-check{min-height:32px;border:1px solid var(--ink-100);border-radius:8px;background:var(--surface);padding:0 8px}.psb-map-controls .psb-icon-btn{width:32px;height:32px}.psb-map-empty{border:1px dashed var(--ink-200);border-radius:12px;background:var(--surface-2);text-align:center;color:var(--ink-500);font-size:12px;font-weight:500;padding:18px}
            .psb-breakdown-list{display:grid;gap:10px}.psb-breakdown-row{display:grid;gap:10px;border:1px solid var(--ink-100);border-radius:12px;background:linear-gradient(180deg,var(--surface),var(--surface-2));padding:10px}.psb-breakdown-head{display:grid;grid-template-columns:34px minmax(0,1fr) auto;gap:10px;align-items:center}.psb-breakdown-head>span{display:grid;place-items:center;width:28px;height:28px;border-radius:9px;background:var(--primary-50);border:1px solid var(--primary-100);color:var(--primary-700);font-family:var(--font-mono);font-size:11px;font-weight:600}.psb-breakdown-head strong{display:block;color:var(--ink-1000);font-size:13px;font-weight:600}.psb-breakdown-head p{margin:1px 0 0;color:var(--ink-500);font-size:11px}.psb-breakdown-head em{font-style:normal;color:var(--ink-700);font-family:var(--font-mono);font-size:12px}.psb-breakdown-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.psb-breakdown-metric{display:grid;gap:3px;border:1px solid var(--ink-100);border-radius:10px;background:var(--surface);padding:8px}.psb-breakdown-metric.highlight{border-color:var(--primary-100);background:var(--primary-50)}.psb-breakdown-metric em{font-style:normal;color:var(--ink-500);font-size:10px}.psb-breakdown-metric strong{color:var(--ink-1000);font-size:13px;font-weight:600}.psb-breakdown-steps{display:flex;flex-wrap:wrap;gap:6px}.psb-breakdown-step{display:inline-flex;gap:8px;align-items:center;border:1px solid var(--ink-100);border-radius:999px;background:var(--surface);padding:5px 8px;font-size:11px}.psb-breakdown-step strong{color:var(--ink-600);font-weight:500}.psb-breakdown-step em{font-style:normal;color:var(--ink-900);font-family:var(--font-mono)}.psb-history-card{gap:8px;background:var(--surface-2);border-color:var(--ink-100);box-shadow:var(--shadow-xs)}.psb-history-card .psb-section-head h2{color:var(--ink-700);font-size:13px;font-weight:600}.psb-history-card .psb-section-head p{color:var(--ink-400);font-size:11px}.psb-history-toggle{display:inline-flex;align-items:center;gap:8px;min-height:28px;border:1px solid var(--ink-150);border-radius:999px;background:var(--surface);color:var(--ink-600);padding:0 10px;font-size:11px;font-weight:500}.psb-history-toggle span{color:var(--ink-400);font-family:var(--font-mono);font-size:10px}.psb-history-card.is-collapsed .psb-history-content{display:none}.psb-history-list{display:grid;gap:6px}.psb-history-event{display:grid;grid-template-columns:12px minmax(0,1fr) minmax(140px,.24fr);gap:8px;align-items:start;border:1px solid var(--ink-100);border-radius:10px;background:var(--surface-3);padding:8px;box-shadow:none}.psb-history-dot{width:6px;height:6px;margin-top:4px;border-radius:999px;background:var(--ink-300);box-shadow:none}.psb-history-event strong{display:block;color:var(--ink-700);font-size:11px;font-weight:500}.psb-history-event p{margin:1px 0 0;color:var(--ink-500);font-size:10px;line-height:1.3}.psb-history-event aside{display:grid;gap:1px;justify-items:end;color:var(--ink-400);font-size:10px;line-height:1.2}.psb-history-event time{font-family:var(--font-mono);color:var(--ink-400);font-size:9px}
            .psb-shell,.psb-editor,.psb-card,.psb-items-body{min-width:0}.psb-line-table-wrap{max-width:100%;min-width:0;overflow-x:auto!important;overflow-y:hidden!important;position:relative;padding-bottom:0;transition:padding-bottom .18s var(--ease)}.psb-line-table-wrap:focus-within{overflow-x:auto!important;overflow-y:hidden!important;padding-bottom:340px}.psb-line-table{width:max-content;min-width:1800px;table-layout:fixed}.psb-line-table th{white-space:nowrap}.psb-line-table input{min-width:0}.psb-line-table col.psb-col-__select{width:44px}.psb-line-table col.psb-col-actions{width:54px}.psb-line-table col.psb-col-item{width:260px}.psb-line-table col.psb-col-item_name{width:300px}.psb-line-table col.psb-col-qty{width:86px}.psb-line-table col.psb-col-source_buying_price_list,.psb-line-table col.psb-col-pricing_scenario,.psb-line-table col.psb-col-resolved_pricing_scenario,.psb-line-table col.psb-col-resolved_scenario_rule,.psb-line-table col.psb-col-resolved_margin_rule{width:220px}.psb-line-table col.psb-col-display_group,.psb-line-table col.psb-col-benchmark_note,.psb-line-table col.psb-col-buy_price_message,.psb-line-table col.psb-col-breakdown_preview{width:220px}.psb-line-table col.psb-col-manual_sell_unit_price{width:150px}.psb-line-table col.psb-col-discount_percent,.psb-line-table col.psb-col-max_discount_percent_allowed{width:118px}.psb-line-table col.psb-col-line_type,.psb-line-table col.psb-col-scenario_source,.psb-line-table col.psb-col-benchmark_status,.psb-line-table col.psb-col-margin_source{width:150px}.psb-line-table col.psb-col-buy_price,.psb-line-table col.psb-col-base_amount,.psb-line-table col.psb-col-expense_unit_price,.psb-line-table col.psb-col-expense_total,.psb-line-table col.psb-col-customs_unit_amount,.psb-line-table col.psb-col-margin_unit_amount,.psb-line-table col.psb-col-margin_total_amount,.psb-line-table col.psb-col-projected_unit_price,.psb-line-table col.psb-col-projected_total_price,.psb-line-table col.psb-col-final_sell_unit_price,.psb-line-table col.psb-col-final_sell_total,.psb-line-table col.psb-col-discount_amount,.psb-line-table col.psb-col-discounted_sell_unit_price,.psb-line-table col.psb-col-discounted_sell_total,.psb-line-table col.psb-col-commission_amount,.psb-line-table col.psb-col-static_list_price,.psb-line-table col.psb-col-benchmark_price,.psb-line-table col.psb-col-benchmark_reference{width:135px}.psb-line-table col{width:140px}.psb-line-table td{overflow:hidden;text-overflow:ellipsis}.psb-line-table td:has(input),.psb-line-table td:has(.awesomplete){overflow:visible}
            .psb-preview-panel{display:grid;gap:8px}.psb-preview-toggle{display:flex;align-items:center;justify-content:space-between;gap:10px;width:100%;min-height:34px;border:1px solid var(--ink-100);border-radius:10px;background:var(--surface);padding:0 11px;color:var(--ink-700);font-size:12px;font-weight:500}.psb-preview-toggle strong{color:var(--primary-700);font-size:12px}.psb-column-list{display:grid;gap:6px;max-height:60vh;overflow:auto;padding:4px}.psb-column-option{display:grid;grid-template-columns:28px minmax(0,1fr);align-items:center;gap:8px;border:1px solid var(--ink-100);border-radius:9px;background:var(--surface);padding:8px 10px;cursor:grab}.psb-column-option:active{cursor:grabbing}.psb-drag-handle{color:var(--ink-400);font-family:var(--font-mono);font-size:12px}.psb-column-option label{margin:0;color:var(--ink-800);font-size:13px;font-weight:500}
            .psb-breakdown-detail-wrap{overflow:auto;border:1px solid var(--ink-100);border-radius:12px;background:var(--surface)}.psb-breakdown-detail{width:100%;min-width:720px;border-collapse:separate;border-spacing:0}.psb-breakdown-detail th{background:var(--surface-2);border-bottom:1px solid var(--ink-100);color:var(--ink-500);font-size:10px;font-weight:600;text-align:left;padding:8px 10px;white-space:nowrap}.psb-breakdown-detail td{border-bottom:1px solid var(--ink-100);padding:8px 10px;color:var(--ink-800);font-size:12px;vertical-align:top}.psb-breakdown-detail tr:last-child td{border-bottom:0}.psb-breakdown-detail td:nth-child(2),.psb-breakdown-detail td:nth-child(3){font-family:var(--font-mono);text-align:right;white-space:nowrap;color:var(--ink-1000);font-weight:600}.psb-breakdown-detail tr.final td{background:var(--primary-50);color:var(--primary-800);font-weight:700}.psb-breakdown-detail tr.discount td{color:var(--rose-700)}.psb-sub-expenses{display:grid;gap:6px}.psb-sub-expenses>strong{color:var(--ink-700);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.04em}
            @media(max-width:1280px){.psb-hero{grid-template-columns:1fr}.psb-hero-kpis,.psb-quote-grid{grid-template-columns:repeat(4,minmax(0,1fr))}.psb-dim-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.psb-form-grid.two{grid-template-columns:repeat(2,minmax(0,1fr))}.psb-map-card{grid-template-columns:1fr}.psb-map-row-head{border-right:0;border-bottom:1px solid var(--ink-100);padding:0 0 8px}.psb-map-fields{grid-template-columns:repeat(2,minmax(0,1fr))}.psb-map-controls{justify-content:flex-start}}@media(max-width:980px){.psb-shell{padding:12px 12px 96px}.psb-form-grid.two,.psb-dim-head,.psb-static-panel{grid-template-columns:1fr}.psb-hero-kpis,.psb-quote-grid,.psb-mode-switch{grid-template-columns:repeat(2,minmax(0,1fr))}.psb-section-head{flex-direction:column}.psb-actions{justify-content:flex-start}.psb-history-event{grid-template-columns:16px minmax(0,1fr)}.psb-history-event aside{grid-column:2;justify-items:start}.psb-bottom-bar{left:12px;right:12px;bottom:8px;transform:none;overflow-x:auto;justify-content:flex-start}}@media(max-width:640px){.psb-hero{padding:12px}.psb-hero-kpis,.psb-quote-grid,.psb-dim-grid,.psb-tabs,.psb-map-fields,.psb-mode-switch{grid-template-columns:1fr}.psb-map-controls{flex-wrap:wrap}.psb-bottom-bar .psb-btn{min-width:max-content}}
        `;
        document.head.appendChild(style);
        return;
        style.textContent = `
            .psb-root{background:#f5f7fb}.psb-shell{min-height:calc(100vh - 56px);padding:14px 18px 96px;color:#0f172a;display:grid;gap:12px}.psb-hero{display:grid;grid-template-columns:minmax(280px,1fr) minmax(420px,.9fr);gap:14px;align-items:center;border:1px solid #dbe4f0;border-radius:22px;background:linear-gradient(135deg,#111827,#0f766e);color:#fff;padding:16px;box-shadow:0 18px 42px rgba(15,23,42,.18)}.psb-eyebrow{color:#99f6e4;font-size:10px;font-weight:900;letter-spacing:.12em;text-transform:uppercase}.psb-hero h1{margin:4px 0 3px;font-size:24px;font-weight:950;line-height:1.08;letter-spacing:-.035em}.psb-hero p{margin:0;color:#ccfbf1;font-size:12px;font-weight:800;line-height:1.45}.psb-hero-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.psb-metric{min-height:62px;border-radius:15px;border:1px solid rgba(255,255,255,.22);background:rgba(255,255,255,.12);padding:9px 10px;display:grid;align-content:center;gap:4px}.psb-metric span{color:#99f6e4;font-size:9px;font-weight:900;text-transform:uppercase;letter-spacing:.08em}.psb-metric strong{color:#fff;font-size:17px;font-weight:950;line-height:1}.psb-metric.accent{background:#fff;color:#0f766e}.psb-metric.accent span,.psb-metric.accent strong{color:#0f766e}.psb-workspace{display:grid;grid-template-columns:190px minmax(0,1fr);gap:12px}.psb-nav{position:sticky;top:72px;align-self:start;border:1px solid #dfe8f3;border-radius:18px;background:#fff;padding:10px;display:grid;gap:8px;box-shadow:0 12px 28px rgba(15,23,42,.06)}.psb-nav-item{min-height:54px;border:1px solid #e2e8f0;border-radius:14px;background:#f8fafc;color:#475569;text-align:left;padding:8px 10px;cursor:pointer}.psb-nav-item span{display:block;color:#0f766e;font-size:10px;font-weight:950}.psb-nav-item strong{display:block;color:#0f172a;font-size:13px;font-weight:950}.psb-nav-item.active{background:#0f766e;border-color:#0f766e}.psb-nav-item.active span,.psb-nav-item.active strong{color:#fff}.psb-card{border:1px solid #dfe8f3;border-radius:22px;background:#fff;padding:14px;box-shadow:0 14px 34px rgba(15,23,42,.07);display:grid;gap:14px}.psb-section-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.psb-section-head h2{margin:0;color:#0f172a;font-size:18px;font-weight:950;letter-spacing:-.02em}.psb-section-head p{margin:4px 0 0;color:#64748b;font-size:12px;font-weight:780}.psb-badge{border-radius:999px;background:#ecfeff;color:#0e7490;padding:5px 9px;font-size:10px;font-weight:950}.psb-form-grid{display:grid;gap:10px}.psb-form-grid.two{grid-template-columns:repeat(2,minmax(0,1fr))}.psb-field{display:grid;gap:5px;margin:0}.psb-field span,.psb-dim-head span{color:#64748b;font-size:10px;font-weight:950;letter-spacing:.08em;text-transform:uppercase}.psb-field input,.psb-field select,.psb-dim-grid input,.psb-dim-grid select,.psb-line-table input,.psb-link-input{width:100%;min-height:40px;border:1px solid #d8e2ee;border-radius:12px;background:#f8fafc;color:#102033;padding:0 10px;font-weight:850;outline:none}.psb-actions,.psb-dim-actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.psb-btn{min-height:40px;border:0;border-radius:999px;padding:0 14px;font-weight:950;cursor:pointer}.psb-btn.primary{background:#0f766e;color:#fff;box-shadow:0 10px 22px rgba(15,118,110,.2)}.psb-btn.dark{background:#111827;color:#fff}.psb-btn.ghost{background:#f8fafc;color:#0f3b61;border:1px solid #d8e2ee}.psb-dim-panel{border:1px dashed #cbd5e1;border-radius:18px;background:#f8fafc;padding:12px;display:grid;gap:12px}.psb-dim-head{display:grid;grid-template-columns:minmax(0,1fr) minmax(260px,.45fr);gap:12px;align-items:end}.psb-dim-head strong{display:block;color:#0f172a;font-size:15px;font-weight:950}.psb-dim-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.psb-field small{color:#64748b;font-weight:750}.psb-check{display:flex;align-items:center;gap:7px;margin:0;min-height:40px}.psb-check.compact{min-height:0}.psb-preview{border:1px solid #e2e8f0;border-radius:14px;background:#fff;padding:10px;color:#64748b;font-weight:800}.psb-preview-row{display:grid;grid-template-columns:minmax(0,1fr) minmax(120px,.4fr) auto;gap:8px;align-items:center;border-bottom:1px solid #eef2f7;padding:7px 0}.psb-preview-row:last-child{border-bottom:0}.psb-preview-row strong{color:#0f172a}.psb-preview-row em{font-style:normal;color:#0f766e;font-weight:950}.psb-line-table-wrap{overflow:auto;border:1px solid #e2e8f0;border-radius:16px}.psb-line-table{width:100%;min-width:980px;border-collapse:collapse;background:#fff}.psb-line-table th{position:sticky;top:0;background:#f8fafc;color:#64748b;font-size:10px;font-weight:950;text-transform:uppercase;letter-spacing:.08em;text-align:left;padding:9px;border-bottom:1px solid #e2e8f0}.psb-line-table td{padding:8px;border-bottom:1px solid #eef2f7;vertical-align:top}.psb-line-item{min-width:240px}.psb-money{font-weight:950;color:#0f172a;white-space:nowrap}.psb-icon-btn{width:34px;height:34px;border:1px solid #fecdd3;border-radius:999px;background:#fff1f2;color:#be123c;font-weight:950;cursor:pointer}.psb-danger{display:block;margin-top:4px;color:#be123c;font-weight:850}.psb-muted{color:#64748b;font-weight:850}.psb-empty{min-height:220px;display:grid;place-items:center;text-align:center;border:1px dashed #cbd5e1;border-radius:18px;background:#fff;padding:20px;color:#64748b}.psb-empty h3{margin:0;color:#0f172a;font-weight:950}.psb-empty p{margin:4px 0 12px}.psb-quote-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.psb-quote-metric{border-radius:15px;background:#f8fafc;border:1px solid #e2e8f0;padding:12px;display:grid;gap:5px}.psb-quote-metric span{color:#64748b;font-size:10px;font-weight:950;text-transform:uppercase;letter-spacing:.08em}.psb-quote-metric strong{color:#0f172a;font-size:20px;font-weight:950}.psb-warning{border-left:3px solid #f59e0b;background:#fffbeb;border-radius:12px;padding:10px;color:#92400e}.psb-warning pre{white-space:pre-wrap;margin:6px 0 0;font-family:inherit}.psb-ok{border:1px solid #bbf7d0;background:#f0fdf4;color:#166534;border-radius:12px;padding:10px;font-weight:900}.psb-error{border:1px solid #fecdd3;background:#fff1f2;color:#9f1239;border-radius:14px;padding:11px 13px;font-weight:850}.psb-skeleton{min-height:360px;border-radius:20px;background:linear-gradient(90deg,#eef2f7 0%,#f8fafc 45%,#eef2f7 90%);background-size:220% 100%;animation:psb-shimmer 1.1s linear infinite}.psb-skeleton.small{min-height:120px}@keyframes psb-shimmer{to{background-position:-220% 0}}.psb-bottom-bar{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:20;display:flex;gap:8px;align-items:center;border:1px solid #dfe8f3;border-radius:999px;background:rgba(255,255,255,.96);box-shadow:0 18px 40px rgba(15,23,42,.14);padding:8px}.psb-bottom-bar .psb-btn{min-width:120px}@media(max-width:1100px){.psb-hero,.psb-workspace,.psb-dim-head{grid-template-columns:1fr}.psb-nav{position:static;grid-template-columns:repeat(3,minmax(0,1fr))}.psb-hero-kpis,.psb-form-grid.two,.psb-dim-grid,.psb-quote-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.psb-actions{justify-content:flex-start}}@media(max-width:700px){.psb-shell{padding:10px 10px 120px}.psb-nav,.psb-hero-kpis,.psb-form-grid.two,.psb-dim-grid,.psb-quote-grid{grid-template-columns:1fr}.psb-bottom-bar{left:10px;right:10px;bottom:10px;transform:none;border-radius:18px;display:grid;grid-template-columns:1fr 1fr}.psb-bottom-bar .psb-btn{min-width:0}}
        `;
        document.head.appendChild(style);
    }
})();
