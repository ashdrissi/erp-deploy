frappe.pages["dimensioning-set-builder"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Dimensioning Set Builder"),
        single_column: true,
    });

    wrapper.page = page;
    page.main.addClass("ods-builder-root");
    injectDimensioningBuilderStyles();
    resetDimensioningBuilderState();
    renderDimensioningBuilder(page);
    applyDimensioningBuilderHeader(page);
    loadInitialDimensioningSet(page);
};

frappe.pages["dimensioning-set-builder"].on_page_show = function (wrapper) {
    if (!wrapper.page) return;
    applyDimensioningBuilderHeader(wrapper.page);
    if (frappe.route_options?.dimensioning_set || frappe.route_options?.new_dimensioning_set) {
        loadInitialDimensioningSet(wrapper.page);
    }
};

const ODS_FIELD_TYPES = ["Int", "Float", "Data", "Select", "Check"];
const ODS_CONDITION_OPERATORS = ["==", "!=", ">", ">=", "<", "<="];
const ODS_ITEM_FILTER_OPERATORS = ["==", "!=", "contains", ">", ">=", "<", "<="];
const ODS_ITEM_FILTER_FIELDS = [
    { value: "item_group", label: "Item Group" },
    { value: "brand", label: "Brand" },
    { value: "custom_material", label: "Material" },
    { value: "custom_length_cm", label: "Length (cm)" },
    { value: "custom_width_cm", label: "Width (cm)" },
    { value: "custom_height_cm", label: "Height (cm)" },
    { value: "item_name", label: "Item Name" },
];
const ODS_NAV_ITEMS = [
    { key: "start", label: "Start", step: "01" },
    { key: "questions", label: "Form", step: "02" },
    { key: "logic", label: "Articles", step: "03" },
    { key: "preview", label: "Test", step: "04" },
];

const ODS_SAMPLE_ITEMS = [
    { item: "IT.1-1", item_name: "Cabine inox standard", item_group: "CABINE & ARCADE", unit: "Pc" },
    { item: "IT.1-7", item_name: "Arcade cabine et contre-poids", item_group: "CABINE & ARCADE", unit: "SET" },
    { item: "IT.3", item_name: "Porte paliere automatique epoxy", item_group: "PORTE", unit: "Pc" },
    { item: "IT.4", item_name: "Operateur automatique", item_group: "OPERATEUR", unit: "Pc" },
    { item: "IT.57", item_name: "Bouton palier avec afficheur", item_group: "BOUTONS", unit: "Pc" },
    { item: "IT.69", item_name: "Armoire VVVF", item_group: "ARMOIRE", unit: "SET" },
    { item: "IT.98", item_name: "Demo article needing a price", item_group: "OPTION", unit: "Pc", missing_price: true },
];
const ODS_ITEM_CACHE = Object.fromEntries(ODS_SAMPLE_ITEMS.map((row) => [row.item, row]));
const ODS_ITEM_LINK_CONTROLS = new Map();

const ODS_INITIAL_SETS = [
    {
        name: "Ascenseur Complet",
        description: "Configuration for a complete lift package. All business fields are config-driven.",
        is_active: true,
        fields: [
            fieldRow("lift_type", "Type", "Select", "VVVF", "VVVF\nHYDRAULIQUE\nGEARLESS\n2V", true, "Main technical family", "General"),
            fieldRow("persons", "Personnes", "Int", "4", "", true, "Capacity requested by customer", "General"),
            fieldRow("levels", "Niveaux", "Int", "4", "", true, "Number of stops/levels", "General"),
            fieldRow("door_material", "Porte materiau", "Select", "EPOXY", "EPOXY\nINOX\nPANORAMIQUE", false, "Door finish", "Doors"),
            fieldRow("door_type", "Porte type", "Select", "AUTOMATIQUE", "AUTOMATIQUE\nSEMI", false, "Door mechanism", "Doors"),
            fieldRow("tactile_button", "Bouton tactile", "Check", "0", "", false, "If enabled, skip standard cabin button", "Options"),
        ],
        derived_fields: [
            derivedRow("capacity_class", "Capacite", "Data", 'ifelse(persons < 5, "MAX4", ifelse(persons < 7, "MAX6", ifelse(persons < 9, "MAX8", "MAX10")))', "Derived from persons", "General"),
            derivedRow("door_count", "Nombre de portes", "Int", "levels", "Default door count follows levels", "Doors"),
        ],
        item_rules: [
            ruleRow("Cabine standard", "IT.1-1", "CABINE & ARCADE", "1", "", true),
            ruleRow("Arcades", "IT.1-7", "CABINE & ARCADE", "1", "", true),
            ruleRow("Portes palieres", "IT.3", "PORTE", "door_count", 'door_type == "AUTOMATIQUE"', true),
            ruleRow("Operateur", "IT.4", "OPERATEUR", "1", 'door_type == "AUTOMATIQUE"', true),
            ruleRow("Boutons palier", "IT.57", "BOUTONS", "levels", "", true),
            ruleRow("Armoire VVVF", "IT.69", "ARMOIRE", "1", 'lift_type == "VVVF"', true),
            ruleRow("Option tactile alternative", "IT.98", "OPTION", "1", "tactile_button", false),
        ],
    },
    {
        name: "Pieces Detachees",
        description: "Small article-selection set proving that the builder is not tied to elevator package fields.",
        is_active: true,
        fields: [
            fieldRow("family", "Famille", "Select", "PORTE", "PORTE\nBOUTONS\nAUTRES", true, "Which article family to include", "Selection"),
            fieldRow("quantity", "Quantite", "Int", "1", "", true, "Requested quantity", "Selection"),
        ],
        derived_fields: [derivedRow("is_bulk", "Commande volume", "Check", "quantity >= 5", "Used by preview warnings", "Selection")],
        item_rules: [
            ruleRow("Porte unitaire", "IT.3", "PORTE", "quantity", 'family == "PORTE"', true),
            ruleRow("Bouton palier", "IT.57", "BOUTONS", "quantity", 'family == "BOUTONS"', true),
        ],
    },
];

const ODS_STATE = {
    sets: [],
    selectedSet: 0,
    activeSection: "start",
    selectedRule: 0,
    selectedFieldToken: "",
    openQuestionCards: {},
    openRuleGroups: {},
    openArticleSettings: {},
    testValues: {},
    validation: [],
    lastPreview: null,
    isSaving: false,
};

function fieldRow(field_key, label, field_type, default_value, options, is_required, help_text, group) {
    return { field_key, label, field_type, default_value, options, is_required: !!is_required, help_text, group };
}

function derivedRow(field_key, label, field_type, formula, help_text, group) {
    return { field_key, label, field_type, formula, help_text, group };
}

function ruleRow(rule_label, item, display_group, qty_formula, condition_formula, show_in_detail) {
    const condition = parseStructuredCondition(condition_formula);
    const quantity = parseQuantityFormula(qty_formula);
    return {
        sequence: 10,
        is_active: true,
        rule_label,
        item_selection_mode: "fixed",
        item,
        item_filters: [],
        item_filters_json: "",
        display_group,
        qty_formula,
        condition_formula,
        show_in_detail: !!show_in_detail,
        condition_mode: condition.mode,
        question_key: condition.question_key,
        operator: condition.operator,
        compare_source: condition.compare_source,
        manual_value: condition.manual_value,
        compare_question_key: condition.compare_question_key,
        quantity_mode: quantity.mode,
        fixed_qty: quantity.fixed_qty,
        quantity_question_key: quantity.quantity_question_key,
    };
}

function resetDimensioningBuilderState() {
    ODS_STATE.sets = JSON.parse(JSON.stringify(ODS_INITIAL_SETS));
    ODS_STATE.selectedSet = 0;
    ODS_STATE.activeSection = "start";
    ODS_STATE.selectedRule = 0;
    ODS_STATE.selectedFieldToken = "";
    ODS_STATE.openQuestionCards = {};
    ODS_STATE.openRuleGroups = {};
    ODS_STATE.openArticleSettings = {};
    ODS_STATE.testValues = buildDefaultValues(getActiveSet());
    ODS_STATE.validation = [];
    ODS_STATE.lastPreview = null;
}

function newBlankDimensioningSet() {
    return {
        docname: "",
        name: __("New Dimensioning Set"),
        description: "",
        is_active: true,
        fields: [],
        derived_fields: [],
        item_rules: [],
    };
}

function applyDimensioningBuilderHeader(page) {
    page.set_title(__("Dimensioning Set Builder"));
    page.clear_actions_menu();
    page.set_primary_action(__("Save Dimensioning Set"), () => saveActiveDimensioningSet(page));
    page.add_action_item(__("Run Test"), () => {
        ODS_STATE.activeSection = "preview";
        ODS_STATE.lastPreview = buildPreview(getActiveSet(), ODS_STATE.testValues);
        ODS_STATE.validation = validateSet(getActiveSet(), ODS_STATE.lastPreview);
        renderDimensioningBuilder(page);
    });
    page.add_action_item(__("Load Existing Set"), () => promptLoadDimensioningSet(page));
    page.add_action_item(__("Delete Dimensioning Set"), () => confirmDeleteActiveDimensioningSet(page));
    page.add_action_item(__("Reset Sample Data"), () => {
        resetDimensioningBuilderState();
        renderDimensioningBuilder(page);
    });
    setTimeout(() => {
        if (!frappe.breadcrumbs) return;
        frappe.breadcrumbs.clear();
        frappe.breadcrumbs.append_breadcrumb_element("/desk/pricing-dashboard", __("Sales"), "title-text");
        frappe.breadcrumbs.append_breadcrumb_element("", __("Dimensioning Set Builder"), "title-text");
        frappe.breadcrumbs.toggle(true);
    }, 0);
}

function getActiveSet() {
    return ODS_STATE.sets[ODS_STATE.selectedSet] || ODS_STATE.sets[0];
}

function renderDimensioningBuilder(page) {
    const set = getActiveSet();
    const preview = ODS_STATE.lastPreview || buildPreview(set, ODS_STATE.testValues);
    const validation = ODS_STATE.validation.length ? ODS_STATE.validation : validateSet(set, preview);
    const content = `
        <div class="ods-shell">
            ${renderHero(set, preview, validation)}
            ${renderNavigation()}
            <div class="ods-workspace">
                <main class="ods-editor">${renderActiveSection(set, preview, validation)}</main>
            </div>
            ${renderBottomBar(set, validation)}
        </div>
    `;
    page.main.html(content);
    bindDimensioningBuilderEvents(page);
    updateDimensioningSaveState(page);
}

function renderHero(set, preview, validation) {
    const generatedCount = (preview.generated || []).length;
    const errorCount = validation.filter((row) => row.level === "error").length;
    const warningCount = validation.filter((row) => row.level === "warning").length;
    const ruleGroupCount = getArticleRuleGroups(set).length;
    return `
        <section class="ods-hero">
            <div>
                <div class="ods-eyebrow">${__("Admin Builder")}</div>
                <h1>${frappe.utils.escape_html(set.name)}</h1>
                <p>${frappe.utils.escape_html(set.description || "")}</p>
            </div>
            <div class="ods-hero-stats">
                ${metricCard(__("Questions"), set.fields.length)}
                ${metricCard(__("Rules"), ruleGroupCount)}
                ${metricCard(__("Generated"), generatedCount)}
                ${metricCard(__("Issues"), warningCount + errorCount, errorCount ? "danger" : warningCount ? "warn" : "ok")}
            </div>
        </section>
    `;
}

function metricCard(label, value, tone = "") {
    return `<div class="ods-metric ${tone}"><span>${label}</span><strong>${value}</strong></div>`;
}

function renderNavigation() {
    const items = ODS_NAV_ITEMS.map((item) => `
        <button class="ods-nav-item ${ODS_STATE.activeSection === item.key ? "active" : ""}" data-nav="${item.key}" type="button">
            <span>${frappe.utils.escape_html(item.step)}</span>
            <strong>${frappe.utils.escape_html(__(item.label))}</strong>
        </button>
    `).join("");
    return `<nav class="ods-nav" aria-label="${frappe.utils.escape_html(__("Dimensioning builder sections"))}"><div class="ods-nav-title">${__("Guided Builder")}</div>${items}</nav>`;
}

function renderActiveSection(set, preview, validation) {
    if (ODS_STATE.activeSection === "questions") return renderQuestionsSection(set);
    if (ODS_STATE.activeSection === "logic") return renderLogicSection(set);
    if (ODS_STATE.activeSection === "preview") return renderPreviewSection(set, preview, validation);
    if (ODS_STATE.activeSection === "payload") return renderPayloadSection(set);
    return renderStartSection(set, preview, validation);
}

function renderStartSection(set, preview, validation) {
    const errorCount = validation.filter((row) => row.level === "error").length;
    return `
        <section class="ods-card">
            <div class="ods-section-head">
                <div>
                    <h2>${__("Build the form, then decide which articles it creates")}</h2>
                    <p>${__("Build a guided sales form on one side, generated articles on the other, with technical details hidden until needed.")}</p>
                </div>
                <span class="ods-badge preview">${__("Draft preview")}</span>
            </div>
            <div class="ods-start-grid">
                <div class="ods-start-main">
                    <div class="ods-form-grid two">
                        ${textInput("set-name", __("Builder name"), set.name)}
                        ${selectInput("set-active", __("Availability"), set.is_active ? "Active" : "Inactive", ["Active", "Inactive"])}
                        <label class="ods-field wide">
                            <span>${__("Short explanation for admins")}</span>
                            <textarea data-set-field="description" rows="3">${frappe.utils.escape_html(set.description || "")}</textarea>
                        </label>
                    </div>
                    <div class="ods-next-actions">
                        <button class="btn btn-primary" type="button" data-nav="questions">${__("Design the form")}</button>
                        <button class="btn btn-default" type="button" data-nav="preview">${__("Open test panel")}</button>
                        <button class="btn btn-default" type="button" data-save-builder ${ODS_STATE.isSaving ? "disabled" : ""}>${ODS_STATE.isSaving ? __("Saving...") : __("Save Dimensioning Set")}</button>
                    </div>
                </div>
                <div class="ods-simple-summary">
                    ${simpleStep("1", __("Design the form"), `${set.fields.length} ${__("questions")}`, "questions")}
                    ${simpleStep("2", __("Attach articles"), `${set.item_rules.length} ${__("article rules")}`, "logic")}
                    ${simpleStep("3", __("Optional calculations"), `${set.derived_fields.length} ${__("hidden values")}`, "logic")}
                    ${simpleStep("4", __("Test before saving"), errorCount ? `${errorCount} ${__("issue(s) to review")}` : `${(preview.generated || []).length} ${__("items generated")}`, "preview")}
                </div>
            </div>
        </section>
        <section class="ods-card ods-guidance">
            <h3>${__("How to think about it")}</h3>
            <div class="ods-guidance-grid">
                ${guidanceItem(__("Form"), __("The simple questions a salesperson sees in Pricing Sheet."))}
                ${guidanceItem(__("Article"), __("A line that appears automatically when answers match the rule."))}
                ${guidanceItem(__("Test"), __("Try real answers and check the generated article list before saving."))}
            </div>
        </section>
    `;
}

function simpleStep(number, title, text, target) {
    return `
        <button class="ods-simple-step" type="button" data-nav="${target}">
            <span>${number}</span>
            <div><strong>${title}</strong><small>${text}</small></div>
        </button>
    `;
}

function renderQuestionsSection(set) {
    return `
        ${renderQuickExplain(
            __("The sales form"),
            __("Start from what the salesperson should understand. Technical keys are hidden in each question's advanced section.")
        )}
        ${renderParametersSection(set)}
    `;
}

function renderLogicSection(set) {
    return `
        ${renderQuickExplain(
            __("Generated articles"),
            __("Build one condition, then attach every article that should appear when that condition is true.")
        )}
        ${renderRulesSection(set)}
    `;
}

function renderQuickExplain(title, text) {
    return `<section class="ods-quick-explain"><strong>${title}</strong><span>${text}</span></section>`;
}

function guidanceItem(title, text) {
    return `<div><strong>${title}</strong><p>${text}</p></div>`;
}

function renderParametersSection(set) {
    const rows = set.fields.map((field, index) => renderParameterCard(field, index)).join("");
    return `
        <section class="ods-card">
            <div class="ods-section-head">
                <div>
                    <h2>${__("Form questions")}</h2>
                    <p>${__("Left side shows the clean salesperson form. Right side edits the questions behind it.")}</p>
                </div>
                <button class="btn btn-default btn-sm" type="button" data-add-field>${__("Add Question")}</button>
            </div>
            <div class="ods-question-layout">
                <div class="ods-sales-preview-card">
                    <div class="ods-preview-title">
                        <strong>${__("Salesperson sees")}</strong>
                        <span>${__("Pricing Sheet form preview")}</span>
                    </div>
                    <div class="ods-sales-preview-list">
                        ${set.fields.map(renderSalesPreviewQuestion).join("")}
                    </div>
                </div>
                <div class="ods-question-edit-list">
                    <div class="ods-preview-title">
                        <strong>${__("Admin edits")}</strong>
                        <span>${__("Labels, choices, defaults, and help text")}</span>
                    </div>
                    <div class="ods-list">${rows}</div>
                </div>
            </div>
        </section>
    `;
}

function renderSalesPreviewQuestion(field) {
    const required = field.is_required ? `<span class="ods-required-dot">${__("Required")}</span>` : "";
    return `
        <div class="ods-sales-question">
            <label>${frappe.utils.escape_html(field.label || field.field_key)} ${required}</label>
            ${renderDisabledControl(field)}
            ${field.help_text ? `<small>${frappe.utils.escape_html(field.help_text)}</small>` : ""}
        </div>
    `;
}

function renderDisabledControl(field) {
    const value = frappe.utils.escape_html(field.default_value || "");
    if (field.field_type === "Select") {
        const options = splitOptions(field.options).map((option) => `<option ${option === field.default_value ? "selected" : ""}>${frappe.utils.escape_html(option)}</option>`).join("");
        return `<select disabled>${options}</select>`;
    }
    if (field.field_type === "Check") {
        return `<label class="ods-preview-check"><input type="checkbox" disabled ${coerceBuilderValue("Check", field.default_value) ? "checked" : ""}> <span>${__("Enabled")}</span></label>`;
    }
    const type = ["Int", "Float"].includes(field.field_type) ? "number" : "text";
    return `<input type="${type}" disabled value="${value}">`;
}

