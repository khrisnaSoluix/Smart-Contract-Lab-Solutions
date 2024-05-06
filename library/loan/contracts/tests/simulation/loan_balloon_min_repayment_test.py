# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone

# third party
from dateutil.relativedelta import relativedelta

# common
import inception_sdk.test_framework.common.constants as constants
from inception_sdk.test_framework.contracts.simulation.utils import (
    SimulationTestCase,
)
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    SimulationTestScenario,
    ExpectedSchedule,
    ExpectedWorkflow,
    ExpectedDerivedParameter,
    SubTest,
    ContractConfig,
    ContractModuleConfig,
    AccountConfig,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
)

# Loan specific
import library.loan.constants.accounts as accounts
import library.loan.constants.dimensions as dimensions
import library.loan.constants.files as contract_files
import library.loan.constants.flags as flags

default_simulation_start_date = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)


min_repayment_instance_params = {
    "fixed_interest_rate": "0.031",
    "fixed_interest_loan": "True",
    "total_term": "2",
    "upfront_fee": "0",
    "amortise_upfront_fee": "True",
    "principal": "10000",
    "repayment_day": "20",
    "deposit_account": accounts.DEPOSIT_ACCOUNT,
    "variable_rate_adjustment": "0.00",
    "loan_start_date": str(datetime(year=2020, month=1, day=11, tzinfo=timezone.utc).date()),
    "repayment_holiday_impact_preference": "increase_emi",
    "capitalise_late_repayment_fee": "False",
    "interest_accrual_rest_type": "daily",
    "balloon_payment_days_delta": "0",
}

