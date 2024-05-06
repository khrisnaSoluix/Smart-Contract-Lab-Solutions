# standard libs
import ast
from typing import Any, Generator, Type

from linters.flake8.datetime_visitor import DatetimeVisitor
from linters.flake8.empty_hook_visitor import EmptyHookVisitor
from linters.flake8.get_parameter_visitor import GetParameterVisitor
from linters.flake8.list_metadata_visitor import ListMetadataVisitor
from linters.flake8.parameter_display_name_visitor import ParameterDisplayNameVisitor
from linters.flake8.parameter_name_visitor import ParameterNameVisitor
from linters.flake8.pid_visitor import PidVisitor
from linters.flake8.typehint_visitor import TypehintVisitor

__version__ = "1.0"


class ContractLinter(object):
    name = "flake8_contracts"
    version = __version__

    def __init__(self, tree, filename=""):
        self.tree: ast.Module = tree
        self.filename: str = filename
        self._contract_version = ""

    def _is_contract_file(self):
        # For now we will just identify contracts and modules via the `api` metadata. It's not
        # perfect, but it's the only thing in common across the different types
        for statement in self.tree.body:
            # setting metadata results in top-level Assign objects, whose targets should have
            # the name(s) we expect
            if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Constant):
                for target in statement.targets:
                    if isinstance(target, ast.Name):
                        if target.id == "api":
                            # contract version == 3/4
                            self._contract_version = statement.value.value[0]
                            return True
        return False

    def _is_feature_file(self):
        if "library/features" in self.filename and "/test" not in self.filename:
            if "/v3/" in self.filename:
                self._contract_version = "3"
            elif "/v4/" in self.filename:
                self._contract_version = "4"
            return True
        return False

    def _is_supervisor_file(self):
        # For now we will just identify supervisor contracts `supervised_smart_contracts` metadata.
        # It's not perfect, but it's the only thing in common across the different types.
        # From 3.10+ this is an optional item of metadata
        # TODO: figure out a new method of checking it's a supervisor
        contract_version = ""
        for statement in self.tree.body:
            if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Constant):
                for target in statement.targets:
                    if isinstance(target, ast.Name) and target.id == "api":
                        # TODO: this only works if api is defined above supervised_smart_contracts
                        contract_version = statement.value.value[0]
            # setting metadata results in top-level Assign objects, whose targets should have
            # the name(s) we expect
            if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.List):
                for target in statement.targets:
                    if isinstance(target, ast.Name):
                        if target.id == "supervised_smart_contracts":
                            self._contract_version = contract_version
                            return True
        return False

    def _is_template_file(self):
        # we are only developing V4 contracts with FLC
        if self._contract_version == "4":
            return True
        for statement in self.tree.body:
            # template files must be stored under the /template dir
            # if imports are included, this is a template file and vault typehints can be used
            if "/template/" in self.filename and (
                isinstance(statement, ast.Import) or isinstance(statement, ast.ImportFrom)
            ):
                return True
        return False

    def run(self) -> Generator[tuple[int, int, str, Type[Any]], None, None]:
        # Check if this is looks like a contract file
        if self._is_contract_file() or self._is_feature_file():
            # Checks for CTR001
            datetime_visitor = DatetimeVisitor()
            datetime_visitor.visit(self.tree)
            for line, col, msg in datetime_visitor.violations:
                yield line, col, msg, type(self)

            # Checks for CTR002
            list_metadata_visitor = ListMetadataVisitor(
                self.tree, contract_version=self._contract_version
            )
            list_metadata_visitor.visit(self.tree)
            for line, col, msg in list_metadata_visitor.violations:
                yield line, col, msg, type(self)

            # Checks for CTR003-4
            typehint_visitor = TypehintVisitor(
                contract_version=self._contract_version,
                is_supervisor=self._is_supervisor_file(),
                is_template=self._is_template_file(),
                is_feature=self._is_feature_file(),
            )
            typehint_visitor.visit(self.tree)
            for line, col, msg in typehint_visitor.violations:
                yield line, col, msg, type(self)

            # Checks for CTR005
            empty_hook_visitor = EmptyHookVisitor(
                contract_version=self._contract_version,
                is_supervisor=self._is_supervisor_file(),
                is_template=self._is_template_file(),
                is_feature=self._is_feature_file(),
                filepath=self.filename,
            )
            empty_hook_visitor.visit(self.tree)
            for line, col, msg in empty_hook_visitor.violations:
                yield line, col, msg, type(self)

            # Checks for CTR006
            if (
                self._contract_version == "4"
                and self._is_contract_file()
                and not self._is_supervisor_file()
            ):
                get_parameter_visitor = GetParameterVisitor()
                get_parameter_visitor.visit(self.tree)
                for line, col, msg in get_parameter_visitor.violations:
                    yield line, col, msg, type(self)

            # Checks for CTR007
            if self._contract_version == "4":
                parameter_name_visitor = ParameterNameVisitor()
                parameter_name_visitor.visit(self.tree)
                for line, col, msg in parameter_name_visitor.violations:
                    yield line, col, msg, type(self)

            # Checks for CTR008
            parameter_display_name_visitor = ParameterDisplayNameVisitor()
            parameter_display_name_visitor.visit(self.tree)
            for line, col, msg in parameter_display_name_visitor.violations:
                yield line, col, msg, type(self)

            # Checks for CTR009
            pid_visitor = PidVisitor()
            pid_visitor.visit(self.tree)
            for line, col, msg in pid_visitor.violations:
                yield line, col, msg, type(self)
