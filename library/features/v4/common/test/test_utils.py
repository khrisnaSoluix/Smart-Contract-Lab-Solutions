# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import ROUND_05UP, ROUND_FLOOR, ROUND_HALF_DOWN, ROUND_HALF_UP, Decimal
from json import dumps
from typing import Mapping
from unittest.mock import MagicMock, call, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.v4.common.utils as utils
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    Balance as _Balance,
    BalanceCoordinate,
    BalanceDefaultDict as _BalanceDefaultDict,
    BalanceTimeseries,
    CustomInstruction,
    FlagTimeseries,
    InboundAuthorisation,
    InboundHardSettlement,
    OutboundHardSettlement,
    Phase,
    Posting,
    ScheduleSkip as _ScheduleSkip,
    Transfer,
    Tside,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    ACCOUNT_ID,
    DEFAULT_DENOMINATION,
    DEFAULT_INTERNAL_ACCOUNT,
    FeatureTest,
    construct_parameter_timeseries,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    Balance,
    BalanceDefaultDict,
    CalendarEvent,
    CalendarEvents,
    EndOfMonthSchedule,
    OptionalValue,
    ParameterTimeseries,
    Rejection,
    RejectionReason,
    ScheduledEvent,
    ScheduleExpression,
    ScheduleFailover,
    ScheduleSkip,
    UnionItemValue,
    UpdateAccountEventTypeDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelEndOfMonthSchedule,
    SentinelScheduledEvent,
)

DEFAULT_DATETIME = datetime(2021, 1, 1, tzinfo=ZoneInfo("UTC"))
# it's clumsy to assert on an unbounded number of decimal places so this is used to enforce
# decimal precision on assertions when converting from yearly rate
DEFAULT_DECIMAL_PRECISION = 10
DECIMAL_ZERO = Decimal("0")


## Miscellaneous helpers
class StrToBoolTest(FeatureTest):
    def test_str_to_bool_returns_true_when_string_is_true(self):
        string = "true"
        expected_result = True
        result = utils.str_to_bool(string)
        self.assertEqual(result, expected_result)

    def test_str_to_bool_returns_true_when_string_is_mixed_case(self):
        string = "tRue"
        expected_result = True
        result = utils.str_to_bool(string)
        self.assertEqual(result, expected_result)

    def test_str_to_bool_returns_false_when_string_is_false(self):
        string = "false"
        expected_result = False
        result = utils.str_to_bool(string)
        self.assertEqual(result, expected_result)

    def test_str_to_bool_returns_false_when_string_is_empty(self):
        string = ""
        expected_result = False
        result = utils.str_to_bool(string)
        self.assertEqual(result, expected_result)

    def test_str_to_bool_returns_false_when_string_is_random_text(self):
        string = "abcd"
        expected_result = False
        result = utils.str_to_bool(string)
        self.assertEqual(result, expected_result)


class RoundDecimalTest(FeatureTest):
    positive_input = Decimal("15.456")
    negative_input = Decimal("-15.456")

    def test_round_with_round_floor(self):
        rounding = ROUND_FLOOR
        input_amount = self.positive_input
        expected_amount = Decimal("15.45")

        result = utils.round_decimal(amount=input_amount, decimal_places=2, rounding=rounding)
        self.assertEqual(result, expected_amount)

    def test_round_with_round_half_down(self):
        rounding = ROUND_HALF_DOWN
        input_amount = self.positive_input
        expected_amount = Decimal("15.46")

        result = utils.round_decimal(amount=input_amount, decimal_places=2, rounding=rounding)
        self.assertEqual(result, expected_amount)

    def test_round_with_round_half_up(self):
        rounding = ROUND_HALF_UP
        input_amount = self.positive_input
        expected_amount = Decimal("15.46")

        result = utils.round_decimal(amount=input_amount, decimal_places=2, rounding=rounding)
        self.assertEqual(result, expected_amount)

    def test_round_with_round_floor_negative(self):
        rounding = ROUND_FLOOR
        input_amount = self.negative_input
        expected_amount = Decimal("-15.46")

        result = utils.round_decimal(amount=input_amount, decimal_places=2, rounding=rounding)
        self.assertEqual(result, expected_amount)

    def test_round_with_round_half_up_negative(self):
        rounding = ROUND_HALF_UP
        input_amount = self.negative_input
        expected_amount = Decimal("-15.46")

        result = utils.round_decimal(amount=input_amount, decimal_places=2, rounding=rounding)
        self.assertEqual(result, expected_amount)

    def test_round_with_round_half_down_negative(self):
        rounding = ROUND_HALF_DOWN
        input_amount = self.negative_input
        expected_amount = Decimal("-15.46")

        result = utils.round_decimal(amount=input_amount, decimal_places=2, rounding=rounding)
        self.assertEqual(result, expected_amount)

    def test_round_with_round_05_up_negative(self):
        rounding = ROUND_05UP
        input_amount = self.negative_input
        expected_amount = Decimal("-15.46")

        result = utils.round_decimal(amount=input_amount, decimal_places=2, rounding=rounding)
        self.assertEqual(result, expected_amount)

    def test_round_with_0_dp(self):
        decimal_places = 0
        expected_amount = Decimal("15")

        result = utils.round_decimal(
            amount=Decimal("15.455555"),
            decimal_places=decimal_places,
            rounding=ROUND_HALF_UP,
        )
        self.assertEqual(result, expected_amount)

    def test_round_with_2_dp(self):
        decimal_places = 2
        expected_amount = Decimal("15.46")

        result = utils.round_decimal(
            amount=Decimal("15.455555"),
            decimal_places=decimal_places,
            rounding=ROUND_HALF_UP,
        )
        self.assertEqual(result, expected_amount)

    def test_round_with_5_dp(self):
        decimal_places = 5
        expected_amount = Decimal("15.45556")

        result = utils.round_decimal(
            amount=Decimal("15.455555"),
            decimal_places=decimal_places,
            rounding=ROUND_HALF_UP,
        )
        self.assertEqual(result, expected_amount)


class YearlyToDailyAndMonthlyRateTest(FeatureTest):
    def test_yearly_to_daily_rate_in_leap_year_with_actual_days_in_year(self):
        daily_rate = utils.yearly_to_daily_rate(
            effective_date=datetime(2020, 1, 1),
            yearly_rate=Decimal("0.0366"),
            days_in_year="actual",
        )
        self.assertEqual(daily_rate, Decimal("0.0001"))

    def test_yearly_to_daily_rate_in_regular_year_with_actual_days_in_year(self):
        daily_rate = utils.yearly_to_daily_rate(
            effective_date=datetime(2021, 1, 1),
            yearly_rate=Decimal("0.0365"),
            days_in_year="actual",
        )
        self.assertEqual(daily_rate, Decimal("0.0001"))

    def test_yearly_to_daily_rate_in_regular_year_with_366_days_in_year(self):
        daily_rate = utils.yearly_to_daily_rate(
            effective_date=datetime(2021, 1, 1),
            yearly_rate=Decimal("0.0366"),
            days_in_year="366",
        )
        self.assertEqual(daily_rate, Decimal("0.0001"))

    def test_yearly_to_daily_rate_in_regular_year_with_360_days_in_year(self):
        daily_rate = utils.yearly_to_daily_rate(
            effective_date=datetime(2021, 1, 1),
            yearly_rate=Decimal("0.0360"),
            days_in_year="360",
        )
        self.assertEqual(daily_rate, Decimal("0.0001"))

    def test_yearly_to_daily_rate_in_leap_year_with_365_days_in_year(self):
        daily_rate = utils.yearly_to_daily_rate(
            effective_date=datetime(2020, 1, 1), yearly_rate=Decimal("0.0365"), days_in_year="365"
        )
        self.assertEqual(daily_rate, Decimal("0.0001"))

    def test_yearly_to_daily_rate_in_leap_year_with_rounding(self):
        daily_rate = utils.yearly_to_daily_rate(
            effective_date=datetime(2020, 1, 1), yearly_rate=Decimal("0.0366"), days_in_year="365"
        )
        self.assertEqual(daily_rate, Decimal("0.0001002740"))

    def test_yearly_to_daily_rate_with_invalid_days_in_year_defaults_to_365(self):
        daily_rate = utils.yearly_to_daily_rate(
            effective_date=datetime(2022, 1, 1), yearly_rate=Decimal("0.0365"), days_in_year="ABC"
        )
        self.assertEqual(daily_rate, Decimal("0.0001"))

    def test_yearly_to_monthly_rate_with_rounding(self):
        result = utils.yearly_to_monthly_rate(Decimal("0.011"))

        self.assertEqual(result, Decimal("0.0009166667"))


class RemoveExponentTest(FeatureTest):
    def test_remove_exponent(self):
        expected_decimal = Decimal("5000")
        result = utils.remove_exponent(Decimal("5E+3"))
        self.assertEqual(result, expected_decimal)


class RoundedDaysBetweenTest(FeatureTest):
    def test_rounded_days_between_exact_single_day(self):
        start_date = datetime(year=2019, month=1, day=1, hour=0, minute=0, second=0)
        end_date = datetime(year=2019, month=1, day=2, hour=0, minute=0, second=0)
        expected_result = 1

        result = utils.rounded_days_between(
            start_date=start_date,
            end_date=end_date,
        )

        self.assertEqual(result, expected_result)

    def test_rounded_days_between_exact_year(self):
        start_date = datetime(year=2019, month=1, day=1, hour=0, minute=0, second=0)
        end_date = datetime(year=2020, month=1, day=1, hour=0, minute=0, second=0)
        expected_result = 365

        result = utils.rounded_days_between(
            start_date=start_date,
            end_date=end_date,
        )

        self.assertEqual(result, expected_result)

    def test_rounded_days_between_fractional_day(self):
        start_date = datetime(year=2019, month=1, day=1, hour=0, minute=0, second=0)
        end_date = datetime(year=2019, month=1, day=1, hour=0, minute=0, second=1)
        expected_result = 1

        result = utils.rounded_days_between(
            start_date=start_date,
            end_date=end_date,
        )

        self.assertEqual(result, expected_result)

    def test_rounded_days_between_fractional_multiple_days(self):
        start_date = datetime(year=2019, month=1, day=1, hour=0, minute=0, second=0)
        end_date = datetime(year=2019, month=1, day=2, hour=0, minute=0, second=1)
        expected_result = 2

        result = utils.rounded_days_between(
            start_date=start_date,
            end_date=end_date,
        )

        self.assertEqual(result, expected_result)

    def test_rounded_days_between_exact_month(self):
        start_date = datetime(year=2019, month=1, day=1, hour=0, minute=0, second=0)
        end_date = datetime(year=2019, month=2, day=1, hour=0, minute=0, second=0)
        expected_result = 31

        result = utils.rounded_days_between(
            start_date=start_date,
            end_date=end_date,
        )

        self.assertEqual(result, expected_result)

    def test_rounded_days_between_fractional_month(self):
        start_date = datetime(year=2019, month=1, day=1, hour=0, minute=0, second=0)
        end_date = datetime(year=2019, month=2, day=1, hour=5, minute=5, second=5)
        expected_result = 32

        result = utils.rounded_days_between(
            start_date=start_date,
            end_date=end_date,
        )

        self.assertEqual(result, expected_result)

    def test_rounded_days_between_fractional_month_ast(self):
        start_date = datetime(year=2019, month=2, day=1, hour=5, minute=5, second=5)
        end_date = datetime(year=2019, month=1, day=1, hour=0, minute=0, second=0)
        expected_result = -32

        result = utils.rounded_days_between(
            start_date=start_date,
            end_date=end_date,
        )

        self.assertEqual(result, expected_result)


class ValidateAmountPrecisionTest(FeatureTest):
    def test_validate_amount_precision_rejects_when_above_precision_round_up(self):
        result = utils.validate_amount_precision(Decimal("1.2346"), 3)
        self.assertEqual(result.message, "Amount 1.2346 has non-zero digits after 3 decimal places")

    def test_validate_amount_precision_rejects_when_above_precision_round_down(self):
        result = utils.validate_amount_precision(Decimal("1.2344"), 3)
        self.assertEqual(result.message, "Amount 1.2344 has non-zero digits after 3 decimal places")

    def test_validate_amount_precision_does_not_raise_when_below_precision(self):
        self.assertIsNone(utils.validate_amount_precision(Decimal("1.234"), 3))

    def test_validate_amount_precision_does_not_raise_for_zero_digits_above_precision(self):
        self.assertIsNone(utils.validate_amount_precision(Decimal("1.2340"), 3))


