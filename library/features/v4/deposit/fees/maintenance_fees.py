# CBF: Monthly Service Fee (Maintenance Fee) apply_monthly_fee
# CBF: Annual Service Fee (Maintenance Fee) apply_annual_fee

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
    UpdateAccountEventTypeDirective,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Constants
# Events
APPLY_MONTHLY_FEE_EVENT = "APPLY_MONTHLY_FEE"
APPLY_ANNUAL_FEE_EVENT = "APPLY_ANNUAL_FEE"

# Frequencies
MONTHLY = "monthly"
ANNUALLY = "annually"

# Prefix
MAINTENANCE_FEE_APPLICATION_PREFIX = "maintenance_fee_application"

# Addresses
OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER = "outstanding_monthly_maintenance_fee_tracker"

# Parameter names
PARAM_MAINTENANCE_FEE_APPLICATION_DAY = f"{MAINTENANCE_FEE_APPLICATION_PREFIX}_day"
PARAM_MAINTENANCE_FEE_APPLICATION_HOUR = f"{MAINTENANCE_FEE_APPLICATION_PREFIX}_hour"
PARAM_MAINTENANCE_FEE_APPLICATION_MINUTE = f"{MAINTENANCE_FEE_APPLICATION_PREFIX}_minute"
PARAM_MAINTENANCE_FEE_APPLICATION_SECOND = f"{MAINTENANCE_FEE_APPLICATION_PREFIX}_second"
PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER = "monthly_maintenance_fee_by_tier"
PARAM_MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT = "monthly_maintenance_fee_income_account"
PARAM_MONTHLY_MAINTENANCE_FEE_PARTIAL_FEE_ENABLED = "partial_maintenance_fee_enabled"
PARAM_ANNUAL_MAINTENANCE_FEE_BY_TIER = "annual_maintenance_fee_by_tier"
PARAM_ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT = "annual_maintenance_fee_income_account"
PARAM_DENOMINATION = "denomination"

schedule_params = [
    # Instance parameters
    Parameter(
        name=PARAM_MAINTENANCE_FEE_APPLICATION_DAY,
        shape=NumberShape(min_value=1, max_value=31, step=1),
        level=ParameterLevel.INSTANCE,
        description="The day of the month on which maintenance fee is applied."
        "If day does not exist in application month, applies on last day of month.",
        display_name="Maintenance Fees Application Day",
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
        default_value=1,
    ),
    # Template parameters
    Parameter(
        name=PARAM_MAINTENANCE_FEE_APPLICATION_HOUR,
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which maintenance fees are applied.",
        display_name="Maintenance Fees Application Hour",
        default_value=0,
    ),
    Parameter(
        name=PARAM_MAINTENANCE_FEE_APPLICATION_MINUTE,
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which fees are applied.",
        display_name="Maintenance Fees Application Minute",
        default_value=1,
    ),
    Parameter(
        name=PARAM_MAINTENANCE_FEE_APPLICATION_SECOND,
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which fees are applied.",
        display_name="Maintenance Fees Application Second",
        default_value=0,
    ),
]

annual_params = [
    # Template parameters
    Parameter(
        name=PARAM_ANNUAL_MAINTENANCE_FEE_BY_TIER,
        level=ParameterLevel.TEMPLATE,
        description="The annual fee charged for account maintenance for different tiers.",
        display_name="Annual Maintenance Fee By Tier",
        shape=StringShape(),
        default_value=dumps(
            {
                "UPPER_TIER": "20",
                "MIDDLE_TIER": "10",
                "LOWER_TIER": "0",
            }
        ),
    ),
    Parameter(
        name=PARAM_ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for annual maintenance fee income balance.",
        display_name="Annual Maintenance Fee Income Account",
        shape=AccountIdShape(),
        default_value="ANNUAL_MAINTENANCE_FEE_INCOME",
    ),
]

monthly_params = [
    # Template parameters
    Parameter(
        name=PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER,
        level=ParameterLevel.TEMPLATE,
        description="The monthly maintenance fee by account tier",
        display_name="Monthly Maintenance Fee By Tier",
        shape=StringShape(),
        default_value=dumps(
            {
                "UPPER_TIER": "20",
                "MIDDLE_TIER": "10",
                "LOWER_TIER": "5",
            }
        ),
    ),
    Parameter(
        name=PARAM_MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for monthly maintenance fee income balance.",
        display_name="Monthly Maintenance Fee Income Account",
        shape=AccountIdShape(),
        default_value="MONTHLY_MAINTENANCE_FEE_INCOME",
    ),
    Parameter(
        name=PARAM_MONTHLY_MAINTENANCE_FEE_PARTIAL_FEE_ENABLED,
        shape=OptionalShape(shape=common_parameters.BooleanShape),
        level=ParameterLevel.TEMPLATE,
        description="Toggles partial payments for monthly maintenance fee",
        display_name="Monthly Maintenance Partial Fees Enabled",
        default_value=OptionalValue(common_parameters.BooleanValueFalse),
    ),
]

