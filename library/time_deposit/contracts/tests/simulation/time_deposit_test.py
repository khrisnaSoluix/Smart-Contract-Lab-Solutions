# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import List, Dict

# common
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ContractModuleConfig,
    ExpectedDerivedParameter,
    SimulationTestScenario,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_inbound_hard_settlement_instruction,
    create_outbound_hard_settlement_instruction,
    create_account_instruction,
    create_outbound_authorisation_instruction,
    create_settlement_event,
    create_inbound_authorisation_instruction,
    create_release_event,
    create_calendar,
    create_calendar_event,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    ExpectedWorkflow,
    get_balances,
    get_num_postings,
    get_workflows_by_id,
    get_processed_scheduled_events,
    SimulationTestCase,
)

CONTRACT_FILE = "library/time_deposit/contracts/time_deposit.py"
CONTRACT_MODULES_ALIAS_FILE_MAP = {
    "utils": "library/common/contract_modules/utils.py",
    "interest": "library/common/contract_modules/interest.py",
}
ASSET_CONTRACT_FILE = "internal_accounts/testing_internal_asset_account_contract.py"
LIABILITY_CONTRACT_FILE = "internal_accounts/testing_internal_liability_account_contract.py"

CONTRACT_FILES = [CONTRACT_FILE]

DEFAULT_DENOMINATION = "GBP"
TD_ACCOUNT = "TIME_DEPOSIT_ACCOUNT"
ACCRUED_INTEREST_PAYABLE_ACCOUNT = "ACCRUED_INTEREST_PAYABLE"
INTEREST_PAID_ACCOUNT = "INTEREST_PAID"
TIME_DEPOSIT_BANK_HOLIDAY = "PUBLIC_HOLIDAYS"

ASSET = "ASSET"
LIABILITY = "LIABILITY"

default_internal_accounts = [
    # generic account used for external postings
    "1",
    ACCRUED_INTEREST_PAYABLE_ACCOUNT,
    INTEREST_PAID_ACCOUNT,
]

default_template_params = {
    "denomination": "GBP",
    "maximum_balance": "1000",
    "minimum_first_deposit": "50",
    "single_deposit": "unlimited",
    "accrued_interest_payable_account": ACCRUED_INTEREST_PAYABLE_ACCOUNT,
    "interest_paid_account": INTEREST_PAID_ACCOUNT,
    "accrual_precision": "5",
    "fulfillment_precision": "2",
    "interest_application_hour": "23",
    "interest_application_minute": "59",
    "interest_application_second": "59",
    "interest_accrual_hour": "23",
    "interest_accrual_minute": "58",
    "interest_accrual_second": "59",
}
default_instance_params = {
    "gross_interest_rate": "0.149",
    "interest_application_frequency": "monthly",
    "interest_application_day": "31",
    "deposit_period": "28",
    "grace_period": "0",
    "cool_off_period": "0",
    "term_unit": "months",
    "term": "60",
    "fee_free_percentage_limit": "0",
    "withdrawal_fee": "10",
    "withdrawal_percentage_fee": "0",
    "account_closure_period": "7",
    "period_end_hour": "0",
    "auto_rollover_type": "no_rollover",
    "partial_principal_amount": "0",
    "rollover_term_unit": "months",
    "rollover_term": "60",
    "rollover_gross_interest_rate": "0.149",
    "rollover_interest_application_day": "31",
    "rollover_interest_application_frequency": "monthly",
    "rollover_grace_period": "7",
    "rollover_period_end_hour": "0",
    "rollover_account_closure_period": "7",
}

GBP_DEFAULT_DIMENSIONS = BalanceDimensions(denomination="GBP")
GBP_CAPITALISED_INTEREST = BalanceDimensions(address="CAPITALISED_INTEREST", denomination="GBP")
GBP_ACCRUED_INTEREST_PAYABLE = BalanceDimensions(
    address="ACCRUED_INTEREST_PAYABLE", denomination="GBP"
)
GBP_INTERNAL_CONTRA = BalanceDimensions(address="INTERNAL_CONTRA", denomination="GBP")
GBP_COMMITTED = BalanceDimensions(phase="POSTING_PHASE_COMMITTED", denomination="GBP")
GBP_PENDING_OUTGOING = BalanceDimensions(phase="POSTING_PHASE_PENDING_OUTGOING", denomination="GBP")
GBP_PENDING_INCOMING = BalanceDimensions(phase="POSTING_PHASE_PENDING_INCOMING", denomination="GBP")
DEFAULT_DIM = BalanceDimensions(
    address="DEFAULT",
    asset="COMMERCIAL_BANK_MONEY",
    denomination="GBP",
    phase="POSTING_PHASE_COMMITTED",
)


class TimeDepositTestBase(SimulationTestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_filepaths = CONTRACT_FILES
        cls.contract_modules = [
            ContractModuleConfig(alias, file_path)
            for (alias, file_path) in CONTRACT_MODULES_ALIAS_FILE_MAP.items()
        ]
        super().setUpClass()

    def default_simulate_account_event(self, start, instance_params=None):
        return create_account_instruction(
            timestamp=start,
            account_id=TD_ACCOUNT,
            product_id="0",
            instance_param_vals=instance_params or default_instance_params,
        )

    def run_test(
        self,
        start: datetime,
        end: datetime,
        events: List,
        template_parameters: Dict[str, str] = None,
        output_account_ids=None,
        output_timestamps=None,
    ):

        return self.client.simulate_smart_contract(
            contract_codes=self.smart_contract_contents.copy(),
            smart_contract_version_ids=["0"],
            templates_parameters=[
                template_parameters or default_template_params,
            ],
            internal_account_ids=default_internal_accounts,
            output_account_ids=output_account_ids,
            output_timestamps=output_timestamps,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            contract_config=self._get_contract_config(template_params=template_parameters),
        )

    def _get_contract_config(self, template_params=None, instance_params=None):
        contract_modules = [
            ContractModuleConfig(alias, file_path)
            for (alias, file_path) in CONTRACT_MODULES_ALIAS_FILE_MAP.items()
        ]

        return ContractConfig(
            contract_file_path=CONTRACT_FILE,
            template_params=template_params or default_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or default_instance_params,
                    account_id_base=TD_ACCOUNT,
                )
            ],
            linked_contract_modules=contract_modules,
        )

    def _get_simulation_test_scenario(
        self,
        start,
        end,
        sub_tests,
        template_params=None,
        instance_params=None,
        internal_accounts=None,
        debug=False,
    ):
        return SimulationTestScenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            contract_config=self._get_contract_config(template_params, instance_params),
            internal_accounts=internal_accounts,
            debug=debug,
        )


