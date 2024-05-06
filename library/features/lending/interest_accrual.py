from datetime import datetime
from dateutil.relativedelta import relativedelta as timedelta
from decimal import Decimal
from typing import Callable, Any, Optional

# inception lib
from inception_sdk.vault.contracts.types_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    AccountIdShape,
    EventType,
    Level,
    NumberShape,
    Parameter,
    PostingInstruction,
    Vault,
)
import library.features.common.utils as utils


ACCRUAL_EVENT = "ACCRUE_INTEREST"
ACCRUED_INTEREST_RECEIVABLE_ADDRESS = "ACCRUED_INTEREST_RECEIVABLE"
NON_EMI_ACCRUED_INTEREST_RECEIVABLE_ADDRESS = "NON_EMI_ACCRUED_INTEREST_RECEIVABLE"
INTERNAL_CONTRA = "INTERNAL_CONTRA"

schedule_parameters = [
    # Template parameters
    Parameter(
        name="interest_accrual_hour",
        level=Level.TEMPLATE,
        description="The hour of the day at which interest is accrued.",
        display_name="Interest accrual hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=0,
    ),
    Parameter(
        name="interest_accrual_minute",
        level=Level.TEMPLATE,
        description="The minute of the hour at which interest is accrued.",
        display_name="Interest accrual minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name="interest_accrual_second",
        level=Level.TEMPLATE,
        description="The second of the minute at which interest is accrued.",
        display_name="Interest accrual second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=1,
    ),
]

account_parameters = [
    # Internal accounts
    Parameter(
        name="accrued_interest_receivable_account",
        level=Level.TEMPLATE,
        description="Internal account for accrued interest receivable balance.",
        display_name="Accrued interest receivable account",
        shape=AccountIdShape,
        default_value="ACCRUED_INTEREST_RECEIVABLE",
    ),
    Parameter(
        name="interest_received_account",
        level=Level.TEMPLATE,
        description="Internal account for interest received balance.",
        display_name="Interest received account",
        shape=AccountIdShape,
        default_value="INTEREST_RECEIVED",
    ),
]

all_parameters = [
    *account_parameters,
    *schedule_parameters,
]


def get_event_types(product_name: str) -> list[EventType]:
    accrual_tags = [f"{product_name.upper()}_ACCRUE_INTEREST_AST"]
    return [EventType(name=ACCRUAL_EVENT, scheduler_tag_ids=accrual_tags)]


def get_execution_schedules(vault: Vault) -> list[tuple[str, dict[str, str]]]:
    # Every day at time set by template parameters
    return [utils.get_daily_schedule(vault, "interest_accrual", ACCRUAL_EVENT)]


def get_accrual_posting_instructions(
    vault: Vault,
    effective_date: datetime,
    denomination: str,
    next_due_amount_calculation_date: datetime,
    accrual_formula: Callable[[Any, Decimal, datetime], Decimal],
    accrual_capital: Decimal,
    accrual_address: str = ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
    non_emi_accrual_address: str = NON_EMI_ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
) -> list[PostingInstruction]:

    """
    Creates the posting instructions to accrue interest on the balances specified by
    the denomination and capital addresses parameters
    :param vault: the vault object to use to for retrieving data and instructing directives
    :param effective_date: the effective date to use for retrieving capital balances to accrue on
    :param denomination: the denomination of the capital balances and the interest accruals
    :param next_due_amount_calculation_date: the next date that the due amount calculation will
    run on. Used to determine whether the interest to accrue is part of EMI or not
    :param accrual_formula: the formula to determine the accrual amount
    :param accrual_capital: capital to accrue on
    :param accrual_address: balance address for the accrual amount to be debited from
    :param non_emi_accrual_address: balance address for the accrual to be debited from if the
    accrual is not included in the EMI
    :return: the accrual posting instructions
    """

    amount_to_accrue = accrual_formula(vault, accrual_capital, effective_date)

    # Interest is not included in EMI if we are accruing earlier than 1 month before next due
    # amount calculation. We need to know this non-emi amount amount (e.g. when determining due
    # principal amounts. Storing it separately avoids excessive fetching requirements
    is_extra_interest = effective_date < next_due_amount_calculation_date - timedelta(months=1)
    final_accrual_address = non_emi_accrual_address if is_extra_interest else accrual_address

    return accrual_posting_instructions(
        vault,
        denomination,
        amount_to_accrue,
        final_accrual_address,
        instruction_details={
            "description": f"Daily interest accrued on balance of {accrual_capital}",
            "event": ACCRUAL_EVENT,
        },
    )


# TODO: rename the interfaces to remove 'posting_instructions' from methods that do more than this
# (e.g. get_accrual_posting_instructions is really 'accrue interest').
def accrual_posting_instructions(
    vault: Vault,
    denomination: str,
    accrual_amount: Decimal,
    accrual_address: str,
    instruction_details: Optional[dict[str, str]] = None,
) -> list[PostingInstruction]:

    """
    Creates the posting instructions to accrue interest for the specified amount
    :param vault: the vault object to use to for retrieving data and instructing directives
    :param denomination: the denomination of the capital balances and the interest accruals
    :param accrual_amount: the amount to accrue
    :param accrual_address: balance address for the accrual amount to be debited from
    :param instruction_details: optional instruction details for the posting instructions
    :return: the accrual posting instructions
    """

    if accrual_amount > 0:
        return vault.make_internal_transfer_instructions(
            amount=accrual_amount,
            denomination=denomination,
            client_transaction_id="ACCRUE_INTEREST"
            f"_{vault.get_hook_execution_id()}_{denomination}",
            from_account_id=vault.account_id,
            from_account_address=accrual_address,
            to_account_id=vault.account_id,
            to_account_address=INTERNAL_CONTRA,
            asset=DEFAULT_ASSET,
            instruction_details={
                **(instruction_details or {}),
                "event": ACCRUAL_EVENT,
            },
            override_all_restrictions=True,
        )

    return []


def get_accrual_capital(
    vault: Vault,
    effective_date: datetime,
    denomination: str,
    capital_addresses: Optional[list[str]] = None,
) -> Decimal:

    # we check the last possible time capital could accrue, i.e. at 23:59:59.999999 on
    # the day before effective_date
    balance_date = effective_date - timedelta(
        hour=0,
        minute=0,
        second=0,
        microseconds=1,
    )

    capital_addresses = capital_addresses or [DEFAULT_ADDRESS]

    return utils.get_balance_sum(
        vault, capital_addresses, denomination=denomination, timestamp=balance_date
    )


def get_accrued_interest(vault: Vault, at: Optional[datetime] = None) -> Decimal:
    return utils.get_balance_sum(vault, [ACCRUED_INTEREST_RECEIVABLE_ADDRESS], timestamp=at)


def get_additional_interest(vault: Vault, at: Optional[datetime] = None) -> Decimal:
    return utils.get_balance_sum(vault, [NON_EMI_ACCRUED_INTEREST_RECEIVABLE_ADDRESS], timestamp=at)
