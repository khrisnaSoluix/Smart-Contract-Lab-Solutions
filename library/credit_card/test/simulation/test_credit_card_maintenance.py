# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from json import dumps
from zoneinfo import ZoneInfo

# library
from library.credit_card.test.simulation.parameters import (
    DEFAULT_CREDIT_CARD_INSTANCE_PARAMS,
    DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS,
)

# inception sdk
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    SimulationTestScenario,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_flag_definition_event,
    create_flag_event,
    create_inbound_hard_settlement_instruction,
    create_outbound_authorisation_instruction,
    create_outbound_hard_settlement_instruction,
    create_settlement_event,
)
from inception_sdk.test_framework.contracts.simulation.utils import SimulationTestCase

CONTRACT_FILE = "library/credit_card/contracts/template/credit_card.py"
DEFAULT_DENOM = "GBP"
EXPIRE_INTEREST_FREE_PERIODS_WORKFLOW = "EXPIRE_INTEREST_FREE_PERIODS"
PUBLISH_STATEMENT_DATA_WORKFLOW = "PUBLISH_STATEMENT_DATA"
ASSET_CONTRACT_FILE = "internal_accounts/testing_internal_asset_account_contract.py"
LIABILITY_CONTRACT_FILE = "internal_accounts/testing_internal_liability_account_contract.py"
CONTRACT_FILES = [CONTRACT_FILE, ASSET_CONTRACT_FILE, LIABILITY_CONTRACT_FILE]

default_instance_params = DEFAULT_CREDIT_CARD_INSTANCE_PARAMS
default_template_params = DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS


