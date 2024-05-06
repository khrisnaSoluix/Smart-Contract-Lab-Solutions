# CBF: Withdrawals and Withdrawal Fees

# standard libs
from datetime import datetime
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.common.addresses as common_addresses
import library.features.common.common_parameters as common_parameters
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.deposit.deposit_interfaces as deposit_interfaces

# contracts api
from contracts_api import (
    AccountNotificationDirective,
    BalanceDefaultDict,
    BalancesFilter,
    BalancesObservationFetcher,
    CustomInstruction,
    DefinedDateTime,
    NumberShape,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    Rejection,
    RejectionReason,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Balance addresses
EARLY_WITHDRAWALS_TRACKER = "EARLY_WITHDRAWALS_TRACKER"


# Fetchers
EARLY_WITHDRAWALS_TRACKER_LIVE_BOF_ID = "EARLY_WITHDRAWALS_TRACKER_LIVE_FETCHER"
EARLY_WITHDRAWALS_TRACKER_LIVE_FETCHER = BalancesObservationFetcher(
    fetcher_id=EARLY_WITHDRAWALS_TRACKER_LIVE_BOF_ID,
    at=DefinedDateTime.LIVE,
    filter=BalancesFilter(addresses=[EARLY_WITHDRAWALS_TRACKER]),
)

# Notifications
WITHDRAWAL_FEE_SUFFIX = "_WITHDRAWAL_FEE"

# Parameters
PARAM_EARLY_WITHDRAWAL_FLAT_FEE = "early_withdrawal_flat_fee"
PARAM_EARLY_WITHDRAWAL_PERCENTAGE_FEE = "early_withdrawal_percentage_fee"
PARAM_MAXIMUM_WITHDRAWAL_PERCENTAGE_LIMIT = "maximum_withdrawal_percentage_limit"
PARAM_FEE_FREE_WITHDRAWAL_PERCENTAGE_LIMIT = "fee_free_withdrawal_percentage_limit"
PARAM_MAXIMUM_WITHDRAWAL_LIMIT = "maximum_withdrawal_limit"
PARAM_FEE_FREE_WITHDRAWAL_LIMIT = "fee_free_withdrawal_limit"

early_withdrawal_flat_fee_parameter = Parameter(
    name=PARAM_EARLY_WITHDRAWAL_FLAT_FEE,
    shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
    level=ParameterLevel.TEMPLATE,
    description="A flat fee applied when making an early withdrawal.",
    display_name="Early Withdrawal Flat Fee",
    default_value=Decimal("10.00"),
)
early_withdrawal_percentage_fee_parameter = Parameter(
    name=PARAM_EARLY_WITHDRAWAL_PERCENTAGE_FEE,
    shape=NumberShape(min_value=Decimal("0"), max_value=Decimal("1")),
    level=ParameterLevel.TEMPLATE,
    description="A percentage fee applied when making an early withdrawal.",
    display_name="Early Withdrawal Percentage Fee",
    default_value=Decimal("0"),
)
maximum_withdrawal_percentage_limit_parameter = Parameter(
    name=PARAM_MAXIMUM_WITHDRAWAL_PERCENTAGE_LIMIT,
    shape=NumberShape(min_value=Decimal("0"), max_value=Decimal("1")),
    level=ParameterLevel.TEMPLATE,
    description="The percentage of the total funds deposited by the customer "
    "that can be withdrawn.",
    display_name="Maximum Withdrawal Percentage Limit",
    default_value=Decimal("0"),
)
fee_free_withdrawal_percentage_limit_parameter = Parameter(
    name=PARAM_FEE_FREE_WITHDRAWAL_PERCENTAGE_LIMIT,
    shape=NumberShape(min_value=Decimal("0"), max_value=Decimal("1"), step=Decimal("0.0001")),
    level=ParameterLevel.INSTANCE,
    description="The percentage of the total funds deposited by the customer "
    "which can be withdrawn without incurring fees.",
    display_name="Fee Free Withdrawal Percentage Limit",
    update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    default_value=Decimal("0"),
)
maximum_withdrawal_limit_parameter = Parameter(
    name=PARAM_MAXIMUM_WITHDRAWAL_LIMIT,
    shape=NumberShape(),
    level=ParameterLevel.INSTANCE,
    derived=True,
    display_name="Maximum Withdrawal Limit",
    description="The total sum of withdrawals cannot exceed this limit.",
)
fee_free_withdrawal_limit_parameter = Parameter(
    name=PARAM_FEE_FREE_WITHDRAWAL_LIMIT,
    shape=NumberShape(),
    level=ParameterLevel.INSTANCE,
    derived=True,
    display_name="Fee Free Withdrawal Limit",
    description="The amount which can be withdrawn without incurring fees.",
)

parameters = [
    early_withdrawal_flat_fee_parameter,
    early_withdrawal_percentage_fee_parameter,
    maximum_withdrawal_percentage_limit_parameter,
    fee_free_withdrawal_percentage_limit_parameter,
    maximum_withdrawal_limit_parameter,
    fee_free_withdrawal_limit_parameter,
]


def notification_type(*, product_name: str) -> str:
    """
    Returns a notification type
    :param product_name: the product name
    :return: notification type
    """
    return f"{product_name.upper()}{WITHDRAWAL_FEE_SUFFIX}"


# Posting helpers
def validate(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    posting_instructions: utils.PostingInstructionListAlias,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
    balance_adjustments: Optional[list[deposit_interfaces.DefaultBalanceAdjustment]] = None,
) -> Optional[Rejection]:
    """
    For use in the pre_posting_hook.
    Deposits are accepted with no validation.
    Reject the posting instructions if any of the following conditions are met:
    - The withdrawal amount exceeds the available balance
    - A partial withdrawal causes the total withdrawal amount to exceed the maximum withdrawal limit
    - The withdrawal occurs on a public holiday and the posting does not include
      `"calendar_override": "true"` in the metadata
    - The withdrawal amount is less than the incurred withdrawal fee amount

    :param vault: the Vault object for the account against which this validation is applied
    :param effective_datetime: datetime at which this method is executed
    :param posting_instructions: list of posting instructions to validate
    :param denomination: the denomination of the account, if not provided the
    'denomination' parameter is retrieved
    :param balances: latest account balances available, if not provided balances will be retrieved
    using the LIVE_BALANCES_BOF_ID
    :param balance_adjustments: list of balance adjustments that impact the default balance,
    used when calculating the customer deposited amount. The customer deposited amount is the sum
    of the DEFAULT balance, EARLY_WITHDRAWALS_TRACKER and the returned amount of each adjustment.
    For example, interest application adjustment should be negative, and a fee
    charge adjustment should be positive.
    :return: rejection if any of the above conditions are met
    """
    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    posting_amount = utils.get_available_balance(
        balances=utils.get_posting_instructions_balances(posting_instructions=posting_instructions),
        denomination=denomination,
    )

    # Deposits are accepted with no validation.
    is_withdrawal = posting_amount < Decimal("0")
    if not is_withdrawal:
        return None

    withdrawal_amount = abs(posting_amount)

    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances

    # Check if the withdrawal amount exceeds the available balance
    current_balance = utils.get_current_net_balance(balances=balances, denomination=denomination)
    if withdrawal_amount > current_balance:
        return Rejection(
            message=f"The withdrawal amount of {withdrawal_amount} {denomination} exceeds the"
            f" available balance of {current_balance} {denomination}.",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )

    # Check if partial withdrawal causes the total withdrawals to exceed maximum withdrawal limit
    is_partial_withdrawal = withdrawal_amount != current_balance
    maximum_withdrawal_limit = _calculate_maximum_withdrawal_limit(
        vault=vault,
        effective_datetime=effective_datetime,
        denomination=denomination,
        balances=balances,
        balance_adjustments=balance_adjustments,
    )
    available_withdrawal_limit = maximum_withdrawal_limit - utils.balance_at_coordinates(
        balances=balances, address=EARLY_WITHDRAWALS_TRACKER, denomination=denomination
    )
    if is_partial_withdrawal and withdrawal_amount > available_withdrawal_limit:
        return Rejection(
            message=f"The withdrawal amount of {withdrawal_amount} {denomination} would exceed "
            f"the available withdrawal limit of {available_withdrawal_limit} {denomination}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

    # Check if withdrawal is being made on calendar event, and if so, is override provided
    calendar_events = vault.get_calendar_events(calendar_ids=["&{PUBLIC_HOLIDAYS}"])
    is_calendar_override = utils.is_key_in_instruction_details(
        key="calendar_override", posting_instructions=posting_instructions
    )
    if (
        utils.falls_on_calendar_events(
            effective_datetime=effective_datetime, calendar_events=calendar_events
        )
        and not is_calendar_override
    ):
        return Rejection(
            message="Cannot withdraw on public holidays.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

    # Check if withdrawal amount is less than the incurred withdrawal fee amount
    flat_fee_amount, percentage_fee_amount = calculate_withdrawal_fee_amounts(
        vault=vault,
        effective_datetime=effective_datetime,
        withdrawal_amount=withdrawal_amount,
        denomination=denomination,
        balances=balances,
        balance_adjustments=balance_adjustments,
    )
    total_fee_amount = flat_fee_amount + percentage_fee_amount
    if withdrawal_amount < total_fee_amount:
        return Rejection(
            message=f"The withdrawal fees of {total_fee_amount} {denomination} are not covered "
            f"by the withdrawal amount of {withdrawal_amount} {denomination}.",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )

    return None


def handle_withdrawals(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    posting_instructions: utils.PostingInstructionListAlias,
    product_name: str,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
    balance_adjustments: Optional[list[deposit_interfaces.DefaultBalanceAdjustment]] = None,
) -> tuple[list[CustomInstruction], list[AccountNotificationDirective]]:
    """
    For use in the post_posting_hook.
    For a withdrawal:
    - Create instruction to track the withdrawal on the EARLY_WITHDRAWALS_TRACKER address
    - Generate the withdrawal fee notification to be used by the bank to orchestrate the
      fee charging externally

    :param vault: the Vault object for the account
    :param effective_datetime: datetime at which this method is executed
    :param posting_instructions: list of posting instructions containing the withdrawal
    :param product_name: the product name
    :param denomination: the denomination of the account, if not provided the
    'denomination' parameter is retrieved
    :param balances: latest account balances available, if not provided balances will be retrieved
    using the LIVE_BALANCES_BOF_ID
    :param balance_adjustments: list of balance adjustments that impact the default balance,
    used when calculating the customer deposited amount. The customer deposited amount is the sum
    of the DEFAULT balance, EARLY_WITHDRAWALS_TRACKER and the returned amount of each adjustment.
    For example, interest application adjustment should be negative, and a fee
    charge adjustment should be positive.
    :return: tuple of the withdrawals tracker instructions and the fee notification
    """
    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances

    posting_amount = utils.get_available_balance(
        balances=utils.get_posting_instructions_balances(posting_instructions=posting_instructions),
        denomination=denomination,
    )

    # Only withdrawals need to be handled
    is_withdrawal = posting_amount < Decimal("0")
    if not is_withdrawal:
        return [], []

    withdrawal_amount = abs(posting_amount)

    withdrawal_tracker_instructions = _update_tracked_withdrawals(
        account_id=vault.account_id,
        withdrawal_amount=withdrawal_amount,
        denomination=denomination,
    )

    current_withdrawal_amount_adjustment = get_current_withdrawal_amount_default_balance_adjustment(
        withdrawal_amount=withdrawal_amount,
    )
    balance_adjustments = balance_adjustments.copy() if balance_adjustments else []
    balance_adjustments.append(current_withdrawal_amount_adjustment)

    flat_fee_amount, percentage_fee_amount = calculate_withdrawal_fee_amounts(
        vault=vault,
        effective_datetime=effective_datetime,
        withdrawal_amount=withdrawal_amount,
        denomination=denomination,
        balances=balances,
        balance_adjustments=balance_adjustments,
    )

    withdrawal_fee_notifications = [
        generate_withdrawal_fee_notification(
            account_id=vault.account_id,
            denomination=denomination,
            withdrawal_amount=withdrawal_amount,
            flat_fee_amount=flat_fee_amount,
            percentage_fee_amount=percentage_fee_amount,
            product_name=product_name,
            client_batch_id=posting_instructions[0].client_batch_id,  # type: ignore
        )
    ]

    return withdrawal_tracker_instructions, withdrawal_fee_notifications


def get_current_withdrawal_amount_default_balance_adjustment(
    *, withdrawal_amount: Decimal
) -> deposit_interfaces.DefaultBalanceAdjustment:
    """

    The customer deposited amount is the sum of the DEFAULT balance, EARLY_WITHDRAWALS_TRACKER
    and the returned amount of each adjustment. However, in post-posting the DEFAULT balance has
    current withdrawal deducted, and the EARLY_WITHDRAWALS_TRACKER has not yet been updated to
    reflect the impact of this withdrawal.
    When calculating the fee amounts, we take previous withdrawals into consideration, so updating
    the withdrawals tracker to reflect the current withdrawal would incorrectly imply that the
    current withdrawal has already been processed, hence updating the balances with the
    withdrawal_tracker_instructions is not suitable.
    Instead, we provide a Default Balance Adjustment which returns the withdrawal amount, which
    will allow the customer deposited amount to be calculated correctly.

    :param withdrawal_amount: the absolute amount withdrawn from the account in this transaction
    :return: the default balance adjustment which accounts for the current withdrawal amount
    """
    return deposit_interfaces.DefaultBalanceAdjustment(
        calculate_balance_adjustment=lambda **_: withdrawal_amount
    )


# Derived parameter helpers
def get_maximum_withdrawal_limit_derived_parameter(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    balance_adjustments: Optional[list[deposit_interfaces.DefaultBalanceAdjustment]] = None,
) -> Decimal:
    """
    Get the maximum withdrawal limit for the derived parameter value

    :param vault: the Vault object for the account
    :param effective_datetime: effective datetime of the hook used for parameter fetching
    :param balances: latest account balances available, if not provided balances will be retrieved
    using the EFFECTIVE_OBSERVATION_FETCHER_ID
    :param denomination: the denomination of the account, if not provided the
    'denomination' parameter is retrieved
    :param balance_adjustments: list of balance adjustments that impact the default balance,
    used when calculating the customer deposited amount. The customer deposited amount is the sum
    of the DEFAULT balance, EARLY_WITHDRAWALS_TRACKER and the returned amount of each adjustment.
    For example, interest application adjustment should be negative, and a fee
    charge adjustment should be positive.
    :return: the maximum withdrawal limit
    """
    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances

    return _calculate_maximum_withdrawal_limit(
        vault=vault,
        balances=balances,
        denomination=denomination,
        effective_datetime=effective_datetime,
        balance_adjustments=balance_adjustments,
    )


def get_fee_free_withdrawal_limit_derived_parameter(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    balance_adjustments: Optional[list[deposit_interfaces.DefaultBalanceAdjustment]] = None,
) -> Decimal:
    """
    Get the fee free withdrawal limit for the derived parameter value

    :param vault: the Vault object for the account
    :param effective_datetime: effective datetime of the hook used for parameter fetching
    :param balances: latest account balances available, if not provided balances will be retrieved
    using the EFFECTIVE_OBSERVATION_FETCHER_ID
    :param denomination: the denomination of the account, if not provided the
    'denomination' parameter is retrieved
    :param balance_adjustments: list of balance adjustments that impact the default balance,
    used when calculating the customer deposited amount. The customer deposited amount is the sum
    of the DEFAULT balance, EARLY_WITHDRAWALS_TRACKER and the returned amount of each adjustment.
    For example, interest application adjustment should be negative, and a fee
    charge adjustment should be positive.
    :return: the fee free withdrawal limit
    """
    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances

    return _calculate_fee_free_withdrawal_limit(
        vault=vault,
        balances=balances,
        denomination=denomination,
        effective_datetime=effective_datetime,
        balance_adjustments=balance_adjustments,
    )


# Withdrawals Tracker helpers
def reset_withdrawals_tracker(
    *,
    vault: SmartContractVault,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Create postings to net-off the withdrawals tracker balance.

    :param vault: the Vault object for the account
    :param balances: latest account balances available, if not provided balances will be retrieved
    using the EARLY_WITHDRAWALS_TRACKER_LIVE_BOF_ID
    :param denomination: the denomination of the account, if not provided the
    'denomination' parameter is retrieved
    :return: list of posting instructions for netting off the withdrawals tracker
    """

    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=EARLY_WITHDRAWALS_TRACKER_LIVE_BOF_ID
        ).balances

    tracker_balance = utils.balance_at_coordinates(
        balances=balances, address=EARLY_WITHDRAWALS_TRACKER, denomination=denomination
    )

    if tracker_balance > Decimal("0"):
        return [
            CustomInstruction(
                postings=utils.create_postings(
                    amount=tracker_balance,
                    debit_account=vault.account_id,
                    credit_account=vault.account_id,
                    debit_address=EARLY_WITHDRAWALS_TRACKER,
                    credit_address=common_addresses.INTERNAL_CONTRA,
                    denomination=denomination,
                ),
                instruction_details={"description": "Resetting the withdrawals tracker"},
                override_all_restrictions=True,
            )
        ]

    return []


def _update_tracked_withdrawals(
    *, account_id: str, withdrawal_amount: Decimal, denomination: str
) -> list[CustomInstruction]:
    """
    Create posting instructions to update the withdrawals tracker balance.

    :param account_id: id of the customer account
    :param withdrawal_amount: the absolute amount withdrawn from the account in this transaction
    :param denomination: the denomination of the account
    :return: list of custom instructions
    """
    if withdrawal_amount > Decimal("0"):
        return [
            CustomInstruction(
                postings=utils.create_postings(
                    amount=withdrawal_amount,
                    debit_account=account_id,
                    credit_account=account_id,
                    debit_address=common_addresses.INTERNAL_CONTRA,
                    credit_address=EARLY_WITHDRAWALS_TRACKER,
                    denomination=denomination,
                ),
                instruction_details={"description": "Updating the withdrawals tracker balance"},
                override_all_restrictions=True,
            )
        ]

    return []


# Notification helpers
def generate_withdrawal_fee_notification(
    *,
    account_id: str,
    denomination: str,
    withdrawal_amount: Decimal,
    flat_fee_amount: Decimal,
    percentage_fee_amount: Decimal,
    product_name: str,
    client_batch_id: str,
) -> AccountNotificationDirective:
    """
    Generate the notification containing the respective fee amounts for a withdrawal

    :param account_id: vault account id for which this notification is sent
    :param denomination: the denomination of the account
    :param withdrawal_amount: the absolute amount withdrawn from the account in this transaction
    :param flat_fee_amount: the flat fee amount chargeable
    :param percentage_fee_amount: the percentage fee amount chargeable
    :param product_name: the product name
    :param client_batch_id: the client_batch_id of the batch containing the withdrawal
    :return: the withdrawal fee account notification directive
    """

    return AccountNotificationDirective(
        notification_type=notification_type(product_name=product_name),
        notification_details={
            "account_id": account_id,
            "denomination": denomination,
            "withdrawal_amount": str(withdrawal_amount),
            "flat_fee_amount": str(flat_fee_amount),
            "percentage_fee_amount": str(percentage_fee_amount),
            "total_fee_amount": str(flat_fee_amount + percentage_fee_amount),
            "client_batch_id": client_batch_id,
        },
    )


# Calculation helpers
def calculate_withdrawal_fee_amounts(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    withdrawal_amount: Decimal,
    denomination: str,
    balances: BalanceDefaultDict,
    balance_adjustments: Optional[list[deposit_interfaces.DefaultBalanceAdjustment]] = None,
) -> tuple[Decimal, Decimal]:
    """
    Calculate the flat fee and percentage fee amounts that are chargeable against a withdrawal

    :param vault: the Vault object for the account
    :param effective_datetime: datetime of the withdrawal
    :param withdrawal_amount: the absolute amount withdrawn from the account in this transaction
    :param denomination: the denomination of the account
    :param balances: the balances to determine the customer's deposited amount
    :param balance_adjustments: list of balance adjustments that impact the default balance,
    used when calculating the customer deposited amount. The customer deposited amount is the sum
    of the DEFAULT balance, EARLY_WITHDRAWALS_TRACKER and the returned amount of each adjustment.
    :return: a tuple of the flat fee amount and the percentage fee amount
    """
    amount_subject_to_fee = _calculate_withdrawal_amount_subject_to_fees(
        vault=vault,
        effective_datetime=effective_datetime,
        withdrawal_amount=withdrawal_amount,
        denomination=denomination,
        balances=balances,
        balance_adjustments=balance_adjustments,
    )

    if amount_subject_to_fee == Decimal("0"):
        return Decimal("0"), Decimal("0")

    flat_fee = _get_early_withdrawal_flat_fee(vault=vault, effective_datetime=effective_datetime)
    percentage_fee = utils.round_decimal(
        amount=(
            amount_subject_to_fee
            * _get_early_withdrawal_percentage_fee(
                vault=vault, effective_datetime=effective_datetime
            )
        ),
        decimal_places=2,
    )

    return flat_fee, percentage_fee


def get_customer_deposit_amount(
    *,
    vault: SmartContractVault,
    balances: BalanceDefaultDict,
    denomination: str,
    balance_adjustments: Optional[list[deposit_interfaces.DefaultBalanceAdjustment]] = None,
) -> Decimal:
    """
    Calculate the amount the customer has deposited in the account. The customer deposited amount
    is the sum of the DEFAULT balance, EARLY_WITHDRAWALS_TRACKER and any adjustments to the
    default balance.

    For example, interest application adjustment should be negative, and a fee
    charge adjustment should be positive.

    :param vault: the Vault object for the account
    :param balances: the balances to determine the customer's deposited amount
    :param denomination: the denomination of the account
    :param balance_adjustments: list of balance adjustments that impact the default balance,
    used when calculating the customer deposited amount.
    :return: the amount the customer has deposited in the account
    """
    default_balance = utils.balance_at_coordinates(balances=balances, denomination=denomination)
    withdrawals_tracker_balance = utils.balance_at_coordinates(
        balances=balances, address=EARLY_WITHDRAWALS_TRACKER, denomination=denomination
    )

    default_balance_adjustment = (
        sum(
            balance_adjustment.calculate_balance_adjustment(
                vault=vault,
                balances=balances,
                denomination=denomination,
            )
            for balance_adjustment in balance_adjustments
        )
        if balance_adjustments is not None
        else Decimal("0")
    )

    return default_balance + withdrawals_tracker_balance + default_balance_adjustment


def _calculate_withdrawal_amount_subject_to_fees(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    withdrawal_amount: Decimal,
    denomination: str,
    balances: BalanceDefaultDict,
    balance_adjustments: Optional[list[deposit_interfaces.DefaultBalanceAdjustment]] = None,
) -> Decimal:
    """
    Calculate the withdrawal amount subject to fee. This is the portion of the withdrawal amount
    that exceeds the fee free limit.

    :param vault: the Vault object for the account
    :param effective_datetime: datetime of the withdrawal
    :param withdrawal_amount: the absolute amount withdrawn from the account in this transaction
    :param denomination: the denomination of the account
    :param balances: the balances to determine the customer's deposited amount
    :param balance_adjustments: list of balance adjustments that impact the default balance,
    used when calculating the customer deposited amount. The customer deposited amount is the sum
    of the DEFAULT balance, EARLY_WITHDRAWALS_TRACKER and the returned amount of each adjustment.
    :return: the amount of the withdrawal which is subject to fees
    """
    withdrawals_tracker_balance = utils.balance_at_coordinates(
        balances=balances, address=EARLY_WITHDRAWALS_TRACKER, denomination=denomination
    )
    fee_free_withdrawal_limit = _calculate_fee_free_withdrawal_limit(
        vault=vault,
        effective_datetime=effective_datetime,
        denomination=denomination,
        balances=balances,
        balance_adjustments=balance_adjustments,
    )

    # Previous withdrawals reduce the remaining fee free limit
    # If we have exceeded the fee free limit, there is 0 fee free limit remaining
    fee_free_withdrawal_limit_remaining = max(
        fee_free_withdrawal_limit - withdrawals_tracker_balance, Decimal("0")
    )

    # If withdrawal amount is less than the remaining fee free limit, then this withdrawal
    # is not subject to fees
    return max(withdrawal_amount - fee_free_withdrawal_limit_remaining, Decimal("0"))


def _calculate_maximum_withdrawal_limit(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    balances: BalanceDefaultDict,
    denomination: str,
    balance_adjustments: Optional[list[deposit_interfaces.DefaultBalanceAdjustment]] = None,
) -> Decimal:
    """
    Calculate the maximum withdrawal limit as a percentage of the customer's deposited amount

    :param vault: the Vault object for the account
    :param effective_datetime: effective datetime of the hook used for parameter fetching
    :param balances: the balances to determine the customer's deposited amount
    :param denomination: the denomination of the account
    :param balance_adjustments: list of balance adjustments that impact the default balance,
    used when calculating the customer deposited amount. The customer deposited amount is the sum
    of the DEFAULT balance, EARLY_WITHDRAWALS_TRACKER and the returned amount of each adjustment.
    :return: the maximum withdrawal limit
    """
    customer_deposit_amount = get_customer_deposit_amount(
        vault=vault,
        balances=balances,
        denomination=denomination,
        balance_adjustments=balance_adjustments,
    )
    return utils.round_decimal(
        amount=(
            customer_deposit_amount
            * _get_maximum_withdrawal_percentage_limit(
                vault=vault, effective_datetime=effective_datetime
            )
        ),
        decimal_places=2,
    )


def _calculate_fee_free_withdrawal_limit(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    balances: BalanceDefaultDict,
    denomination: str,
    balance_adjustments: Optional[list[deposit_interfaces.DefaultBalanceAdjustment]] = None,
) -> Decimal:
    """
    Calculate the fee free withdrawal limit as a percentage of the customer's deposited amount

    :param vault: the Vault object for the account
    :param effective_datetime: effective datetime of the hook used for parameter fetching
    :param balances: the balances to determine the customer's deposited amount
    :param denomination: the denomination of the account
    :param balance_adjustments: list of balance adjustments that impact the default balance,
    used when calculating the customer deposited amount. The customer deposited amount is the sum
    of the DEFAULT balance, EARLY_WITHDRAWALS_TRACKER and the returned amount of each adjustment.
    :return: the fee free withdrawal limit
    """
    customer_deposit_amount = get_customer_deposit_amount(
        vault=vault,
        balances=balances,
        denomination=denomination,
        balance_adjustments=balance_adjustments,
    )
    return utils.round_decimal(
        amount=(
            customer_deposit_amount
            * _get_fee_free_withdrawal_percentage_limit(
                vault=vault, effective_datetime=effective_datetime
            )
        ),
        decimal_places=2,
    )


# Parameter getters
def _get_early_withdrawal_flat_fee(
    *, vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> Decimal:
    return Decimal(
        utils.get_parameter(
            vault=vault, name=PARAM_EARLY_WITHDRAWAL_FLAT_FEE, at_datetime=effective_datetime
        )
    )


def _get_early_withdrawal_percentage_fee(
    *, vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> Decimal:
    return Decimal(
        utils.get_parameter(
            vault=vault, name=PARAM_EARLY_WITHDRAWAL_PERCENTAGE_FEE, at_datetime=effective_datetime
        )
    )


def _get_maximum_withdrawal_percentage_limit(
    *, vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> Decimal:
    return Decimal(
        utils.get_parameter(
            vault=vault,
            name=PARAM_MAXIMUM_WITHDRAWAL_PERCENTAGE_LIMIT,
            at_datetime=effective_datetime,
        )
    )


def _get_fee_free_withdrawal_percentage_limit(
    *, vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> Decimal:
    return Decimal(
        utils.get_parameter(
            vault=vault,
            name=PARAM_FEE_FREE_WITHDRAWAL_PERCENTAGE_LIMIT,
            at_datetime=effective_datetime,
        )
    )
