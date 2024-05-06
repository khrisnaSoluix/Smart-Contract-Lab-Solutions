# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

# library
import library.current_account.contracts.template.current_account as current_account
import library.current_account.test.dimensions as ca_dimensions
import library.current_account.test.parameters as ca_test_parameters
import library.current_account.test.simulation.accounts as ca_accounts
import library.mortgage.contracts.template.mortgage as mortgage_account
import library.mortgage.test.accounts as mortgage_accounts
import library.mortgage.test.dimensions as mortgage_dimensions
import library.mortgage.test.parameters as mortgage_test_parameters
import library.mortgage.test.simulation.accounts as mortgage_sim_accounts
import library.offset_mortgage.test.files as contract_files
import library.savings_account.contracts.template.savings_account as savings_account
import library.savings_account.test.dimensions as sa_dimensions
import library.savings_account.test.parameters as sa_test_parameters
import library.savings_account.test.simulation.accounts as sa_accounts
from library.offset_mortgage.supervisors.template import offset_mortgage

# inception sdk
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ContractNotificationResourceType,
    ExpectedContractNotification,
    ExpectedSchedule,
    SimulationTestScenario,
    SubTest,
    SupervisorConfig,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_inbound_hard_settlement_instruction,
    create_outbound_hard_settlement_instruction,
)
from inception_sdk.test_framework.contracts.simulation.utils import SimulationTestCase

MORTGAGE_ACCOUNT_BASE = "MORTGAGE_ACCOUNT "
MORTGAGE_ACCOUNT_0 = f"{MORTGAGE_ACCOUNT_BASE}0"
CURRENT_ACCOUNT_BASE = "CURRENT_ACCOUNT "
CURRENT_ACCOUNT_0 = f"{CURRENT_ACCOUNT_BASE}0"
CURRENT_ACCOUNT_1 = f"{CURRENT_ACCOUNT_BASE}1"
SAVINGS_ACCOUNT_BASE = "SAVINGS_ACCOUNT "
SAVINGS_ACCOUNT_0 = f"{SAVINGS_ACCOUNT_BASE}0"
SAVINGS_ACCOUNT_1 = f"{SAVINGS_ACCOUNT_BASE}1"
SAVINGS_ACCOUNT_2 = f"{SAVINGS_ACCOUNT_BASE}2"

DEFAULT_PLAN_ID = "1"


LIABILITY = "LIABILITY"
DEFAULT_INTERNAL_ACCOUNT = "1"
default_internal_accounts = {
    DEFAULT_INTERNAL_ACCOUNT: LIABILITY,
    **mortgage_sim_accounts.default_internal_accounts,
    **ca_accounts.default_internal_accounts,
    **sa_accounts.default_internal_accounts,
}


