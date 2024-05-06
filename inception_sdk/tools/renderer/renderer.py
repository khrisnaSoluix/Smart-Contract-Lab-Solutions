# standard libs
import ast
import inspect
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

# contracts api
from contracts_api.versions.version_400.common.types.natives import ALLOWED_NATIVES

# inception sdk
from inception_sdk.common.python import ast_utils
from inception_sdk.tools.common.git_utils import (
    get_relative_filepath as get_relative_filepath_from_repo,
    get_validated_commit_hash_for_file_checksum,
    load_repo,
)
from inception_sdk.tools.common.tools_utils import (
    get_file_checksum,
    get_relative_filepath_from_cwd,
    override_logging_level,
    path_import,
)
from inception_sdk.tools.renderer.render_utils import (
    ImportedModule,
    ImportedObject,
    NativeModule,
    RenderException,
    clear_node_location_metadata,
    combine_module_and_object_name,
    get_module_dirname,
    get_module_filename,
    get_stmt_attribute_data,
    get_unreferenced_objects,
    module_header_stmts,
    recursive_topological_sort,
    remove_quotes_from_module_headers,
    remove_remaining_headers,
    reorder_nodes,
)
from inception_sdk.vault.contracts.extensions.contracts_api_extensions.vault_types import (
    SmartContractVault,
    SuperviseeContractVault,
    SupervisorContractVault,
)
from inception_sdk.vault.contracts.utils import is_module_in_contracts_language_v4

# third-party library
with override_logging_level(logging.WARNING):
    # third party
    from black import format_str
    from black.mode import Mode


log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

__version__ = "3.0.0"


# Used for reordering of nodes in the rendered contract
# Note that some metadata fields are omitted below (e.g. event_types), this is because they're
# usually constructed with various assignment objects (constants, feature-level assignments)
# which must be defined within the contract beforehand,
# (e.g. event_types = [*event_types_debt_management, *event_types_interest_accrual]), therefore the
# omitted metadata fields "event_types", "event_types_groups", "data_fetchers", "notification",
TOP_LEVEL_METADATA_FIELDS = [
    "api",
    "version",
    "display_name",
    "summary",
    "explanation",
    "tside",
    "supervised_smart_contracts",
    "supported_denominations",
    "events_timezone",
    "contract_module_imports",
    "global_parameters",
]

CONTRACT_METADATA_FIELDS = [
    *TOP_LEVEL_METADATA_FIELDS,
    "data_fetchers",
    "event_types_groups",
    "event_types",
    "notification_types",
    "parameters",
]


HOOKS = [
    "activation_hook",
    "conversion_hook",
    "deactivation_hook",
    "derived_parameter_hook",
    "post_parameter_change_hook",
    "post_posting_hook",
    "pre_parameter_change_hook",
    "pre_posting_hook",
    "scheduled_event_hook",
]
# this should match the string defined in allowed_natives for modules that must be imported
# directly, see "math"
ALL_REQUIRED = "all_required"
CONTRACTS_API = "contracts_api"
CONTRACTS_API_EXTENSIONS = "inception_sdk.vault.contracts.extensions.contracts_api_extensions"


VAULT_TYPES = [
    SmartContractVault.__name__,
    SuperviseeContractVault.__name__,
    SupervisorContractVault.__name__,
]


@dataclass
class RendererConfig:
    autogen_warning: str = (
        f"# Code auto-generated using Inception Smart Contract Renderer Version {__version__}\n"
    )
    hashing_algorithm: str = "md5"
    include_autogen_warning: bool = True
    module_header_prefix: str = "Objects below have been imported from"
    output_filepath: str | None = None
    git_repo_root: os.PathLike | None = None
    use_git: bool = False
    use_full_filepath_in_headers: bool = False
    render_metadata_at_top_of_file: bool = True
    apply_formatting: bool = True

    # NOTE: Assignment definitions included here must have no dependencies (metadata)
    # E.g. "api" must be a literal and not reference another object as dependencies are not
    # reordered
    sc_order: list[str] = field(init=False)

    # Allowed modules and natives that can be imported. Since everything from contracts_api is
    # allowed we initialise as empty list and it is treated differently in logic
    whitelisted_modules: dict[str, list[str]] = field(
        default_factory=lambda: {
            CONTRACTS_API: [],
            **{package: list(objects) for package, objects in ALLOWED_NATIVES.items()},
        }
    )

    def __post_init__(self):
        # done in post init due to dependency on whitelisted modules
        self.sc_order = [*self.whitelisted_modules, *TOP_LEVEL_METADATA_FIELDS, *HOOKS]


