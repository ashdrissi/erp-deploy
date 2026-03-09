frappe.ui.form.on("Dimensioning Set", {
    refresh(frm) {
        ensureDimensioningSetStyles();
        setupDimensioningGridHints(frm);
        renderDimensioningOverview(frm);
        renderSelectionRuleBuilder(frm);
        renderDimensioningPreview(frm);

        frm.clear_custom_buttons();
        frm.add_custom_button(__("Ajouter un exemple"), () => addDimensioningSamples(frm), __("Aide"));
        frm.add_custom_button(__("Apercu des articles"), () => renderDimensioningPreview(frm, true), __("Aide"));
    },

    set_name: renderDimensioningOverview,
    description: renderDimensioningOverview,
    is_active(frm) {
        renderDimensioningOverview(frm);
        renderSelectionRuleBuilder(frm);
    },
});

frappe.ui.form.on("Dimensioning Set Field", {
    input_fields_add(frm) {
        renderDimensioningOverview(frm);
        renderSelectionRuleBuilder(frm);
        renderDimensioningPreview(frm);
    },
    input_fields_remove(frm) {
        renderDimensioningOverview(frm);
        renderSelectionRuleBuilder(frm);
        renderDimensioningPreview(frm);
    },
    field_key: renderDimensioningPreview,
    label(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        autoFillCharacteristicKey(cdt, cdn, row);
        renderDimensioningOverview(frm);
        renderSelectionRuleBuilder(frm);
        renderDimensioningPreview(frm);
    },
    field_type(frm) {
        renderSelectionRuleBuilder(frm);
        renderDimensioningPreview(frm);
    },
    options: renderDimensioningPreview,
    default_value: renderDimensioningPreview,
    is_required: renderDimensioningPreview,
    help_text: renderDimensioningPreview,
});

frappe.ui.form.on("Dimensioning Set Item Rule", {
    item_rules_add(frm) {
        renderDimensioningOverview(frm);
        renderSelectionRuleBuilder(frm);
        renderDimensioningPreview(frm);
    },
    item_rules_remove(frm) {
        renderDimensioningOverview(frm);
        renderSelectionRuleBuilder(frm);
        renderDimensioningPreview(frm);
    },
    rule_label(frm) {
        renderDimensioningOverview(frm);
        renderSelectionRuleBuilder(frm);
    },
    condition_formula(frm) {
        renderSelectionRuleBuilder(frm);
        renderDimensioningPreview(frm);
    },
    item(frm) {
        renderDimensioningOverview(frm);
        renderSelectionRuleBuilder(frm);
    },
    qty_formula(frm) {
        renderSelectionRuleBuilder(frm);
        renderDimensioningPreview(frm);
    },
    display_group(frm) {
        renderSelectionRuleBuilder(frm);
        renderDimensioningPreview(frm);
    },
    show_in_detail(frm) {
        renderSelectionRuleBuilder(frm);
        renderDimensioningPreview(frm);
    },
    is_active(frm) {
        renderDimensioningOverview(frm);
        renderSelectionRuleBuilder(frm);
    },
});

function setupDimensioningGridHints(frm) {
    const fieldsGrid = frm.get_field("input_fields")?.grid;
    const rulesGrid = frm.get_field("item_rules")?.grid;
    if (fieldsGrid) {
        fieldsGrid.wrapper.addClass("ds-native-grid");
    }
    if (rulesGrid) {
        rulesGrid.wrapper.addClass("ds-native-grid");
        rulesGrid.wrapper.hide();
    }
}

function renderSelectionRuleBuilder(frm) {
    const wrapper = frm.get_field("rule_builder_html")?.$wrapper;
    if (!wrapper) return;

    const hasCharacteristics = (frm.doc.input_fields || []).some((row) => (row.field_key || row.label));
    const blocks = getSelectionRuleBlocks(frm);

    const cards = blocks.length
        ? blocks.map((block) => renderSelectionRuleBlock(block)).join("")
        : `<div class="ds-empty">${__("Aucune regle de selection. Ajoutez une premiere regle pour transformer les caracteristiques en articles." )}</div>`;

    wrapper.html(`
        <div class="ds-section">
            <div class="ds-rule-toolbar">
                <div>
                    <div class="ds-section-title">${__("2. Construire les regles de selection")}</div>
                    <div class="ds-help">${hasCharacteristics ? __("Creez des phrases simples du type 'Quand [caracteristique] ... alors ajouter [article]'.") : __("Commencez par ajouter au moins une caracteristique avant de creer les regles.")}</div>
                </div>
                <div class="ds-rule-actions">
                    <button class="btn btn-default btn-sm" type="button" data-open-advanced-grid>${__("Afficher la grille avancee")}</button>
                    <button class="btn btn-primary btn-sm" type="button" data-add-selection-rule ${hasCharacteristics ? "" : "disabled"}>${__("Ajouter une regle")}</button>
                </div>
            </div>
            <div class="ds-rule-stack">${cards}</div>
        </div>
    `);

    wrapper.find("[data-add-selection-rule]").on("click", () => openSelectionRuleBlockDialog(frm));
    wrapper.find("[data-open-advanced-grid]").on("click", () => {
        const grid = frm.get_field("item_rules")?.grid;
        if (grid) {
            grid.wrapper.toggle();
        }
    });
    wrapper.find("[data-edit-block]").on("click", function () {
        openSelectionRuleBlockDialog(frm, $(this).data("ruleGroup"));
    });
    wrapper.find("[data-add-item]").on("click", function () {
        openSelectionRuleItemDialog(frm, null, $(this).data("ruleGroup"));
    });
    wrapper.find("[data-edit-item]").on("click", function () {
        openSelectionRuleItemDialog(frm, $(this).data("ruleName"));
    });
    wrapper.find("[data-duplicate-block]").on("click", function () {
        duplicateSelectionRuleBlock(frm, $(this).data("ruleGroup"));
    });
    wrapper.find("[data-delete-block]").on("click", function () {
        deleteSelectionRuleBlock(frm, $(this).data("ruleGroup"));
    });
    wrapper.find("[data-delete-item]").on("click", function () {
        deleteSelectionRuleItem(frm, $(this).data("ruleName"));
    });
}