function renderParameterCard(field, index) {
    const isOpen = !!ODS_STATE.openQuestionCards[index];
    const helpText = (field.help_text || "").trim();
    return `
        <article class="ods-row-card ods-question-card ${isOpen ? "is-open" : "is-collapsed"}" data-question-card="${index}">
            <div class="ods-row-top" data-toggle-question="${index}" role="button" tabindex="0" aria-expanded="${isOpen ? "true" : "false"}">
                <span class="ods-row-index">${index + 1}</span>
                <div class="ods-question-summary-copy">
                    <span class="ods-hierarchy-kicker">${__("Question")}</span>
                    <strong>${frappe.utils.escape_html(field.label || field.field_key)}</strong>
                    ${helpText ? `<small>${frappe.utils.escape_html(helpText)}</small>` : ""}
                </div>
                <div class="ods-article-status">
                    <span class="ods-badge">${frappe.utils.escape_html(field.field_type)}</span>
                    ${field.is_required ? `<span class="ods-badge warn">${__("Required")}</span>` : ""}
                </div>
                <span class="ods-rule-toggle-indicator">${isOpen ? __("Collapse") : __("Edit")}</span>
                <button class="ods-icon-button danger" type="button" data-remove-field="${index}" aria-label="${__("Remove parameter")}">×</button>
            </div>
            ${isOpen ? `<div class="ods-question-card-body">
                <div class="ods-form-grid two">
                    ${inlineInput("field", index, "label", __("Question label"), field.label)}
                    ${inlineSelect("field", index, "field_type", __("Answer type"), field.field_type, ODS_FIELD_TYPES)}
                    ${inlineInput("field", index, "default_value", __("Default answer"), field.default_value || "")}
                    ${inlineInput("field", index, "group", __("Section"), field.group || "")}
                    ${inlineCheck("field", index, "is_required", __("Required"), field.is_required)}
                    <label class="ods-field wide">
                        <span>${__("Choices, one per line")}</span>
                        <textarea data-update-kind="field" data-update-index="${index}" data-update-field="options" rows="3">${frappe.utils.escape_html(field.options || "")}</textarea>
                    </label>
                    <label class="ods-field wide">
                        <span>${__("Help text shown to the user")}</span>
                        <input data-update-kind="field" data-update-index="${index}" data-update-field="help_text" value="${frappe.utils.escape_html(field.help_text || "")}">
                    </label>
                </div>
                <details class="ods-advanced-inline">
                    <summary>${__("Technical key")}</summary>
                    ${inlineInput("field", index, "field_key", __("Field key"), field.field_key)}
                </details>
            </div>` : ""}
        </article>
    `;
}

function renderDerivedSection(set, embedded = false) {
    const rows = set.derived_fields.map((field, index) => renderDerivedCard(field, index, set)).join("");
    const content = `
            <div class="ods-section-head">
                <div>
                    <h2>${__("Hidden Calculations")}</h2>
                    <p>${__("Optional. Use these to simplify rules when the same calculation is reused several times.")}</p>
                </div>
                <button class="btn btn-default btn-sm" type="button" data-add-derived>${__("Add Calculation")}</button>
            </div>
            <div class="ods-helper-strip">
                <span class="ods-helper-label">${__("Available values")}</span>
                ${renderTokenButtons(set)}
            </div>
            <div class="ods-list">${rows}</div>
    `;
    if (embedded) return `<div class="ods-derived-embedded">${content}</div>`;
    return `
        <section class="ods-card">
            ${content}
        </section>
    `;
}

function renderDerivedCard(field, index) {
    return `
        <article class="ods-row-card">
            <div class="ods-row-top">
                <span class="ods-row-index">${index + 1}</span>
                <strong>${frappe.utils.escape_html(field.label || field.field_key)}</strong>
                <span class="ods-badge">${frappe.utils.escape_html(field.field_type)}</span>
                <button class="ods-icon-button danger" type="button" data-remove-derived="${index}" aria-label="${__("Remove derived value")}">×</button>
            </div>
            <div class="ods-form-grid three">
                ${inlineInput("derived", index, "label", __("Calculation name"), field.label)}
                ${inlineSelect("derived", index, "field_type", __("Result type"), field.field_type, ODS_FIELD_TYPES)}
                ${inlineInput("derived", index, "group", __("Section"), field.group || "")}
                <label class="ods-field wide">
                    <span>${__("Formula")}</span>
                    <textarea class="ods-code-input" data-update-kind="derived" data-update-index="${index}" data-update-field="formula" rows="3">${frappe.utils.escape_html(field.formula || "")}</textarea>
                    <small>${__("Example: levels, quantity >= 5, or ifelse(persons < 5, \"MAX4\", \"MAX6\")")}</small>
                </label>
                <label class="ods-field wide">
                    <span>${__("Help text")}</span>
                    <input data-update-kind="derived" data-update-index="${index}" data-update-field="help_text" value="${frappe.utils.escape_html(field.help_text || "")}">
                </label>
            </div>
            <details class="ods-advanced-inline">
                <summary>${__("Technical key")}</summary>
                ${inlineInput("derived", index, "field_key", __("Calculation key"), field.field_key)}
            </details>
        </article>
    `;
}

function renderRulesSection(set) {
    const groups = getArticleRuleGroups(set);
    const rows = groups.map((group, index) => renderArticleRuleGroup(group, index, set)).join("");
    return `
        <section class="ods-card">
            <div class="ods-section-head">
                <div>
                    <h2>${__("Rules that generate articles")}</h2>
                    <p>${__("Create one rule from the answers, then choose all articles that should be added by that rule.")}</p>
                </div>
                <button class="btn btn-default btn-sm" type="button" data-add-rule>${__("Add Rule")}</button>
            </div>
            <div class="ods-article-list">${rows || renderEmptyRuleState()}</div>
        </section>
    `;
}

function renderArticleRuleGroup(group, groupIndex, set) {
    const conditionMode = group.condition_state.mode || "always";
    const hasFormula = group.rules.some(({ rule }) => rule.uses_advanced_formula);
    const conditionLabel = describeConditionGroup(group, set);
    const articles = group.rules.map(({ rule, index }, articleIndex) => renderArticleRuleRow(rule, index, articleIndex, set)).join("");
    const articlePreview = renderRuleGroupArticlePreview(group, set);
    const isOpen = !!ODS_STATE.openRuleGroups[groupIndex];
    return `
        <article class="ods-rule-group-card ${isOpen ? "is-open" : "is-collapsed"}" data-rule-group-card="${groupIndex}">
            <div class="ods-rule-group-head" data-toggle-rule-group="${groupIndex}" role="button" tabindex="0" aria-expanded="${isOpen ? "true" : "false"}">
                <div class="ods-article-number">${groupIndex + 1}</div>
                <div>
                    <span class="ods-hierarchy-kicker">${__("Rule")} ${groupIndex + 1}</span>
                    <h3>${hasFormula ? __("Workbook formulas") : conditionMode === "always" ? __("Always included") : __("Based on one answer")}</h3>
                    <p>${frappe.utils.escape_html(hasFormula ? __("Each article uses its imported quantity formula.") : conditionLabel)}</p>
                    ${articlePreview}
                </div>
                <div class="ods-article-status">
                    <span class="ods-badge ${hasFormula || conditionMode !== "always" ? "warn" : ""}">${hasFormula ? __("Formula") : conditionMode === "always" ? __("Always") : __("Conditional")}</span>
                    <span class="ods-badge ok-soft">${group.rules.length} ${__("article(s)")}</span>
                </div>
                <span class="ods-rule-toggle-indicator">${isOpen ? __("Collapse") : __("Expand")}</span>
            </div>
            ${isOpen ? `<div class="ods-rule-group-body">
                <div class="ods-hierarchy-block when">
                    <div class="ods-hierarchy-label">${__("WHEN")}</div>
                    ${hasFormula ? renderWorkbookFormulaCondition(group) : renderRuleConditionControls(group, groupIndex, set)}
                </div>
                <div class="ods-hierarchy-block then">
                    <div class="ods-group-articles-head">
                        <div>
                            <div class="ods-hierarchy-label">${__("THEN")}</div>
                            <strong>${__("Articles to add")}</strong>
                        </div>
                        <button class="btn btn-xs btn-default" type="button" data-add-rule-article="${groupIndex}">${__("Add Article")}</button>
                    </div>
                    <div class="ods-group-article-list" role="list">${articles || renderEmptyArticleRows()}</div>
                    <details class="ods-article-picker-details">
                        <summary>${__("Quick add from sample catalog")}</summary>
                        ${renderArticlePicker(groupIndex)}
                    </details>
                </div>
            </div>` : ""}
        </article>
    `;
}

function renderRuleGroupArticlePreview(group, set) {
    if (!group.rules.length) return "";
    const chips = group.rules.slice(0, 4).map(({ rule }) => {
        const item = (rule.item_selection_mode || "fixed") === "filtered" ? describeItemFilters(rule) : rule.item || __("Item");
        return `<span>${frappe.utils.escape_html(item)} <strong>x ${frappe.utils.escape_html(describeRuleQuantity(rule, set))}</strong></span>`;
    }).join("");
    const overflow = group.rules.length > 4 ? `<span>${__("+ {0} more", [group.rules.length - 4])}</span>` : "";
    return `<div class="ods-rule-group-preview">${chips}${overflow}</div>`;
}

function renderArticlePicker(groupIndex) {
    return `
        <div class="ods-article-picker">
            <button class="btn btn-xs btn-primary" type="button" data-open-item-picker="${groupIndex}">${__("Choose Item from Catalog")}</button>
            <div>
                ${ODS_SAMPLE_ITEMS.map((item) => `
                    <button class="ods-picker-chip" type="button" data-add-catalog-article="${groupIndex}" data-catalog-item="${frappe.utils.escape_html(item.item)}">
                        <strong>${frappe.utils.escape_html(item.item)}</strong>
                        <small>${frappe.utils.escape_html(item.item_name)}</small>
                    </button>
                `).join("")}
            </div>
        </div>
    `;
}

function renderWorkbookFormulaCondition(group) {
    const examples = group.rules.slice(0, 2).map(({ rule }) => `
        <code>${frappe.utils.escape_html((rule.qty_formula || "0").trim())}</code>
    `).join("");
    return `
        <div class="ods-rule-condition-card ods-formula-rule-note">
            <div class="ods-condition-summary">
                <span>${__("Imported workbook logic")}</span>
                <strong>${__("The Excel formula decides whether each article is added and in what quantity.")}</strong>
            </div>
            <div class="ods-rule-group-preview">${examples}</div>
        </div>
    `;
}

function renderRuleConditionControls(group, groupIndex, set) {
    const state = group.condition_state;
    const mode = state.mode || "always";
    const selectedField = state.question_key || getQuestionKeys(set)[0] || "";
    const operator = getCompatibleOperator(set, selectedField, state.operator || "==");
    const compareSource = state.compare_source || "manual";
    const manualValue = state.manual_value || defaultComparisonValue(getContextField(set, selectedField));
    const compareQuestion = state.compare_question_key || getQuestionKeys(set).find((key) => key !== selectedField) || selectedField;
    return `
        <div class="ods-rule-condition-card">
            <label class="ods-field">
                <span>${__("When should this rule apply?")}</span>
                <select data-group-condition-mode="${groupIndex}">
                    <option value="always" ${mode === "always" ? "selected" : ""}>${__("Always")}</option>
                    <option value="based" ${mode === "based" ? "selected" : ""}>${__("Based on one answer")}</option>
                </select>
            </label>
            ${mode === "based" ? `
                <label class="ods-field">
                    <span>${__("Question")}</span>
                    <select data-group-condition-question="${groupIndex}">${renderQuestionOptions(set, selectedField)}</select>
                </label>
                <label class="ods-field">
                    <span>${__("Condition")}</span>
                    <select data-group-condition-operator="${groupIndex}">${renderOperatorOptions(set, selectedField, operator)}</select>
                </label>
                <label class="ods-field">
                    <span>${__("Compare with")}</span>
                    <select data-group-compare-source="${groupIndex}">
                        <option value="manual" ${compareSource === "manual" ? "selected" : ""}>${__("Typed value")}</option>
                        <option value="question" ${compareSource === "question" ? "selected" : ""}>${__("Another question")}</option>
                    </select>
                </label>
                ${compareSource === "question" ? `
                    <label class="ods-field">
                        <span>${__("Other question")}</span>
                        <select data-group-compare-question="${groupIndex}">${renderQuestionOptions(set, compareQuestion)}</select>
                    </label>
                ` : `
                    <label class="ods-field">
                        <span>${__("Value")}</span>
                        <input data-group-manual-value="${groupIndex}" value="${frappe.utils.escape_html(manualValue)}" placeholder="VALUE">
                    </label>
                `}
                <div class="ods-condition-summary">
                    <span>${__("Rule preview")}</span>
                    <strong>${frappe.utils.escape_html(compileStructuredCondition({ ...state, condition_mode: "based", question_key: selectedField, operator, compare_source: compareSource, manual_value: manualValue, compare_question_key: compareQuestion }, set) || __("Always"))}</strong>
                </div>
            ` : ""}
        </div>
    `;
}

function renderQuestionOptions(set, selectedField) {
    return getQuestionKeys(set).map((key) => `<option value="${frappe.utils.escape_html(key)}" ${key === selectedField ? "selected" : ""}>${frappe.utils.escape_html(getContextFieldLabel(set, key))}</option>`).join("");
}

function renderOperatorOptions(set, selectedField, selectedOperator) {
    return getConditionOperators(getContextField(set, selectedField)).map((operator) => `<option value="${operator}" ${operator === selectedOperator ? "selected" : ""}>${frappe.utils.escape_html(operatorLabel(operator))}</option>`).join("");
}

function getArticleRuleGroups(set) {
    const groups = [];
    const groupIndexes = new Map();
    (set.item_rules || []).forEach((rule, index) => {
        ensureStructuredRule(rule, set);
        const condition = (rule.condition_formula || "").trim();
        const key = (rule.rule_group || "").trim() || condition || "__always__";
        if (!groupIndexes.has(key)) {
            groupIndexes.set(key, groups.length);
            groups.push({ key, condition, condition_state: extractConditionState(rule), rules: [] });
        }
        groups[groupIndexes.get(key)].rules.push({ rule, index });
    });
    return groups;
}

function extractConditionState(rule) {
    return {
        mode: ["always", "based"].includes(rule.condition_mode) ? rule.condition_mode : "based",
        question_key: rule.question_key || "",
        operator: rule.operator || "==",
        compare_source: rule.compare_source || "manual",
        manual_value: rule.manual_value || "",
        compare_question_key: rule.compare_question_key || "",
        condition_formula: rule.condition_formula || "",
    };
}

function ensureStructuredRule(rule, set) {
    if (!["fixed", "filtered"].includes(rule.item_selection_mode)) rule.item_selection_mode = "fixed";
    normalizeRuleItemFilters(rule);
    if (rule.uses_advanced_formula) {
        rule.condition_mode = rule.condition_mode || "always";
        rule.quantity_mode = rule.quantity_mode || "fixed";
        rule.fixed_qty = rule.fixed_qty || "1";
        return;
    }
    if (!rule.condition_mode) {
        Object.assign(rule, conditionFields(parseStructuredCondition(rule.condition_formula)));
    }
    if (!rule.quantity_mode) {
        Object.assign(rule, quantityFields(parseQuantityFormula(rule.qty_formula)));
    }
    if (!["always", "based"].includes(rule.condition_mode)) rule.condition_mode = "based";
    if (rule.condition_mode === "based") {
        rule.question_key = rule.question_key || getQuestionKeys(set)[0] || "";
        rule.operator = getCompatibleOperator(set, rule.question_key, rule.operator || "==");
        rule.compare_source = rule.compare_source || "manual";
        if (rule.compare_source === "manual" && !rule.manual_value) {
            rule.manual_value = defaultComparisonValue(getContextField(set, rule.question_key));
        }
    }
    if (!["fixed", "question"].includes(rule.quantity_mode)) rule.quantity_mode = "fixed";
    rule.condition_formula = compileStructuredCondition(rule, set);
    rule.qty_formula = compileQuantityFormula(rule);
}

function conditionFields(condition) {
    return {
        condition_mode: condition.mode,
        question_key: condition.question_key,
        operator: condition.operator,
        compare_source: condition.compare_source,
        manual_value: condition.manual_value,
        compare_question_key: condition.compare_question_key,
    };
}

function quantityFields(quantity) {
    const fields = {
        quantity_mode: quantity.mode,
        fixed_qty: quantity.fixed_qty,
        quantity_question_key: quantity.quantity_question_key,
    };
    return fields;
}

function describeConditionGroup(group, set) {
    const state = group.condition_state;
    if (!state || state.mode === "always") return __("Always add these articles");
    const left = getContextFieldLabel(set, state.question_key);
    const operator = operatorLabel(state.operator || "==");
    const right = state.compare_source === "question" ? getContextFieldLabel(set, state.compare_question_key) : state.manual_value;
    return `${left} ${operator} ${right || __("value")}`;
}

function getConditionOperators(field) {
    const type = field?.field_type || "Data";
    if (["Int", "Float"].includes(type)) return ODS_CONDITION_OPERATORS;
    return ["==", "!="];
}

function getCompatibleOperator(set, questionKey, operator) {
    const operators = getConditionOperators(getContextField(set, questionKey));
    return operators.includes(operator) ? operator : operators[0];
}

function operatorLabel(operator) {
    return {
        "==": __("is"),
        "!=": __("is not"),
        ">": __("is greater than"),
        ">=": __("is at least"),
        "<": __("is less than"),
        "<=": __("is at most"),
    }[operator] || operator;
}

function getContextField(set, key) {
    return [...(set.fields || []), ...(set.derived_fields || [])].find((row) => row.field_key === key) || null;
}

function getContextFieldLabel(set, key) {
    const field = getContextField(set, key);
    return field ? `${field.label || field.field_key} (${field.field_key})` : key || "";
}

function getQuestionKeys(set) {
    return getContextKeys(set);
}

function defaultComparisonValue(field) {
    if (!field) return "VALUE";
    if (field.field_type === "Check") return "1";
    if (["Int", "Float"].includes(field.field_type)) return "1";
    if (field.field_type === "Select") return splitOptions(field.options)[0] || "VALUE";
    return "VALUE";
}

