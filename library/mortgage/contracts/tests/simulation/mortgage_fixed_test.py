# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from itertools import chain
from json import dumps

# third party
from dateutil.relativedelta import relativedelta

# common
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.contracts.simulation.helper import (
    account_to_simulate,
    create_inbound_hard_settlement_instruction,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    SimulationTestCase,
    get_balances,
)

from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    SimulationTestScenario,
    ExpectedDerivedParameter,
    ExpectedWorkflow,
    SubTest,
    ContractConfig,
    ContractModuleConfig,
    AccountConfig,
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
num_payments = 1
repayment_day = 28
payment_hour = 12
start_year = 2020
start_month = 1

mortgage_2_first_month_payment = str(Decimal("2910.69") + Decimal("229.32"))
mortgage_2_EMI = "2910.69"
mortgage_2_expected_fee = "35.0"

mortgage_3_EMI = "2542.18"
mortgage_3_first_month_payment = "2565.11"


mortgage_1_instance_params = {
    "fixed_interest_rate": "0.031",
    "fixed_interest_term": "48",
    "total_term": "48",
    "overpayment_fee_percentage": "0.05",
    "interest_only_term": "0",
    "principal": "300000",
    "repayment_day": "20",
    "deposit_account": DEPOSIT_ACCOUNT,
    "overpayment_percentage": "0.1",
    "variable_rate_adjustment": "0.00",
    "mortgage_start_date": str(default_simulation_start_date.date()),
}

