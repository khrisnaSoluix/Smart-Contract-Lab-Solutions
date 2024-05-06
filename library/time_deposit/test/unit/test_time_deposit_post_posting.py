# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, PropertyMock, call, patch, sentinel

# library
import library.time_deposit.contracts.template.time_deposit as time_deposit
from library.time_deposit.test.unit.test_time_deposit_common import TimeDepositTest

# features
import library.features.common.fetchers as fetchers
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import DEFAULT_ADDRESS, PostPostingHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    ACCOUNT_ID,
    DEFAULT_DATETIME,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    AccountNotificationDirective,
    CustomInstruction,
    PostingInstructionsDirective,
    PostPostingHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    DEFAULT_POSTINGS,
    SentinelAccountNotificationDirective,
    SentinelBalancesObservation,
    SentinelCustomInstruction,
)


class PostPostingHookCommonTest:
    """
    This class is intended to be used as a shared class, to be inherited by the Test classes defined
    below and never to be run in isolation. Class Inheritance means that the defined tests within
    this class are executed for each class that inherits from it.

    Note that the ordering of inheritance in the below class is important
    """

    default_denom: str

    def setUp(self) -> None:
        # mock vault
        self.mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live"),
            },
        )

        mock_posting_instruction = MagicMock()
        mock_posting_instruction.client_batch_id = "client_batch_id"
        self.hook_args_posting_instructions = [mock_posting_instruction]

        self.hook_args = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=self.hook_args_posting_instructions,
            client_transactions=sentinel.client_transactions,
        )

        # is_force_override
        patch_is_force_override = patch.object(time_deposit.utils, "is_force_override")
        self.mock_is_force_override = patch_is_force_override.start()
        self.mock_is_force_override.return_value = False

        # get_parameter
        patch_get_parameter = patch.object(time_deposit.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={time_deposit.common_parameters.PARAM_DENOMINATION: self.default_denom}
        )

        # get_available_balance
        patch_get_available_balance = patch.object(time_deposit.utils, "get_available_balance")
        self.mock_get_available_balance = patch_get_available_balance.start()
        self.mock_get_available_balance.return_value = Decimal("-1")  # posting_amount

        # get_posting_instructions_balances
        patch_get_posting_instructions_balances = patch.object(
            time_deposit.utils, "get_posting_instructions_balances"
        )
        self.mock_get_posting_instructions_balances = (
            patch_get_posting_instructions_balances.start()
        )
        self.mock_get_posting_instructions_balances.return_value = sentinel.posting_balances

        # get_grace_period_parameter
        patch_get_grace_period_parameter = patch.object(
            time_deposit.grace_period, "get_grace_period_parameter"
        )
        self.mock_get_grace_period_parameter = patch_get_grace_period_parameter.start()
        self.mock_get_grace_period_parameter.return_value = 0

        # handle_withdrawals
        patch_handle_withdrawals = patch.object(time_deposit.withdrawal_fees, "handle_withdrawals")
        self.mock_handle_withdrawals = patch_handle_withdrawals.start()
        self.mock_handle_withdrawals.return_value = (
            [SentinelCustomInstruction("withdrawal_fees")],
            [SentinelAccountNotificationDirective("withdrawal_fees")],
        )

        # _handle_withdrawal_fees_with_number_of_interest_days_fee
        patch_handle_withdrawal_fees_with_number_of_interest_days_fee = patch.object(
            time_deposit, "_handle_withdrawal_fees_with_number_of_interest_days_fee"
        )
        self.mock_handle_withdrawal_fees_with_number_of_interest_days_fee = (
            patch_handle_withdrawal_fees_with_number_of_interest_days_fee.start()
        )
        self.mock_handle_withdrawal_fees_with_number_of_interest_days_fee.return_value = [
            SentinelAccountNotificationDirective("withdrawal_fees_inc_number_of_interest_days")
        ]

        # _handle_full_withdrawal_notification
        patch_handle_full_withdrawal_notification = patch.object(
            time_deposit, "_handle_full_withdrawal_notification"
        )
        self.mock_handle_full_withdrawal_notification = (
            patch_handle_full_withdrawal_notification.start()
        )
        self.mock_handle_full_withdrawal_notification.return_value = []

        # generate_withdrawal_fee_notification
        patch_generate_withdrawal_fee_notification = patch.object(
            time_deposit.withdrawal_fees, "generate_withdrawal_fee_notification"
        )
        self.mock_generate_withdrawal_fee_notification = (
            patch_generate_withdrawal_fee_notification.start()
        )
        self.mock_generate_withdrawal_fee_notification.return_value = (
            SentinelAccountNotificationDirective("zero_fee")
        )

        # _update_notification_with_number_of_interest_days_fee
        patch_update_notification_with_number_of_interest_days_fee = patch.object(
            time_deposit, "_update_notification_with_number_of_interest_days_fee"
        )
        self.mock_update_notification_with_number_of_interest_days_fee = (
            patch_update_notification_with_number_of_interest_days_fee.start()
        )
        self.mock_update_notification_with_number_of_interest_days_fee.return_value = (
            SentinelAccountNotificationDirective("zero_fee_with_number_of_interest_days")
        )

        # _handle_partial_interest_forfeiture
        patch_handle_partial_interest_forfeiture = patch.object(
            time_deposit, "_handle_partial_interest_forfeiture"
        )
        self.mock_handle_partial_interest_forfeiture = (
            patch_handle_partial_interest_forfeiture.start()
        )
        self.mock_handle_partial_interest_forfeiture.return_value = []

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_force_override_returns_none(self):
        self.mock_is_force_override.return_value = True
        self.assertIsNone(
            time_deposit.post_posting_hook(vault=self.mock_vault, hook_arguments=self.hook_args)
        )

    def test_no_interest_forfeited_for_deposits(self):
        self.mock_get_available_balance.return_value = Decimal("1")  # posting_amount
        self.assertIsNone(
            time_deposit.post_posting_hook(vault=self.mock_vault, hook_arguments=self.hook_args)
        )
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=self.hook_args_posting_instructions
        )
        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.posting_balances, denomination=self.default_denom
        )
        self.mock_handle_partial_interest_forfeiture.assert_not_called()

    def test_no_interest_is_forfeited_for_partial_withdrawals_when_no_interest_has_been_accrued(
        self,
    ):
        self.mock_handle_partial_interest_forfeiture.return_value = []

        expected_result = PostPostingHookResult(
            account_notification_directives=[
                SentinelAccountNotificationDirective("zero_fee_with_number_of_interest_days"),
            ]
        )
        self.assertEqual(
            time_deposit.post_posting_hook(vault=self.mock_vault, hook_arguments=self.hook_args),
            expected_result,
        )
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=self.hook_args_posting_instructions
        )
        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.posting_balances, denomination=self.default_denom
        )
        self.mock_handle_partial_interest_forfeiture.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.balances_live,
            withdrawal_amount=Decimal("1"),
        )

    def test_interest_is_forfeited_for_partial_withdrawals(self):
        self.mock_handle_partial_interest_forfeiture.return_value = [
            SentinelCustomInstruction("interest_forfeiture")
        ]
        expected_result = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[SentinelCustomInstruction("interest_forfeiture")],
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
            account_notification_directives=[
                SentinelAccountNotificationDirective("zero_fee_with_number_of_interest_days")
            ],
        )
        self.assertEqual(
            time_deposit.post_posting_hook(vault=self.mock_vault, hook_arguments=self.hook_args),
            expected_result,
        )
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=self.hook_args_posting_instructions
        )
        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.posting_balances, denomination=self.default_denom
        )
        self.mock_handle_partial_interest_forfeiture.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.balances_live,
            withdrawal_amount=Decimal("1"),
        )

    def test_interest_is_forfeited_and_notification_sent_for_full_withdrawal(self):
        self.mock_get_available_balance.return_value = Decimal("-1")
        self.mock_handle_full_withdrawal_notification.return_value = [
            SentinelAccountNotificationDirective("full_withdrawal")
        ]
        self.mock_handle_partial_interest_forfeiture.return_value = [
            SentinelCustomInstruction("interest_forfeiture")
        ]
        expected_result = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[
                        SentinelCustomInstruction("interest_forfeiture"),
                    ],
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
            account_notification_directives=[
                SentinelAccountNotificationDirective("zero_fee_with_number_of_interest_days"),
                SentinelAccountNotificationDirective("full_withdrawal"),
            ],
        )
        self.assertEqual(
            time_deposit.post_posting_hook(vault=self.mock_vault, hook_arguments=self.hook_args),
            expected_result,
        )
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=self.hook_args_posting_instructions
        )
        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.posting_balances, denomination=self.default_denom
        )
        self.mock_handle_partial_interest_forfeiture.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.balances_live,
            withdrawal_amount=Decimal("1"),
        )
        self.mock_handle_full_withdrawal_notification.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.balances_live,
            denomination=self.default_denom,
        )


