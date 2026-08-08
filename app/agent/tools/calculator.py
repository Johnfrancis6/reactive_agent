
import ast
import operator as op
from typing import Any
from langchain_core.tools import tool
from app.core.logging import get_logger

log = get_logger(__name__)



_ALLOWED_OPERATORS = {
    ast.Add:      op.add,
    ast.Sub:      op.sub,
    ast.Mult:     op.mul,
    ast.Div:      op.truediv,
    ast.Pow:      op.pow,
    ast.USub:     op.neg,
    ast.Mod:      op.mod,
    ast.FloorDiv: op.floordiv,
}




def _eval_math(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, float)):
            raise ValueError(f"Type not supported: {type(node.value).__name__}")
        return node.value

    if isinstance(node, ast.BinOp):
        left  = _eval_math(node.left)
        right = _eval_math(node.right)
        if isinstance(node.op, (ast.Div, ast.FloorDiv)) and right == 0:
            raise ValueError("Division by zero")
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise ValueError(f"Exponent too large: {right}")
        operator_fn = _ALLOWED_OPERATORS.get(type(node.op))
        if operator_fn is None:
            raise ValueError(f"Unsupported operator: {ast.dump(node.op)}")
        return operator_fn(left, right)

    if isinstance(node, ast.UnaryOp):
        operand = _eval_math(node.operand)
        operator_fn = _ALLOWED_OPERATORS.get(type(node.op))
        if operator_fn is None:
            raise ValueError(f"Unsupported unary operator: {ast.dump(node.op)}")
        return operator_fn(operand)

    raise ValueError(f"Unsupported expression: {ast.dump(node)}")



@tool
async def calculator(expression: str) -> str:
    """
    Safely evaluates a simple mathematical expression.
    Arguments:
        expression: Arithmetic expression to evaluate.
    """
    try:
        parsed = ast.parse(expression, mode="eval")
        result = _eval_math(parsed.body)
        log.info("calculator_completed: expr=%s result=%s", expression, result)
        return str(result)
    except Exception as exc:
        log.error("calculator_error: expr=%s error=%s", expression, str(exc))
        return f"Calculation error: {str(exc)}"


