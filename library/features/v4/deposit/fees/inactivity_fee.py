# CBF: Inactivity and Inactivity Fee

# standard libs
from datetime import datetime
from decimal import Decimal
from json import dumps
from typing import Optional

# features
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

APPLICATION_EVENT = "APPLY_INACTIVITY_FEE"
# Addresses
OUTSTANDING_INACTIVITY_FEE_TRACKER = "outstanding_inactivity_fee_tracker"

# Parameters
PARAM_INACTIVITY_FLAGS = "inactivity_flags"
PARAM_INACTIVITY_FEE = "inactivity_fee"
PARAM_INACTIVITY_FEE_INCOME_ACCOUNT = "inactivity_fee_income_account"
PARAM_INACTIVITY_FEE_PARTIAL_FEE_ENABLED = "partial_inactivity_fee_enabled"

inactivity_flags_parameter = Parameter(
    name=PARAM_INACTIVITY_FLAGS,
    shape=StringShape(),
    level=ParameterLevel.TEMPLATE,
    description="The list of flag definitions that indicate an account is inactive. "
    "Inactive accounts may incur an inactivity fee. "
    "Expects a string representation of a JSON list.",
    display_name="Inactivity Flags",
    default_value=dumps(["ACCOUNT_INACTIVE"]),
)
fee_parameters = [
    Parameter(
        name=PARAM_INACTIVITY_FEE,
        level=ParameterLevel.TEMPLATE,
        description="The monthly fee charged for inactivity on an account.",
        display_name="Monthly Inactivity Fee",
        shape=NumberShape(min_value=0, step=Decimal("0.01")),
        default_value=Decimal("0.00"),
    ),
    Parameter(
        name=PARAM_INACTIVITY_FEE_INCOME_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for inactivity fee income balance.",
        display_name="Inactivity Fee Income Account",
        shape=AccountIdShape(),
        default_value="INACTIVITY_FEE_INCOME",
    ),
    Parameter(
        name=PARAM_INACTIVITY_FEE_PARTIAL_FEE_ENABLED,
        shape=OptionalShape(shape=common_parameters.BooleanShape),
        level=ParameterLevel.TEMPLATE,
        description="Toggles partial payments for inactivity fee",
        display_name="Inactivity Partial Fees Enabled",
        default_value=OptionalValue(common_parameters.BooleanValueFalse),
    ),
]

INACTIVITY_FEE_APPLICATION_PREFIX = "inactivity_fee_application"
PARAM_INACTIVITY_FEE_APPLICATION_DAY = f"{INACTIVITY_FEE_APPLICATION_PREFIX}_day"
PARAM_INACTIVITY_FEE_APPLICATION_HOUR = f"{INACTIVITY_FEE_APPLICATION_PREFIX}_hour"
PARAM_INACTIVITY_FEE_APPLICATION_MINUTE = f"{INACTIVITY_FEE_APPLICATION_PREFIX}_minute"
PARAM_INACTIVITY_FEE_APPLICATION_SECOND = f"{INACTIVITY_FEE_APPLICATION_PREFIX}_second"
schedule_parameters = [
    Parameter(
        name=PARAM_INACTIVITY_FEE_APPLICATION_DAY,
        shape=NumberShape(min_value=1, max_value=31, step=1),
        level=ParameterLevel.INSTANCE,
        description="The day of the month on which inactivity fee is applied. If day does not exist"
        " in application month, applies on last day of month.",
        display_name="Inactivity Fee Application Day",
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
        default_value=1,
    ),
    Parameter(
        name=PARAM_INACTIVITY_FEE_APPLICATION_HOUR,
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which inactivity fee is applied.",
        display_name="Inactivity Fee Application Hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_INACTIVITY_FEE_APPLICATION_MINUTE,
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which inactivity fee is applied.",
        display_name="Inactivity Fee Application Minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_INACTIVITY_FEE_APPLICATION_SECOND,
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which inactivity fee is applied.",
        display_name="Inactivity Fee Application Second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=1,
    ),
]

parameters = [*fee_parameters, *schedule_parameters, inactivity_flags_parameter]


