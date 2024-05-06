# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone
from decimal import Decimal

# third party
from dateutil.relativedelta import relativedelta

# common
import inception_sdk.test_framework.common.constants as constants
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_template_parameter_change_event,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    SimulationTestCase,
)
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    ExpectedDerivedParameter,
    SimulationTestScenario,
    SubTest,
    ContractConfig,
    ContractModuleConfig,
    AccountConfig,
)

# Loan specific
import library.loan.constants.accounts as accounts
import library.loan.constants.dimensions as dimensions
import library.loan.constants.files as contract_files
import library.loan.constants.flags as flags
import library.loan.contracts.tests.simulation.constants.files as sim_files

default_simulation_start_date = datetime(year=2020, month=1, day=11, tzinfo=timezone.utc)
num_payments = 1
repayment_day = 28
payment_hour = 12
start_year = 2020
start_month = 1
loan_1_expected_monthly_repayment = "2275.16"
loan_1_expected_remaining_balance = "-46.67"


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


class LoanVariableTest(SimulationTestCase):
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

    def _get_simulation_test_scenario(
        self,
        start,
        end,
        sub_tests,
        template_params=None,
        instance_params=None,
        internal_accounts=None,
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
        return SimulationTestScenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            contract_config=contract_config,
            internal_accounts=internal_accounts,
        )

    def test_monthly_due_for_variable_rate_with_overpayment(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=12, day=13, minute=1, tzinfo=timezone.utc)

        events = []
        sub_tests = []

        for event in self.input_data["monthly_due_for_variable_rate_with_overpayment"]:
            if event[0] == "variable_rate_change":
                # Rate changes occuring just after repayment
                events.append(
                    create_template_parameter_change_event(
                        timestamp=datetime(
                            year=int(event[1]),
                            month=int(event[2]),
                            day=int(event[3]),
                            tzinfo=timezone.utc,
                        ),
                        variable_interest_rate=str(event[4]),
                    )
                )
            else:
                # Repayments occur on repayment day
                events.extend(
                    _set_up_deposit_events(
                        int(event[1]),
                        event[2],
                        12,
                        payment_hour,
                        int(event[3]),
                        int(event[4]),
                    )
                )

        sub_tests.append(SubTest(description="rate change and repayment events", events=events))

        repayment_date = datetime(
            year=start_year,
            month=2,
            day=12,
            hour=0,
            minute=1,
            second=0,
            microsecond=2,
            tzinfo=timezone.utc,
        )
        for i, values in enumerate(self.expected_output["variable_rate_with_overpayments"]):
            sub_tests.append(
                SubTest(
                    description=f"check balance at repayment {i}",
                    expected_balances_at_ts={
                        repayment_date
                        + relativedelta(months=i): {
                            accounts.LOAN_ACCOUNT: [
                                (dimensions.PRINCIPAL_DUE, values[0]),
                                (dimensions.INTEREST_DUE, values[1]),
                            ]
                        }
                    },
                )
            )

        before_first_rate_change = datetime(2020, 2, 4, 1, tzinfo=timezone.utc)
        after_first_rate_change = datetime(2020, 2, 5, 1, tzinfo=timezone.utc)
        # overpayment of £10,000 made on repayment day 12/3/2020
        before_overpayment = datetime(2020, 3, 12, 1, tzinfo=timezone.utc)
        after_overpayment = datetime(2020, 3, 12, 21, tzinfo=timezone.utc)

        sub_tests.extend(
            [
                SubTest(
                    description="remaining term before_first_rate_change",
                    expected_derived_parameters=[
                        ExpectedDerivedParameter(
                            timestamp=before_first_rate_change,
                            account_id=accounts.LOAN_ACCOUNT,
                            name="remaining_term",
                            value="120",
                        )
                    ],
                ),
                SubTest(
                    description="remaining term after_first_rate_change",
                    expected_derived_parameters=[
                        ExpectedDerivedParameter(
                            timestamp=after_first_rate_change,
                            account_id=accounts.LOAN_ACCOUNT,
                            name="remaining_term",
                            value="120",
                        )
                    ],
                ),
                SubTest(
                    description="remaining term before_overpayment",
                    expected_derived_parameters=[
                        ExpectedDerivedParameter(
                            timestamp=before_overpayment,
                            account_id=accounts.LOAN_ACCOUNT,
                            name="remaining_term",
                            value="118",
                        )
                    ],
                ),
                SubTest(
                    description="remaining term after_overpayment",
                    expected_derived_parameters=[
                        ExpectedDerivedParameter(
                            timestamp=after_overpayment,
                            account_id=accounts.LOAN_ACCOUNT,
                            name="remaining_term",
                            value="114",
                        )
                    ],
                ),
            ]
        )

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=loan_1_template_params,
            instance_params=loan_1_instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_variable_rate_with_overpayment_emi_adjustment(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=6, days=16)

        template_params = loan_1_template_params.copy()
        template_params["overpayment_impact_preference"] = "reduce_emi"

        instance_params = loan_1_instance_params.copy()
        instance_params["total_term"] = "12"
        instance_params["repayment_day"] = "20"
        instance_params["principal"] = "3000"

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

        new_repayment_day = "25"
        sixth_repayment_date = datetime(
            year=start_year,
            month=7,
            day=25,
            hour=0,
            minute=1,
            second=0,
            microsecond=2,
            tzinfo=timezone.utc,
        )

        sub_tests = [
            SubTest(
                description="first month emi",
                expected_balances_at_ts={
                    first_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "2753.68"),
                            (dimensions.PRINCIPAL_DUE, "246.32"),
                            (dimensions.INTEREST_DUE, "10.19"),
                            (dimensions.EMI_ADDRESS, "254.22"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="11",
                    )
                ],
            ),
            SubTest(
                description="rate change without overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # emi plus additional interest from account creation
                        "256.51",
                        first_repayment_date + relativedelta(hours=5),
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_template_parameter_change_event(
                        timestamp=first_repayment_date + relativedelta(hours=10),
                        # 0.029 - 0.01 adjustment = 0.028
                        variable_interest_rate="0.029",
                    ),
                ],
                expected_balances_at_ts={
                    second_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "247.72"),
                            (dimensions.INTEREST_DUE, "6.13"),
                            (dimensions.EMI_ADDRESS, "253.85"),
                            (dimensions.OVERPAYMENT, "0"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=second_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="10",
                    )
                ],
            ),
            SubTest(
                description="rate change with overpayment",
                events=[
                    # overpayment: 210.53, fee: 10.53, overpayment - fee: 200
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("253.85") + Decimal("200") + Decimal("10.53")),
                        second_repayment_date + relativedelta(hours=5),
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_template_parameter_change_event(
                        timestamp=second_repayment_date + relativedelta(hours=10),
                        # 0.016 - 0.01 adjustment = 0.015
                        variable_interest_rate="0.016",
                    ),
                ],
                expected_balances_at_ts={
                    third_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "229.24"),
                            (dimensions.INTEREST_DUE, "2.94"),
                            (dimensions.EMI_ADDRESS, "232.18"),
                            (dimensions.OVERPAYMENT, "-200"),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=third_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="9",
                    )
                ],
            ),
            SubTest(
                description="overpayment without rate change",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # overpayment: 105.26, fee: 5.26, overpayment - fee: 100
                        str(Decimal("232.18") + Decimal("100") + Decimal("5.26")),
                        third_repayment_date + relativedelta(hours=5),
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    fourth_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "218.57"),
                            (dimensions.INTEREST_DUE, "2.44"),
                            (dimensions.EMI_ADDRESS, "221.01"),
                            (dimensions.OVERPAYMENT, "-300"),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=fourth_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="8",
                    )
                ],
            ),
            SubTest(
                description="constant rate value with no overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "221.01",
                        fourth_repayment_date + relativedelta(hours=5),
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    fifth_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "218.77"),
                            (dimensions.INTEREST_DUE, "2.24"),
                            (dimensions.EMI_ADDRESS, "221.01"),
                            (dimensions.OVERPAYMENT, "-300"),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=fifth_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="7",
                    )
                ],
            ),
            SubTest(
                description="overpayment made after repayment day change triggers emi recalc",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=fifth_repayment_date + relativedelta(hours=2),
                        account_id=accounts.LOAN_ACCOUNT,
                        repayment_day=new_repayment_day,
                    ),
                    create_inbound_hard_settlement_instruction(
                        # overpayment: 105.26, fee: 5.26, overpayment - fee: 100
                        str(Decimal("221.01") + Decimal("100") + Decimal("5.26")),
                        fifth_repayment_date + relativedelta(hours=5),
                        target_account_id=accounts.LOAN_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    sixth_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.EMI_ADDRESS, "206.66"),
                            (dimensions.OVERPAYMENT, "-400"),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=sixth_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="6",
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

    def test_interest_rate_change_after_final_repayment_day(self):
        """
        test added logic in _calculate_monthly_payment_interest_and_principal
        to ensure that if emi is recalculated after the final repayment day
        we do not encounter [<class 'decimal.DivisionUndefined'>] errors.
        """
        start = default_simulation_start_date
        end = datetime(year=2021, month=5, day=21, minute=1, tzinfo=timezone.utc)
        instance_params = loan_1_instance_params.copy()
        template_params = loan_1_template_params.copy()

        instance_params["total_term"] = "12"
        instance_params["principal"] = "80000"
        instance_params["variable_rate_adjustment"] = "0"

        monthly_emi = "6782.79"
        first_payment = "6789.80"

        before_final_repayment_day = datetime(
            year=2021,
            month=1,
            day=12,
            hour=0,
            minute=0,
            second=30,
            tzinfo=timezone.utc,
        )
        after_final_repayment_day = before_final_repayment_day + relativedelta(hours=5)

        first_payment_date = datetime(
            year=2020,
            month=2,
            day=12,
            hour=10,
            minute=0,
            second=30,
            tzinfo=timezone.utc,
        )
        payments = [
            create_inbound_hard_settlement_instruction(
                first_payment,
                first_payment_date,
                target_account_id=accounts.LOAN_ACCOUNT,
                internal_account_id=accounts.DEPOSIT_ACCOUNT,
            )
        ]
        payments.extend(_set_up_deposit_events(10, monthly_emi, 12, 10, 2020, 3))

        sub_tests = [
            SubTest(
                description="payments excluding final payment",
                events=payments,
                expected_balances_at_ts={
                    before_final_repayment_day: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "6765.23"),
                            (dimensions.ACCRUED_INTEREST, "18.38672"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI_ADDRESS, "6782.79"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ]
                    },
                    after_final_repayment_day: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_DUE, "6765.23"),
                            (dimensions.INTEREST_DUE, "18.39"),
                            (dimensions.EMI_ADDRESS, "6782.79"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=after_final_repayment_day + relativedelta(hours=5),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="next_repayment_date",
                        value="2021-02-12",
                    )
                ],
            ),
            SubTest(
                description="change interest rate once N = 0 to trigger emi recalculation",
                events=[
                    create_template_parameter_change_event(
                        timestamp=before_final_repayment_day + relativedelta(months=1),
                        variable_interest_rate="0.01",
                    ),
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_final_repayment_day + relativedelta(months=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="0",
                    )
                ],
                expected_balances_at_ts={
                    before_final_repayment_day
                    + relativedelta(months=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI_ADDRESS, "6782.79"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "6765.23"),
                            (dimensions.INTEREST_OVERDUE, "18.39"),
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