class CreditCardMaintenanceTest(SimulationTestCase):
    """
    Tests of account flags, closing and other behaviour that doesn't fit elsewhere
    """

    contract_filepaths = [CONTRACT_FILE]

    internal_accounts = {
        "annual_fee_income_int": "LIABILITY",
        "1": "LIABILITY",
        "Dummy account": "LIABILITY",
        "customer_deposits_int": "LIABILITY",
        "Internal account": "LIABILITY",
        "late_repayment_fee_income_int": "LIABILITY",
        "purchase_interest_income_int": "LIABILITY",
        "cash_advance_fee_income_int": "LIABILITY",
        "casa_account_id": "LIABILITY",
        "overlimit_fee_income_int": "LIABILITY",
        "cash_advance_interest_income_int": "LIABILITY",
        "dispute_fee_income_int": "LIABILITY",
        "transfer_fee_income_int": "LIABILITY",
        "principal_write_off_int": "LIABILITY",
        "interest_write_off_int": "LIABILITY",
    }

    # Defining here for lint purposes
    PURCHASE_INT_PRE_SCOD_UNCHRGD = "PURCHASE_INTEREST_PRE_SCOD_UNCHARGED"
    PURCHASE_INT_POST_SCOD_UNCHRGD = "PURCHASE_INTEREST_POST_SCOD_UNCHARGED"

    BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD = "BALANCE_TRANSFER_REF1_INTEREST_PRE_SCOD_UNCHARGED"
    BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD = "BALANCE_TRANSFER_REF1_INTEREST_POST_SCOD_UNCHARGED"

    BAL_TRAN_REF2_INT_PRE_SCOD_UNCHRGD = "BALANCE_TRANSFER_REF2_INTEREST_PRE_SCOD_UNCHARGED"
    BAL_TRAN_REF2_INT_POST_SCOD_UNCHRGD = "BALANCE_TRANSFER_REF2_INTEREST_POST_SCOD_UNCHARGED"

    def _get_simulation_test_scenario(
        self,
        start,
        end,
        sub_tests,
        template_params=None,
        instance_params=None,
        internal_accounts=None,
    ):
        contract_config = ContractConfig(
            contract_content=self.smart_contract_path_to_content[CONTRACT_FILE],
            template_params=template_params or default_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or default_instance_params,
                )
            ],
        )
        return SimulationTestScenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            contract_config=contract_config,
            internal_accounts=internal_accounts or self.internal_accounts,
        )

    def test_purchase_dispute_smaller_than_mad(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "8000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit_opt_in": "False",
        }
        template_params = {
            **default_template_params,
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Purchase Auth A",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="5000",
                        client_transaction_id="12345",
                        event_datetime=datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), "0"),
                            (BalanceDimensions("AVAILABLE_BALANCE"), "25000"),
                            (BalanceDimensions("PURCHASE_CHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_AUTH"), "5000"),
                            (BalanceDimensions("MAD_BALANCE"), "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Settlement A",
                events=[
                    create_settlement_event(
                        amount="5000",
                        client_transaction_id="12345",
                        final=True,
                        event_datetime=datetime(2019, 1, 10, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 10, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), "5000.00"),
                            (BalanceDimensions("AVAILABLE_BALANCE"), "25000"),
                            (BalanceDimensions("PURCHASE_CHARGED"), ("5000.0")),
                            (BalanceDimensions("PURCHASE_AUTH"), "0"),
                            (BalanceDimensions("MAD_BALANCE"), "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Auth B",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="150",
                        client_transaction_id="23456",
                        event_datetime=datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), "5000"),
                            (BalanceDimensions("AVAILABLE_BALANCE"), "24850"),
                            (BalanceDimensions("PURCHASE_CHARGED"), "5000"),
                            (BalanceDimensions("PURCHASE_AUTH"), "150"),
                            (BalanceDimensions("MAD_BALANCE"), "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Settlement B",
                events=[
                    create_settlement_event(
                        amount="150",
                        client_transaction_id="23456",
                        final=True,
                        event_datetime=datetime(2019, 1, 15, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 15, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5150.00")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), "24850"),
                            (BalanceDimensions("PURCHASE_CHARGED"), ("5150.0")),
                            (BalanceDimensions("PURCHASE_AUTH"), "0"),
                            (BalanceDimensions("MAD_BALANCE"), "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5244.92")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24755.08")),
                            (BalanceDimensions("PURCHASE_CHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_AUTH"), "0"),
                            (BalanceDimensions("PURCHASE_BILLED"), "0"),
                            (BalanceDimensions("PURCHASE_UNPAID"), ("5150.0")),
                            (BalanceDimensions("PURCHASE_INTEREST_CHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_INTEREST_BILLED"), ("94.92")),
                            (BalanceDimensions("MAD_BALANCE"), ("346.42")),
                            (BalanceDimensions("OVERDUE_1"), ("200")),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                "0",
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Transaction B Disputed",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="150", event_datetime=datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC"))
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5094.92")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24905.08")),
                            (BalanceDimensions("PURCHASE_CHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_AUTH"), "0"),
                            (BalanceDimensions("PURCHASE_BILLED"), "0"),
                            (BalanceDimensions("PURCHASE_UNPAID"), ("5094.92")),
                            (BalanceDimensions("PURCHASE_INTEREST_CHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_INTEREST_BILLED"), "0"),
                            (BalanceDimensions("MAD_BALANCE"), ("346.42")),
                            (BalanceDimensions("OVERDUE_1"), ("50")),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                "150",
                            ),
                        ]
                    }
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_purchase_dispute_larger_than_mad(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "8000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit_opt_in": "False",
        }
        template_params = {
            **default_template_params,
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Purchase Auth A",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="5000",
                        client_transaction_id="12345",
                        event_datetime=datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), "0"),
                            (BalanceDimensions("AVAILABLE_BALANCE"), "25000"),
                            (BalanceDimensions("PURCHASE_CHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_AUTH"), "5000"),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Settlement A",
                events=[
                    create_settlement_event(
                        amount="5000",
                        client_transaction_id="12345",
                        final=True,
                        event_datetime=datetime(2019, 1, 10, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 10, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), "5000.00"),
                            (BalanceDimensions("AVAILABLE_BALANCE"), "25000"),
                            (BalanceDimensions("PURCHASE_CHARGED"), ("5000.0")),
                            (BalanceDimensions("PURCHASE_AUTH"), "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Auth B",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="150",
                        client_transaction_id="23456",
                        event_datetime=datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), "5000"),
                            (BalanceDimensions("AVAILABLE_BALANCE"), "24850"),
                            (BalanceDimensions("PURCHASE_CHARGED"), "5000"),
                            (BalanceDimensions("PURCHASE_AUTH"), "150"),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Settlement B",
                events=[
                    create_settlement_event(
                        amount="150",
                        client_transaction_id="23456",
                        final=True,
                        event_datetime=datetime(2019, 1, 15, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 15, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5150.00")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), "24850"),
                            (BalanceDimensions("PURCHASE_CHARGED"), ("5150.0")),
                            (BalanceDimensions("PURCHASE_AUTH"), "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5244.92")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24755.08")),
                            (BalanceDimensions("PURCHASE_CHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_AUTH"), "0"),
                            (BalanceDimensions("PURCHASE_BILLED"), "0"),
                            (BalanceDimensions("PURCHASE_UNPAID"), ("5150.0")),
                            (BalanceDimensions("PURCHASE_INTEREST_CHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_INTEREST_BILLED"), ("94.92")),
                            (BalanceDimensions("MAD_BALANCE"), ("346.42")),
                            (BalanceDimensions("OVERDUE_1"), ("200")),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                "0",
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Transaction A Disputed",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("244.92")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("29755.08")),
                            (BalanceDimensions("PURCHASE_CHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_AUTH"), "0"),
                            (BalanceDimensions("PURCHASE_BILLED"), "0"),
                            (BalanceDimensions("PURCHASE_UNPAID"), ("244.92")),
                            (BalanceDimensions("PURCHASE_INTEREST_CHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_INTEREST_BILLED"), "0"),
                            (BalanceDimensions("MAD_BALANCE"), ("346.42")),
                            (BalanceDimensions("OVERDUE_1"), "0"),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                "5000",
                            ),
                        ]
                    }
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_cash_advance_dispute_smaller_than_mad(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "8000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit_opt_in": "False",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Cash Advance A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5100")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24900")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), "5000"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"), ("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance B",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="150",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5374.65")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24650")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), ("5150")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                ("24.65"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"), ("200")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5461.01")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24538.99")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), ("5150")),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"), "0"),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                ("111.01"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_FEES_BILLED"), ("200")),
                            (BalanceDimensions("MAD_BALANCE"), ("362.51")),
                            (BalanceDimensions("OVERDUE_1"), "0"),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                "0",
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5603.25")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24396.75")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), ("5150.0")),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"), "0"),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                ("142.24"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                ("111.01"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_FEES_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"), ("200")),
                            (BalanceDimensions("MAD_BALANCE"), ("867.26")),
                            (BalanceDimensions("OVERDUE_1"), ("362.51")),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                "0",
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Transaction B Disputed",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="150", event_datetime=datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC"))
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5453.25")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24546.75")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), ("5150.0")),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"), "0"),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                ("103.25"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"), ("200")),
                            (BalanceDimensions("MAD_BALANCE"), ("867.26")),
                            (BalanceDimensions("OVERDUE_1"), ("212.51")),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                "150",
                            ),
                        ]
                    }
                },
            ),
        ]
        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_cash_advance_dispute_larger_than_mad(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "8000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit_opt_in": "False",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Cash Advance A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5100")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24900")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), "5000"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"), ("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance B",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="150",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5374.65")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24650")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), ("5150")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                ("24.65"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"), ("200")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5603.25")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24396.75")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), ("5150.0")),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"), "0"),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                ("142.24"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                ("111.01"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"), ("200")),
                            (BalanceDimensions("MAD_BALANCE"), ("867.26")),
                            (BalanceDimensions("OVERDUE_1"), ("362.51")),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                "0",
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Transaction A Disputed",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("603.25")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("29396.75")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), ("603.25")),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"), "0"),
                            (BalanceDimensions("MAD_BALANCE"), ("867.26")),
                            (BalanceDimensions("OVERDUE_1"), "0"),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                "5000",
                            ),
                        ]
                    }
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_cash_advance_and_fees_dispute(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, 1, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "8000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit_opt_in": "False",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Cash Advance A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5100")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24900")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), "5000"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"), ("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance B",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="150",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5374.65")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24650")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), ("5150")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                ("24.65"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"), ("200")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5603.25")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24396.75")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), ("5150.0")),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"), "0"),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                ("142.24"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                ("111.01"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"), ("200")),
                            (BalanceDimensions("MAD_BALANCE"), ("867.26")),
                            (BalanceDimensions("OVERDUE_1"), ("362.51")),
                            (BalanceDimensions("OVERDUE_2"), "0"),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                "0",
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Transaction B Disputed",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=datetime(2019, 3, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5453.25")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24546.75")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), ("5150.0")),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"), "0"),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                ("103.25"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"), ("200")),
                            (BalanceDimensions("MAD_BALANCE"), ("867.26")),
                            (BalanceDimensions("OVERDUE_1"), ("212.51")),
                            (BalanceDimensions("OVERDUE_2"), "0"),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                "150",
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Transaction B Fee Disputed",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=datetime(2019, 3, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5353.25")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24646.75")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), ("5150.0")),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"), "0"),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                ("3.25"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"), ("200")),
                            (BalanceDimensions("MAD_BALANCE"), ("867.26")),
                            (BalanceDimensions("OVERDUE_1"), ("112.51")),
                            (BalanceDimensions("OVERDUE_2"), "0"),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                ("250"),
                            ),
                        ]
                    }
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_cash_advance_fees_only_dispute(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, 1, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "6000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit_opt_in": "False",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Cash Advance A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5100")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24900")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), "5000"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"), ("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance B",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="150",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5374.65")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24650")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), ("5150")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                ("24.65"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"), ("200")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5461.01")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24538.99")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), ("5150.0")),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"), "0"),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                ("111.01"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), ("362.51")),
                            (BalanceDimensions("OVERDUE_1"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_BILLED"), ("200")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5603.25")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24396.75")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), ("5150.0")),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"), "0"),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                ("142.24"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                ("111.01"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), ("867.26")),
                            (BalanceDimensions("OVERDUE_1"), ("362.51")),
                            (BalanceDimensions("OVERDUE_2"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"), ("200")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Transaction B Fee Disputed",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=datetime(2019, 3, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5503.25")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24496.75")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), ("5150.0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                "0",
                            ),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"), "0"),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                ("142.24"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                ("11.01"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), ("867.26")),
                            (BalanceDimensions("OVERDUE_1"), ("262.51")),
                            (BalanceDimensions("OVERDUE_2"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"), ("200")),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                ("100"),
                            ),
                        ]
                    }
                },
            ),
        ]
        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_purchase_dispute_larger_than_full_overdue_amount(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 5, 23, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "8000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit_opt_in": "False",
        }
        template_params = {
            **default_template_params,
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Purchase Auth A",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="1000",
                        client_transaction_id="123456",
                        event_datetime=datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), "0"),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("29000")),
                            (BalanceDimensions("PURCHASE_AUTH"), ("1000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Settlement A",
                events=[
                    create_settlement_event(
                        amount="1000",
                        client_transaction_id="123456",
                        final=True,
                        event_datetime=datetime(2019, 1, 10, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 10, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("1000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("29000")),
                            (BalanceDimensions("PURCHASE_AUTH"), "0"),
                            (BalanceDimensions("PURCHASE_CHARGED"), ("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances",
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("1038.94")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("28961.06")),
                            (BalanceDimensions("PURCHASE_AUTH"), "0"),
                            (BalanceDimensions("PURCHASE_CHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_BILLED"), "0"),
                            (BalanceDimensions("PURCHASE_UNPAID"), ("1000.0")),
                            (BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_INTEREST_CHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_INTEREST_BILLED"), ("20.46")),
                            (BalanceDimensions("MAD_BALANCE"), ("277.42")),
                            (BalanceDimensions("OVERDUE_1"), ("28.48")),
                            (BalanceDimensions("OVERDUE_2"), ("200")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Auth B",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="5000",
                        client_transaction_id="23456",
                        event_datetime=datetime(2019, 4, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("1038.94")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("23961.06")),
                            (BalanceDimensions("PURCHASE_AUTH"), "5000"),
                            (BalanceDimensions("PURCHASE_CHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_BILLED"), "0"),
                            (BalanceDimensions("PURCHASE_UNPAID"), ("1000.0")),
                            (BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_INTEREST_CHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_INTEREST_BILLED"), ("20.46")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Settlement B",
                events=[
                    create_settlement_event(
                        amount="5000",
                        client_transaction_id="23456",
                        final=True,
                        event_datetime=datetime(2019, 4, 1, 3, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 3, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("6038.94")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("23961.06")),
                            (BalanceDimensions("PURCHASE_AUTH"), "0"),
                            (BalanceDimensions("PURCHASE_CHARGED"), "5000"),
                            (BalanceDimensions("PURCHASE_BILLED"), "0"),
                            (BalanceDimensions("PURCHASE_UNPAID"), ("1000.0")),
                            (BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_INTEREST_CHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_INTEREST_BILLED"), ("20.46")),
                            (BalanceDimensions("MAD_BALANCE"), ("277.42")),
                            (BalanceDimensions("OVERDUE_1"), ("28.48")),
                            (BalanceDimensions("OVERDUE_2"), ("200")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Transaction B Disputed",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=datetime(2019, 4, 5, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 4, 5, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("1054.74")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("28961.06")),
                            (BalanceDimensions("PURCHASE_AUTH"), "0"),
                            (BalanceDimensions("PURCHASE_CHARGED"), ("1038.94")),
                            (BalanceDimensions("PURCHASE_BILLED"), "0"),
                            (BalanceDimensions("PURCHASE_UNPAID"), "0"),
                            (BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_INTEREST_CHARGED"), ("15.80")),
                            (BalanceDimensions("PURCHASE_INTEREST_BILLED"), "0"),
                            (BalanceDimensions("MAD_BALANCE"), ("277.42")),
                            (BalanceDimensions("OVERDUE_1"), "0"),
                            (BalanceDimensions("OVERDUE_2"), "0"),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                "5000",
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check Balances",
                expected_balances_at_ts={
                    datetime(2019, 5, 23, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("1087.38")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("28927.58")),
                            (BalanceDimensions("PURCHASE_AUTH"), "0"),
                            (BalanceDimensions("PURCHASE_CHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_BILLED"), "0"),
                            (BalanceDimensions("PURCHASE_UNPAID"), ("1038.94")),
                            (BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_INTEREST_CHARGED"), ("14.96")),
                            (BalanceDimensions("PURCHASE_INTEREST_BILLED"), "0"),
                            (BalanceDimensions("MAD_BALANCE"), ("200.00")),
                            (BalanceDimensions("OVERDUE_1"), ("200")),
                            (BalanceDimensions("OVERDUE_2"), "0"),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                "0",
                            ),
                        ]
                    }
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_failed_purchase_dispute_int(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 2, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "8000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit_opt_in": "False",
        }
        template_params = {
            **default_template_params,
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Purchase Auth A",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="5000",
                        client_transaction_id="12345",
                        event_datetime=datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), "0"),
                            (BalanceDimensions("AVAILABLE_BALANCE"), "25000"),
                            (BalanceDimensions("PURCHASE_CHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_AUTH"), "5000"),
                            (BalanceDimensions("MAD_BALANCE"), "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Settlement A",
                events=[
                    create_settlement_event(
                        amount="5000",
                        client_transaction_id="12345",
                        final=True,
                        event_datetime=datetime(2019, 1, 10, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 10, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), "5000.00"),
                            (BalanceDimensions("AVAILABLE_BALANCE"), "25000"),
                            (BalanceDimensions("PURCHASE_CHARGED"), ("5000.0")),
                            (BalanceDimensions("PURCHASE_AUTH"), "0"),
                            (BalanceDimensions("MAD_BALANCE"), "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Auth B",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="150",
                        client_transaction_id="23456",
                        event_datetime=datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), "5000"),
                            (BalanceDimensions("AVAILABLE_BALANCE"), "24850"),
                            (BalanceDimensions("PURCHASE_CHARGED"), "5000"),
                            (BalanceDimensions("PURCHASE_AUTH"), "150"),
                            (BalanceDimensions("MAD_BALANCE"), "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Settlement B",
                events=[
                    create_settlement_event(
                        amount="150",
                        client_transaction_id="23456",
                        final=True,
                        event_datetime=datetime(2019, 1, 15, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 15, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5150.00")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), "24850"),
                            (BalanceDimensions("PURCHASE_CHARGED"), ("5150.0")),
                            (BalanceDimensions("PURCHASE_AUTH"), "0"),
                            (BalanceDimensions("MAD_BALANCE"), "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5244.92")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24755.08")),
                            (BalanceDimensions("PURCHASE_CHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_AUTH"), "0"),
                            (BalanceDimensions("PURCHASE_BILLED"), "0"),
                            (BalanceDimensions("PURCHASE_UNPAID"), ("5150.0")),
                            (BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_INTEREST_CHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_INTEREST_BILLED"), ("94.92")),
                            (BalanceDimensions("MAD_BALANCE"), ("346.42")),
                            (BalanceDimensions("OVERDUE_1"), ("200")),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                "0",
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase A Disputed",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("244.92")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("29755.08")),
                            (BalanceDimensions("PURCHASE_CHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_AUTH"), "0"),
                            (BalanceDimensions("PURCHASE_BILLED"), "0"),
                            (BalanceDimensions("PURCHASE_UNPAID"), ("244.92")),
                            (BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_INTEREST_CHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_INTEREST_BILLED"), "0"),
                            (BalanceDimensions("MAD_BALANCE"), ("346.42")),
                            (BalanceDimensions("OVERDUE_1"), "0"),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                "5000",
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase A Dispute failed",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=datetime(2019, 3, 2, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 2, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5245.08")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24755.08")),
                            (BalanceDimensions("PURCHASE_CHARGED"), ("5000.0")),
                            (BalanceDimensions("PURCHASE_AUTH"), "0"),
                            (BalanceDimensions("PURCHASE_BILLED"), "0"),
                            (BalanceDimensions("PURCHASE_UNPAID"), ("244.92")),
                            (BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_INTEREST_CHARGED"), ("0.16")),
                            (BalanceDimensions("PURCHASE_INTEREST_BILLED"), "0"),
                            (BalanceDimensions("MAD_BALANCE"), ("346.42")),
                            (BalanceDimensions("OVERDUE_1"), "0"),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                "5000",
                            ),
                            (BalanceDimensions("DISPUTE_FEES_CHARGED"), "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="Dispute fee charged",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        instruction_details={"fee_type": "DISPUTE_FEE"},
                        event_datetime=datetime(2019, 3, 2, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 2, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5345.08")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24655.08")),
                            (BalanceDimensions("PURCHASE_CHARGED"), ("5000.0")),
                            (BalanceDimensions("PURCHASE_AUTH"), "0"),
                            (BalanceDimensions("PURCHASE_BILLED"), "0"),
                            (BalanceDimensions("PURCHASE_UNPAID"), ("244.92")),
                            (BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_INTEREST_CHARGED"), ("0.16")),
                            (BalanceDimensions("PURCHASE_INTEREST_BILLED"), "0"),
                            (BalanceDimensions("MAD_BALANCE"), ("346.42")),
                            (BalanceDimensions("OVERDUE_1"), "0"),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                "5000",
                            ),
                            (BalanceDimensions("DISPUTE_FEES_CHARGED"), ("100")),
                        ]
                    }
                },
            ),
        ]
        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_failed_cash_advance_dispute(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 2, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "8000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit_opt_in": "False",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Cash Advance A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5100")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24900")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), "5000"),
                            (BalanceDimensions("MAD_BALANCE"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"), ("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance B",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="150",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5374.65")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24650")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), ("5150")),
                            (BalanceDimensions("MAD_BALANCE"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"), ("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                ("24.65"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5603.25")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24396.75")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), ("5150.0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                "0",
                            ),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"), "0"),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                ("142.24"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                ("111.01"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), ("867.26")),
                            (BalanceDimensions("OVERDUE_1"), ("362.51")),
                            (BalanceDimensions("OVERDUE_2"), "0"),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                "0",
                            ),
                            (BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"), ("200")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance B Disputed",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="150", event_datetime=datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC"))
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5453.25")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24546.75")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), ("5150.0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                "0",
                            ),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"), "0"),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                ("103.25"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"), "0"),
                            (BalanceDimensions("MAD_BALANCE"), ("867.26")),
                            (BalanceDimensions("OVERDUE_1"), ("212.51")),
                            (BalanceDimensions("OVERDUE_2"), "0"),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                "150",
                            ),
                            (BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"), ("200")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance B Dispute failed",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="150",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 3, 2, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 2, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("5708.33")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24296.75")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), "150"),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), ("5150")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                ("5.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                ("103.25"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"), "0"),
                            (BalanceDimensions("MAD_BALANCE"), ("867.26")),
                            (BalanceDimensions("OVERDUE_1"), ("212.51")),
                            (BalanceDimensions("OVERDUE_2"), "0"),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                "150",
                            ),
                            (BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"), ("100")),
                            (BalanceDimensions("CASH_ADVANCE_FEES_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"), ("200")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Dispute fee charged",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        instruction_details={"fee_type": "DISPUTE_FEE"},
                        event_datetime=datetime(2019, 3, 2, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 2, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            # DEFAULT double counts the fee until we build fee GL postings
                            (BalanceDimensions("DEFAULT"), ("5808.33")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("24196.75")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), "150"),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), ("5150")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                ("5.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                ("103.25"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"), "0"),
                            (BalanceDimensions("MAD_BALANCE"), ("867.26")),
                            (BalanceDimensions("OVERDUE_1"), ("212.51")),
                            (BalanceDimensions("OVERDUE_2"), "0"),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                "150",
                            ),
                            (BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"), ("100")),
                            (BalanceDimensions("CASH_ADVANCE_FEES_BILLED"), "0"),
                            (BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"), ("200")),
                            (BalanceDimensions("DISPUTE_FEES_CHARGED"), ("100")),
                        ]
                    }
                },
            ),
        ]
        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_mad_eq_statement_balance_if_dpd_gt_90_auth_settle_10000_int(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 6, 1, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "8000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit_opt_in": "False",
        }
        template_params = {
            **default_template_params,
            "mad_as_full_statement_flags": '["OVER_90_DPD"]',
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Purchase Auth A",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10000",
                        client_transaction_id="12345",
                        event_datetime=datetime(2019, 1, 5, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 5, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), "0"),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("20000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_AUTH"), ("10000")),
                            (BalanceDimensions("MAD_BALANCE"), "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Settlement A",
                events=[
                    create_settlement_event(
                        amount="10000",
                        client_transaction_id="12345",
                        final=True,
                        event_datetime=datetime(2019, 1, 5, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 5, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("10000.00")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("20000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), ("10000.0")),
                            (BalanceDimensions("PURCHASE_AUTH"), "0"),
                            (BalanceDimensions("MAD_BALANCE"), "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement A",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("10000.00")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("20000")),
                            (BalanceDimensions("PURCHASE_BILLED"), ("10000.0")),
                            (BalanceDimensions("MAD_BALANCE"), ("200")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement B",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("10184.24")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("19815.76")),
                            (BalanceDimensions("PURCHASE_UNPAID"), ("10000.0")),
                            (BalanceDimensions("PURCHASE_INTEREST_BILLED"), ("184.24")),
                            (BalanceDimensions("MAD_BALANCE"), ("484.24")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement C",
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("10388.22")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("19611.78")),
                            (BalanceDimensions("PURCHASE_UNPAID"), ("10000.0")),
                            (BalanceDimensions("PURCHASE_INTEREST_BILLED"), ("203.98")),
                            (BalanceDimensions("PURCHASE_INTEREST_UNPAID"), ("184.24")),
                            (BalanceDimensions("MAD_BALANCE"), ("972.46")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement D",
                expected_balances_at_ts={
                    datetime(2019, 5, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("10585.62")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("19414.38")),
                            (BalanceDimensions("PURCHASE_UNPAID"), ("10000.0")),
                            (BalanceDimensions("PURCHASE_INTEREST_BILLED"), ("197.40")),
                            (BalanceDimensions("PURCHASE_INTEREST_UNPAID"), ("388.22")),
                            (BalanceDimensions("MAD_BALANCE"), ("1658.08")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Set 90 DPD Flag",
                events=[
                    create_flag_definition_event(
                        timestamp=datetime(2019, 5, 23, tzinfo=ZoneInfo("UTC")),
                        flag_definition_id="OVER_90_DPD",
                    ),
                    create_flag_event(
                        flag_definition_id="OVER_90_DPD",
                        timestamp=datetime(2019, 5, 23, tzinfo=ZoneInfo("UTC")),
                        expiry_timestamp=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
                        account_id="Main account",
                    ),
                ],
            ),
            SubTest(
                description="Statement E",
                expected_balances_at_ts={
                    datetime(2019, 6, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("10789.6")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("19210.40")),
                            (BalanceDimensions("PURCHASE_UNPAID"), ("10000.0")),
                            (BalanceDimensions("PURCHASE_INTEREST_BILLED"), ("203.98")),
                            (BalanceDimensions("PURCHASE_INTEREST_UNPAID"), ("585.62")),
                            (BalanceDimensions("MAD_BALANCE"), ("10789.60")),
                        ]
                    }
                },
            ),
        ]
        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_mad_eq_statement_balance_if_dpd_gt_90_auth_settle_100_int(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 6, 1, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "8000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit_opt_in": "False",
        }
        template_params = {
            **default_template_params,
            "mad_as_full_statement_flags": '["OVER_90_DPD"]',
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Purchase Auth A",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="100",
                        client_transaction_id="12345",
                        event_datetime=datetime(2019, 1, 5, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 5, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), "0"),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("29900")),
                            (BalanceDimensions("PURCHASE_CHARGED"), "0"),
                            (BalanceDimensions("PURCHASE_AUTH"), ("100")),
                            (BalanceDimensions("MAD_BALANCE"), "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Settlement A",
                events=[
                    create_settlement_event(
                        amount="100",
                        client_transaction_id="12345",
                        final=True,
                        event_datetime=datetime(2019, 1, 5, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 5, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("100")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("29900")),
                            (BalanceDimensions("PURCHASE_CHARGED"), ("100")),
                            (BalanceDimensions("PURCHASE_AUTH"), "0"),
                            (BalanceDimensions("MAD_BALANCE"), "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement A",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("100")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("29900")),
                            (BalanceDimensions("PURCHASE_BILLED"), ("100")),
                            (BalanceDimensions("MAD_BALANCE"), ("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement B",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("101.96")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("29898.04")),
                            (BalanceDimensions("PURCHASE_UNPAID"), ("100")),
                            (BalanceDimensions("PURCHASE_INTEREST_BILLED"), ("1.96")),
                            (BalanceDimensions("MAD_BALANCE"), ("101.96")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement C",
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("104.13")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("29895.87")),
                            (BalanceDimensions("PURCHASE_UNPAID"), ("100")),
                            (BalanceDimensions("PURCHASE_INTEREST_BILLED"), ("2.17")),
                            (BalanceDimensions("PURCHASE_INTEREST_UNPAID"), ("1.96")),
                            (BalanceDimensions("MAD_BALANCE"), ("104.13")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement D",
                expected_balances_at_ts={
                    datetime(2019, 5, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("106.23")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("29893.77")),
                            (BalanceDimensions("PURCHASE_UNPAID"), ("100")),
                            (BalanceDimensions("PURCHASE_INTEREST_BILLED"), ("2.10")),
                            (BalanceDimensions("PURCHASE_INTEREST_UNPAID"), ("4.13")),
                            (BalanceDimensions("MAD_BALANCE"), ("106.23")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Set 90 DPD Flag",
                events=[
                    create_flag_definition_event(
                        timestamp=datetime(2019, 5, 30, tzinfo=ZoneInfo("UTC")),
                        flag_definition_id="OVER_90_DPD",
                    ),
                    create_flag_event(
                        flag_definition_id="OVER_90_DPD",
                        timestamp=datetime(2019, 5, 30, tzinfo=ZoneInfo("UTC")),
                        expiry_timestamp=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
                        account_id="Main account",
                    ),
                ],
            ),
            SubTest(
                description="Statement E",
                expected_balances_at_ts={
                    datetime(2019, 6, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("108.4")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("29891.60")),
                            (BalanceDimensions("PURCHASE_UNPAID"), ("100")),
                            (BalanceDimensions("PURCHASE_INTEREST_BILLED"), ("2.17")),
                            (BalanceDimensions("PURCHASE_INTEREST_UNPAID"), ("6.23")),
                            (BalanceDimensions("MAD_BALANCE"), ("108.40")),
                        ]
                    }
                },
            ),
        ]
        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_mad_eq_zero_if_positive_balance_on_closure(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC"))

        flags = '["OVER_90_DPD", "ACCOUNT_CLOSURE_REQUESTED"]'

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "8000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit_opt_in": "False",
        }
        template_params = {
            **default_template_params,
            "mad_as_full_statement_flags": flags,
        }

        sub_tests = [
            SubTest(
                description="Repay",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 5, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Set account closure request Flag",
                events=[
                    create_flag_definition_event(
                        timestamp=datetime(2019, 2, 11, 13, tzinfo=ZoneInfo("UTC")),
                        flag_definition_id="ACCOUNT_CLOSURE_REQUESTED",
                    ),
                    create_flag_event(
                        flag_definition_id="ACCOUNT_CLOSURE_REQUESTED",
                        timestamp=datetime(2019, 2, 11, 13, tzinfo=ZoneInfo("UTC")),
                        expiry_timestamp=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
                        account_id="Main account",
                    ),
                ],
            ),
            SubTest(
                description="Statement A",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("-1000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("31000")),
                            (BalanceDimensions("MAD_BALANCE"), "0"),
                        ]
                    }
                },
            ),
        ]
        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_mad_eq_statement_balance_on_closure_request(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC"))

        flags = '["OVER_90_DPD", "ACCOUNT_CLOSURE_REQUESTED"]'

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "8000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit_opt_in": "False",
        }
        template_params = {
            **default_template_params,
            "mad_as_full_statement_flags": flags,
        }

        sub_tests = [
            SubTest(
                description="Cash Advance A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 5, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 5, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("1100")),
                            (BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"), ("100")),
                            (BalanceDimensions("MAD_BALANCE"), "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement A",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("1126.73")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("28873.27")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), ("1000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                ("26.73"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_FEES_BILLED"), ("100")),
                            (BalanceDimensions("MAD_BALANCE"), ("200")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Set account closure request Flag",
                events=[
                    create_flag_definition_event(
                        timestamp=datetime(2019, 2, 11, 13, tzinfo=ZoneInfo("UTC")),
                        flag_definition_id="ACCOUNT_CLOSURE_REQUESTED",
                    ),
                    create_flag_event(
                        flag_definition_id="ACCOUNT_CLOSURE_REQUESTED",
                        timestamp=datetime(2019, 2, 11, 13, tzinfo=ZoneInfo("UTC")),
                        expiry_timestamp=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
                        account_id="Main account",
                    ),
                ],
            ),
            SubTest(
                description="Statement B",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), ("1154.45")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), ("28845.55")),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), ("1000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                ("27.72"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                ("26.73"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"), ("100")),
                            (BalanceDimensions("MAD_BALANCE"), ("1154.45")),
                        ]
                    }
                },
            ),
        ]
        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_account_created_29_feb_after_23_50_schedule_triggered(self):
        """
        - Spend and accrue from day after SCOD
        - repay before the due date
        - cancel interest charge for positive balance
        - next scod - no interest billed
        """
        start = datetime(2020, 2, 29, 23, 57, tzinfo=ZoneInfo("UTC"))
        end = datetime(2021, 3, 31, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Annual Fee 1 Charged",
                expected_balances_at_ts={
                    datetime(2020, 3, 1, 23, 55, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("ANNUAL_FEES_CHARGED"),
                                ("100"),
                            )
                        ]
                    }
                },
            ),
            SubTest(
                description="Annual Fee 1 Statement",
                expected_balances_at_ts={
                    datetime(2020, 3, 31, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("STATEMENT_BALANCE"), ("100")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), ("100")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), ("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay and check balance",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100", event_datetime=datetime(2020, 4, 1, tzinfo=ZoneInfo("UTC"))
                    )
                ],
                expected_balances_at_ts={
                    datetime(2020, 4, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("ANNUAL_FEES_CHARGED"), "0"),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), "0"),
                            (BalanceDimensions("ANNUAL_FEES_UNPAID"), "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="Annual Fee 2 Charged",
                expected_balances_at_ts={
                    datetime(2021, 2, 28, 23, 55, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("STATEMENT_BALANCE"), "0"),
                            (BalanceDimensions("ANNUAL_FEES_CHARGED"), ("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Annual Fee 2 Statement",
                expected_balances_at_ts={
                    datetime(2021, 3, 31, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("STATEMENT_BALANCE"), ("100")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), ("100")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), ("100")),
                        ]
                    }
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_mad_eq_zero_flag_takes_precedence_over_mad_eq_statement_flag(self):
        """
        Set both mad_equal_to_zero_flags and mad_as_full_statement_flags active.
        See that MAD is calculated to be 0 on SCOD.

            instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()
        """
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 6, 1, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
        }
        template_params = {
            **default_template_params,
            "mad_as_full_statement_flags": '["OVER_90_DPD"]',
            "mad_equal_to_zero_flags": '["REPAYMENT_HOLIDAY"]',
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000", event_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
                    )
                ],
            ),
            SubTest(
                description="Set Repayment Holiday Flag",
                events=[
                    create_flag_definition_event(
                        timestamp=datetime(2019, 5, 30, tzinfo=ZoneInfo("UTC")),
                        flag_definition_id="REPAYMENT_HOLIDAY",
                    ),
                    create_flag_event(
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        timestamp=datetime(2019, 5, 30, tzinfo=ZoneInfo("UTC")),
                        expiry_timestamp=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
                        account_id="Main account",
                    ),
                ],
            ),
            SubTest(
                description="Set 90 DPD Flag",
                events=[
                    create_flag_definition_event(
                        timestamp=datetime(2019, 5, 30, tzinfo=ZoneInfo("UTC")),
                        flag_definition_id="OVER_90_DPD",
                    ),
                    create_flag_event(
                        flag_definition_id="OVER_90_DPD",
                        timestamp=datetime(2019, 5, 30, tzinfo=ZoneInfo("UTC")),
                        expiry_timestamp=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
                        account_id="Main account",
                    ),
                ],
            ),
            SubTest(
                description="SCOD 6",
                expected_balances_at_ts={
                    datetime(2019, 6, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("PURCHASE_UNPAID"), ("2000")),
                            (BalanceDimensions("PURCHASE_INTEREST_UNPAID"), ("117.48")),
                            (BalanceDimensions("MAD_BALANCE"), "0"),
                            (BalanceDimensions("OVERDUE_1"), ("537.48")),
                            (BalanceDimensions("OVERDUE_2"), ("397.88")),
                            (BalanceDimensions("OVERDUE_3"), ("256.96")),
                            (BalanceDimensions("OVERDUE_4"), ("200")),
                        ]
                    }
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)
