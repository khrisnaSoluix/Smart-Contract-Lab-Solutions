# this is a module that represents a monthly amortisation cycle
# variants that does not need a monthly schedule e.g. no repayment loan
# will not import this particular component; it covers:
# 1. scheduling of monthly repayment events to calculate and allocate DUE amount
# that customers need to payment within a repayment period
# 2. scheduling of events to move outstanding DUE into OVERDUE after repayment period
# 3. method to process repayment and redistribute the amount into various outstanding
# balances according a hierarchy
# 4. orchestrates other features like interest accrual, amortisation and overpayment etc
# to ensure the interactions among them are consistent and correct
# 5. it also contains logic to determine where the product is within its lifecycle (term counts)

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, NamedTuple
from dateutil.relativedelta import relativedelta as timedelta
from json import dumps as json_dumps

# inception libraries
from inception_sdk.vault.contracts.types_extension import (
    AccountIdShape,
    EventType,
    FlagTimeseries,
    EventTypeSchedule,
    Parameter,
    NumberShape,
    NumberKind,
    Level,
    UpdatePermission,
    DEFAULT_ASSET,
    DEFAULT_ADDRESS,
    PostingInstruction,
    Rejected,
    RejectedReason,
    StringShape,
    Vault,
)
import library.features.common.utils as utils

# import disbursement directly into debt management assuming there would be
# no loan that does not require initial disbursement
import library.features.lending.disbursement as disbursement

# interest accrual feature should be injected by template instead of
# hard coded import into this component as some variants may not
# need daily accruals
# unfortunately, this results in more wordy method signatures, as renderer does not support
# class based syntax, and there is no way to "instantiate" a debt management object with
# one injection at init
import library.features.lending.interest_accrual as interest_accrual
import library.features.lending.overpayment as overpayment
import library.features.lending.amortisation.declining_principal as declining_principal

# Schedule event names
DUE_AMOUNT_CALCULATION = "DUE_AMOUNT_CALCULATION"
CHECK_OVERDUE = "CHECK_OVERDUE"
CHECK_DELINQUENCY = "CHECK_DELINQUENCY"

# addresses
INTERNAL_CONTRA = "INTERNAL_CONTRA"
PRINCIPAL_DUE_ADDRESS = "PRINCIPAL_DUE"
INTEREST_DUE_ADDRESS = "INTEREST_DUE"
PRINCIPAL_OVERDUE_ADDRESS = "PRINCIPAL_OVERDUE"
INTEREST_OVERDUE_ADDRESS = "INTEREST_OVERDUE"
PENALTIES_ADDRESS = "PENALTIES"
EMI_ADDRESS = "EMI"

# address groups
DUE_ADDRESSES = [PRINCIPAL_DUE_ADDRESS, INTEREST_DUE_ADDRESS]
OVERDUE_ADDRESSES = [PRINCIPAL_OVERDUE_ADDRESS, INTEREST_OVERDUE_ADDRESS]
LATE_PAYMENT_ADDRESSES = OVERDUE_ADDRESSES + [PENALTIES_ADDRESS]

REPAYMENT_ORDER = LATE_PAYMENT_ADDRESSES + DUE_ADDRESSES

due_schedule_parameters = [
    Parameter(
        name="due_amount_calculation_day",
        shape=NumberShape(min_value=1, max_value=28, step=1),
        level=Level.INSTANCE,
        description="The day of the month that the monthly due amount calculations takes place on."
        " This day must be between the 1st and 28th day of the month.",
        display_name="Due amount calculation day",
        default_value=Decimal(28),
        update_permission=UpdatePermission.USER_EDITABLE,
    ),
    Parameter(
        name="due_amount_calculation_hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=Level.TEMPLATE,
        description="The hour of the day at which due amount is calculated.",
        display_name="Repayment hour",
        default_value=0,
    ),
    Parameter(
        name="due_amount_calculation_minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The minute of the day at which due amount is calculated.",
        display_name="Repayment minute",
        default_value=1,
    ),
    Parameter(
        name="due_amount_calculation_second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The second of the day at which due amount is calculated.",
        display_name="Repayment second",
        default_value=0,
    ),
]

overdue_schedule_parameters = [
    Parameter(
        name="repayment_period",
        shape=NumberShape(max_value=27, min_value=1, step=1),
        level=Level.TEMPLATE,
        description="The number of days after the due amount calculation that the customer must "
        "repay the due amount by before incurring penalties.",
        display_name="Repayment period (days)",
        default_value=1,
    ),
    Parameter(
        name="check_overdue_hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=Level.TEMPLATE,
        description="The hour of the day at which overdue is checked.",
        display_name="Check overdue hour",
        default_value=0,
    ),
    Parameter(
        name="check_overdue_minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The minute of the day at which overdue is checked.",
        display_name="Check overdue minute",
        default_value=0,
    ),
    Parameter(
        name="check_overdue_second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The second of the day at which overdue is checked.",
        display_name="Check overdue second",
        default_value=2,
    ),
    Parameter(
        name="late_repayment_fee",
        shape=NumberShape(kind=NumberKind.MONEY),
        level=Level.TEMPLATE,
        description="Fee to apply due to late repayment.",
        display_name="Late repayment fee",
        default_value=Decimal("25"),
    ),
    Parameter(
        name="late_repayment_fee_income_account",
        level=Level.TEMPLATE,
        description="Internal account for late repayment fee income balance.",
        display_name="Late repayment fee income account",
        shape=AccountIdShape,
        default_value="LATE_REPAYMENT_FEE_INCOME",
    ),
    Parameter(
        name="delinquency_flags",
        shape=StringShape,
        level=Level.TEMPLATE,
        description="Flag definition id to be used for account delinquency.",
        display_name="Account delinquency flag",
        default_value=json_dumps(["ACCOUNT_DELINQUENT"]),
    ),
]