class CreatePostingsTest(FeatureTest):
    common_args = dict(
        debit_account=sentinel.debit_account,
        denomination=sentinel.denomination,
        credit_account=sentinel.credit_account,
        credit_address=sentinel.credit_address,
        debit_address=sentinel.debit_address,
        asset=sentinel.asset,
    )

    def test_create_postings_0_posting_amount_returns_an_empty_array(self):
        self.assertEqual(
            [],
            utils.create_postings(amount=Decimal("0"), **self.common_args),
        )

    def test_create_postings_negative_posting_amount_returns_an_empty_array(self):
        self.assertEqual(
            [],
            utils.create_postings(amount=Decimal("-1"), **self.common_args),
        )

    def test_create_postings_positive_posting_amount_returns_correct_postings(self):
        self.assertEqual(
            [
                Posting(
                    credit=True,
                    amount=Decimal("1"),
                    denomination=sentinel.denomination,
                    account_id=sentinel.credit_account,
                    account_address=sentinel.credit_address,
                    asset=sentinel.asset,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    credit=False,
                    amount=Decimal("1"),
                    denomination=sentinel.denomination,
                    account_id=sentinel.debit_account,
                    account_address=sentinel.debit_address,
                    asset=sentinel.asset,
                    phase=Phase.COMMITTED,
                ),
            ],
            utils.create_postings(amount=Decimal("1"), **self.common_args),
        )

    def test_create_postings_defaults_values_correctly(self):
        self.assertEqual(
            [
                Posting(
                    credit=True,
                    amount=Decimal("1"),
                    denomination="GBP",
                    account_id=sentinel.credit_account,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    credit=False,
                    amount=Decimal("1"),
                    denomination="GBP",
                    account_id=sentinel.debit_account,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ],
            utils.create_postings(
                amount=Decimal("1"),
                debit_account=self.common_args["debit_account"],
                credit_account=self.common_args["credit_account"],
            ),
        )


## Parameter helpers
class GetParameterTest(FeatureTest):
    parameter_timeseries = construct_parameter_timeseries(
        parameter_name_to_value_map={
            "test_parameter": "test_value",
            "test_parameter_json": dumps({"test_key": "test_value"}),
            "test_parameter_union": UnionItemValue(key="test_value"),
            "test_parameter_boolean": UnionItemValue(key="True"),
            "test_parameter_optional": OptionalValue(value="test_value"),
            "test_parameter_optional_not_set": OptionalValue(value=None),
            "test_parameter_optional_union": OptionalValue(value=UnionItemValue(key="test_value")),
            "test_parameter_optional_json": OptionalValue(value=dumps({"test_key": "test_value"})),
            "test_parameter_optional_boolean": OptionalValue(value=UnionItemValue(key="True")),
        },
        default_datetime=DEFAULT_DATETIME,
    )

    def test_get_parameter_returns_latest_value(self):
        mock_vault = self.create_mock(parameter_ts=self.parameter_timeseries)
        result = utils.get_parameter(
            vault=mock_vault,
            name="test_parameter",
        )
        self.assertEqual(result, "test_value")

    def test_get_parameter_returns_at_value(self):
        parameter_ts = self.parameter_timeseries.copy()
        previous_datetime = DEFAULT_DATETIME - relativedelta(hours=1)
        parameter_ts["test_parameter"] = ParameterTimeseries(
            [(previous_datetime, "some_old_value"), (DEFAULT_DATETIME, "test_value")]
        )
        mock_vault = self.create_mock(parameter_ts=parameter_ts)
        result = utils.get_parameter(
            vault=mock_vault, name="test_parameter", at_datetime=previous_datetime
        )
        self.assertEqual(result, "some_old_value")

    def test_get_parameter_returns_json_value(self):
        mock_vault = self.create_mock(parameter_ts=self.parameter_timeseries)
        result = utils.get_parameter(vault=mock_vault, name="test_parameter_json", is_json=True)
        self.assertEqual(result, {"test_key": "test_value"})

    def test_get_parameter_returns_union_value(self):
        mock_vault = self.create_mock(parameter_ts=self.parameter_timeseries)
        result = utils.get_parameter(vault=mock_vault, name="test_parameter_union", is_union=True)
        self.assertEqual(result, "test_value")

    def test_get_parameter_returns_boolean_value(self):
        mock_vault = self.create_mock(parameter_ts=self.parameter_timeseries)
        result = utils.get_parameter(
            vault=mock_vault, name="test_parameter_boolean", is_boolean=True
        )
        self.assertEqual(result, True)

    def test_get_parameter_returns_optional_value_when_set(self):
        mock_vault = self.create_mock(parameter_ts=self.parameter_timeseries)
        result = utils.get_parameter(
            vault=mock_vault, name="test_parameter_optional", is_optional=True
        )
        self.assertEqual(result, "test_value")

    def test_get_parameter_returns_optional_value_when_not_set(self):
        mock_vault = self.create_mock(parameter_ts=self.parameter_timeseries)
        result = utils.get_parameter(
            vault=mock_vault, name="test_parameter_optional_not_set", is_optional=True
        )
        self.assertEqual(result, None)

    def test_get_parameter_returns_optional_value_when_not_set_default_value(self):
        mock_vault = self.create_mock(parameter_ts=self.parameter_timeseries)
        result = utils.get_parameter(
            vault=mock_vault,
            name="test_parameter_optional_not_set",
            is_optional=True,
            default_value="some_value",
        )
        self.assertEqual(result, "some_value")

    def test_get_parameter_returns_optional_union_value(self):
        mock_vault = self.create_mock(parameter_ts=self.parameter_timeseries)
        result = utils.get_parameter(
            vault=mock_vault, name="test_parameter_optional_union", is_optional=True, is_union=True
        )
        self.assertEqual(result, "test_value")

    def test_get_parameter_returns_optional_json_value(self):
        mock_vault = self.create_mock(parameter_ts=self.parameter_timeseries)
        result = utils.get_parameter(
            vault=mock_vault, name="test_parameter_optional_json", is_optional=True, is_json=True
        )
        self.assertEqual(result, {"test_key": "test_value"})

    def test_get_parameter_returns_optional_boolean_value(self):
        mock_vault = self.create_mock(parameter_ts=self.parameter_timeseries)
        result = utils.get_parameter(
            vault=mock_vault,
            name="test_parameter_optional_boolean",
            is_optional=True,
            is_boolean=True,
        )
        self.assertEqual(result, True)


class HasParameterChangedTest(FeatureTest):
    def test_has_parameter_changed_returns_true_if_parameters_have_changed(self):
        old_parameters: dict[str, utils.ParameterValueTypeAlias] = {
            "interest_application_day": "25"
        }
        updated_parameters: dict[str, utils.ParameterValueTypeAlias] = {
            "interest_application_day": "21"
        }
        expected_result = True

        has_parameter_value_changed = utils.has_parameter_value_changed(
            parameter_name="interest_application_day",
            old_parameters=old_parameters,
            updated_parameters=updated_parameters,
        )

        self.assertEqual(has_parameter_value_changed, expected_result)

    def test_has_parameter_changed_returns_false_if_parameters_have_not_changed(self):
        old_parameters: dict[str, utils.ParameterValueTypeAlias] = {
            "interest_application_day": "25"
        }
        updated_parameters: dict[str, utils.ParameterValueTypeAlias] = {
            "interest_application_day": "25"
        }
        expected_result = False

        has_parameter_value_changed = utils.has_parameter_value_changed(
            parameter_name="interest_application_day",
            old_parameters=old_parameters,
            updated_parameters=updated_parameters,
        )

        self.assertEqual(has_parameter_value_changed, expected_result)

    def test_has_parameter_changed_returns_false_if_updated_parameters_not_previously_present(self):
        old_parameters: dict[str, utils.ParameterValueTypeAlias] = {
            "interest_application_day": "25"
        }
        updated_parameters: dict[str, utils.ParameterValueTypeAlias] = {"new_param": "25"}
        expected_result = False

        has_parameter_value_changed = utils.has_parameter_value_changed(
            parameter_name="interest_application_day",
            old_parameters=old_parameters,
            updated_parameters=updated_parameters,
        )

        self.assertEqual(has_parameter_value_changed, expected_result)


class AreOptionalParametersSetTest(FeatureTest):
    parameters = [
        "test_parameter_1",
        "test_parameter_2",
        "test_parameter_3",
    ]

    def test_are_optional_parameters_set_all_parameters_are_set(self):
        expected_result = True

        parameter_ts = construct_parameter_timeseries(
            {
                "test_parameter_1": OptionalValue("1"),
                "test_parameter_2": OptionalValue("2"),
                "test_parameter_3": OptionalValue("3"),
            },
            default_datetime=DEFAULT_DATETIME,
        )
        mock_vault = self.create_mock(parameter_ts=parameter_ts)

        result = utils.are_optional_parameters_set(
            vault=mock_vault,
            parameters=self.parameters,
        )
        self.assertEqual(result, expected_result)

    def test_are_optional_parameters_set_some_parameters_are_set(self):
        expected_result = False
        parameter_ts = construct_parameter_timeseries(
            {
                "test_parameter_1": OptionalValue("1"),
                "test_parameter_2": OptionalValue(),
                "test_parameter_3": OptionalValue("3"),
            },
            default_datetime=DEFAULT_DATETIME,
        )
        mock_vault = self.create_mock(parameter_ts=parameter_ts)

        result = utils.are_optional_parameters_set(
            vault=mock_vault,
            parameters=self.parameters,
        )
        self.assertEqual(result, expected_result)

    def test_are_optional_parameters_set_no_parameters_are_set(self):
        expected_result = False
        parameter_ts = construct_parameter_timeseries(
            {
                "test_parameter_1": OptionalValue(),
                "test_parameter_2": OptionalValue(),
                "test_parameter_3": OptionalValue(),
            },
            default_datetime=DEFAULT_DATETIME,
        )
        mock_vault = self.create_mock(parameter_ts=parameter_ts)

        result = utils.are_optional_parameters_set(
            vault=mock_vault,
            parameters=self.parameters,
        )
        self.assertEqual(result, expected_result)


# Flag Helpers
class IsFlagAppliedTest(FeatureTest):
    @patch.object(utils, "get_parameter")
    def test_is_flag_in_list_applied_returns_true_when_flag_is_set(
        self, mock_get_parameter: MagicMock
    ):
        mock_vault = self.create_mock(
            flags_ts={"test_flag": FlagTimeseries([(DEFAULT_DATETIME, True)])}
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"blocking_flags": ["test_flag"]}
        )

        is_flag_applied = utils.is_flag_in_list_applied(
            vault=mock_vault, parameter_name="blocking_flags"
        )
        self.assertEqual(is_flag_applied, True)

    @patch.object(utils, "get_parameter")
    def test_is_flag_in_list_applied_returns_false_when_flag_is_not_set(
        self, mock_get_parameter: MagicMock
    ):
        mock_vault = self.create_mock(
            flags_ts={"test_flag": FlagTimeseries([(DEFAULT_DATETIME, False)])}
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"blocking_flags": ["test_flag"]}
        )

        is_flag_applied = utils.is_flag_in_list_applied(
            vault=mock_vault, parameter_name="blocking_flags"
        )
        self.assertEqual(is_flag_applied, False)

    @patch.object(utils, "get_parameter")
    def test_is_flag_in_list_applied_returns_true_when_optional_date_is_used(
        self, mock_get_parameter: MagicMock
    ):
        mock_vault = self.create_mock(
            flags_ts={
                "test_flag": FlagTimeseries([(datetime(2021, 1, 2, tzinfo=ZoneInfo("UTC")), True)]),
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"blocking_flags": ["test_flag"]}
        )

        is_flag_applied = utils.is_flag_in_list_applied(
            vault=mock_vault, parameter_name="blocking_flags"
        )
        self.assertEqual(is_flag_applied, True)

    @patch.object(utils, "get_parameter")
    def test_is_flag_in_list_applied_returns_false_when_optional_date_is_used(
        self, mock_get_parameter: MagicMock
    ):
        mock_vault = self.create_mock(
            flags_ts={
                "test_flag": FlagTimeseries([(datetime(2021, 1, 2, tzinfo=ZoneInfo("UTC")), False)])
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"blocking_flags": ["test_flag"]}
        )

        is_flag_applied = utils.is_flag_in_list_applied(
            vault=mock_vault, parameter_name="blocking_flags"
        )
        self.assertEqual(is_flag_applied, False)

    def test_is_flag_in_timeseries_applied_returns_true_when_flag_is_set(self):
        is_flag_applied = utils.is_flag_in_timeseries_applied(
            flag_timeseries_iterable=[FlagTimeseries([(DEFAULT_DATETIME, True)])]
        )
        self.assertEqual(is_flag_applied, True)

    def test_is_flag_in_timeseries_applied_returns_false_when_flag_is_not_set(self):
        is_flag_applied = utils.is_flag_in_timeseries_applied(
            flag_timeseries_iterable=[FlagTimeseries([(DEFAULT_DATETIME, False)])],
        )
        self.assertEqual(is_flag_applied, False)

    def test_is_flag_in_timeseries_applied_returns_true_when_optional_date_is_used(self):
        is_flag_applied = utils.is_flag_in_timeseries_applied(
            flag_timeseries_iterable=[
                FlagTimeseries([(datetime(2021, 1, 2, tzinfo=ZoneInfo("UTC")), True)])
            ],
            effective_datetime=datetime(2021, 1, 2, tzinfo=ZoneInfo("UTC")),
        )
        self.assertEqual(is_flag_applied, True)

    def test_is_flag_in_timeseries_applied_returns_false_when_optional_date_is_used(self):
        is_flag_applied = utils.is_flag_in_timeseries_applied(
            flag_timeseries_iterable=[
                FlagTimeseries([(datetime(2021, 1, 2, tzinfo=ZoneInfo("UTC")), False)])
            ],
            effective_datetime=datetime(2021, 1, 2, tzinfo=ZoneInfo("UTC")),
        )
        self.assertEqual(is_flag_applied, False)


