# CBF: Minimum Balance Threshold and Fee

# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from json import dumps
from typing import Optional

# features
import library.features.v4.common.account_tiers as account_tiers
import library.features.common.common_parameters as common_parameters
import library.features.v4.common.fees as fees
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.deposit.deposit_interfaces as deposit_interfaces
import library.features.v4.deposit.fees.partial_fee as partial_fee

# contracts api
from contracts_api import (
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
    StringShape,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

APPLY_MINIMUM_MONTHLY_BALANCE_EVENT = "APPLY_MINIMUM_BALANCE_FEE"

# Addresses
OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER = "outstanding_minimum_balance_fee_tracker"

PARAM_MINIMUM_BALANCE_FEE = "minimum_balance_fee"
PARAM_MINIMUM_BALANCE_THRESHOLD_BY_TIER = "minimum_balance_threshold_by_tier"
PARAM_MINIMUM_BALANCE_FEE_INCOME_ACCOUNT = "minimum_balance_fee_income_account"
MINIMUM_BALANCE_FEE_PREFIX = "minimum_balance_fee_application"
PARAM_MINIMUM_BALANCE_FEE_DAY = f"{MINIMUM_BALANCE_FEE_PREFIX}_day"
PARAM_MINIMUM_BALANCE_FEE_HOUR = f"{MINIMUM_BALANCE_FEE_PREFIX}_hour"
PARAM_MINIMUM_BALANCE_FEE_MINUTE = f"{MINIMUM_BALANCE_FEE_PREFIX}_minute"
PARAM_MINIMUM_BALANCE_FEE_SECOND = f"{MINIMUM_BALANCE_FEE_PREFIX}_second"
PARAM_MINIMUM_BALANCE_PARTIAL_FEE_ENABLED = f"partial_{MINIMUM_BALANCE_FEE_PREFIX}_enabled"

parameters = [
    Parameter(
        name=PARAM_MINIMUM_BALANCE_FEE,
        level=ParameterLevel.TEMPLATE,
        description="The fee charged if the minimum balance falls below the threshold.",
        display_name="Minimum Balance Fee",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        default_value=Decimal("0.00"),
    ),
    Parameter(
        name=PARAM_MINIMUM_BALANCE_THRESHOLD_BY_TIER,
        level=ParameterLevel.TEMPLATE,
        description="The monthly minimum mean balance threshold by account tier",
        display_name="Minimum Balance Threshold By Tier",
        shape=StringShape(),
        default_value=dumps(
            {
                "UPPER_TIER": "25",
                "MIDDLE_TIER": "75",
                "LOWER_TIER": "100",
            }
        ),
    ),
    Parameter(
        name=PARAM_MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for minimum balance fee income balance.",
        display_name="Minimum Balance Fee Income Account",
        shape=AccountIdShape(),
        default_value="MINIMUM_BALANCE_FEE_INCOME",
    ),
    Parameter(
        name=PARAM_MINIMUM_BALANCE_FEE_DAY,
        shape=NumberShape(min_value=1, max_value=31, step=1),
        level=ParameterLevel.INSTANCE,
        description="The day of the month on which minimum balance fee is applied."
        "If day does not exist in application month, applies on last day of month.",
        display_name="Minimum Balance Fee Application Day",
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
        default_value=1,
    ),
    Parameter(
        name=PARAM_MINIMUM_BALANCE_FEE_HOUR,
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which minimum balance fee is applied.",
        display_name="Minimum Balance Fee Application Hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_MINIMUM_BALANCE_FEE_MINUTE,
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which minimum balance fee is applied.",
        display_name="Minimum Balance Fee Application Minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_MINIMUM_BALANCE_FEE_SECOND,
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which minimum balance fee is applied.",
        display_name="Minimum Balance Fee Application Second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=1,
    ),
    Parameter(
        name=PARAM_MINIMUM_BALANCE_PARTIAL_FEE_ENABLED,
        shape=OptionalShape(shape=common_parameters.BooleanShape),
        level=ParameterLevel.TEMPLATE,
        description="Enables / Disables partial payments for the Minimum Balance Fee.",
        display_name="Partial Minimum Balance Fees Enabled",
        default_value=OptionalValue(common_parameters.BooleanValueFalse),
    ),
]


def event_types(product_name: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=APPLY_MINIMUM_MONTHLY_BALANCE_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{APPLY_MINIMUM_MONTHLY_BALANCE_EVENT}_AST"],
        )
    ]


def scheduled_events(
    *, vault: SmartContractVault, start_datetime: datetime
) -> dict[str, ScheduledEvent]:
    """
    Creates scheduled event for minimum balance fee application
    :param vault: Vault object to retrieve application frequency and schedule params
    :param start_datetime: date to start schedules from e.g. account creation or loan start date
    :return: dict of minimum balance fee application scheduled events
    """
    scheduled_event = utils.monthly_scheduled_event(
        vault=vault,
        start_datetime=start_datetime,
        parameter_prefix=MINIMUM_BALANCE_FEE_PREFIX,
    )
    return {APPLY_MINIMUM_MONTHLY_BALANCE_EVENT: scheduled_event}