function renderSelectionRuleBlock(block) {
    const ruleLabel = frappe.utils.escape_html(block.rule_label || __("Nouvelle regle"));
    const statusChip = cint(block.is_active) ? __("Active") : __("Inactive");
    const itemRows = block.items.filter((row) => row.item);
    const itemsHtml = itemRows.length ? itemRows.map((row) => `
        <div class="ds-block-item">
            <div>
                <div class="ds-rule-title">${frappe.utils.escape_html(row.item || __("Article non defini"))}</div>
                <div class="ds-rule-meta">${cint(row.show_in_detail) ? __("Affiche en detail") : __("Masque en detail")}</div>
            </div>
            <div class="ds-block-item-formula">${frappe.utils.escape_html(describeQuantityFormula(row))}</div>
            <div class="ds-card-actions">
                <button class="btn btn-default btn-xs" type="button" data-edit-item data-rule-name="${frappe.utils.escape_html(row.name || "")}">${__("Modifier l'article")}</button>
                <button class="btn btn-default btn-xs" type="button" data-delete-item data-rule-name="${frappe.utils.escape_html(row.name || "")}">${__("Supprimer l'article")}</button>
            </div>
        </div>
    `).join("") : `<div class="ds-empty">${__("Aucun article dans ce bloc. Ajoutez un article pour activer cette regle.")}</div>`;

    return `
        <div class="ds-sentence-card ${cint(block.is_active) ? "" : "is-disabled"}">
            <div class="ds-sentence-head">
                <div>
                    <div class="ds-rule-title">${ruleLabel}</div>
                    <div class="ds-rule-meta">${statusChip}</div>
                </div>
                <div class="ds-card-actions">
                    <button class="btn btn-default btn-xs" type="button" data-edit-block data-rule-group="${frappe.utils.escape_html(block.rule_group || "")}">${__("Modifier la regle")}</button>
                    <button class="btn btn-default btn-xs" type="button" data-add-item data-rule-group="${frappe.utils.escape_html(block.rule_group || "")}">${__("Ajouter un article")}</button>
                    <button class="btn btn-default btn-xs" type="button" data-duplicate-block data-rule-group="${frappe.utils.escape_html(block.rule_group || "")}">${__("Dupliquer le bloc")}</button>
                    <button class="btn btn-default btn-xs" type="button" data-delete-block data-rule-group="${frappe.utils.escape_html(block.rule_group || "")}">${__("Supprimer le bloc")}</button>
                </div>
            </div>
            <div class="ds-sentence-body">
                <span class="ds-sentence-pill ds-sentence-pill--soft">${describeConditionPill(block)}</span>
                <span class="ds-sentence-word">${__("alors ajouter les articles suivants")}</span>
            </div>
            <div class="ds-block-items">
                ${itemsHtml}
            </div>
        </div>
    `;
}

function openSelectionRuleBlockDialog(frm, ruleGroup = null) {
    const block = ruleGroup ? getSelectionRuleBlocks(frm).find((entry) => entry.rule_group === ruleGroup) : null;
    const parsed = parseBlockForDialog(block);
    const characteristics = getCharacteristicChoices(frm);
    const characteristicOptions = characteristics.length ? characteristics.join("\n") : "";

    const dialog = new frappe.ui.Dialog({
        title: block ? __("Modifier la regle de selection") : __("Ajouter une regle de selection"),
        fields: [
            { fieldname: "rule_label", fieldtype: "Data", label: __("Libelle de Regle"), reqd: 1, default: parsed.rule_label },
            { fieldname: "is_active", fieldtype: "Check", label: __("Active"), default: parsed.is_active ? 1 : 0 },
            { fieldname: "condition_mode", fieldtype: "Select", label: __("Quand"), options: "Toujours\nCondition simple\nFormule avancee", default: parsed.condition_mode },
            { fieldname: "condition_characteristic", fieldtype: "Select", label: __("Caracteristique"), options: characteristicOptions, default: parsed.condition_characteristic, depends_on: "eval:doc.condition_mode=='Condition simple'" },
            { fieldname: "condition_operator", fieldtype: "Select", label: __("Operateur"), options: ">\n>=\n<\n<=\n==\n!=", default: parsed.condition_operator, depends_on: "eval:doc.condition_mode=='Condition simple'" },
            { fieldname: "condition_value", fieldtype: "Data", label: __("Valeur"), default: parsed.condition_value, depends_on: "eval:doc.condition_mode=='Condition simple'" },
            { fieldname: "condition_formula", fieldtype: "Data", label: __("Condition Avancee"), default: parsed.condition_formula, depends_on: "eval:doc.condition_mode=='Formule avancee'" },
        ],
        primary_action_label: block ? __("Mettre a jour") : __("Continuer"),
        primary_action: (values) => {
            try {
                const resolvedGroup = persistSelectionRuleBlock(frm, block, values);
                dialog.hide();
                frm.refresh_field("item_rules");
                renderDimensioningOverview(frm);
                renderSelectionRuleBuilder(frm);
                renderDimensioningPreview(frm, true);
                if (!block) {
                    openSelectionRuleItemDialog(frm, null, resolvedGroup);
                }
            } catch (e) {
                frappe.msgprint({ title: __("Regle invalide"), message: e.message || __("Impossible de sauvegarder la regle."), indicator: "red" });
            }
        },
    });
    dialog.show();
}

