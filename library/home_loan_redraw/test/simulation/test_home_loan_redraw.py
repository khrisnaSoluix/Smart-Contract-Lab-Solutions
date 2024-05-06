# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

# library
from library.home_loan_redraw.contracts.template import home_loan_redraw
from library.home_loan_redraw.test import accounts, dimensions, files, parameters
from library.home_loan_redraw.test.simulation.accounts import default_internal_accounts

# inception sdk
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ContractNotificationResourceType,
    ExpectedContractNotification,
    ExpectedDerivedParameter,
    ExpectedRejection,
    ExpectedSchedule,
    SimulationTestScenario,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.errors import missing_parameter
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_account_product_version_update_instruction,
    create_inbound_authorisation_instruction,
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_outbound_hard_settlement_instruction,
    create_posting_instruction_batch,
    create_template_parameter_change_event,
    update_account_status_pending_closure,
)
from inception_sdk.test_framework.contracts.simulation.utils import SimulationTestCase
from inception_sdk.vault.postings.posting_classes import InboundHardSettlement

HOME_LOAN_REDRAW_PAID_OFF = "HOME_LOAN_REDRAW_PAID_OFF"

default_start_date = datetime(year=2020, month=1, day=5, tzinfo=ZoneInfo("UTC"))


def get_expected_derived_parameters(timestamp, account_id, expected_parameters):
    expected_derived_parameters = []
    for parameter in expected_parameters:
        expected_derived_parameters.append(
            ExpectedDerivedParameter(
                timestamp, account_id, parameter, expected_parameters[parameter]
            )
        )
    return expected_derived_parameters


