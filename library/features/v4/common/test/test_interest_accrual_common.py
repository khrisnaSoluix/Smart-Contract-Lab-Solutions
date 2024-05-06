# standard libs
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.v4.common.interest_accrual_common as interest_accrual_common

# contracts api
from contracts_api import ScheduleSkip

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    SmartContractEventType,
    UpdateAccountEventTypeDirective,
)

DEFAULT_DATE = datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))


class InterestAccrualTestCommon(FeatureTest):
    maxDiff = None


class InterestAccrualScheduleTest(InterestAccrualTestCommon):
    def test_interest_accrual_event_types(self):
        event_types = interest_accrual_common.event_types(product_name="product_a")
        self.assertListEqual(
            event_types,
            [
                SmartContractEventType(
                    name=interest_accrual_common.ACCRUAL_EVENT,
                    scheduler_tag_ids=[f"PRODUCT_A_{interest_accrual_common.ACCRUAL_EVENT}_AST"],
                )
            ],
        )

    @patch.object(interest_accrual_common.utils, "daily_scheduled_event")
    def test_interest_accrual_scheduled_event_use_skip_default(
        self, mock_daily_scheduled_event: MagicMock
    ):
        mock_vault = MagicMock()
        mock_daily_scheduled_event.return_value = sentinel.daily_scheduled_event

        scheduled_events = interest_accrual_common.scheduled_events(
            vault=mock_vault, start_datetime=sentinel.start_datetime
        )

        self.assertDictEqual(
            scheduled_events,
            {interest_accrual_common.ACCRUAL_EVENT: sentinel.daily_scheduled_event},
        )
        mock_daily_scheduled_event.assert_called_once_with(
            vault=mock_vault,
            start_datetime=sentinel.start_datetime,
            parameter_prefix="interest_accrual",
            skip=False,
        )

    @patch.object(interest_accrual_common.utils, "daily_scheduled_event")
    def test_interest_accrual_scheduled_event_skip_defined(
        self, mock_daily_scheduled_event: MagicMock
    ):
        mock_vault = MagicMock()
        mock_daily_scheduled_event.return_value = sentinel.daily_scheduled_event

        scheduled_events = interest_accrual_common.scheduled_events(
            vault=mock_vault, start_datetime=sentinel.start_datetime, skip=sentinel.skip
        )

        self.assertDictEqual(
            scheduled_events,
            {interest_accrual_common.ACCRUAL_EVENT: sentinel.daily_scheduled_event},
        )
        mock_daily_scheduled_event.assert_called_once_with(
            vault=mock_vault,
            start_datetime=sentinel.start_datetime,
            parameter_prefix="interest_accrual",
            skip=sentinel.skip,
        )

    def test_update_schedule_events_skip_true(self):

        result = interest_accrual_common.update_schedule_events_skip(skip=True)

        expected = [
            UpdateAccountEventTypeDirective(
                event_type=interest_accrual_common.ACCRUAL_EVENT,
                skip=True,
            )
        ]

        self.assertListEqual(result, expected)

    def test_update_schedule_events_skip_false(self):

        result = interest_accrual_common.update_schedule_events_skip(skip=False)

        expected = [
            UpdateAccountEventTypeDirective(
                event_type=interest_accrual_common.ACCRUAL_EVENT,
                skip=False,
            )
        ]

        self.assertListEqual(result, expected)

    def test_update_schedule_events_skip_schedule_skip(self):
        schedule_skip = ScheduleSkip(end=DEFAULT_DATE)
        result = interest_accrual_common.update_schedule_events_skip(skip=schedule_skip)

        expected = [
            UpdateAccountEventTypeDirective(
                event_type=interest_accrual_common.ACCRUAL_EVENT,
                skip=schedule_skip,
            )
        ]

        self.assertListEqual(result, expected)


