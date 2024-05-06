# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

# library
import library.mortgage.contracts.template.mortgage as mortgage
from library.mortgage.test import accounts, dimensions, files, parameters
from library.mortgage.test.simulation.common import MortgageTestBase

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

reduce_emi_template_params = {
    **parameters.mortgage_template_params,
    mortgage.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: "reduce_emi",
}


class MortgageTest(MortgageTestBase):
    def test_account_opening_principal_payment(self):
        start = self.default_simulation_start_date
        end = start + relativedelta(days=1)

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("300000")),
                            (dimensions.EMI, Decimal("25135.62")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
            )
        ]
        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_deactivation_hook_correctly_zeros_out_balances(self):
        start = self.default_simulation_start_date
        first_due_amount_calculation = start + relativedelta(months=1, day=28, minute=1)
        end = first_due_amount_calculation + relativedelta(days=1, seconds=2)

        instance_params = parameters.mortgage_instance_params.copy()
        instance_params["total_repayment_count"] = "2"

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("300000")),
                            (dimensions.EMI, Decimal("150187.53")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Check all balances before repayment",
                events=[
                    create_flag_definition_event(
                        flag_definition_id="REPAYMENT_HOLIDAY", timestamp=start
                    ),
                    create_flag_event(
                        timestamp=start,
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        effective_timestamp=start,
                        expiry_timestamp=start + relativedelta(days=10),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    first_due_amount_calculation: {
                        self.account_id_base: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("150104.27")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, Decimal("0")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("73.97")),
                            # reamortised due to repayment holiday
                            (dimensions.EMI, Decimal("150224.56")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("320.63")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("149969.70")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_due_amount_calculation + relativedelta(days=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.PARAM_TOTAL_EARLY_REPAYMENT_FEE,
                        value="7355.42",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_due_amount_calculation + relativedelta(days=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="300398.71",
                    ),
                ],
            ),
            SubTest(
                description="Make a full repayment, including overpayment to clear all debt and "
                "early repayment fees",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="307754.13",
                        event_datetime=first_due_amount_calculation
                        + relativedelta(days=1, seconds=1),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    first_due_amount_calculation
                    + relativedelta(days=1, seconds=1): {
                        self.account_id_base: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, Decimal("0")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("73.97")),
                            (dimensions.EMI, Decimal("150224.56")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("150104.27")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("4.11245")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("150104.27"),
                            ),
                            (
                                dimensions.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
                                Decimal("-147104.27"),
                            ),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                        ],
                    }
                },
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
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, Decimal("0")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("0")),
                            (dimensions.EMI, Decimal("0")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (
                                dimensions.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                        ],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params
        )
        self.run_test_scenario(test_scenario)

    def test_pre_posting_hook_rejections(self):
        start = self.default_simulation_start_date
        end = start + relativedelta(seconds=4)

        sub_tests = [
            SubTest(
                description="check wrong denomination is rejected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination="USD",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(seconds=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
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
                                target_account_id=accounts.MORTGAGE_ACCOUNT,
                                internal_account_id=accounts.INTERNAL_ACCOUNT,
                                denomination=parameters.TEST_DENOMINATION,
                            ),
                            InboundHardSettlement(
                                amount="2000",
                                target_account_id=accounts.MORTGAGE_ACCOUNT,
                                internal_account_id=accounts.INTERNAL_ACCOUNT,
                                denomination=parameters.TEST_DENOMINATION,
                            ),
                        ],
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(seconds=2),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        rejection_type="Custom",
                        rejection_reason="Only batches with a single hard settlement or transfer "
                        "posting are supported",
                    )
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_posting_accepted_for_force_override(self):
        start = self.default_simulation_start_date
        end = start + relativedelta(seconds=4)

        sub_tests = [
            SubTest(
                description="Test force override accepts postings",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        instruction_details={"force_override": "true"},
                        denomination="USD",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.USD_DEFAULT, Decimal("-1")),
                        ],
                    }
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_post_posting_fees(self):
        start = self.default_simulation_start_date
        end = start + relativedelta(seconds=4)

        sub_tests = [
            SubTest(
                description="OHS with 'fee' metadata is reflected in PENALTIES",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        instruction_details={"fee": "true"},
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.PENALTIES, Decimal("50")),
                        ],
                    }
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_post_posting_interest_adjustment(self):
        start = self.default_simulation_start_date
        first_due_amount_calculation = start + relativedelta(months=1, days=17, minutes=1)
        interest_adjustment = first_due_amount_calculation + relativedelta(seconds=1)
        end = interest_adjustment

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("300000")),
                            (dimensions.EMI, Decimal("25135.62")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="300000.00",  # sum(PRINCIPAL)
                    ),
                ],
            ),
            SubTest(
                description="Check balances at first due amount calc",
                expected_balances_at_ts={
                    first_due_amount_calculation: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("275119.17")),
                            (dimensions.EMI, Decimal("25135.62")),
                            (dimensions.INTEREST_DUE, Decimal("394.52")),
                            (dimensions.PRINCIPAL_DUE, Decimal("24880.83")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("394.52")),
                        ],
                    }
                },
            ),
            SubTest(
                description="OHS with 'interest_adjustment' metadata is reflected in INTEREST_DUE "
                "and interest is adjusted correctly",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=interest_adjustment,
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        internal_account_id=accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT,
                        instruction_details={"interest_adjustment": "true"},
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    interest_adjustment: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("275119.17")),
                            (dimensions.EMI, Decimal("25135.62")),
                            (dimensions.INTEREST_DUE, Decimal("100.00")),
                            (dimensions.PRINCIPAL_DUE, Decimal("24880.83")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("100.00")),
                        ],
                    }
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_due_amount_calculation_day_change(self):
        start = self.default_simulation_start_date
        first_due_amount_calc_datetime = start + relativedelta(
            months=1, day=12, hour=0, minute=1, second=0
        )
        second_due_amount_calc_datetime = first_due_amount_calc_datetime + relativedelta(
            months=1, day=16, hour=0, minute=1, second=0
        )
        end = second_due_amount_calc_datetime + relativedelta(seconds=4)

        instance_params = self.mortgage_instance_params.copy()
        instance_params["due_amount_calculation_day"] = "12"

        sub_tests = [
            SubTest(
                description="check parameter change before first schedule is rejected",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(seconds=2),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        due_amount_calculation_day="5",
                    )
                ],
                expected_parameter_change_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(seconds=2),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        rejection_type="AgainstTNC",
                        rejection_reason=(
                            "It is not possible to change the monthly repayment day "
                            "if the first repayment date has not passed."
                        ),
                    )
                ],
            ),
            SubTest(
                description="check parameter change after first schedule is accepted",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=first_due_amount_calc_datetime + relativedelta(days=2),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        due_amount_calculation_day="16",
                    )
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_due_amount_calc_datetime, second_due_amount_calc_datetime],
                        event_id=mortgage.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                    )
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params
        )
        self.run_test_scenario(test_scenario)

    def test_early_repayment_fee_is_calculated_as_percent_of_remaining_principal(self):
        start = self.default_simulation_start_date
        first_due_amount_calculation = start + relativedelta(months=1, day=28, minute=1)
        end = first_due_amount_calculation + relativedelta(days=1, seconds=2)

        instance_params = parameters.mortgage_instance_params.copy()
        instance_params[mortgage.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT] = "2"
        template_parameters = parameters.mortgage_template_params.copy()
        template_parameters[mortgage.PARAM_EARLY_REPAYMENT_FEE] = "-1"

        sub_tests = [
            SubTest(
                description="Check balances at the start of the mortgage",
                expected_balances_at_ts={
                    start: {
                        self.account_id_base: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.EMI, Decimal("150187.53")),
                            (dimensions.PRINCIPAL, Decimal("300000.00")),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.PARAM_DERIVED_EARLY_REPAYMENT_FEE,
                        # 5% of 300000
                        value="15000.00",
                    ),
                ],
            ),
            SubTest(
                description="Make a repayment and check the early repayment fee has decreased",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="150327.26",
                        event_datetime=first_due_amount_calculation + relativedelta(days=1),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    first_due_amount_calculation
                    + relativedelta(days=1): {
                        self.account_id_base: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.EMI, Decimal("150187.53")),
                            (dimensions.PRINCIPAL, Decimal("150067.26")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_due_amount_calculation + relativedelta(days=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.PARAM_DERIVED_EARLY_REPAYMENT_FEE,
                        # 5% of 150067.26
                        value="7503.36",
                    ),
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_parameters,
        )
        self.run_test_scenario(test_scenario)

    def test_positive_early_repayment_fee_is_used_as_a_flat_amount(self):
        start = self.default_simulation_start_date
        end = start + relativedelta(seconds=1)

        instance_params = parameters.mortgage_instance_params.copy()
        instance_params[mortgage.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT] = "2"
        template_parameters = parameters.mortgage_template_params.copy()
        template_parameters[mortgage.PARAM_EARLY_REPAYMENT_FEE] = "2050"

        sub_tests = [
            SubTest(
                description="Check balances and the early repayment fee "
                "at the start of the mortgage",
                expected_balances_at_ts={
                    start: {
                        self.account_id_base: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.EMI, Decimal("150187.53")),
                            (dimensions.PRINCIPAL, Decimal("300000.00")),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.PARAM_DERIVED_EARLY_REPAYMENT_FEE,
                        value="2050",
                    ),
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_parameters,
        )
        self.run_test_scenario(test_scenario)

    def test_early_repayment_with_fees_capitalised(self):
        start = self.default_simulation_start_date
        early_repayment_datetime = datetime(year=2020, month=4, day=28, tzinfo=ZoneInfo("UTC"))
        before_early_repayment = early_repayment_datetime - relativedelta(seconds=1)
        after_early_repayment = early_repayment_datetime + relativedelta(seconds=1)
        end = after_early_repayment

        template_parameters = parameters.mortgage_template_params.copy()
        template_parameters[mortgage.PARAM_EARLY_REPAYMENT_FEE] = "2050"
        template_parameters["capitalise_penalty_interest"] = "True"

        sub_tests = [
            SubTest(
                description="before early repayment",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_early_repayment,
                        account_id=self.account_id_base,
                        name=mortgage.PARAM_TOTAL_EARLY_REPAYMENT_FEE,
                        value="14446.36",
                    ),
                ],
                expected_balances_at_ts={
                    before_early_repayment: {
                        self.account_id_base: [
                            (dimensions.PRINCIPAL, "250202.14"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "205.6458"),
                            (dimensions.INTEREST_DUE, "218.59"),
                            (dimensions.PRINCIPAL_DUE, "24917.03"),
                            (dimensions.EMI, "25135.62"),
                            (dimensions.PENALTIES, "15"),
                            (dimensions.PRINCIPAL_OVERDUE, "24880.83"),
                            (dimensions.INTEREST_OVERDUE, "394.52"),
                            (dimensions.DEFAULT, "0"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "519.3564",
                            ),
                        ]
                    },
                },
            ),
            SubTest(
                description="Make the early repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="315799.47",
                        event_datetime=early_repayment_datetime,
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    after_early_repayment: {
                        self.account_id_base: [
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.EMI, "25135.62"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.DEFAULT, "0"),
                            (dimensions.OVERPAYMENT, "250202.14"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "0",
                            ),
                        ]
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=parameters.mortgage_instance_params,
            template_params=template_parameters,
        )
        self.run_test_scenario(test_scenario)

    def test_early_full_repayment_with_flat_fee(self):
        start = self.default_simulation_start_date
        end = start + relativedelta(seconds=3)

        template_parameters = parameters.mortgage_template_params.copy()
        template_parameters[mortgage.PARAM_EARLY_REPAYMENT_FEE] = "2050"

        sub_tests = [
            SubTest(
                description="Check the early repayment fee amount at the start of the loan",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.PARAM_TOTAL_EARLY_REPAYMENT_FEE,
                        # early repayment fee + overpayment allowance fee
                        # since the overpayment allowance is 1%, and the overpayment
                        # allowance percentage fee is 5%, and 300,000 is being overpaid,
                        # the overpayment allowance fee is
                        # (300,000 - (.01 * 300,000)) * .05 = 14850
                        # so 2050 + 14850 = 16900
                        value="16900.00",
                    ),
                ],
            ),
            SubTest(
                description="Attempt to pay with a fee less than the early repayment fee",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="302000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(seconds=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Cannot pay more than is owed. To repay the full "
                        "amount of the mortgage - including fees - a posting for "
                        "316900.00 GBP must be made.",
                    )
                ],
            ),
            SubTest(
                description="Repay the mortgage in full",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # 300000 + 16900.00
                        amount="316900.00",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        self.account_id_base: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("300000")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("300000"),
                            ),
                            (
                                dimensions.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
                                Decimal("-297000"),
                            ),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        accounts.INTERNAL_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("16900"))
                        ],
                    }
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(seconds=2),
                        notification_type="MORTGAGE_CLOSURE",
                        notification_details={
                            "account_id": accounts.MORTGAGE_ACCOUNT,
                        },
                        resource_id=f"{accounts.MORTGAGE_ACCOUNT}",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=parameters.mortgage_instance_params,
            template_params=template_parameters,
        )
        self.run_test_scenario(test_scenario)

    def test_early_full_repayment_with_percentage_fee(self):
        start = self.default_simulation_start_date
        end = start + relativedelta(seconds=2)

        template_parameters = parameters.mortgage_template_params.copy()
        # the fee will be calculated as the
        # overpayment allowance fee percentage * remaining principal
        # so 300,000 * .05 = 15,000
        template_parameters[mortgage.PARAM_EARLY_REPAYMENT_FEE] = "-1"

        sub_tests = [
            SubTest(
                description="Check the early repayment fee amount at the start of the loan",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.PARAM_TOTAL_EARLY_REPAYMENT_FEE,
                        # early repayment fee + overpayment allowance fee
                        # since the overpayment allowance is 1%, and the overpayment
                        # allowance percentage fee is 5%, and 300,000 is being overpaid,
                        # the overpayment allowance fee is
                        # (300,000 - (.01 * 300,000)) * .05 = 14850
                        # so 15,000 + 14,850 = 29850.00
                        value="29850.00",
                    ),
                ],
            ),
            SubTest(
                description="Repay the mortgage in full",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # 300000 + 29850.00
                        amount="329850.00",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        self.account_id_base: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("300000")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("300000"),
                            ),
                            (
                                dimensions.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
                                Decimal("-297000"),
                            ),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        accounts.INTERNAL_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("29850"))
                        ],
                    }
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(seconds=1),
                        notification_type="MORTGAGE_CLOSURE",
                        notification_details={
                            "account_id": accounts.MORTGAGE_ACCOUNT,
                        },
                        resource_id=f"{accounts.MORTGAGE_ACCOUNT}",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=parameters.mortgage_instance_params,
            template_params=template_parameters,
        )
        self.run_test_scenario(test_scenario)

    def test_repaying_after_mortgage_term_ends_does_not_incur_early_repayment_fee(self):
        start = self.default_simulation_start_date
        last_due_amount_calculation = start + relativedelta(months=2, day=28, minute=1)
        end = last_due_amount_calculation + relativedelta(days=1, seconds=2)

        instance_params = parameters.mortgage_instance_params.copy()
        instance_params[mortgage.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT] = "2"
        template_parameters = parameters.mortgage_template_params.copy()
        template_parameters[mortgage.PARAM_EARLY_REPAYMENT_FEE] = "50"

        sub_tests = [
            SubTest(
                description="Check balances at the start of the mortgage",
                expected_balances_at_ts={
                    start: {
                        self.account_id_base: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.EMI, Decimal("150187.53")),
                            (dimensions.PRINCIPAL, Decimal("300000.00")),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.PARAM_DERIVED_EARLY_REPAYMENT_FEE,
                        value="50",
                    ),
                ],
            ),
            SubTest(
                description="Check balances after final due amount calculation",
                expected_balances_at_ts={
                    last_due_amount_calculation
                    + relativedelta(days=1): {
                        self.account_id_base: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("150067.26")),
                            (dimensions.INTEREST_DUE, Decimal("119.23")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("149932.74")),
                            (dimensions.INTEREST_OVERDUE, Decimal("394.52")),
                            (dimensions.PENALTIES, Decimal("117.96")),
                        ],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=last_due_amount_calculation + relativedelta(days=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        # This is the sum of all the balance addresses in the
                        # expected balance check above
                        value="300631.71",
                    ),
                ],
            ),
            SubTest(
                description="Repay the mortgage in full",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="300631.71",
                        event_datetime=last_due_amount_calculation
                        + relativedelta(days=1, seconds=1),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    last_due_amount_calculation
                    + relativedelta(days=1, seconds=1): {
                        self.account_id_base: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                    }
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=last_due_amount_calculation + relativedelta(days=1, seconds=1),
                        notification_type="MORTGAGE_CLOSURE",
                        notification_details={
                            "account_id": accounts.MORTGAGE_ACCOUNT,
                        },
                        resource_id=f"{accounts.MORTGAGE_ACCOUNT}",
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
            template_params=template_parameters,
        )
        self.run_test_scenario(test_scenario)

    def test_cannot_repay_exact_mortgage_amount_with_early_repayment_fee_set(self):
        start = self.default_simulation_start_date
        last_due_amount_calculation = start + relativedelta(months=2, day=28, minute=1)
        end = last_due_amount_calculation + relativedelta(days=1, seconds=2)

        instance_params = parameters.mortgage_instance_params.copy()
        instance_params[mortgage.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT] = "2"
        template_parameters = parameters.mortgage_template_params.copy()
        template_parameters[mortgage.PARAM_EARLY_REPAYMENT_FEE] = "50"

        sub_tests = [
            SubTest(
                description="Check balances at the start of the mortgage",
                expected_balances_at_ts={
                    start: {
                        self.account_id_base: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.EMI, Decimal("150187.53")),
                            (dimensions.PRINCIPAL, Decimal("300000.00")),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.PARAM_DERIVED_EARLY_REPAYMENT_FEE,
                        value="50",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.PARAM_TOTAL_EARLY_REPAYMENT_FEE,
                        value="14900.00",
                    ),
                ],
            ),
            SubTest(
                description="Repay the total outstanding debt without repayment fees",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="300000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=self.account_id_base,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(seconds=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Cannot pay more than is owed. To repay the full "
                        "amount of the mortgage - including fees - a posting for "
                        "314900.00 GBP must be made.",
                    )
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_parameters,
        )
        self.run_test_scenario(test_scenario)

    def test_overpayment_trackers(self):
        start = self.default_simulation_start_date
        # make sure we test on both fixed and variable rates
        instance_params = self.mortgage_instance_params.copy()
        instance_params["fixed_interest_term"] = "2"
        due_amount_calc_1 = start + relativedelta(months=1, day=28, minutes=1)
        due_amount_calc_2 = due_amount_calc_1 + relativedelta(months=1)
        accrual_after_due_amount_calc_2 = due_amount_calc_2 + relativedelta(days=1)
        overpayment_1 = due_amount_calc_1 + relativedelta(minutes=1)
        accrual_after_overpayment = overpayment_1 + relativedelta(
            days=1, hour=0, minute=0, second=1
        )
        end = accrual_after_due_amount_calc_2

        emi = Decimal("25135.62")

        sub_tests = [
            SubTest(
                description="Expected interest matches actual interest without overpayments",
                expected_balances_at_ts={
                    due_amount_calc_1
                    - relativedelta(seconds=1): {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("300000")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("394.52112")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("394.52112")),
                            (dimensions.EMI, emi),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
            ),
            SubTest(
                description="Expected interest reset at first due amount calc",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("275119.17")),
                            (dimensions.PRINCIPAL_DUE, Decimal("24880.83")),
                            (dimensions.INTEREST_DUE, Decimal("394.52")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                            # no change to excess as actual and expected interest are identical
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (dimensions.EMI, emi),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
            ),
            SubTest(
                description="Expected and actual interest diverge after overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount=str(emi + Decimal("1139.73")),
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        event_datetime=overpayment_1,
                    )
                ],
                expected_balances_at_ts={
                    accrual_after_overpayment: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("274119.17")),
                            # there is non-emi interest to repay
                            (dimensions.OVERPAYMENT, Decimal("1000")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            # accrues on 274119.17
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("7.51013")),
                            # accrues on 274119.17 + 1000 (removes overpayment impact)
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("7.53752")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (dimensions.EMI, emi),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
            ),
            SubTest(
                description="EMI Principal Excess set at due amount calculation",
                expected_balances_at_ts={
                    due_amount_calc_2
                    - relativedelta(seconds=1): {
                        accounts.MORTGAGE_ACCOUNT: [
                            # 29 accruals of 7.51011
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("217.79377")),
                            # 29 accruals of 7.53751
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("218.58808")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    },
                    due_amount_calc_2: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("249201.34")),
                            (dimensions.OVERPAYMENT, Decimal("1000")),
                            (dimensions.PRINCIPAL_DUE, Decimal("24917.83")),
                            (dimensions.INTEREST_DUE, Decimal("217.79")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                            # rounded expected: 218.59 rounded actual: 217.79
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0.8")),
                            (dimensions.EMI, emi),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    },
                },
            ),
            SubTest(
                description="Expected and actual interest continue to diverge after "
                "fixed-to-variable transition",
                expected_balances_at_ts={
                    accrual_after_due_amount_calc_2: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("249201.34")),
                            (dimensions.OVERPAYMENT, Decimal("1000")),
                            (dimensions.PRINCIPAL_DUE, Decimal("24917.830")),
                            (dimensions.INTEREST_DUE, Decimal("217.79")),
                            # round(round((0.032-0.001) / 365, 10) * 249201.45, 5)
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("21.16504")),
                            # round(round((0.032-0.001) / 365, 10) * (249201.45 + 1000 + 0.8), 5)
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("21.25004")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0.8")),
                            (dimensions.EMI, emi),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params
        )

        self.run_test_scenario(test_scenario)

    def test_overpayment_allowance(self):
        instance_params = {
            **parameters.mortgage_instance_params,
            # due_amount_calculation_day is same day as start day
            "due_amount_calculation_day": "11",
            # increasing count to check a year under and a year over allowances but
            # test only uses first 2 years
            "total_repayment_count": "36",
        }

        template_params = {
            **parameters.mortgage_template_params,
            "early_repayment_fee": "50",
        }

        start = self.default_simulation_start_date
        due_amount_calc_1 = start + relativedelta(months=1, days=1, minutes=1)
        repayment_1 = due_amount_calc_1 + relativedelta(minutes=10)
        repayment_2 = repayment_1 + relativedelta(months=1)
        end_of_year_1 = start + relativedelta(years=1)
        end_of_year_2 = start + relativedelta(years=2)
        allowance_check_year_1 = start + relativedelta(years=1, minutes=3)
        allowance_check_year_2 = start + relativedelta(years=2, minutes=3)
        end = start + relativedelta(years=2, days=1, hours=1)
        emi = Decimal("8462.43")
        # Mortgage reamortises after year 1 due to fixed to variable rate change
        emi_after_reamortisation = Decimal("8648.28")

        sub_tests = [
            SubTest(
                description="Overpayment allowance initialised on account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("300000")),
                            (dimensions.EMI, emi),
                            (dimensions.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER, "3000"),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_REMAINING,
                        value="3000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_USED,
                        value="0",
                    ),
                ],
            ),
            SubTest(
                description="Overpayment allowance unchanged after due amount calc",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("291792.36")),
                            (dimensions.PRINCIPAL_DUE, Decimal("8207.64")),
                            (dimensions.INTEREST_DUE, Decimal("254.79")),
                            (dimensions.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER, "3000"),
                            (dimensions.EMI, emi),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_1,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_REMAINING,
                        value="3000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_1,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_USED,
                        value="0",
                    ),
                ],
            ),
            SubTest(
                description="Regular payment does not affect the allowance",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount=str(emi),
                        event_datetime=repayment_1,
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    repayment_1: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("291792.36")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER, "3000"),
                            (dimensions.EMI, emi),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=repayment_1,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_REMAINING,
                        value="3000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=repayment_1,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_USED,
                        value="0",
                    ),
                ],
            ),
            SubTest(
                description="Overpayment consumes the allowance",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount=str(emi + Decimal("500")),
                        event_datetime=repayment_2,
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    repayment_2: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("283061.77")),
                            (dimensions.OVERPAYMENT, Decimal("500")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER, "2500"),
                            (dimensions.EMI, emi),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=repayment_2,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_REMAINING,
                        value="2500.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=repayment_2,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_USED,
                        value="500",
                    ),
                ],
            ),
            SubTest(
                description="Repeated overpayments consume the allowance",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount=str(emi + Decimal("500")),
                        event_datetime=repayment_2 + relativedelta(months=month_offset),
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                    )
                    # this provides 10 repayments on top of the 2 before
                    for month_offset in range(1, 11)
                ],
                # the 12th overpayment of 500 technically happens in the next year
                expected_balances_at_ts={
                    end_of_year_1: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("204269.70")),
                            (dimensions.OVERPAYMENT, Decimal("5000")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER, "-2000"),
                            (dimensions.EMI, emi),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=end_of_year_1,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_REMAINING,
                        value="-2000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=end_of_year_1,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_USED,
                        value="5000",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=end_of_year_1,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_FEE,
                        value="100.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=end_of_year_1,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="204437.61",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=end_of_year_1,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.PARAM_TOTAL_EARLY_REPAYMENT_FEE,
                        # early repayment fee + overpayment allowance fee
                        # since the overpayment allowance percentage fee is 5%, and
                        # 204437.61 would be overpaid, to fully pay off the mortgage,
                        # the overpayment allowance fee is (2000 + 204437.61) * .05 = 10321.88
                        # so 50 + 10321.88 = 10371.88
                        value="10371.88",
                    ),
                ],
            ),
            SubTest(
                description="Allowance check charges fee",
                expected_balances_at_ts={
                    allowance_check_year_1: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("195980.77")),
                            (dimensions.OVERPAYMENT, Decimal("5000")),
                            # 5% of the 2000 excess overpayment
                            (dimensions.PENALTIES, Decimal("100")),
                            (dimensions.PRINCIPAL_DUE, Decimal("8288.93")),
                            (dimensions.INTEREST_DUE, Decimal("173.5")),
                            (
                                dimensions.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
                                Decimal("2042.70"),
                            ),
                            (dimensions.EMI, emi),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                        accounts.INTERNAL_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("100"))
                        ],
                    },
                },
                expected_derived_parameters=[
                    # the parameters have now reset
                    ExpectedDerivedParameter(
                        timestamp=allowance_check_year_1,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_REMAINING,
                        value="2042.70",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=allowance_check_year_1,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_USED,
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=allowance_check_year_1,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_FEE,
                        value="0",
                    ),
                ],
            ),
            SubTest(
                description="Repeated overpayments consume the allowance (year 2)",
                events=[
                    # 12 additional repayments, each with 100 overpayment, resuming from repayment
                    # 13, as we created 12 repayments beforehand
                    create_inbound_hard_settlement_instruction(
                        amount=str(emi_after_reamortisation + Decimal("100")),
                        event_datetime=repayment_2 + relativedelta(months=10 + month_offset),
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                    )
                    for month_offset in range(1, 12)
                ],
                expected_balances_at_ts={
                    end_of_year_2: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("103714.96")),
                            # 5000 from first year + 1600 overpayment - 100 penalties repaid
                            (dimensions.OVERPAYMENT, Decimal("6500")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER, Decimal("542.70")),
                            (dimensions.EMI, emi_after_reamortisation),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=end_of_year_2,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_REMAINING,
                        value="542.70",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=end_of_year_2,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_USED,
                        value="1500",
                    ),
                ],
            ),
            SubTest(
                description="Allowance check doesn't charge fee",
                expected_balances_at_ts={
                    allowance_check_year_2: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("95339.76")),
                            (dimensions.OVERPAYMENT, Decimal("6500.00")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("8375.20")),
                            (dimensions.INTEREST_DUE, Decimal("273.08")),
                            (
                                dimensions.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
                                Decimal("1037.15"),
                            ),
                            (dimensions.EMI, emi_after_reamortisation),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                        accounts.INTERNAL_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("100.00"))
                        ],
                    },
                },
                expected_derived_parameters=[
                    # the parameters have now reset
                    ExpectedDerivedParameter(
                        timestamp=allowance_check_year_2,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_REMAINING,
                        value="1037.15",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=allowance_check_year_2,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_USED,
                        value="0",
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

    def test_overpayment_reamortisation_with_reduce_emi(self):
        start = self.default_simulation_start_date
        template_parameters = reduce_emi_template_params
        due_amount_calc_1 = start + relativedelta(months=1, day=28, minutes=1)
        due_amount_calc_2 = due_amount_calc_1 + relativedelta(months=1)
        due_amount_calc_3 = due_amount_calc_2 + relativedelta(months=1)
        due_amount_calc_4 = due_amount_calc_3 + relativedelta(months=1)
        overpayment_1 = due_amount_calc_1 + relativedelta(hours=2)
        overpayment_2 = due_amount_calc_3 + relativedelta(hours=2)

        end = due_amount_calc_4 + relativedelta(hours=1)

        sub_tests = [
            SubTest(
                description="No re-amortisation on first due amount calc",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("275119.17")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.PRINCIPAL_DUE, Decimal("24880.83")),
                            (dimensions.INTEREST_DUE, Decimal("394.52")),
                            (dimensions.EMI, Decimal("25135.62")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Re-amortisation on second due amount calc due to overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # EMI + extra interest + overpayment
                        amount=str(Decimal("25275.35") + Decimal("10000")),
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        event_datetime=overpayment_1,
                    )
                ],
                expected_balances_at_ts={
                    overpayment_1: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("265119.17")),
                            (dimensions.OVERPAYMENT, Decimal("10000")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("10000"),
                            ),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            # EMI unchanged until due amount calculation runs
                            (dimensions.EMI, Decimal("25135.62")),
                        ],
                    },
                    due_amount_calc_2: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("241107.39")),
                            (dimensions.OVERPAYMENT, Decimal("10000")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.PRINCIPAL_DUE, Decimal("24011.78")),
                            (dimensions.INTEREST_DUE, Decimal("210.64")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("7.95")),
                            # Reamortising using 265956.75 principal and 11 remaining terms
                            # (including current term)
                            (dimensions.EMI, Decimal("24222.42")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    },
                },
            ),
            SubTest(
                description="No re-amortisation on third due amount calc after normal repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="24222.42",
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        event_datetime=due_amount_calc_2 + relativedelta(minutes=2),
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_3: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("217089.75")),
                            (dimensions.OVERPAYMENT, Decimal("10000")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.PRINCIPAL_DUE, Decimal("24017.64")),
                            (dimensions.INTEREST_DUE, Decimal("204.78")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("16.45")),
                            (dimensions.EMI, Decimal("24222.42")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    },
                },
            ),
            SubTest(
                description="Re-amortisation on fourth due amount calc due to overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # EMI + overpayment
                        amount=str(Decimal("24222.42") + Decimal("5000")),
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        event_datetime=overpayment_2,
                    )
                ],
                expected_balances_at_ts={
                    overpayment_2: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("212089.75")),
                            (dimensions.OVERPAYMENT, Decimal("15000")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("5000"),
                            ),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            # EMI unchanged until due amount calculation runs
                            (dimensions.EMI, Decimal("24222.42")),
                        ],
                    },
                    due_amount_calc_4: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("188600.24")),
                            (dimensions.OVERPAYMENT, Decimal("15000")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.PRINCIPAL_DUE, Decimal("23489.51")),
                            (dimensions.INTEREST_DUE, Decimal("174.32")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("28.79")),
                            # Reamortising using 212089.76 principal and 9 remaining terms
                            # (including current term)
                            (dimensions.EMI, Decimal("23663.83")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_parameters
        )
        self.run_test_scenario(test_scenario)

    def test_overpayment_no_reamortisation_with_reduce_term(self):
        start = self.default_simulation_start_date
        template_parameters = parameters.mortgage_template_params.copy()
        template_parameters[
            mortgage.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE
        ] = "reduce_term"
        due_amount_calc_1 = start + relativedelta(months=1, day=28, minutes=1)
        due_amount_calc_2 = due_amount_calc_1 + relativedelta(months=1)
        due_amount_calc_3 = due_amount_calc_2 + relativedelta(months=1)
        overpayment_1 = due_amount_calc_1 + relativedelta(hours=2)
        overpayment_2 = due_amount_calc_2 + relativedelta(hours=2)

        end = due_amount_calc_3 + relativedelta(hours=1)

        sub_tests = [
            SubTest(
                description="No re-amortisation on first due amount calc",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("275119.17")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.PRINCIPAL_DUE, Decimal("24880.83")),
                            (dimensions.INTEREST_DUE, Decimal("394.52")),
                            (dimensions.EMI, Decimal("25135.62")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Term not reduced by smaller overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # EMI + extra interest + overpayment
                        amount=str(Decimal("25275.35") + Decimal("10000")),
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        event_datetime=overpayment_1,
                    )
                ],
                expected_balances_at_ts={
                    overpayment_1: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("265119.17")),
                            (dimensions.OVERPAYMENT, Decimal("10000")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("10000"),
                            ),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.EMI, Decimal("25135.62")),
                        ],
                    },
                    due_amount_calc_2: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("240194.19")),
                            (dimensions.OVERPAYMENT, Decimal("10000")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.PRINCIPAL_DUE, Decimal("24924.98")),
                            (dimensions.INTEREST_DUE, Decimal("210.64")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("7.95")),
                            # No reamortisation despite overpayment due to preference reduce_term
                            (dimensions.EMI, Decimal("25135.62")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_2,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_REMAINING_TERM,
                        # 2 terms have elapsed and overpayment isn't sufficient to reduce
                        # remaining term count
                        value="10",
                    ),
                ],
            ),
            SubTest(
                description="Term reduces after sufficient overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # EMI + Overpayment
                        amount=str(Decimal("25135.62") + Decimal("15000")),
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        event_datetime=overpayment_2,
                    )
                ],
                expected_balances_at_ts={
                    overpayment_2: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("225194.19")),
                            (dimensions.OVERPAYMENT, Decimal("25000")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("15000"),
                            ),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.EMI, Decimal("25135.62")),
                        ],
                    },
                    due_amount_calc_3: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("200249.83")),
                            (dimensions.OVERPAYMENT, Decimal("25000")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.PRINCIPAL_DUE, Decimal("24944.36")),
                            (dimensions.INTEREST_DUE, Decimal("191.26")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("29.19")),
                            # No reamortisation despite overpayment due to preference reduce_term
                            (dimensions.EMI, Decimal("25135.62")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=overpayment_2,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_REMAINING_TERM,
                        # 2 terms have elapsed and overpayment is sufficient to reduce
                        # remaining term count by 1
                        value="9",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_3,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_REMAINING_TERM,
                        # 3 terms have elapsed and overpayment is sufficient to reduce
                        # remaining term count by 1
                        value="8",
                    ),
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_parameters
        )
        self.run_test_scenario(test_scenario)


