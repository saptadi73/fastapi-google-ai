"""Small arithmetic interpreter. Sheet content is never executed as Python or SQL."""

import ast
from decimal import Decimal, DecimalException, localcontext


def parse_expression(expression):
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, RecursionError):
        raise ValueError("Formula tidak valid") from None
    nodes = list(ast.walk(tree))
    allowed = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.UAdd,
        ast.USub,
    )
    if len(nodes) > 100 or any(not isinstance(n, allowed) for n in nodes):
        raise ValueError("Formula hanya mendukung angka, kode metrik/formula, + - * / dan tanda kurung")
    for node in nodes:
        if isinstance(node, ast.Constant):
            if type(node.value) not in (int, float):
                raise ValueError("Konstanta formula harus angka terbatas")
            try:
                number = Decimal(ast.get_source_segment(expression, node).replace("_", ""))
            except DecimalException:
                raise ValueError("Konstanta formula harus angka desimal") from None
            if not number.is_finite() or len(number.as_tuple().digits) > 28 or abs(number) > Decimal("1e18"):
                raise ValueError("Konstanta formula terlalu besar")
            node.decimal_value = number
    return tree.body


def validate_formulas(formulas, metrics):
    available = set(metrics)
    for formula in formulas:
        tree = parse_expression(formula.expression)
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        if not names:
            raise ValueError("Formula harus merujuk metrik atau formula sebelumnya sebagai bukti data")
        if names - available:
            raise ValueError(
                "Formula merujuk kode tidak tersedia atau urutan dependency salah: "
                + ", ".join(sorted(names - available))
            )
        available.add(formula.formula_code)


def calculate(expression, values):
    def visit(node):
        if isinstance(node, ast.Constant):
            return node.decimal_value
        if isinstance(node, ast.Name):
            value = values.get(node.id)
            if value is None:
                raise ValueError("MISSING_VALUE")
            if isinstance(value, bool):
                raise ValueError("NON_NUMERIC_VALUE")
            number = Decimal(str(value))
            if not number.is_finite():
                raise ValueError("NON_NUMERIC_VALUE")
            return number
        if isinstance(node, ast.UnaryOp):
            number = visit(node.operand)
            return -number if isinstance(node.op, ast.USub) else number
        left, right = visit(node.left), visit(node.right)
        if isinstance(node.op, ast.Div) and right == 0:
            raise ValueError("ZERO_DENOMINATOR")
        if isinstance(node.op, ast.Add):
            result = left + right
        elif isinstance(node.op, ast.Sub):
            result = left - right
        elif isinstance(node.op, ast.Mult):
            result = left * right
        else:
            result = left / right
        if not result.is_finite() or abs(result) > Decimal("1e30"):
            raise ValueError("NUMERIC_OUT_OF_RANGE")
        return result

    try:
        with localcontext() as context:
            context.prec = 28
            result = visit(parse_expression(expression))
            if abs(result) > Decimal("1e30"):
                raise ValueError("NUMERIC_OUT_OF_RANGE")
            return result, None
    except (DecimalException, ValueError, TypeError) as exc:
        message = str(exc)
        return None, message if message in {
            "ZERO_DENOMINATOR",
            "MISSING_VALUE",
            "NON_NUMERIC_VALUE",
            "NUMERIC_OUT_OF_RANGE",
        } else "NON_NUMERIC_VALUE"
