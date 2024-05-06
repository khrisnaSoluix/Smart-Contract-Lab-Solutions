# flake8: noqa

# inception sdk
import inception_sdk.tools.renderer.test.feature.test_resources.test_import_repeated_definitions.module_2 as module_2
import inception_sdk.tools.renderer.test.feature.test_resources.test_import_repeated_definitions.module_3 as module_3


def function_1():
    a = module_2.CONST_1
    b = module_2.CONST_2
    c = module_3.CONST_1
    d = module_3.CONST_2