min_repayment_template_params = {
    "variable_interest_rate": "0.189965",
    "annual_interest_rate_cap": "1.00",
    "annual_interest_rate_floor": "0.00",
    "denomination": constants.DEFAULT_DENOMINATION,
    "late_repayment_fee": "15",
    "penalty_interest_rate": "0.24",
    "capitalise_no_repayment_accrued_interest": "no_capitalisation",
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
    "amortisation_method": "minimum_repayment_with_balloon_payment",
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


class LoanBalloonTest(SimulationTestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_filepath = contract_files.CONTRACT_FILE
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

    def test_min_repayment_balloon_loan_with_repayment_day_change(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, days=16)

        instance_params = min_repayment_instance_params.copy()
        instance_params["repayment_day"] = "1"
        instance_params["balloon_payment_days_delta"] = "5"
        instance_params["loan_start_date"] = str(default_simulation_start_date.date())

        sub_tests = [
            SubTest(
                description="Change repayment day and check schedules",
                events=[
                    # this should change the balloon payment schedule from being
                    # run on 06/03/20 to 15/03/20
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(months=1, days=3),
                        account_id=accounts.LOAN_ACCOUNT,
                        repayment_day="10",
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=2,
                                day=1,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=3,
                                day=10,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=timezone.utc,
                            ),
                        ],
                        event_id="REPAYMENT_DAY_SCHEDULE",
                        account_id=accounts.LOAN_ACCOUNT,
                        count=2,
                    ),
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=3,
                                day=15,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=timezone.utc,
                            ),
                        ],
                        event_id="BALLOON_PAYMENT_SCHEDULE",
                        account_id=accounts.LOAN_ACCOUNT,
                        count=1,
                    ),
                ],
            )
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=min_repayment_template_params,
            instance_params=instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_min_repayment_balloon_loan_overdue_balances_capitalise_penalty_interest(
        self,
    ):
        start = datetime(year=2020, month=1, day=11, tzinfo=timezone.utc)
        first_repayment_schedule = start + relativedelta(months=1, days=9, minutes=1)
        second_repayment_schedule = start + relativedelta(months=2, days=9, minutes=1)
        end = start + relativedelta(months=2, days=12)

        template_params = min_repayment_template_params.copy()
        template_params["repayment_period"] = "1"
        template_params["capitalise_penalty_interest"] = "True"

        instance_params = min_repayment_instance_params.copy()
        instance_params["balloon_payment_days_delta"] = "5"
        instance_params["balloon_payment_amount"] = "5000"

        sub_tests = [
            SubTest(
                description="due balances updated after first repayment date",
                expected_balances_at_ts={
                    first_repayment_schedule
                    - relativedelta(seconds=10): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "33.97280"),
                            (dimensions.ACCRUED_INTEREST, "33.97280"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "33.97280"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "33.97280"),
                        ],
                    },
                    first_repayment_schedule
                    + relativedelta(minutes=10): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "7503.72"),
                            (dimensions.PRINCIPAL_DUE, "2496.28"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.INTEREST_DUE, "33.97"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.EMI_ADDRESS, "2522.61"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "33.97"),
                        ],
                    },
                },
            ),
            SubTest(
                description="due balances moved to overdue after missing payment "
                "and interest is accrued on overdue address",
                expected_balances_at_ts={
                    first_repayment_schedule
                    + relativedelta(days=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "7503.72"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "2496.28"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "33.97"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "0",
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.63730"),
                            (dimensions.ACCRUED_INTEREST, "0.63730"),
                            # late repayment fee of 15
                            (dimensions.PENALTIES, "15"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0.63730"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "34.60730"),
                        ],
                        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "15")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                    first_repayment_schedule
                    + relativedelta(days=2): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "7503.72"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "2496.28"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "33.97"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "1.87862",
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "1.27460"),
                            (dimensions.ACCRUED_INTEREST, "1.27460"),
                            (dimensions.PENALTIES, "15"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "1.27460"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "35.24460"),
                        ],
                        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "15")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "1.87862")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1.87862")
                        ],
                    },
                },
            ),
            SubTest(
                description="overdue interest is capitalised after next repayment date",
                expected_balances_at_ts={
                    second_repayment_schedule
                    + relativedelta(minutes=10): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "4999.59"),
                            (dimensions.PRINCIPAL_DUE, "2504.13"),
                            (dimensions.PRINCIPAL_OVERDUE, "2496.28"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "52.60"),
                            (dimensions.INTEREST_DUE, "18.48"),
                            (dimensions.INTEREST_OVERDUE, "33.97"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "0",
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.PENALTIES, "15"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "52.45"),
                        ],
                        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "15")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "52.60")
                        ],
                    },
                    second_repayment_schedule
                    + relativedelta(days=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "4999.59"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "5000.41"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "52.60"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "52.45"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "1.87862",
                            ),
                            # Interest calculation includes PRINCIPAL_CAPITALISED_INTEREST
                            # (4999.59+52.60)*ROUND(0.031/365,10)
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.42909"),
                            (dimensions.ACCRUED_INTEREST, "0.42909"),
                            (dimensions.PENALTIES, "30"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0.42909"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "52.87909"),
                        ],
                        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "30")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "1.87862")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "54.47862")
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

    def test_min_repayment_predefined_emi_missed_repayment(self):
        start = default_simulation_start_date
        one_month_one_second_after_loan_start = start + relativedelta(months=1, seconds=1)
        one_month_one_minute_after_loan_start = start + relativedelta(months=1, minutes=1)
        two_month_one_second_after_loan_start = start + relativedelta(months=2, seconds=1)
        two_month_one_minute_after_loan_start = start + relativedelta(months=2, minutes=1)
        end = start + relativedelta(months=2, days=5)

        instance_params = min_repayment_instance_params.copy()
        instance_params["balloon_emi_amount"] = "821"
        instance_params["balloon_payment_amount"] = None
        instance_params["principal"] = "100000"
        instance_params["total_term"] = "36"
        instance_params["fixed_interest_rate"] = "0.02"
        instance_params["loan_start_date"] = str(default_simulation_start_date.date())
        instance_params["repayment_day"] = "1"

        sub_tests = [
            SubTest(
                description="Standard Interest Accrual",
                expected_balances_at_ts={
                    start: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "0"),
                            (dimensions.PENALTIES, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    # accrued_interest = round(daily_interest_rate * principal ,5) * days
                    #                  = round((0.02 / 365) * 100000 ,5) * 31
                    one_month_one_second_after_loan_start: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "169.86295"),
                            (dimensions.ACCRUED_INTEREST, "169.86295 "),
                            (dimensions.EMI_ADDRESS, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PENALTIES, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "169.86295 "),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "169.86295 "),
                        ],
                    },
                    one_month_one_minute_after_loan_start: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "99348.86"),
                            (dimensions.PRINCIPAL_DUE, "651.14"),
                            (dimensions.INTEREST_DUE, "169.86"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "821"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PENALTIES, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "169.86"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Due becomes Overdue",
                expected_balances_at_ts={
                    two_month_one_second_after_loan_start: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "99348.86"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "651.14"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "169.86"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "157.86933"),
                            (dimensions.ACCRUED_INTEREST, "157.86933 "),
                            (dimensions.EMI_ADDRESS, "821"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            # daily penalty rate = (0.02 + 0.24)/365 = 0.00071232876
                            # daily accrual = ROUND(0.00071232876 * 821,2) = 0.58
                            # total accrual = 0.58 * 19 = 11.02
                            # 15 late repayment fee
                            (dimensions.PENALTIES, "26.02"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "157.86933 "),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "327.72933 "),
                        ],
                        accounts.INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "11.02")
                        ],
                        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "15")
                        ],
                        accounts.INTERNAL_CAPITALISED_PENALTIES_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                    two_month_one_minute_after_loan_start: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "98685.73"),
                            (dimensions.PRINCIPAL_DUE, "663.13"),
                            (dimensions.PRINCIPAL_OVERDUE, "651.14"),
                            (dimensions.INTEREST_DUE, "157.87"),
                            (dimensions.INTEREST_OVERDUE, "169.86"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "821"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PENALTIES, "26.02"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "327.73"),
                        ],
                        accounts.INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "11.02")
                        ],
                        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "15")
                        ],
                        accounts.INTERNAL_CAPITALISED_PENALTIES_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="LOAN_MARK_DELINQUENT",
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
            template_params=min_repayment_template_params,
            instance_params=instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_min_repayment_predefined_emi_balloon_payment_days_delta_22(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=12, days=23)

        instance_params = min_repayment_instance_params.copy()
        instance_params["balloon_emi_amount"] = "1850"
        instance_params["total_term"] = "12"
        instance_params["balloon_payment_amount"] = None
        instance_params["principal"] = "100000"
        instance_params["fixed_interest_rate"] = "0.02"
        instance_params["loan_start_date"] = str(default_simulation_start_date.date())
        instance_params["repayment_day"] = "1"
        instance_params["balloon_payment_days_delta"] = "22"

        sub_tests = [
            SubTest(
                description="Standard Interest Accrual",
                events=_set_up_deposit_events(11, "1850", 1, 16, 2020, 2),
                expected_balances_at_ts={
                    start: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    # accrued_interest = round(daily_interest_rate * principal ,5) * days
                    #                  = round((0.02 / 365) * 100000 ,5) * 31
                    start
                    + relativedelta(months=1, minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "98319.86"),
                            (dimensions.PRINCIPAL_DUE, "1680.14"),
                            (dimensions.INTEREST_DUE, "169.86"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "169.86"),
                        ],
                    },
                    start
                    + relativedelta(months=2, minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "96626.09"),
                            (dimensions.PRINCIPAL_DUE, "1693.77"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "156.23"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "326.09"),
                        ],
                    },
                    start
                    + relativedelta(months=3, minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "94940.22"),
                            (dimensions.PRINCIPAL_DUE, "1685.87"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "164.13"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "490.22"),
                        ],
                    },
                    start
                    + relativedelta(months=4, minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "93246.29"),
                            (dimensions.PRINCIPAL_DUE, "1693.93"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "156.07"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "646.29"),
                        ],
                    },
                    start
                    + relativedelta(months=5, minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "91554.68"),
                            (dimensions.PRINCIPAL_DUE, "1691.61"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "158.39"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "804.68"),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="12",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="1850",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_principal",
                        value="100000",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="total_outstanding_debt",
                        value="100000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="outstanding_payments",
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="next_repayment_date",
                        value="2020-02-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="next_overdue_date",
                        value="2020-02-11",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="total_early_repayment_amount",
                        value="105263.16",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_balloon_payment_amount",
                        value="79613.80",
                    ),
                ],
            ),
            SubTest(
                description="Final Instalment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="1850",
                        event_datetime=start + relativedelta(months=12, days=1),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(months=12, seconds=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "81330.15"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "138.14964"),
                            (dimensions.ACCRUED_INTEREST, "138.14964"),
                            (dimensions.EMI_ADDRESS, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "138.14964"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1818.29964"),
                        ],
                    },
                    start
                    + relativedelta(months=12, minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "79618.30"),
                            (dimensions.PRINCIPAL_DUE, "1711.85"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "138.15"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1818.30"),
                        ],
                    },
                    start
                    + relativedelta(months=12, days=1, minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "79618.30"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "4.36264"),
                            (dimensions.ACCRUED_INTEREST, "4.36264"),
                            (dimensions.EMI_ADDRESS, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "4.36264"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1822.66264"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Lump Sum Repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="79714.28",
                        event_datetime=start + relativedelta(months=12, days=22, hours=6),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(months=12, days=5, minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "79618.30"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "21.8132"),
                            (dimensions.ACCRUED_INTEREST, "21.8132"),
                            (dimensions.EMI_ADDRESS, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "21.8132"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1840.1132"),
                        ],
                    },
                    start
                    + relativedelta(months=12, days=10, minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "79618.30"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "43.6264"),
                            (dimensions.ACCRUED_INTEREST, "43.6264"),
                            (dimensions.EMI_ADDRESS, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "43.6264"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1861.9264"),
                        ],
                    },
                    start
                    + relativedelta(months=12, days=20, minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "79618.30"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "87.2528"),
                            (dimensions.ACCRUED_INTEREST, "87.2528"),
                            (dimensions.EMI_ADDRESS, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "87.2528"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1905.5528"),
                        ],
                    },
                    start
                    + relativedelta(months=12, days=22, hours=5): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "79618.30"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "95.98"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1914.28"),
                        ],
                    },
                    start
                    + relativedelta(months=12, days=23): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1914.28"),
                        ],
                    },
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="LOAN_MARK_DELINQUENT",
                        account_id=accounts.LOAN_ACCOUNT,
                        count=0,
                    ),
                    ExpectedWorkflow(
                        workflow_definition_id="LOAN_REPAYMENT_NOTIFICATION",
                        account_id=accounts.LOAN_ACCOUNT,
                        count=13,
                    ),
                    ExpectedWorkflow(
                        workflow_definition_id="LOAN_OVERDUE_REPAYMENT_NOTIFICATION",
                        account_id=accounts.LOAN_ACCOUNT,
                        count=0,
                    ),
                    ExpectedWorkflow(
                        workflow_definition_id="LOAN_CLOSURE",
                        account_id=accounts.LOAN_ACCOUNT,
                        count=1,
                    ),
                ],
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=min_repayment_template_params,
            instance_params=instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_min_repayment_predefined_emi_under_repayment(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, days=5)

        instance_params = min_repayment_instance_params.copy()
        instance_params["balloon_emi_amount"] = "821"
        instance_params["balloon_payment_amount"] = None
        instance_params["principal"] = "100000"
        instance_params["total_term"] = "36"
        instance_params["fixed_interest_rate"] = "0.02"
        instance_params["loan_start_date"] = str(default_simulation_start_date.date())
        instance_params["repayment_day"] = "1"

        sub_tests = [
            SubTest(
                description="Standard Interest Accrual, single repayment less than EMI. Check "
                "balances after one month",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="820",
                        event_datetime=datetime(2020, 2, 1, 16, tzinfo=timezone.utc),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    # accrued_interest = round(daily_interest_rate * principal ,5) * days
                    #                  = round((0.02 / 365) * 100000 ,5) * 31
                    start
                    + relativedelta(months=1, seconds=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "169.86295"),
                            (dimensions.ACCRUED_INTEREST, "169.86295 "),
                            (dimensions.EMI_ADDRESS, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "169.86295 "),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "169.86295 "),
                        ],
                    },
                    start
                    + relativedelta(months=1, minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "99348.86"),
                            (dimensions.PRINCIPAL_DUE, "651.14"),
                            (dimensions.INTEREST_DUE, "169.86"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "821"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "169.86"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Outstanding Due becomes Overdue after two months",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=2, seconds=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "99348.86"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "1"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "157.86933"),
                            (dimensions.ACCRUED_INTEREST, "157.86933 "),
                            (dimensions.EMI_ADDRESS, "821"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "157.86933 "),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "327.72933 "),
                        ],
                    },
                    start
                    + relativedelta(months=2, minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "98685.73"),
                            (dimensions.PRINCIPAL_DUE, "663.13"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "157.87"),
                            (dimensions.INTEREST_OVERDUE, "1"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "821"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "327.73"),
                        ],
                    },
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="LOAN_MARK_DELINQUENT",
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
            template_params=min_repayment_template_params,
            instance_params=instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_min_repayment_predefined_emi_amount_lt_interest(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, days=5)

        instance_params = min_repayment_instance_params.copy()
        instance_params["balloon_emi_amount"] = "2"
        instance_params["balloon_payment_amount"] = None
        instance_params["principal"] = "100000"
        instance_params["total_term"] = "36"
        instance_params["fixed_interest_rate"] = "0.02"
        instance_params["loan_start_date"] = str(default_simulation_start_date.date())
        instance_params["repayment_day"] = "1"

        sub_tests = [
            SubTest(
                description="Standard Interest Accrual, with single repayment for EMI amount after "
                "one month.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="2",
                        event_datetime=datetime(2020, 2, 1, 16, tzinfo=timezone.utc),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    # accrued_interest = round(daily_interest_rate * principal ,5) * days
                    #                  = round((0.02 / 365) * 100000 ,5) * 31
                    start
                    + relativedelta(months=1, seconds=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "169.86295"),
                            (dimensions.ACCRUED_INTEREST, "169.86295 "),
                            (dimensions.EMI_ADDRESS, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "169.86295 "),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "169.86295 "),
                        ],
                    },
                    start
                    + relativedelta(months=1, minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "2"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "167.86295"),
                            (dimensions.ACCRUED_INTEREST, "167.86295"),
                            (dimensions.EMI_ADDRESS, "2"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "167.86295"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "169.86295"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check accrued and due amounts after two months.",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=2, seconds=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "326.76700"),
                            (dimensions.ACCRUED_INTEREST, "326.76700"),
                            (dimensions.EMI_ADDRESS, "2"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "326.76700"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "328.76700"),
                        ],
                    },
                    start
                    + relativedelta(months=2, minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "2"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "324.76700"),
                            (dimensions.ACCRUED_INTEREST, "324.76700"),
                            (dimensions.EMI_ADDRESS, "2"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "324.76700"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "328.76700"),
                        ],
                    },
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="LOAN_MARK_DELINQUENT",
                        account_id=accounts.LOAN_ACCOUNT,
                        count=0,
                    )
                ],
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=min_repayment_template_params,
            instance_params=instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_min_repayment_with_predefined_emi_lt_interest_flattened_at_final_payment_delta_days_4(
        self,
    ):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, days=5)

        instance_params = min_repayment_instance_params.copy()
        instance_params["balloon_emi_amount"] = "2"
        instance_params["balloon_payment_amount"] = None
        instance_params["principal"] = "100000"
        instance_params["total_term"] = "2"
        instance_params["fixed_interest_rate"] = "0.02"
        instance_params["loan_start_date"] = str(default_simulation_start_date.date())
        instance_params["repayment_day"] = "1"
        instance_params["balloon_payment_days_delta"] = "4"

        sub_tests = [
            SubTest(
                description="Standard Interest Accrual, balances checked after one month.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="2",
                        event_datetime=datetime(2020, 2, 1, 16, tzinfo=timezone.utc),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    # accrued_interest = round(daily_interest_rate * principal ,5) * days
                    #                  = round((0.02 / 365) * 100000 ,5) * 31
                    start
                    + relativedelta(months=1, seconds=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "169.86295"),
                            (dimensions.ACCRUED_INTEREST, "169.86295 "),
                            (dimensions.EMI_ADDRESS, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "169.86295 "),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "169.86295 "),
                        ],
                    },
                    start
                    + relativedelta(months=1, minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "2"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "167.86295"),
                            (dimensions.ACCRUED_INTEREST, "167.86295"),
                            (dimensions.EMI_ADDRESS, "2"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "167.86295"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "169.86295"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Standard Interest Accrual, balances checked after two months.",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=2, seconds=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "326.76700"),
                            (dimensions.ACCRUED_INTEREST, "326.76700"),
                            (dimensions.EMI_ADDRESS, "2"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "326.76700"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "328.76700"),
                        ],
                    },
                    start
                    + relativedelta(months=2, minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "2"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "324.76700"),
                            (dimensions.ACCRUED_INTEREST, "324.76700"),
                            (dimensions.EMI_ADDRESS, "2"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "324.76700"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "328.76700"),
                        ],
                    },
                    start
                    + relativedelta(months=2, days=4): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "2"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "341.20535"),
                            (dimensions.ACCRUED_INTEREST, "341.20535"),
                            (dimensions.EMI_ADDRESS, "2"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "341.20535"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "345.20535"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Lump Sum Repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="100348.68",
                        event_datetime=datetime(2020, 3, 5, 16, tzinfo=timezone.utc),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(months=2, days=4, hours=18): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "2"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "350.68"),
                        ],
                    },
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="LOAN_MARK_DELINQUENT",
                        account_id=accounts.LOAN_ACCOUNT,
                        count=0,
                    ),
                    ExpectedWorkflow(
                        workflow_definition_id="LOAN_REPAYMENT_NOTIFICATION",
                        account_id=accounts.LOAN_ACCOUNT,
                        count=3,
                    ),
                    ExpectedWorkflow(
                        workflow_definition_id="LOAN_CLOSURE",
                        account_id=accounts.LOAN_ACCOUNT,
                        count=1,
                    ),
                ],
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=min_repayment_template_params,
            instance_params=instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_min_repayment_balloon_amount_emi_calc_required_delta_days_0(self):

        start = default_simulation_start_date
        end = start + relativedelta(years=3, days=10)

        instance_params = min_repayment_instance_params.copy()
        instance_params["balloon_payment_amount"] = "50000"
        instance_params["loan_start_date"] = str(default_simulation_start_date.date())
        instance_params["fixed_interest_rate"] = "0.02"
        instance_params["total_term"] = "36"
        instance_params["principal"] = "100000"
        instance_params["repayment_day"] = "1"

        sub_tests = [
            SubTest(
                description="create monthly deposit events for payment of due balances and"
                "check daily interest accrual on day 1",
                events=_set_up_deposit_events(35, "1515.46", 1, 11, 2020, 2),
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST, "5.47945"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "5.47945"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI_ADDRESS, "0"),
                            (dimensions.INTERNAL_CONTRA, "-10.95890"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "5.47945")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "5.47945")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances after 1 month",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "98654.40"),
                            (dimensions.PRINCIPAL_DUE, "1345.60"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTEREST_DUE, "169.86"),
                            (dimensions.EMI_ADDRESS, "1515.46"),
                            (dimensions.INTERNAL_CONTRA, "-1515.46"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "169.86")
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="36",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="1515.46",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_principal",
                        value="100000",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="total_outstanding_debt",
                        value="100000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="outstanding_payments",
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="next_repayment_date",
                        value="2020-02-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="next_overdue_date",
                        value="2020-02-11",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="total_early_repayment_amount",
                        value="105263.16",
                    ),
                ],
            ),
            SubTest(
                description="check balances after repayment of due amounts",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, days=1, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "98654.40"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST, "5.40572"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "5.40572"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI_ADDRESS, "1515.46"),
                            # -(1515.46 + 5.40572 + 5.40572) = -1526.27144
                            (dimensions.INTERNAL_CONTRA, "-1526.27144"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "5.40572")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "175.26572")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances after 6 months",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=6, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "91870.79"),
                            (dimensions.PRINCIPAL_DUE, "1362.20"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTEREST_DUE, "153.26"),
                            (dimensions.EMI_ADDRESS, "1515.46"),
                            (dimensions.INTERNAL_CONTRA, "-1515.46"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "963.55")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances on balloon payment date",
                expected_balances_at_ts={
                    start
                    + relativedelta(years=3, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "51431.43"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTEREST_DUE, "87.36"),
                            (dimensions.EMI_ADDRESS, "1515.46"),
                            (dimensions.INTERNAL_CONTRA, "-1515.46"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "4559.89")
                        ],
                    },
                },
            ),
            SubTest(
                description="check payment clears due balances and instantiates closure wf",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="51518.79",
                        event_datetime=start + relativedelta(years=3, hours=2),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(years=3, hours=12): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI_ADDRESS, "1515.46"),
                            (dimensions.INTERNAL_CONTRA, "-1515.46"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "4559.89")
                        ],
                    },
                },
                expected_workflows=[
                    ExpectedWorkflow(
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
            template_params=min_repayment_template_params,
            instance_params=instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_min_repayment_balloon_amount_emi_calc_required_with_date_delta(
        self,
    ):
        start = datetime(year=2020, month=1, day=11, tzinfo=timezone.utc)
        one_month_after_loan_start = start + relativedelta(months=1, minutes=1)

        before_first_payment = start + relativedelta(months=1, days=9, minutes=5)
        after_first_payment = start + relativedelta(months=1, days=9, hours=20)

        before_second_repayment_event = start + relativedelta(months=2, days=9, seconds=30)
        after_second_repayment_event = start + relativedelta(months=2, days=9, minutes=5)

        after_second_deposit = start + relativedelta(months=2, days=9, hours=20)

        day_after_theoretical_final_repayment_event = start + relativedelta(
            months=2, days=10, hours=20
        )
        before_balloon_payment_event = start + relativedelta(months=3, days=13, seconds=2)
        after_balloon_payment_event = start + relativedelta(months=3, days=13, hours=1)

        balloon_payment = after_balloon_payment_event + relativedelta(hours=5)
        after_balloon_payment = after_balloon_payment_event + relativedelta(hours=6)

        end = start + relativedelta(months=4)

        instance_params = min_repayment_instance_params.copy()
        instance_params["balloon_payment_days_delta"] = "35"
        instance_params["balloon_payment_amount"] = "5000"

        sub_tests = [
            SubTest(
                description="interest accrued correctly",
                expected_balances_at_ts={
                    start: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "0"),
                            (dimensions.INTERNAL_CONTRA, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    # accrued_interest = round(daily_interest_rate * principal ,5) * days
                    #                  = round((0.031 / 365) * 10000 ,5) * 31
                    one_month_after_loan_start: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "26.32892"),
                            (dimensions.ACCRUED_INTEREST, "26.32892"),
                            (dimensions.EMI_ADDRESS, "0"),
                            (dimensions.INTERNAL_CONTRA, "-52.65784"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "26.32892"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "26.32892"),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="2",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="2522.61",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_principal",
                        value="10000",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="total_outstanding_debt",
                        value="10000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="outstanding_payments",
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="next_repayment_date",
                        value="2020-02-20",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="next_overdue_date",
                        value="2020-03-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="total_early_repayment_amount",
                        value="10526.32",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_balloon_payment_amount",
                        value="5000",
                    ),
                ],
            ),
            SubTest(
                description="interest moved to interest due after first repayment date",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="2530.25",
                        event_datetime=datetime(
                            year=2020, month=2, day=20, hour=12, tzinfo=timezone.utc
                        ),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    # First repayment date is 40 days after the loan start
                    # so more interest has been accrued
                    before_first_payment: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "7503.72"),
                            (dimensions.PRINCIPAL_DUE, "2496.28"),
                            (dimensions.INTEREST_DUE, "33.97"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "2522.61"),
                            (dimensions.INTERNAL_CONTRA, "-2522.61"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "33.97"),
                        ],
                    },
                    after_first_payment: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "7503.72"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "2522.61"),
                            (dimensions.INTERNAL_CONTRA, "-2522.61"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "33.97"),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_first_payment,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="2",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_first_payment + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="1",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_first_payment,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="2522.61",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_first_payment,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_principal",
                        value="7503.72",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_first_payment,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="total_outstanding_debt",
                        value="10033.97",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_first_payment,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="outstanding_payments",
                        value="2530.25",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_first_payment,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_balloon_payment_amount",
                        value="5000",
                    ),
                ],
            ),
            SubTest(
                description="Check second repayment event and payment clears due",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="2522.61",
                        event_datetime=datetime(
                            year=2020, month=3, day=20, hour=12, tzinfo=timezone.utc
                        ),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    before_second_repayment_event: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "7503.72"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "18.48170"),
                            (dimensions.ACCRUED_INTEREST, "18.48170"),
                            (dimensions.EMI_ADDRESS, "2522.61"),
                            (dimensions.INTERNAL_CONTRA, "-2559.57340"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "18.48170"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "52.4517"),
                        ],
                    },
                    after_second_repayment_event: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "4999.59"),
                            (dimensions.PRINCIPAL_DUE, "2504.13"),
                            (dimensions.INTEREST_DUE, "18.48"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "2522.61"),
                            (dimensions.INTERNAL_CONTRA, "-2522.61"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "52.45"),
                        ],
                    },
                    after_second_deposit: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "4999.59"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "2522.61"),
                            (dimensions.INTERNAL_CONTRA, "-2522.61"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "52.45"),
                        ],
                    },
                },
            ),
            SubTest(
                description="check interest accrued after theoretical final repayment",
                expected_balances_at_ts={
                    day_after_theoretical_final_repayment_event: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "4999.59"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.42462"),
                            (dimensions.ACCRUED_INTEREST, "0.42462"),
                            (dimensions.EMI_ADDRESS, "2522.61"),
                            (dimensions.INTERNAL_CONTRA, "-2523.45924"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0.42462"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "52.87462"),
                        ],
                    },
                    before_balloon_payment_event: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "4999.59"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "14.86170"),
                            (dimensions.ACCRUED_INTEREST, "14.86170"),
                            (dimensions.EMI_ADDRESS, "2522.61"),
                            (dimensions.INTERNAL_CONTRA, "-2552.33340"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "14.86170"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "67.3117"),
                        ],
                    },
                    after_balloon_payment_event: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "4999.59"),
                            (dimensions.INTEREST_DUE, "14.86"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "2522.61"),
                            (dimensions.INTERNAL_CONTRA, "-2522.61"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "67.31"),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=day_after_theoretical_final_repayment_event,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=day_after_theoretical_final_repayment_event,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="2522.61",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=day_after_theoretical_final_repayment_event,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_principal",
                        value="4999.59",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=day_after_theoretical_final_repayment_event,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="total_outstanding_debt",
                        value="5000.01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=day_after_theoretical_final_repayment_event,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="outstanding_payments",
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=day_after_theoretical_final_repayment_event,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="next_repayment_date",
                        value="2020-04-24",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=day_after_theoretical_final_repayment_event,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="next_overdue_date",
                        value="2020-05-04",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=day_after_theoretical_final_repayment_event,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_balloon_payment_amount",
                        value="5000",
                    ),
                ],
            ),
            SubTest(
                description="check payment clears due amounts and check schedules",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="5014.45",
                        event_datetime=balloon_payment,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    after_balloon_payment: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.EMI_ADDRESS, "2522.61"),
                            (dimensions.INTERNAL_CONTRA, "-2522.61"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "67.31"),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=2,
                                day=20,
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
                        ],
                        event_id="REPAYMENT_DAY_SCHEDULE",
                        account_id=accounts.LOAN_ACCOUNT,
                        count=2,
                    ),
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=4,
                                day=24,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=timezone.utc,
                            ),
                        ],
                        event_id="BALLOON_PAYMENT_SCHEDULE",
                        account_id=accounts.LOAN_ACCOUNT,
                        count=1,
                    ),
                ],
                expected_workflows=[
                    ExpectedWorkflow(
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
            template_params=min_repayment_template_params,
            instance_params=instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)


def _set_up_deposit_events(
    num_payments: int,
    repayment_amount: str,
    repayment_day: int,
    repayment_hour: int,
    start_year: int,
    start_month: int,
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
