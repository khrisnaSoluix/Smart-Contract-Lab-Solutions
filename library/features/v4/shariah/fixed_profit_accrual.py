# standard libs
from datetime import datetime
from decimal import Decimal
from json import dumps
from typing import Optional
from zoneinfo import ZoneInfo
from dateutil.relativedelta import relativedelta

# features
import library.features.v4.common.accruals as accruals
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.deposit.deposit_maturity_mdh as deposit_maturity_mdh
import library.features.v4.shariah.profit_application as profit_application
import library.features.v4.shariah.shariah_interfaces as shariah_interfaces

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    AccountIdShape,
    BalanceDefaultDict,
    CustomInstruction,
    NumberShape,
    Parameter,
    ParameterLevel,
    ScheduledEvent,
    SmartContractEventType,
    StringShape,
    UnionItem,
    UnionItemValue,
    UnionShape,
    ParameterUpdatePermission,
    DateShape,
    OptionalShape,
    OptionalValue,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Constants
ACCRUAL_EVENT = "ACCRUE_PROFIT"
REVERSAL_ACCRUAL_EVENT = "REVERSAL_ACCRUE_PROFIT"
ACCRUED_PROFIT_PAYABLE = "ACCRUED_PROFIT_PAYABLE"

PROFIT_ACCRUAL_PREFIX = "profit_accrual"
PARAM_ACCRUAL_PRECISION = "accrual_precision"
PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT = "accrued_profit_payable_account"
PARAM_DAYS_IN_YEAR = "days_in_year"
PARAM_PENALTY_DAYS = "penalty_days"
PARAM_PROFIT_ACCRUAL_HOUR = f"{PROFIT_ACCRUAL_PREFIX}_hour"
PARAM_PROFIT_ACCRUAL_MINUTE = f"{PROFIT_ACCRUAL_PREFIX}_minute"
PARAM_PROFIT_ACCRUAL_SECOND = f"{PROFIT_ACCRUAL_PREFIX}_second"

PARAM_EARLY_WITHDRAWAL_GROSS_DISTRIBUTION_RATE = "early_withdrawal_gross_distribution_rate"

PARAM_NISBAH = "nisbah_rate"

PARAM_EXPECTED_DEPOSIT_DATE = "expected_deposit_date"
PARAM_EXPECTED_DEPOSIT_AMOUNT = "expected_deposit_amount"
# Fetchers
data_fetchers = [fetchers.EOD_FETCHER]

# Global Parameters
PARAM_GROSS_DISTRIBUTION_RATE = "gross_distribution_rate"

# Parameters
validation_parameters = [
    Parameter(
        name= PARAM_EXPECTED_DEPOSIT_DATE,
        level=ParameterLevel.INSTANCE,
        description= "The expected date of deposit",
        display_name= "Expected Date of Deposit",
        shape=OptionalShape(shape=DateShape()),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
        default_value=OptionalValue(datetime.min.replace(tzinfo=ZoneInfo("UTC")))
    ),
    Parameter(
        name= PARAM_EXPECTED_DEPOSIT_AMOUNT,
        level= ParameterLevel.INSTANCE,
        description="The expected amount of deposit",
        display_name="Expected Amount of Deposit",
        shape= NumberShape(),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
        default_value=Decimal('8000000')
    )
]

