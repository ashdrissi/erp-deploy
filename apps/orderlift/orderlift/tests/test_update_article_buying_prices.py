import sys
import types
import unittest


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda value, *args, **kwargs: value
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.throw = lambda message: (_ for _ in ()).throw(ValueError(message))
frappe_stub.only_for = lambda *roles: None
frappe_stub.db = types.SimpleNamespace()
sys.modules["frappe"] = frappe_stub

utils_stub = types.ModuleType("frappe.utils")
utils_stub.cint = lambda value=0: int(float(value or 0))
utils_stub.flt = lambda value=0: float(value or 0)
sys.modules["frappe.utils"] = utils_stub


from orderlift.scripts import rename_article_items_by_category_article, switch_item_group_category, update_article_buying_prices


class TestUpdateArticleBuyingPrices(unittest.TestCase):
    def test_catalog_import_splits_item_material_and_customs_material(self):
        class FakeDoc(dict):
            def get(self, fieldname, default=None):
                return super().get(fieldname, default)

        original_get_doc = getattr(update_article_buying_prices.catalog_import.frappe, "get_doc", None)
        original_ensure_material = update_article_buying_prices.catalog_import._ensure_item_material
        original_ensure_tariff = update_article_buying_prices.catalog_import._ensure_customs_tariff_number
        update_article_buying_prices.catalog_import.frappe.get_doc = lambda values: FakeDoc(values)
        update_article_buying_prices.catalog_import._ensure_item_material = lambda name, summary, caches, dry_run: name
        update_article_buying_prices.catalog_import._ensure_customs_tariff_number = lambda code, summary, caches, dry_run: code
        try:
            doc = update_article_buying_prices.catalog_import._build_item_doc(
                {
                    "ITEM NAME FR": "Nom article FR",
                    "ITEM NAME EN": "Item name EN",
                    "MATERIAL": "INOX",
                    "DOUANE MATERIAL": "ACIER",
                    "HS CODE (10 DIGIT)": "3925900000",
                },
                "ITEM-001",
                "Parts",
                "PC",
                "Category",
                {},
                {},
                dry_run=True,
            )
        finally:
            if original_get_doc:
                update_article_buying_prices.catalog_import.frappe.get_doc = original_get_doc
            else:
                delattr(update_article_buying_prices.catalog_import.frappe, "get_doc")
            update_article_buying_prices.catalog_import._ensure_item_material = original_ensure_material
            update_article_buying_prices.catalog_import._ensure_customs_tariff_number = original_ensure_tariff

        self.assertEqual(doc.get("item_name"), "Nom article FR")
        self.assertEqual(doc.get("custom_item_name_language"), "fr")
        self.assertEqual(doc.get("custom_secondary_item_name"), "Item name EN")
        self.assertEqual(doc.get("custom_secondary_item_name_language"), "en")
        self.assertEqual(doc.get("custom_material"), "INOX")
        self.assertEqual(doc.get("custom_customs_material"), "ACIER")

    def test_supplier_currency_normalization_supports_split_buying_lists(self):
        self.assertEqual(update_article_buying_prices._normalize_supplier_currency("DOLLAR"), "USD")
        self.assertEqual(update_article_buying_prices._normalize_supplier_currency("MAD"), "MAD")
        self.assertEqual(update_article_buying_prices._normalize_supplier_currency("TL"), "TRY")

        self.assertEqual(
            update_article_buying_prices.BUYING_PRICE_LISTS["USD_WEIGHT"]["name"],
            "PRIX FOURNISSEUR USD Weight",
        )
        self.assertEqual(
            update_article_buying_prices.BUYING_PRICE_LISTS["TRY_VOLUME"]["name"],
            "PRIX FOURNISSEUR TRY Volume",
        )
        self.assertIn("PRIX FOURNISSEUR USD", update_article_buying_prices.BUYING_PRICE_LIST_NAMES)
        self.assertIn("PRIX FOURNISSEUR TRY", update_article_buying_prices.BUYING_PRICE_LIST_NAMES)

    def test_supplier_price_route_splits_by_packaging_density(self):
        row = self._row("SRC-001", "Parts", "Dense")
        row.update({"POIDS": "0.355", "VOLUME": "1"})
        price_list, route = update_article_buying_prices._resolve_supplier_buying_price_list("USD", row)
        self.assertEqual(price_list, "PRIX FOURNISSEUR USD Weight")
        self.assertEqual(route["route"], "Weight")

        row.update({"POIDS": "0.354", "VOLUME": "1"})
        price_list, route = update_article_buying_prices._resolve_supplier_buying_price_list("TRY", row)
        self.assertEqual(price_list, "PRIX FOURNISSEUR TRY Volume")
        self.assertEqual(route["route"], "Volume")

    def test_supplier_price_route_uses_value_when_packaging_is_missing(self):
        row = self._row("SRC-001", "Parts", "No Packaging")
        row.update({"POIDS": "10", "VOLUME": "", "VOLUME (L)": ""})

        price_list, route = update_article_buying_prices._resolve_supplier_buying_price_list("USD", row)

        self.assertEqual(price_list, "PRIX FOURNISSEUR USD Value")
        self.assertEqual(route["route"], "Value")

    def test_supplier_price_route_uses_kg_per_liter(self):
        row = self._row("SRC-001", "Parts", "Liters")
        row.update({"POIDS": "0.4", "VOLUME": "", "VOLUME (L)": "1000"})

        price_list, route = update_article_buying_prices._resolve_supplier_buying_price_list("TRY", row)

        self.assertEqual(price_list, "PRIX FOURNISSEUR TRY Volume")
        self.assertEqual(route["route"], "Volume")
        self.assertEqual(str(route["volume_l"]), "1000")

    def test_supplier_price_route_leaves_mad_unchanged(self):
        row = self._row("SRC-001", "Parts", "MAD")
        row.update({"POIDS": "0.1", "VOLUME": "1"})

        price_list, route = update_article_buying_prices._resolve_supplier_buying_price_list("MAD", row)

        self.assertEqual(price_list, "PRIX FOURNISSEUR MAD")
        self.assertEqual(route["route"], "Default")

    def test_price_parser_treats_blank_and_zero_as_no_buying_price(self):
        self.assertEqual(update_article_buying_prices._parse_price(""), (None, "blank"))
        self.assertEqual(update_article_buying_prices._parse_price("0"), (None, "zero"))
        value, reason = update_article_buying_prices._parse_price("1,25")
        self.assertEqual(str(value), "1.25")
        self.assertEqual(reason, "")

    def test_run_supports_separate_original_sheet_name(self):
        reads = []
        original_read = update_article_buying_prices._read_xlsx_rows
        original_load_caches = update_article_buying_prices._load_caches
        original_catalog_load_caches = update_article_buying_prices.catalog_import._load_caches
        original_load_virtual_sequences = update_article_buying_prices.catalog_import._load_virtual_sequences
        original_ensure_buying_price_lists = update_article_buying_prices._ensure_buying_price_lists
        update_article_buying_prices._read_xlsx_rows = lambda path, sheet_name: reads.append((str(path), sheet_name)) or []
        update_article_buying_prices._load_caches = lambda: {
            "price_lists": set(),
            "item_categories": {},
            "item_category_by_abbreviation": {},
        }
        update_article_buying_prices.catalog_import._load_caches = lambda: {}
        update_article_buying_prices.catalog_import._load_virtual_sequences = lambda caches: {}
        update_article_buying_prices._ensure_buying_price_lists = lambda summary, caches, dry_run: None
        try:
            summary = update_article_buying_prices.run(
                workbook_path=__file__,
                original_workbook_path=__file__,
                sheet_name="Sheet1",
                original_sheet_name="Database",
                dry_run=1,
                delete_selling_prices=0,
                delete_stale_buying_prices=0,
                create_new_items=0,
                delete_old_items=0,
            )
        finally:
            update_article_buying_prices._read_xlsx_rows = original_read
            update_article_buying_prices._load_caches = original_load_caches
            update_article_buying_prices.catalog_import._load_caches = original_catalog_load_caches
            update_article_buying_prices.catalog_import._load_virtual_sequences = original_load_virtual_sequences
            update_article_buying_prices._ensure_buying_price_lists = original_ensure_buying_price_lists

        self.assertEqual(reads, [(__file__, "Sheet1"), (__file__, "Database")])
        self.assertEqual(summary["sheet_name"], "Sheet1")
        self.assertEqual(summary["original_sheet_name"], "Database")

    def test_reused_unmatched_item_is_removed_from_old_cleanup_map(self):
        original_map = {
            ("old",): [
                {"item_code": "OLD-00001", "source_item_code": "SRC-OLD"},
                {"item_code": "KEEP-00001", "source_item_code": "SRC-KEEP"},
            ],
            ("other",): [{"item_code": "OLD-00001", "source_item_code": "SRC-DUP"}],
        }

        update_article_buying_prices._remove_original_item_code_from_map(original_map, "OLD-00001")

        remaining_codes = [row["item_code"] for rows in original_map.values() for row in rows]
        self.assertEqual(remaining_codes, ["KEEP-00001"])

    def test_delete_unlisted_buying_prices_only_removes_non_source_rows(self):
        deleted = []
        calls = []
        rows = [
            types.SimpleNamespace(
                name="keep",
                item_code="ITEM-001",
                price_list="PRIX FOURNISSEUR MAD",
                price_list_rate=10,
                supplier="Supplier A",
                get=lambda fieldname, default=None: "Supplier A" if fieldname == "supplier" else default,
            ),
            types.SimpleNamespace(
                name="delete",
                item_code="ITEM-002",
                price_list="PRIX FOURNISSEUR USD Value",
                price_list_rate=20,
                supplier="Supplier B",
                get=lambda fieldname, default=None: "Supplier B" if fieldname == "supplier" else default,
            ),
            types.SimpleNamespace(
                name="legacy",
                item_code="ITEM-003",
                price_list="PRIX FOURNISSEUR USD",
                price_list_rate=30,
                supplier="Supplier C",
                get=lambda fieldname, default=None: "Supplier C" if fieldname == "supplier" else default,
            ),
        ]
        original_get_all = getattr(update_article_buying_prices.frappe, "get_all", None)
        original_delete_doc = getattr(update_article_buying_prices.frappe, "delete_doc", None)
        update_article_buying_prices.frappe.get_all = lambda doctype, **kwargs: calls.append(kwargs) or rows
        update_article_buying_prices.frappe.delete_doc = lambda doctype, name, **kwargs: deleted.append(name)
        summary = {"buying_prices_deleted_unlisted": 0, "unlisted_buying_price_delete_samples": []}
        try:
            update_article_buying_prices._delete_unlisted_buying_prices(
                {("ITEM-001", "PRIX FOURNISSEUR MAD")}, summary, dry_run=False
            )
        finally:
            if original_get_all:
                update_article_buying_prices.frappe.get_all = original_get_all
            else:
                delattr(update_article_buying_prices.frappe, "get_all")
            if original_delete_doc:
                update_article_buying_prices.frappe.delete_doc = original_delete_doc
            else:
                delattr(update_article_buying_prices.frappe, "delete_doc")

        self.assertEqual(deleted, ["delete"])
        self.assertEqual(summary["buying_prices_deleted_unlisted"], 1)
        self.assertIn("PRIX FOURNISSEUR USD Value", calls[0]["filters"]["price_list"][1])
        self.assertNotIn("PRIX FOURNISSEUR USD", calls[0]["filters"]["price_list"][1])

    def test_old_item_cleanup_disables_item_when_delete_is_blocked(self):
        class DbStub:
            def __init__(self):
                self.disabled = []

            def exists(self, doctype, name):
                return doctype == "Item" and name == "OLD-00001"

            def set_value(self, doctype, name, fieldname, value):
                self.disabled.append((doctype, name, fieldname, value))

        db_stub = DbStub()
        original_db = getattr(update_article_buying_prices.frappe, "db", None)
        original_get_all = getattr(update_article_buying_prices.frappe, "get_all", None)
        original_delete_doc = getattr(update_article_buying_prices.frappe, "delete_doc", None)
        update_article_buying_prices.frappe.db = db_stub
        update_article_buying_prices.frappe.get_all = lambda doctype, **kwargs: []
        update_article_buying_prices.frappe.delete_doc = lambda doctype, name, **kwargs: (_ for _ in ()).throw(
            ValueError("blocked")
        )
        summary = {
            "old_items_deleted": 0,
            "old_items_disabled": 0,
            "old_item_prices_deleted": 0,
            "old_item_delete_failures": [],
            "old_item_disable_failures": [],
        }
        try:
            update_article_buying_prices._delete_unmatched_original_items(
                {("old",): [{"item_code": "OLD-00001", "source_item_code": "SRC-OLD"}]},
                summary,
                dry_run=False,
            )
        finally:
            update_article_buying_prices.frappe.db = original_db
            if original_get_all:
                update_article_buying_prices.frappe.get_all = original_get_all
            else:
                delattr(update_article_buying_prices.frappe, "get_all")
            if original_delete_doc:
                update_article_buying_prices.frappe.delete_doc = original_delete_doc
            else:
                delattr(update_article_buying_prices.frappe, "delete_doc")

        self.assertEqual(summary["old_items_disabled"], 1)
        self.assertEqual(summary["old_item_delete_failures"][0]["disabled"], True)
        self.assertEqual(db_stub.disabled, [("Item", "OLD-00001", "disabled", 1)])

    def test_original_mapping_reconstructs_generated_codes_and_matches_exact_rows(self):
        caches = {
            "item_categories": {
                "Door Operators": {"abbreviation": "DOP", "sequence_digits": 5},
                "Motors": {"abbreviation": "MTR", "sequence_digits": 5},
            },
            "item_category_by_abbreviation": {
                "DOP": "Door Operators",
                "MTR": "Motors",
            },
        }
        original_rows = [
            self._row("OPR1", "5. PORTES ET ACCÈS", "Door A", item_group="Door Operators"),
            self._row("OPR2", "5. PORTES ET ACCÈS", "Door B", item_group="Door Operators"),
            self._row("MTR1", "1. GROUPE DE TRACTION (MOTORISATION)", "Motor A", item_group="Motors"),
        ]
        original_map = update_article_buying_prices._build_original_item_map(original_rows, caches)

        matched, unmatched = update_article_buying_prices._match_new_rows(
            [
                self._row("OPR2", "5. PORTES ET ACCÈS", "Door B", item_group="Door Operators"),
                self._row("OPR1", "5. PORTES ET ACCÈS", "Door changed", item_group="Door Operators"),
            ],
            original_map,
        )

        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0][0]["item_code"], "DOP-00002")
        self.assertEqual(len(unmatched), 1)
        self.assertEqual(unmatched[0]["ITEM NAME"], "Door changed")

    def test_original_mapping_uses_workbook_item_group_for_code_prefix(self):
        caches = {
            "item_categories": {
                "1. GROUPE DE TRACTION (MOTORISATION)": {"abbreviation": "GTR", "sequence_digits": 5},
                "Métallerie": {"abbreviation": "MET", "sequence_digits": 5},
            },
            "item_category_by_abbreviation": {
                "GTR": "1. GROUPE DE TRACTION (MOTORISATION)",
                "MET": "Métallerie",
            },
        }

        original_map = update_article_buying_prices._build_original_item_map(
            [self._row("SRC-001", "1. GROUPE DE TRACTION (MOTORISATION)", "Support", item_group="Métallerie")],
            caches,
        )
        mapped = next(iter(original_map.values()))[0]

        self.assertEqual(mapped["item_code"], "MET-00001")
        self.assertEqual(mapped["category"], "Métallerie")

    def test_catalog_import_uses_workbook_item_group_for_new_item_code(self):
        class FakeDoc(dict):
            def insert(self, **kwargs):
                return self

        created_docs = []
        original_get_doc = getattr(update_article_buying_prices.catalog_import.frappe, "get_doc", None)
        original_ensure_material = update_article_buying_prices.catalog_import._ensure_item_material
        update_article_buying_prices.catalog_import.frappe.get_doc = lambda values: created_docs.append(FakeDoc(values)) or created_docs[-1]
        update_article_buying_prices.catalog_import._ensure_item_material = lambda name, summary, caches, dry_run: name
        summary = update_article_buying_prices.catalog_import._new_summary(
            "source.xlsx", "Database", True, 0, 2, True, False, False
        )
        caches = {
            "item_groups": {"1. GROUPE DE TRACTION (MOTORISATION)"},
            "item_group_by_key": {"1 groupe de traction motorisation": "1. GROUPE DE TRACTION (MOTORISATION)"},
            "item_categories": {"Métallerie": {"abbreviation": "MET", "sequence_digits": 5, "current_sequence": 7}},
            "item_category_by_abbreviation": {"MET": "Métallerie"},
            "uoms": {"Pce"},
            "uom_by_key": {"pce": "Pce"},
            "spec_attributes": set(update_article_buying_prices.catalog_import.SPEC_COLUMNS.values()),
            "customs_tariff_numbers": set(),
            "brands": set(),
            "brand_by_key": {},
            "suppliers": set(),
            "supplier_by_key": {},
            "item_materials": set(),
            "item_material_by_key": {},
        }
        row = self._row("SRC-001", "1. GROUPE DE TRACTION (MOTORISATION)", "Support", item_group="Métallerie")
        row["excel_row"] = 2
        try:
            update_article_buying_prices.catalog_import._process_row(
                row,
                summary,
                caches,
                {"Métallerie": 7},
                dry_run=True,
                skip_zero_prices=True,
            )
        finally:
            if original_get_doc:
                update_article_buying_prices.catalog_import.frappe.get_doc = original_get_doc
            else:
                delattr(update_article_buying_prices.catalog_import.frappe, "get_doc")
            update_article_buying_prices.catalog_import._ensure_item_material = original_ensure_material

        self.assertEqual(summary["generated_item_code_samples"][0]["item_code"], "MET-00008")
        self.assertEqual(created_docs[0]["item_code"], "MET-00008")
        self.assertEqual(created_docs[0]["item_group"], "1. GROUPE DE TRACTION (MOTORISATION)")
        self.assertEqual(created_docs[0]["custom_item_category"], "Métallerie")

    def test_unmatched_rows_can_match_unique_existing_source_code(self):
        caches = {
            "item_categories": {"Door Operators": {"abbreviation": "DOP", "sequence_digits": 5}},
            "item_category_by_abbreviation": {"DOP": "Door Operators"},
        }
        original_map = update_article_buying_prices._build_original_item_map(
            [self._row("OPR1", "5. PORTES ET ACCÈS", "Door A", item_group="Door Operators")],
            caches,
        )

        source_matched, unmatched = update_article_buying_prices._match_unmatched_by_unique_source_code(
            [self._row("OPR1", "5. PORTES ET ACCÈS", "Door A with new detail", item_group="Door Operators")],
            original_map,
        )

        self.assertEqual(len(source_matched), 1)
        self.assertEqual(source_matched[0][0]["item_code"], "DOP-00001")
        self.assertEqual(unmatched, [])
        self.assertEqual(sum(len(rows) for rows in original_map.values()), 0)

    def test_unmatched_rows_can_match_unique_loose_identity_when_uom_changes(self):
        caches = {
            "item_categories": {"Cable Trays": {"abbreviation": "CBT", "sequence_digits": 5}},
            "item_category_by_abbreviation": {"CBT": "Cable Trays"},
        }
        original_map = update_article_buying_prices._build_original_item_map(
            [
                self._row(
                    "CBL30",
                    "6. ÉLECTRICITÉ ET ÉLECTRONIQUE (CONTRÔLE)",
                    "GOULOTTE DE CÂBLES 40×40 MM (2 M)",
                    uom="PC",
                    item_group="Cable Trays",
                )
            ],
            caches,
        )

        matched, unmatched = update_article_buying_prices._match_unmatched_by_unique_loose_identity(
            [
                self._row(
                    "CBE31",
                    "6. ÉLECTRICITÉ ET ÉLECTRONIQUE (CONTRÔLE)",
                    "GOULOTTE DE CÂBLES 40×40 MM (2 M)",
                    uom="M",
                    item_group="Cable Trays",
                )
            ],
            original_map,
        )

        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0][0]["item_code"], "CBT-00001")
        self.assertEqual(unmatched, [])
        self.assertEqual(sum(len(rows) for rows in original_map.values()), 0)

    def test_preserves_local_image_unless_image_update_requested(self):
        existing_doc = types.SimpleNamespace(get=lambda field: "/files/ELEC-00044.png" if field == "image" else "")
        source_doc = types.SimpleNamespace(
            values={"image": "https://drive.google.com/thumbnail?id=abc123&sz=w1000"},
            get=lambda field: source_doc.values.get(field),
            set=lambda field, value: source_doc.values.update({field: value}),
        )
        summary = {"images_preserved": 0}

        update_article_buying_prices._preserve_existing_local_image(existing_doc, source_doc, summary, update_images=False)

        self.assertEqual(source_doc.values["image"], "/files/ELEC-00044.png")
        self.assertEqual(summary["images_preserved"], 1)

    def test_existing_item_lookup_uses_switched_group_category_storage(self):
        calls = {}
        original_get_all = getattr(update_article_buying_prices.frappe, "get_all", None)
        def fake_get_all(doctype, **kwargs):
            calls[doctype] = kwargs
            return [types.SimpleNamespace(name="POR-00677", stock_uom="Pce")]

        update_article_buying_prices.frappe.get_all = fake_get_all
        caches = {
            "item_categories": {"Parts": {"abbreviation": "PART", "sequence_digits": 5}},
            "item_category_by_abbreviation": {"PART": "Parts"},
        }
        try:
            result = update_article_buying_prices._find_existing_item_for_new_row(
                self._row("POR-00677", "Porte", "Operateur", item_group="Parts"),
                caches,
            )
        finally:
            if original_get_all:
                update_article_buying_prices.frappe.get_all = original_get_all
            else:
                delattr(update_article_buying_prices.frappe, "get_all")

        self.assertEqual(result["item_code"], "POR-00677")
        filters = calls["Item"]["filters"]
        self.assertEqual(filters["item_group"], "Porte")
        self.assertEqual(filters["custom_item_category"], "Parts")

    def test_switch_script_preserves_item_code_and_swaps_values(self):
        class DbStub:
            def __init__(self):
                self.updated = {}

            def has_column(self, doctype, fieldname):
                return doctype == "Item" and fieldname == "custom_item_category"

            def sql(self, query, params=None, as_dict=False, pluck=False):
                if "FROM `tabItem`" in query and "item_group" in query and as_dict:
                    return [
                        {
                            "name": "POR-00677",
                            "item_group": "OPÉRATEURS ET MÉCANISMES DE PORTE",
                            "custom_item_category": "Porte",
                        }
                    ]
                if pluck:
                    return []
                return []

            def set_value(self, doctype, name, values, **kwargs):
                self.updated[(doctype, name)] = values

            def commit(self):
                pass

        class FakeDoc(types.SimpleNamespace):
            def insert(self, **kwargs):
                return self

        db_stub = DbStub()
        original_db = getattr(switch_item_group_category.frappe, "db", None)
        original_get_all = getattr(switch_item_group_category.frappe, "get_all", None)
        original_get_doc = getattr(switch_item_group_category.frappe, "get_doc", None)
        original_new_doc = getattr(switch_item_group_category.frappe, "new_doc", None)
        switch_item_group_category.frappe.db = db_stub
        switch_item_group_category.frappe.get_all = lambda doctype, **kwargs: _switch_get_all(doctype)
        switch_item_group_category.frappe.get_doc = lambda values: FakeDoc(**values)
        switch_item_group_category.frappe.new_doc = lambda doctype: FakeDoc(doctype=doctype)
        try:
            summary = switch_item_group_category.run(dry_run=0)
        finally:
            switch_item_group_category.frappe.db = original_db
            if original_get_all:
                switch_item_group_category.frappe.get_all = original_get_all
            else:
                delattr(switch_item_group_category.frappe, "get_all")
            if original_get_doc:
                switch_item_group_category.frappe.get_doc = original_get_doc
            else:
                delattr(switch_item_group_category.frappe, "get_doc")
            if original_new_doc:
                switch_item_group_category.frappe.new_doc = original_new_doc
            else:
                delattr(switch_item_group_category.frappe, "new_doc")

        self.assertEqual(summary["items_updated"], 1)
        updated = db_stub.updated[("Item", "POR-00677")]
        self.assertEqual(updated["item_group"], "Porte")
        self.assertEqual(updated["custom_item_category"], "OPÉRATEURS ET MÉCANISMES DE PORTE")

    def test_switch_script_skips_items_already_matching_code_prefix_group(self):
        class DbStub:
            def __init__(self):
                self.updated = {}

            def has_column(self, doctype, fieldname):
                return doctype == "Item" and fieldname == "custom_item_category"

            def sql(self, query, params=None, as_dict=False, pluck=False):
                if "FROM `tabItem`" in query and as_dict:
                    return [{"name": "POR-00677", "item_group": "Porte", "custom_item_category": "OPÉRATEURS ET MÉCANISMES DE PORTE"}]
                return []

            def set_value(self, doctype, name, values, **kwargs):
                self.updated[(doctype, name)] = values

            def commit(self):
                pass

        db_stub = DbStub()
        original_db = getattr(switch_item_group_category.frappe, "db", None)
        original_get_all = getattr(switch_item_group_category.frappe, "get_all", None)
        switch_item_group_category.frappe.db = db_stub
        switch_item_group_category.frappe.get_all = lambda doctype, **kwargs: _switch_get_all(doctype)
        try:
            summary = switch_item_group_category.run(dry_run=0)
        finally:
            switch_item_group_category.frappe.db = original_db
            if original_get_all:
                switch_item_group_category.frappe.get_all = original_get_all
            else:
                delattr(switch_item_group_category.frappe, "get_all")

        self.assertEqual(summary["items_to_update"], 0)
        self.assertEqual(db_stub.updated, {})

    def test_rename_script_supports_start_row_and_limit_for_controlled_batches(self):
        rows = [
            self._row("SRC-001", "ERP Group", "First", item_group="Category A"),
            self._row("SRC-002", "ERP Group", "Second", item_group="Category A"),
            self._row("SRC-003", "ERP Group", "Third", item_group="Category A"),
        ]
        for index, row in enumerate(rows, start=2):
            row["excel_row"] = index

        seen_rows = []
        db_stub = types.SimpleNamespace(exists=lambda doctype, name: None)
        original_read = rename_article_items_by_category_article.article_update._read_xlsx_rows
        original_load_caches = rename_article_items_by_category_article.article_update._load_caches
        original_find = rename_article_items_by_category_article._find_live_item_for_row
        original_db = getattr(rename_article_items_by_category_article.frappe, "db", None)
        rename_article_items_by_category_article.article_update._read_xlsx_rows = lambda path, sheet_name: rows
        rename_article_items_by_category_article.article_update._load_caches = lambda: {
            "item_categories": {"Category A": {"abbreviation": "CTA", "sequence_digits": 5}},
            "item_category_by_abbreviation": {"CTA": "Category A"},
        }
        rename_article_items_by_category_article._find_live_item_for_row = (
            lambda row, summary, caches, consumed_items: seen_rows.append(row["excel_row"]) or f"OLD-{row['excel_row']}"
        )
        rename_article_items_by_category_article.frappe.db = db_stub
        try:
            summary = rename_article_items_by_category_article.run(
                workbook_path=__file__, dry_run=1, start_row=3, limit=1
            )
        finally:
            rename_article_items_by_category_article.article_update._read_xlsx_rows = original_read
            rename_article_items_by_category_article.article_update._load_caches = original_load_caches
            rename_article_items_by_category_article._find_live_item_for_row = original_find
            rename_article_items_by_category_article.frappe.db = original_db

        self.assertEqual(summary["start_row"], 3)
        self.assertEqual(summary["limit"], 1)
        self.assertEqual(summary["rows_total"], 3)
        self.assertEqual(summary["rows_read"], 1)
        self.assertEqual(summary["last_selected_excel_row"], 3)
        self.assertEqual(seen_rows, [3])
        self.assertEqual(summary["renames"][0]["new_item_code"], "CTA-00002")

    def test_rename_script_allows_targets_freed_by_earlier_planned_sources(self):
        rows = [
            self._row("SRC-001", "ERP Group", "First", item_group="Category A"),
            self._row("SRC-002", "ERP Group", "Second", item_group="Category A"),
        ]
        for index, row in enumerate(rows, start=2):
            row["excel_row"] = index

        source_by_code = {"SRC-001": "AEC-00002", "SRC-002": "CAB-00050"}
        original_read = rename_article_items_by_category_article.article_update._read_xlsx_rows
        original_load_caches = rename_article_items_by_category_article.article_update._load_caches
        original_find = rename_article_items_by_category_article._find_live_item_for_row
        original_db = getattr(rename_article_items_by_category_article.frappe, "db", None)
        rename_article_items_by_category_article.article_update._read_xlsx_rows = lambda path, sheet_name: rows
        rename_article_items_by_category_article.article_update._load_caches = lambda: {
            "item_categories": {"Category A": {"abbreviation": "AEC", "sequence_digits": 5}},
            "item_category_by_abbreviation": {"AEC": "Category A"},
        }
        rename_article_items_by_category_article._find_live_item_for_row = (
            lambda row, summary, caches, consumed_items: source_by_code[row["ITEM CODE"]]
        )
        rename_article_items_by_category_article.frappe.db = types.SimpleNamespace(
            exists=lambda doctype, name: "AEC-00002" if name == "AEC-00002" else None
        )
        try:
            summary = rename_article_items_by_category_article.run(workbook_path=__file__, dry_run=1)
        finally:
            rename_article_items_by_category_article.article_update._read_xlsx_rows = original_read
            rename_article_items_by_category_article.article_update._load_caches = original_load_caches
            rename_article_items_by_category_article._find_live_item_for_row = original_find
            rename_article_items_by_category_article.frappe.db = original_db

        self.assertEqual(summary["target_conflicts"], [])
        self.assertEqual(summary["items_to_rename"], 2)
        self.assertEqual(
            [(row["old_item_code"], row["new_item_code"]) for row in summary["renames"]],
            [("AEC-00002", "AEC-00001"), ("CAB-00050", "AEC-00002")],
        )

    def test_rename_script_temp_phase_allows_targets_freed_by_later_sources(self):
        rows = [
            self._row("SRC-001", "ERP Group", "First", item_group="Category A"),
            self._row("SRC-002", "ERP Group", "Second", item_group="Category A"),
        ]
        for index, row in enumerate(rows, start=2):
            row["excel_row"] = index

        source_by_code = {"SRC-001": "OLD-A", "SRC-002": "CTA-00001"}
        original_read = rename_article_items_by_category_article.article_update._read_xlsx_rows
        original_load_caches = rename_article_items_by_category_article.article_update._load_caches
        original_find = rename_article_items_by_category_article._find_live_item_for_row
        original_db = getattr(rename_article_items_by_category_article.frappe, "db", None)
        rename_article_items_by_category_article.article_update._read_xlsx_rows = lambda path, sheet_name: rows
        rename_article_items_by_category_article.article_update._load_caches = lambda: {
            "item_categories": {"Category A": {"abbreviation": "CTA", "sequence_digits": 5}},
            "item_category_by_abbreviation": {"CTA": "Category A"},
        }
        rename_article_items_by_category_article._find_live_item_for_row = (
            lambda row, summary, caches, consumed_items: source_by_code[row["ITEM CODE"]]
        )
        rename_article_items_by_category_article.frappe.db = types.SimpleNamespace(
            exists=lambda doctype, name: "CTA-00001" if name == "CTA-00001" else None
        )
        try:
            summary = rename_article_items_by_category_article.run(
                workbook_path=__file__, dry_run=1, use_temp_phase=1
            )
        finally:
            rename_article_items_by_category_article.article_update._read_xlsx_rows = original_read
            rename_article_items_by_category_article.article_update._load_caches = original_load_caches
            rename_article_items_by_category_article._find_live_item_for_row = original_find
            rename_article_items_by_category_article.frappe.db = original_db

        self.assertEqual(summary["target_conflicts"], [])
        self.assertEqual(summary["items_to_rename"], 2)
        self.assertEqual(
            [(row["old_item_code"], row["new_item_code"]) for row in summary["renames"]],
            [("OLD-A", "CTA-00001"), ("CTA-00001", "CTA-00002")],
        )

    def test_rename_script_temp_phase_applies_all_temporary_renames_before_final_names(self):
        rows = [
            self._row("SRC-001", "ERP Group", "First", item_group="Category A"),
            self._row("SRC-002", "ERP Group", "Second", item_group="Category A"),
        ]
        for index, row in enumerate(rows, start=2):
            row["excel_row"] = index

        source_by_code = {"SRC-001": "OLD-A", "SRC-002": "CTA-00001"}
        rename_calls = []
        original_read = rename_article_items_by_category_article.article_update._read_xlsx_rows
        original_load_caches = rename_article_items_by_category_article.article_update._load_caches
        original_find = rename_article_items_by_category_article._find_live_item_for_row
        original_db = getattr(rename_article_items_by_category_article.frappe, "db", None)
        original_rename_doc = getattr(rename_article_items_by_category_article.frappe, "rename_doc", None)
        rename_article_items_by_category_article.article_update._read_xlsx_rows = lambda path, sheet_name: rows
        rename_article_items_by_category_article.article_update._load_caches = lambda: {
            "item_categories": {"Category A": {"abbreviation": "CTA", "sequence_digits": 5}},
            "item_category_by_abbreviation": {"CTA": "Category A"},
        }
        rename_article_items_by_category_article._find_live_item_for_row = (
            lambda row, summary, caches, consumed_items: source_by_code[row["ITEM CODE"]]
        )
        rename_article_items_by_category_article.frappe.db = types.SimpleNamespace(
            exists=lambda doctype, name: "CTA-00001" if name == "CTA-00001" else None,
            commit=lambda: None,
            rollback=lambda: None,
            get_value=lambda *args, **kwargs: 0,
            set_value=lambda *args, **kwargs: None,
        )
        rename_article_items_by_category_article.frappe.rename_doc = (
            lambda doctype, old, new, **kwargs: rename_calls.append((old, new)) or new
        )
        try:
            summary = rename_article_items_by_category_article.run(
                workbook_path=__file__,
                dry_run=0,
                confirm=rename_article_items_by_category_article.CONFIRM_TOKEN,
                use_temp_phase=1,
            )
        finally:
            rename_article_items_by_category_article.article_update._read_xlsx_rows = original_read
            rename_article_items_by_category_article.article_update._load_caches = original_load_caches
            rename_article_items_by_category_article._find_live_item_for_row = original_find
            rename_article_items_by_category_article.frappe.db = original_db
            if original_rename_doc:
                rename_article_items_by_category_article.frappe.rename_doc = original_rename_doc
            else:
                delattr(rename_article_items_by_category_article.frappe, "rename_doc")

        self.assertEqual(summary["items_temp_renamed"], 2)
        self.assertEqual(summary["items_renamed"], 2)
        self.assertEqual(rename_calls[0][0], "OLD-A")
        self.assertEqual(rename_calls[1][0], "CTA-00001")
        self.assertTrue(rename_calls[0][1].startswith("TMPREN-"))
        self.assertTrue(rename_calls[1][1].startswith("TMPREN-"))
        self.assertEqual(rename_calls[2], (rename_calls[0][1], "CTA-00001"))
        self.assertEqual(rename_calls[3], (rename_calls[1][1], "CTA-00002"))

    def _row(self, source_code, category, item_name, uom="Pce", item_group="Parts"):
        row = {
            "ITEM CODE": source_code,
            "ITEM CATEGORY": category,
            "ITEM GROUP": item_group,
            "ITEM NAME": item_name,
            "DEFAULT UNIT OF MEASURE": uom,
        }
        for column in update_article_buying_prices.SPEC_COLUMNS:
            row[column] = ""
        return row


def _switch_get_all(doctype):
    if doctype == "Item Group":
        return ["All Item Groups", "Porte"]
    if doctype == "Item Category":
        return [
            types.SimpleNamespace(name="Porte", abbreviation="POR", sequence_digits=5, current_sequence=677),
            types.SimpleNamespace(name="OPÉRATEURS ET MÉCANISMES DE PORTE", abbreviation="OEMD", sequence_digits=5, current_sequence=0),
        ]
    return []


if __name__ == "__main__":
    unittest.main()
