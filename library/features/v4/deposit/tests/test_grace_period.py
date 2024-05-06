# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.v4.deposit.grace_period as grace_period
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import RejectionReason

# inception sdk
from inception_sdk.test_framework.common.utils import ac_coverage
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DATETIME,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    AccountNotificationDirective,
    Rejection,
    ScheduledEvent,
    SmartContractEventType,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelScheduleExpression,
)


class GracePeriodGeneralTest(FeatureTest):
    def test_notification_type(self):
        product_name = "TEST_PRODUCT"

        result = grace_period.notification_type(product_name=product_name)

        self.assertEqual(result, "TEST_PRODUCT_GRACE_PERIOD_END")

    def test_event_types(self):
        product_name = "TEST_PRODUCT"
        expected_schedule_tag = ["TEST_PRODUCT_GRACE_PERIOD_END_AST"]
        expected_event_type: list[SmartContractEventType] = [
            SmartContractEventType(
                name=grace_period.GRACE_PERIOD_END_EVENT,
                scheduler_tag_ids=expected_schedule_tag,
            )
        ]

        result = grace_period.event_types(product_name=product_name)

        self.assertListEqual(result, expected_event_type)


class DerivedParameterTest(FeatureTest):
    @ac_coverage(["CPP-2083-AC-03"])
    @patch.object(grace_period.utils, "get_parameter")
    def test_derived_params_grace_period_end_datetime(self, mock_get_parameter: MagicMock):
        mock_vault = self.create_mock(creation_date=DEFAULT_DATETIME)
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "grace_period": 5,
            }
        )

        expected_result = datetime(2019, 1, 6, 23, 59, 59, 999999, tzinfo=ZoneInfo("UTC"))
        result = grace_period.get_grace_period_end_datetime(vault=mock_vault)

        self.assertEqual(result, expected_result)


class ScheduleEventTest(FeatureTest):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = self.create_mock()

        # get parameter
        patch_get_grace_period_end_datetime = patch.object(
            grace_period, "get_grace_period_end_datetime"
        )
        self.mock_get_grace_period_end_datetime = patch_get_grace_period_end_datetime.start()
        self.mock_get_grace_period_end_datetime.return_value = DEFAULT_DATETIME

        # get one off schedule expression
        patch_one_off_schedule_expression = patch.object(
            grace_period.utils, "one_off_schedule_expression"
        )
        self.mock_one_off_schedule_expression = patch_one_off_schedule_expression.start()
        self.mock_one_off_schedule_expression.return_value = SentinelScheduleExpression(
            "grace_period_end"
        )

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_scheduled_events(self):
        expected_schedule_event = {
            grace_period.GRACE_PERIOD_END_EVENT: ScheduledEvent(
                start_datetime=DEFAULT_DATETIME - relativedelta(seconds=1),
                expression=SentinelScheduleExpression("grace_period_end"),
                end_datetime=DEFAULT_DATETIME,
            )
        }

        result = grace_period.scheduled_events(vault=sentinel.vault)

        self.assertDictEqual(result, expected_schedule_event)
        self.mock_one_off_schedule_expression.assert_called_once_with(
            schedule_datetime=DEFAULT_DATETIME
        )
        self.mock_get_grace_period_end_datetime.assert_called_once_with(vault=sentinel.vault)


