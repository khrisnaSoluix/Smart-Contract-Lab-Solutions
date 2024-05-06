# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.

# standard libs
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.v4.deposit.fees.withdrawal.withdrawal_fees as withdrawal_fees
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    ACCOUNT_ID,
    DEFAULT_DATETIME,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    AccountNotificationDirective,
    CalendarEvent,
    CustomInstruction,
    Rejection,
    RejectionReason,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    DEFAULT_POSTINGS,
    SentinelBalancesObservation,
)

DEFAULT_CALENDAR_EVENT = CalendarEvent(
    id="TEST",
    calendar_id="PUBLIC_HOLIDAYS",
    start_datetime=datetime(2020, 9, 5, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
    end_datetime=datetime(2020, 9, 6, 23, 23, 59, tzinfo=ZoneInfo("UTC")),
)


class WithdrawalFeesNotificationTest(FeatureTest):
    product_name = "TEST_PRODUCT"

    def test_notification_type(self):
        result = withdrawal_fees.notification_type(product_name=self.product_name)

        self.assertEqual(result, "TEST_PRODUCT_WITHDRAWAL_FEE")

    def test_withdrawal_fee_notification(self):
        expected_result = AccountNotificationDirective(
            notification_type="TEST_PRODUCT_WITHDRAWAL_FEE",
            notification_details={
                "account_id": "vault_account_id",
                "denomination": "GBP",
                "withdrawal_amount": "20",
                "flat_fee_amount": "5",
                "percentage_fee_amount": "10",
                "total_fee_amount": "15",
                "client_batch_id": "withdrawal_client_batch_id",
            },
        )

        result = withdrawal_fees.generate_withdrawal_fee_notification(
            account_id="vault_account_id",
            denomination=self.default_denomination,
            withdrawal_amount=Decimal("20"),
            flat_fee_amount=Decimal("5"),
            percentage_fee_amount=Decimal("10"),
            product_name=self.product_name,
            client_batch_id="withdrawal_client_batch_id",
        )
        self.assertEqual(result, expected_result)


class ValidatePrePostingTest(FeatureTest):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                withdrawal_fees.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live")
            },
        )
        self.mock_vault_with_calendar = self.create_mock(
            balances_observation_fetchers_mapping={
                withdrawal_fees.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live")
            },
            calendar_events=[DEFAULT_CALENDAR_EVENT],
        )

        # get_parameter
        patch_get_parameter = patch.object(withdrawal_fees.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )

        # get_available_balance
        patch_get_available_balance = patch.object(withdrawal_fees.utils, "get_available_balance")
        self.mock_get_available_balance = patch_get_available_balance.start()
        self.mock_get_available_balance.return_value = Decimal("-100")  # withdrawal amount

        # get_posting_instructions_balances
        patch_get_posting_instructions_balances = patch.object(
            withdrawal_fees.utils, "get_posting_instructions_balances"
        )
        self.mock_get_posting_instructions_balances = (
            patch_get_posting_instructions_balances.start()
        )
        self.mock_get_posting_instructions_balances.return_value = sentinel.instruction_balances

        # get_current_credit_balance
        patch_get_current_net_balance = patch.object(
            withdrawal_fees.utils, "get_current_net_balance"
        )
        self.mock_get_current_net_balance = patch_get_current_net_balance.start()
        self.mock_get_current_net_balance.return_value = Decimal("150")

        # _calculate_maximum_withdrawal_limit
        patch_calculate_maximum_withdrawal_limit = patch.object(
            withdrawal_fees, "_calculate_maximum_withdrawal_limit"
        )
        self.mock_calculate_maximum_withdrawal_limit = (
            patch_calculate_maximum_withdrawal_limit.start()
        )
        self.mock_calculate_maximum_withdrawal_limit.return_value = Decimal("110")

        # balance_at_coordinates
        patch_balance_at_coordinates = patch.object(withdrawal_fees.utils, "balance_at_coordinates")
        self.mock_balance_at_coordinates = patch_balance_at_coordinates.start()
        self.mock_balance_at_coordinates.return_value = Decimal("0")  # withdrawals tracker

        # is_key_in_instruction_details
        patch_is_key_in_instruction_details = patch.object(
            withdrawal_fees.utils, "is_key_in_instruction_details"
        )
        self.mock_is_key_in_instruction_details = patch_is_key_in_instruction_details.start()
        self.mock_is_key_in_instruction_details.return_value = True

        # falls_on_calendar_events
        patch_falls_on_calendar_events = patch.object(
            withdrawal_fees.utils, "falls_on_calendar_events"
        )
        self.mock_falls_on_calendar_events = patch_falls_on_calendar_events.start()
        self.mock_falls_on_calendar_events.return_value = False

        # _calculate_withdrawal_fee_amounts
        patch_calculate_withdrawal_fee_amounts = patch.object(
            withdrawal_fees, "calculate_withdrawal_fee_amounts"
        )
        self.mock_calculate_withdrawal_fee_amounts = patch_calculate_withdrawal_fee_amounts.start()
        self.mock_calculate_withdrawal_fee_amounts.return_value = Decimal("5"), Decimal("15")

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_valid_withdrawal_does_not_raise_rejection(self):
        result = withdrawal_fees.validate(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.posting_instructions,
        )
        self.assertIsNone(result)

        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.instruction_balances, denomination=self.default_denomination
        )
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions
        )
        self.mock_get_current_net_balance.assert_called_once_with(
            balances=sentinel.balances_live, denomination=self.default_denomination
        )
        self.mock_calculate_maximum_withdrawal_limit.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=self.default_denomination,
            balances=sentinel.balances_live,
            balance_adjustments=None,
        )
        self.mock_is_key_in_instruction_details.assert_called_once_with(
            key="calendar_override",
            posting_instructions=sentinel.posting_instructions,
        )
        self.mock_falls_on_calendar_events.assert_called_once_with(
            effective_datetime=DEFAULT_DATETIME, calendar_events=[]
        )
        self.mock_calculate_withdrawal_fee_amounts.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            withdrawal_amount=Decimal("100"),
            denomination=self.default_denomination,
            balances=sentinel.balances_live,
            balance_adjustments=None,
        )

    def test_valid_withdrawal_does_not_raise_rejection_with_optional_parameters(self):
        result = withdrawal_fees.validate(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.posting_instructions,
            denomination=sentinel.provided_denomination,
            balances=sentinel.provided_balances,
            balance_adjustments=[sentinel.balance_adjustment],
        )
        self.assertIsNone(result)

        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.instruction_balances, denomination=sentinel.provided_denomination
        )
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions
        )
        self.mock_get_current_net_balance.assert_called_once_with(
            balances=sentinel.provided_balances, denomination=sentinel.provided_denomination
        )
        self.mock_calculate_maximum_withdrawal_limit.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=sentinel.provided_denomination,
            balances=sentinel.provided_balances,
            balance_adjustments=[sentinel.balance_adjustment],
        )
        self.mock_is_key_in_instruction_details.assert_called_once_with(
            key="calendar_override",
            posting_instructions=sentinel.posting_instructions,
        )
        self.mock_falls_on_calendar_events.assert_called_once_with(
            effective_datetime=DEFAULT_DATETIME, calendar_events=[]
        )
        self.mock_calculate_withdrawal_fee_amounts.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            withdrawal_amount=Decimal("100"),
            denomination=sentinel.provided_denomination,
            balances=sentinel.provided_balances,
            balance_adjustments=[sentinel.balance_adjustment],
        )

    def test_withdrawal_exceeds_current_balance_raises_rejection(self):
        self.mock_get_current_net_balance.return_value = Decimal("90")
        expected_result = Rejection(
            message="The withdrawal amount of 100 GBP exceeds the available balance of 90 GBP.",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )

        result = withdrawal_fees.validate(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.posting_instructions,
        )
        self.assertEqual(result, expected_result)

        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.instruction_balances, denomination=self.default_denomination
        )
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions
        )
        self.mock_get_current_net_balance.assert_called_once_with(
            balances=sentinel.balances_live, denomination=self.default_denomination
        )
        self.mock_calculate_maximum_withdrawal_limit.assert_not_called()
        self.mock_is_key_in_instruction_details.assert_not_called()
        self.mock_falls_on_calendar_events.assert_not_called()
        self.mock_calculate_withdrawal_fee_amounts.assert_not_called()

    def test_partial_withdrawal_exceeds_maximum_withdrawal_limit_raises_rejection(self):
        self.mock_get_available_balance.return_value = Decimal("-70")  # withdrawal amount
        self.mock_balance_at_coordinates.return_value = Decimal("25")  # withdrawals tracker
        self.mock_calculate_maximum_withdrawal_limit.return_value = Decimal("90")

        expected_result = Rejection(
            message="The withdrawal amount of 70 GBP would exceed "
            "the available withdrawal limit of 65 GBP.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        result = withdrawal_fees.validate(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.posting_instructions,
        )
        self.assertEqual(result, expected_result)

        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.instruction_balances, denomination=self.default_denomination
        )
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions
        )
        self.mock_get_current_net_balance.assert_called_once_with(
            balances=sentinel.balances_live, denomination=self.default_denomination
        )
        self.mock_calculate_maximum_withdrawal_limit.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=self.default_denomination,
            balances=sentinel.balances_live,
            balance_adjustments=None,
        )
        self.mock_is_key_in_instruction_details.assert_not_called()
        self.mock_falls_on_calendar_events.assert_not_called()
        self.mock_calculate_withdrawal_fee_amounts.assert_not_called()

    def test_withdrawal_on_calendar_event_raises_rejection(self):
        self.mock_is_key_in_instruction_details.return_value = False
        self.mock_falls_on_calendar_events.return_value = True

        expected_result = Rejection(
            message="Cannot withdraw on public holidays.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        result = withdrawal_fees.validate(
            vault=self.mock_vault_with_calendar,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.posting_instructions,
        )
        self.assertEqual(result, expected_result)

        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.instruction_balances, denomination=self.default_denomination
        )
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions
        )
        self.mock_get_current_net_balance.assert_called_once_with(
            balances=sentinel.balances_live, denomination=self.default_denomination
        )
        self.mock_calculate_maximum_withdrawal_limit.assert_called_once_with(
            vault=self.mock_vault_with_calendar,
            effective_datetime=DEFAULT_DATETIME,
            denomination=self.default_denomination,
            balances=sentinel.balances_live,
            balance_adjustments=None,
        )
        self.mock_is_key_in_instruction_details.assert_called_once_with(
            key="calendar_override",
            posting_instructions=sentinel.posting_instructions,
        )
        self.mock_falls_on_calendar_events.assert_called_once_with(
            effective_datetime=DEFAULT_DATETIME, calendar_events=[DEFAULT_CALENDAR_EVENT]
        )
        self.mock_calculate_withdrawal_fee_amounts.assert_not_called()

    def test_withdrawal_on_calendar_event_with_override_does_not_raise_rejection(self):
        self.mock_is_key_in_instruction_details.return_value = True

        result = withdrawal_fees.validate(
            vault=self.mock_vault_with_calendar,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.posting_instructions,
        )
        self.assertIsNone(result)

        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.instruction_balances, denomination=self.default_denomination
        )
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions
        )
        self.mock_get_current_net_balance.assert_called_once_with(
            balances=sentinel.balances_live, denomination=self.default_denomination
        )
        self.mock_calculate_maximum_withdrawal_limit.assert_called_once_with(
            vault=self.mock_vault_with_calendar,
            effective_datetime=DEFAULT_DATETIME,
            denomination=self.default_denomination,
            balances=sentinel.balances_live,
            balance_adjustments=None,
        )
        self.mock_is_key_in_instruction_details.assert_called_once_with(
            key="calendar_override",
            posting_instructions=sentinel.posting_instructions,
        )
        self.mock_falls_on_calendar_events.assert_called_once_with(
            effective_datetime=DEFAULT_DATETIME, calendar_events=[DEFAULT_CALENDAR_EVENT]
        )
        self.mock_calculate_withdrawal_fee_amounts.assert_called_once_with(
            vault=self.mock_vault_with_calendar,
            effective_datetime=DEFAULT_DATETIME,
            withdrawal_amount=Decimal("100"),
            denomination=self.default_denomination,
            balances=sentinel.balances_live,
            balance_adjustments=None,
        )

    def test_withdrawal_fees_exceed_withdrawal_amount_raises_rejection(self):
        self.mock_calculate_withdrawal_fee_amounts.return_value = Decimal("50"), Decimal("55")
        expected_result = Rejection(
            message="The withdrawal fees of 105 GBP are not covered by "
            "the withdrawal amount of 100 GBP.",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )

        result = withdrawal_fees.validate(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.posting_instructions,
        )
        self.assertEqual(result, expected_result)

        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.instruction_balances, denomination=self.default_denomination
        )
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions
        )
        self.mock_get_current_net_balance.assert_called_once_with(
            balances=sentinel.balances_live, denomination=self.default_denomination
        )
        self.mock_calculate_maximum_withdrawal_limit.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=self.default_denomination,
            balances=sentinel.balances_live,
            balance_adjustments=None,
        )
        self.mock_is_key_in_instruction_details.assert_called_once_with(
            key="calendar_override",
            posting_instructions=sentinel.posting_instructions,
        )
        self.mock_falls_on_calendar_events.assert_called_once_with(
            effective_datetime=DEFAULT_DATETIME, calendar_events=[]
        )
        self.mock_calculate_withdrawal_fee_amounts.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            withdrawal_amount=Decimal("100"),
            denomination=self.default_denomination,
            balances=sentinel.balances_live,
            balance_adjustments=None,
        )

    def test_deposit_does_not_raise_rejection(self):
        self.mock_get_available_balance.return_value = Decimal("100")

        result = withdrawal_fees.validate(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.posting_instructions,
        )
        self.assertIsNone(result)

        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.instruction_balances, denomination=self.default_denomination
        )
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions
        )
        self.mock_get_current_net_balance.assert_not_called()
        self.mock_calculate_maximum_withdrawal_limit.assert_not_called()
        self.mock_calculate_withdrawal_fee_amounts.assert_not_called()


