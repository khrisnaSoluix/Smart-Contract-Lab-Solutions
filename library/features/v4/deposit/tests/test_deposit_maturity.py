# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from unittest.mock import MagicMock, call, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.v4.deposit.deposit_maturity as deposit_maturity
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import RejectionReason

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DATETIME,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    AccountNotificationDirective,
    CalendarEvent,
    Rejection,
    ScheduledEvent,
    SmartContractEventType,
    UpdateAccountEventTypeDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelScheduleExpression,
    SentinelUpdateAccountEventTypeDirective,
)

PUBLIC_HOLIDAYS = "PUBLIC_HOLIDAYS"
DEFAULT_CALENDAR_EVENT = CalendarEvent(
    id="TEST",
    calendar_id=PUBLIC_HOLIDAYS,
    start_datetime=datetime(2020, 9, 5, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
    end_datetime=datetime(2020, 9, 6, 23, 23, 59, tzinfo=ZoneInfo("UTC")),
)
PRODUCT_NAME = "TEST_PRODUCT"


class DepositMaturityGeneralTest(FeatureTest):
    def test_notification_type_at_account_maturity(self):
        result = deposit_maturity.notification_type_at_account_maturity(product_name=PRODUCT_NAME)

        self.assertEqual(result, "TEST_PRODUCT_ACCOUNT_MATURITY")

    def test_notification_type_maturity_notice_period(self):
        result = deposit_maturity.notification_type_notify_upcoming_maturity(
            product_name=PRODUCT_NAME
        )

        self.assertEqual(result, "TEST_PRODUCT_NOTIFY_UPCOMING_MATURITY")

    def test_event_types(self):
        expected_schedule_tag = [
            "TEST_PRODUCT_ACCOUNT_MATURITY_AST",
            "TEST_PRODUCT_NOTIFY_UPCOMING_MATURITY_AST",
        ]
        expected_event_type: list[SmartContractEventType] = [
            SmartContractEventType(
                name=deposit_maturity.ACCOUNT_MATURITY_EVENT,
                scheduler_tag_ids=[expected_schedule_tag[0]],
            ),
            SmartContractEventType(
                name=deposit_maturity.NOTIFY_UPCOMING_MATURITY_EVENT,
                scheduler_tag_ids=[expected_schedule_tag[1]],
            ),
        ]

        result = deposit_maturity.event_types(product_name=PRODUCT_NAME)

        self.assertListEqual(result, expected_event_type)


class ScheduleEventTest(FeatureTest):
    def setUp(self) -> None:
        self.maturity_notice_period = 2

        # get_parameter
        patch_get_parameter = patch.object(deposit_maturity.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={deposit_maturity.PARAM_MATURITY_NOTICE_PERIOD: self.maturity_notice_period}
        )

        # get account maturity without calendars
        patch_get_maturity_datetime_without_calendars = patch.object(
            deposit_maturity, "get_maturity_datetime_without_calendars"
        )
        self.mock_get_maturity_datetime_without_calendars = (
            patch_get_maturity_datetime_without_calendars.start()
        )
        self.mock_get_maturity_datetime_without_calendars.return_value = DEFAULT_DATETIME

        # get account maturity with calendars
        patch_get_maturity_datetime_with_calendars = patch.object(
            deposit_maturity, "get_maturity_datetime_with_calendars"
        )
        self.mock_get_maturity_datetime_with_calendars = (
            patch_get_maturity_datetime_with_calendars.start()
        )
        self.mock_get_maturity_datetime_with_calendars.return_value = DEFAULT_DATETIME

        # get one off schedule expression
        patch_one_off_schedule_expression = patch.object(
            deposit_maturity.utils, "one_off_schedule_expression"
        )
        self.mock_one_off_schedule_expression = patch_one_off_schedule_expression.start()
        self.mock_one_off_schedule_expression.side_effect = [
            SentinelScheduleExpression("account_maturity"),
            SentinelScheduleExpression("account_notify"),
        ]

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_scheduled_events(self):
        expected_notify_maturity_datetime = DEFAULT_DATETIME - relativedelta(
            days=self.maturity_notice_period
        )
        notify_maturity_scheduled_event = ScheduledEvent(
            start_datetime=expected_notify_maturity_datetime - relativedelta(seconds=1),
            expression=SentinelScheduleExpression("account_notify"),
            end_datetime=expected_notify_maturity_datetime,
        )
        maturity_scheduled_event = ScheduledEvent(
            start_datetime=DEFAULT_DATETIME - relativedelta(seconds=1),
            expression=SentinelScheduleExpression("account_maturity"),
            end_datetime=DEFAULT_DATETIME,
        )

        expected_scheduled_events = {
            deposit_maturity.ACCOUNT_MATURITY_EVENT: maturity_scheduled_event,
            deposit_maturity.NOTIFY_UPCOMING_MATURITY_EVENT: notify_maturity_scheduled_event,
        }

        result = deposit_maturity.scheduled_events(vault=sentinel.mock_vault)

        self.assertDictEqual(result, expected_scheduled_events)
        self.mock_one_off_schedule_expression.assert_has_calls(
            [
                call(schedule_datetime=DEFAULT_DATETIME),
                call(schedule_datetime=expected_notify_maturity_datetime),
            ]
        )
        self.mock_get_maturity_datetime_without_calendars(vault=sentinel.mock_vault)
        self.mock_get_maturity_datetime_without_calendars(
            vault=sentinel.mock_vault, maturity_datetime=DEFAULT_DATETIME
        )

    def test_update_account_maturity_schedule(self):
        self.mock_one_off_schedule_expression.return_value = SentinelScheduleExpression(
            "account_maturity"
        )
        expected_account_event_update = UpdateAccountEventTypeDirective(
            event_type=deposit_maturity.ACCOUNT_MATURITY_EVENT,
            expression=SentinelScheduleExpression("account_maturity"),
            end_datetime=DEFAULT_DATETIME,
        )
        result = deposit_maturity._update_account_maturity_schedule(
            maturity_datetime=DEFAULT_DATETIME
        )
        self.assertEqual(result, expected_account_event_update)
        self.mock_one_off_schedule_expression.assert_called_once_with(
            schedule_datetime=DEFAULT_DATETIME
        )


class NotificationAtAccountMaturityTest(FeatureTest):
    def test_handle_account_maturity_event_when_schedules_to_skip_are_absent(self):
        expected_notification_details = {
            "account_id": sentinel.account_id,
            "account_maturity_datetime": str(DEFAULT_DATETIME),
            "reason": "Account has now reached maturity",
        }
        expected_notification_type = "TEST_PRODUCT_ACCOUNT_MATURITY"
        expected_notification = [
            AccountNotificationDirective(
                notification_type=expected_notification_type,
                notification_details=expected_notification_details,
            )
        ]

        result = deposit_maturity.handle_account_maturity_event(
            product_name=PRODUCT_NAME,
            account_id=sentinel.account_id,
            effective_datetime=DEFAULT_DATETIME,
        )

        self.assertTupleEqual(result, (expected_notification, []))

    @patch.object(deposit_maturity, "_handle_skipping_schedules_indefinitely_at_maturity")
    def test_handle_account_maturity_event_when_schedules_to_skip_are_present(
        self, mock_handle_skipping_schedules_indefinitely_at_maturity: MagicMock
    ):
        expected_scheduled_to_skip_indefinitely_ = [
            SentinelUpdateAccountEventTypeDirective("interest_accrual"),
            SentinelUpdateAccountEventTypeDirective("interest_application"),
        ]
        mock_handle_skipping_schedules_indefinitely_at_maturity.return_value = (
            expected_scheduled_to_skip_indefinitely_
        )
        expected_notification_details = {
            "account_id": sentinel.account_id,
            "account_maturity_datetime": str(DEFAULT_DATETIME),
            "reason": "Account has now reached maturity",
        }
        expected_notification_type = "TEST_PRODUCT_ACCOUNT_MATURITY"
        expected_notification = [
            AccountNotificationDirective(
                notification_type=expected_notification_type,
                notification_details=expected_notification_details,
            )
        ]

        result = deposit_maturity.handle_account_maturity_event(
            product_name=PRODUCT_NAME,
            account_id=sentinel.account_id,
            effective_datetime=DEFAULT_DATETIME,
            schedules_to_skip_indefinitely=["TEST_SCHEDULE"],
        )

        self.assertTupleEqual(
            result, (expected_notification, expected_scheduled_to_skip_indefinitely_)
        )


class NotificationBeforeMaturityTest(FeatureTest):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = self.create_mock()

        # get account maturity without calendars
        patch_get_maturity_datetime_without_calendars = patch.object(
            deposit_maturity, "get_maturity_datetime_without_calendars"
        )
        self.mock_get_maturity_datetime_without_calendars = (
            patch_get_maturity_datetime_without_calendars.start()
        )
        self.mock_get_maturity_datetime_without_calendars.return_value = DEFAULT_DATETIME

        # get account maturity with calendars
        patch_get_maturity_datetime_with_calendars = patch.object(
            deposit_maturity, "get_maturity_datetime_with_calendars"
        )
        self.mock_get_maturity_datetime_with_calendars = (
            patch_get_maturity_datetime_with_calendars.start()
        )
        self.mock_get_maturity_datetime_with_calendars.return_value = DEFAULT_DATETIME

        # update account maturity schedule
        patch_update_account_maturity_schedule = patch.object(
            deposit_maturity, "_update_account_maturity_schedule"
        )
        self.mock_update_account_maturity_schedule = patch_update_account_maturity_schedule.start()
        self.mock_update_account_maturity_schedule.return_value = (
            SentinelUpdateAccountEventTypeDirective("account_maturity")
        )

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_handle_notification_when_mature_datetime_is_not_extended_due_to_holiday(self):
        expected_notification_details = {
            "account_id": self.mock_vault.account_id,
            "account_maturity_datetime": str(DEFAULT_DATETIME),
        }
        expected_notification = [
            AccountNotificationDirective(
                notification_type="TEST_PRODUCT_NOTIFY_UPCOMING_MATURITY",
                notification_details=expected_notification_details,
            )
        ]

        result = deposit_maturity.handle_notify_upcoming_maturity_event(
            vault=self.mock_vault,
            product_name=PRODUCT_NAME,
        )

        self.assertTupleEqual(result, (expected_notification, []))
        self.mock_get_maturity_datetime_without_calendars(vault=self.mock_vault)
        self.mock_get_maturity_datetime_with_calendars(
            vault=self.mock_vault, maturity_datetime=DEFAULT_DATETIME
        )

    def test_handle_notification_when_mature_datetime_is_extended_due_to_holiday(self):
        expected_holiday_extended_mature_datetime = DEFAULT_DATETIME + relativedelta(days=2)
        expected_updated_maturity_schedule = [
            SentinelUpdateAccountEventTypeDirective("account_maturity")
        ]
        self.mock_get_maturity_datetime_with_calendars.return_value = (
            expected_holiday_extended_mature_datetime
        )
        expected_notification_details = {
            "account_id": self.mock_vault.account_id,
            "account_maturity_datetime": str(expected_holiday_extended_mature_datetime),
        }
        expected_notification = [
            AccountNotificationDirective(
                notification_type="TEST_PRODUCT_NOTIFY_UPCOMING_MATURITY",
                notification_details=expected_notification_details,
            )
        ]

        result = deposit_maturity.handle_notify_upcoming_maturity_event(
            vault=self.mock_vault,
            product_name=PRODUCT_NAME,
        )

        self.assertTupleEqual(result, (expected_notification, expected_updated_maturity_schedule))
        self.mock_get_maturity_datetime_without_calendars(vault=self.mock_vault)
        self.mock_get_maturity_datetime_with_calendars(
            vault=self.mock_vault, maturity_datetime=DEFAULT_DATETIME
        )


class ValidatePostingsTest(FeatureTest):
    def setUp(self) -> None:
        # get account maturity without calendars
        patch_get_maturity_datetime_without_calendars = patch.object(
            deposit_maturity, "get_maturity_datetime_without_calendars"
        )
        self.mock_get_maturity_datetime_without_calendars = (
            patch_get_maturity_datetime_without_calendars.start()
        )
        self.mock_get_maturity_datetime_without_calendars.return_value = DEFAULT_DATETIME

        # get account maturity with calendars
        patch_get_maturity_datetime_with_calendars = patch.object(
            deposit_maturity, "get_maturity_datetime_with_calendars"
        )
        self.mock_get_maturity_datetime_with_calendars = (
            patch_get_maturity_datetime_with_calendars.start()
        )
        self.mock_get_maturity_datetime_with_calendars.return_value = DEFAULT_DATETIME

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_no_rejections_raised_when_posting_before_maturity(self):
        result = deposit_maturity.validate_postings(
            vault=sentinel.mock_vault,
            effective_datetime=DEFAULT_DATETIME - relativedelta(seconds=1),
        )

        self.assertIsNone(result)
        self.mock_get_maturity_datetime_without_calendars(vault=sentinel.mock_vault)
        self.mock_get_maturity_datetime_with_calendars(
            vault=sentinel.mock_vault, maturity_datetime=DEFAULT_DATETIME
        )

    def test_no_rejections_raised_when_posting_at_maturity(self):
        expected_rejection = Rejection(
            message="No transactions are allowed at or after account maturity",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        result = deposit_maturity.validate_postings(
            vault=sentinel.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
        )

        self.assertEqual(result, expected_rejection)
        self.mock_get_maturity_datetime_without_calendars(vault=sentinel.mock_vault)
        self.mock_get_maturity_datetime_with_calendars(
            vault=sentinel.mock_vault, maturity_datetime=DEFAULT_DATETIME
        )

    def test_rejections_raised_when_posting_after_maturity(self):
        expected_rejection = Rejection(
            message="No transactions are allowed at or after account maturity",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        result = deposit_maturity.validate_postings(
            vault=sentinel.mock_vault,
            effective_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
        )

        self.assertEqual(result, expected_rejection)
        self.mock_get_maturity_datetime_without_calendars(vault=sentinel.mock_vault)
        self.mock_get_maturity_datetime_with_calendars(
            vault=sentinel.mock_vault, maturity_datetime=DEFAULT_DATETIME
        )


class AccountMaturityDatetimeTest(FeatureTest):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = self.create_mock(creation_date=DEFAULT_DATETIME)

        # get_parameter
        patch_get_parameter = patch.object(deposit_maturity.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={deposit_maturity.PARAM_DESIRED_MATURITY_DATE: None}
        )

        # get term
        patch_get_term_parameter = patch.object(
            deposit_maturity.deposit_parameters, "get_term_parameter"
        )
        self.mock_get_term_parameter = patch_get_term_parameter.start()
        self.mock_get_term_parameter.return_value = 10

        # get term unit
        patch_get_term_unit_parameter = patch.object(
            deposit_maturity.deposit_parameters, "get_term_unit_parameter"
        )
        self.mock_get_term_unit_parameter = patch_get_term_unit_parameter.start()
        self.mock_get_term_unit_parameter.return_value = "days"

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_account_maturity_when_desired_maturity_date_is_absent_and_term_is_days(self):
        expected_maturity_datetime = datetime(2019, 1, 12, tzinfo=ZoneInfo("UTC"))

        result = deposit_maturity.get_maturity_datetime_without_calendars(
            vault=self.mock_vault,
        )

        self.mock_get_term_parameter.assert_called_once_with(vault=self.mock_vault)
        self.mock_get_term_unit_parameter.assert_called_once_with(vault=self.mock_vault)
        self.assertEqual(result, expected_maturity_datetime)

    def test_account_maturity_when_desired_maturity_date_is_absent_and_term_is_months(self):
        expected_maturity_datetime = datetime(2019, 11, 2, tzinfo=ZoneInfo("UTC"))
        self.mock_get_term_unit_parameter.return_value = "months"

        result = deposit_maturity.get_maturity_datetime_without_calendars(
            vault=self.mock_vault,
        )

        self.mock_get_term_parameter.assert_called_once_with(vault=self.mock_vault)
        self.mock_get_term_unit_parameter.assert_called_once_with(vault=self.mock_vault)
        self.assertEqual(result, expected_maturity_datetime)

    def test_account_maturity_when_desired_maturity_date_is_after_account_creation(self):
        test_desired_maturity_datetime = datetime(2019, 1, 18, tzinfo=ZoneInfo("UTC"))
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                deposit_maturity.PARAM_DESIRED_MATURITY_DATE: test_desired_maturity_datetime
            }
        )
        expected_maturity_datetime = datetime(2019, 1, 19, tzinfo=ZoneInfo("UTC"))

        result = deposit_maturity.get_maturity_datetime_without_calendars(
            vault=self.mock_vault,
        )

        self.assertEqual(result, expected_maturity_datetime)

    def test_account_maturity_when_desired_maturity_date_is_before_account_creation(self):
        test_desired_maturity_datetime = datetime(2018, 1, 18, tzinfo=ZoneInfo("UTC"))
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                deposit_maturity.PARAM_DESIRED_MATURITY_DATE: test_desired_maturity_datetime
            }
        )
        expected_maturity_datetime = datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC"))

        result = deposit_maturity.get_maturity_datetime_without_calendars(
            vault=self.mock_vault,
        )

        self.assertEqual(result, expected_maturity_datetime)


