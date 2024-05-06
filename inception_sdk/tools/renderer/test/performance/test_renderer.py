# standard libs
import os
import sys
import unittest
from contextlib import contextmanager
from importlib import util
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

# inception sdk
import inception_sdk.tools.renderer.renderer as renderer
from inception_sdk.tools.renderer.render_utils import combine_module_and_object_name
from inception_sdk.tools.renderer.renderer import (
    RenameDefinitionTransformer,
    RenameReferenceTransformer,
    RendererConfig,
    SmartContractRenderer,
)


@contextmanager
def add_to_path(p):
    """
    Temporarily add to the system path variable.
    """
    old_path = sys.path
    sys.path = sys.path[:]
    sys.path.insert(0, p)
    try:
        yield
    finally:
        sys.path = old_path


def path_import(absolute_path, module_name):
    """implementation taken from
    https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly"""
    with add_to_path(os.path.dirname(absolute_path)):
        spec = util.spec_from_file_location(module_name, absolute_path)
        module = util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module


class RendererPerformanceTest(TestCase):
    """
    This test creates a temporary directory and test files. See generate_imported_modules.
    The purpose of these tests is to ensure that the number of calls to expensive operations
    increases at an expected rate as complexity increases.
    """

    def setUp(self) -> None:
        self.temp_test_data_path = Path(os.path.dirname(os.path.realpath(__file__))) / "temp_data"
        self.temp_test_data_path.mkdir(exist_ok=True)
        self.renderer_config = RendererConfig()
        return super().setUp()

    def tearDown(self) -> None:
        if self.imported_modules:
            for module in self.imported_modules.values():
                os.remove(module.__file__)
        self.imported_modules = {}
        return super().tearDown()

    def generate_imported_modules(self, number_of_modules: int, import_depth: int) -> None:
        """
        Generates test Python module files. The number of module files generated is determined by a
        combination of number_of_modules and import_depth. Each of the module files generated will
        declare an attribute (e.g. module1_attr = 1) and depending on import_depth will also
        declare an attribute referencing a common child module (e.g. common_attr_1 = 1).
        Each common module specified by import_depth will also declare an attribute
        referencing the previously created common module. (e.g. common_attr_1 = common.attr1) along
        with its own attribute (e.g. attr1 = 1).

        Here is an example where number_of_modules = 1 and import_depth = 4:
        (common0.py)
        attr0 = 1

        (common1.py)
        attr1 = 1
        import common0
        common_attr_0 = common0.attr0

        (common2.py)
        attr2 = 1
        import common0
        common_attr_0 = common0.attr0
        import common1
        common_attr_1 = common1.attr1

        (module0.py)
        module0_attr = 1
        import common0
        module0_attr0 = common0.attr0
        import common1
        module0_attr1 = common1.attr1
        import common2
        module0_attr2 = common2.attr2

        (template.py)
        import module0
        module0_a = module0.module0_attr
        """

        imported_modules = {}
        template = 'api = "4.0.0"'

        for i in range(max(import_depth - 1, 0)):
            common_path = self.temp_test_data_path / f"common{i}.py"
            with open(common_path, "w+") as file:
                s = f"\nattr{i} = 1\n"
                if i > 0:
                    for j in range(i):
                        s += (
                            f"\nimport common{j} as common{j}\ncommon_attr_{j} = "
                            f"common{j}.attr{j}\n"
                        )
                file.write(s)
            imported_modules.update({f"common{i}": path_import(str(common_path), f"common{i}")})

        for i in range(number_of_modules):
            module_name = f"module{i}"
            p = self.temp_test_data_path / f"{module_name}.py"
            with open(p, "w+") as file:
                s = f"\n{module_name}_attr = 1\n"
                for i in range(max(import_depth - 1, 0)):
                    s += (
                        f"\nimport common{i} as common{i}\n{module_name}_attr{i} = "
                        f"common{i}.attr{i}"
                    )
                file.write(s)
            imported_modules.update({module_name: path_import(str(p), module_name)})
            template += (
                f"\nimport {module_name} as {module_name}\n"
                f"{module_name}_a = {module_name}.{module_name}_attr\n"
            )

        template_path = self.temp_test_data_path / "template.py"
        with open(template_path, "w+") as file:
            file.write(template)
            imported_modules.update({"template": path_import(str(template_path), "template")})

        for name, module in imported_modules.items():
            setattr(imported_modules["template"], name, module)

        self.imported_modules = imported_modules

    @patch.object(renderer, "combine_module_and_object_name")
    @patch.object(RenameDefinitionTransformer, "visit")
    @patch.object(RenameReferenceTransformer, "visit")
    def test_renderer_performance_100_by_1(
        self,
        mock_RenameReferenceTransformer_visit: Mock,
        mock_RenameDefinitionTransformer_visit: Mock,
        mock_combine_module_and_object_name: Mock,
    ):
        """
        Import 100 modules with a single import depth.
        E.g the template will import 100 modules.
        """
        mock_combine_module_and_object_name.side_effect = combine_module_and_object_name
        self.generate_imported_modules(100, 1)
        scr = SmartContractRenderer(self.imported_modules["template"], self.renderer_config)
        scr.render(False)
        # 100 calls for each object in each module (1 to 1)
        self.assertEqual(mock_combine_module_and_object_name.call_count, 100)
        # 100 calls for each object in template module + api statement
        self.assertEqual(mock_RenameReferenceTransformer_visit.call_count, 101)
        # 1 imported object for each of the 100 imported modules
        self.assertEqual(mock_RenameDefinitionTransformer_visit.call_count, 100)

    @patch.object(renderer, "combine_module_and_object_name")
    @patch.object(RenameDefinitionTransformer, "visit")
    @patch.object(RenameReferenceTransformer, "visit")
    def test_renderer_performance_100_by_2(
        self,
        mock_RenameReferenceTransformer_visit: Mock,
        mock_RenameDefinitionTransformer_visit: Mock,
        mock_combine_module_and_object_name: Mock,
    ):
        """
        Import 100 modules with an import depth of 2.
        E.g the template will import 100 modules and each of those will import a common module
        """
        mock_combine_module_and_object_name.side_effect = combine_module_and_object_name
        self.generate_imported_modules(100, 2)
        scr = SmartContractRenderer(self.imported_modules["template"], self.renderer_config)
        scr.render(False)
        # 100 imported modules and 1 common module
        self.assertEqual(len(scr.modules_visited), 101)
        # 100 for each imported module object (2 per module) and 1 for common module objects
        self.assertEqual(mock_combine_module_and_object_name.call_count, 201)
        # called once per template object (100) and 2 times per imported module object (200)
        # + api statement
        self.assertEqual(mock_RenameReferenceTransformer_visit.call_count, 301)
        # called once per object in imported modules (200) and once per common module object
        # definition (1 in total)
        self.assertEqual(mock_RenameDefinitionTransformer_visit.call_count, 201)

    @patch.object(renderer, "combine_module_and_object_name")
    @patch.object(RenameDefinitionTransformer, "visit")
    @patch.object(RenameReferenceTransformer, "visit")
    def test_renderer_performance_100_by_3(
        self,
        mock_RenameReferenceTransformer_visit: Mock,
        mock_RenameDefinitionTransformer_visit: Mock,
        mock_combine_module_and_object_name: Mock,
    ):
        """
        Import 100 modules with an import depth of 3.
        E.g the template will import 100 modules, each of which will import 2 more child modules.
        --Template
            |--Module (x100)
                |--Module
                    |--Module
            ...
        """
        mock_combine_module_and_object_name.side_effect = combine_module_and_object_name
        self.generate_imported_modules(100, 3)
        scr = SmartContractRenderer(self.imported_modules["template"], self.renderer_config)
        scr.render(False)
        # 100 imported modules and 2 common modules
        self.assertEqual(len(scr.modules_visited), 102)
        # 100 for each imported module object (3 per module) and 3 for common module objects
        self.assertEqual(mock_combine_module_and_object_name.call_count, 303)
        # called once per template object (100) and 3 times per imported module object (300)
        # and once for each common module object that imports another module (2 in total)
        # (the first common module doesn't import anything so isn't included here)
        # + api statement
        self.assertEqual(mock_RenameReferenceTransformer_visit.call_count, 403)
        # called once per object in imported modules (300) and once per common module object
        # definition (3 in total) (the first common module is included here as it defines an
        # attribute)
        self.assertEqual(mock_RenameDefinitionTransformer_visit.call_count, 303)

    @patch.object(renderer, "combine_module_and_object_name")
    @patch.object(RenameDefinitionTransformer, "visit")
    @patch.object(RenameReferenceTransformer, "visit")
    def test_renderer_performance_100_by_4(
        self,
        mock_RenameReferenceTransformer_visit: Mock,
        mock_RenameDefinitionTransformer_visit: Mock,
        mock_combine_module_and_object_name: Mock,
    ):
        """
        Import 100 modules with an import depth of 4.
        """
        mock_combine_module_and_object_name.side_effect = combine_module_and_object_name
        self.generate_imported_modules(100, 4)
        scr = SmartContractRenderer(self.imported_modules["template"], self.renderer_config)
        scr.render(False)
        # 100 imported modules and 3 common modules
        self.assertEqual(len(scr.modules_visited), 103)
        # 100 for each imported module object (4 per module) and 6 for common module objects
        self.assertEqual(mock_combine_module_and_object_name.call_count, 406)
        # called once per template object (100) and 4 times per imported module object (400)
        # and once for each common module object that imports another module (5 in total)
        # (the first common module doesn't import anything so isn't included here)
        # + api statement
        self.assertEqual(mock_RenameReferenceTransformer_visit.call_count, 506)
        # called once per object in imported modules (400) and once per common module object
        # definition (6 in total) (the first common module is included here as it defines an
        # attribute)
        self.assertEqual(mock_RenameDefinitionTransformer_visit.call_count, 406)


if __name__ == "__main__":
    unittest.main()
