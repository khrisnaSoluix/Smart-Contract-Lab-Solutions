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
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
)

interest_only_instance_params = {
    **parameters.loan_instance_params,
    loan.PARAM_AMORTISE_UPFRONT_FEE: "True",
    loan.PARAM_CAPITALISE_LATE_REPAYMENT_FEE: "False",
    loan.PARAM_FIXED_RATE_LOAN: "True",
    loan.balloon_payments.PARAM_BALLOON_PAYMENT_DAYS_DELTA: "0",
    loan.disbursement.PARAM_PRINCIPAL: "10000",
    loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "20",
    loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.031",
    loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "2",
    loan.repayment_holiday.PARAM_REPAYMENT_HOLIDAY_IMPACT_PREFERENCE: "increase_emi",
    loan.variable_rate.PARAM_VARIABLE_RATE_ADJUSTMENT: "0.00",
}

interest_only_template_params = {
    **parameters.loan_template_params,
    loan.PARAM_AMORTISATION_METHOD: "interest_only",
    loan.PARAM_ACCRUE_ON_DUE_PRINCIPAL: "False",
    loan.PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST: "no_capitalisation",
    loan.PARAM_LATE_REPAYMENT_FEE: "15",
    loan.PARAM_PENALTY_INCLUDES_BASE_RATE: "True",
    loan.PARAM_PENALTY_COMPOUNDS_OVERDUE_INTEREST: "True",
    loan.PARAM_GRACE_PERIOD: "5",
    loan.early_repayment.PARAM_EARLY_REPAYMENT_FLAT_FEE: "0",
    loan.early_repayment.PARAM_EARLY_REPAYMENT_FEE_RATE: "0",
    loan.overdue.PARAM_REPAYMENT_PERIOD: "10",
    loan.overpayment.PARAM_OVERPAYMENT_FEE_RATE: "0.05",
    loan.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: "reduce_term",
    loan.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0.189965",
    loan.variable_rate.PARAM_ANNUAL_INTEREST_RATE_CAP: "1.00",
    loan.variable_rate.PARAM_ANNUAL_INTEREST_RATE_FLOOR: "0.00",
}

default_simulation_start_date = datetime(year=2020, month=1, day=1, tzinfo=ZoneInfo("UTC"))


