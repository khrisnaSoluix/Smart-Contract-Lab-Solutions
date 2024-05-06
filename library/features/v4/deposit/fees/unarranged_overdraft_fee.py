# CBF: Unarranged Overdraft and Unarranged Overdraft Fee

# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.common.accruals as accruals
import library.features.common.common_parameters as common_parameters
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.deposit.transaction_limits.overdraft.overdraft_limit as overdraft_limit

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    AccountIdShape,
    BalanceDefaultDict,
    CustomInstruction,
    NumberShape,
    OptionalShape,
    OptionalValue,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    ScheduledEvent,
    SmartContractEventType,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Constants
ACCRUAL_EVENT = "ACCRUE_UNARRANGED_OVERDRAFT_FEE"
APPLICATION_EVENT = "APPLY_UNARRANGED_OVERDRAFT_FEE"
# fetchers
data_fetchers = [fetchers.EOD_FETCHER, fetchers.EFFECTIVE_OBSERVATION_FETCHER]

# addresses
OVERDRAFT_FEE = "UNARRANGED_OVERDRAFT_FEE"

# parameter names specific to this feature
FEE_ACCRUAL_PREFIX = "unarranged_overdraft_fee_accrual"
FEE_APPLICATION_PREFIX = "unarranged_overdraft_fee_application"

PARAM_FEE_ACCRUAL_HOUR = f"{FEE_ACCRUAL_PREFIX}_hour"
PARAM_FEE_ACCRUAL_MINUTE = f"{FEE_ACCRUAL_PREFIX}_minute"
PARAM_FEE_ACCRUAL_SECOND = f"{FEE_ACCRUAL_PREFIX}_second"
PARAM_FEE_APPLICATION_DAY = f"{FEE_APPLICATION_PREFIX}_day"
PARAM_FEE_APPLICATION_HOUR = f"{FEE_APPLICATION_PREFIX}_hour"
PARAM_FEE_APPLICATION_MINUTE = f"{FEE_APPLICATION_PREFIX}_minute"
PARAM_FEE_APPLICATION_SECOND = f"{FEE_APPLICATION_PREFIX}_second"
PARAM_UNARRANGED_OVERDRAFT_FEE = "unarranged_overdraft_fee"
PARAM_UNARRANGED_OVERDRAFT_FEE_CAP = "unarranged_overdraft_fee_cap"
PARAM_UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT = "unarranged_overdraft_fee_income_account"
PARAM_UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT = "unarranged_overdraft_fee_receivable_account"

# Parameters specific to this feature

accrual_schedule_parameters = [
    Parameter(
        name=PARAM_FEE_ACCRUAL_HOUR,
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which unarranged overdraft fee is accrued.",
        display_name="Unarranged Overdraft Fee Accrual Hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_FEE_ACCRUAL_MINUTE,
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which unarranged overdraft fee is accrued.",
        display_name="Unarranged Overdraft Fee Accrual Minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_FEE_ACCRUAL_SECOND,
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which unarranged overdraft fee is accrued.",
        display_name="Unarranged Overdraft Fee Accrual Second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
]

application_schedule_parameters = [
    Parameter(
        name=PARAM_FEE_APPLICATION_DAY,
        shape=NumberShape(min_value=1, max_value=31, step=1),
        level=ParameterLevel.INSTANCE,
        description="The day of the month on which unarranged overdraft fee is applied. "
        "If day does not exist in application month, applies on last day of month.",
        display_name="Interest Application Day",
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
        default_value=1,
    ),
    Parameter(
        name=PARAM_FEE_APPLICATION_HOUR,
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which unarranged overdraft fee is applied.",
        display_name="Unarranged Overdraft Fee Application Hour",
        default_value=0,
    ),
    Parameter(
        name=PARAM_FEE_APPLICATION_MINUTE,
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which unarranged overdraft fee is applied.",
        display_name="Unarranged Overdraft Fee Application Minute",
        default_value=1,
    ),
    Parameter(
        name=PARAM_FEE_APPLICATION_SECOND,
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which unarranged overdraft fee is applied.",
        display_name="Unarranged Overdraft Fee Application Second",
        default_value=0,
    ),
]

feature_parameters = [
    Parameter(
        name=PARAM_UNARRANGED_OVERDRAFT_FEE,
        level=ParameterLevel.TEMPLATE,
        description="The daily fee charged for being in unarranged overdraft.",
        display_name="Unarranged Overdraft Fee",
        shape=OptionalShape(shape=NumberShape(min_value=0, step=Decimal("0.01"))),
        default_value=OptionalValue(Decimal("5.00")),
    ),
    Parameter(
        name=PARAM_UNARRANGED_OVERDRAFT_FEE_CAP,
        level=ParameterLevel.TEMPLATE,
        description="A monthly cap on accumulated fees for entering an unarranged overdraft.",
        display_name="Unarranged Overdraft Fee Cap",
        shape=OptionalShape(shape=NumberShape(min_value=0, step=Decimal("0.01"))),
        default_value=OptionalValue(Decimal("15.00")),
    ),
    Parameter(
        name=PARAM_UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for overdraft fee income balance.",
        display_name="Unarranged Overdraft Fee Income Account",
        shape=OptionalShape(shape=AccountIdShape()),
        default_value=OptionalValue("UNARRANGED_OVERDRAFT_FEE_INCOME"),
    ),
    Parameter(
        name=PARAM_UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for overdraft fee receivable account.",
        display_name="Unarranged Overdraft Fee Receivable Account",
        shape=OptionalShape(shape=AccountIdShape()),
        default_value=OptionalValue("UNARRANGED_OVERDRAFT_FEE_RECEIVABLE"),
    ),
]


def application_event_types(product_name: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=APPLICATION_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{APPLICATION_EVENT}_AST"],
        ),
    ]


