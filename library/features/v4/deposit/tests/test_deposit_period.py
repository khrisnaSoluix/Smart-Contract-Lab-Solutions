# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.v4.deposit.deposit_period as deposit_period
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


class DepositPeriodGeneralTest(FeatureTest):
    def test_notification_type(self):
        product_name = "TEST_PRODUCT"

        result = deposit_period.notification_type(product_name=product_name)

        self.assertEqual(result, "TEST_PRODUCT_DEPOSIT_PERIOD_END")

    def test_event_types(self):
        product_name = "TEST_PRODUCT"
        expected_schedule_tag = ["TEST_PRODUCT_DEPOSIT_PERIOD_END_AST"]
        expected_event_type: list[SmartContractEventType] = [
            SmartContractEventType(
                name=deposit_period.DEPOSIT_PERIOD_END_EVENT,
                scheduler_tag_ids=expected_schedule_tag,
            )
        ]

        result = deposit_period.event_types(product_name=product_name)

        self.assertListEqual(result, expected_event_type)


class DerivedParameterTest(FeatureTest):
    @ac_coverage(["CPP-2082-AC03"])
    @patch.object(deposit_period.utils, "get_parameter")
    def test_derived_params_deposit_period_end_datetime(self, mock_get_parameter: MagicMock):
        mock_vault = self.create_mock(creation_date=DEFAULT_DATETIME)
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "deposit_period": 2,
            }
        )
        expected_result = datetime(2019, 1, 3, 23, 59, 59, 999999, tzinfo=ZoneInfo("UTC"))
        result = deposit_period.get_deposit_period_end_datetime(vault=mock_vault)

        self.assertEqual(result, expected_result)


class ScheduleEventTest(FeatureTest):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = self.create_mock()

        # get parameter
        patch_get_parameter = patch.object(deposit_period.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "deposit_period": 2,
            }
        )

        # get one off schedule expression
        patch_one_off_schedule_expression = patch.object(
            deposit_period.utils, "one_off_schedule_expression"
        )
        self.mock_one_off_schedule_expression = patch_one_off_schedule_expression.start()
        self.mock_one_off_schedule_expression.return_value = SentinelScheduleExpression(
            "deposit_period_end"
        )

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_scheduled_events(self):
        test_deposit_period_end_datetime = datetime(
            2019, 1, 3, 23, 59, 59, 999999, tzinfo=ZoneInfo("UTC")
        )
        expected_schedule_event = ScheduledEvent(
            start_datetime=test_deposit_period_end_datetime - relativedelta(seconds=1),
            expression=SentinelScheduleExpression("deposit_period_end"),
            end_datetime=test_deposit_period_end_datetime,
        )

        result = deposit_period.scheduled_events(vault=self.mock_vault)

        self.assertEqual(result["DEPOSIT_PERIOD_END"], expected_schedule_event)
        self.mock_one_off_schedule_expression.assert_called_once_with(
            schedule_datetime=test_deposit_period_end_datetime
        )