def get_inactivity_fee_amount(
    vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> Decimal:
    return Decimal(
        utils.get_parameter(vault=vault, name=PARAM_INACTIVITY_FEE, at_datetime=effective_datetime)
    )


def _get_inactivity_internal_income_account(
    vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> str:
    return utils.get_parameter(
        vault=vault,
        name=PARAM_INACTIVITY_FEE_INCOME_ACCOUNT,
        at_datetime=effective_datetime,
    )


def _are_inactivity_partial_payments_enabled(
    vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> bool:
    return utils.get_parameter(
        vault=vault,
        name=PARAM_INACTIVITY_FEE_PARTIAL_FEE_ENABLED,
        is_boolean=True,
        is_optional=True,
        default_value=False,
        at_datetime=effective_datetime,
    )


def event_types(product_name: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=APPLICATION_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{APPLICATION_EVENT}_AST"],
        )
    ]


def scheduled_events(
    *, vault: SmartContractVault, start_datetime: datetime
) -> dict[str, ScheduledEvent]:
    """
    Creates monthly scheduled event for inactivity fee application
    :param vault: Vault object to retrieve application frequency and schedule params
    :param start_datetime: date to start schedules from e.g. account creation
    :return: dict of inactivity fee application scheduled events
    """
    scheduled_event = utils.monthly_scheduled_event(
        vault=vault,
        start_datetime=start_datetime,
        parameter_prefix=INACTIVITY_FEE_APPLICATION_PREFIX,
    )
    return {APPLICATION_EVENT: scheduled_event}


def apply(
    vault: SmartContractVault,
    effective_datetime: datetime,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
    available_balance_feature: Optional[deposit_interfaces.AvailableBalance] = None,
) -> list[CustomInstruction]:
    """
    Gets inactivity fees to apply on the account.

    :param vault: vault object of the account whose fee is being assessed
    :param effective_datetime: date and time of hook being run
    :param denomination: the denomination of the paper statement fee, if not provided the
    'denomination' parameter is retrieved
    :param balances: Account balances, if not provided balances will be retrieved using the
    EFFECTIVE_OBSERVATION_FETCHER
    :param available_balance_feature: Interface to calculate the available balance for the account
    using a custom definition
    :return: Custom Instruction to apply the inactivity fee
    """
    inactivity_fee_amount = get_inactivity_fee_amount(
        vault=vault, effective_datetime=effective_datetime
    )
    posting_instructions: list[CustomInstruction] = []

    if Decimal(inactivity_fee_amount) > 0:
        inactivity_fee_income_account = _get_inactivity_internal_income_account(vault=vault)
        if denomination is None:
            denomination = common_parameters.get_denomination_parameter(vault=vault)

        fee_instructions = fees.fee_custom_instruction(
            customer_account_id=vault.account_id,
            denomination=denomination,
            amount=inactivity_fee_amount,
            internal_account=inactivity_fee_income_account,
            instruction_details={
                "description": "Monthly Inactivity Fee Application",
                "event": APPLICATION_EVENT,
            },
        )

        if (
            _are_inactivity_partial_payments_enabled(
                vault=vault, effective_datetime=effective_datetime
            )
            and fee_instructions
        ):
            if balances is None:
                balances = vault.get_balances_observation(
                    fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
                ).balances
            posting_instructions.extend(
                partial_fee.charge_partial_fee(
                    vault=vault,
                    effective_datetime=effective_datetime,
                    fee_custom_instruction=fee_instructions[0],
                    fee_details=PARTIAL_FEE_DETAILS,
                    balances=balances,
                    denomination=denomination,
                    available_balance_feature=available_balance_feature,
                )
            )
        else:
            posting_instructions.extend(fee_instructions)

    return posting_instructions


def is_account_inactive(vault: SmartContractVault, effective_datetime: datetime) -> bool:
    return utils.is_flag_in_list_applied(
        vault=vault,
        parameter_name=PARAM_INACTIVITY_FLAGS,
        effective_datetime=effective_datetime,
    )


PARTIAL_FEE_DETAILS = deposit_interfaces.PartialFeeCollection(
    outstanding_fee_address=OUTSTANDING_INACTIVITY_FEE_TRACKER,
    fee_type="Partial Inactivity Fee",
    get_internal_account_parameter=_get_inactivity_internal_income_account,
)