def apply_minimum_balance_fee(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
    available_balance_feature: Optional[deposit_interfaces.AvailableBalance] = None,
) -> list[CustomInstruction]:
    """
    Retrieves the minimum balance fee, minimum balance fee income account,
    and minimum balance threshold.
    The balance is calculated by averaging the monthly balance
    of the account in the currency at the point when the fee is charged.

    :param vault: vault object of the account whose fee is being assessed
    :param effective_datetime: date and time of hook being run
    :param denomination: the denomination of the paper statement fee, if not provided the
    'denomination' parameter is retrieved
    :param balances: Account balances, if not provided balances will be retrieved using the
    PREVIOUS_EOD_OBSERVATION_FETCHERS ids for the average balance calculations and the
    EFFECTIVE_OBSERVATION_FETCHER_ID for partial fee charging considerations.
    :param available_balance_feature: Callable to calculate the available balance for the account
    using a custom definition
    :return: Custom Instruction to apply the minimum monthly balance fee
    """
    fee_custom_instructions: list[CustomInstruction] = []

    minimum_balance_fee = _get_minimum_balance_fee(
        vault=vault, effective_datetime=effective_datetime
    )

    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    # If minimum balance fee is enabled, and balance fell below threshold, apply it
    if minimum_balance_fee > Decimal("0") and not _is_monthly_mean_balance_above_threshold(
        vault=vault,
        effective_datetime=effective_datetime,
        denomination=denomination,
    ):
        minimum_balance_fee_income_account = get_minimum_balance_fee_income_account(
            vault=vault, effective_datetime=effective_datetime
        )
        fee_custom_instructions = fees.fee_custom_instruction(
            customer_account_id=vault.account_id,
            denomination=denomination,
            amount=minimum_balance_fee,
            internal_account=minimum_balance_fee_income_account,
            instruction_details={
                "description": "Minimum balance fee",
                "event": APPLY_MINIMUM_MONTHLY_BALANCE_EVENT,
            },
        )
        if (
            are_partial_payments_enabled(vault=vault, effective_datetime=effective_datetime)
            and fee_custom_instructions
        ):
            if balances is None:
                balances = vault.get_balances_observation(
                    fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
                ).balances
            return partial_fee.charge_partial_fee(
                vault=vault,
                effective_datetime=effective_datetime,
                fee_custom_instruction=fee_custom_instructions[0],
                fee_details=PARTIAL_FEE_DETAILS,
                balances=balances,
                denomination=denomination,
                available_balance_feature=available_balance_feature,
            )

    return fee_custom_instructions


def _is_monthly_mean_balance_above_threshold(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    denomination: Optional[str] = None,
) -> bool:
    """
    Retrieves the minimum balance fee, minimum balance fee income account,
    and minimum balance threshold.
    The balance is calculated by averaging the monthly balance
    of the account in the currency at the point when the fee is charged.
    :param vault: vault object of the account whose fee is being assessed
    :param effective_datetime: date and time of hook being run
    :param denomination: the denomination of the minimum monthly fee
    :return: bool True if balance is above requirement
    """
    # Threshold is a tier parameter driven by an account-level flag
    minimum_balance_threshold_tiers = _get_minimum_balance_threshold_by_tier(
        vault=vault, effective_datetime=effective_datetime
    )

    tier = account_tiers.get_account_tier(vault, effective_datetime)

    minimum_balance_threshold = Decimal(
        account_tiers.get_tiered_parameter_value_based_on_account_tier(
            tiered_parameter=minimum_balance_threshold_tiers,
            tier=tier,
            convert=Decimal,
        )
        or Decimal("0")
    )

    if minimum_balance_threshold > Decimal("0"):
        creation_date = vault.get_account_creation_datetime().date()
        period_start = (effective_datetime - relativedelta(months=1)).date()

        # Scenarios when the account is created on a day that does not exist on the next month
        # e.g. Account Created Jan/31st Effective date Feb/28th = Period start Jan/28th
        if period_start <= creation_date:
            # Add one day to the creation date
            # because the balance is retrieved at midnight 00:00:00
            period_start = creation_date + relativedelta(days=1)

        num_days = (effective_datetime.date() - period_start).days

        balances_to_average = [
            utils.balance_at_coordinates(
                balances=vault.get_balances_observation(
                    fetcher_id=fetchers.PREVIOUS_EOD_OBSERVATION_FETCHERS[i].fetcher_id
                ).balances,
                denomination=denomination
                or common_parameters.get_denomination_parameter(vault=vault),
            )
            for i in range(num_days)
        ]

        monthly_mean_balance = utils.average_balance(
            balances=balances_to_average,
        )

        if monthly_mean_balance >= minimum_balance_threshold:
            return True
        return False

    return True


def get_minimum_balance_fee_income_account(
    vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> str:
    return str(
        utils.get_parameter(
            vault, name=PARAM_MINIMUM_BALANCE_FEE_INCOME_ACCOUNT, at_datetime=effective_datetime
        )
    )


def are_partial_payments_enabled(
    *, vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> bool:
    return utils.get_parameter(
        vault=vault,
        name=PARAM_MINIMUM_BALANCE_PARTIAL_FEE_ENABLED,
        at_datetime=effective_datetime,
        is_boolean=True,
        default_value=False,
        is_optional=True,
    )


def _get_minimum_balance_fee(vault: SmartContractVault, effective_datetime: datetime) -> Decimal:
    return Decimal(
        utils.get_parameter(vault, name=PARAM_MINIMUM_BALANCE_FEE, at_datetime=effective_datetime)
    )


def _get_minimum_balance_threshold_by_tier(
    vault: SmartContractVault, effective_datetime: datetime
) -> dict[str, str]:
    return utils.get_parameter(
        vault=vault,
        name=PARAM_MINIMUM_BALANCE_THRESHOLD_BY_TIER,
        at_datetime=effective_datetime,
        is_json=True,
    )


PARTIAL_FEE_DETAILS = deposit_interfaces.PartialFeeCollection(
    outstanding_fee_address=OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER,
    fee_type="Partial Minimum Balance Fee",
    get_internal_account_parameter=get_minimum_balance_fee_income_account,
)


WAIVE_FEE_WITH_MEAN_BALANCE_ABOVE_THRESHOLD = deposit_interfaces.WaiveFeeCondition(
    waive_fees=_is_monthly_mean_balance_above_threshold
)