class ValidateDepositTest(FeatureTest):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                "live_balances_bof": SentinelBalancesObservation("dummy_observation")
            }
        )

        # get_parameter
        patch_get_parameter = patch.object(deposit_period.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "deposit_period": 2,
                "number_of_permitted_deposits": "single",
            }
        )
        self.deposit_period_end_datetime = datetime(2019, 1, 3, 23, 59, 59, tzinfo=ZoneInfo("UTC"))

        # get_current_credit_balance
        patch_get_current_credit_balance = patch.object(
            deposit_period.utils, "get_current_credit_balance"
        )
        self.mock_get_current_credit_balance = patch_get_current_credit_balance.start()
        self.mock_get_current_credit_balance.side_effect = [
            Decimal("12"),  # deposit_proposed_amount
            Decimal("5"),  # credit_default_balance
        ]

        # get_posting_instructions_balances
        patch_get_posting_instructions_balances = patch.object(
            deposit_period.utils, "get_posting_instructions_balances"
        )
        self.mock_get_posting_instructions_balances = (
            patch_get_posting_instructions_balances.start()
        )
        self.mock_get_posting_instructions_balances.return_value = sentinel.instruction_balances

        # is_within_deposit_period
        patch_is_within_deposit_period = patch.object(deposit_period, "is_within_deposit_period")
        self.mock_is_within_deposit_period = patch_is_within_deposit_period.start()
        self.mock_is_within_deposit_period.return_value = True

        self.addCleanup(patch.stopall)
        return super().setUp()

    @ac_coverage(["CPP-2082-AC04", "CPP-2082-AC08"])
    def test_validation_when_unlimited_deposits_before_end_of_deposit_period(self):
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "deposit_period": 2,
                "number_of_permitted_deposits": "unlimited",
            }
        )

        result = deposit_period.validate(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.instructions,
            denomination=self.default_denomination,
            balances=sentinel.balances_observation,
        )

        self.assertIsNone(result)
        self.mock_get_current_credit_balance.assert_called_once_with(
            balances=sentinel.instruction_balances, denomination=self.default_denomination
        )

    @ac_coverage(["CPP-2082-AC05"])
    def test_validation_when_unlimited_deposits_after_end_of_deposit_period(self):
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "deposit_period": 2,
                "number_of_permitted_deposits": "unlimited",
            }
        )
        self.mock_is_within_deposit_period.return_value = False

        expected_rejection = Rejection(
            message="No deposits are allowed after the deposit period end datetime",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        result = deposit_period.validate(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME + relativedelta(days=10),
            posting_instructions=sentinel.instructions,
            denomination=self.default_denomination,
            balances=sentinel.balances_observation,
        )

        self.assertEqual(result, expected_rejection)
        self.mock_get_current_credit_balance.assert_called_once_with(
            balances=sentinel.instruction_balances, denomination=self.default_denomination
        )

    @ac_coverage(["CPP-2082-AC04", "CPP-2082-AC06"])
    def test_posting_is_accepted_when_single_deposit_is_configured_and_no_previous_deposits(self):
        self.mock_get_current_credit_balance.side_effect = [
            Decimal("12"),  # deposit_proposed_amount
            Decimal("0"),  # credit_default_balance
        ]

        result = deposit_period.validate(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.instructions,
            denomination=self.default_denomination,
            balances=sentinel.balances_observation,
        )

        self.assertIsNone(result)
        self.mock_get_current_credit_balance.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.instruction_balances, denomination=self.default_denomination
                ),
                call(
                    balances=sentinel.balances_observation, denomination=self.default_denomination
                ),
            ]
        )

    @ac_coverage(["CPP-2082-AC07"])
    def test_posting_is_rejected_when_single_deposit_is_configured_and_multiple_previous_deposits(
        self,
    ):
        expected_rejection = Rejection(
            message="Only a single deposit is allowed",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        result = deposit_period.validate(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.instructions,
            denomination=self.default_denomination,
            balances=sentinel.balances_observation,
        )

        self.assertEqual(result, expected_rejection)
        self.mock_get_current_credit_balance.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.instruction_balances, denomination=self.default_denomination
                ),
                call(
                    balances=sentinel.balances_observation, denomination=self.default_denomination
                ),
            ]
        )

    @ac_coverage(["CPP-2082-AC05"])
    def test_validation_when_deposit_made_on_deposit_period_end_date(self):
        DEPOSIT_PERIOD_END_DATETIME = datetime(2019, 1, 4, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        self.mock_is_within_deposit_period.return_value = False

        expected_rejection = Rejection(
            message="No deposits are allowed after the deposit period end datetime",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        result = deposit_period.validate(
            vault=self.mock_vault,
            effective_datetime=DEPOSIT_PERIOD_END_DATETIME,
            posting_instructions=sentinel.instructions,
            denomination=self.default_denomination,
            balances=sentinel.balances_observation,
        )

        self.assertEqual(result, expected_rejection)
        self.mock_get_current_credit_balance.assert_called_once_with(
            balances=sentinel.instruction_balances, denomination=self.default_denomination
        )

    def test_validation_when_optional_arguments_are_absent(self):
        self.mock_get_current_credit_balance.side_effect = [
            Decimal("12"),  # deposit_proposed_amount
            Decimal("0"),  # credit_default_balance
        ]
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "deposit_period": 2,
                "number_of_permitted_deposits": "single",
                "denomination": self.default_denomination,
            }
        )

        result = deposit_period.validate(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.instructions,
        )
        self.assertIsNone(result)
        self.mock_get_current_credit_balance.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.instruction_balances, denomination=self.default_denomination
                ),
                call(
                    balances=sentinel.balances_dummy_observation,
                    denomination=self.default_denomination,
                ),
            ]
        )


