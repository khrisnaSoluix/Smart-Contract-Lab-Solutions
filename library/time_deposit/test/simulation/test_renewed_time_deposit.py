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
    ExpectedDerivedParameter,
    SimulationTestScenario,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_outbound_hard_settlement_instruction,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    ExpectedContractNotification,
    ExpectedRejection,
    ExpectedSchedule,
    SimulationTestCase,
)

time_deposit_instance_params = parameters.time_deposit_instance_params
time_deposit_template_params = parameters.renewed_time_deposit_template_params

DEFAULT_SIMULATION_START_DATETIME = datetime(year=2022, month=1, day=1, tzinfo=ZoneInfo("UTC"))


class RenewedTimeDepositTest(SimulationTestCase):
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

    @ac_coverage(
        ["CPP-2083-AC04", "CPP-2083-AC05", "CPP-2083-AC07", "CPP-2092-AC08", "CPP-2092-AC11"]
    )
    def test_additional_deposits_and_withdrawals_within_and_outside_grace_period(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        end = start + relativedelta(days=2, hours=1)

        sub_tests = [
            SubTest(
                description="Make an initial deposit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start,
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("1000"))],
                    },
                },
            ),
            SubTest(
                description="Withdrawal within grace period is accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                        client_batch_id="partial_withdrawal_150",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("850")),
                            # Customer can change deposited amount during grace period,
                            # hence withdrawals tracker not updated
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("0")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(seconds=1),
                        notification_type=time_deposit.WITHDRAWAL_FEES_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "denomination": "GBP",
                            "withdrawal_amount": "150",
                            "flat_fee_amount": "0",
                            "percentage_fee_amount": "0",
                            "number_of_interest_days_fee": "0",
                            "total_fee_amount": "0",
                            "client_batch_id": "partial_withdrawal_150",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Additional deposit within grace period is accepted",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="25",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("875")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Additional deposit outside grace period is rejected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="200",
                        event_datetime=start + relativedelta(days=2),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=2): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("875")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("0")),
                        ],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(days=2),
                        account_id=accounts.TIME_DEPOSIT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="No deposits are allowed after the grace period end",
                    )
                ],
            ),
            SubTest(
                description="Withdrawal outside grace period is accepted with fee notification",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="200",
                        event_datetime=start + relativedelta(days=2, seconds=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                        client_batch_id="partial_withdrawal_200",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=2, seconds=1): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("675")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("200")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(days=2, seconds=1),
                        notification_type=time_deposit.WITHDRAWAL_FEES_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "denomination": "GBP",
                            "withdrawal_amount": "200",
                            "flat_fee_amount": "10",
                            "percentage_fee_amount": "2.00",
                            "number_of_interest_days_fee": "0",
                            "total_fee_amount": "12.00",
                            "client_batch_id": "partial_withdrawal_200",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Full withdrawal outside grace period is accepted "
                "with fee notification and full-withdrawal notification",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="675",
                        event_datetime=start + relativedelta(days=2, seconds=2),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                        client_batch_id="full_withdrawal_675",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=2, seconds=2): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("875")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(days=2, seconds=2),
                        notification_type=time_deposit.FULL_WITHDRAWAL_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "reason": "The account balance has been fully withdrawn.",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(days=2, seconds=2),
                        notification_type=time_deposit.WITHDRAWAL_FEES_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "denomination": "GBP",
                            "withdrawal_amount": "675",
                            "flat_fee_amount": "10",
                            "percentage_fee_amount": "6.75",
                            "number_of_interest_days_fee": "0",
                            "total_fee_amount": "16.75",
                            "client_batch_id": "full_withdrawal_675",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-2083-AC06"])
    def test_full_withdrawal_during_grace_period_is_accepted_without_fees(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        end = start + relativedelta(days=2, hours=1)

        sub_tests = [
            SubTest(
                description="Make an initial deposit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start,
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("1000"))],
                    },
                },
            ),
            SubTest(
                description="Full withdrawal within grace period is accepted "
                "with zero-fee notification",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                        client_batch_id="full_withdrawal_1000",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("0")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(seconds=1),
                        notification_type=time_deposit.WITHDRAWAL_FEES_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "denomination": "GBP",
                            "withdrawal_amount": "1000",
                            "flat_fee_amount": "0",
                            "percentage_fee_amount": "0",
                            "number_of_interest_days_fee": "0",
                            "total_fee_amount": "0",
                            "client_batch_id": "full_withdrawal_1000",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-2083-AC09"])
    def test_changing_term_parameter_rejected_when_outside_grace_period(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        end = start + relativedelta(days=2, hours=1)

        outside_grace_period = start + relativedelta(days=2)

        sub_tests = [
            SubTest(
                description="Change term",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=outside_grace_period,
                        account_id=accounts.TIME_DEPOSIT,
                        term="24",
                    )
                ],
                expected_parameter_change_rejections=[
                    ExpectedRejection(
                        timestamp=outside_grace_period,
                        account_id=accounts.TIME_DEPOSIT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Term length cannot be changed outside the grace period",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_changing_term_parameter_rejected_when_desired_maturity_datetime_set(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        end = start + relativedelta(days=2, hours=1)

        parameter_change_datetime = start + relativedelta(days=1)

        instance_params = {
            **time_deposit_instance_params,
            time_deposit.deposit_maturity.PARAM_DESIRED_MATURITY_DATE: str(
                datetime(year=2022, month=1, day=9, tzinfo=ZoneInfo("UTC")).date()
            ),
        }
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
                        rejection_reason="Term length cannot be changed if the desired "
                        "maturity datetime is set.",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params
        )
        self.run_test_scenario(test_scenario)

    def test_changing_term_parameter_rejected_when_start_of_notice_period_in_the_past(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        end = start + relativedelta(days=6, seconds=1)

        # opening 2022-01-01 00:00:00
        # notify_upcoming_maturity_datetime 2022-01-05 00:00:00
        # account_maturity_datetime 2022-01-06 00:00:00
        notify_upcoming_maturity_datetime = start + relativedelta(days=4)
        account_maturity_datetime = start + relativedelta(days=5)

        # attempt parameter change on 2022-01-02 12:00:00
        # this would attempt to change the term to 2 days, i.e.
        # notify_upcoming_maturity_datetime 2022-01-02 00:00:00
        # account_maturity_datetime 2022-01-03 00:00:00
        # Hence the term change should be rejected since notify schedule would be before
        # parameter change effective datetime
        parameter_change_datetime = start + relativedelta(days=1, hours=12)

        template_params = {
            **time_deposit_template_params,
            time_deposit.deposit_parameters.PARAM_TERM_UNIT: "days",
            time_deposit.deposit_maturity.PARAM_MATURITY_NOTICE_PERIOD: "1",
        }

        sub_tests = [
            SubTest(
                description="Change term",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=parameter_change_datetime,
                        account_id=accounts.TIME_DEPOSIT,
                        term="2",
                    )
                ],
                expected_parameter_change_rejections=[
                    ExpectedRejection(
                        timestamp=parameter_change_datetime,
                        account_id=accounts.TIME_DEPOSIT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Term length cannot be changed such that the maturity "
                        "notification period starts in the past.",
                    )
                ],
            ),
            SubTest(
                description="Notify of account maturity occurs at original datetime",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            notify_upcoming_maturity_datetime,
                        ],
                        event_id=time_deposit.deposit_maturity.NOTIFY_UPCOMING_MATURITY_EVENT,
                        account_id=accounts.TIME_DEPOSIT,
                    ),
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=notify_upcoming_maturity_datetime,
                        notification_type=time_deposit.NOTIFY_UPCOMING_MATURITY_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "account_maturity_datetime": "2022-01-06 00:00:00+00:00",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Notification at account maturity occurs at original datetime",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            account_maturity_datetime,
                        ],
                        event_id=time_deposit.deposit_maturity.ACCOUNT_MATURITY_EVENT,
                        account_id=accounts.TIME_DEPOSIT,
                    ),
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=account_maturity_datetime,
                        notification_type=time_deposit.ACCOUNT_MATURITY_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "account_maturity_datetime": "2022-01-06 00:00:00+00:00",
                            "reason": "Account has now reached maturity",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-2083-AC08"])
    def test_changing_term_parameter_accepted_when_valid_and_schedules_updated(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        end = start + relativedelta(days=6, seconds=1)

        parameter_change_datetime = start + relativedelta(days=1)
        # Before parameter change, maturity datetime is 2022-01-06
        # After parameter change, maturity datetime is 2022-01-07
        notify_upcoming_maturity_datetime = start + relativedelta(
            days=5, hour=0, minute=0, second=0
        )
        account_maturity_datetime = start + relativedelta(days=6, hour=0, minute=0, second=0)

        template_params = {
            **time_deposit_template_params,
            time_deposit.deposit_parameters.PARAM_TERM_UNIT: "days",
        }

        sub_tests = [
            SubTest(
                description="Change term",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=parameter_change_datetime,
                        account_id=accounts.TIME_DEPOSIT,
                        term="5",
                    )
                ],
            ),
            SubTest(
                description="Notification before account maturity",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            notify_upcoming_maturity_datetime,
                        ],
                        event_id=time_deposit.deposit_maturity.NOTIFY_UPCOMING_MATURITY_EVENT,
                        account_id=accounts.TIME_DEPOSIT,
                    ),
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=notify_upcoming_maturity_datetime,
                        notification_type=time_deposit.NOTIFY_UPCOMING_MATURITY_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "account_maturity_datetime": "2022-01-07 00:00:00+00:00",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Notification at account maturity",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            account_maturity_datetime,
                        ],
                        event_id=time_deposit.deposit_maturity.ACCOUNT_MATURITY_EVENT,
                        account_id=accounts.TIME_DEPOSIT,
                    ),
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=account_maturity_datetime,
                        notification_type=time_deposit.ACCOUNT_MATURITY_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "account_maturity_datetime": "2022-01-07 00:00:00+00:00",
                            "reason": "Account has now reached maturity",
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
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-2083-AC10"])
    def test_account_closure_after_grace_period(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        end = start + relativedelta(days=3, seconds=1)
        grace_period_end_date = start + relativedelta(days=1, hour=23, minute=59, second=59)

        sub_tests = [
            SubTest(
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100.00",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="100.00",
                        event_datetime=start + relativedelta(hours=3),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                description="Account closure notification when no funds by the "
                "end of grace period",
                expected_balances_at_ts={
                    grace_period_end_date: {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("0"))]
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            grace_period_end_date,
                        ],
                        event_id="GRACE_PERIOD_END",
                        account_id=accounts.TIME_DEPOSIT,
                    ),
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=grace_period_end_date,
                        notification_type=time_deposit.GRACE_PERIOD_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "grace_period_end_datetime": "2022-01-02 23:59:59+00:00",
                            "reason": "Close account due to lack of funds at "
                            "the end of grace period",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_interest_application_event_starts_after_end_of_grace_period(self):
        start = datetime(2023, 1, 15, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        instance_parameters = {
            **time_deposit_instance_params,
            time_deposit.interest_application.PARAM_INTEREST_APPLICATION_DAY: "17",
        }
        template_params = {
            **time_deposit_template_params,
            time_deposit.grace_period.PARAM_GRACE_PERIOD: "7",
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

    def test_period_derived_parameters(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        within_periods_datetime = start + relativedelta(hours=5)
        after_periods_datetime = start + relativedelta(days=1, seconds=1)
        end = start + relativedelta(days=2, seconds=2)

        sub_tests = [
            SubTest(
                description="Check derived parameter before grace period end datetime",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=within_periods_datetime,
                        account_id=accounts.TIME_DEPOSIT,
                        name="deposit_period_end_date",
                        value="0001-01-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=within_periods_datetime,
                        account_id=accounts.TIME_DEPOSIT,
                        name="cooling_off_period_end_date",
                        value="0001-01-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=within_periods_datetime,
                        account_id=accounts.TIME_DEPOSIT,
                        name="grace_period_end_date",
                        value="2022-01-02",
                    ),
                ],
            ),
            SubTest(
                description="Check derived parameter after grace period end datetime",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=after_periods_datetime,
                        account_id=accounts.TIME_DEPOSIT,
                        name="deposit_period_end_date",
                        value="0001-01-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_periods_datetime,
                        account_id=accounts.TIME_DEPOSIT,
                        name="cooling_off_period_end_date",
                        value="0001-01-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=within_periods_datetime,
                        account_id=accounts.TIME_DEPOSIT,
                        name="grace_period_end_date",
                        value="2022-01-02",
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)

        self.run_test_scenario(test_scenario)