delinquency_schedule_parameters = [
    Parameter(
        name="grace_period",
        shape=NumberShape(max_value=27, min_value=0, step=1),
        level=Level.TEMPLATE,
        description="The number of days after which the account becomes delinquent "
        "if overdue amount and their penalties are not paid in full.",
        display_name="Grace period (days)",
        default_value=Decimal(15),
    ),
    Parameter(
        name="check_delinquency_hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=Level.TEMPLATE,
        description="The hour of the day at which delinquency is checked.",
        display_name="Check delinquency hour",
        default_value=0,
    ),
    Parameter(
        name="check_delinquency_minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The minute of the day at which delinquency is checked.",
        display_name="Check delinquency minute",
        default_value=0,
    ),
    Parameter(
        name="check_delinquency_second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The second of the day at which delinquency is checked.",
        display_name="Check delinquency second",
        default_value=2,
    ),
]

drawdown_parameters = [
    Parameter(
        name="total_term",
        shape=NumberShape(min_value=Decimal(12), max_value=Decimal(60), step=Decimal(1)),
        level=Level.INSTANCE,
        description="The agreed length of the product (in months).",
        display_name="Term (months)",
        default_value=Decimal(12),
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
]

all_parameters = [
    *due_schedule_parameters,
    *overdue_schedule_parameters,
    *delinquency_schedule_parameters,
    *drawdown_parameters,
]


def get_event_types(
    product_name: str,
    include_due_amount_calculation_schedule=True,
    include_overdue_schedule=True,
    include_delinquency_schedule=True,
) -> list[EventType]:
    """
    Creates event_types metadata for DUE_AMOUNT_CALCULATION, CHECK_OVERDUE and CHECK_DELINQUENCY
     schedules
    :param product_name: the name of the product for the tag prefix
    :param include_due_amount_calculation_schedule: if false, the due amount calculation event
    type is not returned
    :param include_overdue_schedule: if false the check overdue event type is not returned
    :param include_delinquency_schedule: if false the check delinquency event type is not returned
    """
    types = []
    if include_due_amount_calculation_schedule:
        types.append(
            EventType(
                name=DUE_AMOUNT_CALCULATION,
                scheduler_tag_ids=[f"{product_name.upper()}_{DUE_AMOUNT_CALCULATION}_AST"],
            ),
        )
    if include_overdue_schedule:
        types.append(
            EventType(
                name=CHECK_OVERDUE,
                scheduler_tag_ids=[f"{product_name.upper()}_{CHECK_OVERDUE}_AST"],
            ),
        )
    if include_delinquency_schedule:
        types.append(
            EventType(
                name=CHECK_DELINQUENCY,
                scheduler_tag_ids=[f"{product_name.upper()}_{CHECK_DELINQUENCY}_AST"],
            ),
        )
    return types


def get_execution_schedules(
    vault: Vault,
    start_date: datetime,
    repayment_period: Optional[int] = None,
    grace_period: Optional[int] = None,
    include_due_amount_calculation_schedule=True,
    include_overdue_schedule=True,
    include_delinquency_schedule=True,
) -> list[tuple[str, dict[str, str]]]:
    """
    Creates list of execution schedules for DUE_AMOUNT_CALCULATION, CHECK_OVERDUE and
    CHECK_DELINQUENCY schedules.

    :param vault: Vault object
    :param start_date: date to start schedules from e.g. account creation date or loan start date
    :param repayment_period: the length of the repayment period if the parameter is not on the
    vault object that is accessed here. Only used if include_overdue_schedule is True
    :param grace_period: the length of the grace period if the parameter is not on the
    vault object that is accessed here. Only used if include_delinquency_schedule is True
    :param include_due_amount_calculation_schedule: if false the due amount calculation schedule
     is not created
    :param include_overdue_schedule: if false the check overdue schedule is not created
    :param include_delinquency_schedule: if false the check delinqunecy schedule is not created
    :return: list of execution schedules
    """
    schedules = []

    # force the start date to be considered at 00:00:00 to ensure that
    # start_date <= first repayment schedule
    start_date = start_date.replace(hour=0, minute=0, second=0)
    start_date_plus_month = start_date + timedelta(months=1)

    if include_due_amount_calculation_schedule:
        schedules.append(
            (
                DUE_AMOUNT_CALCULATION,
                {
                    "day": str(utils.get_parameter(vault, "due_amount_calculation_day")),
                    "hour": str(utils.get_parameter(vault, "due_amount_calculation_hour")),
                    "minute": str(utils.get_parameter(vault, "due_amount_calculation_minute")),
                    "second": str(utils.get_parameter(vault, "due_amount_calculation_second")),
                },
            )
        )

    if include_overdue_schedule or include_delinquency_schedule:
        if repayment_period is None:
            repayment_period = int(utils.get_parameter(vault, "repayment_period"))
        start_date_plus_month_plus_repayment_period = start_date_plus_month + timedelta(
            days=repayment_period
        )
        if include_overdue_schedule:
            schedules.append(
                (
                    CHECK_OVERDUE,
                    {
                        "year": str(start_date_plus_month_plus_repayment_period.year),
                        "month": str(start_date_plus_month_plus_repayment_period.month),
                        "day": str(start_date_plus_month_plus_repayment_period.day),
                        "hour": str(utils.get_parameter(vault, "check_overdue_hour")),
                        "minute": str(utils.get_parameter(vault, "check_overdue_minute")),
                        "second": str(utils.get_parameter(vault, "check_overdue_second")),
                    },
                )
            )
        if include_delinquency_schedule:
            if grace_period is None:
                grace_period = int(utils.get_parameter(vault, "grace_period"))
            # This schedule must be defined in execution schedules so that it can be scheduled
            # when required during CHECK_OVERDUE, but to ensure this schedule does not run
            # before CHECK_OVERDUE, force grace period > 0
            grace_period = grace_period if grace_period > 0 else 1
            start_date_plus_month_plus_repayment_period_plus_grace = (
                start_date_plus_month_plus_repayment_period + timedelta(days=grace_period)
            )
            schedules.append(
                (
                    CHECK_DELINQUENCY,
                    {
                        "year": str(start_date_plus_month_plus_repayment_period_plus_grace.year),
                        "month": str(start_date_plus_month_plus_repayment_period_plus_grace.month),
                        "day": str(start_date_plus_month_plus_repayment_period_plus_grace.day),
                        "hour": str(utils.get_parameter(vault, "check_delinquency_hour")),
                        "minute": str(utils.get_parameter(vault, "check_delinquency_minute")),
                        "second": str(utils.get_parameter(vault, "check_delinquency_second")),
                    },
                )
            )

    return schedules


def get_transfer_due_instructions(
    vault: Vault,
    denomination: str,
    effective_date: datetime,
    interest_calculation: NamedTuple,
    repayment_period: Optional[int] = None,
    emi_adjustment_effects: Optional[list[NamedTuple]] = None,
    principal_adjustment_effects: Optional[list[NamedTuple]] = None,
    interest_application_effects: Optional[list[NamedTuple]] = None,
    due_amount_schedule_details: Optional[utils.ScheduleDetails] = None,
    due_amount_calculation_blocking_flags: Optional[list[FlagTimeseries]] = None,
    due_amount_calculation_blocking_param: Optional[str] = "due_amount_calculation_blocking_flags",
    **kwargs,
) -> list[PostingInstruction]:

    """
    Creates posting instructions to update the due amounts, typically as part of the due
    amount calculation schedule. Also sends a repayment notification.
    Interfaces are detailed in library/features/lending/interfaces.md
    :param vault: the vault object for the account to perform due amount updates for
    :param denomination: the account denomination
    :param effective_date: the date used for fetching data and creating directives
    :param interest_calculation: an interest calculation feature
    :param repayment_period: the number of days between due amount calculation and overdue checks.
    Used for repayment notifications and scheduling overdue checks. Only required if the parameters
    are not retrievable via the vault object (e.g. using the method in a supervisor where params are
    split between accounts)
    :param emi_adjustment_effects: features that can impact EMI calculation. Must
    implement the `Reamortisation` interface
    :param principal_adjustment_effects: features that can impact principal amounts. Must
    implement the `Principal Adjustment` interface
    :param interest_application_effects: features that determine interest application effects. Must
    implement the `Interest application` interface
    :param due_amount_schedule_details: only required if the due amount schedule parameters and last
    execution time are not retrievable via the vault object (e.g. using the method in a supervisor
    where params are split between accounts)
    :param due_amount_calculation_blocking_flags: only required if the parameters are not
    retrievable via the vault object (e.g. using the method in a supervisor where params are split
    between accounts) list of flag timeseries for due amount blocking flags. If any are currently
    applied, an empty list is returned
    :param due_amount_calculation_blocking_param: name of the due amount blocking flags parameter,
    not needed if due_amount_calculation_blocking_flags provided
    :param kwargs: this can be used to pass extra information to effects
    :return: due amount calculation postings
    """

    # Exclude loans if they are less than a month old as they haven't completed a monthly cycle yet
    # Using account_creation_date as loan_start_date param value can change over time.
    # .date() is used so that time components do not affect this logic:
    # - the cut-off for inclusion is at midnight of the due amount calculation day, regardless of
    #  when the schedule runs
    # - all accounts created between 00:00:00 and 23:59:59 of a given day will have the same number
    # of accruals by due amount calculation date, so this shouldn't affect inclusion
    if (vault.get_account_creation_date() + timedelta(months=1)).date() > effective_date.date():
        return []
    if utils.blocking_flags_applied(
        vault=vault,
        effective_date=effective_date,
        flag_timeseries=due_amount_calculation_blocking_flags,
        parameter_name=due_amount_calculation_blocking_param,
    ):
        return []

    if due_amount_schedule_details is None:
        due_amount_schedule_details = get_due_amount_calculation_schedule_details(
            vault, effective_date
        )
    if repayment_period is None:
        repayment_period = int(utils.get_parameter(vault, "repayment_period"))

    term_details = get_expected_remaining_term(
        vault, effective_date, schedule_details=due_amount_schedule_details
    )

    P = get_remaining_principal(vault, principal_adjustment_effects)
    # contains logic to resolve to fixed or variable rate, can be injected via contract template
    # placeholder for when variable rate diff is landed
    R = interest_calculation.get_monthly_interest_rate(vault)
    N = term_details["remaining"]

    emi_adjustment_effects = emi_adjustment_effects or []
    principal_adjustment_effects = principal_adjustment_effects or []
    interest_application_effects = interest_application_effects or []

    stored_emi = utils.get_balance_sum(vault, [EMI_ADDRESS])
    # Would be nice to avoid this, but the argument is named in this function and needs to be in
    # kwargs to be passed into the reamortisation interface
    kwargs.update({"due_amount_calculation_blocking_flags": due_amount_calculation_blocking_flags})
    emi = (
        declining_principal.calculate_emi(P, R, N)
        if stored_emi == 0
        or any(
            emi_adjustment_effect.should_trigger_reamortisation(
                vault, term_details["elapsed"], due_amount_schedule_details, **kwargs
            )
            for emi_adjustment_effect in emi_adjustment_effects
        )
        else stored_emi
    )

    # accrued interest inherently excludes any additional interest from accruals that happened more
    # than 1 month before due amount calculation date
    accrued_interest = interest_accrual.get_accrued_interest(vault)
    principal_due = min(
        (emi - utils.round_decimal(accrued_interest, 2)),
        P,  # principal due can't exceed remaining principal (e.g. last month)
    )

    posting_instructions = get_store_emi_posting_instructions(
        vault, emi, stored_emi, denomination
    ) + get_principal_due_posting_instructions(vault, principal_due, denomination)

    for interest_application_effect in interest_application_effects:
        posting_instructions.extend(
            interest_application_effect.get_application_posting_instructions(
                vault, effective_date, denomination
            )
        )

    # The actual principal may need updating due to features like overpayments, whereby
    # remaining principal is less than it would have normally be, or from principal
    # capitalisations, whereby additional amounts # (e.g. from interest accrual) are treated as
    # an increase in principal amount (compounding);
    # we could have hardcoded these scenarios more explicitly, but re-using the
    # `<x>_adjustment_effects` pattern is consistent with what we do for EMI and avoids coupling
    for principal_adjustment_effect in principal_adjustment_effects:
        posting_instructions.extend(
            principal_adjustment_effect.get_principal_adjustment_posting_instructions(
                vault, denomination
            )
        )

    return posting_instructions


# posting instruction wrappers
def get_store_emi_posting_instructions(
    vault: Vault, emi: Decimal, stored_emi: Decimal, denomination: str
) -> list[PostingInstruction]:
    if emi > 0 and emi != stored_emi:
        if emi > stored_emi:
            # Increase ASSET balance net by debiting it
            from_address = EMI_ADDRESS
            to_address = INTERNAL_CONTRA
        else:
            from_address = INTERNAL_CONTRA
            to_address = EMI_ADDRESS
        return vault.make_internal_transfer_instructions(
            amount=abs(emi - stored_emi),
            denomination=denomination,
            client_transaction_id=f"UPDATE_EMI_{vault.get_hook_execution_id()}",
            from_account_id=vault.account_id,
            from_account_address=from_address,
            to_account_id=vault.account_id,
            to_account_address=to_address,
            instruction_details={
                "description": f"Updating EMI amount from {stored_emi} to {emi}",
                "event": DUE_AMOUNT_CALCULATION,
            },
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
        )
    return []


def get_principal_due_posting_instructions(
    vault: Vault, principal_due: Decimal, denomination: str
) -> list[PostingInstruction]:
    return (
        vault.make_internal_transfer_instructions(
            amount=principal_due,
            denomination=denomination,
            client_transaction_id=f"UPDATE_PRINCIPAL_DUE_{vault.get_hook_execution_id()}",
            from_account_id=vault.account_id,
            from_account_address=PRINCIPAL_DUE_ADDRESS,
            to_account_id=vault.account_id,
            to_account_address=disbursement.PRINCIPAL,
            instruction_details={
                "description": f"Monthly principal added to due address: {principal_due}",
                "event": DUE_AMOUNT_CALCULATION,
            },
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
        )
        if principal_due > 0
        else []
    )


def get_overdue_posting_instructions(
    vault: Vault,
    effective_date: datetime,
    overdue_amount_calculation_blocking_flags: Optional[list[FlagTimeseries]] = None,
    overdue_amount_calculation_blocking_param: Optional[
        str
    ] = "overdue_amount_calculation_blocking_flags",
) -> list[PostingInstruction]:
    """
    Creates posting instructions to move any due amounts to overdue addresses
    at the end of the repayment period.

    :param vault: the vault object for the account to perform due amount updates for
    :param effective_date: the date used for fetching data and creating directives
    :param overdue_amount_calculation_blocking_flags: only required if the parameters are not
    retrievable via the vault object (e.g. using the method in a supervisor where params are split
    between accounts) list of flag timeseries for overdue blocking flags. If any are currently
    applied, an empty list is returned
    :param overdue_amount_calculation_blocking_param: name of the overdue amount blocking
    flags parameter, not needed if overdue_amount_calculation_blocking_flags provided
    :return: overdue amount postings
    """
    if utils.blocking_flags_applied(
        vault=vault,
        effective_date=effective_date,
        flag_timeseries=overdue_amount_calculation_blocking_flags,
        parameter_name=overdue_amount_calculation_blocking_param,
    ):
        return []
    effective_date = effective_date + timedelta(microseconds=1)

    posting_instructions = []
    denomination: str = utils.get_parameter(vault, name="denomination")

    for due_address in DUE_ADDRESSES:
        amount_to_transfer = utils.get_balance_sum(vault, [due_address])
        overdue_address = (
            PRINCIPAL_OVERDUE_ADDRESS
            if due_address == PRINCIPAL_DUE_ADDRESS
            else INTEREST_OVERDUE_ADDRESS
        )
        if amount_to_transfer > 0:
            posting_instructions.extend(
                vault.make_internal_transfer_instructions(
                    amount=amount_to_transfer,
                    denomination=denomination,
                    client_transaction_id=vault.get_hook_execution_id() + "_" + overdue_address,
                    from_account_id=vault.account_id,
                    from_account_address=overdue_address,
                    to_account_id=vault.account_id,
                    to_account_address=due_address,
                    instruction_details={
                        "description": f"Mark outstanding due amount of "
                        f"{amount_to_transfer} as {overdue_address}.",
                        "event": "MOVE_BALANCE_INTO_" + overdue_address,
                    },
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                )
            )

    return posting_instructions


def get_late_repayment_fee_posting_instructions(vault: Vault) -> list[PostingInstruction]:
    fee_amount: Decimal = utils.get_parameter(vault, name="late_repayment_fee")
    if fee_amount == 0:
        return []

    denomination: str = utils.get_parameter(vault, name="denomination")

    late_repayment_fee_income_account: str = utils.get_parameter(
        vault, "late_repayment_fee_income_account"
    )
    return vault.make_internal_transfer_instructions(
        amount=fee_amount,
        denomination=denomination,
        client_transaction_id=vault.get_hook_execution_id() + "_CHARGE_FEE",
        from_account_id=vault.account_id,
        from_account_address=PENALTIES_ADDRESS,
        to_account_id=late_repayment_fee_income_account,
        to_account_address=DEFAULT_ADDRESS,
        instruction_details={
            "description": f"Incur late repayment fees of {fee_amount}",
            "event": "INCUR_PENALTY_FEES",
        },
        asset=DEFAULT_ASSET,
        override_all_restrictions=True,
    )


# Time calculation helper functions
def _calculate_next_due_amount_calculation_date(
    loan_start_date: datetime,
    effective_date: datetime,
    due_amount_schedule_details: utils.ScheduleDetails,
) -> datetime:
    """
    Determines the next time that the due amount calculation should take place

    :param loan_start_date: The loan's start date
    :param effective_date: Date as of which the calculation is made
    :param due_amount_schedule_details: the details of the due amount calculation schedule
    :return: datetime representing when the due amount calculation should next take place
    """

    last_execution_time = due_amount_schedule_details.last_execution_time

    delta_to_schedule_time = timedelta(
        day=due_amount_schedule_details.day,
        hour=due_amount_schedule_details.hour,
        minute=due_amount_schedule_details.minute,
        second=due_amount_schedule_details.second,
        microsecond=0,
    )

    previous_due_amount_calculation_day = (
        last_execution_time.day
        if last_execution_time and effective_date != loan_start_date
        else due_amount_schedule_details.day
    )

    if previous_due_amount_calculation_day != due_amount_schedule_details.day:

        # then we've had a due amount calculation day change
        if (
            last_execution_time.month == effective_date.month
            or due_amount_schedule_details.day > effective_date.day
        ):
            # then repayment event has either occurred this month
            # or it has not AND the new due amount calculation day is in the future
            # so next repayment event is the following month from the last execution
            # on the new due amount calculation day
            next_due_amount_calculation_date = (
                last_execution_time + timedelta(months=1) + delta_to_schedule_time
            )

        else:
            # the due amount calculation day has not occurred this month yet
            next_due_amount_calculation_date = last_execution_time + timedelta(months=1)
        return next_due_amount_calculation_date

    earliest_event_start_date: datetime = loan_start_date + timedelta(months=1)
    if last_execution_time and loan_start_date < last_execution_time <= effective_date:
        # The earliest time repayment event can run from effective_date
        earliest_event_start_date = last_execution_time + timedelta(months=1)

    next_payment_date: datetime = effective_date + delta_to_schedule_time
    if next_payment_date <= effective_date:
        next_payment_date += timedelta(months=1)

    if effective_date < earliest_event_start_date:
        next_payment_date = earliest_event_start_date + delta_to_schedule_time
        if next_payment_date < earliest_event_start_date:
            next_payment_date += timedelta(months=1)

    return next_payment_date


def get_expected_remaining_term(
    vault: Vault,
    effective_date: datetime,
    schedule_details: utils.ScheduleDetails,
    term_name: str = "total_term",
) -> dict[str, int]:
    """
    return: a dictionary with keys elapsed and remaining, providing number
    of months elapsed since the starting date of the loan and the remaining
    months until its maturity according to the natural end of term.
    """
    term = int(utils.get_parameter(vault, name=term_name))
    loan_start_date: datetime = utils.get_parameter(vault, name="loan_start_date")
    first_due_amount_calculation_date: datetime = _calculate_next_due_amount_calculation_date(
        loan_start_date=loan_start_date,
        effective_date=loan_start_date,
        due_amount_schedule_details=schedule_details,
    )

    if effective_date < first_due_amount_calculation_date:
        remaining_term = timedelta(months=term)
    else:
        remaining_term = timedelta(
            first_due_amount_calculation_date.date(), effective_date.date()
        ) + timedelta(months=term)
    if effective_date + remaining_term < effective_date + timedelta(months=1):
        return {"elapsed": term, "remaining": 0}
    else:
        # negative days should reduce term by up to 1 month
        rounded_month = -1 if remaining_term.days < 0 else 0
        remaining = remaining_term.years * 12 + remaining_term.months + rounded_month
        elapsed = term - remaining
        return {"elapsed": elapsed, "remaining": remaining}


# notification helpers
def send_repayment_notification(
    vault: Vault,
    repayment_amount: Decimal,
    due_amount_calculation_date: datetime,
    repayment_period: int,
    product_name: str = "LOAN",
    notification_blocking_flags: Optional[list[FlagTimeseries]] = None,
) -> None:
    """
    Instruct a repayment notification.

    :param vault: Vault object
    :param repayment_amount: monthly payment to be made
    :param due_amount_calculation_date: the date that the repayment amount became due
    :param repayment_period: the number of days between due amount calculation and
    repayment being due
    :param product_name: the name of the product for the notification prefix
    :param notification_blocking_flags: only required if the parameters are not
    retrievable via the vault object (e.g. using the method in a supervisor where params are split
    between accounts) list of flag timeseries for notification blocking flags. If any are currently
    applied, no notification is sent
    :return: None
    """
    if (
        not _notification_blocked(
            vault=vault,
            effective_date=due_amount_calculation_date,
            notification_blocking_flags=notification_blocking_flags,
        )
        and repayment_amount > 0
    ):
        overdue_date: datetime = due_amount_calculation_date + timedelta(days=repayment_period)
        vault.instruct_notification(
            notification_type=f"{product_name.upper()}_REPAYMENT",
            notification_details={
                "account_id": vault.account_id,
                "repayment_amount": str(repayment_amount),
                "overdue_date": str(overdue_date.date()),
            },
        )


def send_overdue_repayment_notification(
    vault: Vault,
    effective_date: datetime,
    due_amount: Decimal,
    product_name: str = "LOAN",
    notification_blocking_flags: Optional[list[FlagTimeseries]] = None,
) -> None:
    """
    Start workflow for sending overdue repayment notification.

    :param vault: Vault object
    :param effective_date: datetime, effective date of scheduled event
    :param due_amount: Decimal, sum of balances in due addresses
    :param product_name: the name of the product for the workflow prefix
    :param notification_blocking_flags: only required if the parameters are not
    retrievable via the vault object (e.g. using the method in a supervisor where params are split
    between accounts) list of flag timeseries for notification blocking flags. If any are currently
    applied, no notification is sent
    :return: None
    """
    if (
        not _notification_blocked(
            vault=vault,
            effective_date=effective_date,
            notification_blocking_flags=notification_blocking_flags,
        )
        and due_amount > 0
    ):
        late_repayment_fee: Decimal = utils.get_parameter(vault, "late_repayment_fee")
        vault.instruct_notification(
            notification_type=f"{product_name.upper()}_OVERDUE_REPAYMENT",
            notification_details={
                "account_id": vault.account_id,
                "repayment_amount": str(due_amount),
                "late_repayment_fee": str(late_repayment_fee),
                "overdue_date": str(effective_date.date()),
            },
        )


def _notification_blocked(
    vault: Vault,
    effective_date: datetime,
    notification_blocking_flags: Optional[list[FlagTimeseries]] = None,
) -> bool:
    return utils.blocking_flags_applied(
        vault=vault,
        effective_date=effective_date,
        flag_timeseries=notification_blocking_flags,
        parameter_name="notification_blocking_flags",
    )


# schedule helpers
def get_due_amount_calculation_schedule_details(
    vault: Vault, effective_date: Optional[datetime] = None
) -> utils.ScheduleDetails:
    # Named tuples to use as return values from functions
    due_amount_schedule_day = int(utils.get_parameter(vault, "due_amount_calculation_day"))
    due_amount_calculation_hour = int(utils.get_parameter(vault, "due_amount_calculation_hour"))
    due_amount_calculation_minute = int(utils.get_parameter(vault, "due_amount_calculation_minute"))
    due_amount_calculation_second = int(utils.get_parameter(vault, "due_amount_calculation_second"))
    last_execution_time = vault.get_last_execution_time(event_type=DUE_AMOUNT_CALCULATION)

    # last_execution_time can be equal to effective date in scenarios where the last due amount
    # date comes from the supervisee and the effective date comes from the supervisor
    # TODO (INC-6804): this will need updating to handle the fact that the previous execution could
    # have been more than a month ago due to parameter updates
    if effective_date and last_execution_time == effective_date:
        last_execution_time += timedelta(months=-1)

    return utils.ScheduleDetails(
        hour=due_amount_calculation_hour,
        minute=due_amount_calculation_minute,
        second=due_amount_calculation_second,
        day=due_amount_schedule_day,
        month=None,
        year=None,
        last_execution_time=last_execution_time,
    )


def schedule_overdue_check(
    vault,
    effective_date: datetime,
    check_overdue_schedule_details: Optional[utils.ScheduleDetails] = None,
) -> None:
    """
    Update schedule to update
    :param vault: Vault object for account to update schedule on
    :param effective_date: effective date
    :param check_overdue_schedule_details: only required if the parameters are not
    retrievable via the vault object (e.g. using the method in a supervisor where
    params are split between accounts)
    """
    if check_overdue_schedule_details is None:
        check_overdue_schedule_details = get_check_overdue_schedule_details(vault, effective_date)

    vault.update_event_type(
        event_type=CHECK_OVERDUE,
        schedule=EventTypeSchedule(
            year=str(check_overdue_schedule_details.year),
            month=str(check_overdue_schedule_details.month),
            day=str(check_overdue_schedule_details.day),
            hour=str(check_overdue_schedule_details.hour),
            minute=str(check_overdue_schedule_details.minute),
            second=str(check_overdue_schedule_details.second),
        ),
    )


def get_check_overdue_schedule_details(vault, effective_date: datetime) -> utils.ScheduleDetails:
    """
    :param vault: either Smart Contract or Supervisor Contract Vault object
    :param repayment_period_end_date: date of the end of the repayment period
    when the overdue check should occur
    """
    # Named tuples to use as return values from functions
    check_overdue_hour = int(utils.get_parameter(vault, "check_overdue_hour"))
    check_overdue_minute = int(utils.get_parameter(vault, "check_overdue_minute"))
    check_overdue_second = int(utils.get_parameter(vault, "check_overdue_second"))

    repayment_period = int(utils.get_parameter(vault, "repayment_period"))
    repayment_period_end_date = effective_date + timedelta(days=repayment_period)

    check_overdue_year = int(repayment_period_end_date.year)
    check_overdue_month = int(repayment_period_end_date.month)
    check_overdue_day = int(repayment_period_end_date.day)

    return utils.ScheduleDetails(
        hour=check_overdue_hour,
        minute=check_overdue_minute,
        second=check_overdue_second,
        day=check_overdue_day,
        month=check_overdue_month,
        year=check_overdue_year,
        last_execution_time=None,
    )


def schedule_delinquency_check(
    vault,
    effective_date: datetime,
    check_delinquency_schedule_details: Optional[utils.ScheduleDetails] = None,
) -> None:
    """
    Schedule delinquency check
    :param vault: Smart/Supervisor Contract Vault object for account to update schedule on
    :param effective_date: effective date
    :param check_delinquency_schedule_details: only required if the parameters are not retrievable
    via the vault object (e.g. using the method in a supervisor where parameters
    are split between accounts)
    """
    if check_delinquency_schedule_details is None:
        check_delinquency_schedule_details = get_check_delinquency_schedule_details(
            vault, effective_date
        )

    vault.update_event_type(
        event_type=CHECK_DELINQUENCY,
        schedule=EventTypeSchedule(
            year=str(check_delinquency_schedule_details.year),
            month=str(check_delinquency_schedule_details.month),
            day=str(check_delinquency_schedule_details.day),
            hour=str(check_delinquency_schedule_details.hour),
            minute=str(check_delinquency_schedule_details.minute),
            second=str(check_delinquency_schedule_details.second),
        ),
    )


def get_check_delinquency_schedule_details(
    vault,
    effective_date: datetime,
) -> utils.ScheduleDetails:
    """
    :param vault: either Smart Contract or Supervisor Contract Vault object
    :param effective_date: date at the beginning of the grace period
    when the delinquency check should occur
    """
    # Named tuples to use as return values from functions
    check_delinquency_hour = int(utils.get_parameter(vault, "check_delinquency_hour"))
    check_delinquency_minute = int(utils.get_parameter(vault, "check_delinquency_minute"))
    check_delinquency_second = int(utils.get_parameter(vault, "check_delinquency_second"))

    grace_period = int(utils.get_parameter(vault, "grace_period"))
    grace_period_end_date = effective_date + timedelta(days=int(grace_period))

    check_delinquency_year = int(grace_period_end_date.year)
    check_delinquency_month = int(grace_period_end_date.month)
    check_delinquency_day = int(grace_period_end_date.day)

    return utils.ScheduleDetails(
        hour=check_delinquency_hour,
        minute=check_delinquency_minute,
        second=check_delinquency_second,
        day=check_delinquency_day,
        month=check_delinquency_month,
        year=check_delinquency_year,
        last_execution_time=None,
    )


# flag helpers
def apply_delinquency_flag(vault: Vault, effective_date: datetime, product_name: str) -> None:
    """
    Start workflow to apply delinquency flag if not already flagged.

    :param vault: Vault object
    :param effective_date: datetime
    :param product_name: the name of the product for the workflow prefix
    :return: None
    """
    if not utils.is_flag_in_list_applied(vault, "delinquency_flags", effective_date):
        vault.start_workflow(
            workflow=f"{product_name.upper()}_MARK_DELINQUENT",
            context={"account_id": str(vault.account_id)},
        )


# balance retrieval
def get_remaining_principal(
    vault: Vault, principal_adjustment_effects: Optional[list[NamedTuple]] = None
) -> Decimal:
    principal_adjustment_effects = principal_adjustment_effects or []
    return utils.get_balance_sum(vault, [disbursement.PRINCIPAL]) + sum(
        principal_adjustment_effect.get_principal_adjustment_amount(vault)
        for principal_adjustment_effect in principal_adjustment_effects
    )


def get_all_remaining_debt(
    vault: Vault, principal_adjustment_effects: Optional[list[NamedTuple]] = None
) -> Decimal:
    return utils.get_balance_sum(
        vault, REPAYMENT_ORDER + [interest_accrual.ACCRUED_INTEREST_RECEIVABLE_ADDRESS]
    ) + get_remaining_principal(vault, principal_adjustment_effects)


def get_remaining_dues(vault: Vault) -> Decimal:
    return utils.get_balance_sum(vault, REPAYMENT_ORDER)


def get_late_payment_balance(vault: Vault, timestamp: Optional[datetime] = None) -> Decimal:
    return utils.get_balance_sum(vault, LATE_PAYMENT_ADDRESSES, timestamp)


# pre posting validation
def validate_repayment(vault, postings, overpayment: Optional[overpayment.Overpayment] = None):
    if len(postings) > 1:
        raise Rejected(
            "Multiple postings in batch not supported",
            reason_code=RejectedReason.CLIENT_CUSTOM_REASON,
        )

    for posting in postings:
        proposed_amount = utils.get_posting_amount(posting)
        if proposed_amount <= 0:
            outstanding_debt = get_all_remaining_debt(vault)
            if abs(proposed_amount) > outstanding_debt:
                raise Rejected(
                    "Cannot pay more than is owed",
                    reason_code=RejectedReason.AGAINST_TNC,
                )
            if abs(proposed_amount) > get_remaining_dues(vault) and (
                not overpayment or not postings.batch_details.get("event") == "early_repayment"
            ):
                raise Rejected(
                    "Overpayments are not allowed",
                    reason_code=RejectedReason.AGAINST_TNC,
                )
        elif (
            postings.batch_details.get("fee") != "True"
            and postings.batch_details.get("interest_adjustment") != "True"
        ):
            raise Rejected(
                "Debiting not allowed from this account",
                reason_code=RejectedReason.AGAINST_TNC,
            )


def get_end_of_loan_cleanup_posting_instructions(
    vault: Vault, residual_cleanups: list[NamedTuple]
) -> list[PostingInstruction]:
    """
    Nets off stored EMI, and calls get_cleanup_residual_posting_instructions
    to reverse any balance amount in accounting addresses from corresponding
    modules.
    """
    denomination: str = utils.get_parameter(vault, name="denomination")
    hook_execution_id: str = vault.get_hook_execution_id()
    posting_instructions: list[PostingInstruction] = []

    emi_balance: Decimal = utils.get_balance_sum(vault, [EMI_ADDRESS])

    for residual_cleanup in residual_cleanups:
        posting_instructions.extend(
            residual_cleanup.get_cleanup_residual_posting_instructions(vault)
        )

    if emi_balance > 0:
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=emi_balance,
                denomination=denomination,
                client_transaction_id=f"CLEAR_EMI_{hook_execution_id}",
                from_account_id=vault.account_id,
                from_account_address=INTERNAL_CONTRA,
                to_account_id=vault.account_id,
                to_account_address=EMI_ADDRESS,
                instruction_details={
                    "description": "Clearing EMI address balance",
                    "event": "END_OF_LOAN",
                },
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
            )
        )

    return posting_instructions


