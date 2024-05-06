# standard libs
from datetime import datetime
from decimal import Decimal
from typing import Union

# features
import library.features.v4.common.fees as fees
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.lending.lending_addresses as lending_addresses

# contracts api
from contracts_api import (
    AccountIdShape,
    CustomInstruction,
    NumberShape,
    Parameter,
    ParameterLevel,
    ScheduledEvent,
    ScheduledEventHookArguments,
    SmartContractEventType,
    SupervisorScheduledEventHookArguments,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

CHECK_LATE_REPAYMENT_EVENT = "CHECK_LATE_REPAYMENT"
CHECK_LATE_REPAYMENT_PREFIX = "check_late_repayment"

PARAM_CHECK_LATE_REPAYMENT_CHECK_HOUR = f"{CHECK_LATE_REPAYMENT_PREFIX}_hour"
PARAM_CHECK_LATE_REPAYMENT_CHECK_MINUTE = f"{CHECK_LATE_REPAYMENT_PREFIX}_minute"
PARAM_CHECK_LATE_REPAYMENT_CHECK_SECOND = f"{CHECK_LATE_REPAYMENT_PREFIX}_second"

PARAM_LATE_REPAYMENT_FEE = "late_repayment_fee"
PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT = "late_repayment_fee_income_account"
PARAM_DENOMINATION = "denomination"

fee_parameters = [
    Parameter(
        name=PARAM_LATE_REPAYMENT_FEE,
        shape=NumberShape(min_value=Decimal("0")),
        level=ParameterLevel.TEMPLATE,
        description="Fee to apply due to late repayment.",
        display_name="Late Repayment Fee",
        default_value=Decimal("25"),
    ),
    Parameter(
        name=PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for late repayment fee income balance.",
        display_name="Late Repayment Fee Income Account",
        shape=AccountIdShape(),
        default_value="LATE_REPAYMENT_FEE_INCOME",
    ),
]

schedule_parameters = [
    Parameter(
        name=PARAM_CHECK_LATE_REPAYMENT_CHECK_HOUR,
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which late repayment is checked.",
        display_name="Check Late Repayment Hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_CHECK_LATE_REPAYMENT_CHECK_MINUTE,
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which late repayment is checked.",
        display_name="Check Late Repayment Minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_CHECK_LATE_REPAYMENT_CHECK_SECOND,
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which late repayment is checked.",
        display_name="Check Late Repayment Second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
]


def get_late_repayment_fee_parameter(vault: SmartContractVault) -> Decimal:
    return Decimal(utils.get_parameter(vault=vault, name=PARAM_LATE_REPAYMENT_FEE))


def event_types(product_name: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=CHECK_LATE_REPAYMENT_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{CHECK_LATE_REPAYMENT_EVENT}_AST"],
        )
    ]


def scheduled_events(
    vault: SmartContractVault, start_datetime: datetime, skip: bool = False
) -> dict[str, ScheduledEvent]:
    """
    Create a check late repayment schedule, starting at the specified date, and using the
    `check_late_repayment_<>` schedule time parameters. This is a monthly schedule starting on the
    specified start_datetime.
    :param vault: the Vault object
    :param start_datetime: the date on which the schedule will initially run, ignores the time
    component
    :param skip: if True, schedule will be skipped indefinitely until this field is updated,
    defaults to False
    :return: a dictionary containing the check late repayment schedule
    """
    return {
        CHECK_LATE_REPAYMENT_EVENT: ScheduledEvent(
            start_datetime=start_datetime.replace(hour=0, minute=0, second=0),
            expression=utils.get_schedule_expression_from_parameters(
                vault=vault,
                parameter_prefix=CHECK_LATE_REPAYMENT_PREFIX,
                day=start_datetime.day,
            ),
            skip=skip,
        )
    }


def get_total_overdue_amount(
    vault: SmartContractVault,
    precision: int = 2,
) -> Decimal:
    """
    Sums the balances across all overdue addresses
    :param vault: the vault object to get the balances
    :param precision: the number of decimal places to round to
    :return: due balance in Decimal
    """
    denomination: str = utils.get_parameter(vault=vault, name=PARAM_DENOMINATION)
    balances = vault.get_balances_observation(
        fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    return utils.sum_balances(
        balances=balances,
        addresses=lending_addresses.OVERDUE_ADDRESSES,
        denomination=denomination,
        decimal_places=precision,
    )


def schedule_logic(
    vault: SmartContractVault,
    hook_arguments: Union[ScheduledEventHookArguments, SupervisorScheduledEventHookArguments],
    denomination: str,
    account_type: str = "",
    check_total_overdue_amount: bool = True,
) -> list[CustomInstruction]:
    """
    Create postings to charge the late repayment fee if there is a late repayment fee configured,
    And: There is an outstanding overdue amount
    Or: The check on the overdue amount is skipped (check_total_overdue_amount set to False).
    :param vault: the vault object for the account to check late repayment
    :param hook_arguments: the hook arguments as received from the contract
    :param denomination: the denomination as used in vault
    :param account_type: the account type as to be noted in custom instruction detail
    :param check_total_overdue_amount: whether to check the total overdue amount is gt zero.
    If True (default) check total overdue amount is gt zero, and if it isn't then do not charge a
    late repayment fee.
    If False, skip the check on total overdue amount and go ahead to charge the late repayment fee
    :return: list of the late repayment fee custom instruction
    """
    fee_amount: Decimal = utils.get_parameter(vault, name=PARAM_LATE_REPAYMENT_FEE)
    late_repayment_fee_income_account: str = utils.get_parameter(
        vault, name=PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT
    )
    if (check_total_overdue_amount and get_total_overdue_amount(vault) <= 0) or not fee_amount:
        return []

    return fees.fee_custom_instruction(
        customer_account_id=vault.account_id,
        denomination=denomination,
        amount=fee_amount,
        internal_account=late_repayment_fee_income_account,
        customer_account_address=lending_addresses.PENALTIES,
        instruction_details=utils.standard_instruction_details(
            description="Charge late payment",
            event_type=hook_arguments.event_type,
            account_type=account_type,
        ),
    )