class HandleWithdrawalsTest(FeatureTest):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                withdrawal_fees.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live")
            },
        )

        self.posting_instructions = [
            self.outbound_hard_settlement(
                amount=Decimal("100"), client_batch_id="withdrawal_client_batch_id"
            )
        ]

        # get_parameter
        patch_get_parameter = patch.object(withdrawal_fees.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )

        # get_available_balance
        patch_get_available_balance = patch.object(withdrawal_fees.utils, "get_available_balance")
        self.mock_get_available_balance = patch_get_available_balance.start()
        self.mock_get_available_balance.return_value = Decimal("-100")  # withdrawal amount

        # get_posting_instructions_balances
        patch_get_posting_instructions_balances = patch.object(
            withdrawal_fees.utils, "get_posting_instructions_balances"
        )
        self.mock_get_posting_instructions_balances = (
            patch_get_posting_instructions_balances.start()
        )
        self.mock_get_posting_instructions_balances.return_value = sentinel.instruction_balances

        # _update_tracked_withdrawals
        patch_update_tracked_withdrawals = patch.object(
            withdrawal_fees, "_update_tracked_withdrawals"
        )
        self.mock_update_tracked_withdrawals = patch_update_tracked_withdrawals.start()
        self.mock_update_tracked_withdrawals.return_value = [sentinel.withdrawal_tracker]

        # get_current_withdrawal_amount_default_balance_adjustment
        patch_get_current_withdrawal_amount_default_balance_adjustment = patch.object(
            withdrawal_fees, "get_current_withdrawal_amount_default_balance_adjustment"
        )
        self.mock_get_current_withdrawal_amount_default_balance_adjustment = (
            patch_get_current_withdrawal_amount_default_balance_adjustment.start()
        )
        self.mock_get_current_withdrawal_amount_default_balance_adjustment.return_value = (
            sentinel.current_withdrawal_amount_adjustment
        )

        # _calculate_withdrawal_fee_amounts
        patch_calculate_withdrawal_fee_amounts = patch.object(
            withdrawal_fees, "calculate_withdrawal_fee_amounts"
        )
        self.mock_calculate_withdrawal_fee_amounts = patch_calculate_withdrawal_fee_amounts.start()
        self.mock_calculate_withdrawal_fee_amounts.return_value = Decimal("5"), Decimal("10")

        # generate_withdrawal_fee_notification
        patch_generate_withdrawal_fee_notification = patch.object(
            withdrawal_fees, "generate_withdrawal_fee_notification"
        )
        self.mock_generate_withdrawal_fee_notification = (
            patch_generate_withdrawal_fee_notification.start()
        )
        self.mock_generate_withdrawal_fee_notification.return_value = sentinel.notification

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_tracker_and_notification_returned(self):
        expected_result = [sentinel.withdrawal_tracker], [sentinel.notification]

        result = withdrawal_fees.handle_withdrawals(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=self.posting_instructions,
            product_name="TEST_PRODUCT",
        )
        self.assertTupleEqual(result, expected_result)

        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.instruction_balances, denomination=self.default_denomination
        )
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=self.posting_instructions
        )
        self.mock_update_tracked_withdrawals.assert_called_once_with(
            account_id=ACCOUNT_ID,
            withdrawal_amount=Decimal("100"),
            denomination=self.default_denomination,
        )
        self.mock_calculate_withdrawal_fee_amounts.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            withdrawal_amount=Decimal("100"),
            denomination=self.default_denomination,
            balances=sentinel.balances_live,
            balance_adjustments=[sentinel.current_withdrawal_amount_adjustment],
        )
        self.mock_generate_withdrawal_fee_notification.assert_called_once_with(
            account_id=ACCOUNT_ID,
            denomination=self.default_denomination,
            withdrawal_amount=Decimal("100"),
            flat_fee_amount=Decimal("5"),
            percentage_fee_amount=Decimal("10"),
            product_name="TEST_PRODUCT",
            client_batch_id="withdrawal_client_batch_id",
        )

    def test_tracker_and_notification_returned_with_optional_parameters(self):
        expected_result = [sentinel.withdrawal_tracker], [sentinel.notification]

        result = withdrawal_fees.handle_withdrawals(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=self.posting_instructions,
            product_name="TEST_PRODUCT",
            denomination=sentinel.provided_denomination,
            balances=sentinel.provided_balances,
            balance_adjustments=[sentinel.balance_adjustment],
        )
        self.assertTupleEqual(result, expected_result)

        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.instruction_balances, denomination=sentinel.provided_denomination
        )
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=self.posting_instructions
        )
        self.mock_update_tracked_withdrawals.assert_called_once_with(
            account_id=ACCOUNT_ID,
            withdrawal_amount=Decimal("100"),
            denomination=sentinel.provided_denomination,
        )
        self.mock_calculate_withdrawal_fee_amounts.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            withdrawal_amount=Decimal("100"),
            denomination=sentinel.provided_denomination,
            balances=sentinel.provided_balances,
            balance_adjustments=[
                sentinel.balance_adjustment,
                sentinel.current_withdrawal_amount_adjustment,
            ],
        )
        self.mock_generate_withdrawal_fee_notification.assert_called_once_with(
            account_id=ACCOUNT_ID,
            denomination=sentinel.provided_denomination,
            withdrawal_amount=Decimal("100"),
            flat_fee_amount=Decimal("5"),
            percentage_fee_amount=Decimal("10"),
            product_name="TEST_PRODUCT",
            client_batch_id="withdrawal_client_batch_id",
        )

    def test_deposit_returns_blank_list(self):
        self.mock_get_available_balance.return_value = Decimal("100")  # deposit amount
        expected_result = [], []
        result = withdrawal_fees.handle_withdrawals(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.posting_instructions,
            product_name="TEST_PRODUCT",
            denomination=sentinel.provided_denomination,
            balances=sentinel.provided_balances,
            balance_adjustments=[sentinel.balance_adjustment],
        )
        self.assertTupleEqual(result, expected_result)

        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.instruction_balances, denomination=sentinel.provided_denomination
        )
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions
        )
        self.mock_update_tracked_withdrawals.assert_not_called()
        self.mock_generate_withdrawal_fee_notification.assert_not_called()


