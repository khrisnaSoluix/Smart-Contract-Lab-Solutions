# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.

# standard libs
import hashlib
import json
import logging
import os
import random
import re
import string
import unittest
import uuid
from typing import Any

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.common.utils import (
    replace_clu_dependencies,
    replace_schedule_tag_ids_in_contract,
)
from inception_sdk.test_framework.endtoend.kafka_helper import kafka_only_helper, wait_for_messages
from inception_sdk.tools.common.tools_utils import override_logging_level

with override_logging_level(logging.WARNING):
    # third party
    from black import format_str
    from black.mode import Mode

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


PLAN_UPDATE_EVENTS_TOPIC = "vault.core_api.v1.plans.plan_update.events"

TERMINAL_PLAN_STATUSES = [
    "PLAN_UPDATE_STATUS_REJECTED",
    "PLAN_UPDATE_STATUS_ERRORED",
    "PLAN_UPDATE_STATUS_COMPLETED",
]


def upload_supervisor_contracts(supervisor_contracts: dict[str, dict[str, Any]]) -> None:
    for product_id, contract_properties in supervisor_contracts.items():
        if "path" not in contract_properties:
            raise NameError(
                "Contract: {} not specified with path. "
                "Specified with {}".format(product_id, str(contract_properties))
            )
        e2e_contract_data = endtoend.contracts_helper.get_contract_content_for_e2e(
            product_id,
            contract_properties,
        )
        e2e_contract_data = replace_clu_dependencies(
            product_id, e2e_contract_data, endtoend.testhandle.clu_reference_mappings
        )

        e2e_contract_data = replace_schedule_tag_ids_in_contract(
            contract_data=e2e_contract_data,
            # we process internal products for which no schedules ever exist and therefore cannot
            # be set on the testhandle
            id_mapping=endtoend.testhandle.controlled_schedule_tags.get(product_id, {}),
            default_paused_tag_id=endtoend.testhandle.default_paused_tag_id,
        )

        e2e_contract_data = format_str(e2e_contract_data, mode=Mode(line_length=100))

        e2e_display_name = "e2e_" + product_id

        description = "Description of " + e2e_display_name

        randomchars = "".join(random.choice(string.ascii_letters) for x in range(10))
        request_id = product_id + randomchars

        request_hash = hashlib.md5((request_id).encode("utf-8")).hexdigest()
        contract_version_request_hash = hashlib.md5((e2e_contract_data).encode("utf-8")).hexdigest()

        supervisor_contract = endtoend.core_api_helper.create_supervisor_contract(
            request_id=request_hash,
            display_name=product_id,
        )

        supervisor_contract_version = endtoend.core_api_helper.create_supervisor_contract_version(
            request_id=contract_version_request_hash,
            supervisor_contract_id=supervisor_contract["id"],
            display_name=e2e_display_name,
            description=description,
            code=e2e_contract_data,
        )

        log.info("Supervisor contract %s version uploaded.", supervisor_contract_version["id"])
        endtoend.testhandle.supervisorcontract_name_to_id[product_id] = supervisor_contract_version[
            "id"
        ]


def create_plan(
    supervisor_contract_version_id: str,
    plan_id: str | None = None,
    details: dict | None = None,
    wait_for_activation: bool = True,
) -> dict:
    request_id = uuid.uuid4().hex

    post_body = {
        "plan": {
            "id": plan_id,
            "supervisor_contract_version_id": supervisor_contract_version_id,
            "details": details,
        },
        "request_id": request_id,
    }

    response = endtoend.helper.send_request("post", "/v1/plans", data=json.dumps(post_body))
    final_plan_id = response["id"]

    if wait_for_activation:
        wait_for_plan_update(plan_id=final_plan_id, plan_update_type="activation_update")

    log.info(f"Plan {final_plan_id} created with {supervisor_contract_version_id=}")
    endtoend.testhandle.plans.append(final_plan_id)

    return response


def close_all_plans():
    for plan_id in endtoend.testhandle.plans:
        close_plan(plan_id)
    endtoend.testhandle.plans.clear()


def close_plan(plan_id):
    request_id = uuid.uuid4().hex

    post_body = {
        "plan_update": {"plan_id": plan_id, "closure_update": {}},
        "request_id": request_id,
    }

    post_body = json.dumps(post_body)

    resp = endtoend.helper.send_request("post", "/v1/plan-updates", data=post_body)
    log.info("Close plan: %s for plan: %s sent.", resp["id"], plan_id)

    return resp


def get_plan_update(plan_update_id: str) -> dict:
    params = {"ids": [plan_update_id]}
    resp = endtoend.helper.send_request("get", "/v1/plan-updates:batchGet", params=params)

    return next(iter(resp["plan_updates"].values()))


def get_plan_updates(plan_id: str, statuses: list[str] | None = None) -> list[dict[str, Any]]:
    params = {"plan_ids": [plan_id], "statuses": statuses}
    return endtoend.helper.list_resources("plan-updates", params)