class TimeDepositPeriodTest(TimeDepositTestBase):
    def test_grace_period(self):
        # Checks for scenarios when grace period is active.
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 25, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["deposit_period"] = "0"
        instance_params["cool_off_period"] = "0"
        instance_params["grace_period"] = "11"
        instance_params["period_end_hour"] = "0"

        sub_test_1_ts = start + relativedelta(days=8, hour=21, minute=0, second=1)
        sub_test_2_ts = start + relativedelta(days=9, hours=23, minutes=59, seconds=59)
        sub_test_3_ts = start + relativedelta(days=11, hour=0, minute=0, second=1)
        sub_test_4_ts = start + relativedelta(days=12, hour=0, minute=0, second=1)

        sub_tests = [
            SubTest(
                description="Withdrawal within grace period should be accepted",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=TD_ACCOUNT,
                        amount="100.00",
                        event_datetime=start + relativedelta(days=1),
                    ),
                    create_outbound_hard_settlement_instruction(
                        target_account_id=TD_ACCOUNT,
                        amount="25.00",
                        event_datetime=sub_test_1_ts,
                    ),
                ],
                expected_balances_at_ts={
                    sub_test_1_ts: {TD_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "75")]},
                },
            ),
            SubTest(
                description="Deposit within grace period should be accepted",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=TD_ACCOUNT,
                        amount="17.00",
                        event_datetime=sub_test_2_ts,
                    ),
                ],
                expected_balances_at_ts={
                    sub_test_2_ts: {TD_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "92")]},
                },
            ),
            SubTest(
                description="Deposit outside grace period should be rejected.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=TD_ACCOUNT,
                        amount="18.00",
                        event_datetime=sub_test_3_ts,
                    ),
                ],
                expected_balances_at_ts={
                    sub_test_3_ts: {TD_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "92")]},
                },
            ),
            SubTest(
                description="Withdrawal outside grace period should be rejected.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=TD_ACCOUNT,
                        amount="17.00",
                        event_datetime=sub_test_4_ts,
                    ),
                ],
                expected_balances_at_ts={
                    sub_test_4_ts: {TD_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "92")]},
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_deposit_period(self):
        # Checks for scenarios when deposit period is active.
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 3, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        template_params["single_deposit"] = "unlimited"
        instance_params = default_instance_params.copy()
        instance_params["deposit_period"] = "1"
        instance_params["cool_off_period"] = "0"
        instance_params["grace_period"] = "0"

        sub_test_1_ts = start + relativedelta(days=1, hour=18, minute=1)
        sub_test_2_ts = start + relativedelta(days=1, hour=19, minute=0, second=1)
        sub_test_3_ts = start + relativedelta(days=1, hour=19, minute=0, second=2)

        sub_tests = [
            SubTest(
                description="Inbound hard settlement allowed during deposit period.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=TD_ACCOUNT,
                        amount="100.00",
                        event_datetime=start,
                    ),
                ],
                expected_balances_at_ts={
                    start: {TD_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "100")]},
                },
            ),
            SubTest(
                description="Rejected withdrawals cannot be done in deposit period.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="30",
                        event_datetime=sub_test_1_ts,
                        target_account_id=TD_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    sub_test_1_ts: {TD_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "100")]},
                },
            ),
            SubTest(
                description="Rejected effective day is grater than deposit period.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=TD_ACCOUNT,
                        amount="101.00",
                        event_datetime=sub_test_2_ts,
                    ),
                ],
                expected_balances_at_ts={
                    sub_test_2_ts: {TD_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "100")]},
                },
            ),
            SubTest(
                description="Rejected withdrawals cannot be done in deposit period.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="30",
                        event_datetime=sub_test_3_ts,
                        target_account_id=TD_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    sub_test_3_ts: {TD_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "100")]},
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_cool_off_period(self):
        # Checks for scenarios when grace period is active.
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 25, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["deposit_period"] = "3"
        instance_params["cool_off_period"] = "11"
        instance_params["grace_period"] = "0"
        instance_params["period_end_hour"] = "0"

        sub_test_1_ts = start + relativedelta(days=8, hour=21, minute=0, second=1)
        sub_test_2_ts = start + relativedelta(days=10, hours=23, minutes=59, seconds=59)
        sub_test_3_ts = start + relativedelta(days=11, hour=0, minute=0, second=1)
        sub_test_4_ts = start + relativedelta(days=12, hour=0, minute=0, second=1)

        sub_tests = [
            SubTest(
                description="Withdrawal accepted during cool off period.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=TD_ACCOUNT,
                        amount="100.00",
                        event_datetime=start + relativedelta(days=1),
                    ),
                    create_outbound_hard_settlement_instruction(
                        target_account_id=TD_ACCOUNT,
                        amount="25.00",
                        event_datetime=sub_test_1_ts,
                    ),
                ],
                expected_balances_at_ts={
                    sub_test_1_ts: {TD_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "75")]},
                },
            ),
            SubTest(
                description="Deposit accepted during cool off period.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=TD_ACCOUNT,
                        amount="17.00",
                        event_datetime=sub_test_2_ts,
                    )
                ],
                expected_balances_at_ts={
                    sub_test_2_ts: {TD_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "92")]},
                },
            ),
            SubTest(
                description="Deposit rejected outside cool off period.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=TD_ACCOUNT,
                        amount="18.00",
                        event_datetime=sub_test_3_ts,
                    ),
                ],
                expected_balances_at_ts={
                    sub_test_3_ts: {TD_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "92")]},
                },
            ),
            SubTest(
                description="Withdrawal rejected outside cool off period.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=TD_ACCOUNT,
                        amount="19.00",
                        event_datetime=sub_test_4_ts,
                    ),
                ],
                expected_balances_at_ts={
                    sub_test_4_ts: {TD_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "92")]},
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_no_period(self):
        # Checks for scenarios when there are no periods at all.
        # Could be useful for rollover scenarios where there is no grace period.
        # No deposits can be made.
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 3, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        template_params["single_deposit"] = "unlimited"
        instance_params = default_instance_params.copy()
        instance_params["deposit_period"] = "0"
        instance_params["cool_off_period"] = "0"
        instance_params["grace_period"] = "0"

        sub_tests = [
            SubTest(
                description="Inbound hard settlement not allowed.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=TD_ACCOUNT,
                        amount="100.00",
                        event_datetime=start,
                    ),
                ],
                expected_balances_at_ts={
                    start: {TD_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "0")]},
                },
            ),
            SubTest(
                description="Outbound hard settlement not allowed.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=TD_ACCOUNT,
                        amount="100.00",
                        event_datetime=start,
                    ),
                ],
                expected_balances_at_ts={
                    start: {TD_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "0")]},
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_accrual_with_cool_off_period(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 9, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["cool_off_period"] = "7"

        events = [
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="50.00", event_datetime=start
            )
        ]

        sub_tests = [
            SubTest(
                description="check interest applied after cool off period",
                events=events,
                expected_balances_at_ts={
                    datetime(2019, 1, 8, tzinfo=timezone.utc): {
                        TD_ACCOUNT: [
                            (GBP_ACCRUED_INTEREST_PAYABLE, "0"),
                            (GBP_INTERNAL_CONTRA, "0"),
                        ]
                    },
                    end: {
                        TD_ACCOUNT: [
                            (GBP_ACCRUED_INTEREST_PAYABLE, "0.16328"),
                            (GBP_INTERNAL_CONTRA, "-0.16328"),
                        ]
                    },
                },
            )
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_accrual_with_grace_period(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 9, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["cool_off_period"] = "0"
        instance_params["grace_period"] = "7"
        instance_params["deposit_period"] = "0"

        events = [
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="50.00", event_datetime=start
            )
        ]

        sub_tests = [
            SubTest(
                description="check interest applied after cool off period",
                events=events,
                expected_balances_at_ts={
                    datetime(2019, 1, 8, tzinfo=timezone.utc): {
                        TD_ACCOUNT: [
                            (GBP_ACCRUED_INTEREST_PAYABLE, "0"),
                            (GBP_INTERNAL_CONTRA, "0"),
                        ]
                    },
                    end: {
                        TD_ACCOUNT: [
                            (GBP_ACCRUED_INTEREST_PAYABLE, "0.16328"),
                            (GBP_INTERNAL_CONTRA, "-0.16328"),
                        ]
                    },
                },
            )
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_accrual_without_grace_and_cool_off_period(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 9, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["cool_off_period"] = "0"
        instance_params["grace_period"] = "0"
        instance_params["deposit_period"] = "5"

        events = [
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="50.00", event_datetime=start
            )
        ]

        sub_tests = [
            SubTest(
                description="check interest will be accrued immidiately"
                + " when there is no cool off period or grace period.",
                events=events,
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 23, 58, 59, tzinfo=timezone.utc): {
                        TD_ACCOUNT: [
                            (GBP_ACCRUED_INTEREST_PAYABLE, "0.02041"),
                            (GBP_INTERNAL_CONTRA, "-0.02041"),
                        ]
                    },
                    end: {
                        TD_ACCOUNT: [
                            (GBP_ACCRUED_INTEREST_PAYABLE, "0.16328"),
                            (GBP_INTERNAL_CONTRA, "-0.16328"),
                        ]
                    },
                },
            )
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_inbound_auth_accepted_within_period(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 2, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_authorisation_instruction(
                target_account_id=TD_ACCOUNT,
                amount="1000",
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id="INBOUND_AUTH",
                event_datetime=start + timedelta(days=1),
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={TD_ACCOUNT: {end: [(GBP_PENDING_INCOMING, "1000")]}},
        )

    def test_inbound_auth_rejected_outside_period(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 5, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["deposit_period"] = "1"

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_authorisation_instruction(
                target_account_id=TD_ACCOUNT,
                amount="1000.00",
                event_datetime=start + timedelta(days=2),
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        self.assertEqual(get_num_postings(res, TD_ACCOUNT), 0)

    def test_full_settlement_accepted_after_deposit_period_close(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 5, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["deposit_period"] = "1"
        instance_params["account_closure_period"] = "3"

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_authorisation_instruction(
                target_account_id=TD_ACCOUNT,
                amount="1000.00",
                event_datetime=start,
                client_transaction_id="SETTLEMENT_TEST_TRANSACTION",
            ),
            create_settlement_event(
                amount="1000.00",
                event_datetime=start + timedelta(days=2),
                client_transaction_id="SETTLEMENT_TEST_TRANSACTION",
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={TD_ACCOUNT: {end: [(GBP_DEFAULT_DIMENSIONS, "1000")]}},
        )

    def test_partial_settlement_accepted_after_deposit_period_close(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 5, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["deposit_period"] = "1"

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_authorisation_instruction(
                target_account_id=TD_ACCOUNT,
                amount="1000.00",
                event_datetime=start,
                client_transaction_id="SETTLEMENT_TEST_TRANSACTION",
            ),
            create_settlement_event(
                amount="30.00",
                event_datetime=start + timedelta(days=2),
                client_transaction_id="SETTLEMENT_TEST_TRANSACTION",
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={TD_ACCOUNT: {end: [(GBP_DEFAULT_DIMENSIONS, "30")]}},
        )

    def test_release_accepted_after_deposit_period_close(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 5, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["deposit_period"] = "1"

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_authorisation_instruction(
                target_account_id=TD_ACCOUNT,
                amount="1000",
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id="RELEASE_TEST_TRANSACTION",
                event_datetime=start,
            ),
            create_release_event(
                client_transaction_id="RELEASE_TEST_TRANSACTION",
                event_datetime=start + timedelta(days=2),
                batch_details={"withdrawal_override": "true"},
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={TD_ACCOUNT: {end: [(GBP_PENDING_INCOMING, "0")]}},
        )

    def test_account_closure_period_end_with_zero_balance_closes_account(self):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2020, 1, 4, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["deposit_period"] = "1"
        instance_params["grace_period"] = "0"
        instance_params["cool_off_period"] = "0"
        instance_params["account_closure_period"] = "1"

        events = [self.default_simulate_account_event(start, instance_params)]

        res = self.run_test(start, end, events, template_params)

        close_account_workflow_requests = get_workflows_by_id(
            res, "TIME_DEPOSIT_CLOSURE", TD_ACCOUNT
        ).latest()
        self.assertEqual(close_account_workflow_requests["context"], {"account_id": TD_ACCOUNT})

    def test_account_closure_period_end_with_committed_balance_doesnt_close_account(
        self,
    ):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2020, 1, 4, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["deposit_period"] = "1"
        instance_params["account_closure_period"] = "1"

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT,
                amount="50.00",
                event_datetime=start,
                denomination="GBP",
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        close_account_workflow_requests = get_workflows_by_id(
            res, "TIME_DEPOSIT_CLOSURE", TD_ACCOUNT
        )

        self.assertEqual(len(close_account_workflow_requests), 0)

    def test_account_closure_end_with_pending_in_balance_doesnt_close_account(self):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2020, 1, 4, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["deposit_period"] = "1"
        instance_params["account_closure_period"] = "1"

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_authorisation_instruction(
                target_account_id=TD_ACCOUNT,
                amount="50.00",
                event_datetime=start,
                denomination="GBP",
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        close_account_workflow_requests = get_workflows_by_id(
            res, "TIME_DEPOSIT_CLOSURE", TD_ACCOUNT
        )

        self.assertEqual(len(close_account_workflow_requests), 0)

    def test_derived_parameters_grace_period(self):
        start = datetime(2020, 1, 1, minute=5, second=10, tzinfo=timezone.utc)
        end = datetime(2020, 1, 10, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["deposit_period"] = "0"
        instance_params["grace_period"] = "3"
        instance_params["account_closure_period"] = "4"
        instance_params["cool_off_period"] = "0"
        instance_params["term"] = "2"

        events = []
        param_output_time = datetime(2020, 1, 2, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="check derived parameters",
                events=events,
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=param_output_time,
                        account_id=TD_ACCOUNT,
                        name="cool_off_period_end_date",
                        value="None",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=param_output_time,
                        account_id=TD_ACCOUNT,
                        name="deposit_period_end_date",
                        value="None",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=param_output_time,
                        account_id=TD_ACCOUNT,
                        name="grace_period_end_date",
                        value="2020-01-04 00:00:00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=param_output_time,
                        account_id=TD_ACCOUNT,
                        name="account_closure_period_end_date",
                        value="2020-01-08 00:05:10",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=param_output_time,
                        account_id=TD_ACCOUNT,
                        name="maturity_date",
                        value="2020-03-01 00:05:10",
                    ),
                ],
            )
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_derived_parameters_no_grace_period(self):
        start = datetime(2020, 1, 1, minute=5, second=10, tzinfo=timezone.utc)
        end = datetime(2020, 1, 10, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["deposit_period"] = "1"
        instance_params["grace_period"] = "0"
        instance_params["cool_off_period"] = "2"
        instance_params["term"] = "2"
        instance_params["account_closure_period"] = "5"
        events = []
        param_output_time = datetime(2020, 1, 2, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="check derived parameters",
                events=events,
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=param_output_time,
                        account_id=TD_ACCOUNT,
                        name="cool_off_period_end_date",
                        value="2020-01-03 00:00:00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=param_output_time,
                        account_id=TD_ACCOUNT,
                        name="fee_free_withdrawal_limit",
                        value="0.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=param_output_time,
                        account_id=TD_ACCOUNT,
                        name="deposit_period_end_date",
                        value="2020-01-02 00:00:00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=param_output_time,
                        account_id=TD_ACCOUNT,
                        name="grace_period_end_date",
                        value="None",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=param_output_time,
                        account_id=TD_ACCOUNT,
                        name="account_closure_period_end_date",
                        value="2020-01-08 00:05:10",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=param_output_time,
                        account_id=TD_ACCOUNT,
                        name="maturity_date",
                        value="2020-03-01 00:05:10",
                    ),
                ],
            )
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)


class TimeDepositDepositTest(TimeDepositTestBase):
    def test_less_than_minimum_deposit_rejected(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 2, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT,
                amount="49.00",
                event_datetime=start + timedelta(days=1),
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        self.assertEqual(get_num_postings(res, TD_ACCOUNT), 0)

    def test_second_deposit_rejected_with_single_deposit(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 3, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        template_params["single_deposit"] = "single"
        instance_params = default_instance_params.copy()

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT,
                amount="50.00",
                event_datetime=start + timedelta(days=1),
                client_transaction_id="DEPOSIT_1",
            ),
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT,
                amount="60.00",
                event_datetime=start + timedelta(days=1),
                client_transaction_id="DEPOSIT_2",
            ),
        ]
        res = self.run_test(start, end, events, template_params)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={TD_ACCOUNT: {end: [(GBP_DEFAULT_DIMENSIONS, "50")]}},
        )

    def test_second_deposit_accepted_without_single_deposit(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 3, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT,
                amount="50.00",
                event_datetime=start + timedelta(days=1),
                client_transaction_id="DEPOSIT_1",
            ),
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT,
                amount="60.00",
                event_datetime=start + timedelta(days=1),
                client_transaction_id="DEPOSIT_2",
            ),
        ]
        res = self.run_test(start, end, events, template_params)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={TD_ACCOUNT: {end: [(GBP_DEFAULT_DIMENSIONS, "110")]}},
        )

    def test_second_deposit_less_than_minimum_accepted(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 3, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT,
                amount="50.00",
                event_datetime=start + timedelta(days=1),
                client_transaction_id="DEPOSIT_1",
            ),
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT,
                amount="49.00",
                event_datetime=start + timedelta(days=1),
                client_transaction_id="DEPOSIT_2",
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={TD_ACCOUNT: {end: [(GBP_DEFAULT_DIMENSIONS, "99")]}},
        )

    def test_second_deposit_rejected_over_max_balance(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 3, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT,
                amount="999.00",
                event_datetime=start + timedelta(days=1),
                client_transaction_id="DEPOSIT_1",
            ),
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT,
                amount="50.00",
                event_datetime=start + timedelta(days=1),
                client_transaction_id="DEPOSIT_2",
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={TD_ACCOUNT: {end: [(GBP_DEFAULT_DIMENSIONS, "999")]}},
        )