class SmartContractRenderer:
    """
    Render a Smart Contract by traversing the import statements from the provided module
    and combining them to form one single file containing namespaced object definitions.
    """

    def __init__(
        self,
        module_to_render: ModuleType,
        renderer_config: RendererConfig = RendererConfig(),
    ) -> None:
        self.root_module: ModuleType = module_to_render
        self.root_tree: ast.Module = ast.parse(inspect.getsource(self.root_module))

        if not is_module_in_contracts_language_v4(self.root_tree):
            raise ValueError(
                "The renderer only supports CLv4 contracts from Product Library Release 21 / "
                "SDK 1.4.0 onwards. Please use a version from an earlier release for CLv3 contracts"
            )

        self.config = renderer_config
        if renderer_config.use_git:
            self.git_repo = load_repo(renderer_config.git_repo_root)
        else:
            log.info("use_git not set to True - git info will be excluded from renderer output")

        self.header_identifier = "<IMPORTED_MODULE_HEADER>"
        self.modules_visited: set[ModuleType] = set()

        # Tracks whether a vault typehint has been replaced by the renderer
        self.vault_type_hint_replaced: bool = False

        # used to deduplicate imports across templates and features
        # E.g. template: from typing import Optional, Union
        # and from datetime import datetime
        # module_1: from typing import Any, Union
        # {
        #     "datetime": ImportedObject(
        #         ast.names=[datetime]
        #     ),
        #     "typing":  ImportedObject(
        #         ast.names=[Optional, Union, Any]
        #     )
        # }
        self.allowed_natives_imported: dict[str, NativeModule] = dict()

        # tracks each module's imported modules
        # E.g.template imports module1 and module2 :
        # {
        #     "template": ["module1", "module2"],
        #     "module1": ["utils1", "module2"],
        # }
        self.module_import_mapping: dict[ModuleType, list[ImportedModule]] = {}

        # tracks each module's imported objects
        # E.g. module1 contains definitions for "get_a", "a", "get_b", "b":
        # {
        #     "module1": ["get_a", "a", "get_b", "b"],
        #     "utils1": ["capitalise", "get_interest", "DEFAULT_DATE"],
        # }
        self.module_object_definitions: dict[ModuleType, list[ImportedObject]] = {}

        # tracks statements from features that will need adding to the rendered contract
        self.stmts_to_append: list[ast.stmt] = []

        # tracks all the objects to import into the final rendered contract
        self.objects_to_import: list[ImportedObject] = []

    def render(self, write_to_file: bool = True) -> None:
        ObjectDiscovery(self).visit(self.root_tree)
        self._add_any_typing_import()
        self._rename_imported_module_references()
        self._rename_imported_object_definitions()
        self._sort_imported_object_definitions()
        self._remove_unused_objects()
        self._add_imported_stmts_to_root_tree()
        if self.config.render_metadata_at_top_of_file:
            self.root_tree.body, order_changed = reorder_nodes(
                self.root_tree.body, self.config.sc_order
            )

            if order_changed:
                # Add root module header for template objects at the top of the tree
                self._add_root_module_header_to_tree()
                self.root_tree.body = remove_remaining_headers(
                    self.root_tree.body, self.config.module_header_prefix
                )

        self._replace_decorator_constants()
        # We use multiple NodeTransformers that introduce new nodes and invalidate location info
        ast.fix_missing_locations(self.root_tree)
        self.rendered_contract = ast.unparse(self.root_tree)
        self.rendered_contract = remove_quotes_from_module_headers(
            self.rendered_contract, self.header_identifier
        )
        if self.config.include_autogen_warning:
            self.rendered_contract = "\n".join(
                [self.config.autogen_warning, self.rendered_contract]
            )

        if self.config.apply_formatting:
            self.rendered_contract = format_str(self.rendered_contract, mode=Mode(line_length=100))

        if write_to_file:
            self._write_smart_contract_to_file()

    def _append_stmt(self, stmt: ast.stmt, unique: bool = True):
        """
        Adds statements to the final list, removing duplicates as required
        """
        clear_node_location_metadata(stmt)
        for stored_node in self.stmts_to_append:
            if unique and ast_utils.compare_ast(stmt, stored_node):
                return
        self.stmts_to_append.append(stmt)

    def _append_stmts(self, stmts: list[ast.stmt], unique: bool = True):
        for stmt in stmts:
            self._append_stmt(stmt, unique)

    def _rename_imported_module_references(self):
        """
        For each imported module, rename any references to their namespaced equivalent.
        E.g, if our template imports module_1 then:
        attribute_1 = module_1.attribute_2
        Becomes:
        attribute_1 = module_1_attribute_2
        """
        for module, imported_modules in self.module_import_mapping.items():
            if module == self.root_module:
                for stmt in self.root_tree.body:
                    RenameReferenceTransformer(imported_modules).visit(stmt)
            else:
                for object_def in self.module_object_definitions.get(module, []):
                    RenameReferenceTransformer(imported_modules).visit(object_def.stmt)

    def _rename_imported_object_definitions(self):
        """
        For each object to import, rename the definition to its namespaced equivalent.
        E.g:
        (From module_1)
        attribute_1 = "test"
        Becomes:
        module_1_attribute_1 = "test"
        """
        for imported_objs in self.module_object_definitions.values():
            for obj in imported_objs:
                RenameDefinitionTransformer(imported_objs).visit(obj.stmt)

    def _remove_unused_objects(self):
        """
        Build a map of all references to imported objects made by every object declared in the root
        template and all other imported objects. Use this map to then find and remove unreferenced
        objects. Refer to `get_unreferenced_objects` function for an example reference map.
        """
        imported_obj_references = defaultdict(set, {o: set() for o in self.objects_to_import})
        imported_obj_by_module = {
            (o.namespaced_name, o.module_from): o for o in self.objects_to_import
        }

        # Get all references made by imported objects to other imported objects
        for current_obj in self.objects_to_import:
            iov = ImportedObjectsVisitor(imported_obj_by_module)
            iov.visit(current_obj.stmt)
            for referenced_obj in [obj for obj in iov.objects_referenced if obj != current_obj]:
                imported_obj_references[referenced_obj].add(current_obj)

        # Get all references made by objects in the root template to imported objects
        for template_obj in self.root_tree.body:
            template_obj_name = get_stmt_attribute_data(template_obj)
            if template_obj_name is None:
                continue
            iov = ImportedObjectsVisitor(imported_obj_by_module)
            iov.visit(template_obj)
            for obj in iov.objects_referenced:
                imported_obj_references[obj].add(template_obj_name)

        objs_not_referenced = get_unreferenced_objects(imported_obj_references)
        for unreferenced_objects in objs_not_referenced:
            self.objects_to_import.remove(unreferenced_objects)

    def _sort_imported_object_definitions(self):
        """
        The object definitions need to be in dependency order to ensure that the rendered output is
        valid. E.g. referencing a function that isn't yet defined is invalid, so imported objects
        should be ordered before their uses.
        """

        # Convert current dependency mapping from dict[ModuleType, list[ImportedModule]] to
        # dict[ModuleType, list[ModuleType]] where both keys and values are ordered to ensure the
        # topological sort is deterministic
        module_dependency_graph = {
            k: [m.module for m in sorted(v, key=lambda x: x.module.__name__)]
            for k, v in sorted(
                self.module_import_mapping.items(),
                key=lambda x: x[0].__name__,
            )
        }
        # Order the dependency graph
        sorted_dependencies = recursive_topological_sort(module_dependency_graph, self.root_module)
        # Don't need to store template module objects as they are already in self.root_tree
        sorted_dependencies.remove(self.root_module)
        for dependency in sorted_dependencies:
            self.objects_to_import.extend(self.module_object_definitions[dependency])

    def _get_module_filename_headers(self, module: ModuleType) -> list[str]:
        if self.config.use_full_filepath_in_headers:
            if self.config.use_git:
                module_filename = get_relative_filepath_from_repo(
                    str(module.__file__), self.git_repo
                )
            else:
                module_filename = get_relative_filepath_from_cwd(str(module.__file__))
        else:
            module_filename = get_module_filename(module)
        return [f"# {self.config.module_header_prefix}:", f"#    {module_filename}"]

    def _get_module_hashes_header(self, module: ModuleType) -> str:
        file_checksum = get_file_checksum(str(module.__file__), self.config.hashing_algorithm)
        hashes_header = f"# {self.config.hashing_algorithm}:{file_checksum}"
        if self.config.use_git:
            git_commit = get_validated_commit_hash_for_file_checksum(
                filepath=str(module.__file__),
                checksum=file_checksum,
                repo=self.git_repo,
                hashing_algorithm=self.config.hashing_algorithm,
            )
            hashes_header += f" git:{git_commit}"

        return hashes_header

    def _prepend_header_identifier(self, headers: list[str]) -> list[str]:
        return [self.header_identifier + header for header in headers]

    def _get_module_headers(self, module: ModuleType) -> list[str]:
        headers = [
            *self._get_module_filename_headers(module),
            self._get_module_hashes_header(module),
        ]
        return self._prepend_header_identifier(headers)

    def _get_header_stmts_for_module(self, module: ModuleType) -> list[ast.stmt]:
        module_headers = self._get_module_headers(module)
        header_stmts = module_header_stmts(module_headers)
        return header_stmts

    def _add_root_module_header_to_tree(self) -> None:
        root_header_nodes = self._get_header_stmts_for_module(self.root_module)
        root_header_nodes.reverse()
        for root_header_node in root_header_nodes:
            self.root_tree.body.insert(0, root_header_node)

    def _append_module_header_stmts(self, module: ModuleType) -> None:
        header_stmts = self._get_header_stmts_for_module(module)
        self._append_stmts(header_stmts, unique=False)

    def _add_imported_stmts_to_root_tree(self) -> None:
        """
        Inserts AST stmts of all imported objects into the root_tree, appending headers if required.
        """
        current_module = None
        for obj in self.objects_to_import:
            if not current_module or obj.module_from != current_module:
                current_module = obj.module_from
                self._append_module_header_stmts(current_module)
            self._append_stmt(obj.stmt)

        self._add_root_module_header_to_tree()
        for native_import in self.allowed_natives_imported.values():
            self._append_stmt(native_import.import_stmt)
        self.root_tree.body = self.stmts_to_append + self.root_tree.body

    def _add_any_typing_import(self) -> None:
        """
        Adds a typing.Any import to contracts if missing. The various Vault type hints we use as
        development aids are replaced with Any during rendering, so if a
        template does not already import typing.Any for other purposes it will not be valid python
        """
        if self.vault_type_hint_replaced:
            if typing_import := self.allowed_natives_imported.get("typing"):
                # Support for importing Any as <xyz>  is deemed unnecessary
                is_any_imported = any(
                    alias.name == "Any" for alias in typing_import.import_stmt.names
                )
                if not is_any_imported:
                    typing_import.import_stmt.names.append(ast.alias(name="Any"))
            else:
                typing_importfrom = ast.ImportFrom(
                    module="typing",
                    names=[ast.alias(name="Any")],
                    # 0 means an absolute import
                    level=0,
                )
                self.allowed_natives_imported["typing"] = NativeModule(
                    name="typing", import_stmt=typing_importfrom, namespaced_name="typing"
                )

    def _replace_decorator_constants(self) -> None:
        """
        Replaces Constant references in decorators with the actual value.
        """

        ReplaceDecoratorConstantsTransformer(self.root_tree).visit(self.root_tree)

    def _write_smart_contract_to_file(self) -> None:
        if not self.config.output_filepath:
            file_suffix = "_rendered.py"
            template_name = self.root_module.__name__.split(".")[-1]
            self.config.output_filepath = template_name + file_suffix
        with open(self.config.output_filepath, "w+") as file:
            log.info(f"Writing rendered output to '{self.config.output_filepath}'")
            file.write(self.rendered_contract)


