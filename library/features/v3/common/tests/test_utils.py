# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
from datetime import datetime, timezone
from decimal import Decimal
from json import dumps
from unittest.mock import call

from inception_sdk.test_framework.contracts.unit.common import (
    ContractFeatureTest,
    balance_dimensions,
    TimeSeries,
)
from inception_sdk.vault.contracts.types_extension import (
    BalancesObservation,
    CalendarEvent,
    CalendarEvents,
    EventTypeSchedule,
    Rejected,
    Tside,
    OptionalValue,
    Balance,
    BalanceDefaultDict,
    Phase,
    PostingInstructionBatch,
    UnionItemValue,
)
from library.features.v3.common import utils

# misc
FEATURE_FILE = "library/features/v3/common/utils.py"
DEFAULT_DATE = datetime(2021, 1, 1)
DEFAULT_DENOMINATION = "GBP"
DECIMAL_ZERO = Decimal(0)
# it's clumsy to assert on an unbounded number of decimal places so this is used to enforce
# decimal precision on assertions when converting from yearly rate
DEFAULT_DECIMAL_PRECISION = 10


def balances_wallet(
    dt=DEFAULT_DATE,
    default_committed=DECIMAL_ZERO,
    todays_spending=DECIMAL_ZERO,
    todays_gifts=DECIMAL_ZERO,
    default_pending_outgoing=DECIMAL_ZERO,
    default_pending_incoming=DECIMAL_ZERO,
):

    balances = BalanceDefaultDict(
        lambda: Balance(),
        {
            balance_dimensions(denomination=DEFAULT_DENOMINATION): Balance(net=default_committed),
            balance_dimensions(
                address="TODAYS_SPENDING", denomination=DEFAULT_DENOMINATION
            ): Balance(net=todays_spending),
            balance_dimensions(address="TODAYS_GIFTS", denomination=DEFAULT_DENOMINATION): Balance(
                net=todays_gifts
            ),
            balance_dimensions(denomination=DEFAULT_DENOMINATION, phase=Phase.PENDING_OUT): Balance(
                net=default_pending_outgoing
            ),
            balance_dimensions(denomination=DEFAULT_DENOMINATION, phase=Phase.PENDING_IN): Balance(
                net=default_pending_incoming
            ),
        },
    )
    return [(dt, balances)]