parameters = [
    *annual_params,
    *monthly_params,
    *schedule_params,
]


def event_types(*, product_name: str, frequency: str) -> list[SmartContractEventType]:
    """
    Creates monthly or annual event to apply maintenance fees
    :param product_name: the name of the product to create the event
    :param frequency: the frequency to create the monthly or annual event
    :return: Smart contract event type to scheduled event
    """
    if frequency == MONTHLY:
        event_name = APPLY_MONTHLY_FEE_EVENT
    elif frequency == ANNUALLY:
        event_name = APPLY_ANNUAL_FEE_EVENT
    else:
        return []
    return [
        SmartContractEventType(
            name=event_name,
            scheduler_tag_ids=[f"{product_name.upper()}_{event_name}_AST"],
        )
    ]


def scheduled_events(
    *,
    vault: SmartContractVault,
    start_datetime: datetime,
    frequency: str,
) -> dict[str, ScheduledEvent]:
    """
    Create monthly or annual scheduled event to apply maintenance fees
    :param vault: vault object for the account that requires the schedule
    :param start_datetime: Start datetime to create the schedule event
    :param frequency: frequency to create the monthly or annual schedule event
    :return: Schedule events for the monthly or annual maintenance fees
    """
    schedule_day = int(utils.get_parameter(vault, name=PARAM_MAINTENANCE_FEE_APPLICATION_DAY))

    if frequency == MONTHLY:
        event_name = APPLY_MONTHLY_FEE_EVENT

        maintenance_fee_schedule = {
            event_name: utils.monthly_scheduled_event(
                vault=vault,
                start_datetime=start_datetime + relativedelta(months=1),
                parameter_prefix=MAINTENANCE_FEE_APPLICATION_PREFIX,
                day=schedule_day,
            )
        }
    elif frequency == ANNUALLY:
        event_name = APPLY_ANNUAL_FEE_EVENT
        next_schedule_datetime = utils.get_next_schedule_date(
            start_date=start_datetime,
            schedule_frequency=ANNUALLY,
            intended_day=schedule_day,
        )
        schedule_expression = utils.get_schedule_expression_from_parameters(
            vault=vault,
            parameter_prefix=MAINTENANCE_FEE_APPLICATION_PREFIX,
            day=next_schedule_datetime.day,
            month=next_schedule_datetime.month,
            year=(
                None
                if (
                    int(next_schedule_datetime.month) != 2
                    or (int(next_schedule_datetime.month) == 2 and schedule_day < 29)
                )
                else next_schedule_datetime.year
            ),
        )
        maintenance_fee_schedule = {
            event_name: ScheduledEvent(
                start_datetime=start_datetime + relativedelta(years=1),
                expression=schedule_expression,
            ),
        }
    else:
        return {}

    return maintenance_fee_schedule


