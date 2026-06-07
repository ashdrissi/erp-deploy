from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from zipfile import ZipFile
from xml.etree import ElementTree as ET

try:
    import frappe
except ModuleNotFoundError:  # Allows local workbook parsing without a bench Python environment.
    frappe = None


DEFAULT_SET_NAME = "Ascenseur Complet Excel V01.2026"
DEFAULT_WORKBOOK_PATH = "/tmp/Pricing & Edition Devis_V01.2026 (1).xlsm"
SHEET_NAME = "Pricelist"
ROW_START = 11
ROW_END = 311

NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
CELL_RE = re.compile(r"(\$?)([A-Z]{1,3})(\$?)(\d+)")

INPUT_CELLS = {
    "E2": "pricing_profile",
    "F2": "lift_type",
    "G2": "persons",
    "H2": "levels",
    "I2": "motor_brand",
    "J2": "door_brand",
    "K2": "door_material",
    "L2": "door_type",
    "M2": "door_dimension",
    "O2": "tactile_button",
    "P2": "external_structure_set",
}
FIELD_ORDER = list(INPUT_CELLS)
INT_CELLS = {"G2", "H2"}
PRICE_LIST_COLUMNS = {
    "price_min": "Morocco Min",
    "price_normal": "Morocco Normal",
    "price_stock": "Morocco With Stock",
}


def _q(name: str) -> str:
    return f"{{{NS['m']}}}{name}"


def _col_to_num(col: str) -> int:
    number = 0
    for char in col:
        number = number * 26 + ord(char) - 64
    return number


def _num_to_col(number: int) -> str:
    col = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        col = chr(65 + remainder) + col
    return col


def _split_ref(ref: str) -> tuple[int, int]:
    match = re.match(r"([A-Z]+)(\d+)$", ref.replace("$", ""))
    if not match:
        raise ValueError(f"Invalid cell reference {ref}")
    return _col_to_num(match.group(1)), int(match.group(2))


def _ref_from_parts(col: int, row: int) -> str:
    return f"{_num_to_col(col)}{row}"


COMPONENT_COLUMNS = [_num_to_col(col) for col in range(_col_to_num("S"), _col_to_num("AC") + 1)]


def _adjust_shared_formula(formula: str, source_ref: str, target_ref: str) -> str:
    source_col, source_row = _split_ref(source_ref)
    target_col, target_row = _split_ref(target_ref)
    col_delta = target_col - source_col
    row_delta = target_row - source_row

    def replace(match: re.Match[str]) -> str:
        col_abs, col, row_abs, row = match.groups()
        new_col = _col_to_num(col) if col_abs else _col_to_num(col) + col_delta
        new_row = int(row) if row_abs else int(row) + row_delta
        return f"{col_abs}{_num_to_col(new_col)}{row_abs}{new_row}"

    return CELL_RE.sub(replace, formula)


def _literal(value) -> str:
    if value in (None, ""):
        return "0"
    text = str(value)
    try:
        number = float(text)
        if number.is_integer():
            return str(int(number))
        return repr(number)
    except ValueError:
        return json.dumps(text, ensure_ascii=False)


def _load_pricelist_sheet(workbook_path: str | Path) -> dict:
    path = Path(workbook_path)
    if not path.exists():
        raise FileNotFoundError(path)

    with ZipFile(path) as workbook:
        shared_strings = _read_shared_strings(workbook)
        workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
        rel_map = _read_relationships(workbook, "xl/_rels/workbook.xml.rels")
        sheet_path = _resolve_sheet_path(workbook_root, rel_map, SHEET_NAME)
        sheet_root = ET.fromstring(workbook.read(sheet_path))

        cells: dict[str, str | None] = {}
        formulas: dict[str, str] = {}
        formula_attrs: dict[str, dict[str, str]] = {}
        shared_formula_masters: dict[str, tuple[str, str]] = {}

        for cell in sheet_root.iter(_q("c")):
            ref = cell.attrib.get("r")
            if not ref:
                continue

            cells[ref] = _cell_value(cell, shared_strings)
            formula = cell.find(_q("f"))
            if formula is None:
                continue

            formula_attrs[ref] = dict(formula.attrib)
            shared_id = formula.attrib.get("si")
            if formula.text:
                formulas[ref] = formula.text
                if formula.attrib.get("t") == "shared" and shared_id is not None:
                    shared_formula_masters[shared_id] = (ref, formula.text)

        for ref, attrs in formula_attrs.items():
            shared_id = attrs.get("si")
            if ref in formulas or attrs.get("t") != "shared" or shared_id not in shared_formula_masters:
                continue
            source_ref, formula = shared_formula_masters[shared_id]
            formulas[ref] = _adjust_shared_formula(formula, source_ref, ref)

        return {
            "cells": cells,
            "formulas": formulas,
            "validations": _read_data_validations(sheet_root),
        }


