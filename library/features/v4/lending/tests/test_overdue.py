# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.common.fetchers as fetchers
import library.features.v4.lending.overdue as overdue
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import (
    BalanceDefaultDict,
    BalancesObservation,
    ScheduledEventHookArguments,
    SupervisorScheduledEventHookArguments,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    AccountNotificationDirective,
    CustomInstruction,
    ScheduledEvent,
    SmartContractEventType,
    SupervisorContractEventType,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelPosting,
    SentinelScheduleExpression,
)

DEFAULT_DATETIME = datetime(2020, 1, 2, 3, tzinfo=ZoneInfo("UTC"))


class OverdueTest(FeatureTest):
    maxDiff = None


sentinel_instruction_details = {"sentinel": "details"}  # TODO: sentinel-ize in the future


class ScheduleLogicTest(OverdueTest):
    def test_overdue_repayment_notification_type(
        self,
    ):
        product_name = "product_a"
        expected_notification_type = (
            f"{product_name.upper()}{overdue.OVERDUE_REPAYMENT_NOTIFICATION_SUFFIX}"
        )
        # run function
        result_notification_type = overdue.notification_type(product_name=product_name)
        # validate results
        self.assertEqual(result_notification_type, expected_notification_type)

    @patch.object(overdue, "notification_type")
    def test_get_overdue_repayment_notification_has_due_principal_only(
        self, mock_notification_type: MagicMock
    ):
        # expected values
        product_name = "PRODUCT_A"
        effective_datetime = DEFAULT_DATETIME
        due_principal_amount = Decimal("700")
        due_interest_amount = Decimal("0")
        late_repayment_fee = Decimal("0")

        expected_notification_type = (
            f"{product_name}{overdue.OVERDUE_REPAYMENT_NOTIFICATION_SUFFIX}"
        )
        mock_notification_type.return_value = expected_notification_type

        # construct expected result
        expected_notification_details = {
            "account_id": sentinel.account_id,
            "overdue_principal": str(due_principal_amount),
            "overdue_interest": str(due_interest_amount),
            "late_repayment_fee": str(late_repayment_fee),
            "overdue_date": str(effective_datetime.date()),
        }
        expected_notifications: list[AccountNotificationDirective] = [
            AccountNotificationDirective(
                notification_type=expected_notification_type,
                notification_details=expected_notification_details,
            )
        ]

        # run function
        result_notifications = overdue.get_overdue_repayment_notification(
            account_id=sentinel.account_id,
            product_name=product_name,
            effective_datetime=effective_datetime,
            overdue_principal_amount=due_principal_amount,
            overdue_interest_amount=due_interest_amount,
        )
        # validate results
        self.assertListEqual(expected_notifications, result_notifications)

    @patch.object(overdue, "notification_type")
    def test_get_overdue_repayment_notification_has_due_interest_only(
        self, mock_notification_type: MagicMock
    ):
        # expected values
        product_name = "PRODUCT_A"
        effective_datetime = DEFAULT_DATETIME
        due_principal_amount = Decimal("0")
        due_interest_amount = Decimal("12")
        late_repayment_fee = Decimal("0")

        expected_notification_type = (
            f"{product_name}{overdue.OVERDUE_REPAYMENT_NOTIFICATION_SUFFIX}"
        )
        mock_notification_type.return_value = expected_notification_type

        # construct expected result
        expected_notification_details = {
            "account_id": sentinel.account_id,
            "overdue_principal": str(due_principal_amount),
            "overdue_interest": str(due_interest_amount),
            "late_repayment_fee": str(late_repayment_fee),
            "overdue_date": str(effective_datetime.date()),
        }
        expected_notifications: list[AccountNotificationDirective] = [
            AccountNotificationDirective(
                notification_type=expected_notification_type,
                notification_details=expected_notification_details,
            )
        ]

        # run function
        result_notifications = overdue.get_overdue_repayment_notification(
            account_id=sentinel.account_id,
            product_name=product_name,
            effective_datetime=effective_datetime,
            overdue_principal_amount=due_principal_amount,
            overdue_interest_amount=due_interest_amount,
        )
        # validate results
        self.assertListEqual(expected_notifications, result_notifications)

    @patch.object(overdue, "notification_type")
    def test_get_overdue_repayment_notification_has_both_due_principal_and_due_interest(
        self, mock_notification_type: MagicMock
    ):
        # expected values
        product_name = "PRODUCT_A"
        effective_datetime = DEFAULT_DATETIME
        due_principal_amount = Decimal("120")
        due_interest_amount = Decimal("12")
        late_repayment_fee = Decimal("10")

        expected_notification_type = (
            f"{product_name}{overdue.OVERDUE_REPAYMENT_NOTIFICATION_SUFFIX}"
        )
        mock_notification_type.return_value = expected_notification_type

        # construct expected result
        expected_notification_details = {
            "account_id": sentinel.account_id,
            "overdue_principal": str(due_principal_amount),
            "overdue_interest": str(due_interest_amount),
            "late_repayment_fee": str(late_repayment_fee),
            "overdue_date": str(effective_datetime.date()),
        }
        expected_notifications: list[AccountNotificationDirective] = [
            AccountNotificationDirective(
                notification_type=expected_notification_type,
                notification_details=expected_notification_details,
            )
        ]

        # run function
        result_notifications = overdue.get_overdue_repayment_notification(
            account_id=sentinel.account_id,
            product_name=product_name,
            effective_datetime=effective_datetime,
            overdue_principal_amount=due_principal_amount,
            overdue_interest_amount=due_interest_amount,
            late_repayment_fee=late_repayment_fee,
        )
        # validate results
        self.assertListEqual(expected_notifications, result_notifications)

    @patch.object(overdue, "notification_type")
    def test_get_overdue_repayment_notification_has_late_repayment_fee(
        self, mock_notification_type: MagicMock
    ):
        # expected values
        product_name = "PRODUCT_A"
        effective_datetime = DEFAULT_DATETIME
        due_principal_amount = Decimal("12")
        due_interest_amount = Decimal("0")
        late_repayment_fee = Decimal("10")

        expected_notification_type = (
            f"{product_name}{overdue.OVERDUE_REPAYMENT_NOTIFICATION_SUFFIX}"
        )
        mock_notification_type.return_value = expected_notification_type

        # construct expected result
        expected_notification_details = {
            "account_id": sentinel.account_id,
            "overdue_principal": str(due_principal_amount),
            "overdue_interest": str(due_interest_amount),
            "late_repayment_fee": str(late_repayment_fee),
            "overdue_date": str(effective_datetime.date()),
        }
        expected_notifications: list[AccountNotificationDirective] = [
            AccountNotificationDirective(
                notification_type=expected_notification_type,
                notification_details=expected_notification_details,
            )
        ]

        # run function
        result_notifications = overdue.get_overdue_repayment_notification(
            account_id=sentinel.account_id,
            product_name=product_name,
            effective_datetime=effective_datetime,
            overdue_principal_amount=due_principal_amount,
            overdue_interest_amount=due_interest_amount,
            late_repayment_fee=late_repayment_fee,
        )
        # validate results
        self.assertListEqual(expected_notifications, result_notifications)

    def test_get_overdue_repayment_notification_no_due_principal_and_due_interest(self):
        # expected values
        product_name = "PRODUCT_A"
        effective_datetime = DEFAULT_DATETIME
        due_principal_amount = Decimal("0")
        due_interest_amount = Decimal("0")
        late_repayment_fee = Decimal("10")
        # run function
        result_notifications = overdue.get_overdue_repayment_notification(
            account_id=sentinel.account_id,
            product_name=product_name,
            effective_datetime=effective_datetime,
            overdue_principal_amount=due_principal_amount,
            overdue_interest_amount=due_interest_amount,
            late_repayment_fee=late_repayment_fee,
        )
        # validate results
        self.assertListEqual(result_notifications, [])

    @patch.object(overdue.utils, "create_postings")
    @patch.object(overdue.utils, "standard_instruction_details")
    @patch.object(overdue.utils, "get_parameter")
    def test_scheduled_logic_without_overdue_accumulation(
        self,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
        mock_create_postings: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: BalancesObservation(
                    balances=BalanceDefaultDict(mapping={}),
                    value_datetime=DEFAULT_DATETIME,
                ),
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_create_postings.return_value = []
        mock_standard_instruction_details.return_value = sentinel_instruction_details
        # run function
        result_instructions, result_notifications = overdue.schedule_logic(
            vault=mock_vault,
            account_type=sentinel.account_type,
            hook_arguments=ScheduledEventHookArguments(
                event_type=sentinel.event_type,
                effective_datetime=DEFAULT_DATETIME,
            ),
        )
        # validate results
        self.assertListEqual(result_instructions, [])
        self.assertListEqual(result_notifications, [])

    @patch.object(overdue.utils, "create_postings")
    @patch.object(overdue.utils, "standard_instruction_details")
    @patch.object(overdue.utils, "get_parameter")
    @patch.object(overdue.utils, "balance_at_coordinates")
    @patch.object(overdue, "get_overdue_repayment_notification")
    def test_scheduled_logic_with_overdue_accumulation(
        self,
        mock_get_overdue_repayment_notification: MagicMock,
        mock_get_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
        mock_create_postings: MagicMock,
    ):
        # expected values
        balances_observation = SentinelBalancesObservation("overdue")
        principal_postings = [SentinelPosting(f"principal_{i}") for i in range(2)]
        interest_postings = [SentinelPosting(f"interest_{i}") for i in range(2)]
        # construct expected result
        expected_instructions = [
            CustomInstruction(
                postings=[*principal_postings, *interest_postings],  # type: ignore
                override_all_restrictions=True,
                instruction_details=sentinel_instruction_details,
            )
        ]
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: balances_observation,
            }
        )
        mock_create_postings.side_effect = [principal_postings, interest_postings]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_standard_instruction_details.return_value = sentinel_instruction_details
        mock_get_overdue_repayment_notification.return_value = []
        # run function
        result_instructions, _ = overdue.schedule_logic(
            vault=mock_vault,
            account_type=sentinel.account_type,
            hook_arguments=ScheduledEventHookArguments(
                event_type=sentinel.event_type,
                effective_datetime=DEFAULT_DATETIME,
            ),
        )
        # validate results
        self.assertListEqual(result_instructions, expected_instructions)

        mock_get_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.balances_overdue,
                    address=overdue.lending_addresses.PRINCIPAL_DUE,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=sentinel.balances_overdue,
                    address=overdue.lending_addresses.INTEREST_DUE,
                    denomination=sentinel.denomination,
                ),
            ]
        )

    @patch.object(overdue.utils, "create_postings")
    @patch.object(overdue.utils, "standard_instruction_details")
    @patch.object(overdue.utils, "get_parameter")
    @patch.object(overdue.utils, "balance_at_coordinates")
    @patch.object(overdue, "get_overdue_repayment_notification")
    def test_scheduled_logic_with_notification_and_late_repayment_fee(
        self,
        mock_get_overdue_repayment_notification: MagicMock,
        mock_get_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
        mock_create_postings: MagicMock,
    ):
        # expected_values
        product_name = "product_a"
        dummy_amount = Decimal("100")
        due_principal_amount = dummy_amount
        due_interest_amount = dummy_amount
        late_repayment_fee = Decimal("10")
        effective_datetime = DEFAULT_DATETIME
        balances_observation = SentinelBalancesObservation("overdue")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: balances_observation,
            }
        )
        principal_postings = [SentinelPosting(f"principal_{i}") for i in range(2)]
        interest_postings = [SentinelPosting(f"interest_{i}") for i in range(2)]

        # construct expected result
        expected_instructions = [
            CustomInstruction(
                postings=[*principal_postings, *interest_postings],  # type: ignore
                override_all_restrictions=True,
                instruction_details=sentinel_instruction_details,
            )
        ]
        expected_notification_details = {
            "account_id": str(mock_vault.account_id),
            "overdue_principal": str(due_principal_amount),
            "overdue_interest": str(due_interest_amount),
            "late_repayment_fee": str(late_repayment_fee),
            "overdue_date": str(effective_datetime),
        }
        expected_notifications: list[AccountNotificationDirective] = [
            AccountNotificationDirective(
                notification_type=overdue.notification_type(product_name),
                notification_details=expected_notification_details,
            )
        ]

        # construct mocks

        mock_create_postings.side_effect = [principal_postings, interest_postings]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_standard_instruction_details.return_value = sentinel_instruction_details
        mock_get_balance_at_coordinates.return_value = dummy_amount
        mock_get_overdue_repayment_notification.return_value = expected_notifications

        # run function
        result_instructions, result_notifications = overdue.schedule_logic(
            vault=mock_vault,
            account_type=product_name,
            hook_arguments=ScheduledEventHookArguments(
                event_type=sentinel.event_type,
                effective_datetime=effective_datetime,
            ),
            late_repayment_fee=late_repayment_fee,
        )

        # validate results
        self.assertListEqual(result_instructions, expected_instructions)
        self.assertListEqual(result_notifications, expected_notifications)

        mock_get_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.balances_overdue,
                    address=overdue.lending_addresses.PRINCIPAL_DUE,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=sentinel.balances_overdue,
                    address=overdue.lending_addresses.INTEREST_DUE,
                    denomination=sentinel.denomination,
                ),
            ]
        )
        mock_get_overdue_repayment_notification.assert_called_with(
            account_id=mock_vault.account_id,
            product_name=product_name,
            effective_datetime=effective_datetime,
            overdue_principal_amount=due_principal_amount,
            overdue_interest_amount=due_interest_amount,
            late_repayment_fee=late_repayment_fee,
        )

    @patch.object(overdue.utils, "create_postings")
    @patch.object(overdue.utils, "standard_instruction_details")
    @patch.object(overdue.utils, "get_parameter")
    @patch.object(overdue.utils, "balance_at_coordinates")
    @patch.object(overdue, "get_overdue_repayment_notification")
    def test_scheduled_logic_as_supervisor_pass_balances(
        self,
        mock_get_overdue_repayment_notification: MagicMock,
        mock_get_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
        mock_create_postings: MagicMock,
    ):
        # expected_values
        product_name = "product_a"
        dummy_amount = Decimal("100")
        due_principal_amount = dummy_amount
        due_interest_amount = dummy_amount
        late_repayment_fee = Decimal("10")
        effective_datetime = DEFAULT_DATETIME
        balances_observation = SentinelBalancesObservation("overdue")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: balances_observation,
            }
        )
        principal_postings = [SentinelPosting(f"principal_{i}") for i in range(2)]
        interest_postings = [SentinelPosting(f"interest_{i}") for i in range(2)]

        # construct expected result
        expected_instructions = [
            CustomInstruction(
                postings=[*principal_postings, *interest_postings],  # type: ignore
                override_all_restrictions=True,
                instruction_details=sentinel_instruction_details,
            )
        ]
        expected_notification_details = {
            "account_id": str(mock_vault.account_id),
            "overdue_principal": str(due_principal_amount),
            "overdue_interest": str(due_interest_amount),
            "late_repayment_fee": str(late_repayment_fee),
            "overdue_date": str(effective_datetime),
        }
        expected_notifications: list[AccountNotificationDirective] = [
            AccountNotificationDirective(
                notification_type=overdue.notification_type(product_name),
                notification_details=expected_notification_details,
            )
        ]

        # construct mocks

        mock_create_postings.side_effect = [principal_postings, interest_postings]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_standard_instruction_details.return_value = sentinel_instruction_details
        mock_get_balance_at_coordinates.return_value = dummy_amount
        mock_get_overdue_repayment_notification.return_value = expected_notifications

        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=effective_datetime,
            event_type=sentinel.event_type,
            supervisee_pause_at_datetime={},
        )

        # run function
        result_instructions, result_notifications = overdue.schedule_logic(
            vault=mock_vault,
            account_type=product_name,
            hook_arguments=hook_arguments,
            balances=sentinel.balances_overdue,
            late_repayment_fee=late_repayment_fee,
        )

        # validate results
        self.assertListEqual(result_instructions, expected_instructions)
        self.assertListEqual(result_notifications, expected_notifications)

        mock_get_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.balances_overdue,
                    address=overdue.lending_addresses.PRINCIPAL_DUE,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=sentinel.balances_overdue,
                    address=overdue.lending_addresses.INTEREST_DUE,
                    denomination=sentinel.denomination,
                ),
            ]
        )
        mock_get_overdue_repayment_notification.assert_called_with(
            account_id=mock_vault.account_id,
            product_name=product_name,
            effective_datetime=effective_datetime,
            overdue_principal_amount=due_principal_amount,
            overdue_interest_amount=due_interest_amount,
            late_repayment_fee=late_repayment_fee,
        )

    @patch.object(overdue.utils, "create_postings")
    @patch.object(overdue.utils, "standard_instruction_details")
    @patch.object(overdue.utils, "get_parameter")
    @patch.object(overdue.utils, "balance_at_coordinates")
    @patch.object(overdue, "get_overdue_repayment_notification")
    def test_scheduled_logic_with_notification_and_without_late_repayment_fee(
        self,
        mock_get_overdue_repayment_notification: MagicMock,
        mock_get_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
        mock_create_postings: MagicMock,
    ):
        # expected_values
        product_name = "product_a"
        dummy_amount = Decimal("100")
        due_principal_amount = dummy_amount
        due_interest_amount = dummy_amount
        late_repayment_fee = Decimal("0")
        effective_datetime = DEFAULT_DATETIME
        balances_observation = SentinelBalancesObservation("overdue")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: balances_observation,
            }
        )
        principal_postings = [SentinelPosting(f"principal_{i}") for i in range(2)]
        interest_postings = [SentinelPosting(f"interest_{i}") for i in range(2)]

        # construct expected result
        expected_instructions = [
            CustomInstruction(
                postings=[*principal_postings, *interest_postings],  # type: ignore
                override_all_restrictions=True,
                instruction_details=sentinel_instruction_details,
            )
        ]
        expected_notification_details = {
            "account_id": str(mock_vault.account_id),
            "overdue_principal": str(due_principal_amount),
            "overdue_interest": str(due_interest_amount),
            "late_repayment_fee": str(late_repayment_fee),
            "overdue_date": str(effective_datetime),
        }
        expected_notifications: list[AccountNotificationDirective] = [
            AccountNotificationDirective(
                notification_type=overdue.notification_type(product_name),
                notification_details=expected_notification_details,
            )
        ]

        # construct mocks

        mock_create_postings.side_effect = [principal_postings, interest_postings]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_standard_instruction_details.return_value = sentinel_instruction_details
        mock_get_balance_at_coordinates.return_value = dummy_amount
        mock_get_overdue_repayment_notification.return_value = expected_notifications

        # run function
        result_instructions, result_notifications = overdue.schedule_logic(
            vault=mock_vault,
            account_type=product_name,
            hook_arguments=ScheduledEventHookArguments(
                event_type=sentinel.event_type,
                effective_datetime=effective_datetime,
            ),
        )

        # validate results
        self.assertListEqual(result_instructions, expected_instructions)
        self.assertListEqual(result_notifications, expected_notifications)

        mock_get_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.balances_overdue,
                    address=overdue.lending_addresses.PRINCIPAL_DUE,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=sentinel.balances_overdue,
                    address=overdue.lending_addresses.INTEREST_DUE,
                    denomination=sentinel.denomination,
                ),
            ]
        )
        mock_get_overdue_repayment_notification.assert_called_with(
            account_id=mock_vault.account_id,
            product_name=product_name,
            effective_datetime=effective_datetime,
            overdue_principal_amount=due_principal_amount,
            overdue_interest_amount=due_interest_amount,
            late_repayment_fee=late_repayment_fee,
        )


