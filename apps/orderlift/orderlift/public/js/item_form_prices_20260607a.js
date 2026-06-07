(function () {
    if (window.__orderlift_item_form_prices_20260607c_installed) return;
    window.__orderlift_item_form_prices_20260607c_installed = true;

    const API = "orderlift.orderlift_sales.utils.item_price_tools";
    const PRICE_TYPES = {
        buying: { title: () => __("Buying Prices"), section: () => __("Purchasing"), tone: "buying" },
        selling: { title: () => __("Selling Prices"), section: () => __("Sales"), tone: "selling" },
    };

    frappe.ui.form.on("Item", {
        setup(frm) {
            enforceAutoItemCode(frm);
            scheduleItemEnhancements(frm);
        },
        onload(frm) {
            enforceAutoItemCode(frm);
            scheduleItemEnhancements(frm);
        },
        refresh(frm) {
            enforceAutoItemCode(frm);
            scheduleItemEnhancements(frm);
            loadAllPriceGrids(frm);
        },
        item_name(frm) {
            enforceAutoItemCode(frm);
        },
        stock_uom(frm) {
            ["buying", "selling"].forEach((priceType) => {
                const state = priceState(frm, priceType);
                (state.rows || []).forEach((row) => {
                    if (!row.uom) row.uom = frm.doc.stock_uom || "";
                });
                renderPriceCard(frm, priceType);
            });
        },
        custom_item_category(frm) {
            enforceAutoItemCode(frm);
        },
    });

    function enforceAutoItemCode(frm) {
        if (!frm || !frm.fields_dict) return;
        frm.set_df_property("item_code", "read_only", 1);
        frm.set_df_property("item_code", "description", __("Generated from Catégorie article sequence when the Item is saved."));
        if (frm.fields_dict.item_code) {
            frm.fields_dict.item_code.df.read_only = 1;
            if (typeof frm.fields_dict.item_code.refresh === "function") frm.fields_dict.item_code.refresh();
        }
        if (!frm.is_new()) return;

        const itemCode = String(frm.doc.item_code || "").trim();
        const itemName = String(frm.doc.item_name || "").trim();
        if (!itemCode || itemCode === itemName) {
            frm.set_value("item_code", "AUTO");
        }
    }

    function scheduleItemEnhancements(frm) {
        [0, 150, 500, 1200].forEach((delay) => {
            setTimeout(() => {
                applyItemLayout(frm);
                ensurePriceCards(frm);
            }, delay);
        });
    }

    function applyItemLayout(frm) {
        hideItemDefaults(frm);
        moveSpecificationFields(frm);
        moveForeignTradeDetails(frm);
    }

    function hideItemDefaults(frm) {
        ["opening_stock", "standard_rate", "country_of_origin"].forEach((fieldname) => {
            if (frm.fields_dict[fieldname]) frm.set_df_property(fieldname, "hidden", 1);
        });
        if (frm.fields_dict.custom_customs_material) {
            frm.set_df_property("custom_customs_material", "label", __("Douane Material"));
        }
    }

    function moveSpecificationFields(frm) {
        const section = findSpecificationSection(frm);
        const anchor = frm.fields_dict.custom_category_abbreviation || frm.fields_dict.custom_item_category || frm.fields_dict.item_group;
        if (!section || !anchor || !anchor.$wrapper) return;

        const $section = $(section.wrapper || section.$wrapper);
        const $body = getSectionBody(section, $section);
        const $anchor = anchor.$wrapper.closest(".frappe-control");
        if (!$section.length || !$body.length || !$anchor.length) return;

        setSectionTitle($section, "Spécifications");
        $section.attr("data-orderlift-spec-section", "1");
        $body.attr("data-orderlift-spec-body", "1");
        $section.insertAfter($anchor);

        [
            "custom_material",
            "custom_weight_kg",
            "custom_volume_m3",
            "custom_length_cm",
            "custom_width_cm",
            "custom_height_cm",
            "custom_inventory_flag",
            "custom_specifications",
        ].forEach((fieldname) => moveFieldIntoBody(frm, fieldname, $body));

        collapseSpecificationSection(section, $section);
        moveUomAndGuideBelowSpecifications(frm, $section);
    }

    function moveForeignTradeDetails(frm) {
        const section = findForeignTradeSection(frm);
        const anchor = frm.fields_dict.custom_category_abbreviation || frm.fields_dict.custom_item_category || frm.fields_dict.item_group;
        if (!section || !anchor || !anchor.$wrapper) return;

        const $section = $(section.wrapper || section.$wrapper);
        const $body = getSectionBody(section, $section);
        const $anchor = anchor.$wrapper.closest(".frappe-control");
        if (!$section.length || !$body.length || !$anchor.length) return;

        setSectionTitle($section, "Foreign Trade Details");
        $section.attr("data-orderlift-foreign-trade-section", "1");
        $body.attr("data-orderlift-foreign-trade-body", "1");
        $section.insertAfter($anchor);

        moveFieldIntoBody(frm, "customs_tariff_number", $body);
        moveFieldIntoBody(frm, "custom_customs_material", $body);
        hideFieldControl(frm, "country_of_origin");
    }

    function moveUomAndGuideBelowSpecifications(frm, $section) {
        const settingsSection = findSectionByFieldname(frm, "custom_item_settings_section");
        const guideSection = findSectionByFieldname(frm, "custom_item_add_guide_section");
        const stockUom = frm.fields_dict.stock_uom;
        if (!guideSection || !stockUom || !stockUom.$wrapper) return;

        const $guideSection = $(guideSection.wrapper || guideSection.$wrapper);
        const $stockUomControl = stockUom.$wrapper.closest(".frappe-control");
        if (!$guideSection.length || !$stockUomControl.length) return;

        if (settingsSection) {
            const $settingsSection = $(settingsSection.wrapper || settingsSection.$wrapper);
            const $settingsBody = getSectionBody(settingsSection, $settingsSection);
            if ($settingsSection.length && $settingsBody.length) {
                $settingsSection.insertAfter($section);
                $settingsBody.append($stockUomControl);
                $guideSection.insertAfter($settingsSection);
                return;
            }
        }
        $stockUomControl.insertAfter($section);
        $guideSection.insertAfter($stockUomControl);
    }

    function ensurePriceCards(frm) {
        ["buying", "selling"].forEach((priceType) => {
            const $card = ensurePriceCardContainer(frm, priceType);
            if ($card.length) renderPriceCard(frm, priceType);
        });
    }

    function loadAllPriceGrids(frm) {
        if (frm.is_new() || !frm.doc.name) {
            ["buying", "selling"].forEach((priceType) => renderPriceCard(frm, priceType));
            return;
        }
        loadPriceGrid(frm, "buying");
        loadPriceGrid(frm, "selling");
    }

    async function loadPriceGrid(frm, priceType, force) {
        if (frm.is_new() || !frm.doc.name) return;
        const state = priceState(frm, priceType);
        if (state.loading || (state.loaded && !force)) return;
        state.loading = true;
        state.error = "";
        renderPriceCard(frm, priceType);
        try {
            const response = await frappe.call({
                method: `${API}.get_item_price_grid`,
                args: { item_code: frm.doc.name, price_type: priceType },
            });
            Object.assign(state, response.message || {}, { loaded: true });
        } catch (error) {
            console.error(`Orderlift ${priceType} prices failed`, error);
            state.error = __("Unable to load Item Prices.");
        } finally {
            state.loading = false;
            renderPriceCard(frm, priceType);
        }
    }

    async function savePriceGrid(frm, priceType) {
        const state = priceState(frm, priceType);
        syncPriceCard(frm, priceType);
        const response = await frappe.call({
            method: `${API}.save_item_price_grid`,
            args: {
                item_code: frm.doc.name,
                price_type: priceType,
                rows: JSON.stringify(state.rows || []),
            },
            freeze: true,
            freeze_message: __("Saving Item Prices..."),
        });
        const out = response.message || {};
        frappe.show_alert({
            message: __("Item Prices saved. Created: {0}, Updated: {1}, Skipped: {2}", [out.created || 0, out.updated || 0, out.skipped || 0]),
            indicator: "green",
        }, 6);
        state.loaded = false;
        await loadPriceGrid(frm, priceType, true);
    }

    function ensurePriceCardContainer(frm, priceType) {
        if (!frm.layout || !frm.layout.wrapper) return $();
        const selector = `[data-orderlift-item-prices="${priceType}"]`;
        let $card = frm.layout.wrapper.find(selector).first();
        if ($card.length) return $card;

        $card = $(`<div class="orderlift-item-price-card ${PRICE_TYPES[priceType].tone}" data-orderlift-item-prices="${priceType}"></div>`);
        const $anchor = findPriceCardAnchor(frm, priceType);
        if ($anchor.length) $card.insertAfter($anchor);
        else {
            const $fallback = $(frm.layout.wrapper).find(".form-layout").first();
            if (!$fallback.length) return $();
            $fallback.append($card);
        }
        bindPriceCard(frm, priceType, $card);
        return $card;
    }

    function findPriceCardAnchor(frm, priceType) {
        const candidates = priceType === "buying"
            ? ["supplier_items", "last_purchase_rate", "is_purchase_item"]
            : ["max_discount", "is_sales_item"];
        for (const fieldname of candidates) {
            const field = frm.fields_dict[fieldname];
            if (field && field.$wrapper) return field.$wrapper.closest(".frappe-control");
        }
        return $();
    }

    function bindPriceCard(frm, priceType, $card) {
        $card.on("click", "[data-orderlift-add-price]", () => {
            syncPriceCard(frm, priceType);
            const state = priceState(frm, priceType);
            state.rows = state.rows || [];
            state.rows.push({ name: "", price_list: "", price_list_rate: 0, uom: frm.doc.stock_uom || state.stock_uom || "", currency: defaultCurrency(state), enabled: 1 });
            renderPriceCard(frm, priceType);
        });
        $card.on("click", "[data-orderlift-save-prices]", () => savePriceGrid(frm, priceType));
        $card.on("click", "[data-orderlift-refresh-prices]", () => loadPriceGrid(frm, priceType, true));
        $card.on("click", "[data-orderlift-open-price]", function () {
            const name = $(this).attr("data-orderlift-open-price");
            if (name) frappe.set_route("Form", "Item Price", name);
        });
        $card.on("input change", "[data-price-field]", function () {
            const $input = $(this);
            if ($input.attr("data-price-field") === "price_list") {
                const rowIndex = Number($input.closest("tr").attr("data-price-row"));
                const state = priceState(frm, priceType);
                const currency = priceListCurrency(state, $input.val());
                if (currency) {
                    state.rows[rowIndex] = state.rows[rowIndex] || {};
                    state.rows[rowIndex].currency = currency;
                    $input.closest("tr").find('[data-price-field="currency"]').val(currency);
                }
            }
        });
    }

    function renderPriceCard(frm, priceType) {
        const $card = ensurePriceCardContainer(frm, priceType);
        if (!$card.length) return;
        const state = priceState(frm, priceType);
        const title = PRICE_TYPES[priceType].title();
        if (frm.is_new() || !frm.doc.name) {
            $card.html(`<div class="ol-price-head"><div><h3>${esc(title)}</h3><p>${esc(__("Save the Item first to manage prices."))}</p></div></div>`);
            return;
        }

        const rows = state.rows || [];
        const fields = state.fields || {};
        const listId = `ol-${priceType}-price-list-${safeId(frm.doc.name)}`;
        const uomValue = frm.doc.stock_uom || state.stock_uom || "";
        const colCount = 5 + (fields.valid_from ? 1 : 0) + (fields.valid_upto ? 1 : 0) + (fields.brand ? 1 : 0) + (fields.enabled ? 1 : 0) + 1;
        const body = state.loading
            ? `<tr><td colspan="${colCount}" class="ol-price-empty">${esc(__("Loading Item Prices..."))}</td></tr>`
            : rows.length
                ? rows.map((row, index) => priceRowHtml(row, index, fields, listId, uomValue)).join("")
                : `<tr><td colspan="${colCount}" class="ol-price-empty">${esc(__("No Item Prices yet. Add a row to create one."))}</td></tr>`;

        $card.html(`
            <datalist id="${attr(listId)}">${(state.price_lists || []).map((row) => `<option value="${attr(row.name)}"></option>`).join("")}</datalist>
            <div class="ol-price-head">
                <div><h3>${esc(title)}</h3><p>${esc(__("Editable Item Price rows for this Item."))}</p></div>
                <div class="ol-price-actions">
                    <button type="button" class="btn btn-xs btn-default" data-orderlift-refresh-prices>${esc(__("Refresh"))}</button>
                    <button type="button" class="btn btn-xs btn-default" data-orderlift-add-price>${esc(__("Add Row"))}</button>
                    <button type="button" class="btn btn-xs btn-primary" data-orderlift-save-prices>${esc(__("Save Prices"))}</button>
                </div>
            </div>
            ${state.error ? `<div class="ol-price-error">${esc(state.error)}</div>` : ""}
            <div class="ol-price-table-wrap">
                <table class="ol-price-table">
                    <thead><tr>
                        <th>${esc(__("Price List"))}</th>
                        <th>${esc(__("Rate"))}</th>
                        <th>${esc(__("UOM"))}</th>
                        <th>${esc(__("Currency"))}</th>
                        ${fields.valid_from ? `<th>${esc(__("Valid From"))}</th>` : ""}
                        ${fields.valid_upto ? `<th>${esc(__("Valid Upto"))}</th>` : ""}
                        ${fields.brand ? `<th>${esc(__("Brand"))}</th>` : ""}
                        ${fields.enabled ? `<th>${esc(__("Enabled"))}</th>` : ""}
                        <th>${esc(__("Open"))}</th>
                    </tr></thead>
                    <tbody>${body}</tbody>
                </table>
            </div>
        `);
        injectStyles();
    }

    function priceRowHtml(row, index, fields, listId, defaultUom) {
        const uom = row.uom || defaultUom || "";
        return `<tr data-price-row="${index}">
            <td><input data-price-field="price_list" list="${attr(listId)}" value="${attr(row.price_list || "")}" placeholder="${attr(__("Price List"))}"></td>
            <td><input data-price-field="price_list_rate" type="number" step="0.01" value="${attr(row.price_list_rate || 0)}"></td>
            <td><input data-price-field="uom" value="${attr(uom)}"></td>
            <td><input data-price-field="currency" value="${attr(row.currency || "")}"></td>
            ${fields.valid_from ? `<td><input data-price-field="valid_from" type="date" value="${attr(dateValue(row.valid_from))}"></td>` : ""}
            ${fields.valid_upto ? `<td><input data-price-field="valid_upto" type="date" value="${attr(dateValue(row.valid_upto))}"></td>` : ""}
            ${fields.brand ? `<td><input data-price-field="brand" value="${attr(row.brand || "")}"></td>` : ""}
            ${fields.enabled ? `<td class="ol-price-center"><input data-price-field="enabled" type="checkbox" ${row.enabled === 0 ? "" : "checked"}></td>` : ""}
            <td>${row.name ? `<button type="button" class="btn btn-xs btn-default" data-orderlift-open-price="${attr(row.name)}">${esc(__("Open"))}</button>` : `<span class="text-muted">${esc(__("New"))}</span>`}</td>
        </tr>`;
    }

    function syncPriceCard(frm, priceType) {
        const state = priceState(frm, priceType);
        const $card = ensurePriceCardContainer(frm, priceType);
        const rows = [];
        $card.find("tr[data-price-row]").each(function () {
            const index = Number($(this).attr("data-price-row"));
            const current = Object.assign({}, (state.rows || [])[index] || {});
            $(this).find("[data-price-field]").each(function () {
                const fieldname = $(this).attr("data-price-field");
                if (fieldname === "enabled") current[fieldname] = $(this).is(":checked") ? 1 : 0;
                else if (fieldname === "price_list_rate") current[fieldname] = Number($(this).val() || 0);
                else current[fieldname] = String($(this).val() || "").trim();
            });
            if (!current.uom) current.uom = frm.doc.stock_uom || state.stock_uom || "";
            rows.push(current);
        });
        state.rows = rows;
    }

    function priceState(frm, priceType) {
        frm.__orderlift_item_prices = frm.__orderlift_item_prices || {};
        frm.__orderlift_item_prices[priceType] = frm.__orderlift_item_prices[priceType] || { rows: [], price_lists: [], fields: {}, loaded: false, loading: false, error: "" };
        return frm.__orderlift_item_prices[priceType];
    }

    function findSpecificationSection(frm) {
        const sections = (frm.layout && frm.layout.sections) || [];
        return findSectionByFieldname(frm, "custom_specifications_section")
            || sections.find((entry) => entry.df && entry.df.fieldname === "section_break_gjns")
            || sections.find((entry) => entry.df && ["Spécifications", "Specifications"].includes(entry.df.label));
    }

    function findForeignTradeSection(frm) {
        return findSectionByFieldname(frm, "foreign_trade_details")
            || findSectionByLabel(frm, ["Foreign Trade Details", "Détails commerce international"])
            || sectionForField(frm, "customs_tariff_number")
            || sectionForField(frm, "country_of_origin");
    }

    function findSectionByFieldname(frm, fieldname) {
        const sections = (frm.layout && frm.layout.sections) || [];
        return sections.find((entry) => entry.df && entry.df.fieldname === fieldname);
    }

    function findSectionByLabel(frm, labels) {
        const normalized = new Set((labels || []).map((label) => String(label || "").toLowerCase()));
        const sections = (frm.layout && frm.layout.sections) || [];
        return sections.find((entry) => entry.df && normalized.has(String(entry.df.label || "").toLowerCase()));
    }

    function sectionForField(frm, fieldname) {
        const field = frm.fields_dict[fieldname];
        if (!field || !field.$wrapper) return null;
        const sectionEl = field.$wrapper.closest(".form-section").get(0);
        const sections = (frm.layout && frm.layout.sections) || [];
        return sections.find((entry) => entry.wrapper === sectionEl || entry.$wrapper?.get?.(0) === sectionEl) || null;
    }

    function getSectionBody(section, $section) {
        if (section.body) return $(section.body);
        return $section.find(".section-body, .form-section, .section-body-wrapper").first();
    }

    function setSectionTitle($section, label) {
        const $title = $section.find(".section-head, .section-title, .h6, .form-section-heading").first();
        if ($title.length) $title.text(__(label));
    }

    function moveFieldIntoBody(frm, fieldname, $body) {
        const field = frm.fields_dict[fieldname];
        if (!field || !field.$wrapper || !$body.length) return;
        const $control = field.$wrapper.closest(".frappe-control");
        if (!$control.length || $control.closest($body).length) return;
        $body.append($control);
    }

    function hideFieldControl(frm, fieldname) {
        const field = frm.fields_dict[fieldname];
        if (!field || !field.$wrapper) return;
        field.$wrapper.closest(".frappe-control").hide();
    }

    function collapseSpecificationSection(section, $section) {
        if ($section.attr("data-orderlift-spec-collapsed") === "1") return;
        if (typeof section.collapse === "function") section.collapse();
        else {
            $section.find(".section-body, .form-section, .section-body-wrapper").first().hide();
            $section.addClass("collapsed hide-control");
        }
        $section.attr("data-orderlift-spec-collapsed", "1");
    }

    function priceListCurrency(state, priceList) {
        const row = (state.price_lists || []).find((candidate) => candidate.name === priceList);
        return row ? row.currency || "" : "";
    }

    function defaultCurrency(state) {
        return ((state.price_lists || [])[0] || {}).currency || frappe.defaults?.get_default?.("currency") || "";
    }

    function dateValue(value) {
        return String(value || "").split(" ")[0];
    }

    function safeId(value) {
        return String(value || "").replace(/[^a-zA-Z0-9_-]/g, "-");
    }

    function esc(value) {
        return frappe.utils.escape_html(String(value == null ? "" : value));
    }

    function attr(value) {
        return esc(value).replace(/`/g, "&#96;");
    }

    function injectStyles() {
        if (document.getElementById("orderlift-item-form-price-style")) return;
        const style = document.createElement("style");
        style.id = "orderlift-item-form-price-style";
        style.textContent = `
            .orderlift-item-price-card{border:1px solid #dbe3ef;border-radius:10px;background:#fff;margin:14px 0;padding:12px;box-shadow:0 2px 10px rgba(15,23,42,.04)}
            .orderlift-item-price-card.buying{border-left:4px solid #2563eb}.orderlift-item-price-card.selling{border-left:4px solid #16a34a}
            .ol-price-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:10px}.ol-price-head h3{margin:0;font-size:14px;font-weight:700}.ol-price-head p{margin:3px 0 0;color:#64748b;font-size:12px}.ol-price-actions{display:flex;gap:6px;flex-wrap:wrap}.ol-price-table-wrap{overflow:auto;border:1px solid #edf2f7;border-radius:8px}.ol-price-table{width:max-content;min-width:100%;border-collapse:collapse}.ol-price-table th,.ol-price-table td{padding:7px;border-bottom:1px solid #edf2f7;vertical-align:middle;white-space:nowrap}.ol-price-table th{background:#f8fafc;color:#475569;font-size:11px;text-transform:uppercase}.ol-price-table input{height:30px;border:1px solid #cbd5e1;border-radius:6px;padding:0 7px;background:#fff;min-width:110px}.ol-price-table input[data-price-field='price_list']{min-width:210px}.ol-price-table input[data-price-field='price_list_rate']{min-width:110px;text-align:right}.ol-price-table input[type='checkbox']{min-width:16px;width:16px;height:16px}.ol-price-center{text-align:center}.ol-price-empty{color:#64748b;text-align:center;padding:16px!important}.ol-price-error{border:1px solid #fecaca;border-radius:8px;background:#fef2f2;color:#991b1b;padding:8px;margin:0 0 10px}
        `;
        document.head.appendChild(style);
    }
})();