@patch.object(utils, "get_parameter")
class GetFlagTimeseriesListForParameterTest(FeatureTest):
    def test_get_flag_timeseries_list_for_parameter(self, mock_get_parameter: MagicMock):
        mock_vault = self.create_mock(
            flags_ts={
                "flag_applied": FlagTimeseries([(DEFAULT_DATETIME, True)]),
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"dummy_flags": ["flag_applied", "flag_not_applied"]}
        )

        flag_timeseries_list = utils.get_flag_timeseries_list_for_parameter(
            vault=mock_vault, parameter_name="dummy_flags"
        )
        flag_applied_timeseries = flag_timeseries_list[0]
        flag_not_applied_timeseries = flag_timeseries_list[1]

        self.assertEqual(flag_applied_timeseries.latest(), True)
        self.assertEqual(flag_not_applied_timeseries.latest(), False)


## Schedule helpers
class ScheduledEventTest(FeatureTest):
    @patch.object(utils, "get_parameter")
    def test_daily_scheduled_event_default_skip(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "my_param_hour": 1,
                "my_param_minute": 2,
                "my_param_second": 3,
            }
        )
        scheduled_event = utils.daily_scheduled_event(
            vault=MagicMock(), start_datetime=DEFAULT_DATETIME, parameter_prefix="my_param"
        )
        self.assertEqual(
            scheduled_event,
            ScheduledEvent(
                start_datetime=DEFAULT_DATETIME,
                expression=ScheduleExpression(hour=1, minute=2, second=3),
                skip=False,
            ),
        )

    @patch.object(utils, "get_parameter")
    def test_daily_scheduled_event_with_skip(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "my_param_hour": 1,
                "my_param_minute": 2,
                "my_param_second": 3,
            }
        )
        scheduled_event = utils.daily_scheduled_event(
            vault=MagicMock(),
            start_datetime=DEFAULT_DATETIME,
            parameter_prefix="my_param",
            skip=True,
        )
        self.assertEqual(
            scheduled_event,
            ScheduledEvent(
                start_datetime=DEFAULT_DATETIME,
                expression=ScheduleExpression(hour=1, minute=2, second=3),
                skip=True,
            ),
        )

    @patch.object(utils, "get_parameter")
    def test_daily_scheduled_event_with_skip_to_datetime(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "my_param_hour": 1,
                "my_param_minute": 2,
                "my_param_second": 3,
            }
        )
        scheduled_event = utils.daily_scheduled_event(
            vault=MagicMock(),
            start_datetime=DEFAULT_DATETIME,
            parameter_prefix="my_param",
            skip=_ScheduleSkip(end=DEFAULT_DATETIME),
        )
        self.assertEqual(
            scheduled_event,
            ScheduledEvent(
                start_datetime=DEFAULT_DATETIME,
                expression=ScheduleExpression(hour=1, minute=2, second=3),
                skip=ScheduleSkip(end=DEFAULT_DATETIME),
            ),
        )

    @patch.object(utils, "get_end_of_month_schedule_from_parameters")
    def test_monthly_scheduled_event(
        self,
        mock_get_end_of_month_schedule_from_parameters: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_end_of_month_schedule_from_parameters.return_value = SentinelEndOfMonthSchedule(
            "end_of_month"
        )
        scheduled_event = utils.monthly_scheduled_event(
            vault=mock_vault,
            start_datetime=DEFAULT_DATETIME,
            parameter_prefix="my_param",
            failover=sentinel.failover,
            day=sentinel.day,
        )
        self.assertEqual(
            scheduled_event,
            ScheduledEvent(
                # Adjust start_datetime. For simulation and E2E, Schedule DSL expressions are
                # exclusive of start_datetime, but inclusive for non DSL expressions.
                start_datetime=DEFAULT_DATETIME - relativedelta(seconds=1),
                schedule_method=SentinelEndOfMonthSchedule("end_of_month"),
            ),
        )
        mock_get_end_of_month_schedule_from_parameters.assert_called_once_with(
            vault=mock_vault,
            parameter_prefix="my_param",
            failover=sentinel.failover,
            day=sentinel.day,
        )

    @patch.object(utils, "get_end_of_month_schedule_from_parameters")
    def test_monthly_scheduled_event_default_failover_and_day(
        self, mock_get_end_of_month_schedule_from_parameters: MagicMock
    ):
        mock_vault = self.create_mock()
        mock_get_end_of_month_schedule_from_parameters.return_value = SentinelEndOfMonthSchedule(
            "end_of_month"
        )
        scheduled_event = utils.monthly_scheduled_event(
            vault=mock_vault,
            start_datetime=DEFAULT_DATETIME,
            parameter_prefix="my_param",
        )
        self.assertEqual(
            scheduled_event,
            ScheduledEvent(
                # Adjust start_datetime. For simulation and E2E, Schedule DSL expressions are
                # exclusive of start_datetime, but inclusive for non DSL expressions.
                start_datetime=DEFAULT_DATETIME - relativedelta(seconds=1),
                schedule_method=SentinelEndOfMonthSchedule("end_of_month"),
            ),
        )
        mock_get_end_of_month_schedule_from_parameters.assert_called_once_with(
            vault=mock_vault,
            parameter_prefix="my_param",
            failover=ScheduleFailover.FIRST_VALID_DAY_BEFORE,
            day=None,
        )

    @patch.object(utils, "get_end_of_month_schedule_from_parameters")
    def test_monthly_scheduled_event_start_datetime_before_account_creation(
        self, mock_get_end_of_month_schedule_from_parameters: MagicMock
    ):
        # If called with a start_datetime earlier than the account creation datetime,
        # the helper will default to account creation datetime.
        mock_vault = self.create_mock()
        mock_get_end_of_month_schedule_from_parameters.return_value = SentinelEndOfMonthSchedule(
            "end_of_month"
        )
        start_datetime = mock_vault.get_account_creation_datetime() - relativedelta(seconds=1)
        scheduled_event = utils.monthly_scheduled_event(
            vault=mock_vault,
            start_datetime=start_datetime,
            parameter_prefix="my_param",
        )
        self.assertEqual(
            scheduled_event,
            ScheduledEvent(
                start_datetime=mock_vault.get_account_creation_datetime(),
                schedule_method=SentinelEndOfMonthSchedule("end_of_month"),
            ),
        )
        mock_get_end_of_month_schedule_from_parameters.assert_called_once_with(
            vault=mock_vault,
            parameter_prefix="my_param",
            failover=ScheduleFailover.FIRST_VALID_DAY_BEFORE,
            day=None,
        )

    @patch.object(utils, "get_end_of_month_schedule_from_parameters")
    def test_monthly_scheduled_event_start_datetime_at_account_creation(
        self, mock_get_end_of_month_schedule_from_parameters: MagicMock
    ):
        mock_vault = self.create_mock()
        mock_get_end_of_month_schedule_from_parameters.return_value = SentinelEndOfMonthSchedule(
            "end_of_month"
        )
        start_datetime = mock_vault.get_account_creation_datetime()
        scheduled_event = utils.monthly_scheduled_event(
            vault=mock_vault,
            start_datetime=start_datetime,
            parameter_prefix="my_param",
        )
        self.assertEqual(
            scheduled_event,
            ScheduledEvent(
                start_datetime=mock_vault.get_account_creation_datetime(),
                schedule_method=SentinelEndOfMonthSchedule("end_of_month"),
            ),
        )
        mock_get_end_of_month_schedule_from_parameters.assert_called_once_with(
            vault=mock_vault,
            parameter_prefix="my_param",
            failover=ScheduleFailover.FIRST_VALID_DAY_BEFORE,
            day=None,
        )


class ScheduleFromParametersTest(FeatureTest):
    def test_create_schedule_expression_from_datetime(self):
        schedule_datetime = datetime(year=2000, month=1, day=2, hour=3, minute=4, second=5)
        expected_schedule_expression = ScheduleExpression(
            year=2000,
            month=1,
            day=2,
            hour=3,
            minute=4,
            second=5,
        )
        schedule_expression = utils.one_off_schedule_expression(
            schedule_datetime=schedule_datetime,
        )

        self.assertTrue(expected_schedule_expression, schedule_expression)

    def test_get_schedule_time_from_parameters(self):
        parameter_timeseries = construct_parameter_timeseries(
            parameter_name_to_value_map={
                "schedule_prefix_hour": "1",
                "schedule_prefix_minute": "2",
                "schedule_prefix_second": "3",
            },
            default_datetime=DEFAULT_DATETIME,
        )
        mock_vault = self.create_mock(parameter_ts=parameter_timeseries)

        expected_tuple = 1, 2, 3
        result = utils.get_schedule_time_from_parameters(
            mock_vault, parameter_prefix="schedule_prefix"
        )

        self.assertTupleEqual(result, expected_tuple)

    @patch.object(utils, "get_schedule_time_from_parameters")
    def test_get_schedule_expression_from_parameters_only_provide_prefix(
        self, mock_get_schedule_time_from_parameters: MagicMock
    ):
        mock_get_schedule_time_from_parameters.return_value = 1, 2, 3
        expected_expression = ScheduleExpression(hour=1, minute=2, second=3)
        result = utils.get_schedule_expression_from_parameters(
            vault=MagicMock(),
            parameter_prefix="dummy_prefix",
            day=None,
            month=None,
            year=None,
            day_of_week=None,
        )
        self.assertEqual(result, expected_expression)

    @patch.object(utils, "get_schedule_time_from_parameters")
    def test_get_schedule_expression_from_parameters_only_provide_day(
        self, mock_get_schedule_time_from_parameters: MagicMock
    ):
        mock_get_schedule_time_from_parameters.return_value = 1, 2, 3
        expected_expression = ScheduleExpression(hour=1, minute=2, second=3, day=4)
        result = utils.get_schedule_expression_from_parameters(
            vault=MagicMock(),
            parameter_prefix="dummy_prefix",
            day=4,
            month=None,
            year=None,
            day_of_week=None,
        )
        self.assertEqual(result, expected_expression)

    @patch.object(utils, "get_schedule_time_from_parameters")
    def test_get_schedule_expression_from_parameters_only_provide_month(
        self, mock_get_schedule_time_from_parameters: MagicMock
    ):
        mock_get_schedule_time_from_parameters.return_value = 1, 2, 3
        expected_expression = ScheduleExpression(hour=1, minute=2, second=3, month=5)
        result = utils.get_schedule_expression_from_parameters(
            vault=MagicMock(),
            parameter_prefix="dummy_prefix",
            day=None,
            month=5,
            year=None,
            day_of_week=None,
        )
        self.assertEqual(result, expected_expression)

    @patch.object(utils, "get_schedule_time_from_parameters")
    def test_get_schedule_expression_from_parameters_only_provide_year(
        self, mock_get_schedule_time_from_parameters: MagicMock
    ):
        mock_get_schedule_time_from_parameters.return_value = 1, 2, 3
        expected_expression = ScheduleExpression(hour=1, minute=2, second=3, year=2023)
        result = utils.get_schedule_expression_from_parameters(
            vault=MagicMock(),
            parameter_prefix="dummy_prefix",
            day=None,
            month=None,
            year=2023,
            day_of_week=None,
        )
        self.assertEqual(result, expected_expression)

    @patch.object(utils, "get_schedule_time_from_parameters")
    def test_get_schedule_expression_from_parameters_only_provide_day_of_week(
        self, mock_get_schedule_time_from_parameters: MagicMock
    ):
        mock_get_schedule_time_from_parameters.return_value = 1, 2, 3
        expected_expression = ScheduleExpression(hour=1, minute=2, second=3, day_of_week=6)
        result = utils.get_schedule_expression_from_parameters(
            vault=MagicMock(),
            parameter_prefix="dummy_prefix",
            day=None,
            month=None,
            year=None,
            day_of_week=6,
        )
        self.assertEqual(result, expected_expression)

    @patch.object(utils, "get_schedule_time_from_parameters")
    def test_get_schedule_expression_from_parameters_provide_day_and_month(
        self, mock_get_schedule_time_from_parameters: MagicMock
    ):
        mock_get_schedule_time_from_parameters.return_value = 1, 2, 3
        expected_expression = ScheduleExpression(hour=1, minute=2, second=3, day=4, month=5)
        result = utils.get_schedule_expression_from_parameters(
            vault=MagicMock(),
            parameter_prefix="dummy_prefix",
            day=4,
            month=5,
            year=None,
            day_of_week=None,
        )
        self.assertEqual(result, expected_expression)

    @patch.object(utils, "get_schedule_time_from_parameters")
    def test_get_schedule_expression_from_parameters_provide_month_and_year(
        self, mock_get_schedule_time_from_parameters: MagicMock
    ):
        mock_get_schedule_time_from_parameters.return_value = 1, 2, 3
        expected_expression = ScheduleExpression(hour=1, minute=2, second=3, month=5, year=2023)
        result = utils.get_schedule_expression_from_parameters(
            vault=MagicMock(),
            parameter_prefix="dummy_prefix",
            day=None,
            month=5,
            year=2023,
            day_of_week=None,
        )
        self.assertEqual(result, expected_expression)

    @patch.object(utils, "get_schedule_time_from_parameters")
    def test_get_schedule_expression_from_parameters_provide_day_month_year(
        self, mock_get_schedule_time_from_parameters: MagicMock
    ):
        mock_get_schedule_time_from_parameters.return_value = 1, 2, 3
        expected_expression = ScheduleExpression(
            hour=1,
            minute=2,
            second=3,
            day=4,
            month=5,
            year=2023,
        )
        result = utils.get_schedule_expression_from_parameters(
            vault=MagicMock(),
            parameter_prefix="dummy_prefix",
            day=4,
            month=5,
            year=2023,
            day_of_week=None,
        )
        self.assertEqual(result, expected_expression)

    @patch.object(utils, "get_schedule_time_from_parameters")
    def test_get_schedule_expression_from_parameters_provide_month_year_day_of_week(
        self, mock_get_schedule_time_from_parameters: MagicMock
    ):
        mock_get_schedule_time_from_parameters.return_value = 1, 2, 3
        expected_expression = ScheduleExpression(
            hour=1, minute=2, second=3, month=5, year=2023, day_of_week=6
        )
        result = utils.get_schedule_expression_from_parameters(
            vault=MagicMock(),
            parameter_prefix="dummy_prefix",
            day=None,
            month=5,
            year=2023,
            day_of_week=6,
        )
        self.assertEqual(result, expected_expression)

    @patch.object(utils, "get_schedule_time_from_parameters")
    def test_get_schedule_expression_from_parameters_provide_day_month_year_day_of_week(
        self, mock_get_schedule_time_from_parameters: MagicMock
    ):
        mock_get_schedule_time_from_parameters.return_value = 1, 2, 3
        expected_expression = ScheduleExpression(
            hour=1, minute=2, second=3, day=4, month=5, year=2023, day_of_week=6
        )
        result = utils.get_schedule_expression_from_parameters(
            vault=MagicMock(),
            parameter_prefix="dummy_prefix",
            day=4,
            month=5,
            year=2023,
            day_of_week=6,
        )
        self.assertEqual(result, expected_expression)

    @patch.object(utils, "get_parameter")
    def test_get_end_of_month_schedule_from_parameters(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "my_param_hour": 1,
                "my_param_minute": 2,
                "my_param_second": 3,
            }
        )
        end_of_month_schedule = utils.get_end_of_month_schedule_from_parameters(
            vault=sentinel.vault,
            parameter_prefix="my_param",
            failover=sentinel.failover,
            day=5,
        )
        self.assertEqual(
            end_of_month_schedule,
            EndOfMonthSchedule(day=5, hour=1, minute=2, second=3, failover=sentinel.failover),
        )

    @patch.object(utils, "get_parameter")
    def test_get_end_of_month_schedule_from_parameters_default_failover_and_day(
        self, mock_get_parameter: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "my_param_day": 24,
                "my_param_hour": 1,
                "my_param_minute": 2,
                "my_param_second": 3,
            }
        )
        end_of_month_schedule = utils.get_end_of_month_schedule_from_parameters(
            vault=sentinel.vault,
            parameter_prefix="my_param",
        )
        self.assertEqual(
            end_of_month_schedule,
            EndOfMonthSchedule(
                day=24,
                hour=1,
                minute=2,
                second=3,
                failover=ScheduleFailover.FIRST_VALID_DAY_BEFORE,
            ),
        )


