# standard libs
from enum import Enum
from typing import Any

# inception sdk
from inception_sdk.test_framework import endtoend as endtoend

STATE_TECHNICAL_ERROR = "technical_error"


class OrderByDirection(Enum):
    ORDER_BY_ASC = "ORDER_BY_ASC"
    ORDER_BY_DESC = "ORDER_BY_DESC"


class WorkflowStateOrderBy(Enum):
    ORDER_BY_TIMESTAMP_ASC = "ORDER_BY_TIMESTAMP_ASC"
    ORDER_BY_TIMESTAMP_DESC = "ORDER_BY_TIMESTAMP_DESC"


class WorkflowDefinitionOrderBy(Enum):
    ORDER_BY_NAME_ASC = "ORDER_BY_NAME_ASC"
    ORDER_BY_NAME_DESC = "ORDER_BY_NAME_DESC"
    ORDER_BY_TIMESTAMP_ASC = "ORDER_BY_TIMESTAMP_ASC"
    ORDER_BY_TIMESTAMP_DESC = "ORDER_BY_TIMESTAMP_DESC"


class DefinitionVersionField(Enum):
    INCLUDE_FIELD_SPECIFICATION = "INCLUDE_FIELD_SPECIFICATION"
    INCLUDE_FIELD_STATES = "INCLUDE_FIELD_STATES"
    INCLUDE_FIELD_TRANSITIONS = "INCLUDE_FIELD_TRANSITIONS"
    INCLUDE_FIELD_END_STATES = "INCLUDE_FIELD_END_STATES"


class InstanceField(Enum):
    INCLUDE_FIELD_ADDITIONAL_DETAILS = "INCLUDE_FIELD_ADDITIONAL_DETAILS"


class WorkflowInstanceStatus(Enum):
    WORKFLOW_INSTANCE_STATUS_UNKNOWN = "WORKFLOW_INSTANCE_STATUS_UNKNOWN"
    WORKFLOW_INSTANCE_STATUS_INSTANTIATED = "WORKFLOW_INSTANCE_STATUS_INSTANTIATED"
    WORKFLOW_INSTANCE_STATUS_CLOSED = "WORKFLOW_INSTANCE_STATUS_CLOSED"
    WORKFLOW_INSTANCE_STATUS_SUSPENDED = "WORKFLOW_INSTANCE_STATUS_SUSPENDED"


def batch_get_workflow_definition_versions(
    ids: list[str], fields_to_include: list[DefinitionVersionField]
) -> dict[str, dict[str, Any]]:
    """
    Get specific workflow definition versions
    :param ids: list of definition version ids to retrieve
    :param fields_to_include: fields to include that are omitted by default.
    :return: all the requested definition versions
    """
    params = {
        "ids": ids,
        "fields_to_include": [field.value for field in fields_to_include],
    }
    resp = endtoend.helper.send_request(
        "get", "/v1/workflow-definition-versions:batchGet", params=params
    )

    return resp["workflow_definition_versions"]


def get_workflow_definition_version(definition_version_id: str) -> dict[str, Any]:
    """
    Convenience wrapper around batch_get_workflow_definition_versions to get
    the full details for one Workflow definition version.

    :param definition_version_id: The Workflow definition version id
    :return: The definition version as a dictionary
    """
    wf_versions = batch_get_workflow_definition_versions(
        ids=[definition_version_id],
        fields_to_include=[
            DefinitionVersionField.INCLUDE_FIELD_STATES,
            DefinitionVersionField.INCLUDE_FIELD_SPECIFICATION,
            DefinitionVersionField.INCLUDE_FIELD_TRANSITIONS,
            DefinitionVersionField.INCLUDE_FIELD_STATES,
        ],
    )

    return wf_versions[definition_version_id] if wf_versions else {}


