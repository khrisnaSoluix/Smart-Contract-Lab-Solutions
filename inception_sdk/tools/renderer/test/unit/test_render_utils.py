# standard libs
import ast
import unittest
from unittest import TestCase

# inception sdk
from inception_sdk.tools.renderer.render_utils import (
    clear_node_location_metadata,
    combine_module_and_object_name,
    get_stmt_attribute_data,
    group_multiline_strings,
    remove_remaining_headers,
    reorder_nodes,
)
from inception_sdk.tools.renderer.renderer import RendererConfig
API_ASSIGN_NODE = ast.Assign(
    targets=[ast.Name(id="api", ctx=ast.Store())],
    value=ast.Constant(value="4.0.0", kind=None),
    lineno=1,
)
VERSION_ASSIGN_NODE = ast.Assign(
    targets=[ast.Name(id="version", ctx=ast.Store())],
    value=ast.Constant(value="1.0.0", kind=None),
    lineno=2,
)


class RenderUtilsTest(TestCase):
    def test_clear_node_location_metadata(self):
        node = ast.Name(
            id="name",
            col_offset=1,
            end_col_offset=2,
            lineno=3,
            end_lineno=4,
        )
        node = clear_node_location_metadata(node)
        self.assertFalse(hasattr(node, "col_offset"))
        self.assertFalse(hasattr(node, "lineno"))
        self.assertEqual(node.end_col_offset, None)
        self.assertEqual(node.end_lineno, None)

    def test_combine_module_and_object_name(self):
        new_object_name = combine_module_and_object_name("tools.renderer.render_utils", "test")
        self.assertEqual(new_object_name, "render_utils_test")

    def test_combine_module_and_object_name_no_dots_in_name(self):
        new_object_name = combine_module_and_object_name("render_utils", "test")
        self.assertEqual(new_object_name, "render_utils_test")

    def test_combine_module_and_object_name_just_dot(self):
        # this scenario occurs if a module does a relative import
        # e.g. from . import my_module
        new_object_name = combine_module_and_object_name(".", "test")
        self.assertEqual(new_object_name, "_test")

    def test_group_multiline_strings(self):
        self.maxDiff = None
        nodes = [
            API_ASSIGN_NODE,
            VERSION_ASSIGN_NODE,
            ast.Assign(
                targets=[ast.Name(id="summary", ctx=ast.Store())],
                value=ast.Constant(value="This is a ", kind=None),
                lineno=3,
            ),
            ast.Expr(value=ast.Constant(value="test product."), lineno=4),
            ast.Assign(
                targets=[ast.Name(id="supported_denomination", ctx=ast.Store())],
                value=ast.Constant(value="GBP", kind=None),
                lineno=5,
            ),
            ast.Assign(
                targets=[ast.Name(id="description", ctx=ast.Store())],
                value=ast.Constant(value="More unit tests ", kind=None),
                lineno=6,
            ),
            ast.Expr(value=ast.Constant(value="please."), lineno=7),
        ]
        expected_output = [
            API_ASSIGN_NODE,
            VERSION_ASSIGN_NODE,
            [
                ast.Assign(
                    targets=[ast.Name(id="summary", ctx=ast.Store())],
                    value=ast.Constant(value="This is a ", kind=None),
                    lineno=3,
                ),
                ast.Expr(value=ast.Constant(value="test product."), lineno=4),
            ],
            ast.Assign(
                targets=[ast.Name(id="supported_denomination", ctx=ast.Store())],
                value=ast.Constant(value="GBP", kind=None),
                lineno=5,
            ),
            [
                ast.Assign(
                    targets=[ast.Name(id="description", ctx=ast.Store())],
                    value=ast.Constant(value="More unit tests ", kind=None),
                    lineno=6,
                ),
                ast.Expr(value=ast.Constant(value="please."), lineno=7),
            ],
        ]
        nodes = group_multiline_strings(nodes)
        self.assertEqual(ast.unparse(nodes), ast.unparse(expected_output))

    def test_reorder_nodes(self):
        nodes = [
            VERSION_ASSIGN_NODE,
            ast.Assign(
                targets=[ast.Name(id="summary", ctx=ast.Store())],
                value=ast.Constant(value="This is a ", kind=None),
                lineno=2,
            ),
            ast.Expr(value=ast.Constant(value="test product."), lineno=3),
            ast.Assign(
                targets=[ast.Name(id="display_name", ctx=ast.Store())],
                value=ast.Constant(value="Test Product", kind=None),
                lineno=4,
            ),
            API_ASSIGN_NODE,
            ast.Assign(
                targets=[ast.Name(id="description", ctx=ast.Store())],
                value=ast.Constant(value="More unit tests ", kind=None),
                lineno=6,
            ),
            ast.Expr(value=ast.Constant(value="please."), lineno=7),
        ]

        expected_output = [
            API_ASSIGN_NODE,
            VERSION_ASSIGN_NODE,
            ast.Assign(
                targets=[ast.Name(id="display_name", ctx=ast.Store())],
                value=ast.Constant(value="Test Product", kind=None),
                lineno=3,
            ),
            ast.Assign(
                targets=[ast.Name(id="description", ctx=ast.Store())],
                value=ast.Constant(value="More unit tests ", kind=None),
                lineno=4,
            ),
            ast.Expr(value=ast.Constant(value="please."), lineno=5),
            ast.Assign(
                targets=[ast.Name(id="summary", ctx=ast.Store())],
                value=ast.Constant(value="This is a ", kind=None),
                lineno=6,
            ),
            ast.Expr(value=ast.Constant(value="test product."), lineno=7),
        ]

        order = [
            "api",
            "version",
            "display_name",
            "description",
            "summary",
        ]

        nodes, order_changed = reorder_nodes(nodes, order)
        self.assertEqual(ast.unparse(nodes), ast.unparse(expected_output))
        self.assertTrue(order_changed)

    def test_reorder_nodes_incl_func_defs_and_missing_objects(self):
        nodes = [
            ast.FunctionDef(
                name="pre_posting_code",
                args=[],
                body=[
                    ast.Assign(
                        targets=[ast.Name(id="denomination", ctx=ast.Store())],
                        value=ast.Constant(value="GBP", kind=None),
                        lineno=3,
                    )
                ],
                decorator_list=[],
                lineno=2,
            ),
            ast.Assign(
                targets=[ast.Name(id="summary", ctx=ast.Store())],
                value=ast.Constant(value="This is a ", kind=None),
                lineno=4,
            ),
            ast.Expr(value=ast.Constant(value="test product."), lineno=3),
            ast.Assign(
                targets=[ast.Name(id="api", ctx=ast.Store())],
                value=ast.Constant(value="3.9.0", kind=None),
                lineno=7,
            ),
            ast.Assign(
                targets=[ast.Name(id="description", ctx=ast.Store())],
                value=ast.Constant(value="More unit tests ", kind=None),
                lineno=8,
            ),
            ast.Expr(value=ast.Constant(value="please."), lineno=7),
        ]

        expected_output = [
            ast.Assign(
                targets=[ast.Name(id="api", ctx=ast.Store())],
                value=ast.Constant(value="3.9.0", kind=None),
                lineno=1,
            ),
            ast.Assign(
                targets=[ast.Name(id="description", ctx=ast.Store())],
                value=ast.Constant(value="More unit tests ", kind=None),
                lineno=4,
            ),
            ast.Expr(value=ast.Constant(value="please."), lineno=5),
            ast.Assign(
                targets=[ast.Name(id="summary", ctx=ast.Store())],
                value=ast.Constant(value="This is a ", kind=None),
                lineno=6,
            ),
            ast.Expr(value=ast.Constant(value="test product."), lineno=7),
            ast.FunctionDef(
                name="pre_posting_code",
                args=[],
                body=[
                    ast.Assign(
                        targets=[ast.Name(id="denomination", ctx=ast.Store())],
                        value=ast.Constant(value="GBP", kind=None),
                        lineno=9,
                    )
                ],
                decorator_list=[],
                lineno=8,
            ),
        ]

        order = [
            "api",
            "version",
            "display_name",
            "description",
            "summary",
            "pre_posting_code",
        ]

        nodes, order_changed = reorder_nodes(nodes, order)
        self.assertEqual(ast.unparse(nodes), ast.unparse(expected_output))
        self.assertTrue(order_changed)

    def test_get_stmt_attribute_data_assign(self):
        func_def_stmt = ast.FunctionDef(
            name="pre_posting_code",
            args=[],
            body=[
                ast.Assign(
                    targets=[ast.Name(id="denomination", ctx=ast.Store())],
                    value=ast.Constant(value="GBP", kind=None),
                    lineno=2,
                )
            ],
            decorator_list=[],
            lineno=1,
        )
        name = get_stmt_attribute_data(func_def_stmt)
        self.assertEqual(name, "pre_posting_code")

    def test_get_stmt_attribute_data_ann_assign(self):
        ann_assign_node = ast.AnnAssign(
            target=ast.Name(ctx=ast.Store(), id="SOME_LIST"),
            annotation=ast.Name(id="list", ctx=ast.Load()),
            value=ast.Constant(value=[1, 2, 3]),
        )
        name = get_stmt_attribute_data(ann_assign_node)
        self.assertEqual(name, "SOME_LIST")

    def test_get_stmt_attribute_data_function_def(self):
        assign_stmt = ast.Assign(
            targets=[ast.Name(id="api", ctx=ast.Store())],
            value=ast.Constant(value="3.9.0", kind=None),
            lineno=1,
        )
        name = get_stmt_attribute_data(assign_stmt)
        self.assertEqual(name, "api")

    def test_get_stmt_attribute_data_unknown_type(self):
        unknown_stmt = "test"
        name = get_stmt_attribute_data(unknown_stmt)
        self.assertEqual(name, None)

    def test_get_stmt_attribute_data_import_from(self):
        import_from_stmt = ast.ImportFrom(module="datetime", names=[ast.alias(names="some object")])
        name = get_stmt_attribute_data(import_from_stmt)
        self.assertEqual(name, "datetime")

    def test_get_stmt_attribute_data_import(self):
        import_stmt = ast.Import(names=[ast.alias(name="math")])
        name = get_stmt_attribute_data(import_stmt)
        self.assertEqual(name, "math")

    def test_remove_remaining_headers(self):
        header_prefix = RendererConfig().module_header_prefix
        nodes = [
            ast.Assign(
                targets=[ast.Name(id="api", ctx=ast.Store())],
                value=ast.Constant(value="3.9.0", kind=None),
                lineno=1,
            ),
            ast.Expr(value=ast.Constant(value=header_prefix + "module.py")),
        ]

        nodes = remove_remaining_headers(nodes, header_prefix)

        expected_output = [
            ast.Assign(
                targets=[ast.Name(id="api", ctx=ast.Store())],
                value=ast.Constant(value="3.9.0", kind=None),
                lineno=1,
            )
        ]
        self.assertEqual(ast.unparse(nodes), ast.unparse(expected_output))

    def test_remove_remaining_headers_multiple(self):
        header_prefix = RendererConfig().module_header_prefix
        nodes = [
            ast.Expr(value=ast.Constant(value=header_prefix + "module.py")),
            ast.Assign(
                targets=[ast.Name(id="api", ctx=ast.Store())],
                value=ast.Constant(value="3.9.0", kind=None),
                lineno=1,
            ),
            ast.Expr(value=ast.Constant(value=header_prefix + "module1.py")),
            ast.Expr(value=ast.Constant(value=header_prefix + "module2.py")),
        ]

        nodes = remove_remaining_headers(nodes, header_prefix)

        expected_output = [
            ast.Expr(value=ast.Constant(value=header_prefix + "module.py")),
            ast.Assign(
                targets=[ast.Name(id="api", ctx=ast.Store())],
                value=ast.Constant(value="3.9.0", kind=None),
                lineno=1,
            ),
        ]
        self.assertEqual(ast.unparse(nodes), ast.unparse(expected_output))


if __name__ == "__main__":
    unittest.main()
