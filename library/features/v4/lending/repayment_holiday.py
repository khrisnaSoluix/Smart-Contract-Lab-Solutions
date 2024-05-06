# standard libs
from datetime import datetime
from json import dumps
from typing import Optional, Union

# features
import library.features.v4.common.utils as utils
import library.features.v4.lending.lending_interfaces as lending_interfaces

# contracts api
from contracts_api import (
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    Rejection,
    RejectionReason,
    StringShape,
    UnionItem,
    UnionItemValue,
    UnionShape,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import (
    SmartContractVault,
    SuperviseeContractVault,
)

# constants
INCREASE_EMI = "increase_emi"
INCREASE_TERM = "increase_term"
REPAYMENT_HOLIDAY = "REPAYMENT_HOLIDAY"

# parameter names
PARAM_DELINQUENCY_BLOCKING_FLAGS = "delinquency_blocking_flags"
PARAM_DUE_AMOUNT_CALCULATION_BLOCKING_FLAGS = "due_amount_calculation_blocking_flags"
PARAM_INTEREST_ACCRUAL_BLOCKING_FLAGS = "interest_accrual_blocking_flags"
PARAM_NOTIFICATION_BLOCKING_FLAGS = "notification_blocking_flags"
PARAM_OVERDUE_AMOUNT_CALCULATION_BLOCKING_FLAGS = "overdue_amount_calculation_blocking_flags"
PARAM_PENALTY_BLOCKING_FLAGS = "penalty_blocking_flags"
PARAM_REPAYMENT_BLOCKING_FLAGS = "repayment_blocking_flags"
PARAM_REPAYMENT_HOLIDAY_IMPACT_PREFERENCE = "repayment_holiday_impact_preference"


delinquency_blocking_param = Parameter(
    name=PARAM_DELINQUENCY_BLOCKING_FLAGS,
    shape=StringShape(),
    level=ParameterLevel.TEMPLATE,
    description="The list of flag definitions that block an account becoming delinquent. "
    "Expects a string representation of a JSON list.",
    display_name="Delinquency Blocking Flags",
    default_value=dumps([REPAYMENT_HOLIDAY]),
)
due_amount_calculation_blocking_param = Parameter(
    name=PARAM_DUE_AMOUNT_CALCULATION_BLOCKING_FLAGS,
    shape=StringShape(),
    level=ParameterLevel.TEMPLATE,
    description="The list of flag definitions that block due amount calculation. "
    "Expects a string representation of a JSON list.",
    display_name="Due Amount Calculation Blocking Flags",
    default_value=dumps([REPAYMENT_HOLIDAY]),
)
interest_accrual_blocking_param = Parameter(
    name=PARAM_INTEREST_ACCRUAL_BLOCKING_FLAGS,
    shape=StringShape(),
    level=ParameterLevel.TEMPLATE,
    description="The list of flag definitions that block interest accruals. "
    "Expects a string representation of a JSON list.",
    display_name="Interest Accrual Blocking Flags",
    default_value=dumps([REPAYMENT_HOLIDAY]),
)
notification_blocking_param = Parameter(
    name=PARAM_NOTIFICATION_BLOCKING_FLAGS,
    shape=StringShape(),
    level=ParameterLevel.TEMPLATE,
    description="The list of flag definitions that block notifications. "
    "Expects a string representation of a JSON list.",
    display_name="Notification Blocking Flags",
    default_value=dumps([REPAYMENT_HOLIDAY]),
)
overdue_amount_calculation_blocking_param = Parameter(
    name=PARAM_OVERDUE_AMOUNT_CALCULATION_BLOCKING_FLAGS,
    shape=StringShape(),
    level=ParameterLevel.TEMPLATE,
    description="The list of flag definitions that block overdue amount calculation. "
    "Expects a string representation of a JSON list.",
    display_name="Overdue Amount Calculation Blocking Flags",
    default_value=dumps([REPAYMENT_HOLIDAY]),
)
penalty_blocking_param = Parameter(
    name=PARAM_PENALTY_BLOCKING_FLAGS,
    shape=StringShape(),
    level=ParameterLevel.TEMPLATE,
    description="The list of flag definitions that block penalty interest accrual. "
    "Expects a string representation of a JSON list.",
    display_name="Penalty Blocking Flags",
    default_value=dumps([REPAYMENT_HOLIDAY]),
)
repayment_blocking_param = Parameter(
    name=PARAM_REPAYMENT_BLOCKING_FLAGS,
    shape=StringShape(),
    level=ParameterLevel.TEMPLATE,
    description="The list of flag definitions that block repayments. "
    "Expects a string representation of a JSON list.",
    display_name="Repayment Blocking Flag",
    default_value=dumps([REPAYMENT_HOLIDAY]),
)
repayment_holiday_impact_preference_param = Parameter(
    name=PARAM_REPAYMENT_HOLIDAY_IMPACT_PREFERENCE,
    shape=UnionShape(
        items=[
            UnionItem(key=INCREASE_TERM, display_name="Increase Term"),
            UnionItem(key=INCREASE_EMI, display_name="Increase EMI"),
        ]
    ),
    level=ParameterLevel.INSTANCE,
    description="Defines how to handle a repayment holiday: "
    "Increase EMI but keep the term of the loan the same. "
    "Increase term but keep the monthly repayments the same. ",
    display_name="Repayment Holiday Impact Preference",
    update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    default_value=UnionItemValue(key="increase_emi"),
)


all_parameters_including_preference = [
    delinquency_blocking_param,
    due_amount_calculation_blocking_param,
    interest_accrual_blocking_param,
    notification_blocking_param,
    overdue_amount_calculation_blocking_param,
    penalty_blocking_param,
    repayment_blocking_param,
    repayment_holiday_impact_preference_param,
]

all_parameters_excluding_preference = [
    delinquency_blocking_param,
    due_amount_calculation_blocking_param,
    interest_accrual_blocking_param,
    notification_blocking_param,
    overdue_amount_calculation_blocking_param,
    penalty_blocking_param,
    repayment_blocking_param,
]


# blocking flag helpers
def are_notifications_blocked(
    vault: SmartContractVault,
    effective_datetime: datetime,
) -> bool:
    return utils.is_flag_in_list_applied(
        vault=vault,
        parameter_name=PARAM_NOTIFICATION_BLOCKING_FLAGS,
        effective_datetime=effective_datetime,
    )


def is_delinquency_blocked(vault: SmartContractVault, effective_datetime: datetime) -> bool:
    return utils.is_flag_in_list_applied(
        vault=vault,
        parameter_name=PARAM_DELINQUENCY_BLOCKING_FLAGS,
        effective_datetime=effective_datetime,
    )


def is_due_amount_calculation_blocked(
    vault: SmartContractVault,
    effective_datetime: datetime,
) -> bool:
    return utils.is_flag_in_list_applied(
        vault=vault,
        parameter_name=PARAM_DUE_AMOUNT_CALCULATION_BLOCKING_FLAGS,
        effective_datetime=effective_datetime,
    )


def is_interest_accrual_blocked(vault: SmartContractVault, effective_datetime: datetime) -> bool:
    return utils.is_flag_in_list_applied(
        vault=vault,
        parameter_name=PARAM_INTEREST_ACCRUAL_BLOCKING_FLAGS,
        effective_datetime=effective_datetime,
    )


def is_overdue_amount_calculation_blocked(
    vault: SmartContractVault,
    effective_datetime: datetime,
) -> bool:
    return utils.is_flag_in_list_applied(
        vault=vault,
        parameter_name=PARAM_OVERDUE_AMOUNT_CALCULATION_BLOCKING_FLAGS,
        effective_datetime=effective_datetime,
    )


def is_penalty_accrual_blocked(vault: SmartContractVault, effective_datetime: datetime) -> bool:
    return utils.is_flag_in_list_applied(
        vault=vault,
        parameter_name=PARAM_PENALTY_BLOCKING_FLAGS,
        effective_datetime=effective_datetime,
    )


def is_repayment_blocked(vault: SmartContractVault, effective_datetime: datetime) -> bool:
    return utils.is_flag_in_list_applied(
        vault=vault,
        parameter_name=PARAM_REPAYMENT_BLOCKING_FLAGS,
        effective_datetime=effective_datetime,
    )


def reject_repayment(
    vault: SmartContractVault, effective_datetime: datetime
) -> Optional[Rejection]:
    return (
        Rejection(
            message="Repayments are blocked for this account.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        if is_repayment_blocked(vault=vault, effective_datetime=effective_datetime)
        else None
    )


def should_trigger_reamortisation_no_impact_preference(
    vault: SmartContractVault,
    period_start_datetime: datetime,
    period_end_datetime: datetime,
    elapsed_term: Optional[int] = None,
) -> bool:
    """
    Determines whether to trigger reamortisation due to a repayment holiday ending.
    Only returns True if a repayment holiday was active at period start datetime
    and no longer is as of period end datetime the repayment holiday impact preference is not
    considered, useful for loans which mandate a repayment holiday increasing emi and therefore do
    not define the parameter.

    :param vault: vault object for the account
    :param period_start_datetime: datetime of the period start, typically this will be the datetime
    of the previous due amount calculation. This is intentionally not an Optional[] argument since
    period_start_datetime=None would result in comparing the monthly interest rate between latest()
    and period_end_datetime.
    :param period_end_datetime: datetime of the period end, typically the effective_datetime of the
    current due amount calculation event
    :param elapsed_term: Not used but required for the interface
    :return bool: Whether reamortisation is required
    """
    return _has_repayment_holiday_ended(
        vault=vault,
        period_start_datetime=period_start_datetime,
        period_end_datetime=period_end_datetime,
    )


def should_trigger_reamortisation_with_impact_preference(
    vault: SmartContractVault,
    period_start_datetime: datetime,
    period_end_datetime: datetime,
    elapsed_term: Optional[int] = None,
) -> bool:
    """
    Determines whether to trigger reamortisation due to a repayment holiday ending.
    Only returns True if a repayment holiday was active at period start datetime
    and no longer is as of period end datetime and the repayment holiday impact preference to
    increase emi

    :param vault: vault object for the account
    :param period_start_datetime: datetime of the period start, typically this will be the datetime
    of the previous due amount calculation. This is intentionally not an Optional[] argument since
    period_start_datetime=None would result in comparing the monthly interest rate between latest()
    and period_end_datetime.
    :param period_end_datetime: datetime of the period end, typically the effective_datetime of the
    current due amount calculation event
    :param elapsed_term: Not used but required for the interface
    :return bool: Whether reamortisation is required
    """
    return is_repayment_holiday_impact_increase_emi(
        vault=vault, effective_datetime=period_end_datetime
    ) and _has_repayment_holiday_ended(
        vault=vault,
        period_start_datetime=period_start_datetime,
        period_end_datetime=period_end_datetime,
    )


def supervisor_should_trigger_reamortisation_no_impact_preference(
    loan_vault: SuperviseeContractVault,
    main_vault: SuperviseeContractVault,
    period_start_datetime: datetime,
    period_end_datetime: datetime,
    elapsed_term: Optional[int] = None,
) -> bool:
    """
    Determines whether to trigger reamortisation due to a repayment holiday ending.
    Only returns True if a repayment holiday was active at period start datetime
    and no longer is as of period end datetime the repayment holiday impact preference is not
    considered, useful for loans which mandate a repayment holiday increasing emi and therefore do
    not define the parameter.

    :param vault: Not used but required for the interface
    :param main_vault: supervisee vault object that stores flag timeseries
    :param period_start_datetime: datetime of the period start, typically this will be the datetime
    of the previous due amount calculation. This is intentionally not an Optional[] argument since
    period_start_datetime=None would result in comparing the monthly interest rate between latest()
    and period_end_datetime.
    :param period_end_datetime: datetime of the period end, typically the effective_datetime of the
    current due amount calculation event
    :param elapsed_term: Not used but required for the interface
    :return bool: Whether reamortisation is required
    """
    return _has_repayment_holiday_ended(
        vault=main_vault,
        period_start_datetime=period_start_datetime,
        period_end_datetime=period_end_datetime,
    )


def is_repayment_holiday_impact_increase_emi(
    vault: SmartContractVault, effective_datetime: datetime
) -> bool:
    return (
        utils.get_parameter(
            vault=vault,
            name=PARAM_REPAYMENT_HOLIDAY_IMPACT_PREFERENCE,
            at_datetime=effective_datetime,
            is_union=True,
        ).lower()
        == INCREASE_EMI
    )


def _has_repayment_holiday_ended(
    vault: Union[SmartContractVault, SuperviseeContractVault],
    period_start_datetime: datetime,
    period_end_datetime: datetime,
) -> bool:
    return is_due_amount_calculation_blocked(
        vault=vault,
        effective_datetime=period_start_datetime,
    ) and not is_due_amount_calculation_blocked(
        vault=vault,
        effective_datetime=period_end_datetime,
    )


ReamortisationConditionWithoutPreference = lending_interfaces.ReamortisationCondition(
    should_trigger_reamortisation=should_trigger_reamortisation_no_impact_preference,
)
ReamortisationConditionWithPreference = lending_interfaces.ReamortisationCondition(
    should_trigger_reamortisation=should_trigger_reamortisation_with_impact_preference,
)
SupervisorReamortisationConditionWithoutPreference = (
    lending_interfaces.SupervisorReamortisationCondition(
        should_trigger_reamortisation=supervisor_should_trigger_reamortisation_no_impact_preference,
    )
)