def distribute_repayment(
    repayment_targets: list,
    repayment_amount: Decimal,
    denomination: str,
    repayment_hierarchy: list[list[str]],
) -> dict[Any, dict[str, tuple[Decimal, Decimal]]]:
    """
    Determines how a repayment amount should be spread across a number of repayment targets (loans),
    based on the repayment hierarchy and the outstanding balances. Each repayment hierarchy address'
    balance is rounded to 2dp for repayment purposes. Both rounded and unrounded amounts are
    returned so that the consumer can decide how to handle remainders. For example, a repayment of
    0.01 distributed to a balance of 0.0052 or to a balance of 0.0012
    :param repayment_targets: all the vault objects for the accounts to spread the
    repayment across. These should be sorted if relevant.
    :param repayment_amount: the 2dp repayment amount to spread
    :param denomination: the denomination of the repayment
    :param repayment_hierarchy: The order in which a repayment amount is spread across
    addresses for one or more targets. The outer list represents ordering across accounts and the
    the inner lists represent ordering within an account.
    For example, the hierarchy [[ADDRESS_1],[ADDRESS_2, ADDRESS_3]] would result in a distribution
    in this order, assuming two loans loan_1 and loan_2:
    # ADDRESS_1 paid on loan_1 and then loan_2
    ADDRESS_1 loan_1
    ADDRESS_1 loan_2
    # ADDRESS_2 and ADDRESS_3 paid on loan 1 and then loan 2
    ADDRESS_2 loan_1
    ADDRESS_3 loan_1
    ADDRESS_2 loan_2
    ADDRESS_3 loan_2
    :return: a dictionary of vault object to dictionary of address to a tuple of unrounded and
    rounded amounts to be repaid
    """

    # this amount is always kept to 2dp precision
    remaining_repayment_amount = repayment_amount
    repayments_per_loan = {loan: {} for loan in repayment_targets}

    for address_list in repayment_hierarchy:
        for loan_vault in repayment_targets:
            for repayment_address in address_list:
                unrounded_address_amount = utils.get_balance_sum(
                    vault=loan_vault,
                    denomination=denomination,
                    addresses=[repayment_address],
                )
                rounded_address_amount = utils.round_decimal(unrounded_address_amount, 2)
                rounded_address_repayment_amount = min(
                    rounded_address_amount, remaining_repayment_amount
                )
                # can't repay a balance that is < 2dp - this should be dealt with in close_code for
                # early repayments
                if rounded_address_repayment_amount == Decimal(0):
                    continue

                # ensure that the unrounded repayment amount is <= unrounded address amount
                # rounded repayment amount can be gt, eq or lt unrounded adress amount
                unrounded_address_repayment_amount = (
                    unrounded_address_amount
                    if rounded_address_amount <= remaining_repayment_amount
                    else remaining_repayment_amount
                )
                repayments_per_loan[loan_vault][repayment_address] = (
                    unrounded_address_repayment_amount,
                    rounded_address_repayment_amount,
                )
                remaining_repayment_amount -= rounded_address_repayment_amount

            if remaining_repayment_amount == Decimal(0):
                return repayments_per_loan

    return repayments_per_loan