eq_rate_parameters = [
    Parameter(
        name=PARAM_EARLY_WITHDRAWAL_GROSS_DISTRIBUTION_RATE,
        level=ParameterLevel.INSTANCE,
        description="The GDR of the product for early withdrawal",
        display_name="Early Withdrawal Gross Distribution Rate",
        shape=NumberShape(min_value=0, max_value=1, step=Decimal('0.0001')),
        default_value=Decimal("0.00"),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name=PARAM_NISBAH,
        level=ParameterLevel.INSTANCE,
        description="The portion of profit shared to customers",
        display_name="Nisbah Rate",
        shape=NumberShape(min_value=0, max_value=1, step=Decimal('0.0001')),
        default_value=Decimal("0.00"),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
    Parameter( # TODO maybe change GDR to global level 
        name=PARAM_PENALTY_DAYS,
        level=ParameterLevel.INSTANCE,
        description="The number of days will be take out from revenue sharing accrual",
        display_name="Penalty days",
        shape=NumberShape(min_value=0, max_value=60, step=Decimal('1')),
        default_value=Decimal("0.00"),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
]

days_in_year_parameter = Parameter(
    name=PARAM_DAYS_IN_YEAR,
    shape=UnionShape(
        items=[
            UnionItem(key="actual", display_name="Actual"),
            UnionItem(key="366", display_name="366"),
            UnionItem(key="365", display_name="365"),
            UnionItem(key="360", display_name="360"),
        ]
    ),
    level=ParameterLevel.TEMPLATE,
    description="The days in the year for profit accrual calculation."
    ' Valid values are "actual", "366", "365", "360"',
    display_name="Profit Accrual Days In Year",
    default_value=UnionItemValue(key="365"),
)

accrual_precision_parameter = Parameter(
    name=PARAM_ACCRUAL_PRECISION,
    level=ParameterLevel.TEMPLATE,
    description="Precision needed for profit accruals.",
    display_name="Profit Accrual Precision",
    shape=NumberShape(min_value=0, max_value=15, step=1),
    default_value=Decimal('6'),
)

schedule_parameters = [
    Parameter(
        name=PARAM_PROFIT_ACCRUAL_HOUR,
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which profit is accrued.",
        display_name="Profit Accrual Hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_PROFIT_ACCRUAL_MINUTE,
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which profit is accrued.",
        display_name="Profit Accrual Minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_PROFIT_ACCRUAL_SECOND,
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which profit is accrued.",
        display_name="Profit Accrual Second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
]

accrued_profit_payable_account_parameter = Parameter(
    name=PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT,
    level=ParameterLevel.TEMPLATE,
    description="Internal account for accrued profit payable balance.",
    display_name="Accrued Profit Payable Account",
    shape=AccountIdShape(),
    default_value=ACCRUED_PROFIT_PAYABLE,
)

PARAM_EARLY_WITHDRAWAL_AMOUNT = "early_withdrawal_amount"
early_withdrawal_parameter = Parameter(
    name=PARAM_EARLY_WITHDRAWAL_AMOUNT,
    shape=NumberShape(),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="The amount which will be disbursed when customer "
    "request for early withdrawal.",
    display_name="Early Withdrawal Amount",
)

all_parameters = [
    accrual_precision_parameter,
    accrued_profit_payable_account_parameter,
    days_in_year_parameter,
    early_withdrawal_parameter,
    *eq_rate_parameters,
    *schedule_parameters,
    *validation_parameters,
]


def event_types(product_name: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=ACCRUAL_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{ACCRUAL_EVENT}_AST"],
        )
    ]


def scheduled_events(
    vault: SmartContractVault, start_datetime: datetime
) -> dict[str, ScheduledEvent]:
    return {
        ACCRUAL_EVENT: utils.daily_scheduled_event(
            vault=vault, start_datetime=start_datetime, parameter_prefix=PROFIT_ACCRUAL_PREFIX
        )
    }


def accrue_profit(
    *,
    vault: SmartContractVault,
    accrual_address: str = ACCRUED_PROFIT_PAYABLE,
    account_type: Optional[str] = None,
    effective_datetime: datetime
) -> list[CustomInstruction]:
    """
    Creates the posting instructions to accrue profit on the balances specified by
    the denomination and capital addresses parameters
    :param vault: the vault object to use to for retrieving data and instructing directives
    :param effective_datetime: the effective date to retrieve capital balances to accrue on
    :param accrual_address: balance address for the accrual amount to be assigned
    :return: the accrual posting custom instructions
    """
    denomination = utils.get_parameter(vault, name="denomination")
    accrued_profit_payable_account: str = utils.get_parameter(
        vault, name=PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT
    )
    days_in_year: str = utils.get_parameter(vault, name=PARAM_DAYS_IN_YEAR, is_union=True)
    numb_of_days = utils.get_days_in_year(
        days_in_year=days_in_year,
        effective_date=effective_datetime,
    )
    rounding_precision: int = utils.get_parameter(vault, name=PARAM_ACCRUAL_PRECISION)
    gdr = utils.get_parameter(vault, name=PARAM_GROSS_DISTRIBUTION_RATE)
    nisbah = utils.get_parameter(vault, name=PARAM_NISBAH)
    amount_to_accrue, instruction_detail = get_accrual_amount(
        effective_balance=get_accrual_capital(vault),
        gdr=gdr,
        nisbah= nisbah,
        days_in_year=numb_of_days,
        precision=rounding_precision,
    )

    if account_type is None:
        account_type = ""

    instruction_details = utils.standard_instruction_details(
        description=instruction_detail.strip(),
        event_type=f"{ACCRUAL_EVENT}",
        account_type=account_type,
    )
    # Negative profit accrual is not supported
    if amount_to_accrue > 0:
        return accruals.accrual_custom_instruction(
            customer_account=vault.account_id,
            customer_address=accrual_address,
            denomination=denomination,
            amount=amount_to_accrue,
            internal_account=accrued_profit_payable_account,
            payable=True,
            instruction_details=instruction_details,
        )
        
    else:
        return []


def get_accrual_amount(
    *,
    effective_balance: Decimal,
    gdr: Decimal,
    nisbah:Decimal,
    days_in_year: int = 360,
    precision: int = 6,
) -> tuple[Decimal, str]:
    """
    Calculate the amount to accrue on each balance portion by tier rate (to defined precision).
    Provide instruction details highlighting the breakdown of the tiered accrual.
    :param effective_balance: balance to accrue on
    :param gdr: gross distribution rates parameter
    :param nisbah: nisbah portion for customer
    :param days_in_year: days in year parameter
    :param accrual_precision: accrual precision parameter
    :return: rounded accrual_amount and instruction_details
    """
    daily_accrual_amount = Decimal("0")
    instruction_detail = ""

    eq_rate = calculate_eq_rate(gdr, nisbah, precision)
    
    daily_accrual_amount = utils.round_decimal(amount= effective_balance * eq_rate / days_in_year, decimal_places= precision)
    
    instruction_detail = (
        f"{instruction_detail}Accrual on {effective_balance:.2f} "
        f"at annual rate of {gdr:.2f}%. "
    )
    return (
        daily_accrual_amount,
        instruction_detail,
    )

def calculate_eq_rate(
        gdr: Decimal,
        nisbah: Decimal,
        precision: int = 6
):
    eq_rate = gdr*nisbah
    return utils.round_decimal(amount= eq_rate, decimal_places= precision)

def get_accrual_capital(
    vault: SmartContractVault,
    *,
    capital_addresses: Optional[list[str]] = None,
) -> Decimal:
    """
    Calculates the sum of balances that will be used to accrue profit on.
    We should check the last possible time capital could accrue
    (i.e. at 23:59:59.999999 on the day before effective_datetime)
    :param vault: the vault object to use to for retrieving data and instructing directives
    :param capital_addresses: list of balance addresses that will be summed up to provide
    the amount to accrue profit on. Defaults to the DEFAULT_ADDRESS
    :return: the sum of balances on which profit will be accrued on
    """
    denomination = utils.get_parameter(vault, name="denomination")
    balances = vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances

    accrual_balance = utils.sum_balances(
        balances=balances,
        addresses=capital_addresses or [DEFAULT_ADDRESS],
        denomination=denomination,
    )

    # This is only used for deposit accruals, so we do not want to accrue on negative balances.
    return accrual_balance if accrual_balance > 0 else Decimal('0')


def get_daily_profit_rate(
    *, annual_rate: str, days_in_year: str, effective_datetime: datetime
) -> Decimal:
    return utils.yearly_to_daily_rate(
        effective_date=effective_datetime,
        yearly_rate=Decimal(annual_rate),
        days_in_year=days_in_year,
    )


def get_accrued_profit(
    *,
    balances: BalanceDefaultDict,
    denomination: str,
    accrued_profit_address: str = ACCRUED_PROFIT_PAYABLE,
) -> Decimal:
    """
    Retrieves the existing balance for accrued profit at a specific time
    :param balances: the balances to sum accrued profit
    :param denomination: the denomination of the capital balances and the profit accruals
    :param accrued_profit_address: the address name in which we are storing the accrued profit
    :return: the value of the balance at the requested time
    """
    return utils.balance_at_coordinates(
        balances=balances, address=accrued_profit_address, denomination=denomination
    )


def get_profit_reversal_postings(
    *,
    vault: SmartContractVault,
    accrued_profit_address: str = ACCRUED_PROFIT_PAYABLE,
    event_name: str = REVERSAL_ACCRUAL_EVENT,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    account_type: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Reverse any accrued profit and apply back to the internal account.
    During account closure, any positively accrued profit that has not been applied
    should return back to the bank's internal account.
    :param vault: the vault object used to create profit reversal postings
    :param accrued_profit_address: the balance address used to store the accrued profit
    :param event_name: the name of the event reversing any accrue profit
    :param balances: balances to use to get profit to reverse. Defaults to previous EOD balances
    if not, relative to hook execution effective datetime
    :param denomination: the denomination of the profit accruals to reverse
    :param account_type: the account type to be populated on posting instruction details
    :return: the accrued profit reversal posting instructions
    """
    accrued_profit_payable_account: str = utils.get_parameter(
        vault, name=PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT
    )
    if denomination is None:
        denomination = str(utils.get_parameter(vault, name="denomination"))
    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances

    accrued_profit = get_accrued_profit(
        balances=balances,
        denomination=denomination,
        accrued_profit_address=accrued_profit_address,
    )

    instruction_details = utils.standard_instruction_details(
        description=f"Reversal of accrued profit of value {accrued_profit} {denomination}"
        " due to account closure.",
        event_type=f"{event_name}",
        gl_impacted=True,
        account_type=account_type or "",
    )

    # negative profit accruals are not supported
    if accrued_profit > 0:
        return accruals.accrual_custom_instruction(
            customer_account=vault.account_id,
            customer_address=accrued_profit_address,
            denomination=denomination,
            amount=accrued_profit,
            internal_account=accrued_profit_payable_account,
            payable=True,
            instruction_details=instruction_details,
            reversal=True,
        )
    else:
        return []


def get_early_withdrawal_amount(
    *,
    vault: SmartContractVault,
    denomination: str,
    profit_address: str = 'APPLIED_PROFIT',
    effective_datetime: Optional[datetime] = None,
)-> tuple[Decimal, Decimal, Decimal]:
    
    application_frequency: str = utils.get_parameter(
        vault, name=profit_application.PARAM_PROFIT_APPLICATION_FREQUENCY, is_union=True
    )
    oncall_date = utils.get_parameter(vault, name=deposit_maturity_mdh.PARAM_DESIRED_MATURITY_DATE,is_optional=True)
    if oncall_date:
        schedule_day = int(oncall_date.day)
    else:
        deposit_date=utils.get_parameter(vault, name=PARAM_EXPECTED_DEPOSIT_DATE,is_optional=True)
        if deposit_date:
            schedule_day = int(deposit_date.day)
        else:
            schedule_day=int(effective_datetime.day)

    last_application_datetimte = utils.get_next_schedule_date(start_date=effective_datetime,schedule_frequency=application_frequency, intended_day=schedule_day)
    last_application_datetimte=last_application_datetimte+relativedelta(months=-1)
    days_difference = (last_application_datetimte.date() - effective_datetime.date()).days
    penalty_days: str = utils.get_parameter(vault, name=PARAM_PENALTY_DAYS)
    
    days_in_year: str = utils.get_parameter(vault, name=PARAM_DAYS_IN_YEAR, is_union=True)
    numb_of_days = utils.get_days_in_year(
        days_in_year=days_in_year,
        effective_date=effective_datetime,
    )
    accrual_precision: int = utils.get_parameter(vault, name=PARAM_ACCRUAL_PRECISION)
    rounding_precision: int = utils.get_parameter(vault, name=profit_application.PARAM_APPLICATION_PRECISION)
    gdr = utils.get_parameter(vault, name=PARAM_EARLY_WITHDRAWAL_GROSS_DISTRIBUTION_RATE)
    nisbah = utils.get_parameter(vault, name=PARAM_NISBAH)
    daily_accrual_amount, _ = get_accrual_amount(
        effective_balance=get_accrual_capital(vault),
        gdr=gdr,
        nisbah= nisbah,
        days_in_year=numb_of_days,
        precision=accrual_precision,
    )
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.LIVE_BALANCES_BOF_ID
    ).balances

    deposit_amount = utils.balance_at_coordinates(
        balances=balances,
        address=DEFAULT_ADDRESS,
        denomination=denomination,
    )
    profit_amount = utils.balance_at_coordinates(
        balances=balances,
        address=profit_address,
        denomination=denomination,
    )
    return (
        utils.round_decimal(abs(deposit_amount),decimal_places=rounding_precision),
        utils.round_decimal(abs(profit_amount),decimal_places=rounding_precision),
        utils.round_decimal(daily_accrual_amount*(days_difference-penalty_days),decimal_places=rounding_precision)
    )


def handle_early_withdrawal(
    *,
    vault: SmartContractVault,
    accrued_profit_address: str = ACCRUED_PROFIT_PAYABLE,
    profit_address: str = 'APPLIED_PROFIT',
    denomination: Optional[str] = None,
    account_type: Optional[str] = None,
    effective_datetime: datetime = None,
) -> list[CustomInstruction]:
    """
    Reverse any accrued profit and apply back to the internal account.
    During account closure, any positively accrued profit that has not been applied
    should return back to the bank's internal account.
    :param vault: the vault object used to create profit reversal postings
    :param accrued_profit_address: the balance address used to store the accrued profit
    :param denomination: the denomination of the profit accruals to reverse
    :param account_type: the account type to be populated on posting instruction details
    :param effective_datetime: the effective date to retrieve capital balances to accrue on
    :return: the accrued profit reversal posting instructions
    """

    principal_amount,_,new_accrual_amount=get_early_withdrawal_amount(
        vault=vault,
        denomination=denomination,
        effective_datetime=effective_datetime
    )
    accrued_profit_payable_account: str = utils.get_parameter(
        vault, name=PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT
    )
    posting_instructions: list[CustomInstruction] = []

    posting_instructions.extend(
        get_profit_reversal_postings(
            vault=vault,
            accrued_profit_address=accrued_profit_address,
            event_name=REVERSAL_ACCRUAL_EVENT,
            account_type=account_type
        )
    )
    instruction_details = utils.standard_instruction_details(
        description=f"Apply of accrued profit of value {new_accrual_amount} {denomination}"
        " due to early withdrawal.",
        event_type=f"{REVERSAL_ACCRUAL_EVENT}",
        gl_impacted=True,
        account_type=account_type or "",
    )

    # negative profit accruals are not supported
    if new_accrual_amount > 0:
        posting_instructions.extend(
           accruals.accrual_custom_instruction(
                customer_account=vault.account_id,
                customer_address=accrued_profit_address,
                denomination=denomination,
                amount=new_accrual_amount,
                internal_account=accrued_profit_payable_account,
                payable=True,
                instruction_details=instruction_details,
                reversal=False,
            ) 
        )
    if abs(principal_amount)>0:
        posting_instructions.extend(
            deposit_maturity_mdh.disbursement_custom_instruction(
                debit_account=vault.account_id,
                denomination=denomination,
                amount=abs(principal_amount),
                instruction_details=utils.standard_instruction_details(
                    description=f"Reverse applied profit {principal_amount} {denomination}",
                    event_type=deposit_maturity_mdh.DISBURSEMENT_EVENT,
                    gl_impacted=True,
                    account_type=account_type,
                ),
                credit_account=vault.account_id,
                debit_address=profit_address
            )
        )

    return posting_instructions