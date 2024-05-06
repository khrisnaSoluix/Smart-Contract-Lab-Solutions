"""Flake8 plugin that warns of Contract anti-patterns"""

import ast
from typing import Generator, Tuple, Any, Type, List

ErrorType = Tuple[int, int, str]
__version__ = "1.0"
ERRORS_CTR001 = "CTR001 Do not use datetime.now()/datetime.utcnow() inside contracts"
ERRORS_CTR002 = (
    "CTR002 List-type metadata objects should be extended using the unpacking operator (*)"
)


class DatetimeVistor(ast.NodeVisitor):
    """
    Raise an error if datetime.now()/datetime.utcnow() is used within a contract.
    """

    def __init__(self):
        self.violations: List[ErrorType] = []

    def visit_Attribute(self, node: ast.Attribute):
        if (
            node.attr in ["now", "utcnow"]
            and isinstance(node.value, ast.Name)
            and node.value.id == "datetime"
        ):
            self.violations.append((node.lineno, node.col_offset, ERRORS_CTR001))
        self.generic_visit(node)


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

    HOOK_FUNCTIONS = {
        "close_code",
        "derived_parameters",
        "execution_schedules",
        "post_activate_code",
        "post_parameter_change_code",
        "post_posting_code",
        "pre_parameter_change_code",
        "pre_posting_code",
        "scheduled_code",
        "upgrade_code",
    }

    def __init__(self, tree):
        self.tree = tree
        self.violations: List[ErrorType] = []
        self.metadata_count = {obj: 0 for obj in self.METADATA_LISTS}
        # track context name and set of names marked as `global`
        self.context = ["global"]
        # get a list of non-hook functions on instantiation
        self.non_hook_non_helper_funcs = self.get_non_hook_non_helper_funcs()

    def get_non_hook_non_helper_funcs(self) -> set:
        all_functions = set(n.name for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef))

        hook_and_helper_functions = self.HOOK_FUNCTIONS.copy()
        for node in ast.walk(self.tree):
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


class ContractLinter(object):
    name = "flake8_contracts"
    version = __version__

    def __init__(self, tree, filename=""):
        self.tree: ast.Module = tree
        self.filename: str = filename

    def _is_contract_file(self):
        # For now we will just identify contracts and modules via the `api`` metadata. It's not
        # perfect, but it's the only thing in common across the different types
        for statement in self.tree.body:
            # setting metadata results in top-level Assign objects, whose targets should have
            # the name(s) we expect
            if isinstance(statement, ast.Assign):
                for target in statement.targets:
                    if isinstance(target, ast.Name):
                        if target.id == "api":
                            return True
        return False

    def run(self) -> Generator[Tuple[int, int, str, Type[Any]], None, None]:
        # Check if this is looks like a contract file
        if self._is_contract_file():
            # Checks for CTR001
            datetime_visitor = DatetimeVistor()
            datetime_visitor.visit(self.tree)
            for line, col, msg in datetime_visitor.violations:
                yield line, col, msg, type(self)

            # Checks for CTR002
            list_metadata_visitor = ListMetadataVisitor(self.tree)
            list_metadata_visitor.visit(self.tree)
            for line, col, msg in list_metadata_visitor.violations:
                yield line, col, msg, type(self)