class ScheduleEventsTest(OverdueTest):
    def test_overdue_event_types(self):
        # run function
        event_types = overdue.event_types(product_name="product_a")
        # validate results
        self.assertListEqual(
            event_types,
            [
                SmartContractEventType(
                    name="CHECK_OVERDUE",
                    scheduler_tag_ids=["PRODUCT_A_CHECK_OVERDUE_AST"],
                )
            ],
        )

    def test_overdue_supervisor_event_types(self):
        result = overdue.supervisor_event_types(product_name="product_a")
        self.assertListEqual(
            result,
            [
                SupervisorContractEventType(
                    name="CHECK_OVERDUE",
                    scheduler_tag_ids=["PRODUCT_A_CHECK_OVERDUE_AST"],
                )
            ],
        )

    @patch.object(overdue.utils, "get_schedule_expression_from_parameters")
    @patch.object(overdue.utils, "get_parameter")
    def test_overdue_check_after_specified_days_after_due_calculation(
        self,
        mock_get_parameter: MagicMock,
        mock_get_schedule_expression_from_parameters: MagicMock,
    ):
        # expected values
        due_calc_dt = datetime(2020, 1, 2, 3, 4, 5, tzinfo=ZoneInfo("UTC"))
        sched_expr = SentinelScheduleExpression("overdue")

        # construct mocks
        mock_vault = sentinel.vault
        mock_get_schedule_expression_from_parameters.return_value = sched_expr
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"repayment_period": 7}
        )
        # construct expected result
        expected = {
            overdue.CHECK_OVERDUE_EVENT: ScheduledEvent(
                start_datetime=due_calc_dt.replace(hour=0, minute=0, second=0)
                + relativedelta(days=7),
                expression=sched_expr,
                skip=False,
            )
        }
        # run function
        scheduled_events = overdue.scheduled_events(
            vault=mock_vault,
            first_due_amount_calculation_datetime=due_calc_dt,
        )
        # validate results

        self.assertDictEqual(scheduled_events, expected)
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=mock_vault,
            parameter_prefix="check_overdue",
            day=9,
            month=None,
            year=None,
        )

    @patch.object(overdue.utils, "get_schedule_expression_from_parameters")
    @patch.object(overdue.utils, "get_parameter")
    def test_overdue_check_after_specified_days_after_due_calculation_skip(
        self,
        mock_get_parameter: MagicMock,
        mock_get_schedule_expression_from_parameters: MagicMock,
    ):
        # expected values
        due_calc_dt = datetime(2020, 1, 2, 3, 4, 5, tzinfo=ZoneInfo("UTC"))
        sched_expr = SentinelScheduleExpression("overdue")
        # construct mocks
        mock_vault = sentinel.vault
        mock_get_schedule_expression_from_parameters.return_value = sched_expr
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"repayment_period": 7}
        )
        # construct expected result
        expected = {
            overdue.CHECK_OVERDUE_EVENT: ScheduledEvent(
                start_datetime=due_calc_dt.replace(hour=0, minute=0, second=0)
                + relativedelta(days=7),
                expression=sched_expr,
                skip=True,
            )
        }
        # run function
        scheduled_events = overdue.scheduled_events(
            vault=mock_vault, first_due_amount_calculation_datetime=due_calc_dt, skip=True
        )

        # validate results
        self.assertDictEqual(scheduled_events, expected)
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=mock_vault,
            parameter_prefix="check_overdue",
            day=9,
            month=None,
            year=None,
        )

    @patch.object(overdue.utils, "get_schedule_expression_from_parameters")
    @patch.object(overdue.utils, "get_parameter")
    def test_overdue_check_after_specified_days_after_due_calculation_one_off(
        self,
        mock_get_parameter: MagicMock,
        mock_get_schedule_expression_from_parameters: MagicMock,
    ):
        # expected values
        due_calc_dt = datetime(2020, 1, 2, 3, 4, 5, tzinfo=ZoneInfo("UTC"))
        sched_expr = SentinelScheduleExpression("overdue")
        # construct mocks
        mock_vault = sentinel.vault
        mock_get_schedule_expression_from_parameters.return_value = sched_expr
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"repayment_period": 7}
        )
        # construct expected result
        expected = {
            overdue.CHECK_OVERDUE_EVENT: ScheduledEvent(
                start_datetime=due_calc_dt.replace(hour=0, minute=0, second=0)
                + relativedelta(days=7),
                expression=sched_expr,
                skip=False,
            )
        }
        # run function
        scheduled_events = overdue.scheduled_events(
            vault=mock_vault, first_due_amount_calculation_datetime=due_calc_dt, is_one_off=True
        )

        # validate results
        self.assertDictEqual(scheduled_events, expected)
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=mock_vault,
            parameter_prefix="check_overdue",
            day=9,
            month=1,
            year=2020,
        )


