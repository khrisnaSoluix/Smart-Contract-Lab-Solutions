# CBF: Overdraft Interest
# CBF: Overdraft Interest Free Buffer

# standard libs
from datetime import datetime
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.common.accruals as accruals
import library.features.common.common_parameters as common_parameters
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    AccountIdShape,
    BalanceDefaultDict,
    BalancesObservation,
    CustomInstruction,
    NumberShape,
    OptionalShape,
    OptionalValue,
    Parameter,
    ParameterLevel,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Addresses
OVERDRAFT_ACCRUED_INTEREST = "OVERDRAFT_ACCRUED_INTEREST"

# Events
OVERDRAFT_ACCRUAL_EVENT = "ACCRUE_OVERDRAFT_DAILY_FEE"
OVERDRAFT_APPLICATION_EVENT = "APPLY_OVERDRAFT_DAILY_FEE"

# Fetchers
overdraft_interest_free_buffer_days_fetchers = [
    fetchers.PREVIOUS_EOD_1_FETCHER,
    fetchers.PREVIOUS_EOD_2_FETCHER,
    fetchers.PREVIOUS_EOD_3_FETCHER,
    fetchers.PREVIOUS_EOD_4_FETCHER,
    fetchers.PREVIOUS_EOD_5_FETCHER,
]
overdraft_accrual_data_fetchers = [
    fetchers.EOD_FETCHER,
    *overdraft_interest_free_buffer_days_fetchers,
]
all_overdraft_interest_fetchers = [
    fetchers.EFFECTIVE_OBSERVATION_FETCHER,
    *overdraft_accrual_data_fetchers,
]

# Parameters
PARAM_OVERDRAFT_INTEREST_RATE = "overdraft_interest_rate"
PARAM_OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT = "overdraft_interest_receivable_account"
PARAM_OVERDRAFT_INTEREST_RECEIVED_ACCOUNT = "overdraft_interest_received_account"
PARAM_OVERDRAFT_INTEREST_FREE_BUFFER_DAYS = "interest_free_buffer_days"
PARAM_OVERDRAFT_INTEREST_FREE_BUFFER_AMOUNT = "interest_free_buffer_amount"

parameters = [
    # Template parameters
    Parameter(
        name=PARAM_OVERDRAFT_INTEREST_RATE,
        level=ParameterLevel.TEMPLATE,
        description="The yearly rate at which overdraft interest is accrued.",
        display_name="Overdraft Interest Rate",
        shape=OptionalShape(
            shape=NumberShape(
                min_value=Decimal("0"), max_value=Decimal("1"), step=Decimal("0.0001")
            )
        ),
        default_value=OptionalValue(Decimal("0.05")),
    ),
    Parameter(
        name=PARAM_OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for overdraft accrued interest receivable balance.",
        display_name="Overdraft Accrued Interest Receivable Account",
        shape=OptionalShape(shape=AccountIdShape()),
        default_value=OptionalValue("accrued_interest_receivable_account"),
    ),
    Parameter(
        name=PARAM_OVERDRAFT_INTEREST_RECEIVED_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for overdraft accrued interest received balance.",
        display_name="Overdraft Accrued Interest Received Account",
        shape=OptionalShape(shape=AccountIdShape()),
        default_value=OptionalValue("accrued_interest_received_account"),
    ),
    Parameter(
        name=PARAM_OVERDRAFT_INTEREST_FREE_BUFFER_DAYS,
        level=ParameterLevel.TEMPLATE,
        description="Maximum number of consecutive days that the account can benefit from the "
        "interest free buffer. If the number is exceeded, the buffer no longer applies and "
        "overdraft interest is accrued on the entire overdrawn balance. The count is reset by the "
        "account balance being positive at end of day. When not defined, the buffer amount always "
        "applies. See Interest Free Buffer Amount for more details.",
        display_name="Interest Free Buffer Days",
        shape=OptionalShape(shape=NumberShape(min_value=0, max_value=5, step=1)),
        default_value=OptionalValue(0),
    ),
    Parameter(
        name=PARAM_OVERDRAFT_INTEREST_FREE_BUFFER_AMOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Courtesy amount that will be added to the customer’s EOD overdraft balance "
        "reducing or eliminating the overdraft interest accrued. If it is not explicitly set, the "
        "buffer amount will be equal to the overdraft balance for the duration of the buffer "
        "period. See Interest Free Buffer Days for more details.",
        display_name="Interest Free Buffer Amount",
        shape=OptionalShape(shape=NumberShape(min_value=0, step=1)),
        default_value=OptionalValue(0),
    ),
]


