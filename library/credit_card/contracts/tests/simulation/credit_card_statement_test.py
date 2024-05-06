# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
from decimal import Decimal
from json import dumps
from dateutil.relativedelta import relativedelta as timedelta
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.contracts.simulation.utils import (
    SimulationTestCase,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_outbound_hard_settlement_instruction,
    create_inbound_hard_settlement_instruction,
    create_outbound_authorisation_instruction,
    create_flag_event,
    create_flag_definition_event,
    create_settlement_event,
)
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    SimulationTestScenario,
    SubTest,
    ContractConfig,
    AccountConfig,
    ExpectedWorkflow,
)
from library.credit_card.contracts.tests.utils.simulation.lending import (
    DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS,
    DEFAULT_CREDIT_CARD_INSTANCE_PARAMS,
    default_template_update,
)
from library.credit_card.contracts.tests.utils.simulation.common import offset_datetime


CONTRACT_FILE = "library/credit_card/contracts/credit_card.py"
ASSET_CONTRACT_FILE = "internal_accounts/testing_internal_asset_account_contract.py"
LIABILITY_CONTRACT_FILE = "internal_accounts/testing_internal_liability_account_contract.py"
CONTRACT_FILES = [CONTRACT_FILE, ASSET_CONTRACT_FILE, LIABILITY_CONTRACT_FILE]
DEFAULT_DENOM = "GBP"
EXPIRE_INTEREST_FREE_PERIODS_WORKFLOW = "CREDIT_CARD_EXPIRE_INTEREST_FREE_PERIODS"
PUBLISH_STATEMENT_DATA_WORKFLOW = "CREDIT_CARD_PUBLISH_STATEMENT_DATA"


