# standard libs
import ast
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from functools import reduce
from typing import Any, Iterable
from unittest.mock import Mock

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def ac_coverage(covered_ac_list: list[str], /, **kwargs):
    """
    To be used as a decorator on tests to provide a mapping for
    CBF ACs to the tests which validate this specific AC

    The AC list must contain unique references which follow
    the format `CPP-111-AC01` where:
    - CPP-111 is the unique CPP number associated with the CBF
    - AC01 is the AC index provided in that CBF

    See `tools/test_coverage_script/README.md` for documentation

    :param covered_ac_list: provided as a typehint, but it is
    enforced as a positional argument
    """

    def _ac_coverage(func):
        return func

    return _ac_coverage


class CLUDuplicateResourceId(BaseException):
    pass


class CLUMissingMapping(BaseException):
    pass


@dataclass
class ResourceDependency:
    # identifies the resource in which the dependency is found
    source_id: str
    # identifies the resource on which the source resource is dependent on
    target_id: str
    # the start position of the dependency in the source content, including `&{`
    start_position: int
    # the end position of the dependency in the source content, including `}`
    end_position: int


def _parse_clu_reference(reference: str) -> str:
    """
    parse a CLU reference specified as `resource_id`. The `resource_id:resource_field` syntax is
    not yet supported.
    :return: the resource id
    """

    if ":" in reference:
        raise ValueError(
            f"Reference `{reference}` contains `resource_id:resource_field` CLU syntax "
            f"that is not yet supported by our tooling"
        )

    return reference


def identify_clu_dependencies(resource_id: str, resource: str) -> list[ResourceDependency]:
    """
    Identify all clu dependencies within a given resource references are specified using the &{a}
    syntax where a is the ID of a resource and b is a field specifier. &{a:b} is not supported

    :param resource: the string content of the resource to process
    :return: a list of references, including the '&{}' syntax
    """

    dependencies: list[ResourceDependency] = []
    dependency_start_idx = 0

    for index in range(1, len(resource)):
        if resource[index] == "{" and resource[index - 1] == "&":
            # dependency_start_idx is only non-0 if we're already inside a `&{` block
            if dependency_start_idx > 0:
                raise ValueError(
                    f"Nested dependency reference in resource `{resource_id}` at position `{index}`"
                )
            dependency_start_idx = index + 1
        elif dependency_start_idx > 0 and resource[index] == "}":
            dependencies.append(
                ResourceDependency(
                    source_id=resource_id,
                    target_id=_parse_clu_reference(resource[dependency_start_idx:index]),
                    start_position=dependency_start_idx - 2,
                    end_position=index,
                )
            )
            dependency_start_idx = 0
        elif resource[index] == os.linesep and dependency_start_idx > 0:
            raise ValueError(
                f"Dependency reference split across lines in resource `{resource_id}` "
                f"at position `{index}`"
            )

    return dependencies


def safe_merge_dicts(dicts: Iterable[dict]) -> dict:
    """
    Merge an iterable of dicts. Duplicate keys result in an exception
    :raises KeyError: Raised if any of the dicts contain identical keys
    """

    if duplicates := _identify_duplicate_dict_keys(*dicts):  # noqa
        raise KeyError(
            f"Duplicate resource ids found across id mappings for different resource types: "
            f"{duplicates}"
        )
    return _merge_dicts(dicts)


def _merge_dicts(dicts: Iterable[dict]) -> dict:
    """
    Merge an iterable of dicts. No special treatment for duplicate keys or varying dict types
    """
    return reduce(lambda dict_1, dict_2: dict(dict_1, **dict_2), dicts, dict())


def _identify_duplicate_dict_keys(*args: dict[str, str]) -> dict[str, list[str]]:
    kvps = defaultdict(list)
    for dictionary in args:
        for key, value in dictionary.items():
            kvps[key].append(value)

    duplicates = {key: value for key, value in kvps.items() if len(value) > 1}

    return duplicates


