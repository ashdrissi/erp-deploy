from __future__ import annotations

import ast
import math
import operator
import re
from typing import Any


KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SAFE_FUNCTIONS = {
    "abs": abs,
    "ceil": math.ceil,
    "concat": lambda *values: "".join("" if value is None else str(value) for value in values),
    "contains": lambda text, needle: str(needle or "").lower() in str(text or "").lower(),
    "floor": math.floor,
    "float": float,
    "ifelse": lambda condition, yes, no: yes if condition else no,
    "int": math.floor,
    "lower": lambda text: str(text or "").lower(),
    "max": max,
    "min": min,
    "one_of": lambda value, *options: value in options,
    "round": round,
    "upper": lambda text: str(text or "").upper(),
}
ALLOWED_BIN_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow)
ALLOWED_UNARY_OPS = (ast.UAdd, ast.USub, ast.Not)
ALLOWED_BOOL_OPS = (ast.And, ast.Or)
ALLOWED_COMPARE_OPS = (ast.Eq, ast.NotEq, ast.Gt, ast.GtE, ast.Lt, ast.LtE)
STRUCTURED_OPERATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
}
NUMERIC_FIELD_TYPES = {"Int", "Float"}


def validate_dimensioning_key(key: str) -> str:
    normalized = (key or "").strip()
    if not KEY_RE.match(normalized):
        raise ValueError(f"Invalid dimensioning key '{key}'. Use letters, digits, and underscores only.")
    if normalized in SAFE_FUNCTIONS:
        raise ValueError(f"Dimensioning key '{key}' is reserved.")
    return normalized


def validate_formula(expression: str, allowed_names: set[str]) -> None:
    if not (expression or "").strip():
        return
    tree = ast.parse(expression, mode="eval")
    _validate_node(tree, allowed_names)


def evaluate_formula(expression: str, variables: dict[str, Any]) -> Any:
    expr = (expression or "").strip()
    if not expr:
        return 0
    allowed_names = set(variables.keys())
    tree = ast.parse(expr, mode="eval")
    _validate_node(tree, allowed_names)
    return _eval_node(tree.body, variables)


def coerce_dimensioning_value(field_type: str, raw_value: Any) -> Any:
    kind = (field_type or "Float").strip().title()
    if kind == "Check":
        if isinstance(raw_value, str):
            return raw_value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(raw_value)
    if kind == "Int":
        if raw_value in (None, ""):
            return 0
        return int(float(raw_value))
    if kind == "Float":
        if raw_value in (None, ""):
            return 0.0
        return float(raw_value)
    return "" if raw_value is None else str(raw_value).strip()


def evaluate_structured_condition(rule: Any, values: dict[str, Any], field_types: dict[str, str] | None = None) -> bool:
    mode = (_get(rule, "condition_mode") or "always").strip()
    if mode == "always":
        return True
    if mode != "based":
        raise ValueError(f"Unsupported condition mode '{mode}'.")

    question_key = (_get(rule, "question_key") or "").strip()
    if not question_key:
        raise ValueError("Condition question is required.")
    if question_key not in values:
        raise ValueError(f"Unknown condition question '{question_key}'.")

    operator_key = normalize_structured_operator(_get(rule, "operator") or "==")
    compare_source = (_get(rule, "compare_source") or "manual").strip()
    left = values[question_key]
    field_type = (field_types or {}).get(question_key, "Data")

    if compare_source == "question":
        compare_question_key = (_get(rule, "compare_question_key") or "").strip()
        if not compare_question_key:
            raise ValueError("Compare question is required.")
        if compare_question_key not in values:
            raise ValueError(f"Unknown compare question '{compare_question_key}'.")
        right = values[compare_question_key]
    elif compare_source == "manual":
        right = coerce_dimensioning_value(field_type, _get(rule, "manual_value"))
    else:
        raise ValueError(f"Unsupported compare source '{compare_source}'.")

    return bool(STRUCTURED_OPERATORS[operator_key](left, right))


def evaluate_structured_quantity(rule: Any, values: dict[str, Any]) -> float:
    mode = (_get(rule, "quantity_mode") or "fixed").strip()
    if mode == "fixed":
        return float(_get(rule, "fixed_qty") or 0)
    if mode == "question":
        question_key = (_get(rule, "quantity_question_key") or "").strip()
        if not question_key:
            raise ValueError("Quantity question is required.")
        if question_key not in values:
            raise ValueError(f"Unknown quantity question '{question_key}'.")
        return float(values[question_key] or 0)
    raise ValueError(f"Unsupported quantity mode '{mode}'.")


def normalize_structured_operator(operator_key: str) -> str:
    normalized = (operator_key or "==").strip()
    if normalized not in STRUCTURED_OPERATORS:
        raise ValueError(f"Unsupported operator '{operator_key}'.")
    return normalized


def allowed_structured_operators(field_type: str) -> set[str]:
    if (field_type or "Data").strip().title() in NUMERIC_FIELD_TYPES:
        return set(STRUCTURED_OPERATORS)
    return {"==", "!="}


