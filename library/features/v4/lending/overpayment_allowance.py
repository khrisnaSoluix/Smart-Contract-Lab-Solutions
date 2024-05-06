# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Mapping, Optional

# features
import library.features.v4.common.addresses as common_addresses
import library.features.v4.common.fees as fees
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.lending.lending_addresses as lending_addresses
import library.features.v4.lending.lending_interfaces as lending_interfaces
import library.features.v4.lending.overpayment as overpayment

# contracts api
from contracts_api import (
    DEFAULT_ASSET,
    AccountIdShape,
    BalanceCoordinate,
    BalanceDefaultDict,
    BalancesFilter,
    BalancesIntervalFetcher,
    BalancesObservationFetcher,
    BalanceTimeseries,
    CustomInstruction,
    DefinedDateTime,
    NumberShape,
    Override,
    Parameter,
    ParameterLevel,
    Phase,
    Posting,
    RelativeDateTime,
    ScheduledEvent,
    ScheduleSkip,
    Shift,
    SmartContractEventType,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# feature addresses
REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER = "REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER"

# TODO: Should move to a common location
PARAM_DENOMINATION = "denomination"

# fetchers
ONE_YEAR_OVERPAYMENT_ALLOWANCE_FETCHER_ID = "ONE_YEAR_OVERPAYMENT_ALLOWANCE"
ONE_YEAR_OVERPAYMENT_ALLOWANCE_INTERVAL_FETCHER_ID = "ONE_YEAR_OVERPAYMENT_ALLOWANCE_INTERVAL"
EOD_OVERPAYMENT_ALLOWANCE_FETCHER_ID = "EFFECTIVE_OVERPAYMENT_ALLOWANCE"

# This is for use in scenarios where we don't know when the start of the
# allowance period is (e.g. derived parameters) and must compute the start
# within the hook
one_year_overpayment_allowance_interval_fetcher = BalancesIntervalFetcher(
    fetcher_id=ONE_YEAR_OVERPAYMENT_ALLOWANCE_INTERVAL_FETCHER_ID,
    start=RelativeDateTime(
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        shift=Shift(years=-1),
        find=Override(hour=0, minute=0, second=0),
    ),
    end=DefinedDateTime.EFFECTIVE_DATETIME,
    filter=BalancesFilter(addresses=[overpayment.OVERPAYMENT, lending_addresses.PRINCIPAL]),
)
one_year_overpayment_allowance_fetcher = BalancesObservationFetcher(
    fetcher_id=ONE_YEAR_OVERPAYMENT_ALLOWANCE_FETCHER_ID,
    at=RelativeDateTime(
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        shift=Shift(years=-1),
        find=Override(hour=0, minute=0, second=0),
    ),
    filter=BalancesFilter(addresses=[overpayment.OVERPAYMENT, lending_addresses.PRINCIPAL]),
)
eod_overpayment_allowance_fetcher = BalancesObservationFetcher(
    fetcher_id=EOD_OVERPAYMENT_ALLOWANCE_FETCHER_ID,
    at=RelativeDateTime(
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
    filter=BalancesFilter(
        addresses=[
            REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
            lending_addresses.PRINCIPAL,
            overpayment.OVERPAYMENT,
        ]
    ),
)

CHECK_OVERPAYMENT_ALLOWANCE_EVENT = "CHECK_OVERPAYMENT_ALLOWANCE"
PARAM_OVERPAYMENT_ALLOWANCE_PERCENTAGE = "overpayment_allowance_percentage"
PARAM_OVERPAYMENT_ALLOWANCE_REMAINING = "overpayment_allowance_remaining"
PARAM_OVERPAYMENT_ALLOWANCE_USED = "overpayment_allowance_used"
PARAM_OVERPAYMENT_ALLOWANCE_FEE = "overpayment_allowance_fee"
PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE = "overpayment_allowance_fee_percentage"
PARAM_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT = "overpayment_allowance_fee_income_account"
CHECK_OVERPAYMENT_ALLOWANCE_PREFIX = "check_overpayment_allowance"
PARAM_CHECK_OVERPAYMENT_ALLOWANCE_HOUR = f"{CHECK_OVERPAYMENT_ALLOWANCE_PREFIX}_hour"
PARAM_CHECK_OVERPAYMENT_ALLOWANCE_MINUTE = f"{CHECK_OVERPAYMENT_ALLOWANCE_PREFIX}_minute"
PARAM_CHECK_OVERPAYMENT_ALLOWANCE_SECOND = f"{CHECK_OVERPAYMENT_ALLOWANCE_PREFIX}_second"

overpayment_allowance_percentage_param = Parameter(
    name=PARAM_OVERPAYMENT_ALLOWANCE_PERCENTAGE,
    shape=NumberShape(min_value=Decimal("0"), max_value=Decimal("1"), step=Decimal("0.0001")),
    level=ParameterLevel.TEMPLATE,
    description="Percent of outstanding principal that can be paid off per year without charge.",
    display_name="Allowed Overpayment Percentage",
    default_value=Decimal("0.1"),
)
overpayment_allowance_fee_percentage_param = Parameter(
    name=PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE,
    shape=NumberShape(min_value=Decimal("0"), max_value=Decimal("1"), step=Decimal("0.0001")),
    level=ParameterLevel.TEMPLATE,
    description="Percentage of excess allowance charged as a fee when going over "
    "overpayment allowance.",
    display_name="Overpayment Fee Percentage",
    default_value=Decimal("0.05"),
)
overpayment_allowance_fee_income_account_param = Parameter(
    name=PARAM_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT,
    level=ParameterLevel.TEMPLATE,
    shape=AccountIdShape(),
    description="Internal account for overpayment allowance fee income balance.",
    display_name="Overpayment Allowance Fee Income Account",
    default_value="OVERPAYMENT_ALLOWANCE_FEE_INCOME",
)
check_overpayment_allowance_hour_param = Parameter(
    name=PARAM_CHECK_OVERPAYMENT_ALLOWANCE_HOUR,
    shape=NumberShape(min_value=0, max_value=23, step=1),
    level=ParameterLevel.TEMPLATE,
    description="The hour of the day at which the overpayment allowance usage is checked.",
    display_name="Check Overpayment Allowance Hour",
    default_value=0,
)
check_overpayment_allowance_minute_param = Parameter(
    name=PARAM_CHECK_OVERPAYMENT_ALLOWANCE_MINUTE,
    shape=NumberShape(min_value=0, max_value=59, step=1),
    level=ParameterLevel.TEMPLATE,
    description="The minute of the day at which which overpayment allowance usage is checked.",
    display_name="Check Overpayment Allowance Minute",
    default_value=0,
)
check_overpayment_allowance_second_param = Parameter(
    name=PARAM_CHECK_OVERPAYMENT_ALLOWANCE_SECOND,
    shape=NumberShape(min_value=0, max_value=59, step=1),
    level=ParameterLevel.TEMPLATE,
    description="The second of the day at which which overpayment allowance usage is checked.",
    display_name="Check Overpayment Allowance Second",
    default_value=0,
)
overpayment_allowance_remaining_param = Parameter(
    name=PARAM_OVERPAYMENT_ALLOWANCE_REMAINING,
    shape=NumberShape(min_value=0),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Remaining overpayment allowance that can be used without incurring a fee in the "
    "current allowance period.",
    display_name="Overpayment Allowance Remaining",
)
overpayment_allowance_used_param = Parameter(
    name=PARAM_OVERPAYMENT_ALLOWANCE_USED,
    shape=NumberShape(min_value=0),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="The overpayment allowance used in the current allowance period.",
    display_name="Overpayment Allowance Used This Period",
)
overpayment_allowance_fee_param = Parameter(
    name=PARAM_OVERPAYMENT_ALLOWANCE_FEE,
    shape=NumberShape(),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Overpayment allowance fee charged on the current overpayment balance",
    display_name="Overpayment Allowance Fee",
)

allowance_schedule_time_parameters = [
    check_overpayment_allowance_hour_param,
    check_overpayment_allowance_minute_param,
    check_overpayment_allowance_second_param,
]

allowance_fee_parameters = [
    overpayment_allowance_percentage_param,
    overpayment_allowance_fee_percentage_param,
    overpayment_allowance_fee_income_account_param,
]

derived_parameters = [
    overpayment_allowance_used_param,
    overpayment_allowance_remaining_param,
    overpayment_allowance_fee_param,
]


def event_types(account_type: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=CHECK_OVERPAYMENT_ALLOWANCE_EVENT,
            scheduler_tag_ids=[f"{account_type.upper()}_{CHECK_OVERPAYMENT_ALLOWANCE_EVENT}_AST"],
        )
    ]


def scheduled_events(
    vault: SmartContractVault,
    allowance_period_start_datetime: datetime,
) -> dict[str, ScheduledEvent]:
    """
    Create scheduled event to check the overpayment allowance on account opening anniversary
    :param vault: vault object for the account that requires the schedule
    :param allowance_period_start_datetime: the datetime on which the yearly allowance
    starts. The time components are ignored. The schedule will run one year from this
    :return: Schedule events for the yearly overpayment allowance check
    """

    one_year_from_period_start = allowance_period_start_datetime.replace(
        hour=0, minute=0, second=0, microsecond=0
    ) + relativedelta(years=1)

    return {
        CHECK_OVERPAYMENT_ALLOWANCE_EVENT: ScheduledEvent(
            # start_datetime is exclusive, so offset by 1s to support running at midnight exactly
            start_datetime=one_year_from_period_start - relativedelta(seconds=1),
            expression=utils.get_schedule_expression_from_parameters(
                vault=vault,
                parameter_prefix=CHECK_OVERPAYMENT_ALLOWANCE_PREFIX,
                day=one_year_from_period_start.day,
                month=one_year_from_period_start.month,
            ),
        )
    }


def update_scheduled_event(
    vault: SmartContractVault,
    effective_datetime: datetime,
) -> dict[str, ScheduledEvent]:
    """
    Re-anchor the schedule event to check the overpayment allowance on the anniversary of the
    effective datetime. This must only be used in the conversion hook as start_datetime is omitted

    :param vault: vault object for the account that requires the schedule
    :param effective_datetime: the datetime on which the yearly allowance is anchored on.
    The time components are ignored. The schedule will run one year from this
    :return: Schedule events for the yearly overpayment allowance check
    """

    one_year_from_effective_datetime = effective_datetime.replace(
        hour=0, minute=0, second=0, microsecond=0
    ) + relativedelta(years=1)

    return {
        CHECK_OVERPAYMENT_ALLOWANCE_EVENT: ScheduledEvent(
            expression=utils.get_schedule_expression_from_parameters(
                vault=vault,
                parameter_prefix=CHECK_OVERPAYMENT_ALLOWANCE_PREFIX,
                day=one_year_from_effective_datetime.day,
                month=one_year_from_effective_datetime.month,
            ),
            # as we can't update the start datetime of the event we must skip until just before we
            # expect it to run again
            skip=ScheduleSkip(end=one_year_from_effective_datetime + relativedelta(seconds=-1)),
        )
    }


def get_allowance_for_period(
    start_of_period_balances: BalanceDefaultDict, allowance_percentage: Decimal, denomination: str
) -> Decimal:
    """Determine the allowance for the period

    :param start_of_period_balances: balances at start of the allowance period
    :param allowance_percentage: percentage of principal at start of allowance period that can be
    overpaid
    :param denomination: denomination of the account
    :return: the allowance for the period
    """
    return get_allowance(
        principal=utils.balance_at_coordinates(
            balances=start_of_period_balances,
            address=lending_addresses.PRINCIPAL,
            denomination=denomination,
        ),
        allowance_percentage=allowance_percentage,
    )


def get_allowance(principal: Decimal, allowance_percentage: Decimal) -> Decimal:
    """Determine the allowance for a given principal

    :param principal: the principal to use in the allowance calculation
    :param allowance_percentage: the percentage of principal included in the allowance
    :return: the allowance for the period
    """
    return utils.round_decimal(
        amount=allowance_percentage * principal,
        decimal_places=2,
    )


def get_allowance_usage(
    start_of_period_balances: BalanceDefaultDict,
    end_of_period_balances: BalanceDefaultDict,
    denomination: str,
) -> Decimal:
    """Determine the allowance usage over the allowance period

    :param start_of_period_balances: balances at start of the allowance period
    :param end_of_period_balances: balances at end of the allowance period
    :param denomination: denomination of the account
    :return: the allowance usage over the allowance period
    """

    used_allowance = utils.balance_at_coordinates(
        balances=end_of_period_balances,
        address=overpayment.OVERPAYMENT,
        denomination=denomination,
    ) - utils.balance_at_coordinates(
        balances=start_of_period_balances,
        address=overpayment.OVERPAYMENT,
        denomination=denomination,
    )

    # it's theoretically possible for the net OVERPAYMENT balance to have decreased
    used_allowance = max(used_allowance, Decimal(0))

    return used_allowance


def get_allowance_usage_fee(
    allowance: Decimal, used_allowance: Decimal, overpayment_allowance_fee_percentage: Decimal
) -> Decimal:
    """Determine the fee amount to charge

    :param allowance: the allowance for the period
    :param used_allowance: the used allowance for the period
    :param overpayment_allowance_fee_percentage: the percentage of excess used allowance to charge
    :return: the fee amount, which can be 0
    """
    if used_allowance <= allowance:
        return Decimal(0)

    return utils.round_decimal(
        overpayment_allowance_fee_percentage * (used_allowance - allowance), decimal_places=2
    )


def handle_allowance_usage(
    vault: SmartContractVault,
    account_type: str,
) -> list[CustomInstruction]:
    """Checks the overpayments in the past year and charges a fee if the total exceeds the
    allowance. For use inside the annual schedule when the start of allowance is at
    a fixed delta from the effective date.

    :param vault: vault object for the account with an overpayment allowance to check
    :param account_type: the account's type, used for posting metadata purposes
    :return: CustomInstructions for any required fees
    """
    posting_instructions: list[CustomInstruction] = []
    denomination: str = utils.get_parameter(vault=vault, name="denomination")
    overpayment_percentage: Decimal = utils.get_parameter(
        vault=vault, name=PARAM_OVERPAYMENT_ALLOWANCE_PERCENTAGE
    )
    overpayment_allowance_fee_percentage: Decimal = utils.get_parameter(
        vault=vault, name=PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE
    )
    overpayment_allowance_fee_income_account: str = utils.get_parameter(
        vault=vault, name=PARAM_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT
    )

    start_of_period_balances = vault.get_balances_observation(
        fetcher_id=ONE_YEAR_OVERPAYMENT_ALLOWANCE_FETCHER_ID
    ).balances
    end_of_period_balances = vault.get_balances_observation(
        fetcher_id=EOD_OVERPAYMENT_ALLOWANCE_FETCHER_ID
    ).balances

    # the overpayment allowance tracker balance needs to be
    # updated with the new overpayment allowance amount every
    # time the overpayment allowance check schedule runs
    # since the tracker is tracking the allowance of the period that is
    # about to start, get_allowance_for_period needs the balances for the
    # upcoming period, i.e. the end_of_period_balances
    current_overpayment_allowance = utils.balance_at_coordinates(
        balances=end_of_period_balances,
        address=REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
        denomination=denomination,
    )

    updated_overpayment_allowance = get_allowance_for_period(
        start_of_period_balances=end_of_period_balances,
        allowance_percentage=overpayment_percentage,
        denomination=denomination,
    )

    posting_instructions += set_overpayment_allowance_for_period(
        current_overpayment_allowance=current_overpayment_allowance,
        updated_overpayment_allowance=updated_overpayment_allowance,
        denomination=denomination,
        account_id=vault.account_id,
    )

    posting_instructions += _handle_allowance_usage_inner(
        account_id=vault.account_id,
        account_type=account_type,
        start_of_period_balances=start_of_period_balances,
        end_of_period_balances=end_of_period_balances,
        denomination=denomination,
        overpayment_percentage=overpayment_percentage,
        overpayment_allowance_fee_percentage=overpayment_allowance_fee_percentage,
        overpayment_allowance_fee_income_account=overpayment_allowance_fee_income_account,
    )

    return posting_instructions


def handle_allowance_usage_adhoc(
    vault: SmartContractVault, account_type: str, effective_datetime: datetime
) -> list[CustomInstruction]:
    """Checks the overpayments in the past year and charges a fee if the total exceeds the
    allowance. For use inside ad-hoc hook executions, such as conversion or deactivation,
    where the start_of_period is not at a fixed delta from the effective date.

    :param vault: vault object for the account with an overpayment allowance to check
    :param account_type: the account's type, used for posting metadata purposes
    :param effective_datetime: when the request to handle the usage is made
    """
    # data extraction
    denomination: str = utils.get_parameter(vault=vault, name="denomination")
    overpayment_percentage: Decimal = utils.get_parameter(
        vault=vault, name=PARAM_OVERPAYMENT_ALLOWANCE_PERCENTAGE
    )
    overpayment_allowance_fee_percentage: Decimal = utils.get_parameter(
        vault=vault, name=PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE
    )
    overpayment_allowance_fee_income_account: str = utils.get_parameter(
        vault=vault, name=PARAM_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT
    )

    one_year_balances = vault.get_balances_timeseries(
        fetcher_id=ONE_YEAR_OVERPAYMENT_ALLOWANCE_INTERVAL_FETCHER_ID
    )

    start_of_period_datetime = get_start_of_current_allowance_period(
        effective_datetime=effective_datetime,
        account_creation_datetime=vault.get_account_creation_datetime(),
        check_overpayment_allowance_last_execution_datetime=vault.get_last_execution_datetime(
            event_type=CHECK_OVERPAYMENT_ALLOWANCE_EVENT
        ),
    )

    start_of_period_balances = _extract_balance_default_dict_from_interval(
        denomination=denomination,
        balance_interval=one_year_balances,
        effective_datetime=start_of_period_datetime,
    )
    end_of_period_balances = _extract_balance_default_dict_from_interval(
        denomination=denomination,
        balance_interval=one_year_balances,
        effective_datetime=effective_datetime,
    )

    # core logic + transformation
    return _handle_allowance_usage_inner(
        account_id=vault.account_id,
        account_type=account_type,
        start_of_period_balances=start_of_period_balances,
        end_of_period_balances=end_of_period_balances,
        denomination=denomination,
        overpayment_percentage=overpayment_percentage,
        overpayment_allowance_fee_percentage=overpayment_allowance_fee_percentage,
        overpayment_allowance_fee_income_account=overpayment_allowance_fee_income_account,
    )


def _handle_allowance_usage_inner(
    account_id: str,
    account_type: str,
    start_of_period_balances: BalanceDefaultDict,
    end_of_period_balances: BalanceDefaultDict,
    denomination: str,
    overpayment_percentage: Decimal,
    overpayment_allowance_fee_percentage: Decimal,
    overpayment_allowance_fee_income_account: str,
) -> list[CustomInstruction]:

    # core logic
    used_allowance = get_allowance_usage(
        start_of_period_balances=start_of_period_balances,
        end_of_period_balances=end_of_period_balances,
        denomination=denomination,
    )

    allowance = get_allowance_for_period(
        start_of_period_balances=start_of_period_balances,
        allowance_percentage=overpayment_percentage,
        denomination=denomination,
    )

    fee_amount = get_allowance_usage_fee(
        used_allowance=used_allowance,
        allowance=allowance,
        overpayment_allowance_fee_percentage=overpayment_allowance_fee_percentage,
    )

    # transformation
    return fees.fee_custom_instruction(
        customer_account_id=account_id,
        denomination=denomination,
        amount=fee_amount,
        internal_account=overpayment_allowance_fee_income_account,
        customer_account_address=lending_addresses.PENALTIES,
        instruction_details=utils.standard_instruction_details(
            description=f"Overpayment fee charged due to used allowance {used_allowance} "
            f"{denomination} exceeding allowance {allowance} {denomination}",
            event_type="CHARGE_OVERPAYMENT_FEE",
            gl_impacted=True,
            account_type=account_type,
        ),
    )


def _extract_balance_default_dict_from_interval(
    denomination: str,
    balance_interval: Mapping[BalanceCoordinate, BalanceTimeseries],
    effective_datetime: datetime,
) -> BalanceDefaultDict:
    overpayment_coordinate = BalanceCoordinate(
        account_address=overpayment.OVERPAYMENT,
        asset=DEFAULT_ASSET,
        denomination=denomination,
        phase=Phase.COMMITTED,
    )
    principal_coordinate = BalanceCoordinate(
        account_address=lending_addresses.PRINCIPAL,
        asset=DEFAULT_ASSET,
        denomination=denomination,
        phase=Phase.COMMITTED,
    )
    overpayment_at_effective_datetime = balance_interval[overpayment_coordinate].at(
        at_datetime=effective_datetime
    )
    principal_at_effective_datetime = balance_interval[principal_coordinate].at(
        at_datetime=effective_datetime
    )

    return BalanceDefaultDict(
        mapping={
            overpayment_coordinate: overpayment_at_effective_datetime,
            principal_coordinate: principal_at_effective_datetime,
        }
    )


def get_overpayment_allowance_status(
    vault: SmartContractVault, effective_datetime: datetime
) -> tuple[Decimal, Decimal]:
    """Determines the original and used overpayment allowance for the current allowance period.
    For use in adhoc situations (e.g. derived parameters)
    Both numbers should be >= 0, but there is no strict relationship between the two (i.e.
    used allowance can be >,=, < original allowance).

    :param vault: vault object for the relevant account
    :param effective_datetime: datetime for which the overpayment status is calculated
    :return: the original and used overpayment allowance
    """

    denomination: str = utils.get_parameter(vault=vault, name="denomination")
    one_year_balances = vault.get_balances_timeseries(
        fetcher_id=ONE_YEAR_OVERPAYMENT_ALLOWANCE_INTERVAL_FETCHER_ID
    )
    start_of_period_datetime = get_start_of_current_allowance_period(
        effective_datetime=effective_datetime,
        account_creation_datetime=vault.get_account_creation_datetime(),
        check_overpayment_allowance_last_execution_datetime=vault.get_last_execution_datetime(
            event_type=CHECK_OVERPAYMENT_ALLOWANCE_EVENT
        ),
    )
    allowance_percentage = utils.get_parameter(
        vault=vault,
        name=PARAM_OVERPAYMENT_ALLOWANCE_PERCENTAGE,
        at_datetime=start_of_period_datetime,
    )

    start_of_period_balances = _extract_balance_default_dict_from_interval(
        denomination=denomination,
        balance_interval=one_year_balances,
        effective_datetime=start_of_period_datetime,
    )
    end_of_period_balances = _extract_balance_default_dict_from_interval(
        denomination=denomination,
        balance_interval=one_year_balances,
        effective_datetime=effective_datetime,
    )

    overpayment_allowance_used = get_allowance_usage(
        start_of_period_balances=start_of_period_balances,
        end_of_period_balances=end_of_period_balances,
        denomination=denomination,
    )

    overpayment_allowance = get_allowance_for_period(
        start_of_period_balances=start_of_period_balances,
        allowance_percentage=allowance_percentage,
        denomination=denomination,
    )

    return overpayment_allowance, overpayment_allowance_used


def get_start_of_current_allowance_period(
    effective_datetime: datetime,
    account_creation_datetime: datetime,
    check_overpayment_allowance_last_execution_datetime: Optional[datetime] = None,
) -> datetime:
    """Determines the start of the allowance period in progress. The initial allowance period
    starts on account creation date and then restarts at midnight on the account creation
    anniversary.

    :param effective_datetime: defines
    :param account_creation_datetime: datetime that the account was created on
    :param handle_allowance_usage_last_execution_datetime: when the handle allowance usage schedule
    last ran, if ever
    :return: the start of the allowance period
    """
    if check_overpayment_allowance_last_execution_datetime is not None:
        return check_overpayment_allowance_last_execution_datetime.replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    one_year_ago = effective_datetime.replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - relativedelta(years=1)

    # we must leave time components on account creation as the period cannot start before the
    # account was actually created
    return max(account_creation_datetime, one_year_ago)


def set_overpayment_allowance_for_period(
    current_overpayment_allowance: Decimal,
    updated_overpayment_allowance: Decimal,
    denomination: str,
    account_id: str,
) -> list[CustomInstruction]:
    """
    Sets the overpayment allowance amount for the current period by initialising the overpayment
    allowance tracker balance with this amount.

    NOTE: This function uses the overpayment allowance tracker balance to track the overpayment
    allowance, and so it likely duplicates work that exists in other functions in this feature.
    This feature should be refactored to remove this duplication by relying only on the
    overpayment allowance tracker balance.
    See https://pennyworth.atlassian.net/browse/INC-8754

    :param current_overpayment_allowance: The overpayment allowance amount
    currently in the overpayment allowance tracker balance.
    :param updated_overpayment_allowance: The overpayment allowance amount for the next period
    :param denomination: The denomination of the loan being repaid
    :param account_id: The id of the loan account
    :return: The list of postings to set the overpayment allowance tracker balance
    to the overpayment allowance amount
    """

    postings: list[Posting] = []

    overpayment_allowance_delta = current_overpayment_allowance - updated_overpayment_allowance

    if overpayment_allowance_delta == Decimal("0"):
        return []

    if overpayment_allowance_delta < Decimal("0"):
        credit_address = common_addresses.INTERNAL_CONTRA
        debit_address = REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER
        overpayment_allowance_delta = abs(overpayment_allowance_delta)
    else:
        credit_address = REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER
        debit_address = common_addresses.INTERNAL_CONTRA

    postings = utils.create_postings(
        amount=overpayment_allowance_delta,
        debit_account=account_id,
        debit_address=debit_address,
        credit_account=account_id,
        credit_address=credit_address,
        denomination=denomination,
    )

    return [
        CustomInstruction(
            postings=postings,
            instruction_details={
                "description": "Resetting the overpayment allowance tracker balance",
                "event": "RESET_REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER",
            },
        )
    ]


def reduce_overpayment_allowance(
    vault: SmartContractVault,
    overpayment_amount: Decimal,
    denomination: str,
    balances: BalanceDefaultDict,
) -> list[Posting]:
    """
    Creates postings to update the overpayment allowance tracker by removing
    the overpayment amount from the overpayment allowance for the
    current allowance period.

    NOTE: This function uses the overpayment allowance tracker balance to track the overpayment
    allowance, and so it likely duplicates work that exists in other functions in this feature.
    This feature should be refactored to remove this duplication by relying only on the
    overpayment allowance tracker balance.
    See https://pennyworth.atlassian.net/browse/INC-8754

    :param vault: The vault object for the account receiving the overpayment
    :param overpayment_amount: The amount overpaid
    :param denomination: The denomination of the repayment / loan being repaid
    :param balances: The balances at the point of overpayment
    :return: The corresponding postings to update the overpayment allowance tracker balance
    """
    postings: list[Posting] = []

    outstanding_principal = utils.balance_at_coordinates(
        balances=balances,
        address=lending_addresses.PRINCIPAL,
        denomination=denomination,
    )

    # since an overpayment can also pay off accrued interest, it is technically
    # possible for an overpayment to be greater than the outstanding principal on the
    # loan, which is why the check below is needed
    if (overpayment_posting_amount := min(overpayment_amount, outstanding_principal)) > Decimal(
        "0"
    ):
        postings += utils.create_postings(
            amount=overpayment_posting_amount,
            debit_account=vault.account_id,
            debit_address=common_addresses.INTERNAL_CONTRA,
            credit_account=vault.account_id,
            credit_address=REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
            denomination=denomination,
        )

    return postings


def get_overpayment_allowance_fee_for_early_repayment(
    vault: SmartContractVault,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
) -> Decimal:
    """
    Calculates the overpayment allowance fee if the total amount on the loan were to be repaid.

    NOTE: This function uses the overpayment allowance tracker balance to calculate the
    overpayment allowance fee, and so it likely duplicates work that exists in other
    functions in this feature. This feature should be refactored to remove this duplication
    by relying only on the overpayment allowance tracker balance.
    See https://pennyworth.atlassian.net/browse/INC-8754

    :param overpayment_allowance_fee_percentage: The percentage of the exceeded overpayment
    allowance amount that gets charged as a fee
    :param denomination: The denomination of the loan being repaid
    :param balances: The balances at the time of overpayment
    :return: The overpayment allowance fee
    """
    if denomination is None:
        denomination = utils.get_parameter(vault=vault, name=PARAM_DENOMINATION)

    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances

    overpayment_allowance_fee_percentage = utils.get_parameter(
        vault=vault, name=PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE
    )

    total_outstanding_debt = utils.sum_balances(
        balances=balances,
        addresses=lending_addresses.ALL_OUTSTANDING,
        denomination=denomination,
    )

    due_amount = utils.sum_balances(
        balances=balances,
        addresses=lending_addresses.REPAYMENT_HIERARCHY,
        denomination=denomination,
    )

    # any amount paid towards a due balance does not count as an overpayment amount
    overpayment_needed_to_completely_repay_loan = total_outstanding_debt - due_amount

    # The overpayment allowance tracker balance is initialized with the total amount
    # that is allowed to be overpaid before a fee is charged. Every time an overpayment
    # occurs, the overpayment amount is subtracted from the overpayment allowance tracker
    # balance. This means that we need to subtract the theoretical overpayment amount
    # that is needed to completely repay the loan from the tracker balance
    # in order to properly calculate the current overpayment allowance used.
    inflight_overpayment_allowance_amount = (
        utils.balance_at_coordinates(
            balances=balances,
            address=REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
            denomination=denomination,
        )
        - overpayment_needed_to_completely_repay_loan
    )

    # If the overpayment allowance tracker balance is non-negative, it means
    # the customer has not yet exceeded the overpayment allowance amount.
    # If the tracker balance is negative, the customer has exceeded the overpayment
    # allowance amount by the tracker balance amount.
    overpayment_allowance_exceeded_amount = (
        abs(inflight_overpayment_allowance_amount)
        if inflight_overpayment_allowance_amount < Decimal("0")
        else Decimal("0")
    )

    return utils.round_decimal(
        amount=overpayment_allowance_fee_percentage * overpayment_allowance_exceeded_amount,
        decimal_places=2,
    )


def initialise_overpayment_allowance_from_principal_amount(
    vault: SmartContractVault,
    principal: Decimal,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Returns the postings needed to set the overpayment allowance amount to the
    principal * the overpayment allowance percentage and assumes no previous
    overpayment allowance tracker balance exists. In other words, this function
    is intended to be used in the activation hook.

    NOTE: This function uses the overpayment allowance tracker balance to calculate the
    overpayment allowance fee, and so it likely duplicates work that exists in other
    functions in this feature. This feature should be refactored to remove this duplication
    by relying only on the overpayment allowance tracker balance.
    See https://pennyworth.atlassian.net/browse/INC-8754

    :param vault: The vault object
    :param principal: The principal from which to calculate the overpayment allowance
    :param denomination: The denomination of the loan being repaid
    :return: The postings to set the overpayment allowance as a percent of the principal
    """

    if denomination is None:
        denomination = utils.get_parameter(vault=vault, name=PARAM_DENOMINATION)

    overpayment_allowance_percentage: Decimal = utils.get_parameter(
        vault=vault, name=PARAM_OVERPAYMENT_ALLOWANCE_PERCENTAGE
    )

    return set_overpayment_allowance_for_period(
        current_overpayment_allowance=Decimal("0"),
        updated_overpayment_allowance=principal * overpayment_allowance_percentage,
        denomination=denomination,  # type: ignore
        account_id=vault.account_id,
    )


def get_residual_cleanup_postings(
    balances: BalanceDefaultDict, account_id: str, denomination: str
) -> list[Posting]:
    """
    Returns the postings needed to cleanup the overpayment allowance tracker balance.

    :param balances: The balances, including the overpayment allowance tracker balance,
    that need to be cleared.
    :param account_id: The id of the loan account
    :param denomination: The denomination of the loan being repaid
    :return: A list of postings to net out the overpayment allowance tracker balance
    """
    overpayment_allowance_amount = utils.balance_at_coordinates(
        balances=balances,
        address=REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
        denomination=denomination,
    )

    return utils.create_postings(
        amount=abs(overpayment_allowance_amount),
        debit_account=account_id,
        credit_account=account_id,
        debit_address=common_addresses.INTERNAL_CONTRA
        if overpayment_allowance_amount > 0
        else REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
        credit_address=REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER
        if overpayment_allowance_amount > 0
        else common_addresses.INTERNAL_CONTRA,
        denomination=denomination,
    )


OverpaymentAllowanceFeature = lending_interfaces.Overpayment(
    handle_overpayment=reduce_overpayment_allowance,
)

OverpaymentAllowanceResidualCleanupFeature = lending_interfaces.ResidualCleanup(
    get_residual_cleanup_postings=get_residual_cleanup_postings
)
