# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timedelta
from json import dumps
from zoneinfo import ZoneInfo

# library
import library.current_account.test.dimensions as ca_dimensions
import library.current_account.test.parameters as ca_parameters
import library.current_account.test.simulation.accounts as ca_accounts
import library.mortgage.contracts.template.mortgage as mortgage
import library.mortgage.test.simulation.accounts as mortgage_sim_accounts
import library.offset_mortgage.test.files as contract_files
import library.savings_account.test.dimensions as sa_dimensions
import library.savings_account.test.parameters as sa_parameters
import library.savings_account.test.simulation.accounts as sa_accounts
from library.current_account.contracts.template import current_account
from library.mortgage.test import (
    accounts as mortgage_accounts,
    dimensions as mortgage_dimensions,
    parameters as mortgage_test_parameters,
)
from library.savings_account.contracts.template import savings_account

# inception sdk
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    SimulationTestScenario,
    SubTest,
    SupervisorConfig,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_inbound_hard_settlement_instruction,
    create_outbound_authorisation_instruction,
    create_outbound_hard_settlement_instruction,
    create_template_parameter_change_event,
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
DEFAULT_DENOMINATION = "GBP"

DEFAULT_SUPERVISEE_VERSION_IDS = {
    "mortgage": "1000",
    "say_access_saver": "1001",
    "current_account": "1002",
}

LIABILITY = "LIABILITY"
DEFAULT_INTERNAL_ACCOUNT = "1"
default_internal_accounts = {
    DEFAULT_INTERNAL_ACCOUNT: LIABILITY,
    **mortgage_sim_accounts.default_internal_accounts,
    **ca_accounts.default_internal_accounts,
    **sa_accounts.default_internal_accounts,
}

DEFAULT_DIMENSION = ca_dimensions.DEFAULT
OVERDRAFT_ACCRUED_INTEREST_DIMENSION = ca_dimensions.OVERDRAFT_ACCRUED_INTEREST

default_simulation_start_date = datetime(year=2021, month=1, day=1, tzinfo=ZoneInfo("UTC"))

default_mortgage_instance_params: dict[str, str] = {
    mortgage.PARAM_INTEREST_ONLY_TERM: "0",
    mortgage.disbursement.PARAM_DEPOSIT_ACCOUNT: mortgage_accounts.DEPOSIT_ACCOUNT,
    mortgage.disbursement.PARAM_PRINCIPAL: "300000",
    mortgage.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "12",
    mortgage.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.129971",
    mortgage.fixed_to_variable.PARAM_FIXED_INTEREST_TERM: "0",
    mortgage.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "120",
    mortgage.variable_rate.PARAM_VARIABLE_RATE_ADJUSTMENT: "0",
}

default_sa_instance_params = {**sa_parameters.default_instance}

default_sa_template_params = {
    **sa_parameters.default_template,
    savings_account.inactivity_fee.PARAM_INACTIVITY_FEE: "0",
    savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
}

default_ca_template_params = {
    **ca_parameters.default_template,
    # unlimited buffer to simplify tests
    current_account.overdraft_interest.PARAM_OVERDRAFT_INTEREST_FREE_BUFFER_DAYS: None,
    # disable fees to simplify tests
    current_account.excess_fee.PARAM_EXCESS_FEE: "0",
}