class GetNextScheduleDateTest(FeatureTest):
    def test_next_schedule_date_returns_correct_date_monthly(self):
        get_next_schedule_date = utils.get_next_schedule_date(
            start_date=datetime(2020, 2, 1, 3, 4, 5),
            intended_day=31,
            schedule_frequency="monthly",
        )

        expected_apply_accrued_interest_schedule = datetime(
            year=2020, month=2, day=29, hour=3, minute=4, second=5
        )

        self.assertEqual(get_next_schedule_date, expected_apply_accrued_interest_schedule)

    def test_next_schedule_date_returns_correct_date_quarterly(self):
        get_next_schedule_date = utils.get_next_schedule_date(
            start_date=datetime(2019, 11, 1, 3, 4, 5),
            intended_day=31,
            schedule_frequency="quarterly",
        )

        expected_apply_accrued_interest_schedule = datetime(
            year=2020, month=2, day=29, hour=3, minute=4, second=5
        )

        self.assertEqual(get_next_schedule_date, expected_apply_accrued_interest_schedule)

    def test_next_schedule_date_returns_correct_date_annually(self):
        get_next_schedule_date = utils.get_next_schedule_date(
            start_date=datetime(2020, 2, 29, 23, 59, 59),
            intended_day=31,
            schedule_frequency="annually",
        )

        expected_apply_accrued_interest_schedule = datetime(
            year=2021, month=2, day=28, hour=23, minute=59, second=59
        )

        self.assertEqual(get_next_schedule_date, expected_apply_accrued_interest_schedule)


