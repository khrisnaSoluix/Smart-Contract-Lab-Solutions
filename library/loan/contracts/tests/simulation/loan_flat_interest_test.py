# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone

# third party
from dateutil.relativedelta import relativedelta

# common
import inception_sdk.test_framework.common.constants as constants
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_inbound_hard_settlement_instruction,
    create_flag_definition_event,
    create_flag_event,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    SimulationTestCase,
)

from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    SimulationTestScenario,
    ExpectedDerivedParameter,
    ExpectedRejection,
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
loan_1_EMI = "257.75"


loan_1_instance_params = {
    "fixed_interest_rate": "0.031",
    "fixed_interest_loan": "True",
    "total_term": "12",
    "upfront_fee": "0",
    "amortise_upfront_fee": "False",
    "principal": "3000",
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
    "accrue_interest_on_due_principal": "True",
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
    "amortisation_method": "flat_interest",
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


class LoanFlatInterestTest(SimulationTestCase):
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
        debug=False,
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
            debug=debug,
        )

    def test_monthly_due_for_flat_interest_amortisation(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=14)

        first_repayment_date = datetime(year=2020, month=2, day=20, minute=1, tzinfo=timezone.utc)
        second_repayment_date = first_repayment_date + relativedelta(months=1)
        third_repayment_date = second_repayment_date + relativedelta(months=1)
        fourth_repayment_date = third_repayment_date + relativedelta(months=1)
        fifth_repayment_date = fourth_repayment_date + relativedelta(months=1)
        sixth_repayment_date = fifth_repayment_date + relativedelta(months=1)
        seventh_repayment_date = sixth_repayment_date + relativedelta(months=1)
        eighth_repayment_date = seventh_repayment_date + relativedelta(months=1)
        ninth_repayment_date = eighth_repayment_date + relativedelta(months=1)
        tenth_repayment_date = ninth_repayment_date + relativedelta(months=1)
        eleventh_repayment_date = tenth_repayment_date + relativedelta(months=1)
        twelveth_repayment_date = eleventh_repayment_date + relativedelta(months=1)
        final_repayment_date = twelveth_repayment_date + relativedelta(months=1)

        payment_holiday_start = second_repayment_date + relativedelta(hours=10)
        payment_holiday_end = third_repayment_date + relativedelta(hours=10)

        sub_tests = [
            SubTest(
                description="first repayment date EMI",
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "250.00"),
                            (dimensions.INTEREST_DUE, "7.75"),
                            (dimensions.EMI_ADDRESS, "257.75"),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="11",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="257.75",
                    ),
                ],
            ),
            SubTest(
                description="overpayments not allowed",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="300",
                        event_datetime=first_repayment_date + relativedelta(hours=1),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        first_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Overpayments are not allowed for flat interest loans",
                    )
                ],
            ),
            SubTest(
                description="unpaid due does not accrue additional interest",
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(days=9): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "250.00"),
                            (dimensions.INTEREST_DUE, "7.75"),
                            (dimensions.EMI_ADDRESS, "257.75"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="unpaid due becomes overdue",
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(days=10, hours=5): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_OVERDUE, "250.00"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "7.75"),
                            (dimensions.EMI_ADDRESS, "257.75"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="overdue amount accrues penalty interest",
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(days=15): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_OVERDUE, "250.00"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "7.75"),
                            (dimensions.EMI_ADDRESS, "257.75"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            # 15 late payment fee + round(257.75 * round(0.271/365,5) * 5,2) = 0.95
                            (dimensions.PENALTIES, "15.95"),
                        ]
                    }
                },
            ),
            SubTest(
                description="repayment clears off penalties",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="273.70",
                        event_datetime=first_repayment_date + relativedelta(days=15, hours=1),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    second_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "250.00"),
                            (dimensions.INTEREST_DUE, "7.75"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.EMI_ADDRESS, "257.75"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.PENALTIES, "0"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=second_repayment_date + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="10",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_repayment_date + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="257.75",
                    ),
                ],
            ),
            SubTest(
                description="repayment holiday does not accrue additional interest",
                events=[
                    create_flag_definition_event(
                        timestamp=second_repayment_date + relativedelta(hours=1),
                        flag_definition_id="REPAYMENT_HOLIDAY",
                    ),
                    create_flag_event(
                        timestamp=second_repayment_date + relativedelta(hours=2),
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        account_id=accounts.LOAN_ACCOUNT,
                        effective_timestamp=payment_holiday_start,
                        expiry_timestamp=payment_holiday_end,
                    ),
                ],
                expected_balances_at_ts={
                    third_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "250.00"),
                            (dimensions.INTEREST_DUE, "7.75"),
                            (dimensions.EMI_ADDRESS, "257.75"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=third_repayment_date + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="10",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=third_repayment_date + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="257.75",
                    ),
                ],
            ),
            SubTest(
                description="end of repayment holiday does not affect remaining principal",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="257.75",
                        event_datetime=third_repayment_date + relativedelta(hours=12),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    fourth_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "250.00"),
                            (dimensions.INTEREST_DUE, "7.75"),
                            (dimensions.EMI_ADDRESS, "257.75"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=fourth_repayment_date + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="9",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=fourth_repayment_date + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="257.75",
                    ),
                ],
            ),
            SubTest(
                description="subsequent dues are all constant",
                events=_set_up_deposit_events(9, "257.75", 20, 1, 2020, 5),
                expected_balances_at_ts={
                    fifth_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "250.00"),
                            (dimensions.INTEREST_DUE, "7.75"),
                            (dimensions.EMI_ADDRESS, "257.75"),
                        ]
                    },
                    sixth_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "250.00"),
                            (dimensions.INTEREST_DUE, "7.75"),
                            (dimensions.EMI_ADDRESS, "257.75"),
                        ]
                    },
                    seventh_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "250.00"),
                            (dimensions.INTEREST_DUE, "7.75"),
                            (dimensions.EMI_ADDRESS, "257.75"),
                        ]
                    },
                    eighth_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "250.00"),
                            (dimensions.INTEREST_DUE, "7.75"),
                            (dimensions.EMI_ADDRESS, "257.75"),
                        ]
                    },
                    ninth_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "250.00"),
                            (dimensions.INTEREST_DUE, "7.75"),
                            (dimensions.EMI_ADDRESS, "257.75"),
                        ]
                    },
                    tenth_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "250.00"),
                            (dimensions.INTEREST_DUE, "7.75"),
                            (dimensions.EMI_ADDRESS, "257.75"),
                        ]
                    },
                    eleventh_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "250.00"),
                            (dimensions.INTEREST_DUE, "7.75"),
                            (dimensions.EMI_ADDRESS, "257.75"),
                        ]
                    },
                    twelveth_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "250.00"),
                            (dimensions.INTEREST_DUE, "7.75"),
                            (dimensions.EMI_ADDRESS, "257.75"),
                        ]
                    },
                    final_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "250.00"),
                            (dimensions.INTEREST_DUE, "7.75"),
                            (dimensions.EMI_ADDRESS, "257.75"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=fifth_repayment_date + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="8",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=sixth_repayment_date + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="7",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=seventh_repayment_date + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="6",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=eighth_repayment_date + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="5",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=ninth_repayment_date + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="4",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=tenth_repayment_date + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="3",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=eleventh_repayment_date + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="2",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=twelveth_repayment_date + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="1",
                    ),
                ],
            ),
            SubTest(
                description="account closure trigger upon final payment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="257.75",
                        event_datetime=final_repayment_date + relativedelta(hours=1),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=final_repayment_date + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="0",
                    )
                ],
                expected_workflows=[
                    ExpectedWorkflow(
                        run_times=[final_repayment_date + relativedelta(hours=1)],
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
            template_params=loan_1_template_params,
            instance_params=loan_1_instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_monthly_due_for_flat_interest_amortisation_rule_of_78(self):
        start = default_simulation_start_date
        end = start + relativedelta(years=2, months=4)
        template_params = loan_1_template_params.copy()
        template_params["amortisation_method"] = "rule_of_78"
        instance_params = loan_1_instance_params.copy()
        instance_params["principal"] = "10000"
        instance_params["fixed_interest_rate"] = "0.1"
        instance_params["total_term"] = "24"

        first_repayment_date = datetime(year=2020, month=2, day=20, minute=1, tzinfo=timezone.utc)
        second_repayment_date = first_repayment_date + relativedelta(months=1)
        third_repayment_date = second_repayment_date + relativedelta(months=1)
        fourth_repayment_date = third_repayment_date + relativedelta(months=1)
        fifth_repayment_date = fourth_repayment_date + relativedelta(months=1)
        sixth_repayment_date = fifth_repayment_date + relativedelta(months=1)
        seventh_repayment_date = sixth_repayment_date + relativedelta(months=1)
        eighth_repayment_date = seventh_repayment_date + relativedelta(months=1)
        ninth_repayment_date = eighth_repayment_date + relativedelta(months=1)
        tenth_repayment_date = ninth_repayment_date + relativedelta(months=1)
        eleventh_repayment_date = tenth_repayment_date + relativedelta(months=1)
        twelveth_repayment_date = eleventh_repayment_date + relativedelta(months=1)
        penultimate_repayment_date_without_holiday = first_repayment_date + relativedelta(
            years=1, month=12
        )
        final_repayment_date_without_holiday = (
            penultimate_repayment_date_without_holiday + relativedelta(months=1)
        )
        actual_final_repayment_date = final_repayment_date_without_holiday + relativedelta(months=1)

        payment_holiday_start = second_repayment_date + relativedelta(hours=10)
        payment_holiday_end = third_repayment_date + relativedelta(hours=10)

        expected_remaining_terms = [
            ("20", fifth_repayment_date + relativedelta(days=1)),
            ("19", sixth_repayment_date + relativedelta(days=1)),
            ("18", seventh_repayment_date + relativedelta(days=1)),
            ("17", eighth_repayment_date + relativedelta(days=1)),
            ("16", ninth_repayment_date + relativedelta(days=1)),
            ("15", tenth_repayment_date + relativedelta(days=1)),
            ("14", eleventh_repayment_date + relativedelta(days=1)),
            ("13", twelveth_repayment_date + relativedelta(days=1)),
            ("2", penultimate_repayment_date_without_holiday + relativedelta(days=1)),
            ("1", final_repayment_date_without_holiday + relativedelta(days=1)),
            ("0", actual_final_repayment_date + relativedelta(days=1)),
        ]
        derived_params_remaining_terms = [
            ExpectedDerivedParameter(
                timestamp=x[1],
                account_id=accounts.LOAN_ACCOUNT,
                name="remaining_term",
                value=x[0],
            )
            for x in expected_remaining_terms
        ]
        sub_tests = [
            SubTest(
                description="first repayment date EMI",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="24",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="23",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(hours=-1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="500.00",
                    ),
                ],
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "9660"),
                            (dimensions.PRINCIPAL_DUE, "340.00"),
                            (dimensions.INTEREST_DUE, "160"),
                            (dimensions.EMI_ADDRESS, "500"),
                        ]
                    }
                },
            ),
            SubTest(
                description="overpayments not allowed",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="600",
                        event_datetime=first_repayment_date + relativedelta(hours=1),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        first_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Overpayments are not allowed for rule of 78 loans",
                    )
                ],
            ),
            SubTest(
                description="unpaid due does not accrue additional interest",
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(days=9): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "9660"),
                            (dimensions.PRINCIPAL_DUE, "340.00"),
                            (dimensions.INTEREST_DUE, "160"),
                            (dimensions.EMI_ADDRESS, "500"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="unpaid due becomes overdue",
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(days=10, hours=5): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "9660"),
                            (dimensions.PRINCIPAL_OVERDUE, "340"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "160"),
                            (dimensions.EMI_ADDRESS, "500"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="overdue amount accrues penalty interest",
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(days=15): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "9660"),
                            (dimensions.PRINCIPAL_OVERDUE, "340"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "160"),
                            (dimensions.EMI_ADDRESS, "500"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            # daily penalty rate = (0.1 + 0.24)/365 = 0.00093
                            # daily accrual = ROUND(0.00093 * 500,2) = 0.47
                            # total accrual = 0.47 * 5 = 2.35
                            # 15 late repayment fee
                            (dimensions.PENALTIES, "17.35"),
                        ]
                    }
                },
            ),
            SubTest(
                description="repayment clears off penalties",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="517.35",
                        event_datetime=first_repayment_date + relativedelta(days=15, hours=1),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(days=15, hours=1, minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "9660"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.EMI_ADDRESS, "500"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.PENALTIES, "0"),
                        ]
                    },
                    second_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "9313.33"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "346.67"),
                            (dimensions.INTEREST_DUE, "153.33"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.EMI_ADDRESS, "500"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.PENALTIES, "0"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=second_repayment_date + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="22",
                    )
                ],
            ),
            SubTest(
                description="repayment holiday does not accrue additional interest",
                events=[
                    create_flag_definition_event(
                        timestamp=second_repayment_date + relativedelta(hours=1),
                        flag_definition_id="REPAYMENT_HOLIDAY",
                    ),
                    create_flag_event(
                        timestamp=second_repayment_date + relativedelta(hours=2),
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        account_id=accounts.LOAN_ACCOUNT,
                        effective_timestamp=payment_holiday_start,
                        expiry_timestamp=payment_holiday_end,
                    ),
                ],
                expected_balances_at_ts={
                    third_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "9313.33"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "346.67"),
                            (dimensions.INTEREST_DUE, "153.33"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.EMI_ADDRESS, "500"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.PENALTIES, "0"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=third_repayment_date + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="22",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=third_repayment_date + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="500",
                    ),
                ],
            ),
            SubTest(
                description="end of repayment holiday does not affect remaining principal",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="500",
                        event_datetime=third_repayment_date + relativedelta(hours=12),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    fourth_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "8960"),
                            (dimensions.PRINCIPAL_DUE, "353.33"),
                            (dimensions.INTEREST_DUE, "146.67"),
                            (dimensions.EMI_ADDRESS, "500"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=fourth_repayment_date + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="21",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=fourth_repayment_date + relativedelta(days=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="500",
                    ),
                ],
            ),
            SubTest(
                description="subsequent dues are all constant",
                events=_set_up_deposit_events(21, "500", 20, 1, 2020, 5),
                expected_balances_at_ts={
                    fifth_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "8600"),
                            (dimensions.PRINCIPAL_DUE, "360"),
                            (dimensions.INTEREST_DUE, "140"),
                            (dimensions.EMI_ADDRESS, "500"),
                        ]
                    },
                    sixth_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "8233.33"),
                            (dimensions.PRINCIPAL_DUE, "366.67"),
                            (dimensions.INTEREST_DUE, "133.33"),
                            (dimensions.EMI_ADDRESS, "500"),
                        ]
                    },
                    seventh_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "7860"),
                            (dimensions.PRINCIPAL_DUE, "373.33"),
                            (dimensions.INTEREST_DUE, "126.67"),
                            (dimensions.EMI_ADDRESS, "500"),
                        ]
                    },
                    eighth_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "7480"),
                            (dimensions.PRINCIPAL_DUE, "380"),
                            (dimensions.INTEREST_DUE, "120"),
                            (dimensions.EMI_ADDRESS, "500"),
                        ]
                    },
                    ninth_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "7093.33"),
                            (dimensions.PRINCIPAL_DUE, "386.67"),
                            (dimensions.INTEREST_DUE, "113.33"),
                            (dimensions.EMI_ADDRESS, "500"),
                        ]
                    },
                    tenth_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "6700"),
                            (dimensions.PRINCIPAL_DUE, "393.33"),
                            (dimensions.INTEREST_DUE, "106.67"),
                            (dimensions.EMI_ADDRESS, "500"),
                        ]
                    },
                    eleventh_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "6300"),
                            (dimensions.PRINCIPAL_DUE, "400"),
                            (dimensions.INTEREST_DUE, "100"),
                            (dimensions.EMI_ADDRESS, "500"),
                        ]
                    },
                    twelveth_repayment_date
                    + relativedelta(minutes=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "5893.33"),
                            (dimensions.PRINCIPAL_DUE, "406.67"),
                            (dimensions.INTEREST_DUE, "93.33"),
                            (dimensions.EMI_ADDRESS, "500"),
                        ]
                    },
                },
                expected_derived_parameters=derived_params_remaining_terms,
            ),
            SubTest(
                description="account closure trigger upon final payment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="500",
                        event_datetime=actual_final_repayment_date + relativedelta(days=1),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    actual_final_repayment_date
                    - relativedelta(hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "493.33"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI_ADDRESS, "500"),
                        ]
                    },
                    actual_final_repayment_date
                    + relativedelta(hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "493.33"),
                            (dimensions.INTEREST_DUE, "6.67"),
                            (dimensions.EMI_ADDRESS, "500"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=actual_final_repayment_date - relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="500",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=actual_final_repayment_date + relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="500",
                    ),
                ],
                expected_workflows=[
                    ExpectedWorkflow(
                        run_times=[actual_final_repayment_date + relativedelta(days=1, hours=1)],
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