class RenewedTimeDepositPostPostingHookTest(PostPostingHookCommonTest, TimeDepositTest):
    def setUp(self) -> None:
        super().setUp()
        self.mock_get_grace_period_parameter.return_value = 1

        patch_is_withdrawal_subject_to_fees = patch.object(
            time_deposit.grace_period, "is_withdrawal_subject_to_fees"
        )
        self.mock_is_withdrawal_subject_to_fees = patch_is_withdrawal_subject_to_fees.start()
        self.mock_is_withdrawal_subject_to_fees.return_value = False

        self.addCleanup(patch.stopall)

    def test_no_withdrawal_fees_charged_if_withdrawal_within_grace_period(self):
        expected_result = PostPostingHookResult(
            account_notification_directives=[
                SentinelAccountNotificationDirective("zero_fee_with_number_of_interest_days")
            ]
        )
        self.assertEqual(
            time_deposit.post_posting_hook(vault=self.mock_vault, hook_arguments=self.hook_args),
            expected_result,
        )
        self.mock_is_withdrawal_subject_to_fees.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=self.hook_args_posting_instructions,
            denomination=self.default_denom,
        )
        self.mock_handle_withdrawals.assert_not_called()
        self.mock_handle_withdrawal_fees_with_number_of_interest_days_fee.assert_not_called()
        self.mock_generate_withdrawal_fee_notification.assert_called_once_with(
            account_id=ACCOUNT_ID,
            denomination=self.default_denom,
            withdrawal_amount=Decimal("1"),
            flat_fee_amount=Decimal("0"),
            percentage_fee_amount=Decimal("0"),
            product_name=time_deposit.PRODUCT_NAME,
            client_batch_id="client_batch_id",
        )

    def test_withdrawal_fees_charged_if_withdrawal_outside_grace_period(self):
        self.mock_is_withdrawal_subject_to_fees.return_value = True

        expected_result = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[SentinelCustomInstruction("withdrawal_fees")],
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
            account_notification_directives=[
                SentinelAccountNotificationDirective("withdrawal_fees_inc_number_of_interest_days")
            ],
        )
        self.assertEqual(
            time_deposit.post_posting_hook(vault=self.mock_vault, hook_arguments=self.hook_args),
            expected_result,
        )
        self.mock_is_withdrawal_subject_to_fees.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=self.hook_args_posting_instructions,
            denomination=self.default_denom,
        )
        self.mock_handle_withdrawals.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=self.hook_args_posting_instructions,
            product_name=time_deposit.PRODUCT_NAME,
            denomination=self.default_denom,
            balances=sentinel.balances_live,
            balance_adjustments=time_deposit.TIME_DEPOSIT_DEFAULT_BALANCE_ADJUSTMENTS,
        )
        self.mock_handle_withdrawal_fees_with_number_of_interest_days_fee.assert_called_once_with(
            vault=self.mock_vault,
            withdrawal_fee_notification=SentinelAccountNotificationDirective("withdrawal_fees"),
            withdrawal_amount=Decimal("1"),
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.balances_live,
            denomination=self.default_denom,
        )
        self.mock_generate_withdrawal_fee_notification.assert_not_called()
        self.mock_update_notification_with_number_of_interest_days_fee.assert_not_called()