class GetPreviousScheduleExecutionDateTest(FeatureTest):
    def test_get_previous_schedule_execution_date_last_exc_date_and_start_date_exist(self):
        account_start_date = datetime(2019, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        last_event_execution_date = datetime(2020, 2, 20, 0, 0, 3, tzinfo=ZoneInfo("UTC"))
        expected_result = datetime(2020, 2, 20, 0, 0, 3, tzinfo=ZoneInfo("UTC"))

        mock_vault = self.create_mock(
            last_execution_datetimes={"REPAYMENT_DAY_SCHEDULE": last_event_execution_date},
        )
        result = utils.get_previous_schedule_execution_date(
            vault=mock_vault,
            event_type="REPAYMENT_DAY_SCHEDULE",
            account_start_date=account_start_date,
        )
        self.assertEqual(result, expected_result)

    def test_get_previous_schedule_execution_date_last_exc_date_none_start_date_exist(self):
        account_start_date = datetime(2019, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        # no last_event_execution_date
        expected_result = datetime(2019, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))

        mock_vault = self.create_mock(last_execution_datetimes={"REPAYMENT_DAY_SCHEDULE": None})
        result = utils.get_previous_schedule_execution_date(
            vault=mock_vault,
            event_type="REPAYMENT_DAY_SCHEDULE",
            account_start_date=account_start_date,
        )
        self.assertEqual(result, expected_result)

    def test_get_previous_schedule_execution_date_last_exc_date_exist_start_date_none(self):
        account_start_date = None
        last_event_execution_date = datetime(2020, 2, 20, 0, 0, 3, tzinfo=ZoneInfo("UTC"))
        expected_result = datetime(2020, 2, 20, 0, 0, 3, tzinfo=ZoneInfo("UTC"))

        mock_vault = self.create_mock(
            last_execution_datetimes={"REPAYMENT_DAY_SCHEDULE": last_event_execution_date},
        )
        result = utils.get_previous_schedule_execution_date(
            vault=mock_vault,
            event_type="REPAYMENT_DAY_SCHEDULE",
            account_start_date=account_start_date,
        )
        self.assertEqual(result, expected_result)

    def test_get_previous_schedule_execution_date_last_exc_date_and_start_date_none(self):
        account_start_date = None
        # no last_event_execution_date
        expected_result = None

        mock_vault = self.create_mock(last_execution_datetimes={"REPAYMENT_DAY_SCHEDULE": None})
        result = utils.get_previous_schedule_execution_date(
            vault=mock_vault,
            event_type="REPAYMENT_DAY_SCHEDULE",
            account_start_date=account_start_date,
        )
        self.assertEqual(result, expected_result)


class FallsOnCalendarEventsTest(FeatureTest):
    calendar_events = CalendarEvents(
        calendar_events=[
            CalendarEvent(
                id="1",
                calendar_id="CALENDAR",
                start_datetime=datetime(2020, 1, 2, 3, tzinfo=ZoneInfo("UTC")),
                end_datetime=datetime(2020, 1, 2, 4, tzinfo=ZoneInfo("UTC")),
            ),
            CalendarEvent(
                id="1",
                calendar_id="CALENDAR",
                start_datetime=datetime(2020, 1, 2, 4, tzinfo=ZoneInfo("UTC")),
                end_datetime=datetime(2020, 1, 2, 5, tzinfo=ZoneInfo("UTC")),
            ),
        ]
    )

    def test_effective_datetime_on_beginning_of_first_event(self):
        effective_datetime = datetime(year=2020, month=1, day=2, hour=3, tzinfo=ZoneInfo("UTC"))
        result = utils.falls_on_calendar_events(
            effective_datetime=effective_datetime, calendar_events=self.calendar_events
        )
        self.assertTrue(result)

    def test_effective_date_on_end_of_second_event(self):
        effective_datetime = datetime(year=2020, month=1, day=2, hour=5, tzinfo=ZoneInfo("UTC"))
        result = utils.falls_on_calendar_events(
            effective_datetime=effective_datetime, calendar_events=self.calendar_events
        )
        self.assertTrue(result)

    def test_effective_date_before_first_event(self):
        effective_datetime = datetime(year=2020, month=1, day=2, hour=2, tzinfo=ZoneInfo("UTC"))
        result = utils.falls_on_calendar_events(
            effective_datetime=effective_datetime, calendar_events=self.calendar_events
        )
        self.assertFalse(result)

    def test_effective_date_after_first_event(self):
        effective_datetime = datetime(year=2020, month=1, day=2, hour=6, tzinfo=ZoneInfo("UTC"))
        result = utils.falls_on_calendar_events(
            effective_datetime=effective_datetime, calendar_events=self.calendar_events
        )
        self.assertFalse(result)


class GetNextScheduleDateCalendarAwareTest(FeatureTest):
    test_calendar_events = CalendarEvents(
        calendar_events=[
            CalendarEvent(
                id="TEST",
                calendar_id="PUBLIC_HOLIDAYS",
                start_datetime=datetime(2020, 9, 5, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
                end_datetime=datetime(2020, 9, 6, 23, 23, 59, tzinfo=ZoneInfo("UTC")),
            ),
        ]
    )

    def test_next_schedule_date_calendar_aware_returns_correct_date_monthly_no_holiday(self):
        """
        Public Holiday Calendar for Sept 5 to Sept 6.
        Date is Feb 1, application date intended day 31.
        Since Feb 31 is invalid, and for 2020 Feb has 29 days, scheduled on Feb 29.
        """
        get_next_schedule_date_calendar_aware = utils.get_next_schedule_date_calendar_aware(
            start_datetime=datetime(2020, 2, 1, 3, 4, 5, tzinfo=ZoneInfo("UTC")),
            intended_day=31,
            schedule_frequency="monthly",
            calendar_events=self.test_calendar_events,
        )

        expected_apply_accrued_interest_schedule = datetime(
            year=2020, month=2, day=29, hour=3, minute=4, second=5, tzinfo=ZoneInfo("UTC")
        )

        self.assertEqual(
            get_next_schedule_date_calendar_aware, expected_apply_accrued_interest_schedule
        )

    def test_next_schedule_date_calendar_aware_returns_correct_date_monthly_on_holiday(self):
        """
        Public Holiday Calendar for Sept 5 to Sept 6.
        Date is Sept 6, application date intended day 6.
        Expect application date to Sept 7.
        """
        get_next_schedule_date_calendar_aware = utils.get_next_schedule_date_calendar_aware(
            start_datetime=datetime(2020, 9, 1, 3, 4, 5, tzinfo=ZoneInfo("UTC")),
            intended_day=6,
            schedule_frequency="monthly",
            calendar_events=self.test_calendar_events,
        )

        expected_apply_accrued_interest_schedule = datetime(
            year=2020, month=9, day=7, hour=3, minute=4, second=5, tzinfo=ZoneInfo("UTC")
        )

        self.assertEqual(
            get_next_schedule_date_calendar_aware, expected_apply_accrued_interest_schedule
        )

    def test_next_schedule_date_calendar_aware_returns_correct_date_monthly_same_day_on_holiday(
        self,
    ):
        """
        ELSE BRANCH. If date is on or after the application day, add appropriate number of months.
        Public Holiday Calendar for Sept 5 to Sept 6.
        Date is Sept 6, application date intended day 6.
        On the holiday or after, so should hit next month.
        Start Date: Sept 7 (one day after intended day). Hence next date should be October 7.
        """
        get_next_schedule_date_calendar_aware = utils.get_next_schedule_date_calendar_aware(
            start_datetime=datetime(2020, 9, 7, 3, 4, 5, tzinfo=ZoneInfo("UTC")),
            intended_day=6,
            schedule_frequency="monthly",
            calendar_events=self.test_calendar_events,
        )

        expected_apply_accrued_interest_schedule = datetime(
            year=2020, month=10, day=6, hour=3, minute=4, second=5, tzinfo=ZoneInfo("UTC")
        )

        self.assertEqual(
            get_next_schedule_date_calendar_aware, expected_apply_accrued_interest_schedule
        )

    def test_get_next_datetime_after_calendar_events(self):
        expected_effective_datetime = datetime(
            year=2020, month=9, day=7, hour=3, minute=4, second=5, tzinfo=ZoneInfo("UTC")
        )
        get_next_datetime_after_calendar_events = utils.get_next_datetime_after_calendar_events(
            effective_datetime=datetime(2020, 9, 6, 3, 4, 5, tzinfo=ZoneInfo("UTC")),
            calendar_events=self.test_calendar_events,
        )
        self.assertEqual(get_next_datetime_after_calendar_events, expected_effective_datetime)


class EndOfTimeScheduleTest(FeatureTest):
    def test_skipped_end_of_times_schedule(self):
        expected_schedule = ScheduledEvent(
            start_datetime=DEFAULT_DATETIME,
            skip=True,
            expression=ScheduleExpression(
                year=2099,
                month=1,
                day=1,
                hour=0,
                minute=0,
                second=0,
            ),
        )

        result = utils.create_end_of_time_schedule(DEFAULT_DATETIME)

        self.assertEqual(result, expected_schedule)


class UpdateCompletedSchedulesTest(FeatureTest):
    def test_empty_completed_schedules_returns_original_list(self):
        scheduled_events = {
            "EVENT_1": SentinelScheduledEvent("event_1"),
            "EVENT_2": SentinelScheduledEvent("event_2"),
        }
        result = utils.update_completed_schedules(
            scheduled_events=scheduled_events,
            effective_datetime=DEFAULT_DATETIME,
            potentially_completed_schedules=[],
        )
        self.assertEqual(result, scheduled_events)

    def test_only_update_events_with_end_datetime_in_the_past(self):
        scheduled_events = {
            "EVENT_1": ScheduledEvent(
                end_datetime=DEFAULT_DATETIME - relativedelta(hours=1),
                expression=ScheduleExpression(
                    year=2023, month=1, day=1, hour=0, minute=0, second=0
                ),
            ),
            "EVENT_2": ScheduledEvent(
                end_datetime=DEFAULT_DATETIME + relativedelta(hours=1),
                expression=ScheduleExpression(
                    year=2023, month=1, day=1, hour=0, minute=0, second=0
                ),
            ),
        }

        expected_result = {
            "EVENT_1": utils.END_OF_TIME_SCHEDULED_EVENT,
            "EVENT_2": ScheduledEvent(
                end_datetime=DEFAULT_DATETIME + relativedelta(hours=1),
                expression=ScheduleExpression(
                    year=2023, month=1, day=1, hour=0, minute=0, second=0
                ),
            ),
        }
        result = utils.update_completed_schedules(
            scheduled_events=scheduled_events,
            effective_datetime=DEFAULT_DATETIME,
            potentially_completed_schedules=["EVENT_1", "EVENT_2"],
        )
        self.assertEqual(result, expected_result)


class DisableCompletedSchedulesTest(FeatureTest):
    def test_update_schedules_to_skip_indefinitely(self):
        expected_result = [
            UpdateAccountEventTypeDirective(
                event_type="EVENT_1",
                expression=utils.END_OF_TIME_EXPRESSION,
                end_datetime=utils.END_OF_TIME,
                skip=True,
            ),
            UpdateAccountEventTypeDirective(
                event_type="EVENT_2",
                expression=utils.END_OF_TIME_EXPRESSION,
                end_datetime=utils.END_OF_TIME,
                skip=True,
            ),
        ]
        result = utils.update_schedules_to_skip_indefinitely(
            schedules=["EVENT_1", "EVENT_2"],
        )

        self.assertEqual(result, expected_result)


## Denomination helpers
class ValidateDenominationTest(FeatureTest):
    common_message = (
        "Cannot make transactions in the given denomination, transactions must be one of"
    )

    def test_validate_denomination_returns_rejection_if_invalid(self):
        posting_instructions = [
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="USD",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
            )
        ]

        result = utils.validate_denomination(
            posting_instructions=posting_instructions, accepted_denominations=["GBP"]
        )
        expected = Rejection(
            message=f"{self.common_message} ['GBP']", reason_code=RejectionReason.WRONG_DENOMINATION
        )
        self.assertEqual(result, expected)

    def test_validate_denomination_returns_rejection_if_invalid_custom_instruction(self):
        posting_instructions = [
            CustomInstruction(
                postings=[
                    Posting(
                        credit=True,
                        amount=Decimal("1"),
                        denomination="GBP",
                        account_id="account",
                        account_address="address",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    Posting(
                        credit=False,
                        amount=Decimal("1"),
                        denomination="USD",
                        account_id="account",
                        account_address="address",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                ]
            )
        ]
        result = utils.validate_denomination(
            posting_instructions=posting_instructions, accepted_denominations=["GBP", "AUD"]
        )
        expected = Rejection(
            message=f"{self.common_message} ['AUD', 'GBP']",
            reason_code=RejectionReason.WRONG_DENOMINATION,
        )
        self.assertEqual(result, expected)

    def test_validate_denomination_returns_rejection_if_invalid_multiple_instructions(self):
        posting_instructions = [
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
            ),
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="USD",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
            ),
        ]

        result = utils.validate_denomination(
            posting_instructions=posting_instructions, accepted_denominations=["GBP", "AUD"]
        )
        expected = Rejection(
            message=f"{self.common_message} ['AUD', 'GBP']",
            reason_code=RejectionReason.WRONG_DENOMINATION,
        )
        self.assertEqual(result, expected)

    def test_validate_denomination_returns_none_if_valid(self):
        posting_instructions = [
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
            ),
            CustomInstruction(
                postings=[
                    Posting(
                        credit=True,
                        amount=Decimal("1"),
                        denomination="GBP",
                        account_id="account",
                        account_address="address",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    Posting(
                        credit=False,
                        amount=Decimal("1"),
                        denomination="GBP",
                        account_id="account",
                        account_address="address",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                ]
            ),
        ]

        result = utils.validate_denomination(
            posting_instructions=posting_instructions, accepted_denominations=["GBP"]
        )
        self.assertIsNone(result)

    def test_validate_denomination_returns_none_if_valid_multiple_instructions(self):
        posting_instructions = [
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
            ),
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
            ),
        ]

        result = utils.validate_denomination(
            posting_instructions=posting_instructions, accepted_denominations=["GBP"]
        )
        self.assertIsNone(result)


## Posting helpers
class ValidateSingleHardSettlementOrTransferTest(FeatureTest):
    common_message = "Only batches with a single hard settlement or transfer posting are supported"
    common_reason = RejectionReason.CLIENT_CUSTOM_REASON

    def test_rejection_returned_if_multiple_hard_settlements(
        self,
    ):
        posting_instructions = [
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
            ),
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
            ),
        ]
        result = utils.validate_single_hard_settlement_or_transfer(
            posting_instructions=posting_instructions
        )
        expected = Rejection(message=self.common_message, reason_code=self.common_reason)
        self.assertEqual(result, expected)

    def test_rejection_returned_if_single_auth(self):
        posting_instructions = [
            InboundAuthorisation(
                client_transaction_id="123",
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
            )
        ]
        result = utils.validate_single_hard_settlement_or_transfer(
            posting_instructions=posting_instructions
        )
        expected = Rejection(message=self.common_message, reason_code=self.common_reason)
        self.assertEqual(result, expected)

    def test_rejection_returned_if_multiple_mixed_instructions(
        self,
    ):
        posting_instructions = [
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
            ),
            InboundAuthorisation(
                client_transaction_id="123",
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
            ),
        ]
        result = utils.validate_single_hard_settlement_or_transfer(
            posting_instructions=posting_instructions
        )
        expected = Rejection(message=self.common_message, reason_code=self.common_reason)
        self.assertEqual(result, expected)

    def test_none_returned_if_single_ihs(self):
        posting_instructions = [
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
            ),
        ]
        result = utils.validate_single_hard_settlement_or_transfer(
            posting_instructions=posting_instructions
        )
        self.assertIsNone(result)

    def test_none_returned_if_single_ohs(self):
        posting_instructions = [
            OutboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
            ),
        ]
        result = utils.validate_single_hard_settlement_or_transfer(
            posting_instructions=posting_instructions
        )
        self.assertIsNone(result)

    def test_none_returned_if_single_transfer(self):
        posting_instructions = [
            Transfer(
                amount=Decimal("1"),
                denomination="GBP",
                debtor_target_account_id="some_account",
                creditor_target_account_id="another_account",
            ),
        ]
        result = utils.validate_single_hard_settlement_or_transfer(
            posting_instructions=posting_instructions
        )
        self.assertIsNone(result)


