# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.

# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

# features
import library.features.v4.common.events as events
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.lending.amortisations.declining_principal as declining_principal
import library.features.v4.lending.close_loan as close_loan
import library.features.v4.lending.derived_params as derived_params
import library.features.v4.lending.disbursement as disbursement
import library.features.v4.lending.due_amount_calculation as due_amount_calculation
import library.features.v4.lending.emi as emi
import library.features.v4.lending.interest_accrual as interest_accrual
import library.features.v4.lending.interest_application as interest_application
import library.features.v4.lending.interest_rate.variable as variable_rate
import library.features.v4.lending.lending_addresses as lending_addresses
import library.features.v4.lending.lending_interfaces as lending_interfaces
import library.features.v4.lending.lending_parameters as lending_parameters
import library.features.v4.lending.payments as payments
import library.features.v4.lending.redraw as redraw

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    AccountNotificationDirective,
    ActivationHookArguments,
    ActivationHookResult,
    BalanceDefaultDict,
    ConversionHookArguments,
    ConversionHookResult,
    CustomInstruction,
    DeactivationHookArguments,
    DeactivationHookResult,
    DerivedParameterHookArguments,
    DerivedParameterHookResult,
    Parameter,
    ParameterLevel,
    Phase,
    PostingInstructionsDirective,
    PostPostingHookArguments,
    PostPostingHookResult,
    PrePostingHookArguments,
    PrePostingHookResult,
    Rejection,
    RejectionReason,
    ScheduledEvent,
    ScheduledEventHookArguments,
    ScheduledEventHookResult,
    StringShape,
    Tside,
    fetch_account_data,
    requires,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

api = "4.0.0"
version = "2.0.2"
display_name = "Home Loan Redraw"
summary = "A loan suitable for Australian market"
tside = Tside.ASSET

PRODUCT_NAME = "HOME_LOAN_REDRAW"

# address groups
# HLR has no overdue today, so overriding the default definition
REPAYMENT_HIERARCHY = [lending_addresses.PRINCIPAL_DUE, lending_addresses.INTEREST_DUE]
DEBT_ADDRESSES = REPAYMENT_HIERARCHY + [lending_addresses.PRINCIPAL]

supported_denominations = ["AUD"]

data_fetchers = [
    *interest_accrual.data_fetchers,
    interest_application.accrued_interest_eff_fetcher,
    interest_application.accrued_interest_one_month_ago_fetcher,
    fetchers.EFFECTIVE_OBSERVATION_FETCHER,
    fetchers.LIVE_BALANCES_BOF,
]

PARAM_DENOMINATION = "denomination"

parameters = [
    Parameter(
        name=PARAM_DENOMINATION,
        level=ParameterLevel.TEMPLATE,
        description="Denomination",
        display_name="Denomination",
        shape=StringShape(),
        default_value="GBP",
    ),
    *derived_params.all_parameters,
    *disbursement.parameters,
    *due_amount_calculation.schedule_parameters,
    due_amount_calculation.next_repayment_date_parameter,
    *interest_accrual.account_parameters,
    *interest_accrual.accrual_parameters,
    *interest_accrual.schedule_parameters,
    *variable_rate.parameters,
    interest_application.application_precision_param,
    *interest_application.account_parameters,
    lending_parameters.total_repayment_count_parameter,
    *redraw.derived_parameters,
]

event_types = [
    *interest_accrual.event_types(PRODUCT_NAME),
    *due_amount_calculation.event_types(PRODUCT_NAME),
]

# Notifications
PAID_OFF_NOTIFICATION = f"{PRODUCT_NAME}_PAID_OFF"
notification_types = [PAID_OFF_NOTIFICATION]