class NewTimeDepositPostPostingHookTest(PostPostingHookCommonTest, TimeDepositTest):
    def setUp(self) -> None:
        patch_is_withdrawal_subject_to_fees = patch.object(
            time_deposit.cooling_off_period, "is_withdrawal_subject_to_fees"
        )
        self.mock_is_withdrawal_subject_to_fees = patch_is_withdrawal_subject_to_fees.start()
        self.mock_is_withdrawal_subject_to_fees.return_value = False

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_no_withdrawal_fees_charged_if_full_withdrawal_within_cooling_off_period(self):
        expected_result = PostPostingHookResult(
            account_notification_directives=[
                SentinelAccountNotificationDirective("zero_fee_with_number_of_interest_days")
            ]
        )
        self.assertEqual(
            time_deposit.post_posting_hook(vault=self.mock_vault, hook_arguments=self.hook_args),
            expected_result,
        )
        self.mock_is_withdrawal_subject_to_fees.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=self.hook_args_posting_instructions,
            denomination=self.default_denom,
        )
        self.mock_handle_withdrawals.assert_not_called()
        self.mock_handle_withdrawal_fees_with_number_of_interest_days_fee.assert_not_called()
        self.mock_generate_withdrawal_fee_notification.assert_called_once_with(
            account_id=ACCOUNT_ID,
            denomination=self.default_denom,
            withdrawal_amount=Decimal("1"),
            flat_fee_amount=Decimal("0"),
            percentage_fee_amount=Decimal("0"),
            product_name=time_deposit.PRODUCT_NAME,
            client_batch_id="client_batch_id",
        )

    def test_withdrawal_fees_charged_if_full_withdrawal_outside_cooling_off_period(self):
        self.mock_is_withdrawal_subject_to_fees.return_value = True

        expected_result = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[SentinelCustomInstruction("withdrawal_fees")],
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
            account_notification_directives=[
                SentinelAccountNotificationDirective("withdrawal_fees_inc_number_of_interest_days")
            ],
        )
        self.assertEqual(
            time_deposit.post_posting_hook(vault=self.mock_vault, hook_arguments=self.hook_args),
            expected_result,
        )
        self.mock_is_withdrawal_subject_to_fees.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=self.hook_args_posting_instructions,
            denomination=self.default_denom,
        )
        self.mock_handle_withdrawals.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=self.hook_args_posting_instructions,
            product_name=time_deposit.PRODUCT_NAME,
            denomination=self.default_denom,
            balances=sentinel.balances_live,
            balance_adjustments=time_deposit.TIME_DEPOSIT_DEFAULT_BALANCE_ADJUSTMENTS,
        )
        self.mock_handle_withdrawal_fees_with_number_of_interest_days_fee.assert_called_once_with(
            vault=self.mock_vault,
            withdrawal_fee_notification=SentinelAccountNotificationDirective("withdrawal_fees"),
            withdrawal_amount=Decimal("1"),
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.balances_live,
            denomination=self.default_denom,
        )
        self.mock_generate_withdrawal_fee_notification.assert_not_called()
        self.mock_update_notification_with_number_of_interest_days_fee.assert_not_called()


