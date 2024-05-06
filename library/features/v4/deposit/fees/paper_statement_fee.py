# CBF: Paper Statement Fee

# standard libs
from datetime import datetime
from decimal import Decimal
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
    ScheduleFailover,
    SmartContractEventType,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

APPLICATION_EVENT = "APPLY_PAPER_STATEMENT_FEE"
PAPER_STATEMENT_FEE_PREFIX = "paper_statement_fee"

# Addresses
OUTSTANDING_MONTHLY_PAPER_STATEMENT_FEE_TRACKER = "outstanding_monthly_paper_statement_fee_tracker"


# Parameters
PARAM_PAPER_STATEMENT_FEE_RATE = f"{PAPER_STATEMENT_FEE_PREFIX}_rate"
PARAM_PAPER_STATEMENT_FEE_DAY = f"{PAPER_STATEMENT_FEE_PREFIX}_day"
PARAM_PAPER_STATEMENT_FEE_HOUR = f"{PAPER_STATEMENT_FEE_PREFIX}_hour"
PARAM_PAPER_STATEMENT_FEE_MINUTE = f"{PAPER_STATEMENT_FEE_PREFIX}_minute"
PARAM_PAPER_STATEMENT_FEE_SECOND = f"{PAPER_STATEMENT_FEE_PREFIX}_second"
PARAM_PAPER_STATEMENT_FEE_INCOME_ACCOUNT = f"{PAPER_STATEMENT_FEE_PREFIX}_income_account"
PARAM_PAPER_STATEMENT_FEE_ENABLED = f"{PAPER_STATEMENT_FEE_PREFIX}_enabled"
PARAM_PAPER_STATEMENT_FEE_PARTIAL_FEE_ENABLED = f"partial_{PAPER_STATEMENT_FEE_PREFIX}_enabled"


parameters = [
    Parameter(
        name=PARAM_PAPER_STATEMENT_FEE_DAY,
        level=ParameterLevel.INSTANCE,
        description="They day of the month on which the paper statement fee is applied."
        "If day does not exist in application month, applies on the first day of the next month.",
        display_name="Paper Statement Fee Application Day",
        shape=NumberShape(min_value=1, max_value=31, step=1),
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
        default_value=1,
    ),
    Parameter(
        name=PARAM_PAPER_STATEMENT_FEE_ENABLED,
        shape=common_parameters.BooleanShape,
        level=ParameterLevel.INSTANCE,
        description="Enables / Disables the Monthly Paper Statement Fee.",
        display_name="Paper Statement Fee Enabled",
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
        default_value=common_parameters.BooleanValueTrue,
    ),
    Parameter(
        name=PARAM_PAPER_STATEMENT_FEE_PARTIAL_FEE_ENABLED,
        shape=OptionalShape(shape=common_parameters.BooleanShape),
        level=ParameterLevel.TEMPLATE,
        description="Enables / Disables partial payments for the Paper Statement Fee.",
        display_name="Partial Paper Statement Fees Enabled",
        default_value=OptionalValue(common_parameters.BooleanValueFalse),
    ),
    Parameter(
        name=PARAM_PAPER_STATEMENT_FEE_RATE,
        level=ParameterLevel.TEMPLATE,
        description="The monthly fee for paper statements on an account.",
        display_name="Paper Statements Rate",
        shape=NumberShape(min_value=0, step=Decimal("0.01")),
        default_value=Decimal("0.00"),
    ),
    Parameter(
        name=PARAM_PAPER_STATEMENT_FEE_INCOME_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for paper statement fee income balance.",
        display_name="Paper Statement Fee Income Account",
        shape=AccountIdShape(),
        default_value="PAPER_STATEMENT_FEE_INCOME",
    ),
    Parameter(
        name=PARAM_PAPER_STATEMENT_FEE_HOUR,
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which the paper statement fee is applied.",
        display_name="Paper Statement Fee Application Hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_PAPER_STATEMENT_FEE_MINUTE,
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which the paper statement fee is applied.",
        display_name="Paper Statement Fee Application Minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_PAPER_STATEMENT_FEE_SECOND,
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which the paper statement fee is applied.",
        display_name="Paper Statement Fee Application Second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=1,
    ),
]