class IsOKeyInInstructionDetailsTest(FeatureTest):
    def test_is_key_in_instruction_details_single_posting_is_override(self):
        posting_instructions = [
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                instruction_details={"dummy_key": "true"},
            ),
        ]
        result = utils.is_key_in_instruction_details(
            key="dummy_key", posting_instructions=posting_instructions
        )
        self.assertTrue(result)

    def test_is_key_in_instruction_details_single_posting_is_not_override(self):
        posting_instructions = [
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
            ),
        ]
        result = utils.is_key_in_instruction_details(
            key="dummy_key", posting_instructions=posting_instructions
        )
        self.assertFalse(result)

    def test_is_key_in_instruction_details_multiple_postings_is_override(self):
        posting_instructions = [
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                instruction_details={"dummy_key": "true"},
            ),
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                instruction_details={"dummy_key": "true"},
            ),
        ]
        result = utils.is_key_in_instruction_details(
            key="dummy_key", posting_instructions=posting_instructions
        )
        self.assertTrue(result)

    def test_is_key_in_instruction_details_multiple_postings_is_not_override(self):
        posting_instructions = [
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                instruction_details={"dummy_key": "true"},
            ),
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
            ),
        ]
        result = utils.is_key_in_instruction_details(
            key="dummy_key", posting_instructions=posting_instructions
        )
        self.assertFalse(result)


class ForceOverrideTest(FeatureTest):
    def test_is_force_override_single_posting_is_override(self):
        posting_instructions = [
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                instruction_details={"force_override": "true"},
            ),
        ]
        result = utils.is_force_override(posting_instructions=posting_instructions)
        self.assertTrue(result)

    def test_is_force_override_single_posting_is_not_override(self):
        posting_instructions = [
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
            ),
        ]
        result = utils.is_force_override(posting_instructions=posting_instructions)
        self.assertFalse(result)

    def test_is_force_override_multiple_postings_is_override(self):
        posting_instructions = [
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                instruction_details={"force_override": "true"},
            ),
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                instruction_details={"force_override": "true"},
            ),
        ]
        result = utils.is_force_override(posting_instructions=posting_instructions)
        self.assertTrue(result)

    def test_is_force_override_multiple_postings_is_not_override(self):
        posting_instructions = [
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                instruction_details={"force_override": "true"},
            ),
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
            ),
        ]
        result = utils.is_force_override(posting_instructions=posting_instructions)
        self.assertFalse(result)


class WithdrawalOverrideTest(FeatureTest):
    def test_is_withdrawal_override_single_posting_is_override(self):
        posting_instructions = [
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                instruction_details={"withdrawal_override": "true"},
            ),
        ]
        result = utils.is_withdrawal_override(posting_instructions=posting_instructions)
        self.assertTrue(result)

    def test_is_withdrawal_override_single_posting_is_not_override(self):
        posting_instructions = [
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
            ),
        ]
        result = utils.is_withdrawal_override(posting_instructions=posting_instructions)
        self.assertFalse(result)

    def test_is_withdrawal_override_multiple_postings_is_override(self):
        posting_instructions = [
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                instruction_details={"withdrawal_override": "true"},
            ),
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                instruction_details={"withdrawal_override": "true"},
            ),
        ]
        result = utils.is_withdrawal_override(posting_instructions=posting_instructions)
        self.assertTrue(result)

    def test_is_withdrawal_override_multiple_postings_is_not_override(self):
        posting_instructions = [
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                instruction_details={"withdrawal_override": "true"},
            ),
            InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
            ),
        ]
        result = utils.is_withdrawal_override(posting_instructions=posting_instructions)
        self.assertFalse(result)


class StandardInstructionDetailsTest(FeatureTest):
    def test_standardised_instruction_details(self):
        instruction_details = utils.standard_instruction_details(
            description="description_1",
            event_type=sentinel.event_type,
            gl_impacted=True,
            account_type=sentinel.account_type,
        )

        self.assertEqual(
            instruction_details,
            {
                "description": "description_1",
                "event": sentinel.event_type,
                "gl_impacted": "True",
                "account_type": sentinel.account_type,
            },
        )


class GetTransactionTypeTest(FeatureTest):
    def test_get_txn_type_returns_correct_type_from_code(self):
        instruction_details = {
            "transaction_code": "00",
        }
        txn_code_to_type_map = {
            "00": "cash_advance",
            "01": "purchase",
        }
        default_txn_type = "purchase"
        expected_result = "cash_advance"

        result = utils.get_transaction_type(
            instruction_details=instruction_details,
            txn_code_to_type_map=txn_code_to_type_map,
            default_txn_type=default_txn_type,
        )

        self.assertEqual(result, expected_result)

    def test_get_txn_type_returns_correct_type_for_empty_string_code(self):
        instruction_details = {"transaction_code": ""}
        txn_code_to_type_map = {
            "": "cash_advance",
            "01": "purchase",
        }
        default_txn_type = "default_purchase"
        expected_result = "cash_advance"

        result = utils.get_transaction_type(
            instruction_details=instruction_details,
            txn_code_to_type_map=txn_code_to_type_map,
            default_txn_type=default_txn_type,
        )

        self.assertEqual(result, expected_result)

        instruction_details = {
            "transaction_code": "04",
        }
        txn_code_to_type_map = {
            "00": "cash_advance",
            "01": "purchase",
        }
        default_txn_type = "default_purchase"
        expected_result = "default_purchase"

        result = utils.get_transaction_type(
            instruction_details=instruction_details,
            txn_code_to_type_map=txn_code_to_type_map,
            default_txn_type=default_txn_type,
        )

        self.assertEqual(result, expected_result)

    def test_get_txn_type_returns_default_type_if_no_transaction_code(self):
        instruction_details = {}
        txn_code_to_type_map = {
            "00": "cash_advance",
            "01": "purchase",
        }
        default_txn_type = "default_purchase"
        expected_result = "default_purchase"

        result = utils.get_transaction_type(
            instruction_details=instruction_details,
            txn_code_to_type_map=txn_code_to_type_map,
            default_txn_type=default_txn_type,
        )

        self.assertEqual(result, expected_result)


## Balances helpers
class BalancesTestBase(FeatureTest):
    def balances(
        self,
        default_committed: Decimal = DECIMAL_ZERO,
        todays_spending: Decimal = DECIMAL_ZERO,
        todays_gifts: Decimal = DECIMAL_ZERO,
        default_pending_outgoing: Decimal = DECIMAL_ZERO,
        default_pending_incoming: Decimal = DECIMAL_ZERO,
    ) -> _BalanceDefaultDict:
        mapping = {
            self.balance_coordinate(): self.balance(net=default_committed),
            self.balance_coordinate(account_address="TODAYS_SPENDING"): self.balance(
                net=todays_spending
            ),
            self.balance_coordinate(account_address="TODAYS_GIFTS"): self.balance(net=todays_gifts),
            self.balance_coordinate(phase=Phase.PENDING_OUT): self.balance(
                net=default_pending_outgoing
            ),
            self.balance_coordinate(phase=Phase.PENDING_IN): self.balance(
                net=default_pending_incoming
            ),
        }
        return _BalanceDefaultDict(mapping=mapping)

    def balance_mapping(
        self,
        default_committed: Decimal = DECIMAL_ZERO,
        todays_spending: Decimal = DECIMAL_ZERO,
        todays_gifts: Decimal = DECIMAL_ZERO,
        default_pending_outgoing: Decimal = DECIMAL_ZERO,
        default_pending_incoming: Decimal = DECIMAL_ZERO,
    ) -> Mapping[BalanceCoordinate, BalanceTimeseries]:
        return {
            self.balance_coordinate(): self.construct_balance_timeseries(
                dt=DEFAULT_DATETIME, net=default_committed
            ),
            self.balance_coordinate(
                account_address="TODAYS_SPENDING"
            ): self.construct_balance_timeseries(dt=DEFAULT_DATETIME, net=todays_spending),
            self.balance_coordinate(
                account_address="TODAYS_GIFTS"
            ): self.construct_balance_timeseries(dt=DEFAULT_DATETIME, net=todays_gifts),
            self.balance_coordinate(phase=Phase.PENDING_OUT): self.construct_balance_timeseries(
                dt=DEFAULT_DATETIME, net=default_pending_outgoing
            ),
            self.balance_coordinate(phase=Phase.PENDING_IN): self.construct_balance_timeseries(
                dt=DEFAULT_DATETIME, net=default_pending_incoming
            ),
        }


