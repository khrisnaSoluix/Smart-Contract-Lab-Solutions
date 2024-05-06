# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.

# standard libs
from decimal import Decimal
from typing import Optional

# library
import library.line_of_credit.constants.addresses as line_of_credit_addresses

# features
import library.features.common.common_parameters as common_parameters
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.lending.credit_limit as credit_limit
import library.features.v4.lending.delinquency as delinquency
import library.features.v4.lending.due_amount_calculation as due_amount_calculation
import library.features.v4.lending.early_repayment as early_repayment
import library.features.v4.lending.interest_accrual as interest_accrual
import library.features.v4.lending.late_repayment as late_repayment
import library.features.v4.lending.lending_addresses as addresses
import library.features.v4.lending.maximum_loan_principal as maximum_loan_principal
import library.features.v4.lending.maximum_outstanding_loans as maximum_outstanding_loans
import library.features.v4.lending.minimum_loan_principal as minimum_loan_principal
import library.features.v4.lending.overdue as overdue
import library.features.v4.lending.overpayment as overpayment
import library.features.v4.lending.repayment_holiday as repayment_holiday

# contracts api
from contracts_api import (
    ActivationHookArguments,
    ActivationHookResult,
    BalanceDefaultDict,
    DerivedParameterHookArguments,
    DerivedParameterHookResult,
    NumberShape,
    Parameter,
    ParameterLevel,
    PreParameterChangeHookArguments,
    PreParameterChangeHookResult,
    PrePostingHookArguments,
    PrePostingHookResult,
    Rejection,
    RejectionReason,
    ScheduledEventHookArguments,
    ScheduledEventHookResult,
    Tside,
    fetch_account_data,
    requires,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

api = "4.0.0"
version = "2.0.1"
display_name = "Line of Credit"
tside = Tside.ASSET

# this can be amended to whichever other currencies as needed
supported_denominations = ["GBP"]

data_fetchers = [fetchers.EFFECTIVE_OBSERVATION_FETCHER, fetchers.LIVE_BALANCES_BOF]

LOC_ACCOUNT_TYPE = "LOC"

REPAYMENT_DUE_NOTIFICATION = "LOC_REPAYMENT_DUE"
OVERDUE_REPAYMENT_NOTIFICATION = "LOC_OVERDUE_REPAYMENT"
DELINQUENT_NOTIFICATION = "LOC_DELINQUENT"
LOANS_PAID_OFF_NOTIFICATION = "LOC_LOANS_PAID_OFF"

notification_types = [
    REPAYMENT_DUE_NOTIFICATION,
    OVERDUE_REPAYMENT_NOTIFICATION,
    DELINQUENT_NOTIFICATION,
    LOANS_PAID_OFF_NOTIFICATION,
]

# We run a dummy due amount calculation event that is synchronised with the corresponding
# supervisor event to enable the last execution datetime to be used by the supervisor.
event_types = [
    *due_amount_calculation.event_types(product_name=LOC_ACCOUNT_TYPE),
]

# Derived Parameters
PARAM_TOTAL_ARREARS_AMOUNT = "total_arrears"
PARAM_TOTAL_MONTHLY_REPAYMENT_AMOUNT = "total_monthly_repayment"
PARAM_TOTAL_ORIGINAL_PRINCIPAL = "total_original_principal"
PARAM_TOTAL_OUTSTANDING_DUE_AMOUNT = "total_outstanding_due"
PARAM_TOTAL_OUTSTANDING_PRINCIPAL = "total_outstanding_principal"
PARAM_TOTAL_AVAILABLE_CREDIT = "total_available_credit"

parameters = [
    # Feature Parameters
    *late_repayment.fee_parameters,
    *maximum_loan_principal.parameters,
    *minimum_loan_principal.parameters,
    *interest_accrual.schedule_parameters,
    *due_amount_calculation.schedule_parameters,
    due_amount_calculation.next_repayment_date_parameter,
    *credit_limit.parameters,
    *overdue.schedule_parameters,
    *delinquency.schedule_parameters,
    *maximum_outstanding_loans.parameters,
    *repayment_holiday.all_parameters_excluding_preference,
    common_parameters.denomination_parameter,
    overpayment.overpayment_fee_income_account_param,
    overpayment.overpayment_fee_rate_param,
    overpayment.overpayment_impact_preference_param,
    early_repayment.total_early_repayment_amount_parameter,
    # Derived Parameters
    Parameter(
        name=PARAM_TOTAL_ARREARS_AMOUNT,
        shape=NumberShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="The amount in arrears.",
        display_name="Arrears Amount",
    ),
    Parameter(
        name=PARAM_TOTAL_MONTHLY_REPAYMENT_AMOUNT,
        shape=NumberShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="The monthly repayment amount across all open loans.",
        display_name="Monthly Repayment Amount",
    ),
    Parameter(
        name=PARAM_TOTAL_ORIGINAL_PRINCIPAL,
        shape=NumberShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="The total original principal taken out across all open loans.",
        display_name="Original Principal",
    ),
    Parameter(
        name=PARAM_TOTAL_OUTSTANDING_DUE_AMOUNT,
        shape=NumberShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="The outstanding amount due to be paid.",
        display_name="Outstanding Due Amount",
    ),
    Parameter(
        name=PARAM_TOTAL_OUTSTANDING_PRINCIPAL,
        shape=NumberShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="The outstanding principal not yet repaid.",
        display_name="Outstanding Principal Remaining",
    ),
    Parameter(
        name=PARAM_TOTAL_AVAILABLE_CREDIT,
        shape=NumberShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="The credit available to be taken as loans.",
        display_name="Available Credit",
    ),
]


@requires(parameters=True)
def activation_hook(
    vault: SmartContractVault, hook_arguments: ActivationHookArguments
) -> Optional[ActivationHookResult]:
    return ActivationHookResult(
        scheduled_events_return_value=due_amount_calculation.scheduled_events(
            vault=vault, account_opening_datetime=hook_arguments.effective_datetime
        ),
    )


@fetch_account_data(balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID])
@requires(
    last_execution_datetime=[
        due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
    ],
    parameters=True,
)
def derived_parameter_hook(
    vault: SmartContractVault, hook_arguments: DerivedParameterHookArguments
) -> DerivedParameterHookResult:
    denomination = common_parameters.get_denomination_parameter(vault=vault)
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    last_execution_datetime = vault.get_last_execution_datetime(
        event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT
    )
    next_due_calc_datetime = due_amount_calculation.get_actual_next_repayment_date(
        vault=vault,
        effective_datetime=hook_arguments.effective_datetime,
        # Hardcode elapsed_term to 1 if the event has run previously, and remaining_term to 1,
        # since both are only checked for non zero. There is no concept of remaining_term here.
        elapsed_term=1 if last_execution_datetime else 0,
        remaining_term=1,
    )
    total_outstanding_principal = _get_total_outstanding_principal(
        denomination=denomination, balances=balances
    )
    derived_parameters: dict[str, utils.ParameterValueTypeAlias] = {
        PARAM_TOTAL_ARREARS_AMOUNT: _get_total_arrears_amount(
            denomination=denomination, balances=balances
        ),
        early_repayment.PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT: _get_total_early_repayment_amount(
            vault=vault, denomination=denomination, balances=balances
        ),
        PARAM_TOTAL_MONTHLY_REPAYMENT_AMOUNT: _get_total_monthly_repayment_amount(
            denomination=denomination, balances=balances
        ),
        PARAM_TOTAL_ORIGINAL_PRINCIPAL: _get_total_original_principal(
            denomination=denomination, balances=balances
        ),
        PARAM_TOTAL_OUTSTANDING_DUE_AMOUNT: _get_total_outstanding_due_amount(
            denomination=denomination, balances=balances
        ),
        PARAM_TOTAL_OUTSTANDING_PRINCIPAL: total_outstanding_principal,
        PARAM_TOTAL_AVAILABLE_CREDIT: _get_total_available_credit(
            vault=vault, total_outstanding_principal=total_outstanding_principal
        ),
        due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE: next_due_calc_datetime,
    }
    return DerivedParameterHookResult(parameters_return_value=derived_parameters)


