# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# library
import library.time_deposit.contracts.template.time_deposit as time_deposit
from library.time_deposit.test.unit.test_time_deposit_common import TimeDepositTest

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import BalanceDefaultDict

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DEFAULT_ASSET,
    AccountNotificationDirective,
    CustomInstruction,
    Phase,
    Posting,
    Rejection,
    RejectionReason,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    DEFAULT_POSTINGS,
    SentinelAccountNotificationDirective,
    SentinelBalancesObservation,
    SentinelPosting,
)


class UpdateTrackedInterestTest(TimeDepositTest):
    def setUp(self) -> None:
        patch_get_current_net_balance = patch.object(time_deposit.utils, "get_current_net_balance")
        self.mock_get_current_net_balance = patch_get_current_net_balance.start()
        self.mock_get_current_net_balance.return_value = Decimal("1")

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_update_tracked_applied_interest_no_application_instructions(self):
        application_instructions = []
        tracker_instructions = time_deposit._update_tracked_applied_interest(
            application_custom_instructions=application_instructions,
            account_id=sentinel.account_id,
            denomination=self.default_denom,
        )
        self.assertListEqual([], tracker_instructions)

    def test_update_tracked_applied_interest_positive_accrued(self):
        application_instructions = [CustomInstruction(postings=DEFAULT_POSTINGS)]
        tracker_instructions = time_deposit._update_tracked_applied_interest(
            application_custom_instructions=application_instructions,
            account_id=sentinel.account_id,
            denomination=self.default_denom,
        )

        expected_postings = [
            Posting(
                denomination=self.default_denom,
                account_id=sentinel.account_id,
                account_address=time_deposit.APPLIED_INTEREST_TRACKER,
                asset=DEFAULT_ASSET,
                credit=True,
                amount=Decimal("1"),
                phase=Phase.COMMITTED,
            ),
            Posting(
                denomination=self.default_denom,
                account_id=sentinel.account_id,
                account_address=time_deposit.common_addresses.INTERNAL_CONTRA,
                asset=DEFAULT_ASSET,
                credit=False,
                amount=Decimal("1"),
                phase=Phase.COMMITTED,
            ),
        ]

        expected_posting_instructions = [
            CustomInstruction(
                postings=expected_postings,
                instruction_details={
                    "description": "Updating the applied interest tracker balance"
                },
                override_all_restrictions=True,
            )
        ]

        self.assertListEqual(expected_posting_instructions, tracker_instructions)


class ResetTrackedInterestTest(TimeDepositTest):
    def setUp(self) -> None:
        patch_balance_at_coordinates = patch.object(time_deposit.utils, "balance_at_coordinates")
        self.mock_balance_at_coordinates = patch_balance_at_coordinates.start()

        patch_create_postings = patch.object(time_deposit.utils, "create_postings")
        self.mock_create_postings = patch_create_postings.start()
        self.mock_create_postings.return_value = [SentinelPosting("reset_applied_interest")]

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_reset_applied_interest_tracker_with_positive_interest(self):
        self.mock_balance_at_coordinates.return_value = Decimal("1")
        expected_result = [
            CustomInstruction(
                postings=[SentinelPosting("reset_applied_interest")],
                instruction_details={"description": "Resetting the applied interest tracker"},
                override_all_restrictions=True,
            )
        ]

        result = time_deposit._reset_applied_interest_tracker(
            balances=sentinel.balances_effective_date,
            account_id=sentinel.account_id,
            denomination=sentinel.denomination,
        )

        self.assertListEqual(result, expected_result)

        self.mock_create_postings.assert_called_once_with(
            amount=Decimal("1"),
            debit_account=sentinel.account_id,
            credit_account=sentinel.account_id,
            debit_address=time_deposit.APPLIED_INTEREST_TRACKER,
            credit_address=time_deposit.common_addresses.INTERNAL_CONTRA,
            denomination=sentinel.denomination,
        )

    def test_reset_applied_interest_tracker_no_postings(self):
        self.mock_balance_at_coordinates.return_value = Decimal("0")

        result = time_deposit._reset_applied_interest_tracker(
            balances=sentinel.balances,
            account_id=sentinel.account_id,
            denomination=sentinel.denomination,
        )

        self.assertListEqual(result, [])
        self.mock_create_postings.assert_not_called()


