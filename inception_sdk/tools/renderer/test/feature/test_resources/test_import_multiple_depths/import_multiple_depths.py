# inception sdk
import inception_sdk.tools.renderer.test.feature.test_resources.test_import_multiple_depths.module_1 as module_1  # noqa: E501
import inception_sdk.tools.renderer.test.feature.test_resources.test_import_multiple_depths.module_3 as module_3  # noqa: E501
import inception_sdk.tools.renderer.test.feature.test_resources.test_import_multiple_depths.module_4 as module_4  # noqa: E501

api = "4.0.0"
attribute_3 = module_3.attribute_1
attribute_4 = module_4.attribute_4
attribute_1 = module_1.attribute_1
attribute_2 = module_1.attribute_2


def function_1() -> str:
    return attribute_1
