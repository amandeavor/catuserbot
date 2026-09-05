"""Bounded arithmetic/string evaluation for untrusted link-page expressions."""
import ast
import operator


def evaluate_link_expression(expression):
    if not isinstance(expression, str) or len(expression) > 8192:
        raise ValueError("Link expression is too large")
    tree = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 256:
        raise ValueError("Link expression is too complex")
    operations = {ast.Add: operator.add, ast.Sub: operator.sub,
                  ast.Mult: operator.mul, ast.Mod: operator.mod}

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, str):
            value = node.value
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            operand = visit(node.operand)
            if type(operand) is not int:
                raise ValueError("Invalid link arithmetic")
            value = operand if isinstance(node.op, ast.UAdd) else -operand
        elif isinstance(node, ast.BinOp) and type(node.op) in operations:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add) and type(left) is str and type(right) is str:
                value = left + right
            elif type(left) is int and type(right) is int:
                try:
                    value = operations[type(node.op)](left, right)
                except ArithmeticError:
                    raise ValueError("Invalid link arithmetic") from None
            else:
                raise ValueError("Unsupported link expression operands")
        else:
            raise ValueError("Unsupported link expression")
        if (type(value) is int and abs(value) > 10**15) or (type(value) is str and len(value) > 8192):
            raise ValueError("Link expression result is too large")
        return value

    return visit(tree.body)
