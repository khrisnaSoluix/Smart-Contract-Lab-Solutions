from typing import Optional, NamedTuple
from dateutil.relativedelta import relativedelta as timedelta
from datetime import datetime
from decimal import ROUND_DOWN, Decimal

# inception lib
from inception_sdk.vault.contracts.types_extension import (
    NumberShape,
    Level,
    Parameter,
    EventType,
    UnionShape,
    UnionItemValue,
    UnionItem,
    AccountIdShape,
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    INTERNAL_CONTRA,
    UpdatePermission,
    PostingInstruction,
    Vault,
)
import library.features.common.utils as utils

DEFAULT_PROFIT_APPLICATION_FREQUENCY = "monthly"
PROFIT_APPLICATION_FREQUENCY_MAP = {"monthly": 1, "quarterly": 3, "annually": 12}

ACCRUAL_EVENT = "ACCRUE_PROFIT"
ACCRUAL_APPLICATION_EVENT = "APPLY_ACCRUED_PROFIT"

ACCRUED_PROFIT_PAYABLE_ADDRESS = "ACCRUED_PROFIT_PAYABLE"

parameters = [
    Parameter(
        name="profit_application_day",
        level=Level.INSTANCE,
        description="The day of the month on which profit is applied. If day does not exist"
        " in application month, applies on last day of month.",
        display_name="Profit application day",
        shape=NumberShape(min_value=1, max_value=31, step=1),
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=1,
    ),
    Parameter(
        name="profit_accrual_hour",
        level=Level.TEMPLATE,
        description="The hour of the day at which profit is accrued.",
        display_name="Profit accrual hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=1,
    ),
    Parameter(
        name="profit_accrual_minute",
        level=Level.TEMPLATE,
        description="The minute of the hour at which profit is accrued.",
        display_name="Profit accrual minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name="profit_accrual_second",
        level=Level.TEMPLATE,
        description="The second of the minute at which profit is accrued.",
        display_name="Profit accrual second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name="profit_application_hour",
        level=Level.TEMPLATE,
        description="The hour of the day at which profit is applied.",
        display_name="Profit application hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=1,
    ),
    Parameter(
        name="profit_application_minute",
        level=Level.TEMPLATE,
        description="The minute of the hour at which profit is applied.",
        display_name="Profit application minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=5,
    ),
    Parameter(
        name="profit_application_second",
        level=Level.TEMPLATE,
        description="The second of the minute at which profit is applied.",
        display_name="Profit application second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name="profit_application_frequency",
        level=Level.TEMPLATE,
        description="The frequency at which deposit profit is applied to deposits in the main"
        ' denomination. Valid values are "monthly", "quarterly", "annually".',
        display_name="Profit application frequency",
        shape=UnionShape(
            UnionItem(key="monthly", display_name="Monthly"),
            UnionItem(key="quarterly", display_name="Quarterly"),
            UnionItem(key="annually", display_name="Annually"),
        ),
        default_value=UnionItemValue(key="monthly"),
    ),
    Parameter(
        name="accrued_profit_payable_account",
        level=Level.TEMPLATE,
        description="Internal account for accrued profit payable balance.",
        display_name="Accrued profit payable account",
        shape=AccountIdShape,
        default_value="ACCRUED_PROFIT_PAYABLE",
    ),
    Parameter(
        name="profit_paid_account",
        level=Level.TEMPLATE,
        description="Internal account for profit paid balance.",
        display_name="Profit paid account",
        shape=AccountIdShape,
        default_value="PROFIT_PAID",
    ),
]


def get_event_types(product_name):
    accrual_tags = [f"{product_name}_ACCRUE_PROFIT_AST"]
    apply_tag = [f"{product_name}_APPLY_ACCRUED_PROFIT_AST"]
    return [
        EventType(
            name=ACCRUAL_EVENT,
            scheduler_tag_ids=accrual_tags,
        ),
        EventType(
            name=ACCRUAL_APPLICATION_EVENT,
            scheduler_tag_ids=apply_tag,
        ),
    ]