def get_plan_updates_by_type(
    plan_id: str, update_types: list[str], statuses: list[str] | None = None
) -> list[dict[str, Any]]:
    """
    Gets a list of plan updates and filters by type
    :param plan_id: the plan id to get plan updates for
    :param update_types: the list of plan update types we want to filter for (not handled in API)
    :param statuses: the list of plan update statuses we want to filter for (handled in API)
    :return: list of plan updates
    """

    plan_updates = get_plan_updates(plan_id, statuses)
    plan_updates_by_type = [
        plan_update
        for plan_update in plan_updates
        for update_type in update_types
        if update_type in plan_update
    ]
    return plan_updates_by_type


def get_plan_updates_by_ids(plan_update_ids: list[str]) -> dict[str, dict]:
    """
    Fetch details for one or more plan update ids.
    :param plan_update_ids: a collection of plan update ids
    :return: dict with id and update plan information
    """
    params = {"ids": plan_update_ids}
    resp = endtoend.helper.send_request("get", "/v1/plan-updates:batchGet", params=params)
    return resp["plan_updates"]


def create_plan_update(
    plan_id: str,
    plan_update_type: str,
    update: dict[str, Any],
    status: str | None = None,
    account_id: str | None = None,
) -> dict[str, Any]:
    request_id = uuid.uuid4().hex

    post_body: dict[str, Any] = {
        "plan_update": {"id": account_id, "plan_id": plan_id, "status": status},
        "request_id": request_id,
    }

    post_body["plan_update"][plan_update_type] = update

    resp = endtoend.helper.send_request("post", "/v1/plan-updates", data=json.dumps(post_body))
    log.info("Plan_update: %s for plan: %s sent.", resp["id"], plan_id)

    return resp


def wait_for_plan_update(
    plan_id: str = "",
    plan_update_type: str = "",
    plan_update_id: str = "",
    target_status: str = "PLAN_UPDATE_STATUS_COMPLETED",
):
    """
    For a given plan id and plan_update_type, or a plan_update_id, wait for the
    corresponding plan_update to reach the target status.
    If using plan + plan_update_type, the latest plan-update of that type is used

    :param plan_id: the plan_id to use to select the plan-update to poll. Only used if
    plan_update_id is not populated
    :param plan_update_type: the plan-update type to use to select the plan-update to poll.
    Only used if plan_update_id is not populated
    :param plan_update_id: id of the specific plan update to wait for
    :param target_status: the plan-update status to keep polling for
    """

    if not plan_update_id:
        plan_updates = endtoend.helper.retry_call(
            func=get_plan_updates_by_type,
            f_kwargs={"plan_id": plan_id, "update_types": [plan_update_type]},
            expected_result=True,
            result_wrapper=lambda x: len(x) > 0,
            failure_message=f"No plan updates for plan {plan_id} could be found.",
        )[-1]
        plan_update_id = plan_updates["id"]

    wait_for_plan_updates(plan_update_ids=[plan_update_id], target_status=target_status)


def wait_for_plan_updates(
    plan_update_ids: list[str], target_status="PLAN_UPDATE_STATUS_COMPLETED"
) -> None:
    """
    Verify if given one or more plan update ids are of target status.
    :param plan_update_ids: a collection of plan update ids
    :param target_status: the plan update status to wait for
    """
    if endtoend.testhandle.use_kafka:
        wait_for_plan_updates_by_id(
            plan_update_ids=plan_update_ids,
            target_status=target_status,
        )
    else:
        # result_wrapper verifies if all plan_updates have target_status
        # and get_plan_updates_by_ids was able to fetch details for all requested ids
        endtoend.helper.retry_call(
            func=get_plan_updates_by_ids,
            f_args=[plan_update_ids],
            expected_result=True,
            result_wrapper=lambda data: all(
                item["status"] == target_status for _, item in data.items()
            )
            and data.keys() == set(plan_update_ids),
            failure_message=f'"One of plan updates in {plan_update_ids} never completed.\n"',
        )


