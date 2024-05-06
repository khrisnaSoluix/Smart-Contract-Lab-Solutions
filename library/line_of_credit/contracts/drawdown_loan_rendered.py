# Code auto-generated using Inception Smart Contract Renderer Version 2.0.1


# Objects below have been imported from:
#    drawdown_loan.py
# md5:99ca9e037d17294ee87de4e62ea71bb2

from contracts_api import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    AuthorisationAdjustment,
    Balance,
    BalanceCoordinate,
    BalanceDefaultDict,
    BalanceTimeseries,
    CalendarEvents,
    CustomInstruction,
    EndOfMonthSchedule,
    FlagTimeseries,
    InboundAuthorisation,
    InboundHardSettlement,
    OptionalValue,
    OutboundAuthorisation,
    OutboundHardSettlement,
    Phase,
    Posting,
    PostingInstructionType,
    Rejection,
    RejectionReason,
    Release,
    ScheduledEvent,
    ScheduleExpression,
    ScheduleFailover,
    ScheduleSkip,
    Settlement,
    Transfer,
    Tside,
    UnionItemValue,
    UpdateAccountEventTypeDirective,
    DenominationShape,
    Parameter,
    ParameterLevel,
    UnionItem,
    UnionShape,
    BalancesObservationFetcher,
    DefinedDateTime,
    Override,
    PostingsIntervalFetcher,
    RelativeDateTime,
    Shift,
    AccountNotificationDirective,
    PostingInstructionsDirective,
    PostPostingHookResult,
    ScheduledEventHookResult,
    SupervisorContractEventType,
    SupervisorScheduledEventHookArguments,
    UpdatePlanEventTypeDirective,
    NumberShape,
    ParameterUpdatePermission,
    AccountIdShape,
    DateShape,
    ScheduledEventHookArguments,
    SmartContractEventType,
    BalancesFilter,
    BalancesObservation,
    ActivationHookArguments,
    ActivationHookResult,
    DeactivationHookArguments,
    DeactivationHookResult,
    DerivedParameterHookArguments,
    DerivedParameterHookResult,
    PrePostingHookArguments,
    PrePostingHookResult,
    fetch_account_data,
    requires,
)
from calendar import isleap
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
from json import loads
import math
from typing import Optional, Any, Iterable, Mapping, Union, Callable, NamedTuple
from zoneinfo import ZoneInfo

api = "4.0.0"
version = "2.0.0"
display_name = "Line of Credit Drawdown Loan"
tside = Tside.ASSET
supported_denominations = ["GBP"]


@requires(parameters=True)
def activation_hook(
    vault: Any, hook_arguments: ActivationHookArguments
) -> Optional[ActivationHookResult]:
    effective_datetime = hook_arguments.effective_datetime
    deposit_account = _get_deposit_account_parameter(vault=vault)
    principal = _get_principal_parameter(vault=vault)
    denomination = common_parameters_get_denomination_parameter(vault=vault)
    loc_account_id = _get_loc_account_id_parameter(vault=vault)
    posting_instructions_directives: list[PostingInstructionsDirective] = []
    activation_custom_instructions: list[CustomInstruction] = []
    activation_custom_instructions.extend(
        disbursement_get_disbursement_custom_instruction(
            account_id=vault.account_id,
            deposit_account_id=deposit_account,
            principal=principal,
            denomination=denomination,
        )
    )
    activation_custom_instructions.extend(
        emi_amortise(
            vault=vault,
            effective_datetime=effective_datetime,
            amortisation_feature=declining_principal_AmortisationFeature,
            interest_calculation_feature=fixed_interest_rate_interface,
        )
    )
    if activation_custom_instructions:
        posting_instructions_directives.append(
            PostingInstructionsDirective(
                posting_instructions=activation_custom_instructions,
                client_batch_id=f"{ACCOUNT_TYPE}_{events_ACCOUNT_ACTIVATION}_{vault.get_hook_execution_id()}",
                value_datetime=effective_datetime,
            )
        )
        activation_aggregate_custom_instructions = (
            supervisor_utils_create_aggregate_posting_instructions(
                aggregate_account_id=loc_account_id,
                posting_instructions_by_supervisee={
                    vault.account_id: activation_custom_instructions
                },
                prefix="TOTAL",
                balances=BalanceDefaultDict(),
                addresses_to_aggregate=[lending_addresses_EMI, lending_addresses_PRINCIPAL],
                rounding_precision=utils_get_parameter(
                    vault=vault, name=interest_application_PARAM_APPLICATION_PRECISION
                ),
            )
        )
        activation_aggregate_custom_instructions += _get_original_principal_custom_instructions(
            principal=principal, loc_account_id=loc_account_id, denomination=denomination
        )
        if activation_aggregate_custom_instructions:
            posting_instructions_directives.append(
                PostingInstructionsDirective(
                    posting_instructions=activation_aggregate_custom_instructions,
                    client_batch_id=f"AGGREGATE_LOC_{ACCOUNT_TYPE}_{events_ACCOUNT_ACTIVATION}_{vault.get_hook_execution_id()}",
                    value_datetime=effective_datetime,
                )
            )
    return ActivationHookResult(posting_instructions_directives=posting_instructions_directives)


@fetch_account_data(balances=["live_balances_bof"])
@requires(parameters=True)
def deactivation_hook(
    vault: Any, hook_arguments: DeactivationHookArguments
) -> Optional[DeactivationHookResult]:
    balances = vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
    denomination = common_parameters_get_denomination_parameter(vault=vault)
    loc_account = _get_loc_account_id_parameter(vault=vault)
    principal = _get_principal_parameter(vault=vault)
    if outstanding_debt_rejection := close_loan_reject_closure_when_outstanding_debt(
        balances=balances,
        denomination=denomination,
        debt_addresses=lending_addresses_ALL_OUTSTANDING_SUPERVISOR,
    ):
        return DeactivationHookResult(rejection=outstanding_debt_rejection)
    loan_closure_custom_instructions = close_loan_net_balances(
        balances=balances,
        denomination=denomination,
        account_id=vault.account_id,
        residual_cleanup_features=[
            overpayment_OverpaymentResidualCleanupFeature,
            due_amount_calculation_DueAmountCalculationResidualCleanupFeature,
        ],
    )
    balances_after_closure_instructions = utils_update_inflight_balances(
        account_id=vault.account_id,
        tside=Tside.ASSET,
        current_balances=balances,
        posting_instructions=loan_closure_custom_instructions,
    )
    internal_contra_amount_after_closure_instructions = utils_balance_at_coordinates(
        balances=balances_after_closure_instructions,
        address=lending_addresses_INTERNAL_CONTRA,
        denomination=denomination,
    )
    repayments_postings = utils_create_postings(
        amount=internal_contra_amount_after_closure_instructions,
        debit_account=loc_account,
        credit_account=vault.account_id,
        debit_address=DEFAULT_ADDRESS,
        credit_address=lending_addresses_INTERNAL_CONTRA,
        denomination=denomination,
    )
    net_aggregate_emi_postings = _net_aggregate_emi(
        balances=balances, loc_account_id=loc_account, denomination=denomination
    )
    if repayments_postings or net_aggregate_emi_postings:
        loan_closure_custom_instructions.append(
            CustomInstruction(
                postings=repayments_postings + net_aggregate_emi_postings,
                instruction_details={
                    "description": "Clearing all residual balances",
                    "event": "END_OF_LOAN",
                    "force_override": "True",
                },
            )
        )
    loan_closure_custom_instructions += _get_original_principal_custom_instructions(
        principal=principal,
        loc_account_id=loc_account,
        denomination=denomination,
        is_closing_loan=True,
    )
    if loan_closure_custom_instructions:
        return DeactivationHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=loan_closure_custom_instructions,
                    value_datetime=hook_arguments.effective_datetime,
                )
            ]
        )
    return None


@fetch_account_data(balances=["EFFECTIVE_FETCHER"])
@requires(parameters=True)
def derived_parameter_hook(
    vault: Any, hook_arguments: DerivedParameterHookArguments
) -> DerivedParameterHookResult:
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    denomination = common_parameters_get_denomination_parameter(vault=vault)
    total_early_repayment_amount = early_repayment_get_total_early_repayment_amount(
        vault=vault,
        early_repayment_fees=[overpayment_EarlyRepaymentOverpaymentFee],
        balances=balances,
        denomination=denomination,
        debt_addresses=lending_addresses_ALL_OUTSTANDING_SUPERVISOR,
        check_for_outstanding_accrued_interest_on_zero_principal=True,
    )
    derived_parameters: dict[str, utils_ParameterValueTypeAlias] = {
        PARAM_PER_LOAN_EARLY_REPAYMENT_AMOUNT: total_early_repayment_amount
    }
    return DerivedParameterHookResult(parameters_return_value=derived_parameters)