def accrual_event_types(product_name: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=ACCRUAL_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{ACCRUAL_EVENT}_AST"],
        )
    ]


def accrual_scheduled_events(
    vault: SmartContractVault,
    start_datetime: datetime,
) -> dict[str, ScheduledEvent]:
    start_datetime_midnight = start_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        ACCRUAL_EVENT: utils.daily_scheduled_event(
            vault=vault,
            start_datetime=start_datetime_midnight + relativedelta(days=1),
            parameter_prefix=FEE_ACCRUAL_PREFIX,
        )
    }


def application_scheduled_events(
    vault: SmartContractVault,
    start_datetime: datetime,
) -> dict[str, ScheduledEvent]:
    start_datetime_midnight = start_datetime.replace(hour=0, minute=0, second=0, microsecond=0)

    return {
        APPLICATION_EVENT: utils.monthly_scheduled_event(
            vault=vault,
            start_datetime=start_datetime_midnight + relativedelta(months=1),
            parameter_prefix=FEE_APPLICATION_PREFIX,
        ),
    }


def accrue_fee(
    *,
    vault: SmartContractVault,
) -> list[CustomInstruction]:
    """
    Returns posting instructions to accrue unarranged overdraft fee
    or empty list if no fee should be accrued or any of the feature parameters not set.
    Overdraft fee is fully accrued if there is no overdraft fee cap or the cap doesn't exceeded
    or  partially accrued if part of new fee sums up to the overdraft fee cap.
    :param vault: Vault object for the account whose overdraft limit is being validated
    :return: posting instructions or empty list
    """
    # fee cannot be applied if optional parameters are not set
    if not utils.are_optional_parameters_set(
        vault=vault,
        parameters=[
            overdraft_limit.PARAM_ARRANGED_OVERDRAFT_AMOUNT,
            overdraft_limit.PARAM_UNARRANGED_OVERDRAFT_AMOUNT,
            PARAM_UNARRANGED_OVERDRAFT_FEE,
            PARAM_UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT,
            PARAM_UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
        ],
    ):
        return []

    denomination: str = utils.get_parameter(vault=vault, name="denomination")
    balances = vault.get_balances_observation(fetcher_id=fetchers.EOD_FETCHER_ID).balances
    effective_balance = utils.balance_at_coordinates(balances=balances, denomination=denomination)

    # fee will not be charged if the EOD balance is positive
    if effective_balance > 0:
        return []

    arranged_overdraft_amount: Decimal = utils.get_parameter(
        vault=vault,
        name=overdraft_limit.PARAM_ARRANGED_OVERDRAFT_AMOUNT,
        is_optional=True,
        default_value=Decimal("0"),
    )

    # fee will not be charged if the overdraft is within the arranged overdraft amount
    if abs(effective_balance) <= arranged_overdraft_amount:
        return []

    overdraft_fee: Decimal = utils.get_parameter(
        vault=vault,
        name=PARAM_UNARRANGED_OVERDRAFT_FEE,
        is_optional=True,
        default_value=Decimal("0"),
    )
    overdraft_fee_cap: Decimal = utils.get_parameter(
        vault=vault,
        name=PARAM_UNARRANGED_OVERDRAFT_FEE_CAP,
        is_optional=True,
        default_value=None,
    )
    overdraft_fee_receivable_account: str = utils.get_parameter(
        vault=vault,
        name=PARAM_UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
        is_optional=True,
        default_value="",
    )

    unarranged_overdraft_fee_balance = utils.balance_at_coordinates(
        balances=balances, address=OVERDRAFT_FEE, denomination=denomination
    )

    # if there is an unarranged overdraft fee cap defined and it has
    # been reached no additional fee will be accrued
    if overdraft_fee_cap:
        unarranged_overdraft_fee_balance = abs(unarranged_overdraft_fee_balance)

        # If overdraft fee balance cap already reached no additional fee will be accrued
        if unarranged_overdraft_fee_balance >= overdraft_fee_cap:
            return []

        # if the new fee can exceed the cap accrue only the amount up to the cap
        if unarranged_overdraft_fee_balance + overdraft_fee > overdraft_fee_cap:
            overdraft_fee = overdraft_fee_cap - unarranged_overdraft_fee_balance

    return accruals.accrual_custom_instruction(
        customer_account=vault.account_id,
        customer_address=OVERDRAFT_FEE,
        amount=Decimal(overdraft_fee),
        internal_account=overdraft_fee_receivable_account,
        payable=False,
        denomination=denomination,
        instruction_details={
            "description": f"Daily unarranged overdraft fee of {overdraft_fee} {denomination}",
            "event": ACCRUAL_EVENT,
        },
    )


