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
    ExpectedRejection,
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


no_repayment_instance_params = {
    "fixed_interest_rate": "0.02",
    "fixed_interest_loan": "True",
    "total_term": "36",
    "upfront_fee": "0",
    "amortise_upfront_fee": "True",
    "principal": "100000",
    "repayment_day": "1",
    "deposit_account": accounts.DEPOSIT_ACCOUNT,
    "variable_rate_adjustment": "0.00",
    "loan_start_date": str(default_simulation_start_date.date()),
    "repayment_holiday_impact_preference": "increase_emi",
    "capitalise_late_repayment_fee": "False",
    "interest_accrual_rest_type": "daily",
    "balloon_payment_days_delta": "0",
}

no_repayment_template_params = {
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
    "amortisation_method": "no_repayment",
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

interest_only_instance_params = no_repayment_instance_params.copy()
interest_only_template_params = no_repayment_template_params.copy()
interest_only_template_params["amortisation_method"] = "interest_only"
interest_only_instance_params["principal"] = "10000"
interest_only_instance_params["upfront_fee"] = "0"
interest_only_instance_params["total_term"] = "2"
interest_only_instance_params["fixed_interest_rate"] = "0.031"
interest_only_instance_params["repayment_day"] = "20"
interest_only_instance_params["loan_start_date"] = str(
    datetime(year=2020, month=1, day=11, tzinfo=timezone.utc).date()
)


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

    def test_disabled_balloon_schedule_does_not_run_interest_only(self):
        """
        Test that if the expected run time of the balloon payment schedule
        is exactly the same as the start and end date of the schedule
        it does not run
        """
        start = default_simulation_start_date
        end = start + relativedelta(days=2)

        instance_params = interest_only_instance_params.copy()
        instance_params["total_term"] = "1"

        template_params = interest_only_template_params.copy()
        template_params["repayment_minute"] = "0"

        sub_tests = [
            SubTest(
                description="check balloon payment schedule is not run",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[],
                        count=0,
                        event_id="BALLOON_PAYMENT_SCHEDULE",
                        account_id=accounts.LOAN_ACCOUNT,
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
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_balloon_payment_schedule_gets_run_no_repayment(self):
        """
        Check balloon payment schedule gets run at correct time
        """
        start = default_simulation_start_date
        end = start + relativedelta(months=1, days=1)

        instance_params = no_repayment_instance_params.copy()
        instance_params["total_term"] = "1"

        sub_tests = [
            SubTest(
                description="check balloon payment schedule is run",
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
                            )
                        ],
                        event_id="BALLOON_PAYMENT_SCHEDULE",
                        account_id=accounts.LOAN_ACCOUNT,
                    ),
                ],
            )
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=no_repayment_template_params,
            instance_params=instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_no_repayment_balloon_loan_no_capitalisation(self):

        start = default_simulation_start_date
        end = start + relativedelta(years=3, days=10)

        sub_tests = [
            SubTest(
                description="check daily interest accrual",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.ACCRUED_INTEREST, "5.47945"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "5.47945"),
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
                        value="0",
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
                        value="2023-01-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="next_overdue_date",
                        value="2023-01-11",
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
                        value="100000",
                    ),
                ],
            ),
            SubTest(
                description="check daily interest accrual day 2",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=2, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.ACCRUED_INTEREST, "10.95890"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "10.95890"),
                            (dimensions.INTERNAL_CONTRA, "-21.91780"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "10.95890")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "10.95890")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances at start of next month",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.ACCRUED_INTEREST, "164.38350"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "164.38350"),
                            (dimensions.INTERNAL_CONTRA, "-328.76700"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "164.38350")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "164.38350")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances 1 day into following month",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.ACCRUED_INTEREST, "169.86295"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "169.86295"),
                            (dimensions.INTERNAL_CONTRA, "-339.72590"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "169.86295")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "169.86295")
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(months=1, hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="35",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(months=1, hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(months=1, hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_principal",
                        value="100000",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(months=1, hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="total_outstanding_debt",
                        value="100169.86",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(months=1, hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_balloon_payment_amount",
                        value="100000",
                    ),
                ],
            ),
            SubTest(
                description="check balances before balloon date",
                expected_balances_at_ts={
                    start
                    + relativedelta(years=3): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.ACCRUED_INTEREST, "5999.99775"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "5999.99775"),
                            (dimensions.INTERNAL_CONTRA, "-11999.99550"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "5999.99775")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "5999.99775")
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(years=3, seconds=-1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="1",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(years=3),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(years=3),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(years=3),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_principal",
                        value="100000",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(years=3),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="total_outstanding_debt",
                        value="106000.00",
                    ),
                ],
            ),
            SubTest(
                description="check balances after balloon date",
                expected_balances_at_ts={
                    start
                    + relativedelta(years=3, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "0"),
                            (dimensions.PRINCIPAL_DUE, "100000"),
                            (dimensions.INTEREST_DUE, "6005.48"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "6005.48")
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(years=3, hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_term",
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(years=3, hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_emi",
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(years=3, hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_principal",
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(years=3, hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="total_outstanding_debt",
                        value="106005.48",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(years=3, hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_balloon_payment_amount",
                        value="0",
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2023,
                                month=1,
                                day=1,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=timezone.utc,
                            )
                        ],
                        event_id="BALLOON_PAYMENT_SCHEDULE",
                        account_id=accounts.LOAN_ACCOUNT,
                        count=1,
                    ),
                ],
            ),
            SubTest(
                description="check payment clears due balances and instantiates closure wf",
                events=[
                    # outstanding balance = principal_due + interest_due = 100,000 + 6005.48
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="106005.48",
                        event_datetime=start + relativedelta(years=3, hours=5),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(years=3, hours=6): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "6005.48")
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
            template_params=no_repayment_template_params,
            instance_params=no_repayment_instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_no_repayment_balloon_loan_capitalised_interest_daily(self):

        start = default_simulation_start_date + relativedelta(years=1)
        end = start + relativedelta(years=1, days=2)

        template_params = no_repayment_template_params.copy()
        template_params["capitalise_no_repayment_accrued_interest"] = "daily"

        instance_params = no_repayment_instance_params.copy()
        instance_params["total_term"] = "12"
        instance_params["loan_start_date"] = str(start.date())

        sub_tests = [
            SubTest(
                description="check daily interest accrual day 1",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "-5.47945"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "5.47945",
                            ),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "5.47945")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "5.47945")
                        ],
                    },
                },
            ),
            SubTest(
                description="check daily interest accrual day 2",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=2, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "5.48"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "-5.47975"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "5.47975",
                            ),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "10.95975")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "5.47975")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances at start of next month",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "159.02"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "-5.48816"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "5.48816",
                            ),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "164.50816")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "5.48816")
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
                        value="0",
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
                        value="2022-01-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="next_overdue_date",
                        value="2022-01-11",
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
                description="check balances 1 day into following month",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "164.51"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "-5.48846"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "5.48846",
                            ),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "169.99846")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "5.48846")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances before balloon date",
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "2008.89"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "-5.58953"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "5.58953",
                            ),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "2014.47953")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "5.58953")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances after balloon date",
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "-2020.07"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "2020.07"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "102020.07"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "2020.07")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2022,
                                month=1,
                                day=1,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=timezone.utc,
                            )
                        ],
                        event_id="BALLOON_PAYMENT_SCHEDULE",
                        account_id=accounts.LOAN_ACCOUNT,
                        count=1,
                    ),
                ],
            ),
            SubTest(
                description="check payment clears due balances and instantiates closure wf",
                events=[
                    # outstanding balance = principal_due = 102020.07
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="102020.07",
                        event_datetime=start + relativedelta(years=1, hours=5),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1, hours=6): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "-2020.07"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "2020.07"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "2020.07")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
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
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_no_repayment_balloon_loan_capitalised_interest_monthly(self):
        start = default_simulation_start_date
        end = start + relativedelta(years=1, days=2)

        template_params = no_repayment_template_params.copy()
        template_params["capitalise_no_repayment_accrued_interest"] = constants.MONTHLY

        instance_params = no_repayment_instance_params.copy()
        instance_params["total_term"] = "12"

        sub_tests = [
            SubTest(
                description="check daily interest accrual day 1",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "-5.47945"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "5.47945",
                            ),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "5.47945")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "5.47945")
                        ],
                    },
                },
            ),
            SubTest(
                description="check daily interest accrual day 2",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=2, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "-10.95890"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "10.95890",
                            ),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "10.95890")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "10.95890")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances at start of next month",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "-164.38350"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "164.38350",
                            ),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "164.38350")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "164.38350")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances 1 day into following month",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "164.38"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "-5.48846"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "5.48846",
                            ),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "169.86846")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "5.48846")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances before balloon date",
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1, minutes=-1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "1845.44"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "-172.99767"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "172.99767",
                            ),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "2018.43767")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "172.99767")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances after balloon date",
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "-2024.03"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "2024.03"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "102024.03"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "2024.03")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2021,
                                month=1,
                                day=1,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=timezone.utc,
                            )
                        ],
                        event_id="BALLOON_PAYMENT_SCHEDULE",
                        account_id=accounts.LOAN_ACCOUNT,
                        count=1,
                    ),
                ],
            ),
            SubTest(
                description="check payment clears due balances and instantiates closure wf",
                events=[
                    # outstanding balance = principal_due = 102024.03
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="102024.03",
                        event_datetime=start + relativedelta(years=1, hours=5),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1, hours=6): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "-2024.03"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "2024.03"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "2024.03")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
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
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_no_repayment_balloon_loan_no_capitalisation_with_overpayment(self):

        start = default_simulation_start_date
        end = start + relativedelta(years=1, days=2)
        instance_params = no_repayment_instance_params.copy()
        instance_params["total_term"] = "12"

        sub_tests = [
            SubTest(
                description="check daily interest accrual after first day",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.ACCRUED_INTEREST, "5.47945"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "5.47945"),
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
                description="check daily interest accrual on day 2 after" "an overpayment on day 1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="2000",
                        event_datetime=start + relativedelta(days=1, hours=2),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                # OVERPAYMENT: 2000 * (1-0.05) = 1900 as a deduction fee from overpayment of 100
                expected_balances_at_ts={
                    start
                    + relativedelta(days=2, hours=2): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.ACCRUED_INTEREST, "10.85479"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "10.95890"),
                            (dimensions.INTERNAL_CONTRA, "-21.81369"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.OVERPAYMENT, "-1900"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "10.85479")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "10.85479")
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(days=2, hours=2),
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_balloon_payment_amount",
                        value="98100",
                    ),
                ],
            ),
            SubTest(
                description="check balances at start of next month",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.ACCRUED_INTEREST, "161.36431"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "164.3835"),
                            (dimensions.INTERNAL_CONTRA, "-325.74781"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.OVERPAYMENT, "-1900"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "161.36431")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "161.36431")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances 1 day into following month",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.ACCRUED_INTEREST, "166.73965"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "169.86295"),
                            (dimensions.INTERNAL_CONTRA, "-336.60260"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.OVERPAYMENT, "-1900"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "166.73965")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "166.73965")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances at end of term before balloon date",
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.ACCRUED_INTEREST, "1962.10321"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "1999.99925"),
                            (dimensions.INTERNAL_CONTRA, "-3962.10246"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.OVERPAYMENT, "-1900"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "1962.10321")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1962.10321")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances after balloon payment date",
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "1900"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "0"),
                            (dimensions.PRINCIPAL_DUE, "98100"),
                            (dimensions.INTEREST_DUE, "1967.48"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.OVERPAYMENT, "-1900"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1967.48")
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2021,
                                month=1,
                                day=1,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=timezone.utc,
                            )
                        ],
                        event_id="BALLOON_PAYMENT_SCHEDULE",
                        account_id=accounts.LOAN_ACCOUNT,
                        count=1,
                    ),
                ],
            ),
            SubTest(
                description="check payment clears due balances and instantiates closure wf",
                events=[
                    # outstanding balance = principal_due + interest_due = 98100 + 1967.48
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="100067.48",
                        event_datetime=start + relativedelta(years=1, days=1, hours=7),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1, days=1, hours=8): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "1900"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.10411"),
                            (dimensions.INTERNAL_CONTRA, "-0.10411"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.OVERPAYMENT, "-1900"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1967.48")
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
            template_params=no_repayment_template_params,
            instance_params=instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_no_repayment_balloon_loan_capitalised_interest_daily_with_overpayment(
        self,
    ):

        start = default_simulation_start_date
        end = start + relativedelta(years=1, days=2)

        template_params = no_repayment_template_params.copy()
        template_params["capitalise_no_repayment_accrued_interest"] = "daily"

        instance_params = no_repayment_instance_params.copy()
        instance_params["total_term"] = "12"

        sub_tests = [
            SubTest(
                description="check daily interest accrual day 1",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "-5.47945"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "5.47945",
                            ),
                            (dimensions.OVERPAYMENT, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "5.47945")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "5.47945")
                        ],
                    },
                },
            ),
            SubTest(
                description="check daily interest accrual day 9 before overpayment",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=9, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "43.84"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "-5.48185"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "5.48185",
                            ),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "49.32185")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "5.48185")
                        ],
                    },
                },
            ),
            SubTest(
                description="check daily interest accrual day 10 after an overpayment on day 9",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="10000",
                        event_datetime=start + relativedelta(days=9, hours=2),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=10, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "49.32"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "-4.96160"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "4.96160",
                            ),
                            (dimensions.OVERPAYMENT, "-9500"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "54.28160")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "4.96160")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances at start of next month, 31/01",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "148.59"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "-4.96704"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "4.96704",
                            ),
                            (dimensions.OVERPAYMENT, "-9500"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "153.55704")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "4.96704")
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
                        value="0",
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
                        value="2021-01-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="next_overdue_date",
                        value="2021-01-11",
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
                description="check balances before balloon date",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=12): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "1827.89"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "-5.05906"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "5.05906",
                            ),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.OVERPAYMENT, "-9500"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1832.94906")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "5.05906")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances after balloon date",
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            # principal = 100000 - 92338.01 = 7661.99
                            (dimensions.PRINCIPAL, "7661.99"),
                            (
                                dimensions.PRINCIPAL_CAPITALISED_INTEREST,
                                "1838.01",
                            ),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            # principal + cap_int + add_cap_int + overpayment)
                            # 100000 +  (1827.89 + 5.05906) + 5.05934 - 9500 = 92338.01
                            # where 5.05934 is the add_int accrued on the balloon payment date
                            (
                                dimensions.PRINCIPAL_DUE,
                                "92338.01",
                            ),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.OVERPAYMENT, "-9500"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1838.01")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2021,
                                month=1,
                                day=1,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=timezone.utc,
                            )
                        ],
                        event_id="BALLOON_PAYMENT_SCHEDULE",
                        account_id=accounts.LOAN_ACCOUNT,
                        count=1,
                    ),
                ],
            ),
            SubTest(
                description="check payment clears due balances and instantiates closure wf",
                events=[
                    # outstanding balance = principal_due = 92338.01
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="92338.01",
                        event_datetime=start + relativedelta(years=1, hours=5),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1, hours=6): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "7661.99"),
                            (dimensions.PRINCIPAL_CAPITALISED_INTEREST, "1838.01"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTERNAL_CONTRA, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.OVERPAYMENT, "-9500"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "1838.01")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
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
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_only_balloon_loan_balloon_delta_days_0(self):
        start = datetime(year=2020, month=1, day=11, tzinfo=timezone.utc)
        one_month_after_loan_start = start + relativedelta(months=1, minutes=1)
        before_first_payment = start + relativedelta(months=1, days=9, minutes=5)
        after_first_payment = start + relativedelta(months=1, days=9, hours=20)
        before_final_repayment_day_schedule = start + relativedelta(months=2, days=9, seconds=30)
        after_final_repayment_day_schedule = start + relativedelta(months=2, days=9, minutes=5)
        after_failed_final_deposit = start + relativedelta(months=2, days=9, hours=13)
        after_final_deposit = start + relativedelta(months=2, days=9, hours=20)
        end = start + relativedelta(months=3)

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
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "26.32892"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "26.32892"),
                        ],
                    },
                },
            ),
            SubTest(
                description="interest moved to interest due after first repayment date",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="33.97",
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
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "33.97"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
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
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
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
                description="principle moves to principle due on final repayment date",
                expected_balances_at_ts={
                    before_final_repayment_day_schedule: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "24.63028"),
                            (dimensions.ACCRUED_INTEREST, "24.63028"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "24.63028"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "58.60028"),
                        ],
                    },
                    after_final_repayment_day_schedule: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "10000"),
                            (dimensions.INTEREST_DUE, "24.63"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "58.60"),
                        ],
                    },
                },
            ),
            SubTest(
                description="a payment of more than the outstanding total fails",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="10024.64",
                        event_datetime=datetime(
                            year=2020, month=3, day=20, hour=12, tzinfo=timezone.utc
                        ),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    after_failed_final_deposit: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "10000"),
                            (dimensions.INTEREST_DUE, "24.63"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "58.60"),
                        ],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=after_failed_final_deposit - relativedelta(hours=1),
                        account_id=accounts.LOAN_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Cannot pay more than is owed",
                    )
                ],
            ),
            SubTest(
                description="check final repayment clears balances and triggers closure WF",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="10024.63",
                        event_datetime=datetime(
                            year=2020, month=3, day=20, hour=16, tzinfo=timezone.utc
                        ),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    after_final_deposit: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "58.60"),
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
            template_params=interest_only_template_params,
            instance_params=interest_only_instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_only_balloon_loan_with_date_delta(self):
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

        instance_params = interest_only_instance_params.copy()
        instance_params["balloon_payment_days_delta"] = "35"

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
                        value="0",
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
                        value="10000",
                    ),
                ],
            ),
            SubTest(
                description="interest moved to interest due after first repayment date",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="33.97",
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
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "33.97"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
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
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
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
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_first_payment,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_principal",
                        value="10000",
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
                        value="33.97",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_balloon_payment_amount",
                        value="10000",
                    ),
                ],
            ),
            SubTest(
                description="Check second repayment event and payment clears due",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="24.63",
                        event_datetime=datetime(
                            year=2020, month=3, day=20, hour=12, tzinfo=timezone.utc
                        ),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    before_second_repayment_event: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "24.63028"),
                            (dimensions.ACCRUED_INTEREST, "24.63028"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "24.63028"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "58.60028"),
                        ],
                    },
                    after_second_repayment_event: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "24.63"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "58.60"),
                        ],
                    },
                    after_second_deposit: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "58.60"),
                        ],
                    },
                },
            ),
            SubTest(
                description="check interest accrued after theoretical final repayment",
                expected_balances_at_ts={
                    day_after_theoretical_final_repayment_event: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.84932"),
                            (dimensions.ACCRUED_INTEREST, "0.84932"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0.84932"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "59.44932"),
                        ],
                    },
                    before_balloon_payment_event: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "29.72620"),
                            (dimensions.ACCRUED_INTEREST, "29.72620"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "29.72620"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "88.32620"),
                        ],
                    },
                    after_balloon_payment_event: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "10000"),
                            (dimensions.INTEREST_DUE, "29.73"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "88.33"),
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
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=day_after_theoretical_final_repayment_event,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="remaining_principal",
                        value="10000",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=day_after_theoretical_final_repayment_event,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="total_outstanding_debt",
                        value="10000.85",
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
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="expected_balloon_payment_amount",
                        value="10000",
                    ),
                ],
            ),
            SubTest(
                description="check payment clears due amounts and check schedules",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="10029.73",
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
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "88.33"),
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
            template_params=interest_only_template_params,
            instance_params=instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_only_balloon_loan_with_repayment_day_change(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, days=16)

        instance_params = interest_only_instance_params.copy()
        instance_params["total_term"] = "2"
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
            template_params=interest_only_template_params,
            instance_params=instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_overpayment_interest_only_balloon_loan(self):
        start = datetime(year=2020, month=1, day=11, tzinfo=timezone.utc)
        overpayment_datetime = start + relativedelta(days=21, hours=12)
        first_repayment_datetime = start + relativedelta(months=1, days=9, hours=12)
        final_repayment_datetime = start + relativedelta(months=2, days=9, hours=12)
        end = start + relativedelta(months=2, days=11)

        sub_tests = [
            SubTest(
                description="overpayment incurs fee and reduces daily accrued interest",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="2000",
                        event_datetime=overpayment_datetime,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    # First day accrues interest of 0.84932
                    start
                    + relativedelta(days=1, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.84932"),
                            (dimensions.ACCRUED_INTEREST, "0.84932"),
                            (dimensions.OVERPAYMENT, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0.84932"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0.84932"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    # accrued_interest = round(daily_interest_rate * principal ,5) * days
                    #                  = round((0.031 / 365) * 10000 ,5) * 21
                    overpayment_datetime
                    - relativedelta(hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "17.83572"),
                            (dimensions.ACCRUED_INTEREST, "17.83572"),
                            (dimensions.OVERPAYMENT, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "17.83572"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "17.83572"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    overpayment_datetime
                    + relativedelta(hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "17.83572"),
                            (dimensions.ACCRUED_INTEREST, "17.83572"),
                            (dimensions.OVERPAYMENT, "-1900"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "17.83572"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "17.83572"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "100"),
                        ],
                    },
                    # After overpayment daily interest accrued is reduced to 0.68795
                    # 17.83572 + 0.68795 = 18.52367
                    overpayment_datetime
                    + relativedelta(days=1, hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "18.68504"),
                            (dimensions.ACCRUED_INTEREST, "18.52367"),
                            (dimensions.OVERPAYMENT, "-1900"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "18.52367"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "18.52367"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "100"),
                        ],
                    },
                },
            ),
            SubTest(
                description="interest due reflects the reduced accrued interest"
                " then first repayment nets of interest due",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="30.91",
                        event_datetime=first_repayment_datetime,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    first_repayment_datetime
                    - relativedelta(hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "30.91"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.OVERPAYMENT, "-1900"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "30.91"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "100"),
                        ],
                    },
                    first_repayment_datetime
                    + relativedelta(hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.OVERPAYMENT, "-1900"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "30.91"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "100"),
                        ],
                    },
                },
            ),
            SubTest(
                description="final balloon payment processed correctly "
                " overpayment address netted off after loan closure",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.LOAN_ACCOUNT,
                        amount="8119.95",
                        event_datetime=final_repayment_datetime,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    final_repayment_datetime
                    - relativedelta(hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "1900"),
                            (dimensions.PRINCIPAL_DUE, "8100"),
                            (dimensions.INTEREST_DUE, "19.95"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.OVERPAYMENT, "-1900"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "50.86"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "100"),
                        ],
                    },
                    final_repayment_datetime
                    + relativedelta(hours=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "1900"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
                            (dimensions.OVERPAYMENT, "-1900"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "50.86"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "100"),
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
            template_params=interest_only_template_params,
            instance_params=interest_only_instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_only_balloon_loan_overdue_balances(self):
        start = datetime(year=2020, month=1, day=11, tzinfo=timezone.utc)
        one_month_after_loan_start = start + relativedelta(months=1, minutes=1)

        before_first_repayment_day = start + relativedelta(months=1, days=9)
        after_first_repayment_day = start + relativedelta(months=1, days=9, hours=1)
        end = start + relativedelta(months=1, days=12)

        instance_params = interest_only_instance_params.copy()
        instance_params["total_term"] = "2"

        template_params = interest_only_template_params.copy()
        template_params["repayment_period"] = "1"

        sub_tests = [
            SubTest(
                description="interest accrued correctly",
                expected_balances_at_ts={
                    start: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST, "0"),
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
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "26.32892"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "26.32892"),
                        ],
                    },
                },
            ),
            SubTest(
                description="interest moved to interest due after first repayment date",
                expected_balances_at_ts={
                    # First repayment date is 40 days after the loan start
                    # so more interest has been accrued
                    before_first_repayment_day: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "33.12348"),
                            (dimensions.ACCRUED_INTEREST, "33.12348"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "33.12348"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "33.12348"),
                        ],
                    },
                    after_first_repayment_day: {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            # 1 additional accrual event before
                            # repayment_day schedule is run
                            (dimensions.INTEREST_DUE, "33.97"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
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
                        value="0",
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
                        value="2020-02-21",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.LOAN_ACCOUNT,
                        name="total_early_repayment_amount",
                        value="10526.32",
                    ),
                ],
            ),
            SubTest(
                description="interest due moved to overdue after missing payment "
                "and interest is accrued on overdue address",
                expected_balances_at_ts={
                    after_first_repayment_day
                    + relativedelta(days=1): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "33.97"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.84932"),
                            (dimensions.ACCRUED_INTEREST, "0.84932"),
                            # late repayment fee of 15
                            (dimensions.PENALTIES, "15"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0.84932"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "34.81932"),
                        ],
                        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "15")
                        ],
                        accounts.INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                    after_first_repayment_day
                    + relativedelta(days=2): {
                        accounts.LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "33.97"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "1.69864"),
                            (dimensions.ACCRUED_INTEREST, "1.69864"),
                            # 15 + ROUND(ROUND(0.24+0.031)/365,10)*33.97,5)
                            # 15 + 0.03
                            (dimensions.PENALTIES, "15.03"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "1.69864"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "35.66864"),
                        ],
                        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "15")
                        ],
                        accounts.INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0.03")
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
