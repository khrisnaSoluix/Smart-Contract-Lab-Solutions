# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
import re
from datetime import datetime
from decimal import Decimal
from json import dumps
from unittest import skip
from zoneinfo import ZoneInfo

# library
from library.credit_card.test.simulation.parameters import (
    DEFAULT_CREDIT_CARD_INSTANCE_PARAMS,
    DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS,
    default_template_update,
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
    create_auth_adjustment_instruction,
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_outbound_authorisation_instruction,
    create_outbound_hard_settlement_instruction,
    create_posting_instruction_batch,
    create_release_event,
    create_settlement_event,
    create_transfer_instruction,
)
from inception_sdk.test_framework.contracts.simulation.utils import SimulationTestCase
from inception_sdk.vault.postings.posting_classes import OutboundHardSettlement, Transfer

CONTRACT_FILE = "library/credit_card/contracts/template/credit_card.py"
EXPIRE_INTEREST_FREE_PERIODS_WORKFLOW = "EXPIRE_INTEREST_FREE_PERIODS"
ASSET_CONTRACT_FILE = "internal_accounts/testing_internal_asset_account_contract.py"
LIABILITY_CONTRACT_FILE = "internal_accounts/testing_internal_liability_account_contract.py"
CONTRACT_FILES = [CONTRACT_FILE, ASSET_CONTRACT_FILE, LIABILITY_CONTRACT_FILE]
DEFAULT_DENOM = "GBP"
EXPIRE_INTEREST_FREE_PERIODS_WORKFLOW = "EXPIRE_INTEREST_FREE_PERIODS"
INCOME_INT = "1"
ANNUAL_FEE_INCOME_INT = "1"
INTEREST_INCOME_INT = "1"
OTHER_LIABILITY_INT = "1"

default_instance_params = DEFAULT_CREDIT_CARD_INSTANCE_PARAMS
default_template_params = DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS

VALID_FORMATS = ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"]


def parse_datetime(text, formats=VALID_FORMATS):
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    raise ValueError("no valid date format found")


def check_postings_correct_after_simulation(res, posting):
    post_cbi = posting["client_batch_id"]
    post_time = posting["value_timestamp"]
    post_cti = posting["posting_instructions"][0]["client_transaction_id"]
    post_amt = posting["posting_instructions"][0]["custom_instruction"]["postings"][0]["amount"]
    for result in res:
        if result["result"]["posting_instruction_batches"]:
            pib = result["result"]["posting_instruction_batches"][0]
            res_cbi = pib["client_batch_id"]
            res_time = parse_datetime(pib["value_timestamp"]).astimezone(ZoneInfo("UTC"))
            for res_instruction in pib["posting_instructions"]:
                res_cti = res_instruction["client_transaction_id"]
                res_amt = res_instruction["committed_postings"][0]["amount"]
                if (
                    post_cbi == res_cbi
                    and re.search(post_cti, res_cti)
                    and post_time == res_time
                    and Decimal(post_amt) == Decimal(res_amt)
                ):
                    return True
    return False


