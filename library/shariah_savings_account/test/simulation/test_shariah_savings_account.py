# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from json import dumps
from zoneinfo import ZoneInfo

# library
from library.shariah_savings_account.test import accounts, dimensions, files, parameters
from library.shariah_savings_account.test.simulation.accounts import default_internal_accounts

# inception sdk
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ExpectedRejection,
    SimulationTestScenario,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_auth_adjustment_instruction,
    create_flag_definition_event,
    create_flag_event,
    create_inbound_authorisation_instruction,
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_outbound_authorisation_instruction,
    create_outbound_hard_settlement_instruction,
    create_posting_instruction_batch,
    create_release_event,
    create_settlement_event,
    update_account_status_pending_closure,
)
from inception_sdk.test_framework.contracts.simulation.utils import SimulationTestCase
from inception_sdk.vault.postings.posting_classes import (
    InboundHardSettlement,
    OutboundHardSettlement,
)

default_instance_params = parameters.default_instance
default_template_params = parameters.default_template


class ShariahSavingsAccountTest(SimulationTestCase):

    account_id_base = accounts.SHARIAH_SAVINGS_ACCOUNT
    contract_filepaths = [files.CONTRACT_FILE]

    def get_simulation_test_scenario(
        self,
        start,
        end,
        sub_tests,
        template_params=None,
        instance_params=None,
        internal_accounts=None,
        debug=True,
    ):
        contract_config = ContractConfig(
            contract_content=self.smart_contract_path_to_content[files.CONTRACT_FILE],
            template_params=template_params or default_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or default_instance_params,
                    account_id_base=self.account_id_base,
                )
            ],
        )
        return SimulationTestScenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            contract_config=contract_config,
            internal_accounts=internal_accounts or default_internal_accounts,
            debug=debug,
        )

    def test_early_account_closure_fee_applied(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=2, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **default_template_params,
            "early_closure_fee": "50",
            "early_closure_days": "2",
        }

        sub_tests = [
            SubTest(
                description="check early closure fee applied when early closure",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    update_account_status_pending_closure(end, accounts.SHARIAH_SAVINGS_ACCOUNT),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("950")),
                            (dimensions.EARLY_CLOSURE_FEE, Decimal("0")),
                        ],
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_early_account_closure_fee_not_applied_when_closed_after_early_closure_days(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=4, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **default_template_params,
            "early_closure_fee": "50",
            "early_closure_days": "2",
        }

        sub_tests = [
            SubTest(
                description="check fee not applied when not early closure",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    update_account_status_pending_closure(end, accounts.SHARIAH_SAVINGS_ACCOUNT),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.EARLY_CLOSURE_FEE, Decimal("0"))
                        ],
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_unapplied_accrued_profit_is_zeroed_out_on_account_closure(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=2, hour=1, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="Fund the account to accrue profit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        event_datetime=start + relativedelta(hours=1),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("1000")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Verify profit is accrued",
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("1000")),
                            (dimensions.ACCRUED_PROFIT_PAYABLE, Decimal("0.40822")),
                        ],
                        accounts.ACCRUED_PROFIT_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.40822"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Close account and zero out accrued profit",
                events=[
                    update_account_status_pending_closure(end, accounts.SHARIAH_SAVINGS_ACCOUNT),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("1000")),
                            (dimensions.ACCRUED_PROFIT_PAYABLE, Decimal("0")),
                        ],
                        accounts.ACCRUED_PROFIT_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )

        self.run_test_scenario(test_scenario)

    def test_payment_type_unknown_no_fee_applied(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="Initial deposit of 500.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("500.00")),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Payment type not defined in any of the fees. No fee applied.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "UNKNOWN"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(hours=1, minutes=10),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "UNKNOWN"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(hours=1, minutes=20),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "UNKNOWN"},
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("350.00")),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
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

    def test_payment_type_flat_fees_1_type_applied_twice(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="Initial deposit of 500.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("500")),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Flat fee applied 1 time.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_IBFT"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=2): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("445.00")),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Flat fee applied a total of 2 times.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(hours=3),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_IBFT"},
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("390.00")),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10")),
                        ],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )

        self.run_test_scenario(test_scenario)

    def test_payment_type_flat_fees_mix_of_types_applied(self):
        """
        Tests that two different flat fees have been applied. Note that payment_type ATM_IBFT
        has both flat and threshold fees. The amounts below do not incur a threshold fee.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="Initial deposit of 500.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(minutes=10),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(minutes=10): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("500")),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Fee applied for payment type ATM_IBFT.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(minutes=20),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_IBFT"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(minutes=20): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("445.00")),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Fee applied for payment types ATM_IBFT and ATM_MEPS.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(minutes=30),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_MEPS"},
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "394"),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("6")),
                        ],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )

        self.run_test_scenario(test_scenario)

    def test_payment_type_threshold_fee_applied(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="Initial deposit of 20,000.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="20000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20000")),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="No fee applied; payment type not in threshold list.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5001",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "DEBIT_POS"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=2): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("14999")),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="No fee applied; threshold not exceeded for payment type.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(hours=3),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "DUITNOW_PROXY"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=3): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("9999")),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Fee applied; threshold exceeded for payment type.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5001",
                        event_datetime=start + relativedelta(hours=4),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "DUITNOW_PROXY"},
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "4997.50"),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0.50")),
                        ],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )

        self.run_test_scenario(test_scenario)

    def test_payment_type_threshold_fee_not_applied(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="Check no threshold fee applied because threshold exceeded 0 times.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="20000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(hours=3),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "DUITNOW_PROXY"},
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "15000.00"),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
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

    def test_payment_type_all_fees_applied(self):
        """
        Fee applied for payment types flat, threshold, and monthly limit.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="Initial deposit of 20,000.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="20000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "20000"),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Flat fee applied.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(hours=3),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_MEPS"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=3): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "14999.00"),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("1.00")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Threshold fee applied.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5005",
                        event_datetime=start + relativedelta(hours=4),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "DUITNOW_PROXY"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=4): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "9993.50"),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("1.50")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Monthly limit fee not applied. Limit met.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=start + relativedelta(hours=5),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=start + relativedelta(hours=5, minutes=10),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=start + relativedelta(hours=5, minutes=20),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "3993.00"),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("2.00")),
                        ],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )

        self.run_test_scenario(test_scenario)

    def test_payment_type_monthly_limit_not_exceeded_no_fee_applied(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="Check no fee applied because monthly limit not exceeded.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("450.00")),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
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

    def test_wrong_denomination(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="Reject wrong denomination instructions without force override",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        event_datetime=start + relativedelta(hours=1),
                        denomination="EUR",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(hours=1),
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="WrongDenomination",
                        rejection_reason=(
                            "Cannot make transactions in the given denomination, "
                            "transactions must be one of ['MYR']"
                        ),
                    ),
                ],
            ),
            SubTest(
                description="Accept wrong denomination instructions with force override",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        event_datetime=start + relativedelta(hours=2),
                        denomination="EUR",
                        instruction_details={"force_override": "true"},
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=2): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.EUR_DEFAULT, Decimal("500"))
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

    def test_payment_type_monthly_limit_exceeded_fee_applied(self):
        """
        Monthly limit for payment type exceeded by 1. Fee applied.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=15, hour=23, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="Initial deposit and meeting monthly limit. No fee applied.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=2): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "400"),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                        accounts.PROFIT_PAID_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Monthly limit exceeded by 1. Fee applied. Profit"
                " applied to balance on profit application day.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(hours=3),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("350.07")),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0.50")),
                        ],
                        accounts.PROFIT_PAID_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0.57")),
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

    def test_payment_type_monthly_limit_across_months_fees_applied(self):
        """
        Across two months, monthly limit exceeded for current month. Fee applied.
        """
        start = datetime(year=2019, month=3, day=26, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=4, day=30, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="Initial deposit of 500 from previous month.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "500"),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                        accounts.PROFIT_PAID_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    }
                },
            ),
            SubTest(
                description="First withdrawal from previous month, no fee applied.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(days=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "450"),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                        accounts.PROFIT_PAID_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Second withdrawal, first for current month, no fee applied.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(days=10),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=10): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "400"),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                        accounts.PROFIT_PAID_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Third withdrawal, second for current month, no fee applied. Profit"
                " applied to balance on profit application day.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(days=12),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=12): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("351.86")),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                        accounts.PROFIT_PAID_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("1.86")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Fourth withdrawal, third for current month exceeding limit, "
                "fee applied.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(days=13),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=13): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("301.36")),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0.50")),
                        ],
                        accounts.PROFIT_PAID_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("1.86")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Fifth withdrawal, fourth for current month, two fees applied.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(days=15),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("250.86")),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("1")),
                        ],
                        accounts.PROFIT_PAID_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("1.86")),
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

    def test_payment_type_monthly_limit_exceeded_in_single_pib(self):

        start = datetime(year=2019, month=3, day=26, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=3, day=26, hour=1, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="Initial deposit of 500 ",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "500"),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    }
                },
            ),
            SubTest(
                description="First withdrawal in month exceeds limit, fee applied.",
                events=[
                    create_posting_instruction_batch(
                        event_datetime=start + relativedelta(hours=1),
                        instructions=[
                            OutboundHardSettlement(
                                amount="25",
                                target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                                internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                                denomination=default_template_params["denomination"],
                                instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                            ),
                            OutboundHardSettlement(
                                amount="25",
                                target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                                internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                                denomination=default_template_params["denomination"],
                                instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                            ),
                            OutboundHardSettlement(
                                amount="25",
                                target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                                internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                                denomination=default_template_params["denomination"],
                                instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                            ),
                        ],
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "424.5"),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0.5")),
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

    def test_payment_type_monthly_limit_template_param_variations(self):
        # Simulation test for monthly limit with improper payment type config scenarios:
        # fee: missing, 0, <0
        # limit: missing, 0, <0
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=15, hour=23, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **default_template_params,
            "maximum_monthly_payment_type_withdrawal_limit": dumps(
                {
                    "ATM_FEE_MISSING": {"feeee": "3", "limit": "1"},
                    "ATM_FEE_ZERO": {"fee": "0", "limit": "1"},
                    "ATM_FEE_NEG": {"fee": "-5", "limit": "1"},
                    "ATM_LIMIT_MISSING": {"fee": "3", "límitEE": "1"},
                    "ATM_LIMIT_NEG": {"fee": "3", "limit": "-2"},
                    "ATM_LIMIT_ZERO": {"fee": "15.25", "limit": "0"},
                },
            ),
        }

        sub_tests = [
            SubTest(
                description="Initial deposit of 500.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "500.00"),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0.00")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Fee definition missing (misspelt). No fee applied.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_FEE_MISSING"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(hours=1, minutes=10),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_FEE_MISSING"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1, minutes=30): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "480.00"),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0.00")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Fee=0. No fee applied.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_FEE_ZERO"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(hours=2, minutes=10),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_FEE_ZERO"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=2, minutes=30): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "460.00"),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0.00")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Fee is negative. No fee applied.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(hours=3),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_FEE_NEG"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(hours=3, minutes=10),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_FEE_NEG"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=3, minutes=30): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "440.00"),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0.00")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Limit missing (misspelt). No fee applied.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(hours=4),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_LIMIT_MISSING"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(hours=4, minutes=10),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_LIMIT_MISSING"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=4, minutes=30): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "420.00"),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0.00")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Limit is negative. No fee applied.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(hours=5),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_LIMIT_NEG"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(hours=5, minutes=10),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_LIMIT_NEG"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=5, minutes=30): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "400.00"),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0.00")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Limit is zero. Fee applied.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(hours=6),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_LIMIT_ZERO"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(hours=6, minutes=10),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_LIMIT_ZERO"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=6, minutes=30): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "349.50"),
                        ],
                        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("30.50")),
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

    def test_min_deposit(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **default_template_params,
            "minimum_deposit": "100",
        }

        sub_tests = [
            SubTest(
                description="check minimum deposit respected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    # Reject the following postings as they are less than the minimum deposit
                    create_inbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="1",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="0.01",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="99",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction amount 50 MYR is less than the minimum deposit amount "
                            "100 MYR."
                        ),
                    ),
                    ExpectedRejection(
                        timestamp=start,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction amount 1 MYR is less than the minimum deposit amount "
                            "100 MYR."
                        ),
                    ),
                    ExpectedRejection(
                        timestamp=start,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction amount 0.01 MYR is less than the minimum deposit amount "
                            "100 MYR."
                        ),
                    ),
                    ExpectedRejection(
                        timestamp=start,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction amount 99 MYR is less than the minimum deposit amount "
                            "100 MYR."
                        ),
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("100")),
                        ],
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_min_initial_deposit(self):
        """Check if `minimum_initial_deposit` is respected"""
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=10, tzinfo=ZoneInfo("UTC"))
        TIERED_MIN_BALANCE_THRESHOLD = dumps(
            {
                "SHARIAH_SAVINGS_ACCOUNT_TIER_UPPER": "0",
                "SHARIAH_SAVINGS_ACCOUNT_TIER_MIDDLE": "0",
                "SHARIAH_SAVINGS_ACCOUNT_TIER_LOWER": "0",
            }
        )

        template_params = {
            **default_template_params,
            "minimum_initial_deposit": "100",
            "minimum_deposit": "10",
            "tiered_minimum_balance_threshold": TIERED_MIN_BALANCE_THRESHOLD,
        }

        sub_tests = [
            SubTest(
                description="Check amount below min initial deposit rejected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="99.99",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction amount 99.99 MYR is less than the minimum"
                            " initial deposit amount 100.00 MYR."
                        ),
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Check amount equal min initial deposit respected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(hours=6),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=6): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("100")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Check debit is respected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(hours=7),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "DEBIT_PAYWAVE"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=7): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Check deposits after initial deposit"
                " can be less than minimum threshold",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="20",
                        event_datetime=end,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20")),
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

    def test_max_deposit(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **default_template_params,
            "maximum_deposit": "10000",
            "maximum_balance": "100000",
        }

        sub_tests = [
            SubTest(
                description="check maximum deposit respected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="50000",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="10001",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="10000.01",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction amount 50000 MYR is more than "
                            "the maximum permitted deposit amount 10000 MYR."
                        ),
                    ),
                    ExpectedRejection(
                        timestamp=start,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction amount 10001 MYR is more than "
                            "the maximum permitted deposit amount 10000 MYR."
                        ),
                    ),
                    ExpectedRejection(
                        timestamp=start,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction amount 10000.01 MYR is more than "
                            "the maximum permitted deposit amount 10000 MYR."
                        ),
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10000")),
                        ],
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_max_balance(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=26, hour=23, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **default_template_params,
            "maximum_balance": "10000",
        }
        instance_params = {
            **default_instance_params,
            "profit_application_day": "28",
        }

        posting_timestamp = start + relativedelta(days=10, hours=1)

        sub_tests = [
            SubTest(
                description="check max balance",
                events=[
                    # create 10 transactions over 10 days to build up to `maximum_balance`
                    *[
                        create_inbound_hard_settlement_instruction(
                            amount="1000",
                            event_datetime=start + relativedelta(days=i, hours=1),
                            target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                            internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                            denomination=template_params["denomination"],
                        )
                        for i in range(0, 10)
                    ],
                    # should fail over max allowable balance
                    create_inbound_hard_settlement_instruction(
                        amount="600",
                        event_datetime=posting_timestamp,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10000")),
                        ],
                    }
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=posting_timestamp,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Posting would exceed maximum permitted balance 10000 MYR",
                    )
                ],
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_maximum_single_withdrawal(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **default_template_params,
            "maximum_withdrawal": "99",
        }

        posting_timestamp = start + relativedelta(hours=3)

        sub_tests = [
            SubTest(
                description="Check max single withdrawal respected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=posting_timestamp,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=posting_timestamp,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction amount 100 MYR is greater than "
                            "the maximum withdrawal amount 99 MYR."
                        ),
                    )
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("450")),
                        ],
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )

        self.run_test_scenario(test_scenario)

    def test_min_balance(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=2, tzinfo=ZoneInfo("UTC"))

        posting_timestamp = start + relativedelta(hours=3)

        sub_tests = [
            SubTest(
                description="Check min balance respected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # Should be rejected as it will bring the balance below min balance
                    create_outbound_hard_settlement_instruction(
                        amount="1",
                        event_datetime=posting_timestamp,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=posting_timestamp,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction amount -1 MYR will result in the account balance falling "
                            "below the minimum permitted of 100 MYR."
                        ),
                    )
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("100")),
                        ],
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )

        self.run_test_scenario(test_scenario)

    def test_maximum_payment_type_withdrawal(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))

        posting_timestamp_1 = start + relativedelta(hours=3)
        posting_timestamp_2 = start + relativedelta(hours=4)
        posting_timestamp_3 = start + relativedelta(hours=5)

        sub_tests = [
            SubTest(
                description="Initial funding of 1000 MYR and accept postings within limit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "DEBIT_PAYWAVE"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="250",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "DEBIT_PAYWAVE"},
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("700")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Check max withdrawal by payment type rejects above limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="250.01",
                        event_datetime=posting_timestamp_1,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "DEBIT_PAYWAVE"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="251",
                        event_datetime=posting_timestamp_2,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "DEBIT_PAYWAVE"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="600",
                        event_datetime=posting_timestamp_3,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "DEBIT_PAYWAVE"},
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=posting_timestamp_1,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction amount 250.01 MYR is more than the maximum withdrawal "
                            "amount 250 MYR allowed for the the payment type DEBIT_PAYWAVE."
                        ),
                    ),
                    ExpectedRejection(
                        timestamp=posting_timestamp_2,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction amount 251.00 MYR is more than the maximum withdrawal "
                            "amount 250 MYR allowed for the the payment type DEBIT_PAYWAVE."
                        ),
                    ),
                    ExpectedRejection(
                        timestamp=posting_timestamp_3,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction amount 600.00 MYR is more than the maximum withdrawal "
                            "amount 250 MYR allowed for the the payment type DEBIT_PAYWAVE."
                        ),
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("700")),
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

    def test_maximum_payment_type_withdrawal_mix(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))

        posting_timestamp = start + relativedelta(hours=2)

        sub_tests = [
            SubTest(
                description="Initial funding of 1000 MYR",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("1000")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Check max withdrawal limit hit rejects posting",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="250",
                        event_datetime=posting_timestamp,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "DEBIT_PAYWAVE"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="251",
                        event_datetime=posting_timestamp,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "DEBIT_PAYWAVE"},
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=posting_timestamp,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction amount 251.00 MYR is more than the maximum withdrawal "
                            "amount 250 MYR allowed for the the payment type DEBIT_PAYWAVE."
                        ),
                    )
                ],
                expected_balances_at_ts={
                    posting_timestamp: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("750")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Check different payment type withdrawal accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(hours=3),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("250")),
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

    def test_max_daily_deposit_in_single_posting(self):
        """
        Check if deposits over `maximum_daily_deposit` are rejected when deposited in 1 go.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **default_template_params,
            "maximum_daily_deposit": "1000",
        }

        posting_timestamp = start + relativedelta(hours=1)

        sub_tests = [
            SubTest(
                description="check max daily deposit in single posting",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="1001",
                        event_datetime=posting_timestamp,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=posting_timestamp,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transactions would cause the maximum daily deposit limit of "
                            "1000 MYR to be exceeded."
                        ),
                    )
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("1000")),
                        ],
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_max_daily_deposit_multiple_postings(self):
        """
        Check if deposits over `maximum_daily_deposit` are rejected when deposited over multiple
        postings.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **default_template_params,
            "maximum_daily_deposit": "1001",
        }

        posting_timestamp = start + relativedelta(hours=3)

        sub_tests = [
            SubTest(
                description="check max daily deposit in multiple posting",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="700",
                        event_datetime=posting_timestamp,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=posting_timestamp,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transactions would cause the maximum daily deposit limit of "
                            "1001 MYR to be exceeded."
                        ),
                    )
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("500")),
                        ],
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_max_daily_deposit_multiple_postings_concurrent(self):
        """
        Are deposits over `maximum_daily_deposit` rejected when deposited over multiple postings at
        the same time.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **default_template_params,
            "maximum_daily_deposit": "1001",
        }

        posting_timestamp = start + relativedelta(hours=1)

        sub_tests = [
            SubTest(
                description="check max daily deposit in multiple concurrent posting",
                events=[
                    create_posting_instruction_batch(
                        instructions=[
                            InboundHardSettlement(
                                amount="500",
                                target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                                internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                                denomination=template_params["denomination"],
                            ),
                            InboundHardSettlement(
                                amount="502",
                                target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                                internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                                denomination=template_params["denomination"],
                            ),
                        ],
                        event_datetime=posting_timestamp,
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=posting_timestamp,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transactions would cause the maximum daily deposit limit of "
                            "1001 MYR to be exceeded."
                        ),
                    )
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_max_daily_deposit_under_24_hrs(self):
        """
        Check if `maximum_daily_deposit` is respected over the midnight boundary.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=3, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **default_template_params,
            "maximum_daily_deposit": "1001",
        }

        posting_timestamp_1 = start + relativedelta(hours=23)
        posting_timestamp_2 = start + relativedelta(days=1, hours=23)

        sub_tests = [
            SubTest(
                description="check max daily deposit within the first 24 hours",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(hours=22),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=posting_timestamp_1,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=posting_timestamp_1,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transactions would cause the maximum daily deposit limit of "
                            "1001 MYR to be exceeded."
                        ),
                    )
                ],
                expected_balances_at_ts={
                    posting_timestamp_1: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("1000")),
                        ],
                    }
                },
            ),
            SubTest(
                description="check max daily deposit within the next 24 hours",
                events=[
                    # should succeed as we're in a new day
                    create_inbound_hard_settlement_instruction(
                        amount="900",
                        event_datetime=start + relativedelta(days=1, hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="400",
                        event_datetime=posting_timestamp_2,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=posting_timestamp_2,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transactions would cause the maximum daily deposit limit of "
                            "1001 MYR to be exceeded."
                        ),
                    )
                ],
                expected_balances_at_ts={
                    posting_timestamp_2: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("1900")),
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

    def test_max_daily_deposit_with_withdrawal(self):
        """
        Check if withdrawing modifies the `maximum_daily_deposit` limit. It should not.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **default_template_params,
            "maximum_daily_deposit": "1000",
        }

        posting_timestamp_1 = start + relativedelta(hours=3)
        posting_timestamp_2 = start + relativedelta(hours=5)

        sub_tests = [
            SubTest(
                description="check max daily deposit standard rejection",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="700",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    # over the deposit limit
                    create_inbound_hard_settlement_instruction(
                        amount="600",
                        event_datetime=posting_timestamp_1,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=posting_timestamp_1,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transactions would cause the maximum daily deposit limit of "
                            "1000 MYR to be exceeded."
                        ),
                    )
                ],
                expected_balances_at_ts={
                    posting_timestamp_1: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("700")),
                        ],
                    }
                },
            ),
            SubTest(
                description="attempt to counter deposit with withdrawal",
                events=[
                    # can we reset the 'counter' with a withdrawal?
                    create_outbound_hard_settlement_instruction(
                        amount="600",
                        event_datetime=start + relativedelta(hours=4),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    # still over the deposit limit so should fail
                    create_inbound_hard_settlement_instruction(
                        amount="600",
                        event_datetime=posting_timestamp_2,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=posting_timestamp_2,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transactions would cause the maximum daily deposit limit of "
                            "1000 MYR to be exceeded."
                        ),
                    )
                ],
                expected_balances_at_ts={
                    posting_timestamp_2: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("100")),
                        ],
                    }
                },
            ),
            SubTest(
                description="check max daily deposit within limit",
                events=[
                    # within deposit limit should pass
                    create_inbound_hard_settlement_instruction(
                        amount="300",
                        event_datetime=start + relativedelta(hours=6),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("400")),
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

    def test_max_daily_deposit_using_auths(self):
        """
        Check that authorisation trigger the `maximum_daily_deposit` limit.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **default_template_params,
            "maximum_daily_deposit": "1000",
        }

        posting_timestamp_1 = start + relativedelta(hours=17)
        posting_timestamp_2 = start + relativedelta(hours=19)

        sub_tests = [
            SubTest(
                description="check max daily deposit with auth above limit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(hours=6),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    # should fail with auth over limit
                    create_inbound_authorisation_instruction(
                        amount="1234",
                        event_datetime=posting_timestamp_1,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=posting_timestamp_1,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transactions would cause the maximum daily deposit limit of "
                            "1000 MYR to be exceeded."
                        ),
                    )
                ],
                expected_balances_at_ts={
                    posting_timestamp_1: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("500")),
                        ],
                    }
                },
            ),
            SubTest(
                description="check max daily deposit with auth adjustment above limit",
                events=[
                    # accept auth within limit
                    create_inbound_authorisation_instruction(
                        amount="300",
                        event_datetime=start + relativedelta(hours=18),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                        client_transaction_id="A",
                    ),
                    # should fail with auth adjustment over limit
                    create_auth_adjustment_instruction(
                        amount="700",
                        event_datetime=posting_timestamp_2,
                        client_transaction_id="A",
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=posting_timestamp_2,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transactions would cause the maximum daily deposit limit of "
                            "1000 MYR to be exceeded."
                        ),
                    )
                ],
                expected_balances_at_ts={
                    posting_timestamp_2: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("500")),
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

    def test_max_daily_withdrawal_single_posting(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))

        posting_timestamp = start + relativedelta(hours=1)

        template_params = {
            **default_template_params,
            "maximum_daily_withdrawal": "100",
        }

        sub_tests = [
            SubTest(
                description="check maxiumum daily withdrawal respected in single posting",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="101",
                        event_datetime=posting_timestamp,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(hours=3),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=posting_timestamp,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transactions would cause the maximum daily withdrawal limit of "
                            "100 MYR to be exceeded."
                        ),
                    )
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("400")),
                        ],
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_max_withdrawal(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))

        posting_timestamp = start + relativedelta(hours=3)

        template_params = {
            **default_template_params,
            "maximum_daily_withdrawal": "10000",
            "maximum_daily_deposit": "10000",
            "maximum_withdrawal": "5000",
        }

        sub_tests = [
            SubTest(
                description="check max withdrawal respected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="5000.01",
                        event_datetime=posting_timestamp,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=posting_timestamp,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction amount 5000.01 MYR is greater than "
                            "the maximum withdrawal amount 5000 MYR."
                        ),
                    )
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5000")),
                        ],
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_withdrawal_independence(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))

        posting_timestamp_1 = start + relativedelta(hours=1)
        posting_timestamp_2 = start + relativedelta(hours=2)
        posting_timestamp_3 = start + relativedelta(hours=3)

        template_params = {
            **default_template_params,
            "maximum_daily_withdrawal": "100",
        }

        sub_tests = [
            SubTest(
                description="Fund account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("1000")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Reject withdrawals above limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="101",
                        event_datetime=posting_timestamp_1,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=posting_timestamp_1,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=posting_timestamp_1,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=posting_timestamp_1,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transactions would cause the maximum daily withdrawal limit of "
                            "100 MYR to be exceeded."
                        ),
                    ),
                    ExpectedRejection(
                        timestamp=posting_timestamp_1,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transactions would cause the maximum daily withdrawal limit of "
                            "100 MYR to be exceeded."
                        ),
                    ),
                    ExpectedRejection(
                        timestamp=posting_timestamp_1,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transactions would cause the maximum daily withdrawal limit of "
                            "100 MYR to be exceeded."
                        ),
                    ),
                ],
                expected_balances_at_ts={
                    posting_timestamp_1: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("1000")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Accept withdrawal within limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=posting_timestamp_2,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    posting_timestamp_2: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("950")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Reject withdrawals above limit (again)",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="101",
                        event_datetime=posting_timestamp_3,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=posting_timestamp_3,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=posting_timestamp_3,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=posting_timestamp_3,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transactions would cause the maximum daily withdrawal limit of "
                            "100 MYR to be exceeded."
                        ),
                    ),
                    ExpectedRejection(
                        timestamp=posting_timestamp_3,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transactions would cause the maximum daily withdrawal limit of "
                            "100 MYR to be exceeded."
                        ),
                    ),
                    ExpectedRejection(
                        timestamp=posting_timestamp_3,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transactions would cause the maximum daily withdrawal limit of "
                            "100 MYR to be exceeded."
                        ),
                    ),
                ],
                expected_balances_at_ts={
                    posting_timestamp_3: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("950")),
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

    def test_max_daily_withdrawal(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=3, tzinfo=ZoneInfo("UTC"))

        posting_timestamp_1 = start + relativedelta(hours=1)
        posting_timestamp_2 = start + relativedelta(hours=2)
        posting_timestamp_3 = start + relativedelta(days=1, hours=3)
        posting_timestamp_4 = start + relativedelta(days=1, hours=9)

        template_params = {
            **default_template_params,
            "maximum_daily_withdrawal": "100",
        }

        sub_tests = [
            SubTest(
                description="Fund account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("1000")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Accept withdrawals within limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=posting_timestamp_1,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=posting_timestamp_1,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    posting_timestamp_1: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("900")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Reject withdrawals over max daily amount",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="60",
                        event_datetime=posting_timestamp_2,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=posting_timestamp_2,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transactions would cause the maximum daily withdrawal limit of "
                            "100 MYR to be exceeded."
                        ),
                    ),
                ],
                expected_balances_at_ts={
                    posting_timestamp_2: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("900")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Accept withdrawals in a new day",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=posting_timestamp_3,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=posting_timestamp_3,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    posting_timestamp_3: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("800")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Reject posting in the same day",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=posting_timestamp_4,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=posting_timestamp_4,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transactions would cause the maximum daily withdrawal limit of "
                            "100 MYR to be exceeded."
                        ),
                    ),
                ],
                expected_balances_at_ts={
                    posting_timestamp_4: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("800")),
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

    def test_max_daily_withdrawal_under_24_hrs(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=3, tzinfo=ZoneInfo("UTC"))

        posting_timestamp_1 = start + relativedelta(hours=22)
        posting_timestamp_2 = start + relativedelta(days=1, hours=1)

        template_params = {
            **default_template_params,
            "maximum_daily_withdrawal": "100",
        }

        sub_tests = [
            SubTest(
                description="Fund account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("1000")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Reject posting over limit in same day",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=posting_timestamp_1,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="60",
                        event_datetime=posting_timestamp_1 + relativedelta(microseconds=10),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=posting_timestamp_1 + relativedelta(microseconds=10),
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transactions would cause the maximum daily withdrawal limit of "
                            "100 MYR to be exceeded."
                        ),
                    ),
                ],
                expected_balances_at_ts={
                    posting_timestamp_1: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("900")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Accept posting after midnight boundary",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="90",
                        event_datetime=posting_timestamp_2,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    posting_timestamp_2: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("810")),
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

    def test_max_withdrawal_of_a_payment_type(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        day1 = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))
        day2 = datetime(year=2019, month=1, day=2, hour=23, tzinfo=ZoneInfo("UTC"))
        day3 = datetime(year=2019, month=1, day=3, hour=23, tzinfo=ZoneInfo("UTC"))
        day4 = datetime(year=2019, month=1, day=4, hour=23, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=5, hour=23, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **default_template_params,
            "maximum_deposit": "20000",
            "maximum_balance": "20000",
            "maximum_daily_withdrawal": "20000",
            "maximum_daily_deposit": "20000",
            "maximum_withdrawal": "6000",
        }
        instance_params = {
            **default_instance_params,
            "profit_application_day": "10",
        }

        sub_tests = [
            SubTest(
                description="check max withdrawal for same payment type respected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="20000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="4000",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                        instruction_details={"TRANSACTION_TYPE": "ATM_VISA"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1000.01",
                        event_datetime=day1,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                        instruction_details={"TRANSACTION_TYPE": "ATM_VISA"},
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=day1,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transactions would cause the maximum daily ATM_VISA withdrawal "
                            "limit of 5000 MYR to be exceeded."
                        ),
                    ),
                ],
                expected_balances_at_ts={
                    day1: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("16000")),
                        ],
                    }
                },
            ),
            SubTest(
                description="check max withdrawal for different payment type respected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(days=1, hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                        instruction_details={"TRANSACTION_TYPE": "ATM_ARBM"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="4000",
                        event_datetime=start + relativedelta(days=1, hours=2),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                        instruction_details={"TRANSACTION_TYPE": "ATM_VISA"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(days=1, hours=3),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                        instruction_details={"TRANSACTION_TYPE": "ATM_VISA"},
                    ),
                ],
                expected_balances_at_ts={
                    day2: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10500")),
                        ],
                    }
                },
            ),
            SubTest(
                description="check max withdrawal for same payment type on authorisation respected",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(days=2, hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                        instruction_details={"TRANSACTION_TYPE": "ATM_VISA"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="60",
                        event_datetime=day3,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                        instruction_details={"TRANSACTION_TYPE": "ATM_VISA"},
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=day3,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transactions would cause the maximum daily ATM_VISA withdrawal "
                            "limit of 5000 MYR to be exceeded."
                        ),
                    ),
                ],
                expected_balances_at_ts={
                    day3: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10500")),
                        ],
                    }
                },
            ),
            SubTest(
                description="check max withdrawal unaffected by deposit with same type",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(days=3, hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                        instruction_details={"TRANSACTION_TYPE": "ATM_VISA"},
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="4500",
                        event_datetime=start + relativedelta(days=3, hours=2),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                        instruction_details={"TRANSACTION_TYPE": "ATM_VISA"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="4000",
                        event_datetime=day4,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                        instruction_details={"TRANSACTION_TYPE": "ATM_VISA"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1",
                        event_datetime=day4 + relativedelta(microseconds=10),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                        instruction_details={"TRANSACTION_TYPE": "ATM_VISA"},
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=day4 + relativedelta(microseconds=10),
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transactions would cause the maximum daily ATM_VISA withdrawal "
                            "limit of 5000 MYR to be exceeded."
                        ),
                    ),
                ],
                expected_balances_at_ts={
                    day4: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10000")),
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
        )

        self.run_test_scenario(test_scenario)

    def test_single_deposit(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="check balance after single deposit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("1000")),
                        ],
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )

        self.run_test_scenario(test_scenario)

    def test_profit_accrual_payable(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=2, hour=2, tzinfo=ZoneInfo("UTC"))

        # the balance of the previous day (23:59:59) is used so on day 1 nothing is paid
        # (0.149 / 365) * 1000 = 0.4082
        sub_tests = [
            SubTest(
                description="check profit accrual payable",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("1000")),
                            (dimensions.ACCRUED_PROFIT_PAYABLE, Decimal("0.40822")),
                        ],
                        accounts.ACCRUED_PROFIT_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.40822")),
                        ],
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )

        self.run_test_scenario(test_scenario)

    def test_profit_application_payable_customer_account(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=2, day=1, minute=1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "profit_application_day": "1",
        }

        sub_tests = [
            SubTest(
                description="check accrued profit payable to customer",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    # 31 days of profit accrued 1000 * 0.00040822 = 0.40822 * 31 = 12.65482
                    # checking just before profit application which runs at 01:05:00
                    end
                    - relativedelta(minutes=1): {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.ACCRUED_PROFIT_PAYABLE, Decimal("12.65482")),
                            (dimensions.DEFAULT, Decimal("1000")),
                        ],
                    },
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.ACCRUED_PROFIT_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("1012.65")),
                        ],
                    },
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_max_balance_with_profit(self):
        """
        Check that profit is applied correctly if account is over `maximum_balance`. As well as
        not being able to deposit.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=2, day=26, hour=23, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **default_template_params,
            "maximum_balance": "10000",
        }
        instance_params = {
            **default_instance_params,
            "profit_application_day": "28",
        }

        sub_tests = [
            SubTest(
                description="check max balance with profit",
                events=[
                    # create 10 transactions over 10 days to build up to `maximum_balance`
                    *[
                        create_inbound_hard_settlement_instruction(
                            amount="1000",
                            event_datetime=start + relativedelta(days=i, minutes=1),
                            target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                            internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                            denomination=template_params["denomination"],
                        )
                        for i in range(0, 10)
                    ],
                    # next 2 events should not get through to the account
                    create_inbound_hard_settlement_instruction(
                        amount="600",
                        event_datetime=start + relativedelta(days=10, minutes=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(days=14, minutes=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10091.85")),
                        ],
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_single_withdrawal(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="check if single withdrawal",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("450")),
                        ],
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )

        self.run_test_scenario(test_scenario)

    def test_change_date(self):
        start = datetime(year=2019, month=1, day=26, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=2, day=4, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "profit_application_day": "27",
        }
        instance_params["profit_application_day"] = "27"

        sub_tests = [
            SubTest(
                description="check profit application day change",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start,
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        profit_application_day="3",
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("100.33")),
                        ],
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_in_auth_release(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=2, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **default_template_params,
            "minimum_deposit": "100",
        }

        sub_tests = [
            SubTest(
                description="check inbound auth and release",
                events=[
                    create_inbound_authorisation_instruction(
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        amount="100.00",
                        event_datetime=start + relativedelta(hours=3),
                        denomination=template_params["denomination"],
                        client_transaction_id="RELEASE_TEST_TRANSACTION",
                    ),
                    create_release_event(
                        client_transaction_id="RELEASE_TEST_TRANSACTION",
                        event_datetime=start + relativedelta(hours=6),
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.INCOMING, Decimal("0")),
                        ],
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_out_auth_release(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=10, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="check outbound auth and release",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_authorisation_instruction(
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        amount="60.00",
                        event_datetime=start + relativedelta(hours=3),
                        denomination=default_template_params["denomination"],
                        client_transaction_id="RELEASE_TEST_TRANSACTION",
                    ),
                    create_release_event(
                        client_transaction_id="RELEASE_TEST_TRANSACTION",
                        event_datetime=start + relativedelta(hours=6),
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("100")),
                            (dimensions.OUTGOING, Decimal("0")),
                        ],
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )

        self.run_test_scenario(test_scenario)

    def test_in_auth_settlement(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=10, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **default_template_params,
            "minimum_deposit": "100",
        }

        sub_tests = [
            SubTest(
                description="check inbound auth and settlement",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="200",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_inbound_authorisation_instruction(
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        amount="100.00",
                        event_datetime=start + relativedelta(hours=3),
                        denomination=template_params["denomination"],
                        client_transaction_id="SETTLEMENT_TEST_TRANSACTION",
                    ),
                    create_settlement_event(
                        "100.00",
                        event_datetime=start + relativedelta(hours=4),
                        client_transaction_id="SETTLEMENT_TEST_TRANSACTION",
                        final=True,
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("300")),
                            (dimensions.INCOMING, Decimal("0")),
                        ],
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_out_auth_settlement(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=10, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="check outbound auth and settlement",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="200",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_authorisation_instruction(
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        amount="60.00",
                        event_datetime=start + relativedelta(hours=3),
                        denomination=default_template_params["denomination"],
                        client_transaction_id="SETTLEMENT_TEST_TRANSACTION",
                    ),
                    create_settlement_event(
                        "60.00",
                        event_datetime=start + relativedelta(hours=4),
                        client_transaction_id="SETTLEMENT_TEST_TRANSACTION",
                        final=True,
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("140")),
                            (dimensions.OUTGOING, Decimal("0")),
                        ],
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )

        self.run_test_scenario(test_scenario)

    def test_out_auth_adjustment(self):
        """
        Check an Outbound Authorisation posting followed by authorisation Adjustment.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=1, hour=10, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="check outbound auth followed by auth adjustment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="200",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_authorisation_instruction(
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        amount="50.00",
                        event_datetime=start + relativedelta(hours=3),
                        denomination=default_template_params["denomination"],
                        client_transaction_id="ADJUSTMENT_TEST_TRANSACTION",
                    ),
                    create_auth_adjustment_instruction(
                        amount="30.00",
                        event_datetime=start + relativedelta(hours=4),
                        client_transaction_id="ADJUSTMENT_TEST_TRANSACTION",
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "200"),
                            (dimensions.OUTGOING, Decimal("-80")),
                        ],
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )

        self.run_test_scenario(test_scenario)

    def test_back_dated_posting_double_spend(self):
        """
        This test will check if backdated posting will be rejected if there are no funds anymore
        during the time it wants to backdate [value timestamp].
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=4, hour=23, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **default_template_params,
            "maximum_daily_withdrawal": "5000",
            "maximum_daily_deposit": "5000",
        }

        sub_tests = [
            SubTest(
                description="",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(hours=5),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    # doing back dated deposit to check if its supported
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(hours=6),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                        value_timestamp=start + relativedelta(hours=1),
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="900",
                        event_datetime=start + relativedelta(hours=7),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    # should be rejected since all funds was withdrawn on the previous event
                    create_outbound_hard_settlement_instruction(
                        amount="900",
                        event_datetime=start + relativedelta(hours=8),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                        value_timestamp=start + relativedelta(hours=5),
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("100")),
                        ],
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_back_dated_posting_max_account_balance(self):
        """
        Test if backdated deposit posting will go above the account balance limit.
        """
        start = datetime(year=2019, month=1, day=5, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=20, hour=23, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **default_template_params,
            "maximum_balance": "10000",
            "maximum_daily_deposit": "10000",
        }

        sub_tests = [
            SubTest(
                description="check backdated deposit will go above account balance limit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(hours=8),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(days=1),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    # Should get rejected since limit is now 10000.
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(days=10),
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                        value_timestamp=start + relativedelta(hours=5),
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SHARIAH_SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10000")),
                        ],
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_expired_flags_no_longer_have_tier_effect(self):
        """
        Check that an expired flag is no longer considered for tiering.
        """

        start = datetime(year=2019, month=1, day=1, hour=0, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=1, day=11, hour=23, tzinfo=ZoneInfo("UTC"))

        account_tier_names = dumps(
            [
                "X",
                "Y",
            ]
        )
        tiered_profit_rates = dumps(
            {
                "X": {"0.00": "0.1", "100.00": "0.2"},
                "Y": {"0.00": "0.3", "100.00": "0.4"},
            }
        )
        tiered_min_balance_threshold = dumps(
            {
                "X": "10",
                "Y": "100",
            }
        )

        template_params = {
            **default_template_params,
            "account_tier_names": account_tier_names,
            "days_in_year": "365",
            "minimum_deposit": "50",
            "profit_accrual_hour": "0",
            "profit_accrual_minute": "0",
            "profit_accrual_second": "0",
            "profit_application_hour": "0",
            "profit_application_minute": "1",
            "profit_application_second": "0",
            "tiered_minimum_balance_threshold": tiered_min_balance_threshold,
            "tiered_profit_rates": tiered_profit_rates,
        }

        instance_params = {
            **default_instance_params,
            "profit_application_day": "30",
        }

        # This is 10 days of profit accrual (with flag change after day 5)
        tiered_profit_accrual_payable = [
            # Daily rate is 1.06749
            "0.00",
            "1.06849",
            "2.13698",
            "3.20547",
            "4.27396",
            "5.34245",
            # Rates change here to 0.52055
            "5.86300",
            "6.38355",
            "6.90410",
            "7.42465",
            "7.94520",
        ]

        # Set expected balances for 10 days of profit accrual
        expected_balances = {}
        for i in range(11):
            profit_date = start + relativedelta(days=i)
            expected_balances[profit_date] = {
                accounts.SHARIAH_SAVINGS_ACCOUNT: [
                    (
                        dimensions.ACCRUED_PROFIT_PAYABLE,
                        tiered_profit_accrual_payable[i],
                    ),
                ],
            }
        expected_balances[end] = {
            accounts.SHARIAH_SAVINGS_ACCOUNT: [
                (dimensions.DEFAULT, Decimal("1000")),
                (dimensions.ACCRUED_PROFIT_PAYABLE, Decimal("7.94520")),
            ],
        }

        sub_tests = [
            SubTest(
                description="Check accrual rates change after initial flag expiration",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start,
                        target_account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DUMMY_DEPOSITING_ACCOUNT,
                        denomination=template_params["denomination"],
                    ),
                    create_flag_definition_event(timestamp=start, flag_definition_id="Y"),
                    create_flag_definition_event(timestamp=start, flag_definition_id="X"),
                    create_flag_event(
                        timestamp=start,
                        expiry_timestamp=start + relativedelta(days=5),
                        flag_definition_id="Y",
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(days=5) + relativedelta(seconds=1),
                        expiry_timestamp=end,
                        flag_definition_id="X",
                        account_id=accounts.SHARIAH_SAVINGS_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts=expected_balances,
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)