def _read_shared_strings(workbook: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []

    root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    return ["".join(text.text or "" for text in string_item.iter(_q("t"))) for string_item in root.findall(_q("si"))]


def _read_relationships(workbook: ZipFile, rels_path: str) -> dict[str, str]:
    root = ET.fromstring(workbook.read(rels_path))
    return {rel.attrib["Id"]: rel.attrib["Target"] for rel in root}


def _resolve_sheet_path(workbook_root, rel_map: dict[str, str], sheet_name: str) -> str:
    sheets = workbook_root.find(_q("sheets"))
    if sheets is None:
        raise ValueError("Workbook has no sheets")
    for sheet in sheets.findall(_q("sheet")):
        if sheet.attrib.get("name") != sheet_name:
            continue
        target = rel_map[sheet.attrib[f"{{{NS['r']}}}id"]]
        if target.startswith("/"):
            return target.lstrip("/")
        return str(PurePosixPath("xl") / target)
    raise ValueError(f"Workbook sheet {sheet_name} was not found")


def _cell_value(cell, shared_strings: list[str]) -> str | None:
    cell_type = cell.attrib.get("t")
    value = cell.find(_q("v"))
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.iter(_q("t")))
    if value is None:
        return None
    if cell_type == "s":
        return shared_strings[int(value.text or 0)]
    return value.text


def _read_data_validations(sheet_root) -> dict[str, list[str]]:
    validations: dict[str, list[str]] = {}
    validation_root = sheet_root.find(_q("dataValidations"))
    if validation_root is None:
        return validations

    for validation in validation_root.findall(_q("dataValidation")):
        formula = validation.find(_q("formula1"))
        options = _parse_validation_options(formula.text if formula is not None else "")
        if not options:
            continue
        for ref in _expand_sqref(validation.attrib.get("sqref") or ""):
            validations[ref] = options
    return validations


def _parse_validation_options(formula: str) -> list[str]:
    text = (formula or "").strip()
    if len(text) < 2 or not text.startswith('"') or not text.endswith('"'):
        return []
    return [option.strip() for option in text[1:-1].split(",") if option.strip()]


def _expand_sqref(sqref: str) -> list[str]:
    refs = []
    for token in sqref.split():
        if ":" not in token:
            refs.append(token.replace("$", ""))
            continue
        start, end = token.split(":", 1)
        start_col, start_row = _split_ref(start)
        end_col, end_row = _split_ref(end)
        for row in range(start_row, end_row + 1):
            for col in range(start_col, end_col + 1):
                refs.append(_ref_from_parts(col, row))
    return refs


class FormulaTranslator:
    def __init__(self, cells: dict[str, str | None], formulas: dict[str, str]):
        self.cells = cells
        self.formulas = formulas
        self.memo: dict[tuple[int, str], str] = {}
        self.visiting: set[tuple[int, str]] = set()

    def row_expression(self, row: int) -> str:
        key = (row, "R")
        if key in self.memo:
            return self.memo[key]

        formula = self.formulas.get(f"R{row}")
        if formula:
            expression = self.translate(formula)
        elif self.cells.get(f"R{row}") not in (None, ""):
            expression = _literal(self.cells.get(f"R{row}"))
        elif self.cells.get(f"I{row}") not in (None, ""):
            expression = _literal(self.cells.get(f"I{row}"))
        else:
            expression = "0"

        self.memo[key] = expression
        return expression

    def component_expression(self, row: int, col: str) -> str:
        key = (row, col)
        if key in self.memo:
            return self.memo[key]
        if key in self.visiting:
            return "0"

        self.visiting.add(key)
        formula = self.formulas.get(f"{col}{row}")
        if formula:
            prefix = f"IF($C{row}={col}$10,"
            if formula.startswith(prefix) and (self.cells.get(f"C{row}") or "") != (self.cells.get(f"{col}10") or ""):
                expression = "0"
            else:
                expression = self.translate(formula)
        else:
            expression = _literal(self.cells.get(f"{col}{row}"))
        self.visiting.remove(key)
        self.memo[key] = expression
        return expression

    def ref_expression(self, ref: str) -> str:
        clean_ref = ref.replace("$", "")
        if clean_ref in INPUT_CELLS:
            return INPUT_CELLS[clean_ref]
        if clean_ref == "N2" and clean_ref in self.formulas:
            return self.translate(self.formulas[clean_ref])
        if clean_ref == "H1":
            return "999"

        col_number, row = _split_ref(clean_ref)
        col = _num_to_col(col_number)
        if col in COMPONENT_COLUMNS and row >= ROW_START:
            return self.component_expression(row, col)
        if col == "R" and row >= ROW_START:
            return self.row_expression(row)
        if clean_ref in self.formulas:
            return self.translate(self.formulas[clean_ref])
        return _literal(self.cells.get(clean_ref))

    def translate(self, formula: str) -> str:
        expression = (formula or "").strip()
        if expression.startswith("+"):
            expression = expression[1:]
        return _FormulaParser(_tokenize(expression), self).parse()