def batch_get_workflow_instances(
    ids: list[str],
    fields_to_include: list[InstanceField] | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Get a list of workflow instances
    :param ids: list of instance ids to retrieve
    :param fields_to_include: fields to include that are omitted by default.
    :return: all the requested instances
    """

    params = {
        "ids": ids,
        "fields_to_include": [field.value for field in fields_to_include or []],
    }
    resp = endtoend.helper.send_request("get", "/v1/workflow-instances:batchGet", params=params)

    return resp["workflow_instances"]


def get_workflow_instances(
    workflow_definition_id: str = "",
    workflow_definition_version_id: str = "",
    customer_ids: list[str] | None = None,
    parent_ids: list[str] | None = None,
    fields_to_include: list[InstanceField] | None = None,
    order_by_direction: OrderByDirection = OrderByDirection.ORDER_BY_ASC,
    include_statuses: list[WorkflowInstanceStatus] | None = None,
) -> list[dict[str, Any]]:
    """
    Get a list of workflow instances
    :param workflow_definition_id: instance workflow definition id
    :param workflow_definition_version_id: instance workflow definition version id
    :param customer_ids: list of customer ids that are linked to the instances
    :param parent_ids: list of parent workflow ids that triggered the instances
    :param fields_to_include: fields that are omitted by default.
    :param order_by_direction: ordering direction of instances by create_timestamp
    :param include_statuses: list of workflow instance statuses to include
    :return: list of workflow instances
    """

    params = {
        "workflow_definition_id": workflow_definition_id,
        "workflow_definition_version_id": workflow_definition_version_id,
        "order_by_direction": order_by_direction.value,
        "customer_ids": customer_ids or [],
        "parent_ids": parent_ids or [],
        "fields_to_include": [field.value for field in fields_to_include or []],
        "include_statuses": [status.value for status in include_statuses or []],
    }

    resp = endtoend.helper.list_resources("workflow-instances", params=params)

    return resp


def get_workflow_instance_states(
    instance_id: str,
    order_by: WorkflowStateOrderBy = WorkflowStateOrderBy.ORDER_BY_TIMESTAMP_DESC,
    result_limit: int = -1,
) -> list[dict[str, Any]]:
    """
    Get the workflow instance states for a given instance
    :param instance_id: the workflow instance id
    :param order_by: ORDER_BY_TIMESTAMP_DESC or ORDER_BY_TIMESTAMP_ASC
    :param result_limit: max number of results
    :return: the instance states
    """

    params = {"workflow_instance_id": instance_id, "order_by": order_by.value}
    return endtoend.helper.list_resources(
        "workflow-instance-states", params=params, result_limit=result_limit
    )


def get_workflow_tickets(
    tags: str = "",
    workflow_instance_ids: list[str] | None = None,
    page_size: int = 10,
) -> list[dict[str, Any]]:
    """
    Get a list of workflow tickets
    :param tags: The tags to filter tickets by
    :param page_size: page size per request
    :return: list of workflow tickets
    """

    params = {"tags": tags, "workflow_instance_ids": workflow_instance_ids}

    resp = endtoend.helper.list_resources("tickets", params=params, page_size=page_size)

    return resp


def get_workflow_instance_events(
    workflow_instance_id: str, limit: int = 0
) -> list[dict[str, dict]]:
    """
    Get all workflow events for a workflow instance
    :param workflow_instance_id: workflow id
    :param limit limit the result set
    :return: dictionary of local context keys and values
    """

    workflow_instance_events = endtoend.helper.list_resources(
        result_limit=limit,
        endpoint="workflow-instance-events",
        params={
            "workflow_instance_id": workflow_instance_id,
            "fields_to_include": "INCLUDE_FIELD_CONTEXT",
        },
    )

    return workflow_instance_events


def get_workflow_instantiation_context(workflow_instance_id: str) -> dict[str, str]:
    workflow_instantiation_context = get_workflow_instance_events(workflow_instance_id, limit=1)[0][
        "context"
    ]

    return workflow_instantiation_context
