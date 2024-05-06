# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# features
import library.features.v4.common.utils as utils

PARAM_CONSTANT = "parameter_constant"


def helper_1(vault):
    var = utils.get_parameter(vault, "parameter_name")


def helper_2(vault):
    return str(utils.get_parameter(vault, name="parameter_name"))


def helper_3(vault):
    var = utils.get_parameter(vault, name=PARAM_CONSTANT)


# flake8: noqa
