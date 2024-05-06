# standard libs
import ast
import io
import logging
import math
import os
import token as t_type
from dataclasses import dataclass
from functools import cmp_to_key
from pathlib import Path
from tokenize import TokenInfo, tokenize, untokenize
from types import ModuleType
from typing import Iterable, TypeVar

# inception sdk
from inception_sdk.common.python import ast_utils
from inception_sdk.tools.common.tools_utils import path_import

T = TypeVar("T")


log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@dataclass
class ImportedObject:
    name: str
    stmt: ast.stmt
    namespaced_name: str
    module_from: ModuleType

    def __eq__(self, __o: object) -> bool:
        return (
            isinstance(__o, type(self))
            and self.name == __o.name
            and self.namespaced_name == __o.namespaced_name
            and self.module_from == __o.module_from
        )

    def __hash__(self) -> int:
        return hash(
            self.name + (self.namespaced_name or "") + getattr(self.module_from, "__name__", "")
        )


@dataclass
class NativeModule:
    name: str
    import_stmt: ast.Import | ast.ImportFrom
    namespaced_name: str
    module_from: ModuleType | None = None

    def __eq__(self, __o: object) -> bool:
        return (
            isinstance(__o, type(self))
            and self.name == __o.name
            and self.namespaced_name == __o.namespaced_name
        )

    def __hash__(self) -> int:
        return hash(
            self.name + (self.namespaced_name or "") + getattr(self.module_from, "__name__", "")
        )


@dataclass
class ImportedModule:
    name: str
    module: ModuleType
    alias: str | None = None

    def get_name(self):
        return self.alias or self.name

    def __str__(self) -> str:
        return f"ImportedModule(name={self.name}, alias={self.alias})"

    def __eq__(self, __o: object) -> bool:
        return (
            isinstance(__o, type(self))
            and self.name == __o.name
            and self.alias == __o.alias
            and self.module.__name__ == __o.module.__name__
        )

    def __hash__(self) -> int:
        return hash(self.name + str(self.alias) + self.module.__name__)


class RenderException(Exception):
    pass


def clear_node_location_metadata(node: ast.AST) -> ast.AST:
    """
    When moving a node, the metadata associated with that node needs to be removed.
    ast.fix_missing_locations() is called to repopulate this metadata when required.
    """
    # This function has no immediate purpose, given we don't refer to these attributes outside
    # of the AST visitors, at which point the original values are still valid. However, leaving
    # this in may be best to avoid confusing issues later on.

    # col_offset and end_lineno are not optional. They just aren't set
    if hasattr(node, "col_offset"):
        delattr(node, "col_offset")
    if hasattr(node, "lineno"):
        delattr(node, "lineno")
    if hasattr(node, "end_col_offset"):
        node.end_col_offset = None
    if hasattr(node, "end_lineno"):
        node.end_lineno = None
    return node


def combine_module_and_object_name(module_name: str, object_name: str) -> str:
    if len(module_name) > 1:
        if "." in module_name:
            return module_name.split(".")[-1] + "_" + object_name
        else:
            return module_name + "_" + object_name
    else:
        return "_" + object_name


def get_stmt_attribute_data(stmt: ast.stmt) -> str | None:
    """
    Gets statement attribute data based on ast.stmt type:
        AnnAssign - returns target_name
        Assign - returns target_name
        FunctionDef - returns name identifier
        ImportFrom - returns module name
        Import - name of alias name at index 0 (see inline comment)

    else will return None

    """
    if isinstance(stmt, ast.AnnAssign):
        return ast_utils.get_ann_assign_node_target_name(stmt)
    elif isinstance(stmt, ast.Assign):
        return ast_utils.get_assign_node_target_name(stmt)
    elif isinstance(stmt, ast.FunctionDef):
        return stmt.name
    elif isinstance(stmt, ast.Import):
        # This is okay because at this point there would only be an object of type ast.Import
        # if the contract is v4 and is importing the math module which will have no aliases.
        return stmt.names[0].name
    elif isinstance(stmt, ast.ImportFrom):
        # module is None when using a relative import. Shouldn't affect us but it could happen
        return stmt.module
    else:
        return None


