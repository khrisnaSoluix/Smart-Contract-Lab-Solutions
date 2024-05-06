# standard libs
import ast

from linters.flake8.common import (
    HOOK_V3_TYPEHINT_MAPPING,
    HOOK_V4_TEMPLATE_TYPEHINT_MAPPING,
    HOOK_V4_TYPEHINT_MAPPING,
    SUPERVISOR_HOOK_V3_TYPEHINT_MAPPING,
    SUPERVISOR_HOOK_V4_TEMPLATE_TYPEHINT_MAPPING,
    SUPERVISOR_HOOK_V4_TYPEHINT_MAPPING,
    ErrorType,
)

ERRORS_CTR003 = "CTR003 Typehints should be used"
ERRORS_CTR004 = f"{ERRORS_CTR003[:5]}4{ERRORS_CTR003[6:]}"


class TypehintVisitor(ast.NodeVisitor):
    """
    Raise an error if typehints are missing
    """

    def __init__(
        self,
        contract_version: str,
        is_supervisor: bool,
        is_template: bool,
        is_feature: bool,
    ):
        self.is_supervisor = is_supervisor
        self.is_template = is_template
        self.is_feature = is_feature

        self.version = contract_version

        self.violations: list[ErrorType] = []

        # set mapping
        if self.version == "3":
            self.hook_mapping = HOOK_V3_TYPEHINT_MAPPING
            self.supervisor_mapping = SUPERVISOR_HOOK_V3_TYPEHINT_MAPPING
        else:
            self.hook_mapping = (
                HOOK_V4_TEMPLATE_TYPEHINT_MAPPING if self.is_template else HOOK_V4_TYPEHINT_MAPPING
            )
            self.supervisor_mapping = (
                SUPERVISOR_HOOK_V4_TEMPLATE_TYPEHINT_MAPPING
                if self.is_template
                else SUPERVISOR_HOOK_V4_TYPEHINT_MAPPING
            )

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._generate_errors(node, self.hook_mapping, self.supervisor_mapping)
        self.generic_visit(node)

    def _generate_errors(
        self, node: ast.FunctionDef, hook_mapping: dict, supervisor_mapping: dict
    ) -> None:
        # TODO: can we automate the generation of hook typehints?
        # Ensure that hook typehints are correct for smart contracts
        if node.name in hook_mapping and not self.is_supervisor:
            self._raise_hook_errors(node, hook_mapping)

        # Ensure that hook typehints are correct for supervisor contracts
        elif node.name in supervisor_mapping and self.is_supervisor:
            self._raise_hook_errors(node, supervisor_mapping)

        # Ensure that helper function typehints are provided
        else:
            all_args = node.args.args + node.args.kwonlyargs + node.args.posonlyargs
            error = f"{ERRORS_CTR004} for helper methods"
            for arg in all_args:
                if not arg.annotation:
                    # only template/features allow for vault typehinting
                    if self.is_template or self.is_feature:
                        self.violations.append((node.lineno, arg.col_offset, error))
                    else:
                        # vault not in arg.arg is a loose check as some helpers in supervisors
                        # use the parameter 'supervisee_vault' or something similar
                        if "vault" not in arg.arg:
                            self.violations.append((node.lineno, arg.col_offset, error))

            if node.returns is None:
                return_error = f"{error} - please include return type"
                self.violations.append((node.lineno, node.col_offset, return_error))

    def _raise_hook_errors(self, node: ast.FunctionDef, mapping: dict) -> None:
        argument_types, return_type = mapping[node.name]
        error = f"{ERRORS_CTR003} for hooks"

        if not self._args_equal(argument_types, node.args.args):
            arg_error = f"{error} - arguments should be '{argument_types}'"
            offset = 0 if len(node.args.args) == 0 else node.args.args[0].col_offset
            self.violations.append((node.lineno, offset, arg_error))

        actual_return = "" if node.returns is None else ast.unparse(node.returns)
        if return_type != actual_return:
            return_error = f"{error} - return type should be '{return_type}'"
            self.violations.append((node.lineno, node.col_offset, return_error))

    @staticmethod
    def _args_equal(expected: str, actual: list[ast.arg]) -> bool:
        actual_str = ", ".join([ast.unparse(a) for a in actual])
        return expected == actual_str
