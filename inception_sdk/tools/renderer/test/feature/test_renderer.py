# standard libs
import unittest
from types import ModuleType
from unittest import TestCase
from unittest.mock import MagicMock, patch

# inception sdk
from inception_sdk.tools.renderer import renderer
from inception_sdk.tools.renderer.render_utils import RenderException
from inception_sdk.tools.renderer.renderer import RendererConfig, SmartContractRenderer
from inception_sdk.tools.renderer.test.feature.test_resources.test_import import (
    import_single_module,
)
from inception_sdk.tools.renderer.test.feature.test_resources.test_import_api_extensions import (
    import_api_extensions,
    import_api_extensions_kwargs,
    import_api_extensions_typing_any,
    import_api_extensions_typing_other,
)
from inception_sdk.tools.renderer.test.feature.test_resources.test_import_multiple_children import (
    import_multiple_children,
)
from inception_sdk.tools.renderer.test.feature.test_resources.test_import_multiple_depths import (
    import_multiple_depths,
)
from inception_sdk.tools.renderer.test.feature.test_resources.test_import_star import (
    import_star_from_contracts_api,
    import_star_from_datetime,
)
from inception_sdk.tools.renderer.test.feature.test_resources.test_invalid_import import (
    import_no_alias,
    import_sys,
    import_third_party_library,
)
from inception_sdk.tools.renderer.test.feature.test_resources.test_invalid_imports import (
    import_contracts_api_directly,
    import_invalid_method,
    import_invalid_native,
    import_math_with_alias,
)
from inception_sdk.tools.renderer.test.feature.test_resources.test_valid_imports import (
    valid_imports,
)

from inception_sdk.tools.renderer.test.feature.test_resources.test_replace_decorator_constants import (  # noqa
    replace_decorator_constants,
)

from inception_sdk.tools.renderer.test.feature.test_resources.test_import_repeated_definitions import (  # noqa
    import_repeated_definitions,
)


TEST_EXPECTED_OUTPUT_ROOT = "inception_sdk/tools/renderer/test/feature/test_resources/"


