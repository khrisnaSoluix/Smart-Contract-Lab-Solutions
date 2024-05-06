# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from collections import defaultdict
from datetime import datetime, timezone
from json import dumps

# third party
from dateutil.relativedelta import relativedelta

# common
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    SimulationTestScenario,
    SubTest,
    ContractConfig,
    ContractModuleConfig,
    AccountConfig,
    ExpectedDerivedParameter,
)
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.contracts.simulation.helper import (
    account_to_simulate,
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_template_parameter_change_event,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    SimulationTestCase,
    get_balances,
)

CONTRACT_FILE = "library/mortgage/contracts/mortgage.py"
CONTRACT_MODULES_ALIAS_FILE_MAP = {
    "utils": "library/common/contract_modules/utils.py",
    "amortisation": "library/common/contract_modules/amortisation.py",
}

INPUT_DATA = "library/mortgage/contracts/tests/simulation/input_data.json"
EXPECTED_OUTPUT = "library/mortgage/contracts/tests/simulation/expected_output.json"

DEFAULT_ASSET = "COMMERCIAL_BANK_MONEY"
DEFAULT_DENOMINATION = "GBP"

MORTGAGE_ACCOUNT = "MORTGAGE_ACCOUNT"
DEPOSIT_ACCOUNT = "DEPOSIT_ACCOUNT"

DEFAULT_PENALTY_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_DUE_AMOUNT_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_DELINQUENCY_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_DELINQUENCY_FLAG = dumps(["ACCOUNT_DELINQUENT"])
DEFAULT_OVERDUE_AMOUNT_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_REPAYMENT_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])

INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "ACCRUED_INTEREST_RECEIVABLE"
INTERNAL_INTEREST_RECEIVED_ACCOUNT = "INTEREST_RECEIVED"
INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT = "PENALTY_INTEREST_RECEIVED"
INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT = "CAPITALISED_INTEREST_RECEIVED"
INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT = "LATE_REPAYMENT_FEE_INCOME"
INTERNAL_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT = "OVERPAYMENT_ALLOWANCE_FEE_INCOME"

ASSET = "ASSET"
LIABILITY = "LIABILITY"

default_internal_accounts = {
    DEPOSIT_ACCOUNT: LIABILITY,
    INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: ASSET,
    INTERNAL_INTEREST_RECEIVED_ACCOUNT: LIABILITY,
    INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT: LIABILITY,
    INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: LIABILITY,
    INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: LIABILITY,
    INTERNAL_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT: LIABILITY,
}

PRINCIPAL = "PRINCIPAL"
INTEREST_DUE = "INTEREST_DUE"
PRINCIPAL_DUE = "PRINCIPAL_DUE"
OVERPAYMENT = "OVERPAYMENT"
EMI_PRINCIPAL_EXCESS = "EMI_PRINCIPAL_EXCESS"
INTEREST_OVERDUE = "INTEREST_OVERDUE"
PRINCIPAL_OVERDUE = "PRINCIPAL_OVERDUE"
PENALTIES = "PENALTIES"
EMI_ADDRESS = "EMI"
ACCRUED_INTEREST = "ACCRUED_INTEREST"

PRINCIPAL_DIMENSION = BalanceDimensions(address=PRINCIPAL)
ACCRUED_INTEREST_DIMENSION = BalanceDimensions(address=ACCRUED_INTEREST)
INTEREST_DUE_DIMENSION = BalanceDimensions(address=INTEREST_DUE)
PRINCIPAL_DUE_DIMENSION = BalanceDimensions(address=PRINCIPAL_DUE)
OVERPAYMENT_DIMENSION = BalanceDimensions(address=OVERPAYMENT)
EMI_PRINCIPAL_EXCESS_DIMENSION = BalanceDimensions(address=EMI_PRINCIPAL_EXCESS)
INTEREST_OVERDUE_DIMENSION = BalanceDimensions(address=INTEREST_OVERDUE)
PRINCIPAL_OVERDUE_DIMENSION = BalanceDimensions(address=PRINCIPAL_OVERDUE)
PENALTIES_DIMENSION = BalanceDimensions(address=PENALTIES)
EMI_ADDRESS_DIMENSION = BalanceDimensions(address=EMI_ADDRESS)

default_simulation_start_date = datetime(year=2020, month=1, day=11, tzinfo=timezone.utc)
interest_only_start_date = datetime(year=2019, month=6, day=11, tzinfo=timezone.utc)
num_payments = 1
repayment_day = 28
payment_hour = 12
start_year = 2020
start_month = 1
mortgage_3_interest_only = "774.9"
mortgage_3_interest_only_first_payment = "1019.18"
mortgage_3_EMI = "3186.78"