def get_execution_schedules(vault: Vault) -> list[tuple[str, dict[str, str]]]:
    account_creation_date = vault.get_account_creation_date()
    # Every day at time set by template parameters
    accrue_profit_schedule = utils.get_daily_schedule(vault, "profit_accrual", ACCRUAL_EVENT)
    apply_accrued_profit_schedule = get_next_apply_accrued_profit_schedule(
        vault, account_creation_date
    )
    return [
        accrue_profit_schedule,
        apply_accrued_profit_schedule,
    ]


def get_accrual_posting_instructions(
    vault: Vault,
    effective_date: datetime,
    denomination: str,
    accrual_formula: NamedTuple,
    capital_address: str = DEFAULT_ADDRESS,
) -> list[PostingInstruction]:
    posting_instructions = []
    accrued_profit_payable_account = utils.get_parameter(vault, "accrued_profit_payable_account")
    profit_paid_account = utils.get_parameter(vault, "profit_paid_account")

    accrual_capital = _get_accrual_capital(vault, effective_date, denomination, capital_address)

    amount_to_accrue = accrual_formula.calculate(
        vault, accrual_capital, effective_date=effective_date
    )

    if amount_to_accrue > 0:

        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=amount_to_accrue,
                denomination=denomination,
                client_transaction_id="INTERNAL_POSTING_ACCRUE_PROFIT"
                f"_{vault.get_hook_execution_id()}_INTERNAL",
                from_account_id=profit_paid_account,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=accrued_profit_payable_account,
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": f"Daily profit accrued on balance of {accrual_capital}",
                    "event": "ACCRUE_PROFIT",
                    "account_type": "MURABAHAH",
                },
            )
        )
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=amount_to_accrue,
                denomination=denomination,
                client_transaction_id="INTERNAL_POSTING_ACCRUE_PROFIT"
                f"_{vault.get_hook_execution_id()}_CUSTOMER",
                from_account_id=vault.account_id,
                from_account_address=INTERNAL_CONTRA,
                to_account_id=vault.account_id,
                to_account_address=ACCRUED_PROFIT_PAYABLE_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": f"Daily profit accrued on balance of {accrual_capital}",
                    "event": ACCRUAL_EVENT,
                    "account_type": "MURABAHAH",
                },
            )
        )

    return posting_instructions


def get_apply_accrual_posting_instructions(
    vault: Vault, effective_date: datetime, denomination: str
) -> list[PostingInstruction]:
    accrued_profit_payable_account = utils.get_parameter(vault, "accrued_profit_payable_account")

    accrued_profit_raw_payable = utils.get_balance_sum(
        vault, [ACCRUED_PROFIT_PAYABLE_ADDRESS], denomination=denomination, timestamp=effective_date
    )

    accrued_profit_rounded = utils.round_decimal(
        accrued_profit_raw_payable, decimal_places=2, rounding=ROUND_DOWN
    )

    posting_instructions = []
    if accrued_profit_rounded > 0:
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=accrued_profit_rounded,
                denomination=denomination,
                from_account_id=accrued_profit_payable_account,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=vault.account_id,
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id=f"INTERNAL_POSTING_APPLY_ACCRUED_PROFIT"
                f"_{vault.get_hook_execution_id()}_{denomination}_INTERNAL",
                instruction_details={
                    "description": "Profit Applied",
                    "event": ACCRUAL_APPLICATION_EVENT,
                    "account_type": "MURABAHAH",
                },
            )
        )
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=abs(accrued_profit_rounded),
                denomination=denomination,
                from_account_id=vault.account_id,
                from_account_address=ACCRUED_PROFIT_PAYABLE_ADDRESS,
                to_account_id=vault.account_id,
                to_account_address=INTERNAL_CONTRA,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id=f"INTERNAL_POSTING_APPLY_ACCRUED_PROFIT"
                f"_{vault.get_hook_execution_id()}_{denomination}_CUSTOMER",
                instruction_details={
                    "description": "Profit Applied",
                    "event": ACCRUAL_APPLICATION_EVENT,
                    "account_type": "MURABAHAH",
                },
            )
        )

    remainder = accrued_profit_raw_payable - accrued_profit_rounded
    instruction_details = {
        "description": "Reversing accrued profit after application",
        "event": ACCRUAL_APPLICATION_EVENT,
        "account_type": "MURABAHAH",
    }
    posting_instructions.extend(
        get_residual_cleanup_posting_instructions(
            vault, denomination, instruction_details, remainder=remainder
        )
    )

    return posting_instructions