class InterestAccrualTest(MortgageTestBase):
    # TODO: align all start dates, but this is temporary to account for INC-8065
    start_date = datetime(year=2020, month=1, day=1, tzinfo=ZoneInfo("UTC"))

    def test_interest_accrual_variable_rate(self):
        start = self.start_date
        end = start + relativedelta(months=1, days=28)
        instance_params = self.mortgage_instance_params.copy()
        instance_params["principal"] = "1000"
        instance_params["fixed_interest_term"] = "0"

        first_accrual_event = start + relativedelta(days=1, seconds=1)
        final_non_emi_accrued_interest_event = first_accrual_event + relativedelta(days=26)

        first_application_event = start + relativedelta(months=1, days=27, minutes=1)

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("1000"))],
                    }
                },
            ),
            SubTest(
                description="check balances after first accrual",
                # accrued_interest = daily_interest_rate * principal
                # (0.032 + -0.001) / 365 * 1000 = 0.08493
                expected_balances_at_ts={
                    first_accrual_event: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.08493")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
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
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
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
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.37804")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
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
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("4.92594")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-4.92594"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance after due amount event",
                expected_balances_at_ts={
                    first_application_event: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("917.90")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("4.93")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.10")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("4.93"))
                        ],
                    }
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params, debug=False
        )
        self.run_test_scenario(test_scenario)

    def test_interest_accrual_variable_rate_with_interest_rate_limits(self):
        start = self.start_date
        end = start + relativedelta(days=3, minutes=1)
        instance_params = self.mortgage_instance_params.copy()
        instance_params["principal"] = "1000"
        instance_params["fixed_interest_term"] = "0"

        template_params = self.mortgage_template_params.copy()
        template_params["annual_interest_rate_cap"] = "0.035"
        template_params["annual_interest_rate_floor"] = "0.030"

        first_accrual_event = start + relativedelta(days=1, seconds=1)
        second_accrual_event = first_accrual_event + relativedelta(days=1)
        third_accrual_event = second_accrual_event + relativedelta(days=1)

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("1000"))],
                    }
                },
            ),
            SubTest(
                description="check balances after first accrual",
                # accrued_interest = daily_interest_rate * principal
                # (0.032 + -0.001) / 365 * 1000 = 0.08493
                expected_balances_at_ts={
                    first_accrual_event: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.08493")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
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
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        variable_rate_adjustment="1.0",
                    )
                ],
                expected_balances_at_ts={
                    second_accrual_event: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.18082")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
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
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        variable_rate_adjustment="-1.0",
                    )
                ],
                expected_balances_at_ts={
                    third_accrual_event: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.26301")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
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
            instance_params=instance_params,
            debug=False,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_accrual_fixed_rate(self):
        start = self.start_date
        end = start + relativedelta(days=28, minutes=2)
        instance_params = self.mortgage_instance_params.copy()
        instance_params["principal"] = "1000"

        first_accrual_event = start + relativedelta(days=1, minutes=1)
        final_non_emi_accrued_interest_event = first_accrual_event + relativedelta(days=26)

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("83.79")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("1000"))],
                    }
                },
            ),
            SubTest(
                description="check balances after first accrual",
                # accrued_interest = daily_interest_rate * principal
                # (0.01) / 365 * 1000 = 0.08493
                expected_balances_at_ts={
                    first_accrual_event: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("83.79")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.02740")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
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
                        accounts.MORTGAGE_ACCOUNT: [
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
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("83.79")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.76720")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
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

    def test_interest_accrual_fixed_to_variable_rate(self):
        instance_params = self.mortgage_instance_params.copy()
        instance_params["principal"] = "1000"
        instance_params["fixed_interest_term"] = "1"

        start = self.start_date
        due_amount_calc_1 = start + relativedelta(months=1, day=28, minutes=1)
        due_amount_calc_2 = due_amount_calc_1 + relativedelta(months=1)
        due_amount_calc_3 = due_amount_calc_2 + relativedelta(months=1)
        end = due_amount_calc_3
        first_accrual_event = start + relativedelta(days=1, minutes=1)
        final_non_emi_accrued_interest_event = first_accrual_event + relativedelta(days=26)
        first_variable_rate_accrual_event = due_amount_calc_1 + relativedelta(days=1, minutes=1)

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("83.79")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("1000"))],
                    }
                },
            ),
            SubTest(
                description="check balances after first accrual",
                # accrued_interest = principal * daily_interest_rate
                # 1000 * 0.01 / 365 = 0.08493
                expected_balances_at_ts={
                    first_accrual_event: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("83.79")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.02740")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.02740"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance at end of non-emi accrued interest period",
                expected_balances_at_ts={
                    final_non_emi_accrued_interest_event: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("83.79")),
                            # (1000 * 0.01 / 365 = 0.02740)  * 27
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.73980")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.73980"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check first accruals after due amount calc on variable rate",
                expected_balances_at_ts={
                    first_variable_rate_accrual_event: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("917.06")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.94")),
                            (dimensions.INTEREST_DUE, Decimal("1.59")),
                            # We reamortise at the end of the cycle, so no change yet due to
                            # fixed -> variable change
                            (dimensions.EMI, Decimal("83.79")),
                            # 917.06 * (0.032-0.001) / 365
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.07789")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.07789"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check reamortisation at second due amount calculation",
                expected_balances_at_ts={
                    due_amount_calc_2
                    - relativedelta(seconds=1): {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("917.06")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.94")),
                            (dimensions.INTEREST_DUE, Decimal("1.59")),
                            (dimensions.EMI, Decimal("83.79")),
                            # 29 * 0.07789
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.25881")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-2.25881"))
                        ],
                    },
                    due_amount_calc_2: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("834.65")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.41")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("82.94")),
                            (dimensions.INTEREST_DUE, Decimal("2.26")),
                            (dimensions.INTEREST_OVERDUE, Decimal("1.59")),
                            # Reamortised on principal 917.07, remaining term 11, rate 0.031
                            (dimensions.EMI, Decimal("84.67")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    },
                },
            ),
            SubTest(
                description="no further reamortisation at third due amount calculation",
                expected_balances_at_ts={
                    due_amount_calc_3: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.EMI, Decimal("84.67")),
                        ],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params, debug=False
        )
        self.run_test_scenario(test_scenario)

    def test_interest_accrual_and_reamortisation_due_to_repayment_holiday(self):
        start = self.start_date
        end = start + relativedelta(months=3, days=4, seconds=2)
        instance_params = self.mortgage_instance_params.copy()
        instance_params["principal"] = "1000"
        # due_amount_calculation_day is same day as start day
        instance_params["due_amount_calculation_day"] = "1"
        instance_params["fixed_interest_term"] = "0"

        first_accrual_event = start + relativedelta(days=1, seconds=1)
        second_accrual_event = first_accrual_event + relativedelta(days=1)
        third_accrual_event = second_accrual_event + relativedelta(days=1)

        first_application_event = start + relativedelta(months=1, minutes=1)
        second_application_event = first_application_event + relativedelta(months=1)
        third_application_event = second_application_event + relativedelta(months=1)

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
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("1000"))],
                    }
                },
            ),
            SubTest(
                description="check correct balance after first accrual event",
                expected_balances_at_ts={
                    first_accrual_event: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.08493")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
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
                        account_id=accounts.MORTGAGE_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    second_accrual_event: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.08493")),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                Decimal("0.08493"),
                            ),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.08493"))
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.08493"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check interest is capitalised after flag expiry and daily accrual "
                "occurs on capitalised interest within the same event",
                expected_balances_at_ts={
                    third_accrual_event: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            # all the previous interest pending capitalisation is rounded and
                            # rebalanced to principal + tracker
                            (dimensions.PRINCIPAL, Decimal("1000.08")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0.08")),
                            (dimensions.EMI, Decimal("84.74")),
                            # daily accrual on 1000.08 = 0.08494
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.16987")),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, Decimal("0")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.16987"))
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0.08"))
                        ],
                    }
                },
            ),
            SubTest(
                description="Apply due/overdue blocking flag for the due amount calculation event ",
                events=[
                    create_flag_event(
                        timestamp=first_application_event - relativedelta(minutes=1),
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        effective_timestamp=first_application_event - relativedelta(minutes=1),
                        expiry_timestamp=first_application_event + relativedelta(minutes=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    first_application_event: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000.08")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0.08")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.46325")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                Decimal("0.08494"),
                            ),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-2.46325"))
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.08494"))
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0.08"))
                        ],
                    }
                },
            ),
            SubTest(
                description="No blocking flag for the second due amount calculation"
                " event moves balances to due addresses",
                expected_balances_at_ts={
                    second_application_event: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("910.29")),
                            # interest accrued at previous due amount calc was 2.46325 so
                            # 4.93-2.46 = 2.47 interest is considered to be emi
                            (dimensions.PRINCIPAL_DUE, Decimal("89.87")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0.16")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("2")),
                            # emi increased due to repayment holiday
                            (dimensions.EMI, Decimal("92.34")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("4.93")),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, Decimal("0")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0.16"))
                        ],
                    }
                },
            ),
            SubTest(
                description="No blocking flag for the third due amount calculation"
                " event moves balances to due and overdue addresses",
                expected_balances_at_ts={
                    third_application_event: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("820.35")),
                            (dimensions.PRINCIPAL_DUE, Decimal("89.94")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("89.87")),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, Decimal("0.16")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("3")),
                            (dimensions.EMI, Decimal("92.34")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            # round(0.031/365 * 912.75, 5) * 31 = 2.40312
                            (dimensions.INTEREST_DUE, Decimal("2.40")),
                            (dimensions.INTEREST_OVERDUE, Decimal("4.93")),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, Decimal("0")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0.16"))
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
        )
        self.run_test_scenario(test_scenario)

    def test_interest_accrual_with_zero_rate(self):
        start = self.start_date
        end = start + relativedelta(months=1, days=28)
        instance_params = self.mortgage_instance_params.copy()
        instance_params["principal"] = "1000"
        instance_params["fixed_interest_term"] = "12"
        instance_params["fixed_interest_rate"] = "0"

        first_accrual_event = start + relativedelta(days=1, seconds=1)
        final_non_emi_accrued_interest_event = first_accrual_event + relativedelta(days=26)

        first_application_event = start + relativedelta(months=1, days=27, minutes=1)

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("83.33")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("1000"))],
                    }
                },
            ),
            SubTest(
                description="check balances after first accrual",
                expected_balances_at_ts={
                    first_accrual_event: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("83.33")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.00")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0.00"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance at end of non-emi accrued interest period",
                expected_balances_at_ts={
                    final_non_emi_accrued_interest_event: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("83.33")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.00")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0.00"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance at start of emi accrued interest period",
                expected_balances_at_ts={
                    final_non_emi_accrued_interest_event
                    + relativedelta(days=1): {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("83.33")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.00")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0.00"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance at end of emi accrued interest period",
                expected_balances_at_ts={
                    first_application_event
                    - relativedelta(seconds=1): {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("83.33")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.00")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0.00"))
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance after due amount event",
                expected_balances_at_ts={
                    first_application_event: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("916.67")),
                            (dimensions.EMI, Decimal("83.33")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0.00")),
                            (dimensions.PRINCIPAL_DUE, Decimal("83.33")),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0.00"))
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0.00"))
                        ],
                    }
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params, debug=False
        )
        self.run_test_scenario(test_scenario)


class DueAmountCalculationTest(MortgageTestBase):
    def test_reamortisation_due_to_variable_rate_change(self):
        instance_params = parameters.mortgage_instance_params.copy()
        instance_params["due_amount_calculation_day"] = "11"
        instance_params["fixed_interest_term"] = "0"

        start = self.default_simulation_start_date

        first_due_amount_datetime = start + relativedelta(months=1, minutes=1)
        first_overpayment_datetime = first_due_amount_datetime + relativedelta(hours=1)
        second_due_amount_datetime = first_due_amount_datetime + relativedelta(months=1)
        second_overpayment_datetime = second_due_amount_datetime + relativedelta(hours=1)
        third_due_amount_datetime = second_due_amount_datetime + relativedelta(months=1)

        end = third_due_amount_datetime

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("300000")),
                            (dimensions.EMI, Decimal("25421.78")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
            ),
            SubTest(
                description="check loan is re-amortised at next due amount calculation after a "
                "variable rate adjustment",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=first_due_amount_datetime - relativedelta(seconds=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        variable_rate_adjustment="-0.01",
                    )
                ],
                expected_balances_at_ts={
                    first_due_amount_datetime
                    - relativedelta(seconds=1): {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("300000")),
                            (dimensions.EMI, Decimal("25421.78")),
                            # (0.032 + -0.001)/365 * 300000 * 31 = 789.86295
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("789.86295")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    },
                    first_due_amount_datetime: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("275490.94")),
                            # emi updated due to variable rate change with principal 300000
                            # rate 0.022 and remaining term 12
                            (dimensions.EMI, Decimal("25298.92")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("789.86")),
                            # 25298.92 - 789.86
                            (dimensions.PRINCIPAL_DUE, Decimal("24509.06")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    },
                },
            ),
            SubTest(
                description="check loan is re-amortised at due amount calculation after a "
                "variable rate adjustment, excluding overpayment impact",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # EMI + overpayment
                        amount=str(Decimal("25298.92") + Decimal("50000")),
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        event_datetime=first_overpayment_datetime,
                    ),
                    create_instance_parameter_change_event(
                        timestamp=second_due_amount_datetime - relativedelta(seconds=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        variable_rate_adjustment="-0.02",
                    ),
                ],
                expected_balances_at_ts={
                    second_due_amount_datetime
                    - relativedelta(seconds=1): {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL, Decimal("225490.94")),
                            (dimensions.OVERPAYMENT, Decimal("50000")),
                            (dimensions.EMI, Decimal("25298.92")),
                            # 29 * round(225490.94 * round(0.022/365, 10), 5) = 29 * 13.59124
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("394.14596")),
                            # 29 * round(275490.94 * round(0.022/365, 10), 5) = 29 * 16.60494
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("481.54326")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    },
                    second_due_amount_datetime: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("200689.94")),
                            (dimensions.OVERPAYMENT, Decimal("50000")),
                            # emi updated due to variable rate change with principal 275490.94
                            # rate 0.012 and remaining term 11
                            # if overpayments were considered this would be principal 225490.94
                            # and emi would be 20622.38
                            (dimensions.EMI, Decimal("25195.15")),
                            # this is not considered during reamortisation as it's set during the
                            # hook execution
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("87.39")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("394.15")),
                            # 25195.15 - 394.15
                            (dimensions.PRINCIPAL_DUE, Decimal("24801")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    },
                },
            ),
            SubTest(
                description="check loan is re-amortised at due amount calculation after a "
                "variable rate adjustment, excluding overpayment + principal excess impact ",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # EMI + overpayment
                        amount=str(Decimal("25195.15") + Decimal("50000")),
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        event_datetime=second_overpayment_datetime,
                    ),
                    create_instance_parameter_change_event(
                        timestamp=third_due_amount_datetime - relativedelta(seconds=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        variable_rate_adjustment="-0.022",
                    ),
                ],
                expected_balances_at_ts={
                    third_due_amount_datetime
                    - relativedelta(seconds=1): {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("150689.94")),
                            (dimensions.OVERPAYMENT, Decimal("100000")),
                            (dimensions.EMI, Decimal("25195.15")),
                            # this will be considered in reamortisation
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("87.39")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    },
                    third_due_amount_datetime: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("100000")),
                            # emi updated due to variable rate change with principal 250777.33
                            # rate 0.010 and remaining term 10
                            # if overpayments and excess were considered this would be principal
                            # 150689.94 and emi would be 15138.15
                            (dimensions.EMI, Decimal("25192.82")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params
        )
        self.run_test_scenario(test_scenario)


