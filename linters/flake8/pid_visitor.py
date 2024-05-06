# standard libs
import ast
from typing import Any

from linters.flake8.common import ErrorType

ERRORS_CTR009 = "CTR009 set value_datetime on PID/PIB by default"


class PidVisitor(ast.NodeVisitor):
    """
    Raise an error if PostingInstructionDirective (Contracts API 4.x) or
    PostingInstructionBatch (Contracts API 3.x) don't set value_datetime
    """

    def __init__(self):
        self.violations: list[ErrorType] = []

    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Name) and node.func.id in {
            "PostingInstructionBatch",
            "PostingInstructionsDirective",
        }:
            if not any(kw.arg == "value_datetime" for kw in node.keywords):
                self.violations.append((node.lineno, node.col_offset, ERRORS_CTR009))
        self.generic_visit(node)
