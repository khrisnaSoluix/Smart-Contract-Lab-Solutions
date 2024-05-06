# standard libs
import logging
import os
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.common.balance_helpers import (
    Balance,
    BalanceDimensions,
    compare_balances as compare_balances_inner,
)
from inception_sdk.test_framework.endtoend.core_api_helper import (
    get_live_balances,
    get_timerange_balances,
)
from inception_sdk.test_framework.endtoend.kafka_helper import kafka_only_helper, wait_for_messages

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

ACCOUNT_BALANCE_EVENTS_TOPIC = "vault.core_api.v1.balances.account_balance.events"


@kafka_only_helper
def wait_for_balance_updates(
    posting_instruction_batch_ids: list[str],
    matched_message_timeout: int = 30,
    inter_message_timeout: int = 30,
) -> list[dict[str, str]]:
    """
    Kafka-based helper to wait for balance updates
    :param posting_instruction_batch_ids: list of posting instruction batch ids
     that have triggered the balance updates to wait for
    :param matched_message_timeout: a maximum time to wait between receiving matched messages from
    the consumer (0 for no timeout)
    :param inter_message_timeout: a maximum time to wait between receiving any messages from the
    consumer (0 for no timeout)
    :return: list of balances
    """

    consumer = endtoend.testhandle.kafka_consumers[ACCOUNT_BALANCE_EVENTS_TOPIC]

    balances = []

    def matcher(event_msg, unique_message_ids):
        pib_id = event_msg["posting_instruction_batch_id"]
        event_request_id = event_msg["event_id"]
        if pib_id in unique_message_ids:
            items = [
                item
                for item in event_msg["balances"]
                if item["posting_instruction_batch_id"] == pib_id
            ]
            balances.extend(items)
            return pib_id, event_request_id, True
        else:
            return "", event_request_id, False

    log.info(f"Waiting for {len(posting_instruction_batch_ids)} balance updates")

    wait_for_messages(
        consumer,
        matcher=matcher,
        callback=None,
        unique_message_ids={pib_id: None for pib_id in posting_instruction_batch_ids},
        matched_message_timeout=matched_message_timeout,
        inter_message_timeout=inter_message_timeout,
    )

    log.info("All balances updated")
    return balances


def wait_for_all_account_balances(
    accounts_expected_balances: dict[str, list[tuple[BalanceDimensions, str]]],
    description: str = "",
    back_off: float = 1.5,
) -> None:
    """
    Waits until all accounts match the expected balances outcome
    :param accounts_expected_balances: Key being the account id and value being
    the expected balances
    :param description: description of the expected outcome
    :return: None
    """

    if endtoend.testhandle.use_kafka:
        wait_for_account_balances_by_ids(accounts_expected_balances)
    else:
        for account_id in [*accounts_expected_balances.keys()]:
            endtoend.helper.retry_call(
                func=compare_balances,
                f_args=[
                    account_id,
                    accounts_expected_balances[account_id],
                ],
                expected_result={},
                back_off=back_off,
                failure_message=f'Unexpected balances for {account_id} at stage "{description}"',
            )


def wait_for_account_balances_by_pib(
    account_id: str, posting_instruction_batch_id: str | None = None
) -> list[dict[str, str]]:
    """
    Posting Instruction Batch ID has been removed from the balances endpoint.
    The current implementation is supported from our side and is a simple
    iteration to find which balances match up with a PIB ID
    """
    balances = get_timerange_balances(account_id)

    if posting_instruction_batch_id:
        return [
            balance
            for balance in balances
            if balance["posting_instruction_batch_id"] == posting_instruction_batch_id
        ]

    return balances


@kafka_only_helper
def wait_for_account_balances_by_ids(
    accounts_expected_balances: dict[str, list[tuple[BalanceDimensions, str]]],
    matched_message_timeout: int = 30,
    inter_message_timeout: int = 30,
    return_failed_accounts: bool = False,
) -> None | dict[str, list[tuple[BalanceDimensions, str]]]:
    """
    listen to the balance update events Kafka topic for the account_id's specified.
    :param accounts_expected_balances: Key being the account id and value being
    the expected balances
    :param matched_message_timeout: a maximum time to wait between receiving matched messages from
    the consumer (0 for no timeout)
    :param inter_message_timeout: a maximum time to wait between receiving any messages from the
    consumer (0 for no timeout)
    :param return_failed_accounts: boolean to return failed account ids instead of raising an
    exception
    :return: None
    """
    consumer = endtoend.testhandle.kafka_consumers[ACCOUNT_BALANCE_EVENTS_TOPIC]

    def matcher(event_msg, unique_message_ids):
        event_account_id = event_msg["account_id"]
        event_request_id = event_msg["event_id"]
        if event_account_id in unique_message_ids:
            balance_wrapper = event_msg.get("balances")
            actual_balances = create_balance_dict(balance_wrapper)
            if (
                compare_balances_inner(
                    accounts_expected_balances[event_account_id], actual_balances
                )
                == {}
            ):
                return (
                    event_account_id,
                    event_request_id,
                    True,
                )
            else:
                return ("", event_request_id, True)
        else:
            return "", event_request_id, False

    failed_account_ids = wait_for_messages(
        consumer,
        matcher=matcher,
        callback=None,
        unique_message_ids=accounts_expected_balances,
        matched_message_timeout=matched_message_timeout,
        inter_message_timeout=inter_message_timeout,
    )

    if return_failed_accounts:
        return failed_account_ids

    if len(failed_account_ids) > 0:
        transformed_outcome = (
            "Failed to retrieve all expected account balance updates for account ids\n"
        )

        for account_id in failed_account_ids.keys():
            transformed_outcome += f"\n{account_id}: \n" + str(
                accounts_expected_balances[account_id]
            )
        raise Exception(transformed_outcome)