mortgage_2_instance_params = {
    "fixed_interest_rate": "0.031",
    "fixed_interest_term": "18",
    "total_term": "18",
    "interest_only_term": "6",
    "principal": "30000",
    "repayment_day": "20",
    "deposit_account": DEPOSIT_ACCOUNT,
    "overpayment_percentage": "0.1",
    "overpayment_fee_percentage": "0.05",
    "variable_rate_adjustment": "0.00",
    "mortgage_start_date": str(interest_only_start_date.date()),
}

mortgage_3_instance_params = {
    "fixed_interest_rate": "0.031",
    "fixed_interest_term": "120",
    "total_term": "120",
    "interest_only_term": "12",
    "principal": "300000",
    "repayment_day": "20",
    "deposit_account": DEPOSIT_ACCOUNT,
    "overpayment_percentage": "0.1",
    "overpayment_fee_percentage": "0.05",
    "variable_rate_adjustment": "0.00",
    "mortgage_start_date": str(default_simulation_start_date.date()),
}

mortgage_3_template_params = {
    "variable_interest_rate": "0.189965",
    "denomination": "GBP",
    "late_repayment_fee": "15",
    "penalty_interest_rate": "0.24",
    "penalty_includes_base_rate": "True",
    "grace_period": "5",
    "penalty_blocking_flags": DEFAULT_PENALTY_BLOCKING_FLAG,
    "due_amount_blocking_flags": DEFAULT_DUE_AMOUNT_BLOCKING_FLAG,
    "delinquency_blocking_flags": DEFAULT_DELINQUENCY_BLOCKING_FLAG,
    "delinquency_flags": DEFAULT_DELINQUENCY_FLAG,
    "overdue_amount_blocking_flags": DEFAULT_OVERDUE_AMOUNT_BLOCKING_FLAG,
    "repayment_blocking_flags": DEFAULT_REPAYMENT_BLOCKING_FLAG,
    "accrued_interest_receivable_account": INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    "capitalised_interest_received_account": INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT,
    "interest_received_account": INTERNAL_INTEREST_RECEIVED_ACCOUNT,
    "penalty_interest_received_account": INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT,
    "late_repayment_fee_income_account": INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
    "overpayment_allowance_fee_income_account": INTERNAL_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT,
    "accrual_precision": "5",
    "fulfillment_precision": "2",
    "overpayment_impact_preference": "reduce_term",
    "accrue_interest_hour": "0",
    "accrue_interest_minute": "0",
    "accrue_interest_second": "1",
    "check_delinquency_hour": "0",
    "check_delinquency_minute": "0",
    "check_delinquency_second": "2",
    "repayment_hour": "0",
    "repayment_minute": "1",
    "repayment_second": "0",
    "overpayment_hour": "0",
    "overpayment_minute": "0",
    "overpayment_second": "0",
}

mortgage_4_instance_params = {
    "fixed_interest_rate": "0.031",
    "fixed_interest_term": "3",
    "total_term": "18",
    "interest_only_term": "6",
    "principal": "30000",
    "repayment_day": "20",
    "deposit_account": DEPOSIT_ACCOUNT,
    "overpayment_percentage": "0.1",
    "overpayment_fee_percentage": "0.05",
    "variable_rate_adjustment": "0.001",
    "mortgage_start_date": str(interest_only_start_date.date()),
}

mortgage_4_template_params = {
    "variable_interest_rate": "0.0279",
    "denomination": "GBP",
    "late_repayment_fee": "15",
    "penalty_interest_rate": "0.24",
    "penalty_includes_base_rate": "True",
    "grace_period": "5",
    "penalty_blocking_flags": DEFAULT_PENALTY_BLOCKING_FLAG,
    "due_amount_blocking_flags": DEFAULT_DUE_AMOUNT_BLOCKING_FLAG,
    "delinquency_blocking_flags": DEFAULT_DELINQUENCY_BLOCKING_FLAG,
    "delinquency_flags": DEFAULT_DELINQUENCY_FLAG,
    "overdue_amount_blocking_flags": DEFAULT_OVERDUE_AMOUNT_BLOCKING_FLAG,
    "repayment_blocking_flags": DEFAULT_REPAYMENT_BLOCKING_FLAG,
    "accrued_interest_receivable_account": INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    "capitalised_interest_received_account": INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT,
    "interest_received_account": INTERNAL_INTEREST_RECEIVED_ACCOUNT,
    "penalty_interest_received_account": INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT,
    "late_repayment_fee_income_account": INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
    "overpayment_allowance_fee_income_account": INTERNAL_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT,
    "accrual_precision": "5",
    "fulfillment_precision": "2",
    "overpayment_impact_preference": "reduce_term",
    "accrue_interest_hour": "0",
    "accrue_interest_minute": "0",
    "accrue_interest_second": "1",
    "check_delinquency_hour": "0",
    "check_delinquency_minute": "0",
    "check_delinquency_second": "2",
    "repayment_hour": "0",
    "repayment_minute": "1",
    "repayment_second": "0",
    "overpayment_hour": "0",
    "overpayment_minute": "0",
    "overpayment_second": "0",
}