class SumBalancesTest(BalancesTestBase):
    def test_sum_balances_of_single_address(self):
        balances = self.balances(
            default_committed=Decimal("100"),
            todays_spending=Decimal("35"),
            todays_gifts=Decimal("20"),
            default_pending_outgoing=Decimal("10"),
            default_pending_incoming=Decimal("0"),
        )

        result = utils.sum_balances(
            balances=balances,
            addresses=["DEFAULT"],
            phase=Phase.COMMITTED,
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(result, Decimal("100"))

    def test_sum_balances_of_multiple_addresses(self):
        balances = self.balances(
            default_committed=Decimal("100"),
            todays_spending=Decimal("35"),
            todays_gifts=Decimal("20"),
            default_pending_outgoing=Decimal("10"),
            default_pending_incoming=Decimal("0"),
        )

        result = utils.sum_balances(
            balances=balances,
            addresses=["DEFAULT", "TODAYS_SPENDING"],
            phase=Phase.COMMITTED,
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(result, Decimal("135"))

    def test_sum_balances_of_specific_phase(self):
        balances = self.balances(
            default_committed=Decimal("100"),
            todays_spending=Decimal("35"),
            todays_gifts=Decimal("20"),
            default_pending_outgoing=Decimal("10"),
            default_pending_incoming=Decimal("0"),
        )

        result = utils.sum_balances(
            balances=balances,
            addresses=["DEFAULT"],
            phase=Phase.PENDING_OUT,
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(result, Decimal("10"))

    def test_sum_balances_no_rounding(self):
        balances = self.balances(
            default_committed=Decimal("100.12345"),
            todays_spending=Decimal("35"),
            todays_gifts=Decimal("20"),
            default_pending_outgoing=Decimal("10"),
            default_pending_incoming=Decimal("0"),
        )

        result = utils.sum_balances(
            balances=balances,
            addresses=["DEFAULT", "TODAYS_SPENDING"],
            phase=Phase.COMMITTED,
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(result, Decimal("135.12345"))

    def test_sum_balances_2_dp_rounding(self):
        balances = self.balances(
            default_committed=Decimal("100.12345"),
            todays_spending=Decimal("35"),
            todays_gifts=Decimal("20"),
            default_pending_outgoing=Decimal("10"),
            default_pending_incoming=Decimal("0"),
        )

        result = utils.sum_balances(
            balances=balances,
            addresses=["DEFAULT", "TODAYS_SPENDING"],
            phase=Phase.COMMITTED,
            denomination=DEFAULT_DENOMINATION,
            decimal_places=2,
        )

        self.assertEqual(result, Decimal("135.12"))

    def test_sum_balances_0_dp_rounding(self):
        balances = self.balances(
            default_committed=Decimal("100.12345"),
            todays_spending=Decimal("35"),
            todays_gifts=Decimal("20"),
            default_pending_outgoing=Decimal("10"),
            default_pending_incoming=Decimal("0"),
        )

        result = utils.sum_balances(
            balances=balances,
            addresses=["DEFAULT", "TODAYS_SPENDING"],
            phase=Phase.COMMITTED,
            denomination=DEFAULT_DENOMINATION,
            decimal_places=0,
        )

        self.assertEqual(result, Decimal("135"))

    def test_sum_balances_negative_dp_rounding(self):
        balances = self.balances(
            default_committed=Decimal("100.12345"),
            todays_spending=Decimal("35"),
            todays_gifts=Decimal("20"),
            default_pending_outgoing=Decimal("10"),
            default_pending_incoming=Decimal("0"),
        )

        result = utils.sum_balances(
            balances=balances,
            addresses=["DEFAULT", "TODAYS_SPENDING"],
            phase=Phase.COMMITTED,
            denomination=DEFAULT_DENOMINATION,
            decimal_places=-1,
        )

        self.assertEqual(result, Decimal("140"))


class GetEffectiveBalanceForAddressTest(FeatureTest):
    def setUp(self) -> None:
        self.balances = _BalanceDefaultDict(
            mapping={
                self.balance_coordinate(): self.balance(net=Decimal("12")),
                self.balance_coordinate(account_address="ADDRESS_1", asset="ASSET_1"): self.balance(
                    net=Decimal("23")
                ),
                self.balance_coordinate(
                    account_address="ADDRESS_2", phase=Phase.PENDING_IN
                ): self.balance(net=Decimal("34")),
                self.balance_coordinate(
                    account_address="ADDRESS_3",
                    denomination="ABC",
                    phase=Phase.PENDING_OUT,
                    asset="ASSET_3",
                ): self.balance(net=Decimal("45")),
            }
        )
        return super().setUp()

    def test_balance_at_coordinates_no_optional_args(self):
        result = utils.balance_at_coordinates(
            balances=self.balances, address=DEFAULT_ADDRESS, denomination="GBP"
        )
        self.assertEqual(result, Decimal("12"))

    def test_balance_at_coordinates_asset_provided(self):
        result = utils.balance_at_coordinates(
            balances=self.balances, address="ADDRESS_1", denomination="GBP", asset="ASSET_1"
        )
        self.assertEqual(result, Decimal("23"))

    def test_balance_at_coordinates_phase_provided(self):
        result = utils.balance_at_coordinates(
            balances=self.balances, address="ADDRESS_2", denomination="GBP", phase=Phase.PENDING_IN
        )
        self.assertEqual(result, Decimal("34"))

    def test_balance_at_coordinates_all_args_provided(self):
        result = utils.balance_at_coordinates(
            balances=self.balances,
            address="ADDRESS_3",
            denomination="ABC",
            asset="ASSET_3",
            phase=Phase.PENDING_OUT,
        )
        self.assertEqual(result, Decimal("45"))

    def test_balance_at_coordinates_returns_0_when_combination_does_not_exist(self):
        result = utils.balance_at_coordinates(
            balances=self.balances, address="ADDRESS_4", denomination="GBP"
        )
        self.assertEqual(result, Decimal("0"))

    def test_balance_at_coordinates_2_decimal_places(self):
        balances = _BalanceDefaultDict(
            mapping={
                self.balance_coordinate(): self.balance(net=Decimal("123.12345")),
            }
        )
        result = utils.balance_at_coordinates(
            balances=balances, address=DEFAULT_ADDRESS, denomination="GBP", decimal_places=2
        )
        self.assertEqual(result, Decimal("123.12"))

    def test_balance_at_coordinates_0_decimal_places(self):
        balances = _BalanceDefaultDict(
            mapping={
                self.balance_coordinate(): self.balance(net=Decimal("123.12345")),
            }
        )
        result = utils.balance_at_coordinates(
            balances=balances, address=DEFAULT_ADDRESS, denomination="GBP", decimal_places=0
        )
        self.assertEqual(result, Decimal("123"))

    def test_balance_at_coordinates_negative_decimal_places(self):
        balances = _BalanceDefaultDict(
            mapping={
                self.balance_coordinate(): self.balance(net=Decimal("123.12345")),
            }
        )
        result = utils.balance_at_coordinates(
            balances=balances, address=DEFAULT_ADDRESS, denomination="GBP", decimal_places=-1
        )
        self.assertEqual(result, Decimal("120"))

    def test_balance_at_coordinates_decimal_places_not_provided(self):
        balances = _BalanceDefaultDict(
            mapping={
                self.balance_coordinate(): self.balance(net=Decimal("123.12345")),
            }
        )
        result = utils.balance_at_coordinates(
            balances=balances, address=DEFAULT_ADDRESS, denomination="GBP"
        )
        self.assertEqual(result, Decimal("123.12345"))


class GetAvailableBalanceTest(BalancesTestBase):
    def test_get_available_balance_committed_and_pending_out_not_zero(self):
        balances = self.balances(
            default_committed=Decimal("100"),
            default_pending_outgoing=Decimal("-50"),
            default_pending_incoming=Decimal("30"),
        )
        result = utils.get_available_balance(balances=balances, denomination=DEFAULT_DENOMINATION)
        self.assertEqual(result, Decimal("50"))

    def test_get_available_balance_committed_zero_and_pending_out_not_zero(self):
        balances = self.balances(
            default_committed=Decimal("0"),
            default_pending_outgoing=Decimal("-50"),
            default_pending_incoming=Decimal("10"),
        )
        result = utils.get_available_balance(balances=balances, denomination=DEFAULT_DENOMINATION)
        self.assertEqual(result, Decimal("-50"))

    def test_get_available_balance_committed_not_zero_and_pending_out_zero(self):
        balances = self.balances(
            default_committed=Decimal("100"),
            default_pending_outgoing=Decimal("0"),
            default_pending_incoming=Decimal("0"),
        )
        result = utils.get_available_balance(balances=balances, denomination=DEFAULT_DENOMINATION)
        self.assertEqual(result, Decimal("100"))

    def test_get_available_balance_both_committed_and_pending_out_are_zero(self):
        balances = self.balances(
            default_committed=Decimal("0"),
            default_pending_outgoing=Decimal("0"),
            default_pending_incoming=Decimal("10"),
        )
        result = utils.get_available_balance(balances=balances, denomination=DEFAULT_DENOMINATION)
        self.assertEqual(result, Decimal("0"))


class GetLatestAvailableBalanceFromMappingTest(BalancesTestBase):
    def test_get_available_balance_committed_and_pending_out_not_zero(self):
        balance_mapping = self.balance_mapping(
            default_committed=Decimal("100"),
            default_pending_outgoing=Decimal("-50"),
            default_pending_incoming=Decimal("30"),
        )
        result = utils.get_latest_available_balance_from_mapping(
            mapping=balance_mapping, denomination=DEFAULT_DENOMINATION
        )
        self.assertEqual(result, Decimal("50"))

    def test_get_available_balance_committed_zero_and_pending_out_not_zero(self):
        balance_mapping = self.balance_mapping(
            default_committed=Decimal("0"),
            default_pending_outgoing=Decimal("-50"),
            default_pending_incoming=Decimal("10"),
        )
        result = utils.get_latest_available_balance_from_mapping(
            mapping=balance_mapping, denomination=DEFAULT_DENOMINATION
        )
        self.assertEqual(result, Decimal("-50"))

    def test_get_available_balance_committed_not_zero_and_pending_out_zero(self):
        balance_mapping = self.balance_mapping(
            default_committed=Decimal("100"),
            default_pending_outgoing=Decimal("0"),
            default_pending_incoming=Decimal("0"),
        )
        result = utils.get_latest_available_balance_from_mapping(
            mapping=balance_mapping, denomination=DEFAULT_DENOMINATION
        )
        self.assertEqual(result, Decimal("100"))

    def test_get_available_balance_both_committed_and_pending_out_are_zero(self):
        balance_mapping = self.balance_mapping(
            default_committed=Decimal("0"),
            default_pending_outgoing=Decimal("0"),
            default_pending_incoming=Decimal("10"),
        )
        result = utils.get_latest_available_balance_from_mapping(
            mapping=balance_mapping, denomination=DEFAULT_DENOMINATION
        )
        self.assertEqual(result, Decimal("0"))


class GetCurrentNetBalanceTest(BalancesTestBase):
    def test_get_current_net_balance_committed_and_pending_in_not_zero(self):
        balances = self.balances(
            default_committed=Decimal("100"),
            default_pending_outgoing=Decimal("-50"),
            default_pending_incoming=Decimal("30"),
        )
        result = utils.get_current_net_balance(balances=balances, denomination=DEFAULT_DENOMINATION)
        self.assertEqual(result, Decimal("130"))

    def test_get_current_net_balance_committed_zero_and_pending_in_not_zero(self):
        balances = self.balances(
            default_committed=Decimal("0"),
            default_pending_outgoing=Decimal("-50"),
            default_pending_incoming=Decimal("10"),
        )
        result = utils.get_current_net_balance(balances=balances, denomination=DEFAULT_DENOMINATION)
        self.assertEqual(result, Decimal("10"))

    def test_get_current_net_balance_committed_not_zero_and_pending_in_zero(self):
        balances = self.balances(
            default_committed=Decimal("100"),
            default_pending_outgoing=Decimal("0"),
            default_pending_incoming=Decimal("0"),
        )
        result = utils.get_current_net_balance(balances=balances, denomination=DEFAULT_DENOMINATION)
        self.assertEqual(result, Decimal("100"))

    def test_get_current_net_balance_both_committed_and_pending_in_are_zero(self):
        balances = self.balances(
            default_committed=Decimal("0"),
            default_pending_outgoing=Decimal("50"),
            default_pending_incoming=Decimal("0"),
        )
        result = utils.get_current_net_balance(balances=balances, denomination=DEFAULT_DENOMINATION)
        self.assertEqual(result, Decimal("0"))


class GetCurrentCreditBalanceTest(BalancesTestBase):
    def setUp(self) -> None:
        self.tside = Tside.LIABILITY
        return super().setUp()

    def test_get_current_credit_balance_committed_and_pending_in_not_zero(self):
        balances = self.balances(
            default_committed=Decimal("100"),
            default_pending_outgoing=Decimal("-50"),
            default_pending_incoming=Decimal("30"),
        )
        result = utils.get_current_credit_balance(
            balances=balances, denomination=DEFAULT_DENOMINATION
        )
        self.assertEqual(result, Decimal("130"))

    def test_get_current_credit_balance_committed_zero_and_pending_in_not_zero(self):
        balances = self.balances(
            default_committed=Decimal("0"),
            default_pending_outgoing=Decimal("-50"),
            default_pending_incoming=Decimal("10"),
        )
        result = utils.get_current_credit_balance(
            balances=balances, denomination=DEFAULT_DENOMINATION
        )
        self.assertEqual(result, Decimal("10"))

    def test_get_current_credit_balance_committed_not_zero_and_pending_in_zero(self):
        balances = self.balances(
            default_committed=Decimal("100"),
            default_pending_outgoing=Decimal("0"),
            default_pending_incoming=Decimal("0"),
        )
        result = utils.get_current_credit_balance(
            balances=balances, denomination=DEFAULT_DENOMINATION
        )
        self.assertEqual(result, Decimal("100"))

    def test_get_current_credit_balance_both_committed_and_pending_in_are_zero(self):
        balances = self.balances(
            default_committed=Decimal("0"),
            default_pending_outgoing=Decimal("50"),
            default_pending_incoming=Decimal("0"),
        )
        result = utils.get_current_credit_balance(
            balances=balances, denomination=DEFAULT_DENOMINATION
        )
        self.assertEqual(result, Decimal("0"))


class GetCurrentDebitBalanceTest(BalancesTestBase):
    def setUp(self) -> None:
        self.tside = Tside.LIABILITY
        return super().setUp()

    def test_get_current_debit_balance_committed_and_pending_not_zero(self):
        balances = _BalanceDefaultDict(
            mapping={
                self.balance_coordinate(): self.balance(credit=Decimal("100"), debit=Decimal("10")),
                self.balance_coordinate(phase=Phase.PENDING_OUT): self.balance(
                    credit=Decimal("0"), debit=Decimal("10")
                ),
                self.balance_coordinate(phase=Phase.PENDING_IN): self.balance(
                    credit=Decimal("20"), debit=Decimal("10")
                ),
            }
        )
        result = utils.get_current_debit_balance(
            balances=balances, denomination=DEFAULT_DENOMINATION
        )
        self.assertEqual(result, Decimal("20"))

    def test_get_current_debit_balance_committed_zero_and_pending_not_zero(self):
        balances = _BalanceDefaultDict(
            mapping={
                self.balance_coordinate(): self.balance(net=Decimal("0")),
                self.balance_coordinate(phase=Phase.PENDING_OUT): self.balance(
                    credit=Decimal("0"), debit=Decimal("10")
                ),
                self.balance_coordinate(phase=Phase.PENDING_IN): self.balance(
                    credit=Decimal("20"), debit=Decimal("10")
                ),
            }
        )
        result = utils.get_current_debit_balance(
            balances=balances, denomination=DEFAULT_DENOMINATION
        )
        self.assertEqual(result, Decimal("10"))

    def test_get_current_debit_balance_committed_not_zero_and_pending_out_zero(self):
        balances = _BalanceDefaultDict(
            mapping={
                self.balance_coordinate(): self.balance(credit=Decimal("100"), debit=Decimal("10")),
                self.balance_coordinate(phase=Phase.PENDING_OUT): self.balance(net=Decimal("0")),
                self.balance_coordinate(phase=Phase.PENDING_IN): self.balance(
                    credit=Decimal("20"), debit=Decimal("10")
                ),
            }
        )
        result = utils.get_current_debit_balance(
            balances=balances, denomination=DEFAULT_DENOMINATION
        )
        self.assertEqual(result, Decimal("10"))

    def test_get_current_debit_balance_both_committed_and_pending_out_are_zero(self):
        balances = _BalanceDefaultDict(
            mapping={
                self.balance_coordinate(): self.balance(net=Decimal("0")),
                self.balance_coordinate(phase=Phase.PENDING_OUT): self.balance(net=Decimal("0")),
                self.balance_coordinate(phase=Phase.PENDING_IN): self.balance(
                    credit=Decimal("20"), debit=Decimal("10")
                ),
            }
        )
        result = utils.get_current_debit_balance(
            balances=balances, denomination=DEFAULT_DENOMINATION
        )
        self.assertEqual(result, Decimal("0"))


class GetBalanceDefaultDictFromMappingTest(BalancesTestBase):
    balance_1 = _Balance(net=Decimal("70"), debit=Decimal("100"), credit=Decimal("30"))
    balance_2 = _Balance(net=Decimal("40"), debit=Decimal("60"), credit=Decimal("20"))

    def ts_balance_mapping(
        self,
    ) -> Mapping[BalanceCoordinate, BalanceTimeseries]:
        return {
            self.balance_coordinate(): BalanceTimeseries(
                [
                    (DEFAULT_DATETIME + relativedelta(days=2), self.balance_1),
                    (DEFAULT_DATETIME, self.balance_2),
                ]
            ),
        }

    def test_returns_latest_default_dict_if_no_effective_datetime_provided(self):
        # construct expected result
        expected_result = BalanceDefaultDict(mapping={self.balance_coordinate(): self.balance_1})
        # run function
        result = utils.get_balance_default_dict_from_mapping(mapping=self.ts_balance_mapping())
        self.assertEqual(result, expected_result)

    def test_returns_default_dict_at_effective_datetime_if_provided(self):
        # construct expected result
        expected_result = BalanceDefaultDict(mapping={self.balance_coordinate(): self.balance_2})
        # run function
        result = utils.get_balance_default_dict_from_mapping(
            mapping=self.ts_balance_mapping(), effective_datetime=DEFAULT_DATETIME
        )
        self.assertEqual(result, expected_result)


class AverageBalance(BalancesTestBase):
    def test_average_balance(self):
        balances = [
            Decimal(100),
            Decimal(100),
            Decimal(100),
        ]

        result = utils.average_balance(balances=balances)

        self.assertEqual(result, Decimal(100))

    def test_average_balance_different_values(self):
        balances = [
            Decimal(100),
            Decimal(-50),
            Decimal(7.85),
        ]

        result = utils.average_balance(balances=balances)

        self.assertEqual(round(result, 2), round(Decimal(19.28), 2))

    def test_average_balance_empty_list(self):
        balances = []

        result = utils.average_balance(balances=balances)

        self.assertEqual(result, Decimal(0))


class UpdateInflightBalancesTest(BalancesTestBase):
    tside = Tside.LIABILITY

    def test_update_inflight_balances_empty_posting_instructions(self):
        current_balances = self.balances(
            default_committed=Decimal("100"), todays_spending=Decimal("10")
        )
        result = utils.update_inflight_balances(
            account_id=sentinel.account_id,
            tside=sentinel.tside,
            current_balances=current_balances,
            posting_instructions=[],
        )
        self.assertDictEqual(result, current_balances)

    def test_update_inflight_balances_non_empty_posting_instructions(self):
        current_balances = _BalanceDefaultDict(
            mapping={
                self.balance_coordinate(): self.balance(net=Decimal("100")),
                self.balance_coordinate(account_address="TODAYS_SPENDING"): self.balance(
                    net=Decimal("10")
                ),
            }
        )

        posting_instructions = [
            self.inbound_hard_settlement(
                amount=Decimal("20"),
                denomination=self.default_denomination,
                target_account_id=ACCOUNT_ID,
                internal_account_id="internal_account",
            ),
            CustomInstruction(
                postings=[
                    Posting(
                        credit=True,
                        amount=Decimal("10"),
                        denomination=self.default_denomination,
                        account_id=ACCOUNT_ID,
                        account_address="TODAYS_SPENDING",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    Posting(
                        credit=False,
                        amount=Decimal("10"),
                        denomination=self.default_denomination,
                        account_id=ACCOUNT_ID,
                        account_address="TODAYS_SAVINGS",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                ]
            ),
        ]

        expected_result = BalanceDefaultDict(
            mapping={
                self.balance_coordinate(): Balance(
                    net=Decimal("120"), credit=Decimal("120"), debit=Decimal("0")
                ),
                self.balance_coordinate(account_address="TODAYS_SPENDING"): Balance(
                    net=Decimal("20"), credit=Decimal("20"), debit=Decimal("0")
                ),
                self.balance_coordinate(account_address="TODAYS_SAVINGS"): Balance(
                    net=Decimal("-10"), credit=Decimal("0"), debit=Decimal("10")
                ),
            }
        )

        result = utils.update_inflight_balances(
            account_id=ACCOUNT_ID,
            tside=Tside.LIABILITY,
            current_balances=current_balances,
            posting_instructions=posting_instructions,
        )
        self.assertDictEqual(result, expected_result)


class GetPostingInstructionsBalances(BalancesTestBase):
    tside = Tside.LIABILITY

    def test_empty_posting_instructions(self):
        expected_result = BalanceDefaultDict()
        result = utils.get_posting_instructions_balances(
            posting_instructions=[],
        )
        self.assertDictEqual(result, expected_result)

    def test_non_empty_posting_instructions(self):
        posting_instructions = [
            self.inbound_hard_settlement(
                amount=Decimal("20"),
                denomination=self.default_denomination,
                target_account_id=ACCOUNT_ID,
                internal_account_id="internal_account",
            ),
            self.custom_instruction(
                postings=[
                    Posting(
                        credit=True,
                        amount=Decimal("10"),
                        denomination=self.default_denomination,
                        account_id=ACCOUNT_ID,
                        account_address="TODAYS_SPENDING",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    Posting(
                        credit=False,
                        amount=Decimal("10"),
                        denomination=self.default_denomination,
                        account_id=ACCOUNT_ID,
                        account_address="TODAYS_SAVINGS",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                ],
            ),
        ]

        expected_result = BalanceDefaultDict(
            mapping={
                self.balance_coordinate(): Balance(
                    net=Decimal("20"), credit=Decimal("20"), debit=Decimal("0")
                ),
                self.balance_coordinate(account_address="TODAYS_SPENDING"): Balance(
                    net=Decimal("10"), credit=Decimal("10"), debit=Decimal("0")
                ),
                self.balance_coordinate(account_address="TODAYS_SAVINGS"): Balance(
                    net=Decimal("-10"), credit=Decimal("0"), debit=Decimal("10")
                ),
            }
        )

        result = utils.get_posting_instructions_balances(
            posting_instructions=posting_instructions,
        )
        self.assertDictEqual(result, expected_result)


@patch.object(utils, "balance_at_coordinates")
@patch.object(utils, "create_postings")
class ResetTrackerBalancesTest(FeatureTest):
    address_list = ["ADDRESS_1", "ADDRESS_2"]

    def test_reset_tracker_balances_liability(
        self, mock_create_postings: MagicMock, mock_balance_at_coordinates: MagicMock
    ):
        mock_create_postings.return_value = [sentinel.postings]
        mock_balance_at_coordinates.return_value = Decimal("1")

        result = utils.reset_tracker_balances(
            balances=sentinel.balances,
            account_id=sentinel.account_id,
            tracker_addresses=self.address_list,
            contra_address=sentinel.contra_address,
            denomination=sentinel.denomination,
            tside=Tside.LIABILITY,
        )
        self.assertListEqual(result, [sentinel.postings] * 2)
        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.balances,
                    address="ADDRESS_1",
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=sentinel.balances,
                    address="ADDRESS_2",
                    denomination=sentinel.denomination,
                ),
            ]
        )

        mock_create_postings.assert_has_calls(
            calls=[
                call(
                    amount=Decimal("1"),
                    debit_account=sentinel.account_id,
                    credit_account=sentinel.account_id,
                    debit_address="ADDRESS_1",
                    credit_address=sentinel.contra_address,
                    denomination=sentinel.denomination,
                ),
                call(
                    amount=Decimal("1"),
                    debit_account=sentinel.account_id,
                    credit_account=sentinel.account_id,
                    debit_address="ADDRESS_2",
                    credit_address=sentinel.contra_address,
                    denomination=sentinel.denomination,
                ),
            ]
        )

    def test_reset_tracker_balances_asset(
        self, mock_create_postings: MagicMock, mock_balance_at_coordinates: MagicMock
    ):
        mock_create_postings.return_value = [sentinel.postings]
        mock_balance_at_coordinates.return_value = Decimal("1")

        result = utils.reset_tracker_balances(
            balances=sentinel.balances,
            account_id=sentinel.account_id,
            tracker_addresses=self.address_list,
            contra_address=sentinel.contra_address,
            denomination=sentinel.denomination,
            tside=Tside.ASSET,
        )
        self.assertListEqual(result, [sentinel.postings] * 2)
        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.balances,
                    address="ADDRESS_1",
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=sentinel.balances,
                    address="ADDRESS_2",
                    denomination=sentinel.denomination,
                ),
            ]
        )

        mock_create_postings.assert_has_calls(
            calls=[
                call(
                    amount=Decimal("1"),
                    debit_account=sentinel.account_id,
                    credit_account=sentinel.account_id,
                    debit_address=sentinel.contra_address,
                    credit_address="ADDRESS_1",
                    denomination=sentinel.denomination,
                ),
                call(
                    amount=Decimal("1"),
                    debit_account=sentinel.account_id,
                    credit_account=sentinel.account_id,
                    debit_address=sentinel.contra_address,
                    credit_address="ADDRESS_2",
                    denomination=sentinel.denomination,
                ),
            ]
        )

    def test_reset_tracker_balances_zero_balance(
        self, mock_create_postings: MagicMock, mock_balance_at_coordinates: MagicMock
    ):
        mock_create_postings.return_value = [sentinel.postings]
        mock_balance_at_coordinates.return_value = Decimal("0")

        result = utils.reset_tracker_balances(
            balances=sentinel.balances,
            account_id=sentinel.account_id,
            tracker_addresses=self.address_list,
            contra_address=sentinel.contra_address,
            denomination=sentinel.denomination,
            tside=Tside.ASSET,
        )
        self.assertListEqual(result, [])
        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.balances,
                    address="ADDRESS_1",
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=sentinel.balances,
                    address="ADDRESS_2",
                    denomination=sentinel.denomination,
                ),
            ]
        )
        mock_create_postings.assert_not_called()
