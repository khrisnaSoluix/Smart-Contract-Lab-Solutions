# standard libs
import ast

from linters.flake8.common import (
    HOOK_V3_TYPEHINT_MAPPING,
    HOOK_V4_TYPEHINT_MAPPING,
    SUPERVISOR_HOOK_V3_TYPEHINT_MAPPING,
    SUPERVISOR_HOOK_V4_TYPEHINT_MAPPING,
    ErrorType,
)

ERRORS_CTR005 = "CTR005 do not add empty hooks to contracts"


class EmptyHookVisitor(ast.NodeVisitor):
    """
    Raise an error if empty hooks are added to a contract/supervisor contract
    """

    def __init__(
        self,
        contract_version: str,
        is_supervisor: bool,
        is_template: bool,
        is_feature: bool,
        filepath: str,
    ):
        self.is_supervisor = is_supervisor
        self.is_template = is_template
        self.is_feature = is_feature

        # need to include feature files in linting
        if is_feature and "/v3/" in filepath:
            self.version = "3"
        elif is_feature and "/v4/" in filepath:
            self.version = "4"
        else:
            self.version = contract_version

        self.violations: list[ErrorType] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # we could optimise and return early for non-contracts/supervisors
        hook_mapping = HOOK_V3_TYPEHINT_MAPPING if self.version == "3" else HOOK_V4_TYPEHINT_MAPPING
        supervisor_mapping = (
            SUPERVISOR_HOOK_V3_TYPEHINT_MAPPING
            if self.version == "3"
            else SUPERVISOR_HOOK_V4_TYPEHINT_MAPPING
        )
        self._generate_errors(node, hook_mapping, supervisor_mapping)
        self.generic_visit(node)

    def _generate_errors(
        self, node: ast.FunctionDef, hook_mapping: dict, supervisor_mapping: dict
    ) -> None:
        # Ensure that neither contract nor supervisors hooks are empty
        if node.name in hook_mapping and not self.is_supervisor:
            self._raise_hook_errors(node)
        elif node.name in supervisor_mapping and self.is_supervisor:
            self._raise_hook_errors(node)

    def _raise_hook_errors(self, node: ast.FunctionDef) -> None:
        error = ERRORS_CTR005
        if len(node.body) == 1 and (
            isinstance(node.body[0], ast.Pass) or self._is_empty_return(node.body[0])
        ):
            self.violations.append((node.lineno, 0, error))

    def _is_empty_return(self, node: ast.stmt):
        if isinstance(node, ast.Return):
            if isinstance(node.value, ast.Call):
                # this could potentially be expanded to check that the args/keyword args aren't
                # None/empty containers
                return len(node.value.args) == 0 and len(node.value.keywords) == 0
            return node.value is None

        return False
