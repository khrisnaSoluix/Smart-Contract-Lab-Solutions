attribute_1 = "a"


def function_1():
    return attribute_1


def function_2(param_1):
    param_1 = attribute_1 + param_1
    return param_1


attribute_2 = function_2(attribute_1)
