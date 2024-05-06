from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, NamedTuple

# inception lib
from inception_sdk.vault.contracts.types_extension import (
    AccountIdShape,
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    Level,
    Parameter,
    PostingInstruction,
    NumberKind,
    NumberShape,
    UnionItem,
    UnionShape,
    UnionItemValue,
    Vault,
)
import library.features.common.utils as utils

# This feature is coupled to interest accrual as it uses the same schedule. For performance
# reasons we do not recommend using separate daily schedules
# It is also coupled to fixed rate as other options (variable) aren't required for penalty interest
import library.features.lending.interest_accrual as interest_accrual
import library.features.lending.interest.fixed_rate as fixed_rate

rate_parameters = [
    # Template parameters
    Parameter(
        name="penalty_interest_rate",
        shape=NumberShape(kind=NumberKind.PERCENTAGE, min_value=0, max_value=1, step=0.0001),
        level=Level.TEMPLATE,
        description="The annual interest rate to be applied to overdues.",
        display_name="Penalty interest rate (p.a.)",
        default_value=Decimal("0.1"),
    ),
    Parameter(
        name="penalty_includes_base_rate",
        level=Level.TEMPLATE,
        description="If true the penalty interest rate is added to the base interest rate.",
        display_name="Penalty includes base rate",
        shape=UnionShape(
            UnionItem(key="True", display_name="True"),
            UnionItem(key="False", display_name="False"),
        ),
        default_value=UnionItemValue(key="True"),
    ),
]
account_parameters = [
    # Template parameters
    Parameter(
        name="penalty_interest_income_account",
        level=Level.TEMPLATE,
        description="Internal account for penalty interest income.",
        display_name="Penalty interest income account",
        shape=AccountIdShape,
        default_value="PENALTY_INTEREST_INCOME",
    ),
]

all_parameters = [*account_parameters, *rate_parameters]

get_accrual_capital = interest_accrual.get_accrual_capital
ACCRUAL_EVENT = interest_accrual.ACCRUAL_EVENT


def calculate_daily_accrual_amount(
    vault: Vault,
    accrual_capital: Decimal,
    effective_date: datetime,
    interest_feature: NamedTuple = fixed_rate.feature,
) -> Decimal:
    daily_rate = get_daily_interest_rate(vault, effective_date, interest_feature)
    # Using 2dp here as penalties are immediately repayable, before due amount calculation and
    # must therefore be kept at same precision as payments
    amount_to_accrue = utils.round_decimal(abs(accrual_capital * daily_rate), decimal_places=2)
    return amount_to_accrue


def get_daily_interest_rate(
    vault: Vault, effective_date: datetime, interest_feature: NamedTuple
) -> Decimal:
    annual_rate = Decimal(utils.get_parameter(vault, "penalty_interest_rate"))
    days_in_year = str(utils.get_parameter(vault, "days_in_year", union=True))
    penalty_interest_rate = utils.yearly_to_daily_rate(
        annual_rate, effective_date.year, days_in_year=days_in_year
    )

    if utils.get_parameter(vault, "penalty_includes_base_rate", union=True).upper() == "TRUE":
        base_rate = interest_feature.get_daily_interest_rate(vault, effective_date)
        penalty_interest_rate += base_rate

    return penalty_interest_rate


def get_accrual_posting_instructions(
    vault: Vault,
    effective_date: datetime,
    denomination: str,
    accrual_formula: Callable[[Any, Decimal, datetime], Decimal],
    accrual_capital: Decimal,
    accrual_address: str,
) -> list[PostingInstruction]:

    """
    Creates the posting instructions to accrue interest on the balances specified by
    the denomination and capital addresses parameters
    :param vault: the vault object to use to for retrieving data and instructing directives
    :param effective_date: the effective date to use for retrieving capital balances to accrue on
    :param denomination: the denomination of the capital balances and the interest accruals
    :param accrual_formula: the formula to determine the accrual amount
    :param accrual_capital: capital to accrue on
    :param accrual_address: balance address for the accrual amount to be debited from
    :return: the accrual posting instructions
    """

    amount_to_accrue = accrual_formula(
        vault,
        accrual_capital,
        effective_date,
    )
    penalty_income_account = utils.get_parameter(vault, "penalty_interest_income_account")
    if amount_to_accrue > 0:
        return vault.make_internal_transfer_instructions(
            amount=amount_to_accrue,
            denomination=denomination,
            client_transaction_id="ACCRUE_PENALTY_INTEREST"
            f"_{vault.get_hook_execution_id()}_{denomination}",
            from_account_id=vault.account_id,
            from_account_address=accrual_address,
            to_account_id=penalty_income_account,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            instruction_details={
                "description": f"Daily penalty interest accrued on balance of {accrual_capital}",
                "event": ACCRUAL_EVENT,
            },
            override_all_restrictions=True,
        )

    return []
