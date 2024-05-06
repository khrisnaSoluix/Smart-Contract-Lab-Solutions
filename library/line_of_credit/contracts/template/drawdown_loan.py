# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.

# standard libs
from datetime import datetime
from decimal import Decimal
from typing import Optional

# library
import library.line_of_credit.constants.addresses as line_of_credit_addresses

# features
import library.features.common.common_parameters as common_parameters
import library.features.v4.common.events as events
import library.features.common.fetchers as fetchers
import library.features.v4.common.supervisor_utils as supervisor_utils
import library.features.v4.common.utils as utils
import library.features.v4.lending.amortisations.declining_principal as declining_principal
import library.features.v4.lending.close_loan as close_loan
import library.features.v4.lending.disbursement as disbursement
import library.features.v4.lending.due_amount_calculation as due_amount_calculation
import library.features.v4.lending.early_repayment as early_repayment
import library.features.v4.lending.emi as emi
import library.features.v4.lending.interest_accrual as interest_accrual
import library.features.v4.lending.interest_application as interest_application
import library.features.v4.lending.interest_rate.fixed as fixed_rate
import library.features.v4.lending.lending_addresses as lending_addresses
import library.features.v4.lending.lending_parameters as lending_parameters
import library.features.v4.lending.overpayment as overpayment

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    AccountIdShape,
    ActivationHookArguments,
    ActivationHookResult,
    BalanceDefaultDict,
    CustomInstruction,
    DeactivationHookArguments,
    DeactivationHookResult,
    DerivedParameterHookArguments,
    DerivedParameterHookResult,
    NumberShape,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    Posting,
    PostingInstructionsDirective,
    PrePostingHookArguments,
    PrePostingHookResult,
    Rejection,
    RejectionReason,
    Tside,
    fetch_account_data,
    requires,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

api = "4.0.0"
version = "2.0.0"
display_name = "Line of Credit Drawdown Loan"
tside = Tside.ASSET

# this can be amended to whichever other currencies as needed
supported_denominations = ["GBP"]

data_fetchers = [
    fetchers.EFFECTIVE_OBSERVATION_FETCHER,
    fetchers.LIVE_BALANCES_BOF,
]

# parameters
PARAM_LOC_ACCOUNT_ID = "line_of_credit_account_id"
PARAM_PENALTY_INTEREST_RATE = "penalty_interest_rate"
PARAM_INCLUDE_BASE_RATE_IN_PENALTY_RATE = "include_base_rate_in_penalty_rate"
PARAM_PENALTY_INTEREST_INCOME_ACCOUNT = "penalty_interest_income_account"
PARAM_PER_LOAN_EARLY_REPAYMENT_AMOUNT = "per_loan_early_repayment_amount"

# other constants
ACCOUNT_TYPE = "DRAWDOWN_LOAN"

parameters = [
    # Instance Parameters
    Parameter(
        name=PARAM_LOC_ACCOUNT_ID,
        shape=AccountIdShape(),
        level=ParameterLevel.INSTANCE,
        description="Linked line of credit account id",
        display_name="Line Of Credit Account Id",
        default_value="00000000-0000-0000-0000-000000000000",
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
    # Penalty Parameters
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
        shape=common_parameters.BooleanShape,
        level=ParameterLevel.TEMPLATE,
        description="If true the penalty interest rate is added to the base interest rate.",
        display_name="Penalty Includes Base Rate",
        default_value=common_parameters.BooleanValueTrue,
    ),
    Parameter(
        name=PARAM_PENALTY_INTEREST_INCOME_ACCOUNT,
        shape=AccountIdShape(),
        level=ParameterLevel.TEMPLATE,
        description="Internal account for penalty interest income.",
        display_name="Penalty Interest Income Account",
        default_value="PENALTY_INTEREST_INCOME",
    ),
    # Derived Parameters
    Parameter(
        name=PARAM_PER_LOAN_EARLY_REPAYMENT_AMOUNT,
        shape=NumberShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="Total early repayment amount required to fully repay and close the account",
        display_name="Total Early Repayment Amount",
    ),
    # Feature Parameters
    *disbursement.parameters,
    *fixed_rate.parameters,
    *interest_accrual.account_parameters,
    *interest_accrual.accrual_parameters,
    interest_application.application_precision_param,
    *interest_application.account_parameters,
    lending_parameters.total_repayment_count_parameter,
    overpayment.overpayment_fee_rate_param,
    common_parameters.denomination_parameter,
]