def apply_monthly_fee(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    monthly_fee_waive_conditions: Optional[list[deposit_interfaces.WaiveFeeCondition]] = None,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
    available_balance_feature: Optional[deposit_interfaces.AvailableBalance] = None,
) -> list[CustomInstruction]:
    """
    Gets monthly maintenance fees and the account where it will be credited.
    :param vault: Vault object for the account getting the fee assessed
    :param denomination: the denomination of the paper statement fee, if not provided the
    'denomination' parameter is retrieved
    :param balances: Account balances, if not provided balances will be retrieved using the
    EFFECTIVE_OBSERVATION_FETCHER_ID
    :param available_balance_feature: Interface to calculate the available balance for the account
    using a custom definition
    :return: Custom instructions to generate posting for monthly maintenance fees
    """
    if any(
        f.waive_fees(vault=vault, effective_datetime=effective_datetime)
        for f in monthly_fee_waive_conditions or []
    ):
        return []

    maintenance_fee_income_account = _get_monthly_internal_income_account(
        vault=vault, effective_datetime=effective_datetime
    )

    # Maintenance fee is a tier parameter driven by an account-level flag
    monthly_maintenance_fee_tiers = _get_monthly_maintenance_fee_tiers(
        vault=vault, effective_datetime=effective_datetime
    )

    tier = account_tiers.get_account_tier(vault)

    maintenance_fee_monthly = Decimal(
        account_tiers.get_tiered_parameter_value_based_on_account_tier(
            tiered_parameter=monthly_maintenance_fee_tiers,
            tier=tier,
            convert=Decimal,
        )
        or 0
    )

    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(
            vault=vault, effective_datetime=effective_datetime
        )

    fee_custom_instructions = fees.fee_custom_instruction(
        customer_account_id=vault.account_id,
        denomination=denomination,
        amount=maintenance_fee_monthly,
        internal_account=maintenance_fee_income_account,
        instruction_details={
            "description": "Monthly maintenance fee",
            "event": APPLY_MONTHLY_FEE_EVENT,
        },
    )

    if (
        _are_monthly_partial_payments_enabled(vault=vault, effective_datetime=effective_datetime)
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


def apply_annual_fee(
    *, vault: SmartContractVault, effective_datetime: datetime
) -> list[CustomInstruction]:
    """
    Gets annual maintenance fees and the account where it will be credited.
    :param vault: Vault object for the account getting the fee assessed
    :return: Custom instructions to generate posting for annual maintenance fees
    """
    annual_maintenance_fee_income_account = _get_annual_internal_income_account(
        vault=vault, effective_datetime=effective_datetime
    )

    # Maintenance fee is a tier parameter driven by an account-level flag
    annual_maintenance_fee_tiers = _get_annual_maintenance_fee_tiers(
        vault=vault, effective_datetime=effective_datetime
    )

    tier = account_tiers.get_account_tier(vault)

    maintenance_fee_annual = Decimal(
        account_tiers.get_tiered_parameter_value_based_on_account_tier(
            tiered_parameter=annual_maintenance_fee_tiers,
            tier=tier,
            convert=Decimal,
        )
        or 0
    )
    denomination = common_parameters.get_denomination_parameter(
        vault=vault, effective_datetime=effective_datetime
    )

    # fees.fee_custom_instruction returns one Custom instruction
    return fees.fee_custom_instruction(
        customer_account_id=vault.account_id,
        denomination=denomination,
        amount=maintenance_fee_annual,
        internal_account=annual_maintenance_fee_income_account,
        instruction_details={
            "description": "Annual maintenance fee",
            "event": APPLY_ANNUAL_FEE_EVENT,
        },
    )


def update_next_annual_schedule_execution(
    *, vault: SmartContractVault, effective_datetime: datetime
) -> Optional[UpdateAccountEventTypeDirective]:
    """
    Update next annual scheduled execution with intended month not february

    :param vault: Vault object to retrieve interest application params
    :param effective_datetime: datetime the schedule is running
    :return: optional update event directive
    """

    schedule_day = int(utils.get_parameter(vault, name=PARAM_MAINTENANCE_FEE_APPLICATION_DAY))
    # no need to reschedule if annual frequency and application month not february or
    # schedule day < 29 since there's no leap year logic to adapt
    if int(effective_datetime.month) != 2 or (
        int(effective_datetime.month) == 2 and schedule_day < 29
    ):
        return None

    new_schedule = scheduled_events(
        vault=vault, start_datetime=effective_datetime, frequency=ANNUALLY
    )

    return UpdateAccountEventTypeDirective(
        event_type=APPLY_ANNUAL_FEE_EVENT,
        expression=new_schedule[APPLY_ANNUAL_FEE_EVENT].expression,
    )


def _get_monthly_internal_income_account(
    *, vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> str:
    return utils.get_parameter(
        vault=vault,
        name=PARAM_MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT,
        at_datetime=effective_datetime,
    )


def _get_monthly_maintenance_fee_tiers(
    vault: SmartContractVault, effective_datetime: Optional[datetime]
) -> dict[str, str]:
    return utils.get_parameter(
        vault=vault,
        name=PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER,
        at_datetime=effective_datetime,
        is_json=True,
    )


def _get_annual_internal_income_account(
    *, vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> str:
    return utils.get_parameter(
        vault=vault,
        name=PARAM_ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT,
        at_datetime=effective_datetime,
    )


def _get_annual_maintenance_fee_tiers(
    vault: SmartContractVault, effective_datetime: Optional[datetime]
) -> dict[str, str]:
    return utils.get_parameter(
        vault=vault,
        name=PARAM_ANNUAL_MAINTENANCE_FEE_BY_TIER,
        at_datetime=effective_datetime,
        is_json=True,
    )


def _are_monthly_partial_payments_enabled(
    *, vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> bool:
    return utils.get_parameter(
        vault=vault,
        name=PARAM_MONTHLY_MAINTENANCE_FEE_PARTIAL_FEE_ENABLED,
        at_datetime=effective_datetime,
        is_boolean=True,
        is_optional=True,
        default_value=False,
    )


PARTIAL_FEE_DETAILS = deposit_interfaces.PartialFeeCollection(
    outstanding_fee_address=OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER,
    fee_type="Partial Monthly Maintenance Fee",
    get_internal_account_parameter=_get_monthly_internal_income_account,
)
