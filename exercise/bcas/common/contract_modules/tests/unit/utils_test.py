# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR, ROUND_HALF_DOWN
from json import dumps

# common
from inception_sdk.test_framework.contracts.unit.common import (
    ContractModuleTest,
    balance_dimensions,
)
from inception_sdk.vault.contracts.types_extension import (
    OptionalValue,
    InvalidContractParameter,
    Balance,
    BalanceDefaultDict,
    Phase,
    UnionItemValue,
)

# misc
CONTRACT_MODULE_FILE = "projects/gundala_s/common/contract_modules/utils.py"
DEFAULT_DATE = datetime(2021, 1, 1)
DEFAULT_DENOMINATION = "GBP"
DECIMAL_ZERO = Decimal(0)


def balances_wallet(
    dt=DEFAULT_DATE,
    default_balance=DECIMAL_ZERO,
    todays_spending=DECIMAL_ZERO,
    todays_gifts=DECIMAL_ZERO,
    default_pending_out=DECIMAL_ZERO,
    default_pending_in=DECIMAL_ZERO,
):

    balances = BalanceDefaultDict(
        lambda: Balance(),
        {
            balance_dimensions(denomination=DEFAULT_DENOMINATION): Balance(net=default_balance),
            balance_dimensions(
                address="TODAYS_SPENDING", denomination=DEFAULT_DENOMINATION
            ): Balance(net=todays_spending),
            balance_dimensions(address="TODAYS_GIFTS", denomination=DEFAULT_DENOMINATION): Balance(
                net=todays_gifts
            ),
            balance_dimensions(denomination=DEFAULT_DENOMINATION, phase=Phase.PENDING_OUT): Balance(
                net=default_pending_out
            ),
            balance_dimensions(denomination=DEFAULT_DENOMINATION, phase=Phase.PENDING_IN): Balance(
                net=default_pending_in
            ),
        },
    )
    return [(dt, balances)]