def get_module_filename(module: ModuleType) -> str:
    # module.__file__ is only None for C modules statically linked to the
    # interpreter, so this feels safe to handle this way
    if hasattr(module, "__file__"):
        return os.path.basename(module.__file__)  # type: ignore
    else:
        return ""


def get_module_dirname(module: ModuleType) -> str:
    # module.__file__ is only None for C modules statically linked to the
    # interpreter, so this feels safe to handle this way
    if hasattr(module, "__file__"):
        return os.path.dirname(module.__file__)  # type: ignore
    else:
        return ""


def remove_quotes_from_module_headers(rendered_contract: str, module_header_identifier: str) -> str:
    """
    The ast module does not preserve comments. This is used as a work-around to allow comments to be
    added to the tree by using an ast.Constant node. The module header prefix is used to determine
    what is and isn't a module header string, so ensure that it is unique enough not to clash with
    other object definitions.
    """

    def strip_header_token(token_value: str) -> str:
        return token_value.replace(module_header_identifier, "").replace('"', "").replace("'", "")

    tokens = tokenize(io.BytesIO(rendered_contract.encode("utf-8")).readline)
    new_tokens: list[TokenInfo] = []
    newlines_added = 0
    header_found = False
    header_whitespace_required = False

    for token in tokens:
        # Check if we need to add a new line below the new module section header
        # We only need to add an NL token if there isn't one directly below
        if header_found:
            # a header has been added, as soon as we find a newline set whitespace required false
            if token.type == t_type.NL:
                if header_whitespace_required:
                    header_whitespace_required = False
                # if we find another new line we need to not add it (continue)
                elif not header_whitespace_required:
                    newlines_added -= 1
                    continue
            # if we have come across a new token type add whitespace if its required
            elif (
                token.type != t_type.NL
                and token.type != t_type.DEDENT
                and module_header_identifier not in token.line
            ):
                header_found = False
                if header_whitespace_required:
                    nl_start = (token.start[0] + newlines_added, token.start[1])
                    nl_end = (token.end[0] + newlines_added, token.end[1])
                    new_tokens.append(
                        TokenInfo(t_type.NL, "\n", (nl_start[0], 0), (nl_end[0], 1), "\n")
                    )
                    newlines_added += 1

        token_start = (token.start[0] + newlines_added, token.start[1])
        token_end = (token.end[0] + newlines_added, token.end[1])

        if module_header_identifier in token.string:
            # check that the previous token is a new line or header line otherwise add an NL 61
            if new_tokens[-1] and (
                module_header_identifier not in new_tokens[-1].line
                and new_tokens[-1].type != t_type.NL
            ):
                nl_start = (token.start[0] + newlines_added, token.start[1])
                nl_end = (token.end[0] + newlines_added, token.end[1])
                new_tokens.append(
                    TokenInfo(t_type.NL, "\n", (nl_start[0], 0), (nl_end[0], 1), "\n")
                )
                newlines_added += 1
                token_start = (token.start[0] + newlines_added, token.start[1])
                token_end = (token.end[0] + newlines_added, token.end[1])

            # Here we need to check whether the previous line is an NL 61
            elif token.type == t_type.STRING and module_header_identifier not in token.line:
                for t in reversed(new_tokens):
                    if t.type == t_type.DEDENT:
                        continue
                    elif t.type != t_type.NL:
                        newlines_added += 2
                        new_tokens.extend(
                            [
                                TokenInfo(
                                    t_type.NL,
                                    "\n",
                                    (token_start[0], 0),
                                    (token_end[0], 1),
                                    "\n",
                                ),
                                TokenInfo(
                                    t_type.NL,
                                    "\n",
                                    (token_start[0] + 1, 0),
                                    (token_end[0] + 1, 1),
                                    "\n",
                                ),
                            ]
                        )
                        token_start = (token.start[0] + newlines_added, token.start[1])
                        token_end = (token.end[0] + newlines_added, token.end[1])
                        break
                    else:
                        break

            new_tokens.append(
                TokenInfo(
                    token.type,
                    strip_header_token(token.string),
                    token_start,
                    token_end,
                    strip_header_token(token.line),
                )
            )
            header_found = True
            header_whitespace_required = True
        else:
            new_tokens.append(
                TokenInfo(token.type, token.string, token_start, token_end, token.line)
            )

    return untokenize(new_tokens).decode("utf-8")