default_ca_instance_params = {
    **ca_parameters.default_instance,
    current_account.interest_application.PARAM_INTEREST_APPLICATION_DAY: "2",
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
        mortgage_instance_params=default_mortgage_instance_params,
        mortgage_template_params=mortgage_test_parameters.mortgage_template_params,
        mortgage_instances=1,
        sa_instance_params=default_sa_instance_params,
        sa_template_params=default_sa_template_params,
        sa_instances=1,
        ca_instance_params=default_ca_instance_params,
        ca_template_params=default_ca_template_params,
        ca_instances=1,
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
            template_params=ca_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=ca_instance_params,
                    account_id_base=CURRENT_ACCOUNT_BASE,
                    number_of_accounts=ca_instances,
                )
            ],
            contract_content=self.smart_contract_path_to_content[
                contract_files.CURRENT_ACCOUNT_CONTRACT
            ],
            clu_resource_id="current_account",
            smart_contract_version_id=self.DEFAULT_SUPERVISEE_VERSION_IDS["current_account"],
        )

        sa_supervisee = ContractConfig(
            template_params=sa_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=sa_instance_params,
                    account_id_base=SAVINGS_ACCOUNT_BASE,
                    number_of_accounts=sa_instances,
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

    def test_daily_offset_accrual_multiple_sa(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2021, month=5, day=12, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="deposit into savings",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=SAVINGS_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=SAVINGS_ACCOUNT_1,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=SAVINGS_ACCOUNT_2,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="1st interest accrual day",
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "23.67122"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "23.67122"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        SAVINGS_ACCOUNT_1: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        SAVINGS_ACCOUNT_2: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 2, 12, 0, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "2190.79"),
                            (mortgage_dimensions.INTEREST_DUE, "994.19"),
                            (mortgage_dimensions.EMI, "2924.6"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        SAVINGS_ACCOUNT_1: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        SAVINGS_ACCOUNT_2: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st interest accrual day after repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3184.98",
                        event_datetime=datetime(2021, 2, 12, 12, 30, 0, tzinfo=ZoneInfo("UTC")),
                        target_account_id=MORTGAGE_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    datetime(2021, 2, 13, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "23.47915"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "23.47915"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        SAVINGS_ACCOUNT_1: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        SAVINGS_ACCOUNT_2: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd interest accrual day after repayment (with 1 savings withdrawn)",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 2, 13, 12, 30, 0, tzinfo=ZoneInfo("UTC")),
                        target_account_id=SAVINGS_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    datetime(2021, 2, 14, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "47.83502"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "47.83502"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        SAVINGS_ACCOUNT_1: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        SAVINGS_ACCOUNT_2: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 3, 12, 0, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "2243.51"),
                            (mortgage_dimensions.INTEREST_DUE, "681.09"),
                            (mortgage_dimensions.EMI, "2924.6"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        SAVINGS_ACCOUNT_1: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        SAVINGS_ACCOUNT_2: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="3rd interest accrual day after repayment (with all savings withdrawn)",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2924.6",
                        event_datetime=datetime(2021, 3, 12, 12, 30, 0, tzinfo=ZoneInfo("UTC")),
                        target_account_id=MORTGAGE_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 3, 13, 12, 30, 0, tzinfo=ZoneInfo("UTC")),
                        target_account_id=SAVINGS_ACCOUNT_1,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 3, 13, 12, 30, 0, tzinfo=ZoneInfo("UTC")),
                        target_account_id=SAVINGS_ACCOUNT_2,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2021, 3, 14, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "50.07178"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "50.07178"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        SAVINGS_ACCOUNT_1: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        SAVINGS_ACCOUNT_2: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
            SubTest(
                description="3rd mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 4, 12, 0, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "2123.06"),
                            (mortgage_dimensions.INTEREST_DUE, "801.54"),
                            (mortgage_dimensions.EMI, "2924.60"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        SAVINGS_ACCOUNT_1: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        SAVINGS_ACCOUNT_2: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(sa_instances=3),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_daily_accrual_multiple_offset_accounts(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2021, month=4, day=12, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="deposit into savings and current account, withdraw from one ca",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=SAVINGS_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=SAVINGS_ACCOUNT_1,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=CURRENT_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="80",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=CURRENT_ACCOUNT_1,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="1st interest accrual day",
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "23.67122"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "23.67122"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        SAVINGS_ACCOUNT_1: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        CURRENT_ACCOUNT_1: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            # round(80 - 50 buffer * 0.05 / 365)
                            (OVERDRAFT_ACCRUED_INTEREST_DIMENSION, "-0.00411"),
                            (DEFAULT_DIMENSION, "-80"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 2, 12, 0, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "2190.79"),
                            (mortgage_dimensions.INTEREST_DUE, "994.19"),
                            (mortgage_dimensions.EMI, "2924.6"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        SAVINGS_ACCOUNT_1: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        CURRENT_ACCOUNT_1: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            # 10 * round(80.13 - 50 buffer * 0.1485 / 365)
                            (OVERDRAFT_ACCRUED_INTEREST_DIMENSION, "-0.0413"),
                            # overdraft interest applied on 2021/01/02 and 2021/02/02
                            (DEFAULT_DIMENSION, "-80.13"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st interest accrual day after repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3184.98",
                        event_datetime=datetime(2021, 2, 12, 12, 30, 0, tzinfo=ZoneInfo("UTC")),
                        target_account_id=MORTGAGE_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    datetime(2021, 2, 13, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "23.47915"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "23.47915"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        SAVINGS_ACCOUNT_1: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        CURRENT_ACCOUNT_1: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            # 11 * round(80.13 - 50 buffer * 0.05 / 365)
                            (OVERDRAFT_ACCRUED_INTEREST_DIMENSION, "-0.04543"),
                            (DEFAULT_DIMENSION, "-80.13"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd interest accrual day after repayment (with 1 savings withdrawn)",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 2, 13, 12, 30, 0, tzinfo=ZoneInfo("UTC")),
                        target_account_id=SAVINGS_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    datetime(2021, 2, 14, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "47.83502"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "47.83502"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        SAVINGS_ACCOUNT_1: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        CURRENT_ACCOUNT_1: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            # 12 * round(80.13 - 50 buffer * 0.1485 / 365)
                            (OVERDRAFT_ACCRUED_INTEREST_DIMENSION, "-0.04956"),
                            (DEFAULT_DIMENSION, "-80.13"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 3, 12, 0, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "2243.51"),
                            (mortgage_dimensions.INTEREST_DUE, "681.09"),
                            (mortgage_dimensions.EMI, "2924.6"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        SAVINGS_ACCOUNT_1: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        CURRENT_ACCOUNT_1: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            # 10 * round(80.25 - 50 buffer * 0.05 / 365)
                            (OVERDRAFT_ACCRUED_INTEREST_DIMENSION, "-0.0414"),
                            # overdraft interest applied on 2021/03/02
                            (DEFAULT_DIMENSION, "-80.25"),
                        ],
                    }
                },
            ),
            SubTest(
                description="3rd interest accrual day after repayment (with all savings withdrawn)",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2924.6",
                        event_datetime=datetime(2021, 3, 12, 12, 30, 0, tzinfo=ZoneInfo("UTC")),
                        target_account_id=MORTGAGE_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 3, 13, 12, 30, 0, tzinfo=ZoneInfo("UTC")),
                        target_account_id=SAVINGS_ACCOUNT_1,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 3, 13, 12, 30, 0, tzinfo=ZoneInfo("UTC")),
                        target_account_id=CURRENT_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2021, 3, 14, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "50.07178"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "50.07178"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        SAVINGS_ACCOUNT_1: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        CURRENT_ACCOUNT_1: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            # 25 * round(80.74 - 50 buffer * 0.05 / 365)
                            (OVERDRAFT_ACCRUED_INTEREST_DIMENSION, "-0.04968"),
                            (DEFAULT_DIMENSION, "-80.25"),
                        ],
                    }
                },
            ),
            SubTest(
                description="3rd mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 4, 12, 0, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "2123.06"),
                            (mortgage_dimensions.INTEREST_DUE, "801.54"),
                            (mortgage_dimensions.EMI, "2924.6"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        SAVINGS_ACCOUNT_1: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        CURRENT_ACCOUNT_1: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            # 10 * round(80.38 - 50 buffer * 0.05 / 365)
                            (OVERDRAFT_ACCRUED_INTEREST_DIMENSION, "-0.0416"),
                            # overdraft interest applied on 2021/04/02
                            (DEFAULT_DIMENSION, "-80.38"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(sa_instances=2, ca_instances=2),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_daily_offset_accrual(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2021, month=3, day=12, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="deposit into savings",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=SAVINGS_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day includes discounted interest",
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "25.42465"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "25.42465"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 2, 12, 0, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "2136.43"),
                            (mortgage_dimensions.INTEREST_DUE, "1067.84"),
                            (mortgage_dimensions.EMI, "2924.6"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="pay 1st mortgage due amount",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3204.27",
                        event_datetime=datetime(2021, 2, 12, 12, 30, 0, tzinfo=ZoneInfo("UTC")),
                        target_account_id=MORTGAGE_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day after repayment",
                expected_balances_at_ts={
                    datetime(2021, 2, 13, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "25.23734"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "25.23734"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="withdraw from savings",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 2, 13, 12, 30, 0, tzinfo=ZoneInfo("UTC")),
                        target_account_id=SAVINGS_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="2nd interest accrual day after repayment (with savings withdrawn)",
                expected_balances_at_ts={
                    datetime(2021, 2, 14, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "51.3514"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "51.3514"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 3, 12, 0, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "2194.28"),
                            (mortgage_dimensions.INTEREST_DUE, "730.32"),
                            (mortgage_dimensions.EMI, "2924.6"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(sa_instances=3),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_daily_offset_accrual_with_overpayment(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2021, month=3, day=12, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="deposit into savings",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=SAVINGS_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day includes discounted interest",
                # interest = 3.2% (25.42 per day)
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "25.42465"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "25.42465"),
                            (mortgage_dimensions.PRINCIPAL, "300000"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 2, 12, 0, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (mortgage_dimensions.PRINCIPAL, "297863.57"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "2136.43"),
                            (mortgage_dimensions.INTEREST_DUE, "1067.84"),
                            (mortgage_dimensions.EMI, "2924.6"),
                            (mortgage_dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="pay 1st mortgage due amount with overpayment",
                # (overpayment 10000 + 3204.27 due)
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="13204.27",
                        event_datetime=datetime(2021, 2, 12, 12, 30, 0, tzinfo=ZoneInfo("UTC")),
                        target_account_id=MORTGAGE_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day after repayment",
                expected_balances_at_ts={
                    datetime(2021, 2, 13, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            # accrues on principal - offset
                            # = 287863.57 - 10000 = 277863.57
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "24.36063"),
                            # accrues on principal - offset + overpayment
                            # = 287863.57 - 10000 + 10000 = 287863.57
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "25.23734"),
                            (mortgage_dimensions.PRINCIPAL, "287863.57"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                            (mortgage_dimensions.OVERPAYMENT, "10000"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="withdraw from savings",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 2, 13, 12, 30, 0, tzinfo=ZoneInfo("UTC")),
                        target_account_id=SAVINGS_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="2nd interest accrual day after repayment (with savings withdrawn)",
                expected_balances_at_ts={
                    datetime(2021, 2, 14, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "49.59797"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "51.3514"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 3, 12, 0, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "2218.83"),
                            (mortgage_dimensions.INTEREST_DUE, "705.77"),
                            (mortgage_dimensions.EMI, "2924.6"),
                            # rounded expected interest 730.32 - 705.77
                            (mortgage_dimensions.EMI_PRINCIPAL_EXCESS, "24.55"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_daily_offset_accrual_with_rate_change(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2021, month=3, day=12, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="deposit into savings",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=SAVINGS_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day includes discounted interest",
                # interest = 3.2% (25.42 per day)
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "25.42465"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "25.42465"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="rate change ready for next interest accrual period",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(days=2),
                        smart_contract_version_id=DEFAULT_SUPERVISEE_VERSION_IDS["mortgage"],
                        **{mortgage.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0.02"},
                    )
                ],
            ),
            SubTest(
                description="2nd interest accrual day includes discounted interest",
                # interest = 3.2% (25.42 per day)
                expected_balances_at_ts={
                    datetime(2021, 1, 3, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "50.8493"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "50.8493"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="3rd interest accrual day includes discounted interest + "
                + "variable rate change",
                # interest = 2% (15.89 per day)
                expected_balances_at_ts={
                    datetime(2021, 1, 4, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "66.73971"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "66.73971"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 2, 12, 0, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "2267.79"),
                            (mortgage_dimensions.INTEREST_DUE, "686.47"),
                            (mortgage_dimensions.EMI, "2760.4"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="pay 1st mortgage due amount",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2954.26",
                        event_datetime=datetime(2021, 2, 12, 12, 30, 0, tzinfo=ZoneInfo("UTC")),
                        target_account_id=MORTGAGE_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day after repayment",
                expected_balances_at_ts={
                    datetime(2021, 2, 13, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "15.76614"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "15.76614"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="withdraw from savings",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 2, 13, 12, 30, 0, tzinfo=ZoneInfo("UTC")),
                        target_account_id=SAVINGS_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="2nd interest accrual day after repayment (with savings withdrawn)",
                expected_balances_at_ts={
                    datetime(2021, 2, 14, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "32.08023"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "32.08023"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 3, 12, 0, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "2304.15"),
                            (mortgage_dimensions.INTEREST_DUE, "456.25"),
                            (mortgage_dimensions.EMI, "2760.4"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_daily_offset_accrual_with_sa_pending_out(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2021, month=2, day=12, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="deposit into savings",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=SAVINGS_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day includes discounted interest",
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "25.42465"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "25.42465"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd interest accrual day includes discounted interest",
                expected_balances_at_ts={
                    datetime(2021, 1, 3, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "50.8493"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "50.8493"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="create pending withdrawal",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(days=2),
                        target_account_id=SAVINGS_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="3rd interest accrual day includes discounted interest + "
                + "pending EAS withdrawal",
                expected_balances_at_ts={
                    datetime(2021, 1, 4, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "76.27395"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "76.27395"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                            (sa_dimensions.PENDING_OUT, "-10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 2, 12, 0, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "2136.43"),
                            (mortgage_dimensions.INTEREST_DUE, "1067.84"),
                            (mortgage_dimensions.EMI, "2924.6"),
                        ],
                        SAVINGS_ACCOUNT_0: [
                            (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_sa_supervisee_only_commits_interest_accruals_no_offset(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))
        end = start + timedelta(minutes=5)
        sub_tests = [
            SubTest(
                description="deposit into savings account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        event_datetime=start + timedelta(seconds=10),
                        amount="1000",
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=SAVINGS_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                mortgage_instances=0,
                ca_instances=0,
                sa_instances=1,
            ),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_daily_ca_offset_accrual(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2021, month=3, day=12, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="deposit into current account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=CURRENT_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day includes discounted interest",
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "25.42465"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "25.42465"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 2, 12, 0, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "2136.43"),
                            (mortgage_dimensions.INTEREST_DUE, "1067.84"),
                            (mortgage_dimensions.EMI, "2924.6"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="pay 1st mortgage due amount",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3204.27",
                        event_datetime=datetime(2021, 2, 12, 12, 30, 0, tzinfo=ZoneInfo("UTC")),
                        target_account_id=MORTGAGE_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day after repayment",
                expected_balances_at_ts={
                    datetime(2021, 2, 13, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "25.23734"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "25.23734"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="withdraw from current account",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 2, 13, 12, 30, 0, tzinfo=ZoneInfo("UTC")),
                        target_account_id=CURRENT_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="2nd interest accrual day after repayment (with savings withdrawn)",
                expected_balances_at_ts={
                    datetime(2021, 2, 14, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "51.3514"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "51.3514"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 3, 12, 0, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "2194.28"),
                            (mortgage_dimensions.INTEREST_DUE, "730.32"),
                            (mortgage_dimensions.EMI, "2924.6"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_daily_ca_offset_accrual_with_overpayment_and_rate_change(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2021, month=3, day=12, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="deposit into current account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=CURRENT_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day includes discounted interest",
                # interest = 3.2% (25.42 per day)
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            # expected interest matches receivable interest until an overpayment
                            # is made
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "25.42465"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "25.42465"),
                            (mortgage_dimensions.PRINCIPAL, "300000"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 2, 12, 0, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (mortgage_dimensions.PRINCIPAL, "297863.57"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "2136.43"),
                            (mortgage_dimensions.INTEREST_DUE, "1067.84"),
                            (mortgage_dimensions.EMI, "2924.6"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="pay 1st mortgage due amount with overpayment",
                # (overpayment 10000 + 3204.27 due)
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="13204.27",
                        event_datetime=datetime(2021, 2, 12, 12, 30, 0, tzinfo=ZoneInfo("UTC")),
                        target_account_id=MORTGAGE_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day after repayment",
                expected_balances_at_ts={
                    datetime(2021, 2, 13, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            # accrues on principal - offset
                            # = 287863.57 - 10000 = 277863.57
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "24.36063"),
                            # accrues on principal - offset + overpayment
                            # = 287863.57 - 10000 + 10000 = 287863.57
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "25.23734"),
                            (mortgage_dimensions.PRINCIPAL, "287863.57"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                            (mortgage_dimensions.OVERPAYMENT, "10000"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="withdraw from current account",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 2, 13, 12, 30, 0, tzinfo=ZoneInfo("UTC")),
                        target_account_id=CURRENT_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="2nd interest accrual day after repayment (with amount withdrawn)",
                expected_balances_at_ts={
                    datetime(2021, 2, 14, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "49.59797"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "51.3514"),
                            (mortgage_dimensions.PRINCIPAL, "287863.57"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                            (mortgage_dimensions.OVERPAYMENT, "10000"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
            SubTest(
                description="Change interest rate to trigger reamortisation",
                events=[
                    create_template_parameter_change_event(
                        # change the rate after final accrual to avoid affecting accrual results
                        timestamp=datetime(2021, 3, 12, 0, 0, 2, tzinfo=ZoneInfo("UTC")),
                        smart_contract_version_id=DEFAULT_SUPERVISEE_VERSION_IDS["mortgage"],
                        **{mortgage.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0.02"},
                    )
                ],
            ),
            SubTest(
                description="2nd mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 3, 12, 0, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (mortgage_dimensions.PRINCIPAL, "285807.79"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "2055.78"),
                            (mortgage_dimensions.INTEREST_DUE, "705.77"),
                            # mortgage is reamortised excluding overpayment and principal excess
                            # due to reduce term preference
                            # principal 297863.57, remaining term 119 and yearly rate 0.02
                            (mortgage_dimensions.EMI, "2761.55"),
                            # rounded expected interest 730.32 - 705.77
                            (mortgage_dimensions.EMI_PRINCIPAL_EXCESS, "24.55"),
                            (mortgage_dimensions.OVERPAYMENT, "10000"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_daily_ca_offset_accrual_with_rate_change(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2021, month=3, day=12, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="deposit into current account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=CURRENT_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day includes discounted interest",
                # interest = 3.2% (25.42 per day)
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "25.42465"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "25.42465"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="rate change ready for next interest accrual period",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(days=2),
                        smart_contract_version_id=DEFAULT_SUPERVISEE_VERSION_IDS["mortgage"],
                        **{mortgage.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0.02"},
                    )
                ],
            ),
            SubTest(
                description="2nd interest accrual day includes discounted interest",
                # interest = 3.2% (25.42 per day)
                expected_balances_at_ts={
                    datetime(2021, 1, 3, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "50.8493"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "50.8493"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="3rd interest accrual day includes discounted interest + "
                + "variable rate change",
                # interest = 2% (15.89 per day)
                expected_balances_at_ts={
                    datetime(2021, 1, 4, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "66.73971"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "66.73971"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 2, 12, 0, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "2267.79"),
                            (mortgage_dimensions.INTEREST_DUE, "686.47"),
                            (mortgage_dimensions.EMI, "2760.4"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="pay 1st mortgage due amount",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2954.26",
                        event_datetime=datetime(2021, 2, 12, 12, 30, 0, tzinfo=ZoneInfo("UTC")),
                        target_account_id=MORTGAGE_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day after repayment",
                expected_balances_at_ts={
                    datetime(2021, 2, 13, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "15.76614"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "15.76614"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="withdraw from current account",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 2, 13, 12, 30, 0, tzinfo=ZoneInfo("UTC")),
                        target_account_id=CURRENT_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="2nd interest accrual day after repayment (with savings withdrawn)",
                expected_balances_at_ts={
                    datetime(2021, 2, 14, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "32.08023"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "32.08023"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 3, 12, 0, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "2304.15"),
                            (mortgage_dimensions.INTEREST_DUE, "456.25"),
                            (mortgage_dimensions.EMI, "2760.4"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_daily_offset_accrual_with_ca_pending_out(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2021, month=2, day=12, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="deposit into current account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=CURRENT_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day includes discounted interest",
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "25.42465"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "25.42465"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd interest accrual day includes discounted interest",
                expected_balances_at_ts={
                    datetime(2021, 1, 3, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "50.8493"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "50.8493"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="create pending withdrawal",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(days=2),
                        target_account_id=CURRENT_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="3rd interest accrual day includes discounted interest + pending "
                + "CA withdrawal",
                expected_balances_at_ts={
                    datetime(2021, 1, 4, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "76.27395"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "76.27395"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                            (ca_dimensions.PENDING_OUT, "-10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 2, 12, 0, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "2136.43"),
                            (mortgage_dimensions.INTEREST_DUE, "1067.84"),
                            (mortgage_dimensions.EMI, "2924.6"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(sa_instances=0),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_daily_offset_accrual_with_ca_monthly_fee_application(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2021, month=3, day=12, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))

        ca_template_params = {
            **default_ca_template_params,
            current_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER: dumps(
                {
                    "UPPER_TIER": "20",
                    "MIDDLE_TIER": "10",
                    "LOWER_TIER": "200",
                }
            ),
        }
        ca_instance_params = {
            **default_ca_instance_params,
            current_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_DAY: "12",
        }

        sub_tests = [
            SubTest(
                description="deposit into current account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=CURRENT_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day",
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "25.42465"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "25.42465"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 2, 12, 0, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "2136.43"),
                            (mortgage_dimensions.INTEREST_DUE, "1067.84"),
                            (mortgage_dimensions.EMI, "2924.6"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "9800"),
                        ],
                    }
                },
            ),
            SubTest(
                description="pay 1st mortgage due amount",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3204.27",
                        event_datetime=datetime(2021, 2, 12, 12, 30, 0, tzinfo=ZoneInfo("UTC")),
                        target_account_id=MORTGAGE_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day after repayment (and CA monthly fee applied)",
                expected_balances_at_ts={
                    datetime(2021, 2, 13, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "25.25488"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "25.25488"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "9800"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd interest accrual day after repayment (and CA monthly fee applied)",
                expected_balances_at_ts={
                    datetime(2021, 2, 14, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "50.50976"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "50.50976"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "0"),
                            (mortgage_dimensions.INTEREST_DUE, "0"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "9800"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 3, 12, 0, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        MORTGAGE_ACCOUNT_0: [
                            (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (mortgage_dimensions.PRINCIPAL_DUE, "2217.46"),
                            (mortgage_dimensions.INTEREST_DUE, "707.14"),
                            (mortgage_dimensions.EMI, "2924.6"),
                        ],
                        CURRENT_ACCOUNT_0: [
                            (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (DEFAULT_DIMENSION, "9600"),
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
                ca_template_params=ca_template_params,
                ca_instance_params=ca_instance_params,
            ),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_ca_supervisee_only_commits_interest_accruals_no_offset(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=ZoneInfo("UTC"))
        end = start + timedelta(minutes=5)
        sub_tests = [
            SubTest(
                description="deposit into current account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        event_datetime=start + timedelta(seconds=10),
                        amount="1000",
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=CURRENT_ACCOUNT_0,
                        internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
                    )
                ],
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                mortgage_instances=0,
                sa_instances=0,
                ca_instances=1,
            ),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)