class UtilsV3Test(ContractFeatureTest):
    target_test_file = FEATURE_FILE
    side = Tside.ASSET

    def create_mock(
        self,
        balance_ts=None,
        postings=None,
        creation_date=DEFAULT_DATE,
        client_transaction=None,
        flags=None,
        calendar_events=None,
        **kwargs,
    ):
        balance_ts = balance_ts or []
        postings = postings or []
        client_transaction = client_transaction or {}
        flags = flags or []

        params = {
            key: {"value": value}
            for key, value in locals().items()
            if key not in self.locals_to_ignore
        }
        parameter_ts = self.param_map_to_timeseries(params, creation_date)
        return super().create_mock(
            balance_ts=balance_ts,
            parameter_ts=parameter_ts,
            postings=postings,
            creation_date=creation_date,
            client_transaction=client_transaction,
            flags=flags,
            calendar_events=calendar_events,
            **kwargs,
        )

    def test_yearly_to_daily_rate_conversion(self):
        days_in_year = "365"
        expected_daily_rate = 1
        yearly_rate = Decimal("365")
        year = 2020
        result = utils.yearly_to_daily_rate(
            yearly_rate=yearly_rate,
            year=year,
            days_in_year=days_in_year,
        )
        self.assertEqual(result, expected_daily_rate)

    def test_yearly_to_daily_rate_converts_actual_days(self):
        input_data = [
            ("leap year", "actual", "0.0002732240", 2020),
            ("non-leap year", "actual", "0.0002739726", 2019),
            ("valid value", "360", "0.0002777778", 2020),
            ("invalid value", "340", "0.0002732240", 2020),
        ]

        yearly_rate = Decimal("0.10")

        for test_name, days_in_year, input_daily_rate, input_year in input_data:
            expected_daily_rate = Decimal(input_daily_rate)

            result = round(
                utils.yearly_to_daily_rate(
                    yearly_rate=yearly_rate,
                    year=input_year,
                    days_in_year=days_in_year,
                ),
                DEFAULT_DECIMAL_PRECISION,
            )

            self.assertEqual(result, expected_daily_rate, test_name)

    def test_rounded_days_between_different_dates(self):
        test_cases = [
            {
                "description": "exact single day",
                "start_date": datetime(year=2019, month=1, day=1, hour=0, minute=0, second=0),
                "end_date": datetime(year=2019, month=1, day=2, hour=0, minute=0, second=0),
                "expected_result": 1,
            },
            {
                "description": "exact year",
                "start_date": datetime(year=2019, month=1, day=1, hour=0, minute=0, second=0),
                "end_date": datetime(year=2020, month=1, day=1, hour=0, minute=0, second=0),
                "expected_result": 365,
            },
            {
                "description": "fractional day",
                "start_date": datetime(year=2019, month=1, day=1, hour=0, minute=0, second=0),
                "end_date": datetime(year=2019, month=1, day=1, hour=0, minute=0, second=1),
                "expected_result": 1,
            },
            {
                "description": "fractional multiple days",
                "start_date": datetime(year=2019, month=1, day=1, hour=0, minute=0, second=0),
                "end_date": datetime(year=2019, month=1, day=2, hour=0, minute=0, second=1),
                "expected_result": 2,
            },
            {
                "description": "exact month",
                "start_date": datetime(year=2019, month=1, day=1, hour=0, minute=0, second=0),
                "end_date": datetime(year=2019, month=2, day=1, hour=0, minute=0, second=0),
                "expected_result": 31,
            },
            {
                "description": "fractional month",
                "start_date": datetime(year=2019, month=1, day=1, hour=0, minute=0, second=0),
                "end_date": datetime(year=2019, month=2, day=1, hour=5, minute=5, second=5),
                "expected_result": 32,
            },
            {
                "description": "fractional month past",
                "end_date": datetime(year=2019, month=1, day=1, hour=0, minute=0, second=0),
                "start_date": datetime(year=2019, month=2, day=1, hour=5, minute=5, second=5),
                "expected_result": -32,
            },
        ]
        for test_case in test_cases:
            days = utils.rounded_days_between(
                start_date=test_case["start_date"],
                end_date=test_case["end_date"],
            )
            self.assertEqual(days, test_case["expected_result"], test_case["description"])

    def test_get_parameter_values(self):
        test_cases = [
            {
                "description": "returns latest value of parameter",
                "test_parameter": "test_value",
                "at": None,
                "is_json": False,
                "expected_result": "test_value",
            },
            {
                "description": "returns value of parameter at timestamp",
                "test_parameter": "test_value",
                "at": DEFAULT_DATE,
                "is_json": False,
                "expected_result": "test_value",
            },
            {
                "description": "returns dict value of json parameter",
                "test_parameter": dumps({"test_key": "test_value"}),
                "at": None,
                "is_json": True,
                "expected_result": {"test_key": "test_value"},
            },
            {
                "description": "returns list value of json parameter",
                "test_parameter": dumps(["test_value"]),
                "at": None,
                "is_json": True,
                "expected_result": ["test_value"],
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock(test_parameter=test_case["test_parameter"])
            result = utils.get_parameter(
                vault=mock_vault,
                name="test_parameter",
                at=test_case["at"],
                is_json=test_case["is_json"],
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_get_parameter_optional(self):
        test_cases = [
            {
                "description": "returns parameter value when optional value is False",
                "test_parameter": "test_value",
                "optional": False,
                "is_json": False,
                "union": False,
                "is_boolean": False,
                "expected_result": "test_value",
            },
            {
                "description": "returns parameter value when optional value is True and "
                "is_set is True",
                "test_parameter": OptionalValue(value="test_value", is_set=True),
                "optional": True,
                "is_json": False,
                "union": False,
                "is_boolean": False,
                "expected_result": "test_value",
            },
            {
                "description": "returns None value when optional value is True and is_set is False",
                "test_parameter": OptionalValue(value="test_value", is_set=False),
                "optional": True,
                "is_json": False,
                "union": False,
                "is_boolean": False,
                "expected_result": None,
            },
            {
                "description": "returns None when value is None, optional value is True, and "
                "is_set is False",
                "test_parameter": OptionalValue(value=None, is_set=False),
                "optional": True,
                "is_json": False,
                "union": False,
                "is_boolean": False,
                "expected_result": None,
            },
            {
                "description": "returns param value when optional value is True, json is True, and "
                "is_set is True",
                "test_parameter": OptionalValue(value=dumps(["test_value"]), is_set=True),
                "optional": True,
                "is_json": True,
                "union": False,
                "is_boolean": False,
                "expected_result": ["test_value"],
            },
            {
                "description": "returns None value when json is True and is_set is False",
                "test_parameter": OptionalValue(is_set=False),
                "optional": True,
                "is_json": True,
                "union": False,
                "is_boolean": False,
                "expected_result": None,
            },
            {
                "description": "returns None when value is None, optional value is True, "
                "is_set is False, and is_json is True",
                "test_parameter": OptionalValue(value=None, is_set=False),
                "optional": True,
                "is_json": True,
                "union": False,
                "is_boolean": False,
                "expected_result": None,
            },
            {
                "description": "returns param value when value is None, optional value is True, "
                "is_set is False, and is_json is True",
                "test_parameter": dumps("test_value"),
                "optional": False,
                "is_json": True,
                "union": False,
                "is_boolean": False,
                "expected_result": "test_value",
            },
            {
                "description": "returns UnionItemValue value when union is True",
                "test_parameter": UnionItemValue(key="test_value"),
                "optional": False,
                "is_json": False,
                "union": True,
                "is_boolean": False,
                "expected_result": "test_value",
            },
            {
                "description": "returns UnionItemValue when union is True, optional is True,"
                " and is_set is True",
                "test_parameter": OptionalValue(
                    value=UnionItemValue(key="test_value"), is_set=True
                ),
                "optional": True,
                "is_json": False,
                "union": True,
                "is_boolean": False,
                "expected_result": "test_value",
            },
            {
                "description": "returns None value when union is True and is_set is False",
                "test_parameter": OptionalValue(
                    value=UnionItemValue(key="test_value"), is_set=False
                ),
                "optional": True,
                "is_json": False,
                "union": True,
                "is_boolean": False,
                "expected_result": None,
            },
            {
                "description": "converts True bool when union is True and is_boolean is True",
                "test_parameter": UnionItemValue(key="True"),
                "optional": False,
                "is_json": False,
                "union": True,
                "is_boolean": True,
                "expected_result": True,
            },
            {
                "description": "converts False bool when union is True and is_boolean is True",
                "test_parameter": UnionItemValue(key="False"),
                "optional": False,
                "is_json": False,
                "union": True,
                "is_boolean": True,
                "expected_result": False,
            },
            {
                "description": "converts True bool when union is False and is_boolean is True",
                "test_parameter": "True",
                "optional": False,
                "is_json": False,
                "union": False,
                "is_boolean": True,
                "expected_result": True,
            },
            {
                "description": "converts False bool when union is False and is_boolean is True",
                "test_parameter": "False",
                "optional": False,
                "is_json": False,
                "union": False,
                "is_boolean": True,
                "expected_result": False,
            },
            {
                "description": "returns False when optional param not set and is_boolean is True",
                "test_parameter": OptionalValue(is_set=False),
                "optional": False,
                "is_json": False,
                "union": False,
                "is_boolean": True,
                "expected_result": False,
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock(test_parameter=test_case["test_parameter"])
            result = utils.get_parameter(
                vault=mock_vault,
                name="test_parameter",
                union=test_case["union"],
                is_json=test_case["is_json"],
                optional=test_case["optional"],
                is_boolean=test_case["is_boolean"],
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_create_schedule_dict_from_datetime(self):
        schedule_datetime = datetime(year=2000, month=1, day=2, hour=3, minute=4, second=5)
        expected_schedule_dict = {
            "year": "2000",
            "month": "1",
            "day": "2",
            "hour": "3",
            "minute": "4",
            "second": "5",
        }

        schedule_dict = utils.create_schedule_dict_from_datetime(
            schedule_datetime=schedule_datetime
        )

        self.assertEqual(schedule_dict, expected_schedule_dict)

    def test_create_schedule_dict_from_datetime_not_one_off(self):
        schedule_datetime = datetime(year=2000, month=1, day=2, hour=3, minute=4, second=5)
        expected_schedule_dict = {
            "month": "1",
            "day": "2",
            "hour": "3",
            "minute": "4",
            "second": "5",
        }

        schedule_dict = utils.create_schedule_dict_from_datetime(
            schedule_datetime=schedule_datetime, one_off=False
        )

        self.assertEqual(schedule_dict, expected_schedule_dict)

    def test_get_daily_schedule(self):
        mock_vault = self.create_mock(my_prefix_hour=2, my_prefix_minute=3, my_prefix_second=4)
        daily_schedule = utils.get_daily_schedule(mock_vault, "my_prefix", "my_event")
        self.assertEqual(
            daily_schedule,
            utils.EventTuple(
                event_type="my_event",
                schedule={"hour": "2", "minute": "3", "second": "4"},
            ),
        )

    def test_get_next_schedule_day(self):

        test_cases = [
            {
                "description": "monthly schedule with effective day < day of month",
                "effective_date": datetime(year=2020, month=1, day=2, tzinfo=timezone.utc),
                "frequency": "monthly",
                "day_of_month": 5,
                "expected_result": datetime(2020, 1, 5, tzinfo=timezone.utc),
            },
            {
                "description": "monthly schedule with effective day > day of month",
                "effective_date": datetime(year=2020, month=1, day=2, tzinfo=timezone.utc),
                "frequency": "monthly",
                "day_of_month": 1,
                "expected_result": datetime(2020, 2, 1, tzinfo=timezone.utc),
            },
            {
                "description": "monthly schedule with calendar event",
                "effective_date": datetime(year=2020, month=1, day=2, tzinfo=timezone.utc),
                "frequency": "monthly",
                "day_of_month": 6,
                "expected_result": datetime(2020, 1, 8, tzinfo=timezone.utc),
            },
            {
                "description": "quarterly schedule with effective day > day of month",
                "effective_date": datetime(year=2020, month=1, day=2, tzinfo=timezone.utc),
                "frequency": "quarterly",
                "day_of_month": 1,
                "expected_result": datetime(2020, 4, 1, tzinfo=timezone.utc),
            },
            {
                "description": "quarterly schedule with effective day < day of month",
                "effective_date": datetime(year=2020, month=1, day=2, tzinfo=timezone.utc),
                "frequency": "quarterly",
                "day_of_month": 1,
                "expected_result": datetime(2020, 4, 1, tzinfo=timezone.utc),
            },
            {
                "description": "annually schedule with effective day > day of month",
                "effective_date": datetime(year=2020, month=1, day=2, tzinfo=timezone.utc),
                "frequency": "annually",
                "day_of_month": 1,
                "expected_result": datetime(2021, 1, 1, tzinfo=timezone.utc),
            },
            {
                "description": "annually schedule with effective day < day of month",
                "effective_date": datetime(year=2020, month=1, day=2, tzinfo=timezone.utc),
                "frequency": "annually",
                "day_of_month": 1,
                "expected_result": datetime(2021, 1, 1, tzinfo=timezone.utc),
            },
        ]
        calendar_events = CalendarEvents(
            [
                CalendarEvent(
                    start_timestamp=datetime(2020, 1, 6, tzinfo=timezone.utc),
                    end_timestamp=datetime(2020, 1, 7, tzinfo=timezone.utc),
                ),
            ]
        )
        mock_vault = self.create_mock(calendar_events=calendar_events)
        for test_case in test_cases:
            result = utils.get_next_schedule_day(
                mock_vault,
                test_case["effective_date"],
                test_case["frequency"],
                test_case["day_of_month"],
                calendar_events,
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_get_next_schedule_datetime(self):

        mock_vault = self.create_mock(my_prefix_hour=2, my_prefix_minute=3, my_prefix_second=4)
        next_datetime = utils.get_next_schedule_datetime(
            mock_vault,
            localised_effective_date=datetime(year=2020, month=1, day=6, tzinfo=timezone.utc),
            param_prefix="my_prefix",
            schedule_frequency="monthly",
            schedule_day_of_month=5,
            calendar_events=CalendarEvents([]),
        )
        self.assertEqual(next_datetime, datetime(2020, 2, 5, 2, 3, 4, tzinfo=timezone.utc))

    def test_falls_on_calendar_events_with_no_events(self):
        calendar_events = CalendarEvents(
            [
                CalendarEvent(
                    start_timestamp=datetime(2020, 1, 2, 3, tzinfo=timezone.utc),
                    end_timestamp=datetime(2020, 1, 2, 4, tzinfo=timezone.utc),
                ),
                CalendarEvent(
                    start_timestamp=datetime(2020, 1, 2, 4, tzinfo=timezone.utc),
                    end_timestamp=datetime(2020, 1, 2, 5, tzinfo=timezone.utc),
                ),
            ]
        )
        test_cases = [
            {
                "description": "effective_date on beginning of first event",
                "effective_date": datetime(year=2020, month=1, day=2, hour=3, tzinfo=timezone.utc),
                "expected_result": True,
            },
            {
                "description": "effective_date on end of second event",
                "effective_date": datetime(year=2020, month=1, day=2, hour=5, tzinfo=timezone.utc),
                "expected_result": True,
            },
            {
                "description": "effective_date before first event",
                "effective_date": datetime(year=2020, month=1, day=2, hour=2, tzinfo=timezone.utc),
                "expected_result": False,
            },
            {
                "description": "effective_date after second event",
                "effective_date": datetime(year=2020, month=1, day=2, hour=6, tzinfo=timezone.utc),
                "expected_result": False,
            },
        ]

        mock_vault = self.create_mock(calendar_events=CalendarEvents([CalendarEvent()]))
        for test_case in test_cases:
            result = utils.falls_on_calendar_events(
                mock_vault, test_case["effective_date"], calendar_events
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_is_flag_in_list_applied(self):
        test_cases = [
            {
                "description": "returns true if flag set",
                "test_flag": True,
                "expected_result": True,
            },
            {
                "description": "returns false if flag not set",
                "test_flag": False,
                "expected_result": False,
            },
            {
                "description": "test true with optional timestamp",
                "test_flag": True,
                "expected_result": True,
                "application_timestamp": datetime(2021, 1, 2),
            },
            {
                "description": "test false with optional timestamp",
                "test_flag": False,
                "expected_result": False,
                "application_timestamp": datetime(2021, 1, 2),
            },
        ]
        for test_case in test_cases:
            mock_vault = self.create_mock(
                list_of_flags=dumps(["test_flag"]),
                flags={
                    "test_flag": [
                        (
                            test_case.get("application_timestamp", DEFAULT_DATE),
                            test_case["test_flag"],
                        )
                    ]
                },
            )

            is_flag_applied = utils.is_flag_in_list_applied(
                vault=mock_vault,
                parameter_name="list_of_flags",
                application_timestamp=test_case.get("application_timestamp"),
            )

            self.assertEqual(
                is_flag_applied, test_case["expected_result"], test_case["description"]
            )

    def test_is_flag_in_list_applied_with_flag_ts_as_param(self):
        test_cases = [
            {
                "description": "returns true if flag set",
                "test_flag": True,
                "expected_result": True,
            },
            {
                "description": "returns false if flag not set",
                "test_flag": False,
                "expected_result": False,
            },
            {
                "description": "test true with optional timestamp",
                "test_flag": True,
                "expected_result": True,
                "application_timestamp": datetime(2021, 1, 2),
            },
            {
                "description": "test false with optional timestamp",
                "test_flag": False,
                "expected_result": False,
                "application_timestamp": datetime(2021, 1, 2),
            },
        ]
        for test_case in test_cases:
            is_flag_applied = utils.is_flag_in_list_applied(
                application_timestamp=test_case.get("application_timestamp"),
                flag_timeseries=[
                    # TODO(INC-6349): mock FlagTimeseries itself to avoid the type hints here
                    TimeSeries(
                        [
                            (
                                test_case.get("application_timestamp", DEFAULT_DATE),
                                test_case["test_flag"],
                            )
                        ]
                    )
                ],
            )

            self.assertEqual(
                is_flag_applied, test_case["expected_result"], test_case["description"]
            )

    def test_has_parameter_changed(self):
        test_cases = [
            {
                "description": "returns true if parameters have changed",
                "old_parameters": {"interest_application_day": "25"},
                "updated_parameters": {"interest_application_day": "21"},
                "expected_result": True,
            },
            {
                "description": "returns false if parameters have not changed",
                "old_parameters": {"interest_application_day": "25"},
                "updated_parameters": {"interest_application_day": "25"},
                "expected_result": False,
            },
            {
                "description": "returns false if updated parameters not previously present",
                "old_parameters": {"interest_application_day": "25"},
                "updated_parameters": {"new_param": "25"},
                "expected_result": False,
            },
        ]
        for test_case in test_cases:
            has_parameter_value_changed = utils.has_parameter_value_changed(
                parameter_name="interest_application_day",
                old_parameters=test_case["old_parameters"],
                updated_parameters=test_case["updated_parameters"],
            )
            self.assertEqual(
                has_parameter_value_changed,
                test_case["expected_result"],
                test_case["description"],
            )

    def test_get_balance_sum(self):
        test_cases = [
            {
                "description": "returns sum of single address",
                "addresses": ["DEFAULT"],
                "expected_result": Decimal("100"),
            },
            {
                "description": "returns sum of multiple addresses",
                "addresses": ["DEFAULT", "TODAYS_SPENDING"],
                "expected_result": Decimal("135"),
            },
        ]

        balance_ts = balances_wallet(
            DEFAULT_DATE,
            default_committed=Decimal("100"),
            todays_spending=Decimal("35.00"),
            todays_gifts=Decimal("10.00"),
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
        )

        for test_case in test_cases:
            result = utils.sum_balances(
                vault=mock_vault,
                addresses=test_case["addresses"],
            )

            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_get_balance_observation_sum(self):
        test_cases = [
            {
                "description": "returns sum of single address",
                "addresses": ["DEFAULT"],
                "expected_result": Decimal("100"),
            },
            {
                "description": "returns sum of multiple addresses",
                "addresses": ["DEFAULT", "TODAYS_SPENDING"],
                "expected_result": Decimal("135"),
            },
        ]

        balance_ts = balances_wallet(
            DEFAULT_DATE,
            default_committed=Decimal("100"),
            todays_spending=Decimal("35.00"),
            todays_gifts=Decimal("10.00"),
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            balances_observation_fetchers_mapping={
                "test_fetcher": BalancesObservation(balances=balance_ts[0][1])
            },
            denomination=DEFAULT_DENOMINATION,
        )

        for test_case in test_cases:
            result = utils.get_balance_observation_sum(
                vault=mock_vault, addresses=test_case["addresses"], fetcher_id="test_fetcher"
            )

            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_are_optional_parameters_set(self):
        test_cases = [
            {
                "description": "All parameters are set",
                "test_parameter_1": OptionalValue("1", is_set=True),
                "test_parameter_2": OptionalValue("2", is_set=True),
                "test_parameter_3": OptionalValue("3", is_set=True),
                "expected_result": True,
            },
            {
                "description": "Some parameters are set",
                "test_parameter_1": OptionalValue("1", is_set=True),
                "test_parameter_2": OptionalValue(is_set=False),
                "test_parameter_3": OptionalValue("3", is_set=True),
                "expected_result": False,
            },
            {
                "description": "No parameters are set",
                "test_parameter_1": OptionalValue(is_set=False),
                "test_parameter_2": OptionalValue(is_set=False),
                "test_parameter_3": OptionalValue(is_set=False),
                "expected_result": False,
            },
        ]

        for test_case in test_cases:

            mock_vault = self.create_mock(
                test_parameter_1=test_case["test_parameter_1"],
                test_parameter_2=test_case["test_parameter_2"],
                test_parameter_3=test_case["test_parameter_3"],
            )

            parameters = [
                "test_parameter_1",
                "test_parameter_2",
                "test_parameter_3",
            ]

            result = utils.are_optional_parameters_set(
                vault=mock_vault,
                parameters=parameters,
            )

            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_get_previous_schedule_execution_date(self):

        test_cases = [
            {
                "description": "last scheduled event & start dt exist - return last sch event",
                "event_type": "REPAYMENT_DAY_SCHEDULE",
                "account_start_date": "2019-01-01",
                "last_event_execution_date": datetime(2020, 2, 20, 0, 0, 3, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 2, 20, 0, 0, 3, tzinfo=timezone.utc),
            },
            {
                "description": "last scheduled event is empty, start dt exists  - return start dt",
                "event_type": "REPAYMENT_DAY_SCHEDULE",
                "account_start_date": datetime(2020, 2, 20, 0, 0, 3, tzinfo=timezone.utc),
                "last_event_execution_date": None,
                "expected_result": datetime(2020, 2, 20, 0, 0, 3, tzinfo=timezone.utc),
            },
            {
                "description": "last scheduled event is empty, start date exists - return start dt",
                "event_type": "REPAYMENT_DAY_SCHEDULE",
                "last_event_execution_date": datetime(2020, 2, 20, 0, 0, 3, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 2, 20, 0, 0, 3, tzinfo=timezone.utc),
            },
            {
                "description": "last scheduled event & start dt are empty - return default of None",
                "event_type": "REPAYMENT_DAY_SCHEDULE",
                "last_event_execution_date": None,
                "expected_result": None,
            },
        ]

        for test_case in test_cases:

            mock_vault = self.create_mock(
                REPAYMENT_DAY_SCHEDULE=test_case["last_event_execution_date"],
            )

            if "account_start_date" in test_case:
                result = utils.get_previous_schedule_execution_date(
                    vault=mock_vault,
                    event_type=test_case["event_type"],
                    account_start_date=test_case["account_start_date"],
                )
            else:
                result = utils.get_previous_schedule_execution_date(
                    vault=mock_vault,
                    event_type=test_case["event_type"],
                )

            self.assertEqual(result, test_case["expected_result"])

    def test_validate_denomination_invalid(self):
        self.side = Tside.LIABILITY
        vault = self.create_mock(denomination="AAA")
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_hard_settlement(amount=1000, denomination="AAA"),
                self.outbound_hard_settlement(amount=1000, denomination="BBB"),
                self.outbound_hard_settlement(amount=1000, denomination="AAA"),
            ]
        )
        accepted_denominations = ["AAA", "CCC"]
        with self.assertRaises(Rejected) as ex:
            utils.validate_denomination(
                vault=vault, accepted_denominations=accepted_denominations, postings=pib
            )
        self.assertEqual(
            ex.exception.message,
            "Cannot make transactions in the given denomination, transactions must be one of "
            "['AAA', 'CCC']",
        )

    def test_validate_denomination_valid(self):
        self.side = Tside.LIABILITY
        vault = self.create_mock(denomination="AAA")
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_hard_settlement(amount=1000, denomination="AAA"),
                self.outbound_hard_settlement(amount=1000, denomination="CCC"),
                self.outbound_hard_settlement(amount=1000, denomination="AAA"),
            ]
        )
        accepted_denominations = ["CCC", "AAA"]
        self.assertIsNone(
            utils.validate_denomination(
                vault=vault, accepted_denominations=accepted_denominations, postings=pib
            )
        )

    def test_validate_denomination_use_parameter(self):
        self.side = Tside.LIABILITY
        vault = self.create_mock(denomination="AAA")
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_hard_settlement(amount=1000, denomination="AAA"),
                self.outbound_hard_settlement(amount=1000, denomination="CCC"),
                self.outbound_hard_settlement(amount=1000, denomination="AAA"),
            ]
        )
        with self.assertRaises(Rejected) as ex:
            utils.validate_denomination(vault=vault, postings=pib)
        self.assertEqual(
            ex.exception.message,
            "Cannot make transactions in the given denomination, transactions must be one of "
            "['AAA']",
        )

    def test_validate_denomination_use_parameter_valid(self):
        self.side = Tside.LIABILITY
        vault = self.create_mock(denomination="AAA")
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_hard_settlement(amount=1000, denomination="AAA"),
                self.outbound_hard_settlement(amount=1000, denomination="AAA"),
                self.outbound_hard_settlement(amount=1000, denomination="AAA"),
            ]
        )
        self.assertIsNone(utils.validate_denomination(vault=vault, postings=pib))

    def test_is_force_override_true(self):
        test_cases = [
            {
                "description": "with force override",
                "batch_details": {"force_override": "True"},
                "expected_output": True,
            },
            {
                "description": "without force override",
                "batch_details": {},
                "expected_output": False,
            },
            {
                "description": "force override false",
                "batch_details": {"force_override": "False"},
                "expected_output": False,
            },
        ]

        for test_case in test_cases:

            pib = self.mock_posting_instruction_batch(
                posting_instructions=[
                    self.outbound_hard_settlement(amount=1000, denomination="AAA"),
                ],
                batch_details=test_case["batch_details"],
            )
            results = utils.is_force_override(pib)
            self.assertEqual(results, test_case["expected_output"], test_case["description"])

    def test_get_posting_amount(self):
        pending_out_posting = self.outbound_auth(
            denomination="GBP",
            amount=Decimal(100),
        )
        committed_posting = self.settle_outbound_auth(
            denomination="GBP",
            amount=Decimal(100),
            final=True,
            unsettled_amount=Decimal(100),
        )
        test_cases = [
            {
                "test_posting": pending_out_posting,
                "include_pending_out": True,
                "expected_result": Decimal(100),
            },
            {
                "test_posting": pending_out_posting,
                "include_pending_out": False,
                "expected_result": Decimal(0),
            },
            {
                "test_posting": committed_posting,
                "include_pending_out": True,
                "expected_result": Decimal(0),
            },
            {
                "test_posting": committed_posting,
                "include_pending_out": False,
                "expected_result": Decimal(100),
            },
        ]
        for test_case in test_cases:
            results = utils.get_posting_amount(
                test_case["test_posting"], test_case["include_pending_out"]
            )
            self.assertEqual(results, test_case["expected_result"])

    def test_create_event_type_schedule_from_datetime(self):
        schedule_datetime = datetime(year=2000, month=1, day=2, hour=3, minute=4, second=5)
        expected_event_type_schedule = EventTypeSchedule(
            day="2", hour="3", minute="4", second="5", month="1", year="2000"
        )
        result = utils.create_event_type_schedule_from_datetime(schedule_datetime)

        self.assertEqual(result.__dict__, expected_event_type_schedule.__dict__)

    def test_validate_amount_precision_raises_when_above_precision_round_up(self):
        with self.assertRaises(Rejected) as ctx:
            utils.validate_amount_precision(Decimal("1.2346"), 3)
        self.assertEqual(
            ctx.exception.message, "Amount 1.2346 has non-zero digits after 3 decimal places"
        )

    def test_validate_amount_precision_raises_when_above_precision_round_down(self):
        with self.assertRaises(Rejected) as ctx:
            utils.validate_amount_precision(Decimal("1.2344"), 3)
        self.assertEqual(
            ctx.exception.message, "Amount 1.2344 has non-zero digits after 3 decimal places"
        )

    def test_validate_amount_precision_does_not_raise_when_below_precision(self):
        self.assertIsNone(utils.validate_amount_precision(Decimal("1.234"), 3))

    def test_validate_amount_precision_does_not_raise_for_zero_digits_above_precision(self):
        self.assertIsNone(utils.validate_amount_precision(Decimal("1.2340"), 3))

    def test_validate_single_hard_settlement_raises_when_multiple_instructions_different_types(
        self,
    ):
        pib = PostingInstructionBatch(
            posting_instructions=[
                self.inbound_hard_settlement(amount=Decimal("5")),
                self.outbound_auth(amount=Decimal("6")),
            ]
        )
        with self.assertRaises(Rejected) as ctx:
            utils.validate_single_hard_settlement(pib)
        self.assertEqual(
            ctx.exception.message, "Only batches with a single hard settlement are supported"
        )

    def test_validate_single_hard_settlement_raises_when_multiple_instructions_hard_settlement(
        self,
    ):
        pib = PostingInstructionBatch(
            posting_instructions=[
                self.inbound_hard_settlement(amount=Decimal("5")),
                self.outbound_hard_settlement(amount=Decimal("6")),
            ]
        )
        with self.assertRaises(Rejected) as ctx:
            utils.validate_single_hard_settlement(pib)
        self.assertEqual(
            ctx.exception.message, "Only batches with a single hard settlement are supported"
        )

    def test_validate_amount_precision_raises_when_instruction_type_isnt_hard_settlement(self):
        pib = PostingInstructionBatch(
            posting_instructions=[
                self.outbound_auth(amount=Decimal("5")),
            ]
        )
        with self.assertRaises(Rejected) as ctx:
            utils.validate_single_hard_settlement(pib)
        self.assertEqual(
            ctx.exception.message, "Only batches with a single hard settlement are supported"
        )

    def test_validate_amount_precision_does_not_raise_for_single_hard_settlement(self):
        pib = PostingInstructionBatch(
            posting_instructions=[
                self.outbound_hard_settlement(amount=Decimal("5")),
            ]
        )

        self.assertIsNone(utils.validate_single_hard_settlement(pib))

    def test_aggregate_pib_delta_debit(self):
        mock_vault = self.create_mock()
        posting_instructions = self.mock_make_internal_transfer_instructions(
            make_instructions_return_full_objects=True,
            amount=Decimal(100),
            denomination="GBP",
            client_transaction_id="TEST_CTI",
            from_account_id="DRAWDOWN_1",
            from_account_address="PRINCIPAL",
            to_account_id="DRAWDOWN_1",
            to_account_address="DEFAULT",
            asset="TEST_ASSET",
            instruction_details={
                "test_key": "test_value",
            },
            custom_instruction_grouping_key="test_grouping_key",
            override_all_restrictions=True,
        )

        posting_instructions.extend(
            self.mock_make_internal_transfer_instructions(
                make_instructions_return_full_objects=True,
                amount=Decimal(500),
                denomination="GBP",
                client_transaction_id="TEST_CTI",
                from_account_id="DRAWDOWN_2",
                from_account_address="PRINCIPAL",
                to_account_id="DRAWDOWN_2",
                to_account_address="DEFAULT",
                asset="TEST_ASSET",
                instruction_details={
                    "test_key": "test_value",
                },
                custom_instruction_grouping_key="test_grouping_key",
                override_all_restrictions=True,
            )
        )

        self.assertIsNone(
            utils.instruct_aggregate_postings(
                vault=mock_vault,
                effective_date=DEFAULT_DATE,
                postings=posting_instructions,
                prefix="TOTAL",
                delta_addresses=["PRINCIPAL"],
            )
        )

        mock_vault.make_internal_transfer_instructions.assert_called_with(
            amount=Decimal("600"),
            denomination="GBP",
            client_transaction_id="AGGREGATE_TOTAL_PRINCIPAL_MOCK_HOOK",
            from_account_id="Main account",
            from_account_address="TOTAL_PRINCIPAL",
            to_account_id="Main account",
            to_account_address="INTERNAL_CONTRA",
            override_all_restrictions=True,
            instruction_details={
                "description": "aggregate balances",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            posting_instructions=["AGGREGATE_TOTAL_PRINCIPAL_MOCK_HOOK"],
            effective_date=DEFAULT_DATE,
            client_batch_id="AGGREGATE_LOC_MOCK_HOOK",
            batch_details={"force_override": "True"},
        )

    def test_aggregate_pib_delta_credit(self):
        mock_vault = self.create_mock()
        posting_instructions = self.mock_make_internal_transfer_instructions(
            make_instructions_return_full_objects=True,
            amount=Decimal(100),
            denomination="GBP",
            client_transaction_id="TEST_CTI",
            from_account_id="DRAWDOWN_1",
            from_account_address="DEFAULT",
            to_account_id="DRAWDOWN_1",
            to_account_address="PRINCIPAL",
            asset="TEST_ASSET",
            instruction_details={
                "test_key": "test_value",
            },
            custom_instruction_grouping_key="test_grouping_key",
            override_all_restrictions=True,
        )

        posting_instructions.extend(
            self.mock_make_internal_transfer_instructions(
                make_instructions_return_full_objects=True,
                amount=Decimal(500),
                denomination="GBP",
                client_transaction_id="TEST_CTI",
                from_account_id="DRAWDOWN_2",
                from_account_address="DEFAULT",
                to_account_id="DRAWDOWN_2",
                to_account_address="PRINCIPAL",
                asset="TEST_ASSET",
                instruction_details={
                    "test_key": "test_value",
                },
                custom_instruction_grouping_key="test_grouping_key",
                override_all_restrictions=True,
            )
        )

        self.assertIsNone(
            utils.instruct_aggregate_postings(
                vault=mock_vault,
                effective_date=DEFAULT_DATE,
                postings=posting_instructions,
                prefix="TOTAL",
                delta_addresses=["PRINCIPAL"],
            )
        )

        mock_vault.make_internal_transfer_instructions.assert_called_with(
            amount=Decimal("600"),
            denomination="GBP",
            client_transaction_id="AGGREGATE_TOTAL_PRINCIPAL_MOCK_HOOK",
            from_account_id="Main account",
            from_account_address="INTERNAL_CONTRA",
            to_account_id="Main account",
            to_account_address="TOTAL_PRINCIPAL",
            override_all_restrictions=True,
            instruction_details={
                "description": "aggregate balances",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            posting_instructions=["AGGREGATE_TOTAL_PRINCIPAL_MOCK_HOOK"],
            effective_date=DEFAULT_DATE,
            client_batch_id="AGGREGATE_LOC_MOCK_HOOK",
            batch_details={"force_override": "True"},
        )

    def test_aggregate_pib_delta_multiple_addresses(self):
        mock_vault = self.create_mock()
        posting_instructions = self.mock_make_internal_transfer_instructions(
            make_instructions_return_full_objects=True,
            amount=Decimal(100),
            denomination="GBP",
            client_transaction_id="TEST_CTI",
            from_account_id="DRAWDOWN_1",
            from_account_address="DEFAULT",
            to_account_id="DRAWDOWN_1",
            to_account_address="PRINCIPAL",
            asset="TEST_ASSET",
            instruction_details={
                "test_key": "test_value",
            },
            custom_instruction_grouping_key="test_grouping_key",
            override_all_restrictions=True,
        )

        posting_instructions.extend(
            self.mock_make_internal_transfer_instructions(
                make_instructions_return_full_objects=True,
                amount=Decimal(200),
                denomination="GBP",
                client_transaction_id="TEST_CTI",
                from_account_id="DRAWDOWN_1",
                from_account_address="DEFAULT",
                to_account_id="DRAWDOWN_1",
                to_account_address="PRINCIPAL",
                asset="TEST_ASSET",
                instruction_details={
                    "test_key": "test_value",
                },
                custom_instruction_grouping_key="test_grouping_key",
                override_all_restrictions=True,
            )
        )
        posting_instructions.extend(
            self.mock_make_internal_transfer_instructions(
                make_instructions_return_full_objects=True,
                amount=Decimal(300),
                denomination="GBP",
                client_transaction_id="TEST_CTI",
                from_account_id="DRAWDOWN_2",
                to_account_id="DRAWDOWN_2",
                from_account_address="DEFAULT",
                to_account_address="PRINCIPAL_DUE",
                asset="TEST_ASSET",
                instruction_details={
                    "test_key": "test_value",
                },
                custom_instruction_grouping_key="test_grouping_key",
                override_all_restrictions=True,
            )
        )

        posting_instructions.extend(
            self.mock_make_internal_transfer_instructions(
                make_instructions_return_full_objects=True,
                amount=Decimal(400),
                denomination="GBP",
                client_transaction_id="TEST_CTI",
                from_account_id="DRAWDOWN_2",
                from_account_address="DEFAULT",
                to_account_id="DRAWDOWN_2",
                to_account_address="PRINCIPAL_DUE",
                asset="TEST_ASSET",
                instruction_details={
                    "test_key": "test_value",
                },
                custom_instruction_grouping_key="test_grouping_key",
                override_all_restrictions=True,
            )
        )

        self.assertIsNone(
            utils.instruct_aggregate_postings(
                vault=mock_vault,
                effective_date=DEFAULT_DATE,
                postings=posting_instructions,
                prefix="TOTAL",
                delta_addresses=["PRINCIPAL", "PRINCIPAL_DUE"],
            )
        )

        expected_posting_calls = [
            call(
                amount=Decimal("300"),
                denomination="GBP",
                client_transaction_id="AGGREGATE_TOTAL_PRINCIPAL_MOCK_HOOK",
                from_account_id="Main account",
                from_account_address="INTERNAL_CONTRA",
                to_account_id="Main account",
                to_account_address="TOTAL_PRINCIPAL",
                override_all_restrictions=True,
                instruction_details={
                    "description": "aggregate balances",
                },
            ),
            call(
                amount=Decimal("700"),
                denomination="GBP",
                client_transaction_id="AGGREGATE_TOTAL_PRINCIPAL_DUE_MOCK_HOOK",
                from_account_id="Main account",
                from_account_address="INTERNAL_CONTRA",
                to_account_id="Main account",
                to_account_address="TOTAL_PRINCIPAL_DUE",
                override_all_restrictions=True,
                instruction_details={
                    "description": "aggregate balances",
                },
            ),
        ]

        mock_vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_aggregate_pib_delta_net_0_no_transfer(self):
        mock_vault = self.create_mock()
        posting_instructions = self.mock_make_internal_transfer_instructions(
            make_instructions_return_full_objects=True,
            amount=Decimal(500),
            denomination="GBP",
            client_transaction_id="TEST_CTI",
            from_account_id="DRAWDOWN_1",
            from_account_address="PRINCIPAL",
            to_account_id="DRAWDOWN_1",
            to_account_address="DEFAULT",
            asset="TEST_ASSET",
            instruction_details={
                "test_key": "test_value",
            },
            custom_instruction_grouping_key="test_grouping_key",
            override_all_restrictions=True,
        )

        posting_instructions.extend(
            self.mock_make_internal_transfer_instructions(
                make_instructions_return_full_objects=True,
                amount=Decimal(500),
                denomination="GBP",
                client_transaction_id="TEST_CTI",
                from_account_id="DRAWDOWN_2",
                from_account_address="DEFAULT",
                to_account_id="DRAWDOWN_2",
                to_account_address="PRINCIPAL",
                asset="TEST_ASSET",
                instruction_details={
                    "test_key": "test_value",
                },
                custom_instruction_grouping_key="test_grouping_key",
                override_all_restrictions=True,
            )
        )

        self.assertIsNone(
            utils.instruct_aggregate_postings(
                vault=mock_vault,
                effective_date=DEFAULT_DATE,
                postings=posting_instructions,
                prefix="TOTAL",
                delta_addresses=["PRINCIPAL"],
            )
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

        mock_vault.instruct_posting_batch.assert_not_called()

    def test_aggregate_pib_absolute_ignored_if_rounded_absolute_unchanged(self):
        mock_vault = self.create_mock()
        # balances are 100 and posting amount is 0.001, so rounded total 100 is unchanged
        posting_amount_1 = Decimal("0.001")
        posting_amount_2 = Decimal("0.001")
        mock_aggregated_vault_1 = self.create_mock(
            account_id="DRAWDOWN_1", balance_ts=balances_wallet(todays_spending=Decimal("100"))
        )
        mock_aggregated_vault_2 = self.create_mock(
            account_id="DRAWDOWN_2", balance_ts=balances_wallet(todays_spending=Decimal("100"))
        )
        posting_instructions = [
            *self.mock_make_internal_transfer_instructions(
                make_instructions_return_full_objects=True,
                amount=posting_amount_1,
                denomination="GBP",
                client_transaction_id="TEST_CTI",
                from_account_id="DRAWDOWN_1",
                from_account_address="TODAYS_SPENDING",
                to_account_id="DRAWDOWN_1",
                to_account_address="DEFAULT",
                asset="TEST_ASSET",
                instruction_details={
                    "test_key": "test_value",
                },
                custom_instruction_grouping_key="test_grouping_key",
                override_all_restrictions=True,
            ),
            *self.mock_make_internal_transfer_instructions(
                make_instructions_return_full_objects=True,
                amount=posting_amount_2,
                denomination="GBP",
                client_transaction_id="TEST_CTI",
                from_account_id="DRAWDOWN_2",
                from_account_address="TODAYS_SPENDING",
                to_account_id="DRAWDOWN_2",
                to_account_address="DEFAULT",
                asset="TEST_ASSET",
                instruction_details={
                    "test_key": "test_value",
                },
                custom_instruction_grouping_key="test_grouping_key",
                override_all_restrictions=True,
            ),
        ]

        self.assertIsNone(
            utils.instruct_aggregate_postings(
                vault=mock_vault,
                effective_date=DEFAULT_DATE,
                postings=posting_instructions,
                prefix="TOTAL",
                absolute_addresses=["TODAYS_SPENDING"],
                aggregated_vaults={
                    "DRAWDOWN_1": mock_aggregated_vault_1,
                    "DRAWDOWN_2": mock_aggregated_vault_2,
                },
            )
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_aggregate_pib_absolute_with_rounded_increase_on_single_account(self):
        mock_vault = self.create_mock()
        # rounded total will increase on account 1 only
        posting_amount_1 = Decimal("0.005")
        posting_amount_2 = Decimal("0.001")
        mock_aggregated_vault_1 = self.create_mock(
            account_id="DRAWDOWN_1", balance_ts=balances_wallet(todays_spending=Decimal("100"))
        )
        mock_aggregated_vault_2 = self.create_mock(
            account_id="DRAWDOWN_2", balance_ts=balances_wallet(todays_spending=Decimal("100"))
        )
        posting_instructions = [
            *self.mock_make_internal_transfer_instructions(
                make_instructions_return_full_objects=True,
                amount=posting_amount_1,
                denomination="GBP",
                client_transaction_id="TEST_CTI",
                from_account_id="DRAWDOWN_1",
                from_account_address="TODAYS_SPENDING",
                to_account_id="DRAWDOWN_1",
                to_account_address="DEFAULT",
                asset="TEST_ASSET",
                instruction_details={
                    "test_key": "test_value",
                },
                custom_instruction_grouping_key="test_grouping_key",
                override_all_restrictions=True,
            ),
            *self.mock_make_internal_transfer_instructions(
                make_instructions_return_full_objects=True,
                amount=posting_amount_2,
                denomination="GBP",
                client_transaction_id="TEST_CTI",
                from_account_id="DRAWDOWN_2",
                from_account_address="TODAYS_SPENDING",
                to_account_id="DRAWDOWN_2",
                to_account_address="DEFAULT",
                asset="TEST_ASSET",
                instruction_details={
                    "test_key": "test_value",
                },
                custom_instruction_grouping_key="test_grouping_key",
                override_all_restrictions=True,
            ),
        ]

        self.assertIsNone(
            utils.instruct_aggregate_postings(
                vault=mock_vault,
                effective_date=DEFAULT_DATE,
                postings=posting_instructions,
                prefix="TOTAL",
                absolute_addresses=["TODAYS_SPENDING"],
                aggregated_vaults={
                    "DRAWDOWN_1": mock_aggregated_vault_1,
                    "DRAWDOWN_2": mock_aggregated_vault_2,
                },
            )
        )

        mock_vault.make_internal_transfer_instructions.assert_called_with(
            amount=Decimal("0.01"),
            denomination="GBP",
            client_transaction_id="AGGREGATE_TOTAL_TODAYS_SPENDING_MOCK_HOOK",
            from_account_id="Main account",
            from_account_address="TOTAL_TODAYS_SPENDING",
            to_account_id="Main account",
            to_account_address="INTERNAL_CONTRA",
            override_all_restrictions=True,
            instruction_details={
                "description": "aggregate balances",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            posting_instructions=["AGGREGATE_TOTAL_TODAYS_SPENDING_MOCK_HOOK"],
            effective_date=DEFAULT_DATE,
            client_batch_id="AGGREGATE_LOC_MOCK_HOOK",
            batch_details={"force_override": "True"},
        )

    def test_aggregate_pib_absolute_with_rounded_increase_on_two_accounts(self):
        mock_vault = self.create_mock()
        # rounded total will increase on account 1 and 2
        posting_amount_1 = Decimal("0.005")
        posting_amount_2 = Decimal("0.005")
        mock_aggregated_vault_1 = self.create_mock(
            account_id="DRAWDOWN_1", balance_ts=balances_wallet(todays_spending=Decimal("100"))
        )
        mock_aggregated_vault_2 = self.create_mock(
            account_id="DRAWDOWN_2", balance_ts=balances_wallet(todays_spending=Decimal("100"))
        )
        posting_instructions = [
            *self.mock_make_internal_transfer_instructions(
                make_instructions_return_full_objects=True,
                amount=posting_amount_1,
                denomination="GBP",
                client_transaction_id="TEST_CTI",
                from_account_id="DRAWDOWN_1",
                from_account_address="TODAYS_SPENDING",
                to_account_id="DRAWDOWN_1",
                to_account_address="DEFAULT",
                asset="TEST_ASSET",
                instruction_details={
                    "test_key": "test_value",
                },
                custom_instruction_grouping_key="test_grouping_key",
                override_all_restrictions=True,
            ),
            *self.mock_make_internal_transfer_instructions(
                make_instructions_return_full_objects=True,
                amount=posting_amount_2,
                denomination="GBP",
                client_transaction_id="TEST_CTI",
                from_account_id="DRAWDOWN_2",
                from_account_address="TODAYS_SPENDING",
                to_account_id="DRAWDOWN_2",
                to_account_address="DEFAULT",
                asset="TEST_ASSET",
                instruction_details={
                    "test_key": "test_value",
                },
                custom_instruction_grouping_key="test_grouping_key",
                override_all_restrictions=True,
            ),
        ]

        self.assertIsNone(
            utils.instruct_aggregate_postings(
                vault=mock_vault,
                effective_date=DEFAULT_DATE,
                postings=posting_instructions,
                prefix="TOTAL",
                absolute_addresses=["TODAYS_SPENDING"],
                aggregated_vaults={
                    "DRAWDOWN_1": mock_aggregated_vault_1,
                    "DRAWDOWN_2": mock_aggregated_vault_2,
                },
            )
        )

        mock_vault.make_internal_transfer_instructions.assert_called_with(
            amount=Decimal("0.02"),
            denomination="GBP",
            client_transaction_id="AGGREGATE_TOTAL_TODAYS_SPENDING_MOCK_HOOK",
            from_account_id="Main account",
            from_account_address="TOTAL_TODAYS_SPENDING",
            to_account_id="Main account",
            to_account_address="INTERNAL_CONTRA",
            override_all_restrictions=True,
            instruction_details={
                "description": "aggregate balances",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            posting_instructions=["AGGREGATE_TOTAL_TODAYS_SPENDING_MOCK_HOOK"],
            effective_date=DEFAULT_DATE,
            client_batch_id="AGGREGATE_LOC_MOCK_HOOK",
            batch_details={"force_override": "True"},
        )

    def test_aggregate_pib_absolute_with_rounded_decrease_on_two_accounts(self):
        mock_vault = self.create_mock()
        # rounded total will decrease on account 1 and 2
        posting_amount_1 = Decimal("0.006")
        posting_amount_2 = Decimal("0.006")
        mock_aggregated_vault_1 = self.create_mock(
            account_id="DRAWDOWN_1", balance_ts=balances_wallet(todays_spending=Decimal("100"))
        )
        mock_aggregated_vault_2 = self.create_mock(
            account_id="DRAWDOWN_2", balance_ts=balances_wallet(todays_spending=Decimal("100"))
        )
        posting_instructions = [
            *self.mock_make_internal_transfer_instructions(
                make_instructions_return_full_objects=True,
                amount=posting_amount_1,
                denomination="GBP",
                client_transaction_id="TEST_CTI",
                # This direction results in a balance decrease for TSIDE ASSET
                from_account_id="DRAWDOWN_2",
                from_account_address="DEFAULT",
                to_account_id="DRAWDOWN_2",
                to_account_address="TODAYS_SPENDING",
                asset="TEST_ASSET",
                instruction_details={
                    "test_key": "test_value",
                },
                custom_instruction_grouping_key="test_grouping_key",
                override_all_restrictions=True,
            ),
            *self.mock_make_internal_transfer_instructions(
                make_instructions_return_full_objects=True,
                amount=posting_amount_2,
                denomination="GBP",
                client_transaction_id="TEST_CTI",
                # This direction results in a balance decrease for TSIDE ASSET
                from_account_id="DRAWDOWN_2",
                from_account_address="DEFAULT",
                to_account_id="DRAWDOWN_2",
                to_account_address="TODAYS_SPENDING",
                asset="TEST_ASSET",
                instruction_details={
                    "test_key": "test_value",
                },
                custom_instruction_grouping_key="test_grouping_key",
                override_all_restrictions=True,
            ),
        ]

        self.assertIsNone(
            utils.instruct_aggregate_postings(
                vault=mock_vault,
                effective_date=DEFAULT_DATE,
                postings=posting_instructions,
                prefix="TOTAL",
                absolute_addresses=["TODAYS_SPENDING"],
                aggregated_vaults={
                    "DRAWDOWN_1": mock_aggregated_vault_1,
                    "DRAWDOWN_2": mock_aggregated_vault_2,
                },
            )
        )

        mock_vault.make_internal_transfer_instructions.assert_called_with(
            amount=Decimal("0.02"),
            denomination="GBP",
            client_transaction_id="AGGREGATE_TOTAL_TODAYS_SPENDING_MOCK_HOOK",
            from_account_id="Main account",
            from_account_address="INTERNAL_CONTRA",
            to_account_id="Main account",
            to_account_address="TOTAL_TODAYS_SPENDING",
            override_all_restrictions=True,
            instruction_details={
                "description": "aggregate balances",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            posting_instructions=["AGGREGATE_TOTAL_TODAYS_SPENDING_MOCK_HOOK"],
            effective_date=DEFAULT_DATE,
            client_batch_id="AGGREGATE_LOC_MOCK_HOOK",
            batch_details={"force_override": "True"},
        )

    def test_aggregate_pib_absolute_with_net_zero_rounded_change_on_two_account(self):
        mock_vault = self.create_mock()
        # rounded total will increase on account 1 and decrease on account 2 by same amount so no
        # aggregate change
        posting_amount_1 = Decimal("0.005")
        posting_amount_2 = Decimal("0.006")
        mock_aggregated_vault_1 = self.create_mock(
            account_id="DRAWDOWN_1", balance_ts=balances_wallet(todays_spending=Decimal("100"))
        )
        mock_aggregated_vault_2 = self.create_mock(
            account_id="DRAWDOWN_2", balance_ts=balances_wallet(todays_spending=Decimal("100"))
        )
        posting_instructions = [
            *self.mock_make_internal_transfer_instructions(
                make_instructions_return_full_objects=True,
                amount=posting_amount_1,
                denomination="GBP",
                client_transaction_id="TEST_CTI",
                from_account_id="DRAWDOWN_1",
                from_account_address="TODAYS_SPENDING",
                to_account_id="DRAWDOWN_1",
                to_account_address="DEFAULT",
                asset="TEST_ASSET",
                instruction_details={
                    "test_key": "test_value",
                },
                custom_instruction_grouping_key="test_grouping_key",
                override_all_restrictions=True,
            ),
            *self.mock_make_internal_transfer_instructions(
                make_instructions_return_full_objects=True,
                amount=posting_amount_2,
                denomination="GBP",
                client_transaction_id="TEST_CTI",
                # This direction results in a balance decrease for TSIDE ASSET
                from_account_id="DRAWDOWN_2",
                from_account_address="DEFAULT",
                to_account_id="DRAWDOWN_2",
                to_account_address="TODAYS_SPENDING",
                asset="TEST_ASSET",
                instruction_details={
                    "test_key": "test_value",
                },
                custom_instruction_grouping_key="test_grouping_key",
                override_all_restrictions=True,
            ),
        ]

        self.assertIsNone(
            utils.instruct_aggregate_postings(
                vault=mock_vault,
                effective_date=DEFAULT_DATE,
                postings=posting_instructions,
                prefix="TOTAL",
                absolute_addresses=["TODAYS_SPENDING"],
                aggregated_vaults={
                    "DRAWDOWN_1": mock_aggregated_vault_1,
                    "DRAWDOWN_2": mock_aggregated_vault_2,
                },
            )
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

        mock_vault.instruct_posting_batch.assert_not_called()

    def test_aggregate_pib_absolute_with_change_no_rounding(self):
        mock_vault = self.create_mock()
        # rounded total will change on account 1 and 2, but in opposite directions, so no aggregate
        # change
        posting_amount_1 = Decimal("0.1")
        posting_amount_2 = Decimal("1.4")
        mock_aggregated_vault_1 = self.create_mock(
            account_id="DRAWDOWN_1", balance_ts=balances_wallet(todays_spending=Decimal("100"))
        )
        mock_aggregated_vault_2 = self.create_mock(
            account_id="DRAWDOWN_2", balance_ts=balances_wallet(todays_spending=Decimal("100"))
        )
        posting_instructions = [
            *self.mock_make_internal_transfer_instructions(
                make_instructions_return_full_objects=True,
                amount=posting_amount_1,
                denomination="GBP",
                client_transaction_id="TEST_CTI",
                from_account_id="DRAWDOWN_1",
                from_account_address="TODAYS_SPENDING",
                to_account_id="DRAWDOWN_1",
                to_account_address="DEFAULT",
                asset="TEST_ASSET",
                instruction_details={
                    "test_key": "test_value",
                },
                custom_instruction_grouping_key="test_grouping_key",
                override_all_restrictions=True,
            ),
            *self.mock_make_internal_transfer_instructions(
                make_instructions_return_full_objects=True,
                amount=posting_amount_2,
                denomination="GBP",
                client_transaction_id="TEST_CTI",
                from_account_id="DRAWDOWN_2",
                from_account_address="TODAYS_SPENDING",
                to_account_id="DRAWDOWN_2",
                to_account_address="DEFAULT",
                asset="TEST_ASSET",
                instruction_details={
                    "test_key": "test_value",
                },
                custom_instruction_grouping_key="test_grouping_key",
                override_all_restrictions=True,
            ),
        ]

        self.assertIsNone(
            utils.instruct_aggregate_postings(
                vault=mock_vault,
                effective_date=DEFAULT_DATE,
                postings=posting_instructions,
                prefix="TOTAL",
                absolute_addresses=["TODAYS_SPENDING"],
                aggregated_vaults={
                    "DRAWDOWN_1": mock_aggregated_vault_1,
                    "DRAWDOWN_2": mock_aggregated_vault_2,
                },
            )
        )

        mock_vault.make_internal_transfer_instructions.assert_called_with(
            amount=Decimal("1.50"),
            denomination="GBP",
            client_transaction_id="AGGREGATE_TOTAL_TODAYS_SPENDING_MOCK_HOOK",
            from_account_id="Main account",
            from_account_address="TOTAL_TODAYS_SPENDING",
            to_account_id="Main account",
            to_account_address="INTERNAL_CONTRA",
            override_all_restrictions=True,
            instruction_details={
                "description": "aggregate balances",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            posting_instructions=["AGGREGATE_TOTAL_TODAYS_SPENDING_MOCK_HOOK"],
            effective_date=DEFAULT_DATE,
            client_batch_id="AGGREGATE_LOC_MOCK_HOOK",
            batch_details={"force_override": "True"},
        )

    def test_aggregate_pib_absolute_and_delta(self):
        mock_vault = self.create_mock()
        # rounded total will increase on account 1 only, delta amount on posting amount 2
        # also reflected
        posting_amount_1 = Decimal("0.005")
        posting_amount_2 = Decimal("0.2")
        mock_aggregated_vault_1 = self.create_mock(
            account_id="DRAWDOWN_1", balance_ts=balances_wallet(todays_spending=Decimal("100"))
        )
        mock_aggregated_vault_2 = self.create_mock(
            account_id="DRAWDOWN_2", balance_ts=balances_wallet(todays_spending=Decimal("100"))
        )
        posting_instructions = [
            *self.mock_make_internal_transfer_instructions(
                make_instructions_return_full_objects=True,
                amount=posting_amount_1,
                denomination="GBP",
                client_transaction_id="TEST_CTI",
                from_account_id="DRAWDOWN_1",
                from_account_address="TODAYS_SPENDING",
                to_account_id="DRAWDOWN_1",
                to_account_address="DEFAULT",
                asset="TEST_ASSET",
                instruction_details={
                    "test_key": "test_value",
                },
                custom_instruction_grouping_key="test_grouping_key",
                override_all_restrictions=True,
            ),
            *self.mock_make_internal_transfer_instructions(
                make_instructions_return_full_objects=True,
                amount=posting_amount_2,
                denomination="GBP",
                client_transaction_id="TEST_CTI",
                from_account_id="DRAWDOWN_2",
                from_account_address="PRINCIPAL",
                to_account_id="DRAWDOWN_2",
                to_account_address="DEFAULT",
                asset="TEST_ASSET",
                instruction_details={
                    "test_key": "test_value",
                },
                custom_instruction_grouping_key="test_grouping_key",
                override_all_restrictions=True,
            ),
        ]

        self.assertIsNone(
            utils.instruct_aggregate_postings(
                vault=mock_vault,
                effective_date=DEFAULT_DATE,
                postings=posting_instructions,
                prefix="TOTAL",
                delta_addresses=["PRINCIPAL"],
                absolute_addresses=["TODAYS_SPENDING"],
                aggregated_vaults={
                    "DRAWDOWN_1": mock_aggregated_vault_1,
                    "DRAWDOWN_2": mock_aggregated_vault_2,
                },
            )
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("0.2"),
                    denomination="GBP",
                    client_transaction_id="AGGREGATE_TOTAL_PRINCIPAL_MOCK_HOOK",
                    from_account_id="Main account",
                    from_account_address="TOTAL_PRINCIPAL",
                    to_account_id="Main account",
                    to_account_address="INTERNAL_CONTRA",
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "aggregate balances",
                    },
                ),
                call(
                    amount=Decimal("0.01"),
                    denomination="GBP",
                    client_transaction_id="AGGREGATE_TOTAL_TODAYS_SPENDING_MOCK_HOOK",
                    from_account_id="Main account",
                    from_account_address="TOTAL_TODAYS_SPENDING",
                    to_account_id="Main account",
                    to_account_address="INTERNAL_CONTRA",
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "aggregate balances",
                    },
                ),
            ]
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            posting_instructions=[
                "AGGREGATE_TOTAL_PRINCIPAL_MOCK_HOOK",
                "AGGREGATE_TOTAL_TODAYS_SPENDING_MOCK_HOOK",
            ],
            effective_date=DEFAULT_DATE,
            client_batch_id="AGGREGATE_LOC_MOCK_HOOK",
            batch_details={"force_override": "True"},
        )

    def test_aggregate_pib_ignores_empty_list_of_postings(self):
        mock_vault = self.create_mock()
        posting_instructions = []
        self.assertIsNone(
            utils.instruct_aggregate_postings(
                vault=mock_vault,
                effective_date=DEFAULT_DATE,
                postings=posting_instructions,
                prefix="TOTAL",
                delta_addresses=["PRINCIPAL"],
            )
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

        mock_vault.instruct_posting_batch.assert_not_called()

    def test_get_available_balance(self):
        test_cases = [
            {
                "description": "returns available balance",
                "default_committed_balance": Decimal("100"),
                "default_pending_outgoing_balance": Decimal("-50"),
                "default_pending_incoming_balance": Decimal("30"),
                "expected_result": Decimal("50"),
            },
            {
                "description": "returns available balance when 0 default balance",
                "default_committed_balance": Decimal("0"),
                "default_pending_outgoing_balance": Decimal("-50"),
                "default_pending_incoming_balance": Decimal("30"),
                "expected_result": Decimal("-50"),
            },
            {
                "description": "returns available balance when 0 pending balance",
                "default_committed_balance": Decimal("100"),
                "default_pending_outgoing_balance": Decimal("0"),
                "default_pending_incoming_balance": Decimal("0"),
                "expected_result": Decimal("100"),
            },
            {
                "description": "returns available balance when 0 balance",
                "default_committed_balance": Decimal("0"),
                "default_pending_outgoing_balance": Decimal("0"),
                "default_pending_incoming_balance": Decimal("0"),
                "expected_result": Decimal("0"),
            },
        ]
        for test_case in test_cases:
            balance_ts = balances_wallet(
                DEFAULT_DATE,
                default_committed=test_case["default_committed_balance"],
                default_pending_outgoing=test_case["default_pending_outgoing_balance"],
                default_pending_incoming=test_case["default_pending_incoming_balance"],
            )

            result = utils.get_available_balance(
                balances=balance_ts[0][1], denomination=DEFAULT_DENOMINATION
            )

            self.assertEqual(result, test_case["expected_result"], test_case["description"])