class TimeDepositInterestTest(TimeDepositTestBase):
    def test_interest_accrual_5dp(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 2, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()

        events = [
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="50.00", event_datetime=start
            )
        ]

        sub_tests = [
            SubTest(
                description="check interest applied",
                events=events,
                expected_balances_at_ts={
                    end: {
                        TD_ACCOUNT: [
                            (GBP_ACCRUED_INTEREST_PAYABLE, "0.02041"),
                            (GBP_INTERNAL_CONTRA, "-0.02041"),
                        ]
                    },
                },
            )
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_accrual_2dp(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 2, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        template_params["accrual_precision"] = "2"
        instance_params = default_instance_params.copy()

        events = [
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="50.00", event_datetime=start
            )
        ]

        sub_tests = [
            SubTest(
                description="check interest applied",
                events=events,
                expected_balances_at_ts={
                    end: {
                        TD_ACCOUNT: [
                            (GBP_ACCRUED_INTEREST_PAYABLE, "0.02"),
                            (GBP_INTERNAL_CONTRA, "-0.02"),
                        ]
                    },
                },
            )
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_account_maturity_stops_interest_accrual_and_application(self):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2020, 3, 1, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["term"] = "1"
        instance_params["interest_application_frequency"] = "monthly"
        instance_params["interest_application_day"] = "1"

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="50.00", event_datetime=start
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        apply_accrued_interest = get_processed_scheduled_events(
            res, "APPLY_ACCRUED_INTEREST", TD_ACCOUNT
        )
        self.assertEqual(len(apply_accrued_interest), 0)

        accrue_interest = get_processed_scheduled_events(res, "ACCRUE_INTEREST", TD_ACCOUNT)
        self.assertEqual(accrue_interest[-1], "2020-01-31T23:58:59Z")
        self.assertEqual(len(accrue_interest), 31)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={
                TD_ACCOUNT: {
                    end: [
                        (GBP_DEFAULT_DIMENSIONS, "50.63"),
                        (GBP_CAPITALISED_INTEREST, "0.63"),
                    ]
                }
            },
        )

    def test_capitalised_interest_moved_between_internal_contra(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 8, 2, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["deposit_period"] = "1"
        instance_params["interest_application_frequency"] = "monthly"
        instance_params["term"] = "7"
        instance_params["interest_application_day"] = "7"
        instance_params["account_closure_period"] = "7"
        instance_params["grace_period"] = "0"
        instance_params["period_end_hour"] = "0"

        sub_tests = [
            SubTest(
                description="transfer applied on the first month throught workflow",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=TD_ACCOUNT, amount="500", event_datetime=start
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        TD_ACCOUNT: [
                            (GBP_DEFAULT_DIMENSIONS, "500.00"),
                            (GBP_CAPITALISED_INTEREST, "0"),
                            (GBP_ACCRUED_INTEREST_PAYABLE, "0"),
                        ]
                    },
                    start
                    + relativedelta(days=7): {
                        TD_ACCOUNT: [
                            (GBP_DEFAULT_DIMENSIONS, "501.43"),
                            (GBP_CAPITALISED_INTEREST, "1.43"),
                            (GBP_INTERNAL_CONTRA, "-1.43"),
                            (GBP_ACCRUED_INTEREST_PAYABLE, "0"),
                        ]
                    },
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="TIME_DEPOSIT_APPLIED_INTEREST_TRANSFER",
                        account_id=TD_ACCOUNT,
                        count=7,
                        run_times=[start + relativedelta(days=7, hour=23, minute=59, second=59)],
                        contexts=[
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "1.43",
                            }
                        ],
                    )
                ],
            ),
            SubTest(
                description="withdrawal doesn't affect capitalised interest address",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=TD_ACCOUNT,
                        amount="50",
                        event_datetime=start + relativedelta(days=10),
                        batch_details={"withdrawal_override": "true"},
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=9): {
                        TD_ACCOUNT: [
                            (GBP_DEFAULT_DIMENSIONS, "501.43"),
                            (GBP_CAPITALISED_INTEREST, "1.43"),
                            (GBP_INTERNAL_CONTRA, "-1.83938"),
                            (GBP_ACCRUED_INTEREST_PAYABLE, "0.40938"),
                        ]
                    },
                    start
                    + relativedelta(days=10): {
                        TD_ACCOUNT: [
                            (GBP_DEFAULT_DIMENSIONS, "451.43"),
                            (GBP_CAPITALISED_INTEREST, "1.43"),
                            (GBP_INTERNAL_CONTRA, "-2.04407"),
                            (GBP_ACCRUED_INTEREST_PAYABLE, "0.61407"),
                        ]
                    },
                },
            ),
            SubTest(
                description="partial withdrawal of capitalised interest",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=TD_ACCOUNT,
                        amount="465.89",
                        event_datetime=end - relativedelta(days=4, hour=23, minute=59, second=59),
                        batch_details={"withdrawal_override": "true"},
                    )
                ],
                expected_balances_at_ts={
                    end
                    - relativedelta(days=5, hour=23, minute=59, second=59): {
                        TD_ACCOUNT: [
                            (GBP_DEFAULT_DIMENSIONS, "485.89"),
                            (GBP_CAPITALISED_INTEREST, "35.89"),
                        ]
                    },
                    end
                    - relativedelta(days=4, hour=23, minute=59, second=59): {
                        TD_ACCOUNT: [
                            (GBP_DEFAULT_DIMENSIONS, "20.00"),
                            (GBP_CAPITALISED_INTEREST, "20.00"),
                        ]
                    },
                },
            ),
            SubTest(
                description="end remaining interest applied through workflow",
                expected_balances_at_ts={
                    end
                    - relativedelta(days=1, hour=23, minute=59, second=59): {
                        TD_ACCOUNT: [
                            (GBP_DEFAULT_DIMENSIONS, "24.38"),
                            (GBP_CAPITALISED_INTEREST, "24.38"),
                        ]
                    },
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="TIME_DEPOSIT_MATURITY",
                        account_id=TD_ACCOUNT,
                        count=1,
                        run_times=[end - relativedelta(days=1, hour=23, minute=59, second=59)],
                        contexts=[
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "4.38",
                            }
                        ],
                    )
                ],
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_accrual_occurs_at_set_time_daily(self):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2020, 1, 3, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        template_params["interest_accrual_hour"] = "11"
        template_params["interest_accrual_minute"] = "22"
        template_params["interest_accrual_second"] = "33"
        instance_params = default_instance_params.copy()

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="100.00", event_datetime=start
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        accrue_interest_events = get_processed_scheduled_events(res, "ACCRUE_INTEREST", TD_ACCOUNT)
        self.assertEqual(len(accrue_interest_events), 2)
        self.assertEqual(accrue_interest_events, ["2020-01-01T11:22:33Z", "2020-01-02T11:22:33Z"])