def validate_structured_condition(rule: Any, field_types: dict[str, str]) -> None:
    mode = (_get(rule, "condition_mode") or "always").strip()
    if mode == "always":
        return
    if mode != "based":
        raise ValueError(f"Unsupported condition mode '{mode}'.")

    question_key = (_get(rule, "question_key") or "").strip()
    if not question_key or question_key not in field_types:
        raise ValueError(f"Unknown condition question '{question_key}'.")
    operator_key = normalize_structured_operator(_get(rule, "operator") or "==")
    if operator_key not in allowed_structured_operators(field_types[question_key]):
        raise ValueError(f"Operator '{operator_key}' is not valid for {field_types[question_key]} questions.")

    compare_source = (_get(rule, "compare_source") or "manual").strip()
    if compare_source == "question":
        compare_question_key = (_get(rule, "compare_question_key") or "").strip()
        if not compare_question_key or compare_question_key not in field_types:
            raise ValueError(f"Unknown compare question '{compare_question_key}'.")
    elif compare_source != "manual":
        raise ValueError(f"Unsupported compare source '{compare_source}'.")


def validate_structured_quantity(rule: Any, field_types: dict[str, str]) -> None:
    mode = (_get(rule, "quantity_mode") or "fixed").strip()
    if mode == "fixed":
        float(_get(rule, "fixed_qty") or 0)
        return
    if mode == "question":
        question_key = (_get(rule, "quantity_question_key") or "").strip()
        if not question_key or question_key not in field_types:
            raise ValueError(f"Unknown quantity question '{question_key}'.")
        if field_types[question_key] not in NUMERIC_FIELD_TYPES:
            raise ValueError(f"Quantity question '{question_key}' must be Int or Float.")
        return
    raise ValueError(f"Unsupported quantity mode '{mode}'.")


def _get(row: Any, key: str) -> Any:
    if isinstance(row, dict):
        return row.get(key)
    return getattr(row, key, None)


def _validate_node(node: ast.AST, allowed_names: set[str]) -> None:
    if isinstance(node, ast.Expression):
        _validate_node(node.body, allowed_names)
        return

    if isinstance(node, ast.Constant):
        return

    if isinstance(node, ast.Name):
        if node.id not in allowed_names and node.id not in SAFE_FUNCTIONS:
            raise ValueError(f"Unknown variable '{node.id}' in formula.")
        return

    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, ALLOWED_BIN_OPS):
            raise ValueError("Unsupported operator in formula.")
        _validate_node(node.left, allowed_names)
        _validate_node(node.right, allowed_names)
        return

    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, ALLOWED_UNARY_OPS):
            raise ValueError("Unsupported unary operator in formula.")
        _validate_node(node.operand, allowed_names)
        return

    if isinstance(node, ast.BoolOp):
        if not isinstance(node.op, ALLOWED_BOOL_OPS):
            raise ValueError("Unsupported boolean operator in formula.")
        for value in node.values:
            _validate_node(value, allowed_names)
        return

    if isinstance(node, ast.Compare):
        if not all(isinstance(op, ALLOWED_COMPARE_OPS) for op in node.ops):
            raise ValueError("Unsupported comparison operator in formula.")
        _validate_node(node.left, allowed_names)
        for comparator in node.comparators:
            _validate_node(comparator, allowed_names)
        return

    if isinstance(node, ast.IfExp):
        _validate_node(node.test, allowed_names)
        _validate_node(node.body, allowed_names)
        _validate_node(node.orelse, allowed_names)
        return

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in SAFE_FUNCTIONS:
            raise ValueError("Unsupported function in formula.")
        for arg in node.args:
            _validate_node(arg, allowed_names)
        for keyword in node.keywords:
            _validate_node(keyword.value, allowed_names)
        return

    raise ValueError("Unsupported expression in formula.")


def _eval_node(node: ast.AST, variables: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        if node.id in SAFE_FUNCTIONS:
            return SAFE_FUNCTIONS[node.id]
        return variables[node.id]

    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, variables)
        right = _eval_node(node.right, variables)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Mod):
            return left % right
        return left**right

    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand, variables)
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.USub):
            return -operand
        return not operand

    if isinstance(node, ast.BoolOp):
        values = [_eval_node(value, variables) for value in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        return any(values)

    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, variables)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, variables)
            if isinstance(op, ast.Eq):
                ok = left == right
            elif isinstance(op, ast.NotEq):
                ok = left != right
            elif isinstance(op, ast.Gt):
                ok = left > right
            elif isinstance(op, ast.GtE):
                ok = left >= right
            elif isinstance(op, ast.Lt):
                ok = left < right
            else:
                ok = left <= right
            if not ok:
                return False
            left = right
        return True

    if isinstance(node, ast.IfExp):
        return _eval_node(node.body, variables) if _eval_node(node.test, variables) else _eval_node(node.orelse, variables)

    if isinstance(node, ast.Call):
        fn = SAFE_FUNCTIONS[node.func.id]
        args = [_eval_node(arg, variables) for arg in node.args]
        kwargs = {kw.arg: _eval_node(kw.value, variables) for kw in node.keywords}
        return fn(*args, **kwargs)

    raise ValueError("Unsupported expression in formula.")