class OverdueHelperTest(OverdueTest):
    def test_get_overdue_datetime(self):
        # expected values
        notification_period = 2
        repayment_period = 2
        due_amount_notification_datetime = datetime(2020, 2, 4, 3, 4, 5, tzinfo=ZoneInfo("UTC"))

        # construct expected result
        # expected_overdue_datetime = due_amount_notification_datetime
        # + repayment_period + notification_period
        # hour minute second is not considered and will remain the same
        expected_due_amount_notification_datetime = datetime(
            2020, 2, 8, 3, 4, 5, tzinfo=ZoneInfo("UTC")
        )

        # run function
        next_due_amount_notification_datetime = overdue.get_overdue_datetime(
            due_amount_notification_datetime=due_amount_notification_datetime,
            repayment_period=repayment_period,
            notification_period=notification_period,
        )

        # validate results
        self.assertEqual(
            next_due_amount_notification_datetime, expected_due_amount_notification_datetime
        )


class GetParametersTest(OverdueTest):
    @patch.object(overdue.utils, "get_parameter")
    def test_get_repayment_period_parameter(self, mock_get_parameter: MagicMock):
        repayment_period_parameter = 100

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={overdue.PARAM_REPAYMENT_PERIOD: repayment_period_parameter},
        )

        result = overdue.get_repayment_period_parameter(vault=sentinel.vault)

        self.assertEqual(
            repayment_period_parameter,
            result,
        )

    @patch.object(overdue, "get_repayment_period_parameter")
    def test_get_next_overdue_derived_parameter(
        self, mock_get_repayment_period_parameter: MagicMock
    ):
        mock_get_repayment_period_parameter.return_value = 5
        previous_event = DEFAULT_DATETIME - relativedelta(months=1)
        expected = previous_event + relativedelta(days=5)

        self.assertEqual(
            overdue.get_next_overdue_derived_parameter(
                vault=sentinel.vault,
                previous_due_amount_calculation_datetime=previous_event,
            ),
            expected,
        )