class DelinquencyTest(MortgageTestBase):
    # TODO: align all start dates, but this is temporary to account for INC-8065
    start_date = datetime(year=2020, month=1, day=1, tzinfo=ZoneInfo("UTC"))

    def test_delinquency_workflow_triggered_for_overdue_balances_after_grace_period(self):
        instance_params = self.mortgage_instance_params.copy()
        instance_params["principal"] = "1000"
        instance_params["due_amount_calculation_day"] = "1"
        instance_params["fixed_interest_term"] = "0"

        start = self.start_date
        first_due_amount_calc_datetime = start + relativedelta(months=1, minutes=1)
        second_due_amount_calc_datetime = first_due_amount_calc_datetime + relativedelta(months=1)
        first_delinquency_event = second_due_amount_calc_datetime + relativedelta(
            days=1, hour=0, minute=0, seconds=2
        )
        end = first_delinquency_event

        sub_tests = [
            SubTest(
                description="Check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1000")),
                            (dimensions.EMI, Decimal("84.74")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("1000"))],
                    }
                },
            ),
            SubTest(
                description="check correct balance after first due event",
                expected_balances_at_ts={
                    first_due_amount_calc_datetime: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("917.89")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.11")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, "2.63"),
                        ],
                    }
                },
            ),
            SubTest(
                description="check correct balance after second due event",
                expected_balances_at_ts={
                    second_due_amount_calc_datetime: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("835.41")),
                            (dimensions.PRINCIPAL_DUE, Decimal("82.48")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("82.11")),
                            (dimensions.PENALTIES, Decimal("15.00")),
                            (dimensions.EMI, Decimal("84.74")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTEREST_DUE, "2.26"),
                        ],
                    }
                },
            ),
            SubTest(
                description="Check mark delinquent notification",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=first_delinquency_event,
                        notification_type=mortgage.MARK_DELINQUENT_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.MORTGAGE_ACCOUNT,
                        },
                        resource_id=f"{accounts.MORTGAGE_ACCOUNT}",
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
            debug=False,
        )
        self.run_test_scenario(test_scenario)


