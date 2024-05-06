# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone
from decimal import Decimal
import sys
import unittest

# third party
from dateutil.relativedelta import relativedelta

# common
import inception_sdk.test_framework.common.constants as constants
from inception_sdk.test_framework.contracts.simulation.helper import (
    account_to_simulate,
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_template_parameter_change_event,
    create_custom_instruction,
    create_inbound_authorisation_instruction,
    create_release_event,
    create_settlement_event,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    SimulationTestCase,
    get_balances,
    get_postings,
    get_processed_scheduled_events,
)
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    ExpectedSchedule,
    ExpectedRejection,
    ExpectedWorkflow,
    ExpectedDerivedParameter,
    SimulationTestScenario,
    SubTest,
    ContractConfig,
    ContractModuleConfig,
    AccountConfig,
)

# Loan specific
import library.loan.constants.accounts as accounts
import library.loan.constants.addresses as address
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
loan_1_EMI = "2910.69"
loan_1_expected_remaining_balance = "-46.67"
loan_2_first_month_payment = str(Decimal("2910.69") + Decimal("229.32"))
loan_2_EMI = "2910.69"
loan_2_expected_fee = "35.0"

loan_1_instance_params = {
    "fixed_interest_rate": "0.129971",
    "fixed_interest_loan": "False",
    "total_term": "120",
    "upfront_fee": "0",
    "amortise_upfront_fee": "True",
    "principal": "300000",
    "repayment_day": "12",
    "deposit_account": accounts.DEPOSIT_ACCOUNT,
    "variable_rate_adjustment": "-0.001",
    "loan_start_date": str(default_simulation_start_date.date()),
    "repayment_holiday_impact_preference": "increase_emi",
    "capitalise_late_repayment_fee": "False",
    "interest_accrual_rest_type": "daily",
}

