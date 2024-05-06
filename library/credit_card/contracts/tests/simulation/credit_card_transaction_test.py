# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
from decimal import Decimal
from json import dumps
from datetime import date, datetime
from unittest import skip
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.contracts.simulation.utils import (
    SimulationTestCase,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_outbound_hard_settlement_instruction,
    create_inbound_hard_settlement_instruction,
    create_transfer_instruction,
    create_instance_parameter_change_event,
    create_settlement_event,
    create_outbound_authorisation_instruction,
    create_posting_instruction_batch,
    create_release_event,
    create_auth_adjustment_instruction,
)
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    SimulationTestScenario,
    SubTest,
    ContractConfig,
    AccountConfig,
)
from inception_sdk.vault.postings.posting_classes import OutboundHardSettlement, Transfer
from library.credit_card.contracts.tests.utils.simulation.lending import (
    DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS,
    DEFAULT_CREDIT_CARD_INSTANCE_PARAMS,
    default_template_update,
)
from library.credit_card.contracts.tests.utils.simulation.common import (
    offset_datetime,
    check_postings_correct_after_simulation,
)

CONTRACT_FILE = "library/credit_card/contracts/credit_card.py"
EXPIRE_INTEREST_FREE_PERIODS_WORKFLOW = "EXPIRE_INTEREST_FREE_PERIODS"
ASSET_CONTRACT_FILE = "internal_accounts/testing_internal_asset_account_contract.py"
LIABILITY_CONTRACT_FILE = "internal_accounts/testing_internal_liability_account_contract.py"
CONTRACT_FILES = [CONTRACT_FILE, ASSET_CONTRACT_FILE, LIABILITY_CONTRACT_FILE]
DEFAULT_DENOM = "GBP"
EXPIRE_INTEREST_FREE_PERIODS_WORKFLOW = "EXPIRE_INTEREST_FREE_PERIODS"
PUBLISH_STATEMENT_DATA_WORKFLOW = "PUBLISH_STATEMENT_DATA"
REVOCABLE_COMMITMENT_INT = "1"
OFF_BALANCE_SHEET_CONTRA_INT = "1"
OTHER_LIABILITY_INT = "1"
DISPUTE_FEE_LOAN_INT = "1"
LOAN_INT = "0"
INCOME_INT = "1"
ANNUAL_FEE_LOAN_INT = "1"
ANNUAL_FEE_INCOME_INT = "1"
AIR_INT = "1"
INTEREST_INCOME_INT = "1"
OTHER_LIABILITY_INT = "1"