class ImportedObjectsVisitor(ast.NodeVisitor):
    """
    This NodeVisitor is used to build a set of imported objects that have been referenced by any
    other objects in the template. It does this by comparing the name/ID of the Name/FunctionDef
    nodes (which have been replaced by their namespace equivalent) with the list of imported
    objects. To ensure the exact object is found (and not just one with the same namespaced name but
    different module) it is compared to the custom references stored on the node by the renderer
    (imported_object_ref and from_module).

    It is common with large contracts that there are multiple objects with the same namespaced name
    imported from different modules. An example of this is `addresses_DEFAULT` where multiple
    modules named `addresses.py` define a `DEFAULT` object.
    """

    def __init__(
        self,
        imported_objects_by_module: dict[tuple[str, ModuleType], ImportedObject],
    ) -> None:
        self.objects_referenced: set[ImportedObject] = set()
        self.imported_objects_by_module = imported_objects_by_module
        super().__init__()

    def visit_Name(self, node: ast.Name):
        # these two attributes are custom and added by the renderer to the nodes
        if imported_object_ref := getattr(node, "imported_object_ref", None):
            self.objects_referenced.add(imported_object_ref)
        elif from_module := getattr(node, "from_module", None):
            if (node.id, from_module) in self.imported_objects_by_module:
                self.objects_referenced.add(self.imported_objects_by_module[(node.id, from_module)])

        return self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # these two attributes are custom and added by the renderer to the nodes
        if imported_object_ref := getattr(node, "imported_object_ref", None):
            self.objects_referenced.add(imported_object_ref)
        elif from_module := getattr(node, "from_module", None):
            if (node.name, from_module) in self.imported_objects_by_module:
                self.objects_referenced.add(
                    self.imported_objects_by_module[(node.name, from_module)]
                )

        return self.generic_visit(node)