@requires(parameters=True)
def activation_hook(
    vault: SmartContractVault, hook_arguments: ActivationHookArguments
) -> Optional[ActivationHookResult]:
    denomination: str = utils.get_parameter(vault=vault, name=PARAM_DENOMINATION)
    effective_datetime: datetime = hook_arguments.effective_datetime

    scheduled_events: dict[str, ScheduledEvent] = {
        **interest_accrual.scheduled_events(
            vault=vault, start_datetime=hook_arguments.effective_datetime
        ),
    }

    principal = utils.get_parameter(vault=vault, name=disbursement.PARAM_PRINCIPAL)
    deposit_account_id = utils.get_parameter(vault=vault, name=disbursement.PARAM_DEPOSIT_ACCOUNT)
    disbursement_posting_instructions = disbursement.get_disbursement_custom_instruction(
        account_id=vault.account_id,
        deposit_account_id=deposit_account_id,
        principal=principal,
        denomination=denomination,
    )

    emi_posting_instructions = emi.amortise(
        vault=vault,
        effective_datetime=effective_datetime,
        amortisation_feature=declining_principal.AmortisationFeature,
        interest_calculation_feature=variable_rate.interest_rate_interface,
    )
    pi_directives = PostingInstructionsDirective(
        posting_instructions=[*disbursement_posting_instructions, *emi_posting_instructions],
        client_batch_id=f"{events.ACCOUNT_ACTIVATION}_{vault.get_hook_execution_id()}",
        value_datetime=effective_datetime,
    )
    scheduled_events = {
        **interest_accrual.scheduled_events(
            vault=vault, start_datetime=hook_arguments.effective_datetime
        ),
        **due_amount_calculation.scheduled_events(
            vault=vault, account_opening_datetime=hook_arguments.effective_datetime
        ),
    }

    return ActivationHookResult(
        posting_instructions_directives=[pi_directives],
        scheduled_events_return_value=scheduled_events,
    )


def conversion_hook(
    vault: SmartContractVault, hook_arguments: ConversionHookArguments
) -> Optional[ConversionHookResult]:
    return ConversionHookResult(scheduled_events_return_value=hook_arguments.existing_schedules)


@fetch_account_data(balances=[fetchers.LIVE_BALANCES_BOF_ID])
@requires(parameters=True)
def deactivation_hook(
    vault: SmartContractVault, hook_arguments: DeactivationHookArguments
) -> Optional[DeactivationHookResult]:
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.LIVE_BALANCES_BOF_ID
    ).balances
    denomination: str = utils.get_parameter(vault=vault, name=PARAM_DENOMINATION)
    if outstanding_debt_rejection := close_loan.reject_closure_when_outstanding_debt(
        balances=balances,
        denomination=denomination,
    ):
        return DeactivationHookResult(rejection=outstanding_debt_rejection)

    if outstanding_redraw_funds_rejection := redraw.reject_closure_when_outstanding_redraw_funds(
        balances=balances,
        denomination=denomination,
    ):
        return DeactivationHookResult(rejection=outstanding_redraw_funds_rejection)

    posting_instructions_to_net_balances = close_loan.net_balances(
        balances=balances,
        denomination=denomination,
        account_id=vault.account_id,
        residual_cleanup_features=[
            due_amount_calculation.DueAmountCalculationResidualCleanupFeature
        ],
    )

    if posting_instructions_to_net_balances:
        return DeactivationHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=posting_instructions_to_net_balances,
                    value_datetime=hook_arguments.effective_datetime,
                )
            ]
        )
    return None