def accrue_interest(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    account_type: str = "",
) -> list[CustomInstruction]:
    """
    Creates the posting instructions to accrue overdraft interest on the balances specified by
    the denomination and addresses parameters.

    This requires 6 days of balances for the interest_free_buffer_days comparison.
    :param vault: the vault object to use to for retrieving data and instructing directives
    :param effective_datetime: the effective date and time to use for retrieving balances to accrue
    overdraft interest on
    :account_type: the account type for GL purposes (e.g. to identify postings pertaining to
    current accounts vs savings accounts)
    :return: the overdraft accrual posting instructions
    """
    yearly_interest_rate: Decimal = utils.get_parameter(
        vault=vault,
        name=PARAM_OVERDRAFT_INTEREST_RATE,
        is_optional=True,
        default_value=Decimal("0"),
    )
    overdraft_interest_receivable_account: str = utils.get_parameter(
        vault=vault,
        name=PARAM_OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT,
        is_optional=True,
        default_value="",
    )
    # Check that the required optional parameters are set
    if yearly_interest_rate > 0 and overdraft_interest_receivable_account:
        interest_free_amount = Decimal(
            utils.get_parameter(
                vault=vault,
                name=PARAM_OVERDRAFT_INTEREST_FREE_BUFFER_AMOUNT,
                is_optional=True,
                default_value=0,
            )
        )
        interest_free_days = int(
            utils.get_parameter(
                vault=vault,
                name=PARAM_OVERDRAFT_INTEREST_FREE_BUFFER_DAYS,
                is_optional=True,
                default_value=0,
            )
        )
        denomination = common_parameters.get_denomination_parameter(
            vault=vault, effective_datetime=effective_datetime
        )
        accrual_balance = _calculate_accrual_balance(
            interest_free_amount=interest_free_amount,
            interest_free_days=interest_free_days,
            denomination=denomination,
            observations=_retrieve_eod_observations(vault=vault),
        )
        if accrual_balance < 0:
            days_in_year = str(utils.get_parameter(vault, "days_in_year", is_union=True))
            rounding_precision: int = utils.get_parameter(vault, "accrual_precision")

            day_rate = utils.yearly_to_daily_rate(
                effective_date=effective_datetime,
                yearly_rate=yearly_interest_rate,
                days_in_year=days_in_year,
            )
            accrual_amount_rounded = utils.round_decimal(
                abs(accrual_balance) * day_rate, decimal_places=rounding_precision
            )

            return accruals.accrual_custom_instruction(
                customer_account=vault.account_id,
                customer_address=OVERDRAFT_ACCRUED_INTEREST,
                denomination=denomination,
                amount=accrual_amount_rounded,
                internal_account=overdraft_interest_receivable_account,
                payable=False,
                instruction_details=utils.standard_instruction_details(
                    description=f"Accrual on overdraft balance of {accrual_balance:.2f} "
                    f"{denomination} at {yearly_interest_rate*100:.2f}%",
                    event_type=OVERDRAFT_ACCRUAL_EVENT,
                    gl_impacted=True,
                    account_type=account_type,
                ),
            )
    return []


def _retrieve_eod_observations(*, vault: SmartContractVault) -> list[BalancesObservation]:
    """
    Retrieves the last 6 End-Of-Day Observations balances to be used in the determination of what
    should be the overdraft balance used in the interest calculation.
    Positions:[0] - current EOD, [1] - Previous Day, [2] - 2 Days Ago, ... , [5] - 5 Days Ago

    :param vault: the vault object used to for retrieving the balance data
    :return: list of observation balances ordered in reverse chronological order
    """
    return [
        vault.get_balances_observation(fetcher_id=fetcher.fetcher_id)
        for fetcher in overdraft_accrual_data_fetchers
    ]


def _calculate_accrual_balance(
    *,
    interest_free_amount: Decimal,
    interest_free_days: int,
    denomination: str,
    observations: list[BalancesObservation],
) -> Decimal:
    """
    Factor in optional interest free buffer days and amount to determine the balance on which the
    customer should be charged overdraft interest. Returns 0 if calculated amount is positive.
    :param interest_free_amount: positive amount to be added to EOD balance, if set to zero the
    buffer amount is considered disabled.
    :param interest_free_days: number of consecutive days that the interest free buffer amount
    should be applied, if set to zero this restriction is disabled and the interest free buffer
    amount will always added to the overdraft balance.
    :param denomination: the denomination of the balances and the interest accruals
    :param observations: EOD observation balances, in a reverse chronological order
    :return: the balance to use in overdraft interest accruals, should always be less or equal zero
    """

    end_of_day_balance = utils.balance_at_coordinates(
        balances=observations[0].balances,
        denomination=denomination,
    )
    # If EOD balance is positive no need to continue since the account is not in overdraft
    if end_of_day_balance >= 0:
        return Decimal("0")

    buffered_end_of_day_balance = end_of_day_balance + interest_free_amount

    # If the buffer period is set to 0 the buffer amount is always applied
    if interest_free_days == 0:
        if buffered_end_of_day_balance >= 0:
            return Decimal("0")
        else:
            return buffered_end_of_day_balance

    highest_amount = max(
        utils.balance_at_coordinates(balances=observation.balances, denomination=denomination)
        for observation in observations[1 : interest_free_days + 1]
    )
    # If there is a positive day in the interest free period the free buffer amount is still
    # applied (if the interest free amount is set to zero the full overdraft amount will covered)
    # otherwise it means the free period limit has been reached and the buffer amount no longer
    # applies
    if highest_amount >= 0:
        if buffered_end_of_day_balance >= 0 or interest_free_amount == 0:
            return Decimal("0")
        else:
            return buffered_end_of_day_balance
    else:
        return end_of_day_balance