class RenameDefinitionTransformer(ast.NodeTransformer):
    """
    This NodeTransformer is responsible for renaming (namespacing) the object definitions (functions
    and variable assignments)
    """

    def __init__(
        self, imported_objects: list[ImportedObject], is_root_module: bool = False
    ) -> None:
        self.imported_objs_by_name = {obj.name: obj for obj in imported_objects}
        self.is_root_module = is_root_module
        super().__init__()

    def visit_Name(self, node: ast.Name):
        """
        If Node ctx is ast.Store() it means the Name node is on the LHS of an assignment, so only
        rename if the module we are walking is not the root template module.
        """
        if self.is_root_module and isinstance(node.ctx, ast.Store):
            return self.generic_visit(node)
        elif node.id in self.imported_objs_by_name:
            # as we're arbitrarily adding a new attribute type hinting fails
            # this may need revisiting (e.g. just store in a separate data structure)
            node.imported_object_ref = self.imported_objs_by_name[node.id]  # type: ignore
            node.id = self.imported_objs_by_name[node.id].namespaced_name
        return self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """
        Only rename functions that are outside the root template module.
        """
        if not self.is_root_module and node.name in self.imported_objs_by_name:
            # as we're arbitrarily adding a new attribute type hinting fails
            # this may need revisiting (e.g. just store in a separate data structure)
            node.imported_object_ref = self.imported_objs_by_name[node.name]  # type: ignore
            node.name = self.imported_objs_by_name[node.name].namespaced_name
        return self.generic_visit(node)


