# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Optional

# features
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.lending.amortisations.interest_only as interest_only
import library.features.v4.lending.amortisations.minimum_repayment as minimum_repayment
import library.features.v4.lending.amortisations.no_repayment as no_repayment
import library.features.v4.lending.due_amount_calculation as due_amount_calculation
import library.features.v4.lending.lending_addresses as lending_addresses
import library.features.v4.lending.lending_interfaces as lending_interfaces
import library.features.v4.lending.lending_parameters as lending_parameters

# contracts api
from contracts_api import (
    BalanceDefaultDict,
    CustomInstruction,
    NumberShape,
    OptionalShape,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    Posting,
    ScheduledEvent,
    ScheduledEventHookArguments,
    SmartContractEventType,
    UpdateAccountEventTypeDirective,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

BALLOON_PAYMENT_EVENT = "BALLOON_PAYMENT_EVENT"

PARAM_BALLOON_PAYMENT_DAYS_DELTA = "balloon_payment_days_delta"
PARAM_BALLOON_PAYMENT_AMOUNT = "balloon_payment_amount"
PARAM_BALLOON_EMI_AMOUNT = "balloon_emi_amount"
PARAM_EXPECTED_BALLOON_PAYMENT_AMOUNT = "expected_balloon_payment_amount"

# Instance parameters
balloon_payment_days_delta_parameter = Parameter(
    name=PARAM_BALLOON_PAYMENT_DAYS_DELTA,
    shape=OptionalShape(shape=NumberShape(min_value=0, step=1)),
    level=ParameterLevel.INSTANCE,
    description="The number of days between the final repayment event and "
    "the balloon payment event.",
    display_name="Balloon Payment Days Delta",
    update_permission=ParameterUpdatePermission.OPS_EDITABLE,
)
balloon_payment_amount_parameter = Parameter(
    name=PARAM_BALLOON_PAYMENT_AMOUNT,
    shape=OptionalShape(
        shape=NumberShape(
            min_value=Decimal(100),
            step=Decimal("0.01"),
        ),
    ),
    level=ParameterLevel.INSTANCE,
    description="The balloon payment amount the customer has chosen to pay on the balloon"
    " payment day. If set, this determines the customer has chosen a fixed balloon payment.",
    display_name="Balloon Payment Amount",
    update_permission=ParameterUpdatePermission.OPS_EDITABLE,
)
balloon_emi_amount_parameter = Parameter(
    name=PARAM_BALLOON_EMI_AMOUNT,
    shape=OptionalShape(
        shape=NumberShape(
            min_value=Decimal("0"),
            step=Decimal("0.01"),
        ),
    ),
    level=ParameterLevel.INSTANCE,
    description="The fixed balloon emi amount the customer has chosen to pay each "
    "month. If set, this determines the customer has chosen a fixed emi payment.",
    display_name="Balloon Payment EMI Amount",
    update_permission=ParameterUpdatePermission.OPS_EDITABLE,
)

# Derived Parameters
expected_balloon_payment_amount_parameter = Parameter(
    name=PARAM_EXPECTED_BALLOON_PAYMENT_AMOUNT,
    shape=NumberShape(
        min_value=Decimal("0"),
        step=Decimal("0.01"),
    ),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="The expected balloon payment amount to be paid on the balloon payment date. "
    "This is only relevant for no_repayment, interest_only and "
    "minimum_repayment_with_balloon_payment loans.",
    display_name="Expected Balloon Payment Amount",
)


parameters = [
    balloon_payment_days_delta_parameter,
    balloon_payment_amount_parameter,
    balloon_emi_amount_parameter,
    expected_balloon_payment_amount_parameter,
]


def event_types(product_name: str) -> list[SmartContractEventType]:
    """
    event_types generate a list of schedules that will be referenced in the given smart contract.

    :param product_name: the product name
    :return: a slice of schedule event type references that will be used by this feature.
    """
    return [
        SmartContractEventType(
            name=BALLOON_PAYMENT_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{BALLOON_PAYMENT_EVENT}_AST"],
        )
    ]


def disabled_balloon_schedule(account_opening_datetime: datetime) -> dict[str, ScheduledEvent]:
    return {BALLOON_PAYMENT_EVENT: utils.create_end_of_time_schedule(account_opening_datetime)}


def scheduled_events(
    vault: SmartContractVault, account_opening_datetime: datetime, amortisation_method: str
) -> dict[str, ScheduledEvent]:
    """
    Create monthly scheduled event for due amount calculation, starting one month from account
    opening. This will also return the due date schedule if the schedule is not a no-repayment loan
    :param vault: vault object for the account that requires the schedule
    :param account_opening_datetime: when the account is opened/activated
    :return: event type to scheduled event
    """
    scheduled_events: dict[str, ScheduledEvent] = {}

    # offset is required so that the schedules are not ran on the first day.
    balloon_payment_start_date = account_opening_datetime + relativedelta(days=1)
    skip_due_date = no_repayment.is_no_repayment_loan(amortisation_method)
    balloon_payment_delta_days = _get_balloon_payment_delta_days(vault=vault)

    if skip_due_date:
        # No Repayment Loans
        total_term = int(
            utils.get_parameter(vault=vault, name=lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT)
        )
        # Balloon Payment date is the date where the balloon payment will be executed.
        balloon_payment_datetime = account_opening_datetime + relativedelta(
            months=total_term, days=balloon_payment_delta_days
        )

        balloon_payment_datetime = set_time_from_due_amount_parameter(
            vault=vault, from_datetime=balloon_payment_datetime
        )

        schedule_expr = utils.one_off_schedule_expression(balloon_payment_datetime)
        scheduled_events[BALLOON_PAYMENT_EVENT] = ScheduledEvent(
            start_datetime=balloon_payment_start_date, expression=schedule_expr
        )
        scheduled_events[
            due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT
        ] = utils.create_end_of_time_schedule(balloon_payment_start_date)
    else:
        # Minimum Repayment and Interest Only Loans

        # The Balloon payment event will be scheduled at a infinite time in the future so
        # the schedule remains active. It will be triggered by the final Due Date Calc.
        # the schedule start time is set to the day after the account opening date to
        # align behaviour to other schedules
        scheduled_events[BALLOON_PAYMENT_EVENT] = ScheduledEvent(
            start_datetime=balloon_payment_start_date, expression=utils.END_OF_TIME_EXPRESSION
        )

        # Attach the due amount calculation schedule to the Min Repayment and Interest only loans.
        scheduled_events.update(
            due_amount_calculation.scheduled_events(vault, account_opening_datetime)
        )

    return scheduled_events


def set_time_from_due_amount_parameter(
    vault: SmartContractVault, from_datetime: datetime
) -> datetime:
    return _set_datetime_from_parameter(
        vault=vault,
        parameter_prefix=due_amount_calculation.DUE_AMOUNT_CALCULATION_PREFIX,
        from_datetime=from_datetime,
    )


def _set_datetime_from_parameter(
    vault: SmartContractVault, parameter_prefix: str, from_datetime: datetime
) -> datetime:
    """
    replaces a datetime with the hours, minutes, and seconds set from a parameter config

    :param vault: smart contract vault object.
    :param parameter_prefix: the parameter prefix to replace the datetime object with.
    :param datetime: the datetime to mutate.
    :return: returns a datetime with the datetime set on a given parameter.
    """
    (
        param_hour,
        param_minute,
        param_second,
    ) = utils.get_schedule_time_from_parameters(vault=vault, parameter_prefix=parameter_prefix)
    return from_datetime.replace(hour=param_hour, minute=param_minute, second=param_second)


def update_balloon_payment_schedule(
    vault: SmartContractVault,
    execution_timestamp: datetime,
) -> list[UpdateAccountEventTypeDirective]:
    """
    this function will schedule a balloon payment for the predetermined amount of days
    after the execution timestamp and will skip the due amount calculation schedule.
    The execution timestamp should be time of the last due payment event.

    :param vault: vault object for the account that requires the schedule
    :param execution_timestamp: the execution timestamp of the last due payment.
    """
    balloon_payment_delta_days = _get_balloon_payment_delta_days(vault=vault)
    balloon_payment_time = execution_timestamp + relativedelta(days=balloon_payment_delta_days)
    balloon_payment_time = set_time_from_due_amount_parameter(
        vault=vault, from_datetime=balloon_payment_time
    )
    schedule_expr = utils.one_off_schedule_expression(balloon_payment_time)
    return [
        UpdateAccountEventTypeDirective(
            event_type=BALLOON_PAYMENT_EVENT,
            expression=schedule_expr,
            skip=False,
        ),
        UpdateAccountEventTypeDirective(
            event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
            expression=utils.END_OF_TIME_EXPRESSION,
            skip=True,
        ),
    ]


def _get_balloon_payment_delta_days(vault: SmartContractVault) -> int:
    return int(
        utils.get_parameter(
            vault=vault,
            name=PARAM_BALLOON_PAYMENT_DAYS_DELTA,
            is_optional=True,
            default_value=Decimal("0"),
        )
    )


def schedule_logic(
    vault: SmartContractVault,
    hook_arguments: ScheduledEventHookArguments,
    account_type: str = "",
    interest_application_feature: Optional[lending_interfaces.InterestApplication] = None,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    The schedule logic that is tied to the balloon payment event.
    This will transfer the existing outstanding principal to principal due.
    :param vault: vault object for the account
    :param hook_arguments: the scheduled event's hook arguments
    :param account_type: the account type, used for GL posting metadata purposes
    :param interest_application_feature: feature that is responsible for applying interest
    as part of the due amount calculation. This can be omitted if no interest is charged for
    a product (e.g. a 0% interest Pay-In-X loan)
    :param reamortisation_condition_features: a list of features used to determine whether
    reamortisation is required
    :param amortisation_feature: feature that is responsible for recalculating the emi if
    reamortisation is required (determined by the reamortisation_condition_features). To be provided
    if reamortisation_condition_features is also provided. If omitted and reamortisation is
    necessary then it will default to use the existing emi balance
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
    effective_datetime: datetime = hook_arguments.effective_datetime
    amortisation_method = utils.get_parameter(
        vault=vault, name="amortisation_method", is_union=True
    )

    # Not a valid balloon loan
    if not is_balloon_loan(amortisation_method=amortisation_method):
        return []

    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances

    if denomination is None:
        denomination = utils.get_parameter(vault=vault, name="denomination")

    current_principal = due_amount_calculation.get_principal(
        balances=balances, denomination=denomination
    )

    postings += due_amount_calculation.transfer_principal_due(
        customer_account=customer_account,
        principal_due=current_principal,
        denomination=denomination,
    )

    #  balloon_payment always moves all principal and accrued interest to due,
    # therefore previous_application_datetime is effective_datetime
    if interest_application_feature is not None:
        postings += interest_application_feature.apply_interest(
            vault=vault,
            effective_datetime=effective_datetime,
            previous_application_datetime=effective_datetime,
        )

    # Return Postings
    if postings:
        return [
            CustomInstruction(
                postings=postings,
                override_all_restrictions=True,
                instruction_details=utils.standard_instruction_details(
                    description="Updating due balances for final balloon payment.",
                    event_type=hook_arguments.event_type,
                    gl_impacted=True,
                    account_type=account_type,
                ),
            )
        ]
    else:
        return []


def is_balloon_loan(amortisation_method: str) -> bool:
    return any(
        [
            no_repayment.is_no_repayment_loan(amortisation_method=amortisation_method),
            minimum_repayment.is_minimum_repayment_loan(amortisation_method=amortisation_method),
            interest_only.is_interest_only_loan(amortisation_method=amortisation_method),
        ]
    )


def get_expected_balloon_payment_amount(
    vault: SmartContractVault,
    effective_datetime: datetime,
    balances: BalanceDefaultDict,
    interest_rate_feature: Optional[lending_interfaces.InterestRate] = None,
) -> Decimal:
    """
    Returns the expected balloon payment amount for a balloon payment loan, else returns Decimal(0)

    This assumes that the interest rate remains the same throughout the lifetime of the loan

    If the interest rate or the EMI is not calculated yet then return 0.
    """
    amortisation_method = utils.get_parameter(
        vault=vault, name="amortisation_method", is_union=True
    )

    principal = utils.balance_at_coordinates(
        balances=balances,
        address=lending_addresses.PRINCIPAL,
        denomination=utils.get_parameter(vault=vault, name="denomination"),
    )

    if no_repayment.is_no_repayment_loan(
        amortisation_method=amortisation_method
    ) or interest_only.is_interest_only_loan(amortisation_method=amortisation_method):
        # Applies a bugfix for when decimal is returned as Decimal("-0")
        if principal == Decimal("0.00"):
            return Decimal("0.00")
        return principal

    elif minimum_repayment.is_minimum_repayment_loan(amortisation_method=amortisation_method):
        # it is therefore a minimum repayment balloon loan
        balloon_payment_amount = utils.get_parameter(
            vault=vault, name=PARAM_BALLOON_PAYMENT_AMOUNT, is_optional=True
        )
        emi = utils.get_parameter(vault=vault, name=PARAM_BALLOON_EMI_AMOUNT, is_optional=True)
        if balloon_payment_amount is not None:
            # we do not allow overpayments for minimum repayment the balloon payment
            # amount will remain fixed so we can just return the
            # balloon_payment_amount parameter if it's set
            return balloon_payment_amount

        elif emi is not None:
            if interest_rate_feature is None:
                return Decimal("0")
            # the emi is predefined so we calculate the balloon payment amount by
            # rearranging the amortisation formula
            total_term = int(
                utils.get_parameter(
                    vault=vault,
                    name=lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT,
                )
            )

            monthly_interest_rate = interest_rate_feature.get_monthly_interest_rate(
                vault=vault, effective_datetime=effective_datetime
            )

            application_precision = int(
                utils.get_parameter(vault=vault, name="application_precision")
            )
            return calculate_lump_sum(
                emi=emi,
                principal=principal,
                rate=monthly_interest_rate,
                terms=total_term,
                precision=application_precision,
            )
        # Value is unsupported so return 0
    return Decimal("0")


def calculate_lump_sum(
    emi: Decimal, principal: Decimal, rate: Decimal, terms: int, precision: int = 2
) -> Decimal:
    """
     Amortisation Formula:
        EMI = (P-(L/(1+R)^(N)))*R*(((1+R)^N)/((1+R)^N-1))

    Re-arranging for L:
        L = (1+R)^(N)*(P - EMI/R) + EMI/R

    P is principal
    R is the monthly interest rate
    N is total term
    L is the lump sum
    """

    amount = (1 + rate) ** (terms) * (principal - emi / rate) + emi / rate
    return utils.round_decimal(amount=amount, decimal_places=precision)


def update_no_repayment_balloon_schedule(
    vault: SmartContractVault,
) -> dict[str, ScheduledEvent]:
    """
    to be called on a conversion hook only.
    will return the updated balloon payment schedule if the term length were ever to change
    """

    amortisation_method = utils.get_parameter(
        vault=vault, name="amortisation_method", is_union=True
    )

    _is_no_repayment_loan = no_repayment.is_no_repayment_loan(
        amortisation_method=amortisation_method
    )
    if not _is_no_repayment_loan:
        return {}

    # using the latest timeseries value here as doing a timeseries value comparison can
    # potentially lead to ghost effects on multiple conversions.
    # Example:
    # Conversion 1: Old Term:12, New term:24
    # Using the change in term length gives an additional 12 months
    # Conversion 2: Updating the amount but not the term.
    # Parameters will reflect the term change in Conversion 1 leading to
    # a 36 term after multiple conversions

    term_length = utils.get_parameter(
        vault=vault, name=lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT
    )

    account_opening_time = vault.get_account_creation_datetime()
    balloon_payment_delta_days = _get_balloon_payment_delta_days(vault=vault)
    balloon_payment_datetime = set_time_from_due_amount_parameter(
        vault=vault, from_datetime=account_opening_time
    )
    return {
        BALLOON_PAYMENT_EVENT: ScheduledEvent(
            # start time is not defined as this is overriden by the system to the conversion time.
            expression=utils.one_off_schedule_expression(
                balloon_payment_datetime
                + relativedelta(months=term_length, days=balloon_payment_delta_days)
            ),
        )
    }
