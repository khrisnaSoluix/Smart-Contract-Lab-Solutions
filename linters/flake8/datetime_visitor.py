# standard libs
import ast
from typing import Any

from linters.flake8.common import ErrorType

ERRORS_CTR001 = "CTR001 Do not use datetime.now()/datetime.utcnow() inside contracts"


class DatetimeVisitor(ast.NodeVisitor):
    """
    Raise an error if datetime.now()/datetime.utcnow() is used within a contract.
    """

    def __init__(self):
        self.all_violations: list[ErrorType] = []
        self.to_ignore: list[ErrorType] = []

    @property
    def violations(self) -> list[ErrorType]:
        return [v for v in self.all_violations if v not in self.to_ignore]

    @staticmethod
    def _attribute_is_datetime(node: ast.Attribute):
        return (
            node.attr in ["now", "utcnow"]
            and isinstance(node.value, ast.Name)
            and node.value.id == "datetime"
        )

    def visit_keyword(self, node: ast.keyword) -> Any:
        if (
            node.arg == "default_value"
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and self._attribute_is_datetime(node.value.func)
        ):
            attribute_node = node.value.func
            # add uses in Parameter default_value to ignore list
            self.to_ignore.append((attribute_node.lineno, attribute_node.col_offset, ERRORS_CTR001))
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if self._attribute_is_datetime(node):
            # add all instances to the violation list
            self.all_violations.append((node.lineno, node.col_offset, ERRORS_CTR001))
        self.generic_visit(node)