class TimeDepositMaturityTest(TimeDepositTestBase):
    def test_pending_outbound_auth_rejected_before_maturity(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 3, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_outbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT,
                amount="50.00",
                event_datetime=start + timedelta(days=1),
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        self.assertEqual(get_num_postings(res, TD_ACCOUNT), 0)
        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={TD_ACCOUNT: {end: [(GBP_DEFAULT_DIMENSIONS, "0")]}},
        )

    def test_pending_out_plus_settlement_magic_word_accepted_before_maturity(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 3, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="1000.00", event_datetime=start
            ),
            create_outbound_authorisation_instruction(
                target_account_id=TD_ACCOUNT,
                amount="100.00",
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id="OUTBOUND_AUTH",
                event_datetime=start + timedelta(minutes=1),
                client_batch_id="OUTBOUND_AUTH",
                batch_details={"withdrawal_override": "true"},
            ),
            create_settlement_event(
                amount="60",
                client_transaction_id="OUTBOUND_AUTH",
                event_datetime=start + timedelta(minutes=2),
                batch_details={"withdrawal_override": "true"},
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={
                TD_ACCOUNT: {end: [(GBP_COMMITTED, "940"), (GBP_PENDING_OUTGOING, "-40")]}
            },
        )

    def test_pending_outbound_auth_plus_settlement_accepted_after_maturity(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 2, 4, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["term"] = "1"
        instance_params["gross_interest_rate"] = "0"

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="50.00", event_datetime=start
            ),
            create_outbound_authorisation_instruction(
                target_account_id=TD_ACCOUNT,
                amount="50",
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id="OUTBOUND_AUTH",
                event_datetime=start + timedelta(days=33),
            ),
            create_settlement_event(
                amount="30",
                client_transaction_id="OUTBOUND_AUTH",
                event_datetime=start + timedelta(days=33, minutes=1),
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={
                TD_ACCOUNT: {end: [(GBP_COMMITTED, "20"), (GBP_PENDING_OUTGOING, "-20")]}
            },
        )

    def test_account_maturity_correct_day_one_month(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 2, 3, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["term"] = "1"

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="50.00", event_datetime=start
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        account_maturity_events = get_processed_scheduled_events(
            res, "ACCOUNT_MATURITY", TD_ACCOUNT
        )
        self.assertIn("2019-02-01T00:00:00Z", account_maturity_events)
        self.assertEqual(len(account_maturity_events), 1)

        maturity_workflows = get_workflows_by_id(res, "TIME_DEPOSIT_MATURITY", TD_ACCOUNT).latest()
        self.assertEqual(
            maturity_workflows["context"],
            {"account_id": TD_ACCOUNT, "applied_interest_amount": "0.00"},
        )

    def test_account_maturity_ends_on_correct_day_leap_year(self):
        start = datetime(2020, 2, 29, tzinfo=timezone.utc)
        end = datetime(2021, 3, 1, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["term"] = "12"
        instance_params["cool_off_period"] = "0"
        instance_params["grace_period"] = "0"

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="50.00", event_datetime=start
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        account_maturity_events = get_processed_scheduled_events(
            res, "ACCOUNT_MATURITY", TD_ACCOUNT
        )
        self.assertIn("2021-02-28T00:00:00Z", account_maturity_events)
        self.assertEqual(len(account_maturity_events), 1)

        maturity_workflows = get_workflows_by_id(res, "TIME_DEPOSIT_MATURITY", TD_ACCOUNT).latest()
        self.assertEqual(
            maturity_workflows["context"],
            {"account_id": TD_ACCOUNT, "applied_interest_amount": "0.63"},
        )

    def test_account_maturity_correct_day_seven_days(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 9, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["term_unit"] = "days"
        instance_params["term"] = "7"

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="50.00", event_datetime=start
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        account_maturity_events = get_processed_scheduled_events(
            res, "ACCOUNT_MATURITY", TD_ACCOUNT
        )
        self.assertIn("2019-01-08T00:00:00Z", account_maturity_events)
        self.assertEqual(len(account_maturity_events), 1)

        maturity_workflows = get_workflows_by_id(res, "TIME_DEPOSIT_MATURITY", TD_ACCOUNT).latest()
        self.assertEqual(
            maturity_workflows["context"],
            {"account_id": TD_ACCOUNT, "applied_interest_amount": "0.14"},
        )


class TimeDepositHolidayTest(TimeDepositTestBase):
    def test_maturity_on_holiday(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 2, 5, tzinfo=timezone.utc)
        holiday_start = datetime(2019, 2, 1, tzinfo=timezone.utc)
        holiday_end = datetime(2019, 2, 1, 23, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["term"] = "1"

        events = [
            create_calendar(
                timestamp=start,
                calendar_id=TIME_DEPOSIT_BANK_HOLIDAY,
            ),
            create_calendar_event(
                timestamp=start,
                calendar_event_id="NEW_YEAR",
                calendar_id=TIME_DEPOSIT_BANK_HOLIDAY,
                start_timestamp=holiday_start,
                end_timestamp=holiday_end,
            ),
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="50.00", event_datetime=start
            ),
        ]

        sub_tests = [
            SubTest(
                description="check withdrawal date when it falls on a holiday",
                events=events,
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="TIME_DEPOSIT_MATURITY",
                        account_id=TD_ACCOUNT,
                        count=1,
                        run_times=[end],
                        contexts=[
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "0.02",
                            },
                        ],
                    )
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=datetime(2019, 1, 1, 1, tzinfo=timezone.utc),
                        account_id=TD_ACCOUNT,
                        name="maturity_date",
                        value="2019-02-02 00:00:00",
                    ),
                ],
            )
        ]
        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_maturity_on_holiday_consecutive(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 2, 5, tzinfo=timezone.utc)
        holiday_start = datetime(2019, 2, 1, tzinfo=timezone.utc)
        holiday_end = datetime(2019, 2, 1, 23, tzinfo=timezone.utc)
        holiday_start2 = datetime(2019, 2, 2, tzinfo=timezone.utc)
        holiday_end2 = datetime(2019, 2, 2, 23, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["term"] = "1"

        events = [
            create_calendar(
                timestamp=start,
                calendar_id=TIME_DEPOSIT_BANK_HOLIDAY,
            ),
            create_calendar_event(
                timestamp=start,
                calendar_event_id="NEW_YEAR",
                calendar_id=TIME_DEPOSIT_BANK_HOLIDAY,
                start_timestamp=holiday_start,
                end_timestamp=holiday_end,
            ),
            create_calendar_event(
                timestamp=start,
                calendar_event_id="CHRISTMAS",
                calendar_id=TIME_DEPOSIT_BANK_HOLIDAY,
                start_timestamp=holiday_start2,
                end_timestamp=holiday_end2,
            ),
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="50.00", event_datetime=start
            ),
        ]

        sub_tests = [
            SubTest(
                description="check withdrawal date when it falls on a holiday",
                events=events,
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="TIME_DEPOSIT_MATURITY",
                        account_id=TD_ACCOUNT,
                        count=1,
                        run_times=[end],
                        contexts=[
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "0.04",
                            },
                        ],
                    )
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=datetime(2019, 1, 1, 1, tzinfo=timezone.utc),
                        account_id=TD_ACCOUNT,
                        name="maturity_date",
                        value="2019-02-03 00:00:00",
                    ),
                ],
            )
        ]
        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_withdrawal_on_calendar_override_true_accepted_before_maturity(self):
        start = datetime(2019, 1, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 3, 1, tzinfo=timezone.utc)
        holiday_start = datetime(2019, 1, 2, 0, tzinfo=timezone.utc)
        holiday_end = datetime(2019, 1, 2, 23, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()

        events = [
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="1000.00", event_datetime=start
            ),
            create_calendar(
                timestamp=start,
                calendar_id=TIME_DEPOSIT_BANK_HOLIDAY,
            ),
            create_calendar_event(
                timestamp=start,
                calendar_event_id="NEW_YEAR",
                calendar_id=TIME_DEPOSIT_BANK_HOLIDAY,
                start_timestamp=holiday_start,
                end_timestamp=holiday_end,
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT,
                amount="60.00",
                event_datetime=start + timedelta(days=1),
                batch_details={
                    "withdrawal_override": "true",
                    "calendar_override": "true",
                },
            ),
        ]

        sub_tests = [
            SubTest(
                description=(
                    "check withdrawal before maturity is accepted when on "
                    "a holiday withdrawal_override and calendar_override is true"
                ),
                events=events,
                expected_balances_at_ts={
                    end: {TD_ACCOUNT: [(GBP_COMMITTED, "940")]},
                },
            )
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_withdrawal_on_calendar_override_none_rejected_before_maturity(self):
        start = datetime(2019, 1, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 3, 1, tzinfo=timezone.utc)
        holiday_start = datetime(2019, 1, 2, 0, tzinfo=timezone.utc)
        holiday_end = datetime(2019, 1, 2, 23, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        events = [
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="1000.00", event_datetime=start
            ),
            create_calendar(
                timestamp=start,
                calendar_id=TIME_DEPOSIT_BANK_HOLIDAY,
            ),
            create_calendar_event(
                timestamp=start,
                calendar_event_id="NEW_YEAR",
                calendar_id=TIME_DEPOSIT_BANK_HOLIDAY,
                start_timestamp=holiday_start,
                end_timestamp=holiday_end,
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT,
                amount="60.00",
                event_datetime=start + timedelta(days=1),
                batch_details={
                    "withdrawal_override": "true",
                },
            ),
        ]

        sub_tests = [
            SubTest(
                description=(
                    "check withdrawal before maturity is rejected when on "
                    "a holiday and withdrawal_override is present"
                ),
                events=events,
                expected_balances_at_ts={
                    end: {TD_ACCOUNT: [(GBP_COMMITTED, "1000")]},
                },
            )
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_withdrawal_on_calendar_override_true_rejected_before_maturity(self):
        start = datetime(2019, 1, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 3, 1, tzinfo=timezone.utc)
        holiday_start = datetime(2019, 1, 2, 0, tzinfo=timezone.utc)
        holiday_end = datetime(2019, 1, 2, 23, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()

        events = [
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="1000.00", event_datetime=start
            ),
            create_calendar(
                timestamp=start,
                calendar_id=TIME_DEPOSIT_BANK_HOLIDAY,
            ),
            create_calendar_event(
                timestamp=start,
                calendar_event_id="NEW_YEAR",
                calendar_id=TIME_DEPOSIT_BANK_HOLIDAY,
                start_timestamp=holiday_start,
                end_timestamp=holiday_end,
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT,
                amount="60.00",
                event_datetime=start + timedelta(days=1),
                batch_details={"calendar_override": "true"},
            ),
        ]

        sub_tests = [
            SubTest(
                description=(
                    "check withdrawal before maturity is rejected when on"
                    "a holiday and withdrawal_override is not present in posting"
                ),
                events=events,
                expected_balances_at_ts={
                    end: {TD_ACCOUNT: [(GBP_COMMITTED, "1000")]},
                },
            )
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_withdrawal_not_on_calendar_override_none_accepted_before_maturity(self):
        start = datetime(2019, 1, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 3, 1, tzinfo=timezone.utc)
        holiday_start = datetime(2019, 1, 1, 0, tzinfo=timezone.utc)
        holiday_end = datetime(2019, 1, 1, 23, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()

        events = [
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="1000.00", event_datetime=start
            ),
            create_calendar(
                timestamp=start,
                calendar_id=TIME_DEPOSIT_BANK_HOLIDAY,
            ),
            create_calendar_event(
                timestamp=start,
                calendar_event_id="NEW_YEAR",
                calendar_id=TIME_DEPOSIT_BANK_HOLIDAY,
                start_timestamp=holiday_start,
                end_timestamp=holiday_end,
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT,
                amount="60.00",
                event_datetime=start + timedelta(days=1),
                batch_details={
                    "withdrawal_override": "true",
                },
            ),
        ]

        sub_tests = [
            SubTest(
                description=(
                    "check withdrawal before maturity is accepted when "
                    "is not a holiday and withdrawal_override is present"
                ),
                events=events,
                expected_balances_at_ts={
                    end: {TD_ACCOUNT: [(GBP_COMMITTED, "940")]},
                },
            )
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_withdrawal_not_on_calendar_override_none_rejected_before_maturity(self):
        start = datetime(2019, 1, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 1, 3, 1, tzinfo=timezone.utc)
        holiday_start = datetime(2019, 1, 1, 0, tzinfo=timezone.utc)
        holiday_end = datetime(2019, 1, 1, 23, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()

        events = [
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="1000.00", event_datetime=start
            ),
            create_calendar(
                timestamp=start,
                calendar_id=TIME_DEPOSIT_BANK_HOLIDAY,
            ),
            create_calendar_event(
                timestamp=start,
                calendar_event_id="NEW_YEAR",
                calendar_id=TIME_DEPOSIT_BANK_HOLIDAY,
                start_timestamp=holiday_start,
                end_timestamp=holiday_end,
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT,
                amount="60.00",
                event_datetime=start + timedelta(days=1),
            ),
        ]

        sub_tests = [
            SubTest(
                description=(
                    "check withdrawal before maturity is rejected when "
                    "not on a holiday and withdrawal_override is not present"
                ),
                events=events,
                expected_balances_at_ts={
                    end: {TD_ACCOUNT: [(GBP_COMMITTED, "1000")]},
                },
            )
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)


class TimeDepositBackdatedTest(TimeDepositTestBase):
    def test_single_backdated_deposit(self):
        # This test case will check that only one deposit can be done
        # Since single_deposit has been set to "single"
        # After deposit was made a backdated posting
        # Should not be allowed since there was already a posting done before it.
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=28, hour=23, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        template_params["single_deposit"] = "single"
        instance_params = default_instance_params.copy()

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_hard_settlement_instruction(
                amount="70",
                event_datetime=start + timedelta(days=4),
                target_account_id=TD_ACCOUNT,
                denomination=default_template_params["denomination"],
            ),
            # All deposits must now be rejected.
            create_inbound_hard_settlement_instruction(
                amount="75",
                event_datetime=start + timedelta(days=19),
                target_account_id=TD_ACCOUNT,
                denomination=default_template_params["denomination"],
                value_timestamp=start + timedelta(days=1, hours=2),
            ),
            create_inbound_hard_settlement_instruction(
                amount="76",
                event_datetime=start + timedelta(days=27),
                target_account_id=TD_ACCOUNT,
                denomination=default_template_params["denomination"],
                value_timestamp=start + timedelta(days=2),
            ),
        ]

        res = self.run_test(start, end, events, template_params)
        actual_balances = get_balances(res)
        expected_balances = {TD_ACCOUNT: {end: [(DEFAULT_DIM, Decimal("70"))]}}

        self.check_balances(expected_balances, actual_balances)
        self.assertEqual(get_num_postings(res, account_id=TD_ACCOUNT), 1)

    def test_multiple_backdated_deposit_max_balance(self):
        # This test case will check that multiple backdated deposit can be done
        # And must also remain below max account balance
        # Since single_deposit has been set to 'unlimited'

        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=28, hour=23, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        template_params["maximum_balance"] = "400"
        template_params["single_deposit"] = "unlimited"
        instance_params = default_instance_params.copy()
        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_hard_settlement_instruction(
                amount="101",
                event_datetime=start + timedelta(days=4),
                target_account_id=TD_ACCOUNT,
                denomination=default_template_params["denomination"],
            ),
            # All backdated deposits below will be accepted
            create_inbound_hard_settlement_instruction(
                amount="102",
                event_datetime=start + timedelta(days=19),
                target_account_id=TD_ACCOUNT,
                denomination=default_template_params["denomination"],
                value_timestamp=start + timedelta(days=1, hours=2),
            ),
            create_inbound_hard_settlement_instruction(
                amount="103",
                event_datetime=start + timedelta(days=27),
                target_account_id=TD_ACCOUNT,
                denomination=default_template_params["denomination"],
                value_timestamp=start + timedelta(days=2),
            ),
            # Except for this one as it will go above the max account balance of 400
            create_inbound_hard_settlement_instruction(
                amount="105",
                event_datetime=start + timedelta(days=27),
                target_account_id=TD_ACCOUNT,
                denomination=default_template_params["denomination"],
                value_timestamp=start + timedelta(days=2),
            ),
        ]

        res = self.run_test(start, end, events, template_params)
        actual_balances = get_balances(res)
        expected_balances = {TD_ACCOUNT: {end: [(DEFAULT_DIM, Decimal("306"))]}}

        self.check_balances(expected_balances, actual_balances)
        self.assertEqual(get_num_postings(res, account_id=TD_ACCOUNT), 3)

    def test_double_spending(self):
        # This test case will check if the TD account can go negative by doing
        # backdated postings

        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=15, hour=23, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["deposit_period"] = "4"
        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_hard_settlement_instruction(
                amount="1000",
                event_datetime=start + timedelta(days=3),
                target_account_id=TD_ACCOUNT,
                denomination=default_template_params["denomination"],
            ),
            create_outbound_hard_settlement_instruction(
                amount="1000",
                event_datetime=start + timedelta(days=4),
                target_account_id=TD_ACCOUNT,
                denomination=default_template_params["denomination"],
                batch_details={"withdrawal_override": "true"},
            ),
            # Should not get accepted.
            create_outbound_hard_settlement_instruction(
                amount="1000",
                event_datetime=start + timedelta(days=5),
                target_account_id=TD_ACCOUNT,
                denomination=default_template_params["denomination"],
                batch_details={"withdrawal_override": "true"},
                value_timestamp=start + timedelta(days=3, hours=1),
            ),
        ]

        res = self.run_test(start, end, events, template_params)
        actual_balances = get_balances(res)
        expected_balances = {TD_ACCOUNT: {end: [(DEFAULT_DIM, Decimal("0"))]}}

        self.check_balances(expected_balances, actual_balances)
        # Check that account was closed since balance is 0 at end of grace period.
        close_account_workflow_requests = get_workflows_by_id(
            res, "TIME_DEPOSIT_CLOSURE", TD_ACCOUNT
        )
        self.assertEqual(len(close_account_workflow_requests), 1)
        self.assertEqual(get_num_postings(res, account_id=TD_ACCOUNT), 2)

    def test_backdated_withdrawals(self):
        # This test case will check that a backdated withdrawal
        # With effective date less than maturity can happen
        # On all time ranges only if 'withdrawal_override': 'true'
        # On the other hand if backdated withdrawal effective date is after maturity
        # withdrawal_override': 'true' is not required

        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=7, day=28, hour=23, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        template_params["maximum_balance"] = "10000"
        instance_params = default_instance_params.copy()
        instance_params["gross_interest_rate"] = "0"
        template_params["single_deposit"] = "unlimited"
        instance_params["deposit_period"] = "1"
        instance_params["account_closure_period"] = "3"
        instance_params["grace_period"] = "0"
        instance_params["cool_off_period"] = "0"
        instance_params["period_end_hour"] = "0"
        instance_params["term"] = "5"

        sub_tests = [
            SubTest(
                description="check balance after deposits",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(days=0, hour=1),
                        target_account_id=TD_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(days=0, hour=2),
                        target_account_id=TD_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    start + relativedelta(days=0, hour=1): {TD_ACCOUNT: [(DEFAULT_DIM, "5000")]},
                    start + relativedelta(days=1, hour=1): {TD_ACCOUNT: [(DEFAULT_DIM, "10000")]},
                },
            ),
            SubTest(
                description="withdrawal during deposit period",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(days=1, hour=1),
                        target_account_id=TD_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        value_timestamp=start + relativedelta(days=1, hour=1),
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(days=1, hour=2),
                        target_account_id=TD_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        value_timestamp=start + relativedelta(days=1, hour=2),
                        batch_details={"withdrawal_override": "true"},
                    ),
                ],
                expected_balances_at_ts={
                    start + relativedelta(days=1, hour=1): {TD_ACCOUNT: [(DEFAULT_DIM, "10000")]},
                    start + relativedelta(days=1, hour=2): {TD_ACCOUNT: [(DEFAULT_DIM, "9000")]},
                },
            ),
            SubTest(
                description="withdrawal during account closure period",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(days=3, hour=1),
                        target_account_id=TD_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        value_timestamp=start + relativedelta(days=3, hour=1),
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(days=3, hour=2),
                        target_account_id=TD_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        value_timestamp=start + relativedelta(days=3, hour=2),
                        batch_details={"withdrawal_override": "true"},
                    ),
                ],
                expected_balances_at_ts={
                    start + relativedelta(days=3, hour=1): {TD_ACCOUNT: [(DEFAULT_DIM, "9000")]},
                    start + relativedelta(days=3, hour=2): {TD_ACCOUNT: [(DEFAULT_DIM, "8000")]},
                },
            ),
            SubTest(
                description="withdrawal after account closure period",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(days=10, hour=1),
                        target_account_id=TD_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        value_timestamp=start + relativedelta(days=10, hour=1),
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(days=10, hour=2),
                        target_account_id=TD_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        value_timestamp=start + relativedelta(days=10, hour=2),
                        batch_details={"withdrawal_override": "true"},
                    ),
                ],
                expected_balances_at_ts={
                    start + relativedelta(days=10, hour=1): {TD_ACCOUNT: [(DEFAULT_DIM, "8000")]},
                    start + relativedelta(days=10, hour=2): {TD_ACCOUNT: [(DEFAULT_DIM, "7000")]},
                },
            ),
            SubTest(
                description="withdrawal after maturity",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=end + relativedelta(days=-1, hour=1),
                        target_account_id=TD_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        value_timestamp=end + relativedelta(days=-2, hour=1),
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=end + relativedelta(days=-1, hour=2),
                        target_account_id=TD_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        value_timestamp=end + relativedelta(days=-2, hour=2),
                        batch_details={"withdrawal_override": "true"},
                    ),
                ],
                expected_balances_at_ts={
                    end + relativedelta(days=-2, hour=1): {TD_ACCOUNT: [(DEFAULT_DIM, "6000")]},
                    end + relativedelta(days=-2, hour=2): {TD_ACCOUNT: [(DEFAULT_DIM, "5000")]},
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_backdated_close_account(self):
        # Check if backdated withdrawal was done to 0 the account
        # It should still trigger a close workflow

        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=28, hour=23, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["gross_interest_rate"] = "1"
        instance_params["deposit_period"] = "10"
        template_params["single_deposit"] = "unlimited"
        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_hard_settlement_instruction(
                amount="70",
                event_datetime=start + timedelta(days=1),
                target_account_id=TD_ACCOUNT,
                denomination=default_template_params["denomination"],
            ),
            create_outbound_hard_settlement_instruction(
                amount="40",
                event_datetime=start + timedelta(days=2),
                target_account_id=TD_ACCOUNT,
                batch_details={"withdrawal_override": "true"},
                denomination=default_template_params["denomination"],
            ),
            create_outbound_hard_settlement_instruction(
                amount="30",
                event_datetime=start + timedelta(days=3),
                target_account_id=TD_ACCOUNT,
                denomination=default_template_params["denomination"],
                batch_details={"withdrawal_override": "true"},
                value_timestamp=start + timedelta(days=1),
            ),
        ]

        res = self.run_test(start, end, events, template_params)
        actual_balances = get_balances(res)
        expected_balances = {TD_ACCOUNT: {end: [(DEFAULT_DIM, Decimal("0"))]}}

        self.check_balances(expected_balances, actual_balances)
        # Check close workflow happened
        close_account_workflow_requests = get_workflows_by_id(
            res, "TIME_DEPOSIT_CLOSURE", TD_ACCOUNT
        )
        self.assertEqual(len(close_account_workflow_requests), 1)
        self.assertEqual(get_num_postings(res, account_id=TD_ACCOUNT), 3)

    def test_backdated_deposit_no_close_account(self):
        # Check if backdated deposit was done to fund the account
        # It should not trigger a close workflow

        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=28, hour=23, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        template_params["single_deposit"] = "unlimited"
        template_params["minimum_first_deposit"] = "50"
        instance_params = default_instance_params.copy()
        instance_params["gross_interest_rate"] = "0"
        instance_params["deposit_period"] = "10"

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_hard_settlement_instruction(
                amount="70",
                event_datetime=start + timedelta(days=1),
                target_account_id=TD_ACCOUNT,
                denomination=default_template_params["denomination"],
            ),
            create_outbound_hard_settlement_instruction(
                amount="40",
                event_datetime=start + timedelta(days=2),
                target_account_id=TD_ACCOUNT,
                batch_details={"withdrawal_override": "true"},
                denomination=default_template_params["denomination"],
            ),
            create_outbound_hard_settlement_instruction(
                amount="30",
                event_datetime=start + timedelta(days=3),
                target_account_id=TD_ACCOUNT,
                denomination=default_template_params["denomination"],
                batch_details={"withdrawal_override": "true"},
                value_timestamp=start + timedelta(days=1),
            ),
            create_inbound_hard_settlement_instruction(
                amount="70",
                event_datetime=start + timedelta(days=4),
                target_account_id=TD_ACCOUNT,
                denomination=default_template_params["denomination"],
                batch_details={"withdrawal_override": "true"},
                value_timestamp=start + timedelta(days=1),
            ),
        ]

        res = self.run_test(start, end, events, template_params)
        actual_balances = get_balances(res)
        expected_balances = {TD_ACCOUNT: {end: [(DEFAULT_DIM, Decimal("70"))]}}

        self.check_balances(expected_balances, actual_balances)
        # Check close workflow did not happened
        close_account_workflow_requests = get_workflows_by_id(
            res, "TIME_DEPOSIT_CLOSURE", TD_ACCOUNT
        )
        self.assertEqual(len(close_account_workflow_requests), 0)
        self.assertEqual(get_num_postings(res, account_id=TD_ACCOUNT), 4)


