# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
from library.features.common.common_imports import *  # noqa: F403
import library.features.common.utils as utils
import library.features.deposits.fees.early_closure_fee as early_closure_fee
import library.features.common.account_tiers as account_tiers

# Transaction limits (pre-posting)
import library.features.deposits.transaction_limits.deposit_limits.minimum_initial_deposit as minimum_initial_deposit  # noqa: E501
import library.features.deposits.transaction_limits.deposit_limits.maximum_single_deposit as maximum_single_deposit  # noqa: E501
import library.features.deposits.transaction_limits.deposit_limits.minimum_single_deposit as minimum_single_deposit  # noqa: E501
import library.features.deposits.transaction_limits.deposit_limits.maximum_balance_limit as maximum_balance_limit  # noqa: E501
import library.features.deposits.transaction_limits.deposit_limits.maximum_daily_deposit as maximum_daily_deposit  # noqa: E501
import library.features.deposits.transaction_limits.withdrawal_limits.maximum_daily_withdrawal as maximum_daily_withdrawal  # noqa: E501
import library.features.deposits.transaction_limits.withdrawal_limits.maximum_daily_withdrawal_by_category as maximum_daily_withdrawal_by_category  # noqa: E501
import library.features.deposits.transaction_limits.withdrawal_limits.maximum_single_withdrawal as maximum_single_withdrawal  # noqa: E501
import library.features.deposits.transaction_limits.withdrawal_limits.maximum_withdrawal_by_payment_type as maximum_withdrawal_by_payment_type  # noqa: E501
import library.features.deposits.transaction_limits.withdrawal_limits.minimum_balance_by_tier as minimum_balance_by_tier  # noqa: E501

# Transaction fees (post-posting)
import library.features.deposits.fees.withdrawal.payment_type_flat_fee as payment_type_flat_fee
import library.features.deposits.fees.withdrawal.payment_type_threshold_fee as payment_type_threshold_fee  # noqa: E501
import library.features.deposits.fees.withdrawal.monthly_limit_by_payment_type as monthly_limit_by_payment_type  # noqa: E501

# Accrual features
import library.features.shariah.profit_accrual as profit_accrual
import library.features.shariah.tiered_profit_calculation as tiered_profit_calculation


api = "3.10.0"
version = "2.0.0"
display_name = "Murabahah"
summary = "A CASA account with a fixed profit rate."
tside = Tside.LIABILITY

supported_denominations = [
    "MYR",
]

LOCAL_UTC_OFFSET = 8
events_timezone = "Asia/Kuala_Lumpur"

event_types = profit_accrual.get_event_types("MURABAHAH")


PAYMENT_CATEGORY = "PAYMENT_CATEGORY"
PAYMENT_TYPE = "PAYMENT_TYPE"
INTERNAL_CONTRA = "INTERNAL_CONTRA"

parameters = [
    # instance param
    Parameter(
        name="maximum_daily_payment_category_withdrawal",
        level=Level.TEMPLATE,
        description="The maximum amount allowed for each payment category per day.",
        display_name="Maximum daily payment category withdrawal amount",
        shape=StringShape,
        update_permission=UpdatePermission.USER_EDITABLE,
        default_value=json_dumps(
            {
                "CASH_ADVANCE": "5000",
            }
        ),
    ),
    Parameter(
        name="maximum_daily_payment_type_withdrawal",
        level=Level.TEMPLATE,
        description="The maximum amount allowed for each payment type per day.",
        display_name="Maximum daily payment type withdrawal amount",
        shape=StringShape,
        default_value=json_dumps(
            {
                "ATM": "500",
            }
        ),
    ),
    # template param
    Parameter(
        name="denomination",
        level=Level.TEMPLATE,
        description="Currency in which the product operates.",
        display_name="Denomination",
        shape=DenominationShape,
        default_value="MYR",
    ),
    # internal accounts
    Parameter(
        name="payment_type_fee_income_account",
        level=Level.TEMPLATE,
        description="Internal account for payment type fee income balance.",
        display_name="Payment type fee income account",
        shape=AccountIdShape,
        default_value="PAYMENT_TYPE_FEE_INCOME",
    ),
    *early_closure_fee.parameters,
    *minimum_initial_deposit.parameters,
    *maximum_single_deposit.parameters,
    *minimum_single_deposit.parameters,
    *maximum_balance_limit.parameters,
    *maximum_daily_deposit.parameters,
    *maximum_daily_withdrawal.parameters,
    *maximum_single_withdrawal.parameters,
    *maximum_withdrawal_by_payment_type.parameters,
    *minimum_balance_by_tier.parameters,
    *account_tiers.parameters,
    *payment_type_flat_fee.parameters,
    *payment_type_threshold_fee.parameters,
    *monthly_limit_by_payment_type.parameters,
    *tiered_profit_calculation.parameters,
    *profit_accrual.parameters,
]


@requires(parameters=True, calendar=["&{PUBLIC_HOLIDAYS}"])
def execution_schedules():
    return profit_accrual.get_execution_schedules(vault)


@requires(event_type="ACCRUE_PROFIT", flags=True, parameters=True, balances="1 day")
@requires(
    event_type="APPLY_ACCRUED_PROFIT",
    parameters=True,
    balances="latest",
    calendar=["&{PUBLIC_HOLIDAYS}"],
)
def scheduled_code(event_type, effective_date):
    posting_instructions = []
    denomination = utils.get_parameter(vault, "denomination")

    if event_type == "ACCRUE_PROFIT":
        posting_instructions.extend(
            profit_accrual.get_accrual_posting_instructions(
                vault,
                effective_date,
                denomination,
                tiered_profit_calculation.feature,
            )
        )
    elif event_type == "APPLY_ACCRUED_PROFIT":
        posting_instructions.extend(
            profit_accrual.get_apply_accrual_posting_instructions(
                vault, effective_date, denomination
            )
        )

        _reschedule_apply_accrued_profit_event(vault, effective_date)

    if posting_instructions:
        vault.instruct_posting_batch(
            posting_instructions=posting_instructions,
            effective_date=effective_date,
            client_batch_id=f"{event_type}_{vault.get_hook_execution_id()}",
            batch_details={
                "event": event_type,
            },
        )