class InterestForfeitureTest(TimeDepositTest):
    def setUp(self) -> None:
        self.withdrawal_amount = Decimal("100")
        self.mock_vault = MagicMock()
        type(self.mock_vault).account_id = PropertyMock(return_value=sentinel.account_id)
        patch_get_parameter = patch.object(time_deposit.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                time_deposit.common_parameters.PARAM_DENOMINATION: self.default_denom,
                time_deposit.fixed_interest_accrual.PARAM_ACCRUAL_PRECISION: 5,
                time_deposit.fixed_interest_accrual.PARAM_ACCRUED_INTEREST_PAYABLE_ACCOUNT: "payable_account_id",  # noqa: E501
            }
        )

        patch_balance_at_coordinates = patch.object(time_deposit.utils, "balance_at_coordinates")
        self.mock_balance_at_coordinates = patch_balance_at_coordinates.start()
        # accrued interest, default address
        self.mock_balance_at_coordinates.side_effect = [Decimal("0.11000"), Decimal("1000")]

        patch_round_decimal = patch.object(time_deposit.utils, "round_decimal")
        self.mock_round_decimal = patch_round_decimal.start()
        self.mock_round_decimal.return_value = Decimal("1")
        self.addCleanup(patch.stopall)

        patch_create_postings = patch.object(time_deposit.utils, "create_postings")
        self.mock_create_postings = patch_create_postings.start()
        self.mock_create_postings.return_value = DEFAULT_POSTINGS

        return super().setUp()

    def test_handle_partial_withdrawal_with_interest_forfeiture(self):
        expected_result = [
            CustomInstruction(postings=DEFAULT_POSTINGS, override_all_restrictions=True)
        ]
        result = time_deposit._handle_partial_interest_forfeiture(
            vault=self.mock_vault,
            effective_datetime=sentinel.effective_datetime,
            balances=sentinel.balances,
            withdrawal_amount=self.withdrawal_amount,
        )
        self.assertListEqual(result, expected_result)

        self.mock_create_postings.assert_called_once_with(
            amount=Decimal("1"),
            debit_account=sentinel.account_id,
            credit_account="payable_account_id",
            debit_address=time_deposit.fixed_interest_accrual.ACCRUED_INTEREST_PAYABLE,
            credit_address=DEFAULT_ADDRESS,
            denomination=self.default_denom,
        )
        self.mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.balances,
                    denomination=self.default_denom,
                    address=time_deposit.fixed_interest_accrual.ACCRUED_INTEREST_PAYABLE,
                ),
                call(
                    balances=sentinel.balances,
                    denomination=self.default_denom,
                    address=DEFAULT_ADDRESS,
                ),
            ]
        )
        self.mock_round_decimal.assert_called_once_with(amount=Decimal("0.01"), decimal_places=5)

    def test_handle_partial_withdrawal_no_interest_accrued(self):
        self.mock_round_decimal.return_value = Decimal("0")
        result = time_deposit._handle_partial_interest_forfeiture(
            vault=self.mock_vault,
            effective_datetime=sentinel.effective_datetime,
            balances=sentinel.balances,
            withdrawal_amount=self.withdrawal_amount,
        )
        self.assertListEqual(result, [])

        self.mock_create_postings.assert_not_called()
        self.mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.balances,
                    denomination=self.default_denom,
                    address=time_deposit.fixed_interest_accrual.ACCRUED_INTEREST_PAYABLE,
                ),
                call(
                    balances=sentinel.balances,
                    denomination=self.default_denom,
                    address=DEFAULT_ADDRESS,
                ),
            ]
        )
        self.mock_round_decimal.assert_called_once_with(amount=Decimal("0.01"), decimal_places=5)