class CalculateDailyAccrualTest(InterestAccrualTestCommon):
    def test_calculate_daily_accrual_on_zero_effective_balance(self):
        daily_accrual = interest_accrual_common.calculate_daily_accrual(
            effective_balance=Decimal("0"),
            effective_datetime=DEFAULT_DATE,
            yearly_rate=Decimal("0.00365"),
            days_in_year="actual",
            rounding=sentinel.rounding,
            precision=sentinel.precision,
        )
        self.assertIsNone(daily_accrual)

    @patch.object(interest_accrual_common.utils, "yearly_to_daily_rate")
    @patch.object(interest_accrual_common.utils, "round_decimal")
    def test_calculate_daily_for_zero_accrual_amount(
        self, mock_round_decimal: MagicMock, mock_yearly_to_daily_rate: MagicMock
    ):

        # it doesn't really matter which of the rate or final amount yields 0
        mock_yearly_to_daily_rate.return_value = Decimal("0.5")
        mock_round_decimal.return_value = 0

        daily_accrual = interest_accrual_common.calculate_daily_accrual(
            effective_balance=Decimal("10"),
            effective_datetime=sentinel.effective_datetime,
            yearly_rate=sentinel.yearly_rate,
            days_in_year=sentinel.days_in_year,
            rounding=sentinel.rounding,
            precision=sentinel.precision,
        )
        self.assertIsNone(daily_accrual)

        # make sure this test isn't returning [] for the wrong reasons
        mock_yearly_to_daily_rate.assert_called_once_with(
            days_in_year=sentinel.days_in_year,
            yearly_rate=sentinel.yearly_rate,
            effective_date=sentinel.effective_datetime,
        )
        mock_round_decimal.assert_called_once_with(
            amount=Decimal("5"),
            decimal_places=sentinel.precision,
            rounding=sentinel.rounding,
        )

    @patch.object(interest_accrual_common.utils, "yearly_to_daily_rate")
    @patch.object(interest_accrual_common.utils, "round_decimal")
    def test_calculate_daily_for_non_zero_accrual_amount(
        self, mock_round_decimal: MagicMock, mock_yearly_to_daily_rate: MagicMock
    ):

        mock_yearly_to_daily_rate.return_value = Decimal("0.05")
        mock_round_decimal.return_value = Decimal("0.01")

        daily_accrual = interest_accrual_common.calculate_daily_accrual(
            effective_balance=Decimal("10"),
            effective_datetime=sentinel.effective_datetime,
            yearly_rate=sentinel.yearly_rate,
            days_in_year=sentinel.days_in_year,
            rounding=sentinel.rounding,
            precision=sentinel.precision,
        )
        self.assertEqual(
            daily_accrual,
            interest_accrual_common.accruals.AccrualDetail(
                amount=Decimal("0.01"),
                description="Daily interest accrued at 5.00000% on balance of 10.00",
            ),
        )


class DailyAccrualTest(InterestAccrualTestCommon):
    @patch.object(interest_accrual_common, "calculate_daily_accrual")
    def test_daily_accrual_no_accrual_required(self, mock_calculate_daily_accrual: MagicMock):
        mock_calculate_daily_accrual.return_value = None

        custom_instructions = interest_accrual_common.daily_accrual(
            customer_account=sentinel.customer_account,
            customer_address=sentinel.customer_address,
            denomination=sentinel.denomination,
            internal_account=sentinel.internal_account,
            payable=sentinel.payable,
            effective_balance=sentinel.effective_balance,
            effective_datetime=sentinel.effective_datetime,
            yearly_rate=sentinel.yearly_rate,
            days_in_year=sentinel.days_in_year,
            rounding=sentinel.rounding,
            precision=sentinel.precision,
            account_type=sentinel.account_type,
            event_type=sentinel.event_type,
        )

        self.assertListEqual(custom_instructions, [])
        mock_calculate_daily_accrual.assert_called_once_with(
            effective_balance=sentinel.effective_balance,
            effective_datetime=sentinel.effective_datetime,
            yearly_rate=sentinel.yearly_rate,
            days_in_year=sentinel.days_in_year,
            rounding=sentinel.rounding,
            precision=sentinel.precision,
        )

    @patch.object(interest_accrual_common.utils, "standard_instruction_details")
    @patch.object(interest_accrual_common.accruals, "accrual_custom_instruction")
    @patch.object(interest_accrual_common, "calculate_daily_accrual")
    def test_daily_accrual(
        self,
        mock_calculate_daily_accrual: MagicMock,
        mock_accrual_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_calculate_daily_accrual.return_value = interest_accrual_common.accruals.AccrualDetail(
            amount=sentinel.amount, description=sentinel.description
        )
        mock_accrual_custom_instruction.return_value = [sentinel.accrual_custom_instruction]
        mock_standard_instruction_details.return_value = sentinel.standard_instruction_details

        custom_instructions = interest_accrual_common.daily_accrual(
            customer_account=sentinel.customer_account,
            customer_address=sentinel.customer_address,
            denomination=sentinel.denomination,
            internal_account=sentinel.internal_account,
            payable=sentinel.payable,
            effective_balance=sentinel.effective_balance,
            effective_datetime=sentinel.effective_datetime,
            yearly_rate=sentinel.yearly_rate,
            days_in_year=sentinel.days_in_year,
            rounding=sentinel.rounding,
            precision=sentinel.precision,
            account_type=sentinel.account_type,
            event_type=sentinel.event_type,
        )

        self.assertListEqual(custom_instructions, [sentinel.accrual_custom_instruction])

        mock_accrual_custom_instruction.assert_called_once_with(
            customer_account=sentinel.customer_account,
            customer_address=sentinel.customer_address,
            denomination=sentinel.denomination,
            amount=sentinel.amount,
            internal_account=sentinel.internal_account,
            payable=sentinel.payable,
            instruction_details=sentinel.standard_instruction_details,
        )
        mock_standard_instruction_details.assert_called_once_with(
            description=sentinel.description,
            event_type=sentinel.event_type,
            gl_impacted=True,
            account_type=sentinel.account_type,
        )
