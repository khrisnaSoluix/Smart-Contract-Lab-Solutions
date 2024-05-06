# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
# standard libs
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from random import choices, getrandbits
from string import ascii_uppercase, digits
from typing import Any, Callable, Generator

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.common.date_helper import extract_date
from inception_sdk.test_framework.endtoend.kafka_helper import (
    kafka_only_helper,
    produce_message,
    wait_for_messages,
)

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

DATA_LOADER_REQUEST_TOPIC = "vault.data_loader_api.v1.data_loader.resource_batch.create.requests"
DATA_LOADER_EVENTS_TOPIC = "vault.data_loader_api.v1.data_loader.resource_batch.events"


@dataclass
class BatchResourceIds:
    account_ids: list[str] = field(default_factory=list)
    customer_ids: list[str] = field(default_factory=list)
    flag_ids: list[str] = field(default_factory=list)


def _construct_resource_batch_request(resources: list, batch_id: str = "") -> dict:
    return {
        "request_id": str(uuid.uuid4()),
        "resource_batch": {"id": batch_id or str(uuid.uuid4()), "resources": resources},
    }


def generate_random_email() -> str:
    return str(uuid.uuid4()) + "@thoughtmachine.net"


def get_customer_resource(resource_id: str, dependencies: list[str] | None = None) -> dict:
    return {
        "id": resource_id,
        "customer_resource": {
            "status": "CUSTOMER_STATUS_ACTIVE",
            "identifiers": [
                {
                    # identifiers must be unique for the customer to be created
                    "identifier_type": "IDENTIFIER_TYPE_EMAIL",
                    "identifier": generate_random_email(),
                }
            ],
            "customer_details": {
                "title": "CUSTOMER_TITLE_MR",
                "first_name": "Perf",
                "middle_name": "L",
                "last_name": "Test",
                "dob": "1985-03-25",
                "gender": "CUSTOMER_GENDER_MALE",
                "nationality": "GB",
                "email_address": "mar@tm.net",
                "mobile_phone_number": "677906636",
                "home_phone_number": "677906636",
                "business_phone_number": "677906636",
                "contact_method": "CUSTOMER_CONTACT_METHOD_EMAIL",
                "country_of_residence": "GB",
                "country_of_taxation": "GB",
                "accessibility": "CUSTOMER_ACCESSIBILITY_AUDIO",
                "external_customer_id": "",
            },
            "additional_details": {},
        },
        "dependencies": dependencies or [],
    }


def get_account_resource(
    account_id: str,
    stakeholder_ids: list[str],
    product_version_id: str,
    instance_param_vals: dict[str, str],
    status: str = "ACCOUNT_STATUS_OPEN",
    permitted_denominations: list[str] | None = None,
    closing_ts: str | None = None,
    opening_ts: str | None = None,
    additional_details: dict[str, str] | None = None,
    dependencies: list[str] | None = None,
) -> dict:
    account = {
        # the actual id will be dictated by the resource id
        "id": str(uuid.uuid4()),
        "product_version_id": product_version_id,
        "permitted_denominations": permitted_denominations or ["GBP"],
        "instance_param_vals": instance_param_vals,
        "status": status,
        "stakeholder_ids": stakeholder_ids,
        "details": additional_details or {},
    }
    if opening_ts:
        account["opening_timestamp"] = opening_ts
    if status == "ACCOUNT_STATUS_CLOSED" and closing_ts:
        account["closing_timestamp"] = closing_ts

    return {
        "id": account_id,
        "account_resource": account,
        "dependencies": dependencies or stakeholder_ids,
    }


def get_flag_resource(
    flag_definition_id: str,
    identifier_type: str,
    target_identifier: str,
    resource_id: str = "",
    description: str = "",
) -> dict:
    return {
        "id": resource_id or str(getrandbits(50)),
        "flag_resource": {
            identifier_type: target_identifier,
            "description": description or flag_definition_id,
            "flag_definition_id": flag_definition_id,
        },
        "dependencies": [target_identifier],
    }


