# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from itertools import chain

# third party
from dateutil.relativedelta import relativedelta

# common
import inception_sdk.test_framework.common.constants as constants
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

# Loan specific
import library.loan.constants.accounts as accounts
import library.loan.constants.dimensions as dimensions
import library.loan.constants.files as contract_files
import library.loan.contracts.tests.simulation.constants.files as sim_files
import library.loan.constants.flags as flags

default_simulation_start_date = datetime(year=2020, month=1, day=11, tzinfo=timezone.utc)
num_payments = 1
repayment_day = 28
payment_hour = 12
start_year = 2020
start_month = 1
loan_1_EMI = "6653.57"
loan_1_first_month_payment = "6882.89"
loan_2_first_month_payment = str(Decimal("2910.69") + Decimal("229.32"))
loan_2_EMI = "2910.69"
loan_2_expected_fee = "35.0"
loan_3_EMI = "2542.18"
loan_3_first_month_payment = "2565.11"


loan_1_instance_params = {
    "fixed_interest_rate": "0.031",
    "fixed_interest_loan": "True",
    "total_term": "48",
    "upfront_fee": "0",
    "amortise_upfront_fee": "True",
    "principal": "300000",
    "repayment_day": "20",
    "deposit_account": accounts.DEPOSIT_ACCOUNT,
    "variable_rate_adjustment": "0.00",
    "loan_start_date": str(default_simulation_start_date.date()),
    "repayment_holiday_impact_preference": "increase_emi",
    "capitalise_late_repayment_fee": "False",
    "interest_accrual_rest_type": "daily",
}

loan_1_template_params = {
    "variable_interest_rate": "0.189965",
    "annual_interest_rate_cap": "1.00",
    "annual_interest_rate_floor": "0.00",
    "denomination": constants.DEFAULT_DENOMINATION,
    "late_repayment_fee": "15",
    "penalty_interest_rate": "0.24",
    "capitalise_penalty_interest": "False",
    "penalty_includes_base_rate": "True",
    "repayment_period": "10",
    "grace_period": "5",
    "penalty_compounds_overdue_interest": "True",
    "accrue_interest_on_due_principal": "False",
    "penalty_blocking_flags": flags.DEFAULT_PENALTY_BLOCKING_FLAG,
    "due_amount_blocking_flags": flags.DEFAULT_DUE_AMOUNT_BLOCKING_FLAG,
    "delinquency_blocking_flags": flags.DEFAULT_DELINQUENCY_BLOCKING_FLAG,
    "delinquency_flags": flags.DEFAULT_DELINQUENCY_FLAG,
    "overdue_amount_blocking_flags": flags.DEFAULT_OVERDUE_AMOUNT_BLOCKING_FLAG,
    "repayment_blocking_flags": flags.DEFAULT_REPAYMENT_BLOCKING_FLAG,
    "accrued_interest_receivable_account": accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    "capitalised_interest_received_account": (
        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT
    ),
    "capitalised_interest_receivable_account": (
        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT
    ),
    "capitalised_penalties_received_account": (
        accounts.INTERNAL_CAPITALISED_PENALTIES_RECEIVED_ACCOUNT
    ),
    "interest_received_account": accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT,
    "penalty_interest_received_account": accounts.INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT,
    "late_repayment_fee_income_account": accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
    "overpayment_fee_income_account": accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT,
    "overpayment_fee_rate": "0.05",
    "upfront_fee_income_account": accounts.INTERNAL_UPFRONT_FEE_INCOME_ACCOUNT,
    "accrual_precision": "5",
    "fulfillment_precision": "2",
    "amortisation_method": "declining_principal",
    "capitalise_no_repayment_accrued_interest": "no_capitalisation",
    "overpayment_impact_preference": "reduce_term",
    "accrue_interest_hour": "0",
    "accrue_interest_minute": "0",
    "accrue_interest_second": "1",
    "check_overdue_hour": "0",
    "check_overdue_minute": "0",
    "check_overdue_second": "2",
    "check_delinquency_hour": "0",
    "check_delinquency_minute": "0",
    "check_delinquency_second": "2",
    "repayment_hour": "0",
    "repayment_minute": "1",
    "repayment_second": "0",
}