class CreditCardTransactionTest(SimulationTestCase):
    """
    Test preposting hook, rebalancing fees, overlimit, credit limit
    """

    contract_filepaths = [CONTRACT_FILE]

    default_instance_params = DEFAULT_CREDIT_CARD_INSTANCE_PARAMS
    default_template_params = DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS

    internal_accounts = {
        "off_balance_sheet_contra_int": "LIABILITY",
        "revocable_commitment_int": "LIABILITY",
        "annual_fee_loan_int": "LIABILITY",
        "annual_fee_income_int": "LIABILITY",
        "purchase_loan_int": "LIABILITY",
        "1": "LIABILITY",
        "Dummy account": "LIABILITY",
        "customer_deposits_int": "LIABILITY",
        "other_liability_int": "LIABILITY",
        "Internal account": "LIABILITY",
        "purchase_air_int": "LIABILITY",
        "late_repayment_fee_loan_int": "LIABILITY",
        "late_repayment_fee_income_int": "LIABILITY",
        "purchase_interest_income_int": "LIABILITY",
        "cash_advance_loan_int": "LIABILITY",
        "cash_advance_fee_loan_int": "LIABILITY",
        "cash_advance_fee_income_int": "LIABILITY",
        "atm_withdrawal_fee_loan_int": "LIABILITY",
        "casa_account_id": "LIABILITY",
        "overlimit_fee_loan_int": "LIABILITY",
        "overlimit_fee_income_int": "LIABILITY",
        "transfer_loan_int": "LIABILITY",
        "cash_advance_air_int": "LIABILITY",
        "cash_advance_interest_income_int": "LIABILITY",
        "dispute_fee_loan_int": "LIABILITY",
        "dispute_fee_income_int": "LIABILITY",
        "transfer_fee_loan_int": "LIABILITY",
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
            contract_file_path=CONTRACT_FILE,
            template_params=template_params or self.default_template_params,
            account_configs=[
                AccountConfig(instance_params=instance_params or self.default_instance_params)
            ],
        )

        return SimulationTestScenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            contract_config=contract_config,
            internal_accounts=internal_accounts or self.internal_accounts,
        )

    def test_transaction_type_fees_charged_on_settlement_and_billed_at_scod(self):
        """
        A cash advance is authorised. When it is settled, fees are charged. After Scod, fees are
        billed
        """
        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 1, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["annual_fee"] = "0"
        template_params["transaction_types"] = default_template_update(
            "transaction_types",
            {"cash_advance": {"charge_interest_from_transaction_date": "False"}},
        )

        sub_tests = [
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        "200",
                        client_transaction_id="1234",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("1800")),
                            (BalanceDimensions("CASH_ADVANCE_AUTH"), Decimal(200)),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal(0),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Settle - fees charged",
                events=[
                    create_settlement_event(
                        amount="200",
                        final=True,
                        event_datetime=offset_datetime(2019, 1, 31, 1),
                        client_transaction_id="1234",
                        instruction_details={"transaction_code": "aaa"},
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 31, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal(1790)),
                            (BalanceDimensions("CASH_ADVANCE_AUTH"), Decimal(0)),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal(200)),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal(10),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="SCOD - fees billed",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal(1790)),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal(200)),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal(10),
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

    def test_multiple_spend_type_and_txn_fees_and_auth_settlement_before_scod(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 1, 25)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["annual_fee"] = "0"
        instance_params["transaction_type_fees"] = dumps(
            {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.02",
                    "flat_fee": "100",
                },
                "transfer": {
                    "over_deposit_only": "True",
                    "percentage_fee": "0.02",
                    "flat_fee": "100",
                },
            }
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "6000"}})

        template_params["transaction_types"] = default_template_update(
            "transaction_types",
            {"cash_advance": {"charge_interest_from_transaction_date": "False"}},
        )

        sub_tests = [
            SubTest(
                description="Auth A",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="1000",
                        client_transaction_id="A",
                        event_datetime=offset_datetime(2019, 1, 5),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 5): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("29000")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("0")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Settle A",
                events=[
                    create_settlement_event(
                        amount="1000",
                        final=True,
                        client_transaction_id="A",
                        event_datetime=offset_datetime(2019, 1, 7),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 7): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("29000")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("1000")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="6000",
                        event_datetime=offset_datetime(2019, 1, 10),
                        instruction_details={"transaction_code": "aaa"},
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 10): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("22880")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("7120")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("7120"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1500", event_datetime=offset_datetime(2019, 1, 15)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 15): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("24380")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("5620")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("5620"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Auth B",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="2000",
                        client_transaction_id="B",
                        event_datetime=offset_datetime(2019, 1, 20),
                    ),
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 20): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("22380")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("5620")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("5620"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Settle B",
                events=[
                    create_settlement_event(
                        amount="2000",
                        final=True,
                        event_datetime=offset_datetime(2019, 1, 25),
                        client_transaction_id="B",
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 25): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("22380")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("7620")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("7620"),
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

    def test_auth_reversal_and_settle(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 1, 6)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["annual_fee"] = "0"

        sub_tests = [
            SubTest(
                description="Initial Auths",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="1000",
                        client_transaction_id="A",
                        event_datetime=offset_datetime(2019, 1, 1, 1),
                    ),
                    create_outbound_authorisation_instruction(
                        amount="2000",
                        client_transaction_id="B",
                        event_datetime=offset_datetime(2019, 1, 1, 1),
                    ),
                    create_outbound_authorisation_instruction(
                        amount="3000",
                        client_transaction_id="C",
                        event_datetime=offset_datetime(2019, 1, 1, 1),
                    ),
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("24000")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("0")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Release A",
                events=[
                    create_release_event(
                        client_transaction_id="A",
                        event_datetime=offset_datetime(2019, 1, 2),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 2): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("25000")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("0")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Auth Adjust B",
                events=[
                    create_auth_adjustment_instruction(
                        amount="-500",
                        client_transaction_id="B",
                        event_datetime=offset_datetime(2019, 1, 3),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 3): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("25500")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("0")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Auth Adjust C",
                events=[
                    create_auth_adjustment_instruction(
                        amount="-1000",
                        client_transaction_id="C",
                        event_datetime=offset_datetime(2019, 1, 4),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 4): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("26500")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("0")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Settle B",
                events=[
                    create_settlement_event(
                        amount="1500",
                        final=True,
                        event_datetime=offset_datetime(2019, 1, 5),
                        client_transaction_id="B",
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 5): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("26500")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("1500")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1500"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Settle C",
                events=[
                    create_settlement_event(
                        amount="2000",
                        final=True,
                        event_datetime=offset_datetime(2019, 1, 6),
                        client_transaction_id="C",
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 6): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("26500")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("3500")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("3500"),
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

    def test_cust_cant_spend_more_than_av_bal_and_overlimit_when_opted_in(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 3, 3, 3, 0, 0, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.025",
                    "flat_fee": "100",
                }
            }
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "15000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"
        instance_params["overlimit"] = "500"
        instance_params["overlimit_opt_in"] = "True"

        template_params["accrue_interest_from_txn_day"] = "False"

        sub_tests = [
            SubTest(
                description="Cash Advance 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="8000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 3, 1),
                    )
                ],
            ),
            SubTest(
                description="Purchase 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000", event_datetime=offset_datetime(2019, 1, 4, 1)
                    )
                ],
            ),
            SubTest(
                description="Repay 1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=offset_datetime(2019, 1, 5, 1),
                    )
                ],
            ),
            SubTest(
                description="Cash Advance 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 2, 1, 1),
                    )
                ],
            ),
            SubTest(
                description="Repay 2",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500", event_datetime=offset_datetime(2019, 2, 10, 1)
                    )
                ],
            ),
            SubTest(
                description="Repay 3",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=offset_datetime(2019, 2, 22, 1),
                    )
                ],
            ),
            SubTest(
                description="Purchase 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 3, 2, 1),
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1500",
                        event_datetime=offset_datetime(2019, 3, 2, 1),
                    ),
                ],
            ),
            SubTest(
                description="Balance Check 8",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 3, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("7843.77")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("22167.21"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("2000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("1902.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("8.68"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("212.23"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1500")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("2.30"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("18.48"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("100"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase over available + overlimit is rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="23000",
                        event_datetime=offset_datetime(2019, 3, 3, 2),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 3, 2): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("7843.77")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("22167.21"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("2000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("1902.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("8.68"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("212.23"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1500")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("2.30"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("18.48"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("100"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase under available is accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="22000", event_datetime=offset_datetime(2019, 3, 3, 3)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 3, 3): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("29843.77")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("167.21")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("2000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("1902.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("8.68"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("212.23"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("23500")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("2.30"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("18.48"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("100"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase under available + overlimit is accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=offset_datetime(2019, 3, 3, 3, 0, 0, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 3, 3, 0, 0, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("30343.77")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("-332.79"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("2000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("1902.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("8.68"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("212.23"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("24000")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("2.30"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("18.48"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("100"),
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

    def test_cust_cant_spend_more_than_av_bal_when_opted_out_of_overlimit(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 3, 3, 4)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {"cash_advance": {"percentage_fee": "0.025", "flat_fee": "100"}}
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "15000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"
        instance_params["overlimit"] = "500"
        instance_params["overlimit_opt_in"] = "False"

        template_params["accrue_interest_from_txn_day"] = "False"

        sub_tests = [
            SubTest(
                description="Cash Advance 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="8000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 3, 1),
                    ),
                ],
            ),
            SubTest(
                description="Purchase 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=offset_datetime(2019, 1, 4, 1),
                    )
                ],
            ),
            SubTest(
                description="Repay 1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=offset_datetime(2019, 1, 5, 1),
                    )
                ],
            ),
            SubTest(
                description="Cash Advance 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 2, 1, 1),
                    ),
                ],
            ),
            SubTest(
                description="Repay 2",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=offset_datetime(2019, 2, 10, 1),
                    )
                ],
            ),
            SubTest(
                description="Repay 3",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=offset_datetime(2019, 2, 22, 1),
                    )
                ],
            ),
            SubTest(
                description="Purchase 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 3, 2, 1),
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1500",
                        event_datetime=offset_datetime(2019, 3, 2, 1),
                    ),
                ],
            ),
            SubTest(
                description="Balance Check 8",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 3, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("7843.77")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("22167.21"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("2000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("1902.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("8.68"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("212.23"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1500")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("2.30"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("18.48"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("100"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase over available + overlimit is rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="23000",
                        event_datetime=offset_datetime(2019, 3, 3, 2),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 3, 2): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("7843.77")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("22167.21"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("2000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("1902.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("8.68"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("212.23"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1500")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("2.30"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("18.48"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("100"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase under available is accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="22000",
                        event_datetime=offset_datetime(2019, 3, 3, 3),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 3, 3): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("29843.77")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("167.21")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("2000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("1902.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("8.68"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("212.23"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("23500")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("2.30"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("18.48"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("100"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase under available + overlimit is rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500", event_datetime=offset_datetime(2019, 3, 3, 4)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 3, 4): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("29843.77")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("167.21")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("2000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("1902.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("8.68"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("212.23"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("23500")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("2.30"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("18.48"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("100"),
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

    def test_updating_credit_limit_will_amend_available_balance_accordingly(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 1, 1, 10)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"

        sub_tests = [
            SubTest(
                description="Available balance is initialised",
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("30000"),
                            )
                        ]
                    }
                },
            ),
            SubTest(
                description="Available balance is increased when credit limit is increased",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=offset_datetime(2019, 1, 1, 5),
                        credit_limit="35000",
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 5): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("35000"),
                            )
                        ]
                    }
                },
            ),
            SubTest(
                description="Available balance is decreased when credit limit is decreased",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=offset_datetime(2019, 1, 1, 10),
                        credit_limit="25000",
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 10): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("25000"),
                            )
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

    def test_overlimit_fee_not_charged_when_principal_(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 1, 1, 4)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["overlimit"] = "3000"
        instance_params["overlimit_opt_in"] = "True"
        instance_params["annual_fee"] = "0"

        sub_tests = [
            SubTest(
                description="Purchase under credit limit is accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="11000",
                        event_datetime=offset_datetime(2019, 1, 1, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("19000")),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("11000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase at credit limit is accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="19000",
                        event_datetime=offset_datetime(2019, 1, 1, 2),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 2): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("0")),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("30000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase within over limit is accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=offset_datetime(2019, 1, 1, 3),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 3): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-1000")),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("31000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase over over limit is rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=offset_datetime(2019, 1, 1, 4),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 4): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-1000")),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("31000"),
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

    def test_overlimit_txn_behaviour_when_customer_has_opted_in(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 1, 1, 4)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["overlimit"] = "3000"
        instance_params["overlimit_opt_in"] = "True"
        instance_params["annual_fee"] = "0"

        sub_tests = [
            SubTest(
                description="Purchase under credit limit is accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="11000",
                        event_datetime=offset_datetime(2019, 1, 1, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("19000")),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("11000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase at credit limit is accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="19000",
                        event_datetime=offset_datetime(2019, 1, 1, 2),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 2): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("0")),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("30000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase within over limit is accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=offset_datetime(2019, 1, 1, 3),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 3): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-1000")),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("31000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase over over limit is rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=offset_datetime(2019, 1, 1, 4),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 4): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-1000")),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("31000"),
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

    def test_overlimit_txn_behaviour_when_customer_has_opted_out(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 1, 1, 3, 0, 0, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["overlimit"] = "3000"
        instance_params["overlimit_opt_in"] = "False"
        instance_params["annual_fee"] = "0"

        sub_tests = [
            SubTest(
                description="Initial Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="1000",
                        client_transaction_id="1",
                        event_datetime=offset_datetime(2019, 1, 1, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("29000")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase under credit limit is accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=offset_datetime(2019, 1, 1, 1, 0, 0, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 1, 0, 0, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("19000")),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("10000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase over credit limit is rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="20000",
                        event_datetime=offset_datetime(2019, 1, 1, 2),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 2): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("19000")),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("10000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase at credit limit is accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="19000",
                        event_datetime=offset_datetime(2019, 1, 1, 3),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 3): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("0")),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("29000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Over settling initial auth is accepted",
                events=[
                    create_settlement_event(
                        amount="5000",
                        final=True,
                        event_datetime=offset_datetime(2019, 1, 1, 3, 0, 0, 1),
                        client_transaction_id="1",
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 3, 0, 0, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-4000")),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("34000"),
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

    def test_no_overlimit_fee_charged_if_settled_principal_lt_credit_limit(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 3, 1, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["overlimit"] = "3000"
        instance_params["overlimit_opt_in"] = "True"
        instance_params["annual_fee"] = "0"
        instance_params["transaction_type_fees"] = "{}"
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "5000"}})
        instance_params["late_repayment_fee"] = "0"

        template_params["transaction_types"] = default_template_update(
            "transaction_types",
            {"cash_advance": {"charge_interest_from_transaction_date": "False"}},
        )
        template_params["accrue_interest_from_txn_day"] = "False"

        sub_tests = [
            SubTest(
                description="Auth below limit",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="5000",
                        event_datetime=offset_datetime(2019, 1, 30, 1),
                    )
                ],
            ),
            SubTest(
                description="Purchase below limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=offset_datetime(2019, 1, 30, 2),
                    )
                ],
            ),
            SubTest(
                description="Cash Advance below limit (individually and cumulatively)",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 31, 3),
                    ),
                ],
            ),
            SubTest(
                description="Auth above limit",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="17000",
                        client_transaction_id="A",
                        event_datetime=offset_datetime(2019, 1, 31, 4),
                    )
                ],
            ),
            SubTest(
                description="No fee at SCOD",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-2000")),
                            (BalanceDimensions("OVERLIMIT_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("STATEMENT_BALANCE"), Decimal("10000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Under settle such that customer is not over limit",
                events=[
                    create_settlement_event(
                        amount="14000",
                        final=True,
                        event_datetime=offset_datetime(2019, 2, 2, 1),
                        client_transaction_id="A",
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 2, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="No fee at SCOD 2",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("521.44")),
                            (BalanceDimensions("OVERLIMIT_FEES_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("STATEMENT_BALANCE"),
                                Decimal("24478.56"),
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

    def test_overlimit_fee_charged_if_auth_settled_transaction_exceeds_credit_limit(
        self,
    ):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 1, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "10000"
        instance_params["overlimit"] = "3000"
        instance_params["overlimit_opt_in"] = "True"
        instance_params["overlimit_fee"] = "180"
        instance_params["annual_fee"] = "0"
        instance_params["transaction_type_fees"] = "{}"
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "5000"}})

        sub_tests = [
            SubTest(
                description="Auth below limit",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="9500",
                        client_transaction_id="A",
                        event_datetime=offset_datetime(2019, 1, 30, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 30, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("500")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase below limit",
                events=[
                    create_settlement_event(
                        amount="10100",
                        final=True,
                        event_datetime=offset_datetime(2019, 1, 31, 1),
                        client_transaction_id="A",
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 31, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Overlimit fee charged at SCOD",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions("OVERLIMIT_FEES_BILLED"),
                                Decimal("180"),
                            ),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-280")),
                            (BalanceDimensions("STATEMENT_BALANCE"), Decimal("10280")),
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

    def test_overlimit_fee_charged_if_hard_settled_transaction_exceeds_credit_limit(
        self,
    ):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 1, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "10000"
        instance_params["overlimit"] = "3000"
        instance_params["overlimit_opt_in"] = "True"
        instance_params["overlimit_fee"] = "180"
        instance_params["annual_fee"] = "0"
        instance_params["transaction_type_fees"] = "{}"
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "5000"}})

        sub_tests = [
            SubTest(
                description="Txn above limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="11000",
                        event_datetime=offset_datetime(2019, 1, 31, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 31, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Overlimit fee charged at SCOD",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions("OVERLIMIT_FEES_BILLED"),
                                Decimal("180"),
                            ),
                            (BalanceDimensions("STATEMENT_BALANCE"), Decimal("11180")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-1180")),
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

    def test_overlimit_fee_charged_if_auth_settled_transactions_exceed_credit_limit(
        self,
    ):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 1, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["overlimit"] = "3000"
        instance_params["overlimit_opt_in"] = "True"
        instance_params["overlimit_fee"] = "180"
        instance_params["annual_fee"] = "0"
        instance_params["late_repayment_fee"] = "0"
        instance_params["transaction_type_fees"] = "{}"
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "5000"}})

        sub_tests = [
            SubTest(
                description="Auth below limit",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="29800",
                        client_transaction_id="A",
                        event_datetime=offset_datetime(2019, 1, 30, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 30, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("200")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Settle",
                events=[
                    create_settlement_event(
                        amount="29800",
                        final=True,
                        event_datetime=offset_datetime(2019, 1, 30, 2),
                        client_transaction_id="A",
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 30, 2): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("200")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Auth above limit (cumulatively)",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="500",
                        client_transaction_id="B",
                        event_datetime=offset_datetime(2019, 1, 31, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 31, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-300")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Settle",
                events=[
                    create_settlement_event(
                        amount="500",
                        final=True,
                        event_datetime=offset_datetime(2019, 1, 31, 2),
                        client_transaction_id="B",
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 31, 2): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-300")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Overlimit fee charged at SCOD",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions("OVERLIMIT_FEES_BILLED"),
                                Decimal("180"),
                            ),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-480")),
                            (BalanceDimensions("STATEMENT_BALANCE"), Decimal("30480")),
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

    def test_overlimit_fee_not_charged_if_credit_limit_exceeded_due_to_charges(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 3, 1, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "10000"
        instance_params["overlimit"] = "3000"
        instance_params["overlimit_opt_in"] = "True"
        instance_params["overlimit_fee"] = "180"
        instance_params["annual_fee"] = "0"
        instance_params["late_repayment_fee"] = "0"
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "10000"}})
        instance_params["transaction_type_fees"] = dumps(
            {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
        )

        sub_tests = [
            SubTest(
                description="Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 30, 1),
                    ),
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 30, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("200"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Overlimit fee not charged at SCOD "
                "as fees/interest push outstanding past",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("19.72"),
                            ),
                            (BalanceDimensions("OVERLIMIT_FEES_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("-219.72"),
                            ),
                            (
                                BalanceDimensions("STATEMENT_BALANCE"),
                                Decimal("10219.72"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Overlimit fee not charged at SCOD 2 as fees/interest push outstanding "
                "past credit limit",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("19.72"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("276.08"),
                            ),
                            (BalanceDimensions("OVERLIMIT_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("OVERLIMIT_FEES_UNPAID"), Decimal("0")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("-495.80"),
                            ),
                            (
                                BalanceDimensions("STATEMENT_BALANCE"),
                                Decimal("10495.80"),
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

    def test_overlimit_fee_not_charged_until_auth_settled(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 3, 1, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "10000"
        instance_params["overlimit"] = "3000"
        instance_params["overlimit_opt_in"] = "True"
        instance_params["overlimit_fee"] = "180"
        instance_params["annual_fee"] = "0"
        instance_params["late_repayment_fee"] = "0"

        sub_tests = [
            SubTest(
                description="Auth under limit",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="9000",
                        client_transaction_id="A",
                        event_datetime=offset_datetime(2019, 1, 31, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 31, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Overlimit fee not charged at SCOD 1",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("OVERLIMIT_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("1000")),
                            (BalanceDimensions("STATEMENT_BALANCE"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Oversettle",
                events=[
                    create_settlement_event(
                        amount="11000",
                        final=True,
                        event_datetime=offset_datetime(2019, 2, 3, 1),
                        client_transaction_id="A",
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 3, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Overlimit fee charged at SCOD 2",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions("OVERLIMIT_FEES_BILLED"),
                                Decimal("180"),
                            ),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-1180")),
                            (BalanceDimensions("STATEMENT_BALANCE"), Decimal("11180")),
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

    def test_overlimit_fee_not_charged_if_temporarily_overlimit(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 3, 1, 2)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "10000"
        instance_params["overlimit"] = "3000"
        instance_params["overlimit_opt_in"] = "True"
        instance_params["overlimit_fee"] = "180"
        instance_params["annual_fee"] = "0"
        instance_params["late_repayment_fee"] = "0"

        template_params["accrue_interest_from_txn_day"] = "False"

        sub_tests = [
            SubTest(
                description="Purchase over limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="11000",
                        event_datetime=offset_datetime(2019, 1, 30, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 30, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay before SCOD",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1001",
                        event_datetime=offset_datetime(2019, 1, 30, 2),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 30, 2): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("1")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Overlimit fee not charged at SCOD 1",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("OVERLIMIT_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("1")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase over limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000", event_datetime=offset_datetime(2019, 2, 2, 1)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 2, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-999")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Overlimit fee charged at SCOD 2",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 1, 2): {
                        "Main account": [
                            (
                                BalanceDimensions("OVERLIMIT_FEES_BILLED"),
                                Decimal("180"),
                            ),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("-1380.78"),
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

    def test_no_txn_type_fees_charged_when_deposit_balance_gt_transfer_amount(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 1, 0, 1, 0)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "22"
        instance_params["transaction_type_fees"] = dumps(
            {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.01",
                    "flat_fee": "100",
                },
                "transfer": {
                    "over_deposit_only": "True",
                    "percentage_fee": "0.01",
                    "flat_fee": "100",
                },
            }
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "6000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"

        template_params["minimum_percentage_due"] = dumps(
            {
                "purchase": "0.01",
                "cash_advance": "0.01",
                "balance_transfer": "0",
                "transfer": "0",
                "interest": "1.0",
                "fees": "1.0",
            }
        )
        template_params["minimum_amount_due"] = "200"

        sub_tests = [
            SubTest(
                description="Overpay",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=offset_datetime(2019, 1, 3, 0, 1),
                    )
                ],
            ),
            SubTest(
                description="Transfer out",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="4000",
                        instruction_details={"transaction_code": "cc"},
                        event_datetime=offset_datetime(2019, 1, 5, 0, 1),
                    )
                ],
            ),
            SubTest(
                description="Check statement accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 0, 1, 0): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("31000")),
                            (BalanceDimensions("DEPOSIT"), Decimal("1000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
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

    def test_no_txn_type_fees_charged_when_deposit_balance_eq_transfer_amount(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 1, 0, 1, 0)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "22"
        instance_params["transaction_type_fees"] = dumps(
            {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.01",
                    "flat_fee": "100",
                },
                "transfer": {
                    "over_deposit_only": "True",
                    "percentage_fee": "0.01",
                    "flat_fee": "100",
                },
            }
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "6000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"

        template_params["minimum_percentage_due"] = dumps(
            {
                "purchase": "0.01",
                "cash_advance": "0.01",
                "balance_transfer": "0",
                "transfer": "0",
                "interest": "1.0",
                "fees": "1.0",
            }
        )
        template_params["minimum_amount_due"] = "200"

        sub_tests = [
            SubTest(
                description="Overpay",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=offset_datetime(2019, 1, 3, 0, 1),
                    )
                ],
            ),
            SubTest(
                description="Transfer out",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        instruction_details={"transaction_code": "cc"},
                        event_datetime=offset_datetime(2019, 1, 5, 0, 1),
                    )
                ],
            ),
            SubTest(
                description="Check statement accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 0, 1, 0): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("30000")),
                            (BalanceDimensions("DEPOSIT"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
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

    def test_txn_type_fees_charged_when_deposit_balance_lt_transfer_amount(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 1, 0, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "22"
        instance_params["transaction_type_fees"] = dumps(
            {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.01",
                    "flat_fee": "100",
                },
                "transfer": {
                    "over_deposit_only": "True",
                    "percentage_fee": "0.01",
                    "flat_fee": "100",
                },
            }
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "6000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"

        template_params["minimum_percentage_due"] = dumps(
            {
                "purchase": "0.01",
                "cash_advance": "0.01",
                "transfer": "0.01",
                "balance_transfer": "0.01",
                "interest": "1.0",
                "fees": "1.0",
            }
        )
        template_params["minimum_amount_due"] = "200"

        sub_tests = [
            SubTest(
                description="Overpay",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=offset_datetime(2019, 1, 3, 0, 1),
                    )
                ],
            ),
            SubTest(
                description="Transfer out",
                events=[
                    create_transfer_instruction(
                        amount="5010",
                        instruction_details={"transaction_code": "cc"},
                        creditor_target_account_id="1",
                        debtor_target_account_id="Main account",
                        event_datetime=offset_datetime(2019, 1, 5, 0, 1),
                    )
                ],
            ),
            SubTest(
                description="Check statement accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 0, 1): {
                        "Main account": [
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("110"),
                            ),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("29890")),
                            (BalanceDimensions("DEPOSIT"), Decimal("0")),
                            (BalanceDimensions("TRANSFER_FEES_BILLED"), Decimal("100")),
                            (BalanceDimensions("TRANSFER_BILLED"), Decimal("10")),
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

    def test_txn_type_fees_charged_when_cash_advance_amount_lt_deposit_balance(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 1, 0, 1, 0)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "22"
        instance_params["transaction_type_fees"] = dumps(
            {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.01",
                    "flat_fee": "100",
                },
                "transfer": {
                    "over_deposit_only": "True",
                    "percentage_fee": "0.01",
                    "flat_fee": "100",
                },
            }
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "6000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"

        template_params["minimum_percentage_due"] = dumps(
            {
                "purchase": "0.01",
                "cash_advance": "0.01",
                "balance_transfer": "0.01",
                "transfer": "0.01",
                "interest": "1.0",
                "fees": "1.0",
            }
        )
        template_params["minimum_amount_due"] = "200"

        sub_tests = [
            SubTest(
                description="Overpay",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=offset_datetime(2019, 1, 3, 0, 1),
                    )
                ],
            ),
            SubTest(
                description="Transfer out",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="4000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 5, 0, 1),
                    ),
                ],
            ),
            SubTest(
                description="Check statement accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 0, 1, 0): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("30900")),
                            (BalanceDimensions("DEPOSIT"), Decimal("900")),
                            # The fees should be 0 as they came out of deposit
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
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

    def test_txn_type_fees_charged_for_multiple_transfers_if_sum_exceeds_deposit(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 1, 3, 0, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "22"
        instance_params["transaction_type_fees"] = dumps(
            {
                "transfer": {
                    "over_deposit_only": "True",
                    "percentage_fee": "0.01",
                    "flat_fee": "100",
                }
            }
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "6000"}})

        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"

        sub_tests = [
            SubTest(
                description="Overpay",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=offset_datetime(2019, 1, 2, 0, 1),
                    )
                ],
            ),
            SubTest(
                description="Transfer out",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="4000",
                        event_datetime=offset_datetime(2019, 1, 3, 0, 1),
                        instruction_details={"transaction_code": "cc"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=offset_datetime(2019, 1, 3, 0, 1),
                        instruction_details={"transaction_code": "cc"},
                    ),
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 3, 0, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("27900")),
                            (BalanceDimensions("DEPOSIT"), Decimal("0")),
                            (BalanceDimensions("TRANSFER_CHARGED"), Decimal("2000")),
                            (
                                BalanceDimensions("TRANSFER_FEES_CHARGED"),
                                Decimal("100"),
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

    def test_daily_interest_correct_when_traversing_normal_to_leap_year(self):

        start = offset_datetime(2019, 12, 1)
        end = offset_datetime(2020, 1, 6, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.025",
                    "flat_fee": "100",
                }
            }
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "15000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"

        sub_tests = [
            SubTest(
                description="Cash Advance 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="8000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 12, 3, 1),
                    ),
                ],
            ),
            SubTest(
                description="Balance Check in normal year",
                expected_balances_at_ts={
                    offset_datetime(2019, 12, 6, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("21800")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("8000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("23.67"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("200"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Balance Check in leap year",
                expected_balances_at_ts={
                    offset_datetime(2020, 1, 6, 1): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("21571.19"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("8000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            # If 2020 were not a leap year the interest would be -39.45
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("39.35"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
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

    def test_stand_in_transaction_follows_instruction_advice_flag(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 1, 1, 5)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "100"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {"cash_advance": {"percentage_fee": "0.025", "flat_fee": "100"}}
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "200"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"
        instance_params["overlimit_opt_in"] = "False"

        sub_tests = [
            SubTest(
                description="Cash Advance with no advice flag is rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="200",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 1, 1),
                    ),
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("100")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Instruction that doesn't support advice flag is rejected",
                events=[
                    create_transfer_instruction(
                        amount="300",
                        instruction_details={"transaction_code": "cc"},
                        creditor_target_account_id="1",
                        debtor_target_account_id="Main account",
                        event_datetime=offset_datetime(2019, 1, 1, 2),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 2): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("100")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Batch with offline and online posting instruction accepted if online"
                " amount does not exceed available balance",
                events=[
                    create_transfer_instruction(
                        amount="5",
                        instruction_details={"transaction_code": "cc"},
                        creditor_target_account_id="1",
                        debtor_target_account_id="Main account",
                        event_datetime=offset_datetime(2019, 1, 1, 3),
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1",
                        event_datetime=offset_datetime(2019, 1, 1, 3),
                        instruction_details={"transaction_code": "xxxx"},
                    ),
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 3): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("94")),
                            (BalanceDimensions("TRANSFER_CHARGED"), Decimal("5")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Batch with offline and online posting instruction rejected if online"
                " amount exceeds available balance",
                events=[
                    create_posting_instruction_batch(
                        instructions=[
                            Transfer(
                                amount="100",
                                creditor_target_account_id="1",
                                debtor_target_account_id="Main account",
                            ),
                            OutboundHardSettlement(
                                target_account_id="Main account",
                                internal_account_id="1",
                                amount="1",
                                advice=True,
                            ),
                        ],
                        instruction_details={"transaction_code": "cc"},
                        event_datetime=offset_datetime(2019, 1, 1, 4),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 4): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("94")),
                            (BalanceDimensions("TRANSFER_CHARGED"), Decimal("5")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance with advice flag is accepted and bypasses txn type limit",
                events=[
                    create_posting_instruction_batch(
                        instructions=[
                            OutboundHardSettlement(
                                target_account_id="Main account",
                                internal_account_id="1",
                                amount="300",
                                advice=True,
                            ),
                        ],
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 1, 5),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 5): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("-306.00"),
                            ),
                            (BalanceDimensions("TRANSFER_CHARGED"), Decimal("5")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("300.0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100.00"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
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

    def test_prevent_transaction_when_limit_plus_overlimit_exceeded(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 1, 1, 3)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "10000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
        )
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"
        instance_params["overlimit"] = "1000"
        instance_params["overlimit_opt_in"] = "True"
        instance_params["overlimit_fee"] = "180"

        sub_tests = [
            SubTest(
                description="Purchase Auth A",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="11000",
                        client_transaction_id="12345",
                        event_datetime=offset_datetime(2019, 1, 1, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("0")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-1000")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("11000")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Settlement A",
                events=[
                    create_settlement_event(
                        amount="11000",
                        final=True,
                        event_datetime=offset_datetime(2019, 1, 1, 2),
                        client_transaction_id="12345",
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 2): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("11000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-1000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("11000")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Auth B is rejected",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="500", event_datetime=offset_datetime(2019, 1, 1, 3)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 3): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("11000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-1000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("11000")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
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

    @skip("Skip for sim test case as there is no skip balance check flag")
    def test_stand_in_transaction_opt_out_overlimit(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 1, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "10000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {"cash_advance": {"percentage_fee": "0.025", "flat_fee": "100"}}
        )

        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "100"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"
        instance_params["overlimit"] = "3000"
        instance_params["overlimit_opt_in"] = "False"
        instance_params["overlimit_fee"] = "180"

        sub_tests = [
            SubTest(
                description="Purchase with skip balance check true",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="11000",
                        instruction_details={"transaction_code": "cc"},
                        event_datetime=offset_datetime(2019, 1, 30, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 30, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("11000.00")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("-1000.0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("11000.0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check Statement accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("11000.0")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("-1000.0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("11000.0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
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

    @skip("Skip for sim test case as there is no skip balance check flag")
    def test_stand_in_transaction_opt_in_overlimit_over_credit_limit_with_fee(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 1, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "10000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {"cash_advance": {"percentage_fee": "0.025", "flat_fee": "100"}}
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "100"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"
        instance_params["overlimit"] = "3000"
        instance_params["overlimit_opt_in"] = "True"
        instance_params["overlimit_fee"] = "180"

        sub_tests = [
            SubTest(
                description="Purchase with skip balance check true",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=offset_datetime(2019, 1, 20, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 20, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10000.00")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10000.0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase with skip balance check true",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="4000",
                        event_datetime=offset_datetime(2019, 1, 30, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 30, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("14000.0")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("-4000.0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("14000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check Statement accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("14180.0")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("-4180.0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("14000")),
                            (
                                BalanceDimensions("OVERLIMIT_FEES_BILLED"),
                                Decimal("180"),
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

    @skip("Skip for sim test case as there is no skip balance check flag")
    def test_overlimit_opt_out_over_credit_limit_no_fees_charged(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 4, 1, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "10000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {"cash_advance": {"percentage_fee": "0.025", "flat_fee": "100"}}
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "100"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"
        instance_params["overlimit_opt_in"] = "False"

        template_params["accrue_interest_from_txn_day"] = "False"

        sub_tests = [
            SubTest(
                description="Purchase with skip balance check true",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="9800",
                        event_datetime=offset_datetime(2019, 1, 20, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 20, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("9800.00")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("200")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("9800.0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase with skip balance check true",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="300",
                        event_datetime=offset_datetime(2019, 3, 10, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 10, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10338.28")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("-280.32"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("300")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("9800")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("57.96"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("180.32"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check Statement accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 4, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10484.36")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("-484.36"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("300")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("9800")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("204.04"),
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

    def test_overlimit_opt_in_over_credit_limit_fee_charged(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 4, 1, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "10000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {"cash_advance": {"percentage_fee": "0.025", "flat_fee": "100"}}
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "100"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"
        instance_params["overlimit"] = "3000"
        instance_params["overlimit_opt_in"] = "True"
        instance_params["overlimit_fee"] = "180"

        template_params["accrue_interest_from_txn_day"] = "False"

        sub_tests = [
            SubTest(
                description="Purchase with skip balance check true",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="9800",
                        event_datetime=offset_datetime(2019, 1, 20, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 20, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("9800.00")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("200")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("9800.0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase with skip balance check true",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="300",
                        event_datetime=offset_datetime(2019, 3, 10, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 10, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10338.28")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("-280.32"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("300")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("9800")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("57.96"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("180.32"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check Statement accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 4, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10664.36")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("-664.36"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("300")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("9800")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("204.04"),
                            ),
                            (
                                BalanceDimensions("OVERLIMIT_FEES_BILLED"),
                                Decimal("180"),
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

    def test_overlimit(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 1, 1, 5)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "10000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "100"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"
        instance_params["overlimit"] = "1000"
        instance_params["overlimit_opt_in"] = "True"
        instance_params["overlimit_fee"] = "180"

        sub_tests = [
            SubTest(
                description="Purchase A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=offset_datetime(2019, 1, 1, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("5000.00")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("5000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("5000.0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase B",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=offset_datetime(2019, 1, 1, 2),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 2): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("8000.00")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("2000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("8000.0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase C",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2500",
                        event_datetime=offset_datetime(2019, 1, 1, 3),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 3): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10500.00")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-500")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10500.0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase D",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=offset_datetime(2019, 1, 1, 4),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 4): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10500.00")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-500")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10500.0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance rejected as overlimit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 1, 5),
                    ),
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 5): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10500.00")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-500")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10500.0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
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

    def test_prevent_transaction_when_fee_or_interest_trigger_overlimit_ca_overlimit_purchase(
        self,
    ):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 1, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "10000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "15000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"
        instance_params["overlimit"] = "1000"
        instance_params["overlimit_opt_in"] = "True"
        instance_params["overlimit_fee"] = "180"

        sub_tests = [
            SubTest(
                description="Cash Advance A goes Overlimit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10800",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 30, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 30, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("11016")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("-1016.00"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("10800"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("216"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Rejected as already Overlimit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=offset_datetime(2019, 2, 1, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("11217.30")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("-1217.30"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_BILLED"),
                                Decimal("10800"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("21.30"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("216.00"),
                            ),
                            (
                                BalanceDimensions("OVERLIMIT_FEES_BILLED"),
                                Decimal("180.00"),
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

    def test_prevent_transaction_when_fee_or_interest_triggers_overlimit_second_purchase(
        self,
    ):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 1, 2, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "10000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "15000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"
        instance_params["overlimit"] = "1000"
        instance_params["overlimit_opt_in"] = "True"
        instance_params["overlimit_fee"] = "180"

        sub_tests = [
            SubTest(
                description="Purchase A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="9900", event_datetime=offset_datetime(2019, 1, 1, 1)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("9900")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("100")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("9900")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase B",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=offset_datetime(2019, 1, 2, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 2, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("9950")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("50")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("9950")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
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

    def test_reject_transaction_when_overlimit_in_use(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 3, 10, 3)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "10000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "15000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"
        instance_params["overlimit"] = "1000"
        instance_params["overlimit_opt_in"] = "True"
        instance_params["overlimit_fee"] = "180"

        template_params["accrue_interest_from_txn_day"] = "False"

        sub_tests = [
            SubTest(
                description="Purchase A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="9900", event_datetime=offset_datetime(2019, 1, 1, 1)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("9900")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("100")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("9900")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Auth B Accepted as account not in Overlimit",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="200",
                        client_transaction_id="B",
                        event_datetime=offset_datetime(2019, 3, 10, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 10, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10140.87")),
                            (
                                BalanceDimensions(
                                    "DEFAULT", phase="POSTING_PHASE_PENDING_OUTGOING"
                                ),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("-282.28"),
                            ),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("200")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("9900.0")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("58.59"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("182.28"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Settle Auth B to push account into overlimit",
                events=[
                    create_settlement_event(
                        amount="200",
                        final=True,
                        event_datetime=offset_datetime(2019, 3, 10, 2),
                        client_transaction_id="B",
                    )
                ],
            ),
            SubTest(
                description="Purchase Auth C rejected as account already overlimit",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="200",
                        event_datetime=offset_datetime(2019, 3, 10, 3),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 10, 3): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10340.87")),
                            (
                                BalanceDimensions(
                                    "DEFAULT", phase="POSTING_PHASE_PENDING_OUTGOING"
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("-282.28"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("200")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("9900.0")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("58.59"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("182.28"),
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

    def test_accept_transaction_when_overlimit_not_in_use_purchase_and_auth(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 1, 1, 2)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "10000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "15000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"
        instance_params["overlimit"] = "1000"
        instance_params["overlimit_opt_in"] = "True"
        instance_params["overlimit_fee"] = "180"

        sub_tests = [
            SubTest(
                description="Purchase A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="9900",
                        event_datetime=offset_datetime(2019, 1, 1, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("9900")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("100")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("9900")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase auth A",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="200",
                        event_datetime=offset_datetime(2019, 1, 1, 2),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 2): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("9900")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-100")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("9900")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("200")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
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

    def test_accept_transaction_when_overlimit_not_in_use_purchase_and_early_repay(
        self,
    ):
        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 1, 5, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "10000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "15000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"
        instance_params["overlimit"] = "1000"
        instance_params["overlimit_opt_in"] = "True"
        instance_params["overlimit_fee"] = "180"

        sub_tests = [
            SubTest(
                description="Purchase A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000", event_datetime=offset_datetime(2019, 1, 1, 1)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("5000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("5000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("5000")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase B",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5500",
                        event_datetime=offset_datetime(2019, 1, 2, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 2, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10500")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-500")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10500")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Pre-repay Balances",
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 3, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10500")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-500")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10500")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=offset_datetime(2019, 1, 3, 2),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 3, 2): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("9500")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("500")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("9500")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                Decimal("1000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase C",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=offset_datetime(2019, 1, 4, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 4, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10500")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-500")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10500")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase D",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1",
                        event_datetime=offset_datetime(2019, 1, 5, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 5, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10500")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-500")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10500")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
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

    def test_accept_transaction_when_overlimit_not_in_use_then_fails_when_in_use(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 1, 5, 2)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "10000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "15000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"
        instance_params["overlimit"] = "1000"
        instance_params["overlimit_opt_in"] = "True"
        instance_params["overlimit_fee"] = "180"

        sub_tests = [
            SubTest(
                description="Purchase A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000", event_datetime=offset_datetime(2019, 1, 1, 1)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("5000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("5000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("5000")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase B",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5500",
                        event_datetime=offset_datetime(2019, 1, 2, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 2, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10500")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-500")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10500")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="600", event_datetime=offset_datetime(2019, 1, 3, 1)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 3, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("9900")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("100")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("9900")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase C",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=offset_datetime(2019, 1, 4, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 4, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10000")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase D",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=offset_datetime(2019, 1, 5, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 5, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10100")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-100")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10100")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase E",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1", event_datetime=offset_datetime(2019, 1, 5, 2)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 5, 2): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10100")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-100")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10100")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
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

    def test_cash_withdrawal_within_positive_balance(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 1, 5, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "8000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"
        instance_params["overlimit_opt_in"] = "False"

        sub_tests = [
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=offset_datetime(2019, 1, 2, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 2, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10000.00")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("20000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10000.0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="15000",
                        event_datetime=offset_datetime(2019, 1, 3, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 3, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("-5000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("35000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Withdrawal",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="4000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 4, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 4, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("-900")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("30900")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check no interest accrued",
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 5, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("-900")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("30900")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
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

    def test_internal_account_postings_generated_correctly(self):

        credit_limit = "10000"

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 2, 5)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = credit_limit
        instance_params["annual_fee"] = "100"

        sub_tests = [
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        "200",
                        client_transaction_id="1234",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 1, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "DEFAULT", phase="POSTING_PHASE_PENDING_OUTGOING"
                                ),
                                Decimal("200"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_AUTH"), Decimal("200")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Settle - Spend and Txn Type Fee GL postings",
                events=[
                    create_settlement_event(
                        amount="200",
                        final=True,
                        event_datetime=offset_datetime(2019, 1, 1, 2),
                        client_transaction_id="1234",
                        instruction_details={"transaction_code": "aaa"},
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 2): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("210")),
                            (BalanceDimensions("CASH_ADVANCE_AUTH"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("10"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial repay - GL postings",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "100",
                        client_transaction_id="2",
                        event_datetime=offset_datetime(2019, 1, 1, 4),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 4): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("110")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("100")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("10"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Annual Fee Charged - GL Postings",
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 23, 50): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("210")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("100")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("10"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_CHARGED"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Interest Charged - Interest GL postings",
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 2, 0, 0): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("210.1")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("100")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("10"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0.1"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_CHARGED"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Interest billed at SCOD",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 0, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("213.1")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("100")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("10"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("3.1"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay interest, fees and partial principal after SCOD",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="120",
                        event_datetime=offset_datetime(2019, 2, 1, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("93.1")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("93.1")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay principal and charged interest",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=offset_datetime(2019, 2, 2, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 2, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("-6.81")),
                            (BalanceDimensions("DEPOSIT"), Decimal("6.81")),
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
                        event_datetime=offset_datetime(2019, 2, 2, 2),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 2, 2): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("93.19")),
                            (
                                BalanceDimensions("DISPUTE_FEES_CHARGED"),
                                Decimal("93.19"),
                            ),
                            (BalanceDimensions("DEPOSIT"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Dispute fee repaid",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="95",
                        event_datetime=offset_datetime(2019, 2, 2, 3),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 2, 3): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("-1.81")),
                            (BalanceDimensions("DISPUTE_FEES_CHARGED"), Decimal("0")),
                            (BalanceDimensions("DEPOSIT"), Decimal("1.81")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Over repay",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=offset_datetime(2019, 2, 2, 4),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 2, 4): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("-101.81")),
                            (BalanceDimensions("DEPOSIT"), Decimal("101.81")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance - Spend and Txn Type Fee from Deposit GL postings",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="99",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 2, 2, 5),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 2, 5): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("2.19")),
                            (BalanceDimensions("DEPOSIT"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("2.19"),
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

        res = self.run_test_scenario(test_scenario)

        expected_posting_batches = [
            settled_spend_gl_postings_batch(
                credit_line_amount="200",
                value_timestamp=offset_datetime(2019, 1, 1, 2),
                txn_type="CASH_ADVANCE",
            ),
            charge_txn_type_fee_gl_postings_batch(
                credit_line_amount="10.00",
                txn_type="cash_advance",
                value_timestamp=offset_datetime(2019, 1, 1, 2),
                hook_effective_datetime=offset_datetime(2019, 1, 1, 2),
            ),
            repay_spend_gl_postings_batch(
                credit_line_amount="100",
                value_timestamp=offset_datetime(2019, 1, 1, 4),
                txn_type="CASH_ADVANCE",
            ),
            repay_billed_interest_gl_postings_batch(
                credit_line_amount="3.10",
                txn_type="CASH_ADVANCE",
                repay_count=0,
                value_timestamp=offset_datetime(2019, 2, 1, 1),
            ),
            repay_charged_fee_gl_postings_batch(
                credit_line_amount="100.00",
                fee_type="ANNUAL_FEE",
                repay_count=1,
                value_timestamp=offset_datetime(2019, 2, 1, 1),
            ),
            repay_charged_fee_gl_postings_batch(
                credit_line_amount="10.00",
                fee_type="CASH_ADVANCE_FEE",
                repay_count=2,
                value_timestamp=offset_datetime(2019, 2, 1, 1),
            ),
            repay_spend_gl_postings_batch(
                credit_line_amount="6.90",
                value_timestamp=offset_datetime(2019, 2, 1, 1),
                repay_count=3,
                txn_type="CASH_ADVANCE",
            ),
            repay_spend_gl_postings_batch(
                credit_line_amount="93.10",
                value_timestamp=offset_datetime(2019, 2, 2, 1),
                txn_type="CASH_ADVANCE",
            ),
            repay_charged_interest_gl_postings_batch(
                amount="0.09",
                txn_type="CASH_ADVANCE",
                value_timestamp=offset_datetime(2019, 2, 2, 1),
            ),
            repay_deposit_gl_postings_batch(
                amount="6.81",
                value_timestamp=offset_datetime(2019, 2, 2, 1),
            ),
            spend_deposit_gl_postings_batch(
                amount="6.81",
                value_timestamp=offset_datetime(2019, 2, 2, 2),
                event="LOAN_FEES",
                trigger="FEES_CHARGED_DISPUTE_FEE",
            ),
            charge_dispute_fee_gl_postings_batch(
                amount="93.19",
                value_timestamp=offset_datetime(2019, 2, 2, 2),
            ),
            repay_dispute_fee_gl_postings_batch(
                amount="93.19",
                value_timestamp=offset_datetime(2019, 2, 2, 3),
            ),
            repay_deposit_gl_postings_batch(
                amount="1.81",
                value_timestamp=offset_datetime(2019, 2, 2, 3),
            ),
            repay_deposit_gl_postings_batch(
                amount="100", value_timestamp=offset_datetime(2019, 2, 2, 4)
            ),
            spend_deposit_gl_postings_batch(
                amount="2.81",
                value_timestamp=offset_datetime(2019, 2, 2, 5),
                event="LOAN_FEES",
                trigger="FEES_CHARGED_CASH_ADVANCE_FEE",
            ),
            spend_deposit_gl_postings_batch(
                amount="99",
                value_timestamp=offset_datetime(2019, 2, 2, 5),
                event="LOAN_DISBURSEMENT",
                trigger="PRINCIPAL_SPENT_CASH_ADVANCE",
            ),
            charge_txn_type_fee_gl_postings_batch(
                credit_line_amount="2.19",
                txn_type="cash_advance",
                value_timestamp=offset_datetime(2019, 2, 2, 5),
                hook_effective_datetime=offset_datetime(2019, 2, 2, 5),
            ),
            charge_annual_fee_gl_postings_batch(
                amount="100.00",
                value_timestamp=offset_datetime(2019, 1, 1, 23, 50),
                hook_effective_datetime=offset_datetime(2019, 1, 1, 23, 50),
            ),
            charge_interest_gl_postings_batch(
                amount="0.10",
                interest_value_date=datetime(2019, 1, 1).date(),
                value_timestamp=offset_datetime(2019, 1, 1, 23, 59, 59, 999999),
                hook_effective_datetime=offset_datetime(2019, 1, 2),
            ),
            bill_interest_gl_postings_batch(
                credit_line_amount="3.10",
                value_timestamp=offset_datetime(2019, 2, 1),
                hook_effective_datetime=offset_datetime(2019, 2, 1, 0, 0, 2),
                txn_type="CASH_ADVANCE",
            ),
        ]

        for postings in expected_posting_batches:
            self.assertTrue(check_postings_correct_after_simulation(res, postings))

    def test_internal_account_postings_generated_correctly_unpaid_interest(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 3, 1, 0, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        credit_limit = "10000"

        instance_params["credit_limit"] = credit_limit
        instance_params["annual_fee"] = "100"
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "8000"}})

        template_params["accrue_interest_on_unpaid_interest"] = "True"
        template_params["base_interest_rates"] = default_template_update(
            "base_interest_rates", {"cash_advance": "0.5"}
        )

        sub_tests = [
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        "4000",
                        client_transaction_id="1234",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 1, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "DEFAULT", phase="POSTING_PHASE_PENDING_OUTGOING"
                                ),
                                Decimal("4000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_AUTH"), Decimal("4000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Settle - Spend and Txn Type Fee GL postings",
                events=[
                    create_settlement_event(
                        amount="4000",
                        final=True,
                        event_datetime=offset_datetime(2019, 1, 1, 2),
                        client_transaction_id="1234",
                        instruction_details={"transaction_code": "aaa"},
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 2): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("4200")),
                            (BalanceDimensions("CASH_ADVANCE_AUTH"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("4000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("200"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial repay - GL postings",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "100",
                        client_transaction_id="2",
                        event_datetime=offset_datetime(2019, 1, 1, 4),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 4): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("4100")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("3900"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("200"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Annual Fee Charged - GL Postings",
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 23, 50): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("4200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("3900"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("200"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_CHARGED"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Interest Charged - Interest GL postings",
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 2, 0, 0): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("4205.34")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("3900"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("5.34"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_CHARGED"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Interest billed at SCOD",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 0, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("4365.54")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("3900")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("165.54"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check interest unpaid",
                events=[],
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 25, 1): {
                        "Main account": [
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("165.54"),
                            )
                        ]
                    }
                },
            ),
            # Interest posting includes amount for interest on interest.
            # Previous Daily - 5.34
            # UNPAID 165.54 * 0.5 / 365 = 0.2268 | 5.34 + 0.23 = 5.57
            SubTest(
                description="Interest Charged - Interest GL postings",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 28, 0, 0): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("4610.41")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("165.54"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("144.87"),
                            ),
                        ]
                    }
                },
            ),
            # Daily 5.34 * 28 = 149.52
            # Daily unpaid 0.23 * 4 = 0.69
            SubTest(
                description="Interest billed at SCOD",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 1, 0, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("4615.98")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("150.44"),
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

        res = self.run_test_scenario(test_scenario)

        expected_posting_batches = [
            settled_spend_gl_postings_batch(
                credit_line_amount="4000",
                value_timestamp=offset_datetime(2019, 1, 1, 2),
                txn_type="CASH_ADVANCE",
            ),
            charge_txn_type_fee_gl_postings_batch(
                credit_line_amount="200.00",
                txn_type="cash_advance",
                value_timestamp=offset_datetime(2019, 1, 1, 2),
                hook_effective_datetime=offset_datetime(2019, 1, 1, 2),
            ),
            repay_spend_gl_postings_batch(
                credit_line_amount="100",
                value_timestamp=offset_datetime(2019, 1, 1, 4),
                txn_type="CASH_ADVANCE",
            ),
            charge_annual_fee_gl_postings_batch(
                amount="100.00",
                value_timestamp=offset_datetime(2019, 1, 1, 23, 50),
                hook_effective_datetime=offset_datetime(2019, 1, 1, 23, 50),
            ),
            charge_interest_gl_postings_batch(
                amount="5.34",
                interest_value_date=datetime(2019, 1, 1).date(),
                value_timestamp=offset_datetime(2019, 1, 1, 23, 59, 59, 999999),
                hook_effective_datetime=offset_datetime(2019, 1, 2),
            ),
            bill_interest_gl_postings_batch(
                credit_line_amount="165.54",
                value_timestamp=offset_datetime(2019, 2, 1),
                hook_effective_datetime=offset_datetime(2019, 2, 1, 0, 0, 2),
                txn_type="CASH_ADVANCE",
            ),
            charge_interest_gl_postings_batch(
                amount="5.57",
                interest_value_date=datetime(2019, 2, 27).date(),
                value_timestamp=offset_datetime(2019, 2, 27, 23, 59, 59, 999999),
                hook_effective_datetime=offset_datetime(2019, 2, 28),
            ),
            bill_interest_gl_postings_batch(
                credit_line_amount="150.44",
                value_timestamp=offset_datetime(2019, 3, 1),
                hook_effective_datetime=offset_datetime(2019, 3, 1, 0, 0, 2),
                txn_type="CASH_ADVANCE",
            ),
        ]

        for postings in expected_posting_batches:
            self.assertTrue(check_postings_correct_after_simulation(res, postings))

    def test_internal_account_postings_generated_correctly_interest_on_unpaid_fees(
        self,
    ):
        credit_limit = "10000"

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 3, 1, 4)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = credit_limit
        instance_params["annual_fee"] = "100"
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "8000"}})

        template_params["accrue_interest_on_unpaid_fees"] = "True"
        template_params["base_interest_rates"] = default_template_update(
            "base_interest_rates", {"cash_advance": "0.5", "fees": "0.5"}
        )
        template_params["annual_percentage_rate"] = default_template_update(
            "annual_percentage_rate", {"cash_advance": "0.5", "fees": "0.5"}
        )

        sub_tests = [
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        "4000",
                        client_transaction_id="1234",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 1, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "DEFAULT", phase="POSTING_PHASE_PENDING_OUTGOING"
                                ),
                                Decimal("4000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_AUTH"), Decimal("4000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Settle - Spend and Txn Type Fee GL postings",
                events=[
                    create_settlement_event(
                        amount="4000",
                        final=True,
                        event_datetime=offset_datetime(2019, 1, 1, 2),
                        client_transaction_id="1234",
                        instruction_details={"transaction_code": "aaa"},
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 2): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("4200")),
                            (BalanceDimensions("CASH_ADVANCE_AUTH"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("4000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("200"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial repay - GL postings",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "100",
                        client_transaction_id="2",
                        event_datetime=offset_datetime(2019, 1, 1, 4),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 4): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("4100")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("3900"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("200"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Interest Charged - Interest GL postings",
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 2, 0, 0): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("4205.34")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("3900"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("5.34"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_CHARGED"), Decimal("100")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEE_INTEREST_CHARGED"),
                                Decimal("0.0"),
                            ),
                            (
                                BalanceDimensions("ANNUAL_FEE_INTEREST_CHARGED"),
                                Decimal("0.0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Interest billed at SCOD",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 0, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("4365.54")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("3900")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("165.54"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check fees unpaid",
                events=[],
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 25, 1): {
                        "Main account": [
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("200"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_UNPAID"), Decimal("100")),
                        ]
                    }
                },
            ),
            # Interest posting includes amount for interest on interest.
            # Previous Daily - 5.34
            # UNPAID 200 * 0.5 / 365 * 3 = 0.81 | (daily) 5.34 + 0.27 = 5.61
            SubTest(
                description="Interest Charged - Interest GL postings",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 28, 0, 0): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("4610.95")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("5534.46"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("4465.54"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4610.95"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("144.18"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEE_INTEREST_CHARGED"),
                                Decimal("0.81"),
                            ),
                            (
                                BalanceDimensions("ANNUAL_FEE_INTEREST_CHARGED"),
                                Decimal("0.42"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Interest billed at SCOD",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 1, 0, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("4616.70")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("5383.30"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("4616.70"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4616.70"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEE_UNPAID"),
                                Decimal("0.0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("149.52"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("165.54"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEE_INTEREST_BILLED"),
                                Decimal("1.08"),
                            ),
                            (BalanceDimensions("ANNUAL_FEE_UNPAID"), Decimal("0.0")),
                            (
                                BalanceDimensions("ANNUAL_FEE_INTEREST_BILLED"),
                                Decimal("0.56"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay - GL postings",
                # cash advance interest unpaid 165.54
                # + ca interest billed 149.52
                # + annual fee unpaid interest 0.56
                # + cash advance fee interest 1.08
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="316.70",
                        event_datetime=offset_datetime(2019, 3, 1, 4),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 1, 4): {
                        "Main account": [
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("3900.0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEE_UNPAID"),
                                Decimal("0.0"),
                            ),
                            (
                                BalanceDimensions("ANNUAL_FEE_INTEREST_BILLED"),
                                Decimal("0.0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEE_INTEREST_BILLED"),
                                Decimal("0.0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_BILLED"),
                                Decimal("100.0"),
                            ),
                            (BalanceDimensions("OVERDUE_1"), Decimal("187.84")),
                            (BalanceDimensions("OVERDUE_2"), Decimal("0.0")),
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

        res = self.run_test_scenario(test_scenario)

        expected_posting_batches = [
            settled_spend_gl_postings_batch(
                credit_line_amount="4000",
                value_timestamp=offset_datetime(2019, 1, 1, 2),
                txn_type="CASH_ADVANCE",
            ),
            charge_txn_type_fee_gl_postings_batch(
                credit_line_amount="200.00",
                txn_type="cash_advance",
                value_timestamp=offset_datetime(2019, 1, 1, 2),
                hook_effective_datetime=offset_datetime(2019, 1, 1, 2),
            ),
            repay_spend_gl_postings_batch(
                credit_line_amount="100",
                value_timestamp=offset_datetime(2019, 1, 1, 4),
                txn_type="CASH_ADVANCE",
            ),
            charge_interest_gl_postings_batch(
                amount="5.34",
                interest_value_date=datetime(2019, 1, 1).date(),
                value_timestamp=offset_datetime(2019, 1, 1, 23, 59, 59, 999999),
                hook_effective_datetime=offset_datetime(2019, 1, 2),
            ),
            bill_interest_gl_postings_batch(
                credit_line_amount="165.54",
                value_timestamp=offset_datetime(2019, 2, 1),
                hook_effective_datetime=offset_datetime(2019, 2, 1, 0, 0, 2),
                txn_type="CASH_ADVANCE",
            ),
            repay_billed_interest_gl_postings_batch(
                credit_line_amount="165.54",
                value_timestamp=offset_datetime(2019, 3, 1, 4),
                repay_count=0,
                txn_type="CASH_ADVANCE",
            ),
            repay_billed_interest_gl_postings_batch(
                credit_line_amount="149.52",
                value_timestamp=offset_datetime(2019, 3, 1, 4),
                repay_count=1,
                txn_type="CASH_ADVANCE",
            ),
            repay_billed_interest_gl_postings_batch(
                credit_line_amount="0.56",
                value_timestamp=offset_datetime(2019, 3, 1, 4),
                repay_count=2,
                txn_type="ANNUAL_FEE",
            ),
            repay_billed_interest_gl_postings_batch(
                credit_line_amount="1.08",
                value_timestamp=offset_datetime(2019, 3, 1, 4),
                repay_count=3,
                txn_type="CASH_ADVANCE_FEE",
            ),
            bill_interest_gl_postings_batch(
                credit_line_amount="149.52",
                value_timestamp=offset_datetime(2019, 3, 1),
                hook_effective_datetime=offset_datetime(2019, 3, 1, 0, 0, 2),
                txn_type="CASH_ADVANCE",
            ),
            bill_interest_gl_postings_batch(
                credit_line_amount="1.08",
                value_timestamp=offset_datetime(2019, 3, 1),
                hook_effective_datetime=offset_datetime(2019, 3, 1, 0, 0, 2),
                txn_type="CASH_ADVANCE_FEE",
            ),
            bill_interest_gl_postings_batch(
                credit_line_amount="0.56",
                value_timestamp=offset_datetime(2019, 3, 1),
                hook_effective_datetime=offset_datetime(2019, 3, 1, 0, 0, 2),
                txn_type="ANNUAL_FEE",
            ),
            charge_interest_gl_postings_batch(
                amount="5.34",
                interest_value_date=datetime(2019, 2, 27).date(),
                value_timestamp=offset_datetime(2019, 2, 27, 23, 59, 59, 999999),
                hook_effective_datetime=offset_datetime(2019, 2, 28),
                txn_type="CASH_ADVANCE",
            ),
            charge_interest_gl_postings_batch(
                amount="0.27",
                interest_value_date=datetime(2019, 2, 27).date(),
                value_timestamp=offset_datetime(2019, 2, 27, 23, 59, 59, 999999),
                hook_effective_datetime=offset_datetime(2019, 2, 28),
                txn_type="CASH_ADVANCE_FEE",
            ),
            charge_interest_gl_postings_batch(
                amount="0.14",
                interest_value_date=datetime(2019, 2, 27).date(),
                value_timestamp=offset_datetime(2019, 2, 27, 23, 59, 59, 999999),
                hook_effective_datetime=offset_datetime(2019, 2, 28),
                txn_type="ANNUAL_FEE",
            ),
        ]

        for postings in expected_posting_batches:
            self.assertTrue(check_postings_correct_after_simulation(res, postings))

    def test_internal_account_postings_generated_for_extra_limit(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 1, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "1000"
        instance_params["annual_fee"] = "0"

        sub_tests = [
            SubTest(
                description="Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="200",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 1, 1),
                    )
                ],
            ),
            SubTest(
                description="Purchase Beyond Limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000", event_datetime=offset_datetime(2019, 1, 1, 2)
                    )
                ],
            ),
            SubTest(
                description="Repay extra limit principal amount",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="400",
                        event_datetime=offset_datetime(2019, 1, 1, 3),
                    )
                ],
            ),
            SubTest(
                description="Cash advance fees beyond limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="182",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 1, 4),
                    )
                ],
            ),
            SubTest(description="Interest billed at SCOD is beyond limit"),
            SubTest(
                description="Repay extra limit interest + fees + regular principal",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="200",
                        event_datetime=offset_datetime(2019, 2, 1, 1),
                    )
                ],
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        res = self.run_test_scenario(test_scenario)

        expected_posting_batches = [
            settled_spend_gl_postings_batch(
                credit_line_amount="200",
                extra_limit_amount="0",
                value_timestamp=offset_datetime(2019, 1, 1, 1),
                txn_type="CASH_ADVANCE",
            ),
            charge_txn_type_fee_gl_postings_batch(
                credit_line_amount="10",
                extra_limit_amount="0",
                txn_type="cash_advance",
                value_timestamp=offset_datetime(2019, 1, 1, 1),
                hook_effective_datetime=offset_datetime(2019, 1, 1, 1),
            ),
            settled_spend_gl_postings_batch(
                credit_line_amount="790",
                extra_limit_amount="210",
                value_timestamp=offset_datetime(2019, 1, 1, 2),
                txn_type="PURCHASE",
            ),
            repay_spend_gl_postings_batch(
                credit_line_amount="0",
                extra_limit_amount="200",
                value_timestamp=offset_datetime(2019, 1, 1, 3),
                txn_type="CASH_ADVANCE",
                repay_count=0,
            ),
            repay_spend_gl_postings_batch(
                credit_line_amount="190",
                extra_limit_amount="10",
                value_timestamp=offset_datetime(2019, 1, 1, 3),
                txn_type="PURCHASE",
                repay_count=1,
            ),
            settled_spend_gl_postings_batch(
                credit_line_amount="182",
                extra_limit_amount="0",
                value_timestamp=offset_datetime(2019, 1, 1, 4),
                txn_type="CASH_ADVANCE",
            ),
            charge_txn_type_fee_gl_postings_batch(
                credit_line_amount="8",
                extra_limit_amount="1.1",
                txn_type="cash_advance",
                value_timestamp=offset_datetime(2019, 1, 1, 4),
                hook_effective_datetime=offset_datetime(2019, 1, 1, 4),
            ),
            bill_interest_gl_postings_batch(
                credit_line_amount="0",
                extra_limit_amount="5.58",
                value_timestamp=offset_datetime(2019, 2, 1),
                hook_effective_datetime=offset_datetime(2019, 2, 1, 0, 0, 2),
                txn_type="CASH_ADVANCE",
            ),
            repay_billed_interest_gl_postings_batch(
                credit_line_amount="0",
                extra_limit_amount="5.58",
                value_timestamp=offset_datetime(2019, 2, 1, 1),
            ),
            repay_charged_fee_gl_postings_batch(
                credit_line_amount="18",
                extra_limit_amount="1.1",
                fee_type="CASH_ADVANCE_FEE",
                repay_count=1,
                value_timestamp=offset_datetime(2019, 2, 1, 1),
            ),
            repay_spend_gl_postings_batch(
                credit_line_amount="175.32",
                extra_limit_amount="0",
                value_timestamp=offset_datetime(2019, 2, 1, 1),
                txn_type="CASH_ADVANCE",
                repay_count=2,
            ),
        ]

        for postings in expected_posting_batches:
            self.assertTrue(check_postings_correct_after_simulation(res, postings))

    def test_external_fee_charged_billed_and_repaid_correctly(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 26, 2)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"

        sub_tests = [
            SubTest(
                description="External Fee Charged",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        instruction_details={"fee_type": "ATM_WITHDRAWAL_FEE"},
                        event_datetime=offset_datetime(2019, 1, 2),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 2): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("100")),
                            (
                                BalanceDimensions("ATM_WITHDRAWAL_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="SCOD - Overlimit Fee",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("100")),
                            (
                                BalanceDimensions("ATM_WITHDRAWAL_FEES_BILLED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("ATM_WITHDRAWAL_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="PDD - Late Repayment Fee",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 25, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("100")),
                            (
                                BalanceDimensions("ATM_WITHDRAWAL_FEES_UNPAID"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("ATM_WITHDRAWAL_FEES_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("ATM_WITHDRAWAL_FEES_CHARGED"),
                                Decimal("0"),
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

    def test_fee_postings_tagged_correctly(self):

        annual_fee = "100.00"
        overlimit_fee = "125.00"
        late_repayment_fee = "150.00"
        cash_advance_flat_fee = "200.00"

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 26, 2)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "2000"
        instance_params["transaction_type_fees"] = dumps(
            {
                "cash_advance": {
                    "percentage_fee": "0.02",
                    "flat_fee": cash_advance_flat_fee,
                }
            }
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "8000"}})
        instance_params["annual_fee"] = annual_fee
        instance_params["overlimit_fee"] = overlimit_fee
        instance_params["late_repayment_fee"] = late_repayment_fee

        # This test can be expanded as we add new use cases for internal account postings
        # to cover them all
        sub_tests = [
            SubTest(description="Annual Fee"),
            SubTest(
                description="Cash Advance Fee",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2200",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 31),
                    )
                ],
            ),
            SubTest(description="SCOD - Overlimit Fee"),
            SubTest(description="PDD - Late Repayment Fee"),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        res = self.run_test_scenario(test_scenario)

        expected_posting_batches = [
            rebalance_fee_batch(
                amount=annual_fee,
                batch_id_prefix="ANNUAL_FEE",
                fee_type="ANNUAL_FEE",
                event_name="ANNUAL_FEE",
                hook_id="5",
                hook_effective_datetime=offset_datetime(2019, 1, 1, 23, 50),
                value_timestamp=offset_datetime(2019, 1, 1, 23, 50),
            ),
            rebalance_fee_batch(
                amount=cash_advance_flat_fee,
                batch_id_prefix="POST_POSTING",
                fee_type="CASH_ADVANCE_FEE",
                hook_id="13",
                posting_id=".*",
                hook_effective_datetime=offset_datetime(2019, 1, 31),
                value_timestamp=offset_datetime(2019, 1, 31),
            ),
            rebalance_fee_batch(
                amount=overlimit_fee,
                batch_id_prefix="SCOD_0",
                fee_type="OVERLIMIT_FEE",
                event_name="STATEMENT_CUT_OFF",
                hook_id="5",
                hook_effective_datetime=offset_datetime(2019, 2, 1, 0, 0, 2),
                value_timestamp=offset_datetime(2019, 1, 31, 23, 59, 59, 999999),
            ),
        ]
        for postings in expected_posting_batches:
            self.assertTrue(check_postings_correct_after_simulation(res, postings))

    def test_available_balance_checks(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 1, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "8000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {"cash_advance": {"percentage_fee": "0.025", "flat_fee": "500"}}
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "15000"}})
        instance_params["late_repayment_fee"] = "100"
        instance_params["annual_fee"] = "100"
        instance_params["overlimit"] = "500"
        instance_params["overlimit_opt_in"] = "False"

        sub_tests = [
            SubTest(
                description="Cash Advance 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="4000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 2, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 2, 1): {
                        "Main account": [
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("4000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("500"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_CHARGED"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance + Fees prevent Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3401",
                        event_datetime=offset_datetime(2019, 1, 2, 2),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 2, 2): {
                        "Main account": [
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("4000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("500"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_CHARGED"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Charged interest does not prevent Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3399", event_datetime=offset_datetime(2019, 1, 3, 1)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 3, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("8002.95")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("3399")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("4000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("500"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("3.95"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_CHARGED"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Billed principal, fees and interest prevent Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1", event_datetime=offset_datetime(2019, 2, 1, 1)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("8117.5")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("3399")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("4000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("500"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("118.5"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("100")),
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

    def test_txn_type_flat_credit_limit_cannot_be_exceeded(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 1, 2)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "20000"
        instance_params["transaction_type_limits"] = dumps(
            {"cash_advance": {"flat": "200", "percentage": "0.1"}}
        )
        sub_tests = [
            SubTest(
                description="Single Cash Advance below flat limit accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 1, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("19985")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("15")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("15"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("10")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("5"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("15")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Single Cash Advance above flat limit rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 1, 2),
                    ),
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 2): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("19985")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("15")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("15"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("10")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("5"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("15")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Single Cash Advance + outstanding above flat limit rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="195",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 1, 3),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 3): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("19985")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("15")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("15"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("10")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("5"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("15")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Multiple Cash Advance in batch cumulatively above flat limit rejected",
                events=[
                    create_posting_instruction_batch(
                        instructions=[
                            OutboundHardSettlement(
                                target_account_id="Main account",
                                internal_account_id="1",
                                amount="100",
                            ),
                            OutboundHardSettlement(
                                target_account_id="Main account",
                                internal_account_id="1",
                                amount="1000",
                            ),
                        ],
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 1, 4),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 4): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("19985")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("15")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("15"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("10")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("5"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("15")),
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

    def test_txn_type_percentage_credit_limit_cannot_be_exceeded(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 1, 2)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "20000"
        instance_params["transaction_type_limits"] = dumps(
            {"cash_advance": {"flat": "10000", "percentage": "0.001"}}
        )

        sub_tests = [
            SubTest(
                description="Single Cash Advance below % limit accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 1, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("19985")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("15")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("15"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("10")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("5"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("15")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Single Cash Advance above % limit rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 1, 2),
                    ),
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 2): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("19985")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("15")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("15"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("10")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("5"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("15")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Single Cash Advance + outstanding above % limit rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="195",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 1, 3),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 3): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("19985")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("15")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("15"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("10")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("5"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("15")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Multiple Cash Advance in batch cumulatively above % limit rejected",
                events=[
                    create_posting_instruction_batch(
                        instructions=[
                            OutboundHardSettlement(
                                target_account_id="Main account",
                                internal_account_id="1",
                                amount="100",
                            ),
                            OutboundHardSettlement(
                                target_account_id="Main account",
                                internal_account_id="1",
                                amount="1000",
                            ),
                        ],
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 1, 4),
                    ),
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 4): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("19985")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("15")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("15"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("10")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("5"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("15")),
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

    def test_partially_specified_txn_type_credit_limits_do_not_prevent_txns(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 1, 2)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "20000"
        instance_params["transaction_type_limits"] = dumps(
            {
                "cash_advance": {"flat": "10000"},
                "purchase": {"percentage": "0.1"},
                "transfer": {},
            }
        )

        sub_tests = [
            SubTest(
                description="Single Cash Advance below flat limit accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 1, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("19985")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("15")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("15"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("10")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("5"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("15")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Single Purchase above % limit accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1500", event_datetime=offset_datetime(2019, 1, 1, 2)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 2): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("18485")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("1515")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1515"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("10")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1500")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("5"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("1515")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Single transfer (no limits) accepted",
                events=[
                    create_transfer_instruction(
                        amount="185",
                        instruction_details={"transaction_code": "cc"},
                        creditor_target_account_id="Dummy account",
                        debtor_target_account_id="Main account",
                        event_datetime=offset_datetime(2019, 1, 1, 3),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 3): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("18300")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("1700")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1700"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("10")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1500")),
                            (BalanceDimensions("TRANSFER_CHARGED"), Decimal("185")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("5"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("1700")),
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

    def test_no_txn_type_credit_limits_do_not_prevent_txns(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 1, 2)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "20000"
        instance_params["transaction_type_limits"] = dumps({})

        sub_tests = [
            SubTest(
                description="Single Cash Advance accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 1, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("19985")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("15")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("15"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("10")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("5"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("15")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Single Purchase accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1500", event_datetime=offset_datetime(2019, 1, 1, 2)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 2): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("18485")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("1515")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1515"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("10")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1500")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("5"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("1515")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Single transfer accepted",
                events=[
                    create_transfer_instruction(
                        amount="185",
                        instruction_details={"transaction_code": "cc"},
                        creditor_target_account_id="Dummy account",
                        debtor_target_account_id="Main account",
                        event_datetime=offset_datetime(2019, 1, 1, 3),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 3): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("18300")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("1700")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1700"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("10")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1500")),
                            (BalanceDimensions("TRANSFER_CHARGED"), Decimal("185")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("5"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("1700")),
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

    def test_txn_level_and_available_rebalance_with_fees_applied(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 1, 1, 3)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["transaction_references"] = dumps({"balance_transfer": ["ref1", "REF2"]})
        instance_params["transaction_annual_percentage_rate"] = dumps(
            {"balance_transfer": {"ref1": "0.25", "REF2": "0.3"}}
        )
        instance_params["transaction_type_fees"] = dumps(
            {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.05",
                    "flat_fee": "5",
                },
                "balance_transfer": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.05",
                    "flat_fee": "5",
                    "combine": "True",
                    "fee_cap": "51",
                },
            },
        )
        instance_params["annual_fee"] = "0"

        sub_tests = [
            SubTest(
                description="Initial Balance Check",
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("0")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("2000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Balance Transfer REF1",
                events=[
                    create_transfer_instruction(
                        amount="1000",
                        creditor_target_account_id="1",
                        debtor_target_account_id="Main account",
                        event_datetime=offset_datetime(2019, 1, 1, 1),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "ref1",
                        },
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1051.00")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("949.00")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_FEES_CHARGED"),
                                Decimal("51"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Balance Transfer REF2",
                events=[
                    create_transfer_instruction(
                        amount="500",
                        creditor_target_account_id="1",
                        debtor_target_account_id="Main account",
                        event_datetime=offset_datetime(2019, 1, 1, 2),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 2): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1581")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("419")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("500"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_FEES_CHARGED"),
                                Decimal("81"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 1, 3),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 3): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1686")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("314")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("500"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_FEES_CHARGED"),
                                Decimal("81"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("100")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("5"),
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

    def test_credit_limits_prevent_txn_type_with_multiple_refs_over_limit(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 1, 1, 3)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "20000"
        instance_params["transaction_type_limits"] = dumps({"balance_transfer": {"flat": "100"}})
        instance_params["transaction_references"] = dumps({"balance_transfer": ["REF1", "REF2"]})
        instance_params["transaction_annual_percentage_rate"] = dumps(
            {"balance_transfer": {"REF1": "0.25", "REF2": "0.3"}}
        )

        sub_tests = [
            SubTest(
                description="BT REF1 accepted",
                events=[
                    create_transfer_instruction(
                        amount="10",
                        creditor_target_account_id="1",
                        debtor_target_account_id="Main account",
                        event_datetime=offset_datetime(2019, 1, 1, 1),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("19990")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("10")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("10"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("10"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("10")),
                        ]
                    }
                },
            ),
            SubTest(
                description="BT REF2 rejected",
                events=[
                    create_transfer_instruction(
                        amount="95",
                        creditor_target_account_id="1",
                        debtor_target_account_id="Main account",
                        event_datetime=offset_datetime(2019, 1, 1, 2),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 2): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("19990")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("10")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("10"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("10"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("10")),
                        ]
                    }
                },
            ),
            SubTest(
                description="BT REF2 accepted",
                events=[
                    create_transfer_instruction(
                        amount="90",
                        creditor_target_account_id="1",
                        debtor_target_account_id="Main account",
                        event_datetime=offset_datetime(2019, 1, 1, 3),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 3): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("19900")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("100")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("10"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("90"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("100")),
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

    def test_time_limits_prevent_txn_beyond_allowed_days_after_opening_window(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 1, 15, 0, 0, 0)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["annual_fee"] = "0"
        instance_params["credit_limit"] = "2000"
        instance_params["transaction_type_limits"] = dumps(
            {"balance_transfer": {"flat": "100", "allowed_days_after_opening": "14"}}
        )
        instance_params["transaction_references"] = dumps({"balance_transfer": ["REF1", "REF2"]})
        instance_params["transaction_base_interest_rates"] = dumps(
            {"balance_transfer": {"ref1": "0.36"}}
        )

        sub_tests = [
            SubTest(
                description="BT REF1 accepted",
                events=[
                    create_transfer_instruction(
                        amount="10",
                        creditor_target_account_id="1",
                        debtor_target_account_id="Main account",
                        event_datetime=offset_datetime(2019, 1, 14, 23, 59, 59),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 14, 23, 59, 59): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("1990")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("10")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("10"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("10"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("10")),
                        ]
                    }
                },
            ),
            SubTest(
                description="BT REF2 rejected",
                events=[
                    create_transfer_instruction(
                        amount="10",
                        creditor_target_account_id="1",
                        debtor_target_account_id="Main account",
                        event_datetime=offset_datetime(2019, 1, 15, 0, 0, 0),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 15, 0, 0, 0): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("1990")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("10")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("10"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("10"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("10")),
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

    def test_no_ref_invalid_ref_reuse_of_ref_fails(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 1, 1, 7)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "20000"
        instance_params["transaction_type_limits"] = dumps({"balance_transfer": {"flat": "100"}})
        instance_params["transaction_references"] = dumps({"balance_transfer": ["REF1", "REF2"]})
        instance_params["transaction_annual_percentage_rate"] = dumps(
            {"balance_transfer": {"REF1": "0.25"}}
        )
        instance_params["annual_fee"] = "0"

        sub_tests = [
            SubTest(
                description="BT without ref rejected",
                events=[
                    create_transfer_instruction(
                        amount="1",
                        creditor_target_account_id="1",
                        debtor_target_account_id="Main account",
                        event_datetime=offset_datetime(2019, 1, 1, 1),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": None,
                        },
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 1): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("20000")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("0")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_CHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("DEFAULT"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="BT with undefined ref rejected",
                events=[
                    create_transfer_instruction(
                        amount="1",
                        creditor_target_account_id="1",
                        debtor_target_account_id="Main account",
                        event_datetime=offset_datetime(2019, 1, 1, 2),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF9",
                        },
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 2): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("20000")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("0")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF9_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_CHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("DEFAULT"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="BT REF1 accepted",
                events=[
                    create_transfer_instruction(
                        amount="10",
                        creditor_target_account_id="1",
                        debtor_target_account_id="Main account",
                        event_datetime=offset_datetime(2019, 1, 1, 3),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 3): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("19990")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("10")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("10"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("10"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("10")),
                        ]
                    }
                },
            ),
            SubTest(
                description="BT REF1 reuse rejected",
                events=[
                    create_transfer_instruction(
                        amount="20",
                        creditor_target_account_id="1",
                        debtor_target_account_id="Main account",
                        event_datetime=offset_datetime(2019, 1, 1, 4),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 4): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("19990")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("10")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("10"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("10"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("10")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5", event_datetime=offset_datetime(2019, 1, 1, 5)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 5): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("19985")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("15")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("15"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("10"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("5")),
                            (BalanceDimensions("DEFAULT"), Decimal("15")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase [reuse] accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="6", event_datetime=offset_datetime(2019, 1, 1, 6)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 6): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("19979")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("21")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("21"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("10"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("11")),
                            (BalanceDimensions("DEFAULT"), Decimal("21")),
                        ]
                    }
                },
            ),
            SubTest(
                description="BT REF2 accepted",
                events=[
                    create_transfer_instruction(
                        amount="3",
                        creditor_target_account_id="1",
                        debtor_target_account_id="Main account",
                        event_datetime=offset_datetime(2019, 1, 1, 7),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 7): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("19976")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("24")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("24"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("10"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("3"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("11")),
                            (BalanceDimensions("DEFAULT"), Decimal("24")),
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


def settled_spend_gl_postings_batch(
    credit_line_amount,
    extra_limit_amount=Decimal(0),
    commitment_account_id=REVOCABLE_COMMITMENT_INT,
    contra_account_id=OFF_BALANCE_SHEET_CONTRA_INT,
    value_timestamp: datetime = datetime(1970, 1, 1),
    txn_type="PURCHASE",
):

    credit_line_amount = Decimal(credit_line_amount)
    extra_limit_amount = Decimal(extra_limit_amount)

    # batch ids and client transaction ids contain the nanosecond epoch, based on value_timestamp
    ns_epoch = f'{Decimal(value_timestamp.timestamp()) * Decimal("1000000000"):.0f}'
    loan_account = LOAN_INT
    instruction_details = {
        "accounting_event": "LOAN_DISBURSEMENT",
        "account_id": "Main account",
        "inst_type": txn_type.lower(),
    }

    posting_instructions = [
        dict(
            client_transaction_id=f"CUSTOMER_TO_LOAN_GL-Main account_13"
            f"__{ns_epoch}-PRINCIPAL_SPENT_{txn_type}_.+",
            instruction_details=instruction_details,
            custom_instruction=dict(
                postings=[
                    dict(
                        credit=False,
                        amount=str(credit_line_amount + extra_limit_amount),
                        account_id=loan_account,
                        account_address="DEFAULT",
                        denomination=DEFAULT_DENOM,
                    ),
                    dict(
                        credit=True,
                        amount=str(credit_line_amount + extra_limit_amount),
                        account_id="Main account",
                        account_address="INTERNAL",
                        denomination=DEFAULT_DENOM,
                    ),
                ]
            ),
        ),
    ]

    if credit_line_amount > 0:
        posting_instructions.extend(
            [
                dict(
                    client_transaction_id=f"DECREASE_COMMITMENT_GL-Main account_13"
                    f"__{ns_epoch}-PRINCIPAL_SPENT_{txn_type}_.+",
                    instruction_details=instruction_details,
                    custom_instruction=dict(
                        postings=[
                            dict(
                                credit=False,
                                amount=str(credit_line_amount),
                                account_id=commitment_account_id,
                                account_address="DEFAULT",
                                denomination=DEFAULT_DENOM,
                            ),
                            dict(
                                credit=True,
                                amount=str(credit_line_amount),
                                account_id=contra_account_id,
                                account_address="DEFAULT",
                                denomination=DEFAULT_DENOM,
                            ),
                        ]
                    ),
                )
            ]
        )
    return dict(
        client_batch_id=f"POST_POSTING-Main account_13__{ns_epoch}",
        posting_instructions=posting_instructions,
        value_timestamp=value_timestamp,
    )


def charge_txn_type_fee_gl_postings_batch(
    credit_line_amount,
    extra_limit_amount=0,
    commitment_account_id=REVOCABLE_COMMITMENT_INT,
    contra_account_id=OFF_BALANCE_SHEET_CONTRA_INT,
    txn_type="",
    value_timestamp: datetime = datetime(1970, 1, 1),
    hook_effective_datetime: datetime = datetime(1970, 1, 1),
):
    credit_line_amount = Decimal(credit_line_amount)
    extra_limit_amount = Decimal(extra_limit_amount)
    fee_type = f"{txn_type.upper()}_FEE"

    # batch ids and client transaction ids contain the nanosecond epoch, based on value_timestamp
    ns_epoch = f'{Decimal(hook_effective_datetime.timestamp()) * Decimal("1000000000"):.0f}'
    hook_execution_id = f"Main account_13__{ns_epoch}"
    loan_internal_account = LOAN_INT
    income_internal_account = INCOME_INT

    posting_instructions = [
        dict(
            client_transaction_id=f"LOAN_TO_INCOME_GL-{hook_execution_id}-"
            f"FEES_CHARGED_{fee_type}_.*",
            instruction_details={
                "accounting_event": "LOAN_FEES",
                "account_id": "Main account",
                "inst_type": txn_type.lower(),
            },
            custom_instruction=dict(
                postings=[
                    dict(
                        credit=False,
                        amount=str(credit_line_amount + extra_limit_amount),
                        account_id=loan_internal_account,
                        account_address="DEFAULT",
                        denomination=DEFAULT_DENOM,
                    ),
                    dict(
                        credit=True,
                        amount=str(credit_line_amount + extra_limit_amount),
                        account_id=income_internal_account,
                        account_address="DEFAULT",
                        denomination=DEFAULT_DENOM,
                    ),
                ]
            ),
        )
    ]
    if credit_line_amount > 0:
        posting_instructions.extend(
            [
                dict(
                    client_transaction_id=f"DECREASE_COMMITMENT_GL-{hook_execution_id}"
                    f"-FEES_CHARGED_{fee_type}_.*",
                    instruction_details={
                        "accounting_event": "LOAN_FEES",
                        "account_id": "Main account",
                        "inst_type": txn_type.lower(),
                    },
                    custom_instruction=dict(
                        postings=[
                            dict(
                                credit=False,
                                amount=str(credit_line_amount),
                                account_id=commitment_account_id,
                                account_address="DEFAULT",
                                denomination=DEFAULT_DENOM,
                            ),
                            dict(
                                credit=True,
                                amount=str(credit_line_amount),
                                account_id=contra_account_id,
                                account_address="DEFAULT",
                                denomination=DEFAULT_DENOM,
                            ),
                        ]
                    ),
                )
            ]
        )

    return dict(
        client_batch_id=f"POST_POSTING-{hook_execution_id}",
        posting_instructions=posting_instructions,
        value_timestamp=value_timestamp,
    )


def repay_spend_gl_postings_batch(
    credit_line_amount,
    extra_limit_amount=0,
    commitment_account_id=REVOCABLE_COMMITMENT_INT,
    contra_account_id=OFF_BALANCE_SHEET_CONTRA_INT,
    repay_count=0,
    txn_type="PURCHASE",
    value_timestamp: datetime = datetime(1970, 1, 1),
):
    credit_line_amount = Decimal(credit_line_amount)
    extra_limit_amount = Decimal(extra_limit_amount)

    # batch ids and client transaction ids contain the nanosecond epoch, based on value_timestamp
    ns_epoch = f'{Decimal(value_timestamp.timestamp()) * Decimal("1000000000"):.0f}'
    loan_account = LOAN_INT
    instruction_details = {
        "accounting_event": "LOAN_REPAYMENT",
        "account_id": "Main account",
        "inst_type": txn_type.lower(),
    }

    posting_instructions = [
        dict(
            client_transaction_id=f"LOAN_TO_CUSTOMER_GL-Main account_13"
            f"__{ns_epoch}-PRINCIPAL_REPAID_{txn_type}.+_{repay_count}",
            instruction_details=instruction_details,
            custom_instruction=dict(
                postings=[
                    dict(
                        credit=False,
                        amount=str(credit_line_amount + extra_limit_amount),
                        account_id="Main account",
                        account_address="INTERNAL",
                        denomination=DEFAULT_DENOM,
                    ),
                    dict(
                        credit=True,
                        amount=str(credit_line_amount + extra_limit_amount),
                        account_id=loan_account,
                        account_address="DEFAULT",
                        denomination=DEFAULT_DENOM,
                    ),
                ]
            ),
        ),
    ]

    if credit_line_amount > 0:
        posting_instructions.extend(
            [
                dict(
                    client_transaction_id=f"INCREASE_COMMITMENT_GL-Main account_13"
                    f"__{ns_epoch}-PRINCIPAL_REPAID_{txn_type}.+_{repay_count}",
                    instruction_details=instruction_details,
                    custom_instruction=dict(
                        postings=[
                            dict(
                                credit=False,
                                amount=str(credit_line_amount),
                                account_id=contra_account_id,
                                account_address="DEFAULT",
                                denomination=DEFAULT_DENOM,
                            ),
                            dict(
                                credit=True,
                                amount=str(credit_line_amount),
                                account_id=commitment_account_id,
                                account_address="DEFAULT",
                                denomination=DEFAULT_DENOM,
                            ),
                        ]
                    ),
                )
            ]
        )

    return dict(
        client_batch_id=f"POST_POSTING-Main account_13__{ns_epoch}",
        posting_instructions=posting_instructions,
        value_timestamp=value_timestamp,
    )


def charge_annual_fee_gl_postings_batch(
    amount,
    commitment_account_id=REVOCABLE_COMMITMENT_INT,
    contra_account_id=OFF_BALANCE_SHEET_CONTRA_INT,
    value_timestamp: datetime = datetime(1970, 1, 1),
    hook_effective_datetime: datetime = datetime(1970, 1, 1),
):

    # batch ids and client transaction ids contain the nanosecond epoch, based on value_timestamp
    ns_epoch = f'{Decimal(hook_effective_datetime.timestamp()) * Decimal("1000000000"):.0f}'
    hook_execution_id = f"Main account_5_ANNUAL_FEE_{ns_epoch}"
    loan_internal_account = ANNUAL_FEE_LOAN_INT
    income_internal_account = ANNUAL_FEE_INCOME_INT
    return dict(
        client_batch_id=f"ANNUAL_FEE-{hook_execution_id}",
        posting_instructions=[
            dict(
                client_transaction_id=f"LOAN_TO_INCOME_GL-{hook_execution_id}-"
                f"FEES_CHARGED_ANNUAL_FEE",
                instruction_details={
                    "accounting_event": "LOAN_FEES",
                    "account_id": "Main account",
                },
                custom_instruction=dict(
                    postings=[
                        dict(
                            credit=False,
                            amount=amount,
                            account_id=loan_internal_account,
                            account_address="DEFAULT",
                            denomination=DEFAULT_DENOM,
                        ),
                        dict(
                            credit=True,
                            amount=amount,
                            account_id=income_internal_account,
                            account_address="DEFAULT",
                            denomination=DEFAULT_DENOM,
                        ),
                    ]
                ),
            ),
            dict(
                client_transaction_id=f"DECREASE_COMMITMENT_GL-{hook_execution_id}-"
                f"FEES_CHARGED_ANNUAL_FEE",
                instruction_details={
                    "accounting_event": "LOAN_FEES",
                    "account_id": "Main account",
                },
                custom_instruction=dict(
                    postings=[
                        dict(
                            credit=False,
                            amount=amount,
                            account_id=commitment_account_id,
                            account_address="DEFAULT",
                            denomination=DEFAULT_DENOM,
                        ),
                        dict(
                            credit=True,
                            amount=amount,
                            account_id=contra_account_id,
                            account_address="DEFAULT",
                            denomination=DEFAULT_DENOM,
                        ),
                    ]
                ),
            ),
        ],
        value_timestamp=value_timestamp,
    )


def charge_interest_gl_postings_batch(
    amount,
    interest_value_date=date(1970, 1, 1),
    txn_type="CASH_ADVANCE",
    value_timestamp: datetime = datetime(1970, 1, 1),
    hook_effective_datetime: datetime = datetime(1970, 1, 1),
):

    # batch ids and client transaction ids contain the nanosecond epoch, based on value_timestamp
    ns_epoch = f'{Decimal(hook_effective_datetime.timestamp()) * Decimal("1000000000"):.0f}'
    air_internal_account = AIR_INT
    interest_income_internal_account = INTEREST_INCOME_INT

    return dict(
        client_batch_id=f"ACCRUE_INTEREST-Main account_5_ACCRUE_INTEREST_{ns_epoch}",
        posting_instructions=[
            dict(
                client_transaction_id=f"AIR_TO_INCOME_GL-Main account_5"
                f"_ACCRUE_INTEREST_{ns_epoch}-INTEREST_CHARGED_{txn_type}",
                instruction_details={
                    "accounting_event": "LOAN_CHARGED_INTEREST",
                    "account_id": "Main account",
                    "inst_type": txn_type.lower(),
                    "interest_value_date": str(interest_value_date),
                },
                custom_instruction=dict(
                    postings=[
                        dict(
                            credit=False,
                            amount=amount,
                            account_id=air_internal_account,
                            account_address="DEFAULT",
                            denomination=DEFAULT_DENOM,
                        ),
                        dict(
                            credit=True,
                            amount=amount,
                            account_id=interest_income_internal_account,
                            account_address="DEFAULT",
                            denomination=DEFAULT_DENOM,
                        ),
                    ]
                ),
            ),
        ],
        value_timestamp=value_timestamp,
    )


def bill_interest_gl_postings_batch(
    credit_line_amount,
    extra_limit_amount=0,
    commitment_account_id=REVOCABLE_COMMITMENT_INT,
    contra_account_id=OFF_BALANCE_SHEET_CONTRA_INT,
    txn_type="CASH_ADVANCE",
    value_timestamp: datetime = datetime(1970, 1, 1),
    hook_effective_datetime: datetime = datetime(1970, 1, 1),
):
    credit_line_amount = Decimal(credit_line_amount)
    extra_limit_amount = Decimal(extra_limit_amount)

    # batch ids and client transaction ids contain the nanosecond epoch, based on value_timestamp
    ns_epoch = f'{Decimal(hook_effective_datetime.timestamp()) * Decimal("1000000000"):.0f}'
    loan_internal_account = LOAN_INT
    air_internal_account = AIR_INT

    posting_instructions = [
        dict(
            client_transaction_id=f"LOAN_TO_AIR_GL-Main account_5"
            f"_STATEMENT_CUT_OFF_{ns_epoch}-INTEREST_BILLED_{txn_type}",
            instruction_details={
                "accounting_event": "LOAN_CHARGED_INTEREST",
                "account_id": "Main account",
                "inst_type": txn_type.lower(),
            },
            custom_instruction=dict(
                postings=[
                    dict(
                        credit=False,
                        amount=str(credit_line_amount + extra_limit_amount),
                        account_id=loan_internal_account,
                        account_address="DEFAULT",
                        denomination=DEFAULT_DENOM,
                    ),
                    dict(
                        credit=True,
                        amount=str(credit_line_amount + extra_limit_amount),
                        account_id=air_internal_account,
                        account_address="DEFAULT",
                        denomination=DEFAULT_DENOM,
                    ),
                ]
            ),
        ),
    ]
    if credit_line_amount > 0:
        posting_instructions.extend(
            [
                dict(
                    client_transaction_id=f"DECREASE_COMMITMENT_GL-Main account_5"
                    f"_STATEMENT_CUT_OFF_{ns_epoch}-INTEREST_BILLED_{txn_type}",
                    instruction_details={
                        "accounting_event": "LOAN_CHARGED_INTEREST",
                        "account_id": "Main account",
                        "inst_type": txn_type.lower(),
                    },
                    custom_instruction=dict(
                        postings=[
                            dict(
                                credit=False,
                                amount=str(credit_line_amount),
                                account_id=commitment_account_id,
                                account_address="DEFAULT",
                                denomination=DEFAULT_DENOM,
                            ),
                            dict(
                                credit=True,
                                amount=str(credit_line_amount),
                                account_id=contra_account_id,
                                account_address="DEFAULT",
                                denomination=DEFAULT_DENOM,
                            ),
                        ]
                    ),
                )
            ]
        )

    return dict(
        client_batch_id=f"SCOD_1-Main account_5_STATEMENT_CUT_OFF_{ns_epoch}",
        posting_instructions=posting_instructions,
        value_timestamp=value_timestamp,
    )


def repay_billed_interest_gl_postings_batch(
    credit_line_amount,
    extra_limit_amount=0,
    commitment_account_id=REVOCABLE_COMMITMENT_INT,
    contra_account_id=OFF_BALANCE_SHEET_CONTRA_INT,
    repay_count=0,
    txn_type="CASH_ADVANCE",
    value_timestamp: datetime = datetime(1970, 1, 1),
):
    credit_line_amount = Decimal(credit_line_amount)
    extra_limit_amount = Decimal(extra_limit_amount)

    # batch ids and client transaction ids contain the nanosecond epoch, based on value_timestamp
    ns_epoch = f'{Decimal(value_timestamp.timestamp()) * Decimal("1000000000"):.0f}'
    loan_internal_account = "1" if txn_type.endswith("_FEE") else LOAN_INT

    posting_instructions = [
        dict(
            client_transaction_id=f"CUSTOMER_TO_LOAN_GL-Main account_13"
            f"__{ns_epoch}-BILLED_INTEREST_REPAID_{txn_type}_."
            f"+_{repay_count}",
            instruction_details={
                "accounting_event": "LOAN_REPAYMENT",
                "account_id": "Main account",
                "inst_type": txn_type.lower(),
            },
            custom_instruction=dict(
                postings=[
                    dict(
                        credit=False,
                        amount=str(credit_line_amount + extra_limit_amount),
                        account_id="Main account",
                        account_address="INTERNAL",
                        denomination=DEFAULT_DENOM,
                    ),
                    dict(
                        credit=True,
                        amount=str(credit_line_amount + extra_limit_amount),
                        account_id=loan_internal_account,
                        account_address="DEFAULT",
                        denomination=DEFAULT_DENOM,
                    ),
                ]
            ),
        ),
    ]
    if credit_line_amount > 0:
        posting_instructions.extend(
            [
                dict(
                    client_transaction_id=f"INCREASE_COMMITMENT_GL-Main account_13"
                    f"__{ns_epoch}-BILLED_INTEREST_REPAID_{txn_type}_."
                    f"+_{repay_count}",
                    instruction_details={
                        "accounting_event": "LOAN_REPAYMENT",
                        "account_id": "Main account",
                        "inst_type": txn_type.lower(),
                    },
                    custom_instruction=dict(
                        postings=[
                            dict(
                                credit=False,
                                amount=str(credit_line_amount),
                                account_id=contra_account_id,
                                account_address="DEFAULT",
                                denomination=DEFAULT_DENOM,
                            ),
                            dict(
                                credit=True,
                                amount=str(credit_line_amount),
                                account_id=commitment_account_id,
                                account_address="DEFAULT",
                                denomination=DEFAULT_DENOM,
                            ),
                        ]
                    ),
                )
            ]
        )

    return dict(
        client_batch_id=f"POST_POSTING-Main account_13__{ns_epoch}",
        posting_instructions=posting_instructions,
        value_timestamp=value_timestamp,
    )


def repay_charged_fee_gl_postings_batch(
    credit_line_amount,
    extra_limit_amount=0,
    commitment_account_id=REVOCABLE_COMMITMENT_INT,
    contra_account_id=OFF_BALANCE_SHEET_CONTRA_INT,
    fee_type="CASH_ADVANCE",
    repay_count=0,
    value_timestamp: datetime = datetime(1970, 1, 1),
):
    credit_line_amount = Decimal(credit_line_amount)
    extra_limit_amount = Decimal(extra_limit_amount)

    # batch ids and client transaction ids contain the nanosecond epoch, based on value_timestamp
    ns_epoch = f'{Decimal(value_timestamp.timestamp()) * Decimal("1000000000"):.0f}'
    loan_internal_account = LOAN_INT

    posting_instructions = [
        dict(
            client_transaction_id=f"CUSTOMER_TO_LOAN_GL-Main account_13"
            f"__{ns_epoch}-FEES_REPAID_{fee_type}_.+_{repay_count}",
            instruction_details={
                "accounting_event": "LOAN_REPAYMENT",
                "account_id": "Main account",
            },
            custom_instruction=dict(
                postings=[
                    dict(
                        credit=False,
                        amount=str(credit_line_amount + extra_limit_amount),
                        account_id="Main account",
                        account_address="INTERNAL",
                        denomination=DEFAULT_DENOM,
                    ),
                    dict(
                        credit=True,
                        amount=str(credit_line_amount + extra_limit_amount),
                        account_id=loan_internal_account,
                        account_address="DEFAULT",
                        denomination=DEFAULT_DENOM,
                    ),
                ]
            ),
        ),
    ]
    if credit_line_amount > 0:
        posting_instructions.extend(
            [
                dict(
                    client_transaction_id=f"INCREASE_COMMITMENT_GL-Main account_13"
                    f"__{ns_epoch}-FEES_REPAID_{fee_type}_.+_{repay_count}",
                    instruction_details={
                        "accounting_event": "LOAN_REPAYMENT",
                        "account_id": "Main account",
                    },
                    custom_instruction=dict(
                        postings=[
                            dict(
                                credit=False,
                                amount=str(credit_line_amount),
                                account_id=contra_account_id,
                                account_address="DEFAULT",
                                denomination=DEFAULT_DENOM,
                            ),
                            dict(
                                credit=True,
                                amount=str(credit_line_amount),
                                account_id=commitment_account_id,
                                account_address="DEFAULT",
                                denomination=DEFAULT_DENOM,
                            ),
                        ]
                    ),
                )
            ]
        )

    return dict(
        client_batch_id=f"POST_POSTING-Main account_13__{ns_epoch}",
        posting_instructions=posting_instructions,
        value_timestamp=value_timestamp,
    )


def repay_deposit_gl_postings_batch(
    amount,
    other_liability_account_id=OTHER_LIABILITY_INT,
    value_timestamp: datetime = datetime(1970, 1, 1),
):
    # batch ids and client transaction ids contain the nanosecond epoch, based on value_timestamp
    ns_epoch = f'{Decimal(value_timestamp.timestamp()) * Decimal("1000000000"):.0f}'
    instruction_details = {
        "accounting_event": "LOAN_REPAYMENT",
        "account_id": "Main account",
    }

    return dict(
        client_batch_id=f"POST_POSTING-Main account_13__{ns_epoch}",
        posting_instructions=[
            dict(
                client_transaction_id=f"CUSTOMER_TO_OTHER_LIABILITY_GL-Main account_13"
                f"__{ns_epoch}-REPAYMENT_RECEIVED_.+",
                instruction_details=instruction_details,
                custom_instruction=dict(
                    postings=[
                        dict(
                            credit=False,
                            amount=amount,
                            account_id="Main account",
                            account_address="INTERNAL",
                            denomination=DEFAULT_DENOM,
                        ),
                        dict(
                            credit=True,
                            amount=amount,
                            account_id=other_liability_account_id,
                            account_address="DEFAULT",
                            denomination=DEFAULT_DENOM,
                        ),
                    ]
                ),
            ),
        ],
        value_timestamp=value_timestamp,
    )


def spend_deposit_gl_postings_batch(
    amount,
    other_liability_account_id=OTHER_LIABILITY_INT,
    value_timestamp: datetime = datetime(1970, 1, 1),
    event="LOAN_DISBURSEMENT",
    trigger="",
):
    # batch ids and client transaction ids contain the nanosecond epoch, based on value_timestamp
    ns_epoch = f'{Decimal(value_timestamp.timestamp()) * Decimal("1000000000"):.0f}'
    instruction_details = {
        "accounting_event": event,
        "account_id": "Main account",
    }

    return dict(
        client_batch_id=f"POST_POSTING-Main account_13__{ns_epoch}",
        posting_instructions=[
            dict(
                client_transaction_id=f"OTHER_LIABILITY_TO_CUSTOMER_GL-Main account_13"
                f"__{ns_epoch}-{trigger}_.+",
                instruction_details=instruction_details,
                custom_instruction=dict(
                    postings=[
                        dict(
                            credit=False,
                            amount=amount,
                            account_id=other_liability_account_id,
                            account_address="DEFAULT",
                            denomination=DEFAULT_DENOM,
                        ),
                        dict(
                            credit=True,
                            amount=amount,
                            account_id="Main account",
                            account_address="INTERNAL",
                            denomination=DEFAULT_DENOM,
                        ),
                    ]
                ),
            ),
        ],
        value_timestamp=value_timestamp,
    )


def charge_dispute_fee_gl_postings_batch(
    amount,
    commitment_account_id=REVOCABLE_COMMITMENT_INT,
    contra_account_id=OFF_BALANCE_SHEET_CONTRA_INT,
    value_timestamp: datetime = datetime(1970, 1, 1),
):
    # batch ids and client transaction ids contain the nanosecond epoch, based on value_timestamp
    ns_epoch = f'{Decimal(value_timestamp.timestamp()) * Decimal("1000000000"):.0f}'
    loan_account = DISPUTE_FEE_LOAN_INT
    instruction_details = {
        "accounting_event": "LOAN_FEES",
        "account_id": "Main account",
    }

    return dict(
        client_batch_id=f"POST_POSTING-Main account_13__{ns_epoch}",
        posting_instructions=[
            dict(
                client_transaction_id=f"LOAN_TO_CUSTOMER_GL-Main account_13"
                f"__{ns_epoch}-FEES_CHARGED_DISPUTE_FEE_.+",
                instruction_details=instruction_details,
                custom_instruction=dict(
                    postings=[
                        dict(
                            credit=False,
                            amount=amount,
                            account_id=loan_account,
                            account_address="DEFAULT",
                            denomination=DEFAULT_DENOM,
                        ),
                        dict(
                            credit=True,
                            amount=amount,
                            account_id="Main account",
                            account_address="INTERNAL",
                            denomination=DEFAULT_DENOM,
                        ),
                    ]
                ),
            ),
            dict(
                client_transaction_id=f"DECREASE_COMMITMENT_GL-Main account_13"
                f"__{ns_epoch}-FEES_CHARGED_DISPUTE_FEE_.+",
                instruction_details=instruction_details,
                custom_instruction=dict(
                    postings=[
                        dict(
                            credit=False,
                            amount=amount,
                            account_id=commitment_account_id,
                            account_address="DEFAULT",
                            denomination=DEFAULT_DENOM,
                        ),
                        dict(
                            credit=True,
                            amount=amount,
                            account_id=contra_account_id,
                            account_address="DEFAULT",
                            denomination=DEFAULT_DENOM,
                        ),
                    ]
                ),
            ),
        ],
        value_timestamp=value_timestamp,
    )


def repay_dispute_fee_gl_postings_batch(
    amount,
    commitment_account_id=REVOCABLE_COMMITMENT_INT,
    contra_account_id=OFF_BALANCE_SHEET_CONTRA_INT,
    value_timestamp: datetime = datetime(1970, 1, 1),
):
    # batch ids and client transaction ids contain the nanosecond epoch, based on value_timestamp
    ns_epoch = f'{Decimal(value_timestamp.timestamp()) * Decimal("1000000000"):.0f}'
    loan_account = DISPUTE_FEE_LOAN_INT
    instruction_details = {
        "accounting_event": "LOAN_REPAYMENT",
        "account_id": "Main account",
    }

    return dict(
        client_batch_id=f"POST_POSTING-Main account_13__{ns_epoch}",
        posting_instructions=[
            dict(
                client_transaction_id=f"CUSTOMER_TO_LOAN_GL-Main account_13"
                f"__{ns_epoch}-FEES_REPAID_DISPUTE_FEE_.+",
                instruction_details=instruction_details,
                custom_instruction=dict(
                    postings=[
                        dict(
                            credit=False,
                            amount=amount,
                            account_id="Main account",
                            account_address="INTERNAL",
                            denomination=DEFAULT_DENOM,
                        ),
                        dict(
                            credit=True,
                            amount=amount,
                            account_id=loan_account,
                            account_address="DEFAULT",
                            denomination=DEFAULT_DENOM,
                        ),
                    ]
                ),
            ),
            dict(
                client_transaction_id=f"INCREASE_COMMITMENT_GL-Main account_13"
                f"__{ns_epoch}-FEES_REPAID_DISPUTE_FEE_.+",
                instruction_details=instruction_details,
                custom_instruction=dict(
                    postings=[
                        dict(
                            credit=False,
                            amount=amount,
                            account_id=contra_account_id,
                            account_address="DEFAULT",
                            denomination=DEFAULT_DENOM,
                        ),
                        dict(
                            credit=True,
                            amount=amount,
                            account_id=commitment_account_id,
                            account_address="DEFAULT",
                            denomination=DEFAULT_DENOM,
                        ),
                    ]
                ),
            ),
        ],
        value_timestamp=value_timestamp,
    )


def repay_charged_interest_gl_postings_batch(
    amount, txn_type="CASH_ADVANCE", value_timestamp: datetime = datetime(1970, 1, 1)
):
    # batch ids and client transaction ids contain the nanosecond epoch, based on value_timestamp
    ns_epoch = f'{Decimal(value_timestamp.timestamp()) * Decimal("1000000000"):.0f}'
    air_internal_account = AIR_INT

    return dict(
        client_batch_id=f"POST_POSTING-Main account_13__{ns_epoch}",
        posting_instructions=[
            dict(
                client_transaction_id=f"CUSTOMER_TO_AIR-Main account_13"
                f"__{ns_epoch}-CHARGED_INTEREST_REPAID_{txn_type}",
                instruction_details={
                    "accounting_event": "LOAN_REPAYMENT",
                    "account_id": "Main account",
                    "inst_type": txn_type.lower(),
                },
                custom_instruction=dict(
                    postings=[
                        dict(
                            credit=False,
                            amount=amount,
                            account_id="Main account",
                            account_address="INTERNAL",
                            denomination=DEFAULT_DENOM,
                        ),
                        dict(
                            credit=True,
                            amount=amount,
                            account_id=air_internal_account,
                            account_address="DEFAULT",
                            denomination=DEFAULT_DENOM,
                        ),
                    ]
                ),
            ),
        ],
        value_timestamp=value_timestamp,
    )


def rebalance_fee_batch(
    amount=Decimal(0),
    batch_id_prefix="",
    fee_type="",
    event_name="",
    hook_id="",
    posting_id="",
    txn_type="",
    hook_effective_datetime: datetime = datetime(1970, 1, 1),
    value_timestamp: datetime = datetime(1970, 1, 1),
):

    # TODO: all of this should become a helper method
    ns_epoch = f'{Decimal(hook_effective_datetime.timestamp()) * Decimal("1000000000"):.0f}'
    hook_execution_id = f"Main account_{hook_id}_{event_name}_{ns_epoch}"
    batch_id = f"{batch_id_prefix}-{hook_execution_id}"

    if txn_type:
        fee_type = f"{txn_type.upper()}_FEE"

    address = f"{fee_type}S_CHARGED"

    # TODO: when we refactor other methods we'll be able to pass in the posting id to the 'trigger'
    client_transaction_id = f"REBALANCE_{address}-{hook_execution_id}-FEES_CHARGED_{fee_type}"

    if posting_id:
        client_transaction_id += f"{posting_id}"

    return dict(
        client_batch_id=batch_id,
        posting_instructions=[
            dict(
                client_transaction_id=client_transaction_id,
                instruction_details={"fee_type": fee_type},
                custom_instruction=dict(
                    postings=[
                        dict(
                            credit=False,
                            amount=amount,
                            account_id="Main account",
                            account_address=address,
                            denomination=DEFAULT_DENOM,
                        ),
                        dict(
                            credit=True,
                            amount=amount,
                            account_id="Main account",
                            account_address="INTERNAL",
                            denomination=DEFAULT_DENOM,
                        ),
                    ]
                ),
            )
        ],
        value_timestamp=value_timestamp,
    )