function openSelectionRuleItemDialog(frm, ruleName = null, ruleGroup = null) {
    const rule = ruleName ? (frm.doc.item_rules || []).find((row) => row.name === ruleName) : null;
    const parsed = parseRuleForDialog(rule);
    const characteristics = getCharacteristicChoices(frm);
    const characteristicOptions = characteristics.length ? characteristics.join("\n") : "";
    const resolvedGroup = rule?.rule_group || ruleGroup;
    if (!resolvedGroup) {
        frappe.msgprint({ title: __("Bloc requis"), message: __("Creez d'abord un bloc de regle avant d'ajouter des articles."), indicator: "orange" });
        return;
    }

    const dialog = new frappe.ui.Dialog({
        title: rule ? __("Modifier l'article genere") : __("Ajouter un article genere"),
        fields: [
            { fieldname: "item", fieldtype: "Link", label: __("Article"), options: "Item", reqd: 1, default: parsed.item },
            { fieldname: "quantity_mode", fieldtype: "Select", label: __("Quantite"), options: "Valeur fixe\nMultiplier x caracteristique\nCaracteristique seule\nFormule avancee", default: parsed.quantity_mode },
            { fieldname: "quantity_value", fieldtype: "Float", label: __("Valeur fixe"), default: parsed.quantity_value, depends_on: "eval:doc.quantity_mode=='Valeur fixe'" },
            { fieldname: "quantity_characteristic", fieldtype: "Select", label: __("Caracteristique"), options: characteristicOptions, default: parsed.quantity_characteristic, depends_on: "eval:doc.quantity_mode=='Multiplier x caracteristique' || doc.quantity_mode=='Caracteristique seule'" },
            { fieldname: "quantity_multiplier", fieldtype: "Float", label: __("Multiplicateur"), default: parsed.quantity_multiplier, depends_on: "eval:doc.quantity_mode=='Multiplier x caracteristique'" },
            { fieldname: "qty_formula", fieldtype: "Data", label: __("Formule avancee"), default: parsed.qty_formula, depends_on: "eval:doc.quantity_mode=='Formule avancee'" },
            { fieldname: "display_group", fieldtype: "Data", label: __("Groupe d'Affichage"), default: parsed.display_group },
            { fieldname: "show_in_detail", fieldtype: "Check", label: __("Afficher en Detail"), default: parsed.show_in_detail ? 1 : 0 },
        ],
        primary_action_label: rule ? __("Mettre a jour") : __("Ajouter"),
        primary_action: (values) => {
            try {
                persistSelectionRuleItem(frm, rule, resolvedGroup, values);
                dialog.hide();
                frm.refresh_field("item_rules");
                renderDimensioningOverview(frm);
                renderSelectionRuleBuilder(frm);
                renderDimensioningPreview(frm, true);
            } catch (e) {
                frappe.msgprint({ title: __("Article invalide"), message: e.message || __("Impossible de sauvegarder l'article."), indicator: "red" });
            }
        },
    });
    dialog.show();
}

function buildConditionFormula(values) {
    if (values.condition_mode === "Toujours") {
        return "";
    }
    if (values.condition_mode === "Formule avancee") {
        return (values.condition_formula || "").trim();
    }
    if (!values.condition_characteristic || !values.condition_operator || values.condition_value === undefined || values.condition_value === null || values.condition_value === "") {
        throw new Error(__("Completez la condition simple."));
    }
    const rawValue = String(values.condition_value).trim();
    const normalizedValue = /^-?\d+(\.\d+)?$/.test(rawValue) ? rawValue : JSON.stringify(rawValue);
    return `${values.condition_characteristic} ${values.condition_operator} ${normalizedValue}`;
}

function buildQuantityFormula(values) {
    if (values.quantity_mode === "Valeur fixe") {
        return String(values.quantity_value || 0);
    }
    if (values.quantity_mode === "Caracteristique seule") {
        if (!values.quantity_characteristic) throw new Error(__("Choisissez la caracteristique utilisee pour la quantite."));
        return values.quantity_characteristic;
    }
    if (values.quantity_mode === "Multiplier x caracteristique") {
        if (!values.quantity_characteristic) throw new Error(__("Choisissez la caracteristique utilisee pour la quantite."));
        const multiplier = flt(values.quantity_multiplier || 0);
        return `${multiplier} * ${values.quantity_characteristic}`;
    }
    return (values.qty_formula || "").trim();
}