class GetCurrentWithdrawalAmountDefaultBalanceAdjustmentTest(FeatureTest):
    def test_get_current_withdrawal_amount_default_balance_adjustment_returns_interface(self):
        result = withdrawal_fees.get_current_withdrawal_amount_default_balance_adjustment(
            withdrawal_amount=Decimal("100")
        )
        self.assertEqual(result.calculate_balance_adjustment(), Decimal("100"))


class GetCustomerDepositAmountTest(FeatureTest):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = sentinel.vault

        # balance_at_coordinates
        patch_balance_at_coordinates = patch.object(withdrawal_fees.utils, "balance_at_coordinates")
        self.mock_balance_at_coordinates = patch_balance_at_coordinates.start()
        self.mock_balance_at_coordinates.side_effect = [
            Decimal("400"),  # default_balance
            Decimal("100"),  # withdrawals_tracker_balance
        ]

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_get_customer_deposit_amount_without_balance_adjustments(self):
        result = withdrawal_fees.get_customer_deposit_amount(
            vault=self.mock_vault,
            balances=sentinel.balances,
            denomination=self.default_denomination,
        )
        # deposit_amount = 400 + 100 + 0 (no balance adjustments)
        self.assertEqual(result, Decimal("500"))

        self.mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.balances,
                    denomination=self.default_denomination,
                ),
                call(
                    balances=sentinel.balances,
                    address=withdrawal_fees.EARLY_WITHDRAWALS_TRACKER,
                    denomination=self.default_denomination,
                ),
            ]
        )

    def test_get_customer_deposit_amount_with_balance_adjustments(self):
        positive_balance_adjustment = withdrawal_fees.deposit_interfaces.DefaultBalanceAdjustment(
            calculate_balance_adjustment=lambda **kwargs: Decimal("10")
        )
        negative_balance_adjustment = withdrawal_fees.deposit_interfaces.DefaultBalanceAdjustment(
            calculate_balance_adjustment=lambda **kwargs: Decimal("-35")
        )
        result = withdrawal_fees.get_customer_deposit_amount(
            vault=self.mock_vault,
            balances=sentinel.balances,
            denomination=self.default_denomination,
            balance_adjustments=[positive_balance_adjustment, negative_balance_adjustment],
        )
        # deposit_amount = 400 + 100 + 10 - 35
        self.assertEqual(result, Decimal("475"))

        self.mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.balances,
                    denomination=self.default_denomination,
                ),
                call(
                    balances=sentinel.balances,
                    address=withdrawal_fees.EARLY_WITHDRAWALS_TRACKER,
                    denomination=self.default_denomination,
                ),
            ]
        )

    def test_get_customer_deposit_amount_with_balance_adjustments_with_optional_parameters(self):
        balance_adjustment = withdrawal_fees.deposit_interfaces.DefaultBalanceAdjustment(
            calculate_balance_adjustment=lambda **kwargs: Decimal("10")
        )
        result = withdrawal_fees.get_customer_deposit_amount(
            vault=self.mock_vault,
            balances=sentinel.provided_balances,
            denomination=sentinel.provided_denomination,
            balance_adjustments=[balance_adjustment],
        )
        # deposit_amount = 400 + 100 + 10
        self.assertEqual(result, Decimal("510"))

        self.mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.provided_balances,
                    denomination=sentinel.provided_denomination,
                ),
                call(
                    balances=sentinel.provided_balances,
                    address=withdrawal_fees.EARLY_WITHDRAWALS_TRACKER,
                    denomination=sentinel.provided_denomination,
                ),
            ]
        )


