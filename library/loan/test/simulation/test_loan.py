# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from json import dumps
from zoneinfo import ZoneInfo

# library
import library.loan.contracts.template.loan as loan
from library.loan.test import accounts, dimensions, parameters
from library.loan.test.simulation.common import LoanTestBase

# inception sdk
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    ContractConfig,
    ContractNotificationResourceType,
    ExpectedContractNotification,
    ExpectedDerivedParameter,
    ExpectedRejection,
    ExpectedSchedule,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_account_product_version_update_instruction,
    create_flag_definition_event,
    create_flag_event,
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_outbound_hard_settlement_instruction,
    create_posting_instruction_batch,
    update_account_status_pending_closure,
)
from inception_sdk.vault.postings.posting_classes import InboundHardSettlement

DUE_AMOUNT_CALCULATION_EVENT = loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT
default_simulation_start_datetime = datetime(year=2023, month=1, day=1, tzinfo=ZoneInfo("UTC"))
BLOCKING_FLAG = parameters.DEFAULT_BLOCKING_FLAG_PARAMETER_VALUE[0]


class LoanTest(LoanTestBase):
    def test_account_activation_no_upfront_fee(self):
        start = default_simulation_start_datetime
        end = start + relativedelta(seconds=2)

        template_params = {
            **self.loan_template_params,
            loan.overpayment.PARAM_OVERPAYMENT_FEE_RATE: "0",
        }

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("3000")),
                            (dimensions.EMI, Decimal("254.22")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("3000"))],
                    }
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
                        value="254.22",
                    ),
                ],
            ),
            SubTest(
                description="check overpayment near start of loan reduces remaining_term",
                # overpayment: 250, fee: 0
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="250",
                        event_datetime=start + relativedelta(seconds=1),
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    end: {
                        self.loan_account_id: [
                            (dimensions.OVERPAYMENT, "250"),
                            (dimensions.PRINCIPAL, "2750"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [(dimensions.DEFAULT, "0")],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=end,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="11",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=end,
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="254.22",
                    ),
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )
        self.run_test_scenario(test_scenario)

    def test_account_activation_non_amortised_upfront_fee(self):
        start = default_simulation_start_datetime
        end = start + relativedelta(seconds=1)
        instance_params = {**self.loan_instance_params, loan.PARAM_UPFRONT_FEE: "100"}

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("3000")),
                            (dimensions.EMI, Decimal("254.22")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("2900"))],
                        accounts.INTERNAL_UPFRONT_FEE_INCOME: [
                            (dimensions.DEFAULT, Decimal("100"))
                        ],
                    }
                },
            )
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params
        )
        self.run_test_scenario(test_scenario)

    def test_account_activation_amortised_upfront_fee(self):
        start = default_simulation_start_datetime
        end = start + relativedelta(seconds=1)

        instance_params = {
            **self.loan_instance_params,
            loan.PARAM_UPFRONT_FEE: "100",
            loan.PARAM_AMORTISE_UPFRONT_FEE: "true",
        }

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("3100")),
                            (dimensions.EMI, Decimal("262.69")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("3000"))],
                        accounts.INTERNAL_UPFRONT_FEE_INCOME: [
                            (dimensions.DEFAULT, Decimal("100"))
                        ],
                    }
                },
            )
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params
        )
        self.run_test_scenario(test_scenario)

    def test_get_repayment_schedule_declining_principal(self):
        start = datetime(year=2020, month=1, day=11, tzinfo=ZoneInfo("UTC"))
        end = start + relativedelta(seconds=1)

        instance_params = {
            **self.loan_instance_params,
            loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.031",
            loan.PARAM_FIXED_RATE_LOAN: "True",
            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "12",
            loan.PARAM_AMORTISE_UPFRONT_FEE: "True",
            loan.disbursement.PARAM_PRINCIPAL: "30000",
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "20",
        }
        template_params = {
            **self.loan_template_params,
            loan.PARAM_AMORTISATION_METHOD: "declining_principal",
        }

        first_repayment_date = datetime(2020, 2, 20, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        expected_repayment_schedule = {
            str(first_repayment_date + relativedelta(months=i)): [
                str(i + 1),  # Payment number
                values[0],  # Principal
                str(Decimal(values[1]) + Decimal(values[2])),  # EMI
                values[1],  # Monthly principal
                values[2],  # Monthly interest
            ]
            for i, values in enumerate(self.expected_output["1year_monthly_repayment"])
        }

        sub_tests = [
            SubTest(
                description="Get repayment_schedule",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start,
                        notification_type=loan.REPAYMENT_SCHEDULE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "repayment_schedule": dumps(expected_repayment_schedule),
                        },
                        resource_id=f"{self.loan_account_id}",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
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

    def test_get_repayment_schedule_declining_principal_long_term(self):
        start = datetime(year=2020, month=1, day=11, tzinfo=ZoneInfo("UTC"))
        end = start + relativedelta(seconds=1)

        instance_params = {
            **self.loan_instance_params,
            loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.031",
            loan.PARAM_FIXED_RATE_LOAN: "True",
            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "120",
            loan.PARAM_AMORTISE_UPFRONT_FEE: "True",
            loan.disbursement.PARAM_PRINCIPAL: "300000",
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "20",
        }
        template_params = {
            **self.loan_template_params,
            loan.PARAM_AMORTISATION_METHOD: "declining_principal",
        }

        first_repayment_date = datetime(2020, 2, 20, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        expected_repayment_schedule = {
            str(first_repayment_date + relativedelta(months=i)): [
                values[0],  # Payment number
                values[1],  # Principal
                values[2],  # EMI
                values[3],  # Monthly principal
                values[4],  # Monthly interest
            ]
            for i, values in enumerate(self.expected_output["10year_monthly_repayment"])
        }

        sub_tests = [
            SubTest(
                description="Get repayment_schedule",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start,
                        notification_type=loan.REPAYMENT_SCHEDULE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "repayment_schedule": dumps(expected_repayment_schedule),
                        },
                        resource_id=f"{self.loan_account_id}",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
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

    def test_get_repayment_schedule_declining_principal_high_interest(self):
        start = datetime(year=2020, month=1, day=11, tzinfo=ZoneInfo("UTC"))
        end = start + relativedelta(seconds=1)

        instance_params = {
            **self.loan_instance_params,
            loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.50",
            loan.PARAM_FIXED_RATE_LOAN: "True",
            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "12",
            loan.PARAM_AMORTISE_UPFRONT_FEE: "True",
            loan.disbursement.PARAM_PRINCIPAL: "30000",
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "20",
        }
        template_params = {
            **self.loan_template_params,
            loan.PARAM_AMORTISATION_METHOD: "declining_principal",
        }

        first_repayment_date = datetime(2020, 2, 20, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        expected_repayment_schedule = {
            str(first_repayment_date + relativedelta(months=i)): [
                values[0],  # Payment number
                values[1],  # Principal
                values[2],  # EMI
                values[3],  # Monthly principal
                values[4],  # Monthly interest
            ]
            for i, values in enumerate(
                self.expected_output["1year_monthly_repayment_high_interest"]
            )
        }

        sub_tests = [
            SubTest(
                description="Get repayment_schedule",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start,
                        notification_type=loan.REPAYMENT_SCHEDULE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "repayment_schedule": dumps(expected_repayment_schedule),
                        },
                        resource_id=f"{self.loan_account_id}",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
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

    def test_get_repayment_schedule_when_not_declining_principal(self):
        start = datetime(year=2020, month=1, day=11, tzinfo=ZoneInfo("UTC"))
        end = start + relativedelta(seconds=1)

        template_params = {
            **self.loan_template_params,
            loan.PARAM_AMORTISATION_METHOD: "flat_interest",
        }

        expected_repayment_schedule = {}

        sub_tests = [
            SubTest(
                description="Get repayment_schedule",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start,
                        notification_type=loan.REPAYMENT_SCHEDULE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "repayment_schedule": dumps(expected_repayment_schedule),
                        },
                        resource_id=f"{self.loan_account_id}",
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
        )

        self.run_test_scenario(test_scenario)

    def test_pre_parameter_hook_rejections_declining_principal(self):
        start = default_simulation_start_datetime
        first_due_amount_calculation = datetime(2023, 2, 28, 0, 1, tzinfo=ZoneInfo("UTC"))
        second_due_amount_calculation = datetime(2023, 3, 16, 0, 1, tzinfo=ZoneInfo("UTC"))
        end = second_due_amount_calculation

        sub_tests = [
            SubTest(
                "due amount calc day change rejected before first due amount calc day",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=first_due_amount_calculation - relativedelta(seconds=1),
                        account_id=self.loan_account_id,
                        **{loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "10"},
                    )
                ],
                expected_parameter_change_rejections=[
                    ExpectedRejection(
                        timestamp=first_due_amount_calculation - relativedelta(seconds=1),
                        account_id=self.loan_account_id,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="It is not possible to change the monthly repayment "
                        "day if the first repayment date has not passed.",
                    )
                ],
            ),
            SubTest(
                "due amount calc day change rejected if there are due amount blocking flags",
                events=[
                    create_flag_definition_event(
                        timestamp=first_due_amount_calculation + relativedelta(seconds=1),
                        flag_definition_id=BLOCKING_FLAG,
                    ),
                    create_flag_event(
                        timestamp=first_due_amount_calculation + relativedelta(seconds=2),
                        flag_definition_id=BLOCKING_FLAG,
                        account_id=self.loan_account_id,
                        expiry_timestamp=first_due_amount_calculation + relativedelta(seconds=4),
                    ),
                    create_instance_parameter_change_event(
                        timestamp=first_due_amount_calculation + relativedelta(seconds=3),
                        account_id=self.loan_account_id,
                        **{loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "10"},
                    ),
                ],
                expected_parameter_change_rejections=[
                    ExpectedRejection(
                        timestamp=first_due_amount_calculation + relativedelta(seconds=3),
                        account_id=self.loan_account_id,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="It is not possible to change the due amount calculation "
                        "day if there are active due amount blocking flags.",
                    )
                ],
            ),
            SubTest(
                description="check due amount calculation change after first schedule is accepted",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=first_due_amount_calculation + relativedelta(days=2),
                        account_id=self.loan_account_id,
                        **{loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "16"},
                    )
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_due_amount_calculation, second_due_amount_calculation],
                        event_id=loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                        account_id=self.loan_account_id,
                        count=2,
                    )
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_pre_parameter_hook_rejections_no_repayment(self):
        start = datetime(2023, 1, 28, 0, 1, tzinfo=ZoneInfo("UTC"))
        first_due_amount_calculation = datetime(2023, 2, 28, 0, 1, tzinfo=ZoneInfo("UTC"))
        end = first_due_amount_calculation + relativedelta(days=1)

        template_params = {
            **self.loan_template_params,
            loan.PARAM_AMORTISATION_METHOD: loan.no_repayment.AMORTISATION_METHOD,
        }

        sub_tests = [
            SubTest(
                "due amount calc day change rejected before first due amount calc day",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(days=10),
                        account_id=self.loan_account_id,
                        **{loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "10"},
                    )
                ],
                expected_parameter_change_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(days=10),
                        account_id=self.loan_account_id,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            # The check for no_repayment comes before check for first due event
                            "It is not possible to change the due amount calculation day for a "
                            "No Repayment (Balloon Payment) loan."
                        ),
                    )
                ],
            ),
            SubTest(
                description=(
                    "check due amount calculation change after first schedule is still "
                    "rejected for a no repayment loan"
                ),
                events=[
                    create_instance_parameter_change_event(
                        timestamp=end,
                        account_id=self.loan_account_id,
                        **{loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "16"},
                    )
                ],
                expected_parameter_change_rejections=[
                    ExpectedRejection(
                        timestamp=end,
                        account_id=self.loan_account_id,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "It is not possible to change the due amount calculation day for a "
                            "No Repayment (Balloon Payment) loan."
                        ),
                    )
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )
        self.run_test_scenario(test_scenario)

    def test_due_amount_calculation_day_change_when_effective_day_is_after_new_repayment_day(self):
        start = default_simulation_start_datetime
        first_due_amount_calculation = datetime(2023, 2, 12, 0, 1, tzinfo=ZoneInfo("UTC"))
        parameter_change_datetime = datetime(2023, 3, 9, tzinfo=ZoneInfo("UTC"))
        second_due_amount_calculation = datetime(2023, 3, 12, 0, 1, tzinfo=ZoneInfo("UTC"))
        third_due_amount_calculation = datetime(2023, 4, 2, 0, 1, tzinfo=ZoneInfo("UTC"))
        end = third_due_amount_calculation

        instance_params = {
            **self.loan_instance_params,
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "12",
        }

        sub_tests = [
            SubTest(
                description="check due amount calculation change from 12 to 2 on 9th of month "
                "so should remain 12 for current month, then implement next month",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=parameter_change_datetime,
                        account_id=self.loan_account_id,
                        **{loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "2"},
                    )
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            first_due_amount_calculation,
                            second_due_amount_calculation,
                            third_due_amount_calculation,
                        ],
                        event_id=loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                        account_id=self.loan_account_id,
                        count=3,
                    ),
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value=str(first_due_amount_calculation.date()),
                    ),
                    ExpectedDerivedParameter(
                        timestamp=parameter_change_datetime - relativedelta(minutes=1),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value=str(second_due_amount_calculation.date()),
                    ),
                    ExpectedDerivedParameter(
                        timestamp=parameter_change_datetime + relativedelta(minutes=1),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value=str(second_due_amount_calculation.date()),
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_due_amount_calculation + relativedelta(minutes=1),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value=str(third_due_amount_calculation.date()),
                    ),
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params
        )
        self.run_test_scenario(test_scenario)

    def test_changing_due_calc_day_multiple_times(self):
        """
        2023/01/01 account is created
        2023/02/05 first due amount event
        2023/02/14 due calc day updated to 20
        2023/03/18 due calc day updated to 7
        2023/03/19 due calc day updated to 6
        2023/03/20 second due amount event
        2023/04/06 third due amount event
        """
        start = default_simulation_start_datetime
        first_due_amount_event = datetime(
            year=2023, month=2, day=5, hour=0, minute=1, second=0, tzinfo=ZoneInfo("UTC")
        )
        before_first_due_amount_event = first_due_amount_event - relativedelta(seconds=1)
        first_overdue_event = first_due_amount_event + relativedelta(days=7)
        first_delinquency_event = first_overdue_event.replace(minute=1, second=0) + relativedelta(
            days=2
        )
        updated_due_day = "20"
        change_due_calc_day_param = first_delinquency_event + relativedelta(seconds=1)
        second_due_amount_event = first_due_amount_event.replace(month=3, day=int(updated_due_day))
        change_due_calc_day_again = second_due_amount_event - relativedelta(days=2)
        change_due_calc_day_third = second_due_amount_event - relativedelta(days=1)
        updated_again_due_day = "7"
        updated_third_due_day = "6"
        third_due_amount_event = first_due_amount_event.replace(
            month=4, day=int(updated_third_due_day)
        )
        end = third_due_amount_event

        instance_params = {
            **self.loan_instance_params,
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "5",
        }

        sub_tests = [
            SubTest(
                description="changing the due amount calc day before the first due calc event",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=before_first_due_amount_event,
                        account_id=self.loan_account_id,
                        **{loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "20"},
                    ),
                ],
                expected_parameter_change_rejections=[
                    ExpectedRejection(
                        timestamp=before_first_due_amount_event,
                        account_id=self.loan_account_id,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="It is not possible to change the monthly repayment "
                        "day if the first repayment date has not passed.",
                    )
                ],
            ),
            SubTest(
                description="changing the due amount calc day after the first due calc event",
                # the new due calc day value will take effect for the 2nd due calc event
                events=[
                    create_instance_parameter_change_event(
                        timestamp=change_due_calc_day_param,
                        account_id=self.loan_account_id,
                        **{
                            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: (
                                updated_due_day
                            )
                        },
                    ),
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=change_due_calc_day_param - relativedelta(seconds=1),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2023-03-05",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=change_due_calc_day_param + relativedelta(seconds=1),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2023-03-20",
                    ),
                ],
            ),
            SubTest(
                description="changing the due amount calc day before second due calc event that "
                "month and after the day of the new value",
                # the new due calc day value will take effect for the 3rd due calc event
                events=[
                    create_instance_parameter_change_event(
                        timestamp=change_due_calc_day_again,
                        account_id=self.loan_account_id,
                        **{
                            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: (
                                updated_again_due_day
                            )
                        },
                    ),
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=change_due_calc_day_again - relativedelta(seconds=1),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2023-03-20",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=change_due_calc_day_again + relativedelta(hours=10),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2023-03-20",
                    ),
                ],
            ),
            SubTest(
                description="changing due amount calc day for a third time between due calc events",
                # the new due calc day value will take effect for the 3rd due calc event
                events=[
                    create_instance_parameter_change_event(
                        timestamp=change_due_calc_day_third,
                        account_id=self.loan_account_id,
                        **{
                            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: (
                                updated_third_due_day
                            )
                        },
                    ),
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=change_due_calc_day_third - relativedelta(seconds=1),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2023-03-20",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=change_due_calc_day_third + relativedelta(hours=10),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2023-03-20",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_due_amount_event + relativedelta(seconds=1),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2023-04-06",
                    ),
                ],
            ),
            SubTest(
                description="schedules ran correctly",
                expected_schedules=[
                    ExpectedSchedule(
                        event_id=DUE_AMOUNT_CALCULATION_EVENT,
                        run_times=[
                            first_due_amount_event,
                            second_due_amount_event,
                            third_due_amount_event,
                        ],
                        account_id=self.loan_account_id,
                        count=3,
                    ),
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params
        )
        self.run_test_scenario(test_scenario)

    def test_due_amount_calculation_day_change_effective_day_is_before_new_repayment_day(self):
        start = default_simulation_start_datetime
        first_due_amount_calculation = datetime(2023, 2, 12, 0, 1, tzinfo=ZoneInfo("UTC"))
        parameter_change_datetime = datetime(2023, 2, 13, tzinfo=ZoneInfo("UTC"))
        second_due_amount_calculation = datetime(2023, 3, 20, 0, 1, tzinfo=ZoneInfo("UTC"))
        third_due_amount_calculation = datetime(2023, 4, 20, 0, 1, tzinfo=ZoneInfo("UTC"))
        end = third_due_amount_calculation

        instance_params = {
            **self.loan_instance_params,
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "12",
        }

        sub_tests = [
            SubTest(
                description="check due amount calculation change from 12 to 20 on 13th of month "
                "so should update to the next calendar month and not run twice in current month",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=parameter_change_datetime,
                        account_id=self.loan_account_id,
                        **{loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "20"},
                    )
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            first_due_amount_calculation,
                            second_due_amount_calculation,
                            third_due_amount_calculation,
                        ],
                        event_id=loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                        account_id=self.loan_account_id,
                        count=3,
                    )
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value=str(first_due_amount_calculation.date()),
                    ),
                    ExpectedDerivedParameter(
                        timestamp=parameter_change_datetime - relativedelta(minutes=1),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value=str((first_due_amount_calculation + relativedelta(months=1)).date()),
                    ),
                    ExpectedDerivedParameter(
                        timestamp=parameter_change_datetime + relativedelta(minutes=1),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value=str(second_due_amount_calculation.date()),
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_due_amount_calculation + relativedelta(minutes=1),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value=str(third_due_amount_calculation.date()),
                    ),
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params
        )
        self.run_test_scenario(test_scenario)

    def test_pre_posting_hook_rejections(self):
        start = default_simulation_start_datetime
        end = start + relativedelta(seconds=3)

        sub_tests = [
            SubTest(
                description="check wrong denomination is rejected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        denomination="USD",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(seconds=1),
                        account_id=self.loan_account_id,
                        rejection_type="WrongDenomination",
                        rejection_reason="Cannot make transactions in the given denomination, "
                        "transactions must be one of ['GBP']",
                    )
                ],
            ),
            SubTest(
                description="check multiple postings in a single batch are rejected",
                events=[
                    create_posting_instruction_batch(
                        event_datetime=start + relativedelta(seconds=2),
                        instructions=[
                            InboundHardSettlement(
                                amount="1000",
                                target_account_id=self.loan_account_id,
                                internal_account_id=accounts.INTERNAL,
                                denomination=parameters.TEST_DENOMINATION,
                            ),
                            InboundHardSettlement(
                                amount="2000",
                                target_account_id=self.loan_account_id,
                                internal_account_id=accounts.INTERNAL,
                                denomination=parameters.TEST_DENOMINATION,
                            ),
                        ],
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(seconds=2),
                        account_id=self.loan_account_id,
                        rejection_type="Custom",
                        rejection_reason="Only batches with a single hard settlement or transfer "
                        "posting are supported",
                    )
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_debit_postings_handled_correctly(self):
        start = default_simulation_start_datetime
        end = start + relativedelta(seconds=5)

        sub_tests = [
            SubTest(
                description="Standard debit is rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(seconds=1),
                        account_id=self.loan_account_id,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Debiting is not allowed from this account.",
                    )
                ],
            ),
            SubTest(
                description="Interest adjustment debit is accepted and rebalanced with no existing"
                "interest due balance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        denomination=parameters.TEST_DENOMINATION,
                        instruction_details={"interest_adjustment": "true"},
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("10")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Interest adjustment debit is accepted and rebalanced with existing"
                "interest due balance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        denomination=parameters.TEST_DENOMINATION,
                        instruction_details={"interest_adjustment": "true"},
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("1")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Fee debit is accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1",
                        event_datetime=start + relativedelta(seconds=4),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        denomination=parameters.TEST_DENOMINATION,
                        instruction_details={"fee": "true"},
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=4): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("1")),
                            (dimensions.PENALTIES, Decimal("1")),
                        ],
                    }
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_credit_postings_handled_correctly(self):
        start = default_simulation_start_datetime
        end = start + relativedelta(seconds=7)

        sub_tests = [
            SubTest(
                description="Credit less than total debt is accepted",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        self.loan_account_id: [
                            # overpayment fee of 0.05
                            (dimensions.PRINCIPAL, Decimal("2999.05")),
                            (dimensions.OVERPAYMENT, Decimal("0.95")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Credit when repayment blocking flag is set is rejected",
                events=[
                    create_flag_definition_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=BLOCKING_FLAG,
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=3),
                        flag_definition_id=BLOCKING_FLAG,
                        account_id=self.loan_account_id,
                        expiry_timestamp=start + relativedelta(seconds=5),
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="1",
                        event_datetime=start + relativedelta(seconds=4),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(seconds=4),
                        account_id=self.loan_account_id,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Repayments are blocked for this account.",
                    )
                ],
            ),
            SubTest(
                description="Credit greater than total debt is rejected",
                events=[
                    # principal = 2999.05
                    # maximum overpayment = 2999.05 / (1-0.05) = 3156.89
                    create_inbound_hard_settlement_instruction(
                        amount="3156.90",
                        event_datetime=start + relativedelta(seconds=6),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(seconds=6),
                        account_id=self.loan_account_id,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Cannot pay more than is owed.",
                    )
                ],
            ),
            SubTest(
                description="Credit equal to total debt + overpayment fee is accepted",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3156.89",
                        event_datetime=start + relativedelta(seconds=7),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=7): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("3000")),
                        ],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, debug=False
        )
        self.run_test_scenario(test_scenario)

    def test_force_override_posting(self):
        start = default_simulation_start_datetime
        end = start + relativedelta(seconds=2)

        sub_tests = [
            SubTest(
                description="Verify force override skips pre and post posting logic",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        instruction_details={"force_override": "true"},
                        denomination="USD",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        self.loan_account_id: [
                            (dimensions.USD_DEFAULT, Decimal("-1")),
                        ],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, debug=True
        )
        self.run_test_scenario(test_scenario)


class DerivedParametersTest(LoanTestBase):
    def get_expected_derived_parameters(self, timestamp, account_id, expected_parameters):
        expected_derived_parameters = []
        for parameter in expected_parameters:
            expected_derived_parameters.append(
                ExpectedDerivedParameter(
                    timestamp, account_id, parameter, expected_parameters[parameter]
                )
            )
        return expected_derived_parameters

    def test_total_remaining_amounts(self):
        start = default_simulation_start_datetime
        first_due_amount_calculation = datetime(2023, 2, 28, 0, 1, tzinfo=ZoneInfo("UTC"))
        end = first_due_amount_calculation + relativedelta(seconds=1)

        sub_tests = [
            SubTest(
                "check derived parameters at the start of the loan",
                expected_derived_parameters=self.get_expected_derived_parameters(
                    timestamp=start,
                    account_id=self.loan_account_id,
                    expected_parameters={
                        loan.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT: "3000.00",
                        loan.derived_params.PARAM_TOTAL_OUTSTANDING_PAYMENTS: "0.00",
                        loan.derived_params.PARAM_TOTAL_REMAINING_PRINCIPAL: "3000.00",
                    },
                ),
            ),
            SubTest(
                "check derived parameters at first due amount calculation",
                expected_derived_parameters=self.get_expected_derived_parameters(
                    timestamp=first_due_amount_calculation,
                    account_id=self.loan_account_id,
                    # The EMI is 254.22 and the daily interest is (3000 * .031) / 365 = 0.25479
                    # So with the 27 additional days of non-EMI interest accrued, the first
                    # payment should be 254.22 + 27 * 0.25479 = 261.10
                    # Also the interest accrued for the first 58 days is 0.25479 * 58 = 14.78
                    # so the total outstanding debt should be 3000 + 14.78 = 3014.78
                    expected_parameters={
                        loan.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT: "3014.78",
                        loan.derived_params.PARAM_TOTAL_OUTSTANDING_PAYMENTS: "261.10",
                        loan.derived_params.PARAM_TOTAL_REMAINING_PRINCIPAL: "3000.00",
                    },
                ),
            ),
            SubTest(
                "check derived parameters after first payment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="261.10",
                        event_datetime=first_due_amount_calculation + relativedelta(seconds=1),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_derived_parameters=self.get_expected_derived_parameters(
                    timestamp=first_due_amount_calculation + relativedelta(seconds=1),
                    account_id=self.loan_account_id,
                    expected_parameters={
                        # 3014.78 - 261.10 = 2753.68
                        loan.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT: "2753.68",
                        loan.derived_params.PARAM_TOTAL_OUTSTANDING_PAYMENTS: "0.00",
                        loan.derived_params.PARAM_TOTAL_REMAINING_PRINCIPAL: "2753.68",
                    },
                ),
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)


class ConversionTest(LoanTestBase):
    def test_schedules_preserved_on_conversion(self):
        """
        Test that all schedules run as expected after two account conversions:
        - the first on a due amount calculation event
        - the second at mid cycle
        """
        start = default_simulation_start_datetime
        instance_params = {
            **self.loan_instance_params,
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "1",
        }

        # before first conversion
        first_due_amount_event = start + relativedelta(months=1, minutes=1)
        # after first conversion
        second_due_amount_event = first_due_amount_event + relativedelta(months=1)
        # after second conversion
        third_due_amount_event = second_due_amount_event + relativedelta(months=1)

        # after first conversion
        first_overdue_event = first_due_amount_event + relativedelta(days=7, minute=0, second=2)
        # after first conversion
        second_overdue_event = first_overdue_event + relativedelta(months=1)
        # after second conversion
        third_overdue_event = second_overdue_event + relativedelta(months=1)

        first_delinquency_event = first_overdue_event + relativedelta(days=1)
        # after first conversion
        second_delinquency_event = first_delinquency_event + relativedelta(months=1)
        # after second conversion
        third_delinquency_event = second_delinquency_event + relativedelta(months=1)

        first_accrual_after_conversion_1 = first_due_amount_event + relativedelta(
            days=1, minute=0, second=1
        )
        first_accrual_after_conversion_2 = second_delinquency_event + relativedelta(
            days=1, minute=0, second=1
        )

        end = third_delinquency_event

        # Define the conversion timings
        conversion_1 = first_due_amount_event + relativedelta(seconds=1)
        convert_to_version_id_1 = "5"
        convert_to_contract_config_1 = ContractConfig(
            contract_content=self.smart_contract_path_to_content[self.contract_filepath],
            smart_contract_version_id=convert_to_version_id_1,
            template_params=parameters.loan_template_params,
            account_configs=[],
        )
        conversion_2 = second_delinquency_event + relativedelta(days=1)
        convert_to_version_id_2 = "6"
        convert_to_contract_config_2 = ContractConfig(
            contract_content=self.smart_contract_path_to_content[self.contract_filepath],
            smart_contract_version_id=convert_to_version_id_2,
            template_params=parameters.loan_template_params,
            account_configs=[],
        )

        sub_tests = [
            SubTest(
                description="Trigger conversions event and check schedule run times are unchanged",
                events=[
                    create_account_product_version_update_instruction(
                        timestamp=conversion_1,
                        account_id=self.loan_account_id,
                        product_version_id=convert_to_version_id_1,
                    ),
                    create_account_product_version_update_instruction(
                        timestamp=conversion_2,
                        account_id=self.loan_account_id,
                        product_version_id=convert_to_version_id_2,
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            first_due_amount_event,
                            second_due_amount_event,
                            third_due_amount_event,
                        ],
                        event_id=loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                        account_id=self.loan_account_id,
                        count=3,
                    ),
                    ExpectedSchedule(
                        run_times=[first_overdue_event, second_overdue_event, third_overdue_event],
                        event_id=loan.overdue.CHECK_OVERDUE_EVENT,
                        account_id=self.loan_account_id,
                        count=3,
                    ),
                    ExpectedSchedule(
                        run_times=[
                            first_delinquency_event,
                            second_delinquency_event,
                            third_delinquency_event,
                        ],
                        event_id=loan.CHECK_DELINQUENCY,
                        account_id=self.loan_account_id,
                        count=3,
                    ),
                    ExpectedSchedule(
                        run_times=[
                            first_accrual_after_conversion_1,
                            first_accrual_after_conversion_2,
                        ],
                        event_id=loan.interest_accrual.ACCRUAL_EVENT,
                        account_id=self.loan_account_id,
                        count=98,
                    ),
                ],
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )

        self.run_test_scenario(
            test_scenario,
            smart_contracts=[convert_to_contract_config_1, convert_to_contract_config_2],
        )

    def test_loan_top_up_when_top_up_parameter_set_to_true(self):
        start = default_simulation_start_datetime
        instance_params = {**self.loan_instance_params, loan.disbursement.PARAM_PRINCIPAL: "1000"}
        template_params = {
            **self.loan_template_params,
            loan.overpayment.PARAM_OVERPAYMENT_FEE_RATE: "0",
        }

        repayment_holiday_start_datetime = start + relativedelta(days=1, seconds=2)
        repayment_holiday_end_datetime = repayment_holiday_start_datetime + relativedelta(days=5)

        first_application_event = start + relativedelta(months=1, days=27, minutes=1)
        first_repayment = first_application_event + relativedelta(seconds=1)

        conversion = first_repayment + relativedelta(days=1)
        end = conversion

        convert_to_version_id = "5"
        convert_to_contract_config = ContractConfig(
            contract_content=self.smart_contract_path_to_content[self.contract_filepath],
            smart_contract_version_id=convert_to_version_id,
            template_params=parameters.loan_template_params,
            account_configs=[],
        )

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
                description="check correct balance after first due amount event",
                events=[
                    create_flag_definition_event(
                        flag_definition_id="REPAYMENT_HOLIDAY", timestamp=start
                    ),
                    create_flag_event(
                        timestamp=repayment_holiday_start_datetime,
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        effective_timestamp=repayment_holiday_start_datetime,
                        expiry_timestamp=repayment_holiday_end_datetime,
                        account_id=self.loan_account_id,
                    ),
                ],
                expected_balances_at_ts={
                    first_application_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("918.31")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("4.50")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.11")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0.42")),
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
                            (dimensions.DEFAULT, Decimal("4.50"))
                        ],
                    }
                },
            ),
            SubTest(
                description="Make an overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # total due + 100 overpayment
                        amount="186.61",
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
                            (dimensions.PRINCIPAL, Decimal("818.31")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0.42")),
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
                            (dimensions.DEFAULT, Decimal("4.50"))
                        ],
                    }
                },
            ),
            SubTest(
                description="Conversion resets tracker balance addresses and reamortises",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=conversion - relativedelta(seconds=1),
                        account_id=self.loan_account_id,
                        **{
                            loan.PARAM_TOP_UP: "True",
                            loan.disbursement.PARAM_PRINCIPAL: "2000",
                            # increase the total term by 10
                            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "22",
                        },
                    ),
                    create_account_product_version_update_instruction(
                        timestamp=conversion,
                        account_id=self.loan_account_id,
                        product_version_id=convert_to_version_id,
                    ),
                ],
                expected_balances_at_ts={
                    conversion
                    - relativedelta(seconds=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("818.31")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.06950")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0.42")),
                            (dimensions.OVERPAYMENT, Decimal("100")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("100"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.07799")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.06950"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("4.50"))
                        ],
                    },
                    conversion: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            # additional 1000 disbursed
                            (dimensions.PRINCIPAL, Decimal("1818.31")),
                            # p = 1818.31
                            # r = round(0.031/12, 10)
                            # n = 21
                            (dimensions.EMI, Decimal("89.07")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.06950")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # should not be reset
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.06950"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("4.50"))
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("2000"))],
                    },
                },
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
        self.run_test_scenario(test_scenario, smart_contracts=[convert_to_contract_config])

    def test_loan_top_up_when_top_up_parameter_set_to_true_monthly_rest_loan(self):
        start = default_simulation_start_datetime
        instance_params = {
            **self.loan_instance_params,
            loan.disbursement.PARAM_PRINCIPAL: "1000",
            loan.PARAM_INTEREST_ACCRUAL_REST_TYPE: "monthly",
        }
        template_params = {
            **self.loan_template_params,
            loan.overpayment.PARAM_OVERPAYMENT_FEE_RATE: "0",
        }

        repayment_holiday_start_datetime = start + relativedelta(days=1, seconds=2)
        repayment_holiday_end_datetime = repayment_holiday_start_datetime + relativedelta(days=5)

        first_application_event = start + relativedelta(months=1, days=27, minutes=1)
        first_repayment = first_application_event + relativedelta(seconds=1)

        conversion = first_repayment + relativedelta(days=1)
        end = conversion

        convert_to_version_id = "5"
        convert_to_contract_config = ContractConfig(
            contract_content=self.smart_contract_path_to_content[self.contract_filepath],
            smart_contract_version_id=convert_to_version_id,
            template_params=parameters.loan_template_params,
            account_configs=[],
        )

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
                description="check correct balance after first due amount event",
                events=[
                    create_flag_definition_event(
                        flag_definition_id="REPAYMENT_HOLIDAY", timestamp=start
                    ),
                    create_flag_event(
                        timestamp=repayment_holiday_start_datetime,
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        effective_timestamp=repayment_holiday_start_datetime,
                        expiry_timestamp=repayment_holiday_end_datetime,
                        account_id=self.loan_account_id,
                    ),
                ],
                expected_balances_at_ts={
                    first_application_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("918.31")),
                            (dimensions.MONTHLY_REST_EFFECTIVE_PRINCIPAL, Decimal("918.31")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("4.50")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.11")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0.42")),
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
                            (dimensions.DEFAULT, Decimal("4.50"))
                        ],
                    }
                },
            ),
            SubTest(
                description="Make an overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # total due + 100 overpayment
                        amount="186.61",
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
                            (dimensions.PRINCIPAL, Decimal("818.31")),
                            (dimensions.MONTHLY_REST_EFFECTIVE_PRINCIPAL, Decimal("918.31")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0.42")),
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
                            (dimensions.DEFAULT, Decimal("4.50"))
                        ],
                    }
                },
            ),
            SubTest(
                description="Conversion resets tracker balance addresses and reamortises",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=conversion - relativedelta(seconds=1),
                        account_id=self.loan_account_id,
                        **{
                            loan.PARAM_TOP_UP: "True",
                            loan.disbursement.PARAM_PRINCIPAL: "2000",
                            # increase the total term by 10
                            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "22",
                        },
                    ),
                    create_account_product_version_update_instruction(
                        timestamp=conversion,
                        account_id=self.loan_account_id,
                        product_version_id=convert_to_version_id,
                    ),
                ],
                expected_balances_at_ts={
                    conversion
                    - relativedelta(seconds=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("818.31")),
                            (dimensions.MONTHLY_REST_EFFECTIVE_PRINCIPAL, Decimal("918.31")),
                            (dimensions.EMI, Decimal("84.74")),
                            # accrual on a balance of 918.31
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.07799")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0.42")),
                            (dimensions.OVERPAYMENT, Decimal("100")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("100"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.07799")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.07799"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("4.50"))
                        ],
                    },
                    conversion: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            # additional 1000 disbursed
                            (dimensions.PRINCIPAL, Decimal("1818.31")),
                            (dimensions.MONTHLY_REST_EFFECTIVE_PRINCIPAL, Decimal("1818.31")),
                            # p = 1818.31
                            # r = round(0.031/12, 10)
                            # n = 21
                            (dimensions.EMI, Decimal("89.07")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.07799")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # should not be reset
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.07799"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("4.50"))
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("2000"))],
                    },
                },
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
        self.run_test_scenario(test_scenario, smart_contracts=[convert_to_contract_config])

    def test_loan_top_up_when_top_up_parameter_not_set_to_true(self):
        start = default_simulation_start_datetime
        instance_params = {**self.loan_instance_params, loan.disbursement.PARAM_PRINCIPAL: "1000"}
        template_params = {
            **self.loan_template_params,
            loan.overpayment.PARAM_OVERPAYMENT_FEE_RATE: "0",
        }

        repayment_holiday_start_datetime = start + relativedelta(days=1, seconds=2)
        repayment_holiday_end_datetime = repayment_holiday_start_datetime + relativedelta(days=5)

        first_application_event = start + relativedelta(months=1, days=27, minutes=1)
        first_repayment = first_application_event + relativedelta(seconds=1)

        conversion_1 = first_repayment + relativedelta(days=1)
        conversion_2 = conversion_1 + relativedelta(minutes=1)
        end = conversion_2

        convert_to_version_id_1 = "5"
        convert_to_contract_config_1 = ContractConfig(
            contract_content=self.smart_contract_path_to_content[self.contract_filepath],
            smart_contract_version_id=convert_to_version_id_1,
            template_params=parameters.loan_template_params,
            account_configs=[],
        )
        convert_to_version_id_2 = "6"
        convert_to_contract_config_2 = ContractConfig(
            contract_content=self.smart_contract_path_to_content[self.contract_filepath],
            smart_contract_version_id=convert_to_version_id_2,
            template_params=parameters.loan_template_params,
            account_configs=[],
        )

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
                description="check correct balance after first due amount event",
                events=[
                    create_flag_definition_event(
                        flag_definition_id="REPAYMENT_HOLIDAY", timestamp=start
                    ),
                    create_flag_event(
                        timestamp=repayment_holiday_start_datetime,
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        effective_timestamp=repayment_holiday_start_datetime,
                        expiry_timestamp=repayment_holiday_end_datetime,
                        account_id=self.loan_account_id,
                    ),
                ],
                expected_balances_at_ts={
                    first_application_event: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("918.31")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("4.50")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.11")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0.42")),
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
                            (dimensions.DEFAULT, Decimal("4.50"))
                        ],
                    }
                },
            ),
            SubTest(
                description="Make an overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # total due + 100 overpayment
                        amount="186.61",
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
                            (dimensions.PRINCIPAL, Decimal("818.31")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0.42")),
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
                            (dimensions.DEFAULT, Decimal("4.50"))
                        ],
                    }
                },
            ),
            SubTest(
                description="Conversion when parameter is unset does not trigger top up",
                events=[
                    create_account_product_version_update_instruction(
                        timestamp=conversion_1,
                        account_id=self.loan_account_id,
                        product_version_id=convert_to_version_id_1,
                    ),
                ],
                expected_balances_at_ts={
                    conversion_1
                    - relativedelta(seconds=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("818.31")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.06950")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0.42")),
                            (dimensions.OVERPAYMENT, Decimal("100")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("100"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.07799")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.06950"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("4.50"))
                        ],
                    },
                    conversion_1: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("818.31")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.06950")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0.42")),
                            (dimensions.OVERPAYMENT, Decimal("100")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("100"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.07799")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.06950"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("4.50"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Conversion when parameter is set to false does not trigger top up",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=conversion_2 - relativedelta(seconds=1),
                        account_id=self.loan_account_id,
                        **{loan.PARAM_TOP_UP: "False"},
                    ),
                    create_account_product_version_update_instruction(
                        timestamp=conversion_2,
                        account_id=self.loan_account_id,
                        product_version_id=convert_to_version_id_2,
                    ),
                ],
                expected_balances_at_ts={
                    conversion_2
                    - relativedelta(seconds=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("818.31")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.06950")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0.42")),
                            (dimensions.OVERPAYMENT, Decimal("100")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("100"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.07799")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.06950"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("4.50"))
                        ],
                    },
                    conversion_2: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("818.31")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.06950")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0.42")),
                            (dimensions.OVERPAYMENT, Decimal("100")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("100"),
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.07799")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.06950"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, Decimal("4.50"))
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
            template_params=template_params,
            debug=False,
        )
        self.run_test_scenario(
            test_scenario,
            smart_contracts=[convert_to_contract_config_1, convert_to_contract_config_2],
        )


