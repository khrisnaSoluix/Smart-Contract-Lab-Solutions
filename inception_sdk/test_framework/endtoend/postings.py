# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
import logging
import os
import time
import uuid
from datetime import datetime
from json import dumps
from typing import Any

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.endtoend.contracts_helper import DUMMY_CONTRA
from inception_sdk.test_framework.endtoend.helper import send_request
from inception_sdk.test_framework.endtoend.kafka_helper import (
    kafka_only_helper,
    produce_message,
    wait_for_messages,
)
from inception_sdk.vault.postings.posting_classes import (
    AuthorisationAdjustment,
    CustomInstruction,
    InboundAuthorisation,
    InboundHardSettlement,
    OutboundAuthorisation,
    OutboundHardSettlement,
    Posting,
    Release,
    Settlement,
    Transfer,
)
from inception_sdk.vault.postings.postings_helper import create_posting_instruction_batch

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


POSTING_PHASES = [
    "POSTING_PHASE_COMMITTED",
    "POSTING_PHASE_PENDING_OUTGOING",
    "POSTING_PHASE_PENDING_INCOMING",
]

MIGRATIONS_POSTINGS_REQUESTS_TOPIC = "vault.migrations.postings.requests"
MIGRATIONS_POSTINGS_RESPONSES_TOPIC = "vault.migrations.postings.responses"
POSTINGS_API_REQUEST_TOPIC = "vault.core.postings.requests.v1"
POSTINGS_API_RESPONSE_TOPIC = "vault.core.postings.async_creation_api.responses"

POSTINGS_API_CLIENT_ID = "AsyncCreatePostingInstructionBatch"


def create_posting_async_operation(pib: dict[str, dict]) -> str:
    """
    Sends an asynchronous posting request and returns the asynchronous operation ID. Note, the
    latter should not to be confused with the ID of the posting instruction batch as these are
    different.
    :param pib: posting instruction batch
    :return: asynchronous operation ID
    """
    post_body = {"request_id": uuid.uuid4().hex, "posting_instruction_batch": pib}
    post_body = dumps(post_body)
    resp = send_request("post", "/v1/posting-instruction-batches:asyncCreate", data=post_body)

    return resp["id"]


def wait_until_async_operation_is_done(
    async_id: str, pib: dict[str, dict], timeout: int = 5
) -> str:
    """
    Retrieves the results of an asynchronous posting request when it is marked as done, returning
    the posting instruction batch ID. Also includes a timeout facility to wait for the response.
    :param async_id: asynchronous id of the original request
    :param pib: posting instruction batch
    :param timeout: number of iterations to query for the result, with a 1 second sleep after each
    iteration
    :return: posting instruction batch ID
    """
    get_body = {"ids": async_id}
    for _ in range(timeout):
        resp = send_request(
            "get",
            "/v1/posting-instruction-batches/async-operations:batchGet",
            params=get_body,
        )

        if (
            resp["async_operations"][async_id]["done"] is True
            and "response" in resp["async_operations"][async_id]
        ):
            return resp["async_operations"][async_id]["response"]["id"]
        elif (
            resp["async_operations"][async_id]["done"] is True
            and "error" in resp["async_operations"][async_id]
        ):
            errorstr = str(resp["async_operations"][async_id]["error"])
            pibstr = str(pib)
            raise Exception(
                f"wait_until_async_operation_is_done got an error, "
                f"async_id: {async_id}, pib: {pibstr}, error: {errorstr}"
            )

        time.sleep(1)

    raise TimeoutError(
        f"{datetime.utcnow()} - "
        "Posting never got accepted or created. Is it formatted correctly?\n"
        "Posting Instruction Batch:\n{}Async Id:\n{}".format(pib, async_id)
    )


def get_posting_batch(pib_id: str) -> Any:
    """
    Sends a request to retrieve a posting batch.
    :param pib_id: posting instruction batch ID
    :return: posting instruction batch
    """
    return send_request("get", f"/v1/posting-instruction-batches/{pib_id}", {})


def send_and_wait_for_posting_instruction_batch(
    pib: dict[str, dict], timeout: int | None = None, migration: bool = False
) -> str:
    """
    Sends and waits for a posting response on a kafka topic. Note, when using the migration option,
    posting requests and reponses are received on the dedicated migration topics (as opposed to the
    standard topics).
    :param pib: posting instruction batch
    :param timeout: number of iterations to query for the result, with a 1 second sleep after each
    iteration
    :param migration: an option to determine whether to send and listen on the migration or
    standard posting topics
    :return: posting instruction batch ID
    """
    pib_id = ""
    if endtoend.testhandle.use_kafka:
        request_id = create_and_produce_posting_request(
            endtoend.testhandle.kafka_producer, pib, migration=migration
        )
        responses, errors = wait_for_posting_responses([request_id], migration=migration)
        if error := errors.get(request_id):
            raise ValueError(f"Posting {request_id=} resulted in {error=}")
        elif responses:
            pib_id = responses[0] if responses else ""
        else:
            raise ValueError(f"No response found for posting {request_id=}")

    else:
        async_id = create_posting_async_operation(pib)
        timeout = timeout or 5
        pib_id = wait_until_async_operation_is_done(async_id, pib, timeout)

    return pib_id