function parseRuleForDialog(rule) {
    const base = {
        item: rule?.item || "",
        display_group: rule?.display_group || "Dimensionnement",
        show_in_detail: cint(rule?.show_in_detail ?? 1),
        quantity_mode: "Formule avancee",
        quantity_value: 1,
        quantity_characteristic: "",
        quantity_multiplier: 1,
        qty_formula: rule?.qty_formula || "",
    };

    const qty = (rule?.qty_formula || "").trim();
    if (/^-?\d+(\.\d+)?$/.test(qty)) {
        base.quantity_mode = "Valeur fixe";
        base.quantity_value = flt(qty);
    } else {
        const multiplied = qty.match(/^(-?\d+(\.\d+)?)\s*\*\s*([A-Za-z_][A-Za-z0-9_]*)$/);
        const characteristicOnly = qty.match(/^([A-Za-z_][A-Za-z0-9_]*)$/);
        if (multiplied) {
            base.quantity_mode = "Multiplier x caracteristique";
            base.quantity_multiplier = flt(multiplied[1]);
            base.quantity_characteristic = multiplied[3];
        } else if (characteristicOnly) {
            base.quantity_mode = "Caracteristique seule";
            base.quantity_characteristic = characteristicOnly[1];
        }
    }

    return base;
}

function parseBlockForDialog(block) {
    const sample = block?.items?.[0] || null;
    const base = {
        rule_label: block?.rule_label || "",
        is_active: cint(block?.is_active ?? 1),
        condition_mode: "Toujours",
        condition_characteristic: "",
        condition_operator: ">",
        condition_value: "",
        condition_formula: sample?.condition_formula || "",
    };
    const condition = (sample?.condition_formula || "").trim();
    if (condition) {
        const simpleCondition = condition.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*(>=|<=|==|!=|>|<)\s*(.+)$/);
        if (simpleCondition) {
            base.condition_mode = "Condition simple";
            base.condition_characteristic = simpleCondition[1];
            base.condition_operator = simpleCondition[2];
            base.condition_value = simpleCondition[3].replace(/^"|"$/g, "").replace(/^'|'$/g, "");
        } else {
            base.condition_mode = "Formule avancee";
        }
    }
    return base;
}

function getCharacteristicChoices(frm) {
    return (frm.doc.input_fields || [])
        .filter((row) => row.field_key)
        .sort((a, b) => cint(a.sequence || 0) - cint(b.sequence || 0) || cint(a.idx || 0) - cint(b.idx || 0))
        .map((row) => row.field_key);
}

function persistSelectionRuleBlock(frm, existingBlock, values) {
    const ruleGroup = existingBlock?.rule_group || makeRuleGroupId();
    const targets = existingBlock?.items?.length ? existingBlock.items : [frm.add_child("item_rules")];
    targets.forEach((target, index) => {
        target.rule_group = ruleGroup;
        target.rule_label = values.rule_label;
        target.is_active = existingBlock ? (values.is_active ? 1 : 0) : 0;
        target.sequence = cint(target.sequence || ((frm.doc.item_rules || []).length + index) * 10 || 10);
        target.condition_formula = buildConditionFormula(values);
    });
    return ruleGroup;
}

function persistSelectionRuleItem(frm, existingRule, ruleGroup, values) {
    const placeholder = !existingRule ? (frm.doc.item_rules || []).find((row) => row.rule_group === ruleGroup && !row.item) : null;
    const target = existingRule || placeholder || frm.add_child("item_rules");
    const block = getSelectionRuleBlocks(frm).find((entry) => entry.rule_group === ruleGroup);
    target.rule_group = ruleGroup;
    target.rule_label = block?.rule_label || values.rule_label || __("Regle");
    target.is_active = block?.is_active ?? 1;
    target.condition_formula = block?.condition_formula || "";
    target.item = values.item;
    target.display_group = values.display_group || "Dimensionnement";
    target.show_in_detail = values.show_in_detail ? 1 : 0;
    target.sequence = cint(target.sequence || ((frm.doc.item_rules || []).length * 10));
    target.qty_formula = buildQuantityFormula(values);
    if (!target.qty_formula) {
        throw new Error(__("La quantite doit etre definie."));
    }
}

function duplicateSelectionRuleBlock(frm, ruleGroup) {
    const block = getSelectionRuleBlocks(frm).find((entry) => entry.rule_group === ruleGroup);
    if (!block) return;
    const newGroup = makeRuleGroupId();
    block.items.forEach((source, index) => {
        const clone = frm.add_child("item_rules");
        ["sequence", "is_active", "condition_formula", "item", "qty_formula", "display_group", "show_in_detail"].forEach((field) => {
            clone[field] = source[field];
        });
        clone.rule_group = newGroup;
        clone.rule_label = `${block.rule_label || __("Regle")} (${__("copie")})`;
        clone.sequence = cint(source.sequence || ((frm.doc.item_rules || []).length + index) * 10);
    });
    frm.refresh_field("item_rules");
    renderDimensioningOverview(frm);
    renderSelectionRuleBuilder(frm);
    renderDimensioningPreview(frm, true);
}

