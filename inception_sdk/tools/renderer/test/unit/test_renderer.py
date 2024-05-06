# standard libs
import ast
import unittest
from unittest import TestCase
from unittest.mock import Mock, call, patch

# inception sdk
import inception_sdk.tools.renderer.renderer as renderer
from inception_sdk.common.python.ast_utils import compare_ast
from inception_sdk.tools.renderer.render_utils import (
    ImportedModule,
    ImportedObject,
    RenderException,
    combine_module_and_object_name,
)
from inception_sdk.tools.renderer.renderer import (
    ObjectDiscovery,
    RendererConfig,
    SmartContractRenderer,
)
from inception_sdk.tools.renderer.test.unit.input import (
    module_1,
    module_2,
    module_3,
    v4_contract_template,
)


class RendererTest(TestCase):
    @patch.object(renderer, "combine_module_and_object_name")
    def test_rename_imported_module_references(self, mock_combine_module_and_object_name: Mock):
        scr = SmartContractRenderer(module_1)
        scr.module_import_mapping = {
            module_1: [
                ImportedModule(
                    name="inception_sdk.tools.renderer.test.unit.input.module_2",
                    alias="module_2",
                    module=module_2,
                )
            ],
            module_2: [
                ImportedModule(
                    name="inception_sdk.tools.renderer.test.unit.input.module_3",
                    alias="module_3",
                    module=module_3,
                )
            ],
        }
        scr.module_object_definitions = {
            module_2: [
                ImportedObject(
                    name="attribute_1",
                    namespaced_name="module_2_attribute_1",
                    module_from=module_2,
                    stmt=ast.parse("attribute_1 = 1").body[0],
                ),
                ImportedObject(
                    name="function_1",
                    namespaced_name="module_2_function_1",
                    module_from=module_2,
                    stmt=ast.parse("def function_1():\n\treturn 1").body[0],
                ),
                ImportedObject(
                    name="attribute_2",
                    namespaced_name="module_2_attribute_2",
                    module_from=module_2,
                    stmt=ast.parse("attribute_2 = module_3.attribute_1").body[0],
                ),
            ],
            module_3: [
                ImportedObject(
                    name="attribute_1",
                    namespaced_name="module_3_attribute_1",
                    module_from=module_3,
                    stmt=ast.parse("attribute_1 = 1").body[0],
                ),
            ],
        }
        scr._rename_imported_module_references()
        mock_combine_module_and_object_name.assert_has_calls(
            [
                call("inception_sdk.tools.renderer.test.unit.input.module_2", "attribute_1"),
                call("inception_sdk.tools.renderer.test.unit.input.module_2", "function_1"),
                call("inception_sdk.tools.renderer.test.unit.input.module_3", "attribute_1"),
            ]
        )

    @patch.object(renderer, "get_stmt_attribute_data")
    def test_remove_unused_objects_indirect_references(self, mock_get_stmt_attribute_data: Mock):
        # This test ensures that objects that are referenced indirectly aren't removed from the
        # tree. An indirect reference could be any number of child references from the root level,
        # e.g. template references function which references an attribute
        # the result should be that both function and attribute remain in the tree
        mock_get_stmt_attribute_data.return_value = "template_object"
        scr = SmartContractRenderer(v4_contract_template)
        # Create a reference to module_1_function_1 from the template
        scr.root_tree.body = ast.parse("module_1_function_1").body
        scr.root_tree.body[0].value.from_module = module_1
        module_1_function_1 = ImportedObject(
            name="function_1",
            namespaced_name="module_1_function_1",
            module_from=module_1,
            stmt=ast.parse("def module_1_function_1():\n\treturn module_2_attribute_1").body[0],
        )
        module_1_unreferenced_attribute = ImportedObject(
            name="unreferenced_attribute",
            namespaced_name="module_1_unreferenced_attribute",
            module_from=module_1,
            stmt=ast.parse("module_1_unreferenced_attribute = 1").body[0],
        )
        module_2_attribute_1 = ImportedObject(
            name="attribute_1",
            namespaced_name="module_2_attribute_1",
            module_from=module_2,
            stmt=ast.parse("module_2_attribute_1 = 1").body[0],
        )
        module_2_unreferenced_function = ImportedObject(
            name="unreferenced_function",
            namespaced_name="module_2_unreferenced_function",
            module_from=module_2,
            stmt=ast.parse("def module_2_unreferenced_function():\n\treturn 1").body[0],
        )

        scr.objects_to_import = [
            module_1_function_1,
            module_1_unreferenced_attribute,
            module_2_attribute_1,
            module_2_unreferenced_function,
        ]

        module_1_function_1.stmt.body[0].value.imported_object_ref = module_2_attribute_1
        for object in scr.objects_to_import:
            object.stmt.imported_object_ref = object

        scr._remove_unused_objects()

        self.assertEqual(len(scr.objects_to_import), 2)
        # Ensure that the two unreferenced objects are removed and the indirectly referenced
        # attribute remains
        self.assertEqual(
            scr.objects_to_import,
            [
                ImportedObject(
                    name="function_1",
                    namespaced_name="module_1_function_1",
                    module_from=module_1,
                    stmt=ast.parse(
                        "def module_1_function_1():\n\treturn module_2_attribute_1"
                    ).body[0],
                ),
                ImportedObject(
                    name="attribute_1",
                    namespaced_name="module_2_attribute_1",
                    module_from=module_2,
                    stmt=ast.parse("module_2_attribute_1 = 1").body[0],
                ),
            ],
        )

    @patch.object(renderer, "get_stmt_attribute_data")
    def test_remove_unused_objects(self, mock_get_stmt_attribute_data: Mock):
        mock_get_stmt_attribute_data.return_value = "template_object"
        scr = SmartContractRenderer(v4_contract_template)
        # Create a reference to module_2_attribute_1 and module_2_function_1 from the template
        scr.root_tree.body = [
            ast.parse('api = "4.0.0"').body[0],
            ast.parse("module_2_attribute_1").body[0],
            ast.parse("module_2_function_1").body[0],
        ]
        scr.root_tree.body[1].value.from_module = module_2
        scr.root_tree.body[2].value.from_module = module_2

        scr.objects_to_import = [
            ImportedObject(
                name="attribute_1",
                namespaced_name="module_2_attribute_1",
                module_from=module_2,
                stmt=ast.parse("module_2_attribute_1 = 1").body[0],
            ),
            ImportedObject(
                name="unreferenced_attribute",
                namespaced_name="module_2_unreferenced_attribute",
                module_from=module_2,
                stmt=ast.parse("module_2_unreferenced_attribute = 1").body[0],
            ),
            ImportedObject(
                name="function_1",
                namespaced_name="module_2_function_1",
                module_from=module_2,
                stmt=ast.parse("def module_2_function_1():\n\treturn 1").body[0],
            ),
            ImportedObject(
                name="unreferenced_function",
                namespaced_name="module_2_unreferenced_function",
                module_from=module_2,
                stmt=ast.parse("def module_2_unreferenced_function():\n\treturn 1").body[0],
            ),
        ]
        for object in scr.objects_to_import:
            object.stmt.imported_object_ref = object

        scr._remove_unused_objects()

        self.assertEqual(len(scr.objects_to_import), 2)
        # Ensure that the two unreferenced objects declared in module_2 have been removed
        # from the output
        self.assertEqual(
            scr.objects_to_import,
            [
                ImportedObject(
                    name="attribute_1",
                    namespaced_name="module_2_attribute_1",
                    module_from=module_2,
                    stmt=ast.parse("module_2_attribute_1 = 1").body[0],
                ),
                ImportedObject(
                    name="function_1",
                    namespaced_name="module_2_function_1",
                    module_from=module_2,
                    stmt=ast.parse("def module_2_function_1():\n\treturn 1").body[0],
                ),
            ],
        )

    @patch.object(renderer, "get_stmt_attribute_data")
    def test_remove_unused_objects_unreferenced_child_objects(
        self, mock_get_stmt_attribute_data: Mock
    ):
        """
        This test ensures that where a feature is imported that contains a function that references
        another function from the same feature, both are removed if they aren't referenced by any
        object in the template. In other words, remove all objects in a chain if the parent and its
        children aren't referenced. E.g:
        template imports feature
        feature defines feature_schedules and get_schedules
            (get_schedules returns feature_schedules)
        neither are referenced in the template, so both should be removed
        """
        mock_get_stmt_attribute_data.return_value = "template_object"
        scr = SmartContractRenderer(v4_contract_template)
        # Create a reference to module_2_attribute_1 and module_2_function_1 from the template
        scr.root_tree.body = []
        scr.objects_to_import = [
            ImportedObject(
                name="feature_schedules",
                namespaced_name="module_1_feature_schedules",
                module_from=module_1,
                stmt=ast.parse("feature_schedules = ['f1', 'f2']").body[0],
            ),
            ImportedObject(
                name="get_schedules",
                namespaced_name="module_1_get_schedules",
                module_from=module_1,
                stmt=ast.parse("def get_schedules():\n\t return module_1_feature_schedules").body[
                    0
                ],
            ),
        ]

        scr._remove_unused_objects()

        self.assertEqual(len(scr.objects_to_import), 0)
        self.assertEqual(scr.objects_to_import, [])

    @patch.object(renderer, "combine_module_and_object_name")
    @patch.object(renderer, "RenameDefinitionTransformer")
    def test_rename_imported_object_definitions(
        self, mock_RenameDefinitionTransformer: Mock, mock_combine_module_and_object_name: Mock
    ):
        """
        Ensure all imported objects are renamed. That is, all objects from module_2 and module_3.
        """
        mock_combine_module_and_object_name.side_effect = combine_module_and_object_name
        scr = SmartContractRenderer(module_1)
        scr.module_import_mapping = {
            module_1: [
                ImportedModule(
                    name="inception_sdk.tools.renderer.test.unit.input.module_2",
                    alias="module_2",
                    module=module_2,
                )
            ],
            module_2: [
                ImportedModule(
                    name="inception_sdk.tools.renderer.test.unit.input.module_3",
                    alias="module_3",
                    module=module_3,
                )
            ],
        }
        module_2_attribute_1 = ImportedObject(
            name="attribute_1",
            namespaced_name="module_2_attribute_1",
            module_from=module_2,
            stmt=ast.parse("attribute_1 = 1").body[0],
        )
        module_2_attribute_2 = ImportedObject(
            name="attribute_2",
            namespaced_name="module_2_attribute_2",
            module_from=module_2,
            stmt=ast.parse("attribute_2 = module_3.attribute_1").body[0],
        )
        module_2_function_1 = ImportedObject(
            name="function_1",
            namespaced_name="module_2_function_1",
            module_from=module_2,
            stmt=ast.parse("def function_1():\n\treturn 1").body[0],
        )
        module_3_attribute_1 = ImportedObject(
            name="attribute_1",
            namespaced_name="module_3_attribute_1",
            module_from=module_3,
            stmt=ast.parse("attribute_1 = 1").body[0],
        )
        scr.module_object_definitions = {
            module_2: [module_2_attribute_1, module_2_attribute_2, module_2_function_1],
            module_3: [module_3_attribute_1],
        }
        scr._rename_imported_object_definitions()
        mock_RenameDefinitionTransformer.assert_any_call(
            [module_2_attribute_1, module_2_attribute_2, module_2_function_1]
        )
        mock_RenameDefinitionTransformer.assert_any_call([module_3_attribute_1])

    @patch.object(renderer, "combine_module_and_object_name")
    def test_rename_imported_object_declarations_tuple_throws_exception(
        self, mock_combine_module_and_object_name: Mock
    ):
        """
        Ensure all imported objects are renamed. That is, all objects from module_2 and module_3.
        """
        mock_combine_module_and_object_name.side_effect = combine_module_and_object_name
        scr = SmartContractRenderer(module_1)
        scr.module_import_mapping = {
            module_1: [
                ImportedModule(
                    name="inception_sdk.tools.renderer.test.unit.input.module_2",
                    alias="module_2",
                    module=module_2,
                )
            ],
        }
        imported_tuple = ImportedObject(
            name="attribute_1",
            namespaced_name="module_2_attribute_1",
            module_from=module_2,
            stmt=ast.parse("attribute_1, attribute_2 = 1, 2").body[0],
        )
        scr.module_object_definitions = {
            module_2: [imported_tuple],
        }
        with self.assertRaises(RenderException) as test:
            ObjectDiscovery(scr, module_2).visit(imported_tuple.stmt)
        self.assertEqual(
            test.exception.args[0],
            "Unable to assign to target of type "
            "<class 'ast.Tuple'> in inception_sdk.tools.renderer.test.unit.input.module_2 "
            "(Line: 1 Col: 0)",
        )

    def test_append_node(self):
        """
        Ensure that only unique ASTs are stored.
        """
        scr = SmartContractRenderer(module_1)
        nodes = [
            ast.parse("attribute_1 = function_1()").body[0],
            ast.parse("attribute_2 = function_1()").body[0],
            ast.parse("attribute_1 = function_1()").body[0],  # this duplicate should not be stored
            ast.parse("attribute_1 = function_1(param_1)").body[0],
        ]
        for node in nodes:
            scr._append_stmt(node)
        self.assertEqual(len(scr.stmts_to_append), 3)

    def test_object_discovery_strips_vault_typehints_from_function_defs(self):
        mock_module = Mock(__name__="TestModule")
        mock_module_object_definitions = {mock_module: []}
        mock_scr = Mock(module_object_definitions=mock_module_object_definitions)

        ObjectDiscovery(mock_scr, mock_module).visit(
            ast.parse(
                "def function_1(\n"
                "\tmy_arg: SmartContractVault,\n"
                "\tmy_arg_2: SmartContractVault | None,\n"
                "\tuntouched_arg: str,\n"
                "\tmy_arg_3: dict[str, tuple[str, SupervisorContractVault]],\n"
                "\tmy_arg_4: list[SmartContractVault],\n"
                "\t) -> SuperviseeContractVault:\n"
                "\treturn 1"
            ).body[0]
        )
        expected_imported_object = ImportedObject(
            name="function_1",
            namespaced_name="TestModule_function_1",
            stmt=ast.parse(
                "def function_1(\n"
                "\tmy_arg: Any,\n"
                "\tmy_arg_2: Any | None,\n"
                "\tuntouched_arg: str,\n"
                "\tmy_arg_3: dict[str, tuple[str, Any]],\n"
                "\tmy_arg_4: list[Any],\n"
                "\t) -> Any:\n"
                "\treturn 1"
            ).body[0],
            module_from=mock_module,
        )
        self.assertEqual(
            mock_scr.module_object_definitions[mock_module][0], expected_imported_object
        )
        self.assertTrue(
            compare_ast(
                mock_scr.module_object_definitions[mock_module][0].stmt,
                expected_imported_object.stmt,
            )
        )

    def test_object_discovery_strips_vault_typehints_from_function_defs_kwonlyargs(self):
        mock_module = Mock(__name__="TestModule")
        mock_module_object_definitions = {mock_module: []}
        mock_scr = Mock(module_object_definitions=mock_module_object_definitions)

        ObjectDiscovery(mock_scr, mock_module).visit(
            ast.parse(
                "def function_1(\n"
                "\t*,\n"
                "\tmy_arg: SmartContractVault,\n"
                "\tmy_arg_2: SmartContractVault | None,\n"
                "\tuntouched_arg: str,\n"
                "\tmy_arg_3: dict[str, tuple[str, SupervisorContractVault]],\n"
                "\tmy_arg_4: list[SmartContractVault],\n"
                "\t) -> SuperviseeContractVault:\n"
                "\treturn 1"
            ).body[0]
        )
        expected_imported_object = ImportedObject(
            name="function_1",
            namespaced_name="TestModule_function_1",
            stmt=ast.parse(
                "def function_1(\n"
                "\t*,\n"
                "\tmy_arg: Any,\n"
                "\tmy_arg_2: Any | None,\n"
                "\tuntouched_arg: str,\n"
                "\tmy_arg_3: dict[str, tuple[str, Any]],\n"
                "\tmy_arg_4: list[Any],\n"
                "\t) -> Any:\n"
                "\treturn 1"
            ).body[0],
            module_from=mock_module,
        )
        self.assertEqual(
            mock_scr.module_object_definitions[mock_module][0], expected_imported_object
        )
        self.assertTrue(
            compare_ast(
                mock_scr.module_object_definitions[mock_module][0].stmt,
                expected_imported_object.stmt,
            )
        )

    def test_object_discovery_strips_vault_typehints_from_function_defs_posonlyargs(self):
        mock_module = Mock(__name__="TestModule")
        mock_module_object_definitions = {mock_module: []}
        mock_scr = Mock(module_object_definitions=mock_module_object_definitions)

        ObjectDiscovery(mock_scr, mock_module).visit(
            ast.parse(
                "def function_1(\n"
                "\tmy_arg: SmartContractVault,\n"
                "\t/,\n"
                "\tmy_arg_2: SmartContractVault | None,\n"
                "\tuntouched_arg: str,\n"
                "\tmy_arg_3: dict[str, tuple[str, SupervisorContractVault]],\n"
                "\tmy_arg_4: list[SmartContractVault],\n"
                "\t) -> SmartContractVault:\n"
                "\treturn 1"
            ).body[0]
        )
        expected_imported_object = ImportedObject(
            name="function_1",
            namespaced_name="TestModule_function_1",
            stmt=ast.parse(
                "def function_1(\n"
                "\tmy_arg: Any,\n"
                "\t/,\n"
                "\tmy_arg_2: Any | None,\n"
                "\tuntouched_arg: str,\n"
                "\tmy_arg_3: dict[str, tuple[str, Any]],\n"
                "\tmy_arg_4: list[Any],\n"
                "\t) -> Any:\n"
                "\treturn 1"
            ).body[0],
            module_from=mock_module,
        )
        self.assertEqual(
            mock_scr.module_object_definitions[mock_module][0], expected_imported_object
        )
        self.assertTrue(
            compare_ast(
                mock_scr.module_object_definitions[mock_module][0].stmt,
                expected_imported_object.stmt,
            )
        )

    def test_object_discovery_strips_vault_typehints_from_function_defs_posonlyargs_inc_vault(self):
        mock_module = Mock(__name__="TestModule")
        mock_module_object_definitions = {mock_module: []}
        mock_scr = Mock(module_object_definitions=mock_module_object_definitions)

        ObjectDiscovery(mock_scr, mock_module).visit(
            ast.parse(
                "def function_1(\n"
                "\tpos_arg: str,\n"
                "\t/,\n"
                "\tmy_arg: SmartContractVault,\n"
                "\tmy_arg_2: SmartContractVault | None,\n"
                "\tuntouched_arg: str,\n"
                "\tmy_arg_3: dict[str, tuple[str, SupervisorContractVault]],\n"
                "\tmy_arg_4: list[SmartContractVault],\n"
                "\t) -> SuperviseeContractVault:\n"
                "\treturn 1"
            ).body[0]
        )
        expected_imported_object = ImportedObject(
            name="function_1",
            namespaced_name="TestModule_function_1",
            stmt=ast.parse(
                "def function_1(\n"
                "\tpos_arg: str,\n"
                "\t/,\n"
                "\tmy_arg: Any,\n"
                "\tmy_arg_2: Any | None,\n"
                "\tuntouched_arg: str,\n"
                "\tmy_arg_3: dict[str, tuple[str, Any]],\n"
                "\tmy_arg_4: list[Any],\n"
                "\t) -> Any:\n"
                "\treturn 1"
            ).body[0],
            module_from=mock_module,
        )
        self.assertEqual(
            mock_scr.module_object_definitions[mock_module][0], expected_imported_object
        )
        self.assertTrue(
            compare_ast(
                mock_scr.module_object_definitions[mock_module][0].stmt,
                expected_imported_object.stmt,
            )
        )

    def test_sort_imported_object_definitions(self):
        scr = SmartContractRenderer(v4_contract_template)
        template = Mock(name="template", __name__="template")
        feature_1 = Mock(name="feature_1", __name__="feature_1")
        feature_2 = Mock(name="feature_2", __name__="feature_2")
        feature_3 = Mock(name="feature_3", __name__="feature_3")
        feature_4 = Mock(name="feature_4", __name__="feature_4")
        utils_1 = Mock(name="utils_1", __name__="utils_1")
        utils_2 = Mock(name="utils_2", __name__="utils_2")
        utils_3 = Mock(name="utils_3", __name__="utils_3")
        utils_4 = Mock(name="utils_4", __name__="utils_4")

        scr.module_import_mapping = {
            template: [
                ImportedModule(name="feature_1", module=feature_1),
                ImportedModule(name="feature_2", module=feature_2),
                ImportedModule(name="feature_3", module=feature_3),
                ImportedModule(name="feature_4", module=feature_4),
            ],
            feature_1: [
                ImportedModule(name="feature_2", module=feature_2),
                ImportedModule(name="feature_3", module=feature_3),
                ImportedModule(name="feature_4", module=feature_4),
                ImportedModule(name="utils_1", module=utils_1),
                ImportedModule(name="utils_2", module=utils_2),
                ImportedModule(name="utils_3", module=utils_3),
                ImportedModule(name="utils_4", module=utils_4),
            ],
            feature_2: [
                ImportedModule(name="feature_3", module=feature_3),
                ImportedModule(name="feature_4", module=feature_4),
                ImportedModule(name="utils_2", module=utils_2),
                ImportedModule(name="utils_3", module=utils_3),
                ImportedModule(name="utils_4", module=utils_4),
            ],
            feature_3: [
                ImportedModule(name="feature_4", module=feature_4),
                ImportedModule(name="utils_3", module=utils_3),
                ImportedModule(name="utils_4", module=utils_4),
            ],
            feature_4: [
                ImportedModule(name="utils_4", module=utils_4),
            ],
        }
        scr.module_object_definitions = {
            feature_1: ["feature_1"],
            feature_2: ["feature_2"],
            feature_3: ["feature_3"],
            feature_4: ["feature_4"],
            utils_1: ["utils_1"],
            utils_2: ["utils_2"],
            utils_3: ["utils_3"],
            utils_4: ["utils_4"],
        }
        scr.root_module = template
        scr._sort_imported_object_definitions()
        self.assertEqual(
            scr.objects_to_import,
            [
                "utils_4",
                "feature_4",
                "utils_3",
                "feature_3",
                "utils_2",
                "feature_2",
                "utils_1",
                "feature_1",
            ],
        )

    def test_sort_imported_object_definitions_multiple_transient_deps(self):
        scr = SmartContractRenderer(v4_contract_template)
        aus_mortgage = Mock(name="aus_mortgage", __name__="aus_mortgage")
        utils = Mock(name="utils", __name__="library.features.common.utils")
        interest_accrual = Mock(
            name="interest_accrual", __name__="library.features.lending.interest_accrual"
        )
        interest_application = Mock(
            name="interest_application", __name__="library.features.interest.interest_application"
        )
        fixed_rate = Mock(name="fixed_rate", __name__="library.features.interest.fixed_rate")
        variable_rate = Mock(
            name="variable_rate", __name__="library.features.interest.variable_rate"
        )
        fixed_to_variable_rate = Mock(
            name="fixed_to_variable_rate",
            __name__="library.features.interest.fixed_to_variable_rate",
        )
        scr.module_import_mapping = {
            aus_mortgage: [
                ImportedModule(name="utils", module=utils),
                ImportedModule(name="interest_application", module=interest_application),
                ImportedModule(name="fixed_to_variable_rate", module=fixed_to_variable_rate),
            ],
            interest_application: [
                ImportedModule(name="utils", module=utils),
                ImportedModule(name="interest_accrual", module=interest_accrual),
            ],
            fixed_to_variable_rate: [
                ImportedModule(name="utils", module=utils),
                ImportedModule(name="fixed_rate", module=fixed_rate),
                ImportedModule(name="variable_rate", module=variable_rate),
            ],
            fixed_rate: [
                ImportedModule(name="utils", module=utils),
            ],
            variable_rate: [
                ImportedModule(name="utils", module=utils),
            ],
        }
        scr.module_object_definitions = {
            utils: ["library.features.common.utils"],
            interest_accrual: ["library.features.lending.interest_accrual"],
            interest_application: ["library.features.interest.interest_application"],
            fixed_rate: ["library.features.interest.fixed_rate"],
            variable_rate: ["library.features.interest.variable_rate"],
            fixed_to_variable_rate: ["library.features.interest.fixed_to_variable_rate"],
        }
        scr.root_module = aus_mortgage
        scr._sort_imported_object_definitions()
        self.assertEqual(
            scr.objects_to_import,
            [
                "library.features.common.utils",
                "library.features.interest.fixed_rate",
                "library.features.interest.variable_rate",
                "library.features.interest.fixed_to_variable_rate",
                "library.features.lending.interest_accrual",
                "library.features.interest.interest_application",
            ],
        )

    @patch.object(renderer, "format_str")
    @patch.object(renderer, "reorder_nodes")
    @patch.object(renderer, "remove_quotes_from_module_headers")
    @patch.object(renderer.SmartContractRenderer, "_add_any_typing_import")
    @patch.object(renderer.SmartContractRenderer, "_rename_imported_module_references")
    @patch.object(renderer.SmartContractRenderer, "_rename_imported_object_definitions")
    @patch.object(renderer.SmartContractRenderer, "_sort_imported_object_definitions")
    @patch.object(renderer.SmartContractRenderer, "_remove_unused_objects")
    @patch.object(renderer.SmartContractRenderer, "_add_imported_stmts_to_root_tree")
    @patch.object(renderer.SmartContractRenderer, "_replace_decorator_constants")
    @patch.object(renderer.SmartContractRenderer, "_write_smart_contract_to_file")
    def test_render_all_flags_true(
        self,
        mock_write_smart_contract_to_file: Mock,
        mock_replace_decorator_constants: Mock,
        mock_add_imported_stmts_to_root_tree: Mock,
        mock_remove_unused_objects: Mock,
        mock_sort_imported_object_definitions: Mock,
        mock_rename_imported_object_definitions: Mock,
        mock_rename_imported_module_references: Mock,
        mock_add_any_typing_import: Mock,
        mock_remove_quotes_from_module_headers: Mock,
        mock_reorder_nodes: Mock,
        mock_format_str: Mock,
    ):
        def format_str_side_effect(*args, **kwargs):
            return args[0]

        mock_format_str.side_effect = format_str_side_effect
        mock_remove_quotes_from_module_headers.return_value = ""

        scr_config = RendererConfig(
            include_autogen_warning=True,
            use_git=True,
            use_full_filepath_in_headers=True,
            render_metadata_at_top_of_file=True,
            apply_formatting=True,
        )
        scr = SmartContractRenderer(module_1, scr_config)
        mock_reorder_nodes.return_value = (scr.root_tree.body, False)

        scr.render(write_to_file=True)

        # always called during render()
        mock_add_any_typing_import.assert_called_once()
        mock_rename_imported_module_references.assert_called_once()
        mock_rename_imported_object_definitions.assert_called_once()
        mock_sort_imported_object_definitions.assert_called_once()
        mock_remove_unused_objects.assert_called_once()
        mock_add_imported_stmts_to_root_tree.assert_called_once()
        mock_replace_decorator_constants.assert_called_once()
        mock_remove_quotes_from_module_headers.assert_called_once()

        # optionally controlled by boolean flags
        # render_metadata_at_top_of_file
        mock_reorder_nodes.assert_called_once()
        # apply_formatting
        mock_format_str.assert_called_once()
        # include_autogen_warning
        self.assertTrue(
            scr_config.autogen_warning in scr.rendered_contract,
            "expected include_autogen_warning flag to be True",
        )
        # write_to_file
        mock_write_smart_contract_to_file.assert_called_once()

    @patch.object(renderer, "format_str")
    @patch.object(renderer, "reorder_nodes")
    @patch.object(renderer, "remove_quotes_from_module_headers")
    @patch.object(renderer.SmartContractRenderer, "_add_any_typing_import")
    @patch.object(renderer.SmartContractRenderer, "_rename_imported_module_references")
    @patch.object(renderer.SmartContractRenderer, "_rename_imported_object_definitions")
    @patch.object(renderer.SmartContractRenderer, "_sort_imported_object_definitions")
    @patch.object(renderer.SmartContractRenderer, "_remove_unused_objects")
    @patch.object(renderer.SmartContractRenderer, "_add_imported_stmts_to_root_tree")
    @patch.object(renderer.SmartContractRenderer, "_replace_decorator_constants")
    @patch.object(renderer.SmartContractRenderer, "_write_smart_contract_to_file")
    def test_render_all_flags_false(
        self,
        mock_write_smart_contract_to_file: Mock,
        mock_replace_decorator_constants: Mock,
        mock_add_imported_stmts_to_root_tree: Mock,
        mock_remove_unused_objects: Mock,
        mock_sort_imported_object_definitions: Mock,
        mock_rename_imported_object_definitions: Mock,
        mock_rename_imported_module_references: Mock,
        mock_add_any_typing_import: Mock,
        mock_remove_quotes_from_module_headers: Mock,
        mock_reorder_nodes: Mock,
        mock_format_str: Mock,
    ):
        scr_config = RendererConfig(
            include_autogen_warning=False,
            render_metadata_at_top_of_file=False,
            apply_formatting=False,
        )
        scr = SmartContractRenderer(module_1, scr_config)
        scr.render(write_to_file=False)

        # always called during render()
        mock_add_any_typing_import.assert_called_once()
        mock_rename_imported_module_references.assert_called_once()
        mock_rename_imported_object_definitions.assert_called_once()
        mock_sort_imported_object_definitions.assert_called_once()
        mock_remove_unused_objects.assert_called_once()
        mock_add_imported_stmts_to_root_tree.assert_called_once()
        mock_replace_decorator_constants.assert_called_once()
        mock_remove_quotes_from_module_headers.assert_called_once()

        # optionally controlled by boolean flags
        # render_metadata_at_top_of_file
        mock_reorder_nodes.assert_not_called()
        # apply_formatting
        mock_format_str.assert_not_called()
        # include_autogen_warning
        self.assertFalse(
            scr_config.autogen_warning in scr.rendered_contract,
            "expected include_autogen_warning flag to be False",
        )
        # write_to_file
        mock_write_smart_contract_to_file.assert_not_called()

    @patch.object(renderer, "is_module_in_contracts_language_v4")
    def test_render_init_fails_for_non_v4_contracts(
        self, mock_is_module_in_contracts_language_v4: Mock
    ):
        mock_is_module_in_contracts_language_v4.return_value = False
        with self.assertRaises(ValueError):
            SmartContractRenderer(module_1)


if __name__ == "__main__":
    unittest.main()