def inbound_hard_settlement(
    amount,
    account_id=None,
    value_datetime=None,
    internal_account_id=None,
    denomination=None,
    client_transaction_id=None,
    override=False,
    advice=None,
    batch_details=None,
    instruction_details=None,
    client_batch_id=None,
    payment_device_token=None,
    client_id=None,
):
    if not account_id and not payment_device_token:
        raise NameError(
            f"{datetime.utcnow()} - "
            "Didn't pass either account_id, or a payment_device_token for payment"
        )

    instruction = generate_instruction(
        is_inbound=True,
        is_auth=False,
        amount=amount,
        denomination=denomination,
        target_account_id=account_id,
        internal_account_id=internal_account_id,
        advice=advice,
        payment_device_token=payment_device_token,
    )

    return send_posting_instruction_batch(
        [instruction],
        value_datetime=value_datetime,
        client_transaction_id=client_transaction_id,
        override=override,
        batch_details=batch_details,
        instruction_details=instruction_details,
        client_batch_id=client_batch_id,
        timeout=10,
        client_id=client_id,
    )


def outbound_hard_settlement(
    amount,
    account_id=None,
    value_datetime=None,
    internal_account_id=None,
    denomination=None,
    client_transaction_id=None,
    advice=None,
    override=False,
    batch_details=None,
    instruction_details=None,
    client_batch_id=None,
    payment_device_token=None,
    client_id=None,
):
    if not account_id and not payment_device_token:
        raise NameError(
            f"{datetime.utcnow()} - "
            "Didn't pass either account_id, or a payment_device_token for payment"
        )

    instruction = generate_instruction(
        is_inbound=False,
        is_auth=False,
        amount=amount,
        denomination=denomination,
        target_account_id=account_id,
        internal_account_id=internal_account_id,
        advice=advice,
        payment_device_token=payment_device_token,
    )

    return send_posting_instruction_batch(
        [instruction],
        value_datetime=value_datetime,
        client_transaction_id=client_transaction_id,
        override=override,
        batch_details=batch_details,
        instruction_details=instruction_details,
        client_batch_id=client_batch_id,
        timeout=10,
        client_id=client_id,
    )


def outbound_auth(
    amount,
    account_id=None,
    value_datetime=None,
    internal_account_id=None,
    denomination=None,
    client_transaction_id=None,
    advice=None,
    batch_details=None,
    instruction_details=None,
    client_batch_id=None,
    payment_device_token=None,
    client_id=None,
):
    if not account_id and not payment_device_token:
        raise NameError(
            f"{datetime.utcnow()} - "
            "Didn't pass either account_id, or a payment_device_token for payment"
        )

    instruction = generate_instruction(
        is_inbound=False,
        is_auth=True,
        amount=amount,
        denomination=denomination,
        target_account_id=account_id,
        internal_account_id=internal_account_id,
        advice=advice,
        payment_device_token=payment_device_token,
    )

    return send_posting_instruction_batch(
        [instruction],
        value_datetime=value_datetime,
        client_transaction_id=client_transaction_id,
        instruction_details=instruction_details,
        batch_details=batch_details,
        client_batch_id=client_batch_id,
        client_id=client_id,
    )


def inbound_auth(
    amount,
    account_id=None,
    value_datetime=None,
    internal_account_id=None,
    denomination=None,
    client_transaction_id=None,
    advice=None,
    batch_details=None,
    instruction_details=None,
    client_batch_id=None,
    payment_device_token=None,
    client_id=None,
):
    if not account_id and not payment_device_token:
        raise NameError(
            f"{datetime.utcnow()} - "
            "Didn't pass either account_id, or a payment_device_token for payment"
        )

    instruction = generate_instruction(
        is_inbound=True,
        is_auth=True,
        amount=amount,
        denomination=denomination,
        target_account_id=account_id,
        internal_account_id=internal_account_id,
        advice=advice,
        payment_device_token=payment_device_token,
    )

    return send_posting_instruction_batch(
        [instruction],
        value_datetime=value_datetime,
        client_transaction_id=client_transaction_id,
        instruction_details=instruction_details,
        batch_details=batch_details,
        client_batch_id=client_batch_id,
        client_id=client_id,
    )