class UpdateWithdrawalsTrackerTest(FeatureTest):
    def setUp(self) -> None:
        # mock vault
        self.account_id = ACCOUNT_ID

        # create_postings
        mock_create_postings = patch.object(withdrawal_fees.utils, "create_postings")
        self.mock_create_postings = mock_create_postings.start()
        self.mock_create_postings.return_value = DEFAULT_POSTINGS

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_update_tracked_withdrawals_returns_custom_instruction_for_withdrawal(self):
        expected_result = [
            CustomInstruction(
                postings=DEFAULT_POSTINGS,
                instruction_details={"description": "Updating the withdrawals tracker balance"},
                override_all_restrictions=True,
            )
        ]

        result = withdrawal_fees._update_tracked_withdrawals(
            account_id=self.account_id,
            withdrawal_amount=Decimal("100"),
            denomination=sentinel.denomination,
        )
        self.assertListEqual(result, expected_result)

        self.mock_create_postings.assert_called_once_with(
            amount=Decimal("100"),
            debit_account=ACCOUNT_ID,
            credit_account=ACCOUNT_ID,
            debit_address=withdrawal_fees.common_addresses.INTERNAL_CONTRA,
            credit_address=withdrawal_fees.EARLY_WITHDRAWALS_TRACKER,
            denomination=sentinel.denomination,
        )

    def test_update_tracked_withdrawals_returns_blank_list_for_zero_withdrawal_amount(self):
        result = withdrawal_fees._update_tracked_withdrawals(
            account_id=self.account_id,
            withdrawal_amount=Decimal("0"),
            denomination=sentinel.denomination,
        )
        self.assertListEqual(result, [])

        self.mock_create_postings.assert_not_called()