class RenameReferenceTransformer(ast.NodeTransformer):
    """
    This NodeTransformer is responsible for renaming any references to imported objects to their
    namespaced name
    """

    def __init__(
        self,
        imported_modules: list[ImportedModule],
    ) -> None:
        self.imported_modules = imported_modules
        super().__init__()

    def _rename_child_attribute_node(self, child_node: ast.Attribute) -> ast.Name | ast.Attribute:
        """
        Flatten attribute calls from imported_modules to single Name nodes.
        E.g:
        module_1.attribute_1 returns module_1_attribute_1
        module_1.attribute_1.attribute_2 returns module_1_attribute_1.attribute_2
        """
        if isinstance(child_node.value, ast.Attribute):
            child_node.value = self._rename_child_attribute_node(child_node.value)
        elif isinstance(child_node.value, ast.Name):
            import_match = [i for i in self.imported_modules if i.get_name() == child_node.value.id]
            if len(import_match) > 1:
                raise RenderException(
                    "Found ambiguous reference to an imported module. Multiple "
                    f"matches of {child_node.value.id} found in {self.imported_modules}"
                )
            if import_match:
                namespaced_id = combine_module_and_object_name(
                    import_match[0].module.__name__, child_node.attr
                )
                # we're arbitrarily adding a new attribute
                # this may need revisiting (e.g. just store in a separate data structure)
                return ast.Name(
                    ctx=ast.Load(), id=namespaced_id, from_module=import_match[0].module
                )
        return child_node

    def visit_Attribute(self, node: ast.Attribute):
        """
        Rename all attribute assignments that reference any imported modules (including aliases).
        E.g:
        import accrual_utils as au
        postings = au.calculate_accruals()

        Should output:
        postings = accrual_utils_calculate_accruals()
        """
        return self.generic_visit(self._rename_child_attribute_node(node))


