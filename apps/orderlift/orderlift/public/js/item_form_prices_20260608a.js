(function () {
    if (window.__orderlift_item_form_prices_20260608a_installed) return;
    window.__orderlift_item_form_prices_20260608a_installed = true;

    const PREVIEW_METHOD = "orderlift.orderlift_logistics.utils.item_sequence.preview_next_item_code";
    const STOCK_METHOD = "orderlift.orderlift_sales.utils.item_price_tools.get_item_stock_snapshot";

    frappe.ui.form.on("Item", {
        setup(frm) {
            enforceAutoItemCode(frm);
            setupItemCategoryQuery(frm);
        },
        onload(frm) {
            enforceAutoItemCode(frm);
            setupItemCategoryQuery(frm);
            refreshCompanyStockFields(frm);
        },
        refresh(frm) {
            enforceAutoItemCode(frm);
            setupItemCategoryQuery(frm);
            refreshCompanyStockFields(frm);
        },
        item_name(frm) {
            enforceAutoItemCode(frm);
        },
        item_group(frm) {
            setupItemCategoryQuery(frm);
            clearCategoryIfGroupChanged(frm);
        },
        async custom_item_category(frm) {
            await syncItemGroupFromCategory(frm);
            updateItemCodePreview(frm);
        },
    });

    function setupItemCategoryQuery(frm) {
        if (!frm || !frm.set_query) return;
        frm.set_query("custom_item_category", () => {
            return {
                query: "orderlift.orderlift_logistics.utils.item_sequence.item_category_query",
                filters: { item_group: frm.doc.item_group || "" },
            };
        });
    }

    async function clearCategoryIfGroupChanged(frm) {
        if (!frm || !frm.doc.custom_item_category || !frm.doc.item_group) return;
        try {
            const categoryGroup = await getItemCategoryGroup(frm.doc.custom_item_category);
            if (categoryGroup && categoryGroup !== frm.doc.item_group) {
                await frm.set_value("custom_item_category", "");
                frappe.show_alert({ message: __("Catégorie article cleared because it belongs to another Item Group."), indicator: "orange" });
            }
        } catch (error) {
            console.error("Orderlift item category group validation failed", error);
        }
    }

    async function syncItemGroupFromCategory(frm) {
        if (!frm || !frm.doc.custom_item_category) return;
        try {
            const categoryGroup = await getItemCategoryGroup(frm.doc.custom_item_category);
            if (categoryGroup && frm.doc.item_group !== categoryGroup) {
                await frm.set_value("item_group", categoryGroup);
                setupItemCategoryQuery(frm);
            }
        } catch (error) {
            console.error("Orderlift item category group autofill failed", error);
        }
    }

    async function getItemCategoryGroup(categoryName) {
        categoryName = String(categoryName || "").trim();
        if (!categoryName) return "";
        const response = await frappe.db.get_value("Item Category", categoryName, "item_group");
        return response && response.message && response.message.item_group;
    }

    function quickEntryDialogSetCategoryQuery(dialog) {
        const field = dialog && dialog.fields_dict && dialog.fields_dict.custom_item_category;
        if (!field || !field.df) return;
        const getQuery = () => {
            return {
                query: "orderlift.orderlift_logistics.utils.item_sequence.item_category_query",
                filters: { item_group: String(dialog.get_value("item_group") || "").trim() },
            };
        };
        field.get_query = getQuery;
        field.df.get_query = getQuery;
    }

    async function quickEntrySyncGroupFromCategory(dialog) {
        if (!dialog || !dialog.get_value || !dialog.set_value) return;
        const categoryName = dialog.get_value("custom_item_category");
        if (!categoryName) return;
        const categoryGroup = await getItemCategoryGroup(categoryName);
        const currentGroup = String(dialog.get_value("item_group") || "").trim();
        if (categoryGroup && currentGroup !== categoryGroup) {
            await dialog.set_value("item_group", categoryGroup);
            quickEntryDialogSetCategoryQuery(dialog);
        }
    }

    async function quickEntryClearCategoryIfGroupChanged(dialog) {
        if (!dialog || !dialog.get_value || !dialog.set_value) return;
        const categoryName = dialog.get_value("custom_item_category");
        const itemGroup = String(dialog.get_value("item_group") || "").trim();
        if (!categoryName || !itemGroup) return;
        const categoryGroup = await getItemCategoryGroup(categoryName);
        if (categoryGroup && categoryGroup !== itemGroup) {
            await dialog.set_value("custom_item_category", "");
            frappe.show_alert({ message: __("Catégorie article cleared because it belongs to another Item Group."), indicator: "orange" });
        }
    }

    function wireQuickEntryCategoryControls(dialog) {
        if (!dialog || dialog.__orderlift_item_category_quick_entry_wired) return;
        if (dialog.doctype !== "Item") return;
        const itemGroupField = dialog.fields_dict && dialog.fields_dict.item_group;
        const categoryField = dialog.fields_dict && dialog.fields_dict.custom_item_category;
        if (!itemGroupField || !categoryField) return;
        dialog.__orderlift_item_category_quick_entry_wired = true;

        quickEntryDialogSetCategoryQuery(dialog);

        const originalItemGroupOnchange = itemGroupField.df.onchange;
        itemGroupField.df.onchange = function () {
            if (typeof originalItemGroupOnchange === "function") {
                originalItemGroupOnchange.apply(this, arguments);
            }
            quickEntryDialogSetCategoryQuery(dialog);
            quickEntryClearCategoryIfGroupChanged(dialog);
        };

        const originalCategoryOnchange = categoryField.df.onchange;
        categoryField.df.onchange = function () {
            if (typeof originalCategoryOnchange === "function") {
                originalCategoryOnchange.apply(this, arguments);
            }
            quickEntrySyncGroupFromCategory(dialog);
        };

        if (itemGroupField.$input) {
            itemGroupField.$input.on("change.orderliftItemCategory awesomplete-selectcomplete.orderliftItemCategory", function () {
                setTimeout(() => {
                    quickEntryDialogSetCategoryQuery(dialog);
                    quickEntryClearCategoryIfGroupChanged(dialog);
                }, 0);
            });
        }
        if (categoryField.$input) {
            categoryField.$input.on("change.orderliftItemCategory awesomplete-selectcomplete.orderliftItemCategory", function () {
                setTimeout(() => quickEntrySyncGroupFromCategory(dialog), 0);
            });
        }
    }

    function installQuickEntrySupport(attempts) {
        if (frappe.ui.form && frappe.ui.form.QuickEntryForm) {
            const Base = frappe.ui.form.ItemQuickEntryForm || frappe.ui.form.QuickEntryForm;
            frappe.ui.form.ItemQuickEntryForm = class ItemQuickEntryForm extends Base {
                render_dialog() {
                    super.render_dialog();
                    wireQuickEntryCategoryControls(this.dialog || this);
                }
            };
            return;
        }
        if (attempts <= 0) return;
        setTimeout(() => installQuickEntrySupport(attempts - 1), 100);
    }

    installQuickEntrySupport(50);

    function enforceAutoItemCode(frm) {
        if (!frm || !frm.fields_dict) return;
        frm.set_df_property("item_code", "read_only", 1);
        frm.set_df_property("item_code", "description", __("Generated from Catégorie article sequence when the Item is saved."));
        if (!frm.is_new()) return;

        const itemCode = String(frm.doc.item_code || "").trim();
        const itemName = String(frm.doc.item_name || "").trim();
        if (!itemCode || itemCode === itemName) {
            frm.set_value("item_code", "AUTO");
        }
        updateItemCodePreview(frm);
    }

    async function updateItemCodePreview(frm) {
        if (!frm || !frm.is_new() || !frm.doc.custom_item_category || frm.__orderlift_item_code_previewing) return;
        frm.__orderlift_item_code_previewing = true;
        try {
            const response = await frappe.call({
                method: PREVIEW_METHOD,
                args: { category_name: frm.doc.custom_item_category },
            });
            const itemCode = response.message && response.message.item_code;
            if (itemCode && frm.doc.item_code !== itemCode) {
                await frm.set_value("item_code", itemCode);
            }
        } catch (error) {
            console.error("Orderlift item code preview failed", error);
        } finally {
            frm.__orderlift_item_code_previewing = false;
        }
    }

    async function refreshCompanyStockFields(frm) {
        if (!frm || frm.is_new() || frm.__orderlift_refreshing_stock_fields) return;
        if (!frm.fields_dict.custom_company_warehouse_stock && !frm.fields_dict.custom_company_stock_total) return;
        frm.__orderlift_refreshing_stock_fields = true;
        try {
            const response = await frappe.call({
                method: STOCK_METHOD,
                args: { item_code: frm.doc.name },
            });
            const out = response.message || {};
            setStockTable(frm, out.rows || []);
            setFieldValueSilently(frm, "custom_company_stock_total", out.total || 0);
            setFieldValueSilently(frm, "custom_current_company_stock_qty", out.total || 0);
            refreshField(frm, "custom_company_warehouse_stock");
            refreshField(frm, "custom_company_stock_total");
            refreshField(frm, "custom_current_company_stock_qty");
        } catch (error) {
            console.error("Orderlift Item stock refresh failed", error);
        } finally {
            frm.__orderlift_refreshing_stock_fields = false;
        }
    }

    function setStockTable(frm, rows) {
        if (!frm.fields_dict.custom_company_warehouse_stock) return;
        frm.doc.custom_company_warehouse_stock = (rows || []).map((row, index) => ({
            doctype: "Orderlift Item Warehouse Stock",
            parenttype: "Item",
            parentfield: "custom_company_warehouse_stock",
            parent: frm.doc.name,
            idx: index + 1,
            warehouse: row.warehouse || "",
            actual_qty: row.actual_qty || 0,
        }));
    }

    function setFieldValueSilently(frm, fieldname, value) {
        if (!frm.fields_dict[fieldname]) return;
        frm.doc[fieldname] = value;
    }

    function refreshField(frm, fieldname) {
        if (frm.fields_dict[fieldname] && typeof frm.refresh_field === "function") {
            frm.refresh_field(fieldname);
        }
    }
})();