function parseStructuredCondition(condition) {
    const expr = (condition || "").trim();
    if (!expr) return { mode: "always", question_key: "", operator: "==", compare_source: "manual", manual_value: "", compare_question_key: "" };
    const bare = expr.match(/^([A-Za-z_][A-Za-z0-9_]*)$/);
    if (bare) return { mode: "based", question_key: bare[1], operator: "==", compare_source: "manual", manual_value: "1", compare_question_key: "" };
    const match = expr.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*(==|!=|>=|<=|>|<)\s*(?:"([^"]*)"|'([^']*)'|([A-Za-z_][A-Za-z0-9_]*)|(-?\d+(?:\.\d+)?)|(true|false))$/i);
    if (!match) return { mode: "based", question_key: "", operator: "==", compare_source: "manual", manual_value: "VALUE", compare_question_key: "" };
    const rightToken = match[5] || "";
    if (rightToken && !["true", "false"].includes(rightToken.toLowerCase())) {
        return { mode: "based", question_key: match[1], operator: match[2], compare_source: "question", manual_value: "", compare_question_key: rightToken };
    }
    return {
        mode: "based",
        question_key: match[1],
        operator: match[2],
        compare_source: "manual",
        manual_value: match[3] ?? match[4] ?? (["true", "false"].includes(rightToken.toLowerCase()) ? rightToken : undefined) ?? match[6] ?? match[7] ?? "",
        compare_question_key: "",
    };
}

function compileStructuredCondition(rule, set) {
    if ((rule.condition_mode || "always") === "always") return "";
    const questionKey = rule.question_key || getQuestionKeys(set)[0] || "";
    if (!questionKey) return "";
    const operator = getCompatibleOperator(set, questionKey, rule.operator || "==");
    if ((rule.compare_source || "manual") === "question") {
        return `${questionKey} ${operator} ${rule.compare_question_key || questionKey}`;
    }
    return `${questionKey} ${operator} ${formulaLiteral(rule.manual_value || defaultComparisonValue(getContextField(set, questionKey)), getContextField(set, questionKey))}`;
}

function formulaLiteral(value, field) {
    const raw = String(value ?? "").trim();
    if ((field?.field_type === "Check") || ["true", "false"].includes(raw.toLowerCase())) {
        return raw === "1" ? "true" : raw === "0" ? "false" : raw.toLowerCase();
    }
    if (["Int", "Float"].includes(field?.field_type) && /^-?\d+(\.\d+)?$/.test(raw)) return raw;
    return JSON.stringify(raw);
}

function parseQuantityFormula(qtyFormula) {
    const formula = String(qtyFormula || "").trim();
    if (/^-?\d+(\.\d+)?$/.test(formula)) return { mode: "fixed", fixed_qty: formula, quantity_question_key: "" };
    if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(formula)) return { mode: "question", fixed_qty: "1", quantity_question_key: formula };
    return { mode: "fixed", fixed_qty: "1", quantity_question_key: "" };
}

function compileQuantityFormula(rule) {
    if ((rule.quantity_mode || "fixed") === "question") return rule.quantity_question_key || "1";
    return String(rule.fixed_qty || "1");
}

function updateRuleGroupCondition(groupIndex, changes) {
    const set = getActiveSet();
    const group = getArticleRuleGroups(set)[groupIndex];
    if (!group) return;
    group.rules.forEach(({ index }) => {
        const rule = set.item_rules[index];
        if (!rule) return;
        Object.assign(rule, changes);
        if (rule.condition_mode === "based") {
            rule.question_key = rule.question_key || getQuestionKeys(set)[0] || "";
            rule.operator = getCompatibleOperator(set, rule.question_key, rule.operator || "==");
            rule.compare_source = rule.compare_source || "manual";
            if (rule.compare_source === "manual" && !rule.manual_value) {
                rule.manual_value = defaultComparisonValue(getContextField(set, rule.question_key));
            }
            if (rule.compare_source === "question" && !rule.compare_question_key) {
                rule.compare_question_key = getQuestionKeys(set).find((key) => key !== rule.question_key) || rule.question_key;
            }
        }
        rule.condition_formula = compileStructuredCondition(rule, set);
    });
}

function updateRuleQuantity(ruleIndex, changes) {
    const set = getActiveSet();
    const rule = set.item_rules[ruleIndex];
    if (!rule) return;
    Object.assign(rule, changes);
    if (rule.quantity_mode === "question" && !rule.quantity_question_key) {
        rule.quantity_question_key = getQuestionKeys(set)[0] || "";
    }
    if (rule.quantity_mode === "fixed" && !rule.fixed_qty) rule.fixed_qty = "1";
    rule.qty_formula = compileQuantityFormula(rule);
}

function renderArticleRuleRow(rule, index, articleIndex, set) {
    ensureStructuredRule(rule, set);
    const itemInfo = getCachedItemInfo(rule.item);
    const selectionMode = rule.item_selection_mode || "fixed";
    const settingsOpen = !!ODS_STATE.openArticleSettings[index];
    const itemName = selectionMode === "filtered" ? describeItemFilters(rule) : itemInfo.item_name || rule.rule_label || __("Choose an item");
    const quantityMode = rule.quantity_mode || "fixed";
    return `
        <article class="ods-article-row ${rule.is_active ? "" : "muted"}" role="listitem">
            <div class="ods-article-row-main">
                <div class="ods-article-row-title">
                    <span class="ods-article-row-index">${articleIndex + 1}</span>
                    <label class="ods-compact-field">
                        <span>${__("Item Source")}</span>
                        <select data-rule-item-selection-mode="${index}">
                            <option value="fixed" ${selectionMode === "fixed" ? "selected" : ""}>${__("Fixed")}</option>
                            <option value="filtered" ${selectionMode === "filtered" ? "selected" : ""}>${__("Filtered")}</option>
                        </select>
                    </label>
                    ${renderRuleItemSelector(rule, index, selectionMode)}
                    <div class="ods-article-name">
                        <strong>${frappe.utils.escape_html(itemName)}</strong>
                        <small>${frappe.utils.escape_html(selectionMode === "filtered" ? __("Resolved when tested/saved") : rule.display_group || itemInfo.item_group || __("No section"))}</small>
                    </div>
                </div>
            </div>
            ${renderQuantityInlineControl(rule, index, quantityMode, set)}
            <div class="ods-article-row-flags">
                ${compactCheck("rule", index, "is_active", __("Active"), rule.is_active)}
                ${compactCheck("rule", index, "show_in_detail", __("Detail"), rule.show_in_detail)}
            </div>
            <button class="ods-icon-button danger ods-article-remove" type="button" data-remove-rule="${index}" aria-label="${__("Remove article")}">x</button>
            <details class="ods-article-row-more" data-article-settings="${index}" ${settingsOpen ? "open" : ""}>
                <summary>${__("More article settings")}</summary>
                <div class="ods-form-grid three">
                    ${inlineInput("rule", index, "rule_label", __("Internal label"), rule.rule_label)}
                    ${inlineInput("rule", index, "display_group", __("Quote section"), rule.display_group)}
                    ${inlineInput("rule", index, "sequence", __("Sort order"), rule.sequence || 10, "number")}
                    ${selectionMode === "filtered" ? renderItemFilterEditor(rule, index, set) : ""}
                    ${rule.uses_advanced_formula ? `
                        <label class="ods-field wide">
                            <span>${__("Condition formula")}</span>
                            <textarea class="ods-code-input" data-update-kind="rule" data-update-index="${index}" data-update-field="condition_formula" rows="2">${frappe.utils.escape_html(rule.condition_formula || "")}</textarea>
                        </label>
                        <label class="ods-field wide">
                            <span>${__("Quantity formula")}</span>
                            <textarea class="ods-code-input" data-update-kind="rule" data-update-index="${index}" data-update-field="qty_formula" rows="3">${frappe.utils.escape_html(rule.qty_formula || "")}</textarea>
                        </label>
                    ` : ""}
                </div>
            </details>
        </article>
    `;
}

function renderRuleItemSelector(rule, index, selectionMode) {
    if (selectionMode === "filtered") {
        return `
            <div class="ods-filter-summary">
                <span>${__("Filters")}</span>
                <strong>${frappe.utils.escape_html(describeItemFilters(rule))}</strong>
            </div>
        `;
    }
    return `
        <label class="ods-compact-field ods-item-code-field">
            <span>${__("Item")}</span>
            <div class="ods-item-search-row">
                <div class="ods-item-link-host" data-rule-item-link="${index}"></div>
                <button class="btn btn-xs btn-default" type="button" data-rule-item-advanced-search="${index}">${__("Advanced Search")}</button>
            </div>
        </label>
    `;
}

function renderItemFilterEditor(rule, index, set) {
    const filters = normalizeRuleItemFilters(rule);
    const rows = filters.map((filter, filterIndex) => renderItemFilterRow(filter, index, filterIndex, set)).join("");
    return `
        <div class="ods-item-filter-editor wide">
            <div class="ods-filter-editor-head">
                <div>
                    <strong>${__("Filtered Item Match")}</strong>
                    <span>${__("Example: Item Group = Porte, Brand = ATERYA, Taille = 70, Material = INOX.")}</span>
                </div>
                <button class="btn btn-xs btn-default" type="button" data-add-item-filter="${index}">${__("Add Filter")}</button>
            </div>
            <div class="ods-item-filter-list">${rows || `<div class="ods-empty ods-empty-articles"><strong>${__("No filters")}</strong><p>${__("Add filters that resolve to exactly one Item.")}</p></div>`}</div>
        </div>
    `;
}

function renderItemFilterRow(filter, ruleIndex, filterIndex, set) {
    const source = filter.source || "item_field";
    const valueSource = filter.value_source || "manual";
    return `
        <div class="ods-item-filter-row">
            <label class="ods-compact-field">
                <span>${__("Source")}</span>
                <select data-rule-filter-source="${ruleIndex}" data-filter-index="${filterIndex}">
                    <option value="item_field" ${source === "item_field" ? "selected" : ""}>${__("Item Field")}</option>
                    <option value="specification" ${source === "specification" ? "selected" : ""}>${__("Specification")}</option>
                </select>
            </label>
            ${source === "specification" ? `
                <label class="ods-compact-field">
                    <span>${__("Attribute")}</span>
                    <input data-rule-filter-attribute="${ruleIndex}" data-filter-index="${filterIndex}" value="${frappe.utils.escape_html(filter.attribute || filter.field || "")}" placeholder="Taille">
                </label>
            ` : `
                <label class="ods-compact-field">
                    <span>${__("Field")}</span>
                    <select data-rule-filter-field="${ruleIndex}" data-filter-index="${filterIndex}">${renderItemFilterFieldOptions(filter.field)}</select>
                </label>
            `}
            <label class="ods-compact-field">
                <span>${__("Operator")}</span>
                <select data-rule-filter-operator="${ruleIndex}" data-filter-index="${filterIndex}">${ODS_ITEM_FILTER_OPERATORS.map((op) => `<option value="${op}" ${op === (filter.operator || "==") ? "selected" : ""}>${frappe.utils.escape_html(op)}</option>`).join("")}</select>
            </label>
            <label class="ods-compact-field">
                <span>${__("Value From")}</span>
                <select data-rule-filter-value-source="${ruleIndex}" data-filter-index="${filterIndex}">
                    <option value="manual" ${valueSource === "manual" ? "selected" : ""}>${__("Typed")}</option>
                    <option value="question" ${valueSource === "question" ? "selected" : ""}>${__("Answer")}</option>
                    <option value="formula" ${valueSource === "formula" ? "selected" : ""}>${__("Formula")}</option>
                </select>
            </label>
            ${renderItemFilterValueControl(filter, ruleIndex, filterIndex, set)}
            <button class="ods-icon-button danger" type="button" data-remove-item-filter="${ruleIndex}" data-filter-index="${filterIndex}" aria-label="${__("Remove filter")}">x</button>
        </div>
    `;
}

function renderItemFilterFieldOptions(selected) {
    const current = selected || "item_group";
    return ODS_ITEM_FILTER_FIELDS.map((field) => `<option value="${frappe.utils.escape_html(field.value)}" ${field.value === current ? "selected" : ""}>${frappe.utils.escape_html(__(field.label))}</option>`).join("");
}

function renderItemFilterValueControl(filter, ruleIndex, filterIndex, set) {
    const valueSource = filter.value_source || "manual";
    if (valueSource === "question") {
        return `
            <label class="ods-compact-field">
                <span>${__("Answer")}</span>
                <select data-rule-filter-question="${ruleIndex}" data-filter-index="${filterIndex}">${renderQuestionOptions(set, filter.question_key || getQuestionKeys(set)[0] || "")}</select>
            </label>
        `;
    }
    if (valueSource === "formula") {
        return `
            <label class="ods-compact-field">
                <span>${__("Formula")}</span>
                <input data-rule-filter-formula="${ruleIndex}" data-filter-index="${filterIndex}" value="${frappe.utils.escape_html(filter.formula || "")}" placeholder='upper(door_material)'>
            </label>
        `;
    }
    return `
        <label class="ods-compact-field">
            <span>${__("Value")}</span>
            <input data-rule-filter-value="${ruleIndex}" data-filter-index="${filterIndex}" value="${frappe.utils.escape_html(filter.value || "")}" placeholder="INOX">
        </label>
    `;
}

function renderQuantityInlineControl(rule, index, quantityMode, set) {
    if (rule.uses_advanced_formula) {
        return `
            <div class="ods-article-row-qty ods-formula-summary">
                <span>${__("Qty formula")}</span>
                <code>${frappe.utils.escape_html((rule.qty_formula || "0").trim())}</code>
            </div>
        `;
    }
    const questionKey = rule.quantity_question_key || getQuestionKeys(set)[0] || "";
    return `
        <div class="ods-article-row-qty">
            <label class="ods-compact-field">
                <span>${__("Qty")}</span>
                <select data-rule-quantity-mode="${index}">
                    <option value="fixed" ${quantityMode === "fixed" ? "selected" : ""}>${__("Fixed")}</option>
                    <option value="question" ${quantityMode === "question" ? "selected" : ""}>${__("From answer")}</option>
                </select>
            </label>
            ${quantityMode === "question" ? `
                <label class="ods-compact-field">
                    <span>${__("Answer")}</span>
                    <select data-rule-quantity-question="${index}">${renderQuestionOptions(set, questionKey)}</select>
                </label>
            ` : `
                <label class="ods-compact-field">
                    <span>${__("Number")}</span>
                    <input type="number" step="0.01" data-rule-fixed-qty="${index}" value="${frappe.utils.escape_html(String(rule.fixed_qty || "1"))}">
                </label>
            `}
        </div>
    `;
}

function compactCheck(kind, index, field, label, value) {
    return `<label class="ods-compact-check"><input type="checkbox" data-update-kind="${kind}" data-update-index="${index}" data-update-field="${field}" ${value ? "checked" : ""}> <span>${label}</span></label>`;
}

function renderEmptyArticleRows() {
    return `<div class="ods-empty ods-empty-articles"><strong>${__("No articles yet")}</strong><p>${__("Add the first article that should be generated when this condition is true.")}</p></div>`;
}

function describeRuleQuantity(rule, set) {
    if (rule.uses_advanced_formula) return (rule.qty_formula || "").trim() || __("formula");
    if ((rule.quantity_mode || "fixed") === "question") {
        return rule.quantity_question_key || getQuestionKeys(set)[0] || "1";
    }
    return String(rule.fixed_qty || "1");
}

function defaultItemFilter(set) {
    return {
        source: "item_field",
        field: "item_group",
        attribute: "",
        operator: "==",
        value_source: "manual",
        value: "",
        question_key: getQuestionKeys(set)[0] || "",
        formula: "",
        enabled: 1,
    };
}

function normalizeRuleItemFilters(rule) {
    if (!Array.isArray(rule.item_filters)) {
        rule.item_filters = parseRuleItemFilters(rule.item_filters_json);
    }
    rule.item_filters = rule.item_filters.map((filter) => ({
        source: filter.source || "item_field",
        field: filter.field || "item_group",
        attribute: filter.attribute || "",
        operator: ODS_ITEM_FILTER_OPERATORS.includes(filter.operator) ? filter.operator : "==",
        value_source: ["manual", "question", "formula"].includes(filter.value_source) ? filter.value_source : "manual",
        value: filter.value ?? "",
        question_key: filter.question_key || "",
        formula: filter.formula || "",
        enabled: filter.enabled ?? 1,
    }));
    syncRuleItemFiltersJson(rule);
    return rule.item_filters;
}

function parseRuleItemFilters(raw) {
    try {
        const parsed = typeof raw === "string" ? JSON.parse(raw || "[]") : raw || [];
        return Array.isArray(parsed) ? parsed : parsed.filters || [];
    } catch (error) {
        return [];
    }
}

function syncRuleItemFiltersJson(rule) {
    rule.item_filters_json = JSON.stringify(rule.item_filters || []);
}

function updateRuleItemFilter(ruleIndex, filterIndex, changes) {
    const set = getActiveSet();
    const rule = set.item_rules[ruleIndex];
    if (!rule) return;
    const filters = normalizeRuleItemFilters(rule);
    const filter = filters[filterIndex];
    if (!filter) return;
    Object.assign(filter, changes);
    if (filter.source === "item_field") filter.attribute = "";
    if (filter.source === "specification" && !filter.attribute) filter.attribute = filter.field || "Taille";
    if (filter.value_source === "question" && !filter.question_key) filter.question_key = getQuestionKeys(set)[0] || "";
    syncRuleItemFiltersJson(rule);
}

function keepArticleSettingsOpen(ruleIndex) {
    ODS_STATE.openArticleSettings[ruleIndex] = true;
}

function describeItemFilters(rule) {
    const filters = normalizeRuleItemFilters(rule);
    if (!filters.length) return __("Filtered item");
    return filters.slice(0, 3).map((filter) => {
        const left = filter.source === "specification" ? filter.attribute || filter.field || __("Spec") : itemFilterFieldLabel(filter.field);
        const right = filter.value_source === "question" ? filter.question_key : filter.value_source === "formula" ? filter.formula : filter.value;
        return `${left} ${filter.operator || "=="} ${right || "..."}`;
    }).join(", ") + (filters.length > 3 ? ` +${filters.length - 3}` : "");
}

function itemFilterFieldLabel(fieldname) {
    return (ODS_ITEM_FILTER_FIELDS.find((field) => field.value === fieldname) || {}).label || fieldname || __("Item Field");
}

function renderRuleSentence(rule) {
    const condition = (rule.condition_formula || "").trim() || __("always");
    const qty = (rule.qty_formula || "").trim() || "0";
    return `
        <div class="ods-rule-sentence">
            <span>${__("When")}</span>
            <code>${frappe.utils.escape_html(condition)}</code>
            <span>${__("add")}</span>
            <strong>${frappe.utils.escape_html(rule.item || __("an item"))}</strong>
            <span>${__("with quantity")}</span>
            <code>${frappe.utils.escape_html(qty)}</code>
        </div>
    `;
}