def pre_posting_hook(
    vault: Any, hook_arguments: PrePostingHookArguments
) -> Optional[PrePostingHookResult]:
    if utils_is_force_override(posting_instructions=hook_arguments.posting_instructions):
        return None
    return PrePostingHookResult(
        rejection=Rejection(
            message="All postings should be made to the Line of Credit account",
            reason_code=RejectionReason.CLIENT_CUSTOM_REASON,
        )
    )


# Objects below have been imported from:
#    utils.py
# md5:b4718e1c735d11f6848158f777e7084f

utils_PostingInstructionListAlias = list[
    Union[
        AuthorisationAdjustment,
        CustomInstruction,
        InboundAuthorisation,
        InboundHardSettlement,
        OutboundAuthorisation,
        OutboundHardSettlement,
        Release,
        Settlement,
        Transfer,
    ]
]
utils_ParameterValueTypeAlias = Union[Decimal, str, datetime, OptionalValue, UnionItemValue, int]
utils_VALID_DAYS_IN_YEAR = ["360", "365", "366", "actual"]
utils_DEFAULT_DAYS_IN_YEAR = "actual"
utils_RATE_DECIMAL_PLACES = 10


def utils_str_to_bool(string: str) -> bool:
    """
    Convert a string true to bool True, default value of False.
    :param string:
    :return:
    """
    return str(string).lower() == "true"


def utils_round_decimal(
    amount: Decimal, decimal_places: int, rounding: str = ROUND_HALF_UP
) -> Decimal:
    """
    Round an amount to specified number of decimal places
    :param amount: Decimal, amount to round
    :param decimal_places: int, number of places to round to
    :param rounding: the type of rounding strategy to use
    :return: Decimal, rounded amount
    """
    return amount.quantize(Decimal((0, (1,), -int(decimal_places))), rounding=rounding)


def utils_yearly_to_daily_rate(
    effective_date: datetime, yearly_rate: Decimal, days_in_year: str = "actual"
) -> Decimal:
    """
    Calculate the daily rate from a yearly rate, for a given `days_in_year` convention and date
    :param effective_date: the date as of which the conversion happens. This may affect the outcome
    based on the `days_in_year` value.
    :param yearly_rate: the rate to convert
    :param days_in_year: the number of days in the year to assume for the calculation. One of `360`,
    `365`, `366` or `actual`. If actual is used, the number of days is based on effective_date's
    year
    :return: the corresponding daily rate
    """
    days_in_year = (
        days_in_year if days_in_year in utils_VALID_DAYS_IN_YEAR else utils_DEFAULT_DAYS_IN_YEAR
    )
    if days_in_year == "actual":
        num_days_in_year = Decimal("366") if isleap(effective_date.year) else Decimal("365")
    else:
        num_days_in_year = Decimal(days_in_year)
    return utils_round_decimal(
        yearly_rate / num_days_in_year, decimal_places=utils_RATE_DECIMAL_PLACES
    )


def utils_yearly_to_monthly_rate(yearly_rate: Decimal) -> Decimal:
    return utils_round_decimal(yearly_rate / 12, decimal_places=utils_RATE_DECIMAL_PLACES)


def utils_get_parameter(
    vault: Any,
    name: str,
    at_datetime: Optional[datetime] = None,
    is_json: bool = False,
    is_boolean: bool = False,
    is_union: bool = False,
    is_optional: bool = False,
    default_value: Optional[Any] = None,
) -> Any:
    """
    Get the parameter value for a given parameter
    :param vault:
    :param name: name of the parameter to retrieve
    :param at_datetime: datetime, time at which to retrieve the parameter value. If not
    specified the latest value is retrieved
    :param is_json: if true json_loads is called on the retrieved parameter value
    :param is_boolean: boolean parameters are treated as union parameters before calling
    str_to_bool on the retrieved parameter value
    :param is_union: if True parameter will be treated as a UnionItem
    :param is_optional: if true we treat the parameter as optional
    :param default_value: only used in conjunction with the is_optional arg, the value to use if the
    parameter is not set.
    :return: the parameter value, this is type hinted as Any because the parameter could be
    json loaded, therefore it value can be any json serialisable type and we gain little benefit
    from having an extensive Union list
    """
    if at_datetime:
        parameter = vault.get_parameter_timeseries(name=name).at(at_datetime=at_datetime)
    else:
        parameter = vault.get_parameter_timeseries(name=name).latest()
    if is_optional:
        parameter = parameter.value if parameter.is_set() else default_value
    if is_union and parameter is not None:
        parameter = parameter.key
    if is_boolean and parameter is not None:
        parameter = utils_str_to_bool(parameter.key)
    if is_json and parameter is not None:
        parameter = loads(parameter)
    return parameter


def utils_create_postings(
    amount: Decimal,
    debit_account: str,
    credit_account: str,
    debit_address: str = DEFAULT_ADDRESS,
    credit_address: str = DEFAULT_ADDRESS,
    denomination: str = "GBP",
    asset: str = DEFAULT_ASSET,
) -> list[Posting]:
    """
    Creates a pair of postings to debit the debit_address on debit_account
    and credit the credit_address on credit_account by the specified amount

    :param amount: The amount to pay. If the amount is <= 0, an empty list is returned
    :param debit_account: The account from which to debit the amount
    :param credit_account: The account to which to credit the amount
    :param debit_address: The address from which to move the amount
    :param credit_address: The address to which to move the amount
    :param denomination: The denomination of the postings
    :param asset: The asset of the postings
    :return: The credit-debit pair of postings
    """
    if amount <= Decimal("0"):
        return []
    return [
        Posting(
            credit=True,
            amount=amount,
            denomination=denomination,
            account_id=credit_account,
            account_address=credit_address,
            asset=asset,
            phase=Phase.COMMITTED,
        ),
        Posting(
            credit=False,
            amount=amount,
            denomination=denomination,
            account_id=debit_account,
            account_address=debit_address,
            asset=asset,
            phase=Phase.COMMITTED,
        ),
    ]


def utils_reset_tracker_balances(
    balances: BalanceDefaultDict,
    account_id: str,
    tracker_addresses: list[str],
    contra_address: str,
    denomination: str,
    tside: Tside,
) -> list[Posting]:
    """
    Resets the balance of the tracking addresses on an account back to zero. It is assumed the
    tracking addresses will always have a balance >= 0 and that the contra_address has been used
    for double entry bookkeeping purposes for all of the addresses in the tracker_addresses list.

    :param balances: balances of the account to be reset
    :param account_id: id of the customer account
    :param tracker_addresses: list of addresses to be cleared (balance assumed >= 0)
    :param contra_address: address that has been used for double entry bookkeeping purposes when
    originally updating the tracker address balances
    :param denomination: denomination of the account
    :param tside: Tside of the account, this is used to determine whether the tracker address is
    debited or credited since the tracker address is always assumed to have a balance >0
    """
    postings: list[Posting] = []
    for address in tracker_addresses:
        address_balance = utils_balance_at_coordinates(
            balances=balances, address=address, denomination=denomination
        )
        if address_balance > Decimal("0"):
            postings += utils_create_postings(
                amount=address_balance,
                debit_account=account_id,
                credit_account=account_id,
                debit_address=contra_address if tside == Tside.ASSET else address,
                credit_address=address if tside == Tside.ASSET else contra_address,
                denomination=denomination,
            )
    return postings


def utils_is_key_in_instruction_details(
    *, key: str, posting_instructions: utils_PostingInstructionListAlias
) -> bool:
    return all(
        (
            utils_str_to_bool(posting_instruction.instruction_details.get(key, "false"))
            for posting_instruction in posting_instructions
        )
    )


def utils_is_force_override(posting_instructions: utils_PostingInstructionListAlias) -> bool:
    return utils_is_key_in_instruction_details(
        key="force_override", posting_instructions=posting_instructions
    )


def utils_sum_balances(
    *,
    balances: BalanceDefaultDict,
    addresses: list[str],
    denomination: str,
    asset: str = DEFAULT_ASSET,
    phase: Phase = Phase.COMMITTED,
    decimal_places: Optional[int] = None,
) -> Decimal:
    balance_sum = Decimal(
        sum(
            (
                balances[BalanceCoordinate(address, asset, denomination, phase)].net
                for address in addresses
            )
        )
    )
    return (
        balance_sum
        if decimal_places is None
        else utils_round_decimal(amount=balance_sum, decimal_places=decimal_places)
    )


def utils_balance_at_coordinates(
    *,
    balances: BalanceDefaultDict,
    address: str = DEFAULT_ADDRESS,
    denomination: str,
    asset: str = DEFAULT_ASSET,
    phase: Phase = Phase.COMMITTED,
    decimal_places: Optional[int] = None,
) -> Decimal:
    balance_net = balances[BalanceCoordinate(address, asset, denomination, phase)].net
    return (
        balance_net
        if decimal_places is None
        else utils_round_decimal(amount=balance_net, decimal_places=decimal_places)
    )