def group_multiline_strings(
    stmts: list[ast.stmt],
) -> list[ast.stmt | list[ast.stmt]]:
    """
    Group nodes into a lists of nodes where there are multi-line string constants defined.
    The AST module will create multiple independent nodes to represent multi-line strings, making
    it difficult to apply sorting to a list of nodes. In almost all cases, multi-line string nodes
    should be kept grouped together.
    An example of how a multi-line string is represented as an AST is below:

    my_attribute = "Here is an example "
    "of a multi-line string."

    Parsed to an AST (simplified):
    [ast.Assign(), ast.Expr()]
    (The second line of the multi-line string is represented as a Constant node type, separate from
     the Assign node.)

    This will return the original list of nodes, with all multi-line assignments grouped as a list.
    E.g.
    Input: [ast.FunctionDef, ast.FunctionDef, ast.Assign, ast.Expr, ast.Assign, ast.FunctionDef]
    Output: [ast.FunctionDef, ast.FunctionDef, [ast.Assign, ast.Expr], ast.Assign, ast.FunctionDef]
    """

    grouped_stmts: list[ast.stmt | list[ast.stmt]] = []
    stmts_to_group: list[ast.stmt] = []

    def add_group(group: list[ast.stmt]):
        if len(group) == 0:
            return
        # a partial inflight group may not be a group at all
        elif len(group) == 1:
            grouped_stmts.append(group[0])
        else:
            grouped_stmts.append(group)

    for stmt in stmts:
        if stmts_to_group:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                # additional group-able stmts are added to the group
                stmts_to_group.append(stmt)
            else:
                # current stmt is not group-able, so any in-flight groups can be added to list
                add_group(stmts_to_group)
                stmts_to_group = []
                # current stmt won't have been added yet
                grouped_stmts.append(stmt)
        elif isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Constant):
            # this is the start of a potential group
            stmts_to_group.append(stmt)
        else:
            grouped_stmts.append(stmt)

    # there could be a in-flight group at the end of the list of stmts
    add_group(stmts_to_group)

    return grouped_stmts


def reorder_nodes(nodes: list[ast.stmt], order: list[str]) -> tuple[list[ast.stmt], bool]:
    """
    Given a list of AST nodes, reorder them according to the order list.

    :param order: Order list defines the order in which to arrange the definition nodes, e.g.
    [
        "display_name",
        "description",
        "pre_posting_code",
        "post_posting_code"
    ]
    In this example, the return list will contain each of the definitions in the same order.
    Objects that do not match any entries in the order list are moved below all those that do
    match. Meaning that any objects defined in the order list are guaranteed to be at the top of
    the returned list (the top being index 0).
    :return tuple: list of ordered nodes, bool to state whether the order has changed
    """
    grouped_nodes = group_multiline_strings(nodes)
    order_val = dict((name, i) for i, name in enumerate(order))
    order_changed = False

    def sort_metadata(node1: ast.stmt, node2: ast.stmt):
        nonlocal order_changed

        if isinstance(node1, list):
            node1 = node1[0]
        if isinstance(node2, list):
            node2 = node2[0]

        # if no name is found, empty string will default to math.inf
        node1_name = get_stmt_attribute_data(node1) or ""
        node2_name = get_stmt_attribute_data(node2) or ""

        # math.inf is used as the default to ensure that undefined order items always fall below
        # those defined in the order list
        node1_order_value = order_val.get(node1_name, math.inf)
        node2_order_value = order_val.get(node2_name, math.inf)

        if not order_changed:
            order_changed = node1_order_value != math.inf or node2_order_value != math.inf

        if node1_order_value == node2_order_value:
            return 0
        elif node1_order_value < node2_order_value:
            return -1
        else:
            return 1

    grouped_nodes = sorted(grouped_nodes, key=cmp_to_key(sort_metadata))
    return ast_utils.ungroup_stmts(grouped_nodes), order_changed