class CreditCardTransactionTest(SimulationTestCase):
    """
    Test preposting hook, rebalancing fees, overlimit, credit limit
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

    def test_transaction_type_fees_charged_on_settlement_and_billed_at_scod(self):
        """
        A cash advance is authorised. When it is settled, fees are charged. After Scod, fees are
        billed
        """
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {**default_instance_params, "annual_fee": "0"}
        template_params = {
            **default_template_params,
            "transaction_types": default_template_update(
                "transaction_types",
                {"cash_advance": {"charge_interest_from_transaction_date": "False"}},
            ),
        }

        sub_tests = [
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        "200",
                        client_transaction_id="1234",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 31, 1, tzinfo=ZoneInfo("UTC")),
                        client_transaction_id="1234",
                        instruction_details={"transaction_code": "aaa"},
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 31, 1, tzinfo=ZoneInfo("UTC")): {
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
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 25, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "annual_fee": "0",
            "transaction_type_fees": dumps(
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
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "6000"}}),
        }
        template_params = {
            **default_template_params,
            "transaction_types": default_template_update(
                "transaction_types",
                {"cash_advance": {"charge_interest_from_transaction_date": "False"}},
            ),
        }

        sub_tests = [
            SubTest(
                description="Auth A",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="1000",
                        client_transaction_id="A",
                        event_datetime=datetime(2019, 1, 5, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 5, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 7, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 7, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 10, tzinfo=ZoneInfo("UTC")),
                        instruction_details={"transaction_code": "aaa"},
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 10, tzinfo=ZoneInfo("UTC")): {
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
                        amount="1500", event_datetime=datetime(2019, 1, 15, tzinfo=ZoneInfo("UTC"))
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 15, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 20, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 20, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 25, tzinfo=ZoneInfo("UTC")),
                        client_transaction_id="B",
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 25, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 6, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "annual_fee": "0",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Initial Auths",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="1000",
                        client_transaction_id="A",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_outbound_authorisation_instruction(
                        amount="2000",
                        client_transaction_id="B",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_outbound_authorisation_instruction(
                        amount="3000",
                        client_transaction_id="C",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 3, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 3, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 4, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 4, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 5, tzinfo=ZoneInfo("UTC")),
                        client_transaction_id="B",
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 5, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 6, tzinfo=ZoneInfo("UTC")),
                        client_transaction_id="C",
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 6, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 3, 3, 0, 0, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.025",
                        "flat_fee": "100",
                    }
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "15000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit": "500",
            "overlimit_opt_in": "True",
        }
        template_params = {
            **default_template_params,
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Cash Advance 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="8000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 3, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Purchase 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 4, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Repay 1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 5, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Cash Advance 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Repay 2",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=datetime(2019, 2, 10, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Repay 3",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=datetime(2019, 2, 22, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Purchase 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 3, 2, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1500",
                        event_datetime=datetime(2019, 3, 2, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Balance Check 8",
                expected_balances_at_ts={
                    datetime(2019, 3, 3, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 3, 3, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 3, 2, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 3, 3, 3, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 3, 3, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 3, 3, 3, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 3, 3, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 3, 4, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.025",
                        "flat_fee": "100",
                    }
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "15000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit": "500",
            "overlimit_opt_in": "False",
        }
        template_params = {
            **default_template_params,
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Cash Advance 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="8000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 3, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Purchase 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 4, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Repay 1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 5, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Cash Advance 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Repay 2",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=datetime(2019, 2, 10, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Repay 3",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=datetime(2019, 2, 22, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Purchase 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 3, 2, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1500",
                        event_datetime=datetime(2019, 3, 2, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Balance Check 8",
                expected_balances_at_ts={
                    datetime(2019, 3, 3, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 3, 3, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 3, 2, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 3, 3, 3, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 3, 3, tzinfo=ZoneInfo("UTC")): {
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
                        amount="500", event_datetime=datetime(2019, 3, 3, 4, tzinfo=ZoneInfo("UTC"))
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 3, 4, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 1, 10, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Available balance is initialised",
                expected_balances_at_ts={
                    datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        timestamp=datetime(2019, 1, 1, 5, tzinfo=ZoneInfo("UTC")),
                        credit_limit="35000",
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 5, tzinfo=ZoneInfo("UTC")): {
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
                        timestamp=datetime(2019, 1, 1, 10, tzinfo=ZoneInfo("UTC")),
                        credit_limit="25000",
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 10, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 1, 4, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "overlimit": "3000",
            "overlimit_opt_in": "True",
            "annual_fee": "0",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Purchase under credit limit is accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="11000",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 4, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 4, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 1, 4, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "overlimit": "3000",
            "overlimit_opt_in": "True",
            "annual_fee": "0",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Purchase under credit limit is accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="11000",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 4, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 4, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 1, 3, 0, 0, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "overlimit": "3000",
            "overlimit_opt_in": "False",
            "annual_fee": "0",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Initial Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="1000",
                        client_transaction_id="1",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 1, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 3, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                        client_transaction_id="1",
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 3, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "overlimit": "3000",
            "overlimit_opt_in": "True",
            "annual_fee": "0",
            "transaction_type_fees": "{}",
            "transaction_type_limits": dumps({"cash_advance": {"flat": "5000"}}),
            "late_repayment_fee": "0",
        }
        template_params = {
            **default_template_params,
            "transaction_types": default_template_update(
                "transaction_types",
                {"cash_advance": {"charge_interest_from_transaction_date": "False"}},
            ),
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Auth below limit",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="5000",
                        event_datetime=datetime(2019, 1, 30, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Purchase below limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=datetime(2019, 1, 30, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Cash Advance below limit (individually and cumulatively)",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 31, 3, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Auth above limit",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="17000",
                        client_transaction_id="A",
                        event_datetime=datetime(2019, 1, 31, 4, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="No fee at SCOD",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 2, 2, 1, tzinfo=ZoneInfo("UTC")),
                        client_transaction_id="A",
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 2, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="No fee at SCOD 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "10000",
            "overlimit": "3000",
            "overlimit_opt_in": "True",
            "overlimit_fee": "180",
            "annual_fee": "0",
            "transaction_type_fees": "{}",
            "transaction_type_limits": dumps({"cash_advance": {"flat": "5000"}}),
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Auth below limit",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="9500",
                        client_transaction_id="A",
                        event_datetime=datetime(2019, 1, 30, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 30, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 31, 1, tzinfo=ZoneInfo("UTC")),
                        client_transaction_id="A",
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 31, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Overlimit fee charged at SCOD",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "10000",
            "overlimit": "3000",
            "overlimit_opt_in": "True",
            "overlimit_fee": "180",
            "annual_fee": "0",
            "transaction_type_fees": "{}",
            "transaction_type_limits": dumps({"cash_advance": {"flat": "5000"}}),
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Txn above limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="11000",
                        event_datetime=datetime(2019, 1, 31, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 31, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Overlimit fee charged at SCOD",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "overlimit": "3000",
            "overlimit_opt_in": "True",
            "overlimit_fee": "180",
            "annual_fee": "0",
            "late_repayment_fee": "0",
            "transaction_type_fees": "{}",
            "transaction_type_limits": dumps({"cash_advance": {"flat": "5000"}}),
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Auth below limit",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="29800",
                        client_transaction_id="A",
                        event_datetime=datetime(2019, 1, 30, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 30, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 30, 2, tzinfo=ZoneInfo("UTC")),
                        client_transaction_id="A",
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 30, 2, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 31, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 31, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 31, 2, tzinfo=ZoneInfo("UTC")),
                        client_transaction_id="B",
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 31, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-300")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Overlimit fee charged at SCOD",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "10000",
            "overlimit": "3000",
            "overlimit_opt_in": "True",
            "overlimit_fee": "180",
            "annual_fee": "0",
            "late_repayment_fee": "0",
            "transaction_type_limits": dumps({"cash_advance": {"flat": "10000"}}),
            "transaction_type_fees": dumps(
                {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
            ),
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 30, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 30, 1, tzinfo=ZoneInfo("UTC")): {
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
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "10000",
            "overlimit": "3000",
            "overlimit_opt_in": "True",
            "overlimit_fee": "180",
            "annual_fee": "0",
            "late_repayment_fee": "0",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Auth under limit",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="9000",
                        client_transaction_id="A",
                        event_datetime=datetime(2019, 1, 31, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 31, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Overlimit fee not charged at SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 2, 3, 1, tzinfo=ZoneInfo("UTC")),
                        client_transaction_id="A",
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 3, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Overlimit fee charged at SCOD 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "10000",
            "overlimit": "3000",
            "overlimit_opt_in": "True",
            "overlimit_fee": "180",
            "annual_fee": "0",
            "late_repayment_fee": "0",
        }
        template_params = {
            **default_template_params,
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Purchase over limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="11000",
                        event_datetime=datetime(2019, 1, 30, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 30, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 30, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 30, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("1")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Overlimit fee not charged at SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        amount="1000",
                        event_datetime=datetime(2019, 2, 2, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 2, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("-999")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Overlimit fee charged at SCOD 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 2, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 1, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "22",
            "transaction_type_fees": dumps(
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
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "6000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
        }
        template_params = {
            **default_template_params,
            "minimum_percentage_due": dumps(
                {
                    "purchase": "0.01",
                    "cash_advance": "0.01",
                    "balance_transfer": "0",
                    "transfer": "0",
                    "interest": "1.0",
                    "fees": "1.0",
                }
            ),
            "minimum_amount_due": "200",
        }

        sub_tests = [
            SubTest(
                description="Overpay",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=datetime(2019, 1, 3, 0, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Transfer out",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="4000",
                        instruction_details={"transaction_code": "cc"},
                        event_datetime=datetime(2019, 1, 5, 0, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Check statement accurate",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 0, 1, 0, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 1, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "22",
            "transaction_type_fees": dumps(
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
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "6000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
        }
        template_params = {
            **default_template_params,
            "minimum_percentage_due": dumps(
                {
                    "purchase": "0.01",
                    "cash_advance": "0.01",
                    "balance_transfer": "0",
                    "transfer": "0",
                    "interest": "1.0",
                    "fees": "1.0",
                }
            ),
            "minimum_amount_due": "200",
        }

        sub_tests = [
            SubTest(
                description="Overpay",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=datetime(2019, 1, 3, 0, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Transfer out",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        instruction_details={"transaction_code": "cc"},
                        event_datetime=datetime(2019, 1, 5, 0, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Check statement accurate",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 0, 1, 0, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 1, 0, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "22",
            "transaction_type_fees": dumps(
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
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "6000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
        }
        template_params = {
            **default_template_params,
            "minimum_percentage_due": dumps(
                {
                    "purchase": "0.01",
                    "cash_advance": "0.01",
                    "balance_transfer": "0.01",
                    "transfer": "0.01",
                    "interest": "1.0",
                    "fees": "1.0",
                }
            ),
            "minimum_amount_due": "200",
        }

        sub_tests = [
            SubTest(
                description="Overpay",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=datetime(2019, 1, 3, 0, 1, tzinfo=ZoneInfo("UTC")),
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
                        event_datetime=datetime(2019, 1, 5, 0, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Check statement accurate",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 1, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "22",
            "transaction_type_fees": dumps(
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
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "6000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
        }
        template_params = {
            **default_template_params,
            "minimum_percentage_due": dumps(
                {
                    "purchase": "0.01",
                    "cash_advance": "0.01",
                    "balance_transfer": "0.01",
                    "transfer": "0.01",
                    "interest": "1.0",
                    "fees": "1.0",
                }
            ),
            "minimum_amount_due": "200",
        }

        sub_tests = [
            SubTest(
                description="Overpay",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=datetime(2019, 1, 3, 0, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Transfer out",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="4000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 5, 0, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Check statement accurate",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 0, 1, 0, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 3, 0, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "22",
            "transaction_type_fees": dumps(
                {
                    "transfer": {
                        "over_deposit_only": "True",
                        "percentage_fee": "0.01",
                        "flat_fee": "100",
                    },
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "6000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Overpay",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=datetime(2019, 1, 2, 0, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Transfer out",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="4000",
                        event_datetime=datetime(2019, 1, 3, 0, 1, tzinfo=ZoneInfo("UTC")),
                        instruction_details={"transaction_code": "cc"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=datetime(2019, 1, 3, 0, 1, tzinfo=ZoneInfo("UTC")),
                        instruction_details={"transaction_code": "cc"},
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 3, 0, 1, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 12, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2020, 1, 6, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.025",
                        "flat_fee": "100",
                    },
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "15000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Cash Advance 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="8000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 12, 3, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Balance Check in normal year",
                expected_balances_at_ts={
                    datetime(2019, 12, 6, 1, tzinfo=ZoneInfo("UTC")): {
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
                    datetime(2020, 1, 6, 1, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 1, 5, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "100",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "percentage_fee": "0.025",
                        "flat_fee": "100",
                    },
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "200"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit_opt_in": "False",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Cash Advance with no advice flag is rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="200",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1",
                        event_datetime=datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")),
                        instruction_details={"transaction_code": "xxxx"},
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 4, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 4, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 5, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 5, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "10000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "percentage_fee": "0.02",
                        "flat_fee": "100",
                    },
                }
            ),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit": "1000",
            "overlimit_opt_in": "True",
            "overlimit_fee": "180",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Purchase Auth A",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="11000",
                        client_transaction_id="12345",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                        client_transaction_id="12345",
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
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
                        amount="500", event_datetime=datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC"))
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "10000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "percentage_fee": "0.025",
                        "flat_fee": "100",
                    },
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "100"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit": "3000",
            "overlimit_opt_in": "False",
            "overlimit_fee": "180",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Purchase with skip balance check true",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="11000",
                        instruction_details={"transaction_code": "cc"},
                        event_datetime=datetime(2019, 1, 30, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 30, 1, tzinfo=ZoneInfo("UTC")): {
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
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "10000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "percentage_fee": "0.025",
                        "flat_fee": "100",
                    },
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "100"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit": "3000",
            "overlimit_opt_in": "True",
            "overlimit_fee": "180",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Purchase with skip balance check true",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2019, 1, 20, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 20, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 30, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 30, 1, tzinfo=ZoneInfo("UTC")): {
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
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "10000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "percentage_fee": "0.025",
                        "flat_fee": "100",
                    },
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "100"}}),
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
                description="Purchase with skip balance check true",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="9800",
                        event_datetime=datetime(2019, 1, 20, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 20, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 3, 10, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 10, 1, tzinfo=ZoneInfo("UTC")): {
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
                    datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "10000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "percentage_fee": "0.025",
                        "flat_fee": "100",
                    },
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "100"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit": "3000",
            "overlimit_opt_in": "True",
            "overlimit_fee": "180",
        }
        template_params = {
            **default_template_params,
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Purchase with skip balance check true",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="9800",
                        event_datetime=datetime(2019, 1, 20, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 20, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 3, 10, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 10, 1, tzinfo=ZoneInfo("UTC")): {
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
                    datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 1, 5, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "10000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "percentage_fee": "0.02",
                        "flat_fee": "100",
                    },
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "100"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit": "1000",
            "overlimit_opt_in": "True",
            "overlimit_fee": "180",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Purchase A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 4, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 4, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 5, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 5, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "10000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "percentage_fee": "0.02",
                        "flat_fee": "100",
                    },
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "15000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit": "1000",
            "overlimit_opt_in": "True",
            "overlimit_fee": "180",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Cash Advance A goes Overlimit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10800",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 30, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 30, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 2, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "10000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "percentage_fee": "0.02",
                        "flat_fee": "100",
                    },
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "15000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit": "1000",
            "overlimit_opt_in": "True",
            "overlimit_fee": "180",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Purchase A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="9900",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 2, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, 1, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 10, 3, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "10000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "percentage_fee": "0.02",
                        "flat_fee": "100",
                    },
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "15000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit": "1000",
            "overlimit_opt_in": "True",
            "overlimit_fee": "180",
        }
        template_params = {
            **default_template_params,
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Purchase A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="9900",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 3, 10, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 10, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 3, 10, 2, tzinfo=ZoneInfo("UTC")),
                        client_transaction_id="B",
                    )
                ],
            ),
            SubTest(
                description="Purchase Auth C rejected as account already overlimit",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="200",
                        event_datetime=datetime(2019, 3, 10, 3, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 10, 3, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "10000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "percentage_fee": "0.02",
                        "flat_fee": "100",
                    },
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "15000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit": "1000",
            "overlimit_opt_in": "True",
            "overlimit_fee": "180",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Purchase A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="9900",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 5, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "10000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "percentage_fee": "0.02",
                        "flat_fee": "100",
                    },
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "15000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit": "1000",
            "overlimit_opt_in": "True",
            "overlimit_fee": "180",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Purchase A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 2, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, 1, tzinfo=ZoneInfo("UTC")): {
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
                    datetime(2019, 1, 3, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 3, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 3, 2, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 4, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 4, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 5, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 5, 1, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 5, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "10000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "percentage_fee": "0.02",
                        "flat_fee": "100",
                    },
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "15000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit": "1000",
            "overlimit_opt_in": "True",
            "overlimit_fee": "180",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Purchase A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 2, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, 1, tzinfo=ZoneInfo("UTC")): {
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
                        amount="600", event_datetime=datetime(2019, 1, 3, 1, tzinfo=ZoneInfo("UTC"))
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 3, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 4, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 4, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 5, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 5, 1, tzinfo=ZoneInfo("UTC")): {
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
                        amount="1", event_datetime=datetime(2019, 1, 5, 2, tzinfo=ZoneInfo("UTC"))
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 5, 2, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 5, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "percentage_fee": "0.02",
                        "flat_fee": "100",
                    },
                }
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
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2019, 1, 2, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 3, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 3, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 4, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 4, 1, tzinfo=ZoneInfo("UTC")): {
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
                    datetime(2019, 1, 5, 1, tzinfo=ZoneInfo("UTC")): {
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

    def test_external_fee_charged_billed_and_repaid_correctly(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 26, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "late_repayment_fee": "0",
            "annual_fee": "0",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="External Fee Charged",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        instruction_details={"fee_type": "ATM_WITHDRAWAL_FEE"},
                        event_datetime=datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")): {
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
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                    datetime(2019, 2, 25, 1, tzinfo=ZoneInfo("UTC")): {
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

    @skip("need to investigate why this is failing")
    def test_fee_postings_tagged_correctly(self):
        annual_fee = "100.00"
        overlimit_fee = "125.00"
        cash_advance_flat_fee = "200.00"

        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 26, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "2000",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "percentage_fee": "0.02",
                        "flat_fee": cash_advance_flat_fee,
                    }
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "8000"}}),
            "annual_fee": annual_fee,
            "overlimit_fee": overlimit_fee,
            "late_repayment_fee": "150.00",
        }
        template_params = {
            **default_template_params,
        }

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
                        event_datetime=datetime(2019, 1, 31, tzinfo=ZoneInfo("UTC")),
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
                hook_effective_datetime=datetime(2019, 1, 1, 23, 50, tzinfo=ZoneInfo("UTC")),
                value_timestamp=datetime(2019, 1, 1, 23, 50, tzinfo=ZoneInfo("UTC")),
            ),
            rebalance_fee_batch(
                amount=cash_advance_flat_fee,
                batch_id_prefix="POST_POSTING",
                fee_type="CASH_ADVANCE_FEE",
                hook_id="13",
                posting_id=".*",
                hook_effective_datetime=datetime(2019, 1, 31, tzinfo=ZoneInfo("UTC")),
                value_timestamp=datetime(2019, 1, 31, tzinfo=ZoneInfo("UTC")),
            ),
            rebalance_fee_batch(
                amount=overlimit_fee,
                batch_id_prefix="SCOD_0",
                fee_type="OVERLIMIT_FEE",
                event_name="STATEMENT_CUT_OFF",
                hook_id="5",
                hook_effective_datetime=datetime(2019, 2, 1, 0, 0, 2, tzinfo=ZoneInfo("UTC")),
                value_timestamp=datetime(2019, 1, 31, 23, 59, 59, 999999, tzinfo=ZoneInfo("UTC")),
            ),
        ]
        for postings in expected_posting_batches:
            self.assertTrue(check_postings_correct_after_simulation(res, postings))

    def test_available_balance_checks(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "8000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {"cash_advance": {"percentage_fee": "0.025", "flat_fee": "500"}}
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "15000"}}),
            "late_repayment_fee": "100",
            "annual_fee": "100",
            "overlimit": "500",
            "overlimit_opt_in": "False",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Cash Advance 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="4000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 2, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 2, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, 2, tzinfo=ZoneInfo("UTC")): {
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
                        amount="3399",
                        event_datetime=datetime(2019, 1, 3, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 3, 1, tzinfo=ZoneInfo("UTC")): {
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
                        amount="1", event_datetime=datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC"))
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "20000",
            "transaction_type_limits": dumps(
                {"cash_advance": {"flat": "200", "percentage": "0.1"}}
            ),
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Single Cash Advance below flat limit accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 4, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 4, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "20000",
            "transaction_type_limits": dumps(
                {"cash_advance": {"flat": "10000", "percentage": "0.001"}}
            ),
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Single Cash Advance below % limit accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 4, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 4, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "20000",
            "transaction_type_limits": dumps(
                {
                    "cash_advance": {"flat": "10000"},
                    "purchase": {"percentage": "0.1"},
                    "transfer": {},
                }
            ),
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Single Cash Advance below flat limit accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        amount="1500",
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "20000",
            "transaction_type_limits": dumps({}),
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Single Cash Advance accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        amount="1500",
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "transaction_references": dumps({"balance_transfer": ["ref1", "REF2"]}),
            "transaction_annual_percentage_rate": dumps(
                {"balance_transfer": {"ref1": "0.25", "REF2": "0.3"}}
            ),
            "transaction_type_fees": dumps(
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
            ),
            "annual_fee": "0",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Initial Balance Check",
                expected_balances_at_ts={
                    datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "ref1",
                        },
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "20000",
            "transaction_type_limits": dumps({"balance_transfer": {"flat": "100"}}),
            "transaction_references": dumps({"balance_transfer": ["ref1", "REF2"]}),
            "transaction_annual_percentage_rate": dumps(
                {"balance_transfer": {"ref1": "0.25", "REF2": "0.3"}}
            ),
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="BT REF1 accepted",
                events=[
                    create_transfer_instruction(
                        amount="10",
                        creditor_target_account_id="1",
                        debtor_target_account_id="Main account",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 15, 0, 0, 0, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "annual_fee": "0",
            "credit_limit": "2000",
            "transaction_type_limits": dumps(
                {"balance_transfer": {"flat": "100", "allowed_days_after_opening": "14"}}
            ),
            "transaction_references": dumps({"balance_transfer": ["REF1", "REF2"]}),
            "transaction_base_interest_rates": dumps({"balance_transfer": {"REF1": "0.36"}}),
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="BT REF1 accepted",
                events=[
                    create_transfer_instruction(
                        amount="10",
                        creditor_target_account_id="1",
                        debtor_target_account_id="Main account",
                        event_datetime=datetime(2019, 1, 14, 23, 59, 59, tzinfo=ZoneInfo("UTC")),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 14, 23, 59, 59, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 15, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 15, 0, 0, 0, tzinfo=ZoneInfo("UTC")): {
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
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 1, 7, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "20000",
            "transaction_type_limits": dumps({"balance_transfer": {"flat": "100"}}),
            "transaction_references": dumps({"balance_transfer": ["REF1", "REF2"]}),
            "transaction_annual_percentage_rate": dumps({"balance_transfer": {"REF1": "0.25"}}),
            "annual_fee": "0",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="BT without ref rejected",
                events=[
                    create_transfer_instruction(
                        amount="1",
                        creditor_target_account_id="1",
                        debtor_target_account_id="Main account",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": None,
                        },
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF9",
                        },
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 4, tzinfo=ZoneInfo("UTC")),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 4, tzinfo=ZoneInfo("UTC")): {
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
                        amount="5", event_datetime=datetime(2019, 1, 1, 5, tzinfo=ZoneInfo("UTC"))
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 5, tzinfo=ZoneInfo("UTC")): {
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
                        amount="6", event_datetime=datetime(2019, 1, 1, 6, tzinfo=ZoneInfo("UTC"))
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 6, tzinfo=ZoneInfo("UTC")): {
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
                        event_datetime=datetime(2019, 1, 1, 7, tzinfo=ZoneInfo("UTC")),
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 7, tzinfo=ZoneInfo("UTC")): {
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
    if batch_id_prefix == "POST_POSTING":
        batch_id = ""

    if txn_type:
        fee_type = f"{txn_type.upper()}_FEE"

    address = f"{fee_type}S_CHARGED"

    # TODO: when we refactor other methods we'll be able to pass in the posting id to the 'trigger'
    client_transaction_id = f"REBALANCE_{address}-{hook_execution_id}-FEES_CHARGED_{fee_type}"

    if posting_id:
        client_transaction_id += f"{posting_id}"

    return dict(
        client_batch_id=batch_id,
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
        value_timestamp=value_timestamp,
    )
