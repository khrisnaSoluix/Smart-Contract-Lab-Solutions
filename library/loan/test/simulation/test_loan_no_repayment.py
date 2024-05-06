# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

# library
from library.loan.contracts.template import loan
from library.loan.test import accounts, dimensions, files, parameters
from library.loan.test.simulation.common import LoanTestBase

# inception sdk
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    ContractConfig,
    ContractNotificationResourceType,
    ExpectedContractNotification,
    ExpectedDerivedParameter,
    ExpectedSchedule,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_account_product_version_update_instruction,
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
)

no_repayment_instance_params = {
    **parameters.loan_instance_params,
    loan.PARAM_FIXED_RATE_LOAN: "True",
    loan.balloon_payments.PARAM_BALLOON_PAYMENT_DAYS_DELTA: "0",
    loan.disbursement.PARAM_PRINCIPAL: "100000",
    loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "1",
    loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.02",
    loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "36",
}

no_repayment_template_params = {
    **parameters.loan_template_params,
    loan.PARAM_AMORTISATION_METHOD: "no_repayment",
    loan.PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST: "no_capitalisation",
    loan.PARAM_PENALTY_INCLUDES_BASE_RATE: "True",
    loan.overdue.PARAM_REPAYMENT_PERIOD: "10",
    loan.overpayment.PARAM_OVERPAYMENT_FEE_RATE: "0.05",
    loan.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: "reduce_term",
}

default_simulation_start_date = datetime(year=2020, month=1, day=1, tzinfo=ZoneInfo("UTC"))


class LoanNoRepaymentConversionTest(LoanTestBase):
    def test_loan_top_up_balloon_payment_schedule_no_conversion(self):
        # Test Parameters
        start = default_simulation_start_date
        end = start + relativedelta(months=1, days=10)

        instance_params = {
            **no_repayment_instance_params,
            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "1",
            loan.balloon_payments.PARAM_BALLOON_PAYMENT_DAYS_DELTA: "5",
        }
        expected_disbursement = Decimal(instance_params[loan.disbursement.PARAM_PRINCIPAL])
        template_params = no_repayment_template_params.copy()
        template_params[loan.overpayment.PARAM_OVERPAYMENT_FEE_RATE] = "0.00"

        sub_tests = [
            SubTest(
                description="check schedules and balances after account opening",
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0.00")),
                            (dimensions.PRINCIPAL, expected_disbursement),
                            (dimensions.EMI, Decimal("0.00")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, expected_disbursement)],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        account_id=self.loan_account_id,
                        timestamp=start,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-02-06",
                    )
                ],
            ),
            SubTest(
                description="check schedule runs at time",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[datetime(2020, 2, 6, 0, 1, 0, tzinfo=ZoneInfo("UTC"))],
                        event_id=loan.balloon_payments.BALLOON_PAYMENT_EVENT,
                        account_id=self.loan_account_id,
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
            debug=False,
        )
        self.run_test_scenario(test_scenario, smart_contracts=[])

    def test_loan_top_up_when_top_up_parameter_set_to_true(self):
        # Test Parameters
        start = default_simulation_start_date
        end = start + relativedelta(months=2, days=16)

        instance_params = {
            **no_repayment_instance_params,
            loan.balloon_payments.PARAM_BALLOON_PAYMENT_DAYS_DELTA: "5",
            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "1",
        }

        template_params = {**no_repayment_template_params}

        conversion = start + relativedelta(days=10)

        convert_to_version_id = "6"
        convert_to_contract_config = ContractConfig(
            contract_content=self.smart_contract_path_to_content[str(files.LOAN_CONTRACT)],
            smart_contract_version_id=convert_to_version_id,
            template_params=template_params,
            account_configs=[],
        )
        expected_disbursement = Decimal(instance_params[loan.disbursement.PARAM_PRINCIPAL])
        sub_tests = [
            SubTest(
                description="check schedules and balances after account opening",
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0.00")),
                            (dimensions.PRINCIPAL, expected_disbursement),
                            (dimensions.EMI, Decimal("0.00")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, expected_disbursement)],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        account_id=self.loan_account_id,
                        timestamp=start,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-02-06",
                    )
                ],
            ),
            SubTest(
                description="Conversion creates new schedules",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=conversion - relativedelta(seconds=1),
                        account_id=self.loan_account_id,
                        **{
                            loan.disbursement.PARAM_PRINCIPAL: "200000",
                            # increase the total term by 1
                            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "2",
                            loan.PARAM_TOP_UP: "true",
                        },
                    ),
                    create_account_product_version_update_instruction(
                        timestamp=conversion,
                        account_id=self.loan_account_id,
                        product_version_id=convert_to_version_id,
                    ),
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        account_id=self.loan_account_id,
                        timestamp=conversion,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-03-06",
                    )
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[datetime(2020, 3, 6, 0, 1, 0, tzinfo=ZoneInfo("UTC"))],
                        event_id=loan.balloon_payments.BALLOON_PAYMENT_EVENT,
                        account_id=self.loan_account_id,
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
            debug=True,
        )
        self.run_test_scenario(test_scenario, smart_contracts=[convert_to_contract_config])


