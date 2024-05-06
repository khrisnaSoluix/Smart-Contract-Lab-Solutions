# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
# standard libs
import logging
import os

# third party
from confluent_kafka import Consumer

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.endtoend.kafka_helper import kafka_only_helper, wait_for_messages

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


ACCOUNT_UPDATE_EVENTS_TOPIC = "vault.core_api.v1.accounts.account_update.events"

SUPPORTED_ACCOUNT_UPDATE_TYPES = [
    "activation_update",
    "closure_update",
    "instance_param_vals_update",
    "product_version_update",
]

TERMINAL_ACCOUNT_STATUSES = [
    "ACCOUNT_UPDATE_STATUS_COMPLETED",
    "ACCOUNT_UPDATE_STATUS_ERRORED",
    "ACCOUNT_UPDATE_STATUS_REJECTED",
]


def wait_for_all_account_updates_to_complete(
    account_id: str, error_on_no_account_updates: bool = True
) -> None:
    """
    Waits for all account updates for a given account to no longer be pending execution. They may
    not necessarily be completed successfully. No account updates is treated as an error by
    default
    :param account_id: account to check account-updates for
    :param error_on_no_account_updates: if true, no account updates being found is treated as an
    error.
    :return: None
    """

    if error_on_no_account_updates:
        account_updates = endtoend.helper.retry_call(
            func=endtoend.core_api_helper.get_account_updates,
            f_args=[account_id],
            result_wrapper=lambda x: len(x) > 0,
            expected_result=True,
            back_off=1.5,
            failure_message=f"Account id {account_id} has no account updates",
        )
        # Checking that account updates exist can provide us an early opportunity to return
        if not any(
            account_update["status"] == "ACCOUNT_UPDATE_STATUS_PENDING_EXECUTION"
            for account_update in account_updates
        ):
            return

    endtoend.helper.retry_call(
        func=endtoend.core_api_helper.get_account_updates,
        f_args=[account_id, ["ACCOUNT_UPDATE_STATUS_PENDING_EXECUTION"]],
        result_wrapper=lambda x: len(x),
        expected_result=0,
        back_off=1.5,
        failure_message=f"Account id {account_id} still has account_updates in"
        f" ACCOUNT_UPDATE_STATUS_PENDING_EXECUTION ",
    )


def wait_for_account_update(
    account_id: str = "",
    account_update_type: str = "",
    account_update_id: str = "",
    target_status: str = "ACCOUNT_UPDATE_STATUS_COMPLETED",
):
    """
    For a given account_id and account_update_type, or an account_update_id, wait for the
    corresponding account_update to reach the target status.
    If using account_id + account_update_type, the latest account-update of that type is used
    :param account_id: the account_id to use to select the account-update to poll. Only used if
    account_update_id is not populated
    :param account_update_type: the account-update type to use to select the account-update to poll.
    Only used if account_update_id is not populated
    :param account_update_id: id of the specific account update to wait for
    :param target_status: the account-update status to keep polling for
    """
    if not account_update_id:
        account_update = endtoend.helper.retry_call(
            func=endtoend.core_api_helper.get_account_updates_by_type,
            f_kwargs={"account_id": account_id, "update_types": [account_update_type]},
            expected_result=True,
            result_wrapper=lambda x: len(x) > 0,
            failure_message=f"No account updates for account {account_id} could be found.",
        )[-1]
        account_update_id = account_update["id"]

    if endtoend.testhandle.use_kafka:
        wait_for_account_updates_by_id(
            account_update_ids=[account_update_id], target_status=target_status
        )

    else:
        endtoend.helper.retry_call(
            func=endtoend.core_api_helper.get_account_update,
            f_args=[account_update_id],
            expected_result=target_status,
            result_wrapper=lambda x: x["status"],
            back_off=1.5,
            failure_message=f"Account update {account_update_id} for account {account_id} "
            "never reached"
            f"status {target_status}",
        )


