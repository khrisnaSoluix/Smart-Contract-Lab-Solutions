# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

# library
import library.line_of_credit.constants.accounts as accounts
import library.line_of_credit.constants.dimensions as dimensions
import library.line_of_credit.constants.test_parameters as test_parameters
import library.line_of_credit.contracts.template.drawdown_loan as drawdown_loan
import library.line_of_credit.contracts.template.line_of_credit as line_of_credit
from library.line_of_credit.supervisors.template import line_of_credit_supervisor
from library.line_of_credit.test.simulation.test_line_of_credit_supervisor_common import (
    DEFAULT_PLAN_ID,
    LineOfCreditSupervisorCommonTest,
    get_mimic_loan_creation_subtest,
)

# features
import library.features.v4.common.supervisor_utils as supervisor_utils
import library.features.v4.lending.lending_addresses as addresses

# inception sdk
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    ContractNotificationResourceType,
    ExpectedContractNotification,
    ExpectedDerivedParameter,
    ExpectedRejection,
    ExpectedSchedule,
    SimulationTestScenario,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_account_instruction,
    create_account_plan_assoc_instruction,
    create_custom_instruction,
    create_instance_parameter_change_event,
    create_outbound_hard_settlement_instruction,
)

REPAYMENT_DUE_NOTIFICATION = line_of_credit_supervisor.REPAYMENT_DUE_NOTIFICATION
REPAYMENT_OVERDUE_NOTIFICATION = (
    f"{line_of_credit_supervisor.LOC_ACCOUNT_TYPE}"
    f"{line_of_credit_supervisor.overdue.OVERDUE_REPAYMENT_NOTIFICATION_SUFFIX}"
)
DELINQUENT_NOTIFICATION = line_of_credit_supervisor.DELINQUENT_NOTIFICATION

ACCRUAL_EVENT = line_of_credit_supervisor.interest_accrual_supervisor.ACCRUAL_EVENT
DUE_AMOUNT_CALCULATION_EVENT = (
    line_of_credit_supervisor.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT
)