class ResetWithdrawalsTrackerTest(FeatureTest):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                withdrawal_fees.EARLY_WITHDRAWALS_TRACKER_LIVE_BOF_ID: SentinelBalancesObservation(
                    "live_tracker"
                )
            }
        )

        # get_parameter
        patch_get_parameter = patch.object(withdrawal_fees.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )

        # balance_at_coordinates
        patch_balance_at_coordinates = patch.object(withdrawal_fees.utils, "balance_at_coordinates")
        self.mock_balance_at_coordinates = patch_balance_at_coordinates.start()

        # create_postings
        mock_create_postings = patch.object(withdrawal_fees.utils, "create_postings")
        self.mock_create_postings = mock_create_postings.start()
        self.mock_create_postings.return_value = DEFAULT_POSTINGS

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_reset_withdrawals_tracker_returns_custom_instruction_when_balance_non_zero(self):
        self.mock_balance_at_coordinates.return_value = Decimal("100")
        expected_result = [
            CustomInstruction(
                postings=DEFAULT_POSTINGS,
                instruction_details={"description": "Resetting the withdrawals tracker"},
                override_all_restrictions=True,
            )
        ]

        result = withdrawal_fees.reset_withdrawals_tracker(
            vault=self.mock_vault,
        )
        self.assertListEqual(result, expected_result)

        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances_live_tracker,
            address=withdrawal_fees.EARLY_WITHDRAWALS_TRACKER,
            denomination=self.default_denomination,
        )
        self.mock_create_postings.assert_called_once_with(
            amount=Decimal("100"),
            debit_account=ACCOUNT_ID,
            credit_account=ACCOUNT_ID,
            debit_address=withdrawal_fees.EARLY_WITHDRAWALS_TRACKER,
            credit_address=withdrawal_fees.common_addresses.INTERNAL_CONTRA,
            denomination=self.default_denomination,
        )

    def test_reset_withdrawals_tracker_returns_custom_instruction_with_optional_parameters(self):
        self.mock_balance_at_coordinates.return_value = Decimal("100")
        expected_result = [
            CustomInstruction(
                postings=DEFAULT_POSTINGS,
                instruction_details={"description": "Resetting the withdrawals tracker"},
                override_all_restrictions=True,
            )
        ]

        result = withdrawal_fees.reset_withdrawals_tracker(
            vault=self.mock_vault,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )
        self.assertListEqual(result, expected_result)

        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=withdrawal_fees.EARLY_WITHDRAWALS_TRACKER,
            denomination=sentinel.denomination,
        )
        self.mock_create_postings.assert_called_once_with(
            amount=Decimal("100"),
            debit_account=ACCOUNT_ID,
            credit_account=ACCOUNT_ID,
            debit_address=withdrawal_fees.EARLY_WITHDRAWALS_TRACKER,
            credit_address=withdrawal_fees.common_addresses.INTERNAL_CONTRA,
            denomination=sentinel.denomination,
        )

    def test_reset_withdrawals_tracker_returns_blank_list_when_balance_zero(self):
        self.mock_balance_at_coordinates.return_value = Decimal("0")

        result = withdrawal_fees.reset_withdrawals_tracker(
            vault=self.mock_vault,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )
        self.assertListEqual(result, [])

        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=withdrawal_fees.EARLY_WITHDRAWALS_TRACKER,
            denomination=sentinel.denomination,
        )
        self.mock_create_postings.assert_not_called()