def remove_remaining_headers(nodes: list[ast.stmt], header_prefix: str) -> list[ast.stmt]:
    """
    Removes any stray unused headers that may be left at the bottom of the list.
    This could happen if all objects from the template have been moved to the top of the file.
    """
    while (
        isinstance(nodes[-1], ast.Expr)
        and isinstance(nodes[-1].value, ast.Constant)
        and header_prefix in nodes[-1].value.value
    ):
        nodes.pop(-1)
    return nodes


def module_header_stmts(headers: list[str]) -> list[ast.stmt]:
    return [ast.Expr(value=ast.Constant(value=header)) for header in headers]


def is_file_renderable(filepath: Path) -> bool:
    try:
        return path_import(filepath, Path(filepath).stem) is not None
    except (AttributeError, NameError):
        return False
    except FileNotFoundError:
        # Its possible the filepath points to a file within a container e.g. .pex or .zip
        # In which case, with current implementation, the files required for rendering should be
        # available from outside containers. If using Please ensure that any contract templates are
        # added as data in the BUILD file.
        if "template" in str(filepath):
            log.warning(
                f"Its possible the file provided '{filepath}' should be rendered, however it could "
                "not be found. If using Please, ensure it is added to the BUILD file as both data "
                "and dependency."
            )

        return False


def recursive_topological_sort(graph: dict[T, list[T]], node: T) -> list[T]:
    """
    Implementation of a recursive DFS algorithm storing result for topological order.
    """
    result = []
    seen = set()

    def recursive_helper(node):
        for neighbour in graph.get(node, []):
            if neighbour not in seen:
                seen.add(neighbour)
                recursive_helper(neighbour)
        result.append(node)

    recursive_helper(node)
    return result


class ObjectReferenceFound(Exception):
    pass


class ObjectReferenceDiscovery(ast.NodeVisitor):
    def __init__(self, reference_to_find: str) -> None:
        self.reference_to_find = reference_to_find
        super().__init__()

    def visit_Name(self, node: ast.Name):
        if node.id == self.reference_to_find:
            # When the first object reference is found we can return to the caller
            # by raising an exception to immediately halt traversal of the AST
            raise ObjectReferenceFound()
        return self.generic_visit(node)


def get_unreferenced_objects(
    object_reference_map: dict[ImportedObject, Iterable[ImportedObject | str]]
) -> list[ImportedObject]:
    """
    Taking each object in object_reference_map, check against the map to see if it is referenced,
    either directly or indirectly. Below is a pseudo example of an object_reference_map:
    {
        get_postings: [create_postings],
        str_to_bool: [get_postings, is_active, get_parameter]
        get_parameter: []
        is_active: [retrieve_product]
        create_postings: []
    }
    In the example data, we should remove get_postings, get_parameter and create_postings as they
    are either not referenced directly or indirectly (get_postings is referenced by create_postings
    but create_postings isn't referenced at all - so both should be removed).

    :param object_reference_map: mapping of object to objects that reference it
    """

    objects_not_referenced = []

    def obj_not_referenced(obj: ImportedObject | str) -> bool:
        """
        Helper function to determine if obj is referenced.
        """
        if isinstance(obj, str):
            # obj reference comes from the template so can be ignored
            return False
        elif not object_reference_map[obj]:
            # current obj is not referenced
            return True
        else:
            return all(obj_not_referenced(o) for o in object_reference_map[obj])

    for object_to_import, references in object_reference_map.items():
        if all(obj_not_referenced(obj) for obj in references):
            objects_not_referenced.append(object_to_import)

    return objects_not_referenced