def auth_adjustment(
    amount,
    client_transaction_id,
    value_datetime=None,
    instruction_details=None,
    client_batch_id=None,
    client_id=None,
):
    instruction = AuthorisationAdjustment(amount=amount)

    return send_posting_instruction_batch(
        [instruction],
        value_datetime=value_datetime,
        client_transaction_id=client_transaction_id,
        instruction_details=instruction_details,
        client_batch_id=client_batch_id,
        client_id=client_id,
    )


def settlement(
    amount,
    client_transaction_id,
    value_datetime=None,
    final=False,
    instruction_details=None,
    client_batch_id=None,
    batch_details=None,
    client_id=None,
):
    instruction = Settlement(amount=amount, final=final)

    return send_posting_instruction_batch(
        [instruction],
        value_datetime=value_datetime,
        client_transaction_id=client_transaction_id,
        instruction_details=instruction_details,
        client_batch_id=client_batch_id,
        batch_details=batch_details,
        client_id=client_id,
    )


def create_release_event(
    client_transaction_id,
    value_datetime=None,
    instruction_details=None,
    client_batch_id=None,
    batch_details=None,
    client_id=None,
):
    instruction = Release()

    return send_posting_instruction_batch(
        [instruction],
        value_datetime=value_datetime,
        client_transaction_id=client_transaction_id,
        instruction_details=instruction_details,
        client_batch_id=client_batch_id,
        batch_details=batch_details,
        client_id=client_id,
    )


def create_transfer(
    amount,
    debtor_target_account_id,
    creditor_target_account_id,
    value_datetime=None,
    denomination=None,
    client_transaction_id=None,
    instruction_details=None,
    client_batch_id=None,
    client_id=None,
):
    instruction = Transfer(
        amount=amount,
        debtor_target_account_id=debtor_target_account_id,
        creditor_target_account_id=creditor_target_account_id,
        denomination=denomination,
    )

    return send_posting_instruction_batch(
        [instruction],
        value_datetime=value_datetime,
        client_transaction_id=client_transaction_id,
        instruction_details=instruction_details,
        client_batch_id=client_batch_id,
        client_id=client_id,
    )


def create_posting(account_id, amount, denomination, asset, account_address, phase, credit):
    posting = Posting(account_id, amount, credit, denomination, asset, account_address, phase)

    return posting


def create_custom_instruction(
    postings,
    value_datetime=None,
    client_transaction_id=None,
    batch_details=None,
    instruction_details=None,
    client_batch_id=None,
    client_id=None,
):
    instruction = CustomInstruction(postings=postings)

    return send_posting_instruction_batch(
        [instruction],
        value_datetime=value_datetime,
        client_transaction_id=client_transaction_id,
        batch_details=batch_details,
        instruction_details=instruction_details,
        client_batch_id=client_batch_id,
        client_id=client_id,
    )


def send_posting_instruction_batch(
    instructions,
    value_datetime=None,
    client_transaction_id=None,
    override=False,
    batch_details=None,
    instruction_details=None,
    client_batch_id=None,
    timeout=None,
    client_id=None,
):
    return send_and_wait_for_posting_instruction_batch(
        create_posting_instruction_batch(
            instructions,
            value_datetime=value_datetime,
            client_transaction_id=client_transaction_id,
            override=override,
            batch_details=batch_details,
            instruction_details=instruction_details,
            client_batch_id=client_batch_id,
            client_id=client_id,
        )["posting_instruction_batch"],
        timeout,
    )


class BatchCompletionRecorder(object):
    def __init__(self, pib_ids: list[str] | None = None) -> None:
        self.pib_ids = pib_ids or []
        self.errored_responses: dict[str, dict[str, str]] = {}

    def __call__(self, event_msg) -> Any:
        """
        When a postings batch is completed we simply record the id.
        """
        if error := event_msg.get("error", {}):
            # no PIB is actually created so event "id", which is output-only and normally PIB id
            # is meaningless
            self.errored_responses[event_msg["create_request_id"]] = error
        else:
            self.pib_ids.append(event_msg["id"])


