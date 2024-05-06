# standard libs
import ast
import re
from typing import Any

from linters.flake8.common import ErrorType

ERRORS_CTR008 = "CTR008 Use Title Caps For Display Names"
_RE_BRACKETS_STRIPPER = re.compile("\\s*(\\(.*\\))\\s*")


class ParameterDisplayNameVisitor(ast.NodeVisitor):
    """
    Raise an error if the Parameter's display name string is not in title case
    """

    def __init__(self):
        self.violations: list[ErrorType] = []

    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Name) and node.func.id == "Parameter":
            for kw in node.keywords:
                # if name= is a assigned to a ast/Constant then it is a string
                if (
                    kw.arg == "display_name"
                    and isinstance(kw.value, ast.Constant)
                    and not self.check_title_caps(kw.value.value)
                ):
                    self.violations.append((kw.lineno, kw.col_offset, ERRORS_CTR008))
        self.generic_visit(node)

    @staticmethod
    def check_title_caps(string: str):
        string = _RE_BRACKETS_STRIPPER.sub(" ", str(string))
        words = [w for w in string.split(" ") if len(w) > 0]
        return all([w[0].isupper() for w in words])