class TimeDepositTest(TimeDepositTestBase):
    def test_derived_parameters_with_term_days(self):
        start = datetime(2020, 1, 1, minute=5, second=10, microsecond=12, tzinfo=timezone.utc)
        end = datetime(2020, 1, 10, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["deposit_period"] = "3"
        instance_params["cool_off_period"] = "1"
        instance_params["grace_period"] = "0"
        instance_params["term_unit"] = "days"
        instance_params["term"] = "14"
        instance_params["account_closure_period"] = "5"
        events = []
        param_output_time = datetime(2020, 1, 2, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="check derived parameters",
                events=events,
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=param_output_time,
                        account_id=TD_ACCOUNT,
                        name="cool_off_period_end_date",
                        value="2020-01-02 00:00:00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=param_output_time,
                        account_id=TD_ACCOUNT,
                        name="deposit_period_end_date",
                        value="2020-01-04 00:00:00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=param_output_time,
                        account_id=TD_ACCOUNT,
                        name="grace_period_end_date",
                        value="None",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=param_output_time,
                        account_id=TD_ACCOUNT,
                        name="account_closure_period_end_date",
                        value="2020-01-09 00:05:10",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=param_output_time,
                        account_id=TD_ACCOUNT,
                        name="maturity_date",
                        value="2020-01-15 00:05:10",
                    ),
                ],
            )
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_withdrawal_below_balance_rejected(self):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2020, 2, 2, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["term"] = "1"

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="500.00", event_datetime=start
            ),
            create_outbound_authorisation_instruction(
                target_account_id=TD_ACCOUNT,
                amount="510.00",
                event_datetime=start + timedelta(days=32),
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT,
                amount="510.00",
                event_datetime=start + timedelta(days=32),
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={
                TD_ACCOUNT: {
                    end
                    - relativedelta(days=2, hour=23, minute=59, second=59): [
                        (GBP_DEFAULT_DIMENSIONS, "506.33"),
                        (GBP_CAPITALISED_INTEREST, "6.33"),
                    ]
                }
            },
        )

    def test_interest_accrual_application(self):
        # Checks interest accrual application is correct
        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 2, 15, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        template_params["maximum_balance"] = "20000"
        instance_params = default_instance_params.copy()
        instance_params["term"] = "1"
        instance_params["cool_off_period"] = "7"
        instance_params["grace_period"] = "0"
        instance_params["deposit_period"] = "0"
        instance_params["term_unit"] = "months"
        instance_params["period_end_hour"] = "23"
        instance_params["gross_interest_rate"] = ".01"
        instance_params["interest_application_day"] = "1"
        instance_params["interest_application_frequency"] = "weekly"

        sub_tests = [
            SubTest(
                description="Fund account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=TD_ACCOUNT,
                        amount="10000.00",
                        event_datetime=start + relativedelta(days=5),
                    ),
                ],
            ),
            SubTest(
                description="Verify 1st interest application",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=8): {
                        TD_ACCOUNT: [
                            (GBP_DEFAULT_DIMENSIONS, "10002.19"),
                            (GBP_CAPITALISED_INTEREST, "2.19"),
                            (GBP_ACCRUED_INTEREST_PAYABLE, "0"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Verify 2nd interest application",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=15): {
                        TD_ACCOUNT: [
                            (GBP_DEFAULT_DIMENSIONS, "10004.11"),
                            (GBP_CAPITALISED_INTEREST, "4.11"),
                            (GBP_ACCRUED_INTEREST_PAYABLE, "0"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Verify 3rd interest application",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=22): {
                        TD_ACCOUNT: [
                            (GBP_DEFAULT_DIMENSIONS, "10006.03"),
                            (GBP_CAPITALISED_INTEREST, "6.03"),
                            (GBP_ACCRUED_INTEREST_PAYABLE, "0"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Verify 4rth interest application",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=29): {
                        TD_ACCOUNT: [
                            (GBP_DEFAULT_DIMENSIONS, "10007.95"),
                            (GBP_CAPITALISED_INTEREST, "7.95"),
                            (GBP_ACCRUED_INTEREST_PAYABLE, "0"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Verify ending total balance",
                expected_balances_at_ts={
                    end: {
                        TD_ACCOUNT: [
                            (GBP_DEFAULT_DIMENSIONS, "10008.5"),
                            (GBP_CAPITALISED_INTEREST, "8.5"),
                            (GBP_ACCRUED_INTEREST_PAYABLE, "0"),
                        ]
                    },
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)