class MortgageFixedTest(SimulationTestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_filepath = CONTRACT_FILE
        cls.input_data_filename = INPUT_DATA
        cls.expected_output_filename = EXPECTED_OUTPUT
        cls.linked_contract_modules = [
            ContractModuleConfig(alias, file_path)
            for (alias, file_path) in CONTRACT_MODULES_ALIAS_FILE_MAP.items()
        ]
        super().setUpClass()

    def _get_contract_config(
        self,
        contract_version_id=None,
        instance_params=None,
        template_params=None,
    ):
        contract_config = ContractConfig(
            contract_file_path=CONTRACT_FILE,
            template_params=template_params or self.default_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or self.default_instance_params,
                    account_id_base=MORTGAGE_ACCOUNT,
                )
            ],
            linked_contract_modules=self.linked_contract_modules,
        )
        if contract_version_id:
            contract_config.smart_contract_version_id = contract_version_id
        return contract_config

    def _get_simulation_test_scenario(
        self,
        start,
        end,
        sub_tests,
        template_params=None,
        instance_params=None,
        internal_accounts=None,
    ):
        return SimulationTestScenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            contract_config=self._get_contract_config(
                instance_params=instance_params,
                template_params=template_params,
            ),
            internal_accounts=internal_accounts,
        )

    def test_monthly_due_for_fixed_rate_interest_only_to_plus_principal_repayment(self):
        start = interest_only_start_date
        end = interest_only_start_date + relativedelta(months=18, days=10)

        main_account = account_to_simulate(
            timestamp=start,
            account_id=MORTGAGE_ACCOUNT,
            instance_params=mortgage_2_instance_params,
            template_params=mortgage_3_template_params,
            contract_file_path=self.contract_filepath,
        )

        events = []

        for event in self.input_data["fixed_rate_interest_only_to_plus_principal"]:
            # Repayments occur on repayment day
            events.extend(
                _set_up_deposit_events(
                    int(event[1]),
                    event[2],
                    20,
                    payment_hour,
                    int(event[3]),
                    int(event[4]),
                )
            )

        res = self.client.simulate_smart_contract(
            account_creation_events=[main_account],
            contract_config=self._get_contract_config(
                contract_version_id=main_account["smart_contract_version_id"],
                instance_params=mortgage_3_instance_params,
                template_params=mortgage_3_template_params,
            ),
            internal_account_ids=default_internal_accounts,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
        )

        balances = get_balances(res)

        repayment_date = datetime(
            year=2019,
            month=7,
            day=20,
            hour=0,
            minute=1,
            second=0,
            microsecond=2,
            tzinfo=timezone.utc,
        )
        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        for i, values in enumerate(self.expected_output["interest_only_to_plus_principal"]):
            expected_balances[MORTGAGE_ACCOUNT][repayment_date + relativedelta(months=i)] = [
                (PRINCIPAL_DUE_DIMENSION, values[0]),
                (INTEREST_DUE_DIMENSION, values[1]),
            ]
        self.check_balances(expected_balances=expected_balances, actual_balances=balances)

    def test_monthly_due_for_fixed_to_variable_rate_interest_only_to_plus_principal_repayment(
        self,
    ):
        start = interest_only_start_date
        end = interest_only_start_date + relativedelta(months=18, days=10)

        main_account = account_to_simulate(
            timestamp=start,
            account_id=MORTGAGE_ACCOUNT,
            instance_params=mortgage_4_instance_params,
            template_params=mortgage_4_template_params,
            contract_file_path=self.contract_filepath,
        )

        events = []
        for event in self.input_data["fixed_to_variable_rate_interest_only_to_plus_principal"]:
            if event[0] == "variable_rate_change":
                events.append(
                    create_template_parameter_change_event(
                        timestamp=datetime(
                            year=int(event[1]),
                            month=int(event[2]),
                            day=int(event[3]),
                            hour=12,
                            tzinfo=timezone.utc,
                        ),
                        smart_contract_version_id=main_account["smart_contract_version_id"],
                        variable_interest_rate=str(event[4]),
                    )
                )
            else:
                events.extend(
                    _set_up_deposit_events(
                        int(event[1]), event[2], 20, 10, int(event[3]), int(event[4])
                    )
                )

        res = self.client.simulate_smart_contract(
            account_creation_events=[main_account],
            contract_config=self._get_contract_config(
                contract_version_id=main_account["smart_contract_version_id"],
                instance_params=mortgage_4_instance_params,
                template_params=mortgage_4_template_params,
            ),
            internal_account_ids=default_internal_accounts,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
        )

        balances = get_balances(res)

        repayment_date = datetime(
            year=2019,
            month=7,
            day=20,
            hour=0,
            minute=1,
            second=0,
            microsecond=2,
            tzinfo=timezone.utc,
        )
        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        for i, values in enumerate(
            self.expected_output["fixed_to_variable_rate_interest_only_to_plus_principal"]
        ):
            expected_balances[MORTGAGE_ACCOUNT][repayment_date + relativedelta(months=i)] = [
                (PRINCIPAL_DUE_DIMENSION, values[0]),
                (INTEREST_DUE_DIMENSION, values[1]),
            ]
        self.check_balances(expected_balances=expected_balances, actual_balances=balances)

    def test_derived_param_is_interest_only_term_true(self):
        start = datetime(2020, 1, 9, minute=5, second=10, tzinfo=timezone.utc)
        end = datetime(2020, 3, 12, tzinfo=timezone.utc)
        template_params = mortgage_3_template_params.copy()
        instance_params = mortgage_3_instance_params.copy()
        instance_params["interest_only_term"] = "1"

        events = []
        # repayment day is 20 hence interest only term will change only after 20.
        before_interest_only_term_end_date = datetime(2020, 2, 20, tzinfo=timezone.utc)
        after_interest_only_term_end_date = datetime(2020, 2, 21, tzinfo=timezone.utc)
        sub_tests = [
            SubTest(
                description="check derived parameters",
                events=events,
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_interest_only_term_end_date,
                        account_id=MORTGAGE_ACCOUNT,
                        name="is_interest_only_term",
                        value="True",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_interest_only_term_end_date,
                        account_id=MORTGAGE_ACCOUNT,
                        name="is_interest_only_term",
                        value="False",
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

    def test_derived_param_is_interest_only_term_false(self):
        start = datetime(2020, 1, 9, minute=5, second=10, tzinfo=timezone.utc)
        end = datetime(2020, 2, 23, tzinfo=timezone.utc)
        template_params = mortgage_3_template_params.copy()
        instance_params = mortgage_3_instance_params.copy()
        instance_params["interest_only_term"] = "0"

        events = [
            create_instance_parameter_change_event(
                account_id=MORTGAGE_ACCOUNT,
                timestamp=datetime(2020, 1, 17, tzinfo=timezone.utc),
                interest_only_term="1",
            ),
        ]
        before_param_change_date = datetime(2020, 1, 16, tzinfo=timezone.utc)
        after_param_change_date = datetime(2020, 1, 18, tzinfo=timezone.utc)
        after_interest_only_term_end_date = datetime(2020, 2, 21, tzinfo=timezone.utc)
        sub_tests = [
            SubTest(
                description="check derived parameters",
                events=events,
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_param_change_date,
                        account_id=MORTGAGE_ACCOUNT,
                        name="is_interest_only_term",
                        value="False",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_param_change_date,
                        account_id=MORTGAGE_ACCOUNT,
                        name="is_interest_only_term",
                        value="True",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_interest_only_term_end_date,
                        account_id=MORTGAGE_ACCOUNT,
                        name="is_interest_only_term",
                        value="False",
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


def _set_up_deposit_events(
    num_payments,
    repayment_amount,
    repayment_day,
    repayment_hour,
    start_year,
    start_month,
):
    events = []
    for i in range(num_payments):
        month = (i + start_month - 1) % 12 + 1
        year = start_year + int((i + start_month + 1 - month) / 12)

        event_date = datetime(
            year=year,
            month=month,
            day=repayment_day,
            hour=repayment_hour,
            tzinfo=timezone.utc,
        )
        events.append(
            create_inbound_hard_settlement_instruction(
                target_account_id=MORTGAGE_ACCOUNT,
                amount=repayment_amount,
                event_datetime=event_date,
                internal_account_id=DEPOSIT_ACCOUNT,
            )
        )

    return events