def generate_account_ids(number_of_accounts: int, id_base: str = "", start: int = 0):
    """
    Generate random account ids using an optional base, to which a number is prefixed and a
    random suffix is suffixed.
    :param number_of_accounts: number of accounts to create ids for
    :param id_base: optional string to include in the account ids
    :param start: optional offset to the numbered prefix
    """

    # account id has max length 36 as it used to be uuid only. 1 subtracted for underscore
    prefix_length = 36 - len(id_base) - 2 - len(str(number_of_accounts))
    id_base = id_base + "".join(choices(ascii_uppercase + digits, k=prefix_length))
    log.info(f"Account id in format <#>_{id_base}")

    # i is prefixed instead of suffixed due to an accounts bug that confuses <acc>_9 and <acc>_90
    return ["_".join([str(i), id_base]) for i in range(start, start + number_of_accounts)]


def process_flags(
    flag_parent: dict[str, Any], flag_parent_id: str, flag_identifier_type: str
) -> dict[str, dict[str, Any]]:
    """
    Creates flags for a given parent (account or customer) and definition
    :param flag_parent: the parent definition, which has a 'flags' key
    :param flag_parent_id: the id of the parent
    :param flag_identifier_type: one of 'account' or 'customer'
    :return: dict of flag id to flag resource
    """

    resources = {}

    for flag in flag_parent.get("flags", []):
        flag_resource = get_flag_resource(
            flag_definition_id=flag["flag_definition_id"],
            identifier_type=flag_identifier_type,
            target_identifier=flag_parent_id,
        )
        resources[flag_resource["id"]] = flag_resource

    return resources


def create_resource_batch(resources: list[dict[str, Any]], batch_id: str = "") -> dict[str, Any]:
    """
    Uses the unofficial resource batch endpoint to create a resource batch
    :param resources: list of data loader resources to include in the batch
    :param batch_id: the resource batch's id
    """

    # We can't re-use construct_resource_batch as the unofficial endpoint doesn't have a request_id
    data = json.dumps({"resources": resources, "batch_id": batch_id or str(uuid.uuid4())})

    return endtoend.helper.send_request("post", "/v1/resource-batches", data=data)


def create_dataloader_resource_batch_requests(
    dependency_groups: list[dict], product_version_id: str, batch_size: int = 150
) -> Generator[tuple[dict, BatchResourceIds], None, None]:
    """
    Creates dataloader resource batches with the required resources and produces
    the corresponding requests to Kafka. Following resource types supported:
    - customers
    - accounts
    - flags (customer or account level)
    :param producer: kafka producer to produce the requests
    :param dependency_groups: list of dependency groups to create requests for
    :param product_version_id: the product_version_id for accounts. This is not known until
    run-time so cannot be stored in test config
    :param batch_size: the number of resources in a batch that must be reached before the request
    is sent. This number may be exceeded if the number of resources in a dependency group is not
    modulo batch_size (e.g. dependency group with 8 items and batch_size 10 would result in a
    single batch with 16 resources). If the total number of resources across all dependency group
    instances is lower than the batch, the batch will still be sent.
    :yields: resource batch requests
    """

    batch_resources = []
    batch_resource_ids = BatchResourceIds()

    for dependency_group in dependency_groups:
        customer_definition = dependency_group["customer"]
        customer_id_base = int(customer_definition["id_base"])
        account_definitions = dependency_group["accounts"]
        num_accounts = len(account_definitions)
        group_instances = dependency_group["instances"]
        # pre-generate ids so we can populate bi-directional dependencies and optimise
        # data-loader processing.
        account_ids = generate_account_ids(number_of_accounts=int(group_instances) * num_accounts)
        for i in range(group_instances):
            customer_id = str(customer_id_base + i)
            customer_flags = process_flags(customer_definition, customer_id, "customer_id")
            batch_resource_ids.flag_ids.extend(customer_flags.keys())
            batch_resources.extend(customer_flags.values())
            batch_resource_ids.customer_ids.append(customer_id)
            batch_resources.append(
                get_customer_resource(
                    customer_id,
                    dependencies=list(customer_flags.keys())
                    + account_ids[i * num_accounts : (i + 1) * num_accounts],  # noqa: E203
                )
            )

            for j, account in enumerate(account_definitions):
                account_id = account_ids[i * len(account_definitions) + j]
                account_flags = process_flags(account, account_id, "account_id")
                batch_resource_ids.flag_ids.extend(account_flags.keys())
                batch_resources.extend(account_flags.values())
                batch_resource_ids.account_ids.append(account_id)
                batch_resources.append(
                    get_account_resource(
                        account_id=account_id,
                        stakeholder_ids=[customer_id],
                        product_version_id=product_version_id,
                        instance_param_vals=account["instance_param_vals"],
                        opening_ts=extract_date(account["account_opening_timestamp"]).isoformat(),
                        dependencies=[customer_id] + list(account_flags.keys()),
                        additional_details=account.get("details"),
                    )
                )

            if len(batch_resources) >= batch_size or i >= group_instances - 1:
                batch_id = str(uuid.uuid4())
                resource_batch = _construct_resource_batch_request(batch_resources, batch_id)
                yield resource_batch, batch_resource_ids
                batch_resources = []
                batch_resource_ids = BatchResourceIds()