class LineOfCreditSupervisorSchedulesTest(LineOfCreditSupervisorCommonTest):
    def test_schedule_setup(self):
        start = datetime(year=2021, month=1, day=1, hour=1, minute=30, tzinfo=ZoneInfo("UTC"))
        setup_schedule_event = start + relativedelta(seconds=30)
        first_daily_event = datetime(
            year=2021, month=1, day=2, hour=0, minute=0, second=0, tzinfo=ZoneInfo("UTC")
        )
        first_monthly_event = datetime(
            year=2021, month=2, day=5, hour=0, minute=0, second=2, tzinfo=ZoneInfo("UTC")
        )
        end = first_monthly_event
        sub_tests = [
            SubTest(
                description="schedules are set correctly",
                expected_schedules=[
                    ExpectedSchedule(
                        event_id=supervisor_utils.SUPERVISEE_SCHEDULE_SYNC_EVENT,
                        run_times=[setup_schedule_event],
                        plan_id=DEFAULT_PLAN_ID,
                        count=1,
                    ),
                    ExpectedSchedule(
                        event_id=ACCRUAL_EVENT,
                        run_times=[first_daily_event],
                        plan_id=DEFAULT_PLAN_ID,
                        count=35,
                    ),
                    ExpectedSchedule(
                        event_id=DUE_AMOUNT_CALCULATION_EVENT,
                        run_times=[first_monthly_event],
                        plan_id=DEFAULT_PLAN_ID,
                        count=1,
                    ),
                ],
            )
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_interest_accrual(self):
        start = test_parameters.default_simulation_start_date
        first_accrual_time = start.replace(hour=22, minute=30) + relativedelta(days=1)
        before_first_accrual_time = first_accrual_time - relativedelta(minutes=1)
        after_first_accrual_time = first_accrual_time + relativedelta(minutes=1)
        repayment_posting_time = start.replace(day=3, hour=0, minute=0, second=1)
        end = start + relativedelta(days=6)

        loc_template_params = test_parameters.loc_template_params.copy()
        new_accrual_time = {
            line_of_credit.interest_accrual.PARAM_INTEREST_ACCRUAL_HOUR: "22",
            line_of_credit.interest_accrual.PARAM_INTEREST_ACCRUAL_MINUTE: "30",
            line_of_credit.interest_accrual.PARAM_INTEREST_ACCRUAL_SECOND: "0",
        }
        loc_template_params.update(new_accrual_time)

        sub_tests = [
            SubTest(
                description="check non emi interest accrues while loans are over 1 month away"
                + " from first due amount calculation date",
                expected_schedules=[
                    ExpectedSchedule(
                        event_id=ACCRUAL_EVENT,
                        run_times=[first_accrual_time],
                        plan_id=DEFAULT_PLAN_ID,
                        count=6,
                    ),
                ],
                expected_balances_at_ts={
                    before_first_accrual_time: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.EMI, "90.21"),
                            (dimensions.INTERNAL_CONTRA, "-90.21"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.EMI, "90.21"),
                            (dimensions.INTERNAL_CONTRA, "-90.21"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.TOTAL_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (
                                dimensions.TOTAL_NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
                                Decimal("0"),
                            ),
                            (dimensions.TOTAL_PENALTIES, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("2000"))],
                        accounts.ACCRUED_INTEREST_RECEIVABLE: [(dimensions.DEFAULT, Decimal("0"))],
                    },
                    # Over a month before due amount calculation so interest should go to
                    # non emi accrued interest receivable account
                    after_first_accrual_time: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.EMI, "90.21"),
                            (dimensions.INTERNAL_CONTRA, "-90.61822"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            # rounded 1000*(0.149/365) = 0.40822
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.40822")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0.40822")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.EMI, "90.21"),
                            (dimensions.INTERNAL_CONTRA, "-90.61822"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            # rounded 1000*(0.149/365) = 0.40822
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.40822")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0.40822")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.TOTAL_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (
                                dimensions.TOTAL_NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
                                Decimal("0.81644"),
                            ),
                            (dimensions.TOTAL_PENALTIES, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("2000"))],
                        accounts.ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.81644"))
                        ],
                    },
                },
            ),
            # TODO: Rework after repayment logic has been implemented
            SubTest(
                description="Check that balance changes after midnight do not affect "
                "interest accrual until next day",
                events=[
                    create_custom_instruction(
                        amount="10",
                        debtor_target_account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0",
                        creditor_target_account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0",
                        debtor_target_account_address="OVERPAYMENT",
                        creditor_target_account_address=addresses.PRINCIPAL,
                        event_datetime=repayment_posting_time,
                        instruction_details={"force_override": "true"},
                    )
                ],
                expected_balances_at_ts={
                    before_first_accrual_time
                    + relativedelta(days=1): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "990"),
                            (dimensions.EMI, "90.21"),
                            (dimensions.INTERNAL_CONTRA, "-90.61822"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.40822")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0.40822")),
                            (dimensions.OVERPAYMENT, Decimal("10")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.EMI, "90.21"),
                            (dimensions.INTERNAL_CONTRA, "-90.61822"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.40822")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0.40822")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.TOTAL_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (
                                dimensions.TOTAL_NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
                                Decimal("0.81644"),
                            ),
                            (dimensions.TOTAL_PENALTIES, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("2000"))],
                        accounts.ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-0.81644"))
                        ],
                    },
                    after_first_accrual_time
                    + relativedelta(days=1): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "990"),
                            (dimensions.EMI, "90.21"),
                            (dimensions.INTERNAL_CONTRA, "-91.02644"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            # rounded 1000*2(0.149/365) = 0.81644
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.81644")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0.81644")),
                            (BalanceDimensions("OVERPAYMENT"), Decimal("10")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.EMI, "90.21"),
                            (dimensions.INTERNAL_CONTRA, "-91.02644"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            # rounded 1000*2(0.149/365) = 0.81644
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.81644")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0.81644")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.TOTAL_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (
                                dimensions.TOTAL_NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
                                Decimal("1.63288"),
                            ),
                            (dimensions.TOTAL_PENALTIES, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("2000"))],
                        accounts.ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-1.63288"))
                        ],
                    },
                    after_first_accrual_time
                    + relativedelta(days=2): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "990"),
                            (dimensions.EMI, "90.21"),
                            (dimensions.INTERNAL_CONTRA, "-91.43466"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            # rounded 1000*3(0.149/365) = 1.22466
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("1.22466")),
                            # rounded 1000*2(0.149/365) + 990*(.0149/365) = 1.22058
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("1.22058")),
                            (BalanceDimensions("OVERPAYMENT"), Decimal("10")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.EMI, "90.21"),
                            (dimensions.INTERNAL_CONTRA, "-91.43466"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            # rounded 1000*3(0.149/365) = 1.22466
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("1.22466")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("1.22466")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.TOTAL_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (
                                dimensions.TOTAL_NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
                                Decimal("2.44524"),
                            ),
                            (dimensions.TOTAL_PENALTIES, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("2000"))],
                        accounts.ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-2.44524"))
                        ],
                    },
                },
            ),
            SubTest(
                description="check regular interest accrues when loan is less than 1 month away"
                + " from first due calculation date",
                expected_balances_at_ts={
                    # due amount calculation happens on day 5, after interest accrual
                    before_first_accrual_time.replace(day=6): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "990"),
                            (dimensions.EMI, "90.21"),
                            (dimensions.INTERNAL_CONTRA, "-91.84288"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("1.63288")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("1.62472")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.EMI, "90.21"),
                            (dimensions.INTERNAL_CONTRA, "-91.84288"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("1.63288")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("1.63288")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.TOTAL_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (
                                dimensions.TOTAL_NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
                                Decimal("3.25760"),
                            ),
                            (dimensions.TOTAL_PENALTIES, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("2000"))],
                        accounts.ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-3.25760"))
                        ],
                    },
                    after_first_accrual_time.replace(day=6): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "990"),
                            (dimensions.EMI, "90.21"),
                            (dimensions.INTERNAL_CONTRA, "-92.2511"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.40414")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("1.62472")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("2.0411")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.EMI, "90.21"),
                            (dimensions.INTERNAL_CONTRA, "-92.2511"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.40822")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("1.63288")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("2.0411")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.TOTAL_ACCRUED_INTEREST_RECEIVABLE, Decimal("0.81236")),
                            (
                                dimensions.TOTAL_NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
                                Decimal("3.2576"),
                            ),
                            (dimensions.TOTAL_PENALTIES, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("2000"))],
                        accounts.ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-4.06996"))
                        ],
                    },
                },
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loc_template_params=loc_template_params,
                drawdown_loan_instances=2,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_changing_due_calc_day_when_interest_accrual_scheduled_before_due_calc_event(self):
        """
        2020/01/01 account is created
        2020/02/05 first due amount event
        2020/02/14 due calc day updated to 20
        2020/03/18 due calc day updated to 7
        2020/03/19 due calc day updated to 6
        2020/03/20 second due amount event
        2020/04/06 third due amount event
        """
        start = test_parameters.default_simulation_start_date
        first_accrual_time = start + relativedelta(days=1)
        first_due_amount_event = datetime(
            year=2020, month=2, day=5, hour=0, minute=0, second=2, tzinfo=ZoneInfo("UTC")
        )
        before_first_due_amount_event = first_due_amount_event - relativedelta(seconds=1)
        first_overdue_event = first_due_amount_event + relativedelta(days=7)
        first_delinquency_event = first_overdue_event.replace(minute=1, second=0) + relativedelta(
            days=2
        )
        updated_due_day = "20"
        change_due_calc_day_param = first_delinquency_event + relativedelta(seconds=1)
        second_due_amount_event = first_due_amount_event.replace(month=3, day=int(updated_due_day))
        second_overdue_event = second_due_amount_event + relativedelta(days=7)
        second_delinquency_event = second_overdue_event.replace(minute=1, second=0) + relativedelta(
            days=2
        )
        change_due_calc_day_again = second_due_amount_event - relativedelta(days=2)
        change_due_calc_day_third = second_due_amount_event - relativedelta(days=1)
        updated_again_due_day = "7"
        updated_third_due_day = "6"
        third_due_amount_event = first_due_amount_event.replace(
            month=4, day=int(updated_third_due_day)
        )
        end = third_due_amount_event

        sub_tests = [
            get_mimic_loan_creation_subtest(start=start, amount="1000", drawdown_loan_instances=2),
            SubTest(
                description="changing the due amount calc day before the first due calc event",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=before_first_due_amount_event,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        due_amount_calculation_day="20",
                    ),
                ],
                expected_parameter_change_rejections=[
                    ExpectedRejection(
                        timestamp=before_first_due_amount_event,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
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
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        due_amount_calculation_day=updated_due_day,
                    ),
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=change_due_calc_day_param - relativedelta(seconds=1),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="next_repayment_date",
                        value="2020-03-05",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=change_due_calc_day_param + relativedelta(seconds=1),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="next_repayment_date",
                        value="2020-03-20",
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
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        due_amount_calculation_day=updated_again_due_day,
                    ),
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        # just before the due calc day param is changed to 7 on the 18th
                        timestamp=change_due_calc_day_again - relativedelta(seconds=1),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="next_repayment_date",
                        value="2020-03-20",
                    ),
                    ExpectedDerivedParameter(
                        # just after the due calc day param is changed to 7 on the 18th
                        timestamp=change_due_calc_day_again + relativedelta(seconds=1),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="next_repayment_date",
                        value="2020-03-20",
                    ),
                ],
            ),
            SubTest(
                description="changing due amount calc day for a third time between due calc events",
                # the new due calc day value will take effect for the 3rd due calc event
                events=[
                    create_instance_parameter_change_event(
                        timestamp=change_due_calc_day_third,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        due_amount_calculation_day=updated_third_due_day,
                    ),
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        # just before the due calc day param is changed to 6 on the 19th
                        timestamp=change_due_calc_day_third - relativedelta(seconds=1),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="next_repayment_date",
                        value="2020-03-20",
                    ),
                    ExpectedDerivedParameter(
                        # just after the due calc day param is changed to 6 on the 19th
                        timestamp=change_due_calc_day_third + relativedelta(hours=10),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="next_repayment_date",
                        value="2020-03-20",
                    ),
                    ExpectedDerivedParameter(
                        # just after the second due amount event on the 20th
                        timestamp=second_due_amount_event + relativedelta(seconds=1),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="next_repayment_date",
                        value="2020-04-06",
                    ),
                ],
            ),
            SubTest(
                description="schedules ran correctly",
                expected_schedules=[
                    ExpectedSchedule(
                        event_id=ACCRUAL_EVENT,
                        run_times=[first_accrual_time],
                        plan_id=DEFAULT_PLAN_ID,
                        count=96,
                    ),
                    ExpectedSchedule(
                        event_id=DUE_AMOUNT_CALCULATION_EVENT,
                        run_times=[
                            first_due_amount_event,
                            second_due_amount_event,
                            third_due_amount_event,
                        ],
                        plan_id=DEFAULT_PLAN_ID,
                        count=3,
                    ),
                    ExpectedSchedule(
                        event_id=DUE_AMOUNT_CALCULATION_EVENT,
                        run_times=[
                            first_due_amount_event,
                            second_due_amount_event,
                            third_due_amount_event,
                        ],
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        count=3,
                    ),
                    ExpectedSchedule(
                        event_id=line_of_credit_supervisor.overdue.CHECK_OVERDUE_EVENT,
                        run_times=[first_overdue_event, second_overdue_event],
                        plan_id=DEFAULT_PLAN_ID,
                        count=2,
                    ),
                    ExpectedSchedule(
                        event_id=line_of_credit_supervisor.delinquency.CHECK_DELINQUENCY_EVENT,
                        run_times=[first_delinquency_event, second_delinquency_event],
                        plan_id=DEFAULT_PLAN_ID,
                        count=2,
                    ),
                ],
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                drawdown_loan_instances=2,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_changing_due_calc_day_when_interest_accrual_scheduled_after_due_calc_event(self):
        start = test_parameters.default_simulation_start_date
        first_accrual_time = start.replace(hour=22, minute=30) + relativedelta(days=1)
        first_due_amount_event = datetime(
            year=2020, month=2, day=5, hour=0, minute=0, second=2, tzinfo=ZoneInfo("UTC")
        )
        updated_due_day = "6"
        change_due_calc_day_param = first_due_amount_event + relativedelta(seconds=1)
        second_due_amount_event = datetime(
            year=2020, month=3, day=6, hour=0, minute=0, second=2, tzinfo=ZoneInfo("UTC")
        )
        updated_again_due_day = "5"
        change_due_calc_day_again = datetime(
            year=2020, month=3, day=5, hour=12, minute=0, second=2, tzinfo=ZoneInfo("UTC")
        )
        third_due_amount_event = datetime(
            year=2020, month=4, day=5, hour=0, minute=0, second=2, tzinfo=ZoneInfo("UTC")
        )
        end = third_due_amount_event

        loc_template_params = test_parameters.loc_template_params.copy()
        new_accrual_time = {
            line_of_credit.interest_accrual.PARAM_INTEREST_ACCRUAL_HOUR: "22",
            line_of_credit.interest_accrual.PARAM_INTEREST_ACCRUAL_MINUTE: "30",
            line_of_credit.interest_accrual.PARAM_INTEREST_ACCRUAL_SECOND: "0",
        }
        loc_template_params.update(new_accrual_time)

        sub_tests = [
            get_mimic_loan_creation_subtest(start=start, amount="1000", drawdown_loan_instances=2),
            SubTest(
                description="changing the due amount calc day after the first due calc event",
                # the new due calc day value will take effect for the 2nd due calc event next month
                events=[
                    create_instance_parameter_change_event(
                        timestamp=change_due_calc_day_param,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        due_amount_calculation_day=updated_due_day,
                    ),
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=change_due_calc_day_param - relativedelta(seconds=1),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="next_repayment_date",
                        value="2020-03-05",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=change_due_calc_day_param + relativedelta(seconds=1),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="next_repayment_date",
                        value="2020-03-06",
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
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        due_amount_calculation_day=updated_again_due_day,
                    ),
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        # just before the due calc day param is changed back to 5 on the 5th
                        timestamp=change_due_calc_day_again - relativedelta(seconds=1),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="next_repayment_date",
                        value="2020-03-06",
                    ),
                    ExpectedDerivedParameter(
                        # just after the due calc day param is changed back to 5 on the 5th
                        timestamp=change_due_calc_day_again + relativedelta(seconds=1),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="next_repayment_date",
                        value="2020-03-06",
                    ),
                    ExpectedDerivedParameter(
                        # after the next due calc event ran on the 6th
                        timestamp=second_due_amount_event + relativedelta(seconds=1),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="next_repayment_date",
                        value="2020-04-05",
                    ),
                ],
            ),
            SubTest(
                description="schedules ran correctly",
                expected_schedules=[
                    ExpectedSchedule(
                        event_id=ACCRUAL_EVENT,
                        run_times=[first_accrual_time],
                        plan_id=DEFAULT_PLAN_ID,
                        count=95,
                    ),
                    ExpectedSchedule(
                        event_id=DUE_AMOUNT_CALCULATION_EVENT,
                        run_times=[
                            first_due_amount_event,
                            second_due_amount_event,
                            third_due_amount_event,
                        ],
                        plan_id=DEFAULT_PLAN_ID,
                        count=3,
                    ),
                    ExpectedSchedule(
                        event_id=DUE_AMOUNT_CALCULATION_EVENT,
                        run_times=[
                            first_due_amount_event,
                            second_due_amount_event,
                            third_due_amount_event,
                        ],
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        count=3,
                    ),
                ],
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loc_template_params=loc_template_params,
                drawdown_loan_instances=2,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_lifecycle_of_schedules_with_no_repayments(self):
        start = test_parameters.default_simulation_start_date
        first_due_amount_event = datetime(
            year=2020, month=2, day=5, hour=0, minute=0, second=2, tzinfo=ZoneInfo("UTC")
        )
        before_first_due_amount_event = first_due_amount_event - relativedelta(seconds=1)
        first_overdue_event = first_due_amount_event + relativedelta(days=7)
        before_first_overdue_event = first_overdue_event - relativedelta(seconds=1)
        first_delinquency_event = first_overdue_event.replace(minute=1, second=0) + relativedelta(
            days=2
        )
        second_due_amount_event = first_due_amount_event + relativedelta(months=1)
        end = second_due_amount_event + relativedelta(seconds=1)

        sub_tests = [
            SubTest(
                description="Make postings to use credit limit - loans already opened due to sim"
                "setup",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start,
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                        batch_details={"force_override": "true"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start,
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                        batch_details={"force_override": "true"},
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("2000")),
                        ],
                    },
                },
            ),
            SubTest(
                description="balances before first due amount calculation event",
                expected_balances_at_ts={
                    before_first_due_amount_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.EMI, Decimal("90.21")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("12.65482")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("1.63288")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.EMI, Decimal("90.21")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("12.65482")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("1.63288")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("2000")),
                            (dimensions.TOTAL_PRINCIPAL, Decimal("2000")),
                            (dimensions.TOTAL_PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.TOTAL_INTEREST_DUE, Decimal("0")),
                            (dimensions.TOTAL_EMI, Decimal("180.42")),
                            (dimensions.TOTAL_ACCRUED_INTEREST_RECEIVABLE, Decimal("25.30964")),
                            (
                                dimensions.TOTAL_NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
                                Decimal("3.26576"),
                            ),
                            (dimensions.TOTAL_PENALTIES, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("2000"))],
                        accounts.ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-28.5754"))
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_first_due_amount_event,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_outstanding_due",
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_first_due_amount_event,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="next_repayment_date",
                        value="2020-02-05",
                    ),
                ],
            ),
            SubTest(
                description="balances after first due amount calculation event",
                expected_balances_at_ts={
                    first_due_amount_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("922.45")),
                            (dimensions.PRINCIPAL_DUE, Decimal("77.55")),
                            (dimensions.INTEREST_DUE, Decimal("14.29")),
                            (dimensions.EMI, Decimal("90.21")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("922.45")),
                            (dimensions.PRINCIPAL_DUE, Decimal("77.55")),
                            (dimensions.INTEREST_DUE, Decimal("14.29")),
                            (dimensions.EMI, Decimal("90.21")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("2000")),
                            (dimensions.TOTAL_PRINCIPAL, Decimal("1844.90")),
                            (dimensions.TOTAL_PRINCIPAL_DUE, Decimal("155.10")),
                            (dimensions.TOTAL_INTEREST_DUE, Decimal("28.58")),
                            (dimensions.TOTAL_EMI, Decimal("180.42")),
                            (dimensions.TOTAL_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (
                                dimensions.TOTAL_NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
                                Decimal("0"),
                            ),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.TOTAL_PENALTIES, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("2000"))],
                        accounts.ACCRUED_INTEREST_RECEIVABLE: [(dimensions.DEFAULT, Decimal("0"))],
                    },
                },
                expected_derived_parameters=[
                    # This value is: Total Principal Due + Total Interest Due
                    # So 155.10 + 28.58 = 183.68
                    ExpectedDerivedParameter(
                        timestamp=first_due_amount_event,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_outstanding_due",
                        value="183.68",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_due_amount_event + relativedelta(seconds=1),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="next_repayment_date",
                        value="2020-03-05",
                    ),
                ],
            ),
            SubTest(
                description="Check repayment due notification",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=first_due_amount_event,
                        notification_type=REPAYMENT_DUE_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                            "repayment_amount": "183.68",
                            "overdue_date": "2020-02-12",
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="balances before first overdue event",
                expected_balances_at_ts={
                    before_first_overdue_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("922.45")),
                            (dimensions.PRINCIPAL_DUE, Decimal("77.55")),
                            (dimensions.INTEREST_DUE, Decimal("14.29")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.EMI, Decimal("90.21")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.63592")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("922.45")),
                            (dimensions.PRINCIPAL_DUE, Decimal("77.55")),
                            (dimensions.INTEREST_DUE, Decimal("14.29")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.EMI, Decimal("90.21")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.63592")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("2000")),
                            (dimensions.TOTAL_PRINCIPAL, Decimal("1844.90")),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.TOTAL_INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.TOTAL_PRINCIPAL_DUE, Decimal("155.10")),
                            (dimensions.TOTAL_INTEREST_DUE, Decimal("28.58")),
                            (dimensions.TOTAL_EMI, Decimal("180.42")),
                            (dimensions.TOTAL_ACCRUED_INTEREST_RECEIVABLE, Decimal("5.27184")),
                            (
                                dimensions.TOTAL_NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
                                Decimal("0"),
                            ),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.TOTAL_PENALTIES, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("2000"))],
                        accounts.ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-5.27184"))
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_first_overdue_event,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_arrears",
                        value="0",
                    ),
                ],
            ),
            SubTest(
                description="balances after first overdue event",
                expected_balances_at_ts={
                    first_overdue_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("922.45")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("77.55")),
                            (dimensions.INTEREST_OVERDUE, Decimal("14.29")),
                            (dimensions.EMI, Decimal("90.21")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.63592")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("922.45")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("77.55")),
                            (dimensions.INTEREST_OVERDUE, Decimal("14.29")),
                            (dimensions.EMI, Decimal("90.21")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.63592")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("2000")),
                            (dimensions.TOTAL_PRINCIPAL, Decimal("1844.90")),
                            (dimensions.TOTAL_PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.TOTAL_INTEREST_DUE, Decimal("0")),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, Decimal("155.10")),
                            (dimensions.TOTAL_INTEREST_OVERDUE, Decimal("28.58")),
                            (dimensions.TOTAL_EMI, Decimal("180.42")),
                            (dimensions.TOTAL_ACCRUED_INTEREST_RECEIVABLE, Decimal("5.27184")),
                            (
                                dimensions.TOTAL_NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
                                Decimal("0"),
                            ),
                            (dimensions.PENALTIES, Decimal("25")),
                            (dimensions.TOTAL_PENALTIES, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("2000"))],
                        accounts.ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-5.27184"))
                        ],
                        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("25"))
                        ],
                    },
                },
                expected_derived_parameters=[
                    # This value is: Total Principal Overdue + Total Interest Overdue
                    # So 155.10 + 28.58 = 183.68
                    ExpectedDerivedParameter(
                        timestamp=first_overdue_event,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_arrears",
                        value="183.68",
                    ),
                ],
            ),
            SubTest(
                description="Check repayment overdue notification",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=first_overdue_event,
                        notification_type=REPAYMENT_OVERDUE_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                            "overdue_principal": "155.10",
                            "overdue_interest": "28.58",
                            "late_repayment_fee": "25",
                            "overdue_date": "2020-02-12",
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                # the only balances changed since first overdue event are from interest accrual
                description="balances after first delinquency event",
                expected_balances_at_ts={
                    first_delinquency_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("922.45")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("77.55")),
                            (dimensions.INTEREST_OVERDUE, Decimal("14.29")),
                            (dimensions.EMI, Decimal("90.21")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("3.38904")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            # penalty interest rate of 0.05 includes base interest rate of 0.149
                            # so ((0.05 + 0.149) / 365) * (77.55 + 14.29) * 2 = 0.10014
                            (dimensions.PENALTIES, Decimal("0.1")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("922.45")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("77.55")),
                            (dimensions.INTEREST_OVERDUE, Decimal("14.29")),
                            (dimensions.EMI, Decimal("90.21")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("3.38904")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0.1")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("2000")),
                            (dimensions.TOTAL_PRINCIPAL, Decimal("1844.90")),
                            (dimensions.TOTAL_PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.TOTAL_INTEREST_DUE, Decimal("0")),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, Decimal("155.10")),
                            (dimensions.TOTAL_INTEREST_OVERDUE, Decimal("28.58")),
                            (dimensions.TOTAL_EMI, Decimal("180.42")),
                            (dimensions.TOTAL_ACCRUED_INTEREST_RECEIVABLE, Decimal("6.77808")),
                            (
                                dimensions.TOTAL_NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
                                Decimal("0"),
                            ),
                            (dimensions.PENALTIES, Decimal("25")),
                            (dimensions.TOTAL_PENALTIES, Decimal("0.2")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("2000"))],
                        accounts.ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, Decimal("-6.77808"))
                        ],
                        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("25"))
                        ],
                    },
                },
                expected_derived_parameters=[
                    # since there are no extra early repayment fees, the early repayment amount is
                    # the same as the maximum overpayment including the associated overpayment fee.
                    # early_repayment_amount = total outstanding amount + max overpayment fee,
                    # where the max overpayment fee is:
                    # (remaining principal * overpayment fee rate) / (1 - overpayment fee rate)
                    # total_outstanding_debt:
                    #   922.45 remaining principal
                    #   + 77.55 principal overdue
                    #   + 14.29 interest overdue
                    #   + 3.38904 accrued interest
                    #   + 0.1 penalties
                    #   = 1017.77904, which rounds to 1017.78
                    # per_loan_early_repayment_amount: 1017.78 + 922.45 * 0.05 / (1-0.05) = 1066.33
                    # total_early_repayment_amount: 1066.33 * 2 loans + 25 penalty = 2157.66
                    ExpectedDerivedParameter(
                        timestamp=first_delinquency_event,
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0",
                        name="per_loan_early_repayment_amount",
                        value="1066.33",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_delinquency_event,
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1",
                        name="per_loan_early_repayment_amount",
                        value="1066.33",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_delinquency_event,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_early_repayment_amount",
                        value="2157.66",
                    ),
                    # 2 * EMI
                    ExpectedDerivedParameter(
                        timestamp=first_delinquency_event,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_monthly_repayment",
                        value="180.42",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_delinquency_event,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_original_principal",
                        value="2000.00",
                    ),
                ],
            ),
            SubTest(
                description="Check delinquency notification",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=first_delinquency_event,
                        notification_type=DELINQUENT_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="checking next_repayment_date derived param after second due event",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=second_due_amount_event - relativedelta(seconds=1),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="next_repayment_date",
                        value="2020-03-05",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_due_amount_event + relativedelta(seconds=1),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="next_repayment_date",
                        value="2020-04-05",
                    ),
                ],
            ),
            SubTest(
                description="schedules ran correctly",
                expected_schedules=[
                    ExpectedSchedule(
                        event_id=DUE_AMOUNT_CALCULATION_EVENT,
                        run_times=[first_due_amount_event, second_due_amount_event],
                        plan_id=DEFAULT_PLAN_ID,
                        count=2,
                    ),
                    ExpectedSchedule(
                        event_id=line_of_credit_supervisor.overdue.CHECK_OVERDUE_EVENT,
                        run_times=[first_overdue_event],
                        plan_id=DEFAULT_PLAN_ID,
                        count=1,
                    ),
                    ExpectedSchedule(
                        event_id=line_of_credit_supervisor.delinquency.CHECK_DELINQUENCY_EVENT,
                        run_times=[first_delinquency_event],
                        plan_id=DEFAULT_PLAN_ID,
                        count=1,
                    ),
                ],
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                drawdown_loan_instances=2,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_due_amount_calculation_excludes_loans_less_than_month_old(self):
        due_amount_calc_day = 5
        start = test_parameters.default_simulation_start_date
        due_amount_calc_1 = datetime(
            year=2020, month=2, day=due_amount_calc_day, second=2, tzinfo=ZoneInfo("UTC")
        )
        # 2 weeks before due amount calc
        second_loan_opening = datetime(year=2020, month=1, day=22, second=2, tzinfo=ZoneInfo("UTC"))
        # 5 days after first due amount calc
        third_loan_opening = due_amount_calc_1 + relativedelta(days=5)
        due_amount_calc_2 = due_amount_calc_1 + relativedelta(months=1)
        end = datetime(year=2020, month=3, day=7, tzinfo=ZoneInfo("UTC"))

        loan_instance_params = {
            **test_parameters.drawdown_loan_instance_params,
            drawdown_loan.disbursement.PARAM_PRINCIPAL: "3000",
            drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.031",
        }
        loc_template_params = {
            **test_parameters.loc_template_params,
            line_of_credit.maximum_loan_principal.PARAM_MAXIMUM_LOAN_PRINCIPAL: "3000",
        }
        loc_instance_params = {
            **test_parameters.loc_instance_params,
            line_of_credit.credit_limit.PARAM_CREDIT_LIMIT: "9000",
        }

        sub_tests = [
            get_mimic_loan_creation_subtest(start=start, amount="3000"),
            SubTest(
                description="Open another loan within a month of due amount calculation date",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="3000",
                        event_datetime=second_loan_opening - relativedelta(seconds=1),
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                    ),
                    create_account_instruction(
                        timestamp=second_loan_opening,
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1",
                        product_id=self.DEFAULT_SUPERVISEE_VERSION_IDS["drawdown_loan"],
                        instance_param_vals=loan_instance_params,
                    ),
                    create_account_plan_assoc_instruction(
                        timestamp=second_loan_opening,
                        assoc_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1 assoc",
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1",
                        plan_id=DEFAULT_PLAN_ID,
                    ),
                ],
            ),
            SubTest(
                description="Check Principal is disbursed for loan opened later",
                expected_balances_at_ts={
                    second_loan_opening: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("3000")),
                            (dimensions.EMI, Decimal("254.22")),
                        ]
                    },
                },
            ),
            SubTest(
                description="Check Accrued Interest is correct before due amount calc",
                expected_balances_at_ts={
                    due_amount_calc_1
                    - relativedelta(microseconds=1): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("3000")),
                            # Accrue from 2020-1-1 to 2020-2-5 at 3.1% on $3000 (i.e. 35 days)
                            # 4 accruals not in EMI from 2020-1-1 to 2020-1-4
                            # 4* round(3000 * 0.031/365, 5) = 1.01916
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("1.01916")),
                            # 31 accruals included in EMI from 2020-1-5 to 2020-1-5
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("7.89849")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("3000")),
                            # Accrue from 2020-1-22 to 2020-2-5 at 3.1% on $3000 (i.e. 14 days)
                            # so 14 * round(3000 * 0.031 / 365, 5)
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("3.56706")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check Due Amounts for first period",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Due amounts exceed EMI becase of 4 extra accruals
                            # 4 * round(3000 * 0.031 / 365 ,5) = 1.02
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("3000")),
                            # All due amounts are 0 as loan is < 1 month old and not considered
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("3.56706")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Open a third loan after the first due amount calculation date",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="3000",
                        event_datetime=third_loan_opening - relativedelta(seconds=1),
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                    ),
                    create_account_instruction(
                        timestamp=third_loan_opening,
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_2",
                        product_id=self.DEFAULT_SUPERVISEE_VERSION_IDS["drawdown_loan"],
                        instance_param_vals=loan_instance_params,
                    ),
                    create_account_plan_assoc_instruction(
                        timestamp=third_loan_opening,
                        assoc_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_2 assoc",
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_2",
                        plan_id=DEFAULT_PLAN_ID,
                    ),
                ],
            ),
            SubTest(
                description="Check Principal is disbursed for third loan",
                expected_balances_at_ts={
                    third_loan_opening: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_2": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("3000")),
                            (dimensions.EMI, Decimal("254.22")),
                        ]
                    },
                },
            ),
            SubTest(
                description="Check Accrued Interest is correct for third loan",
                expected_balances_at_ts={
                    third_loan_opening
                    + relativedelta(days=1): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_2": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("3000")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0.25479")),
                        ],
                    },
                },
            ),
            # This subtest validates that there's no extra interest in the second period
            # for the first loan, and extra interest for the second loan
            SubTest(
                description="Check Due Amounts for second period",
                expected_balances_at_ts={
                    due_amount_calc_2: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2506.24")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Interest due is 6.78 = 29 * round (2753.68 * 0.031 / 365, 5)
                            (dimensions.INTEREST_DUE, Decimal("6.78")),
                            (dimensions.PRINCIPAL_DUE, Decimal("247.44")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.17")),
                            # (INTEREST_DUE-NON_EMI_ACCRUED_INTEREST) + PRINCIPAL_DUE = EMI
                            # (10.96-3.57) + 246.83 = 254.22
                            (dimensions.EMI, Decimal("254.22")),
                            # Due amounts exceed EMI because of 14 extra accruals
                            # 14 * round(3000 * 0.031 / 365 ,5) = 3.57
                            (dimensions.INTEREST_DUE, Decimal("10.96")),
                            # Due / overdue principal is different for each loan because loan 1 is
                            # on its second due event, and loan 2 is on its first.
                            (dimensions.PRINCIPAL_DUE, Decimal("246.83")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_2": [
                            # Nothing due yet, and only non EMI interest has been accrued since
                            # there is a whole month before the next due event
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("3000")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("6.11496")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check accrual after second due calculation event for third loan",
                expected_balances_at_ts={
                    due_amount_calc_2
                    + relativedelta(days=1): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_2": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("3000")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # interest now starts accruing in the regular address
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.25479")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("6.11496")),
                        ],
                    },
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loc_instance_params=loc_instance_params,
                loc_template_params=loc_template_params,
                drawdown_loan_instance_params=loan_instance_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_overdue_balances_incur_correct_penalty_fees_with_base_interest_rate_included(self):
        start = test_parameters.default_simulation_start_date
        first_due_amount_event = datetime(
            year=2020, month=2, day=5, hour=0, minute=0, second=2, tzinfo=ZoneInfo("UTC")
        )
        first_overdue_event = first_due_amount_event + relativedelta(days=7)
        before_first_overdue_event = first_overdue_event - relativedelta(seconds=1)
        one_day_after_overdue_event = first_overdue_event + relativedelta(days=1)
        end = one_day_after_overdue_event

        sub_tests = [
            get_mimic_loan_creation_subtest(start=start, amount="1000", drawdown_loan_instances=2),
            SubTest(
                description="Check balances before the first overdue event",
                expected_balances_at_ts={
                    before_first_overdue_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, Decimal("77.55")),
                            (dimensions.INTEREST_DUE, Decimal("14.29")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, Decimal("77.55")),
                            (dimensions.INTEREST_DUE, Decimal("14.29")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.TOTAL_INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.TOTAL_PRINCIPAL_DUE, Decimal("155.10")),
                            (dimensions.TOTAL_INTEREST_DUE, Decimal("28.58")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.TOTAL_PENALTIES, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check balances after the first overdue event",
                expected_balances_at_ts={
                    first_overdue_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("77.55")),
                            (dimensions.INTEREST_OVERDUE, Decimal("14.29")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("77.55")),
                            (dimensions.INTEREST_OVERDUE, Decimal("14.29")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.TOTAL_PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.TOTAL_INTEREST_DUE, Decimal("0")),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, Decimal("155.10")),
                            (dimensions.TOTAL_INTEREST_OVERDUE, Decimal("28.58")),
                            (dimensions.PENALTIES, Decimal("25")),
                            (dimensions.TOTAL_PENALTIES, Decimal("0")),
                        ],
                        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("25"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Check balances one day after the overdue event",
                expected_balances_at_ts={
                    one_day_after_overdue_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("77.55")),
                            (dimensions.INTEREST_OVERDUE, Decimal("14.29")),
                            # penalty interest rate of 0.05 includes base interest rate of 0.149
                            # so ((0.05 + 0.149) / 365) * (77.55 + 14.29) = 0.05007
                            (dimensions.PENALTIES, Decimal("0.05")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("77.55")),
                            (dimensions.INTEREST_OVERDUE, Decimal("14.29")),
                            (dimensions.PENALTIES, Decimal("0.05")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.TOTAL_PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.TOTAL_INTEREST_DUE, Decimal("0")),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, Decimal("155.10")),
                            (dimensions.TOTAL_INTEREST_OVERDUE, Decimal("28.58")),
                            (dimensions.PENALTIES, Decimal("25")),
                            (dimensions.TOTAL_PENALTIES, Decimal("0.1")),
                        ],
                        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("25"))
                        ],
                    },
                },
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                drawdown_loan_instances=2,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_overdue_balances_incur_correct_penalty_fees_without_base_interest_rate(self):
        start = test_parameters.default_simulation_start_date
        first_due_amount_event = datetime(
            year=2020, month=2, day=5, hour=0, minute=0, second=2, tzinfo=ZoneInfo("UTC")
        )
        first_overdue_event = first_due_amount_event + relativedelta(days=7)
        before_first_overdue_event = first_overdue_event - relativedelta(seconds=1)
        one_day_after_overdue_event = first_overdue_event + relativedelta(days=1)
        end = one_day_after_overdue_event

        drawdown_loan_template_params = test_parameters.drawdown_loan_template_params.copy()
        drawdown_loan_template_params.update(
            {drawdown_loan.PARAM_INCLUDE_BASE_RATE_IN_PENALTY_RATE: "False"}
        )

        sub_tests = [
            get_mimic_loan_creation_subtest(start=start, amount="1000", drawdown_loan_instances=2),
            SubTest(
                description="Check balances before the first overdue event",
                expected_balances_at_ts={
                    before_first_overdue_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, Decimal("77.55")),
                            (dimensions.INTEREST_DUE, Decimal("14.29")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, Decimal("77.55")),
                            (dimensions.INTEREST_DUE, Decimal("14.29")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.TOTAL_INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.TOTAL_PRINCIPAL_DUE, Decimal("155.10")),
                            (dimensions.TOTAL_INTEREST_DUE, Decimal("28.58")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.TOTAL_PENALTIES, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check balances after the first overdue event",
                expected_balances_at_ts={
                    first_overdue_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("77.55")),
                            (dimensions.INTEREST_OVERDUE, Decimal("14.29")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("77.55")),
                            (dimensions.INTEREST_OVERDUE, Decimal("14.29")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.TOTAL_PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.TOTAL_INTEREST_DUE, Decimal("0")),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, Decimal("155.10")),
                            (dimensions.TOTAL_INTEREST_OVERDUE, Decimal("28.58")),
                            (dimensions.PENALTIES, Decimal("25")),
                            (dimensions.TOTAL_PENALTIES, Decimal("0")),
                        ],
                        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("25"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Check balances one day after the overdue event",
                expected_balances_at_ts={
                    one_day_after_overdue_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("77.55")),
                            (dimensions.INTEREST_OVERDUE, Decimal("14.29")),
                            # penalty interest rate of 0.05
                            # so (0.05 / 365) * (77.55 + 14.29) = 0.01258
                            (dimensions.PENALTIES, Decimal("0.01")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("77.55")),
                            (dimensions.INTEREST_OVERDUE, Decimal("14.29")),
                            (dimensions.PENALTIES, Decimal("0.01")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.TOTAL_PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.TOTAL_INTEREST_DUE, Decimal("0")),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, Decimal("155.10")),
                            (dimensions.TOTAL_INTEREST_OVERDUE, Decimal("28.58")),
                            (dimensions.PENALTIES, Decimal("25")),
                            (dimensions.TOTAL_PENALTIES, Decimal("0.02")),
                        ],
                        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("25"))
                        ],
                    },
                },
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                drawdown_loan_template_params=drawdown_loan_template_params,
                drawdown_loan_instances=2,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_overdue_schedules_correct_day_1_day_repayment_period(self):
        start = test_parameters.default_simulation_start_date
        drawdown_loan_instances = 2
        due_amount_calc_day = 5
        due_check_date_1 = datetime(2020, 2, 5, 0, 0, 2, tzinfo=ZoneInfo("UTC"))
        due_check_date_2 = datetime(2020, 3, 5, 0, 0, 2, tzinfo=ZoneInfo("UTC"))
        overdue_check_date_1 = datetime(2020, 2, 6, 0, 0, 2, tzinfo=ZoneInfo("UTC"))
        overdue_check_date_2 = datetime(2020, 3, 6, 0, 0, 2, tzinfo=ZoneInfo("UTC"))
        delinquency_check_1 = datetime(2020, 2, 11, 0, 1, 0, tzinfo=ZoneInfo("UTC"))
        delinquency_check_2 = datetime(2020, 3, 11, 0, 1, 0, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2020, month=4, day=1, hour=12, minute=1, tzinfo=ZoneInfo("UTC"))

        loan_instance_params = {
            **test_parameters.drawdown_loan_instance_params,
            drawdown_loan.disbursement.PARAM_PRINCIPAL: "3000",
            drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.031",
        }
        loc_template_params = {
            **test_parameters.loc_template_params,
            line_of_credit.overdue.PARAM_REPAYMENT_PERIOD: "1",
            line_of_credit.delinquency.PARAM_GRACE_PERIOD: "5",
            line_of_credit.maximum_loan_principal.PARAM_MAXIMUM_LOAN_PRINCIPAL: "3000",
        }
        loc_instance_params = {
            **test_parameters.loc_instance_params,
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: str(
                due_amount_calc_day
            ),
            line_of_credit.credit_limit.PARAM_CREDIT_LIMIT: "9000",
        }

        sub_tests = [
            get_mimic_loan_creation_subtest(
                start=start, amount="3000", drawdown_loan_instances=drawdown_loan_instances
            ),
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    start
                    + relativedelta(microseconds=1000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Repayment notification sent on first due amount schedule",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_check_date_1,
                        notification_type=REPAYMENT_DUE_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                            "repayment_amount": "510.48",
                            "overdue_date": str(overdue_check_date_1.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Fee is charged and notification sent on first overdue schedule",
                expected_balances_at_ts={
                    overdue_check_date_1: {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.PENALTIES, "25"),
                        ],
                        f"{accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT}": [
                            (dimensions.DEFAULT, "25"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_check_date_1,
                        notification_type=REPAYMENT_OVERDUE_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                            "overdue_principal": "492.64",
                            "overdue_interest": "17.84",
                            "late_repayment_fee": "25",
                            "overdue_date": str(overdue_check_date_1.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                    ExpectedContractNotification(
                        timestamp=delinquency_check_1,
                        notification_type=DELINQUENT_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Repayment notification sent on second due amount schedule",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_check_date_2,
                        notification_type=REPAYMENT_DUE_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                            "repayment_amount": "508.44",
                            "overdue_date": str(overdue_check_date_2.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Fee is charged and notification sent on second overdue schedule",
                expected_balances_at_ts={
                    overdue_check_date_2: {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.PENALTIES, "50"),
                        ],
                        f"{accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT}": [
                            (dimensions.DEFAULT, "50"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_check_date_2,
                        notification_type=REPAYMENT_OVERDUE_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                            "overdue_principal": "494.88",
                            "overdue_interest": "13.56",
                            "late_repayment_fee": "25",
                            "overdue_date": str(overdue_check_date_2.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                    ExpectedContractNotification(
                        timestamp=delinquency_check_2,
                        notification_type=DELINQUENT_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loc_instance_params=loc_instance_params,
                loc_template_params=loc_template_params,
                drawdown_loan_instance_params=loan_instance_params,
                drawdown_loan_instances=drawdown_loan_instances,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_overdue_schedules_correct_day_27_day_repayment_period(self):
        start = test_parameters.default_simulation_start_date
        drawdown_loan_instances = 2
        due_amount_calc_day = 5

        due_check_date_1 = datetime(2020, 2, 5, 0, 0, 2, tzinfo=ZoneInfo("UTC"))
        due_check_date_2 = datetime(2020, 3, 5, 0, 0, 2, tzinfo=ZoneInfo("UTC"))
        overdue_check_date_1 = datetime(2020, 3, 3, 0, 0, 2, tzinfo=ZoneInfo("UTC"))
        overdue_check_date_2 = datetime(2020, 4, 1, 0, 0, 2, tzinfo=ZoneInfo("UTC"))
        delinquency_check_1 = datetime(2020, 3, 8, 0, 1, 0, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2020, month=4, day=1, hour=12, minute=1, tzinfo=ZoneInfo("UTC"))

        loan_instance_params = {
            **test_parameters.drawdown_loan_instance_params,
            drawdown_loan.disbursement.PARAM_PRINCIPAL: "3000",
            drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.031",
        }
        loc_template_params = {
            **test_parameters.loc_template_params,
            line_of_credit.overdue.PARAM_REPAYMENT_PERIOD: "27",
            line_of_credit.delinquency.PARAM_GRACE_PERIOD: "5",
            line_of_credit.maximum_loan_principal.PARAM_MAXIMUM_LOAN_PRINCIPAL: "3000",
        }
        loc_instance_params = {
            **test_parameters.loc_instance_params,
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: str(
                due_amount_calc_day
            ),
            line_of_credit.credit_limit.PARAM_CREDIT_LIMIT: "9000",
        }

        sub_tests = [
            get_mimic_loan_creation_subtest(
                start=start, amount="3000", drawdown_loan_instances=drawdown_loan_instances
            ),
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    start
                    + relativedelta(microseconds=1000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Repayment notification sent on first due amount schedule",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_check_date_1,
                        notification_type=REPAYMENT_DUE_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                            "repayment_amount": "510.48",
                            "overdue_date": str(overdue_check_date_1.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Fee is charged and notification sent on first overdue schedule",
                expected_balances_at_ts={
                    overdue_check_date_1: {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.PENALTIES, "25"),
                        ],
                        f"{accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT}": [
                            (dimensions.DEFAULT, "25"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_check_date_1,
                        notification_type=REPAYMENT_OVERDUE_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                            "overdue_principal": "492.64",
                            "overdue_interest": "17.84",
                            "late_repayment_fee": "25",
                            "overdue_date": str(overdue_check_date_1.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                    ExpectedContractNotification(
                        timestamp=delinquency_check_1,
                        notification_type=DELINQUENT_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Repayment notification sent on second due amount schedule",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_check_date_2,
                        notification_type=REPAYMENT_DUE_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                            "repayment_amount": "508.44",
                            "overdue_date": str(overdue_check_date_2.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Fee is charged and notification sent on second overdue schedule",
                expected_balances_at_ts={
                    overdue_check_date_2: {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.PENALTIES, "50"),
                        ],
                        f"{accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT}": [
                            (dimensions.DEFAULT, "50"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_check_date_2,
                        notification_type=REPAYMENT_OVERDUE_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                            "overdue_principal": "494.88",
                            "overdue_interest": "13.56",
                            "late_repayment_fee": "25",
                            "overdue_date": str(overdue_check_date_2.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loc_instance_params=loc_instance_params,
                loc_template_params=loc_template_params,
                drawdown_loan_instance_params=loan_instance_params,
                drawdown_loan_instances=drawdown_loan_instances,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)