@requires(parameters=True, calendar=["&{PUBLIC_HOLIDAYS}"])
def post_parameter_change_code(old_parameters, new_parameters, effective_date):
    if utils.has_parameter_value_changed("profit_application_day", old_parameters, new_parameters):
        _reschedule_apply_accrued_profit_event(vault, effective_date)


@requires(parameters=True, balances="latest live", postings="1 day")
def pre_posting_code(postings, effective_date):
    # allow a force_override to bypass all pre-posting checks
    if postings.batch_details.get("force_override", "false").lower() == "true":
        return

    utils.validate_denomination(vault, postings)

    denomination = utils.get_parameter(vault, "denomination")
    balances = vault.get_balance_timeseries().latest()
    client_transactions = vault.get_client_transactions(include_proposed=True)
    client_transactions_excluding_proposed = vault.get_client_transactions(include_proposed=False)

    # One-off limit checks
    maximum_balance_limit.validate(
        vault=vault, postings=postings, balances=balances, denomination=denomination
    )
    maximum_single_withdrawal.validate(vault=vault, postings=postings, denomination=denomination)
    minimum_initial_deposit.validate(
        vault=vault, postings=postings, balances=balances, denomination=denomination
    )
    minimum_balance_by_tier.validate(
        vault=vault,
        postings=postings,
        balances=balances,
        denomination=denomination,
    )
    maximum_withdrawal_by_payment_type.validate(
        vault=vault, postings=postings, denomination=denomination
    )
    minimum_single_deposit.validate(vault=vault, postings=postings, denomination=denomination)
    maximum_single_deposit.validate(vault=vault, postings=postings, denomination=denomination)

    # Daily limit checks
    category_limit_mapping = utils.get_parameter(
        vault, "maximum_daily_payment_category_withdrawal", is_json=True
    )
    type_limit_mapping = utils.get_parameter(
        vault, "maximum_daily_payment_type_withdrawal", is_json=True
    )
    maximum_daily_deposit.validate(
        vault=vault,
        client_transactions=client_transactions,
        client_transactions_excluding_proposed=client_transactions_excluding_proposed,
        effective_date=effective_date,
        denomination=denomination,
        net_batch=False,
    )
    maximum_daily_withdrawal.validate(
        vault=vault,
        client_transactions=client_transactions,
        client_transactions_excluding_proposed=client_transactions_excluding_proposed,
        effective_date=effective_date,
        denomination=denomination,
        net_batch=False,
    )
    maximum_daily_withdrawal_by_category.validate(
        limit_mapping=category_limit_mapping,
        instruction_detail_key=PAYMENT_CATEGORY,
        postings=postings,
        client_transactions=client_transactions,
        effective_date=effective_date,
        denomination=denomination,
    )
    maximum_daily_withdrawal_by_category.validate(
        limit_mapping=type_limit_mapping,
        instruction_detail_key=PAYMENT_TYPE,
        postings=postings,
        client_transactions=client_transactions,
        effective_date=effective_date,
        denomination=denomination,
    )


@requires(parameters=True, postings="1 month")
def post_posting_code(postings, effective_date):
    denomination = utils.get_parameter(vault, "denomination")
    client_transactions = vault.get_client_transactions(include_proposed=True)

    flat_fees = payment_type_flat_fee.get_fees(
        vault=vault, postings=postings, denomination=denomination
    )
    threshold_fees = payment_type_threshold_fee.get_fees(
        vault=vault, postings=postings, denomination=denomination
    )
    monthly_limit_fees = monthly_limit_by_payment_type.get_fees(
        vault=vault,
        postings=postings,
        client_transactions=client_transactions,
        effective_date=effective_date,
        denomination=denomination,
    )

    posting_instructions = flat_fees + threshold_fees + monthly_limit_fees
    if posting_instructions:
        vault.instruct_posting_batch(
            posting_instructions=posting_instructions, effective_date=effective_date
        )


@requires(parameters=True, balances="latest live")
def close_code(effective_date):
    denomination = utils.get_parameter(vault, "denomination")

    closure_fees = early_closure_fee.get_fees(vault, denomination, effective_date)

    residual_cleanups = profit_accrual.get_residual_cleanup_posting_instructions(
        vault,
        denomination,
        instruction_details={
            "description": "Reverse profit due to account closure",
            "event": "CLOSE_ACCOUNT",
            "account_type": "MURABAHAH",
        },
    )

    posting_instructions = closure_fees + residual_cleanups
    if posting_instructions:
        vault.instruct_posting_batch(
            posting_instructions=posting_instructions,
            effective_date=effective_date,
            client_batch_id=f"{vault.get_hook_execution_id()}",
            batch_details={
                "event": "CLOSE_CODE",
            },
        )


def _reschedule_apply_accrued_profit_event(vault, effective_date: datetime):
    """
    Calculate the next date for apply accrue profit and update the schedule.
    :param vault: Vault object
    :param effective_date: effective date
    :return: None
    """
    apply_profit_schedule = profit_accrual.get_next_apply_accrued_profit_schedule(
        vault, effective_date
    )

    vault.amend_schedule(
        event_type=apply_profit_schedule.event_type, new_schedule=apply_profit_schedule.schedule
    )