@kafka_only_helper
def wait_for_account_updates(
    account_ids: list[str],
    account_update_type: str = "",
    target_status: str = "ACCOUNT_UPDATE_STATUS_COMPLETED",
):
    """
    listen to the account update Kafka topic for updates to accounts in account_ids of type
    account_update_type.
    :param account_ids: a collection of accounts to listen for account updates
    :param account_update_type: used to specify the account update type to find for each account in
    account_ids
    :param target_status: the account update status to wait for
    """
    if account_update_type != "" and account_update_type not in SUPPORTED_ACCOUNT_UPDATE_TYPES:
        log.warning(
            f"The account update type {account_update_type} is not recognised as a valid "
            "account_update_type."
        )

    consumer = endtoend.testhandle.kafka_consumers[ACCOUNT_UPDATE_EVENTS_TOPIC]

    def matcher(event_msg, unique_message_ids):
        if target_status == "ACCOUNT_UPDATE_STATUS_PENDING_EXECUTION":
            account_update_wrapper = event_msg.get("account_update_created")
        else:
            account_update_wrapper = event_msg.get("account_update_updated")
        event_request_id = event_msg.get("event_id")
        if account_update_wrapper:
            account_update = account_update_wrapper["account_update"]
            if account_update["account_id"] in unique_message_ids:
                if account_update["status"] == target_status and (
                    # If account_update_type is specified, look for it
                    account_update_type == ""
                    or account_update_type in account_update
                ):
                    return (
                        account_update["account_id"],
                        event_request_id,
                        True,
                    )
                if account_update["status"] in TERMINAL_ACCOUNT_STATUSES:
                    log.warning(
                        f"Account update {account_update['id']} reached terminal status"
                        f" {account_update['status']} that did not match target status"
                        f" {target_status}"
                    )

        return "", event_request_id, False

    failed_account_updates = wait_for_messages(
        consumer,
        matcher=matcher,
        callback=None,
        unique_message_ids={account_id: None for account_id in account_ids},
        inter_message_timeout=30,
        matched_message_timeout=30,
    )

    if len(failed_account_updates) > 0:
        raise Exception(
            f"Failed to retrieve {len(failed_account_updates)} of {len(account_ids)} account "
            f"updates for account ids: {', '.join(failed_account_updates.keys())}"
        )


@kafka_only_helper
def wait_for_account_updates_by_id(
    account_update_ids: list[str],
    target_status: str = "ACCOUNT_UPDATE_STATUS_COMPLETED",
):
    """
    listen to the account update events Kafka topic for specific account update ids.
    :param account_update_ids: a collection of account update ids to listen for
    :param target_status: the account update status to wait for
    """
    consumer: Consumer = endtoend.testhandle.kafka_consumers[ACCOUNT_UPDATE_EVENTS_TOPIC]

    def matcher(event_msg, unique_message_ids):
        if target_status == "ACCOUNT_UPDATE_STATUS_PENDING_EXECUTION":
            account_update_wrapper = event_msg.get("account_update_created")
        else:
            account_update_wrapper = event_msg.get("account_update_updated")
        event_request_id = event_msg.get("event_id")
        if account_update_wrapper:
            account_update = account_update_wrapper["account_update"]
            if account_update["id"] in unique_message_ids:
                if account_update["status"] == target_status:
                    return (
                        account_update["id"],
                        event_request_id,
                        True,
                    )
                if account_update["status"] in TERMINAL_ACCOUNT_STATUSES:
                    log.warning(
                        f"Account update {account_update['id']} reached terminal status"
                        f" {account_update['status']} that did not match target status"
                        f" {target_status}"
                    )

        return "", event_request_id, False

    failed_account_updates = wait_for_messages(
        consumer,
        matcher=matcher,
        callback=None,
        unique_message_ids={update_id: None for update_id in account_update_ids},
        inter_message_timeout=30,
        matched_message_timeout=45,
    )

    if len(failed_account_updates) > 0:
        raise Exception(
            f"Failed to retrieve {len(failed_account_updates)} of {len(account_update_ids)} "
            f"account updates for update ids: {', '.join(failed_account_updates.keys())}"
        )