@requires(parameters=True)
def activation_hook(
    vault: SmartContractVault, hook_arguments: ActivationHookArguments
) -> Optional[ActivationHookResult]:
    effective_datetime = hook_arguments.effective_datetime
    deposit_account = _get_deposit_account_parameter(vault=vault)
    principal = _get_principal_parameter(vault=vault)
    denomination = common_parameters.get_denomination_parameter(vault=vault)
    loc_account_id = _get_loc_account_id_parameter(vault=vault)

    posting_instructions_directives: list[PostingInstructionsDirective] = []

    activation_custom_instructions: list[CustomInstruction] = []
    activation_custom_instructions.extend(
        disbursement.get_disbursement_custom_instruction(
            account_id=vault.account_id,
            deposit_account_id=deposit_account,
            principal=principal,
            denomination=denomination,
        )
    )
    activation_custom_instructions.extend(
        emi.amortise(
            vault=vault,
            effective_datetime=effective_datetime,
            amortisation_feature=declining_principal.AmortisationFeature,
            interest_calculation_feature=fixed_rate.interest_rate_interface,
        )
    )

    if activation_custom_instructions:
        posting_instructions_directives.append(
            PostingInstructionsDirective(
                posting_instructions=activation_custom_instructions,
                client_batch_id=f"{ACCOUNT_TYPE}_{events.ACCOUNT_ACTIVATION}_"
                f"{vault.get_hook_execution_id()}",
                value_datetime=effective_datetime,
            )
        )

        activation_aggregate_custom_instructions = (
            supervisor_utils.create_aggregate_posting_instructions(
                aggregate_account_id=loc_account_id,
                posting_instructions_by_supervisee={
                    vault.account_id: activation_custom_instructions
                },
                prefix="TOTAL",
                balances=BalanceDefaultDict(),
                addresses_to_aggregate=[lending_addresses.EMI, lending_addresses.PRINCIPAL],
                rounding_precision=utils.get_parameter(
                    vault=vault, name=interest_application.PARAM_APPLICATION_PRECISION
                ),
            )
        )

        # Populate TOTAL_ORIGINAL_PRINCIPAL
        activation_aggregate_custom_instructions += _get_original_principal_custom_instructions(
            principal=principal, loc_account_id=loc_account_id, denomination=denomination
        )

        if activation_aggregate_custom_instructions:
            posting_instructions_directives.append(
                PostingInstructionsDirective(
                    posting_instructions=activation_aggregate_custom_instructions,
                    client_batch_id=f"AGGREGATE_LOC_{ACCOUNT_TYPE}_{events.ACCOUNT_ACTIVATION}_"
                    f"{vault.get_hook_execution_id()}",
                    value_datetime=effective_datetime,
                )
            )

    return ActivationHookResult(posting_instructions_directives=posting_instructions_directives)


@fetch_account_data(balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID])
@requires(
    parameters=True,
)
def derived_parameter_hook(
    vault: SmartContractVault, hook_arguments: DerivedParameterHookArguments
) -> DerivedParameterHookResult:
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    denomination = common_parameters.get_denomination_parameter(vault=vault)

    total_early_repayment_amount = early_repayment.get_total_early_repayment_amount(
        vault=vault,
        early_repayment_fees=[overpayment.EarlyRepaymentOverpaymentFee],
        balances=balances,
        denomination=denomination,
        debt_addresses=lending_addresses.ALL_OUTSTANDING_SUPERVISOR,
        check_for_outstanding_accrued_interest_on_zero_principal=True,
    )
    derived_parameters: dict[str, utils.ParameterValueTypeAlias] = {
        PARAM_PER_LOAN_EARLY_REPAYMENT_AMOUNT: total_early_repayment_amount,
    }
    return DerivedParameterHookResult(parameters_return_value=derived_parameters)


def pre_posting_hook(
    vault: SmartContractVault, hook_arguments: PrePostingHookArguments
) -> Optional[PrePostingHookResult]:
    if utils.is_force_override(posting_instructions=hook_arguments.posting_instructions):
        return None

    return PrePostingHookResult(
        rejection=Rejection(
            message="All postings should be made to the Line of Credit account",
            reason_code=RejectionReason.CLIENT_CUSTOM_REASON,
        )
    )