class AppliedInterestBalanceAdjustmentTest(TimeDepositTest):
    def setUp(self) -> None:
        patch_balance_at_coordinates = patch.object(time_deposit.utils, "balance_at_coordinates")
        self.mock_balance_at_coordinates = patch_balance_at_coordinates.start()
        self.mock_balance_at_coordinates.return_value = Decimal("100")

        self.addCleanup(patch.stopall)
        return super().setUp()

    @patch.object(time_deposit.common_parameters, "get_denomination_parameter")
    def test_calculate_applied_interest_balance_adjustment(
        self, mock_get_denomination_parameter: MagicMock
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                time_deposit.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live"),
            },
        )
        mock_get_denomination_parameter.return_value = sentinel.fetched_denomination

        result = time_deposit._calculate_applied_interest_balance_adjustment(vault=mock_vault)
        self.assertEqual(result, Decimal("-100"))
        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances_live,
            address=time_deposit.APPLIED_INTEREST_TRACKER,
            denomination=sentinel.fetched_denomination,
        )

    def test_calculate_applied_interest_balance_adjustment_with_optional_args(self):
        balances = BalanceDefaultDict(
            mapping={
                self.balance_coordinate(
                    account_address=time_deposit.APPLIED_INTEREST_TRACKER,
                    denomination=self.default_denomination,
                ): self.balance(credit=Decimal("100"), debit=Decimal("0"))
            }
        )
        result = time_deposit._calculate_applied_interest_balance_adjustment(
            vault=sentinel.vault, balances=balances, denomination=self.default_denomination
        )
        self.assertEqual(result, Decimal("-100"))
        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=balances,
            address=time_deposit.APPLIED_INTEREST_TRACKER,
            denomination=self.default_denomination,
        )


class NumberOfInterestDaysFeeHelpersTest(TimeDepositTest):
    @patch.object(time_deposit, "_update_notification_with_number_of_interest_days_fee")
    @patch.object(
        time_deposit.withdrawal_fees, "get_current_withdrawal_amount_default_balance_adjustment"
    )
    @patch.object(time_deposit, "_calculate_number_of_interest_days_fee")
    def test_handle_withdrawal_fees_with_number_of_interest_days_fee(
        self,
        mock_calculate_number_of_interest_days_fee: MagicMock,
        mock_get_current_withdrawal_amount_default_balance_adjustment: MagicMock,
        mock_update_notification_with_number_of_interest_days_fee: MagicMock,
    ):
        mock_calculate_number_of_interest_days_fee.return_value = Decimal("1")
        mock_get_current_withdrawal_amount_default_balance_adjustment.return_value = (
            sentinel.current_withdrawal_amount_adjustment
        )
        mock_update_notification_with_number_of_interest_days_fee.return_value = (
            SentinelAccountNotificationDirective("withdrawal_fees_with_number_of_interest_days")
        )

        result = time_deposit._handle_withdrawal_fees_with_number_of_interest_days_fee(
            vault=sentinel.vault,
            withdrawal_fee_notification=sentinel.withdrawal_fee_notification,
            withdrawal_amount=sentinel.withdrawal_amount,
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

        self.assertEqual(
            result,
            [SentinelAccountNotificationDirective("withdrawal_fees_with_number_of_interest_days")],
        )

        mock_calculate_number_of_interest_days_fee.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=sentinel.denomination,
            balances=sentinel.balances,
            balance_adjustments=[
                *time_deposit.TIME_DEPOSIT_DEFAULT_BALANCE_ADJUSTMENTS,
                sentinel.current_withdrawal_amount_adjustment,
            ],
        )
        mock_get_current_withdrawal_amount_default_balance_adjustment.assert_called_once_with(
            withdrawal_amount=sentinel.withdrawal_amount
        )
        mock_update_notification_with_number_of_interest_days_fee.assert_called_once_with(
            withdrawal_fee_notification=sentinel.withdrawal_fee_notification,
            number_of_interest_days_fee=Decimal("1"),
        )

    def test_update_notification_with_number_of_interest_days_fee_with_zero_fee(self):
        expected_result = AccountNotificationDirective(
            notification_type=time_deposit.WITHDRAWAL_FEES_NOTIFICATION,
            notification_details={
                "account_id": "account_id",
                "denomination": "GBP",
                "withdrawal_amount": "100",
                "flat_fee_amount": "10",
                "percentage_fee_amount": "0.05",
                "number_of_interest_days_fee": "0",
                "total_fee_amount": "10.05",
                "client_batch_id": "client_batch_id",
            },
        )

        result = time_deposit._update_notification_with_number_of_interest_days_fee(
            withdrawal_fee_notification=AccountNotificationDirective(
                notification_type=time_deposit.WITHDRAWAL_FEES_NOTIFICATION,
                notification_details={
                    "account_id": "account_id",
                    "denomination": "GBP",
                    "withdrawal_amount": "100",
                    "flat_fee_amount": "10",
                    "percentage_fee_amount": "0.05",
                    "total_fee_amount": "10.05",
                    "client_batch_id": "client_batch_id",
                },
            ),
            number_of_interest_days_fee=Decimal("0"),
        )

        self.assertEqual(result, expected_result)

    def test_update_notification_with_number_of_interest_days_fee_with_non_zero_fee(self):
        # ensure percentage_fee_amount is overridden
        expected_result = AccountNotificationDirective(
            notification_type=time_deposit.WITHDRAWAL_FEES_NOTIFICATION,
            notification_details={
                "account_id": "account_id",
                "denomination": "GBP",
                "withdrawal_amount": "100",
                "flat_fee_amount": "10",
                "percentage_fee_amount": "0",
                "number_of_interest_days_fee": "15",
                "total_fee_amount": "25",
                "client_batch_id": "client_batch_id",
            },
        )

        result = time_deposit._update_notification_with_number_of_interest_days_fee(
            withdrawal_fee_notification=AccountNotificationDirective(
                notification_type=time_deposit.WITHDRAWAL_FEES_NOTIFICATION,
                notification_details={
                    "account_id": "account_id",
                    "denomination": "GBP",
                    "withdrawal_amount": "100",
                    "flat_fee_amount": "10",
                    "percentage_fee_amount": "0.05",
                    "total_fee_amount": "10.05",
                    "client_batch_id": "client_batch_id",
                },
            ),
            number_of_interest_days_fee=Decimal("15"),
        )

        self.assertEqual(result, expected_result)


