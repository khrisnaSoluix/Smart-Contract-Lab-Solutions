"""
Provides commonly used Contracts API v4 helper methods for use with supervisor contracts
"""
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Callable, Union

# features
import library.features.v4.common.addresses as addresses
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import (
    AccountNotificationDirective,
    BalanceDefaultDict,
    CustomInstruction,
    Posting,
    PostingInstructionsDirective,
    PostPostingHookResult,
    ScheduledEvent,
    ScheduledEventHookResult,
    SupervisorContractEventType,
    SupervisorScheduledEventHookArguments,
    Tside,
    UpdateAccountEventTypeDirective,
    UpdatePlanEventTypeDirective,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import (
    SuperviseeContractVault,
    SupervisorContractVault,
)

# an event for synchronising schedules in a supervisor from a supervisee schedule
SUPERVISEE_SCHEDULE_SYNC_EVENT = "SUPERVISEE_SCHEDULE_SYNC"


def schedule_sync_event_types(product_name: str) -> list[SupervisorContractEventType]:
    return [
        SupervisorContractEventType(
            name=SUPERVISEE_SCHEDULE_SYNC_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{SUPERVISEE_SCHEDULE_SYNC_EVENT}_AST"],
        ),
    ]


def get_supervisees_for_alias(
    vault: SupervisorContractVault, alias: str
) -> list[SuperviseeContractVault]:
    """
    Returns a list of supervisee vault objects for the given alias, ordered by account creation date
    TODO: (INC-8671) reintroduce num_requested logic from v3

    :param vault: supervisor vault object
    :param alias: the supervisee alias to filter for
    :return: supervisee vault objects for given alias, ordered by account creation date

    """
    return sort_supervisees(
        [
            supervisee
            for supervisee in vault.supervisees.values()
            if supervisee.get_alias() == alias
        ],
    )


def sort_supervisees(supervisees: list[SuperviseeContractVault]) -> list[SuperviseeContractVault]:
    """
    Sorts supervisees first by creation date, and then alphabetically by id if
    numerous supervisees share the same creation date and creates a list of ordered
    vault objects.

    :param supervisees: list of supervisee vault objects
    :return sorted_supervisees: list of ordered vault objects
    """
    sorted_supervisees_by_id = sorted(supervisees, key=lambda vault: vault.account_id)
    sorted_supervisees_by_age_then_id = sorted(
        sorted_supervisees_by_id, key=lambda vault: vault.get_account_creation_datetime()
    )

    return sorted_supervisees_by_age_then_id


def get_balance_default_dicts_for_supervisees(
    supervisees: list[SuperviseeContractVault],
    fetcher_id: str,
) -> list[BalanceDefaultDict]:
    """
    Returns a list of the supervisee balances at the datetime defined in a fetcher
    :param supervisees: the vault objects to get balances observations from
    :param fetcher_id: the id of the fetcher used to get balances observations
    :return: the list of balances of the specified supervisees
    """
    return [
        supervisee.get_balances_observation(fetcher_id=fetcher_id).balances
        for supervisee in supervisees
    ]


def get_balances_default_dicts_from_timeseries(
    supervisees: list[SuperviseeContractVault], effective_datetime: datetime
) -> dict[str, BalanceDefaultDict]:
    """
    Returns supervisee balances at the provided datetime, using balances timeseries.
    This is intended to be used where a fetcher cannot be used (e.g. post posting hook).
    :param supervisees: the vault objects to get balances timeseries from
    :param effective_datetime: the datetime at which the balances should be retrieved
    :return: a dictionary that maps the supervisees account ID to the retrieved balances
    """
    return {
        supervisee.account_id: utils.get_balance_default_dict_from_mapping(
            mapping=supervisee.get_balances_timeseries(), effective_datetime=effective_datetime
        )
        for supervisee in supervisees
    }


def sum_balances_across_supervisees(
    balances: list[BalanceDefaultDict],
    denomination: str,
    addresses: list[str],
    rounding_precision: int = 2,
) -> Decimal:
    """
    Sums the net balance values for the addresses across multiple vault objects,
    rounding the balance sum at a per-vault level. Default asset and phase are used.
    :param balances: the list of balances to sum
    :param denomination: the denomination of the balances
    :param addresses: the addresses of the balances
    :param rounding_precision: the precision to which each balance is individually rounded
    :return: the sum of balances across the specified supervisees
    """
    return Decimal(
        sum(
            utils.round_decimal(
                utils.sum_balances(
                    balances=balance,
                    addresses=addresses,
                    denomination=denomination,
                ),
                rounding_precision,
            )
            for balance in balances
        )
    )


def get_supervisee_directives_mapping(
    vault: SuperviseeContractVault,
) -> tuple[
    dict[str, list[AccountNotificationDirective]],
    dict[str, list[PostingInstructionsDirective]],
    dict[str, list[UpdateAccountEventTypeDirective]],
]:
    """
    Return the mapping from supervisee account id to list of AccountNotificationDirective,
    PostingInstructionsDirectives and UpdateAccountEventTypeDirective to be returned
    in the supervisor ScheduledEventHookResult and PostPostingHookResult

    :param vault: supervisee vault account
    :return: dictionary mapping of a tuple of vault account id to their respective directive.
    """
    supervisee_hook_results: Union[
        PostPostingHookResult, ScheduledEventHookResult
    ] = vault.get_hook_result()  # type: ignore
    supervisee_notification_directives = supervisee_hook_results.account_notification_directives
    supervisee_notification_directives_dict = (
        {vault.account_id: supervisee_notification_directives}
        if supervisee_notification_directives
        else {}
    )

    supervisee_posting_directives = supervisee_hook_results.posting_instructions_directives
    supervisee_posting_directives_dict = (
        {vault.account_id: supervisee_posting_directives} if supervisee_posting_directives else {}
    )

    supervisee_update_account_event_type_directives = (
        supervisee_hook_results.update_account_event_type_directives
    )
    supervisee_update_account_event_type_directives_dict = (
        {vault.account_id: supervisee_update_account_event_type_directives}
        if supervisee_update_account_event_type_directives
        else {}
    )
    return (
        supervisee_notification_directives_dict,
        supervisee_posting_directives_dict,
        supervisee_update_account_event_type_directives_dict,
    )


def create_aggregate_posting_instructions(
    aggregate_account_id: str,
    posting_instructions_by_supervisee: dict[str, list[CustomInstruction]],
    prefix: str,
    balances: BalanceDefaultDict,
    addresses_to_aggregate: list[str],
    tside: Tside = Tside.ASSET,
    force_override: bool = True,
    rounding_precision: int = 2,
) -> list[CustomInstruction]:
    """
    Used for supervisor contracts to aggregate multiple posting instructions that arise
    from supervisee accounts. This util is helpful when you have a "main" supervisee
    account that is responsible for holding aggregate balances (i.e. an account where
    aggregate postings are made).

    Any postings targeting the same balance address name will be aggregated. e.g. If supervisee 1
    and supervisee 2 both have postings to address PRINCIPAL_DUE, the aggregate value of these will
    be calculated into a new posting instruction of length 1 to a balance address:
    <prefix>_<balance_address> (e.g. TOTAL_PRINCIPAL_DUE).

    :param aggregate_account_id: The account id of the vault object where the aggregate postings
    are made (i.e. the "main" account)
    :param posting_instructions_by_supervisee: A mapping of supervisee account id to posting
    instructions to derive the aggregate posting instructions from
    :param prefix: The prefix of the aggregated balances
    :param balances: The balances of the account where the aggregate postings are made (i.e. the
    "main" account). Typically these are the latest balances for the account, but in theory any
    balances can be passed in.
    :param addresses_to_aggregate: A list of addresses to get aggregate postings for
    :param tside: The Tside of the account
    :param force_override: boolean to pass into instruction details to force override hooks
    :param rounding_precision: The rounding precision to correct for
    :return: The aggregated custom instructions
    """

    aggregate_balances = BalanceDefaultDict()
    for supervisee_account_id, posting_instructions in posting_instructions_by_supervisee.items():
        for posting_instruction in posting_instructions:
            aggregate_balances += posting_instruction.balances(
                account_id=supervisee_account_id, tside=tside
            )

    filtered_aggregate_balances = filter_aggregate_balances(
        aggregate_balances=aggregate_balances,
        balances=balances,
        addresses_to_aggregate=addresses_to_aggregate,
        rounding_precision=rounding_precision,
    )

    # create postings from the filtered aggregate balances dict
    # two sets of postings (a credit and a debit) are created for each item in the dict
    aggregate_postings: list[Posting] = []
    for balance_coordinate, balance in filtered_aggregate_balances.items():
        amount: Decimal = balance.net
        prefixed_address = f"{prefix}_{balance_coordinate.account_address}"
        debit_address = (
            prefixed_address
            if (tside == Tside.ASSET and amount > Decimal("0"))
            or (tside == Tside.LIABILITY and amount < Decimal("0"))
            else addresses.INTERNAL_CONTRA
        )
        credit_address = (
            prefixed_address
            if (tside == Tside.ASSET and amount < Decimal("0"))
            or (tside == Tside.LIABILITY and amount > Decimal("0"))
            else addresses.INTERNAL_CONTRA
        )

        aggregate_postings += utils.create_postings(
            amount=abs(amount),
            debit_account=aggregate_account_id,
            credit_account=aggregate_account_id,
            debit_address=debit_address,
            credit_address=credit_address,
            denomination=balance_coordinate.denomination,
            asset=balance_coordinate.asset,
        )

    aggregate_posting_instructions: list[CustomInstruction] = []
    if aggregate_postings:
        aggregate_posting_instructions.append(
            CustomInstruction(
                postings=aggregate_postings,
                instruction_details={"force_override": str(force_override).lower()},
            )
        )

    return aggregate_posting_instructions


def filter_aggregate_balances(
    aggregate_balances: BalanceDefaultDict,
    balances: BalanceDefaultDict,
    addresses_to_aggregate: list[str],
    rounding_precision: int = 2,
) -> BalanceDefaultDict:
    """
    Removes aggregate balances that would cause discrepancies between the supervisor
    and the supervisee(s) due to rounding errors.
    Only aggregates given addresses to avoid unnecessary aggregations (e.g. INTERNAL_CONTRA)

    For instance, assume the rounding precision is 2. If account 1 has a balance A with a current
    value of 0.123 and the aggregate amount is 0.001, no aggregate posting needs to be created as
    the rounded absolute amount is unchanged (round(0.123, 2) == round(0.124, 2)). If account 1 has
    a balance A with a current value of 0.123 and there is a posting to increase this by 0.002,
    an aggregate posting is needed as the rounded absolute amount has changed from 0.12 to 0.13.

    Normally this filtering only needs to be applied to the accrued interest balance address,
    but we simply check all addresses being aggregated to guard against this edge case.

    This util is mainly for use in the create_aggregate_posting_instructions util, but in theory
    it could be used independently.

    :param aggregate_balances: The aggregate balances to filter
    :param balances: The balances of the account where the aggregate postings are made (i.e. the
    "main" account). Typically these are the latest balances for the account, but in theory any
    balances can be passed in.
    :param addresses_to_aggregate: A list of addresses to aggregate balances for
    :param rounding_precision: The rounding precision to correct for
    :return: A filtered dict of aggregated balances
    """
    filtered_aggregate_balance_mapping = aggregate_balances.copy()
    new_balance_mapping = aggregate_balances + balances

    for balance_coordinate in aggregate_balances:
        if balance_coordinate.account_address in addresses_to_aggregate:
            current_amount = balances[balance_coordinate].net
            new_amount = new_balance_mapping[balance_coordinate].net

            if utils.round_decimal(
                amount=new_amount, decimal_places=rounding_precision
            ) == utils.round_decimal(amount=current_amount, decimal_places=rounding_precision):
                del filtered_aggregate_balance_mapping[balance_coordinate]
        else:
            del filtered_aggregate_balance_mapping[balance_coordinate]

    return filtered_aggregate_balance_mapping


def supervisee_schedule_sync_scheduled_event(
    vault: SupervisorContractVault,
    delay_seconds: int = 30,
) -> dict[str, ScheduledEvent]:
    """
    Return a one-off event for synchronising schedules in a supervisor from a supervisee
    schedule, to be run after plan opening date based on the delay seconds.
    The delay seconds needs to allow for plan activation to complete after opening, as well as
    adequate time for supervisee accounts to be added to the plan.
    """
    plan_opening_datetime = vault.get_plan_opening_datetime()
    first_schedule_date = plan_opening_datetime + relativedelta(seconds=delay_seconds)
    return {
        SUPERVISEE_SCHEDULE_SYNC_EVENT: ScheduledEvent(
            start_datetime=plan_opening_datetime,
            expression=utils.one_off_schedule_expression(first_schedule_date),
        )
    }


def get_supervisee_schedule_sync_updates(
    vault: SupervisorContractVault,
    supervisee_alias: str,
    hook_arguments: SupervisorScheduledEventHookArguments,
    schedule_updates_when_supervisees: Callable[
        [SuperviseeContractVault, SupervisorScheduledEventHookArguments],
        list[UpdatePlanEventTypeDirective],
    ],
    delay_seconds: int = 60,
) -> list[UpdatePlanEventTypeDirective]:
    """
    Get schedule updates needed when synchronising schedules with supervisee schedules based on
    their parameters. If the SUPERVISEE_SCHEDULE_SYNC_EVENT runs on a plan with no associated
    supervisee accounts we reschedule to run this event again after the delay seconds have elapsed.

    :param vault: supervisor vault object
    :param supervisee_alias: the supervisee product alias that must be associated to the plan
    :param hook_arguments: the scheduled event's hook arguments
    :param schedule_updates_when_supervisees: a function to get the required schedule updates, given
    the Vault object of the supervisee
    :param delay_seconds: the number of seconds to delay before rerunning the supervisee schedule
    sync event
    :return: the required schedule updates
    """
    supervisee_vaults = get_supervisees_for_alias(vault=vault, alias=supervisee_alias)
    if supervisee_vaults:
        return schedule_updates_when_supervisees(supervisee_vaults[0], hook_arguments)
    else:
        return [
            UpdatePlanEventTypeDirective(
                event_type=SUPERVISEE_SCHEDULE_SYNC_EVENT,
                expression=utils.one_off_schedule_expression(
                    schedule_datetime=hook_arguments.effective_datetime
                    + relativedelta(seconds=delay_seconds)
                ),
            )
        ]