function renderEmptyRuleState() {
    return `<div class="ods-empty"><strong>${__("No rule selected")}</strong><p>${__("Add an article rule to start configuring generated items.")}</p></div>`;
}

function renderAdvancedCalculations(set) {
    return `
        <details class="ods-card ods-advanced-card">
            <summary>
                <strong>${__("Advanced: hidden calculations")}</strong>
                <span>${__("Use only when article rules need reusable computed values.")}</span>
            </summary>
            <div class="ods-advanced-card-body">
                ${renderDerivedSection(set, true)}
            </div>
        </details>
    `;
}

function renderTokenButtons(set) {
    return getContextKeys(set).map((key) => `<span class="ods-token">${frappe.utils.escape_html(key)}</span>`).join("");
}

function renderPreviewSection(set, preview, validation) {
    const testInputs = set.fields.map((field) => renderTestInput(field, ODS_STATE.testValues[field.field_key])).join("");
    return `
        <section class="ods-card">
            <div class="ods-section-head">
                <div>
                    <h2>${__("Try it like a sales user")}</h2>
                    <p>${__("Change answers on the left and confirm the generated article list looks right.")}</p>
                </div>
                <button class="btn btn-primary btn-sm" type="button" data-refresh-preview>${__("Run Test")}</button>
            </div>
            ${renderTestSummary(preview, validation)}
            <div class="ods-preview-layout">
                <div class="ods-test-panel">
                    <h3>${__("Sales-user answers")}</h3>
                    <div class="ods-form-grid one">${testInputs}</div>
                </div>
                <div class="ods-result-panel">
                    ${renderValidation(validation)}
                    ${renderGeneratedItems(preview)}
                    ${renderDerivedPreview(preview)}
                </div>
            </div>
        </section>
    `;
}

function renderTestSummary(preview, validation) {
    const errorCount = validation.filter((row) => row.level === "error").length;
    const warningCount = validation.filter((row) => row.level === "warning").length;
    const generatedCount = (preview.generated || []).length;
    const status = errorCount ? __("Needs fixes") : warningCount ? __("Review warnings") : __("Looks ready");
    const tone = errorCount ? "danger" : warningCount ? "warn" : "ok";
    return `
        <div class="ods-test-summary">
            <div class="ods-test-tile ${tone}"><span>${__("Status")}</span><strong>${status}</strong></div>
            <div class="ods-test-tile"><span>${__("Articles generated")}</span><strong>${generatedCount}</strong></div>
            <div class="ods-test-tile"><span>${__("Rules not used")}</span><strong>${preview.skipped_count || 0}</strong></div>
        </div>
    `;
}

function renderTestInput(field, value) {
    const key = frappe.utils.escape_html(field.field_key);
    if (field.field_type === "Select") {
        const options = splitOptions(field.options).map((option) => `<option value="${frappe.utils.escape_html(option)}" ${String(value) === option ? "selected" : ""}>${frappe.utils.escape_html(option)}</option>`).join("");
        return `<label class="ods-field"><span>${frappe.utils.escape_html(field.label)}</span><select data-test-key="${key}">${options}</select></label>`;
    }
    if (field.field_type === "Check") {
        return `<label class="ods-check-field"><input type="checkbox" data-test-key="${key}" ${value ? "checked" : ""}> <span>${frappe.utils.escape_html(field.label)}</span></label>`;
    }
    const type = ["Int", "Float"].includes(field.field_type) ? "number" : "text";
    return `<label class="ods-field"><span>${frappe.utils.escape_html(field.label)}</span><input type="${type}" data-test-key="${key}" value="${frappe.utils.escape_html(String(value ?? ""))}"></label>`;
}

function renderDerivedPreview(preview) {
    const entries = Object.entries(preview.derived || {});
    if (!entries.length) return "";
    return `
        <div class="ods-mini-card">
            <h3>${__("Hidden calculation results")}</h3>
            <div class="ods-derived-grid">
                ${entries.map(([key, value]) => `<div><span>${frappe.utils.escape_html(key)}</span><strong>${frappe.utils.escape_html(String(value))}</strong></div>`).join("")}
            </div>
        </div>
    `;
}

function renderGeneratedItems(preview) {
    const generated = preview.generated || [];
    if (!generated.length) {
        return `<div class="ods-empty"><strong>${__("No generated items")}</strong><p>${__("Adjust test values or rules to generate article lines.")}</p></div>`;
    }
    const groups = groupBy(generated, (row) => row.display_group || "Ungrouped");
    return `
        <div class="ods-mini-card">
            <h3>${__("Generated quote lines")}</h3>
            ${Object.keys(groups).map((group) => `
                <div class="ods-generated-group">
                    <strong>${frappe.utils.escape_html(group)}</strong>
                    <div class="ods-generated-list">
                        ${groups[group].map(renderGeneratedRow).join("")}
                    </div>
                </div>
            `).join("")}
        </div>
    `;
}

function renderGeneratedRow(row) {
    const warnings = [];
    if (row.missing_item) warnings.push(`<span class="ods-badge danger">${__("Missing item")}</span>`);
    if (row.filtered_item) warnings.push(`<span class="ods-badge warn">${__("Server match")}</span>`);
    if (row.missing_price) warnings.push(`<span class="ods-badge warn">${__("Missing price")}</span>`);
    if (!row.show_in_detail) warnings.push(`<span class="ods-badge muted">${__("Summary only")}</span>`);
    return `
        <div class="ods-generated-row">
            <div>
                <strong>${frappe.utils.escape_html(row.item)}</strong>
                <span>${frappe.utils.escape_html(row.item_name || row.rule_label || "")}</span>
            </div>
            <div class="ods-generated-meta">
                <strong>${frappe.utils.escape_html(String(row.qty))}</strong>
                <span>${frappe.utils.escape_html(row.unit || "")}</span>
            </div>
            <div class="ods-row-badges">${warnings.join("")}</div>
        </div>
    `;
}

function renderPayloadSection(set) {
    return `
        <section class="ods-card">
            <div class="ods-section-head">
                <div>
                    <h2>${__("Advanced JSON")}</h2>
                    <p>${__("Developer view only. This mirrors the payload shape the real page can later save to Dimensioning Set.")}</p>
                </div>
                <button class="btn btn-default btn-sm" type="button" data-copy-payload>${__("Copy JSON")}</button>
            </div>
            <pre class="ods-payload" data-payload-json>${frappe.utils.escape_html(JSON.stringify(set, null, 2))}</pre>
        </section>
    `;
}

function renderLivePanel(set, preview, validation) {
    const errorCount = validation.filter((row) => row.level === "error").length;
    const warningCount = validation.filter((row) => row.level === "warning").length;
    return `
        <aside class="ods-live-panel">
            <div class="ods-mini-card">
                <h3>${__("Builder Draft")}</h3>
                <select data-select-set>
                    ${ODS_STATE.sets.map((row, index) => `<option value="${index}" ${index === ODS_STATE.selectedSet ? "selected" : ""}>${frappe.utils.escape_html(row.name)}</option>`).join("")}
                </select>
                <p>${__("Direct URL only. This page does not update live records yet.")}</p>
            </div>
            <div class="ods-mini-card ods-next-card">
                <h3>${__("Recommended next step")}</h3>
                <p>${errorCount ? __("Fix blocking issues in Test.") : warningCount ? __("Review warnings, then test again.") : __("Try a few sales-user answers.")}</p>
                <button class="btn btn-primary btn-sm" type="button" data-nav="preview">${__("Go to Test")}</button>
            </div>
            ${renderValidation(validation)}
            <div class="ods-mini-card">
                <h3>${__("Current test")}</h3>
                <div class="ods-coverage">
                    <span>${__("Added")}</span><strong>${preview.matched_count || 0}</strong>
                    <span>${__("Not added")}</span><strong>${preview.skipped_count || 0}</strong>
                    <span>${__("Errors")}</span><strong>${preview.errors.length || 0}</strong>
                </div>
            </div>
        </aside>
    `;
}

function renderValidation(validation) {
    if (!validation.length) {
        return `<div class="ods-mini-card"><h3>${__("Readiness")}</h3><p class="ods-ok-text">${__("No blocking issues in this builder test.")}</p></div>`;
    }
    return `
        <div class="ods-mini-card">
            <h3>${__("Readiness")}</h3>
            <div class="ods-validation-list">
                ${validation.map((row) => `<div class="ods-validation ${row.level}"><strong>${frappe.utils.escape_html(row.title)}</strong><span>${frappe.utils.escape_html(row.message)}</span></div>`).join("")}
            </div>
        </div>
    `;
}

function renderBottomBar(set, validation) {
    const errorCount = validation.filter((row) => row.level === "error").length;
    const deleteButton = set.docname ? `<button class="btn btn-default ods-danger-action" type="button" data-delete-builder>${__("Delete Set")}</button>` : "";
    return `
        <div class="ods-bottom-bar">
            <div>
                <strong>${set.docname ? frappe.utils.escape_html(set.docname) : __("Draft builder: safe to experiment")}</strong>
                <span>${__("Use Test to validate generated articles before saving this Dimensioning Set.")}</span>
            </div>
            <div class="ods-bottom-actions">
                ${deleteButton}
                <button class="btn btn-default" type="button" data-reset-builder>${__("Reset")}</button>
                <button class="btn btn-primary" type="button" data-bottom-validate>${errorCount ? __("Review Issues") : __("Run Test")}</button>
            </div>
        </div>
    `;
}

function textInput(id, label, value) {
    return `<label class="ods-field"><span>${label}</span><input id="${id}" data-set-field="name" value="${frappe.utils.escape_html(value || "")}"></label>`;
}

function selectInput(id, label, value, options) {
    return `<label class="ods-field"><span>${label}</span><select id="${id}" data-set-field="is_active">${options.map((option) => `<option value="${option}" ${option === value ? "selected" : ""}>${option}</option>`).join("")}</select></label>`;
}

function inlineInput(kind, index, field, label, value, type = "text") {
    return `<label class="ods-field"><span>${label}</span><input type="${type}" data-update-kind="${kind}" data-update-index="${index}" data-update-field="${field}" value="${frappe.utils.escape_html(String(value ?? ""))}"></label>`;
}

function inlineSelect(kind, index, field, label, value, options) {
    return `<label class="ods-field"><span>${label}</span><select data-update-kind="${kind}" data-update-index="${index}" data-update-field="${field}">${options.map((option) => `<option value="${option}" ${option === value ? "selected" : ""}>${option}</option>`).join("")}</select></label>`;
}

function inlineCheck(kind, index, field, label, value) {
    return `<label class="ods-check-field"><input type="checkbox" data-update-kind="${kind}" data-update-index="${index}" data-update-field="${field}" ${value ? "checked" : ""}> <span>${label}</span></label>`;
}

function bindDimensioningBuilderEvents(page) {
    const root = page.main;
    mountDimensioningItemLinks(page);
    root.find("[data-nav]").on("click", function () {
        ODS_STATE.activeSection = this.dataset.nav;
        renderDimensioningBuilder(page);
    });
    root.find("[data-select-set]").on("change", function () {
        ODS_STATE.selectedSet = Number(this.value) || 0;
        ODS_STATE.selectedRule = 0;
        ODS_STATE.testValues = buildDefaultValues(getActiveSet());
        ODS_STATE.lastPreview = null;
        ODS_STATE.validation = [];
        renderDimensioningBuilder(page);
    });
    root.find("[data-set-field]").on("change", function () {
        const set = getActiveSet();
        const field = this.dataset.setField;
        if (field === "is_active") set.is_active = this.value === "Active";
        else set[field] = this.value;
        ODS_STATE.lastPreview = null;
        renderDimensioningBuilder(page);
    });
    root.find("[data-update-kind]").on("change input", function () {
        updateConfigValue(this);
        ODS_STATE.lastPreview = null;
    });
    root.find("[data-test-key]").on("change", function () {
        const key = this.dataset.testKey;
        ODS_STATE.testValues[key] = this.type === "checkbox" ? this.checked : this.value;
        ODS_STATE.lastPreview = buildPreview(getActiveSet(), ODS_STATE.testValues);
        ODS_STATE.validation = validateSet(getActiveSet(), ODS_STATE.lastPreview);
        renderDimensioningBuilder(page);
    });
    root.find("[data-add-field]").on("click", () => {
        const set = getActiveSet();
        set.fields.push(fieldRow(uniqueDimensioningKey(set, "question"), "New question", "Data", "", "", false, "", "General"));
        ODS_STATE.openQuestionCards = { [set.fields.length - 1]: true };
        renderDimensioningBuilder(page);
    });
    root.find("[data-add-derived]").on("click", () => {
        const set = getActiveSet();
        set.derived_fields.push(derivedRow(uniqueDimensioningKey(set, "calculation"), "New calculation", "Data", '""', "", "General"));
        renderDimensioningBuilder(page);
    });
    root.find("[data-add-rule]").on("click", () => {
        const set = getActiveSet();
        const nextGroup = `GROUP-${getArticleRuleGroups(set).length + 1}`;
        const rule = ruleRow("New rule article", "", "Ungrouped", "1", "", true);
        rule.rule_group = nextGroup;
        set.item_rules.push(rule);
        ODS_STATE.selectedRule = set.item_rules.length - 1;
        ODS_STATE.openRuleGroups = { [getArticleRuleGroups(set).length - 1]: true };
        renderDimensioningBuilder(page);
    });
    root.find("[data-add-rule-article]").on("click", function () {
        const set = getActiveSet();
        const group = getArticleRuleGroups(set)[Number(this.dataset.addRuleArticle) || 0];
        if (!group) return;
        const rule = ruleRow("New article", "", "Ungrouped", "1", group.condition, true);
        rule.rule_group = group.key;
        set.item_rules.push(rule);
        ODS_STATE.selectedRule = set.item_rules.length - 1;
        renderDimensioningBuilder(page);
    });
    root.find("[data-add-catalog-article]").on("click", function () {
        const set = getActiveSet();
        const group = getArticleRuleGroups(set)[Number(this.dataset.addCatalogArticle) || 0];
        const itemInfo = ODS_SAMPLE_ITEMS.find((row) => row.item === this.dataset.catalogItem);
        if (!group || !itemInfo) return;
        const rule = ruleRow(itemInfo.item_name, itemInfo.item, itemInfo.item_group, "1", group.condition, true);
        rule.rule_group = group.key;
        set.item_rules.push(rule);
        ODS_STATE.selectedRule = set.item_rules.length - 1;
        renderDimensioningBuilder(page);
    });
    root.find("[data-open-item-picker]").on("click", function () {
        openDimensioningItemPicker(page, Number(this.dataset.openItemPicker) || 0);
    });
    root.find("[data-rule-item-advanced-search]").on("click", function () {
        openDimensioningItemAdvancedSearch(Number(this.dataset.ruleItemAdvancedSearch) || 0);
    });
    root.find("[data-remove-field]").on("click", function (event) {
        event?.preventDefault?.();
        event?.stopPropagation?.();
        getActiveSet().fields.splice(Number(this.dataset.removeField), 1);
        ODS_STATE.openQuestionCards = {};
        ODS_STATE.testValues = buildDefaultValues(getActiveSet());
        renderDimensioningBuilder(page);
    });
    root.find("[data-remove-derived]").on("click", function () {
        getActiveSet().derived_fields.splice(Number(this.dataset.removeDerived), 1);
        renderDimensioningBuilder(page);
    });
    root.find("[data-remove-rule]").on("click", function () {
        const set = getActiveSet();
        set.item_rules.splice(Number(this.dataset.removeRule), 1);
        ODS_STATE.selectedRule = Math.max(0, ODS_STATE.selectedRule - 1);
        renderDimensioningBuilder(page);
    });
    root.find("[data-select-rule]").on("click", function () {
        ODS_STATE.selectedRule = Number(this.dataset.selectRule) || 0;
        renderDimensioningBuilder(page);
    });
    root.find("[data-toggle-question]").on("click", function () {
        toggleQuestionCard(page, Number(this.dataset.toggleQuestion) || 0);
    });
    root.find("[data-toggle-question]").on("keydown", function (event) {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        toggleQuestionCard(page, Number(this.dataset.toggleQuestion) || 0);
    });
    root.find("[data-toggle-rule-group]").on("click", function () {
        toggleRuleGroup(page, Number(this.dataset.toggleRuleGroup) || 0);
    });
    root.find("[data-toggle-rule-group]").on("keydown", function (event) {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        toggleRuleGroup(page, Number(this.dataset.toggleRuleGroup) || 0);
    });
    root.find("[data-article-settings]").on("toggle", function () {
        ODS_STATE.openArticleSettings[Number(this.dataset.articleSettings) || 0] = this.open;
    });
    root.find("[data-group-condition-mode]").on("change", function () {
        const set = getActiveSet();
        const groupIndex = Number(this.dataset.groupConditionMode) || 0;
        const token = getQuestionKeys(set)[0] || "field_key";
        const nextMode = this.value;
        updateRuleGroupCondition(groupIndex, {
            condition_mode: nextMode,
            question_key: token,
            operator: "==",
            compare_source: "manual",
            manual_value: defaultComparisonValue(getContextField(set, token)),
        });
        ODS_STATE.lastPreview = null;
        renderDimensioningBuilder(page);
    });
    root.find("[data-group-condition-question]").on("change", function () {
        const set = getActiveSet();
        const questionKey = String(this.value || "");
        updateRuleGroupCondition(Number(this.dataset.groupConditionQuestion) || 0, {
            condition_mode: "based",
            question_key: questionKey,
            operator: getCompatibleOperator(set, questionKey, "=="),
            manual_value: defaultComparisonValue(getContextField(set, questionKey)),
        });
        ODS_STATE.lastPreview = null;
        renderDimensioningBuilder(page);
    });
    root.find("[data-group-condition-operator]").on("change", function () {
        updateRuleGroupCondition(Number(this.dataset.groupConditionOperator) || 0, { condition_mode: "based", operator: this.value });
        ODS_STATE.lastPreview = null;
        renderDimensioningBuilder(page);
    });
    root.find("[data-group-compare-source]").on("change", function () {
        updateRuleGroupCondition(Number(this.dataset.groupCompareSource) || 0, { condition_mode: "based", compare_source: this.value });
        ODS_STATE.lastPreview = null;
        renderDimensioningBuilder(page);
    });
    root.find("[data-group-manual-value]").on("change", function () {
        updateRuleGroupCondition(Number(this.dataset.groupManualValue) || 0, { condition_mode: "based", compare_source: "manual", manual_value: this.value });
        ODS_STATE.lastPreview = null;
        renderDimensioningBuilder(page);
    });
    root.find("[data-group-compare-question]").on("change", function () {
        updateRuleGroupCondition(Number(this.dataset.groupCompareQuestion) || 0, { condition_mode: "based", compare_source: "question", compare_question_key: this.value });
        ODS_STATE.lastPreview = null;
        renderDimensioningBuilder(page);
    });
    root.find("[data-rule-quantity-mode]").on("change", function () {
        updateRuleQuantity(Number(this.dataset.ruleQuantityMode) || 0, { quantity_mode: this.value });
        ODS_STATE.lastPreview = null;
        renderDimensioningBuilder(page);
    });
    root.find("[data-rule-fixed-qty]").on("change", function () {
        updateRuleQuantity(Number(this.dataset.ruleFixedQty) || 0, { quantity_mode: "fixed", fixed_qty: this.value });
        ODS_STATE.lastPreview = null;
    });
    root.find("[data-rule-quantity-question]").on("change", function () {
        updateRuleQuantity(Number(this.dataset.ruleQuantityQuestion) || 0, { quantity_mode: "question", quantity_question_key: this.value });
        ODS_STATE.lastPreview = null;
        renderDimensioningBuilder(page);
    });
    root.find("[data-rule-item-selection-mode]").on("change", function () {
        const set = getActiveSet();
        const ruleIndex = Number(this.dataset.ruleItemSelectionMode) || 0;
        const rule = set.item_rules[ruleIndex];
        if (!rule) return;
        keepArticleSettingsOpen(ruleIndex);
        rule.item_selection_mode = this.value;
        if (rule.item_selection_mode === "filtered" && !normalizeRuleItemFilters(rule).length) {
            rule.item_filters = [defaultItemFilter(set)];
            syncRuleItemFiltersJson(rule);
        }
        ODS_STATE.lastPreview = null;
        renderDimensioningBuilder(page);
    });
    root.find("[data-add-item-filter]").on("click", function () {
        const set = getActiveSet();
        const ruleIndex = Number(this.dataset.addItemFilter) || 0;
        const rule = set.item_rules[ruleIndex];
        if (!rule) return;
        keepArticleSettingsOpen(ruleIndex);
        normalizeRuleItemFilters(rule).push(defaultItemFilter(set));
        syncRuleItemFiltersJson(rule);
        ODS_STATE.lastPreview = null;
        renderDimensioningBuilder(page);
    });
    root.find("[data-remove-item-filter]").on("click", function () {
        const ruleIndex = Number(this.dataset.removeItemFilter) || 0;
        const rule = getActiveSet().item_rules[ruleIndex];
        if (!rule) return;
        keepArticleSettingsOpen(ruleIndex);
        normalizeRuleItemFilters(rule).splice(Number(this.dataset.filterIndex) || 0, 1);
        syncRuleItemFiltersJson(rule);
        ODS_STATE.lastPreview = null;
        renderDimensioningBuilder(page);
    });
    root.find("[data-rule-filter-source]").on("change", function () {
        const ruleIndex = Number(this.dataset.ruleFilterSource) || 0;
        keepArticleSettingsOpen(ruleIndex);
        updateRuleItemFilter(ruleIndex, Number(this.dataset.filterIndex) || 0, { source: this.value });
        ODS_STATE.lastPreview = null;
        renderDimensioningBuilder(page);
    });
    root.find("[data-rule-filter-field]").on("change", function () {
        const ruleIndex = Number(this.dataset.ruleFilterField) || 0;
        keepArticleSettingsOpen(ruleIndex);
        updateRuleItemFilter(ruleIndex, Number(this.dataset.filterIndex) || 0, { field: this.value });
        ODS_STATE.lastPreview = null;
        renderDimensioningBuilder(page);
    });
    root.find("[data-rule-filter-attribute]").on("change", function () {
        const ruleIndex = Number(this.dataset.ruleFilterAttribute) || 0;
        keepArticleSettingsOpen(ruleIndex);
        updateRuleItemFilter(ruleIndex, Number(this.dataset.filterIndex) || 0, { attribute: this.value });
        ODS_STATE.lastPreview = null;
        renderDimensioningBuilder(page);
    });
    root.find("[data-rule-filter-operator]").on("change", function () {
        const ruleIndex = Number(this.dataset.ruleFilterOperator) || 0;
        keepArticleSettingsOpen(ruleIndex);
        updateRuleItemFilter(ruleIndex, Number(this.dataset.filterIndex) || 0, { operator: this.value });
        ODS_STATE.lastPreview = null;
        renderDimensioningBuilder(page);
    });
    root.find("[data-rule-filter-value-source]").on("change", function () {
        const ruleIndex = Number(this.dataset.ruleFilterValueSource) || 0;
        keepArticleSettingsOpen(ruleIndex);
        updateRuleItemFilter(ruleIndex, Number(this.dataset.filterIndex) || 0, { value_source: this.value });
        ODS_STATE.lastPreview = null;
        renderDimensioningBuilder(page);
    });
    root.find("[data-rule-filter-value]").on("change", function () {
        const ruleIndex = Number(this.dataset.ruleFilterValue) || 0;
        keepArticleSettingsOpen(ruleIndex);
        updateRuleItemFilter(ruleIndex, Number(this.dataset.filterIndex) || 0, { value: this.value });
        ODS_STATE.lastPreview = null;
    });
    root.find("[data-rule-filter-question]").on("change", function () {
        const ruleIndex = Number(this.dataset.ruleFilterQuestion) || 0;
        keepArticleSettingsOpen(ruleIndex);
        updateRuleItemFilter(ruleIndex, Number(this.dataset.filterIndex) || 0, { question_key: this.value });
        ODS_STATE.lastPreview = null;
        renderDimensioningBuilder(page);
    });
    root.find("[data-rule-filter-formula]").on("change", function () {
        const ruleIndex = Number(this.dataset.ruleFilterFormula) || 0;
        keepArticleSettingsOpen(ruleIndex);
        updateRuleItemFilter(ruleIndex, Number(this.dataset.filterIndex) || 0, { formula: this.value });
        ODS_STATE.lastPreview = null;
    });
    root.find("[data-refresh-preview], [data-bottom-validate]").on("click", () => {
        ODS_STATE.activeSection = "preview";
        ODS_STATE.lastPreview = buildPreview(getActiveSet(), ODS_STATE.testValues);
        ODS_STATE.validation = validateSet(getActiveSet(), ODS_STATE.lastPreview);
        renderDimensioningBuilder(page);
    });
    root.find("[data-reset-builder]").on("click", () => {
        resetDimensioningBuilderState();
        renderDimensioningBuilder(page);
    });
    root.find("[data-delete-builder]").on("click", () => confirmDeleteActiveDimensioningSet(page));
    root.find("[data-save-builder]").on("click", () => saveActiveDimensioningSet(page));
    root.find("[data-copy-payload]").on("click", () => {
        const payload = JSON.stringify(getActiveSet(), null, 2);
        navigator.clipboard?.writeText(payload);
        frappe.show_alert({ message: __("Builder payload copied"), indicator: "green" });
    });
}

