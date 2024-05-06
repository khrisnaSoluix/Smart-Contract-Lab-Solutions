# standard libs
import ast


class AstHandlingException(Exception):
    pass


def get_assign_node_target_name(node: ast.Assign) -> str:
    """
    Return the LHS (target) of an Assign node.
    E.g get the my_list node in the statement below
    my_list = [1, 2, 3]

    tuple assignments are not implemented, so using the syntax below would fail.
    a, b = get_tuple()
    """
    if len(node.targets) > 1:
        raise AstHandlingException("Unpacking tuples is not yet implemented.")
    else:
        if isinstance(node.targets[0], ast.Name):
            return node.targets[0].id
        elif isinstance(node.targets[0], ast.Attribute):
            return node.targets[0].attr
        else:
            raise AstHandlingException(f"Unknown target type {type(node.targets[0])}")


def get_ann_assign_node_target_name(node: ast.AnnAssign) -> str:
    """
    Return the LHS (target) of an AnnAssign node. AnnAssign is an assignment with a type annotation.
    E.g get the my_list node in the statement below
    my_list: list[int] = [1, 2, 3]
    """
    if isinstance(node.target, ast.Name):
        return node.target.id
    elif isinstance(node.target, ast.Attribute):
        return node.target.attr
    elif isinstance(node.target, ast.Subscript):
        return node.target.value.id  # type: ignore
    else:
        raise AstHandlingException(f"Unknown target type {type(node.target)}")


def compare_ast(node1: ast.AST | list[ast.AST], node2: ast.AST | list[ast.AST]) -> bool:
    """
    Do a comparison of two (or more) AST nodes, ignoring metadata.
    """
    if type(node1) is not type(node2):
        return False

    if isinstance(node1, ast.AST):
        for k, v in vars(node1).items():
            if k in ("lineno", "col_offset", "ctx", "end_lineno", "end_col_offset"):
                continue
            if not hasattr(node2, k):
                return False
            if not compare_ast(v, getattr(node2, k)):
                return False
        return True

    elif isinstance(node1, list) and isinstance(node2, list):
        if len(node1) != len(node2):
            return False
        else:
            return all([compare_ast(n1, n2) for n1, n2 in zip(node1, node2)])
    else:
        return node1 == node2


def ungroup_stmts(nodes: list[ast.stmt | list[ast.stmt]]) -> list[ast.stmt]:
    """
    Flatten a list of lists of AST nodes.
    """
    flattened_list = []
    for item in nodes:
        if isinstance(item, list):
            flattened_list.extend(item)
        else:
            flattened_list.append(item)
    return flattened_list