class CalculateNumberOfInterestDaysFeeTest(TimeDepositTest):
    def setUp(self) -> None:
        patch_get_parameter = patch.object(time_deposit.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()

        patch_get_daily_interest_rate = patch.object(
            time_deposit.fixed_interest_accrual, "get_daily_interest_rate"
        )
        self.mock_get_daily_interest_rate = patch_get_daily_interest_rate.start()
        self.mock_get_daily_interest_rate.return_value = Decimal("0.01")

        patch_get_customer_deposit_amount = patch.object(
            time_deposit.withdrawal_fees, "get_customer_deposit_amount"
        )
        self.mock_get_customer_deposit_amount = patch_get_customer_deposit_amount.start()
        self.mock_get_customer_deposit_amount.return_value = Decimal("200")

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_calculate_number_of_interest_days_fee_returns_zero_when_not_configured(self):
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={time_deposit.PARAM_NUMBER_OF_INTEREST_DAYS_EARLY_WITHDRAWAL_FEE: 0}
        )

        result = time_deposit._calculate_number_of_interest_days_fee(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=sentinel.denomination,
            balances=sentinel.balances,
            balance_adjustments=sentinel.balance_adjustments,
        )
        self.assertEqual(result, Decimal("0"))

    def test_calculate_number_of_interest_days_fee_returns_fee_amount(self):
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={time_deposit.PARAM_NUMBER_OF_INTEREST_DAYS_EARLY_WITHDRAWAL_FEE: 30}
        )

        result = time_deposit._calculate_number_of_interest_days_fee(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=sentinel.denomination,
            balances=sentinel.balances,
            balance_adjustments=sentinel.balance_adjustments,
        )
        self.assertEqual(result, Decimal("60.00"))