function mountDimensioningItemLinks(page) {
    ODS_ITEM_LINK_CONTROLS.clear();
    page.main.find("[data-rule-item-link]").each((_, host) => {
        const index = Number(host.dataset.ruleItemLink) || 0;
        const rule = getActiveSet().item_rules[index];
        if (!rule || !frappe.ui?.form?.make_control) return;
        host.innerHTML = "";
        let syncing = true;
        const control = frappe.ui.form.make_control({
            parent: host,
            only_input: true,
            render_input: true,
            df: {
                fieldname: `dimensioning_rule_item_${index}`,
                fieldtype: "Link",
                options: "Item",
                only_select: true,
                get_query: () => ({
                    query: "orderlift.orderlift_sales.doctype.dimensioning_set.dimensioning_set.dimensioning_item_query",
                }),
                change: () => {
                    if (syncing) return;
                    const item = control.get_value() || "";
                    if ((rule.item || "") === item) return;
                    rule.item = item;
                    ODS_STATE.lastPreview = null;
                    fetchDimensioningItemInfo(item).then((info) => {
                        if (!info || rule.item !== item) return;
                        if (!rule.rule_label || rule.rule_label === __("New article")) rule.rule_label = info.item_name || item;
                        if (!rule.display_group) rule.display_group = info.item_group || "";
                        renderDimensioningBuilder(page);
                    });
                },
            },
        });
        if (control.df) control.df.only_select = true;
        control.refresh();
        ODS_ITEM_LINK_CONTROLS.set(index, control);
        control.set_value(rule.item || "");
        setTimeout(() => { syncing = false; }, 0);
        if (control.$input) control.$input.addClass("ods-item-link-input");
        bindDimensioningItemLinkDropdown(host);
        if (rule.item && !ODS_ITEM_CACHE[rule.item]?.__lookup_attempted) {
            fetchDimensioningItemInfo(rule.item).then((info) => {
                if (info && rule.item === info.item) renderDimensioningBuilder(page);
            });
        }
    });
}

function openDimensioningItemAdvancedSearch(index) {
    const control = ODS_ITEM_LINK_CONTROLS.get(index);
    if (control?.open_advanced_search) {
        control.open_advanced_search.call(control);
    }
}

function bindDimensioningItemLinkDropdown(host) {
    const input = host.querySelector("input");
    if (!input) return;
    const place = () => requestAnimationFrame(() => positionDimensioningItemLinkDropdown(host));
    input.addEventListener("focus", place);
    input.addEventListener("input", place);
    input.addEventListener("keydown", place);
    input.addEventListener("awesomplete-open", place);
    const observer = new MutationObserver(place);
    observer.observe(host, { attributes: true, attributeFilter: ["hidden", "class"], childList: true, subtree: true });
}

function positionDimensioningItemLinkDropdown(host) {
    const input = host.querySelector("input");
    const list = host.querySelector(".awesomplete > ul[role='listbox']");
    if (!input || !list || list.hasAttribute("hidden")) return;

    const rect = input.getBoundingClientRect();
    const bottomBar = document.querySelector(".ods-bottom-bar");
    const bottomLimit = bottomBar ? Math.min(window.innerHeight, bottomBar.getBoundingClientRect().top) : window.innerHeight;
    const availableBelow = Math.max(0, bottomLimit - rect.bottom - 8);
    const availableAbove = Math.max(0, rect.top - 8);
    const desiredHeight = Math.min(list.scrollHeight || 320, 320);
    const openAbove = availableBelow < Math.min(desiredHeight, 220) && availableAbove > availableBelow;
    const availableSpace = openAbove ? availableAbove : availableBelow;

    host.classList.toggle("ods-awesomplete-above", openAbove);
    list.style.maxHeight = `${Math.max(120, Math.min(availableSpace - 8, 320))}px`;
}

function openDimensioningItemPicker(page, groupIndex) {
    const dialog = new frappe.ui.Dialog({
        title: __("Add Item to Rule"),
        fields: [
            {
                fieldname: "item",
                fieldtype: "Link",
                label: __("Item"),
                options: "Item",
                reqd: 1,
                only_select: true,
                get_query: () => ({ query: "orderlift.orderlift_sales.doctype.dimensioning_set.dimensioning_set.dimensioning_item_query" }),
            },
        ],
        primary_action_label: __("Add"),
        primary_action: async (values) => {
            const item = values.item;
            const group = getArticleRuleGroups(getActiveSet())[groupIndex];
            if (!item || !group) return;
            const info = await fetchDimensioningItemInfo(item);
            const rule = ruleRow(info?.item_name || item, item, info?.item_group || "", "1", group.condition, true);
            rule.rule_group = group.key;
            getActiveSet().item_rules.push(rule);
            dialog.hide();
            renderDimensioningBuilder(page);
        },
    });
    dialog.show();
}

function confirmDeleteActiveDimensioningSet(page) {
    const set = getActiveSet();
    if (!set?.docname) {
        frappe.msgprint({
            title: __("Nothing to delete"),
            message: __("Save or load a Dimensioning Set before deleting it."),
            indicator: "orange",
        });
        return;
    }
    frappe.confirm(
        __("Delete Dimensioning Set {0}? This cannot be undone.", [set.docname]),
        async () => {
            try {
                await frappe.call({
                    method: "orderlift.orderlift_sales.doctype.dimensioning_set.dimensioning_set.delete_dimensioning_set",
                    args: { set_name: set.docname },
                    freeze: true,
                });
                frappe.show_alert({ message: __("Dimensioning Set deleted"), indicator: "green" });
                frappe.set_route("dimensioning-set-manager");
            } catch (error) {
                frappe.msgprint({
                    title: __("Delete failed"),
                    message: extractDimensioningBuilderError(error) || __("Unable to delete this Dimensioning Set."),
                    indicator: "red",
                });
            }
        }
    );
}

function extractDimensioningBuilderError(error) {
    const raw = error?._server_messages || error?.message || error?.responseJSON?._server_messages || error?.responseJSON?.message || "";
    if (!raw) return "";
    try {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
            return parsed.map((entry) => extractDimensioningBuilderError({ message: entry })).filter(Boolean).join(" ");
        }
        return parsed.message || String(parsed);
    } catch (e) {
        return $("<div>").html(String(raw)).text().trim();
    }
}

async function loadInitialDimensioningSet(page) {
    const urlParams = new URLSearchParams(window.location.search || "");
    const shouldCreate = Boolean(frappe.route_options?.new_dimensioning_set || urlParams.get("new_dimensioning_set"));
    if (shouldCreate) {
        if (frappe.route_options) frappe.route_options.new_dimensioning_set = null;
        ODS_STATE.sets = [newBlankDimensioningSet()];
        ODS_STATE.selectedSet = 0;
        ODS_STATE.activeSection = "start";
        ODS_STATE.testValues = {};
        ODS_STATE.openQuestionCards = {};
        ODS_STATE.openRuleGroups = {};
        ODS_STATE.validation = [];
        ODS_STATE.lastPreview = null;
        renderDimensioningBuilder(page);
        return;
    }
    const setName = frappe.route_options?.dimensioning_set || urlParams.get("dimensioning_set");
    if (!setName) return;
    if (frappe.route_options) frappe.route_options.dimensioning_set = null;
    await loadDimensioningSet(page, setName);
}

function promptLoadDimensioningSet(page) {
    frappe.prompt(
        [{ fieldname: "dimensioning_set", label: __("Dimensioning Set"), fieldtype: "Link", options: "Dimensioning Set", reqd: 1 }],
        (values) => loadDimensioningSet(page, values.dimensioning_set),
        __("Load Dimensioning Set"),
        __("Load")
    );
}

async function loadDimensioningSet(page, setName) {
    if (!setName) return;
    const response = await frappe.call({
        method: "orderlift.orderlift_sales.doctype.dimensioning_set.dimensioning_set.get_dimensioning_builder_payload",
        args: { set_name: setName },
    });
    const payload = (response.message || {}).set;
    if (!payload) return;
    const loadedSet = builderSetFromPayload(payload);
    ODS_STATE.sets = [loadedSet, ...ODS_STATE.sets.filter((row) => row.docname !== loadedSet.docname)];
    ODS_STATE.selectedSet = 0;
    ODS_STATE.openQuestionCards = {};
    ODS_STATE.openRuleGroups = {};
    ODS_STATE.testValues = buildDefaultValues(loadedSet);
    ODS_STATE.validation = [];
    ODS_STATE.lastPreview = null;
    renderDimensioningBuilder(page);
}

async function saveActiveDimensioningSet(page) {
    if (ODS_STATE.isSaving) return;
    const set = getActiveSet();
    ODS_STATE.isSaving = true;
    updateDimensioningSaveState(page);
    try {
        const response = await frappe.call({
            method: "orderlift.orderlift_sales.doctype.dimensioning_set.dimensioning_set.save_dimensioning_builder_payload",
            args: { payload: JSON.stringify(payloadFromBuilderSet(set)) },
        });
        const payload = (response.message || {}).set;
        if (payload) {
            ODS_STATE.sets[ODS_STATE.selectedSet] = builderSetFromPayload(payload);
            ODS_STATE.testValues = buildDefaultValues(getActiveSet());
            ODS_STATE.lastPreview = null;
        }
        frappe.show_alert({ message: __("Dimensioning Set saved"), indicator: "green" });
        renderDimensioningBuilder(page);
    } catch (error) {
        frappe.msgprint({
            title: __("Save failed"),
            message: extractDimensioningBuilderError(error) || __("Unable to save this Dimensioning Set."),
            indicator: "red",
        });
    } finally {
        ODS_STATE.isSaving = false;
        updateDimensioningSaveState(page);
    }
}

function updateDimensioningSaveState(page) {
    const saving = !!ODS_STATE.isSaving;
    page.main.find("[data-save-builder]").prop("disabled", saving).text(saving ? __("Saving...") : __("Save Dimensioning Set"));
    if (page.btn_primary) {
        page.btn_primary.prop("disabled", saving).toggleClass("disabled", saving).text(saving ? __("Saving...") : __("Save Dimensioning Set"));
    }
}

function builderSetFromPayload(payload) {
    const set = {
        docname: payload.name || "",
        name: payload.set_name || payload.name || __("New Dimensioning Set"),
        description: payload.description || "",
        is_active: !!payload.is_active,
        fields: (payload.fields || []).map((field) => ({
            ...field,
            is_required: !!field.is_required,
            options: Array.isArray(field.options) ? field.options.join("\n") : field.options || "",
        })),
        derived_fields: (payload.derived_fields || []).map((field) => ({ ...field })),
        item_rules: [],
    };
    (payload.rule_groups || []).forEach((group) => {
        (group.articles || []).forEach((article) => {
            const rule = ruleRow(
                article.rule_label || article.item,
                article.item || "",
                article.display_group || "",
                article.quantity_mode === "question" ? article.quantity_question_key || "1" : String(article.fixed_qty || "1"),
                "",
                !!article.show_in_detail
            );
            Object.assign(rule, {
                sequence: article.sequence || group.sequence || 10,
                is_active: !!article.is_active,
                rule_group: group.rule_group || "",
                condition_mode: group.condition_mode || "always",
                question_key: group.question_key || "",
                operator: group.operator || "==",
                compare_source: group.compare_source || "manual",
                manual_value: group.manual_value || "",
                compare_question_key: group.compare_question_key || "",
                quantity_mode: article.quantity_mode === "question" ? "question" : "fixed",
                fixed_qty: String(article.fixed_qty || "1"),
                quantity_question_key: article.quantity_question_key || "",
                item_selection_mode: article.item_selection_mode || "fixed",
                item_filters_json: article.item_filters_json || "",
                item_filters: parseRuleItemFilters(article.item_filters_json),
                condition_formula: article.condition_formula || "",
                qty_formula: article.qty_formula || "",
                uses_advanced_formula: !!((article.condition_formula || "").trim() || (article.qty_formula || "").trim()),
            });
            ensureStructuredRule(rule, set);
            set.item_rules.push(rule);
        });
    });
    return set;
}