loan_1_template_params = {
    "variable_interest_rate": "0.032",
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


class LoanTest(SimulationTestCase):
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

    def test_monthly_rest_interest_accrual_with_repayment_day_change(self):
        # Change repayment day after 1st repayment and ensure interest accrual continues until
        # the new repayment day. Ensure that overpayments aren't included in interest accrual
        # until the following repayment day.
        # Daily interest for 1st repayment period = 25.47945 (Remaining principal 300000)
        # Total interest for 1st repayment period = 32 days = 815.3424
        # Daily interest for 2nd repayment period = 21.26508 (Remaining principal 250379.17 )
        # Total interest for 2nd repayment period = 35 days = 744.2778

        start = default_simulation_start_date
        end = start + relativedelta(months=3, days=8, minutes=2)
        instance_params = loan_1_instance_params.copy()
        instance_params["interest_accrual_rest_type"] = constants.MONTHLY

        sub_tests = [
            SubTest(
                description="5 days interest accrual on full starting principal",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=1): {
                        accounts.LOAN_ACCOUNT: [(dimensions.ACCRUED_INTEREST, "25.47945")]
                    },
                    start
                    + relativedelta(days=2, seconds=1): {
                        accounts.LOAN_ACCOUNT: [(dimensions.ACCRUED_INTEREST, "50.9589")]
                    },
                    start
                    + relativedelta(days=3, seconds=1): {
                        accounts.LOAN_ACCOUNT: [(dimensions.ACCRUED_INTEREST, "76.43835")]
                    },
                    start
                    + relativedelta(days=4, seconds=1): {
                        accounts.LOAN_ACCOUNT: [(dimensions.ACCRUED_INTEREST, "101.9178")]
                    },
                    start
                    + relativedelta(days=5, seconds=1): {
                        accounts.LOAN_ACCOUNT: [(dimensions.ACCRUED_INTEREST, "127.39725")]
                    },
                },
            ),
            SubTest(
                description="penalty fee and 4 days penalty accrual on current overdue balances",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=2, days=17, minutes=2): {
                        accounts.LOAN_ACCOUNT: [(dimensions.PENALTIES, "15")]
                    },
                    start
                    + relativedelta(months=2, days=18, seconds=2): {
                        accounts.LOAN_ACCOUNT: [(dimensions.PENALTIES, "17.16")]
                    },
                    start
                    + relativedelta(months=2, days=19, seconds=2): {
                        accounts.LOAN_ACCOUNT: [(dimensions.PENALTIES, "19.32")]
                    },
                    start
                    + relativedelta(months=2, days=20, seconds=2): {
                        accounts.LOAN_ACCOUNT: [(dimensions.PENALTIES, "21.48")]
                    },
                    start
                    + relativedelta(months=2, days=21, seconds=2): {
                        accounts.LOAN_ACCOUNT: [(dimensions.PENALTIES, "23.64")]
                    },
                },
            ),
            SubTest(
                description="monthly rest to continue accrual until new repayment date",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="50000",
                        event_datetime=start + relativedelta(days=2),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="50000",
                        event_datetime=start + relativedelta(months=1, days=3),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(months=1, days=3),
                        account_id=accounts.LOAN_ACCOUNT,
                        repayment_day="18",
                    ),
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="50000",
                        event_datetime=start + relativedelta(months=1, days=4),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, days=1, minutes=2): {
                        accounts.LOAN_ACCOUNT: [(dimensions.INTEREST_DUE, "815.34")]
                    },
                    start
                    + relativedelta(months=2, days=7, minutes=2): {
                        accounts.LOAN_ACCOUNT: [(dimensions.INTEREST_DUE, "744.28")]
                    },
                    start
                    + relativedelta(months=3, days=7, minutes=2): {
                        accounts.LOAN_ACCOUNT: [(dimensions.INTEREST_DUE, "410.73")]
                    },
                    start
                    + relativedelta(months=3, days=8, minutes=2): {
                        accounts.LOAN_ACCOUNT: [(dimensions.ACCRUED_INTEREST, "13.03717")]
                    },
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=loan_1_template_params,
            instance_params=instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_account_opening_without_upfront_fee(self):
        start = default_simulation_start_date
        end = default_simulation_start_date + relativedelta(minutes=1)

        instance_params = loan_1_instance_params.copy()
        template_params = loan_1_template_params.copy()
        template_params["overpayment_fee_rate"] = "0"
        instance_params["principal"] = "10000"
        instance_params["upfront_fee"] = "0"
        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "10000"),
                        ],
                        accounts.INTERNAL_UPFRONT_FEE_INCOME_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="120",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="97.02",
                    ),
                ],
            ),
            SubTest(
                description="check overpayment near start of loan reduces remaining_term",
                # overpayment: 98, fee: 0
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="98",
                        event_datetime=end - relativedelta(seconds=1),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.OVERPAYMENT, "-98"),
                            (dimensions.PRINCIPAL, "10000"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=end,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="119",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=end,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="97.02",
                    ),
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

    def test_account_opening_with_upfront_fee_added(self):
        start = default_simulation_start_date
        end = default_simulation_start_date + relativedelta(minutes=1)

        instance_params = loan_1_instance_params.copy()
        template_params = loan_1_template_params.copy()
        instance_params["principal"] = "10000"
        instance_params["upfront_fee"] = "500"
        instance_params["amortise_upfront_fee"] = "True"
        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "10500"),
                        ],
                        accounts.INTERNAL_UPFRONT_FEE_INCOME_ACCOUNT: [(dimensions.DEFAULT, "500")],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, "10000")],
                    }
                },
            )
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

    def test_account_opening_with_upfront_fee_subtracted(self):
        start = default_simulation_start_date
        end = default_simulation_start_date + relativedelta(minutes=1)

        instance_params = loan_1_instance_params.copy()
        template_params = loan_1_template_params.copy()
        instance_params["principal"] = "10000"
        instance_params["upfront_fee"] = "500"
        instance_params["amortise_upfront_fee"] = "False"
        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "10000"),
                        ],
                        accounts.INTERNAL_UPFRONT_FEE_INCOME_ACCOUNT: [(dimensions.DEFAULT, "500")],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, "9500")],
                    }
                },
            )
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

    def test_regular_events(self):
        start = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)

        first_repayment_time = datetime(
            year=2021, month=2, day=12, hour=0, minute=1, second=0, tzinfo=timezone.utc
        )
        before_first_repayment = first_repayment_time - relativedelta(seconds=1)
        after_first_repayment = first_repayment_time + relativedelta(minutes=1)
        after_first_deposit = first_repayment_time + relativedelta(hours=2)

        second_repayment_time = datetime(
            year=2021, month=3, day=12, hour=0, minute=1, second=0, tzinfo=timezone.utc
        )
        before_second_repayment = second_repayment_time - relativedelta(seconds=1)
        after_second_repayment = second_repayment_time + relativedelta(minutes=1)
        after_second_deposit = second_repayment_time + relativedelta(hours=2)

        third_overdue_check = datetime(
            year=2021, month=4, day=12, hour=0, minute=0, second=2, tzinfo=timezone.utc
        )
        after_third_overdue_check = third_overdue_check + relativedelta(seconds=10)
        third_repayment_time = datetime(
            year=2021, month=4, day=12, hour=0, minute=1, second=0, tzinfo=timezone.utc
        )
        after_third_repayment = third_repayment_time + relativedelta(minutes=1)
        after_third_deposit = third_repayment_time + relativedelta(hours=2)

        fourth_repayment_time = datetime(
            year=2021, month=5, day=12, hour=0, minute=1, second=0, tzinfo=timezone.utc
        )
        before_fourth_repayment = fourth_repayment_time - relativedelta(seconds=1)
        after_fourth_repayment = fourth_repayment_time + relativedelta(minutes=1)

        end = datetime(year=2021, month=5, day=31, tzinfo=timezone.utc)

        instance_params = loan_1_instance_params.copy()
        instance_params["total_term"] = "10"
        instance_params["principal"] = "1000"
        instance_params["fixed_interest_rate"] = "0.01"
        instance_params["fixed_interest_loan"] = "True"
        instance_params["loan_start_date"] = str(start.date())

        template_params = loan_1_template_params.copy()
        template_params["variable_interest_rate"] = "0"
        template_params["capitalise_penalty_interest"] = "True"

        sub_tests = [
            SubTest(
                description="activation",
                expected_balances_at_ts={
                    start: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "1000"),
                        ]
                    },
                },
            ),
            SubTest(
                description="first scheduled repayment with overpayment",
                events=_set_up_deposit_events(1, "101", 12, 1, 2021, 2),
                expected_balances_at_ts={
                    # accrued_interest = daily_interest_rate * days_since_start_of_loan * principal
                    #                  = 0.01 / 365 * 42 * 1000
                    before_first_repayment: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "1.1508"),
                            (dimensions.ACCRUED_INTEREST, "1.1508"),
                        ]
                    },
                    # EMI and principal_due get calculated according to formula
                    # accrued_interest gets transferred to interest_due
                    after_first_repayment: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "900.39"),
                            (dimensions.PRINCIPAL_DUE, "99.61"),
                            (dimensions.INTEREST_DUE, "1.15"),
                            (dimensions.EMI_ADDRESS, "100.46"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                        ]
                    },
                    # deposit of 101 repays the principal_due, interest_due and the remainder gets
                    # put in the overpayment address, after the overpayment fee of 5% is also paid
                    after_first_deposit: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "900.39"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI_ADDRESS, "100.46"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.OVERPAYMENT, "-0.23"),
                        ]
                    },
                },
            ),
            SubTest(
                description="second scheduled repayment with underpayment sets overdue addresses",
                events=_set_up_deposit_events(1, "50", 12, 1, 2021, 3),
                expected_balances_at_ts={
                    # accrued_interest = 0.01 / 365 * 28 * 900.39
                    before_second_repayment: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "900.39"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI_ADDRESS, "100.46"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.69076"),
                            (dimensions.ACCRUED_INTEREST, "0.69048"),
                            (dimensions.OVERPAYMENT, "-0.23"),
                        ]
                    },
                    after_second_repayment: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "800.62"),
                            (dimensions.PRINCIPAL_DUE, "99.77"),
                            (dimensions.INTEREST_DUE, "0.69"),
                            (dimensions.EMI_ADDRESS, "100.46"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.OVERPAYMENT, "-0.23"),
                        ]
                    },
                    # deposit of 50 only covers part of the principal_due
                    after_second_deposit: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "800.62"),
                            (dimensions.PRINCIPAL_DUE, "49.77"),
                            (dimensions.INTEREST_DUE, "0.69"),
                            (dimensions.EMI_ADDRESS, "100.46"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.OVERPAYMENT, "-0.23"),
                        ]
                    },
                    # the amounts left in the _due addresses get transferred to _overdue addresses
                    # a late repayment fee of 15 gets incurred in PENALTIES
                    after_third_overdue_check: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "800.62"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "49.77"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0.69"),
                            (dimensions.EMI_ADDRESS, "100.46"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.67983"),
                            (dimensions.ACCRUED_INTEREST, "0.67983"),
                            (dimensions.OVERPAYMENT, "-0.23"),
                            (dimensions.PENALTIES, "15"),
                        ]
                    },
                },
            ),
            SubTest(
                description="capitalisation and large overpayment",
                events=_set_up_deposit_events(1, "500", 12, 1, 2021, 4),
                expected_balances_at_ts={
                    # on the next scheduled repayment day, we can see interest from the penalties
                    # being accrued daily and transferred to PRINCIPAL_CAPITALISED_INTEREST (0.73)
                    after_third_repayment: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "700.84"),
                            (dimensions.PRINCIPAL_DUE, "99.78"),
                            (dimensions.PRINCIPAL_OVERDUE, "49.77"),
                            (dimensions.INTEREST_DUE, "0.68"),
                            (dimensions.INTEREST_OVERDUE, "0.69"),
                            (dimensions.EMI_ADDRESS, "100.46"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.OVERPAYMENT, "-0.23"),
                            (dimensions.PENALTIES, "15"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0.73"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                        ]
                    },
                    # third deposit of 500 pays off all overdue and due balances and also
                    # adds 317.38 to the overpayment balance
                    after_third_deposit: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "700.84"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.EMI_ADDRESS, "100.46"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.OVERPAYMENT, "-317.61"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0.73"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                        ]
                    },
                    # accrued expected interest is higher than the accrued interest, because the
                    # expected principal (700.84) is higher that the calculated one (700.84-317.61)
                    # due to the overpayment
                    before_fourth_repayment: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "700.84"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.EMI_ADDRESS, "100.46"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.5766"),
                            (dimensions.ACCRUED_INTEREST, "0.3156"),
                            (dimensions.OVERPAYMENT, "-317.61"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0.73"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                        ]
                    },
                    # the previous overpayment also resulted in 0.26 being stored in the
                    # EMI_PRINCIPAL_EXCESS balance since accrued expected interest was higher
                    # than the accrued interest
                    after_fourth_repayment: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "600.96"),
                            (dimensions.PRINCIPAL_DUE, "100.14"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0.32"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.EMI_ADDRESS, "100.46"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.OVERPAYMENT, "-317.61"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0.73"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "-0.26"),
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
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_top_up(self):
        start = datetime(year=2019, month=1, day=4, tzinfo=timezone.utc)
        repayment_date = datetime(year=2019, month=2, day=5, hour=9, tzinfo=timezone.utc)
        top_up_date = datetime(year=2019, month=4, day=7, hour=10, tzinfo=timezone.utc)
        top_up_date2 = datetime(year=2019, month=7, day=20, hour=10, tzinfo=timezone.utc)
        end = datetime(year=2019, month=9, day=5, hour=23, tzinfo=timezone.utc)

        instance_params = loan_1_instance_params.copy()
        instance_params["total_term"] = "12"
        instance_params["principal"] = "6500"
        instance_params["fixed_interest_rate"] = "0.045"
        instance_params["fixed_interest_loan"] = "True"
        instance_params["repayment_day"] = "5"
        instance_params["loan_start_date"] = str(start.date())

        before_top_up = top_up_date - relativedelta(days=1)
        after_top_up = top_up_date + relativedelta(hour=12)
        before_2nd_top_up = top_up_date2 - relativedelta(days=1)
        after_2nd_top_up = top_up_date2 + relativedelta(hour=12)

        sub_tests = [
            SubTest(
                description="first EMI due",
                events=_set_up_deposit_events(1, "555.76", 5, 10, 2019, 2),
                expected_balances_at_ts={
                    repayment_date
                    + relativedelta(hour=8): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "5969.88"),
                            (dimensions.PRINCIPAL_DUE, "530.12"),
                            (dimensions.INTEREST_DUE, "25.64"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                        ]
                    },
                    repayment_date
                    + relativedelta(hour=12): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "5969.88"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                        ]
                    },
                },
            ),
            SubTest(
                description="repayments before topup",
                events=_set_up_deposit_events(2, "554.96", 5, 10, 2019, 3),
                expected_balances_at_ts={
                    before_top_up: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "4901.34"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.EMI_ADDRESS, "554.96"),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_top_up,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="9",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_top_up,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="554.96",
                    ),
                ],
            ),
            SubTest(
                description="do topup 5000.66",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=top_up_date,
                        account_id=accounts.LOAN_ACCOUNT,
                        principal="9902",
                        fixed_interest_rate="0.06",
                        total_term="18",
                        loan_start_date=str(top_up_date.date()),
                    ),
                    create_custom_instruction(
                        amount="5000.66",
                        creditor_target_account_id=accounts.DEPOSIT_ACCOUNT,
                        debtor_target_account_id=accounts.LOAN_ACCOUNT,
                        creditor_target_account_address="DEFAULT",
                        debtor_target_account_address=address.PRINCIPAL,
                        event_datetime=top_up_date,
                        denomination=constants.DEFAULT_DENOMINATION,
                        batch_details={
                            "withdrawal_override": "true",
                            "event": "PRINCIPAL_PAYMENT_TOP_UP",
                        },
                    ),
                ],
                expected_balances_at_ts={
                    after_top_up: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "9902"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.EMI_ADDRESS, "0"),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=after_top_up,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="18",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_top_up,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="576.61",
                    ),
                ],
            ),
            SubTest(
                description="repayments after topup",
                events=(
                    # first repayment after topup has accrued different interest
                    _set_up_deposit_events(1, "577.81", 5, 10, 2019, 5)
                    + _set_up_deposit_events(2, "576.61", 5, 10, 2019, 6)
                ),
                expected_balances_at_ts={
                    repayment_date
                    + relativedelta(month=5, hour=8): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "9370.97"),
                            (dimensions.PRINCIPAL_DUE, "531.03"),
                            (dimensions.INTEREST_DUE, "46.78"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.EMI_ADDRESS, "576.61"),
                        ]
                    },
                    repayment_date
                    + relativedelta(month=5, hour=12): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "9370.97"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.EMI_ADDRESS, "576.61"),
                        ]
                    },
                    repayment_date
                    + relativedelta(month=6, hour=8): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "8842.11"),
                            (dimensions.PRINCIPAL_DUE, "528.86"),
                            (dimensions.INTEREST_DUE, "47.75"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.EMI_ADDRESS, "576.61"),
                        ]
                    },
                    repayment_date
                    + relativedelta(month=6, hour=12): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "8842.11"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.EMI_ADDRESS, "576.61"),
                        ]
                    },
                    repayment_date
                    + relativedelta(month=7, hour=12): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "8309.11"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.EMI_ADDRESS, "576.61"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_2nd_top_up,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="15",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_2nd_top_up,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="576.61",
                    ),
                ],
            ),
            SubTest(
                description="do 2nd topup 8000.89",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=top_up_date2,
                        account_id=accounts.LOAN_ACCOUNT,
                        principal="16310",
                        fixed_interest_rate="0.05",
                        total_term="27",
                        loan_start_date=str(top_up_date2.date()),
                    ),
                    create_custom_instruction(
                        amount="8000.89",
                        creditor_target_account_id=accounts.DEPOSIT_ACCOUNT,
                        debtor_target_account_id=accounts.LOAN_ACCOUNT,
                        creditor_target_account_address="DEFAULT",
                        debtor_target_account_address=address.PRINCIPAL,
                        event_datetime=top_up_date2,
                        denomination=constants.DEFAULT_DENOMINATION,
                        batch_details={
                            "withdrawal_override": "true",
                            "event": "PRINCIPAL_PAYMENT_TOP_UP",
                        },
                    ),
                ],
                expected_balances_at_ts={
                    after_2nd_top_up: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "16310"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.EMI_ADDRESS, "0"),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=after_2nd_top_up,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="27",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_2nd_top_up,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="639.95",
                    ),
                ],
            ),
            SubTest(
                description="repayments after 2nd topup",
                events=(
                    # first repayment after topup has accrued different interest
                    _set_up_deposit_events(1, "660.44", 5, 10, 2019, 8)
                    + _set_up_deposit_events(1, "639.95", 5, 10, 2019, 9)
                ),
                expected_balances_at_ts={
                    repayment_date
                    + relativedelta(month=8, hour=8): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "15705.8"),
                            (dimensions.PRINCIPAL_DUE, "604.2"),
                            (dimensions.INTEREST_DUE, "56.24"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.EMI_ADDRESS, "639.95"),
                        ]
                    },
                    repayment_date
                    + relativedelta(month=8, hour=12): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "15705.8"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.EMI_ADDRESS, "639.95"),
                        ]
                    },
                    repayment_date
                    + relativedelta(month=9, hour=12): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "15132.55"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.EMI_ADDRESS, "639.95"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=end,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="25",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=end,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="639.95",
                    ),
                ],
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=loan_1_template_params,
            instance_params=instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_daily_interest_accrual(self):
        start = default_simulation_start_date
        end = start + relativedelta(days=3, seconds=1)

        events = []
        events.append(
            create_inbound_hard_settlement_instruction(
                target_account_id=accounts.LOAN_ACCOUNT,
                # overpayment: 105,263.16, fee: 5,263.16, overpayment - fee: 100,000
                amount=str(Decimal("100000") + Decimal("5263.16")),
                event_datetime=start + relativedelta(days=2),
                internal_account_id=accounts.DEPOSIT_ACCOUNT,
            )
        )
        events.append(
            create_inbound_hard_settlement_instruction(
                target_account_id=accounts.LOAN_ACCOUNT,
                # overpayment: 105,263.16, fee: 5,263.16, overpayment - fee: 100,000
                amount=str(Decimal("100000") + Decimal("5263.16")),
                event_datetime=start + relativedelta(days=3),
                internal_account_id=accounts.DEPOSIT_ACCOUNT,
            )
        )

        main_account = account_to_simulate(
            timestamp=start,
            account_id=accounts.LOAN_ACCOUNT,
            instance_params=loan_1_instance_params,
            template_params=loan_1_template_params,
            contract_file_path=self.contract_filepath,
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

        expected_balances = {
            accounts.LOAN_ACCOUNT: {
                start
                + relativedelta(days=1, seconds=1): [
                    (dimensions.ACCRUED_INTEREST, "25.47945"),
                    (dimensions.OVERPAYMENT, "0"),
                ],
                start
                + relativedelta(days=2, seconds=1): [
                    (dimensions.ACCRUED_INTEREST, "42.46575"),
                    (dimensions.OVERPAYMENT, "-100000"),
                ],
                start
                + relativedelta(days=3, seconds=1): [
                    (dimensions.ACCRUED_INTEREST, "50.95890"),
                    (dimensions.OVERPAYMENT, "-200000"),
                ],
            },
            accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: {
                start
                + relativedelta(days=1, seconds=1): [
                    (dimensions.DEFAULT, "0"),
                ],
                start
                + relativedelta(days=2, seconds=1): [
                    (dimensions.DEFAULT, "5263.16"),
                ],
                start
                + relativedelta(days=3, seconds=1): [
                    (dimensions.DEFAULT, "10526.32"),
                ],
            },
        }
        self.check_balances(expected_balances=expected_balances, actual_balances=get_balances(res))

        schedules = get_processed_scheduled_events(
            res, event_id="ACCRUE_INTEREST", account_id=accounts.LOAN_ACCOUNT
        )
        self.assertEqual(len(schedules), 3)
        self.assertEqual("2020-01-12T00:00:01Z", schedules[0])
        self.assertEqual("2020-01-13T00:00:01Z", schedules[1])
        self.assertEqual("2020-01-14T00:00:01Z", schedules[2])

    def test_daily_penalty_accrual(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=3, day=19, minute=1, tzinfo=timezone.utc)

        main_account = account_to_simulate(
            timestamp=start,
            account_id=accounts.LOAN_ACCOUNT,
            instance_params=loan_2_instance_params,
            template_params=loan_2_template_params,
            contract_file_path=self.contract_filepath,
        )

        events = []

        res = self.client.simulate_smart_contract(
            account_creation_events=[main_account],
            contract_config=self._get_contract_config(
                contract_version_id=main_account["smart_contract_version_id"],
                instance_params=loan_2_instance_params,
                template_params=loan_2_template_params,
            ),
            internal_account_ids=accounts.default_internal_accounts,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
        )

        principal_overdues = [
            posting
            for posting in get_postings(res, accounts.LOAN_ACCOUNT, dimensions.PRINCIPAL_OVERDUE)
            if posting["credit"]
        ]
        interest_overdues = [
            posting
            for posting in get_postings(res, accounts.LOAN_ACCOUNT, dimensions.INTEREST_OVERDUE)
            if posting["credit"]
        ]
        penalties = [
            posting
            for posting in get_postings(res, accounts.LOAN_ACCOUNT, dimensions.PENALTIES)
            if posting["credit"]
        ]

        for index, amount_due in enumerate(zip(principal_overdues, interest_overdues)):
            self.assertEquals(
                Decimal(self.expected_output["late_payment"]["overdue"][index][0]),
                Decimal(amount_due[0]["amount"]),
            )
            self.assertEquals(
                Decimal(self.expected_output["late_payment"]["overdue"][index][1]),
                Decimal(amount_due[1]["amount"]),
            )

        for index, amount_due in enumerate(penalties):
            self.assertEquals(
                Decimal(self.expected_output["late_payment"]["penalties"][index]),
                Decimal(amount_due["amount"]),
            )

    def test_daily_penalty_accrual_without_interest_capitalisation(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=3, day=3, hour=5, tzinfo=timezone.utc)

        template_params = loan_1_template_params.copy()
        template_params["penalty_compounds_overdue_interest"] = "False"

        sub_tests = [
            SubTest(
                description="first EMI due",
                expected_balances_at_ts={
                    datetime(year=2020, month=2, day=12, hour=1, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2120.83"),
                            (dimensions.INTEREST_DUE, "815.34"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                        ]
                    }
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="LOAN_REPAYMENT_NOTIFICATION",
                        account_id=accounts.LOAN_ACCOUNT,
                        run_times=[datetime(2020, 2, 12, 1, tzinfo=timezone.utc)],
                        contexts=[
                            {
                                "account_id": accounts.LOAN_ACCOUNT,
                                "repayment_amount": "2936.17",
                                "overdue_date": "2020-02-22",
                            }
                        ],
                        count=1,
                    )
                ],
            ),
            SubTest(
                description="first EMI overdue",
                expected_balances_at_ts={
                    datetime(year=2020, month=2, day=22, hour=1, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "2120.83"),
                            (dimensions.INTEREST_OVERDUE, "815.34"),
                            (dimensions.PENALTIES, "15"),
                        ]
                    }
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="LOAN_OVERDUE_REPAYMENT_NOTIFICATION",
                        account_id=accounts.LOAN_ACCOUNT,
                        run_times=[datetime(2020, 2, 22, 1, tzinfo=timezone.utc)],
                        contexts=[
                            {
                                "account_id": accounts.LOAN_ACCOUNT,
                                "repayment_amount": "2936.17",
                                "overdue_date": "2020-02-22",
                                "late_repayment_fee": "15",
                            }
                        ],
                        count=1,
                    )
                ],
            ),
            SubTest(
                description="penalty accrual on overdue principal",
                expected_balances_at_ts={
                    datetime(year=2020, month=2, day=27, hour=1, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "2120.83"),
                            (dimensions.INTEREST_OVERDUE, "815.34"),
                            # penalty rate (0.24 + 0.032 - 0.001)
                            # overdue principal 2120.83
                            # number of days 5
                            # 15 + (0.24 + 0.032 - 0.001)/365 * 2120.83 * 5 = 22.85
                            (dimensions.PENALTIES, "22.85"),
                        ]
                    }
                },
            ),
            SubTest(
                description="penalty accrual on overdue principal and interest",
                events=[
                    create_template_parameter_change_event(
                        timestamp=datetime(
                            year=2020, month=2, day=27, hour=10, tzinfo=timezone.utc
                        ),
                        penalty_compounds_overdue_interest="True",
                    )
                ],
                expected_balances_at_ts={
                    datetime(year=2020, month=3, day=3, hour=1, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "2120.83"),
                            (dimensions.INTEREST_OVERDUE, "815.34"),
                            # penalty rate (0.24 + 0.032 - 0.001)
                            # total overdue 2120.83 + 815.34 = 2936.17
                            # overdue interest 815.34
                            # number of days 5
                            # 22.85 + (0.24 + 0.032 - 0.001)/365 * 2936.17 * 5 = 33.75
                            (dimensions.PENALTIES, "33.75"),
                        ]
                    }
                },
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

    def test_daily_penalty_accrual_without_penalty_compounding_interest(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=3, day=3, hour=5, tzinfo=timezone.utc)

        template_params = loan_1_template_params.copy()
        template_params["penalty_compounds_overdue_interest"] = "False"

        sub_tests = [
            SubTest(
                description="first EMI due",
                expected_balances_at_ts={
                    datetime(year=2020, month=2, day=12, hour=1, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2120.83"),
                            (dimensions.INTEREST_DUE, "815.34"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                        ]
                    }
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="LOAN_REPAYMENT_NOTIFICATION",
                        account_id=accounts.LOAN_ACCOUNT,
                        run_times=[datetime(2020, 2, 12, 1, tzinfo=timezone.utc)],
                        contexts=[
                            {
                                "account_id": accounts.LOAN_ACCOUNT,
                                "repayment_amount": "2936.17",
                                "overdue_date": "2020-02-22",
                            }
                        ],
                        count=1,
                    )
                ],
            ),
            SubTest(
                description="first EMI overdue",
                expected_balances_at_ts={
                    datetime(year=2020, month=2, day=22, hour=1, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST, "252.9932"),
                            (dimensions.PRINCIPAL_OVERDUE, "2120.83"),
                            (dimensions.INTEREST_OVERDUE, "815.34"),
                            (dimensions.PENALTIES, "15"),
                        ]
                    }
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="LOAN_OVERDUE_REPAYMENT_NOTIFICATION",
                        account_id=accounts.LOAN_ACCOUNT,
                        run_times=[datetime(2020, 2, 22, 1, tzinfo=timezone.utc)],
                        contexts=[
                            {
                                "account_id": accounts.LOAN_ACCOUNT,
                                "repayment_amount": "2936.17",
                                "overdue_date": "2020-02-22",
                                "late_repayment_fee": "15",
                            }
                        ],
                        count=1,
                    )
                ],
            ),
            SubTest(
                description="penalty accrual on overdue principal",
                expected_balances_at_ts={
                    datetime(year=2020, month=2, day=27, hour=1, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST, "379.4898"),
                            (dimensions.PRINCIPAL_OVERDUE, "2120.83"),
                            (dimensions.INTEREST_OVERDUE, "815.34"),
                            # penalty rate (0.24 + 0.032 - 0.001)
                            # overdue principal 2120.83
                            # number of days 5
                            # 15 + (0.24 + 0.032 - 0.001)/365 * 2120.83 * 5 = 22.85
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PENALTIES, "22.85"),
                        ]
                    }
                },
            ),
            SubTest(
                description="penalty accrual on overdue principal and interest",
                events=[
                    create_template_parameter_change_event(
                        timestamp=datetime(
                            year=2020, month=2, day=27, hour=10, tzinfo=timezone.utc
                        ),
                        penalty_compounds_overdue_interest="True",
                    )
                ],
                expected_balances_at_ts={
                    datetime(year=2020, month=3, day=3, hour=1, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST, "505.9864"),
                            (dimensions.PRINCIPAL_OVERDUE, "2120.83"),
                            (dimensions.INTEREST_OVERDUE, "815.34"),
                            # penalty rate (0.24 + 0.032 - 0.001)
                            # total overdue 2120.83 + 815.34 = 2936.17
                            # overdue interest 815.34
                            # number of days 5
                            # 22.85 + (0.24 + 0.032 - 0.001)/365 * 2936.17 * 5 = 33.75
                            (dimensions.PENALTIES, "33.75"),
                        ]
                    }
                },
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

    def test_zero_interest_rate(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2)

        template_params = loan_1_template_params.copy()
        template_params["variable_interest_rate"] = "0.001"

        sub_tests = [
            SubTest(
                description="0 interest accrual",
                expected_balances_at_ts={
                    datetime(year=2020, month=2, day=12, hour=1, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            # 300000/120 = 2500
                            (dimensions.PRINCIPAL_DUE, "2500"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                        ]
                    }
                },
            )
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

    def test_change_repayment_day_scenarios(self):
        """
        There are 6 scenarios relating to a repayment day change
        after the first repayment date
        3 where the repayment day change request occurs after the months repayment day
        and 3 where the repayment day change request occurs before the current months repayment day

        scenarios:
            after repayment day has passed:
                1. old_repayment_day < change_day < new_repayment_day
                    (e.g. on 15th change from 12th to 20th)
                2. old repayment_day < new_repayment_day < change_day
                    e.g. on 23rd change from 20th to 21st)
                3. new_repayment_day < old_repayment_day < change_day
                    (e.g. on 23rd change from 21st to 12th)

            before repayment day:
                1. change_day < old_repayment_day < new_repayment_day
                    (e.g. on 9th change from 12th to 15th)
                2. change_day < new_repayment_day < old repayment_day
                    (e.g. on 9th change from 15th to 13th)
                3. new_repayment_day < change_day < old_repayment day
                    (e.g. on 9th change from 13th to 5th)

        """
        start = default_simulation_start_date
        end = start + relativedelta(months=9)
        instance_params = loan_2_instance_params.copy()
        instance_params["repayment_day"] = "12"

        first_param_change = datetime(2020, 2, 15, 10, tzinfo=timezone.utc)
        second_param_change = datetime(2020, 3, 23, 10, tzinfo=timezone.utc)
        third_param_change = datetime(2020, 4, 23, 10, tzinfo=timezone.utc)
        fourth_param_change = datetime(2020, 6, 9, 10, tzinfo=timezone.utc)
        fifth_param_change = datetime(2020, 7, 9, 10, tzinfo=timezone.utc)
        sixth_param_change = datetime(2020, 8, 9, 10, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="Change repayment day after current months repayment day event",
                events=[
                    # After payment day - scenario 1
                    # expect next schedule 20/03/20
                    create_instance_parameter_change_event(
                        timestamp=first_param_change,
                        account_id=accounts.LOAN_ACCOUNT,
                        repayment_day="20",
                    ),
                    # After payment day - scenario 2
                    # expect next schedule 21/04/20
                    create_instance_parameter_change_event(
                        timestamp=second_param_change,
                        account_id=accounts.LOAN_ACCOUNT,
                        repayment_day="21",
                    ),
                    # After payment day - scenario 3
                    # expect next schedule 12/05/20
                    create_instance_parameter_change_event(
                        timestamp=third_param_change,
                        account_id=accounts.LOAN_ACCOUNT,
                        repayment_day="12",
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=2,
                                day=12,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=3,
                                day=20,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=4,
                                day=21,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=5,
                                day=12,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=timezone.utc,
                            ),
                        ],
                        event_id="REPAYMENT_DAY_SCHEDULE",
                        account_id=accounts.LOAN_ACCOUNT,
                        count=9,
                    )
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="next_repayment_date",
                        value="2020-02-12",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="120",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_param_change + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="next_repayment_date",
                        value="2020-03-20",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_param_change + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="119",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_param_change + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="next_repayment_date",
                        value="2020-04-21",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_param_change + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="118",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=third_param_change + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="next_repayment_date",
                        value="2020-05-12",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=third_param_change + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="117",
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2020, 2, 12, 10, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "297879.17"),
                            (dimensions.INTEREST_DUE, "815.34"),
                            (dimensions.PRINCIPAL_DUE, "2120.83"),
                            (dimensions.EMI_ADDRESS, "2910.69"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                        ],
                    },
                    datetime(2020, 3, 20, 10, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "295904.55"),
                            (dimensions.INTEREST_DUE, "936.07"),
                            (dimensions.PRINCIPAL_DUE, "1974.62"),
                            (dimensions.EMI_ADDRESS, "2910.69"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                        ],
                    },
                    datetime(2020, 4, 21, 10, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "293798.07"),
                            (dimensions.INTEREST_DUE, "804.21"),
                            (dimensions.PRINCIPAL_DUE, "2106.48"),
                            (dimensions.EMI_ADDRESS, "2910.69"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Change repayment day before current months repayment day event",
                events=[
                    # Before payment day - scenario 1
                    # on 09/06/20 change from 12th to 15th
                    # expect next schedule 15/06/20
                    create_instance_parameter_change_event(
                        timestamp=fourth_param_change,
                        account_id=accounts.LOAN_ACCOUNT,
                        repayment_day="15",
                    ),
                    #  Before payment day - scenario 2
                    # on 09/07/20 change from 15th to 13th
                    # expect next schedule 13/07/20
                    create_instance_parameter_change_event(
                        timestamp=fifth_param_change,
                        account_id=accounts.LOAN_ACCOUNT,
                        repayment_day="13",
                    ),
                    # Before payment day - scenario 3
                    # on 09/08/20 change from 13th to 5th
                    # expect next schedule 13/08/20
                    # and the subsequent on 05/09/20
                    create_instance_parameter_change_event(
                        timestamp=sixth_param_change,
                        account_id=accounts.LOAN_ACCOUNT,
                        repayment_day="5",
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=6,
                                day=15,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=7,
                                day=13,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=8,
                                day=13,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=9,
                                day=5,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=10,
                                day=5,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=timezone.utc,
                            ),
                        ],
                        event_id="REPAYMENT_DAY_SCHEDULE",
                        account_id=accounts.LOAN_ACCOUNT,
                        count=9,
                    )
                ],
                expected_balances_at_ts={
                    datetime(2020, 5, 12, 10, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "291411.39"),
                            (dimensions.INTEREST_DUE, "524.01"),
                            (dimensions.PRINCIPAL_DUE, "2386.68"),
                            (dimensions.EMI_ADDRESS, "2910.69"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                        ],
                    },
                    datetime(2020, 6, 15, 10, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "289342.20"),
                            (dimensions.INTEREST_DUE, "841.50"),
                            (dimensions.PRINCIPAL_DUE, "2069.19"),
                            (dimensions.EMI_ADDRESS, "2910.69"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                        ],
                    },
                    datetime(2020, 7, 13, 10, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "287119.59"),
                            (dimensions.INTEREST_DUE, "688.08"),
                            (dimensions.PRINCIPAL_DUE, "2222.61"),
                            (dimensions.EMI_ADDRESS, "2910.69"),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=fourth_param_change + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="next_repayment_date",
                        value="2020-06-15",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=fourth_param_change + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="116",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=fifth_param_change + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="next_repayment_date",
                        value="2020-07-13",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=fifth_param_change + relativedelta(hours=1),  # 09/07/2020
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="115",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=sixth_param_change + relativedelta(hours=1),  # 09/08/2020
                        account_id=accounts.LOAN_ACCOUNT,
                        name="next_repayment_date",
                        value="2020-08-13",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=sixth_param_change + relativedelta(hours=1),  # 09/08/2020,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="114",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=sixth_param_change + relativedelta(months=1, day=3, hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="next_repayment_date",
                        value="2020-09-05",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=datetime(2020, 8, 14, 10, tzinfo=timezone.utc),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="113",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=sixth_param_change + relativedelta(months=2, day=3, hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="next_repayment_date",
                        value="2020-10-05",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=sixth_param_change + relativedelta(months=2, day=3, hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="112",
                    ),
                ],
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=loan_2_template_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_post_repayment_day_schedules(self):
        """
        Check overdue and check delinquency both depend on repayment day schedule
        this test case ensures both events can be scheduled correctly
        """
        start = datetime(year=2020, month=1, day=11, tzinfo=timezone.utc)
        end = datetime(year=2021, month=1, day=10, minute=1, tzinfo=timezone.utc)

        # overpayment: 10,526.32, fee: 526.32, overpayment - fee: 10,000
        repayment_with_overpayment = str(Decimal(loan_2_EMI) + Decimal("10000") + Decimal("526.32"))

        sub_tests = [
            SubTest(
                description="check overdue, missing repayment triggers deliquency schedule",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=3,
                                day=1,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            )
                        ],
                        event_id="CHECK_OVERDUE",
                        account_id=accounts.LOAN_ACCOUNT,
                    ),
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=3,
                                day=6,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            )
                        ],
                        event_id="CHECK_DELINQUENCY",
                        account_id=accounts.LOAN_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="check overdue scheduled, "
                "check delinquency not scheduled if due and overdue repaid",
                events=_set_up_deposit_events(
                    2,
                    repayment_with_overpayment,
                    int(loan_2_instance_params["repayment_day"]),
                    payment_hour,
                    start_year,
                    3,
                ),
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=3,
                                day=30,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=4,
                                day=30,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=5,
                                day=30,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                        ],
                        event_id="CHECK_OVERDUE",
                        account_id=accounts.LOAN_ACCOUNT,
                    ),
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=6,
                                day=4,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            )
                        ],
                        event_id="CHECK_DELINQUENCY",
                        account_id=accounts.LOAN_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="repayment day change updates check overdue and delinquency schedule",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=datetime(year=2020, month=6, day=15, tzinfo=timezone.utc),
                        account_id=accounts.LOAN_ACCOUNT,
                        repayment_day="25",
                    )
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=7,
                                day=5,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=8,
                                day=4,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=9,
                                day=4,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=10,
                                day=5,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=11,
                                day=4,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=12,
                                day=5,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2021,
                                month=1,
                                day=4,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                        ],
                        event_id="CHECK_OVERDUE",
                        account_id=accounts.LOAN_ACCOUNT,
                        count=11,
                    ),
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=7,
                                day=10,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=8,
                                day=9,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=9,
                                day=9,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=10,
                                day=10,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=11,
                                day=9,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=12,
                                day=10,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2021,
                                month=1,
                                day=9,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                        ],
                        event_id="CHECK_DELINQUENCY",
                        account_id=accounts.LOAN_ACCOUNT,
                        count=9,
                    ),
                ],
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=loan_2_template_params,
            instance_params=loan_2_instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_early_repayment(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=3, day=29, hour=3, tzinfo=timezone.utc)

        template_params = loan_1_template_params.copy()
        template_params["repayment_period"] = "29"

        early_repayment_time = datetime(year=2020, month=3, day=28, tzinfo=timezone.utc)
        before_early_repayment = early_repayment_time - relativedelta(seconds=1)
        after_early_repayment = early_repayment_time + relativedelta(seconds=1)

        sub_tests = [
            SubTest(
                description="early repayment triggers close loan workflow",
                events=[
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("301973.44") + Decimal("15563.27")),
                        early_repayment_time,
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    before_early_repayment: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "295702.16"),
                            (dimensions.ACCRUED_INTEREST, "376.71645"),
                            (dimensions.INTERNAL_CONTRA, "-3664.1229"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "376.71645"),
                            (dimensions.INTEREST_DUE, "733.68"),
                            (dimensions.PRINCIPAL_DUE, "2177.01"),
                            (dimensions.EMI_ADDRESS, "2910.69"),
                            (dimensions.PENALTIES, "47.7"),
                            (dimensions.PRINCIPAL_OVERDUE, "2120.83"),
                            (dimensions.INTEREST_OVERDUE, "815.34"),
                            (dimensions.DEFAULT, "0"),
                            (dimensions.OVERPAYMENT, "0"),
                        ]
                    },
                    # residual balances not cleared until close account
                    # workflow is complete
                    after_early_repayment: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "295702.16"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "-3312.52088"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "401.83088"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.EMI_ADDRESS, "2910.69"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            # from backdated posting in withdrawal override subtest
                            (dimensions.DEFAULT, "-10000"),
                            (dimensions.OVERPAYMENT, "-295702.16"),
                        ]
                    },
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="LOAN_CLOSURE",
                        account_id=accounts.LOAN_ACCOUNT,
                        count=1,
                    )
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_early_repayment,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="118",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_early_repayment,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="total_early_repayment_amount",
                        value=str(Decimal("301973.44") + Decimal("15563.27")),
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_early_repayment,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="total_outstanding_debt",
                        value="301973.44",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_early_repayment,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="0",
                    ),
                ],
            ),
            SubTest(
                description="back dated overpayment is rejected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount=str(Decimal("301973.44") + Decimal("15563.27")),
                        # amount="301973.44",
                        event_datetime=early_repayment_time + relativedelta(hours=1),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        value_timestamp=early_repayment_time - relativedelta(hours=1),
                    )
                ],
                expected_balances_at_ts={
                    early_repayment_time
                    + relativedelta(hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "295702.16"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "-3312.52088"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "401.83088"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.EMI_ADDRESS, "2910.69"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            # from backdated posting in withdrawal override subtest
                            (dimensions.DEFAULT, "-10000"),
                            (dimensions.OVERPAYMENT, "-295702.16"),
                        ]
                    }
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=early_repayment_time + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Cannot pay more than is owed",
                    )
                ],
            ),
            SubTest(
                description="back dated posting with withdrawal override",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="10000",
                        event_datetime=early_repayment_time + relativedelta(hours=2),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        value_timestamp=early_repayment_time - relativedelta(hours=2),
                        batch_details={"withdrawal_override": "true"},
                    )
                ],
                expected_balances_at_ts={
                    early_repayment_time
                    + relativedelta(hours=2): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "295702.16"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "-3312.52088"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "401.83088"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.EMI_ADDRESS, "2910.69"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.DEFAULT, "-10000"),
                            (dimensions.OVERPAYMENT, "-295702.16"),
                        ]
                    }
                },
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

    def test_early_repayment_with_fees_capitalised(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=3, day=29, hour=3, tzinfo=timezone.utc)

        instance_params = loan_1_instance_params.copy()
        instance_params["capitalise_late_repayment_fee"] = "True"

        template_params = loan_1_template_params.copy()
        template_params["repayment_period"] = "29"
        template_params["capitalise_penalty_interest"] = "True"

        early_repayment_time = datetime(year=2020, month=3, day=28, tzinfo=timezone.utc)
        before_early_repayment = early_repayment_time - relativedelta(seconds=1)
        after_early_repayment = early_repayment_time + relativedelta(seconds=1)

        sub_tests = [
            SubTest(
                description="early repayment triggers close loan workflow",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "317537.52",
                        early_repayment_time,
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    before_early_repayment: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "295702.16"),
                            (dimensions.ACCRUED_INTEREST, "376.7355"),
                            (dimensions.INTERNAL_CONTRA, "-3696.86115"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "376.7355"),
                            (dimensions.INTEREST_DUE, "733.68"),
                            (dimensions.PRINCIPAL_DUE, "2177.01"),
                            (dimensions.EMI_ADDRESS, "2910.69"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "2120.83"),
                            (dimensions.INTEREST_OVERDUE, "815.34"),
                            (dimensions.DEFAULT, "0"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_PENALTIES, "15"),
                            (dimensions.CAPITALISED_INTEREST, "0"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "32.70015",
                            ),
                        ]
                    },
                    after_early_repayment: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "295702.16"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "-3312.5412"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "401.8512"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.EMI_ADDRESS, "2910.69"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.DEFAULT, "0"),
                            (dimensions.OVERPAYMENT, "-295717.16"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_PENALTIES, "15"),
                            (dimensions.CAPITALISED_INTEREST, "0"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "0",
                            ),
                        ]
                    },
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="LOAN_CLOSURE",
                        account_id=accounts.LOAN_ACCOUNT,
                        count=1,
                    )
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_early_repayment,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="118",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_early_repayment,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="total_early_repayment_amount",
                        value="317537.52",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_early_repayment,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="total_outstanding_debt",
                        value="301973.46",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_early_repayment,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="0",
                    ),
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

    def test_delinquency_with_backdated_repayments(self):
        """
        When a repayment is made before the grace period but vault received
        during the grace period, ensure repayment amount is applied to live overdue
        balances first, followed repayment hierarchy and
        CHECK_DELINQUENCY schedule has not instantiated the LOAN_MARK_DELINQUENT workflow.
        Limitation: Penalties accrual not adjusted in retrospect by backdated payment
        """
        start = default_simulation_start_date
        end = datetime(year=2020, month=4, day=7, hour=2, minute=1, tzinfo=timezone.utc)

        first_repayment_date = datetime(
            year=2020, month=2, day=20, hour=0, minute=1, second=0, tzinfo=timezone.utc
        )
        first_grace_period_end = first_repayment_date + relativedelta(days=15, minute=0, second=2)

        second_repayment_date = datetime(
            year=2020, month=3, day=20, hour=0, minute=1, second=0, tzinfo=timezone.utc
        )
        second_grace_period_end = second_repayment_date + relativedelta(days=15, minute=0, second=2)

        before_first_repayment_date = first_repayment_date - relativedelta(hours=1)
        after_first_repayment_date = first_repayment_date + relativedelta(hours=1)

        sub_tests = [
            SubTest(
                description="late payment triggers check delinquency event",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_repayment_date],
                        event_id="REPAYMENT_DAY_SCHEDULE",
                        account_id=accounts.LOAN_ACCOUNT,
                    ),
                    ExpectedSchedule(
                        run_times=[first_grace_period_end],
                        event_id="CHECK_DELINQUENCY",
                        account_id=accounts.LOAN_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            # EMI 2910.69 + Extra interest 229.32 = 3140.01 = 2120.83 + 1019.18
                            (dimensions.PRINCIPAL, "297879.17"),
                            (dimensions.PRINCIPAL_DUE, "2120.83"),
                            (dimensions.INTEREST_DUE, "1019.18"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.EMI_ADDRESS, "2910.69"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                        ]
                    },
                },
            ),
            SubTest(
                description="first transfer due reduces remaining term by 1 month on repayment day",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_first_repayment_date,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="120",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_first_repayment_date,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="119",
                    ),
                ],
            ),
            SubTest(
                description="backdated repayment after graceperiod triggers mark delinquency",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount=loan_2_first_month_payment,
                        event_datetime=first_grace_period_end + relativedelta(hours=1),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        value_timestamp=first_grace_period_end - relativedelta(days=6),
                    )
                ],
                expected_workflows=[
                    ExpectedWorkflow(
                        run_times=[first_grace_period_end],
                        workflow_definition_id="LOAN_MARK_DELINQUENT",
                        account_id=accounts.LOAN_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    first_grace_period_end: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            # penalty rate 0.24 + base rate 0.031 = 0.271
                            # 3140.01 * 0.271/365 * 5 + 15 fee = 26.65
                            # penalties not adjusted by backdating currently
                            (dimensions.PENALTIES, "26.65"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="backdated repayment during graceperiod avoids mark delinquency",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount=loan_2_first_month_payment,
                        event_datetime=second_grace_period_end - relativedelta(days=1),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        value_timestamp=second_grace_period_end - relativedelta(days=2),
                    )
                ],
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="LOAN_MARK_DELINQUENT",
                        account_id=accounts.LOAN_ACCOUNT,
                        # total workflow instance remains at 1, without increase
                        count=1,
                    )
                ],
                expected_balances_at_ts={
                    second_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            # EMI 2910.69 = 2177.01 + 733.68
                            (dimensions.PRINCIPAL_DUE, "2177.01"),
                            (dimensions.INTEREST_DUE, "733.68"),
                            (dimensions.PENALTIES, "26.65"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ]
                    },
                    second_grace_period_end: {
                        accounts.LOAN_ACCOUNT: [
                            # customer second repayment pays off penalties
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ]
                    },
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=loan_2_template_params,
            instance_params=loan_2_instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_in_auth_release(self):
        start = default_simulation_start_date
        end = start + relativedelta(hours=1)

        events = [
            create_inbound_authorisation_instruction(
                target_account_id=accounts.LOAN_ACCOUNT,
                amount=str(Decimal("100")),
                event_datetime=start + relativedelta(minutes=10),
                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                client_transaction_id="RELEASE_TEST_TRANSACTION",
            ),
            create_release_event(
                client_transaction_id="RELEASE_TEST_TRANSACTION",
                event_datetime=start + relativedelta(minutes=20),
            ),
        ]

        main_account = account_to_simulate(
            timestamp=start,
            account_id=accounts.LOAN_ACCOUNT,
            instance_params=loan_1_instance_params,
            template_params=loan_1_template_params,
            contract_file_path=self.contract_filepath,
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
            debug=True,
        )

        expected_balances = {
            accounts.LOAN_ACCOUNT: {
                end: [
                    (dimensions.INCOMING, Decimal("0")),
                    (dimensions.DEFAULT, Decimal("0")),
                ]
            }
        }
        self.check_balances(expected_balances=expected_balances, actual_balances=get_balances(res))

    def test_in_auth_settle(self):
        start = default_simulation_start_date
        end = start + relativedelta(hours=1)

        events = [
            create_inbound_authorisation_instruction(
                target_account_id=accounts.LOAN_ACCOUNT,
                amount=str(Decimal("100")),
                event_datetime=start + relativedelta(minutes=10),
                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                client_transaction_id="SETTLEMENT_TEST_TRANSACTION",
            ),
            create_settlement_event(
                "100.00",
                event_datetime=start + relativedelta(minutes=20),
                client_transaction_id="SETTLEMENT_TEST_TRANSACTION",
                final=True,
            ),
        ]

        main_account = account_to_simulate(
            timestamp=start,
            account_id=accounts.LOAN_ACCOUNT,
            instance_params=loan_1_instance_params,
            template_params=loan_1_template_params,
            contract_file_path=self.contract_filepath,
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
            debug=True,
        )

        expected_balances = {
            accounts.LOAN_ACCOUNT: {
                end: [
                    (dimensions.INCOMING, Decimal("0")),
                    (dimensions.DEFAULT, Decimal("0")),
                    (dimensions.OVERPAYMENT, Decimal("-95")),
                ]
            },
            accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: {
                end: [(dimensions.DEFAULT, Decimal("5"))]
            },
        }
        self.check_balances(expected_balances=expected_balances, actual_balances=get_balances(res))

    def test_capitalised_penalty_interest_and_fees(self):
        start = datetime(year=2021, month=1, day=19, tzinfo=timezone.utc)
        end = datetime(year=2021, month=7, day=21, hour=2, minute=1, tzinfo=timezone.utc)

        instance_params = loan_2_instance_params.copy()
        instance_params["principal"] = "800000"
        instance_params["fixed_interest_loan"] = "False"
        instance_params["capitalise_late_repayment_fee"] = "True"
        instance_params["loan_start_date"] = "2021-01-19"

        template_params = loan_2_template_params.copy()
        template_params["variable_interest_rate"] = "0.02"
        template_params["accrue_interest_on_due_principal"] = "True"
        template_params["penalty_interest_rate"] = "0.02"
        template_params["penalty_includes_base_rate"] = "False"
        template_params["late_repayment_fee"] = "50"
        template_params["repayment_period"] = "1"
        template_params["capitalise_penalty_interest"] = "True"
        template_params["penalty_compounds_overdue_interest"] = "True"

        first_repayment_date = datetime(
            year=2021, month=2, day=20, hour=0, minute=1, second=0, tzinfo=timezone.utc
        )
        sub_tests = [
            SubTest(
                description="repayment events before going into overdue",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_repayment_date],
                        event_id="REPAYMENT_DAY_SCHEDULE",
                        account_id=accounts.LOAN_ACCOUNT,
                    ),
                ],
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount=str(Decimal("6002.18") + Decimal("1402.74")),
                        event_datetime=first_repayment_date + relativedelta(hours=1),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount=str(Decimal("6142.89") + Decimal("1218.19")),
                        event_datetime=first_repayment_date + relativedelta(months=1, hours=1),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount=str(Decimal("6022.81") + Decimal("1338.27")),
                        event_datetime=first_repayment_date + relativedelta(months=2, hours=1),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_template_parameter_change_event(
                        timestamp=datetime(
                            year=2021,
                            month=4,
                            day=20,
                            hour=3,
                            tzinfo=timezone.utc,
                        ),
                        variable_interest_rate="0.021",
                    ),
                ],
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(months=1, minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "787854.93"),
                            (dimensions.PRINCIPAL_DUE, "6142.89"),
                            (dimensions.INTEREST_DUE, "1218.19"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.EMI_ADDRESS, "7361.08"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                        ]
                    },
                    first_repayment_date
                    + relativedelta(months=2, minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "781832.12"),
                            (dimensions.PRINCIPAL_DUE, "6022.81"),
                            (dimensions.INTEREST_DUE, "1338.27"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.EMI_ADDRESS, "7361.08"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                            (dimensions.OVERPAYMENT, "0"),
                        ]
                    },
                    first_repayment_date
                    + relativedelta(months=3, minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "775786"),
                            (dimensions.PRINCIPAL_DUE, "6046.12"),
                            (dimensions.INTEREST_DUE, "1349.46"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.EMI_ADDRESS, "7395.58"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                            (dimensions.OVERPAYMENT, "0"),
                        ]
                    },
                },
            ),
            SubTest(
                description="overdue fees capitalisation day 1",
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(months=3, days=1, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "775786"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "6046.12"),
                            (dimensions.INTEREST_OVERDUE, "1349.46"),
                            # amounts are transferred to overdue after accrual
                            # principal 781,832.12 * rate 0.021 / 365 = 44.98209
                            (dimensions.ACCRUED_INTEREST, "44.98209"),
                            (dimensions.EMI_ADDRESS, "7395.58"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_PENALTIES, "50"),
                            (dimensions.CAPITALISED_INTEREST, "0"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "0",
                            ),
                        ]
                    },
                },
            ),
            SubTest(
                description="overdue fees capitalisation day 2",
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(months=3, days=2, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "775786"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "6046.12"),
                            (dimensions.INTEREST_OVERDUE, "1349.46"),
                            # accrual now excludes the overdue principal
                            # 44.98209 + (principal 775,836.00 * rate 0.021 / 365) = 89.61919
                            (dimensions.ACCRUED_INTEREST, "89.61919"),
                            (dimensions.EMI_ADDRESS, "7395.58"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_PENALTIES, "50"),
                            (dimensions.CAPITALISED_INTEREST, "0"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "0.40524",
                            ),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0.40524")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0.40524")
                        ],
                    },
                },
            ),
            SubTest(
                description="overdue fees capitalisation day 3",
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(months=3, days=3, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "775786"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "6046.12"),
                            (dimensions.INTEREST_OVERDUE, "1349.46"),
                            # accrual now excludes the overdue principal
                            # 89.61919 + (principal 775,836.00 * rate 0.021 / 365) = 134.25629
                            (dimensions.ACCRUED_INTEREST, "134.25629"),
                            (dimensions.EMI_ADDRESS, "7395.58"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_PENALTIES, "50"),
                            (dimensions.CAPITALISED_INTEREST, "0"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "0.81048",
                            ),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0.81048")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0.81048")
                        ],
                    },
                },
            ),
            SubTest(
                description="overdue repayment received on day 3 overdue",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount=str(Decimal("6046.12") + Decimal("1349.46")),
                        event_datetime=first_repayment_date
                        + relativedelta(months=3, days=3, hours=11),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(months=3, days=3, hours=12): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "775786"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST, "134.25629"),
                            (dimensions.EMI_ADDRESS, "7395.58"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_PENALTIES, "50"),
                            (dimensions.CAPITALISED_INTEREST, "0"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "0.81048",
                            ),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0.81048")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0.81048")
                        ],
                    },
                },
            ),
            SubTest(
                description="repayment event after overdue fees and capitalisation",
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(months=4, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "769774.52"),
                            (dimensions.PRINCIPAL_DUE, "6011.48"),
                            (dimensions.INTEREST_DUE, "1384.1"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "7395.58"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0.81"),
                            (dimensions.PRINCIPAL_CAPITALISED_PENALTIES, "50"),
                            (dimensions.CAPITALISED_INTEREST, "0"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "0",
                            ),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0.81")
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(months=4, hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_principal",
                        # 769825.34 = principal 769774.52
                        #             + capitalised interest 0.82
                        #             + capitalised penalties 50
                        value="769825.33",
                    ),
                ],
            ),
            SubTest(
                description="change rate after overdue fee capitalisations",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount=str(Decimal("6011.48") + Decimal("1384.1")),
                        event_datetime=first_repayment_date + relativedelta(months=4, hours=1),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_template_parameter_change_event(
                        timestamp=datetime(
                            year=2021,
                            month=6,
                            day=20,
                            hour=3,
                            tzinfo=timezone.utc,
                        ),
                        variable_interest_rate="0.02",
                    ),
                ],
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(months=5, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "763678.3"),
                            (dimensions.PRINCIPAL_DUE, "6096.22"),
                            (dimensions.INTEREST_DUE, "1265.47"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "7361.69"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0.81"),
                            (dimensions.PRINCIPAL_CAPITALISED_PENALTIES, "50"),
                            (dimensions.CAPITALISED_INTEREST, "0"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "0",
                            ),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0.81")
                        ],
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