class WithinDepositPeriodTest(FeatureTest):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = self.create_mock(creation_date=DEFAULT_DATETIME)

        # get parameter
        patch_get_parameter = patch.object(deposit_period.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "deposit_period": 2,
            }
        )

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_within_deposit_period_returns_true(self):
        effective_datetime = datetime(2019, 1, 2, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        result = deposit_period.is_within_deposit_period(
            vault=self.mock_vault,
            effective_datetime=effective_datetime,
        )

        self.assertTrue(result)

    def test_at_deposit_period_end_time_returns_true(self):
        effective_datetime = datetime(2019, 1, 3, 23, 59, 59, 999999, tzinfo=ZoneInfo("UTC"))
        result = deposit_period.is_within_deposit_period(
            vault=self.mock_vault,
            effective_datetime=effective_datetime,
        )

        self.assertTrue(result)

    def test_outside_deposit_period_returns_false(self):
        effective_datetime = datetime(2019, 1, 4, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        result = deposit_period.is_within_deposit_period(
            vault=self.mock_vault,
            effective_datetime=effective_datetime,
        )

        self.assertFalse(result)


class NotificationTest(FeatureTest):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = self.create_mock()

        self.product_name = "TEST_PRODUCT"

        # get current credit balance
        patch_get_current_net_balance = patch.object(
            deposit_period.utils, "get_current_net_balance"
        )
        self.mock_get_current_net_balance = patch_get_current_net_balance.start()
        self.mock_get_current_net_balance.return_value = Decimal("0")

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_no_notification_when_funds_are_deposited(self):
        self.mock_get_current_net_balance.return_value = Decimal("100")

        result = deposit_period.handle_account_closure_notification(
            product_name=self.product_name,
            balances=sentinel.balances_observation,
            denomination=self.default_denomination,
            account_id=self.mock_vault.account_id,
            effective_datetime=DEFAULT_DATETIME,
        )

        self.assertListEqual(result, [])
        self.mock_get_current_net_balance.assert_called_once_with(
            balances=sentinel.balances_observation, denomination=self.default_denomination
        )

    @ac_coverage(["CPP-2082-AC09"])
    def test_deposit_period_end_notification_when_no_funds(self):
        expected_notification_details = {
            "account_id": self.mock_vault.account_id,
            "deposit_balance": str(Decimal("0")),
            "deposit_period_end_datetime": str(DEFAULT_DATETIME),
            "reason": "Close account due to lack of deposits at the end of deposit period",
        }
        expected_notification_type = "TEST_PRODUCT_DEPOSIT_PERIOD_END"
        expected_notification = [
            AccountNotificationDirective(
                notification_type=expected_notification_type,
                notification_details=expected_notification_details,
            )
        ]
        result = deposit_period.handle_account_closure_notification(
            product_name=self.product_name,
            balances=sentinel.balances_observation,
            denomination=self.default_denomination,
            account_id=self.mock_vault.account_id,
            effective_datetime=DEFAULT_DATETIME,
        )

        self.assertListEqual(result, expected_notification)
        self.mock_get_current_net_balance.assert_called_once_with(
            balances=sentinel.balances_observation, denomination=self.default_denomination
        )