def scheduled_event_hook(
    vault: SmartContractVault, hook_arguments: ScheduledEventHookArguments
) -> Optional[ScheduledEventHookResult]:
    return None


@requires(parameters=True, flags=True)
def pre_posting_hook(
    vault: SmartContractVault, hook_arguments: PrePostingHookArguments
) -> Optional[PrePostingHookResult]:
    posting_instructions = hook_arguments.posting_instructions
    if utils.is_force_override(posting_instructions=posting_instructions):
        return None

    if posting_rejection := utils.validate_single_hard_settlement_or_transfer(
        posting_instructions=posting_instructions
    ):
        return PrePostingHookResult(rejection=posting_rejection)
    posting_instruction = posting_instructions[0]

    denomination = common_parameters.get_denomination_parameter(vault=vault)
    if denomination_rejection := utils.validate_denomination(
        posting_instructions=posting_instructions, accepted_denominations=[denomination]
    ):
        return PrePostingHookResult(rejection=denomination_rejection)

    posting_amount = utils.get_available_balance(
        balances=posting_instruction.balances(), denomination=denomination
    )
    if posting_rejection := utils.validate_amount_precision(amount=posting_amount):
        return PrePostingHookResult(rejection=posting_rejection)

    if posting_amount <= 0:
        if repayment_holiday.is_repayment_blocked(
            vault=vault, effective_datetime=hook_arguments.effective_datetime
        ):
            return PrePostingHookResult(
                rejection=Rejection(
                    message="Repayments blocked for this account",
                    reason_code=RejectionReason.AGAINST_TNC,
                )
            )
    else:
        if rejection := minimum_loan_principal.validate(
            vault=vault, posting_instruction=posting_instruction
        ):
            return PrePostingHookResult(rejection=rejection)
        if rejection := maximum_loan_principal.validate(
            vault=vault, posting_instruction=posting_instruction
        ):
            return PrePostingHookResult(rejection=rejection)
        pass
    return None


