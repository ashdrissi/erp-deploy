from __future__ import annotations

import ast
import math
import re
from typing import Any


KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SAFE_FUNCTIONS = {
    "abs": abs,
    "ceil": math.ceil,
    "floor": math.floor,
    "float": float,
    "int": int,
    "max": max,
    "min": min,
    "round": round,
}
ALLOWED_BIN_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow)
ALLOWED_UNARY_OPS = (ast.UAdd, ast.USub, ast.Not)
ALLOWED_BOOL_OPS = (ast.And, ast.Or)
ALLOWED_COMPARE_OPS = (ast.Eq, ast.NotEq, ast.Gt, ast.GtE, ast.Lt, ast.LtE)


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
