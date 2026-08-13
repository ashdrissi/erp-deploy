import json
import unittest
from pathlib import Path

from orderlift.sales.utils.dimensioning import (
    coerce_dimensioning_value,
    evaluate_formula,
    evaluate_structured_condition,
    evaluate_structured_quantity,
    validate_dimensioning_key,
    validate_formula,
    validate_structured_condition,
    validate_structured_quantity,
)
APP_ROOT = Path(__file__).resolve().parents[1]


class TestDimensioning(unittest.TestCase):
    def test_validate_dimensioning_key(self):
        self.assertEqual(validate_dimensioning_key("floors_count"), "floors_count")
        with self.assertRaises(ValueError):
            validate_dimensioning_key("3floors")

    def test_formula_supports_math_and_functions(self):
        variables = {"floors": 5, "doors": 2}
        self.assertEqual(evaluate_formula("3 * floors + max(doors, 1)", variables), 17)

    def test_formula_supports_conditionals(self):
        variables = {"floors": 4, "premium": True}
        self.assertEqual(evaluate_formula("10 if premium and floors > 3 else 0", variables), 10)

    def test_validate_formula_rejects_unknown_names(self):
        with self.assertRaises(ValueError):
            validate_formula("3 * unknown_value", {"floors"})

    def test_formula_helpers_cover_workbook_rules(self):
        variables = {"levels": 4, "motor_brand": "AKİŞ", "lift_type": "VVF"}

        self.assertEqual(evaluate_formula('ifelse(contains("MOTEUR AKİŞ MAX4", motor_brand), levels, 0)', variables), 4)
        self.assertTrue(evaluate_formula('one_of(lift_type, "VVF", "2V")', variables))
        self.assertEqual(evaluate_formula('concat("(", levels)', variables), "(4")
        self.assertEqual(evaluate_formula("int(3.8)", variables), 3)

    def test_formula_helpers_match_builder_helpers(self):
        variables = {"brand": "Akis", "delta": -2.2}

        self.assertEqual(evaluate_formula("lower(brand)", variables), "akis")
        self.assertEqual(evaluate_formula("upper(brand)", variables), "AKIS")
        self.assertEqual(evaluate_formula("ceil(abs(delta))", variables), 3)

    def test_formula_supports_dimensioning_quantity_expression(self):
        variables = {"hauteur_de_la_gaine": 8, "hauteur_cabine": 2.5, "nbr_etage": 4}

        self.assertEqual(evaluate_formula("(hauteur_de_la_gaine + 3) * 4 + 5", variables), 49)
        self.assertEqual(evaluate_formula("(hauteur_cabine * 2 + nbr_etage * 4) * 1.05", variables), 22.05)
        self.assertEqual(evaluate_formula("int((hauteur_cabine * 2 + nbr_etage * 4) * 1.05)", variables), 22)

    def test_formula_supports_dimensioning_condition_expression(self):
        variables = {"nbr_etage": 5, "hauteur_cabine": 2.5}

        self.assertTrue(evaluate_formula("nbr_etage >= 4 and hauteur_cabine > 2", variables))

    def test_coerce_dimensioning_values(self):
        self.assertEqual(coerce_dimensioning_value("Int", "4"), 4)
        self.assertEqual(coerce_dimensioning_value("Float", "4.5"), 4.5)
        self.assertTrue(coerce_dimensioning_value("Check", "true"))
        self.assertEqual(coerce_dimensioning_value("Data", 12), "12")

    def test_structured_condition_manual_value(self):
        rule = {
            "condition_mode": "based",
            "question_key": "levels",
            "operator": ">=",
            "compare_source": "manual",
            "manual_value": "4",
        }

        self.assertTrue(evaluate_structured_condition(rule, {"levels": 5}, {"levels": "Int"}))
        self.assertFalse(evaluate_structured_condition(rule, {"levels": 3}, {"levels": "Int"}))

    def test_structured_condition_question_value(self):
        rule = {
            "condition_mode": "based",
            "question_key": "door_count",
            "operator": "==",
            "compare_source": "question",
            "compare_question_key": "levels",
        }

        self.assertTrue(evaluate_structured_condition(rule, {"door_count": 4, "levels": 4}))
        self.assertFalse(evaluate_structured_condition(rule, {"door_count": 3, "levels": 4}))

    def test_condition_rules_json_multiple_and_rows(self):
        rule = {
            "condition_mode": "based",
            "condition_rules_json": json.dumps(
                {
                    "rows": [
                        {"parameter": "levels", "operator": ">=", "value_source": "integer", "value": "4"},
                        {"join": "and", "parameter": "finish", "operator": "==", "value_source": "text", "value": "INOX"},
                    ]
                }
            ),
        }
        values = {"levels": 5, "finish": "INOX"}
        field_types = {"levels": "Int", "finish": "Data"}

        self.assertTrue(evaluate_structured_condition(rule, values, field_types))
        self.assertFalse(evaluate_structured_condition(rule, {**values, "finish": "EPOXY"}, field_types))
        validate_structured_condition(rule, field_types)

    def test_condition_rules_json_multiple_or_rows(self):
        rule = {
            "condition_mode": "based",
            "condition_rules_json": json.dumps(
                {
                    "rows": [
                        {"parameter": "finish", "operator": "==", "value_source": "text", "value": "INOX"},
                        {"join": "or", "parameter": "finish", "operator": "==", "value_source": "text", "value": "PANORAMIQUE"},
                    ]
                }
            ),
        }

        self.assertTrue(evaluate_structured_condition(rule, {"finish": "PANORAMIQUE"}, {"finish": "Data"}))
        self.assertFalse(evaluate_structured_condition(rule, {"finish": "EPOXY"}, {"finish": "Data"}))

    def test_condition_rules_json_mixed_join_is_left_to_right(self):
        rule = {
            "condition_mode": "based",
            "condition_rules_json": json.dumps(
                {
                    "rows": [
                        {"parameter": "a", "operator": "==", "value_source": "integer", "value": "1"},
                        {"join": "or", "parameter": "b", "operator": "==", "value_source": "integer", "value": "1"},
                        {"join": "and", "parameter": "c", "operator": "==", "value_source": "integer", "value": "1"},
                    ]
                }
            ),
        }
        field_types = {"a": "Int", "b": "Int", "c": "Int"}

        self.assertFalse(evaluate_structured_condition(rule, {"a": 1, "b": 0, "c": 0}, field_types))
        self.assertTrue(evaluate_structured_condition(rule, {"a": 1, "b": 0, "c": 1}, field_types))

    def test_condition_rules_json_typed_values(self):
        integer_rule = {
            "condition_mode": "based",
            "condition_rules_json": json.dumps({"rows": [{"parameter": "levels", "operator": ">", "value_source": "integer", "value": "3"}]}),
        }
        decimal_rule = {
            "condition_mode": "based",
            "condition_rules_json": json.dumps({"rows": [{"parameter": "height", "operator": ">=", "value_source": "decimal", "value": "2.5"}]}),
        }
        check_rule = {
            "condition_mode": "based",
            "condition_rules_json": json.dumps({"rows": [{"parameter": "premium", "operator": "==", "value_source": "check", "value": "1"}]}),
        }

        self.assertTrue(evaluate_structured_condition(integer_rule, {"levels": 4}, {"levels": "Int"}))
        self.assertTrue(evaluate_structured_condition(decimal_rule, {"height": 2.5}, {"height": "Float"}))
        self.assertTrue(evaluate_structured_condition(check_rule, {"premium": True}, {"premium": "Check"}))

    def test_condition_rules_json_text_contains(self):
        rule = {
            "condition_mode": "based",
            "condition_rules_json": json.dumps(
                {"rows": [{"parameter": "finish", "operator": "contains", "value_source": "text", "value": "inox"}]}
            ),
        }

        self.assertTrue(evaluate_structured_condition(rule, {"finish": "INOX BROSSE"}, {"finish": "Data"}))
        self.assertFalse(evaluate_structured_condition(rule, {"finish": "EPOXY"}, {"finish": "Data"}))

    def test_filtered_item_resolution_preserves_repeated_item_fields(self):
        source = (APP_ROOT / "orderlift_sales" / "doctype" / "dimensioning_set" / "dimensioning_set.py").read_text()

        self.assertIn('item_filters = [["Item", "disabled", "=", 0]]', source)
        self.assertIn("item_filters.append(_db_filter_condition(filter_row))", source)
        self.assertNotIn('item_filters[filter_row["field"]] =', source)

    def test_filtered_item_contains_matches_dot_and_comma_decimals(self):
        source = (APP_ROOT / "orderlift_sales" / "doctype" / "dimensioning_set" / "dimensioning_set.py").read_text()

        self.assertIn('value = str(value).replace(".", "_").replace(",", "_")', source)
        self.assertIn('return str(right).replace(",", ".") in str(left).replace(",", ".")', source)

    def test_dimensioning_builder_rule_actions_are_implemented(self):
        script = (APP_ROOT / "orderlift_sales" / "page" / "dimensioning_set_builder" / "dimensioning_set_builder.js").read_text()

        for token in [
            "function duplicateActiveDimensioningSet",
            "function duplicateArticleRule",
            "function deleteArticleRule",
            "function duplicateRuleGroup",
            "function deleteRuleGroup",
            "function resetDimensioningBuilderScroll",
            "resetDimensioningBuilderScroll(page)",
        ]:
            self.assertIn(token, script)

    def test_dimensioning_builder_uses_record_name_in_durable_route(self):
        builder = (APP_ROOT / "orderlift_sales" / "page" / "dimensioning_set_builder" / "dimensioning_set_builder.js").read_text()
        manager = (APP_ROOT / "orderlift_sales" / "page" / "dimensioning_set_manager" / "dimensioning_set_manager.js").read_text()
        form = (APP_ROOT / "orderlift_sales" / "doctype" / "dimensioning_set" / "dimensioning_set.js").read_text()

        for token in [
            "function currentDimensioningSetRouteName()",
            "const routeName = currentDimensioningSetRouteName();",
            "syncDimensioningSetRoute(loadedSet.docname, loadedSet.name);",
            "syncDimensioningSetRoute(getActiveSet().docname, getActiveSet().name);",
            'frappe.set_route("dimensioning-set-builder", label, target)',
        ]:
            self.assertIn(token, builder)
        self.assertIn('frappe.set_route("dimensioning-set-builder", "new")', manager)
        self.assertIn('frappe.set_route("dimensioning-set-builder", displayName, setName)', manager)
        self.assertIn('frappe.set_route("dimensioning-set-builder", frm.doc.set_name || frm.doc.name, frm.doc.name)', form)

    def test_dimensioning_builder_save_uses_write_permission_for_existing_sets(self):
        source = (APP_ROOT / "orderlift_sales" / "doctype" / "dimensioning_set" / "dimensioning_set.py").read_text()

        self.assertIn('if name and frappe.db.exists("Dimensioning Set", name):', source)
        self.assertIn('doc.check_permission("write")', source)
        self.assertIn('frappe.has_permission("Dimensioning Set", "create", throw=True)', source)
        self.assertLess(source.index('doc.check_permission("write")'), source.index('doc.set_name ='))

    def test_dimensioning_use_paths_accept_select_without_configuration_read(self):
        dimensioning_source = (APP_ROOT / "orderlift_sales" / "doctype" / "dimensioning_set" / "dimensioning_set.py").read_text()
        pricing_sheet_source = (APP_ROOT / "orderlift_sales" / "doctype" / "pricing_sheet" / "pricing_sheet.py").read_text()
        reference_access_source = (APP_ROOT / "reference_access.py").read_text()

        self.assertIn('from orderlift.reference_access import get_reference_doc_for_use', dimensioning_source)
        self.assertIn('filters={"is_active": 1}', dimensioning_source)
        self.assertIn('ptype="select"', reference_access_source)
        self.assertIn('frappe.get_list(', reference_access_source)
        self.assertIn('frappe.has_permission("Item", "read", throw=True)', dimensioning_source)
        self.assertIn('get_match_cond("Item")', dimensioning_source)
        self.assertIn('candidates = frappe.get_list(', dimensioning_source)
        self.assertIn('return get_reference_doc_for_use(', pricing_sheet_source)
        self.assertNotIn('doc.check_permission("read")', pricing_sheet_source)
        self.assertIn('frappe.has_permission("Dimensioning Set", "read", throw=True)', dimensioning_source)

    def test_dimensioning_document_tool_hides_mutations_on_read_only_documents(self):
        source = (APP_ROOT / "public" / "js" / "dimensioning_document_tool_20260724d.js").read_text()

        self.assertIn("if (!canEditDocument(frm))", source)
        self.assertIn("frm.is_new() ? permissions.create : permissions.write", source)

    def test_formula_builder_uses_source_neutral_language(self):
        source = (APP_ROOT / "orderlift_sales" / "page" / "dimensioning_set_builder" / "dimensioning_set_builder.js").read_text()

        self.assertNotIn('__("Workbook formulas")', source)
        self.assertNotIn('__("Imported workbook logic")', source)
        self.assertNotIn('__("The Excel formula decides whether each article is added and in what quantity.")', source)
        self.assertIn('__("Custom formula protected")', source)

    def test_rule_group_title_round_trips_into_child_rows(self):
        source = (APP_ROOT / "orderlift_sales" / "doctype" / "dimensioning_set" / "dimensioning_set.py").read_text()

        self.assertIn('"rule_group_title": group.get("rule_group_title") or article.get("rule_group_title") or ""', source)
        self.assertIn('"rule_group_title": getattr(row, "rule_group_title", None) or ""', source)
        schema = json.loads(
            (APP_ROOT / "orderlift_sales" / "doctype" / "dimensioning_set_item_rule" / "dimensioning_set_item_rule.json").read_text()
        )
        self.assertIn("rule_group_title", schema["field_order"])

    def test_missing_dynamic_filter_value_is_not_silently_discarded(self):
        source = (APP_ROOT / "orderlift_sales" / "doctype" / "dimensioning_set" / "dimensioning_set.py").read_text()

        self.assertIn('diagnostic["status"] = "missing_value"', source)
        self.assertIn('missing.append(', source)
        self.assertIn('"missing_filter_values": missing_filter_values', source)

    def test_builder_persists_titles_test_values_and_resolution_counts(self):
        source = (APP_ROOT / "orderlift_sales" / "page" / "dimensioning_set_builder" / "dimensioning_set_builder.js").read_text()

        for token in [
            "data-rule-group-title",
            "rule_group_title: group.title",
            "preview_test_values: ODS_STATE.testValues",
            'generated.filter((row) => !row.missing_item).length',
            "function renderResolutionDetails",
            "data-test-rule-filters",
        ]:
            self.assertIn(token, source)

    def test_raw_and_visual_formula_sync_is_guarded(self):
        source = (APP_ROOT / "orderlift_sales" / "page" / "dimensioning_set_builder" / "dimensioning_set_builder.js").read_text()

        for token in [
            "function conditionFormulaBuilderFromRaw",
            "function quantityFormulaBuilderFromRaw",
            "function formulasEquivalent",
            "data-replace-custom-condition",
            "data-replace-custom-quantity",
            "hasArticleSpecificCondition",
            "Replace this custom condition formula",
            "Replace this custom quantity formula",
        ]:
            self.assertIn(token, source)

    def test_condition_rules_json_parameter_comparison(self):
        rule = {
            "condition_mode": "based",
            "condition_rules_json": json.dumps(
                {
                    "rows": [
                        {
                            "parameter": "door_count",
                            "operator": "==",
                            "value_source": "parameter",
                            "value_parameter": "levels",
                        }
                    ]
                }
            ),
        }

        self.assertTrue(evaluate_structured_condition(rule, {"door_count": 4, "levels": 4}, {"door_count": "Int", "levels": "Int"}))
        self.assertFalse(evaluate_structured_condition(rule, {"door_count": 3, "levels": 4}, {"door_count": "Int", "levels": "Int"}))

    def test_condition_rules_json_rejects_invalid_integer_and_decimal(self):
        integer_rule = {
            "condition_mode": "based",
            "condition_rules_json": json.dumps({"rows": [{"parameter": "levels", "operator": ">", "value_source": "integer", "value": "4.5"}]}),
        }
        decimal_rule = {
            "condition_mode": "based",
            "condition_rules_json": json.dumps({"rows": [{"parameter": "height", "operator": ">", "value_source": "decimal", "value": "abc"}]}),
        }

        with self.assertRaises(ValueError):
            validate_structured_condition(integer_rule, {"levels": "Int"})
        with self.assertRaises(ValueError):
            validate_structured_condition(decimal_rule, {"height": "Float"})

    def test_condition_rules_json_is_ignored_for_always_mode(self):
        rule = {
            "condition_mode": "always",
            "condition_rules_json": json.dumps({"rows": [{"parameter": "levels", "operator": ">", "value_source": "integer", "value": "99"}]}),
        }

        self.assertTrue(evaluate_structured_condition(rule, {"levels": 1}, {"levels": "Int"}))
        validate_structured_condition(rule, {"levels": "Int"})

    def test_structured_quantity_modes(self):
        self.assertEqual(evaluate_structured_quantity({"quantity_mode": "fixed", "fixed_qty": "2"}, {}), 2)
        self.assertEqual(
            evaluate_structured_quantity({"quantity_mode": "question", "quantity_question_key": "levels"}, {"levels": 4}),
            4,
        )

    def test_structured_validation_rejects_text_greater_than(self):
        rule = {
            "condition_mode": "based",
            "question_key": "family",
            "operator": ">",
            "compare_source": "manual",
            "manual_value": "PORTE",
        }

        with self.assertRaises(ValueError):
            validate_structured_condition(rule, {"family": "Select"})

    def test_structured_validation_rejects_text_quantity_question(self):
        with self.assertRaises(ValueError):
            validate_structured_quantity(
                {"quantity_mode": "question", "quantity_question_key": "family"},
                {"family": "Select"},
            )


if __name__ == "__main__":
    unittest.main()
