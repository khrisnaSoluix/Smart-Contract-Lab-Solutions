# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from zoneinfo import ZoneInfo

# library
from library.shariah_savings_account.contracts.template import shariah_savings_account
from library.shariah_savings_account.test import accounts, dimensions, files, parameters
from library.shariah_savings_account.test.simulation.accounts import default_internal_accounts

# inception sdk
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ExpectedSchedule,
    SimulationTestScenario,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_account_product_version_update_instruction,
    create_calendar,
    create_calendar_event,
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
)
from inception_sdk.test_framework.contracts.simulation.utils import SimulationTestCase

PUBLIC_HOLIDAYS = "PUBLIC_HOLIDAYS"

default_instance_params = parameters.default_instance
default_template_params = parameters.default_template


class ShariahSavingsAccountTest(SimulationTestCase):

    account_id_base = accounts.SHARIAH_SAVINGS_ACCOUNT
    contract_filepaths = [files.CONTRACT_FILE]

    def get_simulation_test_scenario(
        self,
        start,
        end,
        sub_tests,
        template_params=None,
        instance_params=None,
        internal_accounts=None,
    ):
        contract_config = ContractConfig(
            contract_content=self.smart_contract_path_to_content[files.CONTRACT_FILE],
            template_params=template_params or default_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or default_instance_params,
                    account_id_base=self.account_id_base,
                )
            ],
        )
        return SimulationTestScenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            contract_config=contract_config,
            internal_accounts=internal_accounts or default_internal_accounts,
        )

    def test_schedules(self):
        """
        Test that the correct profit accrual, application and maintenance fee schedules are
        created when the account is instantiated.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=2, day=2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "profit_application_day": "1",
        }

        # Get accrue profit schedules
        run_times_accrue_profit = []
        accrue_profit_date = start
        accrue_profit_date = accrue_profit_date.replace(
            hour=int(default_template_params["profit_accrual_hour"]),
            minute=int(default_template_params["profit_accrual_minute"]),
            second=int(default_template_params["profit_accrual_second"]),
        )
        run_times_accrue_profit.append(accrue_profit_date)
        for _ in range(32):
            accrue_profit_date = accrue_profit_date + relativedelta(days=1)
            run_times_accrue_profit.append(accrue_profit_date)

        first_application_date = (start + relativedelta(months=1)).replace(
            day=int(instance_params["profit_application_day"]),
            hour=int(default_template_params["profit_application_hour"]),
            minute=int(default_template_params["profit_application_minute"]),
            second=int(default_template_params["profit_application_second"]),
        )

        sub_tests = [
            SubTest(
                description="Check schedules",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=run_times_accrue_profit,
                        event_id="ACCRUE_PROFIT",
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        count=33,
                    ),
                    ExpectedSchedule(
                        run_times=[first_application_date],
                        event_id="APPLY_PROFIT",
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        count=1,
                    ),
                ],
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_schedules_are_preserved_after_conversion(self):
        """
        Instantiate an account with the same profit accrual and application schedules as in the
        above test_schedules test case.

        Convert the account before the first schedule run and also midcycle

        Observe the same schedule timings as expected prior to the two conversions.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=2, day=2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "profit_application_day": "1",
        }

        # Get accrue profit schedules
        run_times_accrue_profit = []
        accrue_profit_date = start
        accrue_profit_date = accrue_profit_date.replace(
            hour=int(default_template_params["profit_accrual_hour"]),
            minute=int(default_template_params["profit_accrual_minute"]),
            second=int(default_template_params["profit_accrual_second"]),
        )
        run_times_accrue_profit.append(accrue_profit_date)
        for _ in range(32):
            accrue_profit_date = accrue_profit_date + relativedelta(days=1)
            run_times_accrue_profit.append(accrue_profit_date)

        first_application_date = (start + relativedelta(months=1)).replace(
            day=int(instance_params["profit_application_day"]),
            hour=int(default_template_params["profit_application_hour"]),
            minute=int(default_template_params["profit_application_minute"]),
            second=int(default_template_params["profit_application_second"]),
        )

        conversion_1 = start + relativedelta(seconds=1)
        convert_to_version_id_1 = "5"
        convert_to_contract_config_1 = ContractConfig(
            contract_content=self.smart_contract_path_to_content[files.CONTRACT_FILE],
            smart_contract_version_id=convert_to_version_id_1,
            template_params=default_template_params,
            account_configs=[],
        )
        conversion_2 = conversion_1 + relativedelta(days=15)
        convert_to_version_id_2 = "6"
        convert_to_contract_config_2 = ContractConfig(
            contract_content=self.smart_contract_path_to_content[files.CONTRACT_FILE],
            smart_contract_version_id=convert_to_version_id_2,
            template_params=default_template_params,
            account_configs=[],
        )

        sub_tests = [
            SubTest(
                description="Trigger Conversions and Check Schedules at EoM",
                events=[
                    create_account_product_version_update_instruction(
                        timestamp=conversion_1,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        product_version_id=convert_to_version_id_1,
                    ),
                    create_account_product_version_update_instruction(
                        timestamp=conversion_2,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        product_version_id=convert_to_version_id_2,
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=run_times_accrue_profit,
                        event_id="ACCRUE_PROFIT",
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        count=33,
                    ),
                    ExpectedSchedule(
                        run_times=[first_application_date],
                        event_id="APPLY_PROFIT",
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        count=1,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )

        self.run_test_scenario(
            test_scenario,
            smart_contracts=[convert_to_contract_config_1, convert_to_contract_config_2],
        )

    def test_account_schedules_apply_accrue_profit_monthly(self):
        """
        Test if the schedules runtime of the apply accrue profit are correct when the frequency is
        set to monthly and when the application creation date falls on the end of the month dates
        29, 30, 31.
        """
        start = datetime(year=2019, month=1, day=29, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=3, day=30, hour=23, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "profit_application_day": "30",
        }

        first_application_date = datetime(
            year=2019,
            month=1,
            day=30,
            hour=int(default_template_params["profit_application_hour"]),
            minute=int(default_template_params["profit_application_minute"]),
            second=int(default_template_params["profit_application_second"]),
            tzinfo=ZoneInfo("UTC"),
        )
        second_application_date = datetime(
            year=2019,
            month=2,
            day=28,
            hour=int(default_template_params["profit_application_hour"]),
            minute=int(default_template_params["profit_application_minute"]),
            second=int(default_template_params["profit_application_second"]),
            tzinfo=ZoneInfo("UTC"),
        )
        third_application_date = datetime(
            year=2019,
            month=3,
            day=30,
            hour=int(default_template_params["profit_application_hour"]),
            minute=int(default_template_params["profit_application_minute"]),
            second=int(default_template_params["profit_application_second"]),
            tzinfo=ZoneInfo("UTC"),
        )

        sub_tests = [
            SubTest(
                description="Fund account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="20000",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination="MYR",
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "20000"),
                        ]
                    }
                },
            ),
            SubTest(
                description="Ensure montly apply profit schedule runtime and amounts are correct",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            first_application_date,
                            second_application_date,
                            third_application_date,
                        ],
                        event_id="APPLY_PROFIT",
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        count=3,
                    )
                ],
                expected_balances_at_ts={
                    first_application_date: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "20008.16"),
                            (dimensions.ACCRUED_PROFIT_PAYABLE, "0"),
                        ]
                    },
                    second_application_date: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "20245.02"),
                            (dimensions.ACCRUED_PROFIT_PAYABLE, "0"),
                        ]
                    },
                    third_application_date: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "20492.95"),
                            (dimensions.ACCRUED_PROFIT_PAYABLE, "0"),
                        ]
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_account_schedules_apply_accrue_profit_quarterly(self):
        """
        Test if the schedules runtime of the apply accrue profit are correct when the frequency is
        set to quarterly and when the application creation date falls on the end of the month dates
        29, 30, 31.
        """
        start = datetime(year=2019, month=1, day=29, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=4, day=30, hour=23, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **default_template_params,
            "profit_application_frequency": "quarterly",
        }
        instance_params = {
            **default_instance_params,
            "profit_application_day": "30",
        }

        first_application_date = datetime(
            year=2019,
            month=4,
            day=30,
            hour=int(template_params["profit_application_hour"]),
            minute=int(template_params["profit_application_minute"]),
            second=int(template_params["profit_application_second"]),
            tzinfo=ZoneInfo("UTC"),
        )

        sub_tests = [
            SubTest(
                description="Fund account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="20000",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination="MYR",
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "20000"),
                        ]
                    }
                },
            ),
            SubTest(
                description="Ensure apply profit schedule quarterly runtime and ammount is correct",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_application_date],
                        event_id="APPLY_PROFIT",
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        count=1,
                    )
                ],
                expected_balances_at_ts={
                    first_application_date
                    - relativedelta(seconds=1): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "20000"),
                            (dimensions.ACCRUED_PROFIT_PAYABLE, "742.95858"),
                        ]
                    },
                    first_application_date: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "20742.96"),
                            (dimensions.ACCRUED_PROFIT_PAYABLE, "0"),
                        ]
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_account_schedules_apply_accrue_profit_annually(self):
        """
        Test if the schedules runtime of the apply accrue profit are correct when the frequency is
        set to annually and when the application creation date falls on the end of the month dates
        29, 30, 31.
        """
        start = datetime(year=2019, month=1, day=29, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2020, month=1, day=30, hour=23, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **default_template_params,
            "profit_application_frequency": "annually",
        }
        instance_params = {
            **default_instance_params,
            "profit_application_day": "30",
        }

        first_application_date = datetime(
            year=2020,
            month=1,
            day=30,
            hour=int(template_params["profit_application_hour"]),
            minute=int(template_params["profit_application_minute"]),
            second=int(template_params["profit_application_second"]),
            tzinfo=ZoneInfo("UTC"),
        )

        sub_tests = [
            SubTest(
                description="Fund account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="20000",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination="MYR",
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "20000"),
                        ]
                    }
                },
            ),
            SubTest(
                description="Ensure apply profit schedule annually runtime and amount is correct",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_application_date],
                        event_id="APPLY_PROFIT",
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        count=1,
                    )
                ],
                expected_balances_at_ts={
                    first_application_date
                    - relativedelta(seconds=1): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "20000"),
                            (dimensions.ACCRUED_PROFIT_PAYABLE, "2988.16308"),
                        ]
                    },
                    first_application_date: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "22988.16"),
                            (dimensions.ACCRUED_PROFIT_PAYABLE, "0"),
                        ]
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_schedules_profit_payment_day_change_monthly(self):
        """
        Test that the profit application schedule is updated when the profit application day
        parameter is changed.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=3, day=3, hour=1, tzinfo=ZoneInfo("UTC"))

        first_application_day = datetime(
            year=2019,
            month=2,
            day=5,
            hour=0,
            minute=1,
            second=0,
            tzinfo=ZoneInfo("UTC"),
        )
        second_application_day = datetime(
            year=2019,
            month=3,
            day=3,
            hour=0,
            minute=1,
            second=0,
            tzinfo=ZoneInfo("UTC"),
        )
        new_profit_application_day = "3"

        sub_tests = [
            SubTest(
                description="Check for first application event",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_application_day],
                        event_id="APPLY_PROFIT",
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Check schedule with new profit application day change",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=first_application_day + relativedelta(seconds=1),
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        profit_application_day=new_profit_application_day,
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[second_application_day],
                        event_id="APPLY_PROFIT",
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )

        self.run_test_scenario(test_scenario)

    def test_schedules_profit_payment_day_change_annually(self):
        """
        Test that the profit application schedule is updated when the profit application day
        parameter is changed.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2021, month=1, day=3, hour=1, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **default_template_params,
            "profit_application_frequency": "annually",
        }
        instance_params = {
            **default_instance_params,
            "profit_application_day": "1",
        }

        first_application_day = datetime(
            year=2020,
            month=1,
            day=1,
            hour=0,
            minute=1,
            second=0,
            tzinfo=ZoneInfo("UTC"),
        )
        second_application_day = datetime(
            year=2021,
            month=1,
            day=3,
            hour=0,
            minute=1,
            second=0,
            tzinfo=ZoneInfo("UTC"),
        )
        new_profit_application_day = "3"

        sub_tests = [
            SubTest(
                description="Check for first application event",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_application_day],
                        event_id="APPLY_PROFIT",
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Check schedule with new profit application day change",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=first_application_day + relativedelta(seconds=1),
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        profit_application_day=new_profit_application_day,
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[second_application_day],
                        event_id="APPLY_PROFIT",
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_account_schedules_apply_accrue_profit_on_holiday(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=3, day=30, hour=23, tzinfo=ZoneInfo("UTC"))

        holiday_start = datetime(2019, 1, 30, tzinfo=ZoneInfo("UTC"))
        holiday_end = datetime(2019, 1, 30, 23, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "profit_application_day": "30",
        }

        events = [
            create_calendar(
                timestamp=start,
                calendar_id=PUBLIC_HOLIDAYS,
            ),
            create_calendar_event(
                timestamp=start,
                calendar_event_id="TEST1",
                calendar_id=PUBLIC_HOLIDAYS,
                start_timestamp=holiday_start,
                end_timestamp=holiday_end,
            ),
        ]

        sub_tests = [
            SubTest(
                description="check apply accrue profit date when it falls on a holiday",
                events=events,
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            # Runs at 2019/1/31 since 2019/1/30 is a holiday here
                            datetime(
                                year=2019,
                                month=1,
                                day=31,
                                hour=int(default_template_params["profit_application_hour"]),
                                minute=int(default_template_params["profit_application_minute"]),
                                second=int(default_template_params["profit_application_second"]),
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            # Runs at 2019/2/28 since it is the first possible day before 2019/2/30
                            datetime(
                                year=2019,
                                month=2,
                                day=28,
                                hour=int(default_template_params["profit_application_hour"]),
                                minute=int(default_template_params["profit_application_minute"]),
                                second=int(default_template_params["profit_application_second"]),
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            # Runs at 2019/3/30 this is the standard application day
                            datetime(
                                year=2019,
                                month=3,
                                day=30,
                                hour=int(default_template_params["profit_application_hour"]),
                                minute=int(default_template_params["profit_application_minute"]),
                                second=int(default_template_params["profit_application_second"]),
                                tzinfo=ZoneInfo("UTC"),
                            ),
                        ],
                        event_id=shariah_savings_account.profit_application.APPLICATION_EVENT,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        count=3,
                    )
                ],
            )
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_account_schedules_apply_accrue_profit_on_holiday_consecutive(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=3, day=30, hour=23, tzinfo=ZoneInfo("UTC"))

        holiday_start = datetime(2019, 1, 30, tzinfo=ZoneInfo("UTC"))
        holiday_end = datetime(2019, 1, 30, 23, tzinfo=ZoneInfo("UTC"))
        holiday_start2 = datetime(2019, 1, 31, tzinfo=ZoneInfo("UTC"))
        holiday_end2 = datetime(2019, 1, 31, 23, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "profit_application_day": "30",
        }

        events = [
            create_calendar(
                timestamp=start,
                calendar_id=PUBLIC_HOLIDAYS,
            ),
            create_calendar_event(
                timestamp=start,
                calendar_event_id="TEST1",
                calendar_id=PUBLIC_HOLIDAYS,
                start_timestamp=holiday_start,
                end_timestamp=holiday_end,
            ),
            create_calendar_event(
                timestamp=start,
                calendar_event_id="TEST2",
                calendar_id=PUBLIC_HOLIDAYS,
                start_timestamp=holiday_start2,
                end_timestamp=holiday_end2,
            ),
        ]

        sub_tests = [
            SubTest(
                description="check withdrawal date when it falls on a holiday",
                events=events,
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            # Runs on 2019/2/1 since 2019/1/30-31 are holidays here
                            datetime(
                                year=2019,
                                month=2,
                                day=1,
                                hour=int(default_template_params["profit_application_hour"]),
                                minute=int(default_template_params["profit_application_minute"]),
                                second=int(default_template_params["profit_application_second"]),
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            # Runs at 2019/2/28 since it is the first possible day before 2019/2/30
                            datetime(
                                year=2019,
                                month=2,
                                day=28,
                                hour=int(default_template_params["profit_application_hour"]),
                                minute=int(default_template_params["profit_application_minute"]),
                                second=int(default_template_params["profit_application_second"]),
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            # Runs at 2019/3/30 this is the standard application day
                            datetime(
                                year=2019,
                                month=3,
                                day=30,
                                hour=int(default_template_params["profit_application_hour"]),
                                minute=int(default_template_params["profit_application_minute"]),
                                second=int(default_template_params["profit_application_second"]),
                                tzinfo=ZoneInfo("UTC"),
                            ),
                        ],
                        event_id=shariah_savings_account.profit_application.APPLICATION_EVENT,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        count=3,
                    )
                ],
            )
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_change_profit_application_day_on_holiday(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=3, day=30, hour=23, tzinfo=ZoneInfo("UTC"))
        change_param_start = datetime(2019, 2, 1, tzinfo=ZoneInfo("UTC"))
        holiday_start = datetime(2019, 2, 3, tzinfo=ZoneInfo("UTC"))
        holiday_end = datetime(2019, 2, 3, 23, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **default_template_params,
        }
        instance_params = {
            **default_instance_params,
            "profit_application_day": "30",
        }

        events = [
            create_calendar(
                timestamp=start,
                calendar_id=PUBLIC_HOLIDAYS,
            ),
            create_calendar_event(
                timestamp=start,
                calendar_event_id="TEST1",
                calendar_id=PUBLIC_HOLIDAYS,
                start_timestamp=holiday_start,
                end_timestamp=holiday_end,
            ),
            create_instance_parameter_change_event(
                timestamp=change_param_start,
                account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                profit_application_day="3",
            ),
        ]

        sub_tests = [
            SubTest(
                description="check apply accrue profit date when it falls on a holiday",
                events=events,
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2019,
                                month=1,
                                day=30,
                                hour=int(template_params["profit_application_hour"]),
                                minute=int(template_params["profit_application_minute"]),
                                second=int(template_params["profit_application_second"]),
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2019,
                                month=2,
                                day=4,
                                hour=int(template_params["profit_application_hour"]),
                                minute=int(template_params["profit_application_minute"]),
                                second=int(template_params["profit_application_second"]),
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2019,
                                month=3,
                                day=3,
                                hour=int(template_params["profit_application_hour"]),
                                minute=int(template_params["profit_application_minute"]),
                                second=int(template_params["profit_application_second"]),
                                tzinfo=ZoneInfo("UTC"),
                            ),
                        ],
                        event_id=shariah_savings_account.profit_application.APPLICATION_EVENT,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        count=3,
                    )
                ],
            )
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)
