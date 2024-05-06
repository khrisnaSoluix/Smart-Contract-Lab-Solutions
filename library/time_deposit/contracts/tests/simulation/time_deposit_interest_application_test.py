# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone
from typing import List, Dict

# common
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ContractModuleConfig,
    SimulationTestScenario,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_inbound_hard_settlement_instruction,
    create_account_instruction,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    ExpectedWorkflow,
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
            smart_contract_version_ids=["0", "1", "2"],
            templates_parameters=[
                template_parameters or default_template_params,
                {},
                {},
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
    def test_interest_application_correct_day_monthly_and_application_handling(self):
        """
        Test the date of the interest application for "monthly", as well as the GL
        account movement for accrual, and application of both positive
        (Feb +0.00024) and negative (Jan -0.00458) remainders. (The deposit
        amount of £51 is chosen as an example that does this)
        """
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        jan_1_end = datetime(2019, 1, 1, 23, 59, 59, tzinfo=timezone.utc)
        jan_30_end = datetime(2019, 1, 30, 23, 59, 59, tzinfo=timezone.utc)
        jan_31_accrual = datetime(2019, 1, 31, 23, 59, 0, tzinfo=timezone.utc)
        jan_31_end = datetime(2019, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
        feb_28_accrual = datetime(2019, 2, 28, 23, 59, 0, tzinfo=timezone.utc)
        feb_28_end = datetime(2019, 2, 28, 23, 59, 59, tzinfo=timezone.utc)
        end = datetime(2019, 5, 1, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["interest_application_frequency"] = "monthly"
        instance_params["interest_application_day"] = "31"

        events = [
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="51.00", event_datetime=start
            )
        ]

        sub_tests = [
            SubTest(
                description="transfer applied interest workflow",
                events=events,
                expected_balances_at_ts={
                    jan_1_end: {
                        TD_ACCOUNT: [
                            (GBP_ACCRUED_INTEREST_PAYABLE, "0.02082"),
                            (GBP_INTERNAL_CONTRA, "-0.02082"),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "0.02082")],
                        INTEREST_PAID_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "-0.02082")],
                    },
                    jan_30_end: {
                        TD_ACCOUNT: [
                            (GBP_ACCRUED_INTEREST_PAYABLE, "0.6246"),
                            (GBP_INTERNAL_CONTRA, "-0.6246"),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "0.6246")],
                        INTEREST_PAID_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "-0.6246")],
                    },
                    jan_31_accrual: {
                        TD_ACCOUNT: [
                            (GBP_ACCRUED_INTEREST_PAYABLE, "0.64542"),
                            (GBP_INTERNAL_CONTRA, "-0.64542"),
                        ],
                        INTEREST_PAID_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "-0.64542")],
                    },
                    jan_31_end: {
                        TD_ACCOUNT: [
                            (GBP_DEFAULT_DIMENSIONS, "51.65"),
                            (GBP_CAPITALISED_INTEREST, "0.65"),
                            (GBP_ACCRUED_INTEREST_PAYABLE, "0"),
                            (GBP_INTERNAL_CONTRA, "-0.65"),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "0")],
                        INTEREST_PAID_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "-0.65")],
                    },
                    feb_28_accrual: {
                        TD_ACCOUNT: [
                            (GBP_ACCRUED_INTEREST_PAYABLE, "0.59024"),
                            (GBP_CAPITALISED_INTEREST, "0.65"),
                            (GBP_INTERNAL_CONTRA, "-1.24024"),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "0.59024")],
                        INTEREST_PAID_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "-1.24024")],
                    },
                    feb_28_end: {
                        TD_ACCOUNT: [
                            (GBP_DEFAULT_DIMENSIONS, "52.24"),
                            (GBP_CAPITALISED_INTEREST, "1.24"),
                            (GBP_ACCRUED_INTEREST_PAYABLE, "0"),
                            (GBP_INTERNAL_CONTRA, "-1.24"),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "0")],
                        INTEREST_PAID_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "-1.24")],
                    },
                    end: {
                        TD_ACCOUNT: [
                            (GBP_CAPITALISED_INTEREST, "2.55"),
                            (GBP_DEFAULT_DIMENSIONS, "53.55"),
                        ]
                    },
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="TIME_DEPOSIT_APPLIED_INTEREST_TRANSFER",
                        account_id=TD_ACCOUNT,
                        count=4,
                        run_times=[
                            datetime(2019, 1, 31, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2019, 2, 28, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2019, 3, 31, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2020, 4, 30, 23, 59, 59, tzinfo=timezone.utc),
                        ],
                        contexts=[
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "0.65",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "0.59",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "0.66",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "0.65",
                            },
                        ],
                    )
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

    def test_interest_application_correct_day_quarterly(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2020, 3, 1, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["interest_application_day"] = "31"
        instance_params["interest_application_frequency"] = "quarterly"

        events = [
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="50.00", event_datetime=start
            )
        ]

        sub_tests = [
            SubTest(
                description="transfer applied interest workflow",
                events=events,
                expected_balances_at_ts={
                    end: {
                        TD_ACCOUNT: [
                            (GBP_CAPITALISED_INTEREST, "8.58"),
                            (GBP_DEFAULT_DIMENSIONS, "58.58"),
                        ]
                    },
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="TIME_DEPOSIT_APPLIED_INTEREST_TRANSFER",
                        account_id=TD_ACCOUNT,
                        count=4,
                        run_times=[
                            datetime(2019, 4, 30, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2019, 7, 31, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2019, 10, 31, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2020, 1, 31, 23, 59, 59, tzinfo=timezone.utc),
                        ],
                        contexts=[
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "2.45",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "1.97",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "2.04",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "2.12",
                            },
                        ],
                    )
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

    def test_interest_application_correct_day_quarterly_intended_day_before_start(
        self,
    ):
        start = datetime(2019, 1, 5, tzinfo=timezone.utc)
        end = datetime(2020, 3, 1, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["interest_application_day"] = "1"
        instance_params["interest_application_frequency"] = "quarterly"
        events = [
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="50.00", event_datetime=start
            )
        ]

        sub_tests = [
            SubTest(
                description="transfer applied interest workflow",
                events=events,
                expected_balances_at_ts={
                    end: {
                        TD_ACCOUNT: [
                            (GBP_CAPITALISED_INTEREST, "7.81"),
                            (GBP_DEFAULT_DIMENSIONS, "57.81"),
                        ]
                    },
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="TIME_DEPOSIT_APPLIED_INTEREST_TRANSFER",
                        account_id=TD_ACCOUNT,
                        count=4,
                        run_times=[
                            datetime(2019, 4, 1, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2019, 7, 1, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2019, 10, 1, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2020, 1, 1, 23, 59, 59, tzinfo=timezone.utc),
                        ],
                        contexts=[
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "1.78",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "1.92",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "2.02",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "2.09",
                            },
                        ],
                    )
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

    def test_interest_application_correct_day_semi_annually(self):
        """
        Test interest application is correct day for the semi annual option. This
        includes testing the add months and resetting the intended day back works
        as expected.
        """
        start = datetime(2019, 1, 5, tzinfo=timezone.utc)
        end = datetime(2020, 1, 6, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["interest_application_day"] = "1"
        instance_params["interest_application_frequency"] = "semi_annually"
        events = [
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="50.00", event_datetime=start
            )
        ]

        sub_tests = [
            SubTest(
                description="transfer applied interest workflow",
                events=events,
                expected_balances_at_ts={
                    end: {
                        TD_ACCOUNT: [
                            (GBP_CAPITALISED_INTEREST, "7.66"),
                            (GBP_DEFAULT_DIMENSIONS, "57.66"),
                        ]
                    },
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="TIME_DEPOSIT_APPLIED_INTEREST_TRANSFER",
                        account_id=TD_ACCOUNT,
                        count=2,
                        run_times=[
                            datetime(2019, 7, 1, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2020, 1, 1, 23, 59, 59, tzinfo=timezone.utc),
                        ],
                        contexts=[
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "3.63",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "4.03",
                            },
                        ],
                    )
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

    def test_interest_application_correct_day_annually(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2020, 1, 6, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["interest_application_day"] = "5"
        instance_params["interest_application_frequency"] = "annually"

        events = [
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="50.00", event_datetime=start
            )
        ]

        sub_tests = [
            SubTest(
                description="transfer applied interest workflow",
                events=events,
                expected_balances_at_ts={
                    end: {
                        TD_ACCOUNT: [
                            (GBP_CAPITALISED_INTEREST, "7.55"),
                            (GBP_DEFAULT_DIMENSIONS, "57.55"),
                        ]
                    },
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="TIME_DEPOSIT_APPLIED_INTEREST_TRANSFER",
                        account_id=TD_ACCOUNT,
                        count=1,
                        run_times=[datetime(2020, 1, 5, 23, 59, 59, tzinfo=timezone.utc)],
                        contexts=[
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "7.55",
                            }
                        ],
                    )
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

    def test_interest_application_correct_day_weekly(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 3, 1, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["interest_application_frequency"] = "weekly"

        events = [
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="50.00", event_datetime=start
            )
        ]

        sub_tests = [
            SubTest(
                description="transfer applied interest workflow",
                events=events,
                expected_balances_at_ts={
                    end: {
                        TD_ACCOUNT: [
                            (GBP_CAPITALISED_INTEREST, "1.16"),
                            (GBP_DEFAULT_DIMENSIONS, "51.16"),
                        ]
                    },
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="TIME_DEPOSIT_APPLIED_INTEREST_TRANSFER",
                        account_id=TD_ACCOUNT,
                        count=8,
                        run_times=[
                            datetime(2019, 1, 8, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2019, 1, 15, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2019, 1, 22, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2019, 1, 29, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2019, 2, 5, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2019, 2, 12, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2019, 2, 19, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2019, 2, 26, 23, 59, 59, tzinfo=timezone.utc),
                        ],
                        contexts=[
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "0.16",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "0.14",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "0.14",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "0.14",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "0.14",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "0.14",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "0.15",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "0.15",
                            },
                        ],
                    )
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

    def test_interest_application_correct_day_fortnightly(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 4, 1, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["interest_application_frequency"] = "fortnightly"

        events = [
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="50.00", event_datetime=start
            )
        ]

        sub_tests = [
            SubTest(
                description="transfer applied interest workflow",
                events=events,
                expected_balances_at_ts={
                    end: {
                        TD_ACCOUNT: [
                            (GBP_CAPITALISED_INTEREST, "1.76"),
                            (GBP_DEFAULT_DIMENSIONS, "51.76"),
                        ]
                    },
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="TIME_DEPOSIT_APPLIED_INTEREST_TRANSFER",
                        account_id=TD_ACCOUNT,
                        count=6,
                        run_times=[
                            datetime(2019, 1, 15, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2019, 1, 29, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2019, 2, 12, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2019, 2, 26, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2019, 3, 12, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2019, 3, 26, 23, 59, 59, tzinfo=timezone.utc),
                        ],
                        contexts=[
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "0.31",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "0.29",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "0.29",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "0.29",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "0.29",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "0.29",
                            },
                        ],
                    )
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

    def test_interest_application_correct_day_four_weekly(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 4, 1, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["interest_application_frequency"] = "four_weekly"

        events = [
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="50.00", event_datetime=start
            )
        ]

        sub_tests = [
            SubTest(
                description="transfer applied interest workflow",
                events=events,
                expected_balances_at_ts={
                    end: {
                        TD_ACCOUNT: [
                            (GBP_CAPITALISED_INTEREST, "1.75"),
                            (GBP_DEFAULT_DIMENSIONS, "51.75"),
                        ]
                    },
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="TIME_DEPOSIT_APPLIED_INTEREST_TRANSFER",
                        account_id=TD_ACCOUNT,
                        count=3,
                        run_times=[
                            datetime(2019, 1, 29, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2019, 2, 26, 23, 59, 59, tzinfo=timezone.utc),
                            datetime(2019, 3, 26, 23, 59, 59, tzinfo=timezone.utc),
                        ],
                        contexts=[
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "0.59",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "0.58",
                            },
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "0.58",
                            },
                        ],
                    )
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

    def test_interest_application_correct_day_maturity(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(2019, 8, 2, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["interest_application_frequency"] = "maturity"
        instance_params["term"] = "7"
        instance_params["interest_application_day"] = "7"

        events = [
            create_inbound_hard_settlement_instruction(
                target_account_id=TD_ACCOUNT, amount="50", event_datetime=start
            )
        ]

        sub_tests = [
            SubTest(
                description="transfer applied interest workflow",
                events=events,
                expected_balances_at_ts={
                    end: {
                        TD_ACCOUNT: [
                            (GBP_DEFAULT_DIMENSIONS, "54.33"),
                            (GBP_CAPITALISED_INTEREST, "4.33"),
                        ]
                    },
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="TIME_DEPOSIT_MATURITY",
                        account_id=TD_ACCOUNT,
                        count=1,
                        run_times=[datetime(2019, 8, 1, 23, 59, 59, tzinfo=timezone.utc)],
                        contexts=[
                            {
                                "account_id": TD_ACCOUNT,
                                "applied_interest_amount": "4.33",
                            }
                        ],
                    )
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