@kafka_only_helper
def wait_for_plan_updates_by_id(
    plan_update_ids: list[str],
    target_status: str = "PLAN_UPDATE_STATUS_COMPLETED",
) -> None:
    """
    listen to the plan update events Kafka topic for specific plan update ids.
    :param plan_update_ids: a collection of plan update ids to listen for
    :param target_status: the plan update status to wait for
    """
    consumer = endtoend.testhandle.kafka_consumers[PLAN_UPDATE_EVENTS_TOPIC]

    def matcher(event_msg, unique_message_ids):
        if target_status == "PLAN_UPDATE_STATUS_PENDING_EXECUTION":
            plan_update_wrapper = event_msg.get("plan_update_created")
        else:
            plan_update_wrapper = event_msg.get("plan_update_updated")
        event_request_id = event_msg["event_id"]
        if plan_update_wrapper:
            plan_update = plan_update_wrapper["plan_update"]
            if plan_update["id"] in unique_message_ids:
                if plan_update["status"] == target_status:
                    return plan_update["id"], event_request_id, True

                if plan_update["status"] in TERMINAL_PLAN_STATUSES:
                    log.warning(
                        f"Plan update {plan_update['id']} returned a status of "
                        f"{plan_update['status']}"
                    )
        return "", event_request_id, False

    failed_plan_updates = wait_for_messages(
        consumer,
        matcher=matcher,
        callback=None,
        unique_message_ids={update_id: None for update_id in plan_update_ids},
        inter_message_timeout=30,
        matched_message_timeout=30,
    )

    if len(failed_plan_updates) > 0:
        raise Exception(
            f"Failed to retrieve {len(failed_plan_updates)} of {len(plan_update_ids)} "
            f"plan updates for update ids: {', '.join(failed_plan_updates)}"
        )


def create_and_wait_for_plan_update(
    plan_id: str,
    plan_action_type: str,
    action: dict[str, Any],
    status: str | None = None,
    account_id: str | None = None,
) -> dict[str, Any]:
    plan_update = create_plan_update(plan_id, plan_action_type, action, status, account_id)
    plan_update_id = plan_update["id"]
    wait_for_plan_updates([plan_update_id])
    return plan_update


def add_account_to_plan(plan_id, account_id):
    action = {"account_id": account_id}
    log.info(f"preparing to link account {account_id} to plan {plan_id}")
    return create_and_wait_for_plan_update(plan_id, "associate_account_update", action)


def disassociate_account_from_plan(plan_id, account_id):
    account_plan_assoc = endtoend.supervisors_helper.get_plan_associations(account_ids=account_id)[
        0
    ]
    action = {"account_plan_assoc_id": account_plan_assoc["id"]}
    log.info(f"Preparing to disassociate account {account_id} from plan {plan_id}")

    return create_and_wait_for_plan_update(
        plan_id=plan_id, plan_action_type="disassociate_account_update", action=action
    )


def link_accounts_to_supervisor(supervisor_contract: str, account_list: list[str]) -> str:
    supervisor_contract_version_id = endtoend.testhandle.supervisorcontract_name_to_id[
        supervisor_contract
    ]
    plan = create_plan(supervisor_contract_version_id)

    for account in account_list:
        add_account_to_plan(plan["id"], account)

    return plan["id"]


def get_plan_associations(account_ids=None, plan_ids=None):
    if not account_ids and not plan_ids:
        raise NameError("account id nor plan id specified")
    if account_ids and not isinstance(account_ids, list):
        account_ids = [account_ids]
    if plan_ids and not isinstance(plan_ids, list):
        plan_ids = [plan_ids]

    params = {"account_ids": account_ids, "plan_ids": plan_ids, "page_size": "100"}

    resp = endtoend.helper.send_request("get", "/v1/account-plan-assocs", params=params)

    return resp["account_plan_assocs"]


def get_plan_schedules(plan_id=None, page_size="20"):
    if not plan_id:
        raise NameError("plan id not specified")

    params = {"plan_id": plan_id, "page_size": page_size}

    resp = endtoend.helper.send_request("get", "/v1/plan-schedules", params=params)

    schedule_ids = [s["id"] for s in resp["plan_schedules"]]

    response_schedules = endtoend.core_api_helper.batch_get_schedules(schedule_ids)

    # A dict of schedule event_names to their schedule objects
    return {
        schedule_details["display_name"].split()[0]: schedule_details
        for schedule_details in response_schedules.values()
        if schedule_details["status"] != "SCHEDULE_STATUS_DISABLED"
        and re.search(rf"{plan_id}", schedule_details["display_name"])
    }


def get_plan_details(plan_id):
    params = {"ids": plan_id}

    resp = endtoend.helper.send_request("get", "/v1/plans:batchGet", params=params)

    return resp["plans"][plan_id]


def check_plan_associations(
    test: unittest.TestCase, plan_id: str, accounts: list[str] | dict[str, str]
):
    """
    Helper method to validate that plan currently has expected associations. If a given account has
    been through multiple associations with the same plan, only the latest is considered
    :param plan_id: the plan id
    :param account_ids: the account ids to validate are currently linked. If passed as a list, the
    link statuses are assumed to be active. If passed as a dict, the values are the statuses and the
    keys are the account ids.
    """
    plan_associations = endtoend.supervisors_helper.get_plan_associations(plan_ids=plan_id)

    # there could be multiple assocs with different statuses, but we'll only consider the latest
    actual_linked_accounts = {
        association["account_id"]: association["status"] for association in plan_associations
    }

    if isinstance(accounts, list):
        accounts = {account_id: "ACCOUNT_PLAN_ASSOC_STATUS_ACTIVE" for account_id in accounts}

    test.assertEqual(
        actual_linked_accounts,
        accounts,
        "latest and expected associations do not match",
    )