class OffsetMortgageSupervisorTest(SimulationTestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_filepaths = [
            contract_files.OFFSET_MORTGAGE_SUPERVISOR_CONTRACT,
            contract_files.MORTGAGE_CONTRACT,
            contract_files.CURRENT_ACCOUNT_CONTRACT,
            contract_files.SAVINGS_ACCOUNT_CONTRACT,
        ]
        cls.DEFAULT_SUPERVISEE_VERSION_IDS = {
            "mortgage": "1000",
            "savings_account": "1001",
            "current_account": "1002",
        }

        super().setUpClass()

    def _get_default_supervisor_config(
        self,
        mortgage_instance_params=mortgage_test_parameters.mortgage_instance_params,
        mortgage_template_params=mortgage_test_parameters.mortgage_template_params,
        current_account_instance_params=ca_test_parameters.default_instance,
        current_account_template_params=ca_test_parameters.default_template,
        savings_account_instance_params=sa_test_parameters.default_instance,
        savings_account_template_params=sa_test_parameters.default_template,
        mortgage_instances=1,
        current_account_instances=1,
        savings_account_instances=1,
    ):
        mortgage_supervisee = ContractConfig(
            template_params=mortgage_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=mortgage_instance_params,
                    account_id_base=MORTGAGE_ACCOUNT_BASE,
                    number_of_accounts=mortgage_instances,
                )
            ],
            contract_content=self.smart_contract_path_to_content[contract_files.MORTGAGE_CONTRACT],
            clu_resource_id="mortgage",
            smart_contract_version_id=self.DEFAULT_SUPERVISEE_VERSION_IDS["mortgage"],
        )
        ca_supervisee = ContractConfig(
            template_params=current_account_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=current_account_instance_params,
                    account_id_base=CURRENT_ACCOUNT_BASE,
                    number_of_accounts=current_account_instances,
                )
            ],
            contract_content=self.smart_contract_path_to_content[
                contract_files.CURRENT_ACCOUNT_CONTRACT
            ],
            clu_resource_id="current_account",
            smart_contract_version_id=self.DEFAULT_SUPERVISEE_VERSION_IDS["current_account"],
        )

        sa_supervisee = ContractConfig(
            template_params=savings_account_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=savings_account_instance_params,
                    account_id_base=SAVINGS_ACCOUNT_BASE,
                    number_of_accounts=savings_account_instances,
                )
            ],
            contract_content=self.smart_contract_path_to_content[
                contract_files.SAVINGS_ACCOUNT_CONTRACT
            ],
            clu_resource_id="savings_account",
            smart_contract_version_id=self.DEFAULT_SUPERVISEE_VERSION_IDS["savings_account"],
        )

        supervisor_config = SupervisorConfig(
            supervisor_contract=self.smart_contract_path_to_content[
                contract_files.OFFSET_MORTGAGE_SUPERVISOR_CONTRACT
            ],
            supervisee_contracts=[
                mortgage_supervisee,
                ca_supervisee,
                sa_supervisee,
            ],
            supervisor_contract_version_id="supervisor version 1",
            plan_id=DEFAULT_PLAN_ID,
        )

        return supervisor_config

    def test_accrue_offset_schedule_created_on_activation(self):
        start = datetime(year=2021, month=1, day=1, hour=1, minute=30, tzinfo=ZoneInfo("UTC"))
        first_accrual_event = datetime(
            year=2021, month=1, day=2, hour=0, minute=0, second=1, tzinfo=ZoneInfo("UTC")
        )
        end = datetime(year=2021, month=1, day=2, hour=2, minute=30, tzinfo=ZoneInfo("UTC"))
        sub_tests = [
            SubTest(
                description="first accrual event is set correctly",
                expected_schedules=[
                    ExpectedSchedule(
                        event_id=offset_mortgage.ACCRUE_OFFSET_INTEREST_EVENT,
                        run_times=[first_accrual_event],
                        plan_id=DEFAULT_PLAN_ID,
                        count=1,
                    )
                ],
            )
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_only_mortgage_associated_returns_mortgage_non_offset_accrual_postings(self):
        start = datetime(year=2021, month=1, day=1, hour=1, minute=30, tzinfo=ZoneInfo("UTC"))
        first_accrual_event = datetime(
            year=2021, month=1, day=2, hour=0, minute=0, second=1, tzinfo=ZoneInfo("UTC")
        )
        end = datetime(year=2021, month=1, day=2, hour=2, minute=30, tzinfo=ZoneInfo("UTC"))
        sub_tests = [
            SubTest(
                description="mortgage disburses successfully",
                expected_balances_at_ts={
                    start: {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.DEFAULT, Decimal("0")),
                            (mortgage_dimensions.PRINCIPAL, Decimal("300000")),
                            (mortgage_dimensions.EMI, Decimal("25135.62")),
                        ]
                    }
                },
            ),
            SubTest(
                description="mortgage accrues without offset since no CA/SA accounts associated",
                expected_schedules=[
                    ExpectedSchedule(
                        event_id=offset_mortgage.ACCRUE_OFFSET_INTEREST_EVENT,
                        run_times=[first_accrual_event],
                        plan_id=DEFAULT_PLAN_ID,
                        count=1,
                    )
                ],
                expected_balances_at_ts={
                    first_accrual_event: {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.DEFAULT, Decimal("0")),
                            (mortgage_dimensions.PRINCIPAL, Decimal("300000")),
                            (mortgage_dimensions.EMI, Decimal("25135.62")),
                            # Daily interest accrued at 0.00274% on balance of 300000.00
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("8.21919")),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("8.21919")),
                        ]
                    }
                },
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                current_account_instances=0,
                savings_account_instances=0,
            ),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_only_ca_associated_returns_ca_non_offset_accrual_postings(self):
        start = datetime(year=2021, month=1, day=1, hour=1, minute=30, tzinfo=ZoneInfo("UTC"))
        first_accrual_event = datetime(
            year=2021, month=1, day=2, hour=0, minute=0, second=1, tzinfo=ZoneInfo("UTC")
        )
        end = datetime(year=2021, month=1, day=2, hour=2, minute=30, tzinfo=ZoneInfo("UTC"))
        sub_tests = [
            SubTest(
                description="deposit into CA",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=CURRENT_ACCOUNT_0,
                        internal_account_id=mortgage_accounts.DEPOSIT_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.DEFAULT, Decimal("5000")),
                        ],
                    }
                },
            ),
            SubTest(
                description="CA accrues since no mortgage accounts associated",
                expected_schedules=[
                    ExpectedSchedule(
                        event_id=offset_mortgage.ACCRUE_OFFSET_INTEREST_EVENT,
                        run_times=[first_accrual_event],
                        plan_id=DEFAULT_PLAN_ID,
                        count=1,
                    )
                ],
                expected_balances_at_ts={
                    first_accrual_event: {
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.DEFAULT, Decimal("5000")),
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.32877")),
                        ],
                    }
                },
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                mortgage_instances=0,
                savings_account_instances=0,
            ),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_mortgage_and_non_GBP_associated_preserves_mortgage_and_non_GBP_pids(self):
        start = datetime(year=2021, month=1, day=1, hour=1, minute=30, tzinfo=ZoneInfo("UTC"))
        first_accrual_event = datetime(
            year=2021, month=1, day=2, hour=0, minute=0, second=1, tzinfo=ZoneInfo("UTC")
        )
        end = datetime(year=2021, month=1, day=2, hour=2, minute=30, tzinfo=ZoneInfo("UTC"))
        sub_tests = [
            SubTest(
                description="mortgage disburses successfully and deposit into CA",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=CURRENT_ACCOUNT_0,
                        internal_account_id=mortgage_accounts.DEPOSIT_ACCOUNT,
                        denomination="USD",
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.DEFAULT, Decimal("0")),
                            (mortgage_dimensions.PRINCIPAL, Decimal("300000")),
                            (mortgage_dimensions.EMI, Decimal("25135.62")),
                        ]
                    },
                    start
                    + relativedelta(seconds=1): {
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.DEFAULT_USD, Decimal("5000")),
                        ],
                    },
                },
            ),
            SubTest(
                description="mortgage accrues without offset since "
                "only non-GBP CA account associated, and CA accrues since non-GBP",
                expected_schedules=[
                    ExpectedSchedule(
                        event_id=offset_mortgage.ACCRUE_OFFSET_INTEREST_EVENT,
                        run_times=[first_accrual_event],
                        plan_id=DEFAULT_PLAN_ID,
                        count=1,
                    )
                ],
                expected_balances_at_ts={
                    first_accrual_event: {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.DEFAULT, Decimal("0")),
                            (mortgage_dimensions.PRINCIPAL, Decimal("300000")),
                            (mortgage_dimensions.EMI, Decimal("25135.62")),
                            # Daily interest accrued at 0.00274% on balance of 300000.00
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("8.21919")),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("8.21919")),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.DEFAULT_USD, Decimal("5000")),
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE_USD, Decimal("0.32877")),
                        ],
                    }
                },
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                current_account_template_params={
                    **ca_test_parameters.default_template,
                    current_account.common_parameters.PARAM_DENOMINATION: "USD",
                },
                savings_account_instances=0,
            ),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_mortgage_and_negative_associated_preserves_mortgage_and_negative_pids(self):
        start = datetime(year=2021, month=1, day=1, hour=1, minute=30, tzinfo=ZoneInfo("UTC"))
        first_accrual_event = datetime(
            year=2021, month=1, day=2, hour=0, minute=0, second=1, tzinfo=ZoneInfo("UTC")
        )
        end = datetime(year=2021, month=1, day=2, hour=2, minute=30, tzinfo=ZoneInfo("UTC"))
        sub_tests = [
            SubTest(
                description="mortgage disburses successfully, force CA0 into negative balance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=CURRENT_ACCOUNT_0,
                        internal_account_id=mortgage_accounts.DEPOSIT_ACCOUNT,
                        denomination="GBP",
                        instruction_details={"force_override": "true"},
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.DEFAULT, Decimal("0")),
                            (mortgage_dimensions.PRINCIPAL, Decimal("300000")),
                            (mortgage_dimensions.EMI, Decimal("25135.62")),
                        ]
                    },
                    start
                    + relativedelta(seconds=1): {
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.DEFAULT, Decimal("-5000")),
                        ],
                    },
                },
            ),
            SubTest(
                description="mortgage accrues without offset since "
                "only CA account associated has negative balance, "
                "CA0 does not accrue since negative balance but incurs"
                "overdraft fee of £5",
                expected_schedules=[
                    ExpectedSchedule(
                        event_id=offset_mortgage.ACCRUE_OFFSET_INTEREST_EVENT,
                        run_times=[first_accrual_event],
                        plan_id=DEFAULT_PLAN_ID,
                        count=1,
                    )
                ],
                expected_balances_at_ts={
                    first_accrual_event: {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.DEFAULT, Decimal("0")),
                            (mortgage_dimensions.PRINCIPAL, Decimal("300000")),
                            (mortgage_dimensions.EMI, Decimal("25135.62")),
                            # Daily interest accrued at 0.00274% on balance of 300000.00
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("8.21919")),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("8.21919")),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.DEFAULT, Decimal("-5000")),
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            # negative since the internal accounts are credited
                            (ca_dimensions.UNARRANGED_OVERDRAFT_FEE, Decimal("-5")),
                            (ca_dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.67808")),
                        ],
                    }
                },
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                savings_account_instances=0,
            ),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_mortgage_has_no_pids_preserves_casa_pids(self):
        start = datetime(year=2021, month=1, day=1, hour=1, minute=30, tzinfo=ZoneInfo("UTC"))
        first_accrual_event = datetime(
            year=2021, month=1, day=2, hour=0, minute=0, second=1, tzinfo=ZoneInfo("UTC")
        )
        end = datetime(year=2021, month=1, day=2, hour=2, minute=30, tzinfo=ZoneInfo("UTC"))
        sub_tests = [
            SubTest(
                description="mortgage disburses successfully,deposit into CA",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=CURRENT_ACCOUNT_0,
                        internal_account_id=mortgage_accounts.DEPOSIT_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.DEFAULT, Decimal("0")),
                            (mortgage_dimensions.PRINCIPAL, Decimal("300000")),
                            # interest rate = 0 -> EMI = 300000 / 12
                            (mortgage_dimensions.EMI, Decimal("25000")),
                        ]
                    },
                    start
                    + relativedelta(seconds=1): {
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.DEFAULT, Decimal("5000")),
                        ],
                    },
                },
            ),
            SubTest(
                description="CA accrues since mortgage account doesn't have any"
                "interest accrual instructions (0% mortgage)",
                expected_schedules=[
                    ExpectedSchedule(
                        event_id=offset_mortgage.ACCRUE_OFFSET_INTEREST_EVENT,
                        run_times=[first_accrual_event],
                        plan_id=DEFAULT_PLAN_ID,
                        count=1,
                    )
                ],
                expected_balances_at_ts={
                    first_accrual_event: {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.DEFAULT, Decimal("0")),
                            (mortgage_dimensions.PRINCIPAL, Decimal("300000")),
                            (mortgage_dimensions.EMI, Decimal("25000")),
                            # Daily interest accrued at 0.00274% on balance of 300000.00
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.DEFAULT, Decimal("5000")),
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.32877")),
                        ],
                    }
                },
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                savings_account_instances=0,
                mortgage_instance_params={
                    **mortgage_test_parameters.mortgage_instance_params,
                    "fixed_interest_rate": "0.00",
                },
            ),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_daily_offset_accrual_with_one_savings_account(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))
        first_accrual_datetime = datetime(2021, 1, 2, 0, 0, 1, tzinfo=ZoneInfo("UTC"))
        end = first_accrual_datetime + relativedelta(minutes=1)

        sub_tests = [
            SubTest(
                description="deposit into savings",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + relativedelta(seconds=10),
                        target_account_id=SAVINGS_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.DEFAULT, Decimal("0")),
                            (mortgage_dimensions.PRINCIPAL, Decimal("300000")),
                            (mortgage_dimensions.EMI, Decimal("25135.62")),
                        ]
                    },
                    start
                    + relativedelta(seconds=11): {
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.DEFAULT, Decimal("10000")),
                        ],
                    },
                },
            ),
            SubTest(
                description="1st interest accrual day",
                expected_balances_at_ts={
                    first_accrual_datetime: {
                        MORTGAGE_ACCOUNT_0: [
                            # Daily offset interest accrued at 0.00274% on outstanding
                            # principal of 300000, offset with balance of 10000
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("7.94522")),
                            # Daily interest accrued at 0.00274% on balance of 300000.00
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("7.94522")),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (sa_dimensions.DEFAULT, "10000"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                savings_account_instances=1,
                current_account_instances=0,
            ),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_daily_offset_accrual_multiple_casa_accounts(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))
        first_accrual_datetime = datetime(2021, 1, 2, 0, 0, 1, tzinfo=ZoneInfo("UTC"))
        first_due_amount_calc_datetime = datetime(2021, 2, 28, 0, 1, 0, tzinfo=ZoneInfo("UTC"))
        first_accrual_after_first_due_amount_calc_datetime = datetime(
            2021, 3, 1, 0, 0, 1, tzinfo=ZoneInfo("UTC")
        )
        second_accrual_after_first_due_amount_calc_datetime = (
            first_accrual_after_first_due_amount_calc_datetime + relativedelta(days=1)
        )
        second_due_amount_calc_datetime = first_due_amount_calc_datetime + relativedelta(months=1)
        second_accrual_after_second_due_amount_calc_datetime = datetime(
            2021, 3, 30, 0, 0, 1, tzinfo=ZoneInfo("UTC")
        )
        third_due_amount_calc_datetime = second_due_amount_calc_datetime + relativedelta(months=1)
        end = datetime(year=2021, month=5, day=12, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="deposit into savings",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + relativedelta(seconds=10),
                        target_account_id=SAVINGS_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + relativedelta(seconds=10),
                        target_account_id=SAVINGS_ACCOUNT_1,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + relativedelta(seconds=10),
                        target_account_id=SAVINGS_ACCOUNT_2,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.DEFAULT, Decimal("0")),
                            (mortgage_dimensions.PRINCIPAL, Decimal("300000")),
                            (mortgage_dimensions.EMI, Decimal("25135.62")),
                        ]
                    },
                    start
                    + relativedelta(seconds=11): {
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.DEFAULT, Decimal("10000")),
                        ],
                        SAVINGS_ACCOUNT_1: [
                            (sa_dimensions.DEFAULT, Decimal("10000")),
                        ],
                        SAVINGS_ACCOUNT_2: [
                            (sa_dimensions.DEFAULT, Decimal("10000")),
                        ],
                    },
                },
            ),
            SubTest(
                description="1st interest accrual day",
                expected_balances_at_ts={
                    first_accrual_datetime: {
                        MORTGAGE_ACCOUNT_0: [
                            # (300000 - 30000) *  0.00274%
                            (
                                mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE,
                                Decimal("7.39727"),
                            ),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("7.39727")),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                            (mortgage_dimensions.EMI, Decimal("25135.62")),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (sa_dimensions.DEFAULT, "10000"),
                        ],
                        SAVINGS_ACCOUNT_1: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (sa_dimensions.DEFAULT, "10000"),
                        ],
                        SAVINGS_ACCOUNT_2: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (sa_dimensions.DEFAULT, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    first_due_amount_calc_datetime
                    - relativedelta(seconds=1): {
                        MORTGAGE_ACCOUNT_0: [
                            # 7.39727 * 58 days
                            (
                                mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE,
                                Decimal("429.04166"),
                            ),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("429.04166")),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                            (mortgage_dimensions.EMI, Decimal("25135.62")),
                        ],
                    },
                    first_due_amount_calc_datetime: {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                            (mortgage_dimensions.PRINCIPAL_DUE, Decimal("24906.31")),
                            (mortgage_dimensions.INTEREST_DUE, Decimal("429.04")),
                            (mortgage_dimensions.EMI, Decimal("25135.62")),
                            (mortgage_dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (sa_dimensions.DEFAULT, Decimal("10000")),
                        ],
                        SAVINGS_ACCOUNT_1: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (sa_dimensions.DEFAULT, Decimal("10000")),
                        ],
                        SAVINGS_ACCOUNT_2: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (sa_dimensions.DEFAULT, Decimal("10000")),
                        ],
                    },
                },
            ),
            SubTest(
                description="1st interest accrual day after repayment, pay mortgage due amounts",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="25335.35",
                        event_datetime=first_accrual_after_first_due_amount_calc_datetime
                        - relativedelta(hours=12),
                        target_account_id=MORTGAGE_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    first_accrual_after_first_due_amount_calc_datetime: {
                        MORTGAGE_ACCOUNT_0: [
                            # (275093.69 - 30000) *  0.00274%
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("6.71491")),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("6.71491")),
                            (mortgage_dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (mortgage_dimensions.INTEREST_DUE, Decimal("0")),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (sa_dimensions.DEFAULT, Decimal("10000")),
                        ],
                        SAVINGS_ACCOUNT_1: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (sa_dimensions.DEFAULT, Decimal("10000")),
                        ],
                        SAVINGS_ACCOUNT_2: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (sa_dimensions.DEFAULT, Decimal("10000")),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd interest accrual day after repayment (with 1 savings withdrawn)",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=second_accrual_after_first_due_amount_calc_datetime
                        - relativedelta(hours=12),
                        target_account_id=SAVINGS_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    second_accrual_after_first_due_amount_calc_datetime: {
                        MORTGAGE_ACCOUNT_0: [
                            # 6.71491 + 6.98888 where
                            # 6.98888 = (275093.69 - 20000) *  0.00274%
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("13.70379")),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("13.70379")),
                            (mortgage_dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (mortgage_dimensions.INTEREST_DUE, Decimal("0")),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (sa_dimensions.DEFAULT, Decimal("0")),
                        ],
                        SAVINGS_ACCOUNT_1: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (sa_dimensions.DEFAULT, Decimal("10000")),
                        ],
                        SAVINGS_ACCOUNT_2: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (sa_dimensions.DEFAULT, Decimal("10000")),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd mortgage transfer due day",
                expected_balances_at_ts={
                    second_due_amount_calc_datetime
                    - relativedelta(seconds=1): {
                        MORTGAGE_ACCOUNT_0: [
                            # 6.71491 + (6.98888* 27 days)
                            (
                                mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE,
                                Decimal("195.41467"),
                            ),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("195.41467")),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                            (mortgage_dimensions.EMI, Decimal("25135.62")),
                        ],
                    },
                    second_due_amount_calc_datetime: {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                            (mortgage_dimensions.PRINCIPAL_DUE, Decimal("24940.21")),
                            (mortgage_dimensions.INTEREST_DUE, Decimal("195.41")),
                            (mortgage_dimensions.EMI, Decimal("25135.62")),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (sa_dimensions.DEFAULT, Decimal("0")),
                        ],
                        SAVINGS_ACCOUNT_1: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (sa_dimensions.DEFAULT, Decimal("10000")),
                        ],
                        SAVINGS_ACCOUNT_2: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (sa_dimensions.DEFAULT, Decimal("10000")),
                        ],
                    },
                },
            ),
            SubTest(
                description="3rd interest accrual day after repayment (with all savings withdrawn),"
                " pay mortgage due amounts",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="25135.62",
                        event_datetime=second_due_amount_calc_datetime + relativedelta(hours=12),
                        target_account_id=MORTGAGE_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=second_accrual_after_second_due_amount_calc_datetime
                        - relativedelta(hours=12),
                        target_account_id=SAVINGS_ACCOUNT_1,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=second_accrual_after_second_due_amount_calc_datetime
                        - relativedelta(hours=12),
                        target_account_id=SAVINGS_ACCOUNT_2,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    second_accrual_after_second_due_amount_calc_datetime: {
                        MORTGAGE_ACCOUNT_0: [
                            # 6.30558 + 6.85353
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("13.15911")),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("13.15911")),
                            (mortgage_dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (mortgage_dimensions.INTEREST_DUE, Decimal("0")),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (sa_dimensions.DEFAULT, Decimal("0")),
                        ],
                        SAVINGS_ACCOUNT_1: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (sa_dimensions.DEFAULT, Decimal("0")),
                        ],
                        SAVINGS_ACCOUNT_2: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (sa_dimensions.DEFAULT, Decimal("0")),
                        ],
                    }
                },
            ),
            SubTest(
                description="3rd mortgage transfer due day",
                expected_balances_at_ts={
                    third_due_amount_calc_datetime
                    - relativedelta(seconds=1): {
                        MORTGAGE_ACCOUNT_0: [
                            # 6.30558 + (6.85353 * 30 days)
                            (
                                mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE,
                                Decimal("211.91148"),
                            ),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("211.91148")),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                            (mortgage_dimensions.EMI, Decimal("25135.62")),
                        ],
                    },
                    third_due_amount_calc_datetime: {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                            (mortgage_dimensions.PRINCIPAL_DUE, Decimal("24923.71")),
                            (mortgage_dimensions.INTEREST_DUE, Decimal("211.91")),
                            (mortgage_dimensions.EMI, Decimal("25135.62")),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (sa_dimensions.DEFAULT, Decimal("0")),
                        ],
                        SAVINGS_ACCOUNT_1: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (sa_dimensions.DEFAULT, Decimal("0")),
                        ],
                        SAVINGS_ACCOUNT_2: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (sa_dimensions.DEFAULT, Decimal("0")),
                        ],
                    },
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                current_account_instances=0,
                savings_account_instances=3,
                savings_account_template_params={
                    **sa_test_parameters.default_template,
                    savings_account.inactivity_fee.PARAM_INACTIVITY_FEE: "0",
                    savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
                },
            ),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_supervisee_notif_and_update_event(
        self,
    ):
        """
        Test that supervisee notif and update event directives are still sent even if they are under
        a supervisor
        """
        mortgage_instance_params = mortgage_test_parameters.mortgage_instance_params
        mortgage_instance_params["principal"] = "1000"
        mortgage_instance_params["due_amount_calculation_day"] = "1"
        mortgage_instance_params["fixed_interest_term"] = "0"

        start_datetime = datetime(year=2020, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        first_due_amount_calc_datetime = start_datetime + relativedelta(months=1, minutes=1)
        second_due_amount_calc_datetime = first_due_amount_calc_datetime + relativedelta(months=1)
        first_delinquency_event = second_due_amount_calc_datetime + relativedelta(
            days=1, hour=0, minute=0, seconds=2
        )
        second_delinquency_event = first_delinquency_event + relativedelta(months=1)
        # 2020-01-02T00:01:00Z
        first_interest_application_event = start_datetime + relativedelta(day=2, minutes=1)
        second_interest_application_event = first_interest_application_event + relativedelta(
            months=1
        )
        third_interest_application_event = second_interest_application_event + relativedelta(
            months=1
        )
        end_datetime = second_delinquency_event

        sub_tests = [
            SubTest(
                description="Check balances after account opening",
                expected_balances_at_ts={
                    start_datetime: {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.DEFAULT, Decimal("0")),
                            (mortgage_dimensions.PRINCIPAL, Decimal("1000")),
                            (mortgage_dimensions.EMI, Decimal("84.74")),
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance after first due event",
                expected_balances_at_ts={
                    first_due_amount_calc_datetime: {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.DEFAULT, Decimal("0")),
                            (mortgage_dimensions.PRINCIPAL, Decimal("917.9")),
                            (mortgage_dimensions.PRINCIPAL_DUE, Decimal("82.1")),
                            (mortgage_dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (mortgage_dimensions.PENALTIES, Decimal("0")),
                            (mortgage_dimensions.EMI, Decimal("84.74")),
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (mortgage_dimensions.INTEREST_DUE, "2.72"),
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance after second due event",
                expected_balances_at_ts={
                    second_due_amount_calc_datetime: {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.DEFAULT, Decimal("0")),
                            (mortgage_dimensions.PRINCIPAL, Decimal("835.42")),
                            (mortgage_dimensions.PRINCIPAL_DUE, Decimal("82.48")),
                            (mortgage_dimensions.PRINCIPAL_OVERDUE, Decimal("82.1")),
                            (mortgage_dimensions.PENALTIES, Decimal("15.00")),
                            (mortgage_dimensions.EMI, Decimal("84.74")),
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (mortgage_dimensions.INTEREST_DUE, "2.26"),
                        ],
                    }
                },
            ),
            SubTest(
                description="Check mark delinquent notification",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=first_delinquency_event,
                        notification_type=mortgage_account.MARK_DELINQUENT_NOTIFICATION,
                        notification_details={
                            "account_id": MORTGAGE_ACCOUNT_0,
                        },
                        resource_id=f"{MORTGAGE_ACCOUNT_0}",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Delinquency runs as expected",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            first_delinquency_event,
                            second_delinquency_event,
                        ],
                        event_id=mortgage_account.CHECK_DELINQUENCY,
                        account_id=MORTGAGE_ACCOUNT_0,
                        count=2,
                    )
                ],
            ),
            SubTest(
                description="Interest Application runs as expected",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            first_interest_application_event,
                            second_interest_application_event,
                            third_interest_application_event,
                        ],
                        event_id=savings_account.interest_application.APPLICATION_EVENT,
                        account_id=SAVINGS_ACCOUNT_0,
                        count=3,
                    )
                ],
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start_datetime,
            end=end_datetime,
            supervisor_config=self._get_default_supervisor_config(
                current_account_instances=0,
                savings_account_instances=1,
                mortgage_instance_params=mortgage_instance_params,
                savings_account_template_params={
                    **sa_test_parameters.default_template,
                    savings_account.inactivity_fee.PARAM_INACTIVITY_FEE: "0",
                    savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
                },
            ),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)