function deleteSelectionRuleBlock(frm, ruleGroup) {
    const block = getSelectionRuleBlocks(frm).find((entry) => entry.rule_group === ruleGroup);
    if (!block) return;
    frappe.confirm(__("Supprimer ce bloc et tous les articles qu'il genere ?"), () => {
        rewriteItemRules(frm, (frm.doc.item_rules || []).filter((entry) => (entry.rule_group || entry.name) !== ruleGroup));
    });
}

function deleteSelectionRuleItem(frm, ruleName) {
    const row = (frm.doc.item_rules || []).find((entry) => entry.name === ruleName);
    if (!row) return;
    frappe.confirm(__("Supprimer cet article du bloc ?"), () => {
        rewriteItemRules(frm, (frm.doc.item_rules || []).filter((entry) => entry.name !== ruleName));
    });
}

function rewriteItemRules(frm, rows) {
    frm.clear_table("item_rules");
    rows.forEach((entry) => {
        const target = frm.add_child("item_rules");
        ["sequence", "is_active", "rule_group", "rule_label", "condition_formula", "item", "qty_formula", "display_group", "show_in_detail"].forEach((field) => {
            target[field] = entry[field];
        });
    });
    frm.refresh_field("item_rules");
    renderDimensioningOverview(frm);
    renderSelectionRuleBuilder(frm);
    renderDimensioningPreview(frm, true);
}

function describeConditionPill(block) {
    const condition = (block.condition_formula || "").trim();
    return condition ? `${__("Quand")} ${condition}` : __("Toujours");
}

function getSelectionRuleBlocks(frm) {
    const grouped = new Map();
    (frm.doc.item_rules || []).forEach((row) => {
        const key = row.rule_group || row.name;
        if (!grouped.has(key)) {
            grouped.set(key, {
                rule_group: key,
                rule_label: row.rule_label || __("Nouvelle regle"),
                is_active: cint(row.is_active ?? 1),
                condition_formula: row.condition_formula || "",
                items: [],
            });
        }
        grouped.get(key).items.push(row);
    });
    return Array.from(grouped.values()).sort((a, b) => {
        const left = cint(a.items[0]?.sequence || 0);
        const right = cint(b.items[0]?.sequence || 0);
        return left - right;
    });
}

function makeRuleGroupId() {
    return `group_${frappe.utils.get_random(8)}`;
}

function describeQuantityFormula(row) {
    return describeSelectionRule(row);
}

function renderDimensioningOverview(frm) {
    const wrapper = frm.get_field("configurator_overview_html")?.$wrapper;
    if (!wrapper) return;

    const fields = (frm.doc.input_fields || []).filter((row) => row.field_key || row.label);
    const rules = (frm.doc.item_rules || []).filter((row) => row.item);
    const activeRules = rules.filter((row) => cint(row.is_active) === 1);

    const fieldChips = fields.length
        ? fields
              .map((row) => `<span class="ds-chip"><b>${frappe.utils.escape_html(row.label || row.field_key)}</b></span>`)
              .join("")
        : `<span class="ds-empty">${__("Ajoutez des caracteristiques comme nombre de niveaux, nombre de personnes, type de batiment ou largeur de cabine.")}</span>`;

    const rulePreview = activeRules.length
        ? activeRules
              .slice(0, 4)
              .map((row) => `
                <div class="ds-rule-card">
                    <div class="ds-rule-title">${frappe.utils.escape_html(row.rule_label || row.item || __("Regle"))}</div>
                    <div class="ds-rule-meta">${frappe.utils.escape_html(row.item || "-")}</div>
                    <div class="ds-rule-formula">${frappe.utils.escape_html(describeSelectionRule(row))}</div>
                </div>
              `)
              .join("")
        : `<div class="ds-empty">${__("Ajoutez des regles de selection pour transformer les caracteristiques en articles et quantites.")}</div>`;

    wrapper.html(`
        <div class="ds-shell">
            <div class="ds-hero">
                <div>
                    <div class="ds-eyebrow">${__("Outil de dimensionnement")}</div>
                    <h2>${frappe.utils.escape_html(frm.doc.set_name || __("Nouveau set de dimensionnement"))}</h2>
                    <p>${frappe.utils.escape_html(frm.doc.description || __("Definissez les caracteristiques du projet puis les regles qui ajoutent automatiquement les articles correspondants."))}</p>
                </div>
                <div class="ds-stat-grid">
                    <div class="ds-stat-card"><span>${__("Caracteristiques")}</span><strong>${fields.length}</strong></div>
                    <div class="ds-stat-card"><span>${__("Regles actives")}</span><strong>${activeRules.length}</strong></div>
                    <div class="ds-stat-card"><span>${__("Statut")}</span><strong>${cint(frm.doc.is_active) ? __("Actif") : __("Brouillon")}</strong></div>
                </div>
            </div>
            <div class="ds-section">
                <div class="ds-section-title">${__("1. Definir les caracteristiques")}</div>
                <div class="ds-help">${__("Chaque caracteristique represente une information que le commercial remplira sur la fiche tarifaire.")}</div>
                <div class="ds-chip-row">${fieldChips}</div>
            </div>
            <div class="ds-section">
                <div class="ds-section-title">${__("2. Definir les regles de selection")}</div>
                <div class="ds-help">${__("Chaque regle decide quel article ajouter et en quelle quantite. Une condition peut rester vide pour toujours ajouter l'article.")}</div>
                <div class="ds-rule-grid">${rulePreview}</div>
            </div>
            <div class="ds-section ds-section--muted">
                <div class="ds-section-title">${__("Aide Formules")}</div>
                <div class="ds-help-list">
                    <div><b>${__("Calcul")}</b>: <code>3 * niveaux + 2</code></div>
                    <div><b>${__("Condition")}</b>: <code>1 if premium else 0</code></div>
                    <div><b>${__("Fonctions")}</b>: <code>min()</code>, <code>max()</code>, <code>round()</code>, <code>ceil()</code>, <code>floor()</code></div>
                    <div><b>${__("Logique")}</b>: <code>and</code>, <code>or</code>, <code>not</code></div>
                </div>
            </div>
        </div>
    `);
}

