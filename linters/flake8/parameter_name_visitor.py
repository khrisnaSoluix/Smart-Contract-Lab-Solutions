# standard libs
import ast
from typing import Any

from linters.flake8.common import ErrorType

ERRORS_CTR007 = "CTR007 Use PARAM_ constant for parameter names"


class ParameterNameVisitor(ast.NodeVisitor):
    """
    Raise an error if a literal string value is passed into the 'name' argument for a
    Parameter definition rather than a PARAM_-prefixed constant.
    """

    def __init__(self):
        self.violations: list[ErrorType] = []

    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Name) and node.func.id == "Parameter":
            for kw in node.keywords:
                # if name= is a assigned to a ast/Constant then it is a string
                if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                    self.violations.append((kw.lineno, kw.col_offset, ERRORS_CTR007))
                # if it is assigned to a ast.Name then it is pointing to a constant,
                # so we want to ensure it begins with PARAM_
                elif (
                    kw.arg == "name"
                    and isinstance(kw.value, ast.Name)
                    and not (kw.value.id).startswith("PARAM_")
                ):
                    self.violations.append((kw.lineno, kw.col_offset, ERRORS_CTR007))
        self.generic_visit(node)