class CalculateLimitsTest(FeatureTest):
    def setUp(self) -> None:
        # get_parameter
        patch_get_parameter = patch.object(withdrawal_fees.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                withdrawal_fees.PARAM_MAXIMUM_WITHDRAWAL_PERCENTAGE_LIMIT: "0.89127",
                withdrawal_fees.PARAM_FEE_FREE_WITHDRAWAL_PERCENTAGE_LIMIT: "0.05145",
            }
        )
        # _get_customer_deposit_amount
        patch_get_customer_deposit_amount = patch.object(
            withdrawal_fees, "get_customer_deposit_amount"
        )
        self.mock_get_customer_deposit_amount = patch_get_customer_deposit_amount.start()
        self.mock_get_customer_deposit_amount.return_value = Decimal("100")

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_calculate_maximum_withdrawal_limit(self):
        result = withdrawal_fees._calculate_maximum_withdrawal_limit(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=self.default_denomination,
            balances=sentinel.balances,
            balance_adjustments=sentinel.balance_adjustments,
        )
        self.assertEqual(result, Decimal("89.13"))

        self.mock_get_customer_deposit_amount.assert_called_once_with(
            vault=sentinel.vault,
            balances=sentinel.balances,
            denomination=self.default_denomination,
            balance_adjustments=sentinel.balance_adjustments,
        )

    def test_calculate_fee_free_withdrawal_limit(self):
        result = withdrawal_fees._calculate_fee_free_withdrawal_limit(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=self.default_denomination,
            balances=sentinel.balances,
            balance_adjustments=sentinel.balance_adjustments,
        )
        self.assertEqual(result, Decimal("5.15"))

        self.mock_get_customer_deposit_amount.assert_called_once_with(
            vault=sentinel.vault,
            balances=sentinel.balances,
            denomination=self.default_denomination,
            balance_adjustments=sentinel.balance_adjustments,
        )