class MaturityDatetimeWithCalendarsTest(FeatureTest):
    @patch.object(deposit_maturity.utils, "get_next_datetime_after_calendar_events")
    def test_get_maturity_datetime_updated_with_calendar_events(
        self, mock_get_next_datetime_after_calendar_events: MagicMock
    ):
        mock_get_next_datetime_after_calendar_events.return_value = DEFAULT_DATETIME

        result = deposit_maturity.get_maturity_datetime_with_calendars(
            vault=self.create_mock(calendar_events=[DEFAULT_CALENDAR_EVENT]),
            maturity_datetime=DEFAULT_DATETIME,
        )

        mock_get_next_datetime_after_calendar_events.assert_called_once_with(
            effective_datetime=DEFAULT_DATETIME, calendar_events=[DEFAULT_CALENDAR_EVENT]
        )
        self.assertEqual(result, DEFAULT_DATETIME)


class HandleDisableScheduleTest(FeatureTest):
    @patch.object(deposit_maturity.utils, "update_schedules_to_skip_indefinitely")
    def test_handle_disable_schedules_at_maturity(
        self, mock_update_schedules_to_skip_indefinitely: MagicMock
    ):
        mock_update_schedules_to_skip_indefinitely.return_value = (
            SentinelUpdateAccountEventTypeDirective("interest_accrual")
        )
        result = deposit_maturity._handle_skipping_schedules_indefinitely_at_maturity(
            schedules_to_skip_indefinitely=["EVENT_1", "EVENT_2"]
        )

        mock_update_schedules_to_skip_indefinitely.assert_called_once_with(
            schedules=["EVENT_1", "EVENT_2"]
        )
        self.assertEqual(result, SentinelUpdateAccountEventTypeDirective("interest_accrual"))