@kafka_only_helper
def create_and_produce_data_loader_requests(
    producer,
    dependency_groups: list[dict],
    product_version_id: str,
    batch_size: int = 150,
) -> dict[str, BatchResourceIds]:
    """
    Creates and publishes data loader resource batch requests
    :param producer: kafka producer to use
    :param dependency_groups: the dependency group definitions to create requests for
    :param product_version_id: the product_version_id for the account resources
    :param batch_size: the number of resources in a batch that must be reached before the request
    is sent. See create_dataloader_resource_batch_requests for more info
    :return: mapping of resource batch id to BatchResourceIds for that batch
    """

    batch_id_mapping = {}
    for request, batch_resource_ids in create_dataloader_resource_batch_requests(
        dependency_groups, product_version_id, batch_size
    ):
        # The data-loader does not include resources in the subsequent events, so we keep track
        # of the ones we're interested in to avoid fetching the batch later
        batch_id = request["resource_batch"]["id"]
        batch_id_mapping[batch_id] = batch_resource_ids
        produce_message(producer, DATA_LOADER_REQUEST_TOPIC, json.dumps(request))

    producer.flush()

    return batch_id_mapping


def wait_for_batch_events(batch_ids: set[str], batch_handler: Callable | None = None):
    """
    Waits for data loader resource batch updated events and calls batch handler for each event.
    :param batch_ids: resource batch ids to wait for
    :param batch_handler: callable that implements desired logic when an event is received. This
    should handle all possible statuses for the event.
    """

    consumer = endtoend.testhandle.kafka_consumers[DATA_LOADER_EVENTS_TOPIC]

    def matcher(event_msg, unique_message_ids):
        updated_resource_batch = event_msg.get("resource_batch_updated", {}).get("resource_batch")
        event_request_id = event_msg["event_id"]
        # This means RESOURCE_BATCH_STATUS_PENDING batches will not match as they have
        # 'resource_batch_created' instead of 'resource_batch_updated'
        if not updated_resource_batch:
            return "", event_request_id, False

        status = updated_resource_batch["status"]
        if status != "RESOURCE_BATCH_STATUS_COMPLETE":
            log.warning(f"Got status {status} for batch_id {updated_resource_batch['id']}")

        event_id = updated_resource_batch["id"]
        if event_id in unique_message_ids:
            return event_id, event_request_id, True
        else:
            return "", event_request_id, False

    log.info(f"Waiting for dataloader responses to batch IDs: {batch_ids}")

    wait_for_messages(
        consumer,
        matcher=matcher,
        callback=batch_handler,
        unique_message_ids={batch_id: None for batch_id in batch_ids},
        # As long as we are receiving new messages from DL we don't care if they are matched or not
        # This avoids premature timeouts when we receive lots of PENDING events that don't match
        # but aren't actually an issue.
        inter_message_timeout=200,
        matched_message_timeout=0,
    )
    log.info("Finished waiting for dataloader responses")


def batch_get_resource_batches(ids: list[str]) -> dict[str, dict]:
    return endtoend.helper.send_request(
        "get", "/v1/resource-batches:batchGet", params={"ids": ids}
    )["resource_batches"]


def wait_for_resource_batch(
    batch_id: str, expected_status: str = "RESOURCE_BATCH_STATUS_COMPLETE"
) -> dict[str, Any]:
    """
    Waits for a resource batch to reach the expected status
    """
    log.info(f"Waiting for dataloader responses to batch ID: {batch_id}")
    try:
        batch = endtoend.helper.retry_call(
            func=batch_get_resource_batches,
            f_args=[[batch_id]],
            result_wrapper=lambda x: x[batch_id]["status"],
            expected_result=expected_status,
            back_off=1.5,
            failure_message=f"Batch {batch_id} still pending",
        )[batch_id]
    except ValueError:
        message = f"Batch {batch_id} never reached status {expected_status}"
        log.error(message)
        raise AssertionError(message)

    return batch