class WithinGracePeriodTest(FeatureTest):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = self.create_mock(creation_date=DEFAULT_DATETIME)

        # get parameter
        patch_get_parameter = patch.object(grace_period.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "grace_period": 5,
            }
        )

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_within_grace_period_returns_true(self):
        effective_datetime = datetime(2019, 1, 6, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        result = grace_period.is_within_grace_period(
            vault=self.mock_vault, effective_datetime=effective_datetime
        )

        self.assertTrue(result)

    def test_at_grace_period_end_time_returns_true(self):
        effective_datetime = datetime(2019, 1, 6, 23, 59, 59, 999999, tzinfo=ZoneInfo("UTC"))
        result = grace_period.is_within_grace_period(
            vault=self.mock_vault, effective_datetime=effective_datetime
        )

        self.assertTrue(result)

    def test_outside_grace_period_returns_false(self):
        effective_datetime = datetime(2019, 1, 7, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        result = grace_period.is_within_grace_period(
            vault=self.mock_vault, effective_datetime=effective_datetime
        )

        self.assertFalse(result)


class ValidateDepositGracePeriodTest(FeatureTest):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = self.create_mock()

        # get_parameter
        patch_get_parameter = patch.object(grace_period.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
                "grace_period": 5,
            }
        )

        # get_current_credit_balance
        patch_get_current_credit_balance = patch.object(
            grace_period.utils, "get_current_credit_balance"
        )
        self.mock_get_current_credit_balance = patch_get_current_credit_balance.start()
        self.mock_get_current_credit_balance.return_value = Decimal("10")

        # get_posting_instructions_balances
        patch_get_posting_instructions_balances = patch.object(
            grace_period.utils, "get_posting_instructions_balances"
        )
        self.mock_get_posting_instructions_balances = (
            patch_get_posting_instructions_balances.start()
        )
        self.mock_get_posting_instructions_balances.return_value = sentinel.instruction_balances

        # is_within_grace_period
        patch_is_within_grace_period = patch.object(grace_period, "is_within_grace_period")
        self.mock_is_within_grace_period = patch_is_within_grace_period.start()
        self.mock_is_within_grace_period.return_value = True

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_withdrawals_are_accepted(self):
        self.mock_get_current_credit_balance.return_value = Decimal("0")

        result = grace_period.validate_deposit(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.instructions,
        )
        self.assertIsNone(result)

    @ac_coverage(["CPP-2083-AC-04"])
    def test_deposits_accepted_within_grace_period(self):
        self.mock_get_current_credit_balance.return_value = Decimal("10")

        result = grace_period.validate_deposit(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.instructions,
        )
        self.assertIsNone(result)

    @ac_coverage(["CPP-2083-AC-05"])
    def test_deposits_rejected_outside_grace_period(self):
        self.mock_is_within_grace_period.return_value = False
        self.mock_get_current_credit_balance.return_value = Decimal("10")

        expected_result = Rejection(
            message="No deposits are allowed after the grace period end",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        result = grace_period.validate_deposit(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.instructions,
        )
        self.assertEqual(result, expected_result)


class WithdrawalSubjectToFeesTest(FeatureTest):
    def setUp(self) -> None:

        patch_is_within_grace_period = patch.object(grace_period, "is_within_grace_period")
        self.mock_is_within_grace_period = patch_is_within_grace_period.start()
        self.mock_is_within_grace_period.return_value = True

        patch_posting_balances = patch.object(
            grace_period.utils, "get_posting_instructions_balances"
        )
        self.mock_get_posting_instructions_balances = patch_posting_balances.start()
        self.mock_get_posting_instructions_balances.return_value = sentinel.posting_balances

        patch_posting_available_balance = patch.object(grace_period.utils, "get_available_balance")
        self.mock_get_available_balance = patch_posting_available_balance.start()
        self.mock_get_available_balance.return_value = Decimal("-1")

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_is_withdrawal_subject_to_fees_withdrawal_within_grace_period(self):
        result = grace_period.is_withdrawal_subject_to_fees(
            vault=sentinel.vault,
            effective_datetime=sentinel.datetime,
            posting_instructions=sentinel.posting_instructions,
            denomination=sentinel.denomination,
        )
        self.assertFalse(result)
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions
        )
        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.posting_balances, denomination=sentinel.denomination
        )
        self.mock_is_within_grace_period.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.datetime
        )

    def test_is_withdrawal_subject_to_fees_withdrawal_outside_grace_period(self):
        self.mock_is_within_grace_period.return_value = False
        result = grace_period.is_withdrawal_subject_to_fees(
            vault=sentinel.vault,
            effective_datetime=sentinel.datetime,
            posting_instructions=sentinel.posting_instructions,
            denomination=sentinel.denomination,
        )
        self.assertTrue(result)
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions
        )
        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.posting_balances, denomination=sentinel.denomination
        )
        self.mock_is_within_grace_period.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.datetime
        )

    def test_is_withdrawal_subject_to_fees_deposit_within_grace_period(self):
        self.mock_get_available_balance.return_value = Decimal("1")
        result = grace_period.is_withdrawal_subject_to_fees(
            vault=sentinel.vault,
            effective_datetime=sentinel.datetime,
            posting_instructions=sentinel.posting_instructions,
            denomination=sentinel.denomination,
        )
        self.assertFalse(result)
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions
        )
        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.posting_balances, denomination=sentinel.denomination
        )
        self.mock_is_within_grace_period.assert_not_called()

    @patch.object(grace_period.common_parameters, "get_denomination_parameter")
    def test_is_withdrawal_subject_to_fees_deposit_outside_grace_period(
        self, mock_get_denomination_parameter: MagicMock
    ):
        self.mock_get_available_balance.return_value = Decimal("1")
        self.mock_is_within_grace_period.return_value = False
        mock_get_denomination_parameter.return_value = sentinel.non_provided_denomination
        result = grace_period.is_withdrawal_subject_to_fees(
            vault=sentinel.vault,
            effective_datetime=sentinel.datetime,
            posting_instructions=sentinel.posting_instructions,
        )
        self.assertFalse(result)
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions
        )
        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.posting_balances, denomination=sentinel.non_provided_denomination
        )
        self.mock_is_within_grace_period.assert_not_called()


