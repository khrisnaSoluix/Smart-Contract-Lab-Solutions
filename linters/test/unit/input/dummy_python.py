# This is a dummy python file to check that our linter does not interpret it as a Contract file to
# lint, and doesn't fall over when it encounters non-contract syntax (e.g. classes and imports)
# standard libs
from datetime import datetime

SOME_CONSTANT = 123


def my_method(a: str) -> bool:
    return len(a) > 1


class MyClass:
    pass


datetime.now()

event_types = []
event_types.append("event")

global_parameters = []
global_parameters.extend([""])

parameters = []
parameters += [""]

supported_denominations = []
supported_denominations.append("")

event_types_groups = []
event_types_groups.extend([""])

contract_module_imports = []
contract_module_imports += [""]

data_fetchers = []
data_fetchers.append("")


def pre_parameter_change_code(parameters):
    if True:
        return parameters