class EarlyRepaymentTest(LoanTestBase):
    def test_loan_early_repayment_using_fee_rate(self):
        start = default_simulation_start_datetime
        early_repayment_date = start + relativedelta(seconds=1)
        end = start + relativedelta(seconds=2)
        instance_params = {
            **self.loan_instance_params,
            loan.disbursement.PARAM_PRINCIPAL: "1000",
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "1",
        }
        template_params = {
            **self.loan_template_params,
            loan.early_repayment.PARAM_EARLY_REPAYMENT_FLAT_FEE: "0",
            loan.early_repayment.PARAM_EARLY_REPAYMENT_FEE_RATE: "0.02",
        }

        sub_tests = [
            SubTest(
                description="Make an early repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1072.63",
                        event_datetime=early_repayment_date,
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    early_repayment_date: {
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
                            (dimensions.OVERPAYMENT, Decimal("1000")),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                Decimal("0"),
                            ),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        accounts.INTERNAL_EARLY_REPAYMENT_FEE_INCOME: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [
                            (dimensions.DEFAULT, Decimal("52.63"))
                        ],
                    }
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=early_repayment_date,
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
                        timestamp=early_repayment_date,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.early_repayment.PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT,
                        value="1072.63",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=early_repayment_date,
                        account_id=self.loan_account_id,
                        name=loan.early_repayment.PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT,
                        value="0.00",
                    ),
                ],
            ),
            SubTest(
                description="Close the account",
                events=[
                    update_account_status_pending_closure(
                        timestamp=end,
                        account_id=self.loan_account_id,
                    ),
                ],
                expected_balances_at_ts={
                    end: {
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
            debug=False,
        )
        self.run_test_scenario(test_scenario)

    def test_loan_early_repayment_using_flat_fee(self):
        start = default_simulation_start_datetime
        rejected_overpayment_date = start + relativedelta(seconds=1)
        overpayment_date = start + relativedelta(seconds=2)
        early_repayment_date = start + relativedelta(seconds=3)
        end = start + relativedelta(seconds=4)
        instance_params = {
            **self.loan_instance_params,
            loan.disbursement.PARAM_PRINCIPAL: "1000",
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "1",
        }
        template_params = {
            **self.loan_template_params,
            loan.early_repayment.PARAM_EARLY_REPAYMENT_FLAT_FEE: "500",
            loan.early_repayment.PARAM_EARLY_REPAYMENT_FEE_RATE: "0",
        }

        sub_tests = [
            SubTest(
                description="The exact max overpayment should be rejected",
                events=[
                    # 1052.63 = principal 1000 + overpayment fee 52.63
                    create_inbound_hard_settlement_instruction(
                        amount="1052.63",
                        event_datetime=rejected_overpayment_date,
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=rejected_overpayment_date,
                        account_id=self.loan_account_id,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Cannot repay remaining debt without paying early "
                        "repayment fees, amount required is 1552.63",
                    )
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=rejected_overpayment_date,
                        account_id=self.loan_account_id,
                        name=loan.early_repayment.PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT,
                        value="1552.63",
                    ),
                ],
            ),
            SubTest(
                description="The exact max overpayment minus 1 penny should be accepted",
                events=[
                    # 1052.62 = principal 1000 + max overpayment fee 52.63 - 0.01
                    create_inbound_hard_settlement_instruction(
                        amount="1052.62",
                        event_datetime=overpayment_date,
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    overpayment_date: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0.01")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0")),
                            (dimensions.CAPITALISED_PENALTIES_TRACKER, Decimal("0")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("999.99")),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                Decimal("0"),
                            ),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [
                            (dimensions.DEFAULT, Decimal("52.63"))
                        ],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=overpayment_date,
                        account_id=self.loan_account_id,
                        name=loan.early_repayment.PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT,
                        value="500.01",
                    ),
                ],
            ),
            SubTest(
                description="Make the early repayment",
                events=[
                    # 500.01 = principal 0.01 + overpayment fee 0 + flat fee 500
                    create_inbound_hard_settlement_instruction(
                        amount="500.01",
                        event_datetime=early_repayment_date,
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.INTERNAL,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    early_repayment_date: {
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
                            (dimensions.OVERPAYMENT, Decimal("1000")),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                Decimal("0"),
                            ),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        accounts.INTERNAL_EARLY_REPAYMENT_FEE_INCOME: [
                            (dimensions.DEFAULT, Decimal("500"))
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [
                            (dimensions.DEFAULT, Decimal("52.63"))
                        ],
                    }
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=early_repayment_date,
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
                        timestamp=early_repayment_date,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=early_repayment_date,
                        account_id=self.loan_account_id,
                        name=loan.early_repayment.PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT,
                        value="0.00",
                    ),
                ],
            ),
            SubTest(
                description="Close the account",
                events=[
                    update_account_status_pending_closure(
                        timestamp=end,
                        account_id=self.loan_account_id,
                    ),
                ],
                expected_balances_at_ts={
                    end: {
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
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=end,
                        account_id=self.loan_account_id,
                        name=loan.early_repayment.PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT,
                        value="0.00",
                    ),
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
        self.run_test_scenario(test_scenario)