function parsePreviewTestValues(frm) {
    try {
        const parsed = JSON.parse(frm.doc.preview_test_values_json || "{}");
        return parsed && typeof parsed === "object" ? parsed : {};
    } catch (e) {
        return {};
    }
}

function normalizePreviewValues(frm) {
    const saved = parsePreviewTestValues(frm);
    const base = buildPreviewSampleValues(frm);
    return { ...base, ...saved };
}

async function renderDimensioningPreview(frm, force = false) {
    const wrapper = frm.get_field("preview_panel_html")?.$wrapper;
    if (!wrapper) return;

    const fields = (frm.doc.input_fields || []).filter((row) => row.field_key);
    if (!frm.doc.name || frm.is_new() || !fields.length) {
        wrapper.html(`<div class="ds-preview-empty">${__("Enregistrez le set et ajoutez au moins une caracteristique pour previsualiser les articles generes.")}</div>`);
        return;
    }

    const sampleValues = normalizePreviewValues(frm);
    frm.doc.preview_test_values_json = JSON.stringify(sampleValues);
    if (!force && !(frm.doc.item_rules || []).length) {
        wrapper.html(`<div class="ds-preview-empty">${__("Ajoutez une ou plusieurs regles de selection pour previsualiser les articles generes.")}</div>`);
        return;
    }

    try {
        const response = await frappe.call({
            method: "orderlift.orderlift_sales.doctype.dimensioning_set.dimensioning_set.preview_dimensioning_set",
            args: {
                set_name: frm.doc.name,
                input_values_json: JSON.stringify(sampleValues),
            },
            freeze: force,
            freeze_message: __("Previewing generated items..."),
        });
        const message = response.message || {};
        const items = message.items || [];
        const values = message.values || sampleValues;
        const sampleHtml = renderPreviewTestInputs(frm, values);
        const rows = items.length
            ? items
                  .map(
                      (row) => `
                        <tr>
                            <td>${frappe.utils.escape_html(row.rule_label || __("Regle sans nom"))}</td>
                            <td>${frappe.utils.escape_html(row.item || "-")}</td>
                            <td>${frappe.format(row.qty || 0, { fieldtype: "Float" })}</td>
                            <td><code>${frappe.utils.escape_html(describeSelectionRule(row))}</code></td>
                        </tr>
                      `
                  )
                  .join("")
            : `<tr><td colspan="4" class="ds-preview-empty-cell">${__("Aucun article n'est genere avec les valeurs d'essai actuelles.")}</td></tr>`;

        wrapper.html(`
            <div class="ds-section">
                <div class="ds-section-title">${__("3. Apercu des articles generes")}</div>
                <div class="ds-help">${__("Modifiez les valeurs de test ci-dessous pour verifier immediatement les articles qui seront generes.")}</div>
                <div class="ds-preview-inputs">${sampleHtml}</div>
                <div class="ds-preview-table-wrap">
                    <table class="ds-preview-table">
                        <thead>
                            <tr>
                                <th>${__("Regle")}</th>
                                <th>${__("Article")}</th>
                                <th>${__("Qty")}</th>
                                <th>${__("Logique")}</th>
                            </tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            </div>
        `);
        bindPreviewTestInputs(frm, sampleValues);
    } catch (e) {
        wrapper.html(`<div class="ds-preview-error">${__("L'apercu a echoue. Verifiez les caracteristiques et les formules des regles.")}</div>`);
    }
}