@fetch_account_data(
    balances=[fetchers.LIVE_BALANCES_BOF_ID],
)
@requires(
    flags=True,
    last_execution_datetime=[due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT],
    parameters=True,
)
def pre_parameter_change_hook(
    vault: SmartContractVault, hook_arguments: PreParameterChangeHookArguments
) -> Optional[PreParameterChangeHookResult]:
    updated_parameter_values: dict[
        str, utils.ParameterValueTypeAlias
    ] = hook_arguments.updated_parameter_values

    if credit_limit.PARAM_CREDIT_LIMIT in updated_parameter_values:
        if rejection := credit_limit.validate_credit_limit_parameter_change(
            vault=vault,
            proposed_credit_limit=updated_parameter_values[  # type: ignore
                credit_limit.PARAM_CREDIT_LIMIT
            ],
            principal_addresses=[f"TOTAL_{address}" for address in addresses.ALL_PRINCIPAL],
        ):
            return PreParameterChangeHookResult(rejection=rejection)

    if due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY in updated_parameter_values:
        if rejection := due_amount_calculation.validate_due_amount_calculation_day_change(
            vault=vault
        ):
            return PreParameterChangeHookResult(rejection=rejection)

        # TODO INC-8842 implement repayment holiday

    return None


def _get_total_arrears_amount(denomination: str, balances: BalanceDefaultDict) -> Decimal:
    return utils.sum_balances(
        balances=balances,
        addresses=[
            line_of_credit_addresses.TOTAL_PRINCIPAL_OVERDUE,
            line_of_credit_addresses.TOTAL_INTEREST_OVERDUE,
        ],
        denomination=denomination,
    )


def _get_total_early_repayment_amount(
    vault: SmartContractVault, denomination: str, balances: BalanceDefaultDict
) -> Decimal:
    overpayment_fee_rate = overpayment.get_overpayment_fee_rate_parameter(vault=vault)
    max_overpayment_fee = overpayment.get_max_overpayment_fee(
        fee_rate=overpayment_fee_rate,
        balances=balances,
        denomination=denomination,
        precision=2,  # TODO: change after INC-9649
        principal_address=line_of_credit_addresses.TOTAL_PRINCIPAL,
    )
    total_outstanding_amount = utils.sum_balances(
        balances=balances,
        addresses=line_of_credit_addresses.OUTSTANDING_DEBT_ADDRESSES,
        denomination=denomination,
        decimal_places=2,  # TODO: change after INC-9649
    )
    return total_outstanding_amount + max_overpayment_fee


def _get_total_monthly_repayment_amount(denomination: str, balances: BalanceDefaultDict) -> Decimal:
    # TODO: sum_balances is being used here instead of balance_at_coordinates because
    # balance_at_coordinates seems to return Decimal("-0"), whereas sum_balances just
    # returns Decimal("0"). The reason for this has not yet been determined but will be
    # investigated as a part of  https://pennyworth.atlassian.net/browse/INC-9773,
    # at which point we should re-examine the use of sum_balances here
    return utils.sum_balances(
        balances=balances,
        addresses=[line_of_credit_addresses.TOTAL_EMI],
        denomination=denomination,
        decimal_places=2,  # TODO: change after INC-9649
    )


def _get_total_outstanding_due_amount(denomination: str, balances: BalanceDefaultDict) -> Decimal:
    return utils.sum_balances(
        balances=balances,
        addresses=[
            line_of_credit_addresses.TOTAL_PRINCIPAL_DUE,
            line_of_credit_addresses.TOTAL_INTEREST_DUE,
        ],
        denomination=denomination,
    )


def _get_total_original_principal(denomination: str, balances: BalanceDefaultDict) -> Decimal:
    # TODO: sum_balances is being used here instead of balance_at_coordinates because
    # balance_at_coordinates seems to return Decimal("-0"), whereas sum_balances just
    # returns Decimal("0"). The reason for this has not yet been determined but will be
    # investigated as a part of  https://pennyworth.atlassian.net/browse/INC-9773,
    # at which point we should re-examine the use of sum_balances here
    return utils.sum_balances(
        balances=balances,
        addresses=[line_of_credit_addresses.TOTAL_ORIGINAL_PRINCIPAL],
        denomination=denomination,
        decimal_places=2,  # TODO: change after INC-9649
    )


def _get_total_outstanding_principal(denomination: str, balances: BalanceDefaultDict) -> Decimal:
    return utils.sum_balances(
        balances=balances,
        addresses=[
            line_of_credit_addresses.TOTAL_PRINCIPAL,
            line_of_credit_addresses.TOTAL_PRINCIPAL_DUE,
            line_of_credit_addresses.TOTAL_PRINCIPAL_OVERDUE,
        ],
        denomination=denomination,
    )


def _get_total_available_credit(
    vault: SmartContractVault, total_outstanding_principal: Decimal
) -> Decimal:
    credit_limit_amount: Decimal = utils.get_parameter(
        vault=vault, name=credit_limit.PARAM_CREDIT_LIMIT
    )
    return credit_limit_amount - total_outstanding_principal