function payloadFromBuilderSet(set) {
    return {
        name: set.docname || "",
        set_name: set.name || "",
        description: set.description || "",
        is_active: set.is_active ? 1 : 0,
        fields: (set.fields || []).map((field, index) => ({
            ...field,
            sequence: field.sequence || (index + 1) * 10,
            options: splitOptions(field.options),
            is_required: field.is_required ? 1 : 0,
        })),
        derived_fields: (set.derived_fields || []).map((field, index) => ({
            ...field,
            sequence: field.sequence || (index + 1) * 10,
        })),
        rule_groups: getArticleRuleGroups(set).map((group, groupIndex) => ({
            rule_group: group.key === "__always__" ? `GROUP-${groupIndex + 1}` : group.key,
            sequence: (groupIndex + 1) * 100,
            is_active: 1,
            condition_mode: group.condition_state.mode || "always",
            question_key: group.condition_state.question_key || "",
            operator: group.condition_state.operator || "==",
            compare_source: group.condition_state.compare_source || "manual",
            manual_value: group.condition_state.manual_value || "",
            compare_question_key: group.condition_state.compare_question_key || "",
            articles: group.rules.map(({ rule, index }, articleIndex) => ({
                sequence: rule.sequence || (groupIndex + 1) * 100 + articleIndex + 1,
                is_active: rule.is_active ? 1 : 0,
                rule_label: rule.rule_label || rule.item || `Article ${articleIndex + 1}`,
                item_selection_mode: rule.item_selection_mode || "fixed",
                item: rule.item || "",
                item_filters_json: JSON.stringify(normalizeRuleItemFilters(rule)),
                display_group: rule.display_group || "",
                quantity_mode: rule.quantity_mode === "question" ? "question" : "fixed",
                fixed_qty: rule.fixed_qty || 1,
                quantity_question_key: rule.quantity_question_key || "",
                condition_formula: rule.uses_advanced_formula ? compileStructuredCondition(rule, set) : "",
                qty_formula: rule.uses_advanced_formula ? compileQuantityFormula(rule) : "",
                show_in_detail: rule.show_in_detail ? 1 : 0,
            })),
        })),
    };
}

function toggleQuestionCard(page, index) {
    ODS_STATE.openQuestionCards[index] = !ODS_STATE.openQuestionCards[index];
    renderDimensioningBuilder(page);
}

function toggleRuleGroup(page, index) {
    ODS_STATE.openRuleGroups[index] = !ODS_STATE.openRuleGroups[index];
    renderDimensioningBuilder(page);
}

function updateConfigValue(el) {
    const set = getActiveSet();
    const kind = el.dataset.updateKind;
    const index = Number(el.dataset.updateIndex) || 0;
    const field = el.dataset.updateField;
    const target = kind === "field" ? set.fields[index] : kind === "derived" ? set.derived_fields[index] : set.item_rules[index];
    if (!target) return;
    if (el.type === "checkbox") target[field] = el.checked;
    else if (field === "sequence") target[field] = Number(el.value) || 0;
    else target[field] = el.value;
    if (kind === "field" && field === "label" && isGeneratedDimensioningKey(target.field_key)) {
        target.field_key = uniqueDimensioningKey(set, target.label || "question", index);
    }
}

function buildDefaultValues(set) {
    const values = {};
    for (const field of set.fields || []) {
        values[field.field_key] = coerceBuilderValue(field.field_type, field.default_value);
    }
    return values;
}

function buildPreview(set, rawValues) {
    const inputs = {};
    const derived = {};
    const errors = [];
    const generated = [];
    let matchedCount = 0;
    let skippedCount = 0;

    for (const field of set.fields || []) {
        inputs[field.field_key] = coerceBuilderValue(field.field_type, rawValues[field.field_key]);
    }

    const context = { ...inputs };
    for (const field of set.derived_fields || []) {
        try {
            const value = evaluateBuilderFormula(field.formula, context);
            derived[field.field_key] = coerceBuilderValue(field.field_type, value);
            context[field.field_key] = derived[field.field_key];
        } catch (error) {
            errors.push({ source: field.field_key, message: error.message || String(error) });
        }
    }

    for (const rule of set.item_rules || []) {
        ensureStructuredRule(rule, set);
        const rowKey = rule.sequence ? `row_${rule.sequence}` : "";
        if (!rule.is_active) {
            if (rowKey) context[rowKey] = 0;
            skippedCount += 1;
            continue;
        }
        try {
            const condition = (rule.condition_formula || "").trim() ? !!evaluateBuilderFormula(rule.condition_formula, context) : true;
            if (!condition) {
                if (rowKey) context[rowKey] = 0;
                skippedCount += 1;
                continue;
            }
            const qty = Number(evaluateBuilderFormula(rule.qty_formula || "0", context)) || 0;
            if (rowKey) context[rowKey] = qty;
            if (qty <= 0) {
                skippedCount += 1;
                continue;
            }
            const isFilteredItem = (rule.item_selection_mode || "fixed") === "filtered";
            const itemInfo = isFilteredItem ? {} : getCachedItemInfo(rule.item);
            generated.push({
                rule_label: rule.rule_label,
                item: isFilteredItem ? __("Filtered Item") : rule.item || "",
                item_name: isFilteredItem ? describeItemFilters(rule) : itemInfo.item_name || "",
                unit: itemInfo.unit || "",
                qty,
                display_group: rule.display_group || itemInfo.item_group || "Ungrouped",
                show_in_detail: !!rule.show_in_detail,
                missing_item: !isFilteredItem && !!rule.item && (!itemInfo.item || itemInfo.missing),
                filtered_item: isFilteredItem,
                missing_price: !!itemInfo.missing_price,
            });
            matchedCount += 1;
        } catch (error) {
            errors.push({ source: rule.rule_label || rule.item || "Rule", message: error.message || String(error) });
        }
    }

    return { inputs, derived, generated, errors, matched_count: matchedCount, skipped_count: skippedCount };
}

function validateSet(set, preview) {
    const issues = [];
    const keys = new Set();
    for (const field of set.fields || []) {
        if (!field.field_key) issues.push({ level: "error", title: "Question needs an advanced key", message: `${field.label || "Question"} needs a unique key so formulas can reference it.` });
        if (keys.has(field.field_key)) issues.push({ level: "error", title: "Duplicate question key", message: `${field.field_key} is used more than once.` });
        keys.add(field.field_key);
        if (field.field_type === "Select" && !splitOptions(field.options).length) issues.push({ level: "warning", title: "Choice question has no choices", message: `${field.label || field.field_key} should define choices.` });
    }
    for (const rule of set.item_rules || []) {
        if ((rule.item_selection_mode || "fixed") === "filtered") {
            if (!normalizeRuleItemFilters(rule).length) issues.push({ level: "error", title: "Filtered rule needs filters", message: `${rule.rule_label || "Rule"} needs at least one Item filter.` });
        } else if (!rule.item) {
            issues.push({ level: "error", title: "Article rule needs an item", message: `${rule.rule_label || "Rule"} needs an item code.` });
        }
        if (!rule.qty_formula) issues.push({ level: "error", title: "Article rule needs a quantity", message: `${rule.rule_label || rule.item || "Rule"} needs a quantity value or formula.` });
    }
    for (const error of preview.errors || []) {
        issues.push({ level: "error", title: `Formula needs review: ${error.source}`, message: error.message });
    }
    for (const row of preview.generated || []) {
        if (row.missing_item) issues.push({ level: "warning", title: "Item not found", message: `${row.item || row.rule_label} was not found in the item catalog.` });
        if (row.filtered_item) issues.push({ level: "warning", title: "Filtered item resolves on server", message: `${row.rule_label || row.item} will resolve against the live Item catalog when generated.` });
        if (row.missing_price) issues.push({ level: "warning", title: "Price warning", message: `${row.item} generated but has a sample missing price warning.` });
    }
    return issues;
}

function evaluateBuilderFormula(expression, context) {
    const expr = normalizeBuilderFormula(expression);
    if (!expr) return 0;
    const helpers = {
        concat: (...values) => values.map((value) => String(value ?? "")).join(""),
        ifelse: (condition, yes, no) => (condition ? yes : no),
        contains: (text, needle) => String(text || "").toLowerCase().includes(String(needle || "").toLowerCase()),
        one_of: (value, ...options) => options.includes(value),
        abs: Math.abs,
        ceil: Math.ceil,
        floor: Math.floor,
        float: (value) => Number.parseFloat(value || 0),
        int: (value) => Math.floor(Number(value) || 0),
        lower: (value) => String(value || "").toLowerCase(),
        upper: (value) => String(value || "").toUpperCase(),
        to_int: (value) => Number.parseInt(value || 0, 10),
        to_float: (value) => Number.parseFloat(value || 0),
        min: Math.min,
        max: Math.max,
        round: Math.round,
    };
    const names = [...Object.keys(context), ...Object.keys(helpers)];
    const values = [...Object.values(context), ...Object.values(helpers)];
    // Frontend-only evaluator. Backend integration must use the server-side safe formula evaluator.
    return Function(...names, `"use strict"; return (${expr});`)(...values);
}

function normalizeBuilderFormula(expression) {
    return String(expression || "")
        .trim()
        .replace(/\band\b/gi, "&&")
        .replace(/\bor\b/gi, "||")
        .replace(/\bnot\b/gi, "!")
        .replace(/\btrue\b/gi, "true")
        .replace(/\bfalse\b/gi, "false");
}

function getCachedItemInfo(itemCode) {
    const item = String(itemCode || "").trim();
    return item ? (ODS_ITEM_CACHE[item] || {}) : {};
}

async function fetchDimensioningItemInfo(itemCode) {
    const item = String(itemCode || "").trim();
    if (!item) return null;
    if (ODS_ITEM_CACHE[item]?.__lookup_attempted) return ODS_ITEM_CACHE[item];
    ODS_ITEM_CACHE[item] = { ...(ODS_ITEM_CACHE[item] || { item }), __lookup_attempted: true };
    try {
        const res = await frappe.db.get_value("Item", item, ["item_name", "item_group", "stock_uom", "description"]);
        const message = res.message || {};
        if (!Object.keys(message).length) {
            ODS_ITEM_CACHE[item].missing = true;
            return ODS_ITEM_CACHE[item];
        }
        ODS_ITEM_CACHE[item] = {
            item,
            item_name: message.item_name || item,
            item_group: message.item_group || "",
            unit: message.stock_uom || "",
            description: message.description || "",
            __from_db: true,
            __lookup_attempted: true,
        };
        return ODS_ITEM_CACHE[item];
    } catch (error) {
        console.error("Dimensioning item lookup failed", error);
        return ODS_ITEM_CACHE[item] || null;
    }
}

function coerceBuilderValue(fieldType, value) {
    const type = (fieldType || "Data").trim();
    if (type === "Check") return value === true || value === 1 || String(value).toLowerCase() === "true" || String(value) === "1";
    if (type === "Int") return Number.parseInt(value || 0, 10) || 0;
    if (type === "Float") return Number.parseFloat(value || 0) || 0;
    return value == null ? "" : String(value);
}

function getContextKeys(set) {
    return [...(set.fields || []).map((row) => row.field_key), ...(set.derived_fields || []).map((row) => row.field_key)].filter(Boolean);
}

function splitOptions(options) {
    return String(options || "").split(/\r?\n/).map((row) => row.trim()).filter(Boolean);
}

function uniqueDimensioningKey(set, label, currentIndex = -1) {
    const base = slugDimensioningKey(label) || "question";
    const used = new Set(getContextKeys(set).filter((_, index) => index !== currentIndex));
    if (!used.has(base)) return base;
    let suffix = 2;
    while (used.has(`${base}_${suffix}`)) suffix += 1;
    return `${base}_${suffix}`;
}

function slugDimensioningKey(label) {
    const slug = String(label || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "")
        .replace(/^[0-9]+/, "");
    return slug || "question";
}

function isGeneratedDimensioningKey(key) {
    return /^(new_)?(question|calculation)(_[0-9]+)?$/.test(String(key || ""));
}

function groupBy(rows, getKey) {
    return rows.reduce((groups, row) => {
        const key = getKey(row);
        groups[key] = groups[key] || [];
        groups[key].push(row);
        return groups;
    }, {});
}

