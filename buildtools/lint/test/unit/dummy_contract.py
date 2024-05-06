# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
display_name = "Contract with Calendar declarations"
api = "3.9.0"
version = "1.0.0"
summary = "Contract with calendars"
parameters = [
    Parameter(
        name="denomination",
        shape=DenominationShape,
        level=Level.TEMPLATE,
        description="Default denomination.",
        display_name="Default denomination for the contract.",
    ),
    Parameter(
        name="interest_rate",
        shape=NumberShape(kind=NumberKind.PERCENTAGE, min_value=0, max_value=1, step=0.01),
        level=Level.TEMPLATE,
        description="Gross Interest Reate",
        display_name="Rate paid on positive balances",
    ),
]


@requires(event_type="ACCRUE_INTEREST", parameters=True, balances="latest")
def scheduled_code(event_type, effective_date):
    now = datetime.now()
    utcnow = datetime.utcnow()


@requires(parameters=True, balances="latest")
def pre_posting_code():
    now = datetime.now()
    utcnow = datetime.utcnow()


event_types = [EventType(name="name1", scheduler_tag_ids=["tag1"])]
event_types.append(EventType(name="name2", scheduler_tag_ids=["tag2"]))
event_types += [EventType(name="name3", scheduler_tag_ids=["tag3"])]
event_types[len(event_types) :] = [EventType(name="name4", scheduler_tag_ids=["tag4"])]


def extend_event_types():
    # this function is *not* a hook/helper function, so error should be raised
    event_types.extend(EventType(name="name5", scheduler_tag_ids=["tag5"]))


extend_event_types()

global_parameters = []
global_parameters.extend([""])

parameters += [""]

supported_denominations = []
supported_denominations.append("")

event_types_groups = []
event_types_groups.extend([""])

contract_module_imports = []
contract_module_imports += [""]

data_fetchers = []
data_fetchers.append("")


@requires(parameters=True, balances="latest")
def pre_parameter_change_code(parameters, effective_date):
    length = _pre_parameter_change_code_helper_function(parameters)
    if length:
        return parameters  # this is local 'parameters', so no error raised


def _pre_parameter_change_code_helper_function(parameters):
    if _pre_parameter_change_code_nested_helper_function(parameters):
        return len(parameters)  # this is within hook helper function, so no error raised


def _pre_parameter_change_code_nested_helper_function(parameters):
    return len(parameters)  # this is within hook helper function, so no error raised


# flake8: noqa: F821