class HomeLoanRedrawTest(SimulationTestCase):
    account_id_base = accounts.HOME_LOAN_REDRAW
    contract_filepaths = [files.HOME_LOAN_REDRAW_CONTRACT]
    default_denomination = dimensions.TEST_DENOMINATION
    internal_accounts = default_internal_accounts
    home_loan_redraw_instance_params = parameters.default_instance
    home_loan_redraw_template_params = parameters.default_template

    def get_simulation_test_scenario(
        self,
        start,
        end,
        sub_tests,
        template_params=None,
        instance_params=None,
        internal_accounts=None,
        debug=False,
    ):
        contract_config = ContractConfig(
            contract_content=self.smart_contract_path_to_content[files.HOME_LOAN_REDRAW_CONTRACT],
            template_params=template_params or self.home_loan_redraw_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or self.home_loan_redraw_instance_params,
                    account_id_base=self.account_id_base,
                )
            ],
        )
        return SimulationTestScenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            contract_config=contract_config,
            internal_accounts=self.internal_accounts or internal_accounts,
            debug=debug,
        )

    def test_basic_accrual_and_due_amount_calculation(self):
        start = datetime(2020, 1, 5, tzinfo=ZoneInfo("UTC"))
        first_due_amount_calculation = datetime(2020, 2, 11, 0, 1, tzinfo=ZoneInfo("UTC"))
        second_due_amount_calculation = first_due_amount_calculation + relativedelta(months=1)
        end = second_due_amount_calculation + relativedelta(days=1)

        sub_tests = [
            SubTest(
                description="check non emi interest accrued",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1): {
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, Decimal("800000")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("43.83560")),
                        ]
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            # interest schedule should run at 00:00:00
                            start
                            + relativedelta(days=1)
                        ],
                        event_id=home_loan_redraw.interest_accrual.ACCRUAL_EVENT,
                        account_id=self.account_id_base,
                    )
                ],
                expected_derived_parameters=get_expected_derived_parameters(
                    timestamp=start + relativedelta(days=1),
                    account_id=accounts.HOME_LOAN_REDRAW,
                    expected_parameters={
                        "available_redraw_funds": "0.00",
                        "next_repayment_date": "2020-02-11",
                        "remaining_term": "12",
                        "total_outstanding_debt": "800043.84",
                        "total_outstanding_payments": "0.00",
                        "total_remaining_principal": "800000.00",
                    },
                ),
            ),
            SubTest(
                description="check emi interest accrued",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=7): {
                        accounts.HOME_LOAN_REDRAW: [
                            (dimensions.PRINCIPAL, Decimal("800000")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("306.8492")),
                        ]
                    },
                },
            ),
            SubTest(
                description="check due amounts > emi with non-emi interest",
                expected_balances_at_ts={
                    first_due_amount_calculation: {
                        accounts.HOME_LOAN_REDRAW: [
                            (dimensions.PRINCIPAL, Decimal("733967.82")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.EMI, Decimal("67391.09")),
                            # DUE exceeds EMI due to non-emi interest
                            (dimensions.PRINCIPAL_DUE, Decimal("66032.18")),
                            (dimensions.INTEREST_DUE, Decimal("1621.92")),
                        ]
                    },
                },
                expected_derived_parameters=get_expected_derived_parameters(
                    timestamp=first_due_amount_calculation,
                    account_id=accounts.HOME_LOAN_REDRAW,
                    expected_parameters={
                        "next_repayment_date": "2020-02-11",
                        "total_outstanding_debt": "801621.92",
                        "total_outstanding_payments": "67654.10",
                        "total_remaining_principal": "800000.00",
                    },
                ),
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_due_amount_calculation],
                        event_id="DUE_AMOUNT_CALCULATION",
                        account_id=self.account_id_base,
                    )
                ],
            ),
            SubTest(
                description="check due amounts == emi with no non-emi interest",
                expected_balances_at_ts={
                    second_due_amount_calculation: {
                        accounts.HOME_LOAN_REDRAW: [
                            (dimensions.PRINCIPAL, Decimal("667743.03")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.EMI, Decimal("67391.09")),
                            # DUE delta w.r.t previous due amount calc is:
                            # 132256.97 + 2788.22 - 66032.18 - 1621.92 == 67391.09 == EMI
                            (dimensions.PRINCIPAL_DUE, Decimal("132256.97")),
                            (dimensions.INTEREST_DUE, Decimal("2788.22")),
                        ]
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[second_due_amount_calculation],
                        event_id="DUE_AMOUNT_CALCULATION",
                        account_id=self.account_id_base,
                    )
                ],
                expected_derived_parameters=get_expected_derived_parameters(
                    timestamp=second_due_amount_calculation,
                    account_id=accounts.HOME_LOAN_REDRAW,
                    expected_parameters={
                        "next_repayment_date": "2020-03-11",
                        "total_outstanding_debt": "802788.22",
                        "total_outstanding_payments": "135045.19",
                        "total_remaining_principal": "800000.00",
                    },
                ),
            ),
            SubTest(
                description="ensure next repayment date decreases the day "
                "after the due day calculation",
                expected_derived_parameters=get_expected_derived_parameters(
                    timestamp=datetime(
                        year=second_due_amount_calculation.year,
                        month=second_due_amount_calculation.month,
                        day=second_due_amount_calculation.day + 1,
                        tzinfo=ZoneInfo("UTC"),
                    ),
                    account_id=accounts.HOME_LOAN_REDRAW,
                    expected_parameters={
                        "next_repayment_date": "2020-04-11",
                    },
                ),
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_auto_repay_due_amounts_from_redraw_balance(self):
        start = datetime(2020, 1, 5, tzinfo=ZoneInfo("UTC"))
        first_due_amount_calculation = datetime(2020, 2, 11, 0, 1, tzinfo=ZoneInfo("UTC"))
        second_due_amount_calculation = first_due_amount_calculation + relativedelta(months=1)
        third_due_amount_calculation = second_due_amount_calculation + relativedelta(months=1)
        end = third_due_amount_calculation + relativedelta(seconds=1)

        sub_tests = [
            SubTest(
                description="Check balances after adding an overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=first_due_amount_calculation - relativedelta(seconds=30),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.DEPOSIT,
                        denomination=self.default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    first_due_amount_calculation
                    - relativedelta(seconds=30): {
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, Decimal("800000")),
                            (dimensions.EMI, Decimal("67391.09")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.REDRAW, Decimal("-10000")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("790000"))],
                    },
                },
                expected_derived_parameters=get_expected_derived_parameters(
                    timestamp=first_due_amount_calculation - relativedelta(seconds=30),
                    account_id=accounts.HOME_LOAN_REDRAW,
                    expected_parameters={
                        "available_redraw_funds": "10000.00",
                        "next_repayment_date": "2020-02-11",
                        "remaining_term": "12",
                        "total_outstanding_debt": "801621.92",
                        "total_outstanding_payments": "0.00",
                        "total_remaining_principal": "800000.00",
                    },
                ),
            ),
            SubTest(
                description="Check that the redraw balance was used to automatically pay off "
                "part of the due amounts",
                expected_balances_at_ts={
                    first_due_amount_calculation: {
                        accounts.HOME_LOAN_REDRAW: [
                            (dimensions.PRINCIPAL, Decimal("733967.82")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.EMI, Decimal("67391.09")),
                            # Original principal due 66032.18, so after using the redraw balance,
                            # the new principal due should be 66032.18 - 10000 = 56032.18
                            (dimensions.PRINCIPAL_DUE, Decimal("56032.18")),
                            (dimensions.INTEREST_DUE, Decimal("1621.92")),
                            (dimensions.REDRAW, Decimal("0")),
                        ]
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_due_amount_calculation],
                        event_id="DUE_AMOUNT_CALCULATION",
                        account_id=self.account_id_base,
                    )
                ],
                expected_derived_parameters=get_expected_derived_parameters(
                    timestamp=first_due_amount_calculation,
                    account_id=accounts.HOME_LOAN_REDRAW,
                    expected_parameters={
                        "available_redraw_funds": "0.00",
                        "next_repayment_date": "2020-02-11",
                        "remaining_term": "11",
                        # total remaining principal + interest
                        # 790000.00 + 1621.92 = 791621.92
                        "total_outstanding_debt": "791621.92",
                        # sum of the remaining principal due and interest due
                        # 56032.18 + 1621.92 = 57654.1
                        "total_outstanding_payments": "57654.10",
                        "total_remaining_principal": "790000.00",
                    },
                ),
            ),
            SubTest(
                description="Repay the remaining due amounts",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # The remaining due amounts from the test above are
                        # 56032.18 + 1621.92 = 57654.10
                        amount="57654.10",
                        event_datetime=first_due_amount_calculation + relativedelta(seconds=1),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.DEPOSIT,
                        denomination=self.default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    first_due_amount_calculation
                    + relativedelta(seconds=1): {
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, Decimal("733967.82")),
                            (dimensions.EMI, Decimal("67391.09")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.REDRAW, Decimal("0")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("732345.90"))],
                    },
                },
                expected_derived_parameters=get_expected_derived_parameters(
                    timestamp=first_due_amount_calculation + relativedelta(seconds=1),
                    account_id=accounts.HOME_LOAN_REDRAW,
                    expected_parameters={
                        "available_redraw_funds": "0.00",
                        "next_repayment_date": "2020-02-11",
                        "remaining_term": "11",
                        "total_outstanding_debt": "733967.82",
                        "total_outstanding_payments": "0.00",
                        "total_remaining_principal": "733967.82",
                    },
                ),
            ),
            SubTest(
                description="Add another overpayment right before second due amount calculation in "
                "order to pay off full due amount from redraw balance",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="67391.09",  # EMI amount
                        event_datetime=second_due_amount_calculation - relativedelta(seconds=30),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.DEPOSIT,
                        denomination=self.default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    second_due_amount_calculation
                    - relativedelta(seconds=30): {
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, Decimal("733967.82")),
                            (dimensions.EMI, Decimal("67391.09")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.REDRAW, Decimal("-67391.09")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("664954.81"))],
                    },
                },
                expected_derived_parameters=get_expected_derived_parameters(
                    timestamp=second_due_amount_calculation - relativedelta(seconds=30),
                    account_id=accounts.HOME_LOAN_REDRAW,
                    expected_parameters={
                        "available_redraw_funds": "67391.09",
                        "next_repayment_date": "2020-03-11",
                        # The remaining term takes into account the redraw balance
                        # and so the remaining term value changes from 11 to 10 before
                        # the next due amount calculation.
                        "remaining_term": "10",
                        "total_outstanding_debt": "735134.12",
                        "total_outstanding_payments": "0.00",
                        "total_remaining_principal": "733967.82",
                    },
                ),
            ),
            SubTest(
                description="Repay all due amounts from the redraw balance",
                expected_balances_at_ts={
                    second_due_amount_calculation: {
                        accounts.HOME_LOAN_REDRAW: [
                            (dimensions.PRINCIPAL, Decimal("667743.03")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.REDRAW, Decimal("0")),
                        ]
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[second_due_amount_calculation],
                        event_id="DUE_AMOUNT_CALCULATION",
                        account_id=self.account_id_base,
                    )
                ],
            ),
            SubTest(
                description="Add another overpayment right before third due amount calculation in "
                "order to pay off full due amount from redraw balance with extra in the "
                "redraw balance",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # EMI amount + 1500 extra
                        # 67391.09 + 1500 = 68891.09
                        amount="68891.09",
                        event_datetime=third_due_amount_calculation - relativedelta(seconds=30),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.DEPOSIT,
                        denomination=self.default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    third_due_amount_calculation
                    - relativedelta(seconds=30): {
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, Decimal("667743.03")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.REDRAW, Decimal("-68891.09")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("596063.72"))],
                    },
                },
            ),
            SubTest(
                description="Repay all due amounts from the redraw balance "
                "with leftover redraw funds",
                expected_balances_at_ts={
                    third_due_amount_calculation: {
                        accounts.HOME_LOAN_REDRAW: [
                            (dimensions.PRINCIPAL, Decimal("601486.19")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.REDRAW, Decimal("-1500")),
                        ]
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[third_due_amount_calculation],
                        event_id="DUE_AMOUNT_CALCULATION",
                        account_id=self.account_id_base,
                    )
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_accrual_accrues_on_net_of_principal_and_redraw_balances(self):
        start = datetime(2020, 1, 5, tzinfo=ZoneInfo("UTC"))
        end = start + relativedelta(days=1, seconds=1)

        sub_tests = [
            SubTest(
                description="Check balances after an overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="400000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.DEPOSIT,
                        denomination=self.default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        self.account_id_base: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("800000")),
                            (dimensions.EMI, Decimal("67391.09")),
                            (dimensions.REDRAW, Decimal("-400000")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("400000"))],
                    }
                },
            ),
            SubTest(
                description="Check that interest is accrued on the net of the principal "
                "and redraw balances",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1): {
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, Decimal("800000")),
                            # This amount should be (PRINCIPAL + REDRAW) *
                            # (Variable interest rate + variable rate adjustment) / 365
                            # = round((800000 - 400000) * round((0.0199 + 0.0001) / 365, 10), 5)
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("21.91780")),
                        ]
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_interest_accruals_with_variable_adjustment_rate_change(self):
        start = datetime(2020, 1, 5, tzinfo=ZoneInfo("UTC"))
        end = start + relativedelta(days=4, seconds=1)

        sub_tests = [
            SubTest(
                description="check initial non emi interest accrued",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1): {
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, Decimal("800000")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("43.83560")),
                        ]
                    },
                },
            ),
            SubTest(
                description="check day 2 variable rate change affects non emi interest",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(days=1, seconds=1),
                        account_id=self.account_id_base,
                        variable_rate_adjustment="0.001",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=2): {
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, Decimal("800000")),
                            # Original + New variable interest rate adjustment at 0.001
                            # Combined Interest Rate at 0.0209
                            # 43.83560 + 45.80824 = 89.64384
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("89.64384")),
                        ]
                    },
                },
            ),
            SubTest(
                description="check day 3 variable rate change affects non emi interest",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(days=2, seconds=1),
                        account_id=self.account_id_base,
                        variable_rate_adjustment="0.002",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=3): {
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, Decimal("800000")),
                            # Original + New variable interest rate adjustment at 0.002
                            # Combined Interest Rate at 0.0219
                            # 89.64384 + 48 = 137.64384
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("137.64384")),
                        ]
                    },
                },
            ),
            SubTest(
                description="check day 4 variable rate change affects non emi interest",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(days=3, seconds=1),
                        account_id=self.account_id_base,
                        variable_rate_adjustment="0.003",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=4): {
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, Decimal("800000")),
                            # Day 3 Bal + New variable interest rate adjustment at 0.003
                            # Combined Interest Rate at 0.0229
                            # 137.64384 + 50.19176 = 187.83560
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("187.83560")),
                        ]
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_interest_accruals_with_variable_interest_rate_change(self):
        start = datetime(2020, 1, 5, tzinfo=ZoneInfo("UTC"))
        end = start + relativedelta(days=5, seconds=1)

        sub_tests = [
            SubTest(
                description="check initial non emi interest accrued",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1): {
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, Decimal("800000")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("43.83560")),
                        ]
                    },
                },
            ),
            SubTest(
                description="check day 2 variable rate change affects non emi interest",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + relativedelta(days=1, seconds=1),
                        variable_interest_rate="0.01",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=2): {
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, Decimal("800000")),
                            # Original + New variable interest rate at 0.01
                            # Combined Interest Rate at 0.0101
                            # 43.83560 + 22.13696 = 65.97256
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("65.97256")),
                        ]
                    },
                },
            ),
            SubTest(
                description="check day 3 variable rate change affects non emi interest",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + relativedelta(days=2, seconds=1),
                        variable_interest_rate="0.02",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=3): {
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, Decimal("800000")),
                            # Original + New variable interest rate at 0.02
                            # Combined Interest Rate at 0.0201
                            # 65.97256 + 44.05480 = 110.02736
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("110.02736")),
                        ]
                    },
                },
            ),
            SubTest(
                description="check day 4 variable rate change affects non emi interest",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + relativedelta(days=3, seconds=1),
                        variable_interest_rate="0.03",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=4): {
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, Decimal("800000")),
                            # Day 3 Bal + New variable interest rate at 0.03
                            # Combined Interest Rate at 0.0301
                            # 110.02736 + 65.97264 = 175.99988
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("176")),
                        ]
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_interest_accruals_with_variable_interest_and_adjustment_rate_change(self):
        start = datetime(2020, 1, 5, tzinfo=ZoneInfo("UTC"))
        end = start + relativedelta(days=5, seconds=1)

        sub_tests = [
            SubTest(
                description="check initial non emi interest accrued",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1): {
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, Decimal("800000")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("43.83560")),
                        ]
                    },
                },
            ),
            SubTest(
                description="day 2 - Interest Rate = 0.01, Adjustment = 0.0001",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + relativedelta(days=1, seconds=1),
                        variable_interest_rate="0.01",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=2): {
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, Decimal("800000")),
                            # Original + New variable interest at 0.0101
                            # 43.83560 + 22.13696 = 65.97256
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("65.97256")),
                        ]
                    },
                },
            ),
            SubTest(
                description="day 3 - Interest Rate = 0.01, Adjustment = 0.0005",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(days=2, seconds=1),
                        account_id=self.account_id_base,
                        variable_rate_adjustment="0.0005",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=3): {
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, Decimal("800000")),
                            # Original + New variable interest at 0.0105
                            # 65.97256 + 23.01368 = 88.98624
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("88.98624")),
                        ]
                    },
                },
            ),
            SubTest(
                description="day 4 - Interest Rate = 0.02, Adjustment = 0.001",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + relativedelta(days=3, seconds=1),
                        variable_interest_rate="0.02",
                    ),
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(days=3, seconds=1),
                        account_id=self.account_id_base,
                        variable_rate_adjustment="0.001",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=4): {
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, Decimal("800000")),
                            # Day 3 Bal + New variable interest at 0.021
                            # 88.98624 + 46.02736 = 135.01360
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("135.01360")),
                        ]
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_account_opening_disbursement(self):
        start = default_start_date
        end = start + relativedelta(seconds=1)

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        self.account_id_base: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("800000")),
                            (dimensions.EMI, Decimal("67391.09")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("800000"))],
                    }
                },
            )
        ]
        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_account_opening_missing_instance_parameters(self):
        start = default_start_date
        end = start + relativedelta(seconds=1)

        req_params = [
            "principal",
            "deposit_account",
            "total_repayment_count",
            "due_amount_calculation_day",
            "variable_rate_adjustment",
        ]
        for param in req_params:
            with self.subTest(f"missing {param}"):
                exp_error = missing_parameter(param)
                instance_params = parameters.default_instance.copy()

                del instance_params[param]

                test_scenario = self.get_simulation_test_scenario(
                    start=start, end=end, instance_params=instance_params, sub_tests=[]
                )
                self.run_test_scenario(test_scenario, expected_simulation_error=exp_error)

    def test_overpayment_redraw_does_not_affect_total_outstanding_debt(self):
        start = default_start_date
        first_due_amount_calculation = datetime(2020, 2, 11, 0, 1, tzinfo=ZoneInfo("UTC"))
        end = first_due_amount_calculation + relativedelta(days=1, seconds=1)
        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        self.account_id_base: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("800000")),
                            (dimensions.EMI, Decimal("67391.09")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("800000"))],
                    }
                },
            ),
            SubTest(
                description="check overpayment over total outstanding debt gets rejected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000000",
                        event_datetime=start + relativedelta(seconds=30),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.DEPOSIT,
                        denomination=self.default_denomination,
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=30),
                        account_id=self.account_id_base,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Cannot make a payment of 1000000 AUD "
                        "greater than the net difference of the total outstanding debt of "
                        "800000.00 AUD and the remaining redraw "
                        "balance of 0.00 AUD.",
                    )
                ],
            ),
            SubTest(
                description="check overpayment equal to total outstanding debt is accepted",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # Principal + expected interest = Total Outstanding Debt
                        # 800000 + 1621.92 = 801621.92
                        amount="801621.92",
                        event_datetime=first_due_amount_calculation - relativedelta(seconds=1),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.DEPOSIT,
                        denomination=self.default_denomination,
                    )
                ],
                expected_derived_parameters=get_expected_derived_parameters(
                    timestamp=first_due_amount_calculation - relativedelta(seconds=1),
                    account_id=accounts.HOME_LOAN_REDRAW,
                    expected_parameters={
                        "available_redraw_funds": "801621.92",
                        "next_repayment_date": "2020-02-11",
                        "total_outstanding_debt": "801621.92",
                        "remaining_term": "0",
                        "total_outstanding_payments": "0.00",
                        "total_remaining_principal": "800000.00",
                    },
                ),
                expected_balances_at_ts={
                    first_due_amount_calculation
                    - relativedelta(seconds=1): {
                        self.account_id_base: [
                            (dimensions.REDRAW, Decimal("-801621.92")),
                            (dimensions.PRINCIPAL, Decimal("800000")),
                            (dimensions.EMI, Decimal("67391.09")),
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("1621.9172")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                        ],
                    }
                },
            ),
            SubTest(
                description="check parameters and balances after due date calc with redraw balance",
                expected_balances_at_ts={
                    first_due_amount_calculation
                    + relativedelta(seconds=1): {
                        self.account_id_base: [
                            # Redraw Total - EMI - Interest Receivable
                            (dimensions.REDRAW, Decimal("-733967.82")),
                            (dimensions.PRINCIPAL, Decimal("733967.82")),
                            (dimensions.EMI, Decimal("67391.09")),
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                        ],
                    }
                },
                expected_derived_parameters=get_expected_derived_parameters(
                    timestamp=first_due_amount_calculation + relativedelta(seconds=1),
                    account_id=accounts.HOME_LOAN_REDRAW,
                    expected_parameters={
                        "available_redraw_funds": "733967.82",
                        "next_repayment_date": "2020-02-11",
                        "total_outstanding_debt": "733967.82",
                        "remaining_term": "0",
                        "total_outstanding_payments": "0.00",
                        "total_remaining_principal": "733967.82",
                    },
                ),
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_account_closure_correctly_closes_account_and_emits_notification(self):
        start = default_start_date
        first_due_amount_calculation = datetime(2020, 2, 11, 0, 1, tzinfo=ZoneInfo("UTC"))
        second_due_amount_calculation = first_due_amount_calculation + relativedelta(months=1)
        end = second_due_amount_calculation + relativedelta(days=1, seconds=1)

        instance_params = parameters.default_instance.copy()
        instance_params[home_loan_redraw.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT] = "2"

        sub_tests = [
            SubTest(
                description="Check due amounts at first due calculation",
                expected_balances_at_ts={
                    first_due_amount_calculation: {
                        accounts.HOME_LOAN_REDRAW: [
                            (dimensions.PRINCIPAL, Decimal("400358.63")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.EMI, Decimal("401000.28")),
                            (dimensions.PRINCIPAL_DUE, Decimal("399641.37")),
                            (dimensions.INTEREST_DUE, Decimal("1621.92")),
                            (dimensions.REDRAW, Decimal("0")),
                        ]
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_due_amount_calculation],
                        event_id="DUE_AMOUNT_CALCULATION",
                        account_id=self.account_id_base,
                    )
                ],
            ),
            SubTest(
                description="Make first payment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="401263.29",
                        event_datetime=first_due_amount_calculation + relativedelta(seconds=1),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.INTERNAL,
                        denomination=self.default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    first_due_amount_calculation
                    + relativedelta(seconds=1): {
                        self.account_id_base: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("400358.63")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.EMI, Decimal("401000.28")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.REDRAW, Decimal("0")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Check due amounts at second due calculation",
                expected_balances_at_ts={
                    second_due_amount_calculation: {
                        accounts.HOME_LOAN_REDRAW: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.EMI, Decimal("401000.28")),
                            (dimensions.PRINCIPAL_DUE, Decimal("400358.63")),
                            (dimensions.INTEREST_DUE, Decimal("636.19")),
                            (dimensions.REDRAW, Decimal("0")),
                        ]
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[second_due_amount_calculation],
                        event_id="DUE_AMOUNT_CALCULATION",
                        account_id=self.account_id_base,
                    )
                ],
            ),
            SubTest(
                description="Make second and final payment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="400994.82",
                        event_datetime=second_due_amount_calculation + relativedelta(seconds=1),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.INTERNAL,
                        denomination=self.default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    second_due_amount_calculation
                    + relativedelta(seconds=1): {
                        self.account_id_base: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.EMI, Decimal("401000.28")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.REDRAW, Decimal("0")),
                        ],
                    }
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=second_due_amount_calculation + relativedelta(seconds=1),
                        notification_type=HOME_LOAN_REDRAW_PAID_OFF,
                        notification_details={"account_id": f"{self.account_id_base}"},
                        resource_id=f"{self.account_id_base}",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
                expected_derived_parameters=get_expected_derived_parameters(
                    timestamp=second_due_amount_calculation + relativedelta(days=1),
                    account_id=accounts.HOME_LOAN_REDRAW,
                    expected_parameters={
                        "available_redraw_funds": "0.00",
                        "next_repayment_date": "2020-04-11",
                        "remaining_term": "0",
                        "total_outstanding_debt": "0.00",
                        "total_outstanding_payments": "0.00",
                        "total_remaining_principal": "0.00",
                    },
                ),
            ),
            SubTest(
                description="Close the account",
                events=[
                    update_account_status_pending_closure(
                        timestamp=end,
                        account_id=self.account_id_base,
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        self.account_id_base: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.EMI, Decimal("0")),
                            (dimensions.REDRAW, Decimal("0")),
                            (dimensions.INTERNAL_CONTRA, Decimal("0")),
                        ],
                    }
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params
        )
        self.run_test_scenario(test_scenario)

    def test_account_closure_gets_rejected_when_debt_not_repaid(self):
        start = default_start_date
        first_due_amount_calculation = datetime(2020, 2, 11, 0, 1, tzinfo=ZoneInfo("UTC"))
        end = first_due_amount_calculation + relativedelta(days=1, seconds=3)

        sub_tests = [
            SubTest(
                description="Make one payment and close account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="401263.30",
                        event_datetime=first_due_amount_calculation + relativedelta(seconds=1),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.INTERNAL,
                        denomination=self.default_denomination,
                    ),
                ],
            ),
            SubTest(
                description="Close the account",
                events=[
                    update_account_status_pending_closure(
                        timestamp=first_due_amount_calculation + relativedelta(day=1),
                        account_id=self.account_id_base,
                    ),
                ],
            ),
        ]

        instance_params = parameters.default_instance.copy()
        instance_params["total_repayment_count"] = "3"
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params
        )
        expected_error = ValueError(
            {
                "grpc_code": 3,
                "http_code": 400,
                "message": "The loan cannot be closed until all outstanding debt is repaid",
                "http_status": "Bad Request",
            }
        )
        self.run_test_scenario(test_scenario, expected_simulation_error=expected_error)

    def test_account_closure_gets_rejected_when_overpaid_debt_and_redraw_nil(self):
        start = default_start_date
        first_due_amount_calculation = datetime(2020, 2, 11, 0, 1, tzinfo=ZoneInfo("UTC"))
        end = first_due_amount_calculation + relativedelta(seconds=3)

        sub_tests = [
            SubTest(
                description="Make first payment for total outstanding debt",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="801621.92",
                        event_datetime=first_due_amount_calculation + relativedelta(seconds=1),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.INTERNAL,
                        denomination=self.default_denomination,
                    )
                ],
            ),
            # Skip Second payment and try to close the account.
            SubTest(
                description="Close the account",
                events=[
                    update_account_status_pending_closure(
                        timestamp=end,
                        account_id=self.account_id_base,
                    ),
                ],
            ),
        ]
        instance_params = parameters.default_instance.copy()
        instance_params["total_repayment_count"] = "3"
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params
        )
        expected_error = ValueError(
            {
                "grpc_code": 3,
                "http_code": 400,
                "message": "The loan cannot be closed until all outstanding debt is repaid",
                "http_status": "Bad Request",
            }
        )
        self.run_test_scenario(test_scenario, expected_simulation_error=expected_error)

    def test_account_opening_date_before_repayment_date_minimum_month_delay(self):
        start = default_start_date
        end = start + relativedelta(seconds=2)
        test_case = SubTest(
            description="opening date before repayment date",
            expected_derived_parameters=get_expected_derived_parameters(
                timestamp=start + relativedelta(seconds=1),
                account_id=accounts.HOME_LOAN_REDRAW,
                expected_parameters={
                    "next_repayment_date": "2020-02-11",
                },
            ),
        )
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=[test_case]
        )
        self.run_test_scenario(test_scenario)

    def test_account_opening_date_on_repayment_date_minimum_month_delay(self):
        # Account opening date : 2020-01-11
        start = default_start_date + relativedelta(days=6)
        end = start + relativedelta(seconds=2)
        test_case = SubTest(
            description="opening date on repayment date",
            expected_derived_parameters=get_expected_derived_parameters(
                timestamp=start + relativedelta(seconds=1),
                account_id=accounts.HOME_LOAN_REDRAW,
                expected_parameters={
                    "next_repayment_date": "2020-02-11",
                },
            ),
        )
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=[test_case]
        )
        self.run_test_scenario(test_scenario)

    def test_account_opening_date_after_repayment_date_minimum_month_delay(self):
        # Account opening date : 2020-01-12
        start = default_start_date + relativedelta(days=7)
        end = start + relativedelta(seconds=2)
        test_case = SubTest(
            description="opening date after repayment date",
            expected_derived_parameters=get_expected_derived_parameters(
                timestamp=start + relativedelta(seconds=1),
                account_id=accounts.HOME_LOAN_REDRAW,
                expected_parameters={
                    "next_repayment_date": "2020-03-11",
                },
            ),
        )
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=[test_case]
        )
        self.run_test_scenario(test_scenario)

    def test_pre_posting_hook_accepts_and_rejects_postings(self):
        start = default_start_date
        end = start + relativedelta(minutes=6)

        sub_tests = [
            SubTest(
                description="Force override accepts 'invalid' postings",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(minutes=4),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.DEPOSIT,
                        denomination="USD",
                        instruction_details={"force_override": "true"},
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(minutes=4): {
                        self.account_id_base: [
                            (BalanceDimensions(denomination="USD"), Decimal("-1000")),
                        ]
                    },
                },
            ),
            SubTest(
                description="Posting with wrong denomination is rejected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start,
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.DEPOSIT,
                        denomination="USD",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start,
                        rejection_type="WrongDenomination",
                        rejection_reason="Cannot make transactions in the given denomination, "
                        f"transactions must be one of ['{self.default_denomination}']",
                        account_id=self.account_id_base,
                    )
                ],
            ),
            SubTest(
                description="Non-settlement posting is rejected",
                events=[
                    create_inbound_authorisation_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(minutes=1),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.DEPOSIT,
                        denomination=self.default_denomination,
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(minutes=1),
                        rejection_type="Custom",
                        rejection_reason="Only batches with a single hard settlement or transfer "
                        "posting are supported",
                        account_id=self.account_id_base,
                    )
                ],
            ),
            SubTest(
                description="Multiple inbound hard settlements are rejected",
                events=[
                    create_posting_instruction_batch(
                        event_datetime=start + relativedelta(minutes=3),
                        instructions=[
                            InboundHardSettlement(
                                amount="1000",
                                target_account_id=self.account_id_base,
                                internal_account_id=accounts.DEPOSIT,
                                denomination=self.default_denomination,
                            ),
                            InboundHardSettlement(
                                amount="2000",
                                target_account_id=self.account_id_base,
                                internal_account_id=accounts.DEPOSIT,
                                denomination=self.default_denomination,
                            ),
                        ],
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(minutes=3),
                        rejection_type="Custom",
                        rejection_reason="Only batches with a single hard settlement or transfer "
                        "posting are supported",
                        account_id=self.account_id_base,
                    )
                ],
            ),
            SubTest(
                description="Withdrawal greater than the available redraw funds is rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(minutes=3),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.DEPOSIT,
                        denomination=self.default_denomination,
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(minutes=3),
                        rejection_type="InsufficientFunds",
                        rejection_reason="Transaction amount 1000 AUD is greater than the "
                        "available redraw funds of 0 AUD.",
                        account_id=self.account_id_base,
                    )
                ],
            ),
            SubTest(
                description="Payment greater than the total outstanding debt is rejected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="900000",
                        event_datetime=start + relativedelta(minutes=4),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.DEPOSIT,
                        denomination=self.default_denomination,
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(minutes=4),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Cannot make a payment of 900000 AUD "
                        "greater than the net difference of the total outstanding debt of "
                        "800000.00 AUD and the remaining redraw balance of 0.00 AUD.",
                        account_id=self.account_id_base,
                    )
                ],
            ),
            SubTest(
                description="Valid overpayment is accepted and put into the redraw balance",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(minutes=5),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.DEPOSIT,
                        denomination=self.default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(minutes=5): {
                        self.account_id_base: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.REDRAW, Decimal("-1000")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("799000"))],
                    },
                },
            ),
            SubTest(
                description="Valid withdrawal is accepted and returned from redraw funds",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(minutes=6),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.DEPOSIT,
                        denomination=self.default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(minutes=6): {
                        self.account_id_base: [
                            # This redraws the previous overpayment from the subtest above
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.REDRAW, Decimal("0")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("800000"))],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, debug=True
        )
        self.run_test_scenario(test_scenario)

    def test_post_posting_hook_correctly_redistributes_repayments(self):
        start = default_start_date
        first_due_amount_calculation = datetime(2020, 2, 11, 0, 1, tzinfo=ZoneInfo("UTC"))
        end = first_due_amount_calculation + relativedelta(minutes=8)

        sub_tests = [
            SubTest(
                description="Principal due is paid off before interest due on a partial repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=first_due_amount_calculation + relativedelta(minutes=4),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.DEPOSIT,
                        denomination=self.default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    first_due_amount_calculation
                    + relativedelta(minutes=4): {
                        # Repaying 1000 - Principal due amount is 66032.18,
                        # so new principal due amt is = 66032.18 - 1000 = 65032.18
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, Decimal("733967.82")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.EMI, Decimal("67391.09")),
                            (dimensions.PRINCIPAL_DUE, Decimal("65032.18")),
                            (dimensions.INTEREST_DUE, Decimal("1621.92")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("799000"))],
                    },
                },
            ),
            SubTest(
                description="Pay of all principal due and some interest due on a partial repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="66032.18",
                        event_datetime=first_due_amount_calculation + relativedelta(minutes=5),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.DEPOSIT,
                        denomination=self.default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    first_due_amount_calculation
                    + relativedelta(minutes=5): {
                        # Repaying 65032.18 (all of the principal due from test before) + 1000
                        # So 1000 of the 1621.92 gets paid back
                        # Therefore the new interest due amount is 1621.92 - 1000 = 621.92
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, Decimal("733967.82")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.EMI, Decimal("67391.09")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("621.92")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("732967.82"))],
                    },
                },
            ),
            SubTest(
                description="Pay of all due balances for a full repayment",
                events=[
                    # Repaying the remaining 621.92 of the interest due from the test before
                    create_inbound_hard_settlement_instruction(
                        amount="621.92",
                        event_datetime=first_due_amount_calculation + relativedelta(minutes=6),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.DEPOSIT,
                        denomination=self.default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    first_due_amount_calculation
                    + relativedelta(minutes=6): {
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, Decimal("733967.82")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.EMI, Decimal("67391.09")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("732345.90"))],
                    },
                },
            ),
            SubTest(
                description="Overpayment should be put into the redraw balance",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=first_due_amount_calculation + relativedelta(minutes=7),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.DEPOSIT,
                        denomination=self.default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    first_due_amount_calculation
                    + relativedelta(minutes=7): {
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, Decimal("733967.82")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.EMI, Decimal("67391.09")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.REDRAW, Decimal("-150")),
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("732195.90"))],
                    },
                },
            ),
            SubTest(
                description="Withdrawal should move funds from the redraw balance "
                "to the deposit account",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=first_due_amount_calculation + relativedelta(minutes=8),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.DEPOSIT,
                        denomination=self.default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    first_due_amount_calculation
                    + relativedelta(minutes=8): {
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, Decimal("733967.82")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.EMI, Decimal("67391.09")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.REDRAW, Decimal("-50")),
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("732295.90"))],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, debug=True
        )
        self.run_test_scenario(test_scenario)

    def test_schedules_are_preserved_after_conversion(self):
        """
        Test ~ a month's worth of schedules running as expected after two account conversions:
        - the first on account opening day
        - the second at mid month
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=2, day=2, tzinfo=ZoneInfo("UTC"))

        instance_params = parameters.default_instance.copy()
        instance_params["due_amount_calculation_day"] = "1"
        template_params = parameters.default_template.copy()

        # Get accrue interest schedules
        run_times_accrue_interest = []
        accrue_interest_date = start
        accrue_interest_date = accrue_interest_date.replace(
            hour=int(template_params["interest_accrual_hour"]),
            minute=int(template_params["interest_accrual_minute"]),
            second=int(template_params["interest_accrual_second"]),
        )
        run_times_accrue_interest.append(accrue_interest_date)
        for _ in range(32):
            accrue_interest_date = accrue_interest_date + relativedelta(days=1)
            run_times_accrue_interest.append(accrue_interest_date)

        first_application_date = (start + relativedelta(months=1)).replace(
            day=int(instance_params["due_amount_calculation_day"]),
            hour=int(template_params["due_amount_calculation_hour"]),
            minute=int(template_params["due_amount_calculation_minute"]),
            second=int(template_params["due_amount_calculation_second"]),
        )

        conversion_1 = start + relativedelta(hours=1)
        convert_to_version_id_1 = "5"
        convert_to_contract_config_1 = ContractConfig(
            contract_content=self.smart_contract_path_to_content[files.HOME_LOAN_REDRAW_CONTRACT],
            smart_contract_version_id=convert_to_version_id_1,
            template_params=template_params,
            account_configs=[],
        )
        conversion_2 = conversion_1 + relativedelta(days=15)
        convert_to_version_id_2 = "6"
        convert_to_contract_config_2 = ContractConfig(
            contract_content=self.smart_contract_path_to_content[files.HOME_LOAN_REDRAW_CONTRACT],
            smart_contract_version_id=convert_to_version_id_2,
            template_params=template_params,
            account_configs=[],
        )

        sub_tests = [
            SubTest(
                description="Trigger Conversions and Check Schedules at EoM",
                events=[
                    create_account_product_version_update_instruction(
                        timestamp=conversion_1,
                        account_id=accounts.HOME_LOAN_REDRAW,
                        product_version_id=convert_to_version_id_1,
                    ),
                    create_account_product_version_update_instruction(
                        timestamp=conversion_2,
                        account_id=accounts.HOME_LOAN_REDRAW,
                        product_version_id=convert_to_version_id_2,
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=run_times_accrue_interest,
                        event_id="ACCRUE_INTEREST",
                        account_id=accounts.HOME_LOAN_REDRAW,
                        count=33,
                    ),
                    ExpectedSchedule(
                        run_times=[first_application_date],
                        event_id="DUE_AMOUNT_CALCULATION",
                        account_id=accounts.HOME_LOAN_REDRAW,
                        count=1,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, instance_params=instance_params, sub_tests=sub_tests
        )

        self.run_test_scenario(
            test_scenario,
            smart_contracts=[convert_to_contract_config_1, convert_to_contract_config_2],
        )