@fetch_account_data(balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID])
@requires(
    last_execution_datetime=[due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT], parameters=True
)
def derived_parameter_hook(
    vault: SmartContractVault, hook_arguments: DerivedParameterHookArguments
) -> DerivedParameterHookResult:
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    denomination: str = utils.get_parameter(vault=vault, name=PARAM_DENOMINATION)

    # available redraw funds
    available_redraw_funds = redraw.get_available_redraw_funds(
        balances=balances, denomination=denomination
    )

    # next_repayment_date
    next_repayment_datetime = _calculate_next_repayment_date(
        vault=vault, derived_parameter_hook_args=hook_arguments
    )

    # total outstanding debt
    total_outstanding_debt = derived_params.get_total_outstanding_debt(
        balances=balances,
        denomination=denomination,
    )

    # total outstanding payments
    total_outstanding_payments = derived_params.get_total_due_amount(
        balances=balances,
        denomination=denomination,
    )

    # total remaining principal
    total_remaining_principal = derived_params.get_total_remaining_principal(
        balances=balances,
        denomination=denomination,
    )

    _, remaining_term = declining_principal.term_details(
        vault=vault,
        effective_datetime=hook_arguments.effective_datetime,
        use_expected_term=False,
        interest_rate=variable_rate.interest_rate_interface,
        principal_adjustments=[
            lending_interfaces.PrincipalAdjustment(
                calculate_principal_adjustment=lambda vault, balances, denomination: available_redraw_funds  # noqa: E501
                * -1
            )
        ],
        balances=balances,
        denomination=denomination,
    )

    derived_parameters: dict[str, utils.ParameterValueTypeAlias] = {
        redraw.PARAM_AVAILABLE_REDRAW_FUNDS: available_redraw_funds,
        due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE: next_repayment_datetime,
        derived_params.PARAM_REMAINING_TERM: remaining_term,
        derived_params.PARAM_TOTAL_OUTSTANDING_DEBT: total_outstanding_debt,
        derived_params.PARAM_TOTAL_OUTSTANDING_PAYMENTS: total_outstanding_payments,
        derived_params.PARAM_TOTAL_REMAINING_PRINCIPAL: total_remaining_principal,
    }

    return DerivedParameterHookResult(parameters_return_value=derived_parameters)


@fetch_account_data(balances=[fetchers.LIVE_BALANCES_BOF_ID])
@requires(parameters=True)
def pre_posting_hook(
    vault: SmartContractVault, hook_arguments: PrePostingHookArguments
) -> Optional[PrePostingHookResult]:
    posting_instructions = hook_arguments.posting_instructions
    if utils.is_force_override(posting_instructions=posting_instructions):
        return None

    denomination: str = utils.get_parameter(vault=vault, name=PARAM_DENOMINATION)
    if invalid_denomination_rejection := utils.validate_denomination(
        posting_instructions=posting_instructions,
        accepted_denominations=[denomination],
    ):
        return PrePostingHookResult(rejection=invalid_denomination_rejection)

    if invalid_posting_instructions_rejection := utils.validate_single_hard_settlement_or_transfer(
        posting_instructions=posting_instructions
    ):
        return PrePostingHookResult(rejection=invalid_posting_instructions_rejection)

    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.LIVE_BALANCES_BOF_ID
    ).balances
    posting_amount: Decimal = (
        hook_arguments.posting_instructions[0]
        .balances()[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)]
        .net
    )
    if invalid_redraw_funds_rejection := redraw.validate_redraw_funds(
        balances=balances,
        posting_amount=posting_amount,
        denomination=denomination,
    ):
        return PrePostingHookResult(rejection=invalid_redraw_funds_rejection)

    total_outstanding_debt = derived_params.get_total_outstanding_debt(
        balances=balances,
        denomination=denomination,
    )
    remaining_redraw_balance = redraw.get_available_redraw_funds(
        balances=balances, denomination=denomination
    )
    if posting_amount < 0 and abs(posting_amount) > (
        total_outstanding_debt - remaining_redraw_balance
    ):
        return PrePostingHookResult(
            rejection=Rejection(
                message=f"Cannot make a payment of {abs(posting_amount)} {denomination} "
                f"greater than the net difference of the total outstanding debt of "
                f"{total_outstanding_debt} {denomination} and the remaining redraw "
                f"balance of {remaining_redraw_balance} {denomination}.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )

    return None


@fetch_account_data(balances=[fetchers.LIVE_BALANCES_BOF_ID])
@requires(parameters=True)
def post_posting_hook(
    vault: SmartContractVault, hook_arguments: PostPostingHookArguments
) -> Optional[PostPostingHookResult]:
    denomination: str = utils.get_parameter(vault=vault, name=PARAM_DENOMINATION)
    # in the pre-posting hook, we only accept posting instructions of length 1,
    # so we can just do posting_instructions[0] here
    posting_amount: Decimal = (
        hook_arguments.posting_instructions[0]
        .balances()[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)]
        .net
    )

    posting_instructions: list[CustomInstruction] = []
    account_notification_directives: list[AccountNotificationDirective] = []

    if posting_amount < 0:
        posting_instructions += payments.generate_repayment_postings(
            vault=vault,
            hook_arguments=hook_arguments,
            repayment_hierarchy=REPAYMENT_HIERARCHY,
            overpayment_features=[redraw.OverpaymentFeature],
        )

        account_notification_directives += _check_and_send_closure_notification(
            repayment_posting_instructions=posting_instructions,
            balances=vault.get_balances_observation(
                fetcher_id=fetchers.LIVE_BALANCES_BOF_ID
            ).balances,
            denomination=denomination,
            account_id=vault.account_id,
        )

    elif posting_amount > 0:
        posting_instructions += _process_withdrawal(
            account_id=vault.account_id, withdrawal_amount=posting_amount, denomination=denomination
        )
    if posting_instructions:
        return PostPostingHookResult(
            account_notification_directives=account_notification_directives,
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=posting_instructions,
                    client_batch_id=f"{vault.get_hook_execution_id()}",
                    value_datetime=hook_arguments.effective_datetime,
                )
            ],
        )

    return None