def utils_update_inflight_balances(
    account_id: str,
    tside: Tside,
    current_balances: BalanceDefaultDict,
    posting_instructions: utils_PostingInstructionListAlias,
) -> BalanceDefaultDict:
    """
    Returns a new BalanceDefaultDict, merging the current balances with the posting balances

    :param account_id: id of the vault account, required for the .balances() method
    :param tside: tside of the account, required for the .balances() method
    :param current_balances: the current balances to be merged with the posting balances
    :param posting_instructions: list of posting instruction objects to get the balances of to
    merge with the current balances
    :return: A new BalanceDefaultDict with the merged balances
    """
    inflight_balances = BalanceDefaultDict(mapping=current_balances)
    for posting_instruction in posting_instructions:
        inflight_balances += posting_instruction.balances(account_id=account_id, tside=tside)
    return inflight_balances


# Objects below have been imported from:
#    common_parameters.py
# md5:11b3b3b4a92b1dc6ec77a2405fb2ca6d

common_parameters_BooleanShape = UnionShape(
    items=[UnionItem(key="True", display_name="True"), UnionItem(key="False", display_name="False")]
)
common_parameters_BooleanValueTrue = UnionItemValue(key="True")
common_parameters_PARAM_DENOMINATION = "denomination"
common_parameters_denomination_parameter = Parameter(
    name=common_parameters_PARAM_DENOMINATION,
    shape=DenominationShape(),
    level=ParameterLevel.TEMPLATE,
    description="Currency in which the product operates.",
    display_name="Denomination",
    default_value="GBP",
)


def common_parameters_get_denomination_parameter(
    vault: Any, effective_datetime: Optional[datetime] = None
) -> str:
    denomination: str = utils_get_parameter(
        vault=vault, name=common_parameters_PARAM_DENOMINATION, at_datetime=effective_datetime
    )
    return denomination


# Objects below have been imported from:
#    events.py
# md5:ee964ddec320f22b8eeab458a02a6835

events_ACCOUNT_ACTIVATION = "ACCOUNT_ACTIVATION"

# Objects below have been imported from:
#    fetchers.py
# md5:dcba39f23bd6808d7c243d6f0f8ff8d0

fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID = "EFFECTIVE_FETCHER"
fetchers_EFFECTIVE_OBSERVATION_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID, at=DefinedDateTime.EFFECTIVE_DATETIME
)
fetchers_LIVE_BALANCES_BOF_ID = "live_balances_bof"
fetchers_LIVE_BALANCES_BOF = BalancesObservationFetcher(
    fetcher_id=fetchers_LIVE_BALANCES_BOF_ID, at=DefinedDateTime.LIVE
)

# Objects below have been imported from:
#    addresses.py
# md5:860f50af37f2fe98540f540fa6394eb7

addresses_INTERNAL_CONTRA = "INTERNAL_CONTRA"
addresses_PENALTIES = "PENALTIES"

# Objects below have been imported from:
#    supervisor_utils.py
# md5:badd574e398fc715274627e947d1a001


def supervisor_utils_create_aggregate_posting_instructions(
    aggregate_account_id: str,
    posting_instructions_by_supervisee: dict[str, list[CustomInstruction]],
    prefix: str,
    balances: BalanceDefaultDict,
    addresses_to_aggregate: list[str],
    tside: Tside = Tside.ASSET,
    force_override: bool = True,
    rounding_precision: int = 2,
) -> list[CustomInstruction]:
    """
    Used for supervisor contracts to aggregate multiple posting instructions that arise
    from supervisee accounts. This util is helpful when you have a "main" supervisee
    account that is responsible for holding aggregate balances (i.e. an account where
    aggregate postings are made).

    Any postings targeting the same balance address name will be aggregated. e.g. If supervisee 1
    and supervisee 2 both have postings to address PRINCIPAL_DUE, the aggregate value of these will
    be calculated into a new posting instruction of length 1 to a balance address:
    <prefix>_<balance_address> (e.g. TOTAL_PRINCIPAL_DUE).

    :param aggregate_account_id: The account id of the vault object where the aggregate postings
    are made (i.e. the "main" account)
    :param posting_instructions_by_supervisee: A mapping of supervisee account id to posting
    instructions to derive the aggregate posting instructions from
    :param prefix: The prefix of the aggregated balances
    :param balances: The balances of the account where the aggregate postings are made (i.e. the
    "main" account). Typically these are the latest balances for the account, but in theory any
    balances can be passed in.
    :param addresses_to_aggregate: A list of addresses to get aggregate postings for
    :param tside: The Tside of the account
    :param force_override: boolean to pass into instruction details to force override hooks
    :param rounding_precision: The rounding precision to correct for
    :return: The aggregated custom instructions
    """
    aggregate_balances = BalanceDefaultDict()
    for (supervisee_account_id, posting_instructions) in posting_instructions_by_supervisee.items():
        for posting_instruction in posting_instructions:
            aggregate_balances += posting_instruction.balances(
                account_id=supervisee_account_id, tside=tside
            )
    filtered_aggregate_balances = supervisor_utils_filter_aggregate_balances(
        aggregate_balances=aggregate_balances,
        balances=balances,
        addresses_to_aggregate=addresses_to_aggregate,
        rounding_precision=rounding_precision,
    )
    aggregate_postings: list[Posting] = []
    for (balance_coordinate, balance) in filtered_aggregate_balances.items():
        amount: Decimal = balance.net
        prefixed_address = f"{prefix}_{balance_coordinate.account_address}"
        debit_address = (
            prefixed_address
            if tside == Tside.ASSET
            and amount > Decimal("0")
            or (tside == Tside.LIABILITY and amount < Decimal("0"))
            else addresses_INTERNAL_CONTRA
        )
        credit_address = (
            prefixed_address
            if tside == Tside.ASSET
            and amount < Decimal("0")
            or (tside == Tside.LIABILITY and amount > Decimal("0"))
            else addresses_INTERNAL_CONTRA
        )
        aggregate_postings += utils_create_postings(
            amount=abs(amount),
            debit_account=aggregate_account_id,
            credit_account=aggregate_account_id,
            debit_address=debit_address,
            credit_address=credit_address,
            denomination=balance_coordinate.denomination,
            asset=balance_coordinate.asset,
        )
    aggregate_posting_instructions: list[CustomInstruction] = []
    if aggregate_postings:
        aggregate_posting_instructions.append(
            CustomInstruction(
                postings=aggregate_postings,
                instruction_details={"force_override": str(force_override).lower()},
            )
        )
    return aggregate_posting_instructions


def supervisor_utils_filter_aggregate_balances(
    aggregate_balances: BalanceDefaultDict,
    balances: BalanceDefaultDict,
    addresses_to_aggregate: list[str],
    rounding_precision: int = 2,
) -> BalanceDefaultDict:
    """
    Removes aggregate balances that would cause discrepancies between the supervisor
    and the supervisee(s) due to rounding errors.
    Only aggregates given addresses to avoid unnecessary aggregations (e.g. INTERNAL_CONTRA)

    For instance, assume the rounding precision is 2. If account 1 has a balance A with a current
    value of 0.123 and the aggregate amount is 0.001, no aggregate posting needs to be created as
    the rounded absolute amount is unchanged (round(0.123, 2) == round(0.124, 2)). If account 1 has
    a balance A with a current value of 0.123 and there is a posting to increase this by 0.002,
    an aggregate posting is needed as the rounded absolute amount has changed from 0.12 to 0.13.

    Normally this filtering only needs to be applied to the accrued interest balance address,
    but we simply check all addresses being aggregated to guard against this edge case.

    This util is mainly for use in the create_aggregate_posting_instructions util, but in theory
    it could be used independently.

    :param aggregate_balances: The aggregate balances to filter
    :param balances: The balances of the account where the aggregate postings are made (i.e. the
    "main" account). Typically these are the latest balances for the account, but in theory any
    balances can be passed in.
    :param addresses_to_aggregate: A list of addresses to aggregate balances for
    :param rounding_precision: The rounding precision to correct for
    :return: A filtered dict of aggregated balances
    """
    filtered_aggregate_balance_mapping = aggregate_balances.copy()
    new_balance_mapping = aggregate_balances + balances
    for balance_coordinate in aggregate_balances:
        if balance_coordinate.account_address in addresses_to_aggregate:
            current_amount = balances[balance_coordinate].net
            new_amount = new_balance_mapping[balance_coordinate].net
            if utils_round_decimal(
                amount=new_amount, decimal_places=rounding_precision
            ) == utils_round_decimal(amount=current_amount, decimal_places=rounding_precision):
                del filtered_aggregate_balance_mapping[balance_coordinate]
        else:
            del filtered_aggregate_balance_mapping[balance_coordinate]
    return filtered_aggregate_balance_mapping


# Objects below have been imported from:
#    lending_addresses.py
# md5:d546448643732336308da8f52c0901d4