class ReplaceDecoratorConstantsTransformer(ast.NodeTransformer):
    """
    This NodeTransformer is responsible for replacing constants in requires / fetch_account_data
    decorators with their actual value.

    Decorators cannot parse constants/variables:
    e.g.
        MONTHLY = 'MONTHLY_SAVINGS_GOAL'
        @requires(event_type=MONTHLY, parameters=True, balances='1 day')
        def scheduled_code(event_type, effective_date):
    would raise the error:
    `IllegalPython: scheduled_code @requires must have an "event_type" keyword with a string value`

    This transformer replaces the constant/variable with the actual value so that the rendered
    contract is a valid contract.
    """

    def __init__(self, tree) -> None:
        self.tree = tree
        # mapping of constants name to ast.Constant object
        # used for replacing constant references to the constant value in decorators
        self._constants: dict[str, ast.Constant] = {}
        # mapping of Assign variable name which are assigned to other variables
        # used to track chained assignments which might need to be added to _constants
        self._chained_assign: dict[str, str] = {}
        # mapping of constant names to ast.List object
        # used to track list assignments for list unpacking in decorators
        self._list_assigns: dict[str, ast.List] = {}
        super().__init__()

    def visit_Module(self, node: ast.Module):
        """
        Find eligible variables to be replaced in decorators
        and store the Name.id -> value mapping in self._constants for later use

        Visiting the top-level module immediately after rendering allow us to
        pre-populate `self._constants` with all the values needed
        """
        assigns = (x for x in node.body if type(x) is ast.Assign)

        for assign in assigns:
            # if assignment is to a Constant-type object, we store this in `_constants``
            # e.g. interest_accrual_common_ACCRUAL_EVENT = "ACCRUE_INTEREST"
            if type(assign.value) is ast.Constant:
                for name in assign.targets:
                    if isinstance(name, ast.Name) and name.id not in CONTRACT_METADATA_FIELDS:
                        # if the Constant is assigned to a variable name that is not
                        # one of the protected metadata variables, add it to the
                        # `_constants` mapping of name.id to value
                        self._constants[name.id] = assign.value

            # if assignment is to a Name-type object, this is a chained definition
            # e.g. interest_accrual_ACCRUAL_EVENT = interest_accrual_common_ACCRUAL_EVENT
            # we store this is `_chained_assign``
            elif type(assign.value) is ast.Name:
                for name in assign.targets:
                    if isinstance(name, ast.Name) and name.id not in CONTRACT_METADATA_FIELDS:
                        # update `_chained_assign` with a mapping of variable name (str) to
                        # assigned variable (str)
                        self._chained_assign[name.id] = assign.value.id

            elif type(assign.value) is ast.List:
                for name in assign.targets:
                    if isinstance(name, ast.Name) and name.id not in CONTRACT_METADATA_FIELDS:
                        # update `_list_assigns` with a mapping of variable name (str) to
                        # assigned variable (list)
                        self._list_assigns[name.id] = assign.value

        for chained_assign, chained_variable_name in self._chained_assign.items():
            # chained assign example:
            # interest_accrual_common_ACCRUAL_EVENT = "ACCRUE_INTEREST"
            # interest_accrual_ACCRUAL_EVENT = interest_accrual_common_ACCRUAL_EVENT
            """
            ! Note that:
            (1) renderer ordering, i.e. template contents ordered last
            (2) python requiring variables to be bound, i.e. x = y implies y must be defined
                before x's assignment
            (3) AST trees are ordered and hence will preserve contract ordering in (1) and (2)
            We do not need to iterate over `_chained_assign` more than once as the necessary
            values will have already be updated in `_constants` due to (1)-(3).

            see inception_sdk/tools/renderer/test/feature/test_renderer.py for an example
            (test name: test_replace_decorator_constants)
            """

            if constant_object := self._constants.get(chained_variable_name):
                self._constants[chained_assign] = constant_object
        return self.generic_visit(node)

    def visit_FunctionDef(self, func_def: ast.FunctionDef):
        """
        visit all function definitions, filtering by those which have decorators,
        and replacing the decorator keywords if appropriate
        """
        if func_def.decorator_list:
            for i, decorator in enumerate(func_def.decorator_list):
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Name)
                    and decorator.func.id in ["requires", "fetch_account_data"]
                    and decorator.keywords
                ):
                    # update the keywords with the constants
                    decorator.keywords = [
                        self._visit_decorator_keyword(k) for k in decorator.keywords
                    ]
                # update the item in decorator list with updated value
                func_def.decorator_list[i] = decorator
        return self.generic_visit(func_def)

    def _visit_decorator_keyword(self, keyword: ast.keyword) -> ast.keyword:
        """
        Contracts only allow decorators to have keywords of types:
        str, bool, list[str], dict[str[list, str]]

        Therefore, decorators with either constants or list unpacking variables need to be replaced
        """

        # KEYWORD HELPERS
        def _update_name_to_constant(name: ast.Name):
            # get either the Constant from _constants mapping or return original Name
            return self._constants.get(name.id, name)

        def _update_list_elements(lst: ast.List) -> ast.List:
            # update Name elements, return original element otherwise
            updated_lst = []
            for elt in lst.elts:
                if isinstance(elt, ast.Name):
                    updated_lst.append(_update_name_to_constant(elt))
                elif isinstance(elt, ast.Starred):
                    updated_lst.extend(_update_starred_elements(elt))
                else:
                    updated_lst.append(elt)
            lst.elts = updated_lst
            return lst

        def _update_starred_elements(strd: ast.Starred) -> list:
            # update Name elements, return original element otherwise
            els = self._list_assigns[strd.value.id].elts
            return [
                _update_name_to_constant(elt) if isinstance(elt, ast.Name) else elt for elt in els
            ]

        if isinstance(keyword.value, ast.Name):
            keyword.value = _update_name_to_constant(keyword.value)

        elif isinstance(keyword.value, ast.List):
            keyword.value = _update_list_elements(keyword.value)

        elif isinstance(keyword.value, ast.Dict):
            # transform keys
            keyword.value.keys = [
                _update_name_to_constant(key) if isinstance(key, ast.Name) else key
                for key in keyword.value.keys
            ]

            # transform values
            for i, value in enumerate(keyword.value.values):
                if isinstance(value, ast.List):
                    value = _update_list_elements(value)
                keyword.value.values[i] = value

        return keyword


