# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from dateutil.relativedelta import relativedelta
from decimal import Decimal

# library
from library.loan.contracts.template import loan
from library.loan.test import accounts, dimensions, parameters
from library.loan.test.simulation.common import LoanTestBase

# inception sdk
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    ContractNotificationResourceType,
    ExpectedContractNotification,
    ExpectedDerivedParameter,
    ExpectedSchedule,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_flag_definition_event,
    create_flag_event,
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_template_parameter_change_event,
    update_account_status_pending_closure,
)


class LoanDecliningPrincipalTest(LoanTestBase):
    loan_instance_params = {
        **LoanTestBase.loan_instance_params,
        loan.disbursement.PARAM_PRINCIPAL: "1000",
    }
    loan_template_params = {
        **LoanTestBase.loan_template_params,
        loan.overpayment.PARAM_OVERPAYMENT_FEE_RATE: "0",
    }

    def test_interest_accrual_variable_rate_including_overpayment_reduce_emi(self):
        start = self.default_simulation_start_datetime
        end = start + relativedelta(months=2, days=28)
        template_params = {
            **self.loan_template_params,
            loan.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: "reduce_emi",
        }

        first_accrual_event = start + relativedelta(days=1, seconds=1)
        final_non_emi_accrued_interest_event = first_accrual_event + relativedelta(days=26)

        first_application_event = start + relativedelta(months=1, days=27, minutes=1)
        first_repayment = first_application_event + relativedelta(seconds=1)

        second_application_event = first_application_event + relativedelta(months=1)
        third_application_event = second_application_event + relativedelta(months=1)

        first_overdue_event = first_application_event + relativedelta(days=7)
        second_overdue_event = second_application_event + relativedelta(days=7)

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("1000"))],
                    }
                },
            ),
            SubTest(
                description="check balances after first accrual",
                # accrued_interest = daily_interest_rate * principal
                # (0.032 + -0.001) / 365 * 1000 = 0.08493
                expected_balances_at_ts={
                    first_accrual_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.08493")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.08493")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.08493"))
                        ],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_accrual_event,
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="84.74",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_accrual_event,
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value=str(first_application_event.date()),
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_accrual_event,
                        account_id=self.loan_account_id,
                        name=loan.overdue.PARAM_NEXT_OVERDUE_DATE,
                        value=str(first_overdue_event.date()),
                    ),
                ],
            ),
            SubTest(
                description="check correct balance at end of non-emi accrued interest period",
                # 0.08493 * 27
                expected_balances_at_ts={
                    final_non_emi_accrued_interest_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.29311")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("2.29311")),
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance at start of emi accrued interest period",
                expected_balances_at_ts={
                    final_non_emi_accrued_interest_event
                    + relativedelta(days=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.37804")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("2.37804")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-2.37804"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance at end of emi accrued interest period",
                expected_balances_at_ts={
                    first_application_event
                    - relativedelta(seconds=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("4.92594")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("4.92594")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-4.92594"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance after due amount event",
                expected_balances_at_ts={
                    first_application_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("917.90")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("4.93")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.10")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("4.93"))
                        ],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_application_event,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="11",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_application_event,
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value=str(second_application_event.date()),
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_application_event,
                        account_id=self.loan_account_id,
                        name=loan.overdue.PARAM_NEXT_OVERDUE_DATE,
                        value=str(first_overdue_event.date()),
                    ),
                ],
            ),
            SubTest(
                description="Make an overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # total due + 100 overpayment
                        amount="187.03",
                        event_datetime=first_repayment,
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    first_repayment: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("817.90")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("100")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("100"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("4.93"))
                        ],
                    }
                },
                # we expect the remaining_term derived parameter to remain unchanged as a result of
                # the 100 overpayment since the preference is to reduce emi
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_repayment + relativedelta(seconds=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="11",
                    )
                ],
            ),
            SubTest(
                description="Second application event",
                expected_balances_at_ts={
                    second_application_event
                    - relativedelta(seconds=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("817.90")),
                            (dimensions.EMI, Decimal("84.74")),
                            # round(round(0.031/365, 10) * 817.90, 5) * 28 = 1.94516
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("1.94516")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("100")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("100"),
                            ),
                            # round(round(0.031/365, 10) * 917.90, 5) * 28 = 2.18288
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("2.18288")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-1.94516"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("4.93"))
                        ],
                    },
                    second_application_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("744.34")),
                            # emi reduced as a result of the overpayment
                            (dimensions.EMI, Decimal("75.51")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("1.95")),
                            (dimensions.PRINCIPAL_DUE, Decimal("73.56")),
                            (dimensions.OVERPAYMENT, Decimal("100")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0.23")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("6.88"))
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=second_application_event,
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="75.51",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_application_event,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="10",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_application_event,
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value=str((third_application_event).date()),
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_application_event,
                        account_id=self.loan_account_id,
                        name=loan.overdue.PARAM_NEXT_OVERDUE_DATE,
                        value=str(second_overdue_event.date()),
                    ),
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            debug=False,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_accrual_variable_rate_including_overpayment_reduce_term(self):
        start = self.default_simulation_start_datetime
        end = start + relativedelta(months=2, days=28)
        template_params = {
            **self.loan_template_params,
            loan.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: "reduce_term",
        }

        first_accrual_event = start + relativedelta(days=1, seconds=1)
        final_non_emi_accrued_interest_event = first_accrual_event + relativedelta(days=26)

        first_application_event = start + relativedelta(months=1, days=27, minutes=1)
        first_repayment = first_application_event + relativedelta(seconds=1)

        second_application_event = first_application_event + relativedelta(months=1)
        third_application_event = second_application_event + relativedelta(months=1)

        first_overdue_event = first_application_event + relativedelta(days=7)
        second_overdue_event = second_application_event + relativedelta(days=7)

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("1000"))],
                    }
                },
            ),
            SubTest(
                description="check balances after first accrual",
                # accrued_interest = daily_interest_rate * principal
                # (0.032 + -0.001) / 365 * 1000 = 0.08493
                expected_balances_at_ts={
                    first_accrual_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.08493")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.08493")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.08493"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance at end of non-emi accrued interest period",
                # 0.08493 * 27
                expected_balances_at_ts={
                    final_non_emi_accrued_interest_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.29311")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("2.29311")),
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance at start of emi accrued interest period",
                expected_balances_at_ts={
                    final_non_emi_accrued_interest_event
                    + relativedelta(days=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.37804")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("2.37804")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-2.37804"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance at end of emi accrued interest period",
                expected_balances_at_ts={
                    first_application_event
                    - relativedelta(seconds=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("4.92594")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("4.92594")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-4.92594"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance after due amount event",
                expected_balances_at_ts={
                    first_application_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("917.90")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("4.93")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.10")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("4.93"))
                        ],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_application_event,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="11",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_application_event,
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value=str(second_application_event.date()),
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_application_event,
                        account_id=self.loan_account_id,
                        name=loan.overdue.PARAM_NEXT_OVERDUE_DATE,
                        value=str(first_overdue_event.date()),
                    ),
                ],
            ),
            SubTest(
                description="Make an overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # total due + 100 overpayment
                        amount="187.03",
                        event_datetime=first_repayment,
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    first_repayment: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("817.90")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("100")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("100"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("4.93"))
                        ],
                    }
                },
                # we expect the remaining_term derived parameter to decrease by 1 as a result of
                # the 100 overpayment
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_repayment,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="10",
                    )
                ],
            ),
            SubTest(
                description="Second application event",
                expected_balances_at_ts={
                    second_application_event
                    - relativedelta(seconds=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("817.90")),
                            (dimensions.EMI, Decimal("84.74")),
                            # round(round(0.031/365, 10) * 817.90, 5) * 28 = 1.94516
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("1.94516")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("100")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("100"),
                            ),
                            # round(round(0.031/365, 10) * 917.90, 5) * 28 = 2.18288
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("2.18288")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-1.94516"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("4.93"))
                        ],
                    },
                    second_application_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("735.11")),
                            # no reamortisation as a result of the overpayment
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("1.95")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.79")),
                            (dimensions.OVERPAYMENT, Decimal("100")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0.23")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("6.88"))
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=second_application_event,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="9",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_application_event,
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value=str((third_application_event).date()),
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_application_event,
                        account_id=self.loan_account_id,
                        name=loan.overdue.PARAM_NEXT_OVERDUE_DATE,
                        value=str((second_overdue_event).date()),
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_application_event,
                        account_id=self.loan_account_id,
                        name=loan.early_repayment.PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT,
                        value="819.85",
                    ),
                ],
            ),
            SubTest(
                description="Clear remaining debt with overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="819.85",
                        event_datetime=second_application_event + relativedelta(minutes=2),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    second_application_event
                    + relativedelta(minutes=2): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0")),
                            (dimensions.CAPITALISED_PENALTIES_TRACKER, Decimal("0")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("835.11")),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                Decimal("0"),
                            ),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                    }
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=second_application_event + relativedelta(minutes=2),
                        notification_type=loan.CLOSURE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                        },
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=second_application_event + relativedelta(minutes=2),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="0",
                    ),
                    # since remaining_term is zero, the next repayment datetime should be equal
                    # to the last execution datetime
                    ExpectedDerivedParameter(
                        timestamp=second_application_event + relativedelta(minutes=2),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value=str(second_application_event.date()),
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_application_event,
                        account_id=self.loan_account_id,
                        name=loan.overdue.PARAM_NEXT_OVERDUE_DATE,
                        value=str((second_overdue_event).date()),
                    ),
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            debug=False,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_accrual_variable_rate_with_rate_changes(self):
        start = self.default_simulation_start_datetime

        first_accrual_event = start + relativedelta(days=1, seconds=1)
        final_non_emi_accrued_interest_event = first_accrual_event + relativedelta(days=26)
        first_application_event = start + relativedelta(months=1, days=27, minutes=1)
        second_application_event = start + relativedelta(months=2, days=27, minutes=1)
        end = second_application_event + relativedelta(days=2)

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("1000"))],
                    }
                },
            ),
            SubTest(
                description="check balances after first accrual",
                # accrued_interest = daily_interest_rate * principal
                # (0.032 + -0.001) / 365 * 1000 = 0.08493
                expected_balances_at_ts={
                    first_accrual_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.08493")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.08493"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance at start of emi accrued interest period",
                expected_balances_at_ts={
                    final_non_emi_accrued_interest_event
                    + relativedelta(days=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.37804")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-2.37804"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance at end of emi accrued interest period",
                expected_balances_at_ts={
                    first_application_event
                    - relativedelta(seconds=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("4.92594")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-4.92594"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance after due amount event",
                expected_balances_at_ts={
                    first_application_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("917.90")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("4.93")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.10")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("4.93"))
                        ],
                    }
                },
            ),
            SubTest(
                description="pay due amounts",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # just the total due
                        amount=str(Decimal("4.93") + Decimal("82.10")),
                        event_datetime=first_application_event + relativedelta(hours=2),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    first_application_event
                    + relativedelta(hours=2): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("917.90")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("4.93"))
                        ],
                    }
                },
            ),
            SubTest(
                description="change interest rate on day 2 after due amount event",
                events=[
                    create_template_parameter_change_event(
                        timestamp=first_application_event + relativedelta(days=2, hours=12),
                        **{loan.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0.051"},
                    ),
                    create_instance_parameter_change_event(
                        timestamp=first_application_event + relativedelta(days=2, hours=12),
                        account_id=self.loan_account_id,
                        **{loan.variable_rate.PARAM_VARIABLE_RATE_ADJUSTMENT: "-0.002"},
                    ),
                ],
            ),
            SubTest(
                description="check balances after first accrual after rate change",
                # daily accrual before rate change:
                #   round(round((0.032 + -0.001) / 365, 10) * 917.9, 5) = 0.07796
                # daily accrual after rate change:
                #   round(round((0.051 + -0.002) / 365, 10) * 917.9, 5) = 0.12322
                # accrued interest = 0.07796 * 2 + 0.12322 = 0.27914
                expected_balances_at_ts={
                    first_application_event
                    + relativedelta(days=3, hours=12): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("917.90")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.27914")),
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance after second due event with reamortisation",
                expected_balances_at_ts={
                    second_application_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("835.76")),
                            (dimensions.EMI, Decimal("85.50")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("3.36")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.14")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("8.29"))
                        ],
                    }
                },
            ),
            SubTest(
                description="pay due amounts after reamortisation",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # just the total due
                        amount=str(Decimal("3.36") + Decimal("82.14")),
                        event_datetime=second_application_event + relativedelta(hours=2),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    second_application_event
                    + relativedelta(hours=2): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("835.76")),
                            (dimensions.EMI, Decimal("85.50")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                    }
                },
            ),
            SubTest(
                description="check balances after first accrual after reamortisation",
                # daily accrual after rate change: (0.05 + -0.001) / 365 * 835.76 = 0.11220
                expected_balances_at_ts={
                    second_application_event
                    + relativedelta(days=1, hours=12): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("835.76")),
                            (dimensions.EMI, Decimal("85.50")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.11220")),
                        ],
                    }
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_accrual_variable_rate_with_interest_rate_limits(self):
        start = self.default_simulation_start_datetime
        end = start + relativedelta(days=3, minutes=1)

        template_params = {
            **self.loan_template_params,
            loan.variable_rate.PARAM_ANNUAL_INTEREST_RATE_CAP: "0.035",
            loan.variable_rate.PARAM_ANNUAL_INTEREST_RATE_FLOOR: "0.030",
        }

        first_accrual_event = start + relativedelta(days=1, seconds=1)
        second_accrual_event = first_accrual_event + relativedelta(days=1)
        third_accrual_event = second_accrual_event + relativedelta(days=1)

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("1000"))],
                    }
                },
            ),
            SubTest(
                description="check balances after first accrual",
                # accrued_interest = daily_interest_rate * principal
                # (0.032 + -0.001) / 365 * 1000 = 0.08493
                expected_balances_at_ts={
                    first_accrual_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.08493")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.08493"))
                        ],
                    }
                },
            ),
            SubTest(
                description="Update variable rate adjustment to ensure interest cap is enforced",
                # accrued_interest = daily_interest_rate * principal
                # the interest rate cap should limit the daily interest accrued to
                # 0.035 / 365 * 1000 = 0.09589
                # 0.08493 + 0.09589 = 0.18082
                events=[
                    create_instance_parameter_change_event(
                        timestamp=second_accrual_event - relativedelta(minutes=1),
                        account_id=self.loan_account_id,
                        **{loan.variable_rate.PARAM_VARIABLE_RATE_ADJUSTMENT: "1.0"},
                    )
                ],
                expected_balances_at_ts={
                    second_accrual_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.18082")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.18082"))
                        ],
                    }
                },
            ),
            SubTest(
                description="Update variable rate adjustment to ensure interest floor is enforced",
                # accrued_interest = daily_interest_rate * principal
                # the interest rate floor should limit the daily interest accrued to
                # 0.030 / 365 * 1000 = 0.08219
                # 0.18082 + 0.08219 = 0.26301
                events=[
                    create_instance_parameter_change_event(
                        timestamp=third_accrual_event - relativedelta(minutes=1),
                        account_id=self.loan_account_id,
                        **{loan.variable_rate.PARAM_VARIABLE_RATE_ADJUSTMENT: "-1.0"},
                    )
                ],
                expected_balances_at_ts={
                    third_accrual_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.26301")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.26301"))
                        ],
                    }
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_accrual_variable_rate_with_repayment_holiday_increase_emi(self):
        start = self.default_simulation_start_datetime
        end = start + relativedelta(months=2, days=28)
        instance_params = {
            **self.loan_instance_params,
            loan.repayment_holiday.PARAM_REPAYMENT_HOLIDAY_IMPACT_PREFERENCE: (
                loan.repayment_holiday.INCREASE_EMI
            ),
        }
        first_accrual_event = start + relativedelta(days=1, seconds=1)
        first_application_event = start + relativedelta(months=1, days=27, minutes=1)
        second_application_event = first_application_event + relativedelta(months=1)

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                events=[
                    create_flag_definition_event(
                        flag_definition_id="REPAYMENT_HOLIDAY", timestamp=start
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("1000"))],
                    }
                },
            ),
            SubTest(
                description="check balances after first accrual",
                # accrued_interest = daily_interest_rate * principal
                # (0.032 + -0.001) / 365 * 1000 = 0.08493
                expected_balances_at_ts={
                    first_accrual_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.08493")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.08493")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.08493"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance at end of first repayment cycle",
                expected_balances_at_ts={
                    first_application_event
                    - relativedelta(seconds=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("4.92594")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("4.92594")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-4.92594"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance after due amount event with an active repayment "
                "holiday",
                events=[
                    create_flag_event(
                        timestamp=first_application_event - relativedelta(seconds=1),
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        effective_timestamp=first_application_event - relativedelta(seconds=1),
                        expiry_timestamp=first_application_event + relativedelta(seconds=1),
                        account_id=self.loan_account_id,
                    ),
                ],
                expected_balances_at_ts={
                    first_application_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("4.92594")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            # should increment since the preference is to increase_emi
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("4.92594")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-4.92594"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, Decimal("0"))],
                    }
                },
            ),
            SubTest(
                description="check correct balance at second due event",
                expected_balances_at_ts={
                    second_application_event
                    - relativedelta(seconds=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            # 4.92594 + round(round(0.031/365,10)*1000, 5) * 28 = 7.30398
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("7.30398")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("7.30398")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-7.30398"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, Decimal("0"))],
                    },
                    second_application_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("910.05")),
                            # reamortised with remaining_term = 11
                            (dimensions.EMI, Decimal("92.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            # 2.37 is emi interest and 4.92 is non-emi interest
                            (dimensions.INTEREST_DUE, Decimal("7.30")),
                            (dimensions.PRINCIPAL_DUE, Decimal("89.95")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            # should increment since the preference is to increase_emi
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("2")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("7.30"))
                        ],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            debug=False,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_accrual_variable_rate_with_repayment_holiday_increase_term(self):
        start = self.default_simulation_start_datetime
        end = start + relativedelta(months=2, days=28)
        instance_params = {
            **self.loan_instance_params,
            loan.repayment_holiday.PARAM_REPAYMENT_HOLIDAY_IMPACT_PREFERENCE: (
                loan.repayment_holiday.INCREASE_TERM
            ),
        }
        first_accrual_event = start + relativedelta(days=1, seconds=1)
        first_application_event = start + relativedelta(months=1, days=27, minutes=1)
        second_application_event = first_application_event + relativedelta(months=1)

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                events=[
                    create_flag_definition_event(
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        timestamp=start,
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("1000"))],
                    }
                },
            ),
            SubTest(
                description="check balances after first accrual",
                # accrued_interest = daily_interest_rate * principal
                # (0.032 + -0.001) / 365 * 1000 = 0.08493
                expected_balances_at_ts={
                    first_accrual_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.08493")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.08493")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.08493"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance at end of first repayment cycle",
                expected_balances_at_ts={
                    first_application_event
                    - relativedelta(seconds=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("4.92594")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("4.92594")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-4.92594"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance after due amount event with an active repayment "
                "holiday",
                events=[
                    create_flag_event(
                        timestamp=first_application_event - relativedelta(seconds=1),
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        effective_timestamp=first_application_event - relativedelta(seconds=1),
                        expiry_timestamp=first_application_event + relativedelta(seconds=1),
                        account_id=self.loan_account_id,
                    ),
                ],
                expected_balances_at_ts={
                    first_application_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("4.92594")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            # should not increment since the preference is to increase_term
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("4.92594")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-4.92594"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, Decimal("0"))],
                    }
                },
            ),
            SubTest(
                description="check correct balance at second due event",
                expected_balances_at_ts={
                    second_application_event
                    - relativedelta(seconds=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            # 4.92594 + round(round(0.031/365,10)*1000, 5) * 28 = 7.30398
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("7.30398")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("7.30398")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-7.30398"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, Decimal("0"))],
                    },
                    second_application_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("917.63")),
                            # no reamortisation
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            # 2.37 is emi interest and 4.92 is non-emi interest
                            (dimensions.INTEREST_DUE, Decimal("7.30")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.37")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("7.30"))
                        ],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            debug=False,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_accrual_fixed_rate(self):
        start = self.default_simulation_start_datetime
        end = start + relativedelta(days=28, minutes=2)
        instance_params = {**self.loan_instance_params, loan.PARAM_FIXED_RATE_LOAN: "true"}

        first_accrual_event = start + relativedelta(days=1, minutes=1)
        final_non_emi_accrued_interest_event = first_accrual_event + relativedelta(days=26)

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("83.79")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("1000"))],
                    }
                },
            ),
            SubTest(
                description="check balances after first accrual",
                # accrued_interest = daily_interest_rate * principal
                # (0.01) / 365 * 1000 = 0.08493
                expected_balances_at_ts={
                    first_accrual_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("83.79")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.02740")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.02740"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance at end of non-emi accrued interest period",
                # 0.02740 * 27
                expected_balances_at_ts={
                    final_non_emi_accrued_interest_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("83.79")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.73980")),
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance at start of emi accrued interest period",
                expected_balances_at_ts={
                    final_non_emi_accrued_interest_event
                    + relativedelta(days=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("83.79")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.76720")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.76720"))
                        ],
                    }
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params, debug=False
        )
        self.run_test_scenario(test_scenario)

    def test_accrue_interest_on_due_principal(self):
        start = self.default_simulation_start_datetime
        end = start + relativedelta(months=1, days=1, seconds=2)
        instance_params = {
            **self.loan_instance_params,
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "1",
        }
        template_params = {**self.loan_template_params, loan.PARAM_ACCRUE_ON_DUE_PRINCIPAL: "True"}

        first_accrual_event = start + relativedelta(days=1, seconds=1)
        first_application_event = start + relativedelta(months=1, minutes=1)

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("1000"))],
                    }
                },
            ),
            SubTest(
                description="check correct balance after first accrual event",
                expected_balances_at_ts={
                    first_accrual_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.08493")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.08493"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance after due amount calc",
                expected_balances_at_ts={
                    first_application_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("917.89")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.11")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, "2.63"),
                        ],
                    }
                },
            ),
            SubTest(
                description="Verify interest accrued on due principal after due amount calc",
                expected_balances_at_ts={
                    first_application_event
                    + relativedelta(days=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("917.89")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.11")),
                            (dimensions.EMI, Decimal("84.74")),
                            # 0.08439 daily accrual on PRINCIPAL + PRINCIPAL_DUE
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.08493")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.08493"))
                        ],
                    }
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            debug=False,
        )
        self.run_test_scenario(test_scenario)

    def test_accrue_interest_pending_capitalisation(self):
        start = self.default_simulation_start_datetime
        end = start + relativedelta(months=1, hours=1)
        instance_params = self.loan_instance_params.copy()
        instance_params = {
            **self.loan_instance_params,
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "1",
        }
        template_params = {**self.loan_template_params, loan.PARAM_ACCRUE_ON_DUE_PRINCIPAL: "True"}

        first_accrual_event = start + relativedelta(days=1, seconds=1)
        second_accrual_event = start + relativedelta(days=2, seconds=1)
        third_accrual_event = start + relativedelta(days=3, seconds=1)

        first_application_event = start + relativedelta(months=1, minutes=1)

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                events=[
                    create_flag_definition_event(
                        flag_definition_id="REPAYMENT_HOLIDAY", timestamp=start
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("1000"))],
                    }
                },
            ),
            SubTest(
                description="check correct balance after first accrual event",
                expected_balances_at_ts={
                    first_accrual_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.08493")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.08493"))
                        ],
                    }
                },
            ),
            SubTest(
                description="apply repayment holiday flag and check accrual to pending cap",
                events=[
                    create_flag_event(
                        timestamp=second_accrual_event,
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        effective_timestamp=second_accrual_event,
                        expiry_timestamp=third_accrual_event - relativedelta(hours=1),
                        account_id=self.loan_account_id,
                    )
                ],
                expected_balances_at_ts={
                    second_accrual_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.08493")),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                Decimal("0.08493"),
                            ),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.08493"))
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.08493"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check interest is capitalised after flag expiry",
                expected_balances_at_ts={
                    third_accrual_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            # all the previous interest pending capitalisation is rounded and
                            # rebalanced to principal + tracker
                            (dimensions.PRINCIPAL, Decimal("1000.08")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0.08")),
                            (dimensions.EMI, Decimal("84.74")),
                            # interest is accrued on the current principal + inflight principal to
                            # be capitalised, therefore second accrual event is on a principal
                            # balance of 1000.08
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.16987")),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, Decimal("0")),
                        ],
                        # this accrual is made as usual
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.16987"))
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("0.08"))
                        ],
                    }
                },
            ),
            SubTest(
                description="Apply due blocking flag for the due amount calculation event",
                events=[
                    create_flag_event(
                        timestamp=first_application_event - relativedelta(minutes=1),
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        effective_timestamp=first_application_event - relativedelta(minutes=1),
                        expiry_timestamp=first_application_event + relativedelta(minutes=1),
                        account_id=self.loan_account_id,
                    ),
                ],
                expected_balances_at_ts={
                    first_application_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000.08")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0.08")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.46325")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                Decimal("0.08494"),
                            ),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-2.46325"))
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.08494"))
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("0.08"))
                        ],
                    }
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            debug=False,
        )
        self.run_test_scenario(test_scenario)

    def test_monthly_rest_loan(self):
        start = self.default_simulation_start_datetime
        end = start + relativedelta(months=2, days=28)
        instance_params = {
            **self.loan_instance_params,
            loan.PARAM_INTEREST_ACCRUAL_REST_TYPE: "monthly",
        }

        first_accrual_event = start + relativedelta(days=1, seconds=1)
        final_non_emi_accrued_interest_event = first_accrual_event + relativedelta(days=26)

        first_application_event = start + relativedelta(months=1, days=27, minutes=1)
        second_application_event = first_application_event + relativedelta(months=1)

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.MONTHLY_REST_EFFECTIVE_PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("1000"))],
                    }
                },
            ),
            SubTest(
                description="check balances after first accrual",
                # accrued_interest = daily_interest_rate * principal
                # (0.032 + -0.001) / 365 * 1000 = 0.08493
                expected_balances_at_ts={
                    first_accrual_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.MONTHLY_REST_EFFECTIVE_PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.08493")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.08493"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance at end of non-emi accrued interest period",
                # 0.08493 * 27
                expected_balances_at_ts={
                    final_non_emi_accrued_interest_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.MONTHLY_REST_EFFECTIVE_PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.29311")),
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance at start of emi accrued interest period",
                expected_balances_at_ts={
                    final_non_emi_accrued_interest_event
                    + relativedelta(days=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.MONTHLY_REST_EFFECTIVE_PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.37804")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-2.37804"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance at end of emi accrued interest period",
                expected_balances_at_ts={
                    first_application_event
                    - relativedelta(seconds=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.MONTHLY_REST_EFFECTIVE_PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("4.92594")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-4.92594"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance after due amount event",
                expected_balances_at_ts={
                    first_application_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("917.90")),
                            (dimensions.MONTHLY_REST_EFFECTIVE_PRINCIPAL, Decimal("917.90")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("4.93")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.10")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("4.93"))
                        ],
                    }
                },
            ),
            SubTest(
                description="Overpay due balances",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="187.03",
                        event_datetime=first_application_event + relativedelta(hours=1),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    first_application_event
                    + relativedelta(hours=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("817.90")),
                            (dimensions.MONTHLY_REST_EFFECTIVE_PRINCIPAL, Decimal("917.90")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.OVERPAYMENT, Decimal("100")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("4.93"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance before second due amount event",
                expected_balances_at_ts={
                    second_application_event
                    - relativedelta(seconds=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("817.90")),
                            (dimensions.MONTHLY_REST_EFFECTIVE_PRINCIPAL, Decimal("917.90")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.OVERPAYMENT, Decimal("100")),
                            # accrued_interest = daily_interest_rate * principal * num days
                            # (0.032 + -0.001) / 365 * 917.9 * 31 = 0.07796 * 28 = 2.18288
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.18288")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-2.18288"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("4.93"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance after second due amount event",
                expected_balances_at_ts={
                    second_application_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("735.34")),
                            (dimensions.MONTHLY_REST_EFFECTIVE_PRINCIPAL, Decimal("735.34")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.OVERPAYMENT, Decimal("100")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("2.18")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.56")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("7.11"))
                        ],
                    }
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            debug=False,
        )
        self.run_test_scenario(test_scenario)

    def test_overdue_notifications_blocked_when_blocking_flag_applied(self):
        start = self.default_simulation_start_datetime

        instance_params = {
            **self.loan_instance_params,
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "1",
        }
        first_application_event = start + relativedelta(months=1, minutes=1)
        first_overdue_event = first_application_event + relativedelta(days=7, minute=0, second=2)
        end = first_overdue_event

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                events=[
                    create_flag_definition_event(
                        flag_definition_id="REPAYMENT_HOLIDAY", timestamp=start
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("1000"))],
                    }
                },
            ),
            SubTest(
                description="check balances after first due event",
                expected_balances_at_ts={
                    first_application_event: {
                        # accrued_interest = daily_interest_rate * principal
                        # (0.032 + -0.001) / 365 * 1000 = 0.08493
                        # 0.08493 * 31 = 2.63283
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("917.89")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("2.63")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.11")),
                        ],
                    }
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=first_application_event,
                        notification_type=loan.REPAYMENT_DUE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "repayment_amount": "84.74",
                            "overdue_date": str(first_overdue_event.date()),
                        },
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="check balances after overdue event are unchanged due to repayment "
                "holiday",
                events=[
                    create_flag_event(
                        timestamp=first_overdue_event - relativedelta(minutes=1),
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        effective_timestamp=first_overdue_event - relativedelta(minutes=1),
                        expiry_timestamp=first_overdue_event + relativedelta(minutes=1),
                        account_id=self.loan_account_id,
                    ),
                ],
                expected_balances_at_ts={
                    first_overdue_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("917.89")),
                            (dimensions.EMI, Decimal("84.74")),
                            # round(round(0.031/365, 10) * 917.89, 5) * 6
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.46776")),
                            (dimensions.INTEREST_DUE, Decimal("2.63")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.11")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            # no late repayment fee
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params, debug=False
        )
        self.run_test_scenario(test_scenario)

    def test_loan_full_cycle(self):
        """
        This test will verify the behaviour of a complete loan cycle, and will be slowly
        grow as more features are implemented (e.g. loan closure etc)
        """

        start = self.default_simulation_start_datetime
        end = start + relativedelta(months=4, days=1)
        instance_params = {
            **self.loan_instance_params,
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "1",
        }
        template_params = {
            **self.loan_template_params,
            loan.overpayment.PARAM_OVERPAYMENT_FEE_RATE: "0.05",
        }
        first_application_event = start + relativedelta(months=1, minutes=1)
        first_overdue_event = first_application_event + relativedelta(days=7, minute=0, second=2)
        first_check_delinquency_event = first_overdue_event + relativedelta(days=1)

        second_application_event = first_application_event + relativedelta(months=1)
        second_overdue_event = first_overdue_event + relativedelta(months=1)

        third_application_event = second_application_event + relativedelta(months=1)
        third_overdue_event = second_overdue_event + relativedelta(months=1)

        fourth_application_event = third_application_event + relativedelta(months=1)

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("1000"))],
                    }
                },
            ),
            SubTest(
                description="check balances before due event",
                expected_balances_at_ts={
                    first_application_event
                    - relativedelta(seconds=1): {
                        # accrued_interest = daily_interest_rate * principal
                        # (0.032 + -0.001) / 365 * 1000 = 0.08493
                        # 0.08493 * 31 = 2.63283
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.63283")),
                        ],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_application_event - relativedelta(seconds=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="12",
                    )
                ],
            ),
            SubTest(
                description="check balances after first due event",
                expected_balances_at_ts={
                    first_application_event: {
                        # accrued_interest = daily_interest_rate * principal
                        # (0.032 + -0.001) / 365 * 1000 = 0.08493
                        # 0.08493 * 31 = 2.63283
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("917.89")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("2.63")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.11")),
                        ],
                    }
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=first_application_event,
                        notification_type=loan.REPAYMENT_DUE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "repayment_amount": "84.74",
                            "overdue_date": str(first_overdue_event.date()),
                        },
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_application_event,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="11",
                    )
                ],
            ),
            SubTest(
                description="check balances after overdue event",
                expected_balances_at_ts={
                    first_overdue_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("917.89")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.54572")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("2.63")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("82.11")),
                            # late repayment fee
                            (dimensions.PENALTIES, Decimal("10")),
                        ],
                    }
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=first_overdue_event,
                        notification_type=loan.REPAYMENT_OVERDUE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "repayment_amount": str(Decimal("84.74")),
                            loan.PARAM_LATE_REPAYMENT_FEE: str(Decimal("10")),
                            "overdue_date": str(first_overdue_event.date()),
                        },
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="check delinquency event",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=first_check_delinquency_event,
                        notification_type=loan.MARK_DELINQUENT_NOTIFICATION,
                        notification_details={"account_id": self.loan_account_id},
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_check_delinquency_event],
                        event_id=loan.CHECK_DELINQUENCY,
                        account_id=self.loan_account_id,
                    )
                ],
            ),
            SubTest(
                description="check balances after second due event",
                expected_balances_at_ts={
                    second_application_event: {
                        # accrued_interest = daily_interest_rate * principal
                        # (0.032 + -0.001) / 365 * 917.89 = 0.07796
                        # 0.07796 * 28 = 2.18288
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("835.33")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("2.18")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.56")),
                            (dimensions.INTEREST_OVERDUE, Decimal("2.63")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("82.11")),
                            # daily penalty interest accrued and applied =
                            # (overdue balance) * (penalty interest rate) (2dp)
                            # (2.63 + 82.11) * ((0.24 + 0.032 - 0.001)/365) = 0.06
                            # total daily_accrual * days since overdue event
                            #  = 0.06* 21 = 1.26
                            # late repayment fee + penalty interest
                            (dimensions.PENALTIES, Decimal("11.26")),
                        ],
                    }
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=second_application_event,
                        notification_type=loan.REPAYMENT_DUE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "repayment_amount": "84.74",
                            "overdue_date": str(second_overdue_event.date()),
                        },
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=second_application_event,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="10",
                    )
                ],
            ),
            SubTest(
                description="check second overdue event",
                events=[
                    # set loan.PARAM_GRACE_PERIOD to 0 to verify notification is emitted by the
                    # overdue schedule
                    create_template_parameter_change_event(
                        timestamp=second_overdue_event - relativedelta(seconds=1),
                        **{loan.PARAM_GRACE_PERIOD: "0"},
                    ),
                    # remove accrual on overdue interest to verify behaviour
                    create_template_parameter_change_event(
                        timestamp=second_overdue_event + relativedelta(seconds=1),
                        **{loan.PARAM_PENALTY_COMPOUNDS_OVERDUE_INTEREST: "False"},
                    ),
                ],
                expected_balances_at_ts={
                    second_overdue_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("835.33")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.49665")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("4.81")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("164.67")),
                            # daily penalty interest accrued and applied =
                            # (overdue balance) * (penalty interest rate) (2dp)
                            # (2.63 + 82.11) * ((0.24)/365) = 0.06
                            # total daily_accrual * days since overdue event
                            # = 0.06 * 7 = 0.42
                            (dimensions.PENALTIES, Decimal("21.68")),
                        ],
                    }
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=second_overdue_event,
                        notification_type=loan.MARK_DELINQUENT_NOTIFICATION,
                        notification_details={"account_id": self.loan_account_id},
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                    ExpectedContractNotification(
                        timestamp=second_overdue_event,
                        notification_type=loan.REPAYMENT_OVERDUE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "repayment_amount": str(Decimal("84.74")),
                            loan.PARAM_LATE_REPAYMENT_FEE: str(Decimal("10")),
                            "overdue_date": str(second_overdue_event.date()),
                        },
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="check balances after third due event",
                expected_balances_at_ts={
                    third_application_event: {
                        # accrued_interest = daily_interest_rate * principal
                        # (0.032 + -0.001) / 365 * 835.33 = 0.07095
                        # 0.07095 * 31 = 2.18288
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("752.79")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("2.20")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.54")),
                            (dimensions.INTEREST_OVERDUE, Decimal("4.81")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("164.67")),
                            # now interest_overdue is not included in penalty accrual
                            # daily accrual = ((0.24 + 0.032 - 0.001)/365) * 164.67 = 0.12
                            # (31-7) * 0.12 = + 2.88
                            (dimensions.PENALTIES, Decimal("24.56")),
                        ],
                    }
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=third_application_event,
                        notification_type=loan.REPAYMENT_DUE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "repayment_amount": "84.74",
                            "overdue_date": str(third_overdue_event.date()),
                        },
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=third_application_event,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="9",
                    )
                ],
            ),
            SubTest(
                description="check balances after capitalising penalty interest",
                events=[
                    create_template_parameter_change_event(
                        timestamp=third_application_event + relativedelta(seconds=1),
                        **{loan.interest_capitalisation.PARAM_CAPITALISE_PENALTY_INTEREST: "True"},
                    ),
                ],
                expected_balances_at_ts={
                    third_application_event
                    + relativedelta(days=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("752.79")),
                            (dimensions.EMI, Decimal("84.74")),
                            # (0.032-0.001 * 752.79) / 365 (5dp) = 0.06394
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.06394")),
                            (dimensions.INTEREST_DUE, Decimal("2.20")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.54")),
                            (dimensions.INTEREST_OVERDUE, Decimal("4.81")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("164.67")),
                            # Penalty accruals are now pending capitalisation and accrued to 5 dp
                            # daily accrual = ((0.24 + 0.032 - 0.001)/365) * 164.67 = 0.12226
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                Decimal("0.12226"),
                            ),
                            (dimensions.PENALTIES, Decimal("24.56")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Check late repayment fee is capitalised at next overdue event",
                events=[
                    create_instance_parameter_change_event(
                        account_id=self.loan_account_id,
                        timestamp=third_overdue_event - relativedelta(hours=1),
                        **{loan.PARAM_CAPITALISE_LATE_REPAYMENT_FEE: "True"},
                    )
                ],
                expected_balances_at_ts={
                    third_overdue_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            # Principal increased by capitalised penalty fees
                            (dimensions.PRINCIPAL, Decimal("762.79")),
                            (dimensions.CAPITALISED_PENALTIES_TRACKER, Decimal("10")),
                            (dimensions.EMI, Decimal("84.74")),
                            # 7 accruals at 0.06394
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.44758")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("7.01")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("247.21")),
                            # 7 accruals at 0.12226
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                Decimal("0.85582"),
                            ),
                            (dimensions.PENALTIES, Decimal("24.56")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Check penalty interest is capitalised at next due event",
                expected_balances_at_ts={
                    fourth_application_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            # Principal decreases by 82.80 due to due amount calculation, but
                            # increases by 5.08 due to capitalisation of of penalty interest
                            (dimensions.PRINCIPAL, Decimal("685.07")),
                            # Capitalised interest includes 7 days accruing at 0.12226 and 23 days
                            # accruing at 247.21 * (0.24+ 0.032 - 0.001)/365 (5dp) = 0.18355
                            # = 5.07747 (2dp) = 5.08
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("5.08")),
                            (dimensions.CAPITALISED_PENALTIES_TRACKER, Decimal("10")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            # 0.44758 + 762.79 * (0.032 - 0.001)/365 (2dp) = 1.94
                            (dimensions.INTEREST_DUE, Decimal("1.94")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.80")),
                            (dimensions.INTEREST_OVERDUE, Decimal("7.01")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("247.21")),
                            # Zero'd out by capitalisation
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                Decimal("0"),
                            ),
                            (dimensions.PENALTIES, Decimal("24.56")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Check repayment with overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # repayment of 363.52 + 100 overpayment. This is before the overpayment fee
                        # is charged (100*0.05)
                        amount="463.52",
                        event_datetime=fourth_application_event + relativedelta(minutes=1),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    fourth_application_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            # 685.07 - (100*0.05) = 590.07
                            (dimensions.PRINCIPAL, Decimal("590.07")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("5.08")),
                            (dimensions.CAPITALISED_PENALTIES_TRACKER, Decimal("10")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            # overpayment fee = 100*0.05 = 5.0
                            (dimensions.OVERPAYMENT, Decimal("95")),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                Decimal("0"),
                            ),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Clear remaining debt with overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # to calculate the total amount required to repay the remaining principal
                        # we must determine the maximum overpayment amount (see overpayment.py).
                        # This is given by: P / (1-R), i.e. 590.07/(1-0.05) = 621.13
                        amount="621.13",
                        event_datetime=fourth_application_event + relativedelta(minutes=2),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    fourth_application_event
                    + relativedelta(minutes=2): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("5.08")),
                            (dimensions.CAPITALISED_PENALTIES_TRACKER, Decimal("10")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("685.07")),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                Decimal("0"),
                            ),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                    }
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=fourth_application_event + relativedelta(minutes=2),
                        notification_type=loan.CLOSURE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                        },
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=fourth_application_event + relativedelta(minutes=2),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="0",
                    )
                ],
            ),
            SubTest(
                description="Close the account",
                events=[
                    update_account_status_pending_closure(
                        timestamp=fourth_application_event + relativedelta(minutes=3),
                        account_id=self.loan_account_id,
                    ),
                ],
                expected_balances_at_ts={
                    fourth_application_event
                    + relativedelta(minutes=3): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0")),
                            (dimensions.CAPITALISED_PENALTIES_TRACKER, Decimal("0")),
                            (dimensions.EMI, Decimal("0")),
                            (dimensions.INTERNAL_CONTRA, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                Decimal("0"),
                            ),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                    }
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )
        self.run_test_scenario(test_scenario)