lending_addresses_ACCRUED_INTEREST_RECEIVABLE = "ACCRUED_INTEREST_RECEIVABLE"
lending_addresses_DUE_CALCULATION_EVENT_COUNTER = "DUE_CALCULATION_EVENT_COUNTER"
lending_addresses_EMI = "EMI"
lending_addresses_INTERNAL_CONTRA = addresses_INTERNAL_CONTRA
lending_addresses_INTEREST_DUE = "INTEREST_DUE"
lending_addresses_INTEREST_OVERDUE = "INTEREST_OVERDUE"
lending_addresses_NON_EMI_ACCRUED_INTEREST_RECEIVABLE = "NON_EMI_ACCRUED_INTEREST_RECEIVABLE"
lending_addresses_PENALTIES = addresses_PENALTIES
lending_addresses_PRINCIPAL = "PRINCIPAL"
lending_addresses_PRINCIPAL_DUE = "PRINCIPAL_DUE"
lending_addresses_PRINCIPAL_OVERDUE = "PRINCIPAL_OVERDUE"
lending_addresses_ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION = (
    "ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION"
)
lending_addresses_DUE_ADDRESSES = [lending_addresses_PRINCIPAL_DUE, lending_addresses_INTEREST_DUE]
lending_addresses_OVERDUE_ADDRESSES = [
    lending_addresses_PRINCIPAL_OVERDUE,
    lending_addresses_INTEREST_OVERDUE,
]
lending_addresses_LATE_REPAYMENT_ADDRESSES = lending_addresses_OVERDUE_ADDRESSES + [
    lending_addresses_PENALTIES
]
lending_addresses_REPAYMENT_HIERARCHY = (
    lending_addresses_LATE_REPAYMENT_ADDRESSES + lending_addresses_DUE_ADDRESSES
)
lending_addresses_DEBT_ADDRESSES = lending_addresses_REPAYMENT_HIERARCHY + [
    lending_addresses_PRINCIPAL
]
lending_addresses_ALL_OUTSTANDING = [
    *lending_addresses_DEBT_ADDRESSES,
    lending_addresses_ACCRUED_INTEREST_RECEIVABLE,
    lending_addresses_ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
]
lending_addresses_ALL_OUTSTANDING_SUPERVISOR = lending_addresses_ALL_OUTSTANDING + [
    lending_addresses_NON_EMI_ACCRUED_INTEREST_RECEIVABLE
]

# Objects below have been imported from:
#    lending_interfaces.py
# md5:a0df1ba0adcd14fa7f99308269ad58a7

lending_interfaces_EarlyRepaymentFee = NamedTuple(
    "EarlyRepaymentFee",
    [
        ("get_early_repayment_fee_amount", Callable[..., Decimal]),
        ("charge_early_repayment_fee", Callable[..., list[CustomInstruction]]),
        ("fee_name", str),
    ],
)
lending_interfaces_InterestRate = NamedTuple(
    "InterestRate",
    [
        ("get_daily_interest_rate", Callable[..., Decimal]),
        ("get_monthly_interest_rate", Callable[..., Decimal]),
        ("get_annual_interest_rate", Callable[..., Decimal]),
    ],
)
lending_interfaces_PrincipalAdjustment = NamedTuple(
    "PrincipalAdjustment", [("calculate_principal_adjustment", Callable[..., Decimal])]
)
lending_interfaces_ResidualCleanup = NamedTuple(
    "ResidualCleanup", [("get_residual_cleanup_postings", Callable[..., list[Posting]])]
)
lending_interfaces_Amortisation = NamedTuple(
    "Amortisation",
    [
        ("calculate_emi", Callable[..., Decimal]),
        ("term_details", Callable[..., tuple[int, int]]),
        ("override_final_event", bool),
    ],
)

# Objects below have been imported from:
#    lending_parameters.py
# md5:7faccb9f85f49b8f7dea97327cbece56

lending_parameters_PARAM_TOTAL_REPAYMENT_COUNT = "total_repayment_count"
lending_parameters_total_repayment_count_parameter = Parameter(
    name=lending_parameters_PARAM_TOTAL_REPAYMENT_COUNT,
    shape=NumberShape(min_value=Decimal(1), step=Decimal(1)),
    level=ParameterLevel.INSTANCE,
    description="The total number of repayments to be made, at a monthly frequency unless a repayment_frequency parameter is present.",
    display_name="Total Repayment Count",
    default_value=Decimal(12),
    update_permission=ParameterUpdatePermission.OPS_EDITABLE,
)

# Objects below have been imported from:
#    term_helpers.py
# md5:daf4d2c8e08d1b80a139d4905726ffff


def term_helpers_calculate_elapsed_term(balances: BalanceDefaultDict, denomination: str) -> int:
    return int(
        utils_balance_at_coordinates(
            balances=balances,
            address=lending_addresses_DUE_CALCULATION_EVENT_COUNTER,
            denomination=denomination,
        )
    )


# Objects below have been imported from:
#    declining_principal.py
# md5:9a0b5e3b9bdf8a8ca9b57a0a01a29e54