class HandleTermParameterChangeTest(FeatureTest):
    def setUp(self) -> None:
        patch_get_deposit_maturity_datetimes = patch.object(
            deposit_maturity,
            "get_account_maturity_and_notify_upcoming_maturity_datetimes",
        )
        self.mock_get_deposit_maturity_datetimes = patch_get_deposit_maturity_datetimes.start()
        self.mock_get_deposit_maturity_datetimes.return_value = (
            DEFAULT_DATETIME,
            DEFAULT_DATETIME - relativedelta(days=2),
        )

        patch_one_off_schedule_expression = patch.object(
            deposit_maturity.utils, "one_off_schedule_expression"
        )
        self.mock_one_off_schedule_expression = patch_one_off_schedule_expression.start()
        self.mock_one_off_schedule_expression.side_effect = [
            SentinelScheduleExpression("account_maturity"),
            SentinelScheduleExpression("account_notify"),
        ]
        return super().setUp()

    def test_handle_term_parameter_change(self):
        expected_result = [
            UpdateAccountEventTypeDirective(
                event_type=deposit_maturity.ACCOUNT_MATURITY_EVENT,
                expression=SentinelScheduleExpression("account_maturity"),
                end_datetime=DEFAULT_DATETIME,
            ),
            UpdateAccountEventTypeDirective(
                event_type=deposit_maturity.NOTIFY_UPCOMING_MATURITY_EVENT,
                expression=SentinelScheduleExpression("account_notify"),
                end_datetime=DEFAULT_DATETIME - relativedelta(days=2),
            ),
        ]

        result = deposit_maturity.handle_term_parameter_change(vault=sentinel.vault)
        self.assertEqual(result, expected_result)
        self.mock_get_deposit_maturity_datetimes.assert_called_once_with(vault=sentinel.vault)
        self.mock_one_off_schedule_expression.assert_has_calls(
            [
                call(schedule_datetime=DEFAULT_DATETIME),
                call(schedule_datetime=DEFAULT_DATETIME - relativedelta(days=2)),
            ]
        )