class ValidateWithdrawalsWithNumberOfInterestDaysFeeTest(TimeDepositTest):
    def setUp(self) -> None:
        # get_available_balance
        patch_get_available_balance = patch.object(time_deposit.utils, "get_available_balance")
        self.mock_get_available_balance = patch_get_available_balance.start()
        self.mock_get_available_balance.return_value = Decimal("-100")  # withdrawal amount

        # get_posting_instructions_balances
        patch_get_posting_instructions_balances = patch.object(
            time_deposit.utils, "get_posting_instructions_balances"
        )
        self.mock_get_posting_instructions_balances = (
            patch_get_posting_instructions_balances.start()
        )
        self.mock_get_posting_instructions_balances.return_value = sentinel.instruction_balances

        # _calculate_number_of_interest_days_fee
        patch__calculate_number_of_interest_days_fee = patch.object(
            time_deposit, "_calculate_number_of_interest_days_fee"
        )
        self.mock_calculate_number_of_interest_days_fee = (
            patch__calculate_number_of_interest_days_fee.start()
        )

        # calculate_withdrawal_fee_amounts
        patch_calculate_withdrawal_fee_amounts = patch.object(
            time_deposit.withdrawal_fees, "calculate_withdrawal_fee_amounts"
        )
        self.mock_calculate_withdrawal_fee_amounts = patch_calculate_withdrawal_fee_amounts.start()

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_deposit_returns_none(self):
        self.mock_get_available_balance.return_value = Decimal("100")
        result = time_deposit._validate_withdrawals_with_number_of_interest_days_fee(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.posting_instructions,
            denomination=self.default_denomination,
            balances=sentinel.balances,
            balance_adjustments=sentinel.balance_adjustments,
        )
        self.assertIsNone(result)

        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.instruction_balances, denomination=self.default_denomination
        )
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions
        )
        self.mock_calculate_number_of_interest_days_fee.assert_not_called()
        self.mock_calculate_withdrawal_fee_amounts.assert_not_called()

    def test_valid_withdrawal_returns_none(self):
        self.mock_calculate_number_of_interest_days_fee.return_value = Decimal("1")
        self.mock_calculate_withdrawal_fee_amounts.return_value = [Decimal("1"), Decimal("1")]
        result = time_deposit._validate_withdrawals_with_number_of_interest_days_fee(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.posting_instructions,
            denomination=self.default_denomination,
            balances=sentinel.balances,
            balance_adjustments=sentinel.balance_adjustments,
        )
        self.assertIsNone(result)

        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.instruction_balances, denomination=self.default_denomination
        )
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions
        )
        self.mock_calculate_number_of_interest_days_fee.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=self.default_denomination,
            balances=sentinel.balances,
            balance_adjustments=sentinel.balance_adjustments,
        )
        self.mock_calculate_withdrawal_fee_amounts.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            withdrawal_amount=Decimal("100"),
            denomination=self.default_denomination,
            balances=sentinel.balances,
            balance_adjustments=sentinel.balance_adjustments,
        )

    def test_zero_number_of_interest_days_fee_amount_returns_none(self):
        self.mock_calculate_number_of_interest_days_fee.return_value = Decimal("0")

        result = time_deposit._validate_withdrawals_with_number_of_interest_days_fee(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.posting_instructions,
            denomination=self.default_denomination,
            balances=sentinel.balances,
            balance_adjustments=sentinel.balance_adjustments,
        )
        self.assertIsNone(result)

        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.instruction_balances, denomination=self.default_denomination
        )
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions
        )
        self.mock_calculate_number_of_interest_days_fee.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=self.default_denomination,
            balances=sentinel.balances,
            balance_adjustments=sentinel.balance_adjustments,
        )
        self.mock_calculate_withdrawal_fee_amounts.assert_not_called()

    def test_withdrawal_fees_exceed_withdrawal_amount_raises_rejection_interest_days_fee(self):
        self.mock_calculate_number_of_interest_days_fee.return_value = Decimal("65")
        self.mock_calculate_withdrawal_fee_amounts.return_value = [Decimal("50"), Decimal("0")]

        expected_result = Rejection(
            message="The withdrawal fees of 115 GBP are not covered by "
            "the withdrawal amount of 100 GBP.",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )
        result = time_deposit._validate_withdrawals_with_number_of_interest_days_fee(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.posting_instructions,
            denomination=self.default_denomination,
            balances=sentinel.balances,
            balance_adjustments=sentinel.balance_adjustments,
        )
        self.assertEqual(result, expected_result)

        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.instruction_balances, denomination=self.default_denomination
        )
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions
        )
        self.mock_calculate_number_of_interest_days_fee.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=self.default_denomination,
            balances=sentinel.balances,
            balance_adjustments=sentinel.balance_adjustments,
        )
        self.mock_calculate_withdrawal_fee_amounts.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            withdrawal_amount=Decimal("100"),
            denomination=self.default_denomination,
            balances=sentinel.balances,
            balance_adjustments=sentinel.balance_adjustments,
        )