class CreditCardStatementTest(SimulationTestCase):
    """
    Tests of statements, MAD, repayment and PDD
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

    def _assert_statement_correct(
        self,
        scod_workflow,
        current_payment_due_date,
        current_statement_balance,
        start_of_statement_period,
        end_of_statement_period,
        minimum_amount_due,
        next_payment_due_date,
        next_statement_cut_off,
        account_id="Main account",
    ):
        """
        :param self:
        :param scod_workflow: Dict[str, Any], the workflow object from the simulation results
        :param account_id: str, the account id
        :param current_payment_due_date: str, the current OFFSET timezone payment due date in
         YYYY-MM-DD format
        :param current_statement_balance: str, the current statement balance
        :param start_of_statement_period: str, the current OFFSET timezone statement start date
         in YYYY-MM-DD
         format
        :param end_of_statement_period:str, the current OFFSET timezone statement cut-off date
         in YYYY-MM-DD
         format
        :param minimum_amount_due: str, the minimum amount due for the current statement
        :param next_statement_cut_off: str, the next OFFSET timezone statement cut-off date
         in YYYY-MM-DD format
        :return: None
        """

        context = scod_workflow[1]["context"]
        self.assertEqual(context["account_id"], account_id)
        self.assertEqual(context["current_payment_due_date"], current_payment_due_date)
        self.assertEqual(context["current_statement_balance"], current_statement_balance)
        self.assertEqual(context["start_of_statement_period"], start_of_statement_period)
        self.assertEqual(context["end_of_statement_period"], end_of_statement_period)
        self.assertEqual(context["minimum_amount_due"], minimum_amount_due)
        self.assertEqual(context["next_payment_due_date"], next_payment_due_date)
        self.assertEqual(context["next_statement_cut_off"], next_statement_cut_off)

    def test_int_billed_incl_accr_from_day_after_prev_scod_until_scod_incl_int_acc_from_scod(
        self,
    ):
        """
        Interest on a transactor account is accrued on a purchase from day after SCOD until PDD
        (inclusive).
        Late repayment is made
        Account continues to accrue until SCOD (inclusive) as account is revolver
            - SCOD1: 2019-1-31, PDD: 2019-2-24, SCOD2: 2019-2-28
            - Expected interest charged at PDD = 24 * rnd(2000 * 0.24/365,2) = 31.68
            - Expected interest billed at SCOD2 = above + 4 * rnd(100 * 0.24/365, 2) = 31.96
        """
        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 3, 1, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["payment_due_period"] = "24"
        instance_params["credit_limit"] = "30000"
        instance_params["overlimit"] = "3000"

        template_params["accrue_interest_from_txn_day"] = "False"

        sub_tests = [
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000", event_datetime=offset_datetime(2019, 1, 10)
                    )
                ],
            ),
            SubTest(
                description="Day after SCOD 1",
                # this accrual would be 1.31507 if rounding to 5dp
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 2, 1): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("1.32"),
                            )
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay after PDD",
                # This repayment will not cover the outstanding balance so accruals continue
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2000", event_datetime=offset_datetime(2019, 2, 25, 1)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 25, 1): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("31.68"),
                            )
                        ]
                    }
                },
            ),
            SubTest(
                description="Day after SCOD 2",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 1): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("31.96"),
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

    def test_int_billed_incl_accr_from_day_after_prev_scod_until_scod_incl_int_acc_from_txn(
        self,
    ):
        """
        Interest on a transactor account is accrued on a purchase from day after SCOD until PDD
        (inclusive).
        Late repayment is made
        Account continues to accrue until SCOD (inclusive) as account is revolver
            - SCOD1: 2019-1-31, PDD: 2019-2-24, SCOD2: 2019-2-28
            - Expected interest charged at PDD = 24 * rnd(2000 * 0.24/365,2) = 31.68
            - Expected interest billed at SCOD2 = above + 4 * rnd(100 * 0.24/365, 2) = 31.96
        """
        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 3, 1, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["payment_due_period"] = "24"
        instance_params["credit_limit"] = "30000"
        instance_params["overlimit"] = "3000"

        sub_tests = [
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000", event_datetime=offset_datetime(2019, 1, 10)
                    )
                ],
            ),
            SubTest(
                description="Day after SCOD 1",
                # this accrual would be 1.31507 if rounding to 5dp
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 2, 1): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_PRE_SCOD_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_POST_SCOD_UNCHARGED"),
                                Decimal("30.36"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay after PDD",
                # This repayment will not cover the outstanding balance so accruals continue
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2000", event_datetime=offset_datetime(2019, 2, 25, 1)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 25, 1): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("60.72"),
                            )
                        ]
                    }
                },
            ),
            SubTest(
                description="Day after SCOD 2",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 1): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("61.00"),
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

    def test_statement_workflow_context_is_accurate(self):
        """
        Generate a quarter's worth of SCOD workflows and check the information is accurate
        """

        start = offset_datetime(year=2018, month=1, day=1)
        end = offset_datetime(year=2018, month=4, day=1, hour=1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        date_1 = start + timedelta(months=1, days=7)
        date_2 = start + timedelta(months=2, days=7)
        date_3 = start + timedelta(months=3, days=7)

        sub_tests = [
            SubTest(
                description="Check number of SCOD workflows triggered is correct",
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id=PUBLISH_STATEMENT_DATA_WORKFLOW,
                        run_times=[date_1, date_2, date_3],
                        # Check that the context of the smart contract as of SCOD
                        # was correctly added to the workflow context for each month
                        contexts=[
                            {
                                "account_id": "Main account",
                                "current_payment_due_date": "2018-02-24",
                                "minimum_amount_due": "100.00",
                                "start_of_statement_period": "2018-01-01",
                                "end_of_statement_period": "2018-01-31",
                                "current_statement_balance": "100.00",
                                "next_payment_due_date": "2018-03-24",
                                "next_statement_cut_off": "2018-02-28",
                                "is_final": "False",
                            },
                            {
                                "account_id": "Main account",
                                "current_payment_due_date": "2018-03-24",
                                "minimum_amount_due": "200.00",
                                "start_of_statement_period": "2018-02-01",
                                "end_of_statement_period": "2018-02-28",
                                "current_statement_balance": "200.00",
                                "next_payment_due_date": "2018-04-24",
                                "next_statement_cut_off": "2018-03-31",
                                "is_final": "False",
                            },
                            {
                                "account_id": "Main account",
                                "current_payment_due_date": "2018-04-24",
                                "minimum_amount_due": "300.00",
                                "start_of_statement_period": "2018-03-01",
                                "end_of_statement_period": "2018-03-31",
                                "current_statement_balance": "300.00",
                                "next_payment_due_date": "2018-05-24",
                                "next_statement_cut_off": "2018-04-30",
                                "is_final": "False",
                            },
                        ],
                        count=3,
                    )
                ],
            )
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_auth_settlement_before_and_across_scod(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 3, 3, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["annual_fee"] = "0"
        instance_params["payment_due_period"] = "21"
        instance_params["late_repayment_fee"] = "0"

        template_params["accrue_interest_from_txn_day"] = "False"

        sub_tests = [
            SubTest(
                description="Auth A",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="1000",
                        client_transaction_id="A",
                        event_datetime=offset_datetime(2019, 1, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("29000"),
                            ),
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
                        event_datetime=offset_datetime(2019, 1, 3),
                        final=True,
                        client_transaction_id="A",
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 3): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("29000"),
                            ),
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
                description="Auth B",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="5000",
                        client_transaction_id="B",
                        event_datetime=offset_datetime(2019, 1, 30, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 30, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("24000"),
                            ),
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
                description="Settle B",
                events=[
                    create_settlement_event(
                        amount="5000",
                        event_datetime=offset_datetime(2019, 2, 3, 1),
                        final=True,
                        client_transaction_id="B",
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 3, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("24000"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("6000")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("6000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Auth C",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="2000",
                        client_transaction_id="C",
                        event_datetime=offset_datetime(2019, 2, 20, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 20, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("22000"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("6000")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("6000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay after PDD",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=offset_datetime(2019, 2, 22, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 22, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("22500"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("5500")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("5576.37"),
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
                        event_datetime=offset_datetime(2019, 2, 25, 1),
                        final=True,
                        client_transaction_id="C",
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 25, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("22500"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("7500")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("7587.23"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Scod 3",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("22393.05"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("7606.95"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("7606.95"),
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

    def test_outstanding_and_full_outstanding_updated_with_int_when_rev(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 4, 3, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["annual_fee"] = "0"
        instance_params["payment_due_period"] = "21"
        instance_params["late_repayment_fee"] = "0"

        template_params["accrue_interest_from_txn_day"] = "False"

        sub_tests = [
            SubTest(
                description="Purchase A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000", event_datetime=offset_datetime(2019, 1, 1)
                    )
                ],
            ),
            SubTest(
                description="Purchase B",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="399", event_datetime=offset_datetime(2019, 1, 3)
                    )
                ],
            ),
            SubTest(
                description="Purchase C",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="100", event_datetime=offset_datetime(2019, 1, 15)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 15): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("28501"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("1499")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1499"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase D",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="900", event_datetime=offset_datetime(2019, 1, 31)
                    )
                ],
            ),
            SubTest(
                description="SCOD 1",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("27601"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("2399")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("2399"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase E",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500", event_datetime=offset_datetime(2019, 2, 2)
                    )
                ],
            ),
            SubTest(
                description="Pre-PDD: no changes to balances",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 16): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("27101"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("2899")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("2899"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repayment A",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500", event_datetime=offset_datetime(2019, 2, 22, 1)
                    )
                ],
            ),
            SubTest(
                description="Purchase F",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000", event_datetime=offset_datetime(2019, 2, 27)
                    )
                ],
            ),
            SubTest(
                description="Purchase G",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000", event_datetime=offset_datetime(2019, 2, 28)
                    )
                ],
            ),
            SubTest(
                description="SCOD 2",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("24546.88"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("5453.12"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("5453.12"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase H",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="900",
                        event_datetime=offset_datetime(2019, 3, 2),
                    )
                ],
            ),
            SubTest(
                description="Revolver - Charged Interest updates full outstanding balance but not "
                "outstanding",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 3): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("23646.88"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("6353.12"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("6360.81"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase I",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000", event_datetime=offset_datetime(2019, 3, 15)
                    )
                ],
            ),
            SubTest(
                description="Revolver 2 - Charged Interest updates full outstanding balance but not"
                "outstanding",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 16): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("22646.88"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("7353.12"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("7415.29"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repayment B",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="200", event_datetime=offset_datetime(2019, 3, 22, 1)
                    )
                ],
            ),
            SubTest(
                description="Purchase J",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000", event_datetime=offset_datetime(2019, 3, 30, 1)
                    )
                ],
            ),
            SubTest(
                description="Purchase K",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500", event_datetime=offset_datetime(2019, 3, 31, 1)
                    )
                ],
            ),
            SubTest(
                description="SCOD 3",
                expected_balances_at_ts={
                    offset_datetime(2019, 4, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("19204.63"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("10795.37"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("10795.37"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase L",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="300",
                        event_datetime=offset_datetime(2019, 4, 2, 1),
                    )
                ],
            ),
            SubTest(
                description="Revolver 3 - Charged Interest updates full outstanding balance but not"
                "outstanding",
                expected_balances_at_ts={
                    offset_datetime(2019, 4, 3, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("18904.63"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("11095.37"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("11109.57"),
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

    def test_overdue_amounts_calculated_and_repaid_correctly_multi_purchase(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 6, 1, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.02",
                    "flat_fee": "100",
                }
            }
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "10000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"

        template_params["accrue_interest_from_txn_day"] = "False"

        sub_tests = [
            SubTest(
                description="Purchase 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=offset_datetime(2019, 1, 10, 1),
                    )
                ],
            ),
            SubTest(
                description="SCOD 1",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("27000"),
                            ),
                            (
                                BalanceDimensions(
                                    "STATEMENT_BALANCE",
                                ),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("3000"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("3000")),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("3000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1500", event_datetime=offset_datetime(2019, 2, 10, 1)
                    )
                ],
            ),
            SubTest(
                description="Partial Repayment 1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=offset_datetime(2019, 2, 22, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 22, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "STATEMENT_BALANCE",
                                ),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("25600"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4453.25"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("4400")),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("2900"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_CHARGED",
                                ),
                                Decimal("1500"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="SCOD 2",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("25526.52"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("73.48"),
                            ),
                            (
                                BalanceDimensions(
                                    "STATEMENT_BALANCE",
                                ),
                                Decimal("4473.48"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("217.48"),
                            ),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4473.48"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("4473.48"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("2900"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("1500"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase 3",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="300", event_datetime=offset_datetime(2019, 3, 10, 1)
                    )
                ],
            ),
            SubTest(
                description="Partial Repayment 2",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="50", event_datetime=offset_datetime(2019, 3, 22, 1)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 22, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("217.48"),
                            ),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                Decimal("50"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("117.48"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_2",
                                ),
                                Decimal("50"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("25276.52"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("23.48"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("63.09"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4786.57"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("4723.48"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("4400"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_CHARGED",
                                ),
                                Decimal("300"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="SCOD 3",
                expected_balances_at_ts={
                    offset_datetime(2019, 4, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("25182.53"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("23.48"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("93.99"),
                            ),
                            (
                                BalanceDimensions(
                                    "STATEMENT_BALANCE",
                                ),
                                Decimal("4817.47"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("117.48"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_2",
                                ),
                                Decimal("50"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("331.95"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4817.47"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("4817.47"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("4400"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("300"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase 4",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500", event_datetime=offset_datetime(2019, 4, 10, 1)
                    )
                ],
            ),
            SubTest(
                description="PDD 3",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100", event_datetime=offset_datetime(2019, 4, 22, 1)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 4, 22, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("331.95"),
                            ),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("164.47"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_2",
                                ),
                                Decimal("67.48"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_3",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("24782.53"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("17.47"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("68.85"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("5286.32"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("5217.47"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("4700"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_CHARGED",
                                ),
                                Decimal("500"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="SCOD 4",
                expected_balances_at_ts={
                    offset_datetime(2019, 5, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("401.05"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("164.47"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_2",
                                ),
                                Decimal("67.48"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_3",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("24682.90"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("17.47"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("99.63"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("5317.1"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("5317.1"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("4700"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("500"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_CHARGED",
                                ),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase 4",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=offset_datetime(2019, 5, 10, 1),
                    )
                ],
            ),
            SubTest(
                description="PDD 4",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=offset_datetime(2019, 5, 22, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 5, 22, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("401.05"),
                            ),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("169.1"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_2",
                                ),
                                Decimal("131.95"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_3",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("23782.90"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("17.1"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("79.74"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("6296.84"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("6217.1"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("5200"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_CHARGED",
                                ),
                                Decimal("1000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="SCOD 5",
                expected_balances_at_ts={
                    offset_datetime(2019, 6, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("500.69"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("169.1"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_2",
                                ),
                                Decimal("131.95"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_3",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("23662.36"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("17.1"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("120.54"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("6337.64"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("6337.64"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("5200"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_CHARGED",
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

    def test_overdue_amounts_calc_and_repaid_correctly_single_purchase(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 5, 1, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.02",
                    "flat_fee": "100",
                }
            }
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "10000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"

        template_params["accrue_interest_from_txn_day"] = "False"

        sub_tests = [
            SubTest(
                description="Purchase 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000", event_datetime=offset_datetime(2019, 1, 10, 1)
                    )
                ],
            ),
            SubTest(
                description="SCOD 1",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("25000"),
                            ),
                            (
                                BalanceDimensions(
                                    "STATEMENT_BALANCE",
                                ),
                                Decimal("5000"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("5000"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("5000")),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("5000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="PDD 1",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 22, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "STATEMENT_BALANCE",
                                ),
                                Decimal("5000"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("25000"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("5069.09"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("5000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("69.09"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("5000"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_CHARGED",
                                ),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="SCOD 2",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("24907.88"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("92.12"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions(
                                    "STATEMENT_BALANCE",
                                ),
                                Decimal("5092.12"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("342.12"),
                            ),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("5092.12"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("5092.12"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("5000"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="PDD 2",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 22, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("342.12"),
                            ),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("142.12"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_2",
                                ),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("24907.88"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("92.12"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("69.09"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("5161.21"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("5092.12"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("5000"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="SCOD 3",
                expected_balances_at_ts={
                    offset_datetime(2019, 4, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("24805.89"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("92.12"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("101.99"),
                            ),
                            (
                                BalanceDimensions(
                                    "STATEMENT_BALANCE",
                                ),
                                Decimal("5194.11"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("142.12"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_2",
                                ),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("586.23"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("5194.11"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("5194.11"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("5000"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="PDD 3",
                expected_balances_at_ts={
                    offset_datetime(2019, 4, 23, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("586.23"),
                            ),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("244.11"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_2",
                                ),
                                Decimal("142.12"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_3",
                                ),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("24805.89"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("194.11"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("72.38"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("5266.49"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("5194.11"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("5000"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay after PDD 3",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=offset_datetime(2019, 4, 23, 2),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 4, 23, 2): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("586.23"),
                            ),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_2",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_3",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("25805.89"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("72.38"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4266.49"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("4194.11"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("4194.11"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="SCOD 4",
                expected_balances_at_ts={
                    offset_datetime(2019, 5, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_2",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_3",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("25711.43"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("94.46"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("4288.57"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("4288.57"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("4194.11"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
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

    def test_statement_balances(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 4, 1, 0, 1, 0)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.02",
                    "flat_fee": "100",
                }
            }
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "6000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"

        template_params["minimum_percentage_due"] = dumps(
            {
                "purchase": "0",
                "cash_advance": "0.01",
                "transfer": "0.01",
                "balance_transfer": "0.0",
                "interest": "1.0",
                "fees": "1.0",
            }
        )
        template_params["minimum_amount_due"] = "200"
        template_params["accrue_interest_from_txn_day"] = "False"

        sub_tests = [
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10000",
                        client_transaction_id="1234",
                        event_datetime=offset_datetime(2019, 1, 3),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="10000",
                        event_datetime=offset_datetime(2019, 1, 3, 0, 0, 0, 1),
                        final=True,
                        client_transaction_id="1234",
                    )
                ],
            ),
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="2000",
                        client_transaction_id="2345",
                        event_datetime=offset_datetime(2019, 1, 5),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="2000",
                        event_datetime=offset_datetime(2019, 1, 5, 0, 0, 0, 1),
                        final=True,
                        client_transaction_id="2345",
                    )
                ],
            ),
            SubTest(
                description="Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="6000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 10),
                    )
                ],
            ),
            SubTest(
                description="Partially repay",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=offset_datetime(2019, 1, 10, 1),
                    )
                ],
            ),
            SubTest(
                description="Check 1st statement accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("12771.54"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("17228.46"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("17228.46"),
                            ),
                            (
                                BalanceDimensions(
                                    "STATEMENT_BALANCE",
                                ),
                                Decimal("17228.46"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("12000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("5000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("108.46"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("120.00"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("278.46"),
                            ),
                            (
                                BalanceDimensions(
                                    "REVOLVER",
                                ),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partially repay",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=offset_datetime(2019, 2, 5),
                    )
                ],
            ),
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="5000",
                        client_transaction_id="3456",
                        event_datetime=offset_datetime(2019, 2, 10, 1),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="5000",
                        event_datetime=offset_datetime(2019, 2, 10, 2, 0, 0, 1),
                        final=True,
                        client_transaction_id="3456",
                    )
                ],
            ),
            SubTest(
                description="Partially repay",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=offset_datetime(2019, 2, 22, 1),
                    )
                ],
            ),
            SubTest(
                description="Check 2nd statement accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("9895.50"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("20104.50"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("20104.50"),
                            ),
                            (
                                BalanceDimensions(
                                    "STATEMENT_BALANCE",
                                ),
                                Decimal("20104.500"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("12000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("2728.46"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("5000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("283.43"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("92.61"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("403.32"),
                            ),
                            (
                                BalanceDimensions(
                                    "REVOLVER",
                                ),
                                Decimal("-1"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 3, 10),
                    )
                ],
            ),
            SubTest(
                description="Partially repay Overlimit and Cash Advance",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=offset_datetime(2019, 3, 22, 1),
                    )
                ],
            ),
            SubTest(
                description="Check 3rd statement accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 4, 1, 0, 1, 0): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("9349.95"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("20650.05"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("20650.05"),
                            ),
                            (
                                BalanceDimensions(
                                    "STATEMENT_BALANCE",
                                ),
                                Decimal("20650.05"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("17000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("2104.50"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("346.58"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("98.97"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("100.0"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("576.60"),
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

    def test_statement_balances_int_acc_from_txn(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 4, 1, 0, 1, 0)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.02",
                    "flat_fee": "100",
                }
            }
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "6000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"

        template_params["minimum_percentage_due"] = dumps(
            {
                "purchase": "0",
                "cash_advance": "0.01",
                "transfer": "0.01",
                "balance_transfer": "0.0",
                "interest": "1.0",
                "fees": "1.0",
            }
        )
        template_params["minimum_amount_due"] = "200"

        sub_tests = [
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10000",
                        client_transaction_id="1234",
                        event_datetime=offset_datetime(2019, 1, 3),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="10000",
                        event_datetime=offset_datetime(2019, 1, 3, 0, 0, 0, 1),
                        final=True,
                        client_transaction_id="1234",
                    )
                ],
            ),
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="2000",
                        client_transaction_id="2345",
                        event_datetime=offset_datetime(2019, 1, 5),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="2000",
                        event_datetime=offset_datetime(2019, 1, 5, 0, 0, 0, 1),
                        final=True,
                        client_transaction_id="2345",
                    )
                ],
            ),
            SubTest(
                description="Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="6000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 10),
                    )
                ],
            ),
            SubTest(
                description="Partially repay",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=offset_datetime(2019, 1, 10, 1),
                    )
                ],
            ),
            SubTest(
                description="Check 1st statement accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("12771.54"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("17228.46"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("17228.46"),
                            ),
                            (
                                BalanceDimensions(
                                    "STATEMENT_BALANCE",
                                ),
                                Decimal("17228.46"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("12000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("5000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("108.46"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("120.00"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("278.46"),
                            ),
                            (
                                BalanceDimensions(
                                    "REVOLVER",
                                ),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partially repay",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=offset_datetime(2019, 2, 5),
                    )
                ],
            ),
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="5000",
                        client_transaction_id="3456",
                        event_datetime=offset_datetime(2019, 2, 10, 1),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="5000",
                        event_datetime=offset_datetime(2019, 2, 10, 2),
                        final=True,
                        client_transaction_id="3456",
                    )
                ],
            ),
            SubTest(
                description="Partially repay",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=offset_datetime(2019, 2, 22, 1),
                    )
                ],
            ),
            SubTest(
                description="Check 2nd statement accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("9669.31"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("20330.69"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("20330.69"),
                            ),
                            (
                                BalanceDimensions(
                                    "STATEMENT_BALANCE",
                                ),
                                Decimal("20330.69"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("12000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("2728.46"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("5000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("509.62"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("92.61"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("629.51"),
                            ),
                            (
                                BalanceDimensions(
                                    "REVOLVER",
                                ),
                                Decimal("-1"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 3, 10),
                        target_account_id="Main account",
                        internal_account_id="Dummy account",
                    )
                ],
            ),
            SubTest(
                description="Partially repay Overlimit and Cash Advance",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=offset_datetime(2019, 3, 22, 1),
                    )
                ],
            ),
            SubTest(
                description="Check 3rd statement accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 4, 1, 0, 1, 0): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("9121.46"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("20878.54"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("20878.54"),
                            ),
                            (
                                BalanceDimensions(
                                    "STATEMENT_BALANCE",
                                ),
                                Decimal("20878.54"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("17000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("2330.69"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("346.58"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("101.27"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("100.0"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("581.16"),
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

    def test_mad_lt_minimum(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 1, 0, 1, 0)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.02",
                    "flat_fee": "100",
                }
            }
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "6000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"

        template_params["minimum_percentage_due"] = dumps(
            {
                "purchase": "0.01",
                "cash_advance": "0",
                "balance_transfer": "0",
                "transfer": "0",
                "interest": "1.0",
                "fees": "1.0",
            }
        )
        template_params["minimum_amount_due"] = "200"

        sub_tests = [
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="1000",
                        client_transaction_id="1234",
                        event_datetime=offset_datetime(2019, 1, 1),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="1000",
                        event_datetime=offset_datetime(2019, 1, 1, 0, 0, 0, 1),
                        final=True,
                        client_transaction_id="1234",
                    )
                ],
            ),
            SubTest(
                description="Check MAD accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 0, 1, 0): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("200"),
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

    def test_mad_gt_minimum(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 1, 0, 1, 0)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.02",
                    "flat_fee": "100",
                }
            }
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "6000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"

        template_params["minimum_percentage_due"] = dumps(
            {
                "purchase": "0.01",
                "cash_advance": "0",
                "balance_transfer": "0",
                "transfer": "0",
                "interest": "1.0",
                "fees": "1.0",
            }
        )
        template_params["minimum_amount_due"] = "200"

        sub_tests = [
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="25000",
                        client_transaction_id="1234",
                        event_datetime=offset_datetime(2019, 1, 1),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="25000",
                        event_datetime=offset_datetime(2019, 1, 1, 0, 0, 0, 1),
                        final=True,
                        client_transaction_id="1234",
                    )
                ],
            ),
            SubTest(
                description="Check MAD accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 0, 1, 0): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("250"),
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

    def test_mad_annual_fee(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 1, 0, 1, 0)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.02",
                    "flat_fee": "100",
                }
            }
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "6000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "500"

        template_params["minimum_percentage_due"] = dumps(
            {
                "purchase": "0.01",
                "cash_advance": "0",
                "balance_transfer": "0",
                "transfer": "0",
                "interest": "1.0",
                "fees": "1.0",
            }
        )
        template_params["minimum_amount_due"] = "200"

        sub_tests = [
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10000",
                        client_transaction_id="1234",
                        event_datetime=offset_datetime(2019, 1, 1),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="10000",
                        event_datetime=offset_datetime(2019, 1, 1, 0, 0, 0, 1),
                        final=True,
                        client_transaction_id="1234",
                    )
                ],
            ),
            SubTest(
                description="Check MAD accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 0, 1, 0): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("600"),
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

    def test_mad_when_overlimit(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 3, 1, 0, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.02",
                    "flat_fee": "100",
                }
            }
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "6000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["overlimit"] = "3000"
        instance_params["overlimit_fee"] = "180"
        instance_params["annual_fee"] = "500"

        template_params["minimum_percentage_due"] = dumps(
            {
                "purchase": "0.01",
                "cash_advance": "0",
                "balance_transfer": "0",
                "transfer": "0",
                "interest": "1.0",
                "fees": "1.0",
            }
        )
        template_params["minimum_amount_due"] = "200"
        template_params["accrue_interest_from_txn_day"] = "False"

        sub_tests = [
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10000",
                        client_transaction_id="1",
                        event_datetime=offset_datetime(2019, 1, 1),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="10000",
                        event_datetime=offset_datetime(2019, 1, 1, 0, 0, 0, 1),
                        final=True,
                        client_transaction_id="1",
                    )
                ],
            ),
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="22000",
                        client_transaction_id="2",
                        event_datetime=offset_datetime(2019, 1, 2),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="22000",
                        event_datetime=offset_datetime(2019, 1, 2, 0, 0, 0, 1),
                        final=True,
                        client_transaction_id="2",
                    )
                ],
            ),
            SubTest(
                description="Check 1st Statement",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 0, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("-2680"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("32000"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("32680"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("500")),
                            (
                                BalanceDimensions("OVERLIMIT_FEES_BILLED"),
                                Decimal("180"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="7000", event_datetime=offset_datetime(2019, 2, 22, 1)
                    )
                ],
            ),
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="3000",
                        client_transaction_id="3",
                        event_datetime=offset_datetime(2019, 2, 28, 1),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="3000",
                        event_datetime=offset_datetime(2019, 2, 28, 2, 0, 0, 1),
                        final=True,
                        client_transaction_id="3",
                    )
                ],
            ),
            SubTest(
                description="Check 2nd Statement",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 1, 0, 1): {
                        "Main account": [
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("29242.04"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("25680"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("562.04"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("3000"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("848.84"),
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

    def test_mad_with_overdue(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 3, 1, 0, 1, 0)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.02",
                    "flat_fee": "100",
                }
            }
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "15000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["overlimit"] = "3000"
        instance_params["overlimit_fee"] = "180"
        instance_params["annual_fee"] = "500"

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
        template_params["accrue_interest_from_txn_day"] = "False"

        sub_tests = [
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10000",
                        client_transaction_id="1",
                        event_datetime=offset_datetime(2019, 1, 1),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="10000",
                        event_datetime=offset_datetime(2019, 1, 1, 0, 0, 0, 1),
                        final=True,
                        client_transaction_id="1",
                    )
                ],
            ),
            SubTest(
                description="Check 1st MAD accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 0, 1, 0): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("600"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("500")),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("10000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="550",
                        event_datetime=offset_datetime(2019, 2, 22, 1),
                    )
                ],
            ),
            SubTest(
                description="Check 2nd MAD accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 1, 0, 1, 0): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("333.46"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("50"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("9950"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("183.96"),
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

    def test_mad_overdue_cash_advance(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 4, 1, 0, 1, 0)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "21"
        instance_params["transaction_type_fees"] = dumps(
            {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.02",
                    "flat_fee": "100",
                }
            }
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "7000"}})
        instance_params["late_repayment_fee"] = "200"
        instance_params["overlimit"] = "3000"
        instance_params["overlimit_fee"] = "180"
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
        template_params["accrue_interest_from_txn_day"] = "False"

        sub_tests = [
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10000",
                        client_transaction_id="1",
                        event_datetime=offset_datetime(2019, 1, 1),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="10000",
                        event_datetime=offset_datetime(2019, 1, 1, 0, 0, 0, 1),
                        final=True,
                        client_transaction_id="1",
                    )
                ],
            ),
            SubTest(
                description="Initial Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="6000.3",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 15, 1),
                    )
                ],
            ),
            SubTest(
                description="Check MAD accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 0, 1, 0): {
                        "Main account": [
                            # MAD: 10000*0.01 + 6000.3*0.01 + 100.64 + 120.01
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("380.65"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("10000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_BILLED"),
                                Decimal("6000.3"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("100.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("120.01"),
                            ),
                            (
                                BalanceDimensions(
                                    "DEFAULT",
                                ),
                                Decimal("16220.95"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("16220.95"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("13779.05"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=offset_datetime(2019, 2, 22, 1),
                    )
                ],
            ),
            SubTest(
                description="Check MAD2 accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 1, 0, 1, 0): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("1011.3"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("230.65"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("10000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("6000.3"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("70.65"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("184.24"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("165.76"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_BILLED"),
                                Decimal("200.00"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="800", event_datetime=offset_datetime(2019, 3, 22, 1)
                    )
                ],
            ),
            SubTest(
                description="Check MAD accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 4, 1, 0, 1, 0): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("955.21"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("211.3"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("10000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("5820.95"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("203.98"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("181.72"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_BILLED"),
                                Decimal("200.00"),
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

    def test_purchase_with_annual_fee_plus_min_mad(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 1, 0, 1, 0)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "22"
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "500"

        template_params["minimum_percentage_due"] = dumps(
            {
                "purchase": "0.01",
                "cash_advance": "0",
                "balance_transfer": "0",
                "transfer": "0",
                "interest": "1.0",
                "fees": "1.0",
            }
        )
        template_params["minimum_amount_due"] = "200"

        sub_tests = [
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="20000",
                        client_transaction_id="1234",
                        event_datetime=offset_datetime(2019, 1, 1),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="20000",
                        event_datetime=offset_datetime(2019, 1, 1, 0, 0, 0, 1),
                        final=True,
                        client_transaction_id="1234",
                    )
                ],
            ),
            SubTest(
                description="Check MAD accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 0, 1, 0): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("700"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("20500"),
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

    def test_mad_outstanding_exceeds_overlimit(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 6, 1, 0, 1, 0)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "22"
        instance_params["overlimit"] = "3000"
        instance_params["overlimit_fee"] = "0"
        instance_params["late_repayment_fee"] = "200"
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
        template_params["accrue_interest_from_txn_day"] = "False"

        sub_tests = [
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="5000",
                        client_transaction_id="1",
                        event_datetime=offset_datetime(2019, 1, 5),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="5000",
                        event_datetime=offset_datetime(2019, 1, 5, 0, 0, 0, 1),
                        final=True,
                        client_transaction_id="1",
                    )
                ],
            ),
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10000",
                        client_transaction_id="2",
                        event_datetime=offset_datetime(2019, 1, 10),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="10000",
                        event_datetime=offset_datetime(2019, 1, 10, 0, 0, 0, 1),
                        final=True,
                        client_transaction_id="2",
                    )
                ],
            ),
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="18000",
                        client_transaction_id="3",
                        event_datetime=offset_datetime(2019, 1, 20, 1),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="18000",
                        event_datetime=offset_datetime(2019, 1, 20, 2, 0, 0, 1),
                        final=True,
                        client_transaction_id="3",
                    )
                ],
            ),
            SubTest(
                description="Check 1st MAD accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 0, 1, 0): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("3330"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("33000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500", event_datetime=offset_datetime(2019, 2, 22, 1)
                    )
                ],
            ),
            SubTest(
                description="Check 2nd MAD accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 1, 0, 1, 0): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("3960.29"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("32500"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("605.29"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_BILLED"),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("2830"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3000", event_datetime=offset_datetime(2019, 3, 22, 1)
                    )
                ],
            ),
            SubTest(
                description="Check 3rd MAD accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 4, 1, 0, 1, 0): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("2111.41"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("30305.29"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("648.07"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_BILLED"),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("960.29"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_2",
                                ),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000", event_datetime=offset_datetime(2019, 4, 22, 1)
                    )
                ],
            ),
            SubTest(
                description="Check 4th MAD accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 5, 1, 0, 1, 0): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("2209.94"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("30153.36"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("597"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_BILLED"),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("1111.41"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_2",
                                ),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="300", event_datetime=offset_datetime(2019, 5, 21, 1)
                    )
                ],
            ),
            SubTest(
                description="Partial repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="700", event_datetime=offset_datetime(2019, 5, 22, 1)
                    )
                ],
            ),
            SubTest(
                description="Check 5th MAD accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 6, 1, 0, 1, 0): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("2322.77"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("29950.36"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("613.33"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_BILLED"),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("1098.53"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_2",
                                ),
                                Decimal("111.41"),
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

    def test_mad_aging_overdue(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 6, 1, 0, 1, 0)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "22"
        instance_params["overlimit"] = "3000"
        instance_params["overlimit_fee"] = "0"
        instance_params["transaction_type_fees"] = dumps(
            {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.02",
                    "flat_fee": "100",
                }
            }
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "6000"}})
        instance_params["late_repayment_fee"] = "200"
        instance_params["annual_fee"] = "0"

        template_params["minimum_percentage_due"] = dumps(
            {
                "purchase": "0.01",
                "cash_advance": "0",
                "balance_transfer": "0",
                "transfer": "0",
                "interest": "1.0",
                "fees": "1.0",
            }
        )
        template_params["minimum_amount_due"] = "200"
        template_params["accrue_interest_from_txn_day"] = "False"

        sub_tests = [
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="500",
                        client_transaction_id="1",
                        event_datetime=offset_datetime(2019, 1, 5),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="500",
                        event_datetime=offset_datetime(2019, 1, 5, 0, 0, 0, 1),
                        final=True,
                        client_transaction_id="1",
                    )
                ],
            ),
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="3000",
                        client_transaction_id="2",
                        event_datetime=offset_datetime(2019, 1, 10),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="3000",
                        event_datetime=offset_datetime(2019, 1, 10, 0, 0, 0, 1),
                        final=True,
                        client_transaction_id="2",
                    )
                ],
            ),
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="700",
                        client_transaction_id="3",
                        event_datetime=offset_datetime(2019, 1, 20),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="700",
                        event_datetime=offset_datetime(2019, 1, 20, 0, 0, 0, 1),
                        final=True,
                        client_transaction_id="3",
                    )
                ],
            ),
            SubTest(
                description="Check 1st MAD uses fixed minimum",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 0, 1, 0): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("4200"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="1000",
                        client_transaction_id="5",
                        event_datetime=offset_datetime(2019, 2, 5),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="1000",
                        event_datetime=offset_datetime(2019, 2, 5, 0, 0, 0, 1),
                        final=True,
                        client_transaction_id="5",
                    )
                ],
            ),
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="1500",
                        client_transaction_id="6",
                        event_datetime=offset_datetime(2019, 2, 10),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="1500",
                        event_datetime=offset_datetime(2019, 2, 10, 0, 0, 0, 1),
                        final=True,
                        client_transaction_id="6",
                    )
                ],
            ),
            SubTest(
                description="Partial repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100", event_datetime=offset_datetime(2019, 2, 22, 1)
                    )
                ],
            ),
            SubTest(
                description="Check 2nd MAD accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 1, 0, 1, 0): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("477.44"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("4100"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("2500"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("111.44"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_BILLED"),
                                Decimal("200"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="1000",
                        client_transaction_id="7",
                        event_datetime=offset_datetime(2019, 3, 1, 2),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="1000",
                        event_datetime=offset_datetime(2019, 3, 1, 2, 0, 0, 1),
                        final=True,
                        client_transaction_id="7",
                    )
                ],
            ),
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="300",
                        client_transaction_id="8",
                        event_datetime=offset_datetime(2019, 3, 10),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="300",
                        event_datetime=offset_datetime(2019, 3, 10, 0, 0, 0, 1),
                        final=True,
                        client_transaction_id="8",
                    )
                ],
            ),
            SubTest(
                description="Partial repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="200", event_datetime=offset_datetime(2019, 3, 22, 1)
                    )
                ],
            ),
            SubTest(
                description="Check 3rd MAD accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 4, 1, 0, 1, 0): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("827.06"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("277.44"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("6600"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("1300"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("159.18"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_UNPAID"),
                                Decimal("111.44"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_BILLED"),
                                Decimal("200"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="500",
                        client_transaction_id="9",
                        event_datetime=offset_datetime(2019, 4, 10),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="500",
                        event_datetime=offset_datetime(2019, 4, 10, 0, 0, 0, 1),
                        final=True,
                        client_transaction_id="9",
                    )
                ],
            ),
            SubTest(
                description="Partial repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="200",
                        event_datetime=offset_datetime(2019, 4, 22, 1),
                    )
                ],
            ),
            SubTest(
                description="Check 4th MAD accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 5, 1, 0, 1, 0): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("1344.31"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("549.62"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_2",
                                ),
                                Decimal("77.44"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("7900"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("500"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("162.63"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_UNPAID"),
                                Decimal("270.62"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_BILLED"),
                                Decimal("200"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="1000",
                        client_transaction_id="10",
                        event_datetime=offset_datetime(2019, 5, 10),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="1000",
                        client_transaction_id="10",
                        final=True,
                        event_datetime=offset_datetime(2019, 5, 10, 0, 0, 0, 1),
                    )
                ],
            ),
            SubTest(
                description="Partial repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="200",
                        event_datetime=offset_datetime(2019, 5, 22, 1),
                    )
                ],
            ),
            SubTest(
                description="Check 5th MAD accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 6, 1, 0, 1, 0): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("2057.20"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("717.25"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_2",
                                ),
                                Decimal("427.06"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("8400"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("185.64"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_UNPAID"),
                                Decimal("433.25"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_BILLED"),
                                Decimal("200"),
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

    def test_no_mad_for_deposit_balance(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 1, 0, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "21"
        instance_params["overlimit"] = "3000"
        instance_params["overlimit_fee"] = "0"
        instance_params["transaction_type_fees"] = dumps(
            {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.02",
                    "flat_fee": "100",
                }
            }
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "6000"}})
        instance_params["late_repayment_fee"] = "0"
        instance_params["annual_fee"] = "0"

        template_params["minimum_percentage_due"] = dumps(
            {
                "purchase": "0.01",
                "cash_advance": "0",
                "balance_transfer": "0",
                "transfer": "0",
                "interest": "1.0",
                "fees": "1.0",
            }
        )
        template_params["minimum_amount_due"] = "200"

        sub_tests = [
            SubTest(
                description="Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10000",
                        client_transaction_id="1234",
                        event_datetime=offset_datetime(2019, 1, 5),
                    )
                ],
            ),
            SubTest(
                description="Settlement",
                events=[
                    create_settlement_event(
                        amount="10000",
                        event_datetime=offset_datetime(2019, 1, 5),
                        final=True,
                        client_transaction_id="1234",
                    )
                ],
            ),
            SubTest(
                description="Initial Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 10),
                    )
                ],
            ),
            SubTest(
                description="Over repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="20000",
                        event_datetime=offset_datetime(2019, 1, 25),
                    )
                ],
            ),
            SubTest(
                description="Check MAD accurate",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 0, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("0"),
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

    def test_scod_schedule_lag_cleanup(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 3, 1, 2)

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

        template_params["transaction_types"] = default_template_update(
            "transaction_types",
            {"cash_advance": {"charge_interest_from_transaction_date": "False"}},
        )
        template_params["minimum_percentage_due"] = dumps(
            {
                "purchase": "0.01",
                "cash_advance": "0.01",
                "transfer": "0.01",
                "interest": "1.0",
                "balance_transfer": "0",
                "fees": "1.0",
            }
        )
        template_params["minimum_amount_due"] = "200"
        template_params["accrue_interest_from_txn_day"] = "False"

        sub_tests = [
            SubTest(
                description="Pre-SCOD 1 Purchase and Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000", event_datetime=offset_datetime(2019, 1, 30, 0)
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 30, 0),
                    ),
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 30, 0): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "PURCHASE_CHARGED",
                                ),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("1000"),
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
                description="Spend during SCOD 1 schedule lag",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=offset_datetime(
                            2019, 2, 1, 0, 0, 0
                        ),  # SCOD runs at 2 secs past
                    )
                ],
            ),
            SubTest(
                description="Repay during SCOD 1 schedule lag",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=offset_datetime(
                            2019, 2, 1, 0, 0, 0, 1
                        ),  # SCOD runs at 2 secs past
                    )
                ],
            ),
            SubTest(
                description="SCOD 1 balances account for interim repayment and spend",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 0, 0, 2): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "STATEMENT_BALANCE",
                                ),
                                Decimal("2100"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1100"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("1100")),
                            (
                                BalanceDimensions(
                                    "PURCHASE_CHARGED",
                                ),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("1000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                Decimal("2000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Pre-SCOD 2 Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000", event_datetime=offset_datetime(2019, 2, 28, 0)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 28, 0): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "PURCHASE_CHARGED",
                                ),
                                Decimal("1000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Over Repay during SCOD 2 schedule lag",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=offset_datetime(
                            2019, 3, 1, 0, 0, 1
                        ),  # SCOD runs at 2 secs past
                    )
                ],
            ),
            SubTest(
                description="SCOD 1 balances account for interim repayment",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 1, 0, 0, 2): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "STATEMENT_BALANCE",
                                ),
                                Decimal("2119.14"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("119.14"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("119.14"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_CHARGED",
                                ),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("INTEREST_PURCHASE_BILLED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("TOTAL_REPAYMENTS_LAST_STATEMENT"),
                                Decimal("2000"),
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

    def test_statement_balance_when_repayments_exceed_spend_and_charges(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 1, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["payment_due_period"] = "22"
        instance_params["transaction_type_fees"] = dumps(
            {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.02",
                    "flat_fee": "100",
                }
            }
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "20000"}})
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
                description="Pre-SCOD Purchase 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000", event_datetime=offset_datetime(2019, 1, 5, 2)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 5, 2): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "PURCHASE_CHARGED",
                                ),
                                Decimal("10000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Pre-SCOD Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 10, 2),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 10, 2): {
                        "Main account": [
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("5000"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Pre-SCOD Repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="20000", event_datetime=offset_datetime(2019, 1, 25, 2)
                    )
                ],
            ),
            SubTest(
                description="SCOD",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "DEPOSIT",
                                ),
                                Decimal("4826.05"),
                            ),
                            (
                                BalanceDimensions(
                                    "STATEMENT_BALANCE",
                                ),
                                Decimal("-4826.05"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("-4826.05"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("-4826.05"),
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

    def test_statement_workflow_context_contains_correct_postings(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 3, 10, 1)

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
                description="Repay",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="4200",
                        client_transaction_id="REPAY1",
                        event_datetime=offset_datetime(2019, 1, 2),
                    )
                ],
            ),
            SubTest(
                description="Cash Advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="4000",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 31),
                        client_transaction_id="CASH1",
                    )
                ],
            ),
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="20",
                        client_transaction_id="TRANSFER1",
                        event_datetime=offset_datetime(2019, 2, 1, 1),
                    )
                ],
            ),
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="30",
                        client_transaction_id="TRANSFER2",
                        event_datetime=offset_datetime(2019, 2, 28),
                    )
                ],
            ),
            SubTest(
                description="Day after SCOD 1",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 10, 1): {
                        "Main account": [(BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0"))]
                    }
                },
            ),
        ]

        sub_tests = [
            SubTest(
                description="Check number of SCOD workflows triggered is correct",
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id=PUBLISH_STATEMENT_DATA_WORKFLOW, count=2
                    )
                ],
            )
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_txn_level_type_statement_balances(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 3, 1, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        annual_percentage_rate = default_template_update(
            "annual_percentage_rate", {"cash_advance": "0.28"}
        )
        base_interest_rates = default_template_update(
            "base_interest_rates", {"cash_advance": "0.36"}
        )

        instance_params["transaction_references"] = dumps({"balance_transfer": ["REF1", "REF2"]})
        instance_params["transaction_annual_percentage_rate"] = dumps(
            {"balance_transfer": {"REF1": "0.25", "REF2": "0.3"}}
        )
        instance_params["transaction_base_interest_rates"] = dumps(
            {"balance_transfer": {"REF1": "0.22", "REF2": "0.28"}}
        )
        instance_params["annual_fee"] = "0"
        instance_params["credit_limit"] = "3000"

        template_params["transaction_types"] = default_template_update(
            "transaction_types",
            {
                "balance_transfer": {"charge_interest_from_transaction_date": "True"},
                "cash_advance": {"charge_interest_from_transaction_date": "True"},
            },
        )
        template_params["base_interest_rates"] = base_interest_rates
        template_params["annual_percentage_rate"] = annual_percentage_rate
        template_params["minimum_percentage_due"] = dumps(
            {
                "purchase": "0.2",
                "cash_advance": "0.2",
                "transfer": "0.2",
                "balance_transfer": "0.2",
                "interest": "1.0",
                "fees": "1.0",
            }
        )

        sub_tests = [
            SubTest(
                description="Initial Balance Check",
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 1, 5): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "DEFAULT",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("3000"),
                            ),
                        ]
                    }
                },
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
                        event_datetime=offset_datetime(2019, 1, 2, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 2, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "DEFAULT",
                                ),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("2000"),
                            ),
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
                        amount="500",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                        event_datetime=offset_datetime(2019, 1, 3, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 3, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "DEFAULT",
                                ),
                                Decimal("1500.60"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("1500"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("500"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0.60"),
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
                        amount="10",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 4, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 4, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "DEFAULT",
                                ),
                                Decimal("1516.58"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("1485"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("500"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("10")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("5"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("1.20"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("0.38"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial repayment 1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500", event_datetime=offset_datetime(2019, 1, 31, 1)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 31, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "DEFAULT",
                                ),
                                Decimal("1043.31"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("1985"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                            # Repaid first
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("17.40"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("10.64"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("10")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0.27"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial repayment 2",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=offset_datetime(2019, 1, 31, 2),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 31, 2): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "DEFAULT",
                                ),
                                Decimal("543.31"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("2485"),
                            ),
                            # Repaid third (partially)
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("510"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("17.40"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("10.64"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            # Repaid second
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0.27"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement 1",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "DEFAULT",
                                ),
                                Decimal("543.62"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("2456.38"),
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
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("510.0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("17.71"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_BILLED"),
                                Decimal("10.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0.27"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("200"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement 2",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 1, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "DEFAULT",
                                ),
                                Decimal("652.30"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("2347.70"),
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
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_UNPAID"),
                                Decimal("510.0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("8.68"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNPAID"),
                                Decimal("17.71"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_UNPAID"),
                                Decimal("10.64"),
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
                                Decimal("0.27"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("444.30"),
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

    def test_mad_rounding_int_acc_from_scod(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 3, 2, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["transaction_type_limits"] = dumps({})
        instance_params["transaction_references"] = dumps({"balance_transfer": ["REF1", "REF2"]})
        instance_params["transaction_annual_percentage_rate"] = dumps(
            {"balance_transfer": {"REF1": "0.5", "REF2": "0.6"}}
        )
        instance_params["transaction_base_interest_rates"] = dumps(
            {"balance_transfer": {"REF1": "0.45", "REF2": "0.55"}}
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
                    "percentage_fee": "0.07",
                    "flat_fee": "2",
                },
            }
        )

        template_params["minimum_amount_due"] = "100"
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
        template_params["transaction_types"] = default_template_update(
            "transaction_types",
            {
                "balance_transfer": {"charge_interest_from_transaction_date": "True"},
                "cash_advance": {"charge_interest_from_transaction_date": "True"},
            },
        )
        template_params["accrue_interest_from_txn_day"] = "False"

        sub_tests = [
            SubTest(
                description="Purchase 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000.25", event_datetime=offset_datetime(2019, 1, 1)
                    )
                ],
            ),
            SubTest(
                description="Cash Advance 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="4000.25",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 31, 20),
                    )
                ],
            ),
            SubTest(
                description="Balance Transfer REF1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1500.33",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                        event_datetime=offset_datetime(2019, 1, 31, 21),
                    )
                ],
            ),
            SubTest(
                description="Balance Transfer REF2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500.77",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                        event_datetime=offset_datetime(2019, 1, 31, 22),
                    )
                ],
            ),
            SubTest(
                description="SCOD 1",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 1): {
                        "Main account": [
                            # Principal contributions to MAD:
                            # PURCHASE: 20.00 CASH_ADVANCE: 40.00  BT REF1: 15.00 BT REF2: 5.00
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("526.64"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("2000.25"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_BILLED"),
                                Decimal("4000.25"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("1500.33"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_BILLED"),
                                Decimal("500.77"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("200.01"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_FEES_BILLED"),
                                Decimal("140.07"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("3.95"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("1.85"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_BILLED"),
                                Decimal("0.75"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000.25", event_datetime=offset_datetime(2019, 2, 1, 10)
                    )
                ],
            ),
            SubTest(
                description="Cash Advance 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="4000.25",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 2, 21, 20),
                    )
                ],
            ),
            SubTest(
                description="SCOD 2",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 2, 1): {
                        "Main account": [
                            # Principal contributions to MAD:
                            # PURCHASE: 40.01 CASH_ADVANCE: 80.01  BT REF1: 15.00 BT REF2: 5.00
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("1701.87"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("2000.25"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("2000.25"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("73.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_BILLED"),
                                Decimal("4000.25"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("200.01"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("142.12"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("4000.25"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("200.01"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("3.95"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_UNPAID"),
                                Decimal("1500.33"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_UNPAID"),
                                Decimal("500.77"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("51.80"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_BILLED"),
                                Decimal("21.00"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNPAID"),
                                Decimal("1.85"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_UNPAID"),
                                Decimal("0.75"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_UNPAID"), Decimal("100")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_FEES_UNPAID"),
                                Decimal("140.07"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_BILLED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("526.64"),
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

    def test_mad_rounding_int_acc_from_txn(self):

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 3, 2, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["credit_limit"] = "30000"
        instance_params["transaction_type_limits"] = dumps({})
        instance_params["transaction_references"] = dumps({"balance_transfer": ["REF1", "REF2"]})
        instance_params["transaction_annual_percentage_rate"] = dumps(
            {"balance_transfer": {"REF1": "0.5", "REF2": "0.6"}}
        )
        instance_params["transaction_base_interest_rates"] = dumps(
            {"balance_transfer": {"REF1": "0.45", "REF2": "0.55"}}
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
                    "percentage_fee": "0.07",
                    "flat_fee": "2",
                },
            }
        )

        template_params["minimum_amount_due"] = "100"
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
        template_params["transaction_types"] = default_template_update(
            "transaction_types",
            {
                "balance_transfer": {"charge_interest_from_transaction_date": "True"},
                "cash_advance": {"charge_interest_from_transaction_date": "True"},
            },
        )

        sub_tests = [
            SubTest(
                description="Purchase 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000.25", event_datetime=offset_datetime(2019, 1, 1)
                    )
                ],
            ),
            SubTest(
                description="Cash Advance 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="4000.25",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 31, 20),
                    )
                ],
            ),
            SubTest(
                description="Balance Transfer REF1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1500.33",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                        event_datetime=offset_datetime(2019, 1, 31, 21),
                    )
                ],
            ),
            SubTest(
                description="Balance Transfer REF2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500.77",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                        event_datetime=offset_datetime(2019, 1, 31, 22),
                    )
                ],
            ),
            SubTest(
                description="SCOD 1",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 1): {
                        "Main account": [
                            # Principal contributions to MAD:
                            # PURCHASE: 20.00 CASH_ADVANCE: 40.00  BT REF1: 15.00 BT REF2: 5.00
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("526.64"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("2000.25"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_BILLED"),
                                Decimal("4000.25"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("1500.33"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_BILLED"),
                                Decimal("500.77"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("200.01"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_FEES_BILLED"),
                                Decimal("140.07"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("3.95"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("1.85"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_BILLED"),
                                Decimal("0.75"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000.25", event_datetime=offset_datetime(2019, 2, 1, 10)
                    )
                ],
            ),
            SubTest(
                description="Cash Advance 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="4000.25",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 2, 21, 20),
                    )
                ],
            ),
            SubTest(
                description="SCOD 2",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 2, 1): {
                        "Main account": [
                            # Principal contributions to MAD:
                            # PURCHASE: 40.01 CASH_ADVANCE: 80.01  BT REF1: 15.00 BT REF2: 5.00
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("1743.03"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("2000.25"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("2000.25"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("114.80"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_BILLED"),
                                Decimal("4000.25"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("200.01"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("142.12"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("4000.25"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("200.01"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("3.95"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_UNPAID"),
                                Decimal("1500.33"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_UNPAID"),
                                Decimal("500.77"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_BILLED"),
                                Decimal("51.80"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_BILLED"),
                                Decimal("21.00"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_UNPAID"),
                                Decimal("1.85"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_UNPAID"),
                                Decimal("0.75"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_UNPAID"), Decimal("100")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_FEES_UNPAID"),
                                Decimal("140.07"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_BILLED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("526.64"),
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

    def test_mad_disregarded_if_repayment_holiday_set_before_scod_and_statement_generated(
        self,
    ):
        """
        Make a purchase, and turn on a repayment holiday ahead of first SCOD following purchase.
        Verify that the MAD is calculated to be 0 on SCOD.
        Verify that the BILLED balance doesn't get transferred to UNPAID on PDD, which means we will
        not charge interest on unpaid interest and fees in the following repayment cycle.
        Check that even if an account is in repayment holiday, the statement still goes out,
        where MAD is set to 0.
        """

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 26, 0, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        template_params["mad_equal_to_zero_flags"] = dumps(["REPAYMENT_HOLIDAY"])
        template_params["overdue_amount_blocking_flags"] = dumps(["REPAYMENT_HOLIDAY"])
        template_params["billed_to_unpaid_transfer_blocking_flags"] = dumps(["REPAYMENT_HOLIDAY"])
        template_params["accrue_interest_from_txn_day"] = "False"

        date_1 = start + timedelta(months=1, days=7)

        sub_tests = [
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500", event_datetime=offset_datetime(2019, 1, 25, 1)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 25, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "DEFAULT",
                                ),
                                Decimal("600"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("1400"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_CHARGED",
                                ),
                                Decimal("500"),
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
                        timestamp=offset_datetime(2019, 1, 26),
                    ),
                    create_flag_event(
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        account_id="Main account",
                        timestamp=offset_datetime(2019, 1, 26),
                        expiry_timestamp=offset_datetime(2019, 7, 26),
                    ),
                ],
            ),
            SubTest(
                # Check MAD is calculated as 0 on SCOD.
                description="After SCOD",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 0, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("1400"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("600")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("600"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("500"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                # Check the BILLED balance hasn't been transferred to UNPAID.
                # The accrued interest is charged because the account has not moved to revolver.
                description="After PDD",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 25, 0, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("1400"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("600")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("607.92"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("500"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("7.92"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_BILLED"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                # Verify that we are now in revolver, and interest is charged daily.
                description="After PDD + 1",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 26, 0, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("1400"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("600")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("608.25"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("500"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("8.25"),
                            ),
                            (
                                BalanceDimensions(
                                    "REVOLVER",
                                ),
                                Decimal("-1"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check number of SCOD workflows triggered is correct",
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id=PUBLISH_STATEMENT_DATA_WORKFLOW,
                        run_times=[date_1],
                        # Check that the context of the smart contract as of SCOD
                        # was correctly added to the workflow context for each month
                        contexts=[
                            {
                                "account_id": "Main account",
                                "current_payment_due_date": "2019-02-24",
                                "minimum_amount_due": "0.00",
                                "start_of_statement_period": "2019-01-01",
                                "end_of_statement_period": "2019-01-31",
                                "current_statement_balance": "600.00",
                                "next_payment_due_date": "2019-03-24",
                                "next_statement_cut_off": "2019-02-28",
                                "is_final": "False",
                            }
                        ],
                        count=1,
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

    def test_mad_disregarded_if_repayment_holiday_set_after_scod(self):
        """
        Make a purchase, and turn on a repayment holiday after first SCOD following purchase.
        Verify that the MAD is calculated to be non-zero on SCOD. However even if the customer
        doesn't pay this sum by PDD, the MAD will still be zeroed by PDD, with no extra fee charged.
        Verify that the BILLED balance doesn't get transferred to UNPAID on PDD, which means we will
        not charge interest on unpaid interest and fees in the following repayment cycle.
        """

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 2, 26, 0, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        template_params["mad_equal_to_zero_flags"] = dumps(["REPAYMENT_HOLIDAY"])
        template_params["overdue_amount_blocking_flags"] = dumps(["REPAYMENT_HOLIDAY"])
        template_params["billed_to_unpaid_transfer_blocking_flags"] = dumps(["REPAYMENT_HOLIDAY"])
        template_params["accrue_interest_from_txn_day"] = "False"

        sub_tests = [
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500", event_datetime=offset_datetime(2019, 1, 25, 1)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 25, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "DEFAULT",
                                ),
                                Decimal("600"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("1400"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_CHARGED",
                                ),
                                Decimal("500"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                # MAD is calculated to be non zero on SCOD.
                description="After SCOD",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 0, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("1400"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("600")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("600"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("500"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("200"),
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
                        timestamp=offset_datetime(2019, 2, 3),
                    ),
                    create_flag_event(
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        account_id="Main account",
                        timestamp=offset_datetime(2019, 2, 3),
                        expiry_timestamp=offset_datetime(2019, 8, 3),
                    ),
                ],
            ),
            SubTest(
                # Check the MAD balance has been zeroed out.
                # Check the BILLED balance hasn't been transferred to UNPAID.
                # The accrued interest is charged because the account has not moved to revolver.
                description="After PDD",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 25, 0, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("1400"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("600")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("607.92"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("500"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("7.92"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_BILLED"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                # Verify that we are now in revolver, and interest is charged daily.
                description="After PDD + 1",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 26, 0, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("1400"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("600")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("608.25"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("500"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("8.25"),
                            ),
                            (
                                BalanceDimensions(
                                    "REVOLVER",
                                ),
                                Decimal("-1"),
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

    def test_existing_billed_balance_not_moved_on_scod_when_suspended_by_flag(self):
        """
        Verify that if we go into an SCOD with some outstanding balance on BILLED addresses,
        (this can happen if the movement of BILLED->UNPAID has been suspended due to active
        repayment holidays), those BILLED balances are left untouched on SCOD.
        """

        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 3, 1, 0, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        template_params["mad_equal_to_zero_flags"] = dumps(["REPAYMENT_HOLIDAY"])
        template_params["overdue_amount_blocking_flags"] = dumps(["REPAYMENT_HOLIDAY"])
        template_params["billed_to_unpaid_transfer_blocking_flags"] = dumps(["REPAYMENT_HOLIDAY"])
        template_params["accrue_interest_from_txn_day"] = "False"

        sub_tests = [
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500", event_datetime=offset_datetime(2019, 1, 25, 1)
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 25, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "DEFAULT",
                                ),
                                Decimal("600"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("1400"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_CHARGED",
                                ),
                                Decimal("500"),
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
                        timestamp=offset_datetime(2019, 1, 26),
                    ),
                    create_flag_event(
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        account_id="Main account",
                        timestamp=offset_datetime(2019, 1, 26),
                        expiry_timestamp=offset_datetime(2019, 7, 26),
                    ),
                ],
            ),
            SubTest(
                # MAD is set to zero on SCOD due to repayment holiday flag.
                description="After SCOD 1",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 1, 0, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("1400"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("600")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("600"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("500"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                # Check the BILLED balance hasn't been transferred to UNPAID.
                # The accrued interest is charged because the account has not moved to revolver.
                description="After PDD 1",
                expected_balances_at_ts={
                    offset_datetime(2019, 2, 25, 0, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("1400"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("600")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("607.92"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("500"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("7.92"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_BILLED"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                # The purchase BILLED address stay the same.
                # Purchase interest has also been moved to BILLED.
                description="After SCOD 2",
                expected_balances_at_ts={
                    offset_datetime(2019, 3, 1, 0, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("1390.76"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("609.24"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("609.24"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_BILLED",
                                ),
                                Decimal("500"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("9.24"),
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

    def test_billed_balance_unaffected_and_overdue_not_aged_on_pdd_but_resumes_after_RH_end(
        self,
    ):
        """
        The customer goes delinquent if they fail to meet their MAD obligations during
        some statement cycle. At which point the unpaid MAD balance moves to OVERDUE_1.
        Normally OVERDUE_* balances gets aged like OVERDUE_1 -> OVERDUE_2 etc on PDD,
        given that the customer remains delinquent.
        Given that there is a repayment holiday issued whilst the customer is already
        delinquent, verify that the customer doesn't go further delinquent on PDD,
        i.e. the overdue buckets are not aged further over multiple statement periods.
        Check that after repayment holiday ends, normal delinquency behaviour has returned -
        overdue buckets are aged & more late repayment fees are charged.
        """
        start = offset_datetime(2019, 1, 1)
        end = offset_datetime(2019, 7, 25, 0, 1)

        instance_params = self.default_instance_params.copy()
        template_params = self.default_template_params.copy()

        instance_params["transaction_type_fees"] = dumps(
            {"cash_advance": {"percentage_fee": "0.02", "flat_fee": "100"}}
        )
        instance_params["transaction_type_limits"] = dumps({"cash_advance": {"flat": "8000"}})

        template_params["mad_equal_to_zero_flags"] = dumps(["REPAYMENT_HOLIDAY"])
        template_params["overdue_amount_blocking_flags"] = dumps(["REPAYMENT_HOLIDAY"])
        template_params["billed_to_unpaid_transfer_blocking_flags"] = dumps(["REPAYMENT_HOLIDAY"])
        template_params["accrue_interest_on_unpaid_fees"] = "True"
        template_params["base_interest_rates"] = default_template_update(
            "base_interest_rates", {"cash_advance": "0.36", "fees": "0.50"}
        )
        template_params["annual_percentage_rate"] = default_template_update(
            "annual_percentage_rate", {"cash_advance": "0.36", "fees": "0.50"}
        )
        template_params["accrue_interest_from_txn_day"] = "False"

        sub_tests = [
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=offset_datetime(2019, 1, 25, 1),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 25, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "DEFAULT",
                                ),
                                Decimal("600"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("1400"),
                            ),
                            (
                                BalanceDimensions(
                                    "PURCHASE_CHARGED",
                                ),
                                Decimal("500"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash advance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        instruction_details={"transaction_code": "aaa"},
                        event_datetime=offset_datetime(2019, 1, 25, 2),
                    )
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 1, 25, 2): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "DEFAULT",
                                ),
                                Decimal("1200"),
                            ),
                            (
                                BalanceDimensions(
                                    "AVAILABLE_BALANCE",
                                ),
                                Decimal("800"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("500")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                        ]
                    }
                },
            ),
            # After PDD 3 MAD is shown as the aggregate of overdue buckets.
            SubTest(
                description="After PDD 3",
                expected_balances_at_ts={
                    offset_datetime(2019, 4, 25, 0, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("500"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("19.47"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_UNPAID"),
                                Decimal("200"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("500")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("32.34"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEE_INTEREST_UNPAID"),
                                Decimal("4.90"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("1011.63"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("461.81"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_2",
                                ),
                                Decimal("336.39"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_3",
                                ),
                                Decimal("213.43"),
                            ),
                        ]
                    }
                },
            ),
            # Set the repayment holiday and take note of current levels of charged interest.
            SubTest(
                description="Bank issues repayment holiday",
                events=[
                    create_flag_definition_event(
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        timestamp=offset_datetime(2019, 4, 26),
                    ),
                    create_flag_event(
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        account_id="Main account",
                        timestamp=offset_datetime(2019, 4, 26),
                        expiry_timestamp=offset_datetime(2019, 6, 26),
                    ),
                ],
                expected_balances_at_ts={
                    offset_datetime(2019, 4, 26, 1): {
                        "Main account": [
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("12.25"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEE_INTEREST_CHARGED"),
                                Decimal("3.50"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEE_INTEREST_CHARGED"),
                                Decimal("3.63"),
                            ),
                        ]
                    }
                },
            ),
            # See that interest is charged on all unpaid balances (including interest and fees)
            # following an accrual event.
            SubTest(
                description="Check after one more accrual event",
                expected_balances_at_ts={
                    offset_datetime(2019, 4, 27, 1): {
                        "Main account": [
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("12.74"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEE_INTEREST_CHARGED"),
                                Decimal("3.64"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEE_INTEREST_CHARGED"),
                                Decimal("3.90"),
                            ),
                        ]
                    }
                },
            ),
            # After SCOD 4 MAD is zero whilst the overdue buckets are untouched,
            # due to active repayment holiday.
            SubTest(
                description="After SCOD 4",
                expected_balances_at_ts={
                    offset_datetime(2019, 5, 1, 0, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("500"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("19.47"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_UNPAID"),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("461.81"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_2",
                                ),
                                Decimal("336.39"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_3",
                                ),
                                Decimal("213.43"),
                            ),
                        ]
                    }
                },
            ),
            # MAD stays zero at PDD 4. Overdue buckets are untouched.
            # This is due to active repayment holiday.
            SubTest(
                description="After PDD 4",
                expected_balances_at_ts={
                    offset_datetime(2019, 5, 25, 0, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("500"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("19.47"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_UNPAID"),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("461.81"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_2",
                                ),
                                Decimal("336.39"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_3",
                                ),
                                Decimal("213.43"),
                            ),
                        ]
                    }
                },
            ),
            # MAD stays zero even after several periods. Overdue buckets are untouched.
            # This is due to active repayment holiday.
            SubTest(
                description="After PDD 5",
                expected_balances_at_ts={
                    offset_datetime(2019, 6, 25, 0, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("500"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("19.47"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_UNPAID"),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("461.81"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_2",
                                ),
                                Decimal("336.39"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_3",
                                ),
                                Decimal("213.43"),
                            ),
                        ]
                    }
                },
            ),
            # The repayment holiday flag was set to expire after PDD 5.
            # Check that following PDD 6, normal delinquency behaviour has returned.
            # Overdue buckets are aged & more late repayment fees are charged.
            # Note that the newest overdue bucket has gone lower than the last one -
            # this is merely because MAD is capped at the statement balance on PDD.
            SubTest(
                description="After PDD 6",
                expected_balances_at_ts={
                    offset_datetime(2019, 7, 25, 0, 1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    "PURCHASE_UNPAID",
                                ),
                                Decimal("500"),
                            ),
                            (
                                BalanceDimensions(
                                    "MAD_BALANCE",
                                ),
                                Decimal("1648.06"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("49.50"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_UNPAID"),
                                Decimal("300"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_1",
                                ),
                                Decimal("636.43"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_2",
                                ),
                                Decimal("461.81"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_3",
                                ),
                                Decimal("336.39"),
                            ),
                            (
                                BalanceDimensions(
                                    "OVERDUE_4",
                                ),
                                Decimal("213.43"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("1784.14"),
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