@kafka_only_helper
def wait_for_posting_responses(
    request_ids: list[str],
    statuses: list[str] | None = None,
    migration: bool = True,
    timeout: int = 0,
) -> tuple[list[str], dict[str, dict[str, str]]]:
    """
    Waits for a posting response on a kafka topic, with the ability to filter for select statuses
    desired. Note, when using the migration option, ensure postings are sent to the migration topic
    (as opposed to the standard topic).
    :param request_ids: list of request ID's
    :param statuses: list of statuses to match against in the posting responses
    :param migration: an option to determine whether to listen on the migration or standard posting
    response
    :param timeout: a maximum time to wait between receiving matched messages from the consumer (0
    for no timeout)
    :return: a list of committed posting instruction batch ids (could be accepted or rejected) and a
    dict of errored posting instruction batch create_request_id to the error received
    """
    posting_response_topic = (
        MIGRATIONS_POSTINGS_RESPONSES_TOPIC if migration else POSTINGS_API_RESPONSE_TOPIC
    )
    consumer = endtoend.testhandle.kafka_consumers[posting_response_topic]
    batch_completion_recorder = BatchCompletionRecorder()

    unique_statuses = set(statuses) if statuses else set()

    def matcher(event_msg, unique_message_ids):
        event_id = event_msg.get("create_request_id")
        event_response_id = event_msg["id"]
        if event_id in unique_message_ids:
            if not unique_statuses or event_msg["status"] in unique_statuses:
                return event_id, event_response_id, True

        return "", event_response_id, False

    log.debug(f"Waiting for {len(request_ids)} postings to commit")

    wait_for_messages(
        consumer,
        matcher=matcher,
        callback=batch_completion_recorder,
        unique_message_ids={request_id: None for request_id in request_ids},
        inter_message_timeout=30,
        matched_message_timeout=timeout,
    )

    log.debug("All postings committed")

    return batch_completion_recorder.pib_ids, batch_completion_recorder.errored_responses


@kafka_only_helper
def create_and_produce_posting_request(
    producer, pib: dict[str, Any], key: str | None = None, migration: bool = False
) -> str:
    """
    For a given PIB, creates a create_posting_instruction_batch_request and produces it to the
    relevant kafka topic, returning the request's id
    :param producer: kafka producer to use
    :param pib: the posting instruction batch to include in the request
    :param key: optional key for kafka partitioning
    :param migration: if true, the request is produced to the migrations request topic. Otherwise
     the regular posting request topic is used
    """
    request_id = str(uuid.uuid4())
    event_msg = {"request_id": request_id, "posting_instruction_batch": pib}
    postings_topic = MIGRATIONS_POSTINGS_REQUESTS_TOPIC if migration else POSTINGS_API_REQUEST_TOPIC
    # We use account_id as key to reduce the risk of postings racing against each other
    # This has no functional impact, but does reduce the amount of potential backdating
    # Note: postings on same partition can still race against each other
    # due to PP design
    produce_message(producer, postings_topic, dumps(event_msg), key)
    return request_id


def produce_posting_messages(
    producer, account_postings: dict[str, list], tps: int = 200
) -> list[str]:
    """
    Produces posting requests for the given accounts, returning the corresponding create request ids
    :param producer: the kafka producer to use
    :param account_postings: list of posting instruction batches to produce per account
    :param tps: the maximum TPS to produce at. This determines the sleep duration between produce
     calls, so the actual TPS will be a little below
    :return: list of create request ids for the produced posting instruction batch requests
    """

    log.info(f"Producing posting requests for {len(account_postings)} accounts")

    # We assume equal number of postings per account
    num_postings = len(account_postings[list(account_postings.keys())[0]])

    create_request_ids = []
    sleep_time = 1 / tps if tps else 0
    # Publish postings by index and then account. Otherwise we get a lot of backdating.
    # We may have to implement something more complex where we send each posting when the previous
    # was successfully completed
    for posting_index in range(num_postings):
        for account_id, pibs in account_postings.items():
            create_request_ids.append(
                create_and_produce_posting_request(
                    producer, pibs[posting_index], key=account_id, migration=True
                )
            )
            time.sleep(sleep_time)
    producer.flush()
    return create_request_ids


def generate_instruction(
    amount: str,
    is_inbound: bool,
    is_auth: bool,
    denomination: str | None = None,
    target_account_id: str | None = None,
    internal_account_id: str | None = None,
    advice: str | None = None,
    payment_device_token: str | None = None,
) -> InboundHardSettlement | OutboundHardSettlement | InboundAuthorisation | OutboundAuthorisation:
    """
    Helper function that returns the posting instruction with internal_account_id defined
    param amount: string represenation of the amount to be sent
    param denomination: denomination in which the money should be sent
    param target_account_id: account to which the money should be sent
    param internal_account_id: internal account to be used (default DUMMY_CONTRA)
    param advice: if true, the amount will be authorised regardless of balance check
    param payment_device_token: payment_device_token to which the money should be sent
    param is_inbound: determines if inbound or outbound posting
    param is_auth: determines if authorisation or hard settlement
    """

    internal_account_id = internal_account_id or DUMMY_CONTRA

    internal_account_id = endtoend.testhandle.internal_account_id_to_uploaded_id[
        internal_account_id
    ]

    if is_inbound:
        posting = InboundAuthorisation if is_auth else InboundHardSettlement
    else:
        posting = OutboundAuthorisation if is_auth else OutboundHardSettlement

    return posting(
        amount=amount,
        denomination=denomination,
        target_account_id=target_account_id,
        internal_account_id=internal_account_id,
        advice=advice,
        payment_device_token=payment_device_token,
    )
