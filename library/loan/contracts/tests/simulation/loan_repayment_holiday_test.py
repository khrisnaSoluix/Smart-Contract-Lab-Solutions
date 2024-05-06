# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import sys
import unittest

# third party
from dateutil.relativedelta import relativedelta

# common
import inception_sdk.test_framework.common.constants as constants
from inception_sdk.test_framework.contracts.simulation.helper import (
    account_to_simulate,
    create_flag_definition_event,
    create_flag_event,
    create_inbound_hard_settlement_instruction,
    create_template_parameter_change_event,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    SimulationTestCase,
    get_balances,
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
import library.loan.contracts.tests.simulation.constants.files as sim_files
import library.loan.constants.flags as flags

default_simulation_start_date = datetime(year=2020, month=1, day=11, tzinfo=timezone.utc)
num_payments = 1
repayment_day = 28
payment_hour = 12
start_year = 2020
start_month = 1
loan_1_expected_monthly_repayment = "2275.16"
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


class LoanRepaymentHolidayTest(SimulationTestCase):
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
        )

    def test_monthly_interest_accrual_fixed_increase_emi(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=9, day=21, tzinfo=timezone.utc)

        payment_holiday_start = datetime(
            year=2020, month=4, day=20, hour=20, minute=2, tzinfo=timezone.utc
        )
        payment_holiday_end = datetime(
            year=2020, month=7, day=20, hour=0, minute=2, tzinfo=timezone.utc
        )

        events = [_set_up_repayment_holiday_flag(start)]

        events.append(
            create_flag_event(
                timestamp=start + timedelta(seconds=2),
                flag_definition_id="REPAYMENT_HOLIDAY",
                account_id=accounts.LOAN_ACCOUNT,
                effective_timestamp=payment_holiday_start,
                expiry_timestamp=payment_holiday_end,
            )
        )

        events.extend(
            _set_up_deposit_events(1, str(Decimal("3140.01")), 20, payment_hour, start_year, 2)
        )
        events.extend(
            _set_up_deposit_events(2, str(Decimal("2910.69")), 20, payment_hour, start_year, 3)
        )

        main_account = account_to_simulate(
            timestamp=start,
            account_id=accounts.LOAN_ACCOUNT,
            instance_params=loan_2_instance_params,
            template_params=loan_2_template_params,
            contract_file_path=self.contract_filepath,
        )

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
        for i, values in enumerate(
            self.expected_output[
                "repayment_holiday_test_monthly_interest_accrual_fixed_increase_emi"
            ]
        ):
            expected_balances[accounts.LOAN_ACCOUNT][repayment_date + relativedelta(months=i)] = [
                (dimensions.PRINCIPAL_DUE, values[0]),
                (dimensions.INTEREST_DUE, values[1]),
                (dimensions.PRINCIPAL, values[2]),
                (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, values[3]),
                (dimensions.ACCRUED_INTEREST, values[4]),
                (dimensions.PRINCIPAL_CAPITALISED_INTEREST, values[5]),
                (dimensions.EMI_ADDRESS, values[6]),
            ]

        self.check_balances(expected_balances=expected_balances, actual_balances=get_balances(res))

    def test_monthly_interest_accrual_fixed_increase_term(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=9, day=21, tzinfo=timezone.utc)

        instance_params = loan_2_instance_params.copy()
        instance_params["repayment_holiday_impact_preference"] = "increase_term"

        payment_holiday_start = datetime(
            year=2020, month=4, day=20, hour=20, minute=2, tzinfo=timezone.utc
        )
        payment_holiday_end = datetime(
            year=2020, month=7, day=20, hour=0, minute=2, tzinfo=timezone.utc
        )

        first_repayment_date = datetime(year=2020, month=2, day=20, minute=2, tzinfo=timezone.utc)
        at_event_b4_holiday_start = payment_holiday_start.replace(hour=0)
        after_event_b4_holiday_start = payment_holiday_start.replace(hour=1)
        before_first_repayment_date = first_repayment_date - relativedelta(hours=1)
        after_first_repayment_due = first_repayment_date + relativedelta(hours=1)
        before_holiday_end = payment_holiday_end - relativedelta(days=1)
        after_holiday_end = payment_holiday_end + relativedelta(hours=1)
        before_repayment_after_holiday = datetime(
            year=2020, month=8, day=19, hour=12, tzinfo=timezone.utc
        )
        before_2nd_repayment_after_holiday = datetime(
            year=2020, month=9, day=19, hour=12, tzinfo=timezone.utc
        )

        sub_tests = [
            SubTest(
                description="create flag definition and flag event with overlapping flag",
                events=[
                    _set_up_repayment_holiday_flag(start),
                    create_flag_event(
                        timestamp=start + timedelta(seconds=2),
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        account_id=accounts.LOAN_ACCOUNT,
                        effective_timestamp=payment_holiday_start,
                        expiry_timestamp=payment_holiday_start + relativedelta(months=1, days=1),
                    ),
                    create_flag_event(
                        timestamp=start + timedelta(seconds=4),
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        account_id=accounts.LOAN_ACCOUNT,
                        effective_timestamp=payment_holiday_start + relativedelta(months=1),
                        expiry_timestamp=payment_holiday_end,
                    ),
                ],
            ),
            SubTest(
                description="repayments up to end of repayment holiday",
                events=_set_up_deposit_events(
                    num_payments=1,
                    repayment_amount=str(Decimal("3140.01")),
                    repayment_day=20,
                    repayment_hour=12,
                    start_year=2020,
                    start_month=2,
                )
                + _set_up_deposit_events(
                    num_payments=2,
                    repayment_amount=str(Decimal("2910.69")),
                    repayment_day=20,
                    repayment_hour=12,
                    start_year=2020,
                    start_month=3,
                ),
                expected_balances_at_ts={
                    first_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2120.83"),
                            (dimensions.INTEREST_DUE, "1019.18"),
                            (dimensions.PRINCIPAL, "297879.17"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI_ADDRESS, "2910.69"),
                        ]
                    },
                    first_repayment_date.replace(month=3): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2177.01"),
                            (dimensions.INTEREST_DUE, "733.68"),
                            (dimensions.PRINCIPAL, "295702.16"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI_ADDRESS, "2910.69"),
                        ]
                    },
                    first_repayment_date.replace(month=4): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2132.14"),
                            (dimensions.INTEREST_DUE, "778.55"),
                            (dimensions.PRINCIPAL, "293570.02"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI_ADDRESS, "2910.69"),
                        ]
                    },
                    # holiday started on April repayment date, April repayment made
                    first_repayment_date.replace(month=5): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL, "293570.02"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            # 293570.02 * 0.031/365 = 24.93334
                            # 24.93334 * 30 = 748.0002
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "748.0002",
                            ),
                            (dimensions.EMI_ADDRESS, "2910.69"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "748.0002")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "748.0002")
                        ],
                    },
                    first_repayment_date.replace(month=6): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL, "293570.02"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            # 293570.02 * 0.031/365 = 24.93334
                            # 24.93334 * 61 = 1520.93374
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "1520.93374",
                            ),
                            (dimensions.EMI_ADDRESS, "2910.69"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "1520.93374")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1520.93374")
                        ],
                    },
                    first_repayment_date.replace(month=7): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL, "293570.02"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            # 293570.02 * 0.031/365 = 24.93334
                            # 24.93334 * 91 = 2268.93394
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "2268.93394",
                            ),
                            (dimensions.EMI_ADDRESS, "2910.69"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "2268.93394")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "2268.93394")
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_first_repayment_date,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="120",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_first_repayment_due,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="119",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=at_event_b4_holiday_start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="117",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_event_b4_holiday_start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="117",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_holiday_end,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="118",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_holiday_end,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="118",
                    ),
                ],
            ),
            SubTest(
                description="repayment after repayment holiday",
                events=_set_up_deposit_events(
                    num_payments=1,
                    repayment_amount=str(Decimal("2910.69")),
                    repayment_day=20,
                    repayment_hour=12,
                    start_year=2020,
                    start_month=8,
                ),
                expected_balances_at_ts={
                    first_repayment_date.replace(month=8, hour=2): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2131.78"),
                            (dimensions.INTEREST_DUE, "778.91"),
                            (dimensions.PRINCIPAL, "291438.24"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "2268.93"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI_ADDRESS, "2910.69"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "2268.93")
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_repayment_after_holiday,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="118",
                    ),
                ],
            ),
            SubTest(
                description="2nd repayment after repayment holiday",
                expected_balances_at_ts={
                    first_repayment_date.replace(month=9, hour=2): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2137.40"),
                            (dimensions.INTEREST_DUE, "773.29"),
                            (dimensions.PRINCIPAL, "289300.84"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "2268.93"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI_ADDRESS, "2910.69"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "2268.93")
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_2nd_repayment_after_holiday,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="117",
                    ),
                ],
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=loan_2_template_params,
            instance_params=instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_monthly_interest_accrual_variable_increase_emi(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=6, day=13, minute=1, tzinfo=timezone.utc)

        payment_holiday_start = datetime(
            year=2020, month=6, day=12, hour=20, minute=2, tzinfo=timezone.utc
        )
        payment_holiday_end = datetime(
            year=2020, month=12, day=12, hour=0, minute=2, tzinfo=timezone.utc
        )

        events = [_set_up_repayment_holiday_flag(start)]

        events.append(
            create_flag_event(
                timestamp=start + timedelta(seconds=2),
                flag_definition_id="REPAYMENT_HOLIDAY",
                account_id=accounts.LOAN_ACCOUNT,
                effective_timestamp=payment_holiday_start,
                expiry_timestamp=payment_holiday_end,
            )
        )

        main_account = account_to_simulate(
            timestamp=start,
            account_id=accounts.LOAN_ACCOUNT,
            instance_params=loan_1_instance_params,
            template_params=loan_1_template_params,
            contract_file_path=self.contract_filepath,
        )

        for event in self.input_data[
            "repayment_holiday_test_monthly_interest_accrual_variable_increase_emi"
        ]:
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
                        smart_contract_version_id=main_account["smart_contract_version_id"],
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

        balances = get_balances(res)

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
        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        for i, values in enumerate(
            self.expected_output[
                "repayment_holiday_test_monthly_interest_accrual_variable_increase_emi"
            ]
        ):
            expected_balances[accounts.LOAN_ACCOUNT][repayment_date + relativedelta(months=i)] = [
                (dimensions.PRINCIPAL_DUE, values[0]),
                (dimensions.INTEREST_DUE, values[1]),
                (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, values[2]),
                (dimensions.PRINCIPAL_CAPITALISED_INTEREST, values[3]),
                (dimensions.EMI_ADDRESS, values[4]),
            ]

        self.check_balances(expected_balances=expected_balances, actual_balances=balances)

    def test_monthly_interest_accrual_variable_increase_term(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=2, day=13, minute=1, tzinfo=timezone.utc)

        instance_params = loan_1_instance_params.copy()
        instance_params["repayment_holiday_impact_preference"] = "increase_term"

        payment_holiday_start = datetime(
            year=2020, month=6, day=12, hour=20, minute=2, tzinfo=timezone.utc
        )
        payment_holiday_end = datetime(
            year=2020, month=12, day=12, hour=0, minute=2, tzinfo=timezone.utc
        )

        first_repayment_date = datetime(year=2020, month=2, day=12, minute=2, tzinfo=timezone.utc)
        at_event_b4_holiday_start = payment_holiday_start.replace(hour=0)
        after_event_b4_holiday_start = payment_holiday_start.replace(hour=1)
        before_first_repayment_date = first_repayment_date - relativedelta(hours=1)
        after_first_repayment_due = first_repayment_date + relativedelta(hours=1)
        before_holiday_end = payment_holiday_end - relativedelta(days=1)
        after_holiday_end = payment_holiday_end + relativedelta(hours=1)
        before_repayment_after_holiday = datetime(
            year=2021, month=1, day=11, hour=11, tzinfo=timezone.utc
        )
        before_2nd_repayment_after_holiday = datetime(
            year=2021, month=2, day=11, hour=11, tzinfo=timezone.utc
        )

        sub_tests = [
            SubTest(
                description="create flag definition and flag event",
                events=[
                    _set_up_repayment_holiday_flag(start),
                    create_flag_event(
                        timestamp=start + timedelta(seconds=2),
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        account_id=accounts.LOAN_ACCOUNT,
                        effective_timestamp=payment_holiday_start,
                        expiry_timestamp=payment_holiday_end,
                    ),
                ],
            ),
            SubTest(
                description="repayments up to end of repayment holiday",
                events=[
                    create_template_parameter_change_event(
                        timestamp=datetime(
                            year=2020,
                            month=2,
                            day=5,
                            tzinfo=timezone.utc,
                        ),
                        variable_interest_rate="0.039",
                    )
                ]
                + _set_up_deposit_events(
                    num_payments=1,
                    repayment_amount=str(Decimal("3034.40")),
                    repayment_day=12,
                    repayment_hour=12,
                    start_year=2020,
                    start_month=2,
                )
                + _set_up_deposit_events(
                    num_payments=1,
                    # overpayment: 10,526.32, fee: 526.32, overpayment - fee: 10,000
                    repayment_amount=str(Decimal("3008.92") + Decimal("10000") + Decimal("526.32")),
                    repayment_day=12,
                    repayment_hour=12,
                    start_year=2020,
                    start_month=3,
                )
                + [
                    create_template_parameter_change_event(
                        timestamp=datetime(
                            year=2020,
                            month=3,
                            day=15,
                            tzinfo=timezone.utc,
                        ),
                        variable_interest_rate="0.041",
                    ),
                    create_template_parameter_change_event(
                        timestamp=datetime(
                            year=2020,
                            month=4,
                            day=10,
                            tzinfo=timezone.utc,
                        ),
                        variable_interest_rate="0.0322",
                    ),
                ]
                + _set_up_deposit_events(
                    num_payments=3,
                    repayment_amount=str(Decimal("2913.37")),
                    repayment_day=12,
                    repayment_hour=12,
                    start_year=2020,
                    start_month=4,
                ),
                expected_balances_at_ts={
                    first_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2173.03"),
                            (dimensions.INTEREST_DUE, "861.37"),
                            (dimensions.PRINCIPAL, "297826.97"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI_ADDRESS, "3008.92"),
                        ]
                    },
                    first_repayment_date.replace(month=3): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2109.73"),
                            (dimensions.INTEREST_DUE, "899.19"),
                            (dimensions.PRINCIPAL, "295717.24"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI_ADDRESS, "3008.92"),
                            (dimensions.OVERPAYMENT, "0"),
                        ]
                    },
                    first_repayment_date.replace(month=4): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "1966.51"),
                            (dimensions.INTEREST_DUE, "946.86"),
                            (dimensions.PRINCIPAL, "293783.87"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI_ADDRESS, "2913.37"),
                            (dimensions.OVERPAYMENT, "-10000"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "526.32")
                        ],
                    },
                    first_repayment_date.replace(month=5): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2185.72"),
                            (dimensions.INTEREST_DUE, "727.65"),
                            (dimensions.PRINCIPAL, "291623.88"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI_ADDRESS, "2913.37"),
                            (dimensions.OVERPAYMENT, "-10000"),
                        ]
                    },
                    first_repayment_date.replace(month=6): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2167.26"),
                            (dimensions.INTEREST_DUE, "746.11"),
                            (dimensions.PRINCIPAL, "289483.27"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI_ADDRESS, "2913.37"),
                        ]
                    },
                    # holiday started on June repayment date, June repayment made
                    first_repayment_date.replace(month=7): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL, "289483.27"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "716.48340",
                            ),
                            (dimensions.EMI_ADDRESS, "2913.37"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "716.48340")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "716.48340")
                        ],
                    },
                    first_repayment_date.replace(month=8): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL, "289483.27"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "1456.84958",
                            ),
                            (dimensions.EMI_ADDRESS, "2913.37"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "1456.84958")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1456.84958")
                        ],
                    },
                    first_repayment_date.replace(month=9): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL, "289483.27"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "2197.21576",
                            ),
                            (dimensions.EMI_ADDRESS, "2913.37"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "2197.21576")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "2197.21576")
                        ],
                    },
                    first_repayment_date.replace(month=10): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL, "289483.27"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "2913.69916",
                            ),
                            (dimensions.EMI_ADDRESS, "2913.37"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "2913.69916")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "2913.69916")
                        ],
                    },
                    first_repayment_date.replace(month=11): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL, "289483.27"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "3654.06534",
                            ),
                            (dimensions.EMI_ADDRESS, "2913.37"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "3654.06534")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "3654.06534")
                        ],
                    },
                    first_repayment_date.replace(month=12): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL, "289483.27"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "4370.54874",
                            ),
                            (dimensions.EMI_ADDRESS, "2913.37"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "4370.54874")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "4370.54874")
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_first_repayment_date,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="120",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_first_repayment_due,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="119",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=at_event_b4_holiday_start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="111",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_event_b4_holiday_start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="111",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_holiday_end,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="113",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_holiday_end,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="113",
                    ),
                ],
            ),
            SubTest(
                description="repayment after repayment holiday",
                events=_set_up_deposit_events(
                    num_payments=1,
                    repayment_amount=str(Decimal("2913.37")),
                    repayment_day=12,
                    repayment_hour=12,
                    start_year=2021,
                    start_month=1,
                ),
                expected_balances_at_ts={
                    first_repayment_date.replace(year=2021, month=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2161.42"),
                            (dimensions.INTEREST_DUE, "751.95"),
                            (dimensions.PRINCIPAL, "287348.57"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "4370.55"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI_ADDRESS, "2913.37"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "4370.55")
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_repayment_after_holiday,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="113",
                    ),
                ],
            ),
            SubTest(
                description="2nd repayment after repayment holiday",
                expected_balances_at_ts={
                    first_repayment_date.replace(year=2021, month=2): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2167.15"),
                            (dimensions.INTEREST_DUE, "746.22"),
                            (dimensions.PRINCIPAL, "285208.22"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "4370.55"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI_ADDRESS, "2913.37"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "4370.55")
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_2nd_repayment_after_holiday,
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
            template_params=loan_1_template_params,
            instance_params=instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_1_year_fixed_with_full_repayment(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=1, day=21, minute=1, tzinfo=timezone.utc)

        instance_params = loan_2_instance_params.copy()
        instance_params["total_term"] = "12"
        instance_params["principal"] = "18000"
        main_account = account_to_simulate(
            timestamp=start,
            account_id=accounts.LOAN_ACCOUNT,
            instance_params=instance_params,
            template_params=loan_2_template_params,
            contract_file_path=self.contract_filepath,
        )

        payment_holiday_start = datetime(
            year=2020, month=4, day=20, hour=20, minute=2, tzinfo=timezone.utc
        )
        payment_holiday_end = datetime(
            year=2020, month=7, day=20, hour=0, minute=2, tzinfo=timezone.utc
        )

        events = [_set_up_repayment_holiday_flag(start)]

        events.append(
            create_flag_event(
                timestamp=start + timedelta(seconds=2),
                flag_definition_id="REPAYMENT_HOLIDAY",
                account_id=accounts.LOAN_ACCOUNT,
                effective_timestamp=payment_holiday_start,
                expiry_timestamp=payment_holiday_end,
            )
        )

        events.extend(_set_up_deposit_events(1, "1539.07", 20, payment_hour, 2020, 2))
        events.extend(_set_up_deposit_events(2, "1525.31", 20, payment_hour, 2020, 3))

        # after repayment holiday
        events.extend(_set_up_deposit_events(5, "2296.70", 20, payment_hour, 2020, 8))

        # Final repayment
        events.extend(_set_up_deposit_events(1, "2297.94", 20, payment_hour, 2021, 1))

        res = self.client.simulate_smart_contract(
            account_creation_events=[main_account],
            contract_config=self._get_contract_config(
                contract_version_id=main_account["smart_contract_version_id"],
                instance_params=instance_params,
                template_params=loan_2_template_params,
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
        for i, values in enumerate(
            self.expected_output["repayment_holiday_1year_fixed_with_full_repayment"]
        ):
            expected_balances[accounts.LOAN_ACCOUNT][repayment_date + relativedelta(months=i)] = [
                (dimensions.PRINCIPAL, values[0]),
                (dimensions.PRINCIPAL_DUE, values[1]),
                (dimensions.INTEREST_DUE, values[2]),
                (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, values[3]),
                (dimensions.PRINCIPAL_CAPITALISED_INTEREST, values[4]),
            ]
        expected_balances[accounts.LOAN_ACCOUNT][end] = [
            (dimensions.PRINCIPAL, "-104.74"),
            (dimensions.PRINCIPAL_DUE, "0"),
            (dimensions.INTEREST_DUE, "0"),
            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "104.74"),
        ]

        self.check_balances(expected_balances=expected_balances, actual_balances=get_balances(res))

    def test_daily_penalty_accrual_and_blocking(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=8, day=21, minute=1, tzinfo=timezone.utc)

        payment_holiday_start = datetime(
            year=2020, month=4, day=20, hour=20, minute=2, tzinfo=timezone.utc
        )
        payment_holiday_end = datetime(
            year=2020, month=6, day=20, hour=20, minute=2, tzinfo=timezone.utc
        )

        first_repayment_date = datetime(year=2020, month=2, day=20, minute=2, tzinfo=timezone.utc)
        before_first_repayment_date = first_repayment_date - relativedelta(hours=1)
        after_first_repayment_due = first_repayment_date + relativedelta(hours=1)

        sub_tests = [
            SubTest(
                description="create flag definition and flag event",
                events=[
                    _set_up_repayment_holiday_flag(start),
                    create_flag_event(
                        timestamp=start + timedelta(seconds=2),
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        account_id=accounts.LOAN_ACCOUNT,
                        effective_timestamp=payment_holiday_start,
                        expiry_timestamp=payment_holiday_end,
                    ),
                ],
            ),
            SubTest(
                description="first EMI due",
                expected_balances_at_ts={
                    first_repayment_date: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2120.83"),
                            (dimensions.INTEREST_DUE, "1019.18"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_first_repayment_date,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="120",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_first_repayment_due,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="119",
                    ),
                ],
            ),
            SubTest(
                description="first EMI overdue, incurring 15 late payment fee",
                expected_balances_at_ts={
                    datetime(year=2020, month=3, day=1, minute=2, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "2120.83"),
                            (dimensions.INTEREST_OVERDUE, "1019.18"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.PENALTIES, "15"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                    }
                },
            ),
            SubTest(
                description="second EMI due",
                expected_balances_at_ts={
                    datetime(year=2020, month=3, day=20, minute=2, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2177.01"),
                            (dimensions.INTEREST_DUE, "733.68"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "2120.83"),
                            (dimensions.INTEREST_OVERDUE, "1019.18"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            # 3140.01*(0.24+0.031)/365 * 19 + 15 = 59.27
                            (dimensions.PENALTIES, "59.27"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                    }
                },
            ),
            SubTest(
                description="second EMI overdue",
                expected_balances_at_ts={
                    datetime(year=2020, month=3, day=30, minute=2, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "4297.84"),
                            (dimensions.INTEREST_OVERDUE, "1752.86"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            # 59.27 + 15 + 3140.01*(0.24+0.031)/365 * 10 = 97.57
                            (dimensions.PENALTIES, "97.57"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                    }
                },
            ),
            SubTest(
                description="third EMI due",
                expected_balances_at_ts={
                    datetime(year=2020, month=4, day=20, minute=2, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2132.14"),
                            (dimensions.INTEREST_DUE, "778.55"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "4297.84"),
                            (dimensions.INTEREST_OVERDUE, "1752.86"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            # 97.57 + (4297.84+1752.86)*(0.24+0.031)/365 * 21 = 191.86
                            (dimensions.PENALTIES, "191.86"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                    }
                },
            ),
            SubTest(
                description="repayment holiday starts, third EMI remains due, no overdue",
                expected_balances_at_ts={
                    datetime(year=2020, month=4, day=30, minute=2, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2132.14"),
                            (dimensions.INTEREST_DUE, "778.55"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "4297.84"),
                            (dimensions.INTEREST_OVERDUE, "1752.86"),
                            (dimensions.PRINCIPAL, "293570.02"),
                            # 293570.02 * 0.031/365 = 24.93334
                            # 24.93334 * 10 = 249.3334
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "249.33340",
                            ),
                            (dimensions.PENALTIES, "191.86"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "249.33340")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "249.33340")
                        ],
                    }
                },
            ),
            SubTest(
                description="repayment holiday ongoing, third EMI remains due",
                expected_balances_at_ts={
                    datetime(year=2020, month=5, day=20, minute=2, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2132.14"),
                            (dimensions.INTEREST_DUE, "778.55"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "4297.84"),
                            (dimensions.INTEREST_OVERDUE, "1752.86"),
                            (dimensions.PRINCIPAL, "293570.02"),
                            # 249.3 + 293570.02 * 0.031/365 = 24.93334
                            # 24.93334 * 30 = 748.0002
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "748.00020",
                            ),
                            (dimensions.PENALTIES, "191.86"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "748.00020")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "748.00020")
                        ],
                    }
                },
            ),
            SubTest(
                description="repayment holiday ongoing, no further overdue from check overdue",
                expected_balances_at_ts={
                    datetime(year=2020, month=5, day=30, minute=2, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2132.14"),
                            (dimensions.INTEREST_DUE, "778.55"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "4297.84"),
                            (dimensions.INTEREST_OVERDUE, "1752.86"),
                            (dimensions.PRINCIPAL, "293570.02"),
                            # 747.9 + 293570.02 * 0.031/365 * 10 = 997.33360
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "997.33360",
                            ),
                            (dimensions.PENALTIES, "191.86"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "997.33360")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "997.33360")
                        ],
                    }
                },
            ),
            SubTest(
                description="repayment holiday ongoing, no further due",
                expected_balances_at_ts={
                    datetime(year=2020, month=6, day=20, minute=2, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2132.14"),
                            (dimensions.INTEREST_DUE, "778.55"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "4297.84"),
                            (dimensions.INTEREST_OVERDUE, "1752.86"),
                            (dimensions.PRINCIPAL, "293570.02"),
                            # 997.2+ 293570.02 * 0.031/365 * 21 = 1520.93374
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "1520.93374",
                            ),
                            (dimensions.PENALTIES, "191.86"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "1520.93374")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1520.93374")
                        ],
                    }
                },
            ),
            SubTest(
                description="repayment holiday ended, third EMI overdue",
                expected_balances_at_ts={
                    datetime(year=2020, month=6, day=30, minute=2, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "1520.93"),
                            (dimensions.PRINCIPAL_OVERDUE, "6429.98"),
                            (dimensions.INTEREST_OVERDUE, "2531.41"),
                            (dimensions.PRINCIPAL, "293570.02"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            # 191.86 + 15 + (4297.84+1752.86)*(0.24+0.031)/365 * 10 = 251.76
                            (dimensions.PENALTIES, "251.76"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1520.93")
                        ],
                    }
                },
            ),
            SubTest(
                description="fourth EMI due",
                expected_balances_at_ts={
                    datetime(year=2020, month=7, day=20, minute=2, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            # EMI increased from 2910.69 to 2969.3
                            # due to capitalised interest added to principal
                            (dimensions.PRINCIPAL_DUE, "2217.42"),
                            (dimensions.INTEREST_DUE, "751.88"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "1520.93"),
                            (dimensions.PRINCIPAL_OVERDUE, "6429.98"),
                            (dimensions.INTEREST_OVERDUE, "2531.41"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            # 251.76+ (6429.98+2531.41)*(0.24+0.031)/365 * 20 = 384.76
                            (dimensions.PENALTIES, "384.76"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1520.93")
                        ],
                    }
                },
            ),
            SubTest(
                description="fourth EMI overdue",
                expected_balances_at_ts={
                    datetime(year=2020, month=7, day=30, minute=2, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "1520.93"),
                            (dimensions.PRINCIPAL_OVERDUE, "8647.4"),
                            (dimensions.INTEREST_OVERDUE, "3283.29"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            # 384.76+15+(6429.98+2531.41)*(0.24+0.031)/365*10 = 466.26
                            (dimensions.PENALTIES, "466.26"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1520.93")
                        ],
                    }
                },
            ),
            SubTest(
                description="fifth EMI due",
                expected_balances_at_ts={
                    datetime(year=2020, month=8, day=20, minute=2, tzinfo=timezone.utc): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2198.2"),
                            (dimensions.INTEREST_DUE, "771.1"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "1520.93"),
                            (dimensions.PRINCIPAL_OVERDUE, "8647.4"),
                            (dimensions.INTEREST_OVERDUE, "3283.29"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            # 466.26+(8647.4+3283.29)*(0.24+0.031)/365*21 = 652.32
                            (dimensions.PENALTIES, "652.32"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1520.93")
                        ],
                    }
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

    def test_monthly_rest_accrual_fixed_increase_emi(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=9, day=21, tzinfo=timezone.utc)
        instance_params = loan_2_instance_params.copy()
        instance_params["interest_accrual_rest_type"] = constants.MONTHLY

        payment_holiday_start = datetime(
            year=2020, month=4, day=20, hour=20, minute=2, tzinfo=timezone.utc
        )
        payment_holiday_end = datetime(
            year=2020, month=7, day=20, hour=0, minute=2, tzinfo=timezone.utc
        )

        events = [_set_up_repayment_holiday_flag(start)]

        events.append(
            create_flag_event(
                timestamp=start + timedelta(seconds=2),
                flag_definition_id="REPAYMENT_HOLIDAY",
                account_id=accounts.LOAN_ACCOUNT,
                effective_timestamp=payment_holiday_start,
                expiry_timestamp=payment_holiday_end,
            )
        )

        events.extend(
            _set_up_deposit_events(1, str(Decimal("3140.01")), 20, payment_hour, start_year, 2)
        )
        events.extend(
            _set_up_deposit_events(2, str(Decimal("2910.69")), 20, payment_hour, start_year, 3)
        )

        main_account = account_to_simulate(
            timestamp=start,
            account_id=accounts.LOAN_ACCOUNT,
            instance_params=instance_params,
            template_params=loan_2_template_params,
            contract_file_path=self.contract_filepath,
        )

        res = self.client.simulate_smart_contract(
            account_creation_events=[main_account],
            contract_config=self._get_contract_config(
                contract_version_id=main_account["smart_contract_version_id"],
                instance_params=instance_params,
                template_params=loan_2_template_params,
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
        for i, values in enumerate(
            self.expected_output["repayment_holiday_test_monthly_rest_fixed_increase_emi"]
        ):
            expected_balances[accounts.LOAN_ACCOUNT][repayment_date + relativedelta(months=i)] = [
                (dimensions.PRINCIPAL_DUE, values[0]),
                (dimensions.INTEREST_DUE, values[1]),
                (dimensions.PRINCIPAL, values[2]),
                (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, values[3]),
                (dimensions.ACCRUED_INTEREST, values[4]),
                (dimensions.PRINCIPAL_CAPITALISED_INTEREST, values[5]),
                (dimensions.EMI_ADDRESS, values[6]),
            ]

        self.check_balances(expected_balances=expected_balances, actual_balances=get_balances(res))


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


def _set_up_repayment_holiday_flag(start):
    return create_flag_definition_event(timestamp=start, flag_definition_id="REPAYMENT_HOLIDAY")


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
                if dimension == dimensions.ACCRUED_INTEREST:
                    daily_accrued_interest = balance.net - prev_accrued_interest
                    prev_accrued_interest = balance.net
                    print(
                        f"{value_datetime} - {dimension[0]}: {balance.net} |"
                        f" increase: {daily_accrued_interest}"
                    )


if __name__ == "__main__":
    if any(item.startswith("test") for item in sys.argv[1:]):
        unittest.main(LoanRepaymentHolidayTest)
    else:
        unittest.main(LoanRepaymentHolidayTest())