function injectDimensioningBuilderStyles() {
    if (document.getElementById("ods-builder-styles")) return;
    const style = document.createElement("style");
    style.id = "ods-builder-styles";
    style.textContent = `
        .ods-builder-root { background: #f5f6fa; font-family: InterVariable, Inter, -apple-system, system-ui, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif; margin: -15px; min-height: calc(100vh - 56px); padding: 0; }
        .ods-shell { color: #0f172a; margin: 0; max-width: none; padding: 0; }
        .ods-hero { align-items: flex-start; background: #fff; border-bottom: 1px solid #e2e8f0; border-radius: 0; box-shadow: none; color: #0f172a; display: grid; gap: 24px; grid-template-columns: minmax(280px, 1fr) minmax(360px, 58vw); padding: 14px 24px 12px; }
        .ods-eyebrow { color: #00b0c8; display: inline-flex; font-size: 10px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }
        .ods-hero h1 { color: #0f172a; font-size: 21px; font-weight: 800; letter-spacing: -.025em; line-height: 1.15; margin: 2px 0 3px; }
        .ods-hero p { color: #64748b; font-size: 12px; line-height: 1.45; margin: 0; max-width: 620px; }
        .ods-hero-stats { display: grid; gap: 8px; grid-template-columns: repeat(4, minmax(118px, 1fr)); width: 100%; }
        .ods-metric { background: #fff; border: 1px solid #e2e8f0; border-radius: 14px; box-shadow: 0 1px 2px rgba(15,23,42,.04); min-height: 58px; padding: 9px 11px; }
        .ods-metric span { color: #94a3b8; display: block; font-size: 10px; font-weight: 800; letter-spacing: .08em; overflow: hidden; text-overflow: ellipsis; text-transform: uppercase; white-space: nowrap; }
        .ods-metric strong { color: #0f172a; display: block; font-size: 18px; font-weight: 800; letter-spacing: -.025em; margin-top: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .ods-metric.ok strong { color: #047857; } .ods-metric.warn strong { color: #b45309; } .ods-metric.danger strong { color: #be123c; }
        .ods-workspace { align-items: start; display: grid; gap: 18px; grid-template-columns: minmax(0, 1fr); margin-top: 0; padding: 18px 24px 18px; }
        .ods-nav, .ods-live-panel, .ods-card, .ods-mini-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 16px; box-shadow: 0 2px 5px rgba(15,23,42,.04), 0 16px 32px -24px rgba(15,23,42,.24); }
        .ods-nav { align-items: center; background: rgba(255,255,255,.96); border: 0; border-bottom: 1px solid #e2e8f0; border-radius: 0; box-shadow: 0 8px 20px rgba(15,23,42,.04); display: flex; gap: 8px; overflow-x: auto; padding: 10px 24px; position: sticky; top: 0; z-index: 15; }
        .ods-nav-title { color: #94a3b8; flex: 0 0 auto; font-size: 10px; font-weight: 900; letter-spacing: .1em; margin-right: 4px; text-transform: uppercase; }
        .ods-nav-item { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; color: #334155; cursor: pointer; display: grid; flex: 1 1 150px; gap: 3px; min-height: 46px; min-width: 136px; overflow: hidden; padding: 8px 10px 8px 13px; position: relative; text-align: left; transition: transform .18s cubic-bezier(.16, 1, .3, 1), border-color .18s ease, background .18s ease, box-shadow .18s ease; }
        .ods-nav-item::before { background: #00b0c8; border-radius: 999px; bottom: 7px; content: ""; left: 0; position: absolute; top: 7px; width: 3px; }
        .ods-nav-item span { color: #94a3b8; font-size: 10px; font-weight: 800; letter-spacing: .08em; }
        .ods-nav-item strong { color: #334155; font-size: 11px; font-weight: 850; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .ods-nav-item:hover { background: #fff; border-color: #a5f3fc; box-shadow: 0 0 0 3px rgba(0,176,200,.08); transform: translateY(-1px); }
        .ods-nav-item.active { background: #ecfeff; border-color: #67e8f9; box-shadow: 0 0 0 3px rgba(0,176,200,.12); color: #0e7490; } .ods-nav-item.active span, .ods-nav-item.active strong { color: #0e7490; }
        .ods-editor { min-width: 0; }
        .ods-card { background: #fff; border-color: #e2e8f0; border-left: 0; margin-bottom: 14px; padding: 14px; }
        .ods-section-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
        .ods-section-head h2, .ods-mini-card h3, .ods-guidance h3 { margin: 0; color: #0f172a; font-weight: 750; }
        .ods-section-head p, .ods-mini-card p, .ods-guidance p { color: #64748b; margin: 4px 0 0; line-height: 1.5; }
        .ods-start-grid { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 16px; align-items: start; }
        .ods-next-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
        .ods-simple-summary { display: grid; gap: 10px; }
        .ods-simple-step { align-items: center; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 16px; color: #0f172a; display: grid; gap: 10px; grid-template-columns: 34px 1fr; min-height: 64px; padding: 12px; text-align: left; }
        .ods-simple-step:hover { background: #eef6ff; border-color: #bfdbfe; }
        .ods-simple-step > span { align-items: center; background: #dbeafe; border-radius: 999px; color: #1d4ed8; display: inline-flex; font-size: 12px; font-weight: 850; height: 34px; justify-content: center; width: 34px; }
        .ods-simple-step strong, .ods-simple-step small { display: block; } .ods-simple-step small { color: #64748b; margin-top: 2px; }
        .ods-quick-explain { background: #fff; border-bottom: 1px solid #e2e8f0; color: #0f172a; display: grid; gap: 2px; margin: 0 -24px 14px; padding: 11px 24px; }
        .ods-quick-explain strong { color: #0f172a; font-size: 13px; font-weight: 850; } .ods-quick-explain span { color: #64748b; font-size: 12px; line-height: 1.45; }
        .ods-question-layout { display: grid; grid-template-columns: 360px minmax(0, 1fr); gap: 16px; align-items: start; }
        .ods-sales-preview-card, .ods-question-edit-list { min-width: 0; }
        .ods-sales-preview-card { background: #f8fafc; border: 2px solid #94a3b8; border-radius: 16px; box-shadow: 0 8px 20px rgba(15,23,42,.08); padding: 14px; position: sticky; top: 72px; }
        .ods-preview-title { margin-bottom: 12px; }
        .ods-preview-title strong, .ods-preview-title span { display: block; } .ods-preview-title strong { color: #0f172a; font-size: 15px; } .ods-preview-title span { color: #64748b; font-size: 12px; margin-top: 2px; }
        .ods-sales-preview-list { display: grid; gap: 10px; }
        .ods-sales-question { background: #fff; border: 1px solid #94a3b8; border-radius: 12px; display: grid; gap: 7px; padding: 10px; }
        .ods-sales-question label { color: #334155; font-size: 12px; font-weight: 800; }
        .ods-sales-question input, .ods-sales-question select { background: #f8fafc; border: 1px solid #dbe3ef; border-radius: 12px; color: #0f172a; min-height: 40px; padding: 9px 11px; width: 100%; }
        .ods-sales-question small { color: #64748b; line-height: 1.4; }
        .ods-required-dot { background: #fff7ed; border: 1px solid #fed7aa; border-radius: 999px; color: #9a3412; display: inline-flex; font-size: 10px; margin-left: 6px; padding: 1px 6px; }
        .ods-preview-check { align-items: center; display: flex !important; flex-direction: row !important; gap: 8px; }
        .ods-preview-check input { width: auto; }
        .ods-form-grid { display: grid; gap: 8px; } .ods-form-grid.one { grid-template-columns: 1fr; } .ods-form-grid.two { grid-template-columns: repeat(2, minmax(0, 1fr)); } .ods-form-grid.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
        .ods-field, .ods-check-field { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
        .ods-field.wide { grid-column: 1 / -1; }
        .ods-field span, .ods-check-field span { color: #475569; font-size: 11px; font-weight: 760; }
        .ods-field small { color: #64748b; font-size: 12px; line-height: 1.4; }
        .ods-field input, .ods-field select, .ods-field textarea, .ods-mini-card select, .ods-assistant select { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; color: #334155; font-size: 12px; font-weight: 650; min-height: 36px; outline: none; padding: 0 11px; transition: border-color .16s ease, box-shadow .16s ease, background .16s ease; width: 100%; }
        .ods-field input:focus, .ods-field select:focus, .ods-field textarea:focus { background: #fff; border-color: #00b0c8; box-shadow: 0 0 0 4px rgba(0,176,200,.1); }
        .ods-field textarea { resize: vertical; }
        .ods-code-input, .ods-payload { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
        .ods-check-field { align-items: center; flex-direction: row; min-height: 34px; padding-top: 16px; }
        .ods-check-field input { margin: 0; }
        .ods-list { display: grid; gap: 12px; }
        .ods-row-card { background: radial-gradient(circle at 100% 0%, rgba(99,102,241,.05), transparent 34%), #fff; border: 1.5px solid #cbd5e1; border-radius: 16px; box-shadow: 0 2px 5px rgba(15,23,42,.06), 0 18px 42px -28px rgba(15,23,42,.30); padding: 12px; position: relative; }
        .ods-row-card::before { background: #00b0c8; border-radius: 999px; bottom: 12px; content: ""; left: 0; opacity: .72; position: absolute; top: 12px; width: 3px; }
        .ods-question-card { overflow: hidden; padding: 0; transition: border-color .18s ease, box-shadow .22s cubic-bezier(.16, 1, .3, 1), transform .22s cubic-bezier(.16, 1, .3, 1); }
        .ods-question-card:hover { border-color: #67e8f9; box-shadow: 0 8px 18px rgba(15,23,42,.10), 0 24px 52px -24px rgba(15,23,42,.34); transform: translateY(-1px); }
        .ods-question-card::before { bottom: 10px; top: 10px; width: 4px; z-index: 1; }
        .ods-question-card.is-collapsed { box-shadow: 0 4px 8px rgba(15,23,42,.04), 0 16px 32px -18px rgba(15,23,42,.14); }
        .ods-row-top { align-items: center; cursor: default; display: grid; gap: 8px; grid-template-columns: 34px minmax(0, 1fr) auto auto 34px; list-style: none; margin: 0; min-height: 58px; padding: 10px 10px 10px 13px; position: relative; }
        .ods-row-top[data-toggle-question] { background: linear-gradient(135deg, #fff 0%, #f8fafc 100%); cursor: pointer; }
        .ods-question-card.is-open, .ods-rule-group-card.is-open { border-color: #94a3b8; box-shadow: 0 8px 18px rgba(15,23,42,.08), 0 28px 60px -30px rgba(15,23,42,.36); }
        .ods-question-card.is-open .ods-rule-toggle-indicator, .ods-rule-group-card.is-open .ods-rule-toggle-indicator { background: #ecfeff; border-color: #67e8f9; color: #0e7490; }
        .ods-row-top:focus-visible, .ods-rule-group-head:focus-visible { box-shadow: inset 0 0 0 3px rgba(0,176,200,.18); outline: 0; }
        .ods-row-index { align-items: center; background: #e8f0ff; border-radius: 999px; color: #1d4ed8; display: inline-flex; font-size: 12px; font-weight: 800; height: 26px; justify-content: center; width: 26px; }
        .ods-question-summary-copy { display: grid; gap: 2px; min-width: 0; }
        .ods-question-summary-copy strong { color: #0f172a; font-size: 13px; font-weight: 850; letter-spacing: -.02em; line-height: 1.18; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .ods-question-summary-copy small { color: #94a3b8; font-size: 10px; font-weight: 600; line-height: 1.3; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .ods-question-card-body { border-top: 1px solid #eff1f4; display: grid; gap: 10px; padding: 10px 12px 12px; }
        .ods-badge { background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 999px; color: #475569; display: inline-flex; font-size: 11px; font-weight: 750; padding: 3px 8px; }
        .ods-badge.preview { background: #fef3c7; border-color: #fde68a; color: #92400e; } .ods-badge.warn { background: #fff7ed; border-color: #fed7aa; color: #9a3412; } .ods-badge.danger { background: #fef2f2; border-color: #fecaca; color: #b91c1c; } .ods-badge.muted { background: #f8fafc; color: #64748b; }
        .ods-icon-button { border: 0; border-radius: 10px; height: 40px; margin-left: auto; width: 40px; }
        .ods-icon-button.danger { background: #fff1f2; color: #be123c; }
        .ods-guidance-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 12px; }
        .ods-guidance-grid > div { background: #f8fafc; border: 2px solid #cbd5e1; border-radius: 14px; padding: 14px; }
        .ods-helper-strip { background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 14px; display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; padding: 10px; }
        .ods-helper-label { align-items: center; color: #64748b; display: inline-flex; font-size: 12px; font-weight: 750; margin-right: 2px; }
        .ods-token { background: #eef6ff; border: 1px solid #bfdbfe; border-radius: 999px; color: #1d4ed8; font-family: ui-monospace, monospace; font-size: 12px; padding: 4px 8px; }
        .ods-advanced-inline { border-top: 1px solid #e4e8f0; margin-top: 14px; padding-top: 12px; }
        .ods-advanced-inline summary { color: #475569; cursor: pointer; font-size: 12px; font-weight: 800; list-style-position: inside; }
        .ods-advanced-inline .ods-field { margin-top: 10px; }
        .ods-article-list { display: grid; gap: 10px; }
        .ods-rule-group-card { background: #fff; border: 1.5px solid #cbd5e1; border-radius: 16px; box-shadow: 0 2px 5px rgba(15,23,42,.08), 0 18px 42px -24px rgba(15,23,42,.35); overflow: hidden; padding: 0; transition: border-color .18s ease, box-shadow .22s cubic-bezier(.16, 1, .3, 1), transform .22s cubic-bezier(.16, 1, .3, 1); }
        .ods-rule-group-card.is-open { overflow: visible; position: relative; z-index: 120; }
        .ods-rule-group-card:hover { border-color: #67e8f9; box-shadow: 0 8px 18px rgba(15,23,42,.10), 0 24px 52px -24px rgba(15,23,42,.42); transform: translateY(-1px); }
        .ods-rule-group-card.is-collapsed { box-shadow: 0 4px 8px rgba(15,23,42,.04), 0 16px 32px -18px rgba(15,23,42,.14); }
        .ods-rule-group-head { align-items: center; background: linear-gradient(135deg, #fff 0%, #f8fafc 100%); cursor: pointer; display: grid; gap: 8px; grid-template-columns: 34px minmax(0, 1fr) auto auto; list-style: none; padding: 10px 10px 10px 13px; position: relative; }
        .ods-rule-group-head::before { background: #00b0c8; bottom: 10px; content: ""; left: 0; opacity: .78; position: absolute; top: 10px; width: 4px; }
        .ods-rule-group-head h3 { color: #0f172a; font-size: 13px; font-weight: 850; letter-spacing: -.02em; line-height: 1.18; margin: 0; }
        .ods-rule-group-head p { color: #64748b; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; margin: 2px 0 0; }
        .ods-rule-group-preview { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 7px; }
        .ods-rule-group-preview span { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 999px; color: #64748b; display: inline-flex; font-size: 10px; font-weight: 760; gap: 4px; max-width: 190px; overflow: hidden; padding: 2px 7px; text-overflow: ellipsis; white-space: nowrap; }
        .ods-rule-group-preview code { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; color: #334155; display: block; font-size: 10px; max-height: 42px; max-width: 360px; overflow: auto; padding: 5px 7px; white-space: pre-wrap; }
        .ods-rule-group-preview strong { color: #0f172a; font-weight: 900; }
        .ods-hierarchy-kicker { color: #00b0c8; display: block; font-size: 9px; font-weight: 900; letter-spacing: .1em; margin-bottom: 2px; text-transform: uppercase; }
        .ods-rule-toggle-indicator { align-items: center; background: #fff; border: 1px solid #e2e8f0; border-radius: 999px; color: #64748b; display: inline-flex; font-size: 10px; font-weight: 900; min-height: 24px; padding: 0 8px; white-space: nowrap; }
        .ods-rule-group-card:hover .ods-rule-toggle-indicator { background: #ecfeff; border-color: #a5f3fc; color: #0e7490; }
        .ods-rule-group-body { border-top: 1px solid #eff1f4; display: grid; gap: 12px; padding: 10px 12px 12px; }
        .ods-hierarchy-block { border-radius: 12px; display: grid; gap: 8px; padding: 9px; }
        .ods-hierarchy-block.when { background: #f8fafc; border: 1px solid #eef2f7; }
        .ods-hierarchy-block.then { background: #fff; border: 1px solid #e2e8f0; }
        .ods-hierarchy-label { color: #94a3b8; font-size: 9px; font-weight: 900; letter-spacing: .1em; line-height: 1; text-transform: uppercase; }
        .ods-rule-condition-card { background: transparent; border: 0; border-radius: 0; display: grid; gap: 8px; grid-template-columns: repeat(4, minmax(0, 1fr)); margin-bottom: 0; padding: 0; }
        .ods-rule-condition-card details { grid-column: 1 / -1; }
        .ods-condition-summary { background: #ecfeff; border: 1px solid #bae6fd; border-radius: 10px; display: grid; gap: 2px; grid-column: 1 / -1; padding: 7px 9px; }
        .ods-condition-summary span { color: #0e7490; font-size: 9px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
        .ods-condition-summary strong { color: #0f172a; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 11px; }
        .ods-group-articles { border-top: 2px solid #e2e8f0; padding-top: 10px; }
        .ods-group-articles-head { align-items: center; display: flex; justify-content: space-between; gap: 8px; }
        .ods-group-articles-head strong { color: #334155; font-size: 13px; }
        .ods-group-article-list { display: grid; gap: 6px; }
        .ods-article-picker-details { border-top: 1px dashed #dbe3ef; margin-top: 6px; padding-top: 6px; }
        .ods-article-picker-details summary { color: #64748b; cursor: pointer; font-size: 11px; font-weight: 850; list-style-position: inside; }
        .ods-article-picker { background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 12px; margin-top: 7px; padding: 8px; }
        .ods-article-picker > span { color: #64748b; display: block; font-size: 12px; font-weight: 800; margin-bottom: 8px; }
        .ods-article-picker > div { display: flex; flex-wrap: wrap; gap: 8px; }
        .ods-picker-chip { background: #fff; border: 1px solid #e2e8f0; border-radius: 9px; color: #334155; min-height: 34px; max-width: 210px; padding: 5px 8px; text-align: left; transition: background .16s ease, border-color .16s ease, color .16s ease, transform .16s cubic-bezier(.16, 1, .3, 1); }
        .ods-picker-chip:hover { background: #ecfeff; border-color: #a5f3fc; color: #0e7490; transform: translateY(-1px); }
        .ods-picker-chip strong, .ods-picker-chip small { display: block; } .ods-picker-chip small { color: #64748b; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .ods-article-row { align-items: start; background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; display: grid; gap: 8px; grid-template-columns: minmax(260px, 1.3fr) minmax(190px, .8fr) auto 40px; padding: 8px; transition: background .16s ease, border-color .16s ease, box-shadow .16s ease; }
        .ods-article-row:hover { background: #fbfdff; border-color: #bae6fd; box-shadow: 0 8px 18px -18px rgba(15,23,42,.42); }
        .ods-article-row.muted { opacity: .68; }
        .ods-article-row-main { min-width: 0; }
        .ods-article-row-title { align-items: end; display: grid; gap: 7px; grid-template-columns: 24px minmax(94px, 116px) minmax(132px, 180px) minmax(0, 1fr); }
        .ods-article-row-index { align-items: center; align-self: center; background: #e0f2fe; border-radius: 999px; color: #0369a1; display: inline-flex; font-size: 11px; font-weight: 900; height: 24px; justify-content: center; width: 24px; }
        .ods-article-name { align-self: center; display: grid; gap: 1px; min-width: 0; }
        .ods-article-name strong { color: #0f172a; font-size: 12px; font-weight: 850; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .ods-article-name small { color: #94a3b8; font-size: 10px; font-weight: 650; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .ods-filter-summary { align-self: end; background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 12px; display: grid; gap: 2px; min-height: 36px; min-width: 0; padding: 6px 9px; }
        .ods-filter-summary span { color: #64748b; font-size: 9px; font-weight: 900; letter-spacing: .07em; text-transform: uppercase; }
        .ods-filter-summary strong { color: #0f172a; font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .ods-item-filter-editor.wide { grid-column: 1 / -1; }
        .ods-item-filter-editor { background: #f8fafc; border: 1px solid #e8ebef; border-radius: 14px; display: grid; gap: 8px; padding: 9px; }
        .ods-filter-editor-head { align-items: center; display: flex; justify-content: space-between; gap: 8px; }
        .ods-filter-editor-head strong, .ods-filter-editor-head span { display: block; }
        .ods-filter-editor-head strong { color: #0f172a; font-size: 12px; font-weight: 850; }
        .ods-filter-editor-head span { color: #64748b; font-size: 11px; margin-top: 2px; }
        .ods-item-filter-list { display: grid; gap: 6px; }
        .ods-item-filter-row { align-items: end; background: #fff; border: 1px solid #e8ebef; border-radius: 12px; display: grid; gap: 7px; grid-template-columns: minmax(96px, .8fr) minmax(128px, 1fr) 86px 100px minmax(136px, 1fr) 34px; padding: 7px; }
        .ods-compact-field { display: grid; gap: 3px; min-width: 0; }
        .ods-compact-field span { color: #64748b; font-size: 9px; font-weight: 900; letter-spacing: .07em; text-transform: uppercase; }
        .ods-compact-field input, .ods-compact-field select { background: #f8fafc; border: 1px solid #dbe3ef; border-radius: 9px; color: #0f172a; font-size: 11px; font-weight: 750; height: 31px; outline: none; padding: 0 8px; width: 100%; }
        .ods-compact-field input:focus, .ods-compact-field select:focus { background: #fff; border-color: #00b0c8; box-shadow: 0 0 0 3px rgba(0,176,200,.1); }
        .ods-item-search-row { align-items: center; display: grid; gap: 6px; grid-template-columns: minmax(0, 1fr) auto; }
        .ods-item-search-row .btn { white-space: nowrap; }
        .ods-item-link-host, .ods-item-link-host .awesomplete { overflow: visible; position: relative; }
        .ods-item-link-host .awesomplete > ul { bottom: auto !important; max-height: 320px; min-width: 280px; overflow-y: auto; top: calc(100% + 4px) !important; z-index: 10050 !important; }
        .ods-item-link-host.ods-awesomplete-above .awesomplete > ul { bottom: calc(100% + 4px) !important; top: auto !important; }
        .ods-article-row-qty { background: #f8fafc; border: 1px solid #eef2f7; border-radius: 10px; display: grid; gap: 6px; grid-template-columns: minmax(88px, .72fr) minmax(90px, 1fr); padding: 7px; }
        .ods-formula-summary { grid-template-columns: 1fr; }
        .ods-formula-summary span { color: #64748b; font-size: 9px; font-weight: 900; letter-spacing: .07em; text-transform: uppercase; }
        .ods-formula-summary code { color: #0f172a; display: block; font-size: 10px; line-height: 1.35; max-height: 46px; overflow: auto; white-space: pre-wrap; }
        .ods-article-row-flags { align-content: start; display: grid; gap: 5px; min-width: 84px; padding-top: 1px; }
        .ods-compact-check { align-items: center; color: #475569; display: flex; font-size: 11px; font-weight: 760; gap: 5px; min-height: 24px; white-space: nowrap; }
        .ods-compact-check input { margin: 0; }
        .ods-article-remove { align-self: start; height: 34px; width: 34px; }
        .ods-article-row-more { border-top: 1px solid #eef2f7; grid-column: 1 / -1; margin-top: 1px; padding-top: 6px; }
        .ods-article-row-more summary { color: #64748b; cursor: pointer; font-size: 10px; font-weight: 850; list-style-position: inside; }
        .ods-article-row-more .ods-form-grid { margin-top: 7px; }
        .ods-empty-articles { padding: 12px; text-align: left; }
        .ods-article-card { background: radial-gradient(circle at 100% 0%, rgba(99,102,241,.06), transparent 34%), #fff; border: 1.5px solid #cbd5e1; border-radius: 16px; box-shadow: 0 2px 5px rgba(15,23,42,.08), 0 18px 42px -24px rgba(15,23,42,.35); overflow: hidden; padding: 11px; position: relative; transition: transform .22s cubic-bezier(.16, 1, .3, 1), box-shadow .22s cubic-bezier(.16, 1, .3, 1), border-color .18s ease; }
        .ods-article-card::before { background: #0891b2; bottom: 0; content: ""; left: 0; opacity: .72; position: absolute; top: 0; width: 4px; }
        .ods-article-card:hover { border-color: #67e8f9; box-shadow: 0 8px 18px rgba(15,23,42,.10), 0 24px 52px -24px rgba(15,23,42,.42); transform: translateY(-2px); }
        .ods-article-card:hover::before { opacity: 1; }
        .ods-article-card.muted { opacity: .72; }
        .ods-quantity-controls { background: #f8fafc; border: 1px solid #eef2f7; border-radius: 12px; display: grid; gap: 8px; grid-template-columns: repeat(2, minmax(0, 1fr)); padding: 8px; }
        .ods-quantity-controls.wide { grid-column: 1 / -1; }
        .ods-quantity-controls details { grid-column: 1 / -1; }
        .ods-article-head { align-items: center; display: grid; gap: 8px; grid-template-columns: 34px minmax(0, 1fr) auto 34px; margin-bottom: 8px; }
        .ods-article-card .ods-article-head { grid-template-columns: minmax(0, 1fr) auto 40px; }
        .ods-article-number { align-items: center; background: #1d4ed8; border-radius: 10px; color: #fff; display: inline-flex; font-size: 13px; font-weight: 850; height: 34px; justify-content: center; width: 34px; }
        .ods-article-head h3 { color: #0f172a; font-size: 13px; font-weight: 850; letter-spacing: -.02em; line-height: 1.18; margin: 0; }
        .ods-article-head p { color: #94a3b8; font-size: 10px; font-weight: 600; line-height: 1.35; margin: 2px 0 0; }
        .ods-article-status { display: flex; flex-wrap: wrap; gap: 6px; justify-content: flex-end; }
        .ods-badge.ok-soft { background: #ecfdf5; border-color: #bbf7d0; color: #047857; }
        .ods-advanced-card { padding: 0; overflow: hidden; }
        .ods-advanced-card > summary { align-items: center; cursor: pointer; display: grid; gap: 3px; list-style-position: inside; padding: 16px 18px; }
        .ods-advanced-card > summary strong { color: #0f172a; font-size: 15px; } .ods-advanced-card > summary span { color: #64748b; font-size: 12px; }
        .ods-advanced-card-body { border-top: 1px solid #e4e8f0; padding: 18px; }
        .ods-derived-embedded .ods-section-head { margin-bottom: 14px; }
        .ods-rule-layout { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 14px; }
        .ods-rule-tabs { display: grid; gap: 8px; }
        .ods-rule-tab { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 14px; min-height: 52px; padding: 11px; text-align: left; }
        .ods-rule-tab.active { background: #e8f0ff; border-color: #93c5fd; }
        .ods-rule-tab strong, .ods-rule-tab span { display: block; }
        .ods-rule-tab span { color: #64748b; font-size: 12px; margin-top: 2px; }
        .ods-rule-editor { border: 1px solid #e4e8f0; border-radius: 16px; padding: 14px; }
        .ods-rule-editor-head { align-items: center; display: flex; justify-content: space-between; margin-bottom: 10px; }
        .ods-rule-editor-head h3 { margin: 0; }
        .ods-rule-sentence { align-items: center; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 14px; display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; padding: 10px 12px; }
        .ods-rule-sentence span { color: #64748b; font-size: 12px; font-weight: 750; } .ods-rule-sentence code { background: #eef6ff; border: 1px solid #bfdbfe; border-radius: 8px; color: #1e40af; padding: 3px 6px; } .ods-rule-sentence strong { color: #0f172a; }
        .ods-assistant { align-items: center; display: flex; flex-wrap: wrap; gap: 8px; width: 100%; }
        .ods-assistant > div { display: flex; align-items: center; gap: 8px; }
        .ods-assistant .btn { min-height: 36px; }
        .ods-test-summary { display: grid; gap: 10px; grid-template-columns: repeat(3, minmax(0, 1fr)); margin-bottom: 14px; }
        .ods-test-tile { background: #f8fafc; border: 2px solid #cbd5e1; border-radius: 14px; padding: 12px; }
        .ods-test-tile span { color: #64748b; display: block; font-size: 12px; font-weight: 750; }
        .ods-test-tile strong { color: #0f172a; display: block; font-size: 18px; margin-top: 4px; }
        .ods-test-tile.ok { background: #ecfdf5; border-color: #bbf7d0; } .ods-test-tile.ok strong { color: #047857; }
        .ods-test-tile.warn { background: #fff7ed; border-color: #fed7aa; } .ods-test-tile.warn strong { color: #9a3412; }
        .ods-test-tile.danger { background: #fef2f2; border-color: #fecaca; } .ods-test-tile.danger strong { color: #991b1b; }
        .ods-preview-layout { display: grid; grid-template-columns: 300px 1fr; gap: 14px; }
        .ods-test-panel { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 16px; padding: 14px; }
        .ods-test-panel h3 { margin-top: 0; }
        .ods-result-panel { display: grid; gap: 12px; }
        .ods-live-panel { display: grid; gap: 12px; padding: 12px; position: sticky; top: 72px; }
        .ods-mini-card { padding: 14px; }
        .ods-next-card .btn { margin-top: 10px; width: 100%; }
        .ods-derived-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-top: 10px; }
        .ods-derived-grid div, .ods-coverage { background: #f8fafc; border-radius: 12px; padding: 10px; }
        .ods-derived-grid span, .ods-coverage span { color: #64748b; display: block; font-size: 12px; }
        .ods-generated-list { display: grid; gap: 8px; margin-top: 12px; }
        .ods-generated-group { border-top: 1px solid #e4e8f0; margin-top: 12px; padding-top: 12px; }
        .ods-generated-group > strong { color: #334155; font-size: 12px; text-transform: uppercase; letter-spacing: .06em; }
        .ods-generated-row { align-items: center; background: #f8fafc; border: 1px solid #94a3b8; border-radius: 14px; display: grid; grid-template-columns: 1fr 80px auto; gap: 10px; padding: 10px; }
        .ods-generated-row strong, .ods-generated-row span { display: block; } .ods-generated-row span { color: #64748b; font-size: 12px; }
        .ods-generated-meta { text-align: right; }
        .ods-row-badges { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 5px; }
        .ods-validation-list { display: grid; gap: 8px; margin-top: 10px; }
        .ods-validation { border-radius: 12px; padding: 10px; }
        .ods-validation strong, .ods-validation span { display: block; } .ods-validation span { font-size: 12px; margin-top: 2px; }
        .ods-validation.error { background: #fef2f2; color: #991b1b; } .ods-validation.warning { background: #fff7ed; color: #9a3412; }
        .ods-ok-text { color: #047857 !important; }
        .ods-empty { background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 16px; color: #64748b; padding: 18px; text-align: center; }
        .ods-payload { background: #0f172a; border-radius: 16px; color: #dbeafe; max-height: 640px; overflow: auto; padding: 16px; white-space: pre-wrap; }
        .ods-bottom-bar { align-items: center; background: rgba(255,255,255,.94); border: 1px solid #e2e8f0; border-radius: 18px; bottom: 12px; box-shadow: 0 18px 40px rgba(15,23,42,.12); display: flex; justify-content: space-between; margin: 0 24px 18px; max-width: calc(100% - 48px); padding: 12px 14px; position: sticky; width: auto; z-index: 20; }
        .ods-bottom-bar span { color: #64748b; display: block; font-size: 12px; }
        .ods-bottom-actions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
        .ods-danger-action { border-color: #fecdd3 !important; color: #be123c !important; }
        .ods-builder-root .btn { min-height: 34px; border-radius: 12px; font-size: 12px; font-weight: 850; box-shadow: none; transition: transform .18s cubic-bezier(.16, 1, .3, 1), border-color .16s ease, background .16s ease, box-shadow .16s ease, color .16s ease; }
        .ods-builder-root .btn:hover, .ods-builder-root .btn:focus { transform: translateY(-1px); outline: 3px solid rgba(0,176,200,.1); }
        .ods-builder-root .btn-primary { background: #0f172a; border-color: #0f172a; color: #fff; }
        .ods-builder-root .btn-primary:hover, .ods-builder-root .btn-primary:focus { background: #00b0c8; border-color: #00b0c8; color: #fff; }
        .ods-builder-root .btn-default { background: #f8fafc; border-color: #e2e8f0; color: #475569; }
        .ods-builder-root .btn-default:hover, .ods-builder-root .btn-default:focus { background: #fff; border-color: #a5f3fc; color: #0e7490; }
        .ods-shell * { box-sizing: border-box; }
        .ods-hero { display: flex; justify-content: space-between; align-items: flex-start; min-width: 0; }
        .ods-hero > div:first-child { min-width: 0; max-width: 620px; }
        .ods-hero h1 { color: #0a0e1a; font-weight: 850; }
        .ods-hero-stats { width: min(760px, 58vw); min-width: 0; }
        .ods-metric { border-color: #e8ebef; box-shadow: 0 1px 2px rgba(15,23,42,.04); }
        .ods-metric strong { color: #11151f; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
        .ods-nav { background: #fff; box-shadow: none; padding: 10px 24px; overscroll-behavior-x: contain; }
        .ods-nav::-webkit-scrollbar, .ods-list::-webkit-scrollbar, .ods-group-article-list::-webkit-scrollbar, .ods-generated-list::-webkit-scrollbar { width: 4px; height: 4px; }
        .ods-nav::-webkit-scrollbar-track, .ods-list::-webkit-scrollbar-track, .ods-group-article-list::-webkit-scrollbar-track, .ods-generated-list::-webkit-scrollbar-track { background: transparent; }
        .ods-nav::-webkit-scrollbar-thumb, .ods-list::-webkit-scrollbar-thumb, .ods-group-article-list::-webkit-scrollbar-thumb, .ods-generated-list::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 999px; }
        .ods-nav-title { color: #94a3b8; }
        .ods-nav-item { flex: 0 0 150px; min-width: 150px; background: #f8fafc; border-color: #e2e8f0; box-shadow: none; }
        .ods-nav-item::before { top: 8px; bottom: 8px; }
        .ods-nav-item:hover, .ods-nav-item:focus { background: #fff; border-color: #a5f3fc; box-shadow: 0 0 0 3px rgba(0,176,200,.08); outline: 0; }
        .ods-nav-item.active { background: #ecfeff; border-color: #67e8f9; box-shadow: 0 0 0 3px rgba(0,176,200,.12); }
        .ods-workspace { padding: 18px 24px 26px; }
        .ods-card, .ods-mini-card, .ods-sales-preview-card, .ods-test-panel { border-color: #e8ebef; border-radius: 18px; box-shadow: 0 4px 8px rgba(15,23,42,.04), 0 16px 32px -18px rgba(15,23,42,.14); }
        .ods-card { padding: 15px; }
        .ods-section-head h2 { color: #11151f; font-size: 17px; letter-spacing: -.025em; font-weight: 850; }
        .ods-section-head p { color: #6b7280; font-size: 12px; font-weight: 600; }
        .ods-quick-explain { margin: 0 0 14px; border: 1px solid #e8ebef; border-radius: 18px; background: #fff; box-shadow: 0 4px 8px rgba(15,23,42,.04), 0 16px 32px -18px rgba(15,23,42,.14); padding: 13px 15px; }
        .ods-quick-explain strong { color: #0f172a; font-size: 12px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
        .ods-quick-explain span { color: #64748b; font-weight: 600; }
        .ods-simple-step, .ods-guidance-grid > div, .ods-sales-question, .ods-test-tile, .ods-derived-grid div, .ods-coverage { border-color: #e8ebef; background: #f7f8fa; box-shadow: inset 0 1px 0 rgba(255,255,255,.7); }
        .ods-simple-step { border-radius: 16px; transition: transform .18s cubic-bezier(.16, 1, .3, 1), border-color .16s ease, background .16s ease; }
        .ods-simple-step:hover, .ods-simple-step:focus { transform: translateY(-1px); background: #fff; border-color: #a5f3fc; outline: 3px solid rgba(0,176,200,.08); }
        .ods-row-card, .ods-rule-group-card, .ods-article-row { border-color: #e8ebef; border-radius: 18px; background: #fff; box-shadow: 0 4px 8px rgba(15,23,42,.04), 0 16px 32px -18px rgba(15,23,42,.14); }
        .ods-row-card::before, .ods-rule-group-head::before { width: 4px; background: #00b0c8; opacity: .72; }
        .ods-question-card:hover, .ods-rule-group-card:hover, .ods-article-row:hover { border-color: #c7d2fe; box-shadow: 0 4px 8px rgba(15,23,42,.04), 0 18px 40px -18px rgba(15,23,42,.18); transform: translateY(-1px); }
        .ods-row-top, .ods-rule-group-head { background: linear-gradient(135deg, #fff 0%, #f8fafc 100%); }
        .ods-row-index, .ods-article-row-index { background: #eef2ff; color: #3730a3; border-radius: 10px; }
        .ods-article-number { background: #0f172a; border-radius: 12px; }
        .ods-question-summary-copy strong, .ods-rule-group-head h3, .ods-article-name strong { color: #0a0e1a; }
        .ods-question-summary-copy small, .ods-rule-group-head p, .ods-article-name small { color: #6b7280; }
        .ods-rule-toggle-indicator, .ods-badge, .ods-token, .ods-picker-chip, .ods-compact-check, .ods-tag { border-color: #e8ebef; }
        .ods-badge { background: #f5f6f8; color: #495061; font-size: 9px; font-weight: 850; letter-spacing: .04em; text-transform: uppercase; }
        .ods-badge.ok-soft { background: #ecfdf5; border-color: #d1fae5; color: #047857; }
        .ods-badge.warn, .ods-badge.preview { background: #fffbeb; border-color: #fde68a; color: #b45309; }
        .ods-badge.danger { background: #fff1f2; border-color: #ffe4e6; color: #be123c; }
        .ods-form-grid { gap: 10px; }
        .ods-field span, .ods-check-field span, .ods-compact-field span, .ods-hierarchy-label { color: #9099a6; font-size: 9px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }
        .ods-field input, .ods-field select, .ods-field textarea, .ods-mini-card select, .ods-assistant select, .ods-compact-field input, .ods-compact-field select, .ods-item-link-host input { min-height: 36px; border-color: #e2e8f0; border-radius: 12px; background: #f8fafc; color: #334155; font-size: 12px; font-weight: 650; }
        .ods-compact-field input, .ods-compact-field select { height: 34px; }
        .ods-field input:focus, .ods-field select:focus, .ods-field textarea:focus, .ods-compact-field input:focus, .ods-compact-field select:focus, .ods-item-link-host input:focus { background: #fff; border-color: #00b0c8; box-shadow: 0 0 0 4px rgba(0,176,200,.1); }
        .ods-sales-preview-card { border-width: 1px; background: #fff; }
        .ods-sales-preview-card::before { content: ""; display: block; height: 4px; margin: -14px -14px 12px; background: linear-gradient(90deg, #00b0c8, #6366f1); border-radius: 18px 18px 0 0; }
        .ods-sales-question { border-width: 1px; }
        .ods-hierarchy-block.when, .ods-hierarchy-block.then, .ods-article-row-qty, .ods-article-picker, .ods-condition-summary, .ods-empty { border-color: #e8ebef; background: #f7f8fa; }
        .ods-condition-summary { background: #ecfeff; border-color: #bae6fd; }
        .ods-group-articles-head strong, .ods-preview-title strong { color: #11151f; }
        .ods-picker-chip { border-radius: 12px; box-shadow: 0 1px 2px rgba(15,23,42,.04); }
        .ods-picker-chip:hover, .ods-picker-chip:focus { background: #eef2ff; border-color: #c7d2fe; color: #3730a3; outline: 3px solid rgba(99,102,241,.12); }
        .ods-article-row { grid-template-columns: minmax(420px, 1.25fr) minmax(210px, .8fr) auto 40px; }
        .ods-generated-row { border-color: #e8ebef; background: #fff; box-shadow: 0 1px 2px rgba(15,23,42,.04); }
        .ods-bottom-bar { border-color: #e8ebef; border-radius: 18px; box-shadow: 0 18px 42px rgba(15,23,42,.12); backdrop-filter: blur(12px); }
        @media (max-width: 1180px) { .ods-nav, .ods-live-panel { position: static; } .ods-nav-title { display: none; } .ods-nav-item { flex: 0 0 150px; white-space: nowrap; } .ods-hero { grid-template-columns: 1fr; } .ods-hero-stats { min-width: 0; } }
        @media (max-width: 760px) { .ods-hero, .ods-workspace, .ods-nav { padding-left: 14px; padding-right: 14px; } .ods-hero-stats, .ods-start-grid, .ods-question-layout, .ods-rule-condition-card, .ods-quantity-controls, .ods-form-grid.two, .ods-form-grid.three, .ods-guidance-grid, .ods-rule-layout, .ods-test-summary, .ods-preview-layout, .ods-article-row, .ods-article-row-title, .ods-article-row-qty, .ods-item-filter-row { grid-template-columns: 1fr; } .ods-sales-preview-card { position: static; } .ods-rule-group-head { align-items: start; grid-template-columns: 34px 1fr; } .ods-rule-group-head .ods-article-status, .ods-rule-toggle-indicator { grid-column: 1 / -1; justify-content: flex-start; } .ods-article-head, .ods-article-card .ods-article-head { align-items: start; grid-template-columns: 1fr; } .ods-article-row-flags { display: flex; flex-wrap: wrap; } .ods-article-status, .ods-article-head .ods-icon-button { grid-column: 1 / -1; justify-content: flex-start; margin-left: 0; } .ods-generated-row { grid-template-columns: 1fr; } .ods-bottom-bar { align-items: stretch; flex-direction: column; gap: 10px; margin-left: 14px; margin-right: 14px; max-width: calc(100% - 28px); } .ods-bottom-actions { display: grid; grid-template-columns: 1fr; } }
    `;
    document.head.appendChild(style);
}
