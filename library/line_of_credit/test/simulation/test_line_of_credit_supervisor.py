# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone
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

# inception sdk
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
    create_flag_definition_event,
    create_flag_event,
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_outbound_hard_settlement_instruction,
)

ACCRUAL_EVENT = line_of_credit_supervisor.interest_accrual_supervisor.ACCRUAL_EVENT


class LineOfCreditSupervisorTest(LineOfCreditSupervisorCommonTest):
    def test_initial_disbursement(self):
        start = test_parameters.default_simulation_start_date
        after_initial_disbursement = start + relativedelta(seconds=1)
        end = after_initial_disbursement
        sub_tests = [
            SubTest(
                description="disbursement correctly aggregates to line of credit supervisee",
                expected_balances_at_ts={
                    after_initial_disbursement: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.EMI, "90.21"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.EMI, "90.21"),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, "2000")],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.TOTAL_PRINCIPAL, "2000"),
                            (dimensions.TOTAL_EMI, "180.42"),
                        ],
                    },
                },
            ),
            SubTest(
                description="check derived parameters after disbursement",
                expected_derived_parameters=[
                    # since there are no extra early repayment fees, the early repayment amount is
                    # the same as the maximum overpayment including the associated overpayment fee.
                    # early_repayment_amount = total outstanding amount + max overpayment fee,
                    # where the max overpayment fee is:
                    # (remaining principal * overpayment fee rate) / (1 - overpayment fee rate)
                    # per_loan_early_repayment_amount: 1000 + 1000 * 0.05 / (1-0.05) = 1052.63
                    # total_early_repayment_amount: 1052.63 * 2 = 2105.26
                    ExpectedDerivedParameter(
                        timestamp=after_initial_disbursement,
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0",
                        name="per_loan_early_repayment_amount",
                        value="1052.63",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_initial_disbursement,
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1",
                        name="per_loan_early_repayment_amount",
                        value="1052.63",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_initial_disbursement,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_early_repayment_amount",
                        value="2105.26",
                    ),
                    # 2 * EMI
                    ExpectedDerivedParameter(
                        timestamp=after_initial_disbursement,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_monthly_repayment",
                        value="180.42",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_initial_disbursement,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name=line_of_credit.PARAM_TOTAL_OUTSTANDING_DUE_AMOUNT,
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_initial_disbursement,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name=line_of_credit.PARAM_TOTAL_ARREARS_AMOUNT,
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_initial_disbursement,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="next_repayment_date",
                        value="2020-02-05",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_initial_disbursement,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name=line_of_credit.PARAM_TOTAL_ORIGINAL_PRINCIPAL,
                        value="2000.00",
                    ),
                ],
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(drawdown_loan_instances=2),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_cannot_exceed_max_number_of_outstanding_loans(self):
        start = test_parameters.default_simulation_start_date
        end = start + relativedelta(hours=2)
        loc_template_params = test_parameters.loc_template_params.copy()
        loc_template_params[
            line_of_credit.maximum_outstanding_loans.PARAM_MAXIMUM_NUMBER_OF_OUTSTANDING_LOANS
        ] = "5"
        drawdown_loan_instances = 5

        sub_tests = [
            SubTest(
                description="Drawdown when number of loans exceeded",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(hours=1),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Cannot create new loan due to outstanding loan limit"
                        " being exceeded. Current number of loans: 5, maximum loan limit: 5.",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                    )
                ],
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                drawdown_loan_instances=drawdown_loan_instances,
                loc_template_params=loc_template_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_outstanding_principal_credit_limit(self):
        due_amount_calc_day = 5
        start = test_parameters.default_simulation_start_date
        due_amount_calc_1 = start.replace(month=2, day=due_amount_calc_day, second=2)
        end = due_amount_calc_1 + relativedelta(days=1)

        loc_template_params = {
            **test_parameters.loc_template_params,
            line_of_credit.maximum_loan_principal.PARAM_MAXIMUM_LOAN_PRINCIPAL: "3000",
            line_of_credit.minimum_loan_principal.PARAM_MINIMUM_LOAN_PRINCIPAL: "500",
        }

        loc_instance_params = {
            **test_parameters.loc_instance_params,
            line_of_credit.credit_limit.PARAM_CREDIT_LIMIT: "7000",
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: str(
                due_amount_calc_day
            ),
        }

        loan_instance_params = {
            **test_parameters.drawdown_loan_instance_params,
            drawdown_loan.disbursement.PARAM_PRINCIPAL: "3000",
            drawdown_loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "3",
            drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.031",
        }

        drawdown_loan_instances = 2

        sub_tests = [
            get_mimic_loan_creation_subtest(
                start=start, amount="3000", drawdown_loan_instances=drawdown_loan_instances
            ),
            SubTest(
                description="Drawdown over remaining credit limit rejected",
                # remaining credit limit is 1000
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(hours=1),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Incoming posting of 2000 exceeds"
                        + " available credit limit of 1000.00",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                    )
                ],
            ),
            SubTest(
                description="Drawdown below remaining credit limit accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=2): {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("6500")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Drawdown above remaining credit limit rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="501",
                        event_datetime=start + relativedelta(hours=3),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(hours=3),
                        rejection_type="AgainstTermsAndConditions",
                        # note this reflects the change in limit despite the 500GBP loan
                        # not yet being associated
                        rejection_reason="Incoming posting of 501 exceeds"
                        + " available credit limit of 500.00",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                    )
                ],
            ),
            SubTest(
                description="Pay some due principal to reduce outstanding principal",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="2012.38",
                        event_datetime=due_amount_calc_1 + relativedelta(hours=4),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(seconds=1): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("997.27")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("997.27")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("6500")),
                        ],
                    },
                    due_amount_calc_1
                    + relativedelta(hours=4): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("4487.62")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Large drawdown above updated limit rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=due_amount_calc_1 + relativedelta(hours=5),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=due_amount_calc_1 + relativedelta(hours=5),
                        rejection_type="AgainstTermsAndConditions",
                        # note this reflects the change in limit despite the 500GBP loan
                        # not yet being associated. The remaining limit is
                        # 7000 - 6500 (original principals) + 2*997.27 (principal repayments)
                        rejection_reason="Incoming posting of 3000 exceeds"
                        + " available credit limit of 2494.54",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                    )
                ],
            ),
            SubTest(
                description="Smaller drawdown accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=due_amount_calc_1 + relativedelta(hours=7),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=7): {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("5487.62")),
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
                drawdown_loan_instances=drawdown_loan_instances,
                loc_instance_params=loc_instance_params,
                loc_template_params=loc_template_params,
                drawdown_loan_instance_params=loan_instance_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_original_principal_credit_limit(self):
        due_amount_calc_day = 5
        start = test_parameters.default_simulation_start_date
        due_amount_calc_1 = start.replace(month=2, day=due_amount_calc_day, second=2)
        end = due_amount_calc_1 + relativedelta(days=1)

        loc_template_params = {
            **test_parameters.loc_template_params,
            line_of_credit.maximum_loan_principal.PARAM_MAXIMUM_LOAN_PRINCIPAL: "3000",
            line_of_credit.minimum_loan_principal.PARAM_MINIMUM_LOAN_PRINCIPAL: "500",
            line_of_credit.credit_limit.PARAM_CREDIT_LIMIT_APPLICABLE_PRINCIPAL: (
                line_of_credit.credit_limit.CREDIT_LIMIT_ORIGINAL
            ),
        }

        loc_instance_params = {
            **test_parameters.loc_instance_params,
            line_of_credit.credit_limit.PARAM_CREDIT_LIMIT: "7000",
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: str(
                due_amount_calc_day
            ),
        }

        loan_instance_params = {
            **test_parameters.drawdown_loan_instance_params,
            drawdown_loan.disbursement.PARAM_PRINCIPAL: "3000",
            drawdown_loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "3",
            drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.031",
        }

        drawdown_loan_instances = 2

        sub_tests = [
            get_mimic_loan_creation_subtest(
                start=start, amount="3000", drawdown_loan_instances=drawdown_loan_instances
            ),
            SubTest(
                description="Drawdown over remaining credit limit rejected",
                # remaining credit limit is 1000
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(hours=1),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Incoming posting of 2000 exceeds"
                        + " available credit limit of 1000.00",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                    )
                ],
            ),
            SubTest(
                description="Drawdown below remaining credit limit accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=2): {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("6500")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Drawdown above remaining credit limit rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="501",
                        event_datetime=start + relativedelta(hours=3),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(hours=3),
                        rejection_type="AgainstTermsAndConditions",
                        # note this reflects the change in limit despite the 500GBP loan
                        # not yet being associated
                        rejection_reason="Incoming posting of 501 exceeds"
                        + " available credit limit of 500.00",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                    )
                ],
            ),
            SubTest(
                description="Pay some due principal to reduce outstanding principal",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="2012.38",
                        event_datetime=due_amount_calc_1 + relativedelta(hours=4),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(seconds=1): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("997.27")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("997.27")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("6500")),
                        ],
                    },
                    due_amount_calc_1
                    + relativedelta(hours=4): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("4487.62")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Original principal limit respected still",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="501",
                        event_datetime=due_amount_calc_1 + relativedelta(hours=5),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=due_amount_calc_1 + relativedelta(hours=5),
                        rejection_type="AgainstTermsAndConditions",
                        # 7000 - 6500 (original principals) + 2*997.27 (principal repayments)
                        # Based on outstanding principal, credit limit = 2494.54
                        # Based on original principal, credit limit = 500
                        rejection_reason="Incoming posting of 501 exceeds"
                        + " available credit limit of 500.00",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                    )
                ],
            ),
            SubTest(
                description="Smaller drawdown accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=due_amount_calc_1 + relativedelta(hours=7),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=7): {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("4987.62")),
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
                drawdown_loan_instances=drawdown_loan_instances,
                loc_instance_params=loc_instance_params,
                loc_template_params=loc_template_params,
                drawdown_loan_instance_params=loan_instance_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_blocking_daily_accrual(self):
        start = test_parameters.default_simulation_start_date
        after_first_accrual = start + relativedelta(days=1, hours=2)
        second_accrual = start + relativedelta(days=2)
        after_second_accrual = start + relativedelta(days=2, hours=2)
        after_third_accrual = start + relativedelta(days=3, hours=2)

        loc_template_params = test_parameters.loc_template_params

        sub_tests = [
            SubTest(
                description="Create flag definition",
                events=[create_flag_definition_event(start, "REPAYMENT_HOLIDAY")],
            ),
            SubTest(
                description="check interest is accrued without the flag applied",
                expected_balances_at_ts={
                    after_first_accrual: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.EMI, "90.21"),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0.40822")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Apply flag",
                events=[
                    create_flag_event(
                        timestamp=after_first_accrual,
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        expiry_timestamp=after_second_accrual,
                    )
                ],
            ),
            SubTest(
                description="Check interest is no longer accrued",
                expected_balances_at_ts={
                    after_second_accrual: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.EMI, "90.21"),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0.40822")),
                        ],
                    },
                },
                # confirm schedule runs even though balance is not changed
                expected_schedules=[
                    ExpectedSchedule(
                        event_id=ACCRUAL_EVENT,
                        run_times=[second_accrual],
                        plan_id=DEFAULT_PLAN_ID,
                        count=3,
                    ),
                ],
            ),
            SubTest(
                description="Interest accrued again after flag expires",
                expected_balances_at_ts={
                    after_third_accrual: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.EMI, "90.21"),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0.81644")),
                        ],
                    },
                },
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=after_third_accrual,
            supervisor_config=self._get_default_supervisor_config(
                loc_template_params=loc_template_params,
                drawdown_loan_instances=1,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_credit_limit_cannot_go_below_total_outstanding_debt_across_all_loans(self):
        start = test_parameters.default_simulation_start_date
        second_due_amount_event = datetime(
            year=2020, month=3, day=5, hour=0, minute=0, second=2, tzinfo=timezone.utc
        )
        end = second_due_amount_event + relativedelta(minutes=1)

        sub_tests = [
            get_mimic_loan_creation_subtest(start=start, amount="1000", drawdown_loan_instances=2),
            SubTest(
                description="Check due amounts at second due event time",
                expected_balances_at_ts={
                    second_due_amount_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL, "843.16"),
                            (dimensions.PRINCIPAL_DUE, "79.29"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "77.55"),
                            (dimensions.INTEREST_OVERDUE, "14.29"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL, "843.16"),
                            (dimensions.PRINCIPAL_DUE, "79.29"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "77.55"),
                            (dimensions.INTEREST_OVERDUE, "14.29"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "2000"),
                            (dimensions.TOTAL_PRINCIPAL, "1686.32"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "158.58"),
                            (dimensions.TOTAL_INTEREST_DUE, "21.84"),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, "155.1"),
                            (dimensions.TOTAL_INTEREST_OVERDUE, "28.58"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Pay back part of the loans",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="100",
                        event_datetime=second_due_amount_event + relativedelta(seconds=1),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    second_due_amount_event
                    + relativedelta(seconds=1): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL, "843.16"),
                            (dimensions.PRINCIPAL_DUE, "79.29"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "14.29"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL, "843.16"),
                            (dimensions.PRINCIPAL_DUE, "79.29"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "55.1"),
                            (dimensions.INTEREST_OVERDUE, "14.29"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "1900"),
                            (dimensions.TOTAL_PRINCIPAL, "1686.32"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "158.58"),
                            (dimensions.TOTAL_INTEREST_DUE, "21.84"),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, "55.1"),
                            (dimensions.TOTAL_INTEREST_OVERDUE, "28.58"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Reject changing the credit limit below the "
                "total outstanding amount of 1900",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=second_due_amount_event + relativedelta(seconds=2),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        credit_limit="1899.99",
                    ),
                ],
                expected_parameter_change_rejections=[
                    ExpectedRejection(
                        timestamp=second_due_amount_event + relativedelta(seconds=2),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Cannot set proposed credit limit 1899.99 "
                        "to a value below the total outstanding debt of 1900",
                    )
                ],
            ),
            SubTest(
                description="Change credit limit to outstanding debt amount "
                "+ 50 (the minimum drawdown loan amount)",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=second_due_amount_event + relativedelta(seconds=3),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        credit_limit="1950",
                    ),
                ],
            ),
            SubTest(
                description="Ensure no loans can be opened above the new credit limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50.01",
                        event_datetime=second_due_amount_event + relativedelta(seconds=4),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=second_due_amount_event + relativedelta(seconds=4),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Incoming posting of 50.01 exceeds available credit limit "
                        "of 50",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                    )
                ],
            ),
        ]

        self.run_test_scenario(
            SimulationTestScenario(
                sub_tests=sub_tests,
                start=start,
                end=end,
                supervisor_config=self._get_default_supervisor_config(
                    drawdown_loan_instances=2,
                ),
                internal_accounts=accounts.default_internal_accounts,
            )
        )

    def test_blocking_during_repayment_holiday(self):
        due_amount_calc_day = 5
        # repayment and grace periods match defaults
        repayment_period = 5
        grace_period = 5
        start = test_parameters.default_simulation_start_date
        # due amount dates
        due_amount_calc_1 = datetime(
            year=2020, month=2, day=due_amount_calc_day, second=2, tzinfo=ZoneInfo("UTC")
        )
        due_amount_calc_2 = due_amount_calc_1 + relativedelta(months=1)
        due_amount_calc_3 = due_amount_calc_2 + relativedelta(months=1)

        # check overdue dates
        check_overdue_1 = due_amount_calc_1 + relativedelta(days=repayment_period, second=3)
        check_overdue_2 = due_amount_calc_2 + relativedelta(days=repayment_period, second=3)
        check_overdue_3 = due_amount_calc_3 + relativedelta(days=repayment_period, second=3)

        # check delinquency dates
        check_delinquency_1 = check_overdue_1 + relativedelta(days=grace_period, minute=1, second=0)
        check_delinquency_2 = check_overdue_2 + relativedelta(days=grace_period, minute=1, second=0)
        check_delinquency_3 = check_overdue_3 + relativedelta(days=grace_period, minute=1, second=0)

        end = check_delinquency_3

        loc_instance_params = {
            **test_parameters.loc_instance_params,
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: str(
                due_amount_calc_day
            ),
        }

        loc_template_params = {
            **test_parameters.loc_template_params,
            line_of_credit.overdue.PARAM_REPAYMENT_PERIOD: str(repayment_period),
            line_of_credit.delinquency.PARAM_GRACE_PERIOD: str(grace_period),
        }

        loan_instance_params = {
            **test_parameters.drawdown_loan_instance_params,
            drawdown_loan.disbursement.PARAM_PRINCIPAL: "3000",
            drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.031",
        }

        sub_tests = [
            SubTest(
                description="Create Flag definition",
                events=[create_flag_definition_event(start, test_parameters.REPAYMENT_HOLIDAY)],
            ),
            SubTest(
                description="Check due amounts for first period with extra interest",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Due amounts exceed EMI because of 4 extra accruals
                            # 4 * round(3000 * 0.031 / 365 ,5) = 1.02
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check overdue amounts for first period",
                expected_balances_at_ts={
                    check_overdue_1: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Existing due amounts have been moved to overdue, but no new due
                            # amounts are added
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            # accrual is at 00:00:01 and check overdue at 00:00:03
                            # so 5 days of accruals since due amount calculation
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("1.16935")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("1.16935")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check delinquency balance after first period",
                expected_balances_at_ts={
                    check_delinquency_1: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Existing due amounts have been moved to overdue, but no new due
                            # amounts are added
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            # accrual is at 00:00:01 and check delinquency at 00:00:02
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.3387")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.3387")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=check_delinquency_1,
                        notification_type=line_of_credit_supervisor.DELINQUENT_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Apply Flag",
                events=[
                    create_flag_event(
                        timestamp=check_delinquency_1 + relativedelta(minutes=1),
                        flag_definition_id=test_parameters.REPAYMENT_HOLIDAY,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        expiry_timestamp=check_delinquency_2 + relativedelta(minutes=1),
                    )
                ],
            ),
            SubTest(
                description="Check due amounts for second period have not changed due to "
                "repayment holiday, except for due calc event counter",
                expected_balances_at_ts={
                    due_amount_calc_2: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Existing due amounts have been moved to overdue, but no new due
                            # amounts are added
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            # accrual is at 00:00:01 and check delinquency at 00:00:02
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.3387")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("2")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.3387")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("2")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check overdue amounts for second period have not changed due to "
                "repayment holiday",
                expected_balances_at_ts={
                    check_overdue_2: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Existing due amounts have been moved to overdue, but no new due
                            # amounts are added
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            # accrual is at 00:00:01 and check delinquency at 00:00:02
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.3387")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("2")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.3387")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("2")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check delinquency amounts at second period have not changed due to "
                "repayment holiday",
                expected_balances_at_ts={
                    check_delinquency_2: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Existing due amounts have been moved to overdue, but no new due
                            # amounts are added
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            # accrual is at 00:00:01 and check delinquency at 00:00:02
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.3387")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("2")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.3387")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("2")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check due amounts change in third period after repayment holiday "
                "ends and loans are re-amortised",
                expected_balances_at_ts={
                    due_amount_calc_3: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2481.63")),
                            # EMI is reamortised with previous P = 2753.68
                            # N = 10 and R is 0.031/12
                            (dimensions.EMI, Decimal("279.30")),
                            # Repayment holiday is effective 2020/02/15 - 2020/03/15 (31 days)
                            # so accrue 2020/02/05 - 2020/02/15 and 2020/03/15 - 2020/04/05
                            # 7.25 = 31 * round (2753.68 * 0.031 / 365, 5)
                            (dimensions.INTEREST_DUE, Decimal("7.25")),
                            (dimensions.PRINCIPAL_DUE, Decimal("272.05")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("3")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2481.63")),
                            (dimensions.EMI, Decimal("279.30")),
                            (dimensions.INTEREST_DUE, Decimal("7.25")),
                            (dimensions.PRINCIPAL_DUE, Decimal("272.05")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("3")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check overdue amounts change in third period after repayment holiday "
                "ends and loans are re-amortised",
                expected_balances_at_ts={
                    check_overdue_3: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2481.63")),
                            (dimensions.EMI, Decimal("279.30")),
                            # Existing due amounts have been moved to overdue, but no new due
                            # amounts are added
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("16.17")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("518.37")),
                            # accrual is at 00:00:01 and check overdue at 00:00:03
                            # so 5 days of accruals since due amount calculation
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("1.05385")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("3")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2481.63")),
                            (dimensions.EMI, Decimal("279.30")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("16.17")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("518.37")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("1.05385")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("3")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check amounts change at delinquency in third period after repayment"
                " holiday ends and loans are re-amortised",
                expected_balances_at_ts={
                    check_delinquency_3: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2481.63")),
                            (dimensions.EMI, Decimal("279.30")),
                            # Existing due amounts have been moved to overdue, but no new due
                            # amounts are added
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("16.17")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("518.37")),
                            # accrual is at 00:00:01 and check overdue at 00:00:03
                            # so 10 days of accruals since due amount calculation
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.1077")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("3")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2481.63")),
                            (dimensions.EMI, Decimal("279.30")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("16.17")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("518.37")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.1077")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("3")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=check_delinquency_3,
                        notification_type=line_of_credit_supervisor.DELINQUENT_NOTIFICATION,
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
                drawdown_loan_instances=2,
                loc_instance_params=loc_instance_params,
                loc_template_params=loc_template_params,
                drawdown_loan_instance_params=loan_instance_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_total_early_repayment_amount_derived_parameter(self):
        start = test_parameters.default_simulation_start_date
        end = start + relativedelta(months=2)

        due_amount_calc_day = 5
        due_amount_calc_1 = datetime(
            year=2020, month=2, day=due_amount_calc_day, second=2, tzinfo=ZoneInfo("UTC")
        )
        repayment_date = due_amount_calc_1 - relativedelta(hours=12)

        loc_instance_params = {
            **test_parameters.loc_instance_params,
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: str(
                due_amount_calc_day
            ),
        }
        loc_template_params = {
            **test_parameters.loc_template_params,
            line_of_credit.overpayment.PARAM_OVERPAYMENT_FEE_RATE: "0",
        }
        loan_instance_params = {
            **test_parameters.drawdown_loan_instance_params,
            drawdown_loan.disbursement.PARAM_PRINCIPAL: "3000",
            drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.031",
        }

        sub_tests = [
            SubTest(
                description="Check amounts the day before first due amount calculation",
                expected_balances_at_ts={
                    due_amount_calc_1
                    - relativedelta(days=1): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("3000")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("7.6437")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("1.01916")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Repay exact principal amount",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=repayment_date,
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_balances_at_ts={
                    repayment_date: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Due amounts exceed EMI because of 4 extra accruals
                            # 4 * round(3000 * 0.031 / 365 ,5) = 1.02
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("7.6437")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("1.01916")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check early repayment amount after principal has been repaid",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=repayment_date,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_early_repayment_amount",
                        value="8.66",
                    ),
                ],
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                drawdown_loan_instances=1,
                loc_template_params=loc_template_params,
                loc_instance_params=loc_instance_params,
                drawdown_loan_instance_params=loan_instance_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)
