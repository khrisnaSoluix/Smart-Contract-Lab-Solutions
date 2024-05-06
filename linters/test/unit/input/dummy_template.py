# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# common imports
from library.features.v3.common.common_imports import *  # noqa: F403

display_name = "Contract"
api = "3.9.0"
version = "1.0.0"
summary = "Contract"
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
        description="Gross Interest Rate",
        display_name="Rate paid on positive balances",
    ),
    Parameter(
        name="loan_start_date",
        shape=DateShape(min_date=datetime.min, max_date=datetime.max),
        level=Level.INSTANCE,
        description="Start of the loan contract terms",
        display_name="Contract effective date",
        default_value=datetime.utcnow(),
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
]


@requires(event_type="ACCRUE_INTEREST", parameters=True, balances="latest")
def scheduled_code(event_type: str, effective_date: datetime) -> None:
    now = datetime.now()
    utcnow = datetime.utcnow()


@requires(parameters=True, balances="latest")
def pre_posting_code(postings: PostingInstructionBatch, effective_date: datetime) -> None:
    now = datetime.now()
    utcnow = datetime.utcnow()


event_types = [EventType(name="name1", scheduler_tag_ids=["tag1"])]
event_types.append(EventType(name="name2", scheduler_tag_ids=["tag2"]))
event_types += [EventType(name="name3", scheduler_tag_ids=["tag3"])]
event_types[len(event_types) :] = [EventType(name="name4", scheduler_tag_ids=["tag4"])]


def extend_event_types() -> None:
    # this function is *not* a hook/helper function, so error should be raised
    event_types.extend([EventType(name="name5", scheduler_tag_ids=["tag5"])])


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
    length = _pre_parameter_change_code_helper_function(vault, parameters)
    if length:
        return parameters  # this is local 'parameters', so no error raised


def _pre_parameter_change_code_helper_function(vault, parameters):
    if _pre_parameter_change_code_nested_helper_function(parameters):
        return len(parameters)  # this is within hook helper function, so no error raised


def _pre_parameter_change_code_nested_helper_function(parameters) -> int:
    return len(parameters)  # this is within hook helper function, so no error raised


# flake8: noqa: F821