class LoanNoRepaymentBalloonTest(LoanTestBase):
    def test_balloon_payment_schedule_gets_run_no_repayment(self):
        """
        Check balloon payment schedule gets run at correct time and due amount calc
        does not run
        """
        # redefined this date explicitly here as the relationship with due amount calculation day
        # is crucial to test coverage. If start day is 5 the first schedule run would be later in
        # order to be >=1 month from start
        start = datetime(year=2020, month=1, day=1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **no_repayment_instance_params,
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "1",
            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "1",
        }
        balloon_payment_date = start.replace(hour=0, minute=1, second=0) + relativedelta(
            months=1,
            days=int(instance_params[loan.balloon_payments.PARAM_BALLOON_PAYMENT_DAYS_DELTA]),
        )
        end = start + relativedelta(months=1, days=2)

        sub_tests = [
            SubTest(
                description="check balloon payment schedule is run",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[balloon_payment_date],
                        event_id=loan.balloon_payments.BALLOON_PAYMENT_EVENT,
                        account_id=self.loan_account_id,
                    ),
                    ExpectedSchedule(
                        run_times=[],
                        count=0,
                        event_id=loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                        account_id=self.loan_account_id,
                    ),
                ],
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=no_repayment_template_params,
            instance_params=instance_params,
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
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "5.47945"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "5.47945"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-5.47945")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="36",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="0.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="100000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2023-01-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.overdue.PARAM_NEXT_OVERDUE_DATE,
                        value="2023-01-11",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.early_repayment.PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT,
                        value="105263.16",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.balloon_payments.PARAM_EXPECTED_BALLOON_PAYMENT_AMOUNT,
                        value="100000",
                    ),
                ],
            ),
            SubTest(
                description="check daily interest accrual day 2",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=2, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "10.95890"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "10.95890"),
                            (dimensions.INTEREST_DUE, "0.00"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.INTEREST_OVERDUE, "0.00"),
                            (dimensions.PRINCIPAL_OVERDUE, "0.00"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-10.95890")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                    },
                },
            ),
            SubTest(
                description="check balances at start of next month",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "164.38350"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "164.38350"),
                            (dimensions.INTEREST_DUE, "0.00"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.INTEREST_OVERDUE, "0.00"),
                            (dimensions.PRINCIPAL_OVERDUE, "0.00"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-164.38350")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                    },
                },
            ),
            SubTest(
                description="check balances 1 day into following month",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "169.86295"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "169.86295"),
                            (dimensions.INTEREST_DUE, "0.00"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.INTEREST_OVERDUE, "0.00"),
                            (dimensions.PRINCIPAL_OVERDUE, "0.00"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-169.86295")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(months=1, hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="35",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(months=1, hours=1),
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="0.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(months=1, hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="100169.86",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(months=1, hours=1),
                        account_id=self.loan_account_id,
                        name=loan.balloon_payments.PARAM_EXPECTED_BALLOON_PAYMENT_AMOUNT,
                        value="100000",
                    ),
                ],
            ),
            SubTest(
                description="check balances before balloon date",
                expected_balances_at_ts={
                    start
                    + relativedelta(years=3): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "5999.99775"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "5999.99775"),
                            (dimensions.INTEREST_DUE, "0.00"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.INTEREST_OVERDUE, "0.00"),
                            (dimensions.PRINCIPAL_OVERDUE, "0.00"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-5999.99775")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(years=3, seconds=-1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="1",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(years=3),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(years=3),
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="0.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(years=3),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="106000.00",
                    ),
                ],
            ),
            SubTest(
                description="check balances after balloon date",
                expected_balances_at_ts={
                    start
                    + relativedelta(years=3, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0.00"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (dimensions.PRINCIPAL_DUE, "100000"),
                            (dimensions.INTEREST_DUE, "6005.48"),
                            (dimensions.INTEREST_OVERDUE, "0.00"),
                            (dimensions.PRINCIPAL_OVERDUE, "0.00"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "6005.48")],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(years=3, hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(years=3, hours=1),
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="0.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(years=3, hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="106005.48",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(years=3, hours=1),
                        account_id=self.loan_account_id,
                        name=loan.balloon_payments.PARAM_EXPECTED_BALLOON_PAYMENT_AMOUNT,
                        value="0.00",
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
                                tzinfo=ZoneInfo("UTC"),
                            )
                        ],
                        event_id=loan.balloon_payments.BALLOON_PAYMENT_EVENT,
                        account_id=self.loan_account_id,
                        count=1,
                    ),
                ],
            ),
            SubTest(
                description="check payment clears due balances and emits notification",
                events=[
                    # outstanding balance = principal_due + interest_due = 100,000 + 6005.48
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="106005.48",
                        event_datetime=start + relativedelta(years=3, hours=5),
                        internal_account_id=accounts.DEPOSIT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(years=3, hours=6): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0.00"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0.00"),
                            (dimensions.INTEREST_DUE, "0.00"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.INTEREST_OVERDUE, "0.00"),
                            (dimensions.PRINCIPAL_OVERDUE, "0.00"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "6005.48")],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(years=3, hours=5),
                        notification_type=loan.CLOSURE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                        },
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=no_repayment_template_params,
            instance_params=no_repayment_instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_no_repayment_balloon_loan_capitalised_interest_daily(self):
        start = default_simulation_start_date + relativedelta(years=1)

        template_params = {
            **no_repayment_template_params,
            loan.PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST: "daily",
        }
        instance_params = {
            **no_repayment_instance_params,
            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "12",
        }

        end = start + relativedelta(years=1, days=2)

        sub_tests = [
            SubTest(
                description="check daily interest accrual day 1",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "5.47945",
                            ),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0.00"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-5.47945")
                        ],
                    },
                },
            ),
            SubTest(
                description="check daily interest accrual day 2",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=2, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100005.48"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "5.47975",
                            ),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "5.48"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "5.48")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-5.47975")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances at start of next month",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100159.02"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "5.48816",
                            ),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "159.02"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "159.02")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-5.48816")
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="12",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="0.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="100000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2022-01-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.overdue.PARAM_NEXT_OVERDUE_DATE,
                        value="2022-01-11",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.early_repayment.PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT,
                        value="105263.16",
                    ),
                ],
            ),
            SubTest(
                description="check balances 1 day into following month",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100164.51"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "5.48846",
                            ),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "164.51"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "164.51")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-5.48846")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances before balloon date",
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "102008.89"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "2008.89"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "5.58953",
                            ),
                            (dimensions.INTEREST_DUE, "0.00"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.INTEREST_OVERDUE, "0.00"),
                            (dimensions.PRINCIPAL_OVERDUE, "0.00"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "2008.89")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-5.58953")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances after balloon date",
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "2020.07"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0.00"),
                            (dimensions.INTEREST_DUE, "0.00"),
                            (dimensions.PRINCIPAL_DUE, "102020.07"),
                            (dimensions.INTEREST_OVERDUE, "0.00"),
                            (dimensions.PRINCIPAL_OVERDUE, "0.00"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "2020.07")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
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
                                tzinfo=ZoneInfo("UTC"),
                            )
                        ],
                        event_id=loan.balloon_payments.BALLOON_PAYMENT_EVENT,
                        account_id=self.loan_account_id,
                        count=1,
                    ),
                ],
            ),
            SubTest(
                description="check payment clears due balances and emits notification",
                events=[
                    # outstanding balance = principal_due = 102020.07
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="102020.07",
                        event_datetime=start + relativedelta(years=1, hours=5),
                        internal_account_id=accounts.DEPOSIT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1, hours=6): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "2020.07"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0.00"),
                            (dimensions.INTEREST_DUE, "0.00"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.INTEREST_OVERDUE, "0.00"),
                            (dimensions.PRINCIPAL_OVERDUE, "0.00"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "2020.07")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(years=1, hours=5),
                        notification_type=loan.CLOSURE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                        },
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_no_repayment_balloon_loan_capitalised_interest_monthly(self):
        start = default_simulation_start_date

        template_params = {
            **no_repayment_template_params,
            loan.PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST: "monthly",
        }
        instance_params = {
            **no_repayment_instance_params,
            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "12",
        }

        end = start + relativedelta(years=1, days=2)

        sub_tests = [
            SubTest(
                description="check daily interest accrual day 1",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0.00"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "5.47945",
                            ),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-5.47945")
                        ],
                    },
                },
            ),
            SubTest(
                description="check daily interest accrual day 2",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=2, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0.00"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "10.95890",
                            ),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-10.95890")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances at start of next month",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0.00"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "164.38350",
                            ),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-164.38350")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances 1 day into following month",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100164.38"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "164.38"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "5.48846",
                            ),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "164.38")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-5.48846")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances before balloon date",
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1, minutes=-1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "101845.44"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "1845.44"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "172.99767",
                            ),
                            (dimensions.INTEREST_DUE, "0.00"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.INTEREST_OVERDUE, "0.00"),
                            (dimensions.PRINCIPAL_OVERDUE, "0.00"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "1845.44")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-172.99767")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances after balloon date",
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0.00"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "2024.03"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0.00"),
                            (dimensions.INTEREST_DUE, "0.00"),
                            (dimensions.PRINCIPAL_DUE, "102024.03"),
                            (dimensions.INTEREST_OVERDUE, "0.00"),
                            (dimensions.PRINCIPAL_OVERDUE, "0.00"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "2024.03")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
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
                                tzinfo=ZoneInfo("UTC"),
                            )
                        ],
                        event_id=loan.balloon_payments.BALLOON_PAYMENT_EVENT,
                        account_id=self.loan_account_id,
                        count=1,
                    ),
                ],
            ),
            SubTest(
                description="check payment clears due balances and emits notification",
                events=[
                    # outstanding balance = principal_due = 102024.03
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="102024.03",
                        event_datetime=start + relativedelta(years=1, hours=5),
                        internal_account_id=accounts.DEPOSIT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1, hours=6): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "2024.03"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0.00"),
                            (dimensions.INTEREST_DUE, "0.00"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.INTEREST_OVERDUE, "0.00"),
                            (dimensions.PRINCIPAL_OVERDUE, "0.00"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "2024.03")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(years=1, hours=5),
                        notification_type=loan.CLOSURE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                        },
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_no_repayment_balloon_loan_no_capitalisation_with_overpayment(self):
        start = default_simulation_start_date

        instance_params = {
            **no_repayment_instance_params,
            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "12",
        }

        end = start + relativedelta(years=1, days=2)

        sub_tests = [
            SubTest(
                description="check daily interest accrual after first day",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "5.47945"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "5.47945"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-5.47945")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                    },
                },
            ),
            SubTest(
                description="check daily interest accrual on day 2 after" "an overpayment on day 1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="2000",
                        event_datetime=start + relativedelta(days=1, hours=2),
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                # OVERPAYMENT: 2000 * (1-0.05) = 1900 as a deduction fee from overpayment of 100
                expected_balances_at_ts={
                    start
                    + relativedelta(days=2, hours=2): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "98100"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0.00"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "10.85479"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "10.95890"),
                            (dimensions.INTEREST_DUE, "0.00"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.INTEREST_OVERDUE, "0.00"),
                            (dimensions.PRINCIPAL_OVERDUE, "0.00"),
                            (dimensions.OVERPAYMENT, "1900"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-10.85479")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(days=2, hours=2),
                        account_id=self.loan_account_id,
                        name=loan.balloon_payments.PARAM_EXPECTED_BALLOON_PAYMENT_AMOUNT,
                        value="98100",
                    ),
                ],
            ),
            SubTest(
                description="check balances at start of next month",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "98100"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "161.36431"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "164.3835"),
                            (dimensions.INTEREST_DUE, "0.00"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.INTEREST_OVERDUE, "0.00"),
                            (dimensions.PRINCIPAL_OVERDUE, "0.00"),
                            (dimensions.OVERPAYMENT, "1900"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-161.36431")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                    },
                },
            ),
            SubTest(
                description="check balances 1 day into following month",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "98100"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "166.73965"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "169.86295"),
                            (dimensions.INTEREST_DUE, "0.00"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.INTEREST_OVERDUE, "0.00"),
                            (dimensions.PRINCIPAL_OVERDUE, "0.00"),
                            (dimensions.OVERPAYMENT, "1900"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-166.73965")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                    },
                },
            ),
            SubTest(
                description="check balances at end of term before balloon date",
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "98100"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "1962.10321"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "1999.99925"),
                            (dimensions.INTEREST_DUE, "0.00"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.INTEREST_OVERDUE, "0.00"),
                            (dimensions.PRINCIPAL_OVERDUE, "0.00"),
                            (dimensions.OVERPAYMENT, "1900"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0.00"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-1962.10321")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                    },
                },
            ),
            SubTest(
                description="check balances after balloon payment date",
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (dimensions.PRINCIPAL_DUE, "98100"),
                            (dimensions.INTEREST_DUE, "1967.48"),
                            (dimensions.INTEREST_OVERDUE, "0.00"),
                            (dimensions.PRINCIPAL_OVERDUE, "0.00"),
                            (dimensions.OVERPAYMENT, "1900"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "1967.48")],
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
                                tzinfo=ZoneInfo("UTC"),
                            )
                        ],
                        event_id=loan.balloon_payments.BALLOON_PAYMENT_EVENT,
                        account_id=self.loan_account_id,
                        count=1,
                    ),
                ],
            ),
            SubTest(
                description="check payment clears due balances and emits notification",
                events=[
                    # outstanding balance = principal_due + interest_due = 98100 + 1967.48
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="100067.48",
                        event_datetime=start + relativedelta(years=1, days=1, hours=7),
                        internal_account_id=accounts.DEPOSIT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1, days=1, hours=8): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            # ACCRUED_EXPECTED_INTEREST = EMI_PRINCIPAL_EXCESS * overpayment balance
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.10619"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.INTEREST_DUE, "0.00"),
                            (dimensions.INTEREST_OVERDUE, "0.00"),
                            (dimensions.PRINCIPAL_OVERDUE, "0.00"),
                            (dimensions.OVERPAYMENT, "1900"),
                            # This gets updated at the final balloon payment event.
                            (dimensions.EMI_PRINCIPAL_EXCESS, "38"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "1967.48")],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(years=1, days=1, hours=7),
                        notification_type=loan.CLOSURE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                        },
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=no_repayment_template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_no_repayment_balloon_loan_capitalised_interest_daily_with_overpayment(
        self,
    ):
        start = default_simulation_start_date

        template_params = {
            **no_repayment_template_params,
            loan.PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST: "daily",
        }
        instance_params = {
            **no_repayment_instance_params,
            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "12",
        }

        end = start + relativedelta(years=1, days=2)

        sub_tests = [
            SubTest(
                description="check daily interest accrual day 1",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "5.47945",
                            ),
                            (dimensions.OVERPAYMENT, "0.00"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-5.47945")
                        ],
                    },
                },
            ),
            SubTest(
                description="check daily interest accrual day 9 before overpayment",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=9, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100043.84"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "43.84"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "5.48185",
                            ),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "43.84")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-5.48185")
                        ],
                    },
                },
            ),
            SubTest(
                description="check daily interest accrual day 10 after an overpayment on day 9",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="10000",
                        event_datetime=start + relativedelta(days=9, hours=2),
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=10, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "90549.32"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "49.32"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "4.96160",
                            ),
                            (dimensions.OVERPAYMENT, "9500"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "49.32")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-4.96160")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances at start of next month, 31/01",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "90648.59"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "148.59"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "4.96704",
                            ),
                            (dimensions.OVERPAYMENT, "9500"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "148.59")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-4.96704")
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="12",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="0.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="100000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2021-01-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.overdue.PARAM_NEXT_OVERDUE_DATE,
                        value="2021-01-11",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.early_repayment.PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT,
                        value="105263.16",
                    ),
                ],
            ),
            SubTest(
                description="check balances before balloon date",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=12): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "92327.89"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "1827.89"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "5.05906",
                            ),
                            (dimensions.INTEREST_DUE, "0.00"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.INTEREST_OVERDUE, "0.00"),
                            (dimensions.PRINCIPAL_OVERDUE, "0.00"),
                            (dimensions.OVERPAYMENT, "9500"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "1827.89")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-5.05906")
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances after balloon date",
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (
                                dimensions.CAPITALISED_INTEREST_TRACKER,
                                "1838.01",
                            ),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0.00"),
                            (dimensions.INTEREST_DUE, "0.00"),
                            # principal + cap_int + add_cap_int + overpayment)
                            # 100000 +  (1827.89 + 5.05906) + 5.05934 - 9500 = 92338.01
                            # where 5.05934 is the add_int accrued on the balloon payment date
                            (
                                dimensions.PRINCIPAL_DUE,
                                "92338.01",
                            ),
                            (dimensions.INTEREST_OVERDUE, "0.00"),
                            (dimensions.PRINCIPAL_OVERDUE, "0.00"),
                            (dimensions.OVERPAYMENT, "9500"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "1838.01")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
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
                                tzinfo=ZoneInfo("UTC"),
                            )
                        ],
                        event_id=loan.balloon_payments.BALLOON_PAYMENT_EVENT,
                        account_id=self.loan_account_id,
                        count=1,
                    ),
                ],
            ),
            SubTest(
                description="check payment clears due balances and emits notification",
                events=[
                    # outstanding balance = principal_due = 92338.01
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="92338.01",
                        event_datetime=start + relativedelta(years=1, hours=5),
                        internal_account_id=accounts.DEPOSIT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1, hours=6): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0.0"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "1838.01"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.00"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.00"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0.00"),
                            (dimensions.INTEREST_DUE, "0.00"),
                            (dimensions.PRINCIPAL_DUE, "0.00"),
                            (dimensions.INTEREST_OVERDUE, "0.00"),
                            (dimensions.PRINCIPAL_OVERDUE, "0.00"),
                            (dimensions.OVERPAYMENT, "9500"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.00")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "1838.01")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0.00")
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(years=1, hours=5),
                        notification_type=loan.CLOSURE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                        },
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)