def wait_for_posting_balance_updates(
    account_id: str, posting_instruction_batch_id: str
) -> list[dict[str, str]]:
    """
    Waits for the balances updates corresponding to a given posting instruction batch
    :param account_id: account id to check balances for
    :param posting_instruction_batch_id: id of the posting instruction batch to get balance
    updates for
    :return: the balances updated by the posting instruction batch. This does not include balances
    that weren't affected, or
    """

    if endtoend.testhandle.use_kafka:
        return wait_for_balance_updates(
            posting_instruction_batch_ids=[posting_instruction_batch_id],
        )
    else:
        return endtoend.helper.retry_call(
            func=wait_for_account_balances_by_pib,
            f_kwargs={
                "account_id": account_id,
                "posting_instruction_batch_id": posting_instruction_batch_id,
            },
            expected_result=True,
            result_wrapper=lambda x: len(x) > 0,
            failure_message=f"Balances for pib {posting_instruction_batch_id} and account id "
            f"{account_id} never updated",
        )


def wait_for_account_balances(
    account_id: str,
    expected_balances: list[tuple[BalanceDimensions, str]],
    description: str = "",
    back_off: float = 1.5,
) -> None:
    """
    Waits until balances match the expected outcome
    :param account_id: the account id to check balances for
    :param expected_balances: the expected balances
    :param description: description of the expected outcome
    :return: None
    """

    if endtoend.testhandle.use_kafka:
        wait_for_account_balances_by_ids({account_id: expected_balances})
    else:
        endtoend.helper.retry_call(
            func=compare_balances,
            f_args=[account_id, expected_balances],
            expected_result={},
            back_off=back_off,
            failure_message=f'Unexpected balances for {account_id} at stage "{description}"',
        )


def create_balance_dict(balances: list[dict[str, str]]) -> defaultdict[BalanceDimensions, Balance]:
    """
    :param balances: list of balances returned by the /v1/balances endpoint
    :return: contract-like balance dictionary mapping dimensions to balances
    """

    balance_dict = {
        BalanceDimensions(
            balance["account_address"],
            balance["asset"],
            balance["denomination"],
            balance["phase"],
        ): Balance(
            balance["total_credit"],
            balance["total_debit"],
            balance["amount"],
            standardise_balance_value_time_format(balance["value_time"]),
        )
        for balance in balances
    }

    balance_default_dict = defaultdict(lambda: Balance(0, 0, 0), balance_dict)

    return balance_default_dict


def compare_balances(
    account_id: str, expected_balances: list[tuple[BalanceDimensions, str]]
) -> dict[BalanceDimensions, dict[str, Decimal]]:
    """
    Compare the actual live balances to specified expected_balances. Any dimensions not included in
    expected_balances are ignored. Only accounts for net, not cr and dr values
    :param account_id: the account id of the account to check balances for
    :param expected_balances: the expected balances
    :return: the delta between expected and actual balances. For each BalanceDimensions with a
    mismatch in net values, an entry to the dictionary is added like:
    {
       BalanceDimensions: {
           'expected': Decimal(expected net)
           'actual': Decimal(actual net)
        }
    }
    """
    balance_dict = create_balance_dict(get_live_balances(account_id))
    return compare_balances_inner(expected_balances, balance_dict)


def get_balances_dict(
    account_id: str,
    from_value_time: datetime | None = None,
    to_value_time: datetime | None = None,
    exclude_starting_balance: bool = False,
    live: bool = True,
) -> defaultdict[BalanceDimensions, Balance]:
    """
    Retrieves balances from Core API and transforms into a balance dictionary
    :param account_id: the account to retrieve balances for
    :param from_value_time: Optional value time to retrieve from. Ignored if live=True
    :param to_value_time: Optional value time to retrieve up until. Ignored if live=True
    :param exclude_starting_balance: if True the balances before from_value_time are excluded.
    Ignored if live=True
    :param live: set to True if for live balances only, or False to also get historical balances
    :return: contract-like balance dictionary mapping dimensions to balances
    """

    return create_balance_dict(
        get_live_balances(account_id)
        if live
        else get_timerange_balances(account_id, from_value_time, to_value_time)
    )


def standardise_balance_value_time_format(timestamp: str) -> datetime:
    """
    Removes milliseconds from datetime string to a datetime string of exactly length 20
    and returns this as a datetime object.
    e.g 1990-01-01T00:00:00.12345Z becomes 1990-01-01T00:00:00Z which is then converted
    into a datetime object.
    :param timestamp: dateime to be converted, defaults to '1970-01-01T00:00:00Z'

    :return: timestamp as a datetime object
    """
    if timestamp:
        return datetime.strptime(timestamp[:19] + "Z", "%Y-%m-%dT%H:%M:%SZ")
    return datetime.strptime("1970-01-01T00:00:00Z", "%Y-%m-%dT%H:%M:%SZ")