class ValidateTermParameterChangeTest(FeatureTest):
    def setUp(self) -> None:
        patch_get_desired_maturity_datetime = patch.object(
            deposit_maturity, "get_desired_maturity_datetime"
        )
        self.mock_get_desired_maturity_datetime = patch_get_desired_maturity_datetime.start()
        self.mock_get_desired_maturity_datetime.return_value = None

        patch_get_parameter = patch.object(deposit_maturity.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                deposit_maturity.deposit_parameters.PARAM_TERM: 10,  # current term
            }
        )

        patch_get_maturity_datetime_from_term_and_unit = patch.object(
            deposit_maturity,
            "get_maturity_datetime_from_term_and_unit",
        )
        self.mock_get_maturity_datetime_from_term_and_unit = (
            patch_get_maturity_datetime_from_term_and_unit.start()
        )
        self.mock_get_maturity_datetime_from_term_and_unit.return_value = (
            sentinel.maturity_datetime_without_calendars
        )

        patch_get_maturity_datetime_with_calendars = patch.object(
            deposit_maturity,
            "get_maturity_datetime_with_calendars",
        )
        self.mock_get_maturity_datetime_with_calendars = (
            patch_get_maturity_datetime_with_calendars.start()
        )
        self.mock_get_maturity_datetime_with_calendars.return_value = sentinel.maturity_datetime

        patch_get_notify_upcoming_maturity_datetime = patch.object(
            deposit_maturity,
            "_get_notify_upcoming_maturity_datetime",
        )
        self.mock_get_notify_upcoming_maturity_datetime = (
            patch_get_notify_upcoming_maturity_datetime.start()
        )
        # self.mock_get_notify_upcoming_maturity_datetime.return_value = None
        return super().setUp()

    def test_term_changed_with_desired_maturity_datetime_set_raises_rejection(self):
        self.mock_get_desired_maturity_datetime.return_value = sentinel.desired_datetime
        expected_result = Rejection(
            message="Term length cannot be changed if the desired maturity datetime is set.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        result = deposit_maturity.validate_term_parameter_change(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME, proposed_term_value=11
        )
        self.assertEqual(result, expected_result)

        self.mock_get_desired_maturity_datetime.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )
        self.mock_get_maturity_datetime_from_term_and_unit.assert_not_called()
        self.mock_get_maturity_datetime_with_calendars.assert_not_called()
        self.mock_get_notify_upcoming_maturity_datetime.assert_not_called()

    def test_term_changed_to_longer_term_is_accepted_and_returns_none(self):
        result = deposit_maturity.validate_term_parameter_change(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME, proposed_term_value=12
        )
        self.assertIsNone(result)

        self.mock_get_desired_maturity_datetime.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )
        self.mock_get_maturity_datetime_from_term_and_unit.assert_not_called()
        self.mock_get_maturity_datetime_with_calendars.assert_not_called()
        self.mock_get_notify_upcoming_maturity_datetime.assert_not_called()

    def test_term_changed_with_notice_period_starting_in_the_past_rejected(self):
        self.mock_get_notify_upcoming_maturity_datetime.return_value = (
            DEFAULT_DATETIME - relativedelta(days=2)
        )
        expected_result = Rejection(
            message="Term length cannot be changed such that the maturity notification"
            " period starts in the past.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        result = deposit_maturity.validate_term_parameter_change(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME, proposed_term_value=8
        )
        self.assertEqual(result, expected_result)

        self.mock_get_desired_maturity_datetime.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )
        self.mock_get_maturity_datetime_from_term_and_unit.assert_called_once_with(
            vault=sentinel.vault, term=8
        )
        self.mock_get_maturity_datetime_with_calendars.assert_called_once_with(
            vault=sentinel.vault, maturity_datetime=sentinel.maturity_datetime_without_calendars
        )
        self.mock_get_notify_upcoming_maturity_datetime.assert_called_once_with(
            vault=sentinel.vault, maturity_datetime=sentinel.maturity_datetime
        )

    def test_term_changed_to_valid_shorter_term_is_accepted_and_returns_none(self):
        self.mock_get_notify_upcoming_maturity_datetime.return_value = (
            DEFAULT_DATETIME + relativedelta(days=2)
        )

        result = deposit_maturity.validate_term_parameter_change(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME, proposed_term_value=8
        )
        self.assertIsNone(result)

        self.mock_get_desired_maturity_datetime.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )
        self.mock_get_maturity_datetime_from_term_and_unit.assert_called_once_with(
            vault=sentinel.vault, term=8
        )
        self.mock_get_maturity_datetime_with_calendars.assert_called_once_with(
            vault=sentinel.vault, maturity_datetime=sentinel.maturity_datetime_without_calendars
        )
        self.mock_get_notify_upcoming_maturity_datetime.assert_called_once_with(
            vault=sentinel.vault, maturity_datetime=sentinel.maturity_datetime
        )
