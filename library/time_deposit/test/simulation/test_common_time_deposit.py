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
    create_calendar,
    create_calendar_event,
    create_inbound_authorisation_instruction,
    create_inbound_hard_settlement_instruction,
    create_outbound_hard_settlement_instruction,
    create_posting_instruction_batch,
    update_account_status_pending_closure,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    ExpectedRejection,
    SimulationTestCase,
)
from inception_sdk.vault.postings.posting_classes import InboundHardSettlement

time_deposit_instance_params = parameters.time_deposit_instance_params
time_deposit_template_params = parameters.time_deposit_template_params

DEFAULT_SIMULATION_START_DATETIME = datetime(year=2022, month=1, day=1, tzinfo=ZoneInfo("UTC"))
PUBLIC_HOLIDAYS = "PUBLIC_HOLIDAYS"


class TimeDepositTest(SimulationTestCase):
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

    @ac_coverage(["CPP-1908-AC03", "CPP-1908-AC04", "CPP-2082-AC10"])
    def test_pre_posting_hook_rejections(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        end = start + relativedelta(seconds=30)

        sub_tests = [
            SubTest(
                description="Rejection due to unsupported denomination",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="40",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination="JPY",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("0"))],
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT_JPY, Decimal("0"))],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=3),
                        account_id=accounts.TIME_DEPOSIT,
                        rejection_type="WrongDenomination",
                        rejection_reason="Cannot make transactions in the given denomination, "
                        "transactions must be one of ['GBP']",
                    )
                ],
            ),
            SubTest(
                description="Balance updates when posting using supported denomination",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="40",
                        event_datetime=start + relativedelta(seconds=5),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=5): {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("40"))]
                    },
                },
            ),
            SubTest(
                description="Force Override",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="40",
                        event_datetime=start + relativedelta(seconds=10),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        instruction_details={"force_override": "true"},
                        denomination="JPY",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=10): {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("40"))],
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT_JPY, Decimal("40"))],
                    },
                },
            ),
            SubTest(
                description="check multiple postings in a single batch are rejected",
                events=[
                    create_posting_instruction_batch(
                        event_datetime=start + relativedelta(seconds=15),
                        instructions=[
                            InboundHardSettlement(
                                amount="1000",
                                target_account_id=accounts.TIME_DEPOSIT,
                                internal_account_id=accounts.INTERNAL_ACCOUNT,
                                denomination=parameters.TEST_DENOMINATION,
                            ),
                            InboundHardSettlement(
                                amount="2000",
                                target_account_id=accounts.TIME_DEPOSIT,
                                internal_account_id=accounts.INTERNAL_ACCOUNT,
                                denomination=parameters.TEST_DENOMINATION,
                            ),
                        ],
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(seconds=15),
                        account_id=accounts.TIME_DEPOSIT,
                        rejection_type="Custom",
                        rejection_reason="Only batches with a single hard settlement or transfer "
                        "posting are supported",
                    )
                ],
            ),
            SubTest(
                description="test authorisation posting is rejected",
                events=[
                    create_inbound_authorisation_instruction(
                        amount="2000",
                        event_datetime=start + relativedelta(seconds=20),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(seconds=20),
                        account_id=accounts.TIME_DEPOSIT,
                        rejection_type="Custom",
                        rejection_reason="Only batches with a single hard settlement or transfer "
                        "posting are supported",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1986-AC03", "CPP-1986-AC04"])
    def test_maximum_balance_limit(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        end = start + relativedelta(seconds=3)

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="30000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, "30000")],
                    },
                },
            ),
            SubTest(
                description="Reject inbound over balance limit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="20000.01",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, "30000")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=2),
                        account_id=accounts.TIME_DEPOSIT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Posting would exceed maximum permitted balance 50000.00"
                        " GBP.",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1913-AC04"])
    def test_interest_application_quarterly(self):
        start = datetime(2023, 1, 15, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        instance_parameters = {
            **time_deposit_instance_params,
            time_deposit.interest_application.PARAM_INTEREST_APPLICATION_DAY: "28",
        }
        template_parameters = {
            **time_deposit_template_params,
            time_deposit.interest_application.PARAM_INTEREST_APPLICATION_FREQUENCY: "quarterly",
        }
        end = datetime(2023, 4, 28, 0, 1, 2, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="Check daily interest calculation after 1 day",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                # (5000 * (0.01/365)) = 0.13698630137 -> 0.13699 Rounded to 5DP
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5000")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.13699")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.13699")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check daily interest calculation before application",
                # 0.13699 * (16+28+31+28) days = 14.10997
                expected_balances_at_ts={
                    end
                    - relativedelta(minutes=1): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5000")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("14.10997")),
                            (dimensions.APPLIED_INTEREST_TRACKER, Decimal("0")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-14.10997")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check interest application day",
                expected_balances_at_ts={
                    end: {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5014.11")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.APPLIED_INTEREST_TRACKER, Decimal("14.11")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("14.11")),
                        ],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_parameters,
            template_params=template_parameters,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1913-AC05"])
    def test_interest_application_annually(self):
        start = datetime(2023, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        instance_parameters = {
            **time_deposit_instance_params,
            time_deposit.interest_application.PARAM_INTEREST_APPLICATION_DAY: "5",
            time_deposit.deposit_parameters.PARAM_TERM: "13",
        }
        template_parameters = {
            **time_deposit_template_params,
            time_deposit.interest_application.PARAM_INTEREST_APPLICATION_FREQUENCY: "annually",
        }
        end = datetime(2024, 1, 5, 0, 1, 2, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="Check daily interest calculation after 1 day",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                # (5000 * (0.01/365)) = 0.13698630137 -> 0.13699 Rounded to 5DP
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5000")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.13699")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.13699")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check daily interest calculation before application",
                # 0.13699 * 369 days = 50.54931
                expected_balances_at_ts={
                    end
                    - relativedelta(minutes=1): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5000")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("50.54931")),
                            (dimensions.APPLIED_INTEREST_TRACKER, Decimal("0")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-50.54931")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check interest application day",
                expected_balances_at_ts={
                    end: {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5050.55")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.APPLIED_INTEREST_TRACKER, Decimal("50.55")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("50.55")),
                        ],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_parameters,
            template_params=template_parameters,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1913-AC07"])
    def test_interest_application_when_day_not_in_month(self):
        start = datetime(2023, 2, 15, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        instance_parameters = {
            **time_deposit_instance_params,
            time_deposit.interest_application.PARAM_INTEREST_APPLICATION_DAY: "29",
        }
        # application day is 28th Feb since 29th not in month
        end = datetime(2023, 2, 28, 0, 1, 2, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="Check daily interest calculation after 1 day",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(minutes=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                # (5000 * (0.01/365)) = 0.13698630137 -> 0.13699 Rounded to 5DP
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5000")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.13699")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.13699")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check daily interest calculation before application",
                # 0.13699 * 13 days
                expected_balances_at_ts={
                    end
                    - relativedelta(minutes=1): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5000")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("1.78087")),
                            (dimensions.APPLIED_INTEREST_TRACKER, Decimal("0")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-1.78087")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check interest application day",
                expected_balances_at_ts={
                    end: {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5001.78")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.APPLIED_INTEREST_TRACKER, Decimal("1.78")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("1.78")),
                        ],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_parameters
        )
        self.run_test_scenario(test_scenario)

    def test_account_closure_cleanup_no_accrued_interest(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        end = start + relativedelta(days=1)

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
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("100.00")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                        ]
                    },
                },
            ),
            SubTest(
                description="Set account to pending closure",
                events=[update_account_status_pending_closure(end, accounts.TIME_DEPOSIT)],
                expected_balances_at_ts={
                    end: {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("100.00")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                        ],
                    },
                },
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

    def test_account_closure_cleanup_with_accrued_and_applied_interest_and_withdrawals(self):
        start = datetime(2023, 1, 15, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        instance_parameters = {
            **time_deposit_instance_params,
            time_deposit.interest_application.PARAM_INTEREST_APPLICATION_DAY: "28",
        }
        interest_application_datetime = datetime(2023, 1, 28, 0, 1, 0, tzinfo=ZoneInfo("UTC"))
        end = start + relativedelta(days=15)

        sub_tests = [
            SubTest(
                description="Deposit funds and partially withdraw before first accrual",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="6000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination="GBP",
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination="GBP",
                        client_batch_id="partial_withdrawal_1000",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("6000.00")),
                        ],
                    },
                    start
                    + relativedelta(seconds=2): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5000.00")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("1000.00")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(seconds=2),
                        notification_type=time_deposit.WITHDRAWAL_FEES_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "denomination": "GBP",
                            "withdrawal_amount": "1000",
                            "flat_fee_amount": "10",
                            "percentage_fee_amount": "10.00",
                            "number_of_interest_days_fee": "0",
                            "total_fee_amount": "20.00",
                            "client_batch_id": "partial_withdrawal_1000",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Check first accrual event",
                # (5000 * (0.01/365)) = 0.13698630137 -> 0.13699 Rounded to 5DP
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5000.00")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.13699")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("1000.00")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.13699")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Interest application event",
                # 0.13699 * 13 = 1.78087
                expected_balances_at_ts={
                    interest_application_datetime: {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5001.78")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.APPLIED_INTEREST_TRACKER, Decimal("1.78")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("1000.00")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Set account to pending closure",
                events=[update_account_status_pending_closure(end, accounts.TIME_DEPOSIT)],
                expected_balances_at_ts={
                    end
                    - relativedelta(seconds=1): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5001.78")),
                            # (5000 * (0.01/365)) = 0.13704 Rounded to 5DP
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.13704")),
                            (dimensions.APPLIED_INTEREST_TRACKER, Decimal("1.78")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("1000.00")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.13704")),
                        ],
                    },
                    end: {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5001.78")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.APPLIED_INTEREST_TRACKER, Decimal("0")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("0")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=time_deposit_template_params,
            instance_params=instance_parameters,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_on_withdrawal_amount_is_forfeited(self):
        start = datetime(2023, 1, 15, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        instance_parameters = {
            **time_deposit_instance_params,
            time_deposit.interest_application.PARAM_INTEREST_APPLICATION_DAY: "28",
        }
        interest_application_datetime = start + relativedelta(days=13, minutes=1)
        withdrawal_datetime = interest_application_datetime + relativedelta(days=10)
        end = start + relativedelta(months=1)

        sub_tests = [
            SubTest(
                description="Deposit funds and wait for accrual",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                # (5000 * (0.01/365)) = 0.13698630137 -> 0.13699 Rounded to 5DP
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5000.00")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.13699")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.13699")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Interest application event",
                # 0.13699 * 13 = 1.78087
                expected_balances_at_ts={
                    interest_application_datetime: {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5001.78")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.APPLIED_INTEREST_TRACKER, Decimal("1.78")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Withdraw funds",
                events=[
                    create_outbound_hard_settlement_instruction(
                        # exactly half the balance
                        amount="2500.89",
                        event_datetime=withdrawal_datetime,
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_balances_at_ts={
                    withdrawal_datetime
                    - relativedelta(seconds=1): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5001.78")),
                            # (5000 * (0.01/365)) = 0.13704 Rounded to 5DP
                            # 0.13704*10 = 1.37040
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("1.37040")),
                            (dimensions.APPLIED_INTEREST_TRACKER, Decimal("1.78")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("0")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-1.37040")),
                        ],
                    },
                    withdrawal_datetime: {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("2500.89")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.68520")),
                            (dimensions.APPLIED_INTEREST_TRACKER, Decimal("1.78")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("2500.89")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.68520")),
                        ],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_parameters
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1829-2-AC-01"])
    def test_interest_on_full_withdrawal_is_forfeited_and_notification_sent(self):
        start = datetime(2023, 1, 15, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        instance_parameters = {
            **time_deposit_instance_params,
            time_deposit.interest_application.PARAM_INTEREST_APPLICATION_DAY: "28",
        }
        interest_application_datetime = start + relativedelta(days=13, minutes=1)
        withdrawal_datetime = interest_application_datetime + relativedelta(days=10)
        end = start + relativedelta(months=1)

        sub_tests = [
            SubTest(
                description="Deposit funds and wait for accrual",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                # (5000 * (0.01/365)) = 0.13698630137 -> 0.13699 Rounded to 5DP
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5000.00")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.13699")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.13699")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Interest application event",
                # 0.13699 * 13 = 1.78087
                expected_balances_at_ts={
                    interest_application_datetime: {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5001.78")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.APPLIED_INTEREST_TRACKER, Decimal("1.78")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Withdraw funds",
                events=[
                    create_outbound_hard_settlement_instruction(
                        # the whole balance
                        amount="5001.78",
                        event_datetime=withdrawal_datetime,
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_balances_at_ts={
                    withdrawal_datetime
                    - relativedelta(seconds=1): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5001.78")),
                            # (5000 * (0.01/365)) = 0.13704 Rounded to 5DP
                            # 0.13704*10 = 1.37040
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("1.37040")),
                            (dimensions.APPLIED_INTEREST_TRACKER, Decimal("1.78")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("0")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-1.37040")),
                        ],
                    },
                    withdrawal_datetime: {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.APPLIED_INTEREST_TRACKER, Decimal("1.78")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("5001.78")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=withdrawal_datetime,
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
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_parameters
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-2347-AC02", "CPP-2347-AC05", "CPP-2347-AC07", "CPP-1913-AC03"])
    def test_interest_accrual_and_application(self):
        start = datetime(2023, 1, 15, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        instance_parameters = {
            **time_deposit_instance_params,
            time_deposit.interest_application.PARAM_INTEREST_APPLICATION_DAY: "28",
        }
        interest_application_time = datetime(2023, 1, 28, 0, 1, 0, tzinfo=ZoneInfo("UTC"))
        end = datetime(2023, 1, 28, 0, 1, 2, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="Check daily interest calculation after 1 day",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(minutes=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                # (5000 * (0.01/365)) = 0.13698630137 -> 0.13699 Rounded to 5DP
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5000")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.13699")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.13699")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check accrued interest before zeroing out default balance",
                # 0.13699 * 3 days
                expected_balances_at_ts={
                    start
                    + relativedelta(days=3, seconds=2): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5000")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.41097")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.41097")
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="No interest accrued for a 0 GBP balance (balance cannot go negative)."
                "All accrued interest should be forfeited",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(days=3, minutes=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=4, seconds=2): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("5000")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Fund account and check daily interest calculation",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(days=4, minutes=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                # Daily accrual
                # (5000 * (0.01/365)) = 0.13698630137 -> 0.13699 Rounded to 5DP
                expected_balances_at_ts={
                    start
                    + relativedelta(days=5, seconds=2): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5000")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.13699")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("5000")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.13699")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check daily interest calculation before application",
                # 0.13699 * 9 days = 1.23291
                expected_balances_at_ts={
                    start
                    + relativedelta(days=13, seconds=2): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5000")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("1.23291")),
                            (dimensions.APPLIED_INTEREST_TRACKER, Decimal("0")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("5000")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-1.23291")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check interest application day",
                expected_balances_at_ts={
                    interest_application_time: {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("5001.23")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.APPLIED_INTEREST_TRACKER, Decimal("1.23")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("5000")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("1.23")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Close the account and check balances are zero-ed out",
                events=[
                    update_account_status_pending_closure(
                        timestamp=end,
                        account_id=self.account_id_base,
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, "5001.23"),
                            (dimensions.APPLIED_INTEREST_TRACKER, Decimal("0")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("0")),
                        ],
                    }
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_parameters
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(
        [
            "CPP-2077-AC01",
            "CPP-2077-AC02",
            "CPP-2077-AC03",
            "CPP-2077-AC04",
            "CPP-2077-AC07",
            "CPP-2077-AC08",
        ]
    )
    def test_account_maturity_notifications_when_term_is_days(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        end = start + relativedelta(days=6, seconds=1)

        notify_upcoming_maturity_datetime = start + relativedelta(
            days=4, hour=0, minute=0, second=0
        )
        account_maturity_datetime = start + relativedelta(days=5, hour=0, minute=0, second=0)

        template_params = {
            **time_deposit_template_params,
            time_deposit.deposit_parameters.PARAM_TERM_UNIT: "days",
        }
        sub_tests = [
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
                            "account_maturity_datetime": "2022-01-06 00:00:00+00:00",
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

    @ac_coverage(
        [
            "CPP-2077-AC01",
            "CPP-2077-AC02",
            "CPP-2077-AC03",
            "CPP-2077-AC04",
            "CPP-2077-AC07",
            "CPP-2077-AC08",
        ]
    )
    def test_account_maturity_notifications_when_term_is_months(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        end = start + relativedelta(months=1, days=4)

        notify_upcoming_maturity_datetime = start + relativedelta(
            days=31, hour=0, minute=0, second=0
        )
        account_maturity_datetime = start + relativedelta(
            months=1, days=1, hour=0, minute=0, second=0
        )

        instance_params = {
            **time_deposit_instance_params,
            time_deposit.deposit_parameters.PARAM_TERM: "1",
        }
        sub_tests = [
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
                            "account_maturity_datetime": "2022-02-02 00:00:00+00:00",
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
                            "account_maturity_datetime": "2022-02-02 00:00:00+00:00",
                            "reason": "Account has now reached maturity",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-2077-AC05", "CPP-2077-AC07", "CPP-2077-AC08"])
    def test_account_maturity_when_term_is_days_and_desired_maturity_date_is_present(
        self,
    ):
        start = DEFAULT_SIMULATION_START_DATETIME
        end = start + relativedelta(days=12, seconds=1)
        # this is the user provided maturity date which overrides the contract
        # calculated maturity date based on term and term unit
        desired_account_maturity_datetime = datetime(
            year=2022, month=1, day=9, hour=0, minute=0, second=0, tzinfo=ZoneInfo("UTC")
        )

        expected_notify_upcoming_maturity_datetime = datetime(
            year=2022, month=1, day=9, hour=0, minute=0, second=0, tzinfo=ZoneInfo("UTC")
        )

        expected_account_maturity_datetime = datetime(
            year=2022, month=1, day=10, hour=0, minute=0, second=0, tzinfo=ZoneInfo("UTC")
        )
        instance_params = {
            **time_deposit_instance_params,
            time_deposit.deposit_maturity.PARAM_DESIRED_MATURITY_DATE: str(
                desired_account_maturity_datetime.date()
            ),
        }
        sub_tests = [
            SubTest(
                description="Notification before account maturity",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            expected_notify_upcoming_maturity_datetime,
                        ],
                        event_id=time_deposit.deposit_maturity.NOTIFY_UPCOMING_MATURITY_EVENT,
                        account_id=accounts.TIME_DEPOSIT,
                    ),
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=expected_notify_upcoming_maturity_datetime,
                        notification_type=time_deposit.NOTIFY_UPCOMING_MATURITY_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "account_maturity_datetime": "2022-01-10 00:00:00+00:00",
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
                            expected_account_maturity_datetime,
                        ],
                        event_id=time_deposit.deposit_maturity.ACCOUNT_MATURITY_EVENT,
                        account_id=accounts.TIME_DEPOSIT,
                    ),
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=expected_account_maturity_datetime,
                        notification_type=time_deposit.ACCOUNT_MATURITY_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "account_maturity_datetime": "2022-01-10 00:00:00+00:00",
                            "reason": "Account has now reached maturity",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-2077-AC05", "CPP-2077-AC07", "CPP-2077-AC08"])
    def test_account_maturity_when_term_is_months_and_desired_maturity_date_is_present(
        self,
    ):
        start = DEFAULT_SIMULATION_START_DATETIME
        end = start + relativedelta(months=2, seconds=1)
        # this is the user provided maturity date which overrides the contract
        # calculated maturity date based on term and term unit
        desired_account_maturity_datetime = datetime(
            year=2022, month=1, day=31, hour=0, minute=0, second=0, tzinfo=ZoneInfo("UTC")
        )

        expected_notify_upcoming_maturity_datetime = datetime(
            year=2022, month=1, day=31, hour=0, minute=0, second=0, tzinfo=ZoneInfo("UTC")
        )
        expected_account_maturity_datetime = datetime(
            year=2022, month=2, day=1, hour=0, minute=0, second=0, tzinfo=ZoneInfo("UTC")
        )

        template_params = {
            **time_deposit_template_params,
            time_deposit.deposit_parameters.PARAM_TERM: "1",
        }
        instance_params = {
            **time_deposit_instance_params,
            time_deposit.deposit_maturity.PARAM_DESIRED_MATURITY_DATE: str(
                desired_account_maturity_datetime.date()
            ),
        }
        sub_tests = [
            SubTest(
                description="Notification before account maturity",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            expected_notify_upcoming_maturity_datetime,
                        ],
                        event_id=time_deposit.deposit_maturity.NOTIFY_UPCOMING_MATURITY_EVENT,
                        account_id=accounts.TIME_DEPOSIT,
                    ),
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=expected_notify_upcoming_maturity_datetime,
                        notification_type=time_deposit.NOTIFY_UPCOMING_MATURITY_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "account_maturity_datetime": "2022-02-01 00:00:00+00:00",
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
                            expected_account_maturity_datetime,
                        ],
                        event_id=time_deposit.deposit_maturity.ACCOUNT_MATURITY_EVENT,
                        account_id=accounts.TIME_DEPOSIT,
                    ),
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=expected_account_maturity_datetime,
                        notification_type=time_deposit.ACCOUNT_MATURITY_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "account_maturity_datetime": "2022-02-01 00:00:00+00:00",
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
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(
        [
            "CPP-2077-AC01",
            "CPP-2077-AC02",
            "CPP-2077-AC03",
            "CPP-2077-AC04",
            "CPP-2077-AC07",
            "CPP-2077-AC08",
            "CPP-2077-AC09",
        ]
    )
    def test_account_maturity_is_updated_to_next_non_holiday_date_when_falls_on_holiday(
        self,
    ):
        start = DEFAULT_SIMULATION_START_DATETIME
        end = start + relativedelta(days=14, seconds=1)
        # this is the user provided maturity date which is overridden to
        # `expected_account_maturity_datetime` as this is the next non holiday date
        # based on calendars
        initial_maturity_datetime = datetime(
            year=2022, month=1, day=9, hour=0, minute=0, second=0, tzinfo=ZoneInfo("UTC")
        )
        holiday_start = datetime(2022, 1, 10, tzinfo=ZoneInfo("UTC"))
        holiday_end = datetime(2022, 1, 11, 23, tzinfo=ZoneInfo("UTC"))

        expected_notify_upcoming_maturity_datetime = datetime(
            year=2022, month=1, day=11, hour=0, minute=0, second=0, tzinfo=ZoneInfo("UTC")
        )

        expected_account_maturity_datetime = datetime(
            year=2022, month=1, day=12, hour=0, minute=0, second=0, tzinfo=ZoneInfo("UTC")
        )
        instance_params = {
            **time_deposit_instance_params,
            time_deposit.deposit_maturity.PARAM_DESIRED_MATURITY_DATE: str(
                initial_maturity_datetime.date()
            ),
        }
        sub_tests = [
            SubTest(
                description="Notification before account maturity when maturity falls on a holiday",
                events=[
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
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            expected_notify_upcoming_maturity_datetime,
                        ],
                        event_id=time_deposit.deposit_maturity.NOTIFY_UPCOMING_MATURITY_EVENT,
                        account_id=accounts.TIME_DEPOSIT,
                    ),
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=expected_notify_upcoming_maturity_datetime,
                        notification_type=time_deposit.NOTIFY_UPCOMING_MATURITY_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "account_maturity_datetime": "2022-01-12 00:00:00+00:00",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Notification at account maturity when maturity falls on a holiday",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            expected_account_maturity_datetime,
                        ],
                        event_id=time_deposit.deposit_maturity.ACCOUNT_MATURITY_EVENT,
                        account_id=accounts.TIME_DEPOSIT,
                    ),
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=expected_account_maturity_datetime,
                        notification_type=time_deposit.ACCOUNT_MATURITY_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "account_maturity_datetime": "2022-01-12 00:00:00+00:00",
                            "reason": "Account has now reached maturity",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(
        [
            "CPP-2077-AC01",
            "CPP-2077-AC02",
            "CPP-2077-AC03",
            "CPP-2077-AC04",
            "CPP-2077-AC06",
            "CPP-2077-AC07",
            "CPP-2077-AC08",
        ]
    )
    def test_transaction_after_account_maturity_is_rejected(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        end = start + relativedelta(days=6, seconds=1)

        account_maturity_datetime = start + relativedelta(days=5, hour=0, minute=0, second=0)

        template_params = {
            **time_deposit_template_params,
            time_deposit.deposit_parameters.PARAM_TERM_UNIT: "days",
        }
        sub_tests = [
            SubTest(
                description="Posting before account maturity and within deposit period is accepted",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("1000"))],
                    },
                },
            ),
            SubTest(
                description="Account maturity notification",
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
            SubTest(
                description="Posting on account maturity is rejected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=account_maturity_datetime + relativedelta(seconds=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("1000"))],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        account_maturity_datetime + relativedelta(seconds=1),
                        account_id=accounts.TIME_DEPOSIT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="No transactions are allowed at or after account maturity",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-2092-AC09", "CPP-2092-AC10", "CPP-2092-AC12"])
    def test_invalid_withdrawals_are_rejected(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        # all logic takes place outside of periods
        after_periods_datetime = start + relativedelta(days=2)
        end = start + relativedelta(days=3, hours=1)

        template_params = {
            **time_deposit_template_params,
            time_deposit.cooling_off_period.PARAM_COOLING_OFF_PERIOD: "1",
            time_deposit.deposit_period.PARAM_DEPOSIT_PERIOD: "0",
            time_deposit.withdrawal_fees.PARAM_EARLY_WITHDRAWAL_PERCENTAGE_FEE: "0.01",
            time_deposit.withdrawal_fees.PARAM_MAXIMUM_WITHDRAWAL_PERCENTAGE_LIMIT: "0.9",
        }

        sub_tests = [
            SubTest(
                description="Make an initial deposit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start,
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("100"))],
                    },
                },
            ),
            SubTest(
                description="Withdrawal amount is less than fee amount",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5",
                        event_datetime=after_periods_datetime + relativedelta(seconds=2),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    after_periods_datetime
                    + relativedelta(seconds=2): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("100")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("0")),
                        ],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        after_periods_datetime + relativedelta(seconds=2),
                        account_id=accounts.TIME_DEPOSIT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="The withdrawal fees of 10.05 GBP are not"
                        " covered by the withdrawal amount of 5 GBP.",
                    )
                ],
            ),
            SubTest(
                description="Withdrawal amount exceeds balance amount",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=after_periods_datetime + relativedelta(seconds=3),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    after_periods_datetime
                    + relativedelta(seconds=3): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("100")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("0")),
                        ],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        after_periods_datetime + relativedelta(seconds=3),
                        account_id=accounts.TIME_DEPOSIT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="The withdrawal amount of 150 GBP exceeds the"
                        " available balance of 100 GBP.",
                    )
                ],
            ),
            SubTest(
                description="Partial withdrawal above the withdrawal amount limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="95",
                        event_datetime=after_periods_datetime + relativedelta(seconds=4),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    after_periods_datetime
                    + relativedelta(seconds=4): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("100")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("0")),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=after_periods_datetime + relativedelta(seconds=4),
                        account_id=accounts.TIME_DEPOSIT,
                        name="maximum_withdrawal_limit",
                        value="90.00",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        after_periods_datetime + relativedelta(seconds=4),
                        account_id=accounts.TIME_DEPOSIT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="The withdrawal amount of 95 GBP would exceed "
                        "the available withdrawal limit of 90.00 GBP.",
                    )
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

    @ac_coverage(["CPP-2092-AC13", "CPP-2092-AC14"])
    def test_withdrawals_above_and_below_fee_free_limit(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        # all logic takes place outside of periods
        after_periods_datetime = start + relativedelta(days=2)
        end = start + relativedelta(days=3, hours=1)

        instance_params = {
            **time_deposit_instance_params,
            time_deposit.withdrawal_fees.PARAM_FEE_FREE_WITHDRAWAL_PERCENTAGE_LIMIT: "0.15",
        }
        template_params = {
            **time_deposit_template_params,
            time_deposit.cooling_off_period.PARAM_COOLING_OFF_PERIOD: "1",
            time_deposit.deposit_period.PARAM_DEPOSIT_PERIOD: "0",
            time_deposit.withdrawal_fees.PARAM_EARLY_WITHDRAWAL_PERCENTAGE_FEE: "0.01",
        }

        sub_tests = [
            SubTest(
                description="Make an initial deposit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start,
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("100"))],
                    },
                },
            ),
            SubTest(
                description="Withdrawal below the fee free limit accepted with no fees, "
                "zero fees notification sent",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=after_periods_datetime + relativedelta(seconds=2),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                        client_batch_id="10_withdrawal",
                    )
                ],
                expected_balances_at_ts={
                    after_periods_datetime
                    + relativedelta(seconds=2): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("90")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("10")),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=after_periods_datetime + relativedelta(seconds=2),
                        account_id=accounts.TIME_DEPOSIT,
                        name="fee_free_withdrawal_limit",
                        value="15.00",
                    )
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=after_periods_datetime + relativedelta(seconds=2),
                        notification_type=time_deposit.WITHDRAWAL_FEES_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "denomination": "GBP",
                            "withdrawal_amount": "10",
                            "flat_fee_amount": "0",
                            "percentage_fee_amount": "0",
                            "number_of_interest_days_fee": "0",
                            "total_fee_amount": "0",
                            "client_batch_id": "10_withdrawal",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Withdrawal exceeding fee free limit is accepted with fee notification",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="15",
                        event_datetime=after_periods_datetime + relativedelta(seconds=4),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                        client_batch_id="15_withdrawal",
                    )
                ],
                expected_balances_at_ts={
                    after_periods_datetime
                    + relativedelta(seconds=4): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("75")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("25")),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=after_periods_datetime + relativedelta(seconds=4),
                        account_id=accounts.TIME_DEPOSIT,
                        name="fee_free_withdrawal_limit",
                        value="15.00",
                    )
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=after_periods_datetime + relativedelta(seconds=4),
                        notification_type=time_deposit.WITHDRAWAL_FEES_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "denomination": "GBP",
                            "withdrawal_amount": "15",
                            "flat_fee_amount": "10",
                            "percentage_fee_amount": "0.10",
                            "number_of_interest_days_fee": "0",
                            "total_fee_amount": "10.10",
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
            template_params=template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-2092-AC15", "CPP-2092-AC16"])
    def test_withdrawals_on_public_holiday_with_and_without_override(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        # all logic takes place outside of periods
        after_periods_datetime = start + relativedelta(days=2)
        holiday_start = after_periods_datetime
        holiday_end = after_periods_datetime + relativedelta(hours=1)
        end = start + relativedelta(days=2, hours=1)

        instance_params = {
            **time_deposit_instance_params,
        }
        template_params = {
            **time_deposit_template_params,
            time_deposit.cooling_off_period.PARAM_COOLING_OFF_PERIOD: "1",
            time_deposit.deposit_period.PARAM_DEPOSIT_PERIOD: "1",
            time_deposit.withdrawal_fees.PARAM_EARLY_WITHDRAWAL_PERCENTAGE_FEE: "0.01",
        }

        sub_tests = [
            SubTest(
                description="Make an initial deposit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start,
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("100")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Block early withdrawals on holiday days without override",
                events=[
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
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=holiday_start + relativedelta(seconds=2),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    holiday_start
                    + relativedelta(seconds=2): {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("100"))],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        holiday_start + relativedelta(seconds=2),
                        account_id=accounts.TIME_DEPOSIT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Cannot withdraw on public holidays.",
                    )
                ],
            ),
            SubTest(
                description="Allow early withdrawals on holiday days with override",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="15",
                        event_datetime=holiday_start + relativedelta(seconds=4),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                        instruction_details={"calendar_override": "true"},
                        client_batch_id="calendar_override_withdrawal",
                    ),
                ],
                expected_balances_at_ts={
                    holiday_start
                    + relativedelta(seconds=4): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("85")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("15")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=holiday_start + relativedelta(seconds=4),
                        notification_type=time_deposit.WITHDRAWAL_FEES_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "denomination": "GBP",
                            "withdrawal_amount": "15",
                            "flat_fee_amount": "10",
                            "percentage_fee_amount": "0.15",
                            "number_of_interest_days_fee": "0",
                            "total_fee_amount": "10.15",
                            "client_batch_id": "calendar_override_withdrawal",
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
            template_params=template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-2366-AC03"])
    def test_full_withdrawal_with_number_of_interest_days_early_withdrawal_fee_configured(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        # all logic takes place outside of periods
        after_periods_datetime = start + relativedelta(days=2)
        end = start + relativedelta(days=3, hours=1)

        instance_params = {
            **time_deposit_instance_params,
            time_deposit.fixed_interest_accrual.PARAM_FIXED_INTEREST_RATE: "0.02",
            time_deposit.withdrawal_fees.PARAM_FEE_FREE_WITHDRAWAL_PERCENTAGE_LIMIT: "0.15",
        }
        template_params = {
            **time_deposit_template_params,
            time_deposit.cooling_off_period.PARAM_COOLING_OFF_PERIOD: "1",
            time_deposit.deposit_period.PARAM_DEPOSIT_PERIOD: "0",
            time_deposit.withdrawal_fees.PARAM_EARLY_WITHDRAWAL_PERCENTAGE_FEE: "0.01",
            time_deposit.PARAM_NUMBER_OF_INTEREST_DAYS_EARLY_WITHDRAWAL_FEE: "90",
        }

        sub_tests = [
            SubTest(
                description="Make an initial deposit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start,
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("10000"))],
                    },
                },
            ),
            SubTest(
                description="Full withdrawal with number of interest days fee configured "
                "overrides percentage fee",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=after_periods_datetime + relativedelta(seconds=4),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                        client_batch_id="full_withdrawal",
                    )
                ],
                expected_balances_at_ts={
                    after_periods_datetime
                    + relativedelta(seconds=4): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("10000")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=after_periods_datetime + relativedelta(seconds=4),
                        notification_type=time_deposit.WITHDRAWAL_FEES_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "denomination": "GBP",
                            "withdrawal_amount": "10000",
                            "flat_fee_amount": "10",
                            "percentage_fee_amount": "0",
                            # (10000 * (2% / 365 days)) * 90 days = 49.32
                            "number_of_interest_days_fee": "49.32",
                            "total_fee_amount": "59.32",
                            "client_batch_id": "full_withdrawal",
                        },
                        resource_id=accounts.TIME_DEPOSIT,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                    ExpectedContractNotification(
                        timestamp=after_periods_datetime + relativedelta(seconds=4),
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
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-2366-AC04", "CPP-2092-AC09"])
    def test_partial_withdrawal_with_number_of_interest_days_early_withdrawal_fee_configured(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        # all logic takes place outside of periods
        after_periods_datetime = start + relativedelta(days=2)
        end = start + relativedelta(days=3, hours=1)

        instance_params = {
            **time_deposit_instance_params,
            time_deposit.fixed_interest_accrual.PARAM_FIXED_INTEREST_RATE: "0.02",
        }
        template_params = {
            **time_deposit_template_params,
            time_deposit.cooling_off_period.PARAM_COOLING_OFF_PERIOD: "1",
            time_deposit.deposit_period.PARAM_DEPOSIT_PERIOD: "0",
            time_deposit.withdrawal_fees.PARAM_EARLY_WITHDRAWAL_PERCENTAGE_FEE: "0.01",
            time_deposit.PARAM_NUMBER_OF_INTEREST_DAYS_EARLY_WITHDRAWAL_FEE: "90",
        }

        sub_tests = [
            SubTest(
                description="Make an initial deposit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start,
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.TIME_DEPOSIT: [(dimensions.DEFAULT, Decimal("10000"))],
                    },
                },
            ),
            SubTest(
                description="Partial withdrawal less than fee amount",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="20",
                        event_datetime=after_periods_datetime + relativedelta(seconds=2),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    after_periods_datetime
                    + relativedelta(seconds=2): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("10000")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("0")),
                        ],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        after_periods_datetime + relativedelta(seconds=2),
                        account_id=accounts.TIME_DEPOSIT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="The withdrawal fees of 59.32 GBP are not"
                        " covered by the withdrawal amount of 20 GBP.",
                    )
                ],
            ),
            SubTest(
                description="Partial withdrawal with number of interest days fee configured "
                "overrides percentage fee",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=after_periods_datetime + relativedelta(seconds=4),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                        client_batch_id="partial_withdrawal_2000",
                    )
                ],
                expected_balances_at_ts={
                    after_periods_datetime
                    + relativedelta(seconds=4): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("8000")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("2000")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=after_periods_datetime + relativedelta(seconds=4),
                        notification_type=time_deposit.WITHDRAWAL_FEES_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.TIME_DEPOSIT,
                            "denomination": "GBP",
                            "withdrawal_amount": "2000",
                            "flat_fee_amount": "10",
                            "percentage_fee_amount": "0",
                            # (10000 * (2% / 365 days)) * 90 days = 49.32
                            "number_of_interest_days_fee": "49.32",
                            "total_fee_amount": "59.32",
                            "client_batch_id": "partial_withdrawal_2000",
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
            template_params=template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_withdrawal_fees_derived_parameters(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        # all logic takes place outside of periods
        interest_application_datetime = start.replace(day=3, hour=0, minute=1, second=0)
        end = start + relativedelta(days=4, hours=1)

        instance_params = {
            **time_deposit_instance_params,
            time_deposit.withdrawal_fees.PARAM_FEE_FREE_WITHDRAWAL_PERCENTAGE_LIMIT: "0.15",
            time_deposit.interest_application.PARAM_INTEREST_APPLICATION_DAY: "3",
        }

        template_params = {
            **time_deposit_template_params,
            time_deposit.cooling_off_period.PARAM_COOLING_OFF_PERIOD: "1",
            time_deposit.deposit_period.PARAM_DEPOSIT_PERIOD: "0",
            time_deposit.withdrawal_fees.PARAM_EARLY_WITHDRAWAL_PERCENTAGE_FEE: "0.01",
            time_deposit.withdrawal_fees.PARAM_MAXIMUM_WITHDRAWAL_PERCENTAGE_LIMIT: "0.9",
        }

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
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.TIME_DEPOSIT,
                        name=time_deposit.withdrawal_fees.PARAM_MAXIMUM_WITHDRAWAL_LIMIT,
                        value="900.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.TIME_DEPOSIT,
                        name=time_deposit.withdrawal_fees.PARAM_FEE_FREE_WITHDRAWAL_LIMIT,
                        value="150.00",
                    ),
                ],
            ),
            SubTest(
                description="Make valid withdrawal, derived parameter values should be unaffected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="200",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.TIME_DEPOSIT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("800")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("200")),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(hours=1),
                        account_id=accounts.TIME_DEPOSIT,
                        name=time_deposit.withdrawal_fees.PARAM_MAXIMUM_WITHDRAWAL_LIMIT,
                        value="900.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(hours=1),
                        account_id=accounts.TIME_DEPOSIT,
                        name=time_deposit.withdrawal_fees.PARAM_FEE_FREE_WITHDRAWAL_LIMIT,
                        value="150.00",
                    ),
                ],
            ),
            SubTest(
                description="Check interest is applied and tracked correctly, derived parameter "
                "values should be unaffected",
                # (80 * (0.01/365)) = 0.02191780821 -> 0.02192 Rounded to 5DP
                # total accrued interest = 0.02192 * 2 = 0.04384
                expected_balances_at_ts={
                    interest_application_datetime
                    - relativedelta(seconds=1): {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("800")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.04384")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("200")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.04384")),
                        ],
                    },
                    interest_application_datetime: {
                        accounts.TIME_DEPOSIT: [
                            (dimensions.DEFAULT, Decimal("800.04")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.APPLIED_INTEREST_TRACKER, Decimal("0.04")),
                            (dimensions.EARLY_WITHDRAWALS_TRACKER, Decimal("200")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=interest_application_datetime + relativedelta(seconds=1),
                        account_id=accounts.TIME_DEPOSIT,
                        name=time_deposit.withdrawal_fees.PARAM_MAXIMUM_WITHDRAWAL_LIMIT,
                        value="900.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=interest_application_datetime + relativedelta(seconds=1),
                        account_id=accounts.TIME_DEPOSIT,
                        name=time_deposit.withdrawal_fees.PARAM_FEE_FREE_WITHDRAWAL_LIMIT,
                        value="150.00",
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )
        self.run_test_scenario(test_scenario)