def replace_clu_dependencies(
    resource_id: str,
    resource: str,
    *args: dict[str, str],
    remove_clu_syntax_for_unknown_ids: bool = False,
) -> str:
    """
    Replace CLU dependencies within a resource based on a list of mapping dictionaries
    :param resource_id: id of the resource to be processed
    :param resource: resource to be processed
    :param remove_clu_syntax_for_unknown_ids: if True, the `&{` and `}` prefix and suffix are
    removed for resource_ids with no mappings, leaving the reference id as it is. This is useful
    for simulator/unit testing where we don't have any mapped ids
    :param args: mapping dictionaries that should all mapped original resource ids to
     desired ids
    :raises CLUDuplicateResourceId: raised if the mapping dictionaries have identical resource ids
     in keys
    :raises CLUMissingMapping: raised if a CLU dependency has no corresponding mapping and
    remove_clu_syntax_for_unknown_ids is not True
    :return: the modified resource
    """

    try:
        merged_mapping = safe_merge_dicts(args)
    except KeyError as e:
        # This is enforced by CLU itself, but because we don't CLU itself in the framework
        # it is handy to catch this type of error early
        raise CLUDuplicateResourceId from e

    dependencies = identify_clu_dependencies(resource_id, resource)
    # process backwards so that indices aren't affected by replacements
    for dependency in reversed(dependencies):
        if dependency_replacement := merged_mapping.get(dependency.target_id):
            resource = (
                resource[: dependency.start_position]
                + dependency_replacement
                + resource[dependency.end_position + 1 :]
            )
        elif remove_clu_syntax_for_unknown_ids:
            # This just removes the `&{` prefix and `}` suffix
            resource = (
                resource[: dependency.start_position]
                + dependency.target_id
                + resource[dependency.end_position + 1 :]
            )
        else:
            raise CLUMissingMapping(
                f"Could not find mapping for CLU reference `{dependency.target_id}`"
            )

    return resource


class ScheduleTagReplacer(ast.NodeTransformer):
    V4_EVENT_TYPES = {"SmartContractEventType", "SupervisorContractEventType"}

    def __init__(self, event_type_name_to_tag_ids: dict[str, str], default_tag_id: str):
        self.event_type_name_to_tag_ids: dict[str, str] = event_type_name_to_tag_ids
        self.default_tag_id: str = default_tag_id
        self.module_constants: dict[str, str] = {}

    def visit_Module(self, node: ast.Module):
        # Get module-level assignments that may be used as constants in EventType name

        # We consider any assignment of a str value to single name as a module constant
        self.module_constants = {
            x.targets[0].id: x.value.value
            for x in node.body
            if type(x) is ast.Assign
            and isinstance(x.value, ast.Str)
            and len(x.targets) == 1
            and isinstance(x.targets[0], ast.Name)
        }

        return self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> ast.AST:
        # identify cases of SmartContractEventType or
        # SupervisorContractEventType(name=.... scheduler_tag_ids=[...])
        # and replace the schedule tag ids based on the name, defaulting
        # to the generic paused e2e tag
        event_type_name: ast.keyword | None = None
        event_type_tag_ids: ast.keyword | None = None
        if isinstance(node.func, ast.Name):
            if node.func.id in self.V4_EVENT_TYPES:
                for keyword in node.keywords:
                    if keyword.arg == "name":
                        event_type_name = keyword
                    elif keyword.arg == "scheduler_tag_ids":
                        event_type_tag_ids = keyword
            else:
                return self.generic_visit(node)
        else:
            return self.generic_visit(node)

        if event_type_name is None:
            raise ValueError(
                "SmartContractEventType/SupervisorContractEventType has no `name` kwarg"
            )
        # We're assuming the __repr__ have been replaced, evaluating the tag ids to a string
        # (ast.Constant) or leaving it as a variable (ast.Name)
        elif isinstance(event_type_name.value, ast.Constant):
            event_type_name_value = str(event_type_name.value.value)
        elif isinstance(event_type_name.value, ast.Name):
            event_type_name_value = self.module_constants.get(event_type_name.value.id, "")
        else:
            log.warning(
                f"EventType name {event_type_name} has unrecognised type. Tag ids won't be replaced"
            )
            return self.generic_visit(node)

        desired_tag_id = self.event_type_name_to_tag_ids.get(
            event_type_name_value, self.default_tag_id
        )

        log.debug(f"Upserting scheduler_tag_ids for {event_type_name_value} to {desired_tag_id}")
        keyword_value = ast.List(elts=[ast.Constant(value=desired_tag_id)])
        # tags are optional, so we must upsert the ast
        if event_type_tag_ids:
            event_type_tag_ids.value = keyword_value
        else:
            node.keywords.append(ast.keyword(arg="scheduler_tag_ids", value=keyword_value))

        return self.generic_visit(node)


