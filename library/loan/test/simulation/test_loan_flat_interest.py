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

flat_interest_loan_template_params = {
    **parameters.loan_template_params,
    loan.PARAM_AMORTISATION_METHOD: "flat_interest",
}


class LoanFlatInterestTest(LoanTestBase):
    def test_full_loan_with_rounding_on_final_interest_due(self):
        """
        Test to verify that the final due event ensures that all of the remaining unpaid interest is
        moved to due
        P = 10000
        n = 12
        r = 0.01
        total interest = 100
        monthly interest = 100/12 = 8.33
        therefore final months interest due is expected to be 100 - 8.33*11 = 8.37
        """
        start = self.default_simulation_start_datetime
        first_application_event = start + relativedelta(months=1, minutes=1)
        final_application_event = first_application_event + relativedelta(months=11)
        end = start + relativedelta(years=1, days=1)

        instance_params = {
            **self.loan_instance_params,
            loan.disbursement.PARAM_PRINCIPAL: "10000",
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "1",
        }
        template_params = {
            **flat_interest_loan_template_params,
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
        # generate monthly repayments and assertions. Each month is identical
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
                                Decimal("10000") - (Decimal("833.34") * (month + 1)),
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
            for month in range(0, 11)
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
                            # final interest_due is 8.37 instead of 8.33 due to rounding
                            (dimensions.INTEREST_DUE, Decimal("8.37")),
                            (dimensions.PRINCIPAL_DUE, Decimal("833.26")),
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
            template_params=template_params,
            instance_params=instance_params,
            debug=False,
        )
        self.run_test_scenario(test_scenario)

    def test_full_loan_cycle_with_overpayment_and_repayment_holiday(self):
        start = datetime(year=2020, month=1, day=11, tzinfo=ZoneInfo("UTC"))
        end = start + relativedelta(months=14)

        instance_params = {
            **self.loan_instance_params,
            loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.031",
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "20",
        }
        template_params = {
            **flat_interest_loan_template_params,
            loan.PARAM_LATE_REPAYMENT_FEE: "15",
            loan.overdue.PARAM_REPAYMENT_PERIOD: "10",
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
        twelfth_due_amount_calculation_event = (
            eleventh_due_amount_calculation_event + relativedelta(months=1)
        )
        final_due_amount_calculation_event = twelfth_due_amount_calculation_event + relativedelta(
            months=1
        )

        payment_holiday_start = second_due_amount_calculation_event + relativedelta(hours=10)
        payment_holiday_end = third_due_amount_calculation_event + relativedelta(hours=10)

        first_penalty_interest_on_overdue = first_due_amount_calculation_event + relativedelta(
            days=11, minute=0, second=1
        )

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("3000")),
                            # total loan interest = (3000 * 0.031 * 12)/12 = 93.00
                            # emi: (3000 + 93)/12 = 257.75
                            (dimensions.EMI, Decimal("257.75")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("3000"))],
                    }
                },
            ),
            SubTest(
                description="first repayment date EMI",
                expected_balances_at_ts={
                    first_due_amount_calculation_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("2750.00")),
                            (dimensions.PRINCIPAL_DUE, Decimal("250.00")),
                            (dimensions.INTEREST_DUE, Decimal("7.75")),
                            (dimensions.EMI, Decimal("257.75")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_due_amount_calculation_event + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="11",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_due_amount_calculation_event + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="257.75",
                    ),
                ],
            ),
            SubTest(
                description="overpayments not allowed",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="1000",
                        event_datetime=first_due_amount_calculation_event + relativedelta(hours=1),
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    first_due_amount_calculation_event
                    + relativedelta(hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("2750.00")),
                            (dimensions.PRINCIPAL_DUE, Decimal("250.00")),
                            (dimensions.INTEREST_DUE, Decimal("7.75")),
                            (dimensions.EMI, Decimal("257.75")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                        ]
                    }
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=first_due_amount_calculation_event + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Overpayments are not allowed for flat interest loans.",
                    )
                ],
            ),
            SubTest(
                description="unpaid due balances do not accrue additional interest and overpayment "
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
                            (dimensions.PRINCIPAL, Decimal("2750.00")),
                            (dimensions.PRINCIPAL_DUE, Decimal("250.00")),
                            (dimensions.INTEREST_DUE, Decimal("7.75")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.EMI, Decimal("257.75")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                        ]
                    }
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=first_due_amount_calculation_event + relativedelta(days=9),
                        account_id=self.loan_account_id,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Overpayments are not allowed for flat interest loans.",
                    )
                ],
            ),
            SubTest(
                description="unpaid due becomes overdue",
                expected_balances_at_ts={
                    first_due_amount_calculation_event
                    + relativedelta(days=10, hours=5): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("2750.00")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("250.00")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("7.75")),
                            (dimensions.EMI, Decimal("257.75")),
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
                            (dimensions.PRINCIPAL, Decimal("2750.00")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("250.00")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("7.75")),
                            (dimensions.EMI, Decimal("257.75")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            # 15 late payment fee + round(257.75 * round(0.271/365,10) * 5,2) = 0.95
                            (dimensions.PENALTIES, Decimal("15.95")),
                        ]
                    }
                },
            ),
            SubTest(
                description="repayment clears off penalties",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="273.70",
                        event_datetime=first_due_amount_calculation_event
                        + relativedelta(days=15, hours=1),
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    first_due_amount_calculation_event
                    + relativedelta(days=15, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("2750.00")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.EMI, Decimal("257.75")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ]
                    }
                },
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
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("250.00")),
                            (dimensions.INTEREST_DUE, Decimal("7.75")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.EMI, Decimal("257.75")),
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
                        value="10",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_due_amount_calculation_event + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="257.75",
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
                            (dimensions.PRINCIPAL, Decimal("2500.00")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("250.00")),
                            (dimensions.INTEREST_DUE, Decimal("7.75")),
                            (dimensions.EMI, Decimal("257.75")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0")),
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
                        value="10",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=third_due_amount_calculation_event + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="257.75",
                    ),
                ],
            ),
            SubTest(
                description="end of repayment holiday does not affect remaining principal",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="257.75",
                        event_datetime=third_due_amount_calculation_event + relativedelta(hours=12),
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    fourth_due_amount_calculation_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("2250.00")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("250.00")),
                            (dimensions.INTEREST_DUE, Decimal("7.75")),
                            (dimensions.EMI, Decimal("257.75")),
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
                        value="9",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=fourth_due_amount_calculation_event + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="257.75",
                    ),
                ],
            ),
            SubTest(
                description="subsequent dues are all constant",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="257.75",
                        event_datetime=datetime(
                            year=2020, month=5, day=20, hour=1, tzinfo=ZoneInfo("UTC")
                        )
                        + relativedelta(months=i),
                        internal_account_id=accounts.DEPOSIT,
                    )
                    for i in range(0, 9)
                ],
                expected_balances_at_ts={
                    fifth_due_amount_calculation_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, Decimal("250.00")),
                            (dimensions.INTEREST_DUE, Decimal("7.75")),
                            (dimensions.EMI, Decimal("257.75")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("4")),
                        ]
                    },
                    sixth_due_amount_calculation_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, Decimal("250.00")),
                            (dimensions.INTEREST_DUE, Decimal("7.75")),
                            (dimensions.EMI, Decimal("257.75")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("5")),
                        ]
                    },
                    seventh_due_amount_calculation_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, Decimal("250.00")),
                            (dimensions.INTEREST_DUE, Decimal("7.75")),
                            (dimensions.EMI, Decimal("257.75")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("6")),
                        ]
                    },
                    eighth_due_amount_calculation_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, Decimal("250.00")),
                            (dimensions.INTEREST_DUE, Decimal("7.75")),
                            (dimensions.EMI, Decimal("257.75")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("7")),
                        ]
                    },
                    ninth_due_amount_calculation_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, Decimal("250.00")),
                            (dimensions.INTEREST_DUE, Decimal("7.75")),
                            (dimensions.EMI, Decimal("257.75")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("8")),
                        ]
                    },
                    tenth_due_amount_calculation_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, Decimal("250.00")),
                            (dimensions.INTEREST_DUE, Decimal("7.75")),
                            (dimensions.EMI, Decimal("257.75")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("9")),
                        ]
                    },
                    eleventh_due_amount_calculation_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, Decimal("250.00")),
                            (dimensions.INTEREST_DUE, Decimal("7.75")),
                            (dimensions.EMI, Decimal("257.75")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("10")),
                        ]
                    },
                    twelfth_due_amount_calculation_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, Decimal("250.00")),
                            (dimensions.INTEREST_DUE, Decimal("7.75")),
                            (dimensions.EMI, Decimal("257.75")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("11")),
                        ]
                    },
                    final_due_amount_calculation_event
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, Decimal("250.00")),
                            (dimensions.INTEREST_DUE, Decimal("7.75")),
                            (dimensions.EMI, Decimal("257.75")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("12")),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=fifth_due_amount_calculation_event + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="8",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=sixth_due_amount_calculation_event + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="7",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=seventh_due_amount_calculation_event + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="6",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=eighth_due_amount_calculation_event + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="5",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=ninth_due_amount_calculation_event + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="4",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=tenth_due_amount_calculation_event + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="3",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=eleventh_due_amount_calculation_event + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="2",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=twelfth_due_amount_calculation_event + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="1",
                    ),
                ],
            ),
            SubTest(
                description="account closure trigger upon final payment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="257.75",
                        event_datetime=final_due_amount_calculation_event + relativedelta(hours=1),
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    final_due_amount_calculation_event
                    + relativedelta(hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.EMI, Decimal("257.75")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("12")),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=final_due_amount_calculation_event + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=final_due_amount_calculation_event + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value=str(final_due_amount_calculation_event.date()),
                    ),
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=final_due_amount_calculation_event + relativedelta(hours=1),
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
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)