@requires(event_type=interest_accrual.ACCRUAL_EVENT, parameters=True)
@fetch_account_data(event_type=interest_accrual.ACCRUAL_EVENT, balances=[fetchers.EOD_FETCHER_ID])
@requires(
    event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
    last_execution_datetime=[due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT],
    parameters=True,
)
@fetch_account_data(
    event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
    balances=[
        fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID,
        interest_application.ACCRUED_INTEREST_EFF_FETCHER_ID,
        interest_application.ACCRUED_INTEREST_ONE_MONTH_AGO_FETCHER_ID,
    ],
)
def scheduled_event_hook(
    vault: SmartContractVault, hook_arguments: ScheduledEventHookArguments
) -> Optional[ScheduledEventHookResult]:
    posting_instructions: list[CustomInstruction] = []
    account_notification_directives: list[AccountNotificationDirective] = []
    if hook_arguments.event_type == interest_accrual.ACCRUAL_EVENT:
        posting_instructions += interest_accrual.daily_accrual_logic(
            vault=vault,
            interest_rate_feature=variable_rate.interest_rate_interface,
            hook_arguments=hook_arguments,
            account_type=PRODUCT_NAME,
            principal_addresses=[lending_addresses.PRINCIPAL, redraw.REDRAW_ADDRESS],
        )
    elif hook_arguments.event_type == due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT:
        due_postings, returned_account_notification_directives = _calculate_due_amounts(
            vault=vault, hook_arguments=hook_arguments
        )
        account_notification_directives += returned_account_notification_directives
        posting_instructions += due_postings
    if posting_instructions:
        return ScheduledEventHookResult(
            account_notification_directives=account_notification_directives,
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=posting_instructions,
                    value_datetime=hook_arguments.effective_datetime,
                )
            ],
        )
    return None


# helper functions
def _calculate_due_amounts(
    vault: SmartContractVault, hook_arguments: ScheduledEventHookArguments
) -> tuple[list[CustomInstruction], list[AccountNotificationDirective]]:
    """
    A top level wrapper that creates posting instructions for any due amounts
    and any auto-repayments that pay off some or all of those due amounts
    from the current redraw balance.

    :param vault: The vault object from the scheduled event hook
    :param hook_arguments: The hook arguments from the scheduled event hook
    :return: A tuple containing the list of due posting instructions and
    a list of account notifications
    """
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    denomination: str = utils.get_parameter(vault=vault, name=PARAM_DENOMINATION)
    due_amount_posting_instructions = due_amount_calculation.schedule_logic(
        vault=vault,
        hook_arguments=hook_arguments,
        account_type=PRODUCT_NAME,
        interest_application_feature=interest_application.InterestApplication,
        amortisation_feature=declining_principal.AmortisationFeature,
    )
    auto_repayment_posting_instructions = redraw.auto_repayment(
        balances=balances,
        due_amount_posting_instructions=due_amount_posting_instructions,
        denomination=denomination,
        account_id=vault.account_id,
        repayment_hierarchy=REPAYMENT_HIERARCHY,
    )
    account_notification_directives = _check_and_send_closure_notification(
        repayment_posting_instructions=auto_repayment_posting_instructions,
        balances=balances,
        denomination=denomination,
        account_id=vault.account_id,
    )
    return (
        due_amount_posting_instructions + auto_repayment_posting_instructions,
        account_notification_directives,
    )


