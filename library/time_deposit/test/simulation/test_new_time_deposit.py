# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

# library
import library.time_deposit.contracts.template.time_deposit as time_deposit
from library.time_deposit.test import accounts, dimensions, files, parameters
from library.time_deposit.test.simulation.accounts import default_internal_accounts

# inception sdk
from inception_sdk.test_framework.common.utils import ac_coverage
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ContractNotificationResourceType,
    ExpectedContractNotification,
    ExpectedDerivedParameter,
    ExpectedSchedule,
    SimulationTestScenario,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_account_product_version_update_instruction,
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_outbound_hard_settlement_instruction,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    ExpectedRejection,
    SimulationTestCase,
)

time_deposit_instance_params = parameters.time_deposit_instance_params
time_deposit_template_params = parameters.time_deposit_template_params

DEFAULT_SIMULATION_START_DATETIME = datetime(year=2022, month=1, day=1, tzinfo=ZoneInfo("UTC"))


class NewTimeDepositTest(SimulationTestCase):
    account_id_base = accounts.TIME_DEPOSIT
    contract_filepaths = [str(files.TIME_DEPOSIT_CONTRACT)]
    internal_accounts = default_internal_accounts

    def get_simulation_test_scenario(
        self,
        start,
        end,
        sub_tests,
        template_params=None,
        instance_params=None,
        internal_accounts=None,
        debug=False,
    ):
        contract_config = ContractConfig(
            contract_content=self.smart_contract_path_to_content[str(files.TIME_DEPOSIT_CONTRACT)],
            template_params=template_params or time_deposit_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or time_deposit_instance_params,
                    account_id_base=self.account_id_base,
                )
            ],
        )
        return SimulationTestScenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            contract_config=contract_config,
            internal_accounts=self.internal_accounts or internal_accounts,
            debug=debug,
        )

    def test_minimum_initial_deposit_is_rejected_and_subsequent_deposits_are_accepted(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        end = start + relativedelta(seconds=3)

        sub_tests = [
            SubTest(
                description="Initial deposit is rejected as below the minimum allowed amount",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="20",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, "0")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=1),
                        account_id=accounts.TIME_DEPOSIT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transaction amount 20.00 GBP is "
                        "less than the minimum initial deposit amount 40.00"
                        " GBP.",
                    )
                ],
            ),
            SubTest(
                description="Initial deposit is accepted as equal to the minimum threshold",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="40",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, "40")],
                    },
                },
            ),
            SubTest(
                description="Subsequent deposit is accepted as the minimum "
                "threshold only applies to initial deposit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="20",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, "60")],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, debug=True
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-2082-AC01", "CPP-2082-AC02", "CPP-2082-AC05", "CPP-2082-AC08"])
    def test_deposit_period_unlimited_deposits(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        end = start + relativedelta(days=6, seconds=1)

        sub_tests = [
            SubTest(
                description="First deposit within the deposit period is accepted",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100.00",
                        event_datetime=start + relativedelta(days=2),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=2): {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("100.00"))]
                    },
                },
            ),
            SubTest(
                description="Second deposit within the deposit period is accepted",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100.00",
                        event_datetime=start + relativedelta(days=3),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=3): {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("200.00"))]
                    },
                },
            ),
            SubTest(
                description="Third deposit rejected as exactly on the deposit period end of day",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100.00",
                        event_datetime=start + relativedelta(days=6),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=6): {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("200.00"))]
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(days=6),
                        account_id=accounts.TIME_DEPOSIT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="No deposits are allowed after the deposit period "
                        "end datetime",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, debug=True
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-2082-AC01", "CPP-2082-AC02", "CPP-2082-AC06", "CPP-2082-AC07"])
    def test_deposit_period_single_deposit(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        end = start + relativedelta(days=2)
        template_parameters = time_deposit_template_params.copy()
        template_parameters["number_of_permitted_deposits"] = "single"

        sub_tests = [
            SubTest(
                description="First deposit is accepted when within the deposit period",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100.00",
                        event_datetime=start + relativedelta(days=2),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=2): {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("100.00"))]
                    },
                },
            ),
            SubTest(
                description="Second deposit is rejected within the deposit period",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100.00",
                        event_datetime=start + relativedelta(days=2),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=2): {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("100.00"))]
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(days=2),
                        account_id=accounts.TIME_DEPOSIT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Only a single deposit is allowed",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            debug=True,
            template_params=template_parameters,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-2082-AC03", "CPP-2082-AC09"])
    def test_account_closure_notification_after_deposit_period(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        end = start + relativedelta(days=6, seconds=1)
        deposit_period_end_date = start + relativedelta(days=5, hour=23, minute=59, second=59)

        sub_tests = [
            SubTest(
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100.00",
                        event_datetime=start + relativedelta(days=2),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="100.00",
                        event_datetime=start + relativedelta(days=3),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                description="Account closure notification when no funds by the "
                "end of deposit period",
                expected_balances_at_ts={
                    deposit_period_end_date: {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("0"))]
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            deposit_period_end_date,
                        ],
                        event_id="DEPOSIT_PERIOD_END",
                        account_id=accounts.TIME_DEPOSIT,
                    ),
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=deposit_period_end_date,
                        notification_type=time_deposit.DEPOSIT_PERIOD_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "deposit_balance": "0",
                            "deposit_period_end_datetime": "2022-01-06 23:59:59+00:00",
                            "reason": "Close account due to lack of deposits at"
                            " the end of deposit period",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_period_derived_parameters(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        within_periods_datetime = start + relativedelta(hours=5)
        after_periods_datetime = start + relativedelta(days=6, seconds=1)
        end = start + relativedelta(days=6, seconds=1)

        sub_tests = [
            SubTest(
                description="Check derived parameter before deposit period end datetime",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=within_periods_datetime,
                        account_id=accounts.TIME_DEPOSIT,
                        name="deposit_period_end_date",
                        value="2022-01-06",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=within_periods_datetime,
                        account_id=accounts.TIME_DEPOSIT,
                        name="cooling_off_period_end_date",
                        value="2022-01-03",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=within_periods_datetime,
                        account_id=accounts.TIME_DEPOSIT,
                        name="grace_period_end_date",
                        value="0001-01-01",
                    ),
                ],
            ),
            SubTest(
                description="Check derived parameter after deposit period end datetime",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=after_periods_datetime,
                        account_id=accounts.TIME_DEPOSIT,
                        name="deposit_period_end_date",
                        value="2022-01-06",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_periods_datetime,
                        account_id=accounts.TIME_DEPOSIT,
                        name="cooling_off_period_end_date",
                        value="2022-01-03",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=within_periods_datetime,
                        account_id=accounts.TIME_DEPOSIT,
                        name="grace_period_end_date",
                        value="0001-01-01",
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)

        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-2084-AC03", "CPP-2092-AC08", "CPP-2092-AC11"])
    def test_partial_withdrawal_within_and_outside_cooling_off_period_subject_to_fees(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        cooling_off_period_end_date = start + relativedelta(
            days=2, hour=23, minute=59, second=59, microsecond=999999
        )
        end = start + relativedelta(days=3, hours=2)

        sub_tests = [
            SubTest(
                description="Deposit funds",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100.00",
                        event_datetime=start + relativedelta(minutes=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination="GBP",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(minutes=1): {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("100.00"))]
                    },
                },
            ),
            SubTest(
                description="Partial withdrawal accepted within cooling-off period "
                "with fee notification",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="20.00",
                        event_datetime=cooling_off_period_end_date - relativedelta(hours=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination="GBP",
                        client_batch_id="20_withdrawal",
                    ),
                ],
                expected_balances_at_ts={
                    cooling_off_period_end_date
                    - relativedelta(hours=1): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("80.00")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("20.00")),
                        ]
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=cooling_off_period_end_date - relativedelta(hours=1),
                        notification_type=time_deposit.WITHDRAWAL_FEES_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "denomination": "GBP",
                            "withdrawal_amount": "20.00",
                            "flat_fee_amount": "10",
                            "percentage_fee_amount": "0.20",
                            "number_of_interest_days_fee": "0",
                            "total_fee_amount": "10.20",
                            "client_batch_id": "20_withdrawal",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Partial withdrawal accepted outside cooling-off period "
                "with fee notification",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="15.00",
                        event_datetime=cooling_off_period_end_date + relativedelta(hours=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination="GBP",
                        client_batch_id="15_withdrawal",
                    ),
                ],
                expected_balances_at_ts={
                    cooling_off_period_end_date
                    + relativedelta(hours=1): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("65.00")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("35.00")),
                        ]
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=cooling_off_period_end_date + relativedelta(hours=1),
                        notification_type=time_deposit.WITHDRAWAL_FEES_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "denomination": "GBP",
                            "withdrawal_amount": "15.00",
                            "flat_fee_amount": "10",
                            "percentage_fee_amount": "0.15",
                            "number_of_interest_days_fee": "0",
                            "total_fee_amount": "10.15",
                            "client_batch_id": "15_withdrawal",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=time_deposit_template_params,
            instance_params=time_deposit_instance_params,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-2084-AC04"])
    def test_full_withdrawal_within_cooling_off_period_no_fees(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        cooling_off_period_end_date = start + relativedelta(
            days=2, hour=23, minute=59, second=59, microsecond=999999
        )
        end = start + relativedelta(days=3, hours=2)

        template_params = {
            **time_deposit_template_params,
            time_deposit.deposit_period.PARAM_DEPOSIT_PERIOD: "1",
        }

        sub_tests = [
            SubTest(
                description="Deposit funds",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100.00",
                        event_datetime=start + relativedelta(minutes=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination="GBP",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(minutes=1): {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("100.00"))]
                    },
                },
            ),
            SubTest(
                description="Full withdrawal accepted within cooling-off period",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="100.00",
                        event_datetime=cooling_off_period_end_date - relativedelta(hours=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination="GBP",
                        client_batch_id="full_withdrawal",
                    ),
                ],
                expected_balances_at_ts={
                    cooling_off_period_end_date
                    - relativedelta(hours=1): {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("0.00"))]
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=cooling_off_period_end_date - relativedelta(hours=1),
                        notification_type=time_deposit.WITHDRAWAL_FEES_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "denomination": "GBP",
                            "withdrawal_amount": "100.00",
                            "flat_fee_amount": "0",
                            "percentage_fee_amount": "0",
                            "number_of_interest_days_fee": "0",
                            "total_fee_amount": "0",
                            "client_batch_id": "full_withdrawal",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                    ExpectedContractNotification(
                        timestamp=cooling_off_period_end_date - relativedelta(hours=1),
                        notification_type=time_deposit.FULL_WITHDRAWAL_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "reason": "The account balance has been fully withdrawn.",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=time_deposit_instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_full_withdrawal_outside_cooling_off_period_has_fee_notification(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        cooling_off_period_end_date = start + relativedelta(
            days=2, hour=23, minute=59, second=59, microsecond=999999
        )
        end = start + relativedelta(days=3, hours=2)

        template_params = {
            **time_deposit_template_params,
            time_deposit.deposit_period.PARAM_DEPOSIT_PERIOD: "1",
        }

        sub_tests = [
            SubTest(
                description="Deposit funds",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100.00",
                        event_datetime=start + relativedelta(minutes=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination="GBP",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(minutes=1): {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("100.00"))]
                    },
                },
            ),
            SubTest(
                description="Full withdrawal accepted outside cooling-off period, "
                "with fee notification",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="100.00",
                        event_datetime=cooling_off_period_end_date + relativedelta(hours=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination="GBP",
                        client_batch_id="full_withdrawal",
                    ),
                ],
                expected_balances_at_ts={
                    cooling_off_period_end_date
                    + relativedelta(hours=1): {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("0.00"))]
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=cooling_off_period_end_date + relativedelta(hours=1),
                        notification_type=time_deposit.WITHDRAWAL_FEES_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "denomination": "GBP",
                            "withdrawal_amount": "100.00",
                            "flat_fee_amount": "10",
                            "percentage_fee_amount": "1.00",
                            "number_of_interest_days_fee": "0",
                            "total_fee_amount": "11.00",
                            "client_batch_id": "full_withdrawal",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                    ExpectedContractNotification(
                        timestamp=cooling_off_period_end_date + relativedelta(hours=1),
                        notification_type=time_deposit.FULL_WITHDRAWAL_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "reason": "The account balance has been fully withdrawn.",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=time_deposit_instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_account_conversion_before_and_after_deposit_period_is_executed(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        deposit_period_end_datetime = DEFAULT_SIMULATION_START_DATETIME + relativedelta(
            days=5, hour=23, minute=59, second=59
        )
        instance_parameters = {
            **time_deposit_instance_params,
            time_deposit.interest_application.PARAM_INTEREST_APPLICATION_DAY: "2",
        }
        end = start + relativedelta(months=1, days=1)

        # conversion before deposit period end schedule
        conversion_1 = start + relativedelta(hours=1)
        convert_to_version_id_1 = "5"
        convert_to_contract_config_1 = ContractConfig(
            contract_content=self.smart_contract_path_to_content[self.contract_filepaths[0]],
            smart_contract_version_id=convert_to_version_id_1,
            template_params=time_deposit_template_params,
            account_configs=[],
        )

        # conversion after deposit period end schedule
        conversion_2 = start + relativedelta(days=15)
        convert_to_version_id_2 = "6"
        convert_to_contract_config_2 = ContractConfig(
            contract_content=self.smart_contract_path_to_content[self.contract_filepaths[0]],
            smart_contract_version_id=convert_to_version_id_2,
            template_params=time_deposit_template_params,
            account_configs=[],
        )

        # interest accrual schedules
        accrue_interest_date = start + relativedelta(days=1)
        accrue_interest_date = accrue_interest_date.replace(
            hour=int(
                time_deposit_template_params[
                    time_deposit.fixed_interest_accrual.PARAM_INTEREST_ACCRUAL_HOUR
                ]
            ),
            minute=int(
                time_deposit_template_params[
                    time_deposit.fixed_interest_accrual.PARAM_INTEREST_ACCRUAL_MINUTE
                ]
            ),
            second=int(
                time_deposit_template_params[
                    time_deposit.fixed_interest_accrual.PARAM_INTEREST_ACCRUAL_SECOND
                ]
            ),
        )

        run_times_accrue_interest_until_conversion_1 = [
            accrue_interest_date + relativedelta(days=i) for i in range(6)
        ]

        run_times_accrue_interest_end_of_sim = [
            accrue_interest_date + relativedelta(days=i) for i in range(30)
        ]

        # interest application schedule
        first_application_datetime = datetime(
            year=2022, month=1, day=2, minute=1, tzinfo=ZoneInfo("UTC")
        )
        sub_tests = [
            SubTest(
                description="Trigger First Conversion before deposit period and Check Schedules",
                events=[
                    create_account_product_version_update_instruction(
                        timestamp=conversion_1,
                        account_id=accounts.TIME_DEPOSIT,
                        product_version_id=convert_to_version_id_1,
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=run_times_accrue_interest_until_conversion_1,
                        event_id=time_deposit.fixed_interest_accrual.ACCRUAL_EVENT,
                        account_id=accounts.TIME_DEPOSIT,
                    ),
                ],
            ),
            SubTest(
                description="Deposit Period Schedule is present"
                "after conversion and a notification is sent",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            deposit_period_end_datetime,
                        ],
                        event_id="DEPOSIT_PERIOD_END",
                        account_id=accounts.TIME_DEPOSIT,
                        count=1,
                    ),
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=deposit_period_end_datetime,
                        notification_type=time_deposit.DEPOSIT_PERIOD_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "deposit_balance": "0",
                            "deposit_period_end_datetime": "2022-01-06 23:59:59+00:00",
                            "reason": "Close account due to lack of deposits at"
                            " the end of deposit period",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Trigger Conversions after" "Deposit Period and Check Schedules",
                events=[
                    create_account_product_version_update_instruction(
                        timestamp=conversion_2,
                        account_id=accounts.TIME_DEPOSIT,
                        product_version_id=convert_to_version_id_2,
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=run_times_accrue_interest_end_of_sim,
                        event_id=time_deposit.fixed_interest_accrual.ACCRUAL_EVENT,
                        account_id=accounts.TIME_DEPOSIT,
                        count=31,
                    ),
                ],
            ),
            SubTest(
                description="Check First Application datetime",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_application_datetime],
                        event_id=time_deposit.interest_application.APPLICATION_EVENT,
                        account_id=accounts.TIME_DEPOSIT,
                        count=1,
                    ),
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            instance_params=instance_parameters,
            sub_tests=sub_tests,
            debug=True,
        )
        self.run_test_scenario(
            test_scenario,
            smart_contracts=[convert_to_contract_config_1, convert_to_contract_config_2],
        )

    def test_interest_application_event_starts_after_end_of_periods(self):
        start = datetime(2023, 1, 15, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        instance_parameters = {
            **time_deposit_instance_params,
            time_deposit.interest_application.PARAM_INTEREST_APPLICATION_DAY: "17",
        }
        template_params = {
            **time_deposit_template_params,
            time_deposit.deposit_period.PARAM_DEPOSIT_PERIOD: "7",
            time_deposit.cooling_off_period.PARAM_COOLING_OFF_PERIOD: "1",
        }
        interest_application_datetime = datetime(2023, 2, 17, 0, 1, 0, tzinfo=ZoneInfo("UTC"))
        end = datetime(2023, 2, 18, 0, 0, 0, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="Fund the account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start,
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5000")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check interest application day",
                expected_balances_at_ts={
                    interest_application_datetime
                    - relativedelta(seconds=1): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5000.00")),
                            # (5000 * (0.01/365)) = 0.13698630137 -> 0.13699 Rounded to 5DP
                            # 0.13699 * 33 = 4.52067
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("4.52067")),
                            (dimensions.APPLIED_INTEREST_TRACKER, Decimal("0")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-4.52067")),
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    },
                    interest_application_datetime: {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5004.52")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.APPLIED_INTEREST_TRACKER, Decimal("4.52")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("4.52")),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[interest_application_datetime],
                        event_id=time_deposit.interest_application.APPLICATION_EVENT,
                        account_id=accounts.TIME_DEPOSIT,
                        count=1,
                    )
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_parameters,
            template_params=template_params,
        )
        self.run_test_scenario(test_scenario)

    def test_changing_term_parameter_rejected_for_new_time_deposits(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        end = start + relativedelta(days=2, hours=1)

        parameter_change_datetime = start + relativedelta(days=2)

        sub_tests = [
            SubTest(
                description="Change term",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=parameter_change_datetime,
                        account_id=accounts.TIME_DEPOSIT,
                        term="24",
                    )
                ],
                expected_parameter_change_rejections=[
                    ExpectedRejection(
                        timestamp=parameter_change_datetime,
                        account_id=accounts.TIME_DEPOSIT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Term length can only be changed on "
                        "Renewed Time Deposit accounts",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)