def replace_schedule_tag_ids_in_contract(
    contract_data: str, id_mapping: dict[str, str], default_paused_tag_id: str
) -> str:
    """
    Replaces the original scheduler tag ids inside a smart contract with the run-specific ids
    :param contract_data: the smart contract code
    :param id_mapping: mapping of event type name to schedule tag id for the contract
    :param default_paused_tag_id: the tag id to use if an event type name is not in id_mapping
    :return: the updated smart contract code
    """

    tree = ast.parse(contract_data)
    ast.fix_missing_locations(ScheduleTagReplacer(id_mapping, default_paused_tag_id).visit(tree))
    rendered_contract = ast.unparse(tree)

    return rendered_contract


def replace_flags_in_parameter(
    param_value: dict[str, Any], id_mapping: dict[str, str]
) -> dict[str, Any] | list[str]:
    """
    Replaces the original flag definition ids inside a parameter value with the run-specific ids
    Examples of parameter values json strings that contain flags are
    {"flag_key": ["REPAYMENT_HOLIDAY"]}
    i.e. one-item dictionary of type dict[str, list[str]]

    or

    {
        "flag_key": {
            "US_CHECKING_ACCOUNT_TIER_UPPER": "-1",
            "US_CHECKING_ACCOUNT_TIER_MIDDLE": "21",
            "US_CHECKING_ACCOUNT_TIER_LOWER": "-1",
        }
    }
    i.e. a nested dictionary of type dict[str, str | dict] (but all nested
    dictionaries must also be of type dict[str, str | dict])

    :param param_value: the parameter value specified in the e2e test
    :return: the updated parameter value with "flag_key" removed
    """

    return_value = {}
    for key, value in param_value.items():
        if key == "flag_key":
            if type(value) is dict:
                return_value.update(_replace_flags_in_dict(value, id_mapping))
            elif type(value) is list:
                # if value is list, then param_value is of type dict[str, list[str]]
                return _replace_flags_in_list(value, id_mapping)
            else:
                return value
        else:
            if type(value) is dict:
                return_value[key] = replace_flags_in_parameter(value, id_mapping)
            else:
                return_value[key] = value

    return return_value


def _replace_flags_in_dict(
    value_dict: dict[str, Any], id_mapping: dict[str, str]
) -> dict[str, Any]:
    """
    Replace the flags in a dictionary with the run-specific ids
    :param value_dict: dictionary from the key-value pair {"flag_key": dict}
    :param id_mapping: flag id mapping
    :return the updated dictionary with the run-specific ids
    """
    return_object = {}
    if len(value_dict) == 0:
        log.info("Value of flag_key is an empty dictionary.")
        return value_dict

    for key, value in value_dict.items():
        key_to_use = id_mapping.get(key, key)
        if type(value) is dict:
            return_object[key_to_use] = replace_flags_in_parameter(value, id_mapping)
        else:
            return_object[key_to_use] = value
    return return_object


def _replace_flags_in_list(value_list: list[str], id_mapping: dict[str, str]) -> list[str]:
    """
    Replace the flags inline with the run-specific ids
    :param value_list: list from the key-value pair {"flag_key": list}
    :param id_mapping: flag id mapping
    :return the updated list with the run-specific ids
    """
    return [id_mapping.get(flag_name, flag_name) for flag_name in value_list]


def create_mock_message_queue(
    sample_message_file: str = "",
    yield_message_range: int = 3,
    matched_message_sleep: int = 1,
    while_loop_sleep: int = 1,
    sample_message: Any = None,
) -> Mock:
    """
    This mocks a kafka consumer, returning a mocked poller
    Rather than overriding the poll function to a mock function, it is
    set to be a generator which is instantiated and then yields the
    desired responses for the kafka message queue mock.
    :param sample_message_file: file path to sample kafka message file
    :param yield_message_range: number of matched messages to return
    :param matched_message_sleep: sleep time between match messages
    :param while_loop_sleep: sleep time between None messages
    :param sample_message: a json message to return. Overrides the
    sample_message_file
    """
    if sample_message is None:
        with open(sample_message_file, encoding="utf-8") as file:
            sample_message = file.read()

    poller = Mock()
    message_response_mock = Mock()
    message_response_decode_mock = Mock()
    message_response_decode_mock.decode.return_value = sample_message
    message_response_mock.error.return_value = False
    message_response_mock.value.return_value = message_response_decode_mock

    def mock_message_queue():
        for _ in range(yield_message_range):
            yield message_response_mock
        time.sleep(matched_message_sleep)
        while True:
            # add sleep here to slow down infinite while loop
            time.sleep(while_loop_sleep)
            yield None

    poller.poll.side_effect = mock_message_queue()
    return poller


def _get_nested_dict_keys(dict_obj):
    for key, value in dict_obj.items():
        yield key
        if isinstance(value, dict):
            for k in _get_nested_dict_keys(value):
                yield k