class DerivedParametersTest(MortgageTestBase):
    def test_total_outstanding_debt(self):

        start = self.default_simulation_start_date
        first_due_amount_calculation = start + relativedelta(months=1, days=17, minutes=1)
        day_after_second_due_amount_calculation = first_due_amount_calculation + relativedelta(
            months=1, days=1
        )
        end = day_after_second_due_amount_calculation

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("300000")),
                            (dimensions.EMI, Decimal("25135.62")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="300000.00",  # sum(PRINCIPAL)
                    ),
                ],
            ),
            SubTest(
                description="Check total outstanding debt at first due amount calc",
                expected_balances_at_ts={
                    first_due_amount_calculation: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("275119.17")),
                            (dimensions.EMI, Decimal("25135.62")),
                            (dimensions.INTEREST_DUE, Decimal("394.52")),
                            (dimensions.PRINCIPAL_DUE, Decimal("24880.83")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_due_amount_calculation,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        # principal + principal due, interest due
                        value="300394.52",
                    ),
                ],
            ),
            SubTest(
                description="Check outstanding debt after second due amount calc "
                "(with overdue balances)",
                expected_balances_at_ts={
                    day_after_second_due_amount_calculation: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("250202.14")),
                            (dimensions.EMI, Decimal("25135.62")),
                            # accrued interest is non-zero but not included
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("6.85486")),
                            (dimensions.INTEREST_DUE, Decimal("218.59")),
                            (dimensions.PRINCIPAL_DUE, Decimal("24917.03")),
                            (dimensions.INTEREST_OVERDUE, Decimal("394.52")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("24880.83")),
                            # 15 late repayment fee + penalty interest
                            (dimensions.PENALTIES, Decimal("32.31")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=day_after_second_due_amount_calculation,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        # principal + principal due / overdue, interest due / overdue, penalties,
                        # accrued interest
                        value="300652.27",
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_is_fixed_interest(self):
        start = self.default_simulation_start_date
        after_opening = start + relativedelta(hours=1)
        # fixed rate term ends after 6 months on the defined repayment day
        fixed_interest_term_ended = (
            start + relativedelta(day=28) + relativedelta(months=6, days=1, hours=1)
        )
        end = fixed_interest_term_ended + relativedelta(days=1)

        instance_params = self.mortgage_instance_params.copy()
        instance_params["fixed_interest_term"] = "6"

        sub_tests = [
            SubTest(
                description="check is fixed interest term is True after opening",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=after_opening,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.fixed_to_variable.PARAM_IS_FIXED_INTEREST,
                        value="True",
                    ),
                ],
            ),
            SubTest(
                description="check is fixed interest term is False after 6 months",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=fixed_interest_term_ended,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.fixed_to_variable.PARAM_IS_FIXED_INTEREST,
                        value="False",
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params
        )
        self.run_test_scenario(test_scenario)

    def test_is_interest_only_term(self):
        start = self.default_simulation_start_date
        after_opening = start + relativedelta(hours=1)
        # interest only term ends after 6 months
        interest_only_term_ended = (
            start + relativedelta(day=28) + relativedelta(months=6, days=1, hours=1)
        )
        end = interest_only_term_ended + relativedelta(days=1)

        instance_params = self.mortgage_instance_params.copy()
        instance_params["interest_only_term"] = "6"

        sub_tests = [
            SubTest(
                description="check is interest only term is True after opening",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=after_opening,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.PARAM_IS_INTEREST_ONLY_TERM,
                        value="True",
                    ),
                ],
            ),
            SubTest(
                description="check is interest only term is False after 6 months",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=interest_only_term_ended,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.PARAM_IS_INTEREST_ONLY_TERM,
                        value="False",
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params
        )
        self.run_test_scenario(test_scenario)

    def test_total_remaining_principal(self):
        start = self.default_simulation_start_date
        end = start + relativedelta(days=1)

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("300000")),
                            (dimensions.EMI, Decimal("25135.62")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="300000.00",  # sum(PRINCIPAL)
                    ),
                ],
            ),
            SubTest(
                description="Make an overpayment to affect total outstanding debt",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("299000")),
                            (dimensions.EMI, Decimal("25135.62")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(seconds=2),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        # sum(PRINCIPAL)
                        value="299000.00",
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_outstanding_payments(self):
        start = self.default_simulation_start_date
        first_due_amount_calculation = start + relativedelta(months=1, days=17, minutes=1)
        day_after_second_due_amount_calculation = first_due_amount_calculation + relativedelta(
            months=1, days=1
        )
        end = day_after_second_due_amount_calculation

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("300000")),
                            (dimensions.EMI, Decimal("25135.62")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.PARAM_OUTSTANDING_PAYMENTS,
                        value="0",  # sum(PRINCIPAL)
                    ),
                ],
            ),
            SubTest(
                description="Check outstanding_payments at first due amount calc",
                expected_balances_at_ts={
                    first_due_amount_calculation: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("275119.17")),
                            (dimensions.EMI, Decimal("25135.62")),
                            (dimensions.INTEREST_DUE, Decimal("394.52")),
                            (dimensions.PRINCIPAL_DUE, Decimal("24880.83")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_due_amount_calculation,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.PARAM_OUTSTANDING_PAYMENTS,
                        # principal due + interest due
                        value="25275.35",
                    ),
                ],
            ),
            SubTest(
                description="Check outstanding_payments after second due amount calc "
                "(with overdue balances)",
                expected_balances_at_ts={
                    day_after_second_due_amount_calculation: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("250202.14")),
                            (dimensions.EMI, Decimal("25135.62")),
                            # accrued interest is non-zero but not included
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("6.85486")),
                            (dimensions.INTEREST_DUE, Decimal("218.59")),
                            (dimensions.PRINCIPAL_DUE, Decimal("24917.03")),
                            (dimensions.INTEREST_OVERDUE, Decimal("394.52")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("24880.83")),
                            # 10 late repayment fee + penalty interest
                            (dimensions.PENALTIES, Decimal("32.31")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=day_after_second_due_amount_calculation,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.PARAM_OUTSTANDING_PAYMENTS,
                        # principal due / overdue, interest due / overdue, penalties
                        value="50443.28",
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_next_repayment_date(self):
        start = self.default_simulation_start_date
        after_opening = start + relativedelta(hours=1)
        after_first_due_amount_calc = datetime(2020, 2, 15, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
        end = start + relativedelta(months=2)

        instance_params = self.mortgage_instance_params.copy()
        instance_params["due_amount_calculation_day"] = "15"

        sub_tests = [
            SubTest(
                description="check first due amount calculation date",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=after_opening,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-02-15",
                    ),
                ],
            ),
            SubTest(
                description="check second due amount calculation date",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=after_first_due_amount_calc,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-03-15",
                    ),
                ],
            ),
            SubTest(
                description="check change in due amount calculation day is handled",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=after_first_due_amount_calc + relativedelta(days=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        due_amount_calculation_day="4",
                    ),
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=after_first_due_amount_calc + relativedelta(days=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        # effective datetime == 16/02 so changing due amount calculation day
                        # to 4th means the next date will be 04/04 to ensure +30 between
                        # due amount calculation dates
                        value="2020-04-04",
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params
        )
        self.run_test_scenario(test_scenario)

    def test_remaining_term(self):
        start = self.default_simulation_start_date
        first_repayment_date = datetime(
            year=2020,
            month=2,
            day=28,
            hour=0,
            minute=1,
            second=0,
            microsecond=2,
            tzinfo=ZoneInfo("UTC"),
        )
        end = start + relativedelta(months=13)

        sub_tests = [
            SubTest(
                description="check remaining term each month after opening",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(hours=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_REMAINING_TERM,
                        value="11",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(months=1, hours=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_REMAINING_TERM,
                        value="10",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(months=2, hours=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_REMAINING_TERM,
                        value="9",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(months=3, hours=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_REMAINING_TERM,
                        value="8",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(months=4, hours=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_REMAINING_TERM,
                        value="7",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(months=5, hours=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_REMAINING_TERM,
                        value="6",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(months=6, hours=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_REMAINING_TERM,
                        value="5",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(months=7, hours=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_REMAINING_TERM,
                        value="4",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(months=8, hours=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_REMAINING_TERM,
                        value="3",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(months=9, hours=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_REMAINING_TERM,
                        value="2",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(months=10, hours=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_REMAINING_TERM,
                        value="1",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(months=11, hours=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.derived_params.PARAM_REMAINING_TERM,
                        value="0",
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)


class InterestOnlyTest(MortgageTestBase):
    def test_monthly_due_for_variable_rate_interest_only(self):
        start = self.default_simulation_start_date
        end = start + relativedelta(months=6, hours=1)

        instance_params = parameters.mortgage_instance_params.copy()
        instance_params["due_amount_calculation_day"] = "11"
        instance_params["fixed_interest_term"] = "0"
        instance_params["interest_only_term"] = "3"

        first_due_calculation_event = start + relativedelta(months=1, minutes=1)
        repayment_1_datetime = first_due_calculation_event + relativedelta(hours=1)
        first_repayment_amount = Decimal("789.86")

        final_interest_only_due_calculation_event = first_due_calculation_event + relativedelta(
            months=2
        )
        final_interest_only_repayment_datetime = repayment_1_datetime + relativedelta(months=2)

        first_emi_due_calculation = final_interest_only_due_calculation_event + relativedelta(
            months=1
        )
        first_emi_repayment = first_emi_due_calculation + relativedelta(hours=1)

        interest_only_repayments = {
            repayment_1_datetime + relativedelta(months=1): Decimal("738.90"),
            repayment_1_datetime + relativedelta(months=2): Decimal("789.86"),
        }

        sub_tests = [
            SubTest(
                description="Check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("300000")),
                            (dimensions.EMI, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
            ),
            SubTest(
                description="First due amount calculation event",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount=str(first_repayment_amount),
                        event_datetime=repayment_1_datetime,
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    first_due_calculation_event: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("300000")),
                            (dimensions.EMI, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("789.86")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    },
                    repayment_1_datetime: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("300000")),
                            (dimensions.EMI, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    },
                },
            ),
            SubTest(
                description="Final interest only repayment due calculation event",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount=str(repayment_amount),
                        event_datetime=repayment_datetime,
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                    )
                    for repayment_datetime, repayment_amount in interest_only_repayments.items()
                ],
                expected_balances_at_ts={
                    final_interest_only_due_calculation_event: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("300000")),
                            (dimensions.EMI, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("789.86")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    },
                    final_interest_only_repayment_datetime: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("300000")),
                            (dimensions.EMI, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    },
                },
            ),
            SubTest(
                description="First non interest only repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="33765.37",
                        event_datetime=first_emi_repayment,
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    first_emi_due_calculation: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("266999.01")),
                            (dimensions.EMI, Decimal("33765.37")),
                            (dimensions.INTEREST_DUE, Decimal("764.38")),
                            (dimensions.PRINCIPAL_DUE, Decimal("33000.99")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    },
                    first_emi_repayment: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("266999.01")),
                            (dimensions.EMI, Decimal("33765.37")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    },
                },
            ),
            SubTest(
                description="Second non interest only repayment",
                expected_balances_at_ts={
                    first_emi_due_calculation
                    + relativedelta(months=1): {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("233936.62")),
                            (dimensions.EMI, Decimal("33765.37")),
                            (dimensions.INTEREST_DUE, Decimal("702.98")),
                            (dimensions.PRINCIPAL_DUE, Decimal("33062.39")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params
        )
        self.run_test_scenario(test_scenario)


class ProductSwitchingTest(MortgageTestBase):
    def test_product_switch_if_parameter_set_to_true(self):

        # In this test we want to check that overpayment allowance fees are charged on conversion
        # and the check allowance schedule is updated to run a year from the conversion.

        instance_params = {
            **parameters.mortgage_instance_params,
            # due_amount_calculation_day is same day as start day
            "due_amount_calculation_day": "11",
            "total_repayment_count": "36",
        }

        convert_to_version_id = "5"
        convert_to_contract_config = ContractConfig(
            contract_content=self.smart_contract_path_to_content[str(files.MORTGAGE_CONTRACT)],
            smart_contract_version_id=convert_to_version_id,
            template_params=parameters.mortgage_template_params,
            account_configs=[],
        )

        start = self.default_simulation_start_date
        due_amount_calc_1 = start + relativedelta(months=1, days=1, minutes=1)

        repayment_1 = due_amount_calc_1 + relativedelta(minutes=10)
        conversion = repayment_1 + relativedelta(minutes=10)
        new_allowance_check = conversion + relativedelta(years=1, minute=3)
        end = new_allowance_check
        emi = Decimal("8462.43")

        sub_tests = [
            SubTest(
                description="Overpayment allowance initialised on account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("300000")),
                            (dimensions.EMI, emi),
                            (dimensions.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER, "3000"),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_REMAINING,
                        value="3000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_USED,
                        value="0",
                    ),
                ],
            ),
            SubTest(
                description="First due amount calc",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("291792.36")),
                            (dimensions.PRINCIPAL_DUE, Decimal("8207.64")),
                            (dimensions.INTEREST_DUE, Decimal("254.79")),
                            (dimensions.EMI, emi),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
            ),
            SubTest(
                description="Consume allowance with overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount=str(emi + Decimal("3500")),
                        event_datetime=repayment_1,
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    repayment_1: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("288292.36")),
                            (dimensions.OVERPAYMENT, Decimal("3500")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.EMI, emi),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("3500"),
                            ),
                            (dimensions.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER, "-500"),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=repayment_1,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_REMAINING,
                        value="-500.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=repayment_1,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        name=mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_USED,
                        value="3500",
                    ),
                ],
            ),
            SubTest(
                description="Product Switch charges overpayment allowance fee and reschedules "
                "next allowance check",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=conversion - relativedelta(seconds=1),
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        product_switch="true",
                    ),
                    create_account_product_version_update_instruction(
                        timestamp=conversion,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        product_version_id=convert_to_version_id,
                    ),
                ],
                expected_balances_at_ts={
                    conversion: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("288292.36")),
                            # 5% of the excess 500 over the allowance = 25
                            (dimensions.PENALTIES, Decimal("25")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            # Reamortise with 288292.36 (excl backdating), 36 months and 0.01 rate
                            (dimensions.EMI, Decimal("8132.18")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("0")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("0"),
                            ),
                            (
                                dimensions.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
                                Decimal("0"),
                            ),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                        accounts.INTERNAL_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("25"))
                        ],
                    }
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[new_allowance_check],
                        event_id=mortgage.overpayment_allowance.CHECK_OVERPAYMENT_ALLOWANCE_EVENT,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        count=1,
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

        self.run_test_scenario(test_scenario, smart_contracts=[convert_to_contract_config])

    def test_no_product_switching_if_parameter_not_set_to_true(self):
        # In this test we want to check no switching behaviours are triggered as part of a regular
        # product version upgrade

        template_params = self.mortgage_template_params.copy()
        template_params["grace_period"] = "2"
        instance_params = self.mortgage_instance_params.copy()
        # due_amount_calculation_day is same day as start day
        instance_params["due_amount_calculation_day"] = "11"
        instance_params["total_repayment_count"] = "36"

        # two configs required to attempt two conversions
        convert_to_version_id = "5"
        convert_to_contract_config = ContractConfig(
            contract_content=self.smart_contract_path_to_content[str(files.MORTGAGE_CONTRACT)],
            smart_contract_version_id=convert_to_version_id,
            template_params=template_params,
            account_configs=[],
        )

        convert_to_version_id_2 = "6"
        convert_to_contract_config_2 = ContractConfig(
            contract_content=self.smart_contract_path_to_content[str(files.MORTGAGE_CONTRACT)],
            smart_contract_version_id=convert_to_version_id_2,
            template_params=template_params,
            account_configs=[],
        )

        start = self.default_simulation_start_date
        due_amount_calc_1 = start + relativedelta(months=1, days=1, minutes=1)

        repayment_1 = due_amount_calc_1 + relativedelta(minutes=10)
        conversion_1 = repayment_1 + relativedelta(minutes=10)
        conversion_2 = conversion_1 + relativedelta(minutes=1)
        original_allowance_check = start + relativedelta(years=1, minute=3)
        end = original_allowance_check
        emi = Decimal("8462.43")

        sub_tests = [
            SubTest(
                description="Account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("300000")),
                            (dimensions.EMI, emi),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
            ),
            SubTest(
                description="First due amount calc",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("291792.36")),
                            (dimensions.PRINCIPAL_DUE, Decimal("8207.64")),
                            (dimensions.INTEREST_DUE, Decimal("254.79")),
                            (dimensions.EMI, emi),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
            ),
            SubTest(
                description="Consume allowance with overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount=str(emi + Decimal("3500")),
                        event_datetime=repayment_1,
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        internal_account_id=accounts.INTERNAL_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    repayment_1: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("288292.36")),
                            (dimensions.OVERPAYMENT, Decimal("3500")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.EMI, emi),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("3500"),
                            ),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
            ),
            SubTest(
                description="Product version update does not trigger switch if param unset",
                events=[
                    create_account_product_version_update_instruction(
                        timestamp=conversion_1,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        product_version_id=convert_to_version_id,
                    ),
                ],
                expected_balances_at_ts={
                    conversion_1: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("288292.36")),
                            (dimensions.OVERPAYMENT, Decimal("3500")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.EMI, emi),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("3500"),
                            ),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
            ),
            SubTest(
                description="Product version update does not trigger switch if param set to false",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=conversion_2,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        product_switch="false",
                    ),
                    create_account_product_version_update_instruction(
                        timestamp=conversion_2,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        product_version_id=convert_to_version_id_2,
                    ),
                ],
                expected_balances_at_ts={
                    conversion_2: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("288292.36")),
                            (dimensions.OVERPAYMENT, Decimal("3500")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.EMI, emi),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                            (
                                dimensions.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                                Decimal("3500"),
                            ),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("300000"))],
                    }
                },
                # the allowance check runs 1y from account opening, as planned
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[original_allowance_check],
                        event_id=mortgage.overpayment_allowance.CHECK_OVERPAYMENT_ALLOWANCE_EVENT,
                        account_id=accounts.MORTGAGE_ACCOUNT,
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
        )

        self.run_test_scenario(
            test_scenario,
            smart_contracts=[convert_to_contract_config, convert_to_contract_config_2],
        )