class SmartContractRendererTest(TestCase):
    maxDiff = None

    def setUp(self) -> None:
        return super().setUp()

    def _get_renderer_config(self) -> RendererConfig:
        return RendererConfig(
            autogen_warning="# Code auto-generated",
            include_autogen_warning=True,
            render_metadata_at_top_of_file=True,
            use_full_filepath_in_headers=False,
        )

    def _run_render_test(
        self,
        template_module: ModuleType,
        expected_output_filename: str,
        render_config: RendererConfig | None = None,
    ):
        render_config = render_config or self._get_renderer_config()
        scr = SmartContractRenderer(template_module, renderer_config=render_config)
        scr.render(write_to_file=False)

        with open(expected_output_filename) as file:
            expected_output = file.read()
        self.assertEqual(scr.rendered_contract, expected_output)

    def test_import(self):
        """
        This test is to ensure that only imported symbols are renamed when sharing the same
        object names across the root module and imported module.
        """
        self._run_render_test(
            import_single_module, TEST_EXPECTED_OUTPUT_ROOT + "test_import/output.txt"
        )

    def test_import_multiple_children(self):
        """
        This test is to ensure that when chaining imports of a common module across multiple
        modules, the common module objects are only imported once.
        """
        self._run_render_test(
            import_multiple_children,
            TEST_EXPECTED_OUTPUT_ROOT + "test_import_multiple_children/output.txt",
        )

    def test_import_multiple_depths(self):
        """
        This test is to ensure that when importing the same thing at different depths of children,
        the import order is correct (the deepest imported child should always be at the top of the
        output) E.g:
        Module 1 imports Module 2
        Module 2 imports Module 3
        Module 1 imports Module 3
        Module 4 imports Module 2
        Template imports Module 1, Module 3 and Module 4
        There is also a specific ordering applied to the output, ensuring that those defined in
        sc_order are moved to the top of the output file in that specific order.
        """
        scr_config = self._get_renderer_config()
        scr_config.sc_order = ["function_1", "attribute_1", "attribute_2", "attribute_4"]

        self._run_render_test(
            import_multiple_depths,
            TEST_EXPECTED_OUTPUT_ROOT + "test_import_multiple_depths/output.txt",
            render_config=scr_config,
        )

    def test_invalid_import_no_alias(self):
        with self.assertRaises(RenderException) as test:
            scr = SmartContractRenderer(
                import_no_alias, renderer_config=self._get_renderer_config()
            )
            scr.render(write_to_file=False)
        self.assertIn("Import statements must include an 'as' alias", test.exception.args[0])

    def test_contract_valid_from_imports_render(self):
        render_config = self._get_renderer_config()
        self._run_render_test(
            valid_imports,
            TEST_EXPECTED_OUTPUT_ROOT + "test_valid_imports/output.txt",
            render_config=render_config,
        )

    def test_contract_invalid_import(self):
        with self.assertRaises(RenderException) as test:
            scr = SmartContractRenderer(import_sys, renderer_config=self._get_renderer_config())
            scr.render(write_to_file=False)
        self.assertEqual(
            "import 'sys' (Line: 2 Col: 0) : <module 'sys' (built-in)> is not a whitelisted "
            "module.",
            test.exception.args[0],
        )

    def test_contract_import_star_contracts_api(self):
        with self.assertRaises(RenderException) as test:
            scr = SmartContractRenderer(
                import_star_from_contracts_api,
                renderer_config=self._get_renderer_config(),
            )
            scr.render(write_to_file=False)
        self.assertIn(
            "Importing '*' from module_name='contracts_api' is against best practices.",
            test.exception.args[0],
        )

    def test_contract_import_star_datetime(self):
        with self.assertRaises(RenderException) as test:
            scr = SmartContractRenderer(
                import_star_from_datetime,
                renderer_config=self._get_renderer_config(),
            )
            scr.render(write_to_file=False)
        self.assertIn(
            "Importing * from module_name='datetime' is not allowed.",
            test.exception.args[0],
        )

    def test_contract_invalid_contracts_api_direct_import(self):
        with self.assertRaises(RenderException) as test:
            scr = SmartContractRenderer(
                import_contracts_api_directly,
                renderer_config=self._get_renderer_config(),
            )
            scr.render(write_to_file=False)
        self.assertIn(
            "contracts_api cannot be imported directly:",
            test.exception.args[0],
        )

    def test_contract_invalid_object_import(self):
        with self.assertRaises(RenderException) as test:
            scr = SmartContractRenderer(
                import_invalid_method,
                renderer_config=self._get_renderer_config(),
            )
            scr.render(write_to_file=False)
        self.assertIn(
            "Importing tzinfo from module_name='datetime' is not allowed.",
            test.exception.args[0],
        )

    def test_contract_invalid_from_import(self):
        with self.assertRaises(RenderException) as e:
            scr = SmartContractRenderer(
                import_invalid_native,
                renderer_config=self._get_renderer_config(),
            )
            scr.render(write_to_file=False)
        self.assertIn(
            "`from <x> import <y>` syntax is only available for native python modules exposed by "
            "the Contracts API. `pathlib` is not such a module. Use `import <x.y> as y` syntax "
            "instead.",
            e.exception.args[0],
        )

    def test_contract_import_math_with_alias(self):
        with self.assertRaises(RenderException) as e:
            scr = SmartContractRenderer(
                import_math_with_alias,
                renderer_config=self._get_renderer_config(),
            )
            scr.render(write_to_file=False)
        self.assertIn(
            "module_name='math' must be imported directly and must not be aliased:",
            e.exception.args[0],
        )

    def test_import_api_extensions(self):
        """
        Checks that API extensions are correctly replaced by Any and Any is added to imports
        """
        self.maxDiff = None
        self._run_render_test(
            import_api_extensions,
            TEST_EXPECTED_OUTPUT_ROOT + "test_import_api_extensions/output.txt",
            render_config=self._get_renderer_config(),
        )

    def test_import_api_extensions_kwargs(self):
        """
        Checks that API extensions are correctly replaced by Any and Any is added to imports
        when using kwargs only syntax (*)
        """
        self.maxDiff = None
        self._run_render_test(
            import_api_extensions_kwargs,
            TEST_EXPECTED_OUTPUT_ROOT + "test_import_api_extensions/output_kwargs.txt",
            render_config=self._get_renderer_config(),
        )

    def test_import_api_extensions_existing_typing_other(self):
        """
        Checks that API extensions are correctly replaced by Any and Any is added to existing typing
        imports that don't already include Any
        """
        self.maxDiff = None
        self._run_render_test(
            import_api_extensions_typing_other,
            TEST_EXPECTED_OUTPUT_ROOT + "test_import_api_extensions/output_other.txt",
            render_config=self._get_renderer_config(),
        )

    def test_import_api_extensions_existing_typing_any(self):
        """
        Checks that API extensions are correctly replaced by Any and Any is not added to typing
        imports if already present
        """
        self.maxDiff = None
        self._run_render_test(
            import_api_extensions_typing_any,
            TEST_EXPECTED_OUTPUT_ROOT + "test_import_api_extensions/output_any.txt",
            render_config=self._get_renderer_config(),
        )

    def test_invalid_import_third_party_library(self):
        with self.assertRaises(RenderException) as test:
            scr = SmartContractRenderer(
                import_third_party_library,
                renderer_config=self._get_renderer_config(),
            )
            scr.render(write_to_file=False)
        self.assertIn(
            "is attempting to import a third-party module",
            test.exception.args[0],
        )

    def test_replace_decorator_constants(self):
        self._run_render_test(
            replace_decorator_constants,
            TEST_EXPECTED_OUTPUT_ROOT + "test_replace_decorator_constants/output.txt",
        )

    @patch.object(renderer, "log")
    def test_import_repeated_constants(self, mock_log: MagicMock):
        self._run_render_test(
            import_repeated_definitions,
            TEST_EXPECTED_OUTPUT_ROOT + "test_import_repeated_definitions/output.txt",
        )

        # module 2 and 3 both have a repeated definition
        self.assertEqual(mock_log.warning.call_count, 2)


if __name__ == "__main__":
    unittest.main()