def _calculate_next_repayment_date(
    vault: SmartContractVault, derived_parameter_hook_args: DerivedParameterHookArguments
) -> datetime:
    """
    Determines the next repayment date based on the due amount calculation date and the
    effective datetime from the derived parameter hook.
    IMPORTANT: This function assumes that the due amount calculation date does not change,
    which is true for the current version of home loan redraw.

    :param vault: The vault object from the derived parameter hook
    :param derived_parameter_hook_args: The hook arguments from the derived parameter hook
    :return: The next repayment date
    """
    effective_datetime: datetime = derived_parameter_hook_args.effective_datetime
    first_due_datetime = due_amount_calculation.get_first_due_amount_calculation_datetime(
        vault=vault
    )
    if effective_datetime.date() <= first_due_datetime.date():
        return first_due_datetime

    due_amount_calc_day = utils.get_parameter(
        vault=vault, name=due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
    )
    potential_next_due_amount_calc = datetime(
        year=effective_datetime.year,
        month=effective_datetime.month,
        day=due_amount_calc_day,
        tzinfo=ZoneInfo("UTC"),
    )
    return (
        potential_next_due_amount_calc
        if effective_datetime.date() <= potential_next_due_amount_calc.date()
        else potential_next_due_amount_calc + relativedelta(months=1)
    )


def _check_and_send_closure_notification(
    repayment_posting_instructions: list[CustomInstruction],
    balances: BalanceDefaultDict,
    denomination: str,
    account_id: str,
) -> list[AccountNotificationDirective]:
    """
    Determines whether the repayment(s) clear(s) the outstanding debt
    and returns an account notification directive if so.
    Handles both auto-repayments via redraw funds and customer initiated repayments.

    :param repayment_posting_instructions: The repayment posting instructions
    :param balances: The current balances used to check the outstanding debt and redraw amounts
    :param denomination: The denomination of the account and the repayment
    :param account_id: The id of the account the repayment is for
    :return: A list of account closure notifications
    """

    account_notification_directives: list[AccountNotificationDirective] = []
    if close_loan.does_repayment_fully_repay_loan(
        repayment_posting_instructions=repayment_posting_instructions,
        balances=balances,
        denomination=denomination,
        account_id=account_id,
    ):
        account_notification_directives += [
            AccountNotificationDirective(
                notification_type=PAID_OFF_NOTIFICATION,
                notification_details={"account_id": account_id},
            )
        ]

    return account_notification_directives


def _process_withdrawal(
    account_id: str, withdrawal_amount: Decimal, denomination: str
) -> list[CustomInstruction]:
    """
    Creates posting instructions to redraw the withdrawal amount from the redraw balance

    :param account_id: The id of the account
    :param withdrawal_amount: The amount to withdrawal from the redraw balance
    :param denomination: The denomination of the account
    :return: A list of posting instructions that will withdrawal from the redraw balance
    """
    postings = utils.create_postings(
        debit_account=account_id,
        debit_address=redraw.REDRAW_ADDRESS,
        denomination=denomination,
        amount=withdrawal_amount,
        credit_account=account_id,
        credit_address=DEFAULT_ADDRESS,
    )
    return [
        CustomInstruction(
            postings=postings,
            instruction_details={
                "description": "Redraw funds from the redraw account",
                "event": "REDRAW_FUNDS_WITHDRAWAL",
            },
        )
    ]
