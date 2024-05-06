# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

# features
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.lending.emi as emi
import library.features.v4.lending.lending_addresses as lending_addresses
import library.features.v4.lending.lending_interfaces as lending_interfaces

# contracts api
from contracts_api import (
    DEFAULT_ASSET,
    BalanceCoordinate,
    BalanceDefaultDict,
    CustomInstruction,
    DateShape,
    NumberShape,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    Phase,
    Posting,
    Rejection,
    RejectionReason,
    ScheduledEvent,
    ScheduledEventHookArguments,
    SmartContractEventType,
    SupervisorContractEventType,
    SupervisorScheduledEventHookArguments,
    Tside,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import (
    SmartContractVault,
    SuperviseeContractVault,
)

DUE_AMOUNT_CALCULATION_EVENT = "DUE_AMOUNT_CALCULATION"
DUE_AMOUNT_CALCULATION_PREFIX = "due_amount_calculation"
PARAM_DUE_AMOUNT_CALCULATION_HOUR = f"{DUE_AMOUNT_CALCULATION_PREFIX}_hour"
PARAM_DUE_AMOUNT_CALCULATION_MINUTE = f"{DUE_AMOUNT_CALCULATION_PREFIX}_minute"
PARAM_DUE_AMOUNT_CALCULATION_SECOND = f"{DUE_AMOUNT_CALCULATION_PREFIX}_second"
PARAM_DUE_AMOUNT_CALCULATION_DAY = "due_amount_calculation_day"
PARAM_NEXT_REPAYMENT_DATE = "next_repayment_date"

due_amount_calculation_day_parameter = Parameter(
    name=PARAM_DUE_AMOUNT_CALCULATION_DAY,
    shape=NumberShape(min_value=1, max_value=31, step=1),
    level=ParameterLevel.INSTANCE,
    description="The day of the month that the monthly due amount calculations takes place on."
    " If the day isn't available in a given month, the previous available day is used instead",
    display_name="Due Amount Calculation Day",
    default_value=Decimal(28),
    update_permission=ParameterUpdatePermission.USER_EDITABLE,
)

next_repayment_date_parameter = Parameter(
    name=PARAM_NEXT_REPAYMENT_DATE,
    shape=DateShape(
        min_date=datetime.min.replace(tzinfo=ZoneInfo("UTC")),
        max_date=datetime.max.replace(tzinfo=ZoneInfo("UTC")),
    ),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Next scheduled repayment date",
    display_name="Next Repayment Date",
)

schedule_time_parameters = [
    Parameter(
        name=PARAM_DUE_AMOUNT_CALCULATION_HOUR,
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which due amounts are calculated.",
        display_name="Due Amount Calculation Hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_DUE_AMOUNT_CALCULATION_MINUTE,
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which due amounts are calculated.",
        display_name="Due Amount Calculation Minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_DUE_AMOUNT_CALCULATION_SECOND,
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which due amounts are calculated.",
        display_name="Due Amount Calculation Second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
]
schedule_parameters = [due_amount_calculation_day_parameter, *schedule_time_parameters]


def event_types(product_name: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=DUE_AMOUNT_CALCULATION_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{DUE_AMOUNT_CALCULATION_EVENT}_AST"],
        )
    ]


def supervisor_event_types(product_name: str) -> list[SupervisorContractEventType]:
    return [
        SupervisorContractEventType(
            name=DUE_AMOUNT_CALCULATION_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{DUE_AMOUNT_CALCULATION_EVENT}_AST"],
        )
    ]


# TODO use configurable_repayment_frequency.get_due_amount_calculation_schedule() instead of below
# TODO that will affect other products.
def scheduled_events(
    vault: SmartContractVault, account_opening_datetime: datetime
) -> dict[str, ScheduledEvent]:
    """
    Create monthly scheduled event for due amount calculation, starting one month from account
    opening
    :param vault: vault object for the account that requires the schedule
    :param account_opening_datetime: when the account is opened/activated
    :return: event type to scheduled event
    """
    return {
        DUE_AMOUNT_CALCULATION_EVENT: utils.monthly_scheduled_event(
            vault=vault,
            start_datetime=account_opening_datetime
            + relativedelta(hour=0, minute=0, second=0)
            + relativedelta(months=1),
            parameter_prefix=DUE_AMOUNT_CALCULATION_PREFIX,
        )
    }


def schedule_logic(
    vault: SmartContractVault,
    hook_arguments: ScheduledEventHookArguments,
    account_type: str,
    amortisation_feature: lending_interfaces.Amortisation,
    interest_application_feature: Optional[lending_interfaces.InterestApplication] = None,
    reamortisation_condition_features: Optional[
        list[lending_interfaces.ReamortisationCondition]
    ] = None,
    interest_rate_feature: Optional[lending_interfaces.InterestRate] = None,
    principal_adjustment_features: Optional[list[lending_interfaces.PrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Calculate due amounts and create CustomInstructions to effect any required balance updates
    :param vault: vault object for the account
    :param hook_arguments: the scheduled event's hook arguments
    :param account_type: the account type, used for GL posting metadata purposes
    :param amortisation_feature: feature responsible for recalculating the emi if
    reamortisation is required (determined by the reamortisation_condition_features), and
    determining term details
    :param interest_application_feature: feature that is responsible for applying interest
    as part of the due amount calculation. This can be omitted if no interest is charged for
    a product (e.g. a 0% interest Pay-In-X loan)
    :param reamortisation_condition_features: a list of features used to determine whether
    reamortisation is required
    :param interest_rate_feature: feature responsible for providing relevant interest information
    to the amortisation feature
    :param principal_adjustment_features: feature responsible for providing relevant principal
    adjustments to the amortisation feature
    :param balances: balances to use for due amount calculation. If not provided balances fetched
    as of effective datetime are used
    :param denomination: denomination to use for due amount calculation. If not provided, parameter
    values as of effective datetime are used
    :return: the custom instructions. Empty if none are required
    """
    postings: list[Posting] = []
    customer_account = vault.account_id
    effective_datetime = hook_arguments.effective_datetime

    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    if denomination is None:
        denomination = utils.get_parameter(vault=vault, name="denomination")

    current_principal = get_principal(balances=balances, denomination=denomination)

    # adjustments not passed in here because we use expected term
    elapsed_term, remaining_term = amortisation_feature.term_details(
        vault=vault,
        effective_datetime=effective_datetime,
        use_expected_term=True,
        interest_rate=interest_rate_feature,
        balances=balances,
    )

    last_execution_effective_datetime = (
        vault.get_account_creation_datetime()
        if elapsed_term == 0
        else vault.get_last_execution_datetime(event_type=DUE_AMOUNT_CALCULATION_EVENT)
    )

    if interest_application_feature is not None:
        interest_amounts = interest_application_feature.get_interest_to_apply(
            vault=vault,
            effective_datetime=effective_datetime,
            previous_application_datetime=last_execution_effective_datetime,
            balances_at_application=balances,
        )
        # This could arguably just be emi rounded, but for consistency with previous
        # behaviour we're sticking to total rounded - non emi rounded. This can cause subtle
        # differences due to round(a+b) != round(a)+round(b)
        emi_interest_to_apply = (
            interest_amounts.total_rounded - interest_amounts.non_emi_rounded_accrued
        )
        postings += interest_application_feature.apply_interest(
            vault=vault,
            effective_datetime=effective_datetime,
            previous_application_datetime=last_execution_effective_datetime,
            balances_at_application=balances,
        )
    else:
        emi_interest_to_apply = Decimal(0)

    requires_reamortisation = any(
        reamortisation_interface.should_trigger_reamortisation(
            vault=vault,
            period_start_datetime=last_execution_effective_datetime,
            period_end_datetime=effective_datetime,
            elapsed_term=elapsed_term,
        )
        for reamortisation_interface in reamortisation_condition_features or []
    )
    current_emi = get_emi(balances=balances, denomination=denomination)

    if requires_reamortisation:
        new_emi = amortisation_feature.calculate_emi(
            vault=vault,
            effective_datetime=effective_datetime,
            use_expected_term=True,
            principal_amount=current_principal,
            interest_calculation_feature=interest_rate_feature,
            principal_adjustments=principal_adjustment_features,
            balances=balances,
        )
        postings += emi.update_emi(
            account_id=vault.account_id,
            denomination=denomination,
            current_emi=current_emi,
            updated_emi=new_emi,
        )
    else:
        new_emi = current_emi

    return _calculate_due_amounts(
        current_principal=current_principal,
        emi_interest_to_apply=emi_interest_to_apply,
        new_emi=new_emi,
        remaining_term=remaining_term,
        override_final_event=amortisation_feature.override_final_event,
        customer_account=customer_account,
        denomination=denomination,
        event_type=hook_arguments.event_type,
        account_type=account_type,
        postings=postings,
    )


def supervisor_schedule_logic(
    loan_vault: SuperviseeContractVault,
    main_vault: SuperviseeContractVault,
    hook_arguments: SupervisorScheduledEventHookArguments,
    account_type: str,
    amortisation_feature: lending_interfaces.SupervisorAmortisation,
    interest_application_feature: Optional[lending_interfaces.InterestApplication] = None,
    reamortisation_condition_features: Optional[
        list[lending_interfaces.SupervisorReamortisationCondition]
    ] = None,
    interest_rate_feature: Optional[lending_interfaces.InterestRate] = None,
    principal_adjustment_features: Optional[
        list[lending_interfaces.SupervisorPrincipalAdjustment]
    ] = None,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Calculate due amounts and create CustomInstructions to affect any required balance updates
    :param loan_vault: vault object for the account that stores balances
    :param main_vault: supervisee vault object that some features are associated with
    :param hook_arguments: the scheduled event's hook arguments
    :param account_type: the account type, used for GL posting metadata purposes
    :param amortisation_feature: feature responsible for recalculating the emi if
    reamortisation is required (determined by the reamortisation_condition_features), and
    determining term details
    :param interest_application_feature: feature that is responsible for applying interest
    as part of the due amount calculation. This can be omitted if no interest is charged for
    a product (e.g. a 0% interest Pay-In-X loan)
    :param reamortisation_condition_features: a list of features used to determine whether
    reamortisation is required
    :param interest_rate_feature: feature responsible for providing relevant interest information
    to the amortisation feature
    :param principal_adjustment_features: feature responsible for providing relevant principal
    adjustments to the amortisation feature
    :param balances: balances to use for due amount calculation. If not provided balances fetched
    as of effective datetime are used
    :param denomination: denomination to use for due amount calculation. If not provided, parameter
    values as of effective datetime are used
    :return: the custom instructions. Empty if none are required
    """
    postings: list[Posting] = []
    customer_account = loan_vault.account_id
    effective_datetime = hook_arguments.effective_datetime

    if balances is None:
        balances_mapping = loan_vault.get_balances_timeseries()
        balances = utils.get_balance_default_dict_from_mapping(
            mapping=balances_mapping,
            effective_datetime=hook_arguments.effective_datetime,
        )
    if denomination is None:
        denomination = utils.get_parameter(vault=loan_vault, name="denomination")

    current_principal = get_principal(balances=balances, denomination=denomination)

    # adjustments not passed in here because we use expected term
    elapsed_term, remaining_term = amortisation_feature.term_details(
        loan_vault=loan_vault,
        main_vault=main_vault,
        effective_datetime=effective_datetime,
        use_expected_term=True,
        interest_rate=interest_rate_feature,
        balances=balances,
    )

    last_execution_effective_datetime = get_supervisee_last_execution_effective_datetime(
        loan_vault=loan_vault,
        main_vault=main_vault,
        event_type=DUE_AMOUNT_CALCULATION_EVENT,
        effective_datetime=effective_datetime,
        elapsed_term=elapsed_term,
    )

    if interest_application_feature is not None:
        interest_amounts = interest_application_feature.get_interest_to_apply(
            vault=loan_vault,
            effective_datetime=effective_datetime,
            previous_application_datetime=last_execution_effective_datetime,
            balances_at_application=balances,
        )
        # This could arguably just be emi rounded, but for consistency with previous
        # behaviour we're sticking to total rounded - non emi rounded. This can cause subtle
        # differences due to round(a+b) != round(a)+round(b)
        emi_interest_to_apply = (
            interest_amounts.total_rounded - interest_amounts.non_emi_rounded_accrued
        )
        postings += interest_application_feature.apply_interest(
            vault=loan_vault,
            effective_datetime=effective_datetime,
            previous_application_datetime=last_execution_effective_datetime,
            balances_at_application=balances,
        )
    else:
        emi_interest_to_apply = Decimal(0)

    requires_reamortisation = any(
        reamortisation_interface.should_trigger_reamortisation(
            loan_vault=loan_vault,
            main_vault=main_vault,
            period_start_datetime=last_execution_effective_datetime,
            period_end_datetime=effective_datetime,
            elapsed_term=elapsed_term,
        )
        for reamortisation_interface in reamortisation_condition_features or []
    )
    current_emi = get_emi(balances=balances, denomination=denomination)

    if requires_reamortisation:
        new_emi = amortisation_feature.calculate_emi(
            loan_vault=loan_vault,
            main_vault=main_vault,
            effective_datetime=effective_datetime,
            use_expected_term=True,
            principal_amount=current_principal,
            interest_calculation_feature=interest_rate_feature,
            principal_adjustments=principal_adjustment_features,
            balances=balances,
        )
        postings += emi.update_emi(
            account_id=loan_vault.account_id,
            denomination=denomination,
            current_emi=current_emi,
            updated_emi=new_emi,
        )
    else:
        new_emi = current_emi

    return _calculate_due_amounts(
        current_principal=current_principal,
        emi_interest_to_apply=emi_interest_to_apply,
        new_emi=new_emi,
        remaining_term=remaining_term,
        override_final_event=amortisation_feature.override_final_event,
        customer_account=customer_account,
        denomination=denomination,
        event_type=hook_arguments.event_type,
        account_type=account_type,
        postings=postings,
    )


def _calculate_due_amounts(
    current_principal: Decimal,
    emi_interest_to_apply: Decimal,
    new_emi: Decimal,
    remaining_term: int,
    override_final_event: bool,
    customer_account: str,
    denomination: str,
    event_type: str,
    account_type: str,
    postings: list[Posting],
) -> list[CustomInstruction]:
    """
    Calculate the due principal amounts from the supplied current principal, EMI interest and other
    parameters.
    :param current_principal: the current principal
    :param emi_interest_to_apply: the amount of interest to apply as a portion of the EMI
    :param new_emi: the new EMI value
    :param remaining_term: the remaining terms of the loan (total - elapsed)
    :param override_final_event: whether to override the due principal final event logic
    :param customer_account: the account where principal is due
    :param denomination: denomination to use for due amount calculation
    :param event_type: schedule event type
    :param account_type: the account type to be populated on posting instruction details
    :param postings: postings to include in the custom instruction
    :return: the due amount custom instructions
    """
    principal_due = calculate_due_principal(
        remaining_principal=current_principal,
        emi_interest_to_apply=emi_interest_to_apply,
        emi=new_emi,
        # remaining term will be calculated using principal at start of this hook execution, which
        # will therefore be 1 on the final due event (and 0 after completion of the hook execution)
        is_final_due_event=(remaining_term == 1 and not override_final_event),
    )

    postings += transfer_principal_due(
        customer_account=customer_account, principal_due=principal_due, denomination=denomination
    )
    postings += update_due_amount_calculation_counter(
        account_id=customer_account, denomination=denomination
    )
    if postings:
        return [
            CustomInstruction(
                postings=postings,
                override_all_restrictions=True,
                instruction_details=utils.standard_instruction_details(
                    description="Updating due balances",
                    event_type=event_type,
                    gl_impacted=True,
                    account_type=account_type,
                ),
            )
        ]
    else:
        return []


def transfer_principal_due(
    customer_account: str, principal_due: Decimal, denomination: str
) -> list[Posting]:
    """
    Create postings to transfer amount from principal to principal due address
    :param customer_account: the account where principal is due
    :param principal_due: the amount that is due
    :param denomination: the amount's denomination
    :return: the relevant postings. Empty if amount <= 0
    """

    if principal_due <= 0:
        return []

    return [
        Posting(
            credit=True,
            account_id=customer_account,
            amount=principal_due,
            account_address=lending_addresses.PRINCIPAL,
            asset=DEFAULT_ASSET,
            denomination=denomination,
            phase=Phase.COMMITTED,
        ),
        Posting(
            credit=False,
            account_id=customer_account,
            amount=principal_due,
            account_address=lending_addresses.PRINCIPAL_DUE,
            asset=DEFAULT_ASSET,
            denomination=denomination,
            phase=Phase.COMMITTED,
        ),
    ]


def calculate_due_principal(
    remaining_principal: Decimal,
    emi_interest_to_apply: Decimal,
    emi: Decimal,
    is_final_due_event: bool,
) -> Decimal:
    """
    Calculate due principal for a given repayment, ensuring it does not exceed remaining principal
    :param remaining_principal: Remaining principal at the point of the due amount calculation
    :param emi_interest_to_apply: emi portion of interest to apply for this repayment
    :param emi: emi for this repayment
    :return: the due principal for this repayment
    """
    # The EMI can be zero for certain types of loans so we need to safeguard against this
    if emi == Decimal("0"):
        return Decimal("0")

    # For the final due event all remaining principal becomes due
    if is_final_due_event:
        return remaining_principal

    # Although final due event scenario is handled above, this is based on expected remaining term,
    # so overpayment scenarios could still result in having emi - emi interest > principal
    return min(emi - emi_interest_to_apply, remaining_principal)


def update_due_amount_calculation_counter(account_id: str, denomination: str) -> list[Posting]:
    return utils.create_postings(
        amount=Decimal("1"),
        debit_account=account_id,
        debit_address=lending_addresses.DUE_CALCULATION_EVENT_COUNTER,
        credit_account=account_id,
        credit_address=lending_addresses.INTERNAL_CONTRA,
        denomination=denomination,
    )


def get_principal(balances: BalanceDefaultDict, denomination: str) -> Decimal:
    return balances[
        BalanceCoordinate(lending_addresses.PRINCIPAL, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net


def get_emi(balances: BalanceDefaultDict, denomination: str) -> Decimal:
    return balances[
        BalanceCoordinate(lending_addresses.EMI, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net


def validate_due_amount_calculation_day_change(vault: SmartContractVault) -> Optional[Rejection]:
    last_execution_datetime = vault.get_last_execution_datetime(
        event_type=DUE_AMOUNT_CALCULATION_EVENT
    )

    if last_execution_datetime is None:
        return Rejection(
            message=(
                "It is not possible to change the monthly repayment "
                "day if the first repayment date has not passed."
            ),
            reason_code=RejectionReason.AGAINST_TNC,
        )

    return None


def get_first_due_amount_calculation_datetime(vault: SmartContractVault) -> datetime:
    due_amount_calculation_day = int(
        utils.get_parameter(vault=vault, name=PARAM_DUE_AMOUNT_CALCULATION_DAY)
    )
    schedule_hour, schedule_minute, schedule_second = utils.get_schedule_time_from_parameters(
        vault=vault, parameter_prefix=DUE_AMOUNT_CALCULATION_PREFIX
    )
    account_creation_datetime = vault.get_account_creation_datetime()
    return _get_next_due_amount_calculation_datetime(
        start_datetime=account_creation_datetime,
        due_amount_calculation_day=due_amount_calculation_day,
        due_amount_calculation_hour=schedule_hour,
        due_amount_calculation_minute=schedule_minute,
        due_amount_calculation_second=schedule_second,
        effective_datetime=account_creation_datetime,
        last_execution_datetime=None,
    )


def get_residual_cleanup_postings(
    balances: BalanceDefaultDict, account_id: str, denomination: str
) -> list[Posting]:
    return utils.reset_tracker_balances(
        balances=balances,  # type: ignore
        account_id=account_id,
        tracker_addresses=[
            lending_addresses.DUE_CALCULATION_EVENT_COUNTER,
        ],
        contra_address=lending_addresses.INTERNAL_CONTRA,
        denomination=denomination,
        tside=Tside.ASSET,
    )


DueAmountCalculationResidualCleanupFeature = lending_interfaces.ResidualCleanup(
    get_residual_cleanup_postings=get_residual_cleanup_postings,
)


def get_actual_next_repayment_date(
    vault: SmartContractVault,
    effective_datetime: datetime,
    elapsed_term: int,
    remaining_term: int,
) -> datetime:
    """
    A wrapper to the main function to get the date of the next due amount calculation datetime.

    This should be used for the derived parameter as this can be called between events which means
    parameter value changes can affect the derived parameter being shown.

    This helper is only intended for use by lending products that require exactly one due
    calculation event per calendar month.

    :param vault:
    :param effective_datetime: effective dt of the calculation
    :param elapsed_term: the number of elapsed terms of the loan. Only used to verify as non-zero.
    :param remaining_term: the remaining terms of the loan (total - elapsed). Only used to verify as
     non-zero.
    :return next_due_amount_calculation_date: next expected date as of effective_datetime
    """
    next_due_calc_datetime = get_next_due_amount_calculation_datetime(
        vault=vault,
        effective_datetime=effective_datetime,
        elapsed_term=elapsed_term,
        remaining_term=remaining_term,
    )
    last_execution_datetime = vault.get_last_execution_datetime(
        event_type=DUE_AMOUNT_CALCULATION_EVENT
    )
    # we need to loop backwards through all the updates that have been made since the last event ran
    # until we find the value that yields a valid next due amount calculation date
    count = 0
    param_timeseries = vault.get_parameter_timeseries(name=PARAM_DUE_AMOUNT_CALCULATION_DAY).all()
    while (
        last_execution_datetime is not None
        and next_due_calc_datetime < effective_datetime
        and next_due_calc_datetime == last_execution_datetime + relativedelta(months=1)
    ):
        count += 1
        # on first loop, we use -2 (previous to the most recent value) going further back each loop
        param_update_position = -(1 + count)
        if (
            len(param_timeseries) > count
            and param_timeseries[param_update_position].at_datetime > last_execution_datetime
        ):
            prev_due_amount_calculation_day = param_timeseries[param_update_position].value
            next_due_calc_datetime = get_next_due_amount_calculation_datetime(
                vault=vault,
                effective_datetime=effective_datetime,
                elapsed_term=elapsed_term,
                remaining_term=remaining_term,
                due_amount_calculation_day=prev_due_amount_calculation_day,
            )
        else:
            # return here since there are no more values of due amount calc day param to check
            return next_due_calc_datetime
    return next_due_calc_datetime


def get_next_due_amount_calculation_datetime(
    vault: SmartContractVault,
    effective_datetime: datetime,
    elapsed_term: int,
    remaining_term: int,
    due_amount_calculation_day: Optional[int] = None,
) -> datetime:
    """
    Calculates the next due amount calculation date, assuming a fixed monthly schedule frequency.

    If called during the opening month, next due amount calculation dt falls on the
    due amount calculation day at least one month after account opening dt.

    Subsequent calculations are exactly one month apart.

    If the due amount calculation day parameter value changes:
        - If a due amount calculation has already occurred this month,
        the new day is reflected in the due amount calculation date for the next month.

        - If a due amount calculation hasn't already occurred in the current month
        and the new due amount calculation day is greater than the day of the change,
        the new day is reflected in the due amount calculation date for the current month.

        - If a due amount calculation hasn't already occurred this month
        and the new day is lower than the current day,
        the new day is reflected in the due amount calculation date for the next month

    The elapsed and remaining terms must be used instead of the last_execution_datetime of the
    DUE_AMOUNT_CALCULATION_EVENT since last_execution_datetime always returns the most recent
    datetime, as of live. Therefore using last_execution_datetime when requesting the next
    DUE_AMOUNT_CALCULATION_EVENT in the past (e.g the derived parameter hook) will result in
    incorrect results

    :param vault:
    :param effective_datetime: effective dt of the calculation
    :param elapsed_term: the number of elapsed terms of the loan. Only used to verify as non-zero.
    :param remaining_term: the remaining terms of the loan (total - elapsed). Only used to verify as
     non-zero.
    :param due_amount_calculation_day: optional due amount calculation day, which will be obtained
    from the parameter if left as None.
    :return next_due_amount_calculation_date: next expected date as of effective_datetime
    """
    # The next due_amount_calculation datetime is being requested before the first event
    if elapsed_term == 0:
        return get_first_due_amount_calculation_datetime(vault=vault)

    # when elapsed_term > 0 we must have had an DUE_AMOUNT_CALCULATION_EVENT therefore this will
    # never be None
    last_execution_datetime = vault.get_last_execution_datetime(
        event_type=DUE_AMOUNT_CALCULATION_EVENT
    )

    # The next due_amount_calculation datetime is being requested after the final event
    # so the datetime of the final event should be returned
    if remaining_term == 0:
        return last_execution_datetime  # type: ignore

    if due_amount_calculation_day is None:
        due_amount_calculation_day = int(
            utils.get_parameter(vault=vault, name=PARAM_DUE_AMOUNT_CALCULATION_DAY)
        )
    schedule_hour, schedule_minute, schedule_second = utils.get_schedule_time_from_parameters(
        vault=vault, parameter_prefix=DUE_AMOUNT_CALCULATION_PREFIX
    )

    # The next due_amount_calculation datetime is being requested at an
    # effective_datetime < last_execution_datetime (i.e. in the past)
    if last_execution_datetime > effective_datetime:  # type: ignore
        last_execution_datetime = None

    return _get_next_due_amount_calculation_datetime(
        start_datetime=vault.get_account_creation_datetime(),
        due_amount_calculation_day=due_amount_calculation_day,
        due_amount_calculation_hour=schedule_hour,
        due_amount_calculation_minute=schedule_minute,
        due_amount_calculation_second=schedule_second,
        effective_datetime=effective_datetime,
        last_execution_datetime=last_execution_datetime,
    )


def _get_next_due_amount_calculation_datetime(
    start_datetime: datetime,
    due_amount_calculation_day: int,
    due_amount_calculation_hour: int,
    due_amount_calculation_minute: int,
    due_amount_calculation_second: int,
    effective_datetime: datetime,
    last_execution_datetime: Optional[datetime],
) -> datetime:
    """
    Calculates the next due amount calculation date, assuming a fixed monthly schedule frequency.

    :param start_datetime: the anchor point to determine the next datetime if the last execution
    datetime is None, e.g. the account creation datetime to determine the first due amount
    calculation datetime
    :param due_amount_calculation_day:
    :param due_amount_calculation_hour:
    :param due_amount_calculation_minute:
    :param due_amount_calculation_second:
    :param effective_datetime: effective dt of the calculation
    :param last_execution_datetime: Optional, last execution dt of DUE_AMOUNT_CALCULATION
    :return next_due_amount_calculation_date: next expected date as of effective_datetime
    """

    if last_execution_datetime is None:
        earliest_datetime = start_datetime.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) + relativedelta(months=1)
        next_due_amount_calculation_datetime = start_datetime.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        # the day value must be updated within the relativedelta and not the replace since
        # relativedelta gracefully handles day not in month errors, which replace does not.
        # e.g. datetime(2021, 2, 2) + relativedelta(day=31) will return datetime(2021, 2, 28)
        next_due_amount_calculation_datetime += relativedelta(
            day=due_amount_calculation_day, months=1
        )
        # we can do the following because the case where the next_due_amount_calculation_datetime
        # is requested after the loan has finished is handled in the parent function
        while (
            earliest_datetime > next_due_amount_calculation_datetime
            or next_due_amount_calculation_datetime < effective_datetime
        ):
            next_due_amount_calculation_datetime += relativedelta(months=1)

    elif _due_amount_calculation_day_changed(
        last_execution_datetime, due_amount_calculation_day
    ) and (
        last_execution_datetime.month == effective_datetime.month
        or due_amount_calculation_day > effective_datetime.day
    ):
        # these two conditions have the same outcome because last execution datetime will
        # be in the previous month if there hasn't been a due amount calculation this month
        # or will be in the effective date month otherwise
        next_due_amount_calculation_datetime = last_execution_datetime + relativedelta(
            months=1,
            day=due_amount_calculation_day,
        )
    else:
        # either the day hasn't changed, in which case we just want to preserve the month,
        # or the day has changed to be prior to the effective date's day,
        # in which case the change will take effect from the following month to ensure we have a
        # due amount calculation in the current month
        next_due_amount_calculation_datetime = last_execution_datetime + relativedelta(months=1)

    return next_due_amount_calculation_datetime.replace(
        hour=due_amount_calculation_hour,
        minute=due_amount_calculation_minute,
        second=due_amount_calculation_second,
    )


def _due_amount_calculation_day_changed(
    last_execution_datetime: Optional[datetime], due_amount_calculation_day: int
) -> bool:
    # can't change due amount calculation day before the first due calculation
    if last_execution_datetime is None:
        return False
    return last_execution_datetime.day != due_amount_calculation_day


def get_supervisee_last_execution_effective_datetime(
    loan_vault: SuperviseeContractVault,
    main_vault: SuperviseeContractVault,
    event_type: str,
    effective_datetime: datetime,
    elapsed_term: int,
) -> datetime:
    # If the event has not run yet, set the last execution datetime to the account creation date
    last_execution_datetime = (
        loan_vault.get_account_creation_datetime()
        if elapsed_term == 0
        else main_vault.get_last_execution_datetime(event_type=event_type)
    )

    if last_execution_datetime is None:
        last_execution_datetime = loan_vault.get_account_creation_datetime()

    # The supervisee event may run before the supervisor event, resulting in an updated last
    # execution datetime. In this case, subtract a month to get the previous execution time
    if last_execution_datetime == effective_datetime:
        last_execution_datetime -= relativedelta(months=1)
    return last_execution_datetime