class HandleFullWithdrawalNotificationTest(TimeDepositTest):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = self.create_mock(account_id="vault_account_id")

        self.expected_notification_directive = AccountNotificationDirective(
            notification_type=time_deposit.FULL_WITHDRAWAL_NOTIFICATION,
            notification_details={
                "account_id": "vault_account_id",
                "reason": "The account balance has been fully withdrawn.",
            },
        )

        # get_available_balance
        patch_get_available_balance = patch.object(time_deposit.utils, "get_available_balance")
        self.mock_get_available_balance = patch_get_available_balance.start()
        self.mock_get_available_balance.return_value = Decimal("0")

        # get_grace_period_parameter
        patch_get_grace_period_parameter = patch.object(
            time_deposit.grace_period, "get_grace_period_parameter"
        )
        self.mock_get_grace_period_parameter = patch_get_grace_period_parameter.start()

        # is_within_grace_period
        patch_is_within_grace_period = patch.object(
            time_deposit.grace_period, "is_within_grace_period"
        )
        self.mock_is_within_grace_period = patch_is_within_grace_period.start()
        self.mock_is_within_grace_period.return_value = False

        # is_within_deposit_period
        patch_is_within_deposit_period = patch.object(
            time_deposit.deposit_period, "is_within_deposit_period"
        )
        self.mock_is_within_deposit_period = patch_is_within_deposit_period.start()
        self.mock_is_within_deposit_period.return_value = False

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_partial_withdrawal_returns_empty_list(self):
        self.mock_get_available_balance.return_value = Decimal("10")

        result = time_deposit._handle_full_withdrawal_notification(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.balances,
            denomination=self.default_denomination,
        )
        self.assertListEqual(result, [])

        self.mock_get_grace_period_parameter.assert_not_called()

    def test_renewed_td_within_grace_period_returns_empty_list(self):
        self.mock_get_grace_period_parameter.return_value = 1  # renewed TD
        self.mock_is_within_grace_period.return_value = True

        result = time_deposit._handle_full_withdrawal_notification(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.balances,
            denomination=self.default_denomination,
        )
        self.assertListEqual(result, [])

    def test_new_td_within_deposit_period_returns_empty_list(self):
        self.mock_get_grace_period_parameter.return_value = 0  # new TD
        self.mock_is_within_deposit_period.return_value = True

        result = time_deposit._handle_full_withdrawal_notification(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.balances,
            denomination=self.default_denomination,
        )
        self.assertListEqual(result, [])

    def test_renewed_td_outside_grace_period_returns_notification(self):
        self.mock_get_grace_period_parameter.return_value = 1  # renewed TD

        result = time_deposit._handle_full_withdrawal_notification(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.balances,
            denomination=self.default_denomination,
        )
        self.assertListEqual(result, [self.expected_notification_directive])

    def test_new_td_outside_deposit_period_returns_notification(self):
        self.mock_get_grace_period_parameter.return_value = 0  # new TD

        result = time_deposit._handle_full_withdrawal_notification(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.balances,
            denomination=self.default_denomination,
        )
        self.assertListEqual(result, [self.expected_notification_directive])