class CalculateWithdrawalAmountSubjectToFeeTest(FeatureTest):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = sentinel.vault

        # balance_at_coordinates
        patch_balance_at_coordinates = patch.object(withdrawal_fees.utils, "balance_at_coordinates")
        self.mock_balance_at_coordinates = patch_balance_at_coordinates.start()

        # _calculate_fee_free_withdrawal_limit
        patch_calculate_fee_free_withdrawal_limit = patch.object(
            withdrawal_fees, "_calculate_fee_free_withdrawal_limit"
        )
        self.mock_calculate_fee_free_withdrawal_limit = (
            patch_calculate_fee_free_withdrawal_limit.start()
        )
        self.mock_calculate_fee_free_withdrawal_limit.return_value = Decimal("40")

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_no_previous_withdrawals(self):
        self.mock_balance_at_coordinates.return_value = Decimal("0")  # withdrawals tracker

        # withdrawal of 100, fee free limit 40, no previous withdrawals
        expected_result = Decimal("60")

        result = withdrawal_fees._calculate_withdrawal_amount_subject_to_fees(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            withdrawal_amount=Decimal("100"),
            denomination=self.default_denomination,
            balances=sentinel.balances,
        )
        self.assertEqual(result, expected_result)

        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=withdrawal_fees.EARLY_WITHDRAWALS_TRACKER,
            denomination=self.default_denomination,
        )
        self.mock_calculate_fee_free_withdrawal_limit.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=self.default_denomination,
            balances=sentinel.balances,
            balance_adjustments=None,
        )

    def test_no_previous_withdrawals_with_optional_parameters(self):
        self.mock_balance_at_coordinates.return_value = Decimal("0")  # withdrawals tracker

        # withdrawal of 100, fee free limit 40, no previous withdrawals
        expected_result = Decimal("60")

        result = withdrawal_fees._calculate_withdrawal_amount_subject_to_fees(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            withdrawal_amount=Decimal("100"),
            denomination=self.default_denomination,
            balances=sentinel.balances,
        )
        self.assertEqual(result, expected_result)

        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=withdrawal_fees.EARLY_WITHDRAWALS_TRACKER,
            denomination=self.default_denomination,
        )
        self.mock_calculate_fee_free_withdrawal_limit.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=self.default_denomination,
            balances=sentinel.balances,
            balance_adjustments=None,
        )

    def test_previous_withdrawals_below_fee_free_limit_and_remain_within_fee_free_limit(self):
        self.mock_balance_at_coordinates.return_value = Decimal("25")  # withdrawals tracker

        # withdrawal of 10, fee free limit 40, previous withdrawals 25
        # => fee free limit remaining 15, hence not subject to fees
        expected_result = Decimal("0")
        result = withdrawal_fees._calculate_withdrawal_amount_subject_to_fees(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            withdrawal_amount=Decimal("10"),
            denomination=self.default_denomination,
            balances=sentinel.balances,
        )
        self.assertEqual(result, expected_result)

        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=withdrawal_fees.EARLY_WITHDRAWALS_TRACKER,
            denomination=self.default_denomination,
        )
        self.mock_calculate_fee_free_withdrawal_limit.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=self.default_denomination,
            balances=sentinel.balances,
            balance_adjustments=None,
        )

    def test_remaining_fee_free_limit_used_and_exceeded_by_withdrawal(self):
        self.mock_balance_at_coordinates.return_value = Decimal("25")  # withdrawals tracker

        # withdrawal of 100, fee free limit 40, previous withdrawals 25
        # => fee free limit remaining 15, 85 of withdrawal amount subject to fees
        expected_result = Decimal("85")
        result = withdrawal_fees._calculate_withdrawal_amount_subject_to_fees(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            withdrawal_amount=Decimal("100"),
            denomination=self.default_denomination,
            balances=sentinel.balances,
        )
        self.assertEqual(result, expected_result)

        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=withdrawal_fees.EARLY_WITHDRAWALS_TRACKER,
            denomination=self.default_denomination,
        )
        self.mock_calculate_fee_free_withdrawal_limit.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=self.default_denomination,
            balances=sentinel.balances,
            balance_adjustments=None,
        )

    def test_previous_withdrawals_exceed_fee_free_limit(self):
        self.mock_balance_at_coordinates.return_value = Decimal("55")  # withdrawals tracker

        # withdrawal of 100, fee free limit 40, previous withdrawals 55
        # => fee free limit remaining 0, 100 of withdrawal amount subject to fees
        expected_result = Decimal("100")
        result = withdrawal_fees._calculate_withdrawal_amount_subject_to_fees(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            withdrawal_amount=Decimal("100"),
            denomination=self.default_denomination,
            balances=sentinel.balances,
        )
        self.assertEqual(result, expected_result)
        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=withdrawal_fees.EARLY_WITHDRAWALS_TRACKER,
            denomination=self.default_denomination,
        )
        self.mock_calculate_fee_free_withdrawal_limit.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=self.default_denomination,
            balances=sentinel.balances,
            balance_adjustments=None,
        )