function renderPreviewTestInputs(frm, values) {
    return (frm.doc.input_fields || []).map((row) => {
        if (!row.field_key) return "";
        const type = (row.field_type || "Float").toLowerCase();
        const value = values[row.field_key];
        let control = "";
        if (type === "select") {
            const options = (row.options || "").split("\n").map((opt) => opt.trim()).filter(Boolean)
                .map((opt) => `<option value="${frappe.utils.escape_html(opt)}" ${String(value ?? "") === opt ? "selected" : ""}>${frappe.utils.escape_html(opt)}</option>`)
                .join("");
            control = `<select class="form-control" data-preview-key="${row.field_key}">${options}</select>`;
        } else if (type === "check") {
            control = `<label class="checkbox"><input type="checkbox" data-preview-key="${row.field_key}" ${value ? "checked" : ""}> <span>${__("Oui")}</span></label>`;
        } else {
            const inputType = type === "int" || type === "float" ? "number" : "text";
            const step = type === "int" ? "1" : "any";
            control = `<input type="${inputType}" step="${step}" class="form-control" data-preview-key="${row.field_key}" value="${frappe.utils.escape_html(String(value ?? ""))}">`;
        }
        return `
            <div class="ds-preview-input-card">
                <label class="control-label">${frappe.utils.escape_html(row.label || row.field_key)}</label>
                ${control}
            </div>
        `;
    }).join("");
}

function bindPreviewTestInputs(frm, currentValues) {
    const wrapper = frm.get_field("preview_panel_html")?.$wrapper;
    if (!wrapper) return;
    wrapper.find("[data-preview-key]").on("change input", () => {
        const values = { ...(currentValues || {}) };
        wrapper.find("[data-preview-key]").each(function () {
            const key = $(this).data("previewKey");
            const row = (frm.doc.input_fields || []).find((entry) => entry.field_key === key);
            const type = (row?.field_type || "Float").toLowerCase();
            if (type === "check") values[key] = $(this).is(":checked");
            else values[key] = $(this).val();
        });
        frm.doc.preview_test_values_json = JSON.stringify(values);
        renderDimensioningPreview(frm, true);
    });
}

function autoFillCharacteristicKey(cdt, cdn, row) {
    if (!row) return;
    const label = (row.label || "").trim();
    if (!label) return;
    const generated = label
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
    if (!generated) return;
    const current = (row.field_key || "").trim();
    if (!current || current === generated || current === current.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "")) {
        frappe.model.set_value(cdt, cdn, "field_key", generated);
    }
}

function describeSelectionRule(row) {
    const condition = (row.condition_formula || "").trim();
    const qtyFormula = (row.qty_formula || "0").trim();
    return condition ? `${condition} -> ${qtyFormula}` : `${__("Toujours")} -> ${qtyFormula}`;
}

function buildPreviewSampleValues(frm) {
    const values = {};
    (frm.doc.input_fields || []).forEach((row) => {
        if (!row.field_key) return;
        const type = (row.field_type || "Float").toLowerCase();
        if (row.default_value !== undefined && row.default_value !== null && String(row.default_value).trim() !== "") {
            if (type === "check") {
                values[row.field_key] = [1, true, "1", "true", "yes", "on"].includes(row.default_value);
            } else if (type === "int") {
                values[row.field_key] = cint(row.default_value || 0);
            } else if (type === "float") {
                values[row.field_key] = flt(row.default_value || 0);
            } else {
                values[row.field_key] = row.default_value;
            }
            return;
        }
        if (type === "check") {
            values[row.field_key] = false;
        } else if (type === "select") {
            values[row.field_key] = (row.options || "").split("\n").map((opt) => opt.trim()).filter(Boolean)[0] || "";
        } else if (type === "data") {
            values[row.field_key] = "sample";
        } else {
            values[row.field_key] = 1;
        }
    });
    return values;
}

function addDimensioningSamples(frm) {
    if ((frm.doc.input_fields || []).length || (frm.doc.item_rules || []).length) {
        frappe.show_alert({ message: __("Les exemples ne s'ajoutent que sur un configurateur vide."), indicator: "orange" });
        return;
    }

    const floors = frm.add_child("input_fields");
    floors.sequence = 10;
    floors.field_key = "floors";
    floors.label = "Nombre de niveaux";
    floors.field_type = "Int";
    floors.default_value = 1;
    floors.is_required = 1;
    floors.help_text = __("Indiquez le nombre de niveaux a desservir.");

    const premium = frm.add_child("input_fields");
    premium.sequence = 20;
    premium.field_key = "premium";
    premium.label = "Projet premium";
    premium.field_type = "Check";
    premium.default_value = 0;

    const ruleA = frm.add_child("item_rules");
    ruleA.sequence = 10;
    ruleA.is_active = 1;
    ruleA.rule_label = "Cable principal par niveau";
    ruleA.item = "";
    ruleA.qty_formula = "3 * floors";
    ruleA.display_group = "Dimensionnement";
    ruleA.show_in_detail = 1;

    const ruleB = frm.add_child("item_rules");
    ruleB.sequence = 20;
    ruleB.is_active = 1;
    ruleB.rule_label = "Controleur premium";
    ruleB.item = "";
    ruleB.condition_formula = "premium";
    ruleB.qty_formula = "1 if premium else 0";
    ruleB.display_group = "Dimensionnement";
    ruleB.show_in_detail = 1;

    frm.refresh_field("input_fields");
    frm.refresh_field("item_rules");
    renderDimensioningOverview(frm);
    renderDimensioningPreview(frm, true);
    frappe.show_alert({ message: __("Exemples ajoutes. Choisissez maintenant les articles cibles."), indicator: "green" });
}