loan_2_instance_params = {
    "fixed_interest_rate": "0.031",
    "fixed_interest_loan": "True",
    "total_term": "120",
    "upfront_fee": "0",
    "amortise_upfront_fee": "True",
    "principal": "300000",
    "repayment_day": "20",
    "deposit_account": accounts.DEPOSIT_ACCOUNT,
    "variable_rate_adjustment": "0.00",
    "loan_start_date": str(default_simulation_start_date.date()),
    "repayment_holiday_impact_preference": "increase_emi",
    "capitalise_late_repayment_fee": "False",
    "interest_accrual_rest_type": "daily",
}

loan_2_template_params = {
    "variable_interest_rate": "0.189965",
    "annual_interest_rate_cap": "1.00",
    "annual_interest_rate_floor": "0.00",
    "denomination": constants.DEFAULT_DENOMINATION,
    "late_repayment_fee": "15",
    "penalty_interest_rate": "0.24",
    "capitalise_penalty_interest": "False",
    "penalty_includes_base_rate": "True",
    "repayment_period": "10",
    "grace_period": "5",
    "penalty_compounds_overdue_interest": "True",
    "accrue_interest_on_due_principal": "False",
    "penalty_blocking_flags": flags.DEFAULT_PENALTY_BLOCKING_FLAG,
    "due_amount_blocking_flags": flags.DEFAULT_DUE_AMOUNT_BLOCKING_FLAG,
    "delinquency_blocking_flags": flags.DEFAULT_DELINQUENCY_BLOCKING_FLAG,
    "delinquency_flags": flags.DEFAULT_DELINQUENCY_FLAG,
    "overdue_amount_blocking_flags": flags.DEFAULT_OVERDUE_AMOUNT_BLOCKING_FLAG,
    "repayment_blocking_flags": flags.DEFAULT_REPAYMENT_BLOCKING_FLAG,
    "accrued_interest_receivable_account": accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    "capitalised_interest_received_account": (
        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT
    ),
    "capitalised_interest_receivable_account": (
        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT
    ),
    "capitalised_penalties_received_account": (
        accounts.INTERNAL_CAPITALISED_PENALTIES_RECEIVED_ACCOUNT
    ),
    "interest_received_account": accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT,
    "penalty_interest_received_account": accounts.INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT,
    "late_repayment_fee_income_account": accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
    "overpayment_fee_income_account": accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT,
    "overpayment_fee_rate": "0.05",
    "upfront_fee_income_account": accounts.INTERNAL_UPFRONT_FEE_INCOME_ACCOUNT,
    "accrual_precision": "5",
    "fulfillment_precision": "2",
    "amortisation_method": "declining_principal",
    "capitalise_no_repayment_accrued_interest": "no_capitalisation",
    "overpayment_impact_preference": "reduce_term",
    "accrue_interest_hour": "0",
    "accrue_interest_minute": "0",
    "accrue_interest_second": "1",
    "check_overdue_hour": "0",
    "check_overdue_minute": "0",
    "check_overdue_second": "2",
    "check_delinquency_hour": "0",
    "check_delinquency_minute": "0",
    "check_delinquency_second": "2",
    "repayment_hour": "0",
    "repayment_minute": "1",
    "repayment_second": "0",
}

loan_3_instance_params = {
    "fixed_interest_rate": "0.031",
    "fixed_interest_loan": "True",
    "total_term": "12",
    "upfront_fee": "0",
    "amortise_upfront_fee": "True",
    "principal": "30000",
    "repayment_day": "20",
    "deposit_account": accounts.DEPOSIT_ACCOUNT,
    "variable_rate_adjustment": "0.00",
    "loan_start_date": str(default_simulation_start_date.date()),
    "repayment_holiday_impact_preference": "increase_emi",
    "capitalise_late_repayment_fee": "False",
    "interest_accrual_rest_type": "daily",
}


