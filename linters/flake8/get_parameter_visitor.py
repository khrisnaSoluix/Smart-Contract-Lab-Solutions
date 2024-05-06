# standard libs
import ast
from typing import Any, Optional

from linters.flake8.common import ErrorType

ERRORS_CTR006 = (
    "CTR006 Call 'utils.get_parameter()' with the parameter constant rather than hard-coded string"
)
# This can be removed when we update get_parameter to use * to enforce kwargs
ERRORS_CTR006B = "CTR006B Pass parameter name as kwarg into 'utils.get_parameter()'"


class GetParameterVisitor(ast.NodeVisitor):
    """
    Raise an error if 'utils.get_parameter()' is called with name="string_name"
    rather than name=PARAM_NAME_CONSTANT
    """

    def __init__(self):
        self.violations: list[ErrorType] = []

    def attribute_is_utils_get_parameter(self, attribute_obj: ast.Attribute):
        return (
            isinstance(attribute_obj.value, ast.Name)
            and attribute_obj.value.id == "utils"
            and attribute_obj.attr == "get_parameter"
        )

    def get_name_arg_from_kwargs(self, keywords: list[ast.keyword]) -> Optional[ast.keyword]:
        for keyword in keywords:
            if keyword.arg == "name":
                return keyword
        return None

    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Attribute) and self.attribute_is_utils_get_parameter(
            node.func
        ):
            if name_kwargs := self.get_name_arg_from_kwargs(node.keywords):
                if isinstance(name_kwargs.value, ast.Constant):
                    self.violations.append((node.lineno, node.col_offset, ERRORS_CTR006))

            else:
                self.violations.append((node.lineno, node.col_offset, ERRORS_CTR006B))
        self.generic_visit(node)