class CalculateWithdrawalFeeAmountsTest(FeatureTest):
    def setUp(self) -> None:
        # _calculate_withdrawal_amount_subject_to_fees
        patch_calculate_withdrawal_amount_subject_to_fees = patch.object(
            withdrawal_fees, "_calculate_withdrawal_amount_subject_to_fees"
        )
        self.mock_calculate_withdrawal_amount_subject_to_fees = (
            patch_calculate_withdrawal_amount_subject_to_fees.start()
        )

        # get_parameter
        patch_get_parameter = patch.object(withdrawal_fees.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                withdrawal_fees.PARAM_EARLY_WITHDRAWAL_FLAT_FEE: "10",
                withdrawal_fees.PARAM_EARLY_WITHDRAWAL_PERCENTAGE_FEE: "0.05",
            }
        )

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_flat_and_percentage_fee_returned_when_positive_amount_subject_to_fee(self):
        self.mock_calculate_withdrawal_amount_subject_to_fees.return_value = Decimal("100")

        result = withdrawal_fees.calculate_withdrawal_fee_amounts(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            withdrawal_amount=sentinel.withdrawal_amount,
            denomination=self.default_denomination,
            balances=sentinel.balances,
        )
        self.assertTupleEqual(result, (Decimal("10"), Decimal("5")))

        self.mock_calculate_withdrawal_amount_subject_to_fees.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            withdrawal_amount=sentinel.withdrawal_amount,
            denomination=self.default_denomination,
            balances=sentinel.balances,
            balance_adjustments=None,
        )

    def test_flat_and_percentage_fee_returned_with_balance_adjustments(self):
        self.mock_calculate_withdrawal_amount_subject_to_fees.return_value = Decimal("100")

        result = withdrawal_fees.calculate_withdrawal_fee_amounts(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            withdrawal_amount=sentinel.withdrawal_amount,
            denomination=self.default_denomination,
            balances=sentinel.balances,
            balance_adjustments=sentinel.balance_adjustments,
        )
        self.assertTupleEqual(result, (Decimal("10"), Decimal("5")))

        self.mock_calculate_withdrawal_amount_subject_to_fees.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            withdrawal_amount=sentinel.withdrawal_amount,
            denomination=self.default_denomination,
            balances=sentinel.balances,
            balance_adjustments=sentinel.balance_adjustments,
        )

    def test_zero_fee_returned_when_zero_amount_subject_to_fee(self):
        self.mock_calculate_withdrawal_amount_subject_to_fees.return_value = Decimal("0")

        result = withdrawal_fees.calculate_withdrawal_fee_amounts(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            withdrawal_amount=sentinel.withdrawal_amount,
            denomination=self.default_denomination,
            balances=sentinel.balances,
        )
        self.assertTupleEqual(result, (Decimal("0"), Decimal("0")))


class DerivedParameterHelpersTest(FeatureTest):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                withdrawal_fees.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                    SentinelBalancesObservation("effective")
                )
            },
        )

        # get_parameter
        patch_get_parameter = patch.object(withdrawal_fees.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
            }
        )

        self.addCleanup(patch.stopall)
        return super().setUp()

    @patch.object(withdrawal_fees, "_calculate_maximum_withdrawal_limit")
    def test_get_maximum_withdrawal_limit_derived_parameter(
        self, mock_calculate_maximum_withdrawal_limit: MagicMock
    ):
        mock_calculate_maximum_withdrawal_limit.return_value = Decimal("1")
        result = withdrawal_fees.get_maximum_withdrawal_limit_derived_parameter(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
        )
        self.assertEqual(result, Decimal("1"))

        mock_calculate_maximum_withdrawal_limit.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.balances_effective,
            denomination=self.default_denomination,
            balance_adjustments=None,
        )

    @patch.object(withdrawal_fees, "_calculate_maximum_withdrawal_limit")
    def test_get_maximum_withdrawal_limit_derived_parameter_with_optional_parameters(
        self, mock_calculate_maximum_withdrawal_limit: MagicMock
    ):
        mock_calculate_maximum_withdrawal_limit.return_value = Decimal("1")
        result = withdrawal_fees.get_maximum_withdrawal_limit_derived_parameter(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.provided_balances,
            denomination=sentinel.provided_denomination,
            balance_adjustments=sentinel.balance_adjustments,
        )
        self.assertEqual(result, Decimal("1"))

        mock_calculate_maximum_withdrawal_limit.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.provided_balances,
            denomination=sentinel.provided_denomination,
            balance_adjustments=sentinel.balance_adjustments,
        )

    @patch.object(withdrawal_fees, "_calculate_fee_free_withdrawal_limit")
    def test_get_fee_free_withdrawal_limit_derived_parameter(
        self, mock__calculate_fee_free_withdrawal_limit: MagicMock
    ):
        mock__calculate_fee_free_withdrawal_limit.return_value = Decimal("1")
        result = withdrawal_fees.get_fee_free_withdrawal_limit_derived_parameter(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
        )
        self.assertEqual(result, Decimal("1"))

        mock__calculate_fee_free_withdrawal_limit.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.balances_effective,
            denomination=self.default_denomination,
            balance_adjustments=None,
        )

    @patch.object(withdrawal_fees, "_calculate_fee_free_withdrawal_limit")
    def test_get_fee_free_withdrawal_limit_derived_parameter_with_optional_parameters(
        self, mock__calculate_fee_free_withdrawal_limit: MagicMock
    ):
        mock__calculate_fee_free_withdrawal_limit.return_value = Decimal("1")
        result = withdrawal_fees.get_fee_free_withdrawal_limit_derived_parameter(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.provided_balances,
            denomination=sentinel.provided_denomination,
            balance_adjustments=sentinel.balance_adjustments,
        )
        self.assertEqual(result, Decimal("1"))

        mock__calculate_fee_free_withdrawal_limit.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.provided_balances,
            denomination=sentinel.provided_denomination,
            balance_adjustments=sentinel.balance_adjustments,
        )