class ObjectDiscovery(ast.NodeTransformer):
    """
    Contains visitor logic to analyse a python module's imports, creating the
    data structures we use later to support renderer functionality.
    """

    def __init__(
        self,
        renderer: SmartContractRenderer,
        current_module: ModuleType | None = None,
        current_root_import: ast.Import | None = None,
    ) -> None:
        self.current_module = current_module or renderer.root_module
        self.local_objects: list[ImportedObject] = []
        self.renderer = renderer
        self.current_root_import = current_root_import
        super().__init__()

    def visit_Import(self, node: ast.Import):
        if not self.current_root_import:
            self.current_root_import = node
        for alias in node.names:
            module_name = alias.name
            module_alias = alias.asname
            if module_name == CONTRACTS_API:
                statement = ast.unparse(node)
                raise RenderException(
                    f"contracts_api cannot be imported directly: \n"
                    f'   File "{self.current_module.__file__}" line {node.lineno}:\n'
                    f"\t{statement}"
                )
            else:
                if module_name in self.renderer.config.whitelisted_modules:
                    if (
                        ALL_REQUIRED in self.renderer.config.whitelisted_modules[module_name]
                        and module_alias
                    ):
                        statement = ast.unparse(node)
                        raise RenderException(
                            f"{module_name=} must be imported directly and must not be aliased:"
                            f'\n   File "{self.current_module.__file__}" line {node.lineno}:\n'
                            f"\t{statement}"
                        )
                    if module_name not in self.renderer.allowed_natives_imported:
                        self.renderer.allowed_natives_imported[module_name] = NativeModule(
                            name=module_name, import_stmt=node, namespaced_name=module_name
                        )

                    continue
                elif not alias.asname:
                    statement = ast.unparse(node)
                    raise RenderException(
                        "Import statements must include an 'as' alias "
                        f'(e.g. "import library.utils as utils"): \n'
                        f"File {self.current_module.__file__} line {node.lineno}:\n"
                        f"\t{statement}"
                    )
                else:
                    # import is either a feature or is another 3rd party/built-in being imported
                    # if it is one of the latter 2 (3rd part or built-in) and is allowed it
                    # would exist in self.renderer.config.whitelisted_modules
                    module_alias = alias.asname
                    module: ModuleType = getattr(self.current_module, module_alias)
                    if any(
                        s in get_module_dirname(module) for s in ["site-packages", "third_party"]
                    ):
                        raise RenderException(
                            f"{self.current_module.__file__} is attempting to import a "
                            f"third-party module: {module.__file__}"
                        )
                    imported_module = ImportedModule(
                        name=alias.name,
                        alias=alias.asname,
                        module=module,
                    )
                    if self.renderer.module_import_mapping.get(self.current_module):
                        if (
                            imported_module
                            not in self.renderer.module_import_mapping[self.current_module]
                        ):
                            self.renderer.module_import_mapping[self.current_module].append(
                                imported_module
                            )
                    else:
                        self.renderer.module_import_mapping.update(
                            {self.current_module: [imported_module]}
                        )
                    if module not in self.renderer.modules_visited:
                        self.renderer.modules_visited.add(module)
                        try:
                            module_ast = ast.parse(inspect.getsource(module))
                        except TypeError as te:
                            import_names = " ".join(
                                [alias.name for alias in self.current_root_import.names]
                            )
                            if "is a built-in module" in te.args[0]:
                                raise RenderException(
                                    f"import '{import_names}' (Line: "
                                    f"{self.current_root_import.lineno} "
                                    f"Col: {self.current_root_import.col_offset}) : "
                                    f"{module} is not a whitelisted module."
                                )
                            raise ImportError(
                                f"Error unable to import '{import_names}' (Line: "
                                f"{self.current_root_import.lineno} Col: "
                                f"{self.current_root_import.col_offset}) : {te}"
                            )

                        obj_discovery = ObjectDiscovery(
                            self.renderer, module, self.current_root_import
                        )
                        obj_discovery.visit(module_ast)
        self.current_root_import = None
        return None

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module_name = node.module
        aliases = node.names
        if module_name and CONTRACTS_API_EXTENSIONS in module_name:
            # we don't want these in the rendered contracts as they're not part of the API
            return None
        elif module_name in self.renderer.config.whitelisted_modules:
            if module_name != CONTRACTS_API:
                # verify objects from module are allowed to be imported
                for alias in aliases:
                    if alias.name not in self.renderer.config.whitelisted_modules[module_name]:
                        raise RenderException(
                            f"Importing {alias.name} from {module_name=} is not allowed.\n"
                            f"Module: '{self.current_module.__name__}' Line: {node.lineno}"
                        )
            else:
                # module is contracts_api so we need to check whether import * is being called
                if any(alias.name == "*" for alias in aliases):
                    raise RenderException(
                        f"Importing '*' from {module_name=} is against best practices.\n"
                        f"Module: '{self.current_module.__name__}' Line: {node.lineno}"
                    )

            # all objects being imported from module are allowed
            if module_name not in self.renderer.allowed_natives_imported:
                self.renderer.allowed_natives_imported[module_name] = NativeModule(
                    name=module_name, import_stmt=node, namespaced_name=module_name
                )
            else:
                alias_names_already_imported = self.renderer.allowed_natives_imported[
                    module_name
                ].import_stmt.names

                for alias in aliases:
                    add_alias = True
                    for existing_alias in alias_names_already_imported:
                        if existing_alias.name == alias.name:
                            add_alias = False
                            break
                    if add_alias:
                        self.renderer.allowed_natives_imported[
                            module_name
                        ].import_stmt.names.append(alias)
        else:
            raise RenderException(
                f"`from <x> import <y>` syntax is only available for native python modules "
                f"exposed by the Contracts API. `{module_name}` is not such a module. "
                f"Use `import <x.y> as y` syntax instead.\n"
                f"Module: '{self.current_module.__name__}' Line: {node.lineno}"
            )

    def _update_module_object_definitions(self, object_definition: ImportedObject):
        if self.renderer.module_object_definitions.get(self.current_module):
            if (
                object_definition
                not in self.renderer.module_object_definitions[self.current_module]
            ):
                self.renderer.module_object_definitions[self.current_module].append(
                    object_definition
                )
            else:
                log.warning(f"Duplicate in {self.current_module} {object_definition=}")
        else:
            self.renderer.module_object_definitions.update(
                {self.current_module: [object_definition]}
            )

    def visit_FunctionDef(self, node: ast.FunctionDef):
        node = self._strip_vault_typehint(node)
        if self.renderer.root_module == self.current_module:
            return self.generic_visit(node)
        else:
            object_definition = ImportedObject(
                name=node.name,
                namespaced_name=combine_module_and_object_name(
                    self.current_module.__name__, node.name
                ),
                stmt=node,
                module_from=self.current_module,
            )
            self._update_module_object_definitions(object_definition)

            return None

    def visit_Assign(self, node: ast.Assign):
        if self.renderer.root_module == self.current_module:
            return self.generic_visit(node)
        else:
            for name in node.targets:
                if isinstance(name, ast.Name):
                    object_definition = ImportedObject(
                        name=name.id,
                        namespaced_name=combine_module_and_object_name(
                            self.current_module.__name__, name.id
                        ),
                        stmt=node,
                        module_from=self.current_module,
                    )
                    self._update_module_object_definitions(object_definition)
                else:
                    raise RenderException(
                        f"Unable to assign to target of type {type(name)} in "
                        f"{self.current_module.__name__} (Line: {node.lineno} Col: "
                        f"{node.col_offset})"
                    )
            return None

    def _strip_expr_vault_typehint(self, node: ast.expr) -> ast.expr:
        """
        This function replaces `Vault` and `SupervisorVault` type hints with `Any` as they are
        supported in templates, but not within Contracts API itself.
        The two types are replaced in arguments and return type annotations, including nested
        annotations such as Optional[Vault] or tuple[list[Vault], str]

        :param node: the FunctionDef to remove the type hints from
        :return: the node, stripped of any Vault/SupervisorVault type hints
        """

        # this handles the simple cases like arg_name: Vault
        if isinstance(node, ast.Name):
            if node.id in VAULT_TYPES:
                node.id = "Any"
                # we'll need to make sure any is added to imports
                self.renderer.vault_type_hint_replaced = True

        # this handles single element subscripts like list[Vault]
        elif isinstance(node, ast.Subscript):
            node.slice = self._strip_expr_vault_typehint(node.slice)

        # this handles `|` cases like `Vault | None`
        elif isinstance(node, ast.BinOp):
            node.left = self._strip_expr_vault_typehint(node.left)
            # right might be another BinOp if we have `Type1 | Type2 | Type3`
            node.right = self._strip_expr_vault_typehint(node.right)

        elif isinstance(node, ast.Set) or isinstance(node, ast.List) or isinstance(node, ast.Tuple):
            for element in node.elts:
                element = self._strip_expr_vault_typehint(element)

        return node

    def _strip_vault_typehint(self, function_def: ast.FunctionDef) -> ast.FunctionDef:
        """
        This function removes `Vault` and `SupervisorVault` type hints from function
        arguments and return type hints. See `_strip_expr_vault_typehint` for more details

        :param function_def: the FunctionDef to remove the type hints from
        :return: function_def, stripped of any Vault/SupervisorVault type hints
        """
        all_args = (
            function_def.args.args + function_def.args.kwonlyargs + function_def.args.posonlyargs
        )
        for arg in all_args:
            if arg.annotation:
                arg.annotation = self._strip_expr_vault_typehint(arg.annotation)

        if function_def.returns is not None:
            function_def.returns = self._strip_expr_vault_typehint(function_def.returns)
        return function_def


def render_smart_contract(path_to_template: str, renderer_config: RendererConfig):
    module_to_render = path_import(path_to_template, Path(path_to_template).stem)
    if module_to_render:
        SmartContractRenderer(
            module_to_render=module_to_render, renderer_config=renderer_config
        ).render()
    else:
        log.warning(
            f"Template at `{path_to_template}` returned None when imported and will not "
            f"be rendered"
        )
