# Copyright @ 2021-2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
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
    ContractNotificationResourceType,
    ExpectedContractNotification,
    SimulationTestScenario,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_flag_definition_event,
    create_flag_event,
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_outbound_hard_settlement_instruction,
    create_transfer_instruction,
)
from inception_sdk.test_framework.contracts.simulation.utils import SimulationTestCase

CONTRACT_FILE = "library/credit_card/contracts/template/credit_card.py"
EXPIRE_INTEREST_FREE_PERIODS_NOTIFICATION = "EXPIRE_INTEREST_FREE_PERIODS_NOTIFICATION"
ASSET_CONTRACT_FILE = "internal_accounts/testing_internal_asset_account_contract.py"
LIABILITY_CONTRACT_FILE = "internal_accounts/testing_internal_liability_account_contract.py"
CONTRACT_FILES = [CONTRACT_FILE]

default_instance_params = DEFAULT_CREDIT_CARD_INSTANCE_PARAMS
default_template_params = DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS


class CreditCardInterestTest(SimulationTestCase):
    """
    Test interest accrual and charging
    """

    contract_filepaths = [CONTRACT_FILE, ASSET_CONTRACT_FILE, LIABILITY_CONTRACT_FILE]

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

    def test_accrual_only_considers_balances_at_cutoff(self):
        """
        Transactions after <yyyy-MM-DD>T23:59:59.999999 are only accrued on DD+2
        """
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 3, 0, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.02",
                        "flat_fee": "100",
                    }
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "10000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
        }

        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Cash advance on and after cut-off",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(
                            2019, 1, 1, 23, 59, 59, 999999, tzinfo=ZoneInfo("UTC")
                        ),
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="2000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Check first accrual excludes transaction after cut-off",
                expected_balances_at_ts={
                    datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("26800.00"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("3200.00"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("3200.99"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                # round(0.36 * 1000 / 365, 2)
                                Decimal("0.99"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check second accrual includes both transactions",
                expected_balances_at_ts={
                    datetime(2019, 1, 3, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("26800.00"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("3200.00"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("3203.95"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                # 0.99 + round(0.36 * 3000 / 365, 2)
                                Decimal("3.95"),
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

    def test_transaction_without_interest_free_period_charges_immediately(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 2, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.02",
                        "flat_fee": "100",
                    }
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "10000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Initial Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="6000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 5, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="EOD after Cash Advance",
                expected_balances_at_ts={
                    datetime(2019, 1, 6, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("23880")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("6120")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("6125.92"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("6000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("120"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("5.92"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="5 days later",
                expected_balances_at_ts={
                    datetime(2019, 1, 11, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("23880")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("6120")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("6155.52"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("6000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("120"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("35.52"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="SCOD",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("23720.16"),
                            ),
                            (
                                BalanceDimensions("STATEMENT_BALANCE"),
                                Decimal("6279.84"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("6279.84"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("6279.84"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("6000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("120"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("159.84"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Day after SCOD",
                expected_balances_at_ts={
                    datetime(2019, 2, 2, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("23720.16"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("6279.84"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("6285.76"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("6000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("120"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("5.92"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("159.84"),
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

    def test_transaction_without_interest_free_period_charges_less_after_repayments(
        self,
    ):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 23, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.02",
                        "flat_fee": "100",
                    }
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "10000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
        }
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Initial Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="6000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 5, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="EOD after Cash Advance",
                expected_balances_at_ts={
                    datetime(2019, 1, 6, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("23880")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("6120")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("6125.92"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("6000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("120"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("5.92"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial Repayment 1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Day after repayment",
                expected_balances_at_ts={
                    datetime(2019, 1, 11, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("26880")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("3120")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("3152.56"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("120"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("32.56"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="SCOD",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("26785.28"),
                            ),
                            (
                                BalanceDimensions("STATEMENT_BALANCE"),
                                Decimal("3214.72"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("3214.72"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("3214.72"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("3000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("120"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("94.72"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial Repayment 2",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 2, 22, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Post-PDD",
                expected_balances_at_ts={
                    datetime(2019, 2, 23, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("27785.28"),
                            ),
                            (
                                BalanceDimensions("STATEMENT_BALANCE"),
                                Decimal("3214.72"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("2214.72"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("64.34"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("2279.06"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("2214.72"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
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

    def test_cash_advance_interest_is_tracked_at_per_transaction_type(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 26, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.02",
                        "flat_fee": "100",
                    }
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
                        event_datetime=datetime(2019, 1, 3, 1, tzinfo=ZoneInfo("UTC")),
                        instruction_details={"transaction_code": "aaa"},
                    )
                ],
            ),
            SubTest(
                description="EOD after Cash Advance 1",
                expected_balances_at_ts={
                    datetime(2019, 1, 4, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("21840")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("8167.89"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("8160")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("8000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("160"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("7.89"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial Repayment 1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 5, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="EOD after Partial Repayment 1",
                expected_balances_at_ts={
                    datetime(2019, 1, 6, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("22840")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("7182.68"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("7160")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("7000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("160"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("22.68"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("22637.92"),
                            ),
                            (
                                BalanceDimensions("STATEMENT_BALANCE"),
                                Decimal("7362.08"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("432.08")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("7362.08"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("7362.08"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("7000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("202.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("160"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=datetime(2019, 2, 1, 3, tzinfo=ZoneInfo("UTC")),
                        instruction_details={"transaction_code": "aaa"},
                    )
                ],
            ),
            SubTest(
                description="Partial Repayment 2",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=datetime(2019, 2, 10, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="EOD after Partial Repayment 2",
                expected_balances_at_ts={
                    datetime(2019, 2, 11, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("21037.92"),
                            ),
                            (
                                BalanceDimensions("STATEMENT_BALANCE"),
                                Decimal("7362.08"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("432.08")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("9050.74"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("8962.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_BILLED"),
                                Decimal("6862.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("2000.00"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("88.66"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial Repayment 3",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=datetime(2019, 2, 22, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Few days after PDD and partial repayment",
                expected_balances_at_ts={
                    datetime(2019, 2, 26, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("26037.92"),
                            ),
                            (
                                BalanceDimensions("STATEMENT_BALANCE"),
                                Decimal("7362.08"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("432.08")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4162.12"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("3962.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("1862.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("2000.00"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("200.04"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
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

    def test_purchase_interest_accrued_from_scod_is_tracked_at_per_transaction_type(
        self,
    ):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 4, 8, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.02",
                        "flat_fee": "100",
                    }
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "15000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
        }

        template_params = {
            **default_template_params,
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Purchase 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Purchase 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="399",
                        event_datetime=datetime(2019, 1, 3, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Purchase 3",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Purchase 4",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="900",
                        event_datetime=datetime(2019, 1, 31, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("27601")),
                            (BalanceDimensions("STATEMENT_BALANCE"), Decimal("2399")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("200")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("2399"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("2399")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("2399")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase 5",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=datetime(2019, 2, 2, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Repay 1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=datetime(2019, 2, 22, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Purchase 6",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=datetime(2019, 2, 27, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Purchase 7",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 2, 28, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="SCOD 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("24546.88"),
                            ),
                            (
                                BalanceDimensions("STATEMENT_BALANCE"),
                                Decimal("5453.12"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("200")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("5453.12"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("5453.12"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1899")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("3500")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("54.12"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase 8",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="900",
                        event_datetime=datetime(2019, 3, 2, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Purchase 9",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 3, 15, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Repay 2",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="200",
                        event_datetime=datetime(2019, 3, 22, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Purchase 10",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=datetime(2019, 3, 30, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Purchase 11",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=datetime(2019, 3, 31, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="SCOD 3",
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("19204.63"),
                            ),
                            (
                                BalanceDimensions("STATEMENT_BALANCE"),
                                Decimal("10795.37"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("248.78")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("10795.37"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("10795.37"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("5253.12")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("5400")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("142.25"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase 12",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="300",
                        event_datetime=datetime(2019, 4, 2, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="6 accruals later",
                expected_balances_at_ts={
                    datetime(2019, 4, 8, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("18904.63"),
                            ),
                            (
                                BalanceDimensions("STATEMENT_BALANCE"),
                                Decimal("10795.37"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("248.78")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("11145.57"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("11095.37"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("5253.12")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("5400")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("300")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("142.25"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("50.20"),
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

    def test_purchase_interest_accrued_from_txn_day_is_tracked_at_per_transaction_type(
        self,
    ):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 4, 8, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.02",
                        "flat_fee": "100",
                    }
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
                description="Purchase 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Purchase 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="399", event_datetime=datetime(2019, 1, 3, 1, tzinfo=ZoneInfo("UTC"))
                    )
                ],
            ),
            SubTest(
                description="Purchase 3",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Purchase 4",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="900",
                        event_datetime=datetime(2019, 1, 31, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("27601")),
                            (BalanceDimensions("STATEMENT_BALANCE"), Decimal("2399")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("200")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("2399"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("2399")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("2399")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase 5",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500", event_datetime=datetime(2019, 2, 2, 1, tzinfo=ZoneInfo("UTC"))
                    )
                ],
            ),
            SubTest(
                description="Repay 1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=datetime(2019, 2, 22, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Purchase 6",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=datetime(2019, 2, 27, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Purchase 7",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 2, 28, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="SCOD 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("24517.10"),
                            ),
                            (
                                BalanceDimensions("STATEMENT_BALANCE"),
                                Decimal("5482.90"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("200")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("5482.90"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("5482.90"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1899")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("3500")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("83.90"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase 8",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="900", event_datetime=datetime(2019, 3, 2, 1, tzinfo=ZoneInfo("UTC"))
                    )
                ],
            ),
            SubTest(
                description="Purchase 9",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 3, 15, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Repay 2",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="200",
                        event_datetime=datetime(2019, 3, 22, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Purchase 10",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=datetime(2019, 3, 30, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Purchase 11",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=datetime(2019, 3, 31, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="SCOD 3",
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("19174.65"),
                            ),
                            (
                                BalanceDimensions("STATEMENT_BALANCE"),
                                Decimal("10825.35"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("249.28")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("10825.35"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("10825.35"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("5282.90")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("5400")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("142.45"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase 12",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="300", event_datetime=datetime(2019, 4, 2, 1, tzinfo=ZoneInfo("UTC"))
                    )
                ],
            ),
            SubTest(
                description="6 accruals later",
                expected_balances_at_ts={
                    datetime(2019, 4, 8, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("18874.65"),
                            ),
                            (
                                BalanceDimensions("STATEMENT_BALANCE"),
                                Decimal("10825.35"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("249.28")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("11175.69"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("11125.35"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("5282.90")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("5400")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("300")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("142.45"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("50.34"),
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

    def test_purchase_and_cash_advance_interest_acc_from_scod_is_tracked_at_per_txn_type(
        self,
    ):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 4, 1, 2, tzinfo=ZoneInfo("UTC"))

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
                description="Balance Check 1",
                expected_balances_at_ts={
                    datetime(2019, 1, 6, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("21800")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("7000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("22.68"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
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
                description="Balance Check 2",
                expected_balances_at_ts={
                    datetime(2019, 2, 2, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("19497.92"),
                            ),
                            (
                                BalanceDimensions("STATEMENT_BALANCE"),
                                Decimal("8402.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("2000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("7000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("8.88"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("202.08"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0.66"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("200"),
                            ),
                        ]
                    }
                },
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
                description="Balance Check 3",
                expected_balances_at_ts={
                    datetime(2019, 2, 11, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("2000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_BILLED"),
                                Decimal("6902.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("88.7"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("6.6"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
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
                description="Repay 3",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=datetime(2019, 2, 22, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Balance Check 4",
                expected_balances_at_ts={
                    datetime(2019, 2, 23, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("2000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("1902.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("189.13"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("14.52"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
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
                description="Balance Check 5",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("2000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("1902.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("212.23"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1000")),
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
                                Decimal("18.48"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
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
                description="Balance Check 6",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("2000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("1902.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("212.23"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1000")),
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
                                Decimal("18.48"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
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
                description="Balance Check 7",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("2000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("1902.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("212.23"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1000")),
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
                                Decimal("18.48"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
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
                description="Purchase 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1500",
                        event_datetime=datetime(2019, 3, 2, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Balance Check 8",
                expected_balances_at_ts={
                    datetime(2019, 3, 3, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("2000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("1902.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("7.7"),
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
                                Decimal("0"),
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
                description="Balance Check 9",
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("23098")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("3902.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("119.35"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("212.23"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1500")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1000")),
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
                                Decimal("49.86"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("18.48"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
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

    def test_purchase_and_cash_advance_int_acc_from_txn_is_tracked_at_per_transaction_type(
        self,
    ):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 4, 1, 2, tzinfo=ZoneInfo("UTC"))

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
                description="Balance Check 1",
                expected_balances_at_ts={
                    datetime(2019, 1, 6, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("21800")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("7000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("22.68"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("1.32"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
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
                description="Balance Check 2",
                expected_balances_at_ts={
                    datetime(2019, 2, 2, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("19497.92"),
                            ),
                            (
                                BalanceDimensions("STATEMENT_BALANCE"),
                                Decimal("8402.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("2000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("7000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("8.88"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("202.08"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("19.14"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("200"),
                            ),
                        ]
                    }
                },
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
                description="Balance Check 3",
                expected_balances_at_ts={
                    datetime(2019, 2, 11, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("2000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_BILLED"),
                                Decimal("6902.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("88.7"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("25.08"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
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
                description="Repay 3",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=datetime(2019, 2, 22, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Balance Check 4",
                expected_balances_at_ts={
                    datetime(2019, 2, 23, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("2000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("1902.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("189.13"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1000")),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("33.00"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
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
                description="Balance Check 5",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("2000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("1902.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("212.23"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1000")),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("36.96"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
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
                description="Purchase 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1500",
                        event_datetime=datetime(2019, 3, 2, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Balance Check 6",
                expected_balances_at_ts={
                    datetime(2019, 3, 3, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("2000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("1902.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("7.7"),
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
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("2.30"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("36.96"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
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
                description="Balance Check 7",
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("23079.52"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("3902.08"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("119.35"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("212.23"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1500")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1000")),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("49.86"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("36.96"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
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

    def test_customer_with_blocking_flag_does_not_accrue(self):
        """
        When flag set to a valid string, interest accrual should be blocked.
        """

        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 7, 0, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.02",
                        "flat_fee": "100",
                    }
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "10000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
        }

        template_params = {
            **default_template_params,
            "accrual_blocking_flags": '["90_DPD","CUSTOMER_FLAGGED"]',
        }

        sub_tests = [
            SubTest(
                description="Initial Cash Advance",
                events=[
                    create_flag_definition_event(
                        flag_definition_id="90_DPD",
                        timestamp=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_flag_event(
                        flag_definition_id="90_DPD",
                        account_id="Main account",
                        timestamp=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                        expiry_timestamp=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="6000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 5, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Check no accrual occurred",
                expected_balances_at_ts={
                    datetime(2019, 1, 7, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("23880.00"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("6120.00"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("6120.00"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("6000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("120"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
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

    def test_customer_with_unrelated_flag_continues_to_accrue(self):
        """
        When flag set to an undefined string, interest accrual should continue.
        """
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 7, 0, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.02",
                        "flat_fee": "100",
                    }
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "10000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
        }

        template_params = {
            **default_template_params,
            "accrual_blocking_flags": '["90_DPD","CUSTOMER_FLAGGED"]',
        }

        sub_tests = [
            SubTest(
                description="Initial Cash Advance",
                events=[
                    create_flag_definition_event(
                        flag_definition_id="THIS_FLAG_DOES_NOTHING",
                        timestamp=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_flag_event(
                        flag_definition_id="THIS_FLAG_DOES_NOTHING",
                        account_id="Main account",
                        timestamp=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                        expiry_timestamp=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="6000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 5, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Check accrual occurred",
                expected_balances_at_ts={
                    datetime(2019, 1, 7, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("23880.00"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("6120.00"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("6131.84"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("6000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("120"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("11.84"),
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

    def test_customer_with_multiple_flags_block_accrual_if_one_is_valid_blocking_flag(
        self,
    ):
        """
        When flag set to a valid string, interest accrual should be blocked,
        even if other unrelated flags are set.
        """
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 7, 0, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.02",
                        "flat_fee": "100",
                    }
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "10000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
        }

        template_params = {
            **default_template_params,
            "accrual_blocking_flags": '["90_DPD","CUSTOMER_FLAGGED"]',
        }

        sub_tests = [
            SubTest(
                description="Initial Cash Advance",
                events=[
                    create_flag_definition_event(
                        flag_definition_id="THIS_FLAG_DOES_NOTHING",
                        timestamp=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_flag_event(
                        flag_definition_id="THIS_FLAG_DOES_NOTHING",
                        account_id="Main account",
                        timestamp=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                        expiry_timestamp=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_flag_definition_event(
                        flag_definition_id="90_DPD",
                        timestamp=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_flag_event(
                        flag_definition_id="90_DPD",
                        account_id="Main account",
                        timestamp=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                        expiry_timestamp=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_flag_definition_event(
                        flag_definition_id="THIS_FLAG_ALSO_DOES_NOTHING",
                        timestamp=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_flag_event(
                        flag_definition_id="THIS_FLAG_ALSO_DOES_NOTHING",
                        account_id="Main account",
                        timestamp=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                        expiry_timestamp=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="6000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 5, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Check no accrual occurred",
                expected_balances_at_ts={
                    datetime(2019, 1, 7, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("23880.00"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("6120.00"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("6120.00"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("6000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("120"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
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

    def test_cash_withdrawal_eq_positive_balance_purchase_repay_ca_no_interest(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 5, 2, tzinfo=ZoneInfo("UTC"))

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
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Withdrawal",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 4, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 4, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("100")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("29900")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
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
                            (BalanceDimensions("DEFAULT"), Decimal("100")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("29900")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
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
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
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

    def test_cash_withdrawal_eq_positive_balance_purchase_overrepay_ca_interest_accrued(
        self,
    ):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 5, 2, tzinfo=ZoneInfo("UTC"))

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
                description="Over Repay",
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
                        amount="5010",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 4, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 4, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("110.2")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("29889.80"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("10")),
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
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100.20"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check interest accrues",
                expected_balances_at_ts={
                    datetime(2019, 1, 5, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("110.21")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("29889.80"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("10")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0.01"),
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
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100.20"),
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

    def test_uncharged_interest_acc_from_scod_reversal(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "transaction_references": dumps({"balance_transfer": ["REF1", "REF2"]}),
            "transaction_annual_percentage_rate": dumps(
                {"balance_transfer": {"REF1": "1", "REF2": "3"}}
            ),
            "transaction_base_interest_rates": dumps(
                {"balance_transfer": {"REF1": "0.22", "REF2": "0.28"}}
            ),
            "annual_fee": "0",
            "transaction_type_limits": dumps({}),
            "credit_limit": "30000",
        }

        template_params = {
            **default_template_params,
            "base_interest_rates": dumps(
                {"cash_advance": "0.36", "purchase": "0.28", "transfer": "0.28"}
            ),
            "annual_percentage_rate": dumps(
                {"cash_advance": "2", "purchase": "1", "transfer": "1"}
            ),
            "minimum_percentage_due": dumps(
                {
                    "purchase": "0.2",
                    "cash_advance": "0.2",
                    "balance_transfer": "0.2",
                    "transfer": "1.0",
                    "interest": "1.0",
                    "fees": "1.0",
                }
            ),
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Balance Transfer REF1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("29000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Balance Transfer REF2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("6000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("24000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("5000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("8100")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("21900")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("5000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("2000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        instruction_details={"transaction_code": "xxx"},
                        event_datetime=datetime(2019, 1, 1, 4, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 4, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("11100")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("18900")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("5000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("2000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("3000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check Outstanding 1",
                expected_balances_at_ts={
                    datetime(2019, 1, 23, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("11143.34")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("18900")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("11143.34"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("5000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("2000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("43.34"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("3000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check Statement 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("11161.07")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("18838.93"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("11161.07"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_BILLED"),
                                Decimal("5000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("2000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("61.07"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("3000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
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
            SubTest(
                description="Check Outstanding 2",
                expected_balances_at_ts={
                    datetime(2019, 2, 23, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("11204.41")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("18838.93"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("11204.41"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_BILLED"),
                                Decimal("5000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("2000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("13.20"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_UNCHARGED"),
                                Decimal("84.48"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("43.34"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("61.07"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("3000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("50.60"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Full Outstanding repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="11204.41",
                        event_datetime=datetime(2019, 2, 23, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 23, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("0")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("30000")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_BILLED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("13.20"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_UNCHARGED"),
                                Decimal("84.48"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("50.60"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check Statement 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("0")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("30000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
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

    def test_uncharged_interest_acc_from_txn_reversal(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "transaction_references": dumps({"balance_transfer": ["REF1", "REF2"]}),
            "transaction_annual_percentage_rate": dumps(
                {"balance_transfer": {"REF1": "1", "REF2": "3"}}
            ),
            "transaction_base_interest_rates": dumps(
                {"balance_transfer": {"REF1": "0.22", "REF2": "0.28"}}
            ),
            "annual_fee": "0",
            "transaction_type_limits": dumps({}),
            "credit_limit": "30000",
        }

        template_params = {
            **default_template_params,
            "base_interest_rates": dumps(
                {"cash_advance": "0.36", "purchase": "0.28", "transfer": "0.28"}
            ),
            "annual_percentage_rate": dumps(
                {"cash_advance": "2", "purchase": "1", "transfer": "1"}
            ),
            "minimum_percentage_due": dumps(
                {
                    "purchase": "0.2",
                    "cash_advance": "0.2",
                    "balance_transfer": "0.2",
                    "transfer": "1.0",
                    "interest": "1.0",
                    "fees": "1.0",
                }
            ),
        }

        sub_tests = [
            SubTest(
                description="Balance Transfer REF1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("29000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Balance Transfer REF2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("6000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("24000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("5000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("8100")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("21900")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("5000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("2000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        instruction_details={"transaction_code": "xxx"},
                        event_datetime=datetime(2019, 1, 1, 4, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 4, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("11100")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("18900")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("5000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("2000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("3000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check Outstanding 1",
                expected_balances_at_ts={
                    datetime(2019, 1, 23, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("11143.34")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("18900")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("11143.34"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("5000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("2000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("13.20"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_PRE_SCOD_UNCHRGD),
                                Decimal("84.48"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("43.34"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("3000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("50.60"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check Statement 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("11161.07")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("18838.93"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("11161.07"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_BILLED"),
                                Decimal("5000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("2000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("18.60"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_POST_SCOD_UNCHRGD),
                                Decimal("119.04"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("61.07"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("3000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("71.30"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check Outstanding 2",
                expected_balances_at_ts={
                    datetime(2019, 2, 23, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("11204.41")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("18838.93"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("11204.41"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_BILLED"),
                                Decimal("5000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("2000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("31.80"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_POST_SCOD_UNCHRGD),
                                Decimal("203.52"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("43.34"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("61.07"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("3000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("121.90"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Full Outstanding repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="11204.41",
                        event_datetime=datetime(2019, 2, 23, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 23, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("0")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("30000")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_BILLED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("31.80"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_POST_SCOD_UNCHRGD),
                                Decimal("203.52"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("121.90"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check Statement 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("0")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("30000")),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
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

    def test_cash_advance_and_interest_on_unpaid_interest_accrued(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 4, 1, 0, 2, tzinfo=ZoneInfo("UTC"))

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
            "accrue_interest_on_unpaid_interest": "True",
            "base_interest_rates": default_template_update(
                "base_interest_rates", {"cash_advance": "0.36"}
            ),
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
                            (BalanceDimensions("DEFAULT"), Decimal("5100")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("24900")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("5000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Payment Due Date + 1 Day",
                expected_balances_at_ts={
                    datetime(2019, 2, 22, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("5311.99")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("24791.54"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("5000.0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("103.53"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("108.46"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("100"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("258.46")),
                            (BalanceDimensions("OVERDUE_1"), Decimal("258.46")),
                            (BalanceDimensions("OVERDUE_2"), Decimal("0")),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            # 1 day of interest for unpaid 108.46
            # 108.46 * 0.36 / 365 * 1 = 0.10697
            # DEFAULT 5316.92 - 0.10697 = 5317.03
            SubTest(
                description="Statement Balances",
                expected_balances_at_ts={
                    datetime(2019, 2, 23, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("100"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("5317.03")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("24791.54"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("5000.0"),
                            ),
                            # 5000 * 0.36/365 (interest on cash advance)
                            # + 108.46 * 0.36 / 365 (interest on unpaid interest)
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("108.57"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0.0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("108.46"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("258.46")),
                            (BalanceDimensions("OVERDUE_1"), Decimal("258.46")),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            # UNPAID INTEREST
            # 23/02 - 21/03 - 108.46 (7 + 21 days)
            # 22/03 - 01/04 - 247.27 (9 + 1 days)
            # 28 * 0.36 / 365 * 108.46 = 2.9953
            # 10 * 0.36 / 365 * 247.24 = 2.4385
            # DEFAULT at 23/02 5499.33 + 5.4338 = 5504.76
            SubTest(
                description="Statement Balances",
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("5504.91")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("24495.09"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0.0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("5000.0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("157.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("247.27"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("100"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("1210.64")),
                            (BalanceDimensions("OVERDUE_1"), Decimal("397.27")),
                            (BalanceDimensions("OVERDUE_2"), Decimal("258.46")),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
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

    def test_cash_advance_and_interest_on_unpaid_fees_accrued(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 4, 1, 0, 2, tzinfo=ZoneInfo("UTC"))

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
            "accrue_interest_on_unpaid_fees": "True",
            "base_interest_rates": default_template_update(
                "base_interest_rates", {"cash_advance": "0.36", "fees": "0.50"}
            ),
            "annual_percentage_rate": default_template_update(
                "annual_percentage_rate", {"cash_advance": "0.36", "fees": "0.50"}
            ),
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
                            (BalanceDimensions("DEFAULT"), Decimal("5100")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("24900")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("5000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Payment Due Date + 1 Day",
                expected_balances_at_ts={
                    datetime(2019, 2, 22, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("5311.99")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("24791.54"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("5000.0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("103.53"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("108.46"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("100"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("258.46")),
                            (BalanceDimensions("OVERDUE_1"), Decimal("258.46")),
                            (BalanceDimensions("OVERDUE_2"), Decimal("0")),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            # 1 day of interest for unpaid fees 100
            # 100 * 0.5 / 365 * 1 = 0.1369
            # DEFAULT 5316.92 + 0.14 = 5317.06
            SubTest(
                description="Statement Balances",
                expected_balances_at_ts={
                    datetime(2019, 2, 23, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("100"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("5317.06")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("24791.54"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("5000.0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("108.46"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0.0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("108.46"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEE_INTEREST_CHARGED"),
                                Decimal("0.14"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEE_INTEREST_BILLED"),
                                Decimal("0.0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEE_INTEREST_UNPAID"),
                                Decimal("0.0"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("258.46")),
                            (BalanceDimensions("OVERDUE_1"), Decimal("258.46")),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            # UNPAID FEES
            # 23/02 - 01/03 - 100 (7 days)
            # 02/03 - 01/04 - 100 (31 days)
            # 31 * 0.14 = 4.34
            # 7 * 0.14 = 0.98
            # DEFAULT at 23/02 5499.33 + 4.34 + 0.98 = 5504.76
            # AVAILABLE BALANCE 24500.67 - 24495.35 = 5.32
            SubTest(
                description="Statement Balances",
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("5504.65")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("24495.35"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0.0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("5000.0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("152.83"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("246.50"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEE_INTEREST_CHARGED"),
                                Decimal("0.0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEE_INTEREST_BILLED"),
                                Decimal("4.34"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEE_INTEREST_UNPAID"),
                                Decimal("0.98"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("1204.29")),
                            (BalanceDimensions("OVERDUE_1"), Decimal("396.50")),
                            (BalanceDimensions("OVERDUE_2"), Decimal("258.46")),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
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

    def test_charge_interest_acc_from_scod_for_types_with_ref_when_revolver_starts(
        self,
    ):
        """
        Set up balance_transfer txn type with charge_interest_from_transaction_date=False.
        Let account go into revolver on PDD.
        See that we do not encounter contract parameter errors when revolver logic attempts
        to move uncharged balance_transfer interests to the charged address
        """
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "transaction_references": dumps({"balance_transfer": ["REF1"]}),
            "transaction_annual_percentage_rate": dumps({"balance_transfer": {"REF1": "0.25"}}),
            "transaction_base_interest_rates": dumps({"balance_transfer": {"REF1": "0.22"}}),
            "annual_fee": "0",
            "credit_limit": "3000",
        }

        template_params = {
            **default_template_params,
            "transaction_types": default_template_update(
                "transaction_types",
                {"balance_transfer": {"charge_interest_from_transaction_date": "False"}},
            ),
            "minimum_percentage_due": default_template_update(
                "minimum_percentage_due", {"balance_transfer": "0.2"}
            ),
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Balance Transfer REF1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                        event_datetime=datetime(2019, 1, 2, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("2000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Before First PDD",
                expected_balances_at_ts={
                    datetime(2019, 2, 24, 23, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("2000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("13.80"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="After First PDD",
                expected_balances_at_ts={
                    datetime(2019, 2, 25, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1114.40")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("1900")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("14.40"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
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

    def test_charge_interest_acc_from_txn_for_types_with_ref_when_revolver_starts(self):
        """
        Set up balance_transfer txn type with charge_interest_from_transaction_date=False.
        Let account go into revolver on PDD.
        See that we do not encounter contract parameter errors when revolver logic attempts
        to move uncharged balance_transfer interests to the charged address
        """
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "transaction_references": dumps({"balance_transfer": ["REF1"]}),
            "transaction_annual_percentage_rate": dumps({"balance_transfer": {"REF1": "0.25"}}),
            "transaction_base_interest_rates": dumps({"balance_transfer": {"REF1": "0.22"}}),
            "annual_fee": "0",
            "credit_limit": "3000",
        }

        template_params = {
            **default_template_params,
            "transaction_types": default_template_update(
                "transaction_types",
                {"balance_transfer": {"charge_interest_from_transaction_date": "False"}},
            ),
            "minimum_percentage_due": default_template_update(
                "minimum_percentage_due", {"balance_transfer": "0.2"}
            ),
        }

        sub_tests = [
            SubTest(
                description="Balance Transfer REF1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                        event_datetime=datetime(2019, 1, 2, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("2000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Before First PDD",
                expected_balances_at_ts={
                    datetime(2019, 2, 24, 23, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("2000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("31.80"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="After First PDD",
                expected_balances_at_ts={
                    datetime(2019, 2, 25, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1132.40")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("1900")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("32.40"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
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

    def test_interest_free_period_unchargd_interest_acc_from_scod_0ed_if_outstanding_bal_paid(
        self,
    ):
        """
        Set up interest free periods for purchases, cash advances, and balance transfers
        Cash advances have charge_interest_from_transaction_date=True
        Make 3000 balance transfer, spend 1000 GBP, and withdraw 500 GBP cash advance
        Pay off all balances before PDD
        Verify uncharged interest (including interest free period uncharged interest) is zeroed out
        Make a purchase and cash advance after PDD - verify that these transactions do not accrue
        any interest before next SCOD, and after the SCOD they will accrue interest in the
        INTEREST_FREE_PERIOD_UNCHARGED addresses again
        """
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 26, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "transaction_references": dumps({"balance_transfer": ["REF1"]}),
            "transaction_annual_percentage_rate": dumps({"balance_transfer": {"REF1": "0.25"}}),
            "transaction_base_interest_rates": dumps({"balance_transfer": {"REF1": "0.22"}}),
            "annual_fee": "0",
            "credit_limit": "10000",
            "interest_free_expiry": dumps(
                {"purchase": "2019-12-31 12:00:00", "cash_advance": "2019-12-31 12:00:00"}
            ),
            "transaction_interest_free_expiry": dumps(
                {"balance_transfer": {"REF1": "2019-12-31 12:00:00"}}
            ),
        }

        template_params = {
            **default_template_params,
            "base_interest_rates": dumps(
                {"purchase": "0.25", "cash_advance": "0.36", "transfer": "0.36"}
            ),
            "annual_percentage_rate": dumps(
                {"transfer": "0.23", "purchase": "0.25", "cash_advance": "0.28"}
            ),
            "minimum_amount_due": "100",
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
            "accrue_interest_from_txn_day": "False",
        }

        # Alias address to shorter form for linter purposes
        BALANCE_TRANSFER_REF1_IFP = "BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"

        sub_tests = [
            SubTest(
                description="Balance Transfer REF1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                        event_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("3000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("7000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("3000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("4000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("6000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="200",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 4, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 4, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("4210")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("5790")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("10"),
                            ),
                        ]
                    }
                },
            ),
            # No interest is accrued before first SCOD, due to active interest free periods
            SubTest(
                description="SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("5790.00"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4210.00"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("4210.00")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("3000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("10"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            # Balance transfer REF1 accrued 23 days worth of interest free period interest
            # at daily rate of 1.81
            # Cash advance accrued 23 days worth of interest free period interest
            # at daily rate of 0.2
            # Purchase accrued 23 days worth of interest free period interest
            # at daily rate of 0.68
            SubTest(
                description="Before PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 24, 20, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4210.00"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("41.63"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("4.60"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("15.64"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay full balance",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="4210",
                        event_datetime=datetime(2019, 2, 24, 23, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            # Check that all uncharged interest is zeroed out, and there is nothing billed
            SubTest(
                description="After PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 25, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
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

    def test_interest_free_period_unchargd_interest_acc_from_txn_0ed_if_outstanding_bal_paid(
        self,
    ):
        """
        Set up interest free periods for purchases, cash advances, and balance transfers
        Cash advances have charge_interest_from_transaction_date=True
        Make 3000 balance transfer, spend 1000 GBP, and withdraw 500 GBP cash advance
        Pay off all balances before PDD
        Verify uncharged interest (including interest free period uncharged interest) is zeroed out
        Make a purchase and cash advance after PDD - verify that these transactions do not accrue
        any interest before next SCOD, and after the SCOD they will accrue interest in the
        INTEREST_FREE_PERIOD_UNCHARGED addresses again
        """
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 26, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "transaction_references": dumps({"balance_transfer": ["REF1"]}),
            "transaction_annual_percentage_rate": dumps({"balance_transfer": {"REF1": "0.25"}}),
            "transaction_base_interest_rates": dumps({"balance_transfer": {"REF1": "0.22"}}),
            "annual_fee": "0",
            "credit_limit": "10000",
            "interest_free_expiry": dumps(
                {"purchase": "2019-12-31 12:00:00", "cash_advance": "2019-12-31 12:00:00"}
            ),
            "transaction_interest_free_expiry": dumps(
                {"balance_transfer": {"REF1": "2019-12-31 12:00:00"}}
            ),
        }
        template_params = {
            **default_template_params,
            "base_interest_rates": dumps(
                {"purchase": "0.25", "cash_advance": "0.36", "transfer": "0.36"}
            ),
            "annual_percentage_rate": dumps(
                {"transfer": "0.23", "purchase": "0.25", "cash_advance": "0.28"}
            ),
            "minimum_amount_due": "100",
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
        }

        # Alias address to shorter form for linter purposes
        BALANCE_TRANSFER_REF1_IFP = "BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
        sub_tests = [
            SubTest(
                description="Balance Transfer REF1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                        event_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("3000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("7000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("3000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("4000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("6000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="200",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 4, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 4, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("4210")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("5790")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("10"),
                            ),
                        ]
                    }
                },
            ),
            # No interest is accrued before first SCOD, due to active interest free periods
            SubTest(
                description="SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("5790.00"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4210.00"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("4210.00")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("3000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("10"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            # Balance transfer REF1 accrued 23 days worth of interest free period interest
            # at daily rate of 1.81
            # Cash advance accrued 23 days worth of interest free period interest
            # at daily rate of 0.2
            # Purchase accrued 23 days worth of interest free period interest
            # at daily rate of 0.68
            SubTest(
                description="Before PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 24, 20, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4210.00"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("41.63"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("4.60"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("15.64"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay full balance",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="4210",
                        event_datetime=datetime(2019, 2, 24, 23, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            # Check that all uncharged interest is zeroed out, and there is nothing billed
            SubTest(
                description="After PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 25, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
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

    @skip(
        "tests were passing in 'no_call' to simulation_test_scenario, which has since been removed"
        " so this is now throwing errors. Will have a closer look"
    )
    def test_interest_free_period_unchrgd_interest_acc_from_scod_0ed_if_mad_paid_and_revolver(
        self,
    ):
        """
        Set up interest free periods for purchases, cash advances, and balance transfers
        Make 3000 balance transfer, spend 1000 GBP, and withdraw 500 GBP cash advance
        Make sure MAD balance is based on fixed amount parameter (100GBP)
        Make sure MAD is repaid by PDD, but leave unpaid balances on all txn types
        Verify uncharged interest is zeroed out according to each txn type's interest free periods
        Verify the behaviour above doesn't change even if the account is in revolver (after SCOD 2)
        Include checks on behavioural difference caused by charge_interest_from_transaction_date
        """

        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 26, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "transaction_references": dumps({"balance_transfer": ["REF1"]}),
            "transaction_annual_percentage_rate": dumps({"balance_transfer": {"REF1": "0.25"}}),
            "transaction_base_interest_rates": dumps({"balance_transfer": {"REF1": "0.22"}}),
            "annual_fee": "0",
            "credit_limit": "10000",
            "interest_free_expiry": dumps(
                {"purchase": "2019-12-31 12:00:00", "cash_advance": "2019-12-31 12:00:00"}
            ),
            "transaction_interest_free_expiry": dumps(
                {"balance_transfer": {"REF1": "2019-12-31 12:00:00"}}
            ),
        }

        template_params = {
            **default_template_params,
            "base_interest_rates": dumps(
                {"transfer": "0.36", "purchase": "0.25", "cash_advance": "0.36"}
            ),
            "annual_percentage_rate": dumps(
                {"transfer": "0.23", "purchase": "0.25", "cash_advance": "0.28"}
            ),
            "minimum_amount_due": "100",
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
            "accrue_interest_from_txn_day": "False",
        }

        # Alias address to shorter form for linter purposes
        BALANCE_TRANSFER_REF1_IFP = "BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"

        sub_tests = [
            SubTest(
                description="Balance Transfer REF1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                        event_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("3000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("7000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("3000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("4000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("6000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="200",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 4, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 4, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("4210")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("5790")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("10"),
                            ),
                        ]
                    }
                },
            ),
            # No interest is accrued before first SCOD, due to active interest free periods
            SubTest(
                description="SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("5790.00"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4210.00"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("4210.00")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("3000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("10"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            # Balance transfer REF1 accrued 23 days worth of interest free period interest
            # at daily rate of 1.81
            # Cash advance accrued 23 days worth of interest free period interest
            # at daily rate of 0.2
            # Purchase accrued 23 days worth of interest free period interest
            # at daily rate of 0.68
            SubTest(
                description="Before PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 24, 20, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("41.63"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("4.60"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("15.64"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay MAD 1 on time",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=datetime(2019, 2, 24, 23, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            # Since MAD was repaid, all uncharged interest free period interest is zeroed out.
            SubTest(
                description="After PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 25, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            # Validate behaviour on SCOD 2 -- the account is now in revolver.
            # We still want the interest free period behaviour to kick in.
            # We don't expect any interest addresses to have accrued anything since last PDD.
            # Cash advance balance decreased by 100 due to repayment earlier.
            SubTest(
                description="SCOD 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("5890.00"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4110.00"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("4110.00")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_UNPAID"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("110")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            # Balance transfer REF1 accrued 23 days worth of interest free period interest
            # at daily rate of 1.81
            # Cash advance accrued 23 days worth of interest free period interest
            # at daily rate of 0.11
            # Purchase accrued 23 days worth of interest free period interest
            # at daily rate of 0.68
            SubTest(
                description="Before PDD 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 24, 20, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_UNPAID"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("41.63"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("110")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("2.53"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("15.64"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay MAD 2 on time",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=datetime(2019, 3, 24, 23, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            # Since MAD was repaid, all uncharged interest free period interest is zeroed out.
            SubTest(
                description="After PDD 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 25, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            # Sanity check that we did not run the workflow to expire the interest free periods,
            # due to MAD being paid on time
            SubTest(
                description="Check expire interest free periods workflow trigger is correct",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(months=1, day=25, seconds=1),
                        notification_type=EXPIRE_INTEREST_FREE_PERIODS_NOTIFICATION,
                        resource_id="Main account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                        notification_details={"account_id": "Main account"},
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
        self.run_test_scenario(test_scenario)

    @skip(
        "tests were passing in 'no_call' to simulation_test_scenario, which has since been removed"
        " so this is now throwing errors. Will have a closer look"
    )
    def test_interest_free_period_unchrgd_interest_acc_from_txn_0ed_if_mad_paid_and_revolver(
        self,
    ):
        """
        Set up interest free periods for purchases, cash advances, and balance transfers
        Make 3000 balance transfer, spend 1000 GBP, and withdraw 500 GBP cash advance
        Make sure MAD balance is based on fixed amount parameter (100GBP)
        Make sure MAD is repaid by PDD, but leave unpaid balances on all txn types
        Verify uncharged interest is zeroed out according to each txn type's interest free periods
        Verify the behaviour above doesn't change even if the account is in revolver (after SCOD 2)
        Include checks on behavioural difference caused by charge_interest_from_transaction_date
        """

        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 26, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "transaction_references": dumps({"balance_transfer": ["REF1"]}),
            "transaction_annual_percentage_rate": dumps({"balance_transfer": {"REF1": "0.25"}}),
            "transaction_base_interest_rates": dumps({"balance_transfer": {"REF1": "0.22"}}),
            "annual_fee": "0",
            "credit_limit": "10000",
            "interest_free_expiry": dumps(
                {"purchase": "2019-12-31 12:00:00", "cash_advance": "2019-12-31 12:00:00"}
            ),
            "transaction_interest_free_expiry": dumps(
                {"balance_transfer": {"REF1": "2019-12-31 12:00:00"}}
            ),
        }
        template_params = {
            **default_template_params,
            "base_interest_rates": dumps(
                {"transfer": "0.36", "purchase": "0.25", "cash_advance": "0.36"}
            ),
            "annual_percentage_rate": dumps(
                {"transfer": "0.23", "purchase": "0.25", "cash_advance": "0.28"}
            ),
            "minimum_amount_due": "100",
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
        }

        # Alias address to shorter form for linter purposes
        BALANCE_TRANSFER_REF1_IFP = "BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
        sub_tests = [
            SubTest(
                description="Balance Transfer REF1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                        event_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("3000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("7000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("3000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("4000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("6000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="200",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 4, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 4, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("4210")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("5790")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("10"),
                            ),
                        ]
                    }
                },
            ),
            # No interest is accrued before first SCOD, due to active interest free periods
            SubTest(
                description="SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("5790.00"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4210.00"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("4210.00")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("3000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("10"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            # Balance transfer REF1 accrued 23 days worth of interest free period interest
            # at daily rate of 1.81
            # Cash advance accrued 23 days worth of interest free period interest
            # at daily rate of 0.2
            # Purchase accrued 23 days worth of interest free period interest
            # at daily rate of 0.68
            SubTest(
                description="Before PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 24, 20, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("41.63"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("4.60"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("15.64"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay MAD 1 on time",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=datetime(2019, 2, 24, 23, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            # Since MAD was repaid, all uncharged interest free period interest is zeroed out.
            SubTest(
                description="After PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 25, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            # Validate behaviour on SCOD 2 -- the account is now in revolver.
            # We still want the interest free period behaviour to kick in.
            # We don't expect any interest addresses to have accrued anything since last PDD.
            # Cash advance balance decreased by 100 due to repayment earlier.
            SubTest(
                description="SCOD 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("5890.00"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4110.00"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("4110.00")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_UNPAID"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("110")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            # Balance transfer REF1 accrued 23 days worth of interest free period interest
            # at daily rate of 1.81
            # Cash advance accrued 23 days worth of interest free period interest
            # at daily rate of 0.11
            # Purchase accrued 23 days worth of interest free period interest
            # at daily rate of 0.68
            SubTest(
                description="Before PDD 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 24, 20, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_UNPAID"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("41.63"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("110")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("2.53"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("15.64"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay MAD 2 on time",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=datetime(2019, 3, 24, 23, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            # Since MAD was repaid, all uncharged interest free period interest is zeroed out.
            SubTest(
                description="After PDD 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 25, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            # Sanity check that we did not run the workflow to expire the interest free periods,
            # due to MAD being paid on time
            SubTest(
                description="Check expire interest free periods workflow trigger is correct",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(months=2, day=22, seconds=1),
                        notification_type=EXPIRE_INTEREST_FREE_PERIODS_NOTIFICATION,
                        resource_id="Main account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                        notification_details={"account_id": "Main account"},
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
        self.run_test_scenario(test_scenario)

    def test_interest_free_period_expired_and_charged_if_mad_not_repaid_int_acc_from_scod(
        self,
    ):
        """
        For transaction types that have active interest free periods, check that the expiry workflow
        is triggered if MAD is not paid by PDD
        Verify that the interest accrued under the INTEREST_FREE_PERIOD_INTEREST_UNCHARGED address
        will now be moved over to the CHARGED address
        Include checks on behavioural difference caused by charge_interest_from_transaction_date
        """
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "transaction_references": dumps({"balance_transfer": ["REF1", "ref2"]}),
            "transaction_annual_percentage_rate": dumps(
                {"balance_transfer": {"REF1": "0.25", "ref2": "0.25"}}
            ),
            "transaction_base_interest_rates": dumps(
                {"balance_transfer": {"REF1": "0.22", "ref2": "0.25"}}
            ),
            "annual_fee": "0",
            "credit_limit": "10000",
            "interest_free_expiry": dumps({"purchase": "2019-12-31 12:00:00"}),
            "transaction_interest_free_expiry": dumps(
                {
                    "balance_transfer": {
                        "REF1": "2019-12-31 12:00:00",
                        "ref2": "2019-12-31 12:00:00",
                    }
                }
            ),
        }

        template_params = {
            **default_template_params,
            "transaction_types": default_template_update(
                "transaction_types",
                {"balance_transfer": {"charge_interest_from_transaction_date": "True"}},
            ),
            "base_interest_rates": default_template_update(
                "base_interest_rates", {"purchase": "0.25"}
            ),
            "annual_percentage_rate": default_template_update(
                "annual_percentage_rate", {"purchase": "0.25"}
            ),
            "minimum_amount_due": "100",
            "accrue_interest_from_txn_day": "False",
        }

        # Alias addresses to shorter forms for linter purposes
        BALANCE_TRANSFER_REF1_IFP = "BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
        BALANCE_TRANSFER_REF2_IFP = "BALANCE_TRANSFER_REF2_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
        sub_tests = [
            SubTest(
                description="Balance Transfer REF1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                        event_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("3000"),
                            )
                        ]
                    }
                },
            ),
            SubTest(
                description="Balance Transfer ref2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                        event_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("3000"),
                            )
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_CHARGED"),
                                Decimal("1000"),
                            )
                        ]
                    }
                },
            ),
            SubTest(
                description="Before PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 24, 20, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("41.63"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_BILLED"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF2_IFP),
                                Decimal("47.15"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("15.64"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                # Simulate instance parameter update done by workflow, which should have fired
                # due to unpaid MAD
                description="Interest free periods expired",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 2, 25, 0, tzinfo=ZoneInfo("UTC")),
                        interest_free_expiry=dumps({"purchase": ""}),
                    ),
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 2, 25, 0, tzinfo=ZoneInfo("UTC")),
                        transaction_interest_free_expiry=dumps(
                            {"balance_transfer": {"REF1": "", "REF2": ""}}
                        ),
                    ),
                ],
            ),
            SubTest(
                # Verify that all the INTEREST_FREE_PERIOD_INTEREST_UNCHARGED balance moved to
                # CHARGED addresses, plus one days worth of accrued interest
                description="After PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 25, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("43.44"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("49.20"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF2_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("16.32"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            # Check that we did run the workflow to expire the interest free periods,
            # due to MAD not being paid on time
            SubTest(
                description="Check expire interest free periods workflow trigger is correct",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(months=1, day=25, seconds=1),
                        notification_type=EXPIRE_INTEREST_FREE_PERIODS_NOTIFICATION,
                        resource_id="Main account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                        notification_details={"account_id": "Main account"},
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
        self.run_test_scenario(test_scenario)

    def test_interest_free_period_expired_and_charged_if_mad_not_repaid_int_acc_from_txn(
        self,
    ):
        """
        For transaction types that have active interest free periods, check that the expiry workflow
        is triggered if MAD is not paid by PDD
        Verify that the interest accrued under the INTEREST_FREE_PERIOD_INTEREST_UNCHARGED address
        will now be moved over to the CHARGED address
        Include checks on behavioural difference caused by charge_interest_from_transaction_date
        """

        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "transaction_references": dumps({"balance_transfer": ["REF1", "ref2"]}),
            "transaction_annual_percentage_rate": dumps(
                {"balance_transfer": {"REF1": "0.25", "ref2": "0.25"}}
            ),
            "transaction_base_interest_rates": dumps(
                {"balance_transfer": {"REF1": "0.22", "ref2": "0.25"}}
            ),
            "annual_fee": "0",
            "credit_limit": "10000",
            "interest_free_expiry": dumps({"purchase": "2019-12-31 12:00:00"}),
            "transaction_interest_free_expiry": dumps(
                {
                    "balance_transfer": {
                        "REF1": "2019-12-31 12:00:00",
                        "ref2": "2019-12-31 12:00:00",
                    }
                }
            ),
        }

        template_params = {
            **default_template_params,
            "transaction_types": default_template_update(
                "transaction_types",
                {"balance_transfer": {"charge_interest_from_transaction_date": "True"}},
            ),
            "base_interest_rates": default_template_update(
                "base_interest_rates", {"purchase": "0.25"}
            ),
            "annual_percentage_rate": default_template_update(
                "annual_percentage_rate", {"purchase": "0.25"}
            ),
            "minimum_amount_due": "100",
        }

        # Alias addresses to shorter forms for linter purposes
        BALANCE_TRANSFER_REF1_IFP = "BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
        BALANCE_TRANSFER_REF2_IFP = "BALANCE_TRANSFER_REF2_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
        sub_tests = [
            SubTest(
                description="Balance Transfer REF1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                        event_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("3000"),
                            )
                        ]
                    }
                },
            ),
            SubTest(
                description="Balance Transfer ref2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                        event_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("3000"),
                            )
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_CHARGED"),
                                Decimal("1000"),
                            )
                        ]
                    }
                },
            ),
            SubTest(
                description="Before PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 24, 20, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("41.63"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_BILLED"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF2_IFP),
                                Decimal("47.15"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_PRE_SCOD_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_POST_SCOD_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("15.64"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                # Simulate instance parameter update done by workflow, which should have fired
                # due to unpaid MAD
                description="Interest free periods expired",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 2, 25, 0, tzinfo=ZoneInfo("UTC")),
                        interest_free_expiry=dumps({"purchase": ""}),
                    ),
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 2, 25, 0, tzinfo=ZoneInfo("UTC")),
                        transaction_interest_free_expiry=dumps(
                            {"balance_transfer": {"REF1": "", "REF2": ""}}
                        ),
                    ),
                ],
            ),
            SubTest(
                # Verify that all the INTEREST_FREE_PERIOD_INTEREST_UNCHARGED balance moved to
                # CHARGED addresses, plus one days worth of accrued interest
                description="After PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 25, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("43.44"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("49.20"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF2_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("16.32"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_PRE_SCOD_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_POST_SCOD_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            # Check that we did run the workflow to expire the interest free periods,
            # due to MAD not being paid on time
            SubTest(
                description="Check expire interest free periods workflow trigger is correct",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(months=1, day=25, seconds=1),
                        notification_type=EXPIRE_INTEREST_FREE_PERIODS_NOTIFICATION,
                        resource_id="Main account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                        notification_details={"account_id": "Main account"},
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
        self.run_test_scenario(test_scenario)

    def test_interest_free_period_expiry_during_current_statement_cycle_int_acc_from_scod(
        self,
    ):
        """
        Set up interest free periods for purchase, cash advances, and balance transfers
        Cash advance has charge_interest_from_transaction_date=True, others have it as False
        Make cash advance interest free period expire during first month
        Make purchase & balance transfer REF1 interest free period expire on second month before PDD
        Make balance transfer REF2 interest free period expire during second month after PDD
        Make 3000 balance transfer REF1, 2000 balance transfer REF2,
        spend 1000 GBP, and withdraw 500 GBP cash advance
        Make sure MAD balance is based on fixed amount parameter (100GBP)
        Make sure MAD is repaid by PDD, but leave unpaid balances on all txn types
        Verify uncharged interest is zeroed out according to each txn type's interest free periods
        Verify that outside the interest free period, interest gets charged and billed accordingly
        """

        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "transaction_references": dumps({"balance_transfer": ["REF1", "REF2"]}),
            "transaction_annual_percentage_rate": dumps(
                {"balance_transfer": {"REF1": "0.25", "REF2": "0.25"}}
            ),
            "transaction_base_interest_rates": dumps(
                {"balance_transfer": {"REF1": "0.22", "REF2": "0.22"}}
            ),
            "annual_fee": "0",
            "credit_limit": "10000",
            "interest_free_expiry": dumps(
                {"purchase": "2019-02-10 12:00:00", "cash_advance": "2019-01-28 12:00:00"}
            ),
            "transaction_interest_free_expiry": dumps(
                {
                    "balance_transfer": {
                        "REF1": "2019-02-27 12:00:00",
                        "REF2": "2019-02-10 12:00:00",
                    }
                }
            ),
        }

        template_params = {
            **default_template_params,
            "base_interest_rates": dumps(
                {"transfer": "0.36", "purchase": "0.25", "cash_advance": "0.36"}
            ),
            "annual_percentage_rate": dumps(
                {"transfer": "0.23", "purchase": "0.25", "cash_advance": "0.28"}
            ),
            "minimum_amount_due": "100",
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
            "accrue_interest_from_txn_day": "False",
        }

        # Alias addresses to shorter forms for linter purposes
        BALANCE_TRANSFER_REF1_IFP = "BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
        BALANCE_TRANSFER_REF2_IFP = "BALANCE_TRANSFER_REF2_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
        sub_tests = [
            SubTest(
                description="Balance Transfer REF1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                        event_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("3000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("7000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("3000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Balance Transfer REF2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("5000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("5000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("2000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("6000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("4000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="200",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 4, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 4, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("6210")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("3790")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("10"),
                            ),
                        ]
                    }
                },
            ),
            # Cash advance billed 4 days worth of interest at daily rate of 0.2
            SubTest(
                description="SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("3789.20"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("6210.80"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("6210.80")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_BILLED"),
                                Decimal("2000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0.80"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("10"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            # Balance transfer REF1 accrued 23 days worth of interest free period interest
            # at at daily rate of 1.81
            # Balance transfer REF2 accrued 9 days worth of interest free period interest
            # at daily rate of 1.21
            # Balance transfer REF2 accrued 14 days worth of interest outside interest
            # free period at daily rate of 1.21
            # Cash advance charged 23 days worth of interest at daily rate of 0.2
            # Purchase accrued 9 days worth of interest free period interest
            # at daily rate of 0.68
            # Purchase accrued 14 days worth of interest outside interest free period
            # at daily rate of 0.68
            SubTest(
                description="Before PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 24, 20, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("41.63"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_BILLED"),
                                Decimal("2000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_UNCHARGED"),
                                Decimal("16.94"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF2_IFP),
                                Decimal("10.89"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("4.60"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("9.52"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("6.12"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay MAD on time",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=datetime(2019, 2, 24, 23, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            # Since MAD was repaid, all uncharged interest free period interest is zeroed out.
            # The UNCHARGED interest accrued outside of interest free periods is moved to
            # CHARGED address, plus one more day's worth of interests.
            SubTest(
                description="After PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 25, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("18.15"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF2_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("4.71"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("10.20"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            # Between PDD and SCOD 2, we don't expect to see any interest accrued for txn types
            # that have active interest free periods.
            # Otherwise we want to see accrued interest to directly go to CHARGED address,
            # since the account is now in revolver. Which is then BILLED by SCOD 2.
            # The only transaction that still has an interest free period is BT REF1, which
            # expires on 27th Feb. So we will see 2 days worth of charged interest for BT REF1.
            # Cash advance balance decreased by 100 due to repayment earlier.
            SubTest(
                description="SCOD 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("3844.52"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("6155.48"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("6155.48")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_UNPAID"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("3.62"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_UNPAID"),
                                Decimal("2000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_BILLED"),
                                Decimal("22.99"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF2_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("110.80"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("5.15"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("12.92"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
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

    def test_interest_free_period_expiry_during_current_statement_cycle_int_acc_from_txn(
        self,
    ):
        """
        Set up interest free periods for purchase, cash advances, and balance transfers
        Cash advance has charge_interest_from_transaction_date=True, others have it as False
        Make cash advance interest free period expire during first month
        Make purchase & balance transfer REF1 interest free period expire on second month before PDD
        Make balance transfer REF2 interest free period expire during second month after PDD
        Make 3000 balance transfer REF1, 2000 balance transfer REF2,
        spend 1000 GBP, and withdraw 500 GBP cash advance
        Make sure MAD balance is based on fixed amount parameter (100GBP)
        Make sure MAD is repaid by PDD, but leave unpaid balances on all txn types
        Verify uncharged interest is zeroed out according to each txn type's interest free periods
        Verify that outside the interest free period, interest gets charged and billed accordingly
        """

        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "transaction_references": dumps({"balance_transfer": ["REF1", "REF2"]}),
            "transaction_annual_percentage_rate": dumps(
                {"balance_transfer": {"REF1": "0.25", "REF2": "0.25"}}
            ),
            "transaction_base_interest_rates": dumps(
                {"balance_transfer": {"REF1": "0.22", "REF2": "0.22"}}
            ),
            "annual_fee": "0",
            "credit_limit": "10000",
            "interest_free_expiry": dumps(
                {"purchase": "2019-02-10 12:00:00", "cash_advance": "2019-01-28 12:00:00"}
            ),
            "transaction_interest_free_expiry": dumps(
                {
                    "balance_transfer": {
                        "REF1": "2019-02-27 12:00:00",
                        "REF2": "2019-02-10 12:00:00",
                    }
                }
            ),
        }

        template_params = {
            **default_template_params,
            "base_interest_rates": dumps(
                {"transfer": "0.36", "purchase": "0.25", "cash_advance": "0.36"}
            ),
            "annual_percentage_rate": dumps(
                {"transfer": "0.23", "purchase": "0.25", "cash_advance": "0.28"}
            ),
            "minimum_amount_due": "100",
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
        }

        # Alias addresses to shorter forms for linter purposes
        BALANCE_TRANSFER_REF1_IFP = "BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
        BALANCE_TRANSFER_REF2_IFP = "BALANCE_TRANSFER_REF2_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
        sub_tests = [
            SubTest(
                description="Balance Transfer REF1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                        event_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("3000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("7000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("3000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Balance Transfer REF2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("5000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("5000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("2000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("6000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("4000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="200",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 4, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 4, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("6210")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("3790")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("10"),
                            ),
                        ]
                    }
                },
            ),
            # Cash advance billed 4 days worth of interest at daily rate of 0.2
            SubTest(
                description="SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("3789.20"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("6210.80"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("6210.80")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_BILLED"),
                                Decimal("2000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0.80"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("10"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            # Balance transfer REF1 accrued 23 days worth of interest free period interest
            # at at daily rate of 1.81
            # Balance transfer REF2 accrued 9 days worth of interest free period interest
            # at daily rate of 1.21
            # Balance transfer REF2 accrued 14 days worth of interest outside interest
            # free period at daily rate of 1.21
            # Cash advance charged 23 days worth of interest at daily rate of 0.2
            # Purchase accrued 9 days worth of interest free period interest
            # at daily rate of 0.68
            # Purchase accrued 14 days worth of interest outside interest free period
            # at daily rate of 0.68
            SubTest(
                description="Before PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 24, 20, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("41.63"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_BILLED"),
                                Decimal("2000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_POST_SCOD_UNCHRGD),
                                Decimal("16.94"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF2_IFP),
                                Decimal("10.89"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("4.60"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("9.52"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("6.12"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay MAD on time",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=datetime(2019, 2, 24, 23, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            # Since MAD was repaid, all uncharged interest free period interest is zeroed out.
            # The UNCHARGED interest accrued outside of interest free periods is moved to
            # CHARGED address, plus one more day's worth of interests.
            SubTest(
                description="After PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 25, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("18.15"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF2_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("4.71"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("10.20"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            # Between PDD and SCOD 2, we don't expect to see any interest accrued for txn types
            # that have active interest free periods.
            # Otherwise we want to see accrued interest to directly go to CHARGED address,
            # since the account is now in revolver. Which is then BILLED by SCOD 2.
            # The only transaction that still has an interest free period is BT REF1, which
            # expires on 27th Feb. So we will see 2 days worth of charged interest for BT REF1.
            # Cash advance balance decreased by 100 due to repayment earlier.
            SubTest(
                description="SCOD 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("3844.52"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("6155.48"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("6155.48")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_UNPAID"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("3.62"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_UNPAID"),
                                Decimal("2000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_BILLED"),
                                Decimal("22.99"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF2_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("110.80"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("5.15"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("12.92"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
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

    def test_interest_free_period_starts_during_current_statement_cycle_int_acc_from_scod(
        self,
    ):
        """
        Make a purchase, take out a cash advance, make a transfer,
        and then start interest free periods on those transaction types.
        Verify that as the interest free periods start, the existing interest accrued address
        are not affected. Only new interest accrual events will add to the
        INTEREST_FREE_PERIOD_INTEREST_UNCHARGED addresses.
        Cash advance has charge_interest_from_transaction_date=True, others have it as False
        Make sure MAD balance is based on fixed amount parameter (100GBP)
        Make sure MAD is repaid by PDD, but leave unpaid balances on all txn types
        Verify INTEREST_FREE_PERIOD_INTEREST_UNCHARGED addresses get zeroed out
        Verify balances are moved from INTEREST_UNCHARGED address over to INTEREST_CHARGED
        addresses, since not the whole outstanding sum has been paid off.
        """
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "annual_fee": "0",
            "credit_limit": "10000",
            "interest_free_expiry": dumps({}),
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.05",
                        "flat_fee": "5",
                    },
                    "transfer": {
                        "over_deposit_only": "True",
                        "percentage_fee": "0.01",
                        "flat_fee": "10",
                    },
                }
            ),
        }
        template_params = {
            **default_template_params,
            "base_interest_rates": dumps(
                {"purchase": "0.25", "cash_advance": "0.36", "transfer": "0.30"}
            ),
            "annual_percentage_rate": dumps(
                {"purchase": "0.25", "cash_advance": "0.28", "transfer": "0.30"}
            ),
            "minimum_amount_due": "100",
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
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("9000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="200",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1210")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("8790")),
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
                description="Transfer out",
                events=[
                    create_transfer_instruction(
                        amount="500",
                        instruction_details={"transaction_code": "cc"},
                        creditor_target_account_id="1",
                        debtor_target_account_id="Main account",
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1720")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("8280")),
                            (BalanceDimensions("TRANSFER_CHARGED"), Decimal("500")),
                            (BalanceDimensions("TRANSFER_FEES_CHARGED"), Decimal("10")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Introduce interest free period for cash advances",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
                        interest_free_expiry=dumps({"cash_advance": "2020-12-31 00:00:00"}),
                    ),
                ],
            ),
            SubTest(
                description="Introduce interest free period for transfers",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 1, 25, 0, tzinfo=ZoneInfo("UTC")),
                        interest_free_expiry=dumps(
                            {
                                "cash_advance": "2020-12-31 00:00:00",
                                "transfer": "2020-12-31 00:00:00",
                            }
                        ),
                    ),
                ],
            ),
            SubTest(
                description="Introduce interest free period for purchases",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 2, 10, 0, tzinfo=ZoneInfo("UTC")),
                        interest_free_expiry=dumps(
                            {
                                "cash_advance": "2020-12-31 00:00:00",
                                "transfer": "2020-12-31 00:00:00",
                                "purchase": "2020-12-31 00:00:00",
                            }
                        ),
                    ),
                ],
            ),
            # Cash advance accrued 23 days worth of interest free period interest
            # at daily rate of 0.2
            # Cash advance charged 9 days worth of interest at daily rate of 0.2
            # Purchase accrued 14 days worth of interest free period interest
            # at daily rate of 0.68
            # Purchase accrued 9 days worth of interest outside interest free period
            # at daily rate of 0.68
            # Transfer accrued 23 days worth of interest free period interest
            # at daily rate of 0.41
            SubTest(
                description="Before PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 24, 20, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("1.80"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("4.60"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("6.12"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("9.52"),
                            ),
                            (BalanceDimensions("TRANSFER_BILLED"), Decimal("500")),
                            (
                                BalanceDimensions("TRANSFER_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("TRANSFER_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("TRANSFER_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "TRANSFER_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("9.43"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay MAD on time",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=datetime(2019, 2, 24, 23, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            # Since MAD was repaid, all uncharged interest free period interest is zeroed out.
            # The UNCHARGED interest accrued outside of interest free periods is moved to
            # CHARGED address. No interest was accrued on the night of 24th, since
            # all transaction types have active interest free periods.
            # There is no unpaid cash advance interest since MAD has paid that off.
            SubTest(
                description="After PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 25, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("6.12"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("TRANSFER_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("TRANSFER_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "TRANSFER_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
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

    def test_interest_free_period_starts_during_current_statement_cycle_int_acc_from_txn(
        self,
    ):
        """
        Make a purchase, take out a cash advance, make a transfer,
        and then start interest free periods on those transaction types.
        Verify that as the interest free periods start, the existing interest accrued address
        are not affected. Only new interest accrual events will add to the
        INTEREST_FREE_PERIOD_INTEREST_UNCHARGED addresses.
        Cash advance has charge_interest_from_transaction_date=True, others have it as False
        Make sure MAD balance is based on fixed amount parameter (100GBP)
        Make sure MAD is repaid by PDD, but leave unpaid balances on all txn types
        Verify INTEREST_FREE_PERIOD_INTEREST_UNCHARGED addresses get zeroed out
        Verify balances are moved from INTEREST_UNCHARGED address over to INTEREST_CHARGED
        addresses, since not the whole outstanding sum has been paid off.
        """
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "annual_fee": "0",
            "credit_limit": "10000",
            "interest_free_expiry": dumps({}),
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.05",
                        "flat_fee": "5",
                    },
                    "transfer": {
                        "over_deposit_only": "True",
                        "percentage_fee": "0.01",
                        "flat_fee": "10",
                    },
                }
            ),
        }
        template_params = {
            **default_template_params,
            "base_interest_rates": dumps(
                {"purchase": "0.25", "cash_advance": "0.36", "transfer": "0.30"}
            ),
            "annual_percentage_rate": dumps(
                {"purchase": "0.25", "cash_advance": "0.28", "transfer": "0.30"}
            ),
            "minimum_amount_due": "100",
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
        }

        sub_tests = [
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("9000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="200",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1210")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("8790")),
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
                description="Transfer out",
                events=[
                    create_transfer_instruction(
                        amount="500",
                        instruction_details={"transaction_code": "cc"},
                        creditor_target_account_id="1",
                        debtor_target_account_id="Main account",
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1720")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("8280")),
                            (BalanceDimensions("TRANSFER_CHARGED"), Decimal("500")),
                            (BalanceDimensions("TRANSFER_FEES_CHARGED"), Decimal("10")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Introduce interest free period for cash advances",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
                        interest_free_expiry=dumps({"cash_advance": "2020-12-31 00:00:00"}),
                    ),
                ],
            ),
            SubTest(
                description="Introduce interest free period for transfers",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 1, 25, 0, tzinfo=ZoneInfo("UTC")),
                        interest_free_expiry=dumps(
                            {
                                "cash_advance": "2020-12-31 00:00:00",
                                "transfer": "2020-12-31 00:00:00",
                            }
                        ),
                    ),
                ],
            ),
            SubTest(
                description="Introduce interest free period for purchases",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 2, 10, 0, tzinfo=ZoneInfo("UTC")),
                        interest_free_expiry=dumps(
                            {
                                "cash_advance": "2020-12-31 00:00:00",
                                "transfer": "2020-12-31 00:00:00",
                                "purchase": "2020-12-31 00:00:00",
                            }
                        ),
                    ),
                ],
            ),
            # Cash advance accrued 23 days worth of interest free period interest
            # at daily rate of 0.2
            # Cash advance charged 9 days worth of interest at daily rate of 0.2
            # Purchase accrued 40 days worth of interest free period interest
            # at daily rate of 0.68
            # Purchase accrued 9 days worth of interest outside interest free period
            # at daily rate of 0.68
            # Transfer accrued 24 days worth of interest outside interest free period
            # at daily rate of 0.41
            # Transfer accrued 23 days worth of interest free period interest
            # at daily rate of 0.41
            SubTest(
                description="Before PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 24, 20, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("1.80"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("4.60"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("27.20"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("9.52"),
                            ),
                            (BalanceDimensions("TRANSFER_BILLED"), Decimal("500")),
                            (
                                BalanceDimensions("TRANSFER_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("TRANSFER_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("TRANSFER_INTEREST_PRE_SCOD_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("TRANSFER_INTEREST_POST_SCOD_UNCHARGED"),
                                Decimal("9.84"),
                            ),
                            (
                                BalanceDimensions(
                                    "TRANSFER_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("9.43"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay MAD on time",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=datetime(2019, 2, 24, 23, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            # Since MAD was repaid, all uncharged interest free period interest is zeroed out.
            # The UNCHARGED interest accrued outside of interest free periods is moved to
            # CHARGED address. No interest was accrued on the night of 24th, since
            # all transaction types have active interest free periods.
            # There is no unpaid cash advance interest since MAD has paid that off.
            SubTest(
                description="After PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 25, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("27.20"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("TRANSFER_INTEREST_CHARGED"),
                                Decimal("9.84"),
                            ),
                            (
                                BalanceDimensions("TRANSFER_INTEREST_PRE_SCOD_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("TRANSFER_INTEREST_POST_SCOD_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "TRANSFER_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
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

    def test_interest_free_period_combined_scenario_1(self):
        """
        Combined scenario to test the general behaviour of interest free periods
        For this scenario we will use a balance transfer to demonstrate behaviour when
        charge_interest_from_transaction_date=True
        Match up the dates & numbers with what's provided in ACs for INC-2459
        Manual QA to verify the accrued values match up against what we see on the front end
        """

        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 4, 15, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "annual_fee": "0",
            "credit_limit": "10000",
            "payment_due_period": "21",
            "transaction_references": dumps({"balance_transfer": ["REF1"]}),
            "transaction_annual_percentage_rate": dumps({"balance_transfer": {"REF1": "0.25"}}),
            "transaction_base_interest_rates": dumps({"balance_transfer": {"REF1": "0.022"}}),
            "interest_free_expiry": dumps({}),
            "transaction_interest_free_expiry": dumps({}),
        }
        template_params = {
            **default_template_params,
            "transaction_types": default_template_update(
                "transaction_types",
                {"balance_transfer": {"charge_interest_from_transaction_date": "True"}},
            ),
            "minimum_amount_due": "100",
        }

        # Alias address to shorter form for linter purposes
        BALANCE_TRANSFER_REF1_IFP = "BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
        sub_tests = [
            SubTest(
                description="Balance Transfer REF1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                        event_datetime=datetime(2019, 1, 2, 12, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("9000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Introduce interest free period 1 for BT REF1",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 1, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                        transaction_interest_free_expiry=dumps(
                            {"balance_transfer": {"REF1": "2019-01-25 23:59:59"}}
                        ),
                    ),
                ],
                # Charged 8 days worth of interest at daily rate of 0.06
                expected_balances_at_ts={
                    datetime(2019, 1, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0.48"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Checkpoint before first interest free period expires",
                # No interest free period interest is accrued due to no outstanding statements
                expected_balances_at_ts={
                    datetime(2019, 1, 25, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0.48"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Checkpoint after SCOD 1",
                # Charged 7 more days of interest at daily rate of 0.06. All charged is billed.
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("8999.10"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1000.90"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("1000.90")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("0.90"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Introduce interest free period 2 for BT REF1",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 2, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                        transaction_interest_free_expiry=dumps(
                            {"balance_transfer": {"REF1": "2019-02-25 23:59:59"}}
                        ),
                    ),
                ],
                # Charged 9 more days of interest at daily rate of 0.06
                expected_balances_at_ts={
                    datetime(2019, 2, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("0.90"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0.54"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Checkpoint before PDD 1",
                # Accrued 11 days worth of interest free period interest at daily rate of 0.06
                expected_balances_at_ts={
                    datetime(2019, 2, 21, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("0.90"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0.54"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0.66"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay MAD on time",
                # This goes to pay off 0.90 billed interest + 99.10 on the principal
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=datetime(2019, 2, 21, 13, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Checkpoint after PDD 1",
                # MAD paid off, uncharged interest free period interest zeroed.
                expected_balances_at_ts={
                    datetime(2019, 2, 22, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("9099.10"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("901.44"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("901.44")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_UNPAID"),
                                Decimal("900.90"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0.54"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            # New daily interest is now 0.05
            SubTest(
                description="Checkpoint after SCOD 2",
                # Charged 4 more days of interest at daily rate of 0.05. All charged is billed.
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("9098.36"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("901.64"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("901.64")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("0.74"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Introduce interest free period 3 for BT REF1",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 3, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                        transaction_interest_free_expiry=dumps(
                            {"balance_transfer": {"REF1": "2019-03-25 23:59:59"}}
                        ),
                    ),
                ],
                # Charged 9 more days of interest at daily rate of 0.05
                expected_balances_at_ts={
                    datetime(2019, 3, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("0.74"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0.45"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Checkpoint before PDD 2",
                # Accrued 11 days worth of interest free period interest at daily rate of 0.05
                expected_balances_at_ts={
                    datetime(2019, 3, 21, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("0.74"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0.45"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0.55"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                # Simulate instance parameter update done by workflow, which should have fired
                # due to unpaid MAD.
                description="Interest free periods expired",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 3, 22, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                        transaction_interest_free_expiry=dumps({"balance_transfer": {"REF1": ""}}),
                    ),
                ],
            ),
            SubTest(
                description="Checkpoint after PDD 2",
                # MAD was unpaid, all interest free period uncharged interest moved to charged,
                # plus 1 more day's worth of accrual.
                expected_balances_at_ts={
                    datetime(2019, 3, 22, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("8998.36"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1002.69"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("1002.69")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_UNPAID"),
                                Decimal("900.90"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("1.05"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Checkpoint after SCOD 3",
                # Charged 10 more days worth of interest, which is added to billed sum.
                # The sum billed at last SCOD is reflected in unpaid address.
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("8996.81"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1003.19"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("1003.19")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNPAID"),
                                Decimal("0.74"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("1.55"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("211.30")),
                        ]
                    }
                },
            ),
            SubTest(
                description="April checkpoint",
                # Just check that new interest is now directly charged
                expected_balances_at_ts={
                    datetime(2019, 4, 11, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("8996.81"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1003.69"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("1003.69")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNPAID"),
                                Decimal("0.74"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("1.55"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0.50"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("211.30")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check expire interest free periods workflow trigger is correct",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(months=2, day=22, seconds=1),
                        notification_type=EXPIRE_INTEREST_FREE_PERIODS_NOTIFICATION,
                        resource_id="Main account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                        notification_details={"account_id": "Main account"},
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
        self.run_test_scenario(test_scenario)

    def test_interest_free_period_combined_scenario_2_int_acc_from_scod(self):
        """
        Combined scenario to test the general behaviour of interest free periods
        For this scenario we will use a purchase to demonstrate behaviour when
        charge_interest_from_transaction_date=False
        Match up the dates & numbers with what's provided in ACs for INC-2459
        Manual QA to verify the accrued values match up against what we see on the front end
        """
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 4, 15, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "annual_fee": "0",
            "credit_limit": "10000",
            "payment_due_period": "21",
            "interest_free_expiry": dumps({}),
            "transaction_interest_free_expiry": dumps({}),
        }
        template_params = {
            **default_template_params,
            "annual_percentage_rate": default_template_update(
                "annual_percentage_rate", {"purchase": "0.2"}
            ),
            "base_interest_rates": default_template_update(
                "base_interest_rates", {"purchase": "0.022"}
            ),
            "minimum_amount_due": "100",
            "accrue_interest_from_txn_day": "False",
        }

        # Alias address to shorter form for linter purposes
        PURCHASE_IFP = "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
        sub_tests = [
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 2, 12, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("9000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Introduce interest free period 1 for purchase",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 1, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                        interest_free_expiry=dumps({"purchase": "2019-01-25 23:59:59"}),
                    ),
                ],
                # No interest accrued before first statement
                expected_balances_at_ts={
                    datetime(2019, 1, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Checkpoint before first interest free period expires",
                # No interest accrued before first statement
                expected_balances_at_ts={
                    datetime(2019, 1, 25, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Checkpoint after SCOD 1",
                # No interest accrued before first statement
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("9000")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1000"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Introduce interest free period 2 for purchase",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 2, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                        interest_free_expiry=dumps({"purchase": "2019-02-25 23:59:59"}),
                    ),
                ],
                # Accrued 9 days worth of uncharged interest at daily rate of 0.06
                expected_balances_at_ts={
                    datetime(2019, 2, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0.54"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Checkpoint before PDD 1",
                # Accrued 11 days worth of interest free period interest at daily rate of 0.06
                expected_balances_at_ts={
                    datetime(2019, 2, 21, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0.54"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0.66")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay MAD on time",
                # Pays off 100 on the principal for purchase
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=datetime(2019, 2, 21, 13, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Checkpoint after PDD 1",
                # MAD paid off, uncharged interest free period interest zeroed.
                # Normal uncharged interest is moved to charged
                expected_balances_at_ts={
                    datetime(2019, 2, 22, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("9100")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("900.54"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("900.54")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("900")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0.54"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            # New daily interest is now 0.05
            SubTest(
                description="Checkpoint after SCOD 2",
                # Charged 4 days of interest at daily rate of 0.05. All charged is billed.
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("9099.26"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("900.74"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("900.74")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0.74"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Introduce interest free period 3 for purchase",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 3, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                        interest_free_expiry=dumps({"purchase": "2019-03-25 23:59:59"}),
                    ),
                ],
                # Charged 9 more days of interest at daily rate of 0.05
                expected_balances_at_ts={
                    datetime(2019, 3, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0.74"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0.45"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Checkpoint before PDD 2",
                # Charged 11 days worth of interest free period interest at daily rate of 0.05
                expected_balances_at_ts={
                    datetime(2019, 3, 21, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0.74"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0.45"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0.55")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                # Simulate instance parameter update done by workflow, which should have fired
                # due to unpaid MAD.
                description="Interest free periods expired",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 3, 22, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                        interest_free_expiry=dumps({"purchase": ""}),
                    ),
                ],
            ),
            SubTest(
                description="Checkpoint after PDD 2",
                # MAD was unpaid, all interest free period uncharged interest moved to charged,
                # plus 1 more day's worth of accrual.
                expected_balances_at_ts={
                    datetime(2019, 3, 22, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("8999.26"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1001.79"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("1001.79")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("900")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("1.05"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Checkpoint after SCOD 3",
                # Charged 10 more days worth of interest, which is added to billed sum.
                # The sum billed at last SCOD is reflected in unpaid address.
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("8997.71"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1002.29"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("1002.29")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0.74"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("1.55"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("211.29")),
                        ]
                    }
                },
            ),
            SubTest(
                description="April checkpoint",
                # Just check that new interest is now directly charged
                expected_balances_at_ts={
                    datetime(2019, 4, 11, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("8997.71"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1002.79"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("1002.79")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0.74"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("1.55"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0.50"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("211.29")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check expire interest free periods workflow trigger is correct",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(months=2, day=22, seconds=1),
                        notification_type=EXPIRE_INTEREST_FREE_PERIODS_NOTIFICATION,
                        resource_id="Main account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                        notification_details={"account_id": "Main account"},
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
        self.run_test_scenario(test_scenario)

    def test_interest_free_period_combined_scenario_2_int_acc_from_txn(self):
        """
        Combined scenario to test the general behaviour of interest free periods
        For this scenario we will use a purchase to demonstrate behaviour when
        charge_interest_from_transaction_date=False
        Match up the dates & numbers with what's provided in ACs for INC-2459
        Manual QA to verify the accrued values match up against what we see on the front end
        """
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 4, 15, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "annual_fee": "0",
            "credit_limit": "10000",
            "payment_due_period": "21",
            "interest_free_expiry": dumps({}),
            "transaction_interest_free_expiry": dumps({}),
        }
        template_params = {
            **default_template_params,
            "annual_percentage_rate": default_template_update(
                "annual_percentage_rate", {"purchase": "0.2"}
            ),
            "base_interest_rates": default_template_update(
                "base_interest_rates", {"purchase": "0.022"}
            ),
            "minimum_amount_due": "100",
        }

        # Alias address to shorter form for linter purposes
        PURCHASE_IFP = "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"

        sub_tests = [
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 2, 12, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("9000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Introduce interest free period 1 for purchase",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 1, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                        interest_free_expiry=dumps({"purchase": "2019-01-25 23:59:59"}),
                    ),
                ],
                # Accrued 8 days worth of uncharged interest at daily rate of 0.06
                expected_balances_at_ts={
                    datetime(2019, 1, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0.48"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Checkpoint before first interest free period expires",
                expected_balances_at_ts={
                    datetime(2019, 1, 25, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0.48"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Checkpoint after SCOD 1",
                # Accrued 9 days worth of uncharged interest at daily rate of 0.06
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": {
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("9000")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1000"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0.90"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        }
                    }
                },
            ),
            SubTest(
                description="Introduce interest free period 2 for purchase",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 2, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                        interest_free_expiry=dumps({"purchase": "2019-02-25 23:59:59"}),
                    ),
                ],
                # Accrued 9 days worth of uncharged interest at daily rate of 0.06
                expected_balances_at_ts={
                    datetime(2019, 2, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("1.44"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Checkpoint before PDD 1",
                # Accrued 11 days worth of interest free period interest at daily rate of 0.06
                expected_balances_at_ts={
                    datetime(2019, 2, 21, 11, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("1.44"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0.66")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay MAD on time",
                # Pays off 100 on the principal for purchase
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=datetime(2019, 2, 21, 13, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Checkpoint after PDD 1",
                # MAD paid off, uncharged interest free period interest zeroed.
                # Normal uncharged interest is moved to charged
                expected_balances_at_ts={
                    datetime(2019, 2, 22, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("9100")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("901.44"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("901.44")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("900")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("1.44"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            # New daily interest is now 0.05
            SubTest(
                description="Checkpoint after SCOD 2",
                # Charged 4 days of interest at daily rate of 0.05. All charged is billed.
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("9098.36"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("901.64"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("901.64")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("1.64"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Introduce interest free period 3 for purchase",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 3, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                        interest_free_expiry=dumps({"purchase": "2019-03-25 23:59:59"}),
                    ),
                ],
                # Charged 9 more days of interest at daily rate of 0.05
                expected_balances_at_ts={
                    datetime(2019, 3, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("1.64"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0.45"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Checkpoint before PDD 2",
                # Charged 11 days worth of interest free period interest at daily rate of 0.05
                expected_balances_at_ts={
                    datetime(2019, 3, 21, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("1.64"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0.45"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0.55")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                # Simulate instance parameter update done by workflow, which should have fired
                # due to unpaid MAD.
                description="Interest free periods expired",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 3, 22, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                        interest_free_expiry=dumps({"purchase": ""}),
                    ),
                ],
            ),
            SubTest(
                description="Checkpoint after PDD 2",
                # MAD was unpaid, all interest free period uncharged interest moved to charged,
                # plus 1 more day's worth of accrual.
                expected_balances_at_ts={
                    datetime(2019, 3, 22, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("8998.36"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1002.69"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("1002.69")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("900")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("1.05"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Checkpoint after SCOD 3",
                # Charged 10 more days worth of interest, which is added to billed sum.
                # The sum billed at last SCOD is reflected in unpaid address.
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("8996.81"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1003.19"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("1003.19")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("1.64"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("1.55"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("212.19")),
                        ]
                    }
                },
            ),
            SubTest(
                description="April checkpoint",
                # Just check that new interest is now directly charged
                expected_balances_at_ts={
                    datetime(2019, 4, 11, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("8996.81"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1003.69"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("1003.69")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("1.64"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("1.55"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0.50"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("212.19")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check expire interest free periods workflow trigger is correct",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(months=2, day=22, seconds=1),
                        notification_type=EXPIRE_INTEREST_FREE_PERIODS_NOTIFICATION,
                        resource_id="Main account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                        notification_details={"account_id": "Main account"},
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
        self.run_test_scenario(test_scenario)

    @skip(
        "tests were passing in 'no_call' to simulation_test_scenario, which has since been removed"
        " so this is now throwing errors. Will have a closer look"
    )
    def test_interest_free_period_combined_scenario_3_int_acc_from_scod(self):
        """
        Combined scenario to test the general behaviour of interest free periods
        For this scenario we will check with both interest_free_period=False and True cases
        Verify behaviour when outstanding balance is paid off on PDD
        Match up the dates & numbers with what's provided in ACs for INC-2459
        Manual QA to verify the accrued values match up against what we see on the front end
        """

        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "annual_fee": "0",
            "credit_limit": "10000",
            "payment_due_period": "21",
            "transaction_references": dumps({"balance_transfer": ["REF1", "REF2"]}),
            "transaction_annual_percentage_rate": dumps(
                {"balance_transfer": {"REF1": "0.25", "REF2": "0.25"}}
            ),
            "transaction_base_interest_rates": dumps(
                {"balance_transfer": {"REF1": "0.022", "REF2": "0.022"}}
            ),
            "interest_free_expiry": dumps({}),
            "transaction_interest_free_expiry": dumps({}),
        }
        template_params = {
            **default_template_params,
            "transaction_types": default_template_update(
                "transaction_types",
                {
                    "purchase": {"charge_interest_from_transaction_date": "False"},
                    "balance_transfer": {"charge_interest_from_transaction_date": "True"},
                },
            ),
            "annual_percentage_rate": default_template_update(
                "annual_percentage_rate", {"purchase": "0.2"}
            ),
            "base_interest_rates": default_template_update(
                "base_interest_rates", {"purchase": "0.022"}
            ),
            "minimum_amount_due": "100",
            "minimum_percentage_due": dumps(
                {
                    "purchase": "0.01",
                    "cash_advance": "0.01",
                    "transfer": "0.01",
                    "balance_transfer": "0.01",
                    "interest": "1.0",
                    "fees": "1.0",
                }
            ),
            "accrue_interest_from_txn_day": "False",
        }

        # Alias address to shorter form for linter purposes
        PURCHASE_IFP = "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
        BALANCE_TRANSFER_REF1_IFP = "BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
        sub_tests = [
            SubTest(
                description="Balance Transfer REF1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                        event_datetime=datetime(2019, 1, 2, 12, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, 12, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("9000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 2, 12, 0, 0, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, 12, 0, 0, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("2000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("8000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Introduce interest free period 1 for both transactions",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 1, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                        interest_free_expiry=dumps({"purchase": "2019-01-25 23:59:59"}),
                    ),
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 1, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                        transaction_interest_free_expiry=dumps(
                            {"balance_transfer": {"REF1": "2019-01-25 23:59:59"}}
                        ),
                    ),
                ],
                # Balance transfer charged 8 days worth of interest at daily rate of 0.06
                expected_balances_at_ts={
                    datetime(2019, 1, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0.48"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Checkpoint before first interest free period expires",
                # No more interest accrued before first statement.
                expected_balances_at_ts={
                    datetime(2019, 1, 25, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0.48"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Checkpoint after SCOD 1",
                # Balance transfer charged 7 more days worth of interest at daily rate of 0.06
                # Charged interest moved to billed.
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("7999.10"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("2000.90"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("2000.90")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("0.90"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Introduce interest free period 2 for both transactions",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 2, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                        interest_free_expiry=dumps({"purchase": "2019-02-25 23:59:59"}),
                    ),
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 2, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                        transaction_interest_free_expiry=dumps(
                            {"balance_transfer": {"REF1": "2019-02-25 23:59:59"}}
                        ),
                    ),
                ],
                # Balance transfer charged 8 more days worth of interest at daily rate of 0.06
                # Purchase accrued 8 more days worth of uncharged interest at daily rate of 0.06
                expected_balances_at_ts={
                    datetime(2019, 2, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("0.90"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0.54"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0.54"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Checkpoint before PDD 1",
                # Both accrued 11 days of interest free period interest at daily rate of 0.06
                expected_balances_at_ts={
                    datetime(2019, 2, 21, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("0.90"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0.54"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0.66"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0.54"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0.66")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Pay outstanding balance",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2000.90",
                        event_datetime=datetime(2019, 2, 21, 13, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Checkpoint after PDD 1",
                # Everything zeroed
                expected_balances_at_ts={
                    datetime(2019, 2, 22, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("10000")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("0.54"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("0.54")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0.54"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Balance Transfer REF2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                        event_datetime=datetime(2019, 2, 26, 12, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 26, 12, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1000.54")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("9000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("1000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 2, 26, 12, 0, 0, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 26, 12, 0, 0, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("2000.54")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("8000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Checkpoint after SCOD 2",
                # Only balance transfer 2 charged interest
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("7999.28"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("2000.72"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("2000.72")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_BILLED"),
                                Decimal("0.18"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check expire interest free periods workflow trigger is correct",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(months=2, day=22, seconds=1),
                        notification_type=EXPIRE_INTEREST_FREE_PERIODS_NOTIFICATION,
                        resource_id="Main account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                        notification_details={"account_id": "Main account"},
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
        self.run_test_scenario(test_scenario)

    @skip(
        "tests were passing in 'no_call' to simulation_test_scenario, which has since been removed"
        " so this is now throwing errors. Will have a closer look"
    )
    def test_interest_free_period_combined_scenario_3_int_acc_from_txn(self):
        """
        Combined scenario to test the general behaviour of interest free periods
        For this scenario we will check with both interest_free_period=False and True cases
        Verify behaviour when outstanding balance is paid off on PDD
        Match up the dates & numbers with what's provided in ACs for INC-2459
        Manual QA to verify the accrued values match up against what we see on the front end
        """

        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "annual_fee": "0",
            "credit_limit": "10000",
            "payment_due_period": "21",
            "transaction_references": dumps({"balance_transfer": ["REF1", "REF2"]}),
            "transaction_annual_percentage_rate": dumps(
                {"balance_transfer": {"REF1": "0.25", "REF2": "0.25"}}
            ),
            "transaction_base_interest_rates": dumps(
                {"balance_transfer": {"REF1": "0.022", "REF2": "0.022"}}
            ),
            "interest_free_expiry": dumps({}),
            "transaction_interest_free_expiry": dumps({}),
        }
        template_params = {
            **default_template_params,
            "transaction_types": default_template_update(
                "transaction_types",
                {
                    "purchase": {"charge_interest_from_transaction_date": "False"},
                    "balance_transfer": {"charge_interest_from_transaction_date": "True"},
                },
            ),
            "annual_percentage_rate": default_template_update(
                "annual_percentage_rate", {"purchase": "0.2"}
            ),
            "base_interest_rates": default_template_update(
                "base_interest_rates", {"purchase": "0.022"}
            ),
            "minimum_amount_due": "100",
            "minimum_percentage_due": dumps(
                {
                    "purchase": "0.01",
                    "cash_advance": "0.01",
                    "transfer": "0.01",
                    "balance_transfer": "0.01",
                    "interest": "1.0",
                    "fees": "1.0",
                }
            ),
        }

        # Alias address to shorter form for linter purposes
        PURCHASE_IFP = "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
        BALANCE_TRANSFER_REF1_IFP = "BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"

        sub_tests = [
            SubTest(
                description="Balance Transfer REF1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                        event_datetime=datetime(2019, 1, 2, 12, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, 12, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("9000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 2, 12, 0, 0, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, 12, 0, 0, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("2000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("8000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Introduce interest free period 1 for both transactions",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 1, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                        interest_free_expiry=dumps({"purchase": "2019-01-25 23:59:59"}),
                    ),
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 1, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                        transaction_interest_free_expiry=dumps(
                            {"balance_transfer": {"REF1": "2019-01-25 23:59:59"}}
                        ),
                    ),
                ],
                # Balance transfer charged 8 days worth of interest at daily rate of 0.06
                # Purchase accrued 8 days worth of interest at daily rate of 0.06
                expected_balances_at_ts={
                    datetime(2019, 1, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0.48"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0.48"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Checkpoint before first interest free period expires",
                # No more interest accrued/charged before first statement.
                expected_balances_at_ts={
                    datetime(2019, 1, 25, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0.48"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0.48"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Checkpoint after SCOD 1",
                # Balance transfer charged 7 more days worth of interest at daily rate of 0.06
                # Purchase accrued 7 more days worth of interest at daily rate of 0.06
                # Charged interest moved to billed.
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("7999.10"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("2000.90"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("2000.90")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("0.90"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0.90"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Introduce interest free period 2 for both transactions",
                events=[
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 2, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                        interest_free_expiry=dumps({"purchase": "2019-02-25 23:59:59"}),
                    ),
                    create_instance_parameter_change_event(
                        account_id="Main account",
                        timestamp=datetime(2019, 2, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                        transaction_interest_free_expiry=dumps(
                            {"balance_transfer": {"REF1": "2019-02-25 23:59:59"}}
                        ),
                    ),
                ],
                # Balance transfer charged 8 more days worth of interest at daily rate of 0.06
                # Purchase accrued 8 more days worth of uncharged interest at daily rate of 0.06
                expected_balances_at_ts={
                    datetime(2019, 2, 10, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("0.90"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0.54"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("1.44"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Checkpoint before PDD 1",
                # Both accrued 11 days of interest free period interest at daily rate of 0.06
                expected_balances_at_ts={
                    datetime(2019, 2, 21, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("0.90"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0.54"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0.66"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("1.44"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0.66")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Pay outstanding balance",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2000.90",
                        event_datetime=datetime(2019, 2, 21, 13, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Checkpoint after PDD 1",
                # Everything zeroed
                expected_balances_at_ts={
                    datetime(2019, 2, 22, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("10000")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("0.54"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("0.54")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0.54"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Balance Transfer REF2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                        event_datetime=datetime(2019, 2, 26, 12, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 26, 12, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1000.54")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("9000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("1000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 2, 26, 12, 0, 0, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 26, 12, 0, 0, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("2000.54")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("8000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Checkpoint after SCOD 2",
                # Only balance transfer 2 charged interest
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("7999.28"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("2000.72"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("2000.72")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_BILLED"),
                                Decimal("0.18"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0.18"),
                            ),
                            (BalanceDimensions(PURCHASE_IFP), Decimal("0")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check expire interest free periods workflow trigger is correct",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(months=2, day=22, seconds=1),
                        notification_type=EXPIRE_INTEREST_FREE_PERIODS_NOTIFICATION,
                        resource_id="Main account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                        notification_details={"account_id": "Main account"},
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
        self.run_test_scenario(test_scenario)

    def test_charge_both_uncharged_addresses_when_revolver_starts(self):
        """
        Make 2 purchases, before and after SCOD.
        Let account go into revolver on PDD.
        See that both PRE_SCOD and POST_SCOD addresses are charged
        """
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 22, 23, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "transaction_references": dumps({"balance_transfer": ["REF1", "REF2"]}),
            "transaction_annual_percentage_rate": dumps(
                {"balance_transfer": {"REF1": "0.24", "REF2": "0.24"}}
            ),
            "transaction_base_interest_rates": dumps(
                {"balance_transfer": {"REF1": "0.24", "REF2": "0.24"}}
            ),
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_limits": dumps(
                {"balance_transfer": {"flat": "1500", "allowed_days_after_opening": "100"}}
            ),
            "late_repayment_fee": "0",
            "annual_fee": "0",
        }
        template_params = {
            **default_template_params,
            "transaction_types": default_template_update(
                "transaction_types",
                {
                    "purchase": {"charge_interest_from_transaction_date": "False"},
                    "balance_transfer": {"charge_interest_from_transaction_date": "False"},
                },
            ),
        }

        sub_tests = [
            SubTest(
                description="Purchase 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Balance Transfer REF1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Pre-SCOD 1 Checkpoint",
                expected_balances_at_ts={
                    datetime(2019, 1, 31, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("28000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("19.80"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("19.80"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("28000")),
                            (BalanceDimensions("STATEMENT_BALANCE"), Decimal("2000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("20.46"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("20.46"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=datetime(2019, 2, 2, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Balance Transfer REF2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                        event_datetime=datetime(2019, 2, 2, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Pre-PDD 1 Checkpoint",
                expected_balances_at_ts={
                    datetime(2019, 2, 21, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("27000")),
                            (BalanceDimensions("STATEMENT_BALANCE"), Decimal("2000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("500")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("500"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("6.27"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("33.66"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("33.66"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_PRE_SCOD_UNCHRGD),
                                Decimal("6.27"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 22, 23, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("27000")),
                            (BalanceDimensions("STATEMENT_BALANCE"), Decimal("2000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("500")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("500"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("40.92"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("34.32"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("6.60"),
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

    def test_only_POST_SCOD_uncharged_address_cleared_when_balance_fully_repaid_before_PDD(
        self,
    ):
        """
        Make 2 purchases, before and after SCOD.
        Clear full oustandning balance before PDD
        See that only POST_SCOD address is cleared. PRE_SCOD address remains uncleared after PDD.
        """
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 22, 23, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "transaction_references": dumps({"balance_transfer": ["REF1", "REF2"]}),
            "transaction_annual_percentage_rate": dumps(
                {"balance_transfer": {"REF1": "0.24", "REF2": "0.24"}}
            ),
            "transaction_base_interest_rates": dumps(
                {"balance_transfer": {"REF1": "0.24", "REF2": "0.24"}}
            ),
            "credit_limit": "30000",
            "payment_due_period": "21",
            "transaction_type_limits": dumps(
                {"balance_transfer": {"flat": "1500", "allowed_days_after_opening": "100"}}
            ),
            "late_repayment_fee": "0",
            "annual_fee": "0",
        }
        template_params = {
            **default_template_params,
            "transaction_types": default_template_update(
                "transaction_types",
                {
                    "purchase": {"charge_interest_from_transaction_date": "False"},
                    "balance_transfer": {"charge_interest_from_transaction_date": "False"},
                },
            ),
        }

        sub_tests = [
            SubTest(
                description="Purchase 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Balance Transfer REF1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Pre-SCOD 1 Checkpoint",
                expected_balances_at_ts={
                    datetime(2019, 1, 31, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("28000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("19.80"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("19.80"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("28000")),
                            (BalanceDimensions("STATEMENT_BALANCE"), Decimal("2000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("20.46"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("20.46"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=datetime(2019, 2, 2, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Balance Transfer REF2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                        event_datetime=datetime(2019, 2, 2, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Full Outstanding repayment before PDD",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=datetime(2019, 2, 21, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 21, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("6.27"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("33.66"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("33.66"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_PRE_SCOD_UNCHRGD),
                                Decimal("6.27"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 22, 23, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("29000")),
                            (BalanceDimensions("STATEMENT_BALANCE"), Decimal("2000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("500")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("6.6"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF1_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_PRE_SCOD_UNCHRGD),
                                Decimal("6.6"),
                            ),
                            (
                                BalanceDimensions(self.BAL_TRAN_REF2_INT_POST_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
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

    def test_interest_free_period_doesnt_charge_interest_in_repayment_holiday(self):
        """
        Set up interest free periods for purchases, cash advances, and balance transfers.
        Cash advances have charge_interest_from_transaction_date=True.
        Make 3000 balance transfer, spend 1000 GBP, and withdraw 500 GBP cash advance.
        Set repayment holiday flag to active after SCOD.
        Verify that the interest accrual behaviour doesn't change just because there is an active
        repayment holiday -- i.e. interest accrued in INTEREST_FREE_PERIOD_INTEREST_UNCHARGED.
        See that when PDD comes, the MAD balance is zeroed out despite no repayments were made.
        Verify uncharged interest (including interest free period uncharged interest) is zeroed out.
        """
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 26, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "transaction_references": dumps({"balance_transfer": ["REF1"]}),
            "transaction_annual_percentage_rate": dumps({"balance_transfer": {"REF1": "0.25"}}),
            "transaction_base_interest_rates": dumps({"balance_transfer": {"REF1": "0.22"}}),
            "credit_limit": "10000",
            "annual_fee": "0",
            "interest_free_expiry": dumps(
                {"purchase": "2019-12-31 12:00:00", "cash_advance": "2019-12-31 12:00:00"}
            ),
            "transaction_interest_free_expiry": dumps(
                {"balance_transfer": {"REF1": "2019-12-31 12:00:00"}}
            ),
        }
        template_params = {
            **default_template_params,
            "base_interest_rates": dumps(
                {"purchase": "0.25", "cash_advance": "0.36", "transfer": "0.36"}
            ),
            "annual_percentage_rate": dumps(
                {"transfer": "0.23", "purchase": "0.25", "cash_advance": "0.28"}
            ),
            "minimum_amount_due": "100",
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
            "mad_equal_to_zero_flags": dumps(["REPAYMENT_HOLIDAY"]),
            "overdue_amount_blocking_flags": dumps(["REPAYMENT_HOLIDAY"]),
            "billed_to_unpaid_transfer_blocking_flags": dumps(["REPAYMENT_HOLIDAY"]),
        }

        # Alias address to shorter form for linter purposes
        BALANCE_TRANSFER_REF1_IFP = "BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"

        sub_tests = [
            SubTest(
                description="Balance Transfer REF1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                        event_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("3000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("7000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("3000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("4000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("6000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="200",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 4, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 4, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("4210")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("5790")),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("10"),
                            ),
                        ]
                    }
                },
            ),
            # No interest is accrued before first SCOD, due to active interest free periods
            SubTest(
                description="SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("5790.00"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4210.00"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("4210.00")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("3000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("10"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Bank issues repayment holiday",
                events=[
                    create_flag_definition_event(
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        timestamp=datetime(2019, 2, 3, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_flag_event(
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        account_id="Main account",
                        timestamp=datetime(2019, 2, 3, tzinfo=ZoneInfo("UTC")),
                        expiry_timestamp=datetime(2019, 8, 3, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            # Balance transfer REF1 accrued 23 days worth of interest free period interest
            # at daily rate of 1.81
            # Cash advance accrued 23 days worth of interest free period interest
            # at daily rate of 0.2
            # Purchase accrued 23 days worth of interest free period interest
            # at daily rate of 0.68
            SubTest(
                description="Before PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 24, 20, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4210.00"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("41.63"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("4.60"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("15.64"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("100")),
                        ]
                    }
                },
            ),
            # # Check that all uncharged interest and mad is zeroed out
            # # Check that the BILLED items remain BILLED, not UNPAID, due to repayment holiday
            SubTest(
                description="After PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 25, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4210"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(BALANCE_TRANSFER_REF1_IFP),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "CASH_ADVANCE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("0")),
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

    def test_accrue_interest_from_txn_day_unchanged_in_repayment_holiday_started_before_scod(
        self,
    ):
        """
        Cash Advance has charge_interest_from_transaction_date=True.
        Make 3000 balance transfer, spend 1000 GBP, and withdraw 500 GBP cash advance.
        Set repayment holiday flag to active before SCOD.
        Verify that the interest accrual behaviour doesn't change just because there is an active
        repayment holiday -- i.e. interest has been accrued in <txn_type>_UNCHARGED and then
        moved to <txn_type>_INTEREST_POST_SCOD_UNCHARGED at SCOD.
        See that when PDD comes, the MAD balance is zeroed out despite no repayments were made.
        Verify uncharged interest has been charged.
        """

        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 26, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "transaction_references": dumps({"balance_transfer": ["REF1"]}),
            "transaction_annual_percentage_rate": dumps({"balance_transfer": {"REF1": "0.25"}}),
            "transaction_base_interest_rates": dumps({"balance_transfer": {"REF1": "0.22"}}),
            "credit_limit": "10000",
            "annual_fee": "0",
        }
        template_params = {
            **default_template_params,
            "base_interest_rates": dumps(
                {"purchase": "0.25", "cash_advance": "0.36", "transfer": "0.36"}
            ),
            "annual_percentage_rate": dumps(
                {"transfer": "0.23", "purchase": "0.25", "cash_advance": "0.28"}
            ),
            "minimum_amount_due": "100",
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
            "mad_equal_to_zero_flags": dumps(["REPAYMENT_HOLIDAY"]),
            "overdue_amount_blocking_flags": dumps(["REPAYMENT_HOLIDAY"]),
            "billed_to_unpaid_transfer_blocking_flags": dumps(["REPAYMENT_HOLIDAY"]),
        }

        sub_tests = [
            SubTest(
                description="Balance Transfer REF1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                        event_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("3000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("7000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("3000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000", event_datetime=datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC"))
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_CHARGED"),
                                Decimal("1000"),
                            )
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="200",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=datetime(2019, 1, 4, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 4, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
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
                description="Bank issues repayment holiday",
                events=[
                    create_flag_definition_event(
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        timestamp=datetime(2019, 1, 10, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_flag_event(
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        account_id="Main account",
                        timestamp=datetime(2019, 1, 10, tzinfo=ZoneInfo("UTC")),
                        expiry_timestamp=datetime(2019, 7, 10, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            # Balance transfer REF1 accrued 30 days worth of interest
            # at daily rate of 1.81
            # Cash advance accrued/charged 27 days worth of interest
            # at daily rate of 0.2
            # Purchase accrued 29 days worth of interest
            # at daily rate of 0.68
            SubTest(
                description="Before SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 1, 31, 23, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("5790.00"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4215.40"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("4215.40")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions(
                                    "BALANCE_TRANSFER_REF1_INTEREST_PRE_SCOD_UNCHARGED"
                                ),
                                Decimal("54.30"),
                            ),
                            (
                                BalanceDimensions(
                                    "BALANCE_TRANSFER_REF1_INTEREST_POST_SCOD_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("5.40"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("10"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_PRE_SCOD_UNCHARGED"),
                                Decimal("19.72"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_POST_SCOD_UNCHARGED"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            # All PRE_SCOD uncharged interest address balances successfully transfered
            # to POST_SCOD uncharged interest address balances
            SubTest(
                description="After SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("5784.40"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4215.60"),
                            ),
                            (BalanceDimensions("DEFAULT"), Decimal("4215.60")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions(
                                    "BALANCE_TRANSFER_REF1_INTEREST_PRE_SCOD_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "BALANCE_TRANSFER_REF1_INTEREST_POST_SCOD_UNCHARGED"
                                ),
                                Decimal("56.11"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("5.60"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("10"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_PRE_SCOD_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_POST_SCOD_UNCHARGED"),
                                Decimal("20.40"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("0")),
                        ]
                    }
                },
            ),
            # make another purchase
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500", event_datetime=datetime(2019, 2, 2, tzinfo=ZoneInfo("UTC"))
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_CHARGED"),
                                Decimal("500"),
                            )
                        ]
                    }
                },
            ),
            # Purchase accrued 22 days worth of interest
            # at daily rate of 0.34 in PRE_SCOD address
            SubTest(
                description="Before PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 24, 20, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4720.20"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "BALANCE_TRANSFER_REF1_INTEREST_PRE_SCOD_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "BALANCE_TRANSFER_REF1_INTEREST_POST_SCOD_UNCHARGED"
                                ),
                                Decimal("97.74"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("5.60"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("500")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_PRE_SCOD_UNCHARGED"),
                                Decimal("7.48"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_POST_SCOD_UNCHARGED"),
                                Decimal("36.04"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("0")),
                        ]
                    }
                },
            ),
            # Check that all uncharged interest is correctly charged when going in revolver
            # Check that the BILLED items remain BILLED, not UNPAID, due to repayment holiday
            SubTest(
                description="After PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 25, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4864.49"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("99.55"),
                            ),
                            (
                                BalanceDimensions(
                                    "BALANCE_TRANSFER_REF1_INTEREST_PRE_SCOD_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "BALANCE_TRANSFER_REF1_INTEREST_POST_SCOD_UNCHARGED"
                                ),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("200")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("4.80"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("44.54"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_PRE_SCOD_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_POST_SCOD_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("0")),
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