def apply_fee(
    *,
    vault: SmartContractVault,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Creates posting instructions to to apply the fees, if required.
    Empty list if there is no fee to apply or feature parameters aren't set
    :param vault: Vault object
    :param balances: latest account balances available, if not provided balances will be retrieved
    using the EFFECTIVE_OBSERVATION_FETCHER_ID
    :param denomination: the denomination of the account, if not provided the
    'denomination' parameter is retrieved
    :return: posting instructions
    """

    # fee cannot be applied if optional parameters are not set
    if not utils.are_optional_parameters_set(
        vault=vault,
        parameters=[
            overdraft_limit.PARAM_ARRANGED_OVERDRAFT_AMOUNT,
            overdraft_limit.PARAM_UNARRANGED_OVERDRAFT_AMOUNT,
            PARAM_UNARRANGED_OVERDRAFT_FEE,
            PARAM_UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT,
            PARAM_UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
        ],
    ):
        return []

    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    unarranged_overdraft_fee_balance = utils.balance_at_coordinates(
        balances=balances, address=OVERDRAFT_FEE, denomination=denomination
    )

    posting_instructions: list[CustomInstruction] = []

    if unarranged_overdraft_fee_balance != 0:
        overdraft_fee_receivable_account: str = utils.get_parameter(
            vault=vault,
            name=PARAM_UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
            is_optional=True,
            default_value="",
        )

        overdraft_fee_income_account: str = utils.get_parameter(
            vault=vault,
            name=PARAM_UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT,
            is_optional=True,
            default_value="",
        )

        unarranged_overdraft_fee_balance = abs(unarranged_overdraft_fee_balance)

        # apply charged fees to customer account
        posting_instructions.extend(
            accruals.accrual_application_custom_instruction(
                customer_account=vault.account_id,
                denomination=denomination,
                application_amount=Decimal(unarranged_overdraft_fee_balance),
                accrual_amount=Decimal(unarranged_overdraft_fee_balance),
                accrual_customer_address=OVERDRAFT_FEE,
                accrual_internal_account=overdraft_fee_receivable_account,
                application_internal_account=overdraft_fee_income_account,
                application_customer_address=DEFAULT_ADDRESS,
                payable=False,
                instruction_details={
                    "description": "Unarranged overdraft fee of "
                    f"{unarranged_overdraft_fee_balance} {denomination} applied.",
                    "event": APPLICATION_EVENT,
                },
            )
        )
    return posting_instructions