class UtilsModuleTest(ContractModuleTest):
    contract_module_file = CONTRACT_MODULE_FILE

    def create_mock(
        self,
        balance_ts=None,
        postings=None,
        creation_date=DEFAULT_DATE,
        client_transaction=None,
        flags=None,
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
            **kwargs,
        )

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
            result = self.run_function(
                function_name="get_parameter",
                vault_object=mock_vault,
                vault=mock_vault,
                name="test_parameter",
                at=test_case["at"],
                is_json=test_case["is_json"],
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_get_parameter_raise_error(self):
        mock_vault = self.create_mock(test_parameter={"test_key": "test_value"})

        with self.assertRaises(InvalidContractParameter) as ex:
            self.run_function(
                function_name="get_parameter",
                vault_object=mock_vault,
                vault=mock_vault,
                name="test_parameter",
                is_json=True,
            )

        self.assertIn(
            "Exception while JSON loading parameter",
            str(ex.exception),
        )

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
            result = self.run_function(
                function_name="get_parameter",
                vault_object=mock_vault,
                vault=mock_vault,
                name="test_parameter",
                union=test_case["union"],
                is_json=test_case["is_json"],
                optional=test_case["optional"],
                is_boolean=test_case["is_boolean"],
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_get_parameter_upper_case(self):
        test_cases = [
            {
                "description": "returns upper case dict of json parameter",
                "test_parameter": dumps({"test_parent_key": {"test_child_key": "test_value"}}),
                "upper_case_dict_values": True,
                "upper_case_list_values": False,
                "expected_result": {"test_parent_key": {"TEST_CHILD_KEY": "TEST_VALUE"}},
            },
            {
                "description": "returns upper case list of json parameter",
                "test_parameter": dumps({"test_key": ["test_value_1", "test_value_2"]}),
                "upper_case_dict_values": False,
                "upper_case_list_values": True,
                "expected_result": {"test_key": ["TEST_VALUE_1", "TEST_VALUE_2"]},
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock(test_parameter=test_case["test_parameter"])
            result = self.run_function(
                function_name="get_parameter",
                vault_object=mock_vault,
                vault=mock_vault,
                name="test_parameter",
                is_json=True,
                upper_case_dict_values=test_case["upper_case_dict_values"],
                upper_case_list_values=test_case["upper_case_list_values"],
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_importing_non_existing_function(self):
        with self.assertRaises(ValueError) as ex:
            self.run_function(
                function_name="non_existant_function",
                vault_object=None,
                amount=Decimal("5.555555"),
            )
        self.assertIn(
            'Function "non_existant_function" does not exist in provided Smart Contract code',
            str(ex.exception),
        )

    def test_str_to_bool(self):
        test_cases = [
            {
                "description": "returns true when string is true",
                "string": "true",
                "expected_result": True,
            },
            {
                "description": "returns true when string is mixed case",
                "string": "tRue",
                "expected_result": True,
            },
            {
                "description": "returns false when string is false",
                "string": "false",
                "expected_result": False,
            },
            {
                "description": "returns false when string is empty",
                "string": "",
                "expected_result": False,
            },
            {
                "description": "returns false when string is random text",
                "string": "abcd",
                "expected_result": False,
            },
        ]

        for test_case in test_cases:
            result = self.run_function(
                function_name="str_to_bool",
                vault_object=None,
                string=test_case["string"],
            )

            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_yearly_to_daily_rate_conversion(self):
        days_in_year = "365"
        expected_daily_rate = 1
        yearly_rate = Decimal("365")
        year = 2020
        result = self.run_function(
            function_name="yearly_to_daily_rate",
            vault_object=None,
            yearly_rate=yearly_rate,
            year=year,
            days_in_year=days_in_year,
        )
        self.assertEqual(result, expected_daily_rate)

    def test_yearly_to_daily_rate_converts_actual_days(self):
        input_data = [
            ("leap year", "actual", "0.0002732240437158469945355191257", 2020),
            ("non-leap year", "actual", "0.0002739726027397260273972602740", 2019),
            ("valid value", "360", "0.0002777777777777777777777777778", 2020),
            ("invalid value", "340", "0.0002732240437158469945355191257", 2020),
        ]

        yearly_rate = Decimal("0.10")

        for test_name, days_in_year, input_daily_rate, input_year in input_data:
            expected_daily_rate = Decimal(input_daily_rate)

            result = self.run_function(
                "yearly_to_daily_rate",
                vault_object=None,
                yearly_rate=yearly_rate,
                year=input_year,
                days_in_year=days_in_year,
            )

            self.assertEqual(result, expected_daily_rate, test_name)

    def test_is_leap_year(self):
        input_data = [
            ("leap year", 2020, True),
            ("non-leap year", 2019, False),
            ("future non-leap year", 2100, False),
            ("future leap year", 2400, True),
        ]

        for test_name, year, expected_output in input_data:
            result = self.run_function(
                function_name="is_leap_year",
                vault_object=None,
                year=year,
            )
            self.assertEqual(result, expected_output, test_name)

    def test_round_with_different_rounding_methods(self):
        input_data = [
            ("round_floor", ROUND_FLOOR, Decimal("15.45")),
            ("round half down", ROUND_HALF_DOWN, Decimal("15.46")),
            ("round half up", ROUND_HALF_UP, Decimal("15.46")),
        ]

        for test_name, rounding, expected_amount in input_data:
            result = self.run_function(
                function_name="round_decimal",
                vault_object=None,
                amount=Decimal("15.456"),
                decimal_places=2,
                rounding=rounding,
            )
            self.assertEqual(result, expected_amount, test_name)

    def test_round_with_different_precision(self):
        input_data = [
            ("0 dp", 0, Decimal("15")),
            ("2 dp", 2, Decimal("15.46")),
            ("5 dp", 5, Decimal("15.45556")),
        ]

        for test_name, decimal_places, expected_amount in input_data:
            result = self.run_function(
                function_name="round_decimal",
                vault_object=None,
                amount=Decimal("15.455555"),
                decimal_places=decimal_places,
                rounding=ROUND_HALF_UP,
            )
            self.assertEqual(result, expected_amount, test_name)

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
            days = self.run_function(
                function_name="rounded_days_between",
                vault_object=None,
                start_date=test_case["start_date"],
                end_date=test_case["end_date"],
            )

            self.assertEqual(days, test_case["expected_result"], test_case["description"])

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

        schedule_dict = self.run_function(
            function_name="create_schedule_dict_from_datetime",
            vault_object=None,
            schedule_datetime=schedule_datetime,
        )

        self.assertEqual(schedule_dict, expected_schedule_dict)

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

            is_flag_applied = self.run_function(
                function_name="is_flag_in_list_applied",
                vault_object=mock_vault,
                vault=mock_vault,
                parameter_name="list_of_flags",
                application_timestamp=test_case.get("application_timestamp"),
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
            has_parameter_value_changed = self.run_function(
                function_name="has_parameter_value_changed",
                vault_object=None,
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
            default_balance=Decimal("100"),
            todays_spending=Decimal("35.00"),
            todays_gifts=Decimal("10.00"),
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
        )

        for test_case in test_cases:
            result = self.run_function(
                function_name="get_balance_sum",
                vault_object=mock_vault,
                vault=mock_vault,
                addresses=test_case["addresses"],
            )

            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_get_transaction_type(self):
        test_cases = [
            {
                "description": "returns correct type from code",
                "instruction_details": {
                    "transaction_code": "00",
                },
                "txn_code_to_type_map": {
                    "00": "cash_advance",
                    "01": "purchase",
                },
                "default_txn_type": "purchase",
                "expected_result": "cash_advance",
            },
            {
                "description": "returns correct type for empty string code",
                "instruction_details": {"transaction_code": ""},
                "txn_code_to_type_map": {
                    "": "cash_advance",
                    "01": "purchase",
                },
                "default_txn_type": "default_purchase",
                "expected_result": "cash_advance",
            },
            {
                "description": "returns default type if code not in map",
                "instruction_details": {
                    "transaction_code": "04",
                },
                "txn_code_to_type_map": {
                    "00": "cash_advance",
                    "01": "purchase",
                },
                "default_txn_type": "default_purchase",
                "expected_result": "default_purchase",
            },
            {
                "description": "returns default type if no transaction_code",
                "instruction_details": {},
                "txn_code_to_type_map": {
                    "00": "cash_advance",
                    "01": "purchase",
                },
                "default_txn_type": "default_purchase",
                "expected_result": "default_purchase",
            },
        ]

        mock_vault = self.create_mock()

        for test_case in test_cases:
            result = self.run_function(
                function_name="get_transaction_type",
                vault_object=mock_vault,
                instruction_details=test_case["instruction_details"],
                txn_code_to_type_map=test_case["txn_code_to_type_map"],
                default_txn_type=test_case["default_txn_type"],
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

            result = self.run_function(
                "are_optional_parameters_set", mock_vault, mock_vault, parameters
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
                result = self.run_function(
                    "get_previous_schedule_execution_date",
                    mock_vault,
                    vault=mock_vault,
                    event_type=test_case["event_type"],
                    account_start_date=test_case["account_start_date"],
                )
            else:
                result = self.run_function(
                    "get_previous_schedule_execution_date",
                    mock_vault,
                    vault=mock_vault,
                    event_type=test_case["event_type"],
                )

            self.assertEqual(result, test_case["expected_result"])