def declining_principal_term_details(
    vault: Any,
    effective_datetime: datetime,
    use_expected_term: bool = True,
    interest_rate: Optional[lending_interfaces_InterestRate] = None,
    principal_adjustments: Optional[list[lending_interfaces_PrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> tuple[int, int]:
    """Calculate the elapsed and remaining term for a loan

    :param vault: the vault object for the loan account
    :param effective_datetime: datetime as of which the calculations are performed
    :param use_expected_term: if True, the remaining term is purely based on original and
        elapsed term, ignoring any adjustments etc. If false, it is calculated based on
        principal, interest rate and emi
    :param principal_amount: the principal amount used for amortisation
        If no value provided, the principal set on parameter level is used.
    :param interest_rate: interest rate feature, if no value is provided, 0 is used.
    :param principal_adjustments: features used to adjust the principal that is amortised
        If no value provided, no adjustment is made to the principal.
    :param balances: balances to use instead of the effective datetime balances
    :param denomination: denomination to use instead of the effective datetime parameter value
    :return: the elapsed and remaining term
    """
    original_total_term = int(
        utils_get_parameter(vault=vault, name=lending_parameters_PARAM_TOTAL_REPAYMENT_COUNT)
    )
    if effective_datetime == vault.get_account_creation_datetime():
        return (0, original_total_term)
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    if denomination is None:
        denomination = utils_get_parameter(vault=vault, name="denomination")
    principal_balance = utils_balance_at_coordinates(
        balances=balances, address=lending_addresses_PRINCIPAL, denomination=denomination
    )
    elapsed = term_helpers_calculate_elapsed_term(balances=balances, denomination=denomination)
    expected_remaining_term = (
        original_total_term - elapsed if principal_balance > Decimal("0") else 0
    )
    if use_expected_term:
        return (elapsed, expected_remaining_term)
    emi = utils_balance_at_coordinates(
        balances=balances, address=lending_addresses_EMI, denomination=denomination
    )
    if emi == 0:
        return (elapsed, expected_remaining_term)
    monthly_interest_rate = (
        interest_rate.get_monthly_interest_rate(
            vault=vault,
            effective_datetime=effective_datetime,
            balances=balances,
            denomination=denomination,
        )
        if interest_rate is not None
        else Decimal(0)
    )
    adjusted_principal = principal_balance + Decimal(
        sum(
            (
                adjustment.calculate_principal_adjustment(
                    vault=vault, balances=balances, denomination=denomination
                )
                for adjustment in principal_adjustments or []
            )
        )
    )
    remaining = declining_principal_calculate_remaining_term(
        emi=emi, remaining_principal=adjusted_principal, monthly_interest_rate=monthly_interest_rate
    )
    remaining = min(remaining, expected_remaining_term)
    return (elapsed, remaining)


def declining_principal_calculate_remaining_term(
    emi: Decimal,
    remaining_principal: Decimal,
    monthly_interest_rate: Decimal,
    decimal_places: int = 2,
    rounding: str = ROUND_HALF_UP,
) -> int:
    """
    The remaining term calculated using the amortisation formula
    math.log((EMI/(EMI - P*R)), (1+R)), where:

    EMI is the equated monthly instalment
    P is the remaining principal
    R is the monthly interest rate

    Note that, when the monthly interest rate R is 0, the remaining term
    is calculated using P / EMI. When the EMI is 0, this function will
    return 0.

    The term is rounded using specified arguments and then ceil'd to ensure that partial
    terms are treated as a full term (e.g. rounded remaining term as 16.4 results in 17)

    :param emi: The equated monthly instalment
    :param remaining_principal: The remaining principal
    :param monthly_interest_rate: The monthly interest rate
    :param decimal_places: The number of decimal places to round to
    :param rounding: The type of rounding strategy to use
    :return: The remaining term left on the loan
    """
    if emi == Decimal("0"):
        return 0
    remaining_term = (
        Decimal(
            math.log(
                emi / (emi - remaining_principal * monthly_interest_rate), 1 + monthly_interest_rate
            )
        )
        if monthly_interest_rate > Decimal("0")
        else remaining_principal / emi
    )
    return int(
        utils_round_decimal(
            amount=remaining_term, decimal_places=decimal_places, rounding=rounding
        ).to_integral_exact(rounding=ROUND_CEILING)
    )


def declining_principal_calculate_emi(
    vault: Any,
    effective_datetime: datetime,
    use_expected_term: bool = True,
    principal_amount: Optional[Decimal] = None,
    interest_calculation_feature: Optional[lending_interfaces_InterestRate] = None,
    principal_adjustments: Optional[list[lending_interfaces_PrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
) -> Decimal:
    """
    Extracts relevant data required and calculates declining principal EMI.
    :param vault: Vault object
    :param effective_datetime: the datetime as of which the calculation is performed
    :param use_expected_term: if True, the remaining term is purely based on original and
        elapsed term, ignoring any adjustments etc. If false, it is calculated based on
        principal, interest rate and emi
    :param principal_amount: the principal amount used for amortisation
        If no value provided, the principal set on parameter level is used.
    :param interest_calculation_feature: interest calculation feature, if no value is
        provided, 0 is used.
    :param principal_adjustments: features used to adjust the principal that is amortised
        If no value provided, no adjustment is made to the principal.
    :param balances: balances to use instead of the effective datetime balances
    :return: emi amount
    """
    (principal, interest_rate) = declining_principal__get_declining_principal_formula_terms(
        vault=vault,
        effective_datetime=effective_datetime,
        principal_amount=principal_amount,
        interest_calculation_feature=interest_calculation_feature,
    )
    (_, remaining_term) = declining_principal_term_details(
        vault=vault,
        effective_datetime=effective_datetime,
        use_expected_term=use_expected_term,
        interest_rate=interest_calculation_feature,
        principal_adjustments=principal_adjustments,
        balances=balances,
    )
    if principal_adjustments:
        denomination: str = utils_get_parameter(vault=vault, name="denomination")
        principal += Decimal(
            sum(
                (
                    adjustment.calculate_principal_adjustment(
                        vault=vault, balances=balances, denomination=denomination
                    )
                    for adjustment in principal_adjustments
                )
            )
        )
    return declining_principal_apply_declining_principal_formula(
        remaining_principal=principal, interest_rate=interest_rate, remaining_term=remaining_term
    )


def declining_principal_apply_declining_principal_formula(
    remaining_principal: Decimal,
    interest_rate: Decimal,
    remaining_term: int,
    fulfillment_precision: int = 2,
    lump_sum_amount: Optional[Decimal] = None,
) -> Decimal:
    """
    Calculates the EMI according to the following formula:
    EMI = (P-(L/(1+R)^(N)))*R*(((1+R)^N)/((1+R)^N-1))
    P is principal remaining
    R is the interest rate, which should match the term unit (i.e. monthly rate if
    remaining term is also in months)
    N is term remaining
    L is the lump sum
    Formula can be used for a standard declining principal loan or a
    minimum repayment loan which includes a lump_sum_amount to be paid at the
    end of the term that is > 0.
    When the lump sum amount L is 0, the formula is reduced to:
    EMI = [P x R x (1+R)^N]/[(1+R)^N-1]
    :param remaining_principal: principal remaining
    :param interest_rate: interest rate appropriate for the term unit
    :param remaining_term: the number of integer term units remaining
    :param fulfillment_precision: precision needed for interest fulfillment
    :param lump_sum_amount: an optional one-off repayment amount
    :return: emi amount
    """
    lump_sum_amount = lump_sum_amount or Decimal("0")
    if remaining_term <= Decimal("0"):
        return remaining_principal
    elif interest_rate == Decimal("0"):
        return utils_round_decimal(remaining_principal / remaining_term, fulfillment_precision)
    else:
        return utils_round_decimal(
            (remaining_principal - lump_sum_amount / (1 + interest_rate) ** remaining_term)
            * interest_rate
            * (1 + interest_rate) ** remaining_term
            / ((1 + interest_rate) ** remaining_term - 1),
            fulfillment_precision,
        )


def declining_principal__get_declining_principal_formula_terms(
    vault: Union[Any, Any],
    effective_datetime: datetime,
    principal_amount: Optional[Decimal] = None,
    interest_calculation_feature: Optional[lending_interfaces_InterestRate] = None,
) -> tuple[Decimal, Decimal]:
    principal = (
        utils_get_parameter(vault=vault, name="principal")
        if principal_amount is None
        else principal_amount
    )
    interest_rate = (
        Decimal(0)
        if not interest_calculation_feature
        else interest_calculation_feature.get_monthly_interest_rate(
            vault=vault, effective_datetime=effective_datetime
        )
    )
    return (principal, interest_rate)


declining_principal_AmortisationFeature = lending_interfaces_Amortisation(
    calculate_emi=declining_principal_calculate_emi,
    term_details=declining_principal_term_details,
    override_final_event=False,
)

# Objects below have been imported from:
#    close_loan.py
# md5:7b4a8d8a8438235415310d37d216ac7f

close_loan_DUE_ADDRESSES = [lending_addresses_PRINCIPAL_DUE, lending_addresses_INTEREST_DUE]
close_loan_OVERDUE_ADDRESSES = [
    lending_addresses_PRINCIPAL_OVERDUE,
    lending_addresses_INTEREST_OVERDUE,
]
close_loan_PENALTIES_ADDRESSES = [lending_addresses_PENALTIES]
close_loan_PRINCIPAL_ADDRESSES = [lending_addresses_PRINCIPAL]
close_loan_PAYMENT_ADDRESSES = (
    close_loan_OVERDUE_ADDRESSES + close_loan_PENALTIES_ADDRESSES + close_loan_DUE_ADDRESSES
)
close_loan_DEBT_ADDRESSES = close_loan_PAYMENT_ADDRESSES + close_loan_PRINCIPAL_ADDRESSES


def close_loan_net_balances(
    balances: BalanceDefaultDict,
    denomination: str,
    account_id: str,
    residual_cleanup_features: Optional[list[lending_interfaces_ResidualCleanup]] = None,
) -> list[CustomInstruction]:
    """
    Nets off the EMI, and any other accounting addresses from other features, that should be
    cleared before the loan is closed

    :param balances: The current balances for the account
    :param denomination: The denomination of the account
    :param account_id: The id of the account
    :param residual_cleanup_features: list of features to get residual cleanup postings
    :return: A list of custom instructions used to net all remaining balances
    """
    net_postings: list[Posting] = []
    emi_amount = utils_balance_at_coordinates(
        balances=balances, address=lending_addresses_EMI, denomination=denomination
    )
    if emi_amount > Decimal("0"):
        net_postings += utils_create_postings(
            amount=emi_amount,
            debit_account=account_id,
            credit_account=account_id,
            debit_address=lending_addresses_INTERNAL_CONTRA,
            credit_address=lending_addresses_EMI,
            denomination=denomination,
        )
    if residual_cleanup_features is not None:
        for feature in residual_cleanup_features:
            net_postings += feature.get_residual_cleanup_postings(
                balances=balances, account_id=account_id, denomination=denomination
            )
    posting_instructions: list[CustomInstruction] = []
    if net_postings:
        posting_instructions += [
            CustomInstruction(
                postings=net_postings,
                instruction_details={
                    "description": "Clearing all residual balances",
                    "event": "END_OF_LOAN",
                },
            )
        ]
    return posting_instructions


def close_loan_reject_closure_when_outstanding_debt(
    balances: BalanceDefaultDict,
    denomination: str,
    debt_addresses: list[str] = close_loan_DEBT_ADDRESSES,
) -> Optional[Rejection]:
    """
    Returns a rejection if the debt addresses sum to a non-zero amount

    :param balances: The current balances for the loan account
    :param denomination: The denomination of the account
    :param debt_addresses: A list of debt addresses to sum
    :return: A rejection if the debt addresses sum to a non-zero value
    """
    if utils_sum_balances(
        balances=balances, addresses=debt_addresses, denomination=denomination
    ) != Decimal("0"):
        return Rejection(
            message="The loan cannot be closed until all outstanding debt is repaid",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None


# Objects below have been imported from:
#    disbursement.py
# md5:54aa49cf8e9b9c7684c275bf28a818d3

disbursement_DISBURSEMENT_EVENT = "PRINCIPAL_DISBURSEMENT"
disbursement_PARAM_PRINCIPAL = "principal"
disbursement_PARAM_DEPOSIT_ACCOUNT = "deposit_account"
disbursement_parameters = [
    Parameter(
        name=disbursement_PARAM_PRINCIPAL,
        shape=NumberShape(min_value=Decimal("1")),
        level=ParameterLevel.INSTANCE,
        description="The agreed amount the customer will borrow from the bank.",
        display_name="Loan Principal",
        default_value=Decimal("1000"),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name=disbursement_PARAM_DEPOSIT_ACCOUNT,
        shape=AccountIdShape(),
        level=ParameterLevel.INSTANCE,
        description="The account to which the principal borrowed amount will be transferred.",
        display_name="Deposit Account",
        default_value="00000000-0000-0000-0000-000000000000",
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
]


def disbursement_get_disbursement_custom_instruction(
    account_id: str,
    deposit_account_id: str,
    principal: Decimal,
    denomination: str,
    principal_address: str = lending_addresses_PRINCIPAL,
) -> list[CustomInstruction]:
    return [
        CustomInstruction(
            postings=[
                Posting(
                    credit=False,
                    amount=principal,
                    denomination=denomination,
                    account_id=account_id,
                    account_address=principal_address,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    credit=True,
                    amount=principal,
                    denomination=denomination,
                    account_id=deposit_account_id,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ],
            override_all_restrictions=True,
            instruction_details={
                "description": f"Principal disbursement of {principal}",
                "event": disbursement_DISBURSEMENT_EVENT,
            },
        )
    ]


# Objects below have been imported from:
#    emi.py
# md5:6fd652b0be2b953dfaf528e599cb7c8b


def emi_amortise(
    vault: Any,
    effective_datetime: datetime,
    amortisation_feature: lending_interfaces_Amortisation,
    principal_amount: Optional[Decimal] = None,
    interest_calculation_feature: Optional[lending_interfaces_InterestRate] = None,
    principal_adjustments: Optional[list[lending_interfaces_PrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
    event: Optional[str] = events_ACCOUNT_ACTIVATION,
) -> list[CustomInstruction]:
    """
    Amortises a loan by calculating EMI and creating a custom instruction to update the balance
    value at the EMI address. Suitable for initial amortisation, and reamortisation if the
    `balances` argument is populated.

    :param vault: Vault object
    :param effective_datetime: effective dt for calculating the emi
    :param amortisation_feature: contains the emi calculation method for the desired amortisation
    :param principal_amount: the principal amount used for amortisation
        If no value provided, the amortisation feature calculate_emi method is expected to set
        principal amount to the value set on parameter level.
    :param interest_calculation_feature: an interest calculation feature
    :param principal_adjustments: features used to adjust the principal that is amortised
        If no value provided, no adjustment is made to the principal.
    :param event: event string to be included in the CustomInstruction instruction_details.
        If not provided, value defaults to ACCOUNT_ACTIVATION.
    :param balances: balances used to calculate emi and determine whether postings are required to
    update it. If balances are None, emi and elapsed term both assumed to be 0. This
    is suitable for scenarios such as initial amortisation on account activation
    :return: list of custom instructions, empty if no changes to the EMI
    """
    updated_emi = amortisation_feature.calculate_emi(
        vault=vault,
        effective_datetime=effective_datetime,
        principal_amount=principal_amount,
        interest_calculation_feature=interest_calculation_feature,
        principal_adjustments=principal_adjustments,
        balances=balances,
    )
    denomination: str = utils_get_parameter(
        vault, name="denomination", at_datetime=effective_datetime
    )
    if balances is None:
        current_emi = Decimal("0")
    else:
        current_emi = utils_balance_at_coordinates(
            balances=balances, address=lending_addresses_EMI, denomination=denomination
        )
    update_emi_postings = emi_update_emi(
        account_id=vault.account_id,
        denomination=denomination,
        current_emi=current_emi,
        updated_emi=updated_emi,
    )
    if not update_emi_postings:
        return []
    return [
        CustomInstruction(
            postings=update_emi_postings,
            instruction_details={
                "description": f"Updating EMI to {updated_emi}",
                "event": f"{event}",
            },
        )
    ]


def emi_update_emi(
    account_id: str, denomination: str, current_emi: Decimal, updated_emi: Decimal
) -> list[Posting]:
    emi_delta = current_emi - updated_emi
    if emi_delta == Decimal("0"):
        return []
    if emi_delta < Decimal("0"):
        credit_address = lending_addresses_INTERNAL_CONTRA
        debit_address = lending_addresses_EMI
        emi_delta = abs(emi_delta)
    else:
        credit_address = lending_addresses_EMI
        debit_address = lending_addresses_INTERNAL_CONTRA
    return utils_create_postings(
        amount=emi_delta,
        debit_account=account_id,
        debit_address=debit_address,
        credit_account=account_id,
        credit_address=credit_address,
        denomination=denomination,
    )


# Objects below have been imported from:
#    due_amount_calculation.py
# md5:764e3e5a69ae8c7f97be1c0a65a16ddf


def due_amount_calculation_get_residual_cleanup_postings(
    balances: BalanceDefaultDict, account_id: str, denomination: str
) -> list[Posting]:
    return utils_reset_tracker_balances(
        balances=balances,
        account_id=account_id,
        tracker_addresses=[lending_addresses_DUE_CALCULATION_EVENT_COUNTER],
        contra_address=lending_addresses_INTERNAL_CONTRA,
        denomination=denomination,
        tside=Tside.ASSET,
    )


due_amount_calculation_DueAmountCalculationResidualCleanupFeature = (
    lending_interfaces_ResidualCleanup(
        get_residual_cleanup_postings=due_amount_calculation_get_residual_cleanup_postings
    )
)

# Objects below have been imported from:
#    derived_params.py
# md5:e5e42c2b86af0ad211853bcc16ea1854


def derived_params_get_total_outstanding_debt(
    balances: BalanceDefaultDict,
    denomination: str,
    precision: int = 2,
    debt_addresses: list[str] = lending_addresses_ALL_OUTSTANDING,
) -> Decimal:
    """
    Sums the balances across all outstanding debt addresses
    :param balances: a dictionary of balances in the account
    :param denomination: the denomination of the balances to be summed
    :param precision: the number of decimal places to round to
    :param debt_addresses: outstanding debt addresses
    :return: outstanding debt balance in Decimal
    """
    return utils_sum_balances(
        balances=balances,
        addresses=debt_addresses,
        denomination=denomination,
        decimal_places=precision,
    )


# Objects below have been imported from:
#    early_repayment.py
# md5:f999fa0e14d31eabc867091bfbd3904d


def early_repayment_get_total_early_repayment_amount(
    vault: Any,
    early_repayment_fees: Optional[list[lending_interfaces_EarlyRepaymentFee]],
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    precision: int = 2,
    debt_addresses: list[str] = lending_addresses_ALL_OUTSTANDING,
    check_for_outstanding_accrued_interest_on_zero_principal: bool = False,
) -> Decimal:
    """
    Get the exact repayment amount required for a full early repayment.

    :param vault: vault object for the relevant account
    :param early_repayment_fees: early repayment fee features
    :param balances: balances to base calculations on
    :param denomination: denomination of the relevant loan
    :param precision: the number of decimal places to round to
    :param debt_addresses: outstanding debt addresses
    :param check_for_outstanding_accrued_interest_on_zero_principal: if outstanding balances on
    loans that have zero principal should count as early repayment
    :return: the exact repayment amount required for a full early repayment
    """
    balances = early_repayment__get_balances(vault=vault, balances=balances)
    denomination = early_repayment__get_denomination(vault=vault, denomination=denomination)
    if (
        not check_for_outstanding_accrued_interest_on_zero_principal
        and early_repayment__is_zero_principal(balances=balances, denomination=denomination)
    ):
        return utils_round_decimal(Decimal("0"), precision)
    return early_repayment__get_sum_of_early_repayment_fees_and_outstanding_debt(
        vault=vault,
        early_repayment_fees=early_repayment_fees or [],
        balances=balances,
        denomination=denomination,
        precision=precision,
        debt_addresses=debt_addresses,
    )


def early_repayment__is_zero_principal(denomination: str, balances: BalanceDefaultDict) -> bool:
    """
    Return true if there is a zero principal balance.

    :param denomination: denomination of the relevant loan
    :param balances: balances to base calculations on
    :return: true if there is a zero principal balance
    """
    return utils_sum_balances(
        balances=balances, addresses=[lending_addresses_PRINCIPAL], denomination=denomination
    ) <= Decimal("0")


def early_repayment__get_denomination(vault: Any, denomination: Optional[str] = None) -> str:
    """
    Get the denomination of the account, allowing for a None to be passed in.

    :param vault: vault object for the relevant account
    :param denomination: denomination of the relevant loan
    :return: the denomination
    """
    return (
        utils_get_parameter(vault=vault, name="denomination")
        if denomination is None
        else denomination
    )


def early_repayment__get_balances(
    vault: Any, balances: Optional[BalanceDefaultDict] = None
) -> BalanceDefaultDict:
    """
    Return the balances that are passed in or get the live balances of the account.

    :param vault: vault object for the relevant account
    :param balances: balances to base calculations on
    :return: the balances
    """
    return (
        vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
        if balances is None
        else balances
    )


def early_repayment__get_sum_of_early_repayment_fees_and_outstanding_debt(
    vault: Any,
    early_repayment_fees: list[lending_interfaces_EarlyRepaymentFee],
    balances: BalanceDefaultDict,
    denomination: str,
    precision: int,
    debt_addresses: list[str],
) -> Decimal:
    """
    Get the exact repayment amount required for a full early repayment.

    :param vault: vault object for the relevant account
    :param early_repayment_fees: early repayment fee features
    :param balances: balances to base calculations on
    :param denomination: denomination of the relevant loan
    :param precision: the number of decimal places to round to
    :param debt_addresses: outstanding debt addresses
    :return: the exact repayment amount required for a full early repayment
    """
    early_repayment_fees_sum = Decimal("0")
    for early_repayment_fee in early_repayment_fees:
        early_repayment_fees_sum += early_repayment_fee.get_early_repayment_fee_amount(
            vault=vault, balances=balances, denomination=denomination, precision=precision
        )
    total_outstanding_debt = derived_params_get_total_outstanding_debt(
        balances=balances, denomination=denomination, debt_addresses=debt_addresses
    )
    return total_outstanding_debt + early_repayment_fees_sum


# Objects below have been imported from:
#    interest_accrual_common.py
# md5:162f41e06e859ca63b416be0f14ea285

interest_accrual_common_PARAM_DAYS_IN_YEAR = "days_in_year"
interest_accrual_common_PARAM_ACCRUAL_PRECISION = "accrual_precision"
interest_accrual_common_days_in_year_param = Parameter(
    name=interest_accrual_common_PARAM_DAYS_IN_YEAR,
    shape=UnionShape(
        items=[
            UnionItem(key="actual", display_name="Actual"),
            UnionItem(key="366", display_name="366"),
            UnionItem(key="365", display_name="365"),
            UnionItem(key="360", display_name="360"),
        ]
    ),
    level=ParameterLevel.TEMPLATE,
    description='The days in the year for interest accrual calculation. Valid values are "actual", "366", "365", "360"',
    display_name="Interest Accrual Days In Year",
    default_value=UnionItemValue(key="365"),
)
interest_accrual_common_accrual_precision_param = Parameter(
    name=interest_accrual_common_PARAM_ACCRUAL_PRECISION,
    level=ParameterLevel.TEMPLATE,
    description="Precision needed for interest accruals.",
    display_name="Interest Accrual Precision",
    shape=NumberShape(min_value=0, max_value=15, step=1),
    default_value=Decimal(5),
)
interest_accrual_common_accrual_parameters = [
    interest_accrual_common_days_in_year_param,
    interest_accrual_common_accrual_precision_param,
]

# Objects below have been imported from:
#    interest_accrual.py
# md5:07236706e076b2c0568b51146520a313

interest_accrual_PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "accrued_interest_receivable_account"
interest_accrual_accrued_interest_receivable_account_param = Parameter(
    name=interest_accrual_PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    level=ParameterLevel.TEMPLATE,
    description="Internal account for accrued interest receivable balance.",
    display_name="Accrued Interest Receivable Account",
    shape=AccountIdShape(),
    default_value="ACCRUED_INTEREST_RECEIVABLE",
)
interest_accrual_accrual_parameters = interest_accrual_common_accrual_parameters
interest_accrual_account_parameters = [interest_accrual_accrued_interest_receivable_account_param]

# Objects below have been imported from:
#    interest_application.py
# md5:b206c2a889540dba58282c6ec772665e

interest_application_PARAM_INTEREST_RECEIVED_ACCOUNT = "interest_received_account"
interest_application_PARAM_APPLICATION_PRECISION = "application_precision"
interest_application_application_precision_param = Parameter(
    name=interest_application_PARAM_APPLICATION_PRECISION,
    level=ParameterLevel.TEMPLATE,
    description="Number of decimal places accrued interest is rounded to when applying interest.",
    display_name="Interest Application Precision",
    shape=NumberShape(max_value=15, step=1),
    default_value=Decimal(2),
)
interest_application_interest_received_account_param = Parameter(
    name=interest_application_PARAM_INTEREST_RECEIVED_ACCOUNT,
    level=ParameterLevel.TEMPLATE,
    description="Internal account for interest received balance.",
    display_name="Interest Received Account",
    shape=AccountIdShape(),
    default_value="INTEREST_RECEIVED",
)
interest_application_account_parameters = [interest_application_interest_received_account_param]

# Objects below have been imported from:
#    fixed.py
# md5:f2f9eef46e1a533911ac0476c6df2d10

fixed_PARAM_FIXED_INTEREST_RATE = "fixed_interest_rate"
fixed_parameters = [
    Parameter(
        name=fixed_PARAM_FIXED_INTEREST_RATE,
        level=ParameterLevel.INSTANCE,
        description="The fixed annual rate of the loan (p.a).",
        display_name="Fixed Interest Rate",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        default_value=Decimal("0.00"),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    )
]


def fixed_get_annual_interest_rate(
    vault: Any,
    effective_datetime: Optional[datetime] = None,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    return Decimal(
        utils_get_parameter(vault, "fixed_interest_rate", at_datetime=effective_datetime)
    )


def fixed_get_daily_interest_rate(
    vault: Any,
    effective_datetime: datetime,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    annual_rate = fixed_get_annual_interest_rate(vault=vault)
    days_in_year = utils_get_parameter(vault, "days_in_year", is_union=True)
    return utils_yearly_to_daily_rate(effective_datetime, annual_rate, days_in_year)


def fixed_get_monthly_interest_rate(
    vault: Any,
    effective_datetime: Optional[datetime] = None,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    annual_rate = fixed_get_annual_interest_rate(vault=vault, effective_datetime=effective_datetime)
    return utils_yearly_to_monthly_rate(annual_rate)


fixed_interest_rate_interface = lending_interfaces_InterestRate(
    get_daily_interest_rate=fixed_get_daily_interest_rate,
    get_monthly_interest_rate=fixed_get_monthly_interest_rate,
    get_annual_interest_rate=fixed_get_annual_interest_rate,
)

# Objects below have been imported from:
#    overpayment.py
# md5:a8cb4d2f6f955706d1b72f5c93822334

overpayment_ACCRUED_EXPECTED_INTEREST = "ACCRUED_EXPECTED_INTEREST"
overpayment_EMI_PRINCIPAL_EXCESS = "EMI_PRINCIPAL_EXCESS"
overpayment_OVERPAYMENT = "OVERPAYMENT"
overpayment_OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER = (
    "OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER"
)
overpayment_PARAM_OVERPAYMENT_FEE_RATE = "overpayment_fee_rate"
overpayment_overpayment_fee_rate_param = Parameter(
    name=overpayment_PARAM_OVERPAYMENT_FEE_RATE,
    shape=NumberShape(min_value=Decimal("0"), max_value=Decimal("1"), step=Decimal("0.0001")),
    level=ParameterLevel.TEMPLATE,
    description="Percentage fee charged on the overpayment amount.",
    display_name="Overpayment Fee Rate",
    default_value=Decimal("0.05"),
)


def overpayment_get_max_overpayment_fee(
    fee_rate: Decimal,
    balances: BalanceDefaultDict,
    denomination: str,
    precision: int = 2,
    principal_address: str = lending_addresses_PRINCIPAL,
) -> Decimal:
    """
    The maximum overpayment fee is equal to the maximum_overpayment_amount * overpayment_fee_rate,

    Maximum Overpayment Amount Proof:
        X = maximum_overpayment_amount
        R = overpayment_fee_rate
        P = remaining_principal
        F = overpayment_fee

        overpayment_fee = overpayment_amount * overpayment_fee_rate
        principal_repaid = overpayment_amount - overpayment_fee
        maximum_overpayment_amount is when principal_repaid == remaining_principal, therefore

        P = X - F
        but F = X*R
        => P = X - XR => X(1-R)
        and so:
        X = P / (1-R)
        and so F_max = PR / (1-R)
    """
    if fee_rate >= 1:
        return Decimal("0")
    principal = utils_balance_at_coordinates(
        balances=balances, address=principal_address, denomination=denomination
    )
    maximum_overpayment = utils_round_decimal(
        amount=principal / (1 - fee_rate), decimal_places=precision
    )
    overpayment_fee = overpayment_get_overpayment_fee(
        principal_repaid=maximum_overpayment, overpayment_fee_rate=fee_rate, precision=precision
    )
    return overpayment_fee


def overpayment_get_overpayment_fee(
    principal_repaid: Decimal, overpayment_fee_rate: Decimal, precision: int
) -> Decimal:
    """Determines the overpayment fee for a given amount of principal being repaid

    :param principal_repaid: the amount of principal repaid by the repayment
    :param overpayment_fee_rate: the percentage of principal to include in the fee. Must be
    < 1, or 0 is returned
    :param precision: decimal places to round the fee to
    :return: the overpayment fee
    """
    if overpayment_fee_rate >= 1:
        return Decimal("0")
    return utils_round_decimal(
        amount=principal_repaid * overpayment_fee_rate, decimal_places=precision
    )


def overpayment_get_residual_cleanup_postings(
    balances: BalanceDefaultDict, account_id: str, denomination: str
) -> list[Posting]:
    return utils_reset_tracker_balances(
        balances=balances,
        account_id=account_id,
        tracker_addresses=[
            overpayment_ACCRUED_EXPECTED_INTEREST,
            overpayment_EMI_PRINCIPAL_EXCESS,
            overpayment_OVERPAYMENT,
            overpayment_OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
        ],
        contra_address=lending_addresses_INTERNAL_CONTRA,
        denomination=denomination,
        tside=Tside.ASSET,
    )


def overpayment_get_overpayment_fee_rate_parameter(vault: Any) -> Decimal:
    overpayment_fee_rate: Decimal = utils_get_parameter(
        vault=vault, name=overpayment_PARAM_OVERPAYMENT_FEE_RATE
    )
    return overpayment_fee_rate


overpayment_OverpaymentResidualCleanupFeature = lending_interfaces_ResidualCleanup(
    get_residual_cleanup_postings=overpayment_get_residual_cleanup_postings
)


def overpayment_get_early_repayment_overpayment_fee(
    vault: Any,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    precision: int = 2,
) -> Decimal:
    """
    Get the early repayment overpayment fee amount. This is always the maximum overpayment fee.
    To be used as a get_early_repayment_fee_amount callable for an EarlyRepaymentFee interface.

    :param vault: vault object for the relevant account
    :param balances: balances to base calculations on
    :param denomination: denomination of the relevant loan
    :param precision: the number of decimal places to round to
    :return: the flat fee amount
    """
    balances = (
        vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
        if balances is None
        else balances
    )
    denomination = (
        utils_get_parameter(vault=vault, name="denomination")
        if denomination is None
        else denomination
    )
    overpayment_fee_rate = overpayment_get_overpayment_fee_rate_parameter(vault=vault)
    max_overpayment_fee = overpayment_get_max_overpayment_fee(
        fee_rate=overpayment_fee_rate,
        balances=balances,
        denomination=denomination,
        precision=precision,
    )
    return max_overpayment_fee


def overpayment_skip_charge_early_repayment_fee_for_overpayment(
    vault: Any,
    account_id: str,
    amount_to_charge: Decimal,
    fee_name: str,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Skip the charge for the overpayment fee within an early repayment since this fee posting is
    already handled by the overpayment logic within post posting.  To be used as a
    charge_early_repayment_fee callable for an EarlyRepaymentFee interface.

    :param vault: only needed to satisfy the interface signature
    :param account_id: only needed to satisfy the interface signature
    :param amount_to_charge: only needed to satisfy the interface signature
    :param fee_name: only needed to satisfy the interface signature
    :param denomination: only needed to satisfy the interface signature
    :return: an empty list
    """
    return []


overpayment_EarlyRepaymentOverpaymentFee = lending_interfaces_EarlyRepaymentFee(
    get_early_repayment_fee_amount=overpayment_get_early_repayment_overpayment_fee,
    charge_early_repayment_fee=overpayment_skip_charge_early_repayment_fee_for_overpayment,
    fee_name="Overpayment Fee",
)

# Objects below have been imported from:
#    addresses.py
# md5:dd8f6d82cd93140051659a35e4e1246c

addresses_TOTAL = "TOTAL"
addresses_TOTAL_ORIGINAL_PRINCIPAL = f"{addresses_TOTAL}_ORIGINAL_{lending_addresses_PRINCIPAL}"

# Objects below have been imported from:
#    drawdown_loan.py
# md5:99ca9e037d17294ee87de4e62ea71bb2

data_fetchers = [fetchers_EFFECTIVE_OBSERVATION_FETCHER, fetchers_LIVE_BALANCES_BOF]
PARAM_LOC_ACCOUNT_ID = "line_of_credit_account_id"
PARAM_PENALTY_INTEREST_RATE = "penalty_interest_rate"
PARAM_INCLUDE_BASE_RATE_IN_PENALTY_RATE = "include_base_rate_in_penalty_rate"
PARAM_PENALTY_INTEREST_INCOME_ACCOUNT = "penalty_interest_income_account"
PARAM_PER_LOAN_EARLY_REPAYMENT_AMOUNT = "per_loan_early_repayment_amount"
ACCOUNT_TYPE = "DRAWDOWN_LOAN"
parameters = [
    Parameter(
        name=PARAM_LOC_ACCOUNT_ID,
        shape=AccountIdShape(),
        level=ParameterLevel.INSTANCE,
        description="Linked line of credit account id",
        display_name="Line Of Credit Account Id",
        default_value="00000000-0000-0000-0000-000000000000",
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name=PARAM_PENALTY_INTEREST_RATE,
        shape=NumberShape(min_value=Decimal("0"), max_value=Decimal("1"), step=Decimal("0.0001")),
        level=ParameterLevel.TEMPLATE,
        description="The annual penalty interest rate to be applied to overdue amounts.",
        display_name="Penalty Interest Rate",
        default_value=Decimal("0"),
    ),
    Parameter(
        name=PARAM_INCLUDE_BASE_RATE_IN_PENALTY_RATE,
        shape=common_parameters_BooleanShape,
        level=ParameterLevel.TEMPLATE,
        description="If true the penalty interest rate is added to the base interest rate.",
        display_name="Penalty Includes Base Rate",
        default_value=common_parameters_BooleanValueTrue,
    ),
    Parameter(
        name=PARAM_PENALTY_INTEREST_INCOME_ACCOUNT,
        shape=AccountIdShape(),
        level=ParameterLevel.TEMPLATE,
        description="Internal account for penalty interest income.",
        display_name="Penalty Interest Income Account",
        default_value="PENALTY_INTEREST_INCOME",
    ),
    Parameter(
        name=PARAM_PER_LOAN_EARLY_REPAYMENT_AMOUNT,
        shape=NumberShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="Total early repayment amount required to fully repay and close the account",
        display_name="Total Early Repayment Amount",
    ),
    *disbursement_parameters,
    *fixed_parameters,
    *interest_accrual_account_parameters,
    *interest_accrual_accrual_parameters,
    interest_application_application_precision_param,
    *interest_application_account_parameters,
    lending_parameters_total_repayment_count_parameter,
    overpayment_overpayment_fee_rate_param,
    common_parameters_denomination_parameter,
]


def _net_aggregate_emi(
    balances: BalanceDefaultDict, loc_account_id: str, denomination: str
) -> list[Posting]:
    net_aggregate_emi_postings: list[Posting] = []
    if emi_amount := utils_balance_at_coordinates(
        balances=balances, address=lending_addresses_EMI, denomination=denomination
    ):
        net_aggregate_emi_postings += utils_create_postings(
            amount=emi_amount,
            debit_account=loc_account_id,
            credit_account=loc_account_id,
            debit_address=lending_addresses_INTERNAL_CONTRA,
            credit_address=f"TOTAL_{lending_addresses_EMI}",
            denomination=denomination,
        )
    return net_aggregate_emi_postings


def _get_deposit_account_parameter(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> str:
    return utils_get_parameter(
        vault=vault, name=disbursement_PARAM_DEPOSIT_ACCOUNT, at_datetime=effective_datetime
    )


def _get_loc_account_id_parameter(vault: Any) -> str:
    loc_account_id: str = utils_get_parameter(vault=vault, name=PARAM_LOC_ACCOUNT_ID)
    return loc_account_id


def _get_principal_parameter(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> Decimal:
    return utils_get_parameter(
        vault=vault, name=disbursement_PARAM_PRINCIPAL, at_datetime=effective_datetime
    )


def _get_original_principal_custom_instructions(
    principal: Decimal, loc_account_id: str, denomination: str, is_closing_loan: bool = False
) -> list[CustomInstruction]:
    """
    Creates custom instructions for aggregating the original principal for each drawdown
    loan.

    :param principal: the principal for this loan
    :param loc_account_id: the line of credit account that holds the aggregate balance
    :param denomination: the principal denomination
    :param is_closing_loan: when set to True generated instructions will subtract the principal
    from the TOTAL_ORIGINAL_PRINCIPAL address; otherwise, the generated instructions will add the
    principal to the TOTAL_ORIGINAL_PRINCIPAL. Defaults to False
    :return: aggregate original principal instructions
    """
    if is_closing_loan:
        debit_address = lending_addresses_INTERNAL_CONTRA
        credit_address = addresses_TOTAL_ORIGINAL_PRINCIPAL
    else:
        debit_address = addresses_TOTAL_ORIGINAL_PRINCIPAL
        credit_address = lending_addresses_INTERNAL_CONTRA
    if postings := utils_create_postings(
        amount=principal,
        debit_account=loc_account_id,
        credit_account=loc_account_id,
        debit_address=debit_address,
        credit_address=credit_address,
        denomination=denomination,
    ):
        return [
            CustomInstruction(postings=postings, instruction_details={"force_override": "True"})
        ]
    return []
