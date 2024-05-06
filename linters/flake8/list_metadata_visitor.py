# standard libs
import ast
from typing import Any

from linters.flake8.common import HOOK_V3_FUNCTIONS, HOOK_V4_FUNCTIONS, ErrorType

ERRORS_CTR002 = (
    "CTR002 List-type metadata objects should be extended using the unpacking operator (*)"
)


class ListMetadataVisitor(ast.NodeVisitor):
    """
    Raise an error if list-type metadata objects are extended not using the unpacking operator (*).
    This includes using .append(), .extend(), +=, list slicing, and modification within a root
    level function.
    """

    METADATA_LISTS = [
        "global_parameters",
        "parameters",
        "supported_denominations",
        "event_types",
        "event_types_groups",
        "contract_module_imports",
        "data_fetchers",
    ]

    def __init__(self, tree: ast.Module, contract_version: str):
        self.tree = tree
        self.version = contract_version
        self.violations: list[ErrorType] = []
        self.metadata_count = {obj: 0 for obj in self.METADATA_LISTS}
        # track context name and set of names marked as `global`
        self.context = ["global"]
        # get a list of non-hook functions on instantiation
        self.non_hook_non_helper_funcs = self.get_non_hook_non_helper_funcs()

    def get_non_hook_non_helper_funcs(self) -> set:
        all_functions = set(n.name for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef))

        hook_and_helper_functions = (
            HOOK_V3_FUNCTIONS.copy() if self.version == "3" else HOOK_V4_FUNCTIONS.copy()
        )
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in hook_and_helper_functions:
                called_functions = [
                    n.func.id
                    for n in ast.walk(node)
                    if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name))
                ]
                # add called functions to set of hook & helper functions
                hook_and_helper_functions.update(called_functions)

        # return only functions that are not hooks and not hook-helpers
        return all_functions - hook_and_helper_functions

    def visit_Name(self, node: ast.Name) -> Any:
        # only check global level changes to list-type metadata objects
        if node.id in self.METADATA_LISTS and self.context[-1] == "global":
            self.metadata_count[node.id] += 1
            if self.metadata_count[node.id] > 1:
                self.violations.append((node.lineno, node.col_offset, ERRORS_CTR002))
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        if node.name in self.non_hook_non_helper_funcs:
            # consider non-hook/non-helper functions as in the global space
            self._non_global_logic(node, "global")
        else:
            self._non_global_logic(node, "function")

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self._non_global_logic(node, "async_function")

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self._non_global_logic(node, "class")

    def visit_Lambda(self, node: ast.Lambda) -> Any:
        self._non_global_logic(node, "lambda")

    def visit_For(self, node: ast.For) -> Any:
        self._non_global_logic(node, "for")

    def _non_global_logic(self, node, context: str) -> Any:
        self.context.append(context)
        self.generic_visit(node)
        self.context.pop()
