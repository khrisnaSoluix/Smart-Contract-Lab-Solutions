from decimal import Decimal
from datetime import datetime
from typing import Optional

from inception_sdk.vault.contracts.supervisor.types_extension import (
    EventTypeSchedule,
    Vault,
    SupervisorVault,
    Rejected,
    RejectedReason,
)

import library.features.v3.common.utils as utils


def get_supervisees_for_alias(
    vault: SupervisorVault, alias: str, num_requested: Optional[int] = None
) -> list[Vault]:
    """
    Returns a list of supervisee vault objects for the given alias, ordered by account creation date
    :param vault: vault, supervisor vault object
    :param alias: str, the supervisee alias to filter for
    :param num_requested: int, the exact number of expected supervisees
    :raises Rejected: if num_requested is specified and the exact amount of supervisees for the
    alias does not match
    :return: list, supervisee vault objects for given alias, ordered by account creation date
    """
    sorted_supervisees = sort_supervisees(
        [
            supervisee
            for supervisee in vault.supervisees.values()
            if supervisee.get_alias() == alias
        ],
    )

    if num_requested:
        if not len(sorted_supervisees) == num_requested:
            raise Rejected(
                f"Requested {num_requested} {alias} accounts but found {len(sorted_supervisees)}.",
                reason_code=RejectedReason.AGAINST_TNC,
            )
    return sorted_supervisees


def sort_supervisees(supervisees: list[Vault]) -> list[Vault]:
    """
    Sorts supervisees first by creation date, and then alphabetically by id if
    numerous supervisees share the same creation date and creates a list of ordered
    vault objects.
    :param supervisees: list[Vault], list of supervisee vault objects
    :return sorted_supervisees: list[Vault], list of ordered vault objects
    """
    sorted_supervisees_by_id = sorted(supervisees, key=lambda vault: vault.account_id)
    sorted_supervisees_by_age_then_id = sorted(
        sorted_supervisees_by_id, key=lambda vault: vault.get_account_creation_date()
    )

    return sorted_supervisees_by_age_then_id


def create_supervisor_event_type_schedule_from_datetime(
    schedule_datetime: datetime, one_off: bool = True
) -> EventTypeSchedule:
    """
    Creates a supervisor contract EventTypeSchedule from a datetime object.

    :param schedule_datetime: datetime, object to be formatted
    :param one_off: if true, the `year` key is included in the dictionary, making this a one-off
    schedule. This is only suitable if the schedule will only be updated before completion, or
    during processing of its own job(s). Otherwise, set to False so that the schedule does not
    complete and can be updated
    :return: EventTypeSchedule representation of datetime
    """
    if one_off:
        return EventTypeSchedule(
            day=str(schedule_datetime.day),
            hour=str(schedule_datetime.hour),
            minute=str(schedule_datetime.minute),
            second=str(schedule_datetime.second),
            month=str(schedule_datetime.month),
            year=str(schedule_datetime.year),
        )
    else:
        return EventTypeSchedule(
            day=str(schedule_datetime.day),
            hour=str(schedule_datetime.hour),
            minute=str(schedule_datetime.minute),
            second=str(schedule_datetime.second),
            month=str(schedule_datetime.month),
        )


def create_supervisor_event_type_schedule_from_schedule_dict(
    schedule_dict: dict,
) -> EventTypeSchedule:
    """
    Creates a supervisor contract EventTypeSchedule from a schedule dictionary.

    :param schedule_datetime: datetime, object to be formatted
    :return: Supervisor EventTypeSchedule representation of the schedule
    """
    return EventTypeSchedule(
        day=schedule_dict.get("day", None),
        day_of_week=schedule_dict.get("day_of_week", None),
        hour=schedule_dict.get("hour", None),
        minute=schedule_dict.get("minute", None),
        second=schedule_dict.get("second", None),
        month=schedule_dict.get("month", None),
        year=schedule_dict.get("year", None),
    )


def sum_balances_across_supervisees(
    supervisees: list[Vault],
    denomination: str,
    addresses: list[str],
    effective_date: Optional[datetime] = None,
    observation_fetcher_id: Optional[str] = None,
    rounding_precision: int = 2,
) -> Decimal:
    """
    Sums the net balance values for the addresses across multiple vault objects,
    rounding the balance sum at a per-vault level. Default asset and phase are used.
    :param supervisees: the vault objects to get balances timeseries/observations from
    :param denomination: the denomination of the balances
    :param addresses: the addresses of the balances
    :param effective_date: the datetime as-of which to get the balances. If not specified
    latest is used. Not used if observation_fetcher_id is specified.
    :param observation_fetcher_id: the fetcher id to use to get the balances. If specified
    the effective_date is unused as the observation is already for a specific datetime
    :param rounding_precision: the precision to which each balance is individually rounded
    :return: the sum of balances across the specified supervisees
    """

    return Decimal(
        sum(
            utils.round_decimal(
                utils.sum_balances(
                    vault=supervisee,
                    addresses=addresses,
                    timestamp=effective_date,
                    denomination=denomination,
                    fetcher_id=observation_fetcher_id,
                ),
                rounding_precision,
            )
            for supervisee in supervisees
        )
    )


def sum_available_balances_across_supervisees(
    supervisees: list[Vault],
    denomination: str,
    effective_date: Optional[datetime] = None,
    observation_fetcher_id: Optional[str] = None,
    rounding_precision: int = 2,
) -> Decimal:
    """
    Sums the net balance values for the committed and pending outgoing phases
    across multiple vault objects, rounding the balance sum at a per-vault level.
    Effective_date and observation_feature_id are both being offered here because optimised
    data fetching isn't supported in all supervisor hooks yet, in the future only
    observation_feature_id's will be supported.
    :param supervisees: the vault objects to get balances timeseries/observations from
    :param denomination: the denomination of the balances
    :param effective_date: the datetime as-of which to get the balances. If not specified
    latest is used. Not used if observation_fetcher_id is specified.
    :param observation_fetcher_id: the fetcher id to use to get the balances. If specified
    the effective_date is unused as the observation is already for a specific datetime
    :param rounding_precision: the precision to which each balance is individually rounded
    :return: the sum of balances across the specified supervisees
    """

    if observation_fetcher_id:
        return Decimal(
            sum(
                utils.round_decimal(
                    utils.get_available_balance(
                        supervisee.get_balances_observation(
                            fetcher_id=observation_fetcher_id
                        ).balances,
                        denomination,
                    ),
                    rounding_precision,
                )
                for supervisee in supervisees
            )
        )
    else:
        return Decimal(
            sum(
                utils.round_decimal(
                    utils.get_available_balance(
                        (
                            supervisee.get_balance_timeseries().latest()
                            if effective_date is None
                            else supervisee.get_balance_timeseries().at(timestamp=effective_date)
                        ),
                        denomination,
                    ),
                    rounding_precision,
                )
                for supervisee in supervisees
            )
        )