class ValidateTermParameterChangeTest(FeatureTest):
    @ac_coverage(["CPP-2083-AC-08"])
    @patch.object(grace_period, "is_within_grace_period")
    def test_accept_term_parameter_change_within_grace_period(
        self, mock_is_within_grace_period: MagicMock
    ):
        mock_is_within_grace_period.return_value = True

        result = grace_period.validate_term_parameter_change(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )
        self.assertIsNone(result)
        mock_is_within_grace_period.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )

    @ac_coverage(["CPP-2083-AC-09"])
    @patch.object(grace_period, "is_within_grace_period")
    def test_reject_term_parameter_change_outside_grace_period(
        self, mock_is_within_grace_period: MagicMock
    ):
        mock_is_within_grace_period.return_value = False
        expected_result = Rejection(
            message="Term length cannot be changed outside the grace period",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        result = grace_period.validate_term_parameter_change(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )
        self.assertEqual(result, expected_result)
        mock_is_within_grace_period.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )


class HandleAccountClosureNotificationTest(FeatureTest):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                "EFFECTIVE_FETCHER": SentinelBalancesObservation("dummy_observation")
            }
        )

        self.product_name = "TEST_PRODUCT"

        # get current credit balance
        patch_get_current_net_balance = patch.object(grace_period.utils, "get_current_net_balance")
        self.mock_get_current_net_balance = patch_get_current_net_balance.start()
        self.mock_get_current_net_balance.return_value = Decimal("0")

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_no_notification_when_non_zero_net_balance(self):
        self.mock_get_current_net_balance.return_value = Decimal("100")

        result = grace_period.handle_account_closure_notification(
            vault=self.mock_vault,
            product_name=self.product_name,
            effective_datetime=DEFAULT_DATETIME,
            denomination=self.default_denomination,
            balances=sentinel.balances_observation,
        )

        self.assertListEqual(result, [])
        self.mock_get_current_net_balance.assert_called_once_with(
            balances=sentinel.balances_observation, denomination=self.default_denomination
        )

    @patch.object(grace_period.common_parameters, "get_denomination_parameter")
    def test_notification_sent_when_no_funds_with_optional_parameters(
        self, mock_get_denomination_parameter: MagicMock
    ):
        mock_get_denomination_parameter.return_value = sentinel.non_provided_denomination
        expected_notification_details = {
            "account_id": self.mock_vault.account_id,
            "grace_period_end_datetime": str(DEFAULT_DATETIME),
            "reason": "Close account due to lack of funds at the end of grace period",
        }
        expected_notification_type = "TEST_PRODUCT_GRACE_PERIOD_END"
        expected_notification = [
            AccountNotificationDirective(
                notification_type=expected_notification_type,
                notification_details=expected_notification_details,
            )
        ]

        result = grace_period.handle_account_closure_notification(
            vault=self.mock_vault,
            product_name=self.product_name,
            effective_datetime=DEFAULT_DATETIME,
        )

        self.assertListEqual(result, expected_notification)
        self.mock_get_current_net_balance.assert_called_once_with(
            balances=sentinel.balances_dummy_observation,
            denomination=sentinel.non_provided_denomination,
        )
