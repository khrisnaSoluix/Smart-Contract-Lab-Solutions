# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

# library
from library.loan.contracts.template import loan
from library.loan.test import accounts, dimensions, parameters
from library.loan.test.simulation.common import LoanTestBase

# inception sdk
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    ContractNotificationResourceType,
    ExpectedContractNotification,
    ExpectedDerivedParameter,
    ExpectedRejection,
    ExpectedSchedule,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_flag_definition_event,
    create_flag_event,
    create_inbound_hard_settlement_instruction,
)

rule_of_78_template_parameters = {
    **parameters.loan_template_params,
    loan.PARAM_AMORTISATION_METHOD: "rule_of_78",
    loan.PARAM_LATE_REPAYMENT_FEE: "15",
    loan.overdue.PARAM_REPAYMENT_PERIOD: "10",
}
rule_of_78_instance_parameters = {
    **parameters.loan_instance_params,
    # rule of 78 loans are inherently fixed interest
    loan.PARAM_FIXED_RATE_LOAN: "True",
    loan.disbursement.PARAM_PRINCIPAL: "10000",
}


class LoanRuleOf78Test(LoanTestBase):

    loan_template_params = rule_of_78_template_parameters
    loan_instance_params = rule_of_78_instance_parameters

    def test_full_loan_with_rounding_on_final_interest_due(self):
        """
        Test to verify that the final due event ensures that all of the remaining unpaid interest is
        moved to due
        P = 10000
        n = 12
        r = 0.01
        total interest = 100
        monthly interest = round(100*remaining_term/78,2), which equates to:
            remaining_term: interest_due
            12: 15.38
            11: 14.1
            10: 12.82
            9: 11.54
            8: 10.26
            7: 8.97
            6: 7.69
            5: 6.41
            4: 5.13
            3: 3.85
            2: 2.56
            1: (100 - sum(interest_due to date) = 1.29)

        Note that if the standard rule of 78 formula was used for the final event then the interest
        due would be 1.28, meaning that only 99.99 of the total 100 interest would have been paid
        """
        start = self.default_simulation_start_datetime
        first_application_event = start + relativedelta(months=1, minutes=1)
        final_application_event = first_application_event + relativedelta(months=11)
        end = start + relativedelta(years=1, days=1)

        instance_params = {
            **self.loan_instance_params,
            loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.01",
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "1",
        }
        # the below data has been calculated as follows:
        # interest_due given by rule of 78 formula
        # principal_due given by emi - interest_due
        # remaining_principal given by principal - principal_due
        # interest_due and principal_due are not used but are provided here for completeness
        monthly_balances = {
            0: {"interest_due": "15.38", "principal_due": "826.29", "principal": "9173.71"},
            1: {"interest_due": "14.1", "principal_due": "827.57", "principal": "8346.14"},
            2: {"interest_due": "12.82", "principal_due": "828.85", "principal": "7517.29"},
            3: {"interest_due": "11.54", "principal_due": "830.13", "principal": "6687.16"},
            4: {"interest_due": "10.26", "principal_due": "831.41", "principal": "5855.75"},
            5: {"interest_due": "8.97", "principal_due": "832.70", "principal": "5023.05"},
            6: {"interest_due": "7.69", "principal_due": "833.98", "principal": "4189.07"},
            7: {"interest_due": "6.41", "principal_due": "835.26", "principal": "3353.81"},
            8: {"interest_due": "5.13", "principal_due": "836.54", "principal": "2517.27"},
            9: {"interest_due": "3.85", "principal_due": "837.82", "principal": "1679.45"},
            10: {"interest_due": "2.56", "principal_due": "839.11", "principal": "840.34"},
        }

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("10000")),
                            (dimensions.EMI, Decimal("841.67")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("10000"))],
                    }
                },
            ),
        ]
        # generate monthly repayments and assertions
        sub_tests += [
            SubTest(
                description=f"check balances at due event {month+1}",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # emi amount
                        amount="841.67",
                        event_datetime=first_application_event
                        + relativedelta(months=month, seconds=1),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    first_application_event
                    + relativedelta(months=month, seconds=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (
                                dimensions.PRINCIPAL,
                                Decimal(balances[loan.disbursement.PARAM_PRINCIPAL]),
                            ),
                            (dimensions.EMI, Decimal("841.67")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal(str(month + 1))),
                        ],
                    },
                },
            )
            for month, balances in monthly_balances.items()
        ]
        sub_tests.append(
            SubTest(
                description="check balances at final due event",
                expected_balances_at_ts={
                    final_application_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.EMI, Decimal("841.67")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            # final interest_due is 1.29 instead of 1.28 due to rounding
                            (dimensions.INTEREST_DUE, Decimal("1.29")),
                            (dimensions.PRINCIPAL_DUE, Decimal("840.34")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("12")),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, Decimal("100"))],
                    },
                },
            )
        )
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            debug=False,
        )
        self.run_test_scenario(test_scenario)

    def test_full_loan_cycle_with_overpayment_and_repayment_holiday(self):
        start = datetime(year=2020, month=1, day=11, tzinfo=ZoneInfo("UTC"))
        end = start + relativedelta(years=2, months=4)

        instance_params = {
            **self.loan_instance_params,
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "20",
            loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.1",
            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "24",
        }

        first_due_amount_calculation_event = datetime(
            year=2020, month=2, day=20, minute=1, tzinfo=ZoneInfo("UTC")
        )
        second_due_amount_calculation_event = first_due_amount_calculation_event + relativedelta(
            months=1
        )
        third_due_amount_calculation_event = second_due_amount_calculation_event + relativedelta(
            months=1
        )
        fourth_due_amount_calculation_event = third_due_amount_calculation_event + relativedelta(
            months=1
        )
        fifth_due_amount_calculation_event = fourth_due_amount_calculation_event + relativedelta(
            months=1
        )
        sixth_due_amount_calculation_event = fifth_due_amount_calculation_event + relativedelta(
            months=1
        )
        seventh_due_amount_calculation_event = sixth_due_amount_calculation_event + relativedelta(
            months=1
        )
        eighth_due_amount_calculation_event = seventh_due_amount_calculation_event + relativedelta(
            months=1
        )
        ninth_due_amount_calculation_event = eighth_due_amount_calculation_event + relativedelta(
            months=1
        )
        tenth_due_amount_calculation_event = ninth_due_amount_calculation_event + relativedelta(
            months=1
        )
        eleventh_due_amount_calculation_event = tenth_due_amount_calculation_event + relativedelta(
            months=1
        )
        twelveth_due_amount_calculation_event = (
            eleventh_due_amount_calculation_event + relativedelta(months=1)
        )
        penultimate_due_amount_calculation_event_without_holiday = (
            first_due_amount_calculation_event + relativedelta(years=1, month=12)
        )
        final_due_amount_calculation_event_without_holiday = (
            penultimate_due_amount_calculation_event_without_holiday + relativedelta(months=1)
        )
        actual_final_due_amount_calculation_event = (
            final_due_amount_calculation_event_without_holiday + relativedelta(months=1)
        )

        payment_holiday_start = second_due_amount_calculation_event + relativedelta(hours=10)
        payment_holiday_end = third_due_amount_calculation_event + relativedelta(hours=10)

        first_penalty_interest_on_overdue = first_due_amount_calculation_event + relativedelta(
            days=11, minute=0, second=1
        )

        expected_remaining_terms = [
            ("20", fifth_due_amount_calculation_event + relativedelta(days=1)),
            ("19", sixth_due_amount_calculation_event + relativedelta(days=1)),
            ("18", seventh_due_amount_calculation_event + relativedelta(days=1)),
            ("17", eighth_due_amount_calculation_event + relativedelta(days=1)),
            ("16", ninth_due_amount_calculation_event + relativedelta(days=1)),
            ("15", tenth_due_amount_calculation_event + relativedelta(days=1)),
            ("14", eleventh_due_amount_calculation_event + relativedelta(days=1)),
            ("13", twelveth_due_amount_calculation_event + relativedelta(days=1)),
            ("2", penultimate_due_amount_calculation_event_without_holiday + relativedelta(days=1)),
            ("1", final_due_amount_calculation_event_without_holiday + relativedelta(days=1)),
            ("0", actual_final_due_amount_calculation_event + relativedelta(days=1)),
        ]
        derived_params_remaining_terms = [
            ExpectedDerivedParameter(
                timestamp=x[1],
                account_id=self.loan_account_id,
                name=loan.derived_params.PARAM_REMAINING_TERM,
                value=x[0],
            )
            for x in expected_remaining_terms
        ]
        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("10000")),
                            # total loan interest = (10000 * 0.1 * 24)/12 = 20000
                            # emi: (10000 + 2000)/24 = 500
                            (dimensions.EMI, Decimal("500")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("10000"))],
                    }
                },
            ),
            SubTest(
                description="first repayment date EMI",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_due_amount_calculation_event - relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="24",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_due_amount_calculation_event + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="23",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_due_amount_calculation_event + relativedelta(hours=-1),
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="500.00",
                    ),
                ],
                expected_balances_at_ts={
                    first_due_amount_calculation_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("9660")),
                            (dimensions.PRINCIPAL_DUE, Decimal("340.00")),
                            (dimensions.INTEREST_DUE, Decimal("160")),
                            (dimensions.EMI, Decimal("500")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                        ]
                    }
                },
            ),
            SubTest(
                description="overpayments not allowed",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="600",
                        event_datetime=first_due_amount_calculation_event + relativedelta(hours=1),
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        first_due_amount_calculation_event + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Overpayments are not allowed for rule of 78 loans",
                    )
                ],
            ),
            SubTest(
                description="unpaid due does not accrue additional interest and overpayment "
                "does not clear due balances",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=first_due_amount_calculation_event + relativedelta(days=9),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    first_due_amount_calculation_event
                    + relativedelta(days=9): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("9660")),
                            (dimensions.PRINCIPAL_DUE, Decimal("340.00")),
                            (dimensions.INTEREST_DUE, Decimal("160")),
                            (dimensions.EMI, Decimal("500")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ]
                    }
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=first_due_amount_calculation_event + relativedelta(days=9),
                        account_id=self.loan_account_id,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Overpayments are not allowed for rule of 78 loans.",
                    )
                ],
            ),
            SubTest(
                description="unpaid due becomes overdue",
                expected_balances_at_ts={
                    first_due_amount_calculation_event
                    + relativedelta(days=10, hours=5): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("9660")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("340")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("160")),
                            (dimensions.EMI, Decimal("500")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="overdue amount accrues penalty interest",
                expected_balances_at_ts={
                    first_due_amount_calculation_event
                    + relativedelta(days=15): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("9660")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("340")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("160")),
                            (dimensions.EMI, Decimal("500")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            # daily penalty rate = (0.1 + 0.24)/365 = 0.00093
                            # daily accrual = ROUND(0.00093 * 500,2) = 0.47
                            # total accrual = 0.47 * 5 = 2.35
                            # 15 late repayment fee
                            (dimensions.PENALTIES, Decimal("17.35")),
                        ]
                    }
                },
            ),
            SubTest(
                description="repayment clears off penalties",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="517.35",
                        event_datetime=first_due_amount_calculation_event
                        + relativedelta(days=15, hours=1),
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    first_due_amount_calculation_event
                    + relativedelta(days=15, hours=1, minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("9660")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.EMI, Decimal("500")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=second_due_amount_calculation_event + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="22",
                    )
                ],
                expected_schedules=[
                    # we expect 5 accrual events which accrue on the overdue balances, then the 6th
                    # accrual event sees no overdue balances (since they've been cleared) and thus
                    # skips itself
                    ExpectedSchedule(
                        run_times=[
                            first_penalty_interest_on_overdue + relativedelta(days=i)
                            for i in range(0, 6)
                        ],
                        event_id=loan.interest_accrual.ACCRUAL_EVENT,
                        account_id=self.loan_account_id,
                        count=6,
                    )
                ],
            ),
            SubTest(
                description="Second Repayment Date",
                expected_balances_at_ts={
                    second_due_amount_calculation_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("9313.33")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("346.67")),
                            (dimensions.INTEREST_DUE, Decimal("153.33")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.EMI, Decimal("500")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("2")),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=second_due_amount_calculation_event + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="22",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_due_amount_calculation_event + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="500.00",
                    ),
                ],
            ),
            SubTest(
                description="repayment holiday does not accrue additional interest",
                events=[
                    create_flag_definition_event(
                        timestamp=second_due_amount_calculation_event + relativedelta(hours=1),
                        flag_definition_id="REPAYMENT_HOLIDAY",
                    ),
                    create_flag_event(
                        timestamp=second_due_amount_calculation_event + relativedelta(hours=2),
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        account_id=self.loan_account_id,
                        effective_timestamp=payment_holiday_start,
                        expiry_timestamp=payment_holiday_end,
                    ),
                ],
                expected_balances_at_ts={
                    third_due_amount_calculation_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("9313.33")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("346.67")),
                            (dimensions.INTEREST_DUE, Decimal("153.33")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.EMI, Decimal("500")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                            # due calculation event counter does not increase due to repayment
                            # holiday
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("2")),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=third_due_amount_calculation_event + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="22",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=third_due_amount_calculation_event + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="500.00",
                    ),
                ],
            ),
            SubTest(
                description="end of repayment holiday does not affect remaining principal",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="500",
                        event_datetime=third_due_amount_calculation_event + relativedelta(hours=12),
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    fourth_due_amount_calculation_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("8960")),
                            (dimensions.PRINCIPAL_DUE, Decimal("353.33")),
                            (dimensions.INTEREST_DUE, Decimal("146.67")),
                            (dimensions.EMI, Decimal("500")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("3")),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=fourth_due_amount_calculation_event + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="21",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=fourth_due_amount_calculation_event + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="500.00",
                    ),
                ],
            ),
            SubTest(
                description="subsequent dues are all constant",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="500",
                        event_datetime=datetime(
                            year=2020, month=5, day=20, hour=1, tzinfo=ZoneInfo("UTC")
                        )
                        + relativedelta(months=i),
                        internal_account_id=accounts.DEPOSIT,
                    )
                    for i in range(0, 21)
                ],
                expected_balances_at_ts={
                    fifth_due_amount_calculation_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("8600")),
                            (dimensions.PRINCIPAL_DUE, Decimal("360")),
                            (dimensions.INTEREST_DUE, Decimal("140")),
                            (dimensions.EMI, Decimal("500")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("4")),
                        ]
                    },
                    sixth_due_amount_calculation_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("8233.33")),
                            (dimensions.PRINCIPAL_DUE, Decimal("366.67")),
                            (dimensions.INTEREST_DUE, Decimal("133.33")),
                            (dimensions.EMI, Decimal("500")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("5")),
                        ]
                    },
                    seventh_due_amount_calculation_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("7860")),
                            (dimensions.PRINCIPAL_DUE, Decimal("373.33")),
                            (dimensions.INTEREST_DUE, Decimal("126.67")),
                            (dimensions.EMI, Decimal("500")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("6")),
                        ]
                    },
                    eighth_due_amount_calculation_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("7480")),
                            (dimensions.PRINCIPAL_DUE, Decimal("380")),
                            (dimensions.INTEREST_DUE, Decimal("120")),
                            (dimensions.EMI, Decimal("500")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("7")),
                        ]
                    },
                    ninth_due_amount_calculation_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("7093.33")),
                            (dimensions.PRINCIPAL_DUE, Decimal("386.67")),
                            (dimensions.INTEREST_DUE, Decimal("113.33")),
                            (dimensions.EMI, Decimal("500")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("8")),
                        ]
                    },
                    tenth_due_amount_calculation_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("6700")),
                            (dimensions.PRINCIPAL_DUE, Decimal("393.33")),
                            (dimensions.INTEREST_DUE, Decimal("106.67")),
                            (dimensions.EMI, Decimal("500")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("9")),
                        ]
                    },
                    eleventh_due_amount_calculation_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("6300")),
                            (dimensions.PRINCIPAL_DUE, Decimal("400")),
                            (dimensions.INTEREST_DUE, Decimal("100")),
                            (dimensions.EMI, Decimal("500")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("10")),
                        ]
                    },
                    twelveth_due_amount_calculation_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("5893.33")),
                            (dimensions.PRINCIPAL_DUE, Decimal("406.67")),
                            (dimensions.INTEREST_DUE, Decimal("93.33")),
                            (dimensions.EMI, Decimal("500")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("11")),
                        ]
                    },
                },
                expected_derived_parameters=derived_params_remaining_terms,
            ),
            SubTest(
                description="account closure trigger upon final payment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="500",
                        event_datetime=actual_final_due_amount_calculation_event
                        + relativedelta(days=1),
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    actual_final_due_amount_calculation_event
                    - relativedelta(hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("493.33")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.EMI, Decimal("500")),
                        ]
                    },
                    actual_final_due_amount_calculation_event
                    + relativedelta(hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("493.33")),
                            (dimensions.INTEREST_DUE, Decimal("6.67")),
                            (dimensions.EMI, Decimal("500")),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=actual_final_due_amount_calculation_event,
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="500.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=actual_final_due_amount_calculation_event,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=actual_final_due_amount_calculation_event,
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value=str(actual_final_due_amount_calculation_event.date()),
                    ),
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=actual_final_due_amount_calculation_event + relativedelta(days=1),
                        notification_type=loan.CLOSURE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                        },
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)
