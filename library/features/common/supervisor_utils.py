# standard libs
from decimal import Decimal
from datetime import datetime
from typing import Optional

# common
from inception_sdk.vault.contracts.supervisor.types_extension import (
    EventTypeSchedule,
)

# other
import library.features.common.utils as utils

# TODO: SupervisorVault typehint raises renderer exception
def get_supervisees_for_alias(vault, alias: str) -> list:
    """
    Returns a list of supervisee vault objects for the given alias, ordered by account creation date
    :param vault: vault, supervisor vault object
    :param alias: str, the supervisee alias to filter for
    :return: list, supervisee vault objects for given alias, ordered by account creation date
    """
    return sort_supervisees(
        [
            supervisee
            for supervisee in vault.supervisees.values()
            if supervisee.get_alias() == alias
        ],
    )


def sort_supervisees(supervisees: list) -> list:
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
    schedule_datetime: datetime,
) -> EventTypeSchedule:
    """
    Creates a supervisor contract EventTypeSchedule from a datetime object.

    :param schedule_datetime: datetime, object to be formatted
    :return: EventTypeSchedule representation of datetime
    """
    return EventTypeSchedule(
        day=str(schedule_datetime.day),
        hour=str(schedule_datetime.hour),
        minute=str(schedule_datetime.minute),
        second=str(schedule_datetime.second),
        month=str(schedule_datetime.month),
        year=str(schedule_datetime.year),
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
    supervisees: list,
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

    if observation_fetcher_id:
        return Decimal(
            sum(
                utils.round_decimal(
                    utils.get_balance_observation_sum(
                        supervisee, observation_fetcher_id, addresses, denomination
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
                    utils.get_balance_sum(supervisee, addresses, effective_date, denomination),
                    rounding_precision,
                )
                for supervisee in supervisees
            )
        )
