# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
display_name = "Supervisor Contract"
api = "3.9.0"
version = "1.0.0"

supervised_smart_contracts = []


def execution_schedules() -> list[tuple[str, dict[str, Any]]]:
    now = datetime.now()
    utcnow = datetime.utcnow()
    return []


@requires(parameters=True, balances="latest")
def pre_posting_code(postings, effective_date) -> None:
    now = datetime.now()
    utcnow = datetime.utcnow()


event_types = [EventType(name="name1", scheduler_tag_ids=["tag1"])]
event_types.append(EventType(name="name2", scheduler_tag_ids=["tag2"]))
event_types += [EventType(name="name3", scheduler_tag_ids=["tag3"])]
event_types[len(event_types) :] = [EventType(name="name4", scheduler_tag_ids=["tag4"])]


def extend_event_types() -> None:
    # this function is *not* a hook/helper function, so error should be raised
    event_types.extend(EventType(name="name5", scheduler_tag_ids=["tag5"]))


extend_event_types()

global_parameters = []
global_parameters.extend([""])

supported_denominations = []
supported_denominations.append("")

event_types_groups = []
event_types_groups.extend([""])

contract_module_imports = []
contract_module_imports += [""]

data_fetchers = []
data_fetchers.append("")


@requires(event_type="ACCRUE_INTEREST", parameters=True, balances="latest")
def scheduled_code(event_type, effective_date) -> None:
    length = _scheduled_code_helper_function(event_type)
    if length:
        return event_type


def _scheduled_code_helper_function(event_type):
    if _scheduled_code_nested_helper_function(event_type):
        return len(event_type)


def _scheduled_code_nested_helper_function(event_type):
    return len(event_type)


# flake8: noqa: F821