@fetch_account_data(balances=[fetchers.LIVE_BALANCES_BOF_ID])
@requires(parameters=True)
def deactivation_hook(
    vault: SmartContractVault, hook_arguments: DeactivationHookArguments
) -> Optional[DeactivationHookResult]:
    balances = vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances
    denomination = common_parameters.get_denomination_parameter(vault=vault)
    loc_account = _get_loc_account_id_parameter(vault=vault)
    principal = _get_principal_parameter(vault=vault)

    if outstanding_debt_rejection := close_loan.reject_closure_when_outstanding_debt(
        balances=balances,
        denomination=denomination,
        debt_addresses=lending_addresses.ALL_OUTSTANDING_SUPERVISOR,
    ):
        return DeactivationHookResult(rejection=outstanding_debt_rejection)

    loan_closure_custom_instructions = close_loan.net_balances(
        balances=balances,
        denomination=denomination,
        account_id=vault.account_id,
        residual_cleanup_features=[
            overpayment.OverpaymentResidualCleanupFeature,
            due_amount_calculation.DueAmountCalculationResidualCleanupFeature,
        ],
    )

    # TODO: Revisit this after INC-9433
    # While the drawdown loan is active, repayments are received by the line of credit account and
    # tracked using the INTERNAL CONTRA address on the drawdown loan. This is done to prevent the
    # triggering of posting hooks for each repayment.

    # After balancing the relevant trackers, the amount left in the INTERNAL CONTRA address should
    # be equal to the total from all the repayments to this drawdown loan
    balances_after_closure_instructions = utils.update_inflight_balances(
        account_id=vault.account_id,
        tside=Tside.ASSET,
        current_balances=balances,
        posting_instructions=loan_closure_custom_instructions,  # type: ignore
    )
    internal_contra_amount_after_closure_instructions = utils.balance_at_coordinates(
        balances=balances_after_closure_instructions,
        address=lending_addresses.INTERNAL_CONTRA,
        denomination=denomination,
    )

    # When closing the drawdown loan, then total from all the repayments is transferred from the
    # line of credit account to the drawdown loan to balance the INTERNAL CONTRA.
    repayments_postings = utils.create_postings(
        amount=internal_contra_amount_after_closure_instructions,
        debit_account=loc_account,
        credit_account=vault.account_id,
        debit_address=DEFAULT_ADDRESS,
        credit_address=lending_addresses.INTERNAL_CONTRA,
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

    # Net TOTAL_ORIGINAL_PRINCIPAL
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


def _net_aggregate_emi(
    balances: BalanceDefaultDict, loc_account_id: str, denomination: str
) -> list[Posting]:
    net_aggregate_emi_postings: list[Posting] = []

    if emi_amount := utils.balance_at_coordinates(
        balances=balances, address=lending_addresses.EMI, denomination=denomination
    ):
        net_aggregate_emi_postings += utils.create_postings(
            amount=emi_amount,
            debit_account=loc_account_id,
            credit_account=loc_account_id,
            debit_address=lending_addresses.INTERNAL_CONTRA,
            credit_address=f"TOTAL_{lending_addresses.EMI}",
            denomination=denomination,
        )

    return net_aggregate_emi_postings


# parameter getters


def _get_deposit_account_parameter(
    *, vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> str:
    return utils.get_parameter(
        vault=vault,
        name=disbursement.PARAM_DEPOSIT_ACCOUNT,
        at_datetime=effective_datetime,
    )


def _get_loc_account_id_parameter(vault: SmartContractVault) -> str:
    loc_account_id: str = utils.get_parameter(vault=vault, name=PARAM_LOC_ACCOUNT_ID)
    return loc_account_id


def _get_principal_parameter(
    *, vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> Decimal:
    return utils.get_parameter(
        vault=vault,
        name=disbursement.PARAM_PRINCIPAL,
        at_datetime=effective_datetime,
    )


def _get_original_principal_custom_instructions(
    principal: Decimal,
    loc_account_id: str,
    denomination: str,
    is_closing_loan: bool = False,
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
        debit_address = lending_addresses.INTERNAL_CONTRA
        credit_address = line_of_credit_addresses.TOTAL_ORIGINAL_PRINCIPAL
    else:
        debit_address = line_of_credit_addresses.TOTAL_ORIGINAL_PRINCIPAL
        credit_address = lending_addresses.INTERNAL_CONTRA

    if postings := utils.create_postings(
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