# Helper debug functions for printing out balances
def _debug_print_repayment_day_balances(balances):
    repayment_day_dimensions = [
        dimensions.PRINCIPAL,
        dimensions.INTEREST_DUE,
        dimensions.PRINCIPAL_DUE,
        dimensions.EMI_ADDRESS,
        dimensions.OVERPAYMENT,
    ]
    for value_datetime, balance_ts in balances[accounts.LOAN_ACCOUNT]:
        if (
            value_datetime.hour == 0
            and value_datetime.minute == 1
            and value_datetime.microsecond == 2
        ):
            for dimension, balance in balance_ts.items():
                if dimension in repayment_day_dimensions:
                    print(f"{value_datetime} - {dimension[0]}: {balance.net}")


def _debug_print_accrue_interest_balances(balances, accrual_year, accrual_months):
    prev_accrued_interest = Decimal(0)
    for value_datetime, balance_ts in balances[accounts.LOAN_ACCOUNT]:
        if (
            value_datetime.year == accrual_year
            and value_datetime.month in accrual_months
            and value_datetime.second == 1
        ):
            for dimension, balance in balance_ts.items():
                if dimension == dimensions.ACCRUED_INTEREST or dimension == dimensions.PENALTIES:
                    daily_accrued_interest = balance.net - prev_accrued_interest
                    prev_accrued_interest = balance.net
                    print(
                        f"{value_datetime} - {dimension[0]}: {balance.net} |"
                        f" increase: {daily_accrued_interest}"
                    )


if __name__ == "__main__":
    if any(item.startswith("test") for item in sys.argv[1:]):
        unittest.main(LoanTest)
    else:
        unittest.main(LoanTest())