def get_paper_statement_fee_day(
    vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> int:
    return int(
        utils.get_parameter(
            vault=vault, name=PARAM_PAPER_STATEMENT_FEE_DAY, at_datetime=effective_datetime
        )
    )


def get_paper_statement_fee_rate(
    vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> Decimal:
    return Decimal(
        utils.get_parameter(
            vault=vault, name=PARAM_PAPER_STATEMENT_FEE_RATE, at_datetime=effective_datetime
        )
    )


def get_paper_statement_fee_income_account(
    vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> str:
    return str(
        utils.get_parameter(
            vault=vault,
            name=PARAM_PAPER_STATEMENT_FEE_INCOME_ACCOUNT,
            at_datetime=effective_datetime,
        )
    )


def is_paper_statement_fee_enabled(
    vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> bool:
    return utils.get_parameter(
        vault=vault,
        name=PARAM_PAPER_STATEMENT_FEE_ENABLED,
        is_boolean=True,
        at_datetime=effective_datetime,
    )


# Fee Details
PARTIAL_FEE_DETAILS = deposit_interfaces.PartialFeeCollection(
    outstanding_fee_address=OUTSTANDING_MONTHLY_PAPER_STATEMENT_FEE_TRACKER,
    fee_type="Partial Paper Statement Fee",
    get_internal_account_parameter=get_paper_statement_fee_income_account,
)


def are_partial_payments_enabled(
    *, vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> bool:
    return utils.get_parameter(
        vault=vault,
        name=PARAM_PAPER_STATEMENT_FEE_PARTIAL_FEE_ENABLED,
        at_datetime=effective_datetime,
        is_boolean=True,
        default_value=False,
        is_optional=True,
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
    Creates scheduled event for paper statement fee application
    :param vault: Vault object to schedule params
    :param start_datetime: date to start schedules from e.g. account creation or loan start date
    :return: dict of paper statement fee application scheduled events
    """
    schedule_day = get_paper_statement_fee_day(vault=vault)

    scheduled_event = utils.monthly_scheduled_event(
        vault=vault,
        start_datetime=start_datetime,
        day=schedule_day,
        parameter_prefix=PAPER_STATEMENT_FEE_PREFIX,
        failover=ScheduleFailover.FIRST_VALID_DAY_AFTER,
    )
    return {APPLICATION_EVENT: scheduled_event}


def apply(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
    available_balance_feature: Optional[deposit_interfaces.AvailableBalance] = None,
) -> list[CustomInstruction]:
    """
    Retrieves the paper statement fee, paper statement fee income account.

    :param vault: vault object of the account whose fee is being assessed
    :param effective_datetime: date and time of hook being run
    :param denomination: the denomination of the paper statement fee, if not provided the
    'denomination' parameter is retrieved
    :param balances: Account balances, if not provided balances will be retrieved using the
    EFFECTIVE_OBSERVATION_FETCHER
    :param available_balance_feature: Interface to calculate the available balance for the account
    using a custom definition
    :return: Custom Instruction to apply the paper statement fee
    """

    fee_custom_instructions: list[CustomInstruction] = []

    # If paper statement fee is enabled, apply it
    if is_paper_statement_fee_enabled(vault=vault):
        paper_statement_fee = get_paper_statement_fee_rate(vault=vault)
        if paper_statement_fee > Decimal("0"):
            paper_statement_fee_income_account = get_paper_statement_fee_income_account(vault=vault)
            if denomination is None:
                denomination = common_parameters.get_denomination_parameter(vault=vault)
            fee_custom_instructions = fees.fee_custom_instruction(
                customer_account_id=vault.account_id,
                denomination=denomination,
                amount=paper_statement_fee,
                internal_account=paper_statement_fee_income_account,
                instruction_details={
                    "description": "Monthly Paper Statement Fee Application",
                    "event": APPLICATION_EVENT,
                },
            )
            # only need to check if partial payments are enabled here since fee_custom_instructions
            # will always be a non-empty list here
            if are_partial_payments_enabled(vault=vault, effective_datetime=effective_datetime):
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
            else:
                return fee_custom_instructions
    return []
