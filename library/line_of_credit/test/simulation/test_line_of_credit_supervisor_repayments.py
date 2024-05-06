# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

# library
import library.line_of_credit.constants.accounts as accounts
import library.line_of_credit.constants.dimensions as dimensions
import library.line_of_credit.constants.test_parameters as test_parameters
from library.line_of_credit.test.simulation.test_line_of_credit_supervisor_common import (
    LineOfCreditSupervisorCommonTest,
    get_mimic_loan_creation_subtest,
)

# inception sdk
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    ExpectedDerivedParameter,
    ExpectedRejection,
    SimulationTestScenario,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_inbound_hard_settlement_instruction,
    create_outbound_hard_settlement_instruction,
)


class LineOfCreditSupervisorRepaymentsTest(LineOfCreditSupervisorCommonTest):
    def test_pre_posting_accepts_and_rejects_postings(self):
        start = test_parameters.default_simulation_start_date
        end = start + relativedelta(hours=5)
        sub_tests = [
            SubTest(
                description="Check balances when account opens",
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [(dimensions.DEFAULT, "0")],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, "1000")],
                    },
                },
            ),
            # note that the supervisor is not meant to call the pre posting hook for the
            # drawdown loan accounts and so these next two subtests are here to ensure that the
            # drawdown loan supervisee pre-posting code functions independently of the supervisor,
            # i.e. that the supervisor does not intercept or override the pre-posting code for
            # the drawdown loan contract
            SubTest(
                description="Check posting directly to drawdown loan is rejected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0",
                        amount="250",
                        event_datetime=start + relativedelta(hours=1),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(hours=1),
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0",
                        rejection_type="Custom",
                        rejection_reason="All postings should be made to the Line of Credit "
                        "account",
                    )
                ],
            ),
            SubTest(
                description="Accepts the inbound hard settlement if a force override is added",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0",
                        amount="250",
                        event_datetime=start + relativedelta(hours=2),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={"force_override": "true"},
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=2): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "-250"),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, "750")],
                    },
                },
            ),
            # the following tests ensure the supervisor pre-posting code still throws
            # the line of credit supervisee rejection
            SubTest(
                description="Drawdown that exceeds the maximum loan amount limit is rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1001",
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
                        rejection_reason="Cannot create loan larger than maximum loan amount "
                        "limit of: 1000.",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                    )
                ],
            ),
            SubTest(
                description="Accepts the outbound hard settlement if a force override is added",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1001",
                        event_datetime=start + relativedelta(hours=4),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                        instruction_details={"force_override": "true"},
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=4): {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "1001"),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, "750")],
                        accounts.DEFAULT_INTERNAL_ACCOUNT: [(dimensions.DEFAULT, "1001")],
                    },
                },
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_repayments_get_rejected_and_accepted_correctly(self):
        start = test_parameters.default_simulation_start_date
        end = start + relativedelta(seconds=4)
        sub_tests = [
            get_mimic_loan_creation_subtest(start=start, amount="1000", drawdown_loan_instances=2),
            SubTest(
                description="Reject repayment if it is greater than "
                "the maximum overpayment amount on the line of credit",
                events=[
                    # the maximum overpayment amount is going to be
                    # total outstanding amount + max overpayment fee
                    # where the max overpayment amount is
                    # (remaining principal * overpayment fee rate) / (1 - overpayment fee rate)
                    # so 2000 + 2000 * 0.05 / (1-0.05) = 2105.26
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="2105.27",
                        event_datetime=start + relativedelta(seconds=2),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(seconds=2),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="The repayment amount 2105.27 GBP exceeds the "
                        "total maximum repayment amount of 2105.26 GBP.",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                    )
                ],
            ),
            SubTest(
                description="Accept repayment if it is less than the "
                "the maximum overpayment amount on the line of credit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="100",
                        event_datetime=start + relativedelta(seconds=3),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        # overpayment fee = 100 * 0.05 = 5
                        f"{accounts.LOC_ACCOUNT}_0": [(dimensions.DEFAULT, "1905")],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, "1900")],
                        accounts.OVERPAYMENT_FEE_INCOME_ACCOUNT: [(dimensions.DEFAULT, "5")],
                    },
                },
            ),
            SubTest(
                description="Accept repayment if it is equal to "
                "the maximum overpayment amount on the line of credit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="2005.26",
                        event_datetime=start + relativedelta(seconds=4),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=4): {
                        # overpayment fee = 2005.26 * 0.05 = 100.26
                        f"{accounts.LOC_ACCOUNT}_0": [(dimensions.DEFAULT, "0")],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, "-105.26")],
                        accounts.OVERPAYMENT_FEE_INCOME_ACCOUNT: [(dimensions.DEFAULT, "105.26")],
                    },
                },
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

    def test_repayments_targeted_to_a_loan_get_rejected_and_accepted_correctly(self):
        start = test_parameters.default_simulation_start_date
        end = start + relativedelta(seconds=4)
        sub_tests = [
            get_mimic_loan_creation_subtest(start=start, amount="1000", drawdown_loan_instances=2),
            SubTest(
                description="Reject repayment if it is greater than "
                "the total outstanding amount on the targeted drawdown loan",
                events=[
                    # the maximum overpayment amount is going to be
                    # total outstanding amount + max overpayment fee
                    # where the max overpayment amount is
                    # (remaining principal * overpayment fee rate) / (1 - overpayment fee rate)
                    # so 1000 + 1000 * 0.05 / (1-0.05) = 1052.63
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="1052.64",
                        event_datetime=start + relativedelta(seconds=2),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={
                            "target_account_id": f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0"
                        },
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(seconds=2),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="The repayment amount 1052.64 GBP exceeds the "
                        "total maximum repayment amount of 1052.63 GBP.",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                    )
                ],
            ),
            SubTest(
                description="Accept repayment if it is less than the "
                "the total outstanding amount on the line of credit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="100",
                        event_datetime=start + relativedelta(seconds=3),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={
                            "target_account_id": f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0"
                        },
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        f"{accounts.LOC_ACCOUNT}_0": [(dimensions.DEFAULT, "1905")],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            # overpayment fee = 100 * 0.05 = 5
                            (dimensions.PRINCIPAL, "905"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, "1900")],
                        accounts.OVERPAYMENT_FEE_INCOME_ACCOUNT: [(dimensions.DEFAULT, "5")],
                    },
                },
            ),
            SubTest(
                description="Accept repayment if it is equal to "
                "the total outstanding amount on the targeted drawdown loan",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        # To fully repay outstanding amount (905):
                        # overpayment amount - overpayment fee = 905
                        # 952.63 - (952.63 * 0.05) = 905
                        amount="952.63",
                        event_datetime=start + relativedelta(seconds=4),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={
                            "target_account_id": f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0"
                        },
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=4): {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            # 1905 - 952.63 + 47.63 (overpayment fee)
                            (dimensions.DEFAULT, "1000")
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, "947.37")],
                    },
                },
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

    def test_repayments_targeted_to_an_invalid_loan_are_rejected(self):
        start = test_parameters.default_simulation_start_date
        end = start + relativedelta(seconds=2)
        sub_tests = [
            SubTest(
                description="Check balances when account opens",
                # we need to mimic the creation of the outbound hard settlement
                # instructions used to create the drawdown loans
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="1000",
                        event_datetime=start,
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        f"{accounts.LOC_ACCOUNT}_0": [(dimensions.DEFAULT, "1000")],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, "1000")],
                    },
                },
            ),
            SubTest(
                description="Reject repayment if the target account id does not exist",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="1000.01",
                        event_datetime=start + relativedelta(seconds=2),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={"target_account_id": "invalid account id"},
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(seconds=2),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="The target account id invalid account id does not exist",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                    )
                ],
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_full_repayment_distributed_correctly(self):
        start = test_parameters.default_simulation_start_date
        first_due_amount_event = datetime(
            year=2020, month=2, day=5, hour=0, minute=0, second=2, tzinfo=timezone.utc
        )
        after_first_due_amount_event = first_due_amount_event + relativedelta(seconds=1)
        end = start + relativedelta(months=2)
        sub_tests = [
            get_mimic_loan_creation_subtest(start=start, amount="1000", drawdown_loan_instances=2),
            SubTest(
                description="Check due amounts",
                expected_balances_at_ts={
                    first_due_amount_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, "77.55"),
                            (dimensions.INTEREST_DUE, "14.29"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, "77.55"),
                            (dimensions.INTEREST_DUE, "14.29"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "2000"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "155.1"),
                            (dimensions.TOTAL_INTEREST_DUE, "28.58"),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_due_amount_event,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_outstanding_principal",
                        value="2000.0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_due_amount_event,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_available_credit",
                        value="3000.0",
                    ),
                ],
            ),
            SubTest(
                description="Full repayments distributed correctly across loans",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="183.68",
                        event_datetime=after_first_due_amount_event,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    after_first_due_amount_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "1816.32"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "0"),
                            (dimensions.TOTAL_INTEREST_DUE, "0"),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=after_first_due_amount_event,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_outstanding_principal",
                        value="1844.9",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_first_due_amount_event,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_available_credit",
                        value="3155.1",
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

    def test_partial_repayment_distributed_correctly(self):
        start = test_parameters.default_simulation_start_date
        first_due_amount_event = datetime(
            year=2020, month=2, day=5, hour=0, minute=0, second=2, tzinfo=timezone.utc
        )
        after_first_due_amount_event = first_due_amount_event + relativedelta(seconds=1)
        end = start + relativedelta(months=2)
        sub_tests = [
            get_mimic_loan_creation_subtest(start=start, amount="1000", drawdown_loan_instances=2),
            SubTest(
                description="Check due amounts",
                expected_balances_at_ts={
                    first_due_amount_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, "77.55"),
                            (dimensions.INTEREST_DUE, "14.29"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, "77.55"),
                            (dimensions.INTEREST_DUE, "14.29"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "2000"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "155.1"),
                            (dimensions.TOTAL_INTEREST_DUE, "28.58"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Partial repayments distributed correctly across loans",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="100",
                        event_datetime=after_first_due_amount_event,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    after_first_due_amount_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "14.29"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, "55.1"),
                            (dimensions.INTEREST_DUE, "14.29"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "1900"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "55.1"),
                            (dimensions.TOTAL_INTEREST_DUE, "28.58"),
                        ],
                    },
                },
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

    def test_targeted_repayment_distributed_correctly(self):
        start = test_parameters.default_simulation_start_date
        first_due_amount_event = datetime(
            year=2020, month=2, day=5, hour=0, minute=0, second=2, tzinfo=timezone.utc
        )
        after_first_due_amount_event = first_due_amount_event + relativedelta(seconds=1)
        end = start + relativedelta(months=2)
        sub_tests = [
            get_mimic_loan_creation_subtest(start=start, amount="1000", drawdown_loan_instances=2),
            SubTest(
                description="Check due amounts",
                expected_balances_at_ts={
                    first_due_amount_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, "77.55"),
                            (dimensions.INTEREST_DUE, "14.29"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, "77.55"),
                            (dimensions.INTEREST_DUE, "14.29"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "2000"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "155.1"),
                            (dimensions.TOTAL_INTEREST_DUE, "28.58"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Targeted repayments distributed correctly across loans",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="91.84",
                        event_datetime=after_first_due_amount_event,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={
                            "target_account_id": f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1"
                        },
                    )
                ],
                expected_balances_at_ts={
                    after_first_due_amount_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, "77.55"),
                            (dimensions.INTEREST_DUE, "14.29"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "1908.16"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "77.55"),
                            (dimensions.TOTAL_INTEREST_DUE, "14.29"),
                        ],
                    },
                },
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

    def test_overdue_repayment_distributed_correctly(self):
        start = test_parameters.default_simulation_start_date
        first_due_amount_event = datetime(
            year=2020, month=2, day=5, hour=0, minute=0, second=2, tzinfo=timezone.utc
        )
        first_overdue_event = first_due_amount_event + relativedelta(days=7)
        second_due_amount_event = first_due_amount_event + relativedelta(months=1)
        first_payment_datetime = second_due_amount_event + relativedelta(seconds=1)
        second_payment_datetime = first_payment_datetime + relativedelta(seconds=1)
        third_payment_datetime = second_payment_datetime + relativedelta(seconds=1)
        fourth_payment_datetime = third_payment_datetime + relativedelta(seconds=1)
        fifth_payment_datetime = fourth_payment_datetime + relativedelta(seconds=1)
        end = start + relativedelta(months=3)
        sub_tests = [
            get_mimic_loan_creation_subtest(start=start, amount="1000", drawdown_loan_instances=2),
            SubTest(
                description="Two overdue payments cycles",
                expected_balances_at_ts={
                    first_overdue_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "77.55"),
                            (dimensions.INTEREST_OVERDUE, "14.29"),
                            (dimensions.PENALTIES, "0"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "77.55"),
                            (dimensions.INTEREST_OVERDUE, "14.29"),
                            (dimensions.PENALTIES, "0"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "2000"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "0"),
                            (dimensions.TOTAL_INTEREST_DUE, "0"),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, "155.1"),
                            (dimensions.TOTAL_INTEREST_OVERDUE, "28.58"),
                            (dimensions.PENALTIES, "25"),
                            (dimensions.TOTAL_PENALTIES, "0"),
                        ],
                    },
                    second_due_amount_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, "79.29"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "77.55"),
                            (dimensions.INTEREST_OVERDUE, "14.29"),
                            (dimensions.PENALTIES, "1.1"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, "79.29"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "77.55"),
                            (dimensions.INTEREST_OVERDUE, "14.29"),
                            (dimensions.PENALTIES, "1.1"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "2000"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "158.58"),
                            (dimensions.TOTAL_INTEREST_DUE, "21.84"),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, "155.1"),
                            (dimensions.TOTAL_INTEREST_OVERDUE, "28.58"),
                            (dimensions.PENALTIES, "25"),
                            (dimensions.TOTAL_PENALTIES, "2.2"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check overdue principals are paid off first",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="155.1",
                        event_datetime=first_payment_datetime,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    first_payment_datetime: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, "79.29"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "14.29"),
                            (dimensions.PENALTIES, "1.1"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, "79.29"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "14.29"),
                            (dimensions.PENALTIES, "1.1"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "1844.9"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "158.58"),
                            (dimensions.TOTAL_INTEREST_DUE, "21.84"),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, "0"),
                            (dimensions.TOTAL_INTEREST_OVERDUE, "28.58"),
                            (dimensions.PENALTIES, "25"),
                            (dimensions.TOTAL_PENALTIES, "2.2"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check over due interests are paid off second",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="28.58",
                        event_datetime=second_payment_datetime,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    second_payment_datetime: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, "79.29"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "1.1"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, "79.29"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "1.1"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "1816.32"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "158.58"),
                            (dimensions.TOTAL_INTEREST_DUE, "21.84"),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, "0"),
                            (dimensions.TOTAL_INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "25"),
                            (dimensions.TOTAL_PENALTIES, "2.2"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check penalties are paid off third",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        # 25 + 2.2 = 27.20
                        amount="27.20",
                        event_datetime=third_payment_datetime,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    third_payment_datetime: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, "79.29"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, "79.29"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            # the 25 for the PENALTIES is rebalanced from DEFAULT into PENALTIES
                            # which means that DEFAULT is only decreased by 2.2
                            (dimensions.DEFAULT, "1814.12"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "158.58"),
                            (dimensions.TOTAL_INTEREST_DUE, "21.84"),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, "0"),
                            (dimensions.TOTAL_INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.TOTAL_PENALTIES, "0"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check due principals are paid off fourth",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="158.58",
                        event_datetime=fourth_payment_datetime,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    fourth_payment_datetime: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "1655.54"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "0"),
                            (dimensions.TOTAL_INTEREST_DUE, "21.84"),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, "0"),
                            (dimensions.TOTAL_INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check due interests are paid off fifth",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="21.84",
                        event_datetime=fifth_payment_datetime,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    fifth_payment_datetime: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "1633.7"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "0"),
                            (dimensions.TOTAL_INTEREST_DUE, "0"),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, "0"),
                            (dimensions.TOTAL_INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                        ],
                    },
                },
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

    def test_overdue_targeted_repayment_distributed_correctly(self):
        start = test_parameters.default_simulation_start_date
        first_due_amount_event = datetime(
            year=2020, month=2, day=5, hour=0, minute=0, second=2, tzinfo=timezone.utc
        )
        first_overdue_event = first_due_amount_event + relativedelta(days=7)
        second_due_amount_event = first_due_amount_event + relativedelta(months=1)
        first_payment_datetime = second_due_amount_event + relativedelta(seconds=1)
        second_payment_datetime = first_payment_datetime + relativedelta(seconds=1)
        third_payment_datetime = second_payment_datetime + relativedelta(seconds=1)
        fourth_payment_datetime = third_payment_datetime + relativedelta(seconds=1)
        fifth_payment_datetime = fourth_payment_datetime + relativedelta(seconds=1)
        end = start + relativedelta(months=3)
        sub_tests = [
            get_mimic_loan_creation_subtest(start=start, amount="1000", drawdown_loan_instances=2),
            SubTest(
                description="Two overdue payments cycles",
                expected_balances_at_ts={
                    first_overdue_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "77.55"),
                            (dimensions.INTEREST_OVERDUE, "14.29"),
                            (dimensions.PENALTIES, "0"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "77.55"),
                            (dimensions.INTEREST_OVERDUE, "14.29"),
                            (dimensions.PENALTIES, "0"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "2000"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "0"),
                            (dimensions.TOTAL_INTEREST_DUE, "0"),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, "155.1"),
                            (dimensions.TOTAL_INTEREST_OVERDUE, "28.58"),
                            (dimensions.PENALTIES, "25"),
                            (dimensions.TOTAL_PENALTIES, "0"),
                        ],
                    },
                    second_due_amount_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, "79.29"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "77.55"),
                            (dimensions.INTEREST_OVERDUE, "14.29"),
                            (dimensions.PENALTIES, "1.1"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, "79.29"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "77.55"),
                            (dimensions.INTEREST_OVERDUE, "14.29"),
                            (dimensions.PENALTIES, "1.1"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "2000"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "158.58"),
                            (dimensions.TOTAL_INTEREST_DUE, "21.84"),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, "155.1"),
                            (dimensions.TOTAL_INTEREST_OVERDUE, "28.58"),
                            (dimensions.PENALTIES, "25"),
                            (dimensions.TOTAL_PENALTIES, "2.2"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check overdue principal of loan 1 is paid off first",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="77.55",
                        event_datetime=first_payment_datetime,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={
                            "target_account_id": f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1"
                        },
                    )
                ],
                expected_balances_at_ts={
                    first_payment_datetime: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, "79.29"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "77.55"),
                            (dimensions.INTEREST_OVERDUE, "14.29"),
                            (dimensions.PENALTIES, "1.1"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, "79.29"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "14.29"),
                            (dimensions.PENALTIES, "1.1"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "1922.45"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "158.58"),
                            (dimensions.TOTAL_INTEREST_DUE, "21.84"),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, "77.55"),
                            (dimensions.TOTAL_INTEREST_OVERDUE, "28.58"),
                            (dimensions.PENALTIES, "25"),
                            (dimensions.TOTAL_PENALTIES, "2.2"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check over due interest of loan 1 is paid off second",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="14.29",
                        event_datetime=second_payment_datetime,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={
                            "target_account_id": f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1"
                        },
                    )
                ],
                expected_balances_at_ts={
                    second_payment_datetime: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, "79.29"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "77.55"),
                            (dimensions.INTEREST_OVERDUE, "14.29"),
                            (dimensions.PENALTIES, "1.1"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, "79.29"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "1.1"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "1908.16"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "158.58"),
                            (dimensions.TOTAL_INTEREST_DUE, "21.84"),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, "77.55"),
                            (dimensions.TOTAL_INTEREST_OVERDUE, "14.29"),
                            (dimensions.PENALTIES, "25"),
                            (dimensions.TOTAL_PENALTIES, "2.2"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check penalties are paid off third",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        # 25 + 1.1 = 26.10
                        amount="26.10",
                        event_datetime=third_payment_datetime,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={
                            "target_account_id": f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1"
                        },
                    )
                ],
                expected_balances_at_ts={
                    third_payment_datetime: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, "79.29"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "77.55"),
                            (dimensions.INTEREST_OVERDUE, "14.29"),
                            (dimensions.PENALTIES, "1.1"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, "79.29"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            # the 25 for the PENALTIES is rebalanced from DEFAULT into PENALTIES
                            # which means that DEFAULT is only decreased by 1.1
                            (dimensions.DEFAULT, "1907.06"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "158.58"),
                            (dimensions.TOTAL_INTEREST_DUE, "21.84"),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, "77.55"),
                            (dimensions.TOTAL_INTEREST_OVERDUE, "14.29"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.TOTAL_PENALTIES, "1.1"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check due principal of loan 1 is paid off fourth",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="79.29",
                        event_datetime=fourth_payment_datetime,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={
                            "target_account_id": f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1"
                        },
                    )
                ],
                expected_balances_at_ts={
                    fourth_payment_datetime: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, "79.29"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "77.55"),
                            (dimensions.INTEREST_OVERDUE, "14.29"),
                            (dimensions.PENALTIES, "1.1"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "1827.77"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "79.29"),
                            (dimensions.TOTAL_INTEREST_DUE, "21.84"),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, "77.55"),
                            (dimensions.TOTAL_INTEREST_OVERDUE, "14.29"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.TOTAL_PENALTIES, "1.1"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check due interest of loan 1 is paid off fifth",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="10.92",
                        event_datetime=fifth_payment_datetime,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={
                            "target_account_id": f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1"
                        },
                    )
                ],
                expected_balances_at_ts={
                    fifth_payment_datetime: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, "79.29"),
                            (dimensions.INTEREST_DUE, "10.92"),
                            (dimensions.PRINCIPAL_OVERDUE, "77.55"),
                            (dimensions.INTEREST_OVERDUE, "14.29"),
                            (dimensions.PENALTIES, "1.1"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "1816.85"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "79.29"),
                            (dimensions.TOTAL_INTEREST_DUE, "10.92"),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, "77.55"),
                            (dimensions.TOTAL_INTEREST_OVERDUE, "14.29"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.TOTAL_PENALTIES, "1.1"),
                        ],
                    },
                },
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

    def test_overpayment_distributed_correctly_before_repayment_is_due(self):
        start = (
            # the simulation start date is datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
            test_parameters.default_simulation_start_date
        )
        # due amount calc day: 5
        # 5 days of non-emi accrual and 1 day of emi accrual
        after_disbursement = start + relativedelta(days=5)
        first_payment_datetime = after_disbursement + relativedelta(seconds=1)
        second_payment_datetime = first_payment_datetime + relativedelta(seconds=1)
        end = second_payment_datetime
        sub_tests = [
            get_mimic_loan_creation_subtest(start=start, amount="1000", drawdown_loan_instances=2),
            SubTest(
                description="Check balances after disbursement",
                expected_balances_at_ts={
                    after_disbursement: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.40822"),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, "1.63288"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER, "0"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.40822"),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, "1.63288"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER, "0"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "2000"),
                            (dimensions.TOTAL_PRINCIPAL, "2000"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "0"),
                            (dimensions.TOTAL_INTEREST_DUE, "0"),
                            (dimensions.TOTAL_ACCRUED_INTEREST_RECEIVABLE, "0.81644"),
                            (dimensions.TOTAL_NON_EMI_ACCRUED_INTEREST_RECEIVABLE, "3.26576"),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=after_disbursement,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_outstanding_principal",
                        value="2000",
                    ),
                    # TODO: Uncomment after INC-9826 lands
                    ExpectedDerivedParameter(
                        timestamp=after_disbursement,
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0",
                        name="per_loan_early_repayment_amount",
                        # overpayment amount + overpayment fee + accrued interest
                        # 1000 + 52.63 + (0.40822 + 1.63288)
                        value="1054.67",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_disbursement,
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1",
                        name="per_loan_early_repayment_amount",
                        # overpayment amount + overpayment fee + accrued interest
                        # 1000 + 52.63 + (0.40822 + 1.63288)
                        value="1054.67",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_disbursement,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_early_repayment_amount",
                        value="2109.34",
                    ),
                ],
            ),
            SubTest(
                description="Loan 1 principal and accrued interest paid first",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        # To fully repay principal and accrued interest (1002.0411):
                        # overpayment amount - overpayment fee = 1002.0411
                        # 1054.78 - (1054.78 * 0.05) = 1002.0411
                        amount="1054.78",
                        event_datetime=first_payment_datetime,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    first_payment_datetime: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.OVERPAYMENT, "1000"),
                            (dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER, "1000"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.40822"),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, "1.63288"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER, "0"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "997.96"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "0"),
                            (dimensions.TOTAL_INTEREST_DUE, "0"),
                            (dimensions.TOTAL_ACCRUED_INTEREST_RECEIVABLE, "0.40822"),
                            (dimensions.TOTAL_NON_EMI_ACCRUED_INTEREST_RECEIVABLE, "1.63288"),
                        ],
                        accounts.OVERPAYMENT_FEE_INCOME_ACCOUNT: [(dimensions.DEFAULT, "52.74")],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_payment_datetime,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_outstanding_principal",
                        value="1000",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_payment_datetime,
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0",
                        name="per_loan_early_repayment_amount",
                        value="0.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_payment_datetime,
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1",
                        name="per_loan_early_repayment_amount",
                        value="1054.67",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_payment_datetime,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_early_repayment_amount",
                        value="1054.67",
                    ),
                ],
            ),
            SubTest(
                description="Loan 2 principal and accrued interest paid second",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        # The overpayment fee is the minimum of the amount derived from the subtest
                        # above (52.74) and the maximum overpayment fee, which is
                        # (principal remaining * overpayment rate) / (1 - overpayment rate),
                        # so (1000 * 0.05) / (1 - 0.05) = 52.63
                        # so in this case we only pay 52.63 in overpayment fees
                        # 1000 + 0.40822 + 1.63288 + 52.63 = 1054.67
                        amount="1054.67",
                        event_datetime=second_payment_datetime,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    second_payment_datetime: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.OVERPAYMENT, "1000"),
                            (dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER, "1000"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.OVERPAYMENT, "1000"),
                            (dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER, "1000"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "-4.08"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "0"),
                            (dimensions.TOTAL_INTEREST_DUE, "0"),
                            (dimensions.TOTAL_ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.TOTAL_NON_EMI_ACCRUED_INTEREST_RECEIVABLE, "0"),
                        ],
                        accounts.OVERPAYMENT_FEE_INCOME_ACCOUNT: [(dimensions.DEFAULT, "105.37")],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=second_payment_datetime,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_outstanding_principal",
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_payment_datetime,
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0",
                        name="per_loan_early_repayment_amount",
                        value="0.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_payment_datetime,
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1",
                        name="per_loan_early_repayment_amount",
                        value="0.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_payment_datetime,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_early_repayment_amount",
                        value="0.00",
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

    def test_overpayment_distributed_correctly_when_repayment_is_due(self):
        start = test_parameters.default_simulation_start_date
        first_due_amount_event = datetime(
            year=2020, month=2, day=5, hour=0, minute=0, second=2, tzinfo=timezone.utc
        )
        first_payment_event = first_due_amount_event + relativedelta(days=2)
        second_payment_event = first_payment_event + relativedelta(seconds=1)
        third_payment_event = second_payment_event + relativedelta(seconds=1)
        end = third_payment_event
        sub_tests = [
            get_mimic_loan_creation_subtest(start=start, amount="1000", drawdown_loan_instances=2),
            SubTest(
                description="Check due amounts",
                expected_balances_at_ts={
                    first_due_amount_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL, "922.45"),
                            (dimensions.PRINCIPAL_DUE, "77.55"),
                            (dimensions.INTEREST_DUE, "14.29"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER, "0"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL, "922.45"),
                            (dimensions.PRINCIPAL_DUE, "77.55"),
                            (dimensions.INTEREST_DUE, "14.29"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER, "0"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "2000"),
                            (dimensions.TOTAL_PRINCIPAL, "1844.90"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "155.1"),
                            (dimensions.TOTAL_INTEREST_DUE, "28.58"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Due amounts paid first",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="183.68",
                        event_datetime=first_payment_event,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    first_payment_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL, "922.45"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.75312"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER, "0"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL, "922.45"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.75312"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER, "0"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "1816.32"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "0"),
                            (dimensions.TOTAL_INTEREST_DUE, "0"),
                        ],
                        accounts.OVERPAYMENT_FEE_INCOME_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Loan 1 principal and accrued interest paid second",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        # To fully repay principal and accrued interest (922.45 + 0.75312 = 923.20):
                        # overpayment amount - overpayment fee = 923.20
                        # 971.79 - (971.79 * 0.05) = 923.20
                        amount="971.79",
                        event_datetime=second_payment_event,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    second_payment_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.OVERPAYMENT, "922.45"),
                            (dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER, "922.45"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL, "922.45"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.75312"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER, "0"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "893.12"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "0"),
                            (dimensions.TOTAL_INTEREST_DUE, "0"),
                        ],
                        accounts.OVERPAYMENT_FEE_INCOME_ACCOUNT: [(dimensions.DEFAULT, "48.59")],
                    },
                },
            ),
            SubTest(
                description="Loan 2 principal and accrued interest paid third",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        # The overpayment fee is the minimum of the amount derived from the subtest
                        # above (48.59) and the maximum overpayment fee, which is
                        # (principal remaining * overpayment rate) / (1 - overpayment rate),
                        # so (922.45 * 0.05) / (1 - 0.05) = 48.55
                        # so in this case we only pay 48.55 in overpayment fees
                        amount="971.75",
                        event_datetime=third_payment_event,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    third_payment_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.OVERPAYMENT, "922.45"),
                            (dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER, "922.45"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.OVERPAYMENT, "922.45"),
                            (dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER, "922.45"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "-30.08"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "0"),
                            (dimensions.TOTAL_INTEREST_DUE, "0"),
                        ],
                        accounts.OVERPAYMENT_FEE_INCOME_ACCOUNT: [(dimensions.DEFAULT, "97.14")],
                    },
                },
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

    def test_targeted_overpayment_distributed_correctly(self):
        start = test_parameters.default_simulation_start_date
        first_due_amount_event = datetime(
            year=2020, month=2, day=5, hour=0, minute=0, second=2, tzinfo=timezone.utc
        )
        first_payment_event = first_due_amount_event + relativedelta(days=2)
        second_payment_event = first_payment_event + relativedelta(seconds=1)
        third_payment_event = second_payment_event + relativedelta(seconds=1)
        end = start + relativedelta(months=2)
        sub_tests = [
            get_mimic_loan_creation_subtest(start=start, amount="1000", drawdown_loan_instances=2),
            SubTest(
                description="Check due amounts",
                expected_balances_at_ts={
                    first_due_amount_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL, "922.45"),
                            (dimensions.PRINCIPAL_DUE, "77.55"),
                            (dimensions.INTEREST_DUE, "14.29"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER, "0"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL, "922.45"),
                            (dimensions.PRINCIPAL_DUE, "77.55"),
                            (dimensions.INTEREST_DUE, "14.29"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER, "0"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "2000"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "155.1"),
                            (dimensions.TOTAL_INTEREST_DUE, "28.58"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Loan 2 due amount paid first",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="91.84",
                        event_datetime=first_payment_event,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={
                            "target_account_id": f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1"
                        },
                    )
                ],
                expected_balances_at_ts={
                    first_payment_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL, "922.45"),
                            (dimensions.PRINCIPAL_DUE, "77.55"),
                            (dimensions.INTEREST_DUE, "14.29"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.75312"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER, "0"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL, "922.45"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.75312"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "1908.16"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "77.55"),
                            (dimensions.TOTAL_INTEREST_DUE, "14.29"),
                        ],
                        accounts.OVERPAYMENT_FEE_INCOME_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Loan 2 principal paid second",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        # To fully repay principal (922.45):
                        # overpayment amount - overpayment fee = 922.45
                        # 971 - (971 * 0.05) = 922.45
                        amount="971",
                        event_datetime=second_payment_event,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={
                            "target_account_id": f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1"
                        },
                    )
                ],
                expected_balances_at_ts={
                    second_payment_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL, "922.45"),
                            (dimensions.PRINCIPAL_DUE, "77.55"),
                            (dimensions.INTEREST_DUE, "14.29"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.75312"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER, "0"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.75312"),
                            (dimensions.OVERPAYMENT, "922.45"),
                            (dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER, "922.45"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "985.71"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "77.55"),
                            (dimensions.TOTAL_INTEREST_DUE, "14.29"),
                        ],
                        accounts.OVERPAYMENT_FEE_INCOME_ACCOUNT: [(dimensions.DEFAULT, "48.55")],
                    },
                },
            ),
            SubTest(
                description="Loan 2 accrued interest paid third",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="0.75",
                        event_datetime=third_payment_event,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={
                            "target_account_id": f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1"
                        },
                    )
                ],
                expected_balances_at_ts={
                    third_payment_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL, "922.45"),
                            (dimensions.PRINCIPAL_DUE, "77.55"),
                            (dimensions.INTEREST_DUE, "14.29"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.75312"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER, "0"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.OVERPAYMENT, "922.45"),
                            (dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER, "922.45"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "984.96"),
                            (dimensions.TOTAL_PRINCIPAL_DUE, "77.55"),
                            (dimensions.TOTAL_INTEREST_DUE, "14.29"),
                        ],
                        accounts.OVERPAYMENT_FEE_INCOME_ACCOUNT: [(dimensions.DEFAULT, "48.55")],
                    },
                },
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
