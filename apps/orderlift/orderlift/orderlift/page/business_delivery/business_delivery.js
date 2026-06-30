(function () {
    const STATE = { tab: "overview" };

    const TABS = [
        { key: "overview", label: "Overview" },
        { key: "diagrams", label: "Diagrams" },
        { key: "features", label: "Feature Map" },
        { key: "processes", label: "P01-P16 Fit" },
        { key: "roles", label: "Role Playbooks" },
        { key: "acceptance", label: "Acceptance" },
    ];

    const ROUTES = {
        "Access Command Center": "/app/access-command-center",
        "Buying Price Builder": "/app/buying-price-builder",
        "Campaign Builder": "/app/campaign-editor",
        "Campaign Manager": "/app/campaign-manager",
        "Catalogue Prix Articles": "/app/catalogue-prix-articles",
        "Commissions Dashboard": "/app/commission-dashboard",
        "Container Planning": "/app/logistics-dashboard",
        "Document Templates": "/app/document-template-manager",
        "Logistics Pipeline": "/app/logistics-pipeline",
        "Menu Editor": "/app/menu-editor",
        "Mobile QC": "/app/sig-qc",
        "Opportunity Pipeline": "/app/opportunity-pipeline",
        "Portal Review Board": "/app/portal-review-board",
        "Pricing Dashboard": "/app/pricing-dashboard",
        "Pricing Sheet Builder": "/app/pricing-sheet-builder",
        "Pricing Sheet Manager": "/app/pricing-sheet-manager",
        "Pricing Sheets": "/app/pricing-sheet-manager",
        "Pricing Simulator": "/app/pricing-simulator",
        "Project Map": "/app/project-map",
        "Project Pipeline": "/app/project-pipeline",
        "SAV Dashboard": "/app/sav-dashboard",
        "SAV Ticket": "/app/sav-ticket",
        "Sale Financial Dashboard": "/app/sale-financial-dashboard",
        "Sales Order Pipeline": "/app/sales-order-pipeline",
        "Selling Price Builder": "/app/pricing-builder-manager",
        "SIG Dashboard": "/app/sig-dashboard",
        "Status Control": "/app/status-control",
        "Stock Dashboard": "/app/stock-dashboard",
        "Training Center": "/app/training-center",
    };

    const PAGE_GUIDE = [
        ["Train users", "Use Role Playbooks to explain daily pages and actions for each team."],
        ["Review scope", "Use Overview and Diagrams to show what Orderlift really supports today."],
        ["Find pages", "Use Feature Map as the practical route index for managers and operators."],
        ["Avoid overclaiming", "Use P01-P16 Fit to separate app support from manual operating controls."],
        ["Run UAT", "Use Acceptance scenarios to test observable business behavior before signoff."],
    ];

    const STATUS_LEGEND = [
        ["Supported", "Implemented in Orderlift through pages, documents, statuses, dashboards, or safeguards."],
        ["Partial", "Represented in the app, but not a complete end-to-end workflow."],
        ["Operating", "A client business procedure outside current app automation."],
    ];

    const CAPABILITIES = [
        {
            title: "Sell",
            summary: "Manage leads, customers, opportunities, quotations, sales orders, campaigns, and B2B portal requests.",
            pages: ["CRM Dashboard", "Opportunity Pipeline", "Campaign Manager", "Portal Review Board", "Sales Order Pipeline"],
            outputs: ["Qualified opportunity", "Quotation", "Sales order", "Campaign follow-up"],
            controls: ["CRM Business Type", "CRM Segment", "Pipeline status", "Company access"],
        },
        {
            title: "Price",
            summary: "Build controlled prices using items, buying prices, scenarios, customs, benchmark policies, tiers, and agent rules.",
            pages: ["Pricing Sheets", "Pricing Dashboard", "Pricing Simulator", "Buying Price Builder", "Selling Price Builder"],
            outputs: ["Calculated pricing sheet", "Quotation", "Updated price list", "Pricing warnings"],
            controls: ["Scenario", "Customs policy", "Benchmark policy", "Tier", "Agent rules"],
        },
        {
            title: "Buy & Stock",
            summary: "Use native ERPNext purchasing and stock documents with Orderlift packaging, price, QC, and dashboard safeguards.",
            pages: ["Purchase Order", "Purchase Receipt", "Stock Dashboard", "Stock Balance", "Item"],
            outputs: ["Purchase order", "Receipt", "Quality inspection", "Stock ledger movement"],
            controls: ["PO pricing alert", "Packaging profile", "QC routing", "Reorder signal"],
        },
        {
            title: "Move Goods",
            summary: "Plan inbound, domestic, and outbound flows with load plans, container profiles, capacity checks, and logistics statuses.",
            pages: ["Logistics Pipeline", "Container Planning", "Container Profiles", "Delivery Note"],
            outputs: ["Forecast Load Plan", "Shipment analysis", "Ready/Loading/In Transit/Delivered status"],
            controls: ["Flow scope", "Shipping responsibility", "Capacity utilization", "Source document links"],
        },
        {
            title: "Install",
            summary: "Track installation projects with project pipeline, map visibility, site data, QC templates, and mobile QC execution.",
            pages: ["Project Pipeline", "SIG Dashboard", "Project Map", "Mobile QC", "Project"],
            outputs: ["Project", "QC checklist", "Map marker", "Completion readiness"],
            controls: ["Project status", "QC completion", "Geolocation", "Sales Order linkage"],
        },
        {
            title: "Support SAV",
            summary: "Operate after-sales tickets from complaint intake to assignment, intervention, stock action, resolution report, and closure.",
            pages: ["SAV Dashboard", "SAV Ticket"],
            outputs: ["SAV ticket", "Technician assignment", "Stock action", "Resolution report"],
            controls: ["Mandatory resolution report", "Status workflow", "Technician notification", "SLA flag"],
        },
        {
            title: "Govern & Report",
            summary: "Keep management control through roles, menu access, company access, finance dashboards, commissions, training, and performance.",
            pages: ["Access Command Center", "Menu Editor", "Sale Financial Dashboard", "Training Center", "Performance Dashboard"],
            outputs: ["Role access", "Business finance view", "Commission status", "Training progress"],
            controls: ["Menu rules", "Company scope", "Account guard", "Performance metrics"],
        },
    ];

    const DIAGRAMS = [
        {
            title: "Distribution Sale",
            purpose: "How a distribution opportunity becomes a controlled quotation, order, delivery handoff, and finance/commission follow-up.",
            lanes: [
                ["Sales", ["Lead / Customer", "Opportunity Pipeline", "Pricing Sheet", "Quotation", "Sales Order Pipeline"]],
                ["Pricing", ["Segment + tier", "Scenario / customs", "Benchmark warning", "Final price output"]],
                ["Stock / Logistics", ["Stock notification", "Availability check", "Delivery Note / Pick List", "Delivery handoff"]],
                ["Finance", ["Sales Invoice", "Payment Entry", "Commission Dashboard"]],
            ],
            implemented: "CRM, pricing sheet, quotation generation, sales order pipeline, stock notification, finance visibility, and commission sync are implemented.",
            manual: "Advance payment confirmation and final commercial approval are business controls, not hard-coded approval gates.",
        },
        {
            title: "Installation Project",
            purpose: "How an installation sale moves from opportunity to project tracking, site visibility, QC, and completion readiness.",
            lanes: [
                ["Sales", ["Opportunity", "Pricing Sheet", "Quotation", "Sales Order"]],
                ["Project", ["Project created/linked", "Project Pipeline", "Tasks / site follow-up"]],
                ["SIG / QC", ["Project Map", "QC Template", "Mobile QC", "QC status"]],
                ["Finance", ["Invoice/payment follow-up", "Project context", "Financial dashboard"]],
            ],
            implemented: "Project pipeline, Sales Order linkage, map page, QC templates, mobile QC, and QC completion safeguards are implemented.",
            manual: "Contract signature, staged payments, commissioning, and guarantee planning are operating controls unless recorded in ERP records.",
        },
        {
            title: "Pricing To Quotation",
            purpose: "How the app calculates a controlled commercial price before a quote is issued.",
            lanes: [
                ["Inputs", ["Item / bundle", "Buying price", "Customer / segment", "Agent context"]],
                ["Policies", ["Scenario expenses", "Customs policy", "Benchmark policy", "Tier modifiers"]],
                ["System", ["Recalculate", "Warnings", "Line breakdown", "Quotation preview"]],
                ["Output", ["Quotation", "Selling price list", "Catalog visibility"]],
            ],
            implemented: "Pricing sheets, scenarios, customs, benchmark policies, tiers, agent rules, recalculation, warnings, quotations, and price builders are implemented.",
            manual: "Management approval before publication remains a governance step unless a formal workflow is added later.",
        },
        {
            title: "Purchase To Stock",
            purpose: "How purchasing and stock operations are supported through native ERP documents plus Orderlift safeguards.",
            lanes: [
                ["Need", ["Low stock / project need", "Material Request", "RFQ optional"]],
                ["Purchase", ["Supplier", "Purchase Order", "PO price alert", "Packaging snapshot"]],
                ["Receipt", ["Purchase Receipt", "Quality Inspection", "Stock Entry routing"]],
                ["Visibility", ["Stock Dashboard", "Stock Ledger", "Reorder follow-up"]],
            ],
            implemented: "Purchase documents, PO price alerts, packaging validation, receipt QC routing, stock dashboard, stock ledger, and reorder checks are implemented.",
            manual: "Supplier negotiation, payment approval, unloading, and physical depot organization remain business procedures.",
        },
        {
            title: "Logistics Planning",
            purpose: "How inbound, domestic, and outbound movement is classified, planned, and tracked.",
            lanes: [
                ["Source", ["Purchase Order", "Sales Order", "Delivery Note"]],
                ["Decision", ["Flow scope", "Shipping responsibility", "Eligible source lines"]],
                ["Planning", ["Forecast Load Plan", "Container Profile", "Capacity utilization", "Shipment Analysis"]],
                ["Execution", ["Ready", "Loading", "In Transit", "Delivered"]],
            ],
            implemented: "Forecast Load Plan, logistics pipeline, source linking, capacity planning, shipment analysis, and lifecycle statuses are implemented.",
            manual: "Carrier booking, proof of delivery, transport scoring, and external notifications are not automated.",
        },
        {
            title: "Portal & Campaign Activation",
            purpose: "How controlled customer access and campaigns create commercial follow-up.",
            lanes: [
                ["Portal", ["Portal policy", "Allowed products", "Portal quote request", "Review Board"]],
                ["Campaign", ["Campaign Builder", "Targets", "Email / WhatsApp / Call / Visit", "Campaign Manager"]],
                ["Sales", ["Lead / Prospect", "Opportunity", "Quotation", "Follow-up"]],
            ],
            implemented: "Portal policies, allowed products, quote requests, review board, quotation visibility, campaign targets, Email, WhatsApp, Call, Visit, and Other actions are implemented.",
            manual: "Marketing content production, AI media generation, and external publication approval remain outside the app.",
        },
        {
            title: "SAV Lifecycle",
            purpose: "How an after-sales issue is captured, assigned, resolved, and closed.",
            lanes: [
                ["Intake", ["Complaint", "SAV Ticket", "Customer / project context"]],
                ["Execution", ["Assign technician", "In Progress", "Stock action", "Intervention record"]],
                ["Closure", ["Resolution report", "Resolved", "Reject if needed", "Closed"]],
            ],
            implemented: "SAV ticket lifecycle, reported channel, assignment, technician notification, stock actions, mandatory resolution report, rejection, and closure discipline are implemented.",
            manual: "Complex escalation policy and satisfaction scoring are operating rules unless added later.",
        },
    ];

    const FEATURES = [
        ["Create a controlled quotation", "Pricing Sheet Builder", "/app/pricing-sheet-builder", "Select customer, items, scenario, recalculation, warnings, and generate quotation.", "Quotation", "Scenario, customs, benchmark, tier, agent rules"],
        ["Open or create pricing work", "Pricing Sheet Manager", "/app/pricing-sheet-manager", "Business landing page for pricing sheets without native list/form complexity.", "Pricing sheet", "Controlled route for sales/pricing users"],
        ["Publish/manage selling prices", "Selling Price Builder", "/app/pricing-builder-manager", "Build selling price lists from pricing metadata and source prices.", "Price List / Item Price", "Source stamps and pricing metadata"],
        ["Maintain buying prices", "Buying Price Builder", "/app/buying-price-builder", "Manage upstream article economics used by pricing.", "Buying Item Price", "Buying price structure"],
        ["Track opportunities", "Opportunity Pipeline", "/app/opportunity-pipeline", "Kanban view using native Opportunity sales stage as the editable commercial status.", "Opportunity status", "Company scope and CRM classification"],
        ["Track sales orders", "Sales Order Pipeline", "/app/sales-order-pipeline", "Operational sales order status using the Orderlift status field.", "Sales order pipeline", "Orderlift order status"],
        ["Run campaigns", "Campaign Manager / Builder", "/app/campaign-manager", "Prepare targets and execute Email, WhatsApp, Call, Visit, or Other actions.", "Campaign follow-up", "Preflight checks and campaign statuses"],
        ["Review portal requests", "Portal Review Board", "/app/portal-review-board", "Approve/reject customer portal quote requests and create quotations.", "Quotation request decision", "Portal policy and allowed products"],
        ["Govern item catalog", "Catalogue Prix Articles / Item", "/app/catalogue-prix-articles", "Maintain article visibility, prices, categories, bundles, specifications, packaging, and customs values.", "Usable article catalog", "Item category, packaging, customs material"],
        ["Plan shipments", "Logistics Pipeline", "/app/logistics-pipeline", "Track load plans across planning, ready, loading, transit, and delivery.", "Forecast Load Plan", "Flow scope, responsibility, status metadata"],
        ["Check stock", "Stock Dashboard", "/app/stock-dashboard", "View operational stock availability, low-stock risks, and warehouse readiness.", "Stock visibility", "Stock ledger and reorder signals"],
        ["Track installation sites", "Project Map", "/app/project-map", "See projects geographically and support installation follow-up.", "Map visibility", "Project geolocation fields"],
        ["Execute installation QC", "Mobile QC", "/app/sig-qc", "Apply/check QC items and save remarks for project quality control.", "QC status", "Completion guardrails"],
        ["Handle after-sales", "SAV Ticket", "/app/sav-ticket", "Create, assign, execute, resolve, and close service tickets.", "Closed ticket", "Mandatory resolution report and stock actions"],
        ["Review business finance", "Sale Financial Dashboard", "/app/sale-financial-dashboard", "Monitor sales orders, invoices, payments, project/customer context, and classification filters.", "Finance visibility", "Protected backend accounts"],
        ["Control access", "Access Command Center", "/app/access-command-center", "Manage users, company access, roles, and menu access.", "Controlled navigation", "Menu access rules and company scope"],
    ];

    const PROCESSES = [
        ["P01", "Achats", "Supported", "Purchase Order, Purchase Receipt, QC routing, PO alerts, packaging safeguards.", "Supplier negotiation and DG payment validation."],
        ["P02", "Pricing", "Supported", "Pricing Sheet, scenarios, customs, benchmark, tiers, agent rules, quotation generation.", "Final management approval before publication."],
        ["P03", "Benchmark marche", "Partial", "Benchmark policies use maintained price lists and margin rules.", "Field collection by agents is outside the app."],
        ["P04", "Intermediaires", "Partial", "Agent rules, price lists, users, roles, commissions, training.", "Recruitment, contract, and digital qualification."],
        ["P05", "Logistique", "Supported", "Forecast Load Plan, logistics pipeline, capacity checks, source links, shipment analysis.", "Carrier communication and reception evaluation."],
        ["P06", "Stock", "Supported", "Stock dashboard, stock ledger, receipt QC routing, delivery logistics analysis.", "Physical picking/loading/signature discipline."],
        ["P07", "Base articles", "Supported", "Items, categories, specs, packaging, customs, prices, catalog, builders.", "Formal BET article approval if desired."],
        ["P08", "Vente Distribution", "Supported", "CRM, opportunity, pricing sheet, quotation, sales order, stock handoff, finance, commission.", "Advance payment and commercial closure procedure."],
        ["P09", "Vente Installation", "Supported", "Opportunity, sales order, project pipeline, SIG map, mobile QC, QC templates.", "Contract, commissioning, guarantee plan."],
        ["P10", "Campagnes", "Supported", "Campaign builder/manager, targets, Email, WhatsApp, Call, Visit, ToDos.", "Marketing content production and external publication."],
        ["P11", "Support BET", "Partial", "Represented through statuses, project/QC records, specs, and dimensioning.", "Dedicated BET request workflow."],
        ["P12", "Contenu marketing", "Operating", "Campaign content/templates are supported.", "Photo/video collection, AI generation, validation, publication."],
        ["P13", "SAV", "Supported", "SAV ticket, assignment, stock action, resolution report, status workflow.", "Advanced escalation and satisfaction scoring."],
        ["P14", "Developpement RH", "Supported", "Training center, programs, modules, quizzes, progress, performance, appraisals.", "Certification policy and AI generation."],
        ["P15", "Admin / Finance / RH", "Supported", "Access control, company scope, invoices, payments, payroll links, commissions, finance dashboard.", "Payment approval workflow if required."],
        ["P16", "Pilotage", "Supported", "Dashboards across CRM, pricing, stock, logistics, SIG, SAV, finance, HR.", "Corrective action and improvement project follow-up."],
    ];

    const ROLES = [
        {
            role: "Sales User",
            pages: ["CRM Dashboard", "Opportunity Pipeline", "Pricing Sheet Builder", "Quotation", "Sales Order Pipeline", "Campaign Manager"],
            actions: ["Qualify customer", "Create opportunity", "Build quotation", "Follow order status", "Run campaign follow-up"],
            output: "Qualified pipeline, quotations, sales orders, campaign outcomes.",
            protection: "CRM classification, company scope, pricing warnings, pipeline status discipline.",
        },
        {
            role: "Pricing Manager",
            pages: ["Pricing Dashboard", "Pricing Sheets", "Pricing Simulator", "Customs Policy", "Benchmark Policy", "Pricing Tiers", "Selling Price Builder"],
            actions: ["Maintain policies", "Recalculate prices", "Review warnings", "Publish/update price lists", "Control agent rules"],
            output: "Controlled prices and consistent quotation logic.",
            protection: "Scenario sequence, customs rules, benchmark fallback, tier/agent controls.",
        },
        {
            role: "Logistics User",
            pages: ["Stock Dashboard", "Purchase Order", "Purchase Receipt", "Logistics Pipeline", "Container Planning", "Delivery Note"],
            actions: ["Check stock", "Prepare purchase/receipt", "Plan load", "Track movement", "Close delivered flow"],
            output: "Stock visibility, load plans, receipts, and delivery execution records.",
            protection: "Packaging profiles, QC routing, flow scope, shipping responsibility, capacity checks.",
        },
        {
            role: "Installation User",
            pages: ["Project Pipeline", "Sales Order Pipeline", "SIG Dashboard", "Project Map", "Mobile QC", "Project"],
            actions: ["Track project", "Review site info", "Use map", "Apply QC", "Update completion readiness"],
            output: "Visible installation progress and QC evidence.",
            protection: "Project status, geolocation, QC checklist, completion guardrails.",
        },
        {
            role: "Service User",
            pages: ["SAV Dashboard", "SAV Ticket"],
            actions: ["Create ticket", "Assign technician", "Track intervention", "Record stock action", "Resolve and close"],
            output: "Traceable after-sales intervention history.",
            protection: "Mandatory resolution report, status workflow, technician notification.",
        },
        {
            role: "Finance User",
            pages: ["Sale Financial Dashboard", "Sales Payment Summary", "Sales Invoice", "Purchase Invoice", "Payment Entry", "Commissions Dashboard"],
            actions: ["Review receivables", "Track payments", "Follow commissions", "Filter by project/customer/business type"],
            output: "Business finance visibility without exposing backend accounting complexity.",
            protection: "Account guard, company defaults, protected Account/Cost Center fields.",
        },
        {
            role: "Orderlift Admin",
            pages: ["Access Command Center", "Menu Editor", "Status Control", "Document Templates", "Business Delivery"],
            actions: ["Manage access", "Control menus", "Maintain statuses", "Govern templates", "Produce business delivery PDF"],
            output: "Controlled adoption and governance model.",
            protection: "Role rules, menu access rules, company scope, document template governance.",
        },
    ];

    const ACCEPTANCE = [
        ["Commercial", "A user can track an opportunity, build a pricing sheet, generate a quotation, and follow the sales order pipeline."],
        ["Pricing", "Pricing rules, customs, benchmark, tiers, and warnings are visible to pricing users."],
        ["Catalog", "Items, prices, packaging, customs material, and catalog pages support business article governance."],
        ["Purchasing/Stock", "Purchase, receipt, QC, stock dashboard, and ledger visibility support stock operations."],
        ["Logistics", "Forecast Load Plan and logistics pipeline support source linking, capacity planning, and lifecycle tracking."],
        ["Portal", "Portal policies and review board support customer quote request handling."],
        ["Installation", "Project pipeline, map, QC templates, and mobile QC support installation follow-up."],
        ["SAV", "SAV Ticket supports assignment, intervention, stock action, resolution report, and closure."],
        ["Finance", "Finance dashboard and protected backend account behavior support business reporting."],
        ["Governance", "Roles, company scope, menu access, statuses, and document templates can be managed by authorized users."],
    ];

    const UAT_SCENARIOS = [
        {
            title: "Controlled quotation",
            steps: ["Open Pricing Sheet Builder", "Select customer and scenario", "Add item or bundle", "Recalculate", "Review warnings", "Generate Quotation"],
            proof: "Quotation exists with pricing context and warnings reviewed.",
        },
        {
            title: "Distribution order handoff",
            steps: ["Open Opportunity Pipeline", "Move opportunity forward", "Create quotation/order", "Submit Sales Order", "Check Sales Order Pipeline", "Check stock/logistics handoff"],
            proof: "Sales order is visible in the operational pipeline and stock/logistics users can act on it.",
        },
        {
            title: "Logistics planning",
            steps: ["Open Logistics Pipeline", "Create or open Forecast Load Plan", "Select container profile", "Add source lines", "Review capacity", "Advance status"],
            proof: "Load plan shows source links, capacity usage, and lifecycle status.",
        },
        {
            title: "Installation QC",
            steps: ["Open Project Pipeline", "Open linked Project", "Apply QC template", "Open Mobile QC", "Update checklist", "Review project status"],
            proof: "Project has QC evidence and completion readiness is visible.",
        },
        {
            title: "SAV closure discipline",
            steps: ["Create SAV Ticket", "Assign technician", "Move to In Progress", "Record stock action if needed", "Attempt resolve", "Add resolution report", "Close"],
            proof: "Ticket cannot be properly closed without resolution discipline.",
        },
        {
            title: "Access governance",
            steps: ["Open Access Command Center", "Review roles", "Review company access", "Open Menu Editor", "Confirm Business Delivery visibility"],
            proof: "Authorized users see intended pages and restricted users do not see protected areas.",
        },
    ];

    const HANDOVER_ACTIONS = [
        "Use Feature Map as the training index for internal users.",
        "Use P01-P16 Fit to decide whether a requested procedure is already supported, partial, or outside automation.",
        "Use Role Playbooks for onboarding by department instead of explaining the ERP module by module.",
        "Use Acceptance scenarios as the minimum UAT checklist before PDF signoff.",
        "Use Business Delivery PDF as the management-level delivery evidence, not as a technical deployment document.",
    ];

    frappe.pages["business-delivery"].on_page_load = function (wrapper) {
        const page = frappe.ui.make_app_page({
            parent: wrapper,
            title: __("Business Delivery"),
            single_column: true,
        });
        wrapper.page = page;
        page.main.addClass("olbd-root");
        page.set_primary_action(__("Print / Save as PDF"), () => window.print(), "printer");
        injectStyles();
        render(page);
    };

    function render(page) {
        page.main.html(`
            <main class="olbd-document" aria-label="${esc(__("Orderlift Business Delivery"))}">
                ${compactHero()}
                ${tabNav()}
                <section class="olbd-panel" data-panel="overview">${overviewPanel()}</section>
                <section class="olbd-panel" data-panel="diagrams">${diagramsPanel()}</section>
                <section class="olbd-panel" data-panel="features">${featuresPanel()}</section>
                <section class="olbd-panel" data-panel="processes">${processesPanel()}</section>
                <section class="olbd-panel" data-panel="roles">${rolesPanel()}</section>
                <section class="olbd-panel" data-panel="acceptance">${acceptancePanel()}</section>
            </main>
        `);
        bind(page);
        activateTab(page, STATE.tab);
    }

    function compactHero() {
        return `
            <section class="olbd-hero">
                <div>
                    <nav class="olbd-breadcrumb" aria-label="${esc(__("Breadcrumb"))}">
                        <a href="/desk/home-page?sidebar=Main+Dashboard">${esc(__("Administration"))}</a>
                        <span>/</span>
                        <strong>${esc(__("Business Delivery"))}</strong>
                    </nav>
                    <h1>${esc(__("Orderlift Business Delivery"))}</h1>
                    <p>${esc(__("A practical map of what the app really supports: business capabilities, diagrams, pages, process fit, role playbooks, and acceptance evidence."))}</p>
                </div>
                <aside class="olbd-hero-facts">
                    <span>${esc(__("Capabilities"))}<strong>${CAPABILITIES.length}</strong></span>
                    <span>${esc(__("Diagrams"))}<strong>${DIAGRAMS.length}</strong></span>
                    <span>${esc(__("Feature Rows"))}<strong>${FEATURES.length}</strong></span>
                    <span>${esc(__("Processes"))}<strong>${PROCESSES.length}</strong></span>
                </aside>
            </section>
        `;
    }

    function tabNav() {
        return `<nav class="olbd-tabs" aria-label="${esc(__("Business Delivery Sections"))}">${TABS.map((tab) => `<button type="button" data-tab="${esc(tab.key)}">${esc(__(tab.label))}</button>`).join("")}</nav>`;
    }

    function overviewPanel() {
        return `
            ${sectionHead("Overview", "Business Capabilities", "Start here: each card explains what the client can practically do in Orderlift, where it is done, what it produces, and what the system controls.")}
            <div class="olbd-guide-grid">
                <section class="olbd-guide-card">
                    <h3>${esc(__("How To Use This Page"))}</h3>
                    <div>${PAGE_GUIDE.map((item) => `<article><strong>${esc(__(item[0]))}</strong><p>${esc(__(item[1]))}</p></article>`).join("")}</div>
                </section>
                <section class="olbd-guide-card compact">
                    <h3>${esc(__("Status Legend"))}</h3>
                    <div>${STATUS_LEGEND.map((item) => `<article class="legend-${esc(item[0].toLowerCase())}"><strong>${esc(__(item[0]))}</strong><p>${esc(__(item[1]))}</p></article>`).join("")}</div>
                </section>
            </div>
            <div class="olbd-capability-grid">${CAPABILITIES.map(capabilityCard).join("")}</div>
        `;
    }

    function diagramsPanel() {
        return `
            ${sectionHead("Diagrams", "Readable Business Diagrams", "These are swimlane-style diagrams tied to real app pages and documents. They avoid claiming automation where the app only supports an operating procedure.")}
            <div class="olbd-diagram-stack">${DIAGRAMS.map(diagramBlock).join("")}</div>
        `;
    }

    function featuresPanel() {
        return `
            ${sectionHead("Feature Map", "Where Do I Click?", "A practical feature map for management, training, and handover. It connects a business need to the page, output, and safeguard.")}
            <div class="olbd-table-wrap">
                <table class="olbd-table">
                    <thead><tr><th>${esc(__("Business Need"))}</th><th>${esc(__("Page"))}</th><th>${esc(__("Route"))}</th><th>${esc(__("What It Does"))}</th><th>${esc(__("Output"))}</th><th>${esc(__("Control"))}</th></tr></thead>
                    <tbody>${FEATURES.map(featureRow).join("")}</tbody>
                </table>
            </div>
        `;
    }

    function processesPanel() {
        return `
            ${sectionHead("P01-P16 Fit", "Process Fit Against The Real App", "Client process names are useful, but the source of truth is the running app. This matrix separates supported behavior from manual controls.")}
            <div class="olbd-process-grid">${PROCESSES.map(processCard).join("")}</div>
        `;
    }

    function rolesPanel() {
        return `
            ${sectionHead("Role Playbooks", "Daily Use By Role", "Each role card explains daily pages, actions, output, and what the app protects. This is the practical adoption layer.")}
            <div class="olbd-role-grid">${ROLES.map(roleCard).join("")}</div>
        `;
    }

    function acceptancePanel() {
        return `
            ${sectionHead("Acceptance", "Business Acceptance Evidence", "This checklist is designed for PDF export and management signoff. It focuses on observable app behavior.")}
            <div class="olbd-acceptance-grid">${ACCEPTANCE.map(acceptanceItem).join("")}</div>
            <section class="olbd-uat">
                <h3>${esc(__("Practical UAT Scenarios"))}</h3>
                <div>${UAT_SCENARIOS.map(uatScenario).join("")}</div>
            </section>
            <section class="olbd-handover">
                <h3>${esc(__("Management Handover Actions"))}</h3>
                <ol>${HANDOVER_ACTIONS.map((action) => `<li>${esc(__(action))}</li>`).join("")}</ol>
            </section>
            <section class="olbd-boundary">
                <h3>${esc(__("Important Boundary"))}</h3>
                <p>${esc(__("Orderlift supports and controls many steps through pages, documents, statuses, permissions, and safeguards. Some steps remain operating controls: commercial approval, supplier negotiation, carrier communication, physical loading, marketing production, and management corrective actions."))}</p>
            </section>
        `;
    }

    function sectionHead(kicker, title, text) {
        return `<div class="olbd-section-head"><div><p>${esc(__(kicker))}</p><h2>${esc(__(title))}</h2></div><span>${esc(__(text))}</span></div>`;
    }

    function capabilityCard(capability) {
        return `
            <article class="olbd-capability-card">
                <h3>${esc(__(capability.title))}</h3>
                <p>${esc(__(capability.summary))}</p>
                ${chipGroup("Pages", capability.pages)}
                ${chipGroup("Outputs", capability.outputs)}
                ${chipGroup("System Controls", capability.controls)}
            </article>
        `;
    }

    function diagramBlock(diagram) {
        return `
            <article class="olbd-diagram">
                <header><h3>${esc(__(diagram.title))}</h3><p>${esc(__(diagram.purpose))}</p></header>
                <div class="olbd-swimlanes">${diagram.lanes.map(laneRow).join("")}</div>
                <div class="olbd-diagram-notes">
                    <p><strong>${esc(__("Implemented in Orderlift"))}</strong>${esc(__(diagram.implemented))}</p>
                    <p><strong>${esc(__("Business operating control"))}</strong>${esc(__(diagram.manual))}</p>
                </div>
            </article>
        `;
    }

    function laneRow(lane) {
        const [label, steps] = lane;
        return `
            <div class="olbd-lane">
                <strong>${esc(__(label))}</strong>
                <div>${steps.map((step) => `<span>${esc(__(step))}</span>`).join("")}</div>
            </div>
        `;
    }

    function featureRow(row) {
        return `<tr><td><strong>${esc(__(row[0]))}</strong></td><td>${pageLink(row[1], row[2])}</td><td><a class="olbd-route" href="${esc(row[2])}">${esc(row[2])}</a></td><td>${esc(__(row[3]))}</td><td>${esc(__(row[4]))}</td><td>${esc(__(row[5]))}</td></tr>`;
    }

    function processCard(row) {
        const statusClass = row[2].toLowerCase().replace(/[^a-z]+/g, "-");
        return `
            <article class="olbd-process-card ${esc(statusClass)}">
                <div><strong>${esc(row[0])}</strong><span>${esc(__(row[2]))}</span></div>
                <h3>${esc(__(row[1]))}</h3>
                <h4>${esc(__("App support"))}</h4>
                <p>${esc(__(row[3]))}</p>
                <h4>${esc(__("Operating control"))}</h4>
                <p>${esc(__(row[4]))}</p>
            </article>
        `;
    }

    function roleCard(role) {
        return `
            <article class="olbd-role-card">
                <h3>${esc(__(role.role))}</h3>
                ${chipGroup("Daily Pages", role.pages)}
                ${chipGroup("Daily Actions", role.actions)}
                <dl><dt>${esc(__("Output"))}</dt><dd>${esc(__(role.output))}</dd><dt>${esc(__("System Protects"))}</dt><dd>${esc(__(role.protection))}</dd></dl>
            </article>
        `;
    }

    function acceptanceItem(item) {
        return `<article class="olbd-acceptance-item"><strong>${esc(__(item[0]))}</strong><p>${esc(__(item[1]))}</p></article>`;
    }

    function uatScenario(scenario) {
        return `
            <article class="olbd-uat-card">
                <h4>${esc(__(scenario.title))}</h4>
                <ol>${scenario.steps.map((step) => `<li>${esc(__(step))}</li>`).join("")}</ol>
                <p><strong>${esc(__("Proof"))}</strong>${esc(__(scenario.proof))}</p>
            </article>
        `;
    }

    function chipGroup(label, values) {
        return `<section class="olbd-chip-group"><h4>${esc(__(label))}</h4><div>${values.map(chip).join("")}</div></section>`;
    }

    function chip(value) {
        const route = ROUTES[value];
        if (route) return `<a href="${esc(route)}">${esc(__(value))}</a>`;
        return `<span>${esc(__(value))}</span>`;
    }

    function pageLink(label, route) {
        return `<a class="olbd-page-link" href="${esc(route)}">${esc(__(label))}</a>`;
    }

    function bind(page) {
        page.main.find("[data-tab]").on("click", function () {
            activateTab(page, $(this).data("tab"));
        });
    }

    function activateTab(page, tabKey) {
        STATE.tab = tabKey || "overview";
        page.main.find("[data-tab]").removeClass("active");
        page.main.find(`[data-tab="${STATE.tab}"]`).addClass("active");
        page.main.find("[data-panel]").removeClass("active");
        page.main.find(`[data-panel="${STATE.tab}"]`).addClass("active");
    }

    function esc(value) {
        return frappe.utils.escape_html(value == null ? "" : String(value));
    }

    function injectStyles() {
        if (document.getElementById("olbd-style")) return;
        const style = document.createElement("style");
        style.id = "olbd-style";
        style.textContent = `
            .olbd-root{background:#edf3f7;min-height:100vh}.olbd-document{width:min(1320px,100%);margin:0 auto;padding:16px clamp(12px,2vw,26px) 60px;color:#102033;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.olbd-hero{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:14px;align-items:center;padding:14px 16px;border:1px solid #cbddea;border-radius:18px;background:linear-gradient(135deg,#fff 0%,#edf8fb 100%);box-shadow:0 14px 32px rgba(15,31,52,.07)}.olbd-breadcrumb{display:flex;align-items:center;gap:7px;margin-bottom:5px;color:#64748b;font-size:11px;font-weight:800}.olbd-breadcrumb a{color:#0f7490;text-decoration:none}.olbd-hero h1{margin:0;color:#0b1f33;font-size:clamp(24px,3vw,36px);line-height:1;letter-spacing:-.045em}.olbd-hero p{max-width:860px;margin:7px 0 0;color:#475569;font-size:13px;line-height:1.5}.olbd-hero-facts{display:grid;grid-template-columns:repeat(4,auto);gap:7px}.olbd-hero-facts span{min-width:94px;padding:8px 10px;border:1px solid #d7e5ee;border-radius:13px;background:rgba(255,255,255,.78);color:#64748b;font-size:10px;font-weight:900;text-transform:uppercase}.olbd-hero-facts strong{display:block;margin-top:2px;color:#0f5f80;font-size:21px;line-height:1}.olbd-tabs{position:sticky;top:0;z-index:5;display:flex;gap:7px;margin:12px 0;padding:7px;border:1px solid #d7e3ec;border-radius:15px;background:rgba(255,255,255,.92);backdrop-filter:blur(12px);overflow:auto}.olbd-tabs button{min-height:36px;border:0;border-radius:11px;background:transparent;color:#475569;padding:0 13px;font-size:13px;font-weight:900;white-space:nowrap;cursor:pointer}.olbd-tabs button.active{background:#0f5f80;color:#fff;box-shadow:0 9px 20px rgba(15,95,128,.22)}.olbd-panel{display:none;padding:18px;border:1px solid #d7e3ec;border-radius:18px;background:#fff;box-shadow:0 13px 30px rgba(15,31,52,.05)}.olbd-panel.active{display:block}.olbd-section-head{display:flex;justify-content:space-between;gap:24px;align-items:flex-end;margin-bottom:16px;border-bottom:1px solid #e5edf3;padding-bottom:14px}.olbd-section-head p{margin:0 0 5px;color:#0f7490;font-size:11px;font-weight:900;letter-spacing:.14em;text-transform:uppercase}.olbd-section-head h2{margin:0;color:#0b1f33;font-size:clamp(22px,2.3vw,31px);line-height:1.06;letter-spacing:-.04em}.olbd-section-head>span{max-width:560px;color:#64748b;font-size:13px;line-height:1.55}.olbd-capability-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.olbd-capability-card,.olbd-role-card,.olbd-process-card,.olbd-diagram,.olbd-acceptance-item,.olbd-boundary{border:1px solid #d8e5ee;border-radius:17px;background:linear-gradient(180deg,#fff 0%,#f9fbfd 100%);padding:15px}.olbd-capability-card h3,.olbd-role-card h3,.olbd-process-card h3,.olbd-diagram h3,.olbd-boundary h3{margin:0;color:#102033;font-size:18px;letter-spacing:-.025em}.olbd-capability-card>p,.olbd-diagram header p,.olbd-boundary p{margin:8px 0 0;color:#475569;font-size:13px;line-height:1.55}.olbd-chip-group{margin-top:13px}.olbd-chip-group h4,.olbd-process-card h4{margin:0 0 6px;color:#102033;font-size:11px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.olbd-chip-group div{display:flex;flex-wrap:wrap;gap:6px}.olbd-chip-group span{border-radius:999px;background:#e8f8fb;color:#0f5f80;padding:5px 8px;font-size:11px;font-weight:850}.olbd-diagram-stack{display:grid;gap:13px}.olbd-swimlanes{display:grid;gap:8px;margin-top:14px}.olbd-lane{display:grid;grid-template-columns:150px minmax(0,1fr);gap:10px;align-items:stretch}.olbd-lane>strong{display:flex;align-items:center;border-radius:12px;background:#0b1f33;color:#fff;padding:10px 12px;font-size:12px}.olbd-lane>div{display:flex;flex-wrap:wrap;gap:8px;padding:9px;border:1px solid #d8e5ee;border-radius:12px;background:#fff}.olbd-lane span{position:relative;border:1px solid #cfe0ea;border-radius:999px;background:#f8fbfd;color:#334155;padding:7px 10px;font-size:12px;font-weight:850}.olbd-lane span:not(:last-child)::after{content:"";position:absolute;right:-9px;top:50%;width:8px;height:1px;background:#9bb8c8}.olbd-diagram-notes{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:12px}.olbd-diagram-notes p{margin:0;border-radius:13px;background:#fff;padding:11px;color:#475569;font-size:12px;line-height:1.5}.olbd-diagram-notes strong{display:block;margin-bottom:5px;color:#102033;font-size:11px;letter-spacing:.08em;text-transform:uppercase}.olbd-table-wrap{overflow:auto;border:1px solid #d8e5ee;border-radius:15px;background:#fff}.olbd-table{width:100%;border-collapse:collapse;min-width:1020px}.olbd-table th{background:#0b1f33;color:#fff;text-align:left;font-size:11px;letter-spacing:.08em;text-transform:uppercase}.olbd-table th,.olbd-table td{padding:12px 13px;border-bottom:1px solid #e5edf3;vertical-align:top}.olbd-table td{color:#334155;font-size:12px;line-height:1.48}.olbd-table code{display:inline-block;border-radius:8px;background:#eef6fa;color:#0f5f80;padding:3px 7px;font-size:11px}.olbd-process-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.olbd-process-card div:first-child{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.olbd-process-card div:first-child strong{display:inline-flex;align-items:center;justify-content:center;border-radius:999px;background:#0f5f80;color:#fff;padding:4px 8px;font-size:11px}.olbd-process-card div:first-child span{border-radius:999px;background:#e8f8fb;color:#0f5f80;padding:4px 8px;font-size:10px;font-weight:900;text-align:right}.olbd-process-card.partial div:first-child span{background:#fff7ed;color:#c2410c}.olbd-process-card.operating div:first-child span{background:#f1f5f9;color:#475569}.olbd-process-card h3{margin-top:10px;font-size:15px}.olbd-process-card h4{margin-top:11px}.olbd-process-card p{margin:0;color:#64748b;font-size:12px;line-height:1.45}.olbd-role-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.olbd-role-card dl{display:grid;grid-template-columns:120px 1fr;gap:8px 10px;margin:14px 0 0}.olbd-role-card dt{color:#102033;font-size:11px;font-weight:900;text-transform:uppercase}.olbd-role-card dd{margin:0;color:#64748b;font-size:12px;line-height:1.5}.olbd-acceptance-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.olbd-acceptance-item strong{display:block;color:#0f5f80;font-size:13px}.olbd-acceptance-item p{margin:6px 0 0;color:#475569;font-size:13px;line-height:1.5}.olbd-boundary{margin-top:12px;border-style:dashed;background:#fbfdff}@media (max-width:1100px){.olbd-hero{grid-template-columns:1fr}.olbd-hero-facts{grid-template-columns:repeat(4,minmax(0,1fr))}.olbd-capability-grid,.olbd-process-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.olbd-lane{grid-template-columns:130px minmax(0,1fr)}}@media (max-width:720px){.olbd-document{padding-inline:10px}.olbd-hero,.olbd-panel{border-radius:15px}.olbd-hero-facts,.olbd-capability-grid,.olbd-process-grid,.olbd-role-grid,.olbd-acceptance-grid,.olbd-diagram-notes{grid-template-columns:1fr}.olbd-section-head{display:block}.olbd-section-head>span{display:block;margin-top:8px}.olbd-lane{grid-template-columns:1fr}.olbd-lane span:not(:last-child)::after{display:none}}@media print{@page{size:A4;margin:12mm}body{background:#fff!important}.layout-main-section,.olbd-root{background:#fff!important}.page-head,.navbar,.layout-side-section,.standard-sidebar,.desk-sidebar,.search-bar,.btn,.page-actions,.olbd-tabs{display:none!important}.olbd-document{width:100%;max-width:none;padding:0;color:#0b1f33}.olbd-hero,.olbd-panel,.olbd-capability-card,.olbd-role-card,.olbd-process-card,.olbd-diagram,.olbd-acceptance-item,.olbd-boundary{box-shadow:none;border-color:#b8c9d4;break-inside:avoid;page-break-inside:avoid}.olbd-panel{display:block!important;margin-top:10px;padding:14px}.olbd-hero{padding:12px}.olbd-hero h1{font-size:26px}.olbd-hero-facts{grid-template-columns:repeat(4,1fr)}.olbd-section-head h2{font-size:22px}.olbd-capability-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.olbd-process-grid{grid-template-columns:repeat(4,minmax(0,1fr))}.olbd-role-grid,.olbd-acceptance-grid,.olbd-diagram-notes{grid-template-columns:repeat(2,minmax(0,1fr))}.olbd-table{min-width:0}.olbd-table th,.olbd-table td{padding:7px 8px;font-size:9px}.olbd-breadcrumb{display:none}.olbd-lane{grid-template-columns:105px minmax(0,1fr)}.olbd-lane span{font-size:9px;padding:5px 7px}.olbd-chip-group span{font-size:9px}}
        `;
        style.textContent += `
            .olbd-guide-grid{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(280px,.75fr);gap:12px;margin-bottom:12px}.olbd-guide-card{border:1px solid #d8e5ee;border-radius:17px;background:#f9fbfd;padding:15px}.olbd-guide-card h3,.olbd-uat h3,.olbd-handover h3{margin:0 0 12px;color:#102033;font-size:18px;letter-spacing:-.025em}.olbd-guide-card>div{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.olbd-guide-card.compact>div{grid-template-columns:1fr}.olbd-guide-card article{border:1px solid #d8e5ee;border-radius:13px;background:#fff;padding:11px}.olbd-guide-card article strong{display:block;color:#0f5f80;font-size:12px}.olbd-guide-card article p{margin:5px 0 0;color:#64748b;font-size:12px;line-height:1.45}.olbd-guide-card .legend-supported strong{color:#0f7490}.olbd-guide-card .legend-partial strong{color:#c2410c}.olbd-guide-card .legend-operating strong{color:#475569}.olbd-chip-group a{border-radius:999px;background:#e8f8fb;color:#0f5f80;padding:5px 8px;font-size:11px;font-weight:850;text-decoration:none}.olbd-chip-group a:hover,.olbd-page-link:hover,.olbd-route:hover{text-decoration:underline}.olbd-page-link{color:#0f5f80;font-weight:900;text-decoration:none}.olbd-route{display:inline-block;border-radius:8px;background:#eef6fa;color:#0f5f80;padding:3px 7px;font-size:11px;text-decoration:none}.olbd-uat,.olbd-handover{margin-top:12px;border:1px solid #d8e5ee;border-radius:17px;background:#f9fbfd;padding:15px}.olbd-uat>div{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.olbd-uat-card{border:1px solid #d8e5ee;border-radius:14px;background:#fff;padding:12px}.olbd-uat-card h4{margin:0 0 8px;color:#102033;font-size:14px}.olbd-uat-card ol,.olbd-handover ol{margin:0;padding-left:18px;color:#475569;font-size:12px;line-height:1.55}.olbd-uat-card p{margin:9px 0 0;color:#64748b;font-size:12px;line-height:1.45}.olbd-uat-card p strong{display:block;color:#102033;font-size:11px;text-transform:uppercase;letter-spacing:.08em}.olbd-handover li{margin-bottom:5px}@media (max-width:1100px){.olbd-guide-grid{grid-template-columns:1fr}.olbd-uat>div{grid-template-columns:repeat(2,minmax(0,1fr))}}@media (max-width:720px){.olbd-guide-card>div,.olbd-uat>div{grid-template-columns:1fr}}@media print{.olbd-guide-grid{grid-template-columns:1fr}.olbd-uat>div{grid-template-columns:repeat(2,minmax(0,1fr))}.olbd-chip-group a{font-size:9px}.olbd-uat,.olbd-handover,.olbd-guide-card,.olbd-uat-card{box-shadow:none;border-color:#b8c9d4;break-inside:avoid;page-break-inside:avoid}}
        `;
        document.head.appendChild(style);
    }
})();
