# inception sdk
import inception_sdk.tools.renderer.test.feature.test_resources.test_import.module_1 as m1
api = "4.0.0"
attribute_1 = m1.attribute_1


def function_1() -> str:
    return m1.function_1()


def function_2() -> str:
    return m1.function_2("b")


attribute_2 = m1.function_2(function_1())