class LoanFixedTest(SimulationTestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_filepath = contract_files.CONTRACT_FILE
        cls.input_data_filename = sim_files.INPUT_DATA
        cls.expected_output_filename = sim_files.EXPECTED_OUTPUT
        cls.linked_contract_modules = [
            ContractModuleConfig(alias, file_path)
            for (alias, file_path) in contract_files.CONTRACT_MODULES_ALIAS_FILE_MAP.items()
        ]
        super().setUpClass()

    def _get_contract_config(
        self,
        contract_version_id=None,
        instance_params=None,
        template_params=None,
    ):
        contract_config = ContractConfig(
            contract_file_path=contract_files.CONTRACT_FILE,
            template_params=template_params or self.default_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or self.default_instance_params,
                    account_id_base=accounts.LOAN_ACCOUNT,
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
                template_params=template_params,
                instance_params=instance_params,
            ),
            internal_accounts=internal_accounts,
            debug=debug,
        )

    def test_monthly_due_for_fixed_rate_with_full_repayment(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=1, day=29, minute=1, tzinfo=timezone.utc)

        main_account = account_to_simulate(
            timestamp=start,
            account_id=accounts.LOAN_ACCOUNT,
            instance_params=loan_3_instance_params,
            template_params=loan_1_template_params,
            contract_file_path=self.contract_filepath,
        )
        events = []

        events.extend(
            _set_up_deposit_events(
                1,
                loan_3_first_month_payment,
                repayment_day,
                payment_hour,
                start_year,
                2,
            )
        )
        events.extend(
            _set_up_deposit_events(11, loan_3_EMI, repayment_day, payment_hour, start_year, 3)
        )

        res = self.client.simulate_smart_contract(
            account_creation_events=[main_account],
            contract_config=self._get_contract_config(
                contract_version_id=main_account["smart_contract_version_id"],
                instance_params=loan_1_instance_params,
                template_params=loan_1_template_params,
            ),
            internal_account_ids=accounts.default_internal_accounts,
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
            expected_balances[accounts.LOAN_ACCOUNT][repayment_date + relativedelta(months=i)] = [
                (dimensions.PRINCIPAL, values[0]),
                (dimensions.PRINCIPAL_DUE, values[1]),
                (dimensions.INTEREST_DUE, values[2]),
            ]

        self.check_balances(expected_balances=expected_balances, actual_balances=get_balances(res))

    def test_monthly_due_for_fixed_rate(self):
        """
        Test for Fixed Rate Interest.
        """
        start = default_simulation_start_date
        end = datetime(year=2021, month=1, day=21, minute=1, tzinfo=timezone.utc)

        loan_account = account_to_simulate(
            timestamp=start,
            account_id=accounts.LOAN_ACCOUNT,
            instance_params=loan_2_instance_params,
            template_params=loan_2_template_params,
            contract_file_path=self.contract_filepath,
        )

        repayment_day = int(loan_2_instance_params["repayment_day"])
        # first repayment includes 9 additional days interest
        # loan start date = 20200111 and repayment day = 20
        # daliy rate (25.48) * additional days (9) = 229.32
        repayment_1 = _set_up_deposit_events(
            1, loan_2_first_month_payment, repayment_day, payment_hour, start_year, 2
        )
        repayment_2 = _set_up_deposit_events(
            11, loan_2_EMI, repayment_day, payment_hour, start_year, 3
        )
        events = list(chain.from_iterable([repayment_1, repayment_2]))

        res = self.client.simulate_smart_contract(
            account_creation_events=[loan_account],
            contract_config=self._get_contract_config(
                contract_version_id=loan_account["smart_contract_version_id"],
                instance_params=loan_2_instance_params,
                template_params=loan_2_template_params,
            ),
            internal_account_ids=accounts.default_internal_accounts,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
        )

        repayment_date = datetime(
            year=start_year, month=2, day=repayment_day, hour=1, tzinfo=timezone.utc
        )
        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        for i, values in enumerate(self.expected_output["monthly_due_fixed"]):
            expected_balances[accounts.LOAN_ACCOUNT][repayment_date + relativedelta(months=i)] = [
                (dimensions.PRINCIPAL_DUE, values[0]),
                (dimensions.INTEREST_DUE, values[1]),
            ]

        self.check_balances(expected_balances, get_balances(res))

    def test_monthly_due_for_fixed_rate_with_one_overpayment(self):
        """
        Test for Fixed Rate Interest with an overpayment in month 3.
        """
        start = default_simulation_start_date
        end = datetime(year=2021, month=1, day=21, minute=1, tzinfo=timezone.utc)

        loan_account = account_to_simulate(
            timestamp=start,
            account_id=accounts.LOAN_ACCOUNT,
            instance_params=loan_2_instance_params,
            template_params=loan_2_template_params,
            contract_file_path=self.contract_filepath,
        )

        repayment_day = int(loan_2_instance_params["repayment_day"])
        # first repayment includes 9 additional days interest
        # loan start date = 20200111 and repayment day = 20
        # daliy rate (25.48) * additional days (9) = 229.32
        repayment_1 = _set_up_deposit_events(
            1, loan_2_first_month_payment, repayment_day, payment_hour, start_year, 2
        )
        # second repayment includes overpayment
        # overpayment: 10,526.32, fee: 526.32, overpayment - fee: 10,000
        repayment_2 = _set_up_deposit_events(
            1,
            str(Decimal(loan_2_EMI) + Decimal("10000") + Decimal("526.32")),
            repayment_day,
            1,
            start_year,
            3,
        )
        repayment_3 = _set_up_deposit_events(
            10, loan_2_EMI, repayment_day, payment_hour, start_year, 4
        )
        events = list(chain.from_iterable([repayment_1, repayment_2, repayment_3]))

        res = self.client.simulate_smart_contract(
            account_creation_events=[loan_account],
            contract_config=self._get_contract_config(
                contract_version_id=loan_account["smart_contract_version_id"],
                instance_params=loan_2_instance_params,
                template_params=loan_2_template_params,
            ),
            internal_account_ids=accounts.default_internal_accounts,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
        )

        repayment_date = datetime(
            year=start_year, month=2, day=repayment_day, hour=1, tzinfo=timezone.utc
        )
        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        for i, values in enumerate(self.expected_output["monthly_due_fixed_with_one_overpayment"]):
            expected_balances[accounts.LOAN_ACCOUNT][repayment_date + relativedelta(months=i)] = [
                (dimensions.PRINCIPAL_DUE, values[0]),
                (dimensions.INTEREST_DUE, values[1]),
            ]

        expected_balances[accounts.LOAN_ACCOUNT][end] = [(dimensions.OVERPAYMENT, "-10000")]
        expected_balances[accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT][end] = [
            (dimensions.DEFAULT, "526.32")
        ]

        self.check_balances(expected_balances, get_balances(res))

    def test_monthly_due_for_fixed_rate_with_regular_overpayment(self):
        """
        Test for Fixed Rate Interest with a regular overpayment every month.
        """
        start = default_simulation_start_date
        end = datetime(year=2021, month=11, day=21, minute=1, tzinfo=timezone.utc)

        loan_account = account_to_simulate(
            timestamp=start,
            account_id=accounts.LOAN_ACCOUNT,
            instance_params=loan_3_instance_params,
            template_params=loan_1_template_params,
            contract_file_path=self.contract_filepath,
        )

        # overpayment: 1,052.63, fee: 52.63, overpayment - fee: 1,000
        first_payment_event = _set_up_deposit_events(
            1,
            str(Decimal(loan_3_first_month_payment) + Decimal("1000") + Decimal("52.63")),
            20,
            payment_hour,
            start_year,
            2,
        )
        repayment_with_overpayment = str(Decimal(loan_3_EMI) + Decimal("1000") + Decimal("52.63"))
        events = first_payment_event + _set_up_deposit_events(
            7, repayment_with_overpayment, 20, payment_hour, start_year, 3
        )

        res = self.client.simulate_smart_contract(
            account_creation_events=[loan_account],
            contract_config=self._get_contract_config(
                contract_version_id=loan_account["smart_contract_version_id"],
                instance_params=loan_1_instance_params,
                template_params=loan_1_template_params,
            ),
            internal_account_ids=accounts.default_internal_accounts,
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
            expected_balances[accounts.LOAN_ACCOUNT][repayment_date + relativedelta(months=i)] = [
                (dimensions.PRINCIPAL_DUE, values[0]),
                (dimensions.INTEREST_DUE, values[1]),
            ]

        # 8 overpayments of 1,000 each (not including fee) = total overpayment 41,000
        # total overpayment fees = 8 * 52.63 = 421.04
        expected_balances[accounts.LOAN_ACCOUNT][end] = [(dimensions.OVERPAYMENT, "-8000")]
        expected_balances[accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT][end] = [
            (dimensions.DEFAULT, "421.04")
        ]

        self.check_balances(expected_balances=expected_balances, actual_balances=get_balances(res))

    def test_monthly_due_for_fixed_rate_with_accrue_on_due_principal(self):
        start = default_simulation_start_date
        end = datetime(year=2024, month=2, day=28, minute=1, tzinfo=timezone.utc)
        template_params = loan_1_template_params.copy()
        template_params["accrue_interest_on_due_principal"] = "True"

        before_first_repayment_date = datetime(
            year=start_year,
            month=2,
            day=20,
            hour=0,
            minute=0,
            second=30,
            tzinfo=timezone.utc,
        )
        after_first_repayment_date = before_first_repayment_date + relativedelta(minute=1)

        first_payment_date = datetime(
            year=start_year,
            month=2,
            day=repayment_day,
            hour=payment_hour,
            tzinfo=timezone.utc,
        )
        before_first_payment_date = first_payment_date - relativedelta(minutes=1)
        after_first_payment_date = first_payment_date + relativedelta(minutes=1)

        before_final_repayment_date = datetime(
            year=2024,
            month=1,
            day=20,
            hour=0,
            minute=0,
            second=30,
            tzinfo=timezone.utc,
        )
        after_final_repayment_date = before_final_repayment_date + relativedelta(minutes=1)
        final_payment_amount = "6869.86"
        final_payment_date = datetime(
            year=2024,
            month=1,
            day=repayment_day,
            hour=payment_hour,
            tzinfo=timezone.utc,
        )
        before_final_payment_date = final_payment_date - relativedelta(minutes=1)
        after_final_payment_date = final_payment_date + relativedelta(minutes=1)

        before_additional_repayment_date = datetime(
            year=2024,
            month=2,
            day=20,
            hour=0,
            minute=0,
            second=30,
            tzinfo=timezone.utc,
        )
        after_additional_repayment_date = before_additional_repayment_date + relativedelta(
            minutes=1
        )

        sub_tests = [
            SubTest(
                description="check balances first repayment date",
                expected_balances_at_ts={
                    start: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "300000"),
                        ]
                    },
                    # 0.031/365 * 300000 = 25.47945
                    # 25.47945 * 40 = 1019.17800
                    before_first_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "300000"),
                            (dimensions.ACCRUED_INTEREST, "1019.17800"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "1019.17800"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1019.17800"),
                        ],
                    },
                    after_first_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "294136.29"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_DUE, "5863.71"),
                            (dimensions.INTEREST_DUE, "1019.18"),
                            (dimensions.EMI_ADDRESS, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1019.18"),
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances after first payment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount=loan_1_first_month_payment,
                        event_datetime=first_payment_date,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    # 0.031/365 * (294136.29+5863.71) = 25.47945
                    # 25.47945 * 8 = 203.8356
                    before_first_payment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "294136.29"),
                            (dimensions.ACCRUED_INTEREST, "203.8356"),
                            (dimensions.PRINCIPAL_DUE, "5863.71"),
                            (dimensions.INTEREST_DUE, "1019.18"),
                            (dimensions.EMI_ADDRESS, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "203.83560"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1223.01560"),
                        ],
                    },
                    after_first_payment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "294136.29"),
                            (dimensions.ACCRUED_INTEREST, "203.8356"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI_ADDRESS, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "203.83560"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1223.01560"),
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances second repayment date",
                expected_balances_at_ts={
                    before_first_repayment_date
                    + relativedelta(months=1): {
                        # 0.031/365 * 294136.29 = 24.98144
                        # 203.8356 + 24.98144 * 21 = 203.8356 + 524.61024 = 728.44584
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "294136.29"),
                            (dimensions.ACCRUED_INTEREST, "728.44584"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI_ADDRESS, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "728.44584"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1747.62584"),
                        ],
                    },
                    after_first_repayment_date
                    + relativedelta(months=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "288211.17"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_DUE, "5925.12"),
                            (dimensions.INTEREST_DUE, "728.45"),
                            (dimensions.EMI_ADDRESS, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1747.63"),
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances after second payment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount=loan_1_EMI,
                        event_datetime=first_payment_date + relativedelta(months=1),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    # 0.031/365 * (288211.17+5925.12) = 24.98144
                    # 24.98144 * 8 = 199.85152
                    before_first_payment_date
                    + relativedelta(months=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "288211.17"),
                            (dimensions.ACCRUED_INTEREST, "199.85152"),
                            (dimensions.PRINCIPAL_DUE, "5925.12"),
                            (dimensions.INTEREST_DUE, "728.45"),
                            (dimensions.EMI_ADDRESS, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "199.85152"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1947.48152"),
                        ],
                    },
                    after_first_payment_date
                    + relativedelta(months=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "288211.17"),
                            (dimensions.ACCRUED_INTEREST, "199.85152"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI_ADDRESS, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "199.85152"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1947.48152"),
                        ],
                    },
                },
            ),
            SubTest(
                description="payments",
                events=_set_up_deposit_events(
                    num_payments=45,
                    repayment_amount=loan_1_EMI,
                    repayment_day=repayment_day,
                    repayment_hour=payment_hour,
                    start_year=2020,
                    start_month=4,
                ),
            ),
            SubTest(
                description="check balances final repayment date",
                expected_balances_at_ts={
                    before_final_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "6847.34"),
                            (dimensions.ACCRUED_INTEREST, "22.52253"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI_ADDRESS, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ]
                    },
                    after_final_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_DUE, "6847.34"),
                            (dimensions.INTEREST_DUE, "22.52"),
                            (dimensions.EMI_ADDRESS, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ]
                    },
                },
            ),
            SubTest(
                description="check balances final payment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount=final_payment_amount,
                        event_datetime=final_payment_date,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    # 0.031/365 * (6847.34) = 0.58155
                    # 0.58155 * 8 = 4.65240
                    before_final_payment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.ACCRUED_INTEREST, "4.65240"),
                            (dimensions.PRINCIPAL_DUE, "6847.34"),
                            (dimensions.INTEREST_DUE, "22.52"),
                            (dimensions.EMI_ADDRESS, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ]
                    },
                    after_final_payment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.ACCRUED_INTEREST, "4.65240"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI_ADDRESS, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=final_payment_date,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="next_repayment_date",
                        value="2024-02-20",
                    ),
                ],
            ),
            SubTest(
                description="check balances additional repayment date",
                expected_balances_at_ts={
                    before_additional_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.ACCRUED_INTEREST, "4.65240"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI_ADDRESS, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ]
                    },
                    after_additional_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "4.65"),
                            (dimensions.EMI_ADDRESS, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "19821.62"),
                        ],
                    },
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="LOAN_REPAYMENT_NOTIFICATION",
                        account_id=accounts.LOAN_ACCOUNT,
                        run_times=[
                            before_additional_repayment_date + relativedelta(minute=1, second=0)
                        ],
                        contexts=[
                            {
                                "account_id": accounts.LOAN_ACCOUNT,
                                "repayment_amount": "4.65",
                                "overdue_date": "2024-03-01",
                            }
                        ],
                        count=49,
                    )
                ],
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=loan_1_instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

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

        template_params = loan_1_template_params.copy()
        template_params["overpayment_impact_preference"] = "reduce_emi"

        instance_params = loan_1_instance_params.copy()
        instance_params["total_term"] = "12"
        instance_params["principal"] = "3000"

        sub_tests = [
            SubTest(
                description="first month emi",
                expected_balances_at_ts={
                    first_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "246.32"),
                            (dimensions.INTEREST_DUE, "10.19"),
                            (dimensions.EMI_ADDRESS, "254.22"),
                            (dimensions.OVERPAYMENT, "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="regular overpayments of 100",
                # overpayment: 105.26, fee: 5.26, overpayment - fee: 100
                events=[
                    create_inbound_hard_settlement_instruction(
                        # emi plus additional interest from account creation
                        str(Decimal("356.51") + Decimal("5.26")),
                        first_repayment_date + relativedelta(hours=5),
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("345.00") + Decimal("5.26")),
                        second_repayment_date + relativedelta(hours=5),
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("334.82") + Decimal("5.26")),
                        third_repayment_date + relativedelta(hours=5),
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("323.58") + Decimal("5.26")),
                        fourth_repayment_date + relativedelta(hours=5),
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("310.93") + Decimal("5.26")),
                        fifth_repayment_date + relativedelta(hours=5),
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("296.51") + Decimal("5.26")),
                        sixth_repayment_date + relativedelta(hours=5),
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("279.68") + Decimal("5.26")),
                        seventh_repayment_date + relativedelta(hours=5),
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("259.53") + Decimal("5.26")),
                        eighth_repayment_date + relativedelta(hours=5),
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("234.38") + Decimal("5.26")),
                        nineth_repayment_date + relativedelta(hours=5),
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("200.87") + Decimal("5.26")),
                        tenth_repayment_date + relativedelta(hours=5),
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        # only paying the EMI amount instead of ending the loan early
                        "50.69",
                        eleventh_repayment_date + relativedelta(hours=5),
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        # final payment of remaining loan + overpayment charge
                        "50.68",
                        final_repayment_date + relativedelta(hours=5),
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    second_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "238.46"),
                            (dimensions.INTEREST_DUE, "6.54"),
                            (dimensions.EMI_ADDRESS, "245.00"),
                            (dimensions.OVERPAYMENT, "-100"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "5.26")
                        ],
                    },
                    third_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "228.72"),
                            (dimensions.INTEREST_DUE, "6.10"),
                            (dimensions.EMI_ADDRESS, "234.82"),
                            (dimensions.OVERPAYMENT, "-200"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "10.52")
                        ],
                    },
                    fourth_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "218.52"),
                            (dimensions.INTEREST_DUE, "5.06"),
                            (dimensions.EMI_ADDRESS, "223.58"),
                            (dimensions.OVERPAYMENT, "-300"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "15.78")
                        ],
                    },
                    fifth_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "206.54"),
                            (dimensions.INTEREST_DUE, "4.39"),
                            (dimensions.EMI_ADDRESS, "210.93"),
                            (dimensions.OVERPAYMENT, "-400"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "21.04")
                        ],
                    },
                    sixth_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "193.04"),
                            (dimensions.INTEREST_DUE, "3.47"),
                            (dimensions.EMI_ADDRESS, "196.51"),
                            (dimensions.OVERPAYMENT, "-500"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "26.30")
                        ],
                    },
                    seventh_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "176.87"),
                            (dimensions.INTEREST_DUE, "2.81"),
                            (dimensions.EMI_ADDRESS, "179.68"),
                            (dimensions.OVERPAYMENT, "-600"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "31.56")
                        ],
                    },
                    eighth_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "157.45"),
                            (dimensions.INTEREST_DUE, "2.08"),
                            (dimensions.EMI_ADDRESS, "159.53"),
                            (dimensions.OVERPAYMENT, "-700"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "36.82")
                        ],
                    },
                    nineth_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "133.02"),
                            (dimensions.INTEREST_DUE, "1.36"),
                            (dimensions.EMI_ADDRESS, "134.38"),
                            (dimensions.OVERPAYMENT, "-800"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "42.08")
                        ],
                    },
                    tenth_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "100.08"),
                            (dimensions.INTEREST_DUE, "0.79"),
                            (dimensions.EMI_ADDRESS, "100.87"),
                            (dimensions.OVERPAYMENT, "-900"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "47.34")
                        ],
                    },
                    eleventh_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "50.43"),
                            (dimensions.INTEREST_DUE, "0.26"),
                            (dimensions.EMI_ADDRESS, "50.69"),
                            (dimensions.OVERPAYMENT, "-1000"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "52.60")
                        ],
                    },
                    final_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            # last payment rounds to remaining principal
                            # instead of using stored EMI
                            # hence total due is 50.68 instead of equal to EMI 50.69
                            (dimensions.PRINCIPAL_DUE, "50.55"),
                            (dimensions.INTEREST_DUE, "0.13"),
                            (dimensions.EMI_ADDRESS, "50.69"),
                            (dimensions.OVERPAYMENT, "-1000"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            # total overpayment = 1000
                            (dimensions.PENALTIES, "0"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "52.60")
                        ],
                    },
                    final_repayment_date
                    + relativedelta(hours=6): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI_ADDRESS, "50.69"),
                            (dimensions.OVERPAYMENT, "-1000"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.PRINCIPAL, "1014.36"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "-14.36"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "52.60")
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="11",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="10",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=third_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="9",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=fourth_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="8",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=fifth_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="7",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=sixth_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="6",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=seventh_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="5",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=eighth_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="4",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=nineth_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="3",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=tenth_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="2",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=eleventh_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="1",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=final_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="0",
                    ),
                ],
                expected_workflows=[
                    ExpectedWorkflow(
                        run_times=[final_repayment_date + relativedelta(hours=5)],
                        workflow_definition_id="LOAN_CLOSURE",
                        account_id=accounts.LOAN_ACCOUNT,
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
            internal_accounts=accounts.default_internal_accounts,
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

        template_params = loan_1_template_params.copy()
        template_params["overpayment_impact_preference"] = "reduce_emi"

        instance_params = loan_1_instance_params.copy()
        instance_params["total_term"] = "12"
        instance_params["principal"] = "3000"

        sub_tests = [
            SubTest(
                description="first month emi",
                expected_balances_at_ts={
                    first_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "246.32"),
                            (dimensions.INTEREST_DUE, "10.19"),
                            (dimensions.EMI_ADDRESS, "254.22"),
                            (dimensions.OVERPAYMENT, "0"),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
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
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "254.22",
                        second_repayment_date + relativedelta(hours=5),
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "254.22",
                        third_repayment_date + relativedelta(hours=5),
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    second_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "247.44"),
                            (dimensions.INTEREST_DUE, "6.78"),
                            (dimensions.EMI_ADDRESS, "254.22"),
                        ]
                    },
                    third_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "247.62"),
                            (dimensions.INTEREST_DUE, "6.60"),
                            (dimensions.EMI_ADDRESS, "254.22"),
                        ]
                    },
                    fourth_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "248.47"),
                            (dimensions.INTEREST_DUE, "5.75"),
                            (dimensions.EMI_ADDRESS, "254.22"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=second_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="10",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=third_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="9",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=fourth_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="8",
                    ),
                ],
            ),
            SubTest(
                description="single overpayments of 250",
                # overpayment: 263.16, fee: 13.16, overpayment - fee: 250
                events=[
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("504.22") + Decimal("13.16")),
                        fourth_repayment_date + relativedelta(hours=5),
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    fifth_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "217.95"),
                            (dimensions.INTEREST_DUE, "4.63"),
                            (dimensions.EMI_ADDRESS, "222.58"),
                            (dimensions.OVERPAYMENT, "-250"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=fifth_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
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
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "218.65"),
                            (dimensions.INTEREST_DUE, "3.93"),
                            (dimensions.EMI_ADDRESS, "222.58"),
                            (dimensions.OVERPAYMENT, "-250"),
                        ]
                    },
                    seventh_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "219.10"),
                            (dimensions.INTEREST_DUE, "3.48"),
                            (dimensions.EMI_ADDRESS, "222.58"),
                            (dimensions.OVERPAYMENT, "-250"),
                        ]
                    },
                    eighth_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "219.67"),
                            (dimensions.INTEREST_DUE, "2.91"),
                            (dimensions.EMI_ADDRESS, "222.58"),
                            (dimensions.OVERPAYMENT, "-250"),
                        ]
                    },
                    nineth_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "220.33"),
                            (dimensions.INTEREST_DUE, "2.25"),
                            (dimensions.EMI_ADDRESS, "222.58"),
                            (dimensions.OVERPAYMENT, "-250"),
                        ]
                    },
                    tenth_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "220.83"),
                            (dimensions.INTEREST_DUE, "1.75"),
                            (dimensions.EMI_ADDRESS, "222.58"),
                            (dimensions.OVERPAYMENT, "-250"),
                        ]
                    },
                    eleventh_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "221.45"),
                            (dimensions.INTEREST_DUE, "1.13"),
                            (dimensions.EMI_ADDRESS, "222.58"),
                            (dimensions.OVERPAYMENT, "-250"),
                        ]
                    },
                    final_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "222.17"),
                            (dimensions.INTEREST_DUE, "0.58"),
                            (dimensions.EMI_ADDRESS, "222.58"),
                            (dimensions.OVERPAYMENT, "-250"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=sixth_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="6",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=seventh_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="5",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=eighth_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="4",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=nineth_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="3",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=tenth_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="2",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=eleventh_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="1",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=final_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
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
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_workflows=[
                    ExpectedWorkflow(
                        run_times=[final_repayment_date + relativedelta(hours=5)],
                        workflow_definition_id="LOAN_CLOSURE",
                        account_id=accounts.LOAN_ACCOUNT,
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
            internal_accounts=accounts.default_internal_accounts,
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
                target_account_id=accounts.LOAN_ACCOUNT,
                amount=repayment_amount,
                event_datetime=event_date,
                internal_account_id=accounts.DEPOSIT_ACCOUNT,
            )
        )

    return events