def _tokenize(expression: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    index = 0
    while index < len(expression):
        char = expression[index]
        if char.isspace():
            index += 1
            continue
        if char == '"':
            end = index + 1
            value = ""
            while end < len(expression):
                if expression[end] == '"':
                    break
                value += expression[end]
                end += 1
            tokens.append(("STRING", value))
            index = end + 1
            continue

        two_chars = expression[index : index + 2]
        if two_chars in {">=", "<=", "<>"}:
            tokens.append(("OP", two_chars))
            index += 2
            continue
        if char in "(),:+-*/=&<>":
            tokens.append((char, char))
            index += 1
            continue

        match = re.match(r"\$?[A-Z]{1,3}\$?\d+", expression[index:])
        if match:
            tokens.append(("CELL", match.group(0)))
            index += len(match.group(0))
            continue
        match = re.match(r"\d+(?:\.\d+)?", expression[index:])
        if match:
            tokens.append(("NUMBER", match.group(0)))
            index += len(match.group(0))
            continue
        match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", expression[index:])
        if match:
            tokens.append(("NAME", match.group(0)))
            index += len(match.group(0))
            continue
        raise ValueError(f"Unsupported formula token near {expression[index:]}")
    tokens.append(("EOF", ""))
    return tokens


class _FormulaParser:
    def __init__(self, tokens: list[tuple[str, str]], translator: FormulaTranslator):
        self.tokens = tokens
        self.index = 0
        self.translator = translator

    def peek(self) -> tuple[str, str]:
        return self.tokens[self.index]

    def pop(self, kind: str | None = None) -> tuple[str, str]:
        token = self.peek()
        if kind and token[0] != kind and token[1] != kind:
            raise ValueError(f"Expected {kind}, got {token}")
        self.index += 1
        return token

    def parse(self) -> str:
        expression = self.comparison()
        if self.peek()[0] != "EOF":
            raise ValueError(f"Unexpected token {self.peek()}")
        return expression

    def comparison(self) -> str:
        left = self.concat()
        while self.peek()[0] == "OP" or self.peek()[0] in {"=", "<", ">"}:
            operator = self.pop()[1]
            py_operator = {"=": "==", "<>": "!=", ">": ">", "<": "<", ">=": ">=", "<=": "<="}[operator]
            right = self.concat()
            left = f"({left} {py_operator} {right})"
        return left

    def concat(self) -> str:
        left = self.add()
        while self.peek()[0] == "&":
            self.pop("&")
            right = self.add()
            left = f"concat({left}, {right})"
        return left

    def add(self) -> str:
        left = self.multiply()
        while self.peek()[0] in {"+", "-"}:
            operator = self.pop()[0]
            right = self.multiply()
            left = f"({left} {operator} {right})"
        return left

    def multiply(self) -> str:
        left = self.unary()
        while self.peek()[0] in {"*", "/"}:
            operator = self.pop()[0]
            right = self.unary()
            left = f"({left} {operator} {right})"
        return left

    def unary(self) -> str:
        if self.peek()[0] in {"+", "-"}:
            operator = self.pop()[0]
            return f"({operator}{self.unary()})"
        return self.atom()

    def atom(self):
        token_type, value = self.peek()
        if token_type == "NUMBER":
            self.pop()
            return value
        if token_type == "STRING":
            self.pop()
            return _literal(value)
        if token_type == "CELL":
            self.pop()
            start_ref = value
            if self.peek()[0] == ":":
                self.pop(":")
                end_ref = self.pop("CELL")[1]
                return ("RANGE", start_ref, end_ref)
            return self.translator.ref_expression(start_ref)
        if token_type == "NAME":
            name = value
            self.pop()
            upper_name = name.upper()
            if upper_name == "TRUE":
                return "True"
            if upper_name == "FALSE":
                return "False"
            if self.peek()[0] == "(":
                self.pop("(")
                args = []
                if self.peek()[0] != ")":
                    while True:
                        args.append(self.comparison())
                        if self.peek()[0] != ",":
                            break
                        self.pop(",")
                self.pop(")")
                return self.call_expression(name, args)
            return name
        if token_type == "(":
            self.pop("(")
            value = self.comparison()
            self.pop(")")
            return f"({value})"
        raise ValueError(f"Unexpected formula token {self.peek()}")

    def call_expression(self, name: str, args: list) -> str:
        upper_name = name.upper()
        if upper_name == "IF":
            condition = args[0] if args else "False"
            yes = args[1] if len(args) > 1 else "0"
            no = args[2] if len(args) > 2 else "0"
            return f"ifelse({condition}, {yes}, {no})"
        if upper_name == "AND":
            return "(" + " and ".join(str(arg) for arg in args) + ")"
        if upper_name == "OR":
            return "(" + " or ".join(str(arg) for arg in args) + ")"
        if upper_name == "ISNUMBER":
            return str(args[0])
        if upper_name == "SEARCH":
            return f"contains({args[1]}, {args[0]})"
        if upper_name == "INT":
            return f"int({args[0]})"
        if upper_name == "SUM":
            terms = []
            for arg in args:
                if isinstance(arg, tuple) and arg[0] == "RANGE":
                    start_col, start_row = _split_ref(arg[1])
                    end_col, end_row = _split_ref(arg[2])
                    for row in range(start_row, end_row + 1):
                        for col in range(start_col, end_col + 1):
                            terms.append(self.translator.ref_expression(_ref_from_parts(col, row)))
                else:
                    terms.append(str(arg))
            return "(" + " + ".join(terms or ["0"]) + ")"
        return f"{name.lower()}(" + ", ".join(str(arg) for arg in args) + ")"


def build_payload(workbook_path: str = DEFAULT_WORKBOOK_PATH, set_name: str = DEFAULT_SET_NAME) -> dict:
    sheet = _load_pricelist_sheet(workbook_path)
    cells = sheet["cells"]
    translator = FormulaTranslator(cells, sheet["formulas"])

    return {
        "set_name": set_name,
        "description": "Imported from workbook formulas in Pricing & Edition Devis V01.2026.",
        "is_active": 1,
        "fields": _build_fields(cells, sheet["validations"]),
        "rule_groups": _build_rule_groups(cells, sheet["formulas"], translator),
    }


def _build_fields(cells: dict[str, str | None], validations: dict[str, list[str]]) -> list[dict]:
    fields = []
    for index, ref in enumerate(FIELD_ORDER, start=1):
        field_type = "Int" if ref in INT_CELLS else "Select"
        fields.append(
            {
                "sequence": index * 10,
                "field_key": INPUT_CELLS[ref],
                "label": cells.get(f"{ref[0]}1") or INPUT_CELLS[ref].replace("_", " ").title(),
                "field_type": field_type,
                "options": [] if field_type == "Int" else validations.get(ref, []),
                "default_value": cells.get(ref) or "",
                "is_required": 1,
                "group": _field_group(ref),
                "help_text": "Imported workbook input cell " + ref,
            }
        )
    return fields


def _field_group(ref: str) -> str:
    if ref in {"E2", "F2", "G2", "H2"}:
        return "General"
    if ref in {"I2", "N2"}:
        return "Motorisation"
    if ref in {"J2", "K2", "L2", "M2"}:
        return "Doors"
    return "Options"


def _build_rule_groups(cells: dict[str, str | None], formulas: dict[str, str], translator: FormulaTranslator) -> list[dict]:
    groups = []
    for row in range(ROW_START, ROW_END + 1):
        item_code = cells.get(f"A{row}")
        if not item_code:
            continue
        has_formula = bool(formulas.get(f"R{row}") or any(formulas.get(f"{col}{row}") for col in COMPONENT_COLUMNS))
        has_static_quantity = cells.get(f"I{row}") not in (None, "") or cells.get(f"R{row}") not in (None, "")
        if not has_formula and not has_static_quantity:
            continue

        expression = translator.row_expression(row)
        groups.append(
            {
                "rule_group": f"WB-{row:03d}",
                "sequence": row * 10,
                "is_active": 1,
                "condition_mode": "always",
                "articles": [
                    {
                        "sequence": row * 10,
                        "is_active": 1,
                        "rule_label": item_code,
                        "item": item_code,
                        "item_name": cells.get(f"B{row}") or item_code,
                        "uom": cells.get(f"D{row}") or "",
                        "weight_kg": cells.get(f"E{row}") or "",
                        "price_min": cells.get(f"F{row}") or "",
                        "price_normal": cells.get(f"G{row}") or "",
                        "price_stock": cells.get(f"H{row}") or "",
                        "display_group": cells.get(f"C{row}") or "Workbook",
                        "quantity_mode": "fixed",
                        "fixed_qty": 1,
                        "condition_formula": "",
                        "qty_formula": expression,
                        "show_in_detail": 1,
                    }
                ],
            }
        )
    return groups


def _summarize_payload(payload: dict) -> dict:
    rules = [article for group in payload.get("rule_groups") or [] for article in group.get("articles") or []]
    return {
        "set_name": payload.get("set_name"),
        "field_count": len(payload.get("fields") or []),
        "rule_group_count": len(payload.get("rule_groups") or []),
        "article_count": len(rules),
    }


def _missing_items(payload: dict) -> list[str]:
    frappe_module = _get_frappe()
    missing = []
    for group in payload.get("rule_groups") or []:
        for article in group.get("articles") or []:
            item = article.get("item")
            if item and not frappe_module.db.exists("Item", item):
                missing.append(item)
    return sorted(set(missing))


def _ensure_missing_items(payload: dict) -> int:
    frappe_module = _get_frappe()
    created = 0
    seen = set()
    for group in payload.get("rule_groups") or []:
        for article in group.get("articles") or []:
            item_code = article.get("item")
            if not item_code or item_code in seen or frappe_module.db.exists("Item", item_code):
                continue
            seen.add(item_code)
            item_group = _ensure_item_group(article.get("display_group") or "Workbook")
            uom = _ensure_uom(article.get("uom") or _default_stock_uom())
            frappe_module.get_doc(
                {
                    "doctype": "Item",
                    "item_code": item_code,
                    "item_name": (article.get("item_name") or item_code)[:140],
                    "description": article.get("item_name") or item_code,
                    "item_group": item_group,
                    "stock_uom": uom,
                    "weight_per_unit": _as_float(article.get("weight_kg")),
                    "weight_uom": "Kg" if _as_float(article.get("weight_kg")) else "",
                    "disabled": 0,
                    "is_stock_item": 1,
                    "include_item_in_manufacturing": 0,
                }
            ).insert(ignore_permissions=True)
            created += 1
    return created


def _ensure_item_prices(payload: dict, dry_run: int = 0) -> int:
    frappe_module = _get_frappe()
    count = 0
    for group in payload.get("rule_groups") or []:
        for article in group.get("articles") or []:
            item_code = article.get("item")
            if not item_code or not frappe_module.db.exists("Item", item_code):
                continue
            item_uom = frappe_module.db.get_value("Item", item_code, "stock_uom") or _ensure_uom(
                article.get("uom") or _default_stock_uom()
            )
            for price_key, price_list in PRICE_LIST_COLUMNS.items():
                rate = _as_float(article.get(price_key))
                if rate <= 0:
                    continue
                filters = {"item_code": item_code, "price_list": price_list, "uom": item_uom}
                if frappe_module.db.exists("Item Price", filters):
                    continue
                count += 1
                if _as_int(dry_run):
                    continue
                _ensure_price_list(price_list)
                frappe_module.get_doc(
                    {
                        "doctype": "Item Price",
                        "item_code": item_code,
                        "price_list": price_list,
                        "currency": "MAD",
                        "price_list_rate": rate,
                        "selling": 1,
                        "buying": 0,
                        "uom": item_uom,
                    }
                ).insert(ignore_permissions=True)
    return count


def _ensure_item_group(item_group: str) -> str:
    frappe_module = _get_frappe()
    item_group = (item_group or "Workbook").strip()
    if frappe_module.db.exists("Item Group", item_group):
        return item_group
    frappe_module.get_doc(
        {
            "doctype": "Item Group",
            "item_group_name": item_group,
            "parent_item_group": "All Item Groups",
            "is_group": 0,
        }
    ).insert(ignore_permissions=True)
    return item_group


def _ensure_price_list(price_list: str) -> str:
    frappe_module = _get_frappe()
    if frappe_module.db.exists("Price List", price_list):
        return price_list
    frappe_module.get_doc(
        {
            "doctype": "Price List",
            "price_list_name": price_list,
            "currency": "MAD",
            "selling": 1,
            "buying": 0,
            "enabled": 1,
        }
    ).insert(ignore_permissions=True)
    return price_list


def _ensure_uom(uom: str) -> str:
    frappe_module = _get_frappe()
    uom = (uom or "Nos").strip()
    if frappe_module.db.exists("UOM", uom):
        return uom
    frappe_module.get_doc({"doctype": "UOM", "uom_name": uom, "enabled": 1}).insert(ignore_permissions=True)
    return uom


def _default_stock_uom() -> str:
    frappe_module = _get_frappe()
    for uom in ("Nos", "Unit"):
        if frappe_module.db.exists("UOM", uom):
            return uom
    frappe_module.get_doc({"doctype": "UOM", "uom_name": "Nos", "enabled": 1}).insert(ignore_permissions=True)
    return "Nos"


def run(
    workbook_path: str = DEFAULT_WORKBOOK_PATH,
    set_name: str = DEFAULT_SET_NAME,
    target_name: str | None = None,
    dry_run: int = 0,
    create_missing_items: int = 0,
    create_missing_prices: int = 0,
) -> dict:
    frappe_module = _get_frappe()
    from orderlift.orderlift_sales.doctype.dimensioning_set.dimensioning_set import save_dimensioning_builder_payload

    payload = build_payload(workbook_path=workbook_path, set_name=set_name)
    existing_name = target_name or frappe_module.db.get_value("Dimensioning Set", {"set_name": set_name}, "name")
    if existing_name:
        payload["name"] = existing_name

    summary = _summarize_payload(payload)
    missing = _missing_items(payload)
    summary["missing_item_count"] = len(missing)
    summary["missing_items"] = missing[:25]
    if missing:
        summary["create_missing_items"] = _as_int(create_missing_items)
        summary["status"] = "missing_items"
        if not _as_int(create_missing_items):
            if not _as_int(dry_run):
                frappe_module.throw("Missing Item records for Dimensioning Set import: " + ", ".join(missing[:25]))
            return summary
        if _as_int(dry_run):
            return summary

        summary["created_item_count"] = _ensure_missing_items(payload)
        missing = _missing_items(payload)
        summary["missing_item_count"] = len(missing)
        summary["missing_items"] = missing[:25]
        if missing:
            frappe_module.throw("Missing Item records for Dimensioning Set import: " + ", ".join(missing[:25]))

    if _as_int(create_missing_prices):
        summary["created_price_count"] = _ensure_item_prices(payload, dry_run=dry_run)

    if _as_int(dry_run):
        summary["status"] = "dry_run"
        summary["target_name"] = existing_name or ""
        return summary

    result = save_dimensioning_builder_payload(payload)
    frappe_module.db.commit()
    summary["status"] = "imported"
    summary["name"] = result.get("name")
    return summary


def preview_summary(set_name: str = "DSET-00038", input_values_json: str | None = None) -> dict:
    from orderlift.orderlift_sales.doctype.dimensioning_set.dimensioning_set import preview_dimensioning_set

    result = preview_dimensioning_set(set_name, input_values_json=input_values_json)
    items = result.get("items") or []
    return {
        "set_name": (result.get("set") or {}).get("set_name") or set_name,
        "field_count": len((result.get("set") or {}).get("fields") or []),
        "rule_group_count": len((result.get("set") or {}).get("rule_groups") or []),
        "item_count": len(items),
        "items": [row.get("item") for row in items],
    }


def _get_frappe():
    if frappe is not None:
        return frappe
    import frappe as frappe_module

    return frappe_module


def _as_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_float(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


if frappe is not None:
    run = frappe.whitelist()(run)
    preview_summary = frappe.whitelist()(preview_summary)