class LoanInterestOnlyTest(LoanTestBase):
    def test_interest_only_balloon_loan_balloon_delta_days_0(self):
        start = datetime(year=2020, month=1, day=11, tzinfo=ZoneInfo("UTC"))
        one_month_after_loan_start = start + relativedelta(months=1, minutes=1)
        before_first_payment = start + relativedelta(months=1, days=9, minutes=5)
        after_first_payment = start + relativedelta(months=1, days=9, hours=20)
        before_final_due_amount_calculation = start + relativedelta(months=2, days=9, seconds=30)
        after_final_due_amount_calculation = start + relativedelta(months=2, days=9, minutes=5)
        after_failed_final_deposit = start + relativedelta(months=2, days=9, hours=13)
        after_final_deposit = start + relativedelta(months=2, days=9, hours=20)
        end = start + relativedelta(months=3)

        sub_tests = [
            SubTest(
                description="interest accrued correctly",
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("10000")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.EMI, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("0")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    },
                    # accrued_interest = round(daily_interest_rate * principal ,5) * days
                    #                  = round((0.031 / 365) * 10000 ,5) * 31
                    one_month_after_loan_start: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("10000")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("26.32892")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("26.32892")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("0")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-26.32892")),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="interest moved to interest due after first repayment date",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="33.97",
                        event_datetime=datetime(
                            year=2020, month=2, day=20, hour=12, tzinfo=ZoneInfo("UTC")
                        ),
                        internal_account_id=accounts.DEPOSIT,
                    ),
                ],
                expected_balances_at_ts={
                    # First repayment date is 40 days after the loan start
                    # so more interest has been accrued
                    before_first_payment: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "33.97"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "33.97"),
                        ],
                    },
                    after_first_payment: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "33.97"),
                        ],
                    },
                },
            ),
            SubTest(
                description="principle moves to principle due on final repayment date",
                expected_balances_at_ts={
                    before_final_due_amount_calculation: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "24.63028"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "24.63028"),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-24.63028"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "33.97"),
                        ],
                    },
                    after_final_due_amount_calculation: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "10000"),
                            (dimensions.INTEREST_DUE, "24.63"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("2")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "58.60"),
                        ],
                    },
                },
            ),
            SubTest(
                description="a payment of more than the outstanding total fails",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="10024.64",
                        event_datetime=datetime(
                            year=2020, month=3, day=20, hour=12, tzinfo=ZoneInfo("UTC")
                        ),
                        internal_account_id=accounts.DEPOSIT,
                    ),
                ],
                expected_balances_at_ts={
                    after_failed_final_deposit: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "10000"),
                            (dimensions.INTEREST_DUE, "24.63"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("2")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "58.60"),
                        ],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=after_failed_final_deposit - relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Cannot pay more than is owed",
                    )
                ],
            ),
            SubTest(
                description="check final repayment clears balances and triggers closure WF",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="10024.63",
                        event_datetime=datetime(
                            year=2020, month=3, day=20, hour=16, tzinfo=ZoneInfo("UTC")
                        ),
                        internal_account_id=accounts.DEPOSIT,
                    ),
                ],
                expected_balances_at_ts={
                    after_final_deposit: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("2")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "58.60"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=datetime(
                            year=2020, month=3, day=20, hour=16, tzinfo=ZoneInfo("UTC")
                        ),
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
            template_params=interest_only_template_params,
            instance_params=interest_only_instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_only_balloon_loan_with_date_delta(self):
        start = datetime(year=2020, month=1, day=11, tzinfo=ZoneInfo("UTC"))
        instance_params = {
            **interest_only_instance_params,
            loan.balloon_payments.PARAM_BALLOON_PAYMENT_DAYS_DELTA: "35",
        }
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

        sub_tests = [
            SubTest(
                description="interest accrued correctly",
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    # accrued_interest = round(daily_interest_rate * principal ,5) * days
                    #                  = round((0.031 / 365) * 10000 ,5) * 31
                    one_month_after_loan_start: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "26.32892"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "26.32892"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-26.32892"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="2",
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
                        name=loan.derived_params.PARAM_TOTAL_REMAINING_PRINCIPAL,
                        value="10000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="10000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_PAYMENTS,
                        value="0.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-02-20",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.overdue.PARAM_NEXT_OVERDUE_DATE,
                        value="2020-03-01",
                    ),
                    # ExpectedDerivedParameter(
                    #     timestamp=start,
                    #     account_id=self.loan_account_id,
                    #     name=loan.early_repayment.PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT,
                    #     value="10526.32",
                    # ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.balloon_payments.PARAM_EXPECTED_BALLOON_PAYMENT_AMOUNT,
                        value="10000",
                    ),
                ],
            ),
            SubTest(
                description="interest moved to interest due after first repayment date",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="33.97",
                        event_datetime=datetime(
                            year=2020, month=2, day=20, hour=12, tzinfo=ZoneInfo("UTC")
                        ),
                        internal_account_id=accounts.DEPOSIT,
                    ),
                ],
                expected_balances_at_ts={
                    # First repayment date is 40 days after the loan start
                    # so more interest has been accrued
                    before_first_payment: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "33.97"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "33.97"),
                        ],
                    },
                    after_first_payment: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "33.97"),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_first_payment,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="1",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_first_payment + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="1",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_first_payment,
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="0.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_first_payment,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_REMAINING_PRINCIPAL,
                        value="10000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_first_payment,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="10033.97",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_first_payment,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_PAYMENTS,
                        value="33.97",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.balloon_payments.PARAM_EXPECTED_BALLOON_PAYMENT_AMOUNT,
                        value="10000",
                    ),
                ],
            ),
            SubTest(
                description="Check second repayment event and payment clears due",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="24.63",
                        event_datetime=datetime(
                            year=2020, month=3, day=20, hour=12, tzinfo=ZoneInfo("UTC")
                        ),
                        internal_account_id=accounts.DEPOSIT,
                    ),
                ],
                expected_balances_at_ts={
                    before_second_repayment_event: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "24.63028"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "24.63028"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-24.63028"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "33.97"),
                        ],
                    },
                    after_second_repayment_event: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "24.63"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "58.60"),
                        ],
                    },
                    after_second_deposit: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "58.60"),
                        ],
                    },
                },
            ),
            SubTest(
                description="check interest accrued after theoretical final repayment",
                expected_balances_at_ts={
                    day_after_theoretical_final_repayment_event: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.84932"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.84932"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-0.84932"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "58.60"),
                        ],
                    },
                    before_balloon_payment_event: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "29.72620"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "29.72620"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-29.72620"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "58.60"),
                        ],
                    },
                    after_balloon_payment_event: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "10000"),
                            (dimensions.INTEREST_DUE, "29.73"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "88.33"),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=day_after_theoretical_final_repayment_event,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=day_after_theoretical_final_repayment_event,
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="0.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=day_after_theoretical_final_repayment_event,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_REMAINING_PRINCIPAL,
                        value="10000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=day_after_theoretical_final_repayment_event,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="10000.85",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=day_after_theoretical_final_repayment_event,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_PAYMENTS,
                        value="0.00",
                    ),
                    # TODO: uncomment once derived parameter logic is updated
                    # ExpectedDerivedParameter(
                    #     timestamp=day_after_theoretical_final_repayment_event,
                    #     account_id=self.loan_account_id,
                    #     name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                    #     value="2020-04-24",
                    # ),
                    # ExpectedDerivedParameter(
                    #     timestamp=day_after_theoretical_final_repayment_event,
                    #     account_id=self.loan_account_id,
                    #     name=loan.overdue.PARAM_NEXT_OVERDUE_DATE,
                    #     value="2020-05-04",
                    # ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.balloon_payments.PARAM_EXPECTED_BALLOON_PAYMENT_AMOUNT,
                        value="10000",
                    ),
                ],
            ),
            SubTest(
                description="check payment clears due amounts and check schedules",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="10029.73",
                        event_datetime=balloon_payment,
                        internal_account_id=accounts.DEPOSIT,
                    ),
                ],
                expected_balances_at_ts={
                    after_balloon_payment: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
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
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=3,
                                day=20,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                        ],
                        event_id=loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                        account_id=self.loan_account_id,
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
                                tzinfo=ZoneInfo("UTC"),
                            ),
                        ],
                        event_id=loan.balloon_payments.BALLOON_PAYMENT_EVENT,
                        account_id=self.loan_account_id,
                        count=1,
                    ),
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=balloon_payment,
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
            template_params=interest_only_template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_only_balloon_loan_with_repayment_day_change(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, days=16)
        instance_params = {
            **interest_only_instance_params,
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "1",
            loan.balloon_payments.PARAM_BALLOON_PAYMENT_DAYS_DELTA: "5",
        }

        sub_tests = [
            SubTest(
                description="Change repayment day and check schedules",
                events=[
                    # this should change the balloon payment schedule from being
                    # run on 06/03/20 to 15/03/20
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(months=1, days=3),
                        account_id=self.loan_account_id,
                        **{loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "10"},
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
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=3,
                                day=10,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                        ],
                        event_id=loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                        account_id=self.loan_account_id,
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
                                tzinfo=ZoneInfo("UTC"),
                            ),
                        ],
                        event_id=loan.balloon_payments.BALLOON_PAYMENT_EVENT,
                        account_id=self.loan_account_id,
                        count=1,
                    ),
                ],
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=interest_only_template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_overpayment_interest_only_balloon_loan(self):
        start = datetime(year=2020, month=1, day=11, tzinfo=ZoneInfo("UTC"))
        overpayment_datetime = start + relativedelta(days=21, hours=12)
        first_repayment_datetime = start + relativedelta(months=1, days=9, hours=12)
        final_repayment_datetime = start + relativedelta(months=2, days=9, hours=12)
        end = start + relativedelta(months=2, days=11)

        sub_tests = [
            SubTest(
                description="overpayment incurs fee and reduces daily accrued interest",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="2000",
                        event_datetime=overpayment_datetime,
                        internal_account_id=accounts.DEPOSIT,
                    ),
                ],
                expected_balances_at_ts={
                    # First day accrues interest of 0.84932
                    start
                    + relativedelta(days=1, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.84932"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.84932"),
                            (dimensions.OVERPAYMENT, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-0.84932"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    # accrued_interest = round(daily_interest_rate * principal ,5) * days
                    #                  = round((0.031 / 365) * 10000 ,5) * 21
                    overpayment_datetime
                    - relativedelta(hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "17.83572"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "17.83572"),
                            (dimensions.OVERPAYMENT, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-17.83572"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    overpayment_datetime
                    + relativedelta(hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "8100"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "17.83572"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "17.83572"),
                            (dimensions.OVERPAYMENT, "1900"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-17.83572"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [
                            (dimensions.DEFAULT, "100"),
                        ],
                    },
                    # After overpayment daily interest accrued is reduced to 0.68795
                    # 17.83572 + 0.68795 = 18.52367
                    overpayment_datetime
                    + relativedelta(days=1, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "8100"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "18.68504"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "18.52367"),
                            (dimensions.OVERPAYMENT, "1900"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-18.52367"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [
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
                        target_account_id=self.loan_account_id,
                        amount="30.91",
                        event_datetime=first_repayment_datetime,
                        internal_account_id=accounts.DEPOSIT,
                    ),
                ],
                expected_balances_at_ts={
                    first_repayment_datetime
                    - relativedelta(hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "8100"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "30.91"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.OVERPAYMENT, "1900"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "30.91"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [
                            (dimensions.DEFAULT, "100"),
                        ],
                    },
                    first_repayment_datetime
                    + relativedelta(hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "8100"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.OVERPAYMENT, "1900"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "30.91"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [
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
                        target_account_id=self.loan_account_id,
                        amount="8119.95",
                        event_datetime=final_repayment_datetime,
                        internal_account_id=accounts.DEPOSIT,
                    ),
                ],
                expected_balances_at_ts={
                    final_repayment_datetime
                    - relativedelta(hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "8100"),
                            (dimensions.INTEREST_DUE, "19.95"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.OVERPAYMENT, "1900"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "50.86"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [
                            (dimensions.DEFAULT, "100"),
                        ],
                    },
                    final_repayment_datetime
                    + relativedelta(hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.OVERPAYMENT, "1900"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "50.86"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [
                            (dimensions.DEFAULT, "100"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=final_repayment_datetime,
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
            template_params=interest_only_template_params,
            instance_params=interest_only_instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_only_balloon_loan_overdue_balances(self):
        start = datetime(year=2020, month=1, day=11, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **interest_only_instance_params,
            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "2",
        }
        template_params = {
            **interest_only_template_params,
            loan.overdue.PARAM_REPAYMENT_PERIOD: "1",
        }

        one_month_after_loan_start = start + relativedelta(months=1, minutes=1)
        before_first_repayment_day = start + relativedelta(months=1, days=9)
        after_first_repayment_day = start + relativedelta(months=1, days=9, hours=1)
        end = start + relativedelta(months=1, days=12)

        sub_tests = [
            SubTest(
                description="interest accrued correctly",
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    # accrued_interest = round(daily_interest_rate * principal ,5) * days
                    #                  = round((0.031 / 365) * 10000 ,5) * 31
                    one_month_after_loan_start: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "26.32892"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "26.32892"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-26.32892"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0"),
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
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "33.12348"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "33.12348"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-33.12348"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    after_first_repayment_day: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            # 1 additional accrual event before
                            # repayment_day schedule is run
                            (dimensions.INTEREST_DUE, "33.97"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "33.97"),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="2",
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
                        name=loan.derived_params.PARAM_TOTAL_REMAINING_PRINCIPAL,
                        value="10000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="10000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_PAYMENTS,
                        value="0.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-02-20",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.overdue.PARAM_NEXT_OVERDUE_DATE,
                        value="2020-02-21",
                    ),
                    # ExpectedDerivedParameter(
                    #     timestamp=start,
                    #     account_id=self.loan_account_id,
                    #     name=loan.early_repayment.PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT,
                    #     value="10526.32",
                    # ),
                ],
            ),
            SubTest(
                description="interest due moved to overdue after missing payment "
                "and interest is accrued on overdue address",
                expected_balances_at_ts={
                    after_first_repayment_day
                    + relativedelta(days=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "33.97"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.84932"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.84932"),
                            # late repayment fee of 15
                            (dimensions.PENALTIES, "15"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-0.84932"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "33.97"),
                        ],
                        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME: [(dimensions.DEFAULT, "15")],
                        accounts.INTERNAL_PENALTY_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0")],
                    },
                    after_first_repayment_day
                    + relativedelta(days=2): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "33.97"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "1.69864"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "1.69864"),
                            # 15 + ROUND(ROUND(0.24+0.031)/365,10)*33.97,5)
                            # 15 + 0.03
                            (dimensions.PENALTIES, "15.03"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-1.69864"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "33.97"),
                        ],
                        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME: [(dimensions.DEFAULT, "15")],
                        accounts.INTERNAL_PENALTY_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0.03")],
                    },
                },
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