def get_residual_cleanup_posting_instructions(
    vault: Vault,
    denomination: str,
    instruction_details: dict[str, str],
    remainder: Optional[Decimal] = None,
) -> list[PostingInstruction]:
    """
    Creates posting instructions to net off the account accrued profit address balance to zero and
    nets off any residual profit on the relevant internal account. After applying accrued profit or
    when closing the account. The remaining profit on the account address and the the type of
    profit determine the posting directions and what customer account address to use.

    If no remainder is given, defaults to cleaning out ACCRUED_PROFIT_PAYABLE_ADDRESS balance
    """
    posting_instructions = []

    accrued_profit_payable_account = utils.get_parameter(vault, "accrued_profit_payable_account")
    profit_paid_account = utils.get_parameter(vault, "profit_paid_account")

    if remainder is None:
        remainder = utils.get_balance_sum(vault, [ACCRUED_PROFIT_PAYABLE_ADDRESS])

    if remainder < 0:
        internal_from_account_id = profit_paid_account
        internal_to_account_id = accrued_profit_payable_account
        cust_from_address = INTERNAL_CONTRA
        cust_to_address = ACCRUED_PROFIT_PAYABLE_ADDRESS
    else:
        internal_from_account_id = accrued_profit_payable_account
        internal_to_account_id = profit_paid_account
        cust_from_address = ACCRUED_PROFIT_PAYABLE_ADDRESS
        cust_to_address = INTERNAL_CONTRA

    if remainder != 0:
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=abs(remainder),
                denomination=denomination,
                from_account_id=internal_from_account_id,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=internal_to_account_id,
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id=f"INTERNAL_POSTING_REVERSE_"
                f"RESIDUAL_PROFIT_{vault.get_hook_execution_id()}"
                f"_{denomination}_INTERNAL",
                instruction_details=instruction_details,
            )
        )
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=abs(remainder),
                denomination=denomination,
                from_account_id=vault.account_id,
                from_account_address=cust_from_address,
                to_account_id=vault.account_id,
                to_account_address=cust_to_address,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id=f"INTERNAL_POSTING_REVERSE_"
                f"RESIDUAL_PROFIT_{vault.get_hook_execution_id()}"
                f"_{denomination}_CUSTOMER",
                instruction_details=instruction_details,
            )
        )
    return posting_instructions


def _get_accrual_capital(
    vault: Vault,
    effective_date: datetime,
    denomination: str,
    capital_address: str = DEFAULT_ADDRESS,
) -> Decimal:
    profit_accrual_hour = utils.get_parameter(vault, "profit_accrual_hour")
    profit_accrual_minute = utils.get_parameter(vault, "profit_accrual_minute")
    profit_accrual_second = utils.get_parameter(vault, "profit_accrual_second")

    # balances need to be queried for the previous day so subtract hour, minute and second
    # (as well as 1 microsecond to take it into the last moment of the previous day)
    # note, there is no daylight saving in this timezone
    balance_date = effective_date - timedelta(
        hours=int(profit_accrual_hour),
        minutes=int(profit_accrual_minute),
        seconds=int(profit_accrual_second),
        microseconds=1,
    )

    return utils.get_balance_sum(
        vault, [capital_address], denomination=denomination, timestamp=balance_date
    )


def get_next_apply_accrued_profit_schedule(
    vault: Vault, effective_date: datetime
) -> utils.EventTuple:
    """
    Sets up dictionary for the next profit application day,
    """

    intended_profit_application_day = utils.get_parameter(vault, "profit_application_day")
    profit_application_frequency = utils.get_parameter(
        vault, "profit_application_frequency", union=True
    )
    calendar_events = vault.get_calendar_events(calendar_ids=["&{PUBLIC_HOLIDAYS}"])

    return utils.get_schedule(
        vault,
        param_prefix="profit_application",
        event_type=ACCRUAL_APPLICATION_EVENT,
        localised_effective_date=vault.localize_datetime(dt=effective_date),
        schedule_frequency=profit_application_frequency,
        schedule_day_of_month=intended_profit_application_day,
        calendar_events=calendar_events,
    )