function ensureDimensioningSetStyles() {
    if (document.getElementById("dimensioning-set-styles")) return;
    $("<style id='dimensioning-set-styles'>\
        .ds-shell{display:grid;gap:14px;}\
        .ds-hero{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(280px,.9fr);gap:16px;padding:18px 20px;border-radius:18px;background:linear-gradient(135deg,#f7f4ec 0%,#edf6f1 100%);border:1px solid #d7e4df;}\
        .ds-eyebrow{font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#64748b;margin-bottom:8px;}\
        .ds-hero h2{margin:0 0 8px;font-size:26px;line-height:1.05;color:#102a43;}\
        .ds-hero p{margin:0;color:#486581;max-width:62ch;}\
        .ds-stat-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;}\
        .ds-stat-card{padding:12px 14px;border-radius:14px;background:rgba(255,255,255,.76);border:1px solid rgba(255,255,255,.7);box-shadow:0 10px 28px rgba(16,42,67,.06);}\
        .ds-stat-card span{display:block;font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:#64748b;margin-bottom:6px;}\
        .ds-stat-card strong{display:block;font-size:18px;color:#0f172a;}\
        .ds-section{padding:16px;border-radius:16px;background:#fff;border:1px solid #e2e8f0;}\
        .ds-section--muted{background:#f8fafc;}\
        .ds-section-title{font-weight:700;color:#102a43;margin-bottom:6px;}\
        .ds-help{color:#64748b;font-size:13px;margin-bottom:10px;}\
        .ds-help-list{display:grid;gap:8px;color:#475569;font-size:13px;}\
        .ds-chip-row{display:flex;flex-wrap:wrap;gap:8px;}\
        .ds-chip{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border-radius:999px;background:#eff6ff;border:1px solid #bfdbfe;color:#1d4ed8;font-size:12px;}\
        .ds-rule-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;}\
        .ds-rule-toolbar{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:12px;}\
        .ds-rule-actions,.ds-card-actions{display:flex;gap:8px;flex-wrap:wrap;}\
        .ds-rule-card{padding:12px;border-radius:14px;background:#f8fafc;border:1px solid #e2e8f0;}\
        .ds-rule-title{font-weight:700;color:#102a43;margin-bottom:4px;}\
        .ds-rule-meta{font-size:12px;color:#64748b;margin-bottom:6px;}\
        .ds-rule-formula{font-family:monospace;font-size:12px;color:#0f172a;background:#fff;padding:6px 8px;border-radius:10px;border:1px solid #e2e8f0;}\
        .ds-rule-stack{display:grid;gap:12px;}\
        .ds-sentence-card{padding:14px;border-radius:16px;background:#fff;border:1px solid #e2e8f0;}\
        .ds-sentence-card.is-disabled{opacity:.75;background:#f8fafc;}\
        .ds-sentence-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:12px;}\
        .ds-sentence-body{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:12px;}\
        .ds-sentence-word{font-size:13px;color:#64748b;}\
        .ds-sentence-pill{display:inline-flex;align-items:center;padding:6px 10px;border-radius:999px;background:#eef2ff;border:1px solid #c7d2fe;color:#4338ca;font-size:12px;font-weight:600;}\
        .ds-sentence-pill--soft{background:#f8fafc;border-color:#e2e8f0;color:#475569;}\
        .ds-sentence-pill--formula{font-family:monospace;}\
        .ds-block-items{display:grid;gap:10px;}\
        .ds-block-item{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:12px;align-items:center;padding:12px;border-radius:14px;background:#f8fafc;border:1px solid #e2e8f0;}\
        .ds-block-item-formula{padding:6px 10px;border-radius:10px;background:#fff;border:1px solid #e2e8f0;font-family:monospace;font-size:12px;color:#0f172a;}\
        .ds-empty,.ds-preview-empty,.ds-preview-error{padding:16px;border-radius:14px;background:#f8fafc;border:1px dashed #cbd5e1;color:#64748b;}\
        .ds-preview-error{background:#fff7ed;border-color:#fdba74;color:#9a3412;}\
        .ds-preview-table-wrap{margin-top:12px;overflow:auto;}\
        .ds-preview-table{width:100%;border-collapse:separate;border-spacing:0 8px;}\
        .ds-preview-table th{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:#64748b;text-align:left;padding:0 10px 4px;}\
        .ds-preview-table td{background:#f8fafc;padding:10px;border-top:1px solid #e2e8f0;border-bottom:1px solid #e2e8f0;}\
        .ds-preview-table td:first-child{border-left:1px solid #e2e8f0;border-top-left-radius:12px;border-bottom-left-radius:12px;}\
        .ds-preview-table td:last-child{border-right:1px solid #e2e8f0;border-top-right-radius:12px;border-bottom-right-radius:12px;}\
        .ds-native-grid .grid-heading-row{background:#f8fafc;border-bottom:1px solid #e2e8f0;}\
        .ds-native-grid .grid-static-col{font-weight:600;}\
        @media (max-width:900px){.ds-hero{grid-template-columns:1fr;}.ds-stat-grid{grid-template-columns:1fr;}.ds-rule-toolbar,.ds-sentence-head,.ds-block-item{grid-template-columns:1fr;display:grid;}.ds-sentence-head,.ds-rule-toolbar{display:grid;}}\
    </style>").appendTo(document.head);
}