mortgage_1_template_params = {
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

mortgage_2_instance_params = {
    "fixed_interest_rate": "0.031",
    "fixed_interest_term": "120",
    "total_term": "120",
    "interest_only_term": "0",
    "overpayment_fee_percentage": "0.05",
    "principal": "300000",
    "repayment_day": "20",
    "deposit_account": DEPOSIT_ACCOUNT,
    "overpayment_percentage": "0.1",
    "variable_rate_adjustment": "0.00",
    "mortgage_start_date": str(default_simulation_start_date.date()),
}

mortgage_2_template_params = {
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

mortgage_3_instance_params = {
    "fixed_interest_rate": "0.031",
    "fixed_interest_term": "12",
    "total_term": "12",
    "interest_only_term": "0",
    "overpayment_fee_percentage": "0.05",
    "principal": "30000",
    "repayment_day": "20",
    "deposit_account": DEPOSIT_ACCOUNT,
    "overpayment_percentage": "0.1",
    "variable_rate_adjustment": "0.00",
    "mortgage_start_date": str(default_simulation_start_date.date()),
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
        debug=False,
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
            debug=debug,
        )

    def test_monthly_due_for_fixed_rate_with_full_repayment(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=1, day=29, minute=1, tzinfo=timezone.utc)

        main_account = account_to_simulate(
            timestamp=start,
            account_id=MORTGAGE_ACCOUNT,
            instance_params=mortgage_3_instance_params,
            template_params=mortgage_2_template_params,
            contract_file_path=self.contract_filepath,
        )
        events = []

        events.extend(
            _set_up_deposit_events(
                1,
                mortgage_3_first_month_payment,
                repayment_day,
                payment_hour,
                start_year,
                2,
            )
        )
        events.extend(
            _set_up_deposit_events(11, mortgage_3_EMI, repayment_day, payment_hour, start_year, 3)
        )

        res = self.client.simulate_smart_contract(
            account_creation_events=[main_account],
            contract_config=self._get_contract_config(
                contract_version_id=main_account["smart_contract_version_id"],
                instance_params=mortgage_2_instance_params,
                template_params=mortgage_2_template_params,
            ),
            internal_account_ids=default_internal_accounts,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
        )

        repayment_date = datetime(
            year=start_year,
            month=2,
            day=20,
            hour=0,
            minute=2,
            second=0,
            microsecond=2,
            tzinfo=timezone.utc,
        )
        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        for i, values in enumerate(self.expected_output["1year_monthly_repayment"]):
            expected_balances[MORTGAGE_ACCOUNT][repayment_date + relativedelta(months=i)] = [
                (PRINCIPAL_DIMENSION, values[0]),
                (PRINCIPAL_DUE_DIMENSION, values[1]),
                (INTEREST_DUE_DIMENSION, values[2]),
            ]

        self.check_balances(expected_balances=expected_balances, actual_balances=get_balances(res))

    def test_monthly_due_for_fixed_rate(self):
        """
        Test for Fixed Rate Interest.
        """
        start = default_simulation_start_date
        end = datetime(year=2021, month=1, day=21, minute=1, tzinfo=timezone.utc)

        mortgage_account = account_to_simulate(
            timestamp=start,
            account_id=MORTGAGE_ACCOUNT,
            instance_params=mortgage_2_instance_params,
            template_params=mortgage_2_template_params,
            contract_file_path=self.contract_filepath,
        )

        repayment_day = int(mortgage_2_instance_params["repayment_day"])
        # first repayment includes 9 additional days interest
        # mortgage start date = 20200111 and repayment day = 20
        # daliy rate (25.48) * additional days (9) = 229.32
        repayment_1 = _set_up_deposit_events(
            1,
            mortgage_2_first_month_payment,
            repayment_day,
            payment_hour,
            start_year,
            2,
        )
        repayment_2 = _set_up_deposit_events(
            11, mortgage_2_EMI, repayment_day, payment_hour, start_year, 3
        )
        events = list(chain.from_iterable([repayment_1, repayment_2]))

        res = self.client.simulate_smart_contract(
            account_creation_events=[mortgage_account],
            contract_config=self._get_contract_config(
                contract_version_id=mortgage_account["smart_contract_version_id"],
                instance_params=mortgage_2_instance_params,
                template_params=mortgage_2_template_params,
            ),
            internal_account_ids=default_internal_accounts,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
        )

        repayment_date = datetime(
            year=start_year, month=2, day=repayment_day, hour=1, tzinfo=timezone.utc
        )
        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        for i, values in enumerate(self.expected_output["monthly_due_fixed"]):
            expected_balances[MORTGAGE_ACCOUNT][repayment_date + relativedelta(months=i)] = [
                (PRINCIPAL_DUE_DIMENSION, values[0]),
                (INTEREST_DUE_DIMENSION, values[1]),
            ]

        self.check_balances(expected_balances, get_balances(res))

    def test_monthly_due_for_fixed_rate_with_one_overpayment(self):
        """
        Test for Fixed Rate Interest with an overpayment in month 3.
        """
        start = default_simulation_start_date
        end = datetime(year=2021, month=1, day=21, minute=1, tzinfo=timezone.utc)

        mortgage_account = account_to_simulate(
            timestamp=start,
            account_id=MORTGAGE_ACCOUNT,
            instance_params=mortgage_2_instance_params,
            template_params=mortgage_2_template_params,
            contract_file_path=self.contract_filepath,
        )

        repayment_day = int(mortgage_2_instance_params["repayment_day"])
        # first repayment includes 9 additional days interest
        # mortgage start date = 20200111 and repayment day = 20
        # daliy rate (25.48) * additional days (9) = 229.32
        repayment_1 = _set_up_deposit_events(
            1,
            mortgage_2_first_month_payment,
            repayment_day,
            payment_hour,
            start_year,
            2,
        )
        # second repayment includes overpayment
        repayment_2 = _set_up_deposit_events(
            1,
            str(Decimal(mortgage_2_EMI) + Decimal("10000")),
            repayment_day,
            1,
            start_year,
            3,
        )
        repayment_3 = _set_up_deposit_events(
            10, mortgage_2_EMI, repayment_day, payment_hour, start_year, 4
        )
        events = list(chain.from_iterable([repayment_1, repayment_2, repayment_3]))

        res = self.client.simulate_smart_contract(
            account_creation_events=[mortgage_account],
            contract_config=self._get_contract_config(
                contract_version_id=mortgage_account["smart_contract_version_id"],
                instance_params=mortgage_2_instance_params,
                template_params=mortgage_2_template_params,
            ),
            internal_account_ids=default_internal_accounts,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
        )

        repayment_date = datetime(
            year=start_year, month=2, day=repayment_day, hour=1, tzinfo=timezone.utc
        )
        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        for i, values in enumerate(self.expected_output["monthly_due_fixed_with_one_overpayment"]):
            expected_balances[MORTGAGE_ACCOUNT][repayment_date + relativedelta(months=i)] = [
                (PRINCIPAL_DUE_DIMENSION, values[0]),
                (INTEREST_DUE_DIMENSION, values[1]),
            ]

        self.check_balances(expected_balances, get_balances(res))

    def test_monthly_due_for_fixed_rate_with_regular_overpayment(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=11, day=21, minute=1, tzinfo=timezone.utc)

        mortgage_account = account_to_simulate(
            timestamp=start,
            account_id=MORTGAGE_ACCOUNT,
            instance_params=mortgage_3_instance_params,
            template_params=mortgage_2_template_params,
            contract_file_path=self.contract_filepath,
        )

        first_payment_event = _set_up_deposit_events(
            1,
            str(Decimal(mortgage_3_first_month_payment) + Decimal("1000")),
            20,
            payment_hour,
            start_year,
            2,
        )
        repayment_with_overpayment = str(Decimal(mortgage_3_EMI) + Decimal("1000"))
        events = first_payment_event + _set_up_deposit_events(
            7, repayment_with_overpayment, 20, payment_hour, start_year, 3
        )

        res = self.client.simulate_smart_contract(
            account_creation_events=[mortgage_account],
            contract_config=self._get_contract_config(
                contract_version_id=mortgage_account["smart_contract_version_id"],
                instance_params=mortgage_2_instance_params,
                template_params=mortgage_2_template_params,
            ),
            internal_account_ids=default_internal_accounts,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
        )

        repayment_date = datetime(
            year=start_year,
            month=2,
            day=20,
            hour=0,
            minute=1,
            second=0,
            microsecond=2,
            tzinfo=timezone.utc,
        )
        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        for i, values in enumerate(
            self.expected_output["monthly_due_fixed_with_regular_overpayment"]
        ):
            expected_balances[MORTGAGE_ACCOUNT][repayment_date + relativedelta(months=i)] = [
                (PRINCIPAL_DUE_DIMENSION, values[0]),
                (INTEREST_DUE_DIMENSION, values[1]),
            ]

        self.check_balances(expected_balances=expected_balances, actual_balances=get_balances(res))

    def test_regular_overpayment_impact_preference_reduce_emi(self):
        start = datetime(year=2020, month=1, day=11, tzinfo=timezone.utc)
        end = start + relativedelta(months=12, days=10)

        first_repayment_date = datetime(
            year=start_year,
            month=2,
            day=20,
            hour=0,
            minute=1,
            second=0,
            microsecond=2,
            tzinfo=timezone.utc,
        )

        second_repayment_date = first_repayment_date + relativedelta(months=1)
        third_repayment_date = second_repayment_date + relativedelta(months=1)
        fourth_repayment_date = third_repayment_date + relativedelta(months=1)
        fifth_repayment_date = fourth_repayment_date + relativedelta(months=1)
        sixth_repayment_date = fifth_repayment_date + relativedelta(months=1)
        seventh_repayment_date = sixth_repayment_date + relativedelta(months=1)
        eighth_repayment_date = seventh_repayment_date + relativedelta(months=1)
        nineth_repayment_date = eighth_repayment_date + relativedelta(months=1)
        tenth_repayment_date = nineth_repayment_date + relativedelta(months=1)
        eleventh_repayment_date = tenth_repayment_date + relativedelta(months=1)
        final_repayment_date = eleventh_repayment_date + relativedelta(months=1)

        template_params = mortgage_1_template_params.copy()
        template_params["overpayment_impact_preference"] = "reduce_emi"

        instance_params = mortgage_1_instance_params.copy()
        instance_params["total_term"] = "12"
        instance_params["principal"] = "3000"

        sub_tests = [
            SubTest(
                description="first month emi",
                expected_balances_at_ts={
                    first_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "246.32"),
                            (INTEREST_DUE_DIMENSION, "10.19"),
                            (EMI_ADDRESS_DIMENSION, "254.22"),
                            (OVERPAYMENT_DIMENSION, "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="regular overpayments of 100",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # emi plus additional interest from account creation
                        "356.51",
                        first_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "345.00",
                        second_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "334.82",
                        third_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "323.58",
                        fourth_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "310.93",
                        fifth_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "296.51",
                        sixth_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "279.68",
                        seventh_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "259.53",
                        eighth_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "234.38",
                        nineth_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "200.87",
                        tenth_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        # only paying the EMI amount instead of ending the mortgage early
                        "50.69",
                        eleventh_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        # final payment of remaining mortgage + overpayment charge
                        "85.68",
                        final_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    second_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "238.46"),
                            (INTEREST_DUE_DIMENSION, "6.54"),
                            (EMI_ADDRESS_DIMENSION, "245.00"),
                            (OVERPAYMENT_DIMENSION, "-100"),
                        ]
                    },
                    third_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "228.72"),
                            (INTEREST_DUE_DIMENSION, "6.10"),
                            (EMI_ADDRESS_DIMENSION, "234.82"),
                            (OVERPAYMENT_DIMENSION, "-200"),
                        ]
                    },
                    fourth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "218.52"),
                            (INTEREST_DUE_DIMENSION, "5.06"),
                            (EMI_ADDRESS_DIMENSION, "223.58"),
                            (OVERPAYMENT_DIMENSION, "-300"),
                        ]
                    },
                    fifth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "206.54"),
                            (INTEREST_DUE_DIMENSION, "4.39"),
                            (EMI_ADDRESS_DIMENSION, "210.93"),
                            (OVERPAYMENT_DIMENSION, "-400"),
                        ]
                    },
                    sixth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "193.04"),
                            (INTEREST_DUE_DIMENSION, "3.47"),
                            (EMI_ADDRESS_DIMENSION, "196.51"),
                            (OVERPAYMENT_DIMENSION, "-500"),
                        ]
                    },
                    seventh_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "176.87"),
                            (INTEREST_DUE_DIMENSION, "2.81"),
                            (EMI_ADDRESS_DIMENSION, "179.68"),
                            (OVERPAYMENT_DIMENSION, "-600"),
                        ]
                    },
                    eighth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "157.45"),
                            (INTEREST_DUE_DIMENSION, "2.08"),
                            (EMI_ADDRESS_DIMENSION, "159.53"),
                            (OVERPAYMENT_DIMENSION, "-700"),
                        ]
                    },
                    nineth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "133.02"),
                            (INTEREST_DUE_DIMENSION, "1.36"),
                            (EMI_ADDRESS_DIMENSION, "134.38"),
                            (OVERPAYMENT_DIMENSION, "-800"),
                        ]
                    },
                    tenth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "100.08"),
                            (INTEREST_DUE_DIMENSION, "0.79"),
                            (EMI_ADDRESS_DIMENSION, "100.87"),
                            (OVERPAYMENT_DIMENSION, "-900"),
                        ]
                    },
                    eleventh_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "50.43"),
                            (INTEREST_DUE_DIMENSION, "0.26"),
                            (EMI_ADDRESS_DIMENSION, "50.69"),
                            (OVERPAYMENT_DIMENSION, "-1000"),
                        ]
                    },
                    final_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            # last payment rounds to remaining principal
                            # instead of using stored EMI
                            # hence total due is 50.68 instead of equal to EMI 50.69
                            (PRINCIPAL_DUE_DIMENSION, "50.55"),
                            (INTEREST_DUE_DIMENSION, "0.13"),
                            (EMI_ADDRESS_DIMENSION, "50.69"),
                            (OVERPAYMENT_DIMENSION, "-1000"),
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            # overpayment fee event ran on 2021/01/11
                            # total overpayment = 1000
                            # allowance 3000 * 0.1 = 300
                            # overpaid above allowance = 1000 - 300 = 700
                            # fee = 700 * 0.05 = 35
                            (PENALTIES_DIMENSION, "35"),
                        ]
                    },
                    final_repayment_date
                    + relativedelta(hours=6): {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                            (EMI_ADDRESS_DIMENSION, "50.69"),
                            (OVERPAYMENT_DIMENSION, "-1000"),
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DIMENSION, "1014.36"),
                            (PENALTIES_DIMENSION, "0"),
                            (
                                BalanceDimensions(address="EMI_PRINCIPAL_EXCESS"),
                                "-14.36",
                            ),
                            (
                                BalanceDimensions(address="PRINCIPAL_CAPITALISED_INTEREST"),
                                "0",
                            ),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="11",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="10",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=third_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="9",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=fourth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="8",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=fifth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="7",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=sixth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="6",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=seventh_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="5",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=eighth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="4",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=nineth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="3",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=tenth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="2",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=eleventh_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="1",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=final_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="0",
                    ),
                ],
                expected_workflows=[
                    ExpectedWorkflow(
                        run_times=[final_repayment_date + relativedelta(hours=5)],
                        workflow_definition_id="MORTGAGE_CLOSURE",
                        account_id=MORTGAGE_ACCOUNT,
                        count=1,
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

    def test_one_off_overpayment_impact_preference_reduce_emi(self):
        start = datetime(year=2020, month=1, day=11, tzinfo=timezone.utc)
        end = start + relativedelta(months=12, days=10)

        first_repayment_date = datetime(
            year=start_year,
            month=2,
            day=20,
            hour=0,
            minute=1,
            second=0,
            microsecond=2,
            tzinfo=timezone.utc,
        )

        second_repayment_date = first_repayment_date + relativedelta(months=1)
        third_repayment_date = second_repayment_date + relativedelta(months=1)
        fourth_repayment_date = third_repayment_date + relativedelta(months=1)
        fifth_repayment_date = fourth_repayment_date + relativedelta(months=1)
        sixth_repayment_date = fifth_repayment_date + relativedelta(months=1)
        seventh_repayment_date = sixth_repayment_date + relativedelta(months=1)
        eighth_repayment_date = seventh_repayment_date + relativedelta(months=1)
        nineth_repayment_date = eighth_repayment_date + relativedelta(months=1)
        tenth_repayment_date = nineth_repayment_date + relativedelta(months=1)
        eleventh_repayment_date = tenth_repayment_date + relativedelta(months=1)
        final_repayment_date = eleventh_repayment_date + relativedelta(months=1)

        template_params = mortgage_1_template_params.copy()
        template_params["overpayment_impact_preference"] = "reduce_emi"

        instance_params = mortgage_1_instance_params.copy()
        instance_params["total_term"] = "12"
        instance_params["principal"] = "3000"

        sub_tests = [
            SubTest(
                description="first month emi",
                expected_balances_at_ts={
                    first_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "246.32"),
                            (INTEREST_DUE_DIMENSION, "10.19"),
                            (EMI_ADDRESS_DIMENSION, "254.22"),
                            (OVERPAYMENT_DIMENSION, "0"),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="11",
                    ),
                ],
            ),
            SubTest(
                description="repayments without overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "256.51",
                        first_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "254.22",
                        second_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "254.22",
                        third_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    second_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "247.44"),
                            (INTEREST_DUE_DIMENSION, "6.78"),
                            (EMI_ADDRESS_DIMENSION, "254.22"),
                        ]
                    },
                    third_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "247.62"),
                            (INTEREST_DUE_DIMENSION, "6.60"),
                            (EMI_ADDRESS_DIMENSION, "254.22"),
                        ]
                    },
                    fourth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "248.47"),
                            (INTEREST_DUE_DIMENSION, "5.75"),
                            (EMI_ADDRESS_DIMENSION, "254.22"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=second_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="10",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=third_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="9",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=fourth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="8",
                    ),
                ],
            ),
            SubTest(
                description="single overpayments of 250",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "504.22",
                        fourth_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    fifth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "217.95"),
                            (INTEREST_DUE_DIMENSION, "4.63"),
                            (EMI_ADDRESS_DIMENSION, "222.58"),
                            (OVERPAYMENT_DIMENSION, "-250"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=fifth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="7",
                    ),
                ],
            ),
            SubTest(
                description="normal payments for the rest of lifetime",
                events=_set_up_deposit_events(
                    7,
                    "222.58",
                    repayment_day,
                    payment_hour,
                    2020,
                    6,
                ),
                expected_balances_at_ts={
                    sixth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "218.65"),
                            (INTEREST_DUE_DIMENSION, "3.93"),
                            (EMI_ADDRESS_DIMENSION, "222.58"),
                            (OVERPAYMENT_DIMENSION, "-250"),
                        ]
                    },
                    seventh_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "219.10"),
                            (INTEREST_DUE_DIMENSION, "3.48"),
                            (EMI_ADDRESS_DIMENSION, "222.58"),
                            (OVERPAYMENT_DIMENSION, "-250"),
                        ]
                    },
                    eighth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "219.67"),
                            (INTEREST_DUE_DIMENSION, "2.91"),
                            (EMI_ADDRESS_DIMENSION, "222.58"),
                            (OVERPAYMENT_DIMENSION, "-250"),
                        ]
                    },
                    nineth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "220.33"),
                            (INTEREST_DUE_DIMENSION, "2.25"),
                            (EMI_ADDRESS_DIMENSION, "222.58"),
                            (OVERPAYMENT_DIMENSION, "-250"),
                        ]
                    },
                    tenth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "220.83"),
                            (INTEREST_DUE_DIMENSION, "1.75"),
                            (EMI_ADDRESS_DIMENSION, "222.58"),
                            (OVERPAYMENT_DIMENSION, "-250"),
                        ]
                    },
                    eleventh_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "221.45"),
                            (INTEREST_DUE_DIMENSION, "1.13"),
                            (EMI_ADDRESS_DIMENSION, "222.58"),
                            (OVERPAYMENT_DIMENSION, "-250"),
                        ]
                    },
                    final_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "222.17"),
                            (INTEREST_DUE_DIMENSION, "0.58"),
                            (EMI_ADDRESS_DIMENSION, "222.58"),
                            (OVERPAYMENT_DIMENSION, "-250"),
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=sixth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="6",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=seventh_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="5",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=eighth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="4",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=nineth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="3",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=tenth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="2",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=eleventh_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="1",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=final_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="0",
                    ),
                ],
            ),
            SubTest(
                description="final repayment closes account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # final EMI + residual
                        "222.75",
                        final_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    )
                ],
                expected_workflows=[
                    ExpectedWorkflow(
                        run_times=[final_repayment_date + relativedelta(hours=5)],
                        workflow_definition_id="MORTGAGE_CLOSURE",
                        account_id=MORTGAGE_ACCOUNT,
                        count=1,
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