def apply_interest(
    *,
    vault: SmartContractVault,
    account_type: str = "",
) -> list[CustomInstruction]:
    """
    Creates the postings instructions to apply the accrued overdraft interest and additional
    postings required to zero the accrued overdraft interest remainders.
    Note: The standard interest application parameters are followed for overdraft interest
    application (frequency, day, hour, minute, second and precision)

    :param vault: the vault object to use to for retrieving data and instructing directives
    :param account_type: the account type for GL purposes (e.g. to identify postings pertaining to
    current accounts vs savings accounts)
    :return: the overdraft interest application related posting instructions
    """

    denomination = common_parameters.get_denomination_parameter(vault=vault)
    balance_observation = vault.get_balances_observation(
        fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
    )
    accrued_overdraft_interest = utils.balance_at_coordinates(
        balances=balance_observation.balances,
        address=OVERDRAFT_ACCRUED_INTEREST,
        denomination=denomination,
    )
    # No accrued overdraft interest to charge to the account
    if accrued_overdraft_interest == 0:
        return []

    overdraft_interest_receivable_account: str = utils.get_parameter(
        vault=vault,
        name=PARAM_OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT,
        is_optional=True,
        default_value="",
    )
    overdraft_interest_received_account: str = utils.get_parameter(
        vault=vault,
        name=PARAM_OVERDRAFT_INTEREST_RECEIVED_ACCOUNT,
        is_optional=True,
        default_value="",
    )

    # Validate that the required optional parameters are set
    if overdraft_interest_receivable_account and overdraft_interest_received_account:
        application_precision: int = utils.get_parameter(vault, "application_precision")
        application_amount_rounded = utils.round_decimal(
            amount=accrued_overdraft_interest,
            decimal_places=application_precision,
        )
        return accruals.accrual_application_custom_instruction(
            customer_account=vault.account_id,
            denomination=denomination,
            accrual_amount=abs(accrued_overdraft_interest),
            accrual_customer_address=OVERDRAFT_ACCRUED_INTEREST,
            accrual_internal_account=overdraft_interest_receivable_account,
            application_amount=abs(application_amount_rounded),
            application_customer_address=DEFAULT_ADDRESS,
            application_internal_account=overdraft_interest_received_account,
            payable=False,
            instruction_details=utils.standard_instruction_details(
                description=f"Apply {application_amount_rounded} {denomination} overdraft "
                f"interest of {accrued_overdraft_interest} rounded to {application_precision}"
                f" DP to {vault.account_id}.",
                event_type=OVERDRAFT_APPLICATION_EVENT,
                gl_impacted=True,
                account_type=account_type,
            ),
        )

    return []


def get_interest_reversal_postings(
    *,
    vault: SmartContractVault,
    event_name: str,
    account_type: str = "",
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Reverse any accrued overdraft interest and apply back to the internal account.
    During account closure, any overdraft interest that has not been applied should return back to
    the bank's internal account.
    :param vault: the vault object used to create interest reversal posting instruction
    :param event_name: the name of the event reversing any accrue interest
    :param account_type: the account type for GL purposes (e.g. to identify postings pertaining to
    current accounts vs savings accounts)
    :param balances: latest account balances available, if not provided balances will be retrieved
    using the EFFECTIVE_OBSERVATION_FETCHER_ID
    :param denomination: the denomination of the account, if not provided the
    'denomination' parameter is retrieved
    :return: the accrued interest reversal posting instructions
    """

    overdraft_interest_receivable_account: str = utils.get_parameter(
        vault=vault,
        name=PARAM_OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT,
        is_optional=True,
        default_value="",
    )
    # Required optional parameters are not set
    if not overdraft_interest_receivable_account:
        return []

    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances

    accrued_overdraft_interest = utils.balance_at_coordinates(
        balances=balances,
        address=OVERDRAFT_ACCRUED_INTEREST,
        denomination=denomination,
    )
    # No accrued overdraft interest to revert
    if accrued_overdraft_interest == 0:
        return []

    return accruals.accrual_custom_instruction(
        customer_account=vault.account_id,
        customer_address=OVERDRAFT_ACCRUED_INTEREST,
        denomination=denomination,
        amount=abs(accrued_overdraft_interest),
        internal_account=overdraft_interest_receivable_account,
        payable=False,
        instruction_details=utils.standard_instruction_details(
            description=f"Reversing {accrued_overdraft_interest} {denomination} "
            "of accrued overdraft interest.",
            event_type=event_name,
            gl_impacted=True,
            account_type=account_type,
        ),
        reversal=True,
    )
